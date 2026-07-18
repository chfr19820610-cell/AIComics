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
                "voice": "windows_tts_placeholder",
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

