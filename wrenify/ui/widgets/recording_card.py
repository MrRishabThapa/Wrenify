"""Recording card widget for the recordings grid."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.recordings.models import Recording
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard


class RecordingCard(GlassCard):
    """Card displaying a saved recording with play/export/delete actions."""

    play_requested   = pyqtSignal(Recording, str)  # recording, version_name
    export_requested = pyqtSignal(Recording)
    delete_requested = pyqtSignal(Recording)

    def __init__(self, recording: Recording, parent: QWidget | None = None) -> None:
        super().__init__(parent, radius=16)
        self.recording = recording
        self.setFixedSize(280, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel(recording.song_title)
        title.setStyleSheet(f"""
            color: {THEME.colors.text_primary};
            font-size: 15px;
            font-weight: 600;
        """)
        title.setWordWrap(True)
        layout.addWidget(title)

        # Artist
        artist = QLabel(recording.song_artist)
        artist.setStyleSheet(f"""
            color: {THEME.colors.lime};
            font-size: 12px;
        """)
        layout.addWidget(artist)

        # Date + duration (that's all metadata now)
        meta = QLabel(f"{recording.date_display} · {recording.duration_display}")
        meta.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 11px;
        """)
        layout.addWidget(meta)

        layout.addStretch()

        # WITH MUSIC section
        music_label = QLabel("WITH MUSIC")
        music_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 9px;
            letter-spacing: 1.5px;
        """)
        layout.addWidget(music_label)

        mixed_row = QHBoxLayout()
        mixed_row.setSpacing(6)

        if recording.has_mixed_raw:
            btn = self._mini_btn("▶ Raw")
            btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "mixed_raw")
            )
            mixed_row.addWidget(btn)

        if recording.has_mixed_autotuned:
            btn = self._mini_btn("✨ Auto-Tune", accent=True)
            btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "mixed_autotuned")
            )
            mixed_row.addWidget(btn)

        if not recording.has_mixed_raw and not recording.has_mixed_autotuned:
            no_mix = self._mini_btn("Not available")
            no_mix.setEnabled(False)
            mixed_row.addWidget(no_mix)

        layout.addLayout(mixed_row)

        # VOICE ONLY section
        voice_label = QLabel("VOICE ONLY")
        voice_label.setStyleSheet(f"""
            color: {THEME.colors.text_tertiary};
            font-size: 9px;
            letter-spacing: 1.5px;
            margin-top: 4px;
        """)
        layout.addWidget(voice_label)

        voice_row = QHBoxLayout()
        voice_row.setSpacing(6)

        if recording.has_voice_raw:
            btn = self._mini_btn("▶ Raw")
            btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "voice_raw")
            )
            voice_row.addWidget(btn)

        if recording.has_voice_autotuned:
            btn = self._mini_btn("✨ Auto-Tune", accent=True)
            btn.clicked.connect(
                lambda: self.play_requested.emit(recording, "voice_autotuned")
            )
            voice_row.addWidget(btn)

        layout.addLayout(voice_row)

        # Actions
        actions = QHBoxLayout()
        actions.setSpacing(6)

        export_btn = self._mini_btn("⤓ Export")
        export_btn.clicked.connect(
            lambda: self.export_requested.emit(recording)
        )
        actions.addWidget(export_btn)

        del_btn = self._mini_btn("🗑", small=True)
        del_btn.clicked.connect(
            lambda: self.delete_requested.emit(recording)
        )
        actions.addWidget(del_btn)

        layout.addLayout(actions)

    def _mini_btn(
        self, text: str, small: bool = False, accent: bool = False
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        if small:
            btn.setFixedWidth(32)

        if accent:
            style = """
                QPushButton {
                    background: rgba(180, 255, 57, 0.15);
                    border: 1px solid rgba(180, 255, 57, 0.4);
                    border-radius: 8px;
                    color: #B4FF39;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.25);
                    border-color: rgba(180, 255, 57, 0.6);
                }
            """
        else:
            style = """
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    color: white;
                    font-size: 11px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(180, 255, 57, 0.15);
                    border-color: rgba(180, 255, 57, 0.4);
                }
                QPushButton:disabled {
                    color: rgba(255, 255, 255, 0.3);
                    background: rgba(255, 255, 255, 0.02);
                }
            """

        btn.setStyleSheet(style)
        return btn
