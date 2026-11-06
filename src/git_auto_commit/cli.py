import argparse
import sys

from . import __version__, repositories, runner, systemd
from .config import repos_file
from .git import GitError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Automatic Git commits and upstream pushes")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("add", "remove"):
        sub = commands.add_parser(name)
        sub.add_argument("paths", nargs="+")
    for name in ("list", "run", "status", "install-timer", "check-environment", "uninstall"):
        commands.add_parser(name)
    schedule = commands.add_parser("schedule", help="Set a systemd OnCalendar expression")
    schedule.add_argument("expression")
    args = parser.parse_args(argv)
    try:
        if args.command in ("add", "remove"):
            failed = False
            for path in args.paths:
                try:
                    print(getattr(repositories, args.command)(path))
                except (GitError, OSError, ValueError) as error:
                    print(f"ERROR: {error}", file=sys.stderr)
                    failed = True
            return int(failed)
        if args.command == "list":
            print(f"List: {repos_file()}")
            for path in repositories.read_repositories():
                print(path)
        elif args.command == "run":
            return runner.run()
        elif args.command == "schedule":
            systemd.install(args.expression)
        elif args.command == "install-timer":
            systemd.install()
        elif args.command == "check-environment":
            systemd.preflight()
        elif args.command == "status":
            systemd.status()
        elif args.command == "uninstall":
            from .installation import uninstall

            uninstall()
        return 0
    except (GitError, OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
