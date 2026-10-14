"""Check step types and helpers shared by every step."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol

from devctl.repo import Repo
from devctl.settings import GateSettings, ProjectSettings

Tier = Literal["fast", "full"]
Status = Literal["passed", "failed", "blocked", "not_applicable"]

# Variables a check tool may need besides PATH and HOME. Never add one that can hold a token.
PASSED_VARIABLES = (
    "TMPDIR",
    "CI",
    "SSL_CERT_FILE",
    "UV_CACHE_DIR",
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_TOOL_DIR",
    "UV_TOOL_BIN_DIR",
)


@dataclass(frozen=True)
class StepResult:
    name: str
    status: Status
    details: tuple[str, ...]


@dataclass(frozen=True)
class CheckContext:
    repo: Repo
    project: ProjectSettings
    gate: GateSettings
    base: str | None
    pr_body: str | None


class Step(Protocol):
    # A frozen dataclass cannot implement these settable members; use a class or plain dataclass.
    name: str
    tier: Tier

    def run(self, context: CheckContext) -> StepResult: ...


def passed(name: str, *details: str) -> StepResult:
    return StepResult(name, "passed", details)


def failed(name: str, *details: str) -> StepResult:
    return StepResult(name, "failed", details)


def blocked(name: str, *details: str) -> StepResult:
    return StepResult(name, "blocked", details)


def not_applicable(name: str, *details: str) -> StepResult:
    return StepResult(name, "not_applicable", details)


def tool_environment() -> dict[str, str]:
    """The variables a check tool gets besides PATH, HOME and the locale."""
    return {name: os.environ[name] for name in PASSED_VARIABLES if name in os.environ}
