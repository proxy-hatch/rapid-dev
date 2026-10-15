"""Map rules 2 (every maintained directory has a guide) and 3 (every guide is reachable)."""

from __future__ import annotations

from check_workspace import Workspace, project_settings, skill_text
from devctl.check.map import MapStep, coverage_errors, guides, reachability_errors

HINT = "add an AGENTS.md guide, or list the directory under [map] unguided"


def layout(workspace: Workspace) -> list[str]:
    workspace.write("AGENTS.md", "[Docs](docs/AGENTS.md)\n")
    workspace.write("docs/AGENTS.md", "# Docs\n")
    workspace.write("tools/devctl/x.py", "")
    workspace.write("src/app/__init__.py", "")
    workspace.write("src/app/api/routes.py", "")
    workspace.write(".github/workflows/ci.yml", "on: push\n")
    return workspace.context().repo.files()


def test_top_level_and_source_root_children_need_guides(workspace: Workspace) -> None:
    files = layout(workspace)

    assert coverage_errors(files, project_settings(source_roots=("src/app",))) == [
        f"src/: {HINT}",
        f"src/app/api/: {HINT}",
        f"tools/: {HINT}",
    ]


def test_unguided_and_excluded_directories_need_no_guide(workspace: Workspace) -> None:
    files = layout(workspace)
    project = project_settings(
        source_roots=("src/app",), unguided=("src", "src/app/api"), map_exclude=("tools",)
    )

    assert coverage_errors(files, project) == []


def test_bytecode_directories_need_no_guide(workspace: Workspace) -> None:
    workspace.write("src/app/__init__.py", "")
    workspace.write("src/app/__pycache__/__init__.cpython-312.pyc", "")
    files = workspace.context().repo.files()

    assert "src/app/__pycache__/__init__.cpython-312.pyc" in files
    assert (
        coverage_errors(files, project_settings(source_roots=("src/app",), unguided=("src",))) == []
    )


def test_missing_source_root_is_reported(workspace: Workspace) -> None:
    files = layout(workspace)

    errors = coverage_errors(files, project_settings(source_roots=("src/other",)))

    assert "src/other: source root has no files; fix [map] source_roots" in errors


def test_every_guide_is_reachable_from_the_root(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "[Docs](docs/)\n")
    workspace.write("docs/AGENTS.md", "[Plans](plans/AGENTS.md)\n")
    workspace.write("docs/plans/AGENTS.md", "# Plans\n")
    workspace.write("docs/orphan/AGENTS.md", "# Orphan\n")
    context = workspace.context()
    root = context.repo.root
    found = guides(root, context.repo.files(), context.project)

    assert reachability_errors(root, found) == [
        "docs/orphan/AGENTS.md: not reachable by links from AGENTS.md; "
        "link it from its parent guide"
    ]


def test_missing_root_guide_is_reported(workspace: Workspace) -> None:
    workspace.write("docs/AGENTS.md", "# Docs\n")

    assert reachability_errors(workspace.root, ["docs/AGENTS.md"])[0].startswith("AGENTS.md:")


def test_excluded_template_guides_are_not_part_of_the_map(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    workspace.write("pkg/templates/common/AGENTS.md", "[Missing](nowhere.md)\n")

    result = MapStep().run(
        workspace.context(source_roots=(), unguided=("pkg",), map_exclude=("pkg/templates/common",))
    )

    assert result.status == "passed", result.details


def test_link_targets_are_normalised_before_they_reach_a_guide(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "[Docs](./api/../docs/) and [Spaced](<spaced%20dir/AGENTS.md>)\n")
    workspace.write("docs/AGENTS.md", "[Up](../docs/sub/#top)\n")
    workspace.write("docs/sub/AGENTS.md", "# Sub\n")
    workspace.write("spaced dir/AGENTS.md", "# Spaced\n")
    context = workspace.context()
    root = context.repo.root

    assert reachability_errors(root, guides(root, context.repo.files(), context.project)) == []


def test_links_that_leave_the_repository_or_are_not_files_reach_nothing(
    workspace: Workspace,
) -> None:
    workspace.write(
        "AGENTS.md",
        "[Web](https://example.com/docs/AGENTS.md) [Anchor](#docs) [Out](../docs/)\n",
    )
    workspace.write("docs/AGENTS.md", "# Docs\n")
    context = workspace.context()
    root = context.repo.root

    assert reachability_errors(root, guides(root, context.repo.files(), context.project)) == [
        "docs/AGENTS.md: not reachable by links from AGENTS.md; link it from its parent guide"
    ]


def test_an_unreadable_guide_links_nothing(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "[Docs](docs/)\n")
    workspace.write("docs/AGENTS.md", "")
    (workspace.root / "docs/AGENTS.md").write_bytes(b"\xff\xfe[Sub](sub/)\n")
    workspace.write("docs/sub/AGENTS.md", "# Sub\n")
    context = workspace.context()
    root = context.repo.root

    assert reachability_errors(root, guides(root, context.repo.files(), context.project)) == [
        "docs/sub/AGENTS.md: not reachable by links from AGENTS.md; link it from its parent guide"
    ]


def test_the_step_fails_on_a_directory_without_a_guide(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    workspace.write("tools/devctl/x.py", "")

    result = MapStep().run(workspace.context(source_roots=()))

    assert result.status == "failed"
    assert result.details == (f"tools/: {HINT}",)


def test_the_step_fails_on_a_guide_no_link_reaches(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    workspace.write("docs/AGENTS.md", "# Docs\n")

    result = MapStep().run(workspace.context(source_roots=()))

    assert result.status == "failed"
    assert result.details == (
        "docs/AGENTS.md: not reachable by links from AGENTS.md; link it from its parent guide",
    )


def test_the_step_reports_links_then_coverage_then_reachability_then_aliases(
    workspace: Workspace,
) -> None:
    workspace.write("AGENTS.md", "[Missing](nowhere.md)\n")
    workspace.write("tools/devctl/x.py", "")
    workspace.write("docs/AGENTS.md", "# Docs\n")
    workspace.write(".agents/skills/demo/SKILL.md", skill_text("demo"))

    result = MapStep().run(workspace.context(source_roots=()))

    assert result.status == "failed"
    assert result.details == (
        "AGENTS.md:1: missing target 'nowhere.md'; update the navigation link",
        f"tools/: {HINT}",
        "docs/AGENTS.md: not reachable by links from AGENTS.md; link it from its parent guide",
        ".claude/skills/demo: add a relative symlink to ../../.agents/skills/demo "
        "and track it in Git",
    )
