"""Rendering Kit templates for one project, with small template trees (offline)."""

import re
from pathlib import Path

import pytest

import rapid_ship
from rapid_ship.kit.templates import (
    KitError,
    Template,
    installed_version,
    is_excluded,
    load_manifest,
    packaged_templates,
    read_excluded,
    read_optional_skills,
    render_files,
    render_path,
)


def by_path(templates):
    return {template.path: template for template in templates}


def test_managed_files_are_copied_and_seeded_files_are_substituted(make_templates, kit_variables):
    root = make_templates()

    rendered = by_path(render_files("python", kit_variables, (), root=root))

    assert rendered["devctl"].kind == "managed"
    assert rendered["devctl"].content == (root / "common/devctl").read_bytes()
    assert rendered["AGENTS.md"] == Template("AGENTS.md", "seeded", b"# demo-app\n", None)
    assert rendered["src/demo_app/__init__.py"].content == b'"""demo_app."""\n'
    assert "src/__package__/__init__.py" not in rendered
    assert list(rendered) == sorted(rendered)


def test_the_stack_layer_overrides_common(make_templates, kit_variables):
    root = make_templates(changes={"common/CLAUDE.md": "common\n", "python/CLAUDE.md": "python\n"})

    assert (
        by_path(render_files("python", kit_variables, (), root=root))["CLAUDE.md"].content
        == b"python\n"
    )
    assert (
        by_path(render_files("agnostic", kit_variables, (), root=root))["CLAUDE.md"].content
        == b"common\n"
    )


def test_skill_links_follow_installed_skills_and_optional_skills_need_opt_in(
    make_templates, kit_variables
):
    root = make_templates()

    default = by_path(render_files("agnostic", kit_variables, (), root=root))
    opted = by_path(render_files("agnostic", kit_variables, ("rs-extra",), root=root))

    link = Template(".claude/skills/rs-demo", "managed", None, "../../.agents/skills/rs-demo")
    assert default[".claude/skills/rs-demo"] == link
    assert ".agents/skills/rs-extra/SKILL.md" not in default
    assert ".claude/skills/rs-extra" not in default
    assert opted[".claude/skills/rs-extra"].link == "../../.agents/skills/rs-extra"
    with pytest.raises(KitError, match="unknown optional Kit skill 'rs-unknown'"):
        render_files("agnostic", kit_variables, ("rs-unknown",), root=root)


def test_an_empty_owner_comments_out_its_line(make_templates, kit_variables):
    root = make_templates(
        changes={"common/.github/CODEOWNERS": "# Walk\n* @{{owner}}\n# /.github/ @{{owner}}\n"}
    )

    rendered = by_path(render_files("agnostic", {**kit_variables, "owner": ""}, (), root=root))

    assert rendered[".github/CODEOWNERS"].content == b"# Walk\n# * @<owner>\n# /.github/ @<owner>\n"


@pytest.mark.parametrize(
    ("changes", "variables", "message"),
    [
        (
            {"common/AGENTS.md": "Owner: {{owner}}\n"},
            {"owner": ""},
            "AGENTS.md: owner must not be empty",
        ),
        ({"common/AGENTS.md": "{{nope}}\n"}, {}, "AGENTS.md: unknown template variable 'nope'"),
        ({"common/tools/__package__/x.py": ""}, {}, "only seeded templates may use __package__"),
        ({"kit.toml": "seeded = []\nextra = []\n"}, {}, "kit.toml: unknown key 'extra'"),
        ({"kit.toml": 'seeded = "AGENTS.md"\n'}, {}, "kit.toml seeded: expected a list"),
    ],
)
def test_template_errors_name_the_file(make_templates, kit_variables, changes, variables, message):
    root = make_templates(changes=changes)

    with pytest.raises(KitError, match=message):
        render_files("agnostic", {**kit_variables, **variables}, (), root=root)


def test_symlinks_in_the_template_tree_are_refused(make_templates, kit_variables):
    root = make_templates()
    (root / "common/alias").symlink_to("devctl")

    with pytest.raises(KitError, match="alias is a symlink"):
        render_files("agnostic", kit_variables, (), root=root)


def test_generated_files_in_the_template_tree_are_ignored(make_templates, kit_variables):
    root = make_templates(
        changes={
            "common/tools/devctl/devctl/__pycache__/cli.cpython-312.pyc": "x",
            "common/tools/devctl/.venv/bin/python3.12": "x",
            "common/.DS_Store": "x",
        }
    )
    # uv's environments hold symlinks, which the template walk would otherwise refuse.
    (root / "common/tools/devctl/.venv/bin/python").symlink_to("python3.12")

    paths = by_path(render_files("agnostic", kit_variables, (), root=root))

    generated = {"__pycache__", ".venv", ".DS_Store"}
    assert not any(generated & set(path.split("/")) for path in paths)
    assert "tools/devctl/devctl/cli.py" in paths


def test_a_tracked_template_tree_renders_only_what_git_keeps(
    git_repo, make_templates, kit_variables, run_git
):
    root = make_templates(
        "project/templates", {"common/scratch.local": "x\n", "common/kept.local": "x\n"}
    )
    (git_repo / ".gitignore").write_text("*.local\n")
    run_git(git_repo, "add", ".gitignore", "templates")
    run_git(git_repo, "add", "--force", "templates/common/kept.local")
    (root / "common/draft.md").write_text("not added yet\n")

    paths = by_path(render_files("agnostic", kit_variables, (), root=root))

    assert "scratch.local" not in paths  # ignored and untracked, so the wheel would not ship it
    assert "kept.local" in paths  # tracked, though an ignore pattern matches it
    assert "draft.md" in paths  # untracked but not ignored
    assert "devctl" in paths


def test_an_untracked_template_tree_inside_a_repository_is_read_as_it_is(
    git_repo, make_templates, kit_variables
):
    # An installed copy can sit in a project's ignored .venv. Its kit.toml is not tracked there.
    (git_repo / ".gitignore").write_text(".venv/\n")
    root = make_templates("project/.venv/site-packages/rapid_ship/templates")

    paths = by_path(render_files("agnostic", kit_variables, (), root=root))

    assert {"devctl", "AGENTS.md", ".claude/skills/rs-demo"} <= set(paths)


def test_the_manifest_reads_every_list(make_templates):
    manifest = load_manifest(make_templates())

    assert manifest.executable == frozenset({"devctl"})
    assert manifest.optional_skills == frozenset({"rs-extra"})
    assert "src/__package__/__init__.py" in manifest.new_project


def test_kit_exclude_is_read_and_normalised(tmp_path, write_kit_settings):
    write_kit_settings(tmp_path, exclude=["devctl", "tools/devctl/", "./.agents/skills/rs-demo"])
    assert read_excluded(tmp_path) == ("devctl", "tools/devctl", ".agents/skills/rs-demo")

    (tmp_path / ".rapid-ship/project.toml").write_text('stack = "python"\n')
    assert read_excluded(tmp_path) == ()


@pytest.mark.parametrize("value", ['"devctl"', '["../outside"]', '["/etc/passwd"]', '[""]', "[1]"])
def test_an_invalid_kit_exclude_is_an_error(tmp_path, value):
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / ".rapid-ship/project.toml").write_text(
        f'stack = "python"\n\n[kit]\nexclude = {value}\n'
    )

    with pytest.raises(KitError, match=re.escape(".rapid-ship/project.toml [kit] exclude:")):
        read_excluded(tmp_path)


def test_an_excluded_directory_covers_its_files_and_a_skill_directory_its_link():
    excluded = ("devctl", "tools/devctl", ".agents/skills/rs-demo")

    for path in (
        "devctl",
        "tools/devctl/devctl/cli.py",
        ".agents/skills/rs-demo/SKILL.md",
        ".claude/skills/rs-demo",
    ):
        assert is_excluded(path, excluded), path
    for path in (
        "devctl.md",
        "tools/devctl-extra/x.py",
        ".agents/skills/rs-demo2/SKILL.md",
        ".claude/skills/rs-demo2",
    ):
        assert not is_excluded(path, excluded), path
    assert is_excluded(".claude/skills/rs-tdd", (".agents/skills",))


def test_kit_optional_is_read(tmp_path, write_kit_settings):
    assert read_optional_skills(tmp_path) == ()  # no project.toml yet

    write_kit_settings(tmp_path, optional=["rs-extra"])
    assert read_optional_skills(tmp_path) == ("rs-extra",)

    (tmp_path / ".rapid-ship/project.toml").write_text('stack = "python"\n')
    assert read_optional_skills(tmp_path) == ()


@pytest.mark.parametrize("value", ['"rs-extra"', "[1]"])
def test_an_invalid_kit_optional_is_an_error(tmp_path, value):
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / ".rapid-ship/project.toml").write_text(
        f'stack = "python"\n\n[kit]\noptional = {value}\n'
    )

    message = ".rapid-ship/project.toml [kit] optional: expected a list of skill names"
    with pytest.raises(KitError, match=re.escape(message)):
        read_optional_skills(tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("kit = 1\n", "[kit] must be a table"),
        ("[kit\n", "cannot read .rapid-ship/project.toml"),
    ],
)
def test_unreadable_project_settings_are_an_error(tmp_path, text, message):
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / ".rapid-ship/project.toml").write_text(text)

    for read in (read_excluded, read_optional_skills):
        with pytest.raises(KitError, match=re.escape(message)):
            read(tmp_path)


def test_project_settings_behind_a_symlink_are_refused(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere/project.toml").write_text('stack = "python"\n')
    (tmp_path / ".rapid-ship").symlink_to("elsewhere")

    with pytest.raises(KitError, match=r"\.rapid-ship is a symlink"):
        read_excluded(tmp_path)


def test_a_package_directory_takes_the_package_name_and_needs_one():
    assert render_path("src/__package__/x.py", {"package": "demo_app"}) == "src/demo_app/x.py"
    assert render_path("AGENTS.md", {}) == "AGENTS.md"
    message = "src/__package__/x.py: the package variable is required"
    with pytest.raises(KitError, match=re.escape(message)):
        render_path("src/__package__/x.py", {"package": ""})


def test_the_packaged_templates_sit_beside_the_package_and_the_version_is_installed():
    assert packaged_templates() == Path(rapid_ship.__file__).parent / "templates"
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", installed_version())
