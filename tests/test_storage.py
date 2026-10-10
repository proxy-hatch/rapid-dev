"""Durable store invariants exercised against real SQLite connections."""

import json
import sqlite3

import pytest

from agentic_engineering.models import TaskSpec
from agentic_engineering.storage import Store


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def task(task_id: str = "a", **changes: object) -> TaskSpec:
    fields = {
        "id": task_id,
        "title": task_id,
        "description": "Implement the task",
        "depends_on": [],
        "owned_paths": [f"src/{task_id}.py"],
        "acceptance": ["Checks pass"],
        "environment": "local",
        "base_sha": "base",
        "runner": None,
        "checks": [],
    }
    fields.update(changes)
    return TaskSpec.model_validate(fields)


def approve(store: Store, task_id: str, owner: str = "worker") -> str:
    attempt = store.claim(task_id, owner)
    for state in ["verifying", "reviewing", "approved"]:
        store.transition(task_id, state, attempt, owner)
    return attempt


def test_restart_preserves_specs_transitions_and_events(tmp_path):
    path = tmp_path / "state.db"
    with Store(path) as store:
        store.add_tasks([task()])
        attempt = store.claim("a", "alice")
        store.transition("a", "verifying", attempt, "alice", note="checks started")
        store.record_event("artifact", {"path": "report.json"})
        assert json.loads(json.dumps(store.get_task("a")))["spec"]["title"] == "a"
        before = store.events()
    with Store(path) as store:
        assert store.get_task("a")["state"] == "verifying"
        assert store.get_task("a")["attempt_id"] == attempt
        assert store.events() == before
        assert before[-1]["kind"] == "artifact"
        assert before[-1]["payload"] == {"path": "report.json"}


def test_duplicate_specs_are_idempotent_and_changed_batch_rolls_back(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task()])
        original_events = store.events()
        store.add_tasks([task(), task()])
        assert store.events() == original_events
        with pytest.raises(ValueError):
            store.add_tasks([task("b"), task(title="different")])
        assert [row["id"] for row in store.tasks()] == ["a"]
        assert store.events() == original_events


def test_missing_dependencies_reject_entire_batch(tmp_path):
    with Store(tmp_path / "state.db") as store:
        with pytest.raises(ValueError):
            store.add_tasks([task("a"), task("b", depends_on=["missing"])])
        assert store.tasks() == []
        assert store.events() == []


def test_dependencies_require_approval_and_accept_merged_or_released(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task(), task("b", depends_on=["a"])])
        with pytest.raises(ValueError):
            store.claim("b", "bob")
        approve(store, "a")
        store.transition("a", "merged")
        store.transition("a", "released")
        assert store.claim("b", "bob")


def test_two_connections_allow_only_one_claim(tmp_path):
    path = tmp_path / "state.db"
    with Store(path) as first, Store(path) as second:
        first.add_tasks([task()])
        attempt = first.claim("a", "alice")
        with pytest.raises(ValueError):
            second.claim("a", "bob")
        row = second.get_task("a")
        assert (row["attempt_id"], row["owner"], row["generation"]) == (attempt, "alice", 1)


@pytest.mark.parametrize("other", ["src/package/file.py", "src", "src/*"])
def test_active_overlapping_paths_block_claims(tmp_path, other):
    path = tmp_path / "state.db"
    with Store(path) as first, Store(path) as second:
        first.add_tasks([task(owned_paths=["src/package"]), task("b", owned_paths=[other])])
        first.claim("a", "alice")
        with pytest.raises(ValueError):
            second.claim("b", "bob")
        assert second.get_task("b")["state"] == "pending"


def test_expiry_fences_writes_and_requires_explicit_recovery_resume(tmp_path):
    clock = Clock()
    with Store(tmp_path / "state.db", clock=clock) as store:
        store.add_tasks([task()])
        first = store.claim("a", "alice", ttl_seconds=5)
        store.acquire_resources(first, "alice", ["database"], ttl_seconds=5)
        clock.now += 5
        for operation in [
            lambda: store.heartbeat(first, "alice"),
            lambda: store.transition("a", "verifying", first, "alice"),
            lambda: store.acquire_resources(first, "alice", ["database"]),
            lambda: store.release_resources(first, "alice"),
            lambda: store.claim("a", "bob"),
        ]:
            with pytest.raises(ValueError):
                operation()
        assert store.recover_expired() == ["a"]
        assert store.get_task("a")["state"] == "blocked"
        with pytest.raises(ValueError):
            store.claim("a", "bob")
        with pytest.raises(ValueError):
            store.transition("a", "pending")
        store.release_recovered("a")
        store.transition("a", "pending", note="supervisor stopped old worker")
        second = store.claim("a", "bob")
        assert second != first
        assert store.get_task("a")["generation"] == 2
        with pytest.raises(ValueError):
            store.transition("a", "verifying", first, "alice")
        store.transition("a", "verifying", second, "bob")


def test_orphan_reservations_survive_expiry_until_stop_reconciliation(tmp_path):
    clock = Clock()
    path = tmp_path / "state.db"
    with Store(path, clock=clock) as store, Store(path, clock=clock) as other:
        store.add_tasks(
            [
                task(),
                task("b", owned_paths=["src/a.py"]),
                task("c"),
            ]
        )
        a = store.claim("a", "alice", ttl_seconds=5)
        c = other.claim("c", "carol")
        store.acquire_resources(a, "alice", ["db"], ttl_seconds=5)
        clock.now += 5
        for recovered in [False, True]:
            if recovered:
                store.recover_expired()
            with pytest.raises(ValueError):
                other.claim("b", "bob")
            with pytest.raises(ValueError):
                other.acquire_resources(c, "carol", ["db"])
        store.release_recovered("a")
        assert other.claim("b", "bob")
        other.acquire_resources(c, "carol", ["db"])


def test_release_recovered_cannot_revoke_live_owner(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task()])
        store.claim("a", "alice")
        with pytest.raises(ValueError):
            store.release_recovered("a")


def test_heartbeat_renews_attempt_and_resource_leases(tmp_path):
    clock = Clock()
    path = tmp_path / "state.db"
    with Store(path, clock=clock) as store, Store(path, clock=clock) as second:
        store.add_tasks([task(), task("b")])
        attempt = store.claim("a", "alice", ttl_seconds=5)
        store.acquire_resources(attempt, "alice", ["db"], ttl_seconds=5)
        competitor = second.claim("b", "bob")
        clock.now += 4
        store.heartbeat(attempt, "alice", ttl_seconds=10)
        clock.now += 2
        assert store.get_task("a")["lease_expires_at"] == 1014
        with pytest.raises(ValueError):
            second.acquire_resources(competitor, "bob", ["db"])


def test_resource_acquisition_is_all_or_nothing_and_owner_fenced(tmp_path):
    path = tmp_path / "state.db"
    with Store(path) as first, Store(path) as second:
        first.add_tasks([task(), task("b"), task("c")])
        a = first.claim("a", "alice")
        b = second.claim("b", "bob")
        c = first.claim("c", "carol")
        first.acquire_resources(a, "alice", ["locked"])
        before = second.events()
        with pytest.raises(ValueError):
            second.acquire_resources(b, "bob", ["free", "locked"])
        assert second.events() == before
        first.acquire_resources(c, "carol", ["free"])
        with pytest.raises(ValueError):
            second.release_resources(a, "bob")
        first.release_resources(a, "alice")
        second.acquire_resources(b, "bob", ["locked"])


def test_repair_creates_new_attempt_and_releases_reservations(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task(), task("b")])
        original = store.claim("a", "alice")
        store.acquire_resources(original, "alice", ["db"])
        for state in ["verifying", "reviewing", "needs_repair"]:
            store.transition("a", state, original, "alice")
        fresh = store.claim("a", "bob")
        assert fresh != original
        store.acquire_resources(fresh, "bob", ["db"])
        with pytest.raises(ValueError):
            store.heartbeat(original, "alice")


@pytest.mark.parametrize("initial", ["pending", "running", "blocked", "needs_repair"])
def test_cancelled_tasks_cannot_be_revived(tmp_path, initial):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task()])
        attempt = None
        if initial != "pending":
            attempt = store.claim("a", "alice")
            if initial == "blocked":
                store.transition("a", "blocked", attempt, "alice")
            elif initial == "needs_repair":
                for state in ["verifying", "reviewing", "needs_repair"]:
                    store.transition("a", state, attempt, "alice")
        store.transition("a", "cancelled", attempt, "alice" if attempt else None)
        for operation in [
            lambda: store.claim("a", "bob"),
            lambda: store.transition("a", "pending"),
        ]:
            with pytest.raises(ValueError):
                operation()


def test_transition_cannot_skip_review_or_bypass_claim(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task()])
        with pytest.raises(ValueError):
            store.transition("a", "running")
        attempt = store.claim("a", "alice")
        for state in ["approved", "unknown", "pending"]:
            with pytest.raises(ValueError):
                store.transition("a", state, attempt, "alice")
        with pytest.raises(ValueError):
            store.transition("a", "verifying", attempt, "bob")
        assert store.get_task("a")["state"] == "running"


def test_effect_intent_conflicts_and_uncertainty_survive_restart(tmp_path):
    path = tmp_path / "state.db"
    with Store(path) as store:
        effect = store.begin_effect("pr:a", "create_pr", {"head": "a"})
        assert effect["status"] == "pending"
        store.mark_effect_uncertain("pr:a", "connection lost")
    with Store(path) as store:
        assert store.begin_effect("pr:a", "create_pr", {"head": "a"})["status"] == "uncertain"
        for kind, payload in [("merge_pr", {"head": "a"}), ("create_pr", {"head": "b"})]:
            with pytest.raises(ValueError):
                store.begin_effect("pr:a", kind, payload)
        store.finish_effect("pr:a", {"number": 42})
        store.finish_effect("pr:a", {"number": 42})
        assert store.begin_effect("pr:a", "create_pr", {"head": "a"})["result"] == {"number": 42}
        with pytest.raises(ValueError):
            store.finish_effect("pr:a", {"number": 43})
        with pytest.raises(ValueError):
            store.mark_effect_uncertain("pr:a", "late error")
        assert store.get_effect("pr:a")["status"] == "completed"


def test_transition_and_event_append_roll_back_together(tmp_path):
    path = tmp_path / "state.db"
    with Store(path) as store:
        store.add_tasks([task()])
        attempt = store.claim("a", "alice")
        before = store.events()
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TRIGGER reject_event BEFORE INSERT ON events "
                "BEGIN SELECT RAISE(ABORT, 'disk failure'); END"
            )
        with pytest.raises(sqlite3.IntegrityError):
            store.transition("a", "verifying", attempt, "alice")
        assert store.get_task("a")["state"] == "running"
        assert store.events() == before


def test_newer_schema_is_rejected_without_modifying_database(tmp_path):
    path = tmp_path / "state.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="schema"):
        Store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999


@pytest.mark.parametrize("ttl", [0, -1, float("nan"), float("inf")])
def test_invalid_ttl_cannot_claim_task(tmp_path, ttl):
    with Store(tmp_path / "state.db") as store:
        store.add_tasks([task()])
        with pytest.raises(ValueError):
            store.claim("a", "alice", ttl_seconds=ttl)
        assert store.get_task("a")["state"] == "pending"
