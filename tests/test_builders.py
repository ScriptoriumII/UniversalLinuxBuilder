import hashlib
import os
import subprocess
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
def test_build_refuses_missing_destination(fake_wsl, tmp_path):
    with pytest.raises(RuntimeError, match="n'existe pas"):
        build_iso(
            "Debian", "Debian", "trixie", [], str(tmp_path / "absent")
        )


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
    assert "ANNULÉ" in next(destination.glob("build_report_*.txt")).read_text()
    assert not list(destination.glob("*.iso"))


@posix_only
def test_build_in_folder_with_existing_isos(fake_wsl, tmp_path, workspaces):
    from ulb.builders import build_iso

    destination = tmp_path / "isos"
    destination.mkdir()
    (destination / "autre.iso").write_bytes(b"ancienne")
    (destination / "SHA256SUMS").write_text("abc *autre.iso\n")

    for _ in range(2):
        files, report = build_iso(
            "Debian", "Debian", "trixie", ["x"],
            str(destination), "Xfce", {"cleanup": True}
        )

    assert (destination / "autre.iso").read_bytes() == b"ancienne"
    assert len(list(destination.glob("ULB_Debian_trixie_*.iso"))) == 2
    sums = (destination / "SHA256SUMS").read_text().splitlines()
    assert sums[0] == "abc *autre.iso" and len(sums) == 3
    assert len(list(destination.glob("build_report_*.txt"))) == 2


def syntax_ok(script):
    return subprocess.run(["sh", "-n", "-c", script]).returncode == 0


def run_clone(tmp_path, release, heads, fail=False, dumb=False):
    """Exécute la sélection de branche avec un faux git."""

    from ulb.builders import fedora_clone_command

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    git = bin_dir / "git"
    listing = "\n".join(
        "abc123\trefs/heads/" + name for name in heads
    )
    git.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = ls-remote ]; then\n'
        + ("  exit 128\n" if fail else "  printf '%s\\n' '" + listing + "'\n")
        + "  exit 0\nfi\n"
        + (
            'case "$*" in *--depth*) '
            'echo "fatal: dumb http transport does not support shallow '
            'capabilities" >&2; exit 128;; esac\n' if dumb else ""
        )
        + 'echo "CLONE $*"\n'
    )
    git.chmod(0o755)

    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])

    return subprocess.run(
        ["sh", "-c", "set -eu; " + fedora_clone_command(release)],
        capture_output=True, text=True, env=env
    )


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_fedora_clone_uses_exact_branch_when_present(tmp_path):
    result = run_clone(tmp_path, "43", ["f41", "f42", "f43", "main"])

    assert result.returncode == 0
    assert "--branch f43" in result.stdout
    assert "ATTENTION" not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_fedora_clone_falls_back_when_branch_missing(tmp_path):
    result = run_clone(tmp_path, "44", ["f41", "f42", "f43", "f9", "main"])

    assert result.returncode == 0
    assert "--branch f43" in result.stdout
    assert "la branche f44 n'existe pas" in result.stdout
    assert "kiwi" in result.stdout and "non validé" in result.stdout

    # Tri numérique : f9 n'est pas la « dernière » branche.
    assert "--branch f9 " not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_fedora_clone_explains_missing_and_network_errors(tmp_path):
    result = run_clone(tmp_path, "44", ["main"])
    assert result.returncode == 1
    assert "Aucune branche de kickstarts utilisable" in result.stderr

    result = run_clone(tmp_path, "44", [], fail=True)
    assert result.returncode == 1
    assert "réseau" in result.stderr


def test_fedora_script_embeds_clone_and_stays_valid_sh():
    script = fedora_script("/w", "44", ["a"], "Xfce", {})

    assert "git ls-remote --heads" in script
    assert "Remote branch" not in script
    assert syntax_ok(script)


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_fedora_clone_retries_without_depth_on_dumb_http(tmp_path):
    result = run_clone(tmp_path, "44", ["f43"], dumb=True)

    assert result.returncode == 0, result.stderr
    assert "Clone superficiel refusé" in result.stdout
    assert "CLONE clone --branch f43 https://pagure.io" in result.stdout
    assert "--depth" not in result.stdout.split("Clone superficiel")[1]

    # Serveur normal : un seul clonage superficiel.
    result = run_clone(tmp_path, "43", ["f43"])
    assert "Clone superficiel refusé" not in result.stdout
    assert "--depth 1 --branch f43" in result.stdout


@posix_only
def test_build_uses_custom_iso_name_without_overwriting(
    fake_wsl, tmp_path, workspaces
):
    destination = tmp_path / "out"
    destination.mkdir()
    options = {"cleanup": True, "iso_name": "ma distro"}

    for expected in ("ma distro.iso", "ma distro-2.iso"):
        files, _ = build_iso(
            "Debian", "Debian", "trixie", ["calamares"],
            str(destination), "Xfce", dict(options), Control()
        )
        assert Path(files[0]["file"]).name == expected
