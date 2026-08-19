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
            ├── audio.wav
            ├── video.mp4          (optional)
            └── meta.json
    """

    def __init__(self, recordings_dir: Path = RECORDINGS_DIR) -> None:
        self.root = recordings_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        song_title: str,
        song_artist: str,
        audio_samples: np.ndarray,
        sample_rate: int,
        video_frames: Optional[list] = None,
        video_fps: float = 24.0,
        score_data: Optional[dict] = None,
    ) -> Recording:
        """
        Save a recording to the library.

        Returns Recording object pointing to saved files.
        """
        now = datetime.utcnow()
        folder_name = self._make_folder_name(song_artist, song_title, now)
        folder = self.root / folder_name
        folder.mkdir(exist_ok=True)

        logger.info(f"Saving recording to: {folder}")

        audio_path = folder / "audio.wav"
        import soundfile as sf
        sf.write(str(audio_path), audio_samples, sample_rate)
        logger.info(f"Saved audio: {audio_path.name}")

        video_path: Optional[Path] = None
        if video_frames:
            video_path = folder / "video.mp4"
            self._save_video(
                video_frames, audio_samples, sample_rate,
                video_path, video_fps,
            )
            logger.info(f"Saved video: {video_path.name}")

        duration = len(audio_samples) / sample_rate

        score = score_data or {}

        recording = Recording(
            id=folder_name,
            song_title=song_title,
            song_artist=song_artist,
            recorded_at=now,
            duration_sec=duration,
            folder=folder,
            audio_path=audio_path,
            video_path=video_path,
            grade=score.get("grade", "N/A"),
            score_pct=score.get("total_score", 0.0),
            correct_count=score.get("correct_count", 0),
            wrong_count=score.get("wrong_count", 0),
            missed_count=score.get("missed_count", 0),
            total_words=score.get("total_words", 0),
        )

        meta_path = folder / "meta.json"
        meta_path.write_text(json.dumps(recording.to_dict(), indent=2))

        logger.success(f"Recording saved: {recording.display_name}")
        return recording

    def _save_video(
        self,
        frames: list,
        audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        fps: float,
    ) -> None:
        """Save frames + audio as MP4 directly into the recording folder."""
        from wrenify.video.exporter import VideoExporter

        try:
            exporter = VideoExporter(output_dir=output_path.parent)
            exporter.export(
                frames=frames,
                audio=audio,
                sample_rate=sample_rate,
                output_name=output_path.stem,
            )
        except Exception as e:
            logger.error(f"Video export failed: {e}")
            raise

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

    def export_to(self, recording: Recording, destination: Path) -> Path:
        """Copy recording (video preferred) to external destination."""
        destination = Path(destination)

        source = recording.video_path if recording.has_video else recording.audio_path

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
