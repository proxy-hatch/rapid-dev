import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts/check_repository.py"


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".venv/\n.worktrees/\noutput/\n")
    canonical = tmp_path / "rapid_ship/skills/example"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("# Example\n")
    for surface in (".agents", ".claude"):
        aliases = tmp_path / surface / "skills"
        aliases.mkdir(parents=True)
        (aliases / "example").symlink_to(
            "../../rapid_ship/skills/example", target_is_directory=True
        )
    return tmp_path


def check(root):
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_accepts_existing_file_and_directory_navigation(repository):
    (repository / "docs").mkdir()
    (repository / "docs/start.md").write_text("Start here\n")
    (repository / "AGENTS.md").write_text("[Start](docs/start.md) and [Docs](docs/)\n")

    result = check(repository)

    assert result.returncode == 0, result.stderr


def test_reports_moved_navigation_target_from_untracked_guide(repository):
    (repository / "docs").mkdir()
    guide = repository / "docs/AGENTS.md"
    guide.write_text("# Docs\n\n[Start](start.md)\n")
    target = repository / "docs/start.md"
    target.write_text("Start here\n")
    target.rename(repository / "docs/moved.md")

    result = check(repository)

    assert result.returncode == 1
    assert "docs/AGENTS.md:3" in result.stderr
    assert "start.md" in result.stderr
    assert "update" in result.stderr.lower()


def test_supports_markdown_paths_titles_and_reference_links(repository):
    docs = repository / "docs"
    docs.mkdir()
    (docs / "hello world.md").write_text("Hello\n")
    (docs / "guide(v2).md").write_text("Version two\n")
    (docs / "AGENTS.md").write_text(
        '[Space](hello%20world.md "Title")\n'
        "[Angle](<hello world.md> 'Title')\n"
        "[Parentheses](guide(v2).md)\n"
        r"[Escaped](guide\(v2\).md)"
        "\n"
        "[Full reference][READ THIS]\n"
        "[collapsed][] and [shortcut]\n"
        '[Read this]: <hello world.md> "Title"\n'
        "[collapsed]: guide(v2).md\n"
        "[shortcut]: hello%20world.md\n"
    )

    result = check(repository)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("link", ["[Broken][target]", "[target][]", "[target]"])
def test_reports_broken_reference_at_its_use(repository, link):
    (repository / "AGENTS.md").write_text(f"# Guide\n\n{link}\n\n[target]: missing.md\n")

    result = check(repository)

    assert result.returncode == 1
    assert "AGENTS.md:3" in result.stderr
    assert "missing.md" in result.stderr


def test_skips_code_external_links_and_ignored_guides(repository):
    (repository / "AGENTS.md").write_text(
        "[Web](https://example.com/missing) [Email](mailto:example@example.com)\n"
        "[External](//example.com/page) [Anchor](#heading)\n"
        "`[Inline](missing.md)` and ``[tick ` example](missing.md)``\n"
        "```markdown\n[Example](missing.md)\n```\n"
        "~~~~markdown\n[Example][missing]\n[missing]: absent.md\n~~~~\n"
    )
    for directory in (".venv", ".worktrees", "output"):
        ignored = repository / directory
        ignored.mkdir()
        (ignored / "AGENTS.md").write_text("[Generated example](absent.md)\n")

    result = check(repository)

    assert result.returncode == 0, result.stderr


def test_does_not_silently_accept_malformed_local_link(repository):
    (repository / "AGENTS.md").write_text("[Broken](unquoted path.md)\n")

    result = check(repository)

    assert result.returncode == 1
    assert "AGENTS.md:1" in result.stderr
    assert "syntax" in result.stderr.lower()


def test_fails_if_git_cannot_enumerate_the_checkout(tmp_path):
    result = check(tmp_path)

    assert result.returncode == 1
    assert "git" in result.stderr.lower()
    assert "repository" in result.stderr.lower()


@pytest.mark.parametrize("target", [".venv/local.md", ".venv/"])
def test_ignored_local_target_cannot_mask_broken_checkout_navigation(repository, target):
    (repository / ".venv").mkdir()
    (repository / ".venv/local.md").write_text("Local only\n")
    (repository / "AGENTS.md").write_text(f"[Local]({target})\n")

    result = check(repository)

    assert result.returncode == 1
    assert "AGENTS.md:1" in result.stderr
    assert "maintained" in result.stderr.lower()


def test_accepts_navigation_through_maintained_skill_alias(repository):
    (repository / "AGENTS.md").write_text("[Skill](.agents/skills/example/SKILL.md)\n")

    result = check(repository)

    assert result.returncode == 0, result.stderr


def test_new_packaged_skill_requires_both_discovery_aliases(repository):
    skill = repository / "rapid_ship/skills/new-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("New skill\n")

    result = check(repository)

    assert result.returncode == 1
    assert ".agents/skills/new-skill" in result.stderr
    assert ".claude/skills/new-skill" in result.stderr
    assert "symlink" in result.stderr.lower()

    for surface in (".agents", ".claude"):
        (repository / surface / "skills/new-skill").symlink_to(
            "../../rapid_ship/skills/new-skill", target_is_directory=True
        )
    assert check(repository).returncode == 0


@pytest.mark.parametrize("surface", [".agents", ".claude"])
@pytest.mark.parametrize(
    "problem", ["missing", "dangling", "wrong", "copied", "absolute", "outside"]
)
def test_rejects_invalid_skill_alias(repository, surface, problem):
    alias = repository / surface / "skills/example"
    alias.unlink()
    if problem == "dangling":
        alias.symlink_to("../../missing", target_is_directory=True)
    elif problem == "wrong":
        alias.symlink_to("../../rapid_ship/skills", target_is_directory=True)
    elif problem == "copied":
        alias.mkdir()
        (alias / "SKILL.md").write_text("Copied skill\n")
    elif problem == "absolute":
        alias.symlink_to(repository / "rapid_ship/skills/example", target_is_directory=True)
    elif problem == "outside":
        alias.symlink_to("../../../", target_is_directory=True)

    result = check(repository)

    assert result.returncode == 1
    assert f"{surface}/skills/example" in result.stderr
    assert "../../rapid_ship/skills/example" in result.stderr


def test_rejects_extra_alias_but_allows_parent_guide(repository):
    alias = repository / ".agents/skills/unpackaged"
    alias.symlink_to("../../rapid_ship/skills/example", target_is_directory=True)
    (repository / ".claude/skills/AGENTS.md").write_text("# Discovery\n")

    result = check(repository)

    assert result.returncode == 1
    assert ".agents/skills/unpackaged" in result.stderr
    assert "remove" in result.stderr.lower()
    assert ".claude/skills/AGENTS.md" not in result.stderr


def test_required_alias_must_be_maintained_in_git(repository):
    with (repository / ".gitignore").open("a") as ignore:
        ignore.write(".agents/skills/example\n")

    result = check(repository)

    assert result.returncode == 1
    assert ".agents/skills/example" in result.stderr
    assert "maintain" in result.stderr.lower()


def test_ignored_files_do_not_count_as_extra_aliases(repository):
    with (repository / ".gitignore").open("a") as ignore:
        ignore.write(".DS_Store\n")
    (repository / ".agents/skills/.DS_Store").write_bytes(b"Local metadata")

    result = check(repository)

    assert result.returncode == 0, result.stderr


def test_copied_directory_counts_as_extra_alias(repository):
    copied = repository / ".agents/skills/unpackaged"
    copied.mkdir()
    (copied / "SKILL.md").write_text("Copied skill\n")

    result = check(repository)

    assert result.returncode == 1
    assert ".agents/skills/unpackaged" in result.stderr
    assert "remove" in result.stderr.lower()


def test_maintained_link_cannot_hide_ignored_navigation_destination(repository):
    (repository / ".venv").mkdir()
    (repository / ".venv/generated.md").write_text("Local generated guide\n")
    (repository / "navigation.md").symlink_to(".venv/generated.md")
    (repository / "AGENTS.md").write_text("[Guide](navigation.md)\n")

    result = check(repository)

    assert result.returncode == 1
    assert "AGENTS.md:1" in result.stderr
    assert "maintained" in result.stderr.lower()
