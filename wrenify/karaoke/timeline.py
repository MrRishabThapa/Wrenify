"""
Wrenify — Karaoke timeline (music position tracking).

Tracks the current playback position and provides lyric line lookup.
No state machine, no scoring — just clean timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Optional

from loguru import logger

from wrenify.lyrics.parser import ParsedLyrics

if TYPE_CHECKING:
    from wrenify.audio.player import AudioPlayer


@dataclass
class TrackedWord:
    """A lyric word with timing info (no state tracking)."""

    text:       str
    start:      float
    end:        float
    line_index: int
    word_index: int

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def display_text(self) -> str:
        return self.text  # No stretching logic here anymore


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

        logger.info(
            f"Timeline created with {len(self.words)} words "
            f"({'player-synced' if player else 'clock-synced'})"
        )

    def _build_tracked_words(self) -> list[TrackedWord]:
        tracked: list[TrackedWord] = []

        for line_idx, line in enumerate(self.lyrics.lines):
            if not line.text:
                continue
            if line.has_word_timing:
                for word_idx, word in enumerate(line.words):
                    tracked.append(TrackedWord(
                        text=word.text,
                        start=word.start,
                        end=word.end or (word.start + 1.0),
                        line_index=line_idx,
                        word_index=word_idx,
                    ))
            else:
                words = line.text.split()
                if not words:
                    continue
                line_dur = (line.end or line.start + 3.0) - line.start
                per_word = line_dur / len(words)
                for word_idx, w in enumerate(words):
                    start = line.start + word_idx * per_word
                    tracked.append(TrackedWord(
                        text=w,
                        start=start,
                        end=start + per_word,
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
