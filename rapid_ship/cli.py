"""Command-line entry point. This first version reports only its version."""

import argparse
from collections.abc import Sequence
from importlib.metadata import version


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rapid-ship")
    release = f"rapid-ship {version('rapid-ship')}"
    parser.add_argument("--version", action="version", version=release)
    parser.parse_args(argv)
    parser.error("no command given; this version supports only --version")
