"""
Wrenify — Hand gesture recognition via MediaPipe Hands.

MediaPipe uses ML models trained specifically for hand tracking,
so it doesn't confuse faces or other skin-colored regions with hands.

Detects two gestures:
- OPEN_PALM: all four fingers extended
- CLOSED_FIST: all four fingers curled

Runs on CPU at ~30 fps on modest hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from loguru import logger


class HandGesture(Enum):
    NONE        = "none"
    OPEN_PALM   = "open_palm"
    CLOSED_FIST = "closed_fist"
    UNKNOWN     = "unknown"


@dataclass
class GestureResult:
    gesture:        HandGesture
    confidence:     float
    hand_landmarks: Optional[object] = None
    bounding_box:   Optional[tuple[int, int, int, int]] = None


class GestureDetector:
    """
    Real-time hand gesture detector using MediaPipe.

    Only detects actual hands (not faces, arms, or skin patches).
    Provides accurate bounding boxes centered on the hand.
    """

    MIN_DETECTION_CONFIDENCE: float = 0.6
    MIN_TRACKING_CONFIDENCE:  float = 0.5

    def __init__(self) -> None:
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=self.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=self.MIN_TRACKING_CONFIDENCE,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        logger.info("MediaPipe Hands initialized")

    def detect(self, frame_bgr: np.ndarray) -> GestureResult:
        """Detect a hand in the frame and classify its pose."""
        # MediaPipe needs RGB
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False

        results = self.hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return GestureResult(gesture=HandGesture.NONE, confidence=0.0)

        landmarks = results.multi_hand_landmarks[0]
        gesture, confidence = self._classify_gesture(landmarks)
        bbox = self._get_bounding_box(landmarks, frame_bgr.shape)

        return GestureResult(
            gesture=gesture,
            confidence=confidence,
            hand_landmarks=landmarks,
            bounding_box=bbox,
        )

    def _classify_gesture(self, landmarks) -> tuple[HandGesture, float]:
        """Classify hand pose based on finger extension.

        MediaPipe hand model has 21 landmarks:
            0: wrist
            4: thumb tip
            8: index finger tip     — compare with 6 (index PIP joint)
            12: middle finger tip   — compare with 10
            16: ring finger tip     — compare with 14
            20: pinky tip           — compare with 18

        A finger is "extended" if its tip is higher (smaller y) than
        its middle joint.
        """
        lm = landmarks.landmark

        # Check which fingers are extended
        index_ext  = lm[8].y  < lm[6].y  - 0.02
        middle_ext = lm[12].y < lm[10].y - 0.02
        ring_ext   = lm[16].y < lm[14].y - 0.02
        pinky_ext  = lm[20].y < lm[18].y - 0.02

        extended = sum([index_ext, middle_ext, ring_ext, pinky_ext])

        if extended >= 3:
            return HandGesture.OPEN_PALM, 0.9
        elif extended == 0:
            return HandGesture.CLOSED_FIST, 0.9
        else:
            return HandGesture.UNKNOWN, 0.5

    def _get_bounding_box(
        self,
        landmarks,
        frame_shape: tuple[int, ...],
    ) -> tuple[int, int, int, int]:
        """Get bounding box tight around the hand."""
        h, w = frame_shape[:2]
        xs = [lm.x * w for lm in landmarks.landmark]
        ys = [lm.y * h for lm in landmarks.landmark]

        x_min, x_max = int(min(xs)), int(max(xs))
        y_min, y_max = int(min(ys)), int(max(ys))

        # Add padding
        padding = 20
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(w, x_max + padding)
        y_max = min(h, y_max + padding)

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def close(self) -> None:
        self.hands.close()


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import time

    from rich.console import Console

    from wrenify.video.camera import WebcamCapture

    console = Console()
    console.print("\n[bold cyan]MediaPipe Hand Gesture Test[/bold cyan]")
    console.print(
        "[yellow]Show hand: open palm, fist. Press Q to quit[/yellow]\n"
    )

    detector = GestureDetector()

    with WebcamCapture() as cam:
        time.sleep(0.5)
        window = "Gesture Test"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)

        while True:
            frame_data = cam.get_latest_frame()
            if frame_data is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame_data.image.copy(), 1)
            result = detector.detect(frame)

            # Draw bounding box
            if result.bounding_box:
                x, y, w, h = result.bounding_box
                color = {
                    HandGesture.OPEN_PALM:   (57, 255, 20),
                    HandGesture.CLOSED_FIST: (57, 255, 180),
                    HandGesture.UNKNOWN:     (0, 165, 255),
                    HandGesture.NONE:        (128, 128, 128),
                }[result.gesture]
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)

            # Draw landmarks
            if result.hand_landmarks:
                detector.mp_drawing.draw_landmarks(
                    frame, result.hand_landmarks,
                    detector.mp_hands.HAND_CONNECTIONS,
                )

            # Label
            cv2.putText(
                frame,
                f"{result.gesture.value.upper()} {result.confidence:.0%}",
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255, 255, 255), 2,
            )

            cv2.imshow(window, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
        detector.close()