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
    QHeaderView, QLabel, QCheckBox, QFileDialog,
    QMessageBox, QTextEdit, QMenu, QAbstractItemView,
    QSplitter
)

VERSION = "1.3"

DISTROS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["43", "42"],
    "Slackware": ["15.0", "current"],
    "Gentoo": ["stable", "testing"],
    "Arch Linux": ["rolling"]
}

KERNEL = {
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
    },
    "Arch Linux": {
        "Stable": ["linux"],
        "LTS": ["linux-lts"],
        "Hardened": ["linux-hardened"]
    }
}

DESKTOP = {
    "Debian": {
        "Aucun": [],
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "lightdm"]
    },
    "Arch Linux": {
        "Aucun": [],
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": ["budgie-desktop", "lightdm"]
    }
}

AUDIO = {
    "Debian": {
        "Aucun": [],
        "PipeWire": ["pipewire", "wireplumber"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    },
    "Arch Linux": {
        "Aucun": [],
        "PipeWire": ["pipewire", "wireplumber"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"]
    }
}

SAFE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/-]{0,120}$"
)


# ============================================================
# THEMES
# ============================================================

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
    border-right: 1px solid #cbd5e1;
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
    border-right: 1px solid #435169;
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
# RECHERCHE DES PAQUETS
# ============================================================

def get_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.3",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:
        return json.load(response)


def lookup(distro, query):
    q = urllib.parse.quote(query)

    if distro == "Arch Linux":
        data = get_json(
            "https://archlinux.org/packages/search/json/?q=" + q
        )

        results = []

        for package in data.get("results", []):
            if package.get("arch") not in ("x86_64", "any"):
                continue

            results.append({
                "name": package["pkgname"],
                "version": str(package.get("pkgver", "")),
                "repo": package.get("repo", ""),
                "arch": package.get("arch", ""),
                "description": package.get("pkgdesc") or "",
                "verified": True,
                "size": package.get("compressed_size"),
                "installed": package.get("installed_size")
            })

        return results[:150]

    data = get_json(
        "https://repology.org/api/v1/projects/?search=" + q
    )

    if not isinstance(data, dict):
        raise ValueError(
            "Réponse du catalogue non reconnue"
        )

    prefixes = {
        "Debian": "debian_",
        "Fedora": "fedora_",
        "Slackware": "slackware_",
        "Gentoo": "gentoo"
    }

    found = {}

    for project, entries in data.items():
        if not isinstance(entries, list):
            continue

        for entry in entries:
            repo = str(entry.get("repo", ""))

            if not repo.startswith(prefixes[distro]):
                continue

            name = str(
                entry.get("binname")
                or entry.get("visiblename")
                or project
            )

            if distro == "Gentoo" and "/" not in name:
                continue

            if not SAFE.fullmatch(name):
                continue

            found[(name, repo)] = {
                "name": name,
                "version": str(entry.get("version", "")),
                "repo": repo,
                "arch": "",
                "description": entry.get("summary") or "",
                "verified": False,
                "size": None,
                "installed": None
            }

    return list(found.values())[:150]


# ============================================================
# DEPENDANCES ARCH
# ============================================================

def arch_details(package):
    segments = [
        urllib.parse.quote(str(package[key]), safe="")
        for key in ("repo", "arch", "name")
    ]

    url = (
        "https://archlinux.org/packages/"
        + "/".join(segments)
        + "/json/"
    )

    return get_json(url)


def dep_name(raw):
    return re.split(
        r"[<>=:]",
        str(raw),
        maxsplit=1
    )[0].strip()


def resolve_arch(root, limit=90):
    graph = {}
    metadata = {}
    warnings = []
    queue = [root]
    seen = set()

    while queue:
        package = queue.pop(0)
        name = package["name"]

        if name in seen:
            continue

        if len(seen) >= limit:
            warnings.append(
                "Limite de 90 paquets atteinte"
            )
            break

        seen.add(name)
        metadata[name] = package

        try:
            info = arch_details(package)

        except Exception as error:
            warnings.append(
                f"{name}: détails indisponibles ({error})"
            )
            graph[name] = []
            continue

        metadata[name]["size"] = info.get(
            "compressed_size",
            package.get("size")
        )

        metadata[name]["installed"] = info.get(
            "installed_size",
            package.get("installed")
        )

        dependencies = []

        for raw in info.get("depends") or []:
            dependency = dep_name(raw)

            if not dependency or not SAFE.fullmatch(dependency):
                warnings.append(
                    f"{name}: dépendance illisible {raw}"
                )
                continue

            dependencies.append(dependency)

            if dependency in seen:
                continue

            if any(
                item["name"] == dependency
                for item in queue
            ):
                continue

            try:
                matches = [
                    item
                    for item in lookup("Arch Linux", dependency)
                    if item["name"] == dependency
                ]

                if matches:
                    queue.append(matches[0])
                else:
                    warnings.append(
                        f"{name}: {dependency} introuvable "
                        "ou fourni virtuellement"
                    )

            except Exception as error:
                warnings.append(
                    f"{name}: {dependency} non vérifié ({error})"
                )

        graph[name] = list(dict.fromkeys(dependencies))

    return graph, metadata, warnings


# ============================================================
# RECHERCHES EN ARRIERE-PLAN
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
            else:
                result = resolve_arch(*self.args)

            self.completed.emit(result, "")

        except Exception as error:
            self.completed.emit(None, str(error))


# ============================================================
# FENETRE PRINCIPALE
# ============================================================

class Window(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.3"
        )

        self.resize(1260, 850)

        self.roots = {}
        self.graph = {}
        self.meta = {}
        self.unresolved = {}

        self.worker = None
        self.request = None

        host = QWidget()
        self.setCentralWidget(host)

        outer = QVBoxLayout(host)

        top = QHBoxLayout()

        title = QLabel("Universal Linux Builder")
        title.setObjectName("title")

        top.addWidget(title)
        top.addStretch()
        top.addWidget(QLabel("Apparence"))

        self.theme = QComboBox()
        self.theme.addItems([
            "Automatique",
            "Clair",
            "Sombre"
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

        self.distro_changed(
            self.distro.currentText()
        )

        self.apply_theme()

        QApplication.styleHints().colorSchemeChanged.connect(
            lambda *_: self.apply_theme()
        )

    # --------------------------------------------------------
    # DESIGN
    # --------------------------------------------------------

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
        combo = QComboBox()
        combo.addItems(values)
        return combo

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

        self.desktop = self.combo([
            "Aucun",
            "GNOME",
            "KDE Plasma",
            "Xfce",
            "Budgie"
        ])

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

        self.kernel = self.combo([])

        for label, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau Linux", self.kernel)
        ]:
            form.addRow(label, widget)

        layout.addLayout(form)

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
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
            ),
            ("calamares", "Préparer Calamares", True)
        ]

        for key, label, checked in equipment:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)

            self.options[key] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()

    def desktop_changed(self, value):
        if value == "Aucun":
            self.display.setCurrentText("Aucun")

        elif value == "Xfce":
            self.display.setCurrentText("X11")

        elif self.display.currentText() == "Aucun":
            self.display.setCurrentText("Wayland")

    def distro_changed(self, distro):
        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(DISTROS[distro])
        self.release.blockSignals(False)

        if hasattr(self, "kernel"):
            previous = self.desktop.currentText()

            choices = (
                ["Aucun", "KDE Plasma", "Xfce"]
                if distro == "Slackware"
                else [
                    "Aucun",
                    "GNOME",
                    "KDE Plasma",
                    "Xfce",
                    "Budgie"
                ]
            )

            self.desktop.clear()
            self.desktop.addItems(choices)

            if previous in choices:
                self.desktop.setCurrentText(previous)

            self.kernel.clear()
            self.kernel.addItems(KERNEL[distro])

            self.desktop_changed(
                self.desktop.currentText()
            )

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

    # --------------------------------------------------------
    # TABLEAUX MODERNES
    # --------------------------------------------------------

    def table(self, columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)

        table.horizontalHeader().setStretchLastSection(True)

        return table

    def set_cell(self, table, row, column, value, data=None):
        item = QTableWidgetItem(str(value))

        if data is not None:
            item.setData(
                Qt.ItemDataRole.UserRole,
                data
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

        search_row = QHBoxLayout()

        self.query = QLineEdit()
        self.query.setPlaceholderText(
            "Rechercher : firefox, vlc, gimp..."
        )

        self.query.returnPressed.connect(
            self.start_search
        )

        self.search_button = QPushButton("Rechercher")
        self.search_button.setObjectName("primary")

        self.search_button.clicked.connect(
            self.start_search
        )

        search_row.addWidget(self.query)
        search_row.addWidget(self.search_button)

        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tableau des résultats
        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)

        results_layout.addWidget(
            QLabel(
                "Résultats — double-clic sur une ligne pour ajouter"
            )
        )

        self.results = self.table([
            "Application",
            "Version",
            "Dépôt",
            "Description"
        ])

        self.results.setColumnWidth(0, 240)
        self.results.setColumnWidth(1, 125)
        self.results.setColumnWidth(2, 155)

        self.results.setSortingEnabled(True)

        self.results.cellDoubleClicked.connect(
            self.add_result
        )

        results_layout.addWidget(self.results)
        splitter.addWidget(results_panel)

        # Tableau des applications et dépendances
        selected_panel = QWidget()
        selected_layout = QVBoxLayout(selected_panel)

        selected_layout.addWidget(
            QLabel(
                "Paquets sélectionnés et dépendances "
                "— clic droit pour retirer une application"
            )
        )

        self.selected = self.table([
            "Paquet",
            "Rôle",
            "Version",
            "Taille compressée"
        ])

        self.selected.setColumnWidth(0, 300)
        self.selected.setColumnWidth(1, 200)
        self.selected.setColumnWidth(2, 140)

        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.selected.customContextMenuRequested.connect(
            self.remove_menu
        )

        selected_layout.addWidget(self.selected)
        splitter.addWidget(selected_panel)

        splitter.setSizes([400, 260])

        layout.addWidget(splitter, 1)

        manual_row = QHBoxLayout()

        self.manual = QLineEdit()
        self.manual.setPlaceholderText(
            "Nom exact d'un paquet "
            "(dépendances non vérifiées)"
        )

        manual_button = QPushButton(
            "Ajouter manuellement"
        )

        manual_button.clicked.connect(
            self.add_manual
        )

        manual_row.addWidget(self.manual)
        manual_row.addWidget(manual_button)

        layout.addLayout(manual_row)

        self.status = QLabel(
            "Recherche intégrée : Arch officiel ; "
            "autres familles : index tiers."
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

    def matching(self):
        return (
            self.repo_distro.currentText()
            == self.distro.currentText()
            and
            self.repo_release.currentText()
            == self.release.currentText()
        )

    def busy(self, value):
        self.search_button.setEnabled(not value)
        self.results.setEnabled(not value)

    # --------------------------------------------------------
    # RECHERCHE INTERNET
    # --------------------------------------------------------

    def start_search(self):
        query = self.query.text().strip()

        if not query or len(query) > 80:
            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir un nom de 80 caractères maximum."
            )
            return

        if not self.matching():
            QMessageBox.warning(
                self,
                "Dépôts",
                "La distribution et la branche doivent "
                "correspondre au projet."
            )
            return

        if self.worker and self.worker.isRunning():
            return

        self.results.setRowCount(0)
        self.busy(True)

        self.status.setText("Recherche en cours...")

        self.request = (
            "search",
            self.distro.currentText(),
            self.release.currentText()
        )

        self.worker = Worker(
            "search",
            self.distro.currentText(),
            query
        )

        self.worker.completed.connect(
            self.search_done
        )

        self.worker.finished.connect(
            lambda: self.busy(False)
        )

        self.worker.start()

    def search_done(self, rows, error):
        if self.request[:3] != (
            "search",
            self.distro.currentText(),
            self.release.currentText()
        ):
            return

        if error:
            self.status.setText(
                "Erreur de recherche : " + error
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
                package["description"]
            ]

            for column, value in enumerate(values):
                self.set_cell(
                    self.results,
                    row,
                    column,
                    value,
                    package if column == 0 else None
                )

        self.results.setSortingEnabled(True)

        self.status.setText(
            f"{len(rows)} résultat(s). "
            "Double-clique sur une ligne pour ajouter."
        )

    # --------------------------------------------------------
    # AJOUT ET DEPENDANCES
    # --------------------------------------------------------

    def add_result(self, row, column):
        if not self.matching():
            return

        if self.worker and self.worker.isRunning():
            return

        item = self.results.item(row, 0)

        if item is None:
            return

        package = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not package:
            return

        if package["name"] in self.roots:
            return

        if self.distro.currentText() != "Arch Linux":
            answer = QMessageBox.question(
                self,
                "Dépendances non vérifiées",
                f"Ajouter {package['name']} ?\n\n"
                "La résolution des dépendances de cette "
                "distribution n'est pas disponible.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if answer == QMessageBox.StandardButton.Yes:
                name = package["name"]

                self.roots[name] = package
                self.meta[name] = package

                self.unresolved[name] = [
                    "Résolution native nécessaire"
                ]

                self.refresh()

            return

        self.busy(True)

        self.status.setText(
            "Analyse récursive des dépendances Arch..."
        )

        self.request = (
            "resolve",
            self.distro.currentText(),
            self.release.currentText(),
            package
        )

        self.worker = Worker("resolve", package)

        self.worker.completed.connect(
            self.resolve_done
        )

        self.worker.finished.connect(
            lambda: self.busy(False)
        )

        self.worker.start()

    def resolve_done(self, result, error):
        if not self.request:
            return

        if self.request[0] != "resolve":
            return

        _, distro, release, package = self.request

        if (distro, release) != (
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
            f"{package['name']} ajouté ; "
            f"{len(graph)} paquets examinés ; "
            f"{len(warnings)} avertissement(s)."
        )

    def add_manual(self):
        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):
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
                "repo": "Manuel",
                "size": None,
                "verified": False
            }

            self.roots[name] = package
            self.meta[name] = package

            self.unresolved[name] = [
                "Dépendances non résolues"
            ]

            self.refresh()

        self.manual.clear()

    # --------------------------------------------------------
    # GRAPHE DES DEPENDANCES
    # --------------------------------------------------------

    def needed(self):
        found = set()
        stack = list(self.roots)

        while stack:
            name = stack.pop()

            if name in found:
                continue

            found.add(name)

            stack.extend(
                self.graph.get(name, [])
            )

        return found

    def human_size(self, size):
        if not isinstance(size, (int, float)):
            return "Inconnue"

        if size < 0:
            return "Inconnue"

        return f"{size / 1048576:.1f} Mio"

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

            values = [
                name,
                role,
                package.get("version", "?"),
                self.human_size(package.get("size"))
            ]

            for column, value in enumerate(values):
                self.set_cell(
                    self.selected,
                    row,
                    column,
                    value,
                    name if column == 0 else None
                )

    def remove_menu(self, position):
        item = self.selected.itemAt(position)

        if item is None:
            return

        root_item = self.selected.item(item.row(), 0)

        if root_item is None:
            return

        name = root_item.data(
            Qt.ItemDataRole.UserRole
        )

        if name not in self.roots:
            QMessageBox.information(
                self,
                "Dépendance",
                "Cette dépendance est utilisée par "
                "une application.\n"
                "Supprime l'application qui la nécessite."
            )
            return

        menu = QMenu(self)

        action = menu.addAction(
            "Retirer l'application et ses "
            "dépendances orphelines"
        )

        chosen = menu.exec(
            self.selected.viewport().mapToGlobal(position)
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
            f"{name} retiré ; "
            f"{removed} dépendance(s) orpheline(s) retirée(s)."
        )

    # --------------------------------------------------------
    # PAQUETS SYSTEME
    # --------------------------------------------------------

    def system_packages(self):
        distro = self.distro.currentText()

        packages = list(
            KERNEL[distro].get(
                self.kernel.currentText(),
                []
            )
        )

        packages += DESKTOP.get(distro, {}).get(
            self.desktop.currentText(),
            []
        )

        packages += AUDIO.get(distro, {}).get(
            self.audio.currentText(),
            []
        )

        if distro == "Debian":
            packages += [
                "pciutils",
                "usbutils",
                "udev",
                "kmod"
            ]

            if self.options["calamares"].isChecked():
                packages.append("calamares")

            if self.options["wifi"].isChecked():
                packages.append("wpasupplicant")

            if self.options["bluetooth"].isChecked():
                packages += ["bluez", "blueman"]

            if self.options["printing"].isChecked():
                packages.append("cups")

            if self.options["firmware"].isChecked():
                packages.append("firmware-linux-free")

        elif distro == "Arch Linux":
            packages += [
                "pciutils",
                "usbutils",
                "kmod",
                "linux-firmware"
            ]

            if self.options["calamares"].isChecked():
                packages.append("calamares")

            if self.options["wifi"].isChecked():
                packages.append("iwd")

            if self.options["bluetooth"].isChecked():
                packages += ["bluez", "bluez-utils"]

            if self.options["printing"].isChecked():
                packages.append("cups")

        return sorted(set(packages))

    def all_packages(self):
        return sorted(
            self.needed()
            | set(self.system_packages())
        )

    # --------------------------------------------------------
    # PROJET / ISO
    # --------------------------------------------------------

    def make_project(self):
        layout = self.page("Projet / ISO")

        layout.addWidget(
            QLabel(
                "Prévisualisation des paquets et "
                "estimation de la taille de l'ISO"
            )
        )

        self.summary = QLabel(
            "Clique sur « Vérifier » pour afficher "
            "la composition du projet."
        )

        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.preview = self.table([
            "Paquet",
            "Catégorie",
            "Version",
            "Taille connue"
        ])

        self.preview.setColumnWidth(0, 330)
        self.preview.setColumnWidth(1, 200)
        self.preview.setColumnWidth(2, 150)

        layout.addWidget(self.preview, 2)

        self.report = QTextEdit()
        self.report.setReadOnly(True)

        layout.addWidget(self.report, 1)

        buttons = QHBoxLayout()

        check_button = QPushButton("Vérifier")
        check_button.clicked.connect(self.check)

        export_button = QPushButton(
            "Exporter le projet"
        )

        export_button.setObjectName("primary")
        export_button.clicked.connect(self.export)

        buttons.addWidget(check_button)
        buttons.addWidget(export_button)

        layout.addLayout(buttons)

    def config(self):
        config = {
            "schema": 13,
            "app_version": VERSION,
            "distribution": self.distro.currentText(),
            "version": self.release.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentText(),
            "applications": sorted(self.roots),
            "dependency_graph": {
                key: value
                for key, value in self.graph.items()
                if key in self.needed()
            },
            "application_packages": sorted(self.needed()),
            "system_packages": self.system_packages(),
            "all_packages": self.all_packages(),
            "unresolved": self.unresolved
        }

        config.update({
            key: checkbox.isChecked()
            for key, checkbox in self.options.items()
        })

        return config

    # --------------------------------------------------------
    # VERIFICATION ET ESTIMATION ISO
    # --------------------------------------------------------

    def check(self):
        config = self.config()

        errors = []
        warnings = []

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
                "Un bureau nécessite X11 ou Wayland."
            )

        if self.unresolved:
            warnings.append(
                f"{len(self.unresolved)} application(s) "
                "avec dépendances non résolues."
            )

        if config["distribution"] not in (
            "Arch Linux",
            "Debian"
        ):
            warnings.append(
                "Liste des composants système incomplète "
                "pour cette distribution."
            )

        warnings.append(
            "Les dépendances du système de base et "
            "les fournisseurs virtuels ne sont pas "
            "tous résolus."
        )

        self.preview.setRowCount(0)

        known_bytes = 0
        known_count = 0
        unknown_count = 0

        for name in config["all_packages"]:
            package = self.meta.get(name, {})
            size = package.get("size")

            if name in config["system_packages"]:
                role = "Système"
            elif name in self.roots:
                role = "Application"
            else:
                role = "Dépendance"

            row = self.preview.rowCount()
            self.preview.insertRow(row)

            values = [
                name,
                role,
                package.get("version", "?"),
                self.human_size(size)
            ]

            for column, value in enumerate(values):
                self.set_cell(
                    self.preview,
                    row,
                    column,
                    value
                )

            if (
                isinstance(size, (int, float))
                and size >= 0
            ):
                known_bytes += size
                known_count += 1
            else:
                unknown_count += 1

        # Estimation indicative uniquement.
        #
        # La taille réelle dépendra :
        # - des dépendances résolues par la distribution ;
        # - des paquets du système de base ;
        # - du contenu de l'initramfs ;
        # - des firmwares ;
        # - du taux de compression SquashFS ;
        # - des fichiers de démarrage de l'ISO.
        #
        # Les valeurs ci-dessous ne sont pas
        # des mesures réelles des paquets inconnus.

        lower_mib = (
            known_bytes / 1048576
            + unknown_count * 2
            + 180
        )

        upper_mib = (
            known_bytes / 1048576
            + unknown_count * 35
            + 700
        )

        package_count = len(config["all_packages"])
        app_count = len(self.roots)

        dependency_count = len(
            self.needed() - set(self.roots)
        )

        system_count = len(
            set(config["system_packages"])
        )

        self.summary.setText(
            f"Applications : {app_count}  |  "
            f"Dépendances connues : {dependency_count}  |  "
            f"Paquets système : {system_count}  |  "
            f"Paquets uniques : {package_count}\n\n"
            f"Taille compressée renseignée : "
            f"{known_bytes / 1048576:.1f} Mio "
            f"({known_count} paquets).\n"
            f"Taille inconnue : {unknown_count} paquets.\n\n"
            f"Fourchette indicative ISO : "
            f"{lower_mib / 1024:.2f} à "
            f"{upper_mib / 1024:.2f} Gio.\n"
            "Cette estimation n'est pas fiable tant que "
            "les tailles et dépendances manquent."
        )

        report = (
            "AVERTISSEMENTS / LIMITES\n"
            + "\n".join(warnings)
            + "\n\nERREURS\n"
            + (
                "\n".join(errors)
                if errors
                else "Aucune erreur de configuration détectée"
            )
            + "\n\nLa taille réelle dépendra du solveur "
            "natif, de SquashFS, des firmwares et du "
            "profil ISO.\n"
            "Aucune ISO n'est construite par cette version."
        )

        self.report.setPlainText(report)

        estimate = {
            "known_compressed_bytes": known_bytes,
            "known_packages": known_count,
            "unknown_packages": unknown_count,
            "indicative_low_mib": round(lower_mib, 1),
            "indicative_high_mib": round(upper_mib, 1)
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
                "Corriger les erreurs affichées avant export."
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
                "Choisir un dossier vide."
            )
            return

        config["size_estimate"] = estimate
        config["warnings"] = warnings

        (path / "project_v1_3.json").write_text(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_3.txt").write_text(
            "\n".join(config["all_packages"]) + "\n",
            encoding="utf-8"
        )

        (path / "README_v1_3.txt").write_text(
            "Universal Linux Builder v1.3\n\n"
            "Préparation uniquement : aucune ISO produite.\n"
            "Tailles indicatives, dépendances incomplètes.\n"
            "Vérifier les paquets avec le gestionnaire natif "
            "avant toute construction.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Projet, liste des paquets connus et "
            "estimation exportés.\n\n"
            "Aucune ISO construite."
        )


# ============================================================
# DEMARRAGE
# ============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = Window()
    window.show()

    sys.exit(app.exec())
