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
