"""In-app recordings library view."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wrenify.recordings.manager import RecordingsManager
from wrenify.recordings.models import Recording
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.recording_card import RecordingCard


class RecordingsView(QWidget):
    """Grid of saved recordings with play/export/delete."""

    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = RecordingsManager()
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(24)

        header = QHBoxLayout()
        title = QLabel("My Recordings")
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 28px;
            font-weight: 300;
        """)
        header.addWidget(title)
        header.addStretch()
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

    def reload(self) -> None:
        """Rescan recordings folder and rebuild grid."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recordings = self.manager.list_all()
        self.count_label.setText(
            f"{len(recordings)} recording{'s' if len(recordings) != 1 else ''}"
        )

        if not recordings:
            empty = QLabel(
                "No recordings yet. Press ⏺ Record during karaoke to save one."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"""
                color: {THEME.colors.text_tertiary};
                font-size: 14px;
                padding: 48px;
            """)
            self.grid_layout.addWidget(empty, 0, 0)
            return

        for i, rec in enumerate(recordings):
            card = RecordingCard(rec)
            card.play_requested.connect(self._play_recording)
            card.export_requested.connect(self._export_recording)
            card.delete_requested.connect(self._delete_recording)
            row, col = divmod(i, 3)
            self.grid_layout.addWidget(card, row, col)

    def _play_recording(self, recording: Recording) -> None:
        """Open recording in system default player."""
        target = (
            recording.video_path
            if recording.has_video
            else recording.audio_path
        )

        try:
            subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:
            QMessageBox.warning(
                self, "Playback Failed",
                f"Could not open {target.name}: {e}",
            )

    def _export_recording(self, recording: Recording) -> None:
        """Export to a user-chosen destination via file dialog."""
        source = (
            recording.video_path
            if recording.has_video
            else recording.audio_path
        )
        suffix = source.suffix

        default_name = (
            f"{recording.song_artist} - {recording.song_title}{suffix}"
        )
        default_name = default_name.replace("/", "_")

        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recording",
            str(Path.home() / default_name),
            f"Media files (*{suffix})",
        )

        if not target:
            return

        try:
            self.manager.export_to(recording, Path(target))
            QMessageBox.information(self, "Exported", f"Saved to {target}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _delete_recording(self, recording: Recording) -> None:
        """Delete with confirmation."""
        reply = QMessageBox.question(
            self,
            "Delete Recording?",
            f"Delete '{recording.display_name}' from {recording.date_display}?"
            "\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.delete(recording):
                self.reload()
