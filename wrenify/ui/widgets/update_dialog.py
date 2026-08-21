"""
Wrenify — Liquid Glass In-App Updating Screen.

Displays update details, real-time download progress, and restart trigger.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.updater import UpdateDownloadWorker, UpdateInfo
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard, PillButton


class UpdateDialog(QDialog):
    """Liquid Glass Modal displaying update notes, progress bar, and restart."""

    def __init__(self, info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self._download_thread: QThread | None = None
        self._download_worker: UpdateDownloadWorker | None = None

        self.setWindowTitle("Wrenify In-App Updater")
        self.setFixedSize(520, 420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME.colors.bg_deep};
                color: {THEME.colors.text_primary};
            }}
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header Card
        card = GlassCard(radius=16)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel(f"✨ Updating Wrenify to v{self.info.latest_version}")
        header.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {THEME.colors.lime};")
        card_layout.addWidget(header)

        sub = QLabel(f"Current version: v{self.info.current_version} · Songs & recordings stay safe!")
        sub.setStyleSheet(f"color: {THEME.colors.text_tertiary}; font-size: 12px;")
        card_layout.addWidget(sub)

        layout.addWidget(card)

        # Status & Progress Section
        self.status_label = QLabel("Click 'Download & Update' to begin.")
        self.status_label.setStyleSheet(f"color: {THEME.colors.text_secondary}; font-size: 13px;")
        layout.addWidget(self.status_label)

        # Gradient Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0 y1:0 x2:1 y2:0,
                    stop:0 {THEME.colors.violet},
                    stop:1 {THEME.colors.lime}
                );
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Download Stats Label
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {THEME.colors.text_tertiary}; font-size: 11px;")
        layout.addWidget(self.stats_label)

        # Changelog Notes
        notes_title = QLabel("WHAT'S NEW")
        notes_title.setStyleSheet(f"color: {THEME.colors.text_tertiary}; font-size: 10px; font-weight: 700; letter-spacing: 2px;")
        layout.addWidget(notes_title)

        notes_body = QLabel(self.info.changelog)
        notes_body.setWordWrap(True)
        notes_body.setStyleSheet(f"color: {THEME.colors.text_secondary}; font-size: 12px; line-height: 1.4;")
        layout.addWidget(notes_body)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = PillButton("Cancel", variant="ghost")
        self.cancel_btn.clicked.connect(self._on_cancel)

        self.action_btn = PillButton("Download & Update", variant="accent")
        self.action_btn.clicked.connect(self._on_action_clicked)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.action_btn)

        layout.addLayout(btn_layout)

    def _on_action_clicked(self) -> None:
        """Triggers download or restarts app when download completes."""
        if self.action_btn.text() == "Restart & Apply":
            # Restart Wrenify
            python = sys.executable
            os.execl(python, python, *sys.argv)

        self.action_btn.setEnabled(False)
        self.action_btn.setText("Downloading...")
        self.cancel_btn.setText("Cancel Download")

        # Start download in worker thread
        self._download_thread = QThread()
        self._download_worker = UpdateDownloadWorker(self.info.download_url)
        self._download_worker.moveToThread(self._download_thread)

        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.status_changed.connect(self.status_label.setText)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.finished.connect(self._download_thread.quit)

        self._download_thread.start()

    def _on_progress(self, percent: float, downloaded: int, total: int, speed: str) -> None:
        self.progress_bar.setValue(int(percent))
        dl_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        if total > 0:
            self.stats_label.setText(f"{dl_mb:.1f} MB / {total_mb:.1f} MB ({percent:.0f}%) · {speed}")
        else:
            self.stats_label.setText(f"{dl_mb:.1f} MB downloaded · {speed}")

    def _on_download_finished(self, success: bool, msg: str) -> None:
        if success:
            self.status_label.setText("✨ Update installed! Click Restart to complete.")
            self.action_btn.setText("Restart & Apply")
            self.action_btn.setEnabled(True)
            self.cancel_btn.setText("Close")
        else:
            self.status_label.setText(f"Update failed: {msg}")
            self.action_btn.setText("Retry")
            self.action_btn.setEnabled(True)

    def _on_cancel(self) -> None:
        if self._download_worker:
            self._download_worker.cancel()
        self.reject()