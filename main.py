"""Lanceur : py main.py   (py main.py --check pour un diagnostic seul)"""

import sys

from ulb.preflight import bootstrap


def run():
    code = bootstrap(sys.argv[1:])

    if code is not None:
        # fenêtre lancée par double-clic : laisse le temps de lire
        if sys.stdin and sys.stdin.isatty() and "--check" not in sys.argv:
            input("\nAppuie sur Entrée pour fermer...")

        return code

    from ulb.app import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
