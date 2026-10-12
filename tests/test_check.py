"""Exercise the validation entry point with executable stand-ins, without nested test runs."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/check.py", root / "scripts/check.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text(".controller/\ndist/\n")
    (root / "source.py").write_text("original\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    (root / "source.py").write_text("edited\n")
    (root / "new.py").write_text("new source\n")
    (root / "alias").symlink_to("source.py")
    (root / ".controller").mkdir()
    (root / ".controller/keep").write_text("installed controller\n")
    record = tmp_path / "stages.jsonl"
    stand_in = """import json, os, pathlib, sys
root = pathlib.Path.cwd()
name = pathlib.Path(sys.argv[0]).stem
with open(os.environ["STAGE_LOG"], "a") as log:
    log.write(json.dumps({"name": name, "args": sys.argv[1:], "root": str(root)}) + "\\n")
if name == os.environ.get("FAIL_STAGE"):
    sys.exit(9)
if name == "devctl":
    assert root != pathlib.Path(os.environ["SOURCE_ROOT"])
    assert (root / "source.py").read_text() == "edited\\n"
    assert (root / "new.py").read_text() == "new source\\n"
    assert (root / "alias").is_symlink()
    assert (root / "alias").readlink() == pathlib.Path("source.py")
    assert not (root / ".controller").exists()
    (root / ".controller/bin").mkdir(parents=True)
    (root / ".controller/bin/python").symlink_to(sys.executable)
if name == "uv":
    assert sys.argv[1:] == ["build"]
    assert (root / ".controller/bin/python").exists()
    (root / "dist").mkdir()
if name == "smoke_distribution":
    assert (root / "dist").is_dir()
"""
    for name in ("ruff", "mypy", "pytest"):
        (root / f"{name}.py").write_text(stand_in)
    for name in ("check_repository", "smoke_controller", "smoke_distribution"):
        (root / "scripts" / f"{name}.py").write_text(stand_in)
    (root / "devctl").write_text(stand_in)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "uv").write_text(f"#!{sys.executable}\n" + stand_in)
    (tools / "uv").chmod(0o755)
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


def test_validation_uses_current_source_and_preserves_installed_controller(tmp_path):
    root, record, environment = checkout(tmp_path)

    result = run(root, environment)

    assert result.returncode == 0, result.stdout + result.stderr
    observed = stages(record)
    names = [stage["name"] for stage in observed]
    assert names == [
        "check_repository",
        "ruff",
        "ruff",
        "mypy",
        "pytest",
        "devctl",
        "smoke_controller",
        "uv",
        "smoke_distribution",
    ]
    assert observed[1]["args"] == ["check", "."]
    assert observed[2]["args"] == ["format", "--check", "."]
    assert observed[3]["args"] == ["rapid_ship"]
    assert all(stage["root"] == str(root) for stage in observed[:5])
    assert len({stage["root"] for stage in observed[5:]}) == 1
    assert not Path(observed[-1]["root"]).exists()
    assert (root / ".controller/keep").read_text() == "installed controller\n"
    assert not (root / "dist").exists()


@pytest.mark.parametrize("failed_stage", ["check_repository", "mypy", "smoke_controller"])
def test_validation_stops_after_failure_and_cleans_temporary_source(tmp_path, failed_stage):
    root, record, environment = checkout(tmp_path)

    result = run(root, {**environment, "FAIL_STAGE": failed_stage})

    assert result.returncode == 9, result.stdout + result.stderr
    observed = stages(record)
    assert observed[-1]["name"] == failed_stage
    assert failed_stage in result.stdout + result.stderr
    assert (root / ".controller/keep").read_text() == "installed controller\n"
    if failed_stage == "smoke_controller":
        assert not Path(observed[-1]["root"]).exists()
