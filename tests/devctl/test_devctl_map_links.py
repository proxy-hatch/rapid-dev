"""Map rule 1 (links in every AGENTS.md), map rule 7's skill discovery aliases and fences."""

from __future__ import annotations

import shutil

import pytest

from check_workspace import Workspace, skill_text
from devctl.check import core_steps
from devctl.check.map import MapStep, guides, link_errors, skill_alias_errors
from devctl.check.markdown import fenced_blocks, without_code, without_fences


@pytest.fixture
def repository(workspace: Workspace) -> Workspace:
    workspace.write(".gitignore", ".venv/\n.worktrees/\noutput/\n")
    workspace.write(".agents/skills/example/SKILL.md", skill_text("example"))
    workspace.link(".claude/skills/example", "../../.agents/skills/example")
    return workspace


def problems(workspace: Workspace) -> str:
    context = workspace.context()
    files = context.repo.files()
    root = context.repo.root
    found = guides(root, files, context.project)
    return "\n".join([*link_errors(root, files, found), *skill_alias_errors(root, files)])


def test_accepts_existing_file_and_directory_navigation(repository: Workspace) -> None:
    repository.write("docs/start.md", "Start here\n")
    repository.write("AGENTS.md", "[Start](docs/start.md) and [Docs](docs/)\n")

    assert problems(repository) == ""


def test_accepts_a_link_to_the_repository_root(repository: Workspace) -> None:
    repository.write("docs/AGENTS.md", "[Root](../) and [Self](.)\n")

    assert problems(repository) == ""


def test_reports_moved_navigation_target_from_untracked_guide(repository: Workspace) -> None:
    repository.write("docs/AGENTS.md", "# Docs\n\n[Start](start.md)\n")
    target = repository.write("docs/start.md", "Start here\n")
    target.rename(repository.root / "docs/moved.md")

    found = problems(repository)

    assert "docs/AGENTS.md:3" in found
    assert "start.md" in found
    assert "update" in found.lower()


def test_supports_markdown_paths_titles_and_reference_links(repository: Workspace) -> None:
    repository.write("docs/hello world.md", "Hello\n")
    repository.write("docs/guide(v2).md", "Version two\n")
    repository.write(
        "docs/AGENTS.md",
        '[Space](hello%20world.md "Title")\n'
        "[Angle](<hello world.md> 'Title')\n"
        "[Parentheses](guide(v2).md)\n"
        r"[Escaped](guide\(v2\).md)"
        "\n"
        "[Full reference][READ THIS]\n"
        "[collapsed][] and [shortcut]\n"
        '[Read this]: <hello world.md> "Title"\n'
        "[collapsed]: guide(v2).md\n"
        "[shortcut]: hello%20world.md\n",
    )

    assert problems(repository) == ""


@pytest.mark.parametrize("link", ["[Broken][target]", "[target][]", "[target]"])
def test_reports_broken_reference_at_its_use(repository: Workspace, link: str) -> None:
    repository.write("AGENTS.md", f"# Guide\n\n{link}\n\n[target]: missing.md\n")

    found = problems(repository)

    assert "AGENTS.md:3" in found
    assert "missing.md" in found


def test_skips_code_external_links_and_ignored_guides(repository: Workspace) -> None:
    repository.write(
        "AGENTS.md",
        "[Web](https://example.com/missing) [Email](mailto:example@example.com)\n"
        "[External](//example.com/page) [Anchor](#heading)\n"
        "`[Inline](missing.md)` and ``[tick ` example](missing.md)``\n"
        "```markdown\n[Example](missing.md)\n```\n"
        "~~~~markdown\n[Example][missing]\n[missing]: absent.md\n~~~~\n",
    )
    for directory in (".venv", ".worktrees", "output"):
        repository.write(f"{directory}/AGENTS.md", "[Generated example](absent.md)\n")

    assert problems(repository) == ""


def test_does_not_silently_accept_malformed_local_link(repository: Workspace) -> None:
    repository.write("AGENTS.md", "[Broken](unquoted path.md)\n")

    found = problems(repository)

    assert "AGENTS.md:1" in found
    assert "syntax" in found.lower()


@pytest.mark.parametrize("target", [".venv/local.md", ".venv/"])
def test_ignored_local_target_cannot_mask_broken_checkout_navigation(
    repository: Workspace, target: str
) -> None:
    repository.write(".venv/local.md", "Local only\n")
    repository.write("AGENTS.md", f"[Local]({target})\n")

    found = problems(repository)

    assert "AGENTS.md:1" in found
    assert "maintained" in found.lower()


def test_accepts_navigation_through_maintained_skill_alias(repository: Workspace) -> None:
    repository.write("AGENTS.md", "[Skill](.claude/skills/example/SKILL.md)\n")

    assert problems(repository) == ""


def test_maintained_link_cannot_hide_ignored_navigation_destination(
    repository: Workspace,
) -> None:
    repository.write(".venv/generated.md", "Local generated guide\n")
    (repository.root / "navigation.md").symlink_to(".venv/generated.md")
    repository.write("AGENTS.md", "[Guide](navigation.md)\n")

    found = problems(repository)

    assert "AGENTS.md:1" in found
    assert "maintained" in found.lower()


def test_new_skill_requires_a_claude_alias(repository: Workspace) -> None:
    repository.write(".agents/skills/new-skill/SKILL.md", skill_text("new-skill"))

    found = problems(repository)

    assert ".claude/skills/new-skill" in found
    assert "symlink" in found.lower()

    repository.link(".claude/skills/new-skill", "../../.agents/skills/new-skill")

    assert problems(repository) == ""


@pytest.mark.parametrize("problem", ["missing", "dangling", "wrong", "absolute", "outside", "copy"])
def test_rejects_invalid_skill_alias(repository: Workspace, problem: str) -> None:
    alias = repository.root / ".claude/skills/example"
    alias.unlink()
    if problem == "dangling":
        alias.symlink_to("../../missing", target_is_directory=True)
    elif problem == "wrong":
        alias.symlink_to("../../.agents/skills", target_is_directory=True)
    elif problem == "absolute":
        alias.symlink_to(repository.root / ".agents/skills/example", target_is_directory=True)
    elif problem == "outside":
        alias.symlink_to("../../../", target_is_directory=True)
    elif problem == "copy":
        # Even an identical copy fails: rule 7 asks for a symlink, and init and sync never copy.
        repository.write(".claude/skills/example/SKILL.md", skill_text("example"))

    found = problems(repository)

    assert ".claude/skills/example" in found
    assert "../../.agents/skills/example" in found


def test_canonical_skill_may_link_into_a_package(workspace: Workspace) -> None:
    workspace.write("pkg/skills/example/SKILL.md", skill_text("example"))
    workspace.link(".agents/skills/example", "../../pkg/skills/example")
    workspace.link(".claude/skills/example", "../../pkg/skills/example")

    assert problems(workspace) == ""


def test_skill_directory_without_skill_md_fails(repository: Workspace) -> None:
    repository.write(".agents/skills/notes/README.md", "# Notes\n")
    repository.link(".claude/skills/notes", "../../.agents/skills/notes")

    assert problems(repository) == ".agents/skills/notes: missing SKILL.md"


def test_nothing_else_may_sit_under_claude_skills(repository: Workspace) -> None:
    repository.write(".claude/skills/AGENTS.md", "# Discovery\n")
    repository.write(".claude/skills/notes.md", "Notes\n")

    assert problems(repository) == (
        ".claude/skills/AGENTS.md: only skill links belong in .claude/skills; remove it\n"
        ".claude/skills/notes.md: only skill links belong in .claude/skills; remove it"
    )


def test_rejects_extra_alias_but_allows_parent_guide(repository: Workspace) -> None:
    repository.link(".claude/skills/unpackaged", "../../.agents/skills/example")
    repository.write(".claude/AGENTS.md", "# Discovery\n")

    found = problems(repository)

    assert ".claude/skills/unpackaged" in found
    assert "remove" in found.lower()
    assert "AGENTS.md" not in found


def test_required_alias_must_be_maintained_in_git(repository: Workspace) -> None:
    with (repository.root / ".gitignore").open("a") as ignore:
        ignore.write(".claude/skills/example\n")

    found = problems(repository)

    assert ".claude/skills/example" in found
    assert "track it in Git" in found


@pytest.mark.parametrize("surface", [".agents", ".claude"])
def test_ignored_files_do_not_count_as_extra_aliases(repository: Workspace, surface: str) -> None:
    with (repository.root / ".gitignore").open("a") as ignore:
        ignore.write(".DS_Store\n")
    repository.write(f"{surface}/skills/.DS_Store", "Local metadata")

    assert problems(repository) == ""


def test_copied_directory_counts_as_extra_alias(repository: Workspace) -> None:
    repository.write(".claude/skills/unpackaged/SKILL.md", skill_text("unpackaged"))

    found = problems(repository)

    assert ".claude/skills/unpackaged" in found
    assert "remove" in found.lower()


def test_agnostic_projects_run_only_the_steps_that_need_no_language_tools(
    workspace: Workspace,
) -> None:
    agnostic = workspace.context(stack="agnostic").project

    assert [(step.name, step.tier) for step in core_steps(agnostic)] == [
        ("map", "fast"),
        ("exceptions", "fast"),
        ("file-size", "fast"),
        ("kit", "fast"),
        ("secrets", "full"),
        ("workflows", "full"),
        ("diff", "full"),
        ("evidence", "full"),
    ]


def test_map_is_blocked_when_git_cannot_list_files(repository: Workspace) -> None:
    context = repository.context()
    shutil.rmtree(repository.root / ".git")

    assert MapStep().run(context).status == "blocked"


def test_without_fences_blanks_fenced_lines_and_keeps_line_numbers() -> None:
    text = "one\n```py\ncode `x`\n```\n~~~\nmore\n~~~\nlast `y`\n"

    blanked = without_fences(text).splitlines()

    assert [line.strip() for line in blanked] == ["one", "", "", "", "", "", "", "last `y`"]
    assert [len(line) for line in blanked] == [len(line) for line in text.splitlines()]
    assert without_code(text).splitlines()[-1] == "last" + " " * 4


def test_fenced_blocks_returns_the_content_of_each_closed_block() -> None:
    text = "intro\n```sh\n$ run\n\nout\n```\n~~~~\n```\n~~~~\n  ```\ntail\n"

    assert fenced_blocks(text) == [["$ run", "", "out"], ["```"]]


def test_fenced_blocks_ignores_a_block_that_never_closes() -> None:
    assert fenced_blocks("```\nopen\n``\n") == []
