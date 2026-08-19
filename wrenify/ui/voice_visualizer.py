"""
Wrenify — Real-time voice level visualizer widget.

A compact bar-graph that animates with the microphone RMS level.
Used in the karaoke view (mini, top-right) and the pre-karaoke
ready screen (prominent, bottom).

Status colors:
    working — yellow/violet gradient bars
    silent  — red bars (mic picking up nothing)
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class VoiceVisualizer(QWidget):
    """
    Draws NUM_BARS vertical bars whose heights follow the mic level.

    Feed it RMS levels via push_audio_level(); call set_status()
    to switch between the working (gradient) and silent (red) modes.
    """

    NUM_BARS: int = 24

    _COLOR_WORK_TOP    = QColor(180, 255, 57)    # Lime
    _COLOR_WORK_BOTTOM = QColor(139, 92, 246)    # Violet
    _COLOR_SILENT      = QColor(255, 184, 77)    # Warm amber
    _COLOR_BG          = QColor(10, 10, 21, 0)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._levels: list[float] = [0.0] * self.NUM_BARS
        self._status: str = "silent"
        self.setMinimumHeight(40)

    # ───────────────── Public API ─────────────────

    def push_audio_level(self, rms: float) -> None:
        """Feed a new RMS level (0.0-1.0); shifts the bar history left."""
        # Log-ish compression makes quiet speech visible
        scaled = min(1.0, max(0.0, rms * 12.0))
        self._levels = (self._levels + [scaled])[-self.NUM_BARS:]
        self.update()

    def set_status(self, status: str) -> None:
        """Set 'working' (gradient bars) or 'silent' (red bars)."""
        if status != self._status:
            self._status = status
            self.update()

    # ───────────────── Painting ─────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._COLOR_BG)

        bar_count = self.NUM_BARS
        gap = 3
        bar_w = max(2, (self.width() - gap * (bar_count + 1)) // bar_count)
        usable_h = self.height() - 6

        working = self._status == "working"

        for i, level in enumerate(self._levels):
            x = gap + i * (bar_w + gap)
            bar_h = max(2, int(usable_h * level))
            y = self.height() - 4 - bar_h

            if working:
                # Gradient by height: yellow (loud) -> violet (quiet)
                t = 1.0 - level
                color = QColor(
                    self._lerp(self._COLOR_WORK_TOP.red(),
                               self._COLOR_WORK_BOTTOM.red(), t),
                    self._lerp(self._COLOR_WORK_TOP.green(),
                               self._COLOR_WORK_BOTTOM.green(), t),
                    self._lerp(self._COLOR_WORK_TOP.blue(),
                               self._COLOR_WORK_BOTTOM.blue(), t),
                )
            else:
                color = self._COLOR_SILENT

            painter.setPen(Qt.PenStyle.NoPen)
            if working:
                gradient = QLinearGradient(x, y, x, self.height())
                gradient.setColorAt(0, self._COLOR_WORK_TOP)
                gradient.setColorAt(1, self._COLOR_WORK_BOTTOM)
                painter.setBrush(gradient)
            else:
                painter.setBrush(color)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2, 2)

        painter.end()

    @staticmethod
    def _lerp(a: int, b: int, t: float) -> int:
        return int(a + (b - a) * t)
