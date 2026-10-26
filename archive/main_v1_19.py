import sys
import os
import re
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QTextEdit, QMessageBox, QFileDialog,
    QGroupBox, QInputDialog, QSplitter, QHeaderView,
    QFrame
)

VERSION = "1.19"

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
    "Debian": "APT",
    "Fedora": "DNF5",
    "Arch Linux": "Pacman",
    "Gentoo": "Portage",
    "Slackware": "Slackpkg"
}

MANAGER_COMMANDS = {
    "Debian": "apt-get",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

INSTALLERS = {
    "Debian": "Calamares",
    "Fedora": "Anaconda",
    "Arch Linux": "Calamares",
    "Gentoo": "Installation Gentoo",
    "Slackware": "Slackware Setup"
}

COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#51A2DA",
    "Arch Linux": "#1793D1",
    "Gentoo": "#9482C9",
    "Slackware": "#7D95A9"
}

# Les symboles ci-dessous servent de solution de secours.
# Les logos SVG officiels peuvent etre places dans :
# Documents/UniversalLinuxBuilder/logos/
#
# Debian.svg
# Fedora.svg
# Arch Linux.svg
# Gentoo.svg
# Slackware.svg

SYMBOLS = {
    "Debian": "D",
    "Fedora": "f",
    "Arch Linux": "A",
    "Gentoo": "g",
    "Slackware": "S"
}

DESKTOPS = {
    "Debian": {
        "Aucun": [],
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"]
    },
    "Fedora": {
        "Aucun": [],
        "GNOME": ["gnome-shell", "gdm"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel"]
    },
    "Arch Linux": {
        "Aucun": [],
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"]
    },
    "Gentoo": {
        "Aucun": [],
        "GNOME": ["gnome-base/gnome"],
        "KDE Plasma": ["kde-plasma/plasma-meta"],
        "Xfce": ["xfce-base/xfce4-meta"]
    },
    "Slackware": {
        "Aucun": [],
        "KDE Plasma": ["plasma-desktop"],
        "Xfce": ["xfce4-session"]
    }
}

BASE_PACKAGES = {
    "Debian": [
        "linux-image-amd64",
        "systemd-sysv",
        "apt",
        "dpkg",
        "sudo",
        "network-manager",
        "ca-certificates"
    ],
    "Fedora": [
        "kernel",
        "systemd",
        "dnf5",
        "rpm",
        "fedora-repos",
        "sudo",
        "NetworkManager",
        "ca-certificates"
    ],
    "Arch Linux": [
        "base",
        "linux",
        "linux-firmware",
        "pacman",
        "archlinux-keyring",
        "sudo",
        "networkmanager"
    ],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
        "sys-apps/portage",
        "sys-apps/sudo",
        "net-misc/networkmanager"
    ],
    "Slackware": [
        "kernel-generic",
        "kernel-modules",
        "pkgtools",
        "slackpkg",
        "sudo",
        "networkmanager"
    ]
}

TOOLS = {
    "Debian": [
        ("apt-get", "apt"),
        ("debootstrap", "debootstrap"),
        ("lb", "live-build"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso")
    ],
    "Fedora": [
        ("dnf5", "dnf5"),
        ("rpm", "rpm"),
        ("lorax", "lorax"),
        ("livemedia-creator", "lorax"),
        ("mksquashfs", "squashfs-tools")
    ],
    "Arch Linux": [
        ("pacman", "pacman"),
        ("mkarchiso", "archiso"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "libisoburn")
    ],
    "Gentoo": [
        ("emerge", "sys-apps/portage"),
        ("mksquashfs", "sys-fs/squashfs-tools"),
        ("xorriso", "app-cdr/libisoburn")
    ],
    "Slackware": [
        ("installpkg", "pkgtools"),
        ("slackpkg", "slackpkg"),
        ("mkisofs", "cdrtools")
    ]
}

EXTRAS = {
    "Debian": {
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"]
    },
    "Fedora": {
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"]
    },
    "Arch Linux": {
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"]
    },
    "Gentoo": {
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"]
    },
    "Slackware": {
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"]
    }
}

SETTINGS = (
    Path(os.environ.get("APPDATA", str(Path.home())))
    / "UniversalLinuxBuilder"
    / "settings.json"
)

APP_DIR = Path.home() / "Documents" / "UniversalLinuxBuilder"
LOGO_DIR = APP_DIR / "logos"

SAFE_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

STYLE = """
QWidget {
    background: #0F1723;
    color: #E0E8F3;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow {
    background: #0F1723;
}

QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #192536;
    border: 1px solid #314258;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: #315C88;
}

QPushButton {
    background: #263A52;
    border: 1px solid #405771;
    border-radius: 5px;
    padding: 7px 11px;
}

QPushButton:hover {
    background: #345270;
}

QPushButton:disabled {
    color: #73849A;
    background: #192332;
}

QTabBar::tab {
    background: #172333;
    padding: 9px 16px;
    border-right: 1px solid #35465A;
}

QTabBar::tab:selected {
    background: #25374C;
    border-bottom: 2px solid #6AABF2;
}

QGroupBox {
    border: 1px solid #34465B;
    border-radius: 6px;
    margin-top: 12px;
    padding: 9px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QHeaderView::section {
    background: #29415B;
    padding: 8px;
    border: none;
}

QTableWidget {
    alternate-background-color: #203047;
    gridline-color: transparent;
}

QLabel#ContextBanner {
    background: #1B2A3C;
    border: 1px solid #38516D;
    border-radius: 7px;
    padding: 12px;
    font-size: 13px;
    font-weight: 600;
}

QFrame#HeaderFrame {
    background: #121E2D;
    border-bottom: 1px solid #30465E;
}
"""


# ============================================================
# CONFIGURATION
# ============================================================

def load_settings():
    try:
        data = json.loads(
            SETTINGS.read_text(encoding="utf-8")
        )
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    SETTINGS.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fd, temporary = tempfile.mkstemp(
        prefix="settings-",
        suffix=".tmp",
        dir=SETTINGS.parent
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as handle:
            json.dump(
                data,
                handle,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temporary, SETTINGS)

    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


# ============================================================
# WSL
# ============================================================

def decode_output(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode(
            "utf-16",
            "replace"
        ).replace("\x00", "").strip()

    if b"\x00" in raw[:120]:
        return raw.decode(
            "utf-16-le",
            "replace"
        ).replace("\x00", "").lstrip("\ufeff").strip()

    return raw.decode(
        "utf-8",
        "replace"
    ).lstrip("\ufeff").strip()


def execute(arguments, timeout=180):
    process = subprocess.run(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        creationflags=getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0
        )
    )

    return (
        decode_output(process.stdout),
        decode_output(process.stderr),
        process.returncode
    )


def linux(env, command, root=False, timeout=300):
    arguments = [
        "wsl.exe",
        "--distribution",
        env
    ]

    if root:
        arguments += [
            "--user",
            "root"
        ]

    arguments += [
        "--exec",
        "/bin/sh",
        "-lc",
        command
    ]

    return execute(arguments, timeout)


def wsl_names():
    output, error, code = execute(
        ["wsl.exe", "--list", "--quiet"],
        60
    )

    if code:
        raise RuntimeError(
            error or output or "Impossible de lire WSL2"
        )

    return list(dict.fromkeys(
        name.strip()
        for name in output.splitlines()
        if name.strip()
    ))


def detect_distribution(env):
    output, error, code = linux(
        env,
        "cat /etc/os-release",
        timeout=45
    )

    if code:
        return {
            "name": env,
            "family": "Inconnue",
            "version": "",
            "codename": "",
            "error": error or output
        }

    info = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            info[key] = value.strip().strip('"').strip("'")

    identifiers = (
        info.get("ID", "")
        + " "
        + info.get("ID_LIKE", "")
    ).lower().split()

    mapping = {
        "debian": "Debian",
        "fedora": "Fedora",
        "arch": "Arch Linux",
        "archlinux": "Arch Linux",
        "gentoo": "Gentoo",
        "slackware": "Slackware"
    }

    family = next(
        (
            mapping[identifier]
            for identifier in identifiers
            if identifier in mapping
        ),
        "Inconnue"
    )

    return {
        "name": env,
        "family": family,
        "version": info.get("VERSION_ID", ""),
        "codename": info.get("VERSION_CODENAME", ""),
        "error": ""
    }


def detect_all(names):
    return [
        detect_distribution(name)
        for name in names
    ]


def online_catalog():
    output, error, code = execute(
        ["wsl.exe", "--list", "--online"],
        90
    )

    if code:
        raise RuntimeError(error or output)

    rows = []

    for line in output.splitlines():
        match = re.match(
            r"^\s*([A-Za-z0-9][\w.-]*)\s{2,}(.+?)\s*$",
            line
        )

        if match:
            name, description = match.groups()

            if name.lower() not in ("name", "nom"):
                rows.append((name, description))

    return rows, output


def best_match(family, release, inventory):
    candidates = [
        item
        for item in inventory
        if item["family"] == family
    ]

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: (
            release not in (
                item["version"],
                item["codename"]
            ),
            item["name"].casefold()
        )
    )

    return candidates[0]["name"]


# ============================================================
# OUTILS
# ============================================================

def check_tools(env, family):
    commands = []

    for executable, package in TOOLS[family]:
        quoted = shlex.quote(executable)

        commands.append(
            "if command -v "
            + quoted
            + " >/dev/null 2>&1; "
            + "then echo "
            + shlex.quote(executable + ":OK")
            + "; else echo "
            + shlex.quote(executable + ":ABSENT")
            + "; fi"
        )

    output, error, code = linux(
        env,
        "; ".join(commands),
        timeout=120
    )

    if code:
        raise RuntimeError(error or output)

    states = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.split(":", 1)
            states[name] = state.strip() == "OK"

    return [
        (
            executable,
            package,
            "Présent" if states.get(executable) else "Absent"
        )
        for executable, package in TOOLS[family]
    ]


def test_manager(env, family):
    command = (
        "command -v "
        + shlex.quote(MANAGER_COMMANDS[family])
    )

    return command, linux(env, command)


def update_repositories(env, family):
    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update"
        ),
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman -Syu --noconfirm",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    command = commands[family]

    return command, linux(
        env,
        command,
        root=True,
        timeout=3600
    )


def install_tools(env, family):
    if family not in (
        "Debian",
        "Fedora",
        "Arch Linux"
    ):
        raise RuntimeError(
            "Installation automatique non prise en charge "
            "pour cette famille."
        )

    rows = check_tools(env, family)

    missing = sorted({
        package
        for executable, package, state in rows
        if state == "Absent"
    })

    if not missing:
        return "Aucun outil manquant", ("", "", 0)

    arguments = " ".join(
        shlex.quote(package)
        for package in missing
    )

    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update"
            " && DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends "
            + arguments
        ),
        "Fedora": (
            "dnf5 install -y " + arguments
        ),
        "Arch Linux": (
            "pacman -Syu --noconfirm --needed "
            + arguments
        )
    }

    command = commands[family]

    return command, linux(
        env,
        command,
        root=True,
        timeout=3600
    )


# ============================================================
# APPLICATIONS
# ============================================================

def search_packages(env, family, query):
    commands = {
        "Debian": "apt-cache search",
        "Fedora": "dnf5 search",
        "Arch Linux": "pacman -Ss",
        "Gentoo": "emerge --search",
        "Slackware": "slackpkg search"
    }

    command = (
        "LC_ALL=C "
        + commands[family]
        + " "
        + shlex.quote(query)
    )

    return linux(
        env,
        command,
        timeout=300
    )


def parse_packages(family, output):
    results = []
    seen = set()

    for line in output.splitlines():
        name = ""
        description = ""

        if family == "Debian":
            match = re.match(
                r"^([\w+.-]+) - (.+)$",
                line
            )

            if match:
                name, description = match.groups()

        elif family == "Fedora":
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|noarch|aarch64|i686|src)"
                r"\s*:\s*(.*)$",
                line.strip()
            )

            if match:
                name, description = match.groups()

        elif family == "Arch Linux":
            match = re.match(
                r"^[\w+.-]+/([^ ]+)\s+([^ ]+)",
                line.strip()
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
                r"([\w+.-]+)-([0-9][\w.+-]*)-"
                r"(?:x86_64|noarch|i[3-6]86)",
                line
            )

            if match:
                name, description = match.groups()

        if (
            name
            and SAFE_PACKAGE.fullmatch(name)
            and name not in seen
        ):
            seen.add(name)

            results.append((
                name,
                description[:180]
            ))

    return results[:500]


def simulate_packages(env, family, packages):
    if family == "Slackware":
        raise RuntimeError(
            "Slackware ne possède pas de résolution "
            "automatique complète des dépendances "
            "avec slackpkg."
        )

    arguments = " ".join(
        shlex.quote(package)
        for package in packages
    )

    commands = {
        "Debian": "apt-get -s install ",
        "Fedora": "dnf5 --assumeno install ",
        "Arch Linux": (
            'pacman -Sp --print-format "%n|%v|%s" '
        ),
        "Gentoo": (
            "emerge --pretend --verbose --tree "
        )
    }

    command = commands[family] + arguments

    return command, linux(
        env,
        "LC_ALL=C " + command,
        timeout=900
    )


# ============================================================
# THREAD
# ============================================================

class Task(QThread):
    finished_data = Signal(object, str)

    def __init__(self, function, *arguments):
        super().__init__()
        self.function = function
        self.arguments = arguments

    def run(self):
        try:
            result = self.function(*self.arguments)
            self.finished_data.emit(result, "")
        except Exception as error:
            self.finished_data.emit(None, str(error))


# ============================================================
# LOGOS
# ============================================================

def create_logo(family, size=42):
    logo_file = LOGO_DIR / (family + ".svg")

    if logo_file.exists():
        pixmap = QPixmap(str(logo_file))

        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )

    painter.setBrush(
        QColor(COLORS[family])
    )

    painter.setPen(Qt.PenStyle.NoPen)

    painter.drawRoundedRect(
        1, 1, size - 2, size - 2, 11, 11
    )

    painter.setPen(QColor("#FFFFFF"))

    font = QFont("Segoe UI", int(size * 0.45))
    font.setBold(True)

    painter.setFont(font)

    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        SYMBOLS[family]
    )

    painter.end()

    return pixmap


# ============================================================
# INTERFACE
# ============================================================

class UniversalLinuxBuilder(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.19"
        )

        self.resize(1320, 820)
        self.setMinimumSize(1050, 650)

        self.config = load_settings()

        self.associations = dict(
            self.config.get("wsl_associations", {})
        )

        self.manual_associations = set(
            self.config.get("manual_associations", [])
        )

        self.inventory = []
        self.catalog_rows = []
        self.active_task = None

        self.family = "Debian"
        self.applications = set()

        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")

        header = QHBoxLayout(header_frame)
        header.setContentsMargins(8, 6, 8, 6)

        title = QLabel(
            "Universal Linux Builder  |  v1.19"
        )

        title.setStyleSheet(
            "font-size:19px;font-weight:600;"
        )

        header.addWidget(title)
        header.addStretch()

        self.header_logo = QLabel()
        self.header_logo.setFixedSize(34, 34)

        header.addWidget(self.header_logo)

        self.current_distribution = QLabel()

        self.current_distribution.setStyleSheet(
            "font-size:13px;font-weight:600;"
        )

        header.addWidget(self.current_distribution)

        outer.addWidget(header_frame)

        # ----------------------------------------------------
        # BANDEAU LOGOS PERMANENT
        # ----------------------------------------------------

        self.logo_bar = QHBoxLayout()
        self.logo_buttons = {}

        for family in FAMILIES:
            button = QPushButton()
            button.setFixedHeight(46)

            button.clicked.connect(
                lambda checked=False, name=family:
                    self.change_family(name)
            )

            row = QHBoxLayout(button)
            row.setContentsMargins(8, 3, 8, 3)

            icon = QLabel()
            icon.setPixmap(create_logo(family, 30))
            icon.setFixedSize(30, 30)

            text = QLabel(family)
            text.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )

            icon.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )

            row.addWidget(icon)
            row.addWidget(text)
            row.addStretch()

            self.logo_bar.addWidget(button)
            self.logo_buttons[family] = button

        outer.addLayout(self.logo_bar)

        # ----------------------------------------------------
        # ONGLETS
        # ----------------------------------------------------

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self.status = QLabel("Prêt")
        outer.addWidget(self.status)

        self.create_distribution_tab()
        self.create_system_tab()
        self.create_applications_tab()
        self.create_verification_tab()
        self.create_iso_tab()
        self.create_wsl_tab()

        self.setStyleSheet(STYLE)

        self.change_family("Debian")
        self.refresh_wsl()

    # --------------------------------------------------------
    # COMPOSANTS
    # --------------------------------------------------------

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(10)

        self.tabs.addTab(widget, name)
        return layout

    def button(self, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        return button

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)

        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(30)

        table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        table.horizontalHeader().setStretchLastSection(True)

        return table

    def fill_table(self, table, rows):
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(str(value))
                )

        table.setSortingEnabled(True)

    def selected_row(self, table):
        row = table.currentRow()

        if row < 0:
            return ""

        item = table.item(row, 0)
        return item.text() if item else ""

    def warning(self, message):
        QMessageBox.warning(
            self,
            "Universal Linux Builder",
            str(message)
        )

    def confirm(self, message):
        return (
            QMessageBox.question(
                self,
                "Confirmation",
                message
            )
            == QMessageBox.StandardButton.Yes
        )

    def run_task(self, function, arguments, callback):
        if self.active_task is not None:
            self.warning(
                "Une opération est déjà en cours."
            )
            return

        task = Task(function, *arguments)
        self.active_task = task

        self.status.setText("Opération en cours...")

        task.finished_data.connect(
            lambda result, error, current=task:
                self.task_finished(
                    current,
                    callback,
                    result,
                    error
                )
        )

        task.finished.connect(task.deleteLater)
        task.start()

    def task_finished(
        self,
        task,
        callback,
        result,
        error
    ):
        if self.active_task is task:
            self.active_task = None

        self.status.setText("Prêt")
        callback(result, error)

    def next_button(self, layout, index):
        row = QHBoxLayout()
        row.addStretch()

        row.addWidget(
            self.button(
                "Continuer →",
                lambda: self.tabs.setCurrentIndex(index)
            )
        )

        layout.addLayout(row)

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def create_distribution_tab(self):
        layout = self.page("Distribution")

        layout.addWidget(
            QLabel(
                "Configuration de la distribution Linux"
            )
        )

        form = QFormLayout()

        self.release = QComboBox()

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        form.addRow("Version", self.release)

        self.installer_label = QLabel()
        self.manager_label = QLabel()

        form.addRow(
            "Installateur",
            self.installer_label
        )

        form.addRow(
            "Gestionnaire de paquets",
            self.manager_label
        )

        layout.addLayout(form)
        layout.addStretch()

        self.next_button(layout, 1)

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def create_system_tab(self):
        layout = self.page("Système")

        form = QFormLayout()

        self.desktop = QComboBox()
        self.init_system = QComboBox()

        self.kernel = QComboBox()
        self.kernel.addItems([
            "Stable",
            "LTS",
            "Hardened"
        ])

        self.audio = QComboBox()
        self.audio.addItems([
            "PipeWire",
            "PulseAudio",
            "ALSA",
            "Aucun"
        ])

        self.boot = QComboBox()
        self.boot.addItems([
            "UEFI",
            "BIOS"
        ])

        for label, control in [
            ("Bureau", self.desktop),
            ("Initialisation", self.init_system),
            ("Noyau", self.kernel),
            ("Audio", self.audio),
            ("Démarrage", self.boot)
        ]:
            form.addRow(label, control)

        layout.addLayout(form)

        self.flags = {}

        for name in [
            "Wi-Fi",
            "Bluetooth",
            "Impression"
        ]:
            checkbox = QCheckBox(name)
            checkbox.setChecked(name != "Impression")

            self.flags[name] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()
        self.next_button(layout, 2)

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def create_applications_tab(self):
        layout = self.page("Applications")

        self.apps_context = QLabel()
        self.apps_context.setObjectName(
            "ContextBanner"
        )

        layout.addWidget(self.apps_context)

        row = QHBoxLayout()

        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText(
            "Rechercher dans les dépôts de la distribution"
        )

        self.search_text.returnPressed.connect(
            self.search_applications
        )

        row.addWidget(self.search_text)

        row.addWidget(
            self.button(
                "Rechercher",
                self.search_applications
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_project_repositories
            )
        )

        layout.addLayout(row)

        self.search_results = self.table([
            "Paquet",
            "Description"
        ])

        self.search_results.setColumnWidth(0, 270)

        self.search_results.cellDoubleClicked.connect(
            self.add_search_result
        )

        layout.addWidget(
            self.search_results,
            3
        )

        layout.addWidget(
            QLabel(
                "Applications sélectionnées "
                "(double-clic pour supprimer)"
            )
        )

        self.selected_apps = self.table(["Paquet"])

        self.selected_apps.cellDoubleClicked.connect(
            self.remove_application
        )

        layout.addWidget(
            self.selected_apps,
            1
        )

        row = QHBoxLayout()

        self.manual_package = QLineEdit()
        self.manual_package.setPlaceholderText(
            "Nom du paquet"
        )

        row.addWidget(self.manual_package)

        row.addWidget(
            self.button(
                "Ajouter",
                self.add_manual_application
            )
        )

        layout.addLayout(row)

        self.app_log = QTextEdit()
        self.app_log.setReadOnly(True)
        self.app_log.setMaximumHeight(90)

        layout.addWidget(self.app_log)
        self.next_button(layout, 3)

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def create_verification_tab(self):
        layout = self.page("Vérification")

        self.verification_context = QLabel()
        self.verification_context.setObjectName(
            "ContextBanner"
        )

        self.verification_context.setWordWrap(True)
        layout.addWidget(self.verification_context)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Vérifier les outils",
                self.verify_project
            )
        )

        row.addWidget(
            self.button(
                "Installer les prérequis manquants",
                self.install_project_tools
            )
        )

        row.addWidget(
            self.button(
                "Simuler les dépendances",
                self.analyze_project
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.verification_summary = QLabel(
            "Aucune vérification effectuée."
        )

        layout.addWidget(self.verification_summary)

        self.verification_table = self.table([
            "Outil",
            "Paquet requis",
            "État"
        ])

        self.verification_table.setColumnWidth(0, 220)
        self.verification_table.setColumnWidth(1, 270)

        layout.addWidget(
            self.verification_table,
            2
        )

        self.verification_log = QTextEdit()
        self.verification_log.setReadOnly(True)

        layout.addWidget(
            self.verification_log,
            2
        )

        self.next_button(layout, 4)

    # --------------------------------------------------------
    # ISO
    # --------------------------------------------------------

    def create_iso_tab(self):
        layout = self.page("ISO")

        self.iso_context = QLabel()
        self.iso_context.setObjectName(
            "ContextBanner"
        )

        layout.addWidget(self.iso_context)

        information = QLabel(
            "Le système installé devra conserver son "
            "gestionnaire de paquets et les dépôts adaptés "
            "à la distribution sélectionnée."
        )

        information.setWordWrap(True)
        layout.addWidget(information)

        warning = QLabel(
            "La création d'une ISO bootable et sa validation "
            "avec Ventoy ne sont pas encore implémentées "
            "dans cette version."
        )

        warning.setWordWrap(True)
        layout.addWidget(warning)

        layout.addWidget(
            self.button(
                "Exporter le manifeste du projet",
                self.export_project
            )
        )

        self.iso_log = QTextEdit()
        self.iso_log.setReadOnly(True)

        layout.addWidget(self.iso_log)

    # --------------------------------------------------------
    # WSL2
    # --------------------------------------------------------

    def create_wsl_tab(self):
        layout = self.page("WSL2")

        self.wsl_sections = QTabWidget()
        layout.addWidget(self.wsl_sections, 1)

        def section(name):
            widget = QWidget()
            section_layout = QVBoxLayout(widget)

            section_layout.setContentsMargins(
                8, 8, 8, 8
            )

            section_layout.setSpacing(8)

            self.wsl_sections.addTab(
                widget,
                name
            )

            return section_layout

        # ----------------------------------------------------
        # ENVIRONNEMENTS
        # ----------------------------------------------------

        environments = section("Environnements")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Actualiser",
                self.refresh_wsl
            )
        )

        row.addWidget(
            self.button(
                "Catalogue WSL",
                self.refresh_catalog
            )
        )

        row.addStretch()
        environments.addLayout(row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        installed_group = QGroupBox(
            "Distributions installées"
        )

        installed_layout = QVBoxLayout(
            installed_group
        )

        self.installed_table = self.table([
            "Nom WSL",
            "Famille",
            "Version"
        ])

        self.installed_table.setColumnWidth(0, 170)
        self.installed_table.setColumnWidth(1, 130)

        installed_layout.addWidget(
            self.installed_table
        )

        installed_layout.addWidget(
            self.button(
                "Supprimer la distribution",
                self.remove_wsl
            )
        )

        splitter.addWidget(installed_group)

        catalog_group = QGroupBox(
            "Distributions disponibles"
        )

        catalog_layout = QVBoxLayout(
            catalog_group
        )

        self.catalog_table = self.table([
            "Distribution",
            "Description"
        ])

        self.catalog_table.setColumnWidth(0, 170)

        catalog_layout.addWidget(
            self.catalog_table
        )

        catalog_layout.addWidget(
            self.button(
                "Installer dans WSL2",
                self.install_wsl
            )
        )

        splitter.addWidget(catalog_group)
        splitter.setSizes([520, 520])

        environments.addWidget(splitter, 1)

        # ----------------------------------------------------
        # OUTILS ET DEPOTS
        # ----------------------------------------------------

        tools_layout = section(
            "Outils et dépôts"
        )

        row = QHBoxLayout()
        row.addWidget(QLabel("Environnement WSL :"))

        self.wsl_choice = QComboBox()
        row.addWidget(self.wsl_choice, 1)

        row.addWidget(
            self.button(
                "Tester le gestionnaire",
                self.test_selected_manager
            )
        )

        row.addWidget(
            self.button(
                "Vérifier",
                self.check_selected_tools
            )
        )

        row.addWidget(
            self.button(
                "Installer les outils",
                self.install_selected_tools
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_selected_repositories
            )
        )

        tools_layout.addLayout(row)

        self.wsl_tools_table = self.table([
            "Exécutable",
            "Paquet requis",
            "État"
        ])

        self.wsl_tools_table.setColumnWidth(0, 220)
        self.wsl_tools_table.setColumnWidth(1, 270)

        tools_layout.addWidget(
            self.wsl_tools_table,
            1
        )

        # ----------------------------------------------------
        # ASSOCIATIONS
        # ----------------------------------------------------

        associations_layout = section(
            "Associations"
        )

        associations_layout.addWidget(
            QLabel(
                "Les associations WSL2 sont sauvegardées "
                "et restaurées automatiquement."
            )
        )

        group = QGroupBox(
            "Environnements de construction"
        )

        form = QFormLayout(group)

        self.mapping_boxes = {}
        self.indicators = {}

        for family in FAMILIES:
            row = QHBoxLayout()

            combo = QComboBox()
            combo.addItem("— Non associé —")

            combo.currentTextChanged.connect(
                lambda name, current_family=family:
                    self.mapping_changed(
                        current_family,
                        name
                    )
            )

            row.addWidget(combo, 1)

            indicator = QLabel("Non associé")
            indicator.setMinimumWidth(140)

            row.addWidget(indicator)

            form.addRow(family, row)

            self.mapping_boxes[family] = combo
            self.indicators[family] = indicator

        associations_layout.addWidget(group)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Réassocier automatiquement",
                self.reset_associations
            )
        )

        row.addStretch()
        associations_layout.addLayout(row)
        associations_layout.addStretch()

        # ----------------------------------------------------
        # JOURNAL
        # ----------------------------------------------------

        row = QHBoxLayout()

        self.log_button = self.button(
            "Afficher le journal ▾",
            self.toggle_wsl_log
        )

        row.addWidget(self.log_button)
        row.addStretch()

        layout.addLayout(row)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setVisible(False)
        self.wsl_log.setMaximumHeight(150)

        layout.addWidget(self.wsl_log)

    # --------------------------------------------------------
    # CONTEXTE DISTRIBUTION
    # --------------------------------------------------------

    def update_context(self):
        release = self.release.currentText()
        desktop = self.desktop.currentText()
        init = self.init_system.currentText()

        self.current_distribution.setText(
            self.family + "  •  " + release
        )

        self.header_logo.setPixmap(
            create_logo(self.family, 32)
        )

        environment = self.associations.get(
            self.family,
            ""
        ) or "Non associé"

        context = (
            self.family
            + " "
            + release
            + "  |  "
            + desktop
            + "  |  "
            + init
            + "  |  "
            + MANAGERS[self.family]
        )

        self.apps_context.setText(
            "APPLICATIONS  •  " + context
            + "  |  WSL2 : " + environment
        )

        self.verification_context.setText(
            "DISTRIBUTION ANALYSÉE  •  "
            + context
            + "\nWSL2 : "
            + environment
            + "  |  Installateur : "
            + INSTALLERS[self.family]
        )

        self.iso_context.setText(
            "PROJET ISO  •  "
            + context
            + "  |  Installateur : "
            + INSTALLERS[self.family]
        )

        for name, button in self.logo_buttons.items():
            if name == self.family:
                button.setStyleSheet(
                    "background:#294765;"
                    "border:1px solid "
                    + COLORS[name]
                    + ";border-radius:6px;"
                )
            else:
                button.setStyleSheet("")

    def change_family(self, family):
        self.family = family

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(RELEASES[family])
        self.release.blockSignals(False)

        self.desktop.clear()
        self.desktop.addItems(
            DESKTOPS[family].keys()
        )

        self.init_system.clear()

        if family == "Gentoo":
            self.init_system.addItems([
                "OpenRC",
                "systemd"
            ])

        elif family == "Slackware":
            self.init_system.addItem(
                "SysVinit"
            )

        else:
            self.init_system.addItem(
                "systemd"
            )

        self.kernel.setEnabled(
            family == "Arch Linux"
        )

        self.kernel.setCurrentText("Stable")

        self.installer_label.setText(
            INSTALLERS[family]
        )

        self.manager_label.setText(
            MANAGERS[family]
        )

        self.update_context()

    def release_changed(self, *_):
        self.update_context()

        if self.inventory:
            self.apply_associations()

    # --------------------------------------------------------
    # JOURNAL
    # --------------------------------------------------------

    def toggle_wsl_log(self):
        visible = not self.wsl_log.isVisible()

        self.wsl_log.setVisible(visible)

        self.log_button.setText(
            "Masquer le journal ▴"
            if visible
            else "Afficher le journal ▾"
        )

    def show_wsl_log(self, message):
        self.wsl_log.setPlainText(str(message))

        if not self.wsl_log.isVisible():
            self.toggle_wsl_log()

    # --------------------------------------------------------
    # ASSOCIATIONS
    # --------------------------------------------------------

    def persist_associations(self):
        self.config["version"] = VERSION

        self.config["wsl_associations"] = dict(
            self.associations
        )

        self.config["manual_associations"] = sorted(
            self.manual_associations
        )

        try:
            save_settings(self.config)
        except OSError as error:
            self.status.setText(
                "Sauvegarde impossible : "
                + str(error)
            )

    def refresh_wsl(self):
        self.run_task(
            wsl_names,
            (),
            self.wsl_names_ready
        )

    def wsl_names_ready(self, names, error):
        if error:
            self.show_wsl_log(error)
            return

        self.run_task(
            detect_all,
            (names,),
            self.inventory_ready
        )

    def inventory_ready(self, items, error):
        if error:
            self.show_wsl_log(error)
            return

        self.inventory = items

        rows = [
            (
                item["name"],
                item["family"],
                item["version"]
            )
            for item in items
        ]

        self.fill_table(
            self.installed_table,
            rows
        )

        previous = self.wsl_choice.currentText()

        self.wsl_choice.clear()

        self.wsl_choice.addItems([
            item["name"]
            for item in items
        ])

        if previous in [
            item["name"]
            for item in items
        ]:
            self.wsl_choice.setCurrentText(previous)

        self.apply_associations()

        self.wsl_log.setPlainText(
            "Détection terminée : "
            + str(len(items))
            + " environnement(s).\n\n"
            + "\n".join(
                item["name"]
                + " → "
                + item["family"]
                + " "
                + item["version"]
                for item in items
            )
        )

    def apply_associations(self):
        names = {
            item["name"]
            for item in self.inventory
        }

        changed = False

        for family in FAMILIES:
            saved = self.associations.get(
                family,
                ""
            )

            valid = (
                saved in names
                and next(
                    (
                        item["family"]
                        for item in self.inventory
                        if item["name"] == saved
                    ),
                    None
                ) == family
            )

            if not valid:
                if (
                    family in self.manual_associations
                    and saved == ""
                ):
                    choice = ""

                else:
                    release = (
                        self.release.currentText()
                        if family == self.family
                        else RELEASES[family][0]
                    )

                    choice = best_match(
                        family,
                        release,
                        self.inventory
                    )

                    self.manual_associations.discard(
                        family
                    )

                if choice != saved:
                    self.associations[family] = choice
                    changed = True

            combo = self.mapping_boxes[family]

            combo.blockSignals(True)
            combo.clear()

            combo.addItems(
                ["— Non associé —"]
                + [
                    item["name"]
                    for item in self.inventory
                ]
            )

            chosen = self.associations.get(
                family,
                ""
            )

            if chosen in names:
                combo.setCurrentText(chosen)

            combo.blockSignals(False)

            self.update_indicator(family)

        if changed:
            self.persist_associations()

        self.update_context()

    def update_indicator(self, family):
        name = self.associations.get(
            family,
            ""
        )

        item = next(
            (
                item
                for item in self.inventory
                if item["name"] == name
            ),
            None
        )

        if (
            item is None
            or item["family"] != family
        ):
            message = "○ Non associé"
            color = "#95A4B6"

        else:
            desired = (
                self.release.currentText()
                if family == self.family
                else RELEASES[family][0]
            )

            mismatch = (
                family in (
                    "Debian",
                    "Fedora",
                    "Slackware"
                )
                and desired not in (
                    item["version"],
                    item["codename"]
                )
            )

            if mismatch:
                message = "● À vérifier"
                color = "#E6AD5D"
            else:
                message = "● Connecté"
                color = "#7FCE9D"

        self.indicators[family].setText(
            message
        )

        self.indicators[family].setStyleSheet(
            "color:" + color
        )

    def mapping_changed(self, family, name):
        chosen = (
            ""
            if name == "— Non associé —"
            else name
        )

        item = next(
            (
                item
                for item in self.inventory
                if item["name"] == chosen
            ),
            None
        )

        if item and item["family"] != family:
            self.warning(
                "Cette distribution WSL appartient à "
                + item["family"]
                + ", pas à "
                + family
            )

            self.apply_associations()
            return

        self.associations[family] = chosen

        self.manual_associations.add(
            family
        )

        self.persist_associations()
        self.update_indicator(family)
        self.update_context()

    def reset_associations(self):
        if not self.confirm(
            "Effacer les associations manuelles "
            "et refaire la détection automatique ?"
        ):
            return

        self.manual_associations.clear()
        self.associations.clear()

        self.apply_associations()
        self.persist_associations()

    # --------------------------------------------------------
    # ENVIRONNEMENT
    # --------------------------------------------------------

    def selected_environment(self):
        name = self.wsl_choice.currentText()

        valid_names = [
            item["name"]
            for item in self.inventory
        ]

        if name not in valid_names:
            self.warning(
                "Sélectionne un environnement WSL."
            )
            return ""

        return name

    def project_environment(self):
        name = self.associations.get(
            self.family,
            ""
        )

        item = next(
            (
                item
                for item in self.inventory
                if item["name"] == name
            ),
            None
        )

        if (
            item is None
            or item["family"] != self.family
        ):
            self.warning(
                "Associe une distribution WSL compatible "
                "dans l'onglet WSL2."
            )

            self.tabs.setCurrentIndex(5)
            self.wsl_sections.setCurrentIndex(2)

            return ""

        return name

    def environment_family(self, name):
        item = next(
            (
                item
                for item in self.inventory
                if item["name"] == name
            ),
            None
        )

        return item["family"] if item else ""

    # --------------------------------------------------------
    # CATALOGUE
    # --------------------------------------------------------

    def refresh_catalog(self):
        self.run_task(
            online_catalog,
            (),
            self.catalog_ready
        )

    def catalog_ready(self, result, error):
        if error:
            self.show_wsl_log(error)
            return

        rows, raw = result
        self.catalog_rows = rows

        self.fill_table(
            self.catalog_table,
            rows
        )

        self.wsl_log.setPlainText(
            str(len(rows))
            + " distributions disponibles.\n"
            + (
                raw[:1500]
                if not rows
                else ""
            )
        )

    def install_wsl(self):
        name = self.selected_row(
            self.catalog_table
        )

        available = [
            row[0]
            for row in self.catalog_rows
        ]

        if name not in available:
            self.warning(
                "Sélectionne une distribution "
                "du catalogue WSL."
            )
            return

        if not self.confirm(
            "Installer "
            + name
            + " dans WSL2 ?"
        ):
            return

        self.run_task(
            execute,
            (
                [
                    "wsl.exe",
                    "--install",
                    "--distribution",
                    name,
                    "--no-launch"
                ],
                1800
            ),
            lambda result, error:
                self.wsl_operation_ready(
                    "Installation",
                    result,
                    error
                )
        )

    def remove_wsl(self):
        name = self.selected_row(
            self.installed_table
        )

        if not name:
            self.warning(
                "Sélectionne une distribution installée."
            )
            return

        typed, ok = QInputDialog.getText(
            self,
            "Suppression définitive",
            "Toutes les données de "
            + name
            + " seront perdues.\n"
            "Saisis exactement : "
            + name
        )

        if not ok or typed != name:
            return

        if not self.confirm(
            "Supprimer définitivement "
            + name
            + " ?"
        ):
            return

        self.run_task(
            execute,
            (
                [
                    "wsl.exe",
                    "--unregister",
                    name
                ],
                900
            ),
            lambda result, error:
                self.wsl_operation_ready(
                    "Suppression",
                    result,
                    error
                )
        )

    def wsl_operation_ready(
        self,
        title,
        result,
        error
    ):
        if error:
            self.show_wsl_log(error)
            return

        output, stderr, code = result

        self.show_wsl_log(
            title
            + "\nCode retour : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

        if code == 0:
            self.refresh_wsl()
        else:
            self.warning(
                title + " échouée."
            )

    # --------------------------------------------------------
    # GESTIONNAIRES
    # --------------------------------------------------------

    def test_selected_manager(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in MANAGER_COMMANDS:
            self.warning(
                "Famille Linux inconnue."
            )
            return

        self.run_task(
            test_manager,
            (name, family),
            self.manager_test_ready
        )

    def manager_test_ready(self, result, error):
        if error:
            self.show_wsl_log(error)
            return

        command, response = result
        output, stderr, code = response

        self.show_wsl_log(
            "Commande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

    def check_selected_tools(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in TOOLS:
            self.warning(
                "Famille Linux inconnue."
            )
            return

        self.run_task(
            check_tools,
            (name, family),
            self.selected_tools_ready
        )

    def selected_tools_ready(self, rows, error):
        if error:
            self.show_wsl_log(error)
            return

        self.fill_table(
            self.wsl_tools_table,
            rows
        )

        missing = [
            row[0]
            for row in rows
            if row[2] == "Absent"
        ]

        self.status.setText(
            "Outils manquants : "
            + (
                ", ".join(missing)
                if missing
                else "aucun"
            )
        )

    def install_selected_tools(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in (
            "Debian",
            "Fedora",
            "Arch Linux"
        ):
            self.warning(
                "Installation automatisée non validée "
                "pour " + family
            )
            return

        if not self.confirm(
            "Installer les outils de construction "
            "dans "
            + name
            + " ?\n\n"
            "Cette opération modifie WSL."
        ):
            return

        self.run_task(
            install_tools,
            (name, family),
            self.tools_install_ready
        )

    def tools_install_ready(self, result, error):
        if error:
            self.show_wsl_log(error)
            self.warning(
                "Installation échouée."
            )
            return

        command, response = result
        output, stderr, code = response

        self.show_wsl_log(
            "Commande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n\n"
            + output[-9000:]
            + "\n"
            + stderr[-5000:]
        )

        if code:
            self.warning(
                "Installation échouée. "
                "Consulte le journal."
            )
        else:
            self.check_selected_tools()

    # --------------------------------------------------------
    # DEPOTS
    # --------------------------------------------------------

    def update_selected_repositories(self):
        name = self.selected_environment()

        if name:
            self.start_repository_update(name)

    def update_project_repositories(self):
        name = self.project_environment()

        if name:
            self.start_repository_update(name)

    def start_repository_update(self, name):
        family = self.environment_family(name)

        if not self.confirm(
            "Actualiser les dépôts de "
            + name
            + " ("
            + family
            + ") ?\n\n"
            "Arch Linux effectuera une mise à niveau "
            "complète."
        ):
            return

        self.run_task(
            update_repositories,
            (name, family),
            self.repository_update_ready
        )

    def repository_update_ready(
        self,
        result,
        error
    ):
        if error:
            self.show_wsl_log(error)
            self.app_log.setPlainText(error)
            return

        command, response = result
        output, stderr, code = response

        message = (
            "Commande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

        self.show_wsl_log(
            message[-15000:]
        )

        self.app_log.setPlainText(
            message[-3000:]
        )

        if code:
            self.warning(
                "Actualisation échouée."
            )

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def search_applications(self):
        name = self.project_environment()

        if not name:
            return

        query = self.search_text.text().strip()

        if not query or len(query) > 70:
            self.warning(
                "Recherche invalide."
            )
            return

        family = self.family

        self.run_task(
            search_packages,
            (name, family, query),
            lambda result, error:
                self.search_ready(
                    family,
                    result,
                    error
                )
        )

    def search_ready(
        self,
        family,
        result,
        error
    ):
        if error:
            self.app_log.setPlainText(error)
            return

        output, stderr, code = result

        rows = parse_packages(
            family,
            output
        )

        self.fill_table(
            self.search_results,
            rows
        )

        self.app_log.setPlainText(
            str(len(rows))
            + " résultats\nCode : "
            + str(code)
            + "\n"
            + (
                stderr
                or (
                    output[:1500]
                    if not rows
                    else "Double-clique pour ajouter."
                )
            )
        )

    def refresh_applications(self):
        self.fill_table(
            self.selected_apps,
            [
                (name,)
                for name in sorted(
                    self.applications
                )
            ]
        )

    def add_search_result(self, row, column):
        item = self.search_results.item(row, 0)

        if item:
            self.applications.add(
                item.text()
            )

            self.refresh_applications()

    def remove_application(self, row, column):
        item = self.selected_apps.item(row, 0)

        if item:
            self.applications.discard(
                item.text()
            )

            self.refresh_applications()

    def add_manual_application(self):
        name = self.manual_package.text().strip()

        if not SAFE_PACKAGE.fullmatch(name):
            self.warning(
                "Nom de paquet invalide."
            )
            return

        self.applications.add(name)
        self.manual_package.clear()

        self.refresh_applications()

    # --------------------------------------------------------
    # PAQUETS
    # --------------------------------------------------------

    def project_packages(self):
        packages = set(
            BASE_PACKAGES[self.family]
        )

        packages.update(
            DESKTOPS[self.family][
                self.desktop.currentText()
            ]
        )

        packages.update(
            self.applications
        )

        for name, checkbox in self.flags.items():
            if checkbox.isChecked():
                packages.update(
                    EXTRAS[self.family][name]
                )

        if self.family == "Arch Linux":
            packages.discard("linux")

            kernels = {
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }

            packages.add(
                kernels[self.kernel.currentText()]
            )

        if self.family == "Gentoo":
            packages.add(
                "sys-apps/openrc"
                if self.init_system.currentText() == "OpenRC"
                else "sys-apps/systemd"
            )

        return sorted(packages)

    # --------------------------------------------------------
    # VERIFICATION PROJET
    # --------------------------------------------------------

    def verify_project(self):
        name = self.project_environment()

        if not name:
            return

        self.verification_summary.setText(
            "Vérification de "
            + self.family
            + " "
            + self.release.currentText()
            + " dans WSL2 : "
            + name
        )

        self.run_task(
            check_tools,
            (name, self.family),
            self.verification_ready
        )

    def verification_ready(
        self,
        rows,
        error
    ):
        if error:
            self.verification_log.setPlainText(
                error
            )
            return

        self.fill_table(
            self.verification_table,
            rows
        )

        present = sum(
            1 for row in rows
            if row[2] == "Présent"
        )

        missing = [
            row[0]
            for row in rows
            if row[2] == "Absent"
        ]

        self.verification_summary.setText(
            str(present)
            + " outil(s) présent(s) / "
            + str(len(missing))
            + " absent(s)"
        )

        self.verification_log.setPlainText(
            "Distribution : "
            + self.family
            + " "
            + self.release.currentText()
            + "\nWSL2 : "
            + self.associations.get(
                self.family,
                ""
            )
            + "\nGestionnaire : "
            + MANAGERS[self.family]
            + "\nInstallateur : "
            + INSTALLERS[self.family]
            + "\n\nOutils manquants : "
            + (
                ", ".join(missing)
                if missing
                else "aucun"
            )
            + "\n\n"
            "Cette vérification ne garantit pas "
            "encore la création d'une ISO bootable."
        )

    def install_project_tools(self):
        name = self.project_environment()

        if not name:
            return

        if self.family not in (
            "Debian",
            "Fedora",
            "Arch Linux"
        ):
            self.warning(
                "Installation automatisée non validée "
                "pour cette famille."
            )
            return

        if not self.confirm(
            "Installer les prérequis manquants "
            "pour "
            + self.family
            + " "
            + self.release.currentText()
            + " dans "
            + name
            + " ?\n\n"
            "Cette opération modifie WSL2."
        ):
            return

        self.run_task(
            install_tools,
            (name, self.family),
            self.project_tools_installed
        )

    def project_tools_installed(
        self,
        result,
        error
    ):
        if error:
            self.verification_log.setPlainText(
                error
            )
            self.warning(
                "Installation échouée."
            )
            return

        command, response = result
        output, stderr, code = response

        self.verification_log.setPlainText(
            "Commande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n\n"
            + output[-10000:]
            + "\n"
            + stderr[-5000:]
        )

        if code:
            self.warning(
                "Installation échouée. "
                "Consulte le journal."
            )
        else:
            self.verify_project()

    def analyze_project(self):
        name = self.project_environment()

        if not name:
            return

        self.run_task(
            simulate_packages,
            (
                name,
                self.family,
                self.project_packages()
            ),
            self.analysis_ready
        )

    def analysis_ready(
        self,
        result,
        error
    ):
        if error:
            self.verification_log.setPlainText(
                error
            )
            return

        command, response = result
        output, stderr, code = response

        self.verification_log.setPlainText(
            "Distribution : "
            + self.family
            + " "
            + self.release.currentText()
            + "\nWSL2 : "
            + self.associations.get(
                self.family,
                ""
            )
            + "\nCommande : "
            + command
            + "\nCode retour : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
            + "\n\n"
            "Simulation indicative : elle ne calcule "
            "pas toutes les dépendances d'un "
            "système cible vierge."
        )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    def export_project(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination"
        )

        if not directory:
            return

        data = {
            "application": "Universal Linux Builder",
            "version": VERSION,
            "family": self.family,
            "release": self.release.currentText(),
            "wsl": self.associations.get(
                self.family,
                ""
            ),
            "installer": INSTALLERS[self.family],
            "package_manager": MANAGERS[self.family],
            "desktop": self.desktop.currentText(),
            "init": self.init_system.currentText(),
            "kernel": self.kernel.currentText(),
            "audio": self.audio.currentText(),
            "boot": self.boot.currentText(),
            "packages": self.project_packages(),
            "iso_bootable_verified": False,
            "installation_verified": False
        }

        try:
            target = (
                Path(directory)
                / "universal_linux_project.json"
            )

            target.write_text(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            )

            packages_file = (
                Path(directory)
                / "packages.txt"
            )

            packages_file.write_text(
                "\n".join(
                    self.project_packages()
                ) + "\n",
                encoding="utf-8"
            )

        except OSError as error:
            self.warning(error)
            return

        self.iso_log.setPlainText(
            "Projet exporté :\n"
            + str(target)
            + "\n\n"
            "Liste des paquets :\n"
            + str(packages_file)
            + "\n\n"
            "Ce manifeste ne constitue pas "
            "une ISO bootable."
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = UniversalLinuxBuilder()
    window.show()

    sys.exit(app.exec())
