"""Fixtures : faux wsl.exe et faux outils de construction.

Les tests qui lancent des processus s'exécutent sous Linux/macOS ;
sous Windows ils sont ignorés (les scripts factices sont en sh).
"""

import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ulb.constants import BUILD_TOOLS  # noqa: E402

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="scripts factices en sh"
)


@pytest.fixture
def fake_wsl(tmp_path, monkeypatch):
    """PATH contenant un faux wsl.exe et des outils factices."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    for source in (ROOT / "tests" / "fakes").iterdir():
        target = bin_dir / source.name
        shutil.copy(source, target)
        target.chmod(target.stat().st_mode | stat.S_IEXEC)

    # Outils exigés par check_tools : présents mais sans effet.
    for tools in BUILD_TOOLS.values():
        for executable, _package in tools:
            stub = bin_dir / executable

            # xorriso : le vrai outil est utilisé quand il est installé
            # (les tests de remaster l'exécutent pour de bon).
            if executable == "xorriso" and shutil.which("xorriso"):
                continue

            if not stub.exists():
                stub.write_text("#!/bin/sh\nexit 0\n")
                stub.chmod(0o755)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))

    return bin_dir


@pytest.fixture
def workspaces():
    """Vérifie qu'aucun espace de travail ne traîne après le test."""

    before = set(Path("/var/tmp").glob("ulb-2*"))
    yield
    leftovers = set(Path("/var/tmp").glob("ulb-2*")) - before

    for path in leftovers:
        shutil.rmtree(path, ignore_errors=True)

    assert not leftovers, leftovers
