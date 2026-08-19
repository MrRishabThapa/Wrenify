"""
Wrenify — Pre-karaoke ready screen with live gesture feedback.

Shows the selected song, a live webcam feed with a gesture bounding
box, and a headphone reminder. The user signals they are ready by
raising an open palm then closing it into a fist (best-effort OpenCV
skin detection) — or by clicking the Start button. A 3-2-1 countdown
follows, then ready_signal fires and the session begins.

Layout (vertical flow, nothing overlaps):
    title → headphone note → webcam → instruction pill →
    [I'm Ready] [Back] → mic visualizer bar (full width)

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
from PyQt6.QtCore import QPointF, QRect, QRectF, Qt, QThread, QTimer, pyqtSignal
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
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wrenify.audio.capture import AudioCapture
from wrenify.songs.song import Song
from wrenify.ui.voice_visualizer import VoiceVisualizer
from wrenify.ui.widgets.glass import PillButton
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


class WebcamPreview(QWidget):
    """
    Dedicated webcam display: fitted frame, gesture box, countdown.

    Painted here (not on the parent) so the surrounding layout stays
    clean and nothing overlaps the instruction pill or buttons.
    """

    # Box colors per state
    COLOR_HAND   = QColor(255, 59, 48)      # Red
    COLOR_PALM   = QColor(76, 217, 100)     # Green
    COLOR_FIST   = QColor(180, 255, 57)     # Bright lime

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_pixmap: Optional[QPixmap] = None
        self._frame_width: int = 0
        self._frame_height: int = 0
        self._current_bbox: Optional[tuple[int, int, int, int]] = None
        self._last_bbox: Optional[tuple[int, int, int, int]] = None
        self._state: PreKaraokeState = PreKaraokeState.NO_HAND
        self._countdown_value: int = 3

    # ───────────────── Public updates ─────────────────

    def update_frame(
        self,
        pixmap: QPixmap,
        frame_w: int,
        frame_h: int,
        bbox: Optional[tuple[int, int, int, int]],
        state: PreKaraokeState,
        countdown_value: int,
    ) -> None:
        """Refresh all visual state from the gesture pipeline."""
        self._current_pixmap = pixmap
        self._frame_width = frame_w
        self._frame_height = frame_h
        self._current_bbox = bbox
        self._state = state
        self._countdown_value = countdown_value
        self.update()

    # ───────────────── Painting ─────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._current_pixmap is None or self._current_pixmap.isNull():
            self._draw_no_webcam_placeholder(painter)
            return

        # Fit frame, centered, capped to the widget's height
        margin = 24
        max_h = self.height() - 2 * margin
        scaled = self._current_pixmap.scaled(
            self.width() - 2 * margin,
            max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        rect = QRect(x, y, scaled.width(), scaled.height())

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 20, 20)
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(x, y, scaled)
        painter.restore()

        painter.setPen(QPen(QColor(255, 255, 255, 42), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 20, 20)

        self._draw_gesture_box(painter, rect)
        self._draw_countdown(painter)

    def _draw_gesture_box(self, painter: QPainter, webcam_rect: QRect) -> None:
        """Draw a colored bounding box around the detected hand."""
        if self._frame_width == 0 or self._frame_height == 0:
            return

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

        x, y, w, h = bbox
        scale_x = webcam_rect.width() / self._frame_width
        scale_y = webcam_rect.height() / self._frame_height
        box_x = int(webcam_rect.x() + x * scale_x)
        box_y = int(webcam_rect.y() + y * scale_y)
        box_w = max(10, int(w * scale_x))
        box_h = max(10, int(h * scale_y))

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
            return

        if pulse:
            pulse_val = (math.sin(time.monotonic() * 4) + 1) / 2
            alpha = int(180 + 75 * pulse_val)
            color = QColor(color.red(), color.green(), color.blue(), alpha)
            thickness += int(2 * pulse_val)

        pen = QPen(color, thickness)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

        marker_len = 20
        marker_pen = QPen(color, thickness + 2)
        marker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(marker_pen)
        painter.drawLine(box_x, box_y, box_x + marker_len, box_y)
        painter.drawLine(box_x, box_y, box_x, box_y + marker_len)
        painter.drawLine(box_x + box_w - marker_len, box_y,
                         box_x + box_w, box_y)
        painter.drawLine(box_x + box_w, box_y,
                         box_x + box_w, box_y + marker_len)
        painter.drawLine(box_x, box_y + box_h, box_x + marker_len,
                         box_y + box_h)
        painter.drawLine(box_x, box_y + box_h - marker_len,
                         box_x, box_y + box_h)
        painter.drawLine(box_x + box_w - marker_len, box_y + box_h,
                         box_x + box_w, box_y + box_h)
        painter.drawLine(box_x + box_w, box_y + box_h - marker_len,
                         box_x + box_w, box_y + box_h)

    def _draw_countdown(self, painter: QPainter) -> None:
        """Big translucent countdown number over the webcam."""
        if self._state not in (PreKaraokeState.COUNTDOWN,
                               PreKaraokeState.STARTING):
            return

        text = str(self._countdown_value) if self._state == PreKaraokeState.COUNTDOWN else "GO!"
        font = QFont("Inter", 180, QFont.Weight.Thin)
        painter.setFont(font)
        painter.setPen(QPen(QColor(180, 255, 57, 55), 12))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.setPen(QColor(180, 255, 57, 230))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_no_webcam_placeholder(self, painter: QPainter) -> None:
        """Draw an informative placeholder when webcam is unavailable."""
        rect = QRect(24, 24, self.width() - 48, self.height() - 48)
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(rect, 20, 20)

        icon_x = rect.center().x() - 28
        icon_y = rect.y() + rect.height() // 2 - 64
        painter.setPen(QPen(QColor(180, 255, 57, 150), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(icon_x, icon_y + 8, 56, 38, 8, 8)
        painter.drawRoundedRect(icon_x + 11, icon_y, 20, 12, 4, 4)
        painter.drawEllipse(icon_x + 19, icon_y + 17, 18, 18)

        painter.setFont(QFont("Inter", 14))
        painter.setPen(QColor(200, 200, 220))
        painter.drawText(
            QRect(rect.x(), rect.y() + rect.height() // 2 + 20,
                  rect.width(), 40),
            Qt.AlignmentFlag.AlignCenter,
            "Webcam not available",
        )


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

    def __init__(self, song: Song, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.song = song

        # Safe defaults FIRST — before any code that may reference them
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
        self._gesture_hold_count: int = 0
        self._last_gesture = HandGesture.NONE
        self._countdown_value: int = self.COUNTDOWN_START
        self._emitted = False

        assert QThread.currentThread() == self.thread(), (
            "PreKaraokeView must be created on the main thread"
        )

        self._build_ui()

        # Timers BEFORE capture startup (startup code starts them)
        self._gesture_timer = QTimer(self)
        self._gesture_timer.setInterval(66)  # ~15fps
        self._gesture_timer.timeout.connect(self._on_gesture_frame)

        self._mic_timer = QTimer(self)
        self._mic_timer.setInterval(50)  # ~20fps
        self._mic_timer.timeout.connect(self._on_mic_level)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        # LAST: start captures (all attributes now exist)
        self._try_start_webcam()
        self._try_start_mic()

    # ───────────────── UI ─────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet("background: transparent; color: white;")

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 24, 48, 24)
        root.setSpacing(16)

        # 1. Top: title + headphone warning (ABOVE webcam, subtle)
        self._song_title_label = QLabel(self.song.display_name)
        self._song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._song_title_label.setStyleSheet(
            "color: rgba(180, 255, 57, 200); font-size: 20px; "
            "font-weight: 500;"
        )
        root.addWidget(self._song_title_label)

        headphone = QLabel("Headphones recommended — so the mic does not pick up the song")
        headphone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headphone.setStyleSheet(
            "color: rgba(255, 190, 110, 0.6); font-size: 11px;"
        )
        root.addWidget(headphone)

        # 2. Webcam preview (dedicated child widget, expands)
        self.preview = WebcamPreview()
        root.addWidget(self.preview, stretch=1)

        # 3. Instruction pill — dedicated row, never overlapped
        self.instruction_label = QLabel()
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setFixedHeight(48)
        self._update_instruction_style(PreKaraokeState.NO_HAND)
        root.addWidget(self.instruction_label)

        # 4. Buttons row (visible so gesture-free start is always possible)
        buttons_row = QHBoxLayout()
        buttons_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons_row.setSpacing(12)

        self._start_btn = PillButton("I'm Ready", variant="accent")
        self._start_btn.setMinimumWidth(140)
        self._start_btn.clicked.connect(self._begin_countdown)
        buttons_row.addWidget(self._start_btn)

        self._cancel_btn = PillButton("Back", variant="ghost")
        self._cancel_btn.setMinimumWidth(100)
        self._cancel_btn.clicked.connect(self._cancel)
        buttons_row.addWidget(self._cancel_btn)

        root.addLayout(buttons_row)

        # 5. Bottom: mic visualizer bar (full width, subtle)
        root.addWidget(self._build_viz_bar())

    def _build_viz_bar(self) -> QWidget:
        """Bottom full-width voice visualizer + status text."""
        container = QWidget()
        container.setFixedHeight(60)
        container.setStyleSheet("""
            background: rgba(255, 255, 255, 0.03);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(24, 8, 24, 8)

        mic_label = QLabel("MIC")
        mic_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 10px;"
            " letter-spacing: 2px;"
        )
        layout.addWidget(mic_label)

        self._viz = VoiceVisualizer()
        self._viz.setFixedWidth(200)
        layout.addWidget(self._viz)

        layout.addStretch()

        self._viz_status = QLabel("Ready · 44.1kHz · Whisper base")
        self._viz_status.setStyleSheet(
            "color: rgba(255,255,255,0.4); font-size: 11px;"
        )
        layout.addWidget(self._viz_status)

        return container

    def _update_instruction_style(self, state: PreKaraokeState) -> None:
        """Set instruction text + color for the current gesture state."""
        text_map = {
            PreKaraokeState.NO_HAND:     ("Raise your hand to begin", "rgba(255,255,255,0.6)"),
            PreKaraokeState.HAND_SEEN:   ("Show your open palm", "#FFB84D"),
            PreKaraokeState.PALM_OPEN:   ("Close your fist to start", "#4CD964"),
            PreKaraokeState.FIST_CLOSED: ("Get ready...", "#B4FF39"),
            PreKaraokeState.COUNTDOWN:   (str(self._countdown_value), "#B4FF39"),
            PreKaraokeState.STARTING:    ("GO!", "#B4FF39"),
        }
        text, color = text_map.get(state, ("", "#FFF"))
        self.instruction_label.setText(text)
        self.instruction_label.setStyleSheet(f"""
            color: {color};
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(180, 255, 57, 0.2);
            border-radius: 24px;
            padding: 8px 32px;
            font-size: 16px;
        """)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Ambient background only — content lives in layout children."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(10, 10, 21))
        for x, y, scale, color in (
            (.16, .18, .60, QColor(139, 92, 246, 40)),
            (.84, .82, .50, QColor(180, 255, 57, 28)),
        ):
            radius = int(min(self.width(), self.height()) * scale)
            gradient = QRadialGradient(
                QPointF(int(self.width() * x), int(self.height() * y)), radius
            )
            gradient.setColorAt(0, color)
            edge = QColor(color)
            edge.setAlpha(0)
            gradient.setColorAt(1, edge)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(
                int(self.width() * x) - radius,
                int(self.height() * y) - radius,
                radius * 2,
                radius * 2,
            )

    # ───────────────── Webcam ─────────────────

    def _try_start_webcam(self) -> None:
        try:
            self.webcam = WebcamCapture()
            self.webcam.start()
            gesture_timer = getattr(self, '_gesture_timer', None)
            if gesture_timer is not None:
                gesture_timer.start()
            logger.info("Pre-karaoke: webcam + gesture detection ready")
        except Exception as e:
            logger.warning(f"Webcam unavailable on ready screen: {e}")
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
        for timer_name in ('_gesture_timer', '_mic_timer', '_countdown_timer'):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                try:
                    timer.stop()
                except Exception as e:
                    logger.debug(f"Failed to stop {timer_name}: {e}")

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
            return

        frame_data = self.webcam.get_latest_frame()
        if frame_data is None:
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

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        self.preview.update_frame(
            pixmap,
            self._frame_width,
            self._frame_height,
            self._current_bbox,
            self._state,
            self._countdown_value,
        )

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
                self._state = PreKaraokeState.HAND_SEEN
                logger.info("Hand lost during palm, back to HAND_SEEN")

        elif self._state == PreKaraokeState.FIST_CLOSED:
            self._state = PreKaraokeState.COUNTDOWN

        self._update_instruction_style(self._state)

    # ───────────────── Countdown ─────────────────

    def _begin_countdown(self) -> None:
        """Manual or gesture trigger — go straight to countdown."""
        if self._emitted or self._countdown_timer.isActive():
            return
        self._start_btn.setEnabled(False)
        self._state = PreKaraokeState.COUNTDOWN
        self._countdown_value = self.COUNTDOWN_START
        self._update_instruction_style(self._state)
        self._countdown_timer.start()

    def _on_countdown_tick(self) -> None:
        self._countdown_value -= 1
        if self._countdown_value > 0:
            self._update_instruction_style(self._state)
            return

        self._countdown_timer.stop()
        self._state = PreKaraokeState.STARTING
        self._update_instruction_style(self._state)
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
