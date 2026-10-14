"""The version-only rapid-ship command, run through its entry point and as a module. Offline."""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
ENTRY_POINT = Path(sys.executable).parent / "rapid-ship"


@pytest.mark.parametrize("command", [[str(ENTRY_POINT)], [sys.executable, "-m", "rapid_ship"]])
def test_version_prints_name_and_project_version(tmp_path, command):
    result = subprocess.run(
        [*command, "--version"], cwd=tmp_path, capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"rapid-ship {VERSION}\n"
    assert result.stderr == ""


@pytest.mark.parametrize("arguments", [[], ["--unknown"]])
def test_anything_else_cannot_run(tmp_path, arguments):
    result = subprocess.run(
        [sys.executable, "-m", "rapid_ship", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage: rapid-ship" in result.stderr
