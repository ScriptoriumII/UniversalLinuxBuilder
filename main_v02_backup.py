import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

FAMILIES = {
    "Debian / Ubuntu": ["Debian", "Ubuntu"],
    "Fedora / Rocky Linux": ["Fedora", "Rocky Linux"],
    "Slackware / Salix": ["Slackware", "Salix"],
    "Gentoo": ["Gentoo"],
    "Arch Linux": ["Arch Linux"]
}

CATALOG = {
    "Firefox": "navigateur internet web browser",
    "Chromium": "navigateur internet web browser",
    "Falkon": "navigateur léger internet browser",
    "VLC": "lecteur vidéo musique multimédia",
    "MPV": "lecteur vidéo léger multimédia",
    "LibreOffice": "bureautique traitement texte tableur",
    "AbiWord": "traitement texte bureautique léger",
    "GIMP": "retouche photo image",
    "Krita": "dessin peinture image",
    "Thunderbird": "messagerie email courriel",
    "GParted": "partition disque système",
    "Geany": "éditeur code développement",
    "Git": "développement versionnement",
    "htop": "moniteur système processus"
}


def os_release(text):
    result = {}

    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value.strip().strip('"')

    return result


def linux_command(distro, query):
    if distro in ("Debian", "Ubuntu"):
        return ["apt-cache", "search", "--", query]

    if distro in ("Fedora", "Rocky Linux"):
        return ["dnf", "search", query]

    if distro in ("Slackware", "Salix"):
        return ["slapt-get", "--search", query]

    if distro == "Gentoo":
        return ["emerge", "--search", query]

    return ["pacman", "-Ss", query]


def distro_matches(distro, data):
    primary = data.get("ID", "").lower()

    mapping = {
        "Debian": {"debian"},
        "Ubuntu": {"ubuntu"},
        "Fedora": {"fedora"},
        "Rocky Linux": {"rocky"},
        "Slackware": {"slackware"},
        "Salix": {"salix"},
        "Gentoo": {"gentoo"},
        "Arch Linux": {"arch"}
    }

    return primary in mapping[distro]


class RepoWorker(QThread):

    finished_search = Signal(str, str)

    def __init__(self, distro, query):
        super().__init__()

        self.distro = distro
        self.query = query

    def run(self):
        try:
            if os.name == "nt":
                if not shutil.which("wsl.exe"):
                    raise RuntimeError(
                        "WSL introuvable. Installer WSL2 et une distribution Linux."
                    )

                prefix = ["wsl.exe", "--exec"]

            elif sys.platform.startswith("linux"):
                prefix = []

            else:
                raise RuntimeError(
                    "Sous macOS, un moteur Linux dans une VM est nécessaire."
                )

            ident = subprocess.run(
                prefix + ["cat", "/etc/os-release"],
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace"
            )

            if ident.returncode != 0:
                raise RuntimeError(
                    "Impossible d'identifier la distribution Linux."
                )

            actual = os_release(ident.stdout)

            if not distro_matches(self.distro, actual):
                raise RuntimeError(
                    "La distribution Linux utilisée ne correspond pas "
                    "à celle sélectionnée dans le projet.\n\n"
                    "Distribution détectée : {}\n"
                    "Distribution sélectionnée : {}".format(
                        actual.get("PRETTY_NAME", "inconnue"),
                        self.distro
                    )
                )

            command = linux_command(self.distro, self.query)

            result = subprocess.run(
                prefix + command,
                capture_output=True,
                text=True,
                timeout=40,
                encoding="utf-8",
                errors="replace"
            )

            if result.returncode not in (0, 1):
                raise RuntimeError(
                    (result.stderr or result.stdout or
                     "Erreur du gestionnaire de paquets")[:700]
                )

            output = result.stdout.strip()

            self.finished_search.emit(
                "ok",
                output[:18000] or
                "Aucun résultat retourné par les dépôts configurés."
            )

        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            self.finished_search.emit("error", str(exc))


class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Universal Linux Builder - v0.2")
        self.resize(1050, 740)

        self.worker = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_apps()
        self.make_project()

        self.setStyleSheet("""
            QWidget {
                background: #151d2a;
                color: #eaf0f8;
                font-size: 13px;
            }

            QLineEdit, QComboBox, QListWidget, QTextEdit {
                background: #233147;
                border: 1px solid #41516a;
                padding: 7px;
                border-radius: 6px;
            }

            QPushButton {
                background: #2477ba;
                padding: 9px;
                border-radius: 6px;
            }

            QPushButton:hover {
                background: #3694d4;
            }

            QTabBar::tab {
                padding: 12px 18px;
            }
        """)

        self.statusBar().showMessage(
            "Version 0.2 - Construction ISO non disponible"
        )

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setSpacing(12)
        self.tabs.addTab(widget, name)

        return layout

    @staticmethod
    def dropdown(items):
        widget = QComboBox()
        widget.addItems(items)
        return widget

    def make_distribution(self):
        layout = self.page("Distribution")

        layout.addWidget(
            QLabel("Famille et distribution Linux")
        )

        form = QFormLayout()

        self.family = self.dropdown(list(FAMILIES))

        self.distro = self.dropdown(
            FAMILIES[self.family.currentText()]
        )

        self.family.currentTextChanged.connect(
            self.family_changed
        )

        self.arch = self.dropdown([
            "x86_64",
            "aarch64"
        ])

        self.version = QLineEdit()
        self.version.setPlaceholderText(
            "Version de la distribution"
        )

        form.addRow("Famille", self.family)
        form.addRow("Distribution", self.distro)
        form.addRow("Architecture", self.arch)
        form.addRow("Version", self.version)

        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Les dépôts interrogés doivent correspondre "
            "à la distribution sélectionnée."
        ))

        layout.addStretch()

    def family_changed(self, family):
        self.distro.clear()
        self.distro.addItems(FAMILIES[family])

    def make_system(self):
        layout = self.page("Système")

        form = QFormLayout()

        self.desktop = self.dropdown([
            "Aucun",
            "GNOME",
            "KDE Plasma",
            "Xfce",
            "Budgie",
            "LXQt"
        ])

        self.display = self.dropdown([
            "Automatique",
            "Wayland",
            "X11"
        ])

        self.audio = self.dropdown([
            "PipeWire",
            "PulseAudio",
            "ALSA",
            "Aucun"
        ])

        self.network = self.dropdown([
            "NetworkManager",
            "systemd-networkd",
            "Manuel"
        ])

        self.init = self.dropdown([
            "Par défaut",
            "systemd",
            "OpenRC",
            "Init traditionnel"
        ])

        form.addRow("Bureau", self.desktop)
        form.addRow("Affichage", self.display)
        form.addRow("Audio", self.audio)
        form.addRow("Réseau", self.network)
        form.addRow("Initialisation", self.init)

        layout.addLayout(form)

        self.flags = {}

        options = [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", False),
            ("printing", "Impression", False),
            ("calamares", "Installateur Calamares", False)
        ]

        for key, title, checked in options:
            box = QCheckBox(title)
            box.setChecked(checked)

            self.flags[key] = box
            layout.addWidget(box)

        layout.addWidget(QLabel(
            "La validation complète des compatibilités "
            "sera ajoutée dans une prochaine version."
        ))

        layout.addStretch()

    def make_apps(self):
        layout = self.page("Applications")

        layout.addWidget(QLabel(
            "Recherche intelligente locale"
        ))

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Navigateur, vidéo, traitement texte..."
        )

        self.search.textChanged.connect(
            self.local_search
        )

        self.results = QListWidget()

        self.results.itemDoubleClicked.connect(
            self.add_app
        )

        self.selected = QListWidget()

        self.selected.itemDoubleClicked.connect(
            self.remove_app
        )

        layout.addWidget(self.search)

        layout.addWidget(QLabel(
            "Catalogue local - Double-clic pour ajouter"
        ))

        layout.addWidget(self.results)

        layout.addWidget(QLabel(
            "Applications sélectionnées - Double-clic pour retirer"
        ))

        layout.addWidget(self.selected)

        row = QHBoxLayout()

        self.repo_query = QLineEdit()

        self.repo_query.setPlaceholderText(
            "Rechercher dans les dépôts Linux"
        )

        self.repo_button = QPushButton(
            "Rechercher dans les dépôts"
        )

        self.repo_button.clicked.connect(
            self.repo_search
        )

        row.addWidget(self.repo_query)
        row.addWidget(self.repo_button)

        layout.addLayout(row)

        self.repo_output = QTextEdit()
        self.repo_output.setReadOnly(True)

        self.repo_output.setPlaceholderText(
            "Résultats du gestionnaire de paquets Linux"
        )

        layout.addWidget(self.repo_output)

        self.local_search()

    def local_search(self):
        query = self.search.text().casefold().split()

        self.results.clear()

        for name, tags in CATALOG.items():
            haystack = (name + " " + tags).casefold()

            if all(word in haystack for word in query):
                self.results.addItem(name)

    def add_app(self, item):
        name = item.text()

        existing = [
            self.selected.item(i).text()
            for i in range(self.selected.count())
        ]

        if name not in existing:
            self.selected.addItem(name)

    def remove_app(self, item):
        self.selected.takeItem(
            self.selected.row(item)
        )

    def repo_search(self):
        query = self.repo_query.text().strip()

        if (
            not query
            or len(query) > 80
            or any(ord(c) < 32 for c in query)
        ):
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir un terme de recherche de 1 à 80 caractères."
            )
            return

        self.repo_output.setPlainText(
            "Recherche en cours..."
        )

        self.repo_button.setEnabled(False)

        self.worker = RepoWorker(
            self.distro.currentText(),
            query
        )

        self.worker.finished_search.connect(
            self.repo_done
        )

        self.worker.start()

    def repo_done(self, status, result):
        if status == "ok":
            self.repo_output.setPlainText(
                "Résultats des dépôts :\n\n" + result
            )
        else:
            self.repo_output.setPlainText(
                "Erreur :\n\n" + result
            )

        self.repo_button.setEnabled(True)

    def config(self):
        data = {
            "schema": 2,
            "family": self.family.currentText(),
            "distribution": self.distro.currentText(),
            "architecture": self.arch.currentText(),
            "version": self.version.text(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "network": self.network.currentText(),
            "init": self.init.currentText(),
            "applications": [
                self.selected.item(i).text()
                for i in range(self.selected.count())
            ]
        }

        data.update({
            key: widget.isChecked()
            for key, widget in self.flags.items()
        })

        return data

    def make_project(self):
        layout = self.page("Projet")

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)

        layout.addWidget(self.summary)

        row = QHBoxLayout()

        actions = [
            ("Actualiser", self.refresh),
            ("Enregistrer JSON", self.save),
            ("Ouvrir JSON", self.load)
        ]

        for title, handler in actions:
            button = QPushButton(title)
            button.clicked.connect(handler)
            row.addWidget(button)

        layout.addLayout(row)

        layout.addWidget(QLabel(
            "La résolution des dépendances et "
            "la génération ISO ne sont pas encore disponibles."
        ))

        self.tabs.currentChanged.connect(
            lambda idx: self.refresh()
            if idx == 3 else None
        )

    def refresh(self):
        self.summary.setPlainText(
            json.dumps(
                self.config(),
                ensure_ascii=False,
                indent=2
            )
        )

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer",
            "distribution.json",
            "JSON (*.json)"
        )

        if filename:
            try:
                Path(filename).write_text(
                    json.dumps(
                        self.config(),
                        ensure_ascii=False,
                        indent=2
                    ),
                    encoding="utf-8"
                )

                self.statusBar().showMessage(
                    "Projet enregistré : " + filename
                )

            except OSError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur d'enregistrement",
                    str(exc)
                )

    def load(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir",
            "",
            "JSON (*.json)"
        )

        if not filename:
            return

        try:
            data = json.loads(
                Path(filename).read_text(
                    encoding="utf-8"
                )
            )

            if (
                not isinstance(data, dict)
                or data.get("family") not in FAMILIES
            ):
                raise ValueError(
                    "Famille Linux inconnue."
                )

            if data.get("distribution") not in FAMILIES[data["family"]]:
                raise ValueError(
                    "Distribution incompatible avec la famille."
                )

            self.family.setCurrentText(
                data["family"]
            )

            self.distro.setCurrentText(
                data["distribution"]
            )

            fields = [
                ("architecture", self.arch),
                ("desktop", self.desktop),
                ("display", self.display),
                ("audio", self.audio),
                ("network", self.network),
                ("init", self.init)
            ]

            for key, widget in fields:
                if isinstance(data.get(key), str):
                    widget.setCurrentText(data[key])

            self.version.setText(
                str(data.get("version", ""))
            )

            for key, widget in self.flags.items():
                widget.setChecked(
                    data.get(
                        key,
                        widget.isChecked()
                    ) is True
                )

            self.selected.clear()

            for app in data.get("applications", []):
                if isinstance(app, str):
                    existing = [
                        self.selected.item(i).text()
                        for i in range(self.selected.count())
                    ]

                    if app not in existing:
                        self.selected.addItem(app)

            self.refresh()

            self.statusBar().showMessage(
                "Projet ouvert : " + filename
            )

        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError
        ) as exc:
            QMessageBox.critical(
                self,
                "Erreur de chargement",
                str(exc)
            )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
