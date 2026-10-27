import json
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from conftest import posix_only


def pump(app, condition, limit=30):
    start = time.time()

    while not condition() and time.time() - start < limit:
        app.processEvents()
        time.sleep(0.02)


def make_window(fake_wsl, monkeypatch):
    from ulb.ui import UniversalLinuxBuilder

    app = QApplication.instance() or QApplication([])

    for name in ("warning", "information"):
        monkeypatch.setattr(
            QMessageBox, name, staticmethod(lambda *a, **k: None)
        )

    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )

    window = UniversalLinuxBuilder()
    window.show()
    pump(app, lambda: window.worker is None)

    return app, window


@posix_only
def test_startup_and_chain(fake_wsl, monkeypatch):
    app, window = make_window(fake_wsl, monkeypatch)

    window.change_family("Fedora")
    assert window.build_button.isEnabled()
    assert {"anaconda", "anaconda-live"} <= set(window.iso_packages())
    assert window.chain_table.rowCount() >= 4
    window.close()


@posix_only
def test_project_survives_restart(fake_wsl, monkeypatch, tmp_path):
    app, window = make_window(fake_wsl, monkeypatch)

    window.change_family("Arch Linux")
    window.desktop.setCurrentText("Xfce")
    window.kernel.setCurrentText("LTS")
    window.profile.setCurrentText("Léger")
    window.selected_packages.update({"firefox", "vlc"})
    window.close()

    saved = json.loads(
        (tmp_path / "UniversalLinuxBuilder" / "settings.json").read_text()
    )
    assert saved["project"]["family"] == "Arch Linux"

    app, again = make_window(fake_wsl, monkeypatch)
    assert again.family_name == "Arch Linux"
    assert again.desktop.currentText() == "Xfce"
    assert again.kernel.currentText() == "LTS"
    assert again.profile.currentText() == "Léger"
    assert sorted(again.selected_packages) == ["firefox", "vlc"]
    again.close()


@posix_only
def test_import_legacy_project(fake_wsl, monkeypatch):
    app, window = make_window(fake_wsl, monkeypatch)
    legacy = Path(__file__).resolve().parent.parent / "examples" / "distribution_legacy.json"

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(legacy), ""))
    )

    window.import_project()
    assert window.family_name == "Gentoo"
    assert window.flags["Wi-Fi"].isChecked()
    window.close()


@posix_only
def test_cancel_button_stops_build(fake_wsl, monkeypatch, tmp_path, workspaces):
    from ulb.builders import build_iso

    monkeypatch.setenv("FAKE_STEPS", "100")
    app, window = make_window(fake_wsl, monkeypatch)
    destination = tmp_path / "iso"
    destination.mkdir()
    callbacks = []

    window.job(
        build_iso,
        ("Debian", "Debian", "trixie", ["x"], str(destination), "Xfce", {}),
        lambda result, error: callbacks.append(error),
        window.iso_log
    )

    pump(app, lambda: "étape 3/" in window.iso_log.toPlainText(), 15)
    assert window.cancel_button.isVisible()

    window.cancel_job()
    pump(app, lambda: window.worker is None, 15)

    assert window.worker is None
    assert callbacks == []
    assert window.status.text() == "Opération annulée."
    window.close()


@posix_only
def test_build_shows_percentage_and_stores_history(
    fake_wsl, monkeypatch, tmp_path, workspaces
):
    from ulb.builders import build_iso
    from ulb.progress import BuildProgress

    monkeypatch.setenv("FAKE_REALISTIC", "1")
    monkeypatch.setenv("FAKE_STEPS", "1")
    monkeypatch.setenv("FAKE_DELAY", "0.15")
    app, window = make_window(fake_wsl, monkeypatch)
    destination = tmp_path / "iso"
    destination.mkdir()
    window.build_family = "Debian"
    seen = []

    window.job(
        build_iso,
        ("Debian", "Debian", "trixie", ["x"], str(destination), "Xfce", {}),
        window.build_done,
        window.iso_log,
        BuildProgress("Debian")
    )

    start = time.time()

    while window.worker is not None and time.time() - start < 60:
        app.processEvents()
        time.sleep(0.03)

        if window.build_tracker is not None:
            seen.append((window.progress.value(), window.progress.format()))

    values = [value for value, _ in seen]

    assert max(values) > 15
    assert values == sorted(values)
    assert any("%p%" in text for _, text in seen)
    assert window.build_summary and window.build_summary["total"] > 0
    assert "Debian" in window.config["build_history"]
    window.close()


@posix_only
def test_remaster_panel_for_gentoo_and_slackware(fake_wsl, monkeypatch, tmp_path):
    app, window = make_window(fake_wsl, monkeypatch)
    pump(app, lambda: window.worker is None and bool(window.inventory), 15)

    assert window.remaster_box.isHidden()
    assert not window.build_options_box.isHidden()

    window.change_family("Gentoo")
    assert not window.remaster_box.isHidden()
    assert window.build_options_box.isHidden()
    assert window.remaster_variant.count() >= 1
    assert window.build_button.text() == "Créer l'ISO personnalisée"
    assert window.remaster_remove.isHidden()
    assert window.remaster_env.count() >= 1  # WSL Debian/Arch, pas Gentoo

    rows = window.chain_rows()
    assert any(row[0].startswith("Amorçage") for row in rows)

    window.change_family("Slackware")
    assert not window.remaster_remove.isHidden()

    window.change_family("Debian")
    assert window.remaster_box.isHidden()
    window.close()


@posix_only
def test_remaster_from_the_ui(fake_wsl, monkeypatch, tmp_path, workspaces):
    import shutil

    import pytest

    if shutil.which("xorriso") is None:
        pytest.skip("xorriso absent")

    from test_remaster import listing, make_iso

    app, window = make_window(fake_wsl, monkeypatch)
    pump(app, lambda: window.worker is None and bool(window.inventory), 15)

    iso = make_iso(tmp_path, "gentoo", {"data.txt": "d"}, volid="GENTOO")
    destination = tmp_path / "sortie"
    destination.mkdir()
    window.change_family("Gentoo")
    window.remember_remaster(source_iso=str(iso))
    window.remaster_env.setCurrentText("Debian")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: str(destination))
    )

    window.create_iso()
    pump(app, lambda: window.worker is None, 60)
    app.processEvents()

    produced = list(destination.glob("ULB_Gentoo_*.iso"))
    assert len(produced) == 1
    assert "data.txt" in listing(produced[0])
    assert "RÉSULTAT" in window.iso_log.toPlainText()
    window.close()


@posix_only
def test_tool_tabs_are_last(fake_wsl, monkeypatch):
    app, window = make_window(fake_wsl, monkeypatch)
    names = [
        window.tabs.tabText(i) for i in range(window.tabs.count())
    ]

    assert names[-4:] == ["ISO", "Virtualisation", "Ventoy", "Configuration"]
    assert names[:5] == [
        "Distribution", "Système", "Applications", "Vérification", "ISO"
    ]


@posix_only
def test_fedora_third_party_option_only_for_fedora(fake_wsl, monkeypatch):
    from ulb.constants import FEDORA_THIRD_PARTY

    app, window = make_window(fake_wsl, monkeypatch)
    box = window.flags[FEDORA_THIRD_PARTY]

    for family in ("Debian", "Arch Linux", "Gentoo", "Slackware"):
        window.change_family(family)
        assert box.isHidden()

    window.change_family("Fedora")
    assert not box.isHidden()
    window.change_family("Debian")
    assert box.isHidden()


@posix_only
def test_internet_catalog_association(fake_wsl, monkeypatch):
    from ulb import ui as ui_module
    from ulb.catalog import INTERNET

    monkeypatch.setattr(
        ui_module, "search_online",
        lambda family, release, query: (
            [("vlc", "3.0", "player")], "", 0
        )
    )

    app, window = make_window(fake_wsl, monkeypatch)

    for family in ("Gentoo", "Slackware"):
        # Pas de WSL de cette famille : le catalogue Internet est choisi.
        assert window.associations[family] == INTERNET
        assert INTERNET in [
            window.mapping_boxes[family].itemText(i)
            for i in range(window.mapping_boxes[family].count())
        ]
        assert "Internet" in window.indicators[family].text()

    for family in ("Debian", "Fedora", "Arch Linux"):
        assert INTERNET not in [
            window.mapping_boxes[family].itemText(i)
            for i in range(window.mapping_boxes[family].count())
        ]

    window.change_family("Slackware")
    window.search_text.setText("vlc")
    window.search_applications()
    pump(app, lambda: window.worker is None)

    assert window.search_results.rowCount() == 1
    assert window.search_results.item(0, 0).text() == "vlc"


@posix_only
def test_advanced_group_and_ventoy_tab(fake_wsl, monkeypatch):
    from ulb.advanced import OFF

    app, window = make_window(fake_wsl, monkeypatch)

    names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert names.index("Ventoy") == names.index("Configuration") - 1
    assert window.tab_index("Configuration") == names.index("Configuration")

    # Avancé : décoché par défaut, rien n'est appliqué.
    data = window.advanced_data()
    assert data["enabled"] is False and "password" not in data
    assert window.build_options()["advanced"]["enabled"] is False
    assert window.adv_report.item(0, 1).text() == OFF
    assert window.advanced_body.isHidden()

    window.advanced_box.setChecked(True)
    assert not window.advanced_body.isHidden()
    window.adv_hostname.setText("poste")
    window.adv_password.setText("secret")
    assert window.advanced_data()["hostname"] == "poste"
    assert "password" not in window.build_options()["advanced"]
    assert "secret" not in json.dumps(window.project_data())

    # Dépôts tiers : visibles seulement sous Arch Linux.
    window.change_family("Debian")
    assert window.adv_arch_box.isHidden()
    window.change_family("Arch Linux")
    assert not window.adv_arch_box.isHidden()
    window.change_family("Fedora")
    assert window.adv_arch_box.isHidden()

    # Persistance : réservée à Debian.
    window.change_family("Debian")
    assert window.adv_persistence.isEnabled()
    window.change_family("Fedora")
    assert not window.adv_persistence.isEnabled()

    # Une saisie invalide bloque la construction.
    window.adv_hostname.setText("mauvais nom;")
    assert window.advanced_errors()

    # Réglages enregistrés dans la configuration, sans mot de passe.
    assert window.config["advanced"]["enabled"] is True
    assert "secret" not in json.dumps(window.config)

    # Ventoy : hors Windows, aucun bouton d'écriture.
    assert not window.ventoy_install_button.isEnabled()
    assert not window.ventoy_copy_button.isEnabled()


@posix_only
def test_configuration_tab_and_online_environment(fake_wsl, monkeypatch):
    from ulb import ui as ui_module
    from ulb.catalog import online_label

    app, window = make_window(fake_wsl, monkeypatch)
    names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "WSL2" not in names and names[-1] == "Configuration"

    # Plus de boutons Flathub / dépôts tiers dans la configuration.
    from PySide6.QtWidgets import QPushButton
    texts = [b.text() for b in window.findChildren(QPushButton)]
    assert "Ajouter Flathub" not in texts
    assert "Dépôts tiers Fedora" not in texts
    assert not hasattr(window, "add_flathub_clicked")

    def choices():
        return [
            window.wsl_choice.itemText(i)
            for i in range(window.wsl_choice.count())
        ]

    # Entrée « dépôt internet » : seulement pour Gentoo / Slackware.
    for family in ("Debian", "Fedora", "Arch Linux"):
        window.change_family(family)
        assert not any("internet" in c for c in choices())

    calls = []
    monkeypatch.setattr(
        ui_module, "refresh_online",
        lambda family, release: calls.append((family, release)) or (
            "GET x", ("ok", "", 0)
        )
    )

    for family in ("Gentoo", "Slackware"):
        window.change_family(family)
        assert online_label(family) in choices()
        assert online_label(
            "Slackware" if family == "Gentoo" else "Gentoo"
        ) not in choices()

        window.wsl_choice.setCurrentText(online_label(family))
        window.update_selected_repositories()
        pump(app, lambda: window.worker is None)

    assert [c[0] for c in calls] == ["Gentoo", "Slackware"]

    # L'actualisation de l'onglet Applications passe aussi par Internet.
    window.update_project_repositories()
    pump(app, lambda: window.worker is None)
    assert calls[-1][0] == "Slackware"


@posix_only
def test_manager_test_gives_precise_message(fake_wsl, monkeypatch):
    app, window = make_window(fake_wsl, monkeypatch)
    shown = []

    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, title, text, *a, **k: shown.append(text))
    )
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda parent, title, text, *a, **k: shown.append(text))
    )

    assert window.wsl_choice.count()
    window.wsl_choice.setCurrentIndex(0)
    window.test_selected_manager()
    pump(app, lambda: window.worker is None)

    assert len(shown) == 1
    assert shown[0].startswith(
        ("Gestionnaire opérationnel", "Gestionnaire incomplet")
    )
    assert "WSL «" in shown[0]
    log = window.wsl_log.toPlainText()
    assert log.startswith(("✔ ", "✘ ")) and "Commande :" in log


@posix_only
def test_fedora_analysis_validated_despite_assumeno_exit_code(
    fake_wsl, monkeypatch
):
    from test_package_view import DNF

    app, window = make_window(fake_wsl, monkeypatch)
    warnings = []

    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda parent, title, text, *a, **k: warnings.append(text))
    )

    window.change_family("Fedora")
    revision = window.revision

    # Cas réel : dnf5 --assumeno calcule puis s'arrête avec le code 1.
    window.analysis_done(
        revision, "Fedora",
        (DNF, "Operation aborted by the user.\n", 1), ""
    )
    assert window.analysis_ok is True and not warnings
    assert "Simulation validée" in window.verification_log.toPlainText()

    # Un vrai échec reste refusé et explique pourquoi.
    window.analysis_done(
        revision, "Fedora", ("", "No match for argument: zzz\n", 1), ""
    )
    assert window.analysis_ok is False
    assert warnings and "No match for argument" in warnings[0]


def test_vanilla_desktop_option(fake_wsl, monkeypatch):
    from ulb.vanilla import desktop_packages

    app, window = make_window(fake_wsl, monkeypatch)

    window.change_family("Debian")
    window.desktop.setCurrentText("GNOME")
    assert window.vanilla.isEnabled()
    assert not window.vanilla_active()
    assert "gnome-core" in window.target_packages()

    window.vanilla.setChecked(True)
    packages = window.target_packages()
    assert window.vanilla_active()
    assert "gnome-core" not in packages
    assert "gnome-shell" in packages
    assert window.build_options()["vanilla"] is True

    window.desktop.setCurrentText("Aucun")
    assert not window.vanilla.isEnabled()
    assert not window.vanilla_active()

    window.change_family("Gentoo")
    assert not window.vanilla.isEnabled()

    assert "gnome-core" in desktop_packages("Debian", "GNOME")
    assert "gnome-core" not in desktop_packages("Debian", "GNOME", True)
    assert desktop_packages("Debian", "Budgie", True) == (
        desktop_packages("Debian", "Budgie")
    )


def test_iso_destination_and_name(fake_wsl, monkeypatch, tmp_path):
    app, window = make_window(fake_wsl, monkeypatch)

    window.out_folder.setText(str(tmp_path))
    window.out_name.setText("ma-distro")

    assert window.output_folder() == str(tmp_path)
    assert "ma-distro.iso" in window.out_preview.text()
    assert window.config["output"]["name"] == "ma-distro"

    window.out_folder.setText(str(tmp_path / "absent"))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    assert window.output_folder() == ""

    window.out_folder.setText("")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )
    assert window.output_folder() == str(tmp_path)
