"""Resumable project decisions, with no implicit execution or authority grants."""
from __future__ import annotations

import json
import keyword
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic_engineering.models import EnvironmentSpec, ProjectConfig
from agentic_engineering.profiles import get_profile

CONFIG = ".devctl/project.json"
INTERVIEW = ".devctl/interview.json"
_QUESTIONS: list[tuple[str, str]] = [
    ("repository", "Which GitHub repository will hold this project (owner/repository)?"),
    ("worker_runner", "Which coding CLI should implement tasks: codex or claude?"),
    ("worker_model", "Which available model should the worker CLI use?"),
    ("reviewer_runner", "Which coding CLI should independently review tasks: codex or claude?"),
    ("reviewer_model", "Which stronger available model should the reviewer CLI use?"),
    ("execution", "Which execution provider should this project use?"),
    ("image", "Which pinned container image should this environment use?"),
    ("allow_native", "Allow task commands to run natively on this host?"),
    ("resources", "Set max_parallel, memory_budget_mb and cpu_budget for this project."),
    ("test_resources", "Which registered external test resources are required?"),
    ("checks", "Which named verification commands should this project run?"),
    ("release_target", "Release to github-release, or none?"),
]


def _safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("Path must stay within the project")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing symlink in project path: {relative}")
    return current


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _design(root: Path, relative: str) -> Path:
    path = _safe_path(root, relative)
    if not path.is_file() or not path.read_text().strip():
        raise ValueError("An existing, nonempty approved design document is required")
    return path


def load_config(root: Path) -> ProjectConfig:
    config = ProjectConfig.model_validate(_read_json(_safe_path(root, CONFIG)))
    if not config.environments:
        raise ValueError("Project configuration requires at least one environment")
    return config


def save_config(root: Path, config: ProjectConfig) -> None:
    _write_json(_safe_path(root, CONFIG), config.model_dump(mode="json"))


def init_project(
    root: Path, name: str, design_path: str, profile: str = "python-cli"
) -> dict[str, Any]:
    root = root.resolve()
    _design(root, design_path)
    config_path = _safe_path(root, CONFIG)
    profile_data = get_profile(profile)
    created: list[str] = []
    if config_path.exists():
        load_config(root)
    else:
        config = ProjectConfig(
            name=name,
            design_path=design_path,
            profile=profile,
            checks=profile_data["checks"],
            environments=[
                EnvironmentSpec(
                    name="default", workspace="clone", execution="native", private_network=False
                )
            ],
        )
        save_config(root, config)
        created.append(CONFIG)
    interview_path = _safe_path(root, INTERVIEW)
    if not interview_path.exists():
        _write_json(interview_path, {"schema_version": 1, "answers": {}})
        created.append(INTERVIEW)
    ignore = _safe_path(root, ".devctl/.gitignore")
    if not ignore.exists():
        ignore.write_text("/state/\n")
        created.append(".devctl/.gitignore")
    elif "/state/" not in ignore.read_text().splitlines():
        raise ValueError("Add /state/ to .devctl/.gitignore before using runtime state")
    for relative, data in [(".devctl/profile.json", profile_data)]:
        destination = _safe_path(root, relative)
        if not destination.exists():
            _write_json(destination, data)
            created.append(relative)
    instructions = _safe_path(root, ".devctl/AGENTS.md")
    if not instructions.exists():
        instructions.write_text(
            "# Project delivery instructions\n\n"
            "Run `devctl doctor --json` before dispatch.\n"
            "Read the approved design and task contract.\n"
            "Use the assigned environment and named checks.\n"
            "Never expand task ownership or authority.\n"
            "Provide reproducible evidence; a worker report does not approve its own changes.\n"
            "See `.devctl/project.json` for project decisions.\n"
            "State files belong in `.devctl/state/`.\n"
        )
        created.append(".devctl/AGENTS.md")
    return {"created": created, "next_question": interview_next(root), "ready": False}


def _interview(root: Path) -> dict[str, Any]:
    state = _read_json(_safe_path(root, INTERVIEW))
    if state.get("schema_version") != 1 or not isinstance(state.get("answers"), dict):
        raise ValueError("Invalid interview state")
    known = {key for key, _ in _QUESTIONS}
    for key, record in state["answers"].items():
        if key not in known or not isinstance(record, dict):
            raise ValueError("Invalid interview answer record")
        if set(record) != {"value", "source", "recorded_at"}:
            raise ValueError("Invalid interview answer fields")
        if record["source"] != "explicit-answer" or not isinstance(record["recorded_at"], str):
            raise ValueError("Invalid interview answer provenance")
        try:
            datetime.fromisoformat(record["recorded_at"])
        except ValueError as error:
            raise ValueError("Invalid interview answer timestamp") from error
        if record["value"] is None:
            raise ValueError("Invalid interview answer value")
    return state


def interview_next(root: Path) -> dict[str, Any]:
    config = load_config(root)
    answers = _interview(root)["answers"]
    execution = config.environments[0].execution
    for key, prompt in _QUESTIONS:
        if key == "allow_native" and execution != "native":
            continue
        if key == "image" and execution not in {"docker", "openhands"}:
            continue
        answered = key in answers
        if answered:
            # Replay validation without writes; a changed config invalidates stale answers.
            proposed = _answer_config(config, key, answers[key]["value"])
            original = config.model_dump(mode="json")
            replayed = proposed.model_dump(mode="json")
            if key == "execution":
                answered = original["environments"][0]["execution"] == answers[key]["value"]
            elif key in {"image", "allow_native", "test_resources"}:
                answered = original["environments"][0][key] == answers[key]["value"]
            elif key == "resources":
                answered = all(original[k] == v for k, v in answers[key]["value"].items())
            else:
                answered = original[key] == replayed[key]
        if not answered:
            return {"complete": False, "id": key, "question": prompt}
    return {"complete": True}


def _answer_config(config: ProjectConfig, question_id: str, value: Any) -> ProjectConfig:
    if question_id not in {key for key, _ in _QUESTIONS}:
        raise ValueError(f"Unknown question: {question_id}")
    data = config.model_dump(mode="json")
    if question_id == "repository":
        if not isinstance(value, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
            raise ValueError("Repository must have the form owner/repository")
        data["repository"] = value
    elif question_id in {"worker_runner", "reviewer_runner"}:
        if not isinstance(value, str) or value not in {"codex", "claude"}:
            raise ValueError("Runner must be codex or claude")
        data[question_id] = value
    elif question_id in {"worker_model", "reviewer_model"}:
        if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
            raise ValueError("An explicit model identifier is required")
        data[question_id] = value
    elif question_id == "execution":
        if not isinstance(value, str) or value not in {"native", "docker", "sbx", "openhands"}:
            raise ValueError("Unsupported execution provider")
        data["environments"][0].update(
            execution=value, private_network=value != "native", allow_native=False, verified=False
        )
    elif question_id == "image":
        if not isinstance(value, str) or not value.strip() or any(c.isspace() for c in value):
            raise ValueError("A container image is required")
        data["environments"][0]["image"] = value
        data["environments"][0]["verified"] = False
    elif question_id == "allow_native":
        if not isinstance(value, bool) or data["environments"][0]["execution"] != "native":
            raise ValueError("Native execution requires an explicit boolean answer")
        data["environments"][0]["allow_native"] = value
    elif question_id == "resources":
        if not isinstance(value, dict) or set(value) != {
            "memory_budget_mb", "cpu_budget", "max_parallel"
        }:
            raise ValueError("Resources require memory_budget_mb, cpu_budget and max_parallel")
        data.update(value)
    elif question_id == "test_resources":
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError("Test resources must be a list of registered resource names")
        data["environments"][0]["test_resources"] = value
        data["environments"][0]["verified"] = False
    elif question_id == "checks":
        if not isinstance(value, dict) or not value:
            raise ValueError("At least one named verification command is required")
        data["checks"] = value
    elif question_id == "release_target":
        if not isinstance(value, str) or value not in {"github-release", "none"}:
            raise ValueError("Release target must be github-release or none")
        data["release_target"] = value
    return ProjectConfig.model_validate(data)


def answer_question(root: Path, question_id: str, value: Any) -> dict[str, Any]:
    config = load_config(root)
    state = _interview(root)
    updated = _answer_config(config, question_id, value)
    if question_id == "execution":
        for dependent in ("allow_native", "image"):
            state["answers"].pop(dependent, None)
    state["answers"][question_id] = {
        "value": value,
        "source": "explicit-answer",
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    save_config(root, updated)
    _write_json(_safe_path(root, INTERVIEW), state)
    return interview_next(root)


def doctor(root: Path) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    config: ProjectConfig | None = None
    complete = False
    try:
        config = load_config(root)
        _design(root, config.design_path)
        complete = bool(interview_next(root)["complete"])
        if not complete:
            blockers.append("Complete the project interview")
        for environment in config.environments:
            if environment.execution == "native" and not environment.allow_native:
                blockers.append(
                    f"{environment.name}: native execution has not been explicitly allowed"
                )
            if not environment.verified:
                warnings.append(f"{environment.name}: live compatibility trial not verified")
            if environment.resources.memory_mb > config.memory_budget_mb:
                blockers.append(f"{environment.name}: requested memory exceeds project budget")
            if environment.resources.cpu > config.cpu_budget:
                blockers.append(f"{environment.name}: requested CPU exceeds project budget")
    except (ValueError, OSError) as error:
        blockers.append(str(error))
    return {
        "ready": not blockers,
        "configuration_ready": config is not None and complete and not blockers,
        "autonomy_ready": False,
        "blockers": blockers,
        "warnings": warnings,
        "next_step": "interview" if not complete else "trial",
    }


def scaffold_feature(root: Path, name: str) -> list[str]:
    load_config(root)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise ValueError("Feature name must be a lowercase Python identifier")
    relative_module = f"src/features/{name}.py"
    relative_test = f"tests/test_{name}.py"
    paths = [_safe_path(root, item) for item in [relative_module, relative_test]]
    if any(path.exists() for path in paths):
        raise ValueError("Refusing to overwrite an existing feature")
    contents = [
        f'"""{name} feature: replace this behaviour with the approved task contract."""\n\n'
        f'def run(value: str) -> str:\n    return f"{name}: {{value}}"\n',
        "from pathlib import Path\nfrom runpy import run_path\n\n\n"
        f"def test_{name}_formats_input():\n"
        f'    feature = Path(__file__).parents[1] / "src/features/{name}.py"\n'
        f'    assert run_path(str(feature))["run"]("example") == "{name}: example"\n',
    ]
    for path, content in zip(paths, contents, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            stream.write(content)
    return [relative_module, relative_test]
