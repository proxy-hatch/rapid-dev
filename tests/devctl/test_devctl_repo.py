"""devctl's view of its git repository, in scratch repositories (offline)."""

import pytest

from devctl.repo import Repo, RepoError


def test_discover_finds_the_root_and_common_dir_from_a_subdirectory(git_repo):
    (git_repo / "sub").mkdir()

    repo = Repo.discover(git_repo / "sub")

    assert repo.root == git_repo.resolve()
    assert repo.git_common_dir == (git_repo / ".git").resolve()


def test_a_worktree_shares_the_main_common_dir(git_repo, commit_all, run_git):
    commit_all(git_repo)
    run_git(git_repo, "worktree", "add", "-q", str(git_repo.parent / "wt"), "-b", "other")

    assert Repo.discover(git_repo.parent / "wt").git_common_dir == (git_repo / ".git").resolve()


def test_tracked_files_lists_only_tracked_paths(git_repo, commit_all):
    (git_repo / "a file.txt").write_text("x\n")
    commit_all(git_repo)
    (git_repo / "untracked.txt").write_text("y\n")

    assert Repo.discover(git_repo).tracked_files() == ["a file.txt"]


def test_merge_base_returns_the_shared_commit_or_none(git_repo, commit_all, run_git):
    commit_all(git_repo, "first")
    first = run_git(git_repo, "rev-parse", "HEAD").strip()
    run_git(git_repo, "switch", "-q", "-c", "feature")
    commit_all(git_repo, "second")
    repo = Repo.discover(git_repo)
    assert repo.merge_base("main") == first

    run_git(git_repo, "switch", "-q", "--orphan", "lonely")
    commit_all(git_repo, "unrelated")
    assert repo.merge_base("main") is None
    with pytest.raises(RepoError, match="merge-base"):
        repo.merge_base("no-such-ref")


def test_outside_a_work_tree_is_a_repo_error(tmp_path):
    with pytest.raises(RepoError):
        Repo.discover(tmp_path)


def test_a_missing_git_is_a_repo_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "no-such-dir"))

    with pytest.raises(RepoError, match="cannot run git"):
        Repo.discover(tmp_path)
