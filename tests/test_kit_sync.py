"""rapid-ship sync with two template versions (offline: the old release and gh are fakes)."""

import errno
import os
import re
import stat
import subprocess

import pytest

from rapid_ship.kit import sync as sync_module
from rapid_ship.kit.init import init_repository
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import (
    Conflict,
    SyncResult,
    pull_request_body,
    push_and_open_pull_request,
    released_templates,
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


@pytest.fixture
def vendored(git_repo, make_templates, kit_variables, commit_all):
    old = make_templates("old")
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    commit_all(git_repo, "Add the Kit")
    return old


def sync(root, new, old, **options):
    return sync_repository(
        root, templates_root=new, kit_version="9.9.9", old_templates=lambda version: old, **options
    )


def entry(root, path):
    return {item.path: item for item in read_lock(root).entries}[path]


def test_nothing_to_sync_creates_no_branch(git_repo, vendored, run_git):
    pulls = PullRequests()

    result = sync(git_repo, vendored, vendored, in_place=False, open_pull_request=pulls)

    assert not result.changed and pulls.calls == []
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"


def test_an_unchanged_file_is_replaced_on_a_sync_branch_and_keeps_its_mode(
    git_repo, vendored, make_templates, run_git
):
    mode = stat.S_IMODE((git_repo / "devctl").stat().st_mode)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    pulls = PullRequests()

    result = sync(git_repo, new, vendored, in_place=False, open_pull_request=pulls)

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


def test_a_local_edit_merges_cleanly_and_the_lock_keeps_the_template_hash(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})
    asked = []

    result = sync_repository(
        git_repo,
        in_place=True,
        templates_root=new,
        kit_version="9.9.9",
        old_templates=lambda version: asked.append(version) or vendored,
    )

    assert result.merged == [CLI]
    assert asked == [installed_version()]
    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nFIVE\n"
    assert entry(git_repo, CLI).sha256 == file_sha256(b"one\ntwo\nthree\nfour\nFIVE\n")
    report = classify(git_repo, templates_root=new)
    assert {item.path: item.state for item in report.files}[CLI] == "modified"
    assert CLI not in report.outdated


def test_a_conflicting_merge_leaves_the_file_and_its_entry(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("one\ntwo\nthree\nfour\nlocal five\n")
    commit_all(git_repo)
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    [conflict] = result.conflicts
    assert conflict.path == CLI
    assert "-five" in conflict.diff and "+FIVE" in conflict.diff
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nlocal five\n"
    assert entry(git_repo, CLI) == before


def test_sync_never_touches_seeded_or_project_files(git_repo, vendored, make_templates, commit_all):
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    (git_repo / "docs").mkdir()
    (git_repo / "docs/guide.md").write_text("mine\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/AGENTS.md": "# {{project_name}}\n\nNew.\n", "common/docs/guide.md": "Kit\n"}
    )

    result = sync(git_repo, new, vendored, in_place=True)

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

    result = sync(git_repo, new, vendored, in_place=True)

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

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.deleted == [CLI]
    assert not (git_repo / "tools").exists()
    assert result.released == ["devctl"]
    assert (git_repo / "devctl").read_text() == "ours\n"
    assert {"devctl", CLI}.isdisjoint(item.path for item in read_lock(git_repo).entries)


def test_a_dropped_file_that_is_already_gone_is_committed_as_a_lock_change(
    git_repo, vendored, make_templates, commit_all, run_git
):
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    pulls = PullRequests()

    result = sync(
        git_repo,
        make_templates("new", {"common/devctl": None}),
        vendored,
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

    result = sync(git_repo, make_templates("new", {"kit.toml": manifest}), vendored, in_place=True)

    assert (result.deleted, result.released, result.seeded_existing) == ([], [CLI], [CLI])
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert entry(git_repo, CLI).kind == "seeded"


def test_opting_in_to_an_optional_skill_adds_it(git_repo, vendored):
    (git_repo / ".rapid-ship/project.toml").write_text(
        'stack = "python"\n\n[kit]\noptional = ["rs-extra"]\n'
    )

    result = sync(git_repo, vendored, vendored, in_place=True)

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
        sync(git_repo, new, vendored, in_place=in_place, open_pull_request=pulls)
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


def test_old_templates_come_from_the_version_tag(make_templates, monkeypatch):
    old = make_templates("cache/rapid_ship/templates")
    commands = []

    def fake_run(command, **options):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=f"{old.parent}\n", stderr="")

    monkeypatch.setattr(sync_module.subprocess, "run", fake_run)

    assert released_templates("0.2.0") == old
    assert commands[0][:3] == [
        "uvx",
        "--from",
        "git+https://github.com/proxy-hatch/rapid-ship@v0.2.0",
    ]
    with pytest.raises(KitError, match="is not a release version"):
        released_templates("main --index-url https://example.invalid")
    assert len(commands) == 1


def test_an_unavailable_base_turns_merges_into_conflicts_and_applies_the_rest(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/devctl": "#!/bin/sh\necho newer\n", f"common/{CLI}": "changed\n"}
    )

    def offline(version):
        raise KitError(f"cannot fetch rapid-ship {version}: offline")

    result = sync_repository(
        git_repo, in_place=True, templates_root=new, kit_version="9.9.9", old_templates=offline
    )

    assert result.updated == ["devctl"]
    assert [(c.path, "offline" in c.reason) for c in result.conflicts] == [(CLI, True)]


def test_a_locked_copy_that_is_not_the_old_template_has_no_merge_base(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    other = make_templates("other", {f"common/{CLI}": "not the locked template\n"})
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, other, in_place=True)

    assert [c.path for c in result.conflicts] == [CLI]
    assert "no merge base" in result.conflicts[0].reason


def test_an_edited_binary_file_is_a_conflict_and_the_rest_applies(
    git_repo, make_templates, kit_variables, commit_all
):
    path = "tools/devctl/logo.bin"
    old = make_templates("old", {f"common/{path}": "a\0base\n"})
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    (git_repo / path).write_bytes(b"a\0local\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {f"common/{path}": "a\0new\n", "common/devctl": "#!/bin/sh\necho newer\n"}
    )

    result = sync(git_repo, new, old, in_place=True)

    assert result.updated == ["devctl"]
    assert [(c.path, "binary" in c.reason) for c in result.conflicts] == [(path, True)]
    assert (git_repo / path).read_bytes() == b"a\0local\n"


def test_in_place_accepts_a_dirty_tree_and_commits_nothing(
    git_repo, vendored, make_templates, run_git
):
    (git_repo / "notes.md").write_text("draft\n")
    head = run_git(git_repo, "rev-parse", "HEAD")
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == ["devctl"] and result.branch is None
    assert run_git(git_repo, "rev-parse", "HEAD") == head
    assert (git_repo / "notes.md").read_text() == "draft\n"


def test_branch_mode_refuses_a_dirty_tree_an_existing_branch_or_a_detached_head(
    git_repo, vendored, make_templates, run_git
):
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    (git_repo / "notes.md").write_text("draft\n")
    with pytest.raises(KitRefusal, match="the work tree has changes"):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
    (git_repo / "notes.md").unlink()

    run_git(git_repo, "branch", "rapid-ship/kit-sync-9.9.9")
    with pytest.raises(KitRefusal, match=re.escape("gh pr list --head rapid-ship/kit-sync-9.9.9")):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
    run_git(git_repo, "branch", "-D", "rapid-ship/kit-sync-9.9.9")

    run_git(git_repo, "switch", "-q", "--detach")
    with pytest.raises(KitRefusal, match="HEAD is detached"):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
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
        old_templates=lambda version: vendored,
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


def test_the_pull_request_body_cuts_diffs_but_never_the_evidence():
    diff = "\n".join(f"+line {number}" for number in range(300))
    result = SyncResult(
        kit_version="9.9.9",
        updated=["devctl"],
        seeded_changed=["AGENTS.md"],
        conflicts=[Conflict(CLI, "local changes conflict", diff)],
    )

    body = pull_request_body(result, "0.1.0")

    owner = body.split("\n## Needs the owner\n", 1)[1].split("\n## Evidence\n", 1)[0]
    assert "make the file equal the new template" in owner and "`[kit] exclude`" in owner
    assert "+line 199\n[diff cut at 200 lines]\n```" in owner
    assert "+line 200" not in owner
    assert (
        "- `rapid-ship sync`: rapid-ship 0.1.0 to 9.9.9; 1 updated, 1 seeded changed, 1 conflicts"
        in body.splitlines()
    )

    wide = "\n".join("+" + "x" * 99 for _ in range(200))
    many = [Conflict(f"file{number}", "conflict", wide) for number in range(5)]

    body = pull_request_body(SyncResult(kit_version="9.9.9", conflicts=many), "0.1.0")

    assert len(body) <= 60_000
    assert body.count("[diff cut to fit the pull request body]") == 5
    assert body.endswith(
        "- `rapid-ship sync`: rapid-ship 0.1.0 to 9.9.9; 5 conflicts\n\n"
        "Not covered: sync did not run ./devctl check; CI runs it on this pull request.\n"
    )


# Owner groups (spec section 3, "Who owns what"): stack Kit, language-agnostic Kit and
# project extensions.


def test_sync_keeps_the_stack_version_over_the_common_one(
    git_repo, make_templates, kit_variables, commit_all
):
    path = "tools/devctl/devctl/stack.py"
    layers = {f"common/{path}": "common\n", f"python/{path}": "python\n"}
    old = make_templates("old", layers)
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    commit_all(git_repo)

    common_only = sync(
        git_repo,
        make_templates("common", {**layers, f"common/{path}": "common, revised\n"}),
        old,
        in_place=True,
    )
    stack = sync(
        git_repo,
        make_templates("stack", {**layers, f"python/{path}": "python, revised\n"}),
        old,
        in_place=True,
    )

    assert not common_only.changed
    assert stack.updated == [path]
    assert (git_repo / path).read_text() == "python, revised\n"


def test_an_edited_kit_skill_is_merged_and_keeps_its_link(
    git_repo, make_templates, kit_variables, commit_all
):
    old = make_templates("old", {f"common/{SKILL}": "one\ntwo\nthree\nfour\nfive\n"})
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    (git_repo / SKILL).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates("new", {f"common/{SKILL}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, old, in_place=True)

    assert result.merged == [SKILL]
    assert (git_repo / SKILL).read_text() == "ONE\ntwo\nthree\nfour\nFIVE\n"
    assert os.readlink(git_repo / ".claude/skills/rs-demo") == "../../.agents/skills/rs-demo"


def test_a_modified_devctl_project_survives_sync(
    git_repo, make_templates, kit_variables, commit_all
):
    seed = '"""Project verbs."""\n\n\ndef register(commands):\n    pass\n'
    old = make_templates("old", {f"common/{PROJECT_HOOKS}": seed})
    manifest = (
        (old / "kit.toml").read_text().replace('"AGENTS.md"]', f'"AGENTS.md", "{PROJECT_HOOKS}"]')
    )
    (old / "kit.toml").write_text(manifest)
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    ours = seed.replace("    pass\n", '    commands.add_parser("seed-demo")\n')
    (git_repo / PROJECT_HOOKS).write_text(ours)
    (git_repo / "tools/devctl/devctl_project/verbs.py").write_text("VERBS = []\n")
    commit_all(git_repo)
    newer_seed = seed + "\n\ndef check_steps():\n    return []\n"
    new = make_templates(
        "new",
        {"kit.toml": manifest, f"common/{PROJECT_HOOKS}": newer_seed, f"common/{CLI}": "changed\n"},
    )

    result = sync(git_repo, new, old, in_place=True)

    assert (result.updated, result.seeded_changed) == ([CLI], [PROJECT_HOOKS])
    assert (git_repo / PROJECT_HOOKS).read_text() == ours
    assert (git_repo / "tools/devctl/devctl_project/verbs.py").read_text() == "VERBS = []\n"


def test_a_project_skill_and_its_link_survive_sync(
    git_repo, vendored, make_templates, commit_all, run_git
):
    (git_repo / ".agents/skills/our-release").mkdir()
    (git_repo / ".agents/skills/our-release/SKILL.md").write_text(
        "---\nname: our-release\ndescription: Ship it.\n---\n"
    )
    (git_repo / ".claude/skills/our-release").symlink_to("../../.agents/skills/our-release")
    commit_all(git_repo)
    new = make_templates(
        "new",
        {f"common/{SKILL}": "demo, revised\n", "common/.agents/skills/rs-new/SKILL.md": "new\n"},
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == [SKILL]
    assert result.added == [".agents/skills/rs-new/SKILL.md", ".claude/skills/rs-new"]
    assert (
        run_git(
            git_repo,
            "status",
            "--porcelain",
            "--",
            ".agents/skills/our-release",
            ".claude/skills/our-release",
        )
        == ""
    )
    assert all("our-release" not in item.path for item in read_lock(git_repo).entries)
    assert all(
        "our-release" not in item.path for item in classify(git_repo, templates_root=new).files
    )


def test_a_project_workflow_survives_beside_a_new_kit_workflow(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / ".github/workflows").mkdir()
    (git_repo / ".github/workflows/release.yml").write_text("name: release\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/.github/workflows/devctl-check.yml": "name: devctl check\n"}
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.added == [".github/workflows/devctl-check.yml"]
    assert (git_repo / ".github/workflows/release.yml").read_text() == "name: release\n"
    assert ".github/workflows/release.yml" not in {
        item.path for item in read_lock(git_repo).entries
    }


# Project overrides: [kit] exclude.


def test_an_excluded_file_the_project_edited_is_not_merged(
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
    write_kit_settings(git_repo, exclude=[CLI])
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nfive\n"
    assert (result.merged, result.conflicts) == ([], [])
    assert entry(git_repo, CLI) == before  # the lock records no exclusion


def test_a_deleted_excluded_file_stays_deleted(
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert not os.path.lexists(git_repo / "devctl")
    assert not result.changed and result.missing == []
    assert (git_repo / LOCK_PATH).read_bytes() == lock  # the kit_version stays too
    report = classify(git_repo, templates_root=new)
    assert {item.path: item.state for item in report.files}["devctl"] == "excluded"
    assert report.strict_ok


def test_an_excluded_skill_directory_covers_its_link(
    git_repo, vendored, make_templates, commit_all, run_git, write_kit_settings
):
    write_kit_settings(git_repo, exclude=[".agents/skills/rs-demo", ".agents/skills/rs-new"])
    run_git(git_repo, "rm", "-q", "-r", ".agents/skills/rs-demo", ".claude/skills/rs-demo")
    commit_all(git_repo)
    new = make_templates(
        "new",
        {f"common/{SKILL}": "demo, revised\n", "common/.agents/skills/rs-new/SKILL.md": "new\n"},
    )

    result = sync(git_repo, new, vendored, in_place=True)

    for name in ("rs-demo", "rs-new"):
        assert not os.path.lexists(git_repo / ".agents/skills" / name)
        assert not os.path.lexists(git_repo / ".claude/skills" / name)
    assert not result.changed and result.missing == []
    locked = {item.path for item in read_lock(git_repo).entries}
    assert {SKILL, ".claude/skills/rs-demo"} <= locked  # kept for when the exclusion ends
    assert all("rs-new" not in path for path in locked)
    report = classify(git_repo, templates_root=new)
    assert report.not_installed == () and report.strict_ok


def test_sync_never_deletes_an_excluded_file_the_kit_dropped(
    git_repo, vendored, make_templates, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["tools/devctl"])
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": None})

    result = sync(git_repo, new, vendored, in_place=True)

    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert (result.deleted, result.released) == ([], [])
    assert entry(git_repo, CLI) == before


def test_removing_a_path_from_exclude_restores_normal_handling(
    git_repo, vendored, make_templates, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["devctl"])
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    assert not sync(git_repo, new, vendored, in_place=True).changed
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"

    write_kit_settings(git_repo, exclude=[])
    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == [
        "devctl"
    ]  # the kept entry still matched the file, so sync replaced it
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"
    assert entry(git_repo, "devctl").sha256 == file_sha256(b"#!/bin/sh\necho newer\n")
