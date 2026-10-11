"""Host policy snapshots cannot be changed by candidate configuration."""

import json

import pytest
from pydantic import ValidationError

from agentic_engineering.policy import Policy, PolicyStore, Recipe


def policy(**changes):
    values = dict(
        project_id="demo",
        controller_version="0.1.0",
        recipes=(Recipe(name="unit", checks=(("unit", ("pytest",)),)),),
        capabilities=("create_pr", "merge", "release"),
    )
    return Policy(**(values | changes))


def test_snapshot_is_pinned_and_conflicting_initialization_cannot_weaken_it(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    store = PolicyStore(tmp_path / "host", candidate)
    original = policy()
    snapshot = store.initialize(original)
    assert store.load_active() == original
    assert store.initialize(original) == snapshot
    with pytest.raises(ValueError, match="ceremony"):
        store.initialize(policy(capabilities=("merge",)))
    assert store.load_active() == original
    with pytest.raises(ValidationError):
        original.controller_version = "forged"
    assert isinstance(original.recipes, tuple)


def test_snapshot_tampering_and_unknown_fields_are_rejected(tmp_path):
    store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    snapshot = store.initialize(policy())
    path = store.directory / f"policy-{snapshot}.json"
    value = json.loads(path.read_text())
    value["payload"]["policy"]["capabilities"] = ["deploy"]
    path.chmod(0o600)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="signature|digest"):
        store.load_active()
    with pytest.raises(ValidationError):
        policy(unknown="permission")


def test_host_store_rejects_candidate_paths_and_symlinks_without_writes(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    with pytest.raises(ValueError, match="candidate"):
        PolicyStore(candidate / "host", candidate)
    assert not (candidate / "host").exists()
    (tmp_path / "link").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        PolicyStore(tmp_path / "link" / "host", candidate)


@pytest.mark.parametrize("version", [True, 1.0, 2])
def test_unknown_or_noninteger_store_version_is_blocked(tmp_path, version):
    store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    store.initialize(policy())
    path = store.directory / "active.json"
    payload = json.loads(path.read_text())
    payload["schema_version"] = version
    path.chmod(0o600)
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="version"):
        store.load_active()


@pytest.mark.parametrize("failed_record", [1, 2])
def test_interrupted_record_publication_restarts_without_partial_final(
    tmp_path, monkeypatch, failed_record
):
    import os
    import stat

    store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    original_fsync = os.fsync
    written_records = 0

    def fail_durable_write(fd):
        nonlocal written_records
        if stat.S_ISREG(os.fstat(fd).st_mode):
            written_records += 1
            if written_records == failed_record:
                raise OSError("injected record write failure")
        return original_fsync(fd)

    with monkeypatch.context() as fault:
        fault.setattr(os, "fsync", fail_durable_write)
        with pytest.raises(OSError, match="injected"):
            store.initialize(policy())
    interrupted_path = (
        store.directory / f"policy-{policy().digest}.json"
        if failed_record == 1
        else store.directory / "active.json"
    )
    assert not interrupted_path.exists()
    restarted = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    restarted.initialize(policy())
    assert restarted.load_active() == policy()


def test_interrupted_key_publication_leaves_no_final_and_restart_succeeds(tmp_path, monkeypatch):
    import os

    with monkeypatch.context() as fault:

        def fail_write(fd):
            raise OSError("injected key write failure")

        fault.setattr(os, "fsync", fail_write)
        with pytest.raises(OSError, match="injected"):
            PolicyStore(tmp_path / "host", tmp_path / "candidate")
    assert not (tmp_path / "host" / ".authority-key").exists()
    restarted = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    restarted.initialize(policy())
    assert restarted.load_active() == policy()


def test_concurrent_same_policy_initialization_has_one_complete_key_and_record(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(4)

    def initialize():
        barrier.wait(timeout=10)
        store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
        store.initialize(policy())
        return store.load_active()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: initialize(), range(4)))
    assert results == [policy()] * 4
    restarted = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    assert restarted.load_active() == policy()


def test_existing_immutable_record_is_preserved_on_conflicting_publication(tmp_path):
    store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    store.save_record("example.json", "example", {"value": "first"})
    original = (store.directory / "example.json").read_bytes()
    with pytest.raises(ValueError, match="overwritten"):
        store.save_record("example.json", "example", {"value": "conflict"})
    assert (store.directory / "example.json").read_bytes() == original


def test_recipe_digest_matches_controller_check_command_binding():
    from agentic_engineering.models import digest

    expected = digest({"unit": ["pytest"]})
    assert policy().recipes[0].digest == expected
    renamed = Recipe(name="renamed", checks=(("unit", ("pytest",)),))
    assert renamed.digest == expected
    # Recipe identity changes policy even when the execution commands match.
    assert policy(recipes=(renamed,)).digest != policy().digest


@pytest.mark.parametrize("target", ["key", "policy"])
def test_partial_stream_write_never_publishes_final_name(tmp_path, monkeypatch, target):
    import os

    root = tmp_path / "host"
    store = PolicyStore(root, tmp_path / "candidate") if target == "policy" else None
    original_fdopen = os.fdopen

    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, content):
            self.stream.write(content[: len(content) // 2])
            self.stream.flush()
            raise OSError("injected partial write")

    def open_partial(fd, mode, *args, **kwargs):
        stream = original_fdopen(fd, mode, *args, **kwargs)
        return PartialWriter(stream) if "w" in mode else stream

    with monkeypatch.context() as fault:
        fault.setattr(os, "fdopen", open_partial)
        with pytest.raises(OSError, match="partial write"):
            if store is None:
                PolicyStore(root, tmp_path / "candidate")
            else:
                store.initialize(policy())
    final = root / (".authority-key" if target == "key" else f"policy-{policy().digest}.json")
    assert not final.exists()
    restarted = PolicyStore(root, tmp_path / "candidate")
    restarted.initialize(policy())
    assert restarted.load_active() == policy()


def test_failure_after_atomic_link_leaves_complete_record_for_restart(tmp_path, monkeypatch):
    import os
    import stat

    store = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    original_fsync = os.fsync

    def fail_directory_sync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("injected publication sync failure")
        return original_fsync(fd)

    with monkeypatch.context() as fault:
        fault.setattr(os, "fsync", fail_directory_sync)
        with pytest.raises(OSError, match="publication sync"):
            store.initialize(policy())
    assert store.load(policy().digest) == policy()
    restarted = PolicyStore(tmp_path / "host", tmp_path / "candidate")
    restarted.initialize(policy())
    assert restarted.load_active() == policy()
