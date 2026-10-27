"""Interface « ISO officielle » pour Gentoo et Slackware : télécharger ou
importer une ISO, puis la personnaliser (remaster) dans un WSL quelconque."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit
)

from .remaster import (
    REMASTER_FAMILIES,
    SLACKWARE_REMOVABLE,
    XORRISO_PACKAGES,
    clean_removals,
    install_xorriso_command,
    remaster_iso
)
from .settings import save_settings
from .sources import SOURCES, SourceError, fetch_iso, import_iso
from .wsl import execute


def install_xorriso(env, family, control=None):
    if family not in XORRISO_PACKAGES:
        raise RuntimeError(
            "Choisis un WSL Debian, Fedora ou Arch Linux pour xorriso."
        )

    return execute(
        env, install_xorriso_command(family), 1800,
        root=True, control=control
    )


class RemasterMixin:
    """Méthodes ajoutées à la fenêtre principale."""

    def default_download_dir(self):
        saved = self.config.get("remaster", {}).get("download_dir", "")

        return saved or str(Path.home() / "ULB" / "sources")

    def build_remaster_group(self, layout):
        box = QGroupBox("Source : ISO officielle (sans WSL dédié)")
        form = QFormLayout(box)
        self.remaster_box = box

        self.remaster_variant = QComboBox()
        self.remaster_variant.currentTextChanged.connect(
            self.remaster_variant_changed
        )
        self.remaster_url = QLineEdit()
        self.remaster_url.setPlaceholderText(
            "Adresse de l'ISO (vide = dernière version de la source)"
        )
        row = QHBoxLayout()
        row.addWidget(self.remaster_variant, 2)
        row.addWidget(self.remaster_url, 3)
        form.addRow("Version / adresse", row)

        self.remaster_dir = QLineEdit(self.default_download_dir())
        row = QHBoxLayout()
        row.addWidget(self.remaster_dir, 1)
        row.addWidget(self.button(
            "Parcourir…", lambda: self.pick_folder(self.remaster_dir)
        ))
        form.addRow("Dossier des sources", row)

        row = QHBoxLayout()
        row.addWidget(self.button(
            "Télécharger l'ISO officielle", self.remaster_fetch
        ))
        row.addWidget(self.button(
            "Importer une ISO…", self.remaster_import
        ))
        row.addStretch()
        form.addRow("", row)

        self.remaster_source = QLabel("Aucune ISO source choisie.")
        self.remaster_source.setWordWrap(True)
        form.addRow("ISO source", self.remaster_source)

        self.remaster_env = QComboBox()
        row = QHBoxLayout()
        row.addWidget(self.remaster_env, 1)
        row.addWidget(self.button(
            "Installer xorriso", self.remaster_install_xorriso
        ))
        form.addRow("WSL d'assemblage", row)

        self.remaster_overlay = QLineEdit()
        self.remaster_overlay.setPlaceholderText(
            "Dossier Windows dont le contenu est ajouté à la racine de l'ISO"
        )
        row = QHBoxLayout()
        row.addWidget(self.remaster_overlay, 1)
        row.addWidget(self.button(
            "Parcourir…", lambda: self.pick_folder(self.remaster_overlay)
        ))
        form.addRow("Fichiers à ajouter", row)

        self.remaster_remove = QLineEdit()
        self.remaster_remove.setPlaceholderText(
            "Séries à retirer, séparées par des espaces : "
            + " ".join(SLACKWARE_REMOVABLE)
        )
        self.remaster_remove_label = QLabel("Séries à retirer")
        form.addRow(self.remaster_remove_label, self.remaster_remove)

        self.remaster_sources_option = QCheckBox(
            "Retirer le dossier source/ (code source, gain de place)"
        )
        self.remaster_sources_option.setChecked(True)
        form.addRow("", self.remaster_sources_option)

        layout.addWidget(box)
        box.setVisible(False)

    def pick_folder(self, field):
        folder = QFileDialog.getExistingDirectory(
            self, "Choisir un dossier", field.text()
        )

        if folder:
            field.setText(folder)

    def remaster_active(self):
        return self.family_name in REMASTER_FAMILIES

    def refresh_remaster(self):
        """Appelé à chaque changement de famille ou d'inventaire WSL."""

        if not hasattr(self, "remaster_box"):
            return

        active = self.remaster_active()
        self.remaster_box.setVisible(active)
        self.build_options_box.setVisible(not active)
        self.iso_note.setVisible(not active)
        self.chain_table.setMinimumHeight(130 if active else 0)

        self.build_button.setText(
            "Créer l'ISO personnalisée"
            if active else "Créer l'ISO expérimentale"
        )

        slackware = self.family_name == "Slackware"
        self.remaster_remove.setVisible(slackware)
        self.remaster_remove_label.setVisible(slackware)
        self.remaster_sources_option.setVisible(slackware)

        if active:
            self.remaster_variant.blockSignals(True)
            self.remaster_variant.clear()
            self.remaster_variant.addItems(SOURCES[self.family_name])
            self.remaster_variant.blockSignals(False)

            self.iso_status.setText(
                "Remaster d'une ISO officielle " + self.family_name
                + " : pas de construction. Télécharge (empreinte "
                "vérifiée) ou importe l'ISO, choisis un WSL Debian, "
                "Fedora ou Arch (xorriso), puis crée l'ISO "
                "personnalisée ; l'amorçage BIOS/UEFI est repris de "
                "l'ISO d'origine."
            )

        current = self.remaster_env.currentText()
        self.remaster_env.clear()

        for item in self.inventory:
            if item["family"] in XORRISO_PACKAGES:
                self.remaster_env.addItem(item["name"])

        if current:
            self.remaster_env.setCurrentText(current)

    def remaster_variant_changed(self, _text):
        self.remaster_url.clear()

    def remaster_environment(self):
        name = self.remaster_env.currentText()

        if not name:
            self.warning(
                "Il faut un WSL Debian, Fedora ou Arch Linux pour "
                "assembler l'ISO (onglet WSL2). Gentoo et Slackware "
                "n'ont pas besoin de leur propre WSL."
            )
            return ""

        return name

    def remaster_iso_path(self):
        return self.config.get("remaster", {}).get("source_iso", "")

    def remember_remaster(self, **values):
        data = self.config.setdefault("remaster", {})

        if not isinstance(data, dict):
            data = self.config["remaster"] = {}

        data.update(values)

        try:
            save_settings(self.config)

        except OSError:
            pass

    def show_source(self, info):
        self.remaster_source.setText(
            info["path"] + "\n"
            + format(info["bytes"] / 1024 ** 3, ".2f") + " Go · volume « "
            + info["label"] + " » · "
            + info.get("checksum", "importée, empreinte non vérifiée")
        )

    def remaster_fetch(self):
        directory = self.remaster_dir.text().strip()

        if not directory:
            self.warning("Choisis un dossier pour les sources.")
            return

        self.remember_remaster(download_dir=directory)

        self.job(
            fetch_iso,
            (
                self.family_name,
                self.remaster_variant.currentText(),
                self.remaster_url.text().strip(),
                directory
            ),
            self.remaster_fetch_done,
            self.iso_log
        )

    def remaster_fetch_done(self, info, error):
        if error:
            self.iso_log.insertPlainText("\nERREUR : " + error + "\n")
            self.warning("Téléchargement impossible.\nConsulte le journal.")
            return

        self.remember_remaster(source_iso=info["path"])
        self.show_source(info)
        self.iso_log.insertPlainText(
            "\n===== ISO PRÊTE =====\n" + info["path"] + "\n"
        )

    def remaster_import(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir l'ISO officielle",
            self.remaster_iso_path() or self.default_download_dir(),
            "Images ISO (*.iso)"
        )

        if not filename:
            return

        try:
            info = import_iso(filename)

        except SourceError as exc:
            self.warning(str(exc))
            return

        self.remember_remaster(source_iso=info["path"])
        self.show_source(info)

    def remaster_install_xorriso(self):
        env = self.remaster_environment()

        if not env:
            return

        family = self.environment_family(env)

        if not self.confirm(
            "Installer xorriso dans " + env + " (" + family + ") ?"
        ):
            return

        self.job(
            install_xorriso,
            (env, family),
            lambda data, error: self.iso_log.insertPlainText(
                "\n" + ("ERREUR : " + error if error
                        else "xorriso installé.") + "\n"
            ),
            self.iso_log
        )

    def remaster_clicked(self):
        env = self.remaster_environment()

        if not env:
            return

        source = self.remaster_iso_path()

        if not source or not Path(source).is_file():
            self.warning(
                "Télécharge ou importe d'abord l'ISO officielle."
            )
            return

        remove = self.remaster_remove.text().split()

        try:
            clean_removals(self.family_name, remove)

        except ValueError as exc:
            self.warning(str(exc))
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination "
            "(il peut contenir d'autres fichiers)"
        )

        if not folder:
            return

        if not self.confirm(
            "Créer l'ISO " + self.family_name + " personnalisée ?\n\n"
            "Source : " + Path(source).name + "\n"
            "WSL : " + env + "\n\n"
            "Cette ISO est un remaster : l'amorçage est contrôlé à la "
            "création mais l'installation n'est PAS testée. Teste-la dans "
            "l'onglet Virtualisation."
        ):
            return

        self.build_family = self.family_name
        self.build_summary = None

        self.job(
            remaster_iso,
            (
                env,
                self.family_name,
                source,
                folder,
                {
                    "overlay": self.remaster_overlay.text().strip(),
                    "remove": remove,
                    "drop_sources": self.remaster_sources_option.isChecked()
                }
            ),
            self.build_done,
            self.iso_log
        )
