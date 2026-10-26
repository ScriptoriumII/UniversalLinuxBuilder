import sys
import json
import re
import shlex
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QFileDialog, QMessageBox,
    QTextEdit, QSplitter, QAbstractItemView
)

VERSION = "1.8"

DISTROS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

INIT = {
    "Debian": ["systemd"],
    "Fedora": ["systemd"],
    "Arch Linux": ["systemd"],
    "Gentoo": ["OpenRC", "systemd"],
    "Slackware": ["SysVinit"]
}

KERNEL = {
    "Debian": {"Stable": ["linux-image-amd64"]},
    "Fedora": {"Stable": ["kernel"]},
    "Arch Linux": {
        "Stable": ["linux"],
        "LTS": ["linux-lts"],
        "Hardened": ["linux-hardened"]
    },
    "Gentoo": {"Stable": ["sys-kernel/gentoo-kernel"]},
    "Slackware": {"Stable": ["kernel-generic"]}
}

DESKTOP = {
    "Debian": {
        "GNOME": ["gnome-core", "gdm3", "network-manager"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm", "network-manager"],
        "Xfce": ["xfce4", "lightdm", "network-manager"],
        "Budgie": ["budgie-desktop", "lightdm", "network-manager"]
    },
    "Fedora": {
        "GNOME": ["gnome-shell", "gnome-session", "gdm", "NetworkManager"],
        "KDE Plasma": ["plasma-desktop", "plasma-workspace", "sddm", "NetworkManager"],
        "Xfce": ["xfce4-session", "xfce4-panel", "xfwm4", "lightdm", "NetworkManager"],
        "Budgie": ["budgie-desktop", "gdm", "NetworkManager"]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm", "networkmanager"],
        "KDE Plasma": ["plasma", "sddm", "networkmanager"],
        "Xfce": ["xfce4", "lightdm", "networkmanager"],
        "Budgie": ["budgie-desktop", "gdm", "networkmanager"]
    },
    "Gentoo": {
        "GNOME": ["gnome-base/gnome", "gnome-base/gdm"],
        "KDE Plasma": ["kde-plasma/plasma-meta", "x11-misc/sddm"],
        "Xfce": ["xfce-base/xfce4-meta", "x11-misc/lightdm"],
        "Budgie": ["gnome-extra/budgie-desktop", "gnome-base/gdm"]
    },
    "Slackware": {
        "KDE Plasma": ["plasma-desktop", "plasma-workspace", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel", "xfwm4"]
    }
}

AUDIO = {
    "Debian": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Fedora": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulseaudio"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Arch Linux": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Gentoo": {
        "PipeWire": ["media-video/pipewire", "media-video/wireplumber"],
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
        "X11": ["xserver-xorg"],
        "Wayland": []
    },
    "Fedora": {
        "Base": ["systemd", "pciutils"],
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": [],
        "X11": ["xorg-x11-server-Xorg"],
        "Wayland": []
    },
    "Arch Linux": {
        "Base": ["base", "pciutils"],
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Calamares": ["calamares"],
        "X11": ["xorg-server"],
        "Wayland": []
    },
    "Gentoo": {
        "Base": ["sys-apps/pciutils"],
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmware": ["sys-kernel/linux-firmware"],
        "Calamares": [],
        "X11": ["x11-base/xorg-server"],
        "Wayland": []
    },
    "Slackware": {
        "Base": ["pciutils"],
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["kernel-firmware"],
        "Calamares": [],
        "X11": ["xorg-server"],
        "Wayland": []
    }
}

GRUB = {
    "Debian": {
        "UEFI": ["grub-efi-amd64", "efibootmgr"],
        "BIOS": ["grub-pc"]
    },
    "Fedora": {
        "UEFI": ["grub2-efi-x64", "grub2-tools", "efibootmgr"],
        "BIOS": ["grub2-pc", "grub2-tools"]
    },
    "Arch Linux": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"]
    },
    "Gentoo": {
        "UEFI": ["sys-boot/grub", "sys-boot/efibootmgr"],
        "BIOS": ["sys-boot/grub"]
    },
    "Slackware": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"]
    }
}

PACKAGE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

COLORS = {
    "Clair": {
        "bg": "#f3f6fa",
        "panel": "#ffffff",
        "text": "#152238",
        "line": "#d9e2ee",
        "muted": "#617086",
        "hover": "#edf3fb",
        "selected": "#d9e9ff"
    },
    "Sombre": {
        "bg": "#101823",
        "panel": "#192637",
        "text": "#ecf2fc",
        "line": "#34465b",
        "muted": "#a0b0c3",
        "hover": "#293b52",
        "selected": "#245c96"
    }
}

CSS = """
QMainWindow, QWidget#root {
    background: %(bg)s;
    color: %(text)s;
}
QWidget {
    color: %(text)s;
    font: 13px "Segoe UI";
}
QLabel#title {
    font-size: 23px;
    font-weight: 700;
}
QLabel#muted {
    color: %(muted)s;
}
QTabWidget::pane {
    background: %(panel)s;
    border: 1px solid %(line)s;
    border-radius: 9px;
}
QTabBar::tab {
    background: transparent;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 13px 20px;
    color: %(muted)s;
}
QTabBar::tab:selected {
    color: #3982f7;
    border-bottom: 2px solid #3982f7;
}
QTabBar::tab:hover {
    background: %(hover)s;
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: %(panel)s;
    color: %(text)s;
    border: 1px solid %(line)s;
    border-radius: 7px;
    padding: 6px;
    selection-background-color: %(selected)s;
}
QPushButton {
    background: %(hover)s;
    border: 1px solid %(line)s;
    border-radius: 7px;
    padding: 9px 14px;
    font-weight: 600;
}
QPushButton#primary {
    background: #2563eb;
    color: white;
    border: 1px solid #2563eb;
}
QPushButton:disabled {
    color: %(muted)s;
}
QHeaderView::section {
    background: %(hover)s;
    color: %(text)s;
    border: 0;
    border-bottom: 1px solid %(line)s;
    padding: 8px;
}
"""


def run_wsl(distro, script, timeout=100):
    if not distro or "\x00" in distro or "\n" in distro:
        raise RuntimeError("Environnement WSL non sélectionné")

    command = [
        "wsl.exe",
        "--distribution",
        distro,
        "--exec",
        "/bin/sh",
        "-lc",
        script
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if result.returncode:
        raise RuntimeError(
            (result.stderr or result.stdout or "Commande WSL en échec")[-1700:]
        )

    return result.stdout


def installed_wsl():
    result = subprocess.run(
        ["wsl.exe", "--list", "--quiet"],
        capture_output=True,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if result.returncode:
        raise RuntimeError(
            "WSL indisponible. Installer WSL2 puis réessayer."
        )

    raw = result.stdout

    if b"\x00" in raw:
        data = raw.decode("utf-16-le", errors="replace")
    else:
        data = raw.decode("utf-8", errors="replace")

    return [
        line.strip().replace("\ufeff", "")
        for line in data.splitlines()
        if line.strip().replace("\x00", "")
    ]


def search_command(family, query):
    q = shlex.quote(query)

    if family == "Debian":
        return "apt-cache search -- " + q

    if family == "Fedora":
        return "dnf5 search " + q

    if family == "Arch Linux":
        return "pacman -Ss " + q

    if family == "Gentoo":
        return "emerge --search " + q

    return (
        "if command -v slackpkg >/dev/null 2>&1; then "
        "slackpkg search " + q +
        '; else echo "slackpkg absent"; fi'
    )


def parse_search(family, output):
    rows = []
    seen = set()

    for line in output.splitlines():
        line = line.strip()
        name = ""
        description = ""
        version = "?"

        if family == "Debian" and " - " in line:
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
                r"^([\w+.-]+)\.(?:x86_64|noarch|aarch64|i686)\s*:\s*(.*)",
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
                r"\b([\w+.-]+)-([0-9][\w.+-]*)-(?:x86_64|noarch|i[3-6]86)",
                line
            )
            if match:
                name, version = match.groups()

        if name and PACKAGE_PATTERN.fullmatch(name) and name not in seen:
            rows.append((name, version, description[:180]))
            seen.add(name)

    return rows[:200]


def solve_command(family, packages):
    arguments = " ".join(shlex.quote(p) for p in packages)

    if family == "Debian":
        return (
            "LC_ALL=C apt-get -s "
            "-o Debug::NoLocking=1 install " + arguments
        )

    if family == "Fedora":
        return "LC_ALL=C dnf5 --assumeno install " + arguments

    if family == "Arch Linux":
        return (
            'LC_ALL=C pacman -Sp '
            '--print-format "%n|%v|%s" ' + arguments
        )

    if family == "Gentoo":
        return "LC_ALL=C emerge --pretend --verbose --tree " + arguments

    return (
        'echo "Slackware pkgtools ne fournit pas '
        'de solveur de dépendances natif."'
    )


def parse_solution(family, output, roots):
    found = {
        package: {
            "version": "?",
            "bytes": None,
            "kind": "Départ"
        }
        for package in roots
    }

    complete = False

    if family == "Debian":
        for line in output.splitlines():
            match = re.match(
                r"^Inst\s+(\S+)(?:\s+\[.*?\])?\s+\(([^ )]+)",
                line
            )
            if match:
                found[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "kind": "Transaction"
                }

    elif family == "Arch Linux":
        for line in output.splitlines():
            match = re.match(
                r"^([^|]+)\|([^|]+)\|(\d+)$",
                line.strip()
            )
            if match:
                found[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": int(match.group(3)),
                    "kind": "Transaction"
                }

    elif family == "Fedora":
        for line in output.splitlines():
            match = re.match(
                r"^\s*([\w+.-]+)\s+"
                r"(?:x86_64|noarch|aarch64|i686)\s+"
                r"([\w:~.+-]+)\s+",
                line
            )
            if match:
                found[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "kind": "Transaction indicative"
                }

    elif family == "Gentoo":
        for line in output.splitlines():
            match = re.search(
                r"\[ebuild[^]]*\]\s+"
                r"([\w+.-]+/[\w+.-]+)-([\w.+-]+)",
                line
            )
            if match:
                found[match.group(1)] = {
                    "version": match.group(2),
                    "bytes": None,
                    "kind": "Transaction indicative"
                }

    return found, complete


class Job(QThread):
    completed = Signal(object, str)

    def __init__(self, kind, *args):
        super().__init__()
        self.kind = kind
        self.args = args

    def run(self):
        try:
            if self.kind == "wsl":
                value = installed_wsl()

            elif self.kind == "probe":
                env, family = self.args

                commands = {
                    "Debian": "command -v apt-cache",
                    "Fedora": "command -v dnf5",
                    "Arch Linux": "command -v pacman",
                    "Gentoo": "command -v emerge",
                    "Slackware": "command -v slackpkg"
                }

                script = (
                    commands[family]
                    + " && cat /etc/os-release | head -8"
                )

                value = run_wsl(env, script, 25)

            elif self.kind == "search":
                env, family, query = self.args

                value = parse_search(
                    family,
                    run_wsl(
                        env,
                        search_command(family, query),
                        70
                    )
                )

            elif self.kind == "solve":
                env, family, packages = self.args

                output = run_wsl(
                    env,
                    solve_command(family, packages),
                    150
                )

                parsed, complete = parse_solution(
                    family,
                    output,
                    packages
                )

                value = (parsed, complete, output)

            else:
                raise RuntimeError("Opération inconnue")

            self.completed.emit(value, "")

        except Exception as error:
            self.completed.emit(None, str(error))


class Main(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Universal Linux Builder v1.8")
        self.resize(1320, 900)

        self.envs = {d: "" for d in DISTROS}
        self.apps = set()
        self.resolved = {}
        self.raw_report = ""
        self.resolution_complete = False
        self.resolution_signature = None
        self.worker = None
        self.revision = 0

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 20)

        header = QHBoxLayout()

        title = QLabel("Universal Linux Builder")
        title.setObjectName("title")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems(["Automatique", "Clair", "Sombre"])

        header.addWidget(self.theme)
        outer.addLayout(header)

        subtitle = QLabel(
            "v1.8 • Moteurs de paquets WSL2 • GRUB / Calamares"
        )
        subtitle.setObjectName("muted")
        outer.addWidget(subtitle)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self.build_distribution()
        self.build_system()
        self.build_apps()
        self.build_project()
        self.build_environments()

        self.theme.currentTextChanged.connect(self.apply_theme)

        QApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.apply_theme()
        )

        self.apply_theme()
        self.changed_distribution()

    def apply_theme(self):
        theme = self.theme.currentText()

        if theme == "Automatique":
            dark = (
                QApplication.styleHints().colorScheme()
                == Qt.ColorScheme.Dark
            )
            theme = "Sombre" if dark else "Clair"

        self.setStyleSheet(CSS % COLORS[theme])

    def page(self, label):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(11)

        self.tabs.addTab(widget, label)
        return layout

    def combo(self, values):
        combo = QComboBox()
        combo.addItems(values)
        return combo

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
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

    def build_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.distro = self.combo(list(DISTROS))
        self.release = self.combo([])

        form.addRow("Distribution", self.distro)
        form.addRow("Version", self.release)

        layout.addLayout(form)
        layout.addStretch()

        self.distro.currentTextChanged.connect(
            self.changed_distribution
        )
        self.release.currentTextChanged.connect(self.invalidate)

    def build_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo([
            "Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"
        ])
        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])
        self.audio = self.combo([
            "PipeWire", "PulseAudio", "ALSA", "Aucun"
        ])
        self.kernel = self.combo([
            "Stable", "LTS", "Hardened"
        ])
        self.init_system = self.combo([])
        self.bootloader = self.combo(["GRUB", "Aucun"])
        self.boot_mode = self.combo(["UEFI", "BIOS"])

        fields = [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau", self.kernel),
            ("Système d'initialisation", self.init_system),
            ("Bootloader", self.bootloader),
            ("Mode de démarrage", self.boot_mode)
        ]

        for label, widget in fields:
            form.addRow(label, widget)

        layout.addLayout(form)

        self.flags = {}

        for key, label, checked in [
            ("Wi-Fi", "Wi-Fi", True),
            ("Bluetooth", "Bluetooth", True),
            ("Impression", "Imprimantes / CUPS", False),
            ("Firmware", "Firmwares", True),
            ("Calamares", "Préparer Calamares", True)
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)

            self.flags[key] = checkbox
            layout.addWidget(checkbox)

            checkbox.toggled.connect(self.invalidate)

        self.system_note = QLabel()
        self.system_note.setWordWrap(True)
        layout.addWidget(self.system_note)

        self.resolve_button = QPushButton(
            "Analyser les dépendances du système"
        )
        self.resolve_button.setObjectName("primary")
        self.resolve_button.clicked.connect(self.resolve)

        layout.addWidget(self.resolve_button)
        layout.addStretch()

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        for widget in [
            self.display,
            self.audio,
            self.kernel,
            self.init_system,
            self.bootloader,
            self.boot_mode
        ]:
            widget.currentTextChanged.connect(self.invalidate)

    def changed_distribution(self, *_):
        distro = self.distro.currentText()

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(DISTROS[distro])
        self.release.blockSignals(False)

        self.init_system.blockSignals(True)
        self.init_system.clear()
        self.init_system.addItems(INIT[distro])
        self.init_system.blockSignals(False)

        old_desktop = self.desktop.currentText()

        self.desktop.blockSignals(True)
        self.desktop.clear()
        self.desktop.addItems(
            ["Aucun"] + list(DESKTOP[distro])
        )

        if old_desktop in DESKTOP[distro]:
            self.desktop.setCurrentText(old_desktop)

        self.desktop.blockSignals(False)

        self.apps.clear()

        if hasattr(self, "selected"):
            self.selected.setRowCount(0)

        self.desktop_changed()
        self.invalidate()

    def desktop_changed(self, *_):
        desktop = self.desktop.currentText()

        if desktop == "Aucun":
            display = "Aucun"
        elif desktop == "Xfce" or self.distro.currentText() == "Slackware":
            display = "X11"
        else:
            display = "Wayland"

        self.display.blockSignals(True)
        self.display.setCurrentText(display)
        self.display.blockSignals(False)

        self.invalidate()

    def invalidate(self, *_):
        self.revision += 1
        self.resolved = {}
        self.raw_report = ""
        self.resolution_complete = False
        self.resolution_signature = None

        if hasattr(self, "system_note"):
            self.system_note.setText(
                "Configuration modifiée : analyse WSL2 à relancer."
            )

    def build_apps(self):
        layout = self.page("Applications")

        bar = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher : firefox, vlc, gimp..."
        )
        self.query.returnPressed.connect(self.search)

        self.search_button = QPushButton("Rechercher via WSL2")
        self.search_button.setObjectName("primary")
        self.search_button.clicked.connect(self.search)

        bar.addWidget(self.query)
        bar.addWidget(self.search_button)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.results = self.table([
            "Application", "Version", "Description"
        ])
        self.results.setColumnWidth(0, 320)
        self.results.setColumnWidth(1, 170)
        self.results.cellDoubleClicked.connect(self.add_result)

        splitter.addWidget(self.results)

        self.selected = self.table(["Application sélectionnée"])
        self.selected.cellDoubleClicked.connect(self.remove_app)

        splitter.addWidget(self.selected)
        splitter.setSizes([350, 200])

        layout.addWidget(splitter, 1)

        row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText("Nom exact du paquet")

        button = QPushButton("Ajouter manuellement")
        button.clicked.connect(self.add_manual)

        row.addWidget(self.manual)
        row.addWidget(button)

        layout.addLayout(row)

        self.app_note = QLabel(
            "Double-clic sur un résultat pour ajouter ; "
            "double-clic sur une sélection pour retirer."
        )
        self.app_note.setWordWrap(True)
        layout.addWidget(self.app_note)

    def add_manual(self):
        name = self.manual.text().strip()

        if not PACKAGE_PATTERN.fullmatch(name):
            QMessageBox.warning(
                self, "Paquet", "Nom de paquet invalide."
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

    def refresh_apps(self):
        self.fill(
            self.selected,
            [(name,) for name in sorted(self.apps)]
        )

    def seeds(self):
        distro = self.distro.currentText()

        if distro == "Gentoo":
            init_packages = (
                ["sys-apps/openrc"]
                if self.init_system.currentText() == "OpenRC"
                else ["sys-apps/systemd"]
            )
        else:
            init_packages = []

        categories = {
            "Base": EXTRA[distro]["Base"][:],
            "Initialisation": init_packages,
            "Noyau": KERNEL[distro].get(
                self.kernel.currentText(), []
            )[:],
            "Bureau": DESKTOP[distro].get(
                self.desktop.currentText(), []
            )[:],
            "Audio": AUDIO[distro].get(
                self.audio.currentText(), []
            )[:],
            "Affichage": (
                EXTRA[distro].get(
                    self.display.currentText(), []
                )[:]
                if self.desktop.currentText() != "Aucun"
                else []
            ),
            "GRUB": (
                GRUB[distro].get(
                    self.boot_mode.currentText(), []
                )[:]
                if self.bootloader.currentText() == "GRUB"
                else []
            ),
            "Applications": sorted(self.apps)
        }

        for key in self.flags:
            categories[key] = (
                EXTRA[distro].get(key, [])[:]
                if self.flags[key].isChecked()
                else []
            )

        return categories

    def signature(self):
        return json.dumps(
            [
                self.distro.currentText(),
                self.release.currentText(),
                self.init_system.currentText(),
                self.current_environment(),
                self.seeds()
            ],
            sort_keys=True
        )

    def current_environment(self):
        return self.envs.get(self.distro.currentText(), "")

    def start_job(self, kind, args, callback):
        if self.worker is not None:
            QMessageBox.information(
                self,
                "Analyse en cours",
                "Attends la fin de la commande WSL."
            )
            return

        job = Job(kind, *args)
        self.worker = job

        self.search_button.setEnabled(False)
        self.resolve_button.setEnabled(False)

        job.completed.connect(callback)
        job.finished.connect(
            lambda: self.job_finished(job)
        )

        job.start()

    def job_finished(self, job):
        if self.worker is job:
            self.worker = None

        self.search_button.setEnabled(True)
        self.resolve_button.setEnabled(True)

        job.deleteLater()

    def search(self):
        query = self.query.text().strip()
        env = self.current_environment()

        if not query or len(query) > 70:
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir une recherche de 1 à 70 caractères."
            )
            return

        if not env:
            QMessageBox.warning(
                self,
                "WSL2",
                "Associer un environnement dans "
                "l'onglet Environnements Linux."
            )
            return

        revision = self.revision

        self.app_note.setText("Recherche WSL2 en cours...")

        self.start_job(
            "search",
            (env, self.distro.currentText(), query),
            lambda data, error: self.search_finished(
                data, error, revision
            )
        )

    def search_finished(self, data, error, revision):
        if revision != self.revision:
            return

        if error:
            self.app_note.setText(
                "Erreur de recherche : " + error
            )
            return

        self.fill(self.results, data)

        self.app_note.setText(
            f"{len(data)} résultats ; double-clic pour ajouter. "
            "Certaines versions peuvent être absentes."
        )

    def resolve(self):
        env = self.current_environment()
        distro = self.distro.currentText()

        if not env:
            QMessageBox.warning(
                self,
                "WSL2",
                "Associer un environnement Linux avant analyse."
            )
            return

        if self.kernel.currentText() not in KERNEL[distro]:
            QMessageBox.warning(
                self,
                "Noyau",
                "Ce noyau n'est pas défini pour cette distribution."
            )
            return

        if (
            self.flags["Calamares"].isChecked()
            and not EXTRA[distro]["Calamares"]
        ):
            QMessageBox.information(
                self,
                "Calamares",
                "Calamares n'est pas défini dans ce profil. "
                "Sa disponibilité devra être vérifiée séparément."
            )

        packages = sorted({
            package
            for group in self.seeds().values()
            for package in group
        })

        if not packages:
            QMessageBox.warning(
                self, "Analyse", "Aucun paquet sélectionné."
            )
            return

        revision = self.revision
        signature = self.signature()

        self.system_note.setText(
            "Simulation de transaction dans " + env + "..."
        )

        self.start_job(
            "solve",
            (env, distro, packages),
            lambda data, error: self.resolve_finished(
                data, error, revision, signature
            )
        )

    def resolve_finished(self, data, error, revision, signature):
        if revision != self.revision:
            return

        if error:
            self.system_note.setText(
                "Échec de la simulation : " + error
            )
            return

        self.resolved, self.resolution_complete, self.raw_report = data
        self.resolution_signature = signature

        self.system_note.setText(
            f"{len(self.resolved)} paquets identifiés.\n"
            "Analyse indicative : consulter le rapport natif "
            "pour vérifier les dépendances et les conflits."
        )

        self.verify()

    def build_project(self):
        layout = self.page("Projet / ISO")

        self.summary = QLabel(
            "Analyser le système pour obtenir "
            "une liste native des paquets."
        )
        self.summary.setWordWrap(True)

        layout.addWidget(self.summary)

        self.preview = self.table([
            "Paquet", "Version", "Statut", "Taille disponible"
        ])
        self.preview.setColumnWidth(0, 340)
        self.preview.setColumnWidth(1, 170)
        self.preview.setColumnWidth(2, 200)

        layout.addWidget(self.preview, 2)

        self.report = QTextEdit()
        self.report.setReadOnly(True)

        layout.addWidget(self.report, 1)

        row = QHBoxLayout()

        verify_button = QPushButton("Vérifier")
        verify_button.clicked.connect(self.verify)

        export_button = QPushButton("Exporter le projet")
        export_button.setObjectName("primary")
        export_button.clicked.connect(self.export)

        row.addWidget(verify_button)
        row.addWidget(export_button)

        layout.addLayout(row)

    def verify(self):
        distro = self.distro.currentText()

        roots = sorted({
            package
            for group in self.seeds().values()
            for package in group
        })

        fresh = (
            self.resolution_signature == self.signature()
        )

        if fresh:
            items = self.resolved
        else:
            items = {
                package: {
                    "version": "?",
                    "bytes": None,
                    "kind": "Départ non résolu"
                }
                for package in roots
            }

        rows = []

        for name, info in sorted(items.items()):
            size = info.get("bytes")

            rows.append((
                name,
                info.get("version", "?"),
                info.get("kind", "?"),
                (
                    f"{size} octets"
                    if size is not None
                    else "Inconnue"
                )
            ))

        self.fill(self.preview, rows)

        known = sum(
            info.get("bytes") or 0
            for info in items.values()
        )

        unknown = sum(
            info.get("bytes") is None
            for info in items.values()
        )

        warnings = []

        if not fresh:
            warnings.append(
                "Simulation WSL2 absente ou obsolète."
            )

        if not self.resolution_complete:
            warnings.append(
                "Résolution non certifiée exhaustive."
            )

        if (
            self.flags["Calamares"].isChecked()
            and not EXTRA[distro]["Calamares"]
        ):
            warnings.append(
                "Calamares : disponibilité non vérifiée "
                "dans les dépôts de cette distribution."
            )

        if distro == "Gentoo":
            warnings.append(
                "Gentoo : le profil Portage et les USE flags "
                "doivent correspondre à "
                + self.init_system.currentText()
                + "."
            )

        if distro == "Slackware":
            warnings.append(
                "Slackware : pkgtools ne résout pas "
                "automatiquement les dépendances."
            )

        warnings.append(
            "Les paquets déjà installés dans WSL "
            "peuvent modifier la simulation."
        )

        warnings.append(
            "GRUB du système installé et démarrage "
            "de l'ISO Live sont deux configurations distinctes."
        )

        self.summary.setText(
            f"{len(items)} paquets affichés • "
            f"{unknown} tailles inconnues • "
            f"{known / 1048576:.1f} Mio de tailles connues.\n"
            "Ce total ne représente PAS la taille finale de l'ISO."
        )

        self.report.setPlainText(
            "AVERTISSEMENTS\n"
            + "\n".join(warnings)
            + "\n\nSORTIE DU GESTIONNAIRE\n"
            + (
                self.raw_report
                if fresh
                else "Lancer une analyse WSL2."
            )
        )

        return {
            "version": VERSION,
            "distribution": distro,
            "release": self.release.currentText(),
            "wsl_environment": self.current_environment(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentText(),
            "init_system": self.init_system.currentText(),
            "bootloader": self.bootloader.currentText(),
            "boot_mode": self.boot_mode.currentText(),
            "categories": self.seeds(),
            "applications": sorted(self.apps),
            "packages": items,
            "analysis_fresh": fresh,
            "resolution_complete": (
                self.resolution_complete if fresh else False
            ),
            "warnings": warnings,
            "known_size_bytes": known,
            "unknown_sizes": unknown
        }

    def export(self):
        data = self.verify()

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier vide",
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

        (path / "project_v1_8.json").write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_8.txt").write_text(
            "\n".join(data["packages"]) + "\n",
            encoding="utf-8"
        )

        (path / "native_report_v1_8.txt").write_text(
            (
                self.raw_report
                if data["analysis_fresh"]
                else "Analyse non disponible"
            ),
            encoding="utf-8"
        )

        (path / "README_v1_8.txt").write_text(
            "Universal Linux Builder v1.8\n\n"
            "Projet préparatoire uniquement.\n"
            "Aucune ISO amorçable n'est générée.\n"
            "Vérifier les dépôts, dépendances, "
            "GRUB et Calamares avant construction.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Projet v1.8 exporté.\nAucune ISO créée."
        )

    def build_environments(self):
        layout = self.page("Environnements Linux")

        note = QLabel(
            "Associer chaque famille à une distribution WSL2 "
            "installée. Vérifier que sa version correspond "
            "au projet, par exemple Fedora 44."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()

        detect_button = QPushButton(
            "Détecter les environnements WSL2"
        )
        detect_button.setObjectName("primary")
        detect_button.clicked.connect(self.detect)

        test_button = QPushButton(
            "Tester le gestionnaire sélectionné"
        )
        test_button.clicked.connect(self.probe)

        row.addWidget(detect_button)
        row.addWidget(test_button)

        layout.addLayout(row)

        form = QFormLayout()
        self.env_combos = {}

        for distro in DISTROS:
            combo = self.combo(["— Non configuré —"])

            combo.currentTextChanged.connect(
                lambda value, family=distro:
                    self.assign_environment(family, value)
            )

            form.addRow(distro, combo)
            self.env_combos[distro] = combo

        layout.addLayout(form)

        self.env_note = QTextEdit()
        self.env_note.setReadOnly(True)
        self.env_note.setPlainText(
            "Cliquer sur Détecter.\n\n"
            "Les environnements WSL2 ne sont pas "
            "installés automatiquement."
        )

        layout.addWidget(self.env_note, 1)

    def assign_environment(self, family, value):
        if value == "— Non configuré —":
            self.envs[family] = ""
        else:
            self.envs[family] = value

        self.invalidate()

    def detect(self):
        self.env_note.setPlainText(
            "Détection des environnements WSL2..."
        )

        self.start_job(
            "wsl",
            (),
            self.detect_finished
        )

    def detect_finished(self, data, error):
        if error:
            self.env_note.setPlainText(
                "Erreur : " + error
            )
            return

        for distro, combo in self.env_combos.items():
            old = self.envs[distro]

            combo.blockSignals(True)
            combo.clear()
            combo.addItems(
                ["— Non configuré —"] + data
            )

            if old in data:
                combo.setCurrentText(old)

            combo.blockSignals(False)

            self.envs[distro] = (
                old if old in data else ""
            )

        self.env_note.setPlainText(
            "Distributions WSL2 détectées :\n"
            + ("\n".join(data) if data else "Aucune")
            + "\n\nAssocier les environnements "
            "et vérifier leur version."
        )

    def probe(self):
        family = self.distro.currentText()
        env = self.current_environment()

        if not env:
            QMessageBox.warning(
                self,
                "WSL2",
                "Associer un environnement à " + family
            )
            return

        self.env_note.setPlainText(
            "Vérification de " + env + "..."
        )

        self.start_job(
            "probe",
            (env, family),
            lambda data, error:
                self.env_note.setPlainText(
                    "Erreur : " + error
                    if error
                    else data
                )
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Main()
    window.show()

    sys.exit(app.exec())
