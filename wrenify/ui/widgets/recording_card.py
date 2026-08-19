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

    play_requested   = pyqtSignal(Recording)
    export_requested = pyqtSignal(Recording)
    delete_requested = pyqtSignal(Recording)

    def __init__(self, recording: Recording, parent: QWidget | None = None) -> None:
        super().__init__(parent, radius=16)
        self.recording = recording
        self.setFixedSize(260, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel(recording.song_title)
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 15px;
            font-weight: 600;
        """)
        title.setWordWrap(True)
        layout.addWidget(title)

        artist = QLabel(recording.song_artist)
        artist.setStyleSheet(f"""
            color: {THEME.colors.lime};
            font-size: 12px;
        """)
        layout.addWidget(artist)

        grade_row = QHBoxLayout()

        grade = QLabel(recording.grade)
        grade.setStyleSheet(f"""
            color: {self._grade_color(recording.grade)};
            font-size: 24px;
            font-weight: 700;
        """)
        grade_row.addWidget(grade)

        score = QLabel(f"{recording.score_pct:.0f}%")
        score.setStyleSheet(f"""
            color: {THEME.colors.text_secondary};
            font-size: 14px;
            font-weight: 500;
        """)
        grade_row.addWidget(score)
        grade_row.addStretch()
        layout.addLayout(grade_row)

        stats = QLabel(
            f"✓ {recording.correct_count}  "
            f"✗ {recording.wrong_count}  "
            f"— {recording.missed_count}"
        )
        stats.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 11px;
        """)
        layout.addWidget(stats)

        meta = QLabel(f"{recording.date_display} · {recording.duration_display}")
        meta.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 10px;
        """)
        layout.addWidget(meta)

        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.setSpacing(6)

        play_btn = self._mini_btn("▶ Play")
        play_btn.clicked.connect(lambda: self.play_requested.emit(recording))
        buttons.addWidget(play_btn)

        export_btn = self._mini_btn("⤓ Export")
        export_btn.clicked.connect(lambda: self.export_requested.emit(recording))
        buttons.addWidget(export_btn)

        del_btn = self._mini_btn("🗑", small=True)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(recording))
        buttons.addWidget(del_btn)

        layout.addLayout(buttons)

    def _mini_btn(self, text: str, small: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        if small:
            btn.setFixedWidth(32)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: white;
                font-size: 12px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(180, 255, 57, 0.15);
                border-color: rgba(180, 255, 57, 0.4);
            }
        """)
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
