import io
import json

import pytest

from ulb import catalog
from ulb.sources import SourceError

PACKAGES = """PACKAGES.TXT;  Tue Oct 27 2026

PACKAGE NAME:  mozilla-firefox-140.3.0esr-x86_64-1_slack15.0.txz
PACKAGE MIRROR:  http://mirror/
PACKAGE LOCATION:  ./patches/packages
PACKAGE SIZE (compressed):  60000 K
PACKAGE DESCRIPTION:
mozilla-firefox: Mozilla Firefox web browser
mozilla-firefox:
mozilla-firefox: Firefox is a fast browser.

PACKAGE NAME:  vlc-3.0.21-x86_64-1.txz
PACKAGE LOCATION:  ./extra
PACKAGE DESCRIPTION:
vlc: vlc (media player)
vlc:
vlc: VLC plays everything.

PACKAGE NAME:  aaa_base-15.0-x86_64-2.txz
PACKAGE DESCRIPTION:
aaa_base: aaa_base (Slackware base system)
"""

REPOLOGY = json.dumps({
    "firefox": [
        {"repo": "gentoo", "srcname": "www-client/firefox",
         "version": "140.3.0", "summary": "Firefox Web Browser"},
        {"repo": "gentoo_overlay", "visiblename": "www-client/firefox-bin",
         "version": "140.3.0"},
        {"repo": "debian_13", "srcname": "firefox-esr", "version": "1"}
    ],
    "vlc": [
        {"repo": "gentoo", "srcname": "media-video/vlc",
         "version": "3.0.21", "summary": "Media player"}
    ]
})


def opener_for(body, urls):
    def opener(url, *a, **k):
        urls.append(url)
        return io.BytesIO(body.encode())

    return opener


def test_parse_packages_txt():
    rows = catalog.parse_packages_txt(PACKAGES)

    assert rows == [
        ("mozilla-firefox", "140.3.0esr", "Mozilla Firefox web browser"),
        ("vlc", "3.0.21", "vlc (media player)"),
        ("aaa_base", "15.0", "aaa_base (Slackware base system)")
    ]


def test_slackware_search_and_url():
    catalog._cache.clear()
    urls = []
    rows, err, code = catalog.search_online(
        "Slackware", "15.0", "firefox", opener_for(PACKAGES, urls)
    )

    assert [r[0] for r in rows] == ["mozilla-firefox"]
    assert code == 0
    assert urls == [
        "https://mirrors.slackware.com/slackware/slackware64-15.0/"
        "PACKAGES.TXT"
    ]
    assert "slackware64-current" in catalog.slackware_url("current")

    # Deuxième recherche : le catalogue est en cache (pas de téléchargement).
    rows, _, _ = catalog.search_online(
        "Slackware", "15.0", "media player", opener_for("", urls)
    )
    assert [r[0] for r in rows] == ["vlc"] and len(urls) == 1


def test_gentoo_repology_parse():
    urls = []
    rows, _, _ = catalog.search_online(
        "Gentoo", "stable", "firefox", opener_for(REPOLOGY, urls)
    )

    assert [r[0] for r in rows] == [
        "media-video/vlc", "www-client/firefox", "www-client/firefox-bin"
    ]
    assert "inrepo=gentoo" in urls[0] and "search=firefox" in urls[0]


def test_bad_answers_raise():
    with pytest.raises(SourceError):
        catalog.parse_repology("<html>")

    with pytest.raises(SourceError):
        catalog.search_online("Debian", "x", "a")
