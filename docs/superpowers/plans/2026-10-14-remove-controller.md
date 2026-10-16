# Remove the old controller implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the old controller and leave a green repository whose package provides only `rapid-ship --version`, with the controller-era records archived and the remaining guides marked historical.

**Architecture:** Delete the controller package, its tests, examples, templates, build scripts and the two skills that drive it, and replace the `devctl` console script with a version-only `rapid-ship` CLI. `scripts/check.py` keeps navigation, lint, format, types, tests, the build and a distribution smoke that installs the wheel and runs `rapid-ship --version`. The documentation moves the controller-era records into `docs/archive/orchestrator/`, rewrites the root documents for the new scope and marks the remaining old guides historical.

**Tech Stack:** Python 3.12+ (argparse, importlib.metadata, tomllib), uv, hatchling, pytest, Ruff, mypy; Docusaurus 3.10.2 for the docs site.

**Spec:** [Spec 1: Kit and Setup](../specs/2026-10-14-kit-and-setup-design.md), section 2. Plan 1 of 5 in the [plan index](2026-10-14-kit-and-setup.md).

## Global Constraints

- This is the first PR of Spec 1. When it lands, CI (`uv run python scripts/check.py` on Python 3.12 and 3.13), the navigation check and the docs site build pass.
- Start from `main` after the design PR has merged; it adds the specs, the plan index, `docs/adr/` and `docs/archive/`. Branch: `codex/remove-controller`. The `codex/` prefix applies until Task 4 rewrites that rule. Never use `rs/`.
- Keep `rapid_ship/files.py`, `rapid_ship/process.py`, `tests/test_files.py` and `tests/test_process.py` unchanged. Later plans reuse them (spec section 2, borrow list).
- Keep the `rapid-ship-engineering` skill. Delete only the `rapid-ship` and `rapid-ship-improve` skills.
- `rapid-ship --version` prints exactly `rapid-ship <version>`, read with `importlib.metadata`. The CLI has no commands yet.
- Exit codes, as the index sets them: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run. When both 1 and 2 apply, 2 wins. This version never exits 1: `--version` exits 0 and anything else exits 2.
- Add no dependency. Drop `pydantic`: nothing kept imports it. Plan 2 adds `tomli-w`, the CLI's only dependency.
- Write tests first. Label offline and simulated tests as such. A blocked or skipped step never counts as passed.
- The docs site gets only what keeps it building and honest: remove the moved pages from `website/sidebars.js`. Leave the navbar, footer and other site configuration unchanged.
- Removal date: every new mention uses the phrase `removed on 2026-10-14`. If the PR merges on a later day, replace each occurrence that `git grep -n 'removed on 2026-10-14'` finds before merging.
- Each old guide gets this line below its title: `> **Historical:** describes the controller removed on 2026-10-14. See the [rapid-ship design](superpowers/specs/2026-10-14-rapid-ship-design.md).`
- Root `AGENTS.md` states: "Metrics never grant Flight, and they end it automatically."
- The tag `archive/controller-2026-10` marks the last commit that contains the controller. The owner creates and pushes it just before merging (Task 7).

## Review Focus

1. **A kept file still names a deleted module or path.** A remaining test imports `rapid_ship.project…`, `pyproject.toml:52` still lists the `tests/typecheck_*.py` fixtures, `pyproject.toml:18` still points `devctl` at the old CLI, or a guide links a deleted file. Expected: `uv run pytest` collects without errors, `uv run mypy` checks 5 files under `rapid_ship`, the navigation check passes and the Task 2 `git grep` prints nothing. Task 2 owns these checks.
2. **State left by the controller in existing checkouts.** The primary checkout still holds `.controller/` and `.controller-setup.lock` (observed on 2026-10-14). Removing their sdist excludes (`pyproject.toml:34`) is safe only while `.gitignore:17-19` keeps them ignored; otherwise Ruff, which respects `.gitignore`, lints a virtualenv and `uv build` packs it. Expected: `git check-ignore` reports each path ignored. Task 2 adds `test_state_left_by_the_removed_controller_stays_ignored`.
3. **Skill aliases outlive their skills.** Deleting `rapid_ship/skills/rapid-ship*` without the four symlinks under `.agents/skills` and `.claude/skills`, or leaving an untracked dangling alias, keeps agents discovering a deleted skill. Expected: both surfaces hold exactly `rapid-ship-engineering`. Task 3 adds `test_checkout_discovers_exactly_the_packaged_skills`.
4. **Anchored links into the rewritten `ARCHITECTURE.md`.** `docs/usage.md:23` links `#project-setup` and `docs/superpowers/plans/2026-10-10-bootstrap.md:3` links `#develop-the-framework`. The site throws on broken anchors (`website/docusaurus.config.js:15`). Expected: both links resolve after the rewrite. Task 4's site build pins it.
5. **Links into and out of the moved records.** Incoming links from four old guides and two AGENTS.md guides, outgoing `docs/authority.md:13` → `metrics.md`, and four sidebar IDs (`website/sidebars.js:17,20,22,23`) break on the move. Moving with the same relative layout keeps the links among the moved files valid. Expected: the site build and navigation pass, and the old-path `git grep` prints nothing. Task 5 pins it. The link from `docs/environments.md:24` to the deleted `examples/` is fixed in Task 2, where `examples/` goes.

## Starting point

- [ ] Confirm the design PR has merged and the controller is still on `main`:

```sh
git fetch origin
git switch -c codex/remove-controller origin/main
git ls-files docs/superpowers/specs/2026-10-14-kit-and-setup-design.md docs/superpowers/plans/2026-10-14-kit-and-setup.md docs/archive/orchestrator/README.md docs/adr/0003-walk-on-bare-sessions-orchestrator-deferred.md
git cat-file -e HEAD:rapid_ship/execution/controller.py && echo "controller present"
uv sync --locked
uv run python scripts/check.py
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
```

Expected: all four paths listed, `controller present`, `Python and repository validation passed.` and a successful site build. If a path is missing, stop: the design PR has not merged. If the site build fails before any change, for example on a broken link or anchor in the design PR's documents, stop and report it; this plan cannot show its own docs changes are safe against a red baseline.

### Task 1: Validate without the controller install stages

**Files:**
- Modify: `scripts/check.py:44-52`
- Test: `tests/test_check.py` (rewrite)
- Modify: `.github/AGENTS.md:3,9`

**Interfaces:**
- Consumes: `uv build`; `scripts/smoke_distribution.py`, unchanged in this task.
- Produces: the stage order of `scripts/check.py`: `scripts/check_repository.py`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest` in the checkout, then `uv build` and `scripts/smoke_distribution.py` in a temporary copy. Plan 2 adds a `rapid-ship status --strict` stage. Plan 3 replaces the script with `devctl check`, which follows the index's step order, and moves the build and smoke into a `distribution` step.

- [x] **Step 1: Write the failing test.** Replace `tests/test_check.py` with:

```python
"""Offline, simulated: run the validation entry point with stand-ins, without nested test runs."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAND_IN = """import json, os, pathlib, sys
root = pathlib.Path.cwd()
name = pathlib.Path(sys.argv[0]).stem
with open(os.environ["STAGE_LOG"], "a") as log:
    log.write(json.dumps({"name": name, "args": sys.argv[1:], "root": str(root)}) + "\\n")
if name == os.environ.get("FAIL_STAGE"):
    sys.exit(9)
if name == "uv":
    assert sys.argv[1:] == ["build"]
    assert root != pathlib.Path(os.environ["SOURCE_ROOT"])
    assert (root / "source.py").read_text() == "edited\\n"
    assert (root / "new.py").read_text() == "new source\\n"
    assert (root / "alias").is_symlink()
    assert (root / "alias").readlink() == pathlib.Path("source.py")
    assert not (root / "ignored").exists()
    (root / "dist").mkdir()
if name == "smoke_distribution":
    assert (root / "dist").is_dir()
"""


def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/check.py", root / "scripts/check.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("ignored/\ndist/\n")
    (root / "source.py").write_text("original\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    (root / "source.py").write_text("edited\n")
    (root / "new.py").write_text("new source\n")
    (root / "alias").symlink_to("source.py")
    (root / "ignored").mkdir()
    (root / "ignored/state").write_text("local state\n")
    for name in ("ruff", "mypy", "pytest"):
        (root / f"{name}.py").write_text(STAND_IN)
    for name in ("check_repository", "smoke_distribution"):
        (root / "scripts" / f"{name}.py").write_text(STAND_IN)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "uv").write_text(f"#!{sys.executable}\n" + STAND_IN)
    (tools / "uv").chmod(0o755)
    record = tmp_path / "stages.jsonl"
    environment = {
        **os.environ,
        "PATH": f"{tools}:{os.environ['PATH']}",
        "STAGE_LOG": str(record),
        "SOURCE_ROOT": str(root),
    }
    return root, record, environment


def run(root, environment):
    return subprocess.run(
        [sys.executable, str(root / "scripts/check.py")],
        cwd=root.parent,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def stages(record):
    return [json.loads(line) for line in record.read_text().splitlines()]


def test_validation_checks_the_checkout_then_builds_a_temporary_copy(tmp_path):
    root, record, environment = checkout(tmp_path)

    result = run(root, environment)

    assert result.returncode == 0, result.stdout + result.stderr
    observed = stages(record)
    assert [stage["name"] for stage in observed] == [
        "check_repository",
        "ruff",
        "ruff",
        "mypy",
        "pytest",
        "uv",
        "smoke_distribution",
    ]
    assert observed[1]["args"] == ["check", "."]
    assert observed[2]["args"] == ["format", "--check", "."]
    assert observed[3]["args"] == []  # Use the complete file list configured in pyproject.toml.
    assert all(stage["root"] == str(root) for stage in observed[:5])
    assert len({stage["root"] for stage in observed[5:]}) == 1
    assert not Path(observed[-1]["root"]).exists()
    assert (root / "ignored/state").read_text() == "local state\n"
    assert not (root / "dist").exists()


@pytest.mark.parametrize("failed_stage", ["check_repository", "mypy", "uv", "smoke_distribution"])
def test_validation_stops_after_failure_and_cleans_temporary_source(tmp_path, failed_stage):
    root, record, environment = checkout(tmp_path)

    result = run(root, {**environment, "FAIL_STAGE": failed_stage})

    assert result.returncode == 9, result.stdout + result.stderr
    observed = stages(record)
    assert observed[-1]["name"] == failed_stage
    assert failed_stage in result.stdout + result.stderr
    assert (root / "ignored/state").read_text() == "local state\n"
    if failed_stage in ("uv", "smoke_distribution"):
        assert not Path(observed[-1]["root"]).exists()
```

- [x] **Step 2: Run it.** `uv run pytest tests/test_check.py -q`. Expected: 3 failed, 2 passed. The first test and the `uv` and `smoke_distribution` cases fail with exit code 2: `scripts/check.py:49` still runs `python devctl setup`, and the stand-in checkout has no `devctl`.

- [x] **Step 3: Implement.** In `scripts/check.py`, replace lines 44-52 with:

```python
        # Build from a temporary copy of current source: ignored local state stays out
        # of the archives, and the checkout gains no dist/ directory.
        with tempfile.TemporaryDirectory(prefix="rapid-ship-check-") as temporary:
            source = Path(temporary).resolve()
            copy_source(root, source)
            run(source, "uv", "build")
            run(source, python, "scripts/smoke_distribution.py")
```

In `.github/AGENTS.md`, change the end of line 3 from "navigation, tests, static checks, installation smoke behavior and distributions." to "navigation, static checks, tests, a distribution build and the distribution smoke." Delete line 9 ("Keep install-smoke checks before distribution builds: …").

- [x] **Step 4: Run the checks.**

```sh
uv run pytest tests/test_check.py -q
uv run ruff check scripts/check.py tests/test_check.py
uv run ruff format --check scripts/check.py tests/test_check.py
uv run python scripts/check_repository.py
```

Expected: 5 passed; Ruff reports no findings and no files to reformat; `Repository navigation and skill aliases passed.`

- [x] **Step 5: Commit.**

```sh
git add scripts/check.py tests/test_check.py .github/AGENTS.md
git commit -m "refactor: drop controller install stages from validation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Replace the controller with a version-only rapid-ship CLI

**Files:**
- Delete, controller code: `rapid_ship/execution/`, `rapid_ship/trust/`, `rapid_ship/project/`, `rapid_ship/templates/`, `rapid_ship/models.py`, `rapid_ship/storage.py`, `rapid_ship/logs.py`, `rapid_ship/protocol_json.py`, `rapid_ship/metrics.py`, `rapid_ship/github_metrics.py`
- Delete, entry points and scripts: `devctl`, `scripts/build_controller.py`, `scripts/smoke_controller.py`
- Delete, examples: `examples/` (`AGENTS.md`, `environments.json`, `task-contract.json`)
- Delete, tests that import a deleted module or script: `tests/test_attempt_lifecycle.py`, `test_configuration.py`, `test_controller.py`, `test_controller_setup.py`, `test_environments.py`, `test_evidence.py`, `test_file_persistence.py`, `test_github.py`, `test_github_extended.py`, `test_github_metrics.py`, `test_interview_state.py`, `test_logs.py`, `test_metrics.py`, `test_models.py`, `test_onboarding.py`, `test_policy.py`, `test_profiles.py`, `test_project_wrapper.py`, `test_provider_evidence.py`, `test_provider_protocol_json.py` (imports `test_providers`), `test_provider_setup_integration.py`, `test_providers.py`, `test_runners.py`, `test_storage.py`, `test_trials.py`, all under `tests/`
- Delete, type fixtures: `tests/typecheck_effect_snapshots.py`, `tests/typecheck_task_snapshots.py`
- Replace: `rapid_ship/cli.py`, `tests/test_cli.py`, `scripts/smoke_distribution.py`
- Modify: `rapid_ship/__init__.py:1`, `pyproject.toml`, `uv.lock`, `.gitignore:17`, `tests/test_skill_discovery.py`, `tests/test_check.py`, `docs/environments.md:24`, `AGENTS.md:26`
- Rewrite guides: `rapid_ship/AGENTS.md`, `tests/AGENTS.md`, `scripts/AGENTS.md`

**Interfaces:**
- Produces:

```python
# rapid_ship/cli.py
def main(argv: Sequence[str] | None = None) -> int: ...
```

  `[project.scripts] rapid-ship = "rapid_ship.cli:main"`; `python -m rapid_ship` calls the same `main` through the unchanged `rapid_ship/__main__.py`. The index keeps this signature. Plan 2 adds `build_parser() -> argparse.ArgumentParser` and the `init`, `status` and `sync` commands, plan 4 adds `app` and plan 5 adds `adopt`.
- Kept unchanged for later plans: `rapid_ship.files.atomic_replace(path: Path, content: bytes) -> None` and `rapid_ship.process.run_process(argv: list[str], cwd: Path, timeout_seconds: float, env: dict[str, str] | None = None, input_text: str | None = None, cancel_event: threading.Event | None = None) -> ProcessResult`.

- [x] **Step 1: Write the failing test.** Overwrite `tests/test_cli.py`, which tested the old controller CLI, with:

```python
"""The version-only rapid-ship command, run through its entry point and as a module. Offline."""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
ENTRY_POINT = Path(sys.executable).parent / "rapid-ship"


@pytest.mark.parametrize("command", [[str(ENTRY_POINT)], [sys.executable, "-m", "rapid_ship"]])
def test_version_prints_name_and_project_version(tmp_path, command):
    result = subprocess.run(
        [*command, "--version"], cwd=tmp_path, capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"rapid-ship {VERSION}\n"
    assert result.stderr == ""


@pytest.mark.parametrize("arguments", [[], ["--unknown"]])
def test_anything_else_cannot_run(tmp_path, arguments):
    result = subprocess.run(
        [sys.executable, "-m", "rapid_ship", *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "usage: rapid-ship" in result.stderr
```

- [x] **Step 2: Run it.** `uv run pytest tests/test_cli.py -q`. Expected: 4 failed. `.venv/bin/rapid-ship` does not exist (`FileNotFoundError`); `python -m rapid_ship --version` prints `devctl 0.1.0` (`rapid_ship/cli.py:37`); the other two cases print `usage: devctl`.

- [x] **Step 3: Delete the controller.**

```sh
git rm -r -q rapid_ship/execution rapid_ship/trust rapid_ship/project rapid_ship/templates \
  rapid_ship/models.py rapid_ship/storage.py rapid_ship/logs.py rapid_ship/protocol_json.py \
  rapid_ship/metrics.py rapid_ship/github_metrics.py \
  devctl scripts/build_controller.py scripts/smoke_controller.py examples \
  tests/test_attempt_lifecycle.py tests/test_configuration.py tests/test_controller.py \
  tests/test_controller_setup.py tests/test_environments.py tests/test_evidence.py \
  tests/test_file_persistence.py tests/test_github.py tests/test_github_extended.py \
  tests/test_github_metrics.py tests/test_interview_state.py tests/test_logs.py \
  tests/test_metrics.py tests/test_models.py tests/test_onboarding.py tests/test_policy.py \
  tests/test_profiles.py tests/test_project_wrapper.py tests/test_provider_evidence.py \
  tests/test_provider_protocol_json.py tests/test_provider_setup_integration.py \
  tests/test_providers.py tests/test_runners.py tests/test_storage.py tests/test_trials.py \
  tests/typecheck_effect_snapshots.py tests/typecheck_task_snapshots.py
git clean -ndX -- rapid_ship tests scripts
git clean -fdX -- rapid_ship tests scripts
```

The preview lists only ignored caches such as `__pycache__/`. Removing them leaves no empty `rapid_ship/execution/` that Python could import as a namespace package.

- [x] **Step 4: Write the CLI.** Replace `rapid_ship/cli.py` with:

```python
"""Command-line entry point. This first version reports only its version."""

import argparse
from collections.abc import Sequence
from importlib.metadata import version


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rapid-ship")
    release = f"rapid-ship {version('rapid-ship')}"
    parser.add_argument("--version", action="version", version=release)
    parser.parse_args(argv)
    parser.error("no command given; this version supports only --version")
```

`parser.error` exits 2 with the usage line, which matches the index's "could not run". Replace `rapid_ship/__init__.py` line 1 with `"""The rapid-ship command. This version reports only its version."""`.

- [x] **Step 5: Update packaging.** In `pyproject.toml`:
  - line 11: `dependencies = []`;
  - lines 17-18: `[project.scripts]` with `rapid-ship = "rapid_ship.cli:main"`;
  - lines 26-27, the comment above `[tool.hatch.build.targets.sdist]`, become:

    ```toml
    # Build tools may resolve Git ignore rules from the primary checkout of a worktree.
    # Explicitly keep generated docs out of source archives; .gitignore keeps out the
    # state left by the removed controller.
    ```

  - line 34: delete `"/.controller", "/.controller-build-*", "/.controller-setup.lock",`;
  - line 52: `files = ["rapid_ship"]`.

  In `.gitignore`, insert above line 17 (`.controller/`) the comment `# Left in existing checkouts by the controller removed on 2026-10-14`. Keep lines 17-19.

  Then run:

```sh
uv lock
git diff --stat uv.lock
uv sync --locked
```

  Expected: `uv lock` reports `Removed annotated-types v0.8.0`, `Removed pydantic v2.14.0`, `Removed pydantic-core v2.50.0` and `Removed typing-inspection v0.4.4`, and nothing else. An offline dry run on a scratch copy on 2026-10-14 showed exactly these four. `uv sync --locked` succeeds, as CI's `uv sync --locked` must.

- [x] **Step 6: Replace the distribution smoke.** Replace `scripts/smoke_distribution.py` with:

```python
"""Install the wheel built from the source archive and check the rapid-ship entry point."""

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def built(root: Path, pattern: str) -> Path:
    matches = list((root / "dist").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected one dist/{pattern}; run uv build --clear first")
    return matches[0]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    built(root, "rapid_ship-*.tar.gz")
    # uv build makes the wheel from the source archive, so a file the archive omits
    # is missing from this installation too.
    wheel = built(root, "rapid_ship-*.whl")
    with tempfile.TemporaryDirectory(prefix="rapid-ship-distribution-") as temporary:
        environment = Path(temporary).resolve() / "venv"
        python = environment / "bin/python"
        subprocess.run(
            ["uv", "venv", "--quiet", "--python", sys.executable, str(environment)], check=True
        )
        subprocess.run(
            ["uv", "pip", "install", "--quiet", "--python", str(python), str(wheel)], check=True
        )
        result = subprocess.run(
            [str(environment / "bin/rapid-ship"), "--version"],
            cwd=temporary,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    if result.stdout != f"rapid-ship {version}\n":
        raise ValueError(f"Installed rapid-ship reported {result.stdout!r}, expected {version}")
    print(f"Installed wheel from the source archive reports rapid-ship {version}.")


if __name__ == "__main__":
    main()
```

  uv's documentation states that `uv build` "will first build a source distribution, and then build a binary distribution (wheel) from that source distribution", so installing the wheel also checks the archive.

- [x] **Step 7: Trim the remaining tests.**
  - `tests/test_skill_discovery.py`: delete lines 37-141, the seven tests that call `init_project`. Then delete line 8 (`from rapid_ship.project.configuration import init_project`) and line 2 (`from importlib.resources import files`). Keep `SKILLS` until Task 3.
  - `tests/test_check.py`: append the test below. It passes before and after this task; it pins the rule that removing the sdist excludes relies on.

```python
@pytest.mark.parametrize(
    "path", [".controller/bin/python", ".controller-build-1/wheel.whl", ".controller-setup.lock"]
)
def test_state_left_by_the_removed_controller_stays_ignored(path):
    # Existing checkouts still hold this state. Unignored, Ruff would lint a virtualenv,
    # check.py would copy it and uv build would pack it into the source archive.
    result = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", path], cwd=ROOT)

    assert result.returncode == 0
```

- [x] **Step 8: Fix links to deleted paths.**
  - `docs/environments.md:24`: change `[Examples](../examples/environments.json)` to `[Examples](https://github.com/proxy-hatch/rapid-ship/blob/archive/controller-2026-10/examples/environments.json)`. Without this, the site build fails on a link to a deleted file.
  - `AGENTS.md:26`: delete the row `| Sample task and environment contracts | [Examples](examples/AGENTS.md) |`. Task 4 rewrites the rest of this file.

- [x] **Step 9: Rewrite the three guides.** `rapid_ship/AGENTS.md`:

```markdown
# rapid_ship package

This root-level directory is the importable `rapid_ship` package behind the `rapid-ship` command. [pyproject.toml](../pyproject.toml) defines wheel selection and the `rapid-ship` entry point. The [plan index](../docs/superpowers/plans/2026-10-14-kit-and-setup.md) fixes the modules that later plans add here.

- [cli.py](cli.py) parses arguments. It supports only `--version`; plans 2, 4 and 5 add the commands. [__main__.py](__main__.py) and the entry point call the same `main`.
- [files.py](files.py) atomically replaces a file. Callers own serialization and path validation. It is kept from the removed controller for the Kit writers and has no caller yet.
- [process.py](process.py) runs a bounded subprocess under process-group supervision. It has no caller yet; plan 3 moves it into devctl and fixes the limits that Spec 1's borrow list names.
- [skills](skills/AGENTS.md) holds the engineering skill used while working on this repository.

Import modules directly; `__init__.py` is a marker, not an alternate interface. Keep resources under this package: `importlib.resources.files("rapid_ship")` is the lookup root in an installed wheel. After packaging changes, run the root checks and the [distribution smoke](../scripts/AGENTS.md).
```

  `tests/AGENTS.md`:

```markdown
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
```

  `scripts/AGENTS.md`:

```markdown
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
```

- [x] **Step 10: Run the checks.**

```sh
uv run ruff format rapid_ship tests scripts
uv run pytest -q
uv run mypy
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_repository.py
uv run rapid-ship --version
uv run python scripts/check.py
git grep -nE 'rapid_ship[./](execution|trust|project|templates|models|storage|logs|protocol_json|metrics|github_metrics)|pydantic|build_controller|smoke_controller|typecheck_|examples/' -- '*.py' '*.toml' '*.yml' '*.js' '*AGENTS.md' CLAUDE.md
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
```

  Expected: pytest passes with no collection errors and nothing skipped; mypy prints `Success: no issues found in 5 source files`; Ruff is clean; navigation passes; `rapid-ship 0.1.0`; `check.py` prints `Installed wheel from the source archive reports rapid-ship 0.1.0.` and then `Python and repository validation passed.`; `git grep` prints nothing; the site build ends with `[SUCCESS] Generated static files in "build".`

  `git ls-files rapid_ship tests scripts` now lists: `rapid_ship/AGENTS.md`, `__init__.py`, `__main__.py`, `cli.py`, `files.py`, `process.py`, the three skills under `rapid_ship/skills/`, `scripts/AGENTS.md`, `check.py`, `check_repository.py`, `smoke_distribution.py`, and `tests/AGENTS.md`, `test_check.py`, `test_cli.py`, `test_files.py`, `test_process.py`, `test_repository_navigation.py`, `test_skill_discovery.py`.

- [x] **Step 11: Commit.**

```sh
git add -A rapid_ship tests scripts pyproject.toml uv.lock .gitignore docs/environments.md AGENTS.md
git status --short   # devctl and examples/ show as deleted (staged by git rm); nothing is unstaged
git commit -m "refactor: replace the controller with a version-only rapid-ship CLI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Delete the controller skills

**Files:**
- Delete: `rapid_ship/skills/rapid-ship/` (`SKILL.md`, `references/run.md`, `references/setup.md`), `rapid_ship/skills/rapid-ship-improve/SKILL.md`, and the symlinks `.agents/skills/rapid-ship`, `.agents/skills/rapid-ship-improve`, `.claude/skills/rapid-ship`, `.claude/skills/rapid-ship-improve`
- Test: `tests/test_skill_discovery.py`
- Rewrite guides: `rapid_ship/skills/AGENTS.md`, `.agents/AGENTS.md`, `.claude/AGENTS.md`
- No change: `scripts/check_repository.py`. It derives the skill set from `rapid_ship/skills/*/SKILL.md` (`scripts/check_repository.py:183-189`) and names no skill.

**Interfaces:**
- Consumes: the alias rule in `scripts/check_repository.py:182-226`.
- Produces: one discovered skill, `rapid-ship-engineering`, on both surfaces. Plan 5 replaces it with the Kit skills.

- [x] **Step 1: Write the failing test.** Replace `tests/test_skill_discovery.py` with:

```python
"""Skill links and discovery aliases in this checkout. Offline."""

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
SKILLS = ("rapid-ship-engineering",)


def test_bundled_skill_dependencies_resolve_inside_package():
    package = REPOSITORY / "rapid_ship/skills"
    for document in package.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
            link = urlparse(target)
            if link.scheme or not link.path:
                continue
            dependency = (document.parent / unquote(link.path)).resolve()
            assert dependency.is_relative_to(package), (document, target)
            assert dependency.is_file(), (document, target)


@pytest.mark.parametrize("surface", [".agents", ".claude"])
@pytest.mark.parametrize("skill", SKILLS)
def test_checkout_discovery_resolves_to_packaged_skill(surface, skill):
    canonical = REPOSITORY / "rapid_ship/skills" / skill
    discovered = REPOSITORY / surface / "skills" / skill

    assert discovered.is_dir()
    assert discovered.samefile(canonical)
    assert (discovered / "SKILL.md").is_file()


@pytest.mark.parametrize("surface", [".agents", ".claude"])
def test_checkout_discovers_exactly_the_packaged_skills(surface):
    # A dangling or untracked alias still reaches agents, so list the directory itself.
    aliases = (REPOSITORY / surface / "skills").iterdir()
    discovered = {path.name for path in aliases if not path.name.startswith(".")}
    package = REPOSITORY / "rapid_ship/skills"
    packaged = {path.parent.name for path in package.glob("*/SKILL.md")}

    assert discovered == packaged == set(SKILLS)
```

- [x] **Step 2: Run it.** `uv run pytest tests/test_skill_discovery.py -q`. Expected: 2 failed, 3 passed. Both surfaces and the package still hold `rapid-ship`, `rapid-ship-engineering` and `rapid-ship-improve`.

- [x] **Step 3: Implement.**

```sh
git rm -r -q rapid_ship/skills/rapid-ship rapid_ship/skills/rapid-ship-improve \
  .agents/skills/rapid-ship .agents/skills/rapid-ship-improve \
  .claude/skills/rapid-ship .claude/skills/rapid-ship-improve
ls -A .agents/skills .claude/skills rapid_ship/skills
```

  Expected listing: `rapid-ship-engineering` under each surface, and `AGENTS.md` and `rapid-ship-engineering` under `rapid_ship/skills`.

  Replace `rapid_ship/skills/AGENTS.md` with:

```markdown
# Packaged skills

These files are the canonical skill sources. Checkout discovery paths under `.agents/skills` and `.claude/skills` are relative symlinks here.
Source archives include the canonical resources and omit those checkout aliases so the build cannot consume resources through a second path.

- [rapid-ship-engineering](rapid-ship-engineering/SKILL.md) routes implementation, review, architecture and writing guidance for agents working on this repository. Spec 1's Kit skills replace it.

Each skill's `SKILL.md` is the navigation entry for its references. Edit that source once; preserve local links, attribution and license files.

After resource edits, run `uv run pytest tests/test_skill_discovery.py` from the repository root. It checks local resource links and that both discovery surfaces hold exactly the packaged skills.
```

  Replace `.agents/AGENTS.md` with:

```markdown
# Repository skill discovery

`skills/` contains relative symlinks to the canonical packaged [skills](../rapid_ship/skills/).
Edit the canonical files; these aliases let coding agents discover the same reviewed content.
The [.claude](../.claude/AGENTS.md) surface points to that same source.

Before changing skill behavior or references, read the packaged [skills guide](../rapid_ship/skills/AGENTS.md).
Keep maintainer navigation outside individual skill bundles.
After changing discovery paths or bundled references, run `uv run pytest tests/test_skill_discovery.py` from the repository root.
```

  In `.claude/AGENTS.md`, change line 5 to "Edit canonical files so both agent discovery surfaces receive the same content."

- [x] **Step 4: Run the checks.**

```sh
uv run pytest tests/test_skill_discovery.py tests/test_repository_navigation.py -q
uv run python scripts/check_repository.py
uv run ruff check tests/test_skill_discovery.py
uv run ruff format --check tests/test_skill_discovery.py
```

  Expected: all pass; `Repository navigation and skill aliases passed.`

- [x] **Step 5: Commit.**

```sh
git add -A rapid_ship/skills .agents .claude tests/test_skill_discovery.py
git commit -m "refactor: remove the controller skills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Rewrite the root documents for the re-scope

**Files:**
- Rewrite: `AGENTS.md`, `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`
- Modify: `docs/usage.md:23`, `docs/superpowers/plans/2026-10-10-bootstrap.md:3`

**Interfaces:**
- Produces: the `ARCHITECTURE.md` heading "Develop rapid-ship" (anchor `#develop-rapid-ship`) and the root Commands that hold after this PR.

- [x] **Step 1: Write the failing check.**

```sh
grep -nE 'codex/|cannot qualify for unattended delivery|Metrics never grant authority|uv run devctl|/rapid-ship setup|rapid-ship-improve|uv sync --frozen' AGENTS.md CLAUDE.md README.md ARCHITECTURE.md
grep -c 'Metrics never grant Flight, and they end it automatically.' AGENTS.md
```

- [x] **Step 2: Run it.** Expected: the first command prints matches in `AGENTS.md` and `CLAUDE.md`; the second prints `0`.

- [x] **Step 3: Write the new files.** `AGENTS.md`:

````markdown
# rapid-ship

rapid-ship is being rebuilt as a Kit that a repository vendors: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and `rs-` skills. The `rapid-ship` command writes and updates the Kit; nothing runs as a service. The [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes the product, and [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) with its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) describes the work in progress. Today the package provides only `rapid-ship --version`.

## Commands

- Setup: `uv sync --locked`
- Full Python/repository validation (same as CI): `uv run python scripts/check.py`
- Navigation only: `uv run python scripts/check_repository.py`
- Tests: `uv run pytest`
- Static checks: `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`
- Build, then check the distribution: `uv build --clear`, then `uv run python scripts/smoke_distribution.py`
- CLI: `uv run rapid-ship --version`
- Documentation site: `npm --prefix website ci --no-audit --no-fund` once, then `npm --prefix website run build`

## Find the change

Read the directory guide before editing there; parent instructions still apply. Small resource and reference folders inherit their nearest guide.

| Work | Start here |
| --- | --- |
| The `rapid-ship` package and kept helpers | [Source map](rapid_ship/AGENTS.md) |
| Tests | [Tests](tests/AGENTS.md) |
| Validation and distribution checks | [Scripts](scripts/AGENTS.md) |
| Designs, plans, ADRs, trials and the archive | [Documentation](docs/AGENTS.md) |
| Documentation site and public images | [Website](website/AGENTS.md), [assets](asset/AGENTS.md) |
| CI and documentation deployment | [Workflows](.github/AGENTS.md) |
| Agent skill discovery | [Codex discovery](.agents/AGENTS.md), [Claude discovery](.claude/AGENTS.md) |

When adding or moving a maintained directory, update its guide and parent navigation in the same change. Keep one canonical implementation and point to it. Build output, caches, worktrees and state left by the removed controller are generated, not source directories to document.

## Writing

Read `.agents/skills/rapid-ship-engineering/references/writing.md` before writing commits, PRs, documentation or agent reports. Use the terms in [GLOSSARY.md](GLOSSARY.md), and read the [ADRs](docs/adr/) before reopening a settled decision.

Lead with the outcome or problem. Prefer one precise finding over several vague ones; name the problem, consequence and file:line. Comments explain non-obvious behaviour, not the code. Keep exact commands, limits and safety conditions.

## Development

- Before coding or review, read `.agents/skills/rapid-ship-engineering/references/ponytail.md`. Use the engineering skill for clarification, TDD, debugging, architecture work and review.
- Build what the current plan names. Write the test first, and keep each task small enough to check on its own.
- Work on a branch and merge through a PR after independent review. Do not use the `rs/` prefix: Spec 1's `devctl dispatch` counts `rs/` branches as Worker claims.
- Turn a repeated correction into the strongest rule that can carry it: a safe interface, then a check, then a skill or advisory Rule.
- Linear holds specs and tasks; GitHub holds code, checks and PRs. Do not mirror tasks into GitHub Issues. Connect Linear through its official MCP or API, never a third-party CLI.
- Agents sign in with their vendor's subscription, never an API key or a proxy. Use the chosen model exactly as named; if it is unavailable, stop instead of falling back.
- Missing metrics are unknown, not zero, and block promotion. Metrics never grant Flight, and they end it automatically.

## Safety

- Label offline and simulated tests. A blocked, skipped or simulated check never counts as passed; missing credentials block the step.
- A review applies to one head commit. A Worker's own report is not independent verification.
- Record an external operation before sending it. Resolve an uncertain result before retrying.
- Worktrees isolate source only, not processes, credentials or ports.
- No silent increase in permissions, model fallback or automatic approval.
- Never write a GitHub App private key or token to disk, a command line or output.
````

  `CLAUDE.md` becomes the single line `@AGENTS.md`.

  `README.md`:

````markdown
![rapid-ship — Ship more. Supervise less.](asset/public/banner.jpeg)

[![CI](https://github.com/proxy-hatch/rapid-ship/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/proxy-hatch/rapid-ship/actions/workflows/ci.yml)

**Hand more of your delivery to coding agents, and keep the evidence that the work is right.**

rapid-ship installs a Kit into your repository: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and a set of skills. GitHub decides what merges and Linear holds the tasks. You start in Walk, where you approve every agent PR. Flight lets agents merge ordinary changes, and only while measured quality holds.

## Status

rapid-ship is being rebuilt, and nothing is usable yet: the package provides only `rapid-ship --version`. The earlier version, a local controller also named devctl, was removed on 2026-10-14. Its code is kept at the git tag [`archive/controller-2026-10`](https://github.com/proxy-hatch/rapid-ship/tree/archive/controller-2026-10), and its guides remain on this site, marked historical.

## Read more

- [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md): the problem, the path from Setup to Flight, and how trust is enforced.
- [Spec 1: Kit and Setup](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md): what is built first, in [five plans](docs/superpowers/plans/2026-10-14-kit-and-setup.md).
- [Architecture](ARCHITECTURE.md): what this repository holds today and how to develop it.

## Credits

Our engineering workflows adapt [Matt Pocock's skills](https://github.com/mattpocock/skills/), with [Ponytail](https://github.com/DietrichGebert/ponytail) by Dietrich Gebert. Thank you for sharing them. [Skill sources and credits](docs/credits.md).
````

  `ARCHITECTURE.md` (the paragraph about pinned dependencies is the current `ARCHITECTURE.md:113`, unchanged):

````markdown
# Architecture

rapid-ship is being rebuilt as a Kit that projects vendor into their repositories; the [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes it. This page describes what the repository holds today and how to work on it.

## What exists today

| Part | Where | Status |
| --- | --- | --- |
| `rapid-ship` CLI | `rapid_ship/cli.py` | Prints its version only. Plan 2 adds `init`, `status` and `sync` |
| Atomic file replacement | `rapid_ship/files.py` | Kept for the Kit writers; no caller yet |
| Bounded process runner | `rapid_ship/process.py` | Kept for devctl's check steps; plan 3 moves it into devctl |
| Engineering skill | `rapid_ship/skills/rapid-ship-engineering/` | Guides agents working on this repository until the Kit skills replace it |
| Repository checks | `scripts/` | Navigation and skill aliases, lint, format, types, tests, build and distribution smoke |
| Documentation site | `website/` | Builds the Markdown in this repository; rewritten once the product works |

devctl, the Kit templates, the GitHub Apps and the `rs-` skills do not exist yet. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) builds them in the order its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) sets.

## What was removed

The earlier controller, a local orchestrator also named devctl, was removed on 2026-10-14. Its last version is the git tag `archive/controller-2026-10`. Later plans retrieve the parts in Spec 1's borrow list with `git show archive/controller-2026-10:<path>`. Its runtime trials and designs are in the [archive](docs/archive/orchestrator/README.md). The guides under `docs/` that describe it start with a "Historical" line.

## Develop rapid-ship

```sh
uv sync --locked
uv run python scripts/check.py
```

`scripts/check.py` runs, in order: the navigation check (local Markdown links in maintained `AGENTS.md` files, and skill aliases), Ruff lint and format, mypy and pytest in the checkout, then `uv build` and the distribution smoke in a temporary copy of current source. The smoke installs the wheel that `uv build` made from the source archive into a fresh environment and checks `rapid-ship --version`. For navigation alone, run `uv run python scripts/check_repository.py`. CI runs the same command on Python 3.12 and 3.13.

## Documentation site

The site reads this file, the README and the Markdown under `docs/` directly, excluding maintainer `AGENTS.md` files. Public images come from `asset/public/`. To preview it, use Node.js 22+ (CI uses 24):

```sh
npm --prefix website ci
npm --prefix website start
# Production build, including internal link and anchor checks:
npm --prefix website run build
```

The site pins four patched transitive dependencies while upstream catches up. As of 2026-10-11, the remaining [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) has no published fix; it concerns deeply nested build patterns. Pages serves static output, without a Node server. Recheck `npm audit` when updating the lockfile.

The docs workflow builds PRs and deploys successful `main` builds to GitHub Pages. Repository Pages settings must use GitHub Actions.
````

- [x] **Step 4: Check the anchors.** Run `npm --prefix website run build`. Expected: it fails on the anchors `#project-setup` (from `docs/usage.md`) and `#develop-the-framework` (from the bootstrap plan), because `onBrokenAnchors` is `'throw'` (`website/docusaurus.config.js:15`). If it passes, the site did not check these anchors; fix the links anyway, since the headings no longer exist. Then:
  - `docs/usage.md:23`: change `(../ARCHITECTURE.md#project-setup)` to `(https://github.com/proxy-hatch/rapid-ship/blob/archive/controller-2026-10/ARCHITECTURE.md#project-setup)`. The historical guide keeps pointing at the architecture it describes.
  - `docs/superpowers/plans/2026-10-10-bootstrap.md:3`: change `#develop-the-framework` to `#develop-rapid-ship`.

- [x] **Step 5: Run the checks.**

```sh
grep -nE 'codex/|cannot qualify for unattended delivery|Metrics never grant authority|uv run devctl|/rapid-ship setup|rapid-ship-improve|uv sync --frozen' AGENTS.md CLAUDE.md README.md ARCHITECTURE.md
grep -c 'Metrics never grant Flight, and they end it automatically.' AGENTS.md
uv run python scripts/check_repository.py
npm --prefix website run build
```

  Expected: no output from the first command; `1`; navigation passes; the site build succeeds.

- [x] **Step 6: Commit.**

```sh
git add AGENTS.md CLAUDE.md README.md ARCHITECTURE.md docs/usage.md docs/superpowers/plans/2026-10-10-bootstrap.md
git commit -m "docs: rewrite root documents for the re-scope" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Archive the controller-era records

**Files:**
- Move to `docs/archive/orchestrator/`: `docs/runtime-choice.md`, `docs/session-handoffs.md`, `docs/environments.md`, `docs/authority.md`
- Move to `docs/archive/orchestrator/trials/`: `docs/trials/astrabox-report.md`, `docs/trials/lightdag-report.md`, `docs/trials/2026-10-11-runtime-comparison.md`, `docs/trials/astrabox-trial-2026-10-11.tar.gz`, `docs/trials/lightdag-trial-2026-10-11.tar.gz`
- Modify: `docs/archive/orchestrator/authority.md:13` (after the move), `docs/usage.md:47,95`, `docs/getting-started.md:383`, `docs/bootstrap-validation.md:15,64,82`, `docs/model-harnesses.md:7,36`, `website/sidebars.js:17,20,22,23`, `docs/AGENTS.md:9-10`, `docs/archive/orchestrator/README.md:114,126,153-159`
- Rewrite guides: `docs/trials/AGENTS.md`, `docs/archive/AGENTS.md`

**Interfaces:**
- Produces: the archived pages at `docs/archive/orchestrator/{runtime-choice,session-handoffs,environments,authority}.md` and `docs/archive/orchestrator/trials/`. Their relative layout is unchanged, so links among them, including both tarball links, still resolve.

- [x] **Step 1: Produce the failing state.** Move the files:

```sh
mkdir -p docs/archive/orchestrator/trials
git mv docs/runtime-choice.md docs/session-handoffs.md docs/environments.md docs/authority.md docs/archive/orchestrator/
git mv docs/trials/astrabox-report.md docs/trials/lightdag-report.md docs/trials/2026-10-11-runtime-comparison.md \
  docs/trials/astrabox-trial-2026-10-11.tar.gz docs/trials/lightdag-trial-2026-10-11.tar.gz docs/archive/orchestrator/trials/
```

- [x] **Step 2: Run the checks.**

```sh
uv run python scripts/check_repository.py
git grep -nE '\]\((\.\./)*(docs/)?(trials/)?(runtime-choice|session-handoffs|environments|authority|astrabox-report|lightdag-report|2026-10-11-runtime-comparison)\.md' -- ':!docs/archive' ':!docs/superpowers'
npm --prefix website run build
```

  Expected: navigation fails on `docs/AGENTS.md:9` and `docs/trials/AGENTS.md:4` and `:5`; `git grep` lists `docs/usage.md:47,95`, `docs/getting-started.md:383`, `docs/bootstrap-validation.md:15,64,82`, `docs/model-harnesses.md:7,36`, `docs/AGENTS.md:9` and `docs/trials/AGENTS.md:4,5`; the site build fails, first on the sidebar IDs that no longer exist.

- [x] **Step 3: Fix the links.**
  - Incoming: in `docs/usage.md`, `docs/getting-started.md`, `docs/bootstrap-validation.md` and `docs/model-harnesses.md`, prefix each listed link target with `archive/orchestrator/`. For example, `(environments.md)` becomes `(archive/orchestrator/environments.md)` and `(trials/2026-10-11-runtime-comparison.md)` becomes `(archive/orchestrator/trials/2026-10-11-runtime-comparison.md)`.
  - Outgoing: in `docs/archive/orchestrator/authority.md:13`, change `(metrics.md)` to `(../../metrics.md)`. The link in `environments.md` already points at the tag (Task 2).
  - `website/sidebars.js`: delete the entries `'docs/environments'`, `'docs/authority'`, `'docs/session-handoffs'` and `'docs/runtime-choice'`.
  - `docs/AGENTS.md`: replace line 10 with the line below, then delete line 9 (the `runtime-choice.md` bullet).

    ```markdown
    - Deferred or abandoned work lives in [archive](archive/AGENTS.md), including the controller-era runtime trials and designs. It does not describe current behaviour.
    ```

  - `docs/archive/orchestrator/README.md:114`: replace "at commit `f7b877b`. That commit is tagged `archive/controller-2026-10` when the old controller is removed." with "at the tag `archive/controller-2026-10`." Line 126: replace "at commit `f7b877b`." with "at the tag `archive/controller-2026-10`." Task 7 checks that these line ranges are the same at the tagged commit.
  - Replace lines 153-159 ("Older records") of the same file with:

```markdown
## Older records

These describe the direction that came before. They moved here when the old controller was removed on 2026-10-14, keeping their relative layout. The controller's code is at the git tag `archive/controller-2026-10`.

- [Runtime choice](runtime-choice.md): the earlier choice of AstraBox.
- [Runtime comparison](trials/2026-10-11-runtime-comparison.md), with the [AstraBox report](trials/astrabox-report.md) and the [LightDAG report](trials/lightdag-report.md): the earlier runtime trials. The comparison links both frozen bundles and their checksums.
- [Session handoffs](session-handoffs.md), [environments](environments.md) and [delivery permissions](authority.md): designs for the old controller.
```

  `docs/trials/AGENTS.md`:

```markdown
# Trial evidence

This directory records observations and reproduction artifacts, including unsuccessful probes.
The controller-era runtime trials and their frozen bundles moved to the [archive](../archive/orchestrator/trials/2026-10-11-runtime-comparison.md).

Record the tested versions, conditions, commands, results, and limits for each trial.
Identify deterministic simulations, live provider calls, and later reruns separately.
Preserve the relationship between each report, its saved artifacts, and the revision actually tested.
When replacing an artifact, update its recorded checksum and explain which observations the replacement reproduces.
Check bundles for credentials and private paths before publication; the website publishes these reports.
Passing unit tests or one successful probe does not qualify a project for Flight.
```

  `docs/archive/AGENTS.md`:

```markdown
# Archive

This directory holds records of deferred or abandoned work. Nothing here describes current behaviour.

- Read [orchestrator](orchestrator/README.md) only when resuming rapid-orchestrator, or when an ADR that defers it is being reconsidered. Its "Older records" section lists the runtime trials and controller designs moved here when the controller was removed; the controller's code is at the git tag `archive/controller-2026-10`.
- Do not copy designs or code from here into current work. Check the ADRs in [adr](../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md) first. The exception is the borrow list in [Spec 1](../superpowers/specs/2026-10-14-kit-and-setup-design.md), retrieved from the tag.
- When a decision defers a body of work, move its documents here with one README that states the status, the decisions, the evidence, and how to resume. Keep their relative layout so links between them still resolve.
```

- [x] **Step 4: Run the checks.**

```sh
uv run python scripts/check_repository.py
git grep -nE '\]\((\.\./)*(docs/)?(trials/)?(runtime-choice|session-handoffs|environments|authority|astrabox-report|lightdag-report|2026-10-11-runtime-comparison)\.md' -- ':!docs/archive' ':!docs/superpowers'
grep -nE "docs/(environments|authority|session-handoffs|runtime-choice)'" website/sidebars.js
shasum -a 256 docs/archive/orchestrator/trials/*.tar.gz
npm --prefix website run build
```

  Expected: navigation passes; both greps print nothing; the checksums are `1446e60efa37fd03b71f4110e3217b4f4d89827272fa27fe65f70de6334d905f` (AstraBox) and `355179ecbc7c18ce3114db265910aaa2e07be323d1217b48212ba528da37811b` (LightDAG), as `2026-10-11-runtime-comparison.md:71-72` records; the site build succeeds.

- [x] **Step 5: Commit.**

```sh
git add -A docs website/sidebars.js
git commit -m "docs: archive controller-era runtime records" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Mark the remaining controller guides historical

**Files:**
- Modify: `docs/getting-started.md` (below the title on line 9), and line 3 of `docs/usage.md`, `docs/task-slicing.md`, `docs/model-harnesses.md`, `docs/linear.md`, `docs/metrics.md`, `docs/engineering-skills.md`, `docs/improving-rapid-ship.md`, `docs/bootstrap-validation.md`
- Modify: `docs/AGENTS.md:5`

**Interfaces:** none. The site keeps each page title because the line goes below the `#` title, not above it.

- [x] **Step 1: Write the failing check.**

```sh
grep -n '^> \*\*Historical:\*\* describes the controller removed on 2026-10-14\.' docs/getting-started.md docs/usage.md docs/task-slicing.md docs/model-harnesses.md docs/linear.md docs/metrics.md docs/engineering-skills.md docs/improving-rapid-ship.md docs/bootstrap-validation.md
```

- [x] **Step 2: Run it.** Expected: no output, exit status 1.

- [x] **Step 3: Implement.** In each of the nine files, insert the banner from the Global Constraints, followed by one blank line, directly after the blank line that follows the `#` title. In `docs/getting-started.md` the title is line 9, after the MDX front matter and imports, so the banner becomes line 11; in the other eight it becomes line 3. In `docs/AGENTS.md`, replace line 5 with:

```markdown
- The nine controller-era guides at this level, such as [getting-started.md](getting-started.md) and [usage.md](usage.md), describe the controller removed on 2026-10-14 and start with a "Historical" line. Do not extend them; the documentation site is rewritten once the product works. [credits.md](credits.md) and [branding.md](branding.md) are current pages; update them as needed.
```

- [x] **Step 4: Run the checks.** Rerun the Step 1 command, then `uv run python scripts/check_repository.py` and `npm --prefix website run build`. Expected: nine matches, `docs/getting-started.md:11` and line `3` in the other eight; navigation passes; the site build succeeds.

- [x] **Step 5: Commit.**

```sh
git add docs/getting-started.md docs/usage.md docs/task-slicing.md docs/model-harnesses.md docs/linear.md docs/metrics.md docs/engineering-skills.md docs/improving-rapid-ship.md docs/bootstrap-validation.md docs/AGENTS.md
git commit -m "docs: mark the controller guides historical" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: Verify the plan, tag the controller and open the PR

**Files:**
- Modify: this plan's "Verification record"

- [x] **Step 1: Bring the branch up to date.** `git fetch origin && git merge --no-edit origin/main`. If `main` moved, resolve any conflict; Step 2 then verifies the merged result.

- [x] **Step 2: Run the full verification.**

```sh
uv sync --locked
uv run python scripts/check.py
uv run rapid-ship --version
git ls-files rapid_ship tests scripts | grep -v '^rapid_ship/skills/rapid-ship-engineering/'
git ls-files rapid_ship/skills/rapid-ship-engineering | wc -l
git ls-files devctl examples rapid_ship/templates rapid_ship/execution rapid_ship/trust rapid_ship/project scripts/build_controller.py scripts/smoke_controller.py
git grep -nE 'rapid_ship[./](execution|trust|project|templates|models|storage|logs|protocol_json|metrics|github_metrics)|pydantic|build_controller|smoke_controller|typecheck_|examples/' -- '*.py' '*.toml' '*.yml' '*.js' '*AGENTS.md' CLAUDE.md README.md ARCHITECTURE.md
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
```

  Expected:
  - `check.py` ends with `Python and repository validation passed.`
  - `rapid-ship 0.1.0`.
  - The file listing is exactly: `rapid_ship/AGENTS.md`, `rapid_ship/__init__.py`, `rapid_ship/__main__.py`, `rapid_ship/cli.py`, `rapid_ship/files.py`, `rapid_ship/process.py`, `rapid_ship/skills/AGENTS.md`, `scripts/AGENTS.md`, `scripts/check.py`, `scripts/check_repository.py`, `scripts/smoke_distribution.py`, `tests/AGENTS.md`, `tests/test_check.py`, `tests/test_cli.py`, `tests/test_files.py`, `tests/test_process.py`, `tests/test_repository_navigation.py`, `tests/test_skill_discovery.py`.
  - The engineering skill keeps its 18 files.
  - The deleted-path listing and `git grep` print nothing.
  - The site build ends with `[SUCCESS] Generated static files in "build".`

- [x] **Step 3: Check every changed directory's guide.** Run `git diff --name-only origin/main...HEAD | xargs -n1 dirname | sort -u`. Each directory must be covered by a guide this plan updated: root (Tasks 2, 4), `.agents` and `.claude` (Task 3), `.github` (Task 1), `docs` (Tasks 5, 6), `docs/archive` and below (Task 5), `docs/trials` (Task 5), `rapid_ship` (Task 2), `rapid_ship/skills` (Task 3), `scripts` and `tests` (Task 2). Two guides stay as they are; confirm they are still accurate: `website/AGENTS.md` (only `sidebars.js` changed) and `docs/superpowers/AGENTS.md` (only one link in the bootstrap plan changed). Deleted directories (`examples`, `rapid_ship/execution`, `rapid_ship/trust`, `rapid_ship/project`, `rapid_ship/templates` and the two skills) need no guide. Any other directory needs its guide updated before continuing.

- [x] **Step 4: Record the local results** from Steps 2 and 3 in the "Verification record" below, then commit:

```sh
git add docs/superpowers/plans/2026-10-14-remove-controller.md
git commit -m "docs: record verification for controller removal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [x] **Step 5: Owner step: tag the last commit that contains the controller.** The owner confirms that nothing else merges into `main` until this PR merges, then runs:

```sh
git fetch origin
git merge-base --is-ancestor origin/main HEAD && echo "branch contains main"
git cat-file -e origin/main:rapid_ship/execution/controller.py && echo "main still has the controller"
git diff --quiet f7b877b origin/main -- rapid_ship scripts tests && echo "controller code unchanged since f7b877b"
```

  Expected: all three confirmations. Stop if either of the first two is missing. Today `origin/main` is `f7b877b`; once the design PR has merged, it is that merge commit. If the third confirmation is missing, controller code changed after `f7b877b`: recheck the line ranges cited in `docs/archive/orchestrator/README.md:114,126` and in the spec's borrow list against `origin/main`, and fix any that moved before tagging. Then:

```sh
git tag -a archive/controller-2026-10 origin/main -m "Last commit containing the old controller"
git push origin archive/controller-2026-10
gh api 'repos/proxy-hatch/rapid-ship/contents/examples/environments.json?ref=archive/controller-2026-10' --jq .name
```

  Expected: `environments.json`, read from the pushed tag. The owner confirms the tag points at this PR's base commit.

- [x] **Step 6: Write the PR body, then owner step: open the PR.** The body follows the index's PR body format. Every test at the base is a top-level `def test_` function (checked at `f7b877b` on 2026-10-14), so `git grep` gives each removed test's `<path>::<name>`:

```sh
base=$(git merge-base origin/main HEAD)
git grep -E '^def test_' "$base" -- 'tests/test_*.py' | sed -E 's/^[^:]+:([^:]+):def (test_[A-Za-z0-9_]+).*/\1::\2/' | sort -u > /tmp/remove-controller-base-tests.txt
git grep -E '^def test_' HEAD -- 'tests/test_*.py' | sed -E 's/^[^:]+:([^:]+):def (test_[A-Za-z0-9_]+).*/\1::\2/' | sort -u > /tmp/remove-controller-head-tests.txt
comm -23 /tmp/remove-controller-base-tests.txt /tmp/remove-controller-head-tests.txt | sed 's/.*/- `&`: tests of the deleted controller/' > /tmp/remove-controller-removed-tests.md
wc -l < /tmp/remove-controller-removed-tests.md
```

  Expected: `401`, counted at `f7b877b`. That is 376 tests from the 25 files deleted in Task 2, 17 replaced in `tests/test_cli.py`, the 7 `init_project` tests from `tests/test_skill_discovery.py`, and `tests/test_check.py::test_validation_uses_current_source_and_preserves_installed_controller`, replaced in Task 1. A different count means `main` changed `tests/` after `f7b877b`; check each differing line against Tasks 1–3 before continuing.

  Write `/tmp/remove-controller-pr.md`:
  1. A summary of the change. It also names the two deleted mypy fixtures, `tests/typecheck_effect_snapshots.py` and `tests/typecheck_task_snapshots.py`; they hold no pytest tests, so they are not `Removed tests:` entries.
  2. `## Evidence`, with one `` - `<command>`: <its result> `` item for each Step 2 command.
  3. Inside that section, `Removed tests:` followed by the lines of `/tmp/remove-controller-removed-tests.md`.
  4. The line `Not covered: No live GitHub or Linear behaviour; this PR changes none.`

  The owner then pushes `codex/remove-controller` and runs `gh pr create --body-file /tmp/remove-controller-pr.md` under their own login. The owner merges once CI and the Docs workflow pass, the tag exists and Step 7 is pushed.

- [x] **Step 7: Record the PR body, tag and hosted results.** Fill the last three lines of the record, then run `git add docs/superpowers/plans/2026-10-14-remove-controller.md` and `git commit -m "docs: record hosted checks for controller removal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"` and ask the owner to push it to the PR branch.

## Verification record

The executor fills this in with observed output only. A skipped or blocked check is recorded as such, never as passed.

- Starting point (`main` commit, design PR present): Local design commit `55fc5df` ("docs: re-scope rapid-ship around a Kit, Walk and Flight") on `codex/remove-controller`. The branch starts there because the design PR is not opened and this commit holds its content. `origin/main` is `f7b877b` and still contains the controller. Step 1, `git fetch origin` then `git merge --no-edit origin/main`, printed `Already up to date.` Baseline at `55fc5df`, run in a scratch clone during the final review: `uv run python scripts/check.py` passed (902 tests, mypy `no issues found in 31 source files`, `Python and repository validation passed.`) and `npm --prefix website run build` passed (`[SUCCESS] Generated static files in "build".`).
- Task 1 red and green (`tests/test_check.py`): Red, `uv run pytest tests/test_check.py -q` before the change: `3 failed, 2 passed`; each failure exited 2 on `can't open file '.../devctl'`. Green, same command after: `5 passed`. These tests are offline and simulated; the real run is the `check.py` line below.
- Task 2 red and green (`tests/test_cli.py`), `uv lock` removals, mypy file count, `git grep` result: Red, `uv run pytest tests/test_cli.py -q` before any production change: `4 failed` (no `rapid-ship` entry point, `devctl 0.1.0` printed instead of `rapid-ship 0.1.0`, usage text `usage: devctl`). Green, `uv run pytest -q`: `71 passed`. `uv lock` removed only `annotated-types v0.8.0`, `pydantic v2.14.0`, `pydantic-core v2.50.0` and `typing-inspection v0.4.4`. `uv run mypy`: `Success: no issues found in 5 source files`. The stale-reference `git grep` printed nothing. `test_state_left_by_the_removed_controller_stays_ignored` passed before and after the change; it guards the `pyproject.toml` edit and is not red and green evidence.
- Task 3 red and green (`tests/test_skill_discovery.py`): Red, `uv run pytest tests/test_skill_discovery.py -q` before deleting: `2 failed, 3 passed`; `.agents` and `.claude` each still held `rapid-ship` and `rapid-ship-improve`. Green, `uv run pytest tests/test_skill_discovery.py tests/test_repository_navigation.py -q`: `35 passed`.
- Task 4 stale-rule grep and anchor build result: Before the rewrite the stale-rule `grep` matched `CLAUDE.md:3` and `AGENTS.md:7,14,46,48,55`, and the `grep -c` printed `0`. After it, the `grep` printed nothing and `grep -c` printed `1`; Task 7 re-ran both with the same result. The site build before the two link fixes failed on exactly `#develop-the-framework` (bootstrap plan) and `#project-setup` (`docs/usage.md`); after them it ended with `[SUCCESS] Generated static files in "build".`
- Task 5 navigation, old-path grep, checksums and site build: Before the link fixes, navigation failed on `docs/AGENTS.md:9` and `docs/trials/AGENTS.md:4,5`, the old-path `git grep` listed the expected links, and the site build failed on the removed sidebar IDs. After them, navigation passed, the old-path `git grep` and the sidebar `grep` printed nothing, and the site build passed. SHA256 `1446e60efa37fd03b71f4110e3217b4f4d89827272fa27fe65f70de6334d905f` (AstraBox) and `355179ecbc7c18ce3114db265910aaa2e07be323d1217b48212ba528da37811b` (LightDAG) equal `docs/archive/orchestrator/trials/2026-10-11-runtime-comparison.md:71-72`. Task 7 re-ran the two greps and the checksums with the same result.
- Task 6 banner grep: Before the edit the nine-file `grep` printed nothing (exit 1). After it, nine matches: `docs/getting-started.md:11` and line 3 of the other eight. Task 7 re-ran it with the same nine matches.
- `uv run python scripts/check.py` on the final head: Passed at `9667791`, the head before the record commit, which changes only this plan: 69 passed, `uv build` built the sdist and wheel, `Installed wheel from the source archive reports rapid-ship 0.1.0.`, then `Python and repository validation passed.` Also at `9667791`: `uv sync --locked` resolved 13 packages and checked 12; `uv run rapid-ship --version` printed `rapid-ship 0.1.0`; the 18-file listing, the engineering skill's 18 files, the empty deleted-path listing and the empty `git grep` all matched Step 2; `git diff --exit-code 55fc5df -- rapid_ship/files.py rapid_ship/process.py tests/test_files.py tests/test_process.py` exited 0.
- `npm --prefix website ci --no-audit --no-fund` and `npm --prefix website run build`: `ci` added 1259 packages and exited 0, with npm `allow-scripts` warnings for `core-js` and `fsevents` only. `build` compiled Server and Client and ended with `[SUCCESS] Generated static files in "build".`
- Changed directories and their guides: Step 3 ran as `git diff --name-only 55fc5df...HEAD | xargs -n1 dirname | sort -u` (the design commit is the base, because `origin/main` lacks the design; against `origin/main` it also lists `docs/adr`, `docs/archive/orchestrator/login-carry-spike`, `docs/superpowers` and `docs/superpowers/specs`, which belong to the design commit). Each directory that still exists is covered by a guide this plan updated: `.` (`AGENTS.md`, Tasks 2, 4); `.agents` and `.agents/skills` (`.agents/AGENTS.md`, Task 3); `.claude` and `.claude/skills` (`.claude/AGENTS.md`, Task 3); `.github` (Task 1); `docs` (Tasks 5, 6); `docs/archive`, `docs/archive/orchestrator` and `docs/archive/orchestrator/trials` (`docs/archive/AGENTS.md`, Task 5); `docs/trials` (Task 5); `rapid_ship` (Task 2); `rapid_ship/skills` (Task 3); `scripts` and `tests` (Task 2). Deleted directories need no guide: `examples`, `rapid_ship/execution`, `rapid_ship/project`, `rapid_ship/templates`, `rapid_ship/trust`, `rapid_ship/skills/rapid-ship`, `rapid_ship/skills/rapid-ship/references` and `rapid_ship/skills/rapid-ship-improve`. `website/AGENTS.md` is still accurate: only `website/sidebars.js` changed, by removing four sidebar entries. `docs/superpowers/AGENTS.md` is still accurate: `docs/superpowers/plans` changed only by one anchor link in the bootstrap plan.
- Removed-test count in the PR body (Task 7 Step 6): `401`, as expected, counted against merge base `f7b877b` (432 test names at the base, 36 at the head). The body is `.superpowers/sdd/2026-10-14-remove-controller/remove-controller-pr.md` (git-ignored): a summary that names the two mypy fixtures, `## Evidence` with one item per Step 2 command, `Removed tests:` with 401 lines and the `Not covered:` line.
- Tag `archive/controller-2026-10` commit and push result: Done on 2026-10-15 with the owner's approval. The three confirmations held at `origin/main` `f7b877b`. Then `archive/controller-2026-10` was created at `origin/main` `f7b877b` and pushed. `gh api 'repos/proxy-hatch/rapid-ship/contents/examples/environments.json?ref=archive/controller-2026-10' --jq .name` printed `environments.json`. Observed read-only when this line was written: `git ls-remote --tags origin 'archive/*'` lists the annotated tag `af5f281`, which peels to `f7b877b`, tagged `2026-10-15T04:11:12Z`. GitHub's `main` is still `f7b877b`.
- Hosted CI (Python 3.12 and 3.13) and Docs workflow on the PR: PR proxy-hatch/rapid-ship#28, `refactor: remove the old controller`, opened 2026-10-15 against `claude/trust-first-agentic-playbook-ba4700`. Its body has the 401 `Removed tests:` entries. At `e035ea9`, CI `checks (3.12)` and `checks (3.13)` passed in both the `push` and the `pull_request` run, and the Docs `build` passed. The Docs `deploy` job was skipped; it runs only on pushes to `main`. `gh pr checks 28 --repo proxy-hatch/rapid-ship` exited 0. These results apply to `e035ea9` only. The merge of the design branch and this record commit get their own hosted runs when the owner pushes them.
