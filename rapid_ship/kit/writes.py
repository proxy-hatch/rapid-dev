"""Write Kit files into a work tree, and put the work tree back when a command fails."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from rapid_ship.files import atomic_replace, create_file
from rapid_ship.kit.status import locate
from rapid_ship.kit.templates import Template


@dataclass
class Undo:
    """What a Kit command changed, so a failed command can put the work tree back."""

    root: Path
    replaced: list[tuple[Path, bytes, str | None, int]] = field(
        default_factory=list
    )  # path, bytes, link, mode
    created: list[Path] = field(
        default_factory=list
    )  # files, links and directories, in creation order

    def before(self, path: Path) -> None:
        """Keep an existing file or link before it is replaced or deleted."""
        if path.is_symlink():
            self.replaced.append((path, b"", str(path.readlink()), 0))
        elif path.is_file():
            self.replaced.append((path, path.read_bytes(), None, stat.S_IMODE(path.stat().st_mode)))

    def make_parents(self, path: Path) -> None:
        for directory in reversed(path.parents):
            if (
                directory.is_relative_to(self.root)
                and directory != self.root
                and not directory.exists()
            ):
                directory.mkdir()
                self.created.append(directory)

    def restore(self) -> None:
        for path in reversed(self.created):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        for path, content, link, mode in reversed(self.replaced):
            path.parent.mkdir(parents=True, exist_ok=True)  # delete_file may have removed it
            if os.path.lexists(path):
                path.unlink()
            if link is not None:
                path.symlink_to(link)
            else:
                atomic_replace(path, content, mode=mode)


def write_template(root: Path, template: Template, executable: bool, undo: Undo) -> None:
    """Create the template's file or link, or replace a managed one, noting the change in undo."""
    target = locate(root, template.path)
    undo.make_parents(target)
    content = template.content or b""
    if template.kind == "seeded" or not os.path.lexists(target):
        # create_file and symlink_to never replace, so a seeded file stays the project's.
        if template.link is not None:
            target.symlink_to(template.link)
        else:
            create_file(target, content, executable=executable)
        undo.created.append(target)  # only after it exists, so a failed create removes nothing
        return
    undo.before(target)
    if template.link is not None or target.is_symlink():
        # A link is never replaced in place: _replace would follow it to read the mode.
        target.unlink()
        if template.link is not None:
            target.symlink_to(template.link)
        else:
            create_file(target, content, executable=executable)
    else:
        _replace(target, content, executable)


def _replace(path: Path, content: bytes, executable: bool) -> None:
    """Replace a file's bytes and keep its mode; atomic_replace alone would publish 0o600."""
    mode = stat.S_IMODE(path.stat().st_mode)
    if executable:
        mode |= (mode & 0o444) >> 2
    atomic_replace(path, content, mode=mode)


def delete_file(root: Path, path: str) -> None:
    """Delete a file, then each parent directory left empty, up to the repository root."""
    target = locate(root, path)
    target.unlink()
    for directory in target.parents:
        if directory == root or any(directory.iterdir()):
            break
        directory.rmdir()
