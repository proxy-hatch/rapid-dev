"""A scratch git repository and check context for devctl tests."""

from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from devctl.check.steps import CheckContext, Status, StepResult, Tier
from devctl.process import ProcessResult, run_process
from devctl.repo import Repo
from devctl.settings import GateSettings, ProjectSettings

GIT_IDENTITY = (
    "-c",
    "user.name=devctl tests",
    "-c",
    "user.email=devctl@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)


def project_settings(**changes: object) -> ProjectSettings:
    base = ProjectSettings(
        stack="python",
        worker=None,
        reviewer=None,
        repository=None,
        worker_app_id=None,
        reviewer_app_id=None,
        linear_team_id=None,
        linear_project_id=None,
        optional_skills=(),
        excluded=(),
        max_workers=5,
        attempt_limit=3,
        worktree_root="../app.worktrees",
        source_roots=("src/app",),
        unguided=(),
        map_exclude=(),
        unit_tests=("tests/unit/**",),
        release_method="none",
    )
    return dataclasses.replace(base, **cast("dict[str, Any]", changes))


def gate_settings(**changes: object) -> GateSettings:
    base = GateSettings(
        mode="walk", flight_lease_until=None, owner_approves_behavioural_test_removal=True
    )
    return dataclasses.replace(base, **cast("dict[str, Any]", changes))


def skill_text(name: str) -> str:
    """A SKILL.md that satisfies map rule 7 for the skill directory `name`."""
    return f"---\nname: {name}\ndescription: Use when testing devctl.\n---\n# {name}\n"


@dataclass(frozen=True)
class Workspace:
    root: Path

    def try_git(self, *args: str) -> ProcessResult:
        return run_process(["git", *GIT_IDENTITY, *args], self.root, 60)

    def git(self, *args: str) -> str:
        result = self.try_git(*args)
        if result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    def write(self, path: str, text: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def write_with_bom(self, path: str, text: str) -> Path:
        """Write text as UTF-8 with the byte-order mark that some Windows editors put first."""
        target = self.write(path, text)
        target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())
        return target

    def link(self, path: str, target: str) -> None:
        alias = self.root / path
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(target, target_is_directory=True)

    def commit(self, message: str = "change") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def context(
        self,
        *,
        base: str | None = None,
        pr_body: str | None = None,
        gate: GateSettings | None = None,
        **project: object,
    ) -> CheckContext:
        return CheckContext(
            Repo.discover(self.root),
            project_settings(**project),
            gate or gate_settings(),
            base,
            pr_body,
        )


def new_workspace(path: Path) -> Workspace:
    path.mkdir(parents=True)
    result = run_process(["git", "init", "-q", "-b", "main", str(path)], path, 60)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return Workspace(path.resolve())


def fake_tool(directory: Path, name: str, body: str) -> Path:
    """Write a stand-in executable that logs its arguments, then runs body."""
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "here = pathlib.Path(__file__)\n"
        "with open(here.with_name(here.name + '.log'), 'a') as log:\n"
        "    log.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(),"
        " 'env': sorted(os.environ)}) + '\\n')\n"
        f"{body}\n"
    )
    tool.chmod(0o700)
    return tool


class FakeStep:
    def __init__(
        self, name: str, tier: Tier, status: Status = "passed", details: tuple[str, ...] = ()
    ) -> None:
        self.name = name
        self.tier = tier
        self.status = status
        self.details = details

    def run(self, context: CheckContext) -> StepResult:
        return StepResult(self.name, self.status, self.details)


class BrokenStep(FakeStep):
    def run(self, context: CheckContext) -> StepResult:
        raise RuntimeError("step bug")
