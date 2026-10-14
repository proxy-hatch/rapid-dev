# Packaged skills

These files are the canonical skill sources. Checkout discovery paths under `.agents/skills` and `.claude/skills` are relative symlinks here.
Source archives include the canonical resources and omit those checkout aliases so the build cannot consume resources through a second path.

- [rapid-ship-engineering](rapid-ship-engineering/SKILL.md) routes implementation, review, architecture and writing guidance for agents working on this repository. Spec 1's Kit skills replace it.

Each skill's `SKILL.md` is the navigation entry for its references. Edit that source once; preserve local links, attribution and license files.

After resource edits, run `uv run pytest tests/test_skill_discovery.py` from the repository root. It checks local resource links and that both discovery surfaces hold exactly the packaged skills.
