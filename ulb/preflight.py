"""Pré-contrôle et installation automatique avant l'ouverture de
l'interface (bibliothèque standard uniquement : PySide6 n'est pas encore
installé quand ce module s'exécute).

    py main.py --check     rapport complet, sans ouvrir l'interface
    py main.py --no-install   ne pas installer automatiquement PySide6
"""

import importlib.util
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)
MIN_FREE_GB = 20

OK, WARN, ERROR = "OK", "À corriger", "BLOQUANT"


class Check:
    def __init__(self, name, state, detail="", fix=""):
        self.name = name
        self.state = state
        self.detail = detail
        self.fix = fix

    def __repr__(self):
        return "Check(%r, %r)" % (self.name, self.state)


def default_run(command, timeout=30):
    """Exécute une commande ; retourne (code, sortie). Jamais d'exception."""

    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout
        )

    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)

    return result.returncode, decode(result.stdout + result.stderr)


def decode(data):
    """wsl.exe écrit en UTF-16 : on retire les octets nuls."""

    return data.replace(b"\x00", b"").decode("utf-8", "replace")


def parse_default_version(text):
    """Version WSL par défaut (« Default Version: 2 » / « Version par
    défaut : 2 »), None si introuvable."""

    for line in text.splitlines():
        if re.search(r"vers", line, re.I):
            found = re.search(r":\s*(\d)\s*$", line.strip())

            if found:
                return int(found.group(1))

    return None


def parse_distributions(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def check_python(version=None):
    version = version or sys.version_info[:3]
    wanted = ".".join(map(str, MIN_PYTHON))
    shown = ".".join(map(str, version))

    if tuple(version[:2]) >= MIN_PYTHON:
        return Check("Python", OK, shown)

    return Check(
        "Python",
        ERROR,
        shown + " : trop ancien (minimum " + wanted + ")",
        "Installe Python 3.12 : winget install -e --id Python.Python.3.12"
    )


def check_pyside(find_spec=importlib.util.find_spec):
    if find_spec("PySide6") is None:
        return Check(
            "PySide6 (interface)",
            ERROR,
            "non installé",
            "python -m pip install -r requirements.txt"
        )

    try:
        importlib.import_module("PySide6.QtWidgets")

    except ImportError as exc:
        return Check(
            "PySide6 (interface)",
            ERROR,
            "installé mais inutilisable : " + str(exc),
            "Installe « Microsoft Visual C++ Redistributable » "
            "(winget install -e --id Microsoft.VCRedist.2015+.x64) "
            "puis relance."
        )

    return Check("PySide6 (interface)", OK)


def check_assets(root=ROOT):
    logos = Path(root) / "ulb" / "assets" / "logos"

    if logos.is_dir() and any(logos.glob("*.svg")):
        return Check("Fichiers de l'application (logos)", OK)

    return Check(
        "Fichiers de l'application (logos)",
        WARN,
        "dossier ulb/assets/logos absent ou vide",
        "Récupère le dossier ulb complet : "
        "git fetch origin; git checkout origin/main -- main.py ulb"
    )


def check_disk(path=None, minimum=MIN_FREE_GB):
    path = path or Path.home()

    try:
        free = shutil.disk_usage(path).free / 1024 ** 3

    except OSError as exc:
        return Check("Espace disque", WARN, str(exc))

    detail = "%.0f Go libres" % free

    if free < minimum:
        return Check(
            "Espace disque",
            WARN,
            detail + " (une ISO demande 10 à 30 Go de travail)",
            "Libère de l'espace avant de construire une ISO."
        )

    return Check("Espace disque", OK, detail)


def check_wsl(run=default_run, system=None):
    """WSL2 : présent, version par défaut, au moins une distribution."""

    system = system or platform.system()

    if system != "Windows":
        return [Check(
            "WSL2", WARN,
            "système " + system + " : l'application est conçue pour Windows",
            "Lance-la sur Windows 10/11 avec WSL2."
        )]

    wsl = shutil.which("wsl.exe") or shutil.which("wsl")

    if not wsl:
        return [Check(
            "WSL2", ERROR, "wsl.exe introuvable",
            "PowerShell administrateur : wsl --install --no-distribution "
            "puis redémarre Windows."
        )]

    code, output = run([wsl, "--status"])
    checks = []

    if code != 0:
        checks.append(Check(
            "WSL2", ERROR,
            "wsl --status a échoué : " + output.strip()[:160],
            "PowerShell administrateur : wsl --install --no-distribution "
            "puis redémarre Windows."
        ))

    else:
        version = parse_default_version(output)

        if version == 1:
            checks.append(Check(
                "WSL2", WARN, "la version par défaut est 1",
                "wsl --set-default-version 2"
            ))

        else:
            checks.append(Check(
                "WSL2", OK,
                "version par défaut : "
                + (str(version) if version else "inconnue")
            ))

    code, output = run([wsl, "-l", "-q"])
    names = parse_distributions(output) if code == 0 else []

    if names:
        checks.append(Check(
            "Distributions WSL", OK, ", ".join(names)
        ))

    else:
        checks.append(Check(
            "Distributions WSL", WARN,
            "aucune distribution installée",
            "Onglet WSL2 de l'application (installer Debian, Fedora "
            "ou Arch) ou : wsl --install -d Debian"
        ))

    return checks


def check_virtualization(run=default_run, system=None):
    system = system or platform.system()

    if system != "Windows":
        return None

    code, output = run([
        "powershell.exe", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_ComputerSystem).HypervisorPresent; "
        "(Get-CimInstance Win32_Processor | Select-Object -First 1)"
        ".VirtualizationFirmwareEnabled"
    ], 45)

    values = [line.strip().lower() for line in output.splitlines() if line.strip()]

    if code != 0 or len(values) < 2:
        return Check(
            "Virtualisation (BIOS/UEFI)", WARN,
            "état non lisible", "Vérifie dans le Gestionnaire des tâches > Performances > UC."
        )

    hypervisor, firmware = values[-2], values[-1]

    if "true" in (hypervisor, firmware):
        return Check("Virtualisation (BIOS/UEFI)", OK, "activée")

    return Check(
        "Virtualisation (BIOS/UEFI)", WARN,
        "désactivée : WSL2 et QEMU/KVM ne fonctionneront pas",
        "Active Intel VT-x / AMD-V (SVM) dans le BIOS/UEFI."
    )


def check_all(run=default_run, system=None):
    checks = [check_python(), check_pyside(), check_assets()]
    checks += check_wsl(run, system)

    virtualization = check_virtualization(run, system)

    if virtualization:
        checks.append(virtualization)

    checks.append(check_disk())

    return checks


def report(checks):
    lines = []

    for check in checks:
        icon = {OK: "[OK]      ", WARN: "[A VOIR]  ", ERROR: "[BLOQUANT]"}[
            check.state
        ]

        lines.append(
            icon + " " + check.name
            + (" : " + check.detail if check.detail else "")
        )

        if check.state != OK and check.fix:
            lines.append("           -> " + check.fix)

    return "\n".join(lines)


def blocking(checks):
    return [c for c in checks if c.state == ERROR]


def pip_command(requirements=None):
    command = [sys.executable, "-m", "pip", "install", "-r",
               str(requirements or ROOT / "requirements.txt")]

    # hors environnement virtuel : installation pour l'utilisateur
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        command.insert(5, "--user")

    return command


def install_requirements(run=default_run, log=print):
    log("Installation de PySide6 (pip)...")

    code, output = run(
        [sys.executable, "-m", "ensurepip", "--upgrade"], 300
    )

    code, output = run(pip_command(), 900)

    if code:
        log("Échec de pip :\n" + output[-800:])
        return False

    importlib.invalidate_caches()
    return True


def bootstrap(argv, run=default_run, log=print):
    """Appelé par main.py avant l'import de l'interface.

    Retourne None pour continuer, ou un code de sortie."""

    only_check = "--check" in argv
    install = "--no-install" not in argv

    checks = check_all(run)

    if not only_check and install:
        wrong = [
            c for c in checks
            if c.name.startswith("PySide6") and c.state != OK
            and "non installé" in c.detail
        ]

        if wrong and install_requirements(run, log):
            checks = check_all(run)

    if only_check:
        log(report(checks))
        return 1 if blocking(checks) else 0

    problems = blocking(checks)

    if problems:
        log("\nL'application ne peut pas démarrer :\n" + report(problems))
        return 1

    attention = [
        c for c in checks if c.state == WARN
    ]

    if attention:
        log("Points à vérifier (l'application démarre quand même) :\n"
            + report(attention) + "\n")

    return None
