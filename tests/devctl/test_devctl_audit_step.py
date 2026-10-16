"""The audit step, run against a simulated uv that stands in for export and pip-audit."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from check_workspace import Workspace, fake_tool
from devctl.check.stacks.python import AuditStep

UV = """
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
if args[0] == "export":
    pathlib.Path(args[args.index("--output-file") + 1]).write_text("requests==2.25.0\\n")
    sys.exit(int((here / "export.exit").read_text()) if (here / "export.exit").exists() else 0)
report = here / "report.json"
if report.exists():
    pathlib.Path(args[args.index("--output") + 1]).write_text(report.read_text())
sys.exit(int((here / "audit.exit").read_text()) if (here / "audit.exit").exists() else 0)
"""

CLEAN = {"dependencies": [{"name": "requests", "version": "2.32.5", "vulns": []}], "fixes": []}
VULNERABLE = {
    "dependencies": [
        {
            "name": "requests",
            "version": "2.25.0",
            "vulns": [{"id": "PYSEC-2023-74", "fix_versions": ["2.31.0"]}],
        }
    ],
    "fixes": [],
}


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    fake_tool(directory, "uv", UV)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def audit(workspace: Workspace, tools: Path, report: object | None, code: int) -> tuple[str, ...]:
    if report is not None:
        (tools / "report.json").write_text(json.dumps(report))
    (tools / "audit.exit").write_text(str(code))
    result = AuditStep().run(workspace.context())
    return (result.status, *result.details)


def test_clean_report_passes(workspace: Workspace, tools: Path) -> None:
    assert audit(workspace, tools, CLEAN, 0) == ("passed",)
    argv = [json.loads(line)["argv"] for line in (tools / "uv.log").read_text().splitlines()]
    assert argv[0][:4] == ["export", "--locked", "--format", "requirements-txt"]
    # Without --all-extras, a dependency reachable only through an extra is never audited.
    assert {"--all-groups", "--all-extras"} <= set(argv[0])
    assert argv[1][:5] == ["tool", "run", "--from", "pip-audit==2.10.1", "pip-audit"]
    assert {"--require-hashes", "--disable-pip", "--strict"} <= set(argv[1])


def test_vulnerability_fails(workspace: Workspace, tools: Path) -> None:
    assert audit(workspace, tools, VULNERABLE, 1) == (
        "failed",
        "requests 2.25.0: PYSEC-2023-74 (fixed in 2.31.0)",
    )


@pytest.mark.parametrize(("report", "code"), [(None, 1), (CLEAN, 1), ("not a report", 0)])
def test_no_report_or_unexplained_exit_is_blocked(
    workspace: Workspace, tools: Path, report: object | None, code: int
) -> None:
    assert audit(workspace, tools, report, code)[0] == "blocked"


def test_failed_export_is_blocked(workspace: Workspace, tools: Path) -> None:
    (tools / "export.exit").write_text("2")

    assert audit(workspace, tools, CLEAN, 0)[0] == "blocked"


def vulnerable(*fix_versions: str) -> dict[str, object]:
    vulns = [{"id": "PYSEC-2023-74", "fix_versions": list(fix_versions)}]
    return {"dependencies": [{"name": "requests", "version": "2.25.0", "vulns": vulns}]}


@pytest.mark.parametrize(
    ("fix_versions", "detail"),
    [
        ((), "requests 2.25.0: PYSEC-2023-74 (no fix yet)"),
        (("2.31.0", "2.32.0"), "requests 2.25.0: PYSEC-2023-74 (fixed in 2.31.0, 2.32.0)"),
    ],
)
def test_each_vulnerability_names_its_fixes(
    workspace: Workspace, tools: Path, fix_versions: tuple[str, ...], detail: str
) -> None:
    assert audit(workspace, tools, vulnerable(*fix_versions), 1) == ("failed", detail)


def test_a_vulnerability_listed_twice_is_reported_once(workspace: Workspace, tools: Path) -> None:
    twice = vulnerable("2.31.0")
    dependency = twice["dependencies"]
    assert isinstance(dependency, list)
    dependency[0]["vulns"] *= 2

    assert audit(workspace, tools, twice, 1) == (
        "failed",
        "requests 2.25.0: PYSEC-2023-74 (fixed in 2.31.0)",
    )


@pytest.mark.parametrize(
    "report",
    [
        {"dependencies": "requests"},
        {"dependencies": ["requests"]},
        {"dependencies": [{"name": "requests", "version": "2.25.0", "vulns": "PYSEC-2023-74"}]},
        {
            "dependencies": [
                {"name": "requests", "version": "2.25.0", "vulns": [{"fix_versions": []}]}
            ]
        },
        {"dependencies": [{"name": "requests", "vulns": [{"id": "PYSEC-2023-74"}]}]},
    ],
)
def test_a_report_the_step_cannot_read_is_never_clean(
    workspace: Workspace, tools: Path, report: object
) -> None:
    assert audit(workspace, tools, report, 0)[:2] == (
        "blocked",
        "pip-audit wrote no readable report",
    )


def test_a_skipped_dependency_without_vulns_is_not_a_finding(
    workspace: Workspace, tools: Path
) -> None:
    skipped = {"dependencies": [{"name": "internal", "skip_reason": "not on PyPI"}]}

    assert audit(workspace, tools, skipped, 0) == ("passed",)


def test_missing_uv_is_blocked(
    workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    result = AuditStep().run(context)

    assert (result.status, result.details) == ("blocked", ("uv is not on PATH",))
