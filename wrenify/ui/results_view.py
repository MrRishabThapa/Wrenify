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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.karaoke.scorer import ScoreReport


class ResultsView(QWidget):
    """Displays final score after a karaoke session ends."""

    retry_signal = pyqtSignal()
    exit_signal  = pyqtSignal()

    def __init__(self, report: ScoreReport, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.report = report
        self.setStyleSheet("background: #0A0A15; color: white;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Title
        title = QLabel("Session Complete")
        title.setFont(QFont("Inter", 32, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #B4FF39;")
        layout.addWidget(title)

        # Grade
        grade = QLabel(report.grade)
        grade.setFont(QFont("Inter", 96, QFont.Weight.Black))
        grade.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grade.setStyleSheet(f"color: {self._grade_color()};")
        layout.addWidget(grade)

        # Score
        score = QLabel(f"{report.total_score:.1f}%")
        score.setFont(QFont("Inter", 48, QFont.Weight.Bold))
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score)

        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(40)
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for label, value, color in [
            ("Correct", report.correct_count, "#4CD964"),
            ("Wrong",   report.wrong_count,   "#FF3B30"),
            ("Missed",  report.missed_count,  "#FF9500"),
            ("Total",   report.total_words,   "#FFFFFF"),
        ]:
            stat = self._stat_widget(label, str(value), color)
            stats_layout.addWidget(stat)
        layout.addLayout(stats_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        retry = QPushButton("Sing Again")
        retry.setFixedSize(180, 50)
        retry.setStyleSheet(self._button_style("#8B5CF6"))
        retry.clicked.connect(self.retry_signal.emit)

        done = QPushButton("Back to Menu")
        done.setFixedSize(180, 50)
        done.setStyleSheet(self._button_style("#333"))
        done.clicked.connect(self.exit_signal.emit)

        btn_layout.addWidget(retry)
        btn_layout.addWidget(done)
        layout.addLayout(btn_layout)

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
        container = QWidget()
        v = QVBoxLayout(container)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        val_label = QLabel(value)
        val_label.setFont(QFont("Inter", 32, QFont.Weight.Bold))
        val_label.setStyleSheet(f"color: {color};")
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(label)
        name_label.setFont(QFont("Inter", 14))
        name_label.setStyleSheet("color: #999;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        v.addWidget(val_label)
        v.addWidget(name_label)
        return container

    @staticmethod
    def _button_style(bg: str) -> str:
        return (
            f"QPushButton {{"
            f"  background: {bg}; color: white; border-radius: 8px;"
            f"  font-size: 16px; font-weight: bold; border: none;"
            f"}}"
            f"QPushButton:hover {{ background: {bg}; }}"
        )
