#!/usr/bin/env python3
"""重建单集（P6 音画对齐版）

读取 runs/{ep}/alignment.json（由 align_episode.py 生成），其中已包含：
- 每镜的 frames / request_sec / actual_sec（按时长对齐）
- SRT 用 TTS 精确时长（天然对齐）
- 景别降级记录（避免口型暴露）

用法: python scripts/rebuild_episode.py E01 E02 ...
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
FFMPEG = "/Users/eric/.local/bin/ffmpeg"


def fmt_srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def build_episode(ep):
    print(f"\n=== {ep} ===", flush=True)
    run_dir = D / "runs" / ep
    align_path = run_dir / "alignment.json"

    if align_path.exists():
        align = json.loads(align_path.read_text(encoding="utf-8"))
        plan = align["plan"]
        srt_entries = align["srt"]
        total = align["total_seconds"]
        print(f"  用对齐计划: {len(plan)} 镜 / {total:.1f}s", flush=True)
    else:
        # 回退：老逻辑
        shots_path = D / "shots" / f"{ep}_70.json"
        if not shots_path.exists():
            shots_path = D / "shots" / f"{ep}.json"
        shots_doc = json.loads(shots_path.read_text(encoding="utf-8"))
        shots = shots_doc["shots"]
        plan = [{"shot_id": s["shot_id"], "has_dialogue": bool((s.get("dialogue") or "").strip()),
                 "dialogue": (s.get("dialogue") or "").strip(), "actual_sec": 3.0,
                 "start": i * 3.0, "end": (i + 1) * 3.0}
                for i, s in enumerate(shots)]
        srt_entries = [{"idx": i + 1, "start": p["start"], "end": p["end"], "text": p["dialogue"]}
                       for i, p in enumerate(plan) if p["has_dialogue"]]
        total = len(shots) * 3.0
        print(f"  回退模式: {len(plan)} 镜 / {total:.1f}s", flush=True)

    audio_dir = run_dir / "audio_new"
    cut_dir = run_dir / "cut"
    audio_dir.mkdir(parents=True, exist_ok=True)
    cut_dir.mkdir(parents=True, exist_ok=True)

    # 1) SRT（用 TTS 精确时长）
    srt_text = "\n".join(
        f"{e['idx']}\n{fmt_srt_time(e['start'])} --> {fmt_srt_time(e['end'])}\n{e['text']}\n"
        for e in srt_entries
    )
    srt_path = cut_dir / f"{ep}_r2.srt"
    srt_path.write_text(srt_text, encoding="utf-8")
    print(f"  SRT: {len(srt_entries)} 条", flush=True)

    # 2) 配音轨：逐句合成后按 start 对位拼接
    tracks = [p for p in plan if p["has_dialogue"]]
    mixed = audio_dir / f"{ep}_mixed.wav"

    # 【修复 2026-11-16】先检查 wav 是否已存在且时长正确 → 跳过 TTS
    # 背景：原代码无条件跑 batch_piper，一旦 TTS 卡住就阻塞 rebuild（实测卡 6.5 分钟 CPU 0%）
    skip_tts = False
    if tracks and mixed.exists() and mixed.stat().st_size > 1000:
        try:
            import re as _re
            _r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mixed)],
                                capture_output=True, text=True, timeout=30)
            _m = _re.search(r"Duration: (\d+):(\d+):([\d.]+)", _r.stderr)
            if _m:
                _dur = int(_m.group(1)) * 3600 + int(_m.group(2)) * 60 + float(_m.group(3))
                if abs(_dur - total) < 5:  # 时长接近（±5s）则认为有效
                    skip_tts = True
                    print(f"  ✅ 复用现有音频 {_dur:.1f}s（跳过 TTS）", flush=True)
                else:
                    print(f"  ⚠️ 现有音频 {_dur:.1f}s ≠ 目标 {total:.1f}s → 重新合成", flush=True)
        except Exception as _e:
            print(f"  ⚠️ 检查现有音频失败: {_e} → 重新合成", flush=True)

    if tracks and not skip_tts:
        # 用 batch_piper 生成（每句按 start 对位）
        plan_path = audio_dir / f"{ep}_plan.json"
        plan_path.write_text(json.dumps({
            "episode_code": ep,
            "tracks": [{"shot_id": p["shot_id"], "text": p["dialogue"],
                        "start": p["start"], "end": p["end"],
                        "voice": "zh_CN-chaowen-medium"} for p in tracks]
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        bp = BASE / "scripts" / "batch_piper.py"
        model = BASE / "local_providers" / "piper" / "models" / "zh_CN-chaowen-medium.onnx"
        # 【修复 2026-11-17】关键：HF_HUB_OFFLINE=1 让 transformers 不联网
        # 根因：piper 的 g2pw 走 transformers，会尝试从 huggingface.co（被墙）下载 → 卡住 600s
        # 实测：无离线标志 → 卡 600s 超时；有离线标志 → 172s 完成 23/23 条
        tts_env = os.environ.copy()
        tts_env["HF_HUB_OFFLINE"] = "1"
        tts_env["TRANSFORMERS_OFFLINE"] = "1"
        tts_ok = False
        try:
            r = subprocess.run([str(BASE / ".venv/bin/python"), str(bp),
                                "--plan", str(plan_path), "--output", str(mixed),
                                "--model", str(model), "--total-seconds", str(int(total) + 1)],  # +1 防 int() 截断丢尾音
                               capture_output=True, text=True, timeout=900, env=tts_env)
            print(r.stdout[-400:] if r.stdout else "", flush=True)
            tts_ok = (r.returncode == 0)
        except subprocess.TimeoutExpired:
            print("  ❌ TTS 超时 900s", flush=True)

        # 【修复 2026-11-17】TTS 失败/超时 → 删除残缺 wav，让下面生成静音轨
        # 原 bug：超时后留下 18s 残缺 wav，ffmpeg --shortest 把成片截成 20s
        if not tts_ok and mixed.exists():
            try:
                mixed.unlink()
                print("  🗑️ 删除残缺音频 → 将生成静音轨", flush=True)
            except Exception:
                pass

    # 【修复 2026-11-17】不只用 size 判断，还要验证时长是否接近 total
    # 原 bug：775K 的 18s 残缺 wav 通过 size>1000 检查 → 成片被截成 20s
    need_silence = True
    if mixed.exists() and mixed.stat().st_size > 1000:
        try:
            import re as _re2
            _r2 = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mixed)],
                                 capture_output=True, text=True, timeout=30)
            _m2 = _re2.search(r"Duration: (\d+):(\d+):([\d.]+)", _r2.stderr)
            if _m2:
                _d2 = int(_m2.group(1)) * 3600 + int(_m2.group(2)) * 60 + float(_m2.group(3))
                if _d2 >= total - 5:  # 时长足够
                    need_silence = False
                else:
                    print(f"  ⚠️ 音频 {_d2:.1f}s < 目标 {total:.1f}s → 生成静音轨补齐", flush=True)
        except Exception:
            pass
    if need_silence:
        subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                        "-t", str(total), str(mixed)], capture_output=True, timeout=60)
        print(f"  静音轨 {total:.0f}s", flush=True)

    # 3) 视频拼接
    shots_dir = D / "assets" / ep / "h3video"
    concat_list = cut_dir / f"_{ep}_concat_r2.txt"
    missing = []
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in plan:
            vp = shots_dir / f"{ep}_{p['shot_id']}_h3.mp4"
            if vp.exists():
                f.write(f"file '{vp}'\n")
            else:
                missing.append(p["shot_id"])
    if missing:
        print(f"  ⚠️ 缺 {len(missing)} 镜: {missing[:5]}", flush=True)

    # 4) 合成（烧字幕 + 混音）
    final = cut_dir / "final_r2.mp4"
    srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    style = ("FontSize=14,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
             "BorderStyle=1,Outline=2,Alignment=2,MarginV=20")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
           "-i", str(mixed),
           "-vf", f"subtitles='{srt_esc}':force_style='{style}'",
           "-c:v", "libx264", "-preset", "medium", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-t", str(total), str(final)]  # 【修复 2026-11-17】--shortest 会按短流截断（音频残缺 → 成片 20s），改成 -t 强制时长
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(f"  ❌ 合成失败: {r.stderr[-300:]}", flush=True)
        return False
    print(f"  ✅ final_r2.mp4 ({final.stat().st_size/1024/1024:.1f}M)", flush=True)
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    # 支持 -h / --help（否则会把 --help 当成 episode 名去读文件）
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        print("依赖：runs/{ep}/alignment.json（由 align_episode.py 生成）")
        print("产物：runs/{ep}/cut/final_r2.mp4（烧字幕+混音）")
        sys.exit(0)
    eps = args if args else ["E01"]
    ok = 0
    for ep in eps:
        if build_episode(ep):
            ok += 1
    print(f"\n=== 完成 {ok}/{len(eps)} ===")
