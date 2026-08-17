<div align="center">

<img src="./assets/wrenify.png" alt="Wrenify" width="140" />

# Wrenify

**A local-first karaoke studio with real-time pitch correction.**

*Your voice. Perfected.*

[![Python](https://img.shields.io/badge/python-3.11+-8B5CF6?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-desktop-B4FF39?style=flat-square&logo=qt&logoColor=black)](https://pypi.org/project/PyQt6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-8B5CF6?style=flat-square)](./LICENSE)
[![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)]()

</div>

---

> ⚠️ **Heads up:** Wrenify is being built in public as a learning project.  
> It's my first serious Python backend project, moving from JS/TS-land.  
> Expect breaking changes, bugs, and questionable commits.

## What is this?

Wrenify is a **local desktop app** that lets you sing along to a song  
and cleans up your voice in real-time using pitch correction (auto-tune).  
It shows synced lyrics as you sing and can export the final performance  
as an MP4 video with webcam overlay.

Everything runs **on your own machine**. No cloud. No account. No telemetry.

## Why?

I sing as a hobby but I'm not great at hitting notes. Existing karaoke apps  
either need internet, are on mobile only, look ugly, or want a subscription.  
I wanted something I could run on my Arch Linux setup, tweak the code of,  
and actually understand end-to-end.

Also — I've been writing JavaScript and TypeScript for years and wanted a  
real backend-heavy Python project to learn from. This checks every box:  
real-time audio, DSP, threading, native UI, file I/O, video processing.

## Planned Features

- 🎤 Real-time pitch correction using the WORLD vocoder
- 📝 Time-synced lyrics with word-level highlighting
- 🎨 Stylized display for held notes (e.g. `faaall-eeen  treeee`)
- 📹 Webcam capture during performance
- 🎬 Final export to MP4 with your corrected voice
- 🎛️ Adjustable correction strength (natural → T-Pain)
- 🎹 Key and scale selection (major, minor, pentatonic, blues)
- 🐧 Runs on Linux, first-class support for Arch

## Current Status

This project is in **early development**. Here's where I'm at:

| Module              | Status         |
| ------------------- | -------------- |
| Project scaffold    | 🚧 In progress |
| Audio capture       | 🚧 In progress |
| Auto-tune engine    | 🚧 In progress |
| Lyrics fetching     | ⏳ Planned     |
| Speech recognition  | ⏳ Planned     |
| PyQt6 UI            | ⏳ Planned     |
| Webcam integration  | ⏳ Planned     |
| MP4 export          | ⏳ Planned     |

Follow the commits if you want to watch me learn Python in real-time.

## Tech Stack

| Concern         | Choice                          | Why                             |
| --------------- | ------------------------------- | ------------------------------- |
| Language        | Python 3.11+                    | Best DSP/audio ecosystem        |
| UI              | PyQt6                           | Native desktop, no browser      |
| Audio I/O       | sounddevice + PortAudio         | Low latency, cross-platform     |
| Pitch engine    | pyworld (WORLD vocoder)         | Industry-grade quality          |
| Audio analysis  | librosa                         | Solid pitch detection           |
| Effects         | pedalboard                      | Spotify's audio processing lib  |
| Speech-to-text  | Vosk                            | Offline, word-level timestamps  |
| Lyrics          | syncedlyrics + lyricsgenius     | Free, no keys required          |
| Video           | OpenCV + moviepy                | Battle-tested                   |
| Package manager | Poetry                          | Feels like npm/yarn             |

## Installation

### Requirements

- Python 3.11 or newer
- A microphone
- A webcam (optional, only for video export)
- ~500 MB disk space
- Linux, macOS, or Windows (developed on Arch Linux)

### System dependencies

**Arch Linux / Manjaro:**
```bash
sudo pacman -S python python-pip portaudio ffmpeg \
  qt6-base qt6-multimedia opencv cmake base-devel git
```

**Ubuntu / Debian:**
```bash
sudo apt install python3.11 python3-pip portaudio19-dev \
  ffmpeg qt6-base-dev libopencv-dev cmake build-essential git
```

**macOS (Homebrew):**
```bash
brew install python@3.11 portaudio ffmpeg qt@6 opencv
```

### Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

### Clone and install

```bash
git clone https://github.com/MrRishabThapa/wrenify.git
cd wrenify
poetry install
poetry shell
```

### Optional: Vosk model for speech recognition

The small English model is ~40 MB and works fine for karaoke:

```bash
mkdir -p models && cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
rm vosk-model-small-en-us-0.15.zip
cd ..
```

### Configuration

Create a `.env` file in the project root:

```env
# Optional — only for fetching lyrics from Genius
GENIUS_TOKEN=your_token_here

# Set to true for verbose logs
DEBUG=false
```

Get a free Genius API token at [genius.com/api-clients](https://genius.com/api-clients).

## Usage

```bash
# Launch the app
poetry run wrenify

# Or use the interactive CLI menu
python -m wrenify

# Test individual components
python wrenify/audio/capture.py                # Test your mic
python wrenify/audio/autotune.py my_voice.wav  # Auto-tune a WAV file
```

## Project Structure

```
wrenify/
├── pyproject.toml
├── LICENSE
├── README.md
├── .env
│
└── wrenify/
    ├── main.py               # Entry point
    │
    ├── core/
    │   ├── config.py         # All settings, one file
    │   └── engine.py         # Master orchestrator
    │
    ├── audio/
    │   ├── capture.py        # Real-time mic input
    │   ├── autotune.py       # WORLD vocoder pitch correction
    │   └── effects.py        # Reverb, compression, EQ
    │
    ├── lyrics/
    │   ├── fetcher.py        # Fetch synced .lrc lyrics
    │   ├── parser.py         # Parse LRC timestamps
    │   └── phonetic.py       # "fallen" → "faaall-eeen"
    │
    ├── speech/
    │   └── recognizer.py     # Vosk offline STT
    │
    ├── video/
    │   ├── camera.py         # OpenCV webcam
    │   └── exporter.py       # Final MP4 export
    │
    ├── ui/
    │   ├── app.py            # PyQt6 main window
    │   └── widgets.py        # Custom widgets
    │
    └── tests/
```

## Configuration

All defaults live in `wrenify/core/config.py`. The stuff you'll actually  
want to tweak:

```python
# Auto-tune correction strength
CONFIG.autotune.strength = 0.7   # 0.0 = natural, 1.0 = T-Pain

# Musical key and scale for correction
CONFIG.autotune.key   = "C"
CONFIG.autotune.scale = "major"   # major | minor | pentatonic | blues

# Audio quality
CONFIG.audio.sample_rate = 44100
CONFIG.audio.chunk_size  = 4096
```

## Roadmap

**Phase 1 — Foundation** *(current)*
- [x] Project setup with Poetry
- [ ] Real-time audio capture
- [ ] WORLD vocoder auto-tune engine
- [ ] CLI-based testing

**Phase 2 — Lyrics**
- [ ] Fetch synced .lrc lyrics
- [ ] Parse and display in real-time
- [ ] Phonetic stretching for held notes

**Phase 3 — Speech alignment**
- [ ] Vosk integration for word recognition
- [ ] Match spoken words to lyric positions
- [ ] Highlight current word as you sing

**Phase 4 — UI**
- [ ] PyQt6 main window
- [ ] Song search and library
- [ ] Live karaoke view
- [ ] Effects rack panel

**Phase 5 — Video export**
- [ ] Webcam capture
- [ ] Composite video with lyrics overlay
- [ ] MP4 export via ffmpeg

**Phase 6 — Polish**
- [ ] Preset library (voice presets)
- [ ] Multi-track recording
- [ ] AppImage / Flatpak packaging
- [ ] Windows and macOS testing

## Contributing

This is a personal learning project, but if you spot bugs or have  
suggestions, open an issue. PRs welcome for anything on the roadmap.

Before submitting:
```bash
poetry install --with dev
poetry run ruff check .
poetry run pytest
```

## FAQ

**Why not just use Smule / Voloco / [insert app here]?**  
Those are great, but they're not open source, need internet, and I can't  
tweak them. Wrenify is for me and anyone else who wants to own their setup.

**Will this work on my machine?**  
Developed and tested on Arch Linux. Should work on Ubuntu, Fedora, macOS.  
Windows is not a priority but might work.

**Is my voice sent to any server?**  
No. Everything runs locally. The only network calls are for fetching  
lyrics (optional) if you provide a Genius API token.

**Can I use this commercially?**  
Yes — it's MIT licensed. Just include the copyright notice.

## Why "Wrenify"?

The **Wren** is one of the smallest birds in the world, yet has one of  
the loudest and most intricate songs relative to its size. A single wren  
can be heard from over 500 meters away.

That's the idea: small setup, massive presence.

## License

MIT © 2025 [Rishab Thapa](https://github.com/MrRishabThapa)

---

<div align="center">

Built with 🎵 on Arch Linux

</div>
