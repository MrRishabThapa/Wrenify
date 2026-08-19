"""
Wrenify — Real-time audio capture from microphone.

Uses sounddevice + PortAudio for low-latency mic input.
Audio chunks are pushed to a thread-safe queue for downstream processing.
"""

from __future__ import annotations

import queue
import time
from typing import Optional

import numpy as np
import sounddevice as sd
from loguru import logger

from wrenify.core.config import CONFIG


class AudioCapture:
    """
    Captures mono audio from the microphone in real-time.

    Audio chunks are placed into a thread-safe queue. Sounddevice runs
    the callback in a separate thread automatically. Old chunks are
    dropped if the queue fills up (to prevent lag).

    Usage:
        with AudioCapture() as cap:
            while running:
                chunk = cap.get_chunk()
                if chunk is not None:
                    process(chunk)
    """

    def __init__(self) -> None:
        self.cfg = CONFIG.audio
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=CONFIG.audio.max_queue_size
        )
        self._stream: Optional[sd.InputStream] = None
        self._running: bool = False

        self._callback_count: int = 0
        self._peak_sum: float = 0.0
        self._rms_sum: float = 0.0

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice for every audio chunk. Runs in its own thread."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        chunk = indata.copy().flatten()

        # Diagnostic: log peak levels periodically
        self._callback_count += 1
        peak = float(np.max(np.abs(chunk)))
        rms  = float(np.sqrt(np.mean(chunk ** 2)))
        self._peak_sum += peak
        self._rms_sum += rms

        # Every ~1 second of audio, log the level
        if self._callback_count >= 10:
            avg_peak = self._peak_sum / self._callback_count
            avg_rms  = self._rms_sum / self._callback_count

            if avg_rms < 0.001:
                logger.warning(
                    f"Mic reading SILENCE: peak={avg_peak:.4f} rms={avg_rms:.6f}. "
                    f"Check: pavucontrol -> Recording tab -> input volume"
                )
            elif avg_rms < 0.01:
                logger.info(
                    f"Mic level LOW: peak={avg_peak:.4f} rms={avg_rms:.6f}. "
                    f"Speak louder or boost mic gain."
                )
            else:
                logger.debug(
                    f"Mic OK: peak={avg_peak:.4f} rms={avg_rms:.6f}"
                )

            self._callback_count = 0
            self._peak_sum = 0.0
            self._rms_sum = 0.0

        try:
            self.audio_queue.put_nowait(chunk)
        except queue.Full:
            # Drop oldest chunk to keep latency low
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(chunk)
            except queue.Empty:
                pass

    def start(self) -> None:
        """Open the audio input stream."""
        self._running = True
        self._stream = sd.InputStream(
            samplerate=self.cfg.sample_rate,
            blocksize=self.cfg.chunk_size,
            device=self.cfg.device_index,
            channels=self.cfg.channels,
            dtype=self.cfg.dtype,
            callback=self._callback,
        )
        self._stream.start()
        logger.info(
            f"Mic capture started "
            f"| SR={self.cfg.sample_rate} chunk={self.cfg.chunk_size}"
        )

    def stop(self) -> None:
        """Close the audio input stream."""
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Mic capture stopped")

    def get_chunk(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Get the next audio chunk, or None if timeout."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @staticmethod
    def list_devices() -> None:
        """Print all available audio input devices."""
        print(sd.query_devices())

    def __enter__(self) -> "AudioCapture":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]AudioCapture Test[/bold cyan]")
    console.print("[dim]Available devices:[/dim]\n")
    AudioCapture.list_devices()

    console.print("\n[yellow]Speak into your mic for 5 seconds...[/yellow]\n")

    with AudioCapture() as cap:
        start = time.time()
        chunks_received = 0
        peak_volume = 0.0

        while time.time() - start < 5.0:
            chunk = cap.get_chunk()
            if chunk is not None:
                chunks_received += 1
                rms = float(np.sqrt(np.mean(chunk**2)))
                peak_volume = max(peak_volume, rms)
                bars = "█" * min(int(rms * 600), 40)
                console.print(
                    f"\r  [magenta]{bars:<40}[/magenta] {rms:.4f}",
                    end="",
                )

    console.print(
        f"\n\n[green]Received {chunks_received} chunks "
        f"| Peak volume: {peak_volume:.4f}[/green]"
    )
