"""Custom styled export dialog with organized version matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.recordings.models import Recording
from wrenify.ui.theme import THEME


class ExportDialog(QDialog):
    """
    Custom export dialog showing all versions organized by:
      - Media type (Audio / Video)
      - Music (With music / Voice only)
      - Voice (Raw / Auto-tuned)
    """

    def __init__(
        self, recording: Recording, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.recording = recording
        self.selected_version: Optional[str] = None
        self.selected_path: Optional[Path] = None

        self.setWindowTitle("Export Recording")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # CRITICAL: Use standard dialog window styling, not transparent
        self.setStyleSheet(f"""
            QDialog {{
                background: {THEME.colors.bg_base};
                color: {THEME.colors.text_primary};
            }}
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        # Header
        title = QLabel("Export Recording")
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 22px;
            font-weight: 300;
        """)
        root.addWidget(title)

        subtitle = QLabel(
            f"{self.recording.song_artist} — {self.recording.song_title}"
        )
        subtitle.setStyleSheet(f"""
            color: {THEME.colors.lime};
            font-size: 13px;
            margin-bottom: 8px;
        """)
        root.addWidget(subtitle)

        # Radio button group (only one selectable)
        self.button_group = QButtonGroup(self)

        # AUDIO SECTION
        audio_section = self._build_section("🎵 AUDIO", [
            ("mixed_raw",       "With Music · Raw voice",
             self.recording.mixed_raw_path, False),
            ("mixed_autotuned", "With Music · Auto-tuned ✨",
             self.recording.mixed_autotuned_path, False),
            ("voice_raw",       "Voice Only · Raw",
             self.recording.voice_raw_path, False),
            ("voice_autotuned", "Voice Only · Auto-tuned ✨",
             self.recording.voice_autotuned_path, False),
        ])
        root.addWidget(audio_section)

        # VIDEO SECTION
        video_section = self._build_section("🎥 VIDEO", [
            ("video_raw",       "With Music · Raw voice",
             self.recording.video_raw_path, True),
            ("video_autotuned", "With Music · Auto-tuned ✨",
             self.recording.video_autotuned_path, True),
            # Voice-only videos not implemented yet — omit
        ])
        root.addWidget(video_section)

        root.addStretch()

        # Bottom buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                color: white;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)

        button_row.addStretch()
        button_row.addWidget(cancel_btn)

        self.export_btn = QPushButton("Export...")
        self.export_btn.setFixedSize(160, 40)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {THEME.colors.lime};
                border: none;
                border-radius: 20px;
                color: {THEME.colors.bg_deep};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #C6FF5E;
            }}
            QPushButton:disabled {{
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.3);
            }}
        """)
        button_row.addWidget(self.export_btn)

        root.addLayout(button_row)

    def _build_section(
        self,
        title: str,
        items: list[tuple[str, str, Optional[Path], bool]],
    ) -> QWidget:
        """Build a section with radio options."""
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Section title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2px;
        """)
        layout.addWidget(title_label)

        # Options
        for version_id, label_text, path, is_video in items:
            available = path is not None and path.exists()

            radio = QRadioButton(label_text)
            radio.setEnabled(available)
            radio.setCursor(
                Qt.CursorShape.PointingHandCursor
                if available
                else Qt.CursorShape.ForbiddenCursor
            )

            # Add file info as tooltip / subtitle
            if available:
                size_mb = path.stat().st_size / (1024 * 1024)
                info = f"{path.suffix} · {size_mb:.1f} MB"
                radio.setToolTip(info)
            else:
                radio.setText(f"{label_text}  (not available)")

            radio.setStyleSheet(f"""
                QRadioButton {{
                    color: {THEME.colors.text_primary if available else THEME.colors.text_disabled};
                    font-size: 13px;
                    padding: 6px 0;
                    spacing: 12px;
                }}
                QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                }}
                QRadioButton::indicator::unchecked {{
                    background: rgba(255, 255, 255, 0.08);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    border-radius: 8px;
                }}
                QRadioButton::indicator::checked {{
                    background: {THEME.colors.lime};
                    border: 1px solid {THEME.colors.lime};
                    border-radius: 8px;
                }}
                QRadioButton:hover:enabled {{
                    color: {THEME.colors.lime};
                }}
                QRadioButton:disabled {{
                    color: rgba(255, 255, 255, 0.25);
                }}
            """)

            if available:
                radio.toggled.connect(
                    lambda checked, v=version_id, p=path: self._on_selected(
                        checked, v, p
                    )
                )
                self.button_group.addButton(radio)

            layout.addWidget(radio)

        return section

    def _on_selected(
        self, checked: bool, version: str, path: Path
    ) -> None:
        if checked:
            self.selected_version = version
            self.selected_path = path
            self.export_btn.setEnabled(True)

    def _on_export_clicked(self) -> None:
        if not self.selected_path:
            return

        # File dialog for save location
        default_name = self._build_filename()
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export",
            str(Path.home() / default_name),
            f"Media Files (*{self.selected_path.suffix})",
        )

        if not target:
            return

        # Copy file
        try:
            import shutil

            shutil.copy(self.selected_path, target)
            self.accept()  # Close dialog on success
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Export Failed", str(e))

    def _build_filename(self) -> str:
        artist_safe = (
            self.recording.song_artist.replace("/", "_").replace(" ", "_")
        )
        title_safe = (
            self.recording.song_title.replace("/", "_").replace(" ", "_")
        )
        version_tag = (
            self.selected_version.replace("_", "-")
            if self.selected_version
            else "export"
        )
        suffix = self.selected_path.suffix
        return f"{artist_safe}_-_{title_safe}_{version_tag}{suffix}"
