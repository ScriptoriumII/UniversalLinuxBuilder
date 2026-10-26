import re
import collections
import threading
import subprocess
from .constants import ANSI


def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        result = data.decode("utf-16", "replace")

    elif b"\x00" in data[:100]:
        result = data.decode("utf-16-le", "replace")

    else:
        result = data.decode("utf-8", "replace")

    return ANSI.sub("", result).replace("\x00", "").lstrip("\ufeff")


def run(argv, timeout=300):
    process = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        creationflags=getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0
        )
    )

    return (
        decode(process.stdout),
        decode(process.stderr),
        process.returncode
    )


def wsl(env, command, timeout=300, root=False):
    argv = ["wsl.exe", "-d", env]

    if root:
        argv += ["-u", "root"]

    argv += [
        "--exec",
        "/bin/sh",
        "-lc",
        command
    ]

    return run(argv, timeout)


# ------------------------------------------------------------
# EXECUTION EN FLUX, ANNULATION
# ------------------------------------------------------------

CANCELLED = "Opération annulée."


class Cancelled(Exception):
    """Levée quand l'utilisateur annule une opération."""


class Control:
    """Canal entre le thread de travail et l'interface.

    - log(texte) : ligne de journal envoyée à l'interface ;
    - progress(valeur) : 0-100, ou None pour un indicateur indéterminé ;
    - cancel() : arrête le processus en cours (appelable depuis l'UI).
    """

    def __init__(self, log=None, progress=None, env=""):
        self._log = log or (lambda text: None)
        self._progress = progress or (lambda value: None)
        self.env = env
        self.history = collections.deque(maxlen=50000)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._process = None
        self._terminator = None

    def log(self, text):
        self.history.append(text)
        self._log(text)

    def progress(self, value):
        self._progress(value)

    @property
    def cancelled(self):
        return self._cancel.is_set()

    def check(self):
        if self._cancel.is_set():
            raise Cancelled(CANCELLED)

    def attach(self, process):
        with self._lock:
            self._process = process

        # Annulation demandée avant le lancement du processus.
        if self._cancel.is_set():
            kill_tree(process)

    def detach(self):
        with self._lock:
            self._process = None

    def cancel(self):
        self._cancel.set()

        with self._lock:
            process = self._process

        if process is not None:
            kill_tree(process)

        if self.env:
            # wsl.exe ne propage pas l'arrêt au processus Linux :
            # on termine la distribution de construction.
            self._terminator = threading.Thread(
                target=_terminate_distribution,
                args=(self.env,),
                daemon=True
            )
            self._terminator.start()

    def settle(self):
        """Attend la fin de l'arrêt de la distribution."""

        if self._terminator is not None:
            self._terminator.join(90)


def kill_tree(process):
    try:
        process.kill()

    except OSError:
        pass


def _terminate_distribution(env):
    try:
        subprocess.run(
            ["wsl.exe", "--terminate", env],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            )
        )

    except (OSError, subprocess.SubprocessError):
        pass


LINE_BREAK = re.compile(rb"[\r\n]+")


def stream(argv, control, timeout=None, keep=4000):
    """Exécute argv en renvoyant chaque ligne à control.log().

    stdout et stderr sont fusionnés pour conserver l'ordre réel.
    Retourne (sortie, code). La sortie est limitée aux `keep`
    dernières lignes ; le journal complet reste dans l'interface.
    """

    control.check()

    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0
        )
    )

    control.attach(process)

    timed_out = threading.Event()
    watchdog = None

    if timeout:
        def expire():
            timed_out.set()
            kill_tree(process)

        watchdog = threading.Timer(timeout, expire)
        watchdog.daemon = True
        watchdog.start()

    tail = collections.deque(maxlen=keep)
    pending = b""

    def emit(raw):
        text = decode(raw).rstrip()

        if text:
            tail.append(text)
            control.log(text)

    try:
        while True:
            chunk = process.stdout.read1(8192)

            if not chunk:
                break

            if b"\x00" in chunk:
                # Sortie UTF-16 de wsl.exe : on garde l'ASCII.
                chunk = chunk.replace(
                    b"\xff\xfe", b""
                ).replace(b"\x00", b"")

            pending += chunk
            parts = LINE_BREAK.split(pending)
            pending = parts.pop()

            for part in parts:
                emit(part)

        if pending:
            emit(pending)

        code = process.wait()

    finally:
        if watchdog is not None:
            watchdog.cancel()

        control.detach()
        process.stdout.close()

        if process.poll() is None:
            kill_tree(process)

    control.check()

    if timed_out.is_set():
        raise RuntimeError(
            "Délai dépassé ("
            + str(timeout)
            + " s) : opération interrompue."
        )

    return "\n".join(tail), code


def wsl_stream(env, command, control, timeout=None, root=False):
    argv = ["wsl.exe", "-d", env]

    if root:
        argv += ["-u", "root"]

    argv += ["--exec", "/bin/sh", "-lc", command]

    control.env = control.env or env

    return stream(argv, control, timeout)


def execute(env, command, timeout=300, root=False, control=None):
    """Comme wsl(), mais en direct si un Control est fourni.

    Retourne toujours (sortie, erreur, code).
    """

    if control is None:
        return wsl(env, command, timeout, root=root)

    output, code = wsl_stream(
        env,
        command,
        control,
        timeout,
        root=root
    )

    return output, "", code
