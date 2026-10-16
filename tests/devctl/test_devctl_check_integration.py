"""Integration test: needs network access (PyPI and pip-audit's lookups) and gitleaks on PATH.

rapid-ship init writes a new project. devctl check's fast tier passes before the first
commit, as rs-setup runs it, and the full tier passes after it. A project's own verb and
check step, written against the seeded devctl_project interface, run through ./devctl.
No GitHub access.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from check_workspace import Workspace, new_workspace
from devctl.check.steps import tool_environment
from devctl.process import run_process

# The agnostic seed has no source roots; a local run has no base commit and no PR body.
NOT_APPLICABLE: dict[tuple[str, str], set[str]] = {
    ("python", "fast"): set(),
    ("agnostic", "fast"): {"file-size"},
    ("python", "full"): {"diff", "evidence"},
    ("agnostic", "full"): {"file-size", "diff", "evidence"},
}


def assert_check_passes(project: Workspace, stack: str, tier: str) -> None:
    result = run_process(
        ["./devctl", "check", "--tier", tier, "--json"], project.root, 1200, env=tool_environment()
    )
    assert result.returncode == 0, result.stdout + result.stderr
    statuses = {step["name"]: step["status"] for step in json.loads(result.stdout)}
    assert set(statuses.values()) <= {"passed", "not_applicable"}
    skipped = {name for name, status in statuses.items() if status == "not_applicable"}
    assert skipped == NOT_APPLICABLE[(stack, tier)]


def init_project(path: Path, stack: str) -> Workspace:
    project = new_workspace(path)
    # init commits the Kit, and a CI runner has no git identity of its own.
    for key, value in (("user.name", "devctl tests"), ("user.email", "devctl@example.invalid")):
        project.git("config", key, value)
    init = run_process(
        [sys.executable, "-m", "rapid_ship", "init", "--stack", stack, "--owner", "test-owner"],
        project.root,
        120,
    )
    assert init.returncode == 0, init.stdout + init.stderr
    return project


@pytest.mark.parametrize("stack", ["python", "agnostic"])
def test_new_project_passes_devctl_check(tmp_path: Path, stack: str) -> None:
    project = init_project(tmp_path / "project", stack)
    if stack == "python":
        # pytest imports the package, so it writes __pycache__ under the source root.
        for command in (["uv", "sync", "--quiet"], ["uv", "run", "--locked", "pytest", "-q"]):
            ran = run_process(command, project.root, 600, env=tool_environment())
            assert ran.returncode == 0, ran.stdout + ran.stderr

    assert_check_passes(project, stack, "fast")
    project.commit("rapid-ship init")
    assert "__pycache__" not in project.git("ls-files")
    assert_check_passes(project, stack, "full")


# A project's replacement for the seeded tools/devctl/devctl_project/__init__.py.
PROJECT_EXTENSION = r'''"""This project's devctl verbs and check steps."""

from __future__ import annotations

import argparse
import sys

from devctl.check.steps import CheckContext, Step, StepResult, Tier, passed


def greet(args: argparse.Namespace) -> int:
    sys.stdout.write(f"hello {args.name}\n")
    return 0


class ReleaseNotesStep:
    name = "release-notes"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult:
        return passed(self.name, "release notes are current")


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    verb = commands.add_parser("greet", help="Print a greeting")
    verb.add_argument("name")
    verb.set_defaults(handler=greet)


def check_steps() -> list[Step]:
    return [ReleaseNotesStep()]
'''


def run_devctl(project: Workspace, *args: str) -> tuple[int, str, str]:
    result = run_process(["./devctl", *args], project.root, 1200, env=tool_environment())
    return result.returncode, result.stdout, result.stderr


def test_a_project_verb_and_check_step_extend_devctl(tmp_path: Path) -> None:
    project = init_project(tmp_path / "project", "agnostic")
    project.write("tools/devctl/devctl_project/__init__.py", PROJECT_EXTENSION)
    project.commit("rapid-ship init, then a project verb and check step")

    greeted = run_devctl(project, "greet", "world")
    fast = run_devctl(project, "check", "--tier", "fast", "--json")
    full = run_devctl(project, "check", "--tier", "full", "--json")

    assert greeted[:2] == (0, "hello world\n"), greeted
    # The step runs in its own tier only, after the core steps.
    assert "release-notes" not in {step["name"] for step in json.loads(fast[1])}
    assert full[0] == 0, full
    assert json.loads(full[1])[-1] == {
        "name": "release-notes",
        "status": "passed",
        "details": ["release notes are current"],
    }
