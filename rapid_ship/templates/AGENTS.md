# Kit templates

`rapid-ship init` and `sync` render these files into projects. [kit.toml](kit.toml) lists the seeded paths, the new-project seeds, the executable files, the optional skills and the template variables; every other file is managed.

- `common/` holds files for every stack, laid out as in a project; `python/` and `agnostic/` add or override files per stack. The [project root guide skeleton](common/AGENTS.md) is one of them.
- Managed files are copied byte for byte. Seeded files substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`, and a `__package__` directory becomes the package. An empty owner or repository renders as `<owner>` or `<repository>` and comments out its line; only TOML and CODEOWNERS templates may use them.
- This repository vendors the Kit. After changing a template, run `uv run rapid-ship sync --in-place` and commit the template with its vendored copy. Never edit the vendored copy itself: sync would record the edited file as this repository's own and stop updating it. The `vendored` check step runs `uv run --locked rapid-ship status --strict`, which fails until they match.
- ruff and mypy check the vendored copy in `tools/devctl/` and skip this directory, so devctl is checked once. Tests import the vendored copy.
- [common/.github/workflows/devctl-check.yml](common/.github/workflows/devctl-check.yml) and [common/.githooks/pre-commit](common/.githooks/pre-commit) are managed Kit files: the CI workflow whose job `devctl check` the ruleset requires, and the fast-tier pre-commit hook. This repository's copies are refreshed by sync, never edited.
- Keep template paths clear of the root `.gitignore` patterns: hatch drops ignored paths from the wheel without a warning. `scripts/smoke_distribution.py` fails when the wheel lacks a template.
- Rendering skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files, and here every path git does not keep. A template that is not yet added still renders unless git ignores it.
