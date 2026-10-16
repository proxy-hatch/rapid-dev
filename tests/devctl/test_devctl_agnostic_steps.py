"""Secrets and workflows steps, run against simulated gitleaks and uv."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from check_workspace import Workspace, fake_tool
from devctl.check.stacks.agnostic import SecretsStep, WorkflowsStep

GITLEAKS = """
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
report = here / "report.json"
if report.exists():
    pathlib.Path(args[args.index("--report-path") + 1]).write_text(report.read_text())
sys.exit(int((here / "gitleaks.exit").read_text()))
"""


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def argv(tools: Path, name: str) -> list[str]:
    return list(json.loads((tools / f"{name}.log").read_text().splitlines()[0])["argv"])


def cwd(tools: Path, name: str) -> str:
    return str(json.loads((tools / f"{name}.log").read_text().splitlines()[0])["cwd"])


def test_secrets_scans_the_change_and_reports_findings(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text("10")
    (tools / "report.json").write_text(
        json.dumps(
            [
                {
                    "RuleID": "aws-access-token",
                    "File": "README.md",
                    "StartLine": 3,
                    "Commit": "0123456789ab",
                }
            ]
        )
    )

    result = SecretsStep().run(workspace.context(base="abc123"))

    assert result.status == "failed"
    assert result.details == ("aws-access-token README.md:3 (commit 01234567)",)
    assert "--log-opts=abc123..HEAD" in argv(tools, "gitleaks")


@pytest.mark.parametrize(("code", "status"), [(0, "passed"), (1, "blocked"), (126, "blocked")])
def test_secrets_exit_codes(workspace: Workspace, tools: Path, code: int, status: str) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text(str(code))

    result = SecretsStep().run(workspace.context())

    assert result.status == status
    assert not any(arg.startswith("--log-opts") for arg in argv(tools, "gitleaks"))


def test_secrets_without_a_base_scans_the_history_from_the_repository_root(
    workspace: Workspace, tools: Path
) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text("0")

    SecretsStep().run(workspace.context())

    command = argv(tools, "gitleaks")
    assert command[:7] == [
        "git",
        "--no-banner",
        "--redact",
        "--exit-code",
        "10",
        "--report-format",
        "json",
    ]
    assert command[7] == "--report-path"
    assert not Path(command[8]).is_relative_to(workspace.root)  # The report stays out of the repo.
    assert command[9:] == ["."]
    assert cwd(tools, "gitleaks") == str(workspace.root)


def test_secrets_lists_every_finding_in_report_order(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text("10")
    finding = {"RuleID": "generic-api-key", "StartLine": 7, "Commit": "fedcba9876543210"}
    (tools / "report.json").write_text(
        json.dumps([{**finding, "File": "a.py"}, {**finding, "File": "b.py"}])
    )

    assert SecretsStep().run(workspace.context()).details == (
        "generic-api-key a.py:7 (commit fedcba98)",
        "generic-api-key b.py:7 (commit fedcba98)",
    )


@pytest.mark.parametrize(
    "report",
    [
        None,
        "not json",
        "[]",
        "{}",
        "[1]",
        '[{"RuleID": "aws-access-token", "File": "a", "StartLine": "3", "Commit": "0123"}]',
        '[{"RuleID": "aws-access-token", "File": "a", "StartLine": 3}]',
    ],
)
def test_a_finding_exit_without_a_readable_report_is_blocked(
    workspace: Workspace, tools: Path, report: str | None
) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text("10")
    if report is not None:
        (tools / "report.json").write_text(report)

    result = SecretsStep().run(workspace.context())

    assert result.status == "blocked"
    assert result.details[0] == "gitleaks found secrets but wrote no readable report"


def test_missing_gitleaks_is_blocked(
    workspace: Workspace, tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    monkeypatch.setenv("PATH", str(tools))  # hide any gitleaks installed on this machine

    assert SecretsStep().run(context).details == (
        "gitleaks is not on PATH; install gitleaks 8.30.1",
    )


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (0, "passed"),
        (11, "failed"),
        (14, "failed"),
        (3, "not_applicable"),
        (1, "blocked"),
        (2, "blocked"),
    ],
)
def test_workflows_exit_codes(workspace: Workspace, tools: Path, code: int, status: str) -> None:
    fake_tool(tools, "uv", f"sys.exit({code})")

    assert WorkflowsStep().run(workspace.context()).status == status
    assert argv(tools, "uv") == [
        "tool",
        "run",
        "--from",
        "zizmor==1.30.1",
        "zizmor",
        "--offline",
        "--no-progress",
        "--strict-collection",
        "--format",
        "plain",
        ".",
    ]


def test_a_missing_uv_blocks_the_workflows_step(
    workspace: Workspace, tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    monkeypatch.setenv("PATH", str(tools))  # hide any uv installed on this machine

    result = WorkflowsStep().run(context)

    assert (result.status, result.details) == ("blocked", ("uv is not on PATH",))


def test_no_inputs_is_not_applicable_and_says_why(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "uv", "sys.exit(3)")

    assert WorkflowsStep().run(workspace.context()).details == ("no workflows or actions found",)
