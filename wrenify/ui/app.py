"""Wrenify — application window, theme and entry point."""

import sys
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.config import CONFIG
from wrenify.karaoke.session import KaraokeSession
from wrenify.songs.song import Song
from wrenify.ui.import_view import ImportView
from wrenify.ui.karaoke_view import KaraokeView
from wrenify.ui.library_view import LibraryView
from wrenify.ui.pre_karaoke_view import PreKaraokeView
from wrenify.ui.recordings_view import RecordingsView
from wrenify.ui.results_view import SessionEndView
from wrenify.ui.theme import THEME, global_stylesheet
from wrenify.ui.widgets import (
    LOGO_PATH,
    LogoLabel,
    NavButton,
    PlaceholderPage,
    WelcomePage,
)
from wrenify.ui.widgets.glass import CaptionLabel, GradientBackground


class MainWindow(QMainWindow):
    """Main application window: sidebar navigation and stacked pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Wrenify — Your voice. Perfected.")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)
        self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self.session: Optional[KaraokeSession] = None
        self.karaoke_view: Optional[KaraokeView] = None
        self.end_view: Optional[SessionEndView] = None
        self._pre_view: Optional[PreKaraokeView] = None
        self._pending_song: Optional[Song] = None
        self._status_labels: list[QLabel] = []

        self._build_main_ui()

    def _build_main_ui(self) -> None:
        self.nav_buttons: list[NavButton] = []
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        root = GradientBackground()
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
        sidebar.setStyleSheet(f"background: rgba(10, 10, 21, .62); border-right: 1px solid {THEME.colors.border_subtle};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 28, 16, 20)
        layout.setSpacing(4)

        layout.addWidget(LogoLabel(56), alignment=Qt.AlignmentFlag.AlignHCenter)

        caption = CaptionLabel("Karaoke studio")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)
        layout.addSpacing(10)

        self._add_section(layout, "WORKSPACE")
        self._add_nav(layout, "Studio", 0)
        self._add_section(layout, "LIBRARY")
        self._add_nav(layout, "Songs", 5)
        self._add_nav(layout, "Recordings", 7)
        self._add_section(layout, "VOICE")
        self._add_nav(layout, "Auto-Tune", 1)
        self._add_nav(layout, "Speech", 2)
        self._add_section(layout, "PRODUCTION")
        self._add_nav(layout, "Lyrics", 3)
        self._add_nav(layout, "Import", 6)
        self._add_nav(layout, "Video", 4)

        layout.addStretch()

        hint = QLabel("v0.1.0  ·  local-first")
        hint.setStyleSheet(f"color: {THEME.colors.text_disabled}; font-size: 11px; padding: 8px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        return sidebar

    def _add_section(self, layout: QVBoxLayout, title: str) -> None:
        label = CaptionLabel(title)
        layout.addWidget(label)

    def _add_nav(self, layout: QVBoxLayout, text: str, index: int) -> None:
        button = NavButton(text)
        self._nav_group.addButton(button, index)
        button.clicked.connect(lambda _checked, target=index: self._select_nav(target))
        self.nav_buttons.append(button)
        layout.addWidget(button)

    def _select_nav(self, index: int) -> None:
        """Keep the glass navigation state aligned with the active page."""
        if index == 5:
            self._show_library()
            return
        if index == 6:
            self._show_import()
            return
        if index == 7:
            self._show_recordings()
            return
        self.stack.setCurrentIndex(index)
        button = self._nav_group.button(index)
        if button is not None:
            button.setChecked(True)

    def _build_pages(self) -> None:
        self.home_view = WelcomePage(
            self._show_library,
            library_callback=self._show_library,
            import_callback=self._show_import,
        )
        pages = [
            self.home_view,
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

        # Library view — grid of song cards
        self.library_view = LibraryView()
        self.library_view.song_selected.connect(self._on_song_selected)
        self.library_view.import_requested.connect(self._show_import)
        self.stack.addWidget(self.library_view)

        # Import view — URL paste + live progress log
        self.import_view = ImportView()
        self.import_view.back_requested.connect(self._show_library)
        self.import_view.import_completed.connect(self.library_view.reload_songs)
        self.import_view.import_completed.connect(self._show_library)
        self.stack.addWidget(self.import_view)

        # Recordings view — grid of saved sessions
        self.recordings_view = RecordingsView()
        self.recordings_view.back_requested.connect(self._show_home)
        self.stack.addWidget(self.recordings_view)

    def _show_home(self) -> None:
        """Show the Studio landing page."""
        self.stack.setCurrentWidget(self.home_view)
        self._check_nav(0)

    def _show_library(self) -> None:
        """Show the in-app song library (rescanning first)."""
        self.library_view.reload_songs()
        self.stack.setCurrentWidget(self.library_view)
        self._check_nav(5)

    def _show_import(self) -> None:
        """Show the import screen."""
        self.stack.setCurrentWidget(self.import_view)
        self._check_nav(6)

    def _show_recordings(self) -> None:
        """Show the saved recordings library (rescanning first)."""
        self.recordings_view.reload()
        self.stack.setCurrentWidget(self.recordings_view)
        self._check_nav(7)

    def _check_nav(self, index: int) -> None:
        """Synchronize sidebar state after programmatic navigation."""
        button = self._nav_group.button(index)
        if button is not None:
            button.setChecked(True)

    def _on_song_selected(self, song: Song) -> None:
        """Launch karaoke with the selected song from library."""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Ready to sing?",
            f"Karaoke: {song.display_name}\n\n"
            "Put on headphones for best results.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.launch_karaoke_with_song(song)

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

    def launch_karaoke_with_song(self, song: Song) -> None:
        """Show the ready screen for a fully-loaded Song."""
        self._pending_song = song
        self._pre_view = PreKaraokeView(song)
        self._pre_view.ready_signal.connect(self._start_karaoke_session)
        self._pre_view.cancel_signal.connect(self._back_to_menu)
        self.setCentralWidget(self._pre_view)

    def _start_karaoke_session(self) -> None:
        """Called after the user confirms ready (gesture or countdown)."""
        if self._pending_song is None:
            return

        self.session = KaraokeSession(self._pending_song, parent=self)
        self.karaoke_view = KaraokeView(self.session)
        self.session.finished_signal.connect(self._show_session_end)
        self.setCentralWidget(self.karaoke_view)
        self.session.start()

    def _show_session_end(self) -> None:
        """Called when karaoke session finishes."""
        recording_was_saved = bool(
            self._pending_song
            and self.session is not None
            and self.session._recorded_audio
        )

        self.end_view = SessionEndView(
            song=self._pending_song,
            recording_saved=recording_was_saved,
        )
        self.end_view.sing_again_requested.connect(self._sing_again)
        self.end_view.library_requested.connect(self._show_library)
        self.end_view.recordings_requested.connect(self._show_recordings)

        self.setCentralWidget(self.end_view)

    def _sing_again(self) -> None:
        """Sing the same song again, straight into the karaoke view."""
        if self._pending_song is not None:
            self._start_karaoke_session()

    def _back_to_menu(self) -> None:
        """Restore the main navigation UI after a karaoke session."""
        self.setCentralWidget(QWidget())
        self._build_main_ui()


def run() -> int:
    """Create the application, show the main window and enter the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Wrenify")
    app.setStyleSheet(global_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()
