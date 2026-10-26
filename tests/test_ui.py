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
