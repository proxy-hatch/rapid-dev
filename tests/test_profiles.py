from importlib.resources import files

from agentic_engineering.configuration import init_project
from agentic_engineering.models import ProjectConfig
from agentic_engineering.profiles import get_profile, list_profiles


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


def test_skill_is_packaged_and_installed_without_overwriting_user_instructions(tmp_path):
    bundled = files("agentic_engineering").joinpath("skills/rapid-ship/SKILL.md")
    assert bundled.is_file()
    (tmp_path / "design.md").write_text("Approved design")
    (tmp_path / "AGENTS.md").write_text("Existing project rules\n")
    init_project(tmp_path, "sample", "design.md")
    installed = tmp_path / ".agents/skills/rapid-ship/SKILL.md"
    assert installed.read_text() == bundled.read_text()
    installed.write_text("Project-specific skill revision\n")
    init_project(tmp_path, "sample", "design.md")
    assert installed.read_text() == "Project-specific skill revision\n"
    assert (tmp_path / "AGENTS.md").read_text() == "Existing project rules\n"


def test_fresh_project_has_discoverable_delivery_instructions(tmp_path):
    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "sample", "design.md")
    assert ".devctl/AGENTS.md" in (tmp_path / "AGENTS.md").read_text()
