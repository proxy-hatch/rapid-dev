"""sync's pull request: its body, and pushing the branch and opening it with gh."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence, Sized
from pathlib import Path
from typing import TYPE_CHECKING

from rapid_ship.kit.git import git
from rapid_ship.kit.templates import KitError

if TYPE_CHECKING:
    from rapid_ship.kit.sync import SyncResult

_DIFF_LINES = 200
_BODY_LIMIT = 60_000  # below GitHub's pull request body limit; the exact limit was not checked
_DIFF_OVERHEAD = 100  # the fence and the cut note around each conflict diff
WAYS_OUT = (
    "sync left each file and its lock entry unchanged. To clear one, make the file equal the new "
    "template, or list the path under `[kit] exclude` in `.rapid-ship/project.toml`."
)


def push_and_open_pull_request(root: Path, branch: str, base: str, title: str, body: str) -> str:
    """Push branch to origin and open a pull request into base with gh. Returns its URL."""
    retry = f"check gh pr list --head {branch} before retrying"
    _progress(f"Pushing {branch} to origin.")
    try:
        git(root, "push", "--no-verify", "--set-upstream", "origin", branch)
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
    """The pull request text. The Evidence section comes last and is never cut."""
    diffs = [_first_lines(conflict.diff) for conflict in result.conflicts]
    body = _body(result, old_version, diffs)
    if len(body) > _BODY_LIMIT:
        spare = _BODY_LIMIT - len(_body(result, old_version, [""] * len(diffs)))
        share = max(spare // max(len(diffs), 1) - _DIFF_OVERHEAD, 0)
        diffs = [_fit(diff, share) for diff in diffs]
        body = _body(result, old_version, diffs)
    return body


def _body(result: SyncResult, old_version: str, diffs: Sequence[str]) -> str:
    new_version = result.kit_version
    parts = [
        f"This pull request updates the vendored rapid-ship Kit from {old_version} to "
        f"{new_version}. `rapid-ship sync` generated it.",
        "## Changes",
    ]
    changes = [
        ("Replaced with the new template:", result.updated),
        ("Merged the template change into the project's edits:", result.merged),
        ("Already equal to the new template; only the lock changed:", result.adopted),
        ("Added:", result.added),
        ("Deleted, because the Kit dropped them:", result.deleted),
    ]
    listed = [_bullets(heading, paths) for heading, paths in changes if paths]
    parts += listed or ["Only the lock changed."]
    parts.append("## Needs the owner")
    needs: list[str] = []
    if result.conflicts:
        needs.append(f"Conflicts. {WAYS_OUT}")
        for conflict, diff in zip(result.conflicts, diffs, strict=True):
            needs.append(f"- `{conflict.path}`: {conflict.reason}")
            if diff:
                fence = "`" * max(3, _longest_backtick_run(diff) + 1)
                needs.append(f"{fence}diff\n{diff}\n{fence}")
    owner_lists = [
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
        (
            "Files the Kit dropped after the project edited them. sync kept them, "
            "and the project owns them now:",
            result.released,
        ),
        (
            "Managed files missing from the work tree. Restore them, or list them under "
            "`[kit] exclude` in `.rapid-ship/project.toml`:",
            result.missing,
        ),
    ]
    needs += [_bullets(heading, paths) for heading, paths in owner_lists if paths]
    parts += needs or ["Nothing."]
    counted: dict[str, Sized] = {
        "updated": result.updated,
        "merged": result.merged,
        "adopted": result.adopted,
        "added": result.added,
        "deleted": result.deleted,
        "released": result.released,
        "seeded_changed": result.seeded_changed,
        "seeded_existing": result.seeded_existing,
        "missing": result.missing,
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


def _first_lines(diff: str) -> str:
    lines = diff.splitlines()
    if len(lines) <= _DIFF_LINES:
        return diff
    return "\n".join([*lines[:_DIFF_LINES], f"[diff cut at {_DIFF_LINES} lines]"])


def _fit(diff: str, size: int) -> str:
    """Keep whole lines of diff within size characters, then say it was cut."""
    if len(diff) <= size:
        return diff
    kept: list[str] = []
    used = 0
    for line in diff.splitlines():
        used += len(line) + 1
        if used > size:
            break
        kept.append(line)
    return "\n".join([*kept, "[diff cut to fit the pull request body]"])


def _longest_backtick_run(text: str) -> int:
    return max((len(run) for run in re.findall(r"`+", text)), default=0)
