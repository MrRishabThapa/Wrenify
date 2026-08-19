<div align="center">

<img src="./assets/wrenify.png" alt="Wrenify" width="140" />

# Wrenify

**A local-first karaoke studio with pitch correction.**

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

Wrenify is a **local desktop karaoke app**. You pick a song from your
library, sing along to the instrumental with synced lyrics on screen,
and hit **Record** — your voice gets mixed with the music into a
performance you can replay, auto-tune, and export.

Everything runs **on your own machine**. No cloud. No account. No telemetry.
No judging — there's no score, no grade. It's just for fun singing.

## Why?

I sing as a hobby but I'm not great at hitting notes. Existing karaoke apps  
either need internet, are on mobile only, look ugly, or want a subscription.  
I wanted something I could run on my Arch Linux setup, tweak the code of,  
and actually understand end-to-end.

Also — I've been writing JavaScript and TypeScript for years and wanted a  
real backend-heavy Python project to learn from. This checks every box:  
real-time audio, DSP, threading, native UI, file I/O, video processing.

## Features

- [x] 🎤 Karaoke sessions: instrumental playback + synced lyric subtitles
- [x] 📝 Time-synced lyrics with current-line highlighting (bright current, dimmed around)
- [x] 📚 In-app song library with card grid (songs live in `songs/<slug>/`)
- [x] 📥 One-URL song import (YouTube link or file path → Demucs stems + Whisper LRC)
- [x] ⏺ Recordings library: every take auto-saves on session end
- [x] 🎚️ Auto-tune toggle — pitch-corrects the voice (WORLD vocoder) before saving
- [x] 🎵 Instrumental mixed into recordings — playback sounds like a real performance
- [x] 🗂️ Up to 6 versions per recording (voice/mixed × raw/auto-tuned, + videos)
- [x] 📦 Styled export dialog with a version matrix (Audio/Video, With Music/Voice Only)
- [x] 📹 Webcam capture with video versions of your take
- [x] 🎛️ Adjustable correction strength (natural → T-Pain)
- [x] 🎹 Key and scale selection (major, minor, pentatonic, blues)
- [x] 🐧 Runs on Linux, first-class support for Arch

## Current Status

The core loop is **complete and working end-to-end** — import a song,
sing it, save your take, export it. Most of the UI is real now, not placeholders.

| Module                 | Status         |
| ---------------------- | -------------- |
| Project scaffold       | Done           |
| Audio capture          | Done           |
| Auto-tune engine       | Done           |
| Effects rack           | Done           |
| Webcam capture         | Done           |
| MP4 export (ffmpeg)    | Done           |
| Lyrics fetching/parsing| Done           |
| Song library + import  | Done           |
| Karaoke session        | Done           |
| Lyric line tracking    | Done           |
| Recordings library     | Done           |
| Music mixing           | Done           |
| Export dialog matrix   | Done           |
| Real-time auto-tune UI | Planned        |
| Packaging / polish     | Planned        |

Follow the commits to watch the project evolve.

## Tech Stack

| Concern         | Choice                          | Why                             |
| --------------- | ------------------------------- | ------------------------------- |
| Language        | Python 3.11+                    | Best DSP/audio ecosystem        |
| UI              | PyQt6                           | Native desktop, no browser      |
| Audio I/O       | sounddevice + PortAudio         | Low latency, cross-platform     |
| Pitch engine    | pyworld (WORLD vocoder)         | Industry-grade quality          |
| Audio analysis  | librosa                         | Solid pitch detection           |
| Effects         | pedalboard                      | Spotify's audio processing lib  |
| Audio mixing    | numpy + soundfile               | Simple, dependency-free         |
| Speech-to-text  | faster-whisper                  | Offline LRC generation on import|
| Lyrics          | syncedlyrics + lyricsgenius     | Free, no keys required          |
| Video           | OpenCV + ffmpeg                 | Battle-tested                   |
| Package manager | Poetry                          | Feels like npm/yarn             |

## Installation

### Requirements

- Python 3.11 or newer
- A microphone
- A webcam (optional, only for video versions)
- ffmpeg on your PATH (for video export)
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

### Optional: Whisper model for song import

Song import can generate a `.lrc` file from the vocals using Whisper.
The `base` model (~74 MB) downloads automatically on first use to
`models/whisper/`. You don't need it for karaoke or recording — only
for importing songs without existing lyrics.

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
# Launch the app (GUI)
poetry run wrenify

# Or the CLI menu (tests + app launcher)
python -m wrenify

# Test individual components
python wrenify/audio/capture.py                # Test your mic
python wrenify/audio/autotune.py my_voice.wav  # Auto-tune a WAV file
```

### Singing a song

1. **Library** (sidebar → Songs) — pick a song card. Songs live in
   `songs/<slug>/` as `instrumental.*` + `lyrics.lrc` (+ optional
   `meta.json`, `cover.jpg`).
2. **Import** (sidebar → Import) — paste a YouTube URL or a local file
   path. The full pipeline splits vocals from the instrumental (Demucs)
   and generates a synced `.lrc` (Whisper), then it appears in the library.
3. **Ready screen** — live webcam preview; raise an open palm and close
   it into a fist (or click **I'm Ready**) to start the 3-2-1 countdown.
4. **Sing** — the instrumental plays while lyric subtitles highlight
   in sync. Current line is bright white, previous/next lines dimmed —
   no overlays, no colors to worry about.
5. **Record** — press `R` or **⏺ Record** to capture your voice
   (webcam frames too, if the camera is on). Toggle **✨ Auto-Tune**
   before or during recording to pitch-correct the voice on save.
6. **End** — the session ends when the song finishes, or via **⏹ End**.
   Your take auto-saves to the recordings library.

**Wear headphones** — otherwise the mic picks up the song audio and
bleeds into your recording.

### Recordings

Every take is saved under `recordings/<artist>_<title>_<timestamp>/`:

```
├── voice_raw.wav        mic only
├── voice_autotuned.wav  pitch-corrected mic (if auto-tune was on)
├── mixed_raw.wav        voice + music          ← default playback
├── mixed_autotuned.wav  auto-tuned voice + music
├── video_raw.mp4        webcam + mixed audio   (if webcam)
├── video_autotuned.mp4  webcam + autotuned mix (if webcam)
└── meta.json
```

The instrumental slice is matched to your recording using the song
position when you pressed Record — so the mix lines up with the music.

- **Playback** — cards show *With Music* and *Voice Only* buttons for
  raw and auto-tuned versions.
- **Export** — the ⤓ Export button opens a styled dialog with an
  Audio/Video matrix; unavailable versions are grayed out.
- **Delete** — with confirmation.

Keyboard shortcuts during karaoke:

| Key        | Action                    |
| ---------- | ------------------------- |
| `R`        | Start/stop recording      |
| `Space`    | Pause/resume              |
| `←` / `→`  | Nudge lyrics sync ±0.5s   |
| `⏮ 5s` / `⏭ 5s` | Seek back/forward    |

### CLI menu (python -m wrenify)

Quick entry points for testing components: mic level, auto-tune a WAV,
effects, webcam preview, video export, lyrics parse/fetch, phonetic
stretcher, instrumental fetch, LRC generation, full song import, and
the library listing. Option **11** launches the GUI.

## Project Structure

```
wrenify/
├── pyproject.toml
├── LICENSE
├── README.md
├── .env
│
└── wrenify/
    ├── main.py               # Entry point (banner + CLI menu)
    │
    ├── core/
    │   └── config.py         # All settings, one file
    │
    ├── audio/
    │   ├── capture.py        # Real-time mic input
    │   ├── autotune.py       # WORLD vocoder pitch correction
    │   ├── mixer.py          # Voice + instrumental mixing
    │   ├── player.py         # Instrumental playback + position tracking
    │   └── effects.py        # Reverb, compression, EQ
    │
    ├── songs/
    │   ├── song.py           # Instrumental + lyrics pairing
    │   ├── full_import.py    # Demucs + Whisper pipeline
    │   └── lrc_generator.py  # Whisper → .lrc
    │
    ├── lyrics/
    │   ├── fetcher.py        # Fetch synced .lrc lyrics
    │   ├── parser.py         # Parse LRC timestamps
    │   └── phonetic.py       # "fallen" → "faaall-eeen"
    │
    ├── karaoke/
    │   ├── session.py        # Session orchestrator (audio + video)
    │   ├── timeline.py       # Master clock + word timing
    │   └── matcher.py        # LyricTracker — current line only, no scoring
    │
    ├── recordings/
    │   ├── manager.py        # Save/load/delete recordings, video mux
    │   └── models.py         # Recording model (6 version paths)
    │
    ├── speech/
    │   └── recognizer.py     # faster-whisper offline STT (import time)
    │
    ├── video/
    │   ├── camera.py         # OpenCV webcam
    │   └── exporter.py       # MP4 export
    │
    ├── vision/
    │   └── gestures.py       # Palm/fist gesture for "I'm Ready"
    │
    ├── ui/
    │   ├── app.py            # PyQt6 main window + navigation
    │   ├── library_view.py   # Song card grid
    │   ├── import_view.py    # URL/path import with progress log
    │   ├── pre_karaoke_view.py # Ready screen (gesture + countdown)
    │   ├── karaoke_view.py   # Webcam + lyric overlay + control bar
    │   ├── recordings_view.py# Recordings grid
    │   ├── results_view.py   # SessionEndView — "Great session!"
    │   ├── theme.py          # Colors, glass styling, global QSS
    │   ├── voice_visualizer.py # Mic level bars
    │   └── widgets/
    │       ├── glass.py      # GlassCard, PillButton, GradientBackground
    │       ├── song_card.py  # Library card
    │       ├── recording_card.py # Recording card (play/export/delete)
    │       ├── export_dialog.py  # Version matrix export dialog
    │       └── log_panel.py  # Import progress log
    │
    └── tests/                # Offscreen smoke tests
```

## Configuration

All defaults live in `wrenify/core/config.py`. The stuff you'll actually  
want to tweak:

```python
# Auto-tune correction strength (applied when saving recordings)
CONFIG.autotune.strength = 0.7   # 0.0 = natural, 1.0 = T-Pain

# Musical key and scale for correction
CONFIG.autotune.key   = "C"
CONFIG.autotune.scale = "major"   # major | minor | pentatonic | blues

# Audio quality
CONFIG.audio.sample_rate = 44100
CONFIG.audio.chunk_size  = 4096
```

## Roadmap

**Phase 1 — Foundation** *(done)*
- [x] Project setup with Poetry
- [x] Real-time audio capture
- [x] WORLD vocoder auto-tune engine
- [x] CLI-based testing

**Phase 2 — Lyrics** *(done)*
- [x] Fetch synced .lrc lyrics
- [x] Parse and display in real-time
- [x] Phonetic stretching for held notes

**Phase 3 — Karaoke sessions** *(done)*
- [x] Instrumental playback + player-synced timeline
- [x] Lyric line highlighting (no scoring — Wrenify is for fun)
- [x] Webcam capture with gesture-triggered countdown

**Phase 4 — Recording**
- [x] Record mic + webcam during a session
- [x] Auto-save to recordings library on session end
- [x] Music mixing + auto-tune post-processing (6 versions)
- [x] Styled export dialog with version matrix
- [ ] Real-time auto-tune (currently applied on save)

**Phase 5 — Song library**
- [x] In-app library with song cards
- [x] One-URL import (YouTube/file → Demucs + Whisper)
- [ ] Effects rack panel
- [ ] Preset library (voice presets)

**Phase 6 — Polish** *(current)*
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

**Where's the scoring?**  
There isn't any, by design. Singing badly is fun — Wrenify records your
take, lets you auto-tune it, and never tells you off.

**Will this work on my machine?**  
Developed and tested on Arch Linux. Should work on Ubuntu, Fedora, macOS.  
Windows is not a priority but might work.

**Is my voice sent to any server?**  
No. Everything runs locally. The only network calls are for fetching  
lyrics or importing songs (optional).

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