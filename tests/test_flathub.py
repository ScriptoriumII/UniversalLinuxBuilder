import subprocess

import pytest

from ulb.builders import (
    arch_script, debian_script, fedora_post_lines, fedora_script
)
from ulb.checklist import installer_checklist
from ulb.constants import EXTRAS, FAMILIES, FLATHUB_URL
from ulb.environments import (
    fedora_third_party_command, flathub_command
)


def syntax_ok(script):
    return subprocess.run(["sh", "-n", "-c", script]).returncode == 0


@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_offers_flatpak(family):
    assert EXTRAS[family]["Flathub"]


@pytest.mark.parametrize("family", FAMILIES)
def test_flathub_command_for_wsl(family):
    command = flathub_command(family)
    assert syntax_ok(command)
    assert FLATHUB_URL in command
    assert "--system" in command


def test_slackware_does_not_pretend_to_install_flatpak():
    assert "SlackBuilds" in flathub_command("Slackware")


def test_build_scripts_embed_flathub_only_when_asked():
    on = {"flathub": True}

    for script in (
        debian_script("/w", "trixie", ["a"], on),
        fedora_script("/w", "44", ["a"], "Xfce", on),
        arch_script("/w", ["a"], on),
    ):
        assert syntax_ok(script)
        assert "etc/flatpak/remotes.d" in script
        assert FLATHUB_URL in script

    for script in (
        debian_script("/w", "trixie", ["a"], {}),
        fedora_script("/w", "44", ["a"], "Xfce", {}),
        arch_script("/w", ["a"], {}),
    ):
        assert "flatpak" not in script


def test_debian_and_arch_use_the_image_root():
    assert "config/includes.chroot/etc/flatpak/remotes.d" in debian_script(
        "/w", "trixie", [], {"flathub": True}
    )
    assert "profile/airootfs/etc/flatpak/remotes.d" in arch_script(
        "/w", [], {"flathub": True}
    )


def test_fedora_third_party_post_section():
    lines = fedora_post_lines("44", {"third_party": True})
    text = "\n".join(lines)
    assert "rpmfusion-free-release-44" in text
    assert "rpmfusion-nonfree-release-44" in text
    assert "fedora-workstation-repositories" in text

    script = fedora_script(
        "/w", "44", ["a"], "Xfce", {"third_party": True}
    )
    assert syntax_ok(script) and "'%post'" in script
    assert "%post" not in fedora_script("/w", "44", ["a"], "Xfce", {})


def test_wsl_third_party_command():
    command = fedora_third_party_command()
    assert syntax_ok(command)
    assert "rpmfusion-nonfree-release-$(rpm -E %fedora)" in command


def test_checklist_mentions_flathub():
    rows = installer_checklist("Debian", "Xfce", ["flatpak"], [])
    assert any(r[0].startswith("Flathub") and r[1] == "À valider" for r in rows)

    rows = installer_checklist("Gentoo", "Xfce", ["sys-apps/flatpak"], [])
    assert any(r[0].startswith("Flathub") and r[1] == "À configurer" for r in rows)

    rows = installer_checklist("Debian", "Xfce", ["a"], [])
    assert not any(r[0].startswith("Flathub") for r in rows)
