# Fix: social-auto-upload CLI Dependencies in AIComics venv

## Date
2026-07-19

## Problem
`sau --help` failed with `ModuleNotFoundError: No module named 'requests'` when run with `PYTHONPATH=""`.

## Root Cause
The `sau` CLI entry point is registered in the AIComics venv:
- Location: `/Users/eric/Desktop/herness/AIComics/10_System/.venv/bin/sau`
- It imports `sau_cli` from the social-auto-upload project (editable install via `.pth` file)

The sau dependencies were NOT installed in the AIComics venv's own site-packages. They were being resolved from `/Users/eric/.hermes/hermes-agent/venv/lib/python3.11/site-packages` via the `PYTHONPATH` env var, which caused:
1. Python version mismatch (3.11 vs 3.12) risks
2. Broken resolution when PYTHONPATH was cleared

## Fix Applied
Installed the dependencies into the AIComics venv directly:

```bash
PYTHONPATH="" /Users/eric/Desktop/herness/AIComics/10_System/.venv/bin/pip install \
  "loguru==0.7.3" \
  "patchright==1.58.2" \
  "requests==2.32.3" \
  "segno>=1.6.6" \
  "opencv-python>=4.13.0.92" \
  "qrcode==8.2" \
  "Flask[async]==3.1.1" \
  "flask-cors==6.0.0"
```

(Note: Used `python3 -m pip install -e .` in the social-auto-upload project would also work for a fresh install)

## Verification
```bash
PYTHONPATH="" sau --help
# Output: shows usage with douyin/kuaishou/xiaohongshu/bilibili subcommands ✓
```

## Key Insights
- **`patchright`** (not `playwright`) — the project uses a playwright fork called `patchright==1.58.2`
- **`segno`** — alternative QR library, needed by `utils.login_qrcode`
- **`loguru`** — logging framework, core dependency
- The `pyproject.toml` at `/Users/eric/Desktop/herness/social-auto-upload/pyproject.toml` is the authoritative dependency source (not `requirements.txt`)
- The AIComics venv is the "source of truth" for running `sau` because vf_master_loop uses it
