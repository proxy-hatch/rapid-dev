"""run_check, exit codes and how the change under check is found."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

import devctl_project
from check_workspace import BrokenStep, FakeStep, Workspace
from devctl import check
from devctl.check import ChangeError, exit_code, resolve_change, run_check
from devctl.check.steps import (
    PASSED_VARIABLES,
    StepResult,
    Tier,
    blocked,
    failed,
    not_applicable,
    passed,
    tool_environment,
)
from devctl.repo import Repo


def use_steps(monkeypatch: pytest.MonkeyPatch, *steps: FakeStep) -> None:
    monkeypatch.setattr(check, "all_steps", lambda project: list(steps))


def test_fast_tier_runs_only_fast_steps(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_steps(monkeypatch, FakeStep("lint", "fast"), FakeStep("tests", "full"))

    assert [r.name for r in run_check(workspace.context(), "fast")] == ["lint"]
    assert [r.name for r in run_check(workspace.context(), "full")] == ["lint", "tests"]


def test_a_step_that_raises_is_blocked(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_steps(monkeypatch, BrokenStep("map", "fast"))

    [result] = run_check(workspace.context(), "full")

    assert result.status == "blocked"
    assert result.details == ("RuntimeError: step bug",)


class NoTier:
    name = "extra"


class NoRun:
    name = "extra"
    tier = "fast"


def raising_check_steps() -> list[object]:
    raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("check_steps", "detail"),
    [
        (raising_check_steps, "RuntimeError: boom"),
        (lambda: [NoTier()], "AttributeError: 'NoTier' object has no attribute 'tier'"),
    ],
)
def test_a_step_list_that_cannot_be_built_is_blocked(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    check_steps: Callable[[], list[object]],
    detail: str,
) -> None:
    monkeypatch.setattr(devctl_project, "check_steps", check_steps)

    assert run_check(workspace.context(), "full") == [StepResult("step list", "blocked", (detail,))]


def test_a_step_without_a_run_method_is_blocked(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check, "core_steps", lambda project: [])
    monkeypatch.setattr(devctl_project, "check_steps", lambda: [NoRun()])

    [result] = run_check(workspace.context(), "full")

    assert result == StepResult(
        "extra", "blocked", ("AttributeError: 'NoRun' object has no attribute 'run'",)
    )


def test_two_steps_that_share_a_name_block_the_run(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        devctl_project,
        "check_steps",
        lambda: [FakeStep("extra", "fast"), FakeStep("extra", "full")],
    )

    [result] = run_check(workspace.context(), "full")

    assert result.status == "blocked"
    assert "two check steps are named extra" in result.details[0]


@pytest.mark.parametrize(
    ("results", "code"),
    [
        ([], 0),
        ([passed("a"), not_applicable("b")], 0),
        ([passed("a"), failed("b")], 1),
        ([failed("a"), blocked("b")], 2),
        ([blocked("a"), passed("b")], 2),
    ],
)
def test_blocked_outranks_failed(results: list[StepResult], code: int) -> None:
    assert exit_code(results) == code


def test_two_steps_cannot_share_a_name(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        devctl_project,
        "check_steps",
        lambda: [FakeStep("extra", "fast"), FakeStep("extra", "full")],
    )

    with pytest.raises(ValueError, match="two check steps are named extra"):
        check.all_steps(workspace.context().project)


def pull_request_event(path: Path, base: str, head: str, body: str | None) -> dict[str, str]:
    event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}, "body": body}}
    path.write_text(json.dumps(event))
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(path),
    }


def test_pull_request_base_is_the_merge_commits_first_parent(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    stale_base = workspace.commit("base")
    workspace.git("checkout", "-q", "-b", "feature")
    workspace.write("b.txt", "feature\n")
    head = workspace.commit("feature")
    workspace.git("checkout", "-q", "main")
    workspace.write("c.txt", "main moved on\n")
    current_base = workspace.commit("main moved")
    # GitHub's refs/pull/<n>/merge commit has these parents: base tip, then PR head.
    workspace.git("merge", "-q", "--no-ff", "--no-edit", "feature")
    environ = pull_request_event(
        workspace.root.parent / "event.json", stale_base, head, "## Evidence\r\nNot covered: x\r\n"
    )

    base, body = resolve_change(Repo.discover(workspace.root), None, None, environ)

    assert base == current_base
    assert body == "## Evidence\nNot covered: x\n"


def test_pull_request_without_a_merge_commit_uses_the_merge_base(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    workspace.git("checkout", "-q", "-b", "feature")
    workspace.write("b.txt", "feature\n")
    head = workspace.commit("feature")
    environ = pull_request_event(workspace.root.parent / "event.json", base_sha, head, None)

    base, body = resolve_change(Repo.discover(workspace.root), None, None, environ)

    assert base == base_sha
    assert body == ""


def test_ci_outside_a_pull_request_has_no_change(workspace: Workspace) -> None:
    workspace.commit("base")
    environ = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "schedule"}

    assert resolve_change(Repo.discover(workspace.root), None, None, environ) == (None, None)


def test_local_base_is_the_merge_base_with_origins_default_branch(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    workspace.git("update-ref", "refs/remotes/origin/main", base_sha)
    workspace.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    workspace.write("b.txt", "two\n")
    workspace.commit("local work")
    body = workspace.root.parent / "body.md"
    body.write_text("PR text\n")

    assert resolve_change(Repo.discover(workspace.root), None, body, {}) == (base_sha, "PR text\n")


def test_local_run_without_origin_has_no_base(workspace: Workspace) -> None:
    workspace.commit("base")

    assert resolve_change(Repo.discover(workspace.root), None, None, {}) == (None, None)


def test_explicit_base_must_be_a_commit(workspace: Workspace) -> None:
    first = workspace.commit("one")
    workspace.commit("two")
    repo = Repo.discover(workspace.root)

    assert resolve_change(repo, "HEAD~1", None, {})[0] == first
    with pytest.raises(ChangeError, match="nope is not a commit"):
        resolve_change(repo, "nope", None, {})


def test_unreadable_event_file_is_an_error(workspace: Workspace) -> None:
    workspace.commit("base")
    environ = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(workspace.root / "missing.json"),
    }

    with pytest.raises(ChangeError, match="event"):
        resolve_change(Repo.discover(workspace.root), None, None, environ)


def test_a_step_cannot_name_an_unknown_tier(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = FakeStep("extra", "fast")
    step.tier = cast("Tier", "slow")
    monkeypatch.setattr(devctl_project, "check_steps", lambda: [step])

    with pytest.raises(ValueError, match="check step extra: tier must be fast or full"):
        check.all_steps(workspace.context().project)


def test_tools_get_only_the_listed_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PASSED_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TMPDIR", "/scratch")
    monkeypatch.setenv("UV_CACHE_DIR", "/cache")
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("HOME", "/home/someone")

    assert tool_environment() == {"TMPDIR": "/scratch", "UV_CACHE_DIR": "/cache"}


def test_pull_request_body_file_outranks_the_event_body(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    environ = pull_request_event(
        workspace.root.parent / "event.json", base_sha, base_sha, "from the event"
    )
    body_file = workspace.root.parent / "body.md"
    body_file.write_text("from the file\r\n")

    _, body = resolve_change(Repo.discover(workspace.root), None, body_file, environ)

    assert body == "from the file\n"


def test_explicit_base_outranks_the_pull_request_base(workspace: Workspace) -> None:
    first = workspace.commit("one")
    head = workspace.commit("two")
    environ = pull_request_event(workspace.root.parent / "event.json", head, head, "text")

    result = resolve_change(Repo.discover(workspace.root), first, None, environ)

    assert result == (first, "text")


def test_unreadable_pr_body_file_is_an_error(workspace: Workspace) -> None:
    workspace.commit("base")

    with pytest.raises(ChangeError, match="cannot read the PR body"):
        resolve_change(Repo.discover(workspace.root), None, workspace.root / "missing.md", {})


@pytest.mark.parametrize(
    "event_text",
    [
        "{",
        "[]",
        '{"pull_request": {"base": {"sha": 1}, "head": {"sha": "b"}}}',
        '{"pull_request": {"base": {"sha": "a"}, "head": {}}}',
        '{"pull_request": {"base": {"sha": "a"}, "head": {"sha": "b"}, "body": 5}}',
    ],
)
def test_a_malformed_pull_request_event_is_an_error(workspace: Workspace, event_text: str) -> None:
    workspace.commit("base")
    event = workspace.root.parent / "event.json"
    event.write_text(event_text)
    environ = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event)}

    with pytest.raises(ChangeError, match="cannot read the pull_request event"):
        resolve_change(Repo.discover(workspace.root), None, None, environ)


def test_a_pull_request_event_without_a_path_is_an_error(workspace: Workspace) -> None:
    workspace.commit("base")

    with pytest.raises(ChangeError, match="GITHUB_EVENT_PATH is not set"):
        resolve_change(
            Repo.discover(workspace.root), None, None, {"GITHUB_EVENT_NAME": "pull_request"}
        )


def test_a_pull_request_base_outside_the_checkout_asks_for_full_history(
    workspace: Workspace,
) -> None:
    head = workspace.commit("shallow")
    environ = pull_request_event(workspace.root.parent / "event.json", "0" * 40, head, None)

    with pytest.raises(ChangeError, match=r"fetch-depth: 0"):
        resolve_change(Repo.discover(workspace.root), None, None, environ)


def test_a_pull_request_with_unrelated_history_asks_for_full_history(
    workspace: Workspace,
) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    workspace.git("checkout", "-q", "--orphan", "lonely")
    head = workspace.commit("unrelated")
    environ = pull_request_event(workspace.root.parent / "event.json", base_sha, head, None)

    with pytest.raises(ChangeError, match=r"fetch-depth: 0"):
        resolve_change(Repo.discover(workspace.root), None, None, environ)
