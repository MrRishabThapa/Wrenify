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
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from wrenify.core.config import ASSETS_DIR, CONFIG

console = Console()

BANNER_PATH = ASSETS_DIR / "banner.txt"


def _load_banner() -> str:
    """Load the dot-map logo banner from disk (empty string if missing)."""
    try:
        return BANNER_PATH.read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        logger.warning(f"Banner file not found: {BANNER_PATH}")
        return ""


def print_banner() -> None:
    banner = _load_banner()
    if banner:
        console.print(f"[bold magenta]{banner}[/bold magenta]")
    text = Text()
    text.append("WRENIFY", style="bold magenta")
    text.append(" v0.1.0\n", style="dim")
    text.append("Your voice. Perfected.", style="italic cyan")
    console.print(Panel(text, border_style="magenta", padding=(1, 4)))


def check_system_resources() -> None:
    """Warn if system resources are low before starting Wrenify."""
    import psutil

    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)

    if available_gb < 2.0:
        console.print(
            f"[yellow]Warning: Only {available_gb:.1f}GB of {total_gb:.1f}GB "
            f"RAM available. Close other apps for best performance.[/yellow]"
        )
    elif CONFIG.debug:
        console.print(
            f"[dim]RAM: {available_gb:.1f}GB / {total_gb:.1f}GB available[/dim]"
        )

    # Check CPU count for Whisper threading
    cpu_count = psutil.cpu_count(logical=False) or 1
    if cpu_count < 2 and CONFIG.debug:
        console.print(
            f"[yellow]Warning: Only {cpu_count} CPU core. "
            f"Whisper will be slow.[/yellow]"
        )


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


def test_webcam() -> None:
    """Live webcam preview with FPS overlay."""
    import subprocess

    console.print("\n[cyan]Launching webcam preview...[/cyan]\n")
    try:
        subprocess.run(["poetry", "run", "python", "-m", "wrenify.video.camera"])
    except KeyboardInterrupt:
        console.print("[dim]Webcam preview interrupted[/dim]")


def test_video_export() -> None:
    """Record 5 seconds of webcam + mic, export as MP4."""
    import subprocess

    console.print("\n[cyan]Recording webcam + mic for 5 seconds...[/cyan]\n")
    try:
        subprocess.run(["poetry", "run", "python", "-m", "wrenify.video.exporter"])
    except KeyboardInterrupt:
        console.print("[dim]Video export interrupted[/dim]")


def test_speech_batch() -> None:
    """Transcribe a WAV file with word timestamps."""
    import subprocess

    from rich.prompt import Prompt

    path = Prompt.ask("[cyan]Path to WAV file[/cyan]")
    subprocess.run([
        "poetry", "run", "python", "-m", "wrenify.speech.recognizer",
        path,
    ])


def test_speech_streaming() -> None:
    """Live speech recognition for 15 seconds."""
    import subprocess
    subprocess.run([
        "poetry", "run", "python", "-m", "wrenify.speech.streaming",
    ])


def test_lyrics_parser() -> None:
    """Parse an LRC file and display structured output."""
    import subprocess

    from rich.prompt import Prompt

    path = Prompt.ask(
        "[cyan]Path to .lrc file (blank for sample)[/cyan]",
        default="",
    )
    args = ["poetry", "run", "python", "-m", "wrenify.lyrics.parser"]
    if path:
        args.append(path)
    subprocess.run(args)


def test_lyrics_fetcher() -> None:
    """Fetch lyrics from online sources."""
    import subprocess
    subprocess.run(["poetry", "run", "python", "-m", "wrenify.lyrics.fetcher"])


def test_fetch_instrumental() -> None:
    """Fetch an instrumental track from YouTube (mp3)."""
    from wrenify.songs.instrumental import InstrumentalFetcher

    title = Prompt.ask("[cyan]Song title[/cyan]")
    artist = Prompt.ask(
        "[cyan]Artist (optional)[/cyan]",
        default="",
    )

    console.print("\n[dim]Searching YouTube for a clean instrumental...[/dim]")
    fetcher = InstrumentalFetcher()
    path = fetcher.search(title, artist or None)

    if path is not None:
        console.print(f"\n[green]Saved:[/green] {path}")
        console.print(
            "[dim]Next: option 11 -> pick this file + your .lrc[/dim]"
        )
    else:
        console.print(
            "\n[yellow]No suitable instrumental found. "
            "Try a different song or check your connection.[/yellow]"
        )


def test_phonetic_stylizer() -> None:
    """Demonstrate word stretching for held notes."""
    import subprocess
    subprocess.run(["poetry", "run", "python", "-m", "wrenify.lyrics.phonetic"])


def launch_ui() -> None:
    """Launch the PyQt6 desktop interface."""
    from wrenify.ui.app import run

    sys.exit(run())


def test_full_karaoke() -> None:
    """Launch a full karaoke session (music + lyrics + scoring)."""
    from PyQt6.QtWidgets import QApplication

    from wrenify.ui.app import THEME_QSS, MainWindow

    console.print("\n[cyan]Launching Wrenify karaoke...[/cyan]")
    console.print("[yellow]You will be asked for:[/yellow]")
    console.print("  1. Instrumental audio file (mp3/wav)")
    console.print("  2. Lyrics file (.lrc)")
    console.print("\n[bold]HEADPHONES RECOMMENDED[/bold] to avoid mic feedback.\n")

    app = QApplication(sys.argv)
    app.setApplicationName("Wrenify")
    app.setStyleSheet(THEME_QSS)
    window = MainWindow()
    window.show()
    window.open_song_dialog()
    sys.exit(app.exec())


def main() -> None:
    print_banner()
    check_system_resources()

    console.print("\n[bold]Menu:[/bold]")
    console.print("  [cyan]1[/cyan] → Test microphone (5s level meter)")
    console.print("  [cyan]2[/cyan] → Auto-tune a WAV file")
    console.print("  [cyan]3[/cyan] → Apply effects to a WAV file")
    console.print("  [cyan]4[/cyan] → Test webcam (live preview)")
    console.print("  [cyan]5[/cyan] → Test video export (webcam + mic → MP4)")
    console.print("  [cyan]6[/cyan] → Speech-to-text on WAV file (batch)")
    console.print("  [cyan]7[/cyan] → Live speech recognition (streaming)")
    console.print("  [cyan]8[/cyan] → Parse an LRC lyrics file")
    console.print("  [cyan]9[/cyan] → Fetch lyrics from online")
    console.print("  [cyan]10[/cyan] → Test phonetic word stretcher")
    console.print("  [cyan]11[/cyan] → Full karaoke session (UI + scoring)")
    console.print("  [cyan]12[/cyan] → Fetch instrumental from YouTube")
    console.print("  [cyan]q[/cyan] → Quit\n")

    choice = Prompt.ask(
        "→",
        choices=[
            "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "q",
        ],
        default="1",
    )

    if choice == "1":
        test_mic()
    elif choice == "2":
        test_autotune()
    elif choice == "3":
        test_effects()
    elif choice == "4":
        test_webcam()
    elif choice == "5":
        test_video_export()
    elif choice == "6":
        test_speech_batch()
    elif choice == "7":
        test_speech_streaming()
    elif choice == "8":
        test_lyrics_parser()
    elif choice == "9":
        test_lyrics_fetcher()
    elif choice == "10":
        test_phonetic_stylizer()
    elif choice == "11":
        test_full_karaoke()
    elif choice == "12":
        test_fetch_instrumental()
    else:
        console.print("[dim]Bye[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
