import hashlib
import threading
import time
from pathlib import Path

import pytest

from conftest import posix_only
from ulb.builders import arch_script, build_iso, debian_script, fedora_script
from ulb.wsl import Cancelled, Control


def test_debian_script_options():
    light = debian_script(
        "/var/tmp/x", "trixie", ["a", "b"],
        {"light": True, "firmware": True}
    )
    assert "--apt-recommends false" in light
    assert "non-free-firmware" in light
    assert "firmware-linux" in light

    plain = debian_script("/var/tmp/x", "trixie", ["a"], {})
    assert "apt-recommends" not in plain
    assert "--archive-areas main;" in plain


def test_debian_script_quotes_packages():
    script = debian_script("/var/tmp/x", "trixie", ["a;b", "c d"], {})
    assert "'a;b'" in script and "'c d'" in script


def test_fedora_script_requires_numeric_release():
    with pytest.raises(RuntimeError):
        fedora_script("/var/tmp/x", "rawhide; rm -rf /", [], "Xfce")

    script = fedora_script("/var/tmp/x", "43", ["anaconda"], "Xfce")
    assert "fedora-live-xfce.ks" in script
    assert "--no-virt" in script
    assert "anaconda" in script


def test_arch_script_uses_releng_profile():
    script = arch_script("/var/tmp/x", ["base", "linux"])
    assert "releng" in script and "mkarchiso" in script


@posix_only
def test_build_success(fake_wsl, tmp_path, workspaces):
    lines, progress = [], []
    control = Control(log=lines.append, progress=progress.append)
    destination = tmp_path / "out"
    destination.mkdir()

    files, report = build_iso(
        "Debian", "Debian", "trixie", ["calamares"],
        str(destination), "Xfce",
        {"firmware": True, "cleanup": True}, control
    )

    iso = Path(files[0]["file"])
    assert files[0]["iso9660"] is True
    assert hashlib.sha256(iso.read_bytes()).hexdigest() == files[0]["sha256"]
    assert (destination / "SHA256SUMS").read_text().startswith(files[0]["sha256"])
    assert "SUCCÈS" in report and "supprimé" in report
    assert any("étape 3/5" in line for line in lines)
    assert progress[0] is None and progress[-1] == 100


@posix_only
def test_build_refuses_non_empty_destination(fake_wsl, tmp_path):
    (tmp_path / "x").write_text("x")

    with pytest.raises(RuntimeError, match="vide"):
        build_iso("Debian", "Debian", "trixie", [], str(tmp_path))


@posix_only
def test_build_cancel(fake_wsl, tmp_path, monkeypatch, workspaces):
    monkeypatch.setenv("FAKE_STEPS", "100")
    lines = []
    control = Control(log=lines.append)
    destination = tmp_path / "out"
    destination.mkdir()

    def stopper():
        while not any("étape 3/" in line for line in lines):
            time.sleep(0.05)

        control.cancel()

    threading.Thread(target=stopper, daemon=True).start()
    start = time.time()

    with pytest.raises(Cancelled):
        build_iso(
            "Debian", "Debian", "trixie", ["x"],
            str(destination), "Xfce", {}, control
        )

    assert time.time() - start < 15
    assert "ANNULÉ" in (destination / "build_report.txt").read_text()
    assert not list(destination.glob("*.iso"))
