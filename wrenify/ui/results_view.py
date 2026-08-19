"""
Wrenify — Post-song results screen showing final score.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wrenify.karaoke.scorer import ScoreReport
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import GlassCard, GlowLabel, GradientBackground, PillButton


class ResultsView(QWidget):
    """Displays final score after a karaoke session ends."""

    retry_signal = pyqtSignal()
    exit_signal  = pyqtSignal()

    def __init__(self, report: ScoreReport, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.report = report
        background = GradientBackground(self)
        background.setGeometry(self.rect())
        background.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        card = GlassCard(elevation=2)
        card.setMaximumWidth(760)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(56, 42, 56, 42)
        card_layout.setSpacing(18)

        # Title
        title = QLabel("SESSION COMPLETE")
        title.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {THEME.colors.text_tertiary}; letter-spacing: 3px;")
        card_layout.addWidget(title)

        # Grade
        grade = GlowLabel(report.grade, self._grade_color())
        grade.setFont(QFont("Inter", 116, QFont.Weight.Thin))
        grade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grade.setStyleSheet(f"color: {self._grade_color()};")
        card_layout.addWidget(grade)

        # Score
        score = QLabel(f"{report.total_score:.1f}%")
        score.setFont(QFont("Inter", 48, QFont.Weight.Light))
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score.setStyleSheet(f"color: {THEME.colors.text_primary};")
        card_layout.addWidget(score)

        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for label, value, color in [
            ("Correct", report.correct_count, "#4CD964"),
            ("Wrong",   report.wrong_count,   "#FF3B30"),
            ("Missed",  report.missed_count,  "#FF9500"),
            ("Total",   report.total_words,   "#FFFFFF"),
        ]:
            stat = self._stat_widget(label, str(value), color)
            stats_layout.addWidget(stat)
        card_layout.addSpacing(8)
        card_layout.addLayout(stats_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        retry = PillButton("Sing Again", "accent")
        retry.setFixedSize(180, 50)
        retry.clicked.connect(self.retry_signal.emit)

        done = PillButton("Back to Menu", "ghost")
        done.setFixedSize(180, 50)
        done.clicked.connect(self.exit_signal.emit)

        btn_layout.addWidget(retry)
        btn_layout.addWidget(done)
        card_layout.addSpacing(10)
        card_layout.addLayout(btn_layout)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event) -> None:  # noqa: N802
        background = self.findChild(GradientBackground)
        if background is not None:
            background.setGeometry(self.rect())
        super().resizeEvent(event)

    def _grade_color(self) -> str:
        g = self.report.grade
        if g.startswith("A"):
            return "#B4FF39"
        if g.startswith("B"):
            return "#4CD964"
        if g.startswith("C"):
            return "#FFD93D"
        if g.startswith("D"):
            return "#FF9500"
        return "#FF3B30"

    def _stat_widget(self, label: str, value: str, color: str) -> QWidget:
        container = GlassCard(elevation=1)
        container.setMinimumWidth(126)
        v = QVBoxLayout(container)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val_label = QLabel(value)
        val_label.setFont(QFont("Inter", 28, QFont.Weight.Light))
        val_label.setStyleSheet(f"color: {color};")
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(label)
        name_label.setFont(QFont("Inter", 14))
        name_label.setStyleSheet(f"color: {THEME.colors.text_tertiary};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        v.addWidget(val_label)
        v.addWidget(name_label)
        return container
