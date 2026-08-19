"""In-app song import view with live progress display."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from wrenify.songs.full_import import FullSongImporter
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard, PillButton
from wrenify.ui.widgets.log_panel import LogPanel


class ImportWorker(QObject):
    """Background worker for song import (avoids blocking UI)."""

    progress = pyqtSignal(str, float)  # message, percentage
    log_line = pyqtSignal(str, str)    # message, level
    finished = pyqtSignal(bool, str)   # success, message

    def __init__(
        self,
        audio_source: str,  # URL or file path
        title: str,
        artist: str,
        album: str,
    ) -> None:
        super().__init__()
        self.audio_source = audio_source
        self.title = title
        self.artist = artist
        self.album = album

    def run(self) -> None:
        """Execute import in background thread."""
        tmp_dir: Path | None = None
        try:
            # If URL, download first
            if self.audio_source.startswith(("http://", "https://")):
                self.log_line.emit("Detected YouTube URL", "INFO")
                self.log_line.emit(f"Downloading: {self.audio_source}", "INFO")
                self.progress.emit("Downloading from YouTube...", 5)

                from wrenify.songs.full_import import download_song_from_url

                tmp_dir = Path(tempfile.mkdtemp(prefix="wrenify_import_"))
                info = download_song_from_url(self.audio_source, tmp_dir)
                audio_path = Path(info["path"])
                self.log_line.emit(f"Downloaded to: {audio_path.name}", "SUCCESS")
                if not self.title.strip():
                    self.title = info["title"]
                if not self.artist.strip():
                    self.artist = info["artist"]
            else:
                audio_path = Path(self.audio_source)
                if not audio_path.exists():
                    self.finished.emit(False, f"File not found: {audio_path}")
                    return

            # Run full import
            importer = FullSongImporter()

            def on_progress(msg: str, pct: float) -> None:
                self.progress.emit(msg, pct)
                self.log_line.emit(msg, "INFO")

            song = importer.import_song(
                audio_path=audio_path,
                title=self.title,
                artist=self.artist,
                album=self.album or None,
                progress_callback=on_progress,
            )

            self.log_line.emit(f"Import complete: {song.display_name}", "SUCCESS")
            self.finished.emit(True, f"Imported: {song.display_name}")

        except Exception as e:
            self.log_line.emit(f"Import failed: {e}", "ERROR")
            self.finished.emit(False, str(e))
        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)


class ImportView(QWidget):
    """UI for importing songs via URL or file path."""

    back_requested = pyqtSignal()
    import_completed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: ImportWorker | None = None
        self._thread: QThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(24)

        header = QHBoxLayout()

        title = QLabel("Import Song")
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 28px;
            font-weight: 300;
        """)
        header.addWidget(title)
        header.addStretch()

        back_btn = PillButton("← Back", variant="ghost")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        layout.addLayout(header)

        form_card = GlassCard(radius=16)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(16)

        url_label = self._label("YouTube URL or file path")
        form_layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://youtube.com/watch?v=... or /path/to/song.mp3"
        )
        self.url_input.setMinimumHeight(44)
        form_layout.addWidget(self.url_input)

        row = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.addWidget(self._label("Song title"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("e.g., Perfect")
        self.title_input.setMinimumHeight(44)
        title_col.addWidget(self.title_input)
        row.addLayout(title_col)

        artist_col = QVBoxLayout()
        artist_col.addWidget(self._label("Artist"))
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("e.g., Ed Sheeran")
        self.artist_input.setMinimumHeight(44)
        artist_col.addWidget(self.artist_input)
        row.addLayout(artist_col)

        form_layout.addLayout(row)

        form_layout.addWidget(self._label("Album (optional)"))
        self.album_input = QLineEdit()
        self.album_input.setPlaceholderText("e.g., Divide")
        self.album_input.setMinimumHeight(44)
        form_layout.addWidget(self.album_input)

        self.import_btn = PillButton("Start Import", variant="accent")
        self.import_btn.setMinimumHeight(48)
        self.import_btn.clicked.connect(self._start_import)
        form_layout.addWidget(self.import_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                text-align: center;
                color: white;
                font-size: 12px;
                min-height: 24px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0 y1:0 x2:1 y2:0,
                    stop:0 {THEME.colors.violet},
                    stop:1 {THEME.colors.lime}
                );
                border-radius: 7px;
            }}
        """)
        form_layout.addWidget(self.progress_bar)

        layout.addWidget(form_card)

        log_label = self._label("Import Progress")
        log_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 11px;
            letter-spacing: 2px;
        """)
        layout.addWidget(log_label)

        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(240)
        layout.addWidget(self.log_panel, stretch=1)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {THEME.colors.text_secondary}; font-size: 12px;"
        )
        return label

    def _start_import(self) -> None:
        source = self.url_input.text().strip()
        title = self.title_input.text().strip()
        artist = self.artist_input.text().strip()
        album = self.album_input.text().strip()

        if not source or not title or not artist:
            self.log_panel.log(
                "Please fill in URL/path, title, and artist",
                "ERROR",
            )
            return

        self.import_btn.setEnabled(False)
        self.import_btn.setText("Importing...")
        self.log_panel.clear_log()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Starting...")
        self.log_panel.log(f"Starting import: {title} by {artist}", "INFO")

        self._thread = QThread()
        self._worker = ImportWorker(source, title, artist, album)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_line.connect(self.log_panel.log)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)

        self._thread.start()

    def _on_progress(self, message: str, percentage: float) -> None:
        self.progress_bar.setValue(int(percentage))
        self.progress_bar.setFormat(f"{message} ({int(percentage)}%)")

    def _on_finished(self, success: bool, message: str) -> None:
        self.import_btn.setEnabled(True)
        self.import_btn.setText("Start Import")

        if success:
            self.log_panel.log(message, "SUCCESS")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Done")
            self.import_completed.emit()
        else:
            self.log_panel.log(f"Failed: {message}", "ERROR")
            self.progress_bar.setFormat("Import failed")
