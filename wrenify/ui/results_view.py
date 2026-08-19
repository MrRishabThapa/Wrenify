"""Simple post-karaoke screen — no judging, just next actions."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wrenify.songs.song import Song
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import PillButton


class SessionEndView(QWidget):
    """Simple 'session complete' screen with next actions."""

    sing_again_requested = pyqtSignal()
    library_requested    = pyqtSignal()
    recordings_requested = pyqtSignal()

    def __init__(
        self,
        song: Song,
        recording_saved: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {THEME.colors.bg_deep};")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        # Icon / celebration
        celebration = QLabel("🎵")
        celebration.setStyleSheet("font-size: 96px;")
        celebration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(celebration)

        # Message
        title = QLabel("Great session!")
        title.setFont(QFont("Inter", 36, QFont.Weight.Light))
        title.setStyleSheet(f"color: {THEME.colors.text_primary};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Song info
        song_label = QLabel(f"{song.artist} — {song.title}")
        song_label.setFont(QFont("Inter", 18, QFont.Weight.Medium))
        song_label.setStyleSheet(f"color: {THEME.colors.lime};")
        song_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(song_label)

        # Recording indicator
        if recording_saved:
            saved = QLabel("✓ Recording saved to library")
            saved.setStyleSheet(f"""
                color: {THEME.colors.text_secondary};
                font-size: 14px;
                padding-top: 16px;
            """)
            saved.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(saved)

        layout.addSpacing(32)

        # Action buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.setAlignment(Qt.AlignmentFlag.AlignCenter)

        again_btn = PillButton("Sing Again", variant="accent")
        again_btn.setMinimumWidth(160)
        again_btn.clicked.connect(self.sing_again_requested.emit)
        buttons.addWidget(again_btn)

        if recording_saved:
            recordings_btn = PillButton("View Recording", variant="primary")
            recordings_btn.setMinimumWidth(160)
            recordings_btn.clicked.connect(self.recordings_requested.emit)
            buttons.addWidget(recordings_btn)

        library_btn = PillButton("Back to Library", variant="ghost")
        library_btn.setMinimumWidth(160)
        library_btn.clicked.connect(self.library_requested.emit)
        buttons.addWidget(library_btn)

        layout.addLayout(buttons)
