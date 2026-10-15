"""rapid-ship's own check steps, run against a simulated uv and smoke script."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import devctl_project
from check_workspace import Workspace, fake_tool
from devctl.process import run_process
from devctl_project import DistributionStep, FloorPythonStep

ROOT = Path(__file__).resolve().parents[2]
UV = """
here = pathlib.Path(__file__).parent
if sys.argv[1:] == ["build"]:
    pathlib.Path("dist").mkdir()
    pathlib.Path("dist/rapid_ship-0.2.0-py3-none-any.whl").write_text("wheel")
    sys.exit(int((here / "build.exit").read_text()) if (here / "build.exit").exists() else 0)
sys.exit(0)
"""

SMOKE = """import json, pathlib, sys
root = pathlib.Path.cwd()
pathlib.Path(LOG).write_text(json.dumps({
    "cwd": str(root),
    "edited": (root / "source.py").read_text(),
    "new": (root / "new.py").exists(),
    "alias": (root / "alias").is_symlink(),
    "git": (root / ".git").exists(),
    "wheels": sorted(p.name for p in (root / "dist").glob("*.whl")),
}))
if (root / "smoke.exit").exists():
    sys.stderr.write("Smoke failed (1): rapid-ship --version\\n")
    sys.exit(int((root / "smoke.exit").read_text()))
"""


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    fake_tool(directory, "uv", UV)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def checkout(workspace: Workspace, log: Path) -> None:
    workspace.write(".gitignore", "dist/\n")
    workspace.write("source.py", "original\n")
    workspace.write("scripts/smoke_distribution.py", f"LOG = {str(log)!r}\n" + SMOKE)
    workspace.commit()
    workspace.write("source.py", "edited\n")
    workspace.write("new.py", "new\n")
    (workspace.root / "alias").symlink_to("source.py")


def test_repository_steps() -> None:
    steps = devctl_project.check_steps()

    assert [(s.name, s.tier) for s in steps] == [
        ("vendored", "fast"),
        ("distribution", "full"),
        ("python-3.12", "full"),
    ]


def test_distribution_builds_and_smokes_a_copy_of_the_work_tree(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    log = tmp_path / "smoke.json"
    checkout(workspace, log)

    result = DistributionStep().run(workspace.context())

    assert result.status == "passed", result.details
    record = json.loads(log.read_text())
    assert record["cwd"] != str(workspace.root)
    assert (record["edited"], record["new"], record["alias"], record["git"]) == (
        "edited\n",
        True,
        True,
        False,
    )
    assert record["wheels"] == ["rapid_ship-0.2.0-py3-none-any.whl"]
    assert not Path(record["cwd"]).exists()
    assert not (workspace.root / "dist").exists()


def test_distribution_fails_when_the_smoke_fails(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    checkout(workspace, tmp_path / "smoke.json")
    workspace.write("smoke.exit", "1")

    result = DistributionStep().run(workspace.context())

    assert result.status == "failed"
    # The smoke reports why on stderr; a failure that hid it would leave nothing to act on.
    assert "Smoke failed (1): rapid-ship --version" in result.details


def test_distribution_fails_when_the_build_fails(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    checkout(workspace, tmp_path / "smoke.json")
    (tools / "build.exit").write_text("1")

    assert DistributionStep().run(workspace.context()).status == "failed"
    assert not (tmp_path / "smoke.json").exists()


def test_python_floor_uses_a_separate_environment(workspace: Workspace, tools: Path) -> None:
    assert FloorPythonStep().run(workspace.context()).status == "passed"
    [call] = [json.loads(line) for line in (tools / "uv.log").read_text().splitlines()]
    assert call["argv"] == ["run", "--locked", "--python", "3.12", "pytest", "-q"]
    assert "UV_PROJECT_ENVIRONMENT" in call["env"]


@pytest.mark.parametrize(
    "path", [".controller/bin/python", ".controller-build-1/wheel.whl", ".controller-setup.lock"]
)
def test_state_left_by_the_removed_controller_stays_ignored(path: str) -> None:
    # Existing checkouts still hold this state. Unignored, Ruff would lint a virtualenv,
    # the distribution step would copy it and uv build would pack it into the source archive.
    result = run_process(["git", "check-ignore", "--no-index", "--quiet", path], ROOT, 30)

    assert result.returncode == 0
