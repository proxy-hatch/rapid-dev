"""[kit] exclude during rapid-ship sync (offline): an excluded path is never written,
re-created or deleted, its skill link is covered, and removing it from the list restores
normal handling (spec section 3, Project overrides)."""

import os
from collections.abc import Callable
from pathlib import Path

from rapid_ship.kit.lock import LOCK_PATH, LockEntry, file_sha256, read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import SyncResult, sync_repository

CLI = "tools/devctl/devctl/cli.py"
SKILL = ".agents/skills/rs-demo/SKILL.md"
NEW_CLI = "one\ntwo\nthree\nfour\nFIVE\n"


def sync(root: Path, new: Path, *, in_place: bool) -> SyncResult:
    return sync_repository(root, in_place=in_place, templates_root=new, kit_version="9.9.9")


def entry(root: Path, path: str) -> LockEntry:
    return {item.path: item for item in read_lock(root).entries}[path]


def test_an_excluded_file_the_project_edited_is_left_unreported(
    git_repo: Path,
    vendored: Path,
    make_templates: Callable[..., Path],
    commit_all: Callable[..., None],
    write_kit_settings: Callable[..., None],
) -> None:
    write_kit_settings(git_repo, exclude=[CLI])
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": NEW_CLI})

    result = sync(git_repo, new, in_place=True)

    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nfive\n"
    assert (result.owned, result.conflicts, result.changed) == ([], [], False)
    assert entry(git_repo, CLI) == before  # the lock records no exclusion


def test_a_deleted_excluded_file_stays_deleted(
    git_repo: Path,
    vendored: Path,
    make_templates: Callable[..., Path],
    commit_all: Callable[..., None],
    write_kit_settings: Callable[..., None],
) -> None:
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, in_place=True)

    assert not os.path.lexists(git_repo / "devctl")
    assert not result.changed
    assert result.owned == []
    assert (git_repo / LOCK_PATH).read_bytes() == lock  # the kit_version stays too
    report = classify(git_repo, templates_root=new)
    assert {item.path: item.state for item in report.files}["devctl"] == "excluded"
    assert report.strict_ok


def test_an_excluded_skill_directory_covers_its_link(
    git_repo: Path,
    vendored: Path,
    make_templates: Callable[..., Path],
    commit_all: Callable[..., None],
    run_git: Callable[..., str],
    write_kit_settings: Callable[..., None],
) -> None:
    write_kit_settings(git_repo, exclude=[".agents/skills/rs-demo", ".agents/skills/rs-new"])
    run_git(git_repo, "rm", "-q", "-r", ".agents/skills/rs-demo", ".claude/skills/rs-demo")
    commit_all(git_repo)
    new = make_templates(
        "new",
        {f"common/{SKILL}": "demo, revised\n", "common/.agents/skills/rs-new/SKILL.md": "new\n"},
    )

    result = sync(git_repo, new, in_place=True)

    for name in ("rs-demo", "rs-new"):
        assert not os.path.lexists(git_repo / ".agents/skills" / name)
        assert not os.path.lexists(git_repo / ".claude/skills" / name)
    assert not result.changed
    assert result.owned == []
    locked = {item.path for item in read_lock(git_repo).entries}
    assert {SKILL, ".claude/skills/rs-demo"} <= locked  # kept for when the exclusion ends
    assert all("rs-new" not in path for path in locked)
    report = classify(git_repo, templates_root=new)
    assert report.not_installed == ()
    assert report.strict_ok


def test_sync_never_deletes_an_excluded_file_the_kit_dropped(
    git_repo: Path,
    vendored: Path,
    make_templates: Callable[..., Path],
    write_kit_settings: Callable[..., None],
) -> None:
    write_kit_settings(git_repo, exclude=["tools/devctl"])
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": None})

    result = sync(git_repo, new, in_place=True)

    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert (result.deleted, result.owned) == ([], [])
    assert entry(git_repo, CLI) == before


def test_removing_a_path_from_exclude_restores_normal_handling(
    git_repo: Path,
    vendored: Path,
    make_templates: Callable[..., Path],
    write_kit_settings: Callable[..., None],
) -> None:
    write_kit_settings(git_repo, exclude=["devctl"])
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    assert not sync(git_repo, new, in_place=True).changed
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"

    write_kit_settings(git_repo, exclude=[])
    result = sync(git_repo, new, in_place=True)

    assert result.updated == [
        "devctl"
    ]  # the kept entry still matched the file, so sync replaced it
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"
    assert entry(git_repo, "devctl").sha256 == file_sha256(b"#!/bin/sh\necho newer\n")
