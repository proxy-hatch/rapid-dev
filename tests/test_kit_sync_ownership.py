"""Who owns what during rapid-ship sync (offline): files the project made its own, --revert,
the owner groups and [kit] exclude (spec section 3)."""

import os
import re
import stat

import pytest

from rapid_ship.kit.init import init_repository
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import KitRefusal

CLI = "tools/devctl/devctl/cli.py"
SKILL = ".agents/skills/rs-demo/SKILL.md"
PROJECT_HOOKS = "tools/devctl/devctl_project/__init__.py"


class PullRequests:
    """A stand-in for push_and_open_pull_request that keeps each pull request body."""

    def __init__(self):
        self.bodies = []

    def __call__(self, root, branch, base, title, body):
        self.bodies.append(body)
        return "https://github.com/octo/demo-app/pull/1"


def sync(root, new, **options):
    return sync_repository(root, templates_root=new, kit_version="9.9.9", **options)


def entry(root, path):
    return {item.path: item for item in read_lock(root).entries}[path]


# A managed file the project edited or deleted becomes the project's own (spec section 3, sync
# step 4). sync never changes it, records it as seeded and says how to revert it.

NEW_CLI = "one\ntwo\nthree\nfour\nFIVE\n"


def test_an_edited_file_becomes_the_projects_own_with_the_current_template_hash(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/devctl": "#!/bin/sh\necho newer\n", f"common/{CLI}": NEW_CLI}
    )

    result = sync(git_repo, new, in_place=True)

    assert (result.updated, result.owned, result.conflicts) == (["devctl"], [CLI], [])
    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nfive\n"
    owned = entry(git_repo, CLI)
    assert (owned.kind, owned.sha256, owned.template_sha256) == (
        "seeded",
        None,
        file_sha256(NEW_CLI.encode()),
    )
    report = classify(git_repo, templates_root=new)
    assert CLI not in {item.path for item in report.files if item.state != "unchanged"}
    assert report.strict_ok  # the lock now records it as the project's own


def test_an_edit_becomes_the_projects_own_when_the_template_did_not_change(
    git_repo, vendored, run_git, commit_all
):
    (git_repo / CLI).write_text("ours\n")
    commit_all(git_repo)
    pulls = PullRequests()

    result = sync(git_repo, vendored, in_place=False, open_pull_request=pulls)

    assert result.owned == [CLI] and result.changed
    assert entry(git_repo, CLI).kind == "seeded"
    assert (git_repo / CLI).read_text() == "ours\n"
    assert run_git(git_repo, "show", "--name-only", "--format=", "HEAD").split() == [LOCK_PATH]
    [body] = pulls.bodies
    assert f"- `{CLI}`" in body.split("\n## Needs the owner\n", 1)[1]


def test_a_deleted_file_becomes_the_projects_own_and_is_not_restored(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    first = sync(git_repo, new, in_place=True)
    again = sync(git_repo, new, in_place=True)

    assert first.owned == ["devctl"] and not again.changed
    assert not os.path.lexists(git_repo / "devctl")
    assert entry(git_repo, "devctl").kind == "seeded"


def test_a_later_template_change_to_an_owned_file_is_reported_and_not_applied(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ours\n")
    commit_all(git_repo)
    assert sync(git_repo, vendored, in_place=True).owned == [CLI]
    newer = make_templates("newer", {f"common/{CLI}": NEW_CLI})

    report = classify(git_repo, templates_root=newer)
    result = sync(git_repo, newer, in_place=True)

    assert {item.path: item.state for item in report.files}[CLI] == "template updated"
    assert (result.seeded_changed, result.updated, result.owned) == ([CLI], [], [])
    assert (git_repo / CLI).read_text() == "ours\n"
    assert entry(git_repo, CLI).template_sha256 == file_sha256(NEW_CLI.encode())


def test_a_repointed_skill_link_becomes_the_projects_own_and_revert_restores_it(git_repo, vendored):
    link = git_repo / ".claude/skills/rs-demo"
    link.unlink()
    link.symlink_to("../../somewhere-else")

    result = sync(git_repo, vendored, in_place=True)

    assert result.owned == [".claude/skills/rs-demo"]
    assert os.readlink(link) == "../../somewhere-else"
    template_hash = file_sha256(b"../../.agents/skills/rs-demo")
    assert entry(git_repo, ".claude/skills/rs-demo").template_sha256 == template_hash

    reverted = sync(git_repo, vendored, in_place=True, revert=[".claude/skills/rs-demo"])

    assert reverted.reverted == [".claude/skills/rs-demo"]
    assert os.readlink(link) == "../../.agents/skills/rs-demo"
    assert entry(git_repo, ".claude/skills/rs-demo").link == "../../.agents/skills/rs-demo"


@pytest.mark.parametrize("in_place", [True, False])
def test_revert_writes_the_current_template_and_manages_the_file_again(
    git_repo, vendored, make_templates, commit_all, run_git, in_place
):
    (git_repo / CLI).write_text("ours\n")
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    sync(git_repo, vendored, in_place=True)
    commit_all(git_repo)
    new = make_templates("new", {f"common/{CLI}": NEW_CLI})
    mode = stat.S_IMODE((git_repo / CLI).stat().st_mode)
    pulls = PullRequests()

    result = sync(
        git_repo, new, in_place=in_place, revert=[CLI, "./devctl"], open_pull_request=pulls
    )

    assert result.reverted == ["devctl", CLI] and result.seeded_changed == []
    assert (git_repo / CLI).read_text() == NEW_CLI
    assert stat.S_IMODE((git_repo / CLI).stat().st_mode) == mode
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"
    assert os.access(git_repo / "devctl", os.X_OK)
    assert entry(git_repo, CLI).sha256 == file_sha256(NEW_CLI.encode())
    assert entry(git_repo, "devctl").kind == "managed"
    assert classify(git_repo, templates_root=new).strict_ok
    if not in_place:
        changed = run_git(git_repo, "show", "--name-only", "--format=", "HEAD").split()
        assert changed == [LOCK_PATH, "devctl", CLI]
        assert "Reverted to the Kit's template;" in pulls.bodies[0]


def test_revert_takes_back_an_edit_that_sync_has_not_recorded(git_repo, vendored):
    (git_repo / CLI).write_text("ours\n")

    # devctl is unchanged, so naming it changes nothing.
    result = sync(git_repo, vendored, in_place=True, revert=[CLI, "devctl"])

    assert (result.reverted, result.owned) == ([CLI], [])
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert entry(git_repo, CLI).kind == "managed"


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("notes.md", "notes.md: not a Kit file"),
        ("../outside", "../outside: not a Kit file"),
        ("AGENTS.md", "AGENTS.md: a seeded Kit file"),
        ("devctl", "devctl: listed under [kit] exclude"),
        (CLI, f"{CLI}: the Kit no longer has a template for it"),
    ],
)
def test_revert_refuses_a_path_it_cannot_revert_and_writes_nothing(
    git_repo, vendored, make_templates, commit_all, write_kit_settings, path, reason
):
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / CLI).write_text("ours\n")
    (git_repo / "devctl").write_text("ours\n")
    commit_all(git_repo)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {f"common/{CLI}": None, f"common/{SKILL}": "demo, revised\n"})

    with pytest.raises(KitRefusal, match=re.escape(reason)):
        sync(git_repo, new, in_place=True, revert=[SKILL, path])

    assert (git_repo / LOCK_PATH).read_bytes() == lock
    assert (git_repo / SKILL).read_text() == "demo\n"
    assert (git_repo / CLI).read_text() == "ours\n"


# Owner groups (spec section 3, "Who owns what"): stack Kit, stack-agnostic Kit and
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
        in_place=True,
    )
    stack = sync(
        git_repo,
        make_templates("stack", {**layers, f"python/{path}": "python, revised\n"}),
        in_place=True,
    )

    assert not common_only.changed
    assert stack.updated == [path]
    assert (git_repo / path).read_text() == "python, revised\n"


def test_an_edited_kit_skill_becomes_the_projects_own_and_keeps_its_link(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / SKILL).write_text("ours\n")
    commit_all(git_repo)
    new = make_templates("new", {f"common/{SKILL}": "demo, revised\n"})

    result = sync(git_repo, new, in_place=True)

    assert result.owned == [SKILL]
    assert (git_repo / SKILL).read_text() == "ours\n"
    assert os.readlink(git_repo / ".claude/skills/rs-demo") == "../../.agents/skills/rs-demo"
    assert entry(git_repo, ".claude/skills/rs-demo").kind == "managed"


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

    result = sync(git_repo, new, in_place=True)

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

    result = sync(git_repo, new, in_place=True)

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

    result = sync(git_repo, new, in_place=True)

    assert result.added == [".github/workflows/devctl-check.yml"]
    assert (git_repo / ".github/workflows/release.yml").read_text() == "name: release\n"
    assert ".github/workflows/release.yml" not in {
        item.path for item in read_lock(git_repo).entries
    }


# Project overrides: [kit] exclude.


def test_an_excluded_file_the_project_edited_is_left_unreported(
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
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
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, in_place=True)

    assert not os.path.lexists(git_repo / "devctl")
    assert not result.changed and result.owned == []
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

    result = sync(git_repo, new, in_place=True)

    for name in ("rs-demo", "rs-new"):
        assert not os.path.lexists(git_repo / ".agents/skills" / name)
        assert not os.path.lexists(git_repo / ".claude/skills" / name)
    assert not result.changed and result.owned == []
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

    result = sync(git_repo, new, in_place=True)

    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert (result.deleted, result.owned) == ([], [])
    assert entry(git_repo, CLI) == before


def test_removing_a_path_from_exclude_restores_normal_handling(
    git_repo, vendored, make_templates, write_kit_settings
):
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
