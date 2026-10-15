"""init and sync run no git hook, and undo a branch switch that git reports as failed (offline)."""

import pytest

from rapid_ship.kit import init as init_module
from rapid_ship.kit import sync as sync_module
from rapid_ship.kit.init import init_repository
from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import KitError

INIT_BRANCH = "rapid-ship/init"
SYNC_BRANCH = "rapid-ship/kit-sync-9.9.9"
# Every hook that git status, add, commit, branch, switch or reset can run.
HOOKS = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "post-checkout",
    "reference-transaction",
    "post-index-change",
)


def track_failing_hooks(root, log, commit_all, run_git):
    """Commit .githooks/ and make it the hooks path, as husky does. Each hook notes its name in
    log and fails."""
    hooks = root / ".githooks"
    hooks.mkdir()
    for name in HOOKS:
        hook = hooks / name
        hook.write_text(f'#!/bin/sh\necho {name} >> "{log}"\nexit 1\n')
        hook.chmod(0o755)
    commit_all(root, "Add hooks")  # git_repo's own hooks path is /dev/null, so none runs here
    run_git(root, "config", "core.hooksPath", ".githooks")


def open_nothing(root, branch, base, title, body):
    return "https://github.com/octo/demo-app/pull/1"


def test_init_runs_no_hook_from_a_tracked_hooks_path(
    git_repo, make_templates, kit_variables, commit_all, run_git, tmp_path
):
    log = tmp_path / "hooks.log"
    track_failing_hooks(git_repo, log, commit_all, run_git)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert not log.exists()  # checked first: the test's own git calls below may run hooks
    assert result.branch == INIT_BRANCH
    assert run_git(git_repo, "rev-parse", INIT_BRANCH).strip() == result.commit


def test_init_lists_a_tracked_hooks_path_and_its_hooks_without_running_them(
    git_repo, make_templates, kit_variables, commit_all, run_git, tmp_path
):
    log = tmp_path / "hooks.log"
    track_failing_hooks(git_repo, log, commit_all, run_git)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert not log.exists()  # checked first: the test's own git calls below may run hooks
    assert result.existing_checks == (
        ".githooks (core.hooksPath)",
        *(f".githooks/{name}" for name in sorted(HOOKS)),
    )


def test_sync_runs_no_hook_from_a_tracked_hooks_path(
    git_repo, vendored, make_templates, commit_all, run_git, tmp_path
):
    log = tmp_path / "hooks.log"
    track_failing_hooks(git_repo, log, commit_all, run_git)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync_repository(
        git_repo,
        in_place=False,
        templates_root=new,
        kit_version="9.9.9",
        open_pull_request=open_nothing,
    )

    assert not log.exists()
    assert (result.branch, result.updated) == (SYNC_BRANCH, ["devctl"])


def failing_switch(monkeypatch, module, *, switched):
    """Make module's git switch fail. With switched, git switches first and then fails, as it
    does when a post-checkout hook fails."""
    real_git = module.git

    def git(root, *args, **options):
        if args[0] == "switch":
            if switched:
                real_git(root, *args, **options)
            raise KitError("git switch failed: exit status 1")
        return real_git(root, *args, **options)

    monkeypatch.setattr(module, "git", git)


@pytest.mark.parametrize("switched", [True, False])
def test_a_failed_switch_to_the_init_branch_restores_the_start(
    git_repo, make_templates, kit_variables, commit_all, run_git, monkeypatch, switched
):
    commit_all(git_repo, "Start")
    head = run_git(git_repo, "rev-parse", "HEAD")
    failing_switch(monkeypatch, init_module, switched=switched)

    with pytest.raises(KitError) as stopped:
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )

    assert str(stopped.value) == (
        "init stopped (git switch failed: exit status 1) and removed the files it had created; "
        f"back on main, {INIT_BRANCH} deleted"
    )
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    assert run_git(git_repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert run_git(git_repo, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("switched", [True, False])
def test_a_failed_switch_to_the_sync_branch_restores_the_start(
    git_repo, vendored, make_templates, run_git, monkeypatch, switched
):
    head = run_git(git_repo, "rev-parse", "HEAD")
    failing_switch(monkeypatch, sync_module, switched=switched)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    with pytest.raises(KitError) as stopped:
        sync_repository(
            git_repo,
            in_place=False,
            templates_root=new,
            kit_version="9.9.9",
            open_pull_request=open_nothing,
        )

    assert str(stopped.value) == (
        "sync stopped (git switch failed: exit status 1) and restored the files it had changed; "
        f"back on main, {SYNC_BRANCH} deleted"
    )
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    assert run_git(git_repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert run_git(git_repo, "rev-parse", "HEAD") == head
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"
