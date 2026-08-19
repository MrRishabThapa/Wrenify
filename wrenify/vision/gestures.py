"""
Wrenify — Vision: hand gesture detection via skin-color analysis.

Lightweight CPU-only detector (no MediaPipe) that segments skin-tone
blobs and classifies the largest one's pose:

    OPEN_PALM — large skin area (hand open)
    HAND      — skin present but pose ambiguous (e.g. fist, partial)
    NONE      — no significant skin blob

Each detection returns a bounding box (x, y, w, h) in frame pixel
coordinates so the UI can draw visual feedback over the webcam feed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2
import numpy as np


class HandGesture(Enum):
    """Pose classification of the largest skin blob."""

    NONE      = "none"        # No significant skin visible
    HAND      = "hand"        # Skin present, pose not identified
    OPEN_PALM = "open_palm"   # Open palm confirmed


@dataclass
class GestureResult:
    """Result of a single gesture detection."""

    gesture:      HandGesture
    confidence:   float = 0.0
    bounding_box: Optional[tuple[int, int, int, int]] = None  # x, y, w, h
    skin_ratio:   float = 0.0                                 # 0.0 to 1.0


class GestureDetector:
    """
    Detects hand gestures from a BGR frame using an HSV skin mask.

    The largest skin-colored contour provides the bounding box;
    the fraction of skin pixels in the frame classifies the pose.
    """

    # HSV skin range
    SKIN_LOWER = np.array([0, 40, 40])
    SKIN_UPPER = np.array([25, 255, 255])

    PALM_RATIO:  float = 0.12   # >= this => open palm
    MIN_BLOB_AREA: int = 250    # px; smaller blobs are noise

    def __init__(self) -> None:
        self._kernel_open = np.ones((5, 5), np.uint8)
        self._kernel_close = np.ones((15, 15), np.uint8)

    def detect(self, frame_bgr: np.ndarray) -> GestureResult:
        """
        Classify the largest skin blob in the frame.

        Args:
            frame_bgr: BGR image, e.g. (480, 640, 3)

        Returns:
            GestureResult with gesture, confidence, bounding box
            (None when nothing significant is detected), and skin ratio.
        """
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.SKIN_LOWER, self.SKIN_UPPER)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel_open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel_close)

        skin_ratio = float(np.count_nonzero(mask)) / float(mask.size)

        bbox: Optional[tuple[int, int, int, int]] = None
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) >= self.MIN_BLOB_AREA:
                x, y, w, h = cv2.boundingRect(largest)
                bbox = (int(x), int(y), int(w), int(h))

        if bbox is None:
            return GestureResult(
                gesture=HandGesture.NONE,
                confidence=0.0,
                bounding_box=None,
                skin_ratio=skin_ratio,
            )

        if skin_ratio >= self.PALM_RATIO:
            return GestureResult(
                gesture=HandGesture.OPEN_PALM,
                confidence=min(1.0, skin_ratio * 3.0),
                bounding_box=bbox,
                skin_ratio=skin_ratio,
            )

        return GestureResult(
            gesture=HandGesture.HAND,
            confidence=min(1.0, skin_ratio * 6.0),
            bounding_box=bbox,
            skin_ratio=skin_ratio,
        )

    def close(self) -> None:
        """Release any resources (no-op for the skin-color detector)."""
        pass
