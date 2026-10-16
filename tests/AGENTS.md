# Tests

Keep tests flat and name them for the behavior or module they cover.

| Change | Start here |
| --- | --- |
| The `rapid-ship` command | [test_cli.py](test_cli.py) |
| Atomic file replacement | [test_files.py](test_files.py) |
| Bounded process runner | [test_process.py](test_process.py) |
| Repository validation, navigation and ignored local state | [test_check.py](test_check.py), [test_repository_navigation.py](test_repository_navigation.py) |
| Skill links and discovery aliases | [test_skill_discovery.py](test_skill_discovery.py) |

Use `tmp_path` for repository state and temporary executables for command stand-ins.
Label offline and simulated tests; live evidence belongs in [docs/trials](../docs/trials/).
Check rejected operations for unchanged state when that is part of the contract.
Run affected files with `uv run pytest tests/test_<area>.py` from the repository root.
