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
    folder:        Path

    # Voice-only versions
    voice_raw_path:       Optional[Path] = None
    voice_autotuned_path: Optional[Path] = None

    # Mixed versions (voice + music)
    mixed_raw_path:       Optional[Path] = None
    mixed_autotuned_path: Optional[Path] = None

    # Video versions
    video_raw_path:       Optional[Path] = None
    video_autotuned_path: Optional[Path] = None

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
    def has_voice_raw(self) -> bool:
        return self.voice_raw_path is not None and self.voice_raw_path.exists()

    @property
    def has_voice_autotuned(self) -> bool:
        return (
            self.voice_autotuned_path is not None
            and self.voice_autotuned_path.exists()
        )

    @property
    def has_mixed_raw(self) -> bool:
        return self.mixed_raw_path is not None and self.mixed_raw_path.exists()

    @property
    def has_mixed_autotuned(self) -> bool:
        return (
            self.mixed_autotuned_path is not None
            and self.mixed_autotuned_path.exists()
        )

    @property
    def has_video(self) -> bool:
        return (
            self.video_raw_path is not None and self.video_raw_path.exists()
        ) or (
            self.video_autotuned_path is not None
            and self.video_autotuned_path.exists()
        )

    def to_dict(self) -> dict:
        return {
            "id":                    self.id,
            "song_title":            self.song_title,
            "song_artist":           self.song_artist,
            "recorded_at":           self.recorded_at.isoformat(),
            "duration_sec":          self.duration_sec,
            "folder":                str(self.folder),
            "voice_raw_path":        str(self.voice_raw_path) if self.voice_raw_path else None,
            "voice_autotuned_path":  str(self.voice_autotuned_path) if self.voice_autotuned_path else None,
            "mixed_raw_path":        str(self.mixed_raw_path) if self.mixed_raw_path else None,
            "mixed_autotuned_path":  str(self.mixed_autotuned_path) if self.mixed_autotuned_path else None,
            "video_raw_path":        str(self.video_raw_path) if self.video_raw_path else None,
            "video_autotuned_path":  str(self.video_autotuned_path) if self.video_autotuned_path else None,
            "grade":                 self.grade,
            "score_pct":             self.score_pct,
            "correct_count":         self.correct_count,
            "wrong_count":           self.wrong_count,
            "missed_count":          self.missed_count,
            "total_words":           self.total_words,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        def _path(key: str, legacy_key: str = "") -> Optional[Path]:
            v = data.get(key)
            if not v and legacy_key:
                v = data.get(legacy_key)
            return Path(v) if v else None

        return cls(
            id=data["id"],
            song_title=data["song_title"],
            song_artist=data["song_artist"],
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
            duration_sec=data["duration_sec"],
            folder=Path(data["folder"]),
            voice_raw_path=_path("voice_raw_path", "audio_path"),
            voice_autotuned_path=_path("voice_autotuned_path", "autotuned_path"),
            mixed_raw_path=_path("mixed_raw_path"),
            mixed_autotuned_path=_path("mixed_autotuned_path"),
            video_raw_path=_path("video_raw_path", "video_path"),
            video_autotuned_path=_path("video_autotuned_path", "autotuned_video_path"),
            grade=data.get("grade", "F"),
            score_pct=data.get("score_pct", 0.0),
            correct_count=data.get("correct_count", 0),
            wrong_count=data.get("wrong_count", 0),
            missed_count=data.get("missed_count", 0),
            total_words=data.get("total_words", 0),
        )
