"""git calls shared by the Kit commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rapid_ship.kit.templates import KitError, KitRefusal


def git(
    root: Path,
    *args: str,
    stdin: bytes | None = None,
    allowed: tuple[int, ...] = (0,),
    literal: bool = True,
) -> bytes:
    """Run git in root and return stdout. Paths are literal, never pathspec patterns.

    check-ignore refuses --literal-pathspecs. It reads its paths from stdin, where they are
    literal anyway, so call it with literal=False.
    """
    command = ["git", *(["--literal-pathspecs"] if literal else []), *args]
    try:
        result = subprocess.run(command, cwd=root, input=stdin, capture_output=True, check=False)
    except OSError as error:
        raise KitError(f"cannot run git: {error}") from error
    if result.returncode not in allowed:
        raise KitError(f"git {args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def work_tree_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise KitError(f"cannot run git: {error}") from error
    if result.returncode != 0:
        raise KitRefusal(f"{start} is not inside a git work tree; run git init first")
    return Path(result.stdout.strip()).resolve()


def is_clean(root: Path) -> bool:
    return git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") == b""
