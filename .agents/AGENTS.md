# Repository skill discovery

`skills/` contains relative symlinks to the canonical packaged [skills](../rapid_ship/skills/).
Edit the canonical files; these aliases let coding agents discover the same reviewed content.
The [.claude](../.claude/AGENTS.md) surface points to that same source.

Before changing skill behavior or references, read the packaged [skills guide](../rapid_ship/skills/AGENTS.md).
Keep maintainer navigation outside individual skill bundles.
After changing discovery paths or bundled references, run `uv run pytest tests/test_skill_discovery.py` from the repository root.
