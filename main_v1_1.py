import sys
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QLabel, QCheckBox, QMenu, QFileDialog,
    QMessageBox, QFrame, QSplitter
)

VERSION = "1.1"
ROOT = Path.home() / "Documents" / "UniversalLinuxBuilder"

DISTROS = {
    "Debian": {
        "versions": ["trixie", "bookworm"],
        "arch": "amd64",
        "repo_prefixes": ["debian_"]
    },
    "Fedora": {
        "versions": ["43", "42"],
        "arch": "x86_64",
        "repo_prefixes": ["fedora_"]
    },
    "Slackware": {
        "versions": ["15.0", "current"],
        "arch": "x86_64",
        "repo_prefixes": ["slackware_"]
    },
    "Gentoo": {
        "versions": ["stable", "testing"],
        "arch": "amd64",
        "repo_prefixes": ["gentoo"]
    },
    "Arch Linux": {
        "versions": ["rolling"],
        "arch": "x86_64",
        "repo_prefixes": ["arch"]
    }
}

DESKTOPS = [
    "Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"
]

KERNELS = ["Stable", "LTS", "Hardened"]

ALIASES = {
    "navigateur": "firefox",
    "vidéo": "vlc",
    "video": "vlc",
    "musique": "audacious",
    "bureautique": "libreoffice",
    "photo": "gimp",
    "courriel": "thunderbird"
}

KERNEL_PACKAGES = {
    "Debian": {
        "Stable": ["linux-image-amd64"],
        "LTS": None,
        "Hardened": None
    },
    "Fedora": {
        "Stable": ["kernel"],
        "LTS": None,
        "Hardened": None
    },
    "Slackware": {
        "Stable": None,
        "LTS": None,
        "Hardened": None
    },
    "Gentoo": {
        "Stable": ["sys-kernel/gentoo-kernel"],
        "LTS": None,
        "Hardened": None
    },
    "Arch Linux": {
        "Stable": ["linux", "linux-headers"],
        "LTS": ["linux-lts", "linux-lts-headers"],
        "Hardened": [
            "linux-hardened",
            "linux-hardened-headers"
        ]
    }
}

PACKAGE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,110}$"
)

GENTOO_RE = re.compile(
    r"^[A-Za-z0-9+_.-]+/[A-Za-z0-9+_.-]+$"
)


# ============================================================
# DESIGN
# ============================================================

LIGHT_STYLE = """
QWidget {
    background: #f4f6fa;
    color: #202936;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QMainWindow, QTabWidget::pane {
    background: #f4f6fa;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #dfe5ed;
    border-radius: 12px;
}
QLabel#title {
    font-size: 23px;
    font-weight: 700;
    color: #182536;
}
QLabel#subtitle {
    color: #617085;
    font-size: 12px;
}
QLineEdit, QComboBox, QTextEdit, QListWidget {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 8px;
    padding: 7px;
    selection-background-color: #2677db;
    selection-color: white;
}
QLineEdit:focus, QComboBox:focus,
QListWidget:focus {
    border: 1px solid #2677db;
}
QPushButton {
    background: #e8edf5;
    border: 1px solid #d5deea;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #dce6f4;
}
QPushButton:disabled {
    color: #8a94a2;
}
QPushButton#primary {
    background: #2677db;
    color: white;
    border: none;
}
QPushButton#primary:hover {
    background: #155fbc;
}
QTabBar::tab {
    padding: 12px 19px;
    border: none;
    border-bottom: 3px solid transparent;
    background: transparent;
}
QTabBar::tab:selected {
    color: #2677db;
    border-bottom: 3px solid #2677db;
    font-weight: bold;
}
QMenu {
    background: white;
    border: 1px solid #cfd8e3;
}
QMenu::item {
    padding: 8px 18px;
}
QMenu::item:selected {
    background: #dceafb;
}
"""

DARK_STYLE = """
QWidget {
    background: #151a23;
    color: #e4e9f2;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QMainWindow, QTabWidget::pane {
    background: #151a23;
}
QFrame#card {
    background: #202735;
    border: 1px solid #354153;
    border-radius: 12px;
}
QLabel#title {
    font-size: 23px;
    font-weight: 700;
    color: #f4f7ff;
}
QLabel#subtitle {
    color: #a1aec0;
    font-size: 12px;
}
QLineEdit, QComboBox, QTextEdit, QListWidget {
    background: #202735;
    color: #f0f3f9;
    border: 1px solid #435169;
    border-radius: 8px;
    padding: 7px;
    selection-background-color: #3988e8;
    selection-color: white;
}
QLineEdit:focus, QComboBox:focus,
QListWidget:focus {
    border: 1px solid #61a5ff;
}
QPushButton {
    background: #303c50;
    color: #edf2fa;
    border: 1px solid #46556d;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #40516c;
}
QPushButton:disabled {
    color: #7c889a;
}
QPushButton#primary {
    background: #2878d9;
    color: white;
    border: none;
}
QPushButton#primary:hover {
    background: #398cf1;
}
QTabBar::tab {
    padding: 12px 19px;
    border: none;
    border-bottom: 3px solid transparent;
    background: transparent;
}
QTabBar::tab:selected {
    color: #7db7ff;
    border-bottom: 3px solid #398cf1;
    font-weight: bold;
}
QMenu {
    background: #202735;
    color: white;
    border: 1px solid #435169;
}
QMenu::item {
    padding: 8px 18px;
}
QMenu::item:selected {
    background: #354d70;
}
"""


# ============================================================
# RECHERCHE INTERNET INTEGREE
# ============================================================

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.1",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=25
    ) as response:
        return json.load(response)


def search_arch(query):
    url = (
        "https://archlinux.org/packages/search/json/?q="
        + urllib.parse.quote(query)
    )

    data = fetch_json(url)
    results = []

    for package in data.get("results", []):
        if package.get("arch") not in ("x86_64", "any"):
            continue

        results.append({
            "name": package.get("pkgname", ""),
            "version": str(package.get("pkgver", "")),
            "repo": package.get("repo", ""),
            "description": package.get("pkgdesc") or "",
            "source": "Arch officiel",
            "verified": True
        })

    return results[:150]


def repology_matches(distro, repo):
    repo = str(repo).lower()

    return any(
        repo.startswith(prefix)
        for prefix in DISTROS[distro]["repo_prefixes"]
    )


def search_repology(distro, version, query):
    """
    Repology est un index tiers multi-distributions.

    Les résultats ne prouvent pas qu'un paquet est
    installable dans la version exacte sélectionnée.

    L'API peut imposer des limites de débit.
    """

    url = (
        "https://repology.org/api/v1/projects/"
        "?search=" + urllib.parse.quote(query)
    )

    data = fetch_json(url)

    if not isinstance(data, dict):
        raise RuntimeError(
            "Format de réponse Repology inattendu."
        )

    results = []

    for project_name, entries in data.items():

        if not isinstance(entries, list):
            continue

        for entry in entries:

            if not isinstance(entry, dict):
                continue

            repo = entry.get("repo", "")

            if not repology_matches(distro, repo):
                continue

            package_name = (
                entry.get("binname")
                or entry.get("visiblename")
                or project_name
            )

            if not isinstance(package_name, str):
                continue

            if distro == "Gentoo":
                # Repology n'expose pas toujours
                # l'atome category/package requis.
                # On ne transforme pas automatiquement
                # un nom simple en atome Portage.
                if "/" not in package_name:
                    continue

            elif not PACKAGE_RE.fullmatch(package_name):
                continue

            results.append({
                "name": package_name,
                "version": str(entry.get("version", "")),
                "repo": str(repo),
                "description": str(
                    entry.get("summary") or ""
                ),
                "source": "Repology (index tiers)",
                "verified": False
            })

    unique = {}

    for result in results:
        key = (result["name"], result["repo"])
        unique[key] = result

    return list(unique.values())[:150]


def search_packages(distro, version, query):
    if distro == "Arch Linux":
        return search_arch(query)

    return search_repology(distro, version, query)


class SearchWorker(QThread):
    completed = Signal(object, str)

    def __init__(self, distro, version, query):
        super().__init__()
        self.distro = distro
        self.version = version
        self.query = query

    def run(self):
        try:
            results = search_packages(
                self.distro,
                self.version,
                self.query
            )
            self.completed.emit(results, "")
        except Exception as error:
            self.completed.emit([], str(error))


# ============================================================
# PROFILS SYSTEME
# ============================================================

def build_packages(config):
    distro = config["distribution"]
    desktop = config["desktop"]
    audio = config["audio"]

    packages = list(config["applications"])

    if distro == "Debian":
        desktops = {
            "Aucun": [],
            "GNOME": ["gnome-core", "gdm3"],
            "KDE Plasma": ["plasma-desktop", "sddm"],
            "Xfce": ["xfce4", "lightdm"],
            "Budgie": ["budgie-desktop", "lightdm"]
        }

        sounds = {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"],
            "ALSA": ["alsa-utils"]
        }

        packages += desktops[desktop]
        packages += sounds[audio]
        packages += [
            "calamares",
            "pciutils",
            "usbutils",
            "udev",
            "kmod"
        ]

        if config["wifi"]:
            packages += ["wpasupplicant"]

        if config["bluetooth"]:
            packages += ["bluez", "blueman"]

        if config["printing"]:
            packages += ["cups"]

        if config["firmware"]:
            packages += ["firmware-linux-free"]

    elif distro == "Arch Linux":
        desktops = {
            "Aucun": [],
            "GNOME": ["gnome", "gdm"],
            "KDE Plasma": ["plasma", "sddm"],
            "Xfce": ["xfce4", "lightdm"],
            "Budgie": ["budgie-desktop", "lightdm"]
        }

        sounds = {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"],
            "ALSA": ["alsa-utils"]
        }

        packages += desktops[desktop]
        packages += sounds[audio]
        packages += [
            "calamares",
            "pciutils",
            "usbutils",
            "kmod"
        ]

        if config["wifi"]:
            packages += ["iwd"]

        if config["bluetooth"]:
            packages += ["bluez", "bluez-utils"]

        if config["printing"]:
            packages += ["cups"]

        if config["firmware"]:
            packages += ["linux-firmware"]

    kernel = KERNEL_PACKAGES[distro][config["kernel"]]

    if kernel:
        packages += kernel

    return list(dict.fromkeys(packages))


def validate(config):
    errors = []
    warnings = []

    distro = config["distribution"]
    desktop = config["desktop"]
    display = config["display"]
    kernel = config["kernel"]

    if desktop == "Aucun" and display != "Aucun":
        errors.append(
            "Sans bureau, l'affichage doit être Aucun."
        )

    if desktop != "Aucun" and display == "Aucun":
        errors.append(
            "Un bureau nécessite un serveur graphique."
        )

    if distro == "Slackware" and desktop in (
        "GNOME", "Budgie"
    ):
        errors.append(
            "Profil Slackware GNOME/Budgie non validé."
        )

    if (
        distro == "Arch Linux"
        and desktop == "Budgie"
        and display == "X11"
    ):
        errors.append(
            "Budgie Arch : choisir Wayland."
        )

    if KERNEL_PACKAGES[distro][kernel] is None:
        errors.append(
            f"Noyau {kernel} non disponible "
            f"dans le profil {distro}."
        )

    if distro in ("Fedora", "Slackware", "Gentoo"):
        warnings.append(
            "Profil de construction natif incomplet."
        )

    warnings.append(
        "Les résultats Repology ne sont pas une "
        "validation des dépendances."
    )

    warnings.append(
        "Calamares et les pilotes nécessitent "
        "une configuration et des tests réels."
    )

    return errors, warnings


# ============================================================
# EXPORT SECURISE
# ============================================================

def export_project(config, folder):
    errors, warnings = validate(config)

    if errors:
        raise ValueError("\n".join(errors))

    if folder.exists() and any(folder.iterdir()):
        raise ValueError(
            "Sélectionner un dossier vide."
        )

    packages = build_packages(config)

    for package in packages:
        valid = PACKAGE_RE.fullmatch(package)

        if config["distribution"] == "Gentoo":
            valid = valid or GENTOO_RE.fullmatch(package)

        if not valid:
            raise ValueError(
                f"Nom de paquet invalide : {package}"
            )

    folder.mkdir(parents=True, exist_ok=True)

    (folder / "project_v1_1.json").write_text(
        json.dumps(
            config,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    (folder / "packages_v1_1.txt").write_text(
        "\n".join(packages) + "\n",
        encoding="utf-8"
    )

    script = """#!/usr/bin/env bash
set -euo pipefail

echo "Universal Linux Builder v1.1"
echo "Projet exporté."
echo
echo "Les profils ISO ne sont pas encore validés."
echo "Aucune construction automatique n'est lancée."
echo
echo "Consulter project_v1_1.json et packages_v1_1.txt."

exit 2
"""

    script_path = folder / "build_v1_1.sh"

    script_path.write_text(
        script,
        encoding="utf-8"
    )

    return script_path, warnings


# ============================================================
# INTERFACE
# ============================================================

class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder 1.1"
        )

        self.resize(1180, 820)
        self.setMinimumSize(900, 650)

        self.worker = None
        self.active_search = None
        self.search_rows = []

        self.root_widget = QWidget()
        self.root_layout = QVBoxLayout(self.root_widget)

        self.setCentralWidget(self.root_widget)

        self.make_header()

        self.tabs = QTabWidget()
        self.root_layout.addWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_applications()
        self.make_export()

        self.statusBar().showMessage(
            "Prêt — recherche intégrée sans navigateur"
        )

        self.distribution_changed(
            self.distribution.currentText()
        )

        self.apply_theme()

    def make_header(self):
        header = QHBoxLayout()

        text_area = QVBoxLayout()

        title = QLabel(
            "Universal Linux Builder"
        )
        title.setObjectName("title")

        subtitle = QLabel(
            "v1.1  •  Création de distributions Linux personnalisées"
        )
        subtitle.setObjectName("subtitle")

        text_area.addWidget(title)
        text_area.addWidget(subtitle)

        header.addLayout(text_area)
        header.addStretch()

        header.addWidget(QLabel("Apparence"))

        self.theme = QComboBox()
        self.theme.addItems([
            "Automatique",
            "Clair",
            "Sombre"
        ])

        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        header.addWidget(self.theme)

        self.root_layout.addLayout(header)

    def apply_theme(self, *_):
        choice = self.theme.currentText()

        if choice == "Automatique":
            color = QApplication.styleHints().colorScheme()
            dark = color == Qt.ColorScheme.Dark
        else:
            dark = choice == "Sombre"

        self.setStyleSheet(
            DARK_STYLE if dark else LIGHT_STYLE
        )

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.tabs.addTab(widget, title)

        return layout

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def heading(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            "font-size: 16px; font-weight: 700;"
        )
        return label

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):
        layout = self.page("Distribution")

        layout.addWidget(
            self.heading("Distribution Linux")
        )

        form = QFormLayout()

        self.distribution = self.combo(list(DISTROS))
        self.version = self.combo([])

        self.distribution.currentTextChanged.connect(
            self.distribution_changed
        )

        self.version.currentTextChanged.connect(
            self.version_changed
        )

        form.addRow("Distribution", self.distribution)
        form.addRow("Version", self.version)

        layout.addLayout(form)

        self.distro_info = QLabel("")
        self.distro_info.setWordWrap(True)

        layout.addWidget(self.distro_info)
        layout.addStretch()

    def distribution_changed(self, distro):
        if distro not in DISTROS:
            return

        self.version.blockSignals(True)
        self.version.clear()
        self.version.addItems(
            DISTROS[distro]["versions"]
        )
        self.version.blockSignals(False)

        self.distro_info.setText(
            f"Architecture : {DISTROS[distro]['arch']}  •  "
            "Recherche de paquets directement dans l'application"
        )

        if hasattr(self, "desktop"):
            previous = self.desktop.currentText()

            choices = (
                ["Aucun", "KDE Plasma", "Xfce"]
                if distro == "Slackware"
                else DESKTOPS
            )

            self.desktop.clear()
            self.desktop.addItems(choices)

            if previous in choices:
                self.desktop.setCurrentText(previous)

            self.desktop_changed(
                self.desktop.currentText()
            )

        if hasattr(self, "kernel"):
            self.update_kernels()

        if hasattr(self, "search_distro"):
            self.search_distro.setCurrentText(distro)
            self.search_version.setCurrentText(
                self.version.currentText()
            )

        if hasattr(self, "selected"):
            self.clear_packages()

    def version_changed(self, version):
        if hasattr(self, "search_version"):
            self.search_version.setCurrentText(version)

        if hasattr(self, "selected"):
            self.clear_packages()

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def make_system(self):
        layout = self.page("Système")

        layout.addWidget(
            self.heading("Environnement système")
        )

        form = QFormLayout()

        self.desktop = self.combo(DESKTOPS)

        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])

        self.audio = self.combo([
            "Aucun", "PipeWire", "PulseAudio", "ALSA"
        ])

        self.kernel = self.combo(KERNELS)

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        self.kernel.currentIndexChanged.connect(
            self.update_kernel_info
        )

        form.addRow("Bureau", self.desktop)
        form.addRow("Affichage", self.display)
        form.addRow("Audio", self.audio)
        form.addRow("Noyau Linux", self.kernel)

        layout.addLayout(form)

        self.kernel_info = QLabel("")
        self.kernel_info.setWordWrap(True)

        layout.addWidget(self.kernel_info)

        layout.addWidget(
            self.heading("Équipements")
        )

        self.options = {}

        equipment = [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", True),
            ("printing", "Imprimantes / CUPS", False),
            (
                "firmware",
                "Firmwares et détection matérielle",
                True
            )
        ]

        for key, label, default in equipment:
            checkbox = QCheckBox(label)
            checkbox.setChecked(default)
            self.options[key] = checkbox
            layout.addWidget(checkbox)

        layout.addWidget(
            self.heading("Installation")
        )

        self.calamares = QCheckBox(
            "Préparer Calamares"
        )
        self.calamares.setChecked(True)

        layout.addWidget(self.calamares)
        layout.addStretch()

    def update_kernels(self):
        distro = self.distribution.currentText()

        self.kernel.blockSignals(True)
        self.kernel.clear()

        for kernel in KERNELS:
            packages = KERNEL_PACKAGES[distro][kernel]

            label = (
                kernel
                if packages is not None
                else kernel + " — indisponible"
            )

            self.kernel.addItem(label, kernel)

            index = self.kernel.count() - 1
            item = self.kernel.model().item(index)

            if item is not None:
                item.setEnabled(packages is not None)

        self.kernel.setCurrentIndex(0)
        self.kernel.blockSignals(False)

        self.update_kernel_info()

    def update_kernel_info(self, *_):
        distro = self.distribution.currentText()
        kernel = self.kernel.currentData()

        if not kernel:
            return

        packages = KERNEL_PACKAGES[distro][kernel]

        if packages:
            self.kernel_info.setText(
                "Paquets du noyau : " + ", ".join(packages)
            )
        else:
            self.kernel_info.setText(
                "Aucun profil de noyau prévalidé."
            )

    def desktop_changed(self, desktop):
        if desktop == "Aucun":
            self.display.setCurrentText("Aucun")

        elif desktop == "Xfce":
            self.display.setCurrentText("X11")

        elif (
            desktop == "Budgie"
            and self.distribution.currentText() == "Arch Linux"
        ):
            self.display.setCurrentText("Wayland")

        elif self.display.currentText() == "Aucun":
            self.display.setCurrentText("Wayland")

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def make_applications(self):
        layout = self.page("Applications")

        layout.addWidget(
            self.heading("Recherche dans les dépôts Linux")
        )

        form = QFormLayout()

        self.search_distro = self.combo(list(DISTROS))
        self.search_version = self.combo([])

        self.search_distro.currentTextChanged.connect(
            self.search_distro_changed
        )

        form.addRow("Distribution", self.search_distro)
        form.addRow("Branche", self.search_version)

        layout.addLayout(form)

        search_row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher Firefox, VLC, GIMP..."
        )

        self.query.returnPressed.connect(
            self.search
        )

        self.search_button = QPushButton(
            "Rechercher"
        )
        self.search_button.setObjectName("primary")
        self.search_button.clicked.connect(
            self.search
        )

        search_row.addWidget(self.query)
        search_row.addWidget(self.search_button)

        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)

        results_layout.addWidget(
            self.heading("Résultats")
        )

        results_layout.addWidget(
            QLabel("Double-clic pour ajouter")
        )

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(
            self.add_result
        )

        results_layout.addWidget(self.results)

        selected_panel = QWidget()
        selected_layout = QVBoxLayout(selected_panel)

        selected_layout.addWidget(
            self.heading("Applications à installer")
        )

        selected_layout.addWidget(
            QLabel("Clic droit pour supprimer")
        )

        self.selected = QListWidget()

        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.selected.customContextMenuRequested.connect(
            self.context_menu
        )

        selected_layout.addWidget(self.selected)

        splitter.addWidget(results_panel)
        splitter.addWidget(selected_panel)

        splitter.setSizes([600, 400])

        layout.addWidget(splitter, 1)

        manual_row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Ajouter un paquet manuellement (non vérifié)"
        )

        manual_button = QPushButton("Ajouter")
        manual_button.clicked.connect(
            self.add_manual
        )

        manual_row.addWidget(self.manual)
        manual_row.addWidget(manual_button)

        layout.addLayout(manual_row)

        self.search_status = QLabel(
            "Prêt. Les recherches s'affichent ici."
        )
        self.search_status.setWordWrap(True)

        layout.addWidget(self.search_status)

        self.search_distro_changed(
            self.search_distro.currentText()
        )

    def clear_packages(self):
        self.results.clear()
        self.selected.clear()
        self.search_rows = []

    def search_distro_changed(self, distro):
        if distro not in DISTROS:
            return

        self.search_version.clear()
        self.search_version.addItems(
            DISTROS[distro]["versions"]
        )

        if hasattr(self, "selected"):
            self.clear_packages()

    def matching_repository(self):
        return (
            self.search_distro.currentText()
            == self.distribution.currentText()
            and
            self.search_version.currentText()
            == self.version.currentText()
        )

    def search(self):
        query = self.query.text().strip()

        if (
            not query
            or len(query) > 80
            or any(ord(c) < 32 for c in query)
        ):
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir un nom d'application valide."
            )
            return

        if not self.matching_repository():
            QMessageBox.warning(
                self,
                "Dépôts incompatibles",
                "Choisir la même distribution et "
                "la même version que le projet ISO."
            )
            return

        query = ALIASES.get(
            query.casefold(),
            query
        )

        self.results.clear()
        self.search_rows = []

        self.search_button.setEnabled(False)
        self.search_status.setText(
            "Recherche Internet en cours..."
        )

        distro = self.search_distro.currentText()
        version = self.search_version.currentText()

        self.active_search = (distro, version)

        self.worker = SearchWorker(
            distro, version, query
        )

        self.worker.completed.connect(
            self.search_done
        )

        self.worker.finished.connect(
            lambda: self.search_button.setEnabled(True)
        )

        self.worker.start()

    def search_done(self, rows, error):
        if self.active_search != (
            self.search_distro.currentText(),
            self.search_version.currentText()
        ):
            self.search_status.setText(
                "Résultats ignorés : la distribution a changé."
            )
            return

        if error:
            self.search_status.setText(
                "Erreur de recherche : " + error
            )
            return

        self.search_rows = rows

        for package in rows:
            name = package["name"]
            version = package["version"]
            repo = package["repo"]
            description = package["description"]

            item = QListWidgetItem(
                f"{name}  •  {version}\n"
                f"{repo}  —  {description[:100]}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                package
            )

            item.setToolTip(
                f"Source : {package['source']}\n"
                f"Dépôt : {repo}\n"
                f"Version : {version}\n"
                f"Description : {description}"
            )

            self.results.addItem(item)

        source = (
            "API officielle Arch"
            if self.search_distro.currentText() == "Arch Linux"
            else "index Repology (tiers)"
        )

        self.search_status.setText(
            f"{len(rows)} résultat(s) — {source}. "
            "Les paquets doivent être validés "
            "pour la version cible avant construction."
        )

    def add_result(self, item):
        if not self.matching_repository():
            QMessageBox.warning(
                self,
                "Dépôts incompatibles",
                "La distribution du projet a changé."
            )
            return

        package = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not package:
            return

        name = package["name"]

        if not package["verified"]:
            response = QMessageBox.question(
                self,
                "Paquet non vérifié",
                f"Le paquet « {name} » provient "
                "d'un index tiers.\n\n"
                "Son installation n'est pas confirmée "
                "pour la version sélectionnée.\n\n"
                "L'ajouter comme paquet non vérifié ?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if response != QMessageBox.StandardButton.Yes:
                return

        self.add_package(name)

    def add_manual(self):
        name = self.manual.text().strip()

        valid = PACKAGE_RE.fullmatch(name)

        if self.distribution.currentText() == "Gentoo":
            valid = valid or GENTOO_RE.fullmatch(name)

        if not valid:
            QMessageBox.warning(
                self,
                "Paquet invalide",
                "Vérifier le nom du paquet."
            )
            return

        self.add_package(name)
        self.manual.clear()

    def add_package(self, name):
        existing = [
            self.selected.item(i).text()
            for i in range(self.selected.count())
        ]

        if name not in existing:
            self.selected.addItem(name)

            self.statusBar().showMessage(
                f"Paquet ajouté : {name}",
                5000
            )

    def context_menu(self, position):
        item = self.selected.itemAt(position)

        if item is None:
            return

        menu = QMenu(self)

        delete_action = menu.addAction(
            "Supprimer de l'installation"
        )

        chosen = menu.exec(
            self.selected.mapToGlobal(position)
        )

        if chosen == delete_action:
            self.selected.takeItem(
                self.selected.row(item)
            )

    # --------------------------------------------------------
    # PROJET / ISO
    # --------------------------------------------------------

    def make_export(self):
        layout = self.page("Projet / ISO")

        layout.addWidget(
            self.heading("Configuration de l'image Linux")
        )

        self.report = QTextEdit()
        self.report.setReadOnly(True)

        layout.addWidget(self.report)

        buttons = QHBoxLayout()

        check_button = QPushButton(
            "Vérifier la configuration"
        )
        check_button.clicked.connect(self.check)

        export_button = QPushButton(
            "Exporter le projet"
        )
        export_button.setObjectName("primary")
        export_button.clicked.connect(self.export)

        buttons.addWidget(check_button)
        buttons.addWidget(export_button)

        layout.addLayout(buttons)

        note = QLabel(
            "La v1.1 prépare le projet et les listes de paquets. "
            "Elle ne construit pas encore automatiquement une "
            "ISO installable avec Calamares."
        )
        note.setWordWrap(True)

        layout.addWidget(note)

    def config(self):
        distro = self.distribution.currentText()

        config = {
            "schema": 11,
            "app_version": VERSION,
            "distribution": distro,
            "version": self.version.currentText(),
            "architecture": DISTROS[distro]["arch"],
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentData(),
            "calamares": self.calamares.isChecked(),
            "applications": [
                self.selected.item(i).text()
                for i in range(self.selected.count())
            ]
        }

        for key, checkbox in self.options.items():
            config[key] = checkbox.isChecked()

        return config

    def check(self):
        config = self.config()

        errors, warnings = validate(config)

        report = json.dumps(
            config,
            indent=2,
            ensure_ascii=False
        )

        report += "\n\nERREURS\n"
        report += "\n".join(errors) or "Aucune erreur connue"

        report += "\n\nAVERTISSEMENTS\n"
        report += "\n".join(warnings) or "Aucun"

        self.report.setPlainText(report)

        return not errors

    def export(self):
        if not self.check():
            QMessageBox.warning(
                self,
                "Configuration",
                "Corriger les erreurs avant l'export."
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier vide",
            str(ROOT)
        )

        if not folder:
            return

        try:
            script, warnings = export_project(
                self.config(),
                Path(folder)
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Export",
                str(error)
            )
            return

        QMessageBox.information(
            self,
            "Export terminé",
            f"Projet enregistré :\n{script}\n\n"
            "Aucune ISO n'a été construite."
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())
