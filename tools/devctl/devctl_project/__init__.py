"""Project verbs and extra check steps for this repository's devctl.

rapid-ship writes this package once; the project owns it afterwards. rapid-ship's own steps
check that the vendored Kit equals its templates, that the wheel ships and runs, and that the
tests pass on the oldest Python that pyproject.toml supports.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from devctl.check.steps import (
    CheckContext,
    CommandStep,
    Step,
    StepResult,
    Tier,
    command_result,
    passed,
    run_tool,
)
from devctl.repo import Repo

VENDORED = CommandStep(
    "vendored", "fast", ("uv", "run", "--locked", "rapid-ship", "status", "--strict")
)


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add project verbs. Each verb sets a handler that returns the exit code:

    verb = commands.add_parser("seed-demo", help="Load demo data")
    verb.set_defaults(handler=seed_demo)
    """


def check_steps() -> list[Step]:
    """Return extra steps for ./devctl check."""
    return [VENDORED, DistributionStep(), FloorPythonStep()]


def copy_work_tree(repo: Repo, target: Path) -> None:
    """Copy the files Git keeps, uncommitted edits included, into target, without .git.

    Symlinks stay links. Ignored local state stays out, so builds from the copy never pack it.
    """
    for path in repo.files():
        source = repo.root / path
        if not source.exists() and not source.is_symlink():
            continue  # An unstaged deletion is part of the work tree.
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)


class DistributionStep:
    """Build the wheel and sdist in a copy of the work tree, then run the distribution smoke.

    scripts/smoke_distribution.py checks that the wheel ships every template, installs it in
    isolation and runs rapid-ship in scratch projects. It uses only the standard library, so it
    runs with devctl's Python. The copy keeps dist/ out of the checkout.
    """

    name = "distribution"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult:
        with tempfile.TemporaryDirectory(prefix="devctl-distribution-") as scratch:
            copy = Path(scratch).resolve()
            copy_work_tree(context.repo, copy)
            commands: tuple[tuple[tuple[str, ...], float], ...] = (
                (("uv", "build"), 600),
                ((sys.executable, "scripts/smoke_distribution.py"), 1800),
            )
            for argv, timeout_seconds in commands:
                result = run_tool(copy, argv, timeout_seconds)
                outcome = command_result(self.name, argv, result, frozenset({1}))
                if outcome.status != "passed":
                    return outcome
        return passed(self.name)


class FloorPythonStep:
    """Run the tests on Python 3.12, the oldest version pyproject.toml supports.

    The environment lives in a temporary directory, so the work tree's .venv keeps its Python.
    """

    name = "python-3.12"
    tier: Tier = "full"
    argv = ("uv", "run", "--locked", "--python", "3.12", "pytest", "-q")

    def run(self, context: CheckContext) -> StepResult:
        with tempfile.TemporaryDirectory(prefix="devctl-python-3.12-") as scratch:
            environment = {"UV_PROJECT_ENVIRONMENT": str(Path(scratch, "venv"))}
            result = run_tool(context.repo.root, self.argv, 1800, environment)
        # pytest exits 5 when it collects no tests.
        return command_result(self.name, self.argv, result, frozenset({1, 5}))
