import sys
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QFileDialog, QMessageBox,
    QTextEdit, QMenu, QAbstractItemView, QSplitter,
    QHeaderView
)

VERSION = "1.7"

DISTROS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

INIT_SYSTEMS = {
    "Debian": ["systemd"],
    "Fedora": ["systemd"],
    "Arch Linux": ["systemd"],
    "Gentoo": ["OpenRC", "systemd"],
    "Slackware": ["SysVinit"]
}

KERNELS = {
    "Debian": {
        "Stable": ["linux-image-amd64"]
    },
    "Fedora": {
        "Stable": ["kernel"]
    },
    "Arch Linux": {
        "Stable": ["linux", "linux-headers"],
        "LTS": ["linux-lts", "linux-lts-headers"],
        "Hardened": ["linux-hardened", "linux-hardened-headers"]
    },
    "Gentoo": {
        "Stable": ["sys-kernel/gentoo-kernel"]
    },
    "Slackware": {
        "Stable": ["kernel-generic"]
    }
}

INIT_PACKAGES = {
    "Debian": {
        "systemd": ["systemd-sysv"]
    },
    "Fedora": {
        "systemd": ["systemd"]
    },
    "Arch Linux": {
        "systemd": ["systemd"]
    },
    "Gentoo": {
        "OpenRC": ["sys-apps/openrc"],
        "systemd": ["sys-apps/systemd"]
    },
    "Slackware": {
        "SysVinit": ["sysvinit"]
    }
}

DESKTOPS = {
    "Debian": {
        "GNOME": ["gnome-core", "gdm3", "network-manager"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm", "network-manager"],
        "Xfce": ["xfce4", "lightdm", "xserver-xorg", "network-manager"],
        "Budgie": ["budgie-desktop", "lightdm", "network-manager"]
    },
    "Fedora": {
        "GNOME": ["gnome-shell", "gnome-session", "gdm", "NetworkManager"],
        "KDE Plasma": ["plasma-desktop", "plasma-workspace", "sddm", "NetworkManager"],
        "Xfce": ["xfce4-session", "xfce4-panel", "xfwm4", "lightdm", "NetworkManager"],
        "Budgie": ["budgie-desktop", "gdm", "NetworkManager"]
    },
    "Arch Linux": {
        "GNOME": ["gnome", "gdm", "networkmanager"],
        "KDE Plasma": ["plasma", "sddm", "networkmanager"],
        "Xfce": ["xfce4", "lightdm", "lightdm-gtk-greeter", "networkmanager"],
        "Budgie": ["budgie-desktop", "gdm", "networkmanager"]
    },
    "Gentoo": {
        "GNOME": ["gnome-base/gnome", "gnome-base/gdm"],
        "KDE Plasma": ["kde-plasma/plasma-meta", "x11-misc/sddm"],
        "Xfce": ["xfce-base/xfce4-meta", "x11-misc/lightdm"],
        "Budgie": ["gnome-extra/budgie-desktop", "gnome-base/gdm"]
    },
    "Slackware": {
        "KDE Plasma": ["plasma-workspace", "plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel", "xfwm4"]
    }
}

DISPLAY_PACKAGES = {
    "Debian": {
        "X11": ["xserver-xorg"],
        "Wayland": ["libwayland-client0"]
    },
    "Fedora": {
        "X11": ["xorg-x11-server-Xorg"],
        "Wayland": ["wayland"]
    },
    "Arch Linux": {
        "X11": ["xorg-server"],
        "Wayland": ["wayland"]
    },
    "Gentoo": {
        "X11": ["x11-base/xorg-server"],
        "Wayland": ["dev-libs/wayland"]
    },
    "Slackware": {
        "X11": ["xorg-server"],
        "Wayland": []
    }
}

AUDIO_PACKAGES = {
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
        "PipeWire": ["media-video/pipewire", "media-video/wireplumber"],
        "PulseAudio": ["media-sound/pulseaudio"],
        "ALSA": ["media-sound/alsa-utils"]
    },
    "Slackware": {
        "PipeWire": ["pipewire", "wireplumber"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    }
}

GRUB_PACKAGES = {
    "Debian": {
        "UEFI": ["grub-efi-amd64", "efibootmgr"],
        "BIOS": ["grub-pc"],
        "BIOS + UEFI": []
    },
    "Fedora": {
        "UEFI": ["grub2-efi-x64", "grub2-tools", "shim-x64"],
        "BIOS": ["grub2-pc", "grub2-tools"],
        "BIOS + UEFI": []
    },
    "Arch Linux": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"],
        "BIOS + UEFI": ["grub", "efibootmgr"]
    },
    "Gentoo": {
        "UEFI": ["sys-boot/grub", "sys-boot/efibootmgr"],
        "BIOS": ["sys-boot/grub"],
        "BIOS + UEFI": ["sys-boot/grub", "sys-boot/efibootmgr"]
    },
    "Slackware": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"],
        "BIOS + UEFI": []
    }
}

EXTRA_PACKAGES = {
    "Debian": {
        "Base": ["udev", "pciutils", "usbutils"],
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmwares": ["firmware-linux-free"],
        "Calamares": ["calamares"]
    },
    "Fedora": {
        "Base": ["NetworkManager", "pciutils", "usbutils"],
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmwares": ["linux-firmware"],
        "Calamares": []
    },
    "Arch Linux": {
        "Base": ["base", "pciutils", "usbutils"],
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez", "bluez-utils"],
        "Impression": ["cups"],
        "Firmwares": ["linux-firmware"],
        "Calamares": ["calamares"]
    },
    "Gentoo": {
        "Base": ["sys-apps/pciutils"],
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmwares": ["sys-kernel/linux-firmware"],
        "Calamares": []
    },
    "Slackware": {
        "Base": ["pciutils", "usbutils"],
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmwares": ["kernel-firmware"],
        "Calamares": []
    }
}

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:/-]{0,120}$")

THEMES = {
    "Clair": {
        "bg": "#f3f5f9",
        "panel": "#ffffff",
        "text": "#172235",
        "muted": "#66768b",
        "border": "#dce3ed",
        "hover": "#e7eef9",
        "alternate": "#f8fafd",
        "selected": "#dceaff",
        "selected_text": "#142d50",
        "accent": "#2563eb"
    },
    "Sombre": {
        "bg": "#101721",
        "panel": "#192332",
        "text": "#eaf0fa",
        "muted": "#9bacbf",
        "border": "#344357",
        "hover": "#32445d",
        "alternate": "#1e2b3b",
        "selected": "#245d9a",
        "selected_text": "#ffffff",
        "accent": "#83b6ff"
    }
}

STYLE = """
QMainWindow, QWidget#root {
    background: %(bg)s;
    color: %(text)s;
}
QWidget {
    color: %(text)s;
    font: 13px "Segoe UI";
}
QLabel#title {
    font-size: 24px;
    font-weight: 700;
}
QLabel#muted {
    color: %(muted)s;
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: %(panel)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 7px;
    selection-background-color: %(selected)s;
    selection-color: %(selected_text)s;
}
QComboBox::drop-down {
    border: none;
    width: 25px;
}
QPushButton {
    background: %(panel)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 10px 15px;
    font-weight: 600;
}
QPushButton:hover {
    background: %(hover)s;
}
QPushButton#primary {
    background: #2563eb;
    color: white;
    border: 1px solid #2563eb;
}
QPushButton#primary:hover {
    background: #1d4ed8;
}
QTabWidget::pane {
    border: 1px solid %(border)s;
    border-radius: 10px;
    background: %(panel)s;
}
QTabBar::tab {
    background: transparent;
    color: %(muted)s;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 13px 19px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    color: %(accent)s;
    border-bottom: 2px solid %(accent)s;
    background: %(panel)s;
}
QTabBar::tab:hover {
    background: %(hover)s;
}
QHeaderView::section {
    background: %(hover)s;
    color: %(text)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    padding: 9px;
    font-weight: 700;
}
QTableWidget {
    alternate-background-color: %(alternate)s;
    gridline-color: %(border)s;
}
QTableWidget::item:selected {
    background: %(selected)s;
    color: %(selected_text)s;
}
QMenu {
    background: %(panel)s;
    color: %(text)s;
    border: 1px solid %(border)s;
}
QMenu::item:selected {
    background: %(selected)s;
    color: %(selected_text)s;
}
"""

def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.7",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        return json.load(response)


def search_packages(distro, release, query):
    encoded = urllib.parse.quote(query)
    results = []

    if distro == "Arch Linux":
        data = download(
            "https://archlinux.org/packages/search/json/?q=" + encoded
        )
        for item in data.get("results", []):
            if item.get("arch") not in ("x86_64", "any"):
                continue
            results.append({
                "name": item["pkgname"],
                "version": str(item.get("pkgver", "")),
                "repo": item.get("repo", ""),
                "arch": item.get("arch", ""),
                "description": item.get("pkgdesc", ""),
                "size": item.get("compressed_size"),
                "source": "Arch officiel"
            })

    elif distro == "Debian":
        data = download(
            "https://sources.debian.org/api/search/" + encoded + "/"
        )
        for item in data.get("results", {}).get("exact", []):
            name = item.get("name", "")
            if name:
                results.append({
                    "name": name,
                    "version": "?",
                    "repo": release,
                    "arch": "",
                    "description": "Paquet source Debian",
                    "size": None,
                    "source": "Debian Sources"
                })

    else:
        # Repology fournit des métadonnées de projets.
        # Ce catalogue ne remplace pas les dépôts natifs.
        #
        # En cas d'indisponibilité de l'API, le programme
        # signale l'erreur au lieu de présenter des
        # résultats non vérifiés comme officiels.
        data = download(
            "https://repology.org/api/v1/projects/?search=" + encoded
        )

        if not isinstance(data, dict):
            raise RuntimeError("Catalogue distant indisponible")

        prefixes = {
            "Fedora": "fedora_",
            "Gentoo": "gentoo",
            "Slackware": "slackware_"
        }

        prefix = prefixes[distro]

        for project, entries in data.items():
            if not isinstance(entries, list):
                continue

            for item in entries:
                repo = str(item.get("repo", ""))

                if not repo.startswith(prefix):
                    continue

                name = str(
                    item.get("binname")
                    or item.get("visiblename")
                    or project
                )

                if not SAFE_NAME.fullmatch(name):
                    continue

                results.append({
                    "name": name,
                    "version": str(item.get("version", "")),
                    "repo": repo,
                    "arch": "",
                    "description": item.get("summary") or "",
                    "size": None,
                    "source": "Repology"
                })

    unique = {}
    for item in results:
        unique[(item["name"], item["repo"])] = item

    return list(unique.values())[:150]


def resolve_arch(names, limit=180):
    graph = {}
    metadata = {}
    warnings = []
    queue = list(names)
    visited = set()

    while queue:
        name = queue.pop(0)

        if name in visited:
            continue

        if len(visited) >= limit:
            warnings.append("Limite de résolution atteinte")
            break

        visited.add(name)

        try:
            matches = [
                p for p in search_packages(
                    "Arch Linux", "rolling", name
                )
                if p["name"] == name
            ]

            if not matches:
                warnings.append(
                    name + " : paquet ou fournisseur virtuel introuvable"
                )
                continue

            package = matches[0]
            metadata[name] = package

            parts = [
                package["repo"],
                package["arch"],
                package["name"]
            ]

            path = "/".join(
                urllib.parse.quote(x, safe="")
                for x in parts
            )

            details = download(
                "https://archlinux.org/packages/"
                + path + "/json/"
            )

            metadata[name]["size"] = details.get(
                "compressed_size"
            )

            dependencies = []

            for raw in details.get("depends") or []:
                dependency = re.split(
                    r"[<>=:]",
                    str(raw),
                    1
                )[0].strip()

                if not SAFE_NAME.fullmatch(dependency):
                    warnings.append(
                        name + " : dépendance non reconnue " + str(raw)
                    )
                    continue

                dependencies.append(dependency)

                if dependency not in visited:
                    if dependency not in queue:
                        queue.append(dependency)

            graph[name] = list(dict.fromkeys(dependencies))

        except Exception as error:
            warnings.append(name + " : " + str(error))

    return graph, metadata, warnings


class Worker(QThread):
    completed = Signal(object, str)

    def __init__(self, mode, *args):
        super().__init__()
        self.mode = mode
        self.args = args

    def run(self):
        try:
            if self.mode == "search":
                result = search_packages(*self.args)
            else:
                result = resolve_arch(*self.args)

            self.completed.emit(result, "")

        except Exception as error:
            self.completed.emit(None, str(error))


class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.7"
        )
        self.resize(1300, 870)

        self.roots = {}
        self.graph = {}
        self.metadata = {}
        self.unresolved = {}
        self.system_scan = {}
        self.worker = None
        self.revision = 0

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 20)

        header = QHBoxLayout()

        title = QLabel("Universal Linux Builder")
        title.setObjectName("title")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Apparence"))

        self.theme = QComboBox()
        self.theme.addItems([
            "Automatique", "Clair", "Sombre"
        ])
        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        header.addWidget(self.theme)
        layout.addLayout(header)

        subtitle = QLabel(
            "Distribution Linux personnalisée · "
            "Dépendances · GRUB · Calamares"
        )
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.build_distribution()
        self.build_system()
        self.build_apps()
        self.build_project()

        self.distro_changed(self.distro.currentText())
        self.apply_theme()

        QApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.apply_theme()
        )

    def apply_theme(self, *_):
        theme = self.theme.currentText()

        if theme == "Automatique":
            dark = (
                QApplication.styleHints().colorScheme()
                == Qt.ColorScheme.Dark
            )
            theme = "Sombre" if dark else "Clair"

        self.setStyleSheet(STYLE % THEMES[theme])

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(13)

        self.tabs.addTab(widget, name)
        return layout

    def combo(self, values):
        widget = QComboBox()
        widget.addItems(values)
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
        widget.verticalHeader().setVisible(False)
        widget.verticalHeader().setDefaultSectionSize(35)

        widget.horizontalHeader().setStretchLastSection(True)

        return widget

    def cell(self, table, row, column, value, data=None):
        item = QTableWidgetItem(str(value))

        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)

        table.setItem(row, column, item)

    def build_distribution(self):
        layout = self.page("Distribution")
        form = QFormLayout()

        self.distro = self.combo(list(DISTROS))
        self.release = self.combo([])

        form.addRow("Distribution", self.distro)
        form.addRow("Version", self.release)

        layout.addLayout(form)
        layout.addStretch()

        self.distro.currentTextChanged.connect(
            self.distro_changed
        )
        self.release.currentTextChanged.connect(
            self.release_changed
        )

    def build_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo(["Aucun"])
        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])
        self.audio = self.combo([
            "Aucun", "PipeWire", "PulseAudio", "ALSA"
        ])
        self.kernel = self.combo([
            "Stable", "LTS", "Hardened"
        ])

        # NOUVEAU V1.7
        self.init_system = self.combo([])

        self.bootloader = self.combo([
            "GRUB", "Aucun (avancé)"
        ])
        self.boot_mode = self.combo([
            "UEFI", "BIOS", "BIOS + UEFI"
        ])

        for label, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau Linux", self.kernel),
            ("Système d'initialisation", self.init_system),
            ("Chargeur de démarrage", self.bootloader),
            ("Mode de démarrage", self.boot_mode)
        ]:
            form.addRow(label, widget)

        layout.addLayout(form)

        self.options = {}

        for key, label, enabled in [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", True),
            ("printing", "Imprimantes / CUPS", False),
            ("firmware", "Firmwares", True),
            ("calamares", "Préparer Calamares", True)
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(enabled)

            self.options[key] = checkbox
            layout.addWidget(checkbox)

            checkbox.toggled.connect(self.system_changed)

        self.system_note = QLabel()
        self.system_note.setWordWrap(True)
        layout.addWidget(self.system_note)

        self.scan_button = QPushButton(
            "Analyser les dépendances du système"
        )
        self.scan_button.setObjectName("primary")
        self.scan_button.clicked.connect(
            self.analyze_system
        )

        layout.addWidget(self.scan_button)
        layout.addStretch()

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        for widget in [
            self.display,
            self.audio,
            self.kernel,
            self.init_system,
            self.bootloader,
            self.boot_mode
        ]:
            widget.currentTextChanged.connect(
                self.system_changed
            )

    def distro_changed(self, distro):
        self.revision += 1

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(DISTROS[distro])
        self.release.blockSignals(False)

        old_desktop = self.desktop.currentText()

        self.desktop.blockSignals(True)
        self.desktop.clear()
        self.desktop.addItems(
            ["Aucun"] + list(DESKTOPS[distro])
        )

        if old_desktop in DESKTOPS[distro]:
            self.desktop.setCurrentText(old_desktop)

        self.desktop.blockSignals(False)

        # NOUVEAU : initialisation selon la distribution
        self.init_system.blockSignals(True)
        self.init_system.clear()
        self.init_system.addItems(INIT_SYSTEMS[distro])
        self.init_system.blockSignals(False)

        if hasattr(self, "catalog_distro"):
            self.catalog_distro.blockSignals(True)
            self.catalog_distro.setCurrentText(distro)
            self.catalog_distro.blockSignals(False)

            self.catalog_release.blockSignals(True)
            self.catalog_release.clear()
            self.catalog_release.addItems(DISTROS[distro])
            self.catalog_release.setCurrentText(
                self.release.currentText()
            )
            self.catalog_release.blockSignals(False)

        self.clear_apps()
        self.desktop_changed(self.desktop.currentText())

    def release_changed(self, version):
        self.revision += 1

        if hasattr(self, "catalog_release"):
            self.catalog_release.setCurrentText(version)

        self.clear_apps()
        self.system_changed()

    def desktop_changed(self, desktop):
        if desktop == "Aucun":
            target = "Aucun"
        elif desktop == "Xfce":
            target = "X11"
        elif self.distro.currentText() == "Slackware":
            target = "X11"
        else:
            target = "Wayland"

        self.display.blockSignals(True)
        self.display.setCurrentText(target)
        self.display.blockSignals(False)

        self.system_changed()

    def system_changed(self, *_):
        self.revision += 1
        self.system_scan = {}

        if not hasattr(self, "system_note"):
            return

        distro = self.distro.currentText()
        kernel = self.kernel.currentText()
        init = self.init_system.currentText()

        kernel_packages = KERNELS[distro].get(kernel, [])

        message = (
            "Noyau : "
            + (
                ", ".join(kernel_packages)
                if kernel_packages
                else "Variante non définie pour cette distribution"
            )
        )

        message += "\nInitialisation : " + init

        if distro == "Gentoo":
            message += (
                "\nGentoo : le choix OpenRC/systemd "
                "doit également correspondre au profil Portage."
            )

        message += (
            "\nAnalyse à relancer après modification "
            "de la configuration."
        )

        self.system_note.setText(message)

    def build_apps(self):
        layout = self.page("Applications")

        form = QFormLayout()

        self.catalog_distro = self.combo(list(DISTROS))
        self.catalog_release = self.combo([])

        form.addRow("Catalogue", self.catalog_distro)
        form.addRow("Version", self.catalog_release)

        layout.addLayout(form)

        self.catalog_distro.currentTextChanged.connect(
            self.catalog_changed
        )

        search_row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher : firefox, vlc, gimp..."
        )
        self.query.returnPressed.connect(self.search)

        self.search_button = QPushButton("Rechercher")
        self.search_button.setObjectName("primary")
        self.search_button.clicked.connect(self.search)

        search_row.addWidget(self.query)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.results = self.table([
            "Application",
            "Version",
            "Dépôt",
            "Source / Description"
        ])

        self.results.setColumnWidth(0, 280)
        self.results.setColumnWidth(1, 160)
        self.results.setColumnWidth(2, 170)
        self.results.setSortingEnabled(True)

        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        splitter.addWidget(self.results)

        self.selected = self.table([
            "Paquet sélectionné",
            "Rôle",
            "Version",
            "Taille"
        ])

        self.selected.setColumnWidth(0, 320)
        self.selected.setColumnWidth(1, 190)

        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.selected.customContextMenuRequested.connect(
            self.remove_menu
        )

        splitter.addWidget(self.selected)
        splitter.setSizes([390, 230])

        layout.addWidget(splitter, 1)

        manual_row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Ajouter un paquet manuellement"
        )

        add_button = QPushButton("Ajouter")
        add_button.clicked.connect(self.add_manual)

        manual_row.addWidget(self.manual)
        manual_row.addWidget(add_button)
        layout.addLayout(manual_row)

        self.app_note = QLabel(
            "Recherche intégrée. Les catalogues tiers "
            "ne garantissent pas la disponibilité du paquet."
        )
        self.app_note.setWordWrap(True)
        layout.addWidget(self.app_note)

        self.catalog_changed(
            self.catalog_distro.currentText()
        )

    def catalog_changed(self, distro):
        self.catalog_release.blockSignals(True)
        self.catalog_release.clear()
        self.catalog_release.addItems(DISTROS[distro])
        self.catalog_release.blockSignals(False)

        self.clear_apps()

    def clear_apps(self):
        self.roots.clear()
        self.graph.clear()
        self.metadata.clear()
        self.unresolved.clear()

        if hasattr(self, "results"):
            self.results.setRowCount(0)

        if hasattr(self, "selected"):
            self.selected.setRowCount(0)

    def matching_catalog(self):
        return (
            self.catalog_distro.currentText()
            == self.distro.currentText()
            and self.catalog_release.currentText()
            == self.release.currentText()
        )

    def run_worker(self, mode, args, callback):
        if self.worker is not None:
            QMessageBox.information(
                self,
                "Opération en cours",
                "Attends la fin de l'opération actuelle."
            )
            return False

        worker = Worker(mode, *args)
        self.worker = worker

        self.search_button.setEnabled(False)
        self.scan_button.setEnabled(False)

        worker.completed.connect(callback)
        worker.finished.connect(
            lambda: self.worker_finished(worker)
        )

        worker.start()
        return True

    def worker_finished(self, worker):
        if self.worker is worker:
            self.worker = None

        self.search_button.setEnabled(True)
        self.scan_button.setEnabled(True)

        worker.deleteLater()

    def search(self):
        query = self.query.text().strip()

        if not query or len(query) > 80:
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir entre 1 et 80 caractères."
            )
            return

        if not self.matching_catalog():
            QMessageBox.warning(
                self,
                "Catalogue",
                "Le catalogue doit correspondre au projet."
            )
            return

        context = self.revision

        self.results.setRowCount(0)
        self.app_note.setText("Recherche en cours...")

        self.run_worker(
            "search",
            (
                self.distro.currentText(),
                self.release.currentText(),
                query
            ),
            lambda data, error: self.search_done(
                data, error, context
            )
        )

    def search_done(self, rows, error, context):
        if context != self.revision:
            return

        if error:
            self.app_note.setText(
                "Recherche indisponible : " + error
            )
            return

        self.results.setSortingEnabled(False)

        for package in rows:
            row = self.results.rowCount()
            self.results.insertRow(row)

            values = [
                package["name"],
                package["version"],
                package["repo"],
                package["source"]
                + " — "
                + package["description"]
            ]

            for column, value in enumerate(values):
                self.cell(
                    self.results,
                    row,
                    column,
                    value,
                    package if column == 0 else None
                )

        self.results.setSortingEnabled(True)

        self.app_note.setText(
            f"{len(rows)} résultat(s). "
            "Double-cliquer pour ajouter."
        )

    def add_result(self, row, column):
        if not self.matching_catalog():
            return

        item = self.results.item(row, 0)

        if not item:
            return

        package = item.data(Qt.ItemDataRole.UserRole)

        if not package:
            return

        name = package["name"]

        if name in self.roots:
            return

        if self.distro.currentText() != "Arch Linux":
            self.roots[name] = package
            self.metadata[name] = package

            self.unresolved[name] = [
                "Dépendances à calculer avec le gestionnaire natif"
            ]

            self.refresh_selected()
            return

        context = self.revision

        self.app_note.setText(
            "Analyse des dépendances de " + name
        )

        self.run_worker(
            "resolve",
            ([name],),
            lambda data, error: self.app_resolved(
                data, error, package, context
            )
        )

    def app_resolved(self, data, error, package, context):
        if context != self.revision:
            return

        if error:
            self.app_note.setText("Erreur : " + error)
            return

        graph, metadata, warnings = data

        name = package["name"]

        self.roots[name] = package
        self.graph.update(graph)
        self.metadata.update(metadata)

        if warnings:
            self.unresolved[name] = warnings

        self.refresh_selected()

        self.app_note.setText(
            f"{name} ajouté · "
            f"{len(graph)} paquets examinés · "
            f"{len(warnings)} avertissement(s)"
        )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE_NAME.fullmatch(name):
            QMessageBox.warning(
                self,
                "Paquet",
                "Nom de paquet invalide."
            )
            return

        if name not in self.roots:
            package = {
                "name": name,
                "version": "?",
                "repo": "manuel",
                "size": None
            }

            self.roots[name] = package
            self.metadata[name] = package
            self.unresolved[name] = [
                "Dépendances non vérifiées"
            ]

            self.refresh_selected()

        self.manual.clear()

    def needed_apps(self):
        found = set()
        stack = list(self.roots)

        while stack:
            name = stack.pop()

            if name in found:
                continue

            found.add(name)
            stack.extend(self.graph.get(name, []))

        return found

    def human_size(self, size):
        if isinstance(size, (int, float)) and size >= 0:
            return f"{size / 1048576:.1f} Mio"

        return "Inconnue"

    def refresh_selected(self):
        self.selected.setRowCount(0)

        for name in sorted(self.needed_apps()):
            package = self.metadata.get(name, {})

            row = self.selected.rowCount()
            self.selected.insertRow(row)

            role = (
                "Application"
                if name in self.roots
                else "Dépendance"
            )

            if name in self.unresolved:
                role += " ⚠"

            values = [
                name,
                role,
                package.get("version", "?"),
                self.human_size(package.get("size"))
            ]

            for column, value in enumerate(values):
                self.cell(
                    self.selected,
                    row,
                    column,
                    value,
                    name if column == 0 else None
                )

    def remove_menu(self, position):
        item = self.selected.itemAt(position)

        if not item:
            return

        name = self.selected.item(
            item.row(), 0
        ).data(Qt.ItemDataRole.UserRole)

        if name not in self.roots:
            return

        menu = QMenu(self)

        action = menu.addAction(
            "Retirer l'application et ses dépendances orphelines"
        )

        selected_action = menu.exec(
            self.selected.viewport().mapToGlobal(position)
        )

        if selected_action != action:
            return

        before = self.needed_apps()

        self.roots.pop(name, None)
        self.unresolved.pop(name, None)

        after = self.needed_apps()

        self.refresh_selected()

        removed = max(0, len(before - after) - 1)

        self.app_note.setText(
            f"{name} retiré · "
            f"{removed} dépendance(s) orpheline(s) retirée(s)"
        )

    def system_categories(self):
        distro = self.distro.currentText()
        desktop = self.desktop.currentText()
        init = self.init_system.currentText()

        extra = EXTRA_PACKAGES[distro]

        categories = {
            "Base": list(extra["Base"]),
            "Initialisation": list(
                INIT_PACKAGES[distro].get(init, [])
            ),
            "Noyau": list(
                KERNELS[distro].get(
                    self.kernel.currentText(), []
                )
            ),
            "Bureau": list(
                DESKTOPS[distro].get(desktop, [])
            ),
            "Affichage": list(
                DISPLAY_PACKAGES[distro].get(
                    self.display.currentText(), []
                )
            ) if desktop != "Aucun" else [],
            "Audio": list(
                AUDIO_PACKAGES[distro].get(
                    self.audio.currentText(), []
                )
            )
        }

        for key, label in [
            ("wifi", "Wi-Fi"),
            ("bluetooth", "Bluetooth"),
            ("printing", "Impression"),
            ("firmware", "Firmwares"),
            ("calamares", "Calamares")
        ]:
            categories[label] = (
                list(extra[label])
                if self.options[key].isChecked()
                else []
            )

        categories["GRUB"] = (
            list(
                GRUB_PACKAGES[distro].get(
                    self.boot_mode.currentText(), []
                )
            )
            if self.bootloader.currentText() == "GRUB"
            else []
        )

        return categories

    def analyze_system(self):
        distro = self.distro.currentText()

        categories = self.system_categories()

        names = sorted({
            name
            for packages in categories.values()
            for name in packages
        })

        if distro != "Arch Linux":
            self.system_scan = {
                "names": names,
                "graph": {},
                "metadata": {},
                "complete": False,
                "warnings": [
                    "Analyse partielle : dépendances supplémentaires "
                    "à calculer avec le gestionnaire natif de "
                    + distro
                ]
            }

            self.system_note.setText(
                f"{distro} : {len(names)} paquets de départ identifiés.\n"
                "Analyse partielle — les dépendances supplémentaires "
                "seront calculées lors de la résolution native.\n"
                f"Initialisation : {self.init_system.currentText()}"
            )
            return

        context = self.revision

        self.system_note.setText(
            "Arch Linux : analyse récursive en cours..."
        )

        self.run_worker(
            "resolve",
            (names,),
            lambda data, error: self.system_resolved(
                data, error, context, names
            )
        )

    def system_resolved(self, data, error, context, names):
        if context != self.revision:
            return

        if error:
            self.system_note.setText(
                "Erreur d'analyse : " + error
            )
            return

        graph, metadata, warnings = data

        self.system_scan = {
            "names": names,
            "graph": graph,
            "metadata": metadata,
            "complete": False,
            "warnings": warnings
        }

        self.system_note.setText(
            f"Arch Linux : {len(graph)} paquets examinés.\n"
            f"{len(warnings)} avertissement(s).\n"
            "Analyse indicative : validation finale avec pacman nécessaire."
        )

    def all_packages(self):
        names = {
            name
            for packages in self.system_categories().values()
            for name in packages
        }

        names.update(self.needed_apps())

        graph = self.system_scan.get("graph", {})

        names.update(graph)

        for dependencies in graph.values():
            names.update(dependencies)

        return sorted(names)

    def build_project(self):
        layout = self.page("Projet / ISO")

        self.summary = QLabel(
            "Clique sur Vérifier pour afficher "
            "la liste des paquets et l'estimation ISO."
        )
        self.summary.setWordWrap(True)

        layout.addWidget(self.summary)

        self.preview = self.table([
            "Paquet",
            "Catégorie",
            "Version",
            "Taille compressée"
        ])

        self.preview.setColumnWidth(0, 340)
        self.preview.setColumnWidth(1, 180)
        self.preview.setColumnWidth(2, 150)

        layout.addWidget(self.preview, 2)

        self.report = QTextEdit()
        self.report.setReadOnly(True)

        layout.addWidget(self.report, 1)

        buttons = QHBoxLayout()

        verify = QPushButton("Vérifier")
        verify.clicked.connect(self.verify_project)

        export = QPushButton("Exporter le projet")
        export.setObjectName("primary")
        export.clicked.connect(self.export_project)

        buttons.addWidget(verify)
        buttons.addWidget(export)

        layout.addLayout(buttons)

    def verify_project(self):
        distro = self.distro.currentText()
        init = self.init_system.currentText()

        categories = self.system_categories()
        packages = self.all_packages()

        errors = []
        warnings = []

        if init not in INIT_SYSTEMS[distro]:
            errors.append(
                "Système d'initialisation incompatible."
            )

        if self.kernel.currentText() not in KERNELS[distro]:
            errors.append(
                "Variante du noyau non définie pour "
                + distro
            )

        if (
            self.desktop.currentText() != "Aucun"
            and self.display.currentText() == "Aucun"
        ):
            errors.append(
                "Le bureau nécessite un système graphique."
            )

        if (
            self.bootloader.currentText() == "GRUB"
            and not categories["GRUB"]
        ):
            errors.append(
                "Configuration GRUB non définie pour ce mode."
            )

        if distro == "Gentoo":
            warnings.append(
                "Gentoo : sélectionner un profil Portage "
                "compatible avec " + init + "."
            )

        if self.options["calamares"].isChecked():
            if not categories["Calamares"]:
                warnings.append(
                    "Calamares : paquet non vérifié "
                    "pour cette distribution."
                )

        if self.unresolved:
            warnings.append(
                f"{len(self.unresolved)} application(s) "
                "avec dépendances à vérifier."
            )

        if not self.system_scan:
            warnings.append(
                "Analyse système non lancée."
            )
        else:
            warnings.extend(
                self.system_scan.get("warnings", [])
            )

        warnings.append(
            "La liste ne représente pas nécessairement "
            "l'ensemble des dépendances finales."
        )

        self.preview.setRowCount(0)

        metadata = dict(
            self.system_scan.get("metadata", {})
        )
        metadata.update(self.metadata)

        known_bytes = 0
        unknown_count = 0

        for name in packages:
            package = metadata.get(name, {})
            size = package.get("size")

            role = next(
                (
                    category
                    for category, values in categories.items()
                    if name in values
                ),
                "Application"
                if name in self.roots
                else "Dépendance"
            )

            row = self.preview.rowCount()
            self.preview.insertRow(row)

            values = [
                name,
                role,
                package.get("version", "?"),
                self.human_size(size)
            ]

            for column, value in enumerate(values):
                self.cell(
                    self.preview,
                    row,
                    column,
                    value
                )

            if isinstance(size, (int, float)) and size >= 0:
                known_bytes += size
            else:
                unknown_count += 1

        # Estimation illustrative, non issue d'une
        # simulation complète du gestionnaire natif.
        low_mib = (
            known_bytes / 1048576
            + unknown_count * 2
            + 180
        )
        high_mib = (
            known_bytes / 1048576
            + unknown_count * 35
            + 700
        )

        self.summary.setText(
            f"Distribution : {distro} "
            f"{self.release.currentText()}  |  "
            f"Initialisation : {init}\n"
            f"Paquets identifiés : {len(packages)}  |  "
            f"Tailles inconnues : {unknown_count}\n"
            f"Fourchette ISO très approximative : "
            f"{low_mib / 1024:.2f} à "
            f"{high_mib / 1024:.2f} Gio"
        )

        self.report.setPlainText(
            "ERREURS\n"
            + ("\n".join(errors) or "Aucune erreur de formulaire")
            + "\n\nAVERTISSEMENTS\n"
            + "\n".join(warnings)
            + "\n\nSYSTÈME D'INITIALISATION\n"
            + init
            + "\n\nCHARGEUR DE DÉMARRAGE\n"
            + self.bootloader.currentText()
            + " / "
            + self.boot_mode.currentText()
        )

        config = {
            "schema": 17,
            "app_version": VERSION,
            "distribution": distro,
            "version": self.release.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentText(),
            "init_system": init,
            "init_packages": categories["Initialisation"],
            "bootloader": self.bootloader.currentText(),
            "boot_mode": self.boot_mode.currentText(),
            "calamares": self.options["calamares"].isChecked(),
            "categories": categories,
            "applications": sorted(self.roots),
            "application_dependencies": self.graph,
            "system_scan": self.system_scan,
            "all_packages": packages,
            "errors": errors,
            "warnings": warnings,
            "iso_estimate": {
                "known_compressed_bytes": known_bytes,
                "unknown_packages": unknown_count,
                "low_mib": round(low_mib, 1),
                "high_mib": round(high_mib, 1)
            }
        }

        return config, errors

    def export_project(self):
        config, errors = self.verify_project()

        if errors:
            QMessageBox.warning(
                self,
                "Export",
                "Corrige les erreurs avant l'export."
            )
            return

        directory = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier vide",
            str(Path.home())
        )

        if not directory:
            return

        path = Path(directory)

        if any(path.iterdir()):
            QMessageBox.warning(
                self,
                "Export",
                "Choisir un dossier vide."
            )
            return

        (path / "project_v1_7.json").write_text(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_7.txt").write_text(
            "\n".join(config["all_packages"]) + "\n",
            encoding="utf-8"
        )

        init_note = (
            "SYSTÈME D'INITIALISATION\n"
            f"Distribution : {config['distribution']}\n"
            f"Version : {config['version']}\n"
            f"Init : {config['init_system']}\n"
            "Paquets : "
            + ", ".join(config["init_packages"])
            + "\n\n"
        )

        if config["distribution"] == "Gentoo":
            init_note += (
                "IMPORTANT : sélectionner un profil Portage "
                "compatible avec le système d'initialisation.\n"
                "Le choix d'un paquet seul ne suffit pas.\n"
            )

        (path / "INIT_v1_7.txt").write_text(
            init_note,
            encoding="utf-8"
        )

        boot_note = (
            "PLAN GRUB / CALAMARES — NON EXÉCUTABLE\n"
            f"Distribution : {config['distribution']}\n"
            f"Bootloader : {config['bootloader']}\n"
            f"Mode : {config['boot_mode']}\n"
            "Paquets GRUB : "
            + ", ".join(config["categories"]["GRUB"])
            + "\n\n"
            "Le module bootloader de Calamares doit être "
            "configuré pour le disque cible.\n"
            "L'ISO Live possède une configuration "
            "de démarrage distincte.\n"
        )

        (path / "GRUB_Calamares_v1_7.txt").write_text(
            boot_note,
            encoding="utf-8"
        )

        (path / "README_v1_7.txt").write_text(
            "Universal Linux Builder v1.7\n\n"
            "Export de préparation uniquement.\n"
            "Aucune ISO amorçable n'est créée.\n"
            "Les dépendances doivent être validées "
            "avec le gestionnaire natif.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Projet v1.7 exporté.\n\n"
            "Configuration, paquets, initialisation "
            "et plan GRUB/Calamares enregistrés."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())
