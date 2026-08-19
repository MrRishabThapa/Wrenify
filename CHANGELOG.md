# Changelog

All notable changes to Wrenify are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- (Nothing yet)

## [0.1.0] - 2025-08-19

**First public release!**

### Added
- Complete karaoke pipeline with real-time lyric sync
- YouTube URL import (via yt-dlp)
- Vocal separation via Demucs AI
- Automatic lyrics generation via faster-whisper
- Hybrid LRC mode (Genius text + Whisper timing)
- WORLD vocoder auto-tune (post-processing)
- Recording with voice + instrumental mixing
- 6 export versions per recording:
  - Voice raw
  - Voice auto-tuned
  - Mixed (voice + music) raw
  - Mixed auto-tuned
  - Video raw
  - Video auto-tuned
- MediaPipe hand gesture detection (open palm → fist)
- Voice level visualizer
- Liquid glass UI (PyQt6)
- In-app song library
- In-app recordings library
- Custom export dialog with organized matrix
- First-run setup wizard
- CLI subcommands: import, library, info, setup
- Windows support (experimental)
- Cross-platform: Linux (Arch, Ubuntu, Fedora) + Windows

### Changed
- Removed scoring system — karaoke is for fun, not judgment

### Fixed
- Windows console window popups during subprocess calls
- Long path issues on Windows
- Various platform-specific bugs

### Known Issues
- Whisper transcription 90-95% accurate (imperfect)
- Demucs takes 5-15 min per song on CPU
- Windows install requires 30-45 minutes setup

## Development Milestones

- **2025-08-05**: Project started (first Python project)
- **2025-08-12**: Core karaoke engine working
- **2025-08-15**: Full song import via Demucs
- **2025-08-17**: Recording + auto-tune added
- **2025-08-18**: UI redesigned with liquid glass
- **2025-08-19**: v0.1.0 released