"""The git calls the Kit commands share, against scratch repositories (offline)."""

from collections.abc import Callable
from pathlib import Path

import pytest

from rapid_ship.kit.git import git, is_clean, work_tree_root
from rapid_ship.kit.templates import KitError, KitRefusal


def test_paths_are_literal_unless_the_caller_turns_that_off(
    git_repo: Path, run_git: Callable[..., str]
) -> None:
    (git_repo / "a.py").write_text("x\n")
    run_git(git_repo, "add", "a.py")

    assert git(git_repo, "ls-files", "-z", "--", "*.py") == b""
    assert git(git_repo, "ls-files", "-z", "--", "*.py", literal=False) == b"a.py\0"


def test_check_ignore_reports_an_ignored_path(git_repo: Path) -> None:
    # check-ignore refuses --literal-pathspecs, so init calls it with literal=False and the
    # paths on stdin, where git reads them literally anyway.
    (git_repo / ".gitignore").write_text("*.local\n")

    ignored = git(
        git_repo,
        "check-ignore",
        "-z",
        "--stdin",
        stdin=b"scratch.local\0kept.txt",
        literal=False,
        allowed=(0, 1),
    )
    none_ignored = git(
        git_repo, "check-ignore", "-z", "--stdin", stdin=b"kept.txt", literal=False, allowed=(0, 1)
    )

    assert ignored == b"scratch.local\0"
    assert none_ignored == b""


def test_a_git_failure_is_a_kit_error_unless_its_exit_code_is_allowed(git_repo: Path) -> None:
    with pytest.raises(KitError, match="git rev-parse failed"):
        git(git_repo, "rev-parse", "--verify", "no-such-revision")

    assert git(git_repo, "ls-files", "--error-unmatch", "nothing", allowed=(0, 1)) == b""


def test_a_failure_that_prints_nothing_names_its_exit_status(git_repo: Path) -> None:
    with pytest.raises(KitError, match=r"^git rev-parse failed: exit status 1$"):
        git(git_repo, "rev-parse", "--verify", "--quiet", "no-such-revision")


def test_git_runs_no_hook_even_when_the_repository_sets_one(
    git_repo: Path, tmp_path: Path, run_git: Callable[..., str]
) -> None:
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    log = tmp_path / "hooks.log"
    for name in ("pre-commit", "post-commit", "reference-transaction"):
        (hooks / name).write_text(f'#!/bin/sh\necho {name} >> "{log}"\nexit 1\n')
        (hooks / name).chmod(0o755)
    run_git(git_repo, "config", "core.hooksPath", str(hooks))

    git(git_repo, "commit", "--quiet", "--allow-empty", "--message", "Start")

    assert not log.exists()


def test_work_tree_root_names_the_repository_from_inside_it(git_repo: Path) -> None:
    (git_repo / "sub").mkdir()

    assert work_tree_root(git_repo / "sub") == git_repo.resolve()


def test_work_tree_root_refuses_a_directory_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    (tmp_path / "plain").mkdir()

    with pytest.raises(KitRefusal, match="is not inside a git work tree"):
        work_tree_root(tmp_path / "plain")


def test_a_work_tree_is_clean_until_a_file_is_added_or_changed(
    git_repo: Path, commit_all: Callable[..., None]
) -> None:
    assert is_clean(git_repo)

    (git_repo / "a.txt").write_text("one\n")
    assert not is_clean(git_repo)  # untracked files count

    commit_all(git_repo)
    assert is_clean(git_repo)

    (git_repo / "a.txt").write_text("two\n")
    assert not is_clean(git_repo)
