"""
Wrenify — MP4 export pipeline.

Combines recorded webcam frames + processed audio into a final MP4
using moviepy + ffmpeg. Optionally overlays lyrics on top of video.

Full implementation lands in Phase 4 (after lyrics engine).
For now, this exports raw webcam + audio without overlays.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from wrenify.core.config import CONFIG, EXPORT_DIR
from wrenify.video.camera import Frame


class VideoExporter:
    """
    Renders a final MP4 from captured frames and processed audio.

    Basic flow:
    1. Take list of Frame objects (image + timestamp)
    2. Take a numpy array of processed audio
    3. Write frames to a temp video file (opencv)
    4. Merge video + audio into MP4 (moviepy)
    5. Optionally burn in lyrics (Phase 4)
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or EXPORT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        frames: list[Frame],
        audio: np.ndarray,
        sample_rate: int,
        output_name: str = "wrenify_export",
    ) -> Path:
        """
        Export video + audio to MP4.

        Args:
            frames: list of captured webcam frames
            audio: processed mono audio as float32 numpy array
            sample_rate: audio sample rate (Hz)
            output_name: filename without extension

        Returns:
            Path to the exported MP4 file
        """
        if not frames:
            raise ValueError("No frames to export")

        if len(audio) == 0:
            raise ValueError("No audio to export")

        output_path = self.output_dir / f"{output_name}.mp4"
        temp_video  = self.output_dir / f"{output_name}_temp.avi"
        temp_audio  = self.output_dir / f"{output_name}_temp.wav"

        logger.info(f"Exporting {len(frames)} frames + {len(audio)/sample_rate:.2f}s audio")

        # Step 1: Write frames to a temp video file
        self._write_video(frames, temp_video)

        # Step 2: Write audio to a temp wav file
        self._write_audio(audio, sample_rate, temp_audio)

        # Step 3: Merge into final MP4
        self._merge(temp_video, temp_audio, output_path)

        # Cleanup temp files
        temp_video.unlink(missing_ok=True)
        temp_audio.unlink(missing_ok=True)

        logger.success(f"Exported: {output_path}")
        return output_path

    def _write_video(self, frames: list[Frame], path: Path) -> None:
        """Write frames to temp AVI using OpenCV."""
        import cv2

        first = frames[0].image
        height, width = first.shape[:2]

        # Calculate actual fps from timestamps
        duration = frames[-1].timestamp - frames[0].timestamp
        actual_fps = len(frames) / duration if duration > 0 else CONFIG.video.fps

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(path), fourcc, actual_fps, (width, height))

        for frame in frames:
            writer.write(frame.image)

        writer.release()
        logger.info(f"Wrote temp video: {path.name} ({actual_fps:.2f} fps)")

    def _write_audio(self, audio: np.ndarray, sample_rate: int, path: Path) -> None:
        """Write audio to temp WAV."""
        import soundfile as sf

        sf.write(str(path), audio, sample_rate)
        logger.info(f"Wrote temp audio: {path.name}")

    def _merge(self, video_path: Path, audio_path: Path, output_path: Path) -> None:
        """Merge video + audio into MP4 using moviepy."""
        from moviepy.editor import AudioFileClip, VideoFileClip

        video = VideoFileClip(str(video_path))
        audio = AudioFileClip(str(audio_path))

        # Trim to shortest of the two
        final_duration = min(video.duration, audio.duration)
        video = video.subclip(0, final_duration)
        audio = audio.subclip(0, final_duration)

        final = video.set_audio(audio)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=video.fps,
            preset="fast",
            logger=None,  # Disable moviepy's noisy logs
        )

        video.close()
        audio.close()
        final.close()


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import time

    import sounddevice as sd
    from rich.console import Console

    from wrenify.video.camera import WebcamCapture

    console = Console()
    console.print("\n[bold cyan]Video Export Test — 5 second recording[/bold cyan]\n")
    console.print("[yellow]Recording webcam + mic for 5 seconds...[/yellow]\n")

    # Record webcam
    cam = WebcamCapture()
    cam.start()

    # Record audio
    duration = 5
    sr = CONFIG.audio.sample_rate
    audio = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")

    time.sleep(duration)
    sd.wait()

    cam.stop()

    frames = cam.drain_frames()
    audio_flat = audio.flatten()

    console.print(f"[green]Captured {len(frames)} frames[/green]")
    console.print(f"[green]Captured {len(audio_flat)} audio samples[/green]\n")

    # Export
    exporter = VideoExporter()
    output_path = exporter.export(frames, audio_flat, sr, "webcam_test")

    console.print(f"\n[green]Play with:[/green] mpv {output_path}")
