import subprocess

import pytest

from ulb import advanced
from ulb.advanced import (
    advanced_report, arch_extras, debian_extras, fedora_extras, normalize,
    parse_repo, sha512_crypt, validate
)
from ulb.builders import arch_script, debian_script, fedora_script

FULL = {
    "enabled": True,
    "locale": "fr_FR.UTF-8",
    "keyboard": "fr",
    "timezone": "Europe/Paris",
    "hostname": "poste-ulb",
    "username": "alice",
    "persistence": True,
    "luks": True,
    "filesystem": "btrfs",
    "snapshots": True,
    "secureboot": True,
    "proprietary": True,
    "mirror": "https://miroir.example.org/debian",
    "proxy": "http://proxy.local:3128",
    "aur": True,
    "aur_packages": ["yay-bin", "paru"],
    "repos": ["monrepo|https://repo.example.org/$arch|Optional TrustAll"]
}


def syntax_ok(script, shell="sh"):
    return subprocess.run([shell, "-n", "-c", script]).returncode == 0


def test_sha512_crypt_matches_openssl():
    for password, salt in (
        ("password", "abcdefghijklmnop"),
        ("é" * 40 + "x" * 30, "S4lt"),
        ("x" * 200, "0123456789abcdef")
    ):
        reference = subprocess.run(
            ["openssl", "passwd", "-6", "-salt", salt, "-stdin"],
            input=password, capture_output=True, text=True
        )

        if reference.returncode:
            pytest.skip("openssl indisponible")

        assert sha512_crypt(password, salt) == reference.stdout.strip()


def test_validation_rejects_dangerous_values():
    bad = dict(FULL, hostname="a;rm -rf /", username="Root")
    errors = validate("Debian", bad)
    assert any("hôte" in e for e in errors)
    assert any("utilisateur" in e.lower() for e in errors)

    assert validate("Debian", dict(FULL, aur=False, repos=[], mirror="x y"))
    assert validate("Debian", dict(FULL, timezone="Europe/Paris; id"))
    assert not validate(
        "Arch Linux", dict(FULL, mirror="https://a.example/arch")
    )
    # Dépôts tiers : réservés à Arch.
    assert any("Arch" in e for e in validate("Fedora", FULL))
    # Désactivé : jamais d'erreur.
    assert validate("Debian", {"enabled": False, "hostname": ";"}) == []


def test_normalize_ignores_unknown_and_never_keeps_password():
    result = normalize({"enabled": 1, "password": "secret", "zzz": 1})
    assert result["enabled"] is True
    assert "password" not in result and "zzz" not in result


def test_parse_repo():
    assert parse_repo("a|https://x.org/y") == (
        "a", "https://x.org/y", "Optional TrustAll"
    )
    assert parse_repo("a|ftp://x") is None
    assert parse_repo("a b|https://x") is None


def test_debian_extras_content():
    extra = debian_extras(FULL, "motdepasse")
    config = " ".join(extra["config"])

    assert extra["nonfree"]
    assert "locales=fr_FR.UTF-8" in config
    assert "keyboard-layouts=fr" in config
    assert "timezone=Europe/Paris" in config
    assert "username=alice" in config and "persistence" in config
    assert "--mirror-bootstrap" in config and "--apt-http-proxy" in config
    assert "nvidia-driver" in extra["packages"]
    assert "shim-signed" in extra["packages"]
    assert "cryptsetup" in extra["packages"] and "snapper" in extra["packages"]
    assert "enableLuksAutomatedPartitioning true" in extra["setup"]
    assert "defaultFileSystemType" in extra["setup"]
    assert "motdepasse" not in extra["setup"]
    assert "$6$" in extra["setup"]


def test_disabled_changes_nothing():
    off = {"enabled": False}
    assert debian_extras(off)["packages"] == []
    assert fedora_extras("44", off)["head"] == []
    assert arch_extras(off)["setup"] == ""
    plain = debian_script("/w", "trixie", ["a"], {})
    assert plain == debian_script("/w", "trixie", ["a"], {"advanced": off})


def test_debian_script_syntax_and_nonfree():
    script = debian_script(
        "/w", "trixie", ["a"], {"advanced": FULL, "password": "pw"}
    )
    assert syntax_ok(script)
    assert "non-free" in script
    assert "--bootappend-live" in script
    assert script.index("hook.chroot") < script.index("lb build")


def test_fedora_extras_and_script():
    extra = fedora_extras("44", FULL, "pw")
    head = "\n".join(extra["head"])

    assert "lang fr_FR.UTF-8" in head
    assert "keyboard --xlayouts='fr'" in head
    assert "timezone Europe/Paris --utc" in head
    assert "network --hostname=poste-ulb" in head
    assert "rpmfusion-nonfree" in head and "nonfree-fedora-44" in head
    assert extra["lmc"] == ["--proxy", "http://proxy.local:3128"]
    assert "default_scheme = BTRFS" in "\n".join(extra["post"])
    assert "file_system_type" not in "\n".join(extra["post"])
    assert "akmod-nvidia" in extra["packages"]

    script = fedora_script(
        "/w", "44", ["a"], "Xfce", {"advanced": FULL, "password": "pw"}
    )
    assert syntax_ok(script)
    assert script.index("flat.ks") < script.index("%packages")
    assert "--proxy" in script

    ext4 = fedora_extras("44", dict(FULL, filesystem="ext4"))
    assert "file_system_type = ext4" in "\n".join(ext4["post"])
    assert "default_scheme = LVM" in "\n".join(ext4["post"])


def test_arch_extras_and_script():
    extra = arch_extras(FULL, "linux-lts", "pw")

    assert "nvidia-lts" in extra["packages"]
    assert "yay-bin" in extra["packages"] and "grub-btrfs" in extra["packages"]
    assert extra["env"].startswith("http_proxy=")
    assert "KEYMAP=fr" in extra["setup"]
    assert "alice:x:1000:1000" in extra["setup"]
    assert "[monrepo]" in extra["setup"]
    assert "makepkg" in extra["setup"] and "repo-add" in extra["setup"]
    clear = arch_extras(FULL, "linux-lts", "MotDePasseClair")["setup"]
    assert "MotDePasseClair" not in clear and "$6$" in clear

    script = arch_script(
        "/w", ["base"], {"advanced": FULL, "kernel_package": "linux-lts",
                         "password": "pw"}
    )
    assert syntax_ok(script)
    assert script.index("ulb-mirrorlist") < script.index("mkarchiso")

    hardened = arch_extras(FULL, "linux-hardened")["packages"]
    assert "nvidia-dkms" in hardened and "linux-hardened-headers" in hardened

    # Sans utilisateur : le mot de passe est celui de root.
    root_only = arch_extras(dict(FULL, username=""), "linux", "pw")
    assert "root:" in root_only["setup"] and "alice" not in root_only["setup"]
    assert syntax_ok(root_only["setup"])


def test_report_is_family_specific():
    def states(family, adv=FULL):
        return {row[0]: row[1] for row in advanced_report(family, adv)}

    assert advanced_report("Debian", {})[0][1] == advanced.OFF
    assert states("Debian")["Chiffrement du disque (LUKS)"] == advanced.APPLIED
    assert states("Arch Linux")["Chiffrement du disque (LUKS)"] == advanced.NA
    assert states("Fedora")["Dépôts tiers (AUR, pacman)"] == advanced.NA
    assert states("Arch Linux")["Dépôts tiers (AUR, pacman)"] == advanced.APPLIED
    assert states("Fedora")["Persistance (clé USB)"] == advanced.NA
    assert states("Debian")["Persistance (clé USB)"] == advanced.PARTIAL


def test_password_never_reaches_report_or_clear_scripts():
    from ulb.builders import public_options

    shown = public_options({"password": "SuperSecret", "light": True})
    assert "SuperSecret" not in str(shown) and shown["light"]

    for script in (
        debian_script("/w", "trixie", ["a"],
                      {"advanced": FULL, "password": "SuperSecret"}),
        fedora_script("/w", "44", ["a"], "Xfce",
                      {"advanced": FULL, "password": "SuperSecret"}),
        arch_script("/w", ["a"],
                    {"advanced": FULL, "password": "SuperSecret"}),
    ):
        assert "SuperSecret" not in script
        assert "$6$" in script
