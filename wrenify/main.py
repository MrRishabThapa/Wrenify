"""
Wrenify — Entry point.

Default: launches the desktop UI directly.
Advanced commands available via subcommands (--help).
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from wrenify.core.config import CONFIG

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0", prog_name="Wrenify")
def cli(ctx: click.Context) -> None:
    """
    Wrenify — Your voice. Perfected.

    A local-first karaoke studio with vocal separation, auto-tune,
    and recording capabilities.

    Run without arguments to launch the desktop app.
    Use subcommands for advanced operations.
    """
    if ctx.invoked_subcommand is None:
        launch_app()


@cli.command()
def launch() -> None:
    """Launch the Wrenify desktop application (default)."""
    launch_app()


@cli.command(name="import")
@click.argument("audio_path", type=click.Path(exists=True))
@click.option("--title", prompt=True, help="Song title")
@click.option("--artist", prompt=True, help="Artist name")
@click.option("--album", default="", help="Album name (optional)")
def import_song(audio_path: str, title: str, artist: str, album: str) -> None:
    """Import a song via CLI (advanced users)."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from wrenify.songs.full_import import FullSongImporter

    importer = FullSongImporter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting import...", total=100)

        def on_progress(msg: str, pct: float) -> None:
            progress.update(task, description=msg[:70], completed=pct)

        try:
            song = importer.import_song(
                audio_path=Path(audio_path),
                title=title,
                artist=artist,
                album=album or None,
                progress_callback=on_progress,
            )
            console.print(f"\n[green]✓ Imported:[/green] {song.display_name}")
        except Exception as e:
            console.print(f"\n[red]✗ Failed:[/red] {e}")
            sys.exit(1)


@cli.command()
def setup() -> None:
    """Re-run the first-time setup wizard."""
    from wrenify.core.setup_wizard import run_setup_wizard
    run_setup_wizard(force=True)


@cli.command()
def info() -> None:
    """Show system diagnostic info."""
    _print_system_info()


@cli.command()
def library() -> None:
    """List all imported songs."""
    import json

    from wrenify.core.config import ROOT_DIR

    songs_dir = ROOT_DIR / "songs"
    if not songs_dir.exists():
        console.print("[yellow]No songs yet. Import via UI or `wrenify import`[/yellow]")
        return

    folders = [f for f in songs_dir.iterdir() if f.is_dir()]
    if not folders:
        console.print("[yellow]No songs imported yet[/yellow]")
        return

    console.print(f"\n[bold]Your Library ({len(folders)} songs)[/bold]\n")
    for folder in sorted(folders):
        meta_file = folder / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                title = meta.get("title", folder.name)
                artist = meta.get("artist", "Unknown")
                duration = meta.get("duration", 0)
                m, s = divmod(int(duration), 60)
                console.print(f"  [cyan]{artist}[/cyan] — {title} ({m}:{s:02d})")
            except Exception:
                console.print(f"  [dim]{folder.name}[/dim]")


def launch_app() -> None:
    """Launch the PyQt6 desktop application."""
    # Check if first run — if so, run setup wizard first
    from wrenify.core.setup_wizard import is_first_run, run_setup_wizard

    if is_first_run():
        console.print("\n[cyan]Welcome to Wrenify! Running first-time setup...[/cyan]\n")
        if not run_setup_wizard(force=False):
            console.print("[red]Setup incomplete. Exiting.[/red]")
            sys.exit(1)

    # Launch UI
    from wrenify.ui.app import run

    sys.exit(run())


def _print_system_info() -> None:
    """Show system diagnostics."""
    import platform

    import psutil

    console.print("\n[bold cyan]Wrenify System Info[/bold cyan]\n")
    console.print("  Version:      0.1.0")
    console.print(f"  OS:           {platform.system()} {platform.release()}")
    console.print(f"  Python:       {sys.version.split()[0]}")
    console.print(f"  CPU cores:    {psutil.cpu_count()}")
    console.print(f"  RAM:          {psutil.virtual_memory().total // (1024**3)} GB")

    console.print("\n[bold]Config:[/bold]")
    console.print(f"  Sample rate:  {CONFIG.audio.sample_rate} Hz")
    console.print(f"  Whisper:      {CONFIG.speech.model_size} ({CONFIG.speech.compute_type})")
    console.print(f"  Auto-tune:    {CONFIG.autotune.key} {CONFIG.autotune.scale}")

    # Check for external dependencies
    console.print("\n[bold]Dependencies:[/bold]")
    _check_dep("ffmpeg", "ffmpeg -version")
    _check_dep("yt-dlp", "yt-dlp --version")

    # Check models
    from wrenify.core.config import MODELS_DIR
    whisper_dir = MODELS_DIR / "whisper"
    demucs_dir = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"

    console.print("\n[bold]Models:[/bold]")
    if whisper_dir.exists() and any(whisper_dir.rglob("*.bin")):
        console.print("  [green]✓[/green] Whisper: downloaded")
    else:
        console.print("  [yellow]○[/yellow] Whisper: not downloaded")

    if demucs_dir.exists() and list(demucs_dir.glob("*.th")):
        console.print("  [green]✓[/green] Demucs: downloaded")
    else:
        console.print("  [yellow]○[/yellow] Demucs: not downloaded")


def _check_dep(name: str, command: str) -> None:
    import subprocess
    try:
        subprocess.run(
            command.split(), capture_output=True, timeout=5, check=True
        )
        console.print(f"  [green]✓[/green] {name}: available")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        console.print(f"  [red]✗[/red] {name}: NOT FOUND")


def main() -> None:
    """Entry point for `wrenify` command."""
    cli()


if __name__ == "__main__":
    main()
