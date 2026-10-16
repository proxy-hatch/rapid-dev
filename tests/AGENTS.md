# Tests

Keep tests flat, except devctl's tests, which go in `devctl/` as `test_devctl_*.py`. Name each test for the behavior or module it covers.

| Change | Start here |
| --- | --- |
| The `rapid-ship` command's version and entry points | [test_cli.py](test_cli.py) |
| `rapid-ship init`, `status` and `sync`: templates, lock, git calls, each command and the command line | `test_kit_*.py`, such as [test_kit_templates.py](test_kit_templates.py), [test_kit_init.py](test_kit_init.py) with [its variables](test_kit_init_variables.py) and [the checks already in the repository](test_kit_init_existing_checks.py), which also covers how the command line prints them, [test_kit_status.py](test_kit_status.py), [test_kit_sync.py](test_kit_sync.py) with [who owns what](test_kit_sync_ownership.py) and [`[kit] exclude`](test_kit_sync_exclude.py), [test_kit_hooks.py](test_kit_hooks.py) for git hooks and failed branch switches, and [test_kit_cli.py](test_kit_cli.py) |
| The packaged templates against Spec 1, and this repository's own Kit | [test_kit_contents.py](test_kit_contents.py), [test_kit_dogfood.py](test_kit_dogfood.py) |
| Fixtures: small template trees, scratch git repositories and the vendored fixture Kit | [conftest.py](conftest.py) |
| The vendored devctl in `tools/devctl/`, and each `devctl check` step | [devctl/](devctl/): `test_devctl_*.py`, with one test file per `devctl check` step, and [check_workspace.py](devctl/check_workspace.py), the typed fixtures that build a scratch repository and check context. pytest's `pythonpath` in `pyproject.toml` puts `tools/devctl` and `tests/devctl` on `sys.path`, so these tests import the vendored copy and the fixtures. The directory has no `__init__.py`, which would make it a regular package that can shadow `devctl`, and no `conftest.py` of its own, so mypy sees one module named `conftest` |
| rapid-ship's own check steps (`vendored`, `distribution`, `python-3.12`) and the ignored state left by the removed controller; the same steps run after `sync --in-place` in a copy of this repository | [devctl/test_devctl_project_steps.py](devctl/test_devctl_project_steps.py), [devctl/test_devctl_project_dogfood.py](devctl/test_devctl_project_dogfood.py) |
| Atomic file replacement, create-only writes and safe paths | [test_files.py](test_files.py) |
| Bounded process runner | [devctl/test_devctl_process.py](devctl/test_devctl_process.py) |
| Skill links and discovery aliases | [test_skill_discovery.py](test_skill_discovery.py) |
| This repository's `.gitleaks.toml`: gitleaks's default rules still apply, and only the placeholder key a plan quotes is allowed | [test_gitleaks_settings.py](test_gitleaks_settings.py) |

Annotate every test, fixture and helper: mypy strict and Ruff's rules cover `tests/`, with only `S101` (assert) ignored. Start a process through `devctl.process.run_process`, as `conftest.py` and `check_workspace.py` do, so a test needs no `rs-exception`.
Use `tmp_path` for repository state and temporary executables for command stand-ins. The Kit tests build scratch git repositories with the `git_repo` fixture, whose commits need no signing and run no hooks.
Label offline and simulated tests; live evidence belongs in [docs/trials](../docs/trials/).
[devctl/test_devctl_check_integration.py](devctl/test_devctl_check_integration.py) and [devctl/test_devctl_project_dogfood.py](devctl/test_devctl_project_dogfood.py) need network access and gitleaks 8.30.1 on PATH, so `uv run pytest` needs them too. [test_gitleaks_settings.py](test_gitleaks_settings.py) runs real gitleaks offline.
Check rejected operations for unchanged state when that is part of the contract.
Run affected files with `uv run pytest tests/test_<area>.py` from the repository root, and devctl's with `uv run pytest tests/devctl`.
