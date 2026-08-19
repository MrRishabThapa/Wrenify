"""
Wrenify — Karaoke view widget.

Shows webcam feed as background with lyrics overlaid as subtitles.
Words change color based on their state:
    PENDING - white with black border
    ACTIVE  - yellow
    CORRECT - green
    WRONG   - red
    MISSED  - red
"""

from __future__ import annotations

import time
from typing import Optional

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from wrenify.karaoke.session import KaraokeSession
from wrenify.karaoke.timeline import TrackedWord, WordState
from wrenify.ui.voice_visualizer import VoiceVisualizer

# Color palette for word states
STATE_COLORS: dict[WordState, QColor] = {
    WordState.PENDING: QColor(255, 255, 255),   # White
    WordState.ACTIVE:  QColor(255, 215, 0),     # Gold/yellow
    WordState.CORRECT: QColor(76,  217, 100),   # Green
    WordState.WRONG:   QColor(255, 59,  48),    # Red
    WordState.MISSED:  QColor(255, 59,  48),    # Red
}

OUTLINE_COLOR = QColor(0, 0, 0, 220)


class KaraokeView(QWidget):
    """
    Main karaoke display: webcam + lyric subtitles.

    Uses a paintEvent to draw everything each frame:
    1. Webcam frame (scaled to widget)
    2. Progress bar at top
    3. Previous line (dimmed, above)
    4. Current line (highlighted words, center-bottom)
    5. Next line (dimmed, below)
    6. Score bar at bottom
    """

    def __init__(self, session: KaraokeSession, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session = session

        self._current_time: float = 0.0
        self._current_pixmap: Optional[QPixmap] = None

        self.setMinimumSize(960, 540)
        self.setStyleSheet("background: #0A0A15;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # For arrow keys

        self._offset_toast: Optional[str] = None
        self._offset_toast_until: float = 0.0

        # Recording indicator state
        self._recording_indicator_visible = False
        self.session.recording_toggled.connect(self._on_recording_toggled)

        # Repaint every tick
        self.session.tick_signal.connect(self._on_tick)

        # Small always-visible visualizer top-right
        self.mini_viz = VoiceVisualizer(self)
        self.mini_viz.setFixedHeight(60)
        self.mini_viz.NUM_BARS = 16  # Fewer bars for compact display

        # Wire session's audio signal to visualizer
        if hasattr(self.session, 'audio_level_signal'):
            self.session.audio_level_signal.connect(self._on_mic_level)

        # Preload font
        self._lyric_font = QFont("Inter", 28, QFont.Weight.Medium)
        self._lyric_font.setStyleHint(QFont.StyleHint.SansSerif)

        self._small_font = QFont("Inter", 14)

    def _on_recording_toggled(self, is_recording: bool) -> None:
        """Show/hide the REC indicator overlay."""
        self._recording_indicator_visible = is_recording
        self.update()

    def _on_mic_level(self, rms: float) -> None:
        """Update the mini visualizer with mic RMS level."""
        self.mini_viz.push_audio_level(rms)
        if rms > 0.002:
            self.mini_viz.set_status("working")
        else:
            self.mini_viz.set_status("silent")

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        # Mini visualizer top-right
        viz_w = 200
        viz_h = 60
        self.mini_viz.setGeometry(
            self.width() - viz_w - 20,
            50,
            viz_w,
            viz_h,
        )
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = event.key()

        if key == Qt.Key.Key_R:
            self.session.toggle_recording()
        elif key == Qt.Key.Key_Left:
            # Shift lyrics 0.5s EARLIER
            new_offset = self.session.timeline.offset_sec - 0.5
            self.session.timeline.set_offset(new_offset)
            self._show_offset_toast(new_offset)
        elif key == Qt.Key.Key_Right:
            # Shift lyrics 0.5s LATER
            new_offset = self.session.timeline.offset_sec + 0.5
            self.session.timeline.set_offset(new_offset)
            self._show_offset_toast(new_offset)
        elif key == Qt.Key.Key_Space:
            # Pause/resume
            if self.session.player.is_playing():
                self.session.pause()
            else:
                self.session.resume()
        else:
            super().keyPressEvent(event)

    def _show_offset_toast(self, offset: float) -> None:
        """Show a temporary toast with current offset."""
        self._offset_toast = f"Offset: {offset:+.1f}s (← / → to adjust)"
        self._offset_toast_until = time.monotonic() + 2.0
        self.update()

    def _on_tick(self, current_time: float) -> None:
        self._current_time = current_time
        self._update_webcam_frame()
        self.update()

    def _update_webcam_frame(self) -> None:
        """Grab latest webcam frame and convert to QPixmap."""
        if self.session.webcam is None:
            return
        frame = self.session.webcam.get_latest_frame()
        if frame is None:
            return

        # Convert BGR (OpenCV) to RGB (Qt)
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._current_pixmap = QPixmap.fromImage(qimg)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 1. Draw webcam background (or dark bg if no webcam)
        self._draw_webcam(painter)

        # 2. Draw dark overlay for text readability
        painter.fillRect(
            0, self.height() - 260, self.width(), 260,
            QColor(0, 0, 0, 140)
        )

        # 3. Draw lyrics
        self._draw_lyrics(painter)

        # 4. Draw progress bar
        self._draw_progress(painter)

        # 5. Draw score bar
        self._draw_score(painter)

        # 6. Draw offset toast if active
        self._draw_offset_toast(painter)

        # 7. Draw recording indicator if active
        self._draw_recording_indicator(painter)

        painter.end()

    def _draw_recording_indicator(self, painter: QPainter) -> None:
        """Pulsing red dot + REC text when recording is active."""
        if not self._recording_indicator_visible:
            return

        import math
        pulse = (math.sin(time.monotonic() * 3) + 1) / 2
        alpha = int(150 + 105 * pulse)

        # Red dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 59, 48, alpha))
        painter.drawEllipse(30, 80, 16, 16)

        # REC text
        painter.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        painter.setPen(QColor(255, 59, 48, alpha))
        painter.drawText(52, 94, "REC")

    def _draw_offset_toast(self, painter: QPainter) -> None:
        """Show a temporary toast with current lyrics offset."""
        if self._offset_toast is None:
            return
        if time.monotonic() > self._offset_toast_until:
            self._offset_toast = None
            return

        painter.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        painter.setPen(QColor(255, 215, 0))
        painter.fillRect(20, 20, 340, 40, QColor(0, 0, 0, 180))
        painter.drawText(30, 47, self._offset_toast)

    def _draw_webcam(self, painter: QPainter) -> None:
        if self._current_pixmap is None:
            painter.fillRect(self.rect(), QColor(20, 20, 30))
            return

        # Scale to fit widget, preserve aspect ratio, center crop
        scaled = self._current_pixmap.scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Center
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def _draw_lyrics(self, painter: QPainter) -> None:
        """Draw current line centered, prev/next lines above/below."""
        timeline = self.session.timeline

        # Get lines around current position
        line_idx = timeline.lyrics.line_index_at(self._current_time)
        if line_idx is None:
            return

        painter.setFont(self._lyric_font)

        y_center = self.height() - 130

        # Draw previous line (dimmer)
        if line_idx > 0:
            prev_line_words = [
                w for w in timeline.words if w.line_index == line_idx - 1
            ]
            self._draw_line_of_words(
                painter, prev_line_words,
                y=y_center - 60,
                dim=True,
            )

        # Draw current line
        current_line_words = [
            w for w in timeline.words if w.line_index == line_idx
        ]
        self._draw_line_of_words(
            painter, current_line_words,
            y=y_center,
            dim=False,
        )

        # Draw next line
        next_line_words = [
            w for w in timeline.words if w.line_index == line_idx + 1
        ]
        if next_line_words:
            self._draw_line_of_words(
                painter, next_line_words,
                y=y_center + 60,
                dim=True,
            )

    def _draw_line_of_words(
        self,
        painter: QPainter,
        words: list[TrackedWord],
        y: int,
        dim: bool,
    ) -> None:
        """Draw a horizontal line of words with per-word colors."""
        if not words:
            return

        # Measure total width to center the line
        metrics = painter.fontMetrics()
        space_width = metrics.horizontalAdvance(" ")
        # USE display_text (may be stretched) instead of text
        word_widths = [
            metrics.horizontalAdvance(w.display_text) for w in words
        ]
        total_width = sum(word_widths) + space_width * (len(words) - 1)

        x = (self.width() - total_width) // 2

        for word, width in zip(words, word_widths):
            color = STATE_COLORS.get(word.state, QColor(255, 255, 255))
            if dim:
                color = QColor(color.red(), color.green(), color.blue(), 80)

            # Use display_text here too
            self._draw_outlined_text(painter, word.display_text, x, y, color)
            x += width + space_width

    def _draw_outlined_text(
        self,
        painter: QPainter,
        text: str,
        x: int,
        y: int,
        color: QColor,
    ) -> None:
        """Draw text with black outline (like karaoke subtitles)."""
        path = QPainterPath()
        path.addText(x, y, painter.font(), text)

        # Outline
        outline_pen = QPen(OUTLINE_COLOR)
        outline_pen.setWidth(3)
        outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)

    def _draw_progress(self, painter: QPainter) -> None:
        duration = self.session.duration or 1.0
        progress = min(1.0, self._current_time / duration)

        bar_x = 40
        bar_y = 20
        bar_w = self.width() - 80
        bar_h = 6

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        # Fill (gradient could go here)
        painter.setBrush(QColor(180, 255, 57))  # Lime
        fill_w = int(bar_w * progress)
        painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

        # Time label
        painter.setFont(self._small_font)
        painter.setPen(QColor(255, 255, 255, 200))
        time_str = (
            f"{self._format_time(self._current_time)} / "
            f"{self._format_time(duration)}"
        )
        painter.drawText(bar_x, bar_y + 24, time_str)

    def _draw_score(self, painter: QPainter) -> None:
        """Draw live score summary at bottom."""
        timeline = self.session.timeline
        correct = sum(1 for w in timeline.words if w.state == WordState.CORRECT)
        wrong   = sum(1 for w in timeline.words if w.state == WordState.WRONG)
        missed  = sum(1 for w in timeline.words if w.state == WordState.MISSED)

        painter.setFont(self._small_font)
        text = f"Correct: {correct}   Wrong: {wrong}   Missed: {missed}"
        painter.setPen(QColor(255, 255, 255, 220))
        painter.drawText(40, self.height() - 20, text)

        # Keyboard hint (bottom-right, subtle)
        hint_text = "R = Record  |  Space = Pause  |  ← → = Sync Lyrics"
        painter.setFont(QFont("Inter", 10))
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawText(
            self.width() - 380, self.height() - 8, hint_text
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
