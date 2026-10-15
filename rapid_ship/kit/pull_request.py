"""sync's pull request: its body, and pushing the branch and opening it with gh."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence, Sized
from pathlib import Path
from typing import TYPE_CHECKING

from rapid_ship.kit.git import git
from rapid_ship.kit.templates import KitError

if TYPE_CHECKING:
    from rapid_ship.kit.sync import SyncResult

REVERT = "rapid-ship sync --revert <path>"


def push_and_open_pull_request(root: Path, branch: str, base: str, title: str, body: str) -> str:
    """Push branch to origin and open a pull request into base with gh. Returns its URL."""
    retry = f"check gh pr list --head {branch} before retrying"
    _progress(f"Pushing {branch} to origin.")
    try:
        git(root, "push", "--set-upstream", "origin", branch)
    except KitError as error:
        raise KitError(f"{error}; the sync commit is on the local branch {branch}") from error
    _progress("Opening a pull request with gh.")
    command = ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title]
    command += ["--body-file", "-"]
    try:
        result = subprocess.run(  # noqa: S603  # rs-exception: EX-7
            command, cwd=root, input=body, capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise KitError(f"cannot run gh ({error}); {branch} is pushed, so {retry}") from error
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        reason = result.stderr.strip() or "it printed no pull request URL"
        raise KitError(f"gh pr create failed ({reason}); {branch} is pushed, so {retry}")
    return lines[-1]


def _progress(line: str) -> None:
    """Report a step now: pushing and gh can take a while."""
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


def pull_request_body(result: SyncResult, old_version: str) -> str:
    """The pull request text. The Evidence section comes last."""
    new_version = result.kit_version
    parts = [
        f"This pull request updates the vendored rapid-ship Kit from {old_version} to "
        f"{new_version}. `rapid-ship sync` generated it.",
        "## Changes",
    ]
    changes = [
        ("Replaced with the new template:", result.updated),
        ("Reverted to the Kit's template; sync updates them again:", result.reverted),
        ("Already equal to the new template; only the lock changed:", result.adopted),
        ("Added:", result.added),
        ("Deleted, because the Kit dropped them:", result.deleted),
    ]
    listed = [_bullets(heading, paths) for heading, paths in changes if paths]
    parts += listed or ["Only the lock changed."]
    parts.append("## Needs the owner")
    owner_lists = [
        (
            "Kit files the project edited or deleted. sync kept them and recorded them as the "
            "project's own, so the Kit no longer updates them. To give one back to the Kit, "
            f"run `{REVERT}`:",
            result.owned,
        ),
        (
            "Seeded files whose template changed. sync did not change them; "
            "apply the template change by hand if the project wants it:",
            result.seeded_changed,
        ),
        (
            "New seeded templates where the project already has a file. sync recorded them "
            "and kept the files; merge the template by hand if the project wants it:",
            result.seeded_existing,
        ),
    ]
    needs = [_bullets(heading, paths) for heading, paths in owner_lists if paths]
    if result.conflicts:
        lines = [f"- `{conflict.path}`: {conflict.reason}" for conflict in result.conflicts]
        needs.append(
            "\n".join(["Conflicts. sync did not write or record these paths:", "", *lines])
        )
    parts += needs or ["Nothing."]
    counted: dict[str, Sized] = {
        "updated": result.updated,
        "reverted": result.reverted,
        "adopted": result.adopted,
        "added": result.added,
        "deleted": result.deleted,
        "owned": result.owned,
        "seeded_changed": result.seeded_changed,
        "seeded_existing": result.seeded_existing,
        "conflicts": result.conflicts,
    }
    counts = ", ".join(
        f"{len(items)} {name.replace('_', ' ')}" for name, items in counted.items() if items
    )
    parts += [
        "## Evidence",
        f"- `rapid-ship sync`: rapid-ship {old_version} to {new_version}; "
        f"{counts or 'nothing changed'}",
        "Not covered: sync did not run ./devctl check; CI runs it on this pull request.",
    ]
    return "\n\n".join(parts) + "\n"


def _bullets(heading: str, paths: Sequence[str]) -> str:
    return "\n".join([heading, "", *(f"- `{path}`" for path in paths)])
