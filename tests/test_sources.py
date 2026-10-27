import hashlib
import http.server
import threading
from functools import partial

import pytest

from ulb import sources
from ulb.sources import SourceError
from ulb.wsl import Cancelled, Control


def test_parse_autobuild_index_ignores_pgp_armor():
    text = (
        "-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\n"
        "# Latest as of Mon, 26 Oct 2026\n"
        "20261026T170000Z/install-amd64-minimal-20261026T170000Z.iso "
        "773849088\n"
        "20261026T170000Z/stage3.tar.xz 10\n"
        "-----BEGIN PGP SIGNATURE-----\nabc\n"
    )

    assert sources.parse_autobuild_index(text) == [
        ("20261026T170000Z/install-amd64-minimal-20261026T170000Z.iso",
         773849088)
    ]


def test_parse_checksums_formats():
    sha = "a" * 64
    big = "b" * 128
    text = (
        "# SHA512 HASH\n" + big + "  install.iso\n"
        "# SHA256\n" + sha + " *dir/install.iso\n"
        "SHA256 (install.iso) = " + sha + "\n"
        + "c" * 64 + "  other.iso\n" + "d" * 32 + "  install.iso\n"
    )

    assert sources.parse_checksums(text, "http://x/install.iso") == {
        "sha512": big, "sha256": sha
    }


@pytest.fixture
def mirror(tmp_path):
    root = tmp_path / "mirror"
    root.mkdir()
    # descripteur de volume primaire : type 1, « CD001 », nom en 40..72
    iso = (
        bytes(32768) + b"\x01CD001\x01\x00" + b" " * 32
        + b"MON_VOLUME".ljust(32) + bytes(2000)
    )
    (root / "demo.iso").write_bytes(iso)
    (root / "demo.iso.sha256").write_text(
        hashlib.sha256(iso).hexdigest() + "  demo.iso\n"
    )
    (root / "bad.iso").write_bytes(iso)
    (root / "bad.iso.sha256").write_text("0" * 64 + "  bad.iso\n")
    (root / "latest.txt").write_text("sub/demo.iso 1234\n")
    (root / "sub").mkdir()
    (root / "sub" / "demo.iso").write_bytes(iso)

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/" % server.server_address[1], root, iso
    server.shutdown()


def test_download_verifies_and_inspects(mirror, tmp_path):
    base, root, iso = mirror
    control = Control()

    info = sources.fetch_iso("Slackware", "", base + "demo.iso",
                             tmp_path / "dl", control)

    assert info["checksum"] == "OK" and info["iso9660"]
    assert info["label"] == "MON_VOLUME"
    assert (tmp_path / "dl" / "demo.iso").read_bytes() == iso


def test_bad_checksum_is_refused(mirror, tmp_path):
    base, *_ = mirror

    with pytest.raises(SourceError, match="Empreinte incorrecte"):
        sources.fetch_iso("Slackware", "", base + "bad.iso",
                          tmp_path / "dl", Control())


def test_resume_partial_download(mirror, tmp_path):
    base, root, iso = mirror
    directory = tmp_path / "dl"
    directory.mkdir()
    (directory / "demo.iso.part").write_bytes(iso[:10000])

    target = sources.download(base + "demo.iso", directory, Control())

    assert target.read_bytes() == iso
    assert not (directory / "demo.iso.part").exists()


def test_cancel_stops_download(mirror, tmp_path):
    base, *_ = mirror
    control = Control()
    control.cancel()

    with pytest.raises(Cancelled):
        sources.download(base + "demo.iso", tmp_path / "dl", control)


def test_resolve_gentoo_from_index(mirror, monkeypatch):
    base, *_ = mirror
    monkeypatch.setitem(
        sources.SOURCES["Gentoo"], "Test",
        {"index": base + "latest.txt", "base": base}
    )

    assert sources.resolve_source("Gentoo", "Test") == base + "sub/demo.iso"


def test_import_rejects_non_iso(tmp_path):
    fake = tmp_path / "x.iso"
    fake.write_bytes(b"pas une iso")

    with pytest.raises(SourceError, match="ISO9660"):
        sources.import_iso(fake)

    with pytest.raises(SourceError):
        sources.download("http://x/archive.zip", tmp_path, Control())
