# Kit commands

The code behind `rapid-ship init`, `status` and `sync`. [cli.py](../cli.py) parses arguments and prints each result. Each module here returns its result; only `sync.py` also prints, to report its push and pull request progress. The files these commands write are in [templates](../templates/AGENTS.md).

- [templates.py](templates.py) reads the manifest (`kit.toml`) and renders the template tree for one stack and project. It also reads the project's `[kit]` lists (`optional` and `exclude`) and holds `KitError` and `KitRefusal`. Discovery skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files and, when the template root's `kit.toml` is tracked by git, every path git does not keep. A source run then renders what the wheel ships.
- [lock.py](lock.py) reads and writes `.rapid-ship/kit.lock`: a content hash for each managed file, a link target for each managed symlink and the template hash for each seeded file. It refuses a path that is not in its canonical form, such as `./devctl`.
- [init.py](init.py) vendors the Kit with create-only, all-or-nothing writes. It plans every write first, writes nothing when any managed file exists, and removes what it created when a write fails. It skips an existing seeded file, even one that is itself a symlink, and lists it for `rs-setup`.
- [status.py](status.py) classifies each locked file against the work tree and the installed templates. It is read-only.
- [sync.py](sync.py) applies template changes with three-way merges and skips `[kit] exclude` paths. Outside `--in-place` it commits on `rapid-ship/kit-sync-<version>`, pushes and opens the PR with `gh`. After a failed write it restores the work tree: each file it changed, what it created and the starting branch.
- [git.py](git.py) makes the git calls: `git()` passes `--literal-pathspecs` (`literal=False` only for `check-ignore`, which refuses it), `work_tree_root` finds the top of the work tree and `is_clean` checks the status.

`KitError` means the command could not run, and the CLI exits 2. So does an `OSError` or `UnicodeDecodeError`, such as an unreadable managed file. `KitRefusal` means the repository's state refuses the request, and the CLI exits 1. Every write stays inside the repository and never passes through a symlink; use `safe_path` and `create_file` from [files.py](../files.py).

Tests are `tests/test_kit_*.py`; see the [test guide](../../tests/AGENTS.md). They are offline: sync's push and PR use a fake there, a local bare repository and a stand-in `gh`, and the old release's templates are injected, so no test contacts GitHub or fetches a tag. Run `uv run pytest tests/test_kit_*.py` after a change here.
