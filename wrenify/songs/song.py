"""
Wrenify — Song data structure.

A "song" in Wrenify is a pairing of:
- instrumental audio file (mp3/wav/ogg)
- synced lyrics file (.lrc)

Songs can be loaded from a folder or created ad-hoc from two file paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Song:
    """A karaoke-ready song: instrumental + lyrics."""

    title:             str
    artist:            str
    instrumental_path: Path
    lyrics_path:       Path

    # Optional metadata
    album:      Optional[str] = None
    duration:   Optional[float] = None
    key:        Optional[str] = None
    scale:      Optional[str] = None
    bpm:        Optional[float] = None
    cover_path: Optional[Path] = None

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"

    @property
    def has_cover(self) -> bool:
        return self.cover_path is not None and self.cover_path.exists()

    @classmethod
    def from_folder(cls, folder: Path) -> "Song":
        """
        Load a Song from a folder with this structure:
            folder/
              instrumental.mp3 (or .wav)
              lyrics.lrc
              meta.json (optional)
              cover.jpg (optional)
        """
        folder = Path(folder)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a folder: {folder}")

        # Find instrumental file
        instrumental: Optional[Path] = None
        for ext in ("mp3", "wav", "ogg", "flac"):
            candidate = folder / f"instrumental.{ext}"
            if candidate.exists():
                instrumental = candidate
                break

        if instrumental is None:
            raise FileNotFoundError(
                f"No instrumental.{{mp3,wav,ogg,flac}} in {folder}"
            )

        # Find lyrics
        lyrics = folder / "lyrics.lrc"
        if not lyrics.exists():
            raise FileNotFoundError(f"No lyrics.lrc in {folder}")

        # Load metadata if present
        meta_file = folder / "meta.json"
        meta: dict = {}
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())

        # Cover art
        cover = folder / "cover.jpg"
        if not cover.exists():
            cover = folder / "cover.png"
        if not cover.exists():
            cover = None

        return cls(
            title=meta.get("title", folder.name.replace("_", " ").title()),
            artist=meta.get("artist", "Unknown"),
            instrumental_path=instrumental,
            lyrics_path=lyrics,
            album=meta.get("album"),
            duration=meta.get("duration"),
            key=meta.get("key"),
            scale=meta.get("scale"),
            bpm=meta.get("bpm"),
            cover_path=cover,
        )

    @classmethod
    def from_files(
        cls,
        instrumental: Path,
        lyrics: Path,
        title: str = "Unknown",
        artist: str = "Unknown",
    ) -> "Song":
        """Create a Song from just two file paths (no folder structure)."""
        return cls(
            title=title,
            artist=artist,
            instrumental_path=Path(instrumental),
            lyrics_path=Path(lyrics),
        )

    def save_meta(self) -> None:
        """Write metadata to meta.json in the same folder as lyrics."""
        meta_file = self.lyrics_path.parent / "meta.json"
        meta = {
            "title":     self.title,
            "artist":    self.artist,
            "album":     self.album,
            "duration":  self.duration,
            "key":       self.key,
            "scale":     self.scale,
            "bpm":       self.bpm,
            "saved_at":  datetime.utcnow().isoformat(),
        }
        meta_file.write_text(json.dumps(meta, indent=2))
