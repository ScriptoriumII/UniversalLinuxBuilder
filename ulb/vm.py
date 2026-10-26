"""Machine virtuelle QEMU/KVM pour essayer l'image avant de graver
ou d'installer : démarrage sur l'ISO, installation sur un disque
virtuel persistant, puis démarrage sur ce disque (GRUB).

Affichage : fenêtre WSLg, page web noVNC ou client VNC externe.
"""

import shlex

from .constants import (
    NOVNC_DIRECTORIES,
    OVMF_CANDIDATES,
    VM_PACKAGES,
    VM_WORKDIR
)
from .wsl import Control, execute, stream

WEB_PORT = 6080
WEBSOCKET_PORT = 5700
VNC_PORT = 5900
URL_MARKER = "ULB_URL "
INFO_MARKER = "ULB_INFO "


def vm_script(
    vm_id,
    iso,
    mode,
    boot,
    ram,
    cpus,
    disk_gb,
    display,
    ovmf_candidates=OVMF_CANDIDATES
):
    """Script sh qui prépare disque, firmware UEFI et affichage puis
    lance QEMU au premier plan."""

    if mode not in ("UEFI", "BIOS"):
        raise ValueError("Mode inconnu : " + mode)

    if boot not in ("iso", "disk"):
        raise ValueError("Démarrage inconnu : " + boot)

    if display not in ("web", "window", "vnc"):
        raise ValueError("Affichage inconnu : " + display)

    ram = int(ram)
    cpus = int(cpus)
    disk_gb = int(disk_gb)

    if ram < 512 or cpus < 1 or disk_gb < 4:
        raise ValueError("Paramètres de machine invalides.")

    work = shlex.quote(VM_WORKDIR)
    parts = [
        "set -eu",
        "mkdir -p " + work,
        "cd " + work,
        # accélération : KVM si disponible, sinon émulation lente
        "accel=tcg; cpu=max",
        "if [ -w /dev/kvm ]; then accel=kvm; cpu=host; "
        'else echo "Attention : KVM indisponible, émulation lente '
        '(active la virtualisation imbriquée de WSL)"; fi',
        "command -v qemu-system-x86_64 >/dev/null || { "
        'echo "qemu-system-x86_64 introuvable : '
        'installe les outils de virtualisation" >&2; exit 3; }',
        "if [ ! -f disk.qcow2 ]; then "
        "qemu-img create -f qcow2 disk.qcow2 " + str(disk_gb) + "G; fi"
    ]

    args = [
        "-name ulb-vm-" + vm_id,
        "-machine q35,accel=$accel",
        "-cpu $cpu",
        "-smp " + str(cpus),
        "-m " + str(ram),
        "-device virtio-vga",
        "-device qemu-xhci -device usb-tablet",
        "-device virtio-rng-pci",
        "-netdev user,id=n0 -device virtio-net-pci,netdev=n0",
        "-drive file=disk.qcow2,if=virtio,format=qcow2,"
        "cache=writeback"
    ]

    if mode == "UEFI":
        candidates = " ".join(shlex.quote(c) for c in ovmf_candidates)

        parts.append(
            'code=""; for f in ' + candidates + "; do "
            '[ -f "$f" ] && { code="$f"; break; }; done; '
            'test -n "$code" || { echo "Firmware UEFI (OVMF) '
            'introuvable : installe ovmf / edk2-ovmf" >&2; exit 3; }; '
            # variables UEFI persistantes : les entrées de démarrage
            # créées par GRUB survivent entre deux lancements
            'vars=$(echo "$code" | sed "s/CODE/VARS/"); '
            'test -f "$vars" || { echo "Fichier VARS introuvable : '
            '$vars" >&2; exit 3; }; '
            '[ -f OVMF_VARS.fd ] || cp "$vars" OVMF_VARS.fd'
        )

        args += [
            "-drive if=pflash,format=raw,unit=0,readonly=on,"
            'file="$code"',
            "-drive if=pflash,format=raw,unit=1,file=OVMF_VARS.fd"
        ]

    if boot == "iso":
        args += [
            "-cdrom " + shlex.quote(iso),
            "-boot order=dc"
        ]

    else:
        args.append("-boot order=c")

    if display == "window":
        args.append("-display gtk,gl=off")

    elif display == "web":
        directories = " ".join(shlex.quote(d) for d in NOVNC_DIRECTORIES)

        parts.append(
            'nv=""; for d in ' + directories + " " + shlex.quote(
                VM_WORKDIR + "/noVNC"
            ) + "; do "
            '[ -f "$d/vnc.html" ] && { nv="$d"; break; }; done; '
            # paquet absent : copie officielle de noVNC (git)
            'if [ -z "$nv" ] && command -v git >/dev/null; then '
            'echo "' + INFO_MARKER + 'noVNC absent : téléchargement '
            'depuis GitHub..."; '
            "git clone --depth 1 https://github.com/novnc/noVNC.git "
            + shlex.quote(VM_WORKDIR + "/noVNC")
            + " >/dev/null 2>&1 && nv=" + shlex.quote(VM_WORKDIR + "/noVNC")
            + "; fi; "
            'test -n "$nv" || { echo "noVNC introuvable : clique sur '
            "« Installer QEMU / noVNC » ou choisis un autre "
            'affichage" >&2; exit 3; }; '
            'command -v python3 >/dev/null || { echo "python3 '
            'introuvable (serveur web noVNC)" >&2; exit 3; }; '
            "python3 -m http.server " + str(WEB_PORT)
            + ' --bind 127.0.0.1 --directory "$nv" '
            ">/dev/null 2>&1 & "
            "web=$!"
        )

        args += [
            "-display none",
            "-vnc 127.0.0.1:0,websocket=" + str(WEBSOCKET_PORT)
        ]

    else:
        parts.append(
            'echo "' + INFO_MARKER + "Client VNC : localhost:"
            + str(VNC_PORT) + " (TigerVNC, RealVNC, TightVNC...). "
            "Sans client VNC, choisis « Web (noVNC) »" + '"'
        )

        args += ["-display none", "-vnc 127.0.0.1:0"]

    # QEMU en arrière-plan : on vérifie qu'il démarre vraiment et que
    # l'affichage répond avant d'annoncer l'adresse.
    port = WEBSOCKET_PORT if display == "web" else VNC_PORT

    parts.append(
        "qemu-system-x86_64 " + " ".join(args)
        + " & qpid=$!; "
        "trap 'kill $qpid ${web:-} 2>/dev/null' EXIT INT TERM"
    )

    if display == "window":
        parts.append(
            'if [ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then '
            'echo "' + INFO_MARKER + "Pas d'affichage WSLg détecté : "
            'choisis « Web (noVNC) » si aucune fenêtre ne s ouvre"; fi'
        )

    else:
        parts.append(
            "ready=0; n=0; while [ $n -lt 30 ]; do "
            "kill -0 $qpid 2>/dev/null || break; "
            "if python3 -c \"import socket;"
            "socket.create_connection(('127.0.0.1'," + str(port)
            + "),1)\" 2>/dev/null; then ready=1; break; fi; "
            "n=$((n+1)); sleep 1; done; "
            'if [ $ready = 1 ]; then echo "' + INFO_MARKER
            + 'Machine démarrée, affichage prêt."; '
            'else echo "' + INFO_MARKER + "Machine lancée mais "
            "l'affichage ne répond pas encore (voir le journal)."
            '"; fi'
        )

    if display == "web":
        parts.append(
            'echo "' + URL_MARKER + "http://localhost:" + str(WEB_PORT)
            + "/vnc.html?autoconnect=true&resize=scale&host=localhost"
            "&port=" + str(WEBSOCKET_PORT) + '"'
        )

    parts.append("wait $qpid")

    return "; ".join(parts)


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


def run_vm(
    env,
    vm_id,
    iso,
    mode,
    boot,
    ram,
    cpus,
    disk_gb,
    display,
    control=None
):
    """Lance la machine ; retourne quand QEMU se termine.

    L'arrêt se fait par stop_vm() (QEMU vit dans WSL) ; on ne passe pas
    par wsl --terminate, qui couperait toute la distribution."""

    control = control or Control()

    wsl_iso = ""

    if boot == "iso":
        if not iso:
            raise RuntimeError("Choisis une ISO.")

        wsl_iso = windows_to_wsl_path(env, iso)

    script = vm_script(
        vm_id, wsl_iso, mode, boot, ram, cpus, disk_gb, display
    )

    output, code = stream(
        [
            "wsl.exe", "-d", env, "-u", "root",
            "--exec", "/bin/sh", "-lc", script
        ],
        control
    )

    if code and not control.cancelled:
        raise RuntimeError(
            "La machine s'est arrêtée avec le code "
            + str(code)
            + ".\n"
            + output[-800:]
        )

    return code


def stop_vm(env, vm_id):
    execute(
        env,
        # « [n]ame » : le motif ne correspond pas à sa propre ligne
        # de commande (sinon pkill tuerait le shell qui le lance).
        "pkill -f -- " + shlex.quote("-[n]ame ulb-vm-" + vm_id)
        + " || true",
        60,
        root=True
    )

    return True


def reset_vm_disk(env):
    output, error, code = execute(
        env,
        "rm -f " + VM_WORKDIR + "/disk.qcow2 "
        + VM_WORKDIR + "/OVMF_VARS.fd",
        60,
        root=True
    )

    if code:
        raise RuntimeError(error or output)

    return True


def install_vm_tools(env, family, control=None):
    """Installe un à un les paquets de virtualisation."""

    packages = VM_PACKAGES.get(family)

    if not packages:
        raise RuntimeError(
            "Virtualisation non prise en charge pour " + family
        )

    commands = {
        "Debian": "DEBIAN_FRONTEND=noninteractive "
        "apt-get install -y --no-install-recommends ",
        "Fedora": "dnf5 -y install ",
        "Arch Linux": "pacman -S --noconfirm --needed "
    }

    prefix = {
        "Debian": "DEBIAN_FRONTEND=noninteractive apt-get update; ",
        "Fedora": "",
        "Arch Linux": "pacman-key --init; "
        "pacman-key --populate archlinux; pacman -Sy; "
    }[family]

    loop = (
        prefix
        + "for p in " + " ".join(shlex.quote(p) for p in packages)
        + "; do " + commands[family] + '"$p" '
        '|| echo "ÉCHEC : $p"; done'
    )

    output, error, code = execute(
        env, loop, 3600, root=True, control=control
    )

    return loop, (output, error, code)
