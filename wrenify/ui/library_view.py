"""In-app song library view."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.config import ROOT_DIR
from wrenify.songs.song import Song
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import PillButton
from wrenify.ui.widgets.song_card import SongCard

SONGS_DIR = ROOT_DIR / "songs"


class LibraryView(QWidget):
    """Grid of song cards. Click card to launch karaoke."""

    song_selected = pyqtSignal(Song)
    import_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.reload_songs()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(24)

        header = QHBoxLayout()

        title = QLabel("Your Library")
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 28px;
            font-weight: 300;
            letter-spacing: -0.5px;
        """)
        header.addWidget(title)

        header.addStretch()

        import_btn = PillButton("+ Import Song", variant="accent")
        import_btn.clicked.connect(self.import_requested.emit)
        header.addWidget(import_btn)

        layout.addLayout(header)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 13px;
        """)
        layout.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, stretch=1)

    def reload_songs(self) -> None:
        """Rescan songs/ folder and rebuild grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        songs = self._scan_songs()

        self.count_label.setText(
            f"{len(songs)} song{'s' if len(songs) != 1 else ''} imported"
        )

        if not songs:
            empty = QLabel(
                "No songs yet. Click '+ Import Song' to add your first."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"""
                color: {THEME.colors.text_tertiary};
                font-size: 14px;
                padding: 48px;
            """)
            self.grid_layout.addWidget(empty, 0, 0)
            return

        for i, song in enumerate(songs):
            card = SongCard(song)
            card.clicked.connect(self.song_selected.emit)
            row, col = divmod(i, 4)
            self.grid_layout.addWidget(card, row, col)

    def _scan_songs(self) -> list[Song]:
        """Load all valid songs from songs/ folder."""
        songs = []
        if not SONGS_DIR.exists():
            return songs

        for folder in sorted(SONGS_DIR.iterdir()):
            if not folder.is_dir():
                continue
            try:
                songs.append(Song.from_folder(folder))
            except Exception:
                continue  # Skip invalid folders

        return songs
