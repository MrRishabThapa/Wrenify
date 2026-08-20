"""
Wrenify — Audio playback for instrumental tracks.

Plays MP3/WAV/OGG files through the system speakers.
Provides accurate playback position for lyric synchronization.

Uses sounddevice for output (already in the project for input).
pydub handles MP3 decoding.

Thread-safe position queries so the Timeline can sync to real audio.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
import sounddevice as sd
import soundfile as sf
from loguru import logger


@dataclass
class PlaybackInfo:
    """Snapshot of current playback state."""

    position_sec: float          # Where in the song we are
    duration_sec: float          # Total song length
    is_playing:   bool
    is_paused:    bool


class AudioPlayer:
    """
    Plays an audio file through speakers with accurate position tracking.

    Design:
    - Loads full file into memory (songs are typically 3-6 MB uncompressed)
    - Streams to sounddevice in a background thread
    - Position tracked by counting samples written to output
    - Pause/resume via a threading Event

    Usage:
        player = AudioPlayer()
        player.load("instrumental.mp3")
        player.play()
        # ... later ...
        print(f"At {player.position_sec():.2f}s of {player.duration_sec():.2f}s")
        player.stop()
    """

    # How many samples to write per callback (small = low latency, more CPU)
    BLOCK_SIZE: int = 1024

    def __init__(self, output_device: Optional[int] = None) -> None:
        self.output_device = output_device

        self._audio: Optional[np.ndarray] = None
        self._sample_rate: int = 44100
        self._channels: int = 2
        self._duration: float = 0.0

        self._stream: Optional[sd.OutputStream] = None
        self._playback_thread: Optional[threading.Thread] = None
        self._position_samples: int = 0
        self._lock = threading.Lock()

        self._paused = threading.Event()
        self._stopped = threading.Event()
        self._stopped.set()  # Not playing initially

    def load(self, path: Union[Path, str]) -> None:
        """Load an audio file."""
        audio, sr = self._load_file(path)
        self._audio = audio
        self._sample_rate = sr
        self._channels = self._audio.shape[1]
        self._duration = len(self._audio) / self._sample_rate
        logger.info(f"Loaded {Path(path).name}: {self._duration:.2f}s")

    def _load_file(self, path: Union[Path, str]) -> tuple[np.ndarray, int]:
        """Helper to load audio via soundfile or pydub."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        try:
            audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
        except Exception:
            audio, sr = self._load_via_pydub(path)
        return audio, sr

    def switch_track(self, new_path: Union[Path, str]) -> None:
        """
        Seamlessly swap the audio track being played while maintaining
        current playback position. (e.g. Instrumental <-> Original)
        """
        logger.info(f"Seamlessly switching track to: {Path(new_path).name}")
        new_audio, sr = self._load_file(new_path)

        if sr != self._sample_rate:
            logger.warning("Sample rate mismatch during hot-swap, resampling...")
            import librosa

            # Resample needs shape (channels, samples); librosa expects
            # (samples,) for mono. Both tracks are typically 44.1k from demucs.
            new_audio = librosa.resample(
                new_audio.T, orig_sr=sr, target_sr=self._sample_rate
            ).T

        with self._lock:
            self._audio = new_audio
            self._channels = self._audio.shape[1]
            self._duration = len(self._audio) / self._sample_rate
            # Ensure position doesn't exceed new duration (should be same length anyway)
            self._position_samples = min(self._position_samples, len(self._audio) - 1)

    @staticmethod
    def _load_via_pydub(path: Path) -> tuple[np.ndarray, int]:
        """Load MP3 or other formats via pydub (uses ffmpeg)."""
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(path))
        sr = audio.frame_rate

        # Convert to numpy: pydub gives int16, we want float32
        samples = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
        else:
            samples = samples.reshape((-1, 1))

        # Normalize int16 to float32 -1.0 to 1.0
        samples = samples.astype(np.float32) / 32768.0

        return samples, sr

    def play(self, start_position_sec: float = 0.0) -> None:
        """Start playback from the given position."""
        if self._audio is None:
            raise RuntimeError("No audio loaded")

        if not self._stopped.is_set():
            logger.warning("Already playing")
            return

        # Reset state
        with self._lock:
            self._position_samples = int(start_position_sec * self._sample_rate)
        self._stopped.clear()
        self._paused.clear()

        # Start playback thread
        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            name="audio-player",
            daemon=True,
        )
        self._playback_thread.start()
        logger.info(f"Playback started from {start_position_sec:.2f}s")

    def _playback_loop(self) -> None:
        """Background thread: write audio to output stream."""
        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                device=self.output_device,
            )
            self._stream.start()

            while not self._stopped.is_set():
                # Handle pause
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue

                # Get current position (thread-safe)
                with self._lock:
                    pos = self._position_samples

                # Re-read each iteration so switch_track() hot-swaps work
                total_samples = len(self._audio)

                # End of song?
                if pos >= total_samples:
                    logger.info("Playback reached end of song")
                    break

                # Compute block to write
                end = min(pos + self.BLOCK_SIZE, total_samples)
                block = self._audio[pos:end]

                # Write to output (blocks until played)
                self._stream.write(block)

                # Advance position
                with self._lock:
                    self._position_samples = end

        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._stopped.set()
            logger.info("Playback thread exited")

    def pause(self) -> None:
        """Pause playback (audio stops, position preserved)."""
        self._paused.set()
        logger.info(f"Paused at {self.position_sec():.2f}s")

    def resume(self) -> None:
        """Resume from pause."""
        self._paused.clear()
        logger.info(f"Resumed at {self.position_sec():.2f}s")

    def stop(self) -> None:
        """Stop playback completely."""
        self._stopped.set()
        self._paused.clear()

        if self._playback_thread is not None:
            self._playback_thread.join(timeout=2.0)
            self._playback_thread = None

    def seek(self, position_sec: float) -> None:
        """Jump to a specific position."""
        with self._lock:
            self._position_samples = int(position_sec * self._sample_rate)
        logger.info(f"Seeked to {position_sec:.2f}s")

    def position_sec(self) -> float:
        """Get current playback position in seconds. Thread-safe."""
        with self._lock:
            return self._position_samples / self._sample_rate

    def duration_sec(self) -> float:
        return self._duration

    def is_playing(self) -> bool:
        return not self._stopped.is_set() and not self._paused.is_set()

    def is_finished(self) -> bool:
        return self._stopped.is_set()

    def info(self) -> PlaybackInfo:
        return PlaybackInfo(
            position_sec=self.position_sec(),
            duration_sec=self._duration,
            is_playing=self.is_playing(),
            is_paused=self._paused.is_set(),
        )

    @staticmethod
    def list_output_devices() -> None:
        """Print all available audio output devices."""
        print(sd.query_devices())


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Audio Player Test[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python -m wrenify.audio.player <audio.mp3>")
        console.print("\n[dim]Available output devices:[/dim]")
        AudioPlayer.list_output_devices()
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        console.print(f"[red]File not found:[/red] {audio_path}")
        sys.exit(1)

    player = AudioPlayer()
    player.load(audio_path)

    console.print(f"[green]Duration:[/green] {player.duration_sec():.2f}s")
    console.print("[yellow]Playing for 10 seconds... (Ctrl+C to stop early)[/yellow]\n")

    player.play()

    try:
        start = time.time()
        while time.time() - start < 10 and not player.is_finished():
            pos = player.position_sec()
            dur = player.duration_sec()
            progress = int((pos / dur) * 40) if dur > 0 else 0
            bar = "█" * progress + "░" * (40 - progress)
            console.print(
                f"\r  [magenta]{bar}[/magenta] {pos:.2f}s / {dur:.2f}s",
                end="",
            )
            time.sleep(0.1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    finally:
        player.stop()

    console.print("\n[green]Playback finished[/green]")
