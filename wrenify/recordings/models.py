"""Recording data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Recording:
    """A saved karaoke session recording."""

    id:            str          # e.g., "perfect_2025-08-19_11-43-22"
    song_title:    str
    song_artist:   str
    recorded_at:   datetime
    duration_sec:  float

    # Files
    folder:              Path
    audio_path:          Path
    autotuned_path:      Optional[Path] = None  # Pitch-corrected audio
    video_path:          Optional[Path] = None  # None if no webcam frames
    autotuned_video_path: Optional[Path] = None  # Webcam + autotuned audio

    # Score data
    grade:         str = "F"
    score_pct:     float = 0.0
    correct_count: int = 0
    wrong_count:   int = 0
    missed_count:  int = 0
    total_words:   int = 0

    @property
    def display_name(self) -> str:
        return f"{self.song_artist} - {self.song_title}"

    @property
    def date_display(self) -> str:
        return self.recorded_at.strftime("%b %d, %Y · %I:%M %p")

    @property
    def duration_display(self) -> str:
        m, s = divmod(int(self.duration_sec), 60)
        return f"{m}:{s:02d}"

    @property
    def has_video(self) -> bool:
        return self.video_path is not None and self.video_path.exists()

    @property
    def has_autotuned(self) -> bool:
        return self.autotuned_path is not None and self.autotuned_path.exists()

    @property
    def has_autotuned_video(self) -> bool:
        return (
            self.autotuned_video_path is not None
            and self.autotuned_video_path.exists()
        )

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "song_title":          self.song_title,
            "song_artist":         self.song_artist,
            "recorded_at":         self.recorded_at.isoformat(),
            "duration_sec":        self.duration_sec,
            "folder":              str(self.folder),
            "audio_path":          str(self.audio_path),
            "autotuned_path":      str(self.autotuned_path) if self.autotuned_path else None,
            "video_path":          str(self.video_path) if self.video_path else None,
            "autotuned_video_path": str(self.autotuned_video_path) if self.autotuned_video_path else None,
            "grade":               self.grade,
            "score_pct":           self.score_pct,
            "correct_count":       self.correct_count,
            "wrong_count":         self.wrong_count,
            "missed_count":        self.missed_count,
            "total_words":         self.total_words,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        return cls(
            id=data["id"],
            song_title=data["song_title"],
            song_artist=data["song_artist"],
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
            duration_sec=data["duration_sec"],
            folder=Path(data["folder"]),
            audio_path=Path(data["audio_path"]),
            autotuned_path=(
                Path(data["autotuned_path"])
                if data.get("autotuned_path")
                else None
            ),
            video_path=(
                Path(data["video_path"]) if data.get("video_path") else None
            ),
            autotuned_video_path=(
                Path(data["autotuned_video_path"])
                if data.get("autotuned_video_path")
                else None
            ),
            grade=data.get("grade", "F"),
            score_pct=data.get("score_pct", 0.0),
            correct_count=data.get("correct_count", 0),
            wrong_count=data.get("wrong_count", 0),
            missed_count=data.get("missed_count", 0),
            total_words=data.get("total_words", 0),
        )
