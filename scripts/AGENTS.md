# Repository maintenance scripts

- [check.py](check.py) runs the Python/repository CI suite: navigation, `rapid-ship status --strict`, lint, format, types and tests in the checkout, then the build and the distribution smoke in a temporary copy of current source. `status --strict` fails until the vendored Kit (`devctl`, `tools/devctl/`) equals its templates; run `uv run rapid-ship sync --in-place` to refresh it. Ignored local state stays out of that copy.
- [check_repository.py](check_repository.py) validates local Markdown link destinations in maintained `AGENTS.md` files and relative skill aliases. Git excludes ignored state; new untracked guides count. Remote URLs and heading anchors are not checked.
- [smoke_distribution.py](smoke_distribution.py) checks the wheel that `uv build` made, then runs its `rapid-ship` in scratch repositories:
  1. The wheel ships every template file git keeps. The script lists them with `git ls-files`, or by walking the tree when there is no `.git`, as in `check.py`'s temporary copy. Hatch silently drops paths that `.gitignore` matches, so a missing file fails here.
  2. It installs the wheel into a fresh `uv venv --python <the running Python>`, so each CI matrix leg smokes its own interpreter. It fails if `rapid_ship` imports from the checkout, or if `rapid-ship --version` differs from the project version.
  3. Each scratch repository has its own git identity and no signing, because `init` commits. In a new repository, which has no commits, it runs `init --stack python` and checks that the Kit is the first commit on the default branch with a clean work tree. It then runs `status --strict`, `uv lock --check --project tools/devctl` and `./devctl --version`.
  4. In an existing project whose uv workspace covers `tools/*`, it runs `init` and checks that the Kit is committed on `rapid-ship/init` with a clean work tree. Then `./devctl --version` must equal the first project's. It then adds `exclude = ["tools/devctl"]` to the workspace, and the project's own `uv lock` and devctl's lock check must pass.

The shared validation sequence is defined in [check.py](check.py); [CI](../.github/workflows/ci.yml) calls it for each supported Python version.
The mypy stage uses the file list in [pyproject.toml](../pyproject.toml): `rapid_ship` and the vendored `tools/devctl`, so devctl is checked once and `rapid_ship/templates` is not. Keep this list shared with `uv run mypy`.
For validation changes, run `uv run pytest tests/test_check.py tests/test_repository_navigation.py`.
For skill changes, also run `uv run pytest tests/test_skill_discovery.py`.
Run `uv run python scripts/check.py` for the full suite. The website keeps its separate `npm --prefix website run build` check.
To check a build in the checkout itself, run `uv build --clear`, then `uv run python scripts/smoke_distribution.py`. The smoke needs uv's cache or the network for `tomli-w` and hatchling.
