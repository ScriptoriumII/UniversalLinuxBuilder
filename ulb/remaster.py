"""Remaster d'une ISO officielle Gentoo ou Slackware avec xorriso.

Pas de construction « from scratch » : on part de l'ISO officielle, on
retire / ajoute des fichiers, puis on regénère l'image en gardant son
amorçage BIOS/UEFI. Les scripts s'exécutent dans n'importe quel WSL2
(Debian, Fedora ou Arch) qui possède xorriso ; Gentoo et Slackware n'ont
donc pas besoin de leur propre distribution WSL.

- Gentoo : méthode générique « -boot_image any replay » (reprise de
  l'amorçage de l'ISO d'origine), puis contrôle que les entrées
  d'amorçage sont identiques.
- Slackware : extraction de l'arbre puis commande officielle du fichier
  isolinux/README.TXT de Slackware (BIOS + UEFI), le secteur MBR étant
  repris de l'ISO d'origine.
"""

import shlex
from pathlib import PurePosixPath

REMASTER_FAMILIES = ("Gentoo", "Slackware")

# Séries Slackware que l'on peut retirer sans casser le système de base.
SLACKWARE_REMOVABLE = [
    "d", "e", "f", "k", "kde", "kdei", "t", "tcl", "x", "xap", "xfce", "y"
]

XORRISO_PACKAGES = {
    "Debian": "xorriso",
    "Fedora": "xorriso",
    "Arch Linux": "libisoburn"
}


def install_xorriso_command(family):
    package = XORRISO_PACKAGES.get(family)

    if not package:
        raise ValueError("Famille WSL non prise en charge : " + family)

    return {
        "Debian": "DEBIAN_FRONTEND=noninteractive apt-get update && "
                  "DEBIAN_FRONTEND=noninteractive apt-get install -y "
                  "--no-install-recommends " + package,
        "Fedora": "dnf -y install " + package,
        "Arch Linux": "pacman -Syu --noconfirm --needed " + package
    }[family]


def clean_removals(family, series):
    """Valide la liste des éléments à retirer ; retourne les chemins
    (relatifs à la racine de l'ISO)."""

    paths = []

    if family == "Slackware":
        for name in series:
            if name not in SLACKWARE_REMOVABLE:
                raise ValueError(
                    "Série non retirable : " + name + " (autorisées : "
                    + " ".join(SLACKWARE_REMOVABLE) + ")"
                )

            paths.append("slackware64/" + name)

    elif series:
        raise ValueError("Aucun retrait automatique pour " + family)

    return paths


def _check_relative(path):
    pure = PurePosixPath(path)

    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("Chemin invalide : " + path)

    return str(pure)


XORRISO_CHECK = (
    'command -v xorriso >/dev/null || { echo "xorriso introuvable : '
    "installe-le (bouton « Installer xorriso » ou "
    'apt install xorriso / dnf install xorriso / pacman -S libisoburn)" '
    ">&2; exit 3; }"
)

# Options d'amorçage (El Torito + zone système) d'une ISO, réduites au nom
# de l'option : l'ISO regénérée doit en avoir exactement les mêmes.
BOOT_SIGNATURE = (
    "boot_sig() { xorriso -indev \"$1\" -report_el_torito as_mkisofs "
    "-report_system_area as_mkisofs 2>/dev/null "
    "| grep '^-' | sed 's/ .*//' | sort | uniq -c; }"
)

BOOT_COMPARE = (
    'a=$(boot_sig "$iso"); b=$(boot_sig "$out"); '
    'if [ -z "$a" ]; then echo "ULB: attention, l\'ISO d\'origine n\'a '
    'aucune entrée d\'amorçage lisible"; '
    'elif [ "$a" != "$b" ]; then '
    'echo "ULB: AMORÇAGE PERDU : les entrées BIOS/UEFI de l\'ISO '
    'regénérée diffèrent de l\'originale" >&2; '
    'echo "origine : $a" >&2; echo "nouvelle : $b" >&2; exit 5; '
    'else echo "ULB: amorçage BIOS/UEFI identique à l\'ISO d\'origine"; fi'
)


def gentoo_script(workspace, iso, out, overlay="", remove=()):
    parts = [
        "set -eu",
        XORRISO_CHECK,
        BOOT_SIGNATURE,
        "iso=" + shlex.quote(iso),
        "out=" + shlex.quote(out),
        'test -f "$iso" || { echo "ISO introuvable : $iso" >&2; exit 2; }',
        "mkdir -p " + shlex.quote(workspace),
        'rm -f "$out"'
    ]

    command = [
        'xorriso -indev "$iso" -outdev "$out"',
        "-boot_image any replay"
    ]

    if remove:
        # « -rm_r » lit des chemins jusqu'au « -- » : sans lui, les
        # options suivantes seraient prises pour des chemins.
        command.append(
            "-rm_r "
            + " ".join(
                shlex.quote("/" + _check_relative(path)) for path in remove
            )
            + " --"
        )

    if overlay:
        command.append("-map " + shlex.quote(overlay) + " /")

    command.append("-commit")

    parts.append(" ".join(command))
    parts.append(BOOT_COMPARE)
    parts.append('ls -l "$out"')

    return "; ".join(parts)


def slackware_script(workspace, iso, out, overlay="", remove=(),
                     volid="SlackDVD", drop_sources=True):
    if not volid or len(volid) > 32:
        raise ValueError("Nom de volume invalide.")

    tree = workspace + "/tree"

    parts = [
        "set -eu",
        XORRISO_CHECK,
        "iso=" + shlex.quote(iso),
        "out=" + shlex.quote(out),
        'test -f "$iso" || { echo "ISO introuvable : $iso" >&2; exit 2; }',
        "mkdir -p " + shlex.quote(workspace),
        "rm -rf " + shlex.quote(tree),
        "mkdir -p " + shlex.quote(tree),
        # extraction de l'arbre officiel et du secteur MBR d'origine
        'echo "ULB: extraction de l\'ISO..."',
        'xorriso -osirrox on:auto_chmod_on -indev "$iso" -extract / '
        + shlex.quote(tree) + " 2>&1 | tail -n 3",
        'dd if="$iso" of=' + shlex.quote(workspace + "/mbr.bin")
        + " bs=432 count=1 2>/dev/null",
        "cd " + shlex.quote(tree),
        # fichiers d'amorçage exigés par le README officiel
        "for f in isolinux/isolinux.bin isolinux/efiboot.img; do "
        '[ -f "$f" ] || { echo "ULB: fichier d\'amorçage absent de '
        'l\'ISO : $f (utilise le DVD officiel)" >&2; exit 4; }; done',
        # générés par xorriso à la reconstruction
        "rm -f isolinux/isolinux.boot isolinux/boot.cat"
    ]

    if drop_sources:
        parts.append("rm -rf source")

    for path in remove:
        parts.append("rm -rf -- " + shlex.quote(_check_relative(path)))

    if overlay:
        parts.append(
            "cp -a " + shlex.quote(overlay.rstrip("/") + "/.") + " ."
        )

    parts += [
        'rm -f "$out"',
        # commande officielle d'isolinux/README.TXT (BIOS + UEFI)
        "xorriso -as mkisofs -iso-level 3 -full-iso9660-filenames "
        '-R -J -A "Slackware Install" -hide-rr-moved -v -d -N '
        "-eltorito-boot isolinux/isolinux.bin "
        "-eltorito-catalog isolinux/boot.cat "
        "-no-emul-boot -boot-load-size 4 -boot-info-table "
        "-isohybrid-mbr " + shlex.quote(workspace + "/mbr.bin") + " "
        "-eltorito-alt-boot -e isolinux/efiboot.img "
        "-no-emul-boot -isohybrid-gpt-basdat "
        "-volid " + shlex.quote(volid) + ' -output "$out" . '
        ">/dev/null 2>&1 || { echo \"ULB: xorriso a échoué\" >&2; exit 1; }",
        # contrôle : les deux entrées d'amorçage existent dans le résultat
        'n=$(xorriso -indev "$out" -report_el_torito plain 2>/dev/null '
        "| grep -c 'El Torito boot img') || true; "
        'if [ "${n:-0}" -lt 2 ]; then echo "ULB: AMORÇAGE PERDU : '
        'moins de deux entrées El Torito (BIOS + UEFI)" >&2; exit 5; fi; '
        'echo "ULB: entrées d\'amorçage BIOS + UEFI présentes"',
        'ls -l "$out"'
    ]

    return "; ".join(parts)


def windows_overlay(path):
    """Dossier de fichiers à ajouter à la racine de l'ISO (optionnel)."""

    from pathlib import Path

    if not path:
        return ""

    folder = Path(path)

    if not folder.is_dir():
        raise RuntimeError("Dossier de fichiers à ajouter introuvable : "
                           + str(path))

    if not any(folder.iterdir()):
        raise RuntimeError("Le dossier de fichiers à ajouter est vide.")

    return str(folder)


def remaster_iso(
    env,
    family,
    source_iso,
    directory,
    options=None,
    control=None
):
    """Génère une ISO personnalisée à partir d'une ISO officielle.

    options : {"overlay": dossier Windows, "remove": [séries/chemins],
    "drop_sources": bool, "cleanup": bool}
    Retourne (fichiers, rapport) comme build_iso()."""

    import datetime
    import shutil
    from pathlib import Path

    from .builders import append_sums, copy_from_wsl, free_name
    from .constants import VERSION
    from .environments import detect_family
    from .sources import import_iso
    from .vm import windows_to_wsl_path
    from .wsl import Control, execute, wsl_stream

    control = control or Control()
    options = dict(options or {})
    options.setdefault("cleanup", True)
    options.setdefault("drop_sources", True)

    if family not in REMASTER_FAMILIES:
        raise RuntimeError("Remaster non prévu pour " + family)

    control.log("== Vérification ==")
    info = import_iso(source_iso)
    control.log(
        "ISO source : " + Path(source_iso).name + " ("
        + format(info["bytes"] / 1024 ** 3, ".2f") + " Go, volume « "
        + info["label"] + " »)"
    )

    destination = Path(directory)

    if not destination.is_dir():
        raise RuntimeError("Le dossier de destination n'existe pas : "
                           + str(directory))

    wsl_family, _metadata = detect_family(env)

    if wsl_family not in XORRISO_PACKAGES:
        raise RuntimeError(
            "WSL « " + env + " » (" + wsl_family + ") ne convient pas : "
            "utilise un WSL Debian, Fedora ou Arch Linux."
        )

    _out, _err, code = execute(env, "command -v xorriso", 60)

    if code:
        raise RuntimeError(
            "xorriso est absent de « " + env + " » : clique sur "
            "« Installer xorriso »."
        )

    remove = clean_removals(family, options.get("remove", []))
    overlay = windows_overlay(options.get("overlay", ""))
    wsl_iso = windows_to_wsl_path(env, source_iso)
    wsl_overlay = windows_to_wsl_path(env, overlay) if overlay else ""

    # Espace : Slackware extrait l'arbre (≈ 1,1 fois l'ISO) puis écrit
    # l'ISO ; Gentoo écrit seulement l'ISO.
    factor = 2.6 if family == "Slackware" else 1.3
    need_wsl = int(info["bytes"] * factor)
    need_windows = int(info["bytes"] * 1.1)
    free_out, _err, status = execute(
        env, "df -Pk /var/tmp | awk 'NR==2{print $4}'", 60, root=True
    )

    try:
        free_wsl = int(free_out.split()[0]) * 1024

    except (ValueError, IndexError):
        raise RuntimeError("Espace libre WSL illisible : " + free_out)

    windows_free = shutil.disk_usage(destination).free

    if free_wsl < need_wsl:
        raise RuntimeError(
            "Espace insuffisant dans WSL : "
            + format(free_wsl / 1024 ** 3, ".1f") + " Go libres, "
            + format(need_wsl / 1024 ** 3, ".1f") + " Go requis."
        )

    if windows_free < need_windows:
        raise RuntimeError(
            "Espace insuffisant sur le disque Windows : "
            + format(windows_free / 1024 ** 3, ".1f") + " Go libres, "
            + format(need_windows / 1024 ** 3, ".1f") + " Go requis."
        )

    control.check()

    identifier = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    workspace = "/var/tmp/ulb-remaster-" + identifier
    stamp = identifier[:15]
    out = workspace + "/out.iso"

    if family == "Gentoo":
        script = gentoo_script(workspace, wsl_iso, out, wsl_overlay, remove)

    else:
        script = slackware_script(
            workspace, wsl_iso, out, wsl_overlay, remove,
            volid=info["label"] or "SlackDVD",
            drop_sources=options["drop_sources"]
        )

    files = []
    failure = ""
    cancelled = False
    code = -1

    try:
        control.log("== Remaster (" + family + ") ==")
        control.progress(None)
        output, code = wsl_stream(env, script, control, 7200, root=True)

        if code:
            raise RuntimeError(
                "Remaster échoué (code " + str(code) + ").\n"
                + output[-1800:]
            )

        sized, _err, status = execute(
            env, "stat -c %s " + shlex.quote(out), 60, root=True
        )

        try:
            size = int(sized.split()[0])

        except (ValueError, IndexError):
            raise RuntimeError("ISO produite introuvable dans WSL.")

        target = free_name(
            destination,
            "ULB_" + family + "_" + stamp + ".iso"
        )
        control.log("== Copie vers Windows : " + target.name + " ==")
        sha256 = copy_from_wsl(env, out, target, size, control)
        info_out = import_iso(target)
        append_sums(destination / "SHA256SUMS",
                    [sha256 + " *" + target.name])

        files.append({
            "file": str(target),
            "bytes": target.stat().st_size,
            "sha256": sha256,
            "iso9660": info_out["iso9660"],
            "source": str(source_iso),
            "boot_tested": False,
            "installer_tested": False
        })

        control.progress(100)
        control.log("== Terminé ==")

    except BaseException as exc:
        failure = str(exc)
        cancelled = control.cancelled
        raise

    finally:
        control.settle()
        cleaned = False

        if options["cleanup"] and (files or cancelled):
            try:
                execute(env, "rm -rf -- " + shlex.quote(workspace),
                        600, root=True)
                cleaned = True

            except Exception:
                pass

        header = (
            "Universal Linux Builder v" + VERSION + " (remaster)\n"
            "Famille : " + family + "\n"
            "ISO source : " + str(source_iso) + "\n"
            "WSL : " + env + "\n"
            "Workspace : " + workspace
            + (" (supprimé)" if cleaned else " (conservé)") + "\n"
            "Options : " + str(options) + "\n"
            "Code retour : " + str(code) + "\n"
            "Résultat : " + (
                "ANNULÉ" if cancelled
                else "ÉCHEC : " + failure.splitlines()[0] if failure
                else "SUCCÈS"
            ) + "\n\n"
        )

        report = header + "\n".join(control.history)

        try:
            free_name(destination, "build_report_" + stamp + ".txt"
                      ).write_text(report, encoding="utf-8")

        except OSError:
            pass

    return files, report
