"""Atomic replacement uses real files with injected filesystem failures."""

import os
import stat

import pytest

from rapid_ship.files import atomic_replace


@pytest.mark.parametrize("existing", [False, True])
def test_replacement_publishes_exact_private_bytes_without_temporary_files(tmp_path, existing):
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
    tmp_path, monkeypatch, stage, existing
):
    target = tmp_path / "record.json"
    if existing:
        target.write_bytes(b"original")
    original_fdopen = os.fdopen
    streams = []

    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, content):
            self.stream.write(content[:3])
            self.stream.flush()
            raise OSError("injected partial write failure")

    def fdopen(*args, **kwargs):
        stream = original_fdopen(*args, **kwargs)
        streams.append(stream)
        return PartialWriter(stream) if stage == "write" else stream

    def fail(*args, **kwargs):
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
    assert streams and all(stream.closed for stream in streams)


def test_replacement_requires_an_existing_parent(tmp_path):
    target = tmp_path / "missing" / "record.json"

    with pytest.raises(FileNotFoundError):
        atomic_replace(target, b"new")

    assert not target.parent.exists()
