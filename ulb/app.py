import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui import UniversalLinuxBuilder


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = UniversalLinuxBuilder()
    window.show()
    QTimer.singleShot(2500, window.startup_update_check)

    return app.exec()
