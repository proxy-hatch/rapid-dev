"""Persisted interviews reject malformed records without changing project decisions."""

import json
from pathlib import Path

import pytest

from rapid_ship.project.configuration import (
    answer_question,
    doctor,
    init_project,
    interview_next,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "example", "design.md")
    return tmp_path


def snapshot(root: Path) -> dict[Path, tuple[bytes, int]]:
    return {
        path.relative_to(root): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("operation", ["next", "answer", "doctor"])
@pytest.mark.parametrize(
    "state",
    [
        pytest.param({"schema_version": True, "answers": {}}, id="boolean-true"),
        pytest.param({"schema_version": 1.0, "answers": {}}, id="float-one"),
        pytest.param({"schema_version": 2.0, "answers": {}}, id="float-two"),
        pytest.param({"schema_version": False, "answers": {}}, id="boolean-false"),
        pytest.param({"schema_version": "2", "answers": {}}, id="string-two"),
        pytest.param({"schema_version": 3, "answers": {}}, id="unknown-version"),
        pytest.param({"schema_version": None, "answers": {}}, id="null-version"),
        pytest.param({"answers": {}}, id="missing-version"),
    ],
)
def test_invalid_schema_is_rejected_without_writes(project, operation, state):
    (project / ".devctl/interview.json").write_text(json.dumps(state))
    before = snapshot(project)

    if operation == "doctor":
        report = doctor(project)
        assert not report["configuration_ready"]
        assert any("interview state" in blocker.lower() for blocker in report["blockers"])
    else:
        with pytest.raises(ValueError, match="interview state"):
            if operation == "next":
                interview_next(project)
            else:
                answer_question(project, "repository", "owner/example")

    assert snapshot(project) == before


REPOSITORY_RECORD = {
    "value": "owner/example",
    "source": "explicit-answer",
    "recorded_at": "2026-10-10T10:00:00+00:00",
}


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(None, id="null-answers"),
        pytest.param([], id="list-answers"),
        pytest.param({"unknown-question": REPOSITORY_RECORD}, id="unknown-question"),
        pytest.param({"repository": []}, id="list-record"),
        pytest.param(
            {"repository": {**REPOSITORY_RECORD, "extra": "untrusted"}}, id="extra-record-field"
        ),
        *[
            pytest.param(
                {
                    "repository": {
                        key: value for key, value in REPOSITORY_RECORD.items() if key != field
                    }
                },
                id=f"missing-{field}",
            )
            for field in ("value", "source", "recorded_at")
        ],
        pytest.param(
            {"repository": {**REPOSITORY_RECORD, "source": "inferred"}}, id="inferred-provenance"
        ),
        pytest.param(
            {"repository": {**REPOSITORY_RECORD, "recorded_at": 123}}, id="numeric-timestamp"
        ),
        pytest.param(
            {"repository": {**REPOSITORY_RECORD, "recorded_at": "yesterday"}},
            id="invalid-timestamp",
        ),
        pytest.param({"repository": {**REPOSITORY_RECORD, "value": None}}, id="null-value"),
    ],
)
def test_invalid_answer_records_block_readers_and_writers_without_changes(project, answers):
    (project / ".devctl/interview.json").write_text(
        json.dumps({"schema_version": 2, "answers": answers})
    )
    before = snapshot(project)

    with pytest.raises(ValueError, match="interview"):
        interview_next(project)
    assert snapshot(project) == before
    with pytest.raises(ValueError, match="interview"):
        answer_question(project, "repository", "owner/replacement")
    assert snapshot(project) == before
    report = doctor(project)
    assert not report["configuration_ready"]
    assert any("interview" in blocker.lower() for blocker in report["blockers"])
    assert snapshot(project) == before


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-10T10:00:00",
        "2026-10-10",
        "2026-10-10T10:00:00+08:00",
        "2026-10-10T10:00:00Z",
    ],
)
def test_resume_preserves_version_timestamp_and_top_level_extensions(project, version, timestamp):
    from datetime import UTC, datetime

    answer_question(project, "repository", "owner/example")
    path = project / ".devctl/interview.json"
    state = json.loads(path.read_text())
    state["schema_version"] = version
    state["answers"]["repository"]["recorded_at"] = timestamp
    state["notes"] = {"owner": "Shawn", "flags": [True, None, {"text": "已核准"}]}
    path.write_text(json.dumps(state))
    before = snapshot(project)

    expected_question = "worker_runner" if version == 1 else "providers"
    assert interview_next(project)["id"] == expected_question
    report = doctor(project)
    assert "Complete the project interview" in report["blockers"]
    assert snapshot(project) == before

    value = "claude" if version == 1 else ["codex"]
    started = datetime.now(UTC)
    next_question = answer_question(project, expected_question, value)
    finished = datetime.now(UTC)

    assert next_question["id"] == ("worker_model" if version == 1 else "models")
    saved = json.loads(path.read_text())
    assert type(saved["schema_version"]) is int
    assert saved["schema_version"] == version
    assert saved["notes"] == state["notes"]
    assert saved["answers"]["repository"] == state["answers"]["repository"]
    record = saved["answers"][expected_question]
    assert set(record) == {"value", "source", "recorded_at"}
    assert record["value"] == value
    assert record["source"] == "explicit-answer"
    assert started <= datetime.fromisoformat(record["recorded_at"]) <= finished


def test_stale_answer_is_reasked_without_restoring_old_project_choice(project):
    from rapid_ship.project.configuration import load_config, save_config

    answer_question(project, "repository", "owner/original")
    config = load_config(project)
    save_config(project, config.model_copy(update={"repository": "owner/changed"}))
    before = snapshot(project)

    assert interview_next(project)["id"] == "repository"
    assert "Complete the project interview" in doctor(project)["blockers"]
    assert snapshot(project) == before
    assert load_config(project).repository == "owner/changed"


@pytest.mark.parametrize("dependent,value", [("allow_native", False), ("image", "example/agent")])
def test_execution_change_discards_dependent_answer_and_preserves_other_records(
    project, dependent, value
):
    from rapid_ship.project.configuration import load_config

    answer_question(project, "repository", "owner/example")
    answer_question(project, dependent, value)
    answer_question(project, "test_resources", [])
    path = project / ".devctl/interview.json"
    before = json.loads(path.read_text())["answers"]
    assert before[dependent]["value"] == value
    assert before["test_resources"]["value"] == []

    answer_question(project, "execution", "docker")

    saved = json.loads(path.read_text())["answers"]
    assert dependent not in saved
    assert saved["repository"] == before["repository"]
    assert saved["test_resources"] == before["test_resources"]
    assert saved["execution"]["value"] == "docker"
    assert load_config(project).environments[0].execution == "docker"


@pytest.mark.parametrize("keep_models", [True, False])
def test_provider_change_discards_model_answer_only_when_tiers_are_incompatible(
    project, keep_models
):
    from datetime import UTC, datetime

    from rapid_ship.project.configuration import load_config, save_provider_records

    answer_question(project, "repository", "owner/example")
    answer_question(project, "providers", ["codex", "claude"])
    save_provider_records(
        project,
        [
            {
                "provider": provider,
                "authenticated": True,
                "checked_at": datetime.now(UTC).isoformat(),
                "models": [{"id": model}],
            }
            for provider, model in [("codex", "worker"), ("claude", "reviewer")]
        ],
    )
    choices = {
        "small": {"provider": "codex", "model": "worker"},
        "large": {"provider": "claude", "model": "reviewer"},
    }
    answer_question(project, "models", choices)
    path = project / ".devctl/interview.json"
    before = json.loads(path.read_text())["answers"]

    providers = ["codex", "claude", "agy"] if keep_models else ["codex"]
    question = answer_question(project, "providers", providers)

    saved = json.loads(path.read_text())["answers"]
    assert saved["repository"] == before["repository"]
    assert saved["providers"]["value"] == providers
    if keep_models:
        assert saved["models"] == before["models"]
        assert question["id"] == "guidance"
        assert load_config(project).models["large"].model == "reviewer"
    else:
        assert "models" not in saved
        assert question["id"] == "models"
        assert load_config(project).models == {}
