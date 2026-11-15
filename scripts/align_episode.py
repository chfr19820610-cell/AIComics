#!/usr/bin/env python3
"""音画对齐重建（P6）：先定语音 → 定镜长 → 生成画面 → 字幕天然对齐

工作流（依据 pconline 实战文章 + 实测验证）：
1. 读 70 镜分镜表，提取有台词的镜
2. Piper TTS 逐句合成，记录每句精确时长
3. 有台词的镜：镜长 = 句长 + 留白（0.4s）
   无台词的镜：固定 2.5s（环境/动作）
4. 输出「对齐后的拍摄计划」：每镜的 seconds + 是否有台词 + 建议景别
5. 字幕用 TTS 的精确起止时间 → 天然对齐

口型处理（文章第三步「藏」）：
- 有台词的镜强制景别为：wide / medium / over_shoulder / hand / environment
- 禁止 closeup 用于有台词的镜（否则嘴型随机暴露）

用法:
  python scripts/align_episode.py E01            # 生成对齐计划
  python scripts/align_episode.py E01 --tts      # 同时生成配音
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
MODEL = BASE / "local_providers" / "piper" / "models" / "zh_CN-chaowen-medium.onnx"
PY = BASE / ".venv" / "bin" / "python"

PADDING = 0.4        # 台词后留白
SILENT_SEC = 3.0     # 无台词镜固定时长（3s 是 h3stream 标准镜长）
MIN_SHOT_SEC = 1.5   # 最短镜头
MAX_SHOT_SEC = 6.0   # 最长镜头（h3stream 6s 约 6.58s）

# 有台词镜允许的景别（避开正脸嘴型）
SPEAK_OK_TYPES = {"wide", "medium", "over_shoulder", "hand", "environment", "action"}
# 需要降级的景别（正脸特写会导致口型暴露）
DOWNGRADE = {"closeup": "medium", "extreme_closeup": "medium"}


def frames_for_seconds(sec, mode="nearest"):
    """h3stream 的帧网格 17*n+5

    mode="nearest": 取最接近（默认）
    mode="up": 向上取整（保证不短于请求秒数，用于有台词镜防台词被裁）
    """
    cands = [(17 * n + 5, (17 * n + 5) / 24) for n in range(1, 30)]
    if mode == "up":
        for f, d in cands:
            if d >= sec:
                return (f, d)
        return cands[-1]
    best = None
    for f, d in cands:
        if best is None or abs(d - sec) < abs(best[1] - sec):
            best = (f, d)
    return best


def build_alignment(ep, do_tts=False):
    shots_path = D / "shots" / f"{ep}_70.json"
    if not shots_path.exists():
        print(f"❌ {ep}: 无 70 镜分镜表")
        return False

    doc = json.loads(shots_path.read_text(encoding="utf-8"))
    shots = doc["shots"]
    print(f"\n=== {ep}: {len(shots)} 镜 ===")

    # 1) TTS 测每句时长
    tts_dur = {}
    if do_tts:
        script = BASE / "scripts" / "measure_tts.py"
        if not script.exists():
            print("❌ 缺 scripts/measure_tts.py")
            return False
        lines = {s["shot_id"]: (s.get("dialogue") or "").strip()
                 for s in shots if (s.get("dialogue") or "").strip()}
        tmp = Path("/tmp") / f"{ep}_lines.json"
        tmp.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
        out = Path("/tmp") / f"{ep}_tts_dur.json"
        r = subprocess.run([str(PY), str(script), str(tmp), str(out)],
                           capture_output=True, text=True, timeout=1800)
        print(r.stdout[-500:] if r.stdout else "", flush=True)
        if r.returncode != 0:
            print(f"❌ TTS 失败: {r.stderr[-300:]}")
            return False
        tts_dur = json.loads(out.read_text(encoding="utf-8"))

    # 2) 计算每镜时长 + 景别调整
    plan = []
    cursor = 0.0
    srt_entries = []
    changed_type = []

    for s in shots:
        sid = s["shot_id"]
        line = (s.get("dialogue") or "").strip()
        is_speaking = bool(line)
        shot_type = s.get("shot_type", "medium")

        if is_speaking and sid in tts_dur:
            speech = tts_dur[sid]
            # 基础：台词 + padding
            sec = max(MIN_SHOT_SEC, speech + PADDING)
            # 约束：台词占比 ≤85%（保证呼吸感）
            sec = max(sec, speech / 0.85)
            sec = min(MAX_SHOT_SEC, sec)
            frame_mode = "up"   # 有台词镜向上取帧，防止台词被裁
        elif is_speaking:
            est = max(1.2, len(line) / 5.0)
            sec = max(MIN_SHOT_SEC, est + PADDING)
            sec = max(sec, est / 0.85)
            sec = min(MAX_SHOT_SEC, sec)
            frame_mode = "up"
        else:
            sec = SILENT_SEC
            frame_mode = "nearest"

        # 口型处理：有台词的镜禁止正脸特写
        final_type = shot_type
        if is_speaking and shot_type in DOWNGRADE:
            final_type = DOWNGRADE[shot_type]
            changed_type.append((sid, shot_type, final_type))

        f, actual = frames_for_seconds(sec, mode=frame_mode)

        plan.append({
            "shot_id": sid,
            "shot_type_original": shot_type,
            "shot_type_final": final_type,
            "has_dialogue": is_speaking,
            "dialogue": line,
            "speech_sec": tts_dur.get(sid),
            "request_sec": round(sec, 2),
            "frames": f,
            "actual_sec": round(actual, 3),
            "start": round(cursor, 3),
            "end": round(cursor + actual, 3),
            "scene": s.get("scene", "")[:60],
            "camera": s.get("camera", ""),
        })

        # 字幕：用 TTS 精确时长（不用 pad）
        if is_speaking:
            srt_end = cursor + (tts_dur.get(sid) or sec)
            srt_entries.append({
                "idx": len(srt_entries) + 1,
                "start": round(cursor, 3),
                "end": round(srt_end, 3),
                "text": line,
            })

        cursor += actual

    total = cursor
    out = {
        "episode_code": ep,
        "shot_count": len(plan),
        "total_seconds": round(total, 2),
        "total_minutes": round(total / 60, 2),
        "plan": plan,
        "srt": srt_entries,
        "type_downgrades": changed_type,
    }

    out_path = D / "runs" / ep / "alignment.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  总时长: {total:.1f}s ({total/60:.2f} 分钟)")
    print(f"  有台词镜: {sum(1 for p in plan if p['has_dialogue'])}")
    print(f"  景别降级: {len(changed_type)} 镜（避免口型暴露）")
    for sid, o, n in changed_type[:5]:
        print(f"    {sid}: {o} → {n}")
    print(f"  ✅ 对齐计划: {out_path}")
    return True


if __name__ == "__main__":
    eps = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_tts = "--tts" in sys.argv
    if not eps:
        eps = ["E01"]
    for ep in eps:
        build_alignment(ep, do_tts=do_tts)
