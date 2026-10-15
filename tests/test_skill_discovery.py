"""Skill links and discovery aliases in this checkout. Offline."""

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("rapid-ship-engineering",)


def test_bundled_skill_dependencies_resolve_inside_package() -> None:
    package = REPOSITORY / "rapid_ship/skills"
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
def test_checkout_discovery_resolves_to_packaged_skill(surface: str, skill: str) -> None:
    canonical = REPOSITORY / "rapid_ship/skills" / skill
    discovered = REPOSITORY / surface / "skills" / skill

    assert discovered.is_dir()
    assert discovered.samefile(canonical)
    assert (discovered / "SKILL.md").is_file()


@pytest.mark.parametrize("surface", [".agents", ".claude"])
def test_checkout_discovers_exactly_the_packaged_skills(surface: str) -> None:
    # A dangling or untracked alias still reaches agents, so list the directory itself.
    aliases = (REPOSITORY / surface / "skills").iterdir()
    discovered = {path.name for path in aliases if not path.name.startswith(".")}
    package = REPOSITORY / "rapid_ship/skills"
    packaged = {path.parent.name for path in package.glob("*/SKILL.md")}

    assert discovered == packaged == set(SKILLS)
