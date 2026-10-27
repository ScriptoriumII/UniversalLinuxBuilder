"""Régressions de données : bureaux, GRUB, installateurs."""

import pytest

from ulb.constants import (
    DESKTOPS, DISPLAY_MANAGERS, FAMILIES, FEDORA_KICKSTARTS,
    GRUB_PACKAGES, LIVE_INSTALLER, RELEASES, SAFE_PACKAGE, TARGET_BASE
)


@pytest.mark.parametrize("family", ["Debian", "Fedora", "Arch Linux"])
def test_budgie_is_offered(family):
    # Régression v1.21 : Budgie avait disparu des bureaux.
    assert "Budgie" in DESKTOPS[family]
    assert any("budgie" in name for name in DESKTOPS[family]["Budgie"])


def test_every_family_has_data():
    for family in FAMILIES:
        assert family in DESKTOPS and family in TARGET_BASE
        assert family in RELEASES and RELEASES[family]


def test_graphical_desktops_bring_a_display_manager_or_installer_path():
    for family, desktops in DESKTOPS.items():
        for name, packages in desktops.items():
            if family == "Fedora" and name in ("Xfce",):
                continue  # géré par le kickstart du bureau

            if name != "Aucun" and family != "Slackware" and family != "Gentoo":
                assert DISPLAY_MANAGERS & set(packages) or family == "Fedora", (
                    family, name
                )


def test_grub_bios_and_uefi_are_exclusive_on_debian():
    uefi = set(GRUB_PACKAGES["Debian"]["UEFI"])
    bios = set(GRUB_PACKAGES["Debian"]["BIOS"])
    assert "grub-pc" in bios and "grub-pc" not in uefi
    assert "grub-efi-amd64" in uefi and "grub-efi-amd64" not in bios


def test_installers():
    assert "calamares" in LIVE_INSTALLER["Debian"]
    assert "anaconda" in LIVE_INSTALLER["Fedora"]
    assert "Arch Linux" not in LIVE_INSTALLER  # Calamares : AUR seulement


def test_fedora_kickstarts_cover_all_fedora_desktops():
    for desktop in DESKTOPS["Fedora"]:
        assert desktop in FEDORA_KICKSTARTS


def test_all_package_names_are_shell_safe():
    names = []

    for table in (DESKTOPS, TARGET_BASE):
        for value in table.values():
            if isinstance(value, dict):
                for packages in value.values():
                    names += packages
            else:
                names += value

    for name in names:
        assert SAFE_PACKAGE.match(name), name


def test_fedora_search_parses_dnf5_and_dnf4_formats():
    from ulb.packages import fedora_search_command, parse_search

    out = (
        "Updating and loading repositories:\n"
        "Repositories loaded.\n"
        "firefox|150.0-1.fc44|Mozilla Firefox Web browser\n"
        "Matched fields: name, summary\n"
        " vlc.x86_64   Multimedia player\n"
        "mpv.x86_64 : Movie player\n"
    )
    rows = parse_search("Fedora", out)
    names = {r[0]: r for r in rows}
    assert set(names) == {"firefox", "vlc", "mpv"}
    assert names["firefox"][1] == "150.0-1.fc44"
    assert parse_search("Fedora", "Repositories loaded.\n") == []

    command = fedora_search_command("fire fox; rm")
    assert "repoquery" in command and "dnf5 search" in command
    assert "'*fire fox; rm*'" in command
