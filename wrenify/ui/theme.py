"""Wrenify's shared liquid-glass design tokens and application stylesheet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    lime: str = "#B4FF39"
    lime_soft: str = "#B4FF3980"
    lime_glow: str = "#B4FF3940"
    violet: str = "#8B5CF6"
    violet_soft: str = "#8B5CF680"
    violet_glow: str = "#8B5CF640"
    bg_deep: str = "#0A0A15"
    bg_base: str = "#0F0F1E"
    bg_elevated: str = "#161629"
    glass_lo: str = "rgba(255, 255, 255, 0.03)"
    glass_md: str = "rgba(255, 255, 255, 0.06)"
    glass_hi: str = "rgba(255, 255, 255, 0.10)"
    border_subtle: str = "rgba(255, 255, 255, 0.08)"
    border_hover: str = "rgba(180, 255, 57, 0.30)"
    border_focus: str = "rgba(139, 92, 246, 0.50)"
    text_primary: str = "#FFFFFF"
    text_secondary: str = "rgba(255, 255, 255, 0.70)"
    text_tertiary: str = "rgba(255, 255, 255, 0.45)"
    text_disabled: str = "rgba(255, 255, 255, 0.25)"
    success: str = "#4CD964"
    warning: str = "#FFB84D"
    error: str = "#FF453A"


@dataclass(frozen=True)
class Typography:
    family_sans: str = "Inter, SF Pro Display, Segoe UI, sans-serif"
    family_mono: str = "JetBrains Mono, Fira Code, monospace"
    size_xs: int = 11
    size_sm: int = 13
    size_md: int = 15
    size_lg: int = 18
    size_xl: int = 24
    size_2xl: int = 32
    size_3xl: int = 48
    size_4xl: int = 72
    weight_thin: int = 100
    weight_light: int = 300
    weight_regular: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48
    huge: int = 64


@dataclass(frozen=True)
class Radius:
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 28
    full: int = 999


@dataclass(frozen=True)
class Effects:
    shadow_sm: tuple = (8, 0, 2, "rgba(0, 0, 0, 0.4)")
    shadow_md: tuple = (16, 0, 4, "rgba(0, 0, 0, 0.5)")
    shadow_lg: tuple = (32, 0, 8, "rgba(0, 0, 0, 0.6)")
    glow_lime: tuple = (24, 0, 0, "rgba(180, 255, 57, 0.35)")
    glow_violet: tuple = (24, 0, 0, "rgba(139, 92, 246, 0.35)")


@dataclass(frozen=True)
class Theme:
    colors: Colors = Colors()
    typography: Typography = Typography()
    spacing: Spacing = Spacing()
    radius: Radius = Radius()
    effects: Effects = Effects()


THEME = Theme()


def global_stylesheet() -> str:
    """Return the base QSS shared by all Wrenify views."""
    C, T, S, R = THEME.colors, THEME.typography, THEME.spacing, THEME.radius
    return f"""
        QWidget {{ background: transparent; color: {C.text_primary};
                  font-family: {T.family_sans}; font-size: {T.size_md}px; }}
        QMainWindow, QDialog {{ background-color: {C.bg_base}; }}
        QPushButton {{ background-color: {C.glass_md}; border: 1px solid {C.border_subtle};
                      border-radius: {R.md}px; color: {C.text_primary};
                      padding: {S.sm}px {S.lg}px; font-weight: {T.weight_medium}; }}
        QPushButton:hover {{ background-color: {C.glass_hi}; border-color: {C.border_hover}; }}
        QPushButton:pressed {{ background-color: rgba(180, 255, 57, 0.15); }}
        QPushButton:focus {{ border-color: {C.border_focus}; }}
        QPushButton:disabled {{ color: {C.text_disabled}; background-color: {C.glass_lo}; }}
        QLineEdit, QComboBox {{ background-color: {C.glass_md}; border: 1px solid {C.border_subtle};
                                border-radius: {R.md}px; padding: {S.sm}px {S.md}px; }}
        QLineEdit:focus, QComboBox:focus {{ border-color: {C.border_focus}; background-color: {C.glass_hi}; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {C.glass_hi}; border-radius: 4px; min-height: 40px; }}
        QScrollBar::handle:vertical:hover {{ background: rgba(180, 255, 57, 0.3); }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        QStatusBar {{ background: rgba(10, 10, 21, .72); border-top: 1px solid {C.border_subtle}; }}
        QStatusBar::item {{ border: none; }}
    """
