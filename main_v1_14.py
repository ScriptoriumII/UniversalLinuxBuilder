import sys
import re
import shlex
import json
import datetime
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QTextEdit, QFileDialog,
    QMessageBox, QInputDialog, QGroupBox, QHeaderView,
    QSplitter
)

VERSION = "1.14"

FAMILIES = [
    "Debian", "Fedora", "Arch Linux", "Gentoo", "Slackware"
]

COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#294172",
    "Arch Linux": "#1793D1",
    "Gentoo": "#54487A",
    "Slackware": "#455A64"
}

MARKS = {
    "Debian": "D",
    "Fedora": "f",
    "Arch Linux": "A",
    "Gentoo": "g",
    "Slackware": "S"
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
        "live-boot", "live-config",
        "linux-image-amd64", "network-manager"
    ],
    "Fedora": ["kernel", "NetworkManager"],
    "Arch Linux": ["base", "linux", "networkmanager"],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
        "net-misc/networkmanager"
    ],
    "Slackware": ["kernel-generic", "networkmanager"]
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
        "Xfce": [
            "xfce4-session", "xfce4-panel"
        ]
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


# ============================================================
# UTILITAIRES
# ============================================================

def clean(text):
    return ANSI.sub("", text).replace("\r", "\n").replace("\x08", "")


def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return clean(data.decode("utf-16", "replace"))

    if b"\x00" in data[:100]:
        return clean(
            data.decode("utf-16-le", "replace").lstrip("\ufeff")
        )

    return clean(data.decode("utf-8", "replace"))


def run(argv, timeout=300):
    process = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        creationflags=getattr(
            subprocess, "CREATE_NO_WINDOW", 0
        )
    )

    return (
        decode(process.stdout),
        decode(process.stderr),
        process.returncode
    )


def wsl(env, script, timeout=300, root=False):
    command = ["wsl.exe", "-d", env]

    if root:
        command += ["-u", "root"]

    command += ["--exec", "/bin/sh", "-lc", script]

    return run(command, timeout)


def installed():
    output, error, code = run(
        ["wsl.exe", "--list", "--quiet"], 60
    )

    if code:
        raise RuntimeError(error or output)

    return [
        name.strip().lstrip("\ufeff")
        for name in output.splitlines()
        if name.strip()
    ]


def catalog():
    output, error, code = run(
        ["wsl.exe", "--list", "--online"], 90
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
            if match.group(1).lower() not in ("name", "nom"):
                rows.append(match.groups())

    return rows, output


def detect(env):
    output, error, code = wsl(
        env, "cat /etc/os-release", 60
    )

    if code:
        raise RuntimeError(error or output)

    data = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"')

    ident = data.get("ID", "").lower()

    family = {
        "debian": "Debian",
        "fedora": "Fedora",
        "arch": "Arch Linux",
        "archlinux": "Arch Linux",
        "gentoo": "Gentoo",
        "slackware": "Slackware"
    }.get(ident, "Inconnue (" + ident + ")")

    return family, data


# ============================================================
# VERIFICATION DES PREREQUIS
# ============================================================

def prereq(env):
    family, metadata = detect(env)

    if family not in TOOLS:
        return family, metadata, [], ""

    commands = []

    for name, package in TOOLS[family]:
        quoted = shlex.quote(name)

        commands.append(
            "command -v " + quoted
            + " >/dev/null 2>&1 && echo "
            + shlex.quote(name + ":OK")
            + " || echo "
            + shlex.quote(name + ":MISSING")
        )

    output, error, code = wsl(
        env, "; ".join(commands), 90
    )

    if code:
        raise RuntimeError(error or output)

    flags = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.split(":", 1)
            flags[name] = state == "OK"

    rows = []

    for name, package in TOOLS[family]:
        state = "Présent" if flags.get(name) else "Absent"
        rows.append((name, package, state))

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

    args = " ".join(map(shlex.quote, missing))

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
            "pacman --noconfirm -Syu --needed " + args
        )

    else:
        raise RuntimeError(
            "Installation automatique non prise en charge pour "
            + family
        )

    return family, command, wsl(
        env, command, 3600, True
    )


def update_repos(env):
    family, metadata = detect(env)

    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update"
        ),
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": "pacman --noconfirm -Syu",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    if family not in commands:
        raise RuntimeError("Famille inconnue")

    command = commands[family]

    return family, command, wsl(
        env, command, 3600, True
    )


# ============================================================
# RECHERCHE D'APPLICATIONS
# ============================================================

def search(env, family, query):
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

        if (
            name
            and SAFE.fullmatch(name)
            and name not in seen
        ):
            seen.add(name)

            rows.append((
                name,
                version,
                description[:170]
            ))

    return rows[:600]


# ============================================================
# SIMULATION DES DEPENDANCES
# ============================================================

def simulate(env, family, packages):
    args = " ".join(map(shlex.quote, packages))

    commands = {
        "Debian": (
            "LC_ALL=C apt-get -s install " + args
        ),
        "Fedora": (
            "LC_ALL=C dnf5 --assumeno install " + args
        ),
        "Arch Linux": (
            'LC_ALL=C pacman -Sp '
            '--print-format "%n|%v|%s" ' + args
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend --verbose --tree "
            + args
        ),
        "Slackware": (
            'echo "Slackware : pas de solveur natif de dépendances"'
        )
    }

    return wsl(env, commands[family], 600)


def parse_size(value):
    match = re.search(
        r"([\d.,]+)\s*(B|KiB|MiB|GiB)",
        value,
        re.I
    )

    if not match:
        return None

    try:
        number = float(
            match.group(1).replace(",", ".")
        )

        factors = {
            "b": 1,
            "kib": 1024,
            "mib": 1024 ** 2,
            "gib": 1024 ** 3
        }

        return int(
            number * factors[match.group(2).lower()]
        )

    except ValueError:
        return None


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
                    "status": "Téléchargement"
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

        has_table = re.search(
            r"(?m)^\s*Package\s+Arch\s+Version",
            text
        )

        has_summary = re.search(
            r"Transaction Summary|Total download size",
            text,
            re.I
        )

        has_refusal = re.search(
            r"Operation aborted|Operation cancelled|"
            r"Operation canceled|Is this ok",
            text,
            re.I
        )

        if has_table and has_summary and has_refusal:
            return True, "Aperçu DNF5 obtenu (--assumeno)"

    return False, "Erreur de simulation : code " + str(code)


def estimate(rows):
    values = [
        value["size"]
        for value in rows.values()
        if value["size"] is not None
    ]

    if not values:
        return "Indisponible (tailles non fournies)"

    coverage = len(values) / max(len(rows), 1)

    if coverage < 0.35:
        return (
            f"Insuffisant : {human(sum(values))} connus "
            f"({len(values)}/{len(rows)})"
        )

    size = sum(values) / coverage

    minimum = int(
        size * 0.8 + 650 * 1024 ** 2
    )

    maximum = int(
        size * 2 + 1700 * 1024 ** 2
    )

    return (
        f"{human(minimum)} à {human(maximum)} "
        "(indicatif)"
    )


# ============================================================
# CONSTRUCTION ISO EXPERIMENTALE
# ============================================================

def build(env, family, release, packages, target):
    if family not in ("Debian", "Arch Linux"):
        raise RuntimeError(
            "Chaîne ISO non intégrée pour " + family
        )

    actual, metadata, checks, extra = prereq(env)

    if actual != family:
        raise RuntimeError(
            "WSL incompatible : " + actual
        )

    missing = [
        package
        for _, package, state in checks
        if state == "Absent"
    ]

    if missing:
        raise RuntimeError(
            "Outils absents : " + ", ".join(missing)
        )

    if family == "Arch Linux" and "absent" in extra:
        raise RuntimeError("Profil releng absent")

    folder = Path(target)

    if any(folder.iterdir()):
        raise RuntimeError(
            "Le dossier de destination doit être vide"
        )

    work = (
        "/var/tmp/ulb-"
        + datetime.datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )
    )

    quoted_work = shlex.quote(work)

    args = " ".join(
        map(shlex.quote, packages)
    )

    if family == "Debian":
        script = (
            "set -eu; "
            "mkdir -p " + quoted_work + "; "
            "cd " + quoted_work + "; "
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
            "mkdir -p " + quoted_work + "; "
            "cp -a /usr/share/archiso/configs/releng "
            + quoted_work + "/profile; "
            "cd " + quoted_work + "; "
            'printf "%s\\n" ' + args
            + " >> profile/packages.x86_64; "
            "sort -u profile/packages.x86_64 "
            "-o profile/packages.x86_64; "
            "mkdir -p out work; "
            "mkarchiso -v -w work -o out profile"
        )

    output, error, code = wsl(
        env, script, 7200, True
    )

    report = (
        f"Famille: {family}\n"
        f"WSL: {env}\n"
        f"Workspace: {work}\n"
        f"Code: {code}\n\n"
        f"{output}\n{error}"
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
        "find " + quoted_work
        + ' -type f -name "*.iso" -print',
        90,
        True
    )

    if code or not paths.strip():
        raise RuntimeError(
            "Aucune ISO produite ; voir build_report.txt"
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
                    "wsl.exe", "-d", env,
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
                "Copie échouée : "
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
            "ISO9660": (
                len(signature) >= 6
                and signature[1:6] == b"CD001"
            ),
            "boot_verifie": False,
            "ventoy_verifie": False
        })

    return copied, report


# ============================================================
# TACHES EN ARRIERE-PLAN
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

            elif action == "install_wsl":
                result = run(
                    [
                        "wsl.exe", "--install",
                        "--distribution", args[0],
                        "--no-launch"
                    ],
                    1800
                )

            elif action == "delete_wsl":
                result = run(
                    [
                        "wsl.exe", "--unregister",
                        args[0]
                    ],
                    900
                )

            elif action == "search":
                result = search(*args)

            elif action == "simulate":
                result = simulate(*args)

            elif action == "build":
                result = build(*args)

            else:
                raise RuntimeError("Action inconnue")

            self.done.emit(result, "")

        except Exception as exc:
            self.done.emit(None, str(exc))


# ============================================================
# THEMES
# ============================================================

DARK = """
QWidget {
    background: #151e2c;
    color: #edf3fa;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #202e42;
    border: 1px solid #465d78;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #304d70;
    border: 1px solid #5b7898;
    border-radius: 5px;
    padding: 8px;
}
QPushButton:hover {
    background: #416991;
}
QTabBar::tab {
    padding: 11px 18px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #6cb0ff;
}
QTableWidget {
    alternate-background-color: #293b53;
    gridline-color: transparent;
}
QHeaderView::section {
    background: #37516f;
    padding: 8px;
    border-right: 1px solid #536a83;
}
QGroupBox {
    border: 1px solid #455a74;
    margin-top: 10px;
    padding-top: 9px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
"""

LIGHT = """
QWidget {
    background: #f5f7fa;
    color: #172438;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: white;
    border: 1px solid #bfccdc;
    border-radius: 5px;
    padding: 5px;
}
QPushButton {
    background: #e0eaf6;
    border: 1px solid #aebed1;
    border-radius: 5px;
    padding: 8px;
}
QPushButton:hover {
    background: #c7dcf4;
}
QTabBar::tab {
    padding: 11px 18px;
}
QTabBar::tab:selected {
    border-bottom: 3px solid #2979dc;
}
QTableWidget {
    alternate-background-color: #edf3fa;
    gridline-color: transparent;
}
QHeaderView::section {
    background: #d9e6f3;
    padding: 8px;
    border-right: 1px solid #b8c8d9;
}
QGroupBox {
    border: 1px solid #bfccdc;
    margin-top: 10px;
    padding-top: 9px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
}
"""


# ============================================================
# PICTOGRAMMES DES DISTRIBUTIONS
# ============================================================

def emblem(family, size=48):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )

    painter.setBrush(
        QColor(COLORS.get(family, "#566879"))
    )

    painter.setPen(
        QPen(QColor("#d5e7f6"), 1)
    )

    painter.drawRoundedRect(
        2, 2,
        size - 4,
        size - 4,
        size * 0.22,
        size * 0.22
    )

    font = QFont(
        "Segoe UI",
        max(13, int(size * 0.47))
    )
    font.setBold(True)

    painter.setFont(font)
    painter.setPen(QColor("white"))

    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        MARKS.get(family, "?")
    )

    painter.end()

    return pixmap


# ============================================================
# INTERFACE PRINCIPALE
# ============================================================

class App(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.14"
        )
        self.resize(1440, 930)

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

        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)

        top = QHBoxLayout()

        self.brand = QLabel()
        self.brand.setFixedSize(58, 58)
        top.addWidget(self.brand)

        text = QVBoxLayout()

        title = QLabel(
            "Universal Linux Builder  |  v1.14"
        )
        title.setStyleSheet(
            "font-size:22px;font-weight:bold"
        )

        text.addWidget(title)

        self.current = QLabel("Projet : Debian")
        text.addWidget(self.current)

        top.addLayout(text)
        top.addStretch()

        top.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems(["Sombre", "Clair"])
        self.theme.currentTextChanged.connect(
            self.apply_style
        )

        top.addWidget(self.theme)
        main.addLayout(top)

        self.steps = QLabel(
            "01 Distribution   →   "
            "02 Système   →   "
            "03 Applications   →   "
            "04 Vérification   →   "
            "05 ISO"
        )

        self.steps.setStyleSheet(
            "font-size:13px;"
            "font-weight:bold;"
            "padding:8px"
        )

        main.addWidget(self.steps)

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
        main.addWidget(self.status)

        self.apply_style()
        self.change_family()

    def apply_style(self, *_):
        self.setStyleSheet(
            DARK
            if self.theme.currentText() == "Sombre"
            else LIGHT
        )

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            16, 16, 16, 16
        )

        self.tabs.addTab(widget, name)
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
            0, len(headers)
        )

        table.setHorizontalHeaderLabels(headers)

        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(31)

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
                "Une opération WSL est déjà en cours."
            )
            return

        worker = Worker(action, *args)
        self.worker = worker

        self.status.setText(
            "Opération en cours : " + action
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
        return self.family_box.currentText()

    def project_env(self):
        return self.mapping.get(
            self.family(), ""
        )

    # --------------------------------------------------------
    # BANDEAU DE DISTRIBUTION
    # --------------------------------------------------------

    def banner(self, layout):
        row = QHBoxLayout()

        label = QLabel()
        label.setMinimumHeight(42)

        label.setStyleSheet(
            "font-size:15px;font-weight:bold"
        )

        row.addWidget(label)
        row.addStretch()

        layout.addLayout(row)

        self.banners.append(label)

    def update_banners(self):
        family = self.family()

        self.brand.setPixmap(
            emblem(family, 52)
        )

        self.current.setText(
            "Projet cible : "
            + family
            + "  •  "
            + self.release.currentText()
            + "  |  WSL : "
            + (self.project_env() or "non associé")
        )

        for label in self.banners:
            label.setText(
                "◆ "
                + family
                + "  —  "
                + self.release.currentText()
            )

    def next_button(self, layout, index):
        layout.addWidget(
            self.button(
                "Continuer →",
                lambda: self.tabs.setCurrentIndex(index)
            )
        )

    # --------------------------------------------------------
    # ETAPE 1 - DISTRIBUTION
    # --------------------------------------------------------

    def tab_distribution(self):
        self.banners = []

        layout = self.page(
            "01  Distribution"
        )

        self.banner(layout)

        cards = QHBoxLayout()
        self.family_buttons = {}

        for family in FAMILIES:
            button = QPushButton()
            button.setMinimumHeight(110)

            icon = emblem(family, 64)

            button.setIcon(icon)
            button.setIconSize(icon.size())
            button.setText("\n" + family)

            button.clicked.connect(
                lambda checked=False, f=family:
                    self.family_box.setCurrentText(f)
            )

            cards.addWidget(button)
            self.family_buttons[family] = button

        layout.addLayout(cards)

        form = QFormLayout()

        self.family_box = self.combo(FAMILIES)
        self.release = self.combo()

        form.addRow(
            "Distribution cible",
            self.family_box
        )

        form.addRow(
            "Version",
            self.release
        )

        layout.addLayout(form)

        note = QLabel(
            "Sélectionne la distribution qui sera utilisée "
            "pour toutes les étapes. WSL2 est un environnement "
            "de travail, pas la distribution à amorcer."
        )

        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        self.next_button(layout, 1)

        self.family_box.currentTextChanged.connect(
            self.change_family
        )

        self.release.currentTextChanged.connect(
            self.release_changed
        )

    # --------------------------------------------------------
    # ETAPE 2 - SYSTEME
    # --------------------------------------------------------

    def tab_system(self):
        layout = self.page("02  Système")
        self.banner(layout)

        form = QFormLayout()

        self.desktop = self.combo()
        self.kernel = self.combo([
            "Stable", "LTS", "Hardened"
        ])
        self.init = self.combo()
        self.display = self.combo([
            "Wayland", "X11", "Aucun"
        ])
        self.audio = self.combo([
            "PipeWire", "PulseAudio", "ALSA", "Aucun"
        ])
        self.boot = self.combo([
            "GRUB", "Aucun"
        ])
        self.bootmode = self.combo([
            "UEFI", "BIOS"
        ])

        widgets = [
            ("Environnement de bureau", self.desktop),
            ("Noyau", self.kernel),
            ("Initialisation", self.init),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Bootloader", self.boot),
            ("Amorçage", self.bootmode)
        ]

        for name, widget in widgets:
            form.addRow(name, widget)
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

    # --------------------------------------------------------
    # ETAPE 3 - APPLICATIONS
    # --------------------------------------------------------

    def tab_apps(self):
        layout = self.page("03  Applications")
        self.banner(layout)

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher firefox, vlc, gimp..."
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
            QLabel(
                "Résultats : double-clic pour ajouter"
            )
        )

        self.results = self.table([
            "Paquet", "Version", "Description"
        ])

        self.results.setColumnWidth(0, 270)
        self.results.setColumnWidth(1, 160)

        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(self.results, 3)

        layout.addWidget(
            QLabel(
                "Sélection : double-clic pour retirer"
            )
        )

        self.selected_apps = self.table([
            "Paquet"
        ])

        self.selected_apps.cellDoubleClicked.connect(
            self.remove_app
        )

        layout.addWidget(self.selected_apps, 1)

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
        self.app_log.setMaximumHeight(105)

        layout.addWidget(self.app_log)

        self.next_button(layout, 3)

    # --------------------------------------------------------
    # ETAPE 4 - VERIFICATION
    # --------------------------------------------------------

    def tab_verify(self):
        layout = self.page("04  Vérification")
        self.banner(layout)

        self.verdict = QLabel(
            "Vérification non effectuée"
        )

        self.verdict.setWordWrap(True)
        layout.addWidget(self.verdict)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Vérifier WSL et les outils ISO",
                self.verify_project
            )
        )

        row.addWidget(
            self.button(
                "Simuler les dépendances",
                self.analyze
            )
        )

        layout.addLayout(row)

        self.check_table = self.table([
            "Contrôle", "Résultat", "Détail"
        ])

        self.check_table.setColumnWidth(0, 240)
        self.check_table.setColumnWidth(1, 160)

        layout.addWidget(self.check_table, 1)

        self.package_table = self.table([
            "Paquet", "Version", "Statut", "Taille"
        ])

        self.package_table.setColumnWidth(0, 320)
        self.package_table.setColumnWidth(1, 190)
        self.package_table.setColumnWidth(2, 180)
        self.package_table.setColumnWidth(3, 130)

        layout.addWidget(self.package_table, 3)

        self.verify_log = QTextEdit()
        self.verify_log.setReadOnly(True)

        layout.addWidget(self.verify_log, 2)

        self.next_button(layout, 4)

    # --------------------------------------------------------
    # ETAPE 5 - ISO
    # --------------------------------------------------------

    def tab_iso(self):
        layout = self.page("05  ISO")
        self.banner(layout)

        self.iso_summary = QLabel(
            "Vérifie les prérequis et analyse les paquets "
            "avant la construction."
        )

        self.iso_summary.setWordWrap(True)
        layout.addWidget(self.iso_summary)

        note = QLabel(
            "Construction expérimentale : Debian et Arch Linux. "
            "Fedora, Gentoo et Slackware : vérification uniquement. "
            "Une ISO9660 détectée ne prouve pas le démarrage "
            "BIOS/UEFI ni la compatibilité Ventoy."
        )

        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addWidget(
            self.button(
                "Créer l’ISO",
                self.create_iso
            )
        )

        self.iso_log = QTextEdit()
        self.iso_log.setReadOnly(True)

        layout.addWidget(self.iso_log)

    # --------------------------------------------------------
    # WSL2 - ENVIRONNEMENTS ET PREREQUIS
    # --------------------------------------------------------

    def tab_wsl(self):
        layout = self.page("WSL2  ⚙")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Installées",
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

        left = QGroupBox("Catalogue WSL")
        left_layout = QVBoxLayout(left)

        self.catalog_table = self.table([
            "Nom", "Description"
        ])

        self.catalog_table.setColumnWidth(0, 190)

        left_layout.addWidget(
            self.catalog_table
        )

        left_layout.addWidget(
            self.button(
                "Installer",
                self.install_wsl
            )
        )

        splitter.addWidget(left)

        right = QGroupBox("WSL installées")
        right_layout = QVBoxLayout(right)

        self.inst_table = self.table(["Nom"])

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
        splitter.setSizes([690, 430])

        layout.addWidget(splitter, 2)

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Environnement à gérer :")
        )

        self.wsl_box = self.combo()
        row.addWidget(self.wsl_box, 1)

        buttons = [
            ("Tester", self.test_wsl),
            ("Prérequis ISO", self.check_prereq),
            ("Installer les outils", self.install_prereq),
            ("Mise à jour", self.update_wsl)
        ]

        for title, callback in buttons:
            row.addWidget(
                self.button(title, callback)
            )

        layout.addLayout(row)

        self.prereq_table = self.table([
            "Outil", "Paquet", "État"
        ])

        self.prereq_table.setColumnWidth(0, 190)
        self.prereq_table.setColumnWidth(1, 250)

        layout.addWidget(self.prereq_table, 1)

        group = QGroupBox(
            "Association WSL à chaque famille de projet"
        )

        form = QFormLayout(group)
        self.mapping_boxes = {}

        for family in FAMILIES:
            row = QHBoxLayout()

            icon = QLabel()
            icon.setPixmap(
                emblem(family, 24)
            )

            row.addWidget(icon)

            combo = self.combo([
                "— Non associé —"
            ])

            row.addWidget(combo)

            form.addRow(family, row)

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.associate(f, value)
            )

            self.mapping_boxes[family] = combo

        layout.addWidget(group)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setMaximumHeight(150)

        layout.addWidget(self.wsl_log)

    # ========================================================
    # GESTION DU PROJET
    # ========================================================

    def release_changed(self, *_):
        self.invalidate()
        self.update_banners()

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
                "OpenRC", "systemd"
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

        for name, button in self.family_buttons.items():
            if name == family:
                button.setStyleSheet(
                    "border:3px solid "
                    + COLORS[name]
                    + ";"
                )
            else:
                button.setStyleSheet("")

    def associate(self, family, value):
        self.mapping[family] = (
            ""
            if value == "— Non associé —"
            else value
        )

        self.invalidate()
        self.update_banners()

    # ========================================================
    # GESTION DES DISTRIBUTIONS WSL
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
            "Distributions WSL : "
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
        self.fill(self.catalog_table, rows)

        self.wsl_log.setPlainText(
            str(len(rows))
            + " entrées du catalogue.\n"
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
            row[0]
            for row in self.catalog
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
            "Installer " + name + " avec WSL ?"
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
            "Tous les fichiers de "
            + name
            + " seront supprimés.\n"
            + "Saisis exactement : "
            + name
        )

        if (
            ok
            and typed == name
            and self.ask(
                "Confirmer la suppression irréversible de "
                + name
                + " ?"
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
                title
                + " échouée : consulte le journal."
            )
        else:
            self.refresh_wsl()

    def current_wsl(self):
        env = self.wsl_box.currentText().strip()

        if env not in self.inst or not env:
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

        confirmation = (
            "Installer les prérequis manquants dans "
            + env
            + " ?\n\n"
            "Debian : apt-get non interactif.\n"
            "Fedora : dnf5 -y.\n"
            "Arch : pacman -Syu --noconfirm "
            "(mise à niveau complète).\n"
            "Gentoo/Slackware : manuel."
        )

        if self.ask(confirmation):
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
            "Commande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n"
            + (output + "\n" + stderr)[-15000:]
        )

        if code:
            self.warn(
                "Échec : code " + str(code)
            )
        else:
            self.info(
                "Outils installés. "
                "Relance la vérification."
            )

    def update_wsl(self):
        env = self.current_wsl()

        if not env:
            return

        if self.ask(
            "Actualiser "
            + env
            + " ?\n"
            "Arch Linux : pacman -Syu "
            "(mise à niveau complète)."
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
                "Associe une distribution WSL "
                "dans l’onglet WSL2."
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
            "WSL : "
            + env
            + "\nCommande : "
            + command
            + "\nCode : "
            + str(code)
            + "\n"
            + (output + "\n" + stderr)[-15000:]
        )

        self.wsl_log.setPlainText(message)
        self.app_log.setPlainText(
            message[-3500:]
        )

        if code:
            self.warn("Actualisation échouée.")
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
                "au projet dans WSL2."
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
        rows = parse_search(family, output)

        self.fill(self.results, rows)

        self.app_log.setPlainText(
            str(len(rows))
            + " résultats, code "
            + str(code)
            + "\n"
            + (
                (stderr or output)[:2500]
                if code or not rows
                else "Double-clique pour ajouter."
            )
        )

    # ========================================================
    # CONSTRUCTION DE LA LISTE DES PAQUETS
    # ========================================================

    def packages(self):
        family = self.family()

        packages = set(BASE[family])

        packages.update(
            DESKTOP[family].get(
                self.desktop.currentText(), []
            )
        )

        packages.update(
            AUDIO[family].get(
                self.audio.currentText(), []
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
    # VERIFICATION DU PROJET
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
            self.verdict.setText(
                "Échec : " + error
            )
            self.checked = False
            return

        family, metadata, tools, extra = data

        target = self.family()
        version = self.release.currentText()
        real = metadata.get("VERSION_ID", "")

        issues = []
        rows = []

        def add_check(label, ok, detail):
            rows.append((
                label,
                "OK" if ok else "À corriger",
                detail
            ))

            if not ok:
                issues.append(detail)

        add_check(
            "Famille WSL",
            family == target,
            env
            + " : "
            + family
            + " (cible : "
            + target
            + ")"
        )

        if target == "Debian":
            add_check(
                "Version Debian",
                version in (
                    real,
                    metadata.get(
                        "VERSION_CODENAME", ""
                    )
                ),
                real
                + " / "
                + metadata.get(
                    "VERSION_CODENAME", "?"
                )
            )

        if target == "Fedora":
            add_check(
                "Version Fedora",
                version == real,
                "WSL "
                + real
                + " / cible "
                + version
            )

        for tool, package, state in tools:
            add_check(
                "Outil " + tool,
                state == "Présent",
                package + " : " + state
            )

        if target == "Arch Linux":
            add_check(
                "Profil releng",
                "présent" in extra,
                extra
            )

        supported = target in (
            "Debian", "Arch Linux"
        )

        add_check(
            "Chaîne ISO implémentée",
            supported,
            (
                target + " : expérimental"
                if supported
                else "Non implémentée"
            )
        )

        self.fill(self.check_table, rows)

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
                "Prérequis détectés. "
                "L’analyse des dépendances et "
                "le test d’amorçage restent nécessaires."
            )
        )

    # ========================================================
    # ANALYSE DES DEPENDANCES
    # ========================================================

    def analyze(self):
        env = self.project_wsl()

        if not env:
            return

        revision = self.revision
        family = self.family()
        packages = self.packages()

        self.verify_log.setPlainText(
            "Simulation en cours..."
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

        size = estimate(self.solution)

        self.iso_summary.setText(
            f"{family} | "
            f"{len(self.solution)} paquets | "
            f"Estimation ISO : {size}\n"
            f"{status}"
        )

        self.verify_log.setPlainText(
            "Simulation indicative sur WSL existant "
            "(pas un rootfs neuf).\n"
            + status
            + "\nCode : "
            + str(code)
            + "\n"
            + output
            + "\n"
            + stderr
        )

        if not self.valid:
            self.warn(
                "Simulation en échec : consulte le journal."
            )

    # ========================================================
    # CREATION ISO
    # ========================================================

    def create_iso(self):
        family = self.family()

        if family not in (
            "Debian", "Arch Linux"
        ):
            self.warn(
                "Construction ISO non implémentée pour "
                + family
                + "."
            )
            return

        if not self.checked:
            self.warn(
                "Effectue la vérification technique "
                "dans l’étape 04."
            )

            self.tabs.setCurrentIndex(3)
            return

        if not self.valid:
            self.warn(
                "Effectue la simulation des paquets "
                "dans l’étape 04."
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

        confirmation = (
            "Construire une ISO "
            + family
            + " avec "
            + env
            + " ?\n\n"
            "La construction peut prendre plusieurs heures "
            "et télécharger plusieurs Go.\n"
            "Le démarrage BIOS/UEFI/Ventoy "
            "n’est pas garanti."
        )

        if not self.ask(confirmation):
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
                self.packages(),
                folder
            ),
            self.build_done
        )

    def build_done(self, data, error):
        if error:
            self.iso_log.setPlainText(
                "ÉCHEC : " + error
            )

            self.warn(
                "Construction échouée. "
                "Consulte le journal ISO."
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
            "Boot et Ventoy : non testés.\n"
            + report[-10000:]
        )

        self.info(
            "ISO produite : teste-la dans une "
            "machine virtuelle, puis avec Ventoy."
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
