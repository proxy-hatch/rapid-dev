"""Read and write .rapid-ship/kit.lock, which records the Kit files a repository vendors."""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import tomli_w

from rapid_ship.files import UnsafePath, atomic_replace, relative_parts, safe_path
from rapid_ship.kit.templates import STACKS, Kind, KitError, Stack, Template

LOCK_PATH = ".rapid-ship/kit.lock"

# Deleting a file and its entry does not drop it: the next sync would add it again.
_HEADER = (
    "# Written by rapid-ship. To own or drop a Kit file, "
    "list it under [kit] exclude in project.toml.\n"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ENTRY_KEYS = {"path", "kind", "sha256", "link", "template_sha256"}


@dataclass(frozen=True)
class LockEntry:
    path: str
    kind: Kind
    sha256: str | None  # managed files
    link: str | None  # managed symlinks
    # Seeded files, including managed files the project edited or deleted (sync step 4).
    template_sha256: str | None


@dataclass(frozen=True)
class Lock:
    kit_version: str
    stack: Stack
    variables: Mapping[str, str]
    entries: tuple[LockEntry, ...]


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def template_hash(template: Template) -> str:
    """The hash a seeded entry records: the template's content, or a symlink's target."""
    if template.link is not None:
        return file_sha256(template.link.encode("utf-8"))
    return file_sha256(template.content or b"")


def seeded_entry(path: str, template_sha256: str) -> LockEntry:
    return LockEntry(path, "seeded", None, None, template_sha256)


def entry_for(template: Template) -> LockEntry:
    """The lock entry for a rendered template. Seeded files record the template's hash only."""
    if template.kind == "seeded":
        return seeded_entry(template.path, template_hash(template))
    if template.link is not None:
        return LockEntry(template.path, "managed", None, template.link, None)
    return LockEntry(template.path, "managed", file_sha256(template.content or b""), None, None)


def read_lock(root: Path) -> Lock:
    try:
        data = tomllib.loads(safe_path(root, LOCK_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise KitError(f"{LOCK_PATH} is missing; run rapid-ship init") from error
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, UnsafePath) as error:
        raise KitError(f"cannot read {LOCK_PATH}: {error}") from error
    _known(data, {"kit_version", "stack", "variables", "file"}, LOCK_PATH)
    version, stack = data.get("kit_version"), data.get("stack")
    variables, items = data.get("variables", {}), data.get("file", [])
    if not isinstance(version, str) or not version:
        raise KitError(f"{LOCK_PATH}: kit_version must be a non-empty string")
    if stack not in STACKS:
        raise KitError(f"{LOCK_PATH}: stack must be python or agnostic")
    if not isinstance(variables, dict) or not all(isinstance(v, str) for v in variables.values()):
        raise KitError(f"{LOCK_PATH}: [variables] must map names to strings")
    if not isinstance(items, list):
        raise KitError(f"{LOCK_PATH}: file must be a list of [[file]] entries")
    entries = tuple(_entry(item, number) for number, item in enumerate(items, start=1))
    seen: set[str] = set()
    for entry in entries:
        if entry.path in seen:
            raise KitError(f"{LOCK_PATH}: {entry.path} is listed twice")
        seen.add(entry.path)
    return Lock(version, cast(Stack, stack), dict(variables), entries)


def write_lock(root: Path, lock: Lock) -> None:
    try:
        path = safe_path(root, LOCK_PATH)
    except UnsafePath as error:
        raise KitError(str(error)) from error
    path.parent.mkdir(exist_ok=True)
    document = {
        "kit_version": lock.kit_version,
        "stack": lock.stack,
        "variables": dict(sorted(lock.variables.items())),
        "file": [_table(entry) for entry in sorted(lock.entries, key=lambda entry: entry.path)],
    }
    atomic_replace(path, (_HEADER + tomli_w.dumps(document)).encode("utf-8"), mode=0o644)


def _known(table: Mapping[str, object], keys: Collection[str], where: str) -> None:
    for key in sorted(table):
        if key not in keys:
            raise KitError(f"{where}: unknown key {key!r}")


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _entry(item: object, number: int) -> LockEntry:
    where = f"{LOCK_PATH} [[file]] #{number}"
    if not isinstance(item, dict):
        raise KitError(f"{where}: must be a table")
    _known(item, _ENTRY_KEYS, where)
    path = item.get("path")
    if not isinstance(path, str):
        raise KitError(f"{where}: path must be a string")
    try:
        canonical = "/".join(relative_parts(path))
    except UnsafePath as error:
        raise KitError(f"{where}: {error}") from error
    if canonical != path:
        # sync keys entries by path, so './devctl' would be deleted as a dropped file
        # while 'devctl' is recorded as present.
        raise KitError(f"{where}: path {path!r} must be written as {canonical!r}")
    kind, sha, link = item.get("kind"), item.get("sha256"), item.get("link")
    template_sha = item.get("template_sha256")
    if kind == "managed" and template_sha is None:
        if _is_hash(sha) and link is None:
            return LockEntry(path, "managed", sha, None, None)
        if sha is None and isinstance(link, str) and link:
            return LockEntry(path, "managed", None, link, None)
    elif kind == "seeded" and _is_hash(template_sha) and sha is None and link is None:
        return LockEntry(path, "seeded", None, None, template_sha)
    raise KitError(
        f"{where} ({path}): a managed entry has sha256 or link, "
        "and a seeded entry has only template_sha256"
    )


def _table(entry: LockEntry) -> dict[str, str]:
    fields = {
        "path": entry.path,
        "kind": entry.kind,
        "sha256": entry.sha256,
        "link": entry.link,
        "template_sha256": entry.template_sha256,
    }
    return {name: value for name, value in fields.items() if value is not None}
