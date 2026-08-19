"""Recording data model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    folder:         Path
    audio_path:     Path
    video_path:     Optional[Path] = None  # None if no webcam frames

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

    def to_dict(self) -> dict:
        d = asdict(self)
        d['folder'] = str(self.folder)
        d['audio_path'] = str(self.audio_path)
        d['video_path'] = str(self.video_path) if self.video_path else None
        d['recorded_at'] = self.recorded_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        data['folder'] = Path(data['folder'])
        data['audio_path'] = Path(data['audio_path'])
        data['video_path'] = Path(data['video_path']) if data.get('video_path') else None
        data['recorded_at'] = datetime.fromisoformat(data['recorded_at'])
        return cls(**data)
