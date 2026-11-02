"""Section « Mises à jour » de l'onglet Configuration et vérification au
démarrage. Ne passe pas par self.job : une vérification ne doit pas
bloquer ni être bloquée par une construction."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QHBoxLayout,
    QTextEdit
)

from .constants import VERSION
from .settings import save_settings
from .tasks import Task
from .updater import PAGE, apply_update, check_update


class UpdateMixin:

    def build_update_section(self, layout):
        self.update_info = None
        self.update_task = None

        self.update_status = QLabel(
            "Version installée : " + VERSION + ". Pas encore vérifiée."
        )
        self.update_status.setWordWrap(True)
        layout.addWidget(self.update_status)

        self.update_auto = QCheckBox(
            "Vérifier les nouvelles versions au démarrage"
        )
        self.update_auto.setChecked(
            bool(self.config.get("auto_update", True))
        )
        self.update_auto.toggled.connect(self.update_auto_changed)
        layout.addWidget(self.update_auto)

        row = QHBoxLayout()
        self.update_check_button = self.button(
            "Vérifier maintenant", self.update_check_clicked
        )
        self.update_apply_button = self.button(
            "Mettre à jour", self.update_apply_clicked
        )
        self.update_apply_button.setEnabled(False)
        row.addWidget(self.update_check_button)
        row.addWidget(self.update_apply_button)
        row.addWidget(self.button(
            "Ouvrir la page GitHub",
            lambda: QDesktopServices.openUrl(QUrl(PAGE))
        ))
        row.addStretch()
        layout.addLayout(row)

        self.update_notes = QTextEdit()
        self.update_notes.setReadOnly(True)
        self.update_notes.setPlaceholderText(
            "Les nouveautés de la version disponible s'affichent ici."
        )
        layout.addWidget(self.update_notes, 1)

    # --------------------------------------------------------

    def update_auto_changed(self, value):
        self.config["auto_update"] = bool(value)

        try:
            save_settings(self.config)

        except OSError:
            pass

    def run_update_task(self, function, args, callback):
        if self.update_task is not None:
            return False

        task = Task(function, *args)
        self.update_task = task

        def finished(result, error):
            self.update_task = None
            callback(result, error)

        task.done.connect(finished)
        task.finished.connect(task.deleteLater)
        task.start()
        return True

    def update_check_clicked(self):
        self.check_for_update(silent=False)

    def startup_update_check(self):
        """Appelé une fois par app.py, jamais par le constructeur."""

        if self.config.get("auto_update", True):
            self.check_for_update(silent=True)

    def check_for_update(self, silent):
        self.update_check_button.setEnabled(False)

        if not silent:
            self.update_status.setText("Vérification sur GitHub…")

        started = self.run_update_task(
            check_update, (VERSION,),
            lambda result, error: self.update_checked(
                result, error, silent
            )
        )

        if not started:
            self.update_check_button.setEnabled(True)

    def update_checked(self, info, error, silent):
        self.update_check_button.setEnabled(True)

        if error:
            if not silent:
                self.update_status.setText("Vérification impossible : " + error)

            return

        self.update_info = info
        self.update_notes.setPlainText(info["notes"])
        self.update_apply_button.setEnabled(info["newer"])

        if not info["newer"]:
            if not silent:
                self.update_status.setText(
                    "À jour : version " + VERSION + "."
                )

            return

        self.update_status.setText(
            "Nouvelle version disponible : " + info["latest"]
            + " (installée : " + VERSION + ")."
        )

        if silent and self.config.get("update_skipped") != info["latest"]:
            if self.confirm(
                "La version " + info["latest"] + " est disponible "
                "(installée : " + VERSION + ").\n\nMettre à jour maintenant ?"
            ):
                self.update_apply_clicked(confirmed=True)

            else:
                self.config["update_skipped"] = info["latest"]

                try:
                    save_settings(self.config)

                except OSError:
                    pass

    def update_apply_clicked(self, confirmed=False):
        if not self.update_info or not self.update_info["newer"]:
            return

        if self.worker is not None:
            self.warning(
                "Une opération est en cours : attends sa fin avant de "
                "mettre à jour."
            )
            return

        if confirmed is not True and not self.confirm(
            "Mettre à jour vers " + self.update_info["latest"] + " ?\n\n"
            "Les fichiers de l'application seront remplacés ; "
            "tes réglages et projets sont conservés. "
            "Il faudra relancer l'application ensuite."
        ):
            return

        self.update_apply_button.setEnabled(False)
        self.update_status.setText("Mise à jour en cours…")
        self.run_update_task(apply_update, (), self.update_applied)

    def update_applied(self, result, error):
        if error:
            self.update_apply_button.setEnabled(True)
            self.update_status.setText("Mise à jour échouée.")
            self.warning("Mise à jour échouée :\n" + error)
            return

        method, message = result
        self.update_status.setText(
            "Mise à jour installée (" + method + "). "
            "Ferme puis relance l'application pour l'utiliser."
        )
        self.update_notes.setPlainText(message)
        self.information(
            "Mise à jour installée.\n\nFerme puis relance l'application "
            "pour utiliser la nouvelle version."
        )
