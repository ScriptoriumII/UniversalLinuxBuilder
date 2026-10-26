import sys
import json
import re
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QLabel, QCheckBox, QMenu, QFileDialog,
    QMessageBox
)

VERSION = "1.0"
ROOT = Path.home() / "Documents" / "UniversalLinuxBuilder"

# ============================================================
# DISTRIBUTIONS
# ============================================================

DISTROS = {
    "Debian": {
        "versions": ["trixie", "bookworm"],
        "arch": "amd64"
    },
    "Fedora": {
        "versions": ["43", "42"],
        "arch": "x86_64"
    },
    "Slackware": {
        "versions": ["15.0", "current"],
        "arch": "x86_64"
    },
    "Gentoo": {
        "versions": ["stable", "testing"],
        "arch": "amd64"
    },
    "Arch Linux": {
        "versions": ["rolling"],
        "arch": "x86_64"
    }
}

DESKTOPS = ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"]
KERNELS = ["Stable", "LTS", "Hardened"]

ALIASES = {
    "navigateur": "firefox",
    "video": "vlc",
    "vidéo": "vlc",
    "musique": "audacious",
    "bureautique": "libreoffice",
    "photo": "gimp",
    "courriel": "thunderbird"
}

PACKAGE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,110}$"
)

GENTOO_RE = re.compile(
    r"^[A-Za-z0-9+_.-]+/[A-Za-z0-9+_.-]+$"
)

# ============================================================
# NOYAUX LINUX
# ============================================================

# "None" signifie que le profil ne dispose pas d'un paquet
# prévalidé. On n'invente pas de nom de paquet.

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

# ============================================================
# RECHERCHE INTERNET
# ============================================================

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.0",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def catalog_url(distro, version, query):
    q = urllib.parse.quote(query)
    v = urllib.parse.quote(version)

    urls = {
        "Debian":
            f"https://packages.debian.org/search?keywords={q}&searchon=names&suite={v}",
        "Fedora":
            f"https://packages.fedoraproject.org/search?query={q}",
        "Slackware":
            f"https://slackbuilds.org/result/?search={q}",
        "Gentoo":
            f"https://packages.gentoo.org/packages/search?q={q}",
        "Arch Linux":
            f"https://archlinux.org/packages/?q={q}"
    }

    return urls[distro]


def search_online(distro, version, query):
    """
    Recherche intégrée pour Arch.
    Pour les autres familles, les catalogues sont consultables
    dans le navigateur, sans prétendre valider les paquets.
    """
    if distro != "Arch Linux":
        raise RuntimeError(
            "Recherche intégrée non disponible pour cette famille. "
            "Utiliser le bouton Catalogue Internet."
        )

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
            "name": package["pkgname"],
            "version": str(package.get("pkgver", "")),
            "repo": package.get("repo", ""),
            "description": package.get("pkgdesc") or ""
        })

    return results[:150]


class SearchWorker(QThread):
    done = Signal(object, str)

    def __init__(self, distro, version, query):
        super().__init__()
        self.distro = distro
        self.version = version
        self.query = query

    def run(self):
        try:
            result = search_online(
                self.distro,
                self.version,
                self.query
            )
            self.done.emit(result, "")
        except Exception as error:
            self.done.emit([], str(error))


# ============================================================
# GENERATION DES LISTES DE PAQUETS
# ============================================================

def build_packages(cfg):
    distro = cfg["distribution"]
    desktop = cfg["desktop"]
    audio = cfg["audio"]
    kernel = cfg["kernel"]

    packages = list(cfg["applications"])

    if distro == "Debian":
        desktops = {
            "Aucun": [],
            "GNOME": ["gnome-core", "gdm3"],
            "KDE Plasma": ["plasma-desktop", "sddm"],
            "Xfce": ["xfce4", "lightdm"],
            "Budgie": ["budgie-desktop", "lightdm"]
        }

        audio_packages = {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"],
            "ALSA": ["alsa-utils"]
        }

        packages += desktops[desktop]
        packages += audio_packages[audio]
        packages += [
            "calamares",
            "pciutils",
            "usbutils",
            "udev",
            "kmod"
        ]

        if cfg["wifi"]:
            packages += ["wpasupplicant", "wireless-regdb"]

        if cfg["bluetooth"]:
            packages += ["bluez", "blueman"]

        if cfg["printing"]:
            packages += ["cups"]

        if cfg["firmware"]:
            packages += ["firmware-linux-free"]

    elif distro == "Arch Linux":
        desktops = {
            "Aucun": [],
            "GNOME": ["gnome", "gdm"],
            "KDE Plasma": ["plasma", "sddm"],
            "Xfce": ["xfce4", "lightdm"],
            "Budgie": ["budgie-desktop", "lightdm"]
        }

        audio_packages = {
            "Aucun": [],
            "PipeWire": ["pipewire", "wireplumber"],
            "PulseAudio": ["pulseaudio"],
            "ALSA": ["alsa-utils"]
        }

        packages += desktops[desktop]
        packages += audio_packages[audio]
        packages += [
            "calamares",
            "pciutils",
            "usbutils",
            "kmod"
        ]

        if cfg["wifi"]:
            packages += ["iwd"]

        if cfg["bluetooth"]:
            packages += ["bluez", "bluez-utils"]

        if cfg["printing"]:
            packages += ["cups"]

        if cfg["firmware"]:
            packages += ["linux-firmware"]

    # Les profils Fedora, Slackware et Gentoo doivent encore
    # être complétés avec leurs listes de paquets natives.

    kernel_packages = KERNEL_PACKAGES[distro][kernel]

    if kernel_packages:
        packages += kernel_packages

    return list(dict.fromkeys(packages))


# ============================================================
# VALIDATION
# ============================================================

def validate(cfg):
    errors = []
    warnings = []

    distro = cfg["distribution"]
    desktop = cfg["desktop"]
    display = cfg["display"]
    kernel = cfg["kernel"]

    if desktop == "Aucun" and display != "Aucun":
        errors.append(
            "Sans bureau, sélectionner Affichage : Aucun."
        )

    if desktop != "Aucun" and display == "Aucun":
        errors.append(
            "Un bureau nécessite X11 ou Wayland."
        )

    if desktop == "Xfce" and display == "Wayland":
        warnings.append(
            "Xfce sous Wayland : compatibilité à valider."
        )

    if distro == "Slackware" and desktop in ("GNOME", "Budgie"):
        errors.append(
            "Profil Slackware GNOME/Budgie non disponible."
        )

    if distro == "Arch Linux":
        if desktop == "Budgie" and display == "X11":
            errors.append(
                "Budgie sur Arch : sélectionner Wayland."
            )

    kernel_packages = KERNEL_PACKAGES[distro][kernel]

    if kernel_packages is None:
        errors.append(
            f"Noyau {kernel} non pris en charge par "
            f"le profil {distro}. Aucun paquet prévalidé."
        )

    if distro == "Arch Linux":
        warnings.append(
            "Archiso : le noyau choisi doit remplacer "
            "les noyaux présents dans le profil releng."
        )

    if distro in ("Fedora", "Slackware", "Gentoo"):
        warnings.append(
            "Construction native, Calamares et pilotes "
            "non automatisés pour cette famille."
        )

    if cfg["firmware"]:
        warnings.append(
            "Les firmwares sélectionnés ne garantissent "
            "pas la prise en charge de tous les périphériques."
        )

    warnings.append(
        "Calamares doit disposer d'une configuration "
        "fonctionnelle et être testé dans une session live."
    )

    return errors, warnings


# ============================================================
# EXPORT DU PROJET
# ============================================================

def export_project(cfg, folder):
    errors, warnings = validate(cfg)

    if errors:
        raise ValueError("\n".join(errors))

    if folder.exists() and any(folder.iterdir()):
        raise ValueError(
            "Choisir un dossier vide pour éviter tout écrasement."
        )

    folder.mkdir(parents=True, exist_ok=True)

    packages = build_packages(cfg)

    for package in packages:
        valid = PACKAGE_RE.fullmatch(package)

        if cfg["distribution"] == "Gentoo":
            valid = valid or GENTOO_RE.fullmatch(package)

        if not valid:
            raise ValueError(
                f"Nom de paquet invalide : {package}"
            )

    (folder / "project_v1_0.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    (folder / "packages_v1_0.txt").write_text(
        "\n".join(packages) + "\n",
        encoding="utf-8"
    )

    distro = cfg["distribution"]

    if distro == "Debian":
        script = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v lb >/dev/null || {
    echo "Installer live-build"
    exit 1
}

[ ! -e config ] || {
    echo "Dossier déjà configuré"
    exit 1
}

mkdir -p config/package-lists
cp packages_v1_0.txt config/package-lists/ulb.list.chroot

lb config \
    --distribution __RELEASE__ \
    --architectures amd64 \
    --binary-images iso-hybrid

echo "ATTENTION : vérifier Calamares, le démarrage"
echo "graphique, les firmwares et les services."
echo "Construction expérimentale."

sudo lb build
"""
        script = script.replace(
            "__RELEASE__",
            cfg["version"]
        )

    elif distro == "Arch Linux":
        # Le profil releng contient son propre noyau.
        # Il faut retirer ses paquets noyau avant d'ajouter
        # celui demandé, pour éviter plusieurs variantes.

        script = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v mkarchiso >/dev/null || {
    echo "Installer archiso"
    exit 1
}

[ ! -e profile ] || {
    echo "Profil déjà présent"
    exit 1
}

cp -a /usr/share/archiso/configs/releng profile

# Supprimer les noyaux concurrents du profil releng.
sed -i -E \
    '/^(linux|linux-lts|linux-hardened|linux-zen|linux-headers|linux-lts-headers|linux-hardened-headers)$/d' \
    profile/packages.x86_64

cat packages_v1_0.txt >> profile/packages.x86_64

sort -u \
    profile/packages.x86_64 \
    -o profile/packages.x86_64

echo "ATTENTION : les entrées de démarrage, initramfs,"
echo "Calamares et services doivent être adaptés"
echo "au noyau sélectionné avant construction."

# Blocage volontaire : la configuration de démarrage
# releng n'est pas automatiquement adaptée au noyau.
exit 2
"""

    elif distro == "Fedora":
        script = """#!/usr/bin/env bash
set -euo pipefail
echo "Profil Fedora à compléter :"
echo "- Kickstart Live"
echo "- Paquets noyau"
echo "- Calamares"
echo "- Pilotes et firmwares"
exit 2
"""

    elif distro == "Slackware":
        script = """#!/usr/bin/env bash
set -euo pipefail
echo "Profil Slackware Liveslak à compléter :"
echo "- Sélection du noyau"
echo "- Bureau et services"
echo "- Calamares"
echo "- Firmwares"
exit 2
"""

    else:
        script = """#!/usr/bin/env bash
set -euo pipefail
echo "Profil Gentoo Catalyst à compléter :"
echo "- Configuration du noyau"
echo "- Stage et spec Catalyst"
echo "- Calamares"
echo "- Pilotes"
exit 2
"""

    script_file = folder / "build_v1_0.sh"

    script_file.write_text(
        script,
        encoding="utf-8"
    )

    (folder / "README_v1_0.txt").write_text(
        "Universal Linux Builder v1.0\n\n"
        "Distribution : " + distro + "\n"
        "Noyau : " + cfg["kernel"] + "\n\n"
        "Le script prépare une construction expérimentale.\n"
        "Calamares et les pilotes ne sont pas garantis.\n"
        "Tester impérativement l'ISO en machine virtuelle.\n",
        encoding="utf-8"
    )

    return script_file, warnings


# ============================================================
# INTERFACE GRAPHIQUE
# ============================================================

class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v" + VERSION
        )
        self.resize(1060, 820)

        self.worker = None
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_applications()
        self.make_export()

        self.distribution_changed(
            self.distribution.currentText()
        )

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, title)
        return layout

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):
        layout = self.page("Distribution")
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
        layout.addStretch()

    def distribution_changed(self, distro):
        if distro not in DISTROS:
            return

        self.version.blockSignals(True)
        self.version.clear()
        self.version.addItems(DISTROS[distro]["versions"])
        self.version.blockSignals(False)

        if hasattr(self, "desktop"):
            current = self.desktop.currentText()

            choices = (
                ["Aucun", "KDE Plasma", "Xfce"]
                if distro == "Slackware"
                else DESKTOPS
            )

            self.desktop.clear()
            self.desktop.addItems(choices)

            if current in choices:
                self.desktop.setCurrentText(current)

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
            self.selected.clear()
            self.results.clear()

    def version_changed(self, version):
        if hasattr(self, "search_version"):
            self.search_version.setCurrentText(version)

        if hasattr(self, "selected"):
            self.selected.clear()
            self.results.clear()

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def make_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo(DESKTOPS)

        self.display = self.combo([
            "Aucun",
            "X11",
            "Wayland"
        ])

        self.audio = self.combo([
            "Aucun",
            "PipeWire",
            "PulseAudio",
            "ALSA"
        ])

        self.kernel = self.combo(KERNELS)

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        form.addRow("Bureau", self.desktop)
        form.addRow("Affichage", self.display)
        form.addRow("Audio", self.audio)

        # NOUVEAU : menu juste en dessous d'Audio
        form.addRow("Noyau Linux", self.kernel)

        layout.addLayout(form)

        self.kernel_info = QLabel("")
        self.kernel_info.setWordWrap(True)

        self.kernel.currentTextChanged.connect(
            self.update_kernel_info
        )

        layout.addWidget(self.kernel_info)

        layout.addWidget(
            QLabel("ÉQUIPEMENTS")
        )

        self.options = {}

        equipment = [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", True),
            ("printing", "Imprimantes (CUPS)", False),
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
            QLabel("INSTALLATION")
        )

        self.calamares = QCheckBox(
            "Préparer l'installateur Calamares"
        )
        self.calamares.setChecked(True)

        layout.addWidget(self.calamares)
        layout.addStretch()

    def update_kernels(self):
        distro = self.distribution.currentText()

        self.kernel.blockSignals(True)
        self.kernel.clear()

        for kernel in KERNELS:
            supported = (
                KERNEL_PACKAGES[distro][kernel]
                is not None
            )

            label = (
                kernel
                if supported
                else kernel + " (non disponible)"
            )

            self.kernel.addItem(label, kernel)

            index = self.kernel.count() - 1

            model_item = self.kernel.model().item(index)

            if model_item is not None:
                model_item.setEnabled(supported)

        self.kernel.setCurrentIndex(0)
        self.kernel.blockSignals(False)

        self.update_kernel_info()

    def update_kernel_info(self):
        distro = self.distribution.currentText()
        kernel = self.kernel.currentData()

        if not kernel or distro not in KERNEL_PACKAGES:
            return

        packages = KERNEL_PACKAGES[distro][kernel]

        if packages:
            self.kernel_info.setText(
                "Paquets noyau du profil : "
                + ", ".join(packages)
            )
        else:
            self.kernel_info.setText(
                "Aucun paquet noyau prévalidé."
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
    # APPLICATIONS INTERNET
    # --------------------------------------------------------

    def make_applications(self):
        layout = self.page("Applications Internet")

        form = QFormLayout()

        self.search_distro = self.combo(list(DISTROS))
        self.search_version = self.combo([])

        self.search_distro.currentTextChanged.connect(
            self.search_distro_changed
        )

        form.addRow("Dépôts", self.search_distro)
        form.addRow("Version", self.search_version)

        layout.addLayout(form)

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "firefox, vlc, gimp, navigateur..."
        )

        self.search_button = QPushButton("Rechercher")
        self.search_button.clicked.connect(self.search)

        self.catalog_button = QPushButton(
            "Catalogue Internet"
        )
        self.catalog_button.clicked.connect(
            self.open_catalog
        )

        row.addWidget(self.query)
        row.addWidget(self.search_button)
        row.addWidget(self.catalog_button)

        layout.addLayout(row)

        layout.addWidget(
            QLabel("Résultats : double-clic pour ajouter")
        )

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(self.results)

        layout.addWidget(
            QLabel(
                "Applications sélectionnées : "
                "clic droit pour supprimer"
            )
        )

        self.selected = QListWidget()
        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.selected.customContextMenuRequested.connect(
            self.context_menu
        )

        layout.addWidget(self.selected)

        row_manual = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Nom exact du paquet (non vérifié)"
        )

        add_button = QPushButton(
            "Ajouter manuellement"
        )
        add_button.clicked.connect(self.add_manual)

        row_manual.addWidget(self.manual)
        row_manual.addWidget(add_button)

        layout.addLayout(row_manual)

        self.search_status = QLabel(
            "Arch : API intégrée. "
            "Autres distributions : catalogue Internet."
        )
        self.search_status.setWordWrap(True)

        layout.addWidget(self.search_status)

        self.search_distro_changed(
            self.search_distro.currentText()
        )

    def search_distro_changed(self, distro):
        if distro not in DISTROS:
            return

        self.search_version.clear()
        self.search_version.addItems(
            DISTROS[distro]["versions"]
        )

        self.results.clear()

        if hasattr(self, "selected"):
            self.selected.clear()

    def matching_repository(self):
        return (
            self.search_distro.currentText()
            == self.distribution.currentText()
            and
            self.search_version.currentText()
            == self.version.currentText()
        )

    def open_catalog(self):
        query = self.query.text().strip()

        if not query:
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir une application."
            )
            return

        url = catalog_url(
            self.search_distro.currentText(),
            self.search_version.currentText(),
            query
        )

        webbrowser.open(url)

    def search(self):
        query = self.query.text().strip()

        if (
            not query
            or len(query) > 80
            or any(ord(char) < 32 for char in query)
        ):
            QMessageBox.warning(
                self,
                "Recherche",
                "Recherche invalide."
            )
            return

        if not self.matching_repository():
            QMessageBox.warning(
                self,
                "Dépôts incompatibles",
                "Sélectionner la même distribution "
                "et la même version que le projet ISO."
            )
            return

        distro = self.search_distro.currentText()

        if distro != "Arch Linux":
            self.open_catalog()
            self.search_status.setText(
                "Catalogue ouvert. Les résultats ne "
                "sont pas automatiquement validés."
            )
            return

        query = ALIASES.get(query.casefold(), query)

        self.results.clear()
        self.search_button.setEnabled(False)

        self.search_status.setText(
            "Recherche Internet en cours..."
        )

        self.worker = SearchWorker(
            distro,
            self.search_version.currentText(),
            query
        )

        self.worker.done.connect(self.search_done)
        self.worker.finished.connect(
            lambda: self.search_button.setEnabled(True)
        )

        self.worker.start()

    def search_done(self, rows, error):
        if error:
            self.search_status.setText(error)
            return

        for package in rows:
            name = package["name"]

            item = QListWidgetItem(
                f'{name} | {package["version"]} | '
                f'{package["repo"]} | '
                f'{package["description"][:75]}'
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                name
            )

            self.results.addItem(item)

        self.search_status.setText(
            f"{len(rows)} résultat(s)."
        )

    def add_result(self, item):
        if not self.matching_repository():
            QMessageBox.warning(
                self,
                "Dépôts incompatibles",
                "La distribution du projet a changé."
            )
            return

        name = item.data(Qt.ItemDataRole.UserRole)
        self.add_package(name)

    def add_manual(self):
        name = self.manual.text().strip()

        valid = PACKAGE_RE.fullmatch(name)

        if self.distribution.currentText() == "Gentoo":
            valid = valid or GENTOO_RE.fullmatch(name)

        if not valid:
            QMessageBox.warning(
                self,
                "Paquet",
                "Nom de paquet invalide."
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

        self.report = QTextEdit()
        self.report.setReadOnly(True)

        layout.addWidget(self.report)

        row = QHBoxLayout()

        check_button = QPushButton(
            "Vérifier la cohérence"
        )
        check_button.clicked.connect(self.check)

        export_button = QPushButton(
            "Exporter projet et script ISO"
        )
        export_button.clicked.connect(self.export)

        row.addWidget(check_button)
        row.addWidget(export_button)

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Important : les scripts sont expérimentaux. "
                "Une ISO installable avec Calamares et pilotes "
                "n'est pas encore garantie."
            )
        )

    def config(self):
        distro = self.distribution.currentText()

        config = {
            "schema": 10,
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
            ensure_ascii=False,
            indent=2
        )

        report += "\n\nERREURS :\n"
        report += "\n".join(errors) or "Aucune erreur connue"

        report += "\n\nAVERTISSEMENTS :\n"
        report += "\n".join(warnings) or "Aucun"

        self.report.setPlainText(report)

        return not errors

    def export(self):
        if not self.check():
            QMessageBox.warning(
                self,
                "Configuration",
                "Corriger les erreurs avant export."
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier de projet vide",
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
            "Projet exporté",
            f"Fichiers créés :\n{script}\n\n"
            "Aucune ISO n'a été construite.\n\n"
            + "\n".join(warnings)
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
