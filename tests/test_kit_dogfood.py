"""This repository's own Kit: every Kit file stays the Kit's, and a sync in a scratch copy
(offline)."""

import shutil
from pathlib import Path

from rapid_ship.kit.lock import read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import is_excluded, read_excluded, read_optional_skills, render_files

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = "rapid_ship/templates"
PROJECT = "tools/devctl/devctl_project"
SEED = f"{PROJECT}/__init__.py"
CLI = "tools/devctl/devctl/cli.py"


def copy_this_repository(destination, run_git):
    """Copy the files git keeps here, uncommitted work included.

    Rendering and the wheel see the same files.
    """
    listed = run_git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for relative in filter(None, listed.split("\0")):
        source = ROOT / relative
        if not (source.is_symlink() or source.is_file()):
            continue  # deleted in the work tree, or an untracked nested repository
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def append(path, text):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(text)


def test_this_repository_sync_leaves_devctl_project_unchanged(git_repo, run_git, commit_all):
    copy_this_repository(git_repo, run_git)
    append(
        git_repo / SEED, "\nOWNED_HERE = True\n"
    )  # this repository's own edit to its seeded copy
    (git_repo / PROJECT / "verbs.py").write_text('"""A project verb module."""\n')
    append(git_repo / TEMPLATES / "common" / SEED, "\n# A newer seed.\n")
    append(git_repo / TEMPLATES / "common" / CLI, "\n# A newer devctl.\n")
    commit_all(git_repo)
    ours = (git_repo / SEED).read_bytes()

    result = sync_repository(git_repo, in_place=True, templates_root=git_repo / TEMPLATES)

    # status --strict keeps every other managed file current, so only the changed template applies.
    assert (result.updated, result.owned, result.conflicts) == ([CLI], [], [])
    assert SEED in result.seeded_changed
    assert (git_repo / SEED).read_bytes() == ours
    assert run_git(git_repo, "status", "--porcelain", "--", PROJECT) == ""


def owned_kit_files(root, templates_root=None):
    """Kit-managed paths that root's lock records as the project's own (seeded), because sync
    found them edited or deleted. Excluded paths are the project's by choice and not listed."""
    lock = read_lock(root)
    excluded = read_excluded(root)
    optional = read_optional_skills(root)
    templates = {
        t.path: t for t in render_files(lock.stack, lock.variables, optional, root=templates_root)
    }
    return [
        entry.path
        for entry in lock.entries
        if entry.kind == "seeded"
        and entry.path in templates
        and templates[entry.path].kind == "managed"
        and not is_excluded(entry.path, excluded)
    ]


def test_no_kit_managed_file_is_this_repositorys_own():
    # status --strict passes a file that sync made the project's own, so this test is what holds
    # every Kit file here to its template (spec section 3, "Who owns what").
    owned = owned_kit_files(ROOT)

    assert owned == [], (
        "these Kit files were edited here and sync recorded them as this repository's own: "
        f"{owned}. Run uv run rapid-ship sync --in-place --revert <path> for each, then make the "
        "change in its template under rapid_ship/templates/"
    )


def test_an_edit_that_sync_makes_the_projects_own_passes_strict_but_not_this_check(
    git_repo, run_git, commit_all
):
    copy_this_repository(git_repo, run_git)
    append(git_repo / CLI, "\n# Edited in the vendored copy.\n")
    commit_all(git_repo)
    templates = git_repo / TEMPLATES

    result = sync_repository(git_repo, in_place=True, templates_root=templates)

    assert result.owned == [CLI]
    assert classify(git_repo, templates_root=templates).strict_ok
    assert owned_kit_files(git_repo, templates) == [CLI]
