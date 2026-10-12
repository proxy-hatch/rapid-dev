# Repository skill discovery

`skills/` contains symlinks to the canonical packaged [skills](../src/agentic_engineering/skills/).
Edit the canonical files; these aliases let coding agents discover the same reviewed content.
The [.claude](../.claude/AGENTS.md) surface points to that same source.

Before changing skill behavior or references, read the packaged [skills guide](../src/agentic_engineering/skills/AGENTS.md).
Keep maintainer navigation outside individual skill bundles; project setup copies those bundles into downstream projects.
After changing discovery paths or bundled references, run `uv run pytest tests/test_skill_discovery.py` from the repository root.
See [engineering-skills.md](../docs/engineering-skills.md) for how installed guidance reaches workers and reviewers.
