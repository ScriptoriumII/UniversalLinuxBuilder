"""Recherche de paquets Gentoo et Slackware sur Internet (sans WSL).

Ces deux familles n'ont pas d'environnement WSL2 exploitable : le catalogue
est lu directement chez la source.
 - Slackware : PACKAGES.TXT du miroir officiel (liste complète des paquets
   de la version choisie, avec descriptions).
 - Gentoo : API JSON de Repology (dépôt « gentoo »).
Bibliothèque standard uniquement. Ces adresses et formats n'ont pas pu être
contrôlés depuis l'environnement de développement (réseau restreint) :
les analyseurs sont testés sur des échantillons conformes à la
documentation, pas sur les vraies réponses.
"""

import json
import re
import urllib.parse

from .sources import SourceError, fetch_text, open_url

INTERNET = "Dépôt internet (sans WSL)"
INTERNET_FAMILIES = ("Gentoo", "Slackware")

SLACKWARE_BASE = "https://mirrors.slackware.com/slackware/"
REPOLOGY_API = "https://repology.org/api/v1/projects/"

MAX_ROWS = 500

_cache = {}


def slackware_url(release):
    folder = "slackware64-current" if release == "current" \
        else "slackware64-" + release

    return SLACKWARE_BASE + folder + "/PACKAGES.TXT"


def repology_url(query):
    return REPOLOGY_API + "?" + urllib.parse.urlencode({
        "search": query,
        "inrepo": "gentoo"
    })


PACKAGE_FILE = re.compile(
    r"^(?P<name>.+)-(?P<version>[^-]+)-"
    r"(?P<arch>x86_64|noarch|i[3-6]86|arm)-(?P<build>[^-]+?)"
    r"\.t[xgb]z$"
)


def parse_packages_txt(text):
    """[(nom, version, description)] depuis un PACKAGES.TXT."""

    rows = []
    name = version = ""
    in_description = False

    for line in text.splitlines():
        if line.startswith("PACKAGE NAME:"):
            file = line.split(":", 1)[1].strip()
            match = PACKAGE_FILE.match(file)

            if match:
                name = match.group("name")
                version = match.group("version")

            else:
                name = version = ""

            in_description = False

        elif line.startswith("PACKAGE DESCRIPTION:"):
            in_description = True

        elif in_description and name:
            prefix = name + ":"

            if line.startswith(prefix):
                text_line = line[len(prefix):].strip()

                if text_line:
                    rows.append((name, version, text_line))
                    name = ""
                    in_description = False

    return rows


def words(query):
    return [word for word in query.lower().split() if word]


def search_slackware(release, query, opener=open_url):
    url = slackware_url(release)
    text = _cache.get(url)

    if text is None:
        text = fetch_text(url, opener)
        _cache[url] = text

    wanted = words(query)
    rows = [
        row for row in parse_packages_txt(text)
        if all(
            word in (row[0] + " " + row[2]).lower() for word in wanted
        )
    ]

    # Nom exact, puis nom commençant par la recherche, puis le reste.
    first = query.strip().lower()
    rows.sort(key=lambda row: (
        row[0].lower() != first,
        not row[0].lower().startswith(first),
        row[0].lower()
    ))

    return rows[:MAX_ROWS]


def parse_repology(text):
    """[(catégorie/paquet, version, résumé)] depuis la réponse JSON."""

    try:
        data = json.loads(text)

    except ValueError:
        raise SourceError("Réponse de Repology illisible.")

    if not isinstance(data, dict):
        raise SourceError("Réponse de Repology inattendue.")

    rows = []
    seen = set()

    for entries in data.values():
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            if not str(entry.get("repo", "")).startswith("gentoo"):
                continue

            name = (
                entry.get("srcname")
                or entry.get("visiblename")
                or ""
            )

            if not name or name in seen:
                continue

            seen.add(name)
            rows.append((
                name,
                str(entry.get("version", "?")),
                str(entry.get("summary", ""))
            ))

    rows.sort(key=lambda row: row[0])

    return rows


def search_gentoo(query, opener=open_url):
    text = fetch_text(repology_url(query), opener)

    return parse_repology(text)[:MAX_ROWS]


def search_online(family, release, query, opener=open_url):
    """Même retour que search_packages : (sortie, erreurs, code).
    La sortie est ici une liste de lignes (nom, version, description)."""

    if family == "Slackware":
        rows = search_slackware(release, query, opener)

    elif family == "Gentoo":
        rows = search_gentoo(query, opener)

    else:
        raise SourceError("Pas de catalogue Internet pour " + family)

    return rows, "", 0


def online_label(family):
    return family + " — dépôt internet (pas un WSL)"


def refresh_online(family, release, opener=open_url):
    """Actualise le catalogue Internet : Slackware retélécharge
    PACKAGES.TXT ; Gentoo sonde l'API Repology (interrogée en direct).
    Retourne (commande, (sortie, erreurs, code)) comme update_repositories."""

    if family == "Slackware":
        url = slackware_url(release)
        _cache.pop(url, None)
        text = fetch_text(url, opener)
        _cache[url] = text
        count = len(parse_packages_txt(text))

        if not count:
            raise SourceError(
                "PACKAGES.TXT téléchargé mais aucun paquet lu : " + url
            )

        return (
            "GET " + url,
            (
                "Catalogue Slackware " + release + " actualisé : "
                + str(count) + " paquets.",
                "", 0
            )
        )

    if family == "Gentoo":
        url = repology_url("gentoo-sources")
        rows = parse_repology(fetch_text(url, opener))

        if not rows:
            raise SourceError(
                "Repology répond mais sans paquet Gentoo : " + url
            )

        return (
            "GET " + url,
            (
                "Repology (dépôt gentoo) joignable ; interrogé en direct "
                "à chaque recherche, rien à télécharger.",
                "", 0
            )
        )

    raise SourceError("Pas de catalogue Internet pour " + family)
