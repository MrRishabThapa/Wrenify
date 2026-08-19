"""
Wrenify — Lyric line tracker.

Simply tracks which lyric line is currently active based on
song time. No matching, no scoring — Wrenify is for FUN singing.
"""

from __future__ import annotations

from typing import Optional

from wrenify.karaoke.timeline import Timeline


class LyricTracker:
    """Tracks the currently active lyric line based on song position."""

    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline
        self._current_line_index: Optional[int] = None

    def get_current_line_index(self) -> Optional[int]:
        """Return index of the line currently being sung."""
        current_time = self.timeline.now()
        return self.timeline.lyrics.line_index_at(current_time)

    def get_visible_lines(
        self,
        before: int = 1,
        after: int = 2,
    ) -> list[tuple[int, str, bool]]:
        """
        Get lines to display: previous, current, upcoming.

        Returns list of (line_index, text, is_current)
        """
        current = self.get_current_line_index()
        if current is None:
            # Before first line — show first few upcoming
            lines = self.timeline.lyrics.lines[: after + 1]
            return [(i, line.text, False) for i, line in enumerate(lines)]

        results = []
        start = max(0, current - before)
        end = min(len(self.timeline.lyrics.lines), current + after + 1)

        for i in range(start, end):
            line = self.timeline.lyrics.lines[i]
            results.append((i, line.text, i == current))

        return results
