"""
Wrenify Global Configuration

Single source of truth for all app settings.
Import anywhere with:  from wrenify.core.config import CONFIG
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
    sample_rate:  int  = 44100
    chunk_size:   int  = 4096
    channels:     int  = 1
    dtype:        str  = "float32"
    device_index: int | None = None


@dataclass
class AutoTuneConfig:
    enabled:  bool  = True
    strength: float = 0.7      # 0.0 = natural, 1.0 = T-Pain
    key:      str   = "C"
    scale:    str   = "major"  # major | minor | pentatonic | blues


@dataclass
class LyricsConfig:
    genius_token: str  = os.getenv("GENIUS_TOKEN", "")
    language:     str  = "en"
    stylize:      bool = True


@dataclass
class VideoConfig:
    webcam_index: int  = int(os.getenv("WEBCAM_INDEX", "0"))
    fps:          int  = 30
    width:        int  = 1280
    height:       int  = 720
    codec:        str  = "libx264"
    audio_codec:  str  = "aac"
    preset:       str  = "fast"
    export_format: str = "mp4"


@dataclass
class AppConfig:
    audio:    AudioConfig    = field(default_factory=AudioConfig)
    autotune: AutoTuneConfig = field(default_factory=AutoTuneConfig)
    lyrics:   LyricsConfig   = field(default_factory=LyricsConfig)
    video:    VideoConfig    = field(default_factory=VideoConfig)
    debug:    bool           = os.getenv("DEBUG", "false").lower() == "true"


# ─────────────── Singleton ───────────────
CONFIG = AppConfig()
