"""
Wrenify — Karaoke view widget.

Shows webcam feed as background with lyrics overlaid as subtitles.
The current lyric line is bright white, previous/next lines are
dimmed. No scoring — just fun singing.
"""

from __future__ import annotations

import time
from typing import Optional

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from wrenify.karaoke.session import KaraokeSession
from wrenify.karaoke.timeline import WordDisplayState
from wrenify.ui.voice_visualizer import VoiceVisualizer

WORD_COLORS = {
    WordDisplayState.PAST:     QColor(76, 217, 100, 160),   # Dim green
    WordDisplayState.CURRENT:  QColor(180, 255, 57, 255),   # Bright lime
    WordDisplayState.UPCOMING: QColor(255, 255, 255, 100),  # Dim white
}

# Current word gets slightly larger font
CURRENT_WORD_SCALE = 1.15


class KaraokeView(QWidget):
    """
    Main karaoke display: webcam + lyric subtitles.

    Uses a paintEvent to draw everything each frame:
    1. Webcam frame (scaled to widget)
    2. Progress bar at top
    3. Previous line (dimmed, above)
    4. Current line (bright, center-bottom)
    5. Next line (dimmed, below)
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
        self._small_font = QFont("Inter", 14)

        # Bottom control bar
        self._build_control_bar()

        # Toast overlay (centered, temporary)
        self._toast_label = QLabel(self)
        self._toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast_label.setStyleSheet("""
            color: #FFD700;
            background: rgba(10, 10, 21, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            font-size: 14px;
            font-weight: 600;
            padding: 8px 20px;
        """)
        self._toast_label.hide()

        # Robust keyboard shortcuts (work even when buttons have focus)
        QShortcut(QKeySequence(Qt.Key.Key_R), self, self._toggle_recording)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._toggle_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self,
                  lambda: self._nudge_lyrics(-0.5))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self,
                  lambda: self._nudge_lyrics(+0.5))

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
        # Control bar pinned to the bottom
        self._control_bar.setGeometry(
            0, self.height() - 64, self.width(), 64
        )

        # Toast centered just above the control bar
        self._toast_label.setGeometry(
            self.width() // 2 - 150, self.height() - 100, 300, 36
        )

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
            self._toggle_recording()
        elif key == Qt.Key.Key_Left:
            self._nudge_lyrics(-0.5)
        elif key == Qt.Key.Key_Right:
            self._nudge_lyrics(+0.5)
        elif key == Qt.Key.Key_Space:
            self._toggle_pause()
        else:
            super().keyPressEvent(event)

    def _nudge_lyrics(self, delta: float) -> None:
        """Shift lyrics timing by delta seconds (negative = earlier)."""
        new_offset = self.session.timeline.offset_sec + delta
        self.session.timeline.set_offset(new_offset)
        self._show_offset_toast(new_offset)

    def _show_toast(self, message: str) -> None:
        """Show a temporary toast above the control bar."""
        self._toast_label.setText(message)
        self._toast_label.show()
        self._toast_label.raise_()
        QTimer.singleShot(2200, self._toast_label.hide)

    # ───────────────── Control bar ─────────────────

    CONTROL_BAR_HEIGHT: int = 64

    def _build_control_bar(self) -> None:
        """Bottom control bar with karaoke playback buttons."""
        container = QWidget(self)
        container.setFixedHeight(self.CONTROL_BAR_HEIGHT)
        container.setStyleSheet("""
            background: rgba(10, 10, 21, 0.85);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(8)

        self.seek_back_btn = self._make_control_btn("⏮ 5s")
        self.pause_btn = self._make_control_btn("⏸ Pause")
        self.seek_fwd_btn = self._make_control_btn("⏭ 5s")

        layout.addWidget(self.seek_back_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.seek_fwd_btn)

        layout.addStretch()

        self.song_label = QLabel(
            f"{self.session.song.artist} — {self.session.song.title}"
        )
        self.song_label.setStyleSheet(
            "color: rgba(255,255,255,0.75); font-size: 13px; font-weight: 500;"
        )
        layout.addWidget(self.song_label)

        layout.addStretch()

        self.record_btn = self._make_control_btn("⏺ Record")
        self.autotune_btn = self._make_control_btn("✨ Auto-Tune")
        self.end_btn = self._make_control_btn("⏹ End", danger=True)

        layout.addWidget(self.record_btn)
        layout.addWidget(self.autotune_btn)
        layout.addWidget(self.end_btn)

        self.seek_back_btn.clicked.connect(lambda: self._seek(-5.0))
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.seek_fwd_btn.clicked.connect(lambda: self._seek(+5.0))
        self.record_btn.clicked.connect(self._toggle_recording)
        self.autotune_btn.clicked.connect(self._toggle_autotune)
        self.end_btn.clicked.connect(self._end_karaoke_early)

        self._control_bar = container

    def _make_control_btn(self, text: str, danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(90)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if danger:
            style = """
                QPushButton {
                    background: rgba(255, 59, 48, 0.15);
                    border: 1px solid rgba(255, 59, 48, 0.4);
                    border-radius: 20px;
                    color: white;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: rgba(255, 59, 48, 0.3);
                    border-color: rgba(255, 59, 48, 0.7);
                }
                QPushButton:pressed {
                    background: rgba(255, 59, 48, 0.4);
                }
            """
        else:
            style = """
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 20px;
                    color: white;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.15);
                    border-color: rgba(180, 255, 57, 0.4);
                }
                QPushButton:pressed {
                    background: rgba(180, 255, 57, 0.25);
                }
                QPushButton:disabled {
                    color: rgba(255, 255, 255, 0.3);
                    background: rgba(255, 255, 255, 0.02);
                }
            """
        btn.setStyleSheet(style)
        return btn

    def _seek(self, delta_sec: float) -> None:
        """Seek forward or back by N seconds."""
        if not self.session.player:
            return
        current = self.session.player.position_sec()
        new_pos = max(0.0, min(
            current + delta_sec, self.session.player.duration_sec()
        ))
        self.session.player.seek(new_pos)
        self._show_toast(f"Seeked to {new_pos:.1f}s")

    def _toggle_pause(self) -> None:
        if self.session.player.is_playing():
            self.session.pause()
            self.pause_btn.setText("▶ Resume")
        else:
            self.session.resume()
            self.pause_btn.setText("⏸ Pause")

    def _toggle_recording(self) -> None:
        """Toggle recording — audio auto-saves to library when session ends."""
        self.session.toggle_recording()
        if self.session.is_recording():
            self.record_btn.setText("⏹ Recording...")
            self.record_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 59, 48, 0.3);
                    border: 1px solid rgba(255, 59, 48, 0.6);
                    border-radius: 20px;
                    color: white;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: rgba(255, 59, 48, 0.4);
                }
            """)
        else:
            self.record_btn.setText("⏺ Record")
            self.record_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 20px;
                    color: white;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.15);
                    border-color: rgba(180, 255, 57, 0.4);
                }
            """)
        self._update_record_tooltip()

    def _toggle_autotune(self) -> None:
        """Toggle auto-tune post-processing for the recording."""
        self.session.toggle_autotune()
        if self.session.is_autotune_enabled():
            self.autotune_btn.setText("✨ Auto-Tune ON")
            self.autotune_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(180, 255, 57, 0.2);
                    border: 1px solid rgba(180, 255, 57, 0.6);
                    border-radius: 20px;
                    color: #B4FF39;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.3);
                }
            """)
            self._show_toast("Auto-tune enabled — will process on save")
        else:
            self.autotune_btn.setText("✨ Auto-Tune")
            self.autotune_btn.setStyleSheet(self._normal_btn_style())
            self._show_toast("Auto-tune disabled")
        self._update_record_tooltip()

    def _normal_btn_style(self) -> str:
        """Standard control button style."""
        return """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 20px;
                color: white;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(180, 255, 57, 0.15);
                border-color: rgba(180, 255, 57, 0.4);
            }
        """

    def _update_record_tooltip(self) -> None:
        """Show what will happen when the session ends."""
        if self.session.is_recording():
            if self.session.is_autotune_enabled():
                status = "Recording — auto-tune will apply on save"
            else:
                status = "Recording — raw version will be saved"
        else:
            status = ""
        self.record_btn.setToolTip(status)

    def _end_karaoke_early(self) -> None:
        """User clicked End — stop and save the recording."""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "End Karaoke?",
            "Stop now and save your recording?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.session.end_early()

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

        # 2. Draw lyrics (outlined text — readable without any overlay)
        self._draw_lyrics(painter)

        # 3. Draw progress bar
        self._draw_progress(painter)

        # 4. Draw offset toast if active
        self._draw_offset_toast(painter)

        # 5. Draw recording indicator if active
        self._draw_recording_indicator(painter)

        painter.end()

    def _draw_recording_indicator(self, painter: QPainter) -> None:
        """Pulsing red dot + REC text when recording is active."""
        if not self._recording_indicator_visible:
            return

        import math
        pulse = (math.sin(time.monotonic() * 3) + 1) / 2
        alpha = int(150 + 105 * pulse)

        # Pulsing lime dot makes recording visible without competing with lyrics.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(180, 255, 57, alpha))
        painter.drawEllipse(30, 80, 16, 16)

        # REC text
        painter.setFont(QFont("Inter", 13, QFont.Weight.Medium))
        painter.setPen(QColor(180, 255, 57, alpha))
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
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawRoundedRect(20, 20, 340, 40, 16, 16)
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
        """Draw lyrics word-by-word with progressive highlighting."""
        tracker = self.session.lyric_tracker
        display_words = tracker.get_display_words()

        if not display_words:
            return

        # Group words by line_index
        lines: dict[int, list] = {}
        for dw in display_words:
            lines.setdefault(dw.line_index, []).append(dw)

        sorted_line_indices = sorted(lines.keys())

        # Find which line is current (contains CURRENT word)
        current_line_idx = None
        for dw in display_words:
            if dw.state == WordDisplayState.CURRENT:
                current_line_idx = dw.line_index
                break

        if current_line_idx is None:
            # No current word — use first upcoming or last past
            for dw in display_words:
                if dw.state == WordDisplayState.UPCOMING:
                    current_line_idx = dw.line_index
                    break
            if current_line_idx is None and sorted_line_indices:
                current_line_idx = sorted_line_indices[-1]

        # Layout: center vertically around current line
        center_y = int(self.height() * 0.72)  # Lower third of screen
        line_height = 55

        # Font setup
        base_font = QFont("Inter", 28, QFont.Weight.Medium)
        current_font = QFont("Inter", 32, QFont.Weight.Bold)  # Slightly bigger for current word
        painter.setFont(base_font)

        metrics = painter.fontMetrics()
        space_width = metrics.horizontalAdvance(" ")

        for line_idx in sorted_line_indices:
            words_in_line = lines[line_idx]

            # Vertical position relative to current line
            if current_line_idx is not None:
                offset = line_idx - current_line_idx
            else:
                offset = sorted_line_indices.index(line_idx)

            y = center_y + offset * line_height

            # Skip lines way off screen
            if y < 50 or y > self.height() - 80:
                continue

            # Measure total line width for centering
            total_width = 0
            word_widths = []
            for dw in words_in_line:
                if dw.state == WordDisplayState.CURRENT:
                    painter.setFont(current_font)
                else:
                    painter.setFont(base_font)
                w = painter.fontMetrics().horizontalAdvance(dw.text)
                word_widths.append(w)
                total_width += w
            total_width += space_width * (len(words_in_line) - 1)

            # Start x for centered line
            x = (self.width() - total_width) // 2

            # Draw each word
            for dw, w_width in zip(words_in_line, word_widths):
                color = WORD_COLORS.get(dw.state, QColor(255, 255, 255, 100))

                if dw.state == WordDisplayState.CURRENT:
                    painter.setFont(current_font)
                else:
                    painter.setFont(base_font)

                self._draw_outlined_text(painter, dw.text, x, y, color)
                x += w_width + space_width

    def _draw_outlined_text(
        self,
        painter: QPainter,
        text: str,
        x: int,
        y: int,
        color: QColor,
    ) -> None:
        """Draw text with dark outline for readability over any background."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QBrush, QPainterPath, QPen

        path = QPainterPath()
        path.addText(x, y, painter.font(), text)

        # Dark outline
        outline_pen = QPen(QColor(0, 0, 0, 230))
        outline_pen.setWidth(4)
        outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Colored fill
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
        painter.setBrush(QColor(255, 255, 255, 45))
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 999, 999)

        gradient = QLinearGradient(bar_x, bar_y, bar_x + bar_w, bar_y)
        gradient.setColorAt(0, QColor(180, 255, 57))
        gradient.setColorAt(1, QColor(139, 92, 246))
        painter.setBrush(gradient)
        fill_w = int(bar_w * progress)
        painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 999, 999)

        # Time label
        painter.setFont(self._small_font)
        painter.setPen(QColor(255, 255, 255, 200))
        time_str = (
            f"{self._format_time(self._current_time)} / "
            f"{self._format_time(duration)}"
        )
        painter.drawText(bar_x, bar_y + 24, time_str)

    @staticmethod
    def _format_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
