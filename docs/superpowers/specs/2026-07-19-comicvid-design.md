# comicvid — Static Images to Animated Video CLI

**Goal:** Extract AIComics rendering engine into a standalone `pip install` CLI tool that converts a folder of images into a Ken Burns zoom video with ASS subtitles + audio sync. Zero API cost, pure FFmpeg + Python.

**Target user:** Content creators, comic artists, indie devs who need to batch produce video from still images.

**Key differentiator:** Single-command, professional ASS subtitles baked in (not SRT), audio sync, pip installable. Unlike `kburns-slideshow` (SRT only, no song) or `ffmpeg-ai` (API-dependent, vertical-only).

## CLI

```bash
$ pip install comicvid

$ comicvid render ./panels/ \
    --output episode.mp4 \
    --duration 30 \
    --subtitle captions.srt \
    --audio narration.wav \
    --width 1280 --height 720

$ comicvid render ./panels/ \
    --output vertical.mp4 \
    --duration 60 \
    --resolution 1080x1920
```

## Architecture

```
src/comicvid/
├── __init__.py          # version
├── cli.py               # Click CLI entry point
├── render.py            # scene rendering + Ken Burns
├── subtitle.py          # SRT/ASS generation
├── audio.py             # re-encode + sync
├── pipeline.py          # orchestrate scenes → concat → burn subtitles
└── types.py             # Config dataclass

tests/
├── test_render.py
├── test_subtitle.py
└── test_pipeline.py

demo/                    # example images + output
```

**Core logic:** Same as AIComics video_synthesis but:
- Input: image folder (sorted by filename) + optional subtitle file + optional audio file
- No episode metadata / JSON config — just file-in, video-out
- Simpler batch mode: `comicvid batch ./episode*/` (auto-find subfolders)

## Tech Stack

- Python 3.10+ / Click / FFmpeg subprocess
- No PyPI deps beyond Click
- ASS subtitle styling (28px Chinese font, black stroke, bottom-center)
- Ken Burns: `zoompan=z='1+0.05*t/N':d=N:s=WxH:fps=24`
- Audio: AAC 44100 Hz mono re-encode
- Concat: FFmpeg concat demuxer for scene assembly

## Files

- `pyproject.toml` — setuptools build, `comicvid` CLI entry point
- `README.md` — GIF demo, install, usage, examples
- `LICENSE` — Apache 2.0
- `demo/` — sample images from E01 (3 panels) + output example

## Release

1. Push to `github.com/chfr19820610-cell/comicvid`
2. PyPI publish via `pypi-publish` workflow
3. Demo GIF in README
4. 2-3 example commands in README
