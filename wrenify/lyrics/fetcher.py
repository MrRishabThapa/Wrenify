"""
Wrenify — Fetch synced lyrics from online sources.

Uses the `syncedlyrics` library which aggregates from:
- Musixmatch
- NetEase
- Lrclib.net
- Megalobiz
- Genius (fallback)

Returns .lrc content as a string. Save it to disk and parse it
with LRCParser to get structured lyrics.

Falls back gracefully if no synced lyrics are found — many songs
only have plain (unsynced) lyrics available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import syncedlyrics
from loguru import logger


@dataclass
class LyricsSearchResult:
    """Result of a lyrics search."""

    lrc_content:  Optional[str]     # Raw LRC text if synced found
    plain_text:   Optional[str]     # Plain lyrics if only unsynced
    source:       str               # Which provider gave us the result
    is_synced:    bool
    query:        str

    @property
    def found(self) -> bool:
        return self.lrc_content is not None or self.plain_text is not None


class LyricsFetcher:
    """
    Fetches lyrics from online sources.

    Prefers synced (.lrc) lyrics when available.
    Falls back to plain text.

    Usage:
        fetcher = LyricsFetcher()
        result = fetcher.search("Someone Like You", "Adele")
        if result.is_synced:
            (path / "lyrics.lrc").write_text(result.lrc_content)
    """

    def search(
        self,
        title: str,
        artist: Optional[str] = None,
        prefer_synced: bool = True,
    ) -> LyricsSearchResult:
        """
        Search for lyrics by song title and optional artist.

        Args:
            title: Song title
            artist: Artist name (improves accuracy)
            prefer_synced: If True, only return synced lyrics

        Returns:
            LyricsSearchResult (check .found and .is_synced)
        """
        query = f"{title} {artist}".strip() if artist else title
        logger.info(f"Searching lyrics for: {query}")

        # Try synced first
        try:
            lrc = syncedlyrics.search(
                query,
                allow_plain_format=not prefer_synced,
            )
        except Exception as e:
            logger.error(f"Lyrics search failed: {e}")
            return LyricsSearchResult(
                lrc_content=None,
                plain_text=None,
                source="error",
                is_synced=False,
                query=query,
            )

        if lrc:
            # Check if we got actually synced content (has timestamps)
            is_synced = "[" in lrc and ":" in lrc
            logger.success(
                f"Found {'synced' if is_synced else 'plain'} lyrics ({len(lrc)} chars)"
            )
            return LyricsSearchResult(
                lrc_content=lrc if is_synced else None,
                plain_text=lrc if not is_synced else None,
                source="syncedlyrics",
                is_synced=is_synced,
                query=query,
            )

        logger.warning(f"No lyrics found for: {query}")
        return LyricsSearchResult(
            lrc_content=None,
            plain_text=None,
            source="none",
            is_synced=False,
            query=query,
        )

    def fetch_plain_lyrics(
        self,
        title: str,
        artist: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fetch plain lyrics text (no timestamps) from lyrics providers.

        Prefers sources that give clean, well-punctuated text.
        Returns None if nothing was found.
        """
        result = self.search(title, artist, prefer_synced=False)
        content = result.lrc_content or result.plain_text
        if not content:
            return None

        cleaned = self._strip_timestamps(content)
        if not cleaned:
            logger.warning(f"Lyrics for {title} stripped to nothing")
            return None

        logger.success(f"Got plain lyrics ({len(cleaned)} chars)")
        return cleaned

    @staticmethod
    def _strip_timestamps(text: str) -> str:
        """Remove [mm:ss.xx] timestamps and metadata tags from LRC text."""
        import re

        # Remove line-level timestamps
        text = re.sub(r"\[\d{2}:\d{2}\.\d{2,3}\]", "", text)
        # Remove word-level timestamps
        text = re.sub(r"<\d{2}:\d{2}\.\d{2,3}>", "", text)
        # Remove metadata tags
        text = re.sub(r"\[(ti|ar|al|by|length|offset|re|ve):[^\]]*\]", "", text)
        # Clean up extra whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def save_to_file(
        self,
        result: LyricsSearchResult,
        output_path: Path,
    ) -> bool:
        """Save fetched lyrics to disk. Returns True on success."""
        content = result.lrc_content or result.plain_text
        if not content:
            logger.warning("Nothing to save — no lyrics found")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved lyrics to: {output_path}")
        return True


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print("\n[bold cyan]Lyrics Fetcher Test[/bold cyan]\n")

    if len(sys.argv) >= 3:
        title = sys.argv[1]
        artist = sys.argv[2]
    else:
        title = Prompt.ask("[cyan]Song title[/cyan]", default="Someone Like You")
        artist = Prompt.ask("[cyan]Artist[/cyan]", default="Adele")

    fetcher = LyricsFetcher()
    result = fetcher.search(title, artist)

    if not result.found:
        console.print("[red]No lyrics found[/red]")
        sys.exit(1)

    console.print(f"\n[green]Source:[/green]  {result.source}")
    console.print(f"[green]Synced:[/green]  {result.is_synced}")
    console.print(f"[green]Length:[/green]  {len(result.lrc_content or result.plain_text)} chars\n")

    # Preview first 20 lines
    content = result.lrc_content or result.plain_text or ""
    preview = "\n".join(content.splitlines()[:20])
    console.print("[bold]Preview:[/bold]")
    console.print(preview)

    # Offer to save
    save = Prompt.ask("\n[cyan]Save to file?[/cyan]", choices=["y", "n"], default="n")
    if save == "y":
        ext = "lrc" if result.is_synced else "txt"
        filename = f"{artist.lower().replace(' ', '-')}_{title.lower().replace(' ', '-')}.{ext}"
        output = Path("exports") / filename
        fetcher.save_to_file(result, output)
        console.print(f"[green]Saved to {output}[/green]")
