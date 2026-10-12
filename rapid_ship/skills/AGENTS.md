# Packaged skills

These files are the canonical skill sources. Checkout discovery paths under `.agents/skills` and `.claude/skills` are symlinks here.
Source archives include the canonical resources and omit those checkout aliases so the build cannot consume resources through a second path.

- [rapid-ship](rapid-ship/SKILL.md) routes setup and delivery to its references.
- [rapid-ship-improve](rapid-ship-improve/SKILL.md) handles framework feedback.
- [rapid-ship-engineering](rapid-ship-engineering/SKILL.md) routes implementation, review, architecture and writing guidance.

Each skill's `SKILL.md` is the navigation entry for its references. Edit that source once; preserve local links, attribution and license files. Keep instructions portable to projects using any language.

Initialization recursively copies each individual skill directory into user projects. Repository maintenance guidance belongs in this parent guide; instructions inside a skill become part of the installed product. Reinitialization preserves customized installed files.

After resource edits, run `uv run pytest tests/test_skill_discovery.py` from the repository root and exercise installation from a built wheel. That test checks local resource links and both discovery surfaces; packaging must retain every referenced resource.
