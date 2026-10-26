import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QTextEdit, QCheckBox,
    QFileDialog, QMessageBox
)

VERSION = "0.6"

FAMILIES = {
    "Debian / Ubuntu": ["Debian", "Ubuntu"],
    "Fedora / Rocky Linux": ["Fedora", "Rocky Linux"],
    "Slackware / Salix": ["Slackware", "Salix"],
    "Gentoo": ["Gentoo"],
    "Arch Linux": ["Arch Linux"]
}

DISTRO_IDS = {
    "Debian": "debian",
    "Ubuntu": "ubuntu",
    "Fedora": "fedora",
    "Rocky Linux": "rocky",
    "Slackware": "slackware",
    "Salix": "salix",
    "Gentoo": "gentoo",
    "Arch Linux": "arch"
}

CATALOG = {
    "firefox": "navigateur internet web",
    "firefox-esr": "navigateur internet web",
    "chromium": "navigateur internet web",
    "falkon": "navigateur léger web",
    "vlc": "vidéo musique multimédia",
    "mpv": "vidéo lecteur léger",
    "libreoffice": "bureautique traitement texte",
    "abiword": "traitement texte léger",
    "gimp": "retouche photo image",
    "krita": "dessin peinture",
    "inkscape": "dessin vectoriel",
    "thunderbird": "messagerie email",
    "gparted": "partition disque",
    "geany": "éditeur code",
    "git": "développement",
    "htop": "surveillance système"
}

ALIASES = {
    "navigateur": ["firefox", "chromium", "browser"],
    "internet": ["firefox", "browser"],
    "video": ["vlc", "mpv"],
    "musique": ["audio", "music"],
    "bureautique": ["libreoffice", "office"],
    "traitement texte": ["abiword", "writer"],
    "photo": ["gimp", "image"],
    "dessin": ["krita", "inkscape"],
    "developpement": ["git", "geany"],
    "messagerie": ["thunderbird", "mail"],
    "partition": ["gparted"],
    "systeme": ["htop", "monitor"]
}

PACKAGE_PATTERN = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,99}$"
)

GENTOO_PATTERN = re.compile(
    r"^[a-zA-Z0-9+_.-]+/[a-zA-Z0-9+_.-]+$"
)


def normalize(value):
    return "".join(
        char
        for char in unicodedata.normalize(
            "NFKD", value.casefold()
        )
        if not unicodedata.combining(char)
    )


def search_terms(query):
    query_normalized = normalize(query.strip())

    for keyword, terms in ALIASES.items():
        if keyword in query_normalized:
            return terms

    return [query.strip()]


def search_command(distro, term):
    if distro in ("Debian", "Ubuntu"):
        return ["apt-cache", "search", "--", term]

    if distro in ("Fedora", "Rocky Linux"):
        return ["dnf", "search", term]

    if distro in ("Slackware", "Salix"):
        return ["slapt-get", "--search", term]

    if distro == "Gentoo":
        return ["emerge", "--search", term]

    if distro == "Arch Linux":
        return ["pacman", "-Ss", term]

    raise ValueError("Distribution inconnue")


def parse_search(distro, output):
    packages = {}
    current = None

    for line in output.splitlines():

        if distro in ("Debian", "Ubuntu"):
            if " - " in line:
                name, description = line.split(" - ", 1)

                if PACKAGE_PATTERN.fullmatch(name):
                    packages[name] = description

        elif distro in ("Fedora", "Rocky Linux"):
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|aarch64|noarch|i686|src)"
                r"\s*:\s*(.*)$",
                line.strip()
            )

            if match:
                packages[match.group(1)] = match.group(2)

        elif distro == "Arch Linux":
            match = re.match(
                r"^([^/\s]+)/([^\s]+)\s+\S+",
                line
            )

            if match:
                current = match.group(2)
                packages[current] = (
                    "Dépôt : " + match.group(1)
                )

            elif current and line.startswith("    "):
                packages[current] = line.strip()

        elif distro in ("Slackware", "Salix"):
            match = re.match(
                r"^([\w+.-]+)-[0-9][^\s]*",
                line.strip()
            )

            if match:
                packages[match.group(1)] = line.strip()

        elif distro == "Gentoo":
            match = re.search(
                r"\*\s+([\w+.-]+/[\w+.-]+)",
                line
            )

            if match:
                packages[match.group(1)] = (
                    "Paquet Portage"
                )

    return packages


def run_linux(args, timeout=60, stdin=None, wsl_name=""):
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            raise RuntimeError(
                "WSL est introuvable sur Windows."
            )

        command = ["wsl.exe"]

        if wsl_name:
            command += ["-d", wsl_name]

        command += ["--exec"] + args

    elif sys.platform.startswith("linux"):
        command = args

    else:
        raise RuntimeError(
            "Une machine virtuelle Linux est nécessaire "
            "sur macOS."
        )

    return subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def linux_info(wsl_name=""):
    result = run_linux(
        ["cat", "/etc/os-release"],
        timeout=15,
        wsl_name=wsl_name
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Impossible de détecter la distribution Linux."
        )

    values = {}

    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')

    return values


def valid_package(name, distro):
    if distro == "Gentoo":
        return bool(GENTOO_PATTERN.fullmatch(name))

    return bool(PACKAGE_PATTERN.fullmatch(name))


def build_packages(config):
    desktop = {
        "Aucun": [],
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "lightdm"],
        "LXQt": ["lxqt-core", "sddm"]
    }

    audio = {
        "PipeWire": ["pipewire", "wireplumber"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    }

    network = {
        "NetworkManager": ["network-manager"],
        "systemd-networkd": [],
        "Manuel": []
    }

    packages = [
        "live-boot",
        "live-config",
        "linux-image-amd64",
        "systemd-sysv"
    ]

    packages += desktop[config["desktop"]]
    packages += audio[config["audio"]]
    packages += network[config["network"]]

    if config["wifi"]:
        packages += [
            "wpasupplicant",
            "wireless-regdb"
        ]

    if config["bluetooth"]:
        packages.append("bluez")

    if config["printing"]:
        packages.append("cups")

    if config["calamares"]:
        packages.append("calamares")

    packages += config["applications"]

    return list(dict.fromkeys(packages))


BUILD_SCRIPT = r"""
set -eu

output="$1"
release="$2"
packages="$3"
profile="$4"

mkdir -p "$output"
cd "$output"

command -v lb >/dev/null || {
    echo "Installer live-build."
    exit 2
}

command -v sudo >/dev/null || {
    echo "sudo introuvable."
    exit 2
}

if ! sudo -n true 2>/dev/null; then
    echo "sudo non interactif indisponible."
    echo "La construction nécessite une autorisation sudo."
    exit 3
fi

mkdir -p config/package-lists

if [ "$profile" = "Standard" ]; then
    recommends=true
else
    recommends=false
fi

lb config \
    --distribution "$release" \
    --binary-images iso-hybrid \
    --architectures amd64 \
    --apt-recommends "$recommends"

printf '%s\n' "$packages" |
    tr ' ' '\n' \
    > config/package-lists/custom.list.chroot

sudo -n lb build

echo "Images ISO générées :"
find . -maxdepth 1 -name '*.iso' -type f
"""


class Worker(QThread):
    completed = Signal(str, object)

    def __init__(
        self,
        action,
        config,
        query="",
        target=""
    ):
        super().__init__()

        self.action = action
        self.config = config
        self.query = query
        self.target = target

    def run(self):
        try:
            config = self.config
            distro = config["distribution"]
            wsl = config["wsl_name"]

            info = linux_info(wsl)

            actual = info.get("ID", "").lower()

            if actual != DISTRO_IDS[distro]:
                raise RuntimeError(
                    "Distribution Linux incorrecte.\n"
                    f"Détectée : {actual}\n"
                    f"Attendue : {DISTRO_IDS[distro]}"
                )

            if self.action == "search":
                self.search(distro, wsl)

            elif self.action == "analyze":
                self.analyze(distro, wsl)

            elif self.action == "build":
                self.build(distro, wsl)

        except Exception as error:
            self.completed.emit(
                "error",
                str(error)
            )

    def search(self, distro, wsl):
        query = self.query.strip()

        if (
            not query
            or len(query) > 80
            or any(ord(c) < 32 for c in query)
        ):
            raise RuntimeError(
                "Recherche invalide."
            )

        packages = {}
        warnings = []

        for term in search_terms(query):
            result = run_linux(
                search_command(distro, term),
                timeout=70,
                wsl_name=wsl
            )

            if result.returncode not in (0, 1):
                warnings.append(
                    (result.stderr or result.stdout)[-300:]
                )
                continue

            packages.update(
                parse_search(
                    distro,
                    result.stdout
                )
            )

        self.completed.emit(
            "search",
            {
                "packages": sorted(
                    packages.items()
                )[:300],
                "warnings": warnings
            }
        )

    def analyze(self, distro, wsl):
        if distro not in ("Debian", "Ubuntu"):
            raise RuntimeError(
                "Simulation APT disponible uniquement "
                "pour Debian et Ubuntu."
            )

        packages = self.config["applications"]

        if not packages:
            raise RuntimeError(
                "Aucune application sélectionnée."
            )

        command = ["apt-get", "-s"]

        if self.config["optimization"] != "Standard":
            command.append("--no-install-recommends")

        command += ["install", "--"] + packages

        result = run_linux(
            command,
            timeout=120,
            wsl_name=wsl
        )

        if result.returncode != 0:
            raise RuntimeError(
                (result.stdout + result.stderr)[-3000:]
            )

        self.completed.emit(
            "analysis",
            {
                "simulation": result.stdout,
                "warning": (
                    "Simulation effectuée sur le Linux "
                    "existant, et non sur une base ISO vierge."
                )
            }
        )

    def build(self, distro, wsl):
        config = self.config

        if distro != "Debian":
            raise RuntimeError(
                "Construction ISO disponible "
                "uniquement pour Debian."
            )

        if config["architecture"] != "amd64":
            raise RuntimeError(
                "Architecture non prise en charge."
            )

        if config["init"] not in (
            "Par défaut", "systemd"
        ):
            raise RuntimeError(
                "Le moteur Debian utilise systemd."
            )

        release = config["version"].strip()

        if not re.fullmatch(
            r"[a-z][a-z0-9-]{1,39}",
            release
        ):
            raise RuntimeError(
                "Version Debian invalide. "
                "Exemple : trixie."
            )

        target = self.target

        if not target:
            raise RuntimeError(
                "Choisir un dossier de construction."
            )

        if os.name == "nt":
            conversion = run_linux(
                ["wslpath", "-a", target],
                timeout=15,
                wsl_name=wsl
            )

            if conversion.returncode != 0:
                raise RuntimeError(
                    "Conversion du chemin Windows impossible."
                )

            target = conversion.stdout.strip()

        packages = build_packages(config)

        command = [
            "bash",
            "-s",
            "--",
            target,
            release,
            " ".join(packages),
            config["optimization"]
        ]

        result = run_linux(
            command,
            timeout=7200,
            stdin=BUILD_SCRIPT,
            wsl_name=wsl
        )

        self.completed.emit(
            "build",
            {
                "returncode": result.returncode,
                "log": (
                    result.stdout + "\n" + result.stderr
                )[-100000:]
            }
        )


class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v0.6"
        )

        self.resize(1100, 780)

        self.worker = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_applications()
        self.make_optimization()
        self.make_builder()
        self.make_project()

        self.tabs.currentChanged.connect(
            self.tab_changed
        )

        self.setStyleSheet("""
            QWidget {
                background: #172131;
                color: #edf3fc;
                font-size: 13px;
            }

            QLineEdit, QComboBox,
            QListWidget, QTextEdit {
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
            "Universal Linux Builder v0.6"
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

    def make_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.family = self.combo(
            list(FAMILIES)
        )

        self.distro = self.combo(
            FAMILIES[self.family.currentText()]
        )

        self.family.currentTextChanged.connect(
            self.change_family
        )

        self.arch = self.combo([
            "amd64",
            "arm64"
        ])

        self.version = QLineEdit("trixie")

        form.addRow("Famille", self.family)
        form.addRow("Distribution", self.distro)
        form.addRow("Architecture", self.arch)
        form.addRow("Version", self.version)

        layout.addLayout(form)
        layout.addStretch()

    def change_family(self, family):
        self.distro.clear()
        self.distro.addItems(FAMILIES[family])

    def make_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo([
            "Aucun",
            "GNOME",
            "KDE Plasma",
            "Xfce",
            "Budgie",
            "LXQt"
        ])

        self.display = self.combo([
            "Automatique",
            "Wayland",
            "X11"
        ])

        self.audio = self.combo([
            "PipeWire",
            "PulseAudio",
            "ALSA",
            "Aucun"
        ])

        self.network = self.combo([
            "NetworkManager",
            "systemd-networkd",
            "Manuel"
        ])

        self.init = self.combo([
            "Par défaut",
            "systemd",
            "OpenRC",
            "Init traditionnel"
        ])

        for title, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Réseau", self.network),
            ("Initialisation", self.init)
        ]:
            form.addRow(title, widget)

        layout.addLayout(form)

        self.flags = {}

        for key, title, checked in [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", False),
            ("printing", "Impression", False),
            ("calamares", "Calamares", False)
        ]:
            checkbox = QCheckBox(title)
            checkbox.setChecked(checked)

            self.flags[key] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()

    def make_applications(self):
        layout = self.page("Applications")

        layout.addWidget(QLabel(
            "Recherche intelligente locale"
        ))

        self.local_query = QLineEdit()

        self.local_query.setPlaceholderText(
            "Navigateur, vidéo, bureautique..."
        )

        self.local_query.textChanged.connect(
            self.local_search
        )

        self.local_results = QListWidget()

        self.local_results.itemDoubleClicked.connect(
            lambda item: self.add_package(item.text())
        )

        layout.addWidget(self.local_query)
        layout.addWidget(self.local_results)

        layout.addWidget(QLabel(
            "Distribution WSL"
        ))

        self.wsl_name = QLineEdit()

        self.wsl_name.setPlaceholderText(
            "Exemple : Debian"
        )

        layout.addWidget(self.wsl_name)

        row = QHBoxLayout()

        self.repo_query = QLineEdit()

        self.repo_query.setPlaceholderText(
            "Rechercher dans les dépôts Linux"
        )

        self.repo_button = QPushButton(
            "Rechercher"
        )

        self.repo_button.clicked.connect(
            lambda: self.start_worker("search")
        )

        row.addWidget(self.repo_query)
        row.addWidget(self.repo_button)

        layout.addLayout(row)

        layout.addWidget(QLabel(
            "Résultats des dépôts — double-clic pour ajouter"
        ))

        self.repo_results = QListWidget()

        self.repo_results.itemDoubleClicked.connect(
            self.add_repo_package
        )

        layout.addWidget(self.repo_results)

        layout.addWidget(QLabel(
            "Applications sélectionnées"
        ))

        self.selected = QListWidget()

        self.selected.itemDoubleClicked.connect(
            self.remove_package
        )

        layout.addWidget(self.selected)

        self.local_search()

    def local_search(self):
        self.local_results.clear()

        words = normalize(
            self.local_query.text()
        ).split()

        for name, description in CATALOG.items():
            text = normalize(
                name + " " + description
            )

            if all(word in text for word in words):
                self.local_results.addItem(name)

    def packages(self):
        return [
            self.selected.item(i).text()
            for i in range(self.selected.count())
        ]

    def add_package(self, name):
        distro = self.distro.currentText()

        if (
            isinstance(name, str)
            and valid_package(name, distro)
            and name not in self.packages()
        ):
            self.selected.addItem(name)

    def add_repo_package(self, item):
        name = item.data(
            Qt.ItemDataRole.UserRole
        )

        self.add_package(name)

    def remove_package(self, item):
        self.selected.takeItem(
            self.selected.row(item)
        )

    def make_optimization(self):
        layout = self.page("Optimisation")

        self.profile = self.combo([
            "Standard",
            "Minimal",
            "Ultra-minimal"
        ])

        layout.addWidget(QLabel(
            "Profil d'optimisation"
        ))

        layout.addWidget(self.profile)

        layout.addWidget(QLabel(
            "Minimal et Ultra-minimal désactivent "
            "les paquets recommandés dans le moteur actuel."
        ))

        self.analyze_button = QPushButton(
            "Analyser les dépendances APT"
        )

        self.analyze_button.clicked.connect(
            lambda: self.start_worker("analyze")
        )

        layout.addWidget(self.analyze_button)

        self.analysis = QTextEdit()
        self.analysis.setReadOnly(True)

        layout.addWidget(self.analysis)

    def make_builder(self):
        layout = self.page("Construire ISO")

        layout.addWidget(QLabel(
            "Moteur expérimental Debian amd64 / live-build"
        ))

        row = QHBoxLayout()

        self.output = QLineEdit(
            str(Path.home() / "Documents" / "ULB-ISO")
        )

        choose = QPushButton("Dossier...")

        choose.clicked.connect(
            self.choose_output
        )

        row.addWidget(self.output)
        row.addWidget(choose)

        layout.addLayout(row)

        self.build_button = QPushButton(
            "Construire ISO Debian"
        )

        self.build_button.clicked.connect(
            self.build_iso
        )

        layout.addWidget(self.build_button)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.log)

        layout.addWidget(QLabel(
            "Prérequis Debian : live-build et sudo.\n"
            "Le journal apparaît à la fin de la construction."
        ))

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Dossier de construction"
        )

        if folder:
            self.output.setText(folder)

    def build_iso(self):
        config = self.config()

        if config["distribution"] != "Debian":
            QMessageBox.warning(
                self,
                "Non disponible",
                "Construction ISO limitée à Debian."
            )
            return

        if config["architecture"] != "amd64":
            QMessageBox.warning(
                self,
                "Non disponible",
                "Architecture amd64 requise."
            )
            return

        if config["init"] not in (
            "Par défaut",
            "systemd"
        ):
            QMessageBox.warning(
                self,
                "Incompatible",
                "Ce moteur utilise systemd."
            )
            return

        if (
            config["display"] == "Wayland"
            and config["desktop"] in ("Xfce", "LXQt")
        ):
            QMessageBox.warning(
                self,
                "Non validé",
                "Cette combinaison n'est pas prise "
                "en charge par le moteur initial."
            )
            return

        answer = QMessageBox.question(
            self,
            "Confirmation",
            "Lancer la construction ISO Debian ?\n"
            "Cette opération utilise sudo dans Linux "
            "et peut consommer plusieurs Go."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.log.setPlainText(
            "Construction en cours..."
        )

        self.start_worker("build")

    def config(self):
        config = {
            "schema": 6,
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
            "applications": self.packages(),
            "wsl_name": self.wsl_name.text().strip()
        }

        for key, widget in self.flags.items():
            config[key] = widget.isChecked()

        return config

    def start_worker(self, action):
        if self.worker and self.worker.isRunning():
            return

        self.repo_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.build_button.setEnabled(False)

        self.worker = Worker(
            action,
            self.config(),
            self.repo_query.text().strip(),
            self.output.text().strip()
        )

        self.worker.completed.connect(
            self.worker_result
        )

        self.worker.finished.connect(
            self.worker_finished
        )

        self.worker.start()

    def worker_finished(self):
        self.repo_button.setEnabled(True)
        self.analyze_button.setEnabled(True)
        self.build_button.setEnabled(True)

    def worker_result(self, action, data):
        if action == "error":
            QMessageBox.warning(
                self,
                "Erreur",
                str(data)
            )

            self.log.append(
                "ERREUR : " + str(data)
            )
            return

        if action == "search":
            self.repo_results.clear()

            for name, description in data["packages"]:
                item = QListWidgetItem(
                    f"{name} — {description[:100]}"
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    name
                )

                self.repo_results.addItem(item)

            count = len(data["packages"])

            self.statusBar().showMessage(
                f"{count} paquets trouvés"
            )

            if data["warnings"]:
                QMessageBox.warning(
                    self,
                    "Recherche partielle",
                    "\n".join(data["warnings"][:2])
                )

        elif action == "analysis":
            self.analysis.setPlainText(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False
                )
            )

        elif action == "build":
            self.log.setPlainText(
                data["log"]
            )

            if data["returncode"] == 0:
                QMessageBox.information(
                    self,
                    "Construction terminée",
                    "La commande live-build est terminée.\n"
                    "Vérifie le fichier ISO dans le journal."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Échec",
                    "La construction a échoué.\n"
                    "Consulte le journal."
                )

    def make_project(self):
        layout = self.page("Projet")

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)

        layout.addWidget(self.summary)

        row = QHBoxLayout()

        for title, callback in [
            ("Actualiser", self.refresh),
            ("Enregistrer JSON", self.save),
            ("Ouvrir JSON", self.load)
        ]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)

        layout.addLayout(row)

    def tab_changed(self, index):
        if index == 5:
            self.refresh()

    def refresh(self):
        self.summary.setPlainText(
            json.dumps(
                self.config(),
                indent=2,
                ensure_ascii=False
            )
        )

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer",
            "distribution.json",
            "JSON (*.json)"
        )

        if not filename:
            return

        try:
            Path(filename).write_text(
                json.dumps(
                    self.config(),
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

        except OSError as error:
            QMessageBox.critical(
                self,
                "Erreur",
                str(error)
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

            family = data.get("family")
            distro = data.get("distribution")

            if (
                family not in FAMILIES
                or distro not in FAMILIES[family]
            ):
                raise ValueError(
                    "Distribution inconnue."
                )

            apps = data.get("applications", [])

            if (
                not isinstance(apps, list)
                or len(apps) > 150
            ):
                raise ValueError(
                    "Liste d'applications invalide."
                )

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

            for key, widget in fields:
                value = data.get(key)

                if (
                    isinstance(value, str)
                    and widget.findText(value) >= 0
                ):
                    widget.setCurrentText(value)

            self.version.setText(
                str(data.get("version", ""))
            )

            self.wsl_name.setText(
                str(data.get("wsl_name", ""))
            )

            for key, widget in self.flags.items():
                if isinstance(data.get(key), bool):
                    widget.setChecked(data[key])

            self.selected.clear()

            for name in apps:
                self.add_package(name)

            self.refresh()

        except (
            OSError,
            ValueError,
            TypeError
        ) as error:
            QMessageBox.critical(
                self,
                "Erreur",
                str(error)
            )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
