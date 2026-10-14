"""rapid-ship init: vendor the Kit into a repository. It creates files and never replaces one."""

from __future__ import annotations

import contextlib
import keyword
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rapid_ship.files import UnsafePath, create_file, safe_path
from rapid_ship.kit.git import git, is_clean, work_tree_root
from rapid_ship.kit.lock import LOCK_PATH, Lock, entry_for, write_lock
from rapid_ship.kit.status import locate
from rapid_ship.kit.templates import (
    KitError,
    KitRefusal,
    Stack,
    Template,
    installed_version,
    load_manifest,
    render_files,
    render_path,
)

_PROJECT_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")  # PEP 508 name
_LOGIN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")  # GitHub login, at most 39
_REPOSITORY = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/[A-Za-z0-9._-]+")
_MAX_LOGIN = 39


@dataclass(frozen=True)
class InitResult:
    stack: Stack
    created: tuple[str, ...]  # includes .rapid-ship/kit.lock; empty when there are conflicts
    skipped: tuple[str, ...]  # seeded files that already existed; rs-setup merges them
    conflicts: tuple[str, ...]  # "path: reason"; when present, init wrote nothing


def resolve_variables(
    root: Path,
    *,
    name: str | None = None,
    package: str | None = None,
    owner: str | None = None,
    repository: str | None = None,
) -> dict[str, str]:
    """The four template variables. These values are substituted into TOML strings and
    CODEOWNERS, so each is validated. An absent owner or repository is "".
    """
    project_name = root.resolve().name if name is None else name
    if not _PROJECT_NAME.fullmatch(project_name):
        raise KitError(f"project name {project_name!r} is not a valid project name; check --name")
    if package is None:
        package = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")
    if not package.isidentifier() or keyword.iskeyword(package):
        raise KitError(f"package {package!r} is not a Python package name; check --package")
    if owner is not None and (len(owner) > _MAX_LOGIN or not _LOGIN.fullmatch(owner)):
        raise KitError(f"owner {owner!r} is not a GitHub login; check --owner")
    if repository is not None and not _REPOSITORY.fullmatch(repository):
        raise KitError(f"repository {repository!r} is not owner/name; check --repository")
    return {
        "project_name": project_name,
        "package": package,
        "owner": owner or "",
        "repository": repository or "",
    }


def init_repository(
    root: Path,
    *,
    stack: Stack | None,
    variables: Mapping[str, str],
    templates_root: Path | None = None,
) -> InitResult:
    root = root.resolve()
    top = work_tree_root(root)
    if top != root:
        raise KitRefusal(f"run init from the top of the work tree, {top}")
    if not is_clean(root):
        raise KitRefusal("the work tree has changes; commit or stash them, then run init")
    if os.path.lexists(root / LOCK_PATH):
        raise KitRefusal(f"{LOCK_PATH} exists; use rapid-ship status or rapid-ship sync")
    existing_project = os.path.lexists(root / "pyproject.toml")
    stack = stack or ("python" if existing_project else None)
    if stack is None:
        raise KitError("there is no pyproject.toml; pass --stack python or --stack neutral")
    manifest = load_manifest(templates_root)
    new_project_only = {render_path(path, variables) for path in manifest.new_project}
    templates = [
        template
        for template in render_files(stack, variables, (), root=templates_root)
        if not (existing_project and template.path in new_project_only)
    ]
    writes, skipped, conflicts = _plan(root, templates)
    if conflicts:
        return InitResult(stack, (), tuple(skipped), tuple(conflicts))
    lock = Lock(installed_version(), stack, dict(variables), tuple(entry_for(t) for t in templates))
    created = _write(root, writes, manifest.executable, lock)
    return InitResult(stack, created, tuple(skipped), ())


def _plan(
    root: Path, templates: Sequence[Template]
) -> tuple[list[tuple[Template, Path]], list[str], list[str]]:
    """Sort the templates into writes, skipped seeded files and conflicts. Nothing is written."""
    writes: list[tuple[Template, Path]] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    checked: set[str] = set()
    seeded = {template.path for template in templates if template.kind == "seeded"}
    for path in [*(template.path for template in templates), LOCK_PATH]:
        try:
            safe_path(root, path)
        except UnsafePath as error:
            # init never writes over a seeded file, so a seeded file that is itself a link, such
            # as CLAUDE.md -> AGENTS.md, is skipped below. A link above it is still a conflict.
            if path not in seeded or not _directories_are_real(root, path):
                conflicts.append(str(error))
                continue
        checked.add(path)
    for template in templates:
        if template.path not in checked:
            continue
        target = locate(root, template.path)
        blocker = next(
            (
                p
                for p in reversed(target.parents)
                if p.is_relative_to(root) and p != root and p.exists() and not p.is_dir()
            ),
            None,
        )
        if blocker is not None:
            conflicts.append(f"{template.path}: {blocker.relative_to(root)} is not a directory")
        elif os.path.lexists(target):
            if template.kind == "managed":
                conflicts.append(f"{template.path}: exists")
            else:
                skipped.append(template.path)
        else:
            writes.append((template, target))
    # A Kit file that git ignores could never be committed, so CI would run without it.
    candidates = [template.path for template, _ in writes]
    if LOCK_PATH in checked:
        candidates.append(LOCK_PATH)
    if candidates:
        output = git(
            root,
            "check-ignore",
            "-z",
            "--stdin",
            stdin=b"\0".join(map(os.fsencode, candidates)),
            allowed=(0, 1),
            literal=False,  # check-ignore refuses pathspec flags; stdin paths are literal
        )
        conflicts += [
            f"{os.fsdecode(path)}: ignored by git, so it could not be committed"
            for path in output.split(b"\0")
            if path
        ]
    return writes, skipped, conflicts


def _directories_are_real(root: Path, path: str) -> bool:
    """True when no directory on the way to path is a symlink. path itself may be one."""
    try:
        locate(root, path)
    except UnsafePath:
        return False
    return True


def _write(
    root: Path, writes: Sequence[tuple[Template, Path]], executable: frozenset[str], lock: Lock
) -> tuple[str, ...]:
    """Write every file, then the lock. On any failure, remove what was created and stop."""
    created: list[Path] = []
    directories: list[Path] = []
    try:
        for template, target in writes:
            _make_parents(root, target, directories)
            if template.link is not None:
                os.symlink(template.link, target)
            else:
                create_file(target, template.content or b"", executable=template.path in executable)
            created.append(target)
        _make_parents(root, root / LOCK_PATH, directories)
        created.append(root / LOCK_PATH)
        write_lock(root, lock)
    except (OSError, KitError) as error:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for directory in reversed(directories):
            with contextlib.suppress(OSError):
                directory.rmdir()
        raise KitError(f"init stopped ({error}) and removed the files it had created") from error
    return (*(template.path for template, _ in writes), LOCK_PATH)


def _make_parents(root: Path, target: Path, directories: list[Path]) -> None:
    """Create the missing directories above target inside root, noting each for cleanup."""
    for directory in reversed(target.parents):
        if directory.is_relative_to(root) and directory != root and not directory.exists():
            directory.mkdir()
            directories.append(directory)
