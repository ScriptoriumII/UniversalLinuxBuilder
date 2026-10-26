import datetime
import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from .constants import (
    BUILD_FAMILIES,
    DEBIAN_FIRMWARE,
    FEDORA_KICKSTARTS,
    FEDORA_LIVE_REQUIRED,
    REQUIRED_SPACE,
    VERSION
)
from .environments import verify_tools
from .wsl import Control, decode, execute, wsl_stream

CHUNK = 4 * 1024 * 1024


# ------------------------------------------------------------
# SCRIPTS DE CONSTRUCTION (purs, donc testables)
# ------------------------------------------------------------

def quote_all(names):
    return " ".join(shlex.quote(name) for name in names)


def debian_script(workspace, release, packages, options):
    areas = (
        "main contrib non-free non-free-firmware"
        if options.get("firmware")
        else "main"
    )

    package_list = list(packages)

    if options.get("firmware"):
        package_list += [
            name
            for name in DEBIAN_FIRMWARE
            if name not in package_list
        ]

    config = [
        "lb config",
        "--distribution " + shlex.quote(release),
        "--architectures amd64",
        "--binary-images iso-hybrid",
        "--archive-areas " + shlex.quote(areas)
    ]

    if options.get("light"):
        config.append("--apt-recommends false")

    return (
        "set -eu; "
        "mkdir -p " + shlex.quote(workspace) + "; "
        "cd " + shlex.quote(workspace) + "; "
        + " ".join(config) + "; "
        "mkdir -p config/package-lists; "
        'printf "%s\\n" '
        + quote_all(sorted(set(package_list)))
        + " > config/package-lists/ulb.list.chroot; "
        "lb build"
    )


def fedora_script(workspace, release, packages, desktop):
    if not release.isdigit():
        raise RuntimeError(
            "Version Fedora invalide : " + release
        )

    kickstart = FEDORA_KICKSTARTS.get(
        desktop,
        FEDORA_KICKSTARTS["Aucun"]
    )

    return (
        "set -eu; "
        "mkdir -p " + shlex.quote(workspace) + "/tmp; "
        "cd " + shlex.quote(workspace) + "; "
        "base=$(rpm -ql fedora-kickstarts 2>/dev/null "
        "| grep '/fedora-live-base[.]ks$' "
        "| head -n 1 || true); "
        'test -n "$base" || { '
        'echo "fedora-kickstarts ne fournit pas '
        'fedora-live-base.ks" >&2; exit 1; }; '
        'dir=$(dirname "$base"); '
        'ks="$dir"/' + shlex.quote(kickstart) + "; "
        'test -f "$ks" || { '
        'echo "Kickstart introuvable : $ks" >&2; '
        'ls "$dir" >&2; exit 1; }; '
        'ksflatten --config "$ks" --output flat.ks '
        "--version F" + release + "; "
        "printf '%s\n' '' '%packages' "
        + quote_all(FEDORA_LIVE_REQUIRED)
        + " "
        + quote_all(packages)
        + " '%end' >> flat.ks; "
        "livemedia-creator --make-iso --no-virt "
        "--ks flat.ks "
        "--project 'Universal Linux Builder' "
        "--releasever " + release + " "
        "--volid ULB-F" + release + " "
        "--iso-only --iso-name ulb-fedora.iso "
        "--nomacboot "
        "--tmp tmp --resultdir result "
        "--logfile lmc.log "
        "|| { tail -n 80 lmc.log >&2 || true; exit 1; }"
    )


def arch_script(workspace, packages):
    profile = "/usr/share/archiso/configs/releng"

    return (
        "set -eu; "
        "test -f "
        + shlex.quote(profile + "/profiledef.sh")
        + "; "
        "mkdir -p " + shlex.quote(workspace) + "; "
        "cp -a "
        + shlex.quote(profile)
        + " "
        + shlex.quote(workspace)
        + "/profile; "
        "cd " + shlex.quote(workspace) + "; "
        'printf "%s\\n" '
        + quote_all(packages)
        + " >> profile/packages.x86_64; "
        "sort -u profile/packages.x86_64 "
        "-o profile/packages.x86_64; "
        "mkdir -p out work; "
        "mkarchiso -v -w work -o out profile"
    )


def iso_directory(family, workspace):
    return {
        "Debian": workspace,
        "Fedora": workspace + "/result",
        "Arch Linux": workspace + "/out"
    }[family]


# ------------------------------------------------------------
# ESPACE DISQUE
# ------------------------------------------------------------

def free_space_wsl(env, control):
    output, error, code = execute(
        env,
        "df -Pk /var/tmp | awk 'NR==2{print $4}'",
        60,
        root=True
    )

    try:
        return int(output.split()[0]) * 1024

    except (ValueError, IndexError):
        raise RuntimeError(
            "Espace libre WSL illisible : "
            + (error or output)
        )


def check_space(env, family, destination, control):
    need_wsl, need_windows = REQUIRED_SPACE[family]

    gib = 1024 ** 3
    wsl_free = free_space_wsl(env, control)
    windows_free = shutil.disk_usage(destination).free

    control.log(
        "Espace libre : WSL "
        + format(wsl_free / gib, ".1f")
        + " Go (minimum "
        + str(need_wsl)
        + "), Windows "
        + format(windows_free / gib, ".1f")
        + " Go (minimum "
        + str(need_windows)
        + ")"
    )

    if wsl_free < need_wsl * gib:
        raise RuntimeError(
            "Espace insuffisant dans WSL : "
            + format(wsl_free / gib, ".1f")
            + " Go libres, "
            + str(need_wsl)
            + " Go requis."
        )

    if windows_free < need_windows * gib:
        raise RuntimeError(
            "Espace insuffisant sur le disque Windows : "
            + format(windows_free / gib, ".1f")
            + " Go libres, "
            + str(need_windows)
            + " Go requis."
        )


# ------------------------------------------------------------
# COPIE DE L'ISO VERS WINDOWS
# ------------------------------------------------------------

def unc_path(env, source):
    if os.name != "nt":
        return None

    relative = source.lstrip("/").replace("/", "\\")

    for root in ("\\\\wsl.localhost\\", "\\\\wsl$\\"):
        candidate = Path(root + env + "\\" + relative)

        if candidate.exists():
            return candidate

    return None


def copy_from_wsl(env, source, target, size, control):
    """Copie une ISO hors de WSL ; retourne son SHA-256."""

    digest = hashlib.sha256()
    copied = 0
    last = -1

    def advance(count):
        nonlocal copied, last

        copied += count

        if size:
            percent = min(100, copied * 100 // size)
            control.progress(percent)

            if percent // 10 != last // 10:
                control.log(
                    "Copie de l'ISO : " + str(percent) + " %"
                )

            last = percent

    try:
        path = unc_path(env, source)

        if path is not None:
            control.log("Copie rapide via " + str(path))

            with path.open("rb") as origin, target.open("wb") as out:
                while True:
                    control.check()
                    chunk = origin.read(CHUNK)

                    if not chunk:
                        break

                    out.write(chunk)
                    digest.update(chunk)
                    advance(len(chunk))

        else:
            control.log("Copie via wsl.exe (flux)")

            process = subprocess.Popen(
                [
                    "wsl.exe", "-d", env, "-u", "root",
                    "--exec", "cat", source
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0
                )
            )

            control.attach(process)

            try:
                with target.open("wb") as out:
                    while True:
                        chunk = process.stdout.read(CHUNK)

                        if not chunk:
                            break

                        out.write(chunk)
                        digest.update(chunk)
                        advance(len(chunk))

                stderr = process.stderr.read()
                code = process.wait()

            finally:
                control.detach()

                if process.poll() is None:
                    process.kill()

            control.check()

            if code:
                raise RuntimeError(
                    "Copie ISO échouée : " + decode(stderr)
                )

        control.check()

        if size and target.stat().st_size != size:
            raise RuntimeError(
                "Copie incomplète : "
                + str(target.stat().st_size)
                + " octets au lieu de "
                + str(size)
            )

    except BaseException:
        target.unlink(missing_ok=True)
        raise

    return digest.hexdigest()


# ------------------------------------------------------------
# CONSTRUCTION
# ------------------------------------------------------------

def build_iso(
    env,
    family,
    release,
    packages,
    directory,
    desktop="Aucun",
    options=None,
    control=None
):
    """
    Construction expérimentale Debian / Arch Linux / Fedora.

    options : {"light": bool, "firmware": bool, "cleanup": bool}
    Ne garantit ni l'installateur ni le démarrage sur Ventoy.
    """

    control = control or Control()
    options = dict(options or {})
    options.setdefault("cleanup", True)

    if family not in BUILD_FAMILIES:
        raise RuntimeError(
            "Construction ISO non implémentée pour "
            + family
        )

    control.log("== Vérification de l'environnement ==")

    actual, metadata, rows = verify_tools(env)

    if actual != family:
        raise RuntimeError(
            "Famille WSL incompatible : " + actual
        )

    missing = [
        name
        for name, package, state in rows
        if state == "Absent"
    ]

    if missing:
        raise RuntimeError(
            "Outils manquants : "
            + ", ".join(missing)
        )

    destination = Path(directory)

    if any(destination.iterdir()):
        raise RuntimeError(
            "Le dossier de destination doit être vide."
        )

    control.check()
    check_space(env, family, destination, control)

    identifier = datetime.datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )

    workspace = "/var/tmp/ulb-" + identifier

    if family == "Debian":
        script = debian_script(
            workspace, release, packages, options
        )

    elif family == "Fedora":
        script = fedora_script(
            workspace, release, packages, desktop
        )

    else:
        script = arch_script(workspace, packages)

    code = -1
    files = []
    failure = ""
    cancelled = False

    try:
        control.log("== Construction (" + family + ") ==")
        control.progress(None)

        output, code = wsl_stream(
            env,
            script,
            control,
            7200,
            root=True
        )

        if code:
            raise RuntimeError(
                "Construction échouée (code "
                + str(code)
                + ").\n"
                + output[-1800:]
            )

        control.log("== Recherche de l'ISO ==")

        found, error, status = execute(
            env,
            "find "
            + shlex.quote(iso_directory(family, workspace))
            + ' -maxdepth 1 -type f -name "*.iso" -print',
            120,
            root=True
        )

        sources = found.split()

        if status or not sources:
            raise RuntimeError(
                "La construction n'a produit aucune ISO."
            )

        sums = []

        for index, source in enumerate(sources, 1):
            control.check()

            sized, error, status = execute(
                env,
                "stat -c %s " + shlex.quote(source),
                60,
                root=True
            )

            try:
                size = int(sized.split()[0])

            except (ValueError, IndexError):
                size = 0

            target = destination / (
                "ULB_"
                + family.replace(" ", "_")
                + "_"
                + str(index)
                + ".iso"
            )

            control.log(
                "== Copie vers Windows : " + target.name + " =="
            )

            sha256 = copy_from_wsl(
                env, source, target, size, control
            )

            with target.open("rb") as handle:
                handle.seek(32768)
                signature = handle.read(7)

            iso9660 = (
                len(signature) >= 6
                and signature[1:6] == b"CD001"
            )

            sums.append(sha256 + " *" + target.name)

            files.append({
                "file": str(target),
                "bytes": target.stat().st_size,
                "sha256": sha256,
                "iso9660": iso9660,
                "boot_tested": False,
                "installer_tested": False,
                "ventoy_tested": False
            })

        (destination / "SHA256SUMS").write_text(
            "\n".join(sums) + "\n",
            encoding="utf-8"
        )

        control.progress(100)
        control.log("== Terminé ==")

    except BaseException as exc:
        failure = str(exc)
        cancelled = control.cancelled
        raise

    finally:
        cleaned = False
        control.settle()

        # Échec : l'espace de travail est conservé pour diagnostic.
        # Succès ou annulation : il est supprimé si demandé.
        if options["cleanup"] and (files or cancelled):
            try:
                execute(
                    env,
                    "rm -rf -- " + shlex.quote(workspace),
                    600,
                    root=True
                )
                cleaned = True

            except Exception:
                pass

        header = (
            "Universal Linux Builder v" + VERSION + "\n"
            "Distribution : " + family + " " + release + "\n"
            "WSL : " + env + "\n"
            "Workspace : " + workspace
            + (" (supprimé)" if cleaned else " (conservé)")
            + "\n"
            "Options : " + str(options) + "\n"
            "Code retour : " + str(code) + "\n"
            + (
                "Résultat : " + (
                    "ANNULÉ" if cancelled
                    else "ÉCHEC : " + failure.splitlines()[0]
                    if failure else "SUCCÈS"
                ) + "\n"
            )
            + "\n"
        )

        report = header + "\n".join(control.history)

        try:
            (destination / "build_report.txt").write_text(
                report,
                encoding="utf-8"
            )

        except OSError:
            pass

    return files, report
