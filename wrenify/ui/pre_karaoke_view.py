"""
Wrenify — Pre-karaoke ready screen.

Shows the selected song, a live webcam preview, and a headphone
reminder. The user signals they are ready by raising an open palm
then closing it into a fist (best-effort OpenCV skin detection) —
or by clicking the Start button. A 3-2-1 countdown follows, then
ready_signal fires and the session begins.

If no webcam is available the gesture hint is hidden and only the
button works.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from loguru import logger
from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.audio.capture import AudioCapture
from wrenify.songs.song import Song
from wrenify.ui.voice_visualizer import VoiceVisualizer
from wrenify.video.camera import WebcamCapture


class PreKaraokeView(QWidget):
    """
    Ready screen before a karaoke session starts.

    Emits:
        ready_signal  — user confirmed ready (countdown finished)
        cancel_signal — user backed out
    """

    ready_signal  = pyqtSignal()
    cancel_signal = pyqtSignal()

    COUNTDOWN_START: int = 3
    GESTURE_WINDOW_SEC: float = 4.0  # Max time between palm and fist

    def __init__(self, song: Song, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.song = song

        # 1. Safe defaults FIRST — before any code that may reference them
        self.webcam: Optional[WebcamCapture] = None
        self.audio_capture: Optional[AudioCapture] = None
        self._gesture_timer: Optional[QTimer] = None
        self._mic_timer: Optional[QTimer] = None
        self._countdown_timer: Optional[QTimer] = None
        self._gesture_state: str = "idle"
        self._palm_seen_at: Optional[float] = None
        self._countdown_value: int = self.COUNTDOWN_START
        self._emitted = False

        assert QThread.currentThread() == self.thread(), (
            "PreKaraokeView must be created on the main thread"
        )

        self._build_ui()

        # 2. Timers BEFORE capture startup (startup code starts them)
        self._gesture_timer = QTimer(self)
        self._gesture_timer.setInterval(66)  # ~15fps
        self._gesture_timer.timeout.connect(self._on_gesture_frame)

        self._mic_timer = QTimer(self)
        self._mic_timer.setInterval(50)  # ~20fps
        self._mic_timer.timeout.connect(self._on_mic_level)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        # 3. LAST: start captures (all attributes now exist)
        self._try_start_webcam()
        self._try_start_mic()

    # ───────────────── UI ─────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet("background: #0A0A15; color: white;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)

        # Song title
        title = QLabel(self.song.display_name)
        title.setFont(QFont("Inter", 34, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #B4FF39;")
        layout.addWidget(title)

        # Webcam preview
        self._preview = QLabel()
        self._preview.setFixedSize(480, 270)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "background: #16161f; border: 1px solid #242434; border-radius: 12px;"
        )
        self._preview.setText("Starting webcam...")
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # Headphone reminder
        headphones = QLabel(
            "IMPORTANT: Wear headphones so the mic does not pick up "
            "the song audio."
        )
        headphones.setFont(QFont("Inter", 14))
        headphones.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headphones.setStyleSheet("color: #FFD93D;")
        layout.addWidget(headphones)

        # Gesture hint
        self._hint = QLabel(
            "Raise an open palm, then close it into a fist  —  or press Start"
        )
        self._hint.setFont(QFont("Inter", 15))
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color: #cfcbe4;")
        layout.addWidget(self._hint)

        # Mic level visualizer (always visible, even if webcam fails)
        self._viz = VoiceVisualizer()
        self._viz.setFixedSize(320, 70)
        layout.addWidget(
            self._viz, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        self._viz_label = QLabel("Mic level")
        self._viz_label.setFont(QFont("Inter", 11))
        self._viz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._viz_label.setStyleSheet("color: #8f8aa9;")
        layout.addWidget(
            self._viz_label, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        # Countdown label (hidden until triggered)
        self._countdown_label = QLabel("")
        self._countdown_label.setFont(QFont("Inter", 96, QFont.Weight.Black))
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet("color: #B4FF39;")
        self._countdown_label.hide()
        layout.addWidget(self._countdown_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._start_btn = QPushButton("I'm Ready")
        self._start_btn.setFixedSize(180, 50)
        self._start_btn.setStyleSheet(self._button_style("#8B5CF6"))
        self._start_btn.clicked.connect(self._begin_countdown)

        self._cancel_btn = QPushButton("Back")
        self._cancel_btn.setFixedSize(120, 50)
        self._cancel_btn.setStyleSheet(self._button_style("#333"))
        self._cancel_btn.clicked.connect(self._cancel)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _button_style(bg: str) -> str:
        return (
            f"QPushButton {{"
            f"  background: {bg}; color: white; border-radius: 8px;"
            f"  font-size: 16px; font-weight: bold; border: none;"
            f"}}"
        )

    # ───────────────── Webcam ─────────────────

    def _try_start_webcam(self) -> None:
        try:
            self.webcam = WebcamCapture()
            self.webcam.start()
            # getattr guard: never reference a timer that may not exist yet
            gesture_timer = getattr(self, '_gesture_timer', None)
            if gesture_timer is not None:
                gesture_timer.start()
            logger.info("Pre-karaoke: webcam + gesture detection ready")
        except Exception as e:
            logger.warning(f"Webcam unavailable on ready screen: {e}")
            # Stop a partially-started capture so no thread leaks
            if self.webcam is not None:
                try:
                    self.webcam.stop()
                except Exception:
                    pass
            self.webcam = None
            self._hint.setText("Webcam unavailable — press Start to begin")
            self._draw_no_webcam_placeholder()

    def _draw_no_webcam_placeholder(self) -> None:
        """Show an informative placeholder when webcam is unavailable."""
        self._preview.setText(
            "📷\n\n"
            "Webcam not available\n\n"
            "Test with: cheese   or   ffplay /dev/video0\n"
            "If those fail too, it is a driver/permission issue, "
            "not Wrenify."
        )
        self._preview.setFont(QFont("Inter", 12))
        self._preview.setStyleSheet(
            "background: #16161f; border: 2px dashed #505064; "
            "border-radius: 12px; color: #c8c8dc;"
        )

    def _try_start_mic(self) -> None:
        """Start mic capture to feed the voice visualizer."""
        try:
            self.audio_capture = AudioCapture()
            self.audio_capture.start()
            mic_timer = getattr(self, '_mic_timer', None)
            if mic_timer is not None:
                mic_timer.start()
            logger.info("Pre-karaoke: mic ready")
        except Exception as e:
            logger.warning(f"Mic unavailable on ready screen: {e}")
            # Stop a partially-started capture so no stream leaks
            if self.audio_capture is not None:
                try:
                    self.audio_capture.stop()
                except Exception:
                    pass
            self.audio_capture = None
            self._viz.set_status("silent")

    def _on_mic_level(self) -> None:
        """Poll mic chunks and push levels into the visualizer."""
        if not self.isVisible() or self.audio_capture is None:
            return
        chunk = self.audio_capture.get_chunk(timeout=0.0)
        if chunk is None:
            return
        rms = float(np.sqrt(np.mean(chunk**2)))
        self._viz.push_audio_level(rms)
        if rms > 0.002:
            self._viz.set_status("working")
        else:
            self._viz.set_status("silent")

    def _teardown_safely(self) -> None:
        """Stop everything in the correct order to prevent segfault."""
        # Stop timers FIRST (they may access other resources)
        for timer_name in ('_gesture_timer', '_mic_timer', '_countdown_timer'):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                try:
                    timer.stop()
                except Exception as e:
                    logger.debug(f"Failed to stop {timer_name}: {e}")

        # Then stop capture threads
        if getattr(self, 'audio_capture', None) is not None:
            try:
                self.audio_capture.stop()
            except Exception as e:
                logger.debug(f"Audio capture cleanup: {e}")
            self.audio_capture = None

        if getattr(self, 'webcam', None) is not None:
            try:
                self.webcam.stop()
            except Exception as e:
                logger.debug(f"Webcam cleanup: {e}")
            self.webcam = None

    # ───────────────── Gesture detection ─────────────────

    def _on_gesture_frame(self) -> None:
        """Grab a frame and run best-effort palm -> fist detection."""
        if not self.isVisible() or self._emitted:
            return
        if self.webcam is None:
            return
        frame = self.webcam.get_latest_frame()
        if frame is None:
            return

        # Show live preview
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self._preview.width(),
                self._preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        ratio = self._skin_ratio(frame.image)
        self._advance_gesture(ratio)

    def _skin_ratio(self, bgr: np.ndarray) -> float:
        """Fraction of frame pixels that look like skin (0.0 to 1.0)."""
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 40, 40), (25, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        return float(np.count_nonzero(mask)) / float(mask.size)

    def _advance_gesture(self, ratio: float) -> None:
        """State machine: idle -> palm -> fist -> countdown."""
        if self._gesture_state == "idle":
            if ratio > 0.18:  # Open palm fills a good chunk of the frame
                self._gesture_state = "palm"
                self._palm_seen_at = cv2.getTickCount() / cv2.getTickFrequency()
                logger.debug(f"Palm detected (skin ratio {ratio:.2f})")

        elif self._gesture_state == "palm":
            elapsed = (
                cv2.getTickCount() / cv2.getTickFrequency() - self._palm_seen_at
            )
            if elapsed > self.GESTURE_WINDOW_SEC:
                self._gesture_state = "idle"
            elif ratio < 0.06:  # Fist: much less skin visible
                logger.info("Fist detected — gesture confirmed")
                self._gesture_state = "idle"
                self._begin_countdown()

    # ───────────────── Countdown ─────────────────

    def _begin_countdown(self) -> None:
        if self._emitted or self._countdown_timer.isActive():
            return
        self._start_btn.setEnabled(False)
        self._hint.setText("Get ready...")
        self._countdown_label.show()
        self._countdown_value = self.COUNTDOWN_START
        self._countdown_label.setText(str(self._countdown_value))
        self._countdown_timer.start()

    def _on_countdown_tick(self) -> None:
        self._countdown_value -= 1
        if self._countdown_value > 0:
            self._countdown_label.setText(str(self._countdown_value))
            return

        self._countdown_timer.stop()
        self._countdown_label.setText("GO!")
        logger.info("Countdown finished, starting session")
        QTimer.singleShot(400, self._emit_ready)

    def _emit_ready(self) -> None:
        if self._emitted:
            return
        self._emitted = True
        self._teardown_safely()
        self.ready_signal.emit()

    def _cancel(self) -> None:
        if self._emitted:
            return
        self._emitted = True
        self._teardown_safely()
        self.cancel_signal.emit()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._teardown_safely()
        super().closeEvent(event)
