"""Onboarding must preserve user decisions and never grant authority implicitly."""

import json
from pathlib import Path

import pytest

from agentic_engineering.configuration import (
    answer_question,
    doctor,
    init_project,
    interview_next,
    load_config,
    scaffold_feature,
)


def design(root: Path) -> None:
    (root / "design.md").write_text("# Approved design\nA small command line application.\n")


def test_doctor_on_missing_project_is_read_only(tmp_path: Path) -> None:
    assert not doctor(tmp_path)["ready"]
    assert list(tmp_path.iterdir()) == []


def test_init_preserves_existing_files_and_answers(tmp_path: Path) -> None:
    design(tmp_path)
    (tmp_path / "AGENTS.md").write_text("Existing project instructions\n")
    init_project(tmp_path, "example", "design.md")
    answer_question(tmp_path, "repository", "owner/example")
    config_before = (tmp_path / ".devctl/project.json").read_bytes()
    interview_before = (tmp_path / ".devctl/interview.json").read_bytes()
    init_project(tmp_path, "changed", "design.md")
    assert (tmp_path / "AGENTS.md").read_text() == "Existing project instructions\n"
    assert (tmp_path / ".devctl/project.json").read_bytes() == config_before
    assert (tmp_path / ".devctl/interview.json").read_bytes() == interview_before
    assert load_config(tmp_path).name == "example"


def test_invalid_answer_does_not_advance_interview(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    before = interview_next(tmp_path)
    with pytest.raises(ValueError):
        answer_question(tmp_path, "repository", "not a repository")
    assert interview_next(tmp_path) == before


def test_native_execution_requires_explicit_decision(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    assert not load_config(tmp_path).environments[0].allow_native
    assert not doctor(tmp_path)["ready"]
    answer_question(tmp_path, "execution", "native")
    assert not load_config(tmp_path).environments[0].allow_native
    answer_question(tmp_path, "allow_native", True)
    assert load_config(tmp_path).environments[0].allow_native
    assert not load_config(tmp_path).environments[0].verified


def test_complete_interview_is_separate_from_environment_verification(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    for key, value in {
        "repository": "owner/example",
        "worker_runner": "codex",
        "worker_model": "worker-model",
        "reviewer_runner": "claude",
        "reviewer_model": "reviewer-model",
        "execution": "native",
        "allow_native": True,
        "resources": {"memory_budget_mb": 8192, "cpu_budget": 4, "max_parallel": 3},
        "test_resources": [],
        "checks": {"unit": ["python", "-m", "pytest"]},
        "release_target": "github-release",
    }.items():
        answer_question(tmp_path, key, value)
    assert interview_next(tmp_path)["complete"]
    state = doctor(tmp_path)
    assert state["configuration_ready"]
    assert not state["autonomy_ready"]
    assert load_config(tmp_path).memory_budget_mb == 8192
    assert load_config(tmp_path).max_parallel == 3


def test_missing_or_escaping_design_blocks_initialization(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        init_project(tmp_path, "example", "../outside.md")
    with pytest.raises(ValueError):
        init_project(tmp_path, "example", "missing.md")
    assert not (tmp_path / ".devctl").exists()


def test_symlinked_configuration_directory_is_rejected(tmp_path: Path) -> None:
    design(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".devctl").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        init_project(tmp_path, "example", "design.md")
    assert list(outside.iterdir()) == []


def test_invalid_existing_configuration_is_not_overwritten(tmp_path: Path) -> None:
    design(tmp_path)
    (tmp_path / ".devctl").mkdir()
    path = tmp_path / ".devctl/project.json"
    path.write_text('{"unknown":"keep me"}')
    with pytest.raises(ValueError):
        init_project(tmp_path, "example", "design.md")
    assert path.read_text() == '{"unknown":"keep me"}'


def test_scaffold_is_executable_and_refuses_overwrites(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md", profile="python-cli")
    paths = scaffold_feature(tmp_path, "greet")
    module_path = tmp_path / "src/features/greet.py"
    scope: dict[str, object] = {}
    exec(compile(module_path.read_text(), str(module_path), "exec"), scope)
    assert callable(scope["run"])
    assert scope["run"]("Shawn") == "greet: Shawn"
    assert "src/features/greet.py" in paths
    with pytest.raises(ValueError):
        scaffold_feature(tmp_path, "greet")
    with pytest.raises(ValueError):
        scaffold_feature(tmp_path, "../../escape")


def test_interview_records_provenance(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    answer_question(tmp_path, "repository", "owner/example")
    state = json.loads((tmp_path / ".devctl/interview.json").read_text())
    assert state["answers"]["repository"]["source"] == "explicit-answer"
    assert "recorded_at" in state["answers"]["repository"]


def test_empty_environment_list_is_reported_as_blocker(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    path = tmp_path / ".devctl/project.json"
    value = json.loads(path.read_text())
    value["environments"] = []
    path.write_text(json.dumps(value))
    assert not doctor(tmp_path)["ready"]


def test_malformed_answer_records_cannot_complete_interview(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    path = tmp_path / ".devctl/interview.json"
    path.write_text(json.dumps({"schema_version": 1, "answers": {"repository": None}}))
    assert not doctor(tmp_path)["configuration_ready"]
    with pytest.raises(ValueError, match="answer"):
        interview_next(tmp_path)


def test_python_keyword_is_not_a_feature_name(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md", profile="python-cli")
    with pytest.raises(ValueError):
        scaffold_feature(tmp_path, "class")


def test_scaffold_runs_in_a_fresh_project(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    design(tmp_path)
    init_project(tmp_path, "example", "design.md", profile="python-cli")
    scaffold_feature(tmp_path, "greet")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=tmp_path,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_state_is_ignored_in_consumer_repository(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    result = subprocess.run(
        ["git", "check-ignore", ".devctl/state/runtime.json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


@pytest.mark.parametrize("answer", [[], {}, ["codex"]])
def test_unhashable_interview_answers_are_reported_as_blockers(tmp_path, answer):
    import json

    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "test", "design.md")
    answer_question(tmp_path, "repository", "owner/repo")
    path = tmp_path / ".devctl/interview.json"
    data = json.loads(path.read_text())
    data["answers"]["worker_runner"] = {
        "value": answer,
        "source": "explicit-answer",
        "recorded_at": "2026-10-10T10:00:00+00:00",
    }
    path.write_text(json.dumps(data))
    assert not doctor(tmp_path)["ready"]


def test_default_project_accepts_non_python_checks_without_python_files(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    config = load_config(tmp_path)
    assert config.profile == "custom"
    assert config.checks == {}
    checks = {"unit": ["cargo", "test", "--locked"], "web": ["npm", "test", "--", "--run"]}
    answer_question(tmp_path, "checks", checks)
    assert load_config(tmp_path).checks == checks
    assert not list(tmp_path.rglob("*.py"))
    assert not list(tmp_path.rglob("pyproject.toml"))


@pytest.mark.parametrize(
    ("stored_profile", "requested_profile"),
    [("python-cli", "custom"), ("custom", "python-cli")],
)
def test_reinitialization_uses_stored_profile_for_missing_generated_files(
    tmp_path: Path, stored_profile: str, requested_profile: str
) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md", profile=stored_profile)
    profile_path = tmp_path / ".devctl/profile.json"
    original_profile = profile_path.read_bytes()
    original_config = (tmp_path / ".devctl/project.json").read_bytes()
    profile_path.unlink()

    init_project(tmp_path, "example", "design.md", profile=requested_profile)

    assert profile_path.read_bytes() == original_profile
    assert (tmp_path / ".devctl/project.json").read_bytes() == original_config


def test_custom_scaffold_reports_missing_template_without_writing_files(tmp_path: Path) -> None:
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    with pytest.raises(ValueError, match="[Ss]caffold.*custom"):
        scaffold_feature(tmp_path, "greet")
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_agy_worker_choice_is_saved_without_claiming_native_compatibility(tmp_path):
    design(tmp_path)
    init_project(tmp_path, "example", "design.md")
    answer_question(tmp_path, "worker_runner", "agy")
    answer_question(tmp_path, "worker_model", "gemini-3.7-flash-medium")
    answer_question(tmp_path, "execution", "native")
    answer_question(tmp_path, "allow_native", True)
    assert load_config(tmp_path).worker_runner == "agy"
    assert any("agy" in item for item in doctor(tmp_path)["blockers"])
    with pytest.raises(ValueError, match="review"):
        answer_question(tmp_path, "reviewer_runner", "agy")
