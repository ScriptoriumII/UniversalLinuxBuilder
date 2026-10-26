import re
import shlex
from .constants import BUILD_TOOLS, MANAGER_BINARY
from .wsl import execute, run, stream, wsl


def wsl_names():
    output, error, code = run(
        ["wsl.exe", "--list", "--quiet"],
        60
    )

    if code:
        raise RuntimeError(
            error or output or "Impossible de lire la liste WSL2"
        )

    return list(dict.fromkeys(
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ))


def online_catalog():
    output, error, code = run(
        ["wsl.exe", "--list", "--online"],
        90
    )

    if code:
        raise RuntimeError(error or output)

    rows = []

    for line in output.splitlines():
        match = re.match(
            r"^\s*([A-Za-z0-9][\w.-]*)\s{2,}(.+?)\s*$",
            line
        )

        if match:
            name, description = match.groups()

            if name.lower() not in ("name", "nom"):
                rows.append((name, description))

    return rows, output


def detect_distribution(env):
    output, error, code = wsl(
        env,
        "cat /etc/os-release",
        45
    )

    if code:
        return {
            "name": env,
            "family": "Inconnue",
            "version": "",
            "codename": "",
            "metadata": {},
            "error": error or output
        }

    metadata = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            metadata[key] = value.strip().strip('"').strip("'")

    identifiers = (
        metadata.get("ID", "")
        + " "
        + metadata.get("ID_LIKE", "")
    ).lower().split()

    mapping = {
        "debian": "Debian",
        "fedora": "Fedora",
        "arch": "Arch Linux",
        "archlinux": "Arch Linux",
        "gentoo": "Gentoo",
        "slackware": "Slackware"
    }

    family = next(
        (
            mapping[identifier]
            for identifier in identifiers
            if identifier in mapping
        ),
        "Inconnue"
    )

    return {
        "name": env,
        "family": family,
        "version": metadata.get("VERSION_ID", ""),
        "codename": metadata.get("VERSION_CODENAME", ""),
        "metadata": metadata,
        "error": ""
    }


def detect_all(names):
    return [
        detect_distribution(name)
        for name in names
    ]


def detect_family(env):
    info = detect_distribution(env)

    if info["error"]:
        raise RuntimeError(info["error"])

    return info["family"], info["metadata"]


def best_match(family, release, inventory):
    candidates = [
        item
        for item in inventory
        if item["family"] == family
    ]

    if not candidates:
        return ""

    candidates.sort(
        key=lambda item: (
            release not in (
                item["version"],
                item["codename"]
            ),
            item["name"].casefold()
        )
    )

    return candidates[0]["name"]


def check_tools(env, family):
    if family not in BUILD_TOOLS:
        raise RuntimeError(
            "Famille WSL non prise en charge : " + family
        )

    commands = []

    for executable, package in BUILD_TOOLS[family]:
        if executable.startswith("rpm:"):
            # « a|b » : plusieurs noms de paquet possibles
            # (fedora-kickstarts s'appelle spin-kickstarts sur
            # certaines versions).
            test = " || ".join(
                "rpm -q --quiet " + shlex.quote(name)
                for name in executable[4:].split("|")
            )

        else:
            test = (
                "command -v "
                + shlex.quote(executable)
                + " >/dev/null 2>&1"
            )

        commands.append(
            "if "
            + test
            + "; then echo "
            + shlex.quote(executable + ":OK")
            + "; else echo "
            + shlex.quote(executable + ":ABSENT")
            + "; fi"
        )

    output, error, code = wsl(
        env,
        "; ".join(commands),
        120
    )

    if code:
        raise RuntimeError(error or output)

    states = {}

    for line in output.splitlines():
        if ":" in line:
            name, state = line.rsplit(":", 1)
            states[name] = state.strip() == "OK"

    return [
        (
            executable,
            package,
            "Présent" if states.get(executable) else "Absent"
        )
        for executable, package in BUILD_TOOLS[family]
    ]


def verify_tools(env):
    family, metadata = detect_family(env)

    return family, metadata, check_tools(env, family)


def test_manager(env, family):
    command = (
        "command -v "
        + shlex.quote(MANAGER_BINARY[family])
    )

    return command, wsl(env, command, 60)


# Un WSL Arch fraîchement installé n'a pas de trousseau de clés :
# sans ceci, pacman échoue avec « keyring is not writable ».
ARCH_KEYRING = (
    "pacman-key --init && pacman-key --populate archlinux && "
)


def update_repositories(env, family, control=None):
    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update"
        ),
        "Fedora": "dnf5 makecache --refresh",
        "Arch Linux": ARCH_KEYRING + "pacman -Syu --noconfirm",
        "Gentoo": "emerge --sync",
        "Slackware": "slackpkg update"
    }

    command = commands[family]

    return command, execute(
        env,
        command,
        3600,
        root=True,
        control=control
    )


def fedora_install_command(missing):
    """Installe les paquets manquants ; le paquet des kickstarts est
    résolu par le fichier qu'il fournit, car son nom varie
    (fedora-kickstarts / spin-kickstarts)."""

    others = " ".join(
        shlex.quote(name)
        for name in missing
        if name != "fedora-kickstarts"
    )

    if "fedora-kickstarts" not in missing:
        return "dnf5 -y install " + others

    return (
        "ks=$(dnf5 repoquery -q --whatprovides "
        "'*/fedora-live-base.ks' 2>/dev/null "
        "| sed 's/-[0-9].*//' | sort -u | head -n 1); "
        'ks=${ks:-spin-kickstarts}; '
        'echo "Paquet des kickstarts : $ks"; '
        'dnf5 -y install "$ks" ' + others
    )


def install_tools(env, family, control=None):
    if family not in (
        "Debian",
        "Fedora",
        "Arch Linux"
    ):
        raise RuntimeError(
            "Installation automatique des outils non validée "
            "pour cette famille. "
            "Utilise son gestionnaire natif manuellement."
        )

    rows = check_tools(env, family)

    missing = sorted({
        package
        for executable, package, state in rows
        if state == "Absent"
    })

    if not missing:
        return "Aucun outil manquant", ("", "", 0)

    arguments = " ".join(
        shlex.quote(package)
        for package in missing
    )

    commands = {
        "Debian": (
            "DEBIAN_FRONTEND=noninteractive apt-get update && "
            "DEBIAN_FRONTEND=noninteractive "
            "apt-get install -y --no-install-recommends "
            + arguments
        ),
        "Fedora": fedora_install_command(missing),
        "Arch Linux": (
            ARCH_KEYRING
            + "pacman -Syu --noconfirm --needed "
            + arguments
        )
    }

    command = commands[family]

    return command, execute(
        env,
        command,
        3600,
        root=True,
        control=control
    )


def install_distribution(name, control):
    output, code = stream(
        [
            "wsl.exe",
            "--install",
            "--distribution",
            name,
            "--no-launch"
        ],
        control,
        1800
    )

    return output, "", code
