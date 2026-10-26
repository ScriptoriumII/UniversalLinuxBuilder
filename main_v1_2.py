import json
import re
import sys
import urllib.parse
import urllib.request

from pathlib import Path
from collections import defaultdict

from PySide6.QtCore import Qt, QThread, Signal

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget
)


VERSION = "1.2"

DISTROS = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["43", "42"],
    "Slackware": ["15.0", "current"],
    "Gentoo": ["stable", "testing"],
    "Arch Linux": ["rolling"]
}

DESKTOPS = [
    "Aucun",
    "GNOME",
    "KDE Plasma",
    "Xfce",
    "Budgie"
]

KERNELS = {
    "Debian": {
        "Stable": ["linux-image-amd64"]
    },
    "Fedora": {
        "Stable": ["kernel"]
    },
    "Slackware": {},
    "Gentoo": {
        "Stable": ["sys-kernel/gentoo-kernel"]
    },
    "Arch Linux": {
        "Stable": ["linux"],
        "LTS": ["linux-lts"],
        "Hardened": ["linux-hardened"]
    }
}

REPOS = {
    "Debian": "debian_",
    "Fedora": "fedora_",
    "Slackware": "slackware_",
    "Gentoo": "gentoo"
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

QLineEdit,
QComboBox,
QTextEdit,
QListWidget {
    background: #ffffff;
    border: 1px solid #ccd5e0;
    border-radius: 8px;
    padding: 7px;
}

QPushButton {
    background: #e4ebf5;
    border: 1px solid #cad6e5;
    border-radius: 8px;
    padding: 9px;
    font-weight: 600;
}

QPushButton:hover {
    background: #d3e4fb;
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

QLineEdit,
QComboBox,
QTextEdit,
QListWidget {
    background: #202735;
    color: #f0f3f9;
    border: 1px solid #435169;
    border-radius: 8px;
    padding: 7px;
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
# COMMUNICATION INTERNET
# ============================================================

def fetch(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "UniversalLinuxBuilder/1.2",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:

        return json.load(response)


# ============================================================
# RECHERCHE DES APPLICATIONS
# ============================================================

def search(distro, query):

    q = urllib.parse.quote(query)

    if distro == "Arch Linux":

        data = fetch(
            "https://archlinux.org/packages/search/json/?q="
            + q
        )

        return [
            {
                "name": p["pkgname"],
                "repo": p["repo"],
                "arch": p["arch"],
                "version": p.get("pkgver", ""),
                "description": p.get("pkgdesc") or "",
                "verified": True
            }

            for p in data.get("results", [])

            if p.get("arch") in ("x86_64", "any")

        ][:100]

    # Index tiers : la version exacte n'est pas garantie.

    data = fetch(
        "https://repology.org/api/v1/projects/?search="
        + q
    )

    result = []
    seen = set()

    for project, entries in data.items():

        for entry in entries:

            repo = str(
                entry.get("repo", "")
            ).lower()

            if not repo.startswith(REPOS[distro]):
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

            if name in seen:
                continue

            seen.add(name)

            result.append({
                "name": name,
                "repo": repo,
                "arch": "",
                "version": entry.get("version", ""),
                "description": entry.get("summary") or "",
                "verified": False
            })

    return result[:100]


# ============================================================
# DEPENDANCES ARCH LINUX
# ============================================================

def arch_detail(repo, arch, name):

    parts = [
        urllib.parse.quote(x, safe="")
        for x in (repo, arch, name)
    ]

    url = (
        "https://archlinux.org/packages/"
        + "/".join(parts)
        + "/json/"
    )

    return fetch(url)


def clean_arch_dep(value):

    name = re.split(
        r"[<>=:]",
        str(value),
        maxsplit=1
    )[0].strip()

    if SAFE.fullmatch(name):
        return name

    return None


def resolve_arch(root, limit=120):

    """
    Recherche recursive des dependances Arch.

    Attention :
    - ne remplace pas pacman
    - les fournisseurs virtuels ne sont pas resolus
    - les conflits doivent etre verifies
    """

    graph = {}
    metadata = {}
    warnings = []

    queue = [
        (
            root["name"],
            root["repo"],
            root["arch"]
        )
    ]

    visited = set()

    while queue:

        name, repo, arch = queue.pop(0)

        if name in visited:
            continue

        if len(visited) >= limit:
            raise RuntimeError(
                "Limite de résolution atteinte : 120 paquets."
            )

        visited.add(name)

        try:

            info = arch_detail(
                repo,
                arch,
                name
            )

        except Exception as exc:

            warnings.append(
                f"{name}: métadonnées indisponibles ({exc})"
            )

            graph[name] = []
            continue

        metadata[name] = {
            "repo": repo,
            "arch": arch
        }

        children = []

        for raw in info.get("depends", []):

            dep = clean_arch_dep(raw)

            if not dep:

                warnings.append(
                    f"{name}: dépendance illisible {raw}"
                )

                continue

            children.append(dep)

            if dep not in visited:

                try:

                    found = search(
                        "Arch Linux",
                        dep
                    )

                    matches = [
                        p for p in found
                        if p["name"] == dep
                    ]

                    if matches:

                        selected = matches[0]

                        queue.append(
                            (
                                dep,
                                selected["repo"],
                                selected["arch"]
                            )
                        )

                    else:

                        warnings.append(
                            f"{name}: {dep} absent "
                            "ou fournisseur virtuel possible"
                        )

                except Exception as exc:

                    warnings.append(
                        f"{name}: résolution de {dep} "
                        f"impossible ({exc})"
                    )

        graph[name] = list(
            dict.fromkeys(children)
        )

    return graph, metadata, warnings


# ============================================================
# THREAD RECHERCHE / DEPENDANCES
# ============================================================

class Worker(QThread):

    done = Signal(object, str)

    def __init__(self, action, *args):

        super().__init__()

        self.action = action
        self.args = args

    def run(self):

        try:

            if self.action == "search":

                value = search(*self.args)

            else:

                value = resolve_arch(*self.args)

            self.done.emit(value, "")

        except Exception as exc:

            self.done.emit(
                None,
                str(exc)
            )


# ============================================================
# INTERFACE PRINCIPALE
# ============================================================

class Window(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v1.2"
        )

        self.resize(1170, 800)

        # Applications choisies explicitement
        self.roots = {}

        # Graphe des dependances
        self.graph = {}

        # Applications dont les dependances
        # ne sont pas entierement resolues
        self.unresolved = {}

        self.worker = None
        self.pending = None

        host = QWidget()
        outer = QVBoxLayout(host)

        self.setCentralWidget(host)

        top = QHBoxLayout()

        title = QLabel(
            "Universal Linux Builder"
        )

        title.setObjectName("title")

        top.addWidget(title)
        top.addStretch()

        top.addWidget(
            QLabel("Thème")
        )

        self.theme = QComboBox()

        self.theme.addItems([
            "Automatique",
            "Clair",
            "Sombre"
        ])

        self.theme.currentIndexChanged.connect(
            self.apply_theme
        )

        top.addWidget(self.theme)

        outer.addLayout(top)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self.make_distro()
        self.make_system()
        self.make_apps()
        self.make_export()

        self.distro_changed(
            self.distro.currentText()
        )

        self.apply_theme()


    # ========================================================
    # APPARENCE
    # ========================================================

    def apply_theme(self, *_):

        choice = self.theme.currentText()

        if choice == "Automatique":

            dark = (
                QApplication.styleHints().colorScheme()
                == Qt.ColorScheme.Dark
            )

        else:

            dark = choice == "Sombre"

        self.setStyleSheet(
            DARK if dark else LIGHT
        )


    def page(self, name):

        widget = QWidget()

        layout = QVBoxLayout(widget)

        layout.setContentsMargins(
            22, 22, 22, 22
        )

        layout.setSpacing(12)

        self.tabs.addTab(
            widget,
            name
        )

        return layout


    # ========================================================
    # DISTRIBUTION
    # ========================================================

    def make_distro(self):

        layout = self.page(
            "Distribution"
        )

        form = QFormLayout()

        self.distro = QComboBox()
        self.distro.addItems(DISTROS)

        self.release = QComboBox()

        self.distro.currentTextChanged.connect(
            self.distro_changed
        )

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        form.addRow(
            "Distribution",
            self.distro
        )

        form.addRow(
            "Version",
            self.release
        )

        layout.addLayout(form)
        layout.addStretch()


    # ========================================================
    # SYSTEME
    # ========================================================

    def make_system(self):

        layout = self.page(
            "Système"
        )

        form = QFormLayout()

        self.desktop = QComboBox()
        self.desktop.addItems(DESKTOPS)

        self.display = QComboBox()

        self.display.addItems([
            "Aucun",
            "X11",
            "Wayland"
        ])

        self.audio = QComboBox()

        self.audio.addItems([
            "Aucun",
            "PipeWire",
            "PulseAudio",
            "ALSA"
        ])

        self.kernel = QComboBox()

        self.desktop.currentTextChanged.connect(
            self.desktop_changed
        )

        for label, widget in [
            ("Bureau", self.desktop),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Noyau Linux", self.kernel)
        ]:

            form.addRow(
                label,
                widget
            )

        layout.addLayout(form)

        self.equipment = {}

        equipment = [
            ("wifi", "Wi-Fi", True),
            ("bluetooth", "Bluetooth", True),
            (
                "printing",
                "Imprimantes / CUPS",
                False
            ),
            (
                "firmware",
                "Firmwares et détection matérielle",
                True
            ),
            (
                "calamares",
                "Préparer Calamares",
                True
            )
        ]

        for key, label, default in equipment:

            check = QCheckBox(label)

            check.setChecked(default)

            self.equipment[key] = check

            layout.addWidget(check)

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

        else:

            self.display.setCurrentText(
                "Wayland"
            )


    def distro_changed(self, distro):

        self.release.blockSignals(True)

        self.release.clear()

        self.release.addItems(
            DISTROS[distro]
        )

        self.release.blockSignals(False)

        if hasattr(self, "desktop"):

            old = self.desktop.currentText()

            self.desktop.clear()

            if distro == "Slackware":

                choices = [
                    "Aucun",
                    "KDE Plasma",
                    "Xfce"
                ]

            else:

                choices = DESKTOPS

            self.desktop.addItems(choices)

            if old in choices:

                self.desktop.setCurrentText(old)

            self.kernel.clear()

            self.kernel.addItems(
                KERNELS[distro]
            )

        if hasattr(self, "repo_distro"):

            self.repo_distro.setCurrentText(
                distro
            )

        self.reset_apps()


    def release_changed(self, version):

        if hasattr(self, "repo_release"):

            self.repo_release.setCurrentText(
                version
            )

        self.reset_apps()


    # ========================================================
    # APPLICATIONS
    # ========================================================

    def make_apps(self):

        layout = self.page(
            "Applications"
        )

        form = QFormLayout()

        self.repo_distro = QComboBox()
        self.repo_distro.addItems(DISTROS)

        self.repo_release = QComboBox()

        self.repo_distro.currentTextChanged.connect(
            self.repo_changed
        )

        form.addRow(
            "Dépôts",
            self.repo_distro
        )

        form.addRow(
            "Branche",
            self.repo_release
        )

        layout.addLayout(form)

        row = QHBoxLayout()

        self.query = QLineEdit()

        self.query.setPlaceholderText(
            "Nom du paquet : firefox, vlc, gimp..."
        )

        self.query.returnPressed.connect(
            self.run_search
        )

        self.search_btn = QPushButton(
            "Rechercher"
        )

        self.search_btn.setObjectName(
            "primary"
        )

        self.search_btn.clicked.connect(
            self.run_search
        )

        row.addWidget(self.query)
        row.addWidget(self.search_btn)

        layout.addLayout(row)

        row2 = QHBoxLayout()

        left = QVBoxLayout()
        right = QVBoxLayout()

        left.addWidget(
            QLabel(
                "Résultats — double-clic pour ajouter"
            )
        )

        self.results = QListWidget()

        self.results.itemDoubleClicked.connect(
            self.add_result
        )

        left.addWidget(
            self.results
        )

        right.addWidget(
            QLabel(
                "Sélection : applications et dépendances"
            )
        )

        self.selected = QListWidget()

        self.selected.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.selected.customContextMenuRequested.connect(
            self.remove_menu
        )

        right.addWidget(
            self.selected
        )

        row2.addLayout(left, 3)
        row2.addLayout(right, 2)

        layout.addLayout(row2, 1)

        manual = QHBoxLayout()

        self.manual = QLineEdit()

        self.manual.setPlaceholderText(
            "Ajouter un nom de paquet non vérifié"
        )

        button = QPushButton(
            "Ajouter manuellement"
        )

        button.clicked.connect(
            self.add_manual
        )

        manual.addWidget(self.manual)
        manual.addWidget(button)

        layout.addLayout(manual)

        self.status = QLabel(
            "Les dépendances Arch sont examinées "
            "via les métadonnées officielles."
        )

        self.status.setWordWrap(True)

        layout.addWidget(
            self.status
        )

        self.repo_changed(
            self.repo_distro.currentText()
        )


    def reset_apps(self):

        if hasattr(self, "results"):

            self.results.clear()

        if hasattr(self, "selected"):

            self.selected.clear()

        self.roots.clear()
        self.graph.clear()
        self.unresolved.clear()


    def repo_changed(self, distro):

        self.repo_release.clear()

        self.repo_release.addItems(
            DISTROS[distro]
        )

        self.reset_apps()


    def compatible(self):

        return (
            self.repo_distro.currentText()
            == self.distro.currentText()
            and
            self.repo_release.currentText()
            == self.release.currentText()
        )


    def busy(self, value):

        self.search_btn.setEnabled(
            not value
        )

        self.results.setEnabled(
            not value
        )


    # ========================================================
    # RECHERCHE INTERNET
    # ========================================================

    def run_search(self):

        q = self.query.text().strip()

        if not q or len(q) > 80:

            QMessageBox.warning(
                self,
                "Recherche",
                "Saisir un nom de paquet "
                "(80 caractères maximum)."
            )

            return

        if not self.compatible():

            QMessageBox.warning(
                self,
                "Dépôts",
                "La branche de recherche doit "
                "correspondre au projet."
            )

            return

        if self.worker and self.worker.isRunning():
            return

        self.results.clear()

        self.busy(True)

        self.status.setText(
            "Recherche en cours..."
        )

        self.pending = (
            "search",
            self.distro.currentText(),
            self.release.currentText()
        )

        self.worker = Worker(
            "search",
            self.distro.currentText(),
            q
        )

        self.worker.done.connect(
            self.search_done
        )

        self.worker.finished.connect(
            lambda: self.busy(False)
        )

        self.worker.start()


    def search_done(self, rows, error):

        if error:

            self.status.setText(
                "Recherche impossible : " + error
            )

            return

        if self.pending[1:] != (
            self.distro.currentText(),
            self.release.currentText()
        ):

            return

        for package in rows:

            item = QListWidgetItem(
                f"{package['name']} "
                f"· {package['version']}\n"
                f"{package['repo']} — "
                f"{package['description'][:75]}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                package
            )

            self.results.addItem(item)

        self.status.setText(
            f"{len(rows)} résultat(s). "
            "Index tiers non validé pour les "
            "branches non-Arch."
        )


    # ========================================================
    # AJOUT DES APPLICATIONS
    # ========================================================

    def add_result(self, item):

        if not self.compatible():
            return

        package = item.data(
            Qt.ItemDataRole.UserRole
        )

        if package["name"] in self.roots:
            return

        if self.worker and self.worker.isRunning():
            return

        if self.distro.currentText() != "Arch Linux":

            answer = QMessageBox.question(
                self,
                "Dépendances non résolues",
                "Les métadonnées de dépendances "
                "de cette distribution ne sont pas intégrées.\n"
                "Ajouter le paquet comme non résolu ? "
                "Il sera bloqué à l'export installable.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if answer == QMessageBox.StandardButton.Yes:

                self.roots[package["name"]] = package

                self.unresolved[package["name"]] = [
                    "Résolution native nécessaire"
                ]

                self.refresh()

            return

        self.busy(True)

        self.status.setText(
            "Résolution des dépendances Arch..."
        )

        self.pending = (
            "resolve",
            self.distro.currentText(),
            self.release.currentText(),
            package
        )

        self.worker = Worker(
            "resolve",
            package
        )

        self.worker.done.connect(
            self.resolve_done
        )

        self.worker.finished.connect(
            lambda: self.busy(False)
        )

        self.worker.start()


    def resolve_done(self, value, error):

        if error:

            self.status.setText(
                "Résolution impossible : " + error
            )

            return

        _, distro, version, package = self.pending

        if (distro, version) != (
            self.distro.currentText(),
            self.release.currentText()
        ):

            return

        graph, metadata, warnings = value

        name = package["name"]

        self.roots[name] = package

        self.graph.update(graph)

        if warnings:

            self.unresolved[name] = warnings

        else:

            self.unresolved.pop(
                name,
                None
            )

        self.refresh()

        message = (
            f"{name} ajouté. "
            f"{len(graph)} paquets inspectés. "
        )

        if warnings:

            message += "Dépendances à vérifier !"

        else:

            message += "Aucune anomalie signalée."

        self.status.setText(message)


    # ========================================================
    # AJOUT MANUEL
    # ========================================================

    def add_manual(self):

        name = self.manual.text().strip()

        if not SAFE.fullmatch(name):

            QMessageBox.warning(
                self,
                "Paquet",
                "Nom invalide."
            )

            return

        if name not in self.roots:

            self.roots[name] = {
                "name": name,
                "verified": False
            }

            self.unresolved[name] = [
                "Paquet ajouté manuellement, "
                "dépendances non résolues"
            ]

        self.manual.clear()

        self.refresh()


    # ========================================================
    # CALCUL DES DEPENDANCES UTILISEES
    # ========================================================

    def needed(self):

        """
        Calcule les paquets necessaires
        a partir des applications selectionnees.

        Les dependances partagees sont conservees.
        """

        used = set()

        stack = list(
            self.roots
        )

        while stack:

            name = stack.pop()

            if name in used:
                continue

            used.add(name)

            stack.extend(
                self.graph.get(name, [])
            )

        return used


    # ========================================================
    # ACTUALISATION DE LA LISTE
    # ========================================================

    def refresh(self):

        self.selected.clear()

        for name in sorted(self.needed()):

            root = name in self.roots

            if root:

                flag = "Application"

            else:

                flag = "Dépendance"

            if root and name in self.unresolved:

                flag += " ⚠ non résolue"

            item = QListWidgetItem(
                f"{name}   [{flag}]"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                name
            )

            self.selected.addItem(item)


    # ========================================================
    # SUPPRESSION APPLICATION + DEPENDANCES
    # ========================================================

    def remove_menu(self, point):

        item = self.selected.itemAt(point)

        if not item:
            return

        name = item.data(
            Qt.ItemDataRole.UserRole
        )

        if name not in self.roots:

            QMessageBox.information(
                self,
                "Dépendance partagée",
                "Ce paquet est une dépendance.\n"
                "Supprimer les applications "
                "qui le nécessitent."
            )

            return

        menu = QMenu(self)

        action = menu.addAction(
            "Supprimer l'application "
            "et les dépendances orphelines"
        )

        chosen = menu.exec(
            self.selected.mapToGlobal(point)
        )

        if chosen != action:
            return

        before = self.needed()

        del self.roots[name]

        self.unresolved.pop(
            name,
            None
        )

        after = self.needed()

        self.refresh()

        removed_dependencies = max(
            0,
            len(before - after) - 1
        )

        self.status.setText(
            f"{name} supprimé ; "
            f"{removed_dependencies} dépendance(s) "
            "devenue(s) inutile(s) retirée(s)."
        )


    # ========================================================
    # EXPORT
    # ========================================================

    def make_export(self):

        layout = self.page(
            "Projet / ISO"
        )

        self.report = QTextEdit()

        self.report.setReadOnly(True)

        layout.addWidget(
            self.report
        )

        row = QHBoxLayout()

        check = QPushButton(
            "Vérifier"
        )

        check.clicked.connect(
            self.check
        )

        save = QPushButton(
            "Exporter le projet"
        )

        save.setObjectName(
            "primary"
        )

        save.clicked.connect(
            self.export
        )

        row.addWidget(check)
        row.addWidget(save)

        layout.addLayout(row)

        layout.addWidget(
            QLabel(
                "Calamares et construction ISO : "
                "profils expérimentaux, "
                "aucune ISO générée."
            )
        )


    def config(self):

        cfg = {
            "schema": 12,
            "app_version": VERSION,
            "distribution": self.distro.currentText(),
            "version": self.release.currentText(),
            "desktop": self.desktop.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "kernel": self.kernel.currentText(),
            "applications": sorted(self.roots),
            "dependency_graph": {
                k: v
                for k, v in self.graph.items()
                if k in self.needed()
            },
            "all_packages": sorted(self.needed()),
            "unresolved": self.unresolved
        }

        cfg.update({
            key: check.isChecked()
            for key, check in self.equipment.items()
        })

        return cfg


    # ========================================================
    # VERIFICATION
    # ========================================================

    def check(self):

        cfg = self.config()

        errors = []

        if (
            cfg["desktop"] == "Aucun"
            and cfg["display"] != "Aucun"
        ):

            errors.append(
                "Affichage incompatible avec Aucun bureau"
            )

        if (
            cfg["desktop"] != "Aucun"
            and cfg["display"] == "Aucun"
        ):

            errors.append(
                "Choisir X11 ou Wayland"
            )

        if self.unresolved:

            errors.append(
                "Dépendances non résolues : "
                "export installable bloqué"
            )

        if cfg["distribution"] not in (
            "Arch Linux",
            "Debian"
        ):

            errors.append(
                "Profil natif de construction ISO "
                "non implémenté"
            )

        report = json.dumps(
            cfg,
            indent=2,
            ensure_ascii=False
        )

        report += "\n\nERREURS / LIMITES :\n"

        report += (
            "\n".join(errors)
            or "Aucune erreur connue"
        )

        self.report.setPlainText(
            report
        )

        return errors


    # ========================================================
    # ENREGISTREMENT DU PROJET
    # ========================================================

    def export(self):

        errors = self.check()

        if errors:

            answer = QMessageBox.question(
                self,
                "Export de préparation",
                "Des dépendances ou profils "
                "ne sont pas validés.\n"
                "Exporter seulement le projet "
                "(sans script ISO exécutable) ?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if answer != QMessageBox.StandardButton.Yes:
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

        cfg = self.config()

        (path / "project_v1_2.json").write_text(
            json.dumps(
                cfg,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        (path / "packages_v1_2.txt").write_text(
            "\n".join(
                cfg["all_packages"]
            ) + "\n",
            encoding="utf-8"
        )

        (path / "README_v1_2.txt").write_text(
            "Projet de préparation uniquement.\n"
            "Dépendances Arch : métadonnées, "
            "pas solveur pacman.\n"
            "Aucune ISO n'est produite.\n"
            "Vérifier avec le gestionnaire natif "
            "avant installation.\n",
            encoding="utf-8"
        )

        QMessageBox.information(
            self,
            "Export",
            "Projet et liste des paquets enregistrés.\n"
            "Aucune ISO construite."
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
