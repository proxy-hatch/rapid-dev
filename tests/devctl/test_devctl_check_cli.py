"""devctl check output, JSON and exit codes, with stand-in steps."""

from __future__ import annotations

import json

import pytest

import devctl_project
from check_workspace import FakeStep, Workspace, gate_settings, project_settings
from devctl import check, cli
from devctl.check.steps import CheckContext, StepResult
from devctl.settings import SettingsError


def work_in(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run from the workspace with no CI variables.

    This repository's pull_request CI sets them, and check would then read the real event and
    fail to find its PR base in the scratch repository.
    """
    monkeypatch.chdir(workspace.root)
    for name in ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(name, raising=False)


def run_captured(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> tuple[int, str, str]:
    work_in(workspace, monkeypatch)
    monkeypatch.setattr(cli, "load_project", lambda root: project_settings())
    monkeypatch.setattr(cli, "load_gate", lambda root: gate_settings())
    code = cli.main(["check", *args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> tuple[int, str]:
    code, out, _ = run_captured(workspace, monkeypatch, capsys, *args)
    return code, out


STEPS = (
    FakeStep("format", "fast"),
    FakeStep("lint", "fast", "failed", ("x.py:1:1: F401 unused import",)),
    FakeStep("evidence", "full", "not_applicable", ("not a pull request",)),
)


def test_one_line_per_step_with_details(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(check, "all_steps", lambda project: list(STEPS))

    code, out = run(workspace, monkeypatch, capsys)

    assert code == 1
    assert out == (
        "passed         format\n"
        "failed         lint\n"
        "    x.py:1:1: F401 unused import\n"
        "not applicable evidence\n"
        "    not a pull request\n"
    )


def test_json_prints_the_same_results(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(check, "all_steps", lambda project: list(STEPS))

    code, out = run(workspace, monkeypatch, capsys, "--tier", "fast", "--json")

    assert code == 1
    assert json.loads(out) == [
        {"name": "format", "status": "passed", "details": []},
        {"name": "lint", "status": "failed", "details": ["x.py:1:1: F401 unused import"]},
    ]


def test_blocked_step_exits_two(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(
        check,
        "all_steps",
        lambda project: [FakeStep("lint", "fast", "failed"), FakeStep("audit", "full", "blocked")],
    )

    assert run(workspace, monkeypatch, capsys)[0] == 2


class RecordingStep(FakeStep):
    """A step that keeps the contexts it ran with."""

    def __init__(self) -> None:
        super().__init__("recorder", "fast")
        self.contexts: list[CheckContext] = []

    def run(self, context: CheckContext) -> StepResult:
        self.contexts.append(context)
        return super().run(context)


def test_base_and_pr_body_reach_the_steps(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = workspace.commit("base")
    workspace.commit("change")
    body = workspace.write("body.md", "## Evidence\n")
    recorder = RecordingStep()
    monkeypatch.setattr(check, "all_steps", lambda project: [recorder])

    code, _ = run(workspace, monkeypatch, capsys, "--base", first, "--pr-body", str(body))

    [context] = recorder.contexts
    assert code == 0
    assert (context.base, context.pr_body) == (first, "## Evidence\n")


def test_without_a_change_the_steps_get_no_base_and_no_body(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    recorder = RecordingStep()
    monkeypatch.setattr(check, "all_steps", lambda project: [recorder])

    run(workspace, monkeypatch, capsys)

    [context] = recorder.contexts
    assert (context.base, context.pr_body) == (None, None)


def test_unreadable_settings_exit_two(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    work_in(workspace, monkeypatch)

    def broken(root: object) -> None:
        raise SettingsError("project.toml: stack is missing")

    monkeypatch.setattr(cli, "load_project", broken)

    assert cli.main(["check"]) == 2
    assert "stack is missing" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("args", "message"),
    [(("--base", "nope"), "nope is not a commit"), (("--pr-body", "missing.md"), "PR body")],
)
def test_an_unusable_change_exits_two_with_one_line_on_stderr(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, ...],
    message: str,
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(check, "all_steps", lambda project: list(STEPS))

    code, out, err = run_captured(workspace, monkeypatch, capsys, *args)

    assert (code, out) == (2, "")
    assert err.startswith("devctl check: ")
    assert message in err
    assert err.count("\n") == 1


def raising_check_steps() -> list[object]:
    raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((), "blocked        step list\n    RuntimeError: boom\n"),
        (
            ("--json",),
            json.dumps(
                [{"name": "step list", "status": "blocked", "details": ["RuntimeError: boom"]}],
                indent=2,
            )
            + "\n",
        ),
    ],
)
def test_a_project_step_list_that_raises_exits_two_without_a_traceback(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: tuple[str, ...],
    expected: str,
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(devctl_project, "check_steps", raising_check_steps)

    code, out, err = run_captured(workspace, monkeypatch, capsys, *args)

    assert (code, out, err) == (2, expected, "")
