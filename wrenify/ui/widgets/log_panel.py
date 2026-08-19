"""Terminal-style log panel with monospace font and auto-scroll."""

from __future__ import annotations

from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import QTextEdit, QWidget


class LogPanel(QTextEdit):
    """Terminal-style log display. Auto-scrolls to bottom."""

    _LEVEL_COLORS = {
        "DEBUG":   "#6C757D",
        "INFO":    "#4CD964",
        "WARNING": "#FFB84D",
        "ERROR":   "#FF453A",
        "SUCCESS": "#B4FF39",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)

        font = QFont("JetBrains Mono, Fira Code, monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: rgba(255, 255, 255, 0.85);
                padding: 12px 16px;
                selection-background-color: rgba(180, 255, 57, 0.3);
            }
        """)

    def log(self, message: str, level: str = "INFO") -> None:
        """Add a log line with colored level tag."""
        color = self._LEVEL_COLORS.get(level, "#FFFFFF")
        html = (
            f'<span style="color:{color};">[{level}]</span> '
            f'<span style="color:rgba(255,255,255,0.75);">'
            f"{message}</span><br>"
        )
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self) -> None:
        self.clear()
