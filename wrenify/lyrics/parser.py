"""
Wrenify — LRC lyrics file parser.

LRC is a simple text format used by karaoke and music apps.
Each line starts with a timestamp in brackets:

    [ti:Song Title]
    [ar:Artist Name]
    [al:Album Name]

    [00:12.34]First line of lyrics
    [00:15.67]Second line of lyrics
    [00:19.20]Third line

Extended LRC supports word-level timing (used by Musixmatch):

    [00:12.34]<00:12.34>First <00:12.60>line <00:12.90>of <00:13.20>lyrics

This parser handles both formats and normalizes them into
structured LyricsLine / LyricsWord objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# LRC timestamp regex: [mm:ss.xx] or [mm:ss.xxx]
TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")

# Word-level tag inside a line: <mm:ss.xx>
WORD_TAG_RE = re.compile(r"<(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?>")

# Metadata tags: [ti:...], [ar:...], [al:...], [length:...]
META_RE = re.compile(r"\[(ti|ar|al|length|by|offset):(.+?)\]")


@dataclass
class LyricsWord:
    """A single word with a timestamp."""

    text:  str
    start: float                # Seconds from song start
    end:   Optional[float] = None  # Filled in during post-processing


@dataclass
class LyricsLine:
    """One line of lyrics with a timestamp and optional word-level timing."""

    text:  str                  # Full line text, e.g. "Hello darkness my old friend"
    start: float                # Line start time in seconds
    end:   Optional[float] = None  # Filled in from next line's start
    words: list[LyricsWord] = field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        if self.end is None:
            return None
        return self.end - self.start

    @property
    def has_word_timing(self) -> bool:
        return len(self.words) > 0

    def word_at(self, time_sec: float) -> Optional[LyricsWord]:
        """Get the word being sung at a given time."""
        if not self.has_word_timing:
            return None
        for word in self.words:
            end = word.end or (self.end or float("inf"))
            if word.start <= time_sec < end:
                return word
        return None


@dataclass
class ParsedLyrics:
    """Full parsed LRC file with metadata."""

    lines:    list[LyricsLine]
    title:    Optional[str] = None
    artist:   Optional[str] = None
    album:    Optional[str] = None
    duration: Optional[float] = None  # Total song length in seconds
    offset:   float = 0.0             # Global timing offset (ms)

    def line_at(self, time_sec: float) -> Optional[LyricsLine]:
        """Get the line being sung at a given time."""
        adjusted = time_sec + (self.offset / 1000.0)
        for line in self.lines:
            end = line.end or float("inf")
            if line.start <= adjusted < end:
                return line
        return None

    def line_index_at(self, time_sec: float) -> Optional[int]:
        """Get the index of the line at a given time."""
        adjusted = time_sec + (self.offset / 1000.0)
        for i, line in enumerate(self.lines):
            end = line.end or float("inf")
            if line.start <= adjusted < end:
                return i
        return None

    def upcoming_lines(self, time_sec: float, count: int = 3) -> list[LyricsLine]:
        """Get next N lines starting from current position."""
        idx = self.line_index_at(time_sec)
        if idx is None:
            return []
        return self.lines[idx : idx + count]

    def __len__(self) -> int:
        return len(self.lines)


class LRCParser:
    """
    Parses LRC file content into structured lyrics.

    Handles:
    - Standard LRC with line-level timestamps
    - Extended LRC with word-level <tags>
    - Multiple timestamps per line (e.g. repeated choruses)
    - Metadata tags (title, artist, album, offset)
    """

    def parse(self, lrc_content: str) -> ParsedLyrics:
        """Parse LRC text into ParsedLyrics."""
        lines: list[LyricsLine] = []
        metadata: dict[str, str] = {}
        offset_ms: float = 0.0

        for raw_line in lrc_content.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            # Check for metadata first
            meta_match = META_RE.match(raw_line)
            if meta_match:
                key, value = meta_match.group(1), meta_match.group(2).strip()
                metadata[key] = value
                if key == "offset":
                    try:
                        offset_ms = float(value)
                    except ValueError:
                        pass
                continue

            # Extract all line-level timestamps at the start
            timestamps = self._extract_leading_timestamps(raw_line)
            if not timestamps:
                continue

            # Everything after the timestamps is the lyric text
            text_start = raw_line.rfind("]") + 1
            text = raw_line[text_start:].strip()

            # Skip empty timestamped lines (often just formatting)
            if not text:
                # Still create a line for timing (some LRC uses this for instrumental gaps)
                for ts in timestamps:
                    lines.append(LyricsLine(text="", start=ts))
                continue

            # Check for word-level timing tags inside the text
            words = self._extract_word_timing(text)
            clean_text = WORD_TAG_RE.sub("", text).strip()

            # Create a line for each timestamp (handles repeated choruses)
            for ts in timestamps:
                # Adjust word timestamps to be absolute
                adjusted_words = [
                    LyricsWord(text=w.text, start=w.start)
                    for w in words
                ] if words else []

                lines.append(
                    LyricsLine(
                        text=clean_text,
                        start=ts,
                        words=adjusted_words,
                    )
                )

        # Sort by start time (multiple timestamps may be out of order)
        lines.sort(key=lambda ln: ln.start)

        # Fill in end times from next line's start
        for i in range(len(lines) - 1):
            lines[i].end = lines[i + 1].start
            # Also fill in word end times where possible
            self._fill_word_ends(lines[i])

        # Last line has no end unless duration metadata exists
        if lines and "length" in metadata:
            lines[-1].end = self._parse_length(metadata["length"])
            self._fill_word_ends(lines[-1])

        return ParsedLyrics(
            lines=lines,
            title=metadata.get("ti"),
            artist=metadata.get("ar"),
            album=metadata.get("al"),
            duration=self._parse_length(metadata.get("length", "")),
            offset=offset_ms,
        )

    def parse_file(self, path: Path) -> ParsedLyrics:
        """Parse an LRC file from disk."""
        content = path.read_text(encoding="utf-8", errors="replace")
        return self.parse(content)

    def _extract_leading_timestamps(self, line: str) -> list[float]:
        """Extract all [mm:ss.xx] timestamps at the start of a line."""
        timestamps: list[float] = []
        pos = 0
        while True:
            match = TIMESTAMP_RE.match(line, pos)
            if not match:
                break
            timestamps.append(self._timestamp_to_seconds(match))
            pos = match.end()
        return timestamps

    def _extract_word_timing(self, text: str) -> list[LyricsWord]:
        """Extract <mm:ss.xx>word pairs from an extended LRC line."""
        words: list[LyricsWord] = []
        matches = list(WORD_TAG_RE.finditer(text))

        for i, match in enumerate(matches):
            start = self._timestamp_to_seconds(match)
            word_start = match.end()
            word_end = (
                matches[i + 1].start() if i + 1 < len(matches) else len(text)
            )
            word_text = text[word_start:word_end].strip()
            if word_text:
                words.append(LyricsWord(text=word_text, start=start))
        return words

    def _fill_word_ends(self, line: LyricsLine) -> None:
        """Fill in end times for words in a line based on next word or line end."""
        if not line.words:
            return
        for i in range(len(line.words) - 1):
            line.words[i].end = line.words[i + 1].start
        # Last word ends at line end (or start + 1s if unknown)
        line.words[-1].end = line.end or (line.words[-1].start + 1.0)

    @staticmethod
    def _timestamp_to_seconds(match: re.Match) -> float:
        """Convert regex match of a timestamp to seconds."""
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        frac_str = match.group(3) or "0"
        # Pad or truncate fractional part to 3 digits (milliseconds)
        frac = int(frac_str.ljust(3, "0")[:3])
        return minutes * 60 + seconds + frac / 1000.0

    @staticmethod
    def _parse_length(length_str: str) -> Optional[float]:
        """Parse [length:03:45] style metadata."""
        if not length_str:
            return None
        match = re.match(r"(\d+):(\d+)", length_str)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))
        return None


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("\n[bold cyan]LRC Parser Test[/bold cyan]\n")

    if len(sys.argv) < 2:
        # Built-in test with sample LRC
        sample_lrc = """[ti:Test Song]
[ar:Wrenify Test]
[al:Demo]
[length:00:30]

[00:00.00]
[00:05.20]Hello darkness my old friend
[00:09.80]I've come to talk with you again
[00:14.50]Because a vision softly creeping
[00:19.00]Left its seeds while I was sleeping
[00:24.00]And the vision that was planted in my brain
"""
        console.print("[yellow]No file given, using built-in sample[/yellow]\n")
        parser = LRCParser()
        result = parser.parse(sample_lrc)
    else:
        path = Path(sys.argv[1])
        if not path.exists():
            console.print(f"[red]File not found:[/red] {path}")
            sys.exit(1)
        parser = LRCParser()
        result = parser.parse_file(path)

    console.print(f"[green]Title:[/green]    {result.title}")
    console.print(f"[green]Artist:[/green]   {result.artist}")
    console.print(f"[green]Album:[/green]    {result.album}")
    console.print(f"[green]Duration:[/green] {result.duration}s")
    console.print(f"[green]Offset:[/green]   {result.offset}ms")
    console.print(f"[green]Lines:[/green]    {len(result)}\n")

    table = Table(title="Parsed Lyrics")
    table.add_column("#",     justify="right", style="dim")
    table.add_column("Start", justify="right", style="cyan")
    table.add_column("End",   justify="right", style="cyan")
    table.add_column("Text",  style="white")

    for i, line in enumerate(result.lines):
        end_str = f"{line.end:.2f}s" if line.end else "-"
        table.add_row(
            str(i + 1),
            f"{line.start:.2f}s",
            end_str,
            line.text or "[dim](empty)[/dim]",
        )

    console.print(table)

    # Test lookup at various times
    console.print("\n[bold]Line lookup test:[/bold]")
    for t in [3.0, 7.0, 12.0, 17.0, 22.0]:
        line = result.line_at(t)
        text = line.text if line else "[dim]none[/dim]"
        console.print(f"  t={t:5.1f}s -> {text}")
