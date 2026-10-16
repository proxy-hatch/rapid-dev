# The rapid-ship CLI implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `rapid-ship init`, `status` and `sync`, the Kit templates they write, and run `init` on this repository so its vendored devctl is tested and kept equal to the templates.

**Architecture:** `rapid_ship/kit/` renders the template tree in `rapid_ship/templates/`, described by `kit.toml`, for one stack and project, and records what it wrote in `.rapid-ship/kit.lock`. `init` writes create-only and all-or-nothing, `status` compares disk, lock and the installed templates, and `sync` applies template changes with three-way merges on a branch or in place. This repository vendors its own Kit, so tests, ruff and mypy run against `tools/devctl/`, and `status --strict` in `scripts/check.py` keeps that copy equal to the templates.

**Tech Stack:** Python 3.12+, argparse, `tomllib`, `tomli-w` 1.2, hatchling, uv (0.11.0 observed locally), git (`merge-file`, `check-ignore`, `ls-files`), gh, pytest, ruff, mypy.

**Spec:** [Spec 1](../specs/2026-10-14-kit-and-setup-design.md), sections 3 and 4, except the CI workflow and the pre-commit hook (plan 3) and the `rs-` skills (plan 5). Order, layout and shared names: [plan index](2026-10-14-kit-and-setup.md).

## Global Constraints

- Python 3.12 or later. uv runs every command. Settings are TOML, read with `tomllib`.
- The rapid-ship CLI depends only on `tomli-w`. devctl has no runtime dependency in this plan; PyYAML arrives in plan 3 and PyJWT in plan 4.
- Commands are one word: `rapid-ship init`, `status` and `sync` here; `app` and `adopt` arrive in plans 4 and 5.
- Exit codes: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run.
- `init` needs a git work tree with a clean status and no `.rapid-ship/kit.lock`. It never edits an existing file, never runs project code or a hook, and writes nothing when any managed file exists.
- Every Kit write stays inside the repository and never passes through a symlink. `init` never writes over an existing file.
- Managed templates are copied byte for byte. Seeded templates substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`; a `__package__` directory becomes the package name. `.claude/skills/<name>` links are generated from `.agents/skills/<name>/`.
- Template discovery skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files everywhere. When the template root's `kit.toml` is tracked by git, as in this repository, it also skips every path git does not keep, so a source run renders what the wheel ships.
- `.claude/skills/<name>` is always a relative symlink, never a copy. When a write fails, a symlink included, both commands exit 2 and leave nothing half-written (spec section 4). `init` removes what it created. `sync` restores each file it changed, removes what it created and, outside `--in-place`, switches back to the starting branch and deletes the sync branch.
- `status` is read-only. `--strict` exits 1 unless every managed file that is not excluded is unchanged and matches the current template. Files not in the lock are not reported.
- `sync` compares template hashes, not versions. It works on the branch `rapid-ship/kit-sync-<version>`, never under `rs/`. It merges with `git merge-file`. The base is the old version's templates, fetched from its tag with `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<old>`. It never changes a seeded or project-authored file, and creates a seeded file that a newer Kit adds only where nothing exists at its path. It opens the PR with `gh` under the owner's login. `--in-place` writes the work tree with no branch, commit or PR.
- `[kit] exclude` in `project.toml` lists Kit files or directories the project owns (spec section 3, "Who owns what"). It is the only record of an exclusion: the lock keeps no mark. A path is excluded when it equals an entry or lies below one; `.claude/skills/<name>` is also excluded when `.agents/skills/<name>` is. `render_files` still renders excluded paths. `sync` never creates, replaces, merges or deletes them, and adds no lock entry for them. An existing lock entry stays as it was, with its last hashes. `status` classifies locked excluded paths as `excluded`, and `--strict` ignores them. When the project removes a path from the list, the next sync applies the decision table (Task 5) to it as usual, using that kept entry. `init` does not read `[kit] exclude`. `status` and `sync` read it only through `read_excluded` and `is_excluded` (Task 2), and devctl loads the same list as `ProjectSettings.excluded` (Task 10).
- The Kit version is the rapid-ship package version, and each Kit release is a tag `v<version>` on `main` that the owner creates (spec section 3).
- Seed defaults: `max_workers = 5`, `attempt_limit = 3`, `[tests] unit = ["tests/unit/**"]`, `[release] method = "none"`, `[kit] optional = []`, `[kit] exclude = []`. `gate.toml`: `mode = "walk"`, an empty Flight lease, `owner_approves_behavioural_test_removal = true`, promotion over the last 30 merged agent PRs and demotion over the last 20, each allowing at most one Revision per PR on average, at most one Rollback and no open Alarm.
- CODEOWNERS during Walk: one active line, `* @<owner>`. The Protected set follows it, commented out: spec section 4's list, which includes the root `devctl` shim. The Python template adds `/pyproject.toml`, where the guardrail settings live. These are exactly plan 4's `PROTECTED_PATHS` and, for Python, `PYTHON_PROTECTED_PATHS`.
- devctl is its own uv workspace (`[tool.uv.workspace] members = []`). A project whose root `[tool.uv.workspace] members` match `tools/devctl` must list it under `exclude`, or the project's own `uv lock`, `uv sync` and `uv run --locked` fail. `init` never edits that file, so `rs-setup` adds the exclude (plan 5) and `devctl doctor` reports it missing (plan 4).
- Python seed: the spec's Ruff rule list, `max-complexity = 10` (section 11 proposal), relative imports banned, an empty `banned-api` table; strict mypy with `warn_unreachable` and the error codes `ignore-without-code`, `redundant-expr`, `truthy-bool`; one `layers` and one `forbidden` import-linter contract; pytest `--strict-markers --strict-config`, `xfail_strict = true`, `filterwarnings = ["error"]`; ruff, mypy, pytest and import-linter as dev dependencies. `tools/devctl` is excluded from the project's lint, type and test settings.
- Tests are offline and labelled as such. A skipped or blocked step never counts as passed.
- This repository's ruff selects `E`, so lines are capped at 100 characters. Some code here is shown on longer lines for reading; wrap it, splitting long strings, until `ruff format --check` and `ruff check` pass.
- Work on a branch whose name does not start with `rs/`.
- rapid-ship is not on PyPI: `https://pypi.org/pypi/rapid-ship/json` returned 404 on 2026-10-14. Owners run `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>` (spec section 3). This plan publishes nothing and creates no tag. On 2026-10-14, `git ls-remote https://github.com/proxy-hatch/rapid-ship HEAD 'refs/tags/*'` listed only `HEAD`. Until the owner tags a release, sync cannot fetch a merge base and lists every needed merge as a conflict. Tests inject the old templates.

## Review Focus

1. **Sync must keep file modes.** `atomic_replace` publishes `0o600` files (`rapid_ship/files.py:14`, pinned by `tests/test_files.py:22`). A naive sync would leave the `devctl` shim unexecutable. Sync keeps each replaced file's mode. Pinned in Task 5.
2. **`init` writes nothing on any conflict.** That covers a dirty tree, an existing managed file, a symlinked directory or a dangling symlink on a target's path, a parent that is a regular file, a Kit path that git ignores, and a write or a symlink failing midway, which must remove everything already created. Pinned in Task 3.
3. **`status --strict` checks the installed templates as well as the lock.** It fails when the lock matches disk but not the installed template, when a managed template has no lock entry, and when the Kit dropped a locked file. Pinned in Task 4.
4. **Sync never touches seeded or project-authored files.** After a clean merge, the lock records the new template's hash, not the merged file's, so the file stays "modified" and the next merge has the right base. A conflict leaves the file and its lock entry unchanged. Pinned in Task 5.
5. **A failed sync puts the work tree back.** When a symlink or any other write fails, sync restores each file it replaced or deleted from memory and removes what it created. Outside `--in-place` it also returns to the starting branch and deletes the sync branch. Pinned in Task 5.
6. **The wheel must ship every template, and a source run must render no more.** Hatch keeps dot-directories and `uv.lock`, but silently drops paths matching `.gitignore`. In a scratch build on 2026-10-14 it dropped `.env`, `build/` and `__pycache__/` with this repository's `.gitignore`. `smoke_distribution.py` compares the wheel with the templates git keeps (Task 12). Template discovery skips what git does not keep and any `.venv`, so a template directory that uv ran in cannot add files or refused symlinks (Task 2).
7. **An excluded path belongs to the project.** Sync must not merge an excluded file the project edited, recreate one it deleted, delete one the Kit dropped, or create a link for an excluded skill directory. `--strict` must pass with an excluded file modified. Only `[kit] exclude` records the exclusion: adding a path to it leaves the lock unchanged, and removing it lets the next sync handle the path with its kept entry. Pinned in Tasks 4, 5 and 7.
8. **Sync respects each owner group** (spec section 3, "Who owns what"). The owner asked for each group to be checked, with this repository's dog-food in mind. Test files are under `tests/`; `::` without a file repeats the file above it.

| Group | Case | Tests |
| --- | --- | --- |
| Stack Kit | The stack's file wins over the common one when rendering, on init and on sync | `test_kit_templates.py::test_the_stack_layer_overrides_common`, `test_kit_init.py::test_the_stack_version_wins_on_init`, `test_kit_sync.py::test_sync_keeps_the_stack_version_over_the_common_one` |
| Language-agnostic Kit | An unchanged file is replaced, an edit is merged, a conflict is left for a person | `test_kit_sync.py::test_an_unchanged_file_is_replaced_on_a_sync_branch_and_keeps_its_mode`, `::test_a_local_edit_merges_cleanly_and_the_lock_keeps_the_template_hash`, `::test_a_conflicting_merge_leaves_the_file_and_its_entry` |
| Language-agnostic Kit | An edited Kit skill is merged and keeps its link; an optional skill arrives only on opt-in | `test_kit_sync.py::test_an_edited_kit_skill_is_merged_and_keeps_its_link`, `::test_opting_in_to_an_optional_skill_adds_it` |
| Project extensions | Seeded files, and a project file where a new Kit file would go, are never written | `test_kit_sync.py::test_sync_never_touches_seeded_or_project_files` |
| Project extensions | A modified `devctl_project` with a module beside it, a project skill with its link, an extra workflow | `test_kit_sync.py::test_a_modified_devctl_project_survives_sync`, `::test_a_project_skill_and_its_link_survive_sync`, `::test_a_project_workflow_survives_beside_a_new_kit_workflow` |
| Project overrides | `[kit] exclude`: no merge, no re-creation, no deletion, the skill link covered, normal handling after removal | `test_kit_sync.py::test_an_excluded_file_the_project_edited_is_not_merged`, `::test_a_deleted_excluded_file_stays_deleted`, `::test_an_excluded_skill_directory_covers_its_link`, `::test_sync_never_deletes_an_excluded_file_the_kit_dropped`, `::test_removing_a_path_from_exclude_restores_normal_handling` |
| Project overrides | `status --strict` passes with an excluded modified file | `test_kit_status.py::test_excluded_paths_are_reported_and_ignored_by_strict`, `test_kit_cli.py::test_strict_status_passes_with_an_excluded_modified_file` |
| Dog-food | This repository's `sync --in-place` leaves `tools/devctl/devctl_project/` unchanged | `test_kit_dogfood.py::test_this_repository_sync_leaves_devctl_project_unchanged` (Task 9) |
| Dog-food | Nothing is excluded here, so `--strict` holds every Kit file to its template | `devctl/test_devctl_settings.py::test_this_repository_settings_load` (Task 10) |

### Task 1: Lock file

**Files:**
- Modify: `pyproject.toml` (dependencies), `uv.lock`, `rapid_ship/files.py`
- Create: `rapid_ship/kit/__init__.py`, `rapid_ship/kit/templates.py` (types and errors only), `rapid_ship/kit/lock.py`
- Test: `tests/test_files.py`, `tests/test_kit_lock.py`

**Interfaces:**
- Consumes (plan 1): `rapid_ship/files.py: atomic_replace(path: Path, content: bytes) -> None`.
- Produces: `atomic_replace(path: Path, content: bytes, *, mode: int = 0o600) -> None`; `UnsafePath(ValueError)`; `relative_parts(relative: str) -> tuple[str, ...]`; `safe_path(root: Path, relative: str) -> Path`; `Stack`, `Kind`, `STACKS`, `KitError`, `KitRefusal`, `Template` (index fields); `LockEntry` (index fields); `Lock(kit_version: str, stack: Stack, variables: Mapping[str, str], entries: tuple[LockEntry, ...])` (index fields); `LOCK_PATH = ".rapid-ship/kit.lock"`; `read_lock(root: Path) -> Lock`; `write_lock(root: Path, lock: Lock) -> None`; `file_sha256(content: bytes) -> str`; `entry_for(template: Template) -> LockEntry`.

- [ ] **Step 1: Confirm plan 1's end state.** Run:

```bash
uv run rapid-ship --version
test ! -e rapid_ship/templates && test ! -e rapid_ship/project && test ! -e devctl && echo "controller removed"
git rev-parse --verify 'archive/controller-2026-10^{commit}'
grep -n 'rapid-ship = "rapid_ship.cli:main"' pyproject.toml
```

Expected: `rapid-ship <version>`, `controller removed`, the tag's commit and the console-script line. If any differs, stop: plan 1 is not merged. Show the code being ported with `git show f7b877b:rapid_ship/project/configuration.py | sed -n '33,44p;218,222p'`: `_safe_path` refuses absolute paths, `..` and every symlink, and `open("xb")` never overwrites.

- [ ] **Step 2: Write the failing tests.** Append to `tests/test_files.py` (its imports grow to `from rapid_ship.files import UnsafePath, atomic_replace, relative_parts, safe_path`):

```python
def test_replacement_can_publish_a_shared_or_executable_mode(tmp_path):
    target = tmp_path / "devctl"

    atomic_replace(target, b"#!/bin/sh\n", mode=0o755)

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


@pytest.mark.parametrize("relative", ["", ".", "/etc/passwd", "../outside", "a/../../b", "a\\b"])
def test_relative_parts_refuse_paths_that_leave_the_root(relative):
    with pytest.raises(UnsafePath, match="must stay inside the repository"):
        relative_parts(relative)


def test_safe_path_refuses_every_symlink_below_the_root(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "docs").symlink_to("real")
    (tmp_path / "dangling").symlink_to("missing")
    for relative in ("docs", "docs/README.md", "dangling"):
        with pytest.raises(UnsafePath, match="is a symlink"):
            safe_path(tmp_path, relative)


def test_safe_path_accepts_a_root_reached_through_a_symlink(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "alias").symlink_to("real")

    assert safe_path(tmp_path / "alias", "a/b.txt") == tmp_path.resolve() / "real" / "a" / "b.txt"
```

Create `tests/test_kit_lock.py`:

```python
"""Kit lock reading and writing (offline)."""

import hashlib
import re
import stat

import pytest

from rapid_ship.kit.lock import LOCK_PATH, Lock, LockEntry, file_sha256, read_lock, write_lock
from rapid_ship.kit.templates import KitError

SHA = hashlib.sha256(b"content\n").hexdigest()
VARIABLES = {"owner": "", "package": "demo_app", "project_name": "demo-app", "repository": ""}
GOOD = f"""kit_version = "0.2.0"
stack = "python"

[variables]
package = "demo_app"

[[file]]
path = "devctl"
kind = "managed"
sha256 = "{SHA}"
"""


def test_file_sha256_is_the_hex_digest():
    assert file_sha256(b"content\n") == SHA


def test_round_trip_keeps_every_field_and_sorts_entries(tmp_path):
    entries = (
        LockEntry("tools/devctl/devctl/cli.py", "managed", SHA, None, None),
        LockEntry(".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None),
        LockEntry("AGENTS.md", "seeded", None, None, SHA),
    )
    write_lock(tmp_path, Lock("0.2.0", "python", VARIABLES, entries))

    restored = read_lock(tmp_path)

    expected = tuple(sorted(entries, key=lambda entry: entry.path))
    assert restored == Lock("0.2.0", "python", VARIABLES, expected)
    assert stat.S_IMODE((tmp_path / LOCK_PATH).stat().st_mode) == 0o644


def test_a_missing_lock_says_to_run_init(tmp_path):
    with pytest.raises(KitError, match="run rapid-ship init"):
        read_lock(tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("kit_version = ", "cannot read .rapid-ship/kit.lock"),
        (GOOD.replace('kit_version = "0.2.0"\n', ""), "kit_version must be a non-empty string"),
        (GOOD.replace('stack = "python"', 'stack = "rust"'), "stack must be python or neutral"),
        (
            GOOD.replace('package = "demo_app"', "package = 1"),
            "[variables] must map names to strings",
        ),
        (GOOD + "extra = 1\n", "unknown key 'extra'"),
        (GOOD.replace('path = "devctl"', 'path = "../outside"'), "must stay inside the repository"),
        (
            GOOD.replace('path = "devctl"', 'path = "/etc/passwd"'),
            "must stay inside the repository",
        ),
        (GOOD + GOOD[GOOD.index("[[file]]") :], "devctl is listed twice"),
        (GOOD.replace(f'sha256 = "{SHA}"', 'sha256 = "abc"'), "a managed entry has sha256 or link"),
        (GOOD.replace('kind = "managed"', 'kind = "seeded"'), "a managed entry has sha256 or link"),
        (GOOD + 'link = "../x"\n', "a managed entry has sha256 or link"),
    ],
)
def test_an_invalid_lock_is_an_error(tmp_path, text, message):
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / LOCK_PATH).write_text(text)

    with pytest.raises(KitError, match=re.escape(message)):
        read_lock(tmp_path)


def test_the_lock_is_never_written_through_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".rapid-ship").symlink_to(outside)

    with pytest.raises(KitError, match="is a symlink"):
        write_lock(root, Lock("0.2.0", "python", VARIABLES, ()))
    assert list(outside.iterdir()) == []
```

- [ ] **Step 3: Run the tests and see them fail.** Run `uv run pytest tests/test_files.py tests/test_kit_lock.py -q`. Expected: collection errors, `ImportError: cannot import name 'UnsafePath' from 'rapid_ship.files'` and `ModuleNotFoundError: No module named 'rapid_ship.kit'`.

- [ ] **Step 4: Implement.**

Add the dependency and lock it: set `[project] dependencies = ["tomli-w>=1.2,<2"]`, then run `uv lock`. Expected: `uv.lock` gains `tomli-w` 1.2.0. If plan 1 left any other runtime dependency, run `git grep -n -e pydantic -- rapid_ship scripts tests`; when it prints nothing, remove that dependency too, because the index allows only `tomli-w`.

In `rapid_ship/files.py`, give `atomic_replace` a keyword-only `mode: int = 0o600` and call `os.fchmod(stream.fileno(), mode)` inside the `with os.fdopen(...)` block before writing; the docstring says the default stays private. Add:

```python
class UnsafePath(ValueError):
    """A path would leave the repository or pass through a symlink."""


def relative_parts(relative: str) -> tuple[str, ...]:
    """Split a repository-relative POSIX path, refusing absolute paths, '..' and backslashes."""
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise UnsafePath(f"{relative!r}: path must stay inside the repository")
    return path.parts


def safe_path(root: Path, relative: str) -> Path:
    """Return root/relative after refusing every symlink below root.

    Ported from rapid_ship/project/configuration.py:33-44 at f7b877b. The root is
    resolved first, so a repository reached through a symlink is accepted.
    """
    root = root.resolve()
    current = root
    for part in relative_parts(relative):
        current = current / part
        if current.is_symlink():
            raise UnsafePath(f"{relative}: {current.relative_to(root)} is a symlink")
    return current
```

Create `rapid_ship/kit/__init__.py` with only the docstring `"""rapid-ship's Kit commands: templates, lock, init, status and sync."""`. Create `rapid_ship/kit/templates.py` with `from __future__ import annotations`, `Stack = Literal["python", "neutral"]`, `Kind = Literal["managed", "seeded"]`, `STACKS: tuple[Stack, ...] = ("python", "neutral")`, the frozen `Template` dataclass exactly as the index gives it, and:

```python
class KitError(Exception):
    """A Kit command could not run. The CLI exits 2."""


class KitRefusal(Exception):
    """The repository's state refuses the request. The CLI exits 1."""
```

Create `rapid_ship/kit/lock.py` with the index's `LockEntry`, `Lock` plus `variables: Mapping[str, str]` between `stack` and `entries`, `LOCK_PATH`, and:

```python
# Deleting a file and its entry does not drop it: the next sync would add it again.
_HEADER = "# Written by rapid-ship. To own or drop a Kit file, list it under [kit] exclude in project.toml.\n"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ENTRY_KEYS = {"path", "kind", "sha256", "link", "template_sha256"}


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def entry_for(template: Template) -> LockEntry:
    """The lock entry for a rendered template. Seeded files record the template's hash only."""
    if template.kind == "seeded":
        return LockEntry(template.path, "seeded", None, None, file_sha256(template.content or b""))
    if template.link is not None:
        return LockEntry(template.path, "managed", None, template.link, None)
    return LockEntry(template.path, "managed", file_sha256(template.content or b""), None, None)


def read_lock(root: Path) -> Lock:
    try:
        data = tomllib.loads(safe_path(root, LOCK_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise KitError(f"{LOCK_PATH} is missing; run rapid-ship init") from error
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, UnsafePath) as error:
        raise KitError(f"cannot read {LOCK_PATH}: {error}") from error
    _known(data, {"kit_version", "stack", "variables", "file"}, LOCK_PATH)
    version, stack = data.get("kit_version"), data.get("stack")
    variables, items = data.get("variables", {}), data.get("file", [])
    if not isinstance(version, str) or not version:
        raise KitError(f"{LOCK_PATH}: kit_version must be a non-empty string")
    if stack not in STACKS:
        raise KitError(f"{LOCK_PATH}: stack must be python or neutral")
    if not isinstance(variables, dict) or not all(isinstance(v, str) for v in variables.values()):
        raise KitError(f"{LOCK_PATH}: [variables] must map names to strings")
    if not isinstance(items, list):
        raise KitError(f"{LOCK_PATH}: file must be a list of [[file]] entries")
    entries = tuple(_entry(item, number) for number, item in enumerate(items, start=1))
    seen: set[str] = set()
    for entry in entries:
        if entry.path in seen:
            raise KitError(f"{LOCK_PATH}: {entry.path} is listed twice")
        seen.add(entry.path)
    return Lock(version, cast(Stack, stack), dict(variables), entries)
```

`_known(table, keys, where)` raises `KitError(f"{where}: unknown key {key!r}")` for the first unknown key in sorted order. `_entry(item, number)` uses `where = f"{LOCK_PATH} [[file]] #{number}"`; it requires a table, checks `_ENTRY_KEYS`, requires `path` to be a string and passes it through `relative_parts` (an `UnsafePath` becomes `KitError(f"{where}: {error}")`). It then accepts exactly three shapes: managed with a 64-hex `sha256` and no `link` or `template_sha256`; managed with a non-empty `link` and neither hash; seeded with a 64-hex `template_sha256` only. Anything else raises `KitError(f"{where} ({path}): a managed entry has sha256 or link, and a seeded entry has only template_sha256")`. The lock records no exclusion; `[kit] exclude` in `project.toml` is the only record (Task 2).

`write_lock(root, lock)` resolves `safe_path(root, LOCK_PATH)` (an `UnsafePath` becomes `KitError(str(error))`), runs `mkdir(exist_ok=True)` on its parent, and calls `atomic_replace(path, (_HEADER + tomli_w.dumps(document)).encode("utf-8"), mode=0o644)`. The document is `kit_version`, `stack`, `variables` sorted by name, and `file`: the entries sorted by path, each without its `None` fields. tomli-w 1.2.0 writes the entries as `[[file]]` tables once any entry is too long for an inline table, as every hashed entry is, and inline otherwise; both read back the same.

- [ ] **Step 5: Run the tests and see them pass.** Run `uv run pytest tests/test_files.py tests/test_kit_lock.py -q`. Expected: all pass, including the existing `atomic_replace` tests that pin `0o600`. Then run `uv run mypy`. Expected: `Success`.

- [ ] **Step 6: Commit.**

```bash
git add pyproject.toml uv.lock rapid_ship/files.py rapid_ship/kit/__init__.py rapid_ship/kit/templates.py rapid_ship/kit/lock.py tests/test_files.py tests/test_kit_lock.py
git commit -m "feat: record the vendored Kit in a lock file

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Template rendering

**Files:**
- Modify: `rapid_ship/kit/templates.py`
- Create: `rapid_ship/kit/git.py`, `tests/conftest.py`
- Test: `tests/test_kit_templates.py`

**Interfaces:**
- Consumes: `UnsafePath`, `relative_parts`, `safe_path`, `KitError`, `KitRefusal` (Task 1).
- Produces: `KitManifest(seeded, new_project, executable, optional_skills, variables: frozenset[str])`; `packaged_templates() -> Path`; `installed_version() -> str`; `load_manifest(root: Path | None = None) -> KitManifest`; `render_path(path: str, variables: Mapping[str, str]) -> str`; `render_files(stack: Stack, variables: Mapping[str, str], optional: Sequence[str], *, root: Path | None = None) -> list[Template]`, where `root=None` means the packaged templates; `read_optional_skills(root: Path) -> tuple[str, ...]`; `read_excluded(root: Path) -> tuple[str, ...]`, the normalised `[kit] exclude`; `is_excluded(path: str, excluded: Sequence[str]) -> bool`; `git(root: Path, *args: str, stdin: bytes | None = None, allowed: tuple[int, ...] = (0,)) -> bytes`; `work_tree_root(start: Path) -> Path`; `is_clean(root: Path) -> bool`; fixtures `kit_variables`, `make_templates`, `git_repo`, `run_git`, `commit_all` and `write_kit_settings`.

The `kit.toml` format, which plans 3 and 5 extend:

```toml
seeded = []           # template paths written once, then owned by the project
new_project = []      # seeded only when init starts a Python project (no pyproject.toml yet)
executable = []       # managed paths written with the executable bit
optional_skills = []  # skill directories under .agents/skills/ installed only when opted in
variables = []        # names seeded templates may use as {{name}}
```

Every template not listed under `seeded` or `new_project` is managed. The index gives the lists after all five plans: this plan adds `devctl` and the `devctl_project` seed (Task 9), plan 3 the hook and the `AGENTS.md` and `.gitignore` seeds, plan 4 `askpass.py`, and plan 5 `rs-contribute`.

- [ ] **Step 1: Write the failing tests.** Create `tests/conftest.py`:

```python
"""Shared offline fixtures: small Kit template trees and scratch git repositories."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

KIT_TOML = """\
seeded = [".github/CODEOWNERS", ".rapid-ship/project.toml", "AGENTS.md"]
new_project = ["pyproject.toml", "src/__package__/__init__.py"]
executable = ["devctl"]
optional_skills = ["rs-extra"]
variables = ["owner", "package", "project_name", "repository"]
"""

TEMPLATE_FILES = {
    "kit.toml": KIT_TOML,
    "common/devctl": "#!/bin/sh\necho devctl\n",
    "common/tools/devctl/devctl/cli.py": "one\ntwo\nthree\nfour\nfive\n",
    "common/AGENTS.md": "# {{project_name}}\n",
    "common/.github/CODEOWNERS": "* @{{owner}}\n",
    "common/.agents/skills/rs-demo/SKILL.md": "demo\n",
    "common/.agents/skills/rs-extra/SKILL.md": "extra\n",
    "python/.rapid-ship/project.toml": 'stack = "python"\n\n[kit]\noptional = []\n',
    "neutral/.rapid-ship/project.toml": 'stack = "neutral"\n\n[kit]\noptional = []\n',
    "python/pyproject.toml": '[project]\nname = "{{project_name}}"\n',
    "python/src/__package__/__init__.py": '"""{{package}}."""\n',
}


@pytest.fixture
def kit_variables() -> dict[str, str]:
    return {
        "project_name": "demo-app",
        "package": "demo_app",
        "owner": "octo",
        "repository": "octo/demo-app",
    }


@pytest.fixture
def make_templates(tmp_path: Path) -> Callable[..., Path]:
    """Write a template tree under tmp_path/name. changes add or replace files; None removes one."""

    def make(name: str = "templates", changes: Mapping[str, str | None] | None = None) -> Path:
        root = tmp_path / name
        for relative, content in {**TEMPLATE_FILES, **(changes or {})}.items():
            if content is not None:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        return root

    return make


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def run_git() -> Callable[..., str]:
    return _git


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """An empty repository on main. Its commits need no signing and run no hooks."""
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    settings = {
        "user.name": "Test",
        "user.email": "test@example.invalid",
        "commit.gpgsign": "false",
        "core.hooksPath": "/dev/null",
    }
    for key, value in settings.items():
        _git(root, "config", key, value)
    return root


@pytest.fixture
def commit_all() -> Callable[..., None]:
    def commit(root: Path, message: str = "Commit") -> None:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "--allow-empty", "-m", message)

    return commit


@pytest.fixture
def write_kit_settings() -> Callable[..., None]:
    """Replace root/.rapid-ship/project.toml with a Python one holding these [kit] lists."""

    def write(root: Path, *, optional: Sequence[str] = (), exclude: Sequence[str] = ()) -> None:
        path = root / ".rapid-ship/project.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        kit = f"optional = {json.dumps(list(optional))}\nexclude = {json.dumps(list(exclude))}\n"
        path.write_text(
            f'stack = "python"\n\n[kit]\n{kit}'
        )  # a JSON list of strings is a TOML array

    return write
```

Create `tests/test_kit_templates.py`:

```python
"""Rendering Kit templates for one project, with small template trees (offline)."""

import re

import pytest

from rapid_ship.kit.templates import (
    KitError,
    Template,
    is_excluded,
    load_manifest,
    read_excluded,
    render_files,
)


def by_path(templates):
    return {template.path: template for template in templates}


def test_managed_files_are_copied_and_seeded_files_are_substituted(make_templates, kit_variables):
    root = make_templates()

    rendered = by_path(render_files("python", kit_variables, (), root=root))

    assert rendered["devctl"].kind == "managed"
    assert rendered["devctl"].content == (root / "common/devctl").read_bytes()
    assert rendered["AGENTS.md"] == Template("AGENTS.md", "seeded", b"# demo-app\n", None)
    assert rendered["src/demo_app/__init__.py"].content == b'"""demo_app."""\n'
    assert "src/__package__/__init__.py" not in rendered
    assert list(rendered) == sorted(rendered)


def test_the_stack_layer_overrides_common(make_templates, kit_variables):
    root = make_templates(changes={"common/CLAUDE.md": "common\n", "python/CLAUDE.md": "python\n"})

    assert (
        by_path(render_files("python", kit_variables, (), root=root))["CLAUDE.md"].content
        == b"python\n"
    )
    assert (
        by_path(render_files("neutral", kit_variables, (), root=root))["CLAUDE.md"].content
        == b"common\n"
    )


def test_skill_links_follow_installed_skills_and_optional_skills_need_opt_in(
    make_templates, kit_variables
):
    root = make_templates()

    default = by_path(render_files("neutral", kit_variables, (), root=root))
    opted = by_path(render_files("neutral", kit_variables, ("rs-extra",), root=root))

    link = Template(".claude/skills/rs-demo", "managed", None, "../../.agents/skills/rs-demo")
    assert default[".claude/skills/rs-demo"] == link
    assert ".agents/skills/rs-extra/SKILL.md" not in default
    assert ".claude/skills/rs-extra" not in default
    assert opted[".claude/skills/rs-extra"].link == "../../.agents/skills/rs-extra"
    with pytest.raises(KitError, match="unknown optional Kit skill 'rs-unknown'"):
        render_files("neutral", kit_variables, ("rs-unknown",), root=root)


def test_an_empty_owner_comments_out_its_line(make_templates, kit_variables):
    root = make_templates(
        changes={"common/.github/CODEOWNERS": "# Walk\n* @{{owner}}\n# /.github/ @{{owner}}\n"}
    )

    rendered = by_path(render_files("neutral", {**kit_variables, "owner": ""}, (), root=root))

    assert rendered[".github/CODEOWNERS"].content == b"# Walk\n# * @<owner>\n# /.github/ @<owner>\n"


@pytest.mark.parametrize(
    ("changes", "variables", "message"),
    [
        (
            {"common/AGENTS.md": "Owner: {{owner}}\n"},
            {"owner": ""},
            "AGENTS.md: owner must not be empty",
        ),
        ({"common/AGENTS.md": "{{nope}}\n"}, {}, "AGENTS.md: unknown template variable 'nope'"),
        ({"common/tools/__package__/x.py": ""}, {}, "only seeded templates may use __package__"),
        ({"kit.toml": "seeded = []\nextra = []\n"}, {}, "kit.toml: unknown key 'extra'"),
        ({"kit.toml": 'seeded = "AGENTS.md"\n'}, {}, "kit.toml seeded: expected a list"),
    ],
)
def test_template_errors_name_the_file(make_templates, kit_variables, changes, variables, message):
    root = make_templates(changes=changes)

    with pytest.raises(KitError, match=message):
        render_files("neutral", {**kit_variables, **variables}, (), root=root)


def test_symlinks_in_the_template_tree_are_refused(make_templates, kit_variables):
    root = make_templates()
    (root / "common/alias").symlink_to("devctl")

    with pytest.raises(KitError, match="alias is a symlink"):
        render_files("neutral", kit_variables, (), root=root)


def test_generated_files_in_the_template_tree_are_ignored(make_templates, kit_variables):
    root = make_templates(
        changes={
            "common/tools/devctl/devctl/__pycache__/cli.cpython-312.pyc": "x",
            "common/tools/devctl/.venv/bin/python3.12": "x",
            "common/.DS_Store": "x",
        }
    )
    # uv's environments hold symlinks, which the template walk would otherwise refuse.
    (root / "common/tools/devctl/.venv/bin/python").symlink_to("python3.12")

    paths = by_path(render_files("neutral", kit_variables, (), root=root))

    generated = {"__pycache__", ".venv", ".DS_Store"}
    assert not any(generated & set(path.split("/")) for path in paths)
    assert "tools/devctl/devctl/cli.py" in paths


def test_a_tracked_template_tree_renders_only_what_git_keeps(
    git_repo, make_templates, kit_variables, run_git
):
    root = make_templates(
        "project/templates", {"common/scratch.local": "x\n", "common/kept.local": "x\n"}
    )
    (git_repo / ".gitignore").write_text("*.local\n")
    run_git(git_repo, "add", ".gitignore", "templates")
    run_git(git_repo, "add", "--force", "templates/common/kept.local")
    (root / "common/draft.md").write_text("not added yet\n")

    paths = by_path(render_files("neutral", kit_variables, (), root=root))

    assert "scratch.local" not in paths  # ignored and untracked, so the wheel would not ship it
    assert "kept.local" in paths  # tracked, though an ignore pattern matches it
    assert "draft.md" in paths  # untracked but not ignored
    assert "devctl" in paths


def test_an_untracked_template_tree_inside_a_repository_is_read_as_it_is(
    git_repo, make_templates, kit_variables
):
    # An installed copy can sit in a project's ignored .venv. Its kit.toml is not tracked there.
    (git_repo / ".gitignore").write_text(".venv/\n")
    root = make_templates("project/.venv/site-packages/rapid_ship/templates")

    paths = by_path(render_files("neutral", kit_variables, (), root=root))

    assert {"devctl", "AGENTS.md", ".claude/skills/rs-demo"} <= set(paths)


def test_the_manifest_reads_every_list(make_templates):
    manifest = load_manifest(make_templates())

    assert manifest.executable == frozenset({"devctl"})
    assert manifest.optional_skills == frozenset({"rs-extra"})
    assert "src/__package__/__init__.py" in manifest.new_project


def test_kit_exclude_is_read_and_normalised(tmp_path, write_kit_settings):
    write_kit_settings(tmp_path, exclude=["devctl", "tools/devctl/", "./.agents/skills/rs-demo"])
    assert read_excluded(tmp_path) == ("devctl", "tools/devctl", ".agents/skills/rs-demo")

    (tmp_path / ".rapid-ship/project.toml").write_text('stack = "python"\n')
    assert read_excluded(tmp_path) == ()


@pytest.mark.parametrize("value", ['"devctl"', '["../outside"]', '["/etc/passwd"]', '[""]', "[1]"])
def test_an_invalid_kit_exclude_is_an_error(tmp_path, value):
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / ".rapid-ship/project.toml").write_text(
        f'stack = "python"\n\n[kit]\nexclude = {value}\n'
    )

    with pytest.raises(KitError, match=re.escape(".rapid-ship/project.toml [kit] exclude:")):
        read_excluded(tmp_path)


def test_an_excluded_directory_covers_its_files_and_a_skill_directory_its_link():
    excluded = ("devctl", "tools/devctl", ".agents/skills/rs-demo")

    for path in (
        "devctl",
        "tools/devctl/devctl/cli.py",
        ".agents/skills/rs-demo/SKILL.md",
        ".claude/skills/rs-demo",
    ):
        assert is_excluded(path, excluded), path
    for path in (
        "devctl.md",
        "tools/devctl-extra/x.py",
        ".agents/skills/rs-demo2/SKILL.md",
        ".claude/skills/rs-demo2",
    ):
        assert not is_excluded(path, excluded), path
    assert is_excluded(".claude/skills/rs-tdd", (".agents/skills",))
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_templates.py -q`. Expected: `ImportError: cannot import name 'load_manifest' from 'rapid_ship.kit.templates'`.

- [ ] **Step 3: Implement.** Create `rapid_ship/kit/git.py`; Task 3 and plan 5's `adopt` use it too:

```python
"""git calls shared by the Kit commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rapid_ship.kit.templates import KitError, KitRefusal


def git(
    root: Path, *args: str, stdin: bytes | None = None, allowed: tuple[int, ...] = (0,)
) -> bytes:
    """Run git in root and return stdout. Paths are literal, never pathspec patterns."""
    try:
        result = subprocess.run(
            ["git", "--literal-pathspecs", *args],
            cwd=root,
            input=stdin,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise KitError(f"cannot run git: {error}") from error
    if result.returncode not in allowed:
        raise KitError(f"git {args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def work_tree_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise KitError(f"cannot run git: {error}") from error
    if result.returncode != 0:
        raise KitRefusal(f"{start} is not inside a git work tree; run git init first")
    return Path(result.stdout.strip()).resolve()


def is_clean(root: Path) -> bool:
    return git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all") == b""
```

Then, in `rapid_ship/kit/templates.py`:

```python
PROJECT_SETTINGS = ".rapid-ship/project.toml"
_VARIABLE = re.compile(r"\{\{([a-z_]+)\}\}")
_GENERATED = frozenset(
    {".venv", "__pycache__", ".DS_Store"}
)  # names skipped in every template tree
_MANIFEST_KEYS = ("seeded", "new_project", "executable", "optional_skills", "variables")


@dataclass(frozen=True)
class KitManifest:
    seeded: frozenset[str]
    new_project: frozenset[str]
    executable: frozenset[str]
    optional_skills: frozenset[str]
    variables: frozenset[str]


def packaged_templates() -> Path:
    # rapid_ship is a regular package installed unpacked, so this is a filesystem path.
    return Path(str(files("rapid_ship").joinpath("templates")))


def installed_version() -> str:
    return importlib.metadata.version("rapid-ship")


def load_manifest(root: Path | None = None) -> KitManifest:
    path = (root or packaged_templates()) / "kit.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise KitError(f"cannot read the Kit manifest {path}: {error}") from error
    unknown = sorted(set(data) - set(_MANIFEST_KEYS))
    if unknown:
        raise KitError(f"kit.toml: unknown key {unknown[0]!r}")
    lists: dict[str, frozenset[str]] = {}
    for key in _MANIFEST_KEYS:
        items = data.get(key, [])
        if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items):
            raise KitError(f"kit.toml {key}: expected a list of non-empty strings")
        lists[key] = frozenset(items)
    return KitManifest(**lists)


def render_path(path: str, variables: Mapping[str, str]) -> str:
    parts = PurePosixPath(path).parts
    if "__package__" in parts and not variables.get("package"):
        raise KitError(f"{path}: the package variable is required")
    return "/".join(variables["package"] if part == "__package__" else part for part in parts)


def render_files(
    stack: Stack, variables: Mapping[str, str], optional: Sequence[str], *, root: Path | None = None
) -> list[Template]:
    root = root or packaged_templates()
    manifest = load_manifest(root)
    unknown = sorted(set(optional) - manifest.optional_skills)
    if unknown:
        raise KitError(f"unknown optional Kit skill {unknown[0]!r}")
    kept = _kept_by_git(root)
    sources = {
        **_layer(root, "common", kept),
        **_layer(root, stack, kept),
    }  # the stack layer overrides common
    templates: list[Template] = []
    for path, source in sorted(sources.items()):
        skill = _skill(path)
        if skill is not None and skill in manifest.optional_skills and skill not in optional:
            continue
        if path in manifest.seeded or path in manifest.new_project:
            text = _render_text(
                path, source.read_bytes().decode("utf-8"), variables, manifest.variables
            )
            templates.append(
                Template(render_path(path, variables), "seeded", text.encode("utf-8"), None)
            )
        elif "__package__" in PurePosixPath(path).parts:
            raise KitError(f"{path}: only seeded templates may use __package__")
        else:
            templates.append(Template(path, "managed", source.read_bytes(), None))
    skills = sorted({name for template in templates if (name := _skill(template.path)) is not None})
    templates += [
        Template(f".claude/skills/{name}", "managed", None, f"../../.agents/skills/{name}")
        for name in skills
    ]
    return sorted(templates, key=lambda template: template.path)


def _render_text(
    path: str, text: str, variables: Mapping[str, str], declared: frozenset[str]
) -> str:
    """Substitute {{name}}. An empty value renders as <name> and comments out a TOML or CODEOWNERS line."""
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        names = _VARIABLE.findall(line)
        for name in names:
            if name not in declared or name not in variables:
                raise KitError(f"{path}: unknown template variable {name!r}")
        empty = [name for name in names if not variables[name]]
        line = _VARIABLE.sub(lambda match: variables[match.group(1)] or f"<{match.group(1)}>", line)
        if empty and not line.lstrip().startswith("#"):
            if not (path.endswith(".toml") or PurePosixPath(path).name == "CODEOWNERS"):
                raise KitError(f"{path}: {empty[0]} must not be empty")
            line = "# " + line
        lines.append(line)
    return "".join(lines)


def _kept_by_git(root: Path) -> frozenset[str] | None:
    """Root-relative paths git keeps, when root/kit.toml is tracked; otherwise None.

    A source checkout then renders what its wheel ships, since hatch leaves ignored paths out.
    An installed copy is never tracked, even inside another repository's ignored .venv,
    so it is read as it is.
    """
    from rapid_ship.kit.git import (
        git,
    )  # a module-level import would be circular: git.py raises KitError

    # Exit 1: kit.toml is not tracked. Exit 128: not in a work tree. Both print nothing.
    if not git(root, "ls-files", "-z", "--error-unmatch", "--", "kit.toml", allowed=(0, 1, 128)):
        return None
    listed = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", ".")
    return frozenset(os.fsdecode(name) for name in listed.split(b"\0") if name)


def _layer(root: Path, layer: str, kept: frozenset[str] | None) -> dict[str, Path]:
    """Map each template file in root/layer, by its path relative to the layer, to its Path."""
    directory = root / layer
    found: dict[str, Path] = {}
    for current, directories, files in os.walk(directory):  # never enters a symlinked directory
        directories[:] = [name for name in directories if name not in _GENERATED]
        for name in [*directories, *files]:
            path = Path(current, name)
            relative = path.relative_to(directory).as_posix()
            if name in _GENERATED or name.endswith(".pyc"):
                continue
            if kept is not None and f"{layer}/{relative}" not in kept:
                continue  # git does not keep it; real directories land here too
            if path.is_symlink():
                raise KitError(
                    f"template {layer}/{relative} is a symlink; templates must be regular files"
                )
            if path.is_file():
                found[relative] = path
    return found
```

`os.walk` yields nothing for a missing layer directory. The generated names are matched against the path below the layer, so a template root inside some `.venv` is still read. `_skill(path)` returns `parts[2]` when the path has at least four parts starting `.agents/skills`, else `None`. `_kit_table(root)` reads `safe_path(root, PROJECT_SETTINGS)` with `tomllib` and returns its `[kit]` table, or `{}` when it is absent. A read error, an `UnsafePath`, or a `kit` value that is not a table raises `KitError(f"cannot read {PROJECT_SETTINGS}: ...")`. `read_optional_skills(root)` returns `[kit] optional` from it as a tuple, defaulting to `()`; a value that is not a list of strings raises `KitError(f"{PROJECT_SETTINGS} [kit] optional: expected a list of skill names")`. Beside it:

```python
def read_excluded(root: Path) -> tuple[str, ...]:
    """[kit] exclude: Kit paths the project owns, normalised without "./" or a trailing "/"."""
    items = _kit_table(root).get("exclude", [])
    where = f"{PROJECT_SETTINGS} [kit] exclude"
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise KitError(f"{where}: expected a list of repository paths")
    try:
        return tuple("/".join(relative_parts(item)) for item in items)
    except UnsafePath as error:
        raise KitError(f"{where}: {error}") from error


def is_excluded(path: str, excluded: Sequence[str]) -> bool:
    """True when path is an entry or lies below one. A skill directory also covers its link."""
    parts = PurePosixPath(path).parts
    if (
        len(parts) == 3
        and parts[:2] == (".claude", "skills")
        and _covered(f".agents/skills/{parts[2]}", excluded)
    ):
        return True
    return _covered(path, excluded)


def _covered(path: str, excluded: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(f"{entry}/") for entry in excluded)
```

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_kit_templates.py -q` and `uv run mypy`. Expected: all pass; `Success`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/kit/templates.py rapid_ship/kit/git.py tests/conftest.py tests/test_kit_templates.py
git commit -m "feat: render Kit templates for one project

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: `rapid-ship init`

**Files:**
- Modify: `rapid_ship/files.py`
- Create: `rapid_ship/kit/init.py`
- Test: `tests/test_files.py`, `tests/test_kit_init.py`

**Interfaces:**
- Consumes: Tasks 1 and 2, including `git`, `work_tree_root`, `is_clean` and the fixtures `git_repo`, `run_git` and `commit_all`.
- Produces: `create_file(path: Path, content: bytes, *, executable: bool = False) -> None`; `InitResult(stack: Stack, created: tuple[str, ...], skipped: tuple[str, ...], conflicts: tuple[str, ...])`; `resolve_variables(root: Path, *, name: str | None = None, package: str | None = None, owner: str | None = None, repository: str | None = None) -> dict[str, str]`; `init_repository(root: Path, *, stack: Stack | None, variables: Mapping[str, str], templates_root: Path | None = None) -> InitResult`.

**Owner handle.** `--owner <GitHub login>` is optional (spec section 3). With it, CODEOWNERS gets the active Walk line `* @<login>`, and the commented Protected-set lines name the same login. Without it, every owner in CODEOWNERS renders as `<owner>` and the Walk line as `# * @<owner>`; init says so. `rs-setup` step 3.5 then puts the owner's login on every line and uncomments the Walk line before the Setup PR. `--repository owner/name` fills `[github] repository` the same way. Both values are validated, because they are substituted into TOML strings and CODEOWNERS.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_files.py` (import `create_file`; add `import os` if absent):

```python
def test_create_file_never_replaces_or_follows_a_symlink(tmp_path):
    create_file(tmp_path / "new.txt", b"new\n")
    (tmp_path / "link").symlink_to("missing")

    for name in ("new.txt", "link"):
        with pytest.raises(FileExistsError):
            create_file(tmp_path / name, b"other\n")

    assert (tmp_path / "new.txt").read_bytes() == b"new\n"
    assert not (tmp_path / "missing").exists()


def test_create_file_marks_executables(tmp_path):
    create_file(tmp_path / "devctl", b"#!/bin/sh\n", executable=True)

    assert os.access(tmp_path / "devctl", os.X_OK)
```

Create `tests/test_kit_init.py`:

```python
"""rapid-ship init: create-only, all-or-nothing writes into scratch repositories (offline)."""

import errno
import os

import pytest

from rapid_ship.kit import init as init_module
from rapid_ship.kit.init import init_repository, resolve_variables
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.templates import KitError, KitRefusal


def files_in(root):
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if ".git" not in p.relative_to(root).parts
    )


def test_init_writes_every_template_and_records_the_lock(git_repo, make_templates, kit_variables):
    templates = make_templates()

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=templates
    )

    assert result.conflicts == () and result.skipped == ()
    assert set(result.created) == {
        ".agents/skills/rs-demo/SKILL.md",
        ".claude/skills/rs-demo",
        ".github/CODEOWNERS",
        ".rapid-ship/project.toml",
        "AGENTS.md",
        "devctl",
        "pyproject.toml",
        "src/demo_app/__init__.py",
        "tools/devctl/devctl/cli.py",
        LOCK_PATH,
    }
    assert os.readlink(git_repo / ".claude/skills/rs-demo") == "../../.agents/skills/rs-demo"
    assert os.access(git_repo / "devctl", os.X_OK)
    assert (git_repo / ".github/CODEOWNERS").read_text() == "* @octo\n"
    lock = read_lock(git_repo)
    entries = {entry.path: entry for entry in lock.entries}
    assert entries["devctl"].sha256 == file_sha256((templates / "common/devctl").read_bytes())
    assert entries["AGENTS.md"].template_sha256 == file_sha256(b"# demo-app\n")
    assert (lock.stack, dict(lock.variables)) == ("python", kit_variables)


def test_existing_seeded_files_are_skipped_and_still_locked(
    git_repo, make_templates, kit_variables, commit_all
):
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.skipped == ("AGENTS.md",)
    assert (git_repo / "AGENTS.md").read_text() == "# Ours\n"
    assert {e.path: e.kind for e in read_lock(git_repo).entries}["AGENTS.md"] == "seeded"


def test_an_existing_python_project_gets_no_new_project_seeds(
    git_repo, make_templates, kit_variables, commit_all
):
    (git_repo / "pyproject.toml").write_text('[project]\nname = "ours"\n')
    commit_all(git_repo)

    result = init_repository(
        git_repo, stack=None, variables=kit_variables, templates_root=make_templates()
    )

    assert result.stack == "python"
    assert not (git_repo / "src").exists()
    assert (git_repo / "pyproject.toml").read_text() == '[project]\nname = "ours"\n'
    assert {"pyproject.toml", "src/demo_app/__init__.py"}.isdisjoint(
        e.path for e in read_lock(git_repo).entries
    )


def link_github_outside(root):
    outside = root.parent / "outside"
    outside.mkdir()
    (root / ".github").symlink_to(outside)


@pytest.mark.parametrize(
    ("arrange", "conflict"),
    [
        (lambda root: (root / "devctl").write_text("ours\n"), "devctl: exists"),
        (
            lambda root: (root / "devctl").symlink_to("missing-target"),
            "devctl: devctl is a symlink",
        ),
        (
            lambda root: (root / "tools").write_text("a file\n"),
            "tools/devctl/devctl/cli.py: tools is not a directory",
        ),
        (
            lambda root: (root / ".gitignore").write_text("tools/\n"),
            "tools/devctl/devctl/cli.py: ignored by git",
        ),
        (link_github_outside, ".github/CODEOWNERS: .github is a symlink"),
    ],
)
def test_init_writes_nothing_on_any_conflict(
    git_repo, make_templates, kit_variables, commit_all, arrange, conflict
):
    arrange(git_repo)
    commit_all(git_repo)
    before = files_in(git_repo)

    result = init_repository(
        git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
    )

    assert result.created == ()
    assert any(item.startswith(conflict) for item in result.conflicts)
    assert files_in(git_repo) == before
    outside = git_repo.parent / "outside"
    assert not outside.exists() or list(outside.iterdir()) == []


def test_init_refuses_a_dirty_tree_an_existing_lock_or_a_non_repository(
    tmp_path, git_repo, make_templates, kit_variables, commit_all
):
    templates = make_templates()
    (git_repo / "notes.txt").write_text("draft\n")
    with pytest.raises(KitRefusal, match="the work tree has changes"):
        init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)
    assert files_in(git_repo) == ["notes.txt"]

    (git_repo / ".rapid-ship").mkdir()
    (git_repo / LOCK_PATH).write_text("")
    commit_all(git_repo)
    with pytest.raises(KitRefusal, match="kit.lock exists"):
        init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(KitRefusal, match="not inside a git work tree"):
        init_repository(plain, stack="python", variables=kit_variables, templates_root=templates)


def test_init_needs_a_stack_without_pyproject(git_repo, make_templates, kit_variables):
    with pytest.raises(KitError, match="pass --stack python or --stack neutral"):
        init_repository(
            git_repo, stack=None, variables=kit_variables, templates_root=make_templates()
        )


def test_the_stack_version_wins_on_init(git_repo, make_templates, kit_variables):
    path = "tools/devctl/devctl/stack.py"
    templates = make_templates(changes={f"common/{path}": "common\n", f"python/{path}": "python\n"})

    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=templates)

    assert (git_repo / path).read_text() == "python\n"
    assert {e.path: e for e in read_lock(git_repo).entries}[path].sha256 == file_sha256(b"python\n")


def test_a_failed_write_removes_everything_init_created(
    git_repo, make_templates, kit_variables, monkeypatch
):
    calls = []
    real = init_module.create_file

    def failing(path, content, *, executable=False):
        calls.append(path)
        if len(calls) == 3:
            raise OSError("disk full")
        real(path, content, executable=executable)

    monkeypatch.setattr(init_module, "create_file", failing)

    with pytest.raises(KitError, match="disk full"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


def test_a_refused_symlink_stops_init_without_writing_a_copy(
    git_repo, make_templates, kit_variables, monkeypatch
):
    def refuse(target, path, *rest):  # Path.symlink_to also passes target_is_directory
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr(init_module.os, "symlink", refuse)

    with pytest.raises(KitError, match="Operation not permitted.*removed the files it had created"):
        init_repository(
            git_repo, stack="python", variables=kit_variables, templates_root=make_templates()
        )
    assert files_in(git_repo) == []


def test_variables_default_from_the_directory(tmp_path):
    assert resolve_variables(tmp_path / "Rapid-Ship.app") == {
        "project_name": "Rapid-Ship.app",
        "package": "rapid_ship_app",
        "owner": "",
        "repository": "",
    }


@pytest.mark.parametrize(
    "options",
    [
        {"name": "my project"},
        {"package": "class"},
        {"package": "3d"},
        {"owner": "-octo"},
        {"owner": 'octo"x'},
        {"owner": "o" * 40},
        {"repository": "octo"},
        {"repository": "octo/demo\nx"},
    ],
)
def test_invalid_variables_are_refused(tmp_path, options):
    with pytest.raises(KitError):
        resolve_variables(tmp_path / "demo", **options)
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_files.py tests/test_kit_init.py -q`. Expected: `ImportError: cannot import name 'create_file'` and `ModuleNotFoundError: No module named 'rapid_ship.kit.init'`.

- [ ] **Step 3: Implement.** Add to `rapid_ship/files.py`:

```python
def create_file(path: Path, content: bytes, *, executable: bool = False) -> None:
    """Create path; never replace an existing file or follow a symlink. The umask applies, as for git."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags, 0o777 if executable else 0o666)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
    except OSError:
        path.unlink(missing_ok=True)
        raise
```

Create `rapid_ship/kit/init.py`:

```python
_PROJECT_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")  # PEP 508 name
_LOGIN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")  # GitHub login, at most 39
_REPOSITORY = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/[A-Za-z0-9._-]+")


@dataclass(frozen=True)
class InitResult:
    stack: Stack
    created: tuple[str, ...]  # includes .rapid-ship/kit.lock; empty when there are conflicts
    skipped: tuple[str, ...]  # seeded files that already existed; rs-setup merges them
    conflicts: tuple[str, ...]  # "path: reason"; when present, init wrote nothing


def init_repository(
    root: Path,
    *,
    stack: Stack | None,
    variables: Mapping[str, str],
    templates_root: Path | None = None,
) -> InitResult:
    root = root.resolve()
    top = work_tree_root(root)
    if top != root:
        raise KitRefusal(f"run init from the top of the work tree, {top}")
    if not is_clean(root):
        raise KitRefusal("the work tree has changes; commit or stash them, then run init")
    if os.path.lexists(root / LOCK_PATH):
        raise KitRefusal(f"{LOCK_PATH} exists; use rapid-ship status or rapid-ship sync")
    existing_project = os.path.lexists(root / "pyproject.toml")
    stack = stack or ("python" if existing_project else None)
    if stack is None:
        raise KitError("there is no pyproject.toml; pass --stack python or --stack neutral")
    new_project_only = {
        render_path(path, variables) for path in load_manifest(templates_root).new_project
    }
    templates = [
        template
        for template in render_files(stack, variables, (), root=templates_root)
        if not (existing_project and template.path in new_project_only)
    ]
    writes, skipped, conflicts = _plan(root, templates)
    if conflicts:
        return InitResult(stack, (), tuple(skipped), tuple(conflicts))
    lock = Lock(installed_version(), stack, dict(variables), tuple(entry_for(t) for t in templates))
    created = _write(root, writes, load_manifest(templates_root).executable, lock)
    return InitResult(stack, created, tuple(skipped), ())


def _plan(
    root: Path, templates: Sequence[Template]
) -> tuple[list[tuple[Template, Path]], list[str], list[str]]:
    writes: list[tuple[Template, Path]] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    checked: list[str] = []
    for path in [*(template.path for template in templates), LOCK_PATH]:
        try:
            safe_path(root, path)
            checked.append(path)
        except UnsafePath as error:
            conflicts.append(str(error))
    for template in templates:
        if template.path not in checked:
            continue
        target = safe_path(root, template.path)
        blocker = next(
            (
                p
                for p in reversed(target.parents)
                if p.is_relative_to(root) and p != root and p.exists() and not p.is_dir()
            ),
            None,
        )
        if blocker is not None:
            conflicts.append(f"{template.path}: {blocker.relative_to(root)} is not a directory")
        elif os.path.lexists(target):
            (
                conflicts.append(f"{template.path}: exists")
                if template.kind == "managed"
                else skipped.append(template.path)
            )
        else:
            writes.append((template, target))
    # A Kit file that git ignores could never be committed, so CI would run without it.
    candidates = [template.path for template, _ in writes] + (
        [LOCK_PATH] if LOCK_PATH in checked else []
    )
    if candidates:
        output = git(
            root,
            "check-ignore",
            "-z",
            "--stdin",
            stdin=b"\0".join(map(os.fsencode, candidates)),
            allowed=(0, 1),
        )
        conflicts += [
            f"{os.fsdecode(path)}: ignored by git, so it could not be committed"
            for path in output.split(b"\0")
            if path
        ]
    return writes, skipped, conflicts


def _write(
    root: Path, writes: Sequence[tuple[Template, Path]], executable: frozenset[str], lock: Lock
) -> tuple[str, ...]:
    """Write every file, then the lock. On any failure, remove what was created and stop."""
    created: list[Path] = []
    directories: list[Path] = []
    try:
        for template, target in writes:
            for directory in reversed(target.parents):
                if directory.is_relative_to(root) and directory != root and not directory.exists():
                    directory.mkdir()
                    directories.append(directory)
            if template.link is not None:
                os.symlink(template.link, target)
            else:
                create_file(target, template.content or b"", executable=template.path in executable)
            created.append(target)
        created.append(root / LOCK_PATH)
        write_lock(root, lock)
    except OSError as error:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for directory in reversed(directories):
            with contextlib.suppress(OSError):
                directory.rmdir()
        raise KitError(f"init stopped ({error}) and removed the files it had created") from error
    return (*(template.path for template, _ in writes), LOCK_PATH)
```

Write the `skipped`/`conflicts` branch of `_plan` as an ordinary `if`/`else` (the one-line form above is for brevity). `resolve_variables` defaults `project_name` to `root.name` and `package` to `re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")`. It raises `KitError` when the project name does not match `_PROJECT_NAME`, the package is not an identifier or is a keyword, the owner does not match `_LOGIN` or is longer than 39 characters, or the repository does not match `_REPOSITORY`. Each message names the value and its option, for example `owner '-x' is not a GitHub login; check --owner`. It returns all four names, with `""` for an absent owner or repository.

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_files.py tests/test_kit_init.py -q`, then `uv run mypy`. Expected: all pass; `Success`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/files.py rapid_ship/kit/init.py tests/test_files.py tests/test_kit_init.py
git commit -m "feat: vendor the Kit with rapid-ship init

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: `rapid-ship status`

**Files:**
- Create: `rapid_ship/kit/status.py`
- Test: `tests/test_kit_status.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `State = Literal["unchanged", "modified", "missing", "template updated", "excluded"]`; `FileStatus(path: str, kind: Kind, state: State)`; `StatusReport(kit_version: str, installed_version: str, stack: Stack, files: tuple[FileStatus, ...], outdated: tuple[str, ...], not_installed: tuple[str, ...])` with property `strict_ok: bool`; `classify(root: Path, *, templates_root: Path | None = None) -> StatusReport`; `locate(root: Path, relative: str) -> Path`; `fingerprint(root: Path, relative: str) -> str | None`; `entry_fingerprint(entry: LockEntry) -> str`; `template_fingerprint(template: Template) -> str`.

`files` holds every managed entry, plus seeded entries whose template changed. An entry whose path `[kit] exclude` covers is listed as `excluded` instead, whatever its kind, and is never `outdated`. `outdated` holds managed entries whose locked hash or link differs from the installed template, or whose template the Kit dropped. `not_installed` holds managed templates with no lock entry, except excluded paths. `status` reads the list from `project.toml` with `read_excluded` and `is_excluded`, as sync does; the lock records no exclusion.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_kit_status.py`:

```python
"""rapid-ship status: classify the vendored Kit against its lock and the installed templates (offline)."""

from rapid_ship.kit.init import init_repository
from rapid_ship.kit.status import classify


def states(report):
    return {item.path: item.state for item in report.files}


def vendor(root, templates, variables):
    init_repository(root, stack="python", variables=variables, templates_root=templates)


def test_a_fresh_init_is_strictly_current(git_repo, make_templates, kit_variables):
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)

    report = classify(git_repo, templates_root=templates)

    assert set(states(report).values()) == {"unchanged"}
    assert (report.outdated, report.not_installed) == ((), ())
    assert report.strict_ok


def test_modified_and_missing_managed_files(git_repo, make_templates, kit_variables):
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)
    (git_repo / "devctl").write_text("changed\n")
    (git_repo / "tools/devctl/devctl/cli.py").unlink()
    (git_repo / ".claude/skills/rs-demo").unlink()
    (git_repo / ".claude/skills/rs-demo").write_text("a copy\n")

    report = classify(git_repo, templates_root=templates)

    assert states(report)["devctl"] == "modified"
    assert states(report)["tools/devctl/devctl/cli.py"] == "missing"
    assert states(report)[".claude/skills/rs-demo"] == "modified"
    assert not report.strict_ok


def test_strict_fails_when_the_lock_matches_disk_but_not_the_installed_template(
    git_repo, make_templates, kit_variables
):
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    report = classify(git_repo, templates_root=new)

    assert states(report)["devctl"] == "unchanged"
    assert report.outdated == ("devctl",)
    assert not report.strict_ok


def test_strict_fails_when_a_managed_template_is_not_installed(
    git_repo, make_templates, kit_variables
):
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/.agents/skills/rs-new/SKILL.md": "new\n"})

    report = classify(git_repo, templates_root=new)

    assert report.not_installed == (".agents/skills/rs-new/SKILL.md", ".claude/skills/rs-new")
    assert not report.strict_ok


def test_a_dropped_template_makes_its_entry_outdated(git_repo, make_templates, kit_variables):
    vendor(git_repo, make_templates("old"), kit_variables)
    new = make_templates("new", {"common/tools/devctl/devctl/cli.py": None})

    assert classify(git_repo, templates_root=new).outdated == ("tools/devctl/devctl/cli.py",)


def test_seeded_files_report_only_template_updates(git_repo, make_templates, kit_variables):
    templates = make_templates("old")
    vendor(git_repo, templates, kit_variables)
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    assert "AGENTS.md" not in states(classify(git_repo, templates_root=templates))

    new = make_templates("new", {"common/AGENTS.md": "# {{project_name}}\n\nNew section.\n"})
    report = classify(git_repo, templates_root=new)

    assert states(report)["AGENTS.md"] == "template updated"
    assert report.strict_ok  # --strict covers managed files only


def test_status_ignores_project_files_and_changes_nothing(
    git_repo, make_templates, kit_variables, commit_all, run_git
):
    templates = make_templates()
    vendor(git_repo, templates, kit_variables)
    commit_all(git_repo)
    (git_repo / "notes.md").write_text("mine\n")
    before = run_git(git_repo, "status", "--porcelain")

    report = classify(git_repo, templates_root=templates)

    assert "notes.md" not in states(report)
    assert run_git(git_repo, "status", "--porcelain") == before


def test_excluded_paths_are_reported_and_ignored_by_strict(
    git_repo, make_templates, kit_variables, write_kit_settings
):
    vendor(git_repo, make_templates("old"), kit_variables)
    write_kit_settings(git_repo, exclude=["devctl", "tools/devctl", ".agents/skills/rs-demo"])
    (git_repo / "devctl").write_text("ours\n")
    (git_repo / "tools/devctl/devctl/cli.py").unlink()
    (git_repo / ".claude/skills/rs-demo").unlink()
    new = make_templates(
        "new",
        {"common/devctl": "#!/bin/sh\necho newer\n", "common/tools/devctl/devctl/new.py": "x\n"},
    )

    report = classify(git_repo, templates_root=new)

    assert states(report) == {
        "devctl": "excluded",
        "tools/devctl/devctl/cli.py": "excluded",
        ".agents/skills/rs-demo/SKILL.md": "excluded",
        ".claude/skills/rs-demo": "excluded",
    }
    assert (report.outdated, report.not_installed) == ((), ())
    assert report.strict_ok
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_status.py -q`. Expected: `ModuleNotFoundError: No module named 'rapid_ship.kit.status'`.

- [ ] **Step 3: Implement** `rapid_ship/kit/status.py`:

```python
def locate(root: Path, relative: str) -> Path:
    """Return the path after refusing a symlink in any directory on the way. The last part may be a link."""
    parent = PurePosixPath(relative).parent
    base = root.resolve() if parent == PurePosixPath(".") else safe_path(root, parent.as_posix())
    return base / PurePosixPath(relative).name


def fingerprint(root: Path, relative: str) -> str | None:
    """'sha256:<hex>' for a file, 'link:<target>' for a symlink, 'other' for anything else, None if absent."""
    path = locate(root, relative)
    if not os.path.lexists(path):
        return None
    if path.is_symlink():
        return f"link:{os.readlink(path)}"
    return f"sha256:{file_sha256(path.read_bytes())}" if path.is_file() else "other"


def entry_fingerprint(entry: LockEntry) -> str:
    return f"link:{entry.link}" if entry.link is not None else f"sha256:{entry.sha256}"


def template_fingerprint(template: Template) -> str:
    return (
        f"link:{template.link}"
        if template.link is not None
        else f"sha256:{file_sha256(template.content or b'')}"
    )


def classify(root: Path, *, templates_root: Path | None = None) -> StatusReport:
    lock = read_lock(root)
    templates = {
        t.path: t
        for t in render_files(
            lock.stack, lock.variables, read_optional_skills(root), root=templates_root
        )
    }
    excluded = read_excluded(root)
    files: list[FileStatus] = []
    outdated: list[str] = []
    for entry in lock.entries:
        template = templates.get(entry.path)
        if is_excluded(entry.path, excluded):
            files.append(FileStatus(entry.path, entry.kind, "excluded"))  # the project owns it
            continue
        if entry.kind == "seeded":
            if (
                template is not None
                and template.kind == "seeded"
                and entry.template_sha256 != file_sha256(template.content or b"")
            ):
                files.append(FileStatus(entry.path, "seeded", "template updated"))
            continue
        try:
            disk = fingerprint(root, entry.path)
        except UnsafePath:
            disk = "other"  # a symlinked directory on the way counts as modified
        state: State = (
            "missing"
            if disk is None
            else "unchanged"
            if disk == entry_fingerprint(entry)
            else "modified"
        )
        files.append(FileStatus(entry.path, "managed", state))
        if (
            template is None
            or template.kind != "managed"
            or template_fingerprint(template) != entry_fingerprint(entry)
        ):
            outdated.append(entry.path)
    locked = {entry.path for entry in lock.entries}
    not_installed = sorted(
        p
        for p, t in templates.items()
        if t.kind == "managed" and p not in locked and not is_excluded(p, excluded)
    )
    return StatusReport(
        lock.kit_version,
        installed_version(),
        lock.stack,
        tuple(files),
        tuple(outdated),
        tuple(not_installed),
    )
```

`StatusReport.strict_ok` is true when every managed item's state is `unchanged` or `excluded` and both `outdated` and `not_installed` are empty.

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_kit_status.py -q` and `uv run mypy`. Expected: all pass; `Success`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/kit/status.py tests/test_kit_status.py
git commit -m "feat: classify the vendored Kit with rapid-ship status

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: `rapid-ship sync`

**Files:**
- Create: `rapid_ship/kit/sync.py`
- Test: `tests/test_kit_sync.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `OldTemplates = Callable[[str], Path]` (Kit version to that release's template root); `OpenPullRequest = Callable[[Path, str, str, str, str], str]` (root, branch, base, title, body to URL); `Conflict(path: str, reason: str, diff: str)`; `SyncResult` with list fields `updated`, `merged`, `adopted`, `added`, `deleted`, `released`, `seeded_changed`, `seeded_existing`, `missing`, `conflicts`, plus `kit_version: str`, `branch: str | None`, `pull_request: str | None` and property `changed: bool`; `sync_repository(root: Path, *, in_place: bool, templates_root: Path | None = None, kit_version: str | None = None, old_templates: OldTemplates = released_templates, open_pull_request: OpenPullRequest = push_and_open_pull_request) -> SyncResult`; `KIT_SOURCE = "git+https://github.com/proxy-hatch/rapid-ship"`; `released_templates(version: str) -> Path`, the templates of the tag `v<version>`; `push_and_open_pull_request(...)`; `merge_file(local: bytes, base: bytes, template: bytes, labels: tuple[str, str, str]) -> bytes | None`; `pull_request_body(result: SyncResult, old_version: str) -> str`.

Tests inject `old_templates` with a fixture tree and `open_pull_request` with a recorder, so they need no network. One test replaces `subprocess.run` to check the `uvx` command that fetches a tag. `git` runs for real in scratch repositories.

Decision table for each managed path. "Template" means the installed one, "entry" the lock entry, "disk" the file's fingerprint:

| Entry | Template | Disk | Action |
| --- | --- | --- | --- |
| none | present | absent | create; add entry (`added`) |
| none | present | equals template | entry only (`adopted`) |
| none | present | other | conflict: exists and is not managed |
| present | none | absent or equals entry | delete the file and empty parents; drop entry (`deleted`) |
| present | none | other | keep the file; drop entry (`released`) |
| present | present | absent | leave it (`missing`) |
| present | equals entry | any | nothing |
| present | changed | equals template | entry only (`adopted`) |
| present | changed | equals entry | replace, keeping the mode (`updated`) |
| present | changed | other, symlink involved | conflict |
| present | changed | other | three-way merge; clean: write and record the template's hash (`merged`); conflict: leave file and entry |

The table applies only to paths `[kit] exclude` does not cover (`is_excluded`, Task 2). For an excluded path, managed or seeded, sync takes no action: no write, no merge, no delete, no new entry and no bucket. Its lock entry, if any, goes back unchanged. The lock keeps no mark, so a path that leaves the list goes through the table in the next sync, using that kept entry.

Seeded templates: a changed template updates `template_sha256` and lists the path (`seeded_changed`); the file is never read or written. A new seeded template with no entry is created only where nothing exists (`added`) and is otherwise only recorded (`seeded_existing`), as spec section 3, sync step 5, requires. sync never adds or records a new-project seed. This repository's own `sync --in-place` in Task 9 relies on the rule to vendor the `devctl_project` seed.

`--in-place` skips the clean-tree check because rs-setup step 8, rs-contribute step 5 and this repository's dog-food all run it on uncommitted work. That is safe: sync replaces or deletes only files equal to their locked content, and a merge keeps local edits.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_kit_sync.py`:

```python
"""rapid-ship sync with two template versions (offline: the old release and gh are fakes)."""

import errno
import os
import re
import stat
import subprocess

import pytest

from rapid_ship.kit import sync as sync_module
from rapid_ship.kit.init import init_repository
from rapid_ship.kit.lock import LOCK_PATH, file_sha256, read_lock
from rapid_ship.kit.status import classify
from rapid_ship.kit.sync import released_templates, sync_repository
from rapid_ship.kit.templates import KitError, KitRefusal, installed_version

CLI = "tools/devctl/devctl/cli.py"
SKILL = ".agents/skills/rs-demo/SKILL.md"
PROJECT_HOOKS = "tools/devctl/devctl_project/__init__.py"


class PullRequests:
    def __init__(self):
        self.calls = []

    def __call__(self, root, branch, base, title, body):
        self.calls.append((branch, base, title, body))
        return "https://github.com/octo/demo-app/pull/1"


@pytest.fixture
def vendored(git_repo, make_templates, kit_variables, commit_all):
    old = make_templates("old")
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    commit_all(git_repo, "Add the Kit")
    return old


def sync(root, new, old, **options):
    return sync_repository(
        root, templates_root=new, kit_version="9.9.9", old_templates=lambda version: old, **options
    )


def entry(root, path):
    return {item.path: item for item in read_lock(root).entries}[path]


def test_nothing_to_sync_creates_no_branch(git_repo, vendored, run_git):
    pulls = PullRequests()

    result = sync(git_repo, vendored, vendored, in_place=False, open_pull_request=pulls)

    assert not result.changed and pulls.calls == []
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"


def test_an_unchanged_file_is_replaced_on_a_sync_branch_and_keeps_its_mode(
    git_repo, vendored, make_templates, run_git
):
    mode = stat.S_IMODE((git_repo / "devctl").stat().st_mode)
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    pulls = PullRequests()

    result = sync(git_repo, new, vendored, in_place=False, open_pull_request=pulls)

    assert result.updated == ["devctl"]
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"
    assert (
        stat.S_IMODE((git_repo / "devctl").stat().st_mode) == mode
    )  # atomic_replace alone leaves 0o600
    assert run_git(git_repo, "branch", "--show-current").strip() == "rapid-ship/kit-sync-9.9.9"
    assert (
        run_git(git_repo, "log", "-1", "--format=%s").strip()
        == "chore: sync rapid-ship Kit to 9.9.9"
    )
    assert run_git(git_repo, "status", "--porcelain") == ""
    [(branch, base, title, body)] = pulls.calls
    assert (branch, base, title) == (
        "rapid-ship/kit-sync-9.9.9",
        "main",
        "Sync rapid-ship Kit to 9.9.9",
    )
    evidence = body.split("\n## Evidence\n", 1)[1]
    # Plan 3's evidence step needs a "- `<command>`: <result>" item and a "Not covered:" line.
    assert re.search(r"^- `[^`]+`: \S", evidence, flags=re.MULTILINE)
    assert (
        f"- `rapid-ship sync`: rapid-ship {installed_version()} to 9.9.9; 1 updated"
        in evidence.splitlines()
    )
    assert "\nNot covered:" in evidence
    assert read_lock(git_repo).kit_version == "9.9.9"
    assert classify(git_repo, templates_root=new).strict_ok


def test_a_local_edit_merges_cleanly_and_the_lock_keeps_the_template_hash(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})
    asked = []

    result = sync_repository(
        git_repo,
        in_place=True,
        templates_root=new,
        kit_version="9.9.9",
        old_templates=lambda version: asked.append(version) or vendored,
    )

    assert result.merged == [CLI]
    assert asked == [installed_version()]
    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nFIVE\n"
    assert entry(git_repo, CLI).sha256 == file_sha256(b"one\ntwo\nthree\nfour\nFIVE\n")
    report = classify(git_repo, templates_root=new)
    assert {item.path: item.state for item in report.files}[CLI] == "modified"
    assert CLI not in report.outdated


def test_a_conflicting_merge_leaves_the_file_and_its_entry(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("one\ntwo\nthree\nfour\nlocal five\n")
    commit_all(git_repo)
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    [conflict] = result.conflicts
    assert conflict.path == CLI
    assert "-five" in conflict.diff and "+FIVE" in conflict.diff
    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nlocal five\n"
    assert entry(git_repo, CLI) == before


def test_sync_never_touches_seeded_or_project_files(git_repo, vendored, make_templates, commit_all):
    (git_repo / "AGENTS.md").write_text("# Ours\n")
    (git_repo / "docs").mkdir()
    (git_repo / "docs/guide.md").write_text("mine\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/AGENTS.md": "# {{project_name}}\n\nNew.\n", "common/docs/guide.md": "Kit\n"}
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert (git_repo / "AGENTS.md").read_text() == "# Ours\n"
    assert (git_repo / "docs/guide.md").read_text() == "mine\n"
    assert result.seeded_changed == ["AGENTS.md"]
    assert [conflict.path for conflict in result.conflicts] == ["docs/guide.md"]
    assert entry(git_repo, "AGENTS.md").template_sha256 == file_sha256(b"# demo-app\n\nNew.\n")
    assert "docs/guide.md" not in {item.path for item in read_lock(git_repo).entries}


def test_new_seeded_templates_are_created_only_where_absent(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / "README.md").write_text("ours\n")
    commit_all(git_repo)
    manifest = (
        (vendored / "kit.toml")
        .read_text()
        .replace('"AGENTS.md"]', '"AGENTS.md", "CONTRIBUTING.md", "README.md"]')
        .replace(
            '"src/__package__/__init__.py"]', '"src/__package__/__init__.py", "tests/test_new.py"]'
        )
    )
    new = make_templates(
        "new",
        {
            "kit.toml": manifest,
            "common/CONTRIBUTING.md": "# {{project_name}}\n",
            "common/README.md": "Kit\n",
            "python/tests/test_new.py": "x = 1\n",
        },
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.added == ["CONTRIBUTING.md"]
    assert result.seeded_existing == ["README.md"]
    assert (git_repo / "CONTRIBUTING.md").read_text() == "# demo-app\n"
    assert (git_repo / "README.md").read_text() == "ours\n"
    assert not (git_repo / "tests/test_new.py").exists()  # a new-project seed
    assert "tests/test_new.py" not in {item.path for item in read_lock(git_repo).entries}


def test_dropped_files_are_deleted_only_when_unchanged(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / "devctl").write_text("ours\n")
    commit_all(git_repo)
    new = make_templates("new", {"common/devctl": None, f"common/{CLI}": None})

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.deleted == [CLI]
    assert not (git_repo / "tools").exists()
    assert result.released == ["devctl"]
    assert (git_repo / "devctl").read_text() == "ours\n"
    assert {"devctl", CLI}.isdisjoint(item.path for item in read_lock(git_repo).entries)


def test_opting_in_to_an_optional_skill_adds_it(git_repo, vendored):
    (git_repo / ".rapid-ship/project.toml").write_text(
        'stack = "python"\n\n[kit]\noptional = ["rs-extra"]\n'
    )

    result = sync(git_repo, vendored, vendored, in_place=True)

    assert result.added == [".agents/skills/rs-extra/SKILL.md", ".claude/skills/rs-extra"]
    assert os.readlink(git_repo / ".claude/skills/rs-extra") == "../../.agents/skills/rs-extra"


@pytest.mark.parametrize("in_place", [True, False])
def test_a_refused_symlink_leaves_nothing_half_written(
    git_repo, vendored, make_templates, commit_all, run_git, monkeypatch, in_place
):
    (git_repo / ".rapid-ship/project.toml").write_text(
        'stack = "python"\n\n[kit]\noptional = ["rs-extra"]\n'
    )
    commit_all(git_repo)
    skill = git_repo / ".agents/skills/rs-demo/SKILL.md"
    mode = stat.S_IMODE(skill.stat().st_mode)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/.agents/skills/rs-demo/SKILL.md": "demo, revised\n"})
    pulls = PullRequests()

    def refuse(target, path, *rest):  # Path.symlink_to also passes target_is_directory
        raise OSError(errno.EPERM, "Operation not permitted", str(path))

    monkeypatch.setattr("os.symlink", refuse)

    with pytest.raises(KitError, match="sync stopped .*Operation not permitted.*restored"):
        sync(git_repo, new, vendored, in_place=in_place, open_pull_request=pulls)
    # In path order, sync replaced rs-demo's SKILL.md and created rs-extra's before the link failed.
    assert skill.read_text() == "demo\n"
    assert stat.S_IMODE(skill.stat().st_mode) == mode
    assert not os.path.lexists(git_repo / ".agents/skills/rs-extra")
    assert not os.path.lexists(git_repo / ".claude/skills/rs-extra")
    assert (git_repo / LOCK_PATH).read_bytes() == lock
    assert run_git(git_repo, "status", "--porcelain") == ""
    assert run_git(git_repo, "branch", "--show-current").strip() == "main"
    assert run_git(git_repo, "branch", "--list", "rapid-ship/*") == ""
    assert pulls.calls == []


def test_old_templates_come_from_the_version_tag(make_templates, monkeypatch):
    old = make_templates("cache/rapid_ship/templates")
    commands = []

    def fake_run(command, **options):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=f"{old.parent}\n", stderr="")

    monkeypatch.setattr(sync_module.subprocess, "run", fake_run)

    assert released_templates("0.2.0") == old
    assert commands[0][:3] == [
        "uvx",
        "--from",
        "git+https://github.com/proxy-hatch/rapid-ship@v0.2.0",
    ]
    with pytest.raises(KitError, match="is not a release version"):
        released_templates("main --index-url https://example.invalid")
    assert len(commands) == 1


def test_an_unavailable_base_turns_merges_into_conflicts_and_applies_the_rest(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/devctl": "#!/bin/sh\necho newer\n", f"common/{CLI}": "changed\n"}
    )

    def offline(version):
        raise KitError(f"cannot fetch rapid-ship {version}: offline")

    result = sync_repository(
        git_repo, in_place=True, templates_root=new, kit_version="9.9.9", old_templates=offline
    )

    assert result.updated == ["devctl"]
    assert [(c.path, "offline" in c.reason) for c in result.conflicts] == [(CLI, True)]


def test_a_locked_copy_that_is_not_the_old_template_has_no_merge_base(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    other = make_templates("other", {f"common/{CLI}": "not the locked template\n"})
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, other, in_place=True)

    assert [c.path for c in result.conflicts] == [CLI]
    assert "no merge base" in result.conflicts[0].reason


def test_in_place_accepts_a_dirty_tree_and_commits_nothing(
    git_repo, vendored, make_templates, run_git
):
    (git_repo / "notes.md").write_text("draft\n")
    head = run_git(git_repo, "rev-parse", "HEAD")
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == ["devctl"] and result.branch is None
    assert run_git(git_repo, "rev-parse", "HEAD") == head
    assert (git_repo / "notes.md").read_text() == "draft\n"


def test_branch_mode_refuses_a_dirty_tree_an_existing_branch_or_a_detached_head(
    git_repo, vendored, make_templates, run_git
):
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    (git_repo / "notes.md").write_text("draft\n")
    with pytest.raises(KitRefusal, match="the work tree has changes"):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
    (git_repo / "notes.md").unlink()

    run_git(git_repo, "branch", "rapid-ship/kit-sync-9.9.9")
    with pytest.raises(KitRefusal, match="gh pr list --head rapid-ship/kit-sync-9.9.9"):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
    run_git(git_repo, "branch", "-D", "rapid-ship/kit-sync-9.9.9")

    run_git(git_repo, "switch", "-q", "--detach")
    with pytest.raises(KitRefusal, match="HEAD is detached"):
        sync(git_repo, new, vendored, in_place=False, open_pull_request=PullRequests())
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"


# Owner groups (spec section 3, "Who owns what"): stack Kit, language-agnostic Kit, project extensions.


def test_sync_keeps_the_stack_version_over_the_common_one(
    git_repo, make_templates, kit_variables, commit_all
):
    path = "tools/devctl/devctl/stack.py"
    layers = {f"common/{path}": "common\n", f"python/{path}": "python\n"}
    old = make_templates("old", layers)
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    commit_all(git_repo)

    common_only = sync(
        git_repo,
        make_templates("common", {**layers, f"common/{path}": "common, revised\n"}),
        old,
        in_place=True,
    )
    stack = sync(
        git_repo,
        make_templates("stack", {**layers, f"python/{path}": "python, revised\n"}),
        old,
        in_place=True,
    )

    assert not common_only.changed
    assert stack.updated == [path]
    assert (git_repo / path).read_text() == "python, revised\n"


def test_an_edited_kit_skill_is_merged_and_keeps_its_link(
    git_repo, make_templates, kit_variables, commit_all
):
    old = make_templates("old", {f"common/{SKILL}": "one\ntwo\nthree\nfour\nfive\n"})
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    (git_repo / SKILL).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    new = make_templates("new", {f"common/{SKILL}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, old, in_place=True)

    assert result.merged == [SKILL]
    assert (git_repo / SKILL).read_text() == "ONE\ntwo\nthree\nfour\nFIVE\n"
    assert os.readlink(git_repo / ".claude/skills/rs-demo") == "../../.agents/skills/rs-demo"


def test_a_modified_devctl_project_survives_sync(
    git_repo, make_templates, kit_variables, commit_all
):
    seed = '"""Project verbs."""\n\n\ndef register(commands):\n    pass\n'
    old = make_templates("old", {f"common/{PROJECT_HOOKS}": seed})
    manifest = (
        (old / "kit.toml").read_text().replace('"AGENTS.md"]', f'"AGENTS.md", "{PROJECT_HOOKS}"]')
    )
    (old / "kit.toml").write_text(manifest)
    init_repository(git_repo, stack="python", variables=kit_variables, templates_root=old)
    ours = seed.replace("    pass\n", '    commands.add_parser("seed-demo")\n')
    (git_repo / PROJECT_HOOKS).write_text(ours)
    (git_repo / "tools/devctl/devctl_project/verbs.py").write_text("VERBS = []\n")
    commit_all(git_repo)
    newer_seed = seed + "\n\ndef check_steps():\n    return []\n"
    new = make_templates(
        "new",
        {"kit.toml": manifest, f"common/{PROJECT_HOOKS}": newer_seed, f"common/{CLI}": "changed\n"},
    )

    result = sync(git_repo, new, old, in_place=True)

    assert (result.updated, result.seeded_changed) == ([CLI], [PROJECT_HOOKS])
    assert (git_repo / PROJECT_HOOKS).read_text() == ours
    assert (git_repo / "tools/devctl/devctl_project/verbs.py").read_text() == "VERBS = []\n"


def test_a_project_skill_and_its_link_survive_sync(
    git_repo, vendored, make_templates, commit_all, run_git
):
    (git_repo / ".agents/skills/our-release").mkdir()
    (git_repo / ".agents/skills/our-release/SKILL.md").write_text(
        "---\nname: our-release\ndescription: Ship it.\n---\n"
    )
    (git_repo / ".claude/skills/our-release").symlink_to("../../.agents/skills/our-release")
    commit_all(git_repo)
    new = make_templates(
        "new",
        {f"common/{SKILL}": "demo, revised\n", "common/.agents/skills/rs-new/SKILL.md": "new\n"},
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == [SKILL]
    assert result.added == [".agents/skills/rs-new/SKILL.md", ".claude/skills/rs-new"]
    assert (
        run_git(
            git_repo,
            "status",
            "--porcelain",
            "--",
            ".agents/skills/our-release",
            ".claude/skills/our-release",
        )
        == ""
    )
    assert all("our-release" not in item.path for item in read_lock(git_repo).entries)
    assert all(
        "our-release" not in item.path for item in classify(git_repo, templates_root=new).files
    )


def test_a_project_workflow_survives_beside_a_new_kit_workflow(
    git_repo, vendored, make_templates, commit_all
):
    (git_repo / ".github/workflows").mkdir()
    (git_repo / ".github/workflows/release.yml").write_text("name: release\n")
    commit_all(git_repo)
    new = make_templates(
        "new", {"common/.github/workflows/devctl-check.yml": "name: devctl check\n"}
    )

    result = sync(git_repo, new, vendored, in_place=True)

    assert result.added == [".github/workflows/devctl-check.yml"]
    assert (git_repo / ".github/workflows/release.yml").read_text() == "name: release\n"
    assert ".github/workflows/release.yml" not in {
        item.path for item in read_lock(git_repo).entries
    }


# Project overrides: [kit] exclude.


def test_an_excluded_file_the_project_edited_is_not_merged(
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
    write_kit_settings(git_repo, exclude=[CLI])
    (git_repo / CLI).write_text("ONE\ntwo\nthree\nfour\nfive\n")
    commit_all(git_repo)
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": "one\ntwo\nthree\nfour\nFIVE\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert (git_repo / CLI).read_text() == "ONE\ntwo\nthree\nfour\nfive\n"
    assert (result.merged, result.conflicts) == ([], [])
    assert entry(git_repo, CLI) == before  # the lock records no exclusion


def test_a_deleted_excluded_file_stays_deleted(
    git_repo, vendored, make_templates, commit_all, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").unlink()
    commit_all(git_repo)
    lock = (git_repo / LOCK_PATH).read_bytes()
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})

    result = sync(git_repo, new, vendored, in_place=True)

    assert not os.path.lexists(git_repo / "devctl")
    assert not result.changed and result.missing == []
    assert (git_repo / LOCK_PATH).read_bytes() == lock  # the kit_version stays too
    report = classify(git_repo, templates_root=new)
    assert {item.path: item.state for item in report.files}["devctl"] == "excluded"
    assert report.strict_ok


def test_an_excluded_skill_directory_covers_its_link(
    git_repo, vendored, make_templates, commit_all, run_git, write_kit_settings
):
    write_kit_settings(git_repo, exclude=[".agents/skills/rs-demo", ".agents/skills/rs-new"])
    run_git(git_repo, "rm", "-q", "-r", ".agents/skills/rs-demo", ".claude/skills/rs-demo")
    commit_all(git_repo)
    new = make_templates(
        "new",
        {f"common/{SKILL}": "demo, revised\n", "common/.agents/skills/rs-new/SKILL.md": "new\n"},
    )

    result = sync(git_repo, new, vendored, in_place=True)

    for name in ("rs-demo", "rs-new"):
        assert not os.path.lexists(git_repo / ".agents/skills" / name)
        assert not os.path.lexists(git_repo / ".claude/skills" / name)
    assert not result.changed and result.missing == []
    locked = {item.path for item in read_lock(git_repo).entries}
    assert {SKILL, ".claude/skills/rs-demo"} <= locked  # kept for when the exclusion ends
    assert all("rs-new" not in path for path in locked)
    report = classify(git_repo, templates_root=new)
    assert report.not_installed == () and report.strict_ok


def test_sync_never_deletes_an_excluded_file_the_kit_dropped(
    git_repo, vendored, make_templates, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["tools/devctl"])
    before = entry(git_repo, CLI)
    new = make_templates("new", {f"common/{CLI}": None})

    result = sync(git_repo, new, vendored, in_place=True)

    assert (git_repo / CLI).read_text() == "one\ntwo\nthree\nfour\nfive\n"
    assert (result.deleted, result.released) == ([], [])
    assert entry(git_repo, CLI) == before


def test_removing_a_path_from_exclude_restores_normal_handling(
    git_repo, vendored, make_templates, write_kit_settings
):
    write_kit_settings(git_repo, exclude=["devctl"])
    new = make_templates("new", {"common/devctl": "#!/bin/sh\necho newer\n"})
    assert not sync(git_repo, new, vendored, in_place=True).changed
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho devctl\n"

    write_kit_settings(git_repo, exclude=[])
    result = sync(git_repo, new, vendored, in_place=True)

    assert result.updated == [
        "devctl"
    ]  # the kept entry still matched the file, so sync replaced it
    assert (git_repo / "devctl").read_text() == "#!/bin/sh\necho newer\n"
    assert entry(git_repo, "devctl").sha256 == file_sha256(b"#!/bin/sh\necho newer\n")
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_sync.py -q`. Expected: `ModuleNotFoundError: No module named 'rapid_ship.kit.sync'`.

- [ ] **Step 3: Implement** `rapid_ship/kit/sync.py`. `SyncResult` is a mutable dataclass whose list fields default to empty lists; `changed` is true when any of `updated`, `merged`, `adopted`, `added`, `deleted`, `released`, `seeded_changed` or `seeded_existing` is non-empty. Editing `[kit] exclude` changes no lock entry, so when every template change falls under the list, sync writes nothing, opens no PR and the lock keeps its `kit_version`. The core:

```python
def sync_repository(
    root,
    *,
    in_place,
    templates_root=None,
    kit_version=None,
    old_templates=released_templates,
    open_pull_request=push_and_open_pull_request,
) -> SyncResult:
    root = root.resolve()
    lock = read_lock(root)
    if not in_place and not is_clean(root):
        raise KitRefusal("the work tree has changes; commit them first, or use --in-place")
    version = kit_version or installed_version()
    optional = read_optional_skills(root)
    excluded = read_excluded(root)
    manifest = load_manifest(templates_root)
    rendered = render_files(lock.stack, lock.variables, optional, root=templates_root)
    # Excluded paths get no action at all; their lock entries go back unchanged below.
    new = {t.path: t for t in rendered if not is_excluded(t.path, excluded)}
    result = SyncResult(kit_version=version)
    entries = {entry.path: entry for entry in lock.entries}
    planned = {path: entry for path, entry in entries.items() if not is_excluded(path, excluded)}
    writes: dict[str, Template] = {}
    merges: dict[str, bytes] = {}
    deletes: list[str] = []
    bases = _Bases(old_templates, lock, optional)
    _plan_managed(root, lock, new, bases, planned, writes, merges, deletes, result, version)
    new_project_only = {render_path(path, lock.variables) for path in manifest.new_project}
    _plan_seeded(root, new, planned, writes, result, new_project_only)
    # [kit] exclude is the only record of an exclusion, so the lock carries no mark.
    entries = {
        **planned,
        **{path: entry for path, entry in entries.items() if is_excluded(path, excluded)},
    }
    if not result.changed:
        result.kit_version = lock.kit_version
        return result
    branch = f"rapid-ship/kit-sync-{version}"
    base = None if in_place else _start_branch(root, branch)
    undo = _Undo(root)
    try:
        for path, template in writes.items():  # managed paths in path order, then new seeded files
            _write_template(root, template, path in manifest.executable, undo)
        for path, content in merges.items():
            undo.before(locate(root, path))
            _replace(locate(root, path), content, path in manifest.executable)
        for path in deletes:
            undo.before(locate(root, path))
            _delete(root, path)
        write_lock(
            root, Lock(version, lock.stack, lock.variables, tuple(entries.values()))
        )  # atomic, last
    except OSError as error:
        raise _stopped(root, error, undo, base, branch) from error
    if base is not None:
        result.branch = branch
        touched = sorted({*result.updated, *result.merged, *result.added, *result.deleted})
        git(root, "add", "--all", "--", *touched, LOCK_PATH)
        # The commit holds only Kit files; CI runs the full check on the pull request.
        git(
            root,
            "commit",
            "--no-verify",
            "--quiet",
            "--message",
            f"chore: sync rapid-ship Kit to {version}",
        )
        title = f"Sync rapid-ship Kit to {version}"
        result.pull_request = open_pull_request(
            root, result.branch, base, title, pull_request_body(result, lock.kit_version)
        )
    return result
```

`_plan_managed` walks `sorted(locked | templates)` over the managed entries in its `entries` argument, which is `planned`, and the managed templates in `new`, and follows the decision table in that order, so `writes` lists managed paths in path order. Both exclude every excluded path, so it never sees one. It uses `fingerprint`, `entry_fingerprint` and `template_fingerprint` from Task 4. An `UnsafePath` from `fingerprint` becomes `Conflict(path, f"{error}; sync never writes through a symlink", "")`. "Add", "update" and "adopt" set `entries[path] = entry_for(template)`. "Delete", "release" and the absent-and-dropped case remove `entries[path]`. A merge:

```python
def _merge(root, path, entry, template, bases, result, version) -> bytes | None:
    if entry.link is not None or template.link is not None:
        result.conflicts.append(
            Conflict(path, "a changed symlink; set it to the template's link by hand", "")
        )
        return None
    new_content = template.content or b""
    try:
        base = bases.content(path, entry)
    except KitError as error:
        result.conflicts.append(Conflict(path, str(error), ""))
        return None
    labels = ("local", f"rapid-ship {bases.version}", f"rapid-ship {version}")
    merged = merge_file(locate(root, path).read_bytes(), base, new_content, labels)
    if merged is None:
        reason = "local changes conflict with the template change; apply the diff by hand"
        result.conflicts.append(
            Conflict(path, reason, _diff(path, base, new_content, bases.version, version))
        )
    return merged


def merge_file(
    local: bytes, base: bytes, template: bytes, labels: tuple[str, str, str]
) -> bytes | None:
    """Three-way merge with git merge-file. None means it conflicted."""
    with tempfile.TemporaryDirectory(prefix="rapid-ship-merge-") as temporary:
        directory = Path(temporary)
        for name, content in (("local", local), ("base", base), ("template", template)):
            (directory / name).write_bytes(content)
        command = [
            "git",
            "merge-file",
            "--stdout",
            "-L",
            labels[0],
            "-L",
            labels[1],
            "-L",
            labels[2],
            "local",
            "base",
            "template",
        ]
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True, check=False)
        except OSError as error:
            raise KitError(f"cannot run git merge-file: {error}") from error
    if result.returncode == 0:
        return result.stdout
    if 0 < result.returncode < 128:  # the number of conflicts; git exits 255 on an error
        return None
    raise KitError(f"git merge-file failed: {result.stderr.decode(errors='replace').strip()}")
```

On a merge, `entries[path] = entry_for(template)`: the lock keeps the template's hash, so `status` still shows the file as modified and the next merge uses this template as its base. `_Bases` exposes `version`, the lock's Kit version, and fetches that release once, on the first merge: it calls `old_templates(lock.kit_version)`, keeps only the opted-in skills that the old manifest knows, and renders with `lock.stack` and `lock.variables`. `content(path, entry)` raises `KitError(f"the locked copy is not rapid-ship {version}'s template, so there is no merge base")` unless the old template's hash equals `entry.sha256`. A fetch failure is kept and raised again for every later merge. `_diff` is `difflib.unified_diff` over the UTF-8 text (errors replaced), with `fromfile`/`tofile` naming each version.

`_plan_seeded` follows the seeded rules above. A new seeded template whose path is absent goes into `writes`, so it is written with `create_file` and can never replace a file that appears meanwhile.

`planned` never holds an excluded path, so the excluded entries put back cannot collide with a planned one. `write_lock` sorts the result by path.

A failed write must leave nothing half-written (spec section 4), so sync keeps what it changed in memory and puts it back:

```python
@dataclass
class _Undo:
    """What sync changed, so a failed sync can put the work tree back."""

    root: Path
    replaced: list[tuple[Path, bytes, str | None, int]] = field(
        default_factory=list
    )  # path, bytes, link, mode
    created: list[Path] = field(
        default_factory=list
    )  # files, links and directories, in creation order

    def before(self, path: Path) -> None:
        """Keep an existing file or link before sync replaces or deletes it."""
        if path.is_symlink():
            self.replaced.append((path, b"", str(path.readlink()), 0))
        elif path.is_file():
            self.replaced.append((path, path.read_bytes(), None, stat.S_IMODE(path.stat().st_mode)))

    def make_parents(self, path: Path) -> None:
        for directory in reversed(path.parents):
            if (
                directory.is_relative_to(self.root)
                and directory != self.root
                and not directory.exists()
            ):
                directory.mkdir()
                self.created.append(directory)

    def restore(self) -> None:
        for path in reversed(self.created):
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        for path, content, link, mode in reversed(self.replaced):
            path.parent.mkdir(parents=True, exist_ok=True)  # _delete may have removed it
            if os.path.lexists(path):
                path.unlink()
            if link is not None:
                path.symlink_to(link)
            else:
                atomic_replace(path, content, mode=mode)


def _stopped(root: Path, error: OSError, undo: _Undo, base: str | None, branch: str) -> KitError:
    try:
        undo.restore()
    except OSError as failure:
        return KitError(
            f"sync stopped ({error}) and could not restore every file ({failure}); check git status"
        )
    if base is None:
        return KitError(f"sync stopped ({error}) and restored the files it had changed")
    git(root, "switch", "--quiet", base)
    git(root, "branch", "--quiet", "--delete", "--force", branch)
    return KitError(
        f"sync stopped ({error}) and restored the files it had changed; back on {base}, {branch} deleted"
    )


def _write_template(root: Path, template: Template, executable: bool, undo: _Undo) -> None:
    target = locate(root, template.path)
    undo.make_parents(target)
    content = template.content or b""
    if template.kind == "seeded" or not os.path.lexists(target):
        # create_file and os.symlink never replace, so a seeded file stays the project's.
        if template.link is not None:
            os.symlink(template.link, target)
        else:
            create_file(target, content, executable=executable)
        undo.created.append(target)  # only after it exists, so a failed create removes nothing
        return
    undo.before(target)
    if template.link is not None:
        target.unlink()
        os.symlink(template.link, target)
    else:
        _replace(target, content, executable)


def _replace(path: Path, content: bytes, executable: bool) -> None:
    """Replace a file's bytes and keep its mode; atomic_replace alone would publish 0o600."""
    mode = stat.S_IMODE(path.stat().st_mode)
    if executable:
        mode |= (mode & 0o444) >> 2
    atomic_replace(path, content, mode=mode)


KIT_SOURCE = "git+https://github.com/proxy-hatch/rapid-ship"


def released_templates(version: str) -> Path:
    """The template root of the Kit release tagged v<version> (spec section 3).

    uv builds the tag's wheel with its declared backend, hatchling. The script below finds the
    package without importing it, so no rapid-ship code from the tag runs.
    """
    if not re.fullmatch(r"[0-9][0-9A-Za-z.+!-]*", version):
        raise KitError(f"the lock's kit_version {version!r} is not a release version")
    source = f"{KIT_SOURCE}@v{version}"
    command = [
        "uvx",
        "--from",
        source,
        "python",
        "-I",
        "-c",
        "import importlib.util; print(importlib.util.find_spec('rapid_ship').submodule_search_locations[0])",
    ]
    with (
        tempfile.TemporaryDirectory() as neutral
    ):  # keep the project's uv settings out of the fetch
        try:
            result = subprocess.run(
                command, cwd=neutral, capture_output=True, text=True, check=False, timeout=600
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise KitError(f"cannot fetch rapid-ship {version} from {source}: {error}") from error
    if result.returncode != 0:
        raise KitError(f"cannot fetch rapid-ship {version} from {source}: {result.stderr.strip()}")
    root = Path(result.stdout.strip()) / "templates"
    if not (root / "kit.toml").is_file():
        raise KitError(f"rapid-ship {version} has no Kit templates")
    return root
```

The version check keeps the lock's text from adding uvx options or changing the URL. On 2026-10-14, `uvx --from <local checkout> python -I -c` with the script above printed the package directory in uv's cache and left `rapid_ship` unimported. The git source was not run: the repository had no tags that day. A missing tag makes `uvx` exit non-zero, so each needed merge becomes a conflict whose reason names the source.

`_delete(root, path)` unlinks `locate(root, path)`, then removes each parent directory that is now empty, stopping at the repository root or at the first non-empty one. `_start_branch(root, branch)` reads `git symbolic-ref --quiet --short HEAD` (allowed exit codes 0 and 1); an empty result raises `KitRefusal("HEAD is detached; check out the branch the pull request should target")`. A non-empty `git branch --list <branch>` raises `KitRefusal(f"branch {branch} exists; a previous sync may have opened a pull request (gh pr list --head {branch})")`. Otherwise it runs `git switch --quiet --create <branch>` and returns the base branch name. Every refusal comes before the first write.

`push_and_open_pull_request(root, branch, base, title, body)` records each external operation before sending it. It prints `Pushing <branch> to origin.`, runs `git push --no-verify --set-upstream origin <branch>`, prints `Opening a pull request with gh.`, and runs `gh pr create --base <base> --head <branch> --title <title> --body-file -` with the body on stdin. It returns the last line of stdout. A push failure raises `KitError` saying the commit is on the local branch. A `gh` failure, or a missing `gh`, raises `KitError` saying the branch is pushed and to check `gh pr list --head <branch>` before retrying.

`pull_request_body(result, old_version)` writes:
- a first line saying the PR updates the vendored Kit from `<old>` to `<new>` and was generated by `rapid-ship sync`;
- `## Changes`, one bulleted list per non-empty bucket;
- `## Needs the owner`, with each conflict's reason and its diff in a `diff` fence (cut to 200 lines), then the `seeded_changed`, `seeded_existing`, `released` and `missing` lists, each with one line on what to do;
- `## Evidence`, last, with the item `` - `rapid-ship sync`: rapid-ship <old> to <new>; <counts> `` and the line `Not covered: sync did not run ./devctl check; CI runs it on this pull request.` `<counts>` is `<n> <bucket>` for each non-empty list among `updated`, `merged`, `adopted`, `added`, `deleted`, `released`, `seeded_changed`, `seeded_existing`, `missing` and `conflicts`, with underscores written as spaces and joined by `, `, for example `1 updated, 2 conflicts`.

Plan 3's evidence step requires that section on every PR, and its `_COMMAND` pattern, ``^\s*[-*]\s+`[^`]+`:\s*\S``, needs the colon right after the closing backtick. The Evidence section is never cut: when the body would pass 60,000 characters, the `## Needs the owner` diffs are cut to fit and end with a line saying so. GitHub's exact body limit was not checked.

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_kit_sync.py -q` and `uv run mypy`. Expected: all pass; `Success`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/kit/sync.py tests/test_kit_sync.py
git commit -m "feat: update the vendored Kit with rapid-ship sync

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Kit settings, guides and Python seeds

**Files:**
- Create: `rapid_ship/templates/kit.toml`, `rapid_ship/templates/AGENTS.md` (directory guide), `rapid_ship/templates/common/AGENTS.md`, `rapid_ship/templates/common/CLAUDE.md`, `rapid_ship/templates/common/.github/CODEOWNERS`, `rapid_ship/templates/python/.github/CODEOWNERS`, `rapid_ship/templates/common/.rapid-ship/gate.toml`, `rapid_ship/templates/common/.rapid-ship/exceptions.toml`, `rapid_ship/templates/common/docs/features/README.md`, `rapid_ship/templates/common/docs/patterns/README.md`, `rapid_ship/templates/python/.rapid-ship/project.toml`, `rapid_ship/templates/neutral/.rapid-ship/project.toml`, `rapid_ship/templates/python/pyproject.toml`, `rapid_ship/templates/python/src/__package__/__init__.py`, `rapid_ship/templates/python/tests/test_import.py`
- Modify: `pyproject.toml` (ruff and mypy exclude the templates)
- Test: `tests/test_kit_contents.py`

**Interfaces:**
- Consumes: `render_files`, `load_manifest`, `packaged_templates`, `STACKS` (Task 2).
- Produces: the packaged Kit's seeds. Front-matter formats for plan 3's map rules 4 and 5 (the two READMEs below).

- [ ] **Step 1: Write the failing tests.** Create `tests/test_kit_contents.py`:

```python
"""The packaged Kit's templates match spec 1, section 4 (offline)."""

import re
import tomllib

import pytest

from rapid_ship.kit.templates import STACKS, load_manifest, packaged_templates, render_files

VARIABLES = {
    "project_name": "demo-app",
    "package": "demo_app",
    "owner": "octo",
    "repository": "octo/demo-app",
}
SEEDED = {
    ".github/CODEOWNERS",
    ".rapid-ship/exceptions.toml",
    ".rapid-ship/gate.toml",
    ".rapid-ship/project.toml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/features/README.md",
    "docs/patterns/README.md",
}


def rendered(stack="python", **variables):
    return {t.path: t for t in render_files(stack, {**VARIABLES, **variables}, ())}


def text(stack, path, **variables):
    return rendered(stack, **variables)[path].content.decode()


def test_every_manifest_path_exists_in_a_layer():
    manifest = load_manifest()
    root = packaged_templates()
    for path in manifest.seeded | manifest.new_project | manifest.executable:
        assert any((root / layer / path).is_file() for layer in ("common", *STACKS)), path


@pytest.mark.parametrize("stack", STACKS)
def test_the_spec_seeded_files_are_seeded(stack):
    kinds = {path: t.kind for path, t in rendered(stack).items()}
    assert {path for path in SEEDED if kinds.get(path) == "seeded"} == SEEDED


def test_python_new_project_seeds():
    kinds = {path: t.kind for path, t in rendered().items()}
    assert {
        kinds[p] for p in ("pyproject.toml", "src/demo_app/__init__.py", "tests/test_import.py")
    } == {"seeded"}


@pytest.mark.parametrize(("stack", "roots"), [("python", ["src/demo_app"]), ("neutral", [])])
def test_project_settings_seed_has_the_spec_defaults(stack, roots):
    settings = tomllib.loads(text(stack, ".rapid-ship/project.toml"))
    assert settings == {
        "stack": stack,
        "github": {"repository": "octo/demo-app", "worker_app_id": 0, "reviewer_app_id": 0},
        "kit": {"optional": [], "exclude": []},
        "linear": {"team_id": "", "project_id": ""},
        "dispatch": {
            "max_workers": 5,
            "attempt_limit": 3,
            "worktree_root": "../demo-app.worktrees",
        },
        "map": {"source_roots": roots, "unguided": []},
        "tests": {"unit": ["tests/unit/**"]},
        "release": {"method": "none"},
    }
    assert "github" in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))
    assert (
        "repository"
        not in tomllib.loads(text(stack, ".rapid-ship/project.toml", repository=""))["github"]
    )


def test_gate_seed_has_the_spec_defaults():
    gate = tomllib.loads(text("neutral", ".rapid-ship/gate.toml"))
    assert gate["mode"] == "walk" and gate["flight_lease_until"] == ""
    assert gate["owner_approves_behavioural_test_removal"] is True
    limits = {"max_revisions_per_pr": 1.0, "max_rollbacks": 1, "max_open_alarms": 0}
    assert gate["thresholds"] == {
        "promotion": {"window": 30, **limits},
        "demotion": {"window": 20, **limits},
    }


def test_exceptions_seed_lists_none():
    assert tomllib.loads(text("neutral", ".rapid-ship/exceptions.toml")) == {}


def active(lines):
    return [line for line in lines if line.strip() and not line.startswith("#")]


# Plan 4's doctor requires these in Flight: PROTECTED_PATHS, plus PYTHON_PROTECTED_PATHS for Python.
PROTECTED = (
    "/.github/",
    "/.githooks/",
    "/devctl",
    "/tools/devctl/",
    "/.agents/skills/",
    "/.claude/skills/",
    "/.rapid-ship/",
)


@pytest.mark.parametrize(("stack", "extra"), [("python", ("/pyproject.toml",)), ("neutral", ())])
def test_codeowners_has_the_walk_line_and_the_stack_protected_set(stack, extra):
    lines = text(stack, ".github/CODEOWNERS").splitlines()
    assert active(lines) == ["* @octo"]
    protected = [line for line in lines if re.fullmatch(r"# /\S+ @octo", line)]
    assert protected == [f"# {path} @octo" for path in (*PROTECTED, *extra)]


def test_the_python_codeowners_only_adds_pyproject():
    python = text("python", ".github/CODEOWNERS").splitlines()
    neutral = text("neutral", ".github/CODEOWNERS").splitlines()
    assert [line for line in python if line != "# /pyproject.toml @octo"] == neutral


def test_codeowners_without_an_owner_leaves_the_owner_to_rs_setup():
    lines = text("neutral", ".github/CODEOWNERS", owner="").splitlines()
    assert active(lines) == []
    assert "# * @<owner>" in lines and "# /devctl @<owner>" in lines


def test_python_seed_has_the_spec_guardrails():
    data = tomllib.loads(text("python", "pyproject.toml"))
    lint = data["tool"]["ruff"]["lint"]
    assert set(lint["select"]) == {
        "E",
        "W",
        "F",
        "I",
        "B",
        "UP",
        "SIM",
        "C4",
        "RUF",
        "PGH",
        "ERA",
        "T20",
        "S",
        "TID",
        "PT",
        "PTH",
        "DTZ",
        "C90",
        "TD",
        "BLE",
        "ANN401",
    }
    assert lint["mccabe"]["max-complexity"] == 10
    assert lint["flake8-tidy-imports"] == {"ban-relative-imports": "all", "banned-api": {}}
    assert data["tool"]["ruff"]["extend-exclude"] == ["tools/devctl"]
    mypy = data["tool"]["mypy"]
    assert mypy["strict"] is True and mypy["warn_unreachable"] is True
    assert set(mypy["enable_error_code"]) == {
        "ignore-without-code",
        "redundant-expr",
        "truthy-bool",
    }
    assert mypy["files"] == ["src", "tests"]
    pytest_options = data["tool"]["pytest"]["ini_options"]
    assert pytest_options["addopts"] == ["--strict-markers", "--strict-config"]
    assert pytest_options["xfail_strict"] is True and pytest_options["filterwarnings"] == ["error"]
    assert [c["type"] for c in data["tool"]["importlinter"]["contracts"]] == ["layers", "forbidden"]
    names = {re.split(r"[<>=]", requirement)[0] for requirement in data["dependency-groups"]["dev"]}
    assert names == {"import-linter", "mypy", "pytest", "ruff"}
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/demo_app"]


def test_python_seeds_are_valid_python():
    for path in ("src/demo_app/__init__.py", "tests/test_import.py"):
        compile(text("python", path), path, "exec")
    assert 'importlib.import_module("demo_app")' in text("python", "tests/test_import.py")


def test_root_guide_skeleton_follows_the_spec():
    guide = text("neutral", "AGENTS.md")
    headings = re.findall(r"^#+ .*$", guide, flags=re.MULTILINE)
    assert headings == [
        "# demo-app",
        "## Commands",
        "## Find the change",
        "## Rules",
        "## Shared language and decisions",
    ]
    rules = guide.split("## Rules")[1].split("##")[0]
    bullets = [line for line in rules.splitlines() if line.startswith("- ")]
    assert bullets and all(re.search(r"(enforced by: \S+|advisory)$", line) for line in bullets)
    assert re.findall(r"\]\(([^)]+)\)", guide) == [
        "docs/features/README.md",
        "docs/patterns/README.md",
    ]
    for pointer in (
        "`GLOSSARY.md`",
        "`docs/adr/`",
        "`rs-writing`",
        "`rs-ponytail`",
        "`./devctl check`",
        "`./devctl doctor`",
    ):
        assert pointer in guide


def test_claude_md_imports_the_guide():
    assert text("neutral", "CLAUDE.md") == "@AGENTS.md\n"


def test_feature_and_pattern_formats_name_every_key():
    features = text("neutral", "docs/features/README.md")
    for key in ("purpose", "entry_points", "data", "observe", "reproduce"):
        assert f"`{key}`" in features
    # Plan 3's map check requires at least one entry point.
    assert "| Paths where the feature is entered | A non-empty list; each path exists |" in features
    patterns = text("neutral", "docs/patterns/README.md")
    for key in (
        "`reference`",
        "`enforced_by`",
        "`check:",
        "`test:",
        "`ruff:",
        "`banned:",
        "`contract:",
        "`type:",
    ):
        assert key in patterns
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_contents.py -q`. Expected: `KitError: cannot read the Kit manifest .../rapid_ship/templates/kit.toml`.

- [ ] **Step 3: Write the templates.** `rapid_ship/templates/kit.toml`:

```toml
# rapid-ship Kit manifest. Paths are relative to common/ or a stack directory, before substitution.
# Every template not listed under seeded or new_project is managed.
seeded = [
    ".github/CODEOWNERS",
    ".rapid-ship/exceptions.toml",
    ".rapid-ship/gate.toml",
    ".rapid-ship/project.toml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/features/README.md",
    "docs/patterns/README.md",
]
new_project = ["pyproject.toml", "src/__package__/__init__.py", "tests/test_import.py"]
executable = []
optional_skills = []
variables = ["owner", "package", "project_name", "repository"]
```

`rapid_ship/templates/common/.github/CODEOWNERS`, which the neutral stack uses:

```text
# Code owners. GitHub reads this file from the pull request's base branch,
# so a pull request cannot exempt itself.
#
# Walk: the owner reviews every path. When init ran without --owner, every
# owner below reads <owner>; rs-setup writes the login and uncomments this line.
* @{{owner}}
#
# Flight: replace the Walk line with the Protected set below, uncommented.
# Add a line for each existing Pattern file in docs/patterns/, and for the
# paths the project adds for access, the data model or the public API.
# /.github/ @{{owner}}
# /.githooks/ @{{owner}}
# /devctl @{{owner}}
# /tools/devctl/ @{{owner}}
# /.agents/skills/ @{{owner}}
# /.claude/skills/ @{{owner}}
# /.rapid-ship/ @{{owner}}
```

`rapid_ship/templates/python/.github/CODEOWNERS` is the same file with one more last line, `# /pyproject.toml @{{owner}}`: the Python guardrail settings live there. The stack layer overrides `common/` (Task 2), and `test_the_python_codeowners_only_adds_pyproject` keeps the two in step. The lines match plan 4's `PROTECTED_PATHS` and `PYTHON_PROTECTED_PATHS`, which doctor requires in Flight. Comments never contain `@`, so plan 3's diff step, which reads `<pattern> @<owner>` lines, sees only the Protected set.

`/devctl` is the root shim, which spec section 4 lists in the Protected set. CI runs `./devctl check --tier full` from the PR's own checkout, so a PR that rewrote the shim to `exit 0` would pass the required check; in Flight only this line makes such a change wait for the owner.

GitHub looks for CODEOWNERS in `.github/`, the root and `docs/`, in that order (GitHub docs, "About code owners"). The templates under `rapid_ship/templates/common/.github/` and `rapid_ship/templates/python/.github/` are therefore not read for this repository.

`rapid_ship/templates/python/.rapid-ship/project.toml` (the neutral copy differs in exactly two lines: `stack = "neutral"` and `source_roots = []`):

```toml
# rapid-ship project settings. No secrets. Changes need the owner (Protected set).
stack = "python"

# rs-setup records the Worker and Reviewer Agents: a Harness (claude, codex or agy)
# and an exact model ID each, used as named.
# [agents.worker]
# harness = "agy"
# model = "gemini-3.8-flash-high"
#
# [agents.reviewer]
# harness = "claude"
# model = "<exact model ID>"

[github]
repository = "{{repository}}"
worker_app_id = 0    # rapid-ship app records the App IDs
reviewer_app_id = 0

[kit]
optional = []        # opt-in Kit skills, such as "rs-contribute"
# Kit files or directories the project owns instead. rapid-ship sync never
# creates, replaces, merges or deletes them. A skill directory covers its
# .claude/skills link.
exclude = []

[linear]
team_id = ""
project_id = ""

[dispatch]
max_workers = 5
attempt_limit = 3
worktree_root = "../{{project_name}}.worktrees"

[map]
source_roots = ["src/{{package}}"]
unguided = []

[tests]
unit = ["tests/unit/**"]   # every other test counts as behavioural

[release]
method = "none"   # github-deployments, tags or none
```

`rapid_ship/templates/common/.rapid-ship/gate.toml`:

```toml
# Mode, Flight lease and thresholds. Changes need the owner (Protected set).
# Spec 3 defines how the thresholds are read.
mode = "walk"
flight_lease_until = ""  # empty: no Flight lease

# In Flight, a declared unit-test removal needs nothing more, while a declared
# behavioural-test removal, such as an integration test, waits for the owner.
owner_approves_behavioural_test_removal = true

[thresholds.promotion]   # Walk to Flight
window = 30              # the last merged agent PRs
max_revisions_per_pr = 1.0
max_rollbacks = 1
max_open_alarms = 0

[thresholds.demotion]    # Flight back to Walk
window = 20
max_revisions_per_pr = 1.0
max_rollbacks = 1
max_open_alarms = 0
```

`rapid_ship/templates/common/.rapid-ship/exceptions.toml` holds only comments: a two-line explanation ("Each suppression carries `rs-exception: EX-<n>` on its line. Each entry names the path, the rule, a reason and when to remove it. Changes need the owner.") and the spec's `EX-1` example commented out line by line.

`rapid_ship/templates/common/AGENTS.md`:

```markdown
# {{project_name}}

{{project_name}} is this repository's product. Replace this paragraph with one that says what it does and who uses it.

## Commands

- `./devctl check` runs every check CI requires. Add `--tier fast` for the quick subset.
- `./devctl doctor` reports missing tools, settings and GitHub configuration.
- `./devctl --help` lists the project's own verbs.

## Find the change

| Work | Start here |
| --- | --- |
| What a feature does, where it starts and how to reproduce it | [Feature map](docs/features/README.md) |
| The one supported way to do a recurring task | [Patterns](docs/patterns/README.md) |

Add a row for each directory guide.

## Rules

- Mark every suppression with `rs-exception: EX-<n>` and list it in `.rapid-ship/exceptions.toml`. enforced by: check:exceptions
- Declare each removed test under `Removed tests:` in the PR body, with a reason. enforced by: check:diff
- Keep each change inside its task's paths. advisory

## Shared language and decisions

- Terms are in `GLOSSARY.md`, and decisions in `docs/adr/`.
- Follow the `rs-writing` skill for prose and the `rs-ponytail` skill for building only what is needed.
```

The skeleton names `./devctl check` and `./devctl doctor`, which plans 3 and 4 add; no project uses the Kit before then. Its only links point to files the Kit seeds, so this repository's navigation check, which reads every AGENTS.md, resolves them inside `rapid_ship/templates/common/`.

`rapid_ship/templates/common/CLAUDE.md` is the single line `@AGENTS.md`.

`rapid_ship/templates/common/docs/features/README.md`:

````markdown
# Feature map

Each feature has one file here, named after the feature, such as `sign-up.md`. Agents keep these files current with the code, and `./devctl check` validates them.

Every feature file starts with YAML front matter:

```yaml
---
purpose: Lets a visitor create an account with an email address.
entry_points:
  - src/app/web/sign_up.py
data:
  - src/app/accounts/store.py
observe: The log line "account created" with the new account ID.
reproduce: ./devctl seed-account demo@example.com
---
```

| Key | Value | `./devctl check` requires |
| --- | --- | --- |
| `purpose` | One sentence on what the feature does for its user | Present and not empty |
| `entry_points` | Paths where the feature is entered | A non-empty list; each path exists |
| `data` | Paths of the data it reads or writes, or `[]` | A list, possibly empty; each path exists |
| `observe` | How to see the feature working | Present and not empty |
| `reproduce` | A `./devctl` command that exercises the feature | The word after `./devctl` is a registered devctl verb |

The text after the front matter describes the feature for a reader who has not seen it.
````

`rapid_ship/templates/common/docs/patterns/README.md`:

````markdown
# Patterns

A Pattern is the one supported way to do a recurring task. Each Pattern has one file here, such as `settings.md`. Agents may add a Pattern; changing an existing one needs the owner. `./devctl check` validates every file.

Every Pattern file starts with YAML front matter:

```yaml
---
reference: src/app/settings.py
enforced_by:
  - banned:os.environ
  - test:tests/test_settings.py::test_settings_are_the_only_reader
---
```

- `reference` is the path of the reference implementation. It must exist.
- `enforced_by` lists at least one reference to the check that enforces the Pattern. Each must resolve:

| Reference | Resolves when |
| --- | --- |
| `check:<step>` | The devctl check step exists |
| `test:<path>::<name>` | The test exists |
| `ruff:<code>` | The rule is selected in the Ruff settings (Python) |
| `banned:<module.member>` | The member is in Ruff's `banned-api` table (Python) |
| `contract:<name>` | An import-linter contract has that name (Python) |
| `type:<path>` | The file exists and mypy checks it (Python) |

The text after the front matter states the rule, when it applies and the bypass it bans.
````

`rapid_ship/templates/python/pyproject.toml` (checked on 2026-10-14: with `{{project_name}}` set to `demo-app` and `{{package}}` to `demo_app`, plus the two seeds below, `uv sync`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest` and `lint-imports` all passed, and ruff skipped a deliberate violation under `tools/devctl`):

```toml
# Guardrail settings from rapid-ship. Changes need the owner (Protected set).
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "{{project_name}}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
    "import-linter>=2.15,<3",
    "mypy>=1.20,<3",
    "pytest>=9,<10",
    "ruff>=0.17,<1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/{{package}}"]

[tool.ruff]
target-version = "py312"
# rapid-ship checks its own Kit code upstream.
extend-exclude = ["tools/devctl"]

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "B", "UP", "SIM", "C4", "RUF", "PGH", "ERA", "T20", "S",
    "TID", "PT", "PTH", "DTZ", "C90", "TD", "BLE", "ANN401",
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # pytest asserts

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

# Patterns add entries here, one per banned member.
[tool.ruff.lint.flake8-tidy-imports.banned-api]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool"]
files = ["src", "tests"]
mypy_path = "src"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config"]
xfail_strict = true
filterwarnings = ["error"]

[tool.importlinter]
root_packages = ["{{package}}"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Layers"
type = "layers"
containers = ["{{package}}"]
# Optional layers, in parentheses, until Plan names the real ones.
layers = ["(entrypoints)", "(services)", "(domain)"]

[[tool.importlinter.contracts]]
name = "Production code never imports the test framework"
type = "forbidden"
source_modules = ["{{package}}"]
forbidden_modules = ["pytest"]
```

import-linter's documentation says a missing layer breaks a `layers` contract unless it is in parentheses; with the optional layers above, both contracts were kept on the empty package, and adding `import pytest` to it broke the second, as observed with import-linter 2.15. ASYNC and FAST are not in the seed: the spec adds them only when those frameworks are detected, which rs-setup and `devctl doctor` do.

`rapid_ship/templates/python/src/__package__/__init__.py` is `"""{{project_name}}."""` and a newline. `rapid_ship/templates/python/tests/test_import.py`:

```python
"""Checks that the package imports. Replace it with real tests."""

import importlib


def test_package_imports() -> None:
    importlib.import_module("{{package}}")
```

The package name stays inside a string, so the template remains valid Python for tools that read it.

`rapid_ship/templates/AGENTS.md` (the directory guide, outside every layer, so never rendered):

```markdown
# Kit templates

`rapid-ship init` and `sync` render these files into projects. [kit.toml](kit.toml) lists the seeded paths, the new-project seeds, the executable files, the optional skills and the template variables; every other file is managed.

- `common/` holds files for every stack, laid out as in a project; `python/` and `neutral/` add or override files per stack. The [project root guide skeleton](common/AGENTS.md) is one of them.
- Managed files are copied byte for byte. Seeded files substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`, and a `__package__` directory becomes the package. An empty owner or repository renders as `<owner>` or `<repository>` and comments out its line; only TOML and CODEOWNERS templates may use them.
- This repository vendors the Kit. After changing a template, run `uv run rapid-ship sync --in-place` and commit the template with its vendored copy. `uv run rapid-ship status --strict`, run by `scripts/check.py`, fails until they match.
- ruff and mypy check the vendored copy in `tools/devctl/` and skip this directory, so devctl is checked once. Tests import the vendored copy.
- Keep template paths clear of the root `.gitignore` patterns: hatch drops ignored paths from the wheel without a warning. `scripts/smoke_distribution.py` fails when the wheel lacks a template.
- Rendering skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files, and here every path git does not keep. A template that is not yet added still renders unless git ignores it.
```

Add `extend-exclude = ["rapid_ship/templates"]` to `[tool.ruff]` and `exclude = ["^rapid_ship/templates/"]` to `[tool.mypy]` in this repository's `pyproject.toml`. Template Python is checked through the vendored copy (Task 9) and through `test_python_seeds_are_valid_python`.

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_kit_contents.py -q`, `uv run ruff check .`, `uv run mypy` and `uv run python scripts/check_repository.py`. Expected: all pass; the navigation check resolves the skeleton's two links inside `rapid_ship/templates/common/`.

- [ ] **Step 5: Commit.**

```bash
git add pyproject.toml rapid_ship/templates tests/test_kit_contents.py
git commit -m "feat: add the Kit's settings, guides and Python seeds

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: CLI commands

**Files:**
- Modify: `rapid_ship/cli.py`
- Test: `tests/test_kit_cli.py`; plan 1's `tests/test_cli.py` runs unchanged

**Interfaces:**
- Consumes: `main(argv: Sequence[str] | None = None) -> int` (plan 1); Tasks 1–6.
- Produces: `rapid-ship init [--stack {python,neutral}] [--owner LOGIN] [--repository OWNER/NAME] [--name NAME] [--package NAME]`, `rapid-ship status [--strict] [--json]`, `rapid-ship sync [--in-place]`; `build_parser() -> argparse.ArgumentParser`; `main(argv: Sequence[str] | None = None) -> int`, unchanged. `KitRefusal` maps to exit 1 and `KitError` to exit 2, with `rapid-ship: <message>` on stderr.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_kit_cli.py`:

```python
"""The rapid-ship command line in scratch repositories (offline)."""

import json

import pytest

from rapid_ship.cli import main


def test_init_status_and_sync_with_the_packaged_kit(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "neutral", "--owner", "octo"]) == 0
    out = capsys.readouterr().out
    assert "Next: commit these files on a branch, then run the rs-setup skill" in out
    assert "* @octo" in (git_repo / ".github/CODEOWNERS").read_text().splitlines()
    assert main(["status", "--strict"]) == 0
    capsys.readouterr()
    assert main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["strict_ok"] is True
    assert main(["sync", "--in-place"]) == 0
    assert "Kit is current; nothing to sync." in capsys.readouterr().out


def test_init_without_an_owner_leaves_the_walk_line_for_rs_setup(git_repo, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "neutral"]) == 0

    assert "# * @<owner>" in (git_repo / ".github/CODEOWNERS").read_text().splitlines()
    assert "CODEOWNERS has no owner line yet; rs-setup writes it." in capsys.readouterr().out


@pytest.fixture
def fixture_kit(make_templates, monkeypatch):
    root = make_templates()
    monkeypatch.setattr("rapid_ship.kit.templates.packaged_templates", lambda: root)
    return root


def test_a_managed_conflict_exits_1_and_writes_nothing(
    git_repo, fixture_kit, commit_all, monkeypatch, capsys
):
    (git_repo / "devctl").write_text("ours\n")
    commit_all(git_repo)
    monkeypatch.chdir(git_repo)

    assert main(["init", "--stack", "python"]) == 1

    assert "devctl: exists" in capsys.readouterr().err
    assert not (git_repo / ".rapid-ship").exists()


def test_strict_status_fails_on_a_modified_managed_file(git_repo, fixture_kit, monkeypatch, capsys):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--stack", "python"]) == 0
    (git_repo / "devctl").write_text("changed\n")
    capsys.readouterr()

    assert main(["status"]) == 0
    assert main(["status", "--strict"]) == 1
    assert "modified          devctl" in capsys.readouterr().out


def test_strict_status_passes_with_an_excluded_modified_file(
    git_repo, fixture_kit, write_kit_settings, monkeypatch, capsys
):
    monkeypatch.chdir(git_repo)
    assert main(["init", "--stack", "python"]) == 0
    write_kit_settings(git_repo, exclude=["devctl"])
    (git_repo / "devctl").write_text("ours\n")
    capsys.readouterr()

    assert main(["status", "--strict"]) == 0
    assert "excluded          devctl" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("arrange", "argv", "code", "message"),
    [
        (
            lambda root: (root / "notes.txt").write_text("x\n"),
            ["init", "--stack", "neutral"],
            1,
            "the work tree has changes",
        ),
        (lambda root: None, ["status"], 2, "kit.lock is missing; run rapid-ship init"),
        (lambda root: None, ["init"], 2, "pass --stack python or --stack neutral"),
        (lambda root: None, ["init", "--stack", "neutral", "--owner", "-x"], 2, "owner"),
    ],
)
def test_refusals_exit_1_and_errors_exit_2(
    git_repo, monkeypatch, capsys, arrange, argv, code, message
):
    arrange(git_repo)
    monkeypatch.chdir(git_repo)

    assert main(argv) == code
    assert message in capsys.readouterr().err


def test_outside_a_work_tree_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["status"]) == 1
    assert "not inside a git work tree" in capsys.readouterr().err


def test_a_command_is_required():
    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == 2
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_cli.py -q`. Expected: failures with `argparse` usage errors (`invalid choice: 'init'` or unrecognised arguments), since plan 1's CLI has no subcommands.

- [ ] **Step 3: Implement** `rapid_ship/cli.py`:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rapid-ship", description="Vendor rapid-ship's Kit and keep it current."
    )
    parser.add_argument("--version", action="version", version=f"rapid-ship {installed_version()}")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    init = commands.add_parser("init", help="vendor the Kit into this repository")
    init.add_argument("--stack", choices=STACKS, help="required when there is no pyproject.toml")
    init.add_argument(
        "--owner", help="your GitHub login, for CODEOWNERS; rs-setup fills it when absent"
    )
    init.add_argument("--repository", help="owner/name on GitHub")
    init.add_argument("--name", help="project name; default: the directory name")
    init.add_argument(
        "--package", help="Python package name; default: derived from the project name"
    )
    status = commands.add_parser(
        "status", help="compare the vendored Kit with its lock and this release"
    )
    status.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 unless every managed file is unchanged and current",
    )
    status.add_argument("--json", action="store_true", help="print the report as JSON")
    sync = commands.add_parser("sync", help="update the vendored Kit and open a pull request")
    sync.add_argument(
        "--in-place",
        action="store_true",
        help="write the work tree; no branch, commit or pull request",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = work_tree_root(Path.cwd())
        if args.command == "init":
            return _init(root, args)
        if args.command == "status":
            return _status(root, strict=args.strict, as_json=args.json)
        return _sync(root, in_place=args.in_place)
    except KitRefusal as error:
        print(f"rapid-ship: {error}", file=sys.stderr)
        return 1
    except KitError as error:
        print(f"rapid-ship: {error}", file=sys.stderr)
        return 2
```

`_init` calls `resolve_variables(root, name=..., package=..., owner=..., repository=...)` and then `init_repository(root, stack=args.stack, variables=variables)`. On conflicts it prints `rapid-ship init wrote nothing. These Kit files conflict with the repository:` and one indented line per conflict to stderr, and returns 1. Otherwise it prints:

- `Vendored the <stack> Kit <version> for <project_name> (package <package>).`;
- `Created:` with one indented path per line;
- when present, `Skipped existing seeded files; rs-setup merges them:` and the paths;
- `CODEOWNERS has no owner line yet; rs-setup writes it.` when the owner is empty;
- `Next: commit these files on a branch, then run the rs-setup skill in your coding agent.`

It returns 0.

`_status` calls `classify(root)`. With `--json` it prints `json.dumps({"kit_version", "installed_version", "stack", "files": [asdict(...)], "outdated", "not_installed", "strict_ok"}, indent=2)`. Otherwise it prints `Kit <kit_version> (installed rapid-ship <installed>), stack <stack>`, then one `f"{state:<17} {path}"` line for each file that is not unchanged, each outdated path (`outdated`) and each not-installed path (`not installed`), then `<n> managed files unchanged.` It returns 1 only for `--strict` without `strict_ok`.

`_sync` calls `sync_repository(root, in_place=in_place)`. When nothing changed and there is no conflict, it prints `Kit is current; nothing to sync.` and any missing paths, and returns 0. Otherwise it prints each non-empty bucket with a heading, then each conflict as `Conflict: <path>: <reason>` followed by its diff. It ends with `Opened <url> on <branch>.` or, for `--in-place`, `Wrote the changes to the work tree.` It returns 1 when conflicts remain, else 0.

Keep plan 1's signature and import `Sequence` from `collections.abc`. Plan 1's `tests/test_cli.py` needs no change: with a required subcommand, a bare call and `--unknown` still exit 2 with `usage: rapid-ship` on stderr and nothing on stdout, and `--version` still prints `rapid-ship <version>`.

- [ ] **Step 4: Run the tests and see them pass.** Run `uv run pytest tests/test_kit_cli.py -q`, the whole suite with `uv run pytest -q`, then `uv run mypy`. Expected: all pass; `Success`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/cli.py tests/test_kit_cli.py
git commit -m "feat: add the init, status and sync commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: Vendor the Kit into this repository

**Files:**
- Create (by `rapid-ship init`): `.github/CODEOWNERS`, `.rapid-ship/project.toml`, `.rapid-ship/gate.toml`, `.rapid-ship/exceptions.toml`, `.rapid-ship/kit.lock`, `docs/features/README.md`, `docs/patterns/README.md`
- Modify: `.rapid-ship/project.toml` (after init), `scripts/check.py`
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: the `rapid-ship` CLI (Task 7); plan 1's `scripts/check.py` and `tests/test_check.py`, in which stand-in modules named after each stage log their arguments.
- Produces: this repository's lock; a `check.py` stage `python -m rapid_ship status --strict`, the same command as `uv run rapid-ship status --strict`, run in the style of the other stages.

- [ ] **Step 1: See the missing lock.** On a clean tree, run `uv run rapid-ship status --strict`. Expected: exit 2, `rapid-ship: .rapid-ship/kit.lock is missing; run rapid-ship init`.

- [ ] **Step 2: Owner step: confirm the GitHub login for CODEOWNERS.** On 2026-10-14, `gh api user --jq .login` returned `proxy-hatch`, and `gh api repos/proxy-hatch/rapid-ship` showed a user-owned repository. The same day, `gh api repos/proxy-hatch/rapid-ship/rulesets` returned `[]` and `main` had no branch protection. Once merged, `* @proxy-hatch` makes GitHub request the owner's review on other people's PRs, but blocks nothing until a ruleset requires code-owner review. The owner confirms the login before Step 3.

- [ ] **Step 3: Run init.**

```bash
uv run rapid-ship init --owner proxy-hatch --repository proxy-hatch/rapid-ship --name rapid-ship
```

Expected: exit 0. It reports stack `python` and package `rapid_ship`. Created: `.github/CODEOWNERS`, `.rapid-ship/exceptions.toml`, `.rapid-ship/gate.toml`, `.rapid-ship/project.toml`, `docs/features/README.md`, `docs/patterns/README.md`, `.rapid-ship/kit.lock`. Skipped: `AGENTS.md` and `CLAUDE.md`. No `src/` or `tests/test_import.py` is written, because `pyproject.toml` exists. `--name` is needed because this checkout's directory name is not the project name.

- [ ] **Step 4: Set this repository's source root.** In `.rapid-ship/project.toml`, set `[map] source_roots = ["rapid_ship"]`; the seed's `src/rapid_ship` does not exist here. Leave `[tests] unit` at its default, so every test here counts as behavioural, which is the safe choice until the owner classes them.

- [ ] **Step 5: Write the failing test.** In `tests/test_check.py`, add `rapid_ship` to the stand-in modules written into the scratch checkout (the loop that writes `ruff.py`, `mypy.py` and `pytest.py` writes `rapid_ship.py` too). `python -m rapid_ship` run from that checkout then imports the stand-in, which logs the stage name `rapid_ship`. Insert `"rapid_ship"` right after `"check_repository"` in the expected stage list, assert `observed[1]["args"] == ["status", "--strict"]`, shift the later index assertions by one, and add `"rapid_ship"` to the stop-after-failure parameters. Run `uv run pytest tests/test_check.py -q`. Expected: failure, because the observed stages lack `rapid_ship`.

- [ ] **Step 6: Add the stage.** In `scripts/check.py`, right after the navigation stage:

```python
        run(root, python, "-m", "rapid_ship", "status", "--strict")
```

Run `uv run pytest tests/test_check.py -q` and `uv run rapid-ship status --strict`. Expected: pass; exit 0. There are no managed files yet, so the report lists `0 managed files unchanged.`

- [ ] **Step 7: Build the docs site,** which now publishes the two seeded READMEs: `npm --prefix website ci --no-audit --no-fund` (once per checkout), then `npm --prefix website run build`. Expected: the build succeeds and lists no broken links.

- [ ] **Step 8: Commit.**

```bash
git add .github/CODEOWNERS .rapid-ship docs/features/README.md docs/patterns/README.md scripts/check.py tests/test_check.py
git commit -m "chore: vendor the rapid-ship Kit into this repository

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: devctl skeleton

**Files:**
- Create: `rapid_ship/templates/common/devctl`, `rapid_ship/templates/common/tools/devctl/pyproject.toml`, `rapid_ship/templates/common/tools/devctl/uv.lock` (generated), `rapid_ship/templates/common/tools/devctl/.gitignore`, `rapid_ship/templates/common/tools/devctl/devctl/__init__.py`, `rapid_ship/templates/common/tools/devctl/devctl/cli.py`, `rapid_ship/templates/common/tools/devctl/devctl_project/__init__.py`, `tests/devctl/conftest.py`
- Create (by `rapid-ship sync --in-place`): `devctl`, `tools/devctl/` with the same files
- Modify: `rapid_ship/templates/kit.toml`, `pyproject.toml`, `.rapid-ship/kit.lock`
- Test: `tests/test_kit_contents.py`, `tests/devctl/test_devctl_cli.py`, `tests/test_kit_dogfood.py`

**Interfaces:**
- Consumes: Tasks 5–8.
- Produces: the `devctl` shim running `exec uv run --project "$root/tools/devctl" --frozen --quiet devctl "$@"`; `devctl.__version__ = "0.1.0"`; `devctl.cli.build_parser() -> argparse.ArgumentParser`; `devctl.cli.main(argv: Sequence[str] | None = None) -> int`; the seed `devctl_project.register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None` and `devctl_project.check_steps() -> list[object]`. A verb sets `handler`, a callable taking `argparse.Namespace` and returning the exit code. As the index says, `check_steps` returns `list[object]` until plan 3 Task 2 defines `Step` and narrows the seed.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_kit_contents.py` (add `import subprocess`):

```python
def test_the_devctl_shim_is_managed_executable_and_valid_sh(tmp_path):
    shim = rendered("neutral")["devctl"]
    assert shim.kind == "managed" and "devctl" in load_manifest().executable
    assert (
        b'exec uv run --project "$root/tools/devctl" --frozen --quiet devctl "$@"' in shim.content
    )
    (tmp_path / "devctl").write_bytes(shim.content)
    subprocess.run(["sh", "-n", str(tmp_path / "devctl")], check=True)


def test_devctl_is_its_own_uv_workspace_and_its_versions_agree():
    files = rendered("neutral")
    project = tomllib.loads(files["tools/devctl/pyproject.toml"].content.decode())
    assert project["tool"]["uv"]["workspace"] == {"members": []}
    assert project["project"]["scripts"] == {"devctl": "devctl.cli:main"}
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "devctl",
        "devctl_project",
    ]
    version = project["project"]["version"]
    lock = tomllib.loads(files["tools/devctl/uv.lock"].content.decode())
    locked = {p["name"]: p.get("version") for p in lock["package"]}
    assert locked["devctl"] == version
    # Plans 3 and 4 add dependencies. uv.lock records each under its normalized name.
    declared = {
        re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~;\s]", requirement, maxsplit=1)[0]).lower()
        for requirement in project["project"]["dependencies"]
    }
    assert declared <= locked.keys()
    assert f'__version__ = "{version}"' in files["tools/devctl/devctl/__init__.py"].content.decode()


def test_devctl_project_is_seeded_and_the_environment_is_ignored():
    files = rendered("neutral")
    assert files["tools/devctl/devctl_project/__init__.py"].kind == "seeded"
    assert files["tools/devctl/.gitignore"].content == b"/.venv/\n__pycache__/\n"
```

Create `tests/devctl/conftest.py`:

```python
"""Import this repository's vendored devctl, which `rapid-ship status --strict` keeps equal to the templates."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "devctl"))
```

Plan 3 Task 2 deletes this file and sets pytest's `pythonpath = ["tools/devctl", "tests/devctl"]` instead, leaving `tests/conftest.py` the only conftest. Do not add `tests/devctl/__init__.py`: with pytest's default import mode it would make a test package named `devctl` and shadow the real one. Name test files `tests/devctl/test_devctl_*.py` so their basenames stay unique; later plans keep this convention. Create `tests/devctl/test_devctl_cli.py`:

```python
"""devctl's command line, from the vendored copy (offline)."""

from pathlib import Path

import pytest

import devctl
import devctl_project
from devctl import cli

ROOT = Path(__file__).resolve().parents[2]


def test_tests_import_the_vendored_copy():
    assert Path(devctl.__file__).resolve().parent == ROOT / "tools/devctl/devctl"


def test_version_prints_the_package_version(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == f"devctl {devctl.__version__}\n"


def test_a_project_verb_returns_its_handler_exit_code(monkeypatch):
    def register(commands):
        commands.add_parser("hello").set_defaults(handler=lambda args: 7)

    monkeypatch.setattr(devctl_project, "register", register)

    assert cli.main(["hello"]) == 7


def test_a_command_is_required():
    with pytest.raises(SystemExit) as raised:
        cli.main([])
    assert raised.value.code == 2


def test_the_seeded_project_hooks_add_nothing():
    assert devctl_project.check_steps() == []
```

Create `tests/test_kit_dogfood.py`. It pins the dog-food case of the owner groups (spec section 3, "Who owns what"): this repository edits both the `devctl_project` seed template and its own seeded copy, and its `sync --in-place` must never write that copy. It syncs a scratch copy, so the real work tree is never written.

```python
"""This repository's own Kit, synced in a scratch copy (offline)."""

import shutil
from pathlib import Path

from rapid_ship.kit.sync import sync_repository
from rapid_ship.kit.templates import KitError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = "rapid_ship/templates"
PROJECT = "tools/devctl/devctl_project"
SEED = f"{PROJECT}/__init__.py"
CLI = "tools/devctl/devctl/cli.py"


def copy_this_repository(destination, run_git):
    """Copy the files git keeps here, uncommitted work included: what rendering and the wheel see."""
    listed = run_git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for relative in filter(None, listed.split("\0")):
        source = ROOT / relative
        if not (source.is_symlink() or source.is_file()):
            continue  # deleted in the work tree, or an untracked nested repository
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def offline(version):
    raise KitError(f"rapid-ship {version} is not fetched in offline tests")


def append(path, text):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(text)


def test_this_repository_sync_leaves_devctl_project_unchanged(git_repo, run_git, commit_all):
    copy_this_repository(git_repo, run_git)
    append(
        git_repo / SEED, "\nOWNED_HERE = True\n"
    )  # this repository's own edit to its seeded copy
    (git_repo / PROJECT / "verbs.py").write_text('"""A project verb module."""\n')
    append(git_repo / TEMPLATES / "common" / SEED, "\n# A newer seed.\n")
    append(git_repo / TEMPLATES / "common" / CLI, "\n# A newer devctl.\n")
    commit_all(git_repo)
    ours = (git_repo / SEED).read_bytes()

    result = sync_repository(
        git_repo, in_place=True, templates_root=git_repo / TEMPLATES, old_templates=offline
    )

    # status --strict keeps every other managed file current, so only the changed template applies.
    assert (result.updated, result.conflicts) == ([CLI], [])
    assert SEED in result.seeded_changed
    assert (git_repo / SEED).read_bytes() == ours
    assert run_git(git_repo, "status", "--porcelain", "--", PROJECT) == ""
```

The copy lists the same paths as `_kept_by_git` (Task 2), so it holds what a source run renders.

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/test_kit_contents.py tests/test_kit_dogfood.py tests/devctl -q`. Expected: `KeyError: 'devctl'` in the content tests, `FileNotFoundError` for `tools/devctl/devctl_project/__init__.py` in the dog-food test, and `ModuleNotFoundError: No module named 'devctl'` when collecting `tests/devctl`.

- [ ] **Step 3: Write the templates.** `rapid_ship/templates/common/devctl`:

```sh
#!/bin/sh
# Runs this repository's devctl in its own locked environment, tools/devctl/.venv.
# rapid-ship manages this file: change the template upstream, then run rapid-ship sync.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
# A shared environment setting would make uv install devctl into the project's environment.
unset UV_PROJECT_ENVIRONMENT
exec uv run --project "$root/tools/devctl" --frozen --quiet devctl "$@"
```

`rapid_ship/templates/common/tools/devctl/pyproject.toml`:

```toml
# devctl, vendored by rapid-ship. rapid-ship sync updates this file.
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "devctl"
version = "0.1.0"
description = "This repository's developer CLI, vendored by rapid-ship"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
devctl = "devctl.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["devctl", "devctl_project"]

# devctl is its own uv workspace. Without this, a project whose pyproject.toml
# declares a workspace over tools/* absorbs devctl, and --frozen finds no lock.
# Such a project must also list tools/devctl under its workspace's exclude.
[tool.uv.workspace]
members = []
```

The workspace table was checked on 2026-10-14 with uv 0.11.0, under a root `pyproject.toml` declaring `[tool.uv.workspace] members = ["tools/*"]`:

- Without the table, `uv run --project tools/devctl --frozen` failed with ``Unable to find lockfile at `uv.lock` ``, and the root `uv lock` resolved devctl as a member of the project's lock.
- With the table, devctl ran and `uv lock --check --project tools/devctl` passed. The project's own root `uv lock`, `uv sync` and `uv run --locked` all failed with ``Nested workspaces are not supported, but workspace member has a `tool.uv.workspace` table: …/tools/devctl``.
- With the table and `exclude = ["tools/devctl"]` in the root workspace, all of those passed, and the root lock held only the project.

The table stays, so the mistake fails loudly at the project's `uv lock` instead of folding devctl into the project's lock. `init` never edits the project's `pyproject.toml`, so `rs-setup` adds the exclude and `devctl doctor` reports it missing (plans 5 and 4). Task 12's smoke runs the root `uv lock` in such a project.

`rapid_ship/templates/common/tools/devctl/.gitignore` is `/.venv/` and `__pycache__/`, one per line; `uv run` creates `tools/devctl/.venv`. `devctl/__init__.py`:

```python
"""devctl, this repository's developer CLI, vendored by rapid-ship.

rapid-ship manages this package. Change its template in rapid-ship and run
rapid-ship sync; a local edit shows as modified in rapid-ship status.
"""

__version__ = "0.1.0"
```

`devctl/cli.py`:

```python
"""devctl's command line: core commands, plus the project's verbs from devctl_project."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

import devctl_project
from devctl import __version__

Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devctl", description="This repository's developer CLI.")
    parser.add_argument("--version", action="version", version=f"devctl {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)
    devctl_project.register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.error(f"{args.command} does not set a handler")
    return handler(args)
```

`devctl_project/__init__.py` (seeded):

```python
"""Project verbs and extra check steps for this repository's devctl.

rapid-ship writes this package once; the project owns it afterwards.
"""

from __future__ import annotations

import argparse


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add project verbs. Each verb sets a handler that returns the exit code:

    verb = commands.add_parser("seed-demo", help="Load demo data")
    verb.set_defaults(handler=seed_demo)
    """


def check_steps() -> list[object]:
    """Return extra steps for ./devctl check."""
    return []
```

Add `"tools/devctl/devctl_project/__init__.py"` to `seeded` and set `executable = ["devctl"]` in `kit.toml`. Generate the lock: `uv lock --project rapid_ship/templates/common/tools/devctl`. Expected: `Resolved 1 package`, and `uv.lock` holds only `devctl` 0.1.0 with `source = { editable = "." }`.

- [ ] **Step 4: Vendor it.** Run `uv run rapid-ship sync --in-place`. Expected: exit 0. Added: `devctl`, `tools/devctl/.gitignore`, `tools/devctl/devctl/__init__.py`, `tools/devctl/devctl/cli.py`, `tools/devctl/devctl_project/__init__.py` (a new seed), `tools/devctl/pyproject.toml`, `tools/devctl/uv.lock`. Ends with `Wrote the changes to the work tree.`

- [ ] **Step 5: Check devctl once.** In `pyproject.toml`, set `[tool.ruff] src = [".", "tools/devctl"]`, so ruff sorts `devctl` and `devctl_project` as first-party, and `[tool.mypy] files = ["rapid_ship", "tools/devctl"]`, keeping `exclude = ["^rapid_ship/templates/"]` from Task 6. In a scratch layout on 2026-10-14, mypy without the exclude also checked the template copies and the `__package__` seed (8 source files); with it, 4 files, each module once. mypy and ruff both skipped a nested `tools/devctl/.venv`.

- [ ] **Step 6: Run the tests and checks.** Run:

```bash
uv run pytest tests/test_kit_contents.py tests/test_kit_dogfood.py tests/devctl -q
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run rapid-ship status --strict
./devctl --version
```

Expected: tests pass. ruff passes. mypy reports `Success: no issues found in N source files`, where N equals `git ls-files 'rapid_ship/*.py' 'tools/devctl/*.py' | grep -v '^rapid_ship/templates/' | wc -l`. status exits 0. `./devctl --version` prints `devctl 0.1.0`; the first run builds devctl with hatchling, from uv's cache or the network. If ruff format or ruff check wants a change in `tools/devctl`, make it in the template, then rerun `sync --in-place`.

- [ ] **Step 7: Commit.**

```bash
git add rapid_ship/templates pyproject.toml devctl tools/devctl .rapid-ship/kit.lock tests/test_kit_contents.py tests/test_kit_dogfood.py tests/devctl
git commit -m "feat: add devctl's skeleton to the Kit and vendor it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 10: devctl settings

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/settings.py`; vendored `tools/devctl/devctl/settings.py` (by sync)
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/cli.py`; vendored copy and `.rapid-ship/kit.lock` (by sync)
- Test: `tests/devctl/test_devctl_settings.py`, `tests/devctl/test_devctl_cli.py`

**Interfaces:**
- Consumes: Task 9.
- Produces: exactly the index's `Agent`, `ProjectSettings`, `GateSettings`, `ExceptionEntry`, `load_project`, `load_gate`, `load_exceptions` and `SettingsError`, plus the path constants `PROJECT`, `GATE`, `EXCEPTIONS`. The one exception is `ProjectSettings.map_exclude`, which plan 3 Task 4 adds with `[map] exclude`. `cli.main` maps `SettingsError` to exit 2.

Rules beyond the index: unknown keys are errors, so a typo cannot silently keep a default. A TOML boolean is never an integer. `0` App IDs and empty strings mean unset (`None`). A model ID is kept exactly; surrounding spaces are an error, not trimmed. `[thresholds]` in `gate.toml` may hold only `promotion` and `demotion`; Spec 3 reads their values. `excluded` is `[kit] exclude` normalised as `read_excluded` does (Task 2), because devctl cannot import `rapid_ship`.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_settings.py`:

```python
"""devctl settings loading, defaults and errors (offline)."""

import re
from pathlib import Path

import pytest

from devctl.settings import (
    EXCEPTIONS,
    GATE,
    PROJECT,
    Agent,
    GateSettings,
    ProjectSettings,
    SettingsError,
    load_exceptions,
    load_gate,
    load_project,
)
from rapid_ship.kit.templates import render_files

ROOT = Path(__file__).resolve().parents[2]
VARIABLES = {"project_name": "demo-app", "package": "demo_app", "owner": "", "repository": ""}
LOADERS = {PROJECT: load_project, GATE: load_gate, EXCEPTIONS: load_exceptions}


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_the_seeded_settings_load_with_the_spec_defaults(tmp_path):
    for template in render_files("python", VARIABLES, ()):
        if template.path.startswith(".rapid-ship/"):
            write(tmp_path, template.path, template.content.decode())

    assert load_project(tmp_path) == ProjectSettings(
        stack="python",
        worker=None,
        reviewer=None,
        repository=None,
        worker_app_id=None,
        reviewer_app_id=None,
        linear_team_id=None,
        linear_project_id=None,
        optional_skills=(),
        excluded=(),
        max_workers=5,
        attempt_limit=3,
        worktree_root="../demo-app.worktrees",
        source_roots=("src/demo_app",),
        unguided=(),
        unit_tests=("tests/unit/**",),
        release_method="none",
    )
    assert load_gate(tmp_path) == GateSettings(
        "walk", None, owner_approves_behavioural_test_removal=True
    )
    assert load_exceptions(tmp_path) == []


def test_absent_keys_take_their_defaults(tmp_path):
    write(tmp_path, PROJECT, 'stack = "neutral"\n')
    write(tmp_path, GATE, "")

    project = load_project(tmp_path)

    assert (project.max_workers, project.attempt_limit, project.unit_tests) == (
        5,
        3,
        ("tests/unit/**",),
    )
    assert project.worktree_root == f"../{tmp_path.name}.worktrees"
    assert load_gate(tmp_path) == GateSettings("walk", None, True)


def test_agents_keep_the_exact_model(tmp_path):
    write(
        tmp_path,
        PROJECT,
        'stack = "python"\n[agents.reviewer]\nharness = "claude"\nmodel = "claude-opus-5-5"\n',
    )

    assert load_project(tmp_path).reviewer == Agent("claude", "claude-opus-5-5")


def test_kit_exclude_is_loaded_and_normalised(tmp_path):
    write(
        tmp_path,
        PROJECT,
        'stack = "python"\n[kit]\nexclude = ["devctl", "tools/devctl/", "./.agents/skills/rs-tdd"]\n',
    )

    assert load_project(tmp_path).excluded == ("devctl", "tools/devctl", ".agents/skills/rs-tdd")


def test_this_repository_settings_load():
    project = load_project(ROOT)
    assert (project.repository, project.source_roots) == ("proxy-hatch/rapid-ship", ("rapid_ship",))
    # Nothing is excluded here, so status --strict holds every Kit file to its template.
    assert project.excluded == ()
    assert load_gate(ROOT).mode == "walk"


def test_a_missing_file_is_a_settings_error(tmp_path):
    with pytest.raises(SettingsError, match=re.escape(".rapid-ship/project.toml: missing")):
        load_project(tmp_path)


EXCEPTION = (
    '[[exception]]\nid = "EX-1"\npath = "a.py"\nrule = "S603"\nreason = "r"\nremove_when = "w"\n'
)


@pytest.mark.parametrize(
    ("relative", "text", "message"),
    [
        (PROJECT, "", "stack: required"),
        (PROJECT, "stack = \n", "project.toml: Invalid value"),
        (PROJECT, 'stack = "rust"\n', "stack: expected python or neutral"),
        (PROJECT, 'stack = "python"\n[test]\nunit = []\n', "unknown key 'test'"),
        (
            PROJECT,
            'stack = "python"\n[github]\nworker_app_id = true\n',
            "worker_app_id: expected an integer of at least 0",
        ),
        (
            PROJECT,
            'stack = "python"\n[dispatch]\nmax_workers = 0\n',
            "max_workers: expected an integer of at least 1",
        ),
        (PROJECT, 'stack = "python"\n[agents.worker]\nharness = "agy"\n', "model: required"),
        (
            PROJECT,
            'stack = "python"\n[agents.worker]\nharness = "agy"\nmodel = " m "\n',
            "model: required",
        ),
        (
            PROJECT,
            'stack = "python"\n[agents.worker]\nharness = "x"\nmodel = "m"\n',
            "harness: expected claude or codex or agy",
        ),
        (
            PROJECT,
            'stack = "python"\n[github]\nrepository = "not a repo"\n',
            "repository: expected owner/name",
        ),
        (
            PROJECT,
            'stack = "python"\n[tests]\nunit = "tests/unit/**"\n',
            "unit: expected a list of non-empty strings",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = "devctl"\n',
            "exclude: expected a list of non-empty strings",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = ["../outside"]\n',
            "exclude: expected paths inside the repository",
        ),
        (
            PROJECT,
            'stack = "python"\n[kit]\nexclude = ["/etc"]\n',
            "exclude: expected paths inside the repository",
        ),
        (GATE, 'mode = "run"\n', "mode: expected walk or flight"),
        (GATE, 'owner_approves_behavioural_test_removal = "false"\n', "expected true or false"),
        (
            GATE,
            "owner_approves_behavioral_test_removal = false\n",
            "unknown key 'owner_approves_behavioral_test_removal'",
        ),
        (GATE, "[thresholds.weekly]\nwindow = 7\n", "unknown key 'weekly'"),
        (EXCEPTIONS, EXCEPTION.replace('remove_when = "w"\n', ""), "remove_when: required"),
        (EXCEPTIONS, EXCEPTION + EXCEPTION, "EX-1 is listed twice"),
        (EXCEPTIONS, EXCEPTION.replace("EX-1", "EX-01"), "id: expected EX-<n>"),
        (
            EXCEPTIONS,
            EXCEPTION.replace('"a.py"', '"../a.py"'),
            "path: expected a path inside the repository",
        ),
    ],
)
def test_invalid_settings_raise_settings_error(tmp_path, relative, text, message):
    write(tmp_path, relative, text)

    with pytest.raises(SettingsError, match=re.escape(message)):
        LOADERS[relative](tmp_path)
```

Append to `tests/devctl/test_devctl_cli.py`:

```python
def test_a_settings_error_exits_2_with_its_message(monkeypatch, capsys):
    from devctl.settings import SettingsError

    def broken(args):
        raise SettingsError(".rapid-ship/gate.toml mode: expected walk or flight")

    monkeypatch.setattr(
        devctl_project,
        "register",
        lambda commands: commands.add_parser("go").set_defaults(handler=broken),
    )

    assert cli.main(["go"]) == 2
    assert "devctl: .rapid-ship/gate.toml mode: expected walk or flight" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/devctl -q`. Expected: `ModuleNotFoundError: No module named 'devctl.settings'`.

- [ ] **Step 3: Implement** in the template `devctl/settings.py`. Use the index's dataclasses verbatim, with `Harness`, `Stack`, `Mode` and `ReleaseMethod` as the `Literal` aliases the index spells out, and:

```python
class SettingsError(Exception):
    """A settings file is missing or invalid. devctl exits 2."""


class _Table:
    """One TOML table with known keys. Each accessor checks the value's type."""

    def __init__(self, value: object, where: str, keys: set[str]) -> None:
        if not isinstance(value, dict):
            raise SettingsError(f"{where}: expected a table")
        unknown = sorted(set(value) - keys)
        if unknown:
            raise SettingsError(f"{where}: unknown key {unknown[0]!r}")
        self.values: dict[str, object] = value
        self.where = where

    def table(self, key: str, keys: set[str]) -> _Table:
        return _Table(self.values.get(key, {}), f"{self.where} [{key}]", keys)

    def _error(self, key: str, expected: str) -> SettingsError:
        return SettingsError(f"{self.where} {key}: expected {expected}")

    def text(self, key: str, default: str = "") -> str:
        value = self.values.get(key, default)
        if not isinstance(value, str):
            raise self._error(key, "a string")
        return value

    def choice(self, key: str, options: tuple[str, ...], default: str | None = None) -> str:
        if key not in self.values and default is None:
            raise SettingsError(f"{self.where} {key}: required")
        value = self.values.get(key, default)
        if value not in options:
            raise self._error(key, " or ".join(options))
        return cast(str, value)

    def integer(self, key: str, default: int, minimum: int) -> int:
        value = self.values.get(key, default)
        # TOML true is a Python bool, which is also an int.
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise self._error(key, f"an integer of at least {minimum}")
        return value

    def boolean(self, key: str, default: bool) -> bool:
        value = self.values.get(key, default)
        if not isinstance(value, bool):
            raise self._error(key, "true or false")
        return value

    def texts(self, key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
        value = self.values.get(key, list(default))
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise self._error(key, "a list of non-empty strings")
        return tuple(value)
```

`_read(root, relative)` returns `tomllib.loads` of the file. `FileNotFoundError` becomes `SettingsError(f"{relative}: missing; rapid-ship init seeds it")`; `OSError`, `UnicodeDecodeError` and `tomllib.TOMLDecodeError` become `SettingsError(f"{relative}: {error}")`.

`load_project` reads the top table with keys `stack`, `agents`, `github`, `kit`, `linear`, `dispatch`, `map`, `tests` and `release`, and the sub-tables with the keys of the seed. `stack` is required, through `choice` without a default. `repository` is `text(...) or None` and must match `[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/[A-Za-z0-9._-]+`, else `repository: expected owner/name`. App IDs are `integer(..., 0, minimum=0) or None`; Linear IDs are `text(...) or None`. The defaults are those in the index, and `worktree_root` defaults to `f"../{root.name}.worktrees"`. `_agent(agents, role)` returns `None` when the role is absent. Otherwise it reads `harness` with `choice(("claude", "codex", "agy"))` and raises `model: required; record the exact model ID` when `model` is empty or `model.strip() != model`.

`[kit]` has the keys `optional` and `exclude`. `optional_skills` is `kit.texts("optional")`. `excluded` reads `kit.texts("exclude")`, then turns each entry into `PurePosixPath(entry)`. An absolute path, a `..` part, a backslash or no parts at all (`"."`) raises `SettingsError(f"{kit.where} exclude: expected paths inside the repository")`. Otherwise the entry becomes `"/".join(path.parts)`, which drops `./` and a trailing `/`.

`load_gate` reads `mode` (default `walk`), `flight_lease_until` (`""` becomes `None`) and `owner_approves_behavioural_test_removal` (default `True`). It validates `thresholds` as a table with keys `promotion` and `demotion`.

`load_exceptions` reads `exception` as a list. Each item is a table with exactly `id`, `path`, `rule`, `reason` and `remove_when`, each non-empty. The `id` must match `EX-[1-9][0-9]*` and be unique (`<id> is listed twice`). The `path` must be relative without `..`. Error messages use `where = f"{EXCEPTIONS} [[exception]] #{n}"`.

In the template `cli.py`, wrap the handler call:

```python
    try:
        return handler(args)
    except SettingsError as error:
        print(f"devctl: {error}", file=sys.stderr)
        return 2
```

- [ ] **Step 4: Vendor and run.** Run `uv run rapid-ship sync --in-place`. Expected: added `tools/devctl/devctl/settings.py`, updated `tools/devctl/devctl/cli.py`. Then run `uv run pytest tests/devctl -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `uv run rapid-ship status --strict`. Expected: all pass; exit 0.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: load rapid-ship settings in devctl

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 11: devctl repository helper

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/repo.py`; vendored copy (by sync)
- Modify: the template `devctl/cli.py`; vendored copy and `.rapid-ship/kit.lock` (by sync)
- Test: `tests/devctl/test_devctl_repo.py`, `tests/devctl/test_devctl_cli.py`

**Interfaces:**
- Consumes: Task 10.
- Produces: `RepoError(Exception)`; `Repo(root: Path, git_common_dir: Path)` with `Repo.discover(start: Path) -> Repo`, `tracked_files() -> list[str]` and `merge_base(ref: str) -> str | None`. `cli.main` maps `RepoError` to exit 2. Plan 3 Task 2 adds `files()` and `git(*args)`, and builds both on the private `_git(cwd, *args, allowed=(0,))` below.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_repo.py`:

```python
"""devctl's view of its git repository, in scratch repositories (offline)."""

import pytest

from devctl.repo import Repo, RepoError


def test_discover_finds_the_root_and_common_dir_from_a_subdirectory(git_repo):
    (git_repo / "sub").mkdir()

    repo = Repo.discover(git_repo / "sub")

    assert repo.root == git_repo.resolve()
    assert repo.git_common_dir == (git_repo / ".git").resolve()


def test_a_worktree_shares_the_main_common_dir(git_repo, commit_all, run_git):
    commit_all(git_repo)
    run_git(git_repo, "worktree", "add", "-q", str(git_repo.parent / "wt"), "-b", "other")

    assert Repo.discover(git_repo.parent / "wt").git_common_dir == (git_repo / ".git").resolve()


def test_tracked_files_lists_only_tracked_paths(git_repo, commit_all):
    (git_repo / "a file.txt").write_text("x\n")
    commit_all(git_repo)
    (git_repo / "untracked.txt").write_text("y\n")

    assert Repo.discover(git_repo).tracked_files() == ["a file.txt"]


def test_merge_base_returns_the_shared_commit_or_none(git_repo, commit_all, run_git):
    commit_all(git_repo, "first")
    first = run_git(git_repo, "rev-parse", "HEAD").strip()
    run_git(git_repo, "switch", "-q", "-c", "feature")
    commit_all(git_repo, "second")
    repo = Repo.discover(git_repo)
    assert repo.merge_base("main") == first

    run_git(git_repo, "switch", "-q", "--orphan", "lonely")
    commit_all(git_repo, "unrelated")
    assert repo.merge_base("main") is None
    with pytest.raises(RepoError, match="merge-base"):
        repo.merge_base("no-such-ref")


def test_outside_a_work_tree_is_a_repo_error(tmp_path):
    with pytest.raises(RepoError):
        Repo.discover(tmp_path)
```

Append to `tests/devctl/test_devctl_cli.py`:

```python
def test_a_repo_error_exits_2_with_its_message(monkeypatch, capsys):
    from devctl.repo import RepoError

    def broken(args):
        raise RepoError("git rev-parse: not a git repository")

    monkeypatch.setattr(
        devctl_project,
        "register",
        lambda commands: commands.add_parser("go").set_defaults(handler=broken),
    )

    assert cli.main(["go"]) == 2
    assert "devctl: git rev-parse: not a git repository" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests and see them fail.** Run `uv run pytest tests/devctl -q`. Expected: `ModuleNotFoundError: No module named 'devctl.repo'`.

- [ ] **Step 3: Implement** the template `devctl/repo.py`:

```python
class RepoError(Exception):
    """git is missing, or the directory is not in a work tree. devctl exits 2."""


def _git(
    cwd: Path, *args: str, allowed: tuple[int, ...] = (0,)
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False)
    except OSError as error:
        raise RepoError(f"cannot run git: {error}") from error
    if result.returncode not in allowed:
        raise RepoError(f"git {args[0]}: {result.stderr.decode(errors='replace').strip()}")
    return result


@dataclass(frozen=True)
class Repo:
    root: Path
    git_common_dir: Path

    @classmethod
    def discover(cls, start: Path) -> Repo:
        output = _git(
            start, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"
        ).stdout
        root, common = os.fsdecode(output).splitlines()
        return cls(Path(root), Path(common))

    def tracked_files(self) -> list[str]:
        output = _git(self.root, "ls-files", "-z").stdout
        return [os.fsdecode(name) for name in output.split(b"\0") if name]

    def merge_base(self, ref: str) -> str | None:
        """The merge base of HEAD and ref; None when they share no history (git exits 1)."""
        return (
            _git(self.root, "merge-base", "HEAD", ref, allowed=(0, 1)).stdout.decode().strip()
            or None
        )
```

On 2026-10-14 with git 2.39.5, `rev-parse --path-format=absolute --show-toplevel --git-common-dir` printed both paths from a subdirectory and gave the main `.git` from a linked worktree. `merge-base` exited 1 with no output for unrelated histories and 128 for an unknown ref. In `cli.py`, catch `(RepoError, SettingsError)` in the same handler.

- [ ] **Step 4: Vendor and run.** Run `uv run rapid-ship sync --in-place` (expected: added `tools/devctl/devctl/repo.py`, updated `tools/devctl/devctl/cli.py`), then `uv run pytest tests/devctl -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `uv run rapid-ship status --strict`. Expected: all pass; exit 0.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: give devctl a view of its git repository

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 12: Wheel contents and installed smoke

**Files:**
- Modify: `scripts/smoke_distribution.py`

**Interfaces:**
- Consumes: plan 1's `scripts/check.py`, which runs `uv build` and then this script in a temporary copy that holds exactly the files git keeps and has no `.git`; Tasks 1–11.
- Produces: a smoke that fails when the wheel lacks a template, imports the source checkout, or cannot init, pass `status --strict`, keep devctl's lock current or run `./devctl` in both a new project and an existing project with a uv workspace, or when that project's own `uv lock` fails once `tools/devctl` is excluded from its workspace.

- [ ] **Step 1: Write the smoke.** Replace `scripts/smoke_distribution.py`:

```python
"""Check the built wheel ships every template, then run its rapid-ship in scratch repositories."""

import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

TEMPLATES = "rapid_ship/templates/"
GIT = [
    "git",
    "-c",
    "user.name=Smoke",
    "-c",
    "user.email=smoke@example.invalid",
    "-c",
    "commit.gpgsign=false",
]
WORKSPACE_PYPROJECT = """[project]
name = "existing-app"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["tools/*"]
"""
# rs-setup adds this to the workspace table above (plan 5); without it the project's own uv lock fails.
DEVCTL_EXCLUDE = 'exclude = ["tools/devctl"]\n'


def run(cwd: Path, *command: str) -> str:
    print(f"Smoke: {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"Smoke failed ({result.returncode}): {' '.join(command)}\n{result.stdout}{result.stderr}"
        )
    return result.stdout


def expected_templates(root: Path) -> set[str]:
    """Template files git keeps. check.py's temporary copy holds exactly these and has no .git."""
    if (root / ".git").exists():
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                TEMPLATES,
            ],
            capture_output=True,
            check=True,
        ).stdout
        return {os.fsdecode(name) for name in listed.split(b"\0") if name}
    return {
        path.relative_to(root).as_posix()
        for path in (root / TEMPLATES).rglob("*")
        if path.is_file()
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / "dist").glob("rapid_ship-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected one rapid-ship wheel in dist/; run uv build first")
    with zipfile.ZipFile(wheels[0]) as wheel:
        shipped = {name for name in wheel.namelist() if name.startswith(TEMPLATES)}
    missing = sorted(expected_templates(root) - shipped)
    if missing:
        raise SystemExit(
            "The wheel lacks template files; hatch drops git-ignored paths:\n" + "\n".join(missing)
        )
    with tempfile.TemporaryDirectory(prefix="rapid-ship-smoke-") as temporary:
        work = Path(temporary).resolve()
        run(work, "uv", "venv", "--quiet", str(work / "venv"))
        python = str(work / "venv/bin/python")
        run(work, "uv", "pip", "install", "--quiet", "--python", python, str(wheels[0]))
        location = Path(
            run(work, python, "-I", "-c", "import rapid_ship; print(rapid_ship.__file__)").strip()
        )
        if location.resolve().is_relative_to(root):
            raise SystemExit("The smoke imported the source checkout instead of the wheel")
        rapid_ship = str(work / "venv/bin/rapid-ship")

        new = work / "new-app"
        new.mkdir()
        run(new, *GIT, "init", "-q")
        run(new, rapid_ship, "init", "--stack", "python", "--owner", "smoke-owner")
        run(new, rapid_ship, "status", "--strict")
        run(new, "uv", "lock", "--check", "--project", "tools/devctl")
        version = run(new, "./devctl", "--version")

        existing = work / "existing-app"
        existing.mkdir()
        (existing / "pyproject.toml").write_text(WORKSPACE_PYPROJECT)
        run(existing, *GIT, "init", "-q")
        run(existing, *GIT, "add", "pyproject.toml")
        run(existing, *GIT, "commit", "-q", "-m", "Existing project")
        run(existing, rapid_ship, "init")
        if run(existing, "./devctl", "--version") != version:
            raise SystemExit("devctl reported different versions in the two projects")
        with (existing / "pyproject.toml").open("a", encoding="utf-8") as pyproject:
            pyproject.write(DEVCTL_EXCLUDE)
        run(existing, "uv", "lock")
        run(existing, "uv", "lock", "--check", "--project", "tools/devctl")
    print("Wheel templates, isolated init, status and devctl smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The existing project runs `./devctl` before the exclude, as between `init` and `rs-setup`, and its own `uv lock` after it, as `rs-setup` leaves the project. Without the exclude that `uv lock` fails with `Nested workspaces are not supported` (Task 9).

- [ ] **Step 2: Show that the template check fails on a dropped file.** Run:

```bash
rm -rf dist
mkdir -p rapid_ship/templates/common/build && echo probe > rapid_ship/templates/common/build/probe.txt
git add -f rapid_ship/templates/common/build/probe.txt
uv build && uv run python scripts/smoke_distribution.py
```

Expected: exit 1, `The wheel lacks template files; hatch drops git-ignored paths:` and `rapid_ship/templates/common/build/probe.txt`, because the root `.gitignore` pattern `build/` keeps it out of the wheel. Then remove it: `git rm -q --cached rapid_ship/templates/common/build/probe.txt && rm -r rapid_ship/templates/common/build`.

- [ ] **Step 3: Run the smoke and the full check.** Run `rm -rf dist && uv build && uv run python scripts/smoke_distribution.py`. Expected: `Wheel templates, isolated init, status and devctl smoke passed.` It needs uv's cache or the network for `tomli-w` and hatchling. Then run `uv run python scripts/check.py`. Expected: `Python and repository validation passed.`

- [ ] **Step 4: Commit.**

```bash
git add scripts/smoke_distribution.py
git commit -m "test: smoke the installed wheel's init, status and devctl

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 13: Verification and guides

**Files:**
- Modify: `AGENTS.md`, `rapid_ship/AGENTS.md`, `tests/AGENTS.md`, `scripts/AGENTS.md`, `docs/AGENTS.md`, `.github/AGENTS.md`, `ARCHITECTURE.md`, `docs/superpowers/plans/2026-10-14-kit-and-setup.md` (index), this plan
- Create: `rapid_ship/kit/AGENTS.md`

**Interfaces:**
- Consumes: Tasks 1–12.
- Produces: guides that match the code, an updated index and the verification record below.

- [ ] **Step 1: Update the guides.**
  - Root `AGENTS.md`: a "Find the change" row for the Kit CLI pointing to `rapid_ship/kit/AGENTS.md`; a row for the vendored devctl pointing to `rapid_ship/templates/AGENTS.md` (edit templates, then sync); commands `uv run rapid-ship status --strict` and `uv run rapid-ship sync --in-place`.
  - `rapid_ship/AGENTS.md`: rows for `kit/` and `templates/`; `files.py` also owns `safe_path`, `relative_parts` and `create_file`.
  - New `rapid_ship/kit/AGENTS.md`: one line per module. `templates.py` covers the manifest and rendering, including which template files count, `lock.py` the lock, `init.py` create-only all-or-nothing writes, `status.py` read-only classification, `sync.py` merges, branch, PR and restoring the work tree after a failed write, and `git.py` the git calls. `KitError` exits 2 and `KitRefusal` exits 1. Tests are `tests/test_kit_*.py`; sync's push and PR use a fake there.
  - `tests/AGENTS.md`: replace plan 1's "Keep tests flat and name them for the behavior or module they cover." with "Keep tests flat, except devctl's tests, which go in `devctl/` as `test_devctl_*.py`. Name each test for the behavior or module it covers." Add rows for `test_kit_*.py`, `conftest.py` (template trees, scratch repositories) and `devctl/`, which imports the vendored copy and must have no `__init__.py`.
  - `scripts/AGENTS.md`: what `smoke_distribution.py` now checks, and that `check.py` runs `status --strict`.
  - `docs/AGENTS.md`: `features/` and `patterns/` and their formats.
  - `.github/AGENTS.md`: `CODEOWNERS` is seeded by the Kit; Walk assigns every path to the owner.
  - `ARCHITECTURE.md`: the rapid-ship CLI section matches what was built (commands, `rapid_ship/kit/`, lock, templates, dog-food); add a short section if plan 1 left none.

- [ ] **Step 2: Update the plan index.** The index already records this plan's lock, manifest, template, settings, repository and CLI interfaces; check each against the code and fix any drift. The index asks a plan to change it in the same PR when it needs something different. Check that its Conventions' Kit version line already says that:
  - each Kit release is a tag `v<version>` on `main`, created by the owner;
  - owners run `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>`, or `--from <local checkout>` before the first tag;
  - `sync` fetches its merge base from the tag `v<old>`, and without that tag lists every needed merge as a conflict.

  Fix the line if it differs. Then make these changes:
  1. Template rules: change "When a symlink cannot be made, `init` and `sync` exit 2" to end "exit 2 and leave nothing half-written". Add: "Template discovery skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files, and, when the template root's `kit.toml` is tracked by git, every path git does not keep."
  2. CODEOWNERS: `/pyproject.toml` appears only in the Python stack's template.

- [ ] **Step 3: Run the whole verification.** Record the actual output of each command below.

```bash
uv lock --check
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run rapid-ship status --strict
uv run python scripts/check_repository.py
uv run python scripts/check.py
rm -rf dist && uv build && uv run python scripts/smoke_distribution.py
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
git status --porcelain
```

Expected:
- `uv lock --check` exits 0.
- pytest reports no failures and no errors. Record the counts; skipped tests are not passes.
- ruff prints `All checks passed!` and every file is already formatted.
- mypy reports `Success` with N source files, N matching the `git ls-files` count from Task 9.
- `status --strict` exits 0, and the navigation check passes.
- `check.py` prints `Python and repository validation passed.`
- The smoke prints its pass line.
- The docs build succeeds with no broken links and publishes the feature and Pattern READMEs.
- `git status --porcelain` is empty after Step 4's commit.

- [ ] **Step 4: Fill in the record below, then commit.**

```bash
git add AGENTS.md ARCHITECTURE.md rapid_ship/AGENTS.md rapid_ship/kit/AGENTS.md tests/AGENTS.md scripts/AGENTS.md docs/AGENTS.md .github/AGENTS.md docs/superpowers/plans/2026-10-14-kit-and-setup.md docs/superpowers/plans/2026-10-14-rapid-ship-cli.md
git commit -m "docs: guide the rapid-ship CLI and record its verification

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Verification record

Fill this in from Task 13, Step 3. Record actual output. A skipped, blocked or simulated check is not a pass.

Run on 2026-10-15 at base `6f140ed` plus this task's edits, on macOS with git 2.39.5 and uv 0.11.0. The default environment is Python 3.13.12.

| Check | Command | Result |
| --- | --- | --- |
| Lock current | `uv lock --check` | Exit 0: `Resolved 14 packages in 31ms`. |
| Tests | `uv run pytest` | `284 passed in 25.44s`: no failures, no errors, no skips. `scripts/check.py` also ran the same suite on Python 3.12.10 in a scratch environment: `284 passed in 26.49s`. The tests are offline; `uv build` and the smoke need uv's cache or the network. |
| Lint and format | `uv run ruff check . && uv run ruff format --check .` | `All checks passed!` and `117 files already formatted`. Ruff also formats the Python blocks in Markdown: its first run flagged this plan's index (`1 file would be reformatted`, three new signature comments over 100 columns), which was fixed by shortening them. |
| Types, devctl checked once | `uv run mypy` | `Success: no issues found in 17 source files`. `git ls-files --cached --others --exclude-standard 'rapid_ship/*.py' 'tools/devctl/*.py' \| grep -v '^rapid_ship/templates/' \| wc -l` printed `17`, so each file is checked once. |
| Vendored Kit equals templates | `uv run rapid-ship status --strict` | Exit 0: `Kit 0.1.0 (installed rapid-ship 0.1.0), stack python` and `8 managed files unchanged.` |
| Navigation | `uv run python scripts/check_repository.py` | Exit 0: `Repository navigation and skill aliases passed.` The new and edited guides, including `rapid_ship/kit/AGENTS.md`, were in the tree. |
| Full validation | `uv run python scripts/check.py` | Exit 0, `Python and repository validation passed.` It ran navigation, `status --strict`, ruff check and format, mypy, 284 tests, `uv build` and the smoke in a temporary copy. The same command also passed on Python 3.12.10 in a scratch environment (`UV_PROJECT_ENVIRONMENT` set to a scratch directory, `uv run --python 3.12`). |
| Wheel templates and installed smoke | `rm -rf dist && uv build && uv run python scripts/smoke_distribution.py` | `Successfully built dist/rapid_ship-0.1.0.tar.gz` and `dist/rapid_ship-0.1.0-py3-none-any.whl`; the smoke ended with `Wheel templates, isolated init, status and devctl smoke passed.` (exit 0). |
| Template check catches a dropped file | Task 12, Step 2 | Re-run here with `rapid_ship/templates/common/build/probe.txt` added by `git add -f`: after `uv build`, the smoke exited 1 and printed `The wheel lacks template files; hatch drops git-ignored paths:` and `rapid_ship/templates/common/build/probe.txt`. The probe was then removed and `git status` showed only this task's files. |
| Docs site | `npm --prefix website ci --no-audit --no-fund`, then `npm --prefix website run build` | `ci`: `added 1259 packages in 7s`, with `allow-scripts` warnings for `core-js` and `fsevents` only. `build`: `[SUCCESS] Generated static files in "build".` The site sets `onBrokenLinks` and `onBrokenAnchors` to `throw`. `website/build/docs/features/index.html` and `website/build/docs/patterns/index.html` exist. |
| Clean work tree | `git status --porcelain` | Empty after this task's commit. |

Re-run on 2026-10-15 after the final review fixes F-1 to F-3, at base `34cdbfe` plus those edits: `uv run pytest` gave `291 passed`, with no failures, errors or skips. `uv lock --check`, ruff check and format (`117 files already formatted`), mypy (`17 source files`), `status --strict`, the navigation check, `scripts/check.py`, `uv build` with the smoke, and the docs build passed again.

Re-run on 2026-10-15 after the remaining minor fixes F-5 to F-10, at base `d16e24b` plus those edits: `uv run pytest` gave `308 passed`, with no failures, errors or skips. `uv lock --check`, ruff check and format (`117 files already formatted`), mypy (`17 source files`), `status --strict` (`8 managed files unchanged.`), the navigation check, `scripts/check.py` (`Python and repository validation passed.`) and the docs build (`[SUCCESS] Generated static files in "build".`) passed again.

Owner steps (outside state):

- Done 2026-10-15: tag `archive/controller-2026-10`, carried from plan 1. With the owner's approval, the tag was created at `origin/main` `f7b877b` and pushed after plan 1's three confirmations held. `gh api 'repos/proxy-hatch/rapid-ship/contents/examples/environments.json?ref=archive/controller-2026-10' --jq .name` printed `environments.json`. Plan 1's Verification record has the details.
- Pending: the CODEOWNERS login `proxy-hatch` (Task 8, Step 2). Task 8 re-confirmed it with the read-only `gh api user --jq .login`. The owner confirms it again at PR review.
- Done 2026-10-15: push `codex/rapid-ship-cli`, open its PR under the owner's login and read the hosted results. PR proxy-hatch/rapid-ship#29, `feat: add rapid-ship init, status and sync and vendor the Kit`, opened 2026-10-15 against `codex/remove-controller`, so it is stacked on plan 1's PR instead of waiting for plan 1 to merge. At `9c89201`, CI `checks (3.12)` and `checks (3.13)` passed in both the `push` and the `pull_request` run, and the Docs `build` passed. Hosted CI runs `scripts/check.py`, which includes `status --strict`. The Docs `deploy` job was skipped; it runs only on pushes to `main`. `gh pr checks 29 --repo proxy-hatch/rapid-ship` exited 0. These results apply to `9c89201` only. The merge of `codex/remove-controller` and this record commit get their own hosted runs when the owner pushes them.

Known limits to confirm or update:

- Not covered: sync's `git push` and `gh pr create` ran only against a fake (offline tests); no live sync PR was opened. The push tests use a local bare repository, and the `gh` tests use a stand-in script.
- Superseded 2026-10-15: sync no longer merges; edited files become the project's own (follow-up 2). Previously: not covered: sync's merge base fetched from a real tag with `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<old>`. The repository had no tags on 2026-10-14, and `git ls-remote --tags origin 'archive/*' 'v*'` still printed nothing on 2026-10-15. Tests inject the old templates, and one test checks the `uvx` command against a fake `subprocess.run`. The owner creates each tag `v<version>` on `main` (spec section 3); until the first one exists, sync lists every merge it needs as a conflict.
- Not covered: a symlink failure on a real filesystem. Tests make `os.symlink` raise `EPERM`. With `core.symlinks=false`, git checks a link out as a small plain file holding the link text (git-config documentation); `status` reports such a link as modified.
- Resolved 2026-10-15: hosted CI. PR #29's CI on Python 3.12 and 3.13, including `status --strict`, and its Docs workflow passed at `9c89201` (owner steps above). Previously: not covered: hosted CI; `scripts/check.py` had passed only locally, on Python 3.13.12 and in a scratch environment on Python 3.12.10.
- Superseded 2026-10-15: sync no longer merges; edited files become the project's own (follow-up 2). Previously: limit, decided 2026-10-15: a sync that both changes other files and hits a conflict moves the lock's `kit_version` to the new version, while the conflicted file keeps its old entry. Later syncs then report `the locked copy is not rapid-ship <old>'s template, so there is no merge base` for it, and `status --strict` reports it outdated. Applying the template's diff by hand while keeping the project's edit does not clear it. Only two ways out remain: make the file equal the new template, which discards the edit, or list its path under `[kit] exclude`, which stops its updates. Any release that changes two files can cause this. The sync output and the PR body name both ways out, and the conflict reason no longer says to apply the diff by hand. `test_a_conflict_beside_other_changes_clears_only_by_the_ways_out` pins this behaviour. The owner accepted it: a conflicted file is the project's own diff, like an excluded file. Spec section 3 says so in sync step 4 and in "Who owns what". No per-file Kit version is planned.
- Resolved: `sync --in-place` skips the clean-work-tree check, so it works on uncommitted template edits, as the spec's Dog-fooding paragraph needs. Without `--in-place`, sync still refuses a dirty tree. Spec section 3 sync step 1 now allows it (d16e24b).
- Limit: a seeded lock entry whose template a later Kit drops stays in the lock. `status` ignores it and `sync` never reports it.
- Limit: `status` and `sync` compare a managed file's content, not its mode. After `chmod -x devctl`, `status --strict` exits 0 and `sync --in-place` says the Kit is current (observed in a scratch repository). `sync` sets the execute bit only when it writes the file, so the owner restores it with `chmod +x devctl`.
- Limit, decided 2026-10-15, revised: the Kit installs at the repository root only; `init` run from a subdirectory installs at the top of the work tree. Several stacks in one repository (monorepos) is a backlog item. `test_init_from_a_subdirectory_installs_at_the_top_of_the_work_tree` in `tests/test_kit_cli.py` pins this.
- Built 2026-10-15: `init` names the project after its GitHub repository (owner decision F-9). The default is, in order: the name in `--repository`; the name in a github.com `origin` URL (`https://`, `http://`, `ssh://` or `git@github.com:`, with a trailing `.git` and `/` removed); the main checkout's directory name, from `git rev-parse --path-format=absolute --git-common-dir`, so a linked worktree such as `.claude/worktrees/<random-name>` gets the main checkout's name; and, outside a git work tree or when git cannot run, the directory's own name. `--name` overrides it. The remote URL can carry a token, so no error message prints it, only the parsed name. A repository name that is not a valid project name, such as `.github`, needs `--name`; `test_a_repository_name_that_is_not_a_project_name_needs_the_name_option` pins this. Not built: `[project] name` from an existing `pyproject.toml`. Tests in `tests/test_kit_init.py`: `test_a_github_remote_url_gives_its_repository_name`, `test_another_host_or_an_unparsable_url_gives_no_name`, `test_variables_default_to_the_origin_repository_name`, `test_the_repository_option_beats_the_origin_remote`, `test_the_name_option_beats_the_repository_and_the_origin`, `test_a_non_github_origin_falls_back_to_the_checkout_directory`, `test_a_linked_worktree_without_a_remote_uses_the_main_checkout_name` and `test_an_invalid_origin_name_is_named_without_the_url_or_its_token`.
- Built 2026-10-15 (follow-up 2), owner decisions on the design PR:
  - A. An edited or deleted managed file becomes the project's own; the three-way merge is gone. `sync` never changes such a file. It records the entry as seeded with the current template's hash, lists the path as the project's own and prints `rapid-ship sync --revert <path>` once. `--revert` writes the current template back and records the entry as managed again. It refuses, with exit 1 and before any write, a path that is not a Kit file, is excluded, is seeded, or whose template the Kit dropped. `status` reports a later template change to such a file as `template updated` and explains that the next `sync` makes a modified or missing file the project's own. `git merge-file`, the release fetch, the conflict diff and the ways-out text are removed, so `sync` no longer needs release tags. A conflict is now only a new Kit path that a project file or a symlink blocks. The seeded root `AGENTS.md` carries the rule. Tests: `tests/test_kit_sync_ownership.py` (`test_an_edited_file_becomes_the_projects_own_with_the_current_template_hash`, `test_an_edit_becomes_the_projects_own_when_the_template_did_not_change`, `test_a_deleted_file_becomes_the_projects_own_and_is_not_restored`, `test_a_later_template_change_to_an_owned_file_is_reported_and_not_applied`, `test_a_repointed_skill_link_becomes_the_projects_own_and_revert_restores_it`, `test_revert_writes_the_current_template_and_manages_the_file_again`, `test_revert_takes_back_an_edit_that_sync_has_not_recorded`, `test_revert_refuses_a_path_it_cannot_revert_and_writes_nothing`, `test_an_edited_kit_skill_becomes_the_projects_own_and_keeps_its_link`, `test_an_excluded_file_the_project_edited_is_left_unreported`); `tests/test_kit_sync.py` (`test_dropped_files_are_deleted_only_when_unchanged`, `test_the_pull_request_body_lists_owned_files_and_the_way_back`); `tests/test_kit_status.py` (`test_a_managed_file_the_project_made_its_own_reports_only_template_updates`); `tests/test_kit_cli.py` (`test_sync_makes_edited_and_deleted_files_the_projects_own_and_says_how_to_revert`, `test_sync_revert_restores_a_file_and_refuses_a_seeded_one`, `test_strict_status_fails_on_a_modified_managed_file`).
  - B. `init` commits the Kit on its own branch. On a clean work tree it creates `rapid-ship/init` at HEAD, from any branch or a detached HEAD, writes the Kit, and commits exactly the created files and the lock as `chore: vendor the rapid-ship Kit <version>`. A repository with no commits gets the Kit as its first commit on the current branch. An existing `rapid-ship/init` is refused before any write. A dirty tree is refused with up to 20 paths listed. A failed switch, write, add or commit removes what `init` created, switches back and deletes the branch. Tests: `tests/test_kit_init.py` (`test_init_commits_exactly_the_kit_on_its_own_branch`, `test_init_from_a_detached_head_branches_at_that_commit`, `test_init_without_commits_makes_the_first_commit_on_the_current_branch`, `test_init_refuses_an_existing_init_branch_before_writing`, `test_a_dirty_tree_is_listed_up_to_20_paths_and_nothing_is_written`, `test_a_failed_commit_restores_the_starting_state`, `test_a_failed_write_on_the_init_branch_switches_back_and_deletes_it`); `tests/test_kit_cli.py` (`test_init_prints_its_branch_its_commit_and_the_next_step`); and `scripts/smoke_distribution.py`, which checks the commit in both scratch projects.
  - C. The `neutral` stack is renamed `agnostic`: `--stack agnostic`, `rapid_ship/templates/agnostic/`, the lock and settings value, devctl's settings, the tests and the spec. There is no migration, because nothing was released.
  - Fixed 2026-10-15 (follow-up 2, fix round 1): every git call in `rapid_ship/kit/git.py` runs with `core.hooksPath=/dev/null`, so `init` and `sync` run no git hook, not even from a tracked hooks path; `--no-verify` had skipped only pre-commit and commit-msg. Both commands create their branch with `git branch` and switch to it inside their undo, so a switch that fails, even after git switched, returns to the start and deletes the branch. A git failure with no message names its exit status. Tests: `tests/test_kit_hooks.py` (`test_init_runs_no_hook_from_a_tracked_hooks_path`, `test_sync_runs_no_hook_from_a_tracked_hooks_path`, `test_a_failed_switch_to_the_init_branch_restores_the_start`, `test_a_failed_switch_to_the_sync_branch_restores_the_start`) and `tests/test_kit_git.py` (`test_git_runs_no_hook_even_when_the_repository_sets_one`, `test_a_failure_that_prints_nothing_names_its_exit_status`).
  - Fixed 2026-10-15 (follow-up 2, fix round 1): `status --strict` passes a managed file that `sync` recorded as the project's own, because its entry is seeded. In this repository, `tests/test_kit_dogfood.py::test_no_kit_managed_file_is_this_repositorys_own` fails on any such entry that is not excluded, and `test_an_edit_that_sync_makes_the_projects_own_passes_strict_but_not_this_check` shows the case it catches. `--strict` is unchanged, because in other projects an owned file is the owner's choice.
- Cascade, owed before plans 3 to 5 merge: they were written before follow-up 2, plan 3 was built on `codex/devctl-check` from a6ba3bf, and `codex/github-commands` starts from plan 3's head, so they still describe the removed behaviour. Bring each up to date with the rename to `agnostic`, the ownership model in place of the merge, `init`'s commit on `rapid-ship/init`, and git calls without hooks:
  - Plan index, `2026-10-14-kit-and-setup.md` conventions: "`sync` fetches its merge base from the tag `v<old>`" no longer holds; sync needs no tag.
  - Plan 3, `2026-10-14-devctl-check.md` Task 6 step 2: the lock reader accepts stack `python` or `neutral`, so it rejects every lock `init` now writes (`stack = "agnostic"`). On `codex/devctl-check` this is code: `devctl/check/kit.py` (`_STACKS`), `devctl/settings.py` (`Stack`), `devctl/check/stacks/neutral.py` and their tests.
  - Plan 3 Task 6, the `kit` step's message for a missing managed file, "restore it or run rapid-ship sync": `rapid-ship sync` now keeps the deletion as the project's own. Name both choices, as spec section 5's `kit` row now does: `rapid-ship sync --revert <path>` restores the file, and `rapid-ship sync` keeps the deletion.
  - Plan 3 Task 18, the exceptions list for `rapid_ship/kit/sync.py`: `merge_file` and `released_templates` no longer exist.
  - Plan 4, `2026-10-14-github-commands.md` Task 12 step 2: run `init --stack agnostic`; `init` commits on `rapid-ship/init`, so merge that branch instead of committing the Kit to `main` by hand.
  - Plan 5, `2026-10-14-kit-skills.md` Task 11 step 2: `init` commits by itself on `rapid-ship/init`, so drop the `git switch -c` and `git commit` after it. Task 7's exclusion steps say sync never "merges" an excluded path; sync no longer merges anything.
