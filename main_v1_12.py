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
    QMessageBox, QInputDialog, QGroupBox, QSplitter,
    QHeaderView, QAbstractItemView
)

VERSION = "1.12"

FAMILIES = [
    "Debian", "Fedora", "Arch Linux", "Gentoo", "Slackware"
]

RELEASES = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

MANAGERS = {
    "Debian": "apt-get",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

DESKTOPS = {
    "Debian": {
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "lightdm"]
    },
    "Fedora": {
        "GNOME": ["gnome-shell", "gnome-session", "gdm"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel", "xfwm4"],
        "Budgie": ["budgie-desktop"]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop"]
    },
    "Gentoo": {
        "GNOME": ["gnome-base/gnome", "gnome-base/gdm"],
        "KDE Plasma": ["kde-plasma/plasma-meta", "x11-misc/sddm"],
        "Xfce": ["xfce-base/xfce4-meta", "x11-misc/lightdm"]
    },
    "Slackware": {
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session"]
    }
}

BASE = {
    "Debian": ["linux-image-amd64", "systemd-sysv", "network-manager"],
    "Fedora": ["kernel", "systemd", "NetworkManager"],
    "Arch Linux": ["base", "linux", "networkmanager"],
    "Gentoo": ["sys-kernel/gentoo-kernel", "sys-apps/openrc"],
    "Slackware": ["kernel-generic", "networkmanager"]
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
        "PipeWire": ["media-video/pipewire"],
        "PulseAudio": ["media-sound/pulseaudio"],
        "ALSA": ["media-sound/alsa-utils"]
    },
    "Slackware": {
        "PipeWire": ["pipewire"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    }
}

EXTRAS = {
    "Debian": {
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["firmware-linux-free"]
    },
    "Fedora": {
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"]
    },
    "Arch Linux": {
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"]
    },
    "Gentoo": {
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmware": ["sys-kernel/linux-firmware"]
    },
    "Slackware": {
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["kernel-firmware"]
    }
}

SAFE_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

STYLE_DARK = """
QWidget {
    background: #151d2a;
    color: #edf3fb;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #202d40;
    border: 1px solid #42566e;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #304966;
    border: 1px solid #587694;
    border-radius: 5px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #41648b;
}
QTabBar::tab {
    padding: 10px 17px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #67adff;
}
QTableWidget {
    alternate-background-color: #26364b;
    gridline-color: transparent;
}
QTableWidget::item {
    padding-left: 8px;
}
QHeaderView::section {
    background: #334b68;
    border: none;
    border-right: 1px solid #506681;
    padding: 8px;
}
QGroupBox {
    border: 1px solid #40556e;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
"""

STYLE_LIGHT = """
QWidget {
    background: #f5f7fb;
    color: #182638;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: white;
    border: 1px solid #c2cfdd;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #e0eaf5;
    border: 1px solid #b9c9db;
    border-radius: 5px;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #ccdef1;
}
QTabBar::tab {
    padding: 10px 17px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #2874d4;
}
QTableWidget {
    alternate-background-color: #edf3fa;
    gridline-color: transparent;
}
QTableWidget::item {
    padding-left: 8px;
}
QHeaderView::section {
    background: #dce7f3;
    border: none;
    border-right: 1px solid #bdccdb;
    padding: 8px;
}
QGroupBox {
    border: 1px solid #c2cfdd;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
"""


# ============================================================
# COMMANDES WINDOWS / WSL
# ============================================================

def decode_output(data):
    if b"\x00" in data:
        return data.decode("utf-16-le", "replace").replace("\ufeff", "")
    return data.decode("utf-8", "replace")


def run_command(argv, timeout=180, check=True):
    process = subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    stdout = decode_output(process.stdout)
    stderr = decode_output(process.stderr)

    if check and process.returncode:
        raise RuntimeError(
            (stderr or stdout or f"Code {process.returncode}")[-4000:]
        )

    return stdout, stderr, process.returncode


def installed_wsl():
    output, _, _ = run_command(
        ["wsl.exe", "--list", "--quiet"],
        45
    )
    return [
        line.strip().strip("\x00").lstrip("\ufeff")
        for line in output.splitlines()
        if line.strip().strip("\x00")
    ]


def online_catalog():
    output, _, _ = run_command(
        ["wsl.exe", "--list", "--online"],
        60
    )

    rows = []
    for line in output.splitlines():
        line = line.strip()

        match = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s{2,}(.+)$",
            line
        )

        if match:
            name, description = match.groups()

            if name.lower() not in ("name", "nom"):
                rows.append((name, description))

    return rows, output


def wsl_command(env, script, timeout=180, root=False):
    argv = [
        "wsl.exe", "--distribution", env
    ]

    if root:
        argv += ["--user", "root"]

    argv += [
        "--exec", "/bin/sh", "-lc", script
    ]

    return run_command(argv, timeout, False)


def identify_family(env):
    script = (
        "cat /etc/os-release; "
        "echo __ULB_MANAGERS__; "
        "for x in apt-get dnf5 pacman emerge slackpkg; "
        'do command -v "$x" || true; done'
    )

    output, error, code = wsl_command(env, script, 90)

    if code:
        raise RuntimeError(error or output)

    info = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in ("ID", "ID_LIKE", "VERSION_ID"):
                info[key] = value.strip().strip('"')

    distro_id = info.get("ID", "").lower()
    distro_like = info.get("ID_LIKE", "").lower()

    if distro_id in ("debian", "ubuntu") or "debian" in distro_like:
        family = "Debian"
    elif distro_id == "fedora" or "fedora" in distro_like:
        family = "Fedora"
    elif distro_id in ("arch", "archlinux"):
        family = "Arch Linux"
    elif distro_id == "gentoo":
        family = "Gentoo"
    elif distro_id == "slackware":
        family = "Slackware"
    else:
        family = ""

    # Un Ubuntu n'est pas un environnement Debian
    # compatible avec un projet Debian natif.
    if distro_id == "ubuntu":
        family = "Ubuntu (non pris en charge comme Debian)"

    return family, info, output


def manager_update(family):
    return {
        "Debian": "apt-get update",
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman -Sy",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }[family]


def manager_search(family, query):
    query = shlex.quote(query)

    return {
        "Debian": "LC_ALL=C apt-cache search " + query,
        "Fedora": "LC_ALL=C dnf5 search " + query,
        "Arch Linux": "LC_ALL=C pacman -Ss " + query,
        "Gentoo": "LC_ALL=C emerge --search " + query,
        "Slackware": "LC_ALL=C slackpkg search " + query
    }[family]


def parse_search(family, output):
    result = []
    seen = set()

    for line in output.splitlines():
        line = line.strip()
        name = ""
        version = "?"
        description = ""

        if family == "Debian":
            match = re.match(
                r"^([\w+.-]+)\s+-\s+(.+)$",
                line
            )
            if match:
                name, description = match.groups()

        elif family == "Fedora":
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|noarch|aarch64|i686|src)"
                r"\s*(?::|\s)\s*(.*)$",
                line
            )
            if match:
                name, description = match.groups()

        elif family == "Arch Linux":
            match = re.match(
                r"^[\w+.-]+/([^ ]+)\s+([^ ]+)",
                line
            )
            if match:
                name, version = match.groups()

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
                name, version = match.groups()

        if name and SAFE_PACKAGE.fullmatch(name) and name not in seen:
            result.append((name, version, description[:220]))
            seen.add(name)

    return result[:500]


def simulation_command(family, packages):
    args = " ".join(shlex.quote(p) for p in packages)

    return {
        "Debian": "LC_ALL=C apt-get -s install " + args,
        "Fedora": "LC_ALL=C dnf5 --assumeno install " + args,
        "Arch Linux": (
            'LC_ALL=C pacman -Sp '
            '--print-format "%n|%v|%s" ' + args
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend --verbose --tree " + args
        ),
        "Slackware": (
            'echo "Slackware : pas de solveur de dependances natif"'
        )
    }[family]


def parse_size(value):
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(B|KiB|MiB|GiB)",
        value,
        re.I
    )

    if not match:
        return None

    number = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()

    factor = {
        "b": 1,
        "kib": 1024,
        "mib": 1024 ** 2,
        "gib": 1024 ** 3
    }[unit]

    return int(number * factor)


def human_size(value):
    if value is None:
        return "Inconnue"

    size = float(value)

    for unit in ("o", "Kio", "Mio", "Gio"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size:.1f} Tio"


def parse_simulation(family, output, requested):
    result = {
        package: {
            "version": "?",
            "status": "Demandé",
            "bytes": None
        }
        for package in requested
    }

    for line in output.splitlines():
        match = None
        size = None

        if family == "Debian":
            match = re.match(
                r"^Inst\s+(\S+)"
                r"(?:\s+\[.*?\])?\s+\(([^ )]+)",
                line
            )

        elif family == "Arch Linux":
            match = re.match(
                r"^([^|]+)\|([^|]+)\|(\d+)$",
                line.strip()
            )
            if match:
                size = int(match.group(3))

        elif family == "Fedora":
            match = re.match(
                r"^\s*([\w+.-]+)\s+"
                r"(?:x86_64|noarch|aarch64|i686)\s+"
                r"([\w:~.+-]+)\s+\S+"
                r"(?:\s+(.+))?$",
                line
            )
            if match:
                size = parse_size(match.group(3) or "")

        elif family == "Gentoo":
            match = re.search(
                r"\[ebuild[^]]*\]\s+"
                r"([\w+.-]+/[\w+.-]+)-([\w.+-]+)",
                line
            )

        if match:
            name = match.group(1)
            version = match.group(2)

            result[name] = {
                "version": version,
                "status": "Transaction",
                "bytes": size
            }

    return result


def evaluate_simulation(family, output, error, code):
    if code == 0:
        return True, "Simulation terminée"

    if family == "Fedora":
        combined = output + "\n" + error

        transaction = bool(
            re.search(
                r"(?m)^\s*Package\s+Arch\s+Version",
                combined
            )
        )

        summary = bool(
            re.search(
                r"Transaction Summary|"
                r"Total download size|"
                r"Total size of",
                combined,
                re.I
            )
        )

        refusal = bool(
            re.search(
                r"Operation aborted|"
                r"Operation cancelled|"
                r"Operation canceled|"
                r"Is this ok.*[Nn]",
                combined,
                re.I
            )
        )

        if transaction and summary and refusal:
            return (
                True,
                "Transaction DNF5 affichée ; refus volontaire --assumeno"
            )

    return False, f"Échec du gestionnaire : code {code}"


def estimate_size(family, packages):
    """
    Fourchette purement indicative.
    Ce n'est PAS une mesure de la future ISO.
    """

    values = [
        item["bytes"]
        for item in packages.values()
        if item.get("bytes") is not None
    ]

    if not values:
        return "Indisponible : tailles non fournies"

    coverage = len(values) / max(len(packages), 1)
    known = sum(values)

    if coverage < 0.25:
        return (
            f"Données insuffisantes : {human_size(known)} "
            "connus seulement"
        )

    extrapolated = known / coverage

    minimum = int(extrapolated * 0.8 + 650 * 1024 ** 2)
    maximum = int(extrapolated * 2.0 + 1700 * 1024 ** 2)

    return (
        f"{human_size(minimum)} à {human_size(maximum)} "
        "(estimation très approximative)"
    )


# ============================================================
# CONSTRUCTION ISO
# ============================================================

def build_iso(family, env, release, packages, destination):
    """
    Construction expérimentale avec les outils officiels
    de chaque distribution.

    Debian : live-build
    Arch : archiso

    La construction peut échouer sous WSL2.
    """

    if family not in ("Debian", "Arch Linux"):
        raise RuntimeError(
            "Construction ISO non activée pour " + family
            + ". La simulation reste disponible."
        )

    target = Path(destination)

    if any(target.iterdir()):
        raise RuntimeError(
            "Le dossier de construction doit être vide."
        )

    output, error, code = run_command(
        [
            "wsl.exe", "--distribution", env,
            "--exec", "wslpath", "-a", str(target)
        ],
        60,
        False
    )

    if code:
        raise RuntimeError(error or output)

    linux_path = output.strip()

    if not linux_path.startswith("/"):
        raise RuntimeError("Chemin WSL invalide.")

    quoted = shlex.quote(linux_path)

    for package in packages:
        if not SAFE_PACKAGE.fullmatch(package):
            raise RuntimeError(
                "Nom de paquet invalide : " + package
            )

    package_args = " ".join(
        shlex.quote(package) for package in packages
    )

    if family == "Debian":
        script = (
            "set -eu; "
            "command -v lb >/dev/null || "
            "{ echo 'Installer live-build'; exit 31; }; "
            "command -v debootstrap >/dev/null || "
            "{ echo 'Installer debootstrap'; exit 32; }; "
            "mkdir -p " + quoted + "/debian-live; "
            "cd " + quoted + "/debian-live; "
            "lb config "
            "--distribution " + shlex.quote(release) + " "
            "--architectures amd64 "
            "--binary-images iso-hybrid; "
            "mkdir -p config/package-lists; "
            "printf '%s\\n' " + package_args
            + " > config/package-lists/ulb.list.chroot; "
            "lb build"
        )

    else:
        script = (
            "set -eu; "
            "command -v mkarchiso >/dev/null || "
            "{ echo 'Installer archiso'; exit 41; }; "
            "test -d /usr/share/archiso/configs/releng || "
            "{ echo 'Profil releng absent'; exit 42; }; "
            "mkdir -p " + quoted + "/arch-build; "
            "cp -a /usr/share/archiso/configs/releng "
            + quoted + "/arch-build/profile; "
            "cd " + quoted + "/arch-build; "
            "printf '%s\\n' " + package_args
            + " >> profile/packages.x86_64; "
            "sort -u profile/packages.x86_64 "
            "-o profile/packages.x86_64; "
            "mkdir -p work out; "
            "mkarchiso -v -w work -o out profile"
        )

    output, error, code = run_command(
        [
            "wsl.exe",
            "--distribution", env,
            "--user", "root",
            "--exec", "/bin/sh", "-lc", script
        ],
        7200,
        False
    )

    report = (
        f"Distribution : {family}\n"
        f"Environnement WSL : {env}\n"
        f"Code : {code}\n\n"
        + output + "\n" + error
    )

    (target / "build_report.txt").write_text(
        report,
        encoding="utf-8"
    )

    if code:
        raise RuntimeError(
            "Échec de construction.\n"
            "Voir build_report.txt.\n"
            + (error or output)[-2000:]
        )

    images = list(target.rglob("*.iso"))

    if not images:
        raise RuntimeError(
            "Aucun fichier ISO produit malgré "
            "la fin de la commande."
        )

    inspections = []

    for image in images:
        with image.open("rb") as handle:
            handle.seek(16 * 2048)
            descriptor = handle.read(2048)

        iso9660 = (
            len(descriptor) >= 7
            and descriptor[1:6] == b"CD001"
        )

        inspections.append({
            "path": str(image),
            "size": image.stat().st_size,
            "iso9660": iso9660,
            "boot_tested": False,
            "ventoy_tested": False
        })

    return inspections, report


# ============================================================
# THREAD DE TRAVAIL
# ============================================================

class Worker(QThread):
    completed = Signal(object, str)

    def __init__(self, action, *args):
        super().__init__()
        self.action = action
        self.args = args

    def run(self):
        try:
            action = self.action
            args = self.args

            if action == "installed":
                result = installed_wsl()

            elif action == "catalog":
                result = online_catalog()

            elif action == "identify":
                result = identify_family(args[0])

            elif action == "install":
                result = run_command(
                    [
                        "wsl.exe", "--install",
                        "--distribution", args[0],
                        "--no-launch"
                    ],
                    1800
                )

            elif action == "delete":
                result = run_command(
                    ["wsl.exe", "--unregister", args[0]],
                    900
                )

            elif action == "update":
                env = args[0]
                family, _, _ = identify_family(env)

                if family not in MANAGERS:
                    raise RuntimeError(
                        "Famille Linux non prise en charge : " + family
                    )

                command = manager_update(family)

                result = (
                    family,
                    command,
                    wsl_command(env, command, 1800, root=True)
                )

            elif action == "search":
                env, family, query = args

                output, error, code = wsl_command(
                    env,
                    manager_search(family, query),
                    180
                )

                result = (
                    parse_search(family, output),
                    output,
                    error,
                    code
                )

            elif action == "solve":
                env, family, packages = args

                output, error, code = wsl_command(
                    env,
                    simulation_command(family, packages),
                    360
                )

                result = (
                    parse_simulation(family, output, packages),
                    output,
                    error,
                    code
                )

            elif action == "build":
                result = build_iso(*args)

            else:
                raise RuntimeError(
                    "Action inconnue : " + action
                )

            self.completed.emit(result, "")

        except Exception as exc:
            self.completed.emit(None, str(exc))


# ============================================================
# INTERFACE
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.12"
        )
        self.resize(1380, 900)

        self.installed = []
        self.catalog_entries = []
        self.associations = {
            family: "" for family in FAMILIES
        }

        self.applications = set()
        self.solution = {}
        self.report = ""
        self.analysis_valid = False
        self.worker = None
        self.revision = 0

        central = QWidget()
        self.setCentralWidget(central)

        main = QVBoxLayout(central)

        header = QHBoxLayout()

        title = QLabel(
            "Universal Linux Builder  |  v1.12"
        )
        title.setStyleSheet(
            "font-size:22px;font-weight:bold"
        )

        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems(["Sombre", "Clair"])
        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        header.addWidget(self.theme)
        main.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        main.addWidget(self.tabs)

        self.create_distribution_tab()
        self.create_system_tab()
        self.create_apps_tab()
        self.create_project_tab()
        self.create_wsl_tab()

        self.status = QLabel("Prêt")
        main.addWidget(self.status)

        self.apply_theme()
        self.change_family()

    def apply_theme(self, *_):
        self.setStyleSheet(
            STYLE_DARK
            if self.theme.currentText() == "Sombre"
            else STYLE_LIGHT
        )

    def new_tab(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.tabs.addTab(widget, name)
        return layout

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def button(self, label, callback):
        widget = QPushButton(label)
        widget.clicked.connect(callback)
        return widget

    def table(self, headers):
        widget = QTableWidget(0, len(headers))
        widget.setHorizontalHeaderLabels(headers)

        widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        widget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        widget.setAlternatingRowColors(True)
        widget.setShowGrid(False)
        widget.setWordWrap(False)

        widget.verticalHeader().setVisible(False)
        widget.verticalHeader().setDefaultSectionSize(31)

        widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        widget.horizontalHeader().setStretchLastSection(True)

        return widget

    def fill_table(self, widget, rows):
        widget.setSortingEnabled(False)
        widget.setRowCount(0)

        for values in rows:
            row = widget.rowCount()
            widget.insertRow(row)

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column == 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignVCenter |
                        Qt.AlignmentFlag.AlignLeft
                    )

                widget.setItem(row, column, item)

        widget.setSortingEnabled(True)

    def selected_name(self, widget):
        row = widget.currentRow()

        if row < 0:
            return ""

        item = widget.item(row, 0)
        return item.text() if item else ""

    def warn(self, text):
        QMessageBox.warning(self, "Universal Linux Builder", text)

    def info(self, text):
        QMessageBox.information(self, "Universal Linux Builder", text)

    def job(self, action, args, callback):
        if self.worker is not None:
            self.warn("Une opération WSL est déjà en cours.")
            return

        worker = Worker(action, *args)
        self.worker = worker

        self.status.setText(
            "Opération en cours : " + action
        )

        worker.completed.connect(callback)
        worker.finished.connect(
            lambda w=worker: self.job_finished(w)
        )

        worker.start()

    def job_finished(self, worker):
        if self.worker is worker:
            self.worker = None

        worker.deleteLater()
        self.status.setText("Prêt")

    def invalidate(self, *_):
        self.revision += 1
        self.analysis_valid = False

    def family(self):
        return self.family_combo.currentText()

    def project_env(self):
        return self.associations.get(
            self.family(), ""
        )

    # ========================================================
    # DISTRIBUTION
    # ========================================================

    def create_distribution_tab(self):
        layout = self.new_tab("Distribution")

        form = QFormLayout()

        self.family_combo = self.combo(FAMILIES)
        self.release_combo = self.combo([])

        form.addRow("Distribution", self.family_combo)
        form.addRow("Version cible", self.release_combo)

        layout.addLayout(form)

        note = QLabel(
            "Chaque famille utilise son propre gestionnaire "
            "de paquets. L'environnement WSL du projet doit "
            "correspondre à la distribution cible."
        )
        note.setWordWrap(True)

        layout.addWidget(note)
        layout.addStretch()

        self.family_combo.currentTextChanged.connect(
            self.change_family
        )
        self.release_combo.currentTextChanged.connect(
            self.invalidate
        )

    # ========================================================
    # SYSTEME
    # ========================================================

    def create_system_tab(self):
        layout = self.new_tab("Système")
        form = QFormLayout()

        self.desktop = self.combo(["Aucun"])
        self.kernel = self.combo(["Stable", "LTS", "Hardened"])
        self.init = self.combo([])
        self.display = self.combo(["Wayland", "X11", "Aucun"])
        self.audio = self.combo([
            "PipeWire", "PulseAudio", "ALSA", "Aucun"
        ])
        self.boot = self.combo(["GRUB", "Aucun"])
        self.bootmode = self.combo(["UEFI", "BIOS"])

        for label, widget in [
            ("Bureau", self.desktop),
            ("Noyau", self.kernel),
            ("Initialisation", self.init),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Bootloader", self.boot),
            ("Démarrage", self.bootmode)
        ]:
            form.addRow(label, widget)
            widget.currentTextChanged.connect(
                self.invalidate
            )

        layout.addLayout(form)

        self.options = {}

        for name, default in [
            ("Wi-Fi", True),
            ("Bluetooth", True),
            ("Impression", False),
            ("Firmware", True)
        ]:
            checkbox = QCheckBox(name)
            checkbox.setChecked(default)
            checkbox.toggled.connect(self.invalidate)

            self.options[name] = checkbox
            layout.addWidget(checkbox)

        layout.addWidget(
            self.button(
                "Analyser les dépendances",
                self.analyze
            )
        )

        layout.addStretch()

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def create_apps_tab(self):
        layout = self.new_tab("Applications")

        row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Rechercher Firefox, VLC, GIMP..."
        )
        self.search_input.returnPressed.connect(
            self.search_apps
        )

        row.addWidget(self.search_input)
        row.addWidget(
            self.button("Rechercher", self.search_apps)
        )
        row.addWidget(
            self.button(
                "Actualiser les dépôts du projet",
                self.update_project_repos
            )
        )

        layout.addLayout(row)

        layout.addWidget(
            QLabel("Résultats : double-clic pour ajouter")
        )

        self.search_table = self.table([
            "Paquet", "Version", "Description"
        ])
        self.search_table.setColumnWidth(0, 300)
        self.search_table.setColumnWidth(1, 160)

        self.search_table.cellDoubleClicked.connect(
            self.add_search_result
        )

        layout.addWidget(self.search_table, 3)

        layout.addWidget(
            QLabel("Applications choisies : double-clic pour retirer")
        )

        self.selected_table = self.table(["Paquet"])
        self.selected_table.cellDoubleClicked.connect(
            self.remove_application
        )

        layout.addWidget(self.selected_table, 1)

        row = QHBoxLayout()

        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText(
            "Nom exact du paquet"
        )

        row.addWidget(self.manual_input)
        row.addWidget(
            self.button("Ajouter", self.add_manual)
        )

        layout.addLayout(row)

        self.app_log = QTextEdit()
        self.app_log.setReadOnly(True)
        self.app_log.setMaximumHeight(120)

        layout.addWidget(self.app_log)

    # ========================================================
    # PROJET ISO
    # ========================================================

    def create_project_tab(self):
        layout = self.new_tab("Projet / ISO")

        self.summary = QLabel(
            "Aucune analyse effectuée."
        )
        self.summary.setWordWrap(True)

        layout.addWidget(self.summary)

        self.package_table = self.table([
            "Paquet", "Version", "Statut", "Taille"
        ])

        self.package_table.setColumnWidth(0, 330)
        self.package_table.setColumnWidth(1, 220)
        self.package_table.setColumnWidth(2, 220)
        self.package_table.setColumnWidth(3, 150)

        layout.addWidget(self.package_table, 3)

        self.project_log = QTextEdit()
        self.project_log.setReadOnly(True)

        layout.addWidget(self.project_log, 2)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Analyser",
                self.analyze
            )
        )

        row.addWidget(
            self.button(
                "Créer l'ISO",
                self.create_iso
            )
        )

        layout.addLayout(row)

    # ========================================================
    # WSL2 INDEPENDANT
    # ========================================================

    def create_wsl_tab(self):
        layout = self.new_tab("WSL2")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Actualiser les installations",
                self.detect_wsl
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

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QGroupBox("Distributions disponibles")
        left_layout = QVBoxLayout(left)

        self.catalog_table = self.table([
            "Nom WSL", "Description"
        ])
        self.catalog_table.setColumnWidth(0, 220)

        left_layout.addWidget(self.catalog_table)

        left_layout.addWidget(
            self.button(
                "Installer la distribution sélectionnée",
                self.install_wsl
            )
        )

        splitter.addWidget(left)

        right = QGroupBox("Distributions installées")
        right_layout = QVBoxLayout(right)

        self.installed_table = self.table(["Nom WSL"])
        right_layout.addWidget(self.installed_table)

        right_layout.addWidget(
            self.button(
                "Supprimer la distribution sélectionnée",
                self.delete_wsl
            )
        )

        splitter.addWidget(right)
        splitter.setSizes([650, 450])

        layout.addWidget(splitter, 3)

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Distribution WSL à tester :")
        )

        self.wsl_selector = self.combo([])
        row.addWidget(self.wsl_selector, 1)

        row.addWidget(
            self.button(
                "Tester le gestionnaire",
                self.test_wsl
            )
        )

        row.addWidget(
            self.button(
                "Mettre à jour les dépôts",
                self.update_selected_wsl
            )
        )

        layout.addLayout(row)

        group = QGroupBox(
            "Association des environnements au projet ISO"
        )
        form = QFormLayout(group)

        self.mapping = {}

        for family in FAMILIES:
            combo = self.combo(["— Non associé —"])

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.associate(f, value)
            )

            form.addRow(family, combo)
            self.mapping[family] = combo

        layout.addWidget(group)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setMaximumHeight(170)

        layout.addWidget(self.wsl_log)

        self.wsl_log.setPlainText(
            "WSL2 fonctionne indépendamment du projet ISO.\n"
            "Sélectionne n'importe quelle distribution installée "
            "pour tester son gestionnaire ou actualiser ses dépôts."
        )

    # ========================================================
    # CHANGEMENT DE DISTRIBUTION
    # ========================================================

    def change_family(self, *_):
        family = self.family()

        self.release_combo.blockSignals(True)
        self.release_combo.clear()
        self.release_combo.addItems(RELEASES[family])
        self.release_combo.blockSignals(False)

        self.desktop.blockSignals(True)
        self.desktop.clear()
        self.desktop.addItems(
            ["Aucun"] + list(DESKTOPS[family])
        )
        self.desktop.blockSignals(False)

        self.init.blockSignals(True)
        self.init.clear()

        if family == "Gentoo":
            self.init.addItems(["OpenRC", "systemd"])
        elif family == "Slackware":
            self.init.addItems(["SysVinit"])
        else:
            self.init.addItems(["systemd"])

        self.init.blockSignals(False)

        self.kernel.setEnabled(
            family == "Arch Linux"
        )
        self.kernel.setCurrentText("Stable")

        self.applications.clear()
        self.refresh_selected()
        self.invalidate()

    def associate(self, family, value):
        self.associations[family] = (
            "" if value == "— Non associé —" else value
        )
        self.invalidate()

    # ========================================================
    # GESTION WSL
    # ========================================================

    def detect_wsl(self):
        self.job(
            "installed",
            (),
            self.detect_done
        )

    def detect_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        self.installed = data

        self.fill_table(
            self.installed_table,
            [(name,) for name in data]
        )

        self.wsl_selector.clear()
        self.wsl_selector.addItems(data)

        for family, combo in self.mapping.items():
            previous = self.associations[family]

            combo.blockSignals(True)
            combo.clear()
            combo.addItems(["— Non associé —"] + data)

            if previous in data:
                combo.setCurrentText(previous)
            else:
                self.associations[family] = ""

            combo.blockSignals(False)

        self.wsl_log.setPlainText(
            "Distributions installées :\n"
            + ("\n".join(data) if data else "Aucune")
        )

    def load_catalog(self):
        self.job(
            "catalog",
            (),
            self.catalog_done
        )

    def catalog_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        entries, raw = data
        self.catalog_entries = entries

        self.fill_table(
            self.catalog_table,
            entries
        )

        self.wsl_log.setPlainText(
            f"{len(entries)} distributions reconnues.\n\n"
            + (
                "Sélectionne une distribution pour l'installer."
                if entries else raw
            )
        )

    def install_wsl(self):
        name = self.selected_name(
            self.catalog_table
        )

        if not name:
            self.warn(
                "Sélectionne une distribution dans le catalogue."
            )
            return

        if name in self.installed:
            self.warn("Cette distribution est déjà installée.")
            return

        if QMessageBox.question(
            self,
            "Installer WSL",
            f"Installer {name} ?\n"
            "Un téléchargement et une initialisation "
            "peuvent être nécessaires."
        ) != QMessageBox.StandardButton.Yes:
            return

        self.job(
            "install",
            (name,),
            self.install_done
        )

    def install_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        self.wsl_log.setPlainText(
            "Installation demandée.\n"
            + str(data)
            + "\nActualise ensuite les installations."
        )

    def delete_wsl(self):
        name = self.selected_name(
            self.installed_table
        )

        if not name:
            self.warn(
                "Sélectionne une distribution installée."
            )
            return

        confirmation, ok = QInputDialog.getText(
            self,
            "Suppression définitive",
            f"ATTENTION : tous les fichiers Linux de "
            f"{name} seront supprimés.\n\n"
            f"Saisis exactement : {name}"
        )

        if not ok or confirmation != name:
            return

        if QMessageBox.question(
            self,
            "Dernière confirmation",
            f"Supprimer définitivement {name} ?"
        ) != QMessageBox.StandardButton.Yes:
            return

        self.job(
            "delete",
            (name,),
            self.delete_done
        )

    def delete_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        self.wsl_log.setPlainText(
            "Suppression terminée.\n" + str(data)
        )
        self.detect_wsl()

    def test_wsl(self):
        env = self.wsl_selector.currentText()

        if not env:
            self.warn("Sélectionne une distribution WSL.")
            return

        self.job(
            "identify",
            (env,),
            lambda data, error:
                self.test_done(env, data, error)
        )

    def test_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        family, info, output = data

        self.wsl_log.setPlainText(
            "Distribution WSL : " + env + "\n"
            "Famille détectée : " + family + "\n"
            "Version : " + info.get("VERSION_ID", "?")
            + "\n\n"
            + output
        )

    def update_selected_wsl(self):
        env = self.wsl_selector.currentText()

        if not env:
            self.warn("Sélectionne une distribution WSL.")
            return

        if QMessageBox.question(
            self,
            "Actualisation des dépôts",
            f"Distribution sélectionnée : {env}\n\n"
            "Le gestionnaire sera détecté automatiquement.\n"
            "La commande sera exécutée en root.\n\n"
            "Continuer ?"
        ) != QMessageBox.StandardButton.Yes:
            return

        self.job(
            "update",
            (env,),
            lambda data, error:
                self.update_done(env, data, error)
        )

    def update_project_repos(self):
        env = self.project_env()

        if not env:
            self.warn(
                "Associe d'abord un environnement WSL au projet."
            )
            return

        if QMessageBox.question(
            self,
            "Actualiser les dépôts du projet",
            f"Actualiser les dépôts de {env} ?"
        ) != QMessageBox.StandardButton.Yes:
            return

        self.job(
            "update",
            (env,),
            lambda data, error:
                self.update_done(env, data, error)
        )

    def update_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(
                "Erreur : " + error
            )
            return

        family, command, result = data
        output, stderr, code = result

        report = (
            f"WSL : {env}\n"
            f"Famille : {family}\n"
            f"Commande : {command}\n"
            f"Code retour : {code}\n\n"
            + output + "\n" + stderr
        )

        self.wsl_log.setPlainText(report)
        self.app_log.setPlainText(report[-4000:])

        if code:
            self.warn(
                "Échec de l'actualisation.\n"
                "Consulte le journal WSL2."
            )
        else:
            self.info(
                f"Dépôts actualisés : {env}\n"
                f"Gestionnaire : {family}"
            )

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def refresh_selected(self):
        self.fill_table(
            self.selected_table,
            [(name,) for name in sorted(self.applications)]
        )

    def add_manual(self):
        name = self.manual_input.text().strip()

        if not SAFE_PACKAGE.fullmatch(name):
            self.warn("Nom de paquet invalide.")
            return

        self.applications.add(name)
        self.manual_input.clear()
        self.refresh_selected()
        self.invalidate()

    def add_search_result(self, row, _):
        item = self.search_table.item(row, 0)

        if item:
            self.applications.add(item.text())
            self.refresh_selected()
            self.invalidate()

    def remove_application(self, row, _):
        item = self.selected_table.item(row, 0)

        if item:
            self.applications.discard(item.text())
            self.refresh_selected()
            self.invalidate()

    def search_apps(self):
        env = self.project_env()
        family = self.family()
        query = self.search_input.text().strip()

        if not env:
            self.warn(
                "Associe une distribution WSL au projet."
            )
            self.tabs.setCurrentIndex(4)
            return

        if not query or len(query) > 70:
            self.warn("Recherche invalide.")
            return

        revision = self.revision

        self.app_log.setPlainText(
            f"Recherche dans {env}..."
        )

        self.job(
            "search",
            (env, family, query),
            lambda data, error:
                self.search_done(data, error, revision)
        )

    def search_done(self, data, error, revision):
        if revision != self.revision:
            return

        if error:
            self.app_log.setPlainText(error)
            return

        rows, output, stderr, code = data

        self.fill_table(self.search_table, rows)

        self.app_log.setPlainText(
            f"{len(rows)} résultats reconnus.\n"
            f"Code : {code}\n\n"
            + (
                stderr or output[:2500]
                if not rows or code
                else "Double-clique sur un paquet pour l'ajouter."
            )
        )

    # ========================================================
    # PAQUETS DU PROJET
    # ========================================================

    def packages(self):
        family = self.family()

        result = set(BASE[family])

        result.update(
            DESKTOPS[family].get(
                self.desktop.currentText(), []
            )
        )

        result.update(
            AUDIO[family].get(
                self.audio.currentText(), []
            )
        )

        result.update(self.applications)

        for option, checkbox in self.options.items():
            if checkbox.isChecked():
                result.update(
                    EXTRAS[family].get(option, [])
                )

        if family == "Arch Linux":
            result.discard("linux")

            result.add({
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }[self.kernel.currentText()])

        if family == "Gentoo":
            result.discard("sys-apps/openrc")

            result.add(
                "sys-apps/openrc"
                if self.init.currentText() == "OpenRC"
                else "sys-apps/systemd"
            )

        return sorted(result)

    # ========================================================
    # ANALYSE
    # ========================================================

    def analyze(self):
        env = self.project_env()

        if not env:
            self.warn(
                "Associe une distribution WSL au projet."
            )
            self.tabs.setCurrentIndex(4)
            return

        family = self.family()
        packages = self.packages()
        revision = self.revision

        self.project_log.setPlainText(
            "Simulation des dépendances en cours..."
        )

        self.job(
            "solve",
            (env, family, packages),
            lambda data, error:
                self.analyze_done(
                    family, revision, data, error
                )
        )

    def analyze_done(self, family, revision, data, error):
        if revision != self.revision:
            return

        if error:
            self.project_log.setPlainText(error)
            self.analysis_valid = False
            return

        solution, output, stderr, code = data

        valid, status = evaluate_simulation(
            family, output, stderr, code
        )

        self.solution = solution
        self.analysis_valid = valid

        rows = []

        for name, item in sorted(solution.items()):
            rows.append((
                name,
                item.get("version", "?"),
                item.get("status", "?"),
                human_size(item.get("bytes"))
            ))

        self.fill_table(
            self.package_table,
            rows
        )

        estimate = estimate_size(family, solution)

        self.summary.setText(
            f"{len(solution)} paquets identifiés | "
            f"{status}\n"
            f"Estimation ISO : {estimate}"
        )

        self.report = (
            f"Distribution : {family}\n"
            f"État : {status}\n"
            f"Code retour : {code}\n\n"
            "ATTENTION : simulation indicative.\n"
            "Les paquets déjà présents dans WSL peuvent "
            "ne pas apparaître dans la transaction.\n"
            "L'estimation ISO n'est pas une mesure réelle.\n\n"
            + output + "\n" + stderr
        )

        self.project_log.setPlainText(self.report)

        if not valid:
            self.warn(
                "La simulation n'a pas produit "
                "de résultat exploitable.\n"
                "Consulte le journal."
            )

    # ========================================================
    # CREATION ISO
    # ========================================================

    def create_iso(self):
        family = self.family()

        if family not in ("Debian", "Arch Linux"):
            self.warn(
                "La construction ISO n'est pas encore "
                "activée pour " + family + ".\n\n"
                "Les outils de génération propres à cette "
                "famille doivent encore être intégrés."
            )
            return

        if not self.analysis_valid:
            self.warn(
                "Effectue d'abord une analyse exploitable."
            )
            return

        env = self.project_env()

        if not env:
            self.warn(
                "Aucun environnement WSL associé."
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier vide pour l'ISO"
        )

        if not folder:
            return

        if any(Path(folder).iterdir()):
            self.warn(
                "Le dossier de construction doit être vide."
            )
            return

        tool = (
            "live-build"
            if family == "Debian"
            else "archiso"
        )

        if QMessageBox.question(
            self,
            "Créer l'ISO",
            f"Distribution : {family}\n"
            f"Environnement : {env}\n"
            f"Outil : {tool}\n\n"
            "La construction peut télécharger plusieurs Go "
            "et durer longtemps.\n\n"
            "WSL2 peut ne pas prendre en charge "
            "toutes les opérations nécessaires.\n"
            "La compatibilité Ventoy ne sera pas "
            "automatiquement validée.\n\n"
            "Lancer la construction expérimentale ?"
        ) != QMessageBox.StandardButton.Yes:
            return

        self.project_log.setPlainText(
            "Construction ISO en cours...\n"
            + folder
        )

        self.job(
            "build",
            (
                family,
                env,
                self.release_combo.currentText(),
                self.packages(),
                folder
            ),
            self.build_done
        )

    def build_done(self, data, error):
        if error:
            self.project_log.setPlainText(
                "ÉCHEC DE CONSTRUCTION\n\n" + error
            )
            self.warn(
                "La construction ISO a échoué.\n"
                "Consulte le journal."
            )
            return

        inspections, report = data

        self.project_log.setPlainText(
            "CONSTRUCTION TERMINÉE\n\n"
            + json.dumps(
                inspections,
                ensure_ascii=False,
                indent=2
            )
            + "\n\n"
            "VÉRIFICATION :\n"
            "ISO9660 : inspection statique uniquement.\n"
            "BIOS/UEFI : non testé.\n"
            "Ventoy : non testé.\n\n"
            + report[-12000:]
        )

        self.info(
            "ISO produite.\n\n"
            "Il reste à vérifier son démarrage "
            "en machine virtuelle puis avec Ventoy."
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":
    application = QApplication(sys.argv)
    application.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(application.exec())
