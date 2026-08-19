"""
Wrenify — Vocal separation using Demucs.

Splits any audio file into isolated vocals and instrumental tracks
using Meta's Demucs AI model (htdemucs).

Processing time: 5-15 min per song on CPU (8GB RAM).
Quality: Near-studio quality separation.
Output: vocals.wav + instrumental.wav stored in song folder.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger


@dataclass
class SeparationResult:
    vocals_path:       Path
    instrumental_path: Path
    processing_time:   float
    source_duration:   float

    @property
    def speed_factor(self) -> str:
        if self.processing_time <= 0:
            return "instant"
        ratio = self.source_duration / self.processing_time
        return f"{ratio:.2f}x realtime"


class VocalSeparator:
    """Demucs wrapper for two-stem vocal/instrumental separation."""

    DEFAULT_MODEL: str = "htdemucs"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._verify_demucs()

    def _verify_demucs(self) -> None:
        try:
            result = subprocess.run(
                # "python -m demucs" imports optional musdb and crashes —
                # demucs.separate is the stable CLI entrypoint.
                ["python", "-m", "demucs.separate", "--help"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                raise RuntimeError("demucs check failed")
            logger.info(f"Demucs ready (model: {self.model})")
        except Exception as e:
            raise RuntimeError(
                f"Demucs not installed: {e}. Run: poetry add demucs"
            )

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SeparationResult:
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"Not found: {input_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        source_duration = self._get_duration(input_path)
        temp_dir = output_dir / "_demucs_temp"
        temp_dir.mkdir(exist_ok=True)

        if progress_callback:
            progress_callback("Starting Demucs separation...")

        cmd = [
            "python", "-m", "demucs.separate",
            "--two-stems", "vocals",
            "-n", self.model,
            "--segment", "6",        # Lower = less RAM on 8GB systems
            "-o", str(temp_dir),
            "--filename", "{stem}.{ext}",
            str(input_path),
        ]

        logger.info(f"Running Demucs on {input_path.name} ({source_duration:.0f}s)")
        start = time.monotonic()

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )

        for line in process.stdout:
            line = line.strip()
            if line:
                logger.debug(f"demucs: {line}")
                if progress_callback and ("%" in line or "Processing" in line):
                    progress_callback(line[:60])

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Demucs failed (exit {process.returncode})")

        elapsed = time.monotonic() - start

        # Find output files
        source_dir = temp_dir / self.model / input_path.stem
        vocals_src = self._find_file(source_dir, "vocals")
        instrumental_src = self._find_file(source_dir, "no_vocals")

        if not vocals_src or not instrumental_src:
            raise RuntimeError(
                f"Demucs output missing. Folder contents: "
                f"{list(source_dir.iterdir()) if source_dir.exists() else 'NONE'}"
            )

        # Move to final location
        vocals_dst = output_dir / "vocals.wav"
        instrumental_dst = output_dir / "instrumental.wav"
        vocals_src.rename(vocals_dst)
        instrumental_src.rename(instrumental_dst)

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

        logger.success(f"Separated in {elapsed:.1f}s ({source_duration/elapsed:.2f}x)")
        return SeparationResult(
            vocals_path=vocals_dst,
            instrumental_path=instrumental_dst,
            processing_time=elapsed,
            source_duration=source_duration,
        )

    @staticmethod
    def _find_file(folder: Path, stem_keyword: str) -> Optional[Path]:
        if not folder.exists():
            return None
        for f in folder.iterdir():
            if stem_keyword in f.stem.lower() and f.suffix in (".wav", ".mp3"):
                return f
        return None

    @staticmethod
    def _get_duration(path: Path) -> float:
        try:
            import soundfile as sf
            return float(sf.info(str(path)).duration)
        except Exception:
            return 0.0


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Demucs Vocal Separation Test[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print(
            "[red]Usage:[/red] "
            "python -m wrenify.songs.vocal_separator <song.mp3> [output_dir]"
        )
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        console.print(f"[red]Not found:[/red] {input_file}")
        sys.exit(1)

    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("separated")
    console.print(f"[cyan]Input:[/cyan]  {input_file}")
    console.print(f"[cyan]Output:[/cyan] {out_dir}")
    console.print("[yellow]This takes 5-15 min on CPU.[/yellow]\n")

    separator = VocalSeparator()
    result = separator.separate(
        input_file, out_dir,
        progress_callback=lambda m: console.print(f"[dim]{m}[/dim]"),
    )

    console.print(f"\n[green]Vocals:[/green]       {result.vocals_path}")
    console.print(f"[green]Instrumental:[/green]  {result.instrumental_path}")
    console.print(
        f"[green]Speed:[/green]         {result.speed_factor}"
    )
