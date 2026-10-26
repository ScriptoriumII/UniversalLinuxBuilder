import sys

from PySide6.QtWidgets import QApplication

from .ui import UniversalLinuxBuilder


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = UniversalLinuxBuilder()
    window.show()

    return app.exec()
