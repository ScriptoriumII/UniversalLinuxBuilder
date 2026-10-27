"""Clé USB bootable avec Ventoy, depuis Windows (sans WSL pour Ventoy).

- téléchargement de la dernière version officielle (GitHub, empreinte
  SHA-256 vérifiée) ;
- liste des clés USB (PowerShell) ;
- installation / mise à jour par la ligne de commande documentée
  `Ventoy2Disk.exe VTOYCLI /I|/U /PhyDrive:N [/GPT] [/NOSB] [/R:Mo]
  [/FS:fs]` (élévation UAC demandée par Windows) ;
- copie d'ISO sur la partition de données et `ventoy/ventoy.json`.

Seule la bibliothèque standard est utilisée. Aucune de ces opérations n'a
pu être exécutée sur une vraie clé depuis l'environnement de
développement : les commandes suivent la documentation de Ventoy.
"""

import hashlib
import json
import re
import shlex
import zipfile
from pathlib import Path

from .constants import settings_file
from .sources import SourceError, fetch_text, open_url
from .wsl import Control, run

RELEASE_API = "https://api.github.com/repos/ventoy/Ventoy/releases/latest"

FILESYSTEMS = ["exFAT", "NTFS", "FAT32"]
STYLES = ["MBR", "GPT"]

VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){1,3}$")
POWERSHELL = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]


class VentoyError(Exception):
    pass


def base_directory():
    return settings_file().parent / "ventoy"


# ------------------------------------------------------------
# VERSION OFFICIELLE
# ------------------------------------------------------------

def parse_release(text):
    """{"version", "zip_url", "zip_name", "sha_url"} depuis la réponse de
    l'API des versions GitHub."""

    try:
        data = json.loads(text)

    except ValueError:
        raise VentoyError("Réponse GitHub illisible.")

    if not isinstance(data, dict):
        raise VentoyError("Réponse GitHub inattendue.")

    version = str(data.get("tag_name", "")).lstrip("v")

    if not VERSION_RE.match(version):
        raise VentoyError("Version Ventoy illisible : " + version)

    zip_url = zip_name = sha_url = ""

    for asset in data.get("assets", []):
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))

        if name == "ventoy-" + version + "-windows.zip":
            zip_url, zip_name = url, name

        elif name == "sha256.txt":
            sha_url = url

    if not zip_url.startswith("https://"):
        raise VentoyError(
            "Archive Windows introuvable dans la version " + version
        )

    return {
        "version": version, "zip_url": zip_url,
        "zip_name": zip_name, "sha_url": sha_url
    }


def latest_release(opener=open_url):
    return parse_release(fetch_text(RELEASE_API, opener))


def installed_versions(base=None):
    base = Path(base or base_directory())

    if not base.is_dir():
        return []

    return sorted(
        item.name[len("ventoy-"):]
        for item in base.iterdir()
        if item.is_dir() and item.name.startswith("ventoy-")
        and any(item.rglob("Ventoy2Disk.exe"))
    )


def find_executable(base, version):
    root = Path(base) / ("ventoy-" + version)

    for path in root.rglob("Ventoy2Disk.exe"):
        return path

    return None


def sha_for(text, filename):
    for line in text.splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line.strip())

        if match and Path(match.group(2)).name == filename:
            return match.group(1).lower()

    return ""


def safe_extract(archive, target):
    target = Path(target).resolve()

    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            destination = (target / name).resolve()

            if target not in destination.parents and destination != target:
                raise VentoyError("Archive refusée (chemin suspect) : " + name)

        bundle.extractall(target)


def fetch_ventoy(control=None, base=None, opener=open_url):
    """Télécharge, vérifie et extrait la dernière version ; retourne
    (version, chemin de Ventoy2Disk.exe)."""

    control = control or Control()
    base = Path(base or base_directory())
    release = latest_release(opener)
    version = release["version"]

    existing = find_executable(base, version)

    if existing:
        control.log("Ventoy " + version + " déjà présent.")
        return version, existing

    base.mkdir(parents=True, exist_ok=True)
    archive = base / release["zip_name"]
    part = base / (release["zip_name"] + ".part")

    control.log("Téléchargement de Ventoy " + version + "…")

    digest = hashlib.sha256()

    try:
        with opener(release["zip_url"], timeout=120) as response, \
                part.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0

            while True:
                control.check()
                block = response.read(1024 * 1024)

                if not block:
                    break

                handle.write(block)
                digest.update(block)
                done += len(block)

                if total:
                    control.progress(min(100, done * 100 // total))

    except OSError as exc:
        part.unlink(missing_ok=True)
        raise SourceError("Téléchargement impossible : " + str(exc))

    expected = ""

    if release["sha_url"]:
        expected = sha_for(
            fetch_text(release["sha_url"], opener), release["zip_name"]
        )

    if expected and expected != digest.hexdigest():
        part.unlink(missing_ok=True)
        raise VentoyError(
            "Empreinte SHA-256 incorrecte : archive supprimée."
        )

    control.log(
        "Empreinte SHA-256 vérifiée."
        if expected else
        "Attention : aucune empreinte publiée, archive non vérifiée."
    )

    part.replace(archive)
    safe_extract(archive, base / ("ventoy-" + version))

    executable = find_executable(base, version)

    if not executable:
        raise VentoyError("Ventoy2Disk.exe introuvable dans l'archive.")

    return version, executable


# ------------------------------------------------------------
# CLES USB
# ------------------------------------------------------------

LIST_DISKS = (
    "Get-Disk | Where-Object { $_.BusType -eq 'USB' } | "
    "ForEach-Object { [pscustomobject]@{ Number=$_.Number; "
    "Name=$_.FriendlyName; Size=$_.Size; Style=[string]$_.PartitionStyle; "
    "Boot=$_.IsBoot; System=$_.IsSystem } } | ConvertTo-Json -Compress"
)


def parse_disks(text):
    """Clés USB utilisables : jamais un disque de démarrage ou système."""

    text = text.strip()

    if not text:
        return []

    try:
        data = json.loads(text)

    except ValueError:
        raise VentoyError("Liste des disques illisible : " + text[:200])

    if isinstance(data, dict):
        data = [data]

    disks = []

    for item in data if isinstance(data, list) else []:
        try:
            number = int(item["Number"])
            size = int(item.get("Size") or 0)

        except (KeyError, TypeError, ValueError):
            continue

        if item.get("Boot") or item.get("System") or number == 0:
            continue

        disks.append({
            "number": number,
            "name": str(item.get("Name") or "Disque USB"),
            "size": size,
            "style": str(item.get("Style") or "")
        })

    return sorted(disks, key=lambda disk: disk["number"])


def human(size):
    gib = size / 1024 ** 3

    return (
        format(gib, ".1f") + " Go" if gib >= 1
        else format(size / 1024 ** 2, ".0f") + " Mo"
    )


def disk_label(disk):
    return (
        "Disque " + str(disk["number"]) + " — " + disk["name"]
        + " (" + human(disk["size"]) + ")"
    )


def list_usb_disks(runner=run):
    output, error, code = runner(POWERSHELL + [LIST_DISKS], 60)

    if code:
        raise VentoyError(
            "PowerShell : " + (error or output or "échec").strip()
        )

    return parse_disks(output)


def data_drive(number, runner=run, attempts=1):
    """Lettre du premier volume du disque (partition de données Ventoy)."""

    command = (
        "(Get-Partition -DiskNumber " + str(int(number)) + " | "
        "Where-Object { $_.DriveLetter } | Select-Object -First 1)"
        ".DriveLetter"
    )

    for _ in range(max(1, attempts)):
        output, error, code = runner(POWERSHELL + [command], 60)
        letter = output.strip()[:1]

        if not code and re.match(r"^[A-Za-z]$", letter):
            return letter.upper() + ":"

    return ""


# ------------------------------------------------------------
# INSTALLATION
# ------------------------------------------------------------

def build_cli_args(action, number, style="MBR", secure_boot=True,
                   reserve_mb=0, filesystem="exFAT"):
    """Arguments de `Ventoy2Disk.exe VTOYCLI …` (documentation Ventoy)."""

    if action not in ("install", "update"):
        raise VentoyError("Action inconnue : " + str(action))

    number = int(number)

    if number <= 0:
        raise VentoyError("Numéro de disque invalide.")

    args = ["VTOYCLI", "/I" if action == "install" else "/U",
            "/PhyDrive:" + str(number)]

    if action == "install":
        if style not in STYLES:
            raise VentoyError("Style de partition invalide : " + str(style))

        if filesystem not in FILESYSTEMS:
            raise VentoyError("Système de fichiers invalide : "
                              + str(filesystem))

        reserve_mb = int(reserve_mb)

        if not 0 <= reserve_mb <= 1048576:
            raise VentoyError("Espace réservé invalide.")

        if style == "GPT":
            args.append("/GPT")

        if reserve_mb:
            args.append("/R:" + str(reserve_mb))

        args.append("/FS:" + filesystem)

    if not secure_boot:
        args.append("/NOSB")

    return args


def powershell_quote(text):
    if "'" in text or "\n" in text:
        raise VentoyError("Caractère interdit dans un chemin : " + text)

    return "'" + text + "'"


def elevated_command(executable, args):
    """Commande PowerShell lançant Ventoy2Disk en administrateur (UAC)."""

    executable = Path(executable)

    return (
        "$p = Start-Process -FilePath "
        + powershell_quote(str(executable))
        + " -ArgumentList "
        + ",".join(powershell_quote(arg) for arg in args)
        + " -WorkingDirectory "
        + powershell_quote(str(executable.parent))
        + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    )


def read_cli_log(executable):
    path = Path(executable).parent / "cli_log.txt"

    try:
        return path.read_text(encoding="utf-8", errors="replace")[-1500:]

    except OSError:
        return ""


def install_ventoy(executable, args, number, control=None, runner=run):
    """Lance l'installation ; la réussite est contrôlée en retrouvant la
    partition de données (le code retour seul n'est pas documenté)."""

    control = control or Control()

    control.log("Commande : Ventoy2Disk.exe " + " ".join(args))
    control.log(
        "Windows va demander l'autorisation (UAC) : accepte pour continuer."
    )

    output, error, code = runner(
        POWERSHELL + [elevated_command(executable, args)], 1800
    )

    log = read_cli_log(executable)

    if log:
        control.log("-- cli_log.txt --\n" + log)

    if code:
        raise VentoyError(
            "Ventoy2Disk s'est terminé avec le code " + str(code) + ". "
            + (error or output).strip()[:300]
        )

    drive = data_drive(number, runner, attempts=5)

    if not drive:
        raise VentoyError(
            "Installation non confirmée : la partition de données de la "
            "clé n'est pas apparue. Consulte cli_log.txt."
        )

    control.log("Clé prête : " + drive)

    return drive


# ------------------------------------------------------------
# ISO ET PERSISTANCE
# ------------------------------------------------------------

def persistence_creation_script(size_mb, workdir="/var/tmp/ulb-persist"):
    """Script sh (WSL) créant le fichier de persistance Debian :
    ext4 d'étiquette « persistence » contenant persistence.conf."""

    size_mb = int(size_mb)

    if not 256 <= size_mb <= 262144:
        raise VentoyError("Taille de persistance invalide.")

    image = workdir + "/ulb-persistence.dat"

    return (
        "set -eu; command -v mke2fs >/dev/null 2>&1 || { "
        "echo 'mke2fs absent (paquet e2fsprogs)' >&2; exit 1; }; "
        "rm -rf " + shlex.quote(workdir) + "; "
        "mkdir -p " + shlex.quote(workdir + "/root") + "; "
        "printf '%s\\n' '/ union' > "
        + shlex.quote(workdir + "/root/persistence.conf") + "; "
        "truncate -s " + str(size_mb) + "M " + shlex.quote(image) + "; "
        "mke2fs -q -t ext4 -F -L persistence -d "
        + shlex.quote(workdir + "/root") + " " + shlex.quote(image) + "; "
        "echo " + shlex.quote(image)
    )


def update_ventoy_json(text, iso_name, backend_name):
    """Ajoute (ou remplace) l'entrée de persistance d'une ISO dans le
    contenu de ventoy.json. Refuse un fichier invalide plutôt que de
    l'écraser."""

    try:
        data = json.loads(text) if text.strip() else {}

    except ValueError:
        raise VentoyError(
            "ventoy.json existant invalide : il n'a pas été modifié."
        )

    if not isinstance(data, dict):
        raise VentoyError("ventoy.json inattendu (objet attendu).")

    image = "/" + iso_name
    entries = [
        entry for entry in data.get("persistence", [])
        if isinstance(entry, dict) and entry.get("image") != image
    ]
    entries.append({"image": image, "backend": "/" + backend_name})
    data["persistence"] = entries

    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def free_target(directory, name):
    target = Path(directory) / name
    stem, suffix = target.stem, target.suffix
    number = 2

    while target.exists():
        target = Path(directory) / (stem + "-" + str(number) + suffix)
        number += 1

    return target


def copy_file(source, target, control):
    source = Path(source)
    size = source.stat().st_size
    done = 0
    last = -1

    with source.open("rb") as origin, Path(target).open("wb") as out:
        while True:
            control.check()
            block = origin.read(4 * 1024 * 1024)

            if not block:
                break

            out.write(block)
            done += len(block)

            if size:
                percent = done * 100 // size

                if percent != last:
                    control.progress(percent)
                    last = percent


def copy_isos(drive, isos, control=None):
    """Copie les ISO à la racine de la partition Ventoy sans écraser
    l'existant ; retourne les noms copiés."""

    import shutil

    control = control or Control()
    root = Path(drive + "\\")

    if not root.exists():
        raise VentoyError("Lecteur introuvable : " + drive)

    names = []

    for iso in isos:
        iso = Path(iso)
        needed = iso.stat().st_size

        if shutil.disk_usage(root).free < needed:
            raise VentoyError("Espace insuffisant sur la clé pour " + iso.name)

        target = free_target(root, iso.name)
        control.log("Copie de " + iso.name + " → " + str(target))
        copy_file(iso, target, control)
        names.append(target.name)

    return names


def persist_on_usb(drive, iso_name, env, size_mb, control=None):
    """Crée le fichier de persistance dans le WSL `env`, le copie sur la
    clé et déclare-le dans ventoy/ventoy.json. Debian live seulement."""

    from .builders import copy_from_wsl
    from .wsl import wsl

    control = control or Control()
    root = Path(drive + "\\")
    backend = Path(iso_name).stem + "-persistence.dat"

    control.log("Création du fichier de persistance (" + str(size_mb)
                + " Mo) dans WSL…")

    output, error, code = wsl(
        env, persistence_creation_script(size_mb), 900, root=True
    )

    lines = output.strip().splitlines()

    if code or not lines:
        raise VentoyError(
            "Création de la persistance impossible : "
            + (error or output).strip()[:300]
        )

    image = lines[-1].strip()
    out, err, code = wsl(env, "stat -c %s " + shlex.quote(image), 60)

    try:
        size = int(out.strip().split()[0])

    except (ValueError, IndexError):
        size = 0

    target = free_target(root, backend)
    copy_from_wsl(env, image, target, size, control)

    config = root / "ventoy" / "ventoy.json"
    config.parent.mkdir(exist_ok=True)

    old = config.read_text(encoding="utf-8") if config.exists() else ""
    config.write_text(
        update_ventoy_json(old, iso_name, target.name), encoding="utf-8"
    )

    control.log("Persistance déclarée dans ventoy/ventoy.json.")

    return target.name


def write_usb(drive, isos, persistence=None, control=None):
    """Copie les ISO ; `persistence` = (indice de l'ISO, env WSL, Mo)."""

    control = control or Control()
    names = copy_isos(drive, isos, control)

    if persistence:
        index, env, size_mb = persistence
        persist_on_usb(drive, names[index], env, size_mb, control)

    return names
