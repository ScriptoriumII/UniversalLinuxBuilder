import urllib.request

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

import os

from .constants import COLORS, LOGOS, VERSION, cache_dir


def logo(family, size=36):
    """Logo depuis le cache local, sans accès réseau.

    Sans fichier en cache (premier démarrage, hors ligne), un pastille
    colorée avec l'initiale est dessinée ; fetch_missing_logos() remplit
    le cache en arrière-plan.
    """

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    filename = cache_dir() / (LOGOS[family] + ".svg")

    if filename.exists():
        renderer = QSvgRenderer(str(filename))

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


def fetch_missing_logos():
    """Télécharge les logos absents du cache. Retourne le nombre
    de fichiers obtenus ; s'arrête au premier échec réseau."""

    if os.environ.get("ULB_OFFLINE"):
        return 0

    cache_dir().mkdir(parents=True, exist_ok=True)
    fetched = 0

    for family, identifier in LOGOS.items():
        filename = cache_dir() / (identifier + ".svg")

        if filename.exists():
            continue

        url = (
            "https://cdn.simpleicons.org/"
            + identifier
            + "/"
            + COLORS[family].replace("#", "")
        )

        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "UniversalLinuxBuilder/" + VERSION
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=2
            ) as response:
                data = response.read(200000)

        except Exception:
            break

        if b"<svg" in data[:1000]:
            filename.write_bytes(data)
            fetched += 1

    return fetched
