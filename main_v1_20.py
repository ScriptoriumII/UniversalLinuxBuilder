import sys
import os
import re
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QTabWidget,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QCheckBox,
    QTextEdit,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QInputDialog,
    QSplitter,
    QHeaderView,
    QFrame,
    QAbstractItemView
)

# ================================================================
# CONSTANTES
# ================================================================

APP_NAME = "Universal Linux Builder"
VERSION = "1.20"

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

DISTRO_COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#51A2DA",
    "Arch Linux": "#1793D1",
    "Gentoo": "#9482C9",
    "Slackware": "#7D95A9"
}

DISTRO_SYMBOLS = {
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

SAFE_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

APP_DIRECTORY = (
    Path.home()
    / "Documents"
    / "UniversalLinuxBuilder"
)

LOGO_DIRECTORY = APP_DIRECTORY / "logos"

SETTINGS_FILE = (
    Path(
        os.environ.get(
            "APPDATA",
            str(Path.home())
        )
    )
    / "UniversalLinuxBuilder"
    / "settings.json"
)

# ================================================================
# DESIGN v1.20
# ================================================================

STYLE = """
QWidget {
    background-color: #0D1420;
    color: #E7EDF5;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow {
    background-color: #0D1420;
}

QFrame#Header {
    background-color: #101B2A;
    border-bottom: 1px solid #283A50;
}

QLabel#AppTitle {
    font-size: 20px;
    font-weight: 600;
    color: #F2F6FC;
}

QLabel#ActiveDistribution {
    font-size: 13px;
    font-weight: 600;
    color: #DCE8F6;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 600;
    color: #F0F5FB;
}

QLabel#Context {
    background-color: #152235;
    border: 1px solid #2B4059;
    border-radius: 5px;
    padding: 10px 12px;
    color: #E5EDF7;
    font-weight: 500;
}

QPushButton {
    background-color: #21334A;
    border: 1px solid #344B65;
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #2B4665;
    border-color: #4C729A;
}

QPushButton:pressed {
    background-color: #1C3855;
}

QPushButton:disabled {
    color: #7D8B9C;
    background-color: #182334;
}

QPushButton#DistroButton {
    background-color: #19283B;
    border: 1px solid #32475F;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 34px;
    text-align: left;
    font-weight: 500;
}

QPushButton#DistroButton:hover {
    background-color: #243B56;
    border-color: #54789F;
}

QPushButton#DistroButton[active="true"] {
    background-color: #263F5C;
    border: 1px solid #6B9AC9;
    color: #FFFFFF;
}

QLineEdit,
QComboBox,
QTextEdit,
QTableWidget {
    background-color: #152235;
    border: 1px solid #2E435B;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: #365E87;
}

QLineEdit:focus,
QComboBox:focus {
    border: 1px solid #608FBE;
}

QComboBox {
    min-height: 22px;
}

QComboBox QAbstractItemView {
    background-color: #18283B;
    selection-background-color: #345A80;
}

QTabWidget::pane {
    border: 1px solid #27394F;
    border-radius: 3px;
}

QTabBar::tab {
    background-color: #111D2C;
    color: #C6D2E1;
    padding: 10px 17px;
    border-right: 1px solid #293A50;
}

QTabBar::tab:selected {
    background-color: #1A2B40;
    color: #FFFFFF;
    border-bottom: 2px solid #75ACDF;
}

QTabBar::tab:hover {
    background-color: #20354D;
}

QGroupBox {
    border: 1px solid #2D4057;
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px;
    font-weight: 500;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QHeaderView::section {
    background-color: #243B55;
    color: #EAF1FA;
    border: none;
    border-right: 1px solid #334A65;
    padding: 8px;
    font-weight: 500;
}

QTableWidget {
    alternate-background-color: #1C2C40;
    gridline-color: transparent;
}

QTableWidget::item {
    padding-left: 5px;
}

QTableWidget::item:selected {
    background-color: #31577D;
}

QScrollBar:vertical {
    background: #101B2A;
    width: 11px;
}

QScrollBar::handle:vertical {
    background: #415A74;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #567696;
}

QStatusBar {
    background-color: #101B2A;
    color: #B7C9DD;
}
"""

# ================================================================
# CONFIGURATION
# ================================================================

def load_settings():
    try:
        result = json.loads(
            SETTINGS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(result, dict):
            return result

    except (OSError, ValueError):
        pass

    return {}


def save_settings(data):
    SETTINGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    descriptor, temporary = tempfile.mkstemp(
        prefix="settings_",
        suffix=".tmp",
        dir=SETTINGS_FILE.parent
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temporary,
            SETTINGS_FILE
        )

    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


# ================================================================
# EXECUTION WSL
# ================================================================

def decode_output(raw):
    if raw.startswith(
        (b"\xff\xfe", b"\xfe\xff")
    ):
        return raw.decode(
            "utf-16",
            errors="replace"
        ).replace("\x00", "").strip()

    if b"\x00" in raw[:120]:
        return raw.decode(
            "utf-16-le",
            errors="replace"
        ).replace("\x00", "").lstrip("\ufeff").strip()

    return raw.decode(
        "utf-8",
        errors="replace"
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


def linux(environment, command, root=False, timeout=300):
    arguments = [
        "wsl.exe",
        "--distribution",
        environment
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

    return execute(
        arguments,
        timeout
    )


def installed_wsl():
    output, error, code = execute(
        [
            "wsl.exe",
            "--list",
            "--quiet"
        ],
        60
    )

    if code:
        raise RuntimeError(
            error or output or "Erreur WSL"
        )

    return list(
        dict.fromkeys(
            line.strip()
            for line in output.splitlines()
            if line.strip()
        )
    )


def detect_wsl(environment):
    output, error, code = linux(
        environment,
        "cat /etc/os-release",
        timeout=60
    )

    if code:
        return {
            "name": environment,
            "family": "Inconnue",
            "version": "",
            "codename": ""
        }

    information = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)

            information[key] = (
                value.strip()
                .strip('"')
                .strip("'")
            )

    identifiers = (
        information.get("ID", "")
        + " "
        + information.get("ID_LIKE", "")
    ).lower().split()

    mapping = {
        "debian": "Debian",
        "fedora": "Fedora",
        "arch": "Arch Linux",
        "archlinux": "Arch Linux",
        "gentoo": "Gentoo",
        "slackware": "Slackware"
    }

    family = "Inconnue"

    for identifier in identifiers:
        if identifier in mapping:
            family = mapping[identifier]
            break

    return {
        "name": environment,
        "family": family,
        "version": information.get(
            "VERSION_ID",
            ""
        ),
        "codename": information.get(
            "VERSION_CODENAME",
            ""
        )
    }


def detect_inventory(names):
    return [
        detect_wsl(name)
        for name in names
    ]


def get_catalog():
    output, error, code = execute(
        [
            "wsl.exe",
            "--list",
            "--online"
        ],
        90
    )

    if code:
        raise RuntimeError(
            error or output
        )

    rows = []

    for line in output.splitlines():
        match = re.match(
            r"^\s*([A-Za-z0-9][\w.-]*)\s{2,}(.+?)\s*$",
            line
        )

        if match:
            name, description = match.groups()

            if name.lower() not in (
                "name",
                "nom"
            ):
                rows.append(
                    (name, description)
                )

    return rows, output


def match_environment(family, release, inventory):
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
            item["name"].lower()
        )
    )

    return candidates[0]["name"]


# ================================================================
# GESTIONNAIRES ET OUTILS
# ================================================================

def check_tools(environment, family):
    commands = []

    for executable, package in TOOLS[family]:
        quoted = shlex.quote(executable)

        commands.append(
            "if command -v "
            + quoted
            + " >/dev/null 2>&1; "
            + "then printf '%s\\n' "
            + shlex.quote(executable + ":OK")
            + "; else printf '%s\\n' "
            + shlex.quote(executable + ":ABSENT")
            + "; fi"
        )

    output, error, code = linux(
        environment,
        "; ".join(commands),
        timeout=120
    )

    if code:
        raise RuntimeError(
            error or output
        )

    states = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.split(
                ":",
                1
            )

            states[name] = (
                state.strip() == "OK"
            )

    return [
        (
            executable,
            package,
            "Présent"
            if states.get(executable)
            else "Absent"
        )
        for executable, package in TOOLS[family]
    ]


def test_manager(environment, family):
    executable = MANAGER_COMMANDS[family]

    command = (
        "command -v "
        + shlex.quote(executable)
    )

    return (
        command,
        linux(
            environment,
            command,
            timeout=60
        )
    )


def update_repositories(environment, family):
    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get update"
        ),
        "Fedora": (
            "dnf5 makecache --refresh"
        ),
        "Arch Linux": (
            "pacman -Syu --noconfirm"
        ),
        "Gentoo": (
            "emerge --sync"
        ),
        "Slackware": (
            "slackpkg update"
        )
    }

    command = commands[family]

    return (
        command,
        linux(
            environment,
            command,
            root=True,
            timeout=3600
        )
    )


def install_tools(environment, family):
    if family not in (
        "Debian",
        "Fedora",
        "Arch Linux"
    ):
        raise RuntimeError(
            "Installation automatique non prise "
            "en charge pour cette famille."
        )

    rows = check_tools(
        environment,
        family
    )

    missing = sorted({
        package
        for executable, package, state in rows
        if state == "Absent"
    })

    if not missing:
        return (
            "Aucun outil manquant",
            ("", "", 0)
        )

    arguments = " ".join(
        shlex.quote(package)
        for package in missing
    )

    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get update && "
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y "
            "--no-install-recommends "
            + arguments
        ),
        "Fedora": (
            "dnf5 install -y "
            + arguments
        ),
        "Arch Linux": (
            "pacman -Syu --noconfirm --needed "
            + arguments
        )
    }

    command = commands[family]

    return (
        command,
        linux(
            environment,
            command,
            root=True,
            timeout=3600
        )
    )


# ================================================================
# RECHERCHE APPLICATIONS
# ================================================================

def search_packages(environment, family, query):
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
        environment,
        command,
        timeout=300
    )


def parse_packages(family, output):
    rows = []
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

            rows.append(
                (
                    name,
                    description[:160]
                )
            )

    return rows[:500]


def simulate_packages(environment, family, packages):
    if family == "Slackware":
        raise RuntimeError(
            "Slackware ne dispose pas d'un "
            "solveur natif complet des dépendances."
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

    command = (
        "LC_ALL=C "
        + commands[family]
        + arguments
    )

    return (
        command,
        linux(
            environment,
            command,
            timeout=900
        )
    )


# ================================================================
# THREAD
# ================================================================

class Worker(QThread):
    completed = Signal(object, str)

    def __init__(self, function, *arguments):
        super().__init__()

        self.function = function
        self.arguments = arguments

    def run(self):
        try:
            result = self.function(
                *self.arguments
            )

            self.completed.emit(
                result,
                ""
            )

        except Exception as error:
            self.completed.emit(
                None,
                str(error)
            )


# ================================================================
# LOGOS
# ================================================================

def fallback_icon(family, size=36):
    pixmap = QPixmap(
        size,
        size
    )

    pixmap.fill(
        Qt.GlobalColor.transparent
    )

    painter = QPainter(pixmap)

    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )

    painter.setBrush(
        QColor(DISTRO_COLORS[family])
    )

    painter.setPen(
        Qt.PenStyle.NoPen
    )

    painter.drawRoundedRect(
        2,
        2,
        size - 4,
        size - 4,
        8,
        8
    )

    painter.setPen(
        QColor("#FFFFFF")
    )

    font = QFont(
        "Segoe UI",
        int(size * 0.45)
    )

    font.setBold(True)
    painter.setFont(font)

    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        DISTRO_SYMBOLS[family]
    )

    painter.end()

    return QIcon(pixmap)


def distribution_icon(family, size=36):
    candidates = [
        LOGO_DIRECTORY / (family + ".svg"),
        LOGO_DIRECTORY / (
            family.lower().replace(" ", "-") + ".svg"
        ),
        LOGO_DIRECTORY / (family + ".png")
    ]

    for path in candidates:
        if path.exists():
            icon = QIcon(str(path))

            if not icon.isNull():
                return icon

    return fallback_icon(
        family,
        size
    )


# ================================================================
# APPLICATION
# ================================================================

class UniversalLinuxBuilder(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            APP_NAME + " v" + VERSION
        )

        self.resize(
            1380,
            840
        )

        self.setMinimumSize(
            1050,
            650
        )

        self.settings = load_settings()

        self.associations = dict(
            self.settings.get(
                "wsl_associations",
                {}
            )
        )

        self.manual_associations = set(
            self.settings.get(
                "manual_associations",
                []
            )
        )

        self.inventory = []
        self.catalog = []

        self.family = "Debian"
        self.applications = set()

        self.active_worker = None

        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)

        self.main_layout = QVBoxLayout(central)

        self.main_layout.setContentsMargins(
            12,
            8,
            12,
            8
        )

        self.main_layout.setSpacing(8)

        self.build_header()
        self.build_distribution_bar()

        self.tabs = QTabWidget()
        self.main_layout.addWidget(
            self.tabs,
            1
        )

        self.build_distribution_tab()
        self.build_system_tab()
        self.build_applications_tab()
        self.build_verification_tab()
        self.build_iso_tab()
        self.build_wsl_tab()

        self.statusBar().showMessage(
            "Prêt"
        )

        self.change_distribution(
            "Debian"
        )

        self.refresh_wsl()

    # ============================================================
    # COMPOSANTS GENERIQUES
    # ============================================================

    def create_page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            16,
            14,
            16,
            14
        )

        layout.setSpacing(10)

        self.tabs.addTab(
            widget,
            name
        )

        return layout

    def create_button(self, text, callback):
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def create_table(self, headers):
        table = QTableWidget(
            0,
            len(headers)
        )

        table.setHorizontalHeaderLabels(
            headers
        )

        table.setAlternatingRowColors(True)

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        table.verticalHeader().hide()

        table.verticalHeader().setDefaultSectionSize(
            30
        )

        table.horizontalHeader().setStretchLastSection(
            True
        )

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        return table

    def fill_table(self, table, rows):
        table.setSortingEnabled(False)

        table.setRowCount(
            len(rows)
        )

        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(
                    str(value)
                )

                table.setItem(
                    row_index,
                    column_index,
                    item
                )

        table.setSortingEnabled(True)

    def selected_table_value(self, table):
        row = table.currentRow()

        if row < 0:
            return ""

        item = table.item(
            row,
            0
        )

        return item.text() if item else ""

    def message(self, text):
        QMessageBox.warning(
            self,
            APP_NAME,
            str(text)
        )

    def confirm(self, text):
        result = QMessageBox.question(
            self,
            APP_NAME,
            text
        )

        return (
            result
            == QMessageBox.StandardButton.Yes
        )

    def run_task(self, function, arguments, callback):
        if self.active_worker is not None:
            self.message(
                "Une opération est déjà en cours."
            )
            return

        worker = Worker(
            function,
            *arguments
        )

        self.active_worker = worker

        self.statusBar().showMessage(
            "Opération en cours..."
        )

        worker.completed.connect(
            lambda result, error, current=worker:
                self.task_completed(
                    current,
                    callback,
                    result,
                    error
                )
        )

        worker.finished.connect(
            worker.deleteLater
        )

        worker.start()

    def task_completed(
        self,
        worker,
        callback,
        result,
        error
    ):
        if self.active_worker is worker:
            self.active_worker = None

        self.statusBar().showMessage(
            "Prêt"
        )

        callback(
            result,
            error
        )

    def add_next_button(self, layout, index):
        row = QHBoxLayout()

        row.addStretch()

        row.addWidget(
            self.create_button(
                "Suivant →",
                lambda: self.tabs.setCurrentIndex(
                    index
                )
            )
        )

        layout.addLayout(row)

    # ============================================================
    # EN-TETE
    # ============================================================

    def build_header(self):
        frame = QFrame()
        frame.setObjectName("Header")

        layout = QHBoxLayout(frame)

        layout.setContentsMargins(
            8,
            5,
            8,
            8
        )

        title = QLabel(
            APP_NAME + "  |  v" + VERSION
        )

        title.setObjectName(
            "AppTitle"
        )

        layout.addWidget(title)
        layout.addStretch()

        self.active_icon = QLabel()

        self.active_icon.setFixedSize(
            30,
            30
        )

        layout.addWidget(
            self.active_icon
        )

        self.active_distribution = QLabel()

        self.active_distribution.setObjectName(
            "ActiveDistribution"
        )

        layout.addWidget(
            self.active_distribution
        )

        self.main_layout.addWidget(
            frame
        )

    # ============================================================
    # BANDEAU DISTRIBUTIONS
    # ============================================================

    def build_distribution_bar(self):
        row = QHBoxLayout()

        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        self.distribution_buttons = {}

        for family in FAMILIES:
            button = QPushButton(
                family
            )

            button.setObjectName(
                "DistroButton"
            )

            button.setIcon(
                distribution_icon(
                    family,
                    30
                )
            )

            button.setIconSize(
                QSize(28, 28)
            )

            button.setFixedHeight(
                44
            )

            button.setProperty(
                "active",
                False
            )

            button.clicked.connect(
                lambda checked=False, name=family:
                    self.change_distribution(name)
            )

            row.addWidget(
                button,
                1
            )

            self.distribution_buttons[family] = button

        self.main_layout.addLayout(
            row
        )

    # ============================================================
    # DISTRIBUTION
    # ============================================================

    def build_distribution_tab(self):
        layout = self.create_page(
            "Distribution"
        )

        title = QLabel(
            "Configuration de la distribution"
        )

        title.setObjectName(
            "SectionTitle"
        )

        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self.release = QComboBox()

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        form.addRow(
            "Version Linux",
            self.release
        )

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

        note = QLabel(
            "Sélectionne la distribution dans le bandeau "
            "supérieur, puis sa version ici."
        )

        note.setStyleSheet(
            "color:#9FB1C6;"
        )

        layout.addWidget(note)

        layout.addStretch()

        self.add_next_button(
            layout,
            1
        )

    # ============================================================
    # SYSTEME
    # ============================================================

    def build_system_tab(self):
        layout = self.create_page(
            "Système"
        )

        title = QLabel(
            "Configuration du système Linux"
        )

        title.setObjectName(
            "SectionTitle"
        )

        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

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

        self.display_server = QComboBox()

        self.display_server.addItems([
            "Wayland",
            "X11"
        ])

        self.boot_mode = QComboBox()

        self.boot_mode.addItems([
            "UEFI",
            "BIOS"
        ])

        for label, control in [
            ("Environnement de bureau", self.desktop),
            ("Système d'initialisation", self.init_system),
            ("Noyau", self.kernel),
            ("Serveur graphique", self.display_server),
            ("Audio", self.audio),
            ("Démarrage", self.boot_mode)
        ]:
            form.addRow(
                label,
                control
            )

        layout.addLayout(form)

        group = QGroupBox(
            "Services supplémentaires"
        )

        group_layout = QHBoxLayout(group)

        self.flags = {}

        for name in [
            "Wi-Fi",
            "Bluetooth",
            "Impression"
        ]:
            checkbox = QCheckBox(name)

            checkbox.setChecked(
                name != "Impression"
            )

            self.flags[name] = checkbox

            group_layout.addWidget(
                checkbox
            )

        group_layout.addStretch()

        layout.addWidget(group)

        layout.addStretch()

        self.add_next_button(
            layout,
            2
        )

    # ============================================================
    # APPLICATIONS
    # ============================================================

    def build_applications_tab(self):
        layout = self.create_page(
            "Applications"
        )

        self.app_context = QLabel()
        self.app_context.setObjectName(
            "Context"
        )

        layout.addWidget(
            self.app_context
        )

        row = QHBoxLayout()

        self.search_field = QLineEdit()

        self.search_field.setPlaceholderText(
            "Rechercher une application dans les dépôts..."
        )

        self.search_field.returnPressed.connect(
            self.search_applications
        )

        row.addWidget(
            self.search_field,
            1
        )

        row.addWidget(
            self.create_button(
                "Rechercher",
                self.search_applications
            )
        )

        row.addWidget(
            self.create_button(
                "Actualiser les dépôts",
                self.update_project_repositories
            )
        )

        layout.addLayout(row)

        self.app_results = self.create_table([
            "Paquet",
            "Description"
        ])

        self.app_results.setColumnWidth(
            0,
            270
        )

        self.app_results.cellDoubleClicked.connect(
            self.add_search_result
        )

        layout.addWidget(
            self.app_results,
            3
        )

        label = QLabel(
            "Applications sélectionnées"
        )

        layout.addWidget(label)

        self.selected_apps = self.create_table([
            "Paquet"
        ])

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
            "Ajouter un paquet manuellement"
        )

        row.addWidget(
            self.manual_package,
            1
        )

        row.addWidget(
            self.create_button(
                "Ajouter",
                self.add_manual_application
            )
        )

        layout.addLayout(row)

        self.app_log = QTextEdit()
        self.app_log.setReadOnly(True)

        self.app_log.setMaximumHeight(
            95
        )

        layout.addWidget(
            self.app_log
        )

        self.add_next_button(
            layout,
            3
        )

    # ============================================================
    # VERIFICATION
    # ============================================================

    def build_verification_tab(self):
        layout = self.create_page(
            "Vérification"
        )

        self.verification_context = QLabel()

        self.verification_context.setObjectName(
            "Context"
        )

        self.verification_context.setWordWrap(
            True
        )

        layout.addWidget(
            self.verification_context
        )

        row = QHBoxLayout()

        row.addWidget(
            self.create_button(
                "Vérifier les outils",
                self.verify_project
            )
        )

        row.addWidget(
            self.create_button(
                "Installer les outils manquants",
                self.install_project_tools
            )
        )

        row.addWidget(
            self.create_button(
                "Simuler les dépendances",
                self.analyze_project
            )
        )

        row.addStretch()

        layout.addLayout(row)

        self.verification_summary = QLabel(
            "Aucune vérification effectuée."
        )

        layout.addWidget(
            self.verification_summary
        )

        self.verification_table = self.create_table([
            "Outil",
            "Paquet requis",
            "État"
        ])

        self.verification_table.setColumnWidth(
            0,
            240
        )

        self.verification_table.setColumnWidth(
            1,
            300
        )

        layout.addWidget(
            self.verification_table,
            2
        )

        self.verification_log = QTextEdit()

        self.verification_log.setReadOnly(
            True
        )

        layout.addWidget(
            self.verification_log,
            1
        )

        self.add_next_button(
            layout,
            4
        )

    # ============================================================
    # ISO
    # ============================================================

    def build_iso_tab(self):
        layout = self.create_page(
            "ISO"
        )

        self.iso_context = QLabel()

        self.iso_context.setObjectName(
            "Context"
        )

        layout.addWidget(
            self.iso_context
        )

        group = QGroupBox(
            "Configuration de construction"
        )

        form = QFormLayout(group)

        self.iso_installer = QLabel()
        self.iso_manager = QLabel()
        self.iso_wsl = QLabel()

        form.addRow(
            "Installateur",
            self.iso_installer
        )

        form.addRow(
            "Gestionnaire de paquets",
            self.iso_manager
        )

        form.addRow(
            "Environnement WSL2",
            self.iso_wsl
        )

        layout.addWidget(group)

        warning = QLabel(
            "La construction d'une ISO amorçable "
            "n'est pas encore implémentée. "
            "Le projet peut être exporté pour préparer "
            "la construction avec les outils natifs "
            "de la distribution."
        )

        warning.setWordWrap(
            True
        )

        warning.setStyleSheet(
            "color:#E6BC77;"
        )

        layout.addWidget(
            warning
        )

        layout.addWidget(
            self.create_button(
                "Exporter le manifeste ISO",
                self.export_project
            )
        )

        self.iso_log = QTextEdit()

        self.iso_log.setReadOnly(
            True
        )

        layout.addWidget(
            self.iso_log,
            1
        )

    # ============================================================
    # WSL2 - DESIGN COMPACT v1.18
    # ============================================================

    def build_wsl_tab(self):
        layout = self.create_page(
            "WSL2"
        )

        self.wsl_tabs = QTabWidget()

        layout.addWidget(
            self.wsl_tabs,
            1
        )

        def section(name):
            widget = QWidget()

            section_layout = QVBoxLayout(
                widget
            )

            section_layout.setContentsMargins(
                8,
                8,
                8,
                8
            )

            section_layout.setSpacing(8)

            self.wsl_tabs.addTab(
                widget,
                name
            )

            return section_layout

        # --------------------------------------------------------
        # ENVIRONNEMENTS
        # --------------------------------------------------------

        environments = section(
            "Environnements"
        )

        row = QHBoxLayout()

        row.addWidget(
            self.create_button(
                "Actualiser les WSL",
                self.refresh_wsl
            )
        )

        row.addWidget(
            self.create_button(
                "Catalogue disponible",
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

        self.installed_table = self.create_table([
            "Nom WSL",
            "Famille",
            "Version"
        ])

        self.installed_table.setColumnWidth(
            0,
            180
        )

        self.installed_table.setColumnWidth(
            1,
            130
        )

        installed_layout.addWidget(
            self.installed_table
        )

        installed_layout.addWidget(
            self.create_button(
                "Supprimer la distribution",
                self.remove_wsl
            )
        )

        splitter.addWidget(
            installed_group
        )

        catalog_group = QGroupBox(
            "Distributions disponibles"
        )

        catalog_layout = QVBoxLayout(
            catalog_group
        )

        self.catalog_table = self.create_table([
            "Distribution",
            "Description"
        ])

        self.catalog_table.setColumnWidth(
            0,
            190
        )

        catalog_layout.addWidget(
            self.catalog_table
        )

        catalog_layout.addWidget(
            self.create_button(
                "Installer dans WSL2",
                self.install_wsl
            )
        )

        splitter.addWidget(
            catalog_group
        )

        splitter.setSizes([
            500,
            500
        ])

        environments.addWidget(
            splitter,
            1
        )

        # --------------------------------------------------------
        # OUTILS ET DEPOTS
        # --------------------------------------------------------

        tools_layout = section(
            "Outils et dépôts"
        )

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Environnement WSL :")
        )

        self.wsl_choice = QComboBox()

        row.addWidget(
            self.wsl_choice,
            1
        )

        row.addWidget(
            self.create_button(
                "Tester le gestionnaire",
                self.test_selected_manager
            )
        )

        row.addWidget(
            self.create_button(
                "Vérifier",
                self.check_selected_tools
            )
        )

        row.addWidget(
            self.create_button(
                "Installer les outils",
                self.install_selected_tools
            )
        )

        row.addWidget(
            self.create_button(
                "Actualiser les dépôts",
                self.update_selected_repositories
            )
        )

        tools_layout.addLayout(row)

        self.wsl_tools_table = self.create_table([
            "Exécutable",
            "Paquet requis",
            "État"
        ])

        self.wsl_tools_table.setColumnWidth(
            0,
            220
        )

        self.wsl_tools_table.setColumnWidth(
            1,
            300
        )

        tools_layout.addWidget(
            self.wsl_tools_table,
            1
        )

        # --------------------------------------------------------
        # ASSOCIATIONS
        # --------------------------------------------------------

        associations_layout = section(
            "Associations"
        )

        description = QLabel(
            "Les environnements WSL sont détectés "
            "automatiquement. Les associations "
            "manuelles sont conservées."
        )

        associations_layout.addWidget(
            description
        )

        group = QGroupBox(
            "Associations WSL aux distributions"
        )

        form = QFormLayout(
            group
        )

        self.mapping_boxes = {}
        self.mapping_indicators = {}

        for family in FAMILIES:
            row = QHBoxLayout()

            combo = QComboBox()

            combo.addItem(
                "— Non associé —"
            )

            combo.currentTextChanged.connect(
                lambda name, current_family=family:
                    self.mapping_changed(
                        current_family,
                        name
                    )
            )

            row.addWidget(
                combo,
                1
            )

            indicator = QLabel(
                "Non associé"
            )

            indicator.setMinimumWidth(
                130
            )

            row.addWidget(
                indicator
            )

            form.addRow(
                family,
                row
            )

            self.mapping_boxes[family] = combo
            self.mapping_indicators[family] = indicator

        associations_layout.addWidget(
            group
        )

        row = QHBoxLayout()

        row.addWidget(
            self.create_button(
                "Réassocier automatiquement",
                self.reset_associations
            )
        )

        row.addStretch()

        associations_layout.addLayout(
            row
        )

        associations_layout.addStretch()

        # --------------------------------------------------------
        # JOURNAL WSL
        # --------------------------------------------------------

        row = QHBoxLayout()

        self.log_button = self.create_button(
            "Afficher le journal ▾",
            self.toggle_wsl_log
        )

        row.addWidget(
            self.log_button
        )

        row.addStretch()

        layout.addLayout(
            row
        )

        self.wsl_log = QTextEdit()

        self.wsl_log.setReadOnly(
            True
        )

        self.wsl_log.setVisible(
            False
        )

        self.wsl_log.setMaximumHeight(
            150
        )

        layout.addWidget(
            self.wsl_log
        )

    # ============================================================
    # DISTRIBUTION ACTIVE
    # ============================================================

    def change_distribution(self, family):
        self.family = family

        self.release.blockSignals(
            True
        )

        self.release.clear()

        self.release.addItems(
            RELEASES[family]
        )

        self.release.blockSignals(
            False
        )

        self.desktop.clear()

        self.desktop.addItems(
            list(
                DESKTOPS[family].keys()
            )
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

        self.kernel.setCurrentText(
            "Stable"
        )

        self.installer_label.setText(
            INSTALLERS[family]
        )

        self.manager_label.setText(
            MANAGERS[family]
        )

        for name, button in self.distribution_buttons.items():
            active = (
                name == family
            )

            button.setProperty(
                "active",
                active
            )

            button.style().unpolish(
                button
            )

            button.style().polish(
                button
            )

            button.update()

        self.update_context()

    def release_changed(self, *_):
        self.update_context()

        if self.inventory:
            self.apply_associations()

    def update_context(self):
        release = self.release.currentText()

        environment = self.associations.get(
            self.family,
            ""
        ) or "Non associé"

        icon = distribution_icon(
            self.family,
            30
        )

        self.active_icon.setPixmap(
            icon.pixmap(
                QSize(28, 28)
            )
        )

        self.active_distribution.setText(
            self.family
            + "  •  "
            + release
        )

        context = (
            self.family
            + " "
            + release
            + "  |  "
            + self.desktop.currentText()
            + "  |  "
            + MANAGERS[self.family]
        )

        self.app_context.setText(
            "APPLICATIONS  •  "
            + context
            + "  |  WSL2 : "
            + environment
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
        )

        self.iso_installer.setText(
            INSTALLERS[self.family]
        )

        self.iso_manager.setText(
            MANAGERS[self.family]
        )

        self.iso_wsl.setText(
            environment
        )

    # ============================================================
    # JOURNAL
    # ============================================================

    def toggle_wsl_log(self):
        visible = not self.wsl_log.isVisible()

        self.wsl_log.setVisible(
            visible
        )

        self.log_button.setText(
            "Masquer le journal ▴"
            if visible
            else "Afficher le journal ▾"
        )

    def show_wsl_log(self, text):
        self.wsl_log.setPlainText(
            str(text)
        )

        if not self.wsl_log.isVisible():
            self.toggle_wsl_log()

    # ============================================================
    # ASSOCIATIONS WSL
    # ============================================================

    def persist_associations(self):
        self.settings["version"] = VERSION

        self.settings["wsl_associations"] = dict(
            self.associations
        )

        self.settings["manual_associations"] = sorted(
            self.manual_associations
        )

        try:
            save_settings(
                self.settings
            )

        except OSError as error:
            self.statusBar().showMessage(
                "Sauvegarde impossible : "
                + str(error)
            )

    def refresh_wsl(self):
        self.run_task(
            installed_wsl,
            (),
            self.wsl_names_ready
        )

    def wsl_names_ready(self, names, error):
        if error:
            self.show_wsl_log(
                error
            )
            return

        self.run_task(
            detect_inventory,
            (names,),
            self.inventory_ready
        )

    def inventory_ready(self, inventory, error):
        if error:
            self.show_wsl_log(
                error
            )
            return

        self.inventory = inventory

        rows = [
            (
                item["name"],
                item["family"],
                item["version"]
            )
            for item in inventory
        ]

        self.fill_table(
            self.installed_table,
            rows
        )

        previous = self.wsl_choice.currentText()

        self.wsl_choice.clear()

        self.wsl_choice.addItems([
            item["name"]
            for item in inventory
        ])

        names = [
            item["name"]
            for item in inventory
        ]

        if previous in names:
            self.wsl_choice.setCurrentText(
                previous
            )

        self.apply_associations()

        self.wsl_log.setPlainText(
            "Distributions détectées :\n\n"
            + "\n".join(
                item["name"]
                + " → "
                + item["family"]
                + " "
                + item["version"]
                for item in inventory
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

            item = next(
                (
                    item
                    for item in self.inventory
                    if item["name"] == saved
                ),
                None
            )

            valid = (
                item is not None
                and item["family"] == family
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

                    choice = match_environment(
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

            combo.blockSignals(
                True
            )

            combo.clear()

            combo.addItems(
                ["— Non associé —"]
                + [
                    item["name"]
                    for item in self.inventory
                ]
            )

            selected = self.associations.get(
                family,
                ""
            )

            if selected in names:
                combo.setCurrentText(
                    selected
                )

            combo.blockSignals(
                False
            )

            self.update_mapping_indicator(
                family
            )

        if changed:
            self.persist_associations()

        self.update_context()

    def update_mapping_indicator(self, family):
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
            text = "○ Non associé"
            color = "#94A6BB"

        else:
            text = "● Connecté"
            color = "#82D3A3"

        indicator = self.mapping_indicators[
            family
        ]

        indicator.setText(
            text
        )

        indicator.setStyleSheet(
            "color:" + color
        )

    def mapping_changed(self, family, name):
        selected = (
            ""
            if name == "— Non associé —"
            else name
        )

        item = next(
            (
                item
                for item in self.inventory
                if item["name"] == selected
            ),
            None
        )

        if (
            item is not None
            and item["family"] != family
        ):
            self.message(
                "Cette distribution WSL appartient "
                "à la famille "
                + item["family"]
                + "."
            )

            self.apply_associations()
            return

        self.associations[family] = selected

        self.manual_associations.add(
            family
        )

        self.persist_associations()

        self.update_mapping_indicator(
            family
        )

        self.update_context()

    def reset_associations(self):
        if not self.confirm(
            "Réinitialiser les associations WSL "
            "et relancer la détection automatique ?"
        ):
            return

        self.manual_associations.clear()
        self.associations.clear()

        self.apply_associations()
        self.persist_associations()

    # ============================================================
    # SELECTION WSL
    # ============================================================

    def selected_environment(self):
        name = self.wsl_choice.currentText()

        names = [
            item["name"]
            for item in self.inventory
        ]

        if name not in names:
            self.message(
                "Sélectionne un environnement WSL."
            )
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

        return (
            item["family"]
            if item
            else ""
        )

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
            self.message(
                "Aucun environnement WSL compatible "
                "n'est associé à "
                + self.family
                + "."
            )

            self.tabs.setCurrentIndex(
                5
            )

            self.wsl_tabs.setCurrentIndex(
                2
            )

            return ""

        return name

    # ============================================================
    # CATALOGUE WSL
    # ============================================================

    def refresh_catalog(self):
        self.run_task(
            get_catalog,
            (),
            self.catalog_ready
        )

    def catalog_ready(self, result, error):
        if error:
            self.show_wsl_log(
                error
            )
            return

        rows, raw = result

        self.catalog = rows

        self.fill_table(
            self.catalog_table,
            rows
        )

        if not rows:
            self.show_wsl_log(
                raw
            )

    def install_wsl(self):
        name = self.selected_table_value(
            self.catalog_table
        )

        available = [
            item[0]
            for item in self.catalog
        ]

        if name not in available:
            self.message(
                "Sélectionne une distribution "
                "dans le catalogue."
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
        name = self.selected_table_value(
            self.installed_table
        )

        if not name:
            self.message(
                "Sélectionne une distribution installée."
            )
            return

        typed, accepted = QInputDialog.getText(
            self,
            "Suppression définitive",
            "Toutes les données de "
            + name
            + " seront supprimées.\n\n"
            "Saisis exactement : "
            + name
        )

        if (
            not accepted
            or typed != name
        ):
            return

        if not self.confirm(
            "Confirmer la suppression définitive "
            "de "
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
        operation,
        result,
        error
    ):
        if error:
            self.show_wsl_log(
                error
            )
            return

        output, stderr, code = result

        self.show_wsl_log(
            operation
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
            self.message(
                operation
                + " échouée."
            )

    # ============================================================
    # TEST GESTIONNAIRE
    # ============================================================

    def test_selected_manager(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(
            name
        )

        if family not in MANAGER_COMMANDS:
            self.message(
                "Famille Linux inconnue."
            )
            return

        self.run_task(
            test_manager,
            (name, family),
            self.manager_ready
        )

    def manager_ready(self, result, error):
        if error:
            self.show_wsl_log(
                error
            )
            return

        command, response = result

        output, stderr, code = response

        self.show_wsl_log(
            "Commande : "
            + command
            + "\nCode retour : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

    # ============================================================
    # OUTILS WSL
    # ============================================================

    def check_selected_tools(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(
            name
        )

        if family not in TOOLS:
            self.message(
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
            self.show_wsl_log(
                error
            )
            return

        self.fill_table(
            self.wsl_tools_table,
            rows
        )

    def install_selected_tools(self):
        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(
            name
        )

        if family not in (
            "Debian",
            "Fedora",
            "Arch Linux"
        ):
            self.message(
                "Installation automatique non prise "
                "en charge pour cette famille."
            )
            return

        if not self.confirm(
            "Installer les outils nécessaires "
            "dans "
            + name
            + " ?"
        ):
            return

        self.run_task(
            install_tools,
            (name, family),
            self.selected_tools_installed
        )

    def selected_tools_installed(
        self,
        result,
        error
    ):
        if error:
            self.show_wsl_log(
                error
            )
            self.message(
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
            self.message(
                "Installation échouée."
            )

        else:
            self.check_selected_tools()

    # ============================================================
    # DEPOTS
    # ============================================================

    def update_selected_repositories(self):
        name = self.selected_environment()

        if name:
            self.start_repository_update(
                name
            )

    def update_project_repositories(self):
        name = self.project_environment()

        if name:
            self.start_repository_update(
                name
            )

    def start_repository_update(self, name):
        family = self.environment_family(
            name
        )

        if family not in MANAGERS:
            self.message(
                "Famille Linux inconnue."
            )
            return

        warning = ""

        if family == "Arch Linux":
            warning = (
                "\n\nAttention : Pacman effectuera "
                "une mise à niveau complète."
            )

        if not self.confirm(
            "Actualiser les dépôts de "
            + name
            + " ("
            + family
            + ") ?"
            + warning
        ):
            return

        self.run_task(
            update_repositories,
            (name, family),
            self.repositories_ready
        )

    def repositories_ready(
        self,
        result,
        error
    ):
        if error:
            self.show_wsl_log(
                error
            )

            self.app_log.setPlainText(
                error
            )

            return

        command, response = result

        output, stderr, code = response

        message = (
            "Commande : "
            + command
            + "\nCode retour : "
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
            self.message(
                "Actualisation des dépôts échouée."
            )

    # ============================================================
    # APPLICATIONS
    # ============================================================

    def search_applications(self):
        name = self.project_environment()

        if not name:
            return

        query = self.search_field.text().strip()

        if (
            not query
            or len(query) > 70
        ):
            self.message(
                "Recherche invalide."
            )
            return

        family = self.family

        self.run_task(
            search_packages,
            (
                name,
                family,
                query
            ),
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
            self.app_log.setPlainText(
                error
            )
            return

        output, stderr, code = result

        rows = parse_packages(
            family,
            output
        )

        self.fill_table(
            self.app_results,
            rows
        )

        self.app_log.setPlainText(
            str(len(rows))
            + " résultat(s).\n"
            + "Code retour : "
            + str(code)
            + "\n\n"
            + (
                stderr
                or (
                    output[:1500]
                    if not rows
                    else "Double-clique sur un paquet "
                         "pour l'ajouter."
                )
            )
        )

    def refresh_selected_applications(self):
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
        item = self.app_results.item(
            row,
            0
        )

        if item:
            self.applications.add(
                item.text()
            )

            self.refresh_selected_applications()

    def remove_application(self, row, column):
        item = self.selected_apps.item(
            row,
            0
        )

        if item:
            self.applications.discard(
                item.text()
            )

            self.refresh_selected_applications()

    def add_manual_application(self):
        package = self.manual_package.text().strip()

        if not SAFE_PACKAGE.fullmatch(
            package
        ):
            self.message(
                "Nom de paquet invalide."
            )
            return

        self.applications.add(
            package
        )

        self.manual_package.clear()

        self.refresh_selected_applications()

    # ============================================================
    # LISTE PAQUETS
    # ============================================================

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
            packages.discard(
                "linux"
            )

            kernels = {
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }

            packages.add(
                kernels[
                    self.kernel.currentText()
                ]
            )

        if self.family == "Gentoo":
            if self.init_system.currentText() == "OpenRC":
                packages.add(
                    "sys-apps/openrc"
                )

            else:
                packages.add(
                    "sys-apps/systemd"
                )

        return sorted(
            packages
        )

    # ============================================================
    # VERIFICATION
    # ============================================================

    def verify_project(self):
        name = self.project_environment()

        if not name:
            return

        self.verification_summary.setText(
            "Vérification : "
            + self.family
            + " "
            + self.release.currentText()
            + "  |  WSL2 : "
            + name
        )

        self.run_task(
            check_tools,
            (
                name,
                self.family
            ),
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
            1
            for row in rows
            if row[2] == "Présent"
        )

        missing = [
            row[0]
            for row in rows
            if row[2] == "Absent"
        ]

        self.verification_summary.setText(
            str(present)
            + " outil(s) présent(s)  |  "
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
            "La présence des outils ne garantit pas "
            "qu'une ISO soit amorçable."
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
            self.message(
                "Installation automatique non prise "
                "en charge pour cette famille."
            )
            return

        if not self.confirm(
            "Installer les outils manquants "
            "pour "
            + self.family
            + " dans WSL2 "
            + name
            + " ?"
        ):
            return

        self.run_task(
            install_tools,
            (
                name,
                self.family
            ),
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

            self.message(
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
            self.message(
                "Installation échouée."
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
            "Simulation indicative : les dépendances "
            "d'un système cible vierge peuvent différer "
            "de celles de l'environnement WSL."
        )

    # ============================================================
    # EXPORT PROJET ISO
    # ============================================================

    def export_project(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination"
        )

        if not directory:
            return

        data = {
            "application": APP_NAME,
            "version": VERSION,
            "distribution": self.family,
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
            "display_server": self.display_server.currentText(),
            "audio": self.audio.currentText(),
            "boot_mode": self.boot_mode.currentText(),
            "packages": self.project_packages(),
            "bootable_iso_created": False,
            "ventoy_verified": False
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
                )
                + "\n",
                encoding="utf-8"
            )

        except OSError as error:
            self.message(
                error
            )
            return

        self.iso_log.setPlainText(
            "Manifeste exporté :\n"
            + str(target)
            + "\n\n"
            "Liste des paquets :\n"
            + str(packages_file)
            + "\n\n"
            "La création de l'ISO bootable "
            "reste à implémenter."
        )


# ================================================================
# DEMARRAGE
# ================================================================

if __name__ == "__main__":
    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    window = UniversalLinuxBuilder()

    window.show()

    sys.exit(
        app.exec()
    )
