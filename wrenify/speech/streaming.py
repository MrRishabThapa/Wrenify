"""
Wrenify — Streaming speech recognition.

Wraps SpeechRecognizer for real-time chunk-based processing.
Feeds 4-second overlapping chunks to Whisper and emits words
via callback as they are recognized.

Expected latency on 8GB CPU with 'base' model: ~1-2 seconds.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Callable, Optional

import numpy as np
from loguru import logger

from wrenify.core.config import CONFIG
from wrenify.speech.recognizer import SpeechRecognizer, Word


class StreamingRecognizer:
    """
    Background streaming wrapper for SpeechRecognizer.

    Accumulates audio chunks until we have chunk_duration_sec worth,
    then transcribes in a worker thread. Overlaps chunks by
    overlap_sec to preserve word context across boundaries.

    Usage:
        def on_words(words: list[Word]):
            for w in words:
                print(f"Heard: {w.text}")

        streamer = StreamingRecognizer(on_words_callback=on_words)
        streamer.start()

        with AudioCapture() as cap:
            while running:
                chunk = cap.get_chunk()
                if chunk is not None:
                    streamer.push_audio(chunk)
    """

    def __init__(
        self,
        on_words_callback: Optional[Callable[[list[Word]], None]] = None,
        initial_prompt: Optional[str] = None,
    ) -> None:
        self.cfg = CONFIG.speech
        self.audio_cfg = CONFIG.audio

        self.recognizer = SpeechRecognizer()
        self.on_words = on_words_callback or (lambda words: None)
        self.initial_prompt = initial_prompt

        # Audio buffer
        chunk_samples = int(
            self.cfg.chunk_duration_sec * self.audio_cfg.sample_rate
        )
        self.buffer: deque[np.ndarray] = deque()
        self.buffer_samples: int = 0
        self.chunk_threshold: int = chunk_samples

        # Threading
        self._process_queue: queue.Queue[object] = queue.Queue(maxsize=5)
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._lock = threading.Lock()

        # Song-time tracking: Whisper timestamps are chunk-relative,
        # convert them to song-relative before emitting words.
        self._chunk_start_song_time: float = 0.0
        self._song_time_provider: Optional[Callable[[], float]] = None

    def set_song_time_provider(self, provider: Callable[[], float]) -> None:
        """Set a callable that returns the current song time."""
        self._song_time_provider = provider

    def start(self) -> None:
        """Warm up the model and start the background thread."""
        if self._running:
            logger.warning("StreamingRecognizer already running")
            return

        logger.info("Warming up Whisper model...")
        self.recognizer._load_model()

        self._running = True
        self._thread = threading.Thread(
            target=self._process_loop,
            name="whisper-stream",
            daemon=True,
        )
        self._thread.start()
        logger.info("Streaming recognizer started")

    def stop(self) -> None:
        """Stop the worker thread cleanly."""
        self._running = False
        if self._thread is not None:
            # Sentinel to unblock queue.get
            try:
                self._process_queue.put_nowait(np.array([]))
            except queue.Full:
                pass
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Streaming recognizer stopped")

    def push_audio(self, chunk: np.ndarray) -> None:
        """Add an audio chunk to the buffer, trigger processing if full."""
        with self._lock:
            # If buffer is empty, this is the START of a new chunk.
            # Record the song time of its first sample.
            if self.buffer_samples == 0 and self._song_time_provider:
                self._chunk_start_song_time = self._song_time_provider()

            self.buffer.append(chunk)
            self.buffer_samples += len(chunk)

            if self.buffer_samples < self.chunk_threshold:
                return

            # Combine buffered audio
            combined = np.concatenate(list(self.buffer))

            # Include the song-time offset of this chunk's first sample
            offset = (
                self._chunk_start_song_time
                if self._song_time_provider
                else 0.0
            )

            # Send to worker (drop if queue full — better than lag)
            try:
                self._process_queue.put_nowait((combined, offset))
            except queue.Full:
                logger.warning("Whisper queue full — dropping chunk")

            # Keep overlap for context
            overlap_samples = int(
                self.cfg.overlap_sec * self.audio_cfg.sample_rate
            )
            if len(combined) > overlap_samples:
                self.buffer.clear()
                self.buffer.append(combined[-overlap_samples:])
                self.buffer_samples = overlap_samples
                # The overlap tail's first sample was captured
                # overlap_sec before now — re-anchor the offset.
                if self._song_time_provider:
                    self._chunk_start_song_time = (
                        self._song_time_provider() - self.cfg.overlap_sec
                    )
            else:
                self.buffer.clear()
                self.buffer_samples = 0
                if self._song_time_provider:
                    self._chunk_start_song_time = self._song_time_provider()

    def _process_loop(self) -> None:
        """Worker thread: pull chunks from queue, transcribe, emit."""
        while self._running:
            try:
                item = self._process_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not isinstance(item, tuple):
                break  # Sentinel

            audio, chunk_song_offset = item

            try:
                start = time.monotonic()
                result = self.recognizer.transcribe_numpy(
                    audio,
                    sample_rate=self.audio_cfg.sample_rate,
                    initial_prompt=self.initial_prompt,
                )
                elapsed = time.monotonic() - start

                if result.words:
                    # Convert chunk-relative timestamps to song-relative
                    for word in result.words:
                        word.start += chunk_song_offset
                        word.end += chunk_song_offset

                    logger.debug(
                        f"Recognized {len(result.words)} words in "
                        f"{elapsed:.2f}s, chunk offset {chunk_song_offset:.2f}s"
                    )
                    self.on_words(result.words)

            except Exception as e:
                logger.error(f"Streaming transcription failed: {e}")


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    from rich.console import Console

    from wrenify.audio.capture import AudioCapture

    console = Console()
    console.print("\n[bold cyan]Streaming Speech Recognition Test[/bold cyan]\n")
    console.print(
        "[yellow]Speak for 15 seconds. "
        "Words appear with ~1-2s delay.[/yellow]\n"
    )

    recognized_all: list[str] = []

    def on_words(words: list[Word]) -> None:
        text = " ".join(w.text for w in words)
        console.print(f"[green]HEARD:[/green] {text}")
        recognized_all.extend(w.text for w in words)

    streamer = StreamingRecognizer(on_words_callback=on_words)
    streamer.start()

    with AudioCapture() as cap:
        start = time.monotonic()
        while time.monotonic() - start < 15.0:
            chunk = cap.get_chunk(timeout=0.1)
            if chunk is not None:
                streamer.push_audio(chunk)
            remaining = 15.0 - (time.monotonic() - start)
            console.print(
                f"\r[dim]Recording... {remaining:4.1f}s left[/dim]", end=""
            )

    console.print("\n\n[cyan]Stopping...[/cyan]")
    streamer.stop()

    console.print(f"\n[green]Total words:[/green] {len(recognized_all)}")
    if recognized_all:
        console.print(
            f"[bold]Transcript:[/bold] {' '.join(recognized_all)}"
        )
