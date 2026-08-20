"""
Wrenify — Lyric display tracker.

Tracks which word and line are currently active based on song time.
No scoring — pure visual progress indicator for karaoke.
"""

from __future__ import annotations

from typing import Optional

from wrenify.karaoke.timeline import (
    DisplayWord,
    Timeline,
)


class LyricTracker:
    """Tracks current lyric position for word-by-word display."""

    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline

    def get_display_words(
        self,
        current_time: Optional[float] = None,
    ) -> list[DisplayWord]:
        """Get words with PAST/CURRENT/UPCOMING states for rendering."""
        return self.timeline.get_display_words(current_time)

    def get_current_line_index(self) -> Optional[int]:
        """Return index of the line currently being sung."""
        return self.timeline.lyrics.line_index_at(self.timeline.now())
