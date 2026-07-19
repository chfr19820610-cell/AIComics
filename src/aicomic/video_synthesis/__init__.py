"""
Video Synthesis Pipeline — Phase 1 MVP.

Based on the verified spike (scripts/video_synthesis_spike.py),
refactored into a formal module with:

- Ken Burns zoom effect (100% → 105%)
- Audio sync (44100 Hz AAC)
- Subtitle burn-in (SRT/ASS)
- 5-episode batch synthesis
- 1500 kbps video bitrate
"""

from aicomic.video_synthesis.pipeline import (
    synthesize_episode,
    verify_video,
)
from aicomic.video_synthesis.batch import (
    batch_synthesize,
    discover_episodes,
)

__all__ = [
    "synthesize_episode",
    "verify_video",
    "batch_synthesize",
    "discover_episodes",
]
