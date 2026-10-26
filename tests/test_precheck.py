import os
import subprocess

from conftest import posix_only
from ulb.builders import debian_script
from ulb.checklist import installer_checklist
from ulb.precheck import (
    DEBIAN_LIVE_ESSENTIAL,
    debian_postcheck,
    live_essentials
)


def test_essentials_include_user_setup_and_graphics():
    extra = live_essentials("Debian", "Xfce", ["xfce4", "lightdm"])

    for name in ("user-setup", "live-config", "sudo", "locales"):
        assert name in extra

    assert "xserver-xorg" in extra
    assert "lightdm-gtk-greeter" in extra


def test_no_graphics_without_desktop_and_no_duplicates():
    extra = live_essentials(
        "Debian", "Aucun", ["sudo", "user-setup"]
    )

    assert "xserver-xorg" not in extra
    assert "sudo" not in extra and "user-setup" not in extra
    assert live_essentials("Fedora", "Xfce", []) == []
    assert live_essentials("Arch Linux", "Xfce", []) == []


def test_debian_script_ends_with_postcheck():
    script = debian_script(
        "/w", "trixie", ["xfce4", "user-setup"], {"light": True}
    )

    assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0
    assert "--apt-recommends false" in script
    assert script.index("lb build") < script.index("dpkg-query")
    assert "ISO INCOMPLÈTE" in script


@posix_only
def test_postcheck_detects_missing_package(tmp_path):
    (tmp_path / "chroot/var/lib/dpkg").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "dpkg-query"
    stub.write_text(
        '#!/bin/sh\nfor a; do last=$a; done\n'
        'case "$last" in user-setup) echo -n "un";; '
        '*) echo -n "ii ";; esac\n'
    )
    stub.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir) + ":" + os.environ["PATH"])

    result = subprocess.run(
        ["sh", "-c", debian_postcheck(["sudo", "user-setup"])],
        cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert result.returncode == 4
    assert "user-setup" in result.stderr and "sudo" not in result.stderr

    result = subprocess.run(
        ["sh", "-c", debian_postcheck(["sudo"])],
        cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert result.returncode == 0 and "vérifiés" in result.stdout


def test_checklist_mentions_live_session_and_postcheck():
    rows = installer_checklist(
        "Debian", "Xfce", ["xfce4", "lightdm", "grub-efi-amd64"], []
    )
    labels = [row[0] for row in rows]

    assert any("Session live" in label for label in labels)
    assert any("Contrôle après construction" in label for label in labels)
    assert "user-setup" in DEBIAN_LIVE_ESSENTIAL
