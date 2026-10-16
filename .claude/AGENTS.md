# Claude skill discovery

`skills/` provides Claude's aliases to the canonical packaged [skills](../rapid_ship/skills/).
Read the shared [discovery guidance](../.agents/AGENTS.md) before changing an alias or its target.
Edit canonical files so both agent discovery surfaces receive the same content.

Preserve each symlink's repository-relative target.
The parameterized checks in [test_skill_discovery.py](../tests/test_skill_discovery.py) cover both discovery surfaces.
