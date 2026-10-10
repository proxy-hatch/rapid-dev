from importlib.resources import files

from agentic_engineering.configuration import init_project


def test_skill_is_packaged_and_installed_without_overwriting_user_instructions(tmp_path):
    bundled = files("agentic_engineering").joinpath("skills/trust-first-engineering/SKILL.md")
    assert bundled.is_file()
    (tmp_path / "design.md").write_text("Approved design")
    (tmp_path / "AGENTS.md").write_text("Existing project rules\n")
    init_project(tmp_path, "sample", "design.md")
    installed = tmp_path / ".agents/skills/trust-first-engineering/SKILL.md"
    assert installed.read_text() == bundled.read_text()
    installed.write_text("Project-specific skill revision\n")
    init_project(tmp_path, "sample", "design.md")
    assert installed.read_text() == "Project-specific skill revision\n"
    assert (tmp_path / "AGENTS.md").read_text() == "Existing project rules\n"


def test_fresh_project_has_discoverable_delivery_instructions(tmp_path):
    (tmp_path / "design.md").write_text("Approved design")
    init_project(tmp_path, "sample", "design.md")
    assert ".devctl/AGENTS.md" in (tmp_path / "AGENTS.md").read_text()
