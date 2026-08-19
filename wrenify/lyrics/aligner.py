"""
Wrenify — Align clean lyrics text to Whisper word timestamps.

Takes:
  - Clean lyric lines (from Genius or user)
  - Whisper word-level transcription (from vocals.wav)

Returns:
  - LRC-formatted output with clean text but accurate timing

Uses dynamic programming to match Whisper's messy transcription
to the clean lyrics character-by-character.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from wrenify.speech.recognizer import Word


@dataclass
class AlignedLine:
    """One line of clean lyrics with a start timestamp."""

    text:  str
    start: float
    end:   Optional[float] = None
    # True when the timestamp was guessed (word not found in audio).
    # Lets callers detect a mismatch between lyrics and what is sung.
    estimated: bool = False


class LyricsAligner:
    """
    Aligns clean lyric text to Whisper word timestamps.

    Uses fuzzy word matching + sequential scanning to map
    each clean lyric line to a start time in the audio.
    """

    def __init__(self) -> None:
        pass

    def align(
        self,
        clean_lyrics: str,
        whisper_words: list[Word],
    ) -> list[AlignedLine]:
        """
        Align clean lyrics text against Whisper word timestamps.

        Args:
            clean_lyrics: Full lyrics as plain text (with line breaks)
            whisper_words: Word list from Whisper transcription

        Returns:
            List of AlignedLine — one per lyric line, with timestamps
        """
        # Split clean lyrics into lines
        lines = [
            line.strip() for line in clean_lyrics.split("\n")
            if line.strip()
        ]

        if not lines:
            logger.warning("No lyric lines to align")
            return []

        if not whisper_words:
            logger.warning("No Whisper words to align against")
            return [AlignedLine(text=line, start=0.0) for line in lines]

        logger.info(
            f"Aligning {len(lines)} lyric lines to "
            f"{len(whisper_words)} Whisper words"
        )

        # Normalize whisper words for matching
        whisper_normalized = [
            self._normalize(w.text) for w in whisper_words
        ]

        # Upper bound for estimates: the last word actually heard.
        # Lyrics beyond that point can't be timed meaningfully.
        audio_end = whisper_words[-1].end

        aligned: list[AlignedLine] = []
        whisper_idx = 0  # Current position in Whisper transcript

        for line_idx, line_text in enumerate(lines):
            # Get first meaningful word of this line
            line_words = self._words_from_line(line_text)
            if not line_words:
                continue

            first_word = self._normalize(line_words[0])

            # Search forward in Whisper transcript for this word
            match_idx = self._find_next_word(
                first_word, whisper_normalized, whisper_idx
            )

            if match_idx == -1:
                # Fallback: guess timestamp based on line position
                if aligned:
                    # Estimate: previous line time + a few seconds
                    estimated = aligned[-1].start + 3.0
                else:
                    estimated = 0.0

                # Never estimate past the last word in the audio
                if estimated >= audio_end:
                    estimated = max(0.0, audio_end - 0.5)

                logger.warning(
                    f"Line {line_idx+1} '{first_word}...' not found in Whisper, "
                    f"estimated {estimated:.1f}s"
                )
                aligned.append(
                    AlignedLine(text=line_text, start=estimated, estimated=True)
                )
                continue

            # Use Whisper's timestamp for this word
            timestamp = whisper_words[match_idx].start
            aligned.append(AlignedLine(text=line_text, start=timestamp))

            # Move Whisper cursor forward for next line
            whisper_idx = match_idx + 1

        # Fill in end times from next line's start
        for i in range(len(aligned) - 1):
            aligned[i].end = aligned[i + 1].start

        # Last line ends at last Whisper word
        if aligned and whisper_words:
            aligned[-1].end = whisper_words[-1].end

        # Fix any missing timestamps by interpolation
        self._fix_missing_timestamps(aligned, audio_end)

        logger.success(f"Aligned {len(aligned)} lines successfully")
        return aligned

    def _find_next_word(
        self,
        target: str,
        whisper_words: list[str],
        start_from: int,
    ) -> int:
        """Find target word in whisper transcript starting from index."""
        if not target:
            return -1

        # Try exact match first
        for i in range(start_from, len(whisper_words)):
            if whisper_words[i] == target:
                return i

        # Try fuzzy match (starts with same 3 chars)
        if len(target) >= 3:
            prefix = target[:3]
            for i in range(start_from, len(whisper_words)):
                if whisper_words[i].startswith(prefix):
                    return i

        # Try any word containing target substring.
        # Only for 2+ char targets — a 1-char word like "i" is a
        # substring of nearly every word and would match garbage.
        if len(target) >= 2:
            for i in range(start_from, len(whisper_words)):
                if target in whisper_words[i] or whisper_words[i] in target:
                    return i

        return -1

    def _fix_missing_timestamps(
        self, aligned: list[AlignedLine], audio_end: float = 0.0
    ) -> None:
        """Fill in reasonable timestamps for lines that failed to align."""
        for i in range(1, len(aligned)):
            # If this line's timestamp is BEFORE previous, that's wrong
            if aligned[i].start <= aligned[i - 1].start:
                # Estimate: 3 seconds after previous
                estimated = aligned[i - 1].start + 3.0
                if audio_end > 0:
                    estimated = min(estimated, max(0.0, audio_end - 0.5))
                aligned[i].start = estimated
                aligned[i].estimated = True
                logger.debug(f"Fixed backward-timestamp for line {i}")

    @staticmethod
    def _normalize(word: str) -> str:
        """Lowercase, strip punctuation, remove filler."""
        return re.sub(r"[^\w]", "", word.lower()).strip()

    @staticmethod
    def _words_from_line(line: str) -> list[str]:
        """Extract just the words from a line (no punctuation)."""
        return re.findall(r"\b\w+\b", line)


def format_as_lrc(
    aligned: list[AlignedLine],
    title: str = "",
    artist: str = "",
    album: str = "",
    duration_sec: float = 0.0,
) -> str:
    """Convert AlignedLine list to standard LRC format."""
    parts: list[str] = []

    if title:
        parts.append(f"[ti:{title}]")
    if artist:
        parts.append(f"[ar:{artist}]")
    if album:
        parts.append(f"[al:{album}]")

    if duration_sec > 0:
        m, s = divmod(int(duration_sec), 60)
        parts.append(f"[length:{m:02d}:{s:02d}]")

    parts.append("[re:Wrenify Hybrid Aligner]")
    parts.append("")

    for line in aligned:
        m, s = divmod(line.start, 60)
        timestamp = f"[{int(m):02d}:{s:05.2f}]"
        parts.append(f"{timestamp}{line.text}")

    return "\n".join(parts) + "\n"


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Lyrics Aligner Test (offline)[/bold cyan]\n")

    if len(sys.argv) >= 3:
        lyrics_file = Path(sys.argv[1]) if sys.argv[1] else None
        words_file = Path(sys.argv[2]) if sys.argv[2] else None
        if lyrics_file and words_file:
            clean = lyrics_file.read_text(encoding="utf-8")
            # Build Word list from "<start> <text>" lines
            words: list[Word] = []
            for raw in words_file.read_text(encoding="utf-8").splitlines():
                parts = raw.split(" ", 1)
                if len(parts) == 2:
                    words.append(
                        Word(text=parts[1], start=float(parts[0]), end=float(parts[0]) + 0.4)
                    )
            aligned = LyricsAligner().align(clean, words)
            console.print(format_as_lrc(aligned))
            sys.exit(0)

    # No args — synthetic self-test
    console.print("[dim]No args given — running synthetic self-test[/dim]\n")
    clean = "First we walked, no time for silence\nSo loud, and I don't need a sound"
    words = [
        Word("first", 15.3, 15.9, 0.9),
        Word("we", 16.0, 16.3, 0.9),
        Word("walked", 16.4, 17.0, 0.9),
        Word("no", 17.1, 17.4, 0.9),
        Word("time", 17.5, 17.9, 0.9),
        Word("for", 18.0, 18.3, 0.9),
        Word("silence", 18.4, 19.2, 0.9),
        Word("so", 19.9, 20.3, 0.9),
        Word("loud", 20.4, 21.0, 0.9),
        Word("and", 21.1, 21.4, 0.9),
        Word("i", 21.5, 21.8, 0.9),
        Word("dont", 21.9, 22.3, 0.9),
        Word("need", 22.4, 22.8, 0.9),
        Word("a", 22.9, 23.1, 0.9),
        Word("sound", 23.2, 23.9, 0.9),
    ]
    aligned = LyricsAligner().align(clean, words)
    output = format_as_lrc(aligned, title="Test", duration_sec=30.0)
    console.print(output)
    assert "[00:15.30]First we walked, no time for silence" in output
    assert "[00:19.90]So loud, and I don't need a sound" in output
    console.print("[green]Self-test OK[/green]")
