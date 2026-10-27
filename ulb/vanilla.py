"""Option « Bureau vanille » : le bureau tel que le conçoivent ses
développeurs (upstream), sans méta-paquet de distribution ni applications
ajoutées.

Concrètement : au lieu du méta-paquet habituel (par exemple `gnome-core`,
`kde-plasma-desktop`, `xfce4`, qui tirent aussi des applications et des
réglages choisis par la distribution), on installe seulement la session,
le gestionnaire de connexion, le gestionnaire de fichiers et les réglages.
Limites : un paquet de marque de la distribution (thème, fond d'écran)
peut rester s'il est exigé par une dépendance ; les noms de paquets sont
validés par « Analyser les paquets », pas ici.
"""

from .constants import BUILD_FAMILIES, DESKTOPS

VANILLA_DESKTOPS = {
    "Debian": {
        "GNOME": [
            "gnome-shell", "gnome-session", "gdm3", "nautilus",
            "gnome-control-center"
        ],
        "KDE Plasma": ["plasma-desktop", "sddm", "dolphin"],
        "Xfce": [
            "xfce4-session", "xfce4-panel", "xfdesktop4", "xfwm4",
            "xfce4-settings", "thunar", "lightdm", "lightdm-gtk-greeter"
        ]
    },
    "Fedora": {
        "GNOME": [
            "gnome-shell", "gnome-session", "gdm", "nautilus",
            "gnome-control-center"
        ],
        "KDE Plasma": ["plasma-desktop", "sddm", "dolphin"],
        "Xfce": [
            "xfce4-session", "xfce4-panel", "xfdesktop", "xfwm4",
            "xfce4-settings", "Thunar"
        ]
    },
    "Arch Linux": {
        "GNOME": [
            "gnome-shell", "gnome-session", "gdm", "nautilus",
            "gnome-control-center"
        ],
        "KDE Plasma": ["plasma-desktop", "sddm", "dolphin"],
        "Xfce": [
            "xfce4-session", "xfce4-panel", "xfdesktop", "xfwm4",
            "xfce4-settings", "thunar", "lightdm", "lightdm-gtk-greeter"
        ]
    }
}


def vanilla_supported(family, desktop):
    """Budgie est déjà installé en paquets unitaires : rien à retirer."""

    return (
        family in BUILD_FAMILIES
        and desktop in VANILLA_DESKTOPS.get(family, {})
    )


def desktop_packages(family, desktop, vanilla=False):
    """Paquets du bureau : liste habituelle, ou liste vanille."""

    if vanilla and vanilla_supported(family, desktop):
        return list(VANILLA_DESKTOPS[family][desktop])

    return list(DESKTOPS[family].get(desktop, []))


def vanilla_note(family, desktop):
    """Texte d'aide : ce que fait l'option pour ce choix."""

    if family not in BUILD_FAMILIES:
        return (
            "Indisponible : " + family + " n'est pas construit ici "
            "(remaster d'une ISO officielle)."
        )

    if desktop in ("", "Aucun"):
        return "Indisponible : aucun bureau choisi."

    if desktop not in VANILLA_DESKTOPS.get(family, {}):
        return (
            desktop + " est déjà installé en paquets unitaires : "
            "l'option ne change rien."
        )

    usual = ", ".join(DESKTOPS[family].get(desktop, [])) or "aucun"
    vanilla = ", ".join(VANILLA_DESKTOPS[family][desktop])

    return (
        "Remplace « " + usual + " » par : " + vanilla + ". "
        "Pas d'applications ni de réglages de la distribution ajoutés."
    )
