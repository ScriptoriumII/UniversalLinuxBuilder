import sys
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
    QLabel, QCheckBox, QTextEdit, QFileDialog,
    QMessageBox, QInputDialog, QSplitter, QGroupBox
)

VERSION = "1.11"

FAMILIES = [
    "Debian",
    "Fedora",
    "Arch Linux",
    "Gentoo",
    "Slackware"
]

RELEASES = {
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

BASE = {
    "Debian": [
        "linux-image-amd64",
        "systemd-sysv",
        "network-manager",
        "sudo"
    ],
    "Fedora": [
        "kernel",
        "systemd",
        "NetworkManager",
        "sudo"
    ],
    "Arch Linux": [
        "base",
        "linux",
        "networkmanager",
        "sudo"
    ],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
        "sys-apps/openrc",
        "net-misc/networkmanager"
    ],
    "Slackware": [
        "kernel-generic",
        "networkmanager"
    ]
}

DESKTOP = {
    "Debian": {
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "lightdm"]
    },
    "Fedora": {
        "GNOME": ["gnome-shell", "gnome-session", "gdm"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": [
            "xfce4-session",
            "xfce4-panel",
            "xfwm4",
            "lightdm"
        ],
        "Budgie": ["budgie-desktop", "gdm"]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "gdm"]
    },
    "Gentoo": {
        "GNOME": [
            "gnome-base/gnome",
            "gnome-base/gdm"
        ],
        "KDE Plasma": [
            "kde-plasma/plasma-meta",
            "x11-misc/sddm"
        ],
        "Xfce": [
            "xfce-base/xfce4-meta",
            "x11-misc/lightdm"
        ],
        "Budgie": ["gnome-extra/budgie-desktop"]
    },
    "Slackware": {
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel"]
    }
}

AUDIO = {
    "Debian": {
        "PipeWire": [
            "pipewire",
            "wireplumber",
            "pipewire-pulse"
        ],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Fedora": {
        "PipeWire": [
            "pipewire",
            "wireplumber",
            "pipewire-pulseaudio"
        ],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Arch Linux": {
        "PipeWire": [
            "pipewire",
            "wireplumber",
            "pipewire-pulse"
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

EXTRAS = {
    "Debian": {
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["firmware-linux-free"],
        "Calamares": ["calamares"]
    },
    "Fedora": {
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": []
    },
    "Arch Linux": {
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": ["calamares"]
    },
    "Gentoo": {
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmware": ["sys-kernel/linux-firmware"],
        "Calamares": []
    },
    "Slackware": {
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["kernel-firmware"],
        "Calamares": []
    }
}

SAFE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

DARK = """
QWidget {
    background: #151c29;
    color: #eef3fb;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #202c3d;
    border: 1px solid #42546a;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #2c4562;
    border: 1px solid #53718f;
    border-radius: 6px;
    padding: 7px 11px;
}
QPushButton:hover {
    background: #3b5d82;
}
QTabBar::tab {
    padding: 9px 14px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #61a7ff;
}
QHeaderView::section {
    background: #2c4562;
    padding: 6px;
}
"""

LIGHT = """
QWidget {
    background: #f6f8fb;
    color: #1a2739;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: white;
    border: 1px solid #bdccdb;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #e1eaf5;
    border: 1px solid #bdccdb;
    border-radius: 6px;
    padding: 7px 11px;
}
QPushButton:hover {
    background: #cbdff5;
}
QTabBar::tab {
    padding: 9px 14px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #2674db;
}
QHeaderView::section {
    background: #e1eaf5;
    padding: 6px;
}
"""


# ============================================================
# COMMANDES WINDOWS ET WSL
# ============================================================

def run(argv, timeout=180, check=True):
    process = subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        creationflags=getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0
        )
    )

    def decode(data):
        if b"\x00" in data:
            return data.decode(
                "utf-16-le",
                "replace"
            ).replace("\ufeff", "")

        return data.decode("utf-8", "replace")

    output = decode(process.stdout)
    error = decode(process.stderr)

    if check and process.returncode:
        raise RuntimeError(
            (error or output or str(process.returncode))[-3000:]
        )

    return output, error, process.returncode


def installed():
    output, _, _ = run(
        ["wsl.exe", "--list", "--quiet"],
        40
    )

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


def catalog():
    output, _, _ = run(
        ["wsl.exe", "--list", "--online"],
        45
    )

    entries = []
    active = False

    for line in output.splitlines():
        value = line.strip()

        if re.search(
            r"\bNAME\s+FRIENDLY NAME\b",
            value,
            re.I
        ):
            active = True
            continue

        if re.search(
            r"\bNOM\s+NOM CONVIVIAL\b",
            value,
            re.I
        ):
            active = True
            continue

        if not active or not value or value.startswith("-"):
            continue

        match = re.match(
            r"^([\w.-]+)\s{2,}(.+)$",
            value
        )

        if match:
            entries.append(
                (match.group(1), match.group(2))
            )

    return entries, output


def wsl(env, script, timeout=180, check=True):
    return run(
        [
            "wsl.exe",
            "--distribution", env,
            "--exec",
            "/bin/sh",
            "-lc",
            script
        ],
        timeout,
        check
    )


def detect_native_manager(env):
    """
    Détecte le gestionnaire directement dans la distribution
    WSL sélectionnée, indépendamment du projet ISO.
    """

    command = (
        "if command -v apt-get >/dev/null 2>&1; then "
        "echo Debian; "
        "elif command -v dnf5 >/dev/null 2>&1; then "
        "echo Fedora; "
        "elif command -v pacman >/dev/null 2>&1; then "
        "echo 'Arch Linux'; "
        "elif command -v emerge >/dev/null 2>&1; then "
        "echo Gentoo; "
        "elif command -v slackpkg >/dev/null 2>&1; then "
        "echo Slackware; "
        "else echo UNKNOWN; fi"
    )

    output, stderr, code = wsl(
        env,
        command,
        60,
        False
    )

    if code != 0:
        raise RuntimeError(
            stderr or output or "Détection impossible"
        )

    family = output.strip().splitlines()[-1].strip()

    if family not in MANAGERS:
        raise RuntimeError(
            "Aucun gestionnaire compatible détecté dans "
            + env
        )

    return family


def update_selected_environment(env):
    """
    Actualise les dépôts de la distribution WSL sélectionnée.
    Ne dépend pas de l'onglet Distribution.
    """

    family = detect_native_manager(env)

    command = update_command(family)

    # L'actualisation nécessite généralement root.
    # WSL permet de choisir explicitement l'utilisateur root.
    result = run(
        [
            "wsl.exe",
            "--distribution", env,
            "--user", "root",
            "--exec",
            "/bin/sh",
            "-lc",
            command
        ],
        1800,
        False
    )

    return family, command, result


def probe(env):
    command = (
        "cat /etc/os-release; "
        "echo __TOOLS__; "
        "for x in apt-cache apt-get dnf5 pacman "
        "emerge slackpkg; "
        'do command -v "$x" || true; done'
    )

    output, _, _ = wsl(
        env,
        command,
        60
    )

    found = [
        family
        for family, manager in MANAGERS.items()
        if re.search(
            r"(?m)^\S*/" + re.escape(manager) + r"$",
            output
        )
    ]

    return output, found


# ============================================================
# GESTIONNAIRES DE PAQUETS
# ============================================================

def update_command(family):
    commands = {
        "Debian": "apt-get update",
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman -Sy",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    return commands[family]


def search_command(family, query):
    query = shlex.quote(query)

    commands = {
        "Debian": "apt-cache search " + query,
        "Fedora": "dnf5 search " + query,
        "Arch Linux": "pacman -Ss " + query,
        "Gentoo": "emerge --search " + query,
        "Slackware": "slackpkg search " + query
    }

    return commands[family]


def parse_search(family, output):
    rows = []
    seen = set()

    for line in output.splitlines():
        value = line.strip()
        name = ""
        version = "?"
        description = ""

        if family == "Debian":
            match = re.match(
                r"^([\w+.-]+)\s+-\s+(.+)$",
                value
            )

            if match:
                name, description = match.groups()

        elif family == "Fedora":
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|noarch|aarch64|i686|src)"
                r"\s*:\s*(.+)$",
                value
            )

            if match:
                name, description = match.groups()
            else:
                match = re.match(
                    r"^([\w+.-]+)\."
                    r"(?:x86_64|noarch|aarch64|i686|src)"
                    r"\s+(.+)$",
                    value
                )

                if match:
                    name, description = match.groups()

        elif family == "Arch Linux":
            match = re.match(
                r"^[\w+.-]+/([^ ]+)\s+([^ ]+)",
                value
            )

            if match:
                name, version = match.groups()

        elif family == "Gentoo":
            match = re.search(
                r"^\*\s+([\w+.-]+/[\w+.-]+)",
                value
            )

            if match:
                name = match.group(1)

        elif family == "Slackware":
            match = re.search(
                r"([\w+.-]+)-([0-9][\w.+-]*)-"
                r"(?:x86_64|noarch|i[3-6]86)",
                value
            )

            if match:
                name, version = match.groups()

        if (
            name
            and SAFE.fullmatch(name)
            and name not in seen
        ):
            rows.append(
                (name, version, description[:200])
            )
            seen.add(name)

    return rows[:500]


def simulate(family, packages):
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
            'echo "Slackware ne dispose pas '
            'de solveur natif complet"'
        )
    }

    return commands[family]


def parse_simulation(family, output, requested):
    result = {
        package: {
            "version": "?",
            "status": "Demandé"
        }
        for package in requested
    }

    for line in output.splitlines():
        match = None

        if family == "Debian":
            match = re.match(
                r"^Inst\s+(\S+)"
                r"(?:\s+\[.*?\])?"
                r"\s+\(([^ )]+)",
                line
            )

        elif family == "Arch Linux":
            match = re.match(
                r"^([^|]+)\|([^|]+)\|\d+$",
                line.strip()
            )

        elif family == "Fedora":
            match = re.match(
                r"^\s*([\w+.-]+)\s+"
                r"(?:x86_64|noarch|aarch64|i686)"
                r"\s+([\w:~.+-]+)\s+",
                line
            )

        elif family == "Gentoo":
            match = re.search(
                r"\[ebuild[^]]*\]\s+"
                r"([\w+.-]+/[\w+.-]+)-"
                r"([\w.+-]+)",
                line
            )

        if match:
            result[match.group(1)] = {
                "version": match.group(2),
                "status": "Simulation"
            }

    return result


# ============================================================
# TÂCHES ASYNCHRONES
# ============================================================

class Task(QThread):
    result = Signal(object, str)

    def __init__(self, kind, *args):
        super().__init__()

        self.kind = kind
        self.args = args

    def run(self):
        try:
            kind = self.kind
            args = self.args

            if kind == "installed":
                value = installed()

            elif kind == "catalog":
                value = catalog()

            elif kind == "probe":
                value = probe(args[0])

            elif kind == "install":
                value = run(
                    [
                        "wsl.exe",
                        "--install",
                        "--distribution",
                        args[0],
                        "--no-launch"
                    ],
                    1800
                )

            elif kind == "delete":
                value = run(
                    [
                        "wsl.exe",
                        "--unregister",
                        args[0]
                    ],
                    900
                )

            elif kind == "import":
                value = run(
                    [
                        "wsl.exe",
                        "--import",
                        args[0],
                        args[1],
                        args[2],
                        "--version",
                        "2"
                    ],
                    1800
                )

            elif kind == "update":
                value = update_selected_environment(
                    args[0]
                )

            elif kind == "search":
                value = wsl(
                    args[0],
                    search_command(args[1], args[2]),
                    180,
                    False
                )

            elif kind == "solve":
                value = wsl(
                    args[0],
                    simulate(args[1], args[2]),
                    360,
                    False
                )

            else:
                raise ValueError("Tâche inconnue")

            self.result.emit(value, "")

        except Exception as error:
            self.result.emit(None, str(error))


# ============================================================
# INTERFACE PRINCIPALE
# ============================================================

class App(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.11"
        )

        self.resize(1320, 880)

        self.assoc = {
            family: ""
            for family in FAMILIES
        }

        self.available = []
        self.existing = []
        self.apps = set()
        self.resolved = {}
        self.native = ""
        self.current_task = None
        self.generation = 0
        self.analysis_gen = -1

        center = QWidget()
        self.setCentralWidget(center)

        main = QVBoxLayout(center)

        top = QHBoxLayout()

        heading = QLabel(
            "Universal Linux Builder  |  v1.11"
        )

        heading.setStyleSheet(
            "font-size:21px;font-weight:bold"
        )

        top.addWidget(heading)
        top.addStretch()
        top.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems(["Sombre", "Clair"])

        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        top.addWidget(self.theme)
        main.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDocumentMode(True)

        main.addWidget(self.tabs)

        self.build_distribution()
        self.build_system()
        self.build_apps()
        self.build_project()
        self.build_wsl()

        self.status = QLabel(
            "Prêt. Détecte les environnements "
            "WSL2 dans le dernier onglet."
        )

        main.addWidget(self.status)

        self.apply_theme()
        self.change_family()

    def apply_theme(self, *_):
        self.setStyleSheet(
            DARK
            if self.theme.currentText() == "Sombre"
            else LIGHT
        )

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            16, 14, 16, 14
        )

        layout.setSpacing(9)

        self.tabs.addTab(widget, name)

        return layout

    def button(self, text, function):
        button = QPushButton(text)
        button.clicked.connect(function)
        return button

    def combo(self, items):
        combo = QComboBox()
        combo.addItems(items)
        return combo

    def table(self, headers):
        table = QTableWidget(
            0,
            len(headers)
        )

        table.setHorizontalHeaderLabels(headers)

        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

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

    def chosen(self, table):
        row = table.currentRow()

        item = (
            table.item(row, 0)
            if row >= 0
            else None
        )

        return item.text() if item else ""

    def message(self, title, body):
        QMessageBox.information(
            self,
            title,
            body
        )

    def fail(self, body):
        QMessageBox.warning(
            self,
            "Universal Linux Builder",
            body
        )

    def task(self, kind, args, callback):
        if self.current_task is not None:
            self.fail(
                "Une opération WSL est déjà en cours."
            )
            return

        worker = Task(kind, *args)

        self.current_task = worker

        self.status.setText(
            "Opération en cours : " + kind
        )

        worker.result.connect(callback)

        worker.finished.connect(
            lambda w=worker: self.task_finished(w)
        )

        worker.start()

    def task_finished(self, worker):
        if self.current_task is worker:
            self.current_task = None

        worker.deleteLater()

        self.status.setText("Prêt")

    def invalidate(self, *_):
        self.generation += 1
        self.analysis_gen = -1
        self.resolved = {}

    def family(self):
        return self.family_box.currentText()

    def env(self):
        return self.assoc.get(
            self.family(),
            ""
        )

    # ========================================================
    # DISTRIBUTION
    # ========================================================

    def build_distribution(self):
        layout = self.page("Distribution")

        form = QFormLayout()

        self.family_box = self.combo(FAMILIES)
        self.release = self.combo([])

        form.addRow(
            "Distribution Linux",
            self.family_box
        )

        form.addRow(
            "Version cible",
            self.release
        )

        layout.addLayout(form)

        label = QLabel(
            "Les dépôts WSL doivent correspondre "
            "à la distribution ET à la version cible. "
            "Une installation Ubuntu ne remplace pas "
            "Fedora, Arch ou Gentoo."
        )

        label.setWordWrap(True)

        layout.addWidget(label)
        layout.addStretch()

        self.family_box.currentTextChanged.connect(
            self.change_family
        )

        self.release.currentTextChanged.connect(
            self.invalidate
        )

    # ========================================================
    # SYSTÈME
    # ========================================================

    def build_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo(["Aucun"])

        self.kernel = self.combo([
            "Stable",
            "LTS",
            "Hardened"
        ])

        self.init = self.combo([])

        self.display = self.combo([
            "Wayland",
            "X11",
            "Aucun"
        ])

        self.audio = self.combo([
            "PipeWire",
            "PulseAudio",
            "ALSA",
            "Aucun"
        ])

        self.boot = self.combo([
            "GRUB",
            "Aucun"
        ])

        self.bootmode = self.combo([
            "UEFI",
            "BIOS"
        ])

        fields = [
            ("Bureau", self.desktop),
            ("Noyau", self.kernel),
            ("Initialisation", self.init),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Bootloader", self.boot),
            ("Démarrage", self.bootmode)
        ]

        for label, widget in fields:
            form.addRow(label, widget)

            widget.currentTextChanged.connect(
                self.invalidate
            )

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

            checkbox.toggled.connect(
                self.invalidate
            )

            self.flags[name] = checkbox

            layout.addWidget(checkbox)

        layout.addWidget(
            self.button(
                "Analyser les dépendances du projet",
                self.solve
            )
        )

        layout.addStretch()

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def build_apps(self):
        layout = self.page("Applications")

        row = QHBoxLayout()

        self.query = QLineEdit()

        self.query.setPlaceholderText(
            "Ex. firefox, vlc, gimp"
        )

        self.query.returnPressed.connect(
            self.search
        )

        row.addWidget(self.query)

        row.addWidget(
            self.button(
                "Rechercher",
                self.search
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_repo
            )
        )

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Catalogue : double-cliquer sur "
                "un paquet pour l’ajouter"
            )
        )

        self.search_table = self.table([
            "Paquet",
            "Version",
            "Description"
        ])

        self.search_table.setColumnWidth(0, 290)
        self.search_table.setColumnWidth(1, 130)

        self.search_table.cellDoubleClicked.connect(
            self.add_search
        )

        layout.addWidget(
            self.search_table,
            3
        )

        layout.addWidget(
            QLabel(
                "Applications sélectionnées : "
                "double-cliquer pour supprimer"
            )
        )

        self.app_table = self.table([
            "Paquet"
        ])

        self.app_table.cellDoubleClicked.connect(
            self.remove_app
        )

        layout.addWidget(
            self.app_table,
            1
        )

        row = QHBoxLayout()

        self.manual = QLineEdit()

        self.manual.setPlaceholderText(
            "Nom exact du paquet"
        )

        row.addWidget(self.manual)

        row.addWidget(
            self.button(
                "Ajouter",
                self.add_manual
            )
        )

        layout.addLayout(row)

        self.search_log = QTextEdit()
        self.search_log.setReadOnly(True)
        self.search_log.setMaximumHeight(115)

        layout.addWidget(self.search_log)

    # ========================================================
    # PROJET
    # ========================================================

    def build_project(self):
        layout = self.page("Projet / ISO")

        self.project_info = QLabel(
            "Aucune analyse."
        )

        layout.addWidget(self.project_info)

        self.project_table = self.table([
            "Paquet",
            "Version",
            "Statut"
        ])

        layout.addWidget(
            self.project_table,
            2
        )

        self.project_log = QTextEdit()
        self.project_log.setReadOnly(True)

        layout.addWidget(
            self.project_log,
            1
        )

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Analyser",
                self.solve
            )
        )

        row.addWidget(
            self.button(
                "Exporter le projet",
                self.export
            )
        )

        layout.addLayout(row)

    # ========================================================
    # NOUVELLE INTERFACE WSL2
    # ========================================================

    def build_wsl(self):
        layout = self.page("WSL2")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Actualiser les installations",
                self.detect
            )
        )

        row.addWidget(
            self.button(
                "Charger le catalogue WSL",
                self.load_catalog
            )
        )

        row.addStretch()
        layout.addLayout(row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        # Catalogue disponible

        left = QGroupBox(
            "Distributions disponibles"
        )

        left_layout = QVBoxLayout(left)

        self.catalog_table = self.table([
            "Nom WSL",
            "Description"
        ])

        self.catalog_table.setColumnWidth(
            0,
            210
        )

        left_layout.addWidget(
            self.catalog_table
        )

        left_layout.addWidget(
            self.button(
                "Installer la distribution sélectionnée",
                self.install_selected
            )
        )

        splitter.addWidget(left)

        # Distributions installées

        right = QGroupBox(
            "Distributions installées"
        )

        right_layout = QVBoxLayout(right)

        self.installed_table = self.table([
            "Nom WSL"
        ])

        right_layout.addWidget(
            self.installed_table
        )

        right_layout.addWidget(
            self.button(
                "Supprimer la distribution sélectionnée",
                self.delete_selected
            )
        )

        splitter.addWidget(right)
        splitter.setSizes([680, 420])

        layout.addWidget(splitter, 3)

        # Test indépendant

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Environnement à tester :")
        )

        self.test_env = self.combo([])

        row.addWidget(
            self.test_env,
            1
        )

        row.addWidget(
            self.button(
                "Tester le gestionnaire",
                self.test_manager
            )
        )

        row.addWidget(
            self.button(
                "Mettre à jour les dépôts",
                self.update_selected_repo
            )
        )

        layout.addLayout(row)

        # Associations WSL / distributions

        form = QFormLayout()

        self.mapping = {}

        for family in FAMILIES:
            combo = self.combo([
                "— Non associé —"
            ])

            combo.currentTextChanged.connect(
                lambda name, f=family:
                    self.associate(f, name)
            )

            form.addRow(
                family,
                combo
            )

            self.mapping[family] = combo

        layout.addLayout(form)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Importer Gentoo / Slackware (TAR)",
                self.import_tar
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setMaximumHeight(170)

        layout.addWidget(
            self.wsl_log,
            1
        )

        self.wsl_log.setPlainText(
            "1. Charger le catalogue WSL.\n"
            "2. Installer une distribution.\n"
            "3. Actualiser les installations.\n"
            "4. Associer chaque famille à son environnement.\n"
            "5. Mettre à jour les dépôts."
        )

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def change_family(self, *_):
        family = self.family()

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(
            RELEASES[family]
        )
        self.release.blockSignals(False)

        self.desktop.blockSignals(True)
        self.desktop.clear()

        self.desktop.addItems(
            ["Aucun"] + list(DESKTOP[family])
        )

        self.desktop.blockSignals(False)

        self.init.blockSignals(True)
        self.init.clear()

        if family == "Gentoo":
            self.init.addItems([
                "OpenRC",
                "systemd"
            ])

        elif family == "Slackware":
            self.init.addItems([
                "SysVinit"
            ])

        else:
            self.init.addItems([
                "systemd"
            ])

        self.init.blockSignals(False)

        self.kernel.setEnabled(
            family == "Arch Linux"
        )

        self.kernel.setCurrentText(
            "Stable"
        )

        self.apps.clear()
        self.refresh_apps()
        self.invalidate()

    def associate(self, family, name):
        self.assoc[family] = (
            ""
            if name == "— Non associé —"
            else name
        )

        self.invalidate()

    def refresh_apps(self):
        self.fill(
            self.app_table,
            [
                (package,)
                for package in sorted(self.apps)
            ]
        )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):
            self.fail(
                "Nom de paquet invalide."
            )
            return

        self.apps.add(name)
        self.manual.clear()

        self.refresh_apps()
        self.invalidate()

    def add_search(self, row, _):
        item = self.search_table.item(
            row,
            0
        )

        if item:
            self.apps.add(item.text())

            self.refresh_apps()
            self.invalidate()

    def remove_app(self, row, _):
        item = self.app_table.item(
            row,
            0
        )

        if item:
            self.apps.discard(
                item.text()
            )

            self.refresh_apps()
            self.invalidate()

    # ========================================================
    # DISTRIBUTIONS INSTALLÉES
    # ========================================================

    def detect(self):
        self.task(
            "installed",
            (),
            self.detect_done
        )

    def detect_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Erreur WSL : " + error
            )
            return

        self.existing = data

        self.fill(
            self.installed_table,
            [
                (name,)
                for name in data
            ]
        )

        self.test_env.clear()
        self.test_env.addItems(data)

        for family, combo in self.mapping.items():
            previous = self.assoc[family]

            combo.blockSignals(True)
            combo.clear()

            combo.addItems(
                ["— Non associé —"] + data
            )

            if previous in data:
                combo.setCurrentText(previous)
            else:
                self.assoc[family] = ""

            combo.blockSignals(False)

        self.wsl_log.setPlainText(
            "Installées : "
            + (
                ", ".join(data)
                if data
                else "aucune"
            )
        )

    # ========================================================
    # CATALOGUE WSL
    # ========================================================

    def load_catalog(self):
        self.task(
            "catalog",
            (),
            self.catalog_done
        )

    def catalog_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Catalogue indisponible : " + error
            )
            return

        self.available, raw = data

        self.fill(
            self.catalog_table,
            self.available
        )

        self.wsl_log.setPlainText(
            f"{len(self.available)} distributions reconnues.\n"
            + (
                raw
                if not self.available
                else (
                    "Sélectionne une ligne "
                    "puis clique sur Installer."
                )
            )
        )

    # ========================================================
    # INSTALLATION WSL
    # ========================================================

    def install_selected(self):
        name = self.chosen(
            self.catalog_table
        )

        if not name:
            self.fail(
                "Sélectionne une distribution "
                "dans le catalogue."
            )
            return

        if name in self.existing:
            self.fail(
                "Cette distribution est déjà installée."
            )
            return

        answer = QMessageBox.question(
            self,
            "Installation WSL",
            f"Installer {name} via le catalogue officiel WSL ?\n"
            "Un téléchargement et un redémarrage "
            "peuvent être nécessaires."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.task(
            "install",
            (name,),
            lambda data, error:
                self.operation_done(
                    data,
                    error,
                    "Installation"
                )
        )

    # ========================================================
    # SUPPRESSION WSL
    # ========================================================

    def delete_selected(self):
        name = self.chosen(
            self.installed_table
        )

        if not name:
            self.fail(
                "Sélectionne une distribution installée."
            )
            return

        typed, ok = QInputDialog.getText(
            self,
            "Suppression définitive",
            f"La suppression de {name} effacera "
            "TOUS ses fichiers Linux.\n"
            f"Pour confirmer, saisis exactement : {name}"
        )

        if not ok or typed != name:
            self.fail(
                "Suppression annulée : "
                "confirmation incorrecte."
            )
            return

        answer = QMessageBox.question(
            self,
            "Dernière confirmation",
            f"Exécuter wsl --unregister {name} ?\n"
            "Cette opération est irréversible."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.task(
            "delete",
            (name,),
            lambda data, error:
                self.operation_done(
                    data,
                    error,
                    "Suppression"
                )
        )

    def operation_done(self, data, error, label):
        self.wsl_log.setPlainText(
            label
            + (
                " échouée : " + error
                if error
                else " terminée.\n" + str(data)
            )
        )

        self.detect()

    # ========================================================
    # IMPORT GENTOO / SLACKWARE
    # ========================================================

    def import_tar(self):
        archive, _ = QFileDialog.getOpenFileName(
            self,
            "Archive rootfs locale",
            "",
            "Archives TAR (*.tar *.tar.gz *.tgz)"
        )

        if not archive:
            return

        parent = QFileDialog.getExistingDirectory(
            self,
            "Dossier parent de la distribution"
        )

        if not parent:
            return

        default_name = (
            "Gentoo-ULB"
            if self.family() == "Gentoo"
            else "Slackware-ULB"
        )

        name, ok = QInputDialog.getText(
            self,
            "Nom WSL",
            "Nom de la distribution importée :",
            text=default_name
        )

        if (
            not ok
            or not re.fullmatch(
                r"[A-Za-z0-9][\w.-]{0,79}",
                name
            )
        ):
            self.fail(
                "Nom WSL invalide."
            )
            return

        destination = str(
            Path(parent) / name
        )

        if Path(destination).exists():
            self.fail(
                "Le dossier cible existe déjà."
            )
            return

        answer = QMessageBox.question(
            self,
            "Importer",
            "Importer une archive Linux de confiance "
            f"dans :\n{destination} ?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.task(
            "import",
            (
                name,
                destination,
                archive
            ),
            lambda data, error:
                self.operation_done(
                    data,
                    error,
                    "Importation"
                )
        )

    # ========================================================
    # TEST GESTIONNAIRE
    # ========================================================

    def test_manager(self):
        env = self.test_env.currentText()

        if not env:
            self.fail(
                "Choisis une distribution WSL installée."
            )
            return

        self.task(
            "probe",
            (env,),
            lambda data, error:
                self.probe_done(
                    env,
                    data,
                    error
                )
        )

    def probe_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Test impossible : " + error
            )
            return

        output, found = data

        self.wsl_log.setPlainText(
            "Environnement : " + env
            + "\nGestionnaires détectés : "
            + (
                ", ".join(found)
                if found
                else "aucun"
            )
            + "\n\n"
            + output
        )

    # ========================================================
    # ACTUALISATION WSL2 INDEPENDANTE
    # ========================================================

    def update_selected_repo(self):
        """
        Utilise exclusivement la distribution sélectionnée
        dans le menu WSL2.
        """

        env = self.test_env.currentText().strip()

        if not env:
            self.fail(
                "Sélectionne une distribution WSL à actualiser."
            )
            return

        if env not in self.existing:
            self.fail(
                "La distribution WSL sélectionnée "
                "n'est plus installée."
            )
            return

        answer = QMessageBox.question(
            self,
            "Actualisation des dépôts WSL2",
            "Distribution WSL : " + env + "\n\n"
            "Le gestionnaire sera détecté automatiquement.\n"
            "L'actualisation sera exécutée en root.\n\n"
            "Cette opération modifie les métadonnées "
            "des dépôts, sans demander de mise à niveau "
            "complète des paquets.\n\n"
            "Continuer ?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.wsl_log.setPlainText(
            "Détection du gestionnaire et actualisation "
            "des dépôts de " + env + "..."
        )

        self.task(
            "update",
            (env,),
            lambda data, error:
                self.update_selected_done(
                    env,
                    data,
                    error
                )
        )

    def update_selected_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Erreur d'actualisation :\n" + error
            )
            return

        family, command, result = data

        output, stderr, code = result

        report = (
            "Distribution WSL : " + env + "\n"
            "Famille détectée : " + family + "\n"
            "Commande : " + command + "\n"
            "Code retour : " + str(code) + "\n\n"
            "SORTIE STANDARD :\n"
            + output
            + "\n\nERREURS :\n"
            + stderr
        )

        self.wsl_log.setPlainText(report)

        if code != 0:
            self.fail(
                "Échec de l'actualisation des dépôts "
                "de " + env + ".\n"
                "Consulte le journal WSL2."
            )
        else:
            self.message(
                "Dépôts actualisés",
                "Distribution : " + env + "\n"
                "Gestionnaire : " + family + "\n"
                "Commande : " + command + "\n\n"
                "Actualisation terminée."
            )

    # ========================================================
    # VALIDATION ENVIRONNEMENT
    # ========================================================

    def check_environment(self):
        env = self.env()

        if not env or env not in self.existing:
            self.fail(
                "Associe une distribution WSL installée à "
                + self.family()
                + " dans WSL2, puis actualise la liste."
            )

            self.tabs.setCurrentIndex(4)

            return ""

        return env

    # ========================================================
    # MISE À JOUR DES DÉPÔTS
    # ========================================================

    def update_repo(self):
        env = self.check_environment()

        if not env:
            return

        family = self.family()
        command = update_command(family)

        extra = ""

        if family == "Arch Linux":
            extra = (
                "\nATTENTION : pacman -Sy actualise "
                "la base de données sans mettre à niveau "
                "les paquets. Ne lance pas ensuite des "
                "installations partielles dans cet "
                "environnement Arch."
            )

        answer = QMessageBox.question(
            self,
            "Actualisation des dépôts",
            f"Environnement : {env}\n"
            f"Commande : {command}\n\n"
            "Cette opération modifie les métadonnées "
            "des dépôts dans WSL et peut nécessiter "
            "les droits root."
            + extra
            + "\n\nContinuer ?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.task(
            "update",
            (env, family),
            lambda data, error:
                self.update_done(
                    env,
                    family,
                    data,
                    error
                )
        )

    def update_done(self, env, family, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Erreur : " + error
            )
            return

        output, stderr, code = data

        text = (
            f"Mise à jour {family} sur {env} "
            f"— code {code}\n"
            + output
            + "\n"
            + stderr
        )

        self.wsl_log.setPlainText(text)

        self.search_log.setPlainText(
            text[-4000:]
        )

        if code:
            self.fail(
                "La mise à jour des dépôts a échoué. "
                "Vérifie le journal WSL2 "
                "et les droits root."
            )
        else:
            self.message(
                "Dépôts",
                "Métadonnées actualisées. "
                "Tu peux relancer la recherche."
            )

    # ========================================================
    # RECHERCHE D'APPLICATIONS
    # ========================================================

    def search(self):
        env = self.check_environment()

        if not env:
            return

        query = self.query.text().strip()

        if not query or len(query) > 70:
            self.fail(
                "Entre une recherche de 1 à 70 caractères."
            )
            return

        family = self.family()
        generation = self.generation

        self.search_log.setPlainText(
            "Recherche dans " + env + "..."
        )

        self.task(
            "search",
            (
                env,
                family,
                query
            ),
            lambda data, error:
                self.search_done(
                    family,
                    generation,
                    data,
                    error
                )
        )

    def search_done(
        self,
        family,
        generation,
        data,
        error
    ):
        if generation != self.generation:
            return

        if error:
            self.search_log.setPlainText(
                "Erreur : " + error
            )
            return

        output, stderr, code = data

        rows = parse_search(
            family,
            output
        )

        self.fill(
            self.search_table,
            rows
        )

        self.search_log.setPlainText(
            f"{len(rows)} résultats reconnus, "
            f"code {code}.\n"
            + (
                stderr
                or (
                    output[:2000]
                    if not rows
                    else (
                        "Double-clique sur un résultat "
                        "pour l’ajouter."
                    )
                )
            )
        )

        if code:
            self.fail(
                "Le gestionnaire a retourné une erreur. "
                "Vérifie son installation et les dépôts."
            )

    # ========================================================
    # LISTE DES PAQUETS
    # ========================================================

    def seeds(self):
        family = self.family()

        packages = set(
            BASE[family]
        )

        packages.update(
            DESKTOP[family].get(
                self.desktop.currentText(),
                []
            )
        )

        packages.update(
            AUDIO[family].get(
                self.audio.currentText(),
                []
            )
        )

        packages.update(self.apps)

        for name, checkbox in self.flags.items():
            if checkbox.isChecked():
                packages.update(
                    EXTRAS[family].get(name, [])
                )

        if family == "Arch Linux":
            packages.discard("linux")

            kernels = {
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }

            packages.add(
                kernels[self.kernel.currentText()]
            )

        if family == "Gentoo":
            packages.discard(
                "sys-apps/openrc"
            )

            packages.add(
                "sys-apps/openrc"
                if self.init.currentText() == "OpenRC"
                else "sys-apps/systemd"
            )

        if self.boot.currentText() == "GRUB":
            grub = {
                "Debian": (
                    "grub-efi-amd64"
                    if self.bootmode.currentText() == "UEFI"
                    else "grub-pc"
                ),
                "Fedora": (
                    "grub2-efi-x64"
                    if self.bootmode.currentText() == "UEFI"
                    else "grub2-pc"
                ),
                "Arch Linux": "grub",
                "Gentoo": "sys-boot/grub",
                "Slackware": "grub"
            }

            packages.add(
                grub[family]
            )

        return sorted(packages)

    # ========================================================
    # SIMULATION DES DÉPENDANCES
    # ========================================================

    def solve(self):
        env = self.check_environment()

        if not env:
            return

        generation = self.generation
        family = self.family()
        packages = self.seeds()

        self.project_log.setPlainText(
            "Simulation native en cours..."
        )

        self.task(
            "solve",
            (
                env,
                family,
                packages
            ),
            lambda data, error:
                self.solve_done(
                    family,
                    packages,
                    generation,
                    data,
                    error
                )
        )

    def solve_done(
        self,
        family,
        packages,
        generation,
        data,
        error
    ):
        if generation != self.generation:
            return

        if error:
            self.project_log.setPlainText(
                "Erreur : " + error
            )
            return

        output, stderr, code = data

        self.native = (
            f"Code retour : {code}\n"
            + output
            + "\n"
            + stderr
        )

        self.resolved = parse_simulation(
            family,
            output,
            packages
        )

        self.analysis_gen = (
            generation
            if code == 0
            else -1
        )

        self.fill(
            self.project_table,
            [
                (
                    package,
                    info["version"],
                    info["status"]
                )
                for package, info
                in sorted(self.resolved.items())
            ]
        )

        self.project_info.setText(
            f"{len(self.resolved)} paquets identifiés · "
            "analyse "
            + (
                "à vérifier"
                if code == 0
                else "en échec"
            )
        )

        self.project_log.setPlainText(
            "ATTENTION : simulation indicative. "
            "Les dépendances peuvent être absentes "
            "si elles sont déjà installées dans WSL. "
            "Aucune ISO amorçable n’est créée.\n\n"
            + self.native
        )

        if code:
            self.fail(
                "La simulation a échoué. "
                "Consulte la sortie native "
                "dans Projet / ISO."
            )

    # ========================================================
    # EXPORT
    # ========================================================

    def export(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier vide pour exporter"
        )

        if not folder:
            return

        target = Path(folder)

        if any(target.iterdir()):
            self.fail(
                "Choisis un dossier vide."
            )
            return

        data = {
            "version": VERSION,
            "distribution": self.family(),
            "release": self.release.currentText(),
            "wsl": self.env(),
            "desktop": self.desktop.currentText(),
            "kernel": self.kernel.currentText(),
            "init": self.init.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "bootloader": self.boot.currentText(),
            "bootmode": self.bootmode.currentText(),
            "requested_applications": sorted(self.apps),
            "requested_packages": self.seeds(),
            "resolved_packages": self.resolved,
            "analysis_current": (
                self.analysis_gen == self.generation
            ),
            "warning": (
                "Export de préparation, "
                "PAS une ISO amorçable. "
                "Résolution non exhaustive."
            )
        }

        (target / "project_v1_10.json").write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (target / "packages_v1_10.txt").write_text(
            "\n".join(self.seeds()) + "\n",
            encoding="utf-8"
        )

        (target / "native_report_v1_10.txt").write_text(
            (
                self.native
                if self.analysis_gen == self.generation
                else "Analyse absente ou obsolète"
            ),
            encoding="utf-8"
        )

        self.message(
            "Export",
            "Projet exporté. Aucune ISO créée."
        )


# ============================================================
# DÉMARRAGE
# ============================================================

if __name__ == "__main__":
    application = QApplication(sys.argv)
    application.setStyle("Fusion")

    window = App()
    window.show()

    sys.exit(application.exec())


