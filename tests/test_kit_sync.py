"""rapid-ship sync with two template versions (offline: gh is a fake)."""

import errno
import os
import re
import stat

import pytest

from rapid_ship.kit import git as git_module
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import (
    Conflict,
    SyncResult,
    pull_request_body,
    push_and_open_pull_request,
    sync_repository,
)
from rapid_ship.kit.templates import KitError, KitRefusal, installed_version

CLI = "tools/devctl/devctl/cli.py"
SKILL = ".agents/skills/rs-demo/SKILL.md"
PROJECT_HOOKS = "tools/devctl/devctl_project/__init__.py"


class PullRequests:
    def __init__(self):
        self.calls = []

    def __call__(self, root, branch, base, title, body):
        self.calls.append((branch, base, title, body))
        return "https://github.com/octo/demo-app/pull/1"


def sync(root, new, **options):
    return sync_repository(root, templates_root=new, kit_version="9.9.9", **options)


def entry(root, path):
    return {item.path: item for item in read_lock(root).entries}[path]


def test_nothing_to_sync_creates_no_branch(git_repo, vendored, run_git):
    pulls = PullRequests()

    result = sync(git_repo, vendored, in_place=False, open_pull_request=pulls)

    assert not result.changed and pulls.calls == []
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"


def test_an_unchanged_file_is_replaced_on_a_sync_branch_and_keeps_its_mode(
    git_repo, vendored, make_templates, run_git
):
    mode = stat.S_IMODE((git_repo / "devctl").stat().st_mode)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    pulls = PullRequests()

    result = sync(git_repo, new, in_place=False, open_pull_request=pulls)

    assert result.updated == ["devctl"]
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"
    assert (
        stat.S_IMODE((git_repo / "devctl").stat().st_mode) == mode
    )  # atomic_replace alone leaves 0o600
    assert run_git(git_repo, "branch", "--show-current").strip() == "rapid-ship/kit-sync-9.9.9"
    assert (
        run_git(git_repo, "log", "-1", "--format=%s").strip()
        == "chore: sync rapid-ship Kit to 9.9.9"
    )
    assert run_git(git_repo, "status", "--porcelain") == ""
    [(branch, base, title, body)] = pulls.calls
    assert (branch, base, title) == (
        "rapid-ship/kit-sync-9.9.9",
        "main",
        "Sync rapid-ship Kit to 9.9.9",
    )
    evidence = body.split("\n## Evidence\n", 1)[1]
    # Plan 3's evidence step needs a "- `<command>`: <result>" item and a "Not covered:" line.
    assert re.search(r"^- `[^`]+`: \S", evidence, flags=re.MULTILINE)
    assert (
        f"- `rapid-ship sync`: rapid-ship {installed_version()} to 9.9.9; 1 updated"
        in evidence.splitlines()
    )
    assert "\nNot covered:" in evidence
    assert read_lock(git_repo).kit_version == "9.9.9"
    assert classify(git_repo, templates_root=new).strict_ok


def test_sync_never_touches_seeded_or_project_files(git_repo, vendored, make_templates, commit_all):
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    (git_repo / "docs").mkdir()
    (git_repo / "docs/guide.md").write_text("mine\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/AGENTS.md": "# {{project_name}}\n\nNew.\n", "common/docs/guide.md": "Kit\n"}
    )

    result = sync(git_repo, new, in_place=True)

    assert (git_repo / "AGENTS.md").read_text() == "# Ours\n"
    assert (git_repo / "docs/guide.md").read_text() == "mine\n"
    assert result.seeded_changed == ["AGENTS.md"]
    assert [conflict.path for conflict in result.conflicts] == ["docs/guide.md"]
    assert entry(git_repo, "AGENTS.md").template_sha256 == file_sha256(b"# demo-app\n\nNew.\n")
    assert "docs/guide.md" not in {item.path for item in read_lock(git_repo).entries}


def test_new_seeded_templates_are_created_only_where_absent(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / "README.md").write_text("ours\n")
    commit_all(git_repo)
    manifest = (
        (vendored / "kit.toml")
        .read_text()
        .replace('"AGENTS.md"]', '"AGENTS.md", "CONTRIBUTING.md", "README.md"]')
        .replace(
            '"src/__package__/__init__.py"]', '"src/__package__/__init__.py", "tests/test_new.py"]'
        )
    )
    new = make_templates(
        "new",
        {
            "kit.toml": manifest,
            "common/CONTRIBUTING.md": "# {{project_name}}\n",
            "common/README.md": "Kit\n",
            "python/tests/test_new.py": "x = 1\n",
        },
    )

    result = sync(git_repo, new, in_place=True)

    assert result.added == ["CONTRIBUTING.md"]
    assert result.seeded_existing == ["README.md"]
    assert (git_repo / "CONTRIBUTING.md").read_text() == "# demo-app\n"
    assert (git_repo / "README.md").read_text() == "ours\n"
    assert not (git_repo / "tests/test_new.py").exists()  # a new-project seed
    assert "tests/test_new.py" not in {item.path for item in read_lock(git_repo).entries}


def test_dropped_files_are_deleted_only_when_unchanged(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / "devctl").write_text("ours\n")
    commit_all(git_repo)
    new = make_templates("new", {"common/devctl": None, f"common/{CLI}": None})

    result = sync(git_repo, new, in_place=True)

    assert result.deleted == [CLI]
    assert not (git_repo / "tools").exists()
    assert CLI not in {item.path for item in read_lock(git_repo).entries}
    # The edited file is the project's own now. Its entry keeps the template it came from.
    assert result.owned == ["devctl"]
    assert (git_repo / "devctl").read_text() == "ours\n"
    owned = entry(git_repo, "devctl")
    assert (owned.kind, owned.template_sha256) == (
        "seeded",
        file_sha256(b"#!/bin/sh\necho devctl\n"),
    )


def test_a_dropped_file_that_is_already_gone_is_committed_as_a_lock_change(
    git_repo, vendored, make_templates, commit_all, run_git
):
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    pulls = PullRequests()

    result = sync(
        git_repo,
        make_templates("new", {"common/devctl": None}),
        in_place=False,
        open_pull_request=pulls,
    )

    assert result.deleted == ["devctl"]
    assert "devctl" not in {item.path for item in read_lock(git_repo).entries}
    assert run_git(git_repo, "status", "--porcelain") == ""
    assert len(pulls.calls) == 1


def test_a_managed_file_the_kit_now_seeds_is_kept_for_the_project(
    git_repo, vendored, make_templates
):
    manifest = (vendored / "kit.toml").read_text().replace('"AGENTS.md"]', f'"AGENTS.md", "{CLI}"]')

    result = sync(git_repo, make_templates("new", {"kit.toml": manifest}), in_place=True)

    assert (result.deleted, result.owned, result.seeded_existing) == ([], [], [CLI])
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert entry(git_repo, CLI).kind == "seeded"


def test_opting_in_to_an_optional_skill_adds_it(git_repo, vendored):
    (git_repo / ".rapid-ship/project.toml").write_text(
        'stack = "python"\n\n[kit]\noptional = ["rs-extra"]\n'
    )

    result = sync(git_repo, vendored, in_place=True)

    assert result.added == [".agents/skills/rs-extra/SKILL.md", ".claude/skills/rs-extra"]
    assert os.readlink(git_repo / ".claude/skills/rs-extra") == "../../.agents/skills/rs-extra"


@pytest.mark.parametrize("in_place", [True, False])
def test_a_refused_symlink_leaves_nothing_half_written(
    git_repo, vendored, make_templates, commit_all, run_git, monkeypatch, in_place
):
    (git_repo / ".rapid-ship/project.toml").write_text(
        'stack = "python"\n\n[kit]\noptional = ["rs-extra"]\n'
    )
    commit_all(git_repo)
    skill = git_repo / ".agents/skills/rs-demo/SKILL.md"
    mode = stat.S_IMODE(skill.stat().st_mode)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/.agents/skills/rs-demo/SKILL.md": "demo, revised\n"})
    pulls = PullRequests()

    def refuse(target, path, *rest):  # Path.symlink_to also passes target_is_directory
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr("os.symlink", refuse)

    with pytest.raises(KitError, match=r"sync stopped .*Operation not permitted.*restored"):
        sync(git_repo, new, in_place=in_place, open_pull_request=pulls)
    # In path order, sync replaced rs-demo's SKILL.md and created rs-extra's before the link failed.
    assert skill.read_text() == "demo\n"
    assert stat.S_IMODE(skill.stat().st_mode) == mode
    assert not os.path.lexists(git_repo / ".agents/skills/rs-extra")
    assert not os.path.lexists(git_repo / ".claude/skills/rs-extra")
    assert (git_repo / LOCK_PATH).read_bytes() == lock
    assert run_git(git_repo, "status", "--porcelain") == ""
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    assert pulls.calls == []


@pytest.mark.parametrize("cause", ["signing", "ignored path"])
def test_a_failed_commit_restores_the_tree_and_deletes_the_sync_branch(
    git_repo, vendored, make_templates, commit_all, run_git, cause
):
    added = "tools/devctl/extra/note.md"
    if cause == "signing":
        run_git(git_repo, "config", "commit.gpgsign", "true")
        run_git(git_repo, "config", "gpg.program", "false")
        expected = "gpg failed to sign"
    else:  # git add stages the other paths, then exits 1
        (git_repo / ".gitignore").write_text("/tools/devctl/extra/\n")
        commit_all(git_repo)
        expected = "ignored"
    mode = stat.S_IMODE((git_repo / "devctl").stat().st_mode)
    lock = (git_repo / LOCK_PATH).read_bytes()
    head = run_git(git_repo, "rev-parse", "HEAD")
    new = make_templates(
        "new",
        {
            "common/devctl": "#!/bin/sh\necho newer\n",
            f"common/{CLI}": None,
            f"common/{added}": "x\n",
        },
    )
    pulls = PullRequests()

    with pytest.raises(KitError) as stopped:
        sync(git_repo, new, in_place=False, open_pull_request=pulls)

    message = str(stopped.value)
    assert message.startswith("sync stopped (git ") and expected in message
    assert message.endswith("back on main, rapid-ship/kit-sync-9.9.9 deleted")
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"
    assert stat.S_IMODE((git_repo / "devctl").stat().st_mode) == mode
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert not (git_repo / "tools/devctl/extra").exists()
    assert (git_repo / LOCK_PATH).read_bytes() == lock
    assert run_git(git_repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    assert run_git(git_repo, "rev-parse", "HEAD") == head
    assert pulls.calls == []


def test_a_stop_that_cannot_switch_back_names_the_branch_and_the_way_back(
    git_repo, vendored, make_templates, run_git, monkeypatch
):
    real_git = git_module.git

    def refusing(root, *args, **options):
        if args[0] == "commit" or args == ("switch", "--quiet", "main"):
            raise KitError(f"git {args[0]} failed: refused")
        return real_git(root, *args, **options)

    # commit_paths and leave_branch in git.py make these calls.
    monkeypatch.setattr(git_module, "git", refusing)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    with pytest.raises(KitError) as stopped:
        sync(git_repo, new, in_place=False, open_pull_request=PullRequests())

    branch = "rapid-ship/kit-sync-9.9.9"
    assert str(stopped.value) == (
        "sync stopped (git commit failed: refused) and restored the files it had changed, "
        f"but could not go back (git switch failed: refused); you are on {branch}; "
        f"run git reset, git switch main and git branch -D {branch}"
    )
    assert run_git(git_repo, "branch", "--show-current").strip() == branch
    assert run_git(git_repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_in_place_accepts_a_dirty_tree_and_commits_nothing(
    git_repo, vendored, make_templates, run_git
):
    (git_repo / "notes.md").write_text("draft\n")
    head = run_git(git_repo, "rev-parse", "HEAD")
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, in_place=True)

    assert result.updated == ["devctl"] and result.branch is None
    assert run_git(git_repo, "rev-parse", "HEAD") == head
    assert (git_repo / "notes.md").read_text() == "draft\n"


def test_branch_mode_refuses_a_dirty_tree_an_existing_branch_or_a_detached_head(
    git_repo, vendored, make_templates, run_git
):
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    (git_repo / "notes.md").write_text("draft\n")
    with pytest.raises(KitRefusal, match="the work tree has changes"):
        sync(git_repo, new, in_place=False, open_pull_request=PullRequests())
    (git_repo / "notes.md").unlink()

    run_git(git_repo, "branch", "rapid-ship/kit-sync-9.9.9")
    with pytest.raises(KitRefusal, match=re.escape("gh pr list --head rapid-ship/kit-sync-9.9.9")):
        sync(git_repo, new, in_place=False, open_pull_request=PullRequests())
    run_git(git_repo, "branch", "-D", "rapid-ship/kit-sync-9.9.9")

    run_git(git_repo, "switch", "-q", "--detach")
    with pytest.raises(KitRefusal, match="HEAD is detached"):
        sync(git_repo, new, in_place=False, open_pull_request=PullRequests())
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"


def fake_gh(tmp_path, monkeypatch, script):
    """Put a gh stand-in first on PATH. It records its arguments and body beside itself."""
    directory = tmp_path / "bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "$0.args"\ncat > "$0.body"\n{script}\n')
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return gh


def test_the_branch_is_pushed_before_gh_opens_the_pull_request(
    git_repo, vendored, make_templates, run_git, tmp_path, monkeypatch, capsys
):
    origin = tmp_path / "origin.git"
    run_git(tmp_path, "init", "-q", "--bare", str(origin))
    run_git(git_repo, "remote", "add", "origin", str(origin))
    gh = fake_gh(
        tmp_path, monkeypatch, "echo Creating; echo https://github.com/octo/demo-app/pull/7"
    )
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync_repository(
        git_repo,
        in_place=False,
        templates_root=new,
        kit_version="9.9.9",
    )

    assert result.pull_request == "https://github.com/octo/demo-app/pull/7"
    branch = "rapid-ship/kit-sync-9.9.9"
    assert run_git(origin, "log", "-1", "--format=%s", branch).strip() == (
        "chore: sync rapid-ship Kit to 9.9.9"
    )
    assert gh.with_name("gh.args").read_text().splitlines() == [
        *("pr", "create", "--base", "main", "--head", branch),
        *("--title", "Sync rapid-ship Kit to 9.9.9", "--body-file", "-"),
    ]
    assert gh.with_name("gh.body").read_text().endswith("CI runs it on this pull request.\n")
    output = capsys.readouterr().out
    assert output.index(f"Pushing {branch} to origin.") < output.index("Opening a pull request")


def test_a_failed_push_or_gh_says_where_the_commit_is(
    git_repo, vendored, run_git, tmp_path, monkeypatch
):
    branch = "rapid-ship/kit-sync-9.9.9"
    run_git(git_repo, "switch", "-q", "--create", branch)
    gh = fake_gh(tmp_path, monkeypatch, "echo 'HTTP 422' >&2; exit 1")

    with pytest.raises(KitError, match=f"on the local branch {branch}"):
        push_and_open_pull_request(git_repo, branch, "main", "Sync", "body")
    assert not gh.with_name("gh.args").exists()

    origin = tmp_path / "origin.git"
    run_git(tmp_path, "init", "-q", "--bare", str(origin))
    run_git(git_repo, "remote", "add", "origin", str(origin))
    with pytest.raises(
        KitError, match=re.escape(f"is pushed, so check gh pr list --head {branch}")
    ):
        push_and_open_pull_request(git_repo, branch, "main", "Sync", "body")


def test_the_pull_request_body_lists_owned_files_and_the_way_back():
    result = SyncResult(
        kit_version="9.9.9",
        updated=["devctl"],
        owned=[CLI],
        seeded_changed=["AGENTS.md"],
        conflicts=[Conflict("docs/guide.md", "exists and is not managed")],
    )

    body = pull_request_body(result, "0.1.0")

    owner = body.split("\n## Needs the owner\n", 1)[1].split("\n## Evidence\n", 1)[0]
    assert f"- `{CLI}`" in owner and "`rapid-ship sync --revert <path>`" in owner
    assert "Conflicts. sync did not write or record these paths:" in owner
    assert "- `docs/guide.md`: exists and is not managed" in owner
    assert body.endswith(
        "- `rapid-ship sync`: rapid-ship 0.1.0 to 9.9.9; "
        "1 updated, 1 owned, 1 seeded changed, 1 conflicts\n\n"
        "Not covered: sync did not run ./devctl check; CI runs it on this pull request.\n"
    )
