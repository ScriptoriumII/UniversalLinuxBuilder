"""Sources d'ISO pour Gentoo et Slackware (pas de WSL requis).

Ces deux familles n'ont pas d'environnement WSL2 exploitable ici : au lieu
de construire, on part d'une ISO officielle que l'on télécharge (miroirs
officiels, vérification d'empreinte) ou que l'on importe depuis le disque.
Seule la bibliothèque standard est utilisée, côté Windows.
"""

import hashlib
import re
import urllib.request
from pathlib import Path

from .wsl import Control

USER_AGENT = "UniversalLinuxBuilder"

GENTOO_BASE = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"

# Adresses officielles connues ; elles n'ont pas pu être vérifiées depuis
# l'environnement de développement : le champ URL reste modifiable.
SOURCES = {
    "Gentoo": {
        "Installation minimale (amd64)": {
            "index": GENTOO_BASE + "latest-install-amd64-minimal.txt",
            "base": GENTOO_BASE
        },
        "Live GUI (amd64)": {
            "index": GENTOO_BASE + "latest-livegui-amd64.txt",
            "base": GENTOO_BASE
        }
    },
    "Slackware": {
        "Slackware64 15.0, DVD d'installation": {
            "url": "https://mirrors.slackware.com/slackware/"
                   "slackware-iso/slackware64-15.0-iso/"
                   "slackware64-15.0-install-dvd.iso"
        }
    }
}


class SourceError(Exception):
    pass


def open_url(url, timeout=60, headers=None):
    request = urllib.request.Request(
        url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {}))
    )

    return urllib.request.urlopen(request, timeout=timeout)


def fetch_text(url, opener=open_url):
    try:
        with opener(url) as response:
            return response.read().decode("utf-8", "replace")

    except OSError as exc:
        raise SourceError("Téléchargement impossible : " + url
                          + " (" + str(exc) + ")")


def parse_autobuild_index(text):
    """Lignes « chemin/relatif.iso taille » d'un fichier latest-*.txt
    (souvent signé PGP : les lignes d'armure sont ignorées)."""

    found = []

    for line in text.splitlines():
        line = line.strip()

        if not line or line.startswith(("#", "-----", "Hash:")):
            continue

        parts = line.split()

        if parts[0].lower().endswith(".iso"):
            found.append((parts[0], int(parts[1]) if len(parts) > 1
                          and parts[1].isdigit() else 0))

    return found


def resolve_source(family, variant, opener=open_url):
    """URL de l'ISO la plus récente pour la variante choisie."""

    entry = SOURCES.get(family, {}).get(variant)

    if not entry:
        raise SourceError("Source inconnue : " + family + " / " + variant)

    if "url" in entry:
        return entry["url"]

    isos = parse_autobuild_index(fetch_text(entry["index"], opener))

    if not isos:
        raise SourceError(
            "Aucune ISO dans l'index " + entry["index"]
            + " : saisis l'adresse de l'ISO à la main."
        )

    return entry["base"] + isos[0][0]


ALGORITHMS = {32: "md5", 64: "sha256", 128: "sha512"}


def parse_checksums(text, filename):
    """Empreintes d'un fichier dans .sha256 / .DIGESTS / .sha512.
    Retourne {algorithme: hex}, md5 ignoré."""

    result = {}
    name = Path(filename).name

    for line in text.splitlines():
        line = line.strip()

        # format BSD : SHA256 (nom) = hex
        bsd = re.match(r"^\w+\s*\((.+)\)\s*=\s*([0-9a-fA-F]+)$", line)

        if bsd and Path(bsd.group(1)).name == name:
            digest = bsd.group(2).lower()

        else:
            # format GNU : hex  nom   /   hex *nom
            gnu = re.match(r"^([0-9a-fA-F]{32,128})\s+\*?(.+)$", line)

            if not gnu or Path(gnu.group(2)).name != name:
                continue

            digest = gnu.group(1).lower()

        algorithm = ALGORITHMS.get(len(digest))

        if algorithm and algorithm != "md5":
            result.setdefault(algorithm, digest)

    return result


def checksum_urls(url):
    return [url + ".sha256", url + ".DIGESTS", url + ".sha512"]


def file_digest(path, algorithm, control=None):
    digest = hashlib.new(algorithm)

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            if control:
                control.check()

            digest.update(block)

    return digest.hexdigest()


def verify_download(path, url, opener=open_url, control=None):
    """Compare l'ISO à l'empreinte publiée par la source.

    Retourne (état, détail) ; état : OK, ÉCHEC ou NON VÉRIFIÉE."""

    expected = {}

    for candidate in checksum_urls(url):
        try:
            text = fetch_text(candidate, opener)

        except SourceError:
            continue

        expected = parse_checksums(text, url)

        if expected:
            break

    if not expected:
        return (
            "NON VÉRIFIÉE",
            "aucune empreinte publiée trouvée ; SHA256 calculé : "
            + file_digest(path, "sha256", control)
        )

    algorithm = "sha512" if "sha512" in expected else "sha256"
    actual = file_digest(path, algorithm, control)

    if actual == expected[algorithm]:
        return "OK", algorithm.upper() + " conforme à la source"

    return (
        "ÉCHEC",
        algorithm.upper() + " différent : attendu "
        + expected[algorithm] + ", obtenu " + actual
    )


def download(url, directory, control=None, opener=open_url):
    """Télécharge url dans directory (reprise possible) ; retourne le
    chemin du fichier. Le fichier n'est renommé qu'une fois complet."""

    control = control or Control()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    name = Path(url.split("?")[0]).name

    if not name.lower().endswith(".iso"):
        raise SourceError("L'adresse ne désigne pas un fichier .iso : " + url)

    target = directory / name
    part = directory / (name + ".part")

    if target.exists():
        control.log("Déjà présent : " + str(target))
        return target

    done = part.stat().st_size if part.exists() else 0
    headers = {"Range": "bytes=" + str(done) + "-"} if done else {}

    try:
        response = opener(url, headers=headers) if headers else opener(url)

    except OSError as exc:
        raise SourceError("Téléchargement impossible : " + str(exc))

    with response:
        status = getattr(response, "status", 200)
        length = int(response.headers.get("Content-Length") or 0)

        if done and status != 206:
            done = 0

        total = done + length if length else 0
        mode = "ab" if done else "wb"
        control.log("Téléchargement : " + url
                    + (" (reprise à %d Mo)" % (done // 2 ** 20) if done else ""))
        last = -1

        with part.open(mode) as handle:
            while True:
                control.check()
                block = response.read(1024 * 1024)

                if not block:
                    break

                handle.write(block)
                done += len(block)

                if total:
                    percent = int(done * 100 / total)

                    if percent != last:
                        control.progress(percent)
                        last = percent

    if total and part.stat().st_size != total:
        raise SourceError("Téléchargement incomplet : relance pour reprendre.")

    part.replace(target)
    return target


def inspect_iso(path):
    """Taille, signature ISO9660 et nom de volume (sans WSL)."""

    path = Path(path)

    if not path.is_file():
        raise SourceError("Fichier introuvable : " + str(path))

    with path.open("rb") as handle:
        handle.seek(32768)
        descriptor = handle.read(2048)

    valid = len(descriptor) >= 40 and descriptor[1:6] == b"CD001"
    label = descriptor[40:72].decode("ascii", "replace").strip() if valid else ""

    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "iso9660": valid,
        "label": label
    }


def import_iso(path):
    info = inspect_iso(path)

    if not info["iso9660"]:
        raise SourceError(
            "Ce fichier n'est pas une image ISO9660 valide : " + str(path)
        )

    return info


def fetch_iso(family, variant, url, directory, control=None, opener=open_url):
    """Téléchargement complet : résolution, copie, vérification."""

    control = control or Control()
    url = url or resolve_source(family, variant, opener)
    control.log("Source : " + url)
    target = download(url, directory, control, opener)
    control.progress(None)
    control.log("Vérification de l'empreinte...")
    state, detail = verify_download(target, url, opener, control)
    control.log("Empreinte : " + state + " — " + detail)

    if state == "ÉCHEC":
        raise SourceError("Empreinte incorrecte, ISO à ne pas utiliser. " + detail)

    info = import_iso(target)
    info.update(url=url, checksum=state, detail=detail)
    return info
