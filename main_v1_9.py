import sys
import os
import re
import json
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QFileDialog, QMessageBox,
    QTextEdit, QAbstractItemView, QInputDialog
)

VERSION = "1.9"

VERSIONS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

MANAGERS = {
    "Debian": "apt-cache",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

INIT = {
    "Debian": ["systemd"],
    "Fedora": ["systemd"],
    "Arch Linux": ["systemd"],
    "Gentoo": ["OpenRC", "systemd"],
    "Slackware": ["SysVinit"]
}

KERNEL = {
    "Debian": {
        "Stable": ["linux-image-amd64"]
    },
    "Fedora": {
        "Stable": ["kernel"]
    },
    "Arch Linux": {
        "Stable": ["linux"],
        "LTS": ["linux-lts"],
        "Hardened": ["linux-hardened"]
    },
    "Gentoo": {
        "Stable": ["sys-kernel/gentoo-kernel"]
    },
    "Slackware": {
        "Stable": ["kernel-generic"]
    }
}

DESKTOP = {
    "Debian": {
        "GNOME": ["gnome-core", "gdm3", "network-manager"],
        "KDE Plasma": [
            "kde-plasma-desktop", "sddm", "network-manager"
        ],
        "Xfce": ["xfce4", "lightdm", "network-manager"],
        "Budgie": [
            "budgie-desktop", "lightdm", "network-manager"
        ]
    },
    "Fedora": {
        "GNOME": [
            "gnome-shell", "gnome-session",
            "gdm", "NetworkManager"
        ],
        "KDE Plasma": [
            "plasma-desktop", "plasma-workspace",
            "sddm", "NetworkManager"
        ],
        "Xfce": [
            "xfce4-session", "xfce4-panel",
            "xfwm4", "lightdm", "NetworkManager"
        ],
        "Budgie": [
            "budgie-desktop", "gdm", "NetworkManager"
        ]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm", "networkmanager"],
        "KDE Plasma": ["plasma", "sddm", "networkmanager"],
        "Xfce": ["xfce4", "lightdm", "networkmanager"],
        "Budgie": [
            "budgie-desktop", "gdm", "networkmanager"
        ]
    },
    "Gentoo": {
        "GNOME": [
            "gnome-base/gnome", "gnome-base/gdm"
        ],
        "KDE Plasma": [
            "kde-plasma/plasma-meta", "x11-misc/sddm"
        ],
        "Xfce": [
            "xfce-base/xfce4-meta", "x11-misc/lightdm"
        ],
        "Budgie": [
            "gnome-extra/budgie-desktop", "gnome-base/gdm"
        ]
    },
    "Slackware": {
        "KDE Plasma": [
            "plasma-desktop", "plasma-workspace", "sddm"
        ],
        "Xfce": [
            "xfce4-session", "xfce4-panel", "xfwm4"
        ]
    }
}

AUDIO = {
    "Debian": {
        "PipeWire": [
            "pipewire", "wireplumber", "pipewire-pulse"
        ],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Fedora": {
        "PipeWire": [
            "pipewire", "wireplumber", "pipewire-pulseaudio"
        ],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Arch Linux": {
        "PipeWire": [
            "pipewire", "wireplumber", "pipewire-pulse"
        ],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Gentoo": {
        "PipeWire": [
            "media-video/pipewire",
            "media-video/wireplumber"
        ],
        "PulseAudio": ["media-sound/pulseaudio"],
        "ALSA": ["media-sound/alsa-utils"]
    },
    "Slackware": {
        "PipeWire": ["pipewire", "wireplumber"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    }
}

EXTRA = {
    "Debian": {
        "Base": ["systemd-sysv", "pciutils"],
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["firmware-linux-free"],
        "Calamares": ["calamares"],
        "X11": ["xserver-xorg"]
    },
    "Fedora": {
        "Base": ["systemd", "pciutils"],
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": [],
        "X11": ["xorg-x11-server-Xorg"]
    },
    "Arch Linux": {
        "Base": ["base", "pciutils"],
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": ["calamares"],
        "X11": ["xorg-server"]
    },
    "Gentoo": {
        "Base": ["sys-apps/pciutils"],
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmware": ["sys-kernel/linux-firmware"],
        "Calamares": [],
        "X11": ["x11-base/xorg-server"]
    },
    "Slackware": {
        "Base": ["pciutils"],
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["kernel-firmware"],
        "Calamares": [],
        "X11": ["xorg-server"]
    }
}

GRUB = {
    "Debian": {
        "UEFI": ["grub-efi-amd64", "efibootmgr"],
        "BIOS": ["grub-pc"]
    },
    "Fedora": {
        "UEFI": [
            "grub2-efi-x64", "grub2-tools", "efibootmgr"
        ],
        "BIOS": ["grub2-pc", "grub2-tools"]
    },
    "Arch Linux": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"]
    },
    "Gentoo": {
        "UEFI": [
            "sys-boot/grub", "sys-boot/efibootmgr"
        ],
        "BIOS": ["sys-boot/grub"]
    },
    "Slackware": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"]
    }
}

SAFE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

DARK = """
QWidget {
    background: #121b28;
    color: #eaf0f9;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #1b293a;
    border: 1px solid #35475d;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #245a9a;
}
QPushButton {
    background: #263a52;
    border: 1px solid #49617b;
    border-radius: 7px;
    padding: 9px;
}
QPushButton:hover {
    background: #31516f;
}
QTabBar::tab {
    padding: 12px;
}
QTabBar::tab:selected {
    border-bottom: 2px solid #64a8ff;
}
QHeaderView::section {
    background: #263a52;
    padding: 8px;
}
"""

LIGHT = """
QWidget {
    background: #f4f6fa;
    color: #172338;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: white;
    border: 1px solid #cbd6e4;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #d3e7ff;
    selection-color: #14243b;
}
QPushButton {
    background: #e7edf6;
    border: 1px solid #c3d0e0;
    border-radius: 7px;
    padding: 9px;
}
QPushButton:hover {
    background: #d7e5f5;
}
QTabBar::tab {
    padding: 12px;
}
QTabBar::tab:selected {
    border-bottom: 2px solid #2670dd;
}
QHeaderView::section {
    background: #e7edf6;
    padding: 8px;
}
"""


# ============================================================
# MOTEUR WINDOWS / WSL2
# ============================================================

def proc(argv, timeout=90, allow_failure=False):
    process = subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        creationflags=getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
    )

    def decode(data):
        if b"\x00" in data:
            return data.decode(
                "utf-16-le", errors="replace"
            )
        return data.decode(
            "utf-8", errors="replace"
        )

    output = decode(process.stdout)
    error = decode(process.stderr)

    if process.returncode and not allow_failure:
        raise RuntimeError(
            (
                error or output
                or f"Code erreur : {process.returncode}"
            )[-2400:]
        )

    return output, error, process.returncode


def wsl_list():
    output, _, _ = proc(
        ["wsl.exe", "--list", "--quiet"],
        timeout=25
    )

    return [
        line.strip().lstrip("\ufeff")
        for line in output.splitlines()
        if line.strip().strip("\x00")
    ]


def wsl_catalog():
    output, _, _ = proc(
        ["wsl.exe", "--list", "--online"],
        timeout=35
    )
    return output


def wsl_run(env, command, timeout=120,
            allow_failure=False):

    if env not in wsl_list():
        raise RuntimeError(
            "Distribution WSL non installée : " + env
        )

    return proc(
        [
            "wsl.exe",
            "--distribution", env,
            "--exec", "/bin/sh", "-lc", command
        ],
        timeout=timeout,
        allow_failure=allow_failure
    )


def identify(env):
    command = (
        "cat /etc/os-release; "
        "echo __MANAGER__; "
        "for x in apt-cache dnf5 pacman emerge slackpkg; "
        'do command -v "$x" || true; done'
    )

    output, _, _ = wsl_run(
        env, command, timeout=35
    )

    return output


# ============================================================
# GESTIONNAIRES DE PAQUETS
# ============================================================

def search_cmd(family, query):
    query = shlex.quote(query)

    commands = {
        "Debian": "LC_ALL=C apt-cache search -- " + query,
        "Fedora": "LC_ALL=C dnf5 search " + query,
        "Arch Linux": "LC_ALL=C pacman -Ss " + query,
        "Gentoo": "LC_ALL=C emerge --search " + query,
        "Slackware": "LC_ALL=C slackpkg search " + query
    }

    return commands[family]


def parse_search(family, output):
    rows = []
    seen = set()

    for line in output.splitlines():
        line = line.strip()

        name = ""
        version = "?"
        description = ""

        if family == "Debian":
            if " - " in line:
                name, description = line.split(" - ", 1)

        elif family == "Arch Linux":
            match = re.match(
                r"^[\w-]+/([^ ]+)\s+([^ ]+)",
                line
            )

            if match:
                name, version = match.groups()

        elif family == "Fedora":
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|noarch|aarch64|i686)"
                r"\s*:\s*(.*)",
                line
            )

            if match:
                name, description = match.groups()

        elif family == "Gentoo":
            match = re.search(
                r"\*\s+([\w+.-]+/[\w+.-]+)",
                line
            )

            if match:
                name = match.group(1)

        elif family == "Slackware":
            match = re.search(
                r"\b([\w+.-]+)-"
                r"([0-9][\w.+-]*)-"
                r"(?:x86_64|noarch|i[3-6]86)",
                line
            )

            if match:
                name, version = match.groups()

        if (
            name
            and SAFE.fullmatch(name)
            and name not in seen
        ):
            seen.add(name)
            rows.append(
                (name, version, description[:170])
            )

    return rows[:250]


def solve_cmd(family, packages):
    arguments = " ".join(
        shlex.quote(package)
        for package in packages
    )

    commands = {
        "Debian": (
            "LC_ALL=C apt-get -s "
            "-o Debug::NoLocking=1 install "
            + arguments
        ),
        "Fedora": (
            "LC_ALL=C dnf5 --assumeno install "
            + arguments
        ),
        "Arch Linux": (
            'LC_ALL=C pacman -Sp '
            '--print-format "%n|%v|%s" '
            + arguments
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend "
            "--verbose --tree "
            + arguments
        ),
        "Slackware": (
            'echo "Slackware: aucune résolution '
            'native des dépendances"'
        )
    }

    return commands[family]


def parse_solve(family, output, roots):
    result = {
        name: {
            "version": "?",
            "bytes": None,
            "status": "Demandé"
        }
        for name in roots
    }

    if family == "Debian":
        for line in output.splitlines():
            match = re.match(
                r"^Inst\s+(\S+)"
                r"(?:\s+\[.*?\])?"
                r"\s+\(([^ )]+)",
                line
            )

            if match:
                result[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "status": "Transaction"
                }

    elif family == "Arch Linux":
        for line in output.splitlines():
            match = re.match(
                r"^([^|]+)\|([^|]+)\|(\d+)$",
                line.strip()
            )

            if match:
                result[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": int(match.group(3)),
                    "status": "Transaction"
                }

    elif family == "Fedora":
        for line in output.splitlines():
            match = re.match(
                r"^\s*([\w+.-]+)\s+"
                r"(?:x86_64|noarch|aarch64|i686)"
                r"\s+([\w:~.+-]+)\s+",
                line
            )

            if match:
                result[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "status": "Indicatif"
                }

    elif family == "Gentoo":
        for line in output.splitlines():
            match = re.search(
                r"\[ebuild[^]]*\]\s+"
                r"([\w+.-]+/[\w+.-]+)-"
                r"([\w.+-]+)",
                line
            )

            if match:
                result[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "status": "Indicatif"
                }

    return result


# ============================================================
# THREADS : OPÉRATIONS LONGUES SANS BLOQUER L'INTERFACE
# ============================================================

class Worker(QThread):
    completed = Signal(object, str)

    def __init__(self, kind, *args):
        super().__init__()
        self.kind = kind
        self.args = args

    def run(self):
        try:
            if self.kind == "detect":
                result = wsl_list()

            elif self.kind == "catalog":
                result = wsl_catalog()

            elif self.kind == "identify":
                result = identify(*self.args)

            elif self.kind == "install":
                name = self.args[0]

                result = proc(
                    [
                        "wsl.exe",
                        "--install",
                        "--distribution", name,
                        "--no-launch"
                    ],
                    timeout=1800
                )[0]

            elif self.kind == "import":
                name, destination, archive = self.args

                result = proc(
                    [
                        "wsl.exe",
                        "--import",
                        name,
                        destination,
                        archive,
                        "--version", "2"
                    ],
                    timeout=1800
                )[0]

            elif self.kind == "search":
                env, family, query = self.args

                output = wsl_run(
                    env,
                    search_cmd(family, query),
                    timeout=120
                )[0]

                result = parse_search(
                    family, output
                )

            elif self.kind == "solve":
                env, family, packages = self.args

                output, error, code = wsl_run(
                    env,
                    solve_cmd(family, packages),
                    timeout=240,
                    allow_failure=True
                )

                if family == "Fedora" and code == 1:
                    # DNF peut refuser une transaction simulée.
                    pass
                elif code:
                    raise RuntimeError(
                        (error or output)[-2200:]
                    )

                result = (
                    parse_solve(family, output, packages),
                    output,
                    error,
                    code
                )

            else:
                raise RuntimeError(
                    "Action inconnue"
                )

            self.completed.emit(result, "")

        except Exception as error:
            self.completed.emit(
                None, str(error)
            )


# ============================================================
# INTERFACE PRINCIPALE
# ============================================================

class Main(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.9"
        )
        self.resize(1320, 880)

        self.envs = {
            distro: "" for distro in VERSIONS
        }

        self.installed = []
        self.catalog_text = ""
        self.apps = set()
        self.solution = {}
        self.report = ""
        self.signature = None
        self.worker = None
        self.revision = 0

        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)

        top = QHBoxLayout()

        title = QLabel(
            "Universal Linux Builder  •  v1.9"
        )
        title.setStyleSheet(
            "font-size:23px;font-weight:700"
        )

        top.addWidget(title)
        top.addStretch()
        top.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems([
            "Automatique",
            "Clair",
            "Sombre"
        ])

        top.addWidget(self.theme)
        outer.addLayout(top)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self.build_distribution()
        self.build_system()
        self.build_apps()
        self.build_project()
        self.build_env()

        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        QApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.apply_theme()
        )

        self.apply_theme()
        self.change_distro()

    def apply_theme(self, *_):
        name = self.theme.currentText()

        if name == "Automatique":
            dark = (
                QApplication.styleHints().colorScheme()
                == Qt.ColorScheme.Dark
            )
            name = "Sombre" if dark else "Clair"

        self.setStyleSheet(
            DARK if name == "Sombre" else LIGHT
        )

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            18, 18, 18, 18
        )

        self.tabs.addTab(
            widget, title
        )

        return layout

    def combo(self, items):
        combo = QComboBox()
        combo.addItems(items)
        return combo

    def table(self, headers):
        table = QTableWidget(
            0, len(headers)
        )

        table.setHorizontalHeaderLabels(
            headers
        )

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setDefaultSectionSize(32)

        return table

    def fill(self, table, rows):
        table.setSortingEnabled(False)
        table.setRowCount(0)

        for values in rows:
            row = table.rowCount()
            table.insertRow(row)

            for column, value in enumerate(values):
                table.setItem(
                    row,
                    column,
                    QTableWidgetItem(str(value))
                )

        table.setSortingEnabled(True)

    # ========================================================
    # ONGLET DISTRIBUTION
    # ========================================================

    def build_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.distro = self.combo(
            list(VERSIONS)
        )

        self.release = self.combo([])

        form.addRow(
            "Distribution", self.distro
        )

        form.addRow(
            "Version cible", self.release
        )

        layout.addLayout(form)

        label = QLabel(
            "La version WSL doit correspondre aux dépôts "
            "de la version cible. Vérifier cette correspondance "
            "avant l'analyse."
        )
        label.setWordWrap(True)

        layout.addWidget(label)
        layout.addStretch()

        self.distro.currentTextChanged.connect(
            self.change_distro
        )

        self.release.currentTextChanged.connect(
            self.invalidate
        )

    # ========================================================
    # ONGLET SYSTÈME
    # ========================================================

    def build_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo(["Aucun"])

        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])

        self.audio = self.combo([
            "PipeWire",
            "PulseAudio",
            "ALSA",
            "Aucun"
        ])

        self.kernel = self.combo([
            "Stable", "LTS", "Hardened"
        ])

        self.init = self.combo([])

        self.boot = self.combo([
            "GRUB", "Aucun"
        ])

        self.bootmode = self.combo([
            "UEFI", "BIOS"
        ])

        fields = [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau", self.kernel),
            ("Système d'initialisation", self.init),
            ("Bootloader", self.boot),
            ("Mode de démarrage", self.bootmode)
        ]

        for title, widget in fields:
            form.addRow(title, widget)

        layout.addLayout(form)

        self.flags = {}

        options = [
            ("Wi-Fi", True),
            ("Bluetooth", True),
            ("Impression", False),
            ("Firmware", True),
            ("Calamares", True)
        ]

        for name, default in options:
            checkbox = QCheckBox(name)
            checkbox.setChecked(default)

            self.flags[name] = checkbox

            layout.addWidget(checkbox)

            checkbox.toggled.connect(
                self.invalidate
            )

        self.systemnote = QLabel(
            "Analyse WSL requise."
        )
        self.systemnote.setWordWrap(True)

        layout.addWidget(self.systemnote)

        button = QPushButton(
            "Analyser système + applications avec WSL2"
        )
        button.clicked.connect(
            self.resolve
        )

        layout.addWidget(button)
        layout.addStretch()

        self.desktop.currentTextChanged.connect(
            self.change_desktop
        )

        for widget in [
            self.display,
            self.audio,
            self.kernel,
            self.init,
            self.boot,
            self.bootmode
        ]:
            widget.currentTextChanged.connect(
                self.invalidate
            )

    # ========================================================
    # ONGLET APPLICATIONS
    # ========================================================

    def build_apps(self):
        layout = self.page("Applications")

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher Firefox, VLC, GIMP..."
        )

        self.query.returnPressed.connect(
            self.search
        )

        search = QPushButton(
            "Rechercher dans WSL2"
        )
        search.clicked.connect(
            self.search
        )

        row.addWidget(self.query)
        row.addWidget(search)

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Catalogue natif — double-clic pour ajouter"
            )
        )

        self.results = self.table([
            "Nom du paquet",
            "Version",
            "Description"
        ])

        self.results.setColumnWidth(0, 320)
        self.results.setColumnWidth(1, 170)

        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(
            self.results, 2
        )

        layout.addWidget(
            QLabel(
                "Applications demandées — "
                "double-clic pour supprimer"
            )
        )

        self.selected = self.table([
            "Application"
        ])

        self.selected.cellDoubleClicked.connect(
            self.remove_app
        )

        layout.addWidget(
            self.selected, 1
        )

        row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Nom exact du paquet"
        )

        add = QPushButton("Ajouter")
        add.clicked.connect(
            self.add_manual
        )

        row.addWidget(self.manual)
        row.addWidget(add)

        layout.addLayout(row)

        self.appnote = QLabel(
            "Les dépendances sont recalculées "
            "à chaque analyse."
        )
        self.appnote.setWordWrap(True)

        layout.addWidget(self.appnote)

    # ========================================================
    # ONGLET PROJET / ISO
    # ========================================================

    def build_project(self):
        layout = self.page("Projet / ISO")

        self.summary = QLabel(
            "Lancer une analyse native pour voir les paquets."
        )
        self.summary.setWordWrap(True)

        layout.addWidget(self.summary)

        self.preview = self.table([
            "Paquet",
            "Version",
            "État",
            "Taille"
        ])

        self.preview.setColumnWidth(0, 320)

        layout.addWidget(
            self.preview, 2
        )

        self.projectreport = QTextEdit()
        self.projectreport.setReadOnly(True)

        layout.addWidget(
            self.projectreport, 1
        )

        row = QHBoxLayout()

        check = QPushButton("Vérifier")
        check.clicked.connect(
            self.verify
        )

        export = QPushButton(
            "Exporter le projet"
        )
        export.clicked.connect(
            self.export
        )

        row.addWidget(check)
        row.addWidget(export)

        layout.addLayout(row)

    # ========================================================
    # ONGLET PRÉREQUIS WSL2
    # ========================================================

    def build_env(self):
        layout = self.page("Prérequis WSL2")

        note = QLabel(
            "Installer uniquement les environnements nécessaires. "
            "Une installation ou un import WSL modifie Windows "
            "et peut télécharger plusieurs Go. "
            "Une confirmation est demandée avant chaque opération."
        )
        note.setWordWrap(True)

        layout.addWidget(note)

        row = QHBoxLayout()

        actions = [
            ("Détecter WSL", self.detect),
            ("Catalogue officiel WSL", self.catalog),
            (
                "Installer la distribution sélectionnée",
                self.install
            ),
            (
                "Importer Gentoo / Slackware",
                self.import_custom
            ),
            (
                "Tester le gestionnaire",
                self.test
            )
        ]

        for title, function in actions:
            button = QPushButton(title)
            button.clicked.connect(function)
            row.addWidget(button)

        layout.addLayout(row)

        form = QFormLayout()

        self.envcombos = {}

        for family in VERSIONS:
            combo = self.combo([
                "— Non configuré —"
            ])

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.assign(f, value)
            )

            form.addRow(
                family, combo
            )

            self.envcombos[family] = combo

        layout.addLayout(form)

        self.envnote = QTextEdit()
        self.envnote.setReadOnly(True)

        self.envnote.setPlainText(
            "1. Détecter WSL.\n"
            "2. Sélectionner la distribution cible.\n"
            "3. Installer depuis le catalogue ou importer un TAR.\n"
            "4. Associer l'environnement.\n"
            "5. Tester le gestionnaire."
        )

        layout.addWidget(
            self.envnote, 1
        )

    # ========================================================
    # CHANGEMENTS DE CONFIGURATION
    # ========================================================

    def change_distro(self, *_):
        family = self.distro.currentText()

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(
            VERSIONS[family]
        )
        self.release.blockSignals(False)

        self.init.blockSignals(True)
        self.init.clear()
        self.init.addItems(
            INIT[family]
        )
        self.init.blockSignals(False)

        old = self.desktop.currentText()

        self.desktop.blockSignals(True)
        self.desktop.clear()

        self.desktop.addItems(
            ["Aucun"] + list(DESKTOP[family])
        )

        if old in DESKTOP[family]:
            self.desktop.setCurrentText(old)

        self.desktop.blockSignals(False)

        self.apps.clear()
        self.refresh_apps()
        self.change_desktop()

    def change_desktop(self, *_):
        desktop = self.desktop.currentText()

        if desktop == "Aucun":
            target = "Aucun"

        elif (
            desktop == "Xfce"
            or self.distro.currentText() == "Slackware"
        ):
            target = "X11"

        else:
            target = "Wayland"

        self.display.blockSignals(True)
        self.display.setCurrentText(target)
        self.display.blockSignals(False)

        self.invalidate()

    def invalidate(self, *_):
        self.revision += 1

        self.solution = {}
        self.report = ""
        self.signature = None

        if hasattr(self, "systemnote"):
            self.systemnote.setText(
                "Configuration modifiée : "
                "recalcul des dépendances requis."
            )

    def refresh_apps(self):
        if hasattr(self, "selected"):
            self.fill(
                self.selected,
                [(app,) for app in sorted(self.apps)]
            )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):
            QMessageBox.warning(
                self,
                "Paquet",
                "Nom invalide"
            )
            return

        self.apps.add(name)
        self.manual.clear()
        self.refresh_apps()
        self.invalidate()

    def add_result(self, row, _):
        item = self.results.item(row, 0)

        if item:
            self.apps.add(item.text())
            self.refresh_apps()
            self.invalidate()

    def remove_app(self, row, _):
        item = self.selected.item(row, 0)

        if item:
            self.apps.discard(item.text())
            self.refresh_apps()
            self.invalidate()

            self.appnote.setText(
                "Application retirée. Relancer la résolution "
                "pour éliminer ses dépendances orphelines."
            )

    def env(self):
        return self.envs.get(
            self.distro.currentText(), ""
        )

    def assign(self, family, value):
        self.envs[family] = (
            ""
            if value == "— Non configuré —"
            else value
        )

        self.invalidate()

    # ========================================================
    # EXÉCUTION ASYNCHRONE
    # ========================================================

    def job(self, kind, args, callback):
        if self.worker is not None:
            QMessageBox.information(
                self,
                "Patiente",
                "Une opération WSL est déjà en cours."
            )
            return

        worker = Worker(kind, *args)
        self.worker = worker

        worker.completed.connect(callback)

        worker.finished.connect(
            lambda: self.finished(worker)
        )

        worker.start()

    def finished(self, worker):
        if self.worker is worker:
            self.worker = None

        worker.deleteLater()

    # ========================================================
    # DÉTECTION WSL2
    # ========================================================

    def detect(self):
        self.envnote.setPlainText(
            "Détection en cours..."
        )

        self.job(
            "detect",
            (),
            self.detect_done
        )

    def detect_done(self, data, error):
        if error:
            self.envnote.setPlainText(
                "Erreur : " + error
            )
            return

        self.installed = data

        for family, combo in self.envcombos.items():
            old = self.envs[family]

            combo.blockSignals(True)
            combo.clear()

            combo.addItems(
                ["— Non configuré —"] + data
            )

            if old in data:
                combo.setCurrentText(old)
            else:
                self.envs[family] = ""

            combo.blockSignals(False)

        self.envnote.setPlainText(
            "Distributions installées :\n"
            + (
                "\n".join(data)
                if data
                else "Aucune"
            )
            + "\n\nUbuntu ne doit pas être associé "
              "à Fedora ou Arch Linux. "
              "Utiliser le gestionnaire natif "
              "de la distribution cible."
        )

    # ========================================================
    # CATALOGUE OFFICIEL WSL
    # ========================================================

    def catalog(self):
        self.envnote.setPlainText(
            "Interrogation du catalogue WSL officiel..."
        )

        self.job(
            "catalog",
            (),
            self.catalog_done
        )

    def catalog_done(self, data, error):
        if error:
            self.envnote.setPlainText(
                "Erreur : " + error
            )
            return

        self.catalog_text = data

        self.envnote.setPlainText(
            data
            + "\n\nUtiliser le nom exact du catalogue. "
              "Gentoo et Slackware nécessitent "
              "généralement un import local."
        )

    # ========================================================
    # INSTALLATION D'UNE DISTRIBUTION WSL
    # ========================================================

    def install(self):
        family = self.distro.currentText()

        if family in ("Gentoo", "Slackware"):
            QMessageBox.information(
                self,
                "Import",
                "Utilise « Importer Gentoo / Slackware » "
                "avec une archive TAR fiable."
            )
            return

        if not self.catalog_text:
            QMessageBox.information(
                self,
                "Catalogue",
                "Cliquer d'abord sur "
                "« Catalogue officiel WSL »."
            )
            return

        default_name = (
            "archlinux"
            if family == "Arch Linux"
            else family
        )

        name, ok = QInputDialog.getText(
            self,
            "Nom WSL",
            "Saisir le nom EXACT affiché par "
            "wsl --list --online :",
            text=default_name
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}",
            name
        ):
            QMessageBox.warning(
                self,
                "Nom",
                "Nom WSL invalide."
            )
            return

        if name.casefold() not in self.catalog_text.casefold():
            QMessageBox.warning(
                self,
                "Catalogue",
                "Nom absent du catalogue affiché. "
                "Vérifie le nom exact."
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Installer WSL",
            f"Installer « {name} » ?\n\n"
            f"Commande : wsl --install -d {name} --no-launch\n\n"
            "Cette opération peut télécharger plusieurs Go "
            "et modifier Windows.\n"
            "Un redémarrage peut être nécessaire."
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        self.envnote.setPlainText(
            "Installation en cours : " + name
            + "\nCette opération peut durer plusieurs minutes."
        )

        self.job(
            "install",
            (name,),
            self.install_done
        )

    def install_done(self, data, error):
        if error:
            self.envnote.setPlainText(
                "Erreur : " + error
            )
        else:
            self.envnote.setPlainText(
                "Installation demandée.\n"
                + data
                + "\n\nDétecter à nouveau les environnements. "
                  "Initialiser la distribution si nécessaire."
            )

    # ========================================================
    # IMPORT GENTOO / SLACKWARE
    # ========================================================

    def import_custom(self):
        family = self.distro.currentText()

        if family not in ("Gentoo", "Slackware"):
            QMessageBox.information(
                self,
                "Import",
                "Réservé à Gentoo et Slackware."
            )
            return

        archive, _ = QFileDialog.getOpenFileName(
            self,
            "Archive rootfs TAR locale",
            "",
            "Archives TAR (*.tar *.tar.gz *.tgz)"
        )

        if not archive:
            return

        destination = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier parent pour WSL",
            str(Path.home())
        )

        if not destination:
            return

        name, ok = QInputDialog.getText(
            self,
            "Nom WSL",
            "Nom unique de la distribution à importer :",
            text=family + "-ULB"
        )

        if not ok:
            return

        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}",
            name
        ):
            QMessageBox.warning(
                self,
                "Nom",
                "Nom WSL invalide."
            )
            return

        target = str(
            Path(destination) / name
        )

        if Path(target).exists():
            QMessageBox.warning(
                self,
                "Dossier",
                "Le dossier cible existe déjà."
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Confirmer l'import",
            f"Importer l'archive sélectionnée dans :\n"
            f"{target}\n\n"
            "Vérifie sa provenance et sa compatibilité WSL2."
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        self.envnote.setPlainText(
            "Import en cours..."
        )

        self.job(
            "import",
            (name, target, archive),
            self.install_done
        )

    # ========================================================
    # TEST DU GESTIONNAIRE DE PAQUETS
    # ========================================================

    def test(self):
        env = self.env()

        if not env:
            QMessageBox.warning(
                self,
                "WSL",
                "Associer un environnement "
                "à la distribution sélectionnée."
            )
            return

        self.envnote.setPlainText(
            "Test de " + env + "..."
        )

        self.job(
            "identify",
            (env,),
            self.test_done
        )

    def test_done(self, data, error):
        if error:
            self.envnote.setPlainText(
                "Erreur : " + error
            )
            return

        family = self.distro.currentText()
        manager = MANAGERS[family]

        self.envnote.setPlainText(
            data
            + "\n\nVérifier ID/VERSION_ID "
              "et la présence de "
            + manager
            + ".\nLa correspondance exacte avec "
            + self.release.currentText()
            + " n'est pas automatiquement garantie."
        )

    # ========================================================
    # RECHERCHE D'APPLICATIONS
    # ========================================================

    def search(self):
        env = self.env()
        query = self.query.text().strip()

        if not env:
            QMessageBox.warning(
                self,
                "WSL",
                "Installer et associer un environnement "
                "dans Prérequis WSL2."
            )
            return

        if not query or len(query) > 70:
            QMessageBox.warning(
                self,
                "Recherche",
                "Recherche de 1 à 70 caractères."
            )
            return

        revision = self.revision

        self.appnote.setText(
            "Recherche native en cours..."
        )

        self.job(
            "search",
            (
                env,
                self.distro.currentText(),
                query
            ),
            lambda data, error:
                self.search_done(
                    data, error, revision
                )
        )

    def search_done(self, data, error, revision):
        if revision != self.revision:
            return

        if error:
            self.appnote.setText(
                "Erreur : " + error
            )
            return

        self.fill(
            self.results, data
        )

        self.appnote.setText(
            f"{len(data)} résultats reconnus. "
            "Les formats de sortie natifs peuvent varier."
        )

    # ========================================================
    # CONSTRUCTION DE LA LISTE DES PAQUETS
    # ========================================================

    def categories(self):
        family = self.distro.currentText()
        extra = EXTRA[family]

        init_packages = []

        if family == "Gentoo":
            init_packages = [
                "sys-apps/openrc"
                if self.init.currentText() == "OpenRC"
                else "sys-apps/systemd"
            ]

        categories = {
            "Base": extra["Base"][:],
            "Initialisation": init_packages,
            "Noyau": KERNEL[family].get(
                self.kernel.currentText(), []
            )[:],
            "Bureau": DESKTOP[family].get(
                self.desktop.currentText(), []
            )[:],
            "Audio": AUDIO[family].get(
                self.audio.currentText(), []
            )[:],
            "Affichage": (
                extra.get(
                    self.display.currentText(), []
                )[:]
                if self.desktop.currentText() != "Aucun"
                else []
            ),
            "GRUB": (
                GRUB[family][
                    self.bootmode.currentText()
                ][:]
                if self.boot.currentText() == "GRUB"
                else []
            ),
            "Applications": sorted(self.apps)
        }

        for key, checkbox in self.flags.items():
            categories[key] = (
                extra.get(key, [])[:]
                if checkbox.isChecked()
                else []
            )

        return categories

    def seeds(self):
        return sorted({
            package
            for values in self.categories().values()
            for package in values
        })

    def fingerprint(self):
        return json.dumps(
            [
                self.distro.currentText(),
                self.release.currentText(),
                self.env(),
                self.init.currentText(),
                self.categories()
            ],
            sort_keys=True
        )

    # ========================================================
    # RÉSOLUTION DES DÉPENDANCES
    # ========================================================

    def resolve(self):
        env = self.env()
        family = self.distro.currentText()

        if not env:
            QMessageBox.warning(
                self,
                "Prérequis",
                "Installer et associer "
                "un environnement WSL2."
            )

            self.tabs.setCurrentIndex(4)
            return

        if self.kernel.currentText() not in KERNEL[family]:
            QMessageBox.warning(
                self,
                "Noyau",
                "Variante de noyau non disponible "
                "dans ce profil."
            )
            return

        packages = self.seeds()

        if not packages:
            return

        revision = self.revision
        signature = self.fingerprint()

        self.systemnote.setText(
            "Simulation native en cours..."
        )

        self.job(
            "solve",
            (env, family, packages),
            lambda data, error:
                self.resolve_done(
                    data,
                    error,
                    revision,
                    signature
                )
        )

    def resolve_done(
        self, data, error, revision, signature
    ):
        if revision != self.revision:
            return

        if error:
            self.systemnote.setText(
                "Erreur de résolution : " + error
            )
            return

        self.solution, self.report, stderr, code = data

        self.signature = signature

        self.systemnote.setText(
            f"{len(self.solution)} paquets identifiés "
            f"(analyse indicative). "
            f"Code gestionnaire : {code}."
        )

        self.report += (
            "\n\nSTDERR:\n" + stderr
        )

        self.verify()

    # ========================================================
    # VÉRIFICATION DU PROJET
    # ========================================================

    def verify(self):
        fresh = (
            self.signature == self.fingerprint()
        )

        if fresh:
            items = self.solution
        else:
            items = {
                package: {
                    "version": "?",
                    "bytes": None,
                    "status": "Demandé non résolu"
                }
                for package in self.seeds()
            }

        rows = []
        known = 0
        unknown = 0

        for name, info in sorted(items.items()):
            size = info.get("bytes")

            known += size or 0
            unknown += size is None

            rows.append((
                name,
                info.get("version", "?"),
                info.get("status", "?"),
                (
                    f"{size / 1048576:.2f} Mio"
                    if size is not None
                    else "Inconnue"
                )
            ))

        self.fill(
            self.preview, rows
        )

        warnings = [
            "Analyse native expérimentale : "
            "exhaustivité non garantie.",

            "La simulation utilise les paquets déjà "
            "installés dans WSL, ce qui peut sous-estimer "
            "les dépendances de la future ISO.",

            "Aucune taille ISO fiable sans système "
            "de fichiers final et compression.",

            "Le démarrage Live et le GRUB installé "
            "par Calamares sont distincts."
        ]

        if not fresh:
            warnings.insert(
                0,
                "Analyse absente ou obsolète."
            )

        if self.distro.currentText() == "Slackware":
            warnings.append(
                "Slackware ne résout pas automatiquement "
                "les dépendances."
            )

        if self.distro.currentText() == "Gentoo":
            warnings.append(
                "Gentoo : vérifier profil Portage, "
                "USE flags et OpenRC/systemd."
            )

        family = self.distro.currentText()

        if (
            self.flags["Calamares"].isChecked()
            and not EXTRA[family]["Calamares"]
        ):
            warnings.append(
                "Calamares non validé dans les dépôts "
                "de cette distribution."
            )

        self.summary.setText(
            f"{len(items)} paquets affichés · "
            f"{unknown} tailles inconnues · "
            f"{known / 1048576:.1f} Mio connus "
            "(PAS une estimation de taille ISO)."
        )

        self.projectreport.setPlainText(
            "AVERTISSEMENTS\n"
            + "\n".join(warnings)
            + "\n\nSORTIE NATIVE\n"
            + (
                self.report
                if fresh
                else "Lancer une analyse."
            )
        )

        return {
            "app_version": VERSION,
            "distribution": family,
            "release": self.release.currentText(),
            "wsl_environment": self.env(),
            "init_system": self.init.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentText(),
            "bootloader": self.boot.currentText(),
            "boot_mode": self.bootmode.currentText(),
            "categories": self.categories(),
            "applications": sorted(self.apps),
            "packages": items,
            "analysis_fresh": fresh,
            "warnings": warnings,
            "known_bytes": known,
            "unknown_sizes": unknown
        }

    # ========================================================
    # EXPORT DU PROJET
    # ========================================================

    def export(self):
        data = self.verify()

        folder = QFileDialog.getExistingDirectory(
            self,
            "Dossier vide pour exporter",
            str(Path.home())
        )

        if not folder:
            return

        path = Path(folder)

        if any(path.iterdir()):
            QMessageBox.warning(
                self,
                "Export",
                "Choisir un dossier vide."
            )
            return

        (path / "project_v1_9.json").write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_9.txt").write_text(
            "\n".join(data["packages"]) + "\n",
            encoding="utf-8"
        )

        (path / "native_report_v1_9.txt").write_text(
            (
                self.report
                if data["analysis_fresh"]
                else "Analyse non disponible"
            ),
            encoding="utf-8"
        )

        (path / "README_v1_9.txt").write_text(
            "Universal Linux Builder v1.9\n\n"
            "Export de préparation.\n"
            "Aucune ISO amorçable créée.\n\n"
            "Dépendances et tailles à valider dans "
            "un environnement propre correspondant "
            "à la version cible.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Projet exporté.\nAucune ISO créée."
        )


# ============================================================
# DÉMARRAGE
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Main()
    window.show()

    sys.exit(app.exec())

