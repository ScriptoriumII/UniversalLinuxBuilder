"""Mise à jour depuis GitHub : détection d'une version plus récente et
application sans « git pull » manuel.

Deux méthodes d'application :
- dossier cloné (présence de .git et de git) : `git pull --ff-only`
  (échoue proprement s'il y a des modifications locales en conflit) ;
- sinon : archive ZIP de la branche principale, extraite dans le dossier
  de l'application (fichiers suivis seulement ; .venv n'est pas touché).

Un dépôt privé demande un jeton : variable d'environnement
ULB_GITHUB_TOKEN (jamais enregistré dans les réglages).
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "ScriptoriumII/UniversalLinuxBuilder"
BRANCH = "main"
RAW = "https://raw.githubusercontent.com/" + REPO + "/" + BRANCH + "/"
ZIP_URL = (
    "https://codeload.github.com/" + REPO + "/zip/refs/heads/" + BRANCH
)
PAGE = "https://github.com/" + REPO

VERSION_RE = re.compile(r'^VERSION\s*=\s*"([0-9]+(?:\.[0-9]+)*)"', re.M)
SECTION_RE = re.compile(r"^## ([0-9][0-9.]*)\s*$", re.M)


def parse_version(text):
    try:
        return tuple(int(part) for part in str(text).strip().split("."))

    except ValueError:
        return ()


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a) and bool(b) and a > b


def fetch(url, timeout=10, token=None):
    """Contenu binaire d'une URL ; lève RuntimeError avec un message clair."""

    headers = {"User-Agent": "UniversalLinuxBuilder-updater"}
    token = token if token is not None else os.environ.get("ULB_GITHUB_TOKEN")

    if token:
        headers["Authorization"] = "Bearer " + token

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(
                "Dépôt introuvable ou privé (HTTP 404). Pour un dépôt "
                "privé, définir la variable ULB_GITHUB_TOKEN."
            )

        raise RuntimeError("GitHub a répondu HTTP " + str(exc.code) + ".")

    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("GitHub injoignable : " + str(exc))


def release_notes(changelog, current):
    """Sections du journal plus récentes que la version actuelle."""

    marks = list(SECTION_RE.finditer(changelog))
    parts = []

    for index, mark in enumerate(marks):
        if not is_newer(mark.group(1), current):
            continue

        end = marks[index + 1].start() if index + 1 < len(marks) else len(
            changelog
        )
        parts.append(changelog[mark.start():end].strip())

    return "\n\n".join(parts)


def check_update(current, getter=fetch):
    """{"current", "latest", "newer", "notes"} ; lève RuntimeError."""

    text = getter(RAW + "ulb/constants.py").decode("utf-8", "replace")
    found = VERSION_RE.search(text)

    if not found:
        raise RuntimeError("Version distante illisible.")

    latest = found.group(1)
    newer = is_newer(latest, current)
    notes = ""

    if newer:
        try:
            notes = release_notes(
                getter(RAW + "CHANGELOG.md").decode("utf-8", "replace"),
                current
            )

        except RuntimeError:
            notes = ""

    return {
        "current": current, "latest": latest, "newer": newer, "notes": notes
    }


def app_directory():
    return Path(__file__).resolve().parent.parent


def git_executable():
    return shutil.which("git")


def run_hidden(command, cwd, timeout=180):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    return subprocess.run(
        command, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=flags
    )


def digest(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    except OSError:
        return ""


def extract_zip(archive, target):
    """Extrait l'archive GitHub (dossier racine unique) dans target.

    Refuse tout chemin qui sortirait du dossier. Retourne le nombre de
    fichiers écrits."""

    target = Path(target).resolve()
    count = 0

    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = Path(info.filename).parts[1:]

            if not parts or info.is_dir():
                continue

            if ".git" in parts:
                continue

            destination = target.joinpath(*parts).resolve()

            if target not in destination.parents:
                raise RuntimeError(
                    "Archive refusée : chemin suspect " + info.filename
                )

            destination.parent.mkdir(parents=True, exist_ok=True)

            with bundle.open(info) as source, open(destination, "wb") as out:
                shutil.copyfileobj(source, out)

            count += 1

    return count


def refresh_requirements(directory, before):
    """Réinstalle requirements.txt s'il a changé ; retourne une phrase."""

    requirements = Path(directory) / "requirements.txt"

    if digest(requirements) in ("", before):
        return ""

    try:
        result = run_hidden(
            [sys.executable, "-m", "pip", "install", "-r",
             str(requirements)],
            directory, 600
        )

    except (OSError, subprocess.TimeoutExpired) as exc:
        return "Dépendances à réinstaller à la main : " + str(exc)

    if result.returncode:
        return (
            "Dépendances à réinstaller à la main (pip a échoué) : "
            + (result.stderr or result.stdout)[-300:]
        )

    return "Dépendances mises à jour."


def apply_update(directory=None, getter=fetch, git=None):
    """Applique la mise à jour ; retourne (méthode, message)."""

    directory = Path(directory or app_directory())
    before = digest(directory / "requirements.txt")
    git = git if git is not None else git_executable()

    if (directory / ".git").exists() and git:
        try:
            result = run_hidden(
                [git, "pull", "--ff-only"], directory, 180
            )

        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("git pull impossible : " + str(exc))

        output = (result.stdout + result.stderr).strip()

        if result.returncode:
            raise RuntimeError(
                "git pull a échoué (modifications locales en conflit ou "
                "branche divergente ?) :\n" + output[-800:]
            )

        extra = refresh_requirements(directory, before)
        return "git", (output + ("\n" + extra if extra else "")).strip()

    data = getter(ZIP_URL, 120)
    fd, name = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    try:
        Path(name).write_bytes(data)

        try:
            count = extract_zip(name, directory)

        except zipfile.BadZipFile:
            raise RuntimeError("Archive GitHub invalide ou incomplète.")

    finally:
        try:
            os.unlink(name)

        except OSError:
            pass

    extra = refresh_requirements(directory, before)
    message = str(count) + " fichier(s) mis à jour depuis GitHub."
    return "zip", message + ("\n" + extra if extra else "")
