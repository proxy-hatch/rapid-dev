"""This repository's own Kit, synced in a scratch copy (offline)."""

import shutil
from pathlib import Path

from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import KitError

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


def offline(version):
    raise KitError(f"rapid-ship {version} is not fetched in offline tests")


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

    result = sync_repository(
        git_repo, in_place=True, templates_root=git_repo / TEMPLATES, old_templates=offline
    )

    # status --strict keeps every other managed file current, so only the changed template applies.
    assert (result.updated, result.conflicts) == ([CLI], [])
    assert SEED in result.seeded_changed
    assert (git_repo / SEED).read_bytes() == ours
    assert run_git(git_repo, "status", "--porcelain", "--", PROJECT) == ""
