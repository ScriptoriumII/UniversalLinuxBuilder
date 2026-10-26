"""Lecture tolérante des fichiers de projet (pure logique, sans Qt)."""

import json

from .constants import FAMILIES

CHOICES = (
    "release", "desktop", "kernel", "init", "display",
    "audio", "bootloader", "boot_mode", "profile"
)

# Ancien format distribution.json (versions 0.x/1.x).
LEGACY_FLAGS = {
    "wifi": "Wi-Fi",
    "bluetooth": "Bluetooth",
    "printing": "Impression"
}

LEGACY_KEYS = {"boot": "bootloader"}


def read_project(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    return normalize_project(data)


def normalize_project(data):
    """Retourne {"family", "choices", "options", "packages",
    "build_options", "notes"} ou lève ValueError."""

    if not isinstance(data, dict):
        raise ValueError("Le fichier n'est pas un projet valide.")

    family = data.get("family") or data.get("distribution")

    if family not in FAMILIES:
        raise ValueError(
            "Famille inconnue ou absente : " + repr(family)
        )

    notes = []
    choices = {}

    # Format interne (« choices » imbriqué) ou export à plat.
    nested = data.get("choices")
    source = {**data, **nested} if isinstance(nested, dict) else data

    for key in CHOICES:
        if isinstance(source.get(key), str) and source[key]:
            choices[key] = source[key]

    for old, new in LEGACY_KEYS.items():
        if isinstance(data.get(old), str) and new not in choices:
            choices[new] = data[old]

    options = {}

    if isinstance(data.get("options"), dict):
        options = {
            str(name): bool(value)
            for name, value in data["options"].items()
        }

    for old, new in LEGACY_FLAGS.items():
        if old in data and new not in options:
            options[new] = bool(data[old])

    packages = []

    if isinstance(data.get("packages"), list):
        packages = [
            item for item in data["packages"]
            if isinstance(item, str)
        ]

    if data.get("applications") and not packages:
        notes.append(
            "Applications nommées sans paquet (ancien format) : "
            + ", ".join(map(str, data["applications"]))
            + " — à rechercher dans l'onglet Applications."
        )

    build_options = {}

    if isinstance(data.get("build_options"), dict):
        build_options = {
            str(name): bool(value)
            for name, value in data["build_options"].items()
        }

    return {
        "family": family,
        "choices": choices,
        "options": options,
        "packages": packages,
        "build_options": build_options,
        "notes": notes
    }
