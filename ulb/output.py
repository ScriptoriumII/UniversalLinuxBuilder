"""Destination et nom de l'ISO produite.

Le nom saisi est nettoyé (pas de dossier, pas de caractère interdit sous
Windows, extension .iso imposée). Un fichier existant n'est jamais écrasé :
le nom reçoit -2, -3… (voir builders.free_name).
"""

import re
from pathlib import Path

FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *("COM" + str(n) for n in range(1, 10)),
    *("LPT" + str(n) for n in range(1, 10))
}


def clean_iso_name(name):
    """Nom de fichier .iso sûr, ou '' si le champ est vide (nom automatique)."""

    name = (name or "").strip()

    if not name:
        return ""

    stem = name[:-4] if name.lower().endswith(".iso") else name
    stem = FORBIDDEN.sub("_", stem).strip(" .")

    if not stem:
        return ""

    if stem.split(".")[0].upper() in RESERVED:
        stem = "_" + stem

    return stem[:120] + ".iso"


def iso_file_name(custom, automatic, index=1, count=1):
    """Nom final : celui choisi (suffixé _N s'il y a plusieurs ISO) ou auto."""

    custom = clean_iso_name(custom)

    if not custom:
        return automatic

    if count > 1:
        stem = custom[:-4]
        return stem + "_" + str(index) + ".iso"

    return custom


def check_folder(folder):
    """Message d'erreur si le dossier est inutilisable, sinon ''."""

    if not folder:
        return "Aucun dossier de destination."

    path = Path(folder)

    if not path.is_dir():
        return "Le dossier n'existe pas : " + str(folder)

    return ""
