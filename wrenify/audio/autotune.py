"""
Wrenify — Auto-tune engine using the WORLD vocoder.

Detects the fundamental frequency (f0) of each audio frame, snaps it to
the nearest note in the target scale, then resynthesizes the audio.
Result: pitch-corrected vocals, like Auto-Tune or Melodyne.

Strength parameter controls the effect:
    0.0 → natural voice (bypass)
    0.5 → subtle correction (professional sound)
    0.8 → strong pop-vocal correction
    1.0 → T-Pain / Cher effect
"""

from __future__ import annotations

import numpy as np
import pyworld as pw
from loguru import logger

from wrenify.core.config import CONFIG


class AutoTuneEngine:
    """
    Real-time pitch correction using the WORLD vocoder pipeline.

    Pipeline per audio chunk:
        raw audio
        → harvest()    detects f0 (pitch)
        → cheaptrick() extracts spectral envelope (timbre)
        → d4c()        extracts aperiodicity (breathiness)
        → snap f0 to scale
        → synthesize() rebuild audio with corrected pitch
    """

    NOTE_FREQS: dict[str, float] = {
        "C": 261.63,
        "C#": 277.18,
        "D": 293.66,
        "D#": 311.13,
        "E": 329.63,
        "F": 349.23,
        "F#": 369.99,
        "G": 392.00,
        "G#": 415.30,
        "A": 440.00,
        "A#": 466.16,
        "B": 493.88,
    }

    SCALES: dict[str, list[int]] = {
        "major": [0, 2, 4, 5, 7, 9, 11],
        "minor": [0, 2, 3, 5, 7, 8, 10],
        "pentatonic": [0, 2, 4, 7, 9],
        "blues": [0, 3, 5, 6, 7, 10],
        "chromatic": list(range(12)),
    }

    MIN_VOICED_FREQ: float = 80.0  # Below this = noise, ignore
    MIN_CHUNK_SEC: float = 0.05  # WORLD needs at least this much audio

    def __init__(self) -> None:
        self.cfg = CONFIG.autotune
        self.sr = CONFIG.audio.sample_rate
        self._targets = self._build_target_frequencies()

        logger.info(
            f"AutoTune ready "
            f"| key={self.cfg.key} scale={self.cfg.scale} "
            f"strength={self.cfg.strength}"
        )

    def _build_target_frequencies(self) -> np.ndarray:
        """Pre-compute all valid target notes across 8 octaves. O(1) lookup later."""
        keys = list(self.NOTE_FREQS.keys())
        key_idx = keys.index(self.cfg.key)
        scale_steps = self.SCALES[self.cfg.scale]

        targets: list[float] = []
        for octave in range(1, 9):
            for step in scale_steps:
                note_name = keys[(key_idx + step) % 12]
                base_freq = self.NOTE_FREQS[note_name]
                freq = base_freq * (2 ** (octave - 4))
                targets.append(freq)

        return np.array(sorted(targets))

    def _snap_pitch(self, freq: float) -> float:
        """Find the nearest scale note and blend by strength."""
        if freq <= 0:
            return freq

        nearest = float(self._targets[np.abs(self._targets - freq).argmin()])
        return freq + (nearest - freq) * self.cfg.strength

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """
        Process one audio chunk through the auto-tune pipeline.

        Args:
            chunk: mono float32 numpy array

        Returns:
            Pitch-corrected mono float32 numpy array
        """
        if not self.cfg.enabled:
            return chunk

        # WORLD needs float64 and a minimum chunk length
        audio = chunk.astype(np.float64)
        min_samples = int(self.sr * self.MIN_CHUNK_SEC)

        if len(audio) < min_samples:
            return chunk

        try:
            # Decompose voice into 3 components
            f0, t = pw.harvest(audio, self.sr)
            sp = pw.cheaptrick(audio, f0, t, self.sr)
            ap = pw.d4c(audio, f0, t, self.sr)

            # Correct pitch (only for voiced frames)
            f0_corrected = np.array(
                [
                    self._snap_pitch(f) if f > self.MIN_VOICED_FREQ else f
                    for f in f0
                ]
            )

            # Resynthesize with corrected pitch
            corrected = pw.synthesize(f0_corrected, sp, ap, self.sr)
            return corrected.astype(np.float32)

        except Exception as e:
            logger.warning(f"AutoTune failed on chunk: {e} — passing through")
            return chunk

    # ─────────── Runtime setters ───────────

    def process_full(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """
        Process an entire audio array through auto-tune.

        Splits into chunks internally, processes each, concatenates result.

        Args:
            audio: Mono float32 audio samples
            sample_rate: Sample rate (must match self.sr)

        Returns:
            Auto-tuned audio, same length as input
        """
        if not self.cfg.enabled or len(audio) == 0:
            return audio

        target_length = len(audio)

        if sample_rate != self.sr:
            import librosa

            audio = librosa.resample(
                audio, orig_sr=sample_rate, target_sr=self.sr
            )

        chunk_size = 4096
        output_chunks: list[np.ndarray] = []

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            if len(chunk) > 0:
                processed = self.process(chunk)
                output_chunks.append(processed)

        if not output_chunks:
            return audio

        result = np.concatenate(output_chunks)

        # Trim/pad to match the original input length exactly
        if len(result) > target_length:
            result = result[:target_length]
        elif len(result) < target_length:
            padding = np.zeros(
                target_length - len(result), dtype=result.dtype
            )
            result = np.concatenate([result, padding])

        return result

    def set_strength(self, strength: float) -> None:
        self.cfg.strength = float(np.clip(strength, 0.0, 1.0))
        logger.info(f"Strength → {self.cfg.strength}")

    def set_key(self, key: str) -> None:
        if key not in self.NOTE_FREQS:
            raise ValueError(f"Invalid key: {key}")
        self.cfg.key = key
        self._targets = self._build_target_frequencies()
        logger.info(f"Key → {key}")

    def set_scale(self, scale: str) -> None:
        if scale not in self.SCALES:
            raise ValueError(f"Invalid scale: {scale}")
        self.cfg.scale = scale
        self._targets = self._build_target_frequencies()
        logger.info(f"Scale → {scale}")


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    import soundfile as sf
    from rich.console import Console
    from rich.progress import Progress

    console = Console()

    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python -m wrenify.audio.autotune <input.wav>")
        console.print("[dim]Record yourself with:[/dim]")
        console.print("  arecord -f cd -d 5 test.wav")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        console.print(f"[red]File not found:[/red] {input_path}")
        sys.exit(1)

    output_path = input_path.with_stem(input_path.stem + "_wrenified")

    console.print(f"\n[cyan]Wrenifying:[/cyan] {input_path}")

    audio, sr = sf.read(str(input_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]  # take left channel if stereo

    console.print(f"[dim]Sample rate:[/dim] {sr} Hz")
    console.print(f"[dim]Duration:[/dim]    {len(audio) / sr:.2f} s")

    engine = AutoTuneEngine()

    chunk_size = CONFIG.audio.chunk_size
    output: list[np.ndarray] = []

    with Progress() as progress:
        task = progress.add_task("[magenta]Processing...", total=len(audio))

        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]
            output.append(engine.process(chunk))
            progress.update(task, advance=len(chunk))

    result = np.concatenate(output)
    sf.write(str(output_path), result, sr)

    console.print(f"\n[green]Saved:[/green] {output_path}")
    console.print(f"[dim]Play with:[/dim] mpv {output_path}")
