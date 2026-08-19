"""Reusable liquid-glass widgets for Wrenify."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QPushButton, QWidget

from wrenify.ui.theme import THEME


class GlassCard(QFrame):
    """Frosted panel with a fine border and restrained shadow."""

    def __init__(self, parent: QWidget | None = None, radius: int | None = None, elevation: int = 1) -> None:
        super().__init__(parent)
        self.setObjectName("GlassCard")
        self.setStyleSheet(f"QFrame#GlassCard {{ background: {THEME.colors.glass_md}; border: 1px solid {THEME.colors.border_subtle}; border-radius: {radius or THEME.radius.lg}px; }}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18 * elevation)
        shadow.setOffset(0, 3 * elevation)
        shadow.setColor(QColor(0, 0, 0, 95))
        self.setGraphicsEffect(shadow)


class GradientBackground(QWidget):
    """Dark navy canvas with low-contrast violet and lime ambience."""

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(10, 10, 21))
        w, h = self.width(), self.height()
        self._orb(painter, QPoint(int(w * .14), int(h * .18)), int(min(w, h) * .62), QColor(139, 92, 246, 44))
        self._orb(painter, QPoint(int(w * .86), int(h * .82)), int(min(w, h) * .54), QColor(180, 255, 57, 32))
        self._orb(painter, QPoint(int(w * .73), int(h * .30)), int(min(w, h) * .26), QColor(139, 92, 246, 24))

    @staticmethod
    def _orb(painter: QPainter, center: QPoint, radius: int, color: QColor) -> None:
        gradient = QRadialGradient(QPointF(center), radius)
        gradient.setColorAt(0, color)
        edge = QColor(color)
        edge.setAlpha(0)
        gradient.setColorAt(1, edge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(center.x() - radius, center.y() - radius, radius * 2, radius * 2)


class GlowLabel(QLabel):
    def __init__(self, text: str = "", glow_color: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(20)
        glow.setOffset(0, 0)
        glow.setColor(QColor(glow_color or THEME.colors.lime))
        self.setGraphicsEffect(glow)


class PillButton(QPushButton):
    """Rounded CTA with a glass, violet, or lime treatment."""

    def __init__(self, text: str = "", variant: str = "ghost", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("PillButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        C = THEME.colors
        if variant == "primary":
            base, hover, fg = f"qlineargradient(x1:0 y1:0 x2:1 y2:0, stop:0 {C.violet}, stop:1 #A57CFF)", "#9B6EF7", "white"
        elif variant == "accent":
            base, hover, fg = f"qlineargradient(x1:0 y1:0 x2:1 y2:0, stop:0 {C.lime}, stop:1 #D4FF6C)", "#C6FF5E", C.bg_deep
        else:
            base, hover, fg = C.glass_md, C.glass_hi, C.text_primary
        self.setStyleSheet(f"""QPushButton#PillButton {{ background: {base}; color: {fg}; border: 1px solid {C.border_subtle}; border-radius: 22px; padding: 12px 28px; font-size: 14px; font-weight: 600; min-height: 20px; }} QPushButton#PillButton:hover {{ background: {hover}; border-color: {C.border_hover}; }}""")


class SidebarItem(QPushButton):
    def __init__(self, text: str, active: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("SidebarItem")
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        C = THEME.colors
        self.setStyleSheet(f"""QPushButton#SidebarItem {{ background: transparent; border: none; border-radius: 12px; color: {C.text_secondary}; text-align: left; padding: 10px 16px; font-size: 14px; font-weight: 500; min-height: 20px; }} QPushButton#SidebarItem:hover {{ background: {C.glass_md}; color: {C.text_primary}; }} QPushButton#SidebarItem:checked {{ background: qlineargradient(x1:0 y1:0 x2:1 y2:0, stop:0 rgba(139,92,246,.20), stop:1 rgba(180,255,57,.10)); color: {C.lime}; border-left: 2px solid {C.lime}; font-weight: 600; }}""")


class CaptionLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("CaptionLabel")
        self.setStyleSheet(f"QLabel#CaptionLabel {{ color: {THEME.colors.text_tertiary}; font-size: 10px; font-weight: 700; letter-spacing: 2px; padding: 8px 16px; }}")
