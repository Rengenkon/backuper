"""User units only. No linger or privileged operations."""

import shutil
import subprocess
from pathlib import Path

from .config import (atomic_write, command_path, config_dir, data_dir, load_settings,
                     save_settings, unit_dir)

UNIT = "git-auto-commit"


def command(*args):
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(str(error)) from error
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def validate_schedule(value):
    if not value.strip() or any(char in value for char in "\n\r\0%"):
        raise ValueError("Invalid OnCalendar value")
    command("systemd-analyze", "calendar", "--", value)
    return value


def preflight():
    for executable in ("git", "systemctl", "systemd-analyze"):
        if not shutil.which(executable):
            raise RuntimeError(f"Required command not found: {executable}")
    command("systemctl", "--user", "show-environment")
    validate_schedule(load_settings()["schedule"])


def quote(value, exec_start=False):
    value = str(value)
    if any(char in value for char in "\n\r\0"):
        raise ValueError("Unit values cannot contain newlines or NUL")
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    if exec_start:
        value = value.replace("$", "$$")
    return f'"{value}"'


def service_text(executable):
    environment = "".join(f"Environment={quote(key + '=' + str(value))}\n" for key, value in (
        ("HOME", Path.home()),
        ("XDG_CONFIG_HOME", config_dir().parent),
        ("XDG_DATA_HOME", data_dir().parent),
    ))
    return ("[Unit]\nDescription=Automatic Git commit and push\n\n"
            "[Service]\nType=oneshot\n"
            f"{environment}ExecStart={quote(executable, exec_start=True)} run\n"
            "TimeoutStartSec=infinity\nStandardOutput=journal\nStandardError=journal\n")


def timer_text(schedule):
    return ("[Unit]\nDescription=Automatic Git backup schedule\n\n"
            f"[Timer]\nOnCalendar={schedule}\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n")


def install(schedule=None):
    preflight()
    settings = load_settings()
    schedule = validate_schedule(schedule if schedule is not None else settings["schedule"])
    directory = unit_dir()
    atomic_write(directory / f"{UNIT}.service", service_text(command_path()))
    atomic_write(directory / f"{UNIT}.timer", timer_text(schedule))
    command("systemctl", "--user", "daemon-reload")
    command("systemctl", "--user", "enable", f"{UNIT}.timer")
    command("systemctl", "--user", "restart", f"{UNIT}.timer")
    settings["schedule"] = schedule
    save_settings(settings)
    print(f"Timer enabled: {schedule} (Persistent=true)")


def status():
    print(command("systemctl", "--user", "list-timers", "--all", f"{UNIT}.timer"), end="")
    print(command("systemctl", "--user", "show", f"{UNIT}.service",
                  "--property=Result,ExecMainStatus,ActiveState"), end="")
