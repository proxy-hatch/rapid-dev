"""git calls shared by the Kit commands."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from rapid_ship.kit.templates import KitError, KitRefusal

# No hook runs from a Kit command: a hooks path such as husky's .husky/ is project code, and
# --no-verify would skip only pre-commit and commit-msg, not post-checkout, post-commit,
# prepare-commit-msg or reference-transaction. git finds no hook below /dev/null.
_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")


def git(
    root: Path,
    *args: str,
    stdin: bytes | None = None,
    allowed: tuple[int, ...] = (0,),
    literal: bool = True,
) -> bytes:
    """Run git in root, with no hook, and return stdout. Paths are literal, never patterns.

    check-ignore refuses --literal-pathspecs. It reads its paths from stdin, where they are
    literal anyway, so call it with literal=False.
    """
    command = ["git", *_NO_HOOKS, *(["--literal-pathspecs"] if literal else []), *args]
    return _run(root, command, args[0], stdin, allowed)


def _run(
    root: Path, command: list[str], name: str, stdin: bytes | None, allowed: tuple[int, ...]
) -> bytes:
    try:
        result = subprocess.run(command, cwd=root, input=stdin, capture_output=True, check=False)
    except OSError as error:
        raise KitError(f"cannot run git: {error}") from error
    if result.returncode not in allowed:
        message = result.stderr.decode(errors="replace").strip()
        raise KitError(f"git {name} failed: {message or f'exit status {result.returncode}'}")
    return result.stdout


def hooks_setup(root: Path) -> tuple[str, Path]:
    """The configured core.hooksPath ("" when unset) and the directory git runs hooks from.

    git() hides both behind its own core.hooksPath override, so these two read-only calls run
    without it. Neither runs a hook, and no other call may skip the override.
    """
    configured = _run(root, ["git", "config", "--get", "core.hooksPath"], "config", None, (0, 1))
    directory = _run(
        root,
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
        "rev-parse",
        None,
        (0,),
    )
    return os.fsdecode(configured).strip(), Path(os.fsdecode(directory).rstrip("\n"))


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
    """Stage exactly paths, deletions included, and commit them. git() runs no hook.

    git add fails on an ignored path, and git commit on a signing error or a missing identity;
    the caller undoes its writes.
    """
    git(root, "add", "--all", "--", *paths)
    git(root, "commit", "--quiet", "--message", message)


def leave_branch(root: Path, base: str, branch: str, *, detached: bool = False) -> None:
    """Unstage everything, switch back to base and delete branch.

    The caller started from a clean tree, so the index holds only what it staged. base is a
    branch name, or a commit when detached. Switching to base also works when the switch to
    branch failed, whether or not git had switched.
    """
    git(root, "reset", "--quiet")
    git(root, "switch", "--quiet", *(["--detach"] if detached else []), base)
    git(root, "branch", "--quiet", "--delete", "--force", branch)
