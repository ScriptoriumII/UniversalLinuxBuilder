"""Groupe « Avancé » de l'onglet Système : langue, clavier, fuseau,
utilisateur, persistance, chiffrement, système de fichiers, Secure Boot,
pilotes, miroir, dépôts tiers (Arch). Les réglages ne contiennent jamais le
mot de passe : il reste en mémoire le temps de la fenêtre."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget
)

from .advanced import (
    FILESYSTEMS,
    KEYBOARDS,
    LOCALES,
    TIMEZONES,
    advanced_report,
    normalize,
    validate
)
from .settings import save_settings


class AdvancedMixin:

    def build_advanced_group(self, layout):
        box = QGroupBox("Avancé")
        box.setCheckable(True)
        box.setChecked(False)
        self.advanced_box = box

        outer = QVBoxLayout(box)

        hint = QLabel(
            "Réglages appliqués à la construction (Debian, Fedora, "
            "Arch Linux). L'état réel de chaque option est détaillé "
            "plus bas, pour la famille choisie."
        )
        hint.setWordWrap(True)
        self.role(hint, "muted")
        outer.addWidget(hint)

        body = QWidget()
        self.advanced_body = body
        form = QFormLayout(body)
        form.setContentsMargins(0, 4, 0, 0)

        self.adv_locale = QComboBox()

        for label, code in LOCALES:
            self.adv_locale.addItem(label + "  —  " + code, code)

        self.adv_keyboard = QComboBox()

        for label, code, _ in KEYBOARDS:
            self.adv_keyboard.addItem(label + "  —  " + code, code)

        self.adv_timezone = QComboBox()
        self.adv_timezone.setEditable(True)
        self.adv_timezone.addItems(TIMEZONES)

        self.adv_hostname = QLineEdit()
        self.adv_hostname.setPlaceholderText("ex. poste-ulb (facultatif)")
        self.adv_username = QLineEdit()
        self.adv_username.setPlaceholderText(
            "ex. alice (facultatif ; Fedora garde « liveuser »)"
        )
        self.adv_password = QLineEdit()
        self.adv_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.adv_password.setPlaceholderText(
            "facultatif — jamais enregistré sur le disque"
        )

        for label, widget in (
            ("Langue (live et installé)", self.adv_locale),
            ("Clavier", self.adv_keyboard),
            ("Fuseau horaire", self.adv_timezone),
            ("Nom d'hôte", self.adv_hostname),
            ("Utilisateur du live", self.adv_username),
            ("Mot de passe du live", self.adv_password)
        ):
            widget.setMaximumWidth(520)
            form.addRow(label, widget)

        persistence = QHBoxLayout()
        self.adv_persistence = QCheckBox("Persistance sur la clé USB")
        self.adv_persistence_mb = QSpinBox()
        self.adv_persistence_mb.setRange(256, 262144)
        self.adv_persistence_mb.setSingleStep(512)
        self.adv_persistence_mb.setValue(4096)
        self.adv_persistence_mb.setSuffix(" Mo")
        persistence.addWidget(self.adv_persistence)
        persistence.addWidget(self.adv_persistence_mb)
        persistence.addStretch()
        form.addRow(persistence)

        self.adv_luks = QCheckBox("Chiffrement du disque (LUKS) à l'installation")
        form.addRow(self.adv_luks)

        self.adv_filesystem = QComboBox()
        self.adv_filesystem.addItems(FILESYSTEMS)
        self.adv_filesystem.setMaximumWidth(200)
        form.addRow("Système de fichiers installé", self.adv_filesystem)

        self.adv_snapshots = QCheckBox("Instantanés btrfs (snapper)")
        form.addRow(self.adv_snapshots)

        self.adv_secureboot = QCheckBox("Secure Boot (paquets signés : shim)")
        form.addRow(self.adv_secureboot)

        self.adv_proprietary = QCheckBox(
            "Pilotes propriétaires (NVIDIA) et codecs multimédia"
        )
        form.addRow(self.adv_proprietary)

        self.adv_mirror = QLineEdit()
        self.adv_mirror.setPlaceholderText(
            "https://miroir.exemple.org/… (facultatif)"
        )
        self.adv_proxy = QLineEdit()
        self.adv_proxy.setPlaceholderText(
            "http://proxy:3128 (facultatif)"
        )
        self.adv_mirror.setToolTip(
            "Debian : URL de l'archive (…/debian). Arch Linux : base "
            "avant /$repo/os/$arch. Fedora : baseurl du dépôt."
        )
        self.adv_proxy.setToolTip(
            "Debian : apt ; Fedora : livemedia-creator --proxy ; "
            "Arch Linux : variables http_proxy / https_proxy de pacman."
        )
        form.addRow("Miroir de dépôts", self.adv_mirror)
        form.addRow("Proxy", self.adv_proxy)

        outer.addWidget(body)

        # Dépôts tiers : Arch Linux seulement
        self.adv_arch_box = QGroupBox("Dépôts tiers (Arch Linux uniquement)")
        arch = QFormLayout(self.adv_arch_box)

        self.adv_aur = QCheckBox(
            "Compiler des paquets AUR (dépôt local, expérimental)"
        )
        self.adv_aur_packages = QLineEdit()
        self.adv_aur_packages.setPlaceholderText(
            "paquets AUR séparés par des espaces, ex. yay-bin paru"
        )
        self.adv_repos = QTextEdit()
        self.adv_repos.setFixedHeight(64)
        self.adv_repos.setPlaceholderText(
            "Un dépôt pacman par ligne : nom|https://hote/$repo/$arch|"
            "Optional TrustAll"
        )

        arch.addRow(self.adv_aur)
        arch.addRow("Paquets AUR", self.adv_aur_packages)
        arch.addRow("Dépôts pacman", self.adv_repos)
        outer.addWidget(self.adv_arch_box)

        self.adv_report = self.table(["Option", "État", "Détail"])
        self.adv_report.setFixedHeight(300)
        outer.addWidget(self.adv_report)

        layout.addWidget(box)

        # Restauration des réglages enregistrés
        saved = self.config.get("advanced", {})
        self.apply_advanced(saved if isinstance(saved, dict) else {})

        box.toggled.connect(self.advanced_changed)

        for widget in (
            self.adv_hostname, self.adv_username, self.adv_password,
            self.adv_mirror, self.adv_proxy, self.adv_aur_packages
        ):
            widget.textChanged.connect(self.advanced_changed)

        for widget in (
            self.adv_locale, self.adv_keyboard, self.adv_filesystem
        ):
            widget.currentIndexChanged.connect(self.advanced_changed)

        self.adv_timezone.currentTextChanged.connect(self.advanced_changed)
        self.adv_persistence_mb.valueChanged.connect(self.advanced_changed)
        self.adv_repos.textChanged.connect(self.advanced_changed)

        for widget in (
            self.adv_persistence, self.adv_luks, self.adv_snapshots,
            self.adv_secureboot, self.adv_proprietary, self.adv_aur
        ):
            widget.toggled.connect(self.advanced_changed)

        self.refresh_advanced()

    # --------------------------------------------------------

    def advanced_data(self):
        """Réglages saisis (sans le mot de passe), normalisés."""

        repos = [
            line.strip()
            for line in self.adv_repos.toPlainText().splitlines()
            if line.strip()
        ]

        return normalize({
            "enabled": self.advanced_box.isChecked(),
            "locale": self.adv_locale.currentData(),
            "keyboard": self.adv_keyboard.currentData(),
            "timezone": self.adv_timezone.currentText().strip(),
            "hostname": self.adv_hostname.text().strip(),
            "username": self.adv_username.text().strip(),
            "persistence": self.adv_persistence.isChecked(),
            "persistence_mb": self.adv_persistence_mb.value(),
            "luks": self.adv_luks.isChecked(),
            "filesystem": self.adv_filesystem.currentText(),
            "snapshots": self.adv_snapshots.isChecked(),
            "secureboot": self.adv_secureboot.isChecked(),
            "proprietary": self.adv_proprietary.isChecked(),
            "mirror": self.adv_mirror.text().strip(),
            "proxy": self.adv_proxy.text().strip(),
            "aur": self.adv_aur.isChecked(),
            "aur_packages": self.adv_aur_packages.text().split(),
            "repos": repos
        })

    def apply_advanced(self, data):
        adv = normalize(data)

        widgets = [
            self.advanced_box, self.adv_locale, self.adv_keyboard,
            self.adv_timezone, self.adv_hostname, self.adv_username,
            self.adv_persistence, self.adv_persistence_mb, self.adv_luks,
            self.adv_filesystem, self.adv_snapshots, self.adv_secureboot,
            self.adv_proprietary, self.adv_mirror, self.adv_proxy,
            self.adv_aur, self.adv_aur_packages, self.adv_repos
        ]

        for widget in widgets:
            widget.blockSignals(True)

        self.advanced_box.setChecked(adv["enabled"])

        index = self.adv_locale.findData(adv["locale"])
        self.adv_locale.setCurrentIndex(max(index, 0))
        index = self.adv_keyboard.findData(adv["keyboard"])
        self.adv_keyboard.setCurrentIndex(max(index, 0))
        self.adv_timezone.setCurrentText(adv["timezone"])
        self.adv_hostname.setText(adv["hostname"])
        self.adv_username.setText(adv["username"])
        self.adv_persistence.setChecked(adv["persistence"])
        self.adv_persistence_mb.setValue(
            min(max(adv["persistence_mb"], 256), 262144)
        )
        self.adv_luks.setChecked(adv["luks"])
        self.adv_filesystem.setCurrentText(adv["filesystem"])
        self.adv_snapshots.setChecked(adv["snapshots"])
        self.adv_secureboot.setChecked(adv["secureboot"])
        self.adv_proprietary.setChecked(adv["proprietary"])
        self.adv_mirror.setText(adv["mirror"])
        self.adv_proxy.setText(adv["proxy"])
        self.adv_aur.setChecked(adv["aur"])
        self.adv_aur_packages.setText(" ".join(adv["aur_packages"]))
        self.adv_repos.setPlainText("\n".join(adv["repos"]))

        for widget in widgets:
            widget.blockSignals(False)

    def advanced_password(self):
        return self.adv_password.text()

    def advanced_errors(self):
        return validate(
            self.family_name, self.advanced_data(), self.advanced_password()
        )

    def advanced_changed(self, *_):
        self.refresh_advanced()

        if getattr(self, "restoring", False):
            return

        self.config["advanced"] = self.advanced_data()

        try:
            save_settings(self.config)

        except OSError:
            pass

        if hasattr(self, "ventoy_refresh_persistence"):
            self.ventoy_refresh_persistence()

    def refresh_advanced(self):
        family = self.family_name
        adv = self.advanced_data()
        enabled = adv["enabled"]

        self.advanced_body.setVisible(enabled)
        self.adv_arch_box.setVisible(enabled and family == "Arch Linux")
        self.adv_persistence.setEnabled(family == "Debian")
        self.adv_persistence_mb.setEnabled(family == "Debian")
        self.adv_snapshots.setEnabled(
            self.adv_filesystem.currentText() == "btrfs"
        )
        self.adv_report.setVisible(enabled)

        self.fill(self.adv_report, advanced_report(family, adv))
        self.adv_report.resizeColumnToContents(0)
        self.adv_report.resizeColumnToContents(1)
