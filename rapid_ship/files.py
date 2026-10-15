"""Atomic replacement, create-only writes and repository-relative paths for the Kit."""

import os
import tempfile
from pathlib import Path, PurePosixPath


class UnsafePath(ValueError):
    """A path would leave the repository or pass through a symlink."""


def relative_parts(relative: str) -> tuple[str, ...]:
    """Split a repository-relative POSIX path, refusing absolute paths, '..' and backslashes."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise UnsafePath(f"{relative!r}: path must stay inside the repository")
    return path.parts


def safe_path(root: Path, relative: str) -> Path:
    """Return root/relative after refusing every symlink below root.

    Ported from rapid_ship/project/configuration.py:33-44 at f7b877b. The root is
    resolved first, so a repository reached through a symlink is accepted.
    """
    root = root.resolve()
    current = root
    for part in relative_parts(relative):
        current = current / part
        if current.is_symlink():
            raise UnsafePath(f"{relative}: {current.relative_to(root)} is a symlink")
    return current


def atomic_replace(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    """Replace a file, removing unpublished temporary files on failure.

    The file is private (0o600) unless the caller passes a mode. The caller
    validates the path and creates its parent directory. The file is synced
    before replacement; the parent directory is not synced.
    """
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(fd, mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def create_file(path: Path, content: bytes, *, executable: bool = False) -> None:
    """Create path; never replace an existing file or follow a symlink.

    The caller validates the path and creates its parent directory. The umask applies, as for git.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o777 if executable else 0o666)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
    except OSError:
        path.unlink(missing_ok=True)
        raise
