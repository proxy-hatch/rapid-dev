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
    init_project(tmp_path, "example", "design.md")
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
