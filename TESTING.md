# Wrenify Testing Guide

How to test every module of Wrenify on your machine.

## Prerequisites

- Poetry environment installed: `poetry install`
- A microphone (options 1, 2, 5, 7)
- A webcam (options 4, 5)
- Network access (option 9, and the first speech run)
- ~3GB free RAM for speech recognition

## Quick sanity checks

```bash
poetry run ruff check .                        # lint
poetry run python -c "from wrenify.core.config import CONFIG; print(CONFIG)"  # config loads
poetry show                                    # all dependencies installed
```

## Interactive menu (test everything)

```bash
poetry run wrenify
```

| Option | What it tests | Requires |
| ------ | ------------- | -------- |
| 1      | Mic level meter (5s) | microphone |
| 2      | Auto-tune a WAV file | a .wav file |
| 3      | Effects (reverb, compression) | a .wav file |
| 4      | Webcam preview | webcam |
| 5      | Webcam + mic recording -> MP4 | webcam + mic |
| 6      | Speech-to-text batch | a .wav file |
| 7      | Live speech streaming (15s) | microphone |
| 8      | LRC lyrics parser | optional .lrc file (blank = sample) |
| 9      | Fetch lyrics online | network |
| 10     | Phonetic word stretcher | nothing |

## Module by module (standalone)

### Audio

```bash
poetry run python -m wrenify.audio.capture                # 5s mic test
arecord -f cd -d 10 -r 16000 test.wav                    # record speech
poetry run python -m wrenify.audio.autotune test.wav     # -> test_wrenified.wav
poetry run python -m wrenify.audio.effects test.wav      # -> test_fx.wav
```

Expected: output WAVs are audible, pitch-corrected (auto-tune) and
effect-processed (FX) versions of the input.

### Video

```bash
poetry run python -m wrenify.video.camera                # live preview (q to quit)
poetry run python -m wrenify.video.exporter              # 5s recording -> exports/*.mp4
```

Expected: preview shows webcam feed with FPS overlay; export produces a
playable MP4 with audio track.

### Speech

```bash
poetry run python -m wrenify.speech.recognizer test.wav  # batch, word timestamps
poetry run python -m wrenify.speech.streaming            # 15s live, ~1-2s delay
```

First run downloads the Whisper `base` model (~74MB) to `models/whisper/`.
Subsequent runs load from cache.

Expected: word-level timestamp table; streaming shows words in green with
1-2 second delay. Monitor RAM in a second terminal:

```bash
watch -n 1 'free -h | head -2'   # RAM should stay under 3GB
```

### Lyrics

```bash
poetry run python -m wrenify.lyrics.parser               # built-in sample LRC
poetry run python -m wrenify.lyrics.parser exports/coldplay_yellow.lrc  # real file
poetry run python -m wrenify.lyrics.fetcher "Yellow" "Coldplay"         # live fetch
poetry run python -m wrenify.lyrics.phonetic             # stretching table
```

Expected: parser shows metadata + timed lines with correct lookup at
various positions; fetcher returns synced LRC (type `y` to save to
`exports/`); phonetic shows words stretched proportional to duration.

### UI

```bash
poetry run python -m wrenify.ui.app                      # or: poetry run python -c "from wrenify.ui.app import run; run()"
```

Expected: dark studio window with sidebar (Studio, Auto-Tune, Speech,
Lyrics, Video), status bar showing audio/whisper config, welcome page
chips reflecting current config.

## Known limitations

- `pytest` currently has no real tests (test files are stubs)
- Lyrics fetcher depends on third-party providers; Musixmatch may
  rate-limit, but syncedlyrics falls back to NetEase/LRCLIB/Genius
- Mic/webcam tests need actual hardware access (PipeWire on Arch)
- Speech streaming is CPU-bound: expect ~1-2s latency on 8GB systems
