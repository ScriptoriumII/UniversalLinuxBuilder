import sys
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QFormLayout, QHBoxLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QLabel, QListWidget,
    QTextEdit, QCheckBox, QFileDialog, QMessageBox
)

FAMILIES = {
    "Debian / Ubuntu": ["Debian", "Ubuntu"],
    "Fedora / Rocky Linux": ["Fedora", "Rocky Linux"],
    "Slackware / Salix": ["Slackware", "Salix"],
    "Gentoo": ["Gentoo"],
    "Arch Linux": ["Arch Linux"]
}

CATALOG = {
    "firefox-esr": "navigateur web internet firefox",
    "firefox": "navigateur web internet",
    "chromium": "navigateur web internet",
    "falkon": "navigateur léger web",
    "vlc": "vidéo musique multimédia",
    "mpv": "vidéo lecteur léger",
    "libreoffice": "bureautique traitement texte tableur",
    "abiword": "traitement texte léger",
    "gimp": "retouche photo image",
    "krita": "dessin peinture",
    "thunderbird": "messagerie email",
    "gparted": "partition disque",
    "geany": "éditeur code développement",
    "git": "développement",
    "htop": "moniteur système"
}

VALID_PACKAGE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,99}$")


def linux_command(args, timeout=60):
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            raise RuntimeError("WSL introuvable.")
        args = ["wsl.exe", "--exec"] + args
    elif sys.platform != "linux":
        raise RuntimeError("Un environnement Linux est nécessaire.")

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def release_info(text):
    result = {}
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value.strip().strip('"')
    return result


class Worker(QThread):
    completed = Signal(str, object)

    def __init__(self, action, distro, version, query, packages, mode):
        super().__init__()
        self.action = action
        self.distro = distro
        self.version = version
        self.query = query
        self.packages = packages
        self.mode = mode

    def run(self):
        try:
            if self.distro not in ("Debian", "Ubuntu"):
                raise RuntimeError(
                    "Moteur APT disponible uniquement pour Debian/Ubuntu."
                )

            info = linux_command(
                ["cat", "/etc/os-release"], 15
            )

            if info.returncode:
                raise RuntimeError("Impossible d'identifier Linux.")

            release = release_info(info.stdout)

            if release.get("ID", "").lower() != self.distro.lower():
                raise RuntimeError(
                    "La distribution WSL/Linux ne correspond pas "
                    "à la distribution sélectionnée."
                )

            if self.version.strip() and self.version.strip() not in (
                release.get("VERSION_ID", ""),
                release.get("VERSION_CODENAME", ""),
                release.get("UBUNTU_CODENAME", "")
            ):
                raise RuntimeError(
                    "La version WSL/Linux ne correspond pas "
                    "à la version du projet."
                )

            if self.action == "search":
                if not self.query or len(self.query) > 80:
                    raise RuntimeError("Recherche invalide.")

                if any(ord(c) < 32 for c in self.query):
                    raise RuntimeError("Caractères non autorisés.")

                result = linux_command(
                    ["apt-cache", "search", "--", self.query]
                )

                if result.returncode:
                    raise RuntimeError(result.stderr)

                packages = []

                for line in result.stdout.splitlines():
                    if " - " in line:
                        name, description = line.split(" - ", 1)

                        if VALID_PACKAGE.fullmatch(name):
                            packages.append((name, description))

                    if len(packages) >= 200:
                        break

                self.completed.emit("search", packages)
                return

            if not self.packages:
                raise RuntimeError("Aucun paquet sélectionné.")

            if len(self.packages) > 150:
                raise RuntimeError("Trop de paquets sélectionnés.")

            if not all(
                VALID_PACKAGE.fullmatch(p) for p in self.packages
            ):
                raise RuntimeError("Nom de paquet invalide.")

            command = ["apt-get", "-s"]

            if self.mode != "Standard":
                command.append("--no-install-recommends")

            command += ["install", "--"] + self.packages

            result = linux_command(command, 120)

            if result.returncode:
                raise RuntimeError(
                    (result.stderr or result.stdout)[-3000:]
                )

            installs = [
                line for line in result.stdout.splitlines()
                if line.startswith("Inst ")
            ]

            removals = [
                line for line in result.stdout.splitlines()
                if line.startswith("Remv ")
            ]

            report = {
                "distribution": release.get("PRETTY_NAME", ""),
                "applications": self.packages,
                "optimization": self.mode,
                "installation_actions": len(installs),
                "removal_actions": len(removals),
                "simulation": result.stdout,
                "warning": (
                    "Simulation sur le système WSL/Linux existant. "
                    "Les paquets déjà installés ne sont pas comptés. "
                    "Ce rapport ne constitue pas une liste complète "
                    "des dépendances d'une ISO minimale."
                )
            }

            self.completed.emit("analysis", report)

        except Exception as exc:
            self.completed.emit("error", str(exc))


class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Universal Linux Builder v0.3")
        self.resize(1050, 750)

        self.worker = None
        self.last_report = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.distribution_page()
        self.system_page()
        self.applications_page()
        self.optimization_page()
        self.project_page()

        self.tabs.currentChanged.connect(self.tab_changed)

        self.setStyleSheet("""
            QWidget {
                background: #172131;
                color: #edf3fc;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QListWidget, QTextEdit {
                background: #27374c;
                border: 1px solid #51647c;
                border-radius: 6px;
                padding: 7px;
            }
            QPushButton {
                background: #2477b9;
                border-radius: 6px;
                padding: 9px;
            }
            QPushButton:hover {
                background: #398fd0;
            }
            QTabBar::tab {
                padding: 12px;
            }
        """)

        self.statusBar().showMessage(
            "Version 0.3 - Génération ISO non disponible"
        )

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, title)
        return layout

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def distribution_page(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.family = self.combo(list(FAMILIES))
        self.distro = self.combo(FAMILIES[self.family.currentText()])
        self.arch = self.combo(["x86_64", "aarch64"])
        self.version = QLineEdit()

        self.version.setPlaceholderText(
            "Version cible (facultatif)"
        )

        self.family.currentTextChanged.connect(
            self.change_family
        )

        form.addRow("Famille Linux", self.family)
        form.addRow("Distribution", self.distro)
        form.addRow("Architecture", self.arch)
        form.addRow("Version", self.version)

        layout.addLayout(form)
        layout.addStretch()

    def change_family(self, family):
        self.distro.clear()
        self.distro.addItems(FAMILIES[family])
        self.last_report = None

    def system_page(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo([
            "Aucun", "GNOME", "KDE Plasma",
            "Xfce", "Budgie", "LXQt"
        ])

        self.display = self.combo([
            "Automatique", "Wayland", "X11"
        ])

        self.audio = self.combo([
            "PipeWire", "PulseAudio", "ALSA", "Aucun"
        ])

        self.network = self.combo([
            "NetworkManager",
            "systemd-networkd",
            "Manuel"
        ])

        self.init = self.combo([
            "Par défaut", "systemd",
            "OpenRC", "Init traditionnel"
        ])

        form.addRow("Bureau", self.desktop)
        form.addRow("Affichage", self.display)
        form.addRow("Audio", self.audio)
        form.addRow("Réseau", self.network)
        form.addRow("Initialisation", self.init)

        layout.addLayout(form)

        self.flags = {}

        for key, title, checked in [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", False),
            ("printing", "Impression", False),
            ("calamares", "Installateur Calamares", False)
        ]:
            box = QCheckBox(title)
            box.setChecked(checked)
            self.flags[key] = box
            layout.addWidget(box)

        layout.addStretch()

    def applications_page(self):
        layout = self.page("Applications")

        layout.addWidget(QLabel("Recherche intelligente locale"))

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Navigateur, vidéo, bureautique..."
        )

        self.search.textChanged.connect(self.local_search)

        self.local_results = QListWidget()
        self.local_results.itemDoubleClicked.connect(
            lambda item: self.add_package(item.text())
        )

        layout.addWidget(self.search)
        layout.addWidget(self.local_results)

        row = QHBoxLayout()

        self.repo_query = QLineEdit()
        self.repo_query.setPlaceholderText(
            "Rechercher dans les dépôts APT"
        )

        self.repo_button = QPushButton("Rechercher")
        self.repo_button.clicked.connect(self.repo_search)

        row.addWidget(self.repo_query)
        row.addWidget(self.repo_button)
        layout.addLayout(row)

        layout.addWidget(QLabel(
            "Résultats des dépôts - double-clic pour ajouter"
        ))

        self.repo_results = QListWidget()
        self.repo_results.itemDoubleClicked.connect(
            self.add_repo_package
        )

        layout.addWidget(self.repo_results)

        layout.addWidget(QLabel(
            "Paquets sélectionnés - double-clic pour retirer"
        ))

        self.selected = QListWidget()
        self.selected.itemDoubleClicked.connect(
            self.remove_package
        )

        layout.addWidget(self.selected)

        self.local_search()

    def local_search(self):
        self.local_results.clear()

        words = self.search.text().casefold().split()

        for name, description in CATALOG.items():
            text = (name + " " + description).casefold()

            if all(word in text for word in words):
                self.local_results.addItem(name)

    def package_list(self):
        return [
            self.selected.item(i).text()
            for i in range(self.selected.count())
        ]

    def add_package(self, name):
        if not VALID_PACKAGE.fullmatch(name):
            return

        if name not in self.package_list():
            self.selected.addItem(name)
            self.last_report = None

    def add_repo_package(self, item):
        name = item.data(256)
        if isinstance(name, str):
            self.add_package(name)

    def remove_package(self, item):
        self.selected.takeItem(self.selected.row(item))
        self.last_report = None

    def start_worker(self, action):
        if self.worker and self.worker.isRunning():
            return

        self.repo_button.setEnabled(False)
        self.analyze_button.setEnabled(False)

        self.worker = Worker(
            action,
            self.distro.currentText(),
            self.version.text(),
            self.repo_query.text().strip(),
            self.package_list(),
            self.profile.currentText()
        )

        self.worker.completed.connect(self.worker_result)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def worker_finished(self):
        self.repo_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

    def repo_search(self):
        self.repo_results.clear()
        self.start_worker("search")

    def worker_result(self, status, data):
        if status == "error":
            QMessageBox.warning(
                self, "Erreur", str(data)
            )
            return

        if status == "search":
            for name, description in data:
                self.repo_results.addItem(
                    f"{name} - {description[:100]}"
                )

                item = self.repo_results.item(
                    self.repo_results.count() - 1
                )

                item.setData(256, name)

            self.statusBar().showMessage(
                f"{len(data)} résultat(s) trouvé(s)"
            )
            return

        if status == "analysis":
            self.last_report = data

            self.analysis.setPlainText(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                )
            )

            self.tabs.setCurrentIndex(3)

    def optimization_page(self):
        layout = self.page("Optimisation")

        self.profile = self.combo([
            "Standard",
            "Minimal",
            "Ultra-minimal"
        ])

        layout.addWidget(QLabel("Profil d'optimisation"))
        layout.addWidget(self.profile)

        layout.addWidget(QLabel(
            "Standard : comportement APT habituel.\n"
            "Minimal / Ultra-minimal : sans recommandations.\n"
            "Les dépendances obligatoires restent conservées."
        ))

        self.analyze_button = QPushButton(
            "Analyser les dépendances APT"
        )

        self.analyze_button.clicked.connect(
            lambda: self.start_worker("analysis")
        )

        layout.addWidget(self.analyze_button)

        self.analysis = QTextEdit()
        self.analysis.setReadOnly(True)

        layout.addWidget(self.analysis)

    def config(self):
        data = {
            "schema": 3,
            "family": self.family.currentText(),
            "distribution": self.distro.currentText(),
            "architecture": self.arch.currentText(),
            "version": self.version.text(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "network": self.network.currentText(),
            "init": self.init.currentText(),
            "optimization": self.profile.currentText(),
            "applications": self.package_list()
        }

        for key, box in self.flags.items():
            data[key] = box.isChecked()

        return data

    def project_page(self):
        layout = self.page("Projet")

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        layout.addWidget(self.summary)

        row = QHBoxLayout()

        for title, action in [
            ("Actualiser", self.refresh),
            ("Enregistrer JSON", self.save),
            ("Ouvrir JSON", self.load),
            ("Exporter rapport", self.export_report)
        ]:
            button = QPushButton(title)
            button.clicked.connect(action)
            row.addWidget(button)

        layout.addLayout(row)

    def tab_changed(self, index):
        if index == 4:
            self.refresh()

    def refresh(self):
        text = json.dumps(
            self.config(),
            indent=2,
            ensure_ascii=False
        )

        text += (
            "\n\nAVERTISSEMENTS :\n"
            "- Compatibilité complète non vérifiée.\n"
            "- Composants Live non résolus.\n"
            "- Taille ISO non calculée.\n"
        )

        if self.last_report:
            text += "\n\nDERNIÈRE ANALYSE :\n"
            text += json.dumps(
                self.last_report,
                indent=2,
                ensure_ascii=False
            )

        self.summary.setPlainText(text)

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer", "distribution.json",
            "JSON (*.json)"
        )

        if filename:
            try:
                Path(filename).write_text(
                    json.dumps(
                        self.config(),
                        indent=2,
                        ensure_ascii=False
                    ),
                    encoding="utf-8"
                )
            except OSError as exc:
                QMessageBox.critical(
                    self, "Erreur", str(exc)
                )

    def load(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir", "", "JSON (*.json)"
        )

        if not filename:
            return

        try:
            data = json.loads(
                Path(filename).read_text(encoding="utf-8")
            )

            family = data.get("family")
            distro = data.get("distribution")

            if family not in FAMILIES:
                raise ValueError("Famille inconnue.")

            if distro not in FAMILIES[family]:
                raise ValueError("Distribution incompatible.")

            self.family.setCurrentText(family)
            self.distro.setCurrentText(distro)

            fields = [
                ("architecture", self.arch),
                ("desktop", self.desktop),
                ("display", self.display),
                ("audio", self.audio),
                ("network", self.network),
                ("init", self.init),
                ("optimization", self.profile)
            ]

            for key, control in fields:
                value = data.get(key)

                if isinstance(value, str):
                    if control.findText(value) >= 0:
                        control.setCurrentText(value)

            self.version.setText(
                str(data.get("version", ""))
            )

            for key, box in self.flags.items():
                if isinstance(data.get(key), bool):
                    box.setChecked(data[key])

            self.selected.clear()

            apps = data.get("applications", [])

            if not isinstance(apps, list):
                raise ValueError("Liste de paquets invalide.")

            for name in apps[:150]:
                if isinstance(name, str):
                    self.add_package(name)

            self.last_report = None
            self.refresh()

        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(
                self, "Erreur", str(exc)
            )

    def export_report(self):
        self.refresh()

        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter rapport", "rapport.txt",
            "Texte (*.txt)"
        )

        if filename:
            try:
                Path(filename).write_text(
                    self.summary.toPlainText(),
                    encoding="utf-8"
                )
            except OSError as exc:
                QMessageBox.critical(
                    self, "Erreur", str(exc)
                )


app = QApplication(sys.argv)
app.setStyle("Fusion")

window = Window()
window.show()

sys.exit(app.exec())
