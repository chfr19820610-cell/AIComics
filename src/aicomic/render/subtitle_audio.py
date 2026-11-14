from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any


def build_subtitle_entries(manifest: dict[str, Any], episode_code: str) -> list[dict[str, Any]]:
    episodes = {item["episode_code"]: item for item in manifest.get("episodes", [])}
    episode = episodes[episode_code]
    entries: list[dict[str, Any]] = []
    current_second = 0
    index = 1
    for shot in episode.get("shots", []):
        dialogue = str(shot.get("dialogue", "")).strip()
        duration = int(shot.get("duration", 1))
        if dialogue:
            entries.append(
                {
                    "index": index,
                    "start": current_second,
                    "end": current_second + duration,
                    "text": dialogue,
                    "shot_id": shot["shot_id"],
                }
            )
            index += 1
        current_second += duration
    return entries


def format_srt_timestamp(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"


def write_srt(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for entry in entries:
        blocks.append(
            "\n".join(
                [
                    str(entry["index"]),
                    f"{format_srt_timestamp(entry['start'])} --> {format_srt_timestamp(entry['end'])}",
                    str(entry["text"]),
                ]
            )
        )
    path.write_text("\n\n".join(blocks), encoding="utf-8")


def build_audio_plan(manifest: dict[str, Any], episode_code: str) -> dict[str, Any]:
    entries = build_subtitle_entries(manifest, episode_code)
    return {
        "episode_code": episode_code,
        "track_count": len(entries),
        "tracks": [
            {
                "shot_id": entry["shot_id"],
                "text": entry["text"],
                "start": entry["start"],
                "end": entry["end"],
                "voice": "local_piper_tts",
            }
            for entry in entries
        ],
    }


def write_audio_plan(path: Path, plan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def write_silence_wav(path: Path, duration_seconds: int, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, duration_seconds * sample_rate)
    silence = b"\x00\x00" * frame_count
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


def synthesize_tracks_with_piper(
    plan: dict[str, Any],
    output_path: Path,
    *,
    piper_script: Path,
    model_path: Path,
    config_path: Path,
    python_executable: str = "python3",
    total_seconds: int | None = None,
    sample_rate: int = 22050,
    timeout: int = 120,
) -> dict[str, Any]:
    """用本地 Piper 合成每句台词，按时间轴拼接成整集 WAV。

    这是对 `write_silence_wav` 的真实替代：原实现只产出静音占位，
    导致成片"有字幕没声音"。本函数逐条合成、按 start/end 定位、
    未覆盖区间补静音，最后写成单声道 16-bit PCM。

    Returns: {"ok", "track_count", "total_seconds", "wav_bytes", "errors"}
    """
    import subprocess
    import tempfile

    tracks = list(plan.get("tracks") or [])
    errors: list[str] = []
    rendered: list[tuple[int, bytes]] = []

    for tr in tracks:
        text = str(tr.get("text", "")).strip()
        if not text:
            continue
        start = int(tr.get("start", 0))
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp = Path(tf.name)
            cmd = [
                python_executable, str(piper_script),
                "--model", str(model_path),
                "--config", str(config_path),
                "--output_file", str(tmp),
            ]
            proc = subprocess.run(
                cmd, input=text.encode("utf-8"), stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=timeout,
            )
            if proc.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 1000:
                errors.append(f"{tr.get('shot_id')}: piper rc={proc.returncode} "
                              f"{proc.stderr.decode('utf-8', 'ignore')[:120]}")
                tmp.unlink(missing_ok=True)
                continue
            with wave.open(str(tmp), "rb") as wf:
                sr = wf.getframerate()
                raw = wf.readframes(wf.getnframes())
                ch = wf.getnchannels()
            tmp.unlink(missing_ok=True)
            if ch > 1:  # 取左声道
                import array as _arr
                a = _arr.array("h", raw)
                raw = a[::ch].tobytes()
            if sr != sample_rate:
                # 简单重采样：按比例抽样（够用，避免引入 scipy 依赖）
                import array as _arr
                src = _arr.array("h", raw)
                ratio = sr / sample_rate
                dst = _arr.array("h", (src[int(i * ratio)] if int(i * ratio) < len(src) else 0
                                       for i in range(int(len(src) / ratio))))
                raw = dst.tobytes()
            rendered.append((start, raw))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tr.get('shot_id')}: {type(exc).__name__}: {exc}")

    total = total_seconds or (max((int(t.get("end", 0)) for t in tracks), default=0) or 1)
    total_frames = int(total * sample_rate)
    buf = bytearray(b"\x00\x00" * total_frames)
    for start, raw in rendered:
        offset = int(start * sample_rate) * 2
        end = min(offset + len(raw), len(buf))
        if offset < len(buf):
            buf[offset:end] = raw[: end - offset]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(bytes(buf))

    return {
        "ok": not errors and bool(rendered),
        "track_count": len(rendered),
        "total_seconds": total,
        "wav_bytes": output_path.stat().st_size if output_path.is_file() else 0,
        "errors": errors,
    }
