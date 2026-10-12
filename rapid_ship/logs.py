"""Local diagnostic summaries; raw prompts and command output stay out of this log."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections import deque
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

_FIELDS = {
    "task_id",
    "attempt_id",
    "from",
    "to",
    "state",
    "head_sha",
    "base_sha",
    "role",
    "runner",
    "model",
    "round",
    "exit_code",
    "duration_seconds",
}


def record_command(state: Path, command: str, exit_code: int, duration: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    record = {
        "at": datetime.now(UTC).isoformat(),
        "command": command,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 6),
    }
    destination = state / "commands.jsonl"
    fd = os.open(destination, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        data = (json.dumps(record, sort_keys=True) + "\n").encode()
        if os.write(fd, data) != len(data):
            raise OSError("Incomplete command log write")
    finally:
        os.close(fd)


def _stamp(path: Path) -> tuple[int, int, int, int] | None:
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _copy_database(database: Path, destination: Path) -> None:
    sources = (database, database.with_name(database.name + "-wal"))
    for _ in range(3):
        before = tuple(_stamp(path) for path in sources)
        try:
            for source, stamp in zip(sources, before, strict=True):
                target = destination.parent / source.name
                target.unlink(missing_ok=True)
                if stamp is not None:
                    shutil.copyfile(source, target)
        except FileNotFoundError:
            continue
        if before[0] is not None and before == tuple(_stamp(path) for path in sources):
            return
    raise ValueError("Workflow log changed during the read; try logs again")


def _event_rows(database: Path, task_id: str | None, limit: int) -> list[Any]:
    # A read-only SQLite connection still creates or writes WAL shared-memory files.
    # Query a stable private copy so diagnostics never change project state.
    with TemporaryDirectory(prefix="rapid-ship-logs-") as directory:
        snapshot = Path(directory) / database.name
        _copy_database(database, snapshot)
        with closing(sqlite3.connect(snapshot)) as connection:
            query = "SELECT id, kind, payload, created_at FROM events"
            parameters: list[Any] = []
            if task_id is not None:
                query += (
                    " WHERE CASE WHEN json_valid(payload) "
                    "THEN json_extract(payload, '$.task_id') END = ?"
                )
                parameters.append(task_id)
            query += " ORDER BY id DESC LIMIT ?"
            parameters.append(limit)
            return connection.execute(query, parameters).fetchall()


def read_logs(state: Path, task_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    if not 1 <= limit <= 1000:
        raise ValueError("Log limit must be between 1 and 1000")
    events: list[dict[str, Any]] = []
    database = state / "workflow.db"
    if database.is_file():
        for event_id, kind, payload, at in reversed(_event_rows(database, task_id, limit)):
            try:
                data = json.loads(payload)
                if not isinstance(data, dict) or not isinstance(kind, str):
                    raise ValueError("Invalid event shape")
                events.append(
                    {
                        "id": event_id,
                        "kind": kind,
                        "at": datetime.fromtimestamp(at, UTC).isoformat(),
                        "details": {
                            key: value
                            for key, value in data.items()
                            if key in _FIELDS and type(value) in (str, int, float, bool, type(None))
                        },
                    }
                )
            except (ValueError, TypeError, OverflowError, OSError):
                events.append({"id": event_id, "status": "invalid event record"})
    commands: list[dict[str, Any]] = []
    path = state / "commands.jsonl"
    if path.is_file():
        with path.open() as stream:
            recent = deque(stream, maxlen=limit)
        for line in recent:
            try:
                record = json.loads(line)
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("at"), str)
                    or not isinstance(record.get("command"), str)
                    or type(record.get("exit_code")) is not int
                    or type(record.get("duration_seconds")) not in (int, float)
                ):
                    raise ValueError("Invalid command summary")
                commands.append(
                    {key: record[key] for key in ("at", "command", "exit_code", "duration_seconds")}
                )
            except (ValueError, KeyError, TypeError):
                commands.append({"status": "incomplete log record"})
    return {"events": events, "commands": commands, "task_filter": task_id}
