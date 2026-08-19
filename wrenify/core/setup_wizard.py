"""
Wrenify — First-run setup wizard.

Detects first launch and guides user through:
- Verifying system dependencies (ffmpeg, portaudio)
- Downloading Whisper model
- Setting up default folders
- Optional: configuring API tokens
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from wrenify.core.config import USER_CONFIG_DIR

console = Console()
SETUP_MARKER_FILE = USER_CONFIG_DIR / "setup_complete"


def is_first_run() -> bool:
    """Check if setup has been completed (with backwards compat)."""
    # Check new location
    if SETUP_MARKER_FILE.exists():
        return False

    # Backwards compat: check old ~/.config/wrenify location (Linux only)
    import platform
    if platform.system() != "Windows":
        old_marker = Path.home() / ".config" / "wrenify" / "setup_complete"
        if old_marker.exists():
            # Migrate to new location
            SETUP_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETUP_MARKER_FILE.touch()
            logger.info("Migrated setup marker to new location")
            return False

    return True


def mark_setup_complete() -> None:
    """Mark that first-time setup has been completed."""
    SETUP_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETUP_MARKER_FILE.touch()


def run_setup_wizard(force: bool = False) -> bool:
    """
    Run interactive first-run setup.

    Returns True if setup succeeded, False if user cancelled.
    """
    console.print(Panel.fit(
        "[bold cyan]Welcome to Wrenify![/bold cyan]\n\n"
        "Let's set up your karaoke studio.\n"
        "This will take about 2-5 minutes.",
        border_style="cyan",
    ))

    if not force and not Confirm.ask("\n[cyan]Continue?[/cyan]", default=True):
        return False

    # Step 1: Check system dependencies
    console.print("\n[bold]Step 1/4:[/bold] Checking system dependencies...\n")
    if not _check_system_deps():
        return False

    # Step 2: Download Whisper model
    console.print("\n[bold]Step 2/4:[/bold] Setting up speech recognition...\n")
    if not _download_whisper_model():
        console.print("[yellow]Skipped Whisper setup. Will download on first use.[/yellow]")

    # Step 3: Create folder structure
    console.print("\n[bold]Step 3/4:[/bold] Creating folders...\n")
    _create_folders()

    # Step 4: Optional API tokens
    console.print("\n[bold]Step 4/4:[/bold] Optional configuration...\n")
    _configure_optional()

    # Done!
    mark_setup_complete()
    console.print(Panel.fit(
        "[bold green]✓ Setup complete![/bold green]\n\n"
        "Wrenify is ready to use.\n"
        "Launching the app now...",
        border_style="green",
    ))

    return True


def _check_system_deps() -> bool:
    """Check that required system dependencies are installed."""
    required = [
        ("ffmpeg",  "ffmpeg -version",  "Video/audio processing"),
        ("yt-dlp",  "yt-dlp --version", "YouTube downloads (optional)"),
    ]

    all_ok = True
    missing = []

    for name, cmd, desc in required:
        try:
            subprocess.run(
                cmd.split(), capture_output=True, timeout=5, check=True
            )
            console.print(f"  [green]✓[/green] {name}: {desc}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            console.print(f"  [red]✗[/red] {name}: {desc}")
            missing.append(name)
            if name == "ffmpeg":
                all_ok = False  # ffmpeg is required

    if not all_ok:
        console.print("\n[red]Required dependencies missing![/red]")
        console.print("[yellow]Install ffmpeg first:[/yellow]")
        console.print("  [dim]# Arch:[/dim]  sudo pacman -S ffmpeg")
        console.print("  [dim]# Debian:[/dim] sudo apt install ffmpeg")
        console.print("  [dim]# Fedora:[/dim] sudo dnf install ffmpeg")
        console.print("  [dim]# macOS:[/dim]  brew install ffmpeg")
        console.print("  [dim]# Windows:[/dim] Download from https://ffmpeg.org")
        return False

    if missing:
        console.print(
            f"\n[yellow]Optional dependencies missing: {', '.join(missing)}[/yellow]"
        )
        console.print("[dim]Some features may be limited without them.[/dim]")

    return True


def _download_whisper_model() -> bool:
    """Pre-download the Whisper model for offline use."""
    if not Confirm.ask(
        "[cyan]Download Whisper AI model now?[/cyan] "
        "([dim]~74 MB, needed for lyrics generation[/dim])",
        default=True,
    ):
        return False

    console.print("[dim]Downloading Whisper 'base' model...[/dim]")

    try:
        from wrenify.speech.recognizer import SpeechRecognizer
        recognizer = SpeechRecognizer()
        recognizer._load_model()  # Triggers download
        console.print("  [green]✓[/green] Whisper model ready")
        return True
    except Exception as e:
        console.print(f"  [red]✗[/red] Whisper download failed: {e}")
        return False


def _create_folders() -> None:
    """Create app folders."""
    from wrenify.core.config import ROOT_DIR

    folders = [
        ROOT_DIR / "songs",
        ROOT_DIR / "recordings",
        ROOT_DIR / "exports",
        ROOT_DIR / "models",
    ]

    for folder in folders:
        folder.mkdir(exist_ok=True, parents=True)
        console.print(f"  [green]✓[/green] {folder.name}/")


def _configure_optional() -> None:
    """Configure optional settings."""
    console.print("[dim]These settings are optional and can be changed later in Settings.[/dim]\n")

    # Genius token
    if Confirm.ask(
        "[cyan]Configure Genius API token?[/cyan] "
        "([dim]improves lyric accuracy for some songs[/dim])",
        default=False,
    ):
        token = Prompt.ask(
            "  [dim]Get free token at https://genius.com/api-clients[/dim]\n"
            "  Token",
            default="",
        )
        if token:
            _save_env_var("GENIUS_TOKEN", token)
            console.print("  [green]✓[/green] Genius token saved")


def _save_env_var(key: str, value: str) -> None:
    """Save an env var to .env file."""
    from wrenify.core.config import ROOT_DIR

    env_path = ROOT_DIR / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    # Update or add the key
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    # Run wizard standalone for testing
    run_setup_wizard(force=True)
