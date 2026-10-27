from pathlib import Path
import os
import re


VERSION = "2.0.28"

FAMILIES = [
    "Debian",
    "Fedora",
    "Arch Linux",
    "Gentoo",
    "Slackware"
]

RELEASES = {
    "Debian": ["trixie", "bookworm"],
    "Fedora": ["44", "43", "42"],
    "Arch Linux": ["rolling"],
    "Gentoo": ["stable", "testing"],
    "Slackware": ["15.0", "current"]
}

COLORS = {
    "Debian": "#D70A53",
    "Fedora": "#51A2DA",
    "Arch Linux": "#1793D1",
    "Gentoo": "#9482C9",
    "Slackware": "#D0D7E2"
}

LOGOS = {
    "Debian": "debian",
    "Fedora": "fedora",
    "Arch Linux": "archlinux",
    "Gentoo": "gentoo",
    "Slackware": "slackware"
}

MANAGERS = {
    "Debian": "apt",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

MANAGER_BINARY = {
    "Debian": "apt-get",
    "Fedora": "dnf5",
    "Arch Linux": "pacman",
    "Gentoo": "emerge",
    "Slackware": "slackpkg"
}

INSTALLERS = {
    "Debian": "Calamares",
    "Fedora": "Anaconda",
    "Arch Linux": "Calamares",
    "Gentoo": "Installation Gentoo personnalisée",
    "Slackware": "Slackware Setup"
}

# Outils nécessaires dans l'environnement de construction.
# Les paquets sont spécifiques à la distribution WSL.

BUILD_TOOLS = {
    "Debian": [
        ("apt-get", "apt"),
        ("dpkg", "dpkg"),
        ("debootstrap", "debootstrap"),
        ("lb", "live-build"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso"),
        ("grub-mkrescue", "grub-common"),
        ("curl", "curl")
    ],
    "Fedora": [
        ("dnf5", "dnf5"),
        ("rpm", "rpm"),
        ("lorax", "lorax"),
        ("livemedia-creator", "lorax"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "xorriso"),
        ("ksflatten", "pykickstart"),
        # Anaconda l'appelle en fin d'installation (sinon : « No such file
        # or directory: '/usr/sbin/load_policy' » masque la vraie erreur).
        ("load_policy", "policycoreutils"),
        # Kickstarts : paquet des dépôts, ou à défaut clonage git.
        ("rpm:fedora-kickstarts|spin-kickstarts|git", "fedora-kickstarts (ou git)"),
        ("rpm:lorax-lmc-novirt", "lorax-lmc-novirt"),
        ("curl", "curl")
    ],
    "Arch Linux": [
        ("pacman", "pacman"),
        ("mkarchiso", "archiso"),
        ("mksquashfs", "squashfs-tools"),
        ("xorriso", "libisoburn"),
        ("grub-mkrescue", "grub"),
        ("curl", "curl")
    ],
    "Gentoo": [
        ("emerge", "sys-apps/portage"),
        ("equery", "app-portage/gentoolkit"),
        ("mksquashfs", "sys-fs/squashfs-tools"),
        ("xorriso", "app-cdr/libisoburn")
    ],
    "Slackware": [
        ("installpkg", "pkgtools"),
        ("slackpkg", "slackpkg"),
        ("mkisofs", "cdrtools"),
        ("mksquashfs", "squashfs-tools")
    ]
}

# Paquets devant être présents dans le Linux installé.
# Leur existence et leur compatibilité doivent être vérifiées
# avec les dépôts de la version choisie.

TARGET_BASE = {
    "Debian": [
        "linux-image-amd64",
        "systemd-sysv",
        "apt",
        "dpkg",
        "ca-certificates",
        "sudo",
        "network-manager",
        "iproute2",
        "openssh-client"
    ],
    "Fedora": [
        "kernel",
        "systemd",
        "dnf5",
        "rpm",
        "fedora-repos",
        "ca-certificates",
        "sudo",
        "NetworkManager",
        "iproute"
    ],
    "Arch Linux": [
        "base",
        "linux",
        "linux-firmware",
        "pacman",
        "archlinux-keyring",
        "sudo",
        "networkmanager",
        "iproute2",
        "ca-certificates"
    ],
    "Gentoo": [
        "sys-kernel/gentoo-kernel",
        "sys-apps/portage",
        "sys-apps/sudo",
        "net-misc/networkmanager",
        "app-misc/ca-certificates",
        "sys-apps/iproute2"
    ],
    "Slackware": [
        "kernel-generic",
        "kernel-modules",
        "pkgtools",
        "slackpkg",
        "sudo",
        "networkmanager",
        "ca-certificates"
    ]
}

DESKTOPS = {
    "Debian": {
        "Aucun": [],
        "GNOME": ["gnome-core", "gdm3"],
        "KDE Plasma": ["kde-plasma-desktop", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": [
            "budgie-desktop",
            "lightdm",
            "lightdm-gtk-greeter"
        ]
    },
    "Fedora": {
        "Aucun": [],
        "GNOME": ["gnome-shell", "gnome-session", "gdm"],
        "KDE Plasma": ["plasma-desktop", "sddm"],
        "Xfce": ["xfce4-session", "xfce4-panel"],
        "Budgie": [
            "budgie-desktop",
            "lightdm",
            "lightdm-gtk"
        ]
    },
    "Arch Linux": {
        "Aucun": [],
        "GNOME": ["gnome", "gdm"],
        "KDE Plasma": ["plasma", "sddm"],
        "Xfce": ["xfce4", "lightdm"],
        "Budgie": [
            "budgie-desktop",
            "budgie-session",
            "budgie-desktop-services",
            "budgie-control-center",
            "budgie-backgrounds",
            "budgie-desktop-view",
            "lightdm",
            "lightdm-gtk-greeter"
        ]
    },
    "Gentoo": {
        "Aucun": [],
        "GNOME": ["gnome-base/gnome"],
        "KDE Plasma": ["kde-plasma/plasma-meta"],
        "Xfce": ["xfce-base/xfce4-meta"]
    },
    "Slackware": {
        "Aucun": [],
        "KDE Plasma": ["plasma-desktop"],
        "Xfce": ["xfce4-session"]
    }
}

# Paquets ajoutés uniquement à l'image live (installateur graphique).
# Calamares est absent des dépôts officiels d'Arch Linux (AUR).

LIVE_INSTALLER = {
    "Debian": [
        "calamares",
        "calamares-settings-debian"
    ],
    "Fedora": [
        "anaconda",
        "anaconda-live"
    ]
}

# Kickstarts officiels du paquet fedora-kickstarts, un par bureau.
# Leur présence est vérifiée au moment de la construction.

FEDORA_KICKSTARTS = {
    "GNOME": "fedora-live-workstation.ks",
    "KDE Plasma": "fedora-live-kde.ks",
    "Xfce": "fedora-live-xfce.ks",
    "Budgie": "fedora-live-budgie.ks",
    "Aucun": "fedora-live-minimal.ks"
}

# Paquets minimaux exigés par la documentation de livemedia-creator
# pour une ISO live ("-" retire dracut-config-rescue).

FEDORA_LIVE_REQUIRED = [
    "dracut-config-generic",
    "dracut-live",
    "-dracut-config-rescue",
    "grub2-efi-x64",
    "shim-x64",
    "syslinux"
]

# GRUB dans le système installé, selon le mode d'amorçage choisi.
# grub-pc et grub-efi-amd64 sont incompatibles sous Debian :
# une image vise donc UEFI ou BIOS, pas les deux.

GRUB_PACKAGES = {
    "Debian": {
        "UEFI": ["grub-efi-amd64", "efibootmgr"],
        "BIOS": ["grub-pc"]
    },
    "Fedora": {
        "UEFI": [
            "grub2-efi-x64",
            "shim-x64",
            "efibootmgr",
            "grub2-tools"
        ],
        "BIOS": ["grub2-pc", "grub2-tools"]
    },
    "Arch Linux": {
        "UEFI": ["grub", "efibootmgr"],
        "BIOS": ["grub"]
    },
    "Gentoo": {
        "UEFI": ["sys-boot/grub", "sys-boot/efibootmgr"],
        "BIOS": ["sys-boot/grub"]
    }
}

DISPLAY_MANAGERS = {"gdm", "gdm3", "sddm", "lightdm"}

AUDIO = {
    "Debian": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Fedora": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulseaudio"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Arch Linux": {
        "PipeWire": ["pipewire", "wireplumber", "pipewire-pulse"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    },
    "Gentoo": {
        "PipeWire": ["media-video/pipewire"],
        "PulseAudio": ["media-sound/pulseaudio"],
        "ALSA": ["media-sound/alsa-utils"],
        "Aucun": []
    },
    "Slackware": {
        "PipeWire": ["pipewire"],
        "PulseAudio": ["pulseaudio"],
        "ALSA": ["alsa-utils"],
        "Aucun": []
    }
}

EXTRAS = {
    "Debian": {
        "Wi-Fi": ["wpasupplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["firmware-linux-free"],
        "Flathub": ["flatpak"]
    },
    "Fedora": {
        "Wi-Fi": ["NetworkManager-wifi"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Flathub": ["flatpak"]
    },
    "Arch Linux": {
        "Wi-Fi": ["iwd"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["linux-firmware"],
        "Flathub": ["flatpak"]
    },
    "Gentoo": {
        "Wi-Fi": ["net-wireless/iwd"],
        "Bluetooth": ["net-wireless/bluez"],
        "Impression": ["net-print/cups"],
        "Firmware": ["sys-kernel/linux-firmware"],
        "Flathub": ["sys-apps/flatpak"]
    },
    "Slackware": {
        "Wi-Fi": ["wpa_supplicant"],
        "Bluetooth": ["bluez"],
        "Impression": ["cups"],
        "Firmware": ["kernel-firmware"],
        "Flathub": ["flatpak"]
    }
}

SAFE_PACKAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9+_.:/@-]{0,119}$"
)

def settings_file():
    """Fichier de réglages persistants (évalué à l'appel)."""

    return (
        Path(os.environ.get("APPDATA", str(Path.home())))
        / "UniversalLinuxBuilder"
        / "settings.json"
    )


ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)

# Micrologiciels propriétaires (zone non-free-firmware, Debian ≥ 12) :
# indispensables au Wi-Fi et à de nombreux GPU sur du matériel récent.
DEBIAN_FIRMWARE = [
    "firmware-linux",
    "firmware-misc-nonfree",
    "firmware-iwlwifi",
    "firmware-realtek",
    "firmware-atheros"
]

# Espace libre minimal (Go) : (espace de travail WSL, dossier Windows).
REQUIRED_SPACE = {
    "Debian": (10, 4),
    "Fedora": (18, 5),
    "Arch Linux": (12, 4)
}

BUILD_FAMILIES = ("Debian", "Arch Linux", "Fedora")

# Profil « Léger » : valeurs proposées (modifiables ensuite) et
# construction sans paquets « recommandés » (Debian).
PROFILES = ["Standard", "Léger"]

LIGHT_PRESET = {
    "desktop": "Xfce",
    "disabled_options": ["Impression", "Bluetooth"]
}

# Test de démarrage QEMU : paquets à installer dans l'environnement WSL
# (QEMU + firmware UEFI OVMF) et chemins usuels du firmware.
QEMU_PACKAGES = {
    "Debian": ["qemu-system-x86", "ovmf"],
    "Fedora": ["qemu-system-x86-core", "edk2-ovmf"],
    "Arch Linux": ["qemu-system-x86", "edk2-ovmf"]
}

OVMF_CANDIDATES = [
    "/usr/share/OVMF/OVMF_CODE_4M.fd",
    "/usr/share/OVMF/OVMF_CODE.fd",
    "/usr/share/edk2/x64/OVMF_CODE.4m.fd",
    "/usr/share/edk2/x64/OVMF_CODE.fd",
    "/usr/share/edk2/ovmf/OVMF_CODE.fd",
    "/usr/share/qemu/OVMF_CODE.fd"
]

# Machine virtuelle (onglet Virtualisation) : outils à installer dans
# l'environnement WSL. Installés un par un : un nom introuvable n'empêche
# pas les autres.
VM_PACKAGES = {
    "Debian": [
        "qemu-system-x86", "qemu-utils", "qemu-system-gui",
        "ovmf", "novnc"
    ],
    "Fedora": [
        "qemu-system-x86-core", "qemu-img", "qemu-ui-gtk",
        "edk2-ovmf", "novnc"
    ],
    "Arch Linux": ["qemu-desktop", "edk2-ovmf", "novnc"]
}

NOVNC_DIRECTORIES = [
    "/usr/share/novnc",
    "/usr/share/webapps/novnc",
    "/usr/share/noVNC"
]

# RAM (Mo) conseillée pour essayer le système selon le bureau choisi.
VM_RAM = {
    "Aucun": 2048,
    "Xfce": 3072,
    "Budgie": 4096,
    "GNOME": 4096,
    "KDE Plasma": 4096
}

VM_DISPLAYS = ["Web (noVNC)", "Fenêtre (WSLg)", "VNC (client externe)"]
VM_BOOTS = ["ISO (installation)", "Disque (après installation)"]
VM_WORKDIR = "/var/tmp/ulb-vm"

# Flathub : fichier de dépôt officiel, déposé dans /etc/flatpak/remotes.d
# de l'image (flatpak l'ajoute comme dépôt système).
FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
FLATHUB_REMOTE_DIR = "etc/flatpak/remotes.d"

# RPM Fusion (Fedora) : dépôts « libre » et « non libre ».
RPMFUSION_URLS = (
    "https://mirrors.rpmfusion.org/free/fedora/"
    "rpmfusion-free-release-{release}.noarch.rpm",
    "https://mirrors.rpmfusion.org/nonfree/fedora/"
    "rpmfusion-nonfree-release-{release}.noarch.rpm"
)

# Options de l'onglet Système propres à une famille.
FEDORA_THIRD_PARTY = "Dépôts tiers non libres (Fedora)"
