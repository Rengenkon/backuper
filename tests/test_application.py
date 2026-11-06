"""No real HOME/config, Git identity, remote, or user bus is used by these tests."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from git_auto_commit import config, installation, repositories, systemd
from git_auto_commit.git import Git, GitError

SOURCE = Path(__file__).resolve().parents[1]


class Sandbox(unittest.TestCase):
    def setUp(self):
        base = Path("/tmp/opencode")
        base.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-auto-commit-test-", dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path("/tmp")))
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.template = self.root / "empty-template"
        self.template.mkdir()
        # Entire environment replaced, not just selected variables overlaid.
        environment = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_RUNTIME_DIR": str(self.root / "runtime"),
            "TMPDIR": str(self.root),
            "PATH": f"{self.bin}:/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": str(self.root / "source/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(self.root / "gitconfig"),
            "GIT_ALLOW_PROTOCOL": "file",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Sandbox Test",
            "GIT_AUTHOR_EMAIL": "sandbox@example.invalid",
            "GIT_COMMITTER_NAME": "Sandbox Test",
            "GIT_COMMITTER_EMAIL": "sandbox@example.invalid",
            "GIT_TEMPLATE_DIR": str(self.template),
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={self.root}/nonexistent-bus",
            "TEST_ROOT": str(self.root),
            "LC_ALL": "C",
        }
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
            Path(os.environ[key]).mkdir(mode=0o700)
        (self.root / "gitconfig").write_text(
            f"[core]\n\thooksPath = {self.template}\n[commit]\n\tgpgSign = false\n"
            "[tag]\n\tgpgSign = false\n", encoding="utf-8")
        shutil.copytree(SOURCE / "src", self.root / "source/src",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(SOURCE / "install.sh", self.root / "source/install.sh")
        self.fake("systemctl", """
import json, os, pathlib, sys
root = pathlib.Path(os.environ['TEST_ROOT'])
with (root / 'systemctl.jsonl').open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('FAIL_SYSTEMCTL'):
    sys.exit('simulated user manager failure')
print('sandbox systemctl')
""")
        # Defense in depth: any Git process outside the sandbox is rejected,
        # including Git launched by the CLI or installer, not just test helpers.
        real_git = shutil.which("git", path="/usr/bin:/bin")
        self.fake("git", f"""
import os, pathlib, sys
root = pathlib.Path(os.environ['TEST_ROOT']).resolve()
assert pathlib.Path.cwd().resolve().is_relative_to(root), 'Git outside sandbox'
assert pathlib.Path(os.environ['GIT_CONFIG_GLOBAL']).resolve().is_relative_to(root)
os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])
""")
        old_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old_cwd)

    def safe(self, path):
        self.assertTrue(Path(path).resolve().is_relative_to(self.root), f"Unsafe test path: {path}")

    def fake(self, name, script):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{script}", encoding="utf-8")
        path.chmod(0o755)

    def git(self, path, *args):
        self.safe(path)
        return Git(path).run(*args).stdout.strip()

    def repo(self, name="репозиторий with spaces", initial=True):
        path = self.root / name
        self.safe(path)
        path.mkdir()
        self.git(path, "init", "--quiet", "--initial-branch=main")
        if initial:
            (path / "file.txt").write_text("initial\n")
            self.git(path, "add", ".")
            self.git(path, "commit", "--quiet", "-m", "initial")
        return path

    def remote(self, repo):
        remote = self.root / (repo.name + "-remote.git")
        remote.mkdir()
        self.git(remote, "init", "--bare", "--quiet")
        self.git(repo, "remote", "add", "backup", str(remote))
        self.git(repo, "push", "--quiet", "--set-upstream", "backup", "HEAD:refs/heads/saved")
        return remote

    def cli(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-m", "git_auto_commit", *map(str, arguments)],
                                cwd=self.root, env=os.environ.copy(), capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def run_backup(self, expected=0):
        for entry in repositories.read_repositories():
            self.safe(entry)
        self.safe(config.repos_file())
        return self.cli("run", expected=expected)


class RepositoryTests(Sandbox):
    def test_add_duplicate_subdirectory_and_remove_last(self):
        repo = self.repo()
        sub = repo / "sub"
        sub.mkdir()
        self.cli("add", sub)
        self.cli("add", repo)
        self.assertEqual(repositories.read_repositories(), [str(repo)])
        self.cli("remove", repo)
        self.assertEqual(config.repos_file().read_text(), "")

    def test_remove_deleted_directory(self):
        repo = self.repo()
        self.cli("add", repo)
        self.safe(repo)
        shutil.rmtree(repo)
        self.cli("remove", repo)
        self.assertEqual(repositories.read_repositories(), [])

    def test_existing_list_and_worktree(self):
        repo = self.repo()
        worktree = self.root / "worktree"
        self.git(repo, "worktree", "add", "-b", "other", str(worktree))
        config.atomic_write(config.repos_file(), str(repo) + "\n")
        self.cli("add", worktree)
        self.assertEqual(repositories.read_repositories(), [str(repo), str(worktree)])
        (worktree / "new.txt").write_text("worktree")
        self.assertIn("COMMITTED", self.run_backup())

    def test_missing_list_not_created_by_read(self):
        self.cli("list")
        self.assertFalse(config.repos_file().exists())

    def test_invalid_repository_and_newline(self):
        self.cli("add", self.root, expected=1)
        with self.assertRaises(ValueError):
            repositories.normalize(self.root / "a\nb")

    def test_relative_xdg_rejected(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}):
            self.cli("list", expected=1)

    def test_failed_atomic_write_preserves_original(self):
        config.atomic_write(config.repos_file(), "original\n")
        with patch.object(Path, "replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                config.atomic_write(config.repos_file(), "replacement\n")
        self.assertEqual(config.repos_file().read_text(), "original\n")


class BackupTests(Sandbox):
    def test_commit_push_different_remote_branch_and_clean_rerun(self):
        repo = self.repo()
        remote = self.remote(repo)
        self.cli("add", repo)
        (repo / "file.txt").write_text("modified")
        (repo / "new.txt").write_text("new")
        output = self.run_backup()
        self.assertIn("COMMITTED", output)
        self.assertIn("PUSHED", output)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"),
                         self.git(remote, "rev-parse", "refs/heads/saved"))
        self.assertNotIn("COMMITTED", self.run_backup())

    def test_push_preexisting_commit_without_changes(self):
        repo = self.repo()
        self.remote(repo)
        self.git(repo, "commit", "--allow-empty", "-m", "pending")
        self.cli("add", repo)
        output = self.run_backup()
        self.assertNotIn("COMMITTED", output)
        self.assertIn("PUSHED", output)

    def test_initial_commit_without_upstream(self):
        repo = self.repo(initial=False)
        self.cli("add", repo)
        (repo / "new.txt").write_text("initial")
        output = self.run_backup()
        self.assertIn("COMMITTED", output)
        self.assertIn("no resolvable upstream", output)
        self.assertEqual(self.git(repo, "rev-list", "--count", "HEAD"), "1")

    def test_detached_and_unfinished_merge_are_not_committed(self):
        repo = self.repo()
        self.cli("add", repo)
        head = self.git(repo, "rev-parse", "HEAD")
        self.git(repo, "checkout", "--detach")
        (repo / "new.txt").write_text("do not commit")
        self.assertIn("detached HEAD", self.run_backup())
        self.git(repo, "checkout", "main")
        (repo / ".git/MERGE_HEAD").write_text(head + "\n")
        self.assertIn("unfinished Git operation", self.run_backup())
        self.assertEqual(head, self.git(repo, "rev-parse", "HEAD"))

    def test_conflict_is_skipped(self):
        repo = self.repo()
        self.git(repo, "checkout", "-b", "other")
        (repo / "file.txt").write_text("other\n")
        self.git(repo, "commit", "-am", "other")
        self.git(repo, "checkout", "main")
        (repo / "file.txt").write_text("main\n")
        self.git(repo, "commit", "-am", "main")
        result = Git(repo).run("merge", "other", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.cli("add", repo)
        self.assertIn("unresolved conflicts", self.run_backup())

    def test_failed_commit_continues_to_next_repository(self):
        broken = self.repo("broken")
        healthy = self.repo("healthy")
        hook = self.root / "failing-hooks"
        hook.mkdir()
        (hook / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
        (hook / "pre-commit").chmod(0o755)
        self.git(broken, "config", "core.hooksPath", str(hook))
        self.cli("add", broken, healthy)
        for repo in (broken, healthy):
            (repo / "new.txt").write_text("new")
        output = self.run_backup(expected=1)
        self.assertIn("failed=1", output)
        self.assertIn(f"{healthy}: COMMITTED", output)

    def test_failed_push_is_reported_without_losing_commit(self):
        repo = self.repo()
        remote = self.remote(repo)
        self.cli("add", repo)
        self.git(repo, "config", "remote.backup.url", str(self.root / "missing.git"))
        (repo / "new.txt").write_text("new")
        self.assertIn("ERROR", self.run_backup(expected=1))
        self.assertEqual(self.git(repo, "rev-list", "--count", "HEAD"), "2")
        self.assertEqual(self.git(remote, "rev-list", "--count", "refs/heads/saved"), "1")

    def test_push_does_not_mirror_or_send_tags(self):
        repo = self.repo()
        remote = self.remote(repo)
        self.git(repo, "config", "remote.backup.mirror", "true")
        self.git(repo, "config", "push.followTags", "true")
        self.git(repo, "tag", "-a", "private-tag", "-m", "do not push")
        self.git(repo, "branch", "private-branch")
        (repo / "new.txt").write_text("new")
        self.cli("add", repo)
        self.assertIn("PUSHED", self.run_backup())
        self.assertEqual(self.git(remote, "for-each-ref", "--format=%(refname)"), "refs/heads/saved")

    def test_remote_divergence_is_rejected_without_force(self):
        repo = self.repo()
        remote = self.remote(repo)
        peer = self.root / "peer"
        self.git(self.root, "clone", "--quiet", "--branch", "saved", str(remote), str(peer))
        (peer / "peer.txt").write_text("remote change")
        self.git(peer, "add", ".")
        self.git(peer, "commit", "-m", "remote change")
        self.git(peer, "push")
        remote_head = self.git(remote, "rev-parse", "refs/heads/saved")
        self.cli("add", repo)
        (repo / "local.txt").write_text("local change")
        self.assertIn("ERROR", self.run_backup(expected=1))
        self.assertEqual(self.git(remote, "rev-parse", "refs/heads/saved"), remote_head)
        self.assertEqual(self.git(repo, "rev-list", "--count", "HEAD"), "2")

    def test_deletions_staged_changes_and_ignored_files(self):
        repo = self.repo()
        self.remote(repo)
        self.cli("add", repo)
        (repo / "file.txt").unlink()
        (repo / ".gitignore").write_text("secret.txt\n")
        (repo / "secret.txt").write_text("not for git")
        (repo / "staged.txt").write_text("staged")
        self.git(repo, "add", "staged.txt")
        self.assertIn("PUSHED", self.run_backup())
        files = self.git(repo, "ls-tree", "--name-only", "HEAD").splitlines()
        self.assertEqual(files, [".gitignore", "staged.txt"])

    def test_timeout_kills_process(self):
        self.fake("git", "import time\ntime.sleep(20)\n")
        with self.assertRaisesRegex(GitError, "timed out"):
            Git(self.root, timeout=0.1).run("status")

    def test_missing_repository_does_not_stop_rest(self):
        repo = self.repo()
        config.atomic_write(config.repos_file(), f"{self.root / 'missing'}\n{repo}\n")
        (repo / "new.txt").write_text("new")
        self.assertIn("COMMITTED", self.run_backup(expected=1))


class TimerTests(Sandbox):
    def test_schedule_and_persistence_with_fake_user_manager(self):
        self.cli("schedule", "daily")
        service = (config.unit_dir() / "git-auto-commit.service").read_text()
        timer = (config.unit_dir() / "git-auto-commit.timer").read_text()
        self.assertIn("Type=oneshot", service)
        self.assertIn(str(config.config_dir().parent), service)
        self.assertIn("Persistent=true", timer)
        self.assertIn("OnCalendar=daily", timer)
        self.assertEqual(config.load_settings()["schedule"], "daily")
        calls = [json.loads(line) for line in (self.root / "systemctl.jsonl").read_text().splitlines()]
        self.assertTrue(all(call[0] == "--user" for call in calls))
        self.assertIn(["--user", "restart", "git-auto-commit.timer"], calls)

    def test_invalid_cron_does_not_write_units(self):
        self.cli("schedule", "0 3 * * *", expected=1)
        self.assertFalse(config.unit_dir().exists())

    def test_unit_injection_rejected(self):
        with self.assertRaises(ValueError):
            systemd.validate_schedule("daily\nOnBootSec=1")
        text = systemd.service_text(self.root / 'x%$"\\.bin')
        self.assertIn("%%$$", text)
        self.assertIn('\\"', text)

    def test_systemctl_failure_is_not_success(self):
        with patch.dict(os.environ, {"FAIL_SYSTEMCTL": "1"}):
            self.cli("install-timer", expected=1)
        self.assertFalse(config.settings_file().exists())

    def test_invalid_settings(self):
        config.atomic_write(config.settings_file(), '{"git_timeout": -1}')
        self.cli("run", expected=1)


class InstallationTests(Sandbox):
    def make_archive(self):
        archive = self.root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(self.root / "source/src", arcname="backuper-v2/src")
        self.fake("curl", """
import os, pathlib, shutil, sys
root = pathlib.Path(os.environ['TEST_ROOT'])
target = pathlib.Path(sys.argv[sys.argv.index('--output') + 1]).resolve()
assert target.is_relative_to(root)
if os.environ.get('FAIL_DOWNLOAD'):
    sys.exit('simulated download failure')
shutil.copyfile(root / 'source.tar.gz', target)
""")

    def installer(self, expected=0):
        result = subprocess.run(["bash", str(self.root / "source/install.sh")],
                                cwd=self.root, env=os.environ.copy(), capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_install_update_run_and_uninstall_preserve_existing_list(self):
        if os.geteuid() == 0:
            self.skipTest("Installer intentionally refuses root")
        self.make_archive()
        repo = self.repo()
        remote = self.remote(repo)
        # A synthetic v1-format list, NOT copied from the user's configuration.
        original = str(repo) + "\n"
        config.atomic_write(config.repos_file(), original)
        self.installer()
        self.assertEqual(config.repos_file().read_text(), original)
        executable = config.command_path()
        self.safe(executable)
        self.assertTrue(os.access(executable, os.X_OK))
        self.assertFalse(executable.is_symlink())
        self.cli("schedule", "daily")
        self.installer()
        self.assertEqual(config.load_settings()["schedule"], "daily")
        self.assertEqual(config.repos_file().read_text(), original)
        # Make the installed entry point prove it does not need the source copy.
        shutil.rmtree(self.root / "source")
        env = os.environ.copy()
        env.pop("PYTHONPATH")
        (repo / "new.txt").write_text("installed program")
        result = subprocess.run([str(executable), "run"], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PUSHED", result.stdout)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"),
                         self.git(remote, "rev-parse", "refs/heads/saved"))
        result = subprocess.run([str(executable), "uninstall"], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(executable.exists())
        self.assertFalse(config.data_dir().exists())
        self.assertEqual(config.repos_file().read_text(), original)
        self.assertTrue(repo.is_dir())

    def test_failed_download_leaves_previous_installation(self):
        if os.geteuid() == 0:
            self.skipTest("Installer intentionally refuses root")
        self.make_archive()
        self.installer()
        before = config.command_path().read_bytes()
        with patch.dict(os.environ, {"FAIL_DOWNLOAD": "1"}):
            self.installer(expected=1)
        self.assertEqual(config.command_path().read_bytes(), before)

    def test_incomplete_archive_does_not_replace_installation(self):
        if os.geteuid() == 0:
            self.skipTest("Installer intentionally refuses root")
        self.make_archive()
        self.installer()
        before = config.command_path().read_bytes()
        with tarfile.open(self.root / "source.tar.gz", "w:gz") as bundle:
            bundle.add(self.root / "source/src/git_auto_commit/__init__.py",
                       arcname="backuper-v2/src/git_auto_commit/__init__.py")
        self.installer(expected=1)
        self.assertEqual(config.command_path().read_bytes(), before)

    def test_archive_traversal_is_rejected(self):
        if os.geteuid() == 0:
            self.skipTest("Installer intentionally refuses root")
        self.make_archive()
        with tarfile.open(self.root / "source.tar.gz", "w:gz") as bundle:
            bundle.add(self.root / "source/src/git_auto_commit/__init__.py",
                       arcname="backuper-v2/src/git_auto_commit/../../escape.py")
        self.installer(expected=1)
        self.assertFalse(config.command_path().exists())
        self.assertFalse((self.root / "escape.py").exists())

    def test_timer_activation_failure_reports_install_failure(self):
        if os.geteuid() == 0:
            self.skipTest("Installer intentionally refuses root")
        self.make_archive()
        # Preflight succeeds; enabling the timer fails after code staging.
        self.fake("systemctl", """
import sys
if 'enable' in sys.argv:
    sys.exit('simulated enable failure')
print('sandbox systemctl')
""")
        result = self.installer(expected=1)
        self.assertNotIn("Installation complete", result.stdout)
        self.assertFalse(config.settings_file().exists())

    def test_unrelated_command_not_overwritten(self):
        path = config.command_path()
        path.parent.mkdir(parents=True)
        path.write_text("unrelated command")
        with self.assertRaises(ValueError):
            installation.install(self.root / "source/src")
        self.assertEqual(path.read_text(), "unrelated command")


if __name__ == "__main__":
    unittest.main()
