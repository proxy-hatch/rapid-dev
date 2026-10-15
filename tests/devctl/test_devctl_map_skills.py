"""Map rule 7, front-matter half: each SKILL.md names its directory and describes itself."""

from __future__ import annotations

import pytest

from check_workspace import Workspace, skill_text
from devctl.check.map import MapStep, skill_errors


def add_skill(workspace: Workspace, name: str, text: str) -> None:
    workspace.write(f".agents/skills/{name}/SKILL.md", text)
    workspace.link(f".claude/skills/{name}", f"../../.agents/skills/{name}")


def errors(workspace: Workspace) -> list[str]:
    context = workspace.context()
    return skill_errors(context.repo.root, context.repo.files())


def test_a_project_authored_skill_passes(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    add_skill(workspace, "rs-tdd", skill_text("rs-tdd"))  # as the Kit vendors it
    add_skill(workspace, "release-notes", skill_text("release-notes"))  # not in the lock

    result = MapStep().run(workspace.context(source_roots=()))

    assert result.status == "passed", result.details


def test_skill_name_must_match_its_directory(workspace: Workspace) -> None:
    # An unpatched upstream fork: Claude Code would register /tdd, not /rs-tdd.
    add_skill(workspace, "rs-tdd", skill_text("tdd"))

    assert errors(workspace) == [
        ".agents/skills/rs-tdd/SKILL.md: name must be rs-tdd, the directory name"
    ]


@pytest.mark.parametrize(
    "text", ["---\nname: notes\n---\n", "---\nname: notes\ndescription: '  '\n---\n"]
)
def test_skill_description_must_not_be_empty(workspace: Workspace, text: str) -> None:
    add_skill(workspace, "notes", text)

    assert errors(workspace) == [".agents/skills/notes/SKILL.md: description is missing or empty"]


def test_skill_without_front_matter_fails(workspace: Workspace) -> None:
    add_skill(workspace, "notes", "# Notes\n")

    assert errors(workspace) == [
        ".agents/skills/notes/SKILL.md: no front matter; start the file with --- "
        "and the keys name and description"
    ]
