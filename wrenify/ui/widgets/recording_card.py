"""Recording card widget for the recordings grid."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.recordings.models import Recording
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard


class RecordingCard(GlassCard):
    """Card displaying a saved recording with play/export/delete actions."""

    play_requested   = pyqtSignal(Recording, str)  # recording, version_name
    export_requested = pyqtSignal(Recording)
    delete_requested = pyqtSignal(Recording)

    def __init__(self, recording: Recording, parent: QWidget | None = None) -> None:
        super().__init__(parent, radius=16)
        self.recording = recording
        self.setFixedSize(280, 280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        # Title
        title = QLabel(recording.song_title)
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 15px;
            font-weight: 600;
        """)
        title.setWordWrap(True)
        layout.addWidget(title)

        # Artist
        artist = QLabel(recording.song_artist)
        artist.setStyleSheet(f"""
            color: {THEME.colors.lime};
            font-size: 12px;
        """)
        layout.addWidget(artist)

        # Grade + score
        grade_row = QHBoxLayout()

        grade = QLabel(recording.grade)
        grade.setStyleSheet(f"""
            color: {self._grade_color(recording.grade)};
            font-size: 22px;
            font-weight: 700;
        """)
        grade_row.addWidget(grade)

        score = QLabel(f"{recording.score_pct:.0f}%")
        score.setStyleSheet(f"""
            color: {THEME.colors.text_secondary};
            font-size: 13px;
            font-weight: 500;
        """)
        grade_row.addWidget(score)
        grade_row.addStretch()
        layout.addLayout(grade_row)

        # Stats
        stats = QLabel(
            f"✓ {recording.correct_count}  "
            f"✗ {recording.wrong_count}  "
            f"— {recording.missed_count}"
        )
        stats.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 10px;
        """)
        layout.addWidget(stats)

        # Date + duration
        meta = QLabel(f"{recording.date_display} · {recording.duration_display}")
        meta.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 10px;
        """)
        layout.addWidget(meta)

        layout.addStretch()

        # Playback buttons — row 1: MIXED (with music)
        music_label = QLabel("WITH MUSIC")
        music_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 9px;
            letter-spacing: 1.5px;
            margin-top: 4px;
        """)
        layout.addWidget(music_label)

        mixed_row = QHBoxLayout()
        mixed_row.setSpacing(6)

        if recording.has_mixed_raw:
            raw_music_btn = self._mini_btn("▶ Raw")
            raw_music_btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "mixed_raw")
            )
            mixed_row.addWidget(raw_music_btn)

        if recording.has_mixed_autotuned:
            autotune_music_btn = self._mini_btn("✨ Auto-Tune", accent=True)
            autotune_music_btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "mixed_autotuned")
            )
            mixed_row.addWidget(autotune_music_btn)

        if not recording.has_mixed_raw and not recording.has_mixed_autotuned:
            no_mix = self._mini_btn("Not available")
            no_mix.setEnabled(False)
            mixed_row.addWidget(no_mix)

        layout.addLayout(mixed_row)

        # Playback buttons — row 2: VOICE ONLY
        voice_label = QLabel("VOICE ONLY")
        voice_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 9px;
            letter-spacing: 1.5px;
            margin-top: 4px;
        """)
        layout.addWidget(voice_label)

        voice_row = QHBoxLayout()
        voice_row.setSpacing(6)

        if recording.has_voice_raw:
            raw_voice_btn = self._mini_btn("▶ Raw")
            raw_voice_btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "voice_raw")
            )
            voice_row.addWidget(raw_voice_btn)

        if recording.has_voice_autotuned:
            autotune_voice_btn = self._mini_btn("✨ Auto-Tune", accent=True)
            autotune_voice_btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "voice_autotuned")
            )
            voice_row.addWidget(autotune_voice_btn)

        layout.addLayout(voice_row)

        # Actions — row 3
        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        export_btn = self._mini_btn("⤓ Export")
        export_btn.clicked.connect(
            lambda: self.export_requested.emit(recording)
        )
        actions_row.addWidget(export_btn)

        del_btn = self._mini_btn("🗑", small=True)
        del_btn.clicked.connect(
            lambda: self.delete_requested.emit(recording)
        )
        actions_row.addWidget(del_btn)

        layout.addLayout(actions_row)

    def _mini_btn(
        self, text: str, small: bool = False, accent: bool = False
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        if small:
            btn.setFixedWidth(32)

        if accent:
            style = """
                QPushButton {
                    background: rgba(180, 255, 57, 0.15);
                    border: 1px solid rgba(180, 255, 57, 0.4);
                    border-radius: 8px;
                    color: #B4FF39;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.25);
                    border-color: rgba(180, 255, 57, 0.6);
                }
            """
        else:
            style = """
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    color: white;
                    font-size: 11px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.15);
                    border-color: rgba(180, 255, 57, 0.4);
                }
                QPushButton:disabled {
                    color: rgba(255, 255, 255, 0.3);
                    background: rgba(255, 255, 255, 0.02);
                }
            """

        btn.setStyleSheet(style)
        return btn

    @staticmethod
    def _grade_color(grade: str) -> str:
        colors = {
            "A": "#B4FF39",
            "B": "#4CD964",
            "C": "#FFB84D",
            "D": "#FF9500",
            "F": "#FF453A",
        }
        return colors.get(grade[0] if grade else "F", "#FF453A")
