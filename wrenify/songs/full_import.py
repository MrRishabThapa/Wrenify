"""
Wrenify — Full song import pipeline.

Input:  Any song file (MP3/WAV with vocals)
Output: songs/<artist>_<title>/
            instrumental.wav   (clean karaoke track)
            vocals.wav         (isolated singing)
            lyrics.lrc         (perfectly timestamped)
            meta.json          (metadata)
            original.mp3       (source file backup)
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from wrenify.core.config import ROOT_DIR
from wrenify.songs.lrc_generator import LRCGenerator, LRCGeneratorConfig
from wrenify.songs.song import Song
from wrenify.songs.vocal_separator import VocalSeparator


SONGS_DIR = ROOT_DIR / "songs"


class FullSongImporter:
    """
    End-to-end song preparation for karaoke.

    Creates a self-contained folder per song with all needed files.
    Each import produces perfectly aligned instrumental + lyrics.
    """

    def __init__(self, songs_dir: Path = SONGS_DIR) -> None:
        self.songs_dir = songs_dir
        self.songs_dir.mkdir(parents=True, exist_ok=True)
        self.separator = VocalSeparator()
        self.lrc_gen = LRCGenerator()

    def import_song(
        self,
        audio_path: Path,
        title: str,
        artist: str,
        album: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Song:
        """
        Full import pipeline.

        Args:
            audio_path: Source song (with vocals)
            title: Song title
            artist: Artist name
            album: Optional album
            progress_callback: fn(message, percentage) for UI updates

        Returns:
            Song pointing to the created folder
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Not found: {audio_path}")

        def notify(msg: str, pct: float) -> None:
            logger.info(msg)
            if progress_callback:
                progress_callback(msg, pct)

        # Create song folder
        folder_name = self._clean_name(f"{artist}_{title}")
        song_folder = self.songs_dir / folder_name
        song_folder.mkdir(exist_ok=True)

        notify(f"Importing: {artist} - {title}", 5)

        # Copy original for backup
        original_backup = song_folder / f"original{audio_path.suffix}"
        if not original_backup.exists():
            shutil.copy(audio_path, original_backup)
            notify("Saved original backup", 10)

        # Stage 1: Demucs separation (80% of time)
        notify("Stage 1/3: Separating vocals from instrumental...", 15)

        def sep_cb(msg: str) -> None:
            notify(f"Demucs: {msg}", 40)

        sep_result = self.separator.separate(
            input_path=audio_path,
            output_dir=song_folder,
            progress_callback=sep_cb,
        )

        notify(
            f"Separation done ({sep_result.processing_time:.0f}s, "
            f"{sep_result.speed_factor})",
            70,
        )

        # Stage 2: Whisper LRC from isolated vocals
        notify("Stage 2/3: Transcribing vocals for lyrics...", 75)

        lrc_config = LRCGeneratorConfig(
            title=title, artist=artist, album=album
        )

        self.lrc_gen.generate_and_save(
            audio_path=sep_result.vocals_path,
            output_path=song_folder / "lyrics.lrc",
            config=lrc_config,
        )

        notify("Lyrics generated", 90)

        # Stage 3: Metadata
        notify("Stage 3/3: Saving metadata...", 95)

        meta = {
            "title":             title,
            "artist":            artist,
            "album":             album,
            "duration":          sep_result.source_duration,
            "instrumental_file": "instrumental.wav",
            "vocals_file":       "vocals.wav",
            "lyrics_file":       "lyrics.lrc",
            "original_file":     original_backup.name,
            "separation_model":  self.separator.model,
            "processing_time":   sep_result.processing_time,
            "imported_at":       datetime.utcnow().isoformat(),
        }

        (song_folder / "meta.json").write_text(
            json.dumps(meta, indent=2)
        )

        notify(f"Done! Saved to: {song_folder.name}", 100)
        return Song.from_folder(song_folder)

    @staticmethod
    def _clean_name(raw: str) -> str:
        return re.sub(r"[^\w]+", "-", raw.lower()).strip("-")


# ────────────────────── CLI ──────────────────────

if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

    console = Console()
    console.print("\n[bold cyan]Wrenify Full Song Import[/bold cyan]")
    console.print("[dim]Demucs + Whisper = perfectly aligned karaoke[/dim]\n")

    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python -m wrenify.songs.full_import <song.mp3>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        console.print(f"[red]Not found:[/red] {path}")
        sys.exit(1)

    title  = Prompt.ask("[cyan]Song title[/cyan]")
    artist = Prompt.ask("[cyan]Artist[/cyan]")
    album  = Prompt.ask("[cyan]Album (optional)[/cyan]", default="")

    console.print("\n[yellow]Estimated time: 5-15 minutes[/yellow]")
    console.print("[dim]Close browser/heavy apps for best speed on 8GB RAM[/dim]\n")

    if not Confirm.ask("Start import?", default=True):
        sys.exit(0)

    importer = FullSongImporter()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), console=console,
    ) as progress:
        task = progress.add_task("Starting...", total=100)

        def on_progress(msg: str, pct: float) -> None:
            progress.update(task, completed=pct, description=msg[:70])

        try:
            song = importer.import_song(
                path, title, artist, album or None, on_progress
            )
            console.print(f"\n[green]Imported:[/green] {song.display_name}")
            console.print(f"[dim]Folder: {song.instrumental_path.parent}[/dim]")
            console.print("\n[cyan]Karaoke:[/cyan] wrenify -> option 11 -> pick these files")
        except Exception as e:
            console.print(f"\n[red]Failed:[/red] {e}")
            import traceback
            traceback.print_exc()