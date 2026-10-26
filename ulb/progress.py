"""Estimation de l'avancement et du temps restant d'une construction.

Les constructeurs (live-build, mkarchiso, livemedia-creator) n'annoncent
pas d'avancement global. On le reconstitue à partir de leur sortie :

- étapes reconnues par des motifs (debootstrap, apt, squashfs, ISO...) ;
- compteurs dans une étape (paquets téléchargés / dépaquetés / configurés,
  « (k/N) installing » de pacman, pourcentage de copie) ;
- le poids de chaque étape vient de la dernière construction réussie
  (durées réelles) ; sans historique, des poids par défaut approximatifs ;
- une étape sans compteur avance au prorata du temps de la dernière fois.

Tout cela reste une estimation : la durée dépend du réseau, du disque et
du processeur.
"""

import re
import time

COPY_STAGE = "Copie vers Windows"


def _ratio(done, total):
    return min(1.0, done / total) if total else 0.0


# Lignes de gestionnaire de paquets : elles citent des noms de paquets
# (xorriso, squashfs-tools...) sans marquer une étape de la construction.
PACKAGE_NOISE = re.compile(
    r"^(Get:|Hit:|Ign:|Unpacking |Setting up |Selecting |Preparing to "
    r"|Processing |Fetched |Building |The following |After this "
    r"|\(Reading database|\(\d+/\d+\) |I: )"
)


class Stage:
    def __init__(self, name, weight, start, counter=None, packages=False):
        self.name = name
        self.weight = weight
        self.start = re.compile(start)
        self.counter = counter() if counter else None
        # étape qui se reconnaît justement à ces lignes de paquets
        self.packages = packages


# ------------------------------------------------------------
# COMPTEURS INTERNES A UNE ETAPE
# ------------------------------------------------------------

class DebootstrapCounter:
    PHASES = (
        ("Retrieving", 0.10),
        ("Validating", 0.40),
        ("Unpacking", 0.55),
        ("Configuring", 0.85),
        ("Base system installed", 1.0)
    )

    def __init__(self):
        self.value = 0.0

    def feed(self, line):
        for key, value in self.PHASES:
            if key in line:
                self.value = max(self.value, value)

        return self.value


class AptCounter:
    """Télécharge 35 % / dépaque 35 % / configure 30 % d'une
    exécution d'apt ; plusieurs exécutions possibles."""

    NEW = re.compile(r"(\d+) newly installed")
    GET = re.compile(r"^Get:\d+ ")

    def __init__(self):
        self.total = 0
        self.get = self.unpack = self.setup = 0
        self.value = 0.0

    def feed(self, line):
        match = self.NEW.search(line)

        if match:
            self.total = int(match.group(1))
            self.get = self.unpack = self.setup = 0

        elif self.GET.match(line):
            self.get += 1

        elif line.startswith("Unpacking "):
            self.unpack += 1

        elif line.startswith("Setting up "):
            self.setup += 1

        if self.total:
            self.value = max(
                self.value,
                0.35 * _ratio(self.get, self.total)
                + 0.35 * _ratio(self.unpack, self.total)
                + 0.30 * _ratio(self.setup, self.total)
            )

        return self.value


class PacmanCounter:
    STEP = re.compile(r"^\((\d+)/(\d+)\) (\S+)")

    def __init__(self):
        self.value = 0.0

    def feed(self, line):
        match = self.STEP.match(line)

        if match:
            done, total = int(match.group(1)), int(match.group(2))
            verb = match.group(3)

            if verb.startswith(("installing", "upgrading")):
                value = 0.25 + 0.75 * _ratio(done, total)

            else:
                value = 0.25 * _ratio(done, total)

            self.value = max(self.value, value)

        return self.value


class PercentCounter:
    """Lignes de pourcentage (mksquashfs en terminal, copie)."""

    PERCENT = re.compile(r"(?:\b|\s)(\d{1,3}) ?%\s*$")

    def __init__(self):
        self.value = 0.0

    def feed(self, line):
        match = self.PERCENT.search(line)

        if match:
            self.value = max(
                self.value, min(100, int(match.group(1))) / 100
            )

        return self.value


class CopyCounter(PercentCounter):
    PERCENT = re.compile(r"Copie de l'ISO : (\d{1,3}) %")


# ------------------------------------------------------------
# ETAPES PAR FAMILLE
# ------------------------------------------------------------

def stages_for(family):
    if family == "Debian":
        stages = [
            Stage(
                "Système de base (debootstrap)", 0.12,
                r"^I: |debootstrap|P: Begin bootstrapping|lb_bootstrap",
                DebootstrapCounter,
                packages=True
            ),
            Stage(
                "Installation des paquets", 0.50,
                r"Reading package lists|Need to get|newly installed"
                r"|P: Begin installing packages|lb_chroot_install",
                AptCounter,
                packages=True
            ),
            Stage(
                "Finalisation du système", 0.05,
                r"lb_chroot_(hooks|hacks|archives|apt|hostname)"
                r"|P: Begin .*hook"
            ),
            Stage(
                "Système de fichiers (squashfs)", 0.20,
                r"mksquashfs|Creating .* filesystem on|lb_binary_rootfs"
                r"|P: Begin building binary|lb_binary_chroot",
                PercentCounter
            ),
            Stage(
                "Image ISO", 0.09,
                r"xorriso|Writing to|genisoimage|lb_binary_iso"
                r"|lb_binary_(grub|syslinux|isolinux)"
            )
        ]

    elif family == "Arch Linux":
        stages = [
            Stage(
                "Paquets (pacman)", 0.70,
                r"Installing packages|^\(\d+/\d+\) |resolving dependencies"
                r"|:: Synchronizing",
                PacmanCounter,
                packages=True
            ),
            Stage(
                "Système (airootfs)", 0.05,
                r"mkinitcpio|Customizing|airootfs"
            ),
            Stage(
                "SquashFS", 0.18,
                r"[Ss]quash[Ff][Ss]|mksquashfs",
                PercentCounter
            ),
            Stage("Image ISO", 0.07, r"Creating ISO|xorriso")
        ]

    else:
        stages = [
            Stage(
                "Construction (livemedia-creator)", 0.95,
                r"livemedia-creator|Running anaconda|INFO:|WARNING:"
            )
        ]

    stages.append(
        Stage(COPY_STAGE, 0.04, r"== Copie vers Windows", CopyCounter)
    )

    return stages


# ------------------------------------------------------------
# SUIVI
# ------------------------------------------------------------

class BuildProgress:
    def __init__(self, family, history=None, clock=time.monotonic):
        self.family = family
        self.clock = clock
        self.stages = stages_for(family)
        self.history = history or {}
        self.started = clock()
        self.current = -1
        self.stage_started = {}
        self.finished = False
        self._fraction = 0.0

        recorded = self.history.get("stages", {})

        if recorded and all(
            stage.name in recorded for stage in self.stages
        ):
            floor = 0.01 * sum(recorded.values())
            self.weights = [
                max(float(recorded[stage.name]), floor)
                for stage in self.stages
            ]

        else:
            self.weights = [stage.weight for stage in self.stages]

        self.total_weight = sum(self.weights)

    # -- entrée ------------------------------------------------

    def feed(self, line):
        line = line.strip()

        if not line:
            return

        if line.startswith("== Terminé"):
            self.finished = True
            self._advance(len(self.stages) - 1)
            return

        noise = bool(PACKAGE_NOISE.match(line))

        for index in range(
            len(self.stages) - 1, self.current, -1
        ):
            stage = self.stages[index]

            if noise and not stage.packages:
                continue

            if stage.start.search(line):
                self._advance(index)
                break

        if 0 <= self.current < len(self.stages):
            counter = self.stages[self.current].counter

            if counter is not None:
                counter.feed(line)

    def _advance(self, index):
        now = self.clock()

        for passed in range(self.current + 1, index + 1):
            self.stage_started.setdefault(passed, now)

        self.current = index

    # -- sortie ------------------------------------------------

    def elapsed(self):
        return self.clock() - self.started

    def stage_name(self):
        if self.finished:
            return "Terminé"

        if 0 <= self.current < len(self.stages):
            return self.stages[self.current].name

        return "Démarrage"

    def _inner(self):
        stage = self.stages[self.current]
        inner = stage.counter.value if stage.counter else 0.0

        recorded = self.history.get("stages", {}).get(stage.name)

        if inner == 0.0 and recorded:
            spent = self.clock() - self.stage_started.get(
                self.current, self.clock()
            )
            inner = min(0.97, spent / recorded)

        return inner

    def fraction(self):
        if self.finished:
            return 1.0

        if self.current < 0:
            value = 0.0

            total = self.history.get("total")

            if total:
                value = min(0.02, self.elapsed() / total * 0.02)

        else:
            done = sum(self.weights[:self.current])
            value = (
                done + self.weights[self.current] * self._inner()
            ) / self.total_weight

        self._fraction = max(self._fraction, min(value, 0.995))

        return self._fraction

    def eta(self):
        """Secondes restantes estimées, ou None si on ne peut pas."""

        fraction = self.fraction()
        elapsed = self.elapsed()

        if self.finished:
            return 0.0

        if fraction >= 0.08:
            return elapsed * (1 - fraction) / fraction

        total = self.history.get("total")

        if total:
            return max(0.0, total - elapsed)

        return None

    def summary(self):
        """Durées réelles, à conserver pour la prochaine estimation."""

        end = self.clock()
        starts = sorted(self.stage_started.items())
        durations = {}

        for position, (index, begin) in enumerate(starts):
            stop = (
                starts[position + 1][1]
                if position + 1 < len(starts)
                else end
            )
            durations[self.stages[index].name] = round(stop - begin, 1)

        complete = all(
            stage.name in durations for stage in self.stages
        )

        return {
            "total": round(end - self.started, 1),
            "stages": durations if complete else {}
        }


def format_duration(seconds):
    seconds = int(max(0, seconds))

    if seconds >= 3600:
        return "%d h %02d min" % (seconds // 3600, seconds % 3600 // 60)

    if seconds >= 90:
        return "%d min" % round(seconds / 60)

    return "%d s" % seconds


def describe(tracker):
    """Texte affiché dans la barre : étape, %, temps restant."""

    fraction = tracker.fraction()
    eta = tracker.eta()
    elapsed = format_duration(tracker.elapsed())

    parts = [tracker.stage_name()]

    if eta is None:
        parts.append("écoulé " + elapsed)

    else:
        parts.append("reste ~" + format_duration(eta) + " (estimation)")

    return int(fraction * 100), "  ·  ".join(parts)
