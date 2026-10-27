import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import posix_only
from ulb.remaster import (
    clean_removals,
    gentoo_script,
    install_xorriso_command,
    slackware_script
)

needs_xorriso = pytest.mark.skipif(
    shutil.which("xorriso") is None, reason="xorriso absent"
)


def make_iso(tmp_path, name, files, volid="SlackDVD"):
    """ISO d'essai avec amorçage BIOS (El Torito) et UEFI (efiboot.img),
    construite comme le fait le README de Slackware."""

    tree = tmp_path / (name + "_tree")
    (tree / "isolinux").mkdir(parents=True)
    (tree / "isolinux" / "isolinux.bin").write_bytes(b"\x90" * 4096)
    (tree / "isolinux" / "efiboot.img").write_bytes(b"\x00" * 65536)

    for relative, content in files.items():
        path = tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    mbr = tmp_path / "mbr.bin"
    mbr.write_bytes(b"\x00" * 432)
    iso = tmp_path / (name + ".iso")

    result = subprocess.run(
        [
            "xorriso", "-as", "mkisofs", "-iso-level", "3", "-R", "-J",
            "-eltorito-boot", "isolinux/isolinux.bin",
            "-eltorito-catalog", "isolinux/boot.cat",
            "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
            "-isohybrid-mbr", str(mbr),
            "-eltorito-alt-boot", "-e", "isolinux/efiboot.img",
            "-no-emul-boot", "-isohybrid-gpt-basdat",
            "-volid", volid, "-output", str(iso), str(tree)
        ],
        capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    return iso


def listing(iso):
    result = subprocess.run(
        ["xorriso", "-indev", str(iso), "-find", "/", "-type", "f"],
        capture_output=True, text=True
    )
    return result.stdout


def run_script(script):
    return subprocess.run(
        ["sh", "-c", script], capture_output=True, text=True
    )


def test_scripts_are_valid_shell():
    for script in (
        gentoo_script("/w", "/a.iso", "/w/o.iso", "/ov", ["x/y"]),
        slackware_script("/w", "/a.iso", "/w/o.iso", "/ov",
                         ["slackware64/kde"])
    ):
        assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0


def test_removals_are_validated():
    assert clean_removals("Slackware", ["kde", "y"]) == [
        "slackware64/kde", "slackware64/y"
    ]

    for bad in (["a"], ["l"], ["../etc"], ["kde;rm"]):
        with pytest.raises(ValueError):
            clean_removals("Slackware", bad)

    with pytest.raises(ValueError):
        clean_removals("Gentoo", ["x"])

    with pytest.raises(ValueError):
        gentoo_script("/w", "/a.iso", "/o", "", ["../x"])


def test_install_command_per_family():
    assert "apt-get install" in install_xorriso_command("Debian")
    assert "libisoburn" in install_xorriso_command("Arch Linux")

    with pytest.raises(ValueError):
        install_xorriso_command("Gentoo")


@posix_only
@needs_xorriso
def test_gentoo_remaster_keeps_boot_and_adds_overlay(tmp_path):
    iso = make_iso(tmp_path, "g", {"boot/readme.txt": "x", "keep.txt": "k"},
                   volid="GENTOO_LIVE")
    overlay = tmp_path / "overlay"
    (overlay / "ulb").mkdir(parents=True)
    (overlay / "ulb" / "bonjour.txt").write_text("salut")
    out = tmp_path / "work" / "out.iso"

    result = run_script(gentoo_script(
        str(tmp_path / "work"), str(iso), str(out), str(overlay),
        ["boot/readme.txt"]
    ))

    assert result.returncode == 0, result.stderr
    assert "amorçage BIOS/UEFI identique" in result.stdout
    files = listing(out)
    assert "bonjour.txt" in files and "keep.txt" in files
    assert "readme.txt" not in files
    label = subprocess.run(
        ["xorriso", "-indev", str(out), "-pvd_info"],
        capture_output=True, text=True
    ).stdout
    assert "GENTOO_LIVE" in label


@posix_only
@needs_xorriso
def test_slackware_remaster_removes_series_and_rebuilds_boot(tmp_path):
    iso = make_iso(tmp_path, "s", {
        "slackware64/a/aaa.txz": "a",
        "slackware64/kde/kde.txz": "k",
        "slackware64/y/y.txz": "y",
        "source/src.tar": "s",
        "ChangeLog.txt": "c"
    })
    overlay = tmp_path / "ov"
    overlay.mkdir()
    (overlay / "extra.txt").write_text("e")
    out = tmp_path / "work" / "out.iso"

    result = run_script(slackware_script(
        str(tmp_path / "work"), str(iso), str(out), str(overlay),
        ["slackware64/kde", "slackware64/y"]
    ))

    assert result.returncode == 0, result.stderr
    assert "BIOS + UEFI présentes" in result.stdout
    files = listing(out)
    assert "aaa.txz" in files and "extra.txt" in files
    assert "kde.txz" not in files and "y.txz" not in files
    assert "src.tar" not in files


@posix_only
@needs_xorriso
def test_slackware_refuses_iso_without_boot_files(tmp_path):
    tree = tmp_path / "t"
    tree.mkdir()
    (tree / "x.txt").write_text("x")
    iso = tmp_path / "plain.iso"
    subprocess.run(["xorriso", "-as", "mkisofs", "-o", str(iso), str(tree)],
                   capture_output=True)

    result = run_script(slackware_script(
        str(tmp_path / "w"), str(iso), str(tmp_path / "w" / "o.iso")
    ))

    assert result.returncode == 4
    assert "fichier d'amorçage absent" in result.stderr
    assert not (tmp_path / "w" / "o.iso").exists()


@posix_only
@needs_xorriso
def test_boot_comparison_detects_lost_boot_entries(tmp_path):
    from ulb.remaster import BOOT_COMPARE, BOOT_SIGNATURE

    booted = make_iso(tmp_path, "b", {"x.txt": "x"})
    plain_tree = tmp_path / "p"
    plain_tree.mkdir()
    (plain_tree / "x.txt").write_text("x")
    plain = tmp_path / "plain.iso"
    subprocess.run(["xorriso", "-as", "mkisofs", "-o", str(plain),
                    str(plain_tree)], capture_output=True)

    result = run_script(
        "set -eu; " + BOOT_SIGNATURE + "; iso=" + str(booted)
        + "; out=" + str(plain) + "; " + BOOT_COMPARE
    )

    assert result.returncode == 5
    assert "AMORÇAGE PERDU" in result.stderr


@posix_only
@needs_xorriso
def test_remaster_iso_end_to_end_gentoo(fake_wsl, tmp_path, workspaces):
    from ulb.remaster import remaster_iso

    iso = make_iso(tmp_path, "gentoo", {"image.squashfs": "x"},
                   volid="GENTOO_LIVE")
    destination = tmp_path / "isos"
    destination.mkdir()
    (destination / "autre.iso").write_bytes(b"deja la")
    overlay = tmp_path / "ov"
    overlay.mkdir()
    (overlay / "mon_script.sh").write_text("echo ok")

    files, report = remaster_iso(
        "Debian", "Gentoo", str(iso), str(destination),
        {"overlay": str(overlay)}
    )

    assert len(files) == 1 and files[0]["iso9660"]
    assert Path(files[0]["file"]).parent == destination
    assert (destination / "autre.iso").read_bytes() == b"deja la"
    assert "mon_script.sh" in listing(files[0]["file"])
    assert "SUCCÈS" in report and "identique" in report
    assert files[0]["sha256"] in (destination / "SHA256SUMS").read_text()
    assert list(destination.glob("build_report_*.txt"))


@posix_only
@needs_xorriso
def test_remaster_iso_slackware_removes_series(fake_wsl, tmp_path, workspaces):
    from ulb.remaster import remaster_iso

    iso = make_iso(tmp_path, "slack", {
        "slackware64/a/a.txz": "a", "slackware64/kde/k.txz": "k"
    })
    destination = tmp_path / "out"
    destination.mkdir()

    files, report = remaster_iso(
        "Debian", "Slackware", str(iso), str(destination),
        {"remove": ["kde"]}
    )

    listing_out = listing(files[0]["file"])
    assert "a.txz" in listing_out and "k.txz" not in listing_out


@posix_only
def test_remaster_iso_rejects_bad_inputs(fake_wsl, tmp_path):
    from ulb.remaster import remaster_iso
    from ulb.sources import SourceError

    notiso = tmp_path / "x.iso"
    notiso.write_bytes(b"non")

    with pytest.raises(SourceError):
        remaster_iso("Debian", "Gentoo", str(notiso), str(tmp_path))

    with pytest.raises(RuntimeError, match="non prévu"):
        remaster_iso("Debian", "Fedora", str(notiso), str(tmp_path))
