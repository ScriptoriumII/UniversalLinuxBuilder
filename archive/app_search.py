import os
import re
import sys
import shutil
import subprocess
import unicodedata

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QMessageBox
)

DISTROS = [
    "Debian", "Ubuntu", "Fedora", "Rocky Linux",
    "Slackware", "Salix", "Gentoo", "Arch Linux"
]

IDS = {
    "Debian": "debian",
    "Ubuntu": "ubuntu",
    "Fedora": "fedora",
    "Rocky Linux": "rocky",
    "Slackware": "slackware",
    "Salix": "salix",
    "Gentoo": "gentoo",
    "Arch Linux": "arch"
}

ALIASES = {
    "navigateur": "firefox chromium browser web",
    "internet": "browser web firefox",
    "video": "vlc mpv video player",
    "musique": "audio music player",
    "bureautique": "libreoffice office writer",
    "traitement texte": "writer abiword office",
    "photo": "gimp krita image editor",
    "dessin": "krita inkscape graphics",
    "developpement": "git geany code editor",
    "messagerie": "thunderbird mail email",
    "partition": "gparted partition disk",
    "systeme": "htop monitor system"
}


def normalize(value):
    return "".join(
        c for c in unicodedata.normalize(
            "NFKD", value.casefold()
        )
        if not unicodedata.combining(c)
    )


def expand_query(query):
    query = normalize(query.strip())

    for key, value in ALIASES.items():
        if key in query:
            return value.split()[:5]

    return [query]


def command_for(distro, term):
    if distro in ("Debian", "Ubuntu"):
        return ["apt-cache", "search", "--", term]

    if distro in ("Fedora", "Rocky Linux"):
        return ["dnf", "search", term]

    if distro in ("Slackware", "Salix"):
        return ["slapt-get", "--search", term]

    if distro == "Gentoo":
        return ["emerge", "--search", term]

    return ["pacman", "-Ss", term]


def parse_results(distro, output):
    results = {}
    lines = output.splitlines()

    if distro in ("Debian", "Ubuntu"):
        for line in lines:
            match = re.match(
                r"^([a-z0-9][a-z0-9+.-]*)\s+-\s+(.+)$",
                line
            )

            if match:
                results[match.group(1)] = match.group(2)

    elif distro in ("Fedora", "Rocky Linux"):
        for line in lines:
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|aarch64|noarch|i686|src)"
                r"\s*:\s*(.+)$",
                line.strip()
            )

            if match:
                results[match.group(1)] = match.group(2)

    elif distro == "Arch Linux":
        current = None

        for line in lines:
            match = re.match(
                r"^([^\s/]+)/([^\s]+)\s+\S+",
                line
            )

            if match:
                current = match.group(2)
                results.setdefault(
                    current,
                    "Dépôt : " + match.group(1)
                )

            elif current and line.startswith("    "):
                results[current] = line.strip()

    elif distro in ("Slackware", "Salix"):
        for line in lines:
            match = re.match(
                r"^([\w+.-]+)-[0-9][^\s]*",
                line.strip()
            )

            if match:
                results.setdefault(
                    match.group(1),
                    line.strip()
                )

    else:
        for line in lines:
            match = re.search(
                r"\*\s+([\w+.-]+/[\w+.-]+)",
                line
            )

            if match:
                results.setdefault(
                    match.group(1),
                    "Paquet Portage"
                )

    return results


class SearchWorker(QThread):
    done = Signal(object, str)

    def __init__(self, distro, wsl_name, query):
        super().__init__()

        self.distro = distro
        self.wsl_name = wsl_name
        self.query = query

    def execute(self, command, timeout):
        if sys.platform == "win32":
            if not shutil.which("wsl.exe"):
                raise RuntimeError("WSL2 introuvable.")

            if not self.wsl_name.strip():
                raise RuntimeError(
                    "Indique le nom de la distribution WSL."
                )

            command = [
                "wsl.exe",
                "-d",
                self.wsl_name.strip(),
                "--exec"
            ] + command

        elif not sys.platform.startswith("linux"):
            raise RuntimeError(
                "Sous macOS, un moteur Linux est nécessaire."
            )

        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )

    def run(self):
        try:
            info = self.execute(
                ["cat", "/etc/os-release"],
                20
            )

            if info.returncode != 0:
                raise RuntimeError(
                    info.stderr.strip()
                    or "Identification Linux impossible."
                )

            match = re.search(
                r'^ID=["\']?([^\n"\']+)',
                info.stdout,
                re.M
            )

            actual = (
                match.group(1).strip().lower()
                if match else ""
            )

            if actual != IDS[self.distro]:
                raise RuntimeError(
                    f"Distribution détectée : {actual or 'inconnue'}\n"
                    f"Distribution attendue : {IDS[self.distro]}"
                )

            results = {}
            warnings = []

            for term in expand_query(self.query):
                process = self.execute(
                    command_for(self.distro, term),
                    70
                )

                if process.returncode not in (0, 1):
                    warnings.append(
                        (process.stderr or process.stdout)
                        .strip()[:250]
                    )
                    continue

                results.update(
                    parse_results(
                        self.distro,
                        process.stdout
                    )
                )

            message = (
                f"{len(results)} paquet(s) trouvé(s) "
                "dans les dépôts configurés."
            )

            if warnings:
                message += (
                    "\nAvertissement : "
                    + "; ".join(warnings[:2])
                )

            self.done.emit(
                sorted(results.items())[:300],
                message
            )

        except (
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired
        ) as error:
            self.done.emit(
                [],
                f"Erreur : {error}"
            )


class SearchWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder - Recherche v0.6"
        )
        self.resize(850, 620)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Recherche d'applications dans les dépôts Linux"
        ))

        row = QHBoxLayout()

        self.distro = QComboBox()
        self.distro.addItems(DISTROS)

        self.wsl = QLineEdit()
        self.wsl.setPlaceholderText(
            "Nom WSL sous Windows : Debian, Ubuntu..."
        )

        row.addWidget(self.distro)
        row.addWidget(self.wsl)

        layout.addLayout(row)

        search_row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Ex. navigateur, vlc, gimp..."
        )

        self.button = QPushButton("Rechercher")
        self.button.clicked.connect(self.search)

        search_row.addWidget(self.query)
        search_row.addWidget(self.button)

        layout.addLayout(search_row)

        layout.addWidget(QLabel(
            "Résultats - double-clic pour ajouter"
        ))

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self.add)

        layout.addWidget(self.results)

        layout.addWidget(QLabel(
            "Paquets sélectionnés - double-clic pour retirer"
        ))

        self.selected = QListWidget()
        self.selected.itemDoubleClicked.connect(self.remove)

        layout.addWidget(self.selected)

        self.status = QLabel(
            "Recherche réelle : dépôts Linux nécessaires."
        )

        layout.addWidget(self.status)

        self.worker = None

    def search(self):
        query = self.query.text().strip()

        if (
            not query
            or len(query) > 80
            or any(ord(c) < 32 for c in query)
        ):
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisis entre 1 et 80 caractères."
            )
            return

        self.button.setEnabled(False)
        self.results.clear()
        self.status.setText("Recherche en cours...")

        self.worker = SearchWorker(
            self.distro.currentText(),
            self.wsl.text(),
            query
        )

        self.worker.done.connect(self.show_results)

        self.worker.finished.connect(
            lambda: self.button.setEnabled(True)
        )

        self.worker.start()

    def show_results(self, packages, message):
        self.status.setText(message)

        for name, description in packages:
            item = QListWidgetItem(
                f"{name} - {description[:130]}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                name
            )

            self.results.addItem(item)

    def add(self, item):
        name = item.data(
            Qt.ItemDataRole.UserRole
        )

        current = {
            self.selected.item(i).text()
            for i in range(self.selected.count())
        }

        if name not in current:
            self.selected.addItem(name)

    def remove(self, item):
        self.selected.takeItem(
            self.selected.row(item)
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = SearchWindow()
    window.show()

    sys.exit(app.exec())
