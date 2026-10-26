import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QTextEdit, QFileDialog,
    QMessageBox, QCheckBox
)

VERSION = "0.7.1"

DATA = {
    "Debian": {
        "family": "Debian / Ubuntu",
        "versions": ["trixie", "bookworm"],
        "arch": ["amd64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire", "PulseAudio"],
        "init": ["systemd"],
        "search": "apt"
    },
    "Ubuntu": {
        "family": "Debian / Ubuntu",
        "versions": ["noble", "jammy"],
        "arch": ["amd64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire", "PulseAudio"],
        "init": ["systemd"],
        "search": "apt"
    },
    "Fedora": {
        "family": "Fedora / Rocky",
        "versions": ["43", "42"],
        "arch": ["x86_64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire"],
        "init": ["systemd"],
        "search": "dnf"
    },
    "Rocky Linux": {
        "family": "Fedora / Rocky",
        "versions": ["10", "9"],
        "arch": ["x86_64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire"],
        "init": ["systemd"],
        "search": "dnf"
    },
    "Slackware": {
        "family": "Slackware / Salix",
        "versions": ["15.0", "current"],
        "arch": ["x86_64"],
        "desktops": ["Aucun", "Xfce", "KDE Plasma"],
        "audio": ["Aucun", "ALSA", "PulseAudio"],
        "init": ["SysV"],
        "search": "slapt"
    },
    "Salix": {
        "family": "Slackware / Salix",
        "versions": ["15.0"],
        "arch": ["x86_64"],
        "desktops": ["Aucun", "Xfce"],
        "audio": ["Aucun", "ALSA", "PulseAudio"],
        "init": ["SysV"],
        "search": "slapt"
    },
    "Gentoo": {
        "family": "Gentoo",
        "versions": ["stable", "testing"],
        "arch": ["amd64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire", "ALSA"],
        "init": ["OpenRC", "systemd"],
        "search": "portage"
    },
    "Arch Linux": {
        "family": "Arch Linux",
        "versions": ["rolling"],
        "arch": ["x86_64"],
        "desktops": ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"],
        "audio": ["Aucun", "PipeWire", "PulseAudio"],
        "init": ["systemd"],
        "search": "pacman"
    }
}

FAMILIES = list(dict.fromkeys(
    value["family"] for value in DATA.values()
))

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

CATALOG = {
    "navigateur": ["firefox", "chromium"],
    "video": ["vlc", "mpv"],
    "bureautique": ["libreoffice"],
    "photo": ["gimp", "krita"],
    "musique": ["audacious", "mpv"],
    "terminal": ["htop", "tmux"],
    "developpement": ["git", "geany"]
}

DEBIAN_DESKTOP = {
    "Aucun": [],
    "Xfce": ["xfce4", "lightdm"],
    "GNOME": ["gnome-core", "gdm3"],
    "KDE Plasma": ["plasma-desktop", "sddm"],
    "Budgie": ["budgie-desktop", "lightdm"]
}

ARCH_DESKTOP = {
    "Aucun": [],
    "Xfce": ["xfce4", "lightdm"],
    "GNOME": ["gnome", "gdm"],
    "KDE Plasma": ["plasma", "sddm"],
    "Budgie": ["budgie-desktop", "lightdm"]
}

VALID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,99}$"
)


def norm(value):
    return "".join(
        char
        for char in unicodedata.normalize(
            "NFKD", value.casefold()
        )
        if not unicodedata.combining(char)
    )


def linux(args, wsl, timeout=90, stdin=None):
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            raise RuntimeError("WSL2 absent")

        if not wsl:
            raise RuntimeError(
                "Indiquer le nom exact de la distribution WSL"
            )

        args = [
            "wsl.exe", "-d", wsl, "--exec"
        ] + args

    elif not sys.platform.startswith("linux"):
        raise RuntimeError(
            "Exécuter dans Linux ou WSL2 "
            "(macOS : VM Linux)"
        )

    return subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout
    )


def info(wsl):
    result = linux(
        ["cat", "/etc/os-release"],
        wsl,
        20
    )

    if result.returncode:
        raise RuntimeError(
            result.stderr or "Linux indisponible"
        )

    return dict(
        (key, value.strip().strip('"'))
        for line in result.stdout.splitlines()
        if "=" in line and not line.startswith("#")
        for key, value in [line.split("=", 1)]
    )


def validate(config):
    errors = []
    warnings = []

    distro = config["distro"]
    spec = DATA[distro]

    for key, option in [
        ("version", "versions"),
        ("arch", "arch"),
        ("desktop", "desktops"),
        ("audio", "audio"),
        ("init", "init")
    ]:
        if config[key] not in spec[option]:
            errors.append(
                f"{key} non compatible avec "
                f"{distro}: {config[key]}"
            )

    if (
        config["desktop"] == "Aucun"
        and config["display"] != "Aucun"
    ):
        errors.append(
            "Sans bureau, sélectionner affichage Aucun"
        )

    if (
        config["desktop"] != "Aucun"
        and config["display"] == "Aucun"
    ):
        errors.append(
            "Un bureau exige un serveur graphique"
        )

    if (
        config["display"] == "Wayland"
        and config["desktop"] in ("Xfce",)
    ):
        errors.append(
            "Wayland non pris en charge dans "
            "ce profil Xfce/LXQt"
        )

    if (
        config["display"] == "Wayland"
        and config["desktop"] == "Aucun"
    ):
        errors.append("Wayland sans bureau")

    if (
        config["audio"] == "PulseAudio"
        and distro in (
            "Fedora", "Rocky Linux", "Gentoo"
        )
    ):
        errors.append(
            "PulseAudio non proposé dans ce profil"
        )

    if distro in ("Slackware", "Salix"):
        if config["desktop"] not in (
            "Aucun", "Xfce", "KDE Plasma"
        ):
            errors.append(
                "Profil liveslak non disponible"
            )

    if distro == "Salix":
        warnings.append(
            "Construction via liveslak Slackware : "
            "compatibilité Salix non garantie"
        )

    if distro == "Rocky Linux":
        warnings.append(
            "Kickstart Rocky à fournir : "
            "aucun modèle universel fiable"
        )

    if distro == "Gentoo":
        warnings.append(
            "Catalyst : un spec LiveCD complet, "
            "stage et snapshot sont nécessaires"
        )

    if distro in ("Slackware", "Salix"):
        warnings.append(
            "Liveslak suit ses listes de paquets ; "
            "les applications sélectionnées "
            "ne sont pas injectées automatiquement"
        )

    if distro in ("Fedora", "Rocky Linux"):
        warnings.append(
            "Le modèle Kickstart doit contenir "
            "la configuration Live et les dépôts"
        )

    if (
        config["apps"]
        and distro in ("Slackware", "Salix", "Gentoo")
    ):
        warnings.append(
            "Applications conservées dans le projet "
            "mais non injectées automatiquement "
            "par ce backend"
        )

    if (
        config["desktop"] != "Aucun"
        and distro in (
            "Fedora", "Rocky Linux", "Gentoo"
        )
    ):
        warnings.append(
            "Le bureau doit être configuré dans "
            "le modèle de construction fourni"
        )

    return errors, warnings


def commands(distro, term):
    if distro in ("Debian", "Ubuntu"):
        return [
            "apt-cache", "search", "--", term
        ]

    if distro in ("Fedora", "Rocky Linux"):
        return ["dnf", "search", term]

    if distro in ("Slackware", "Salix"):
        return [
            "slapt-get", "--search", term
        ]

    if distro == "Gentoo":
        return [
            "emerge", "--search", term
        ]

    return [
        "pacman", "-Ss", term
    ]


def parse(distro, output):
    packages = {}
    current = None

    for line in output.splitlines():

        if distro in ("Debian", "Ubuntu"):
            if " - " in line:
                name, description = line.split(
                    " - ", 1
                )

                if VALID.fullmatch(name):
                    packages[name] = description

        elif distro in ("Fedora", "Rocky Linux"):
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|aarch64|noarch|i686)"
                r"\s*:\s*(.*)$",
                line.strip()
            )

            if match:
                packages[match.group(1)] = (
                    match.group(2)
                )

        elif distro == "Arch Linux":
            match = re.match(
                r"^([^/\s]+)/([^\s]+)\s+\S+",
                line
            )

            if match:
                current = match.group(2)

                packages[current] = (
                    "Dépôt " + match.group(1)
                )

            elif current and line.startswith("    "):
                packages[current] = line.strip()

        elif distro in ("Slackware", "Salix"):
            match = re.match(
                r"^([\w+.-]+)-\d[^\s]*",
                line.strip()
            )

            if match:
                packages[match.group(1)] = (
                    line.strip()
                )

        elif distro == "Gentoo":
            match = re.search(
                r"\*\s+([\w+.-]+/[\w+.-]+)",
                line
            )

            if match:
                packages[match.group(1)] = "Portage"

    return packages


def build_script(config):
    distro = config["distro"]
    apps = config["apps"]
    dest = config["target"]
    extra = config["template"]
    version = config["version"]

    if distro in ("Debian", "Ubuntu"):
        packages = (
            DEBIAN_DESKTOP[config["desktop"]] + apps
        )

        packages += {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"]
        }[config["audio"]]

        if config["wifi"]:
            packages += ["wpasupplicant"]

        if config["bluetooth"]:
            packages += ["bluez"]

        if config["printing"]:
            packages += ["cups"]

        if config["calamares"]:
            packages += ["calamares"]

        packages = list(dict.fromkeys(packages))

        script = """set -eu
command -v lb >/dev/null || {
    echo "Installer live-build"
    exit 2
}
mkdir -p "$1"
cd "$1"
[ ! -e config ] || {
    echo "Dossier déjà configuré : choisir un dossier neuf"
    exit 3
}
mkdir -p config/package-lists
lb config \
    --distribution "$2" \
    --architectures amd64 \
    --binary-images iso-hybrid \
    --apt-recommends "$3"
printf '%s\\n' "$4" |
    tr ' ' '\\n' > config/package-lists/ulb.list.chroot
lb build
"""

        args = [
            "bash", "-s", "--",
            dest,
            version,
            (
                "true"
                if config["optimization"] == "Standard"
                else "false"
            ),
            " ".join(packages)
        ]

        return script, args

    if distro == "Arch Linux":
        packages = (
            ARCH_DESKTOP[config["desktop"]] + apps
        )

        packages += {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"]
        }[config["audio"]]

        if config["wifi"]:
            packages += ["iwd"]

        if config["bluetooth"]:
            packages += ["bluez"]

        if config["printing"]:
            packages += ["cups"]

        if config["calamares"]:
            packages += ["calamares"]

        script = """set -eu
command -v mkarchiso >/dev/null || {
    echo "Installer archiso"
    exit 2
}
[ -d /usr/share/archiso/configs/releng ] || {
    echo "Profil releng absent"
    exit 2
}
mkdir -p "$1"
[ ! -e "$1/profile" ] || {
    echo "Profil déjà existant"
    exit 3
}
cp -a /usr/share/archiso/configs/releng "$1/profile"
printf '%s\\n' "$2" |
    tr ' ' '\\n' >> "$1/profile/packages.x86_64"
sort -u "$1/profile/packages.x86_64" \
    -o "$1/profile/packages.x86_64"
mkdir -p "$1/out" "$1/work"
mkarchiso -v \
    -w "$1/work" \
    -o "$1/out" \
    "$1/profile"
"""

        args = [
            "bash", "-s", "--",
            dest,
            " ".join(packages)
        ]

        return script, args

    if distro in ("Fedora", "Rocky Linux"):
        if not extra:
            raise RuntimeError(
                "Indiquer le chemin Linux vers "
                "un Kickstart Live complet"
            )

        script = """set -eu
command -v livecd-creator >/dev/null || {
    echo "Installer livecd-tools"
    exit 2
}
[ -f "$2" ] || {
    echo "Kickstart introuvable"
    exit 2
}
mkdir -p "$1"
[ ! -e "$1/ulb.ks" ] || {
    echo "ulb.ks existe déjà"
    exit 3
}
cp "$2" "$1/ulb.ks"

python3 - "$1/ulb.ks" "$3" <<'PYCODE'
import sys

path, packages = sys.argv[1:]
content = open(path).read()

start = content.find("%packages")
end = content.find("%end", start)

if start < 0 or end < 0:
    raise SystemExit(
        "Section %packages manquante"
    )

content = (
    content[:end]
    + "\\n"
    + "\\n".join(packages.split())
    + "\\n"
    + content[end:]
)

open(path, "w").write(content)
PYCODE

cd "$1"
livecd-creator \
    --verbose \
    --config=ulb.ks \
    --fslabel=ULB-Live
"""

        args = [
            "bash", "-s", "--",
            dest,
            extra,
            " ".join(apps)
        ]

        return script, args

    if distro in ("Slackware", "Salix"):
        if not extra:
            raise RuntimeError(
                "Indiquer le dossier Linux liveslak"
            )

        variant = {
            "Aucun": "SLACKWARE",
            "Xfce": "XFCE",
            "KDE Plasma": "LEAN"
        }[config["desktop"]]

        script = """set -eu
[ -f "$1/make_slackware_live.sh" ] || {
    echo "Sources liveslak absentes"
    exit 2
}
cd "$1"
echo "Attention : ISO créée selon les listes liveslak"
echo "Les applications ULB ne sont pas injectées"
./make_slackware_live.sh -d "$2" -a x86_64
"""

        args = [
            "bash", "-s", "--",
            extra,
            variant
        ]

        return script, args

    if distro == "Gentoo":
        if not extra:
            raise RuntimeError(
                "Indiquer le chemin Linux vers "
                "un spec Catalyst LiveCD complet"
            )

        script = """set -eu
command -v catalyst >/dev/null || {
    echo "Installer catalyst"
    exit 2
}
[ -f "$1" ] || {
    echo "Spec Catalyst introuvable"
    exit 2
}
echo "Catalyst utilisera les paramètres du spec"
catalyst -f "$1"
"""

        args = [
            "bash", "-s", "--",
            extra
        ]

        return script, args

    raise RuntimeError("Backend absent")


class Worker(QThread):
    done = Signal(str, object)

    def __init__(self, action, config, query=""):
        super().__init__()

        self.action = action
        self.config = config
        self.query = query

    def run(self):
        try:
            config = self.config

            actual = info(
                config["wsl"]
            ).get("ID", "").lower()

            expected = IDS[config["distro"]]

            if actual != expected:
                raise RuntimeError(
                    f"Environnement {actual} != {expected}"
                )

            if self.action == "search":
                terms = []
                query = norm(self.query)

                if (
                    not query
                    or len(query) > 80
                    or any(ord(char) < 32 for char in query)
                ):
                    raise RuntimeError(
                        "Recherche invalide"
                    )

                for keyword, values in CATALOG.items():
                    if keyword in query:
                        terms = values
                        break

                if not terms:
                    terms = [self.query]

                found = {}
                warnings = []

                for term in terms:
                    result = linux(
                        commands(config["distro"], term),
                        config["wsl"],
                        90
                    )

                    if result.returncode not in (0, 1):
                        warnings.append(
                            (
                                result.stderr
                                or result.stdout
                            )[-200:]
                        )
                    else:
                        found.update(
                            parse(
                                config["distro"],
                                result.stdout
                            )
                        )

                self.done.emit(
                    "search",
                    (
                        sorted(found.items())[:300],
                        warnings
                    )
                )
                return

            errors, warnings = validate(config)

            if errors:
                raise RuntimeError(
                    "\n".join(errors)
                )

            if self.action == "check":
                self.done.emit("check", warnings)
                return

            script, args = build_script(config)

            self.done.emit(
                "plan",
                {
                    "command": args,
                    "script": script,
                    "warnings": warnings
                }
            )

        except Exception as error:
            self.done.emit(
                "error",
                str(error)
            )


class Window(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v" + VERSION
        )
        self.resize(1000, 770)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.worker = None

        self.make_distribution()
        self.make_system()
        self.make_apps()
        self.make_build()
        self.make_project()

        self.tabs.currentChanged.connect(
            lambda index:
            self.refresh() if index == 4 else None
        )

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.tabs.addTab(widget, title)
        return layout

    def combo(self, items):
        widget = QComboBox()
        widget.addItems(items)
        return widget

    def make_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.family = self.combo(FAMILIES)
        self.distro = self.combo([])
        self.version = self.combo([])
        self.arch = self.combo([])

        self.family.currentTextChanged.connect(
            self.change_family
        )
        self.distro.currentTextChanged.connect(
            self.change_distro
        )

        for name, widget in [
            ("Famille", self.family),
            ("Distribution", self.distro),
            ("Version", self.version),
            ("Architecture", self.arch)
        ]:
            form.addRow(name, widget)

        layout.addLayout(form)
        layout.addStretch()

        self.change_family(
            self.family.currentText()
        )

    def change_family(self, family):
        self.distro.blockSignals(True)
        self.distro.clear()

        self.distro.addItems([
            distro
            for distro, spec in DATA.items()
            if spec["family"] == family
        ])

        self.distro.blockSignals(False)

        self.change_distro(
            self.distro.currentText()
        )

    def change_distro(self, distro):
        if distro not in DATA:
            return

        spec = DATA[distro]

        for widget, key in [
            (self.version, "versions"),
            (self.arch, "arch")
        ]:
            widget.clear()
            widget.addItems(spec[key])

        if hasattr(self, "desktop"):
            for widget, key in [
                (self.desktop, "desktops"),
                (self.audio, "audio"),
                (self.init, "init")
            ]:
                widget.clear()
                widget.addItems(spec[key])

            self.change_desktop(
                self.desktop.currentText()
            )

        if hasattr(self, "selected"):
            self.selected.clear()
            self.repo_results.clear()

    def make_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo([])
        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])
        self.audio = self.combo([])
        self.init = self.combo([])
        self.optim = self.combo([
            "Standard",
            "Minimal",
            "Ultra-minimal"
        ])

        for name, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Init", self.init),
            ("Optimisation", self.optim)
        ]:
            form.addRow(name, widget)

        layout.addLayout(form)

        self.desktop.currentTextChanged.connect(
            self.change_desktop
        )

        self.flags = {}

        for key, label in [
            ("wifi", "Wi-Fi"),
            ("bluetooth", "Bluetooth"),
            ("printing", "Impression"),
            ("calamares", "Calamares")
        ]:
            checkbox = QCheckBox(label)

            self.flags[key] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()

        self.change_distro(
            self.distro.currentText()
        )

    def change_desktop(self, desktop):
        if desktop == "Aucun":
            self.display.setCurrentText("Aucun")

        elif desktop in ("Xfce",):
            self.display.setCurrentText("X11")

        elif self.display.currentText() == "Aucun":
            self.display.setCurrentText("Wayland")

    def make_apps(self):
        layout = self.page("Applications")

        self.wsl = QLineEdit()
        self.wsl.setPlaceholderText(
            "Nom WSL exact (ex. Debian)"
        )

        layout.addWidget(self.wsl)

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "navigateur, vidéo, firefox..."
        )

        button = QPushButton("Rechercher")
        button.clicked.connect(
            lambda: self.work("search")
        )

        row.addWidget(self.query)
        row.addWidget(button)

        layout.addLayout(row)

        layout.addWidget(QLabel(
            "Dépôts (double-clic pour ajouter)"
        ))

        self.repo_results = QListWidget()
        self.repo_results.itemDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(self.repo_results)

        layout.addWidget(QLabel(
            "Paquets sélectionnés "
            "(double-clic pour supprimer)"
        ))

        self.selected = QListWidget()

        self.selected.itemDoubleClicked.connect(
            lambda item:
            self.selected.takeItem(
                self.selected.row(item)
            )
        )

        layout.addWidget(self.selected)

    def add_result(self, item):
        name = item.data(
            Qt.ItemDataRole.UserRole
        )

        if name and name not in self.apps():
            self.selected.addItem(name)

    def apps(self):
        return [
            self.selected.item(index).text()
            for index in range(self.selected.count())
        ]

    def make_build(self):
        layout = self.page("ISO / Préparation")
        form = QFormLayout()

        self.target = QLineEdit(
            "/home/ulb/build-v07"
        )

        self.template = QLineEdit()
        self.template.setPlaceholderText(
            "Chemin Linux Kickstart / liveslak / "
            "Catalyst (si nécessaire)"
        )

        form.addRow(
            "Dossier Linux de sortie",
            self.target
        )

        form.addRow(
            "Modèle Linux",
            self.template
        )

        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Préparation sûre : génère un script à "
            "lancer dans le Linux correspondant.\n"
            "Aucune commande privilégiée "
            "n'est exécutée automatiquement."
        ))

        row = QHBoxLayout()

        button = QPushButton(
            "Vérifier les choix"
        )
        button.clicked.connect(
            lambda: self.work("check")
        )
        row.addWidget(button)

        button = QPushButton(
            "Générer le script ISO"
        )
        button.clicked.connect(
            lambda: self.work("plan")
        )
        row.addWidget(button)

        layout.addLayout(row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.log)

    def config(self):
        config = {
            "schema": 7,
            "distro": self.distro.currentText(),
            "family": self.family.currentText(),
            "version": self.version.currentText(),
            "arch": self.arch.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "init": self.init.currentText(),
            "optimization": self.optim.currentText(),
            "wsl": self.wsl.text().strip(),
            "apps": self.apps(),
            "target": self.target.text().strip(),
            "template": self.template.text().strip()
        }

        config.update({
            key: widget.isChecked()
            for key, widget in self.flags.items()
        })

        return config

    def work(self, action):
        if self.worker and self.worker.isRunning():
            return

        self.worker = Worker(
            action,
            self.config(),
            self.query.text().strip()
        )

        self.worker.done.connect(
            self.result
        )

        self.worker.start()

    def result(self, kind, data):
        if kind == "error":
            QMessageBox.warning(
                self,
                "Erreur",
                str(data)
            )

            self.log.setPlainText(
                str(data)
            )
            return

        if kind == "search":
            self.repo_results.clear()

            items, warnings = data

            for name, description in items:
                item = QListWidgetItem(
                    f"{name} — {description[:110]}"
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    name
                )

                self.repo_results.addItem(item)

            self.statusBar().showMessage(
                f"{len(items)} résultats ; "
                f"{len(warnings)} avertissements"
            )
            return

        if kind == "check":
            self.log.setPlainText(
                "Configuration cohérente selon "
                "les règles connues.\n"
                + "\n".join(data)
            )
            return

        if kind == "plan":
            base = (
                Path.home()
                / "Documents"
                / "UniversalLinuxBuilder"
            )

            base.mkdir(
                parents=True,
                exist_ok=True
            )

            distro_name = (
                self.distro.currentText()
                .lower()
                .replace(" ", "_")
            )

            path = base / (
                f"build_v0_7_{distro_name}.sh"
            )

            import shlex

            shell = data["script"]

            command = " ".join(
                shlex.quote(value)
                for value in data["command"]
            )

            if data["command"][:2] == [
                "bash", "-s"
            ]:
                command += (
                    " <<'ULB_SCRIPT_V07'\n"
                    + shell
                    + "\nULB_SCRIPT_V07\n"
                )

            path.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                + command
                + "\n",
                encoding="utf-8"
            )

            self.log.setPlainText(
                "Script généré : "
                + str(path)
                + "\n\nCopier ce script dans "
                "le Linux cible et le lancer "
                "avec les privilèges adaptés.\n\n"
                + "\n".join(data["warnings"])
            )

    def make_project(self):
        layout = self.page("Projet")

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)

        layout.addWidget(self.summary)

        row = QHBoxLayout()

        for label, function in [
            ("Actualiser", self.refresh),
            ("Enregistrer", self.save),
            ("Ouvrir", self.load)
        ]:
            button = QPushButton(label)
            button.clicked.connect(function)
            row.addWidget(button)

        layout.addLayout(row)

    def refresh(self):
        config = self.config()

        errors, warnings = validate(config)

        self.summary.setPlainText(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2
            )
            + "\n\nErreurs :\n"
            + "\n".join(errors)
            + "\nAvertissements :\n"
            + "\n".join(warnings)
        )

    def save(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer",
            f"projet_v{VERSION}.json",
            "JSON (*.json)"
        )

        if path:
            Path(path).write_text(
                json.dumps(
                    self.config(),
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            )

    def load(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir",
            "",
            "JSON (*.json)"
        )

        if not path:
            return

        try:
            config = json.loads(
                Path(path).read_text(
                    encoding="utf-8"
                )
            )

            distro = config["distro"]

            if distro not in DATA:
                raise ValueError(
                    "Distribution inconnue"
                )

            self.family.setCurrentText(
                DATA[distro]["family"]
            )

            self.distro.setCurrentText(
                distro
            )

            for widget, key in [
                (self.version, "version"),
                (self.arch, "arch"),
                (self.desktop, "desktop"),
                (self.display, "display"),
                (self.audio, "audio"),
                (self.init, "init"),
                (self.optim, "optimization")
            ]:
                if widget.findText(
                    config.get(key, "")
                ) >= 0:
                    widget.setCurrentText(
                        config[key]
                    )

            self.wsl.setText(
                config.get("wsl", "")
            )

            self.target.setText(
                config.get("target", "")
            )

            self.template.setText(
                config.get("template", "")
            )

            self.selected.clear()

            for app in config.get("apps", []):
                if (
                    isinstance(app, str)
                    and (
                        VALID.fullmatch(app)
                        or (
                            distro == "Gentoo"
                            and re.fullmatch(
                                r"[\w+.-]+/[\w+.-]+",
                                app
                            )
                        )
                    )
                ):
                    self.selected.addItem(app)

            for key, widget in self.flags.items():
                widget.setChecked(
                    config.get(key, False) is True
                )

            self.refresh()

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError
        ) as error:
            QMessageBox.warning(
                self,
                "Projet invalide",
                str(error)
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())

