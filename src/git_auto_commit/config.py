"""Application paths and deliberately small JSON configuration."""

import json
import os
from pathlib import Path


def xdg(variable, default):
    value = os.environ.get(variable)
    if value and not Path(value).is_absolute():
        raise ValueError(f"{variable} must be an absolute path")
    return Path(value) if value else Path.home() / default


def config_dir():
    return xdg("XDG_CONFIG_HOME", ".config") / "git-auto-commit"


def repos_file():
    return config_dir() / "repos.list"


def settings_file():
    return config_dir() / "settings.json"


def unit_dir():
    return xdg("XDG_CONFIG_HOME", ".config") / "systemd" / "user"


def data_dir():
    return xdg("XDG_DATA_HOME", ".local/share") / "git-auto-commit"


def command_path():
    return Path.home() / ".local/bin/git-auto-commit"


def load_settings():
    path = settings_file()
    if not path.exists():
        return {"schedule": "weekly", "git_timeout": 120}
    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    timeout = settings.get("git_timeout", 120)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise ValueError("git_timeout must be between 0 and 3600 seconds")
    schedule = settings.get("schedule", "weekly")
    if not isinstance(schedule, str) or not schedule.strip():
        raise ValueError("schedule must be a nonempty string")
    return {**settings, "schedule": schedule, "git_timeout": timeout}


def atomic_write(path, text, mode=0o600):
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_settings(settings):
    atomic_write(settings_file(), json.dumps(settings, indent=2) + "\n")
