"""Présentation des paquets : origine de chaque paquet cible et lecture
de la sortie native de la simulation (dnf5, apt, pacman, emerge), pour
afficher des colonnes lisibles et propres à la famille choisie."""

import re

from .constants import MANAGERS

ROLE_REQUESTED = "Demandé"
ROLE_DEPENDENCY = "Dépendance"
ROLE_WEAK = "Dépendance faible"
ROLE_UPGRADE = "Mise à jour"


def human_size(count):
    count = float(count)

    for unit in ("o", "Kio", "Mio", "Gio"):
        if count < 1024 or unit == "Gio":
            return (
                format(count, ".0f") if unit == "o"
                else format(count, ".1f")
            ) + " " + unit

        count /= 1024


def package_origins(
    base,
    desktop_packages,
    desktop_name,
    audio_packages,
    audio_name,
    grub_packages,
    boot_mode,
    options,
    selected,
    kernel_packages=()
):
    """Étiquette d'origine de chaque paquet cible. Premier critère
    satisfait : un paquet n'a qu'une origine affichée.

    options : {nom d'option cochée: [paquets]}."""

    origins = {}

    def mark(names, label):
        for name in names:
            origins.setdefault(name, label)

    mark(kernel_packages, "Noyau")
    mark(base, "Système de base")
    mark(desktop_packages, "Bureau " + desktop_name)
    mark(audio_packages, "Audio " + audio_name)
    mark(grub_packages, "Chargeur GRUB (" + boot_mode + ")")

    for name, packages in options.items():
        mark(packages, "Option " + name)

    mark(selected, "Application choisie")

    return origins


def _dnf(output, requested):
    rows = []
    role = ROLE_REQUESTED
    pattern = re.compile(
        r"^\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+"
        r"(\d[\d.,]*\s*[KMG]?i?B)\s*$"
    )

    for line in output.splitlines():
        header = line.strip()

        if line and not line[0].isspace() and header.endswith(":"):
            lowered = header.lower()

            if "weak" in lowered:
                role = ROLE_WEAK
            elif "dependenc" in lowered:
                role = ROLE_DEPENDENCY
            elif "upgrad" in lowered:
                role = ROLE_UPGRADE
            elif "install" in lowered:
                role = ROLE_REQUESTED
            else:
                role = ""

            continue

        match = pattern.match(line)

        if match and role:
            name, arch, version, repo, size = match.groups()
            rows.append((name, version, repo, size, role))

    return rows


def _apt(output, requested):
    rows = []
    pattern = re.compile(
        r"^Inst\s+(\S+)\s+(?:\[[^\]]*\]\s+)?\((\S+)\s+([^\[)]*?)"
        r"(?:\s*\[[^\]]*\])?\)"
    )

    for line in output.splitlines():
        match = pattern.match(line)

        if match:
            name, version, repo = match.groups()
            rows.append((
                name, version, repo.strip(), "",
                ROLE_REQUESTED if name in requested else ROLE_DEPENDENCY
            ))

    return rows


def _pacman(output, requested):
    rows = []

    for line in output.splitlines():
        parts = line.strip().split("|")

        if len(parts) == 3 and parts[2].isdigit():
            name, version, size = parts
            rows.append((
                name, version, "", human_size(size),
                ROLE_REQUESTED if name in requested else ROLE_DEPENDENCY
            ))

    return rows


def _emerge(output, requested):
    rows = []
    pattern = re.compile(
        r"^\[ebuild[^\]]*\]\s*(\S+?)-(\d\S*?)(?::\S+)?::(\S+)"
        r"(?:.*?\s([\d,]+\s*\S+))?\s*$"
    )

    for line in output.splitlines():
        match = pattern.match(line.strip())

        if match:
            name, version, repo, size = match.groups()
            rows.append((
                name, version, repo, (size or "").strip(),
                ROLE_REQUESTED if name in requested else ROLE_DEPENDENCY
            ))

    return rows


PARSERS = {
    "Fedora": _dnf,
    "Debian": _apt,
    "Arch Linux": _pacman,
    "Gentoo": _emerge
}


def parse_simulation(family, output, requested=()):
    """Lignes (paquet, version, dépôt, taille, rôle) de la sortie native.
    Liste vide si le format n'est pas reconnu (la sortie brute reste
    affichée)."""

    parser = PARSERS.get(family)

    if parser is None:
        return []

    return parser(output, set(requested))


# Marqueurs d'échec de dnf5 (au début d'une ligne).
DNF_FAILURE = re.compile(
    r"^\s*(Failed to resolve|No match for argument|Problem|"
    r"Cannot find a package|Unable to find a match|"
    r"Error:|Failed to (?:load|download))",
    re.IGNORECASE | re.MULTILINE
)


def simulation_verdict(family, output, stderr, code, rows):
    """(valide, explication) pour la simulation d'installation.

    dnf5 --assumeno calcule la transaction puis répond « non » à la
    question de confirmation : il se termine alors avec le code 1
    (« Operation aborted by the user »). C'est un succès de simulation,
    pas une erreur ; l'échec réel se reconnaît à ses messages
    (Problem, Failed to resolve, No match for argument)."""

    text = output + "\n" + stderr

    if family == "Fedora":
        failure = DNF_FAILURE.search(text)

        if failure:
            line = text[failure.start():].strip().splitlines()[0]

            return False, "dnf5 signale : " + line[:160]

        summarized = (
            bool(rows)
            or "Transaction Summary" in output
            or "Nothing to do" in text
        )

        if code == 0 and summarized:
            return True, "transaction calculée"

        if code == 1 and summarized:
            return True, (
                "transaction calculée ; dnf5 s'arrête volontairement "
                "avant l'installation (--assumeno, code 1 normal)"
            )

        if code not in (0, 1):
            return False, "dnf5 a renvoyé le code " + str(code)

        return False, (
            "aucune transaction calculée (code " + str(code) + ")"
        )

    if code:
        return False, "code retour " + str(code)

    if family == "Debian" and re.search(r"^E: ", stderr, re.MULTILINE):
        return False, "apt signale une erreur (E:)"

    return True, "simulation terminée"


UPDATE_EFFECTS = {
    "Debian": "Met à jour l'index des paquets (apt-get update). "
              "Aucun paquet n'est mis à niveau.",
    "Fedora": "Rafraîchit les métadonnées des dépôts "
              "(dnf5 makecache --refresh). Aucun paquet n'est "
              "mis à niveau.",
    "Arch Linux": "Initialise le trousseau de clés puis effectue une "
                  "mise à niveau COMPLÈTE du système (pacman -Syu).",
    "Gentoo": "Synchronise l'arbre Portage (emerge --sync).",
    "Slackware": "Met à jour la liste des paquets (slackpkg update)."
}


def update_message(name, family):
    """Texte de confirmation propre à la famille de l'environnement."""

    return (
        "Actualiser les dépôts de " + name + " (" + family + ", "
        + MANAGERS.get(family, "gestionnaire inconnu") + ") ?\n\n"
        + UPDATE_EFFECTS.get(family, "")
    )


def context_line(family, release, manager, installer, env):
    """Ligne rappelant sur quelle distribution on travaille."""

    return (
        family + " " + release + "  ·  gestionnaire : " + manager
        + "  ·  installateur : " + installer
        + "  ·  WSL : " + (env or "non associé")
    )
