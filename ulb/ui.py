from pathlib import Path
import json
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHeaderView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QDesktopServices, QIcon, QPixmap
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from .constants import AUDIO, FEDORA_THIRD_PARTY, BUILD_FAMILIES, BUILD_TOOLS, DESKTOPS, EXTRAS, FAMILIES, GRUB_PACKAGES, INSTALLERS, LIGHT_PRESET, LIVE_INSTALLER, PROFILES, VM_BOOTS, VM_DISPLAYS, VM_RAM, LOGOS, MANAGERS, MANAGER_BINARY, RELEASES, SAFE_PACKAGE, TARGET_BASE, VERSION
from .theme import SETTING_LABELS, SETTING_VALUES, THEMES, palette, resolve_mode, stylesheet
from .tasks import Task
from .environments import install_distribution, best_match, check_tools, detect_all, install_tools, manager_report, online_catalog, test_manager, update_repositories, verify_tools, wsl_names
from .builders import build_iso
from .progress import BuildProgress, describe
from .vmtest import boot_test
from .vm import INFO_MARKER, URL_MARKER, install_vm_tools, reset_vm_disk, run_vm, stop_vm
from .project import export_project
from .projects import normalize_project, read_project
from .checklist import installer_checklist
from .package_view import context_line, package_origins, parse_simulation, simulation_verdict, update_message
from .precheck import live_essentials
from .settings import load_settings, save_settings
from .logos import logo, set_mode as set_logo_mode
from .catalog import (
    INTERNET, INTERNET_FAMILIES, online_label, refresh_online, search_online
)
from .remaster import REMASTER_FAMILIES
from .output import check_folder, clean_iso_name
from .ui_advanced import AdvancedMixin
from .vanilla import desktop_packages, vanilla_note, vanilla_supported
from .ui_remaster import RemasterMixin
from .ui_ventoy import VentoyMixin
from .packages import parse_search, search_packages, simulate_packages
from .wsl import CANCELLED, run


class UniversalLinuxBuilder(
    RemasterMixin, AdvancedMixin, VentoyMixin, QMainWindow
):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Universal Linux Builder v" + VERSION
        )
        self.resize(1400, 900)

        self.family_name = "Debian"
        self.results_stale = False

        self.config = load_settings()
        self.theme_setting = self.config.get("theme", "system")

        if self.theme_setting not in ("system", "light", "dark"):
            self.theme_setting = "system"

        self.theme_mode = "dark"

        saved = self.config.get("wsl_associations", {})

        if not isinstance(saved, dict):
            saved = {}

        self.associations = {
            family: (
                saved.get(family, "")
                if isinstance(saved.get(family, ""), str)
                else ""
            )
            for family in FAMILIES
        }

        manual = self.config.get("manual_associations", [])

        self.manual_associations = {
            family
            for family in (manual if isinstance(manual, list) else [])
            if family in FAMILIES
        }

        self.inventory = []
        self.catalog_rows = []

        self.selected_packages = set()
        self.cards = {}
        self.banners = []
        self.worker = None
        self.build_tracker = None
        self.build_summary = None
        self.build_family = ""
        self.vm_task = None
        self.vm_id = "main"
        self.vm_env = ""
        self.vm_url = ""
        self.vm_ram_auto = True
        self.last_iso = ""
        self.boot_smoke = {}
        self.mapping_icons = {}

        self.analysis_ok = False
        self.tools_ok = False
        self.revision = 0

        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(16, 12, 16, 10)
        main.setSpacing(10)

        header = QHBoxLayout()

        self.header_logo = QLabel()
        self.header_logo.setFixedSize(48, 48)
        header.addWidget(self.header_logo)

        titles = QVBoxLayout()

        title = QLabel("Universal Linux Builder")
        self.role(title, "title")

        titles.addWidget(title)

        self.subtitle = QLabel()
        self.role(self.subtitle, "subtitle")
        titles.addWidget(self.subtitle)

        header.addLayout(titles)
        header.addStretch()

        version = QLabel("v" + VERSION)
        self.role(version, "muted")
        header.addWidget(version)

        self.theme_choice = QComboBox()
        self.theme_choice.addItems(THEMES)
        self.theme_choice.setToolTip(
            "Thème : suivre le système, clair ou sombre"
        )
        self.theme_choice.setCurrentText(
            SETTING_LABELS.get(self.theme_setting, "Système")
        )
        self.theme_choice.currentTextChanged.connect(
            self.theme_changed
        )
        header.addWidget(QLabel("Thème"))
        header.addWidget(self.theme_choice)

        main.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        main.addWidget(line)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        self.make_distribution()
        self.make_system()
        self.make_applications()
        self.make_verification()
        self.make_iso()
        self.make_virtualization()
        self.make_ventoy()
        self.make_wsl()

        footer = QHBoxLayout()

        self.status = QLabel("Prêt")
        self.role(self.status, "muted")
        footer.addWidget(self.status, 1)

        self.progress = QProgressBar()
        self.progress.setMinimumWidth(520)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        footer.addWidget(self.progress)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_job)
        footer.addWidget(self.cancel_button)

        main.addLayout(footer)

        self.restoring = False
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(1000)
        self.save_timer.timeout.connect(self.save_project_state)

        self.log_view = None
        self.log_buffer = []
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(150)
        self.log_timer.timeout.connect(self.flush_log)

        self.apply_theme()
        hints = QGuiApplication.styleHints()

        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self.system_scheme_changed)

        self.change_family("Debian")
        self.profile_changed(self.profile.currentText())
        self.restore_project_state()
        self.refresh_wsl()

    # --------------------------------------------------------
    # OUTILS GRAPHIQUES
    # --------------------------------------------------------

    def page(self, name):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs.addTab(widget, name)

        return layout

    def scroll_page(self, name):
        """Page défilante (onglets longs)."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        scroll.setWidget(widget)
        self.tabs.addTab(scroll, name)

        return layout

    def tab_index(self, name):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == name:
                return index

        return 0

    # --------------------------------------------------------
    # THÈME
    # --------------------------------------------------------

    def detect_scheme(self):
        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme() if hasattr(hints, "colorScheme") else None
        app = QGuiApplication.instance()
        lightness = (
            app.palette().window().color().lightness() if app else None
        )

        return str(scheme) if scheme is not None else None, lightness

    def theme_colors(self):
        return palette(self.theme_mode)

    def apply_theme(self):
        scheme, lightness = self.detect_scheme()
        self.theme_mode = resolve_mode(
            self.theme_setting, scheme, lightness
        )

        set_logo_mode(self.theme_mode)
        self.setStyleSheet(stylesheet(self.theme_mode))

        # Qt 6.8+ : barres de titre et boîtes de dialogue natives
        # alignées sur le choix ; « Unknown » = suivre le système.
        hints = QGuiApplication.styleHints()

        if hasattr(hints, "setColorScheme"):
            try:
                hints.setColorScheme(
                    {
                        "light": Qt.ColorScheme.Light,
                        "dark": Qt.ColorScheme.Dark
                    }.get(self.theme_setting, Qt.ColorScheme.Unknown)
                )

            except (AttributeError, TypeError):
                pass

        if not hasattr(self, "tabs") or not hasattr(self, "cards"):
            return

        self.update_header()
        self.refresh_chain()

        # logos : redessinés (le logo Slackware change selon le thème)
        for family, button in self.cards.items():
            button.setIcon(QIcon(logo(family, 32)))

        for family, icon in self.mapping_icons.items():
            icon.setPixmap(logo(family, 22))

        self.apply_table_icons()

        for family in self.indicators:
            self.update_indicator(family)

    def theme_changed(self, label):
        self.theme_setting = SETTING_VALUES.get(label, "system")
        self.config["theme"] = self.theme_setting

        try:
            save_settings(self.config)

        except OSError:
            pass

        self.apply_theme()

    def system_scheme_changed(self, *_):
        if self.theme_setting == "system":
            self.apply_theme()

    def role(self, widget, name):
        """Style par propriété (voir theme.py) : suit le thème choisi."""

        widget.setProperty("role", name)
        return widget

    def button(self, text, callback):
        widget = QPushButton(text)
        widget.clicked.connect(callback)
        return widget

    def combo(self, values=()):
        widget = QComboBox()
        widget.addItems(values)
        return widget

    def table(self, headers):
        widget = QTableWidget(0, len(headers))
        widget.setHorizontalHeaderLabels(headers)
        widget.setAlternatingRowColors(True)
        widget.setShowGrid(False)
        widget.horizontalHeader().setStretchLastSection(True)
        widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        widget.verticalHeader().hide()
        widget.verticalHeader().setDefaultSectionSize(29)

        widget.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        widget.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        widget.horizontalHeader().setStretchLastSection(True)

        return widget

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

        if table.property("auto"):
            # colonnes ajustées au contenu, plafonnées pour que la
            # dernière reste visible dans la fenêtre
            table.resizeColumnsToContents()

            for column in range(table.columnCount() - 1):
                table.setColumnWidth(
                    column,
                    min(max(table.columnWidth(column) + 24, 110), 420)
                )

    def selected(self, table):
        row = table.currentRow()

        if row < 0:
            return ""

        item = table.item(row, 0)
        return item.text() if item else ""

    def warning(self, message):
        QMessageBox.warning(
            self,
            "Universal Linux Builder",
            message
        )

    def information(self, message):
        QMessageBox.information(
            self,
            "Universal Linux Builder",
            message
        )

    def confirm(self, message):
        return QMessageBox.question(
            self,
            "Confirmation",
            message
        ) == QMessageBox.StandardButton.Yes

    def job(self, function, args, callback, log_view=None, tracker=None):
        if self.worker is not None:
            self.warning(
                "Une opération est déjà en cours."
            )
            return

        worker = Task(function, *args)
        self.worker = worker

        live = worker.wants_control()

        self.status.setText(
            "Opération en cours : " + function.__name__
        )

        if live:
            self.log_view = log_view
            self.log_buffer = []
            self.build_tracker = tracker

            if tracker is not None:
                self.progress.setRange(0, 100)
                self.progress.setValue(0)
                self.progress.setFormat("%p%  ·  Démarrage")

            else:
                self.progress.setRange(0, 0)
            self.progress.setVisible(True)
            self.cancel_button.setEnabled(True)
            self.cancel_button.setVisible(True)

            if log_view is not None:
                log_view.clear()
                document = log_view.document()
                document.setMaximumBlockCount(20000)

                if log_view is self.wsl_log:
                    if not self.wsl_log.isVisible():
                        self.toggle_wsl_log()

            worker.log.connect(self.queue_log)
            worker.progress.connect(self.set_progress)
            self.log_timer.start()

        worker.done.connect(
            lambda result, error, current=worker:
                self.job_done(
                    current,
                    callback,
                    result,
                    error
                )
        )

        worker.finished.connect(worker.deleteLater)

        worker.start()

    def queue_log(self, text):
        self.log_buffer.append(text)

        if self.build_tracker is not None:
            self.build_tracker.feed(text)

    def update_progress_bar(self):
        tracker = self.build_tracker

        if tracker is None:
            return

        percent, text = describe(tracker)
        self.progress.setValue(percent)
        self.progress.setFormat("%p%  ·  " + text)

    def flush_log(self):
        self.update_progress_bar()

        if not self.log_buffer:
            return

        lines, self.log_buffer = self.log_buffer, []

        if self.log_view is None:
            self.status.setText(lines[-1][:140])
            return

        bar = self.log_view.verticalScrollBar()
        follow = bar.value() >= bar.maximum() - 4

        self.log_view.moveCursor(
            self.log_view.textCursor().MoveOperation.End
        )
        self.log_view.insertPlainText("\n".join(lines) + "\n")

        if follow:
            bar.setValue(bar.maximum())

        self.status.setText(lines[-1][:140])

    def set_progress(self, value):
        if self.build_tracker is not None:
            return

        if value is None:
            self.progress.setRange(0, 0)

        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(value))

    def cancel_job(self):
        worker = self.worker

        if worker is None:
            return

        if not self.confirm(
            "Annuler l'opération en cours ?\n\n"
            "L'environnement WSL concerné sera arrêté "
            "(wsl --terminate) pour interrompre le processus Linux."
        ):
            return

        self.cancel_button.setEnabled(False)
        self.status.setText("Annulation en cours…")
        worker.cancel()

    def job_done(self, worker, callback, result, error):
        # Libère le verrou avant le rappel : un rappel peut
        # enchaîner une autre opération.
        if self.worker is worker:
            self.worker = None

        self.log_timer.stop()
        self.flush_log()

        tracker, self.build_tracker = self.build_tracker, None

        if tracker is not None and not error:
            self.build_summary = tracker.summary()

        self.progress.setFormat("%p%")
        self.progress.setVisible(False)
        self.cancel_button.setVisible(False)
        self.status.setText("Prêt")

        if error == CANCELLED:
            self.status.setText(CANCELLED)

            if self.log_view is not None:
                self.log_view.insertPlainText(
                    "\n" + CANCELLED + "\n"
                )

            self.log_view = None
            return

        self.log_view = None

        callback(result, error)

    def closeEvent(self, event):
        worker = self.worker

        self.save_timer.stop()
        self.save_project_state()

        if worker is None:
            event.accept()
            return

        if not self.confirm(
            "Une opération est en cours.\n\n"
            "Annuler l'opération et quitter ?"
        ):
            event.ignore()
            return

        worker.cancel()
        worker.wait(20000)
        event.accept()

    def combo_map(self):
        return {
            "release": self.release,
            "desktop": self.desktop,
            "kernel": self.kernel,
            "init": self.init,
            "display": self.display,
            "audio": self.audio,
            "bootloader": self.boot,
            "boot_mode": self.boot_mode,
            "profile": self.profile
        }

    def project_state(self):
        return {
            "family": self.family_name,
            "choices": {
                key: combo.currentText()
                for key, combo in self.combo_map().items()
            },
            "options": {
                name: checkbox.isChecked()
                for name, checkbox in self.flags.items()
            },
            "packages": sorted(self.selected_packages),
            "build_options": {
                "firmware": self.firmware_option.isChecked(),
                "cleanup": self.cleanup_option.isChecked()
            }
        }

    def save_project_state(self):
        if self.restoring:
            return

        self.config["project"] = self.project_state()
        self.config["version"] = VERSION

        try:
            save_settings(self.config)

        except OSError as exc:
            self.status.setText(
                "Sauvegarde impossible : " + str(exc)
            )

    def apply_project(self, project):
        """Applique un projet normalisé (voir projects.py).

        Retourne la liste des éléments ignorés."""

        ignored = []
        self.restoring = True

        try:
            self.change_family(project["family"])

            for key, value in project["choices"].items():
                combo = self.combo_map().get(key)

                if combo is None:
                    continue

                if combo.findText(value) < 0:
                    ignored.append(key + " = " + value)
                    continue

                combo.blockSignals(True)
                combo.setCurrentText(value)
                combo.blockSignals(False)

            for name, value in project["options"].items():
                if name in self.flags:
                    self.flags[name].setChecked(value)

                else:
                    ignored.append("option " + name)

            build = project["build_options"]

            if "firmware" in build:
                self.firmware_option.setChecked(build["firmware"])

            if "cleanup" in build:
                self.cleanup_option.setChecked(build["cleanup"])

            # Les paquets issus du bureau, de l'audio, des options
            # ou de GRUB sont recalculés : on ne garde comme
            # « applications » que le surplus.
            self.selected_packages.clear()
            derived = set(self.target_packages())

            self.selected_packages.update(
                name
                for name in project["packages"]
                if name not in derived
                and SAFE_PACKAGE.match(name)
            )

        finally:
            self.restoring = False

        self.refresh_selected_apps()
        self.profile_note_refresh()
        self.invalidate()
        self.update_header()
        self.refresh_target_packages()

        return ignored

    def restore_project_state(self):
        saved = self.config.get("project")

        if not isinstance(saved, dict):
            return

        try:
            self.apply_project(normalize_project(saved))

        except (ValueError, KeyError, TypeError):
            pass

    def import_project(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un projet",
            "",
            "Projet (*.json);;Tous les fichiers (*)"
        )

        if not filename:
            return

        try:
            project = read_project(filename)

        except (OSError, ValueError) as exc:
            self.warning("Import impossible : " + str(exc))
            return

        ignored = self.apply_project(project)

        message = (
            "Projet importé : "
            + project["family"]
            + " ("
            + str(len(project["packages"]))
            + " paquet(s) lus)."
        )

        if ignored:
            message += (
                "\n\nIgnoré (non disponible ici) :\n- "
                + "\n- ".join(ignored)
            )

        if project["notes"]:
            message += "\n\n" + "\n".join(project["notes"])

        self.information(message)

    def invalidate(self, *_):
        if hasattr(self, "save_timer"):
            self.save_timer.start()

        if hasattr(self, "vm_ram"):
            self.refresh_vm_defaults()

        self.revision += 1
        self.analysis_ok = False
        self.tools_ok = False

        if hasattr(self, "resolution_table") and (
            self.resolution_table.rowCount()
            or self.checks_table.rowCount()
        ):
            self.results_stale = True
            self.refresh_verification_titles()

        if hasattr(self, "chain_table"):
            self.refresh_chain()

    def iso_packages(self):
        packages = set(self.target_packages()) | set(
            LIVE_INSTALLER.get(self.family_name, [])
        )

        return sorted(
            packages
            | set(
                live_essentials(
                    self.family_name,
                    self.desktop.currentText(),
                    packages
                )
            )
        )

    def chain_rows(self):
        family = self.family_name

        return installer_checklist(
            family,
            self.desktop.currentText(),
            self.target_packages(),
            LIVE_INSTALLER.get(family, [])
        )

    def refresh_chain(self):
        rows = self.chain_rows()

        tones = self.theme_colors()

        colors = {
            "Inclus": tones["ok"],
            "Présent": tones["ok"],
            "Automatique": tones["ok"],
            "Absent": tones["bad"],
            "Non implémenté": tones["bad"],
            "À valider": tones["warn"],
            "À configurer": tones["warn"],
            "Non testé": tones["warn"]
        }

        self.chain_table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))

                if j == 1:
                    item.setForeground(
                        QColor(colors.get(value, tones["default"]))
                    )

                self.chain_table.setItem(i, j, item)

    def banner(self, layout):
        row = QHBoxLayout()

        image = QLabel()
        image.setFixedSize(26, 26)

        text = QLabel()
        self.role(text, "banner")

        row.addWidget(image)
        row.addWidget(text)
        row.addStretch()

        layout.addLayout(row)
        self.banners.append((image, text))

    def update_header(self):
        family = self.family_name
        release = self.release.currentText()

        self.header_logo.setPixmap(
            logo(family, 44)
        )

        self.subtitle.setText(
            family
            + "  •  "
            + release
            + "  |  "
            + INSTALLERS[family]
            + "  |  "
            + MANAGERS[family]
        )

        for image, text in self.banners:
            image.setPixmap(logo(family, 24))
            text.setText(
                family + " / " + release
            )

        self.refresh_verification_titles()

        for name, button in self.cards.items():
            button.setProperty("role", "card")
            button.setProperty("selected", name == family)
            button.style().unpolish(button)
            button.style().polish(button)

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

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    def make_distribution(self):
        layout = self.page("Distribution")

        title = QLabel("Choisir une distribution")
        self.role(title, "heading")
        layout.addWidget(title)

        cards = QHBoxLayout()
        cards.setSpacing(9)

        for family in FAMILIES:
            button = QPushButton(family)
            button.setIcon(QIcon(logo(family, 32)))
            button.setIconSize(QSize(32, 32))
            button.setFixedHeight(64)

            button.clicked.connect(
                lambda checked=False, f=family:
                    self.change_family(f)
            )

            cards.addWidget(button)
            self.cards[family] = button

        layout.addLayout(cards)

        form = QFormLayout()

        self.release = self.combo()
        self.release.setMaximumWidth(320)

        form.addRow("Version", self.release)

        layout.addLayout(form)

        self.release.currentTextChanged.connect(
            self.release_changed
        )

        group = QGroupBox("Composants natifs")
        group_layout = QFormLayout(group)

        self.installer_label = QLabel()
        self.manager_label = QLabel()

        group_layout.addRow(
            "Installateur",
            self.installer_label
        )

        group_layout.addRow(
            "Gestionnaire de paquets",
            self.manager_label
        )

        layout.addWidget(group)

        self.distribution_note = QLabel()
        self.distribution_note.setWordWrap(True)
        self.role(self.distribution_note, "note")

        layout.addWidget(self.distribution_note)

        layout.addStretch()
        self.next_button(layout, 1)

    # --------------------------------------------------------
    # SYSTEME
    # --------------------------------------------------------

    def make_system(self):
        layout = self.scroll_page("Système")
        self.banner(layout)

        form = QFormLayout()

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

        self.boot_mode = self.combo([
            "UEFI",
            "BIOS"
        ])

        fields = [
            ("Bureau", self.desktop),
            ("Noyau", self.kernel),
            ("Initialisation", self.init),
            ("Affichage", self.display),
            ("Audio", self.audio),
            ("Bootloader", self.boot),
            ("Amorçage", self.boot_mode)
        ]

        self.vanilla = QCheckBox("Bureau vanille")
        self.vanilla.toggled.connect(self.vanilla_changed)
        self.flags = {"Bureau vanille": self.vanilla}

        desktop_row = QHBoxLayout()
        desktop_row.addWidget(self.desktop)
        desktop_row.addWidget(self.vanilla)
        desktop_row.addStretch()

        for label, widget in fields:
            widget.setMaximumWidth(400)
            form.addRow(
                label,
                desktop_row if widget is self.desktop else widget
            )

            widget.currentTextChanged.connect(
                self.invalidate
            )

        layout.addLayout(form)

        self.vanilla_label = QLabel()
        self.vanilla_label.setWordWrap(True)
        self.role(self.vanilla_label, "muted")
        layout.addWidget(self.vanilla_label)

        self.desktop.currentTextChanged.connect(self.refresh_vanilla)

        for name, enabled in [
            ("Wi-Fi", True),
            ("Bluetooth", True),
            ("Impression", False),
            ("Firmware", True),
            ("Flathub", True),
            (FEDORA_THIRD_PARTY, False)
        ]:
            checkbox = QCheckBox(name)
            checkbox.setChecked(enabled)
            checkbox.toggled.connect(
                self.invalidate
            )

            self.flags[name] = checkbox
            layout.addWidget(checkbox)

        self.build_advanced_group(layout)

        layout.addStretch()
        self.next_button(layout, 2)

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def make_applications(self):
        layout = self.page("Applications")
        self.banner(layout)

        row = QHBoxLayout()

        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText(
            "Rechercher : firefox, vlc, gimp..."
        )

        self.search_text.returnPressed.connect(
            self.search_applications
        )

        row.addWidget(self.search_text)

        row.addWidget(
            self.button(
                "Rechercher",
                self.search_applications
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_project_repositories
            )
        )

        layout.addLayout(row)

        self.search_results = self.table([
            "Paquet",
            "Version",
            "Description"
        ])

        self.search_results.setColumnWidth(0, 270)
        self.search_results.setColumnWidth(1, 150)

        self.search_results.cellDoubleClicked.connect(
            self.add_search_result
        )

        layout.addWidget(
            self.search_results,
            3
        )

        layout.addWidget(
            QLabel("Applications ajoutées")
        )

        self.apps_table = self.table(["Paquet"])

        self.apps_table.cellDoubleClicked.connect(
            self.remove_application
        )

        layout.addWidget(
            self.apps_table,
            1
        )

        row = QHBoxLayout()

        self.manual_package = QLineEdit()
        self.manual_package.setPlaceholderText(
            "Nom exact du paquet"
        )

        row.addWidget(self.manual_package)

        row.addWidget(
            self.button(
                "Ajouter",
                self.add_manual_application
            )
        )

        layout.addLayout(row)

        self.apps_log = QTextEdit()
        self.apps_log.setReadOnly(True)
        self.apps_log.setMaximumHeight(110)

        layout.addWidget(self.apps_log)

        self.next_button(layout, 3)

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def make_verification(self):
        layout = self.page("Vérification")
        self.banner(layout)

        self.verification_status = QLabel(
            "Vérifications non effectuées"
        )

        layout.addWidget(self.verification_status)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Vérifier les outils ISO",
                self.verify_project
            )
        )

        row.addWidget(
            self.button(
                "Analyser les paquets",
                self.analyze_packages
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.context_label = QLabel()
        self.context_label.setWordWrap(True)
        self.role(self.context_label, "context")
        layout.insertWidget(1, self.context_label)

        self.checks_table = self.table([
            "Composant",
            "Paquet",
            "État"
        ])
        self.checks_table.setProperty("auto", True)

        self.checks_group = QGroupBox()
        QVBoxLayout(self.checks_group).addWidget(self.checks_table)

        self.packages_table = self.table([
            "Paquet cible",
            "Origine"
        ])
        self.packages_table.setProperty("auto", True)

        self.packages_group = QGroupBox()
        QVBoxLayout(self.packages_group).addWidget(self.packages_table)

        self.resolution_table = self.table([
            "Paquet",
            "Version",
            "Dépôt",
            "Taille",
            "Rôle"
        ])
        self.resolution_table.setProperty("auto", True)

        self.resolution_group = QGroupBox()
        QVBoxLayout(self.resolution_group).addWidget(
            self.resolution_table
        )

        self.verification_log = QTextEdit()
        self.verification_log.setReadOnly(True)
        self.verification_log.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.verification_log.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )

        self.log_group = QGroupBox()
        QVBoxLayout(self.log_group).addWidget(self.verification_log)

        # un sous-onglet par étape : chaque tableau garde toute la hauteur
        self.verification_tabs = QTabWidget()
        self.verification_tabs.addTab(self.checks_group, "Outils")
        self.verification_tabs.addTab(self.packages_group, "Paquets cibles")
        self.verification_tabs.addTab(self.resolution_group, "Résolution")
        self.verification_tabs.addTab(self.log_group, "Sortie native")
        layout.addWidget(self.verification_tabs, 1)

        self.results_family = ""
        self.refresh_verification_titles()

        self.next_button(layout, 4)

    # --------------------------------------------------------
    # ISO
    # --------------------------------------------------------

    # --------------------------------------------------------
    # VIRTUALISATION
    # --------------------------------------------------------

    def make_virtualization(self):
        layout = self.page("Virtualisation")
        self.banner(layout)

        note = QLabel(
            "Essaie l'image dans une machine virtuelle QEMU/KVM "
            "réglée d'après le projet : mode UEFI/BIOS, mémoire selon "
            "le bureau. Un disque virtuel persistant permet de tester "
            "l'installateur (Calamares / Anaconda) puis de démarrer "
            "sur le disque installé pour vérifier GRUB."
        )
        note.setWordWrap(True)
        self.role(note, "note")
        layout.addWidget(note)

        group = QGroupBox("Machine virtuelle")
        form = QFormLayout(group)

        iso_row = QHBoxLayout()
        self.vm_iso = QLineEdit()
        self.vm_iso.setPlaceholderText(
            "ISO à démarrer (construite ici ou officielle)"
        )
        iso_row.addWidget(self.vm_iso, 1)
        iso_row.addWidget(
            self.button("Parcourir…", self.browse_vm_iso)
        )
        form.addRow("ISO", iso_row)

        self.vm_boot = self.combo(VM_BOOTS)
        form.addRow("Démarrage", self.vm_boot)

        self.vm_mode = self.combo(["UEFI", "BIOS"])
        form.addRow("Firmware", self.vm_mode)

        self.vm_ram = QSpinBox()
        self.vm_ram.setRange(512, 65536)
        self.vm_ram.setSingleStep(512)
        self.vm_ram.setSuffix(" Mo")
        self.vm_ram.valueChanged.connect(self.vm_ram_edited)
        form.addRow("Mémoire", self.vm_ram)

        self.vm_cpus = QSpinBox()
        self.vm_cpus.setRange(1, 32)
        self.vm_cpus.setValue(2)
        form.addRow("Processeurs", self.vm_cpus)

        self.vm_disk = QSpinBox()
        self.vm_disk.setRange(4, 512)
        self.vm_disk.setValue(32)
        self.vm_disk.setSuffix(" Go")
        form.addRow("Disque virtuel", self.vm_disk)

        self.vm_display = self.combo(VM_DISPLAYS)
        form.addRow("Affichage", self.vm_display)

        layout.addWidget(group)

        row = QHBoxLayout()

        self.vm_start_button = self.button(
            "Démarrer la machine", self.start_vm
        )
        row.addWidget(self.vm_start_button)

        self.vm_stop_button = self.button(
            "Arrêter", self.stop_vm_clicked
        )
        self.vm_stop_button.setEnabled(False)
        row.addWidget(self.vm_stop_button)

        self.vm_open_button = self.button(
            "Ouvrir l'affichage web", self.open_vm_display
        )
        self.vm_open_button.setEnabled(False)
        row.addWidget(self.vm_open_button)

        row.addWidget(
            self.button(
                "Installer QEMU / noVNC", self.install_vm_tools_clicked
            )
        )

        row.addWidget(
            self.button(
                "Recréer le disque", self.reset_vm_disk_clicked
            )
        )

        row.addStretch()
        layout.addLayout(row)

        self.vm_log = QTextEdit()
        self.vm_log.setReadOnly(True)
        self.vm_log.document().setMaximumBlockCount(5000)
        layout.addWidget(self.vm_log, 1)


        self.refresh_vm_defaults()

    def refresh_vm_defaults(self):
        if self.vm_ram_auto:
            self.vm_ram.blockSignals(True)
            self.vm_ram.setValue(
                VM_RAM.get(self.desktop.currentText(), 2048)
            )
            self.vm_ram.blockSignals(False)

        mode = self.boot_mode.currentText()

        if self.vm_mode.currentText() != mode:
            self.vm_mode.setCurrentText(mode)

    def vm_ram_edited(self, _value):
        self.vm_ram_auto = False

    def browse_vm_iso(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir l'ISO",
            self.vm_iso.text() or self.last_iso,
            "Images ISO (*.iso)"
        )

        if filename:
            self.vm_iso.setText(filename)

    def vm_running(self):
        return self.vm_task is not None and self.vm_task.isRunning()

    def start_vm(self):
        if self.vm_running():
            self.warning("La machine virtuelle tourne déjà.")
            return

        family = self.family_name

        if family not in BUILD_FAMILIES + REMASTER_FAMILIES:
            self.warning(
                "Virtualisation disponible pour Debian, Fedora, "
                "Arch Linux, Gentoo et Slackware."
            )
            return

        env = (
            self.remaster_environment()
            if family in REMASTER_FAMILIES
            else self.project_environment()
        )

        if not env:
            return

        boot = (
            "iso"
            if self.vm_boot.currentIndex() == 0
            else "disk"
        )

        display = ["web", "window", "vnc"][
            self.vm_display.currentIndex()
        ]

        iso = self.vm_iso.text().strip()

        if boot == "iso" and not Path(iso).is_file():
            self.warning("Choisis une ISO existante.")
            return

        self.vm_env = env
        self.vm_url = ""
        self.vm_log.clear()
        self.vm_open_button.setEnabled(False)

        task = Task(
            run_vm,
            env,
            self.vm_id,
            iso,
            self.vm_mode.currentText(),
            boot,
            self.vm_ram.value(),
            self.vm_cpus.value(),
            self.vm_disk.value(),
            display
        )

        task.log.connect(self.vm_line)
        task.done.connect(self.vm_finished)
        self.vm_task = task

        self.vm_start_button.setEnabled(False)
        self.vm_stop_button.setEnabled(True)

        task.start()

    def vm_line(self, text):
        if text.startswith(URL_MARKER):
            self.vm_url = text[len(URL_MARKER):].strip()
            self.vm_open_button.setEnabled(True)
            self.vm_log.insertPlainText(
                "Affichage web : " + self.vm_url + "\n"
            )
            QDesktopServices.openUrl(QUrl(self.vm_url))
            return

        if text.startswith(INFO_MARKER):
            text = text[len(INFO_MARKER):]

        # bruit inoffensif de PipeWire (audio) au démarrage de QEMU
        if "pw.conf" in text and "client.conf" in text:
            return

        self.vm_log.insertPlainText(text + "\n")

    def vm_finished(self, result, error):
        self.vm_start_button.setEnabled(True)
        self.vm_stop_button.setEnabled(False)
        self.vm_open_button.setEnabled(False)

        self.vm_log.insertPlainText(
            "\n===== MACHINE ARRÊTÉE =====\n"
            + (error + "\n" if error else "")
        )

    def stop_vm_clicked(self):
        if not self.vm_running():
            return

        self.vm_task.cancel()

        self.vm_stopper = Task(
            stop_vm, self.vm_env, self.vm_id
        )
        self.vm_stopper.start()

    def open_vm_display(self):
        if self.vm_url:
            QDesktopServices.openUrl(QUrl(self.vm_url))

    def install_vm_tools_clicked(self):
        env = self.selected_or_project_environment()

        if not env:
            return

        family = self.environment_family(env)

        if not self.confirm(
            "Installer QEMU, OVMF et noVNC dans " + env + " ?\n\n"
            "Les paquets sont installés un par un ; ceux "
            "introuvables sont signalés dans le journal."
        ):
            return

        self.job(
            install_vm_tools,
            (env, family),
            self.vm_tools_done,
            self.vm_log
        )

    def selected_or_project_environment(self):
        if self.family_name in REMASTER_FAMILIES:
            return self.remaster_environment()

        name = self.associations.get(self.family_name, "")

        if self.environment_item(name) is not None:
            return name

        return self.project_environment()

    def vm_tools_done(self, data, error):
        if error:
            self.vm_log.insertPlainText("\nERREUR : " + error + "\n")
            return

        self.vm_log.insertPlainText(
            "\n===== INSTALLATION TERMINÉE =====\n"
            "Cherche « ÉCHEC : » ci-dessus pour les paquets "
            "introuvables.\n"
        )

    def reset_vm_disk_clicked(self):
        env = self.selected_or_project_environment()

        if not env or self.vm_running():
            if self.vm_running():
                self.warning("Arrête d'abord la machine.")

            return

        if not self.confirm(
            "Supprimer le disque virtuel et les variables UEFI ?\n\n"
            "Le système installé dans la machine sera perdu."
        ):
            return

        self.job(
            reset_vm_disk,
            (env,),
            lambda data, error: self.vm_log.insertPlainText(
                ("Erreur : " + error if error else "Disque supprimé.")
                + "\n"
            )
        )

    def build_output_group(self, layout):
        box = QGroupBox("Destination de l'ISO")
        form = QFormLayout(box)

        saved = self.config.get("output", {})
        saved = saved if isinstance(saved, dict) else {}

        self.out_folder = QLineEdit(str(saved.get("folder", "")))
        self.out_folder.setPlaceholderText(
            "vide = demander le dossier à chaque construction"
        )
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self.choose_output_folder)

        row = QHBoxLayout()
        row.addWidget(self.out_folder, 1)
        row.addWidget(browse)
        form.addRow("Dossier", row)

        self.out_name = QLineEdit(str(saved.get("name", "")))
        self.out_name.setPlaceholderText(
            "vide = nom automatique ULB_<distribution>_<version>_<date>.iso"
        )
        self.out_name.setToolTip(
            "L'extension .iso est ajoutée si besoin. Un fichier existant "
            "n'est jamais écrasé : -2, -3… est ajouté au nom."
        )
        form.addRow("Nom du fichier", self.out_name)

        self.out_preview = QLabel()
        self.out_preview.setWordWrap(True)
        self.role(self.out_preview, "muted")
        form.addRow(self.out_preview)

        self.out_folder.textChanged.connect(self.output_changed)
        self.out_name.textChanged.connect(self.output_changed)
        self.refresh_output()
        layout.addWidget(box)

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination des ISO",
            self.out_folder.text().strip()
        )

        if folder:
            self.out_folder.setText(folder)

    def refresh_output(self):
        name = clean_iso_name(self.out_name.text())
        folder = self.out_folder.text().strip()
        problem = check_folder(folder) if folder else ""

        self.out_preview.setText(
            problem
            if problem
            else "Fichier : "
            + (name or "nom automatique")
            + (" — dans " + folder if folder else " — dossier demandé au lancement")
        )

    def output_changed(self, *_):
        self.refresh_output()

        self.config["output"] = {
            "folder": self.out_folder.text().strip(),
            "name": self.out_name.text().strip()
        }

        try:
            save_settings(self.config)

        except OSError:
            pass

    def output_folder(self):
        """Dossier mémorisé s'il existe, sinon boîte de dialogue ; '' = annulé."""

        folder = self.out_folder.text().strip()

        if folder:
            problem = check_folder(folder)

            if not problem:
                return folder

            self.warning(problem)
            return ""

        return QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination "
            "(il peut contenir d'autres fichiers)"
        )

    def make_iso(self):
        layout = self.page("ISO")
        self.banner(layout)

        self.iso_status = QLabel()
        self.iso_status.setWordWrap(True)
        layout.addWidget(self.iso_status)

        self.iso_note = QLabel(
            "La vérification d'une signature ISO9660 "
            "ne constitue pas un test de démarrage.\n"
            "Une ISO doit être testée en machine virtuelle, "
            "puis avec Ventoy et son installateur."
        )

        self.iso_note.setWordWrap(True)
        self.role(self.iso_note, "note")

        layout.addWidget(self.iso_note)

        self.build_output_group(layout)
        self.build_remaster_group(layout)

        layout.addWidget(
            QLabel("Chaîne d'installation")
        )

        self.chain_table = self.table([
            "Élément",
            "État",
            "Remarque"
        ])

        self.chain_table.setSortingEnabled(False)
        self.chain_table.setColumnWidth(0, 300)
        self.chain_table.setColumnWidth(1, 130)
        self.chain_table.setMaximumHeight(215)

        layout.addWidget(self.chain_table)

        options = QGroupBox("Options de construction")
        self.build_options_box = options
        form = QFormLayout(options)

        self.profile = self.combo(PROFILES)
        self.profile.setFixedWidth(150)
        self.profile.currentTextChanged.connect(
            self.profile_changed
        )

        self.profile_note = QLabel()
        self.profile_note.setWordWrap(True)
        self.role(self.profile_note, "note")

        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile)
        profile_row.addWidget(self.profile_note, 1)
        form.addRow("Profil", profile_row)

        self.firmware_option = QCheckBox(
            "Inclure les micrologiciels non libres "
            "(Wi-Fi, GPU) — Debian"
        )
        self.firmware_option.setChecked(True)

        self.cleanup_option = QCheckBox(
            "Supprimer l'espace de travail WSL après la copie"
        )
        self.cleanup_option.setChecked(True)

        checks = QHBoxLayout()
        checks.addWidget(self.firmware_option)
        checks.addWidget(self.cleanup_option)
        checks.addStretch()
        form.addRow("", checks)

        layout.addWidget(options)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Exporter le projet",
                self.export_current_project
            )
        )

        row.addWidget(
            self.button(
                "Importer un projet",
                self.import_project
            )
        )

        self.build_button = self.button(
            "Créer l'ISO expérimentale",
            self.create_iso
        )

        row.addWidget(self.build_button)
        row.addStretch()

        layout.addLayout(row)

        vm_row = QHBoxLayout()

        vm_row.addWidget(
            self.button(
                "Tester le démarrage (QEMU)",
                self.test_boot
            )
        )

        self.smoke_mode = self.combo(["UEFI", "BIOS"])
        vm_row.addWidget(self.smoke_mode)

        self.smoke_wait = self.combo(["60 s", "120 s", "240 s"])
        self.smoke_wait.setCurrentText("120 s")
        vm_row.addWidget(self.smoke_wait)

        vm_row.addWidget(
            QLabel(
                "Capture d'écran après le délai ; "
                "ne valide pas l'installateur."
            )
        )

        vm_row.addStretch()
        layout.addLayout(vm_row)

        split = QHBoxLayout()

        self.iso_log = QTextEdit()
        self.iso_log.setReadOnly(True)
        split.addWidget(self.iso_log, 3)

        self.boot_preview = QLabel("Aucune capture")
        self.boot_preview.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.boot_preview.setMinimumWidth(320)
        self.role(self.boot_preview, "preview")
        split.addWidget(self.boot_preview, 2)

        layout.addLayout(split, 1)

    # --------------------------------------------------------
    # WSL2
    # --------------------------------------------------------

    def make_wsl(self):
        layout = self.page("Configuration")

        title = QLabel("Environnements WSL2")
        self.role(title, "heading")
        layout.addWidget(title)

        self.wsl_sections = QTabWidget()
        self.wsl_sections.setObjectName("sections")
        layout.addWidget(self.wsl_sections, 1)

        def section(name):
            widget = QWidget()

            section_layout = QVBoxLayout(widget)
            section_layout.setContentsMargins(12, 12, 12, 12)
            section_layout.setSpacing(10)

            self.wsl_sections.addTab(widget, name)

            return section_layout

        # ----------------------------------------------------
        # SOUS-ONGLET 1 : ENVIRONNEMENTS
        # ----------------------------------------------------

        environments = section("Environnements")

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Actualiser les WSL",
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
        environments.addLayout(row)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        installed_group = QGroupBox(
            "Distributions installées"
        )

        installed_layout = QVBoxLayout(installed_group)

        self.installed_table = self.table([
            "Nom WSL",
            "Famille",
            "Version"
        ])

        self.installed_table.setColumnWidth(0, 190)
        self.installed_table.setColumnWidth(1, 150)

        installed_layout.addWidget(
            self.installed_table
        )

        installed_layout.addWidget(
            self.button(
                "Supprimer la distribution",
                self.remove_wsl
            )
        )

        splitter.addWidget(installed_group)

        catalog_group = QGroupBox(
            "Distributions disponibles"
        )

        catalog_layout = QVBoxLayout(catalog_group)

        self.catalog_table = self.table([
            "Distribution",
            "Description"
        ])

        self.catalog_table.setColumnWidth(0, 190)

        catalog_layout.addWidget(
            self.catalog_table
        )

        catalog_layout.addWidget(
            self.button(
                "Installer dans WSL2",
                self.install_wsl
            )
        )

        splitter.addWidget(catalog_group)
        splitter.setSizes([560, 560])

        environments.addWidget(splitter, 1)

        # ----------------------------------------------------
        # SOUS-ONGLET 2 : OUTILS ET DEPOTS
        # ----------------------------------------------------

        tools_layout = section("Outils et dépôts")

        row = QHBoxLayout()

        row.addWidget(
            QLabel("Environnement")
        )

        self.wsl_choice = self.combo()
        row.addWidget(self.wsl_choice, 1)

        row.addWidget(
            self.button(
                "Tester le gestionnaire",
                self.test_selected_manager
            )
        )

        row.addWidget(
            self.button(
                "Vérifier les outils",
                self.check_selected_tools
            )
        )

        row.addWidget(
            self.button(
                "Installer les outils",
                self.install_selected_tools
            )
        )

        row.addWidget(
            self.button(
                "Actualiser les dépôts",
                self.update_selected_repositories
            )
        )

        tools_layout.addLayout(row)

        self.wsl_tools_table = self.table([
            "Exécutable",
            "Paquet requis",
            "État"
        ])

        self.wsl_tools_table.setColumnWidth(0, 230)
        self.wsl_tools_table.setColumnWidth(1, 270)

        tools_layout.addWidget(
            self.wsl_tools_table,
            1
        )

        # ----------------------------------------------------
        # SOUS-ONGLET 3 : ASSOCIATIONS
        # ----------------------------------------------------

        associations_layout = section("Associations")

        note = QLabel(
            "Chaque famille du projet est associée "
            "automatiquement à un environnement WSL2 "
            "compatible.\n"
            "Les choix manuels sont enregistrés et "
            "restaurés au démarrage."
        )

        note.setWordWrap(True)
        self.role(note, "note")

        associations_layout.addWidget(note)

        group = QGroupBox(
            "Environnements de construction"
        )

        form = QFormLayout(group)

        self.mapping_boxes = {}
        self.mapping_icons = {}
        self.indicators = {}

        for family in FAMILIES:
            row = QHBoxLayout()

            icon = QLabel()
            icon.setFixedSize(24, 24)
            icon.setPixmap(logo(family, 22))
            self.mapping_icons[family] = icon

            row.addWidget(icon)

            combo = self.combo(["— Non associé —"])

            combo.currentTextChanged.connect(
                lambda value, f=family:
                    self.mapping_changed(f, value)
            )

            row.addWidget(combo, 1)

            indicator = QLabel("○ Non associé")
            indicator.setMinimumWidth(130)

            row.addWidget(indicator)

            form.addRow(family, row)

            self.mapping_boxes[family] = combo
            self.indicators[family] = indicator

        associations_layout.addWidget(group)

        row = QHBoxLayout()

        row.addWidget(
            self.button(
                "Réassocier automatiquement",
                self.reset_associations
            )
        )

        row.addStretch()

        associations_layout.addLayout(row)
        associations_layout.addStretch()

        # ----------------------------------------------------
        # JOURNAL REPLIABLE
        # ----------------------------------------------------

        row = QHBoxLayout()

        self.log_button = self.button(
            "Afficher le journal ▾",
            self.toggle_wsl_log
        )

        row.addWidget(self.log_button)
        row.addStretch()

        layout.addLayout(row)

        self.wsl_log = QTextEdit()
        self.wsl_log.setReadOnly(True)
        self.wsl_log.setVisible(False)
        self.wsl_log.setMaximumHeight(155)

        layout.addWidget(self.wsl_log)

    # --------------------------------------------------------
    # SELECTION DISTRIBUTION
    # --------------------------------------------------------

    def change_family(self, family):
        self.family_name = family

        self.release.blockSignals(True)
        self.release.clear()
        self.release.addItems(RELEASES[family])
        self.release.blockSignals(False)

        self.desktop.blockSignals(True)
        self.desktop.clear()
        self.desktop.addItems(DESKTOPS[family].keys())
        self.desktop.blockSignals(False)

        self.init.blockSignals(True)
        self.init.clear()

        if family == "Gentoo":
            self.init.addItems([
                "OpenRC",
                "systemd"
            ])

        elif family == "Slackware":
            self.init.addItem("SysVinit")

        else:
            self.init.addItem("systemd")

        self.init.blockSignals(False)

        self.kernel.setEnabled(
            family == "Arch Linux"
        )

        self.kernel.setCurrentText("Stable")

        # Option propre à Fedora : invisible pour les autres familles.
        self.flags[FEDORA_THIRD_PARTY].setVisible(
            family == "Fedora"
        )

        self.installer_label.setText(
            INSTALLERS[family]
        )

        self.manager_label.setText(
            MANAGERS[family]
        )

        self.distribution_note.setText(
            "Le gestionnaire de paquets natif et les dépôts "
            "devront rester fonctionnels après l'installation.\n"
            "WSL2 sert uniquement à préparer le projet."
            + (
                "\nBudgie n'est pas proposé : absent des dépôts "
                "officiels ou non pris en charge ici."
                if family in ("Gentoo", "Slackware")
                else ""
            )
        )

        supported = family in BUILD_FAMILIES + REMASTER_FAMILIES

        self.build_button.setEnabled(supported)

        if supported:
            self.iso_status.setText(
                "Construction expérimentale disponible pour "
                + family
                + ". L'installation sur disque et le démarrage "
                "ne sont pas encore validés."
            )
        else:
            self.iso_status.setText(
                "Construction ISO non implémentée pour "
                + family
                + ". Tu peux vérifier les outils et exporter "
                "le projet."
            )

        self.selected_packages.clear()
        self.refresh_selected_apps()

        self.invalidate()
        self.update_header()

        if hasattr(self, "checks_table"):
            self.clear_verification()

        self.refresh_target_packages()

        if self.inventory:
            self.apply_associations()

        self.refresh_remaster()
        self.refresh_advanced()

        if hasattr(self, "wsl_choice"):
            self.refresh_environment_choice()

        self.refresh_vanilla()

    def release_changed(self, *_):
        self.invalidate()
        self.update_header()

        if self.inventory:
            self.apply_associations()

    # --------------------------------------------------------
    # WSL2 : JOURNAL
    # --------------------------------------------------------

    def toggle_wsl_log(self):
        visible = not self.wsl_log.isVisible()

        self.wsl_log.setVisible(visible)

        self.log_button.setText(
            "Masquer le journal ▴"
            if visible
            else "Afficher le journal ▾"
        )

    def show_wsl_log(self, message):
        self.wsl_log.setPlainText(str(message))

        if not self.wsl_log.isVisible():
            self.toggle_wsl_log()

    # --------------------------------------------------------
    # WSL2 : SAUVEGARDE DES ASSOCIATIONS
    # --------------------------------------------------------

    def persist_associations(self):
        self.config["version"] = VERSION

        self.config["wsl_associations"] = dict(
            self.associations
        )

        self.config["manual_associations"] = sorted(
            self.manual_associations
        )

        try:
            save_settings(self.config)

        except OSError as exc:
            self.status.setText(
                "Sauvegarde impossible : " + str(exc)
            )

    # --------------------------------------------------------
    # WSL2 : DETECTION AUTOMATIQUE
    # --------------------------------------------------------

    def refresh_wsl(self):
        self.job(
            wsl_names,
            (),
            self.wsl_names_ready
        )

    def wsl_names_ready(self, names, error):
        if error:
            self.show_wsl_log(error)
            return

        self.job(
            detect_all,
            (names,),
            self.inventory_ready
        )

    def inventory_ready(self, items, error):
        if error:
            self.show_wsl_log(error)
            return

        self.inventory = items
        self.refresh_remaster()

        self.fill(
            self.installed_table,
            [
                (
                    item["name"],
                    item["family"],
                    item["version"]
                )
                for item in items
            ]
        )

        self.apply_table_icons()

        names = [item["name"] for item in items]
        self.wsl_names_cache = names
        self.refresh_environment_choice()

        self.apply_associations()

        self.wsl_log.setPlainText(
            "Détection terminée : "
            + str(len(items))
            + " environnement(s).\n\n"
            + "\n".join(
                item["name"]
                + " → "
                + item["family"]
                + " "
                + item["version"]
                for item in items
            )
        )

    def apply_table_icons(self):
        for row in range(self.installed_table.rowCount()):
            cell = self.installed_table.item(row, 1)

            if cell and cell.text() in LOGOS:
                cell.setIcon(
                    QIcon(logo(cell.text(), 18))
                )

    def environment_item(self, name):
        return next(
            (
                item
                for item in self.inventory
                if item["name"] == name
            ),
            None
        )

    def environment_family(self, name):
        item = self.environment_item(name)

        return item["family"] if item else ""

    def apply_associations(self):
        names = [
            item["name"]
            for item in self.inventory
        ]

        changed = False

        for family in FAMILIES:
            saved = self.associations.get(family, "")
            item = self.environment_item(saved)

            valid = (
                item is not None
                and item["family"] == family
            ) or (
                saved == INTERNET
                and family in INTERNET_FAMILIES
            )

            if not valid:
                if (
                    family in self.manual_associations
                    and saved == ""
                ):
                    choice = ""

                else:
                    release = (
                        self.release.currentText()
                        if family == self.family_name
                        else RELEASES[family][0]
                    )

                    choice = best_match(
                        family,
                        release,
                        self.inventory
                    )

                    self.manual_associations.discard(family)

                    # Gentoo / Slackware sans WSL : catalogue Internet.
                    if not choice and family in INTERNET_FAMILIES:
                        choice = INTERNET

                if choice != saved:
                    self.associations[family] = choice
                    changed = True

            combo = self.mapping_boxes[family]

            combo.blockSignals(True)
            combo.clear()

            extra = (
                [INTERNET] if family in INTERNET_FAMILIES else []
            )

            combo.addItems(
                ["— Non associé —"] + extra + names
            )

            chosen = self.associations.get(family, "")

            if chosen in names or chosen in extra:
                combo.setCurrentText(chosen)

            combo.blockSignals(False)

            self.update_indicator(family)

        if changed:
            self.persist_associations()
            self.invalidate()

    def update_indicator(self, family):
        name = self.associations.get(family, "")
        item = self.environment_item(name)

        if name == INTERNET and family in INTERNET_FAMILIES:
            message = "● Internet"
            state = "ok"

        elif item is None or item["family"] != family:
            message = "○ Non associé"
            state = "off"

        else:
            desired = (
                self.release.currentText()
                if family == self.family_name
                else RELEASES[family][0]
            )

            mismatch = (
                family in ("Debian", "Fedora", "Slackware")
                and desired not in (
                    item["version"],
                    item["codename"]
                )
            )

            if mismatch:
                message = "● À vérifier"
                state = "warn"

            else:
                message = "● Connecté"
                state = "ok"

        self.indicators[family].setText(message)

        indicator = self.indicators[family]
        indicator.setProperty("state", state)
        indicator.style().unpolish(indicator)
        indicator.style().polish(indicator)

    def mapping_changed(self, family, name):
        chosen = (
            ""
            if name == "— Non associé —"
            else name
        )

        item = self.environment_item(chosen)

        if item and item["family"] != family:
            self.warning(
                "Cette distribution WSL appartient à "
                + item["family"]
                + ", pas à "
                + family
            )

            self.apply_associations()
            return

        self.associations[family] = chosen
        self.manual_associations.add(family)

        self.persist_associations()
        self.update_indicator(family)
        self.invalidate()

    def reset_associations(self):
        if not self.confirm(
            "Effacer les associations manuelles "
            "et refaire la détection automatique ?"
        ):
            return

        self.manual_associations.clear()
        self.associations = {
            family: ""
            for family in FAMILIES
        }

        self.apply_associations()
        self.persist_associations()

    # --------------------------------------------------------
    # WSL2 : ENVIRONNEMENT SELECTIONNE ET PROJET
    # --------------------------------------------------------

    def refresh_environment_choice(self):
        """WSL installés + (Gentoo / Slackware seulement) le dépôt
        internet de la famille choisie."""

        previous = self.wsl_choice.currentText()
        names = list(getattr(self, "wsl_names_cache", []))

        if self.family_name in INTERNET_FAMILIES:
            names.append(online_label(self.family_name))

        self.wsl_choice.blockSignals(True)
        self.wsl_choice.clear()
        self.wsl_choice.addItems(names)

        if previous in names:
            self.wsl_choice.setCurrentText(previous)

        self.wsl_choice.blockSignals(False)

    def selected_online_family(self):
        text = self.wsl_choice.currentText()

        return next(
            (
                family for family in INTERNET_FAMILIES
                if text == online_label(family)
            ),
            ""
        )

    def selected_environment(self):
        name = self.wsl_choice.currentText()

        if self.environment_item(name) is None:
            self.warning(
                "Sélectionne un environnement WSL installé."
            )
            return ""

        return name

    def project_environment(self):
        name = self.associations.get(
            self.family_name,
            ""
        )

        item = self.environment_item(name)

        if name == INTERNET and self.family_name in INTERNET_FAMILIES:
            self.warning(
                "Mode « Dépôt internet » : seule la recherche de "
                "paquets est disponible. Les outils et l'analyse des "
                "dépendances demandent un WSL " + self.family_name
                + " (onglet Configuration)."
            )
            return ""

        if (
            item is None
            or item["family"] != self.family_name
        ):
            self.warning(
                "Associe un environnement WSL compatible avec "
                + self.family_name
                + " dans l'onglet Configuration."
            )

            self.tabs.setCurrentIndex(self.tab_index("Configuration"))
            self.wsl_sections.setCurrentIndex(2)

            return ""

        return name

    # --------------------------------------------------------
    # WSL2 : CATALOGUE, INSTALLATION, SUPPRESSION
    # --------------------------------------------------------

    def refresh_catalog(self):
        self.job(
            online_catalog,
            (),
            self.catalog_ready
        )

    def catalog_ready(self, data, error):
        if error:
            self.show_wsl_log(error)
            return

        rows, raw = data
        self.catalog_rows = rows

        self.fill(
            self.catalog_table,
            rows
        )

        self.wsl_log.setPlainText(
            str(len(rows))
            + " distributions disponibles.\n"
            + (raw[:1500] if not rows else "")
        )

    def install_wsl(self):
        name = self.selected(
            self.catalog_table
        )

        if name not in [row[0] for row in self.catalog_rows]:
            self.warning(
                "Sélectionne une distribution du catalogue."
            )
            return

        if self.environment_item(name) is not None:
            self.warning("Déjà installée.")
            return

        if not self.confirm(
            "Installer " + name + " dans WSL2 ?"
        ):
            return

        self.job(
            install_distribution,
            (name,),
            lambda data, error:
                self.wsl_operation_done(
                    "Installation",
                    data,
                    error
                ),
            self.wsl_log
        )

    def remove_wsl(self):
        name = self.selected(
            self.installed_table
        )

        if not name:
            self.warning(
                "Sélectionne une distribution installée."
            )
            return

        typed, ok = QInputDialog.getText(
            self,
            "Suppression définitive",
            "Toutes les données de "
            + name
            + " seront supprimées.\n"
            "Saisis exactement : " + name
        )

        if not ok or typed != name:
            return

        if not self.confirm(
            "Supprimer définitivement " + name + " ?"
        ):
            return

        self.job(
            run,
            (
                ["wsl.exe", "--unregister", name],
                900
            ),
            lambda data, error:
                self.wsl_operation_done(
                    "Suppression",
                    data,
                    error
                )
        )

    def wsl_operation_done(self, title, data, error):
        if error:
            self.show_wsl_log(error)
            return

        output, stderr, code = data

        self.show_wsl_log(
            title
            + "\nCode retour : "
            + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

        if code == 0:
            self.refresh_wsl()

        else:
            self.warning(title + " échouée.")

    # --------------------------------------------------------
    # WSL2 : GESTIONNAIRE ET OUTILS
    # --------------------------------------------------------

    def test_selected_manager(self):
        if self.selected_online_family():
            self.start_online_update(self.selected_online_family())
            return

        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in MANAGER_BINARY:
            self.warning("Famille Linux inconnue.")
            return

        self.job(
            test_manager,
            (name, family),
            lambda data, error:
                self.manager_test_done(name, family, data, error)
        )

    def manager_test_done(self, name, family, data, error):
        if error:
            self.show_wsl_log(error)
            self.warning("Test du gestionnaire impossible :\n" + error)
            return

        command, response = data
        output, stderr, code = response

        ok, title, detail = manager_report(
            name, family, output, stderr, code
        )

        self.show_wsl_log(
            ("✔ " if ok else "✘ ") + title + "\n\n" + detail
            + "\n\nCommande : " + command
        )

        if ok:
            self.information(title + "\n\n" + detail)

        else:
            self.warning(title + "\n\n" + detail)

    def online_has_no_tools(self):
        if not self.selected_online_family():
            return False

        self.information(
            "Un dépôt internet n'a pas d'outils à vérifier ni à "
            "installer : seule l'actualisation du catalogue est utile."
        )

        return True

    def check_selected_tools(self):
        if self.online_has_no_tools():
            return

        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in BUILD_TOOLS:
            self.warning("Famille Linux inconnue.")
            return

        self.job(
            check_tools,
            (name, family),
            self.selected_tools_done
        )

    def selected_tools_done(self, rows, error):
        if error:
            self.show_wsl_log(error)
            return

        self.fill(
            self.wsl_tools_table,
            rows
        )

        missing = [
            row[0]
            for row in rows
            if row[2] == "Absent"
        ]

        self.status.setText(
            "Outils manquants : "
            + (", ".join(missing) if missing else "aucun")
        )

    def install_selected_tools(self):
        if self.online_has_no_tools():
            return

        name = self.selected_environment()

        if not name:
            return

        family = self.environment_family(name)

        if family not in (
            "Debian",
            "Fedora",
            "Arch Linux"
        ):
            self.warning(
                "Installation automatisée non validée pour "
                + family
            )
            return

        if not self.confirm(
            "Installer les outils de construction dans "
            + name
            + " ?\n\n"
            "Cette opération modifie cet environnement WSL "
            "et peut télécharger plusieurs paquets."
        ):
            return

        self.job(
            install_tools,
            (name, family),
            self.install_tools_done,
            self.wsl_log
        )

    def install_tools_done(self, data, error):
        if error:
            self.show_wsl_log(error)
            self.warning("Installation impossible :\n" + error)
            return

        command, response = data
        output, stderr, code = response

        self.show_wsl_log(
            "Commande : " + command
            + "\nCode : " + str(code)
            + "\n\n"
            + output[-9000:]
            + "\n"
            + stderr[-5000:]
        )

        if code:
            self.warning(
                "Installation échouée. Consulte le journal."
            )

        else:
            self.invalidate()
            self.check_selected_tools()

    # --------------------------------------------------------
    # WSL2 : ACTUALISATION DES DEPOTS
    # --------------------------------------------------------

    def update_selected_repositories(self):
        if self.selected_online_family():
            self.start_online_update(self.selected_online_family())
            return

        name = self.selected_environment()

        if name:
            self.start_update(name)

    def update_project_repositories(self):
        if self.uses_internet_catalog():
            self.start_online_update(self.family_name)
            return

        name = self.project_environment()

        if name:
            self.start_update(name)

    def start_online_update(self, family):
        release = (
            self.release.currentText()
            if family == self.family_name
            else RELEASES[family][0]
        )

        self.job(
            refresh_online,
            (family, release),
            lambda data, error:
                self.update_done(online_label(family), data, error),
            self.wsl_log
        )

    def start_update(self, name):
        family = self.environment_family(name)

        if family not in MANAGER_BINARY:
            self.warning("Famille Linux inconnue.")
            return

        if not self.confirm(update_message(name, family)):
            return

        self.job(
            update_repositories,
            (name, family),
            lambda data, error:
                self.update_done(name, data, error),
            self.wsl_log
        )

    def update_done(self, name, data, error):
        if error:
            self.show_wsl_log(error)
            self.apps_log.setPlainText(error)
            return

        command, response = data
        output, stderr, code = response

        message = (
            "Environnement : " + name
            + "\nCommande : " + command
            + "\nCode : " + str(code)
            + "\n\n"
            + output
            + "\n"
            + stderr
        )

        self.show_wsl_log(message[-15000:])
        self.apps_log.setPlainText(message[-3500:])

        if code:
            self.warning(
                "Actualisation échouée. Consulte le journal."
            )

        else:
            self.information(
                "Dépôts actualisés pour " + name
            )

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    def refresh_selected_apps(self):
        self.fill(
            self.apps_table,
            [
                (name,)
                for name in sorted(self.selected_packages)
            ]
        )

    def add_manual_application(self):
        name = self.manual_package.text().strip()

        if not SAFE_PACKAGE.fullmatch(name):
            self.warning(
                "Nom de paquet invalide."
            )
            return

        self.selected_packages.add(name)
        self.manual_package.clear()

        self.refresh_selected_apps()
        self.refresh_target_packages()
        self.invalidate()

    def add_search_result(self, row, column):
        item = self.search_results.item(row, 0)

        if item:
            self.selected_packages.add(item.text())
            self.refresh_selected_apps()
            self.refresh_target_packages()
            self.invalidate()

    def remove_application(self, row, column):
        item = self.apps_table.item(row, 0)

        if item:
            self.selected_packages.discard(item.text())
            self.refresh_selected_apps()
            self.refresh_target_packages()
            self.invalidate()

    def search_applications(self):
        if self.uses_internet_catalog():
            self.search_internet()
            return

        env = self.project_environment()

        if not env:
            return

        query = self.search_text.text().strip()

        if not query or len(query) > 70:
            self.warning(
                "Recherche invalide."
            )
            return

        family = self.family_name
        revision = self.revision

        self.apps_log.setPlainText(
            "Recherche dans " + env + "..."
        )

        self.job(
            search_packages,
            (env, family, query),
            lambda data, error:
                self.search_done(
                    family,
                    revision,
                    data,
                    error
                )
        )

    def uses_internet_catalog(self):
        return (
            self.family_name in INTERNET_FAMILIES
            and self.associations.get(self.family_name, "") == INTERNET
        )

    def search_internet(self):
        query = self.search_text.text().strip()

        if not query or len(query) > 70:
            self.warning("Recherche invalide.")
            return

        family = self.family_name
        revision = self.revision

        self.apps_log.setPlainText(
            "Recherche sur Internet (" + family + ")..."
        )

        self.job(
            search_online,
            (family, self.release.currentText(), query),
            lambda data, error:
                self.search_done(family, revision, data, error)
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
            self.apps_log.setPlainText(error)
            return

        output, stderr, code = data

        rows = (
            output if isinstance(output, list)
            else parse_search(family, output)
        )

        self.fill(
            self.search_results,
            rows
        )

        self.apps_log.setPlainText(
            str(len(rows))
            + " résultats.\n"
            + "Code : " + str(code)
            + "\n"
            + (
                (stderr or output)[:2500]
                if code or not rows
                else "Double-clique pour ajouter un paquet."
            )
            + (
                "\n\nAucun paquet trouvé. Sur Fedora, certains logiciels "
                "(vlc, ffmpeg complet, codecs) ne sont pas dans les dépôts "
                "officiels mais dans RPM Fusion : active « Dépôts tiers "
                "Fedora » puis relance la recherche."
                if family == "Fedora" and not rows and not code
                else ""
            )
        )

    # --------------------------------------------------------
    # PAQUETS CIBLES
    # --------------------------------------------------------

    def target_packages(self):
        family = self.family_name

        packages = set(
            TARGET_BASE[family]
        )

        packages.update(
            desktop_packages(
                family,
                self.desktop.currentText(),
                self.vanilla_active()
            )
        )

        packages.update(
            AUDIO[family].get(
                self.audio.currentText(),
                []
            )
        )

        packages.update(
            self.selected_packages
        )

        for name, checkbox in self.flags.items():
            if checkbox.isChecked():
                packages.update(
                    EXTRAS[family].get(name, [])
                )

        if self.boot.currentText() == "GRUB":
            packages.update(
                GRUB_PACKAGES.get(family, {}).get(
                    self.boot_mode.currentText(),
                    []
                )
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

    def package_origin_map(self):
        family = self.family_name
        desktop = self.desktop.currentText()
        audio = self.audio.currentText()
        mode = self.boot_mode.currentText()

        options = {
            name: EXTRAS[family].get(name, [])
            for name, checkbox in self.flags.items()
            if checkbox.isChecked()
        }

        return package_origins(
            TARGET_BASE[family],
            desktop_packages(family, desktop, self.vanilla_active()),
            desktop,
            AUDIO[family].get(audio, []),
            audio,
            GRUB_PACKAGES.get(family, {}).get(mode, [])
            if self.boot.currentText() == "GRUB" else [],
            mode,
            options,
            self.selected_packages,
            (
                ["linux", "linux-lts", "linux-hardened"]
                if family == "Arch Linux" else []
            )
        )

    def refresh_target_packages(self):
        if not hasattr(self, "packages_table"):
            return

        origins = self.package_origin_map()

        self.fill(
            self.packages_table,
            [
                (package, origins.get(package, "Autre"))
                for package in self.target_packages()
            ]
        )

        self.refresh_verification_titles()

    def verification_env(self):
        return self.associations.get(self.family_name, "")

    def refresh_verification_titles(self):
        """Titres des blocs : toujours la famille et le gestionnaire,
        et « obsolète » si le résultat date d'un autre réglage."""

        if not hasattr(self, "checks_group"):
            return

        family = self.family_name
        manager = MANAGERS[family]
        env = self.verification_env()
        label = family + " " + self.release.currentText()

        self.context_label.setText(
            context_line(
                family,
                self.release.currentText(),
                manager,
                INSTALLERS[family],
                env
            )
        )

        stale = " — obsolète, à relancer" if self.results_stale else ""

        self.checks_group.setTitle(
            "1. Outils de préparation dans le WSL « "
            + (env or "non associé") + " »" + stale
            if self.checks_table.rowCount() else
            "1. Outils de préparation (non vérifiés)"
        )

        self.packages_group.setTitle(
            "2. Paquets cibles — " + label + " (" + manager + ")"
        )

        self.resolution_group.setTitle(
            "3. Résolution par " + manager + " (simulation)"
            + (
                " — " + self.results_family + stale
                if self.resolution_table.rowCount()
                and self.results_family else ""
            )
        )

        self.log_group.setTitle(
            "4. Sortie native de " + manager
        )

        counts = (
            self.checks_table.rowCount(),
            self.packages_table.rowCount(),
            self.resolution_table.rowCount()
        )

        for index, (name, count) in enumerate((
            ("Outils", counts[0]),
            ("Paquets cibles", counts[1]),
            ("Résolution", counts[2])
        )):
            self.verification_tabs.setTabText(
                index,
                name + (" (" + str(count) + ")" if count else "")
            )

        self.verification_tabs.setTabText(3, "Sortie " + manager)

    def clear_verification(self):
        """Évite de garder des résultats d'une autre distribution."""

        for table in (
            self.checks_table,
            self.resolution_table
        ):
            table.setRowCount(0)

        self.verification_log.clear()
        self.verification_status.setText(
            "Vérifications non effectuées"
        )
        self.results_family = ""
        self.results_stale = False
        self.refresh_verification_titles()

    # --------------------------------------------------------
    # VERIFICATION
    # --------------------------------------------------------

    def verify_project(self):
        env = self.project_environment()

        if not env:
            return

        revision = self.revision

        self.verification_status.setText(
            "Vérification en cours..."
        )

        self.job(
            verify_tools,
            (env,),
            lambda data, error:
                self.verify_done(
                    env,
                    revision,
                    data,
                    error
                )
        )

    def verify_done(
        self,
        env,
        revision,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.tools_ok = False
            self.verification_log.setPlainText(error)
            self.verification_status.setText(
                "Échec de vérification"
            )
            return

        family, metadata, rows = data

        self.fill(
            self.checks_table,
            rows
        )

        missing = [
            name
            for name, package, state in rows
            if state == "Absent"
        ]

        target = self.family_name
        release = self.release.currentText()

        issues = []

        if family != target:
            issues.append(
                "Famille WSL incompatible : " + family
            )

        actual_version = metadata.get(
            "VERSION_ID",
            ""
        )

        if target == "Debian":
            codename = metadata.get(
                "VERSION_CODENAME",
                ""
            )

            if release not in (
                actual_version,
                codename
            ):
                issues.append(
                    "Version Debian WSL différente "
                    "de la cible."
                )

        if target == "Fedora":
            if release != actual_version:
                issues.append(
                    "Version Fedora WSL différente "
                    "de la cible."
                )

        if missing:
            issues.append(
                "Outils absents : "
                + ", ".join(missing)
            )

        self.tools_ok = not issues
        self.verification_tabs.setCurrentIndex(0)
        self.results_stale = False
        self.refresh_verification_titles()

        subject = target + " " + release + " (WSL « " + env + " »)"

        if self.tools_ok:
            self.verification_status.setText(
                subject + " : outils de préparation présents"
            )
        else:
            self.verification_status.setText(
                subject + " : " + str(len(issues))
                + " problème(s) détecté(s)"
            )

        self.verification_log.setPlainText(
            "Distribution : " + target
            + "\nVersion : " + release
            + "\nWSL : " + env
            + "\nInstallateur prévu : "
            + INSTALLERS[target]
            + "\nGestionnaire cible : "
            + MANAGERS[target]
            + "\n\n"
            + (
                "\n".join(issues)
                if issues
                else "Aucun outil de construction manquant."
            )
            + "\n\n"
            "ATTENTION : cette vérification concerne "
            "l'environnement WSL.\n"
            "Elle ne valide pas l'installateur, "
            "les dépôts dans le système cible, "
            "ni le démarrage de l'ISO."
        )

    # --------------------------------------------------------
    # ANALYSE DES PAQUETS
    # --------------------------------------------------------

    def analyze_packages(self):
        env = self.project_environment()

        if not env:
            return

        revision = self.revision
        family = self.family_name

        packages = self.target_packages()

        self.refresh_target_packages()

        self.verification_log.setPlainText(
            "Simulation native en cours..."
        )

        self.job(
            simulate_packages,
            (env, family, packages),
            lambda data, error:
                self.analysis_done(
                    revision,
                    family,
                    data,
                    error
                )
        )

    def analysis_done(
        self,
        revision,
        family,
        data,
        error
    ):
        if revision != self.revision:
            return

        if error:
            self.analysis_ok = False
            self.verification_log.setPlainText(error)
            return

        output, stderr, code = data

        requested = set(self.target_packages())
        rows = parse_simulation(family, output, requested)
        self.fill(self.resolution_table, rows)
        self.verification_tabs.setCurrentIndex(2 if rows else 3)
        self.results_family = (
            family + " " + self.release.currentText()
        )
        self.results_stale = False
        self.refresh_verification_titles()

        # dnf5 --assumeno se termine par le code 1 après un calcul réussi :
        # le verdict regarde le contenu, pas seulement le code retour.
        self.analysis_ok, reason = simulation_verdict(
            family, output, stderr, code, rows
        )

        self.verification_log.setPlainText(
            "Famille : " + family
            + " (" + MANAGERS[family] + ")"
            + "\nPaquets lus dans la sortie : " + str(len(rows))
            + (
                ""
                if rows
                else " (format non reconnu : lis la sortie ci-dessous)"
            )
            + "\nCode retour : " + str(code)
            + "\nStatut : "
            + (
                "Simulation validée"
                if self.analysis_ok
                else "Résultat non validé"
            )
            + " (" + reason + ")"
            + "\n\n"
            + output
            + "\n"
            + stderr
            + "\n\n"
            "La simulation utilise les paquets déjà présents "
            "dans WSL et ne représente pas nécessairement "
            "les dépendances d'un système cible vierge."
        )

        if not self.analysis_ok:
            self.warning(
                "Analyse non validée : " + reason + ".\n"
                "Consulte la sortie native."
            )

    # --------------------------------------------------------
    # PROJET / ISO
    # --------------------------------------------------------

    def project_data(self):
        return {
            "application": "Universal Linux Builder",
            "version": VERSION,
            "family": self.family_name,
            "release": self.release.currentText(),
            "installer": INSTALLERS[self.family_name],
            "manager": MANAGERS[self.family_name],
            "wsl": self.associations.get(
                self.family_name,
                ""
            ),
            "desktop": self.desktop.currentText(),
            "kernel": self.kernel.currentText(),
            "init": self.init.currentText(),
            "display": self.display.currentText(),
            "audio": self.audio.currentText(),
            "bootloader": self.boot.currentText(),
            "boot_mode": self.boot_mode.currentText(),
            "profile": self.profile.currentText(),
            "build_options": self.build_options(),
            "options": {
                name: checkbox.isChecked()
                for name, checkbox in self.flags.items()
            },
            "packages": self.target_packages(),
            "live_installer_packages": LIVE_INSTALLER.get(
                self.family_name,
                []
            ),
            "install_chain": [
                {
                    "element": row[0],
                    "state": row[1],
                    "note": row[2]
                }
                for row in self.chain_rows()
            ],
            "tools_verified": self.tools_ok,
            "dependency_analysis_ok": self.analysis_ok,
            "boot_smoke_test": dict(self.boot_smoke),
            "boot_verified": False,
            "installer_verified": False,
            "ventoy_verified": False
        }

    def export_current_project(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier d'export"
        )

        if not folder:
            return

        try:
            destination = export_project(
                self.project_data(),
                folder
            )

        except Exception as exc:
            self.warning(str(exc))
            return

        self.iso_log.setPlainText(
            "Projet exporté dans :\n"
            + destination
            + "\n\n"
            "Fichiers :\n"
            "universal_linux_project.json\n"
            "packages.txt\n"
            "README.txt"
        )

        self.information(
            "Projet exporté."
        )

    def profile_note_refresh(self):
        light = self.profile.currentText() == "Léger"

        self.profile_note.setText(
            "Léger : bureau Xfce, ni impression ni Bluetooth "
            "par défaut (modifiables), et sous Debian "
            "construction sans paquets « recommandés ». "
            "Budgie, GNOME et KDE sont nettement plus lourds."
            if light
            else "Standard : choix du bureau et des options "
            "sans restriction."
        )

    def vanilla_active(self):
        return self.vanilla.isChecked() and vanilla_supported(
            self.family_name, self.desktop.currentText()
        )

    def refresh_vanilla(self, *_):
        family = self.family_name
        desktop = self.desktop.currentText()
        supported = vanilla_supported(family, desktop)

        self.vanilla.setEnabled(supported)
        self.vanilla.setToolTip(vanilla_note(family, desktop))
        self.vanilla_label.setText(
            "Bureau vanille actif — " + vanilla_note(family, desktop)
            if self.vanilla.isChecked() and supported
            else ""
        )
        self.vanilla_label.setVisible(bool(self.vanilla_label.text()))

    def vanilla_changed(self, *_):
        self.refresh_vanilla()
        self.invalidate()

        if hasattr(self, "packages_table"):
            self.refresh_target_packages()

    def profile_changed(self, name):
        light = name == "Léger"

        if light and not self.restoring:
            if "Xfce" in DESKTOPS[self.family_name]:
                self.desktop.setCurrentText(
                    LIGHT_PRESET["desktop"]
                )

            for option in LIGHT_PRESET["disabled_options"]:
                if option in self.flags:
                    self.flags[option].setChecked(False)

        self.profile_note_refresh()

        self.invalidate()

    def test_boot(self):
        family = self.family_name

        if family not in BUILD_FAMILIES:
            self.warning(
                "Test de démarrage disponible pour les familles "
                "dont l'ISO peut être construite."
            )
            return

        env = self.project_environment()

        if not env:
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir l'ISO à tester",
            self.last_iso,
            "Images ISO (*.iso)"
        )

        if not filename:
            return

        mode = self.smoke_mode.currentText()
        wait = int(self.smoke_wait.currentText().split()[0])

        if not self.confirm(
            "Démarrer l'ISO dans QEMU (" + mode + ") et "
            "capturer l'écran après " + str(wait) + " s ?\n\n"
            "QEMU et OVMF doivent être installés dans "
            + env
            + ". Sans accélération KVM, l'émulation est lente "
            "(augmente le délai)."
        ):
            return

        self.boot_preview.setPixmap(QPixmap())
        self.boot_preview.setText("Test en cours…")

        self.job(
            boot_test,
            (
                env,
                family,
                filename,
                mode,
                wait,
                str(Path(filename).parent)
            ),
            self.boot_done,
            self.iso_log
        )

    def boot_done(self, data, error):
        self.boot_preview.setText("Aucune capture")

        if error:
            self.iso_log.insertPlainText(
                "\n===== TEST DE DÉMARRAGE IMPOSSIBLE =====\n"
                + error
                + "\n"
            )
            self.warning(
                "Test de démarrage impossible.\n\n" + error[:600]
            )
            return

        pixmap = QPixmap(data["screenshot"])

        if not pixmap.isNull():
            self.boot_preview.setPixmap(
                pixmap.scaled(
                    self.boot_preview.width() - 8,
                    260,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

        self.boot_smoke[data["mode"]] = not data["blank"]

        self.iso_log.insertPlainText(
            "\n===== TEST DE DÉMARRAGE ("
            + data["mode"]
            + ") =====\n"
            + data["verdict"]
            + "\nCapture : " + data["screenshot"]
            + "\nPixels allumés : "
            + str(round(data["lit_ratio"] * 100, 1))
            + " %, couleurs : " + str(data["colors"])
            + "\n\nInstallateur et Ventoy : NON TESTÉS\n"
            + (
                "\nSortie série :\n" + data["serial_tail"] + "\n"
                if data["serial_tail"].strip()
                else ""
            )
        )

    def build_options(self):
        return {
            "light": self.profile.currentText() == "Léger",
            "firmware": (
                self.family_name == "Debian"
                and self.firmware_option.isChecked()
            ),
            "flathub": self.flags["Flathub"].isChecked(),
            "third_party": (
                self.family_name == "Fedora"
                and self.flags[FEDORA_THIRD_PARTY].isChecked()
            ),
            "cleanup": self.cleanup_option.isChecked(),
            "vanilla": self.vanilla_active(),
            "advanced": self.advanced_data(),
            "kernel_package": {
                "Stable": "linux",
                "LTS": "linux-lts",
                "Hardened": "linux-hardened"
            }.get(self.kernel.currentText(), "linux")
        }

    def create_iso(self):
        family = self.family_name

        if family in REMASTER_FAMILIES:
            self.remaster_clicked()
            return

        if family not in (
            "Debian",
            "Arch Linux",
            "Fedora"
        ):
            self.warning(
                "Construction ISO non implémentée "
                "pour " + family
            )
            return

        if not self.tools_ok:
            self.warning(
                "Vérifie d'abord les outils de construction."
            )

            self.tabs.setCurrentIndex(3)
            return

        if not self.analysis_ok:
            self.warning(
                "L'analyse des paquets doit être validée "
                "avant la construction."
            )

            self.tabs.setCurrentIndex(3)
            return

        env = self.project_environment()

        if not env:
            return

        problems = self.advanced_errors()

        if problems:
            self.warning(
                "Options avancées invalides :\n- " + "\n- ".join(problems)
            )
            self.tabs.setCurrentIndex(self.tab_index("Système"))
            return

        folder = self.output_folder()

        if not folder:
            return

        gaps = [
            row[0]
            for row in self.chain_rows()
            if row[1] in ("Absent", "Non implémenté")
        ]

        if not self.confirm(
            "Lancer la construction expérimentale "
            + family
            + " ?\n\n"
            + (
                "Éléments manquants dans la chaîne :\n- "
                + "\n- ".join(gaps)
                + "\n\n"
                if gaps
                else ""
            )
            + (
                "Fedora : livemedia-creator --no-virt exécute "
                "Anaconda directement dans l'environnement WSL. "
                "Utilise un WSL Fedora dédié, de la même version "
                "que la cible.\n\n"
                if family == "Fedora"
                else ""
            )
            + (
                "Fedora 44 et plus : Fedora ne publie plus de kickstarts "
                "pour ces versions (images construites avec kiwi). "
                "L'application se rabat sur la branche la plus récente "
                "disponible ; ce repli n'est pas validé et peut échouer.\n\n"
                if family == "Fedora"
                and self.release.currentText().isdigit()
                and int(self.release.currentText()) >= 44
                else ""
            )
            + (
                "Arch Linux : l'ISO sera un système live "
                "sans installateur graphique (Calamares n'est "
                "disponible que dans l'AUR).\n\n"
                if family == "Arch Linux"
                else ""
            )
            + (
                "Options avancées activées : générées mais jamais "
                "validées sur une vraie construction.\n\n"
                if self.advanced_data()["enabled"]
                else ""
            )
            + "Cette opération peut durer longtemps et "
            "nécessiter plusieurs Go d'espace.\n\n"
            "L'installation sur disque, BIOS/UEFI "
            "et Ventoy ne sont pas garantis."
        ):
            return

        history = self.config.get("build_history", {})

        self.build_family = family
        self.build_summary = None

        self.job(
            build_iso,
            (
                env,
                family,
                self.release.currentText(),
                self.iso_packages(),
                folder,
                self.desktop.currentText(),
                dict(
                    self.build_options(),
                    iso_name=self.out_name.text().strip(),
                    password=(
                        self.advanced_password()
                        if self.advanced_data()["enabled"]
                        else ""
                    )
                )
            ),
            self.build_done,
            self.iso_log,
            BuildProgress(
                family,
                history.get(family)
                if isinstance(history, dict)
                else None
            )
        )

    def build_done(self, data, error):
        if error:
            self.iso_log.insertPlainText(
                "\n===== ÉCHEC DE CONSTRUCTION =====\n"
                + error
                + "\n"
            )

            self.warning(
                "Construction échouée.\n"
                "Consulte le journal."
            )
            return

        files, report = data

        if self.build_summary:
            history = self.config.setdefault("build_history", {})

            if isinstance(history, dict):
                history[self.build_family] = self.build_summary

                try:
                    save_settings(self.config)

                except OSError:
                    pass

        if files:
            self.last_iso = files[0]["file"]
            self.vm_iso.setText(self.last_iso)

        self.iso_log.insertPlainText(
            "\n===== RÉSULTAT =====\n"
            + json.dumps(
                files,
                ensure_ascii=False,
                indent=2
            )
            + "\n\n"
            "Amorçage : NON TESTÉ\n"
            "Installateur : NON TESTÉ\n"
            "Ventoy : NON TESTÉ\n"
        )

        self.information(
            "Fichier ISO produit.\n\n"
            "Teste son démarrage et son installation "
            "dans une machine virtuelle avant "
            "de l'utiliser sur un PC."
        )
