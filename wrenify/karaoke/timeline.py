"""
Wrenify — Karaoke timeline (music position tracking).

Tracks the current playback position and provides lyric line lookup.
No state machine, no scoring — just clean timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import TYPE_CHECKING, Optional

from loguru import logger

from wrenify.lyrics.parser import ParsedLyrics

if TYPE_CHECKING:
    from wrenify.audio.player import AudioPlayer


class WordDisplayState(Enum):
    """Visual state for karaoke display (NOT scoring)."""

    PAST = "past"           # Already passed
    CURRENT = "current"     # Being sung right now
    UPCOMING = "upcoming"   # Not yet reached


@dataclass
class DisplayWord:
    """A word with its display state for rendering."""

    text: str
    start: float
    end: float
    line_index: int
    word_index: int
    state: WordDisplayState
    is_line_start: bool = False  # First word of a line


@dataclass
class TrackedWord:
    """A lyric word with timing info (no state tracking)."""

    text:       str
    start:      float
    end:        float
    line_index: int
    word_index: int

    stretched_text: Optional[str] = None  # Cached stylized version

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def display_text(self) -> str:
        """Return stretched version if available, else plain text."""
        return self.stretched_text or self.text


class Timeline:
    """Song position tracker synced to audio player."""

    def __init__(
        self,
        lyrics: ParsedLyrics,
        player: Optional["AudioPlayer"] = None,
        offset_sec: float = 0.0,
    ) -> None:
        self.lyrics = lyrics
        self.offset_sec = offset_sec
        self._player = player
        self._start_time: Optional[float] = None
        self._paused_at: Optional[float] = None
        self._pause_offset: float = 0.0
        self._lock = Lock()

        # Flatten words for easy iteration
        self.words: list[TrackedWord] = self._build_tracked_words()

        # Compute stretched display text based on word durations
        self._apply_stretching()

        logger.info(
            f"Timeline created with {len(self.words)} words "
            f"({'player-synced' if player else 'clock-synced'})"
        )

    def _apply_stretching(self) -> None:
        """Compute stretched display text for all words based on duration."""
        from wrenify.lyrics.phonetic import PhoneticStylizer, StretchOptions

        # Slightly more aggressive stretching for karaoke display
        stylizer = PhoneticStylizer(
            StretchOptions(
                min_duration_sec=0.4,       # Stretch even shorter holds
                stretch_multiplier=3.0,     # A bit more visible
                max_repeats=8,              # Cap so it stays readable
            )
        )

        for word in self.words:
            try:
                word.stretched_text = stylizer.stylize_word(
                    word.text, word.duration
                )
            except Exception as e:
                logger.debug(f"Stretch failed for '{word.text}': {e}")
                word.stretched_text = word.text

    def _build_tracked_words(self) -> list[TrackedWord]:
        tracked: list[TrackedWord] = []

        for line_idx, line in enumerate(self.lyrics.lines):
            if not line.text:
                continue

            if line.has_word_timing:
                for word_idx, word in enumerate(line.words):
                    end = word.end
                    if end is None:
                        # Use next word's start, or line end
                        if word_idx + 1 < len(line.words):
                            end = line.words[word_idx + 1].start
                        else:
                            end = line.end or (word.start + 0.8)

                    tracked.append(TrackedWord(
                        text=word.text,
                        start=word.start,
                        end=end,
                        line_index=line_idx,
                        word_index=word_idx,
                    ))
            else:
                # Evenly distribute words across line duration
                words = line.text.split()
                if not words:
                    continue
                line_start = line.start
                line_end = line.end or (line.start + 3.0)
                line_dur = line_end - line_start
                per_word = line_dur / len(words)

                for word_idx, w in enumerate(words):
                    start = line_start + word_idx * per_word
                    end = start + per_word
                    tracked.append(TrackedWord(
                        text=w,
                        start=start,
                        end=end,
                        line_index=line_idx,
                        word_index=word_idx,
                    ))

        return tracked

    def start(self) -> None:
        with self._lock:
            self._start_time = time.monotonic()
            self._paused_at = None
            self._pause_offset = 0.0
        logger.info("Timeline started")

    def pause(self) -> None:
        with self._lock:
            if self._start_time is None or self._paused_at is not None:
                return
            self._paused_at = time.monotonic()

    def resume(self) -> None:
        with self._lock:
            if self._paused_at is None:
                return
            self._pause_offset += time.monotonic() - self._paused_at
            self._paused_at = None

    def stop(self) -> None:
        with self._lock:
            self._start_time = None

    def now(self) -> float:
        if self._player is not None:
            return self._player.position_sec() - self.offset_sec
        with self._lock:
            if self._start_time is None:
                return 0.0
            if self._paused_at is not None:
                base = self._paused_at - self._start_time - self._pause_offset
            else:
                base = time.monotonic() - self._start_time - self._pause_offset
            return base - self.offset_sec

    def set_offset(self, offset_sec: float) -> None:
        self.offset_sec = offset_sec
        logger.info(f"Lyric offset: {offset_sec:+.2f}s")

    def total_words(self) -> int:
        return len(self.words)

    def get_display_words(
        self,
        current_time: Optional[float] = None,
        context_lines: int = 2,
    ) -> list[DisplayWord]:
        """
        Get words around the current position with display states.

        Returns words from (current_line - 1) to (current_line + context_lines)
        each tagged as PAST, CURRENT, or UPCOMING based on song time.

        Args:
            current_time: Song time in seconds (defaults to self.now())
            context_lines: How many lines after current to include

        Returns:
            List of DisplayWord ready for rendering
        """
        now = current_time if current_time is not None else self.now()

        # Find current line index
        current_line_idx = self.lyrics.line_index_at(now)
        if current_line_idx is None:
            # Before first line or after last — show first few lines as upcoming
            if not self.lyrics.lines:
                return []
            # If past the end
            if self.lyrics.lines and now > (self.lyrics.lines[-1].end or float("inf")):
                # Show last few lines as all PAST
                start_line = max(0, len(self.lyrics.lines) - 3)
                result = []
                for li in range(start_line, len(self.lyrics.lines)):
                    line_words = [w for w in self.words if w.line_index == li]
                    for wi, w in enumerate(line_words):
                        result.append(DisplayWord(
                            text=w.display_text,
                            start=w.start,
                            end=w.end,
                            line_index=li,
                            word_index=wi,
                            state=WordDisplayState.PAST,
                            is_line_start=(wi == 0),
                        ))
                return result

            # Before start — show first lines as upcoming
            result = []
            for li in range(min(3, len(self.lyrics.lines))):
                line_words = [w for w in self.words if w.line_index == li]
                for wi, w in enumerate(line_words):
                    result.append(DisplayWord(
                        text=w.display_text,
                        start=w.start,
                        end=w.end,
                        line_index=li,
                        word_index=wi,
                        state=WordDisplayState.UPCOMING,
                        is_line_start=(wi == 0),
                    ))
            return result

        # Get words from previous line through current + context
        start_line = max(0, current_line_idx - 1)
        end_line = min(len(self.lyrics.lines), current_line_idx + context_lines + 1)

        result: list[DisplayWord] = []

        for li in range(start_line, end_line):
            line_words = [w for w in self.words if w.line_index == li]

            for wi, w in enumerate(line_words):
                # Determine state based on time
                if w.end <= now:
                    state = WordDisplayState.PAST
                elif w.start <= now < w.end:
                    state = WordDisplayState.CURRENT
                else:
                    state = WordDisplayState.UPCOMING

                result.append(DisplayWord(
                    text=w.display_text,
                    start=w.start,
                    end=w.end,
                    line_index=li,
                    word_index=wi,
                    state=state,
                    is_line_start=(wi == 0),
                ))

        return result

    def get_current_word(self, current_time: Optional[float] = None) -> Optional[TrackedWord]:
        """Get the single word being sung right now."""
        now = current_time if current_time is not None else self.now()

        for w in self.words:
            if w.start <= now < w.end:
                return w

        return None
