"""
Wrenify — Main Entry Point

Run with:
    poetry run wrenify
    python -m wrenify
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from wrenify.core.config import CONFIG

console = Console()


def print_banner() -> None:
    text = Text()
    text.append("WRENIFY", style="bold magenta")
    text.append(" v0.1.0\n", style="dim")
    text.append("Your voice. Perfected.", style="italic cyan")
    console.print(Panel(text, border_style="magenta", padding=(1, 4)))


def test_mic() -> None:
    """Live mic level meter for 5 seconds."""
    from wrenify.audio.capture import AudioCapture

    console.print("\n[cyan]Mic test — speak for 5 seconds...[/cyan]\n")

    with AudioCapture() as cap:
        start = time.time()
        while time.time() - start < 5.0:
            chunk = cap.get_chunk()
            if chunk is not None:
                rms = float(np.sqrt(np.mean(chunk**2)))
                bars = "█" * min(int(rms * 600), 40)
                console.print(
                    f"\r  [magenta]{bars:<40}[/magenta] {rms:.4f}", end=""
                )

    console.print("\n\n[green]Mic working![/green]")


def test_autotune() -> None:
    """Auto-tune a WAV file."""
    import soundfile as sf

    from wrenify.audio.autotune import AutoTuneEngine

    path_str = Prompt.ask("[cyan]Path to .wav file[/cyan]")
    path = Path(path_str).expanduser()

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        return

    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]

    engine = AutoTuneEngine()
    chunk_size = CONFIG.audio.chunk_size
    output = []

    console.print(f"\n[cyan]Processing {path.name}...[/cyan]")
    for i in range(0, len(audio), chunk_size):
        output.append(engine.process(audio[i : i + chunk_size]))
        progress = (i / len(audio)) * 100
        console.print(f"\r  [magenta]{progress:5.1f}%[/magenta]", end="")

    result = np.concatenate(output)
    out_path = path.with_stem(path.stem + "_wrenified")
    sf.write(str(out_path), result, sr)
    console.print(f"\n[green]Saved:[/green] {out_path}")


def test_effects() -> None:
    """Apply effects to a WAV file."""
    import soundfile as sf

    from wrenify.audio.effects import EffectsRack

    path_str = Prompt.ask("[cyan]Path to .wav file[/cyan]")
    path = Path(path_str).expanduser()

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        return

    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]

    rack = EffectsRack()
    result = rack.process(audio)

    out_path = path.with_stem(path.stem + "_fx")
    sf.write(str(out_path), result, sr)
    console.print(f"[green]Saved:[/green] {out_path}")


def launch_ui() -> None:
    """Launch the PyQt6 desktop interface."""
    from wrenify.ui.app import run

    sys.exit(run())


def main() -> None:
    print_banner()

    console.print("\n[bold]Menu:[/bold]")
    console.print("  [cyan]1[/cyan] → Test microphone (5s level meter)")
    console.print("  [cyan]2[/cyan] → Auto-tune a WAV file")
    console.print("  [cyan]3[/cyan] → Apply effects to a WAV file")
    console.print("  [cyan]4[/cyan] → Launch the desktop UI")
    console.print("  [cyan]q[/cyan] → Quit\n")

    choice = Prompt.ask("→", choices=["1", "2", "3", "4", "q"], default="1")

    if choice == "1":
        test_mic()
    elif choice == "2":
        test_autotune()
    elif choice == "3":
        test_effects()
    elif choice == "4":
        launch_ui()
    else:
        console.print("[dim]Bye[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
