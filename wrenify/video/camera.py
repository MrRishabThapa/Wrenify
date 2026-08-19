"""
Wrenify — Real-time webcam capture using OpenCV.

Captures frames from the system webcam into a thread-safe deque.
The main app pulls frames when it needs them (for preview or export).

Key design:
- Frames run in a background thread (like AudioCapture)
- We keep only the last N frames in memory (deque with maxlen)
- Both raw frames AND timestamps are stored (for A/V sync during export)
"""

from __future__ import annotations

import os
import platform
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from wrenify.core.config import CONFIG


@dataclass
class Frame:
    """A single webcam frame with its capture timestamp."""

    image: np.ndarray       # BGR image, shape (H, W, 3)
    timestamp: float        # Seconds since capture start (monotonic)


class WebcamCapture:
    """
    Captures webcam frames in a background thread.

    Frames are stored in a thread-safe deque with a max length so
    memory does not grow forever. The main thread pulls frames
    on demand via get_latest_frame() or drain_frames().

    Usage:
        with WebcamCapture() as cam:
            while running:
                frame = cam.get_latest_frame()
                if frame is not None:
                    cv2.imshow("Preview", frame.image)
    """

    def __init__(self, max_buffer_frames: int = 300) -> None:
        """
        Args:
            max_buffer_frames: Max frames in memory. Default 300 =
                               ~12 seconds at 24fps. Tuned for 8GB RAM.
                               Bump to 900+ on 16GB systems.
        """
        self.cfg = CONFIG.video
        self.frames: deque[Frame] = deque(maxlen=max_buffer_frames)
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    def _check_linux_video_devices(self) -> None:
        """Diagnostics for Linux /dev/video* devices (Linux only)."""
        # Diagnostic: check /dev/video devices exist
        video_devices = sorted(Path("/dev").glob("video*"))
        if not video_devices:
            logger.error(
                "No /dev/video* devices found. "
                "Check: is a webcam plugged in? Is the kernel driver loaded?"
            )
            raise RuntimeError("No video devices in /dev/")

        logger.info(f"Available video devices: {[str(d) for d in video_devices]}")

        # Diagnostic: check permissions
        device_path = f"/dev/video{self.cfg.webcam_index}"
        if os.path.exists(device_path):
            readable = os.access(device_path, os.R_OK)
            writable = os.access(device_path, os.W_OK)
            logger.info(
                f"{device_path} permissions: read={readable} write={writable}"
            )
            if not readable:
                logger.error(
                    f"Cannot read {device_path}. "
                    f"Fix: sudo usermod -aG video $USER && logout"
                )

        # Diagnostic: check if device is busy
        try:
            import subprocess
            result = subprocess.run(
                ["fuser", device_path],
                capture_output=True, text=True, timeout=1,
            )
            if result.stdout.strip():
                logger.warning(
                    f"{device_path} is being used by PID: {result.stdout.strip()}. "
                    f"Close other webcam apps (Zoom, Discord, browser tabs)."
                )
        except Exception:
            pass  # fuser not available or timed out

    def _open_camera(self) -> cv2.VideoCapture:
        """Open the webcam with detailed diagnostics on failure."""
        logger.info(f"Opening webcam at index {self.cfg.webcam_index}")

        # Platform-specific pre-checks
        system = platform.system()
        if system == "Linux":
            self._check_linux_video_devices()

        # Default backend (works on all platforms)
        cap = cv2.VideoCapture(self.cfg.webcam_index)

        # Fallback backends only if default fails
        if not cap.isOpened():
            if system == "Linux":
                logger.warning("Default backend failed, trying V4L2")
                cap = cv2.VideoCapture(self.cfg.webcam_index, cv2.CAP_V4L2)
            elif system == "Windows":
                logger.warning("Default backend failed, trying DirectShow")
                cap = cv2.VideoCapture(self.cfg.webcam_index, cv2.CAP_DSHOW)

        if not cap.isOpened():
            logger.error(
                f"Cannot open webcam at index {self.cfg.webcam_index}. "
                f"Try: cheese  OR  ffplay /dev/video0  to test outside Wrenify."
            )
            raise RuntimeError(f"cv2.VideoCapture({self.cfg.webcam_index}) failed")

        # Configure resolution + fps
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        cap.set(cv2.CAP_PROP_FPS,          self.cfg.fps)

        # Verify actual config
        actual_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = float(cap.get(cv2.CAP_PROP_FPS))

        # CRITICAL: test that we can actually READ a frame
        ret, test_frame = cap.read()
        if not ret or test_frame is None:
            logger.error(
                "Webcam opened but cannot read frames. "
                "This can happen when another app owns exclusive access."
            )
            cap.release()
            raise RuntimeError("Webcam read test failed")

        logger.success(
            f"Webcam ready | index={self.cfg.webcam_index} "
            f"resolution={actual_w}x{actual_h} fps={actual_fps:.1f} "
            f"test_frame_shape={test_frame.shape}"
        )
        return cap

    def _capture_loop(self) -> None:
        """Background thread: continuously read frames from webcam."""
        assert self._cap is not None
        frame_interval = 1.0 / self.cfg.fps

        while self._running:
            loop_start = time.monotonic()

            ret, image = self._cap.read()
            if not ret:
                logger.warning("Webcam read failed, retrying...")
                time.sleep(0.05)
                continue

            timestamp = time.monotonic() - self._start_time
            frame = Frame(image=image, timestamp=timestamp)

            with self._lock:
                self.frames.append(frame)

            # Sleep to hit target fps (best effort)
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, frame_interval - elapsed)
            time.sleep(sleep_time)

    def start(self) -> None:
        """Open the webcam and start the capture thread."""
        if self._running:
            logger.warning("Webcam already running")
            return

        self._cap = self._open_camera()
        self._running = True
        self._start_time = time.monotonic()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="webcam-capture",
            daemon=True,
        )
        self._thread.start()
        logger.info("Webcam capture thread started")

    def stop(self) -> None:
        """Stop capture and release the webcam."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("Webcam capture stopped")

    def get_latest_frame(self) -> Optional[Frame]:
        """Get the most recent frame (non-blocking)."""
        with self._lock:
            if not self.frames:
                return None
            return self.frames[-1]

    def drain_frames(self) -> list[Frame]:
        """Get ALL buffered frames and clear the buffer (for export)."""
        with self._lock:
            frames = list(self.frames)
            self.frames.clear()
            return frames

    def frame_count(self) -> int:
        """Number of frames currently in buffer."""
        with self._lock:
            return len(self.frames)

    @staticmethod
    def list_cameras(max_check: int = 5) -> list[int]:
        """Probe device indices 0..max_check-1 and return available ones."""
        available: list[int] = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def __enter__(self) -> "WebcamCapture":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


# ────────────────────── Standalone test ──────────────────────

def _check_display_env() -> None:
    """Make OpenCV windows work under Wayland and silence Qt warnings."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        # cv2's bundled Qt ships an xcb plugin but no wayland plugin;
        # force xcb so preview windows render through XWayland.
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        logger.info(
            "Wayland session detected: forcing QT_QPA_PLATFORM=xcb "
            "(preview runs through XWayland)"
        )
    # kvantum/qt5ct style overrides are not available inside cv2's Qt build
    os.environ.pop("QT_STYLE_OVERRIDE", None)


if __name__ == "__main__":
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]Webcam Capture Test[/bold cyan]\n")

    _check_display_env()

    # Show available cameras
    console.print("[dim]Scanning for cameras...[/dim]")
    cameras = WebcamCapture.list_cameras()
    if not cameras:
        console.print("[red]No webcams found![/red]")
        console.print("[dim]Check that /dev/video0 exists and you have permission.[/dim]")
        exit(1)

    console.print(f"[green]Found cameras at indices:[/green] {cameras}\n")
    console.print("[yellow]Opening live preview. Press [bold]q[/bold] to quit.[/yellow]\n")

    try:
        with WebcamCapture() as cam:
            # Wait a moment for the first frame
            time.sleep(0.5)

            window_name = "Wrenify Webcam Preview (press q to quit)"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        fps_display_time = time.monotonic()
        fps_count = 0
        current_fps = 0.0

        while True:
            frame = cam.get_latest_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            display = frame.image.copy()

            # Overlay FPS and frame count
            fps_count += 1
            now = time.monotonic()
            if now - fps_display_time >= 1.0:
                current_fps = fps_count / (now - fps_display_time)
                fps_count = 0
                fps_display_time = now

            cv2.putText(
                display,
                f"WRENIFY | FPS: {current_fps:.1f} | Buffer: {cam.frame_count()}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (180, 92, 246),  # Violet (BGR)
                2,
            )
            cv2.putText(
                display,
                f"t = {frame.timestamp:.2f}s",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (57, 255, 20),  # Lime (BGR)
                1,
            )

            cv2.imshow(window_name, display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            cv2.destroyAllWindows()

        console.print(f"\n[green]Captured {cam.frame_count()} frames in buffer at exit[/green]")
    except KeyboardInterrupt:
        console.print("\n[dim]Preview interrupted[/dim]")
        cv2.destroyAllWindows()
        exit(0)
