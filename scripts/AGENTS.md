# Repository maintenance scripts

- [smoke_distribution.py](smoke_distribution.py) checks the wheel that `uv build` made, then runs its `rapid-ship` in scratch repositories. The `distribution` check step in `./devctl check` runs it after `uv build`, in a temporary copy of the files Git keeps, without `.git`:
  1. The wheel ships every template file git keeps. The script lists them with `git ls-files`, or by walking the tree when there is no `.git`, as in the `distribution` step's copy. Hatch silently drops paths that `.gitignore` matches, so a missing file fails here.
  2. It installs the wheel into a fresh `uv venv --python <the running Python>`; under the `distribution` step that is devctl's Python. It fails if `rapid_ship` imports from the checkout, or if `rapid-ship --version` differs from the project version.
  3. Each scratch repository has its own git identity and no signing, because `init` commits. In a new repository, which has no commits, it runs `init --stack python` and checks that the Kit is the first commit on the default branch with a clean work tree. It then runs `status --strict`, `uv lock --check --project tools/devctl` and `./devctl --version`.
  4. In an existing project whose uv workspace covers `tools/*`, it runs `init` and checks that the Kit is committed on `rapid-ship/init` with a clean work tree. Then `./devctl --version` must equal the first project's. It then adds `exclude = ["tools/devctl"]` to the workspace, and the project's own `uv lock` and devctl's lock check must pass.

The smoke uses only the standard library. Its `run` starts every command, `git ls-files` included, under exception EX-8, and a failed command stops the smoke with its stdout and stderr.

The step itself is in [tools/devctl/devctl_project/](../tools/devctl/devctl_project/__init__.py). For changes to it, run `uv run pytest tests/devctl/test_devctl_project_steps.py`.
For skill changes, also run `uv run pytest tests/test_skill_discovery.py`.
Run `./devctl check` for the full suite. The website keeps its separate `npm --prefix website run build` check.
To check a build in the checkout itself, run `uv build --clear`, then `uv run python scripts/smoke_distribution.py`. The smoke needs uv's cache or the network for `tomli-w` and hatchling.
