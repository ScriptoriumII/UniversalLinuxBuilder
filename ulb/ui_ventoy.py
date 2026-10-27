"""Onglet Ventoy : clé USB bootable, copie d'ISO, persistance."""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSpinBox,
    QTextEdit,
    QVBoxLayout
)

from . import ventoy
from .ventoy import VentoyError


# Fonctions exécutées hors du thread de l'interface -----------------

def ventoy_fetch(control=None):
    version, executable = ventoy.fetch_ventoy(control)

    return version, str(executable)


def ventoy_list():
    return ventoy.list_usb_disks()


def ventoy_install(executable, args, disk, control=None):
    """Revérifie que le disque est toujours celui choisi avant d'écrire."""

    current = {
        item["number"]: item for item in ventoy.list_usb_disks()
    }
    found = current.get(disk["number"])

    if (
        not found
        or found["name"] != disk["name"]
        or found["size"] != disk["size"]
    ):
        raise VentoyError(
            "La clé a changé depuis la sélection : actualise la liste et "
            "recommence."
        )

    return ventoy.install_ventoy(
        executable, args, disk["number"], control
    )


def ventoy_copy(drive, isos, persistence, control=None):
    return ventoy.write_usb(drive, isos, persistence, control)


class VentoyMixin:

    def make_ventoy(self):
        layout = self.page("Ventoy")
        self.banner(layout)

        title = QLabel("Clé USB bootable (Ventoy)")
        self.role(title, "heading")
        layout.addWidget(title)

        self.ventoy_available = os.name == "nt"

        note = QLabel(
            "Prépare une clé USB avec Ventoy depuis Windows, copie tes "
            "ISO dessus et, pour Debian, crée la persistance. "
            "L'installation EFFACE la clé ; Windows demandera "
            "l'autorisation administrateur (UAC)."
            if self.ventoy_available else
            "Cet onglet fonctionne sous Windows (PowerShell et "
            "Ventoy2Disk.exe)."
        )
        note.setWordWrap(True)
        self.role(note, "muted")
        layout.addWidget(note)

        self.ventoy_executable = ""
        self.ventoy_disks = []

        # 1. Ventoy ---------------------------------------------------
        box = QGroupBox("1. Ventoy")
        row = QHBoxLayout(box)
        self.ventoy_version = QLabel("Version : non téléchargée")
        row.addWidget(self.ventoy_version, 1)
        self.ventoy_fetch_button = self.button(
            "Télécharger / mettre à jour Ventoy", self.ventoy_fetch_clicked
        )
        row.addWidget(self.ventoy_fetch_button)
        layout.addWidget(box)

        # 2. Clé USB --------------------------------------------------
        box = QGroupBox("2. Clé USB")
        form = QFormLayout(box)

        disks = QHBoxLayout()
        self.ventoy_disk = QComboBox()
        disks.addWidget(self.ventoy_disk, 1)
        self.ventoy_refresh_button = self.button(
            "Actualiser", self.ventoy_refresh_clicked
        )
        disks.addWidget(self.ventoy_refresh_button)
        form.addRow("Clé", disks)

        self.ventoy_action = QComboBox()
        self.ventoy_action.addItems([
            "Installer Ventoy (efface la clé)",
            "Mettre à jour Ventoy (garde les données)"
        ])
        self.ventoy_style = QComboBox()
        self.ventoy_style.addItems(ventoy.STYLES)
        self.ventoy_style.setCurrentText("GPT")
        self.ventoy_fs = QComboBox()
        self.ventoy_fs.addItems(ventoy.FILESYSTEMS)
        self.ventoy_reserve = QSpinBox()
        self.ventoy_reserve.setRange(0, 1048576)
        self.ventoy_reserve.setSingleStep(512)
        self.ventoy_reserve.setSuffix(" Mo")
        self.ventoy_secure = QCheckBox(
            "Prise en charge de Secure Boot (recommandé)"
        )
        self.ventoy_secure.setChecked(True)

        for label, widget in (
            ("Action", self.ventoy_action),
            ("Style de partition", self.ventoy_style),
            ("Système de fichiers des données", self.ventoy_fs),
            ("Espace réservé en fin de clé", self.ventoy_reserve)
        ):
            widget.setMaximumWidth(360)
            form.addRow(label, widget)

        form.addRow(self.ventoy_secure)

        self.ventoy_install_button = self.button(
            "Installer / mettre à jour Ventoy sur la clé",
            self.ventoy_install_clicked
        )
        form.addRow(self.ventoy_install_button)

        limits = QLabel(
            "Options non proposées : alignement 4 Ko et « Effacer "
            "Ventoy » (absents de la ligne de commande documentée), "
            "choix du nom de volume, disques non USB (volontairement "
            "refusés)."
        )
        limits.setWordWrap(True)
        self.role(limits, "muted")
        form.addRow(limits)
        layout.addWidget(box)

        # 3. ISO ------------------------------------------------------
        box = QGroupBox("3. ISO sur la clé")
        inner = QVBoxLayout(box)

        drive_row = QHBoxLayout()
        drive_row.addWidget(QLabel("Lecteur Ventoy"))
        self.ventoy_drive = QLineEdit()
        self.ventoy_drive.setPlaceholderText("ex. E:")
        self.ventoy_drive.setMaximumWidth(90)
        drive_row.addWidget(self.ventoy_drive)
        drive_row.addWidget(self.button(
            "Détecter", self.ventoy_detect_drive_clicked
        ))
        drive_row.addStretch()
        inner.addLayout(drive_row)

        self.ventoy_isos = QListWidget()
        self.ventoy_isos.setMaximumHeight(110)
        inner.addWidget(self.ventoy_isos)

        buttons = QHBoxLayout()
        buttons.addWidget(self.button("Ajouter une ISO…", self.ventoy_add_iso))
        buttons.addWidget(self.button(
            "Ajouter la dernière ISO construite", self.ventoy_add_last
        ))
        buttons.addWidget(self.button("Retirer", self.ventoy_remove_iso))
        buttons.addStretch()
        inner.addLayout(buttons)

        self.ventoy_persist_label = QLabel()
        self.ventoy_persist_label.setWordWrap(True)
        self.role(self.ventoy_persist_label, "muted")
        inner.addWidget(self.ventoy_persist_label)

        self.ventoy_persist_iso = QComboBox()
        self.ventoy_persist_iso.setMaximumWidth(520)
        inner.addWidget(self.ventoy_persist_iso)

        self.ventoy_copy_button = self.button(
            "Copier sur la clé", self.ventoy_copy_clicked
        )
        inner.addWidget(self.ventoy_copy_button)
        layout.addWidget(box)

        self.ventoy_log = QTextEdit()
        self.ventoy_log.setReadOnly(True)
        self.ventoy_log.document().setMaximumBlockCount(5000)
        layout.addWidget(self.ventoy_log, 1)

        self.ventoy_isos.model().rowsInserted.connect(
            self.ventoy_refresh_persistence
        )
        self.ventoy_isos.model().rowsRemoved.connect(
            self.ventoy_refresh_persistence
        )

        if not self.ventoy_available:
            for widget in (
                self.ventoy_fetch_button, self.ventoy_refresh_button,
                self.ventoy_install_button, self.ventoy_copy_button
            ):
                widget.setEnabled(False)

        self.ventoy_load_versions()
        self.ventoy_refresh_persistence()

    # --------------------------------------------------------

    def ventoy_say(self, text):
        self.ventoy_log.append(text)

    def ventoy_load_versions(self):
        try:
            versions = ventoy.installed_versions()

        except OSError:
            versions = []

        if versions:
            version = versions[-1]
            executable = ventoy.find_executable(
                ventoy.base_directory(), version
            )
            self.ventoy_executable = str(executable) if executable else ""
            self.ventoy_version.setText("Version : " + version)

    def ventoy_fetch_clicked(self):
        self.ventoy_log.clear()
        self.job(
            ventoy_fetch, (), self.ventoy_fetch_done, self.ventoy_log
        )

    def ventoy_fetch_done(self, data, error):
        if error:
            self.ventoy_say("ERREUR : " + error)
            self.warning("Ventoy : " + error)
            return

        version, executable = data
        self.ventoy_executable = executable
        self.ventoy_version.setText("Version : " + version)
        self.ventoy_say("Ventoy " + version + " prêt.")

    def ventoy_refresh_clicked(self):
        self.job(ventoy_list, (), self.ventoy_refresh_done)

    def ventoy_refresh_done(self, data, error):
        if error:
            self.ventoy_say("ERREUR : " + error)
            self.warning("Liste des clés impossible : " + error)
            return

        self.ventoy_disks = data
        self.ventoy_disk.clear()

        for disk in data:
            self.ventoy_disk.addItem(ventoy.disk_label(disk), disk["number"])

        self.ventoy_say(
            str(len(data)) + " clé(s) USB détectée(s). Les disques de "
            "démarrage et système sont toujours exclus."
        )

    def ventoy_selected_disk(self):
        number = self.ventoy_disk.currentData()

        return next(
            (d for d in self.ventoy_disks if d["number"] == number), None
        )

    def ventoy_install_clicked(self):
        disk = self.ventoy_selected_disk()

        if not self.ventoy_executable or not Path(
            self.ventoy_executable
        ).exists():
            self.warning("Télécharge d'abord Ventoy (bloc 1).")
            return

        if disk is None:
            self.warning("Actualise la liste et choisis une clé USB.")
            return

        update = self.ventoy_action.currentIndex() == 1

        try:
            args = ventoy.build_cli_args(
                "update" if update else "install",
                disk["number"],
                self.ventoy_style.currentText(),
                self.ventoy_secure.isChecked(),
                self.ventoy_reserve.value(),
                self.ventoy_fs.currentText()
            )

        except VentoyError as exc:
            self.warning(str(exc))
            return

        if not self.confirm(
            ("Mettre à jour Ventoy sur " if update
             else "INSTALLER Ventoy sur ")
            + ventoy.disk_label(disk) + " ?\n\n"
            + ("Les données sont conservées." if update
               else "TOUT LE CONTENU DE LA CLÉ SERA EFFACÉ.")
            + "\n\nVérifie que c'est bien la bonne clé."
        ):
            return

        self.ventoy_log.clear()
        self.job(
            ventoy_install,
            (self.ventoy_executable, args, disk),
            self.ventoy_install_done,
            self.ventoy_log
        )

    def ventoy_install_done(self, data, error):
        if error:
            self.ventoy_say("ERREUR : " + error)
            self.warning("Ventoy : " + error)
            return

        self.ventoy_drive.setText(data)
        self.information("Ventoy est installé sur " + data + ".")

    def ventoy_detect_drive_clicked(self):
        disk = self.ventoy_selected_disk()

        if disk is None:
            self.warning("Choisis d'abord une clé USB (bloc 2).")
            return

        self.job(
            ventoy.data_drive, (disk["number"],), self.ventoy_drive_done
        )

    def ventoy_drive_done(self, data, error):
        if error or not data:
            self.warning("Lecteur introuvable" + (" : " + error if error else "."))
            return

        self.ventoy_drive.setText(data)

    # --- ISO ----------------------------------------------------

    def ventoy_add_iso(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choisir des ISO", "", "ISO (*.iso);;Tous (*)"
        )

        for name in files:
            self.ventoy_isos.addItem(name)

    def ventoy_add_last(self):
        if not self.last_iso:
            self.warning("Aucune ISO construite dans cette session.")
            return

        self.ventoy_isos.addItem(self.last_iso)

    def ventoy_remove_iso(self):
        for item in self.ventoy_isos.selectedItems():
            self.ventoy_isos.takeItem(self.ventoy_isos.row(item))

    def ventoy_iso_paths(self):
        return [
            self.ventoy_isos.item(i).text()
            for i in range(self.ventoy_isos.count())
        ]

    def ventoy_refresh_persistence(self, *_):
        if not hasattr(self, "ventoy_persist_iso"):
            return

        adv = self.advanced_data() if hasattr(self, "adv_persistence") \
            else {"persistence": False, "enabled": False}
        wanted = adv["enabled"] and adv["persistence"]

        self.ventoy_persist_iso.clear()

        for path in self.ventoy_iso_paths():
            self.ventoy_persist_iso.addItem(Path(path).name, path)

        self.ventoy_persist_iso.setVisible(wanted)
        self.ventoy_persist_label.setText(
            "Persistance (Debian live) : activée dans Système > Avancé ("
            + str(adv.get("persistence_mb", 0)) + " Mo). Choisis l'ISO "
            "Debian concernée ; un WSL Debian associé est nécessaire."
            if wanted else
            "Persistance : non demandée (Système > Avancé, Debian "
            "seulement)."
        )

    def ventoy_copy_clicked(self):
        drive = self.ventoy_drive.text().strip().upper()
        isos = self.ventoy_iso_paths()

        if len(drive) != 2 or drive[1] != ":" or not drive[0].isalpha():
            self.warning("Indique la lettre du lecteur Ventoy (ex. E:).")
            return

        if not isos:
            self.warning("Ajoute au moins une ISO.")
            return

        missing = [p for p in isos if not Path(p).is_file()]

        if missing:
            self.warning("ISO introuvable :\n" + "\n".join(missing))
            return

        adv = self.advanced_data()
        persistence = None

        if adv["enabled"] and adv["persistence"]:
            env = self.associations.get("Debian", "")

            if self.environment_item(env) is None:
                self.warning(
                    "La persistance demande un WSL Debian associé "
                    "(onglet WSL2)."
                )
                return

            index = max(self.ventoy_persist_iso.currentIndex(), 0)
            persistence = (index, env, adv["persistence_mb"])

        self.ventoy_log.clear()
        self.job(
            ventoy_copy,
            (drive, isos, persistence),
            self.ventoy_copy_done,
            self.ventoy_log
        )

    def ventoy_copy_done(self, data, error):
        if error:
            self.ventoy_say("ERREUR : " + error)
            self.warning("Copie échouée : " + error)
            return

        self.ventoy_say("Terminé : " + ", ".join(data))
        self.information(
            "ISO copiée(s) sur la clé : " + ", ".join(data)
            + "\n\nDémarre le PC sur la clé (menu de démarrage), puis "
            "choisis l'ISO dans le menu Ventoy."
        )
