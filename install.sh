#!/usr/bin/env bash
# Run as the target user, never through sudo.
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this installer as a normal user, without sudo." >&2
    exit 1
fi
for dependency in python3 git curl systemctl systemd-analyze; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "Required command not found: $dependency" >&2
        exit 1
    fi
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "Python 3.9+ is required")'

ref="${GIT_AUTO_COMMIT_REF:-v2}"
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
archive="$temporary/source.tar.gz"
echo "Downloading Rengenkon/backuper at $ref..."
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 15 --max-time 180 \
    "https://codeload.github.com/Rengenkon/backuper/tar.gz/$ref" --output "$archive"

python3 - "$archive" "$temporary/source" <<'PY'
import pathlib
import sys
import tarfile

archive, target = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
target.mkdir()
count = 0
total = 0
with tarfile.open(archive, "r:gz") as bundle:
    for member in bundle:
        parts = pathlib.PurePosixPath(member.name).parts
        if len(parts) < 4 or parts[1:3] != ("src", "git_auto_commit"):
            continue
        relative = pathlib.PurePosixPath(*parts[1:])
        if relative.is_absolute() or ".." in relative.parts or not member.isfile():
            raise SystemExit("Unsafe archive entry")
        if relative.suffix != ".py":
            continue
        count += 1
        total += member.size
        if count > 100 or total > 5_000_000:
            raise SystemExit("Unexpected archive size")
        output = target.joinpath(*relative.parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        stream = bundle.extractfile(member)
        if stream is None:
            raise SystemExit("Unreadable archive entry")
        output.write_bytes(stream.read())
required = ("__init__", "__main__", "cli", "config", "repositories", "git", "runner", "systemd", "installation")
for name in required:
    file = target / "src/git_auto_commit" / (name + ".py")
    if not file.is_file():
        raise SystemExit("Incomplete download: " + str(file))
    compile(file.read_bytes(), str(file), "exec")
PY

export PYTHONPATH="$temporary/source/src"
python3 -m git_auto_commit check-environment
python3 - "$temporary/source/src" <<'PY'
import sys
from git_auto_commit.installation import install
install(sys.argv[1])
PY
"$HOME/.local/bin/git-auto-commit" install-timer

echo "Installation complete. Repository list and existing settings preserved."
echo "Logs: journalctl --user -u git-auto-commit.service"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo 'Add ~/.local/bin to PATH, for example: export PATH="$HOME/.local/bin:$PATH"' ;;
esac
