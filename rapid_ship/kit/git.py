"""git calls shared by the Kit commands."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
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


def changed_paths(root: Path) -> list[str]:
    """The uncommitted and untracked paths, in git status order: tracked changes first."""
    items = iter(git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0"))
    paths: list[str] = []
    for item in items:
        if not item:
            continue
        paths.append(os.fsdecode(item[3:]))  # "XY path"
        if b"R" in item[:2] or b"C" in item[:2]:
            next(items, None)  # a rename or copy names its source next
    return paths


def is_clean(root: Path) -> bool:
    return not changed_paths(root)


def head_branch(root: Path) -> str | None:
    """The checked-out branch, unborn or not; None for a detached HEAD."""
    name = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1))
    return os.fsdecode(name).strip() or None


def head_commit(root: Path) -> str | None:
    """HEAD's commit; None when the branch has no commits yet."""
    commit = git(root, "rev-parse", "--verify", "--quiet", "HEAD", allowed=(0, 1))
    return commit.decode().strip() or None


def commit_paths(root: Path, paths: Sequence[str], message: str) -> None:
    """Stage exactly paths, deletions included, and commit them.

    --no-verify skips the pre-commit and commit-msg hooks. git add fails on an ignored path, and
    git commit on a signing error or a missing identity; the caller undoes its writes.
    """
    git(root, "add", "--all", "--", *paths)
    git(root, "commit", "--no-verify", "--quiet", "--message", message)


def leave_branch(root: Path, base: str, branch: str, *, detached: bool = False) -> None:
    """Unstage everything, switch back to base and delete branch.

    The caller started from a clean tree, so the index holds only what it staged. base is a
    branch name, or a commit when detached.
    """
    git(root, "reset", "--quiet")
    git(root, "switch", "--quiet", *(["--detach"] if detached else []), base)
    git(root, "branch", "--quiet", "--delete", "--force", branch)
