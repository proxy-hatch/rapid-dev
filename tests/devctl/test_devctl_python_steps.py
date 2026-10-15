"""Python tool steps, run against a simulated uv."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from check_workspace import Workspace, fake_tool
from devctl.check import core_steps
from devctl.check.stacks.python import CONTRACTS, FORMAT, LINT, TESTS, TYPES
from devctl.check.steps import CommandStep


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def calls(tools: Path, name: str = "uv") -> list[dict[str, object]]:
    log = tools / f"{name}.log"
    return [json.loads(line) for line in log.read_text().splitlines()]


@pytest.mark.parametrize(
    ("step", "argv"),
    [
        (FORMAT, ["run", "--locked", "ruff", "format", "--check", "."]),
        (LINT, ["run", "--locked", "ruff", "check", "--output-format", "concise", "."]),
        (TYPES, ["run", "--locked", "mypy"]),
        (CONTRACTS, ["run", "--locked", "lint-imports"]),
        (TESTS, ["run", "--locked", "pytest"]),
    ],
)
def test_each_tool_runs_through_uv(
    workspace: Workspace, tools: Path, step: CommandStep, argv: list[str]
) -> None:
    fake_tool(tools, "uv", "sys.exit(0)")

    assert step.run(workspace.context()).status == "passed"
    assert calls(tools)[0]["argv"] == argv
    assert calls(tools)[0]["cwd"] == str(workspace.root)


@pytest.mark.parametrize(
    ("step", "code", "status"),
    [
        (LINT, 1, "failed"),
        (LINT, 2, "blocked"),
        (TESTS, 1, "failed"),
        (TESTS, 5, "failed"),
        (TESTS, 3, "blocked"),
    ],
)
def test_exit_codes_map_to_statuses(
    workspace: Workspace, tools: Path, step: CommandStep, code: int, status: str
) -> None:
    fake_tool(tools, "uv", f"print('tool output'); sys.exit({code})")

    result = step.run(workspace.context())

    assert result.status == status
    assert "tool output" in result.details


def test_missing_tool_is_blocked(
    workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert LINT.run(context).details == ("uv is not on PATH",)


def test_timeout_is_blocked(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "uv", "import time; time.sleep(30)")
    step = CommandStep("slow", "full", ("uv",), timeout_seconds=0.5)

    result = step.run(workspace.context())

    assert result.status == "blocked"
    assert result.details[0].startswith("timed out after")


def test_tools_get_a_scrubbed_environment(
    workspace: Workspace, tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_TOKEN", "must-not-pass")
    monkeypatch.setenv("UV_CACHE_DIR", str(tools / "cache"))
    fake_tool(tools, "uv", "sys.exit(0)")

    TYPES.run(workspace.context())

    environment = calls(tools)[0]["env"]
    assert isinstance(environment, list)
    assert "GH_TOKEN" not in environment
    assert "UV_CACHE_DIR" in environment


def test_python_projects_run_the_tools_around_the_core_checks(workspace: Workspace) -> None:
    steps = core_steps(workspace.context(stack="python").project)

    assert [(step.name, step.tier) for step in steps] == [
        ("format", "fast"),
        ("lint", "fast"),
        ("map", "fast"),
        ("exceptions", "fast"),
        ("file-size", "fast"),
        ("kit", "fast"),
        ("types", "full"),
        ("contracts", "full"),
        ("tests", "full"),
        ("audit", "full"),
        ("secrets", "full"),
        ("workflows", "full"),
        ("diff", "full"),
        ("evidence", "full"),
    ]
