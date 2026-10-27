from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from pathlib import Path

from .constants import COLORS, LOGOS
from .theme import PALETTES

PALETTES_LIGHT_SLACKWARE = PALETTES["light"]["slackware"]


ASSETS = Path(__file__).resolve().parent / "assets" / "logos"

# Thème courant (« dark » ou « light ») : le logo Slackware, gris clair,
# serait invisible sur fond clair.
_mode = {"value": "dark"}


def set_mode(mode):
    _mode["value"] = "light" if mode == "light" else "dark"


def logo(family, size=36):
    """Logo officiel (Simple Icons, CC0) embarqué dans ulb/assets/logos.

    Aucun accès réseau. Si le fichier manque, une pastille colorée
    avec l'initiale est dessinée."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    filename = ASSETS / (LOGOS[family] + ".svg")

    if filename.exists():
        data = filename.read_bytes()

        if _mode["value"] == "light":
            data = data.replace(
                b"#D0D7E2",
                PALETTES_LIGHT_SLACKWARE.encode()
            )

        renderer = QSvgRenderer(data)

        if renderer.isValid():
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )
    painter.setBrush(QColor(COLORS[family]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)

    painter.setPen(QColor("#10151D"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(max(8, int(size * 0.5)))
    painter.setFont(font)
    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        family[0]
    )
    painter.end()

    return pixmap
