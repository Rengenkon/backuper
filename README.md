# git-auto-commit v2

Automatic commits and pushes for selected Git repositories. Python standard library only;
no pip, virtual environment, clone, sudo, or permanent background process required.

## Install / update

Requirements: Linux, Python **3.9+**, Git, curl, and a working **user systemd manager**.
Run as your normal user:

```bash
curl -fsSL --proto '=https' --proto-redir '=https' https://raw.githubusercontent.com/Rengenkon/backuper/v2/install.sh | bash
```

This URL will work once the `v2` branch is published. The installer downloads that branch
over HTTPS. Installing from a branch trusts its current contents; for a reproducible
installation, use a trusted release tag in both the installer URL and
`GIT_AUTO_COMMIT_REF`. You can inspect the installer before executing it.

Repeat the command to update. Settings and the existing repository list are preserved.
Complete version directories are staged before the command is switched; previous version
directories are retained until uninstall. An interrupted download does not replace the
installed command. If timer activation fails, the installer reports failure; fix the
reported problem and rerun it.

If necessary, add this to your shell configuration:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Usage

```bash
git-auto-commit add /absolute/path/to/repository
git-auto-commit list
git-auto-commit remove /absolute/path/to/repository
git-auto-commit run
git-auto-commit schedule daily
git-auto-commit schedule 'Mon,Thu *-*-* 02:30:00'
git-auto-commit status
git-auto-commit --version
```

Add/remove accept multiple paths. Adding a subdirectory registers its repository root.
Worktrees are supported. Bare repositories are not. Remove a deleted repository by its
original absolute path.

**Warning:** every nonignored change is staged with `git add --all`, including existing
staged changes, deletions, untracked files and potentially secrets. Configure `.gitignore`
and only register repositories where this policy is appropriate. Hooks still run; a failed
commit can leave changes staged. This is not a full backup: ignored files and uncommitted
submodule contents are not saved.

Runs process repositories sequentially. Detached HEAD, conflicts and unfinished Git
operations are skipped with a warning. Failed repositories do not stop the rest; any failure
produces exit code 1. Skips are reported separately and are not errors.

Any active branch is eligible. Push uses its **configured upstream**, even when its remote
or branch name differs. Without a resolvable upstream, local commits are still made but
push is skipped. Configure tracking yourself using Git. No force push, automatic pull,
merge, reset, or upstream creation is performed. No remote fetch is done: the ahead check
uses the local upstream reference; remote divergence can cause a normal rejected push.

Git processes have a 120-second timeout, including their hooks and helpers. Terminal
prompts are disabled. SSH uses BatchMode and strict host-key checking: configure credentials
and trust the host manually first. Standard SSH config and available agents are used;
an agent available in your shell is not necessarily available to user systemd.
Password-only authentication cannot work unattended.

## Scheduling

The default is systemd `weekly`. Use systemd **OnCalendar**, not cron expressions.
Schedules are checked with `systemd-analyze calendar` before saving.

The timer uses `Persistent=true`: if an event was missed while the user manager was
inactive, one catch-up run happens when the timer is next activated, normally at login.
Multiple missed events do not trigger multiple runs. Linger and sudo are not required.
Exact execution time is not guaranteed. Logging in before any event has been missed does
not itself trigger a backup. Parallel manual runs are unsupported; do not run manually
while the timer's service is active.

```bash
journalctl --user -u git-auto-commit.service
systemctl --user list-timers --all git-auto-commit.timer
```

`settings.json` contains `schedule` and `git_timeout` (seconds, >0 and <=3600).
Use the schedule command to update both settings and timer units.

## Files

| Purpose | Default path |
| --- | --- |
| Application versions | `~/.local/share/git-auto-commit/` |
| Command | `~/.local/bin/git-auto-commit` |
| Repository list | `~/.config/git-auto-commit/repos.list` |
| Settings | `~/.config/git-auto-commit/settings.json` |
| User units | `~/.config/systemd/user/git-auto-commit.{service,timer}` |

`XDG_CONFIG_HOME` and `XDG_DATA_HOME` override their respective base directories and must
be absolute. Keep them consistent for installation, commands and the user systemd manager.
The v1 list (one absolute path per line) is used **in place**, never replaced by the
installer. The other v1 commands and scripts are not retained. If migrating from v1,
its obsolete `/usr/local/bin/git-manager` and `git-committer` links are not modified;
the v2 installer never changes privileged files.

## Uninstall

```bash
git-auto-commit uninstall
```

Disables the timer, stops the service and removes managed application files. Repository
list, settings, journal entries and systemd timer persistence state are preserved.
Repositories themselves are never deleted. There is deliberately no purge-data command.

## Development / tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use a fresh directory under `/tmp/opencode`, isolated HOME, XDG paths, Git configuration
and local-only remotes. They never read/copy the real repository list or connect to real
user systemd. Unit management is tested with command substitutes; genuine login catch-up
requires a separate disposable Linux user/session and is not exercised on your account.
