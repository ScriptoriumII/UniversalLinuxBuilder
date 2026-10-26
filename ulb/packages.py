import re
import shlex
from .constants import SAFE_PACKAGE
from .wsl import wsl


def search_packages(env, family, query):
    command = {
        "Debian": "apt-cache search",
        "Fedora": "dnf5 search",
        "Arch Linux": "pacman -Ss",
        "Gentoo": "emerge --search",
        "Slackware": "slackpkg search"
    }[family]

    return wsl(
        env,
        "LC_ALL=C "
        + command
        + " "
        + shlex.quote(query),
        300
    )


def parse_search(family, output):
    rows = []
    seen = set()

    for line in output.splitlines():
        line = line.strip()

        name = ""
        version = "?"
        description = ""

        if family == "Debian":
            match = re.match(
                r"^([\w+.-]+)\s+-\s+(.+)$",
                line
            )

            if match:
                name, description = match.groups()

        elif family == "Fedora":
            match = re.match(
                r"^([\w+.-]+)\."
                r"(?:x86_64|noarch|aarch64|i686|src)"
                r"\s*:\s*(.+)$",
                line
            )

            if match:
                name, description = match.groups()

        elif family == "Arch Linux":
            match = re.match(
                r"^[\w+.-]+/([^ ]+)\s+([^ ]+)",
                line
            )

            if match:
                name, version = match.groups()

        elif family == "Gentoo":
            match = re.search(
                r"\*\s+([\w+.-]+/[\w+.-]+)",
                line
            )

            if match:
                name = match.group(1)

        elif family == "Slackware":
            match = re.search(
                r"([\w+.-]+)-([0-9][\w.+-]*)-"
                r"(?:x86_64|noarch|i[3-6]86)",
                line
            )

            if match:
                name, version = match.groups()

        if (
            name
            and SAFE_PACKAGE.fullmatch(name)
            and name not in seen
        ):
            seen.add(name)
            rows.append((
                name,
                version,
                description[:180]
            ))

    return rows[:500]


def simulate_packages(env, family, packages):
    arguments = " ".join(
        shlex.quote(name)
        for name in packages
    )

    commands = {
        "Debian": (
            "LC_ALL=C apt-get -s install "
            + arguments
        ),
        "Fedora": (
            "LC_ALL=C dnf5 --assumeno install "
            + arguments
        ),
        "Arch Linux": (
            "LC_ALL=C pacman -Sp "
            '--print-format "%n|%v|%s" '
            + arguments
        ),
        "Gentoo": (
            "LC_ALL=C emerge --pretend --verbose --tree "
            + arguments
        )
    }

    if family == "Slackware":
        raise RuntimeError(
            "Slackware ne fournit pas de résolution native "
            "complète des dépendances avec slackpkg."
        )

    return wsl(
        env,
        commands[family],
        600
    )
