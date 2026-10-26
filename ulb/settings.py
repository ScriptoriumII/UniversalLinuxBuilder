import json
import os
import tempfile
from .constants import settings_file


def load_settings():
    try:
        data = json.loads(
            settings_file().read_text(encoding="utf-8")
        )

        return data if isinstance(data, dict) else {}

    except (OSError, ValueError):
        return {}


def save_settings(data):
    settings_file().parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fd, temporary = tempfile.mkstemp(
        prefix="settings-",
        suffix=".tmp",
        dir=settings_file().parent
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as handle:
            json.dump(
                data,
                handle,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temporary, settings_file())

    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
