"""Sequential backup runs with per-repository failures and a final summary."""

from datetime import datetime
from pathlib import Path

from .config import load_settings
from .git import Git, GitError
from .repositories import read_repositories


def process_repository(path, timeout, report):
    if not path.is_absolute() or not path.is_dir():
        raise GitError("Repository path must be an existing absolute directory")
    git = Git(path, timeout)
    if Path(git.root()).resolve() != path.resolve():
        raise GitError("Tracked directory is not the repository root; add it again")
    branch = git.run("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode:
        report("SKIPPED: detached HEAD")
        return "skipped"
    blocked = git.blocked_state()
    if blocked:
        report(f"SKIPPED: {blocked}")
        return "skipped"
    if git.run("status", "--porcelain", "--untracked-files=all").stdout:
        git.run("add", "--all", "--", ".")
        # A dirty submodule can appear in status without anything committable.
        staged = git.run("diff", "--cached", "--quiet", check=False)
        if staged.returncode not in (0, 1):
            raise GitError("Cannot inspect staged changes")
        if staged.returncode == 1:
            message = f"Auto-backup {datetime.now().astimezone():%Y-%m-%d %H:%M:%S %z}"
            git.run("commit", "--quiet", "-m", message)
            report(f"COMMITTED: {branch.stdout.strip()}")
        else:
            report("WARNING: working-tree changes cannot be staged (check submodules)")
    upstream = git.run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if upstream.returncode:
        report("SKIPPED PUSH: no resolvable upstream; configure it manually")
        return "skipped"
    ahead = int(git.run("rev-list", "--count", "@{upstream}..HEAD").stdout.strip())
    if not ahead:
        report("UP-TO-DATE: no unpushed commits (relative to local upstream reference)")
        return "ok"
    # Ignore push.default, pushRemote and custom push refspecs: send only HEAD to
    # the configured upstream's remote and branch, never another destination.
    name = branch.stdout.strip()
    remote = git.run("config", "--get", f"branch.{name}.remote").stdout.strip()
    target = git.run("config", "--get-all", f"branch.{name}.merge").stdout.splitlines()
    if remote == "." or len(target) != 1 or not target[0].startswith("refs/heads/"):
        raise GitError("Upstream must be a single branch on an external remote")
    git.run("-c", f"remote.{remote}.mirror=false", "push", "--quiet", "--no-force",
            "--no-follow-tags", "--recurse-submodules=no", "--",
            remote, f"HEAD:{target[0]}")
    report(f"PUSHED: {ahead} commit(s) to {upstream.stdout.strip()}")
    return "ok"


def run():
    timeout = load_settings()["git_timeout"]
    repositories = read_repositories()
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    actions = {"committed": 0, "pushed": 0}
    print(f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}", flush=True)
    for entry in repositories:
        def report(message):
            if message.startswith("COMMITTED:"):
                actions["committed"] += 1
            elif message.startswith("PUSHED:"):
                actions["pushed"] += 1
            print(f"{entry}: {message}", flush=True)

        try:
            result = process_repository(Path(entry), timeout, report)
            counts[result] += 1
        except (GitError, OSError, ValueError) as error:
            counts["failed"] += 1
            report(f"ERROR: {error}")
    print(f"Finished: total={len(repositories)}, ok={counts['ok']}, "
          f"skipped={counts['skipped']}, failed={counts['failed']}, "
          f"committed={actions['committed']}, pushed={actions['pushed']}", flush=True)
    return 1 if counts["failed"] else 0
