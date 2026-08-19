"""
Wrenify — Pre-karaoke ready screen with live gesture feedback.

Shows the selected song, a live webcam feed with a gesture bounding
box, and a headphone reminder. The user signals they are ready by
raising an open palm then closing it into a fist (best-effort OpenCV
skin detection) — or by clicking the Start button. A 3-2-1 countdown
follows, then ready_signal fires and the session begins.

Visual feedback:
    NO_HAND      — no box, "Raise your hand to begin"
    HAND_SEEN    — RED box, "Show your open palm"
    PALM_OPEN    — GREEN box, "Close your fist to start"
    FIST_CLOSED  — BRIGHT GREEN pulsing box
    COUNTDOWN    — BRIGHT GREEN pulsing box + big countdown number
"""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Optional

import cv2
import numpy as np
from loguru import logger
from PyQt6.QtCore import QPoint, QPointF, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QLabel, QPushButton, QWidget

from wrenify.audio.capture import AudioCapture
from wrenify.songs.song import Song
from wrenify.ui.voice_visualizer import VoiceVisualizer
from wrenify.ui.theme import THEME
from wrenify.video.camera import WebcamCapture
from wrenify.vision.gestures import GestureDetector, HandGesture


class PreKaraokeState(Enum):
    """UI states for the pre-karaoke gesture flow."""

    NO_HAND     = "no_hand"        # Waiting for user to raise hand
    HAND_SEEN   = "hand_seen"      # Hand detected but pose not identified
    PALM_OPEN   = "palm_open"      # Open palm confirmed
    FIST_CLOSED = "fist_closed"    # Fist detected, countdown starting
    COUNTDOWN   = "countdown"      # 3-2-1 in progress
    STARTING    = "starting"       # Emitting ready signal


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
    GESTURE_HOLD_FRAMES: int = 6  # ~0.4s at 15fps gesture timer

    # Box colors per state
    COLOR_HAND   = QColor(255, 59, 48)      # Red
    COLOR_PALM   = QColor(76, 217, 100)     # Green
    COLOR_FIST   = QColor(180, 255, 57)     # Bright lime

    def __init__(self, song: Song, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.song = song
        self._song_title = song.display_name

        # 1. Safe defaults FIRST — before any code that may reference them
        self.webcam: Optional[WebcamCapture] = None
        self.audio_capture: Optional[AudioCapture] = None
        self.gesture_detector = GestureDetector()
        self._gesture_timer: Optional[QTimer] = None
        self._mic_timer: Optional[QTimer] = None
        self._countdown_timer: Optional[QTimer] = None

        # Gesture visualization state
        self._state: PreKaraokeState = PreKaraokeState.NO_HAND
        self._current_bbox: Optional[tuple[int, int, int, int]] = None
        self._last_bbox: Optional[tuple[int, int, int, int]] = None
        self._current_gesture = HandGesture.NONE
        self._gesture_confidence: float = 0.0
        self._frame_width: int = 0
        self._frame_height: int = 0
        self._current_pixmap: Optional[QPixmap] = None
        self._gesture_hold_count: int = 0
        self._last_gesture = HandGesture.NONE
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
        self.setStyleSheet("background: transparent; color: white;")

        # Mic level visualizer (always visible, even if webcam fails)
        self._viz = VoiceVisualizer(self)
        self._viz.setFixedSize(240, 50)
        self._viz_label = QLabel("Mic level", self)
        self._viz_label.setFont(QFont("Inter", 10))
        self._viz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._viz_label.setStyleSheet(f"color: {THEME.colors.text_tertiary}; font-size: 11px;")

        # Buttons — smaller, refined
        self._start_btn = QPushButton("I'm Ready", self)
        self._start_btn.setFixedSize(160, 44)
        self._start_btn.setStyleSheet(self._button_style("#8B5CF6", "white"))
        self._start_btn.clicked.connect(self._begin_countdown)

        self._cancel_btn = QPushButton("Back", self)
        self._cancel_btn.setFixedSize(120, 44)
        self._cancel_btn.setStyleSheet(self._button_style("rgba(255,255,255,.07)", "white"))
        self._cancel_btn.clicked.connect(self._cancel)

    @staticmethod
    def _button_style(bg: str, fg: str) -> str:
        return (
            f"QPushButton {{"
            f"  background: {bg}; color: {fg}; border-radius: 999px;"
            f"  font-size: 14px; font-weight: 600; border: 1px solid {THEME.colors.border_subtle};"
            f"}}"
            f"QPushButton:hover {{ border-color: {THEME.colors.border_hover}; background: {THEME.colors.glass_hi}; }}"
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Position overlay child widgets."""
        w, h = self.width(), self.height()

        # Voice visualizer sits within the painted glass panel at bottom-left.
        self._viz.setGeometry(36, h - 82, 220, 42)
        self._viz_label.setGeometry(32, h - 112, 230, 20)

        # Buttons bottom-center, just above the instruction pill
        btn_y = h - 175
        self._start_btn.move(w // 2 - 145, btn_y)
        self._cancel_btn.move(w // 2 + 25, btn_y)
        super().resizeEvent(event)

    # ───────────────── Painting ─────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 1. Background
        self._draw_ambient_background(painter)
        self._draw_visualizer_panel(painter)

        # 2. Song title — small, elegant, top center
        self._draw_title(painter)

        # 3. Webcam feed
        webcam_rect = self._draw_webcam(painter)

        # 4. Gesture bounding box on top of webcam
        self._draw_gesture_box(painter, webcam_rect)

        # 5. Headphone reminder — subtle line below webcam
        self._draw_headphone_warning(painter, webcam_rect)

        # 6. Instruction text / countdown
        self._draw_current_instruction(painter)

        # 7. Gesture debug indicator (top left)
        self._draw_gesture_indicator(painter)

        painter.end()

    def _draw_ambient_background(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor(10, 10, 21))
        for x, y, scale, color in ((.16, .18, .60, QColor(139, 92, 246, 40)), (.84, .82, .50, QColor(180, 255, 57, 28))):
            radius = int(min(self.width(), self.height()) * scale)
            gradient = QRadialGradient(QPointF(int(self.width() * x), int(self.height() * y)), radius)
            gradient.setColorAt(0, color)
            edge = QColor(color); edge.setAlpha(0)
            gradient.setColorAt(1, edge)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(int(self.width() * x) - radius, int(self.height() * y) - radius, radius * 2, radius * 2)

    def _draw_visualizer_panel(self, painter: QPainter) -> None:
        panel = QRect(20, self.height() - 126, 252, 102)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(panel, 16, 16)

    def _draw_title(self, painter: QPainter) -> None:
        """Song title — small, elegant, top center."""
        font = QFont("Inter", 20, QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QColor(180, 255, 57, 200))  # Lime at 80%
        painter.drawText(
            self.rect().adjusted(0, 25, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self._song_title,
        )

    def _draw_headphone_warning(self, painter: QPainter, webcam_rect: QRect) -> None:
        """Subtle headphone reminder below the webcam feed."""
        font = QFont("Inter", 11)
        painter.setFont(font)
        painter.setPen(QColor(255, 190, 110, 150))  # Warm orange at 60%
        text = "Headphones recommended so the mic does not pick up the song"
        pill_y = min(webcam_rect.bottom() + 14, self.height() - 170)
        painter.drawText(
            QRect(0, pill_y, self.width(), 24),
            Qt.AlignmentFlag.AlignHCenter,
            text,
        )

    def _draw_webcam(self, painter: QPainter) -> QRect:
        """Draw webcam frame fitted to the widget. Returns its rect."""
        if self._current_pixmap is None:
            return self._draw_no_webcam_placeholder(painter)

        # Cap at ~60% of screen height for breathing room
        max_h = int(self.height() * 0.6)
        scaled = self._current_pixmap.scaled(
            self.width(),
            max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        rect = QRect(x, y, scaled.width(), scaled.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(x, y, scaled)
        painter.restore()
        painter.setPen(QPen(QColor(255, 255, 255, 42), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 20, 20)
        return rect

    def _draw_no_webcam_placeholder(self, painter: QPainter) -> QRect:
        """Draw an informative placeholder when webcam is unavailable."""
        rect = QRect(20, 110, self.width() - 40, self.height() - 240)
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(rect, 20, 20)

        # A simple camera glyph, painted from geometry so it remains crisp
        # and consistent with the rest of the interface at every scale.
        icon_x = rect.center().x() - 28
        icon_y = rect.y() + rect.height() // 2 - 64
        painter.setPen(QPen(QColor(180, 255, 57, 150), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(icon_x, icon_y + 8, 56, 38, 8, 8)
        painter.drawRoundedRect(icon_x + 11, icon_y, 20, 12, 4, 4)
        painter.drawEllipse(icon_x + 19, icon_y + 17, 18, 18)

        msg_font = QFont("Inter", 14)
        painter.setFont(msg_font)
        painter.setPen(QColor(200, 200, 220))
        painter.drawText(
            QRect(rect.x(), rect.y() + rect.height() // 2 + 20,
                  rect.width(), 40),
            Qt.AlignmentFlag.AlignCenter,
            "Webcam not available",
        )

        hint_font = QFont("Inter", 11)
        painter.setFont(hint_font)
        painter.setPen(QColor(140, 140, 160))
        painter.drawText(
            QRect(rect.x(), rect.y() + rect.height() // 2 + 60,
                  rect.width(), 30),
            Qt.AlignmentFlag.AlignCenter,
            "Test with: cheese  or  ffplay /dev/video0",
        )
        return self.rect()

    def _draw_gesture_box(self, painter: QPainter, webcam_rect: QRect) -> None:
        """Draw a colored bounding box around the detected hand."""
        if self._frame_width == 0 or self._frame_height == 0:
            return

        # Fist/countdown: keep drawing the last known box even if the
        # blob briefly disappears.
        bbox = self._current_bbox
        if bbox is None:
            if self._state in (
                PreKaraokeState.FIST_CLOSED,
                PreKaraokeState.COUNTDOWN,
                PreKaraokeState.STARTING,
            ):
                bbox = self._last_bbox
            else:
                return
        if bbox is None:
            return

        # Map frame coords -> displayed webcam rect.
        # The frame is already mirrored at capture time, so no flip here.
        x, y, w, h = bbox
        scale_x = webcam_rect.width() / self._frame_width
        scale_y = webcam_rect.height() / self._frame_height
        box_x = int(webcam_rect.x() + x * scale_x)
        box_y = int(webcam_rect.y() + y * scale_y)
        box_w = max(10, int(w * scale_x))
        box_h = max(10, int(h * scale_y))

        # Color + thickness by state
        if self._state == PreKaraokeState.HAND_SEEN:
            color, thickness, pulse = self.COLOR_HAND, 3, False
        elif self._state == PreKaraokeState.PALM_OPEN:
            color, thickness, pulse = self.COLOR_PALM, 4, False
        elif self._state in (
            PreKaraokeState.FIST_CLOSED,
            PreKaraokeState.COUNTDOWN,
            PreKaraokeState.STARTING,
        ):
            color, thickness, pulse = self.COLOR_FIST, 5, True
        else:
            return  # No hand or still waiting

        # Pulse effect
        if pulse:
            pulse_val = (math.sin(time.monotonic() * 4) + 1) / 2  # 0-1
            alpha = int(180 + 75 * pulse_val)                     # 180-255
            color = QColor(color.red(), color.green(), color.blue(), alpha)
            thickness += int(2 * pulse_val)

        # Box with rounded corners
        pen = QPen(color, thickness)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

        # Corner markers (cyber/HUD aesthetic)
        marker_len = 20
        marker_pen = QPen(color, thickness + 2)
        marker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(marker_pen)
        # Top-left
        painter.drawLine(box_x, box_y, box_x + marker_len, box_y)
        painter.drawLine(box_x, box_y, box_x, box_y + marker_len)
        # Top-right
        painter.drawLine(box_x + box_w - marker_len, box_y,
                         box_x + box_w, box_y)
        painter.drawLine(box_x + box_w, box_y,
                         box_x + box_w, box_y + marker_len)
        # Bottom-left
        painter.drawLine(box_x, box_y + box_h, box_x + marker_len,
                         box_y + box_h)
        painter.drawLine(box_x, box_y + box_h - marker_len,
                         box_x, box_y + box_h)
        # Bottom-right
        painter.drawLine(box_x + box_w - marker_len, box_y + box_h,
                         box_x + box_w, box_y + box_h)
        painter.drawLine(box_x + box_w, box_y + box_h - marker_len,
                         box_x + box_w, box_y + box_h)

    def _draw_current_instruction(self, painter: QPainter) -> None:
        """Draw the state-appropriate instruction at the bottom."""
        instructions = {
            PreKaraokeState.NO_HAND:     "Raise your hand to begin",
            PreKaraokeState.HAND_SEEN:   "Show your open palm",
            PreKaraokeState.PALM_OPEN:   "Close your fist to start",
            PreKaraokeState.FIST_CLOSED: "Get ready...",
            PreKaraokeState.COUNTDOWN:   str(self._countdown_value),
            PreKaraokeState.STARTING:    "GO!",
        }

        text = instructions.get(self._state, "")
        if not text:
            return

        # Big centered countdown number — big but light
        if self._state in (PreKaraokeState.COUNTDOWN,
                           PreKaraokeState.STARTING):
            font = QFont("Inter", 180, QFont.Weight.Thin)
            painter.setFont(font)
            painter.setPen(QPen(QColor(180, 255, 57, 55), 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(QColor(180, 255, 57, 230))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
            return

        # Elegant pill-shaped instruction near the bottom
        font = QFont("Inter", 24, QFont.Weight.Normal)
        painter.setFont(font)

        if self._state == PreKaraokeState.NO_HAND:
            text_color = QColor(200, 200, 220, 160)   # Dim gray
        elif self._state == PreKaraokeState.HAND_SEEN:
            text_color = QColor(255, 149, 0, 204)     # Orange 80%
        elif self._state == PreKaraokeState.PALM_OPEN:
            text_color = QColor(76, 217, 100, 204)    # Green 80%
        else:
            text_color = QColor(180, 255, 57, 204)    # Lime 80%

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()

        pill_x = (self.width() - text_width) // 2 - 20
        pill_y = self.height() - 120
        pill_w = text_width + 40
        pill_h = text_height + 16

        painter.setPen(QPen(QColor(180, 255, 57, 60), 1))
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, pill_h // 2, pill_h // 2)

        painter.setPen(text_color)
        painter.drawText(
            pill_x + 20,
            pill_y + text_height + 4,
            text,
        )

    def _draw_gesture_indicator(self, painter: QPainter) -> None:
        """Small debug badge in the top-left corner."""
        text = (
            f"state={self._state.value} | "
            f"gesture={self._current_gesture.value} | "
            f"conf={self._gesture_confidence:.2f}"
        )
        painter.setFont(QFont("Inter", 9))
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawText(16, 30, text)

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

        # Finally release detector
        if getattr(self, 'gesture_detector', None) is not None:
            try:
                self.gesture_detector.close()
            except Exception as e:
                logger.debug(f"Gesture cleanup: {e}")

    # ───────────────── Gesture detection ─────────────────

    def _on_gesture_frame(self) -> None:
        """Grab a frame, detect gesture, update preview + state."""
        if not self.isVisible() or self._emitted:
            return
        if self.webcam is None:
            self.update()
            return

        frame_data = self.webcam.get_latest_frame()
        if frame_data is None:
            self.update()
            return

        # Mirror the frame (selfie view)
        frame = cv2.flip(frame_data.image, 1)
        self._frame_height, self._frame_width = frame.shape[:2]

        result = self.gesture_detector.detect(frame)
        self._current_gesture = result.gesture
        self._gesture_confidence = result.confidence
        if result.bounding_box is not None:
            self._current_bbox = result.bounding_box
            self._last_bbox = result.bounding_box
        else:
            self._current_bbox = None

        self._update_state(result.gesture)

        # Convert to pixmap (displayed mirrored, same as detection)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._current_pixmap = QPixmap.fromImage(qimg)

        self.update()

    def _update_state(self, gesture: HandGesture) -> None:
        """State machine transitions based on detected gesture."""
        # Debounce: require the gesture to persist for N frames
        if gesture == self._last_gesture:
            self._gesture_hold_count += 1
        else:
            self._gesture_hold_count = 1
            self._last_gesture = gesture

        hold_confirmed = self._gesture_hold_count >= self.GESTURE_HOLD_FRAMES

        if self._state == PreKaraokeState.NO_HAND:
            if gesture != HandGesture.NONE:
                self._state = PreKaraokeState.HAND_SEEN
                logger.info("Hand detected")

        elif self._state == PreKaraokeState.HAND_SEEN:
            if gesture == HandGesture.NONE:
                # Lost the hand
                if hold_confirmed:
                    self._state = PreKaraokeState.NO_HAND
                    logger.info("Hand lost, back to NO_HAND")
            elif hold_confirmed and gesture == HandGesture.OPEN_PALM:
                self._state = PreKaraokeState.PALM_OPEN
                logger.info("Open palm confirmed")

        elif self._state == PreKaraokeState.PALM_OPEN:
            if gesture == HandGesture.CLOSED_FIST and hold_confirmed:
                self._state = PreKaraokeState.FIST_CLOSED
                logger.info("Fist confirmed, starting countdown")
                self._begin_countdown()
            elif gesture == HandGesture.NONE and hold_confirmed:
                # Hand dropped entirely — back to scanning
                self._state = PreKaraokeState.HAND_SEEN
                logger.info("Hand lost during palm, back to HAND_SEEN")

        elif self._state == PreKaraokeState.FIST_CLOSED:
            self._state = PreKaraokeState.COUNTDOWN

    # ───────────────── Countdown ─────────────────

    def _begin_countdown(self) -> None:
        """Manual or gesture trigger — go straight to countdown."""
        if self._emitted or self._countdown_timer.isActive():
            return
        self._start_btn.setEnabled(False)
        self._state = PreKaraokeState.COUNTDOWN
        self._countdown_value = self.COUNTDOWN_START
        self._countdown_timer.start()

    def _on_countdown_tick(self) -> None:
        self._countdown_value -= 1
        if self._countdown_value > 0:
            self.update()
            return

        self._countdown_timer.stop()
        self._state = PreKaraokeState.STARTING
        self.update()
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
