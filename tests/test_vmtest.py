import struct
import zlib

import pytest

from ulb.vmtest import analyse_screen, qemu_script, read_ppm, write_png


def ppm(width, height, pixels):
    return b"P6\n%d %d\n255\n" % (width, height) + pixels


def test_ppm_roundtrip_and_png(tmp_path):
    rgb = bytes([200, 10, 10, 10, 200, 10, 10, 10, 200, 255, 255, 255])
    width, height, data = read_ppm(ppm(2, 2, rgb))
    assert (width, height, data) == (2, 2, rgb)

    target = tmp_path / "shot.png"
    write_png(target, width, height, data)
    png = target.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert zlib.crc32(png[12:29]) & 0xFFFFFFFF == struct.unpack(">I", png[29:33])[0]


def test_truncated_ppm():
    with pytest.raises(ValueError):
        read_ppm(ppm(4, 4, b"\x00" * 10))


def test_black_screen_is_blank():
    assert analyse_screen(10, 10, bytes(300))["blank"] is True


def test_colourful_screen_is_not_blank():
    pixels = bytes([200, 30, 30, 30, 200, 30, 30, 30, 200]) * 40
    assert analyse_screen(40, 3, pixels)["blank"] is False


def test_qemu_script_modes():
    uefi = qemu_script("/a.iso", "UEFI", 90, "/var/tmp/w")
    bios = qemu_script("/a.iso", "BIOS", 90, "/var/tmp/w")
    assert "pflash" in uefi and "pflash" not in bios
    assert "screendump" in uefi and "-display none" in bios

    with pytest.raises(ValueError):
        qemu_script("/a.iso", "XYZ", 1, "/w")
