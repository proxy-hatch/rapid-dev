"""The kit step: the lock is readable and every managed file that is not excluded is present.

devctl cannot import rapid_ship, so this module reads .rapid-ship/kit.lock itself and ignores
its [variables] table. [kit] exclude in project.toml is the only record of an exclusion. A Kit
file the project edited or deleted has a seeded entry after rapid-ship sync, so it is the
project's own and never required.
"""

from __future__ import annotations

import stat
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from devctl.check.steps import CheckContext, StepResult, Tier, failed, passed

LOCK_PATH = ".rapid-ship/kit.lock"

_STACKS = ("python", "agnostic")
_KINDS = ("managed", "seeded")


class KitLockError(Exception):
    """The Kit lock is missing or invalid."""


@dataclass(frozen=True)
class _LockFile:
    path: str
    kind: str
    sha256: str | None
    link: str | None


def is_excluded(path: str, excluded: Sequence[str]) -> bool:
    """A copy of rapid_ship.kit.templates.is_excluded; test_is_excluded_matches_the_cli pins it.

    True when path is an entry of [kit] exclude or lies below one. Excluding a skill
    directory also excludes its .claude/skills link.
    """
    parts = PurePosixPath(path).parts
    link = len(parts) == 3 and parts[:2] == (".claude", "skills")
    return (link and _covered(f".agents/skills/{parts[2]}", excluded)) or _covered(path, excluded)


def _covered(path: str, excluded: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(f"{entry}/") for entry in excluded)


def _lock_error(reason: object) -> KitLockError:
    return KitLockError(f"{LOCK_PATH}: {reason}")


def _read_lock(root: Path) -> dict[str, object]:
    try:
        return tomllib.loads((root / LOCK_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise _lock_error("missing; run rapid-ship init") from None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise _lock_error(error) from error


def _lock_file(item: object, number: int) -> _LockFile:
    where = f"[[file]] #{number}"
    if not isinstance(item, dict):
        raise _lock_error(f"{where}: expected a table")
    path, kind = item.get("path"), item.get("kind")
    if not isinstance(path, str):
        raise _lock_error(f"{where}: path must be a string")
    if kind not in _KINDS:
        raise _lock_error(f"{where} ({path}): kind must be managed or seeded")
    sha256, link = item.get("sha256"), item.get("link")
    sha256 = sha256 if isinstance(sha256, str) else None
    link = link if isinstance(link, str) else None
    if kind == "managed" and sha256 is None and link is None:
        raise _lock_error(f"{where} ({path}): a managed entry needs sha256 or link")
    return _LockFile(path, kind, sha256, link)


def _entries(root: Path) -> tuple[_LockFile, ...]:
    """The lock's [[file]] entries in lock order. Raises KitLockError if the lock is unreadable."""
    data = _read_lock(root)
    if not isinstance(data.get("kit_version"), str):
        raise _lock_error("kit_version must be a string")
    if data.get("stack") not in _STACKS:
        raise _lock_error("stack must be python or agnostic")
    items = data.get("file", [])
    if not isinstance(items, list):
        raise _lock_error("file must be a list of [[file]] entries")
    return tuple(_lock_file(item, number) for number, item in enumerate(items, start=1))


def _managed(root: Path, excluded: Sequence[str]) -> list[_LockFile]:
    return [
        entry
        for entry in _entries(root)
        if entry.kind == "managed" and not is_excluded(entry.path, excluded)
    ]


def managed_paths(root: Path, excluded: Sequence[str]) -> frozenset[str]:
    """The managed paths in the lock, less those the project owns under [kit] exclude."""
    return frozenset(entry.path for entry in _managed(root, excluded))


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _problem(root: Path, entry: _LockFile) -> str | None:
    """What is wrong with a managed entry's path on disk, or None when it is as the lock says."""
    target = root / entry.path
    if entry.link is not None:
        present, noun = target.is_symlink(), "link"
    else:
        present, noun = _is_regular_file(target), "file"
    if present:
        return None
    return (
        f"{entry.path}: managed {noun} is missing; rapid-ship sync --revert {entry.path} "
        "restores it, and rapid-ship sync keeps the deletion as the project's own"
    )


class KitStep:
    name = "kit"
    tier: Tier = "fast"

    def run(self, context: CheckContext) -> StepResult:
        root = context.repo.root
        try:
            managed = _managed(root, context.project.excluded)
        except KitLockError as error:
            return failed(self.name, str(error))
        problems = [problem for entry in managed if (problem := _problem(root, entry))]
        return failed(self.name, *problems) if problems else passed(self.name)
