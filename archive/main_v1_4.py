import sys
import json
import re
import urllib.request
import urllib.parse

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QCheckBox, QFileDialog, QMessageBox,
    QTextEdit, QMenu, QAbstractItemView, QSplitter
)

VERSION = "1.4"

DISTROS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["43", "42"],
    "Slackware": ["15.0", "current"],
    "Gentoo": ["stable", "testing"],
    "Arch Linux": ["rolling"]
}

DESKTOPS = ["Aucun", "GNOME", "KDE Plasma", "Xfce", "Budgie"]

KERNELS = {
    "Arch Linux": {
        "Stable": ["linux"],
        "LTS": ["linux-lts"],
        "Hardened": ["linux-hardened"]
    },
    "Debian": {
        "Stable": ["linux-image-amd64"]
    },
    "Fedora": {
        "Stable": ["kernel"]
    },
    "Slackware": {
        "Stable": ["kernel-generic"]
    },
    "Gentoo": {
        "Stable": ["sys-kernel/gentoo-kernel"]
    }
}

# Profils de depart des environnements graphiques.
# Les dependances transitives doivent etre validees par
# le gestionnaire natif de chaque distribution.

PROFILES = {
    "Arch Linux": {
        "GNOME": (
            [
                "gnome-shell", "gnome-session",
                "gnome-control-center", "nautilus",
                "gnome-terminal", "gdm", "networkmanager",
                "mesa", "xdg-desktop-portal-gnome"
            ],
            "gdm.service", "Wayland"
        ),
        "KDE Plasma": (
            [
                "plasma-desktop", "plasma-workspace",
                "konsole", "dolphin", "sddm",
                "networkmanager", "mesa",
                "xdg-desktop-portal-kde"
            ],
            "sddm.service", "Wayland"
        ),
        "Xfce": (
            [
                "xfce4-session", "xfce4-panel", "xfwm4",
                "xfdesktop", "thunar", "xfce4-settings",
                "xfce4-terminal", "lightdm",
                "lightdm-gtk-greeter", "xorg-server",
                "networkmanager", "mesa"
            ],
            "lightdm.service", "X11"
        ),
        "Budgie": (
            [
                "budgie-desktop", "budgie-session",
                "budgie-control-center", "gdm",
                "networkmanager", "mesa"
            ],
            "gdm.service", "Wayland"
        )
    },
    "Debian": {
        "GNOME": (
            [
                "gnome-core", "gdm3",
                "network-manager", "mesa-utils"
            ],
            "gdm3.service", "Wayland"
        ),
        "KDE Plasma": (
            [
                "kde-plasma-desktop", "sddm",
                "network-manager", "mesa-utils"
            ],
            "sddm.service", "Wayland"
        ),
        "Xfce": (
            [
                "xfce4", "xfce4-terminal",
                "lightdm", "lightdm-gtk-greeter",
                "xserver-xorg", "network-manager"
            ],
            "lightdm.service", "X11"
        ),
        "Budgie": (
            [
                "budgie-desktop", "lightdm",
                "lightdm-gtk-greeter", "xserver-xorg",
                "network-manager"
            ],
            "lightdm.service", "X11"
        )
    },
    "Fedora": {
        "GNOME": (
            [
                "gnome-shell", "gnome-session",
                "gdm", "NetworkManager",
                "mesa-dri-drivers"
            ],
            "gdm.service", "Wayland"
        ),
        "KDE Plasma": (
            [
                "plasma-desktop", "plasma-workspace",
                "sddm", "NetworkManager",
                "mesa-dri-drivers"
            ],
            "sddm.service", "Wayland"
        ),
        "Xfce": (
            [
                "xfce4-session", "xfce4-panel",
                "xfwm4", "xfdesktop", "thunar",
                "lightdm", "lightdm-gtk",
                "xorg-x11-server-Xorg", "NetworkManager"
            ],
            "lightdm.service", "X11"
        ),
        "Budgie": (
            [
                "budgie-desktop", "gdm",
                "NetworkManager", "mesa-dri-drivers"
            ],
            "gdm.service", "Wayland"
        )
    },
    "Gentoo": {
        "GNOME": (
            [
                "gnome-base/gnome-shell",
                "gnome-base/gnome-session",
                "gnome-base/gdm",
                "net-misc/networkmanager"
            ],
            "gdm.service", "Wayland"
        ),
        "KDE Plasma": (
            [
                "kde-plasma/plasma-desktop",
                "kde-plasma/plasma-workspace",
                "x11-misc/sddm",
                "net-misc/networkmanager"
            ],
            "sddm.service", "Wayland"
        ),
        "Xfce": (
            [
                "xfce-base/xfce4-session",
                "xfce-base/xfce4-panel",
                "xfce-base/xfwm4",
                "x11-misc/lightdm",
                "x11-base/xorg-server",
                "net-misc/networkmanager"
            ],
            "lightdm.service", "X11"
        ),
        "Budgie": (
            [
                "gnome-extra/budgie-desktop",
                "gnome-base/gdm",
                "net-misc/networkmanager"
            ],
            "gdm.service", "Wayland"
        )
    },
    "Slackware": {
        "KDE Plasma": (
            [
                "kde/plasma-workspace",
                "kde/plasma-desktop",
                "kde/sddm"
            ],
            "sddm", "X11"
        ),
        "Xfce": (
            [
                "xfce/xfce4-session",
                "xfce/xfce4-panel",
                "xfce/xfwm4"
            ],
            "xdm", "X11"
        )
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
    "Arch Linux": {
        "PipeWire": [
            "pipewire", "wireplumber",
            "pipewire-pulse", "pipewire-alsa"
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
    }
}

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:/-]{0,120}$")

LIGHT = """
QWidget {
    background: #f4f6fa;
    color: #202936;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 5px;
    selection-background-color: #cfe4ff;
    selection-color: #152b49;
}
QHeaderView::section {
    background: #e8eff9;
    color: #20354e;
    padding: 9px;
    border: 0;
    font-weight: 700;
}
QPushButton {
    background: #e4ebf5;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px;
    font-weight: 600;
}
QPushButton:hover {
    background: #d5e7ff;
}
QPushButton#primary {
    background: #2677db;
    color: white;
    border: 0;
}
QTabBar::tab {
    padding: 12px 18px;
}
QTabBar::tab:selected {
    color: #2677db;
    border-bottom: 3px solid #2677db;
}
QLabel#title {
    font-size: 23px;
    font-weight: 700;
}
"""

DARK = """
QWidget {
    background: #151a23;
    color: #e4e9f2;
    font: 13px "Segoe UI";
}
QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: #202735;
    color: #edf2fa;
    border: 1px solid #435169;
    border-radius: 8px;
    padding: 5px;
    selection-background-color: #2266a7;
    selection-color: white;
}
QHeaderView::section {
    background: #303c50;
    color: #f0f4fc;
    padding: 9px;
    border: 0;
    font-weight: 700;
}
QPushButton {
    background: #303c50;
    color: #edf2fa;
    border: 1px solid #46556d;
    border-radius: 8px;
    padding: 9px;
    font-weight: 600;
}
QPushButton:hover {
    background: #40516c;
}
QPushButton#primary {
    background: #2878d9;
    color: white;
    border: 0;
}
QTabBar::tab {
    padding: 12px 18px;
}
QTabBar::tab:selected {
    color: #7db7ff;
    border-bottom: 3px solid #398cf1;
}
QLabel#title {
    font-size: 23px;
    font-weight: 700;
}
"""


# ============================================================
# CATALOGUE DES APPLICATIONS
# ============================================================

def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.4",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def lookup(distro, query):
    q = urllib.parse.quote(query)

    if distro == "Arch Linux":
        data = fetch(
            "https://archlinux.org/packages/search/json/?q=" + q
        )

        return [
            {
                "name": p["pkgname"],
                "version": str(p.get("pkgver", "")),
                "repo": p.get("repo", ""),
                "arch": p.get("arch", ""),
                "description": p.get("pkgdesc") or "",
                "size": p.get("compressed_size"),
                "verified": True
            }
            for p in data.get("results", [])
            if p.get("arch") in ("x86_64", "any")
        ][:150]

    data = fetch(
        "https://repology.org/api/v1/projects/?search=" + q
    )

    if not isinstance(data, dict):
        raise ValueError("Catalogue non disponible")

    prefix = {
        "Debian": "debian_",
        "Fedora": "fedora_",
        "Slackware": "slackware_",
        "Gentoo": "gentoo"
    }[distro]

    result = {}

    for project, entries in data.items():
        if not isinstance(entries, list):
            continue

        for p in entries:
            repo = str(p.get("repo", ""))

            if not repo.startswith(prefix):
                continue

            name = str(
                p.get("binname")
                or p.get("visiblename")
                or project
            )

            if distro == "Gentoo" and "/" not in name:
                continue

            if not SAFE.fullmatch(name):
                continue

            result[(name, repo)] = {
                "name": name,
                "version": str(p.get("version", "")),
                "repo": repo,
                "arch": "",
                "description": p.get("summary") or "",
                "size": None,
                "verified": False
            }

    return list(result.values())[:150]


# ============================================================
# RESOLUTION ARCH LINUX
# ============================================================

def resolve_arch(roots, limit=250):
    graph = {}
    meta = {}
    warnings = []
    queue = list(roots)
    seen = set()

    while queue:
        p = queue.pop(0)
        name = p["name"]

        if name in seen:
            continue

        if len(seen) >= limit:
            warnings.append("Limite de 250 paquets atteinte")
            break

        seen.add(name)
        meta[name] = dict(p)

        try:
            path = "/".join(
                urllib.parse.quote(str(p[k]), safe="")
                for k in ("repo", "arch", "name")
            )

            info = fetch(
                "https://archlinux.org/packages/"
                + path + "/json/"
            )

        except Exception as exc:
            graph[name] = []
            warnings.append(
                f"{name}: métadonnées indisponibles ({exc})"
            )
            continue

        meta[name]["size"] = info.get("compressed_size")
        deps = []

        for raw in info.get("depends") or []:
            dep = re.split(
                r"[<>=:]",
                str(raw),
                1
            )[0].strip()

            if not SAFE.fullmatch(dep):
                warnings.append(
                    f"{name}: dépendance illisible {raw}"
                )
                continue

            deps.append(dep)

            if dep in seen or any(
                x["name"] == dep for x in queue
            ):
                continue

            try:
                matches = [
                    x for x in lookup("Arch Linux", dep)
                    if x["name"] == dep
                ]

                if matches:
                    queue.append(matches[0])
                else:
                    warnings.append(
                        f"{name}: {dep} non résolue "
                        "(fournisseur virtuel possible)"
                    )

            except Exception as exc:
                warnings.append(
                    f"{name}: {dep} non vérifiée ({exc})"
                )

        graph[name] = list(dict.fromkeys(deps))

    return graph, meta, warnings


def resolve_desktop(seeds):
    roots = []
    missing = []

    for name in seeds:
        try:
            matches = [
                p for p in lookup("Arch Linux", name)
                if p["name"] == name
            ]

            if matches:
                roots.append(matches[0])
            else:
                missing.append(
                    name + " : paquet de départ introuvable"
                )

        except Exception as exc:
            missing.append(name + " : " + str(exc))

    if not roots:
        return {}, {}, missing

    graph, meta, warnings = resolve_arch(roots)

    return graph, meta, missing + warnings


# ============================================================
# THREADS
# ============================================================

class Worker(QThread):
    completed = Signal(object, str)

    def __init__(self, mode, *args):
        super().__init__()
        self.mode = mode
        self.args = args

    def run(self):
        try:
            if self.mode == "search":
                result = lookup(*self.args)
            elif self.mode == "desktop":
                result = resolve_desktop(*self.args)
            else:
                result = resolve_arch(*self.args)

            self.completed.emit(result, "")

        except Exception as exc:
            self.completed.emit(None, str(exc))


# ============================================================
# INTERFACE
# ============================================================

class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.4"
        )
        self.resize(1280, 850)

        self.roots = {}
        self.graph = {}
        self.meta = {}
        self.unresolved = {}

        self.worker = None
        self.desktop_scan = {}
        self.desktop_warnings = []

        host = QWidget()
        self.setCentralWidget(host)

        outer = QVBoxLayout(host)
        top = QHBoxLayout()

        title = QLabel("Universal Linux Builder")
        title.setObjectName("title")

        top.addWidget(title)
        top.addStretch()
        top.addWidget(QLabel("Thème"))

        self.theme = QComboBox()
        self.theme.addItems([
            "Automatique", "Clair", "Sombre"
        ])

        self.theme.currentTextChanged.connect(
            self.apply_theme
        )

        top.addWidget(self.theme)
        outer.addLayout(top)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_apps()
        self.make_project()

        self.distro_changed(self.distro.currentText())
        self.apply_theme()

        QApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.apply_theme()
        )

    def apply_theme(self, *_):
        mode = self.theme.currentText()

        if mode == "Automatique":
            dark = (
                QApplication.styleHints().colorScheme()
                == Qt.ColorScheme.Dark
            )
        else:
            dark = mode == "Sombre"

        self.setStyleSheet(DARK if dark else LIGHT)

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.tabs.addTab(widget, name)
        return layout

    def combo(self, values):
        c = QComboBox()
        c.addItems(values)
        return c

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):
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

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def make_system(self):
        layout = self.page("Système")
        form = QFormLayout()

        self.desktop = self.combo(DESKTOPS)
        self.display = self.combo([
            "Aucun", "X11", "Wayland"
        ])
        self.audio = self.combo([
            "Aucun", "PipeWire", "PulseAudio", "ALSA"
        ])

        # CORRECTIF V1.4 :
        # Les trois variantes sont toujours affichees.
        self.kernel = self.combo([
            "Stable", "LTS", "Hardened"
        ])

        for label, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau Linux", self.kernel)
        ]:
            form.addRow(label, widget)

        layout.addLayout(form)

        self.kernel_note = QLabel()
        self.kernel_note.setWordWrap(True)
        layout.addWidget(self.kernel_note)

        self.desktop_note = QLabel()
        self.desktop_note.setWordWrap(True)
        layout.addWidget(self.desktop_note)

        self.options = {}

        for key, label, checked in [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", True),
            ("printing", "Imprimantes / CUPS", False),
            (
                "firmware",
                "Firmwares et détection matérielle",
                True
            ),
            ("calamares", "Préparer Calamares", True)
        ]:
            box = QCheckBox(label)
            box.setChecked(checked)

            self.options[key] = box
            layout.addWidget(box)

        self.scan_button = QPushButton(
            "Analyser les dépendances du bureau (Arch Linux)"
        )

        self.scan_button.clicked.connect(
            self.scan_desktop
        )

        layout.addWidget(self.scan_button)
        layout.addStretch()

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )
        self.kernel.currentTextChanged.connect(
            self.kernel_changed
        )

    def distro_changed(self, distro):
        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(DISTROS[distro])
        self.release.blockSignals(False)

        if hasattr(self, "desktop"):
            old = self.desktop.currentText()

            choices = (
                ["Aucun", "KDE Plasma", "Xfce"]
                if distro == "Slackware"
                else DESKTOPS
            )

            self.desktop.blockSignals(True)
            self.desktop.clear()
            self.desktop.addItems(choices)

            self.desktop.setCurrentText(
                old if old in choices else "Aucun"
            )

            self.desktop.blockSignals(False)

            self.desktop_changed(
                self.desktop.currentText()
            )
            self.kernel_changed()

        if hasattr(self, "repo_distro"):
            self.repo_distro.setCurrentText(distro)
            self.repo_release.setCurrentText(
                self.release.currentText()
            )

        self.reset_apps()

    def release_changed(self, version):
        if hasattr(self, "repo_release"):
            self.repo_release.setCurrentText(version)

        self.reset_apps()
        self.desktop_scan = {}
        self.desktop_warnings = []

    def kernel_changed(self, *_):
        distro = self.distro.currentText()
        choice = self.kernel.currentText()

        supported = choice in KERNELS[distro]

        if supported:
            self.kernel_note.setText(
                "✓ Paquet noyau : "
                + ", ".join(KERNELS[distro][choice])
            )
        else:
            self.kernel_note.setText(
                "⚠ " + choice
                + " : aucun paquet officiel vérifié "
                "dans ce profil. Export de préparation "
                "uniquement."
            )

    def desktop_changed(self, desktop):
        self.desktop_scan = {}
        self.desktop_warnings = []

        if desktop == "Aucun":
            self.display.setCurrentText("Aucun")
            self.desktop_note.setText(
                "Aucun bureau graphique sélectionné."
            )
            return

        profile = PROFILES.get(
            self.distro.currentText(), {}
        ).get(desktop)

        if profile:
            packages, service, display = profile

            self.display.setCurrentText(display)

            self.desktop_note.setText(
                f"Profil {desktop} : "
                f"{len(packages)} paquets de départ · "
                f"Connexion : {service} · "
                f"Session : {display}. "
                "Les dépendances complètes "
                "doivent être résolues."
            )
        else:
            self.desktop_note.setText(
                "⚠ Aucun profil disponible pour ce bureau."
            )

    # --------------------------------------------------------
    # TABLEAUX
    # --------------------------------------------------------

    def table(self, columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)

        table.horizontalHeader().setStretchLastSection(True)
        return table

    def cell(self, table, row, column, value, data=None):
        item = QTableWidgetItem(str(value))

        if data is not None:
            item.setData(
                Qt.ItemDataRole.UserRole, data
            )

        table.setItem(row, column, item)

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def make_apps(self):
        layout = self.page("Applications")
        form = QFormLayout()

        self.repo_distro = self.combo(list(DISTROS))
        self.repo_release = self.combo([])

        form.addRow("Dépôts", self.repo_distro)
        form.addRow("Branche", self.repo_release)

        layout.addLayout(form)

        self.repo_distro.currentTextChanged.connect(
            self.repo_changed
        )

        row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher firefox, vlc, gimp..."
        )
        self.query.returnPressed.connect(
            self.start_search
        )

        self.search_button = QPushButton("Rechercher")
        self.search_button.setObjectName("primary")
        self.search_button.clicked.connect(
            self.start_search
        )

        row.addWidget(self.query)
        row.addWidget(self.search_button)
        layout.addLayout(row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)

        results_layout.addWidget(
            QLabel("Résultats — double-clic pour ajouter")
        )

        self.results = self.table([
            "Application", "Version", "Dépôt", "Description"
        ])

        self.results.setColumnWidth(0, 250)
        self.results.setColumnWidth(1, 130)
        self.results.setColumnWidth(2, 160)

        self.results.setSortingEnabled(True)
        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        results_layout.addWidget(self.results)
        splitter.addWidget(results_panel)

        selected_panel = QWidget()
        selected_layout = QVBoxLayout(selected_panel)

        selected_layout.addWidget(
            QLabel(
                "Applications et dépendances "
                "— clic droit pour supprimer"
            )
        )

        self.selected = self.table([
            "Paquet", "Rôle", "Version", "Taille compressée"
        ])

        self.selected.setColumnWidth(0, 300)
        self.selected.setColumnWidth(1, 210)

        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.selected.customContextMenuRequested.connect(
            self.remove_menu
        )

        selected_layout.addWidget(self.selected)
        splitter.addWidget(selected_panel)
        splitter.setSizes([380, 250])

        layout.addWidget(splitter, 1)

        manual_row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Ajouter un paquet manuellement (non résolu)"
        )

        button = QPushButton("Ajouter")
        button.clicked.connect(self.add_manual)

        manual_row.addWidget(self.manual)
        manual_row.addWidget(button)
        layout.addLayout(manual_row)

        self.status = QLabel(
            "Recherche intégrée : Arch officiel, "
            "autres distributions via index tiers."
        )

        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.repo_changed(
            self.repo_distro.currentText()
        )

    def repo_changed(self, distro):
        self.repo_release.blockSignals(True)
        self.repo_release.clear()
        self.repo_release.addItems(DISTROS[distro])
        self.repo_release.blockSignals(False)

        self.reset_apps()

    def reset_apps(self):
        if hasattr(self, "results"):
            self.results.setRowCount(0)

        if hasattr(self, "selected"):
            self.selected.setRowCount(0)

        self.roots.clear()
        self.graph.clear()
        self.meta.clear()
        self.unresolved.clear()

        self.desktop_scan = {}
        self.desktop_warnings = []

    def matching(self):
        return (
            self.repo_distro.currentText()
            == self.distro.currentText()
            and
            self.repo_release.currentText()
            == self.release.currentText()
        )

    # --------------------------------------------------------
    # OPERATIONS EN ARRIERE-PLAN
    # --------------------------------------------------------

    def start_worker(self, mode, args, callback):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Patientez",
                "Une opération est déjà en cours."
            )
            return False

        self.search_button.setEnabled(False)
        self.scan_button.setEnabled(False)

        worker = Worker(mode, *args)
        self.worker = worker

        worker.completed.connect(callback)
        worker.finished.connect(
            lambda: self.finish_worker(worker)
        )

        worker.start()
        return True

    def finish_worker(self, worker):
        self.search_button.setEnabled(True)
        self.scan_button.setEnabled(True)

        if self.worker is worker:
            self.worker = None

        worker.deleteLater()

    def start_search(self):
        query = self.query.text().strip()

        if not query or len(query) > 80:
            QMessageBox.warning(
                self, "Recherche",
                "Saisir un nom de 80 caractères maximum."
            )
            return

        if not self.matching():
            QMessageBox.warning(
                self, "Dépôts",
                "La branche doit correspondre au projet."
            )
            return

        self.results.setRowCount(0)
        self.status.setText("Recherche en cours...")

        context = (
            self.distro.currentText(),
            self.release.currentText()
        )

        self.start_worker(
            "search",
            (context[0], query),
            lambda rows, error: self.search_done(
                rows, error, context
            )
        )

    def search_done(self, rows, error, context):
        if context != (
            self.distro.currentText(),
            self.release.currentText()
        ):
            return

        if error:
            self.status.setText(
                "Recherche impossible : " + error
            )
            return

        self.results.setSortingEnabled(False)

        for package in rows:
            row = self.results.rowCount()
            self.results.insertRow(row)

            values = (
                package["name"],
                package["version"],
                package["repo"],
                package["description"]
            )

            for column, value in enumerate(values):
                self.cell(
                    self.results,
                    row,
                    column,
                    value,
                    package if column == 0 else None
                )

        self.results.setSortingEnabled(True)

        self.status.setText(
            f"{len(rows)} résultat(s). "
            "Double-cliquer pour ajouter."
        )

    # --------------------------------------------------------
    # AJOUT DES APPLICATIONS
    # --------------------------------------------------------

    def add_result(self, row, _column):
        if not self.matching():
            return

        item = self.results.item(row, 0)

        if not item:
            return

        package = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not package or package["name"] in self.roots:
            return

        if self.distro.currentText() != "Arch Linux":
            self.roots[package["name"]] = package
            self.meta[package["name"]] = package

            self.unresolved[package["name"]] = [
                "Résolution native requise"
            ]

            self.refresh()
            return

        context = (
            self.distro.currentText(),
            self.release.currentText()
        )

        self.status.setText(
            "Résolution Arch en cours..."
        )

        self.start_worker(
            "resolve",
            ([package],),
            lambda result, error: self.application_done(
                result, error, package, context
            )
        )

    def application_done(self, result, error, package, context):
        if context != (
            self.distro.currentText(),
            self.release.currentText()
        ):
            return

        if error:
            self.status.setText("Erreur : " + error)
            return

        graph, metadata, warnings = result

        self.roots[package["name"]] = package
        self.graph.update(graph)
        self.meta.update(metadata)

        if warnings:
            self.unresolved[package["name"]] = warnings

        self.refresh()

        self.status.setText(
            f"{package['name']} ajouté · "
            f"{len(graph)} paquets inspectés · "
            f"{len(warnings)} avertissement(s)."
        )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):
            QMessageBox.warning(
                self, "Paquet", "Nom invalide."
            )
            return

        if name not in self.roots:
            package = {
                "name": name,
                "version": "?",
                "repo": "Manuel",
                "size": None
            }

            self.roots[name] = package
            self.meta[name] = package

            self.unresolved[name] = [
                "Dépendances non résolues"
            ]

            self.refresh()

        self.manual.clear()

    # --------------------------------------------------------
    # ANALYSE DU BUREAU
    # --------------------------------------------------------

    def scan_desktop(self):
        distro = self.distro.currentText()
        desktop = self.desktop.currentText()

        profile = PROFILES.get(
            distro, {}
        ).get(desktop)

        if not profile:
            QMessageBox.information(
                self,
                "Bureau",
                "Aucun bureau ou profil non disponible."
            )
            return

        if distro != "Arch Linux":
            QMessageBox.information(
                self,
                "Résolution",
                "Les paquets de départ sont déjà ajoutés.\n\n"
                "La résolution complète exige le gestionnaire "
                "natif de " + distro + "."
            )
            return

        seeds = profile[0]

        self.desktop_note.setText(
            "Recherche des dépendances du bureau en cours..."
        )

        context = (
            distro,
            self.release.currentText(),
            desktop
        )

        self.start_worker(
            "desktop",
            (seeds,),
            lambda result, error: self.desktop_done(
                result, error, context
            )
        )

    def desktop_done(self, result, error, context):
        if context != (
            self.distro.currentText(),
            self.release.currentText(),
            self.desktop.currentText()
        ):
            return

        if error:
            self.desktop_note.setText(
                "⚠ Analyse impossible : " + error
            )
            return

        graph, metadata, warnings = result

        self.desktop_scan = {
            "graph": graph,
            "meta": metadata
        }

        self.desktop_warnings = warnings

        self.desktop_note.setText(
            f"Bureau {context[2]} : "
            f"{len(graph)} paquets analysés, "
            f"{len(warnings)} avertissement(s). "
            "Résolution indicative, à valider avec pacman."
        )

    # --------------------------------------------------------
    # DEPENDANCES DES APPLICATIONS
    # --------------------------------------------------------

    def needed(self):
        used = set()
        stack = list(self.roots)

        while stack:
            name = stack.pop()

            if name in used:
                continue

            used.add(name)
            stack.extend(self.graph.get(name, []))

        return used

    def human(self, size):
        if isinstance(size, (int, float)) and size >= 0:
            return f"{size / 1048576:.1f} Mio"

        return "Inconnue"

    def refresh(self):
        self.selected.setRowCount(0)

        for name in sorted(self.needed()):
            package = self.meta.get(name, {})

            row = self.selected.rowCount()
            self.selected.insertRow(row)

            role = (
                "Application"
                if name in self.roots
                else "Dépendance"
            )

            if name in self.unresolved:
                role += " ⚠"

            values = (
                name,
                role,
                package.get("version", "?"),
                self.human(package.get("size"))
            )

            for column, value in enumerate(values):
                self.cell(
                    self.selected,
                    row,
                    column,
                    value,
                    name if column == 0 else None
                )

    def remove_menu(self, point):
        item = self.selected.itemAt(point)

        if not item:
            return

        first = self.selected.item(item.row(), 0)
        name = first.data(Qt.ItemDataRole.UserRole)

        if name not in self.roots:
            QMessageBox.information(
                self,
                "Dépendance",
                "Ce paquet est nécessaire à une application."
            )
            return

        menu = QMenu(self)

        action = menu.addAction(
            "Supprimer et retirer les dépendances orphelines"
        )

        chosen = menu.exec(
            self.selected.viewport().mapToGlobal(point)
        )

        if chosen != action:
            return

        before = self.needed()

        self.roots.pop(name, None)
        self.unresolved.pop(name, None)

        after = self.needed()

        self.refresh()

        removed = max(
            0,
            len(before - after) - 1
        )

        self.status.setText(
            f"{name} retiré · "
            f"{removed} dépendance(s) orpheline(s) retirée(s)."
        )

    # --------------------------------------------------------
    # COMPOSANTS SYSTEME
    # --------------------------------------------------------

    def profile(self):
        return PROFILES.get(
            self.distro.currentText(), {}
        ).get(self.desktop.currentText())

    def system_packages(self):
        distro = self.distro.currentText()
        choice = self.kernel.currentText()

        packages = list(
            KERNELS[distro].get(choice, [])
        )

        profile = self.profile()

        if profile:
            packages += profile[0]

        packages += AUDIO.get(distro, {}).get(
            self.audio.currentText(), []
        )

        if distro == "Arch Linux":
            packages += [
                "base", "linux-firmware",
                "pciutils", "usbutils", "kmod"
            ]

            if self.options["wifi"].isChecked():
                packages.append("iwd")

            if self.options["bluetooth"].isChecked():
                packages += ["bluez", "bluez-utils"]

            if self.options["printing"].isChecked():
                packages.append("cups")

            if self.options["calamares"].isChecked():
                packages.append("calamares")

        elif distro == "Debian":
            packages += [
                "systemd-sysv", "udev",
                "pciutils", "usbutils", "kmod"
            ]

            if self.options["wifi"].isChecked():
                packages.append("wpasupplicant")

            if self.options["bluetooth"].isChecked():
                packages.append("bluez")

            if self.options["printing"].isChecked():
                packages.append("cups")

            if self.options["calamares"].isChecked():
                packages.append("calamares")

            if self.options["firmware"].isChecked():
                packages.append("firmware-linux-free")

        return sorted(set(packages))

    def all_packages(self):
        packages = set(self.system_packages())
        packages.update(self.needed())

        graph = self.desktop_scan.get("graph", {})

        packages.update(graph)

        for dependencies in graph.values():
            packages.update(dependencies)

        return sorted(packages)

    # --------------------------------------------------------
    # PROJET / ISO
    # --------------------------------------------------------

    def make_project(self):
        layout = self.page("Projet / ISO")

        self.summary = QLabel(
            "Cliquez sur Vérifier pour afficher les paquets "
            "et estimer la taille."
        )

        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.preview = self.table([
            "Paquet", "Catégorie", "Version", "Taille connue"
        ])

        self.preview.setColumnWidth(0, 350)
        self.preview.setColumnWidth(1, 210)
        self.preview.setColumnWidth(2, 140)

        layout.addWidget(self.preview, 2)

        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)

        row = QHBoxLayout()

        button = QPushButton("Vérifier")
        button.clicked.connect(self.check)

        export = QPushButton("Exporter le projet")
        export.setObjectName("primary")
        export.clicked.connect(self.export)

        row.addWidget(button)
        row.addWidget(export)
        layout.addLayout(row)

    def config(self):
        profile = self.profile()

        distro = self.distro.currentText()
        kernel = self.kernel.currentText()

        config = {
            "schema": 14,
            "app_version": VERSION,
            "distribution": distro,
            "version": self.release.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": kernel,
            "kernel_packages": KERNELS[distro].get(
                kernel, []
            ),
            "kernel_supported_in_profile": (
                kernel in KERNELS[distro]
            ),
            "display_manager_service": (
                profile[1] if profile else None
            ),
            "desktop_seed_packages": (
                profile[0] if profile else []
            ),
            "desktop_dependencies_scanned": bool(
                self.desktop_scan
            ),
            "desktop_warnings": self.desktop_warnings,
            "applications": sorted(self.roots),
            "dependency_graph": self.graph,
            "application_packages": sorted(self.needed()),
            "system_packages": self.system_packages(),
            "all_packages": self.all_packages(),
            "unresolved": self.unresolved
        }

        config.update({
            key: value.isChecked()
            for key, value in self.options.items()
        })

        return config

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def check(self):
        config = self.config()

        errors = []
        warnings = []

        if not config["kernel_supported_in_profile"]:
            errors.append(
                "Noyau "
                + config["kernel"]
                + " non pris en charge par le profil "
                + config["distribution"]
                + "."
            )

        if (
            config["desktop"] == "Aucun"
            and config["display"] != "Aucun"
        ):
            errors.append(
                "Sans bureau, choisir Affichage : Aucun."
            )

        if (
            config["desktop"] != "Aucun"
            and config["display"] == "Aucun"
        ):
            errors.append(
                "Le bureau nécessite un système graphique."
            )

        if (
            config["desktop"] != "Aucun"
            and not self.profile()
        ):
            errors.append(
                "Profil du bureau indisponible."
            )

        if self.unresolved:
            warnings.append(
                f"{len(self.unresolved)} application(s) "
                "dont les dépendances restent incomplètes."
            )

        if (
            config["desktop"] != "Aucun"
            and not config["desktop_dependencies_scanned"]
        ):
            warnings.append(
                "Dépendances transitives du bureau "
                "non vérifiées dans cette application."
            )

        warnings += self.desktop_warnings

        warnings.append(
            "Les paquets du système de base, "
            "les fournisseurs virtuels et les dépendances "
            "transitives peuvent manquer."
        )

        self.preview.setRowCount(0)

        known = 0
        count = 0
        unknown = 0

        metadata = dict(
            self.desktop_scan.get("meta", {})
        )
        metadata.update(self.meta)

        for name in config["all_packages"]:
            package = metadata.get(name, {})
            size = package.get("size")

            if name in config["system_packages"]:
                role = "Système / Bureau"
            elif name in self.roots:
                role = "Application"
            else:
                role = "Dépendance"

            row = self.preview.rowCount()
            self.preview.insertRow(row)

            values = (
                name,
                role,
                package.get("version", "?"),
                self.human(size)
            )

            for column, value in enumerate(values):
                self.cell(
                    self.preview,
                    row,
                    column,
                    value
                )

            if (
                isinstance(size, (int, float))
                and size >= 0
            ):
                known += size
                count += 1
            else:
                unknown += 1

        # Fourchette indicative uniquement.
        # Elle ne remplace pas une simulation native
        # d'installation et une compression SquashFS.

        low = (
            known / 1048576
            + unknown * 2
            + 180
        )

        high = (
            known / 1048576
            + unknown * 35
            + 700
        )

        self.summary.setText(
            f"Paquets uniques prévus : "
            f"{len(config['all_packages'])} · "
            f"Applications : {len(self.roots)} · "
            f"Bureau : {config['desktop']}\n"
            f"Tailles connues : {count} "
            f"({known / 1048576:.1f} Mio) · "
            f"Tailles inconnues : {unknown}\n"
            f"Fourchette très approximative : "
            f"{low / 1024:.2f} à "
            f"{high / 1024:.2f} Gio — "
            "pas une mesure de la future ISO."
        )

        self.report.setPlainText(
            "ERREURS\n"
            + (
                "\n".join(errors)
                or "Aucune erreur de configuration détectée"
            )
            + "\n\nAVERTISSEMENTS\n"
            + "\n".join(warnings)
            + "\n\nLe projet prépare les paquets et "
            "le gestionnaire de connexion, mais ne "
            "construit pas encore d'ISO amorçable."
        )

        estimate = {
            "known_compressed_bytes": known,
            "known_packages": count,
            "unknown_packages": unknown,
            "indicative_low_mib": round(low, 1),
            "indicative_high_mib": round(high, 1)
        }

        return config, errors, warnings, estimate

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    def export(self):
        config, errors, warnings, estimate = self.check()

        if errors:
            QMessageBox.warning(
                self,
                "Configuration",
                "Corriger les erreurs dans Vérifier "
                "avant export."
            )
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir un dossier VIDE",
            str(Path.home())
        )

        if not folder:
            return

        path = Path(folder)

        if any(path.iterdir()):
            QMessageBox.warning(
                self,
                "Export",
                "Le dossier doit être vide."
            )
            return

        config["size_estimate"] = estimate
        config["warnings"] = warnings

        (path / "project_v1_4.json").write_text(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_4.txt").write_text(
            "\n".join(config["all_packages"]) + "\n",
            encoding="utf-8"
        )

        service = config["display_manager_service"]

        script = (
            "#!/bin/sh\n"
            "set -eu\n"
            "# Exécuter dans le système Linux cible, "
            "après installation des paquets.\n"
        )

        if (
            service
            and config["distribution"] in (
                "Arch Linux", "Debian", "Fedora", "Gentoo"
            )
        ):
            script += (
                "systemctl enable " + service + "\n"
                "systemctl set-default graphical.target\n"
            )
        else:
            script += (
                "# Activation graphique manuelle "
                "nécessaire pour ce profil.\n"
            )

        (path / "configure_graphical_v1_4.sh").write_text(
            script,
            encoding="utf-8"
        )

        (path / "README_v1_4.txt").write_text(
            "Projet de préparation uniquement.\n"
            "Aucune ISO produite.\n"
            "Les paquets doivent être validés et résolus "
            "par le gestionnaire natif.\n"
            "configure_graphical_v1_4.sh doit être exécuté "
            "dans le système cible après installation.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Configuration, liste de paquets et script "
            "d'activation graphique exportés.\n\n"
            "Aucune ISO créée."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())
