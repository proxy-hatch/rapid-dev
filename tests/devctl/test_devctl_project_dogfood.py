"""Integration test: needs network access (uv, pip-audit, Python 3.12) and gitleaks on PATH.

After a template edit and `uv run rapid-ship sync --in-place`, the vendored devctl carries the
edit, the seeded devctl_project does not, and ./devctl check still runs this repository's own
steps. Everything runs in a copy of the work tree, so the checkout is never written.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from check_workspace import new_workspace
from devctl.check.steps import tool_environment
from devctl.process import run_process
from devctl.repo import Repo
from devctl_project import copy_work_tree

ROOT = Path(__file__).resolve().parents[2]
ONLY_TEST = '''"""The one test in the dog-food copy."""

from rapid_ship.files import atomic_replace


def test_the_package_imports() -> None:
    assert callable(atomic_replace)
'''
TEMPLATES = "rapid_ship/templates/common/tools/devctl"
MANAGED = "devctl/check/__init__.py"
EDIT = "# Edited by the dog-food test.\n"


def test_own_check_steps_still_run_after_sync(tmp_path: Path) -> None:
    copy = new_workspace(tmp_path / "copy")
    copy_work_tree(Repo.discover(ROOT), copy.root)
    shutil.rmtree(copy.root / "tests")
    copy.write("tests/test_copy.py", ONLY_TEST)
    copy.commit("copy of the work tree")
    for template in (f"{TEMPLATES}/{MANAGED}", f"{TEMPLATES}/devctl_project/__init__.py"):
        path = copy.root / template
        path.write_text(path.read_text() + EDIT)
    copy.commit("edit a managed devctl template and the devctl_project seed template")

    synced = run_process(
        ["uv", "run", "--locked", "rapid-ship", "sync", "--in-place"],
        copy.root,
        600,
        env=tool_environment(),
    )

    assert synced.returncode == 0, synced.stdout + synced.stderr
    # sync vendors the managed edit and never writes the seeded copy this repository owns.
    assert copy.git("status", "--porcelain", "--", "tools/devctl/devctl")
    assert (copy.root / "tools/devctl" / MANAGED).read_text().endswith(EDIT)
    assert copy.git("status", "--porcelain", "--", "tools/devctl/devctl_project") == ""

    checked = run_process(
        ["./devctl", "check", "--tier", "full", "--json"], copy.root, 1800, env=tool_environment()
    )

    assert checked.stdout, checked.stderr
    # Core steps may fail on the reduced tests/ directory; only the project's steps count here.
    results = [(step["name"], step["status"]) for step in json.loads(checked.stdout)]
    assert results[-3:] == [
        ("vendored", "passed"),
        ("distribution", "passed"),
        ("python-3.12", "passed"),
    ], checked.stdout
