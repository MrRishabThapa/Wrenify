<div align="center">

<img src="./assets/logo.svg" alt="Wrenify" width="160" />

# Wrenify

### *Your voice. Perfected.*

A local-first AI karaoke studio with real-time auto-tune,  
synced lyrics, and webcam recording.

[![Python](https://img.shields.io/badge/python-3.11+-8B5CF6?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-desktop-B4FF39?style=flat-square&logo=qt&logoColor=black)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/license-MIT-8B5CF6?style=flat-square)](./LICENSE)
[![Arch Linux](https://img.shields.io/badge/arch-linux-B4FF39?style=flat-square&logo=arch-linux&logoColor=black)](https://archlinux.org)
[![Status](https://img.shields.io/badge/status-early--development-orange?style=flat-square)]()

</div>

---

## ✨ What is Wrenify?

Wrenify turns your bedroom mic into a studio.  
Pick a song, sing along, and Wrenify handles the rest —  
pitch correction, lyric syncing, and a final video export.

Named after the **Wren** — a small bird with one of the  
loudest, most complex songs in nature relative to its size.  
That's the vibe: small setup, massive presence.

## 🎯 Features

- 🎤 **Real-time Auto-Tune** — WORLD vocoder pitch correction
- 📝 **Synced Lyrics** — Word-level highlighting as you sing
- 🎨 **Stylized Display** — Long notes shown as `faaall-eeen treeee`
- 📹 **Webcam Recording** — Capture the performance
- 🎬 **Video Export** — MP4 with your beautified voice
- 🖥️ **Local-first** — Runs entirely on your machine, no cloud
- 🐧 **Linux native** — Built and tested on Arch Linux

## 🛠️ Tech Stack

| Layer         | Technology                                    |
| ------------- | --------------------------------------------- |
| UI            | PyQt6                                         |
| Audio Capture | sounddevice + PortAudio                       |
| Pitch Engine  | pyworld (WORLD vocoder) + librosa             |
| Effects       | pedalboard (Spotify's audio lib)              |
| Lyrics        | syncedlyrics + lyricsgenius                   |
| Speech-to-Text| Vosk (offline)                                |
| Video         | OpenCV + moviepy + ffmpeg                     |
| Package Mgmt  | Poetry                                        |

## 📦 Installation

### Prerequisites (Arch Linux)

\`\`\`bash
sudo pacman -S python python-pip portaudio ffmpeg \
  qt6-base qt6-multimedia opencv cmake base-devel git

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
\`\`\`

### Prerequisites (Ubuntu / Debian)

\`\`\`bash
sudo apt install python3.11 python3-pip portaudio19-dev \
  ffmpeg qt6-base-dev libopencv-dev cmake build-essential git

curl -sSL https://install.python-poetry.org | python3 -
\`\`\`

### Clone & Install

\`\`\`bash
git clone https://github.com/YOUR_USERNAME/wrenify.git
cd wrenify
poetry install
poetry shell
\`\`\`

### Optional: Vosk Model (for speech recognition)

\`\`\`bash
mkdir -p models && cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
cd ..
\`\`\`

### Environment Variables

Create a `.env` file in the project root:

\`\`\`env
# Optional - only needed for lyrics fetching
GENIUS_TOKEN=your_genius_api_token_here

# Debug mode
DEBUG=false
\`\`\`

Get a free Genius token at [genius.com/api-clients](https://genius.com/api-clients).

## 🚀 Usage

\`\`\`bash
# Launch Wrenify
poetry run wrenify

# Or run modules individually
python -m wrenify                           # Interactive menu
python wrenify/audio/capture.py             # Test mic
python wrenify/audio/autotune.py input.wav  # Auto-tune a file
\`\`\`

## 📂 Project Structure

\`\`\`
wrenify/
├── pyproject.toml
├── README.md
├── .env
│
└── wrenify/
    ├── main.py               # Entry point
    │
    ├── core/
    │   ├── config.py         # All settings
    │   └── engine.py         # Master orchestrator
    │
    ├── audio/
    │   ├── capture.py        # Real-time mic input
    │   ├── autotune.py       # WORLD vocoder pitch correction
    │   └── effects.py        # Reverb, compression
    │
    ├── lyrics/
    │   ├── fetcher.py        # Fetch synced .lrc lyrics
    │   ├── parser.py         # Parse LRC timestamps
    │   └── phonetic.py       # Stylize: "fallen" → "faaall-eeen"
    │
    ├── speech/
    │   └── recognizer.py     # Vosk offline STT
    │
    ├── video/
    │   ├── camera.py         # OpenCV webcam
    │   └── exporter.py       # moviepy MP4 export
    │
    ├── ui/
    │   ├── app.py            # PyQt6 main window
    │   └── widgets.py        # Custom widgets
    │
    └── tests/
\`\`\`

## 🗺️ Roadmap

- [x] Project scaffold + Poetry setup
- [x] Real-time audio capture
- [x] WORLD vocoder auto-tune engine
- [ ] Synced lyrics fetching & parsing
- [ ] Phonetic stretching engine
- [ ] Vosk speech recognition integration
- [ ] Word-to-lyrics real-time alignment
- [ ] PyQt6 main window
- [ ] Webcam integration
- [ ] Final MP4 export pipeline
- [ ] Effects rack (reverb, EQ, compression)
- [ ] Song library management
- [ ] Multi-track recording

## 🎛️ Configuration

All settings live in `wrenify/core/config.py`. Common tweaks:

\`\`\`python
# Auto-tune strength
CONFIG.autotune.strength = 0.7    # 0.0 natural → 1.0 T-Pain

# Musical key
CONFIG.autotune.key   = "C"
CONFIG.autotune.scale = "major"   # major, minor, pentatonic, blues

# Audio quality
CONFIG.audio.sample_rate = 44100
CONFIG.audio.chunk_size  = 4096
\`\`\`

## 🤝 Contributing

This is a personal hobby project, but PRs are welcome.  
Open an issue first if you want to add something big.

\`\`\`bash
# Dev setup
poetry install --with dev
poetry run ruff check .
poetry run pytest
\`\`\`

## 📜 License

MIT © [Rishab Thapa](https://github.com/MrRishabThapa)

## 🐦 Why "Wrenify"?

> The **Wren** is one of the smallest birds in the world, yet has  
> one of the loudest, most intricate songs relative to its body size.  
> A single wren can be heard from over 500 meters away.
>  
> That's what Wrenify does for your voice.  
> Small setup. Massive presence.

---

<div align="center">

**Built with 🎵 on Arch Linux**

</div>
