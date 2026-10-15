"""devctl's typed view of .rapid-ship settings.

Unknown keys are errors, so a typo cannot silently keep a default. Every loader reads
one file and raises SettingsError, which devctl reports with exit 2.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast, get_args

PROJECT = ".rapid-ship/project.toml"
GATE = ".rapid-ship/gate.toml"
EXCEPTIONS = ".rapid-ship/exceptions.toml"

Harness = Literal["claude", "codex", "agy"]
Stack = Literal["python", "agnostic"]
Mode = Literal["walk", "flight"]
ReleaseMethod = Literal["github-deployments", "tags", "none"]

_REPOSITORY = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/(?!\.{1,2}$)[A-Za-z0-9._-]+")
_EXCEPTION_ID = re.compile(r"EX-[1-9][0-9]*")
_EXCEPTION_KEYS = ("id", "path", "rule", "reason", "remove_when")


class SettingsError(Exception):
    """A settings file is missing or invalid. devctl exits 2."""


@dataclass(frozen=True)
class Agent:
    harness: Harness
    model: str  # kept exactly


@dataclass(frozen=True)
class ProjectSettings:
    stack: Stack
    worker: Agent | None
    reviewer: Agent | None
    repository: str | None  # "owner/name"
    worker_app_id: int | None  # 0 in the file means unset
    reviewer_app_id: int | None
    linear_team_id: str | None
    linear_project_id: str | None
    optional_skills: tuple[str, ...]  # [kit] optional
    # [kit] exclude: Kit paths the project owns; a skill directory also covers its link.
    excluded: tuple[str, ...]
    max_workers: int  # default 5
    attempt_limit: int  # default 3
    worktree_root: str  # default "../<repo>.worktrees"
    source_roots: tuple[str, ...]  # [map] source_roots
    unguided: tuple[str, ...]  # [map] unguided
    # [map] exclude: directories whose AGENTS.md files are template content, not guides.
    map_exclude: tuple[str, ...]
    unit_tests: tuple[str, ...]  # [tests] unit; default ("tests/unit/**",)
    release_method: ReleaseMethod


@dataclass(frozen=True)
class GateSettings:
    mode: Mode
    flight_lease_until: str | None
    owner_approves_behavioural_test_removal: bool  # default True


@dataclass(frozen=True)
class ExceptionEntry:
    id: str  # "EX-<n>", n >= 1, unique
    path: str
    rule: str
    reason: str
    remove_when: str


class _Table:
    """One TOML table with known keys. Each accessor checks the value's type."""

    def __init__(self, value: object, where: str, keys: set[str]) -> None:
        if not isinstance(value, dict):
            raise SettingsError(f"{where}: expected a table")
        unknown = sorted(set(value) - keys)
        if unknown:
            raise SettingsError(f"{where}: unknown key {unknown[0]!r}")
        self.values: dict[str, object] = value
        self.where = where

    def table(self, key: str, keys: set[str]) -> _Table:
        return _Table(self.values.get(key, {}), f"{self.where} [{key}]", keys)

    def _error(self, key: str, expected: str) -> SettingsError:
        return SettingsError(f"{self.where} {key}: expected {expected}")

    def text(self, key: str, default: str = "") -> str:
        value = self.values.get(key, default)
        if not isinstance(value, str):
            raise self._error(key, "a string")
        return value

    def choice(self, key: str, options: tuple[str, ...], default: str | None = None) -> str:
        if key not in self.values and default is None:
            raise SettingsError(f"{self.where} {key}: required")
        value = self.values.get(key, default)
        if value not in options:
            raise self._error(key, " or ".join(options))
        return value

    def integer(self, key: str, default: int, minimum: int) -> int:
        value = self.values.get(key, default)
        # TOML true is a Python bool, which is also an int.
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise self._error(key, f"an integer of at least {minimum}")
        return value

    def boolean(self, key: str, default: bool) -> bool:
        value = self.values.get(key, default)
        if not isinstance(value, bool):
            raise self._error(key, "true or false")
        return value

    def texts(self, key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
        value = self.values.get(key, list(default))
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise self._error(key, "a list of non-empty strings")
        return tuple(value)


def _read(root: Path, relative: str) -> dict[str, object]:
    try:
        return tomllib.loads((root / relative).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SettingsError(f"{relative}: missing; rapid-ship init seeds it") from None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise SettingsError(f"{relative}: {error}") from error


def _inside_repository(entry: str) -> str | None:
    """The repository-relative POSIX path without "./" or a trailing "/", or None if it leaves."""
    path = PurePosixPath(entry)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in entry:
        return None
    return "/".join(path.parts)


def _agent(agents: _Table, role: str) -> Agent | None:
    if role not in agents.values:
        return None
    table = agents.table(role, {"harness", "model"})
    harness = cast(Harness, table.choice("harness", get_args(Harness)))
    model = table.text("model")
    if not model or model.strip() != model:
        raise SettingsError(f"{table.where} model: required; record the exact model ID")
    return Agent(harness, model)


def _exclude_paths(table: _Table) -> tuple[str, ...]:
    """A table's `exclude` list, normalised as rapid-ship's read_excluded does."""
    paths = [_inside_repository(entry) for entry in table.texts("exclude")]
    if None in paths:
        raise table._error("exclude", "paths inside the repository")
    return tuple(path for path in paths if path is not None)


def load_project(root: Path) -> ProjectSettings:
    top = _Table(
        _read(root, PROJECT),
        PROJECT,
        {"stack", "agents", "github", "kit", "linear", "dispatch", "map", "tests", "release"},
    )
    stack = cast(Stack, top.choice("stack", get_args(Stack)))
    agents = top.table("agents", {"worker", "reviewer"})
    github = top.table("github", {"repository", "worker_app_id", "reviewer_app_id"})
    kit = top.table("kit", {"optional", "exclude"})
    linear = top.table("linear", {"team_id", "project_id"})
    dispatch = top.table("dispatch", {"max_workers", "attempt_limit", "worktree_root"})
    source_map = top.table("map", {"source_roots", "unguided", "exclude"})
    tests = top.table("tests", {"unit"})
    release = top.table("release", {"method"})

    repository = github.text("repository") or None
    if repository is not None and not _REPOSITORY.fullmatch(repository):
        raise github._error("repository", "owner/name")
    return ProjectSettings(
        stack=stack,
        worker=_agent(agents, "worker"),
        reviewer=_agent(agents, "reviewer"),
        repository=repository,
        worker_app_id=github.integer("worker_app_id", 0, minimum=0) or None,
        reviewer_app_id=github.integer("reviewer_app_id", 0, minimum=0) or None,
        linear_team_id=linear.text("team_id") or None,
        linear_project_id=linear.text("project_id") or None,
        optional_skills=kit.texts("optional"),
        excluded=_exclude_paths(kit),
        max_workers=dispatch.integer("max_workers", 5, minimum=1),
        attempt_limit=dispatch.integer("attempt_limit", 3, minimum=1),
        worktree_root=dispatch.text("worktree_root") or f"../{root.resolve().name}.worktrees",
        source_roots=source_map.texts("source_roots"),
        unguided=source_map.texts("unguided"),
        map_exclude=_exclude_paths(source_map),
        unit_tests=tests.texts("unit", ("tests/unit/**",)),
        release_method=cast(
            ReleaseMethod, release.choice("method", get_args(ReleaseMethod), default="none")
        ),
    )


def load_gate(root: Path) -> GateSettings:
    gate = _Table(
        _read(root, GATE),
        GATE,
        {"mode", "flight_lease_until", "owner_approves_behavioural_test_removal", "thresholds"},
    )
    # Spec 3 reads the threshold values; here only the two table names are checked.
    gate.table("thresholds", {"promotion", "demotion"})
    return GateSettings(
        mode=cast(Mode, gate.choice("mode", get_args(Mode), default="walk")),
        flight_lease_until=gate.text("flight_lease_until") or None,
        owner_approves_behavioural_test_removal=gate.boolean(
            "owner_approves_behavioural_test_removal", True
        ),
    )


def load_exceptions(root: Path) -> list[ExceptionEntry]:
    top = _Table(_read(root, EXCEPTIONS), EXCEPTIONS, {"exception"})
    items = top.values.get("exception", [])
    if not isinstance(items, list):
        raise top._error("exception", "a list of tables")
    entries: list[ExceptionEntry] = []
    for number, item in enumerate(items, start=1):
        row = _Table(item, f"{EXCEPTIONS} [[exception]] #{number}", set(_EXCEPTION_KEYS))
        fields = {key: row.text(key) for key in _EXCEPTION_KEYS}
        for key, value in fields.items():
            if not value.strip():
                raise SettingsError(f"{row.where} {key}: required")
        if not _EXCEPTION_ID.fullmatch(fields["id"]):
            raise row._error("id", "EX-<n>")
        if any(entry.id == fields["id"] for entry in entries):
            raise SettingsError(f"{row.where}: {fields['id']} is listed twice")
        if _inside_repository(fields["path"]) is None:
            raise row._error("path", "a path inside the repository")
        entries.append(ExceptionEntry(**fields))
    return entries
