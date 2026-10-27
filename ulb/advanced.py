"""Options « Avancé » : langue, clavier, fuseau, utilisateur, chiffrement,
système de fichiers, Secure Boot, pilotes, miroir, dépôts tiers Arch.

Ce module est pur (aucune interface, aucun accès réseau) : il valide les
réglages et produit, pour chaque famille, les paquets et les morceaux de
script à ajouter à la construction. Rien de ceci n'a été validé sur une
vraie construction : l'état de chaque option est exposé par
`advanced_report` pour que l'interface ne promette que ce qui est écrit.
"""

import hashlib
import re
import secrets
import shlex

# ------------------------------------------------------------
# DONNEES
# ------------------------------------------------------------

LOCALES = [
    ("Français (France)", "fr_FR.UTF-8"),
    ("Français (Belgique)", "fr_BE.UTF-8"),
    ("Français (Suisse)", "fr_CH.UTF-8"),
    ("Français (Canada)", "fr_CA.UTF-8"),
    ("English (US)", "en_US.UTF-8"),
    ("English (UK)", "en_GB.UTF-8"),
    ("Deutsch", "de_DE.UTF-8"),
    ("Español", "es_ES.UTF-8"),
    ("Italiano", "it_IT.UTF-8"),
    ("Português (Portugal)", "pt_PT.UTF-8"),
    ("Português (Brasil)", "pt_BR.UTF-8"),
    ("Nederlands", "nl_NL.UTF-8")
]

# Disposition X11 -> (libellé, keymap console Arch)
KEYBOARDS = [
    ("Français (AZERTY)", "fr", "fr"),
    ("Belge", "be", "be-latin1"),
    ("Suisse romande", "ch", "fr_CH"),
    ("Canadien français", "ca", "cf"),
    ("US (QWERTY)", "us", "us"),
    ("UK", "gb", "uk"),
    ("Allemand", "de", "de"),
    ("Espagnol", "es", "es"),
    ("Italien", "it", "it"),
    ("Portugais", "pt", "pt-latin9"),
    ("Brésilien", "br", "br-abnt2"),
    ("Néerlandais", "nl", "nl")
]

TIMEZONES = [
    "Europe/Paris", "Europe/Brussels", "Europe/Zurich", "Europe/Luxembourg",
    "Europe/London", "Europe/Berlin", "Europe/Madrid", "Europe/Rome",
    "Europe/Lisbon", "Europe/Amsterdam", "America/Toronto",
    "America/Montreal", "America/New_York", "America/Chicago",
    "America/Los_Angeles", "America/Sao_Paulo", "Africa/Casablanca",
    "Africa/Algiers", "Africa/Tunis", "Asia/Tokyo", "UTC"
]

FILESYSTEMS = ["ext4", "btrfs", "xfs"]

LOCALE_RE = re.compile(r"^[a-z]{2,3}_[A-Z]{2}\.UTF-8$")
KEYBOARD_RE = re.compile(r"^[a-z]{2,10}$")
TIMEZONE_RE = re.compile(r"^(UTC|[A-Z][A-Za-z_]+(/[A-Za-z0-9_+-]+)+)$")
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")
URL_RE = re.compile(r"^https?://[A-Za-z0-9._~:/@%+=-]+/?$")
# Les URL de dépôt pacman contiennent souvent $repo / $arch (écrits entre
# apostrophes dans les scripts : aucune expansion).
REPO_URL_RE = re.compile(r"^https?://[A-Za-z0-9._~:/@%+=$-]+/?$")
REPO_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,30}$")
AUR_RE = re.compile(r"^[A-Za-z0-9@._+-]{1,80}$")

RESERVED_USERS = {
    "root", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail",
    "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "nobody",
    "ulbbuild"
}

SIGLEVELS = ["Optional TrustAll", "Never", "Required DatabaseOptional"]

DEFAULTS = {
    "enabled": False,
    "locale": "fr_FR.UTF-8",
    "keyboard": "fr",
    "timezone": "Europe/Paris",
    "hostname": "",
    "username": "",
    "persistence": False,
    "persistence_mb": 4096,
    "luks": False,
    "filesystem": "ext4",
    "snapshots": False,
    "secureboot": False,
    "proprietary": False,
    "mirror": "",
    "proxy": "",
    "aur": False,
    "aur_packages": [],
    "repos": []
}


def normalize(data):
    """Complète et nettoie un dictionnaire de réglages (valeurs inconnues
    ignorées). Le mot de passe n'en fait jamais partie."""

    result = dict(DEFAULTS)

    if isinstance(data, dict):
        for key, default in DEFAULTS.items():
            value = data.get(key, default)

            if isinstance(default, bool):
                result[key] = bool(value)

            elif isinstance(default, int):
                try:
                    result[key] = int(value)

                except (TypeError, ValueError):
                    result[key] = default

            elif isinstance(default, list):
                result[key] = [
                    str(item) for item in value
                ] if isinstance(value, list) else []

            else:
                result[key] = str(value).strip() if value is not None \
                    else default

    return result


def keymap_for(layout):
    for _, code, console in KEYBOARDS:
        if code == layout:
            return console

    return layout


def parse_repo(line):
    """« nom|URL|SigLevel » -> (nom, url, siglevel) ou None."""

    parts = [part.strip() for part in line.split("|")]

    if len(parts) not in (2, 3):
        return None

    name, url = parts[0], parts[1]
    sig = parts[2] if len(parts) == 3 and parts[2] else SIGLEVELS[0]

    if (
        not REPO_NAME_RE.match(name)
        or not REPO_URL_RE.match(url)
        or sig not in SIGLEVELS
    ):
        return None

    return name, url, sig


def validate(family, data, password=""):
    """Liste de messages d'erreur (vide si tout est valide)."""

    adv = normalize(data)
    errors = []

    if not adv["enabled"]:
        return errors

    if not LOCALE_RE.match(adv["locale"]):
        errors.append("Langue invalide : " + adv["locale"])

    if not KEYBOARD_RE.match(adv["keyboard"]):
        errors.append("Clavier invalide : " + adv["keyboard"])

    if not TIMEZONE_RE.match(adv["timezone"]):
        errors.append("Fuseau horaire invalide : " + adv["timezone"])

    if adv["hostname"] and not HOSTNAME_RE.match(adv["hostname"]):
        errors.append(
            "Nom d'hôte invalide (lettres, chiffres, tirets, 63 max)."
        )

    if adv["username"]:
        if not USERNAME_RE.match(adv["username"]):
            errors.append(
                "Nom d'utilisateur invalide (minuscules, chiffres, - et _)."
            )

        elif adv["username"] in RESERVED_USERS:
            errors.append("Nom d'utilisateur réservé : " + adv["username"])

    if password and not adv["username"] and family != "Fedora":
        errors.append(
            "Un mot de passe demande aussi un nom d'utilisateur."
        )

    if password and (
        "\n" in password or "\r" in password or len(password) > 128
    ):
        errors.append("Mot de passe invalide (une ligne, 128 max).")

    if adv["filesystem"] not in FILESYSTEMS:
        errors.append("Système de fichiers invalide.")

    if adv["persistence"] and not 256 <= adv["persistence_mb"] <= 262144:
        errors.append("Taille de persistance invalide (256 Mo à 256 Go).")

    for key in ("mirror", "proxy"):
        if adv[key] and not URL_RE.match(adv[key]):
            errors.append(
                ("Miroir" if key == "mirror" else "Proxy")
                + " invalide : http(s)://hote/chemin, sans espace."
            )

    if adv["aur"] or adv["repos"]:
        if family != "Arch Linux":
            errors.append(
                "Les dépôts tiers (AUR, dépôts pacman) ne concernent "
                "qu'Arch Linux."
            )

    for name in adv["aur_packages"]:
        if not AUR_RE.match(name):
            errors.append("Paquet AUR invalide : " + name)

    for line in adv["repos"]:
        if parse_repo(line) is None:
            errors.append(
                "Dépôt pacman invalide (nom|http(s)://…|SigLevel) : "
                + line
            )

    return errors


# ------------------------------------------------------------
# MOT DE PASSE : SHA-512 crypt ($6$), sans dépendance
# ------------------------------------------------------------

_B64 = (
    "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

_ORDER = [
    (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4),
    (47, 5, 26), (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51),
    (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
    (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19),
    (62, 20, 41)
]


def _b64(b2, b1, b0, count):
    word = (b2 << 16) | (b1 << 8) | b0
    out = ""

    for _ in range(count):
        out += _B64[word & 0x3F]
        word >>= 6

    return out


def sha512_crypt(password, salt=None, rounds=5000):
    """Empreinte `$6$salt$…` compatible avec crypt(3) / chpasswd -e."""

    if salt is None:
        salt = "".join(secrets.choice(_B64) for _ in range(16))

    salt = salt[:16]
    pw = password.encode("utf-8")
    sb = salt.encode("ascii")
    plen = len(pw)

    b = hashlib.sha512(pw + sb + pw).digest()
    a = hashlib.sha512()
    a.update(pw + sb)
    a.update(b * (plen // 64) + b[:plen % 64])

    i = plen

    while i:
        a.update(b if i & 1 else pw)
        i >>= 1

    ad = a.digest()

    dp = hashlib.sha512(pw * plen).digest()
    p = dp * (plen // 64) + dp[:plen % 64]

    ds = hashlib.sha512(sb * (16 + ad[0])).digest()
    s = ds * (len(sb) // 64) + ds[:len(sb) % 64]

    c = ad

    for r in range(rounds):
        h = hashlib.sha512()
        h.update(p if r & 1 else c)

        if r % 3:
            h.update(s)

        if r % 7:
            h.update(p)

        h.update(c if r & 1 else p)
        c = h.digest()

    encoded = "".join(
        _b64(c[x], c[y], c[z], 4) for x, y, z in _ORDER
    ) + _b64(0, 0, c[63], 2)

    return "$6$" + salt + "$" + encoded


# ------------------------------------------------------------
# OUTILS DE SCRIPT
# ------------------------------------------------------------

def write_file(path, lines, mode=None):
    """Commande sh qui écrit `lines` dans `path` (dossiers créés)."""

    directory = path.rsplit("/", 1)[0] if "/" in path else "."

    return (
        "mkdir -p " + shlex.quote(directory) + " && printf '%s\\n' "
        + " ".join(shlex.quote(line) for line in lines)
        + " > " + shlex.quote(path)
        + (
            " && chmod " + mode + " " + shlex.quote(path)
            if mode else ""
        )
    )


def append_file(path, lines):
    directory = path.rsplit("/", 1)[0] if "/" in path else "."

    return (
        "mkdir -p " + shlex.quote(directory) + " && printf '%s\\n' "
        + " ".join(shlex.quote(line) for line in lines)
        + " >> " + shlex.quote(path)
    )


def joined(commands):
    return "; ".join(command for command in commands if command)


def region_zone(timezone):
    if "/" in timezone:
        region, zone = timezone.split("/", 1)
        return region, zone

    return timezone, ""


# ------------------------------------------------------------
# DEBIAN (live-build + live-config + Calamares)
# ------------------------------------------------------------

def debian_extras(adv, password=""):
    """{"packages", "config" (arguments lb config), "nonfree", "setup"}."""

    adv = normalize(adv)
    packages = []
    config = []
    setup = []
    nonfree = False

    if not adv["enabled"]:
        return {
            "packages": packages, "config": config,
            "nonfree": nonfree, "setup": ""
        }

    packages += ["locales", "keyboard-configuration", "console-setup"]

    boot = [
        "boot=live", "components", "quiet", "splash",
        "locales=" + adv["locale"],
        "keyboard-layouts=" + adv["keyboard"],
        "timezone=" + adv["timezone"]
    ]

    if adv["hostname"]:
        boot.append("hostname=" + adv["hostname"])

    if adv["username"]:
        boot += [
            "username=" + adv["username"],
            "user-fullname=" + adv["username"]
        ]

    if adv["persistence"]:
        boot.append("persistence")

    config.append("--bootappend-live " + shlex.quote(" ".join(boot)))

    if adv["mirror"]:
        mirror = shlex.quote(adv["mirror"])
        config += [
            "--mirror-bootstrap " + mirror,
            "--mirror-chroot " + mirror,
            "--mirror-binary " + mirror
        ]

    if adv["proxy"]:
        config.append("--apt-http-proxy " + shlex.quote(adv["proxy"]))

    if adv["secureboot"]:
        packages += ["shim-signed", "grub-efi-amd64-signed", "mokutil"]

    if adv["proprietary"]:
        nonfree = True
        packages += [
            "nvidia-driver", "gstreamer1.0-libav",
            "gstreamer1.0-plugins-ugly", "libavcodec-extra"
        ]

    if adv["luks"]:
        packages += ["cryptsetup", "cryptsetup-initramfs"]

    if adv["filesystem"] == "btrfs":
        packages.append("btrfs-progs")

        if adv["snapshots"]:
            packages.append("snapper")

    elif adv["filesystem"] == "xfs":
        packages.append("xfsprogs")

    # Réglages de Calamares : appliqués par un hook exécuté dans le chroot
    # une fois les paquets installés (calamares-settings-debian en place).
    region, zone = region_zone(adv["timezone"])

    hook = [
        "#!/bin/sh",
        "set -e",
        "setkey() {",
        '  f="$1"; k="$2"; v="$3"',
        '  mkdir -p "$(dirname "$f")"; touch "$f"',
        '  sed -i "/^$k:/d" "$f"',
        "  printf '%s: %s\\n' \"$k\" \"$v\" >> \"$f\"",
        "}",
        "d=/etc/calamares/modules",
        "setkey $d/partition.conf defaultFileSystemType "
        + shlex.quote('"' + adv["filesystem"] + '"'),
        "setkey $d/partition.conf enableLuksAutomatedPartitioning "
        + ("true" if adv["luks"] else "false"),
        "setkey $d/locale.conf region " + shlex.quote('"' + region + '"'),
    ]

    if zone:
        hook.append(
            "setkey $d/locale.conf zone " + shlex.quote('"' + zone + '"')
        )

    setup.append(write_file(
        "config/hooks/live/0100-ulb-advanced.hook.chroot", hook, "755"
    ))

    # Mot de passe du compte live : script live-config exécuté après la
    # création de l'utilisateur.
    if password:
        digest = sha512_crypt(password)
        user = adv["username"]

        script = [
            "#!/bin/sh",
            ". /lib/live/config.sh",
            "## live-config(7) - mot de passe du compte live (ULB)",
            "Init ()",
            "{",
            '  echo -n " ulb-password"',
            "}",
            "Config ()",
            "{",
            "  printf '%s:%s\\n' "
            + shlex.quote(user) + " " + shlex.quote(digest)
            + " | chpasswd -e",
            "}",
            "Init",
            "Config"
        ]

        setup.append(write_file(
            "config/includes.chroot/lib/live/config/0035-ulb-password",
            script, "755"
        ))

    return {
        "packages": packages, "config": config,
        "nonfree": nonfree, "setup": joined(setup)
    }


# ------------------------------------------------------------
# FEDORA (kickstart + Anaconda)
# ------------------------------------------------------------

RPMFUSION_REPOS = [
    (
        "rpmfusion-free",
        "https://mirrors.rpmfusion.org/mirrorlist"
        "?repo=free-fedora-{release}&arch=x86_64"
    ),
    (
        "rpmfusion-nonfree",
        "https://mirrors.rpmfusion.org/mirrorlist"
        "?repo=nonfree-fedora-{release}&arch=x86_64"
    )
]


def fedora_extras(release, adv, password=""):
    """{"packages", "head" (commandes kickstart avant %packages),
    "post" (lignes %post), "lmc" (arguments livemedia-creator)}."""

    adv = normalize(adv)
    out = {"packages": [], "head": [], "post": [], "lmc": []}

    if not adv["enabled"]:
        return out

    out["head"] += [
        "lang " + adv["locale"],
        "keyboard --xlayouts='" + adv["keyboard"] + "' --vckeymap="
        + keymap_for(adv["keyboard"]),
        "timezone " + adv["timezone"] + " --utc"
    ]

    if adv["hostname"]:
        out["head"].append("network --hostname=" + adv["hostname"])

    if adv["mirror"]:
        out["head"].append(
            "repo --name=fedora --baseurl=" + adv["mirror"]
        )

    if adv["proxy"]:
        out["lmc"] += ["--proxy", adv["proxy"]]

    if adv["proprietary"]:
        for name, url in RPMFUSION_REPOS:
            out["head"].append(
                "repo --name=" + name + " --mirrorlist="
                + url.format(release=release)
            )

        out["packages"] += [
            "akmod-nvidia", "xorg-x11-drv-nvidia",
            "gstreamer1-plugins-bad-freeworld",
            "gstreamer1-plugins-ugly", "gstreamer1-libav"
        ]

    if adv["secureboot"]:
        out["packages"] += ["shim-x64", "grub2-efi-x64", "mokutil"]

    if adv["luks"]:
        out["packages"].append("cryptsetup")

    if adv["filesystem"] == "btrfs":
        out["packages"].append("btrfs-progs")

        if adv["snapshots"]:
            out["packages"].append("snapper")

    elif adv["filesystem"] == "xfs":
        out["packages"].append("xfsprogs")

    scheme = "BTRFS" if adv["filesystem"] == "btrfs" else "LVM"

    out["post"] += [
        "mkdir -p /etc/anaconda/conf.d",
        "cat > /etc/anaconda/conf.d/90-ulb.conf <<'ULB_EOF'",
        "[Storage]",
        "default_scheme = " + scheme
    ]

    if adv["filesystem"] != "btrfs":
        out["post"].append("file_system_type = " + adv["filesystem"])

    out["post"].append("ULB_EOF")

    if password:
        out["post"].append(
            "usermod -p " + shlex.quote(sha512_crypt(password))
            + " liveuser || echo 'ULB: liveuser absent'"
        )

    return out


# ------------------------------------------------------------
# ARCH LINUX (archiso)
# ------------------------------------------------------------

def arch_nvidia(kernel_package):
    if kernel_package == "linux":
        return ["nvidia", "nvidia-utils"]

    if kernel_package == "linux-lts":
        return ["nvidia-lts", "nvidia-utils"]

    return ["nvidia-dkms", "nvidia-utils", kernel_package + "-headers"]


def arch_extras(adv, kernel_package="linux", password="", workspace="."):
    """{"packages", "setup" (script avant mkarchiso), "env"}.

    `setup` s'exécute dans le dossier de travail (profile/ présent)."""

    adv = normalize(adv)
    out = {"packages": [], "setup": "", "env": ""}

    if not adv["enabled"]:
        return out

    root = "profile/airootfs"
    setup = []

    setup.append(append_file(
        root + "/etc/locale.gen", [adv["locale"] + " UTF-8"]
    ))
    setup.append(write_file(
        root + "/etc/locale.conf", ["LANG=" + adv["locale"]]
    ))
    setup.append(write_file(
        root + "/etc/vconsole.conf", ["KEYMAP=" + keymap_for(adv["keyboard"])]
    ))
    setup.append(
        "mkdir -p " + root + "/etc && ln -sfn "
        + shlex.quote("/usr/share/zoneinfo/" + adv["timezone"])
        + " " + root + "/etc/localtime"
    )
    setup.append(write_file(
        root + "/root/customize_airootfs.sh",
        ["#!/bin/sh", "locale-gen"], "755"
    ))

    if adv["hostname"]:
        setup.append(write_file(root + "/etc/hostname", [adv["hostname"]]))

    out["packages"] += ["sudo"]

    user = adv["username"]

    if user:
        setup.append(append_file(
            root + "/etc/passwd",
            [user + ":x:1000:1000::/home/" + user + ":/bin/bash"]
        ))
        setup.append(append_file(root + "/etc/group", [user + ":x:1000:"]))
        setup.append(append_file(root + "/etc/gshadow", [user + ":!*::"]))

        digest = sha512_crypt(password) if password else "!"

        setup.append(append_file(
            root + "/etc/shadow", [user + ":" + digest + ":14871::::::"]
        ))
        setup.append("mkdir -p " + root + "/home/" + shlex.quote(user))
        setup.append(write_file(
            root + "/etc/sudoers.d/99-ulb-user",
            [user + " ALL=(ALL:ALL) ALL"], "440"
        ))
        setup.append(append_file(
            "profile/profiledef.sh",
            [
                'file_permissions+=(["/home/' + user
                + '"]="1000:1000:750")',
                'file_permissions+=(["/etc/sudoers.d/99-ulb-user"]'
                '="0:0:440")'
            ]
        ))

    elif password:
        # Pas d'utilisateur : le mot de passe est celui de root.
        setup.append(
            "sed -i " + shlex.quote(
                "s#^root:[^:]*:#root:" + sha512_crypt(password)
                .replace("#", "\\#").replace("&", "\\&") + ":#"
            ) + " " + root + "/etc/shadow"
        )

    if adv["secureboot"]:
        out["packages"] += ["sbctl", "mokutil"]

    if adv["proprietary"]:
        out["packages"] += arch_nvidia(kernel_package) + [
            "ffmpeg", "gst-libav", "gst-plugins-ugly"
        ]

    if adv["luks"]:
        out["packages"].append("cryptsetup")

    if adv["filesystem"] == "btrfs":
        out["packages"].append("btrfs-progs")

        if adv["snapshots"]:
            out["packages"] += ["snapper", "grub-btrfs"]

    elif adv["filesystem"] == "xfs":
        out["packages"].append("xfsprogs")

    if adv["mirror"]:
        mirrorlist = ["Server = " + adv["mirror"].rstrip("/")
                      + "/$repo/os/$arch"]

        setup.append(write_file("ulb-mirrorlist", mirrorlist))
        setup.append(write_file(
            root + "/etc/pacman.d/mirrorlist", mirrorlist
        ))
        setup.append(
            "sed -i 's#^Include = /etc/pacman.d/mirrorlist#Include = '"
            '"$PWD"\'/ulb-mirrorlist#\' profile/pacman.conf'
        )

    if adv["proxy"]:
        proxy = shlex.quote(adv["proxy"])
        out["env"] = "http_proxy=" + proxy + " https_proxy=" + proxy + " "

    repos = [parse_repo(line) for line in adv["repos"]]
    repos = [repo for repo in repos if repo]

    for name, url, sig in repos:
        setup.append(append_file(
            "profile/pacman.conf",
            ["", "[" + name + "]", "SigLevel = " + sig, "Server = " + url]
        ))

    if adv["aur"] and adv["aur_packages"]:
        names = sorted(set(adv["aur_packages"]))
        quoted = " ".join(shlex.quote(name) for name in names)

        setup.append(
            "pacman -S --needed --noconfirm base-devel git sudo; "
            "id ulbbuild >/dev/null 2>&1 || useradd -m ulbbuild; "
            "echo 'ulbbuild ALL=(ALL) NOPASSWD: ALL' "
            "> /etc/sudoers.d/ulbbuild; chmod 440 /etc/sudoers.d/ulbbuild; "
            'aur="$PWD/aur-repo"; rm -rf "$aur" aur-src; '
            'mkdir -p "$aur" aur-src; chmod 777 aur-src; '
            "for p in " + quoted + "; do "
            'su ulbbuild -c "cd \\"$PWD/aur-src\\" && '
            "git clone --depth 1 https://aur.archlinux.org/$p.git && "
            'cd $p && makepkg -s --noconfirm" '
            "|| { echo \"AUR : échec de $p\" >&2; "
            "rm -f /etc/sudoers.d/ulbbuild; exit 1; }; "
            'cp aur-src/"$p"/*.pkg.tar.* "$aur"/; done; '
            "rm -f /etc/sudoers.d/ulbbuild; "
            'repo-add "$aur/ulb-aur.db.tar.gz" "$aur"/*.pkg.tar.*; '
            "printf '%s\\n' '' '[ulb-aur]' 'SigLevel = Optional TrustAll' "
            '"Server = file://$aur" >> profile/pacman.conf'
        )
        out["packages"] += names

    out["setup"] = joined(setup)

    return out


# ------------------------------------------------------------
# RAPPORT : ce qui est réellement appliqué, par famille
# ------------------------------------------------------------

APPLIED = "Appliqué (non testé)"
PARTIAL = "Partiel"
NA = "Non applicable"
OFF = "Désactivé"


def advanced_report(family, data):
    """[(option, état, détail)] : honnête sur ce que chaque famille fait."""

    adv = normalize(data)

    if not adv["enabled"]:
        return [("Avancé", OFF, "Cocher « Avancé » pour régler ces options.")]

    debian = family == "Debian"
    fedora = family == "Fedora"
    arch = family == "Arch Linux"

    rows = []

    rows.append((
        "Langue, clavier, fuseau (live)", APPLIED,
        "Paramètres de démarrage live-config." if debian else
        "Directives lang / keyboard / timezone du kickstart." if fedora else
        "locale.conf, vconsole.conf, localtime dans l'image."
    ))

    rows.append((
        "Langue, clavier, fuseau (système installé)",
        PARTIAL if debian else PARTIAL if fedora else NA,
        "Fuseau proposé par défaut dans Calamares ; langue et clavier "
        "repris du live." if debian else
        "Valeurs du kickstart, modifiables dans Anaconda." if fedora else
        "Pas d'installateur graphique : à régler à la main."
    ))

    rows.append((
        "Nom d'hôte", APPLIED if adv["hostname"] else OFF,
        "Live." if adv["hostname"] else "Non renseigné."
    ))

    rows.append((
        "Utilisateur du live",
        (APPLIED if debian or arch else PARTIAL) if adv["username"] else OFF,
        "Nom d'utilisateur live-config." if debian else
        "Compte créé dans l'image (passwd, shadow, sudo)." if arch else
        "Fedora garde le compte « liveuser » (seul le mot de passe "
        "est modifiable)."
        if adv["username"] else "Non renseigné."
    ))

    rows.append((
        "Persistance (clé USB)",
        PARTIAL if adv["persistence"] and debian else
        NA if adv["persistence"] else OFF,
        "Fichier créé par l'onglet Ventoy (Debian seulement)."
        if adv["persistence"] and debian else
        "Prise en charge uniquement prévue pour Debian."
        if adv["persistence"] else "Non demandée."
    ))

    rows.append((
        "Chiffrement du disque (LUKS)",
        (APPLIED if debian else PARTIAL if fedora else NA)
        if adv["luks"] else OFF,
        "Calamares : partitionnement automatique chiffré." if debian else
        "Outils ajoutés ; la case de chiffrement se coche dans Anaconda."
        if fedora else
        "Pas d'installateur graphique ; cryptsetup ajouté."
        if adv["luks"] else "Non demandé."
    ))

    rows.append((
        "Système de fichiers (" + adv["filesystem"] + ")",
        (APPLIED if debian or fedora else NA),
        "Calamares : defaultFileSystemType." if debian else
        "Anaconda : /etc/anaconda/conf.d." if fedora else
        "Pas d'installateur graphique ; outils ajoutés."
    ))

    rows.append((
        "Instantanés btrfs",
        PARTIAL if adv["snapshots"] and adv["filesystem"] == "btrfs"
        else OFF,
        "Paquets ajoutés ; la configuration reste à faire après "
        "l'installation."
        if adv["snapshots"] and adv["filesystem"] == "btrfs" else
        "Demande btrfs." if adv["snapshots"] else "Non demandés."
    ))

    rows.append((
        "Secure Boot",
        PARTIAL if adv["secureboot"] else OFF,
        "Paquets signés ajoutés ; la chaîne complète n'est pas validée "
        "(Ventoy doit aussi enrôler sa clé)."
        if adv["secureboot"] else "Non demandé."
    ))

    rows.append((
        "Pilotes propriétaires / codecs",
        (APPLIED if debian or fedora or arch else NA)
        if adv["proprietary"] else OFF,
        "Zones non-free activées, nvidia-driver et codecs." if debian else
        "Dépôts RPM Fusion ajoutés au kickstart, akmod-nvidia et codecs."
        if fedora else
        "Paquet nvidia adapté au noyau, ffmpeg et GStreamer."
        if adv["proprietary"] else "Non demandés."
    ))

    rows.append((
        "Miroir / proxy",
        APPLIED if adv["mirror"] or adv["proxy"] else OFF,
        "Options de live-build." if debian else
        "Dépôt du kickstart et --proxy de livemedia-creator." if fedora else
        "Liste de miroirs et variables de proxy de pacman."
        if adv["mirror"] or adv["proxy"] else "Non renseignés."
    ))

    rows.append((
        "Dépôts tiers (AUR, pacman)",
        (APPLIED if arch else NA)
        if adv["aur"] or adv["repos"] else OFF,
        "AUR : paquets compilés dans un dépôt local (expérimental)."
        if arch and adv["aur"] else
        "Dépôts pacman ajoutés à profile/pacman.conf."
        if arch and adv["repos"] else
        "Réservé à Arch Linux." if adv["aur"] or adv["repos"]
        else "Non demandés."
    ))

    return rows
