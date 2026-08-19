"""In-app recordings library view."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger
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

    def _play_recording(self, recording: Recording, version: str) -> None:
        """Play a specific version of the recording."""
        version_map = {
            "voice_raw":       recording.voice_raw_path,
            "voice_autotuned": recording.voice_autotuned_path,
            "mixed_raw":       recording.mixed_raw_path,
            "mixed_autotuned": recording.mixed_autotuned_path,
        }

        target = version_map.get(version)
        if not target or not target.exists():
            QMessageBox.warning(
                self, "Not Available",
                f"The '{version}' version doesn't exist for this recording.",
            )
            return

        try:
            subprocess.Popen(["xdg-open", str(target)])
            logger.info(f"Playing: {target.name}")
        except Exception as e:
            QMessageBox.warning(
                self, "Playback Failed",
                f"Could not open {target.name}: {e}",
            )

    def _export_recording(self, recording: Recording) -> None:
        """Choose which version to export."""
        # Build list of available versions
        options = []
        version_paths = {}

        if recording.has_mixed_raw:
            options.append("With music — Raw voice")
            version_paths["With music — Raw voice"] = recording.mixed_raw_path

        if recording.has_mixed_autotuned:
            options.append("With music — Auto-tuned ✨")
            version_paths["With music — Auto-tuned ✨"] = (
                recording.mixed_autotuned_path
            )

        if recording.has_voice_raw:
            options.append("Voice only — Raw")
            version_paths["Voice only — Raw"] = recording.voice_raw_path

        if recording.has_voice_autotuned:
            options.append("Voice only — Auto-tuned ✨")
            version_paths["Voice only — Auto-tuned ✨"] = (
                recording.voice_autotuned_path
            )

        if recording.video_raw_path and recording.video_raw_path.exists():
            options.append("Video — Raw")
            version_paths["Video — Raw"] = recording.video_raw_path

        if (
            recording.video_autotuned_path
            and recording.video_autotuned_path.exists()
        ):
            options.append("Video — Auto-tuned ✨")
            version_paths["Video — Auto-tuned ✨"] = (
                recording.video_autotuned_path
            )

        if not options:
            QMessageBox.warning(
                self, "Nothing to Export", "No versions available."
            )
            return

        from PyQt6.QtWidgets import QInputDialog

        # Default: mixed_autotuned if available, else mixed_raw
        default_idx = 0
        if "With music — Auto-tuned ✨" in options:
            default_idx = options.index("With music — Auto-tuned ✨")
        elif "With music — Raw voice" in options:
            default_idx = options.index("With music — Raw voice")

        choice, ok = QInputDialog.getItem(
            self,
            "Export Version",
            f"Which version to export?\n\n({recording.display_name})",
            options,
            default_idx,
            False,
        )
        if not ok:
            return

        source = version_paths[choice]
        suffix = source.suffix

        # Build filename
        safe_title = recording.song_title.replace("/", "_")
        safe_artist = recording.song_artist.replace("/", "_")
        version_tag = (
            choice.replace(" ", "_")
            .replace("—", "-")
            .replace("✨", "autotuned")
        )
        default_name = f"{safe_artist}_-_{safe_title}_{version_tag}{suffix}"

        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recording",
            str(Path.home() / default_name),
            f"Media files (*{suffix})",
        )

        if not target:
            return

        try:
            import shutil

            shutil.copy(source, target)
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
