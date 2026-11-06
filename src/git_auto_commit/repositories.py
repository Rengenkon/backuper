"""The v1-compatible list: one absolute repository path per line."""

from pathlib import Path

from .config import atomic_write, repos_file
from .git import Git


def read_repositories():
    path = repos_file()
    if not path.exists():
        return []
    return list(dict.fromkeys(line for line in path.read_text(encoding="utf-8").splitlines() if line))


def normalize(value):
    path = Path(value).expanduser().resolve()
    if "\n" in str(path) or "\r" in str(path):
        raise ValueError("Repository paths cannot contain newlines")
    return path


def write_repositories(repositories):
    atomic_write(repos_file(), "".join(f"{path}\n" for path in repositories))


def add(value):
    path = normalize(value)
    root = normalize(Git(path).root())
    repositories = read_repositories()
    if str(root) in repositories:
        return f"Already tracked: {root}"
    repositories.append(str(root))
    write_repositories(repositories)
    return f"ADDED: {root}"


def remove(value):
    path = str(normalize(value))
    repositories = read_repositories()
    if path not in repositories:
        raise ValueError(f"Not tracked: {path}")
    write_repositories([entry for entry in repositories if entry != path])
    return f"REMOVED: {path}"
