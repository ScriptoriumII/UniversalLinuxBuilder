import json
import re
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QListWidget, QLabel,
    QTextEdit, QMessageBox, QFileDialog, QCheckBox
)

VERSION = "0.8"
ROOT = Path.home() / "Documents" / "UniversalLinuxBuilder"

DISTROS = {
    "Debian": {
        "family": "Debian / Ubuntu",
        "versions": ["trixie", "bookworm"],
        "url": "https://packages.debian.org/search?keywords={q}&searchon=names&suite={v}&section=all"
    },
    "Ubuntu": {
        "family": "Debian / Ubuntu",
        "versions": ["noble", "jammy"],
        "url": "https://packages.ubuntu.com/search?keywords={q}&searchon=names&suite={v}&section=all"
    },
    "Fedora": {
        "family": "Fedora / Rocky Linux",
        "versions": ["43", "42"],
        "url": "https://packages.fedoraproject.org/search?query={q}"
    },
    "Rocky Linux": {
        "family": "Fedora / Rocky Linux",
        "versions": ["10", "9"],
        "url": "https://pkgs.org/search/?q={q}"
    },
    "Slackware": {
        "family": "Slackware / Salix",
        "versions": ["15.0", "current"],
        "url": "https://slackware.pkgs.org/search/?q={q}"
    },
    "Salix": {
        "family": "Slackware / Salix",
        "versions": ["15.0"],
        "url": "https://slackware.pkgs.org/search/?q={q}"
    },
    "Gentoo": {
        "family": "Gentoo",
        "versions": ["stable", "testing"],
        "url": "https://packages.gentoo.org/packages/search?q={q}"
    },
    "Arch Linux": {
        "family": "Arch Linux",
        "versions": ["rolling"],
        "url": "https://archlinux.org/packages/?q={q}"
    }
}

FAMILIES = list(dict.fromkeys(
    value["family"] for value in DISTROS.values()
))

DESKTOPS = [
    "Aucun",
    "GNOME",
    "KDE Plasma",
    "Xfce",
    "Budgie"
]

ALIASES = {
    "navigateur": "firefox",
    "internet": "firefox",
    "video": "vlc",
    "musique": "audacious",
    "bureautique": "libreoffice",
    "photo": "gimp",
    "courriel": "thunderbird",
    "terminal": "alacritty"
}

PACKAGE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.@/-]{0,120}$"
)


def arch_search(query):
    """Recherche dans l'API officielle Arch Linux."""

    url = (
        "https://archlinux.org/packages/search/json/?q="
        + urllib.parse.quote(query)
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/0.8"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=18
    ) as response:
        payload = json.load(response)

    results = []

    for package in payload.get("results", []):
        if package.get("arch") not in (
            "x86_64",
            "any"
        ):
            continue

        results.append((
            package["pkgname"],
            package.get("pkgver", ""),
            package.get("repo", ""),
            package.get("pkgdesc") or ""
        ))

    return results[:100]


def catalog_url(distro, version, query):
    pattern = DISTROS[distro]["url"]

    return pattern.format(
        q=urllib.parse.quote(query),
        v=urllib.parse.quote(version)
    )


class SearchThread(QThread):

    result = Signal(object, str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        try:
            results = arch_search(self.query)
            self.result.emit(results, "")

        except Exception as error:
            self.result.emit([], str(error))


def package_list(config):
    distro = config["distro"]
    desktop = config["desktop"]
    audio = config["audio"]

    applications = list(config["apps"])

    if distro in ("Debian", "Ubuntu"):
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

    else:
        # Les autres familles nécessitent des profils
        # de paquets propres à leurs outils natifs.
        return applications

    packages = (
        desktops[desktop]
        + sounds[audio]
        + applications
    )

    return list(dict.fromkeys(packages))


def validate(config):
    errors = []
    warnings = []

    distro = config["distro"]
    desktop = config["desktop"]
    display = config["display"]

    if desktop == "Aucun" and display != "Aucun":
        errors.append(
            "Sans bureau, sélectionner affichage Aucun."
        )

    if desktop != "Aucun" and display == "Aucun":
        errors.append(
            "Un bureau exige X11 ou Wayland."
        )

    if desktop == "Xfce" and display == "Wayland":
        errors.append(
            "Xfce/Wayland non validé dans ce générateur."
        )

    if (
        desktop == "Budgie"
        and display == "X11"
        and distro == "Arch Linux"
    ):
        errors.append(
            "Budgie sur Arch : sélectionner Wayland."
        )

    if distro in ("Slackware", "Salix"):
        if desktop not in (
            "Aucun",
            "Xfce",
            "KDE Plasma"
        ):
            errors.append(
                "Bureau non validé pour Liveslak."
            )

    if distro == "Salix" and desktop == "KDE Plasma":
        errors.append(
            "Profil Salix KDE non validé."
        )

    if distro in (
        "Fedora",
        "Rocky Linux",
        "Gentoo",
        "Slackware",
        "Salix"
    ):
        warnings.append(
            "Bureau, audio et applications : "
            "vérifier leur intégration dans "
            "le modèle de construction natif."
        )

    if distro != "Arch Linux":
        warnings.append(
            "Le catalogue web ne constitue pas "
            "une vérification automatique "
            "de disponibilité."
        )

    return errors, warnings


def generate(config, target):
    target.mkdir(
        parents=True,
        exist_ok=True
    )

    distro = config["distro"]
    version = config["version"]

    packages = package_list(config)

    for package in packages:
        if not PACKAGE_PATTERN.fullmatch(package):
            raise ValueError(
                f"Nom de paquet invalide : {package}"
            )

    project = target / "project_v0_8.json"

    project.write_text(
        json.dumps(
            config,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    package_file = target / "packages_v0_8.txt"

    package_file.write_text(
        "\n".join(packages) + "\n",
        encoding="utf-8"
    )

    if distro in ("Debian", "Ubuntu"):

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

command -v lb >/dev/null || {
    echo "Installer live-build"
    exit 1
}

[ ! -e config ] || {
    echo "Dossier de construction déjà utilisé"
    exit 1
}

mkdir -p config/package-lists

cp packages_v0_8.txt \
    config/package-lists/ulb.list.chroot

lb config \
    --distribution __VERSION__ \
    --architectures amd64 \
    --binary-images iso-hybrid

sudo lb build
"""

        script = script.replace(
            "__VERSION__",
            version
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

cat packages_v0_8.txt \
    >> profile/packages.x86_64

sort -u \
    profile/packages.x86_64 \
    -o profile/packages.x86_64

mkdir -p work out

sudo mkarchiso \
    -v \
    -w "$PWD/work" \
    -o "$PWD/out" \
    "$PWD/profile"
"""

    elif distro in ("Fedora", "Rocky Linux"):

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f template.ks ] || {
    echo "Fournir un template.ks Live compatible"
    exit 1
}

command -v livecd-creator >/dev/null || {
    echo "Installer livecd-tools"
    exit 1
}

python3 - <<'PYCODE'
from pathlib import Path

content = Path("template.ks").read_text()

start = content.find("%packages")
end = content.find("%end", start)

if start < 0 or end < 0:
    raise SystemExit(
        "Section %packages absente"
    )

packages = Path(
    "packages_v0_8.txt"
).read_text()

content = (
    content[:end]
    + packages
    + "\\n"
    + content[end:]
)

Path("ulb.ks").write_text(content)
PYCODE

sudo livecd-creator \
    --config=ulb.ks \
    --fslabel=ULB-Live
"""

    elif distro in ("Slackware", "Salix"):

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f make_slackware_live.sh ] || {
    echo "Copier les sources Liveslak ici"
    exit 1
}

echo "Les paquets ne sont pas encore injectés."
echo "Adapter les listes Liveslak avant construction."

exit 2
"""

    else:

        script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f livecd.spec ] || {
    echo "Fournir un spec Catalyst complet"
    exit 1
}

command -v catalyst >/dev/null || {
    echo "Installer Catalyst"
    exit 1
}

echo "Adapter le spec et les listes de paquets."
echo "Construction bloquée par sécurité."

exit 2
"""

    script_file = target / "build_v0_8.sh"

    script_file.write_text(
        script,
        encoding="utf-8"
    )

    return script_file


class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v0.8"
        )

        self.resize(990, 760)

        self.search_thread = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_distribution()
        self.setup_system()
        self.setup_search()
        self.setup_build()

        self.family_changed(
            self.family.currentText()
        )

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.tabs.addTab(widget, name)

        return layout

    def combo(self, items):
        widget = QComboBox()
        widget.addItems(items)

        return widget

    def setup_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.family = self.combo(FAMILIES)
        self.distro = self.combo([])
        self.version = self.combo([])

        self.family.currentTextChanged.connect(
            self.family_changed
        )

        self.distro.currentTextChanged.connect(
            self.distro_changed
        )

        form.addRow("Famille", self.family)
        form.addRow("Distribution", self.distro)
        form.addRow("Version", self.version)

        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Architecture : x86_64 / amd64"
        ))

        layout.addStretch()

    def family_changed(self, family):
        self.distro.blockSignals(True)

        self.distro.clear()

        distributions = [
            name
            for name, spec in DISTROS.items()
            if spec["family"] == family
        ]

        self.distro.addItems(distributions)

        self.distro.blockSignals(False)

        self.distro_changed(
            self.distro.currentText()
        )

    def distro_changed(self, distro):
        if distro not in DISTROS:
            return

        self.version.clear()

        self.version.addItems(
            DISTROS[distro]["versions"]
        )

        if hasattr(self, "packages"):
            self.packages.clear()
            self.results.clear()

        if hasattr(self, "desktop"):
            self.desktop.clear()

            if distro == "Slackware":
                choices = [
                    "Aucun",
                    "Xfce",
                    "KDE Plasma"
                ]

            elif distro == "Salix":
                choices = [
                    "Aucun",
                    "Xfce"
                ]

            else:
                choices = DESKTOPS

            self.desktop.addItems(choices)

            self.desktop_changed(
                self.desktop.currentText()
            )

    def setup_system(self):
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

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        form.addRow("Bureau", self.desktop)
        form.addRow("Affichage", self.display)
        form.addRow("Audio", self.audio)

        layout.addLayout(form)

        self.wifi = QCheckBox(
            "Wi-Fi (configuration ISO à compléter)"
        )

        self.wifi.setChecked(True)

        layout.addWidget(self.wifi)
        layout.addStretch()

    def desktop_changed(self, desktop):
        if desktop == "Aucun":
            self.display.setCurrentText("Aucun")

        elif desktop == "Xfce":
            self.display.setCurrentText("X11")

        elif (
            desktop == "Budgie"
            and self.distro.currentText() == "Arch Linux"
        ):
            self.display.setCurrentText("Wayland")

        elif self.display.currentText() == "Aucun":
            self.display.setCurrentText("Wayland")

    def setup_search(self):
        layout = self.page("Applications Internet")

        layout.addWidget(QLabel(
            "Arch : API officielle. "
            "Autres distributions : catalogue web."
        ))

        row = QHBoxLayout()

        self.query = QLineEdit()

        self.query.setPlaceholderText(
            "firefox, navigateur, vidéo..."
        )

        button = QPushButton(
            "Rechercher sur Internet"
        )

        button.clicked.connect(self.search)

        row.addWidget(self.query)
        row.addWidget(button)

        layout.addLayout(row)

        self.results = QListWidget()

        self.results.itemDoubleClicked.connect(
            self.add_result
        )

        layout.addWidget(self.results)

        layout.addWidget(QLabel(
            "Applications sélectionnées "
            "(double-clic pour supprimer)"
        ))

        self.packages = QListWidget()

        self.packages.itemDoubleClicked.connect(
            lambda item: self.packages.takeItem(
                self.packages.row(item)
            )
        )

        layout.addWidget(self.packages)

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

        manual_row.addWidget(self.manual)
        manual_row.addWidget(add_button)

        layout.addLayout(manual_row)

        self.search_status = QLabel("")

        layout.addWidget(self.search_status)

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
                "Saisir une recherche valide."
            )
            return

        query = ALIASES.get(
            query.casefold(),
            query
        )

        distro = self.distro.currentText()

        self.results.clear()

        if distro != "Arch Linux":
            url = catalog_url(
                distro,
                self.version.currentText(),
                query
            )

            webbrowser.open(url)

            self.search_status.setText(
                "Catalogue ouvert dans le navigateur. "
                "Vérifier le paquet avant de l'ajouter."
            )
            return

        self.search_status.setText(
            "Recherche dans les dépôts Arch..."
        )

        self.search_thread = SearchThread(query)

        self.search_thread.result.connect(
            self.search_result
        )

        self.search_thread.start()

    def search_result(self, results, error):
        if error:
            self.search_status.setText(
                "Erreur réseau : " + error
            )
            return

        for name, version, repo, description in results:
            self.results.addItem(
                f"{name} | {version} | "
                f"{repo} | {description[:75]}"
            )

        self.search_status.setText(
            f"{len(results)} résultats trouvés."
        )

    def add_result(self, item):
        name = item.text().split(
            " | ",
            1
        )[0]

        self.add_package(name)

    def add_manual(self):
        name = self.manual.text().strip()

        if not PACKAGE_PATTERN.fullmatch(name):
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
            self.packages.item(index).text()
            for index in range(
                self.packages.count()
            )
        ]

        if name not in existing:
            self.packages.addItem(name)

    def setup_build(self):
        layout = self.page("Projet / ISO")

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)

        layout.addWidget(self.summary)

        row = QHBoxLayout()

        check_button = QPushButton(
            "Vérifier la cohérence"
        )

        check_button.clicked.connect(
            self.check
        )

        generate_button = QPushButton(
            "Générer projet et script ISO"
        )

        generate_button.clicked.connect(
            self.export
        )

        row.addWidget(check_button)
        row.addWidget(generate_button)

        layout.addLayout(row)

        layout.addWidget(QLabel(
            "Les scripts nécessitent un environnement "
            "Linux compatible. Aucune construction "
            "n'est lancée automatiquement."
        ))

    def config(self):
        return {
            "schema": 8,
            "version_app": VERSION,
            "family": self.family.currentText(),
            "distro": self.distro.currentText(),
            "version": self.version.currentText(),
            "arch": "x86_64",
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "wifi": self.wifi.isChecked(),
            "apps": [
                self.packages.item(index).text()
                for index in range(
                    self.packages.count()
                )
            ]
        }

    def check(self):
        config = self.config()

        errors, warnings = validate(config)

        report = json.dumps(
            config,
            indent=2,
            ensure_ascii=False
        )

        report += "\n\nERREURS :\n"

        report += (
            "\n".join(errors)
            or "Aucune erreur connue"
        )

        report += "\n\nAVERTISSEMENTS :\n"

        report += "\n".join(warnings)

        self.summary.setPlainText(report)

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
            "Choisir le dossier du projet",
            str(ROOT)
        )

        if not folder:
            return

        destination = Path(folder)

        if (
            destination / "build_v0_8.sh"
        ).exists():
            QMessageBox.warning(
                self,
                "Fichier existant",
                "Choisir un dossier vierge pour "
                "conserver le projet précédent."
            )
            return

        try:
            script = generate(
                self.config(),
                destination
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
            "Projet généré",
            f"Projet enregistré :\n{script}\n\n"
            "Le script n'a pas été exécuté."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())
