import os
import shutil
import subprocess

import pytest

from ulb.constants import FAMILIES
from ulb.environments import (
    MANAGER_CHECKS, manager_command, manager_report, parse_manager_probe
)

VERSIONS = {
    "apt-get": "apt 3.0.3 (amd64)",
    "apt-cache": "apt 3.0.3 (amd64)",
    "dnf5": "dnf5 version 5.2.17.0",
    "pacman": "Pacman v7.0.0 - libalpm v15.0.0",
    "emerge": "Portage 3.0.68 (python 3.12)",
    "slackpkg": ""
}


def run_probe(tmp_path, family, present):
    """Exécute vraiment la commande avec de faux gestionnaires."""

    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir()

    for tool in ("head", "sh"):
        (tmp_path / tool).symlink_to(shutil.which(tool))

    for name in present:
        script = tmp_path / name
        text = VERSIONS.get(name, "")
        script.write_text("#!/bin/sh\necho '" + text + "'\necho second\n")
        script.chmod(0o755)

    result = subprocess.run(
        ["/bin/sh", "-c", manager_command(family)],
        capture_output=True, text=True, env={"PATH": str(tmp_path)}
    )

    return result.stdout


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
@pytest.mark.parametrize("family", FAMILIES)
def test_manager_test_succeeds_on_every_family(tmp_path, family):
    names = [binary for binary, _ in MANAGER_CHECKS[family]]
    output = run_probe(tmp_path, family, names)

    ok, title, detail = manager_report("MonWSL", family, output)

    assert ok, detail
    assert title.startswith("Gestionnaire opérationnel")
    assert family in title and "MonWSL" in title

    for binary in names:
        assert "✔ " + binary in detail

    # Seule la première ligne de version est conservée.
    assert "second" not in detail

    version = VERSIONS[names[0]]

    if version:
        assert version in detail


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
@pytest.mark.parametrize("family", FAMILIES)
def test_manager_test_names_what_is_missing(tmp_path, family):
    output = run_probe(tmp_path, family, [])
    ok, title, detail = manager_report("MonWSL", family, output)

    assert not ok
    assert title.startswith("Gestionnaire incomplet")
    assert MANAGER_CHECKS[family][0][0] in title
    assert "Installer les outils" in detail


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_fedora_with_only_dnf4_gets_a_hint(tmp_path):
    output = run_probe(tmp_path, "Fedora", ["dnf"])
    ok, title, detail = manager_report("F", "Fedora", output)

    assert not ok and "dnf5" in title
    assert "dnf4 est présent" in detail

    rows, hint = parse_manager_probe("Fedora", output)
    assert rows[0][:2] == ("dnf5", False) and hint


@pytest.mark.skipif(os.name == "nt", reason="sh requis")
def test_debian_partial_install_is_reported(tmp_path):
    output = run_probe(tmp_path, "Debian", ["apt-get"])
    ok, title, detail = manager_report("D", "Debian", output)

    assert not ok and "apt-cache" in title
    assert "✔ apt-get" in detail and "✘ apt-cache" in detail


def test_wsl_error_is_shown():
    ok, title, detail = manager_report(
        "D", "Debian", "", "Le système ne trouve pas le fichier", 1
    )

    assert not ok and "code 1" in detail
    assert "Le système ne trouve pas" in detail
