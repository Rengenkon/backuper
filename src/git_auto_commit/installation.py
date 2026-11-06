"""Narrowly scoped installation / removal helpers."""

from pathlib import Path
import shutil
import sys
import tempfile

from .config import atomic_write, command_path, data_dir, unit_dir
from .systemd import UNIT, command

MARKER = ".git-auto-commit-v2"


def install(source):
    destination = data_dir()
    if destination.is_symlink():
        raise ValueError(f"Refusing symlink installation directory: {destination}")
    if destination.exists() and not (destination / MARKER).is_file():
        raise ValueError(f"Refusing to overwrite unrecognized directory: {destination}")
    executable = command_path()
    if executable.exists() or executable.is_symlink():
        if executable.is_symlink() or "# git-auto-commit v2 launcher" not in executable.read_text():
            raise ValueError(f"Refusing to overwrite unrelated command: {executable}")
    # Stage complete versions before atomically switching the launcher.
    destination.mkdir(parents=True, exist_ok=True)
    atomic_write(destination / MARKER, "Managed by git-auto-commit v2\n")
    version = Path(tempfile.mkdtemp(prefix="version-", dir=destination))
    try:
        shutil.copytree(Path(source) / "git_auto_commit", version / "git_auto_commit")
        atomic_write(version / MARKER, "Managed application version\n")
        launcher = (f"#!{sys.executable}\n# git-auto-commit v2 launcher\n"
                    "import sys\n"
                    f"sys.path.insert(0, {str(version)!r})\n"
                    "from git_auto_commit.cli import main\n"
                    "raise SystemExit(main())\n")
        atomic_write(executable, launcher, mode=0o755)
    except BaseException:
        shutil.rmtree(version)
        raise
    print(f"Installed command: {executable}")
    print(f"Application: {version}")


def uninstall():
    destination = data_dir()
    executable = command_path()
    if destination.is_symlink() or not (destination / MARKER).is_file():
        raise ValueError(f"Not a managed installation: {destination}")
    if executable.is_symlink() or not executable.is_file() or "# git-auto-commit v2 launcher" not in executable.read_text():
        raise ValueError(f"Not a managed command: {executable}")
    command("systemctl", "--user", "disable", "--now", f"{UNIT}.timer")
    command("systemctl", "--user", "stop", f"{UNIT}.service")
    for suffix in ("service", "timer"):
        (unit_dir() / f"{UNIT}.{suffix}").unlink(missing_ok=True)
    command("systemctl", "--user", "daemon-reload")
    executable.unlink()
    for entry in destination.glob("version-*"):
        if not entry.is_symlink() and entry.is_dir() and (entry / MARKER).is_file():
            shutil.rmtree(entry)
    (destination / MARKER).unlink()
    try:
        destination.rmdir()
    except OSError:
        pass
    print("Uninstalled. Repository list and settings have been preserved.")
