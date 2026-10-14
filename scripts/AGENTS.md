# Repository maintenance scripts

- [check.py](check.py) runs the Python/repository CI suite: navigation, lint, format, types and tests in the checkout, then the build and the distribution smoke in a temporary copy of current source. Ignored local state stays out of that copy.
- [check_repository.py](check_repository.py) validates local Markdown link destinations in maintained `AGENTS.md` files and relative skill aliases. Git excludes ignored state; new untracked guides count. Remote URLs and heading anchors are not checked.
- [smoke_distribution.py](smoke_distribution.py) installs the wheel that `uv build` made from the source archive into a fresh environment and checks that `rapid-ship --version` reports the project version.

The shared validation sequence is defined in [check.py](check.py); [CI](../.github/workflows/ci.yml) calls it for each supported Python version.
The mypy stage uses the file list in [pyproject.toml](../pyproject.toml). Keep this list shared with `uv run mypy`.
For validation changes, run `uv run pytest tests/test_check.py tests/test_repository_navigation.py`.
For skill changes, also run `uv run pytest tests/test_skill_discovery.py`.
Run `uv run python scripts/check.py` for the full suite. The website keeps its separate `npm --prefix website run build` check.
To check a build in the checkout itself, run `uv build --clear`, then `uv run python scripts/smoke_distribution.py`.
