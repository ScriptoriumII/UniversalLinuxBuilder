import subprocess
import sys

from ulb import preflight
from ulb.preflight import ERROR, OK, WARN


def fake_run(table):
    def run(command, timeout=30):
        for key, value in table.items():
            if key in " ".join(command):
                return value
        return 0, ""
    return run


def test_parse_default_version_french_and_english():
    assert preflight.parse_default_version("Version par défaut : 2\n") == 2
    assert preflight.parse_default_version(
        "Default Version: 1\nKernel version: 5.15.1\n"
    ) == 1
    assert preflight.parse_default_version("rien") is None


def test_decode_utf16_output():
    assert preflight.decode("Debian\n".encode("utf-16-le")) == "Debian\n"


def test_python_too_old_is_blocking():
    assert preflight.check_python((3, 8, 10)).state == ERROR
    assert preflight.check_python((3, 12, 1)).state == OK


def test_missing_pyside_is_blocking_with_fix():
    check = preflight.check_pyside(lambda name: None)

    assert check.state == ERROR and "pip install" in check.fix


def test_wsl_checks_on_windows(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "wsl.exe")
    run = fake_run({
        "--status": (0, "Version par défaut : 2"),
        "-l -q": (0, "Debian\nArchLinux\n")
    })
    checks = preflight.check_wsl(run, "Windows")

    assert [c.state for c in checks] == [OK, OK]
    assert "Debian" in checks[1].detail


def test_wsl_without_distribution_and_wsl1(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "wsl.exe")
    run = fake_run({
        "--status": (0, "Default Version: 1"),
        "-l -q": (0, "")
    })
    checks = preflight.check_wsl(run, "Windows")

    assert [c.state for c in checks] == [WARN, WARN]
    assert "set-default-version 2" in checks[0].fix


def test_wsl_missing_is_blocking(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: None)

    assert preflight.check_wsl(fake_run({}), "Windows")[0].state == ERROR


def test_virtualization_states():
    on = fake_run({"powershell": (0, "True\nTrue\n")})
    off = fake_run({"powershell": (0, "False\nFalse\n")})

    assert preflight.check_virtualization(on, "Windows").state == OK
    assert preflight.check_virtualization(off, "Windows").state == WARN
    assert preflight.check_virtualization(on, "Linux") is None


def test_bootstrap_installs_missing_pyside_then_continues(monkeypatch):
    state = {"installed": False}

    def fake_pyside(find_spec=None):
        if state["installed"]:
            return preflight.Check("PySide6 (interface)", OK)
        return preflight.Check("PySide6 (interface)", ERROR, "non installé", "pip")

    commands = []

    def run(command, timeout=30):
        commands.append(command)
        if "-r" in command:
            state["installed"] = True
        return 0, ""

    monkeypatch.setattr(preflight, "check_pyside", fake_pyside)
    monkeypatch.setattr(preflight, "check_wsl", lambda *a: [])
    messages = []

    assert preflight.bootstrap([], run, messages.append) is None
    assert any("-r" in c for c in commands)


def test_bootstrap_no_install_blocks(monkeypatch):
    monkeypatch.setattr(
        preflight, "check_pyside",
        lambda *a: preflight.Check("PySide6 (interface)", ERROR, "non installé", "pip")
    )
    monkeypatch.setattr(preflight, "check_wsl", lambda *a: [])
    messages = []

    assert preflight.bootstrap(["--no-install"], lambda *a, **k: (0, ""), messages.append) == 1
    assert "ne peut pas démarrer" in "\n".join(messages)


def test_main_check_runs_without_gui():
    result = subprocess.run(
        [sys.executable, "main.py", "--check"],
        capture_output=True, text=True, timeout=60,
        cwd=str(preflight.ROOT)
    )

    assert "Python" in result.stdout and result.returncode == 0
