"""Atomic replacement uses real files with injected filesystem failures."""

import os
import stat
from pathlib import Path
from types import TracebackType
from typing import IO, NoReturn, Self

import pytest

from rapid_ship.files import UnsafePath, atomic_replace, create_file, relative_parts, safe_path


@pytest.mark.parametrize("existing", [False, True])
def test_replacement_publishes_exact_private_bytes_without_temporary_files(
    tmp_path: Path, existing: bool
) -> None:
    target = tmp_path / "record.json"
    if existing:
        target.write_bytes(b"original")
        target.chmod(0o644)
    content = b"complete new record\x00\xff\n"

    atomic_replace(target, content)

    assert target.read_bytes() == content
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("stage", ["write", "fsync", "replace"])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_replacement_preserves_destination_and_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, existing: bool
) -> None:
    target = tmp_path / "record.json"
    if existing:
        target.write_bytes(b"original")
    original_fdopen = os.fdopen
    streams: list[IO[bytes]] = []

    class PartialWriter:
        def __init__(self, stream: IO[bytes]) -> None:
            self.stream = stream

        def __enter__(self) -> Self:
            return self

        def __exit__(
            self,
            kind: type[BaseException] | None,
            error: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self.stream.__exit__(kind, error, traceback)

        def write(self, content: bytes) -> None:
            self.stream.write(content[:3])
            self.stream.flush()
            raise OSError("injected partial write failure")

    def fdopen(descriptor: int, mode: str) -> IO[bytes] | PartialWriter:
        stream = original_fdopen(descriptor, mode)
        streams.append(stream)
        return PartialWriter(stream) if stage == "write" else stream

    def fail(*args: object) -> NoReturn:
        raise OSError(f"injected {stage} failure")

    monkeypatch.setattr(os, "fdopen", fdopen)
    if stage != "write":
        monkeypatch.setattr(os, stage, fail)

    with pytest.raises(OSError, match="injected"):
        atomic_replace(target, b"replacement bytes")

    if existing:
        assert target.read_bytes() == b"original"
    else:
        assert not target.exists()
    assert list(tmp_path.iterdir()) == ([target] if existing else [])
    assert streams
    assert all(stream.closed for stream in streams)


def test_replacement_requires_an_existing_parent(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "record.json"

    with pytest.raises(FileNotFoundError):
        atomic_replace(target, b"new")

    assert not target.parent.exists()


def test_replacement_can_publish_a_shared_or_executable_mode(tmp_path: Path) -> None:
    target = tmp_path / "devctl"

    atomic_replace(target, b"#!/bin/sh\n", mode=0o755)

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


@pytest.mark.parametrize("relative", ["", ".", "/etc/passwd", "../outside", "a/../../b", "a\\b"])
def test_relative_parts_refuse_paths_that_leave_the_root(relative: str) -> None:
    with pytest.raises(UnsafePath, match="must stay inside the repository"):
        relative_parts(relative)


def test_safe_path_refuses_every_symlink_below_the_root(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "docs").symlink_to("real")
    (tmp_path / "dangling").symlink_to("missing")
    for relative in ("docs", "docs/README.md", "dangling"):
        with pytest.raises(UnsafePath, match="is a symlink"):
            safe_path(tmp_path, relative)


def test_safe_path_accepts_a_root_reached_through_a_symlink(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to("real")

    assert safe_path(tmp_path / "alias", "a/b.txt") == tmp_path.resolve() / "real" / "a" / "b.txt"


def test_create_file_never_replaces_or_follows_a_symlink(tmp_path: Path) -> None:
    create_file(tmp_path / "new.txt", b"new\n")
    (tmp_path / "link").symlink_to("missing")

    for name in ("new.txt", "link"):
        with pytest.raises(FileExistsError):
            create_file(tmp_path / name, b"other\n")

    assert (tmp_path / "new.txt").read_bytes() == b"new\n"
    assert not (tmp_path / "missing").exists()


def test_create_file_marks_executables(tmp_path: Path) -> None:
    create_file(tmp_path / "devctl", b"#!/bin/sh\n", executable=True)

    assert os.access(tmp_path / "devctl", os.X_OK)
