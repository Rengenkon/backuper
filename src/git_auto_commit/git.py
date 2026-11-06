"""Bounded, noninteractive Git processes. No shell command interpolation."""

import os
import signal
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


class Git:
    def __init__(self, path, timeout=120):
        self.path = path
        self.timeout = timeout

    def run(self, *arguments, check=True):
        env = os.environ.copy()
        # Never inherit a caller's repository/index redirection.
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                    "GIT_NAMESPACE", "GIT_PREFIX"):
            env.pop(key, None)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15",
            "GCM_INTERACTIVE": "never",
            "LC_ALL": "C",
        })
        try:
            process = subprocess.Popen(
                ["git", *arguments], cwd=self.path, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise GitError(f"git {arguments[0]} timed out after {self.timeout}s") from None
        except OSError as error:
            raise GitError(str(error)) from error
        result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        if check and result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise GitError(f"git {arguments[0]} failed ({result.returncode}): {detail}")
        return result

    def root(self):
        if self.run("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            raise GitError("Not a working-tree repository")
        return self.run("rev-parse", "--show-toplevel").stdout.strip()

    def blocked_state(self):
        if self.run("ls-files", "--unmerged").stdout:
            return "unresolved conflicts"
        for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "REBASE_HEAD",
                       "rebase-merge", "rebase-apply", "sequencer", "BISECT_START"):
            value = self.run("rev-parse", "--git-path", marker).stdout.strip()
            path = Path(value)
            if not path.is_absolute():
                path = self.path / path
            if path.exists():
                return f"unfinished Git operation ({marker})"
        return None
