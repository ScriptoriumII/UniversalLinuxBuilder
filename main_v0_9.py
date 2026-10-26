import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
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
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QLabel,
    QCheckBox,
    QMenu,
    QFileDialog,
    QMessageBox
)


VERSION = "0.9"

ROOT = (
    Path.home()
    / "Documents"
    / "UniversalLinuxBuilder"
)


# ============================================================
# DISTRIBUTIONS
# ============================================================

DISTROS = {
    "Debian": {
        "versions": ["trixie", "bookworm"],
        "arch": "amd64",
        "engine": "live-build"
    },

    "Fedora": {
        "versions": ["43", "42"],
        "arch": "x86_64",
        "engine": "kickstart"
    },

    "Slackware": {
        "versions": ["15.0", "current"],
        "arch": "x86_64",
        "engine": "liveslak"
    },

    "Gentoo": {
        "versions": ["stable", "testing"],
        "arch": "amd64",
        "engine": "catalyst"
    },

    "Arch Linux": {
        "versions": ["rolling"],
        "arch": "x86_64",
        "engine": "archiso"
    }
}


DESKTOPS = [
    "Aucun",
    "GNOME",
    "KDE Plasma",
    "Xfce",
    "Budgie"
]


ALIASES = {
    "navigateur": "firefox",
    "video": "vlc",
    "musique": "audacious",
    "bureautique": "libreoffice",
    "photo": "gimp",
    "courriel": "thunderbird"
}


PKG = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,110}$"
)

ATOM = re.compile(
    r"^[A-Za-z0-9+_.-]+/[A-Za-z0-9+_.-]+$"
)


# ============================================================
# RECHERCHE INTERNET
# ============================================================

def fetch_json(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/0.9",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=18
    ) as response:

        return json.load(response)


def search_online(distro, version, query):

    q = urllib.parse.quote(query)

    items = []

    if distro == "Arch Linux":

        url = (
            "https://archlinux.org/packages/"
            "search/json/?q=" + q
        )

        data = fetch_json(url)

        for package in data.get("results", []):

            if package.get("arch") not in (
                "x86_64",
                "any"
            ):
                continue

            items.append((
                package["pkgname"],
                str(package.get("pkgver", "")),
                package.get("pkgdesc") or "",
                package.get("repo", "")
            ))

    elif distro == "Debian":

        # Attention :
        # Cette API référence des paquets sources.
        # Elle ne confirme pas qu'un paquet binaire
        # est installable dans la version sélectionnée.

        url = (
            "https://sources.debian.org/"
            "api/search/" + q + "/"
        )

        data = fetch_json(url)

        results = data.get("results", {})

        for category in ("exact", "other"):

            for package in results.get(category, []):

                if not isinstance(package, dict):
                    continue

                name = package.get("name")

                if name:

                    items.append((
                        name,
                        "",
                        "Paquet source : installation non vérifiée",
                        "sources.debian.org"
                    ))

    elif distro == "Fedora":

        raise RuntimeError(
            "Recherche Fedora non disponible dans "
            "cette version sans métadonnées DNF "
            "de la version cible."
        )

    elif distro == "Slackware":

        raise RuntimeError(
            "Recherche Slackware non disponible "
            "sans index de dépôt configuré."
        )

    elif distro == "Gentoo":

        raise RuntimeError(
            "Recherche Gentoo non disponible "
            "sans backend Portage."
        )

    return items[:150]


class SearchWorker(QThread):

    done = Signal(object, str)

    def __init__(self, distro, version, query):

        super().__init__()

        self.distro = distro
        self.version = version
        self.query = query

    def run(self):

        try:

            results = search_online(
                self.distro,
                self.version,
                self.query
            )

            self.done.emit(results, "")

        except Exception as error:

            self.done.emit([], str(error))


# ============================================================
# PAQUETS SYSTEME
# ============================================================

def build_packages(config):

    distro = config["distribution"]
    desktop = config["desktop"]

    applications = list(
        config["applications"]
    )

    if distro == "Debian":

        desktops = {
            "Aucun": [],
            "GNOME": [
                "gnome-core",
                "gdm3"
            ],
            "KDE Plasma": [
                "plasma-desktop",
                "sddm"
            ],
            "Xfce": [
                "xfce4",
                "lightdm"
            ],
            "Budgie": [
                "budgie-desktop",
                "lightdm"
            ]
        }

        audio = {
            "Aucun": [],
            "PipeWire": [
                "pipewire",
                "wireplumber"
            ],
            "PulseAudio": [
                "pulseaudio"
            ],
            "ALSA": [
                "alsa-utils"
            ]
        }

        packages = (
            desktops[desktop]
            + audio[config["audio"]]
            + applications
            + [
                "calamares",
                "udev",
                "pciutils",
                "usbutils",
                "kmod"
            ]
        )

        if config["wifi"]:

            packages += [
                "wpasupplicant",
                "wireless-regdb"
            ]

        if config["bluetooth"]:

            packages += [
                "bluez",
                "blueman"
            ]

        if config["printing"]:

            packages += [
                "cups",
                "system-config-printer"
            ]

        if config["firmware"]:

            packages += [
                "firmware-linux-free"
            ]

    elif distro == "Arch Linux":

        desktops = {
            "Aucun": [],
            "GNOME": [
                "gnome",
                "gdm"
            ],
            "KDE Plasma": [
                "plasma",
                "sddm"
            ],
            "Xfce": [
                "xfce4",
                "lightdm"
            ],
            "Budgie": [
                "budgie-desktop",
                "lightdm"
            ]
        }

        audio = {
            "Aucun": [],
            "PipeWire": [
                "pipewire",
                "wireplumber"
            ],
            "PulseAudio": [
                "pulseaudio"
            ],
            "ALSA": [
                "alsa-utils"
            ]
        }

        packages = (
            desktops[desktop]
            + audio[config["audio"]]
            + applications
            + [
                "calamares",
                "linux-firmware",
                "pciutils",
                "usbutils",
                "kmod"
            ]
        )

        if config["wifi"]:

            packages += ["iwd"]

        if config["bluetooth"]:

            packages += [
                "bluez",
                "bluez-utils"
            ]

        if config["printing"]:

            packages += ["cups"]

    else:

        # Les autres distributions nécessitent
        # des profils natifs spécifiques.
        packages = applications

    return list(
        dict.fromkeys(packages)
    )


# ============================================================
# VERIFICATION DE CONFIGURATION
# ============================================================

def validate(config):

    errors = []
    warnings = []

    distro = config["distribution"]
    desktop = config["desktop"]
    display = config["display"]

    if (
        desktop == "Aucun"
        and display != "Aucun"
    ):

        errors.append(
            "Sans bureau : affichage Aucun requis."
        )

    if (
        desktop != "Aucun"
        and display == "Aucun"
    ):

        errors.append(
            "Un bureau nécessite X11 ou Wayland."
        )

    if (
        desktop == "Xfce"
        and display == "Wayland"
    ):

        warnings.append(
            "Xfce/Wayland dépend de la version "
            "et du profil : à valider."
        )

    if distro == "Slackware":

        if desktop in (
            "GNOME",
            "Budgie"
        ):

            errors.append(
                "Profil Liveslak GNOME/Budgie "
                "non pris en charge."
            )

    if (
        distro == "Arch Linux"
        and desktop == "Budgie"
        and display == "X11"
    ):

        errors.append(
            "Budgie Arch : sélectionner Wayland."
        )

    if distro in (
        "Fedora",
        "Slackware",
        "Gentoo"
    ):

        warnings.append(
            "Bureau, Calamares et pilotes "
            "nécessitent un profil natif validé. "
            "Export de préparation seulement."
        )

    if config["firmware"]:

        warnings.append(
            "Les firmwares sélectionnés ne "
            "garantissent pas la présence de "
            "tous les pilotes matériels."
        )

    if distro == "Debian":

        warnings.append(
            "Calamares nécessite une configuration "
            "complète et des tests de démarrage."
        )

    if distro == "Arch Linux":

        warnings.append(
            "Archiso + Calamares nécessite des "
            "modules et une session live validés."
        )

    return errors, warnings


# ============================================================
# GENERATION DU PROJET ISO
# ============================================================

def export_project(config, folder):

    errors, warnings = validate(config)

    if errors:

        raise ValueError(
            "\n".join(errors)
        )

    if (
        folder.exists()
        and any(folder.iterdir())
    ):

        raise ValueError(
            "Choisir un dossier vide "
            "pour ne rien écraser."
        )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    project_file = (
        folder / "project_v0_9.json"
    )

    project_file.write_text(
        json.dumps(
            config,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    packages = build_packages(config)

    package_file = (
        folder / "packages_v0_9.txt"
    )

    package_file.write_text(
        "\n".join(packages) + "\n",
        encoding="utf-8"
    )

    distro = config["distribution"]

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

cp packages_v0_9.txt \
    config/package-lists/ulb.list.chroot

lb config \
    --distribution __RELEASE__ \
    --architectures amd64 \
    --binary-images iso-hybrid

echo "Vérifier Calamares, les dépôts,"
echo "les firmwares et la session live."

sudo lb build
"""

        script = script.replace(
            "__RELEASE__",
            config["version"]
        )

    elif distro == "Arch Linux":

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

cp -a \
    /usr/share/archiso/configs/releng \
    profile

cat packages_v0_9.txt \
    >> profile/packages.x86_64

sort -u \
    profile/packages.x86_64 \
    -o profile/packages.x86_64

mkdir -p work out

echo "Configurer Calamares,"
echo "le démarrage graphique,"
echo "les services et les firmwares."

sudo mkarchiso \
    -v \
    -w "$PWD/work" \
    -o "$PWD/out" \
    "$PWD/profile"
"""

    elif distro == "Fedora":

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f template.ks ] || {
    echo "Fournir un Kickstart Live Fedora"
    exit 2
}

command -v livecd-creator >/dev/null || {
    echo "Installer livecd-tools"
    exit 2
}

echo "Intégrer packages_v0_9.txt,"
echo "Calamares et les firmwares"
echo "au Kickstart avant construction."

exit 2
"""

    elif distro == "Slackware":

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f make_slackware_live.sh ] || {
    echo "Fournir Liveslak"
    exit 2
}

echo "Adapter les listes Liveslak,"
echo "intégrer Calamares et les firmwares."

exit 2
"""

    else:

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f livecd.spec ] || {
    echo "Fournir un spec Catalyst complet"
    exit 2
}

echo "Adapter Catalyst, Calamares"
echo "et les firmwares."

exit 2
"""

    script_file = (
        folder / "build_v0_9.sh"
    )

    script_file.write_text(
        script,
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

        self.resize(1020, 800)

        self.worker = None

        self.tabs = QTabWidget()

        self.setCentralWidget(
            self.tabs
        )

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

        self.tabs.addTab(
            widget,
            title
        )

        return layout

    def combo(self, items):

        combo = QComboBox()

        combo.addItems(items)

        return combo

    # --------------------------------------------------------
    # ONGLET DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):

        layout = self.page(
            "Distribution"
        )

        form = QFormLayout()

        self.distribution = self.combo(
            list(DISTROS)
        )

        self.version = self.combo([])

        self.distribution.currentTextChanged.connect(
            self.distribution_changed
        )

        form.addRow(
            "Distribution",
            self.distribution
        )

        form.addRow(
            "Version",
            self.version
        )

        layout.addLayout(form)
        layout.addStretch()

    def distribution_changed(self, distro):

        if distro not in DISTROS:
            return

        self.version.clear()

        self.version.addItems(
            DISTROS[distro]["versions"]
        )

        if hasattr(self, "results"):
            self.results.clear()

        if hasattr(self, "selected"):
            self.selected.clear()

        if hasattr(self, "search_distro"):
            self.search_distro.setCurrentText(
                distro
            )

        if hasattr(self, "desktop"):

            current = (
                self.desktop.currentText()
            )

            if distro == "Slackware":

                choices = [
                    "Aucun",
                    "KDE Plasma",
                    "Xfce"
                ]

            else:

                choices = DESKTOPS

            self.desktop.clear()
            self.desktop.addItems(choices)

            if current in choices:

                self.desktop.setCurrentText(
                    current
                )

            self.desktop_changed(
                self.desktop.currentText()
            )

    # --------------------------------------------------------
    # ONGLET SYSTEME
    # --------------------------------------------------------

    def make_system(self):

        layout = self.page(
            "Système"
        )

        form = QFormLayout()

        self.desktop = self.combo(
            DESKTOPS
        )

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

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        form.addRow(
            "Bureau",
            self.desktop
        )

        form.addRow(
            "Affichage",
            self.display
        )

        form.addRow(
            "Audio",
            self.audio
        )

        layout.addLayout(form)

        self.options = {}

        equipment = [
            (
                "wifi",
                "Wi-Fi",
                True
            ),
            (
                "bluetooth",
                "Bluetooth",
                True
            ),
            (
                "printing",
                "Imprimantes (CUPS)",
                False
            ),
            (
                "firmware",
                "Firmwares et détection matérielle",
                True
            )
        ]

        for key, label, enabled in equipment:

            checkbox = QCheckBox(label)

            checkbox.setChecked(
                enabled
            )

            self.options[key] = checkbox

            layout.addWidget(
                checkbox
            )

        layout.addWidget(
            QLabel(
                "Calamares est demandé dans "
                "le projet ISO. Son fonctionnement "
                "dépend du profil de construction."
            )
        )

        layout.addStretch()

    def desktop_changed(self, desktop):

        if desktop == "Aucun":

            self.display.setCurrentText(
                "Aucun"
            )

        elif desktop == "Xfce":

            self.display.setCurrentText(
                "X11"
            )

        elif (
            desktop == "Budgie"
            and self.distribution.currentText()
            == "Arch Linux"
        ):

            self.display.setCurrentText(
                "Wayland"
            )

        elif (
            self.display.currentText()
            == "Aucun"
        ):

            self.display.setCurrentText(
                "Wayland"
            )

    # --------------------------------------------------------
    # ONGLET APPLICATIONS
    # --------------------------------------------------------

    def make_applications(self):

        layout = self.page(
            "Applications Internet"
        )

        form = QFormLayout()

        self.search_distro = self.combo(
            list(DISTROS)
        )

        self.search_version = self.combo([])

        self.search_distro.currentTextChanged.connect(
            self.search_distro_changed
        )

        form.addRow(
            "Dépôts de",
            self.search_distro
        )

        form.addRow(
            "Version du dépôt",
            self.search_version
        )

        layout.addLayout(form)

        row = QHBoxLayout()

        self.query = QLineEdit()

        self.query.setPlaceholderText(
            "firefox, navigateur, vidéo..."
        )

        self.search_button = QPushButton(
            "Rechercher"
        )

        self.search_button.clicked.connect(
            self.search
        )

        row.addWidget(
            self.query
        )

        row.addWidget(
            self.search_button
        )

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Résultats — double-clic pour ajouter"
            )
        )

        self.results = QListWidget()

        self.results.itemDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(
            self.results
        )

        layout.addWidget(
            QLabel(
                "Applications sélectionnées — "
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

        layout.addWidget(
            self.selected
        )

        manual_row = QHBoxLayout()

        self.manual = QLineEdit()

        self.manual.setPlaceholderText(
            "Nom exact du paquet"
        )

        add_button = QPushButton(
            "Ajouter manuellement"
        )

        add_button.clicked.connect(
            self.add_manual
        )

        manual_row.addWidget(
            self.manual
        )

        manual_row.addWidget(
            add_button
        )

        layout.addLayout(
            manual_row
        )

        self.search_status = QLabel(
            "Recherche Internet : "
            "Arch API intégrée. "
            "Autres catalogues à compléter."
        )

        layout.addWidget(
            self.search_status
        )

        self.search_distro_changed(
            self.search_distro.currentText()
        )

    def search_distro_changed(self, distro):

        self.search_version.clear()

        self.search_version.addItems(
            DISTROS[distro]["versions"]
        )

        self.results.clear()
        self.selected.clear()

    def search(self):

        query = (
            self.query.text().strip()
        )

        if (
            not query
            or len(query) > 80
            or any(
                ord(char) < 32
                for char in query
            )
        ):

            QMessageBox.warning(
                self,
                "Recherche",
                "Recherche invalide."
            )

            return

        if (
            self.search_distro.currentText()
            != self.distribution.currentText()
            or
            self.search_version.currentText()
            != self.version.currentText()
        ):

            QMessageBox.warning(
                self,
                "Dépôts incompatibles",
                "Pour ajouter à l'ISO, sélectionner "
                "la même distribution et la même "
                "version dans les deux onglets."
            )

            return

        query = ALIASES.get(
            query.casefold(),
            query
        )

        self.results.clear()

        self.search_button.setEnabled(
            False
        )

        self.search_status.setText(
            "Recherche en cours..."
        )

        self.worker = SearchWorker(
            self.search_distro.currentText(),
            self.search_version.currentText(),
            query
        )

        self.worker.done.connect(
            self.search_done
        )

        self.worker.finished.connect(
            lambda: self.search_button.setEnabled(
                True
            )
        )

        self.worker.start()

    def search_done(self, rows, error):

        if error:

            self.search_status.setText(
                error
            )

            return

        for name, version, description, repo in rows:

            item = QListWidgetItem(
                f"{name} | {version} | "
                f"{repo} | {description[:70]}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                name
            )

            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                self.search_distro.currentText()
                == "Arch Linux"
            )

            self.results.addItem(
                item
            )

        self.search_status.setText(
            f"{len(rows)} résultat(s). "
            "Seuls les résultats Arch sont "
            "des paquets binaires confirmés."
        )

    def add_result(self, item):

        verified = item.data(
            Qt.ItemDataRole.UserRole + 1
        )

        if not verified:

            QMessageBox.warning(
                self,
                "Paquet non vérifié",
                "Ce résultat ne confirme pas "
                "un paquet binaire installable. "
                "Ajout automatique bloqué."
            )

            return

        name = item.data(
            Qt.ItemDataRole.UserRole
        )

        self.add_package(name)

    def add_manual(self):

        name = (
            self.manual.text().strip()
        )

        valid = (
            PKG.fullmatch(name)
            or (
                self.distribution.currentText()
                == "Gentoo"
                and ATOM.fullmatch(name)
            )
        )

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
            self.selected.item(index).text()
            for index in range(
                self.selected.count()
            )
        ]

        if name not in existing:

            self.selected.addItem(
                name
            )

    def context_menu(self, position):

        item = self.selected.itemAt(
            position
        )

        if item is None:
            return

        menu = QMenu(self)

        delete_action = menu.addAction(
            "Supprimer de l'installation"
        )

        selected_action = menu.exec(
            self.selected.mapToGlobal(
                position
            )
        )

        if selected_action == delete_action:

            self.selected.takeItem(
                self.selected.row(item)
            )

    # --------------------------------------------------------
    # ONGLET ISO
    # --------------------------------------------------------

    def make_export(self):

        layout = self.page(
            "Projet / ISO"
        )

        self.report = QTextEdit()

        self.report.setReadOnly(
            True
        )

        layout.addWidget(
            self.report
        )

        row = QHBoxLayout()

        check_button = QPushButton(
            "Vérifier les choix"
        )

        check_button.clicked.connect(
            self.check
        )

        export_button = QPushButton(
            "Exporter projet et script ISO"
        )

        export_button.clicked.connect(
            self.export
        )

        row.addWidget(
            check_button
        )

        row.addWidget(
            export_button
        )

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Calamares et pilotes : "
                "l'inclusion des paquets ne garantit "
                "pas un installateur fonctionnel. "
                "Tester l'ISO en machine virtuelle."
            )
        )

    def config(self):

        distro = (
            self.distribution.currentText()
        )

        config = {
            "schema": 9,
            "app_version": VERSION,
            "distribution": distro,
            "version": self.version.currentText(),
            "architecture": DISTROS[distro]["arch"],
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "calamares": True,
            "applications": [
                self.selected.item(index).text()
                for index in range(
                    self.selected.count()
                )
            ]
        }

        for key, checkbox in self.options.items():

            config[key] = (
                checkbox.isChecked()
            )

        return config

    def check(self):

        config = self.config()

        errors, warnings = validate(
            config
        )

        report = json.dumps(
            config,
            ensure_ascii=False,
            indent=2
        )

        report += "\n\nERREURS :\n"

        report += (
            "\n".join(errors)
            or "Aucune erreur de profil connue"
        )

        report += "\n\nAVERTISSEMENTS :\n"

        report += (
            "\n".join(warnings)
            or "Aucun"
        )

        self.report.setPlainText(
            report
        )

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
            "Choisir un dossier de projet VIDE",
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
            f"Projet et script créés :\n{script}\n\n"
            "Aucune ISO construite automatiquement.\n"
            + "\n".join(warnings)
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    window = Window()

    window.show()

    sys.exit(
        app.exec()
    )
