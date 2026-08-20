"""Standard Wrenify navigation and page widgets."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.config import ASSETS_DIR, CONFIG
from wrenify.ui.theme import THEME
from wrenify.ui.widgets.glass import (
    CaptionLabel,
    GlassCard,
    GlowLabel,
    PillButton,
    SidebarItem,
)

LOGO_PATH = ASSETS_DIR / "wrenify.png"


def logo_pixmap(height: int) -> QPixmap:
    pixmap = QPixmap(str(LOGO_PATH))
    return pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


class LogoLabel(QLabel):
    def __init__(self, height: int = 64, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPixmap(logo_pixmap(height))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class NavButton(SidebarItem):
    """Compatibility name for the sidebar's glass navigation item."""


class WelcomePage(QWidget):
    """The Studio landing page with in-app entry points."""

    def __init__(
        self,
        start_callback: Callable[[], None] | None = None,
        library_callback: Callable[[], None] | None = None,
        import_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 42, 48, 42)
        layout.setSpacing(14)
        layout.addStretch()

        layout.addWidget(LogoLabel(210), alignment=Qt.AlignmentFlag.AlignCenter)
        title = GlowLabel("WRENIFY", THEME.colors.violet)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {THEME.colors.text_primary}; font-size: 52px; font-weight: 300; letter-spacing: 8px;")
        layout.addWidget(title)
        tagline = QLabel("Your voice. Perfected.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(f"color: {THEME.colors.lime}; font-size: 18px; font-weight: 300; font-style: italic; letter-spacing: 1px;")
        layout.addWidget(tagline)
        layout.addSpacing(20)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        start = PillButton("Start Karaoke", "accent")
        start.setMinimumWidth(180)
        if start_callback is not None:
            start.clicked.connect(start_callback)
        library = PillButton("My Library", "ghost")
        imported = PillButton("Import Song", "primary")
        library.setMinimumWidth(140)
        imported.setMinimumWidth(140)
        if library_callback is not None:
            library.clicked.connect(library_callback)
        if import_callback is not None:
            imported.clicked.connect(import_callback)
        for button in (start, library, imported):
            actions.addWidget(button)
        layout.addLayout(actions)
        layout.addSpacing(28)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        chips.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for text in (
            f"Audio · {CONFIG.audio.sample_rate} Hz",
            f"Whisper · {CONFIG.speech.model_size} ({CONFIG.speech.compute_type})",
            "Device · system default" if CONFIG.audio.device_index is None else f"Device · {CONFIG.audio.device_index}",
        ):
            chip = QLabel(text)
            chip.setStyleSheet(f"background: {THEME.colors.glass_md}; border: 1px solid {THEME.colors.border_subtle}; border-radius: 999px; padding: 8px 16px; color: {THEME.colors.text_secondary}; font-size: 12px;")
            chips.addWidget(chip)
        layout.addLayout(chips)
        layout.addStretch()


class PlaceholderPage(QWidget):
    """A restrained glass placeholder for modules that are not live yet."""

    def __init__(self, title: str, description: str, features: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(56, 48, 56, 40)
        layout.setSpacing(18)
        heading = QLabel(title)
        heading.setStyleSheet(f"color: {THEME.colors.text_primary}; font-size: 32px; font-weight: 300;")
        layout.addWidget(heading)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {THEME.colors.text_secondary}; font-size: 15px;")
        layout.addWidget(desc)
        card = GlassCard(elevation=1)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(8)
        card_layout.addWidget(CaptionLabel("Planned capabilities"))
        for feature in features:
            item = QLabel(f"•  {feature}")
            item.setStyleSheet(f"color: {THEME.colors.text_secondary}; padding: 4px 0;")
            card_layout.addWidget(item)
        layout.addWidget(card)
        layout.addStretch()
