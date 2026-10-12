from importlib.resources import files

import pytest

from rapid_ship.models import ProjectConfig
from rapid_ship.project.configuration import init_project
from rapid_ship.project.profiles import get_profile, list_profiles


def test_custom_profile_is_language_neutral_and_is_the_default():
    profile = get_profile("custom")
    assert profile["id"] == "custom"
    assert not profile.get("language")
    assert not profile.get("tools")
    assert not profile.get("checks")
    assert ProjectConfig(name="sample", design_path="design.md").profile == "custom"
    assert {item["id"] for item in list_profiles()} == {"custom", "python-cli"}


def test_python_profile_remains_an_explicit_independent_choice():
    profile = get_profile("python-cli")
    assert profile["language"] == "python"
    assert profile["checks"]["unit"] == ["uv", "run", "pytest"]
    profile["checks"]["unit"].append("changed")
    assert get_profile("python-cli")["checks"]["unit"] == ["uv", "run", "pytest"]


@pytest.mark.parametrize("skill", ["rapid-ship", "rapid-ship-improve"])
def test_skill_is_packaged_and_installed_without_overwriting_user_instructions(tmp_path, skill):
    bundled = files("rapid_ship").joinpath(f"skills/{skill}/SKILL.md")
    assert bundled.is_file()
    (tmp_path / "design.md").write_text("Approved design")
    (tmp_path / "AGENTS.md").write_text("Existing project rules\n")
    init_project(tmp_path, "sample", "design.md")
    installed = tmp_path / f".agents/skills/{skill}/SKILL.md"
    assert installed.read_text() == bundled.read_text()
    installed.write_text("Project-specific skill revision\n")
    init_project(tmp_path, "sample", "design.md")
    assert installed.read_text() == "Project-specific skill revision\n"
    assert (tmp_path / "AGENTS.md").read_text() == "Existing project rules\n"


def test_reinit_adds_missing_improvement_skill_without_changing_project_choices(tmp_path):
    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "sample", "design.md")
    improvement = ".agents/skills/rapid-ship-improve/SKILL.md"
    (tmp_path / improvement).unlink(missing_ok=True)
    delivery = tmp_path / ".agents/skills/rapid-ship/SKILL.md"
    delivery.write_text("Project-specific delivery instructions\n")
    preserved = {
        path: (tmp_path / path).read_bytes()
        for path in (
            "AGENTS.md",
            ".devctl/AGENTS.md",
            ".devctl/project.json",
            ".devctl/interview.json",
            ".agents/skills/rapid-ship/SKILL.md",
        )
    }

    result = init_project(tmp_path, "changed", "design.md", profile="python-cli")

    assert (tmp_path / improvement).is_file()
    assert result["created"] == [improvement]
    assert {path: (tmp_path / path).read_bytes() for path in preserved} == preserved


def test_fresh_project_has_discoverable_delivery_instructions(tmp_path):
    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "sample", "design.md")
    assert ".devctl/AGENTS.md" in (tmp_path / "AGENTS.md").read_text()
