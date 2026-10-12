"""Persistence failures must preserve trusted state without leaving partial files."""

import os
import stat
import sys
from dataclasses import replace

import pytest
from test_environments import native
from test_environments import repository as repository

from rapid_ship.execution.environments import EnvironmentManager
from rapid_ship.models import ProjectConfig
from rapid_ship.project.configuration import save_config, save_provider_records


def inject_failure(monkeypatch, operation):
    def fail(*args, **kwargs):
        raise OSError(f"injected {operation} failure")

    monkeypatch.setattr(os, operation, fail)


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_failed_initial_ownership_write_does_not_adopt_or_notify(
    tmp_path, repository, monkeypatch, operation
):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    observations = []
    manager.set_observer(observations.append)

    with monkeypatch.context() as patch:
        inject_failure(patch, operation)
        with pytest.raises(OSError, match=f"injected {operation} failure"):
            manager.prepare(native(), repo, "failed-persistence", sha)

    assert manager.owned_handles() == []
    assert observations == []
    assert not [path for path in manager.root.rglob("*") if path.is_file()]


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_failed_ownership_update_preserves_record_and_observed_identity(
    tmp_path, repository, monkeypatch, operation
):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    observations = []
    manager.set_observer(observations.append)
    handle = manager.prepare(native(), repo, "owned", sha)
    marker = handle.workspace.parent / "owner.json"
    original = marker.read_bytes()
    original_entries = set(marker.parent.iterdir())
    updated = replace(handle, metadata={**handle.metadata, "pending": "unpersisted identity"})

    with monkeypatch.context() as patch:
        inject_failure(patch, operation)
        with pytest.raises(OSError, match=f"injected {operation} failure"):
            # Isolate replacement from prepare's recovery and resource effects.
            manager._remember(updated)

    assert marker.read_bytes() == original
    assert manager.owned_handles() == [handle]
    assert observations == [handle]
    assert set(marker.parent.iterdir()) == original_entries
    manager.cleanup(handle)
    assert manager.owned_handles() == []


@pytest.mark.parametrize("operation", ["fsync", "replace"])
def test_failed_stop_preserves_cleanup_progress_and_workspace(
    tmp_path, repository, monkeypatch, operation
):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    handle = manager.prepare(native(), repo, "cleanup", sha)
    result = manager.execute(handle, [sys.executable, "-c", "pass"], 3)
    assert result.returncode == 0
    progress = handle.workspace.parent / "cleanup.json"
    original = progress.read_bytes()
    original_entries = set(progress.parent.iterdir())

    with monkeypatch.context() as patch:
        inject_failure(patch, operation)
        with pytest.raises(OSError, match=f"injected {operation} failure"):
            manager.stop(handle)

    assert original == b"[]"
    assert progress.read_bytes() == original
    assert handle.workspace.is_dir()
    assert manager.owned_handles() == [handle]
    assert set(progress.parent.iterdir()) == original_entries
    restarted = EnvironmentManager(manager.root)
    restarted.recover(handle)
    restarted.cleanup(handle)
    assert not handle.workspace.parent.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_provider_config_remains_pretty_printed_and_private(tmp_path, existing):
    path = tmp_path / ".devctl/providers.json"
    if existing:
        path.parent.mkdir()
        path.write_text("{}\n")
        path.chmod(0o644)

    save_provider_records(
        tmp_path,
        [
            {
                "provider": "codex",
                "models": [],
                "checked_at": "2026-10-12T00:00:00Z",
                "authenticated": False,
            }
        ],
    )

    assert path.read_bytes() == (
        b'{\n  "codex": {\n    "authenticated": false,\n'
        b'    "checked_at": "2026-10-12T00:00:00Z",\n'
        b'    "models": [],\n    "provider": "codex"\n  }\n}\n'
    )
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert set(path.parent.iterdir()) == {path}


def test_save_config_rejects_existing_destination_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"private configuration")
    path = tmp_path / ".devctl/project.json"
    path.parent.mkdir()
    path.symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        save_config(tmp_path, ProjectConfig(name="fixture", design_path="design.md"))

    assert path.is_symlink()
    assert outside.read_bytes() == b"private configuration"
    assert set(path.parent.iterdir()) == {path}


@pytest.mark.parametrize("filename", ["owner.json", "cleanup.json"])
def test_environment_persistence_rejects_existing_destination_symlink(
    tmp_path, repository, filename
):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    observations = []
    manager.set_observer(observations.append)
    handle = manager.prepare(native(), repo, "symlink", sha)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"unrelated state")
    destination = handle.workspace.parent / filename
    destination.unlink(missing_ok=True)
    destination.symlink_to(outside)
    original_entries = set(destination.parent.iterdir())

    with pytest.raises(ValueError, match="symlink"):
        if filename == "owner.json":
            manager._remember(handle)
        else:
            manager.stop(handle)

    assert destination.is_symlink()
    assert outside.read_bytes() == b"unrelated state"
    assert manager.owned_handles() == [handle]
    assert observations == [handle]
    assert set(destination.parent.iterdir()) == original_entries
