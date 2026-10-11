"""Resumable project decisions, with no implicit execution or authority grants."""

from __future__ import annotations

import json
import keyword
import os
import re
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from agentic_engineering.communication import WRITING_RULES
from agentic_engineering.models import EnvironmentSpec, ProjectConfig
from agentic_engineering.profiles import get_profile

CONFIG = ".devctl/project.json"
INTERVIEW = ".devctl/interview.json"
PROVIDERS = ".devctl/providers.json"
_LEGACY_QUESTIONS: list[tuple[str, str]] = [
    ("repository", "Which GitHub repository will hold this project (owner/repository)?"),
    ("worker_runner", "Which coding CLI should implement tasks: codex, claude, or agy (Docker)?"),
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


_QUESTIONS = [
    _LEGACY_QUESTIONS[0],
    ("providers", "Which coding providers should this project use: codex, claude or agy?"),
    (
        "models",
        "Choose a small worker and a large reviewer from your provider models. Medium is optional.",
    ),
    ("guidance", "Keep the default concise writing and simple-code rules, or change them?"),
    *_LEGACY_QUESTIONS[5:],
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
    root: Path,
    name: str,
    design_path: str,
    profile: str = "custom",
    *,
    framework_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    _design(root, design_path)
    wrapper = _safe_path(root, "devctl")
    config_path = _safe_path(root, CONFIG)
    created: list[str] = []
    if config_path.exists():
        config = load_config(root)
        profile_data = get_profile(config.profile)
    else:
        profile_data = get_profile(profile)
        config = ProjectConfig(
            name=name,
            design_path=design_path,
            profile=profile,
            checks=profile_data.get("checks", {}),
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
        _write_json(interview_path, {"schema_version": 2, "answers": {}})
        created.append(INTERVIEW)
    ignore = _safe_path(root, ".devctl/.gitignore")
    if not ignore.exists():
        ignore.write_text("/state/\n/local.json\n/providers.json\n")
        created.append(".devctl/.gitignore")
    elif "/state/" not in ignore.read_text().splitlines():
        raise ValueError("Add /state/ to .devctl/.gitignore before using runtime state")
    for entry in ("/local.json", "/providers.json"):
        if entry not in ignore.read_text().splitlines():
            with ignore.open("a") as stream:
                stream.write(f"\n{entry}\n")
    for relative, data in [(".devctl/profile.json", profile_data)]:
        destination = _safe_path(root, relative)
        if not destination.exists():
            _write_json(destination, data)
            created.append(relative)
    instructions = _safe_path(root, ".devctl/AGENTS.md")
    if not instructions.exists():
        instructions.write_text(
            "# Project delivery instructions\n\n"
            "Run `devctl doctor --json` before starting work.\n"
            "Read the approved design and assigned task.\n"
            "Use Linear for tasks and dependencies, and GitHub for code and PRs.\n"
            "Give each coding agent one leaf task: one testable outcome with code and tests.\n"
            "Choose model, harness, and environment separately; preserve compatible choices.\n"
            "Never silently switch models, harnesses, or environments.\n"
            "Use the assigned environment and checks. Change only assigned files.\n"
            "Stay within your permissions. Independent review is required for your changes.\n"
            "Record the commands and results so others can check them.\n"
            "Project choices and writing/code guidance are in `.devctl/project.json`.\n"
            "Read those choices before setup, implementation, review or documentation.\n"
            "Keep code simple; build only what the current task needs.\n"
            "Before coding or review, read "
            "`.agents/skills/rapid-ship-engineering/references/ponytail.md`.\n"
            "Before writing commits, PRs, documentation or agent reports, read "
            "`.agents/skills/rapid-ship-engineering/references/writing.md`.\n"
            "Use `.agents/skills/rapid-ship-engineering/SKILL.md` to load the relevant "
            "clarification, implementation, debugging, review or architecture guidance.\n"
            "Reuse `GLOSSARY.md` terms and relevant `docs/adr/` decisions when present.\n"
            "Clarify implementation decisions without questioning the project's purpose.\n"
            "State files belong in `.devctl/state/`.\n"
            f"\n{WRITING_RULES}\n"
        )
        created.append(".devctl/AGENTS.md")
    root_instructions = _safe_path(root, "AGENTS.md")
    if not root_instructions.exists():
        root_instructions.write_text("Read `.devctl/AGENTS.md` before project delivery work.\n")
        created.append("AGENTS.md")
    claude_instructions = _safe_path(root, "CLAUDE.md")
    if not claude_instructions.exists():
        claude_instructions.write_text("@AGENTS.md\n@.devctl/AGENTS.md\n")
        created.append("CLAUDE.md")
    for skill in ("rapid-ship", "rapid-ship-improve", "rapid-ship-engineering"):
        source = files("agentic_engineering").joinpath(f"skills/{skill}")
        for namespace in (".agents", ".claude"):
            created.extend(_copy_skill(source, root, f"{namespace}/skills/{skill}"))
    local = _safe_path(root, ".devctl/local.json")
    framework_root = framework_root or _installed_framework()
    if framework_root is not None and not local.exists():
        framework_root = framework_root.resolve()
        metadata = tomllib.loads((framework_root / "pyproject.toml").read_text())
        if metadata.get("project", {}).get("name") != "rapid-ship":
            raise ValueError("Framework path must point to a rapid-ship checkout")
        controller = framework_root / ".controller/bin/devctl"
        if not controller.is_file() or not os.access(controller, os.X_OK):
            raise ValueError("Build the framework controller with ./devctl setup first")
        _write_json(local, {"framework_root": str(framework_root), "controller": str(controller)})
        created.append(".devctl/local.json")
    if not wrapper.exists():
        template = files("agentic_engineering").joinpath("templates/devctl")
        with wrapper.open("xb") as stream:
            stream.write(template.read_bytes())
            os.fchmod(stream.fileno(), 0o755)
        created.append("devctl")
    instruction_updates = [
        relative
        for relative, references in (
            (
                ".devctl/AGENTS.md",
                (
                    ".agents/skills/rapid-ship-engineering/references/ponytail.md",
                    ".agents/skills/rapid-ship-engineering/references/writing.md",
                ),
            ),
            ("AGENTS.md", (".devctl/AGENTS.md",)),
            ("CLAUDE.md", ("@.devctl/AGENTS.md",)),
        )
        if any(reference not in _safe_path(root, relative).read_text() for reference in references)
    ]
    return {
        "created": created,
        "instruction_updates": instruction_updates,
        "next_question": interview_next(root),
        "ready": False,
    }


def _copy_skill(source: Any, root: Path, relative: str) -> list[str]:
    destination = _safe_path(root, relative)
    destination.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for child in source.iterdir():
        child_relative = f"{relative}/{child.name}"
        target = _safe_path(root, child_relative)
        if child.is_dir():
            created.extend(_copy_skill(child, root, child_relative))
        elif not target.exists():
            with target.open("xb") as stream:
                stream.write(child.read_bytes())
            created.append(child_relative)
    return created


def _installed_framework() -> Path | None:
    marker = Path(sys.prefix) / "source.json"
    if marker.is_file():
        value = _read_json(marker).get("framework_root")
        if isinstance(value, str) and Path(value).is_absolute():
            return Path(value)
    return None


def provider_records(root: Path) -> dict[str, Any]:
    path = _safe_path(root, PROVIDERS)
    return _read_json(path) if path.is_file() else {}


def _recent(timestamp: Any) -> bool:
    if not isinstance(timestamp, str):
        return False
    try:
        checked = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return 0 <= (datetime.now(UTC) - checked).total_seconds() <= 86400
    except (TypeError, ValueError):
        return False


def save_provider_records(root: Path, records: list[dict[str, Any]]) -> None:
    existing = provider_records(root)
    for record in records:
        provider = record["provider"]
        record = dict(record)
        if provider == "agy":
            previous = existing.get(provider, {})
            saved = previous.get("model_verifications", {}) if isinstance(previous, dict) else {}
            verifications = dict(saved) if isinstance(saved, dict) else {}
            model = record.get("selected_model")
            if record.get("verification_method") == "inference" and isinstance(model, str):
                # A failed explicit check invalidates that model. Catalog refreshes do not
                # renew or discard earlier checks, including checks for other model tiers.
                verifications.pop(model, None)
                if record.get("verified") is True and record.get("authenticated") is True:
                    verifications[model] = record.get("verified_at")
            record["model_verifications"] = verifications
        existing[provider] = record
    _write_json(_safe_path(root, PROVIDERS), existing)


def _check_models(root: Path, config: ProjectConfig) -> None:
    reports = provider_records(root)
    for provider in config.providers:
        report = reports.get(provider, {})
        if not isinstance(report, dict):
            raise ValueError(f"Refresh provider checks for {provider}")
        if provider == "agy":
            proofs = report.get("model_verifications", {})
            authenticated = isinstance(proofs, dict) and any(_recent(t) for t in proofs.values())
        else:
            authenticated = report.get("authenticated") is True
        if not authenticated:
            raise ValueError(f"Verify authentication for {provider} with devctl providers")
        if not _recent(report.get("checked_at")):
            raise ValueError(f"Refresh provider checks for {provider}")
    for choice in config.models.values():
        report = reports[choice.provider]
        models = report.get("models", [])
        if not isinstance(models, list) or not any(
            item.get("id") == choice.model for item in models if isinstance(item, dict)
        ):
            raise ValueError(f"Choose {choice.provider} model from the discovered catalog")
        if choice.provider == "agy":
            proofs = report.get("model_verifications", {})
            if not isinstance(proofs, dict) or not _recent(proofs.get(choice.model)):
                raise ValueError(f"Verify authentication for agy model {choice.model} explicitly")


def _interview(root: Path) -> dict[str, Any]:
    state = _read_json(_safe_path(root, INTERVIEW))
    if state.get("schema_version") not in (1, 2) or not isinstance(state.get("answers"), dict):
        raise ValueError("Invalid interview state")
    known = {key for key, _ in [*_QUESTIONS, *_LEGACY_QUESTIONS]}
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
    interview = _interview(root)
    answers = interview["answers"]
    execution = config.environments[0].execution
    for key, prompt in _QUESTIONS if interview["schema_version"] == 2 else _LEGACY_QUESTIONS:
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
            question: dict[str, Any] = {"complete": False, "id": key, "question": prompt}
            if key == "models":
                records = provider_records(root)
                question["choices"] = {name: records.get(name, {}) for name in config.providers}
                try:
                    _check_models(root, config)
                except ValueError as error:
                    question["blocked"] = str(error)
            if key == "guidance":
                question["default"] = config.guidance.model_dump()
            return question
    return {"complete": True}


def _answer_config(config: ProjectConfig, question_id: str, value: Any) -> ProjectConfig:
    if question_id not in {key for key, _ in [*_QUESTIONS, *_LEGACY_QUESTIONS]}:
        raise ValueError(f"Unknown question: {question_id}")
    data = config.model_dump(mode="json")
    if config.models and question_id in {
        "worker_runner",
        "worker_model",
        "reviewer_runner",
        "reviewer_model",
    }:
        raise ValueError("Update the selected model tiers through the models question")
    if question_id == "repository":
        if not isinstance(value, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
            raise ValueError("Repository must have the form owner/repository")
        data["repository"] = value
    elif question_id == "providers":
        if not isinstance(value, list) or not value:
            raise ValueError("Select at least one provider")
        data["providers"] = value
        if any(choice.provider not in value for choice in config.models.values()):
            data["models"] = {}
    elif question_id == "models":
        if not isinstance(value, dict) or not value:
            raise ValueError("Choose both small and large models")
        data["models"] = value
    elif question_id == "guidance":
        data["guidance"] = value
    elif question_id in {"worker_runner", "reviewer_runner"}:
        if not isinstance(value, str) or value not in {"codex", "claude", "agy"}:
            raise ValueError("Runner must be codex, claude, or agy")
        if question_id == "reviewer_runner" and value == "agy":
            raise ValueError("agy reviewer read-only execution has not been verified")
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
            "memory_budget_mb",
            "cpu_budget",
            "max_parallel",
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
    if question_id == "models":
        _check_models(root, updated)
    if question_id == "providers" and updated.models != config.models:
        state["answers"].pop("models", None)
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
        if config.models:
            _check_models(root, config)
        if not complete:
            blockers.append("Complete the project interview")
        if config.reviewer_runner == "agy":
            blockers.append("agy reviewer read-only execution has not been verified")
        if config.worker_runner == "agy" and config.worker_model is None:
            blockers.append("agy requires an explicit model identifier from agy models")
        for environment in config.environments:
            if config.worker_runner == "agy" and environment.execution != "docker":
                blockers.append(f"{environment.name}: agy workers require Docker isolation")
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
    config = load_config(root)
    if config.profile != "python-cli":
        raise ValueError(f"No feature scaffold is available for profile {config.profile!r}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise ValueError("Feature name must be a lowercase Python identifier")
    relative_module = f"src/features/{name}.py"
    relative_test = f"tests/test_{name}.py"
    paths = [_safe_path(root, item) for item in [relative_module, relative_test]]
    if any(path.exists() for path in paths):
        raise ValueError("Refusing to overwrite an existing feature")
    contents = [
        f'"""{name} feature: replace this behaviour with the approved task requirements."""\n\n'
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
