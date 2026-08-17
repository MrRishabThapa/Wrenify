"""Wrenify — application window, theme and entry point."""

import sys

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
                    "Speech-to-text with Vosk models",
                    "No cloud calls, works without internet",
                    "Phrase spotting for karaoke alignment",
                ],
            ),
            PlaceholderPage(
                "Lyrics",
                "Time-synced lyrics with word-level highlighting.",
                [
                    "Fetch synced lyrics (LRCLIB / Genius)",
                    "Parse LRC and enhanced LRC formats",
                    "Phonetic alignment for imperfect sync",
                    "Karaoke-style line highlighting",
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
        status.addPermanentWidget(QLabel(f"Audio: {CONFIG.audio.sample_rate} Hz"))
        status.addPermanentWidget(
            QLabel(
                f"Auto-tune: {CONFIG.autotune.key} {CONFIG.autotune.scale}"
            )
        )
        if CONFIG.audio.device_index is not None:
            status.addPermanentWidget(
                QLabel(f"Device: index {CONFIG.audio.device_index}")
            )
        else:
            status.addPermanentWidget(QLabel("Device: system default"))
        status.addPermanentWidget(
            QLabel("Debug: on" if CONFIG.debug else "Debug: off")
        )


def run() -> int:
    """Create the application, show the main window and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Wrenify")
    app.setStyleSheet(THEME_QSS)
    window = MainWindow()
    window.show()
    return app.exec()
