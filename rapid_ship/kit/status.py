"""rapid-ship status: classify the vendored Kit against its lock and the installed templates."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from rapid_ship.files import UnsafePath, safe_path
from rapid_ship.kit.lock import LockEntry, file_sha256, read_lock, template_hash
from rapid_ship.kit.templates import (
    Kind,
    Stack,
    Template,
    installed_version,
    is_excluded,
    read_excluded,
    read_optional_skills,
    render_files,
)

State = Literal["unchanged", "modified", "missing", "template updated", "excluded"]


@dataclass(frozen=True)
class FileStatus:
    path: str
    kind: Kind
    state: State


@dataclass(frozen=True)
class StatusReport:
    kit_version: str  # the version that wrote the lock
    installed_version: str
    stack: Stack
    files: tuple[FileStatus, ...]
    outdated: tuple[str, ...]  # managed entries the installed templates no longer match
    not_installed: tuple[str, ...]  # managed templates with no lock entry

    @property
    def strict_ok(self) -> bool:
        """True when every managed file is unchanged or excluded and nothing is outdated."""
        managed_current = all(
            item.state in ("unchanged", "excluded") for item in self.files if item.kind == "managed"
        )
        return managed_current and not self.outdated and not self.not_installed


def locate(root: Path, relative: str) -> Path:
    """Return the path after refusing a symlink in any directory on the way.

    The last part may be a link.
    """
    parent = PurePosixPath(relative).parent
    base = root.resolve() if parent == PurePosixPath(".") else safe_path(root, parent.as_posix())
    return base / PurePosixPath(relative).name


def fingerprint(root: Path, relative: str) -> str | None:
    """'sha256:<hex>' for a file, 'link:<target>' for a symlink and 'other' for anything else.

    None means nothing exists at the path.
    """
    path = locate(root, relative)
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        return f"link:{path.readlink()}"
    return f"sha256:{file_sha256(path.read_bytes())}" if path.is_file() else "other"


def entry_fingerprint(entry: LockEntry) -> str:
    return f"link:{entry.link}" if entry.link is not None else f"sha256:{entry.sha256}"


def template_fingerprint(template: Template) -> str:
    return (
        f"link:{template.link}"
        if template.link is not None
        else f"sha256:{file_sha256(template.content or b'')}"
    )


def classify(root: Path, *, templates_root: Path | None = None) -> StatusReport:
    lock = read_lock(root)
    templates = {
        t.path: t
        for t in render_files(
            lock.stack, lock.variables, read_optional_skills(root), root=templates_root
        )
    }
    excluded = read_excluded(root)
    files: list[FileStatus] = []
    outdated: list[str] = []
    for entry in lock.entries:
        template = templates.get(entry.path)
        if is_excluded(entry.path, excluded):
            files.append(FileStatus(entry.path, entry.kind, "excluded"))  # the project owns it
            continue
        if entry.kind == "seeded":
            # The template may be managed: sync records a managed file the project edited or
            # deleted as seeded. Either way the file is the project's and is never compared.
            if template is not None and entry.template_sha256 != template_hash(template):
                files.append(FileStatus(entry.path, "seeded", "template updated"))
            continue
        try:
            disk = fingerprint(root, entry.path)
        except UnsafePath:
            disk = "other"  # a symlinked directory on the way counts as modified
        state: State = (
            "missing"
            if disk is None
            else "unchanged"
            if disk == entry_fingerprint(entry)
            else "modified"
        )
        files.append(FileStatus(entry.path, "managed", state))
        if (
            template is None
            or template.kind != "managed"
            or template_fingerprint(template) != entry_fingerprint(entry)
        ):
            outdated.append(entry.path)
    locked = {entry.path for entry in lock.entries}
    not_installed = sorted(
        p
        for p, t in templates.items()
        if t.kind == "managed" and p not in locked and not is_excluded(p, excluded)
    )
    return StatusReport(
        lock.kit_version,
        installed_version(),
        lock.stack,
        tuple(files),
        tuple(outdated),
        tuple(not_installed),
    )
