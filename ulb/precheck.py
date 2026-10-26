"""Paquets indispensables à une ISO live qui démarre vraiment, et
contrôle de l'image après construction.

Pourquoi : plusieurs paquets vitaux ne sont que « recommandés » par
Debian (user-setup, sudo, locales, keyboard-configuration, live-tools,
serveur X). Avec `--apt-recommends false` ils manquent, et l'image
démarre sans utilisateur (« Authentication failure » en connexion
automatique) ou sans interface graphique. On les nomme donc
explicitement, puis on vérifie dans le chroot que tout est installé.
"""

# live-config ne crée l'utilisateur « user » que si user-setup est
# installé (composant 0030-user-setup : « if ! pkg_is_installed
# user-setup ... exit 0 »). Les autres sont des Recommends de live-config.
DEBIAN_LIVE_ESSENTIAL = [
    "live-boot",
    "live-config",
    "live-config-systemd",
    "live-tools",
    "user-setup",
    "sudo",
    "locales",
    "keyboard-configuration",
    "systemd-sysv",
    "dbus",
    "network-manager",
    "iproute2"
]

# Serveur graphique : simples « Recommends » des bureaux.
DEBIAN_GRAPHICAL_ESSENTIAL = [
    "xserver-xorg",
    "xserver-xorg-input-libinput",
    "xserver-xorg-video-all",
    "x11-xserver-utils"
]

# Un gestionnaire de connexion a besoin d'un greeter (Recommends).
GREETERS = {"lightdm": "lightdm-gtk-greeter"}


def live_essentials(family, desktop, packages):
    """Paquets à ajouter à l'image live en plus de la sélection."""

    if family != "Debian":
        return []

    names = set(packages)
    extra = list(DEBIAN_LIVE_ESSENTIAL)

    if desktop and desktop != "Aucun":
        extra += DEBIAN_GRAPHICAL_ESSENTIAL

        for manager, greeter in GREETERS.items():
            if manager in names:
                extra.append(greeter)

    return sorted(set(extra) - names)


def debian_postcheck(packages):
    """Fragment sh : vérifie que chaque paquet demandé est installé
    dans le chroot de live-build ; échoue (code 4) sinon."""

    from .builders import quote_all

    return (
        'if [ -d chroot/var/lib/dpkg ]; then miss=""; '
        "for p in " + quote_all(sorted(set(packages))) + "; do "
        "s=$(dpkg-query --admindir=chroot/var/lib/dpkg -W "
        "-f='${db:Status-Abbrev}' \"$p\" 2>/dev/null || true); "
        '[ "$s" = "ii " ] || miss="$miss $p"; done; '
        'if [ -n "$miss" ]; then '
        'echo "ULB: ISO INCOMPLÈTE, paquets absents du chroot :$miss" '
        ">&2; exit 4; fi; "
        'echo "ULB: paquets de l\'image vérifiés dans le chroot"; '
        'else echo "ULB: chroot introuvable, vérification impossible"; fi'
    )


def precheck_rows(family, desktop, packages):
    """Lignes (élément, état, remarque) pour la chaîne d'installation."""

    if family != "Debian":
        return []

    names = set(packages)
    rows = []

    missing = [n for n in DEBIAN_LIVE_ESSENTIAL if n not in names]

    rows.append((
        "Session live (utilisateur, sudo, clavier)",
        "Inclus",
        "user-setup, live-config, sudo… ajoutés explicitement "
        "(sinon aucun utilisateur live n'est créé)."
        if missing
        else "Présents dans la sélection."
    ))

    if desktop and desktop != "Aucun":
        rows.append((
            "Serveur graphique (Xorg, pilotes, libinput)",
            "Inclus",
            "Ajouté explicitement : simple « recommandation » "
            "des bureaux."
        ))

    rows.append((
        "Contrôle après construction",
        "Automatique",
        "Chaque paquet demandé est vérifié dans le chroot ; "
        "la construction échoue si l'un manque."
    ))

    return rows
