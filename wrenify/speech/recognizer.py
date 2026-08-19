"""
Wrenify — Speech recognition using faster-whisper.

Loads a Whisper model once at startup, reuses for all calls.
First run downloads the model (~74MB for 'base').

For 8GB RAM systems, defaults to 'base' model in int8 mode.
This gives 5-7x realtime speed with ~800MB RAM footprint.

Used for:
- Batch: transcribe a full song for lyrics alignment
- Streaming: real-time word detection (see streaming.py)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

from wrenify.core.config import CONFIG


@dataclass
class Word:
    """A single recognized word with timing and confidence."""

    text:        str      # The word itself, e.g. "hello"
    start:       float    # Start time in seconds
    end:         float    # End time in seconds
    probability: float    # Confidence 0.0 to 1.0

    @property
    def duration(self) -> float:
        return self.end - self.start

    def __repr__(self) -> str:
        return f"Word({self.text!r} @ {self.start:.2f}-{self.end:.2f}s)"


@dataclass
class TranscriptionResult:
    """Result of a full transcription: words + metadata."""

    words:           list[Word]
    full_text:       str
    language:        str
    duration:        float
    processing_time: float

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def realtime_factor(self) -> float:
        """How many times faster than realtime we processed."""
        if self.processing_time <= 0:
            return 0.0
        return self.duration / self.processing_time

    def words_between(self, start: float, end: float) -> list[Word]:
        """Get all words whose START time falls in [start, end)."""
        return [w for w in self.words if start <= w.start < end]


class SpeechRecognizer:
    """
    Wrapper around faster-whisper for word-level speech recognition.

    The model loads lazily on first transcription and is reused.
    Not thread-safe for concurrent transcribe() calls — use a queue
    or lock if multiple threads need access.

    Usage:
        recognizer = SpeechRecognizer()
        result = recognizer.transcribe("song.wav")
        for word in result.words:
            print(f"{word.text} at {word.start:.2f}s")
    """

    def __init__(self) -> None:
        self.cfg = CONFIG.speech
        self._model: Optional[WhisperModel] = None
        self._device_used: str = ""

    def _load_model(self) -> WhisperModel:
        """Lazy-load the Whisper model. Downloads on first use."""
        if self._model is not None:
            return self._model

        # Resolve device
        device = self.cfg.device
        if device == "auto":
            device = self._detect_device()

        # Enforce compatible compute type
        compute_type = self.cfg.compute_type
        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"
            logger.warning("float16 unsupported on CPU, using int8 instead")

        logger.info(
            f"Loading Whisper model: {self.cfg.model_size} "
            f"(device={device}, compute={compute_type})"
        )
        logger.info(f"Model cache: {self.cfg.model_cache_dir}")

        Path(self.cfg.model_cache_dir).mkdir(parents=True, exist_ok=True)

        self._model = WhisperModel(
            self.cfg.model_size,
            device=device,
            compute_type=compute_type,
            download_root=self.cfg.model_cache_dir,
        )
        self._device_used = device
        logger.success(f"Whisper model loaded on {device}")
        return self._model

    def _detect_device(self) -> str:
        """Detect CUDA availability, fall back to CPU."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"CUDA detected: {gpu_name}")
                return "cuda"
        except ImportError:
            pass
        logger.info("Using CPU (no CUDA available)")
        return "cpu"

    def transcribe(
        self,
        audio_input: Union[str, Path, np.ndarray],
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio with word-level timestamps.

        Args:
            audio_input: Path to audio file OR numpy array of samples
            language: Language code (e.g., 'en'). None = auto-detect
            initial_prompt: Context hint (e.g. song title + lyrics)

        Returns:
            TranscriptionResult with word timings
        """
        model = self._load_model()
        lang = language or self.cfg.language

        # Convert Path to str for faster-whisper
        if isinstance(audio_input, Path):
            audio_input = str(audio_input)

        start_time = time.monotonic()

        segments, info = model.transcribe(
            audio_input,
            language=lang,
            beam_size=self.cfg.beam_size,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300,  # Was 500 — trigger faster
                "speech_pad_ms": 200,            # Pad detected speech
            },
            initial_prompt=initial_prompt,  # Context hint
            temperature=0.0,                # More deterministic
            no_speech_threshold=0.4,        # Was 0.6 — accept quieter speech
        )

        words: list[Word] = []
        text_parts: list[str] = []

        for segment in segments:
            text_parts.append(segment.text)
            if segment.words:
                for w in segment.words:
                    words.append(
                        Word(
                            text=w.word.strip(),
                            start=w.start,
                            end=w.end,
                            probability=w.probability,
                        )
                    )

        processing_time = time.monotonic() - start_time
        full_text = "".join(text_parts).strip()

        logger.info(
            f"Transcribed {len(words)} words in {processing_time:.2f}s "
            f"(audio: {info.duration:.2f}s, "
            f"speed: {info.duration/processing_time:.1f}x)"
        )

        return TranscriptionResult(
            words=words,
            full_text=full_text,
            language=info.language,
            duration=info.duration,
            processing_time=processing_time,
        )

    def transcribe_numpy(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        initial_prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe raw audio numpy array.

        faster-whisper expects 16kHz mono float32.
        This method handles resampling and channel conversion.
        """
        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(
                audio, orig_sr=sample_rate, target_sr=16000
            )

        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32)

        return self.transcribe(audio, initial_prompt=initial_prompt)


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("\n[bold cyan]Speech Recognizer Test[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print(
            "[red]Usage:[/red] python -m wrenify.speech.recognizer <audio.wav>"
        )
        console.print("\n[dim]Record a test file:[/dim]")
        console.print("  arecord -f cd -d 10 -r 16000 test_speech.wav")
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        console.print(f"[red]File not found:[/red] {audio_path}")
        sys.exit(1)

    console.print(f"[cyan]Transcribing:[/cyan] {audio_path}")
    console.print("[dim]First run will download ~74MB model...[/dim]\n")

    recognizer = SpeechRecognizer()
    result = recognizer.transcribe(audio_path)

    console.print(f"[green]Language:[/green]   {result.language}")
    console.print(f"[green]Duration:[/green]   {result.duration:.2f}s")
    console.print(f"[green]Processing:[/green] {result.processing_time:.2f}s")
    console.print(
        f"[green]Speed:[/green]      {result.realtime_factor:.1f}x realtime\n"
    )

    console.print("[bold]Full text:[/bold]")
    console.print(f"  {result.full_text}\n")

    # Word-level table (first 30)
    table = Table(title="Word-level Timestamps")
    table.add_column("Word",       style="cyan")
    table.add_column("Start",      justify="right", style="green")
    table.add_column("End",        justify="right", style="green")
    table.add_column("Duration",   justify="right", style="magenta")
    table.add_column("Confidence", justify="right", style="yellow")

    for word in result.words[:30]:
        table.add_row(
            word.text,
            f"{word.start:.2f}s",
            f"{word.end:.2f}s",
            f"{word.duration:.2f}s",
            f"{word.probability:.1%}",
        )

    console.print(table)

    if len(result.words) > 30:
        console.print(f"[dim]... and {len(result.words) - 30} more words[/dim]")
