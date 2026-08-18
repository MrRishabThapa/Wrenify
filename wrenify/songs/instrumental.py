"""
Wrenify — Fetch instrumental audio from YouTube.

Uses yt-dlp to search YouTube for a karaoke instrumental of a song
and download it as MP3 (extracted via ffmpeg, which must be on PATH).

Results are screened before downloading:
- Rejects remix / reverb / slowed / cover / mashup / live / vocals uploads
- Keeps only 2-8 minute videos (skips live streams and hour-long loops)
- Ranks the survivors by channel subscriber count so real creators
  rank higher than spam channels

The chosen upload (title, channel, URL) is logged so the pick can be
verified before/after download.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from wrenify.core.config import EXPORT_DIR

# Title keywords that signal a bad pick (remakes, effects, vocals)
BANNED_KEYWORDS: tuple[str, ...] = (
    "remix",
    "reverb",
    "slowed",
    "sped up",
    "spedup",
    "cover",
    "mashup",
    "reaction",
    "with lyrics",
    "with vocals",
    "official audio",
    "nightcore",
    "8d",
)

MIN_DURATION_SEC: int = 120    # 2 min — skip trailers/shorts
MAX_DURATION_SEC: int = 480    # 8 min — skip live streams and loops
SEARCH_LIMIT: int = 10         # How many results to screen


class InstrumentalFetcher:
    """
    Searches YouTube for an instrumental and downloads it as MP3.

    Usage:
        fetcher = InstrumentalFetcher()
        path = fetcher.search("Perfect", "Ed Sheeran")
        if path:
            print(f"Saved instrumental: {path}")
    """

    def search(self, title: str, artist: Optional[str] = None) -> Optional[Path]:
        """
        Search, screen and download the best instrumental match.

        Args:
            title: Song title
            artist: Artist name (optional, improves the search)

        Returns:
            Path to the downloaded MP3, or None if nothing was found.
        """
        query = f"{title} {artist} karaoke instrumental".strip() if artist \
            else f"{title} karaoke instrumental"
        logger.info(f"Searching YouTube for: {query}")

        try:
            entries = self._fetch_search_results(query)
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return None

        if not entries:
            logger.warning("No results found on YouTube")
            return None

        screened = self._screen(entries)
        if not screened:
            logger.warning(
                "All results were filtered out (remixes, covers, "
                "live streams, etc.) — nothing suitable found"
            )
            return None

        best = self._rank(screened)[0]
        logger.info(
            f"Best match: '{best.get('title')}' by "
            f"{best.get('channel') or best.get('uploader')}"
            f" ({best.get('duration', 0)}s, "
            f"{best.get('channel_follower_count', 0) or 0} subscribers)"
        )
        logger.info(f"Source: {best.get('webpage_url')}")

        try:
            return self._download(best, title, artist)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _fetch_search_results(self, query: str) -> list[dict]:
        """Get top search results metadata without downloading."""
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            # Default web client often gets HTTP 403 from YouTube;
            # android/web_safari clients bypass the bot check.
            "extractor_args": {
                "youtube": {"player_client": ["android", "web_safari"]}
            },
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"ytsearch{SEARCH_LIMIT}:{query}", download=False
            )
        return info.get("entries", []) if info else []

    def _screen(self, entries: list[dict]) -> list[dict]:
        """Keep only plausible instrumental uploads."""
        candidates: list[dict] = []
        for entry in entries:
            title = (entry.get("title") or "").lower()
            duration = entry.get("duration") or 0

            if duration < MIN_DURATION_SEC or duration > MAX_DURATION_SEC:
                continue
            if any(kw in title for kw in BANNED_KEYWORDS):
                continue

            candidates.append(entry)
        return candidates

    @staticmethod
    def _rank(candidates: list[dict]) -> list[dict]:
        """Sort by channel subscriber count (real creators first)."""
        def key(entry: dict) -> tuple[int, int]:
            followers = entry.get("channel_follower_count") or 0
            views = entry.get("view_count") or 0
            return followers, views

        return sorted(candidates, key=key, reverse=True)

    def _download(
        self,
        entry: dict,
        title: str,
        artist: Optional[str],
    ) -> Path:
        """Download the chosen video's audio and extract it to MP3."""
        from yt_dlp import YoutubeDL

        base = self._safe_name(f"{artist or 'unknown'}_{title}_instrumental")
        outtmpl = str(EXPORT_DIR / f"{base}.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {"player_client": ["android", "web_safari"]}
            },
        }

        with YoutubeDL(opts) as ydl:
            ydl.download([entry["webpage_url"]])

        mp3 = EXPORT_DIR / f"{base}.mp3"
        if not mp3.exists():
            raise FileNotFoundError(
                f"Expected downloaded file missing: {mp3}"
            )

        logger.success(f"Saved instrumental: {mp3}")
        return mp3

    @staticmethod
    def _safe_name(text: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace."""
        cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return cleaned or "instrumental"


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Instrumental Fetcher[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print(
            "[red]Usage:[/red] "
            "python -m wrenify.songs.instrumental \"<title>\" [\"<artist>\"]"
        )
        sys.exit(1)

    song_title = sys.argv[1]
    song_artist = sys.argv[2] if len(sys.argv) > 2 else None

    console.print(
        f"[cyan]Fetching instrumental for:[/cyan] "
        f"{song_artist + ' - ' if song_artist else ''}{song_title}\n"
    )

    fetcher = InstrumentalFetcher()
    result = fetcher.search(song_title, song_artist)

    if result is not None:
        console.print(f"\n[green]Saved:[/green] {result}")
        console.print(
            "[dim]Next: poetry run wrenify -> option 11 -> "
            "pick this file + your .lrc[/dim]"
        )
    else:
        console.print("\n[red]Could not fetch an instrumental.[/red]")
        sys.exit(1)
