"""Validated data contracts shared by controllers, providers and evidence gates."""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)


def _nonempty(value: str) -> str:
    if not value.strip() or "\x00" in value:
        raise ValueError("must be nonempty and contain no NUL")
    return value


def _token(value: str) -> str:
    _nonempty(value)
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ValueError("token must contain no whitespace or control characters")
    return value


def _component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError("must be a safe path component")
    return value


def _relative_path(value: str) -> str:
    _nonempty(value)
    if value.startswith("/") or "\\" in value or ":" in value:
        raise ValueError("must be a safe relative path")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("path must contain no control characters")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("path must contain no empty, dot or dotdot components")
    return value


def _argument(value: str) -> str:
    if "\x00" in value:
        raise ValueError("command argument must contain no NUL")
    return value


def _command(value: list[str]) -> list[str]:
    if not value or not value[0].strip():
        raise ValueError("command must have a nonempty executable")
    return value


Text = Annotated[str, AfterValidator(_nonempty)]
Token = Annotated[str, AfterValidator(_token)]
Component = Annotated[str, AfterValidator(_component)]
RelativePath = Annotated[str, AfterValidator(_relative_path)]
Argument = Annotated[str, AfterValidator(_argument)]
Command = Annotated[list[Argument], Field(min_length=1), AfterValidator(_command)]
PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class Contract(BaseModel):
    """Do not coerce input, accept unknown authority, or permit field replacement."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class Resources(Contract):
    memory_mb: PositiveInt = 2048
    cpu: PositiveFloat = 1.0


class EnvironmentSpec(Contract):
    name: Component
    workspace: Literal["clone", "worktree"]
    execution: Literal["native", "docker", "sbx", "openhands"]
    image: Text | None = None
    resources: Resources = Field(default_factory=Resources)
    private_network: bool = True
    exclusive_resources: list[Token] = Field(default_factory=list)
    test_resources: list[Token] = Field(default_factory=list)
    allow_native: bool = False
    verified: bool = False


class ProjectConfig(Contract):
    schema_version: Literal[1] = 1
    name: Text
    design_path: RelativePath
    profile: Component = "custom"
    repository: Text | None = None
    default_branch: Token = "main"
    max_parallel: PositiveInt = 1
    memory_budget_mb: PositiveInt = 4096
    cpu_budget: PositiveFloat = 4.0
    max_repair_rounds: Annotated[int, Field(ge=0)] = 2
    environments: list[EnvironmentSpec] = Field(default_factory=list)
    checks: dict[Token, Command] = Field(default_factory=dict)
    worker_runner: Token = "codex"
    reviewer_runner: Token = "claude"
    worker_model: Token | None = None
    reviewer_model: Token | None = None
    release_target: Literal["github-release", "none"] = "github-release"

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_schema_version(cls, value: object) -> object:
        # Literal equality alone allows True and 1.0 to impersonate integer 1.
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def unique_environments(self) -> ProjectConfig:
        names = [environment.name for environment in self.environments]
        if len(set(names)) != len(names):
            raise ValueError("duplicate environment names")
        return self


class TaskSpec(Contract):
    id: Component
    title: Text
    description: Text
    depends_on: list[Component] = Field(default_factory=list)
    owned_paths: Annotated[list[RelativePath], Field(min_length=1)]
    acceptance: Annotated[list[Text], Field(min_length=1)]
    environment: Component
    base_sha: Token
    timeout_seconds: PositiveInt = 1800
    runner: Token | None = None
    model: Token | None = None
    checks: list[Token] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        # New optional overrides must not change saved task identities or evidence hashes.
        data: dict[str, object] = handler(self)
        if self.model is None:
            data.pop("model", None)
        return data

    @model_validator(mode="after")
    def unique_dependencies(self) -> TaskSpec:
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("duplicate dependencies")
        return self


class EvidenceBinding(Contract):
    task_id: Component
    attempt_id: Component
    head_sha: Token
    base_sha: Token
    policy_digest: Token
    recipe_digest: Token
    environment_digest: Token
    controller_version: Token


class CheckResult(Contract):
    name: Token
    argv: Command
    exit_code: int
    duration_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    stdout: str
    stderr: str


class ReviewFinding(Contract):
    severity: Literal["critical", "important", "minor"]
    message: Text
    category: Token | None = None
    path: RelativePath | None = None
    line: PositiveInt | None = None

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        # Keep older evidence hashes stable when no category was recorded.
        data: dict[str, object] = handler(self)
        if self.category is None:
            data.pop("category", None)
        return data


class ReviewDecision(Contract):
    binding: EvidenceBinding
    verdict: Literal["approve", "changes_requested", "blocked"]
    findings: list[ReviewFinding] = Field(default_factory=list)
    reviewer_runner: Token
    independent: bool
    summary: Text


class TaskEvidence(Contract):
    binding: EvidenceBinding
    checks: list[CheckResult] = Field(default_factory=list)
    review: ReviewDecision | None = None
    live: bool = False
    artifact_paths: list[RelativePath] = Field(default_factory=list)

    @model_validator(mode="after")
    def matching_review_binding(self) -> TaskEvidence:
        if self.review is not None and self.review.binding != self.binding:
            raise ValueError("review binding must match evidence binding")
        return self


def digest(value: BaseModel | dict[str, object]) -> str:
    """Hash compact, sorted JSON; preserve list order and reject non-JSON numbers."""
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_task_graph(tasks: list[TaskSpec]) -> None:
    """Reject duplicate IDs, missing dependencies and cycles before scheduling."""
    by_id = {task.id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("duplicate task IDs")
    followers: dict[str, list[str]] = {task.id: [] for task in tasks}
    indegree = {task.id: len(task.depends_on) for task in tasks}
    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in by_id:
                raise ValueError(f"missing dependency {dependency!r} for task {task.id!r}")
            followers[dependency].append(task.id)
    ready = deque(identifier for identifier, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        identifier = ready.popleft()
        visited += 1
        for follower in followers[identifier]:
            indegree[follower] -= 1
            if indegree[follower] == 0:
                ready.append(follower)
    if visited != len(tasks):
        raise ValueError("task dependency cycle")


def _ownership_prefix(path: str) -> tuple[str, ...]:
    """A glob owns its entire stable directory prefix, including descendants."""
    _relative_path(path)
    parts: list[str] = []
    for part in path.split("/"):
        if any(character in part for character in "*?["):
            break
        parts.append(part)
    return tuple(parts)


def paths_overlap(left: list[str], right: list[str]) -> bool:
    """Compare safe path ownership conservatively; never fold filesystem case."""
    left_prefixes = [_ownership_prefix(path) for path in left]
    right_prefixes = [_ownership_prefix(path) for path in right]
    for a in left_prefixes:
        for b in right_prefixes:
            shared = min(len(a), len(b))
            if a[:shared] == b[:shared]:
                return True
    return False
