"""SQLite workflow state, fenced leases, resource reservations and effect intents.

Task snapshots are JSON-compatible dictionaries with ``id``, nested ``spec``
(TaskSpec's JSON representation), ``state``, ``attempt_id``, ``owner``,
``lease_expires_at``, ``generation``, ``note`` and ``reconciliation_required``.
Attempt/owner/expiry are null before the first claim, then preserve the latest
attempt's identity even after it leaves an active state. Generations increase
on every claim; attempt IDs never repeat. Only a current, unexpired active
attempt can heartbeat, mutate active state, or change resource reservations.

Expiry fences authority; it does not prove a process has stopped. Recovery
retains reservations until the supervisor calls
``release_recovered(task_id, expected_attempt_id)`` after confirming that exact
attempt's termination, then explicitly resumes the blocked task to pending.
Effect snapshots include key, kind, payload, status, result, note, created_at,
and updated_at. An uncertain intent may be completed after reconciliation but
is never implicitly restarted. Events include id, kind, payload and created_at.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from rapid_ship.models import TaskSpec, paths_overlap, validate_task_graph

TaskState = Literal[
    "pending",
    "running",
    "verifying",
    "reviewing",
    "needs_repair",
    "approved",
    "merged",
    "released",
    "blocked",
    "failed",
    "cancelled",
]


class TaskSnapshot(TypedDict):
    """JSON-compatible task view; unclaimed tasks have no attempt identity."""

    id: str
    spec: dict[str, Any]
    state: TaskState
    attempt_id: str | None
    owner: str | None
    lease_expires_at: float | None
    generation: int
    note: str
    reconciliation_required: bool


SCHEMA_VERSION = 1
ACTIVE_STATES: frozenset[TaskState] = frozenset({"running", "verifying", "reviewing"})
DEPENDENCY_STATES: frozenset[TaskState] = frozenset({"approved", "merged", "released"})
TRANSITIONS: dict[TaskState, set[TaskState]] = {
    "pending": {"running", "cancelled"},
    "running": {"verifying", "blocked", "failed", "cancelled"},
    "verifying": {"reviewing", "blocked", "failed", "cancelled"},
    "reviewing": {"approved", "needs_repair", "blocked", "failed", "cancelled"},
    "needs_repair": {"running", "cancelled"},
    "approved": {"merged"},
    "merged": {"released"},
    "released": set(),
    "blocked": {"pending", "cancelled"},
    "failed": set(),
    "cancelled": set(),
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


class Store:
    """A single SQLite connection; separate Store instances coordinate via SQL locks."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.connection = sqlite3.connect(path, isolation_level=None, timeout=30)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError(f"unsupported newer schema version: {version}")
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = FULL")
            with self._transaction():
                # Recheck under the writer lock: another connection may have migrated.
                version = self.connection.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise ValueError(f"unsupported newer schema version: {version}")
                if version == 0:
                    self._create_schema()
                    self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except BaseException:
            self.connection.close()
            raise

    def _create_schema(self) -> None:
        statements = [
            """CREATE TABLE tasks (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL,
                attempt_id TEXT, owner TEXT, lease_expires_at REAL,
                generation INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
                reconciliation_required INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            )""",
            """CREATE TABLE attempts (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                owner TEXT NOT NULL, generation INTEGER NOT NULL,
                lease_expires_at REAL NOT NULL, created_at REAL NOT NULL,
                UNIQUE(task_id, generation)
            )""",
            """CREATE TABLE resources (
                name TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(id),
                owner TEXT NOT NULL, generation INTEGER NOT NULL,
                lease_expires_at REAL NOT NULL
            )""",
            """CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                payload TEXT NOT NULL, created_at REAL NOT NULL
            )""",
            """CREATE TABLE effects (
                key TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, result TEXT, note TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            )""",
        ]
        for statement in statements:
            self.connection.execute(statement)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def _now(self) -> float:
        now = float(self.clock())
        if not math.isfinite(now):
            raise ValueError("clock must return a finite timestamp")
        return now

    def _expiry(self, now: float, ttl_seconds: float) -> float:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive and finite")
        expiry = now + ttl_seconds
        if not math.isfinite(expiry):
            raise ValueError("lease expiry must be finite")
        return expiry

    def _task(self, task_id: str) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown task: {task_id}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _task_snapshot(row: sqlite3.Row) -> TaskSnapshot:
        return {
            "id": row["id"],
            "spec": json.loads(row["spec"]),
            "state": row["state"],
            "attempt_id": row["attempt_id"],
            "owner": row["owner"],
            "lease_expires_at": row["lease_expires_at"],
            "generation": row["generation"],
            "note": row["note"],
            "reconciliation_required": bool(row["reconciliation_required"]),
        }

    def _fence(self, attempt_id: str, owner: str, now: float) -> sqlite3.Row:
        _nonempty(owner, "owner")
        attempt = self.connection.execute(
            "SELECT * FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        if attempt is None:
            raise ValueError(f"unknown attempt: {attempt_id}")
        task = self._task(attempt["task_id"])
        if (
            task["attempt_id"] != attempt_id
            or task["owner"] != owner
            or attempt["owner"] != owner
            or task["generation"] != attempt["generation"]
            or task["state"] not in ACTIVE_STATES
            or task["lease_expires_at"] <= now
            or attempt["lease_expires_at"] <= now
        ):
            raise ValueError("attempt ownership is stale, inactive or expired")
        return task

    def _event(self, kind: str, payload: dict[str, Any], now: float) -> None:
        _nonempty(kind, "event kind")
        self.connection.execute(
            "INSERT INTO events(kind, payload, created_at) VALUES (?, ?, ?)",
            (kind, _json(payload), now),
        )

    def add_tasks(self, tasks: list[TaskSpec]) -> None:
        with self._transaction():
            existing = {
                row["id"]: row["spec"]
                for row in self.connection.execute("SELECT id, spec FROM tasks")
            }
            additions: dict[str, str] = {}
            for task in tasks:
                serialized = _json(task.model_dump(mode="json"))
                previous = existing.get(task.id, additions.get(task.id))
                if previous is not None and previous != serialized:
                    raise ValueError(f"changed spec for task: {task.id}")
                if task.id not in existing:
                    additions[task.id] = serialized
            graph = [TaskSpec.model_validate(json.loads(spec)) for spec in existing.values()]
            graph.extend(TaskSpec.model_validate(json.loads(spec)) for spec in additions.values())
            validate_task_graph(graph)
            now = self._now()
            for task_id, spec in additions.items():
                self.connection.execute(
                    "INSERT INTO tasks(id, spec, state, created_at, updated_at) "
                    "VALUES (?, ?, 'pending', ?, ?)",
                    (task_id, spec, now, now),
                )
                self._event("task_added", {"task_id": task_id, "spec": json.loads(spec)}, now)

    def tasks(self) -> list[TaskSnapshot]:
        return [
            self._task_snapshot(row)
            for row in self.connection.execute("SELECT * FROM tasks ORDER BY id")
        ]

    def get_task(self, task_id: str) -> TaskSnapshot:
        return self._task_snapshot(self._task(task_id))

    def rebase_task(self, task_id: str, base_sha: str, expected_base_sha: str) -> None:
        """Explicitly change only an inactive task's base after dependency integration.

        Historical attempt identities remain intact; pending/blocked tasks have
        no active attempt. Unreconciled orphan attempts prevent rebasing. The
        expected base fences a concurrent supervisor's stale observation, and
        this operation neither resumes blocked tasks nor weakens add_tasks.
        """
        if (
            not isinstance(base_sha, str)
            or re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", base_sha) is None
        ):
            raise ValueError("base_sha must be a full 40 or 64 character hexadecimal commit SHA")
        with self._transaction():
            task = self._task(task_id)
            if task["state"] not in {"pending", "blocked"}:
                raise ValueError("rebase requires an inactive pending or blocked task")
            if task["reconciliation_required"]:
                raise ValueError("orphan attempt requires stop reconciliation before rebase")
            spec = json.loads(task["spec"])
            old_base = spec["base_sha"]
            if old_base != expected_base_sha:
                raise ValueError("task base changed since the expected base was observed")
            spec["base_sha"] = base_sha
            validated = TaskSpec.model_validate(spec)
            self.connection.execute(
                "UPDATE tasks SET spec = ? WHERE id = ?",
                (_json(validated.model_dump(mode="json")), task_id),
            )
            self._event(
                "task_rebased",
                {"task_id": task_id, "old_base_sha": old_base, "new_base_sha": base_sha},
                self._now(),
            )

    def claim(self, task_id: str, owner: str, ttl_seconds: float = 60) -> str:
        _nonempty(owner, "owner")
        with self._transaction():
            now = self._now()
            expiry = self._expiry(now, ttl_seconds)
            task = self._task(task_id)
            if task["state"] not in {"pending", "needs_repair"}:
                raise ValueError(f"task cannot be claimed in state: {task['state']}")
            spec = json.loads(task["spec"])
            for dependency in spec["depends_on"]:
                if self._task(dependency)["state"] not in DEPENDENCY_STATES:
                    raise ValueError(f"dependency is not approved: {dependency}")
            for other in self.connection.execute("SELECT * FROM tasks WHERE id != ?", (task_id,)):
                reserved = other["state"] in ACTIVE_STATES or other["reconciliation_required"]
                if reserved and paths_overlap(
                    spec["owned_paths"], json.loads(other["spec"])["owned_paths"]
                ):
                    raise ValueError(f"owned paths reserved by task: {other['id']}")
            attempt_id = uuid.uuid4().hex
            generation = task["generation"] + 1
            self.connection.execute(
                "INSERT INTO attempts(id, task_id, owner, generation, "
                "lease_expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (attempt_id, task_id, owner, generation, expiry, now),
            )
            self.connection.execute(
                "UPDATE tasks SET state = 'running', attempt_id = ?, owner = ?, "
                "generation = ?, lease_expires_at = ?, note = '', updated_at = ? WHERE id = ?",
                (attempt_id, owner, generation, expiry, now, task_id),
            )
            self._event(
                "task_claimed",
                {
                    "task_id": task_id,
                    "attempt_id": attempt_id,
                    "owner": owner,
                    "generation": generation,
                    "lease_expires_at": expiry,
                },
                now,
            )
            return attempt_id

    def heartbeat(self, attempt_id: str, owner: str, ttl_seconds: float = 60) -> None:
        with self._transaction():
            now = self._now()
            expiry = self._expiry(now, ttl_seconds)
            task = self._fence(attempt_id, owner, now)
            self.connection.execute(
                "UPDATE tasks SET lease_expires_at = ?, updated_at = ? WHERE id = ?",
                (expiry, now, task["id"]),
            )
            self.connection.execute(
                "UPDATE attempts SET lease_expires_at = ? WHERE id = ?", (expiry, attempt_id)
            )
            self.connection.execute(
                "UPDATE resources SET lease_expires_at = ? WHERE attempt_id = ? "
                "AND owner = ? AND generation = ?",
                (expiry, attempt_id, owner, task["generation"]),
            )
            self._event("heartbeat", {"attempt_id": attempt_id, "lease_expires_at": expiry}, now)

    def transition(
        self,
        task_id: str,
        state: str,
        attempt_id: str | None = None,
        owner: str | None = None,
        note: str = "",
    ) -> None:
        with self._transaction():
            now = self._now()
            task = self._task(task_id)
            current = task["state"]
            if state not in TRANSITIONS[current]:
                raise ValueError(f"invalid transition: {current} -> {state}")
            if state == "running":
                raise ValueError("enter running through claim()")
            if task["reconciliation_required"]:
                raise ValueError("orphan attempt requires stop reconciliation")
            if current in ACTIVE_STATES:
                if attempt_id is None or owner is None:
                    raise ValueError("active transition requires attempt and owner")
                fenced = self._fence(attempt_id, owner, now)
                if fenced["id"] != task_id:
                    raise ValueError("attempt belongs to a different task")
            elif attempt_id is not None and (
                task["attempt_id"] != attempt_id or task["owner"] != owner
            ):
                raise ValueError("attempt ownership does not match task")
            self.connection.execute(
                "UPDATE tasks SET state = ?, note = ?, updated_at = ? WHERE id = ?",
                (state, note, now, task_id),
            )
            if current in ACTIVE_STATES and state not in ACTIVE_STATES:
                self.connection.execute(
                    "DELETE FROM resources WHERE attempt_id = ?", (task["attempt_id"],)
                )
            self._event(
                "task_transition",
                {
                    "task_id": task_id,
                    "from": current,
                    "to": state,
                    "attempt_id": task["attempt_id"],
                    "note": note,
                },
                now,
            )

    def recover_expired(self) -> list[str]:
        """Block expired active tasks without releasing their orphan reservations."""
        with self._transaction():
            now = self._now()
            rows = self.connection.execute(
                "SELECT * FROM tasks WHERE state IN ('running', 'verifying', 'reviewing') "
                "AND lease_expires_at <= ? ORDER BY id",
                (now,),
            ).fetchall()
            for row in rows:
                note = "attempt lease expired; supervisor stop reconciliation required"
                self.connection.execute(
                    "UPDATE tasks SET state = 'blocked', reconciliation_required = 1, "
                    "note = ?, updated_at = ? WHERE id = ?",
                    (note, now, row["id"]),
                )
                self._event(
                    "attempt_expired",
                    {
                        "task_id": row["id"],
                        "attempt_id": row["attempt_id"],
                        "note": note,
                    },
                    now,
                )
            return [row["id"] for row in rows]

    def release_recovered(self, task_id: str, expected_attempt_id: str) -> None:
        """Attest this exact expired worker stopped; reject stale confirmations.

        The supervisor must retain the attempt ID from the process it confirmed
        stopped, rather than reading the latest attempt immediately before this
        call. Identity comparison and reservation release share a transaction.
        """
        with self._transaction():
            now = self._now()
            task = self._task(task_id)
            if task["attempt_id"] != expected_attempt_id:
                raise ValueError("stop confirmation belongs to a different attempt")
            if (
                task["state"] != "blocked"
                or not task["reconciliation_required"]
                or task["lease_expires_at"] is None
                or task["lease_expires_at"] > now
            ):
                raise ValueError("task is not an expired blocked attempt awaiting reconciliation")
            self.connection.execute(
                "DELETE FROM resources WHERE attempt_id = ?", (task["attempt_id"],)
            )
            self.connection.execute(
                "UPDATE tasks SET reconciliation_required = 0, updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            self._event(
                "attempt_reconciled",
                {
                    "task_id": task_id,
                    "attempt_id": task["attempt_id"],
                },
                now,
            )

    def acquire_resources(
        self,
        attempt_id: str,
        owner: str,
        names: list[str],
        ttl_seconds: float = 60,
    ) -> None:
        for name in names:
            _nonempty(name, "resource name")
        with self._transaction():
            now = self._now()
            expiry = self._expiry(now, ttl_seconds)
            task = self._fence(attempt_id, owner, now)
            for name in sorted(set(names)):
                row = self.connection.execute(
                    "SELECT * FROM resources WHERE name = ?", (name,)
                ).fetchone()
                if row is not None and (
                    row["attempt_id"] != attempt_id
                    or row["owner"] != owner
                    or row["generation"] != task["generation"]
                ):
                    raise ValueError(f"resource is reserved: {name}")
                self.connection.execute(
                    "INSERT INTO resources(name, attempt_id, owner, generation, lease_expires_at) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET "
                    "lease_expires_at = excluded.lease_expires_at",
                    (name, attempt_id, owner, task["generation"], expiry),
                )
            self._event(
                "resources_acquired",
                {
                    "attempt_id": attempt_id,
                    "owner": owner,
                    "names": sorted(set(names)),
                    "generation": task["generation"],
                    "lease_expires_at": expiry,
                },
                now,
            )

    def release_resources(self, attempt_id: str, owner: str) -> None:
        with self._transaction():
            now = self._now()
            task = self._fence(attempt_id, owner, now)
            self.connection.execute(
                "DELETE FROM resources WHERE attempt_id = ? AND owner = ? AND generation = ?",
                (attempt_id, owner, task["generation"]),
            )
            self._event("resources_released", {"attempt_id": attempt_id, "owner": owner}, now)

    def record_event(self, kind: str, payload: dict[str, Any]) -> None:
        with self._transaction():
            self._event(kind, payload, self._now())

    def events(self) -> list[dict[str, Any]]:
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in self.connection.execute("SELECT * FROM events ORDER BY id")
        ]

    def _effect(self, key: str) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM effects WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise ValueError(f"unknown effect: {key}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _effect_snapshot(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "key": row["key"],
            "kind": row["kind"],
            "payload": json.loads(row["payload"]),
            "status": row["status"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "note": row["note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def begin_effect(self, key: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        _nonempty(key, "effect key")
        _nonempty(kind, "effect kind")
        serialized = _json(payload)
        with self._transaction():
            now = self._now()
            existing = self.connection.execute(
                "SELECT * FROM effects WHERE key = ?", (key,)
            ).fetchone()
            if existing is not None:
                if existing["kind"] != kind or existing["payload"] != serialized:
                    raise ValueError("effect key reused with a different kind or payload")
                return self._effect_snapshot(existing)
            self.connection.execute(
                "INSERT INTO effects(key, kind, payload, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?)",
                (key, kind, serialized, now, now),
            )
            self._event("effect_started", {"key": key, "kind": kind, "payload": payload}, now)
            return self._effect_snapshot(self._effect(key))

    def finish_effect(self, key: str, result: dict[str, Any]) -> None:
        serialized = _json(result)
        with self._transaction():
            now = self._now()
            effect = self._effect(key)
            if effect["status"] == "completed":
                if effect["result"] != serialized:
                    raise ValueError("completed effect has a different result")
                return
            self.connection.execute(
                "UPDATE effects SET status = 'completed', result = ?, updated_at = ? WHERE key = ?",
                (serialized, now, key),
            )
            self._event("effect_completed", {"key": key, "result": result}, now)

    def mark_effect_uncertain(self, key: str, note: str) -> None:
        with self._transaction():
            now = self._now()
            effect = self._effect(key)
            if effect["status"] == "completed":
                raise ValueError("completed effect cannot become uncertain")
            self.connection.execute(
                "UPDATE effects SET status = 'uncertain', note = ?, updated_at = ? WHERE key = ?",
                (note, now, key),
            )
            self._event("effect_uncertain", {"key": key, "note": note}, now)

    def get_effect(self, key: str) -> dict[str, Any]:
        return self._effect_snapshot(self._effect(key))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
