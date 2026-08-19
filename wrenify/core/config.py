"""
Wrenify Global Configuration

Single source of truth for all app settings.
Import anywhere with:  from wrenify.core.config import CONFIG

Tuned for 8GB RAM systems. See docstrings for override guidance.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ─────────────────── Paths ───────────────────
ROOT_DIR   = Path(__file__).parent.parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
EXPORT_DIR = ROOT_DIR / "exports"
MODELS_DIR = ROOT_DIR / "models"

# Ensure directories exist
EXPORT_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)


# ────────────── Config Dataclasses ──────────────

@dataclass
class AudioConfig:
    """
    Real-time audio capture settings.

    On 8GB systems, we cap the queue at 30 chunks (~2.8 seconds
    of buffered audio at 4096-sample chunks / 44.1kHz).
    """

    sample_rate:    int = 44100
    chunk_size:     int = 4096
    channels:       int = 1
    dtype:          str = "float32"
    device_index:   int | None = None
    max_queue_size: int = 30       # Reduced from 50 for 8GB systems


@dataclass
class AutoTuneConfig:
    """WORLD vocoder pitch correction settings."""

    enabled:  bool  = True
    strength: float = 0.7      # 0.0 = natural, 1.0 = T-Pain
    key:      str   = "C"
    scale:    str   = "major"  # major | minor | pentatonic | blues


@dataclass
class LyricsConfig:
    """Lyrics fetching and display settings."""

    genius_token: str  = os.getenv("GENIUS_TOKEN", "")
    language:     str  = "en"
    stylize:      bool = True


@dataclass
class VideoConfig:
    """
    Webcam capture and video export settings.

    On 8GB systems, defaults are 960x540 @ 24fps to reduce
    both RAM usage and CPU load for encoding.

    A single 720p frame = ~2.7MB uncompressed.
    A single 540p frame = ~1.5MB uncompressed (44% smaller).

    Bump to 1280x720 @ 30 on systems with 16GB+.
    """

    webcam_index:  int  = int(os.getenv("WEBCAM_INDEX", "0"))
    fps:           int  = 24        # Reduced from 30 for 8GB systems
    width:         int  = 960       # Reduced from 1280 for 8GB systems
    height:        int  = 540       # Reduced from 720 for 8GB systems
    codec:         str  = "libx264"
    audio_codec:   str  = "aac"
    preset:        str  = "fast"
    export_format: str  = "mp4"


@dataclass
class SpeechConfig:
    """
    Speech recognition settings for faster-whisper.

    Tuned for 8GB RAM + CPU-only systems:
    - base model: 74MB disk, ~800MB RAM, 5-7x realtime speed
    - int8 quantization: smallest CPU footprint
    - beam_size 5: better accuracy when singing (slower than 1)
    - 5-second chunks with 1.5s overlap: better word continuity

    For 16GB+ systems, override in .env:
        WHISPER_MODEL=small
        WHISPER_COMPUTE_TYPE=int8

    For CUDA GPU:
        WHISPER_DEVICE=cuda
        WHISPER_COMPUTE_TYPE=float16
        WHISPER_MODEL=medium (or large-v3)
    """

    model_size:   str  = os.getenv("WHISPER_MODEL", "base")
    device:       str  = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type: str  = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    language:     str  = "en"
    beam_size:    int  = 5     # Increased for accuracy (was 1)

    # Streaming settings
    chunk_duration_sec: float = 5.0   # Was 4.0
    overlap_sec:        float = 1.5   # Was 0.5 (much more overlap)

    # Model cache directory
    model_cache_dir: str = str(MODELS_DIR / "whisper")


@dataclass
class AppConfig:
    audio:    AudioConfig    = field(default_factory=AudioConfig)
    autotune: AutoTuneConfig = field(default_factory=AutoTuneConfig)
    lyrics:   LyricsConfig   = field(default_factory=LyricsConfig)
    video:    VideoConfig    = field(default_factory=VideoConfig)
    speech:   SpeechConfig   = field(default_factory=SpeechConfig)
    debug:    bool           = os.getenv("DEBUG", "false").lower() == "true"


# ─────────────── Singleton ───────────────
CONFIG = AppConfig()
