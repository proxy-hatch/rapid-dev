import re
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from agentic_engineering.configuration import init_project

REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("rapid-ship", "rapid-ship-improve", "rapid-ship-engineering")


def test_bundled_skill_dependencies_resolve_inside_package():
    package = REPOSITORY / "src/agentic_engineering/skills"
    for document in package.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
            link = urlparse(target)
            if link.scheme or not link.path:
                continue
            dependency = (document.parent / unquote(link.path)).resolve()
            assert dependency.is_relative_to(package), (document, target)
            assert dependency.is_file(), (document, target)


@pytest.mark.parametrize("surface", [".agents", ".claude"])
@pytest.mark.parametrize("skill", SKILLS)
def test_checkout_discovery_resolves_to_packaged_skill(surface, skill):
    canonical = REPOSITORY / "src/agentic_engineering/skills" / skill
    discovered = REPOSITORY / surface / "skills" / skill

    assert discovered.is_dir()
    assert discovered.samefile(canonical)
    assert (discovered / "SKILL.md").is_file()


@pytest.mark.parametrize("surface", [".agents", ".claude"])
@pytest.mark.parametrize("skill", SKILLS)
def test_new_project_installs_all_skill_resources(tmp_path, surface, skill):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    init_project(tmp_path, "hello", "design.md")
    bundled = files("agentic_engineering").joinpath("skills", skill)
    installed = tmp_path / surface / "skills" / skill

    def check_tree(source, target):
        for child in source.iterdir():
            destination = target / child.name
            if child.is_dir():
                check_tree(child, destination)
            else:
                assert destination.read_bytes() == child.read_bytes()

    check_tree(bundled, installed)


def test_reinit_preserves_custom_claude_skill(tmp_path):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    customized = tmp_path / ".claude/skills/rapid-ship/SKILL.md"
    customized.parent.mkdir(parents=True)
    customized.write_text("Custom Claude project setup instructions\n")

    init_project(tmp_path, "hello", "design.md")
    init_project(tmp_path, "hello", "design.md")

    assert customized.read_text() == "Custom Claude project setup instructions\n"
    assert (tmp_path / ".claude/skills/rapid-ship-improve/SKILL.md").is_file()


def test_reinit_restores_missing_reference_without_overwriting_custom_entrypoint(tmp_path):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    init_project(tmp_path, "hello", "design.md")
    skill = tmp_path / ".agents/skills/rapid-ship"
    entrypoint = skill / "SKILL.md"
    entrypoint.write_text("Project-specific delivery guidance\n")
    reference = skill / "references/run.md"
    reference.unlink()

    init_project(tmp_path, "hello", "design.md")

    assert entrypoint.read_text() == "Project-specific delivery guidance\n"
    bundled = files("agentic_engineering").joinpath("skills/rapid-ship/references/run.md")
    assert reference.read_bytes() == bundled.read_bytes()


def test_new_project_loads_engineering_defaults_without_skill_discovery(tmp_path):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    init_project(tmp_path, "hello", "design.md")

    assert ".devctl/AGENTS.md" in (tmp_path / "AGENTS.md").read_text()
    instructions = (tmp_path / ".devctl/AGENTS.md").read_text()
    assert ".agents/skills/rapid-ship-engineering/references/ponytail.md" in instructions
    assert ".agents/skills/rapid-ship-engineering/SKILL.md" in instructions
    assert "@.devctl/AGENTS.md" in (tmp_path / "CLAUDE.md").read_text()


def test_reinit_preserves_custom_engineering_and_claude_instructions(tmp_path):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    init_project(tmp_path, "hello", "design.md")
    rules = tmp_path / ".agents/skills/rapid-ship-engineering/references/ponytail.md"
    rules.write_text("Use existing project conventions.\n")
    (tmp_path / "CLAUDE.md").write_text("Existing Claude instructions.\n")

    result = init_project(tmp_path, "hello", "design.md")

    assert rules.read_text() == "Use existing project conventions.\n"
    assert (tmp_path / "CLAUDE.md").read_text() == "Existing Claude instructions.\n"
    assert result["instruction_updates"] == ["CLAUDE.md"]


def test_reinit_reports_old_instructions_without_overwriting(tmp_path):
    (tmp_path / "design.md").write_text("Approved hello command design\n")
    init_project(tmp_path, "hello", "design.md")
    paths = (".devctl/AGENTS.md", "AGENTS.md", "CLAUDE.md")
    for path in paths:
        (tmp_path / path).write_text("Keep the project's existing rules.\n")

    result = init_project(tmp_path, "hello", "design.md")

    assert result["instruction_updates"] == list(paths)
    for path in paths:
        assert (tmp_path / path).read_text() == "Keep the project's existing rules.\n"
