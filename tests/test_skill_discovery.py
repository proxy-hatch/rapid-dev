from importlib.resources import files
from pathlib import Path

import pytest

from agentic_engineering.configuration import init_project

REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("rapid-ship", "rapid-ship-improve")


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
