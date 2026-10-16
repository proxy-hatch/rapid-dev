# Tests

Keep tests flat, except devctl's tests, which go in `devctl/` as `test_devctl_*.py`. Name each test for the behavior or module it covers.

| Change | Start here |
| --- | --- |
| The `rapid-ship` command's version and entry points | [test_cli.py](test_cli.py) |
| `rapid-ship init`, `status` and `sync`: templates, lock, git calls, each command and the command line | `test_kit_*.py`, such as [test_kit_templates.py](test_kit_templates.py), [test_kit_init.py](test_kit_init.py) with [its variables](test_kit_init_variables.py) and [the checks already in the repository](test_kit_init_existing_checks.py), [test_kit_status.py](test_kit_status.py), [test_kit_sync.py](test_kit_sync.py) with [who owns what](test_kit_sync_ownership.py), [test_kit_hooks.py](test_kit_hooks.py) for git hooks and failed branch switches, and [test_kit_cli.py](test_kit_cli.py) |
| The packaged templates against Spec 1, and this repository's own Kit | [test_kit_contents.py](test_kit_contents.py), [test_kit_dogfood.py](test_kit_dogfood.py) |
| Fixtures: small template trees, scratch git repositories and the vendored fixture Kit | [conftest.py](conftest.py) |
| The vendored devctl in `tools/devctl/` | [devctl/](devctl/): `test_devctl_*.py`. These tests import the vendored copy. The directory must have no `__init__.py`, which would make it a regular package that can shadow `devctl`. Its `conftest.py` puts `tools/devctl` on `sys.path` until plan 3 sets pytest's `pythonpath` |
| Atomic file replacement, create-only writes and safe paths | [test_files.py](test_files.py) |
| Bounded process runner | [test_process.py](test_process.py) |
| Repository validation, navigation and ignored local state | [test_check.py](test_check.py), [test_repository_navigation.py](test_repository_navigation.py) |
| Skill links and discovery aliases | [test_skill_discovery.py](test_skill_discovery.py) |

Use `tmp_path` for repository state and temporary executables for command stand-ins. The Kit tests build scratch git repositories with the `git_repo` fixture, whose commits need no signing and run no hooks.
Label offline and simulated tests; live evidence belongs in [docs/trials](../docs/trials/).
Check rejected operations for unchanged state when that is part of the contract.
Run affected files with `uv run pytest tests/test_<area>.py` from the repository root, and devctl's with `uv run pytest tests/devctl`.
