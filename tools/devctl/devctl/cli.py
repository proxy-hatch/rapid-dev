"""devctl's command line: core commands, plus the project's verbs from devctl_project."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

import devctl_project
from devctl import __version__
from devctl.repo import RepoError
from devctl.settings import SettingsError

Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devctl", description="This repository's developer CLI.")
    parser.add_argument("--version", action="version", version=f"devctl {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    devctl_project.register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.error(f"{args.command} does not set a handler")
    try:
        return handler(args)
    except (RepoError, SettingsError) as error:
        print(f"devctl: {error}", file=sys.stderr)
        return 2
