"""
Wrenify — Audio mixing utilities.

Handles combining vocal audio with instrumental tracks for
karaoke recordings.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from loguru import logger


class AudioMixer:
    """Mixes vocal and instrumental audio tracks."""

    @staticmethod
    def mix(
        vocal: np.ndarray,
        instrumental: np.ndarray,
        vocal_gain: float = 1.0,
        instrumental_gain: float = 0.6,
    ) -> np.ndarray:
        """
        Mix a vocal track over an instrumental track.

        Args:
            vocal: Mono float32 mic audio
            instrumental: Mono or stereo instrumental audio (float32)
            vocal_gain: Volume multiplier for voice (default 1.0)
            instrumental_gain: Volume multiplier for music (default 0.6)
                         Lower than vocal so voice stands out

        Returns:
            Mixed mono float32 audio
        """
        # Convert instrumental to mono if stereo
        if instrumental.ndim == 2:
            instrumental = instrumental.mean(axis=1)

        # Ensure both are float32
        vocal = vocal.astype(np.float32)
        instrumental = instrumental.astype(np.float32)

        # Match lengths (crop to shorter)
        min_len = min(len(vocal), len(instrumental))
        vocal = vocal[:min_len]
        instrumental = instrumental[:min_len]

        # Mix with gains
        mixed = (vocal * vocal_gain) + (instrumental * instrumental_gain)

        # Prevent clipping — soft normalize if peak > 0.98
        peak = np.max(np.abs(mixed))
        if peak > 0.98:
            logger.debug(
                f"Mix peak {peak:.2f} — normalizing to prevent clipping"
            )
            mixed = mixed / peak * 0.98

        return mixed

    @staticmethod
    def load_instrumental_slice(
        instrumental_path: Path,
        start_sec: float,
        duration_sec: float,
    ) -> tuple[np.ndarray, int]:
        """
        Load a specific time slice of the instrumental file.

        Used to extract just the portion that plays during recording.

        Args:
            instrumental_path: Path to instrumental audio file
            start_sec: When recording started (song position)
            duration_sec: How long the recording was

        Returns:
            (audio_samples, sample_rate)
        """
        with sf.SoundFile(str(instrumental_path)) as f:
            sample_rate = f.samplerate
            start_frame = int(start_sec * sample_rate)
            num_frames = int(duration_sec * sample_rate)

            # Seek to start position
            f.seek(start_frame)
            audio = f.read(num_frames, dtype="float32", always_2d=False)

        logger.info(
            f"Loaded instrumental slice: {start_sec:.2f}s - "
            f"{start_sec + duration_sec:.2f}s ({len(audio)} samples)"
        )

        return audio, sample_rate


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Audio Mixer Test[/bold cyan]\n")

    if len(sys.argv) < 3:
        console.print(
            "Usage: python -m wrenify.audio.mixer <vocal.wav> <instrumental.wav>"
        )
        sys.exit(1)

    vocal_path = Path(sys.argv[1])
    inst_path = Path(sys.argv[2])
    output_path = Path("mixed_test.wav")

    vocal, vsr = sf.read(str(vocal_path), dtype="float32", always_2d=False)
    inst, isr = sf.read(str(inst_path), dtype="float32", always_2d=False)

    if vsr != isr:
        console.print(f"[red]Sample rate mismatch: {vsr} vs {isr}[/red]")
        sys.exit(1)

    mixer = AudioMixer()
    mixed = mixer.mix(vocal, inst)

    sf.write(str(output_path), mixed, vsr)
    console.print(f"[green]Mixed to: {output_path}[/green]")
