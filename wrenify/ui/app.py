"""Wrenify — application window, theme and entry point."""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.config import CONFIG
from wrenify.karaoke.scorer import ScoreReport
from wrenify.karaoke.session import KaraokeSession
from wrenify.lyrics.parser import LRCParser
from wrenify.ui.karaoke_view import KaraokeView
from wrenify.ui.results_view import ResultsView
from wrenify.ui.widgets import (
    LOGO_PATH,
    LogoLabel,
    NavButton,
    PlaceholderPage,
    WelcomePage,
)

THEME_QSS = """
* {
    font-family: "Inter", "Noto Sans", sans-serif;
}

QMainWindow, QWidget#Root {
    background-color: #101019;
}

QWidget#Sidebar {
    background-color: #0a0a10;
    border-right: 1px solid #1d1d2b;
}

QLabel#SidebarCaption {
    color: #8b87a6;
    font-size: 10px;
    font-weight: 700;
}

QLabel#SidebarSection {
    color: #4d4a63;
    font-size: 10px;
    font-weight: 700;
    padding: 14px 14px 4px 14px;
}

QPushButton#NavButton {
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 8px;
    color: #9793b2;
    font-size: 14px;
    padding: 10px 14px;
    text-align: left;
}

QPushButton#NavButton:hover {
    background: #14141f;
    color: #d9d6ea;
}

QPushButton#NavButton:checked {
    background: #1c1428;
    color: #b38bff;
    border-left: 3px solid #a020f0;
    font-weight: 600;
}

QStackedWidget {
    background-color: #101019;
}

QLabel#PageHeader {
    font-size: 24px;
    font-weight: 700;
    color: #f1eefb;
}

QLabel#PageDesc {
    color: #8f8aa9;
    font-size: 13px;
}

QLabel#Badge {
    background-color: #1a1226;
    color: #a78bfa;
    border: 1px solid #33244d;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
}

QFrame#Card {
    background-color: #14141f;
    border: 1px solid #1e1e2c;
    border-radius: 12px;
}

QLabel#FeatureItem {
    color: #b5b1cd;
    font-size: 13px;
    padding: 3px 0;
}

QLabel#WelcomeTitle {
    font-size: 30px;
    font-weight: 800;
    color: #f1eefb;
}

QLabel#WelcomeTagline {
    font-size: 14px;
    color: #a78bfa;
    font-style: italic;
}

QLabel#Chip {
    background-color: #16161f;
    border: 1px solid #242434;
    border-radius: 12px;
    color: #cfcbe4;
    font-size: 12px;
    padding: 6px 14px;
}

QLabel#SidebarHint {
    color: #4d4a63;
    font-size: 10px;
}

QStatusBar {
    background-color: #0a0a10;
    color: #6f6b8a;
    border-top: 1px solid #1d1d2b;
}

QStatusBar::item {
    border: none;
}

QStatusBar QLabel {
    color: #6f6b8a;
    font-size: 12px;
    padding: 0 10px;
}
"""


class MainWindow(QMainWindow):
    """Main application window: sidebar navigation and stacked pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Wrenify — Your voice. Perfected.")
        self.resize(1280, 800)
        self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self.session: Optional[KaraokeSession] = None
        self.karaoke_view: Optional[KaraokeView] = None
        self.results_view: Optional[ResultsView] = None
        self._last_lrc: Optional[Path] = None
        self._status_labels: list[QLabel] = []

        self._build_main_ui()

    def _build_main_ui(self) -> None:
        self.nav_buttons: list[NavButton] = []

        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(root)
        self._build_pages()
        self._build_status_bar()
        self.nav_buttons[0].setChecked(True)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)

        layout.addWidget(LogoLabel(56), alignment=Qt.AlignmentFlag.AlignHCenter)

        caption = QLabel("KARAOKE STUDIO")
        caption.setObjectName("SidebarCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)
        layout.addSpacing(10)

        self._add_section(layout, "WORKSPACE")
        self._add_nav(layout, "Studio", 0)
        self._add_section(layout, "VOICE")
        self._add_nav(layout, "Auto-Tune", 1)
        self._add_nav(layout, "Speech", 2)
        self._add_section(layout, "PRODUCTION")
        self._add_nav(layout, "Lyrics", 3)
        self._add_nav(layout, "Video", 4)

        layout.addStretch()

        hint = QLabel("v0.1.0  ·  local-first")
        hint.setObjectName("SidebarHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        return sidebar

    def _add_section(self, layout: QVBoxLayout, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("SidebarSection")
        layout.addWidget(label)

    def _add_nav(self, layout: QVBoxLayout, text: str, index: int) -> None:
        button = NavButton(text)
        button.clicked.connect(lambda: self.stack.setCurrentIndex(index))
        self.nav_buttons.append(button)
        layout.addWidget(button)

    def _build_pages(self) -> None:
        pages = [
            WelcomePage(),
            PlaceholderPage(
                "Auto-Tune",
                "Real-time pitch correction for your voice.",
                [
                    "Pitch tracking with the WORLD vocoder",
                    "Key and scale presets (major, minor, pentatonic)",
                    "Adjustable correction strength",
                    "Vibrato and formant shaping effects",
                ],
            ),
            PlaceholderPage(
                "Speech",
                "Offline voice recognition, fully local.",
                [
                    "Word-level timestamps with faster-whisper",
                    "Batch transcription of WAV files",
                    "Live streaming mode with ~1-2s latency",
                    "Base model in int8 mode: ~800MB RAM",
                ],
            ),
            PlaceholderPage(
                "Lyrics",
                "Time-synced lyrics with word-level highlighting.",
                [
                    "Fetch synced lyrics (Musixmatch / LRCLIB / NetEase)",
                    "LRC + enhanced LRC parsing with word timings",
                    "Phonetic stretching for held notes",
                    "Karaoke-style line highlighting (planned)",
                ],
            ),
            PlaceholderPage(
                "Video",
                "Webcam recording with an MP4 export.",
                [
                    "Webcam preview and capture",
                    "Overlay your performance render",
                    "Export MP4 with the mixed audio track",
                ],
            ),
        ]
        for page in pages:
            self.stack.addWidget(page)

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        for label in self._status_labels:
            status.removeWidget(label)
            label.deleteLater()
        self._status_labels.clear()

        for text in (
            f"Audio: {CONFIG.audio.sample_rate} Hz",
            f"Auto-tune: {CONFIG.autotune.key} {CONFIG.autotune.scale}",
            f"Whisper: {CONFIG.speech.model_size} "
            f"({CONFIG.speech.compute_type})",
            f"Device: index {CONFIG.audio.device_index}"
            if CONFIG.audio.device_index is not None
            else "Device: system default",
            "Debug: on" if CONFIG.debug else "Debug: off",
        ):
            label = QLabel(text)
            status.addPermanentWidget(label)
            self._status_labels.append(label)

    def launch_karaoke(self, lrc_path: Path) -> None:
        """Start a karaoke session with the given .lrc file."""
        parser = LRCParser()
        lyrics = parser.parse_file(lrc_path)

        self._last_lrc = lrc_path
        self.session = KaraokeSession(lyrics, parent=self)
        self.karaoke_view = KaraokeView(self.session)
        self.session.finished_signal.connect(self._show_results)

        self.setCentralWidget(self.karaoke_view)
        self.session.start()

    def _show_results(self, report: ScoreReport) -> None:
        """Show results screen after session ends."""
        self.results_view = ResultsView(report)
        self.results_view.retry_signal.connect(self._retry)
        self.results_view.exit_signal.connect(self._back_to_menu)
        self.setCentralWidget(self.results_view)

    def _retry(self) -> None:
        if self._last_lrc is not None:
            self.launch_karaoke(self._last_lrc)

    def _back_to_menu(self) -> None:
        """Restore the main navigation UI after a karaoke session."""
        self.setCentralWidget(QWidget())
        self._build_main_ui()


def run() -> int:
    """Create the application, show the main window and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Wrenify")
    app.setStyleSheet(THEME_QSS)
    window = MainWindow()
    window.show()
    return app.exec()
