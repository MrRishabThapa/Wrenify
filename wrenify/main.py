"""
Wrenify — Main Entry Point

Run with:
    poetry run wrenify
    python -m wrenify
"""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from wrenify.core.config import CONFIG


console = Console()


def print_banner() -> None:
    text = Text()
    text.append("🐦 ", style="bold")
    text.append("WRENIFY", style="bold magenta")
    text.append(" v0.1.0\n", style="dim")
    text.append("Your voice. Perfected.", style="italic cyan")

    console.print(
        Panel(text, border_style="magenta", padding=(1, 4))
    )


def main() -> None:
    print_banner()
    console.print(f"\n[dim]Debug mode:[/dim] {CONFIG.debug}")
    console.print(f"[dim]Sample rate:[/dim] {CONFIG.audio.sample_rate} Hz")
    console.print(f"[dim]Auto-tune:[/dim] {CONFIG.autotune.key} {CONFIG.autotune.scale}")
    console.print(
        "\n[yellow]⚠️  App not yet implemented. "
        "This is the boilerplate.[/yellow]\n"
    )


if __name__ == "__main__":
    main()
