import pytest

from conftest import posix_only
from ulb.constants import FAMILIES
from ulb.package_view import (
    human_size,
    package_origins,
    parse_simulation,
    update_message
)

DNF = """Package               Arch   Version                Repository     Size
Installing:
 budgie-desktop       x86_64 0:10.10.2-1.fc44       fedora       6.2 MiB
 grub2-efi-x64        x86_64 1:2.12-66.fc44         updates      6.2 MiB
 kernel               x86_64 0:7.2.12-200.fc44      updates      0.0 B
Installing dependencies:
 LibRaw               x86_64 0:0.22.2-1.fc44        updates      2.6 MiB
Installing weak dependencies:
 linux-firmware       noarch 0:20261019-1.fc44      updates     35.0 MiB

Transaction Summary:
 Installing:         5 packages
"""

APT = """Reading package lists...
Inst libfoo1 (1.2-3 Debian:13.0/stable [amd64])
Inst xfce4 (4.20 Debian:13.0/stable [all])
Inst sudo [1.9.1] (1.9.16-2 Debian:13.0/stable [amd64])
Conf xfce4 (4.20 Debian:13.0/stable [all])
"""

PACMAN = "base|3-2|0\nlinux|6.9.1|143000000\nlibfoo|1.0|2048\nwarning: nope\n"

EMERGE = (
    "[ebuild  N     ] sys-apps/openrc-0.54::gentoo  USE=\"ncurses\" 197 KiB\n"
    "[ebuild  N    ~] dev-libs/foo-2.0-r1:0/2::gentoo  1,024 KiB\n"
)


def test_dnf_columns_roles_and_sizes():
    rows = parse_simulation("Fedora", DNF, {"kernel", "budgie-desktop"})

    assert rows[0] == ("budgie-desktop", "0:10.10.2-1.fc44", "fedora",
                       "6.2 MiB", "Demandé")
    assert ("LibRaw", "0:0.22.2-1.fc44", "updates", "2.6 MiB",
            "Dépendance") in rows
    assert rows[-1][4] == "Dépendance faible"
    assert len(rows) == 5


def test_apt_rows():
    rows = parse_simulation("Debian", APT, {"xfce4", "sudo"})

    assert [r[0] for r in rows] == ["libfoo1", "xfce4", "sudo"]
    assert rows[0][4] == "Dépendance" and rows[1][4] == "Demandé"
    assert rows[2][1] == "1.9.16-2"
    assert rows[2][2] == "Debian:13.0/stable"


def test_pacman_and_emerge_rows():
    rows = parse_simulation("Arch Linux", PACMAN, {"base", "linux"})

    assert [r[0] for r in rows] == ["base", "linux", "libfoo"]
    assert rows[1][3] == "136.4 Mio" and rows[2][4] == "Dépendance"

    rows = parse_simulation("Gentoo", EMERGE, {"sys-apps/openrc"})

    assert rows[0][:3] == ("sys-apps/openrc", "0.54", "gentoo")
    assert rows[0][4] == "Demandé" and rows[1][1] == "2.0-r1"


def test_unknown_format_gives_no_rows():
    assert parse_simulation("Fedora", "rien de lisible") == []
    assert parse_simulation("Slackware", DNF) == []


def test_human_size():
    assert human_size(0) == "0 o" and human_size(1536) == "1.5 Kio"


def test_origins_first_match_wins_and_labels():
    origins = package_origins(
        ["systemd", "sudo"], ["xfce4", "sudo"], "Xfce",
        ["wireplumber"], "PipeWire", ["shim-x64"], "UEFI",
        {"Wi-Fi": ["wpasupplicant"]}, ["vim"], ["kernel"]
    )

    assert origins["systemd"] == "Système de base"
    assert origins["sudo"] == "Système de base"
    assert origins["xfce4"] == "Bureau Xfce"
    assert origins["wireplumber"] == "Audio PipeWire"
    assert origins["shim-x64"] == "Chargeur GRUB (UEFI)"
    assert origins["wpasupplicant"] == "Option Wi-Fi"
    assert origins["vim"] == "Application choisie"
    assert origins["kernel"] == "Noyau"


@pytest.mark.parametrize("family", FAMILIES)
def test_update_message_is_specific_to_the_family(family):
    message = update_message("MonWSL", family)
    others = [f for f in FAMILIES if f != family]

    assert family in message
    assert not any(other in message for other in others)
    assert ("COMPLÈTE" in message) == (family == "Arch Linux")


@posix_only
@pytest.mark.parametrize("family", ["Debian", "Fedora", "Arch Linux"])
def test_ui_messages_never_mention_another_family(
    fake_wsl, monkeypatch, family
):
    from PySide6.QtWidgets import QMessageBox

    from test_ui import make_window, pump

    app, window = make_window(fake_wsl, monkeypatch)
    pump(app, lambda: window.worker is None and bool(window.inventory), 15)
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda parent, title, text, *a, **k:
                     asked.append(text) or QMessageBox.StandardButton.No)
    )
    window.change_family(family)
    window.environment_item = lambda name: {"name": name, "family": family}
    window.environment_family = lambda name: family
    window.start_update("MonWSL")

    text = " ".join(asked)
    others = [f for f in FAMILIES if f != family]

    assert family in text
    assert not any(other in text for other in others)

    texts = " ".join([
        window.context_label.text(), window.packages_group.title(),
        window.resolution_group.title(), window.log_group.title(),
        window.verification_status.text()
    ])
    assert not any(other in texts for other in others)
    window.close()


@posix_only
def test_switching_family_clears_previous_results(fake_wsl, monkeypatch):
    from test_ui import make_window, pump

    app, window = make_window(fake_wsl, monkeypatch)
    pump(app, lambda: window.worker is None and bool(window.inventory), 15)

    window.fill(window.resolution_table, [("p", "1", "r", "1 Mio", "Demandé")])
    window.fill(window.checks_table, [("t", "t", "Présent")])
    window.verification_log.setPlainText("sortie Debian")
    window.results_family = "Debian 13"

    window.change_family("Fedora")

    assert window.resolution_table.rowCount() == 0
    assert window.checks_table.rowCount() == 0
    assert window.verification_log.toPlainText() == ""
    assert "Fedora" in window.packages_group.title()
    assert "dnf5" in window.log_group.title()
    assert "Fedora" in window.context_label.text()

    window.fill(window.resolution_table, [("p", "1", "r", "1 Mio", "Demandé")])
    window.results_family = "Fedora 44"
    window.release.setCurrentIndex(max(0, window.release.count() - 1))
    window.invalidate()
    assert "obsolète" in window.resolution_group.title()

    window.change_family("Gentoo")
    assert window.build_button.isEnabled()
    window.close()
