import sys
import os
import re
import json
import shlex
import subprocess
import urllib.request
import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
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
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QGroupBox,
    QHeaderView,
    QSplitter,
    QFrame
)

VERSION = "1.16"

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

COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#51A2DA",
    "Arch Linux": "#1793D1",
    "Gentoo": "#9482C9",
    "Slackware": "#D0D7E2"
}

LOGOS = {
    "Debian": "debian",
    "Fedora": "fedora",
    "Arch Linux": "archlinux",
    "Gentoo": "gentoo",
    "Slackware": "slackware"
}

MANAGERS = {
    "Debian": "apt",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

INSTALLERS = {
    "Debian": "Calamares",
    "Fedora": "Anaconda",
    "Arch Linux": "Calamares",
    "Gentoo": "Installation Gentoo personnalisée",
    "Slackware": "Slackware Setup"
}

# Outils nécessaires dans l'environnement de construction.
# Les paquets sont spécifiques à la distribution WSL.

BUILD_TOOLS = {
    "Debian": [
        ("apt-get", "apt"),
        ("dpkg", "dpkg"),
        ("debootstrap", "debootstrap"),
        ("lb", "live-build"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso"),
        ("grub-mkrescue", "grub-common")
    ],
    "Fedora": [
        ("dnf5", "dnf5"),
        ("rpm", "rpm"),
        ("lorax", "lorax"),
        ("livemedia-creator", "lorax"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso")
    ],
    "Arch Linux": [
        ("pacman", "pacman"),
        ("mkarchiso", "archiso"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "libisoburn"),
        ("grub-mkrescue", "grub")
    ],
    "Gentoo": [
        ("emerge", "sys-apps/portage"),
        ("equery", "app-portage/gentoolkit"),
        ("mksquashfs", "sys-fs/squashfs-tools"),
        ("xorriso", "app-cdr/libisoburn")
    ],
    "Slackware": [
        ("installpkg", "pkgtools"),
        ("slackpkg", "slackpkg"),
        ("mkisofs", "cdrtools"),
        ("mksquashfs", "squashfs-tools")
    ]
}

# Paquets devant être présents dans le Linux installé.
# Leur existence et leur compatibilité doivent être vérifiées
# avec les dépôts de la version choisie.

TARGET_BASE = {
    "Debian": [
        "linux-image-amd64",
        "systemd-sysv",
        "apt",
        "dpkg",
        "ca-certificates",
        "sudo",
        "network-manager",
        "iproute2",
        "openssh-client"
    ],
    "Fedora": [
        "kernel",
        "systemd",
        "dnf5",
        "rpm",
        "fedora-repos",
        "ca-certificates",
        "sudo",
        "NetworkManager",
        "iproute"
    ],
    "Arch Linux": [
        "base",
        "linux",
        "linux-firmware",
        "pacman",
        "archlinux-keyring",
        "sudo",
        "networkmanager",
        "iproute2",
        "ca-certificates"
    ],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
        "sys-apps/portage",
        "sys-apps/sudo",
        "net-misc/networkmanager",
        "app-misc/ca-certificates",
        "sys-apps/iproute2"
    ],
    "Slackware": [
        "kernel-generic",
        "kernel-modules",
        "pkgtools",
        "slackpkg",
        "sudo",
        "networkmanager",
        "ca-certificates"
    ]
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
        "GNOME": ["gnome-shell", "gnome-session", "gdm"],
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

AUDIO = {
    "Debian": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Fedora": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulseaudio"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Arch Linux": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Gentoo": {
        "PipeWire": ["media-video/pipewire"],
        "PulseAudio": ["media-sound/pulseaudio"],
        "ALSA": ["media-sound/alsa-utils"],
        "Aucun": []
    },
    "Slackware": {
        "PipeWire": ["pipewire"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
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

CACHE = Path.home() / ".universal_linux_builder" / "logos"

ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)

DARK = """
QWidget {
    background: #10151D;
    color: #DCE4EF;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow {
    background: #10151D;
}

QLabel {
    background: transparent;
}

QLineEdit,
QComboBox,
QTextEdit,
QTableWidget {
    background: #171F2B;
    color: #E5ECF5;
    border: 1px solid #2C394B;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: #28558A;
}

QPushButton {
    background: #253448;
    color: #E5EDF7;
    border: 1px solid #354A62;
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 22px;
}

QPushButton:hover {
    background: #304761;
    border-color: #52789E;
}

QPushButton:disabled {
    color: #66778A;
    background: #1A2330;
}

QTabWidget::pane {
    border: 1px solid #263447;
    border-top: none;
}

QTabBar::tab {
    background: #151D29;
    color: #AAB8CB;
    padding: 10px 17px;
    border-right: 1px solid #263447;
}

QTabBar::tab:selected {
    background: #1D2A3B;
    color: white;
    border-bottom: 2px solid #5B9DE3;
}

QTableWidget {
    alternate-background-color: #1D2939;
    gridline-color: transparent;
}

QHeaderView::section {
    background: #24344A;
    color: #DCE5F1;
    border: none;
    border-right: 1px solid #34455B;
    padding: 7px;
}

QGroupBox {
    border: 1px solid #2B3A4D;
    border-radius: 6px;
    margin-top: 13px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #9EB8D6;
}

QScrollBar:vertical {
    background: #141D29;
    width: 11px;
}

QScrollBar::handle:vertical {
    background: #3B4E66;
    border-radius: 5px;
}
"""


# ============================================================
# LOGOS
# ============================================================

def logo(family, size=36):
    CACHE.mkdir(parents=True, exist_ok=True)

    identifier = LOGOS[family]
    filename = CACHE / (identifier + ".svg")

    if not filename.exists():
        color = COLORS[family].replace("#", "")

        url = (
            "https://cdn.simpleicons.org/"
            + identifier
            + "/"
            + color
        )

        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "UniversalLinuxBuilder/1.16"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=3
            ) as response:
                data = response.read(200000)

            if b"<svg" in data[:1000]:
                filename.write_bytes(data)

        except Exception:
            pass

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    if filename.exists():
        renderer = QSvgRenderer(str(filename))

        if renderer.isValid():
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )
    painter.setBrush(QColor(COLORS[family]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()

    return pixmap


# ============================================================
# EXECUTION WSL
# ============================================================

def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        result = data.decode("utf-16", "replace")

    elif b"\x00" in data[:100]:
        result = data.decode("utf-16-le", "replace")

    else:
        result = data.decode("utf-8", "replace")

    return ANSI.sub("", result).replace("\x00", "").lstrip("\ufeff")


def run(argv, timeout=300):
    process = subprocess.run(
        argv,
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
        decode(process.stdout),
        decode(process.stderr),
        process.returncode
    )


def wsl(env, command, timeout=300, root=False):
    argv = ["wsl.exe", "-d", env]

    if root:
        argv += ["-u", "root"]

    argv += [
        "--exec",
        "/bin/sh",
        "-lc",
        command
    ]

    return run(argv, timeout)


def installed_wsl():
    output, error, code = run(
        ["wsl.exe", "--list", "--quiet"],
        60
    )

    if code:
        raise RuntimeError(error or output)

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


def online_wsl():
    output, error, code = run(
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


def detect_family(env):
    output, error, code = wsl(
        env,
        "cat /etc/os-release",
        60
    )

    if code:
        raise RuntimeError(error or output)

    metadata = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            metadata[key] = value.strip().strip('"')

    ident = metadata.get("ID", "").lower()

    family = {
        "debian": "Debian",
        "fedora": "Fedora",
        "arch": "Arch Linux",
        "archlinux": "Arch Linux",
        "gentoo": "Gentoo",
        "slackware": "Slackware"
    }.get(ident, "Inconnue")

    return family, metadata


def verify_tools(env):
    family, metadata = detect_family(env)

    if family not in BUILD_TOOLS:
        raise RuntimeError(
            "Famille WSL non prise en charge : " + family
        )

    commands = []

    for executable, package in BUILD_TOOLS[family]:
        commands.append(
            "if command -v "
            + shlex.quote(executable)
            + " >/dev/null 2>&1; then echo "
            + shlex.quote(executable + ":OK")
            + "; else echo "
            + shlex.quote(executable + ":ABSENT")
            + "; fi"
        )

    output, error, code = wsl(
        env,
        "; ".join(commands),
        120
    )

    if code:
        raise RuntimeError(error or output)

    states = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.split(":", 1)
            states[name] = state == "OK"

    rows = []

    for executable, package in BUILD_TOOLS[family]:
        rows.append((
            executable,
            package,
            "Présent" if states.get(executable) else "Absent"
        ))

    return family, metadata, rows


def install_tools(env):
    family, metadata, rows = verify_tools(env)

    missing = sorted({
        package
        for executable, package, state in rows
        if state == "Absent"
    })

    if not missing:
        return family, "Aucun outil manquant", ("", "", 0)

    packages = " ".join(
        shlex.quote(name)
        for name in missing
    )

    if family == "Debian":
        command = (
            "DEBIAN_FRONTEND=noninteractive apt-get update && "
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends "
            + packages
        )

    elif family == "Fedora":
        command = (
            "dnf5 -y install "
            + packages
        )

    elif family == "Arch Linux":
        command = (
            "pacman -Syu --noconfirm --needed "
            + packages
        )

    else:
        raise RuntimeError(
            "Installation automatique des outils non validée "
            "pour cette famille. "
            "Utilise son gestionnaire natif manuellement."
        )

    result = wsl(
        env,
        command,
        3600,
        root=True
    )

    return family, command, result


def update_repositories(env):
    family, metadata = detect_family(env)

    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update"
        ),
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman -Syu --noconfirm",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    if family not in commands:
        raise RuntimeError(
            "Gestionnaire inconnu"
        )

    command = commands[family]

    return family, command, wsl(
        env,
        command,
        3600,
        root=True
    )


def search_packages(env, family, query):
    command = {
        "Debian": "apt-cache search",
        "Fedora": "dnf5 search",
        "Arch Linux": "pacman -Ss",
        "Gentoo": "emerge --search",
        "Slackware": "slackpkg search"
    }[family]

    return wsl(
        env,
        "LC_ALL=C "
        + command
        + " "
        + shlex.quote(query),
        300
    )


def parse_search(family, output):
    rows = []
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
                r"\s*:\s*(.+)$",
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

        if (
            name
            and SAFE_PACKAGE.fullmatch(name)
            and name not in seen
        ):
            seen.add(name)
            rows.append((
                name,
                version,
                description[:180]
            ))

    return rows[:500]


def simulate_packages(env, family, packages):
    arguments = " ".join(
        shlex.quote(name)
        for name in packages
    )

    commands = {
        "Debian": (
            "LC_ALL=C apt-get -s install "
            + arguments
        ),
        "Fedora": (
            "LC_ALL=C dnf5 --assumeno install "
            + arguments
        ),
        "Arch Linux": (
            "LC_ALL=C pacman -Sp "
            '--print-format "%n|%v|%s" '
            + arguments
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend --verbose --tree "
            + arguments
        )
    }

    if family == "Slackware":
        raise RuntimeError(
            "Slackware ne fournit pas de résolution native "
            "complète des dépendances avec slackpkg."
        )

    return wsl(
        env,
        commands[family],
        600
    )


def export_project(data, directory):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)

    json_file = destination / "universal_linux_project.json"
    packages_file = destination / "packages.txt"
    readme_file = destination / "README.txt"

    json_file.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    packages_file.write_text(
        "\n".join(data["packages"]) + "\n",
        encoding="utf-8"
    )

    readme_file.write_text(
        "Universal Linux Builder v1.16\n\n"
        "Distribution : " + data["family"] + "\n"
        "Version : " + data["release"] + "\n"
        "Installateur : " + data["installer"] + "\n"
        "Gestionnaire : " + data["manager"] + "\n\n"
        "Ce projet est un manifeste de préparation.\n"
        "Il ne constitue pas une ISO amorçable.\n\n"
        "Les paquets doivent être vérifiés pour la version "
        "exacte de la distribution.\n"
        "Le gestionnaire de paquets doit rester présent "
        "dans le système installé.\n"
        "L'installateur doit être configuré et testé "
        "séparément.\n",
        encoding="utf-8"
    )

    return str(destination)


# ============================================================
# CONSTRUCTION ISO EXPERIMENTALE
# ============================================================

def build_iso(env, family, release, packages, directory):
    """
    Construction expérimentale Debian / Arch.
    Ne garantit ni Calamares ni le démarrage sur Ventoy.
    """

    if family not in ("Debian", "Arch Linux"):
        raise RuntimeError(
            "Construction ISO non implémentée pour "
            + family
        )

    actual, metadata, rows = verify_tools(env)

    if actual != family:
        raise RuntimeError(
            "Famille WSL incompatible : " + actual
        )

    missing = [
        name
        for name, package, state in rows
        if state == "Absent"
    ]

    if missing:
        raise RuntimeError(
            "Outils manquants : "
            + ", ".join(missing)
        )

    destination = Path(directory)

    if any(destination.iterdir()):
        raise RuntimeError(
            "Le dossier de destination doit être vide."
        )

    identifier = datetime.datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )

    workspace = "/var/tmp/ulb-" + identifier
    quoted_workspace = shlex.quote(workspace)

    package_arguments = " ".join(
        shlex.quote(name)
        for name in packages
    )

    if family == "Debian":
        script = (
            "set -eu; "
            "mkdir -p " + quoted_workspace + "; "
            "cd " + quoted_workspace + "; "
            "lb config "
            "--distribution " + shlex.quote(release) + " "
            "--architectures amd64 "
            "--binary-images iso-hybrid; "
            "mkdir -p config/package-lists; "
            'printf "%s\\n" '
            + package_arguments
            + " > config/package-lists/ulb.list.chroot; "
            "lb build"
        )

    else:
        profile = "/usr/share/archiso/configs/releng"

        script = (
            "set -eu; "
            "test -f "
            + shlex.quote(profile + "/profiledef.sh")
            + "; "
            "mkdir -p " + quoted_workspace + "; "
            "cp -a "
            + shlex.quote(profile)
            + " "
            + quoted_workspace
            + "/profile; "
            "cd " + quoted_workspace + "; "
            'printf "%s\\n" '
            + package_arguments
            + " >> profile/packages.x86_64; "
            "sort -u profile/packages.x86_64 "
            "-o profile/packages.x86_64; "
            "mkdir -p out work; "
            "mkarchiso -v -w work -o out profile"
        )

    output, error, code = wsl(
        env,
        script,
        7200,
        root=True
    )

    report = (
        "Universal Linux Builder v1.16\n"
        "Distribution : " + family + "\n"
        "WSL : " + env + "\n"
        "Workspace : " + workspace + "\n"
        "Code retour : " + str(code) + "\n\n"
        + output + "\n" + error
    )

    (destination / "build_report.txt").write_text(
        report,
        encoding="utf-8"
    )

    if code:
        raise RuntimeError(
            "Construction échouée.\n"
            + (error or output)[-1800:]
        )

    paths, error, code = wsl(
        env,
        "find "
        + quoted_workspace
        + ' -type f -name "*.iso" -print',
        120,
        root=True
    )

    if code or not paths.strip():
        raise RuntimeError(
            "La construction n'a produit aucune ISO."
        )

    files = []

    for index, source in enumerate(
        paths.splitlines(),
        1
    ):
        target = destination / (
            "ULB_"
            + family.replace(" ", "_")
            + "_"
            + str(index)
            + ".iso"
        )

        with target.open("wb") as handle:
            process = subprocess.run(
                [
                    "wsl.exe",
                    "-d", env,
                    "-u", "root",
                    "--exec", "cat", source
                ],
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.PIPE,
                timeout=1800,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0
                )
            )

        if process.returncode:
            raise RuntimeError(
                "Copie ISO échouée : "
                + decode(process.stderr)
            )

        with target.open("rb") as handle:
            handle.seek(32768)
            signature = handle.read(7)

        iso9660 = (
            len(signature) >= 6
            and signature[1:6] == b"CD001"
        )

        files.append({
            "file": str(target),
            "bytes": target.stat().st_size,
            "iso9660": iso9660,
            "boot_tested": False,
            "installer_tested": False,
            "ventoy_tested": False
        })

    return files, report


# ============================================================
# THREAD
# ============================================================

class Worker(QThread):
    done = Signal(object, str)

    def __init__(self, action, *args):
        super().__init__()
        self.action = action
        self.args = args

    def run(self):
        try:
            functions = {
                "installed": installed_wsl,
                "online": online_wsl,
                "detect": detect_family,
                "tools": verify_tools,
                "install_tools": install_tools,
                "update": update_repositories,
                "search": search_packages,
                "simulate": simulate_packages,
                "build": build_iso
            }

            if self.action in functions:
                result = functions[self.action](*self.args)

            elif self.action == "install_wsl":
                result = run(
                    [
                        "wsl.exe",
                        "--install",
                        "--distribution",
                        self.args[0],
                        "--no-launch"
                    ],
                    1800
                )

            elif self.action == "remove_wsl":
                result = run(
                    [
                        "wsl.exe",
                        "--unregister",
                        self.args[0]
                    ],
                    900
                )

            else:
                raise RuntimeError(
                    "Action inconnue : " + self.action
                )

            self.done.emit(result, "")

        except Exception as exc:
            self.done.emit(None, str(exc))


# ============================================================
# INTERFACE
# ============================================================

class UniversalLinuxBuilder(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.16"
        )
        self.resize(1400, 900)

        self.family_name = "Debian"
        self.installed = []
        self.online = []
        self.associations = {
            family: ""
            for family in FAMILIES
        }

        self.selected_packages = set()
        self.cards = {}
        self.banners = []
        self.worker = None

        self.analysis_ok = False
        self.tools_ok = False
        self.revision = 0

        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(16, 12, 16, 10)
        main.setSpacing(10)

        header = QHBoxLayout()

        self.header_logo = QLabel()
        self.header_logo.setFixedSize(48, 48)
        header.addWidget(self.header_logo)

        titles = QVBoxLayout()

        title = QLabel("Universal Linux Builder")
        title.setStyleSheet(
            "font-size:20px;font-weight:600;color:#F0F5FC;"
        )

        titles.addWidget(title)

        self.subtitle = QLabel()
        self.subtitle.setStyleSheet(
            "color:#8FA9C8;font-size:12px;"
        )
        titles.addWidget(self.subtitle)

        header.addLayout(titles)
        header.addStretch()

        version = QLabel("v1.16")
        version.setStyleSheet("color:#7892AF;")
        header.addWidget(version)

        main.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        main.addWidget(line)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_applications()
        self.make_verification()
        self.make_iso()
        self.make_wsl()

        self.status = QLabel("Prêt")
        self.status.setStyleSheet("color:#7892AF;")
        main.addWidget(self.status)

        self.setStyleSheet(DARK)

        self.change_family("Debian")
        self.refresh_wsl()

    # --------------------------------------------------------
    # OUTILS GRAPHIQUES
    # --------------------------------------------------------

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs.addTab(widget, name)

        return layout

    def button(self, text, callback):
        widget = QPushButton(text)
        widget.clicked.connect(callback)
        return widget

    def combo(self, values=()):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def table(self, headers):
        widget = QTableWidget(0, len(headers))
        widget.setHorizontalHeaderLabels(headers)
        widget.setAlternatingRowColors(True)
        widget.setShowGrid(False)
        widget.verticalHeader().hide()
        widget.verticalHeader().setDefaultSectionSize(29)

        widget.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        widget.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        widget.horizontalHeader().setStretchLastSection(True)

        return widget

    def fill(self, table, rows):
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                table.setItem(
                    i,
                    j,
                    QTableWidgetItem(str(value))
                )

        table.setSortingEnabled(True)

    def selected(self, table):
        row = table.currentRow()

        if row < 0:
            return ""

        item = table.item(row, 0)
        return item.text() if item else ""

    def warning(self, message):
        QMessageBox.warning(
            self,
            "Universal Linux Builder",
            message
        )

    def information(self, message):
        QMessageBox.information(
            self,
            "Universal Linux Builder",
            message
        )

    def confirm(self, message):
        return QMessageBox.question(
            self,
            "Confirmation",
            message
        ) == QMessageBox.StandardButton.Yes

    def job(self, action, args, callback):
        if self.worker is not None:
            self.warning(
                "Une opération est déjà en cours."
            )
            return

        worker = Worker(action, *args)
        self.worker = worker

        self.status.setText(
            "Opération en cours : " + action
        )

        worker.done.connect(callback)

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
        self.analysis_ok = False
        self.tools_ok = False

    def banner(self, layout):
        row = QHBoxLayout()

        image = QLabel()
        image.setFixedSize(26, 26)

        text = QLabel()
        text.setStyleSheet(
            "font-size:13px;font-weight:600;color:#C9D8EA;"
        )

        row.addWidget(image)
        row.addWidget(text)
        row.addStretch()

        layout.addLayout(row)
        self.banners.append((image, text))

    def update_header(self):
        family = self.family_name
        release = self.release.currentText()

        self.header_logo.setPixmap(
            logo(family, 44)
        )

        self.subtitle.setText(
            family
            + "  •  "
            + release
            + "  |  "
            + INSTALLERS[family]
            + "  |  "
            + MANAGERS[family]
        )

        for image, text in self.banners:
            image.setPixmap(logo(family, 24))
            text.setText(
                family + " / " + release
            )

        for name, button in self.cards.items():
            if name == family:
                button.setStyleSheet(
                    "QPushButton{"
                    "background:#20354C;"
                    "border:1px solid #5796D5;"
                    "border-radius:7px;"
                    "padding:8px;"
                    "font-weight:600;"
                    "color:white;"
                    "}"
                )
            else:
                button.setStyleSheet(
                    "QPushButton{"
                    "background:#192431;"
                    "border:1px solid #2C3A4D;"
                    "border-radius:7px;"
                    "padding:8px;"
                    "color:#B8C8DB;"
                    "}"
                    "QPushButton:hover{"
                    "background:#24364B;"
                    "}"
                )

    def next_button(self, layout, index):
        row = QHBoxLayout()
        row.addStretch()

        button = self.button(
            "Continuer",
            lambda: self.tabs.setCurrentIndex(index)
        )

        button.setFixedWidth(125)
        row.addWidget(button)

        layout.addLayout(row)

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):
        layout = self.page("Distribution")

        title = QLabel("Choisir une distribution")
        title.setStyleSheet(
            "font-size:16px;font-weight:600;"
        )
        layout.addWidget(title)

        cards = QHBoxLayout()
        cards.setSpacing(9)

        for family in FAMILIES:
            button = QPushButton(family)
            button.setIcon(QIcon(logo(family, 32)))
            button.setIconSize(QSize(32, 32))
            button.setFixedHeight(64)

            button.clicked.connect(
                lambda checked=False, f=family:
                    self.change_family(f)
            )

            cards.addWidget(button)
            self.cards[family] = button

        layout.addLayout(cards)

        form = QFormLayout()

        self.release = self.combo()
        self.release.setMaximumWidth(320)

        form.addRow("Version", self.release)

        layout.addLayout(form)

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        group = QGroupBox("Composants natifs")
        group_layout = QFormLayout(group)

        self.installer_label = QLabel()
        self.manager_label = QLabel()

        group_layout.addRow(
            "Installateur",
            self.installer_label
        )

        group_layout.addRow(
            "Gestionnaire de paquets",
            self.manager_label
        )

        layout.addWidget(group)

        self.distribution_note = QLabel()
        self.distribution_note.setWordWrap(True)
        self.distribution_note.setStyleSheet(
            "color:#8FA4BF;"
        )

        layout.addWidget(self.distribution_note)

        layout.addStretch()
        self.next_button(layout, 1)

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def make_system(self):
        layout = self.page("Système")
        self.banner(layout)

        form = QFormLayout()

        self.desktop = self.combo()
        self.kernel = self.combo([
            "Stable",
            "LTS",
            "Hardened"
        ])

        self.init = self.combo()

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

        self.boot_mode = self.combo([
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
            ("Amorçage", self.boot_mode)
        ]

        for label, widget in fields:
            widget.setMaximumWidth(400)
            form.addRow(label, widget)

            widget.currentTextChanged.connect(
                self.invalidate
            )

        layout.addLayout(form)

        self.flags = {}

        for name, enabled in [
            ("Wi-Fi", True),
            ("Bluetooth", True),
            ("Impression", False),
            ("Firmware", True)
        ]:
            checkbox = QCheckBox(name)
            checkbox.setChecked(enabled)
            checkbox.toggled.connect(
                self.invalidate
            )

            self.flags[name] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()
        self.next_button(layout, 2)

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def make_applications(self):
        layout = self.page("Applications")
        self.banner(layout)

        row = QHBoxLayout()

        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText(
            "Rechercher : firefox, vlc, gimp..."
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
            "Version",
            "Description"
        ])

        self.search_results.setColumnWidth(0, 270)
        self.search_results.setColumnWidth(1, 150)

        self.search_results.cellDoubleClicked.connect(
            self.add_search_result
        )

        layout.addWidget(
            self.search_results,
            3
        )

        layout.addWidget(
            QLabel("Applications ajoutées")
        )

        self.apps_table = self.table(["Paquet"])

        self.apps_table.cellDoubleClicked.connect(
            self.remove_application
        )

        layout.addWidget(
            self.apps_table,
            1
        )

        row = QHBoxLayout()

        self.manual_package = QLineEdit()
        self.manual_package.setPlaceholderText(
            "Nom exact du paquet"
        )

        row.addWidget(self.manual_package)

        row.addWidget(
            self.button(
                "Ajouter",
                self.add_manual_application
            )
        )

        layout.addLayout(row)

        self.apps_log = QTextEdit()
        self.apps_log.setReadOnly(True)
        self.apps_log.setMaximumHeight(110)

        layout.addWidget(self.apps_log)

        self.next_button(layout, 3)

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def make_verification(self):
        layout = self.page("Vérification")
        self.banner(layout)

        self.verification_status = QLabel(
            "Vérifications non effectuées"
        )

        layout.addWidget(self.verification_status)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Vérifier les outils ISO",
                self.verify_project
            )
        )

        row.addWidget(
            self.button(
                "Analyser les paquets",
                self.analyze_packages
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.checks_table = self.table([
            "Composant",
            "Paquet",
            "État"
        ])

        self.checks_table.setColumnWidth(0, 270)
        self.checks_table.setColumnWidth(1, 270)

        layout.addWidget(
            self.checks_table,
            2
        )

        self.packages_table = self.table([
            "Paquet cible",
            "Origine"
        ])

        self.packages_table.setColumnWidth(0, 360)

        layout.addWidget(
            self.packages_table,
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

    def make_iso(self):
        layout = self.page("ISO")
        self.banner(layout)

        self.iso_status = QLabel()
        self.iso_status.setWordWrap(True)
        layout.addWidget(self.iso_status)

        self.iso_note = QLabel(
            "La vérification d'une signature ISO9660 "
            "ne constitue pas un test de démarrage.\n"
            "Une ISO doit être testée en machine virtuelle, "
            "puis avec Ventoy et son installateur."
        )

        self.iso_note.setWordWrap(True)
        self.iso_note.setStyleSheet(
            "color:#8FA4BF;"
        )

        layout.addWidget(self.iso_note)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Exporter le projet",
                self.export_current_project
            )
        )

        self.build_button = self.button(
            "Créer l'ISO expérimentale",
            self.create_iso
        )

        row.addWidget(self.build_button)
        row.addStretch()

        layout.addLayout(row)

        self.iso_log = QTextEdit()
        self.iso_log.setReadOnly(True)

        layout.addWidget(self.iso_log)

    # --------------------------------------------------------
    # WSL2
    # --------------------------------------------------------

    def make_wsl(self):
        layout = self.page("WSL2")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Actualiser les WSL",
                self.refresh_wsl
            )
        )

        row.addWidget(
            self.button(
                "Catalogue disponible",
                self.refresh_catalog
            )
        )

        row.addStretch()
        layout.addLayout(row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QGroupBox("Distributions disponibles")
        left_layout = QVBoxLayout(left)

        self.catalog_table = self.table([
            "Distribution",
            "Description"
        ])

        self.catalog_table.setColumnWidth(0, 190)
        left_layout.addWidget(self.catalog_table)

        left_layout.addWidget(
            self.button(
                "Installer dans WSL2",
                self.install_wsl
            )
        )

        splitter.addWidget(left)

        right = QGroupBox("Distributions installées")
        right_layout = QVBoxLayout(right)

        self.installed_table = self.table([
            "Nom WSL"
        ])

        right_layout.addWidget(
            self.installed_table
        )

        right_layout.addWidget(
            self.button(
                "Supprimer la distribution",
                self.remove_wsl
            )
        )

        splitter.addWidget(right)
        splitter.setSizes([680, 440])

        layout.addWidget(splitter, 2)

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Environnement WSL à gérer")
        )

        self.wsl_choice = self.combo()
        row.addWidget(self.wsl_choice, 1)

        row.addWidget(
            self.button(
                "Identifier",
                self.identify_wsl
            )
        )

        row.addWidget(
            self.button(
                "Vérifier les outils",
                self.check_wsl_tools
            )
        )

        row.addWidget(
            self.button(
                "Installer les outils",
                self.install_wsl_tools
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_selected_wsl
            )
        )

        layout.addLayout(row)

        self.wsl_tools_table = self.table([
            "Exécutable",
            "Paquet",
            "État"
        ])

        self.wsl_tools_table.setColumnWidth(0, 190)
        self.wsl_tools_table.setColumnWidth(1, 260)

        layout.addWidget(
            self.wsl_tools_table,
            1
        )

        group = QGroupBox(
            "Association WSL aux distributions du projet"
        )

        form = QFormLayout(group)

        self.mapping_boxes = {}

        for family in FAMILIES:
            combo = self.combo([
                "— Non associé —"
            ])

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.associate_wsl(f, value)
            )

            self.mapping_boxes[family] = combo

            form.addRow(
                family,
                combo
            )

        layout.addWidget(group)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setMaximumHeight(155)

        layout.addWidget(self.wsl_log)

    # --------------------------------------------------------
    # SELECTION DISTRIBUTION
    # --------------------------------------------------------

    def change_family(self, family):
        self.family_name = family

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(RELEASES[family])
        self.release.blockSignals(False)

        self.desktop.blockSignals(True)
        self.desktop.clear()
        self.desktop.addItems(DESKTOPS[family].keys())
        self.desktop.blockSignals(False)

        self.init.blockSignals(True)
        self.init.clear()

        if family == "Gentoo":
            self.init.addItems([
                "OpenRC",
                "systemd"
            ])

        elif family == "Slackware":
            self.init.addItem("SysVinit")

        else:
            self.init.addItem("systemd")

        self.init.blockSignals(False)

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

        self.distribution_note.setText(
            "Le gestionnaire de paquets natif et les dépôts "
            "devront rester fonctionnels après l'installation.\n"
            "WSL2 sert uniquement à préparer le projet."
        )

        supported = family in (
            "Debian",
            "Arch Linux"
        )

        self.build_button.setEnabled(supported)

        if supported:
            self.iso_status.setText(
                "Construction expérimentale disponible pour "
                + family
                + ". L'installation sur disque et le démarrage "
                "ne sont pas encore validés."
            )
        else:
            self.iso_status.setText(
                "Construction ISO non implémentée pour "
                + family
                + ". Tu peux vérifier les outils et exporter "
                "le projet."
            )

        self.selected_packages.clear()
        self.refresh_selected_apps()

        self.invalidate()
        self.update_header()
        self.refresh_target_packages()

    def release_changed(self, *_):
        self.invalidate()
        self.update_header()

    def associate_wsl(self, family, value):
        self.associations[family] = (
            ""
            if value == "— Non associé —"
            else value
        )

        self.invalidate()

    # --------------------------------------------------------
    # WSL : INVENTAIRE
    # --------------------------------------------------------

    def refresh_wsl(self):
        self.job(
            "installed",
            (),
            self.wsl_loaded
        )

    def wsl_loaded(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        self.installed = data

        self.fill(
            self.installed_table,
            [(name,) for name in data]
        )

        old = self.wsl_choice.currentText()

        self.wsl_choice.clear()
        self.wsl_choice.addItems(data)

        if old in data:
            self.wsl_choice.setCurrentText(old)

        for family, combo in self.mapping_boxes.items():
            previous = self.associations[family]

            combo.blockSignals(True)
            combo.clear()
            combo.addItems(
                ["— Non associé —"] + data
            )

            if previous in data:
                combo.setCurrentText(previous)
            else:
                self.associations[family] = ""

            combo.blockSignals(False)

        self.wsl_log.setPlainText(
            "Environnements installés :\n"
            + ("\n".join(data) or "Aucun")
        )

    def refresh_catalog(self):
        self.job(
            "online",
            (),
            self.catalog_loaded
        )

    def catalog_loaded(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        rows, raw = data
        self.online = rows

        self.fill(
            self.catalog_table,
            rows
        )

        self.wsl_log.setPlainText(
            str(len(rows))
            + " distributions trouvées.\n"
            + (raw[:1000] if not rows else "")
        )

    def install_wsl(self):
        name = self.selected(
            self.catalog_table
        )

        valid = [
            row[0]
            for row in self.online
        ]

        if name not in valid:
            self.warning(
                "Sélectionne une distribution du catalogue."
            )
            return

        if name in self.installed:
            self.warning("Déjà installée.")
            return

        if self.confirm(
            "Installer " + name + " dans WSL2 ?"
        ):
            self.job(
                "install_wsl",
                (name,),
                lambda data, error:
                    self.wsl_operation_done(
                        "Installation",
                        data,
                        error
                    )
            )

    def remove_wsl(self):
        name = self.selected(
            self.installed_table
        )

        if not name:
            self.warning(
                "Sélectionne une distribution."
            )
            return

        typed, ok = QInputDialog.getText(
            self,
            "Suppression WSL",
            "Toutes les données de "
            + name
            + " seront supprimées.\n"
            "Saisis exactement : " + name
        )

        if (
            ok
            and typed == name
            and self.confirm(
                "Supprimer définitivement "
                + name + " ?"
            )
        ):
            self.job(
                "remove_wsl",
                (name,),
                lambda data, error:
                    self.wsl_operation_done(
                        "Suppression",
                        data,
                        error
                    )
            )

    def wsl_operation_done(self, title, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        output, stderr, code = data

        self.wsl_log.setPlainText(
            title
            + " : code "
            + str(code)
            + "\n"
            + output
            + "\n"
            + stderr
        )

        if code:
            self.warning(title + " échouée.")
        else:
            self.refresh_wsl()

    def selected_wsl(self):
        env = self.wsl_choice.currentText()

        if env not in self.installed:
            self.warning(
                "Sélectionne une distribution WSL installée."
            )
            return ""

        return env

    def project_wsl(self):
        env = self.associations.get(
            self.family_name,
            ""
        )

        if env not in self.installed:
            self.warning(
                "Associe un environnement WSL à "
                + self.family_name
                + " dans l'onglet WSL2."
            )

            self.tabs.setCurrentIndex(5)
            return ""

        return env

    def identify_wsl(self):
        env = self.selected_wsl()

        if env:
            self.job(
                "detect",
                (env,),
                lambda data, error:
                    self.identify_done(
                        env,
                        data,
                        error
                    )
            )

    def identify_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        family, metadata = data

        self.wsl_log.setPlainText(
            "WSL : " + env
            + "\nFamille : " + family
            + "\nVersion : "
            + metadata.get("VERSION_ID", "?")
        )

    def check_wsl_tools(self):
        env = self.selected_wsl()

        if env:
            self.job(
                "tools",
                (env,),
                lambda data, error:
                    self.wsl_tools_done(
                        env,
                        data,
                        error
                    )
            )

    def wsl_tools_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        family, metadata, rows = data

        self.fill(
            self.wsl_tools_table,
            rows
        )

        missing = [
            name
            for name, package, state in rows
            if state == "Absent"
        ]

        self.wsl_log.setPlainText(
            "Environnement : " + env
            + "\nFamille : " + family
            + "\nVersion : "
            + metadata.get("VERSION_ID", "?")
            + "\nOutils absents : "
            + (", ".join(missing) or "aucun")
        )

    def install_wsl_tools(self):
        env = self.selected_wsl()

        if not env:
            return

        if self.confirm(
            "Installer les outils de construction dans "
            + env
            + " ?\n\n"
            "L'opération modifie cet environnement WSL."
        ):
            self.job(
                "install_tools",
                (env,),
                self.install_tools_done
            )

    def install_tools_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            self.warning(
                "Installation impossible :\n" + error
            )
            return

        family, command, result = data
        output, stderr, code = result

        self.wsl_log.setPlainText(
            "Famille : " + family
            + "\nCommande : " + command
            + "\nCode : " + str(code)
            + "\n\n"
            + (output + "\n" + stderr)[-15000:]
        )

        if code:
            self.warning(
                "Installation échouée."
            )
        else:
            self.information(
                "Opération terminée.\n"
                "Relance la vérification des outils."
            )

    def update_selected_wsl(self):
        env = self.selected_wsl()

        if env:
            self.start_update(env)

    def update_project_repositories(self):
        env = self.project_wsl()

        if env:
            self.start_update(env)

    def start_update(self, env):
        if not self.confirm(
            "Actualiser les dépôts de "
            + env
            + " ?\n\n"
            "Attention : sous Arch Linux, cette opération "
            "effectue une mise à niveau complète."
        ):
            return

        self.job(
            "update",
            (env,),
            lambda data, error:
                self.update_done(
                    env,
                    data,
                    error
                )
        )

    def update_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            self.apps_log.setPlainText(error)
            return

        family, command, result = data
        output, stderr, code = result

        message = (
            "WSL : " + env
            + "\nFamille : " + family
            + "\nCommande : " + command
            + "\nCode : " + str(code)
            + "\n\n"
            + (output + "\n" + stderr)[-15000:]
        )

        self.wsl_log.setPlainText(message)
        self.apps_log.setPlainText(message[-3500:])

        if code:
            self.warning(
                "Actualisation échouée."
            )
        else:
            self.information(
                "Opération terminée pour " + env
            )

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def refresh_selected_apps(self):
        self.fill(
            self.apps_table,
            [
                (name,)
                for name in sorted(self.selected_packages)
            ]
        )

    def add_manual_application(self):
        name = self.manual_package.text().strip()

        if not SAFE_PACKAGE.fullmatch(name):
            self.warning(
                "Nom de paquet invalide."
            )
            return

        self.selected_packages.add(name)
        self.manual_package.clear()

        self.refresh_selected_apps()
        self.refresh_target_packages()
        self.invalidate()

    def add_search_result(self, row, column):
        item = self.search_results.item(row, 0)

        if item:
            self.selected_packages.add(item.text())
            self.refresh_selected_apps()
            self.refresh_target_packages()
            self.invalidate()

    def remove_application(self, row, column):
        item = self.apps_table.item(row, 0)

        if item:
            self.selected_packages.discard(item.text())
            self.refresh_selected_apps()
            self.refresh_target_packages()
            self.invalidate()

    def search_applications(self):
        env = self.project_wsl()

        if not env:
            return

        query = self.search_text.text().strip()

        if not query or len(query) > 70:
            self.warning(
                "Recherche invalide."
            )
            return

        family = self.family_name
        revision = self.revision

        self.apps_log.setPlainText(
            "Recherche dans " + env + "..."
        )

        self.job(
            "search",
            (env, family, query),
            lambda data, error:
                self.search_done(
                    family,
                    revision,
                    data,
                    error
                )
        )

    def search_done(
        self,
        family,
        revision,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.apps_log.setPlainText(error)
            return

        output, stderr, code = data

        rows = parse_search(
            family,
            output
        )

        self.fill(
            self.search_results,
            rows
        )

        self.apps_log.setPlainText(
            str(len(rows))
            + " résultats.\n"
            + "Code : " + str(code)
            + "\n"
            + (
                (stderr or output)[:2500]
                if code or not rows
                else "Double-clique pour ajouter un paquet."
            )
        )

    # --------------------------------------------------------
    # PAQUETS CIBLES
    # --------------------------------------------------------

    def target_packages(self):
        family = self.family_name

        packages = set(
            TARGET_BASE[family]
        )

        packages.update(
            DESKTOPS[family].get(
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

        packages.update(
            self.selected_packages
        )

        for name, checkbox in self.flags.items():
            if checkbox.isChecked():
                packages.update(
                    EXTRAS[family].get(name, [])
                )

        if family == "Arch Linux":
            packages.discard("linux")

            packages.add({
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }[self.kernel.currentText()])

        if family == "Gentoo":
            packages.add(
                "sys-apps/openrc"
                if self.init.currentText() == "OpenRC"
                else "sys-apps/systemd"
            )

        return sorted(packages)

    def refresh_target_packages(self):
        if not hasattr(self, "packages_table"):
            return

        base = set(
            TARGET_BASE[self.family_name]
        )

        rows = []

        for package in self.target_packages():
            origin = (
                "Système de base"
                if package in base
                else "Bureau / option / application"
            )

            rows.append((
                package,
                origin
            ))

        self.fill(
            self.packages_table,
            rows
        )

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def verify_project(self):
        env = self.project_wsl()

        if not env:
            return

        revision = self.revision

        self.verification_status.setText(
            "Vérification en cours..."
        )

        self.job(
            "tools",
            (env,),
            lambda data, error:
                self.verify_done(
                    env,
                    revision,
                    data,
                    error
                )
        )

    def verify_done(
        self,
        env,
        revision,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.tools_ok = False
            self.verification_log.setPlainText(error)
            self.verification_status.setText(
                "Échec de vérification"
            )
            return

        family, metadata, rows = data

        self.fill(
            self.checks_table,
            rows
        )

        missing = [
            name
            for name, package, state in rows
            if state == "Absent"
        ]

        target = self.family_name
        release = self.release.currentText()

        issues = []

        if family != target:
            issues.append(
                "Famille WSL incompatible : " + family
            )

        actual_version = metadata.get(
            "VERSION_ID",
            ""
        )

        if target == "Debian":
            codename = metadata.get(
                "VERSION_CODENAME",
                ""
            )

            if release not in (
                actual_version,
                codename
            ):
                issues.append(
                    "Version Debian WSL différente "
                    "de la cible."
                )

        if target == "Fedora":
            if release != actual_version:
                issues.append(
                    "Version Fedora WSL différente "
                    "de la cible."
                )

        if missing:
            issues.append(
                "Outils absents : "
                + ", ".join(missing)
            )

        self.tools_ok = not issues

        if self.tools_ok:
            self.verification_status.setText(
                "Outils de préparation présents"
            )
        else:
            self.verification_status.setText(
                str(len(issues))
                + " problème(s) détecté(s)"
            )

        self.verification_log.setPlainText(
            "Distribution : " + target
            + "\nVersion : " + release
            + "\nWSL : " + env
            + "\nInstallateur prévu : "
            + INSTALLERS[target]
            + "\nGestionnaire cible : "
            + MANAGERS[target]
            + "\n\n"
            + (
                "\n".join(issues)
                if issues
                else "Aucun outil de construction manquant."
            )
            + "\n\n"
            "ATTENTION : cette vérification concerne "
            "l'environnement WSL.\n"
            "Elle ne valide pas l'installateur, "
            "les dépôts dans le système cible, "
            "ni le démarrage de l'ISO."
        )

    # --------------------------------------------------------
    # ANALYSE DES PAQUETS
    # --------------------------------------------------------

    def analyze_packages(self):
        env = self.project_wsl()

        if not env:
            return

        revision = self.revision
        family = self.family_name

        packages = self.target_packages()

        self.refresh_target_packages()

        self.verification_log.setPlainText(
            "Simulation native en cours..."
        )

        self.job(
            "simulate",
            (env, family, packages),
            lambda data, error:
                self.analysis_done(
                    revision,
                    family,
                    data,
                    error
                )
        )

    def analysis_done(
        self,
        revision,
        family,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.analysis_ok = False
            self.verification_log.setPlainText(error)
            return

        output, stderr, code = data

        # DNF5 --assumeno peut retourner un code non nul
        # lors d'un refus volontaire.
        # On ne transforme pas ce code en succès sans preuve.

        self.analysis_ok = code == 0

        self.verification_log.setPlainText(
            "Famille : " + family
            + "\nCode retour : " + str(code)
            + "\nStatut : "
            + (
                "Simulation terminée"
                if self.analysis_ok
                else "Résultat non validé"
            )
            + "\n\n"
            + output
            + "\n"
            + stderr
            + "\n\n"
            "La simulation utilise les paquets déjà présents "
            "dans WSL et ne représente pas nécessairement "
            "les dépendances d'un système cible vierge."
        )

        if not self.analysis_ok:
            self.warning(
                "Analyse non validée.\n"
                "Consulte la sortie native."
            )

    # --------------------------------------------------------
    # PROJET / ISO
    # --------------------------------------------------------

    def project_data(self):
        return {
            "application": "Universal Linux Builder",
            "version": VERSION,
            "family": self.family_name,
            "release": self.release.currentText(),
            "installer": INSTALLERS[self.family_name],
            "manager": MANAGERS[self.family_name],
            "wsl": self.associations.get(
                self.family_name,
                ""
            ),
            "desktop": self.desktop.currentText(),
            "kernel": self.kernel.currentText(),
            "init": self.init.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "bootloader": self.boot.currentText(),
            "boot_mode": self.boot_mode.currentText(),
            "options": {
                name: checkbox.isChecked()
                for name, checkbox in self.flags.items()
            },
            "packages": self.target_packages(),
            "tools_verified": self.tools_ok,
            "dependency_analysis_ok": self.analysis_ok,
            "boot_verified": False,
            "installer_verified": False,
            "ventoy_verified": False
        }

    def export_current_project(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier d'export"
        )

        if not folder:
            return

        try:
            destination = export_project(
                self.project_data(),
                folder
            )

        except Exception as exc:
            self.warning(str(exc))
            return

        self.iso_log.setPlainText(
            "Projet exporté dans :\n"
            + destination
            + "\n\n"
            "Fichiers :\n"
            "universal_linux_project.json\n"
            "packages.txt\n"
            "README.txt"
        )

        self.information(
            "Projet exporté."
        )

    def create_iso(self):
        family = self.family_name

        if family not in (
            "Debian",
            "Arch Linux"
        ):
            self.warning(
                "Construction ISO non implémentée "
                "pour " + family
            )
            return

        if not self.tools_ok:
            self.warning(
                "Vérifie d'abord les outils de construction."
            )

            self.tabs.setCurrentIndex(3)
            return

        if not self.analysis_ok:
            self.warning(
                "L'analyse des paquets doit être validée "
                "avant la construction."
            )

            self.tabs.setCurrentIndex(3)
            return

        env = self.project_wsl()

        if not env:
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier Windows vide"
        )

        if not folder:
            return

        if any(Path(folder).iterdir()):
            self.warning(
                "Le dossier de destination doit être vide."
            )
            return

        if not self.confirm(
            "Lancer la construction expérimentale "
            + family
            + " ?\n\n"
            "Cette opération peut durer longtemps et "
            "nécessiter plusieurs Go d'espace.\n\n"
            "L'installation sur disque, BIOS/UEFI "
            "et Ventoy ne sont pas garantis."
        ):
            return

        self.iso_log.setPlainText(
            "Construction en cours..."
        )

        self.job(
            "build",
            (
                env,
                family,
                self.release.currentText(),
                self.target_packages(),
                folder
            ),
            self.build_done
        )

    def build_done(self, data, error):
        if error:
            self.iso_log.setPlainText(
                "ÉCHEC DE CONSTRUCTION\n\n"
                + error
            )

            self.warning(
                "Construction échouée.\n"
                "Consulte le journal."
            )
            return

        files, report = data

        self.iso_log.setPlainText(
            json.dumps(
                files,
                ensure_ascii=False,
                indent=2
            )
            + "\n\n"
            "Amorçage : NON TESTÉ\n"
            "Installateur : NON TESTÉ\n"
            "Ventoy : NON TESTÉ\n\n"
            + report[-10000:]
        )

        self.information(
            "Fichier ISO produit.\n\n"
            "Teste son démarrage et son installation "
            "dans une machine virtuelle avant "
            "de l'utiliser sur un PC."
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
