import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("rapid-ship", "rapid-ship-improve", "rapid-ship-engineering")


def test_bundled_skill_dependencies_resolve_inside_package():
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
def test_checkout_discovery_resolves_to_packaged_skill(surface, skill):
    canonical = REPOSITORY / "rapid_ship/skills" / skill
    discovered = REPOSITORY / surface / "skills" / skill

    assert discovered.is_dir()
    assert discovered.samefile(canonical)
    assert (discovered / "SKILL.md").is_file()
