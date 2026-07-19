"""
Configuration constants for the video synthesis pipeline.
"""

from pathlib import Path

# ── System paths ──────────────────────────────────────────────────────────
SYSTEM_ROOT = Path("/Users/eric/Desktop/herness/AIComics/10_System")
FFMPEG = Path("/Users/eric/.local/bin/ffmpeg")

# Asset directories — each episode has images/ and audio/ subdirectories
LOCAL_PROVIDER_DIR = SYSTEM_ROOT / "state" / "local_provider_output"
DEMO_ASSETS_DIR = SYSTEM_ROOT / "state" / "demo_assets"

# Output directories
OUTPUT_DIR = SYSTEM_ROOT / "state" / "releases"
TEMP_DIR = Path("/tmp") / "video_synthesis"

# ── Video quality — 1080p @ 30fps ─────────────────────────────────────────
FPS = 30
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_SIZE = f"{VIDEO_WIDTH}:{VIDEO_HEIGHT}"
VIDEO_SIZE_X = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"

# Bitrate — increased for 1080p
VIDEO_BITRATE = "4000k"       # 1080p 30fps (up from 1500k @ 720p)
AUDIO_SAMPLE_RATE = 44100
AUDIO_BITRATE = "128k"
CRF = 23                      # H.264 quality (lower = better, 18-28 typical)

# ── Audio Enhancement ──────────────────────────────────────────────────────
# Enable voice audio enhancement (compression + EQ + normalization)
AUDIO_ENHANCE_ENABLED = True
# Debug output directory for enhanced audio (None = disabled)
AUDIO_ENHANCE_DEBUG_DIR = None  # set to SYSTEM_ROOT / "state" / "enhanced_audio" for debug

# BGM settings
BGM_ENABLED = True
BGM_VOLUME = 0.35       # BGM volume relative to voice (0.0-1.0, 0.35 ≈ 7:3 voice:bgm)
BGM_FADE_IN = 2.0       # BGM fade-in duration (seconds)
BGM_FADE_OUT = 3.0      # BGM fade-out duration (seconds)

# ── LUT color grading ─────────────────────────────────────────────────────
# Path to .cube LUT file for cinematic color grading.
# Set to None to skip LUT application.
LUT_PATH = SYSTEM_ROOT / "assets" / "luts" / "cinematic_warm.cube"

# ── Ken Burns ─────────────────────────────────────────────────────────────
KEN_BURNS_ZOOM_MAX = 1.05     # 100% → 105%
DEFAULT_SCENE_DURATION = 5.0  # fallback when no audio and no explicit duration

# ── Subtitle styling — 1080p enhanced ─────────────────────────────────────
SUBTITLE_FONT_SIZE = 36       # 1080p: larger text (was 28 @ 720p)
SUBTITLE_BORDER_SIZE = 3      # thicker stroke for readability (was 2)
SUBTITLE_FONT = "PingFang SC" # macOS Chinese system font

# ── Episode definitions ───────────────────────────────────────────────────
# Subtitles for each episode's scenes (empty string = no subtitle)
EPISODE_SUBTITLES = {
    "E01": [
        "这份方案，是你这种实习生能碰的吗？",
        "如果我能证明这不是我的错呢？",
        "谁批准你们动她的？",
        "她的身份，你还没资格问。",
        "",  # S05 — no dialogue
        "",  # S06 — no dialogue
    ],
    "E02": [
        "你以为换个地方就安全了？",
        "我从不依赖运气。",
        "你到底还瞒了多少事？",
        "够了，全都给我住手！",
        "",  # S05
        "",  # S06
    ],
    "E03": [
        "这次计划，我们必须万无一失。",
        "信任不是用嘴说的，是用行动证明的。",
        "她不会同意的。",
        "那就让她不得不同意。",
        "你疯了……你这是要把所有人都拖下水。",
        "这个局，才刚刚开始。",
    ],
    "E04": [
        "我警告过你别插手。",
        "可惜，我这人最不听劝。",
        "你到底站在哪一边？",
        "我只站在真相这一边。",
        "那就看看谁先撑不住。",
        "奉陪到底。",
    ],
    "E05": [
        "一切都结束了。",
        "不，一切才刚刚开始。",
        "他们来了多少人？",
        "这不重要，重要的是我们已经准备好了。",
        "你们可别拖我后腿。",
        "那就走着瞧。",
    ],
}

# Asset source mapping: which directory to use for each episode
# local_provider_output has E01-E03, demo_assets has E04-E05
ASSET_SOURCE = {
    "E01": LOCAL_PROVIDER_DIR,
    "E02": LOCAL_PROVIDER_DIR,
    "E03": LOCAL_PROVIDER_DIR,
    "E04": DEMO_ASSETS_DIR,
    "E05": DEMO_ASSETS_DIR,
}
