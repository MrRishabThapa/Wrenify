"""
Wrenify — Audio effects rack.

Wraps Spotify's pedalboard library for reverb, compression, and EQ.
These are applied AFTER auto-tune to polish the vocal sound.
"""

from __future__ import annotations

import numpy as np
from loguru import logger
from pedalboard import (
    Compressor,
    HighpassFilter,
    Pedalboard,
    Reverb,
)

from wrenify.core.config import CONFIG


class EffectsRack:
    """
    Chainable audio effects for post-autotune vocal polish.

    Default chain: HP filter → Compressor → Reverb
    (mimics a light professional vocal treatment)
    """

    def __init__(self) -> None:
        self.sr = CONFIG.audio.sample_rate
        self.board = self._build_default_chain()
        logger.info("Effects rack loaded (HP filter → Comp → Reverb)")

    def _build_default_chain(self) -> Pedalboard:
        """Standard vocal chain: filter → compress → reverb."""
        return Pedalboard(
            [
                HighpassFilter(cutoff_frequency_hz=80.0),
                Compressor(
                    threshold_db=-16.0,
                    ratio=2.5,
                    attack_ms=5.0,
                    release_ms=100.0,
                ),
                Reverb(
                    room_size=0.25,
                    damping=0.5,
                    wet_level=0.15,
                    dry_level=0.85,
                ),
            ]
        )

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """Apply effects chain to an audio chunk."""
        return self.board(chunk, self.sr)

    def set_reverb(self, room_size: float, wet_level: float) -> None:
        """Adjust reverb parameters at runtime."""
        for effect in self.board:
            if isinstance(effect, Reverb):
                effect.room_size = float(np.clip(room_size, 0.0, 1.0))
                effect.wet_level = float(np.clip(wet_level, 0.0, 1.0))
                logger.info(f"Reverb → room={room_size} wet={wet_level}")
                return

    def bypass(self) -> None:
        """Remove all effects — pass-through."""
        self.board = Pedalboard([])
        logger.info("Effects bypassed")


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    import soundfile as sf
    from rich.console import Console

    console = Console()

    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python -m wrenify.audio.effects <input.wav>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = input_path.with_stem(input_path.stem + "_fx")

    audio, sr = sf.read(str(input_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]

    console.print(f"[cyan]Applying effects to:[/cyan] {input_path}")

    rack = EffectsRack()
    result = rack.process(audio)

    sf.write(str(output_path), result, sr)
    console.print(f"[green]Saved:[/green] {output_path}")
