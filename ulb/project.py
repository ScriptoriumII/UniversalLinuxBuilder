from pathlib import Path
import json
from .constants import VERSION


def export_project(data, directory):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)

    json_file = destination / "universal_linux_project.json"
    packages_file = destination / "packages.txt"
    readme_file = destination / "README.txt"

    json_file.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    packages_file.write_text(
        "\n".join(data["packages"]) + "\n",
        encoding="utf-8"
    )

    readme_file.write_text(
        "Universal Linux Builder v" + VERSION + "\n\n"
        "Distribution : " + data["family"] + "\n"
        "Version : " + data["release"] + "\n"
        "Installateur : " + data["installer"] + "\n"
        "Gestionnaire : " + data["manager"] + "\n\n"
        "Ce projet est un manifeste de préparation.\n"
        "Il ne constitue pas une ISO amorçable.\n\n"
        "Les paquets doivent être vérifiés pour la version "
        "exacte de la distribution.\n"
        "Le gestionnaire de paquets doit rester présent "
        "dans le système installé.\n"
        "L'installateur doit être configuré et testé "
        "séparément.\n",
        encoding="utf-8"
    )

    return str(destination)
