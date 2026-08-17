"""Wrenify — reusable UI widgets."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrenify.core.config import ASSETS_DIR, CONFIG

LOGO_PATH = ASSETS_DIR / "wrenify.png"


def logo_pixmap(height: int) -> QPixmap:
    """Load the Wrenify logo scaled to a target height."""
    pixmap = QPixmap(str(LOGO_PATH))
    return pixmap.scaledToHeight(
        height, Qt.TransformationMode.SmoothTransformation
    )


class LogoLabel(QLabel):
    """The Wrenify logo as a label."""

    def __init__(self, height: int = 64, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPixmap(logo_pixmap(height))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class NavButton(QPushButton):
    """Sidebar navigation button, checkable to track the active page."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class WelcomePage(QWidget):
    """Studio landing page: logo, tagline and live configuration chips."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addStretch()

        logo = LogoLabel(220)
        layout.addWidget(logo)

        title = QLabel("WRENIFY")
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        tagline = QLabel("Your voice. Perfected.")
        tagline.setObjectName("WelcomeTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        layout.addSpacing(18)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        chips.addStretch()
        for text in (
            f"Audio: {CONFIG.audio.sample_rate} Hz",
            f"Auto-tune: {CONFIG.autotune.key} {CONFIG.autotune.scale}",
            (
                f"Device: index {CONFIG.audio.device_index}"
                if CONFIG.audio.device_index is not None
                else "Device: system default"
            ),
            "Debug: on" if CONFIG.debug else "Debug: off",
        ):
            chip = QLabel(text)
            chip.setObjectName("Chip")
            chips.addWidget(chip)
        chips.addStretch()
        layout.addLayout(chips)

        layout.addStretch()


class PlaceholderPage(QWidget):
    """A module placeholder: title, badge, description and planned features."""

    def __init__(
        self,
        title: str,
        description: str,
        features: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 36, 48, 28)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("PageHeader")
        badge = QLabel("NOT IMPLEMENTED")
        badge.setObjectName("Badge")
        header.addWidget(title_label)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        header.addStretch()
        layout.addLayout(header)

        description_label = QLabel(description)
        description_label.setObjectName("PageDesc")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(4)
        for feature in features:
            item = QLabel(f"•  {feature}")
            item.setObjectName("FeatureItem")
            card_layout.addWidget(item)
        layout.addWidget(card)

        layout.addStretch()

        watermark = LogoLabel(170)
        effect = QGraphicsOpacityEffect(watermark)
        effect.setOpacity(0.07)
        watermark.setGraphicsEffect(effect)
        layout.addWidget(
            watermark,
            alignment=(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
            ),
        )
