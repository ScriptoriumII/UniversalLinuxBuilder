import subprocess
import time

import pytest

from conftest import posix_only
from ulb.vm import URL_MARKER, vm_script


def test_script_uefi_boot_iso(tmp_path):
    ovmf = tmp_path / "OVMF_CODE.fd"
    ovmf.write_bytes(b"x")

    script = vm_script(
        "t", "/a.iso", "UEFI", "iso", 4096, 2, 32, "web", [str(ovmf)]
    )

    assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0
    assert "if=pflash" in script and "OVMF_VARS.fd" in script
    assert "-cdrom /a.iso" in script and "-boot order=dc" in script
    assert "-m 4096" in script and "-smp 2" in script
    assert "websocket=5700" in script and URL_MARKER in script
    assert "-device virtio-vga" in script and "usb-tablet" in script


def test_script_bios_boot_disk_window():
    script = vm_script("t", "", "BIOS", "disk", 2048, 1, 16, "window")

    assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0
    assert "pflash" not in script and "-cdrom" not in script
    assert "-boot order=c" in script and "-display gtk" in script


@pytest.mark.parametrize(
    "bad",
    [
        dict(mode="XYZ"),
        dict(boot="usb"),
        dict(display="rdp"),
        dict(ram=100),
        dict(disk_gb=1),
    ],
)
def test_script_rejects_bad_parameters(bad):
    arguments = dict(
        vm_id="t", iso="/a.iso", mode="BIOS", boot="iso",
        ram=2048, cpus=2, disk_gb=16, display="vnc"
    )
    arguments.update(bad)

    with pytest.raises(ValueError):
        vm_script(**arguments)


def test_iso_path_is_quoted():
    script = vm_script("t", "/a b;rm -rf /.iso", "BIOS", "iso", 2048, 1, 8, "vnc")
    assert "'/a b;rm -rf /.iso'" in script


@posix_only
def test_vm_starts_and_stops_from_the_ui(fake_wsl, monkeypatch, tmp_path):
    from test_ui import make_window, pump

    app, window = make_window(fake_wsl, monkeypatch)
    window.associations["Debian"] = "Debian"
    iso = tmp_path / "x.iso"
    iso.write_bytes(b"\0" * 4096)

    window.vm_iso.setText(str(iso))
    window.vm_display.setCurrentIndex(2)  # VNC externe : pas de navigateur
    window.vm_mode.setCurrentText("BIOS")
    window.start_vm()

    pump(app, lambda: "ULB_FAKE_VM_RUNNING" in window.vm_log.toPlainText(), 15)
    assert window.vm_running()
    assert window.vm_stop_button.isEnabled()
    assert "Client VNC" in window.vm_log.toPlainText()

    window.stop_vm_clicked()
    pump(app, lambda: not window.vm_running(), 15)
    app.processEvents()

    assert not window.vm_running()
    assert window.vm_start_button.isEnabled()
    assert "MACHINE ARRÊTÉE" in window.vm_log.toPlainText()
    window.close()
    time.sleep(0.2)
