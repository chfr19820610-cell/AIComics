#!/usr/bin/env python3
"""重建单集：TTS(用 batch_piper) + SRT + 合成（3 秒/镜正确时间轴）

用法: python scripts/rebuild_episode.py E01 E02 ...

关键：不能逐条调 piper（每次重新加载模型 2m53s），
必须调 scripts/batch_piper.py（同进程加载一次）。
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
PY = BASE / ".venv" / "bin" / "python"
FFMPEG = "/Users/eric/.local/bin/ffmpeg"
BATCH_PIPER = BASE / "scripts" / "batch_piper.py"
MODEL = BASE / "local_providers" / "piper" / "models" / "zh_CN-chaowen-medium.onnx"

SHOT_SEC = 3.0


def fmt_srt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def build_episode(ep, skip_tts=False):
    print(f"\n=== {ep} ===", flush=True)
    run_dir = D / "runs" / ep
    # 优先用 70 镜版本（P5 扩写版），回退到 6 镜版本
    shots_path = D / "shots" / f"{ep}_70.json"
    if not shots_path.exists():
        shots_path = D / "shots" / f"{ep}.json"
    shots_doc = json.loads(shots_path.read_text(encoding="utf-8"))
    shots = shots_doc["shots"]
    print(f"  使用分镜: {shots_path.name} ({len(shots)} 镜)", flush=True)

    audio_dir = run_dir / "audio_new"
    cut_dir = run_dir / "cut"
    audio_dir.mkdir(parents=True, exist_ok=True)
    cut_dir.mkdir(parents=True, exist_ok=True)

    total = len(shots) * SHOT_SEC

    # 1) 构造 plan（batch_piper 格式）
    tracks = []
    srt_entries = []
    for i, s in enumerate(shots):
        line = (s.get("dialogue") or "").strip()
        if not line:
            continue
        start = int(i * SHOT_SEC)
        end = int(start + SHOT_SEC)
        tracks.append({
            "shot_id": s["shot_id"],
            "text": line,
            "start": start,
            "end": end,
            "voice": "zh_CN-chaowen-medium",
        })
        srt_entries.append({"idx": len(srt_entries) + 1, "start": start, "end": end, "text": line})

    plan_path = audio_dir / f"{ep}_plan.json"
    plan_path.write_text(
        json.dumps({"episode_code": ep, "shot_sec": SHOT_SEC, "tracks": tracks},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  plan: {len(tracks)} 条台词", flush=True)

    # 2) batch_piper 生成配音
    mixed = audio_dir / f"{ep}_mixed.wav"
    if tracks and not skip_tts:
        cmd = [
            str(PY), str(BATCH_PIPER),
            "--plan", str(plan_path),
            "--output", str(mixed),
            "--model", str(MODEL),
            "--total-seconds", str(int(total)),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        print(r.stdout[-500:] if r.stdout else "", flush=True)
        if r.returncode != 0:
            print(f"  WARN batch_piper rc={r.returncode}: {r.stderr[-300:]}", flush=True)
    if not mixed.exists() or mixed.stat().st_size < 1000:
        r = subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
             "-t", str(total), str(mixed)],
            capture_output=True, text=True, timeout=60)
        print(f"  静音轨 {total}s", flush=True)

    # 3) SRT
    srt_text = "\n".join(
        f"{e['idx']}\n{fmt_srt_time(e['start'])} --> {fmt_srt_time(e['end'])}\n{e['text']}\n"
        for e in srt_entries
    )
    srt_path = cut_dir / f"{ep}_r2.srt"
    srt_path.write_text(srt_text, encoding="utf-8")
    print(f"  SRT {len(srt_entries)} 条", flush=True)

    # 4) 拼接视频
    shots_dir = D / "assets" / ep / "h3video"
    concat_list = cut_dir / f"_{ep}_concat_r2.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in shots:
            p = shots_dir / f"{ep}_{s['shot_id']}_h3.mp4"
            if p.exists():
                f.write(f"file '{p}'\n")

    # 5) 合成
    final = cut_dir / "final_r2.mp4"
    srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    style = ("FontSize=14,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
             "BorderStyle=1,Outline=2,Alignment=2,MarginV=20")
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(mixed),
        "-vf", f"subtitles='{srt_esc}':force_style='{style}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(final),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"  FAIL 合成: {r.stderr[-400:]}", flush=True)
        return False
    sz = final.stat().st_size / 1024 / 1024
    print(f"  OK final_r2.mp4 ({sz:.1f}M)", flush=True)
    return True


if __name__ == "__main__":
    if not MODEL.exists():
        print(f"FAIL 模型不存在: {MODEL}")
        sys.exit(1)
    eps = sys.argv[1:] if len(sys.argv) > 1 else ["E01"]
    ok = 0
    for ep in eps:
        if build_episode(ep):
            ok += 1
    print(f"\n=== 完成 {ok}/{len(eps)} ===")
