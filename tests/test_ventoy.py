import hashlib
import io
import json
import zipfile

import pytest

from ulb import ventoy
from ulb.ventoy import (
    VentoyError, build_cli_args, elevated_command, parse_disks,
    parse_release, persistence_creation_script, update_ventoy_json
)

RELEASE = json.dumps({
    "tag_name": "v1.1.05",
    "assets": [
        {"name": "ventoy-1.1.05-linux.tar.gz",
         "browser_download_url": "https://github.com/x/linux.tar.gz"},
        {"name": "ventoy-1.1.05-windows.zip",
         "browser_download_url": "https://github.com/x/windows.zip"},
        {"name": "sha256.txt",
         "browser_download_url": "https://github.com/x/sha256.txt"}
    ]
})


def test_parse_release():
    release = parse_release(RELEASE)
    assert release["version"] == "1.1.05"
    assert release["zip_name"] == "ventoy-1.1.05-windows.zip"
    assert release["sha_url"].endswith("sha256.txt")

    with pytest.raises(VentoyError):
        parse_release("pas du json")

    with pytest.raises(VentoyError):
        parse_release(json.dumps({"tag_name": "v1.1", "assets": []}))

    with pytest.raises(VentoyError):
        parse_release(json.dumps({"tag_name": "v1; rm", "assets": []}))


def test_parse_disks_refuses_system_and_boot_disks():
    text = json.dumps([
        {"Number": 0, "Name": "SSD", "Size": 500 * 10 ** 9,
         "Style": "GPT", "Boot": True, "System": True},
        {"Number": 2, "Name": "SanDisk", "Size": 32 * 10 ** 9,
         "Style": "MBR", "Boot": False, "System": False},
        {"Number": 3, "Name": "Boot USB", "Size": 8 * 10 ** 9,
         "Style": "MBR", "Boot": True, "System": False}
    ])

    disks = parse_disks(text)
    assert [d["number"] for d in disks] == [2]
    assert "Disque 2" in ventoy.disk_label(disks[0])

    # Un seul disque : PowerShell renvoie un objet, pas une liste.
    one = parse_disks(json.dumps(
        {"Number": 4, "Name": "K", "Size": 1, "Boot": False, "System": False}
    ))
    assert [d["number"] for d in one] == [4]
    assert parse_disks("") == []

    with pytest.raises(VentoyError):
        parse_disks("{pas json")


def test_cli_arguments_follow_documentation():
    assert build_cli_args("install", 2, "GPT", False, 4096, "exFAT") == [
        "VTOYCLI", "/I", "/PhyDrive:2", "/GPT", "/R:4096", "/FS:exFAT",
        "/NOSB"
    ]
    assert build_cli_args("install", 3) == [
        "VTOYCLI", "/I", "/PhyDrive:3", "/FS:exFAT"
    ]
    assert build_cli_args("update", 3, secure_boot=False) == [
        "VTOYCLI", "/U", "/PhyDrive:3", "/NOSB"
    ]

    for bad in (
        dict(action="install", number=0),
        dict(action="install", number=2, style="XYZ"),
        dict(action="install", number=2, filesystem="ext4"),
        dict(action="install", number=2, reserve_mb=-5),
        dict(action="format", number=2)
    ):
        with pytest.raises(VentoyError):
            build_cli_args(**bad)


def test_elevated_command_quotes_and_refuses_quotes():
    command = elevated_command(
        r"C:\Users\Moi\ventoy\Ventoy2Disk.exe", ["VTOYCLI", "/I"]
    )
    assert "-Verb RunAs" in command and "-Wait" in command
    assert "'VTOYCLI','/I'" in command

    with pytest.raises(VentoyError):
        elevated_command("C:\\a'b\\Ventoy2Disk.exe", ["VTOYCLI"])


def test_ventoy_json_merge_keeps_existing_and_refuses_invalid():
    first = update_ventoy_json("", "a.iso", "a.dat")
    assert json.loads(first)["persistence"] == [
        {"image": "/a.iso", "backend": "/a.dat"}
    ]

    existing = json.dumps({
        "control": [{"VTOY_DEFAULT_MENU_MODE": "1"}],
        "persistence": [{"image": "/b.iso", "backend": "/b.dat"}]
    })
    merged = json.loads(update_ventoy_json(existing, "a.iso", "a.dat"))
    assert merged["control"] == [{"VTOY_DEFAULT_MENU_MODE": "1"}]
    assert len(merged["persistence"]) == 2

    again = json.loads(
        update_ventoy_json(json.dumps(merged), "a.iso", "new.dat")
    )
    assert {"image": "/a.iso", "backend": "/new.dat"} in again["persistence"]
    assert len(again["persistence"]) == 2

    with pytest.raises(VentoyError):
        update_ventoy_json("{casse", "a.iso", "a.dat")


def test_persistence_script_syntax_and_limits():
    import subprocess

    script = persistence_creation_script(1024)
    assert "-L persistence" in script and "/ union" in script
    assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0

    with pytest.raises(VentoyError):
        persistence_creation_script(10)


def make_zip(files):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)

    return buffer.getvalue()


class Fake(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(archive, good_hash=True):
    digest = hashlib.sha256(archive).hexdigest()

    if not good_hash:
        digest = "0" * 64

    def opener(url, *a, **k):
        if url.endswith("releases/latest"):
            return Fake(RELEASE.encode())

        if url.endswith("sha256.txt"):
            return Fake(
                (digest + "  ventoy-1.1.05-windows.zip\n").encode()
            )

        return Fake(archive)

    return opener


def test_fetch_ventoy_verifies_hash_and_extracts(tmp_path):
    archive = make_zip({"ventoy-1.1.05/Ventoy2Disk.exe": b"MZ"})

    version, exe = ventoy.fetch_ventoy(
        base=tmp_path, opener=fake_opener(archive)
    )
    assert version == "1.1.05" and exe.name == "Ventoy2Disk.exe"
    assert ventoy.installed_versions(tmp_path) == ["1.1.05"]

    # Déjà présent : aucun nouveau téléchargement.
    again = ventoy.fetch_ventoy(base=tmp_path, opener=fake_opener(b"x"))
    assert again[1] == exe


def test_fetch_ventoy_rejects_bad_hash_and_bad_paths(tmp_path):
    archive = make_zip({"ventoy-1.1.05/Ventoy2Disk.exe": b"MZ"})

    with pytest.raises(VentoyError, match="SHA-256"):
        ventoy.fetch_ventoy(
            base=tmp_path / "a", opener=fake_opener(archive, False)
        )

    assert not list((tmp_path / "a").glob("*.zip"))

    evil = make_zip({"../evil.txt": b"x"})

    with pytest.raises(VentoyError, match="suspect"):
        ventoy.fetch_ventoy(base=tmp_path / "b", opener=fake_opener(evil))

    assert not (tmp_path / "evil.txt").exists()


def test_install_checks_data_partition(tmp_path):
    exe = tmp_path / "Ventoy2Disk.exe"
    exe.write_bytes(b"MZ")
    calls = []

    def runner(argv, timeout=0):
        calls.append(argv[-1])

        if "Start-Process" in argv[-1]:
            return "", "", 0

        return "E\n", "", 0

    drive = ventoy.install_ventoy(
        exe, ["VTOYCLI", "/I", "/PhyDrive:2"], 2, runner=runner
    )
    assert drive == "E:" and "Start-Process" in calls[0]

    def failing(argv, timeout=0):
        return ("", "", 0) if "Start-Process" in argv[-1] else ("", "", 1)

    with pytest.raises(VentoyError, match="non confirmée"):
        ventoy.install_ventoy(
            exe, ["VTOYCLI", "/I", "/PhyDrive:2"], 2, runner=failing
        )

    def refused(argv, timeout=0):
        return "", "annulé par l'utilisateur", 1

    with pytest.raises(VentoyError, match="code 1"):
        ventoy.install_ventoy(
            exe, ["VTOYCLI", "/I", "/PhyDrive:2"], 2, runner=refused
        )


def test_copy_isos_never_overwrites(tmp_path, monkeypatch):
    drive = tmp_path / "usb"
    drive.mkdir()
    iso = tmp_path / "a.iso"
    iso.write_bytes(b"x" * 1000)
    (drive / "a.iso").write_bytes(b"old")

    class Root(str):
        pass

    monkeypatch.setattr(ventoy, "Path", lambda value: (
        __import__("pathlib").Path(str(drive)) if str(value).endswith("\\")
        else __import__("pathlib").Path(value)
    ))

    names = ventoy.copy_isos("X:", [iso])
    assert names == ["a-2.iso"]
    assert (drive / "a.iso").read_bytes() == b"old"
    assert (drive / "a-2.iso").read_bytes() == b"x" * 1000
