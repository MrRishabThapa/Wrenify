"""Song card widget for the library grid."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from wrenify.songs.song import Song
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard


class SongCard(GlassCard):
    """Clickable card representing one song in the library."""

    clicked = pyqtSignal(Song)

    def __init__(self, song: Song, parent=None) -> None:
        super().__init__(parent, radius=16)
        self.song = song
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(240, 160)
        self.setStyleSheet(f"""
            QFrame#GlassCard {{
                background: {THEME.colors.glass_md};
                border: 1px solid {THEME.colors.border_subtle};
                border-radius: 16px;
            }}
            QFrame#GlassCard:hover {{
                background: rgba(180, 255, 57, 0.06);
                border: 1px solid rgba(180, 255, 57, 0.30);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel(song.title)
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 16px;
            font-weight: 600;
        """)
        title.setWordWrap(True)
        layout.addWidget(title)

        artist = QLabel(song.artist)
        artist.setStyleSheet(f"""
            color: {THEME.colors.lime};
            font-size: 13px;
            font-weight: 400;
        """)
        layout.addWidget(artist)

        layout.addStretch()

        meta_parts = []
        if song.duration:
            m, s = divmod(int(song.duration), 60)
            meta_parts.append(f"{m}:{s:02d}")
        if song.key and song.scale:
            meta_parts.append(f"{song.key} {song.scale}")
        if song.bpm:
            meta_parts.append(f"{int(song.bpm)} BPM")

        meta = QLabel(" · ".join(meta_parts))
        meta.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 11px;
        """)
        layout.addWidget(meta)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.song)
        super().mousePressEvent(event)
