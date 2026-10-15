"""The kit step: the lock is readable and every managed file that is not excluded is present."""

from __future__ import annotations

import pytest

from check_workspace import Workspace
from devctl.check.kit import KitLockError, KitStep, is_excluded, managed_paths
from devctl.settings import PROJECT, load_project
from rapid_ship.kit.lock import Lock, LockEntry, write_lock
from rapid_ship.kit.templates import is_excluded as cli_is_excluded

SKILL = ".agents/skills/rs-demo"


def lock(workspace: Workspace) -> None:
    write_lock(
        workspace.root,
        Lock(
            "0.2.0",
            "python",
            {"package": "app"},
            (
                LockEntry("devctl", "managed", "a" * 64, None, None),
                LockEntry(
                    ".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None
                ),
                LockEntry("AGENTS.md", "seeded", None, None, "b" * 64),
            ),
        ),
    )


def choices(path: str) -> str:
    """Spec section 5's kit row: the message names both choices."""
    return (
        f"rapid-ship sync --revert {path} restores it, "
        "and rapid-ship sync keeps the deletion as the project's own"
    )


def test_present_files_pass_and_managed_paths_are_read(workspace: Workspace) -> None:
    lock(workspace)
    workspace.write("devctl", "#!/bin/sh\n")
    workspace.write(".agents/skills/rs-tdd/SKILL.md", "# TDD\n")
    workspace.link(".claude/skills/rs-tdd", "../../.agents/skills/rs-tdd")

    assert KitStep().run(workspace.context()).status == "passed"
    assert managed_paths(workspace.root, ()) == frozenset({"devctl", ".claude/skills/rs-tdd"})


def test_missing_managed_file_and_link_fail(workspace: Workspace) -> None:
    lock(workspace)

    result = KitStep().run(workspace.context())

    assert result.status == "failed"
    assert sorted(result.details) == [
        f".claude/skills/rs-tdd: managed link is missing; {choices('.claude/skills/rs-tdd')}",
        f"devctl: managed file is missing; {choices('devctl')}",
    ]


def test_a_kit_file_the_lock_records_as_the_projects_own_is_not_required(
    workspace: Workspace,
) -> None:
    # rapid-ship sync moved these entries from managed to seeded: the project deleted devctl and
    # edited the skill link into a file. Their lock entries keep only the template's hash.
    write_lock(
        workspace.root,
        Lock(
            "0.2.0",
            "python",
            {"package": "app"},
            (
                LockEntry("devctl", "seeded", None, None, "a" * 64),
                LockEntry(".claude/skills/rs-tdd", "seeded", None, None, "c" * 64),
            ),
        ),
    )
    workspace.write(".claude/skills/rs-tdd", "the project's own copy\n")

    assert KitStep().run(workspace.context()).status == "passed"
    # The project owns both, so the exceptions and file-size steps scan them.
    assert managed_paths(workspace.root, ()) == frozenset()


def test_a_deleted_path_that_project_toml_excludes_is_not_required(workspace: Workspace) -> None:
    # The project deleted devctl and listed it under [kit] exclude; the lock still names it.
    lock(workspace)
    workspace.write(".agents/skills/rs-tdd/SKILL.md", "# TDD\n")
    workspace.link(".claude/skills/rs-tdd", "../../.agents/skills/rs-tdd")
    workspace.write(PROJECT, 'stack = "python"\n\n[kit]\nexclude = ["devctl"]\n')
    excluded = load_project(workspace.root).excluded

    assert KitStep().run(workspace.context(excluded=excluded)).status == "passed"
    assert managed_paths(workspace.root, excluded) == frozenset({".claude/skills/rs-tdd"})


def test_an_excluded_skill_directory_covers_its_link(workspace: Workspace) -> None:
    write_lock(
        workspace.root,
        Lock(
            "0.2.0",
            "python",
            {"package": "app"},
            (
                LockEntry("devctl", "managed", "a" * 64, None, None),
                LockEntry(".agents/skills/rs-tdd/SKILL.md", "managed", "c" * 64, None, None),
                LockEntry(
                    ".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None
                ),
            ),
        ),
    )
    workspace.write("devctl", "#!/bin/sh\n")
    excluded = (".agents/skills/rs-tdd",)

    assert KitStep().run(workspace.context(excluded=excluded)).status == "passed"
    # The project owns an excluded file, so the exceptions and file-size steps scan it.
    assert managed_paths(workspace.root, excluded) == frozenset({"devctl"})


@pytest.mark.parametrize(
    ("path", "excluded", "expected"),
    [
        ("devctl", ("devctl",), True),
        ("devctl.md", ("devctl",), False),
        ("tools/devctl/devctl/cli.py", ("tools/devctl",), True),
        ("tools/devctl-extra/x.py", ("tools/devctl",), False),
        (f"{SKILL}/SKILL.md", (SKILL,), True),
        (".claude/skills/rs-demo", (SKILL,), True),
        (".claude/skills/rs-demo2", (SKILL,), False),
        (".claude/skills/rs-demo/notes.md", (SKILL,), False),
        (".claude/skills/rs-tdd", (".agents/skills",), True),
        (".claude/skills/rs-tdd", (".claude/skills/rs-tdd",), True),
        ("devctl", (), False),
    ],
)
def test_is_excluded_matches_the_cli(path: str, excluded: tuple[str, ...], expected: bool) -> None:
    # devctl cannot import rapid_ship, so it keeps a copy; this keeps the two equal.
    assert (is_excluded(path, excluded), cli_is_excluded(path, excluded)) == (expected, expected)


@pytest.mark.parametrize("text", [None, "not toml [", 'kit_version = "1"\n'])
def test_unreadable_lock_fails(workspace: Workspace, text: str | None) -> None:
    if text is not None:
        workspace.write(".rapid-ship/kit.lock", text)

    assert KitStep().run(workspace.context()).status == "failed"
    with pytest.raises(KitLockError):
        managed_paths(workspace.root, ())


@pytest.mark.parametrize(
    "text",
    [
        'kit_version = "1"\nstack = "ruby"\n',
        'kit_version = 1\nstack = "python"\n',
        'kit_version = "1"\nstack = "python"\nfile = "devctl"\n',
        'kit_version = "1"\nstack = "python"\nfile = ["devctl"]\n',
        'kit_version = "1"\nstack = "python"\n[[file]]\nkind = "managed"\nsha256 = "a"\n',
        'kit_version = "1"\nstack = "python"\n[[file]]\npath = "devctl"\nkind = "owned"\n',
        'kit_version = "1"\nstack = "python"\n[[file]]\npath = "devctl"\nkind = "managed"\n',
    ],
)
def test_malformed_lock_names_the_problem(workspace: Workspace, text: str) -> None:
    workspace.write(".rapid-ship/kit.lock", text)

    result = KitStep().run(workspace.context())

    assert result.status == "failed"
    assert len(result.details) == 1
    assert result.details[0].startswith(".rapid-ship/kit.lock: ")


def test_a_lock_without_files_passes(workspace: Workspace) -> None:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "1"\nstack = "agnostic"\n')

    assert KitStep().run(workspace.context()).status == "passed"


def test_a_file_or_link_of_the_wrong_kind_is_missing(workspace: Workspace) -> None:
    lock(workspace)
    workspace.write(".claude/skills/rs-tdd", "a copy, not the link\n")
    workspace.link("devctl", "elsewhere")  # a symlink is not the managed regular file

    result = KitStep().run(workspace.context())

    assert result.status == "failed"
    assert sorted(result.details) == [
        f".claude/skills/rs-tdd: managed link is missing; {choices('.claude/skills/rs-tdd')}",
        f"devctl: managed file is missing; {choices('devctl')}",
    ]
