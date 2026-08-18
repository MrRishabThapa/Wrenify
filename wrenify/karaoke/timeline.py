"""
Wrenify — Karaoke timeline and word state tracking.

The Timeline is the source of truth for:
- Current position in the song (in seconds)
- What state each word is in (pending, active, correct, etc.)
- When to transition words between states

State transitions:
    PENDING -> ACTIVE   when song time enters word's time window
    ACTIVE  -> CORRECT  when user sings it correctly
    ACTIVE  -> WRONG    when user sings wrong word
    ACTIVE  -> MISSED   when time window ends and no input received
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional

from loguru import logger

from wrenify.lyrics.parser import ParsedLyrics


class WordState(Enum):
    """State of a single word in the karaoke session."""

    PENDING = "pending"    # Not sung yet
    ACTIVE  = "active"     # Song is here right now
    CORRECT = "correct"    # User sang correctly
    WRONG   = "wrong"      # User sang wrong / mispronounced
    MISSED  = "missed"     # User did not sing during time window


@dataclass
class TrackedWord:
    """A lyric word with karaoke state tracking."""

    text:       str
    start:      float                  # Song time when word starts
    end:        float                  # Song time when word ends
    line_index: int                    # Which line this word belongs to
    word_index: int                    # Position within the line
    state:      WordState = WordState.PENDING

    # Timing data for scoring
    activated_at: Optional[float] = None  # When it became ACTIVE
    resolved_at:  Optional[float] = None  # When it left ACTIVE state
    match_score:  float = 0.0             # 0.0 to 1.0, how well user matched

    @property
    def duration(self) -> float:
        return self.end - self.start


class Timeline:
    """
    Master clock and state tracker for a karaoke session.

    Thread-safe: state can be updated from speech recognition thread
    while read from the UI thread.

    Usage:
        timeline = Timeline(lyrics)
        timeline.start()

        # From audio playback thread:
        song_time = timeline.now()

        # From UI thread:
        for word in timeline.words_in_window(song_time):
            render(word)
    """

    # How far ahead/behind a sung word can be to still count
    MATCH_WINDOW_SEC: float = 1.5

    def __init__(self, lyrics: ParsedLyrics) -> None:
        self.lyrics = lyrics
        self.words: list[TrackedWord] = self._build_tracked_words(lyrics)
        self._start_time: Optional[float] = None
        self._paused_at: Optional[float] = None
        self._pause_offset: float = 0.0
        self._lock = Lock()

        logger.info(f"Timeline created with {len(self.words)} trackable words")

    def _build_tracked_words(self, lyrics: ParsedLyrics) -> list[TrackedWord]:
        """Flatten lyrics into a list of TrackedWord objects."""
        tracked: list[TrackedWord] = []

        for line_idx, line in enumerate(lyrics.lines):
            if not line.text:
                continue

            # Use word-level timing if available
            if line.has_word_timing:
                for word_idx, word in enumerate(line.words):
                    tracked.append(
                        TrackedWord(
                            text=word.text,
                            start=word.start,
                            end=word.end or (word.start + 1.0),
                            line_index=line_idx,
                            word_index=word_idx,
                        )
                    )
            else:
                # Split line into words and estimate timing evenly
                words = line.text.split()
                if not words:
                    continue
                line_dur = (line.end or line.start + 3.0) - line.start
                per_word = line_dur / len(words)
                for word_idx, w in enumerate(words):
                    start = line.start + word_idx * per_word
                    tracked.append(
                        TrackedWord(
                            text=w,
                            start=start,
                            end=start + per_word,
                            line_index=line_idx,
                            word_index=word_idx,
                        )
                    )

        return tracked

    def start(self) -> None:
        """Start the timeline clock."""
        with self._lock:
            self._start_time = time.monotonic()
            self._paused_at = None
            self._pause_offset = 0.0
        logger.info("Timeline started")

    def pause(self) -> None:
        """Pause the clock."""
        with self._lock:
            if self._start_time is None or self._paused_at is not None:
                return
            self._paused_at = time.monotonic()
        logger.info("Timeline paused")

    def resume(self) -> None:
        """Resume from a pause."""
        with self._lock:
            if self._paused_at is None:
                return
            self._pause_offset += time.monotonic() - self._paused_at
            self._paused_at = None
        logger.info("Timeline resumed")

    def stop(self) -> None:
        """Stop the timeline."""
        with self._lock:
            self._start_time = None
            self._paused_at = None
        logger.info("Timeline stopped")

    def now(self) -> float:
        """Get current song time in seconds."""
        with self._lock:
            if self._start_time is None:
                return 0.0
            if self._paused_at is not None:
                return self._paused_at - self._start_time - self._pause_offset
            return time.monotonic() - self._start_time - self._pause_offset

    def update_word_states(self, current_time: Optional[float] = None) -> None:
        """
        Advance word states based on current time.

        Called every frame from the UI. Handles PENDING -> ACTIVE
        and ACTIVE -> MISSED transitions.
        """
        now = current_time if current_time is not None else self.now()

        with self._lock:
            for word in self.words:
                if word.state == WordState.PENDING:
                    if word.start <= now <= word.end:
                        word.state = WordState.ACTIVE
                        word.activated_at = now

                elif word.state == WordState.ACTIVE:
                    if now > word.end + 0.5:  # 500ms grace period
                        word.state = WordState.MISSED
                        word.resolved_at = now

    def mark_word_correct(self, word: TrackedWord, match_score: float) -> None:
        """Mark a word as correctly sung."""
        resolved_at = self.now()
        with self._lock:
            if word.state in (WordState.PENDING, WordState.ACTIVE):
                word.state = WordState.CORRECT
                word.match_score = match_score
                word.resolved_at = resolved_at

    def mark_word_wrong(self, word: TrackedWord, match_score: float) -> None:
        """Mark a word as sung incorrectly."""
        resolved_at = self.now()
        with self._lock:
            if word.state in (WordState.PENDING, WordState.ACTIVE):
                word.state = WordState.WRONG
                word.match_score = match_score
                word.resolved_at = resolved_at

    def words_in_window(
        self,
        current_time: Optional[float] = None,
        before_sec: float = 2.0,
        after_sec: float = 6.0,
    ) -> list[TrackedWord]:
        """Get words visible in the current display window."""
        now = current_time if current_time is not None else self.now()
        window_start = now - before_sec
        window_end = now + after_sec

        with self._lock:
            return [
                w for w in self.words
                if w.start >= window_start and w.start <= window_end
            ]

    def find_matchable_words(self, current_time: float) -> list[TrackedWord]:
        """Get words that a recognized speech should try to match against."""
        with self._lock:
            return [
                w for w in self.words
                if w.state in (WordState.ACTIVE, WordState.PENDING)
                and abs(w.start - current_time) <= self.MATCH_WINDOW_SEC
            ]

    def total_words(self) -> int:
        return len(self.words)

    def is_finished(self) -> bool:
        """True if all words have been resolved."""
        with self._lock:
            return all(w.state != WordState.PENDING for w in self.words)
