"""Atomic replacement for mutable files with caller-owned paths and serialization."""

import os
import tempfile
from pathlib import Path


def atomic_replace(path: Path, content: bytes) -> None:
    """Replace a file privately, removing unpublished temporary files on failure.

    The caller validates the path and creates its parent directory. The file is
    synced before replacement; the parent directory is not synced.
    """
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
