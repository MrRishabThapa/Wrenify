<div align="center">

<img src="./assets/wrenify.png" alt="Wrenify" width="140" />

# Wrenify

**A local-first karaoke studio with vocal separation, auto-tune, and recording.**

*Your voice. Perfected.*

[![License: MIT](https://img.shields.io/badge/License-MIT-8B5CF6?style=flat-square)](./LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-B4FF39?style=flat-square)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-8B5CF6?style=flat-square)](https://www.python.org)

[Features](#features) · [Install](#installation) · [Usage](#usage) · [FAQ](#faq)

</div>

---

## What is Wrenify?

Wrenify turns any song into a karaoke experience — automatically.

- 🎵 Paste a YouTube URL → get a clean karaoke track with synced lyrics
- 🎤 Sing along with real-time lyric highlighting
- ✨ Optional auto-tune snaps your voice to the song's key
- 📼 Record your performance and export as MP4
- 🐧 Runs 100% locally on your machine — no cloud, no account, no telemetry

## Features

### AI-Powered Song Import
- **Vocal separation** via Meta's Demucs — extract clean instrumentals from any song
- **Lyric transcription** via OpenAI's Whisper — automatic word-level timing
- **Hybrid lyrics** — combines clean text from Genius with AI-timed alignment

### Karaoke Experience
- **Hand gesture control** via MediaPipe — raise hand + close fist to start
- **Real-time lyric sync** — words highlight as they're sung
- **Phonetic stretching** — held notes shown as "faaall-eeeen"
- **Voice visualizer** — see your mic level in real-time

### Recording Studio
- **Optional recording** — toggle during any karaoke session
- **Voice + music mixing** — recordings sound like real performances
- **Post-processing auto-tune** — WORLD vocoder pitch correction
- **6 export versions** — voice/mixed × raw/autotuned × audio/video

### Modern UI
- **Liquid glass design** — beautiful PyQt6 interface
- **Song library** — grid of imported songs
- **Recordings library** — playback and export
- **No file dialogs** — everything managed in-app

## Installation

### Option 1: AppImage (Recommended for Linux)

Download the latest AppImage from [Releases](https://github.com/MrRishabThapa/Wrenify/releases):

```bash
# Download
wget https://github.com/MrRishabThapa/Wrenify/releases/latest/download/Wrenify-x86_64.AppImage

# Make executable
chmod +x Wrenify-x86_64.AppImage

# Install ffmpeg (required for audio processing)
# Arch/Manjaro:
sudo pacman -S ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# Fedora:
sudo dnf install ffmpeg

# Run
./Wrenify-x86_64.AppImage
```

First launch runs a 2-minute setup wizard. After that, just double-click to launch.

### Option 2: From Source (Any Platform)

**Requirements:**
- Python 3.11 or newer
- ffmpeg (system package)
- 8 GB RAM minimum
- 5 GB free disk space

```bash
# Install system dependencies
# Arch:
sudo pacman -S python ffmpeg portaudio git

# Ubuntu/Debian:
sudo apt install python3.11 python3.11-venv ffmpeg portaudio19-dev git

# macOS (with Homebrew):
brew install python@3.11 ffmpeg portaudio git

# Clone repository
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify

# Install Poetry (Python package manager)
curl -sSL https://install.python-poetry.org | python3 -

# Install Wrenify
poetry install

# Launch
poetry run wrenify
```

### Windows Installation

Windows support is experimental and requires manual setup. See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for developer setup notes.

## Usage

### First Launch

1. Run `wrenify` (or double-click the AppImage)
2. Setup wizard checks dependencies (~2 min)
3. UI opens automatically

### Import Your First Song

1. Click **Import** in the sidebar
2. Paste a YouTube URL of the song (with vocals)
3. Enter title and artist
4. Click **Start Import** — wait 10-15 minutes for processing
5. Song appears in **Library**

### Sing Karaoke

1. Click a song card in Library
2. Put on headphones (important!)
3. Click **I'm Ready** or raise your open hand
4. Close your fist → 3-2-1 countdown
5. Sing along as lyrics highlight
6. Optional: Press ⏺ **Record** and ✨ **Auto-Tune**
7. Click ⏹ **End** when done

### Export Your Performance

1. Go to **Recordings** in the sidebar
2. Click ⤓ **Export** on any recording
3. Choose format: audio/video, with/without music, raw/auto-tuned
4. Save to any location

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Linux | Arch, Ubuntu 22.04+, Fedora 38+ |
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8 cores |
| GPU | None (CPU only) | NVIDIA (for faster Demucs) |
| Disk | 5 GB | 20 GB (for song library) |
| Python | 3.11 | 3.12 |

## FAQ

**Q: Does Wrenify need internet?**  
A: Only for downloading songs from YouTube. Everything else runs locally.

**Q: Is my data private?**  
A: Yes. Nothing is uploaded. All recordings stay on your machine.

**Q: Why does importing take so long?**  
A: Demucs vocal separation is CPU-intensive. Expect 5-15 minutes per song on CPU, or ~1 minute with a GPU.

**Q: Can I use existing MP3 files instead of YouTube?**  
A: Yes — click Import and paste a file path instead of a URL.

**Q: The lyrics don't align perfectly with the music. Why?**  
A: Whisper AI transcription is 90-95% accurate. Adjustments coming in future versions.

**Q: Does it work on Windows/macOS?**  
A: Linux is the primary platform. Windows works but requires manual setup. macOS is untested.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines.

Report bugs at [Issues](https://github.com/MrRishabThapa/Wrenify/issues).

## Credits

Built by [Rishab Thapa](https://github.com/MrRishabThapa).

Powered by amazing open source:
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech recognition
- [Demucs](https://github.com/adefossez/demucs) — vocal separation
- [MediaPipe](https://google.github.io/mediapipe/) — hand tracking
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — desktop UI
- [pyworld](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder) — auto-tune
- [pedalboard](https://github.com/spotify/pedalboard) — audio effects
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube downloads

## License

MIT © 2025 Rishab Thapa. See [LICENSE](./LICENSE).
