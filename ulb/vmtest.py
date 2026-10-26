"""Test de démarrage automatisé (QEMU headless + capture d'écran).

Ce test prouve seulement que le firmware charge un chargeur d'amorçage
et que quelque chose s'affiche. Il ne valide ni l'installateur, ni
l'installation sur disque, ni Ventoy.
"""

import base64
import shlex
import struct
import zlib
from pathlib import Path

from .constants import OVMF_CANDIDATES, QEMU_PACKAGES
from .wsl import Control, execute, wsl_stream


def qemu_script(iso, mode, wait, workdir, ovmf_candidates=OVMF_CANDIDATES):
    """Script shell : démarre QEMU sans écran, attend `wait`
    secondes, enregistre une capture (shot.ppm) puis quitte."""

    if mode not in ("UEFI", "BIOS"):
        raise ValueError("Mode inconnu : " + mode)

    firmware = ""

    if mode == "UEFI":
        candidates = " ".join(shlex.quote(c) for c in ovmf_candidates)

        firmware = (
            'code=""; for f in ' + candidates + "; do "
            '[ -f "$f" ] && { code="$f"; break; }; done; '
            'test -n "$code" || { '
            'echo "Firmware UEFI (OVMF) introuvable : '
            'installe le paquet ovmf / edk2-ovmf" >&2; exit 3; }; '
        )

    drive = (
        '-drive if=pflash,format=raw,readonly=on,file="$code" '
        if mode == "UEFI"
        else ""
    )

    return (
        "set -eu; "
        "command -v qemu-system-x86_64 >/dev/null || { "
        'echo "qemu-system-x86_64 introuvable" >&2; exit 3; }; '
        "mkdir -p " + shlex.quote(workdir) + "; "
        "cd " + shlex.quote(workdir) + "; "
        "rm -f shot.ppm serial.log; "
        + firmware
        + "accel=tcg; "
        "if [ -w /dev/kvm ]; then accel=kvm:tcg; fi; "
        "( sleep " + str(int(wait)) + "; "
        "echo 'screendump shot.ppm'; sleep 3; echo quit ) | "
        "qemu-system-x86_64 -machine accel=$accel -m 2048 -smp 2 "
        + drive
        + "-cdrom " + shlex.quote(iso) + " -boot d "
        "-vga std -display none -monitor stdio "
        "-serial file:serial.log -no-reboot"
    )


def read_ppm(data):
    """Décode un PPM P6 binaire → (largeur, hauteur, octets RGB)."""

    if not data.startswith(b"P6"):
        raise ValueError("Capture non reconnue (PPM P6 attendu).")

    tokens = []
    position = 2

    while len(tokens) < 3:
        while data[position:position + 1].isspace():
            position += 1

        if data[position:position + 1] == b"#":
            while data[position:position + 1] != b"\n":
                position += 1

            continue

        start = position

        while not data[position:position + 1].isspace():
            position += 1

        tokens.append(int(data[start:position]))

    width, height, maximum = tokens

    if maximum != 255:
        raise ValueError("Profondeur de couleur non gérée.")

    pixels = data[position + 1:position + 1 + width * height * 3]

    if len(pixels) != width * height * 3:
        raise ValueError("Capture tronquée.")

    return width, height, pixels


def write_png(path, width, height, rgb):
    def chunk(kind, payload):
        body = kind + payload

        return (
            struct.pack(">I", len(payload))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    stride = width * 3
    raw = b"".join(
        b"\x00" + rgb[row * stride:(row + 1) * stride]
        for row in range(height)
    )

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def analyse_screen(width, height, rgb):
    """Statistiques simples : part de pixels non noirs, nombre de
    couleurs distinctes (échantillonné)."""

    total = width * height
    step = max(1, total // 20000)
    sampled = 0
    lit = 0
    colors = set()

    for index in range(0, total, step):
        offset = index * 3
        r, g, b = rgb[offset], rgb[offset + 1], rgb[offset + 2]
        sampled += 1

        if r + g + b > 30:
            lit += 1

        colors.add((r >> 4, g >> 4, b >> 4))

    ratio = lit / sampled if sampled else 0

    return {
        "width": width,
        "height": height,
        "lit_ratio": round(ratio, 4),
        "colors": len(colors),
        "blank": ratio < 0.005 or len(colors) <= 2
    }


def vm_tools_missing(env, family):
    output, error, code = execute(
        env,
        "command -v qemu-system-x86_64 >/dev/null && echo qemu:OK "
        "|| echo qemu:ABSENT; "
        "for f in " + " ".join(shlex.quote(c) for c in OVMF_CANDIDATES)
        + "; do [ -f \"$f\" ] && { echo ovmf:OK; exit 0; }; done; "
        "echo ovmf:ABSENT",
        60
    )

    missing = []

    if "qemu:ABSENT" in output:
        missing.append("QEMU")

    if "ovmf:ABSENT" in output:
        missing.append("OVMF (UEFI)")

    return missing, QEMU_PACKAGES.get(family, [])


def windows_to_wsl_path(env, path):
    output, error, code = execute(
        env,
        "wslpath -a " + shlex.quote(str(path)),
        30
    )

    if code or not output.strip():
        raise RuntimeError(
            "Chemin illisible dans WSL : " + (error or output)
        )

    return output.strip().splitlines()[-1]


def boot_test(env, family, iso, mode, wait, directory, control=None):
    """Démarre l'ISO dans QEMU et retourne un verdict + capture PNG."""

    control = control or Control()
    iso = Path(iso)

    if not iso.is_file():
        raise RuntimeError("ISO introuvable : " + str(iso))

    missing, packages = vm_tools_missing(env, family)

    if missing and ("QEMU" in missing or mode == "UEFI"):
        raise RuntimeError(
            "Outils manquants dans WSL : "
            + ", ".join(missing)
            + ". Paquets à installer : "
            + ", ".join(packages)
        )

    wsl_iso = windows_to_wsl_path(env, iso)
    workdir = "/var/tmp/ulb-vmtest-" + mode.lower()

    control.log(
        "== Démarrage QEMU (" + mode + "), capture après "
        + str(int(wait)) + " s =="
    )

    control.progress(None)

    output, code = wsl_stream(
        env,
        qemu_script(wsl_iso, mode, wait, workdir),
        control,
        int(wait) + 120,
        root=True
    )

    if code:
        raise RuntimeError(
            "QEMU a échoué (code " + str(code) + ").\n" + output[-800:]
        )

    control.check()

    data, error, status = execute(
        env,
        "base64 -w0 " + shlex.quote(workdir + "/shot.ppm"),
        120,
        root=True
    )

    if status or not data.strip():
        raise RuntimeError("Aucune capture d'écran produite.")

    width, height, rgb = read_ppm(base64.b64decode(data.strip()))

    destination = Path(directory) / ("boot_test_" + mode.lower() + ".png")
    write_png(destination, width, height, rgb)

    stats = analyse_screen(width, height, rgb)

    serial, error, status = execute(
        env,
        "tail -n 20 " + shlex.quote(workdir + "/serial.log") + " 2>/dev/null",
        30,
        root=True
    )

    stats.update({
        "mode": mode,
        "wait": int(wait),
        "screenshot": str(destination),
        "verdict": (
            "Écran noir ou vide : démarrage probablement échoué"
            if stats["blank"]
            else "Un écran s'affiche (chargeur d'amorçage ou système)"
        ),
        "serial_tail": serial
    })

    execute(env, "rm -rf -- " + shlex.quote(workdir), 60, root=True)

    return stats
