"""Diagnostic reads preserve source files and expose only summary-shaped data."""

import json
import sqlite3

from agentic_engineering.logs import read_logs, record_command
from agentic_engineering.storage import Store


def test_reading_closed_wal_database_creates_no_project_files(tmp_path):
    database = tmp_path / "workflow.db"
    with Store(database) as store:
        store.record_event("state", {"task_id": "hello", "state": "approved"})
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    result = read_logs(tmp_path)

    assert result["events"][0]["details"]["state"] == "approved"
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_reading_logs_includes_committed_live_wal_events(tmp_path):
    with Store(tmp_path / "workflow.db") as store:
        store.record_event("state", {"task_id": "hello", "state": "implementing"})
        before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

        result = read_logs(tmp_path, task_id="hello")

        assert result["events"][0]["details"]["state"] == "implementing"
        assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_malformed_event_payload_is_reported_without_crashing(tmp_path):
    with Store(tmp_path / "workflow.db") as store:
        store.record_event("state", {"task_id": "hello"})
    with sqlite3.connect(tmp_path / "workflow.db") as connection:
        connection.execute("UPDATE events SET payload = ?", ("[]",))

    result = read_logs(tmp_path)

    assert result["events"][0]["status"] == "invalid event record"


def test_summary_fields_do_not_return_nested_event_or_command_data(tmp_path):
    with Store(tmp_path / "workflow.db") as store:
        store.record_event("state", {"task_id": "hello", "model": {"raw_prompt": "SECRET_PROMPT"}})
    (tmp_path / "commands.jsonl").write_text(
        json.dumps(
            {
                "at": "now",
                "command": {"secret": "SECRET_COMMAND"},
                "exit_code": 0,
                "duration_seconds": 1,
            }
        )
        + "\n"
    )

    result = read_logs(tmp_path)

    assert result["events"][0]["details"] == {"task_id": "hello"}
    assert result["commands"] == [{"status": "incomplete log record"}]
    assert "SECRET" not in json.dumps(result)


def test_command_record_round_trip_and_truncated_tail(tmp_path):
    record_command(tmp_path, "interview", 0, 1.23456789)
    with (tmp_path / "commands.jsonl").open("a") as stream:
        stream.write('{"at":')

    result = read_logs(tmp_path)

    assert result["commands"][0]["command"] == "interview"
    assert result["commands"][0]["duration_seconds"] == 1.234568
    assert result["commands"][1] == {"status": "incomplete log record"}


def test_log_read_retries_when_database_changes_during_copy(tmp_path, monkeypatch):
    from agentic_engineering import logs

    database = tmp_path / "workflow.db"
    with Store(database) as store:
        store.record_event("state", {"task_id": "hello", "state": "implementing"})
    copy = logs.shutil.copyfile
    changed = False

    def copy_then_commit(source, destination):
        nonlocal changed
        result = copy(source, destination)
        if source == database and not changed:
            changed = True
            with Store(database) as store:
                store.record_event("state", {"task_id": "hello", "state": "reviewing"})
        return result

    monkeypatch.setattr(logs.shutil, "copyfile", copy_then_commit)

    result = read_logs(tmp_path)

    assert [event["details"]["state"] for event in result["events"]] == [
        "implementing",
        "reviewing",
    ]
