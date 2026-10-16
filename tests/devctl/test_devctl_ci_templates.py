"""The managed CI workflow and pre-commit hook. The hook test runs a simulated devctl."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from check_workspace import Workspace
from devctl.check.stacks.agnostic import GITLEAKS_VERSION

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "rapid_ship/templates/common/.github/workflows/devctl-check.yml"
HOOK = ROOT / "rapid_ship/templates/common/.githooks/pre-commit"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_UV = "astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884"
GITLEAKS_SHA256 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"


def workflow() -> dict[Any, Any]:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict)
    return data


def test_triggers_include_body_edits_pushes_nightly_and_manual_runs() -> None:
    on = workflow()[True]  # PyYAML reads the key "on" as the boolean True.

    assert on["pull_request"] == {"types": ["opened", "synchronize", "reopened", "edited"]}
    assert on["push"] == {"branches": ["main", "master"]}
    assert on["schedule"] == [{"cron": "23 4 * * *"}]
    assert "workflow_dispatch" in on


def test_permissions_and_concurrency() -> None:
    data = workflow()

    assert data["permissions"] == {"contents": "read"}
    assert data["concurrency"] == {
        "group": "devctl-check-${{ github.ref }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }


def test_job_checks_out_full_history_without_credentials_and_runs_the_full_tier() -> None:
    job = workflow()["jobs"]["check"]
    steps = job["steps"]

    assert job["name"] == "devctl check"
    assert steps[0] == {"uses": CHECKOUT, "with": {"persist-credentials": False, "fetch-depth": 0}}
    assert steps[1] == {"uses": SETUP_UV}
    assert steps[-1] == {"name": "Run devctl check", "run": "./devctl check --tier full"}
    assert all("${{" not in step.get("run", "") for step in steps)


def test_actions_are_pinned_by_sha_with_a_version_comment() -> None:
    uses = [line.strip() for line in WORKFLOW.read_text().splitlines() if "uses:" in line]

    assert uses
    assert all(re.search(r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$", line) for line in uses)


def test_gitleaks_is_pinned_and_verified() -> None:
    install = workflow()["jobs"]["check"]["steps"][2]

    assert install["env"] == {
        "GITLEAKS_VERSION": GITLEAKS_VERSION,
        "GITLEAKS_SHA256": GITLEAKS_SHA256,
    }
    assert "sha256sum --check --strict" in install["run"]


def test_vendored_copies_match_their_templates() -> None:
    assert (ROOT / ".github/workflows/devctl-check.yml").read_bytes() == WORKFLOW.read_bytes()
    assert (ROOT / ".githooks/pre-commit").read_bytes() == HOOK.read_bytes()
    assert os.access(ROOT / ".githooks/pre-commit", os.X_OK)


def test_hook_runs_the_fast_tier_and_blocks_a_failing_commit(workspace: Workspace) -> None:
    workspace.write(".githooks/pre-commit", HOOK.read_text()).chmod(0o700)
    workspace.write(
        "devctl",
        f"#!{sys.executable}\nimport pathlib, sys\n"
        "pathlib.Path('devctl.log').write_text(' '.join(sys.argv[1:]))\n"
        "sys.exit(int(pathlib.Path('devctl.exit').read_text()))\n",
    ).chmod(0o700)
    workspace.write(".gitignore", "devctl.log\ndevctl.exit\n")
    workspace.write("devctl.exit", "1")
    workspace.git("add", "-A")

    rejected = workspace.try_git("-c", "core.hooksPath=.githooks", "commit", "-q", "-m", "x")
    workspace.write("devctl.exit", "0")
    accepted = workspace.try_git("-c", "core.hooksPath=.githooks", "commit", "-q", "-m", "x")

    assert rejected.returncode != 0
    assert accepted.returncode == 0
    assert (workspace.root / "devctl.log").read_text() == "check --tier fast"
