import sys
import re
import shlex
import json
import datetime
import subprocess
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QTextEdit, QFileDialog,
    QMessageBox, QInputDialog, QGroupBox, QHeaderView,
    QSplitter, QFrame
)

VERSION = "1.15"

FAMILIES = [
    "Debian",
    "Fedora",
    "Arch Linux",
    "Gentoo",
    "Slackware"
]

COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#51A2DA",
    "Arch Linux": "#1793D1",
    "Gentoo": "#9482C9",
    "Slackware": "#D0D7E2"
}

LOGO_IDS = {
    "Debian": "debian",
    "Fedora": "fedora",
    "Arch Linux": "archlinux",
    "Gentoo": "gentoo",
    "Slackware": "slackware"
}

RELEASES = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

BASE = {
    "Debian": [
        "live-boot",
        "live-config",
        "linux-image-amd64",
        "network-manager"
    ],
    "Fedora": [
        "kernel",
        "NetworkManager"
    ],
    "Arch Linux": [
        "base",
        "linux",
        "networkmanager"
    ],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
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
        "Xfce": ["xfce4", "lightdm"]
    },
    "Fedora": {
        "GNOME": ["gnome-shell", "gdm"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel"]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"]
    },
    "Gentoo": {
        "GNOME": ["gnome-base/gnome"],
        "KDE Plasma": ["kde-plasma/plasma-meta"],
        "Xfce": ["xfce-base/xfce4-meta"]
    },
    "Slackware": {
        "KDE Plasma": ["plasma-desktop"],
        "Xfce": ["xfce4-session"]
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

TOOLS = {
    "Debian": [
        ("lb", "live-build"),
        ("debootstrap", "debootstrap"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso")
    ],
    "Fedora": [
        ("dnf5", "dnf5"),
        ("livemedia-creator", "lorax"),
        ("xorriso", "xorriso"),
        ("mksquashfs", "squashfs-tools")
    ],
    "Arch Linux": [
        ("mkarchiso", "archiso"),
        ("pacman", "pacman"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "libisoburn")
    ],
    "Gentoo": [
        ("emerge", "sys-apps/portage"),
        ("mksquashfs", "sys-fs/squashfs-tools"),
        ("xorriso", "app-cdr/libisoburn")
    ],
    "Slackware": [
        ("slackpkg", "slackpkg"),
        ("mkisofs", "cdrtools"),
        ("mksquashfs", "squashfs-tools")
    ]
}

SAFE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)

CACHE = Path.home() / ".universal_linux_builder" / "logos"


# ============================================================
# LOGOS DES DISTRIBUTIONS
# ============================================================

def load_logo(family, size=42):
    """
    Récupère une icône SVG de la distribution.
    Le SVG est mis en cache localement.
    Une icône de remplacement est utilisée hors connexion.
    """

    CACHE.mkdir(parents=True, exist_ok=True)

    identifier = LOGO_IDS[family]
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
                    "User-Agent": "UniversalLinuxBuilder/1.15"
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
        renderer = QSvgRenderer(
            str(filename)
        )

        if renderer.isValid():
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )

    painter.setBrush(
        QColor(COLORS[family])
    )

    painter.setPen(
        Qt.PenStyle.NoPen
    )

    painter.drawEllipse(
        2, 2, size - 4, size - 4
    )

    painter.end()

    return pixmap


# ============================================================
# EXECUTION WINDOWS / WSL
# ============================================================

def clean(text):
    return ANSI.sub("", text).replace("\r", "\n")


def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return clean(
            data.decode("utf-16", "replace")
        )

    if b"\x00" in data[:100]:
        return clean(
            data.decode("utf-16-le", "replace").lstrip("\ufeff")
        )

    return clean(
        data.decode("utf-8", "replace")
    )


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
    args = ["wsl.exe", "-d", env]

    if root:
        args += ["-u", "root"]

    args += [
        "--exec",
        "/bin/sh",
        "-lc",
        command
    ]

    return run(args, timeout)


def installed():
    output, error, code = run(
        ["wsl.exe", "--list", "--quiet"],
        60
    )

    if code:
        raise RuntimeError(error or output)

    return [
        item.strip().lstrip("\ufeff")
        for item in output.splitlines()
        if item.strip()
    ]


def catalog():
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

        if match and match.group(1).lower() not in (
            "name", "nom"
        ):
            rows.append(match.groups())

    return rows, output


def detect(env):
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


def prereq(env):
    family, metadata = detect(env)

    if family not in TOOLS:
        return family, metadata, [], ""

    commands = []

    for tool, package in TOOLS[family]:
        commands.append(
            "if command -v "
            + shlex.quote(tool)
            + " >/dev/null 2>&1; then echo "
            + shlex.quote(tool + ":OK")
            + "; else echo "
            + shlex.quote(tool + ":MISSING")
            + "; fi"
        )

    output, error, code = wsl(
        env,
        "; ".join(commands),
        90
    )

    if code:
        raise RuntimeError(error or output)

    states = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.split(":", 1)
            states[name] = state == "OK"

    rows = []

    for tool, package in TOOLS[family]:
        rows.append((
            tool,
            package,
            "Présent" if states.get(tool) else "Absent"
        ))

    extra = ""

    if family == "Arch Linux":
        _, _, code = wsl(
            env,
            "test -f /usr/share/archiso/configs/releng/profiledef.sh",
            60
        )

        extra = (
            "Profil releng : "
            + ("présent" if code == 0 else "absent")
        )

    return family, metadata, rows, extra


def install_prereqs(env):
    family, metadata, rows, extra = prereq(env)

    missing = sorted(set(
        package
        for _, package, state in rows
        if state == "Absent"
    ))

    if not missing:
        return family, "Aucun outil manquant", ("", "", 0)

    args = " ".join(
        map(shlex.quote, missing)
    )

    if family == "Debian":
        command = (
            "DEBIAN_FRONTEND=noninteractive apt-get update && "
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends "
            + args
        )

    elif family == "Fedora":
        command = "dnf5 -y install " + args

    elif family == "Arch Linux":
        command = (
            "pacman --noconfirm -Syu --needed "
            + args
        )

    else:
        raise RuntimeError(
            "Installation automatique indisponible pour "
            + family
        )

    return family, command, wsl(
        env,
        command,
        3600,
        True
    )


def update_repos(env):
    family, metadata = detect(env)

    commands = {
        "Debian": "DEBIAN_FRONTEND=noninteractive apt-get update",
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman -Syu --noconfirm",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    if family not in commands:
        raise RuntimeError(
            "Distribution non prise en charge"
        )

    command = commands[family]

    return family, command, wsl(
        env,
        command,
        3600,
        True
    )


# ============================================================
# APPLICATIONS ET DEPENDANCES
# ============================================================

def search(env, family, query):
    managers = {
        "Debian": "apt-cache search",
        "Fedora": "dnf5 search",
        "Arch Linux": "pacman -Ss",
        "Gentoo": "emerge --search",
        "Slackware": "slackpkg search"
    }

    command = (
        "LC_ALL=C "
        + managers[family]
        + " "
        + shlex.quote(query)
    )

    return wsl(env, command, 300)


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

        if name and SAFE.fullmatch(name) and name not in seen:
            seen.add(name)
            rows.append((
                name,
                version,
                description[:170]
            ))

    return rows[:600]


def simulate(env, family, packages):
    args = " ".join(
        map(shlex.quote, packages)
    )

    commands = {
        "Debian": "LC_ALL=C apt-get -s install " + args,
        "Fedora": "LC_ALL=C dnf5 --assumeno install " + args,
        "Arch Linux": (
            'LC_ALL=C pacman -Sp '
            '--print-format "%n|%v|%s" '
            + args
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend --verbose --tree "
            + args
        ),
        "Slackware": (
            'echo "Slackware : résolution automatique '
            'des dépendances non disponible"'
        )
    }

    return wsl(
        env,
        commands[family],
        600
    )


def parse_size(value):
    match = re.search(
        r"([\d.,]+)\s*(B|KiB|MiB|GiB)",
        value,
        re.I
    )

    if not match:
        return None

    number = float(
        match.group(1).replace(",", ".")
    )

    factor = {
        "b": 1,
        "kib": 1024,
        "mib": 1024 ** 2,
        "gib": 1024 ** 3
    }[match.group(2).lower()]

    return int(number * factor)


def human(number):
    if number is None:
        return "—"

    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if number < 1024:
            return f"{number:.1f} {unit}"

        number /= 1024

    return f"{number:.1f} Pio"


def parse_transaction(family, output, requested):
    rows = {
        package: {
            "version": "?",
            "size": None,
            "status": "Demandé"
        }
        for package in requested
    }

    for line in output.splitlines():

        if family == "Debian":
            match = re.match(
                r"^Inst\s+(\S+)"
                r"(?:\s+\[.*?\])?\s+\(([^ )]+)",
                line
            )

            if match:
                rows[match.group(1)] = {
                    "version": match.group(2),
                    "size": None,
                    "status": "Transaction"
                }

        elif family == "Arch Linux":
            match = re.match(
                r"^([^|]+)\|([^|]+)\|(\d+)$",
                line.strip()
            )

            if match:
                rows[match.group(1)] = {
                    "version": match.group(2),
                    "size": int(match.group(3)),
                    "status": "Transaction"
                }

        elif family == "Fedora":
            match = re.match(
                r"^\s*([\w+.-]+)\s+"
                r"(?:x86_64|noarch|aarch64|i686)\s+"
                r"(\S+)\s+(\S+)(?:\s+(.+))?$",
                line
            )

            if match:
                rows[match.group(1)] = {
                    "version": match.group(2),
                    "size": parse_size(
                        match.group(4) or ""
                    ),
                    "status": "Transaction"
                }

        elif family == "Gentoo":
            match = re.search(
                r"\[ebuild[^]]*\]\s+"
                r"([\w+.-]+/[\w+.-]+)-([\w.+-]+)",
                line
            )

            if match:
                rows[match.group(1)] = {
                    "version": match.group(2),
                    "size": None,
                    "status": "Transaction"
                }

    return rows


def assess(family, output, error, code):
    if code == 0:
        return True, "Simulation terminée"

    if family == "Fedora":
        text = output + "\n" + error

        if (
            re.search(
                r"(?m)^\s*Package\s+Arch\s+Version",
                text
            )
            and re.search(
                r"Transaction Summary|Total download size",
                text,
                re.I
            )
            and re.search(
                r"Operation aborted|Operation cancelled|"
                r"Operation canceled|Is this ok",
                text,
                re.I
            )
        ):
            return True, "Transaction DNF5 analysée"

    return False, "Échec de simulation : " + str(code)


def estimate(rows):
    values = [
        item["size"]
        for item in rows.values()
        if item["size"] is not None
    ]

    if not values:
        return "Estimation indisponible"

    coverage = len(values) / max(1, len(rows))

    if coverage < 0.35:
        return (
            "Données insuffisantes : "
            + human(sum(values))
            + " mesurés"
        )

    total = sum(values) / coverage

    minimum = int(
        total * 0.8 + 650 * 1024 ** 2
    )

    maximum = int(
        total * 2 + 1700 * 1024 ** 2
    )

    return (
        human(minimum)
        + " à "
        + human(maximum)
        + " (indicatif)"
    )


# ============================================================
# CONSTRUCTION ISO EXPERIMENTALE
# ============================================================

def build(env, family, release, packages, target):
    if family not in ("Debian", "Arch Linux"):
        raise RuntimeError(
            "Construction non intégrée pour " + family
        )

    actual, metadata, checks, extra = prereq(env)

    if actual != family:
        raise RuntimeError(
            "Environnement WSL incompatible : " + actual
        )

    missing = [
        package
        for _, package, state in checks
        if state == "Absent"
    ]

    if missing:
        raise RuntimeError(
            "Prérequis manquants : "
            + ", ".join(missing)
        )

    if family == "Arch Linux" and "absent" in extra:
        raise RuntimeError(
            "Profil Archiso releng absent"
        )

    folder = Path(target)

    if any(folder.iterdir()):
        raise RuntimeError(
            "Le dossier de destination doit être vide"
        )

    workspace = (
        "/var/tmp/ulb-"
        + datetime.datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )
    )

    work = shlex.quote(workspace)
    args = " ".join(
        map(shlex.quote, packages)
    )

    if family == "Debian":
        script = (
            "set -eu; "
            "mkdir -p " + work + "; "
            "cd " + work + "; "
            "lb config "
            "--distribution " + shlex.quote(release) + " "
            "--architectures amd64 "
            "--binary-images iso-hybrid; "
            "mkdir -p config/package-lists; "
            'printf "%s\\n" ' + args
            + " > config/package-lists/ulb.list.chroot; "
            "lb build"
        )

    else:
        script = (
            "set -eu; "
            "mkdir -p " + work + "; "
            "cp -a /usr/share/archiso/configs/releng "
            + work + "/profile; "
            "cd " + work + "; "
            'printf "%s\\n" ' + args
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
        True
    )

    report = (
        "Distribution : " + family
        + "\nWSL : " + env
        + "\nWorkspace : " + workspace
        + "\nCode : " + str(code)
        + "\n\n" + output
        + "\n" + error
    )

    (folder / "build_report.txt").write_text(
        report,
        encoding="utf-8"
    )

    if code:
        raise RuntimeError(
            "Construction échouée (code "
            + str(code)
            + "). Voir build_report.txt\n"
            + (error or output)[-1800:]
        )

    paths, error, code = wsl(
        env,
        "find "
        + work
        + ' -type f -name "*.iso" -print',
        90,
        True
    )

    if code or not paths.strip():
        raise RuntimeError(
            "Aucune ISO produite"
        )

    copied = []

    for index, source in enumerate(
        paths.splitlines(), 1
    ):
        destination = folder / (
            "ULB_"
            + family.replace(" ", "_")
            + "_"
            + str(index)
            + ".iso"
        )

        with destination.open("wb") as handle:
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

        with destination.open("rb") as handle:
            handle.seek(32768)
            signature = handle.read(7)

        copied.append({
            "fichier": str(destination),
            "taille": human(
                destination.stat().st_size
            ),
            "iso9660": (
                len(signature) >= 6
                and signature[1:6] == b"CD001"
            ),
            "boot_teste": False,
            "ventoy_teste": False
        })

    return copied, report


# ============================================================
# WORKER
# ============================================================

class Worker(QThread):
    done = Signal(object, str)

    def __init__(self, action, *args):
        super().__init__()

        self.action = action
        self.args = args

    def run(self):
        try:
            action = self.action
            args = self.args

            if action == "installed":
                result = installed()

            elif action == "catalog":
                result = catalog()

            elif action == "detect":
                result = detect(*args)

            elif action == "prereq":
                result = prereq(*args)

            elif action == "install_prereq":
                result = install_prereqs(*args)

            elif action == "update":
                result = update_repos(*args)

            elif action == "search":
                result = search(*args)

            elif action == "simulate":
                result = simulate(*args)

            elif action == "build":
                result = build(*args)

            elif action == "install_wsl":
                result = run(
                    [
                        "wsl.exe",
                        "--install",
                        "--distribution",
                        args[0],
                        "--no-launch"
                    ],
                    1800
                )

            elif action == "delete_wsl":
                result = run(
                    [
                        "wsl.exe",
                        "--unregister",
                        args[0]
                    ],
                    900
                )

            else:
                raise RuntimeError(
                    "Action inconnue"
                )

            self.done.emit(result, "")

        except Exception as exc:
            self.done.emit(
                None,
                str(exc)
            )


# ============================================================
# THEME SOMBRE PROFESSIONNEL
# ============================================================

DARK = """
QWidget {
    background-color: #10151D;
    color: #DCE4EF;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow {
    background-color: #10151D;
}

QLabel {
    background: transparent;
}

QLineEdit,
QComboBox,
QTextEdit,
QTableWidget {
    background-color: #171F2B;
    border: 1px solid #2C394B;
    border-radius: 5px;
    padding: 5px;
    color: #E5ECF5;
    selection-background-color: #28558A;
}

QLineEdit:focus,
QComboBox:focus {
    border: 1px solid #4F8AC9;
}

QPushButton {
    background-color: #253448;
    border: 1px solid #354A62;
    border-radius: 5px;
    padding: 6px 12px;
    min-height: 22px;
    color: #E5EDF7;
}

QPushButton:hover {
    background-color: #304761;
    border-color: #52789E;
}

QPushButton:pressed {
    background-color: #1E3045;
}

QTabWidget::pane {
    border: 1px solid #263447;
    border-top: none;
    background: #10151D;
}

QTabBar::tab {
    background: #151D29;
    color: #AAB8CB;
    padding: 10px 18px;
    border-right: 1px solid #263447;
}

QTabBar::tab:selected {
    background: #1D2A3B;
    color: #FFFFFF;
    border-bottom: 2px solid #5B9DE3;
}

QTabBar::tab:hover {
    background: #202F42;
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
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #9EB8D6;
}

QCheckBox {
    spacing: 9px;
}

QSplitter::handle {
    background: #263447;
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
# INTERFACE
# ============================================================

class App(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.15"
        )

        self.resize(1400, 900)

        self.inst = []
        self.catalog = []

        self.mapping = {
            family: ""
            for family in FAMILIES
        }

        self.apps = set()
        self.solution = {}

        self.valid = False
        self.checked = False
        self.revision = 0
        self.worker = None

        self.current_family = "Debian"
        self.cards = {}
        self.banners = []

        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(16, 12, 16, 10)
        main.setSpacing(10)

        # EN-TETE

        header = QHBoxLayout()
        header.setSpacing(12)

        self.brand = QLabel()
        self.brand.setFixedSize(48, 48)
        header.addWidget(self.brand)

        title_area = QVBoxLayout()
        title_area.setSpacing(2)

        title = QLabel(
            "Universal Linux Builder"
        )

        title.setStyleSheet(
            "font-size:20px;"
            "font-weight:600;"
            "color:#F0F5FC;"
        )

        title_area.addWidget(title)

        self.current = QLabel()

        self.current.setStyleSheet(
            "color:#8FA9C8;"
            "font-size:12px;"
        )

        title_area.addWidget(self.current)
        header.addLayout(title_area)

        header.addStretch()

        version = QLabel("v1.15")
        version.setStyleSheet(
            "color:#738AA5;"
            "font-size:12px;"
        )

        header.addWidget(version)

        main.addLayout(header)

        separator = QFrame()
        separator.setFrameShape(
            QFrame.Shape.HLine
        )

        separator.setStyleSheet(
            "color:#273448;"
        )

        main.addWidget(separator)

        # ONGLETS

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)

        main.addWidget(self.tabs)

        self.tab_distribution()
        self.tab_system()
        self.tab_apps()
        self.tab_verify()
        self.tab_iso()
        self.tab_wsl()

        self.status = QLabel("Prêt")

        self.status.setStyleSheet(
            "color:#7892AF;"
            "font-size:11px;"
        )

        main.addWidget(self.status)

        self.setStyleSheet(DARK)

        self.change_family()

        # Chargement initial des WSL.
        self.refresh_wsl()

    # ========================================================
    # OUTILS INTERFACE
    # ========================================================

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            16, 16, 16, 16
        )

        layout.setSpacing(12)

        self.tabs.addTab(
            widget,
            name
        )

        return layout

    def combo(self, items=()):
        widget = QComboBox()
        widget.addItems(items)
        return widget

    def button(self, text, callback):
        widget = QPushButton(text)
        widget.clicked.connect(callback)
        return widget

    def table(self, headers):
        table = QTableWidget(
            0,
            len(headers)
        )

        table.setHorizontalHeaderLabels(
            headers
        )

        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(29)

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        table.horizontalHeader().setStretchLastSection(True)

        return table

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

        item = (
            table.item(row, 0)
            if row >= 0
            else None
        )

        return item.text() if item else ""

    def warn(self, message):
        QMessageBox.warning(
            self,
            "Universal Linux Builder",
            message
        )

    def info(self, message):
        QMessageBox.information(
            self,
            "Universal Linux Builder",
            message
        )

    def ask(self, message):
        return QMessageBox.question(
            self,
            "Confirmation",
            message
        ) == QMessageBox.StandardButton.Yes

    def job(self, action, args, callback):
        if self.worker is not None:
            self.warn(
                "Une opération est déjà en cours."
            )
            return

        worker = Worker(
            action,
            *args
        )

        self.worker = worker

        self.status.setText(
            "En cours : " + action
        )

        worker.done.connect(callback)

        worker.finished.connect(
            lambda w=worker: self.finished(w)
        )

        worker.start()

    def finished(self, worker):
        if self.worker is worker:
            self.worker = None

        worker.deleteLater()
        self.status.setText("Prêt")

    def invalidate(self, *_):
        self.revision += 1
        self.valid = False
        self.checked = False

    def family(self):
        return self.current_family

    def project_env(self):
        return self.mapping.get(
            self.family(),
            ""
        )

    def banner(self, layout):
        row = QHBoxLayout()

        logo = QLabel()
        logo.setFixedSize(25, 25)

        label = QLabel()

        label.setStyleSheet(
            "font-size:13px;"
            "font-weight:600;"
            "color:#C9D8EA;"
        )

        row.addWidget(logo)
        row.addWidget(label)
        row.addStretch()

        layout.addLayout(row)

        self.banners.append(
            (logo, label)
        )

    def update_banners(self):
        family = self.family()
        release = self.release.currentText()

        self.brand.setPixmap(
            load_logo(family, 44)
        )

        self.current.setText(
            family
            + "  •  "
            + release
            + "  |  WSL : "
            + (self.project_env() or "non associé")
        )

        for logo, label in self.banners:
            logo.setPixmap(
                load_logo(family, 23)
            )

            label.setText(
                family + "  /  " + release
            )

        for name, button in self.cards.items():
            selected = name == family

            button.setProperty(
                "selectedCard",
                selected
            )

            if selected:
                button.setStyleSheet(
                    "QPushButton {"
                    "background:#20354C;"
                    "border:1px solid #5796D5;"
                    "border-radius:7px;"
                    "padding:8px 12px;"
                    "font-weight:600;"
                    "color:#FFFFFF;"
                    "}"
                    "QPushButton:hover {"
                    "background:#29445F;"
                    "}"
                )

            else:
                button.setStyleSheet(
                    "QPushButton {"
                    "background:#192431;"
                    "border:1px solid #2C3A4D;"
                    "border-radius:7px;"
                    "padding:8px 12px;"
                    "color:#B8C8DB;"
                    "}"
                    "QPushButton:hover {"
                    "background:#24364B;"
                    "border-color:#466481;"
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

    # ========================================================
    # DISTRIBUTION
    # ========================================================

    def tab_distribution(self):
        layout = self.page("Distribution")

        title = QLabel(
            "Choisir une distribution"
        )

        title.setStyleSheet(
            "font-size:16px;"
            "font-weight:600;"
            "color:#E7EFF9;"
        )

        layout.addWidget(title)

        subtitle = QLabel(
            "Sélectionne la base Linux de ton projet ISO."
        )

        subtitle.setStyleSheet(
            "color:#8499B3;"
        )

        layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setSpacing(9)

        for family in FAMILIES:
            button = QPushButton(family)

            button.setIcon(
                QIcon(load_logo(family, 33))
            )

            button.setIconSize(
                QSize(33, 33)
            )

            button.setFixedHeight(64)
            button.setMinimumWidth(150)

            button.clicked.connect(
                lambda checked=False, f=family:
                    self.select_family(f)
            )

            cards.addWidget(button)
            self.cards[family] = button

        layout.addLayout(cards)

        # Le menu de distribution cible a été supprimé.
        # Seule la version reste configurable.

        form = QFormLayout()
        form.setSpacing(12)

        self.release = self.combo()

        self.release.setMaximumWidth(330)

        form.addRow(
            "Version",
            self.release
        )

        layout.addLayout(form)

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        note = QLabel(
            "La distribution sélectionnée est conservée "
            "dans tout le processus de création. "
            "L'environnement WSL associé doit appartenir "
            "à la même famille."
        )

        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#8499B3;"
        )

        layout.addWidget(note)

        layout.addStretch()
        self.next_button(layout, 1)

    # ========================================================
    # SYSTEME
    # ========================================================

    def tab_system(self):
        layout = self.page("Système")
        self.banner(layout)

        form = QFormLayout()
        form.setSpacing(12)

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

        self.bootmode = self.combo([
            "UEFI",
            "BIOS"
        ])

        fields = [
            ("Environnement de bureau", self.desktop),
            ("Noyau", self.kernel),
            ("Initialisation", self.init),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Bootloader", self.boot),
            ("Mode d'amorçage", self.bootmode)
        ]

        for name, widget in fields:
            widget.setMaximumWidth(400)

            form.addRow(
                name,
                widget
            )

            widget.currentTextChanged.connect(
                self.invalidate
            )

        layout.addLayout(form)

        self.flags = {}

        for name, default in [
            ("Wi-Fi", True),
            ("Bluetooth", True),
            ("Impression", False),
            ("Firmware", True)
        ]:
            checkbox = QCheckBox(name)
            checkbox.setChecked(default)

            checkbox.toggled.connect(
                self.invalidate
            )

            self.flags[name] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()
        self.next_button(layout, 2)

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def tab_apps(self):
        layout = self.page("Applications")
        self.banner(layout)

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher un paquet : firefox, vlc, gimp..."
        )

        self.query.returnPressed.connect(
            self.search_apps
        )

        row.addWidget(self.query)

        row.addWidget(
            self.button(
                "Rechercher",
                self.search_apps
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_project
            )
        )

        layout.addLayout(row)

        layout.addWidget(
            QLabel("Résultats de recherche")
        )

        self.results = self.table([
            "Paquet",
            "Version",
            "Description"
        ])

        self.results.setColumnWidth(0, 270)
        self.results.setColumnWidth(1, 160)

        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(
            self.results,
            3
        )

        layout.addWidget(
            QLabel("Applications sélectionnées")
        )

        self.selected_apps = self.table([
            "Paquet"
        ])

        self.selected_apps.cellDoubleClicked.connect(
            self.remove_app
        )

        layout.addWidget(
            self.selected_apps,
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

        self.app_log = QTextEdit()
        self.app_log.setReadOnly(True)
        self.app_log.setMaximumHeight(95)

        layout.addWidget(self.app_log)

        self.next_button(layout, 3)

    # ========================================================
    # VERIFICATION
    # ========================================================

    def tab_verify(self):
        layout = self.page("Vérification")
        self.banner(layout)

        self.verdict = QLabel(
            "Aucune vérification effectuée"
        )

        self.verdict.setStyleSheet(
            "font-size:13px;"
            "color:#A9BCD4;"
        )

        layout.addWidget(self.verdict)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Vérifier les prérequis",
                self.verify_project
            )
        )

        row.addWidget(
            self.button(
                "Analyser les dépendances",
                self.analyze
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.check_table = self.table([
            "Contrôle",
            "Résultat",
            "Détail"
        ])

        self.check_table.setColumnWidth(0, 250)
        self.check_table.setColumnWidth(1, 130)

        layout.addWidget(
            self.check_table,
            1
        )

        self.package_table = self.table([
            "Paquet",
            "Version",
            "Statut",
            "Taille"
        ])

        self.package_table.setColumnWidth(0, 310)
        self.package_table.setColumnWidth(1, 190)
        self.package_table.setColumnWidth(2, 180)
        self.package_table.setColumnWidth(3, 120)

        layout.addWidget(
            self.package_table,
            3
        )

        self.verify_log = QTextEdit()
        self.verify_log.setReadOnly(True)

        layout.addWidget(
            self.verify_log,
            2
        )

        self.next_button(layout, 4)

    # ========================================================
    # ISO
    # ========================================================

    def tab_iso(self):
        layout = self.page("ISO")
        self.banner(layout)

        self.iso_summary = QLabel(
            "Effectue les vérifications avant "
            "de lancer la construction."
        )

        self.iso_summary.setWordWrap(True)
        layout.addWidget(self.iso_summary)

        note = QLabel(
            "Construction expérimentale : Debian et Arch Linux. "
            "Pour Fedora, Gentoo et Slackware, seule la préparation "
            "et la vérification sont actuellement disponibles. "
            "La compatibilité Ventoy doit être testée."
        )

        note.setWordWrap(True)

        note.setStyleSheet(
            "color:#8EA4BF;"
        )

        layout.addWidget(note)

        row = QHBoxLayout()

        create = self.button(
            "Créer l'ISO",
            self.create_iso
        )

        create.setFixedWidth(180)

        row.addWidget(create)
        row.addStretch()

        layout.addLayout(row)

        self.iso_log = QTextEdit()
        self.iso_log.setReadOnly(True)

        layout.addWidget(self.iso_log)

    # ========================================================
    # WSL2
    # ========================================================

    def tab_wsl(self):
        layout = self.page("WSL2")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Distributions installées",
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
        layout.addLayout(row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QGroupBox("Catalogue WSL")
        left_layout = QVBoxLayout(left)

        self.catalog_table = self.table([
            "Nom",
            "Description"
        ])

        self.catalog_table.setColumnWidth(0, 190)

        left_layout.addWidget(
            self.catalog_table
        )

        left_layout.addWidget(
            self.button(
                "Installer la distribution",
                self.install_wsl
            )
        )

        splitter.addWidget(left)

        right = QGroupBox("Distributions installées")
        right_layout = QVBoxLayout(right)

        self.inst_table = self.table([
            "Nom WSL"
        ])

        right_layout.addWidget(
            self.inst_table
        )

        right_layout.addWidget(
            self.button(
                "Supprimer",
                self.delete_wsl
            )
        )

        splitter.addWidget(right)
        splitter.setSizes([680, 440])

        layout.addWidget(splitter, 2)

        row = QHBoxLayout()

        row.addWidget(
            QLabel("WSL à gérer")
        )

        self.wsl_box = self.combo()
        row.addWidget(self.wsl_box, 1)

        for title, callback in [
            ("Tester", self.test_wsl),
            ("Vérifier les outils", self.check_prereq),
            ("Installer les outils", self.install_prereq),
            ("Mise à jour", self.update_wsl)
        ]:
            row.addWidget(
                self.button(
                    title,
                    callback
                )
            )

        layout.addLayout(row)

        self.prereq_table = self.table([
            "Outil",
            "Paquet",
            "État"
        ])

        self.prereq_table.setColumnWidth(0, 190)
        self.prereq_table.setColumnWidth(1, 230)

        layout.addWidget(
            self.prereq_table,
            1
        )

        group = QGroupBox(
            "Association des environnements WSL aux projets"
        )

        form = QFormLayout(group)
        self.mapping_boxes = {}

        for family in FAMILIES:
            row = QHBoxLayout()

            logo = QLabel()
            logo.setPixmap(
                load_logo(family, 22)
            )

            row.addWidget(logo)

            combo = self.combo([
                "— Non associé —"
            ])

            row.addWidget(combo)

            form.addRow(
                family,
                row
            )

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.associate(f, value)
            )

            self.mapping_boxes[family] = combo

        layout.addWidget(group)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setMaximumHeight(125)

        layout.addWidget(self.wsl_log)

    # ========================================================
    # DISTRIBUTION ACTIVE
    # ========================================================

    def select_family(self, family):
        if family == self.current_family:
            return

        self.current_family = family
        self.change_family()

    def release_changed(self, *_):
        self.invalidate()
        self.update_banners()

    def change_family(self):
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

        self.kernel.setCurrentText("Stable")

        self.apps.clear()
        self.refresh_apps()

        self.invalidate()
        self.update_banners()

    def associate(self, family, value):
        self.mapping[family] = (
            ""
            if value == "— Non associé —"
            else value
        )

        self.invalidate()
        self.update_banners()

    # ========================================================
    # WSL2 : INVENTAIRE
    # ========================================================

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

        self.inst = data

        self.fill(
            self.inst_table,
            [(name,) for name in data]
        )

        self.wsl_box.clear()
        self.wsl_box.addItems(data)

        for family, combo in self.mapping_boxes.items():
            old = self.mapping[family]

            combo.blockSignals(True)
            combo.clear()

            combo.addItems(
                ["— Non associé —"] + data
            )

            if old in data:
                combo.setCurrentText(old)
            else:
                self.mapping[family] = ""

            combo.blockSignals(False)

        self.update_banners()

        self.wsl_log.setPlainText(
            "WSL installées : "
            + (", ".join(data) or "aucune")
        )

    def refresh_catalog(self):
        self.job(
            "catalog",
            (),
            self.catalog_loaded
        )

    def catalog_loaded(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        rows, raw = data

        self.catalog = rows

        self.fill(
            self.catalog_table,
            rows
        )

        self.wsl_log.setPlainText(
            str(len(rows))
            + " distributions disponibles.\n"
            + (
                raw[:1500]
                if not rows
                else "Sélectionne une distribution."
            )
        )

    def install_wsl(self):
        name = self.selected(
            self.catalog_table
        )

        available = [
            item[0]
            for item in self.catalog
        ]

        if name not in available:
            self.warn(
                "Sélectionne une distribution du catalogue."
            )
            return

        if name in self.inst:
            self.warn("Déjà installée.")
            return

        if self.ask(
            "Installer " + name + " dans WSL2 ?"
        ):
            self.job(
                "install_wsl",
                (name,),
                lambda data, error:
                    self.operation_done(
                        "Installation",
                        data,
                        error
                    )
            )

    def delete_wsl(self):
        name = self.selected(
            self.inst_table
        )

        if not name:
            self.warn(
                "Sélectionne une distribution installée."
            )
            return

        typed, ok = QInputDialog.getText(
            self,
            "Suppression définitive",
            "Toutes les données de "
            + name
            + " seront supprimées.\n"
            + "Saisis exactement : "
            + name
        )

        if (
            ok
            and typed == name
            and self.ask(
                "Confirmer la suppression irréversible "
                "de " + name + " ?"
            )
        ):
            self.job(
                "delete_wsl",
                (name,),
                lambda data, error:
                    self.operation_done(
                        "Suppression",
                        data,
                        error
                    )
            )

    def operation_done(self, title, data, error):
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
            self.warn(
                title + " échouée."
            )
        else:
            self.refresh_wsl()

    def current_wsl(self):
        env = self.wsl_box.currentText().strip()

        if not env or env not in self.inst:
            self.warn(
                "Sélectionne une distribution WSL installée."
            )
            return ""

        return env

    def test_wsl(self):
        env = self.current_wsl()

        if env:
            self.job(
                "detect",
                (env,),
                lambda data, error:
                    self.test_done(
                        env,
                        data,
                        error
                    )
            )

    def test_done(self, env, data, error):
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

    def check_prereq(self):
        env = self.current_wsl()

        if env:
            self.job(
                "prereq",
                (env,),
                lambda data, error:
                    self.prereq_done(
                        env,
                        data,
                        error
                    )
            )

    def prereq_done(self, env, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            return

        family, metadata, rows, extra = data

        self.fill(
            self.prereq_table,
            rows
        )

        missing = [
            row[1]
            for row in rows
            if row[2] == "Absent"
        ]

        self.wsl_log.setPlainText(
            "WSL : " + env
            + "\nFamille : " + family
            + "\nVersion : "
            + metadata.get("VERSION_ID", "?")
            + "\n"
            + extra
            + "\nManquants : "
            + (", ".join(missing) or "aucun")
        )

    def install_prereq(self):
        env = self.current_wsl()

        if not env:
            return

        if self.ask(
            "Installer les prérequis dans "
            + env
            + " ?\n\n"
            "Debian : APT\n"
            "Fedora : DNF5\n"
            "Arch : Pacman -Syu\n\n"
            "Cette opération modifie le système WSL."
        ):
            self.job(
                "install_prereq",
                (env,),
                self.install_done
            )

    def install_done(self, data, error):
        if error:
            self.wsl_log.setPlainText(error)
            self.warn("Installation échouée.")
            return

        family, command, result = data
        output, stderr, code = result

        self.wsl_log.setPlainText(
            "Commande : " + command
            + "\nCode : " + str(code)
            + "\n"
            + (output + "\n" + stderr)[-15000:]
        )

        if code:
            self.warn(
                "Installation échouée : "
                + str(code)
            )
        else:
            self.info(
                "Installation terminée. "
                "Relance la vérification."
            )

    def update_wsl(self):
        env = self.current_wsl()

        if not env:
            return

        if self.ask(
            "Actualiser les dépôts de "
            + env
            + " ?\n"
            "Arch Linux : mise à niveau complète."
        ):
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

    def update_project(self):
        env = self.project_env()

        if not env:
            self.warn(
                "Associe un environnement WSL "
                "au projet dans l'onglet WSL2."
            )
            return

        if self.ask(
            "Actualiser les dépôts de " + env + " ?"
        ):
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
            return

        family, command, result = data
        output, stderr, code = result

        message = (
            "WSL : " + env
            + "\nCommande : " + command
            + "\nCode : " + str(code)
            + "\n"
            + (output + "\n" + stderr)[-15000:]
        )

        self.wsl_log.setPlainText(message)
        self.app_log.setPlainText(
            message[-3500:]
        )

        if code:
            self.warn("Mise à jour échouée.")
        else:
            self.info(
                "Dépôts actualisés : " + env
            )

    # ========================================================
    # APPLICATIONS
    # ========================================================

    def refresh_apps(self):
        self.fill(
            self.selected_apps,
            [(name,) for name in sorted(self.apps)]
        )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):
            self.warn("Nom de paquet invalide.")
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
        item = self.selected_apps.item(row, 0)

        if item:
            self.apps.discard(item.text())
            self.refresh_apps()
            self.invalidate()

    def project_wsl(self):
        env = self.project_env()

        if not env or env not in self.inst:
            self.warn(
                "Associe une distribution WSL installée "
                "dans l'onglet WSL2."
            )

            self.tabs.setCurrentIndex(5)
            return ""

        return env

    def search_apps(self):
        env = self.project_wsl()
        query = self.query.text().strip()

        if not env:
            return

        if not query or len(query) > 70:
            self.warn("Recherche invalide.")
            return

        family = self.family()
        revision = self.revision

        self.app_log.setPlainText(
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
            self.app_log.setPlainText(error)
            return

        output, stderr, code = data

        rows = parse_search(
            family,
            output
        )

        self.fill(
            self.results,
            rows
        )

        self.app_log.setPlainText(
            str(len(rows))
            + " résultats ; code "
            + str(code)
            + "\n"
            + (
                (stderr or output)[:2500]
                if code or not rows
                else "Double-clique pour ajouter."
            )
        )

    # ========================================================
    # PAQUETS DU PROJET
    # ========================================================

    def packages(self):
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

        for flag, checkbox in self.flags.items():
            if checkbox.isChecked():
                packages.update(
                    EXTRAS[family].get(flag, [])
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

    # ========================================================
    # VERIFICATION
    # ========================================================

    def verify_project(self):
        env = self.project_wsl()

        if not env:
            return

        revision = self.revision

        self.verdict.setText(
            "Vérification en cours..."
        )

        self.job(
            "prereq",
            (env,),
            lambda data, error:
                self.verify_done(
                    revision,
                    env,
                    data,
                    error
                )
        )

    def verify_done(
        self,
        revision,
        env,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.checked = False
            self.verdict.setText(error)
            return

        family, metadata, tools, extra = data

        target = self.family()
        version = self.release.currentText()

        real = metadata.get(
            "VERSION_ID",
            ""
        )

        rows = []
        issues = []

        def check(label, ok, detail):
            rows.append((
                label,
                "OK" if ok else "À corriger",
                detail
            ))

            if not ok:
                issues.append(detail)

        check(
            "Famille WSL",
            family == target,
            env + " : " + family
        )

        if target == "Debian":
            check(
                "Version Debian",
                version in (
                    real,
                    metadata.get(
                        "VERSION_CODENAME",
                        ""
                    )
                ),
                "Version WSL : " + real
            )

        if target == "Fedora":
            check(
                "Version Fedora",
                version == real,
                "Version WSL : " + real
            )

        for tool, package, state in tools:
            check(
                tool,
                state == "Présent",
                package + " : " + state
            )

        if target == "Arch Linux":
            check(
                "Profil releng",
                "présent" in extra,
                extra
            )

        check(
            "Construction ISO",
            target in ("Debian", "Arch Linux"),
            (
                "Expérimentale"
                if target in ("Debian", "Arch Linux")
                else "Non implémentée"
            )
        )

        self.fill(
            self.check_table,
            rows
        )

        self.checked = not issues

        if self.checked:
            self.verdict.setText(
                "✓ Vérification technique réussie"
            )
        else:
            self.verdict.setText(
                "⚠ "
                + str(len(issues))
                + " point(s) à corriger"
            )

        self.verify_log.setPlainText(
            "\n".join(issues)
            if issues
            else (
                "Prérequis détectés.\n"
                "L'analyse des dépendances et le test "
                "d'amorçage restent nécessaires."
            )
        )

    # ========================================================
    # ANALYSE
    # ========================================================

    def analyze(self):
        env = self.project_wsl()

        if not env:
            return

        revision = self.revision
        family = self.family()
        packages = self.packages()

        self.verify_log.setPlainText(
            "Analyse des dépendances..."
        )

        self.job(
            "simulate",
            (env, family, packages),
            lambda data, error:
                self.analyze_done(
                    revision,
                    family,
                    packages,
                    data,
                    error
                )
        )

    def analyze_done(
        self,
        revision,
        family,
        packages,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.valid = False
            self.verify_log.setPlainText(error)
            return

        output, stderr, code = data

        self.valid, status = assess(
            family,
            output,
            stderr,
            code
        )

        self.solution = parse_transaction(
            family,
            output,
            packages
        )

        rows = []

        for name, value in sorted(
            self.solution.items()
        ):
            rows.append((
                name,
                value["version"],
                value["status"],
                human(value["size"])
            ))

        self.fill(
            self.package_table,
            rows
        )

        size = estimate(
            self.solution
        )

        self.iso_summary.setText(
            family
            + "  |  "
            + str(len(self.solution))
            + " paquets  |  "
            + "Estimation ISO : "
            + size
            + "\n"
            + status
        )

        self.verify_log.setPlainText(
            "Simulation indicative sur WSL existant.\n"
            + status
            + "\nCode : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

        if not self.valid:
            self.warn(
                "Simulation en échec. Consulte le journal."
            )

    # ========================================================
    # CREATION ISO
    # ========================================================

    def create_iso(self):
        family = self.family()

        if family not in (
            "Debian",
            "Arch Linux"
        ):
            self.warn(
                "Construction ISO non implémentée "
                "pour " + family
            )
            return

        if not self.checked:
            self.warn(
                "Effectue la vérification des prérequis."
            )

            self.tabs.setCurrentIndex(3)
            return

        if not self.valid:
            self.warn(
                "Effectue l'analyse des dépendances."
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
            self.warn(
                "Le dossier de destination doit être vide."
            )
            return

        if not self.ask(
            "Construire une ISO "
            + family
            + " dans "
            + env
            + " ?\n\n"
            "Prévoir plusieurs Go libres.\n"
            "BIOS, UEFI et Ventoy ne sont pas garantis."
        ):
            return

        self.iso_log.setPlainText(
            "Construction ISO en cours..."
        )

        self.job(
            "build",
            (
                env,
                family,
                self.release.currentText(),
                self.packages(),
                folder
            ),
            self.build_done
        )

    def build_done(self, data, error):
        if error:
            self.iso_log.setPlainText(
                "ÉCHEC\n" + error
            )

            self.warn(
                "Construction échouée. "
                "Consulte le journal."
            )
            return

        files, report = data

        self.iso_log.setPlainText(
            json.dumps(
                files,
                indent=2,
                ensure_ascii=False
            )
            + "\n\n"
            "Boot BIOS/UEFI et Ventoy : non testés.\n\n"
            + report[-10000:]
        )

        self.info(
            "ISO produite.\n"
            "Teste son démarrage dans une VM "
            "puis avec Ventoy."
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":
    application = QApplication(sys.argv)
    application.setStyle("Fusion")

    window = App()
    window.show()

    sys.exit(application.exec())
