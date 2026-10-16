# Tools

[devctl/](devctl/) is this repository's vendored devctl, written by `uv run rapid-ship sync --in-place` from the templates in `rapid_ship/templates/common/tools/devctl/`. Never edit `devctl/devctl/` by hand: change the template, then sync. The `vendored` check step fails when the two differ. `devctl/devctl_project/` is seeded and owned here; it adds rapid-ship's own check steps: `vendored`, `distribution` and `python-3.12`. Their tests are in `tests/devctl/test_devctl_project_steps.py`, and `tests/devctl/test_devctl_project_dogfood.py` checks that they still run after a sync.
