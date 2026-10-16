"""Offline, simulated: run the validation entry point with stand-ins, without nested test runs."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAND_IN = """import json, os, pathlib, sys
root = pathlib.Path.cwd()
name = pathlib.Path(sys.argv[0]).stem
with open(os.environ["STAGE_LOG"], "a") as log:
    log.write(json.dumps({"name": name, "args": sys.argv[1:], "root": str(root)}) + "\\n")
if name == os.environ.get("FAIL_STAGE"):
    sys.exit(9)
if name == "uv":
    assert sys.argv[1:] == ["build"]
    assert root != pathlib.Path(os.environ["SOURCE_ROOT"])
    assert (root / "source.py").read_text() == "edited\\n"
    assert (root / "new.py").read_text() == "new source\\n"
    assert (root / "alias").is_symlink()
    assert (root / "alias").readlink() == pathlib.Path("source.py")
    assert not (root / "ignored").exists()
    (root / "dist").mkdir()
if name == "smoke_distribution":
    assert (root / "dist").is_dir()
"""


def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/check.py", root / "scripts/check.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("ignored/\ndist/\n")
    (root / "source.py").write_text("original\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    (root / "source.py").write_text("edited\n")
    (root / "new.py").write_text("new source\n")
    (root / "alias").symlink_to("source.py")
    (root / "ignored").mkdir()
    (root / "ignored/state").write_text("local state\n")
    for name in ("ruff", "mypy", "pytest", "rapid_ship"):
        (root / f"{name}.py").write_text(STAND_IN)
    for name in ("check_repository", "smoke_distribution"):
        (root / "scripts" / f"{name}.py").write_text(STAND_IN)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "uv").write_text(f"#!{sys.executable}\n" + STAND_IN)
    (tools / "uv").chmod(0o755)
    record = tmp_path / "stages.jsonl"
    environment = {
        **os.environ,
        "PATH": f"{tools}:{os.environ['PATH']}",
        "STAGE_LOG": str(record),
        "SOURCE_ROOT": str(root),
    }
    return root, record, environment


def run(root, environment):
    return subprocess.run(
        [sys.executable, str(root / "scripts/check.py")],
        cwd=root.parent,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def stages(record):
    return [json.loads(line) for line in record.read_text().splitlines()]


def test_validation_checks_the_checkout_then_builds_a_temporary_copy(tmp_path):
    root, record, environment = checkout(tmp_path)

    result = run(root, environment)

    assert result.returncode == 0, result.stdout + result.stderr
    observed = stages(record)
    assert [stage["name"] for stage in observed] == [
        "check_repository",
        "rapid_ship",
        "ruff",
        "ruff",
        "mypy",
        "pytest",
        "uv",
        "smoke_distribution",
    ]
    assert observed[1]["args"] == ["status", "--strict"]
    assert observed[2]["args"] == ["check", "."]
    assert observed[3]["args"] == ["format", "--check", "."]
    assert observed[4]["args"] == []  # Use the complete file list configured in pyproject.toml.
    assert all(stage["root"] == str(root) for stage in observed[:6])
    assert len({stage["root"] for stage in observed[6:]}) == 1
    assert not Path(observed[-1]["root"]).exists()
    assert (root / "ignored/state").read_text() == "local state\n"
    assert not (root / "dist").exists()


@pytest.mark.parametrize(
    "failed_stage", ["check_repository", "rapid_ship", "mypy", "uv", "smoke_distribution"]
)
def test_validation_stops_after_failure_and_cleans_temporary_source(tmp_path, failed_stage):
    root, record, environment = checkout(tmp_path)

    result = run(root, {**environment, "FAIL_STAGE": failed_stage})

    assert result.returncode == 9, result.stdout + result.stderr
    observed = stages(record)
    assert observed[-1]["name"] == failed_stage
    assert failed_stage in result.stdout + result.stderr
    assert (root / "ignored/state").read_text() == "local state\n"
    if failed_stage in ("uv", "smoke_distribution"):
        assert not Path(observed[-1]["root"]).exists()


@pytest.mark.parametrize(
    "path", [".controller/bin/python", ".controller-build-1/wheel.whl", ".controller-setup.lock"]
)
def test_state_left_by_the_removed_controller_stays_ignored(path):
    # Existing checkouts still hold this state. Unignored, Ruff would lint a virtualenv,
    # check.py would copy it and uv build would pack it into the source archive.
    result = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", path], cwd=ROOT)

    assert result.returncode == 0
