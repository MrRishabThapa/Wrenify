"""Manages saved karaoke recordings."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from wrenify.core.config import ROOT_DIR
from wrenify.recordings.models import Recording

RECORDINGS_DIR = ROOT_DIR / "recordings"


class RecordingsManager:
    """
    Saves recordings to internal library organized by song + timestamp.

    Folder structure:
        recordings/
        └── ed-sheeran_perfect_2025-08-19_11-43-22/
            ├── voice_raw.wav        (mic only)
            ├── voice_autotuned.wav  (pitch-corrected mic, optional)
            ├── mixed_raw.wav        (mic + music, optional)
            ├── mixed_autotuned.wav  (autotuned mic + music, optional)
            ├── video_raw.mp4        (webcam + mixed audio, optional)
            ├── video_autotuned.mp4  (webcam + autotuned mix, optional)
            └── meta.json
    """

    def __init__(self, recordings_dir: Path = RECORDINGS_DIR) -> None:
        self.root = recordings_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        song_title: str,
        song_artist: str,
        sample_rate: int,
        voice_samples: np.ndarray,
        voice_autotuned: Optional[np.ndarray] = None,
        instrumental_samples: Optional[np.ndarray] = None,
        video_frames: Optional[list] = None,
        video_fps: float = 24.0,
    ) -> Recording:
        """
        Save a recording with all available audio versions.

        Args:
            voice_samples: Raw microphone audio
            voice_autotuned: Optional auto-tuned voice
            instrumental_samples: Optional matching instrumental slice
                          (enables mixed versions)
            video_frames: Optional webcam frames

        Returns:
            Recording object pointing to saved files
        """
        from wrenify.audio.mixer import AudioMixer

        now = datetime.utcnow()
        folder_name = self._make_folder_name(song_artist, song_title, now)
        folder = self.root / folder_name
        folder.mkdir(exist_ok=True)

        logger.info(f"Saving recording to: {folder}")

        mixer = AudioMixer()
        import soundfile as sf

        # ── 1. Voice only (raw) — always save ──
        voice_raw_path = folder / "voice_raw.wav"
        sf.write(str(voice_raw_path), voice_samples, sample_rate)
        logger.info("Saved: voice_raw.wav")

        # ── 2. Voice only (autotuned) — if provided ──
        voice_autotuned_path: Optional[Path] = None
        if voice_autotuned is not None:
            voice_autotuned_path = folder / "voice_autotuned.wav"
            sf.write(str(voice_autotuned_path), voice_autotuned, sample_rate)
            logger.info("Saved: voice_autotuned.wav")

        # ── 3. Mixed (voice + music, raw) — if instrumental provided ──
        mixed_raw_path: Optional[Path] = None
        if instrumental_samples is not None:
            mixed_raw = mixer.mix(voice_samples, instrumental_samples)
            mixed_raw_path = folder / "mixed_raw.wav"
            sf.write(str(mixed_raw_path), mixed_raw, sample_rate)
            logger.info("Saved: mixed_raw.wav")

        # ── 4. Mixed (autotuned voice + music) — if both provided ──
        mixed_autotuned_path: Optional[Path] = None
        if instrumental_samples is not None and voice_autotuned is not None:
            mixed_autotuned = mixer.mix(
                voice_autotuned, instrumental_samples
            )
            mixed_autotuned_path = folder / "mixed_autotuned.wav"
            sf.write(str(mixed_autotuned_path), mixed_autotuned, sample_rate)
            logger.info("Saved: mixed_autotuned.wav")

        # ── Video versions (if webcam captured) ──
        video_raw_path: Optional[Path] = None
        video_autotuned_path: Optional[Path] = None

        if video_frames:
            # Video with mixed_raw audio (or voice_raw as fallback)
            video_audio_source = (
                mixed_raw_path if mixed_raw_path else voice_raw_path
            )
            video_raw_path = folder / "video_raw.mp4"
            self._save_video_with_audio(
                video_frames, video_audio_source, video_raw_path, video_fps,
            )

            # Video with mixed_autotuned (or voice_autotuned) if available
            if mixed_autotuned_path or voice_autotuned_path:
                video_autotuned_source = (
                    mixed_autotuned_path or voice_autotuned_path
                )
                video_autotuned_path = folder / "video_autotuned.mp4"
                self._save_video_with_audio(
                    video_frames, video_autotuned_source,
                    video_autotuned_path, video_fps,
                )

        # Metadata
        duration = len(voice_samples) / sample_rate

        recording = Recording(
            id=folder_name,
            song_title=song_title,
            song_artist=song_artist,
            recorded_at=now,
            duration_sec=duration,
            folder=folder,
            voice_raw_path=voice_raw_path,
            voice_autotuned_path=voice_autotuned_path,
            mixed_raw_path=mixed_raw_path,
            mixed_autotuned_path=mixed_autotuned_path,
            video_raw_path=video_raw_path,
            video_autotuned_path=video_autotuned_path,
        )

        meta_path = folder / "meta.json"
        meta_path.write_text(json.dumps(recording.to_dict(), indent=2))

        logger.success(f"Recording saved: {recording.display_name}")
        return recording

    def _save_video_with_audio(
        self,
        frames: list,
        audio_path: Path,
        output_path: Path,
        fps: float = 24.0,
    ) -> None:
        """Save frames as video with audio, using ACTUAL frame timing."""
        import platform
        import subprocess

        import cv2

        if not frames:
            return

        # Calculate actual FPS from timestamps if available
        actual_fps = fps
        if hasattr(frames[0], 'timestamp') and len(frames) > 1:
            duration = frames[-1].timestamp - frames[0].timestamp
            if duration > 0:
                actual_fps = len(frames) / duration
                # Clamp to reasonable range
                actual_fps = max(10.0, min(actual_fps, 60.0))
                logger.info(
                    f"Calculated actual FPS: {actual_fps:.2f} "
                    f"from {len(frames)} frames over {duration:.2f}s"
                )

        first = frames[0].image if hasattr(frames[0], 'image') else frames[0]
        height, width = first.shape[:2]

        temp_video = Path(str(output_path).replace(".mp4", "_temp.mp4"))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(temp_video), fourcc, actual_fps, (width, height)
        )

        for frame in frames:
            img = frame.image if hasattr(frame, 'image') else frame
            writer.write(img)
        writer.release()

        # Mux with audio using ffmpeg
        # CRITICAL: use -async 1 or -vsync cfr to keep A/V in sync
        ffmpeg_kwargs: dict = {"capture_output": True, "check": True}
        if platform.system() == "Windows":
            ffmpeg_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(temp_video),
                    "-i", str(audio_path),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",           # End when shortest stream ends
                    "-vsync", "cfr",       # Constant frame rate
                    "-af", "aresample=async=1",  # Fix audio sync drift
                    str(output_path),
                ],
                **ffmpeg_kwargs,
            )
            logger.info(f"Saved synced video: {output_path.name} @ {actual_fps:.1f}fps")
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed: {e}")
            # Fallback: just copy temp video without fancy flags
            shutil.copy(temp_video, output_path)
        finally:
            if temp_video.exists():
                temp_video.unlink()

    def list_all(self) -> list[Recording]:
        """Load all recordings from disk, newest first."""
        recordings = []
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
            meta_path = folder / "meta.json"
            if not meta_path.exists():
                continue
            try:
                data = json.loads(meta_path.read_text())
                recordings.append(Recording.from_dict(data))
            except Exception as e:
                logger.warning(f"Could not load recording {folder.name}: {e}")

        recordings.sort(key=lambda r: r.recorded_at, reverse=True)
        return recordings

    def delete(self, recording: Recording) -> bool:
        """Delete a recording folder."""
        try:
            shutil.rmtree(recording.folder)
            logger.info(f"Deleted: {recording.id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def export_to(
        self, recording: Recording, destination: Path, version: str = "raw"
    ) -> Path:
        """Copy recording (video preferred) to external destination.

        Args:
            version: one of "voice_raw", "voice_autotuned",
                     "mixed_raw", "mixed_autotuned",
                     "video_raw", "video_autotuned"
        """
        destination = Path(destination)

        source = getattr(recording, f"{version}_path", None)
        if source is None:
            raise ValueError(f"Recording has no '{version}' version")

        # Preserve extension of source
        if destination.suffix == "":
            destination = destination.with_suffix(source.suffix)

        shutil.copy(source, destination)
        logger.success(f"Exported to: {destination}")
        return destination

    @staticmethod
    def _make_folder_name(artist: str, title: str, timestamp: datetime) -> str:
        def clean(s: str) -> str:
            return re.sub(r"[^\w]+", "-", s.lower()).strip("-")
        ts = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        return f"{clean(artist)}_{clean(title)}_{ts}"
