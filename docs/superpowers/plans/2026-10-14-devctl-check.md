# `devctl check` implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `devctl check`, the one entry point that the pre-commit hook and CI run, with every step in spec section 5. Ship its CI workflow and hook in the Kit, and switch this repository from `scripts/check.py` to `./devctl check`.

**Architecture:** `devctl/check/` holds one module per rule family. Each exposes a step object that returns a `StepResult`; `run_check` runs one tier's steps in the spec's order, and the CLI maps the results to exit codes 0, 1 and 2. Python knowledge (tools, test identities, suppressions) lives in `stacks/python.py` and stack-neutral tools in `stacks/neutral.py`. devctl is edited only under `rapid_ship/templates/common/tools/devctl/` and vendored into `tools/devctl/` with `uv run rapid-ship sync --in-place`.

**Tech Stack:** Python 3.12+ standard library (argparse, tomllib, ast, tokenize), PyYAML 6.0.3, uv; ruff, mypy, pytest and import-linter from the project's lock; pip-audit 2.10.1 and zizmor 1.30.1 through `uv tool run`; gitleaks 8.30.1; GitHub Actions.

**Spec:** [Spec 1](../specs/2026-10-14-kit-and-setup-design.md), section 5 in full and, from section 4, the CI workflow and the pre-commit hook. Plan 3 of 5 in the [plan index](2026-10-14-kit-and-setup.md), which fixes the layout and the shared interfaces.

## Global Constraints

- Exit codes: 0 when every applicable step passed, 1 when a step failed, 2 when a step could not run. When both 1 and 2 apply, 2 wins. A blocked step never counts as passed.
- Steps, tiers and order follow spec section 5: fast is format, lint, map, exceptions, file-size, kit; full adds types, contracts, tests, audit, secrets, workflows, diff, evidence. `--tier` defaults to `full`. The neutral stack has no format, lint, types, contracts, tests or audit step.
- `check` never runs a model and needs no GitHub credential. It reaches the network only through uv: package downloads, and pip-audit's vulnerability lookups.
- Pins, looked up on 2026-10-14 with `gh api`: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1); `astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884` (v10.3.0); gitleaks 8.30.1, whose `gitleaks_8.30.1_linux_x64.tar.gz` has SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` in the release's checksum file and in GitHub's asset digest; `zizmor==1.30.1`; `pip-audit==2.10.1`; `pyyaml>=6.0.3,<7`.
- Caps from spec section 11's proposals: 500 lines per source file (`LINE_CAP`) and Ruff `max-complexity = 10`.
- devctl source is edited only under `rapid_ship/templates/common/tools/devctl/`. After every edit, run `uv run rapid-ship sync --in-place`. Never edit `tools/devctl/devctl/` by hand. Commit the template, the vendored copy and `.rapid-ship/kit.lock` together.
- devctl code passes the Python guardrail settings that task 18 adopts: no `print` (write to `sys.stdout`), no relative imports, no `Any` in a signature, complexity at most 10. devctl starts processes in two places only, each with one exception: `process.run_process` (EX-1) and plan 2's `repo._git` (EX-3). Other modules import the module and call `process.run_process`, the convention plan 4 relies on to record argv in tests.
- A suppression's exception marker has the form `<suppression>  # rs-exception: EX-<n>` on the same line.
- Check tools run with a scrubbed environment: `PATH`, `HOME`, a fixed locale, and the names in `PASSED_VARIABLES`. No token is ever passed.
- devctl's only new dependency is PyYAML. pip-audit and zizmor run with `uv tool run --from <exact pin>` and are not devctl dependencies.
- Tests come first, are fully annotated (mypy strict covers tests), and build fixture repositories in `tmp_path` with `git init`. A test module that uses stand-in executables says "simulated" in its docstring. devctl test files are named `tests/devctl/test_devctl_*.py`, plan 2's convention, so basenames stay unique without an `__init__.py`.
- From task 16 on, `uv run pytest` needs network access and gitleaks 8.30.1 on PATH: the integration tests run the full tier on a new project and, from task 17, on a synced copy of this repository. The CI workflow installs gitleaks before the check.
- This branch removes eight tests. Task 19's PR body declares each under `Removed tests:`; until then the full tier's diff step fails on them. Seven come from the tasks. The eighth is a rename: the final review's CODEOWNERS fix renames `test_the_python_codeowners_only_adds_pyproject`, and the diff step counts a renamed test as a removal.
- Branch names may use any prefix except `rs/`.

## Review Focus

1. **A test that moved, or whose name exists in another file.** A test moved to another file is not a removal. A removed test whose name survives in a different, unrelated file still counts as removed, because removal compares per-name counts over the changed files. Pinned in task 13.
2. **Blocked outranks failed, and a step that raises is blocked.** Results with both a failure and a blocked step exit 2, and an exception inside a step becomes a blocked result instead of a traceback that exits 1. Pinned in task 2.
3. **Exception IDs that are stale or misused.** An entry that no marker carries fails as stale; an ID on two lines fails; a marker whose entry names another path or rule fails. A rule with a tool prefix and several names, such as `zizmor:a,b`, matches its entry in any name order. Pinned in task 7.
4. **PR context in CI.** On GitHub's merge commit the base is the merge's first parent, not a stale `base.sha`; a null PR body becomes `""` so the evidence step fails instead of being skipped; CRLF line endings from the web editor are normalised. Pinned in task 2.
5. **Rules bullets with nested lists or fenced code, and feature files with no front matter.** A nested list item is part of its parent rule and needs no marker; a list inside a fenced block is code; a feature file without front matter fails with a message, not a crash. Pinned in task 5.
6. **Project overrides and extensions.** A Kit path under `[kit] exclude` in `project.toml` is the project's: the kit step does not require it, and the exceptions and file-size steps scan it. devctl reads the list only as `ProjectSettings.excluded`, never from a mark in the lock, and decides with its own `is_excluded`, which a parity test holds equal to the CLI's. A project's own verb and check step run through the seeded interface, and this repository's own steps still run after `sync --in-place` vendors a managed template edit and leaves the seeded `devctl_project` alone although its template changed. Pinned in tasks 6, 7, 16 and 17.

---

### Task 1: Move the process runner into devctl and fix its three defects

**Files:**
- Move: `rapid_ship/process.py` → `rapid_ship/templates/common/tools/devctl/devctl/process.py`
- Move: `tests/test_process.py` → `tests/devctl/test_devctl_process.py`
- Generated by sync: `tools/devctl/devctl/process.py`, `.rapid-ship/kit.lock`
- Modify: `.rapid-ship/exceptions.toml`, `rapid_ship/AGENTS.md`, `tests/AGENTS.md`, `ARCHITECTURE.md`

**Interfaces:**
- Consumes: nothing.
- Produces, in `devctl/process.py`:

```python
MAX_OUTPUT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


def safe_environment(env: Mapping[str, str] | None = None) -> dict[str, str]: ...
def run_process(
    argv: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> ProcessResult: ...
```

`cancel_event` and `ProcessResult.cancelled` are removed. Every caller that passes `cancel_event` today is in `rapid_ship/execution/` or its tests, which plan 1 deletes, and the cancel check is what forces the 10 ms poll.

The three defects, cited at the archive tag's `rapid_ship/process.py`:

| Defect | Where | Fix |
| --- | --- | --- |
| Hard-coded macOS `PATH` | `:33` | Inherit the caller's `PATH` (and `HOME`); nothing else |
| In-band truncation marker | `:15-16`, `:57-62` | Drop `_TRUNCATED`; report `stdout_truncated` and `stderr_truncated` |
| 10 ms poll | `:144-150` | Block in `proc.wait()`; a `threading.Timer` ends the group on timeout |

- [ ] **Step 1: Confirm the move breaks no caller and that sync accepts uncommitted changes.**

Run: `git grep -n -E "rapid_ship(\.process| import process)" -- '*.py'`
Expected: only `tests/test_process.py`. The `*.py` filter keeps plan documents that quote the import out of the result. If any `rapid_ship` module appears, stop: plan 2 depends on the runner, and the index must say where it lives before it moves.

Plan 2's `sync --in-place` skips the clean-tree check, so every task here can run it on uncommitted work (plan 2, task 5).

- [ ] **Step 2: Move the files and update the imports.**

```bash
git mv rapid_ship/process.py rapid_ship/templates/common/tools/devctl/devctl/process.py
git mv tests/test_process.py tests/devctl/test_devctl_process.py
```

In `tests/devctl/test_devctl_process.py`: replace `rapid_ship.process` with `devctl.process` (lines 9, 133 and 150 today); annotate every function; in `is_running`, replace `subprocess.run([...])` with `run_process(["ps", "-o", "stat=", "-p", str(pid)], Path.cwd(), 5)` and read `.returncode` and `.stdout`; add `match="argv must contain|positive finite"` to `pytest.raises(ValueError)`.

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_process.py -q`
Expected: all pass; the runner itself is unchanged.

- [ ] **Step 3: Write the failing tests for the three defects.**

Add to `tests/devctl/test_devctl_process.py`:

```python
import devctl.process as process


def test_tools_are_found_on_the_callers_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "bin"
    tools.mkdir()
    tool = tools / "fake-tool"
    tool.write_text("#!/bin/sh\necho found\n")
    tool.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")

    result = run_process(["fake-tool"], tmp_path, 5)

    assert result.returncode == 0
    assert result.stdout == "found\n"


def test_truncation_is_reported_beside_the_output_not_inside_it(tmp_path: Path) -> None:
    result = run_process(
        python(
            "import sys; sys.stdout.write('x' * 3000000); sys.stderr.write('[output truncated]')"
        ),
        tmp_path,
        10,
    )

    assert result.stdout_truncated
    assert result.stdout == "x" * MAX_OUTPUT_BYTES
    assert not result.stderr_truncated
    assert result.stderr == "[output truncated]"


def test_waiting_for_a_process_does_not_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(process.time, "sleep", sleeps.append)

    result = run_process(python("import time; time.sleep(0.3)"), tmp_path, 5)

    assert result.returncode == 0
    assert sleeps == []


def test_timeout_kills_a_leader_that_ignores_sigterm(tmp_path: Path) -> None:
    started = time.monotonic()
    result = run_process(
        python("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"),
        tmp_path,
        0.3,
    )

    assert result.timed_out
    assert time.monotonic() - started < 3
```

In `test_explicit_environment_and_output_are_bounded`, replace `assert "truncated" in result.stdout` with `assert result.stdout_truncated`. Delete `test_cancel_before_launch_does_not_execute`. Remove the `cancel` parameter from the grandchild test, rename it `test_timeout_kills_grandchild_even_if_it_ignores_sigterm`, and keep its timeout case.

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_process.py -q`
Expected failures: the `PATH` test raises `FileNotFoundError`, because `:33` replaces `PATH`; the truncation tests fail with `AttributeError: 'ProcessResult' object has no attribute 'stdout_truncated'`; the polling test records about thirty `0.01` sleeps. The SIGTERM-leader test passes already; it guards the rewrite in step 4.

- [ ] **Step 4: Fix the defects in the template.**

Edit `rapid_ship/templates/common/tools/devctl/devctl/process.py`:

```python
_GRACE_SECONDS = 0.15


def safe_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Pass PATH and HOME, which tools need to start, and nothing else unless supplied."""
    result = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if "HOME" in os.environ:
        result["HOME"] = os.environ["HOME"]
    if env:
        result.update(env)
    return result
```

In `_Capture.text`, return the retained bytes only: `bytes(self.data).decode("utf-8", errors="replace").replace("\ufffd", "?")`. Delete `_TRUNCATED`.

Remove the `cancel_event` parameter and the early cancelled return. Replace the poll loop and its `finally` block with:

```python
expired = threading.Event()


def expire() -> None:
    expired.set()
    _kill_group(proc.pid, signal.SIGTERM)
    time.sleep(_GRACE_SECONDS)
    _kill_group(proc.pid, signal.SIGKILL)


timer = threading.Timer(timeout_seconds, expire)
timer.daemon = True
timer.start()
try:
    proc.wait()  # Blocks in waitpid; on timeout the timer ends the group.
finally:
    timer.cancel()
    timer.join()
    # Descendants can outlive the leader and hold the pipes, so signal the group.
    _kill_group(proc.pid, signal.SIGTERM)
    proc.poll()
    _kill_group(proc.pid, signal.SIGKILL)
    proc.wait()
    if writer:
        writer.join(timeout=1)
    for reader in readers:
        reader.join(timeout=1)
return ProcessResult(
    list(argv),
    proc.returncode,
    captures[0].text(),
    captures[1].text(),
    time.monotonic() - start,
    expired.is_set(),
    captures[0].truncated,
    captures[1].truncated,
)
```

Replace the two `assert` statements about pipes with `if ...: raise RuntimeError("process pipes were not created")`. Mark the `subprocess.Popen(` line `# noqa: S603  # rs-exception: EX-1`. Accept `Sequence[str]` and `Mapping[str, str]` as typed above.

Add to `.rapid-ship/exceptions.toml`:

```toml
[[exception]]
id = "EX-1"
path = "rapid_ship/templates/common/tools/devctl/devctl/process.py"
rule = "S603"
reason = "The one place devctl starts a process; argv is a list and no shell runs"
remove_when = "Ruff stops reporting S603 for list arguments without a shell"
```

- [ ] **Step 5: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_process.py -q`
Expected: all pass.

- [ ] **Step 6: Update the guides.** In `rapid_ship/AGENTS.md`, delete the `process.py` bullet that plan 1 wrote. In `tests/AGENTS.md`, point plan 1's `Bounded process runner` row at `[devctl/test_devctl_process.py](devctl/test_devctl_process.py)`, so no link names the moved `test_process.py`. In `ARCHITECTURE.md`, replace plan 1's `Bounded process runner` row, which names `rapid_ship/process.py`, with:

```markdown
| Bounded process runner | `tools/devctl/devctl/process.py`, edited in its template under `rapid_ship/templates/common/tools/devctl/` | Runs devctl's check tools; after a template edit, run `uv run rapid-ship sync --in-place` |
```

- [ ] **Step 7: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl/devctl/process.py tools/devctl/devctl/process.py \
  .rapid-ship/kit.lock .rapid-ship/exceptions.toml tests/devctl/test_devctl_process.py \
  rapid_ship/AGENTS.md tests/AGENTS.md ARCHITECTURE.md
git commit -m "refactor: move the process runner into devctl

Inherit the caller's PATH, report truncation beside the output and wait
without polling. Cancellation goes: no caller remains after plan 1.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Step types, the runner and the `check` command

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`, `check/steps.py`, `check/stacks/__init__.py` (empty package marker)
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/cli.py`, `devctl/repo.py`, `devctl_project/__init__.py` (the seed), and this repository's seeded `tools/devctl/devctl_project/__init__.py`
- Modify: `.rapid-ship/exceptions.toml`, `pyproject.toml` (pytest `pythonpath`), `tests/conftest.py`, plan 2's `tests/devctl/test_devctl_repo.py`
- Delete: `tests/devctl/conftest.py`
- Create: `tests/devctl/check_workspace.py`, `tests/devctl/test_devctl_check_runner.py`, `tests/devctl/test_devctl_check_cli.py`

**Interfaces:**
- Consumes from plan 2: `ProjectSettings`, `GateSettings`, `SettingsError`, `load_project(root: Path) -> ProjectSettings`, `load_gate(root: Path) -> GateSettings`; `build_parser() -> argparse.ArgumentParser` and `main(argv: Sequence[str] | None = None) -> int` in `devctl/cli.py`, where a verb sets a `handler` that returns the exit code; and `devctl/repo.py`'s `RepoError`, `Repo(root: Path, git_common_dir: Path)`, `Repo.discover(start: Path) -> Repo`, `tracked_files() -> list[str]`, `merge_base(ref: str) -> str | None` and the private `_git(cwd, *args, allowed=(0,))`.
- Produces, in `devctl/repo.py`, the two members plan 2 leaves to this plan:

```python
def files(self) -> list[str]:
    """Tracked files plus untracked files that Git does not ignore, as POSIX paths."""
    output = _git(self.root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    return sorted({os.fsdecode(name) for name in output.split(b"\0") if name})


def git(self, *args: str) -> str:
    """Run git in the work tree and return its output; RepoError when it fails."""
    return os.fsdecode(_git(self.root, *args).stdout)
```

- Produces, in the `devctl_project` seed: `check_steps() -> list[Step]`, narrowing plan 2's `list[object]` now that `Step` exists.

- Produces, in `devctl/check/steps.py`, the index's `Tier`, `Status`, `StepResult`, `CheckContext` and `Step` unchanged, plus:

```python
PASSED_VARIABLES: tuple[str, ...]


def passed(name: str, *details: str) -> StepResult: ...
def failed(name: str, *details: str) -> StepResult: ...
def blocked(name: str, *details: str) -> StepResult: ...
def not_applicable(name: str, *details: str) -> StepResult: ...
def tool_environment() -> dict[str, str]: ...
```

- Produces, in `devctl/check/__init__.py`:

```python
TIERS: dict[Tier, frozenset[Tier]]


class ChangeError(Exception): ...


def core_steps(project: ProjectSettings) -> list[Step]: ...
def all_steps(project: ProjectSettings) -> list[Step]: ...
def run_check(context: CheckContext, tier: Tier) -> list[StepResult]: ...  # index signature
def exit_code(results: Sequence[StepResult]) -> int: ...
def resolve_change(
    repo: Repo, base: str | None, pr_body_path: Path | None, environ: Mapping[str, str]
) -> tuple[str | None, str | None]: ...
```

- Produces, in `devctl/cli.py`: the `check` command with `--tier {fast,full}`, `--json`, `--base REV` and `--pr-body PATH`, whose handler is `check_command(args: argparse.Namespace) -> int`.

- [ ] **Step 1: Write the failing Repo tests.** Append to plan 2's `tests/devctl/test_devctl_repo.py`, adding `from collections.abc import Callable` and `from pathlib import Path` to its imports:

```python
def test_files_lists_tracked_and_unignored_untracked_paths(
    git_repo: Path, commit_all: Callable[..., None]
) -> None:
    (git_repo / ".gitignore").write_text("ignored.txt\n")
    (git_repo / "tracked.txt").write_text("x\n")
    commit_all(git_repo)
    (git_repo / "new dir").mkdir()
    (git_repo / "new dir/untracked.txt").write_text("y\n")
    (git_repo / "ignored.txt").write_text("z\n")

    assert Repo.discover(git_repo).files() == [".gitignore", "new dir/untracked.txt", "tracked.txt"]


def test_git_returns_the_output_and_raises_repo_error_on_failure(
    git_repo: Path, commit_all: Callable[..., None]
) -> None:
    commit_all(git_repo)
    repo = Repo.discover(git_repo)

    assert repo.git("rev-parse", "--abbrev-ref", "HEAD") == "main\n"
    with pytest.raises(RepoError, match="rev-parse"):
        repo.git("rev-parse", "--verify", "no-such-ref")
```

Run: `uv run pytest tests/devctl/test_devctl_repo.py -q`
Expected: both new tests fail with `AttributeError: 'Repo' object has no attribute 'files'` and `... no attribute 'git'`; plan 2's tests pass.

- [ ] **Step 2: Add the Repo members, narrow the seed and move the test path setting.**

Add `files` and `git` above to the template's `repo.py`.

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_repo.py -q`
Expected: all pass. Run it before narrowing the seed below, which imports `devctl.check.steps` before step 6 creates it.

Mark the `subprocess.run(` line in plan 2's `_git` with `# noqa: S603, S607  # rs-exception: EX-3`, and add EX-3 to `.rapid-ship/exceptions.toml` with `rule = "S603,S607"`, `path = "rapid_ship/templates/common/tools/devctl/devctl/repo.py"`, `reason = "Runs git with fixed arguments and keeps raw bytes for paths that are not UTF-8"` and `remove_when = "repo.py runs git through process.run_process"`.

In the seed template `devctl_project/__init__.py` and in this repository's seeded copy, import `Step` from `devctl.check.steps` and annotate `check_steps() -> list[Step]`.

Delete `tests/devctl/conftest.py`, which only inserts `tools/devctl` into `sys.path`. Add `pythonpath = ["tools/devctl", "tests/devctl"]` to `[tool.pytest.ini_options]` instead. pytest applies it before it imports any conftest, so `tests/conftest.py` can import the devctl test helper. With one `conftest.py` left, mypy does not see two modules named `conftest` once task 18 type-checks `tests/`. The index's layout note for `tests/devctl/` records this choice.

- [ ] **Step 3: Add the test workspace.**

Create `tests/devctl/check_workspace.py`:

```python
"""A scratch git repository and check context for devctl tests."""

from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass
from pathlib import Path

from devctl.check.steps import CheckContext, Status, StepResult, Tier
from devctl.process import ProcessResult, run_process
from devctl.repo import Repo
from devctl.settings import GateSettings, ProjectSettings

GIT_IDENTITY = (
    "-c",
    "user.name=devctl tests",
    "-c",
    "user.email=devctl@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)


def project_settings(**changes: object) -> ProjectSettings:
    base = ProjectSettings(
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
        worktree_root="../app.worktrees",
        source_roots=("src/app",),
        unguided=(),
        unit_tests=("tests/unit/**",),
        release_method="none",
    )
    return dataclasses.replace(base, **changes)


def gate_settings(**changes: object) -> GateSettings:
    base = GateSettings(
        mode="walk", flight_lease_until=None, owner_approves_behavioural_test_removal=True
    )
    return dataclasses.replace(base, **changes)


def skill_text(name: str) -> str:
    """A SKILL.md that satisfies map rule 7 for the skill directory `name`."""
    return f"---\nname: {name}\ndescription: Use when testing devctl.\n---\n# {name}\n"


@dataclass(frozen=True)
class Workspace:
    root: Path

    def try_git(self, *args: str) -> ProcessResult:
        return run_process(["git", *GIT_IDENTITY, *args], self.root, 60)

    def git(self, *args: str) -> str:
        result = self.try_git(*args)
        if result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()

    def write(self, path: str, text: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def link(self, path: str, target: str) -> None:
        alias = self.root / path
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(target, target_is_directory=True)

    def commit(self, message: str = "change") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def context(
        self,
        *,
        base: str | None = None,
        pr_body: str | None = None,
        gate: GateSettings | None = None,
        **project: object,
    ) -> CheckContext:
        return CheckContext(
            Repo.discover(self.root),
            project_settings(**project),
            gate or gate_settings(),
            base,
            pr_body,
        )


def new_workspace(path: Path) -> Workspace:
    path.mkdir(parents=True)
    result = run_process(["git", "init", "-q", "-b", "main", str(path)], path, 60)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return Workspace(path.resolve())


def fake_tool(directory: Path, name: str, body: str) -> Path:
    """Write a stand-in executable that logs its arguments, then runs body."""
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "here = pathlib.Path(__file__)\n"
        "with open(here.with_name(here.name + '.log'), 'a') as log:\n"
        "    log.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(),"
        " 'env': sorted(os.environ)}) + '\\n')\n"
        f"{body}\n"
    )
    tool.chmod(0o700)
    return tool


class FakeStep:
    def __init__(
        self, name: str, tier: Tier, status: Status = "passed", details: tuple[str, ...] = ()
    ) -> None:
        self.name = name
        self.tier = tier
        self.status = status
        self.details = details

    def run(self, context: CheckContext) -> StepResult:
        return StepResult(self.name, self.status, self.details)


class BrokenStep(FakeStep):
    def run(self, context: CheckContext) -> StepResult:
        raise RuntimeError("step bug")
```

Add to plan 2's `tests/conftest.py`, beside its `git_repo` fixture:

```python
from check_workspace import Workspace, new_workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A git repository for devctl check tests."""
    return new_workspace(tmp_path / "repo")
```

- [ ] **Step 4: Write the failing runner tests.** Create `tests/devctl/test_devctl_check_runner.py`:

```python
"""run_check, exit codes and how the change under check is found."""

from __future__ import annotations

import json
from pathlib import Path

import devctl_project
import pytest
from check_workspace import BrokenStep, FakeStep, Workspace
from devctl import check
from devctl.check import ChangeError, exit_code, resolve_change, run_check
from devctl.check.steps import StepResult, blocked, failed, not_applicable, passed
from devctl.repo import Repo


def use_steps(monkeypatch: pytest.MonkeyPatch, *steps: FakeStep) -> None:
    monkeypatch.setattr(check, "all_steps", lambda project: list(steps))


def test_fast_tier_runs_only_fast_steps(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_steps(monkeypatch, FakeStep("lint", "fast"), FakeStep("tests", "full"))

    assert [r.name for r in run_check(workspace.context(), "fast")] == ["lint"]
    assert [r.name for r in run_check(workspace.context(), "full")] == ["lint", "tests"]


def test_a_step_that_raises_is_blocked(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_steps(monkeypatch, BrokenStep("map", "fast"))

    [result] = run_check(workspace.context(), "full")

    assert result.status == "blocked"
    assert result.details == ("RuntimeError: step bug",)


@pytest.mark.parametrize(
    ("results", "code"),
    [
        ([], 0),
        ([passed("a"), not_applicable("b")], 0),
        ([passed("a"), failed("b")], 1),
        ([failed("a"), blocked("b")], 2),
        ([blocked("a"), passed("b")], 2),
    ],
)
def test_blocked_outranks_failed(results: list[StepResult], code: int) -> None:
    assert exit_code(results) == code


def test_two_steps_cannot_share_a_name(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        devctl_project, "check_steps", lambda: [FakeStep("map", "fast"), FakeStep("map", "full")]
    )

    with pytest.raises(ValueError, match="two check steps are named map"):
        check.all_steps(workspace.context().project)


def pull_request_event(path: Path, base: str, head: str, body: str | None) -> dict[str, str]:
    event = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}, "body": body}}
    path.write_text(json.dumps(event))
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(path),
    }


def test_pull_request_base_is_the_merge_commits_first_parent(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    stale_base = workspace.commit("base")
    workspace.git("checkout", "-q", "-b", "feature")
    workspace.write("b.txt", "feature\n")
    head = workspace.commit("feature")
    workspace.git("checkout", "-q", "main")
    workspace.write("c.txt", "main moved on\n")
    current_base = workspace.commit("main moved")
    # GitHub's refs/pull/<n>/merge commit has these parents: base tip, then PR head.
    workspace.git("merge", "-q", "--no-ff", "--no-edit", "feature")
    environ = pull_request_event(
        workspace.root.parent / "event.json", stale_base, head, "## Evidence\r\nNot covered: x\r\n"
    )

    base, body = resolve_change(Repo.discover(workspace.root), None, None, environ)

    assert base == current_base
    assert body == "## Evidence\nNot covered: x\n"


def test_pull_request_without_a_merge_commit_uses_the_merge_base(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    workspace.git("checkout", "-q", "-b", "feature")
    workspace.write("b.txt", "feature\n")
    head = workspace.commit("feature")
    environ = pull_request_event(workspace.root.parent / "event.json", base_sha, head, None)

    base, body = resolve_change(Repo.discover(workspace.root), None, None, environ)

    assert base == base_sha
    assert body == ""


def test_ci_outside_a_pull_request_has_no_change(workspace: Workspace) -> None:
    workspace.commit("base")
    environ = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "schedule"}

    assert resolve_change(Repo.discover(workspace.root), None, None, environ) == (None, None)


def test_local_base_is_the_merge_base_with_origins_default_branch(workspace: Workspace) -> None:
    workspace.write("a.txt", "one\n")
    base_sha = workspace.commit("base")
    workspace.git("update-ref", "refs/remotes/origin/main", base_sha)
    workspace.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    workspace.write("b.txt", "two\n")
    workspace.commit("local work")
    body = workspace.root.parent / "body.md"
    body.write_text("PR text\n")

    assert resolve_change(Repo.discover(workspace.root), None, body, {}) == (base_sha, "PR text\n")


def test_local_run_without_origin_has_no_base(workspace: Workspace) -> None:
    workspace.commit("base")

    assert resolve_change(Repo.discover(workspace.root), None, None, {}) == (None, None)


def test_explicit_base_must_be_a_commit(workspace: Workspace) -> None:
    first = workspace.commit("one")
    workspace.commit("two")
    repo = Repo.discover(workspace.root)

    assert resolve_change(repo, "HEAD~1", None, {})[0] == first
    with pytest.raises(ChangeError, match="nope is not a commit"):
        resolve_change(repo, "nope", None, {})


def test_unreadable_event_file_is_an_error(workspace: Workspace) -> None:
    workspace.commit("base")
    environ = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(workspace.root / "missing.json"),
    }

    with pytest.raises(ChangeError, match="event"):
        resolve_change(Repo.discover(workspace.root), None, None, environ)
```

- [ ] **Step 5: Write the failing CLI tests.** Create `tests/devctl/test_devctl_check_cli.py`:

```python
"""devctl check output, JSON and exit codes, with stand-in steps."""

from __future__ import annotations

import json

import pytest
from check_workspace import FakeStep, Workspace, gate_settings, project_settings
from devctl import check, cli
from devctl.settings import SettingsError


def run(
    workspace: Workspace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> tuple[int, str]:
    monkeypatch.chdir(workspace.root)
    for name in ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "load_project", lambda root: project_settings())
    monkeypatch.setattr(cli, "load_gate", lambda root: gate_settings())
    code = cli.main(["check", *args])
    return code, capsys.readouterr().out


STEPS = (
    FakeStep("format", "fast"),
    FakeStep("lint", "fast", "failed", ("x.py:1:1: F401 unused import",)),
    FakeStep("evidence", "full", "not_applicable", ("not a pull request",)),
)


def test_one_line_per_step_with_details(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(check, "all_steps", lambda project: list(STEPS))

    code, out = run(workspace, monkeypatch, capsys)

    assert code == 1
    assert out == (
        "passed         format\n"
        "failed         lint\n"
        "    x.py:1:1: F401 unused import\n"
        "not applicable evidence\n"
        "    not a pull request\n"
    )


def test_json_prints_the_same_results(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(check, "all_steps", lambda project: list(STEPS))

    code, out = run(workspace, monkeypatch, capsys, "--tier", "fast", "--json")

    assert code == 1
    assert json.loads(out) == [
        {"name": "format", "status": "passed", "details": []},
        {"name": "lint", "status": "failed", "details": ["x.py:1:1: F401 unused import"]},
    ]


def test_blocked_step_exits_two(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.setattr(
        check,
        "all_steps",
        lambda project: [FakeStep("lint", "fast", "failed"), FakeStep("audit", "full", "blocked")],
    )

    assert run(workspace, monkeypatch, capsys)[0] == 2


def test_unreadable_settings_exit_two(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace.commit("base")
    monkeypatch.chdir(workspace.root)

    def broken(root: object) -> None:
        raise SettingsError("project.toml: stack is missing")

    monkeypatch.setattr(cli, "load_project", broken)

    assert cli.main(["check"]) == 2
    assert "stack is missing" in capsys.readouterr().err
```

Run: `uv run pytest tests/devctl/test_devctl_check_runner.py tests/devctl/test_devctl_check_cli.py -q`
Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.check'`.

- [ ] **Step 6: Implement `check/steps.py`.**

```python
"""Check step types and helpers shared by every step."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol

from devctl.repo import Repo
from devctl.settings import GateSettings, ProjectSettings

Tier = Literal["fast", "full"]
Status = Literal["passed", "failed", "blocked", "not_applicable"]

# Variables a check tool may need besides PATH and HOME. Never add one that can hold a token.
PASSED_VARIABLES = (
    "TMPDIR",
    "CI",
    "SSL_CERT_FILE",
    "UV_CACHE_DIR",
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_TOOL_DIR",
    "UV_TOOL_BIN_DIR",
)


@dataclass(frozen=True)
class StepResult:
    name: str
    status: Status
    details: tuple[str, ...]


@dataclass(frozen=True)
class CheckContext:
    repo: Repo
    project: ProjectSettings
    gate: GateSettings
    base: str | None
    pr_body: str | None


class Step(Protocol):
    # A frozen dataclass cannot implement these settable members; use a class or plain dataclass.
    name: str
    tier: Tier

    def run(self, context: CheckContext) -> StepResult: ...


def passed(name: str, *details: str) -> StepResult:
    return StepResult(name, "passed", details)
```

`failed`, `blocked` and `not_applicable` follow the same one-line form. `tool_environment()` returns `{name: os.environ[name] for name in PASSED_VARIABLES if name in os.environ}`.

- [ ] **Step 7: Implement `check/__init__.py`.**

```python
TIERS: dict[Tier, frozenset[Tier]] = {
    "fast": frozenset({"fast"}),
    "full": frozenset({"fast", "full"}),
}


class ChangeError(Exception):
    """The base commit or the PR body could not be determined."""


def core_steps(project: ProjectSettings) -> list[Step]:
    """Core steps for the project's stack in spec section 5's order. Tasks 3-13 fill this."""
    return []


def all_steps(project: ProjectSettings) -> list[Step]:
    import devctl_project  # Imported late: devctl_project imports devctl.check.steps.

    steps = [*core_steps(project), *devctl_project.check_steps()]
    names: set[str] = set()
    for step in steps:
        if step.tier not in TIERS:
            raise ValueError(f"check step {step.name}: tier must be fast or full")
        if step.name in names:
            raise ValueError(f"two check steps are named {step.name}")
        names.add(step.name)
    return steps


def run_check(context: CheckContext, tier: Tier) -> list[StepResult]:
    results: list[StepResult] = []
    for step in all_steps(context.project):
        if step.tier not in TIERS[tier]:
            continue
        try:
            results.append(step.run(context))
        except Exception as error:  # noqa: BLE001  # rs-exception: EX-2
            # An uncaught error would exit 1, which reads as a failure, not "could not run".
            results.append(blocked(step.name, f"{type(error).__name__}: {error}"))
    return results


def exit_code(results: Sequence[StepResult]) -> int:
    statuses = {result.status for result in results}
    if "blocked" in statuses:
        return 2
    return 1 if "failed" in statuses else 0
```

`resolve_change`, with private helpers:

1. When `environ["GITHUB_EVENT_NAME"] == "pull_request"`, read the JSON at `GITHUB_EVENT_PATH` and take its `pull_request` object. A missing path, unreadable file, invalid JSON, missing object, or a `base.sha` or `head.sha` that is not a string raises `ChangeError("cannot read the pull_request event: ...")`.
2. Body: the `--pr-body` file's text when given; else the event's `body`, with `None` read as `""`; else `None`. Replace `"\r\n"` with `"\n"` in any body.
3. Base, first match wins:
   - `--base` given: `repo.git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()`; on `RepoError` raise `ChangeError(f"--base {rev} is not a commit")`.
   - Pull request: read `HEAD`'s parents with `repo.git("rev-list", "--parents", "-n", "1", "HEAD").split()`. When there are two parents and the second is `pull_request.head.sha`, return the first. `actions/checkout` checks out GitHub's merge commit for `pull_request` events, whose parents are the base tip and then the PR head; on 2026-10-14 `gh api repos/astral-sh/uv/commits/<merge_commit_sha>` for open PR #22528 listed exactly its `base.sha` then its `head.sha`. The first parent is the base the change was merged onto, even when `base.sha` in the payload is older. Otherwise return `repo.merge_base(<pull_request.base.sha>)`, raising `ChangeError("cannot find the PR base; check out full history (fetch-depth: 0)")` when it returns `None` or raises `RepoError`.
   - `environ.get("GITHUB_ACTIONS") == "true"`: `None` (push, schedule or manual run).
   - Locally: `repo.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")`, then `repo.merge_base(<that ref>)`. A `RepoError` from either gives `None`.

Add to `.rapid-ship/exceptions.toml`:

```toml
[[exception]]
id = "EX-2"
path = "rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py"
rule = "BLE001"
reason = "A step's unexpected error must report that step as blocked, never crash the run as a failure"
remove_when = "Every step catches its own errors and run_check no longer needs a fallback"
```

- [ ] **Step 8: Add the `check` command to `cli.py`.** Register it the way plan 2 registers commands: `--tier` with `choices=("fast", "full")` and default `"full"`, `--json` as `store_true`, `--base`, and `--pr-body` with `type=Path`. The handler:

```python
def check_command(args: argparse.Namespace) -> int:
    try:
        repo = Repo.discover(Path.cwd())
        base, pr_body = resolve_change(repo, args.base, args.pr_body, os.environ)
        context = CheckContext(repo, load_project(repo.root), load_gate(repo.root), base, pr_body)
        results = run_check(context, args.tier)
    except (RepoError, SettingsError, ChangeError, OSError, ValueError) as error:
        sys.stderr.write(f"devctl check: {error}\n")
        return 2
    sys.stdout.write(render_json(results) if args.json else render_text(results))
    return exit_code(results)


LABELS: dict[Status, str] = {
    "passed": "passed",
    "failed": "failed",
    "blocked": "blocked",
    "not_applicable": "not applicable",
}


def render_text(results: Sequence[StepResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f"{LABELS[result.status]:<15}{result.name}")
        lines.extend(f"    {detail}" for detail in result.details)
    return "".join(f"{line}\n" for line in lines)


def render_json(results: Sequence[StepResult]) -> str:
    data = [{"name": r.name, "status": r.status, "details": list(r.details)} for r in results]
    return json.dumps(data, indent=2) + "\n"
```

- [ ] **Step 9: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`
Expected: all pass.

- [ ] **Step 10: Commit.**

```bash
git add -A rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship tests/devctl \
  tests/conftest.py pyproject.toml
git commit -m "feat: add the devctl check runner and command

Steps report passed, failed, blocked or not applicable; blocked exits 2
and outranks failed. In CI the base and PR body come from the event.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Map links and skill aliases, ported from `scripts/check_repository.py`

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/markdown.py`, `check/map.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`
- Create: `tests/devctl/test_devctl_map_links.py`

**Interfaces:**
- Consumes: `CheckContext`, `Repo.files()`, `RepoError`, step helpers from task 2.
- Produces, in `devctl/check/markdown.py`:

```python
def without_fences(text: str) -> str: ...  # blanks fenced code, keeps line numbers
def without_code(text: str) -> str: ...  # also blanks inline code spans
def navigation_links(text: str) -> list[tuple[int, str]]: ...  # raises ValueError on bad syntax
def fenced_blocks(text: str) -> list[list[str]]: ...
```

- Produces, in `devctl/check/map.py`:

```python
class MapStep:
    name = "map"
    tier: Tier = "fast"

    def run(self, context: CheckContext) -> StepResult: ...


def guides(root: Path, files: Sequence[str], project: ProjectSettings) -> list[str]: ...
def link_errors(root: Path, files: Sequence[str], found: Sequence[str]) -> list[str]: ...
def skill_alias_errors(root: Path, files: Sequence[str]) -> list[str]: ...  # map rule 7, alias half
```

Map rule 7 has two halves. This task writes the alias half: each `.agents/skills/<name>` has a `SKILL.md` and a relative symlink at `.claude/skills/<name>`, and nothing else sits under `.claude/skills/`. Task 5 adds the front-matter half once `front_matter` exists. The fixtures write `SKILL.md` with `skill_text`, so these tests stay green after task 5.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_map_links.py`. Port every test from `tests/test_repository_navigation.py` with these changes, and add the four new tests shown.

```python
"""Map rule 1 (links in every AGENTS.md) and map rule 7's skill discovery aliases."""

from __future__ import annotations

import shutil

import pytest
from check_workspace import Workspace, skill_text
from devctl.check.map import MapStep, guides, link_errors, skill_alias_errors


@pytest.fixture
def repository(workspace: Workspace) -> Workspace:
    workspace.write(".gitignore", ".venv/\n.worktrees/\noutput/\n")
    workspace.write(".agents/skills/example/SKILL.md", skill_text("example"))
    workspace.link(".claude/skills/example", "../../.agents/skills/example")
    return workspace


def problems(workspace: Workspace) -> str:
    context = workspace.context()
    files = context.repo.files()
    root = context.repo.root
    found = guides(root, files, context.project)
    return "\n".join([*link_errors(root, files, found), *skill_alias_errors(root, files)])


def test_accepts_existing_file_and_directory_navigation(repository: Workspace) -> None:
    repository.write("docs/start.md", "Start here\n")
    repository.write("AGENTS.md", "[Start](docs/start.md) and [Docs](docs/)\n")

    assert problems(repository) == ""


@pytest.mark.parametrize("problem", ["missing", "dangling", "wrong", "absolute", "outside", "copy"])
def test_rejects_invalid_skill_alias(repository: Workspace, problem: str) -> None:
    alias = repository.root / ".claude/skills/example"
    alias.unlink()
    if problem == "dangling":
        alias.symlink_to("../../missing", target_is_directory=True)
    elif problem == "wrong":
        alias.symlink_to("../../.agents/skills", target_is_directory=True)
    elif problem == "absolute":
        alias.symlink_to(repository.root / ".agents/skills/example", target_is_directory=True)
    elif problem == "outside":
        alias.symlink_to("../../../", target_is_directory=True)
    elif problem == "copy":
        # Even an identical copy fails: rule 7 asks for a symlink, and init and sync never copy.
        repository.write(".claude/skills/example/SKILL.md", skill_text("example"))

    found = problems(repository)

    assert ".claude/skills/example" in found
    assert "../../.agents/skills/example" in found


def test_canonical_skill_may_link_into_a_package(workspace: Workspace) -> None:
    workspace.write("pkg/skills/example/SKILL.md", skill_text("example"))
    workspace.link(".agents/skills/example", "../../pkg/skills/example")
    workspace.link(".claude/skills/example", "../../pkg/skills/example")

    assert problems(workspace) == ""


def test_skill_directory_without_skill_md_fails(repository: Workspace) -> None:
    repository.write(".agents/skills/notes/README.md", "# Notes\n")
    repository.link(".claude/skills/notes", "../../.agents/skills/notes")

    assert problems(repository) == ".agents/skills/notes: missing SKILL.md"


def test_nothing_else_may_sit_under_claude_skills(repository: Workspace) -> None:
    repository.write(".claude/skills/AGENTS.md", "# Discovery\n")
    repository.write(".claude/skills/notes.md", "Notes\n")

    assert problems(repository) == (
        ".claude/skills/AGENTS.md: only skill links belong in .claude/skills; remove it\n"
        ".claude/skills/notes.md: only skill links belong in .claude/skills; remove it"
    )


def test_map_is_blocked_when_git_cannot_list_files(repository: Workspace) -> None:
    context = repository.context()
    shutil.rmtree(repository.root / ".git")

    assert MapStep().run(context).status == "blocked"
```

Port the remaining tests of `tests/test_repository_navigation.py` with these mechanical changes: `repository` is the fixture above; `check(repository)` becomes `problems(repository)`; `returncode == 0` becomes `== ""`; `returncode == 1` plus `result.stderr` checks become substring checks on the returned string. Adapt the alias tests to the new layout:
- `test_accepts_navigation_through_maintained_skill_alias` links `.claude/skills/example/SKILL.md`.
- `test_new_packaged_skill_requires_both_discovery_aliases` becomes `test_new_skill_requires_a_claude_alias`: add `.agents/skills/new-skill/SKILL.md` with `skill_text("new-skill")` and expect `.claude/skills/new-skill` and `symlink` in the result; then link it and expect `""`.
- `test_rejects_extra_alias_but_allows_parent_guide` adds an extra `.claude/skills/unpackaged` link and the parent guide `.claude/AGENTS.md`, which sits beside `skills/`, not in it; it expects `.claude/skills/unpackaged` and `remove`, and no mention of `AGENTS.md`.
- `test_required_alias_must_be_maintained_in_git` ignores `.claude/skills/example` and expects `.claude/skills/example` and `track it in Git`.
- `test_copied_directory_counts_as_extra_alias` writes `.claude/skills/unpackaged/SKILL.md` and expects `.claude/skills/unpackaged` and `remove`.
- `test_fails_if_git_cannot_enumerate_the_checkout` is replaced by `test_map_is_blocked_when_git_cannot_list_files` above.

Run: `uv run pytest tests/devctl/test_devctl_map_links.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.map'`.

- [ ] **Step 2: Port the Markdown parsing to `markdown.py`.** Move `LABEL`, `TITLE`, `blank`, `without_code`, `destination`, `reference_key` and `navigation_links` from `scripts/check_repository.py:17-125`. Split the fence handling of `without_code` (`:25-38`) into `without_fences`, and have `without_code` call it before blanking inline code (`:39-43`). Split `navigation_links` into `_reference_definitions(text) -> tuple[dict[str, str], str]` and the link scan, so each function stays within complexity 10. Behaviour, messages and line numbers stay as they are. Add:

```python
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def fenced_blocks(text: str) -> list[list[str]]:
    """Return the content lines of each closed fenced code block."""
    blocks: list[list[str]] = []
    fence = ""
    current: list[str] = []
    for line in text.splitlines():
        if not fence:
            if opening := _FENCE.match(line):
                fence = opening.group(1)
            continue
        if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line):
            blocks.append(current)
            fence, current = "", []
        else:
            current.append(line)
    return blocks
```

- [ ] **Step 3: Port the link check to `map.py`.** `guides(root, files, project)` returns the paths in `files` named `AGENTS.md` that exist as files. `link_errors` is `check_navigation` from `scripts/check_repository.py:137-179`, taking POSIX strings instead of `Path` lists. Move the per-link body (`:152-178`) into `_link_error(root, guide, line, target, maintained, aliases) -> str | None` and keep its messages. Then write the skill alias rule. It replaces `:182-226`, whose canonical location was the hard-coded `rapid_ship/skills`; now `.agents/skills/<name>` is canonical and `.claude/skills/<name>` is its alias:

```python
def skill_alias_errors(root: Path, files: Sequence[str]) -> list[str]:
    present = set(files)
    canonical = _skill_names(root, files, ".agents/skills")
    aliases = _skill_names(root, files, ".claude/skills")
    errors = [_canonical_error(root, name) for name in sorted(canonical)]
    errors += [_alias_error(root, present, name) for name in sorted(canonical)]
    errors += [
        f".claude/skills/{name}: no matching .agents/skills/{name} in Git; "
        "remove the alias or add the skill"
        for name in sorted(aliases - canonical)
    ]
    errors += [
        f"{path}: only skill links belong in .claude/skills; remove it"
        for path in _stray_files(root, files)
    ]
    return [error for error in errors if error]


def _skill_names(root: Path, files: Sequence[str], surface: str) -> set[str]:
    names: set[str] = set()
    for path in files:
        if path.startswith(f"{surface}/"):
            name = path[len(surface) + 1 :].split("/", 1)[0]
            entry = root / surface / name
            if entry.is_symlink() or entry.is_dir():  # files are not skills
                names.add(name)
    return names


def _stray_files(root: Path, files: Sequence[str]) -> list[str]:
    """Files directly under .claude/skills, such as a guide; rule 7 allows only skill links."""
    names = {path.split("/")[2] for path in files if path.startswith(".claude/skills/")}
    entries = {name: root / ".claude/skills" / name for name in names}
    return sorted(
        f".claude/skills/{name}"
        for name, entry in entries.items()
        if not entry.is_symlink() and not entry.is_dir()
    )


def _canonical_error(root: Path, name: str) -> str | None:
    entry = root / ".agents/skills" / name
    if entry.is_symlink() and (
        entry.readlink().is_absolute() or not entry.resolve().is_relative_to(root.resolve())
    ):
        return f".agents/skills/{name}: make it a relative symlink inside the repository"
    if not (entry / "SKILL.md").is_file():
        return f".agents/skills/{name}: missing SKILL.md"
    return None


def _alias_error(root: Path, present: set[str], name: str) -> str | None:
    relative = f".claude/skills/{name}"
    alias, canonical = root / relative, root / ".agents/skills" / name
    expected = f"../../.agents/skills/{name}"
    if relative in present and alias.is_symlink():
        resolved = alias.resolve()
        inside = resolved.is_relative_to(root.resolve())
        if not alias.readlink().is_absolute() and inside and resolved == canonical.resolve():
            return None
        return f"{relative}: make it a relative symlink to {expected}"
    if (
        alias.is_dir()
        and not alias.is_symlink()
        and any(p.startswith(f"{relative}/") for p in present)
    ):
        return (
            f"{relative}: a copy is not an alias; replace it with a relative symlink to {expected}"
        )
    return f"{relative}: add a relative symlink to {expected} and track it in Git"
```

A copy fails even when identical. Rule 7 asks for a symlink, and spec section 4 makes `init` and `sync` stop with exit 2 where one cannot be created, so the Kit never writes a copy.

`MapStep.run` reads `context.repo.files()` (returning `blocked` on `RepoError`), runs `link_errors` and `skill_alias_errors`, and returns `failed` with all errors, or `passed`. In `core_steps`, return `[MapStep()]`.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_map_links.py -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_map_links.py
git commit -m "feat: port navigation and skill alias checks into devctl map

.agents/skills is now the canonical skill location in any project. Each
skill needs a SKILL.md and a relative symlink in .claude/skills, and
nothing else may sit there.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Map directory coverage and reachability

**Files:**
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/map.py`, `devctl/settings.py`, `rapid_ship/templates/python/.rapid-ship/project.toml`, `rapid_ship/templates/neutral/.rapid-ship/project.toml`, `.rapid-ship/project.toml`; plan 2's `tests/devctl/test_devctl_settings.py` and `tests/test_kit_contents.py`
- Modify: `tests/devctl/check_workspace.py`
- Create: `tests/devctl/test_devctl_map_coverage.py`

**Interfaces:**
- Consumes: `ProjectSettings.source_roots`, `.unguided`, and `.map_exclude: tuple[str, ...]`, read from `[map] exclude` with default `()`. The index's settings block lists `map_exclude` as this task's addition. Template trees that hold `AGENTS.md` files, such as this repository's `rapid_ship/templates/common`, need it so that they are not treated as guides.
- Produces, in `map.py`:

```python
def excluded(path: str, project: ProjectSettings) -> bool: ...
def coverage_errors(files: Sequence[str], project: ProjectSettings) -> list[str]: ...
def reachability_errors(root: Path, found: Sequence[str]) -> list[str]: ...
```

- [ ] **Step 1: Add `map_exclude` to the settings.** Plan 2's `load_project` rejects unknown keys, so `[map] exclude` needs a field. Add `map_exclude: tuple[str, ...]` after `unguided` in `ProjectSettings`, read from `[map] exclude` as a list of relative paths without `..`, with default `()`. Add `exclude = []` under `[map]` in both seeded `project.toml` templates and in this repository's `.rapid-ship/project.toml`. In plan 2's `tests/devctl/test_devctl_settings.py`, add `map_exclude=()` to the expected defaults and a case where `exclude = ["../x"]` raises `SettingsError`. In plan 2's `tests/test_kit_contents.py`, the expected `map` table gains `"exclude": []`. Add `map_exclude=()` to `project_settings` in `tests/devctl/check_workspace.py`.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_map_coverage.py`:

```python
"""Map rules 2 (every maintained directory has a guide) and 3 (every guide is reachable)."""

from __future__ import annotations

from check_workspace import Workspace, project_settings
from devctl.check.map import MapStep, coverage_errors, guides, reachability_errors

HINT = "add an AGENTS.md guide, or list the directory under [map] unguided"


def layout(workspace: Workspace) -> list[str]:
    workspace.write("AGENTS.md", "[Docs](docs/AGENTS.md)\n")
    workspace.write("docs/AGENTS.md", "# Docs\n")
    workspace.write("tools/devctl/x.py", "")
    workspace.write("src/app/__init__.py", "")
    workspace.write("src/app/api/routes.py", "")
    workspace.write(".github/workflows/ci.yml", "on: push\n")
    return workspace.context().repo.files()


def test_top_level_and_source_root_children_need_guides(workspace: Workspace) -> None:
    files = layout(workspace)

    assert coverage_errors(files, project_settings(source_roots=("src/app",))) == [
        f"src/: {HINT}",
        f"src/app/api/: {HINT}",
        f"tools/: {HINT}",
    ]


def test_unguided_and_excluded_directories_need_no_guide(workspace: Workspace) -> None:
    files = layout(workspace)
    project = project_settings(
        source_roots=("src/app",), unguided=("src", "src/app/api"), map_exclude=("tools",)
    )

    assert coverage_errors(files, project) == []


def test_bytecode_directories_need_no_guide(workspace: Workspace) -> None:
    workspace.write("src/app/__init__.py", "")
    workspace.write("src/app/__pycache__/__init__.cpython-312.pyc", "")
    files = workspace.context().repo.files()

    assert "src/app/__pycache__/__init__.cpython-312.pyc" in files
    assert (
        coverage_errors(files, project_settings(source_roots=("src/app",), unguided=("src",))) == []
    )


def test_missing_source_root_is_reported(workspace: Workspace) -> None:
    files = layout(workspace)

    errors = coverage_errors(files, project_settings(source_roots=("src/other",)))

    assert "src/other: source root has no files; fix [map] source_roots" in errors


def test_every_guide_is_reachable_from_the_root(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "[Docs](docs/)\n")
    workspace.write("docs/AGENTS.md", "[Plans](plans/AGENTS.md)\n")
    workspace.write("docs/plans/AGENTS.md", "# Plans\n")
    workspace.write("docs/orphan/AGENTS.md", "# Orphan\n")
    context = workspace.context()
    root = context.repo.root
    found = guides(root, context.repo.files(), context.project)

    assert reachability_errors(root, found) == [
        "docs/orphan/AGENTS.md: not reachable by links from AGENTS.md; "
        "link it from its parent guide"
    ]


def test_missing_root_guide_is_reported(workspace: Workspace) -> None:
    workspace.write("docs/AGENTS.md", "# Docs\n")

    assert reachability_errors(workspace.root, ["docs/AGENTS.md"])[0].startswith("AGENTS.md:")


def test_excluded_template_guides_are_not_part_of_the_map(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    workspace.write("pkg/templates/common/AGENTS.md", "[Missing](nowhere.md)\n")

    result = MapStep().run(
        workspace.context(source_roots=(), unguided=("pkg",), map_exclude=("pkg/templates/common",))
    )

    assert result.status == "passed", result.details
```

Run: `uv run pytest tests/devctl/test_devctl_map_coverage.py -q`
Expected: `ImportError: cannot import name 'coverage_errors'`.

- [ ] **Step 3: Implement.** In `map.py`:
- `excluded(path, project)` is true when `path` equals an entry of `project.map_exclude` or starts with that entry plus `/`. `guides` drops excluded paths.
- `coverage_errors`: collect the first component of every path with at least two components. For each source root, report `"<root>: source root has no files; fix [map] source_roots"` when no file lies under it; otherwise collect `<root>/<child>` for every file at least one directory below it. Skip directories whose last component starts with `.` or is `__pycache__` (Python writes bytecode there on import), entries of `project.unguided` and excluded paths. Report `"<dir>/: add an AGENTS.md guide, or list the directory under [map] unguided"` for each remaining directory without `<dir>/AGENTS.md` in `files`, sorted.
- Spec rule 2 names tracked directories. `MapStep` passes `Repo.files()` instead, the files `git add -A` would commit, because `rs-setup` (plan 5) runs the check on a new project before it commits the Kit's files. Other generated directories therefore need a `.gitignore` entry; task 16 seeds one for new Python projects.
- `reachability_errors`: return `["AGENTS.md: add a root guide that links every other guide"]` when the root guide is not in `found`. Otherwise run a breadth-first search from `AGENTS.md`. A guide's edges are its `navigation_links` targets; an unreadable guide has none, because `link_errors` reports it. Normalise each target against the guide's directory with `posixpath.normpath` after unescaping and `unquote`, as `_link_error` does. A target reaches `X` when `X` is in `found` and the target is `X` itself or the directory holding `X`. Report each unreached guide, sorted, with the message in the test.

Add `coverage_errors(files, context.project)` and `reachability_errors(root, found)` to `MapStep.run`.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_map_links.py tests/devctl/test_devctl_map_coverage.py -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add -A rapid_ship/templates tools/devctl .rapid-ship tests/devctl tests/test_kit_contents.py
git commit -m "feat: require a guide per maintained directory and a reachable map

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: References, feature, Pattern and skill front matter, and Rules

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/references.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/markdown.py`, `check/map.py`, `rapid_ship/templates/common/tools/devctl/pyproject.toml`, `rapid_ship/templates/common/tools/devctl/uv.lock`
- Modify: `pyproject.toml`, `uv.lock` (dev dependencies `pyyaml`, `types-pyyaml`)
- Generated by sync: the vendored copies under `tools/devctl/`, including `pyproject.toml` and `uv.lock`; `.rapid-ship/kit.lock`
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/stacks/python.py` (test identities only; task 9 adds the steps)
- Create: `tests/devctl/test_devctl_references.py`, `tests/devctl/test_devctl_map_documents.py`, `tests/devctl/test_devctl_map_skills.py`
- Test, unchanged: plan 2's `tests/test_kit_contents.py`, whose devctl workspace test must stay green with PyYAML in the lock

**Interfaces:**
- Consumes: `all_steps` (for `check:`), `build_parser()` (for registered verbs).
- Produces:

```python
# devctl/check/markdown.py
@dataclass(frozen=True)
class ListItem:
    line: int  # line of the item's marker
    text: str  # the item's own text, without nested lists or code, joined by spaces


def rules_items(text: str) -> list[ListItem]: ...
def section(text: str, title: str, level: int) -> str | None: ...
def front_matter(
    text: str,
) -> object | None: ...  # None without front matter; ValueError if unclosed


# devctl/check/references.py
def resolve(reference: str, context: CheckContext) -> str | None: ...  # None when it resolves


# devctl/check/stacks/python.py
def is_test_file(path: str) -> bool: ...
def test_identities(
    source: str,
) -> list[str]: ...  # "test_x" or "TestA::test_x"; SyntaxError propagates


# devctl/check/map.py
def registered_verbs() -> frozenset[str]: ...
def feature_errors(context: CheckContext, files: Sequence[str]) -> list[str]: ...
def pattern_errors(context: CheckContext, files: Sequence[str]) -> list[str]: ...
def rule_errors(context: CheckContext, found: Sequence[str]) -> list[str]: ...
def skill_errors(
    root: Path, files: Sequence[str]
) -> list[str]: ...  # map rule 7, front-matter half
```

The front matter formats are the ones plan 2 seeds in `docs/features/README.md` and `docs/patterns/README.md` (plan 2, task 6), and the index's front matter table. This task owns the check, so `entry_points` must be a non-empty list; the index's resolved disagreements have plan 2's README row say the same. The skill row is the front-matter half of spec map rule 7; task 3 wrote the alias half.

| File | Front matter |
| --- | --- |
| `docs/features/*.md` except `README.md` | `purpose`: non-empty text. `entry_points`: non-empty list of existing paths. `data`: list of existing paths, possibly empty. `observe`: non-empty text. `reproduce`: one `./devctl <verb> ...` command whose verb is registered |
| `docs/patterns/*.md` except `README.md` | `reference`: an existing path. `enforced_by`: non-empty list of references that resolve |
| `.agents/skills/<name>/SKILL.md`, for Kit and project skills alike | `name`: equals `<name>`. `description`: non-empty text |

- [ ] **Step 1: Add PyYAML, regenerate devctl's lock and re-vendor.** `uv add` rewrites the template's `uv.lock`; `sync` copies it and `pyproject.toml` to `tools/devctl/`. `--no-sync` only stops uv from creating a virtual environment in the template directory, which nothing there needs. One left there would not reach the Kit: plan 2's `_layer` skips `.venv` and every path git does not keep.

```bash
uv add --no-sync --project rapid_ship/templates/common/tools/devctl "pyyaml>=6.0.3,<7"
uv add --dev "pyyaml>=6.0.3,<7" "types-pyyaml>=6.0.12.20260906"
uv lock --check --project rapid_ship/templates/common/tools/devctl
uv run rapid-ship sync --in-place
uv run pytest tests/test_kit_contents.py -q
```

Expected: `uv lock --check` exits 0. The template's `pyproject.toml` lists `pyyaml>=6.0.3,<7` as devctl's only new dependency, and its `uv.lock` holds `pyyaml` beside `devctl`. The root `uv.lock` changes too. `sync` updates the vendored `tools/devctl/pyproject.toml` and `uv.lock` to match the template. `tests/test_kit_contents.py` passes, including plan 2's `test_devctl_is_its_own_uv_workspace_and_its_versions_agree`.

- [ ] **Step 2: Write the failing reference tests.** Create `tests/devctl/test_devctl_references.py`:

```python
"""Each reference kind in spec section 5 resolves only when its target exists."""

from __future__ import annotations

import pytest
from check_workspace import Workspace
from devctl.check.references import resolve

PYPROJECT = """
[tool.ruff.lint]
select = ["E", "S"]
ignore = ["S101"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"os.environ".msg = "Read settings through app.settings"

[tool.importlinter]
root_packages = ["app"]

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = ["app.api", "app.core"]

[tool.mypy]
files = ["src", "tests"]
exclude = ["^src/app/generated/"]
"""

TESTS = """
def test_top(): pass
class TestCore:
    def test_runs(self): pass
"""


@pytest.mark.parametrize(
    ("reference", "resolves"),
    [
        ("check:map", True),
        ("check:nope", False),
        ("ruff:S603", True),
        ("ruff:S101", False),
        ("ruff:F401", False),
        ("banned:os.environ", True),
        ("banned:os.getenv", False),
        ("contract:layers", True),
        ("contract:missing", False),
        ("type:src/app/core.py", True),
        ("type:src/app/generated/x.py", False),
        ("type:scripts/run.py", False),
        ("type:src/app/absent.py", False),
        ("test:tests/test_core.py::TestCore::test_runs", True),
        ("test:tests/test_core.py::test_top", True),
        ("test:tests/test_core.py::test_absent", False),
        ("nonsense", False),
        ("lint:E501", False),
    ],
)
def test_python_references(workspace: Workspace, reference: str, resolves: bool) -> None:
    workspace.write("pyproject.toml", PYPROJECT)
    workspace.write("src/app/core.py", "")
    workspace.write("src/app/generated/x.py", "")
    workspace.write("scripts/run.py", "")
    workspace.write("tests/test_core.py", TESTS)

    reason = resolve(reference, workspace.context())

    assert (reason is None) is resolves, reason
    if reason is not None:
        assert reference in reason


def test_python_only_kinds_do_not_resolve_for_the_neutral_stack(workspace: Workspace) -> None:
    workspace.write("pyproject.toml", PYPROJECT)

    reason = resolve("ruff:S603", workspace.context(stack="neutral"))

    assert reason == "ruff:S603: unknown reference kind ruff for the neutral stack"
```

- [ ] **Step 3: Write the failing map document tests.** Create `tests/devctl/test_devctl_map_documents.py`:

```python
"""Map rules 4-6: feature files, Pattern files and Rules bullets."""

from __future__ import annotations

from check_workspace import Workspace
from devctl.check.map import feature_errors, guides, pattern_errors, rule_errors
from devctl.check.markdown import rules_items

FEATURE = """---
purpose: Sign users in
entry_points: [src/app/auth.py]
data: [src/app/models.py]
observe: The auth.login log line with the user ID.
reproduce: ./devctl check --tier fast
---
# Sign-in
"""


def features(workspace: Workspace) -> list[str]:
    context = workspace.context()
    return feature_errors(context, context.repo.files())


def test_valid_feature_and_readme_pass(workspace: Workspace) -> None:
    workspace.write("src/app/auth.py", "")
    workspace.write("src/app/models.py", "")
    workspace.write("docs/features/README.md", "# Feature files\n")
    workspace.write("docs/features/sign-in.md", FEATURE)

    assert features(workspace) == []


def test_feature_without_front_matter_fails(workspace: Workspace) -> None:
    workspace.write("docs/features/sign-in.md", "# Sign-in\n")

    assert features(workspace) == [
        "docs/features/sign-in.md: no front matter; start the file with --- and the keys "
        "purpose, entry_points, data, observe and reproduce"
    ]


def test_feature_names_missing_path_missing_key_and_unknown_verb(workspace: Workspace) -> None:
    workspace.write(
        "docs/features/sign-in.md",
        "---\npurpose: Sign in\nentry_points: [src/app/gone.py]\ndata: []\n"
        "reproduce: ./devctl seed-demo\n---\n",
    )

    assert features(workspace) == [
        "docs/features/sign-in.md: entry_points names src/app/gone.py, which does not exist",
        "docs/features/sign-in.md: observe is missing or empty",
        "docs/features/sign-in.md: reproduce runs ./devctl seed-demo; seed-demo is not a devctl verb",
    ]


def test_feature_needs_at_least_one_entry_point(workspace: Workspace) -> None:
    workspace.write("src/app/models.py", "")
    workspace.write("docs/features/sign-in.md", FEATURE.replace("[src/app/auth.py]", "[]"))

    assert features(workspace) == ["docs/features/sign-in.md: entry_points is missing or empty"]


def test_unclosed_or_invalid_front_matter_fails(workspace: Workspace) -> None:
    workspace.write("docs/features/a.md", "---\npurpose: x\n")
    workspace.write("docs/features/b.md", "---\n- a list\n---\n")

    assert features(workspace) == [
        "docs/features/a.md: front matter is not closed with ---",
        "docs/features/b.md: front matter must be a mapping",
    ]


def test_pattern_reference_and_enforcement(workspace: Workspace) -> None:
    workspace.write("src/app/settings.py", "")
    workspace.write(
        "docs/patterns/settings.md",
        "---\nreference: src/app/settings.py\nenforced_by: [check:map]\n---\n",
    )
    workspace.write(
        "docs/patterns/empty.md", "---\nreference: src/app/settings.py\nenforced_by: []\n---\n"
    )
    workspace.write(
        "docs/patterns/broken.md",
        "---\nreference: src/app/gone.py\nenforced_by: [check:nope]\n---\n",
    )
    context = workspace.context()

    errors = pattern_errors(context, context.repo.files())

    assert errors == [
        "docs/patterns/broken.md: reference names src/app/gone.py, which does not exist",
        "docs/patterns/broken.md: check:nope: no devctl check step is named nope",
        "docs/patterns/empty.md: enforced_by is missing or empty",
    ]


GUIDE = """# Root

Some text.

## Rules

- Read settings through `app.settings`. enforced by: check:map
  - This nested note belongs to the rule above.
- Keep handlers thin; the Reviewer checks this
  advisory
- Run the checks before pushing:

  ~~~sh
  - this dash is code, not a rule
  ~~~

  advisory
1. Numbered rules count too. enforced by: `check:map`
- Forgot the marker.
- Points nowhere. enforced by: check:nope

Closing paragraph after the list.

## Other

- Not a rule.
"""


def test_rules_items_skip_nested_lists_and_code() -> None:
    assert [(item.line, item.text) for item in rules_items(GUIDE)] == [
        (7, "Read settings through `app.settings`. enforced by: check:map"),
        (9, "Keep handlers thin; the Reviewer checks this advisory"),
        (11, "Run the checks before pushing: advisory"),
        (18, "Numbered rules count too. enforced by: `check:map`"),
        (19, "Forgot the marker."),
        (20, "Points nowhere. enforced by: check:nope"),
    ]


def test_every_rule_ends_with_a_resolving_marker(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", GUIDE)
    context = workspace.context()
    found = guides(context.repo.root, context.repo.files(), context.project)

    assert rule_errors(context, found) == [
        "AGENTS.md:19: end the rule with 'enforced by: <reference>' or 'advisory'",
        "AGENTS.md:20: check:nope: no devctl check step is named nope",
    ]
```

Create `tests/devctl/test_devctl_map_skills.py`:

```python
"""Map rule 7, front-matter half: each SKILL.md names its directory and describes itself."""

from __future__ import annotations

import pytest
from check_workspace import Workspace, skill_text
from devctl.check.map import MapStep, skill_errors


def add_skill(workspace: Workspace, name: str, text: str) -> None:
    workspace.write(f".agents/skills/{name}/SKILL.md", text)
    workspace.link(f".claude/skills/{name}", f"../../.agents/skills/{name}")


def errors(workspace: Workspace) -> list[str]:
    context = workspace.context()
    return skill_errors(context.repo.root, context.repo.files())


def test_a_project_authored_skill_passes(workspace: Workspace) -> None:
    workspace.write("AGENTS.md", "# Root\n")
    add_skill(workspace, "rs-tdd", skill_text("rs-tdd"))  # as the Kit vendors it
    add_skill(workspace, "release-notes", skill_text("release-notes"))  # not in the lock

    result = MapStep().run(workspace.context(source_roots=()))

    assert result.status == "passed", result.details


def test_skill_name_must_match_its_directory(workspace: Workspace) -> None:
    # An unpatched upstream fork: Claude Code would register /tdd, not /rs-tdd.
    add_skill(workspace, "rs-tdd", skill_text("tdd"))

    assert errors(workspace) == [
        ".agents/skills/rs-tdd/SKILL.md: name must be rs-tdd, the directory name"
    ]


@pytest.mark.parametrize(
    "text", ["---\nname: notes\n---\n", "---\nname: notes\ndescription: '  '\n---\n"]
)
def test_skill_description_must_not_be_empty(workspace: Workspace, text: str) -> None:
    add_skill(workspace, "notes", text)

    assert errors(workspace) == [".agents/skills/notes/SKILL.md: description is missing or empty"]


def test_skill_without_front_matter_fails(workspace: Workspace) -> None:
    add_skill(workspace, "notes", "# Notes\n")

    assert errors(workspace) == [
        ".agents/skills/notes/SKILL.md: no front matter; start the file with --- "
        "and the keys name and description"
    ]
```

A skill directory without `SKILL.md` is task 3's `test_skill_directory_without_skill_md_fails`; `skill_errors` skips it, so the map reports it once.

Run: `uv run pytest tests/devctl/test_devctl_references.py tests/devctl/test_devctl_map_documents.py tests/devctl/test_devctl_map_skills.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.references'`, and `ImportError: cannot import name 'skill_errors'`.

- [ ] **Step 4: Implement `stacks/python.py` test identities.**

```python
def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def test_identities(source: str) -> list[str]:
    """Pytest's default names: test* functions, and test* methods in Test* classes."""
    return list(_tests(ast.parse(source).body, ""))


def _tests(body: Sequence[ast.stmt], prefix: str) -> Iterator[str]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            yield prefix + node.name
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from _tests(node.body, f"{prefix}{node.name}::")
```

- [ ] **Step 5: Implement `references.py`.** `resolve` splits on the first `:`; a missing kind or value returns `"<reference>: write <kind>:<value>"`. Kinds:
- `check:<step>` resolves when a step of that name is in `all_steps(context.project)` (imported inside the function, because `devctl.check` imports this module). Otherwise: `"check:<step>: no devctl check step is named <step>"`.
- `test:<path>::<name>`: the file must exist. For the Python stack, `<name>` must be in `test_identities` of the file; a file that does not parse does not resolve. For the neutral stack, `<name>` must occur in the file as a whole word.
- Python stack only, read from `pyproject.toml` with `tomllib`: `ruff:<code>` resolves when the longest `select` plus `extend-select` prefix of the code (with `ALL` as a zero-length prefix, and Ruff's default `["E4", "E7", "E9", "F"]` when `select` is absent) is longer than the longest `ignore` plus `extend-ignore` prefix; ignore wins ties. Read `[tool.ruff.lint]`, falling back to `[tool.ruff]`. `banned:<member>` resolves when `<member>` is a key of `[tool.ruff.lint.flake8-tidy-imports.banned-api]`. `contract:<name>` resolves when an entry of `[[tool.importlinter.contracts]]` has that `name`. `type:<path>` resolves when the file exists, `<path>` equals or lies under an entry of `[tool.mypy] files`, and no `[tool.mypy] exclude` pattern matches it with `re.search`.
- A Python-only kind on the neutral stack returns `"<reference>: unknown reference kind <kind> for the neutral stack"`. An unknown kind returns `"<reference>: unknown reference kind <kind>"`. A missing or invalid `pyproject.toml` makes Python kinds fail with a reason that names the file.

- [ ] **Step 6: Implement `front_matter`, `section` and `rules_items` in `markdown.py`.**

```python
def front_matter(text: str) -> object | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            return yaml.safe_load("\n".join(lines[1:index]))  # yaml.YAMLError propagates
    raise ValueError("front matter is not closed with ---")


_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_ITEM = re.compile(r"^(?P<indent> *)(?:[-*+]|\d{1,9}[.)])[ \t]+(?P<text>\S.*)$")


def _headings(text: str) -> list[tuple[int, int, str]]:
    """(line index, level, title) for each ATX heading outside fenced code."""
    found = []
    for index, line in enumerate(without_fences(text).splitlines()):
        if match := _HEADING.match(line):
            found.append((index, len(match.group(1)), (match.group(2) or "").strip()))
    return found


def section(text: str, title: str, level: int) -> str | None:
    lines = text.splitlines()
    marks = _headings(text)
    for position, (index, depth, name) in enumerate(marks):
        if depth == level and name == title:
            ends = [i for i, d, _ in marks[position + 1 :] if d <= level]
            return "\n".join(lines[index + 1 : ends[0] if ends else len(lines)])
    return None


class _RulesScanner:
    """Collect the top-level items of lists under a "Rules" heading.

    An item's text is its first line plus its own continuation lines. Nested list
    items and their continuation lines belong to the rule above but are not rules.
    Fenced code is blanked before scanning, so a list inside code is ignored.
    """

    def __init__(self) -> None:
        self.items: list[ListItem] = []
        self.rules_level: int | None = None
        self.base: int | None = None  # marker indent of this section's top-level items
        self.nested: int | None = None  # marker indent of the open nested item
        self.current: tuple[int, list[str]] | None = None
        self.blank = False

    def heading(self, level: int, title: str) -> None:
        self.close()
        if self.rules_level is not None and level <= self.rules_level:
            self.rules_level = None
        if title == "Rules":
            self.rules_level, self.base = level, None

    def line(self, number: int, text: str) -> None:
        if self.rules_level is None:
            return
        if not text.strip():
            self.blank = True
            return
        indent = len(text) - len(text.lstrip(" "))
        item = _ITEM.match(text)
        if item and (self.base is None or indent <= self.base):
            self.close()
            self.base = indent if self.base is None else self.base
            self.current = (number, [item.group("text").strip()])
        elif self.current is not None:
            self.continuation(indent, text, item is not None)
        self.blank = False

    def continuation(self, indent: int, text: str, is_item: bool) -> None:
        if self.current is None or self.base is None:
            return
        if is_item:
            self.nested = indent
        elif self.nested is not None and indent > self.nested:
            return
        elif self.blank and indent <= self.base:
            self.close()  # a paragraph after the list ends it
        else:
            self.nested = None
            self.current[1].append(text.strip())

    def close(self) -> None:
        if self.current is not None:
            self.items.append(ListItem(self.current[0], " ".join(self.current[1])))
        self.current, self.nested = None, None


def rules_items(text: str) -> list[ListItem]:
    scanner = _RulesScanner()
    for number, line in enumerate(without_fences(text).splitlines(), start=1):
        if heading := _HEADING.match(line):
            scanner.heading(len(heading.group(1)), (heading.group(2) or "").strip())
        else:
            scanner.line(number, line)
    scanner.close()
    return scanner.items
```

- [ ] **Step 7: Implement the map document rules.**
- `registered_verbs()` imports `build_parser` from `devctl.cli` inside the function. It returns the `choices` keys of the parser's `argparse._SubParsersAction`, which include the project verbs added by `devctl_project.register`.
- `feature_errors`: for each `.md` file under `docs/features/` except `docs/features/README.md`, call `front_matter`. `None` gives the "no front matter" message in the test; `ValueError` and `yaml.YAMLError` give `"<path>: <error>"`; a non-mapping gives `"<path>: front matter must be a mapping"`. Then check the keys in the order `purpose`, `entry_points`, `data`, `observe`, `reproduce`, with the types in this task's table. A key that is missing or of the wrong type gives `"<path>: <key> is missing or empty"`. An empty value gives the same message for every key except `data`, which may be `[]`. Each `entry_points` and `data` item must be a file or directory in the repository; otherwise `"<path>: <key> names <item>, which does not exist"`. `shlex.split` the `reproduce` command: its first word must be `./devctl`, otherwise `"<path>: reproduce must be a ./devctl command"`, and its second word a registered verb, otherwise `"<path>: reproduce runs <command>; <verb> is not a devctl verb"`.
- `pattern_errors`: the same loading for `docs/patterns/`, then `reference` must name an existing path and `enforced_by` must be a non-empty list whose items each `resolve`; an unresolved item reports `"<path>: <reason>"`.
- `rule_errors`: for each guide and each `rules_items` entry, match `_RULE_END` (below) against the item text. No match gives `"<guide>:<line>: end the rule with 'enforced by: <reference>' or 'advisory'"`; an unresolved reference gives `"<guide>:<line>: <reason>"`.
- `skill_errors`: for each name in task 3's `_skill_names(root, files, ".agents/skills")` whose `SKILL.md` is a file, load its front matter as `feature_errors` does, sharing one private loader that takes the key names for the "no front matter" message. `<path>` is `.agents/skills/<name>/SKILL.md`. A `name` that is not a string equal to `<name>` gives `"<path>: name must be <name>, the directory name"`. A `description` that is not a string, or is blank after `strip()`, gives `"<path>: description is missing or empty"`. Report skills in name order, a skill's `name` error before its `description` error. Kit and project skills follow the same rule, so the step never reads the lock.

```python
# The reference may be wrapped in backticks, as in "enforced by: `check:map`".
_RULE_END = re.compile(r"(?:^|\s)(?:enforced by: `?(?P<reference>[^\s`]+)`?|advisory)$")
```

Add `feature_errors`, `pattern_errors`, `rule_errors(context, found)` and `skill_errors(root, files)` to `MapStep.run`.

This repository's one skill until plan 5, `rapid-ship-engineering`, already has `name: rapid-ship-engineering` and a description in `rapid_ship/skills/rapid-ship-engineering/SKILL.md`. Plan 5 patches each forked skill's `name` to its `rs-` directory name.

- [ ] **Step 8: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl tests/test_kit_contents.py -q`
Expected: all pass.

- [ ] **Step 9: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock \
  pyproject.toml uv.lock tests/devctl
git commit -m "feat: check feature files, Patterns, skills and Rules in the devctl map

Every Rule ends with 'enforced by: <reference>' or 'advisory', and every
reference must name a check, test, Ruff rule, banned API, contract or
type-checked file that exists. Every skill's front matter names its
directory and has a description.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Kit step

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/kit.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`
- Create: `tests/devctl/test_devctl_kit_step.py`

**Interfaces:**
- Consumes: the lock format from spec section 3, which plan 2 extends with a `variables` table. devctl cannot import `rapid_ship.kit.lock`, because projects do not install rapid-ship, so it reads the TOML itself and ignores `variables`. A test writes a lock with plan 2's `write_lock(root, Lock(kit_version, stack, variables, entries))` and reads it here, so the two readers cannot drift.
- Consumes: `ProjectSettings.excluded`, `[kit] exclude` from `project.toml` as plan 2's `load_project` normalises it, and plan 2's `rapid_ship.kit.templates.is_excluded(path: str, excluded: Sequence[str]) -> bool`, which only the parity test imports. `[kit] exclude` is the only record of an exclusion; the lock carries no mark (index, "Kit exclusions and skill discovery"). `rapid-ship status` reads the same list, so the two agree.
- Produces:

```python
LOCK_PATH = ".rapid-ship/kit.lock"


class KitLockError(Exception): ...


def is_excluded(path: str, excluded: Sequence[str]) -> bool: ...  # devctl's copy of the CLI's
def managed_paths(root: Path, excluded: Sequence[str]) -> frozenset[str]: ...


class KitStep:
    name = "kit"
    tier: Tier = "fast"

    def run(self, context: CheckContext) -> StepResult: ...
```

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_kit_step.py`:

```python
"""The kit step: the lock is readable and every managed file that is not excluded is present."""

from __future__ import annotations

import pytest
from check_workspace import Workspace
from devctl.check.kit import KitLockError, KitStep, is_excluded, managed_paths
from devctl.settings import PROJECT, load_project
from rapid_ship.kit.lock import Lock, LockEntry, write_lock
from rapid_ship.kit.templates import is_excluded as cli_is_excluded

SKILL = ".agents/skills/rs-demo"


def lock(workspace: Workspace) -> None:
    write_lock(
        workspace.root,
        Lock(
            "0.2.0",
            "python",
            {"package": "app"},
            (
                LockEntry("devctl", "managed", "a" * 64, None, None),
                LockEntry(
                    ".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None
                ),
                LockEntry("AGENTS.md", "seeded", None, None, "b" * 64),
            ),
        ),
    )


def choices(path: str) -> str:
    """Spec section 5's kit row: the message names both choices."""
    return (
        f"rapid-ship sync --revert {path} restores it, "
        "and rapid-ship sync keeps the deletion as the project's own"
    )


def test_present_files_pass_and_managed_paths_are_read(workspace: Workspace) -> None:
    lock(workspace)
    workspace.write("devctl", "#!/bin/sh\n")
    workspace.write(".agents/skills/rs-tdd/SKILL.md", "# TDD\n")
    workspace.link(".claude/skills/rs-tdd", "../../.agents/skills/rs-tdd")

    assert KitStep().run(workspace.context()).status == "passed"
    assert managed_paths(workspace.root, ()) == frozenset({"devctl", ".claude/skills/rs-tdd"})


def test_missing_managed_file_and_link_fail(workspace: Workspace) -> None:
    lock(workspace)

    result = KitStep().run(workspace.context())

    assert result.status == "failed"
    assert sorted(result.details) == [
        f".claude/skills/rs-tdd: managed link is missing; {choices('.claude/skills/rs-tdd')}",
        f"devctl: managed file is missing; {choices('devctl')}",
    ]


def test_a_deleted_path_that_project_toml_excludes_is_not_required(workspace: Workspace) -> None:
    # The project deleted devctl and listed it under [kit] exclude; the lock still names it.
    lock(workspace)
    workspace.write(".agents/skills/rs-tdd/SKILL.md", "# TDD\n")
    workspace.link(".claude/skills/rs-tdd", "../../.agents/skills/rs-tdd")
    workspace.write(PROJECT, 'stack = "python"\n\n[kit]\nexclude = ["devctl"]\n')
    excluded = load_project(workspace.root).excluded

    assert KitStep().run(workspace.context(excluded=excluded)).status == "passed"
    assert managed_paths(workspace.root, excluded) == frozenset({".claude/skills/rs-tdd"})


def test_an_excluded_skill_directory_covers_its_link(workspace: Workspace) -> None:
    write_lock(
        workspace.root,
        Lock(
            "0.2.0",
            "python",
            {"package": "app"},
            (
                LockEntry("devctl", "managed", "a" * 64, None, None),
                LockEntry(".agents/skills/rs-tdd/SKILL.md", "managed", "c" * 64, None, None),
                LockEntry(
                    ".claude/skills/rs-tdd", "managed", None, "../../.agents/skills/rs-tdd", None
                ),
            ),
        ),
    )
    workspace.write("devctl", "#!/bin/sh\n")
    excluded = (".agents/skills/rs-tdd",)

    assert KitStep().run(workspace.context(excluded=excluded)).status == "passed"
    # The project owns an excluded file, so the exceptions and file-size steps scan it.
    assert managed_paths(workspace.root, excluded) == frozenset({"devctl"})


@pytest.mark.parametrize(
    ("path", "excluded", "expected"),
    [
        ("devctl", ("devctl",), True),
        ("devctl.md", ("devctl",), False),
        ("tools/devctl/devctl/cli.py", ("tools/devctl",), True),
        ("tools/devctl-extra/x.py", ("tools/devctl",), False),
        (f"{SKILL}/SKILL.md", (SKILL,), True),
        (".claude/skills/rs-demo", (SKILL,), True),
        (".claude/skills/rs-demo2", (SKILL,), False),
        (".claude/skills/rs-demo/notes.md", (SKILL,), False),
        (".claude/skills/rs-tdd", (".agents/skills",), True),
        (".claude/skills/rs-tdd", (".claude/skills/rs-tdd",), True),
        ("devctl", (), False),
    ],
)
def test_is_excluded_matches_the_cli(path: str, excluded: tuple[str, ...], expected: bool) -> None:
    # devctl cannot import rapid_ship, so it keeps a copy; this keeps the two equal.
    assert (is_excluded(path, excluded), cli_is_excluded(path, excluded)) == (expected, expected)


@pytest.mark.parametrize("text", [None, "not toml [", 'kit_version = "1"\n'])
def test_unreadable_lock_fails(workspace: Workspace, text: str | None) -> None:
    if text is not None:
        workspace.write(".rapid-ship/kit.lock", text)

    assert KitStep().run(workspace.context()).status == "failed"
    with pytest.raises(KitLockError):
        managed_paths(workspace.root, ())
```

Run: `uv run pytest tests/devctl/test_devctl_kit_step.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.kit'`.

- [ ] **Step 2: Implement `kit.py`.** `_entries(root)` reads `LOCK_PATH` with `tomllib` and returns each `[[file]]` table as a frozen `_LockFile(path, kind, sha256, link)`. It raises `KitLockError(f"{LOCK_PATH}: {reason}")` when the file is missing, is not TOML, lacks a string `kit_version` or a `stack` of `python` or `agnostic`, or has a `[[file]]` without a string `path` and a `kind` of `managed` or `seeded`, or a managed entry with neither `sha256` nor `link`. It reads no exclusion from the lock. `is_excluded` copies plan 2's, because devctl cannot import `rapid_ship`:

```python
def is_excluded(path: str, excluded: Sequence[str]) -> bool:
    """A copy of rapid_ship.kit.templates.is_excluded; test_is_excluded_matches_the_cli pins it.

    True when path is an entry of [kit] exclude or lies below one. Excluding a skill
    directory also excludes its .claude/skills link.
    """
    parts = PurePosixPath(path).parts
    link = len(parts) == 3 and parts[:2] == (".claude", "skills")
    return (link and _covered(f".agents/skills/{parts[2]}", excluded)) or _covered(path, excluded)


def _covered(path: str, excluded: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(f"{entry}/") for entry in excluded)
```

`managed_paths(root, excluded)` returns the managed paths for which `is_excluded` is false. `KitStep.run` returns `failed(name, str(error))` on `KitLockError` (spec section 5: the kit step fails when the lock is unreadable). Otherwise it skips each entry that `is_excluded(entry.path, context.project.excluded)` covers and reports, in lock order, each other managed `link` entry that is not a symlink and each managed file entry that is not a regular file, with the messages in the test. Add `KitStep()` to `core_steps` after `MapStep()`.

Plan 4's `kit_summary` reads the lock through `_entries` and counts a path as excluded with `is_excluded` and `ProjectSettings.excluded`, as this step does.

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_kit_step.py -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_kit_step.py
git commit -m "feat: fail devctl check when the Kit lock or a managed file is missing

A path under [kit] exclude in project.toml is the project's own and is
not required. devctl keeps a copy of the CLI's is_excluded, and a parity
test holds the two equal.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Exceptions step

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/exceptions.py`, `check/stacks/neutral.py` (suppression patterns only; task 11 adds the steps)
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/stacks/python.py`, `check/__init__.py`
- Create: `tests/devctl/test_devctl_exceptions_step.py`

**Interfaces:**
- Consumes: `load_exceptions(root) -> list[ExceptionEntry]`, `SettingsError`, `managed_paths(root, excluded)`, `ProjectSettings.excluded`.
- Produces:

```python
# devctl/check/stacks/python.py
def comments(source: str) -> dict[int, str]: ...  # line -> comment text
def comment_rules(comment: str) -> list[str]: ...
def marker_rules(source: str) -> list[tuple[int, str]]: ...  # skip and xfail markers and calls
def autouse_fixtures(source: str) -> list[tuple[str, int]]: ...  # (name, decorator line)


# devctl/check/stacks/neutral.py
def text_rules(path: str, text: str) -> list[str]: ...


# devctl/check/exceptions.py
MARKER: re.Pattern[str]  # rs-exception:\s*(?P<id>EX-\d+)


@dataclass(frozen=True)
class SuppressedLine:
    path: str
    number: int
    rules: tuple[str, ...]  # suppressions that need an exception
    optional: tuple[str, ...]  # autouse fixtures: validated when marked, required only by diff
    markers: tuple[str, ...]


def scan(
    root: Path, files: Sequence[str], managed: frozenset[str], stack: str
) -> list[SuppressedLine]: ...
def normal_rule(rule: str) -> str: ...  # sorts the names after any "<tool>:" prefix
def exception_errors(
    lines: Sequence[SuppressedLine], entries: Sequence[ExceptionEntry]
) -> list[str]: ...


class ExceptionsStep:
    name = "exceptions"
    tier: Tier = "fast"

    def run(self, context: CheckContext) -> StepResult: ...
```

Suppressions and their rule strings. Several codes or names join sorted, separated by `,` (`E501,F401`, `zizmor:a,b`). `normal_rule` normalises an entry's `rule` the same way before comparison, keeping a `zizmor:` or `mypy:` prefix in front.

| Suppression | Where | Rule |
| --- | --- | --- |
| `# noqa`, `# noqa: A1, B2`, `# ruff: noqa`, `# flake8: noqa` | Python comments | the codes upper-cased, or `noqa` |
| `# type: ignore`, `# type: ignore[a, b]` | Python comments | the codes, or `type-ignore` |
| `# mypy: ignore-errors`, `# mypy: disable-error-code=...` | Python comments | `mypy:ignore-errors`, `mypy:disable-error-code` |
| `# pragma: no cover` | Python comments | `no-cover` |
| `pytest.mark.skip`, `skipif`, `xfail` (also `mark.*`) | Python syntax tree | `skip`, `skipif`, `xfail` |
| `pytest.skip()`, `pytest.xfail()`, `pytest.importorskip()` | Python syntax tree | `skip`, `xfail`, `importorskip` |
| `@pytest.fixture(autouse=True)` in `conftest.py` | Python syntax tree | `autouse`, required only by the diff step |
| gitleaks's inline allow comment | Python comments; every line of other text files | `gitleaks` |
| `# zizmor: ignore[a,b]` | `.yml` and `.yaml` lines | `zizmor:a,b` |

This table and the code in step 2 are the one definition of suppressions and their rule names. The index's suppressions table repeats this table. The rapid-ship CLI cannot import devctl, so plan 5's `rapid_ship/kit/adopt.py` copies the Python rows. It keeps these names: `_NOQA`, `_TYPE_IGNORE`, `_MYPY`, `_NO_COVER`, `_GITLEAKS_ALLOW`, `_SKIP_MARKS`, `_SKIP_CALLS`, `_codes` and `_dotted`. It also copies the logic of `comment_rules`, `marker_rules` and the gitleaks count in `text_rules`. Plan 5's `tests/devctl/test_devctl_adopt_rules.py` runs `scan` and `adopt` on one source and fails when they disagree. To change a rule, change it here first, then in `adopt.py`.

Files scanned: `Repo.files()` that exist as regular files, are not symlinks, decode as UTF-8 and are not in `managed_paths(root, context.project.excluded)`. A Kit file under `[kit] exclude` is the project's, so it is scanned. On the Python stack, `.py` and `.pyi` files use the Python rows; only comment tokens and the syntax tree count, so strings that mention a suppression do not. Every other file, and every file on the neutral stack, uses `text_rules` line by line. There a marker counts only on a line with a suppression, so documents that quote markers do not.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_exceptions_step.py`:

```python
"""The exceptions step: each suppression has exactly one listed, current exception."""

from __future__ import annotations

import pytest
from check_workspace import Workspace
from devctl.check.exceptions import ExceptionsStep, normal_rule
from devctl.check.steps import StepResult

ENTRY = """
[[exception]]
id = "{id}"
path = "{path}"
rule = "{rule}"
reason = "Runs the build tool with fixed arguments"
remove_when = "The build tool has a Python API"
"""
KIT_FILE_LOCK = (
    'kit_version = "0.2.0"\nstack = "python"\n\n[[file]]\n'
    'path = "tools/devctl/devctl/run.py"\nkind = "managed"\nsha256 = "' + "a" * 64 + '"\n'
)


def setup(workspace: Workspace, source: str, *entries: tuple[str, str, str]) -> StepResult:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write("src/app/run.py", source)
    text = "".join(ENTRY.format(id=i, path=p, rule=r) for i, p, r in entries)
    workspace.write(".rapid-ship/exceptions.toml", text)
    return ExceptionsStep().run(workspace.context())


def test_marked_suppression_with_entry_passes(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "import subprocess\nsubprocess.run(['make'])  # noqa: S603  # rs-exception: EX-1\n",
        ("EX-1", "src/app/run.py", "S603"),
    )

    assert result.status == "passed", result.details


def test_unmarked_suppression_fails(workspace: Workspace) -> None:
    result = setup(workspace, "x = 1  # type: ignore[assignment]\n")

    assert result.details == (
        "src/app/run.py:1: suppression assignment needs '# rs-exception: EX-<n>' "
        "and an entry in .rapid-ship/exceptions.toml",
    )


def test_stale_entry_fails(workspace: Workspace) -> None:
    result = setup(workspace, "x = 1\n", ("EX-1", "src/app/run.py", "S603"))

    assert result.details == ("EX-1 is stale: no suppression carries it; delete the entry",)


def test_id_used_twice_fails(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "a = 1  # noqa: E501  # rs-exception: EX-1\nb = 2  # noqa: E501  # rs-exception: EX-1\n",
        ("EX-1", "src/app/run.py", "E501"),
    )

    assert "EX-1 is used on 2 lines; each ID is used once" in result.details


def test_marker_for_another_path_or_rule_fails(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "a = 1  # noqa: E501  # rs-exception: EX-1\nb = 2  # noqa: E501  # rs-exception: EX-2\n",
        ("EX-1", "src/app/other.py", "E501"),
        ("EX-2", "src/app/run.py", "S603"),
    )

    assert "src/app/run.py:1: EX-1 names src/app/other.py, not this file" in result.details
    assert (
        "src/app/run.py:2: EX-2 is for rule S603, which is not suppressed on this line"
        in result.details
    )


def test_unknown_id_fails(workspace: Workspace) -> None:
    result = setup(workspace, "a = 1  # noqa: E501  # rs-exception: EX-9\n")

    assert "src/app/run.py:1: EX-9 is not in .rapid-ship/exceptions.toml" in result.details


def test_invalid_exceptions_file_blocks_the_step(workspace: Workspace) -> None:
    # Plan 2's load_exceptions rejects blank fields, malformed IDs and repeated IDs.
    result = setup(
        workspace, "x = 1\n", ("EX-1", "src/app/run.py", "E501"), ("EX-1", "src/app/run.py", "S603")
    )

    assert result.status == "blocked"
    assert "EX-1" in result.details[0]


def test_skip_markers_and_calls_are_suppressions(workspace: Workspace) -> None:
    result = setup(
        workspace,
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_a():\n"
        "    pytest.skip('later')\n",
    )

    assert [d.split(":")[1] for d in result.details] == ["2", "4"]


def test_strings_and_kit_files_are_not_suppressions(workspace: Workspace) -> None:
    workspace.write("tools/devctl/devctl/run.py", "x = 1  # noqa: E501\n")
    workspace.write(".rapid-ship/kit.lock", KIT_FILE_LOCK)
    workspace.write("src/app/run.py", "TEXT = '# noqa: E501'\n")
    workspace.write("docs/notes.md", "Write `# noqa: S603  # rs-exception: EX-<n>`.\n")
    workspace.write(".rapid-ship/exceptions.toml", "")

    assert ExceptionsStep().run(workspace.context()).status == "passed"


def test_a_kit_file_under_kit_exclude_is_scanned(workspace: Workspace) -> None:
    # [kit] exclude lists tools/devctl, so the project owns the file and its suppressions.
    workspace.write("tools/devctl/devctl/run.py", "x = 1  # noqa: E501\n")
    workspace.write(".rapid-ship/kit.lock", KIT_FILE_LOCK)
    workspace.write(".rapid-ship/exceptions.toml", "")

    result = ExceptionsStep().run(workspace.context(excluded=("tools/devctl",)))

    assert result.details == (
        "tools/devctl/devctl/run.py:1: suppression E501 needs '# rs-exception: EX-<n>' "
        "and an entry in .rapid-ship/exceptions.toml",
    )


def test_workflow_ignore_comment_needs_an_exception(workspace: Workspace) -> None:
    workspace.write(
        ".github/workflows/ci.yml", "permissions: {}  # zizmor: ignore[excessive-permissions]\n"
    )

    result = setup(workspace, "x = 1\n")

    assert result.details == (
        ".github/workflows/ci.yml:1: suppression zizmor:excessive-permissions needs "
        "'# rs-exception: EX-<n>' and an entry in .rapid-ship/exceptions.toml",
    )


def test_workflow_ignore_with_several_names_matches_its_entry(workspace: Workspace) -> None:
    workspace.write(
        ".github/workflows/ci.yml",
        "permissions: write-all  # zizmor: ignore[excessive-permissions, artipacked]"
        "  # rs-exception: EX-1\n",
    )

    result = setup(
        workspace,
        "x = 1\n",
        ("EX-1", ".github/workflows/ci.yml", "zizmor:artipacked,excessive-permissions"),
    )

    assert result.status == "passed", result.details


@pytest.mark.parametrize(
    ("rule", "normal"),
    [
        ("S607, S603", "S603,S607"),
        ("zizmor:excessive-permissions,artipacked", "zizmor:artipacked,excessive-permissions"),
        ("zizmor: unpinned-uses, artipacked", "zizmor:artipacked,unpinned-uses"),
        ("mypy:disable-error-code", "mypy:disable-error-code"),
        ("arg-type,call-arg", "arg-type,call-arg"),
        ("file-size", "file-size"),
    ],
)
def test_normal_rule_sorts_the_names_after_a_tool_prefix(rule: str, normal: str) -> None:
    assert normal_rule(rule) == normal


def test_marked_autouse_fixture_is_validated_unmarked_one_is_left_to_diff(
    workspace: Workspace,
) -> None:
    workspace.write(
        "tests/conftest.py",
        "import pytest\n"
        "@pytest.fixture(autouse=True)  # rs-exception: EX-1\n"
        "def fake_clock(): pass\n"
        "@pytest.fixture(autouse=True)\n"
        "def other(): pass\n",
    )

    result = setup(workspace, "x = 1\n", ("EX-1", "tests/conftest.py", "autouse"))

    assert result.status == "passed", result.details
```

Run: `uv run pytest tests/devctl/test_devctl_exceptions_step.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.exceptions'`.

- [ ] **Step 2: Implement the Python and neutral scanners.** In `stacks/python.py`:

```python
# rapid_ship/kit/adopt.py copies these patterns, comment_rules, marker_rules, _codes and
# _dotted, because rapid-ship cannot import devctl. tests/devctl/test_devctl_adopt_rules.py
# fails when the copies differ.
_NOQA = re.compile(
    r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b(?::\s*(?P<codes>[A-Za-z]+[0-9]+(?:[\s,]+[A-Za-z]+[0-9]+)*))?",
    re.IGNORECASE,
)
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b(?:\[(?P<codes>[^\]]*)\])?")
_MYPY = re.compile(r"#\s*mypy:\s*(?P<setting>ignore-errors|disable-error-code)")
_NO_COVER = re.compile(r"#\s*pragma:\s*no\s+cover", re.IGNORECASE)
_SKIP_MARKS = frozenset({"skip", "skipif", "xfail"})
_SKIP_CALLS = frozenset({"skip", "xfail", "importorskip"})


def comments(source: str) -> dict[int, str]:
    """Comment text by line. Source that does not tokenize falls back to text after '#'."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        return {t.start[0]: t.string for t in tokens if t.type == tokenize.COMMENT}
    except (tokenize.TokenError, SyntaxError):
        lines = enumerate(source.splitlines(), start=1)
        return {number: line[line.index("#") :] for number, line in lines if "#" in line}


def comment_rules(comment: str) -> list[str]:
    rules = [_codes(m.group("codes"), upper=True) or "noqa" for m in _NOQA.finditer(comment)]
    rules += [_codes(m.group("codes")) or "type-ignore" for m in _TYPE_IGNORE.finditer(comment)]
    rules += [f"mypy:{m.group('setting')}" for m in _MYPY.finditer(comment)]
    rules += ["no-cover" for _ in _NO_COVER.finditer(comment)]
    return rules


def _codes(text: str | None, *, upper: bool = False) -> str:
    parts = [part for part in re.split(r"[\s,]+", text or "") if part]
    return ",".join(sorted(part.upper() if upper else part for part in parts))


def marker_rules(source: str) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _SKIP_MARKS:
            if _dotted(node.value) in ("pytest.mark", "mark"):
                found.append((node.lineno, node.attr))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _SKIP_CALLS and _dotted(node.func.value) == "pytest":
                found.append((node.lineno, node.func.attr))
    return found
```

`_dotted(node)` joins `Name` and `Attribute` chains such as `pytest.mark`, and returns `""` for anything else. `autouse_fixtures` walks function definitions and returns `(name, decorator.lineno)` for each decorator that is a call to `pytest.fixture` or `fixture` with the keyword `autouse=True`. A source that does not parse returns `[]`.

In `stacks/neutral.py`:

```python
# Split so that documents quoting this code do not contain gitleaks's allow comment.
# rapid_ship/kit/adopt.py copies _GITLEAKS_ALLOW.
_GITLEAKS_ALLOW = "gitleaks" + ":allow"
_ZIZMOR = re.compile(r"#\s*zizmor:\s*ignore\[(?P<names>[^\]]+)\]")


def text_rules(path: str, text: str) -> list[str]:
    rules = ["gitleaks"] * text.count(_GITLEAKS_ALLOW)
    if path.endswith((".yml", ".yaml")):
        for match in _ZIZMOR.finditer(text):
            names = sorted(name for name in re.split(r"[\s,]+", match.group("names")) if name)
            rules.append("zizmor:" + ",".join(names))
    return rules
```

Every rule these scanners return is already normal: `normal_rule(rule) == rule`.

- [ ] **Step 3: Implement `exceptions.py`.** `scan` builds one `SuppressedLine` for each line with a suppression, or, in a Python file, with a marker, in path then line order. When `stack` is `"python"`, for a `.py` or `.pyi` file the rules on line *n* are `comment_rules(comment)`, `text_rules(path, comment)` and the `marker_rules` on *n*, in that order. The optional rules are `autouse` for each `autouse_fixtures` decorator on *n* when the file is named `conftest.py`. The markers are the `MARKER` IDs in the line's comment. For every other file, the rules are `text_rules(path, line)` and the markers are the line's IDs. The pairing rule:

```python
def exception_errors(
    lines: Sequence[SuppressedLine], entries: Sequence[ExceptionEntry]
) -> list[str]:
    # load_exceptions has already checked the fields, the ID format and uniqueness.
    by_id = {entry.id: entry for entry in entries}
    errors: list[str] = []
    uses = Counter(marker for line in lines for marker in line.markers)
    for line in lines:
        errors += _line_errors(line, by_id)
    errors += [f"{i} is used on {n} lines; each ID is used once" for i, n in uses.items() if n > 1]
    errors += [
        f"{entry.id} is stale: no suppression carries it; delete the entry"
        for entry in by_id.values()
        if entry.rule != "file-size" and uses[entry.id] == 0
    ]
    return errors


def _line_errors(line: SuppressedLine, by_id: Mapping[str, ExceptionEntry]) -> list[str]:
    where = f"{line.path}:{line.number}"
    required, optional = list(line.rules), list(line.optional)
    errors: list[str] = []
    for marker in line.markers:
        entry = by_id.get(marker)
        if entry is None:
            errors.append(f"{where}: {marker} is not in .rapid-ship/exceptions.toml")
        elif entry.path != line.path:
            errors.append(f"{where}: {marker} names {entry.path}, not this file")
        elif (rule := normal_rule(entry.rule)) in required:
            required.remove(rule)
        elif rule in optional:
            optional.remove(rule)
        else:
            errors.append(
                f"{where}: {marker} is for rule {entry.rule}, which is not suppressed on this line"
            )
    errors += [
        f"{where}: suppression {rule} needs '# rs-exception: EX-<n>' and an entry in "
        ".rapid-ship/exceptions.toml"
        for rule in required
    ]
    return errors
```

`normal_rule` keeps a tool prefix such as `zizmor:` in front and sorts only the names after it:

```python
def normal_rule(rule: str) -> str:
    """'S607, S603' -> 'S603,S607'; 'zizmor:b, a' -> 'zizmor:a,b'."""
    prefix, colon, names = rule.strip().rpartition(":")
    parts = sorted(part for part in re.split(r"[\s,]+", names) if part)
    return f"{prefix.strip()}{colon}{','.join(parts)}"
```

Splitting the whole rule on commas would sort the prefix with the names: `zizmor:b,a` would become `a,zizmor:b`, and the step would reject a correct entry. The zizmor cases in step 1 fail that way. Entry validation stays in plan 2's `load_exceptions`; a `SettingsError` from it blocks the step. `ExceptionsStep.run` loads the entries, `managed_paths(root, context.project.excluded)` and the files, returning `blocked` on `SettingsError`, `KitLockError` or `RepoError`. It calls `scan(root, files, managed, context.project.stack)`, then returns `failed` with `exception_errors`, or `passed`. Add `ExceptionsStep()` to `core_steps` between `MapStep()` and `KitStep()`.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_exceptions_step.py -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_exceptions_step.py
git commit -m "feat: require a listed exception for every suppression

Each rs-exception ID is used once; an entry no suppression carries fails
as stale, so removing one suppression cannot pay for another.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: File-size step

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/filesize.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`
- Create: `tests/devctl/test_devctl_filesize_step.py`

**Interfaces:**
- Consumes: `load_exceptions`, `managed_paths(root, excluded)`, `ProjectSettings.source_roots` and `.excluded`.
- Produces: `LINE_CAP = 500` and `class FileSizeStep` with `name = "file-size"` and `tier: Tier = "fast"`.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_filesize_step.py`:

```python
"""The file-size step: source files stay within the line cap unless excepted."""

from __future__ import annotations

from check_workspace import Workspace
from devctl.check.filesize import LINE_CAP, FileSizeStep
from devctl.check.steps import StepResult


def run(workspace: Workspace, exceptions: str = "", **project: object) -> StepResult:
    workspace.write(".rapid-ship/kit.lock", 'kit_version = "0.2.0"\nstack = "python"\n')
    workspace.write(".rapid-ship/exceptions.toml", exceptions)
    return FileSizeStep().run(workspace.context(**project))


FILE_SIZE = (
    '[[exception]]\nid = "EX-1"\npath = "src/app/big.py"\nrule = "file-size"\n'
    'reason = "Generated parser"\nremove_when = "The parser is generated at build time"\n'
)


def test_file_over_the_cap_fails(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n" * (LINE_CAP + 1))
    workspace.write("src/app/ok.py", "x = 1\n" * LINE_CAP)
    workspace.write("tests/test_long.py", "x = 1\n" * (LINE_CAP + 1))

    assert run(workspace).details == (
        "src/app/big.py: 501 lines exceeds the 500-line cap; "
        "split the file or add a file-size exception",
    )


def test_file_size_exception_allows_the_file(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n" * (LINE_CAP + 1))

    assert run(workspace, FILE_SIZE).status == "passed"


def test_exception_for_a_file_under_the_cap_is_stale(workspace: Workspace) -> None:
    workspace.write("src/app/big.py", "x = 1\n")

    assert run(workspace, FILE_SIZE).details == (
        "EX-1: src/app/big.py is within the 500-line cap or gone; delete this file-size exception",
    )


def test_no_source_roots_is_not_applicable(workspace: Workspace) -> None:
    assert run(workspace, source_roots=()).status == "not_applicable"
```

Run: `uv run pytest tests/devctl/test_devctl_filesize_step.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.filesize'`.

- [ ] **Step 2: Implement `filesize.py`.** With no source roots, return `not_applicable(name, "no [map] source_roots")`. Otherwise load the entries, `managed_paths(root, context.project.excluded)` and the files, returning `blocked` on their errors. Count `len(text.splitlines())` for each file under a source root that is a regular non-symlink file, is not in those managed paths (a Kit file under `[kit] exclude` counts), decodes as UTF-8 and, on the Python stack, ends in `.py` or `.pyi`. Fail each file over `LINE_CAP` without a `file-size` entry for its path, and each `file-size` entry whose path is not over the cap, with the messages in the tests, sorted by path. Add `FileSizeStep()` to `core_steps` between `ExceptionsStep()` and `KitStep()`.

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_filesize_step.py -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_filesize_step.py
git commit -m "feat: cap source files at 500 lines unless excepted

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Command steps and the Python tool steps

**Files:**
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/steps.py`, `check/stacks/python.py`, `check/__init__.py`
- Create: `tests/devctl/test_devctl_python_steps.py`

**Interfaces:**
- Consumes: `process.run_process` and `ProcessResult` (task 1). `steps.py` imports the module with `from devctl import process` and calls `process.run_process`, the index's convention, so a test that patches `devctl.process.run_process` sees every tool's argv.
- Produces, in `steps.py`:

```python
def run_tool(
    root: Path, argv: Sequence[str], timeout_seconds: float, env: Mapping[str, str] | None = None
) -> ProcessResult | None: ...  # None when argv[0] is not on PATH
def output_tail(result: ProcessResult, lines: int = 40) -> tuple[str, ...]: ...
def command_result(
    name: str, argv: Sequence[str], result: ProcessResult | None, failed_codes: frozenset[int]
) -> StepResult: ...


@dataclass
class CommandStep:  # not frozen: Step's members are settable
    name: str
    tier: Tier
    argv: tuple[str, ...]
    failed_codes: frozenset[int] = frozenset({1})
    timeout_seconds: float = 1800.0

    def run(self, context: CheckContext) -> StepResult: ...
```

- Produces, in `stacks/python.py`: `FORMAT`, `LINT`, `TYPES`, `CONTRACTS` and `TESTS`, each a `CommandStep`.

| Step | Tier | Command | Failed on | Blocked on |
| --- | --- | --- | --- | --- |
| format | fast | `uv run --locked ruff format --check .` | 1 | anything else, missing tool, timeout |
| lint | fast | `uv run --locked ruff check --output-format concise .` | 1 | same |
| types | full | `uv run --locked mypy` | 1 | same |
| contracts | full | `uv run --locked lint-imports` | 1 (lint-imports also uses 1 for its own errors) | same |
| tests | full | `uv run --locked pytest` | 1, 5 (no tests collected) | same |

`uv run` exits 2 with `Failed to spawn` when the project does not install the tool. This was observed with uv 0.11.0, and matches uv 0.13.1's source: the spawn error is an `anyhow` context error (`crates/uv-project-commands/src/run.rs:1283-1285`), which `crates/uv/src/lib.rs:3157-3167` maps to exit status 2. `--locked` keeps the old CI's `uv sync --locked` guarantee: a stale lock stops the step, with uv's message in the details.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_python_steps.py`:

```python
"""Python tool steps, run against a simulated uv."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from check_workspace import Workspace, fake_tool
from devctl.check.stacks.python import CONTRACTS, FORMAT, LINT, TESTS, TYPES
from devctl.check.steps import CommandStep


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def calls(tools: Path, name: str = "uv") -> list[dict[str, object]]:
    log = tools / f"{name}.log"
    return [json.loads(line) for line in log.read_text().splitlines()]


@pytest.mark.parametrize(
    ("step", "argv"),
    [
        (FORMAT, ["run", "--locked", "ruff", "format", "--check", "."]),
        (LINT, ["run", "--locked", "ruff", "check", "--output-format", "concise", "."]),
        (TYPES, ["run", "--locked", "mypy"]),
        (CONTRACTS, ["run", "--locked", "lint-imports"]),
        (TESTS, ["run", "--locked", "pytest"]),
    ],
)
def test_each_tool_runs_through_uv(
    workspace: Workspace, tools: Path, step: CommandStep, argv: list[str]
) -> None:
    fake_tool(tools, "uv", "sys.exit(0)")

    assert step.run(workspace.context()).status == "passed"
    assert calls(tools)[0]["argv"] == argv
    assert calls(tools)[0]["cwd"] == str(workspace.root)


@pytest.mark.parametrize(
    ("step", "code", "status"),
    [
        (LINT, 1, "failed"),
        (LINT, 2, "blocked"),
        (TESTS, 1, "failed"),
        (TESTS, 5, "failed"),
        (TESTS, 3, "blocked"),
    ],
)
def test_exit_codes_map_to_statuses(
    workspace: Workspace, tools: Path, step: CommandStep, code: int, status: str
) -> None:
    fake_tool(tools, "uv", f"print('tool output'); sys.exit({code})")

    result = step.run(workspace.context())

    assert result.status == status
    assert "tool output" in result.details


def test_missing_tool_is_blocked(
    workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert LINT.run(context).details == ("uv is not on PATH",)


def test_timeout_is_blocked(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "uv", "import time; time.sleep(30)")
    step = CommandStep("slow", "full", ("uv",), timeout_seconds=0.5)

    result = step.run(workspace.context())

    assert result.status == "blocked"
    assert result.details[0].startswith("timed out after")


def test_tools_get_a_scrubbed_environment(
    workspace: Workspace, tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_TOKEN", "must-not-pass")
    monkeypatch.setenv("UV_CACHE_DIR", str(tools / "cache"))
    fake_tool(tools, "uv", "sys.exit(0)")

    TYPES.run(workspace.context())

    environment = calls(tools)[0]["env"]
    assert "GH_TOKEN" not in environment
    assert "UV_CACHE_DIR" in environment
```

`fake_tool`'s body runs after `import json, os, pathlib, sys`, so `sys.exit` needs no import.

Run: `uv run pytest tests/devctl/test_devctl_python_steps.py -q`
Expected: `ImportError: cannot import name 'CONTRACTS'`.

- [ ] **Step 2: Implement.** In `steps.py`:

```python
def run_tool(
    root: Path, argv: Sequence[str], timeout_seconds: float, env: Mapping[str, str] | None = None
) -> ProcessResult | None:
    try:
        return process.run_process(
            argv, root, timeout_seconds, env={**tool_environment(), **(env or {})}
        )
    except FileNotFoundError:
        return None


def output_tail(result: ProcessResult, lines: int = 40) -> tuple[str, ...]:
    tail = tuple((result.stdout + result.stderr).splitlines()[-lines:])
    if result.stdout_truncated or result.stderr_truncated:
        return ("(output over 1 MiB was cut; the end may be missing)", *tail)
    return tail


def command_result(
    name: str, argv: Sequence[str], result: ProcessResult | None, failed_codes: frozenset[int]
) -> StepResult:
    if result is None:
        return blocked(name, f"{argv[0]} is not on PATH")
    if result.timed_out:
        return blocked(
            name, f"timed out after {result.duration_seconds:.0f} s", *output_tail(result)
        )
    if result.returncode == 0:
        return passed(name)
    if result.returncode in failed_codes:
        return failed(name, *output_tail(result))
    return blocked(name, f"{shlex.join(argv)} exited {result.returncode}", *output_tail(result))
```

`CommandStep.run` returns `command_result(self.name, self.argv, run_tool(context.repo.root, self.argv, self.timeout_seconds), self.failed_codes)`. Define the five steps in `stacks/python.py` with the commands in this task's table; `TESTS` passes `failed_codes=frozenset({1, 5})`. Make `core_steps` start with `[FORMAT, LINT]` and put `[TYPES, CONTRACTS, TESTS]` after `KitStep()`, both only when `project.stack == "python"`.

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_python_steps.py
git commit -m "feat: run ruff, mypy, import-linter and pytest as devctl check steps

A missing tool or a timeout blocks the step; it never passes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Audit step with pip-audit

**Files:**
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/stacks/python.py`, `check/__init__.py`
- Create: `tests/devctl/test_devctl_audit_step.py`

**Interfaces:**
- Consumes: `run_tool`, `command_result`.
- Produces: `PIP_AUDIT = "pip-audit==2.10.1"` and `class AuditStep` with `name = "audit"` and `tier: Tier = "full"`.

Spec section 5 names pip-audit as the Python audit tool, because `uv audit` is still experimental. The evidence, checked on 2026-10-14:
- uv 0.13.1, the latest release, still prints "`uv audit` is experimental and may change without warning" (`crates/uv-project-commands/src/audit.rs:64-68` at tag `0.13.1`), and its JSON output carries a separate experimental warning (`:72-76`).
- uv 0.11.0 and 0.11.1 exit 0 when vulnerabilities are found. With uv 0.11.0, a probe project locking `requests==2.25.0` printed "Found 26 known vulnerabilities" and exited 0. Tag `0.11.2` is the first whose audit returns `ExitStatus::Failure` on findings.
- In 0.13.1, user errors also exit 1 (`crates/uv/src/lib.rs:3146-3150`), so the exit code alone cannot tell findings from errors.

pip-audit 2.10.1 (released 2026-06-10) is stable and writes a documented JSON report. The step reads that report, not the exit code alone: a report with vulnerabilities is failed; no report, or a clean report with a non-zero exit, is blocked.

- [ ] **Step 1: Confirm the decision's facts are unchanged.**

Run: `uv --version; gh api repos/astral-sh/uv/releases/latest --jq .tag_name`
Run: `gh api "repos/astral-sh/uv/contents/crates/uv-project-commands/src/audit.rs?ref=$(gh api repos/astral-sh/uv/releases/latest --jq .tag_name)" --jq .content | base64 -d | grep -n "experimental"`
Expected: the latest release still prints the experimental warning. If it no longer does, keep pip-audit, which spec section 5 names, and record the change under Remaining limits for the owner.

Run: `curl -s https://pypi.org/pypi/pip-audit/2.10.1/json -o /dev/null -w "%{http_code}\n"`
Expected: `200`.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_audit_step.py`:

```python
"""The audit step, run against a simulated uv that stands in for export and pip-audit."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from check_workspace import Workspace, fake_tool
from devctl.check.stacks.python import AuditStep

UV = """
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
if args[0] == "export":
    pathlib.Path(args[args.index("--output-file") + 1]).write_text("requests==2.25.0\\n")
    sys.exit(int((here / "export.exit").read_text()) if (here / "export.exit").exists() else 0)
report = here / "report.json"
if report.exists():
    pathlib.Path(args[args.index("--output") + 1]).write_text(report.read_text())
sys.exit(int((here / "audit.exit").read_text()) if (here / "audit.exit").exists() else 0)
"""

CLEAN = {"dependencies": [{"name": "requests", "version": "2.32.5", "vulns": []}], "fixes": []}
VULNERABLE = {
    "dependencies": [
        {
            "name": "requests",
            "version": "2.25.0",
            "vulns": [{"id": "PYSEC-2023-74", "fix_versions": ["2.31.0"]}],
        }
    ],
    "fixes": [],
}


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    fake_tool(directory, "uv", UV)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def audit(workspace: Workspace, tools: Path, report: object | None, code: int) -> tuple[str, ...]:
    if report is not None:
        (tools / "report.json").write_text(json.dumps(report))
    (tools / "audit.exit").write_text(str(code))
    result = AuditStep().run(workspace.context())
    return (result.status, *result.details)


def test_clean_report_passes(workspace: Workspace, tools: Path) -> None:
    assert audit(workspace, tools, CLEAN, 0) == ("passed",)
    argv = [json.loads(line)["argv"] for line in (tools / "uv.log").read_text().splitlines()]
    assert argv[0][:4] == ["export", "--locked", "--format", "requirements-txt"]
    assert argv[1][:5] == ["tool", "run", "--from", "pip-audit==2.10.1", "pip-audit"]
    assert {"--require-hashes", "--disable-pip", "--strict"} <= set(argv[1])


def test_vulnerability_fails(workspace: Workspace, tools: Path) -> None:
    assert audit(workspace, tools, VULNERABLE, 1) == (
        "failed",
        "requests 2.25.0: PYSEC-2023-74 (fixed in 2.31.0)",
    )


@pytest.mark.parametrize(("report", "code"), [(None, 1), (CLEAN, 1), ("not a report", 0)])
def test_no_report_or_unexplained_exit_is_blocked(
    workspace: Workspace, tools: Path, report: object | None, code: int
) -> None:
    assert audit(workspace, tools, report, code)[0] == "blocked"


def test_failed_export_is_blocked(workspace: Workspace, tools: Path) -> None:
    (tools / "export.exit").write_text("2")

    assert audit(workspace, tools, CLEAN, 0)[0] == "blocked"
```

Run: `uv run pytest tests/devctl/test_devctl_audit_step.py -q`
Expected: `ImportError: cannot import name 'AuditStep'`.

- [ ] **Step 3: Implement `AuditStep.run`.** In a `tempfile.TemporaryDirectory(prefix="devctl-audit-")`:
1. Run `uv export --locked --format requirements-txt --all-groups --no-emit-project --no-emit-local --no-header --quiet --output-file <tmp>/requirements.txt` with a 300 s timeout. Anything but exit 0 returns `command_result(name, argv, result, frozenset())`, which is always blocked.
2. Run `uv tool run --from pip-audit==2.10.1 pip-audit --requirement <tmp>/requirements.txt --require-hashes --disable-pip --strict --progress-spinner off --format json --output <tmp>/audit.json` with a 600 s timeout. A missing `uv` or a timeout is blocked.
3. Read `audit.json`. A missing file, invalid JSON, or a value without a `dependencies` list is blocked: `"pip-audit wrote no readable report"` plus the output tail. Each vulnerability gives a failure detail `"<name> <version>: <id> (fixed in <versions>)"`, or `"... (no fix yet)"` when `fix_versions` is empty. With vulnerabilities, return `failed`. Without them, return `passed` when pip-audit exited 0; otherwise return blocked with the exit code and tail.

Add `AuditStep()` after `TESTS` in `core_steps`.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_audit_step.py -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_audit_step.py
git commit -m "feat: audit locked dependencies with pip-audit

uv audit is still experimental in uv 0.13.1, and uv 0.11.0 exits 0 with
known vulnerabilities, so the step reads pip-audit's JSON report.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Secrets and workflows steps

**Files:**
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/stacks/neutral.py`, `check/__init__.py`
- Create: `tests/devctl/test_devctl_neutral_steps.py`

**Interfaces:**
- Consumes: `run_tool`, `command_result`, `CheckContext.base`.
- Produces: `GITLEAKS_VERSION = "8.30.1"`, `ZIZMOR = "zizmor==1.30.1"`, `class SecretsStep` (`name = "secrets"`, `tier: Tier = "full"`) and `class WorkflowsStep` (`name = "workflows"`, `tier: Tier = "full"`).

Commands and exit codes, checked against the pinned sources: gitleaks `cmd/root.go:76` (`--exit-code`), `:493-499` (exit 1 on error, `exitCode` on findings), `cmd/git.go:17-19`; zizmor 1.30.1 `docs/usage.md:563-578`.

| Step | Command | Passed | Failed | Not applicable | Blocked |
| --- | --- | --- | --- | --- | --- |
| secrets | `gitleaks git --no-banner --redact --exit-code 10 --report-format json --report-path <tmp> [--log-opts=<base>..HEAD] .` | 0 | 10 | — | gitleaks missing, any other code, timeout |
| workflows | `uv tool run --from zizmor==1.30.1 zizmor --offline --no-progress --strict-collection --format plain .` | 0 | 11-14 | 3 (no inputs) | any other code, timeout |

Without a base (push, schedule, local run with no `origin`), gitleaks scans the whole history. Uncommitted changes are not scanned; CI scans every commit of the change.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_neutral_steps.py`:

```python
"""Secrets and workflows steps, run against simulated gitleaks and uv."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from check_workspace import Workspace, fake_tool
from devctl.check.stacks.neutral import SecretsStep, WorkflowsStep

GITLEAKS = """
args = sys.argv[1:]
here = pathlib.Path(__file__).parent
report = here / "report.json"
if report.exists():
    pathlib.Path(args[args.index("--report-path") + 1]).write_text(report.read_text())
sys.exit(int((here / "gitleaks.exit").read_text()))
"""


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def argv(tools: Path, name: str) -> list[str]:
    return json.loads((tools / f"{name}.log").read_text().splitlines()[0])["argv"]


def test_secrets_scans_the_change_and_reports_findings(workspace: Workspace, tools: Path) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text("10")
    (tools / "report.json").write_text(
        json.dumps(
            [
                {
                    "RuleID": "aws-access-token",
                    "File": "README.md",
                    "StartLine": 3,
                    "Commit": "0123456789ab",
                }
            ]
        )
    )

    result = SecretsStep().run(workspace.context(base="abc123"))

    assert result.status == "failed"
    assert result.details == ("aws-access-token README.md:3 (commit 01234567)",)
    assert "--log-opts=abc123..HEAD" in argv(tools, "gitleaks")


@pytest.mark.parametrize(("code", "status"), [(0, "passed"), (1, "blocked"), (126, "blocked")])
def test_secrets_exit_codes(workspace: Workspace, tools: Path, code: int, status: str) -> None:
    fake_tool(tools, "gitleaks", GITLEAKS)
    (tools / "gitleaks.exit").write_text(str(code))

    result = SecretsStep().run(workspace.context())

    assert result.status == status
    assert not any(arg.startswith("--log-opts") for arg in argv(tools, "gitleaks"))


def test_missing_gitleaks_is_blocked(
    workspace: Workspace, tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = workspace.context()
    monkeypatch.setenv("PATH", str(tools))  # hide any gitleaks installed on this machine

    assert SecretsStep().run(context).details == (
        "gitleaks is not on PATH; install gitleaks 8.30.1",
    )


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (0, "passed"),
        (11, "failed"),
        (14, "failed"),
        (3, "not_applicable"),
        (1, "blocked"),
        (2, "blocked"),
    ],
)
def test_workflows_exit_codes(workspace: Workspace, tools: Path, code: int, status: str) -> None:
    fake_tool(tools, "uv", f"sys.exit({code})")

    assert WorkflowsStep().run(workspace.context()).status == status
    assert argv(tools, "uv") == [
        "tool",
        "run",
        "--from",
        "zizmor==1.30.1",
        "zizmor",
        "--offline",
        "--no-progress",
        "--strict-collection",
        "--format",
        "plain",
        ".",
    ]
```

Run: `uv run pytest tests/devctl/test_devctl_neutral_steps.py -q`
Expected: `ImportError: cannot import name 'SecretsStep'`.

- [ ] **Step 2: Implement.** `SecretsStep.run` returns `blocked(name, f"gitleaks is not on PATH; install gitleaks {GITLEAKS_VERSION}")` when `shutil.which("gitleaks")` is `None`. Otherwise it runs the command in the table from the repository root, with `--report-path` inside a temporary directory and a 900 s timeout. Exit 10 reads the report, a list of objects, and fails with one detail per finding: `"<RuleID> <File>:<StartLine> (commit <first 8 of Commit>)"`. An unreadable report on exit 10 is blocked. Other codes go through `command_result` with `failed_codes=frozenset()`. `WorkflowsStep.run` maps 3 to `not_applicable(name, "no workflows or actions found")`, and otherwise uses `command_result` with `failed_codes=frozenset({11, 12, 13, 14})`. Add `SecretsStep()` and `WorkflowsStep()` at the end of `core_steps`, for every stack.

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_neutral_steps.py -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_neutral_steps.py
git commit -m "feat: scan for secrets with gitleaks and audit workflows with zizmor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Evidence step

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/evidence.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`
- Create: `tests/devctl/test_devctl_evidence_step.py`

**Interfaces:**
- Consumes: `markdown.section`, `markdown.fenced_blocks`, `markdown.without_fences`.
- Produces:

```python
def evidence_section(body: str) -> str | None: ...
def removed_test_declarations(body: str) -> tuple[dict[str, str], list[str]]:
    ...
    # ({"path::name": reason}, malformed item lines), read from the Evidence section only


class EvidenceStep:
    name = "evidence"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult: ...
```

The Evidence format that `rs-pr` writes (plan 5, task 3) and this step reads:

```markdown
## Evidence

- `./devctl check`: exit 0; every step passed except evidence, not applicable
- **Before:** test_parse_dates failed. **After:** it passes.

Removed tests:
- `tests/test_flags.py::test_legacy_flag`: the flag was deleted in this PR

Not covered: behaviour on Windows.
```

A command with its result is a list item outside `Removed tests:` that starts with a code span, then a colon and text: `` - `<command>`: <result> ``. A fenced block whose first non-empty line starts with `$ `, followed by at least one more non-empty line, also counts. `Not covered:` starts a line outside code and has text after the colon. `Removed tests:` is optional; each item is `` - `<path>::<name>`: <reason> ``, with or without the backticks.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_evidence_step.py`:

```python
"""The evidence step and the Removed tests declarations it carries."""

from __future__ import annotations

import pytest
from check_workspace import Workspace
from devctl.check.evidence import EvidenceStep, removed_test_declarations

GOOD = """Fixes the parser.

## Evidence

- `uv run pytest tests/test_dates.py`: 12 passed
- **Before:** test_parse_dates failed. **After:** it passes.

Removed tests:
- tests/test_flags.py::test_legacy_flag: the flag was deleted in this PR
- `tests/test_cli.py::TestCli::test_old`: covered by test_new

Not covered: behaviour on Windows.

## Notes

Not covered: this line is outside the section.
"""

FENCED = (
    "## Evidence\n\n~~~console\n$ ./devctl check\npassed         format\n~~~\n\nNot covered: x\n"
)
NO_COMMAND = "Evidence: list a command you ran with its result, as '- `<command>`: <result>'"


def test_evidence_outside_a_pull_request_is_not_applicable(workspace: Workspace) -> None:
    assert EvidenceStep().run(workspace.context(pr_body=None)).status == "not_applicable"


@pytest.mark.parametrize("body", [GOOD, FENCED])
def test_complete_evidence_passes(workspace: Workspace, body: str) -> None:
    assert EvidenceStep().run(workspace.context(pr_body=body)).status == "passed"


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ("", "add an '## Evidence' section with a command, its result and a 'Not covered:' line"),
        ("## Evidence\n\nNot covered: x\n", NO_COMMAND),
        ("## Evidence\n\n- `make test`:\n\nNot covered: x\n", NO_COMMAND),
        ("## Evidence\n\n~~~\n$ make test\n~~~\n\nNot covered: x\n", NO_COMMAND),
        (
            "## Evidence\n\nRemoved tests:\n- `tests/test_a.py::test_a`: gone\n\nNot covered: x\n",
            NO_COMMAND,
        ),
        (
            "## Evidence\n\n- `make test`: ok\n\nNot covered:\n",
            "Evidence: add a line starting 'Not covered:' that names what the commands do not show",
        ),
        (
            "## Evidence\n\n- `make test`: ok\n\nRemoved tests:\n- test_a\n\nNot covered: x\n",
            "Removed tests: cannot read '- test_a'; write '- `<path>::<test>`: <reason>'",
        ),
    ],
)
def test_incomplete_evidence_fails(workspace: Workspace, body: str, detail: str) -> None:
    result = EvidenceStep().run(workspace.context(pr_body=body))

    assert result.status == "failed"
    assert result.details == (detail,)


def test_declarations_are_read_from_the_evidence_section() -> None:
    assert removed_test_declarations(GOOD) == (
        {
            "tests/test_flags.py::test_legacy_flag": "the flag was deleted in this PR",
            "tests/test_cli.py::TestCli::test_old": "covered by test_new",
        },
        [],
    )
```

Run: `uv run pytest tests/devctl/test_devctl_evidence_step.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.evidence'`.

- [ ] **Step 2: Implement `evidence.py`.** `evidence_section(body)` is `section(body, "Evidence", 2)`. Work on `without_fences(section)` lines for everything except fenced commands:
- `removed_test_declarations` finds the line `Removed tests:` in the section and reads the list items that follow until the first blank or non-item line. Each item is matched with `_DECLARATION` below; a non-matching item goes to the malformed list.
- A command exists when a list item outside the `Removed tests:` block matches `_COMMAND`, or when some `fenced_blocks(section)` entry has a first non-empty line starting with `$ ` and a later non-empty line.
- `Not covered:` is a line whose stripped text starts with `Not covered:` and has text after it.

```python
_DECLARATION = re.compile(r"^\s*[-*]\s+`?(?P<test>[^\s`]+::[^\s`]+?)`?:\s+(?P<reason>\S.*)$")
_COMMAND = re.compile(r"^\s*[-*]\s+`[^`]+`:\s*\S")
```

`EvidenceStep.run` returns `not_applicable(name, "not a pull request")` when `context.pr_body is None`. It fails with the details in the tests, in this order: section, command, `Not covered:`, malformed declarations. Whether each removed test is declared is checked by the diff step, so one missing declaration is reported once. Add `EvidenceStep()` at the end of `core_steps`.

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_evidence_step.py -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_evidence_step.py
git commit -m "feat: require an Evidence section on every pull request

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Diff policy, removed tests

**Files:**
- Create: `rapid_ship/templates/common/tools/devctl/devctl/check/diff.py`
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/__init__.py`
- Create: `tests/devctl/test_devctl_diff_removed_tests.py`, `tests/devctl/test_devctl_step_order.py`

**Interfaces:**
- Consumes: `Repo.git`, `is_test_file`, `test_identities`, `removed_test_declarations`, `ProjectSettings.unit_tests`, `GateSettings.mode` and `.owner_approves_behavioural_test_removal`.
- Produces:

```python
@dataclass(frozen=True)
class Change:
    path: str
    status: Literal["A", "M", "D"]


def changed_files(repo: Repo, base: str) -> list[Change]: ...
def glob_match(pattern: str, path: str) -> bool: ...  # "**" spans directories, "*" does not
def removed_tests(identities: Mapping[str, tuple[list[str], list[str]]]) -> list[str]: ...


class DiffStep:
    name = "diff"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult: ...
```

A test's identity is its name within its file (`test_x` or `TestA::test_x`). A test is removed when the number of tests with that identity across the changed test files falls between base and head. Files that did not change hold the same tests on both sides and cancel out. That is why a move between files is not a removal, while a removal is still caught when the same name exists in an unrelated file.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_diff_removed_tests.py`:

```python
"""Removed tests: identity across files, declarations, and unit or behavioural class."""

from __future__ import annotations

from check_workspace import Workspace, gate_settings
from devctl.check.diff import DiffStep, removed_tests
from devctl.check.steps import StepResult

EVIDENCE = "## Evidence\n\n~~~\n$ make test\nok\n~~~\n\nNot covered: x\n\n"


def run(workspace: Workspace, base: str, body: str | None = None, **gate: object) -> StepResult:
    return DiffStep().run(workspace.context(base=base, pr_body=body, gate=gate_settings(**gate)))


def test_moved_test_is_not_removed() -> None:
    assert (
        removed_tests({"tests/test_a.py": (["test_x"], []), "tests/test_b.py": ([], ["test_x"])})
        == []
    )


def test_name_in_another_file_does_not_hide_a_removal() -> None:
    assert removed_tests({"tests/test_a.py": (["test_x", "test_y"], ["test_y"])}) == [
        "tests/test_a.py::test_x"
    ]
    assert removed_tests(
        {"tests/test_a.py": (["test_x"], []), "tests/test_b.py": (["test_x"], ["test_x"])}
    ) == ["tests/test_a.py::test_x"]


def test_undeclared_removal_fails_and_names_its_class(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_create(): pass\ndef test_delete(): pass\n")
    workspace.write("tests/unit/test_math.py", "def test_add(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "def test_create(): pass\n")
    workspace.write("tests/unit/test_math.py", "\n")

    result = run(workspace, base, EVIDENCE)

    assert result.status == "failed"
    assert result.details[:2] == (
        "removed unit test tests/unit/test_math.py::test_add: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
        "removed behavioural test tests/test_api.py::test_delete: "
        "declare it under 'Removed tests:' in the PR's Evidence section",
    )


def test_declared_removal_passes_and_flight_waits_for_the_owner(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "class TestApi:\n    def test_delete(self): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "class TestApi:\n    pass\n")
    body = (
        EVIDENCE + "Removed tests:\n- tests/test_api.py::TestApi::test_delete: endpoint removed\n"
    )

    walk = run(workspace, base, body)
    flight = run(workspace, base, body, mode="flight")
    flight_off = run(
        workspace, base, body, mode="flight", owner_approves_behavioural_test_removal=False
    )

    assert walk.status == flight.status == flight_off.status == "passed"
    assert walk.details[0] == (
        "removed behavioural test tests/test_api.py::TestApi::test_delete: "
        "declared (endpoint removed)"
    )
    assert flight.details[0].endswith("; in Flight this waits for the owner's approval")
    assert flight_off.details[0] == walk.details[0]


def test_test_moved_to_an_untracked_file_is_not_removed(workspace: Workspace) -> None:
    workspace.write("tests/test_old.py", "def test_kept(): pass\n")
    base = workspace.commit()
    (workspace.root / "tests/test_old.py").unlink()
    workspace.write("tests/test_new.py", "def test_kept(): pass\n")

    assert run(workspace, base, EVIDENCE).status == "passed"


def test_removal_without_a_pr_body_explains_how_to_check_locally(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "\n")

    result = run(workspace, base)

    assert result.details[0].endswith("(pass --pr-body <file> to check a body locally)")


def test_test_file_that_stops_parsing_fails(workspace: Workspace) -> None:
    workspace.write("tests/test_api.py", "def test_delete(): pass\n")
    base = workspace.commit()
    workspace.write("tests/test_api.py", "def test_delete(:\n")

    assert (
        run(workspace, base, EVIDENCE)
        .details[0]
        .startswith("tests/test_api.py: cannot parse the tests at head")
    )


def test_no_base_is_not_applicable(workspace: Workspace) -> None:
    assert DiffStep().run(workspace.context()).status == "not_applicable"
```

Create `tests/devctl/test_devctl_step_order.py`:

```python
"""Core steps appear in spec section 5's order for each stack."""

from __future__ import annotations

from check_workspace import project_settings
from devctl.check import core_steps

PYTHON = [
    "format",
    "lint",
    "map",
    "exceptions",
    "file-size",
    "kit",
    "types",
    "contracts",
    "tests",
    "audit",
    "secrets",
    "workflows",
    "diff",
    "evidence",
]


def test_core_steps_follow_the_spec() -> None:
    python = core_steps(project_settings(stack="python"))
    neutral = core_steps(project_settings(stack="neutral"))

    assert [step.name for step in python] == PYTHON
    assert [step.name for step in neutral] == [
        "map",
        "exceptions",
        "file-size",
        "kit",
        "secrets",
        "workflows",
        "diff",
        "evidence",
    ]
    assert [step.name for step in python if step.tier == "fast"] == PYTHON[:6]
```

Run: `uv run pytest tests/devctl/test_devctl_diff_removed_tests.py tests/devctl/test_devctl_step_order.py -q`
Expected: `ModuleNotFoundError: No module named 'devctl.check.diff'`.

- [ ] **Step 2: Implement.**

```python
def changed_files(repo: Repo, base: str) -> list[Change]:
    """Changes from base to the work tree, plus untracked files that Git does not ignore."""
    fields = repo.git("diff", "--name-status", "-z", "--no-renames", base).split("\0")
    changes = [
        Change(path, "A" if status == "A" else "D" if status == "D" else "M")
        for status, path in zip(fields[0::2], fields[1::2], strict=False)
        if path
    ]
    known = {change.path for change in changes}
    untracked = repo.git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return changes + [Change(path, "A") for path in untracked if path and path not in known]


def removed_tests(identities: Mapping[str, tuple[list[str], list[str]]]) -> list[str]:
    """identities maps each changed test file to its test identities at (base, head)."""
    totals: Counter[str] = Counter()
    places: dict[str, list[str]] = defaultdict(list)
    for path, (before, after) in sorted(identities.items()):
        totals.update(before)
        totals.subtract(after)
        for name, count in sorted((Counter(before) - Counter(after)).items()):
            places[name].extend([path] * count)
    return [
        f"{path}::{name}"
        for name, paths in sorted(places.items())
        for path in paths[: max(totals[name], 0)]
    ]


def _glob(pattern: str) -> str:
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        else:
            char = pattern[index]
            parts.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
            index += 1
    return "".join(parts)


def glob_match(pattern: str, path: str) -> bool:
    return re.fullmatch(_glob(pattern), path) is not None
```

`DiffStep.run`:
1. With no base, return `not_applicable(name, "no base commit: not a change (pass --base to check one)")`.
2. Get `changed_files`; a `RepoError` is blocked. All later git reads go through `repo.git("show", f"{base}:{path}")`, and a `RepoError` from them is blocked too.
3. On the Python stack, for each changed test file, parse the base text (status M or D) and the head text (status M or A) with `test_identities`. A base that does not parse gives `[]`. A head that does not parse while its base did adds the problem `"<path>: cannot parse the tests at head (<error>)"`, and its head identities are taken to equal the base's, so the problem is reported once.
4. For each entry of `removed_tests`, in its returned order (by test name), its class is `unit` when its path matches a glob in `context.project.unit_tests`, else `behavioural`. A declared removal adds the note `"removed <class> test <id>: declared (<reason>)"`. In Flight, for a behavioural test with `owner_approves_behavioural_test_removal` on, append `"; in Flight this waits for the owner's approval"`; the Flight merge gate (Spec 3) enforces it. An undeclared one adds the problem `"removed <class> test <id>: declare it under 'Removed tests:' in the PR's Evidence section"`, plus `" (pass --pr-body <file> to check a body locally)"` when `pr_body` is `None`.
5. Return `failed(name, *problems, *notes)` when there are problems, else `passed(name, *notes)`.

Insert `DiffStep()` before `EvidenceStep()` in `core_steps`. `core_steps` now reads:

```python
def core_steps(project: ProjectSettings) -> list[Step]:
    python = project.stack == "python"
    return [
        *([FORMAT, LINT] if python else []),
        MapStep(),
        ExceptionsStep(),
        FileSizeStep(),
        KitStep(),
        *([TYPES, CONTRACTS, TESTS, AuditStep()] if python else []),
        SecretsStep(),
        WorkflowsStep(),
        DiffStep(),
        EvidenceStep(),
    ]
```

- [ ] **Step 3: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: fail a change that removes a test without declaring it

Tests keep their identity when moved between files. Each removal is
classed unit or behavioural by the [tests] unit globs.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Diff policy, tautologies, faking fixtures and Protected paths

**Files:**
- Modify: `rapid_ship/templates/common/tools/devctl/devctl/check/diff.py`, `check/stacks/python.py`
- Create: `tests/devctl/test_devctl_diff_rules.py`

**Interfaces:**
- Consumes: `comments`, `autouse_fixtures` and `MARKER` from task 7.
- Produces:

```python
# devctl/check/stacks/python.py
def tautologies(source: str) -> list[tuple[int, str]]: ...  # (line, unparsed assertion)


# devctl/check/diff.py
def protected_patterns(root: Path) -> list[str] | None: ...  # None without a CODEOWNERS file
def codeowners_match(pattern: str, path: str) -> bool: ...
```

CODEOWNERS format this step reads, which plan 2's seeded template must keep: the Protected set is written as `<pattern> @<owner>` lines. They are commented out as `# <pattern> @<owner>` during Walk. The catch-all `*` is not a Protected path.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_diff_rules.py`:

```python
"""Tautologies, new autouse fixtures and the Protected-path listing."""

from __future__ import annotations

import pytest
from check_workspace import Workspace
from devctl.check.diff import DiffStep, codeowners_match
from devctl.check.steps import StepResult

ALWAYS_TRUE = "is always true; assert on the behaviour instead"


def change(workspace: Workspace, path: str, before: str, after: str) -> StepResult:
    workspace.write(path, before)
    base = workspace.commit()
    workspace.write(path, after)
    return DiffStep().run(workspace.context(base=base))


@pytest.mark.parametrize(
    "after",
    [
        "def test_total():\n    assert True\n",
        "def test_total():\n    assert total(1) == total(1)\n",
        "class TestTotal:\n    def test_total(self):\n        self.assertEqual(x, x)\n",
    ],
)
def test_assertion_turned_into_a_tautology_fails(workspace: Workspace, after: str) -> None:
    result = change(
        workspace, "tests/test_total.py", "def test_total():\n    assert total(1) == 1\n", after
    )

    # The class-based case also renames the test, which the removed-test rule reports.
    [tautology] = [detail for detail in result.details if detail.endswith(ALWAYS_TRUE)]
    assert result.status == "failed"
    assert tautology.startswith("tests/test_total.py:")


def test_existing_tautology_is_not_reported(workspace: Workspace) -> None:
    source = "def test_placeholder():\n    assert True\n"

    assert change(workspace, "tests/test_p.py", source, source + "\n").status == "passed"


def test_new_autouse_fixture_needs_an_exception_marker(workspace: Workspace) -> None:
    before = "import pytest\n@pytest.fixture(autouse=True)\ndef old(): pass\n"
    after = before + "@pytest.fixture(autouse=True)\ndef fake_clock(): pass\n"

    result = change(workspace, "tests/conftest.py", before, after)

    assert result.status == "failed"
    assert result.details[0] == (
        "tests/conftest.py:4: new autouse fixture fake_clock needs an exception: add "
        "'# rs-exception: EX-<n>' on its decorator line and an entry with rule autouse"
    )


def test_marked_autouse_fixture_passes(workspace: Workspace) -> None:
    after = "import pytest\n@pytest.fixture(autouse=True)  # rs-exception: EX-4\ndef fake(): pass\n"

    assert change(workspace, "tests/conftest.py", "", after).status == "passed"


def test_protected_paths_are_listed_without_failing(workspace: Workspace) -> None:
    workspace.write(
        ".github/CODEOWNERS",
        "* @owner\n# Flight: uncomment below.\n# .github/ @owner\n# /pyproject.toml @owner\n",
    )

    result = change(workspace, ".github/workflows/ci.yml", "on: push\n", "on: [push]\n")

    assert result.status == "passed"
    assert result.details == ("protected: .github/workflows/ci.yml",)


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    [
        (".github/", ".github/workflows/ci.yml", True),
        (".github/", "docs/.github/x", True),
        ("/pyproject.toml", "pyproject.toml", True),
        ("/pyproject.toml", "sub/pyproject.toml", False),
        ("docs/patterns/", "docs/patterns/settings.md", True),
        ("*.toml", "a/b.toml", True),
        ("tools/devctl/", "tools/devctl", False),
    ],
)
def test_codeowners_patterns(pattern: str, path: str, matches: bool) -> None:
    assert codeowners_match(pattern, path) is matches
```

Run: `uv run pytest tests/devctl/test_devctl_diff_rules.py -q`
Expected: `ImportError: cannot import name 'codeowners_match'`.

- [ ] **Step 2: Implement `tautologies` in `stacks/python.py`.**

```python
_TRUTHY_CALLS = frozenset({"assertTrue", "assert_"})
_EQUAL_CALLS = frozenset(
    {"assertEqual", "assertEquals", "assertIs", "assertGreaterEqual", "assertLessEqual"}
)
_REFLEXIVE = (ast.Eq, ast.Is, ast.GtE, ast.LtE)


def tautologies(source: str) -> list[tuple[int, str]]:
    """Assertions that cannot fail; SyntaxError propagates."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assert) and _always_true(node.test):
            found.append((node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if _tautological_call(node.func.attr, node.args):
                found.append((node.lineno, ast.unparse(node)))
    return found


def _tautological_call(name: str, args: list[ast.expr]) -> bool:
    if name in _TRUTHY_CALLS and args:
        return _truthy_constant(args[0])
    return name in _EQUAL_CALLS and len(args) >= 2 and _same(args[0], args[1])


def _always_true(test: ast.expr) -> bool:
    if _truthy_constant(test):
        return True
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], _REFLEXIVE)
        and _same(test.left, test.comparators[0])
    )


def _truthy_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and bool(node.value)


def _same(first: ast.expr, second: ast.expr) -> bool:
    return ast.dump(first) == ast.dump(second)
```

- [ ] **Step 3: Implement the diff rules.** In `DiffStep.run`, on the Python stack:
- **Tautologies:** for each changed test file not deleted, compare `Counter` of unparsed tautologies at head with base (an empty base when added; unparsable text counts as none). Report each excess occurrence at its head line: `"<path>:<line>: <assertion> is always true; assert on the behaviour instead"`.
- **Faking fixtures:** for each changed file named `conftest.py` not deleted, the new autouse fixtures are the head `autouse_fixtures` whose names are not autouse fixtures at base. Each one whose decorator line's comment (from `comments`) has no `MARKER` match is a problem, with the message in the test. The exceptions step checks that the marked ID exists and matches.

For every stack:
- **Protected paths:** `protected_patterns` reads the first of `.github/CODEOWNERS`, `CODEOWNERS` and `docs/CODEOWNERS` that exists, which is GitHub's search order. It keeps the pattern of each line matching `^#?\s*(?P<pattern>[^\s#]+)(?:\s+(?:@[\w./-]+|\S+@\S+))+\s*$` except `*`. `codeowners_match` follows gitignore rules: a pattern with a `/` other than a trailing one is anchored at the root, and otherwise matches at any depth; a trailing `/` matches only below a directory; a pattern otherwise matches the path or anything below it. Use `_glob` for `*`, `**` and `?`. Add a note `"protected: <path>"` for each changed path that matches, sorted. Without a CODEOWNERS file, add the note `"no CODEOWNERS file; Protected paths are not listed"`. Protected paths never fail the step; CODEOWNERS enforces the approval.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl/test_devctl_diff_rules.py
git commit -m "feat: reject tautological assertions and unexcepted autouse fixtures

The diff step also lists the Protected paths a change touches; CODEOWNERS
enforces their approval.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: CI workflow and pre-commit hook templates

**Files:**
- Create: `rapid_ship/templates/common/.github/workflows/devctl-check.yml`, `rapid_ship/templates/common/.githooks/pre-commit`
- Generated by sync: `.github/workflows/devctl-check.yml`, `.githooks/pre-commit`, `.rapid-ship/kit.lock`
- Modify: `rapid_ship/templates/kit.toml`, `rapid_ship/templates/AGENTS.md`
- Create: `tests/devctl/test_devctl_ci_templates.py`

**Interfaces:**
- Consumes: `GITLEAKS_VERSION`; plan 2's `executable` list in `kit.toml`, which `init` and `sync` use to write the executable bit.
- Produces: two managed Kit files. The job is named `devctl check`, which the ruleset requires; `rs-setup` (plan 5) applies the ruleset and `devctl doctor` (plan 4) reads it back.

Push runs are limited at the trigger to `main` and `master`. The Kit file is identical in every project, so it cannot name each project's default branch. A job-level `if` is not used, because GitHub reports a skipped job as successful, and a skipped run on a PR head commit could satisfy the required check. Projects with another default branch get PR and nightly runs only.

`rs-setup` (plan 5) records a Setup gap when the default branch is neither `main` nor `master`, as spec section 4 says.

The workflow installs only gitleaks. The audit step runs the pinned `pip-audit==2.10.1`, and the workflows step `zizmor==1.30.1`, through `uv tool run` with the uv that `setup-uv` installs (tasks 10 and 11). No step runs `uv audit`.

- [ ] **Step 1: Mark the hook executable in the manifest.** In `rapid_ship/templates/kit.toml`, set `executable = ["devctl", ".githooks/pre-commit"]`, as plan 2's task 2 reserves for this plan.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_ci_templates.py`:

```python
"""The managed CI workflow and pre-commit hook. The hook test runs a simulated devctl."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml
from check_workspace import Workspace
from devctl.check.stacks.neutral import GITLEAKS_VERSION

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "rapid_ship/templates/common/.github/workflows/devctl-check.yml"
HOOK = ROOT / "rapid_ship/templates/common/.githooks/pre-commit"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_UV = "astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884"
GITLEAKS_SHA256 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"


def workflow() -> dict[object, object]:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict)
    return data


def test_triggers_include_body_edits_pushes_nightly_and_manual_runs() -> None:
    on = workflow()[True]  # PyYAML reads the key "on" as the boolean True.

    assert on["pull_request"] == {"types": ["opened", "synchronize", "reopened", "edited"]}
    assert on["push"] == {"branches": ["main", "master"]}
    assert on["schedule"] == [{"cron": "23 4 * * *"}]
    assert "workflow_dispatch" in on


def test_permissions_and_concurrency() -> None:
    data = workflow()

    assert data["permissions"] == {"contents": "read"}
    assert data["concurrency"] == {
        "group": "devctl-check-${{ github.ref }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }


def test_job_checks_out_full_history_without_credentials_and_runs_the_full_tier() -> None:
    job = workflow()["jobs"]["check"]
    steps = job["steps"]

    assert job["name"] == "devctl check"
    assert steps[0] == {"uses": CHECKOUT, "with": {"persist-credentials": False, "fetch-depth": 0}}
    assert steps[1] == {"uses": SETUP_UV}
    assert steps[-1] == {"name": "Run devctl check", "run": "./devctl check --tier full"}
    assert all("${{" not in step.get("run", "") for step in steps)


def test_actions_are_pinned_by_sha_with_a_version_comment() -> None:
    uses = [line.strip() for line in WORKFLOW.read_text().splitlines() if "uses:" in line]

    assert uses
    assert all(re.search(r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$", line) for line in uses)


def test_gitleaks_is_pinned_and_verified() -> None:
    install = workflow()["jobs"]["check"]["steps"][2]

    assert install["env"] == {
        "GITLEAKS_VERSION": GITLEAKS_VERSION,
        "GITLEAKS_SHA256": GITLEAKS_SHA256,
    }
    assert "sha256sum --check --strict" in install["run"]


def test_vendored_copies_match_their_templates() -> None:
    assert (ROOT / ".github/workflows/devctl-check.yml").read_bytes() == WORKFLOW.read_bytes()
    assert (ROOT / ".githooks/pre-commit").read_bytes() == HOOK.read_bytes()
    assert os.access(ROOT / ".githooks/pre-commit", os.X_OK)


def test_hook_runs_the_fast_tier_and_blocks_a_failing_commit(workspace: Workspace) -> None:
    workspace.write(".githooks/pre-commit", HOOK.read_text()).chmod(0o700)
    workspace.write(
        "devctl",
        f"#!{sys.executable}\nimport pathlib, sys\n"
        "pathlib.Path('devctl.log').write_text(' '.join(sys.argv[1:]))\n"
        "sys.exit(int(pathlib.Path('devctl.exit').read_text()))\n",
    ).chmod(0o700)
    workspace.write(".gitignore", "devctl.log\ndevctl.exit\n")
    workspace.write("devctl.exit", "1")
    workspace.git("add", "-A")

    rejected = workspace.try_git("-c", "core.hooksPath=.githooks", "commit", "-q", "-m", "x")
    workspace.write("devctl.exit", "0")
    accepted = workspace.try_git("-c", "core.hooksPath=.githooks", "commit", "-q", "-m", "x")

    assert rejected.returncode != 0
    assert accepted.returncode == 0
    assert (workspace.root / "devctl.log").read_text() == "check --tier fast"
```

Run: `uv run pytest tests/devctl/test_devctl_ci_templates.py -q`
Expected: `FileNotFoundError` for `devctl-check.yml`.

- [ ] **Step 3: Write the templates.** `rapid_ship/templates/common/.github/workflows/devctl-check.yml`:

```yaml
# Managed by rapid-ship. Change the template in rapid-ship, then run `rapid-ship sync`.
name: devctl check

on:
  pull_request:
    # edited: the evidence step reads the PR body, so a body edit reruns the check.
    types: [opened, synchronize, reopened, edited]
  push:
    # Kit files are identical in every project, so the default branch is listed by name.
    branches: [main, master]
  schedule:
    - cron: "23 4 * * *"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: devctl-check-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  check:
    name: devctl check
    runs-on: ubuntu-24.04
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 0
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
      - name: Install gitleaks
        env:
          GITLEAKS_VERSION: "8.30.1"
          GITLEAKS_SHA256: 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
        run: |
          archive="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
          curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
            --output "${RUNNER_TEMP}/${archive}" \
            "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${archive}"
          echo "${GITLEAKS_SHA256}  ${RUNNER_TEMP}/${archive}" | sha256sum --check --strict
          mkdir -p "${RUNNER_TEMP}/gitleaks"
          tar -xzf "${RUNNER_TEMP}/${archive}" -C "${RUNNER_TEMP}/gitleaks" gitleaks
          echo "${RUNNER_TEMP}/gitleaks" >> "${GITHUB_PATH}"
      - name: Run devctl check
        run: ./devctl check --tier full
```

`rapid_ship/templates/common/.githooks/pre-commit`:

```sh
#!/bin/sh
# Managed by rapid-ship. Runs the fast tier of devctl check before each commit.
# Enable with: git config core.hooksPath .githooks
# Skip once with: git commit --no-verify. CI still runs the full check.
exec ./devctl check --tier fast
```

Run `git add --chmod=+x rapid_ship/templates/common/.githooks/pre-commit`, so the template is executable in Git as well, then `uv run rapid-ship sync --in-place`. In `rapid_ship/templates/AGENTS.md`, add one line naming both templates as managed Kit files and saying that this repository's copies are refreshed by sync, never edited.

- [ ] **Step 4: Run the tests.**

Run: `uv run pytest tests/devctl/test_devctl_ci_templates.py -q && git ls-files -s .githooks/pre-commit`
Expected: all pass; mode `100755`.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates/common/.github rapid_ship/templates/common/.githooks rapid_ship/templates/kit.toml \
  .github/workflows/devctl-check.yml .githooks/pre-commit .rapid-ship/kit.lock \
  rapid_ship/templates/AGENTS.md tests/devctl/test_devctl_ci_templates.py
git commit -m "feat: ship the devctl check workflow and pre-commit hook in the Kit

Actions are pinned by commit, gitleaks by version and checksum, and the
workflow reruns when a PR body is edited.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: A newly initialised project passes devctl check

Spec section 8 says that the seeded skeleton of a new project passes `./devctl check`, and spec section 10 lists `init` on both stacks followed by a passing check as an integration test. `./devctl check` defaults to the full tier, so the test runs both tiers. It needs network access, for uv's downloads and pip-audit's lookups, and gitleaks 8.30.1 on PATH.

The same file pins the extension contract (spec section 3, "Who owns what"). A project replaces its seeded `devctl_project/__init__.py`, adds a verb through `register` and a check step through `check_steps`, and both run through `./devctl` without any change to devctl.

**Files:**
- Create: `tests/devctl/test_devctl_check_integration.py`
- Create, seeded: `rapid_ship/templates/common/tools/AGENTS.md`, `rapid_ship/templates/common/docs/AGENTS.md`, `rapid_ship/templates/python/AGENTS.md` (the Python root guide, seeded as `AGENTS.md`)
- Create, new-project seeds: `rapid_ship/templates/python/src/AGENTS.md`, `rapid_ship/templates/python/tests/AGENTS.md`, `rapid_ship/templates/python/.gitignore`
- Modify: `rapid_ship/templates/common/AGENTS.md`, `rapid_ship/templates/kit.toml`, plan 2's `tests/test_kit_contents.py`
- Generated by sync: `tools/AGENTS.md`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: `rapid-ship init --stack {python,neutral} --owner LOGIN` (plan 2), the `devctl` shim, `tool_environment()`, `new_workspace` and `Workspace.commit`; the seeded interface `register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None` (plan 2, task 9) and `check_steps() -> list[Step]` (task 2), with `Step`, `Tier`, `CheckContext`, `StepResult` and `passed` from `devctl.check.steps`.
- Produces: `kit.toml` gains the seeded paths `docs/AGENTS.md` and `tools/AGENTS.md`, and the new-project paths `.gitignore`, `src/AGENTS.md` and `tests/AGENTS.md`. The Python stack overrides the root guide, which plan 2 keeps in `common/` only.

- [ ] **Step 1: Confirm the `init` interface.**

Run: `uv run rapid-ship init --help`
Expected: `--stack {python,neutral}` and `--owner LOGIN` among the options (plan 2, task 7). The owner variable must not be empty, so the test passes `--owner`.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_check_integration.py`:

```python
"""Integration test: needs network access (PyPI and pip-audit's lookups) and gitleaks on PATH.

rapid-ship init writes a new project. devctl check's fast tier passes before the first
commit, as rs-setup runs it, and the full tier passes after it. A project's own verb and
check step, written against the seeded devctl_project interface, run through ./devctl.
No GitHub access.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from check_workspace import Workspace, new_workspace
from devctl.check.steps import tool_environment
from devctl.process import run_process

# The neutral seed has no source roots; a local run has no base commit and no PR body.
NOT_APPLICABLE: dict[tuple[str, str], set[str]] = {
    ("python", "fast"): set(),
    ("neutral", "fast"): {"file-size"},
    ("python", "full"): {"diff", "evidence"},
    ("neutral", "full"): {"file-size", "diff", "evidence"},
}


def assert_check_passes(project: Workspace, stack: str, tier: str) -> None:
    result = run_process(
        ["./devctl", "check", "--tier", tier, "--json"], project.root, 1200, env=tool_environment()
    )
    assert result.returncode == 0, result.stdout + result.stderr
    statuses = {step["name"]: step["status"] for step in json.loads(result.stdout)}
    assert set(statuses.values()) <= {"passed", "not_applicable"}
    skipped = {name for name, status in statuses.items() if status == "not_applicable"}
    assert skipped == NOT_APPLICABLE[(stack, tier)]


def init_project(path: Path, stack: str) -> Workspace:
    project = new_workspace(path)
    init = run_process(
        [sys.executable, "-m", "rapid_ship", "init", "--stack", stack, "--owner", "test-owner"],
        project.root,
        120,
    )
    assert init.returncode == 0, init.stdout + init.stderr
    return project


@pytest.mark.parametrize("stack", ["python", "neutral"])
def test_new_project_passes_devctl_check(tmp_path: Path, stack: str) -> None:
    project = init_project(tmp_path / "project", stack)
    if stack == "python":
        # pytest imports the package, so it writes __pycache__ under the source root.
        for command in (["uv", "sync", "--quiet"], ["uv", "run", "--locked", "pytest", "-q"]):
            ran = run_process(command, project.root, 600, env=tool_environment())
            assert ran.returncode == 0, ran.stdout + ran.stderr

    assert_check_passes(project, stack, "fast")
    project.commit("rapid-ship init")
    assert "__pycache__" not in project.git("ls-files")
    assert_check_passes(project, stack, "full")


# A project's replacement for the seeded tools/devctl/devctl_project/__init__.py.
PROJECT_EXTENSION = r'''"""This project's devctl verbs and check steps."""

from __future__ import annotations

import argparse
import sys

from devctl.check.steps import CheckContext, Step, StepResult, Tier, passed


def greet(args: argparse.Namespace) -> int:
    sys.stdout.write(f"hello {args.name}\n")
    return 0


class ReleaseNotesStep:
    name = "release-notes"
    tier: Tier = "full"

    def run(self, context: CheckContext) -> StepResult:
        return passed(self.name, "release notes are current")


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    verb = commands.add_parser("greet", help="Print a greeting")
    verb.add_argument("name")
    verb.set_defaults(handler=greet)


def check_steps() -> list[Step]:
    return [ReleaseNotesStep()]
'''


def run_devctl(project: Workspace, *args: str) -> tuple[int, str, str]:
    result = run_process(["./devctl", *args], project.root, 1200, env=tool_environment())
    return result.returncode, result.stdout, result.stderr


def test_a_project_verb_and_check_step_extend_devctl(tmp_path: Path) -> None:
    project = init_project(tmp_path / "project", "neutral")
    project.write("tools/devctl/devctl_project/__init__.py", PROJECT_EXTENSION)
    project.commit("rapid-ship init, then a project verb and check step")

    greeted = run_devctl(project, "greet", "world")
    fast = run_devctl(project, "check", "--tier", "fast", "--json")
    full = run_devctl(project, "check", "--tier", "full", "--json")

    assert greeted[:2] == (0, "hello world\n"), greeted
    # The step runs in its own tier only, after the core steps.
    assert "release-notes" not in {step["name"] for step in json.loads(fast[1])}
    assert full[0] == 0, full
    assert json.loads(full[1])[-1] == {
        "name": "release-notes",
        "status": "passed",
        "details": ["release notes are current"],
    }
```

In plan 2's `tests/test_kit_contents.py`, keep each test's name so no test is removed:
- Replace `test_root_guide_skeleton_follows_the_spec` with this version, which runs on both stacks and expects the new links; its other assertions are plan 2's:

```python
ROOT_GUIDE_LINKS = [
    "docs/features/README.md",
    "docs/patterns/README.md",
    "docs/AGENTS.md",
    "tools/AGENTS.md",
]
POINTERS = (
    "`GLOSSARY.md`",
    "`docs/adr/`",
    "`rs-writing`",
    "`rs-ponytail`",
    "`./devctl check`",
    "`./devctl doctor`",
)


@pytest.mark.parametrize(
    ("stack", "links"),
    [
        ("neutral", ROOT_GUIDE_LINKS),
        ("python", [*ROOT_GUIDE_LINKS, "src/AGENTS.md", "tests/AGENTS.md"]),
    ],
)
def test_root_guide_skeleton_follows_the_spec(stack: str, links: list[str]) -> None:
    guide = text(stack, "AGENTS.md")
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
    assert re.findall(r"\]\(([^)]+)\)", guide) == links
    assert all(pointer in guide for pointer in POINTERS)


def test_the_python_root_guide_only_adds_the_source_and_test_rows() -> None:
    python = text("python", "AGENTS.md").splitlines()
    rows = [line for line in python if "](src/AGENTS.md)" in line or "](tests/AGENTS.md)" in line]

    assert len(rows) == 2
    assert [line for line in python if line not in rows] == text(
        "neutral", "AGENTS.md"
    ).splitlines()
```

- In `test_python_new_project_seeds`, add `".gitignore"`, `"src/AGENTS.md"` and `"tests/AGENTS.md"` to the paths whose kind is `seeded`, and add `assert text("python", ".gitignore") == "__pycache__/\n*.py[cod]\n.venv/\ndist/\n"`.

Run: `uv run pytest tests/devctl/test_devctl_check_integration.py tests/test_kit_contents.py -q`
Expected: the integration test fails on the fast tier's map step for both stacks: `tools/` and `docs/` need guides, and for Python also `src/` and `tests/`. `test_a_project_verb_and_check_step_extend_devctl` already gets its greeting and no fast-tier `release-notes`, because plan 2 and task 2 built the interface; it fails at `full[0] == 0` on the same neutral map findings. In `test_kit_contents.py`, both root guide tests fail on plan 2's two-link guide and `test_python_new_project_seeds` raises `KeyError` for a missing seed.

- [ ] **Step 3: Write the seeds.** Change the seeded templates only, never devctl.
- `rapid_ship/templates/common/tools/AGENTS.md`: "`devctl/` is this project's devctl, vendored by rapid-ship. Do not edit `devctl/devctl/`; `rapid-ship sync` replaces it. Add project verbs and check steps in `devctl/devctl_project/`."
- `rapid_ship/templates/common/docs/AGENTS.md`: links `features/README.md` and `patterns/README.md`, and says each holds one file per feature or Pattern. It has no Rules heading.
- `rapid_ship/templates/python/src/AGENTS.md`: "`{{package}}/` is the product's code. Add a guide for each directory directly under it." `rapid_ship/templates/python/tests/AGENTS.md`: "pytest runs every test here. Unit tests go in `unit/`, which `[tests] unit` in `.rapid-ship/project.toml` names; every other test counts as behavioural."
- `rapid_ship/templates/python/.gitignore`: the four lines `__pycache__/`, `*.py[cod]`, `.venv/` and `dist/`. Without it, the first pytest run leaves `src/<package>/__pycache__/` beside the code, and `rs-setup`'s `git add -A` would commit the bytecode.
- In `rapid_ship/templates/common/AGENTS.md`, add two rows to "Find the change", after Patterns: `| Where feature and Pattern files live | [Documentation](docs/AGENTS.md) |` and `| This project's devctl verbs and check steps | [Tools](tools/AGENTS.md) |`.
- `rapid_ship/templates/python/AGENTS.md` is a copy of the common root guide with two more rows after Tools: `| Product code | [Source](src/AGENTS.md) |` and `| Tests, and which count as unit tests | [Tests](tests/AGENTS.md) |`. The stack layer overrides `common/` (plan 2, task 2), and `test_the_python_root_guide_only_adds_the_source_and_test_rows` keeps the two copies in step.
- In `rapid_ship/templates/kit.toml`, add `docs/AGENTS.md` and `tools/AGENTS.md` to `seeded`, and `.gitignore`, `src/AGENTS.md` and `tests/AGENTS.md` to `new_project`: an existing project already has its own source layout and ignore rules. Plan 2 already seeds `source_roots = []` for the neutral stack, and its root guide's Rules already end with markers.

`scripts/check_repository.py` reads `rapid_ship/templates/python/AGENTS.md` as a guide of this repository, and the override's links to common-layer files do not resolve from there. Nothing runs that script after this task; task 17 deletes it and excludes the template trees from the map.

- [ ] **Step 4: Run the tests.**

Run: `uv run rapid-ship sync --in-place && uv run pytest tests/test_kit_contents.py tests/devctl/test_devctl_check_integration.py -q`
Expected: sync adds `tools/AGENTS.md` to this repository, records the existing `docs/AGENTS.md`, and lists `AGENTS.md` as a changed seed. All tests pass for both stacks, and the extension test passes. If the full tier fails:
- zizmor reports the Kit workflow: fix `rapid_ship/templates/common/.github/workflows/devctl-check.yml`, never with an ignore comment, and update task 15's test where a pinned value changes.
- gitleaks reports a Kit file or a generated lock: stop and report it. An allowlist would be a new Kit file, which is a design change.

- [ ] **Step 5: Commit.**

```bash
git add rapid_ship/templates tests/devctl/test_devctl_check_integration.py tests/test_kit_contents.py \
  tools/AGENTS.md .github/workflows/devctl-check.yml .rapid-ship/kit.lock
git commit -m "test: a newly initialised project passes devctl check

Seed a guide for every top-level directory so the map rules pass, and a
.gitignore so a new Python project never commits its bytecode. A project
verb and check step written against the seeded devctl_project interface
run through ./devctl.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: rapid-ship's own check steps, and the switch from `scripts/check.py`

**Files:**
- Modify: `tools/devctl/devctl_project/__init__.py` and `tools/AGENTS.md` (both seeded; this repository owns them)
- Create: `tests/devctl/test_devctl_project_steps.py`, `tests/devctl/test_devctl_project_dogfood.py`
- Modify: plan 2's `tests/devctl/test_devctl_cli.py`
- Delete: `scripts/check.py`, `scripts/check_repository.py`, `tests/test_check.py`, `tests/test_repository_navigation.py`, `.github/workflows/ci.yml`
- Modify: `.rapid-ship/project.toml`, `AGENTS.md`, `.github/AGENTS.md`, `scripts/AGENTS.md`, `tests/AGENTS.md`, `rapid_ship/templates/AGENTS.md`, `ARCHITECTURE.md`, `README.md`

**Interfaces:**
- Consumes: `CommandStep`, `command_result`, `run_tool`, `tool_environment`, `Step`, `StepResult`, `CheckContext`, `Tier`, `Repo.files()`, `new_workspace`; plan 2's `scripts/smoke_distribution.py`, which reads the wheel from `dist/` under its own checkout and expects a copy without `.git`.
- Produces: `devctl_project.check_steps() -> list[Step]`, returning `VENDORED`, `DistributionStep()` and `FloorPythonStep()`; `devctl_project.copy_work_tree(repo: Repo, target: Path) -> None`, which the distribution step and the dog-food test share.

| Step | Tier | Replaces | Behaviour |
| --- | --- | --- | --- |
| `vendored` | fast | the `rapid-ship status --strict` stage plan 2 adds to `scripts/check.py` | `uv run --locked rapid-ship status --strict`: 0 passed, 1 failed, else blocked |
| `distribution` | full | `scripts/check.py`'s `copy_source` and its temporary-copy stages, `uv build` then `scripts/smoke_distribution.py` | Copy the files Git keeps (`Repo.files()`, symlinks kept, no `.git`) into a temporary directory; run `uv build` there, then `scripts/smoke_distribution.py` with devctl's Python. Exit 1 fails; anything else blocks |
| `python-3.12` | full | the 3.12 leg of `.github/workflows/ci.yml:14-17` | `uv run --locked --python 3.12 pytest -q` with `UV_PROJECT_ENVIRONMENT` set to a temporary directory, so the work tree's `.venv` is untouched |

The smoke stays a script: plan 2's version checks that the wheel ships every template, installs it in isolation, and runs `init`, `status --strict` and `./devctl` in a new and an existing project. The step only moves the stage that `scripts/check.py` ran.

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_project_steps.py`:

```python
"""rapid-ship's own check steps, run against a simulated uv and smoke script."""

from __future__ import annotations

import json
import os
from pathlib import Path

import devctl_project
import pytest
from check_workspace import Workspace, fake_tool
from devctl.process import run_process
from devctl_project import DistributionStep, FloorPythonStep

ROOT = Path(__file__).resolve().parents[2]
UV = """
here = pathlib.Path(__file__).parent
if sys.argv[1:] == ["build"]:
    pathlib.Path("dist").mkdir()
    pathlib.Path("dist/rapid_ship-0.2.0-py3-none-any.whl").write_text("wheel")
    sys.exit(int((here / "build.exit").read_text()) if (here / "build.exit").exists() else 0)
sys.exit(0)
"""

SMOKE = """import json, pathlib, sys
root = pathlib.Path.cwd()
pathlib.Path(LOG).write_text(json.dumps({
    "cwd": str(root),
    "edited": (root / "source.py").read_text(),
    "new": (root / "new.py").exists(),
    "alias": (root / "alias").is_symlink(),
    "git": (root / ".git").exists(),
    "wheels": sorted(p.name for p in (root / "dist").glob("*.whl")),
}))
sys.exit(int((root / "smoke.exit").read_text()) if (root / "smoke.exit").exists() else 0)
"""


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    fake_tool(directory, "uv", UV)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return directory


def checkout(workspace: Workspace, log: Path) -> None:
    workspace.write(".gitignore", "dist/\n")
    workspace.write("source.py", "original\n")
    workspace.write("scripts/smoke_distribution.py", f"LOG = {str(log)!r}\n" + SMOKE)
    workspace.commit()
    workspace.write("source.py", "edited\n")
    workspace.write("new.py", "new\n")
    (workspace.root / "alias").symlink_to("source.py")


def test_repository_steps() -> None:
    steps = devctl_project.check_steps()

    assert [(s.name, s.tier) for s in steps] == [
        ("vendored", "fast"),
        ("distribution", "full"),
        ("python-3.12", "full"),
    ]


def test_distribution_builds_and_smokes_a_copy_of_the_work_tree(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    log = tmp_path / "smoke.json"
    checkout(workspace, log)

    result = DistributionStep().run(workspace.context())

    assert result.status == "passed", result.details
    record = json.loads(log.read_text())
    assert record["cwd"] != str(workspace.root)
    assert (record["edited"], record["new"], record["alias"], record["git"]) == (
        "edited\n",
        True,
        True,
        False,
    )
    assert record["wheels"] == ["rapid_ship-0.2.0-py3-none-any.whl"]
    assert not Path(record["cwd"]).exists()
    assert not (workspace.root / "dist").exists()


def test_distribution_fails_when_the_smoke_fails(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    checkout(workspace, tmp_path / "smoke.json")
    workspace.write("smoke.exit", "1")

    assert DistributionStep().run(workspace.context()).status == "failed"


def test_distribution_fails_when_the_build_fails(
    workspace: Workspace, tools: Path, tmp_path: Path
) -> None:
    checkout(workspace, tmp_path / "smoke.json")
    (tools / "build.exit").write_text("1")

    assert DistributionStep().run(workspace.context()).status == "failed"
    assert not (tmp_path / "smoke.json").exists()


def test_python_floor_uses_a_separate_environment(workspace: Workspace, tools: Path) -> None:
    assert FloorPythonStep().run(workspace.context()).status == "passed"
    [call] = [json.loads(line) for line in (tools / "uv.log").read_text().splitlines()]
    assert call["argv"] == ["run", "--locked", "--python", "3.12", "pytest", "-q"]
    assert "UV_PROJECT_ENVIRONMENT" in call["env"]


@pytest.mark.parametrize(
    "path", [".controller/bin/python", ".controller-build-1/wheel.whl", ".controller-setup.lock"]
)
def test_state_left_by_the_removed_controller_stays_ignored(path: str) -> None:
    # Existing checkouts still hold this state. Unignored, Ruff would lint a virtualenv,
    # the distribution step would copy it and uv build would pack it into the source archive.
    result = run_process(["git", "check-ignore", "--no-index", "--quiet", path], ROOT, 30)

    assert result.returncode == 0
```

The last test moves here from `tests/test_check.py`, which step 3 deletes, with `run_process` in place of `subprocess.run`. It keeps its name, so the diff step counts it as moved, and it passes already.

Create `tests/devctl/test_devctl_project_dogfood.py`. Plan 2's `tests/test_kit_dogfood.py` pins that `sync --in-place` leaves `devctl_project` byte for byte. This test makes that sync do real work: before it, the copy edits a managed devctl template and the `devctl_project` seed template and commits. The sync must vendor the managed edit, leave this repository's own `devctl_project` untouched, and `./devctl check` must still run the three steps afterwards. The copy holds one small test instead of this suite, because its `tests` and `python-3.12` steps run pytest there and would start this test again.

```python
"""Integration test: needs network access (uv, pip-audit, Python 3.12) and gitleaks on PATH.

After a template edit and `uv run rapid-ship sync --in-place`, the vendored devctl carries the
edit, the seeded devctl_project does not, and ./devctl check still runs this repository's own
steps. Everything runs in a copy of the work tree, so the checkout is never written.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from check_workspace import new_workspace
from devctl.check.steps import tool_environment
from devctl.process import run_process
from devctl.repo import Repo
from devctl_project import copy_work_tree

ROOT = Path(__file__).resolve().parents[2]
ONLY_TEST = '''"""The one test in the dog-food copy."""

from rapid_ship.files import atomic_replace


def test_the_package_imports() -> None:
    assert callable(atomic_replace)
'''
TEMPLATES = "rapid_ship/templates/common/tools/devctl"
MANAGED = "devctl/check/__init__.py"
EDIT = "# Edited by the dog-food test.\n"


def test_own_check_steps_still_run_after_sync(tmp_path: Path) -> None:
    copy = new_workspace(tmp_path / "copy")
    copy_work_tree(Repo.discover(ROOT), copy.root)
    shutil.rmtree(copy.root / "tests")
    copy.write("tests/test_copy.py", ONLY_TEST)
    copy.commit("copy of the work tree")
    for template in (f"{TEMPLATES}/{MANAGED}", f"{TEMPLATES}/devctl_project/__init__.py"):
        path = copy.root / template
        path.write_text(path.read_text() + EDIT)
    copy.commit("edit a managed devctl template and the devctl_project seed template")

    synced = run_process(
        ["uv", "run", "--locked", "rapid-ship", "sync", "--in-place"],
        copy.root,
        600,
        env=tool_environment(),
    )

    assert synced.returncode == 0, synced.stdout + synced.stderr
    # sync vendors the managed edit and never writes the seeded copy this repository owns.
    assert copy.git("status", "--porcelain", "--", "tools/devctl/devctl")
    assert (copy.root / "tools/devctl" / MANAGED).read_text().endswith(EDIT)
    assert copy.git("status", "--porcelain", "--", "tools/devctl/devctl_project") == ""

    checked = run_process(
        ["./devctl", "check", "--tier", "full", "--json"], copy.root, 1800, env=tool_environment()
    )

    assert checked.stdout, checked.stderr
    # Core steps may fail on the reduced tests/ directory; only the project's steps count here.
    results = [(step["name"], step["status"]) for step in json.loads(checked.stdout)]
    assert results[-3:] == [
        ("vendored", "passed"),
        ("distribution", "passed"),
        ("python-3.12", "passed"),
    ], checked.stdout
```

`uv run` in the copy installs the copy's `rapid_ship`, so the sync reads the copy's templates, as it does in this checkout.

Run: `uv run pytest tests/devctl/test_devctl_project_steps.py tests/devctl/test_devctl_project_dogfood.py -q`
Expected: `ImportError: cannot import name 'DistributionStep'` and `ImportError: cannot import name 'copy_work_tree'`.

- [ ] **Step 2: Implement `tools/devctl/devctl_project/__init__.py`.** Keep plan 2's `register` stub. Add `VENDORED = CommandStep("vendored", "fast", ("uv", "run", "--locked", "rapid-ship", "status", "--strict"))`. Add `DistributionStep` and `FloorPythonStep` as plain classes with `name` and `tier` class attributes, implementing the table above with `run_tool` and `command_result` (`failed_codes=frozenset({1})`, or `frozenset({1, 5})` for pytest). Each uses its own `tempfile.TemporaryDirectory`, so nothing is left in the checkout. Port `copy_source` from `scripts/check.py` as `copy_work_tree(repo, target)`: for each path in `repo.files()` that exists under `repo.root` or is a symlink, create its parent under `target` with `exist_ok=True` and `shutil.copy2(source, destination, follow_symlinks=False)`. `DistributionStep` copies `context.repo` with it, then stops at the first command that does not pass. It runs the smoke as `(sys.executable, "scripts/smoke_distribution.py")` with a 1800 s timeout; the smoke uses only the standard library.

In plan 2's `tests/devctl/test_devctl_cli.py`, delete `test_the_seeded_project_hooks_add_nothing`: this repository's copy now adds three steps, which `test_repository_steps` pins, and task 16's integration test runs the empty seed in a new project. Task 19's PR body declares the removal.

Run: `uv run pytest tests/devctl/test_devctl_project_steps.py tests/devctl/test_devctl_project_dogfood.py -q`
Expected: all pass. The dog-food test takes minutes: in the copy it creates the root and devctl environments, builds the wheel, runs the smoke and runs pytest on Python 3.12. A full `./devctl check` runs it twice, in the `tests` and `python-3.12` steps.

- [ ] **Step 3: Switch this repository.**

```bash
git rm scripts/check.py scripts/check_repository.py \
  tests/test_check.py tests/test_repository_navigation.py .github/workflows/ci.yml
```

`scripts/` keeps `smoke_distribution.py` and its guide. Of the three tests in `tests/test_check.py`, step 1 moved one; the other two tested `scripts/check.py` and go with it. Task 3 ported the navigation tests under their names, except the two it replaced. Task 19's PR body declares all four.

Owner step: none is needed for required checks. On 2026-10-14, `gh api repos/proxy-hatch/rapid-ship/rulesets --jq length` printed `0` and `main` had no branch protection, so removing the `CI` workflow strands no required check. In a project, `rs-setup` (plan 5) applies the ruleset that requires `devctl check`. Plan 5 Task 12 applies it to this repository as an Owner step.

- [ ] **Step 4: Set this repository's map settings.** In `.rapid-ship/project.toml`, which is seeded and owned here:

```toml
[map]
source_roots = ["rapid_ship"]
unguided = []
# Template trees hold the AGENTS.md files of future projects, not guides of this one.
exclude = ["rapid_ship/templates/common", "rapid_ship/templates/python", "rapid_ship/templates/neutral"]
```

- [ ] **Step 5: Update the guides.**
- Replace the seeded `tools/AGENTS.md`, which task 16's sync wrote, with: "`[devctl/](devctl/)` is this repository's vendored devctl, written by `uv run rapid-ship sync --in-place` from the templates in `rapid_ship/templates/common/tools/devctl/`. Never edit `devctl/devctl/` by hand: change the template, then sync. The `vendored` check step fails when the two differ. `devctl/devctl_project/` is seeded and owned here; it adds rapid-ship's own check steps: `vendored`, `distribution` and `python-3.12`. Their tests are in `tests/devctl/test_devctl_project_steps.py`, and `tests/devctl/test_devctl_project_dogfood.py` checks that they still run after a sync."
- Root `AGENTS.md`: the commands become `uv sync --locked` and `git config core.hooksPath .githooks` (setup), `./devctl check` (full check, same as CI), `./devctl check --tier fast` (what the hook runs), `uv run pytest`, `uv run rapid-ship sync --in-place` (refresh the vendored Kit after a template change) and `npm --prefix website run build`. Remove the `scripts/check.py`, `scripts/check_repository.py` and `smoke_distribution.py` commands; the `distribution` step runs the smoke. Add a "Find the change" row for `tools/AGENTS.md`.
- `.github/AGENTS.md`: `workflows/devctl-check.yml` is the managed Kit workflow; it runs `./devctl check --tier full` and is changed only through its template. Keep the `docs.yml` lines. Delete the lines about `scripts/check.py` and install-smoke ordering.
- `scripts/AGENTS.md`: drop the `check.py` and `check_repository.py` entries and the commands that run them; say that the `distribution` check step runs `smoke_distribution.py` after `uv build` in a copy without `.git`.
- `rapid_ship/templates/AGENTS.md`: `rapid-ship status --strict` is now run by the `vendored` check step, not `scripts/check.py`.
- `tests/AGENTS.md`: delete plan 1's "Repository validation, navigation and ignored local state" row, whose files step 3 deletes. Extend plan 2's `devctl/` row: it also holds one test file per `devctl check` step and the typed fixtures in `devctl/check_workspace.py`, which pytest's `pythonpath` makes importable. Add a row for `devctl/test_devctl_project_steps.py`, rapid-ship's own check steps, and `devctl/test_devctl_project_dogfood.py`, which runs them after `sync --in-place` in a copy. Say that `devctl/test_devctl_check_integration.py` and `devctl/test_devctl_project_dogfood.py` need network access and gitleaks 8.30.1 on PATH.
- `ARCHITECTURE.md`: replace the `uv run python scripts/check.py` block and its two paragraphs with `./devctl check` and one sentence on what it covers. Say that CI runs the same command once, with `python-3.12` as a step.
- `README.md`: point the badge at `actions/workflows/devctl-check.yml` and label it "devctl check".

- [ ] **Step 6: Run the tests and the new check.**

Run: `uv run pytest -q`
Expected: all pass, with gitleaks on PATH (Global Constraints).

Run: `./devctl check --tier full --json > /tmp/devctl-check.json; echo $?`
Expected: `vendored`, `distribution` and `python-3.12` are `passed`. Findings in lint, types, contracts, exceptions, map or workflows are expected; task 18 fixes them. The diff step fails on the eight removed tests, which task 19's PR body declares. Record this run's statuses in the commit body.

- [ ] **Step 7: Commit.**

```bash
git add -A tools/devctl/devctl_project tools/AGENTS.md tests scripts .github .rapid-ship/project.toml \
  rapid_ship/templates/AGENTS.md AGENTS.md ARCHITECTURE.md README.md
git commit -m "chore: run rapid-ship's own checks through devctl

The wheel build with its smoke, status --strict and the Python 3.12 run
become project check steps, and a dog-food test runs them after
sync --in-place. scripts/check.py, check_repository.py and the CI
workflow are replaced by ./devctl check and devctl-check.yml.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 18: Adopt the Python guardrail settings and fix the findings

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `.rapid-ship/exceptions.toml`, `.github/workflows/docs.yml` (only for zizmor findings)
- Modify: files under `rapid_ship/`, `tests/` and the devctl templates that the findings name, and `scripts/smoke_distribution.py`

**Interfaces:**
- Consumes: the guardrail settings from spec section 4 and plan 2's seeded `rapid_ship/templates/python/pyproject.toml`.
- Produces: nothing new.

- [ ] **Step 1: Adopt the settings.** Run `uv add --dev "import-linter>=2.15,<3"`. Set these tables in `pyproject.toml`. The rule selection, mypy flags and pytest options must equal plan 2's seeded template; where they differ, copy the template's values. The values marked "this repository" are local.

```toml
[tool.ruff]
target-version = "py312"
# this repository: lines are capped at 100 characters
line-length = 100
# this repository: devctl and its test helper are first-party for import sorting
src = [".", "tools/devctl", "tests/devctl"]
# this repository: templates are byte-identical to tools/devctl, which is linted; `vendored` enforces it
extend-exclude = ["rapid_ship/templates"]

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "B", "UP", "SIM", "C4", "RUF", "PGH", "ERA", "T20", "S", "TID",
    "PT", "PTH", "DTZ", "C90", "TD", "BLE", "ANN401",
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.flake8-tidy-imports.banned-api]

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool"]
# this repository: the vendored devctl is checked here, its template copy is excluded,
# and devctl replaces the seed's mypy_path "src"
files = ["rapid_ship", "tools/devctl", "tests"]
exclude = ["^rapid_ship/templates/"]
mypy_path = "tools/devctl"

[tool.pytest.ini_options]
testpaths = ["tests"]
# this repository: devctl tests import the vendored devctl and their shared workspace helper
pythonpath = ["tools/devctl", "tests/devctl"]
# this repository: "-ra" before the seed's two options
addopts = ["-ra", "--strict-markers", "--strict-config"]
xfail_strict = true
filterwarnings = ["error"]

[tool.importlinter]
root_packages = ["rapid_ship"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "rapid-ship CLI layers"
type = "layers"
layers = ["rapid_ship.cli", "rapid_ship.kit", "rapid_ship.files"]

[[tool.importlinter.contracts]]
name = "rapid-ship never imports the vendored devctl"
type = "forbidden"
source_modules = ["rapid_ship"]
forbidden_modules = ["devctl", "devctl_project"]
```

If plan 2 added top-level `rapid_ship` modules besides `cli`, `kit` and `files`, place them in the layers in their import order. The forbidden contract names packages outside the graph; with `include_external_packages = true`, import-linter checks only forbidden modules that are present, so it passes until `rapid_ship` imports devctl (`src/importlinter/contracts/forbidden.py:102-113` on import-linter's default branch, read 2026-10-14).

- [ ] **Step 2: Fix the findings.**

Run: `./devctl check --tier full`
Fix every failed step in this order: format (`uv run ruff format .`), lint, types, contracts, exceptions, map, workflows. Rules:
- Change the code, never the settings. Edit devctl only in its template, then sync.
- A finding that cannot be fixed takes `# noqa: <code>  # rs-exception: EX-<n>` and an entry in `.rapid-ship/exceptions.toml` with the next free ID, a reason and a removal condition. Call out each new exception in the PR body.
- A `print` in `rapid_ship/cli.py` or `scripts/smoke_distribution.py` becomes `sys.stdout.write`.
- A zizmor finding in `.github/workflows/docs.yml` is fixed in that file. For `cache-poisoning`, remove `cache: npm` from `actions/setup-node`. Do not add an ignore comment.
- A map finding is fixed by adding the missing guide or link. For a missing `rapid_ship/<child>/AGENTS.md`, write a guide that names the modules in that directory and their responsibility in one line each, and link it from `rapid_ship/AGENTS.md`.

Expected work, from the code plans 1 and 2 leave:
- **types:** mypy strict now covers `tests/`, and plans 1 and 2 wrote unannotated tests: `tests/conftest.py`, `tests/test_cli.py`, `tests/test_files.py`, every `tests/test_kit_*.py`, and `tests/devctl/test_devctl_cli.py`, `test_devctl_repo.py` and `test_devctl_settings.py`. Annotate every test, fixture and helper. Never exclude tests from mypy.
- **lint, S603 and S607:** the S rules apply to tests too; only S101 is ignored there. Tests start processes through `devctl.process.run_process`, as `check_workspace.py` does, so tests need no exception. Rewrite plan 2's `tests/conftest.py::_git` on `run_process`, raising `AssertionError` when git fails, and do the same for the direct `subprocess` calls in `tests/test_cli.py` and `tests/test_kit_contents.py`.
- **exceptions for code that cannot import devctl:** `rapid_ship` must not import it (step 1's forbidden contract), and the smoke uses only the standard library. Ruff 0.17.0 reports S603 on the call's line and S607 on the line that holds a literal argv, so a call split over lines would need two markers. Build such an argv in a variable first; Ruff then reports only S603, on the call. Expected entries, from EX-4, each with the rule Ruff reports on its marked line:
  - `rapid_ship/kit/git.py`: the `subprocess.run` in `git`. Route `work_tree_root` through `git` with `allowed=(0, 128)`, since git exits 128 outside a work tree, instead of keeping a second call.
  - `rapid_ship/kit/sync.py`: each direct `subprocess` call in `push_and_open_pull_request`. Plan 2's follow-up 2 removed `merge_file` and `released_templates`, so their calls need no exception.
  - `scripts/smoke_distribution.py`: the call in `run`. Make `expected_templates` list the files through `run`, splitting its text output on `"\0"`, instead of its own `subprocess.run`.

Re-run `./devctl check --tier full` until the only failure is the diff step naming the eight removed tests that task 19's PR body declares. Expected then: exit 1.

- [ ] **Step 3: Commit.**

```bash
git add -A
git commit -m "chore: adopt the Python guardrail settings in this repository

Fix the findings in rapid_ship and devctl. Each remaining suppression has
an rs-exception entry.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 19: Verify the whole plan

**Files:**
- Modify: this plan's "Verification record"; any guide still out of date

- [ ] **Step 1: Write the PR body.** Write `/tmp/pr-body.md` with a one-paragraph summary of this plan's change and then the section below. Correct each result to the one step 2 observes. Under `## New exceptions`, list every entry this PR adds to `.rapid-ship/exceptions.toml`, one line each with its ID, path, rule and reason: tasks 1 and 2 added EX-1 to EX-3, task 18 the rest, and a merge may add more. `git diff <base>..HEAD -- .rapid-ship/exceptions.toml` shows them all.

```markdown
## Evidence

- `./devctl check --tier fast`: exit 0; every step passed
- `./devctl check --tier full --pr-body /tmp/pr-body.md`: exit 0; diff passed with the declared removals below; evidence passed
- `./devctl check --tier full`: exit 1 without a PR body; diff names the eight removed tests below

Removed tests:
- `tests/test_process.py::test_cancel_before_launch_does_not_execute`: the process runner no longer supports cancellation; plan 1 removed its last callers
- `tests/test_process.py::test_timeout_or_cancel_kills_grandchild_even_if_it_ignores_sigterm`: renamed `test_timeout_kills_grandchild_even_if_it_ignores_sigterm` in `tests/devctl/test_devctl_process.py`, without the cancel case
- `tests/test_repository_navigation.py::test_new_packaged_skill_requires_both_discovery_aliases`: replaced by `test_new_skill_requires_a_claude_alias`; `.agents/skills` is canonical now, so only the Claude alias is required
- `tests/test_repository_navigation.py::test_fails_if_git_cannot_enumerate_the_checkout`: replaced by `test_map_is_blocked_when_git_cannot_list_files`; the map step reports blocked instead of exiting 1
- `tests/test_check.py::test_validation_checks_the_checkout_then_builds_a_temporary_copy`: `scripts/check.py` is deleted; `test_distribution_builds_and_smokes_a_copy_of_the_work_tree` covers the copy, build and smoke, and `test_core_steps_follow_the_spec` the step order
- `tests/test_check.py::test_validation_stops_after_failure_and_cleans_temporary_source`: `scripts/check.py` is deleted; `test_distribution_fails_when_the_build_fails` and `test_distribution_fails_when_the_smoke_fails` cover stopping after a failure
- `tests/devctl/test_devctl_cli.py::test_the_seeded_project_hooks_add_nothing`: this repository's `devctl_project` now adds three steps, pinned by `test_repository_steps`; `test_new_project_passes_devctl_check` runs the empty seed
- `tests/test_kit_contents.py::test_the_python_codeowners_only_adds_pyproject`: renamed `test_the_python_codeowners_only_adds_the_python_settings`; the Python CODEOWNERS now adds the settings file of every Python tool, not only `pyproject.toml`

Not covered: devctl-check.yml on GitHub until this PR's own runs, and the push and nightly runs, which start only after merge.
```

Keep the `Removed tests:` items together, with no blank line between them: the evidence step reads the list up to the first blank line. Every other test that moved keeps its name, so the diff step counts it as moved.

- [ ] **Step 2: Run the checks from a clean tree.** gitleaks 8.30.1 must be on PATH (`gitleaks version`; `brew install gitleaks` reports the version it installs). Without it the secrets step is blocked, and the tests step fails too, because the integration test runs the full tier. If `git symbolic-ref refs/remotes/origin/HEAD` fails, run `git remote set-head origin --auto` first; without that ref the diff step has no base and is not applicable.

```bash
git status --short
uv sync --locked
uv run rapid-ship sync --in-place && git status --short
./devctl check --tier fast; echo "fast exit $?"
./devctl check --tier full; echo "full exit $?"
./devctl check --tier full --pr-body /tmp/pr-body.md; echo "full with body exit $?"
uv run pytest tests/devctl -q
```

Expected:
- Both `git status` runs print nothing, so sync changes nothing.
- The fast tier exits 0 with format, lint, map, exceptions, file-size, kit and vendored passed.
- The full tier without a body exits 1. Only diff fails: it names the eight removed tests from step 1, each ending "(pass --pr-body <file> to check a body locally)". Evidence is not applicable.
- The full tier with the body exits 0. Diff passes against the merge base with `origin/main`, with a "declared" note for each of the eight tests, and evidence passes.
- Record the pytest count.

- [ ] **Step 3: Re-confirm the pins.**

```bash
gh api repos/actions/checkout/git/ref/tags/v7.0.1 --jq .object.sha
gh api repos/astral-sh/setup-uv/git/ref/tags/v10.3.0 --jq .object.sha
gh api repos/gitleaks/gitleaks/releases/tags/v8.30.1 \
  --jq '.assets[] | select(.name=="gitleaks_8.30.1_linux_x64.tar.gz") | .digest'
```

Expected: `3d3c42e5aac5ba805825da76410c181273ba90b1`, `1c37ad07a6a961277cf70c0d37d6f313000f5884` and `sha256:551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.

- [ ] **Step 4: Build the documentation site.**

```bash
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
```

Expected: the build succeeds with no broken links.

- [ ] **Step 5: Check the guides.** Every directory changed by this plan has a current guide: `tools/AGENTS.md` (new), `tests/AGENTS.md`, `.github/AGENTS.md`, `rapid_ship/AGENTS.md`, `rapid_ship/templates/AGENTS.md`, `scripts/AGENTS.md` and the root `AGENTS.md`. The map step's pass in step 2 confirms their links and reachability.

- [ ] **Step 6: Owner step, CI on GitHub.** Push the branch and open the PR with the body from step 1: `gh pr create --body-file /tmp/pr-body.md`. Confirm:
- `gh run list --workflow devctl-check.yml --branch <branch> --limit 1` shows a successful `pull_request` run whose job is named `devctl check`, and its log shows diff passed with the eight declared removals.
- After editing the PR body, a new `pull_request` run starts within a minute.
- After merge, a `push` run on `main` succeeds, and the next day a `schedule` run appears.

Record the run URLs below.

- [ ] **Step 7: Commit the record.**

```bash
git add docs/superpowers/plans/2026-10-14-devctl-check.md
git commit -m "docs: record the devctl check verification

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Verification record

The executor fills each line with the observed result. A skipped or blocked check is recorded as such, never as passed.

- Clean tree and `rapid-ship sync --in-place` no-op: observed on `codex/devctl-check` at 9958c75, before the guide edits. `git status --short` printed nothing before and after `uv sync --locked` and `uv run rapid-ship sync --in-place`, which reported "Kit is current; nothing to sync."
- `./devctl check --tier fast` exit code and step statuses: exit 0. format, lint, map, exceptions, file-size, kit and vendored passed.
- `./devctl check --tier full` without a body, exit code and step statuses: re-run on 2026-10-15 as `./devctl check --tier full --base a6ba3bf`, the head of `codex/rapid-ship-cli`, which the PR targets and which this branch merged as 4800a95 (Remaining limits, "Base"). Exit 1 in 198 seconds. format, lint, map, exceptions, file-size, kit, types, contracts, tests, audit, secrets, workflows, vendored, distribution and python-3.12 passed. Only diff failed: it names the eight removed tests from step 1, each ending "(pass --pr-body <file> to check a body locally)", and lists 30 Protected-path notes. Evidence was not applicable ("not a pull request"). Task 17 ran it with `--base db65920`, plan 2's head at the plan start (controller ruling 1), and measured 2 minutes 45 seconds. With no `--base`, the diff step is based on the merge base with `origin/main` (f7b877b) and lists 406 removed tests. Before `.gitleaks.toml`, the secrets step also failed there, on a `private-key` at `docs/superpowers/plans/2026-10-14-github-commands.md:3274` (commit 55fc5dfa).
- `./devctl check --tier full --pr-body <file>` exit code, diff notes and evidence status: re-run on 2026-10-15 as `./devctl check --tier full --base a6ba3bf --pr-body .superpowers/sdd/2026-10-14-devctl-check/pr-body.md` (the body is under this plan's workspace by controller ruling, not `/tmp`). Exit 0 in 203 seconds. Diff passed with a "declared (<reason>)" note for each of the eight tests and the same 30 Protected-path notes. Evidence passed. vendored, distribution and python-3.12 passed.
- `uv run pytest tests/devctl -q` count: 419 passed in 66.79s. These tests need network access and gitleaks, so they are not offline.
- Pins re-confirmed: yes, on 2026-10-15 with `gh api`. `actions/checkout` v7.0.1 is `3d3c42e5aac5ba805825da76410c181273ba90b1`, `astral-sh/setup-uv` v10.3.0 is `1c37ad07a6a961277cf70c0d37d6f313000f5884`, and gitleaks 8.30.1's `gitleaks_8.30.1_linux_x64.tar.gz` has digest `sha256:551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`. `.github/workflows/devctl-check.yml` and its template carry the same values.
- Documentation build: `npm --prefix website run build` succeeded ("Generated static files"). `npm ci` was skipped by controller ruling, so the build ran against the existing `website/node_modules`. Docusaurus is configured to throw on broken links, anchors and Markdown links, and none were reported.
- Guides: each guide the plan lists matches the final tree, and the map step passed. Two stale statements were fixed in commit b390d98: `docs/AGENTS.md` said the feature and Pattern check arrives with `devctl check`, and the plan index's `kit/` layout omitted `merge.py` and `pull_request.py`.
- Exceptions added in task 18 (IDs and reasons):
  - EX-4, `rapid_ship/kit/git.py`, S603: rapid_ship must not import devctl's process runner, so `git()` starts git itself.
  - EX-5, `rapid_ship/kit/merge.py`, S603: `released_templates` runs uvx with a fixed argv to fetch the locked Kit release; the version is pattern-checked first.
  - EX-6, `rapid_ship/kit/merge.py`, S603: `merge_file` runs `git merge-file` on files in a private temporary directory.
  - EX-7, `rapid_ship/kit/pull_request.py`, S603: `gh pr create` with an argv list and the body on stdin.
  - EX-8, `scripts/smoke_distribution.py`, S603: the standard-library smoke's `run()` starts each command itself.
  - EX-9, `tests/test_kit_cli.py`, skipif: root can read a mode-000 file, so the unreadable-file case cannot happen as root.
  - EX-4 to EX-7 are removed when rapid_ship has a process runner of its own. Task 18's brief put EX-5 to EX-7 in `sync.py`; the split that keeps `sync.py` under 500 lines moved them to `merge.py` and `pull_request.py`.
- Final review fixes (F1 to F4), observed at be2bbc0 on 2026-10-15. The commit after it changes only this record.
  - F3, audit: the step exported the lock without `--all-extras`, so a package that only an extra pulls in was never audited. Fixed in 20a2517. With uv 0.11.0, a scratch project with an extra `yaml = ["pyyaml>=6"]` and a dev group holding `six` exports only `six==1.17.0` without the flag, and `pyyaml==6.0.3` as well with it.
  - F2, Protected set: the seeded CODEOWNERS listed no settings file except `pyproject.toml`, yet a root `.gitleaks.toml` or `ruff.toml` can switch a check off. Fixed in 1c1a7d8. Every stack lists `/.gitleaks.toml`, `/.gitleaksignore`, `/zizmor.yml` and `/zizmor.yaml`. The Python stack adds `/pyproject.toml`, `/**/ruff.toml`, `/**/.ruff.toml`, `/mypy.ini`, `/.mypy.ini`, `/pytest.ini`, `/.pytest.ini`, `/pytest.toml`, `/.pytest.toml`, `/setup.cfg`, `/tox.ini` and `/.importlinter`. This repository's CODEOWNERS, plan 4's `PROTECTED_PATHS` and `PYTHON_PROTECTED_PATHS`, and the plan index follow. Renaming `test_the_python_codeowners_only_adds_pyproject` makes it the eighth removed test.
  - F1, secrets history: `.gitleaks.toml`, in be2bbc0 (Remaining limits, "Secrets history").
  - F4, deferred findings: Remaining limits, "Deferred reviewer findings", grouped for Linear.
  - `./devctl check --tier fast`: exit 0; every step passed.
  - `./devctl check --tier full`, without and with the body: these runs at be2bbc0 used `--base db65920` (exit 1 in 190 seconds, then exit 0 in 185 seconds). The minor fixes below re-ran both with `--base a6ba3bf`; the second and third bullets of this record hold those results.
  - The secrets step on this repository, with the merge base with `origin/main` (f7b877b) and with no base, which scans the whole history as the `push` and `schedule` runs do: passed both times. Without `.gitleaks.toml`, the whole-history scan reports the `private-key` finding in 55fc5dfa.
  - `uv run pytest -q`: 665 passed in 89.81 seconds. `uv run pytest tests/devctl -q`: 422 passed in 59.07 seconds.
- Final review minor fixes (F4 rest, F5, F6, NB1 to NB3), observed on 2026-10-15 with the change that makes them:
  - F5, byte-order mark: `stacks/python.py` parses through `_parse`, which strips one leading U+FEFF. `test_identities`, `tautologies`, `marker_rules` and `autouse_fixtures` all use it, so the diff step and the exceptions step read a file that starts with the mark. Six new test cases failed before the fix: a removed test with the mark at the base and head, at the base only and at the head only; a tautology; a new autouse fixture; and a skip marker in the exceptions step.
  - F4, rest: `test_base_and_pr_body_reach_the_steps` and `test_without_a_change_the_steps_get_no_base_and_no_body` pin what `check_command` hands the steps. The first fails when base and pr_body are swapped or either becomes None (three changes tried). `CheckContext` has its two field comments again.
  - F6: `pr-body.md` and this record name `--base a6ba3bf`. The second and third bullets of this record are the full-tier re-run with that base.
  - NB1 to NB3: Remaining limits ("Base" and "Deferred reviewer findings": two Before Flight bullets and one audit bullet). This plan says eight removed tests throughout.
  - `./devctl check --tier fast`: exit 0; every step passed. `uv run rapid-ship status --strict`: exit 0 (24 managed files unchanged). `npm --prefix website run build`: succeeded.
  - `uv run pytest -q`: 673 passed in 90.20 seconds. `uv run pytest tests/devctl -q`: 430 passed in 59.85 seconds.
- Merge of plan 2's follow-ups, observed at afe82b0 on 2026-10-15. The merge took `codex/rapid-ship-cli` at 5a6c4b5: Kit ownership in place of sync's three-way merge, `init`'s commit on `rapid-ship/init`, git calls without hooks and the `agnostic` stack.
  - `rapid_ship/kit/merge.py` is deleted, and EX-5 and EX-6 with it. `pull_request.py` keeps the pull request helpers and `REVERT`. `sync.py` splits its decision table into helpers so each function stays under complexity 10.
  - devctl's `neutral` names are `agnostic`: `devctl/check/stacks/agnostic.py`, `tests/devctl/test_devctl_agnostic_steps.py`, the lock reader's stacks and the tests. The `kit` step's missing-file message names both choices from spec section 5, and `test_a_kit_file_the_lock_records_as_the_projects_own_is_not_required` covers a Kit file the lock records as seeded.
  - `./devctl check --tier fast`: exit 0; every step passed. `uv run pytest -q`: 703 passed in 108 seconds.
  - `./devctl check --tier full --base 5a6c4b5`: exit 1 in 266 seconds; only diff failed, naming the eight removed tests; evidence was not applicable. With `--pr-body .superpowers/sdd/2026-10-14-devctl-check/pr-body.md`: exit 0 in 223 seconds; diff passed with the eight declarations and 30 Protected-path notes, and evidence passed.
- Second merge of plan 2, observed at db57ed0 on 2026-10-15. The merge took `codex/rapid-ship-cli` at 9c89201: `init` lists the tool settings, hooks and workflows a repository already has (`rapid_ship/kit/existing_checks.py`, `git.hooks_setup`), and a too deeply nested `pyproject.toml` is listed as unreadable.
  - `hooks_setup` and `git()` share `git.py`'s `_run`, whose process call keeps EX-4. EX-10 covers the `skipif` on the unreadable-hooks-directory test. The three command-line tests of the listing moved to `tests/test_kit_init_existing_checks.py`, so `tests/test_kit_cli.py` stays under 500 lines.
  - `./devctl check --tier fast`: exit 0; every step passed. `uv run pytest -q`: 756 passed in 156 seconds. `uv run rapid-ship status --strict`: exit 0 (24 managed files unchanged).
  - `./devctl check --tier full --base 9c89201`: exit 1 in 299 seconds; only diff failed, naming the eight removed tests; evidence was not applicable. With `--pr-body .superpowers/sdd/2026-10-14-devctl-check/pr-body.md`: exit 0 in 286 seconds; diff passed with the eight declarations and 30 Protected-path notes, and evidence passed.
- Fix round 1 after the second merge (F1 to F5), observed on 2026-10-15 with the change that makes them:
  - F1: `pr-body.md`'s "New exceptions" lists all eight entries that `git diff 9c89201..HEAD -- .rapid-ship/exceptions.toml` adds. EX-1 to EX-3 (devctl's templates: S603 in `process.py`, BLE001 in `check/__init__.py`, S603 and S607 in `repo.py`) were missing, because step 1 of the last task asked only for task 18's entries. Step 1 now asks for every entry the PR adds.
  - F2: the `[kit] exclude` tests moved from `tests/test_kit_sync_ownership.py` to `tests/test_kit_sync_exclude.py`, so no test file is over 500 lines (390 and 136 lines). The diff step treats a moved test as kept.
  - F3: `pr-body-publish.md`, a stale copy written before both merges, is deleted. `pr-body.md` is the one body the owner publishes, and it ends with the Claude Code attribution line.
  - F4: plan 4's Global Constraints and Task 2 step 6 keep both choices of the `kit` step's message, `rapid-ship sync --revert <path>` and `rapid-ship sync`, each as the full `uvx --from` command. Plan 4 names `devctl/check/stacks/agnostic.py` and the `agnostic` stack. Only Task 12 step 2 still says `--stack neutral`; plan 2's cascade list names that step with `init`'s commit on `rapid-ship/init`.
  - F5: the plan index's `kit/` layout lists `existing_checks.py` (`find_existing_checks`) and `git.hooks_setup`.
  - `./devctl check --tier fast`: exit 0; every step passed. `uv run pytest -q`: 756 passed in 121 seconds. `uv run rapid-ship status --strict`: exit 0 (24 managed files unchanged).
  - `./devctl check --tier full --base 9c89201 --pr-body .superpowers/sdd/2026-10-14-devctl-check/pr-body.md` at 7875ec2: exit 0 in 244 seconds; diff passed with the eight declarations and 30 Protected-path notes, and evidence passed. The run without a body was not repeated.
- CI runs (pull_request, edited body, push, schedule): PR proxy-hatch/rapid-ship#30, `feat: add devctl check, its CI workflow and pre-commit hook`, opened 2026-10-15 against `codex/rapid-ship-cli`. Read on 2026-10-15 with `gh pr checks 30 --repo proxy-hatch/rapid-ship`, `gh run list` and the job logs, all read-only.
  - `pull_request` at 07e685a, when the PR opened: passed. That head predates both merges of plan 2's follow-ups.
  - `pull_request` at f6dd8c7: failed. `tests` and `python-3.12` each failed with `3 failed, 753 passed`. `rapid-ship init` stopped with `git commit failed: Author identity unknown` in `tests/devctl/test_devctl_check_integration.py` (`test_new_project_passes_devctl_check[agnostic]` and `test_a_project_verb_and_check_step_extend_devctl` are named in the log). `init` now commits the Kit on `rapid-ship/init`, and the runner has no git identity; a machine with a global identity hid it. Every other step passed, including secrets, evidence, and diff with the eight removals declared.
  - Edited body: the PR body was edited at 06:58:24Z, and a new `pull_request` run at f6dd8c7 started at 06:58:27Z; it is the failed run above. It cancelled the `pull_request` (synchronize) run that pushing f6dd8c7 had started at 06:58:10Z; no `push` run has happened yet. That the edit started it is inferred from the times; the event's action was not read.
  - 8b4abff gives the integration tests' scratch repository its own git identity. `pull_request` at 8b4abff: the job `devctl check` passed in 1m33s, and every step passed: format, lint, map, exceptions, file-size, kit, types, contracts, tests, audit, secrets, workflows, diff (eight removals declared), evidence, vendored, distribution and python-3.12. The Docs `build` passed, and Docs `deploy` was skipped, because it runs only on pushes to `main`. `gh pr checks 30 --repo proxy-hatch/rapid-ship` exited 0.
  - Not yet observed: the `push` run on `main` after merge, and the next day's `schedule` run.
  - These results apply to 8b4abff. The merge of `codex/rapid-ship-cli` that brings in the Claims design, and this record commit, get their own runs when the owner pushes them.
  - Run URLs: 07e685a https://github.com/proxy-hatch/rapid-ship/actions/runs/38679343891; f6dd8c7, cancelled https://github.com/proxy-hatch/rapid-ship/actions/runs/38695655091 and failed https://github.com/proxy-hatch/rapid-ship/actions/runs/38695683937; 8b4abff https://github.com/proxy-hatch/rapid-ship/actions/runs/38696503478, Docs https://github.com/proxy-hatch/rapid-ship/actions/runs/38696503386.
- Linear issues for the deferred findings: the deferred findings are recorded in Remaining limits, "Deferred reviewer findings". Filing them in Linear is the owner's choice; this run made no change in Linear. Filed or not, the three "Before Flight" items there still block Flight.
- Remaining limits:
  - **Base.** The PR targets `codex/rapid-ship-cli`, which contains plans 1 and 2. This branch merged it at a6ba3bf (4800a95), at 5a6c4b5 (afe82b0) and at 9c89201 (db57ed0). The full-tier runs in this record use `--base a6ba3bf`, except the merges', which use the merged head as the base; tasks 17 to 19 and the final review used `--base db65920`, plan 2's head at the plan start (controller ruling 1). Against `origin/main` (f7b877b) the diff step listed 406 undeclared removals when task 17 measured it, because plans 1 and 2 are not merged.
  - **Secrets history (fixed in be2bbc0; the owner approves the file in the PR).** Commit 55fc5dfa adds `docs/superpowers/plans/2026-10-14-github-commands.md:3274`, a test fixture that assigns a placeholder PEM string (a header, the text `MIIE` and a footer) to a variable. gitleaks reports it as `private-key`. It is a false positive. The commit is in db65920 and HEAD, not in `origin/main`, and it is on `origin/codex/rapid-ship-cli`, `origin/codex/remove-controller` and `origin/claude/trust-first-agentic-playbook-ba4700`. Without a fix:
    - The plan's literal `./devctl check --tier full` cannot end with "only diff fails" in this repository. It also fails secrets, and it passes secrets only when the range starts at db65920.
    - A PR against `origin/main` fails secrets and diff. After plans 1 and 2 merge, the `push` and `schedule` runs scan the whole history and fail on it.
    - Editing the file does not help, because gitleaks reads commits. An inline allow comment for gitleaks, added to the line in a later commit, left the finding in place. (The exceptions step flags that comment's literal text even inside a document, so it is not quoted here.)
    - Each option below was tried on 2026-10-15 with gitleaks 8.30.1 in a scratch clone, using the secrets step's own command: `gitleaks git --no-banner --redact ... .` with no `--config` and a scrubbed environment.
      - **A `.gitleaks.toml` at the repository root.** The step reads it. A path allowlist is keyed on the path, so it survives a squash or rebase merge. The file must start with `[extend]` and `useDefault = true`. Without them gitleaks drops its default rules, and the step passed while a synthetic token sat in another file. Add `condition = "AND"` and a `regexes` entry beside `paths` to exempt only the placeholder, so a real key added to that file is still caught. With such a file in the scratch clone, a planted synthetic token was still found, `./devctl check --tier fast` exited 0 (the map step accepts the new root file), and `./devctl check --tier full` exited 0. In that clone the diff step compared HEAD with itself, so its pass says nothing about the diff.
      - **A `.gitleaksignore` line** with the fingerprint `55fc5dfa64d9b674c56bc7cd278890fa0890ef59:docs/superpowers/plans/2026-10-14-github-commands.md:private-key:3274`. It clears the finding, but the fingerprint holds the commit hash. A squash merge, or a rebase that rewrites 55fc5dfa, makes the same line a new finding under the new hash (observed in a squash simulation). It holds only if plans 1 and 2 merge with a merge commit that keeps 55fc5dfa.
      - **A rewrite of the history** of plans 1 and 2 so that no commit adds the string. The finding goes away. Every later commit gets a new hash, this branch needs a rebase, and the three published branches above need a force-push.
    - Chosen: the `.gitleaks.toml` option, in be2bbc0, as the final review recommended (F1). It is the only option that holds after a squash or rebase merge and needs no force-push. Its allowlist needs both the document's path and a secret that starts with the placeholder (`condition = "AND"`). `tests/test_gitleaks_settings.py` runs the secrets step with real gitleaks on a scratch repository: a token, the same placeholder under another path and a real-looking key added to the same document are still found. The test fails when the file drops `useDefault`, its regex or its path condition. A squash of the branch into one commit was simulated: its scan passed with the file and found the placeholder without it. The file is Protected (1c1a7d8), so the owner approves it in the PR or replaces it with another option. Run URL that shows secrets passing on GitHub over 55fc5dfa: pending. PR #30's secrets step passed, but a `pull_request` run scans only from the PR's base, which already contains 55fc5dfa; the whole-history `push` or `schedule` run after the merge shows it.
    - One limit: gitleaks's `private-key` match runs from the placeholder to the next "KEY" and five dashes. In a commit that adds the placeholder line itself, such as a squash of plans 1 and 2, a real key placed after it in the same document falls inside that match and is allowed. Any other commit that adds such a key is scanned on its own and fails.
  - **Hosted behaviour, partly verified.** On PR #30, `devctl-check.yml`'s `pull_request` runs ran on GitHub (CI runs above). At 8b4abff the job passed in 1m33s on a warm uv cache (`Cache hit`), and the gitleaks download passed its SHA-256 check. Not measured: the 60-minute timeout on a cold uv cache, the `push` and `schedule` runs, and the ruleset requiring the `devctl check` job. `gh api repos/proxy-hatch/rapid-ship/rulesets --jq length` still printed `0` on 2026-10-15.
  - **Networked tests.** `uv run pytest` needs network access and gitleaks on PATH, because the integration and dog-food tests run the full tier. Spec section 10 asks for offline tests; the networked tests say so in their docstrings. gitleaks here is 8.30.1, the pinned version. The step checks only that gitleaks is on PATH, so another version still runs.
  - **Files the map sees.** `Repo.files` lists tracked files plus untracked files that Git does not ignore, which is stricter than spec map rule 2's tracked files. An untracked, unignored scratch directory fails the map locally.
  - **New-project guides.** The Python root guide links guides that exist only in a new project. Plan 5's `rs-setup` must add those guides, or edit the two rows, in an existing Python project. It already reruns `./devctl check` until it passes.
  - **Live uses of stand-ins.** The `uvx` fetch (EX-5) and the real `gh pr create` (EX-7) run only against stand-ins in tests; the code moved textually unchanged out of `sync.py`.
  - **Deferred reviewer findings, not fixed in this plan.** The task reviewers deferred these as minor; the final review asked that none be lost after the merge. Filing each group as one Linear issue is the owner's choice (Linear line above). Items marked "fail-open" can let a check pass when it should fail.
    - **Before Flight: the settings files in the Protected set** (final review F2). The seeded set lists them since 1c1a7d8, but three gaps remain. A project initialised before that keeps its old seeded CODEOWNERS, because sync never rewrites a seeded file and only reports "template updated". A nested `pyproject.toml` with a `[tool.ruff]` table changes Ruff's settings for its subtree and is not listed. The diff step finds no Protected line while the owners are still the `<owner>` placeholder (diff group below). Flight must not start until the active CODEOWNERS covers every settings file a check step reads.
    - **Before Flight: conflicting extras in the audit step** (final review NB1). `uv export --all-extras` exits 2 for a project that declares conflicting extras, so the audit step is blocked and the full tier exits 2 (measured in the audit bullet below). The step fails closed, but such a project cannot pass `devctl check`. Flight must not start on a project that declares `[tool.uv] conflicts` until the step exports once per extra.
    - **Before Flight: the `/**/` CODEOWNERS entries** (final review NB3). The seeded Python CODEOWNERS writes the ruff entries as `/**/ruff.toml` and `/**/.ruff.toml`. Git's matcher and devctl's `codeowners_match` read them as any depth, but GitHub documents `**/name` without a leading slash. The leading slash keeps the lines inside the pattern that `tests/test_kit_contents.py` and plan 4's test (`# /\S+ @o`) read. On the first pull request that touches a root `ruff.toml`, confirm that GitHub requests the code owner. If it does not, switch to `**/ruff.toml` and `**/.ruff.toml` and change the regex in both tests.
    - **Process runner and test helpers:**
      - No test asserts that `stderr_truncated` is true, so a runner that always reports false passes (`test_explicit_environment_and_output_are_bounded`).
      - The HOME passthrough and the `os.defpath` fallback of `safe_environment` are untested, and its docstring leaves out the fixed locale (`LANG`, `LC_ALL`).
      - `test_waiting_for_a_process_does_not_poll` patches only `time.sleep`, so a loop over `wait(timeout=0.01)` would pass.
      - `tests/conftest.py` imports `check_workspace`, and so devctl, at module level: an import error in devctl fails collection of every test.
      - `tests/conftest.py::_git` ignores `stdout_truncated`; the largest listing is 9 KB against the runner's 1 MiB cap.
    - **Files that the index lists but the work tree lacks.** `Repo.files` uses `ls-files --cached`, so it still lists a file deleted from the work tree but not from the index. Steps that open each path then report blocked, map rule 2 accepts a deleted guide, and `_stray_files` calls a deleted, tracked skill alias a stray file beside a contradictory "add a relative symlink" line.
    - **Map step:**
      - A feature's `reproduce` accepts a command chain such as `./devctl check && <command>`, because only the first two words are checked. Agents are meant to run this field.
      - A `ruff:<code>` reference resolves for any code that starts with a selected prefix, such as `ruff:S99999` under `select = ["S"]`.
      - The "missing target" and "not maintained" messages quote the raw link target, escapes included, not the path that was checked.
      - `[map] unguided` and `source_roots` are compared as written: `"docs/"` or `"./docs"` has no effect, unlike `[map] exclude`.
      - An empty front matter block, or a file that starts with a byte-order mark, is reported as "no front matter". A YAML error is PyYAML's raw text, with no hint to quote a value that contains `: `.
      - The Rules scanner counts only spaces, so a tab-indented nested bullet joins its parent's text and fails the end-marker check.
      - No test pins project verbs in `registered_verbs`, an unreadable guide that `rule_errors` skips, the order of a skill's name and description errors, a Pattern with a missing `reference` or a non-list `enforced_by`, or a feature with a non-list `data`.
      - `without_fences` and `fenced_blocks` each carry their own fence scanner; one shared scanner would keep them in step.
      - `map.py` has 443 of its 500 lines; the document rules could move to a sibling module.
      - Spec section 4's `[map]` table and map rule 2 do not mention `[map] exclude` or `__pycache__` (owner's call: amend the spec).
      - `test_devctl_map_links.py` and `test_devctl_step_order.py` both pin the whole core step list, so each new core step edits both.
    - **Kit step:**
      - The step accepts locks that `rapid-ship status` refuses: an unknown key, a malformed or absent sha256, or a duplicate, non-canonical, `..` or absolute path. An absolute path lets the step look outside the repository. A parity test with `rapid_ship/kit/lock.py` would keep the two readers in step.
      - A managed path of the wrong type, such as a file where a link belongs, is reported as missing.
      - `test_malformed_lock_names_the_problem` checks only each detail's prefix, so a case can pass for the wrong reason.
    - **Exceptions and file-size steps:**
      - Fail-open: `marker_rules` and `autouse_fixtures` return no rows for a file that does not parse, so its skip, xfail and autouse suppressions go unreported, with no detail.
      - Exception paths are compared as written: `./src/app/big.py` matches nothing, and the two resulting messages contradict each other. `load_exceptions` should store the normalised path or reject it.
      - No test shows that a marker on a suppression-free line of a non-Python file is ignored, and the step's `OSError` branch is untested.
      - Splitting a rule's names is written three times (zizmor names, `_codes`, `normal_rule`), and no test runs scanner output through `normal_rule`.
      - Comments in the vendored `python.py`, `neutral.py` and `exceptions.py` name `rapid_ship/kit/adopt.py` and its test, which plan 5 adds and which a project that vendors devctl never has.
    - **Command, audit, secrets and workflows steps:**
      - Fail-open: the audit step counts a dependency with no `vulns` key as clean, so a report whose key is renamed passes. Require `vulns` unless `skip_reason` is present.
      - The audit step's timeouts, and a report with vulnerabilities from a pip-audit that exits 0, have no test.
      - The audit step is blocked on a project with conflicting extras (final review NB1). `uv export --all-extras` exits 2 when `[tool.uv] conflicts` declares extras that cannot be installed together. Measured with uv 0.11.0 on a scratch project whose extras `old` (`six==1.16.0`) and `new` (`six==1.17.0`) conflict: the export prints "error: Extras `new` and `old` are incompatible with the declared conflicts: {`demo[new]`, `demo[old]`}" and exits 2, and the step reports blocked with that message. `uv export --extra old` and `--extra new` each exit 0. If target projects need it, export once per extra and audit each file.
      - `test_missing_tool_is_blocked` asserts the detail but not the blocked status.
      - `output_tail` joins stdout and stderr with no separator, so a last stdout line without a newline merges with the first stderr line. Its truncation note, `command_result`'s blocked message and `run_tool`'s `env` merge have no test.
      - A failed workflows step shows only zizmor's last 40 lines and not the command, so the first findings can be cut.
      - A whole-history secrets scan prints one detail per finding, with no cap.
      - In `neutral.py`, `_ZIZMOR` (a regular expression) and `ZIZMOR` (the tool pin) differ by one underscore.
    - **Evidence step:**
      - A blank line after `Removed tests:`, a bold label or a numbered list ends the list silently. The declared tests are then reported as undeclared, and a declaration line can count as the evidence command.
      - `_DECLARATION` backtracks quadratically on a long run of colons, about a minute at GitHub's 65,536-character body limit. Only the PR author can trigger it.
      - An indented transcript counts, because `_is_transcript` strips the line, but no test pins it.
      - The step parses the body several times per run.
    - **Diff step:**
      - The owner pattern does not match the `<owner>` placeholder that `init` writes without `--owner`, so such a project gets no Protected-path notes until `rs-setup` writes the login.
      - The Protected set is read from the work tree, not from the base that GitHub enforces, so a change that drops a CODEOWNERS line also hides its own edits to that path.
      - `**`, `/*` and `/**` match every path, and `docs/*` matches nested files where GitHub covers only direct children. The effect is extra notes.
      - A test of the same name added in any other changed test file cancels a removal, so a behavioural test can become a unit test without a declaration. This is spec section 5's identity rule (owner's call).
      - No test covers: a declared unit-test removal in Flight carrying no owner-wait suffix, a head read error giving blocked, an added test file or `conftest.py`, a neutral-stack change listed as Protected, the order of the CODEOWNERS locations, or the path order of `changed_files`.
    - **CI workflow and hook templates:**
      - `setup-uv` has no `version`, so each run installs the latest uv, which then runs the pinned pip-audit and zizmor. The plan's test pins the step to `uses` alone.
      - `test_gitleaks_is_pinned_and_verified` does not check that the checksum runs before `tar`, or that the download URL uses `${GITLEAKS_VERSION}`.
      - `test_vendored_copies_match_their_templates` checks the executable bit of this repository's copy, not what sync writes.
    - **Kit templates, init and this repository's steps:**
      - `init` takes the package name from the directory without checking that it shadows a module: a project named `py` fails `contracts`.
      - `rapid_ship/templates/python/AGENTS.md` copies the common root guide and adds two rows. `rapid_ship/templates/AGENTS.md` does not say that the Python stack overrides the guide, and no test pins where the rows go.
      - `SEEDED` in `tests/test_kit_contents.py` lists `docs/AGENTS.md` and `tools/AGENTS.md`, which spec section 4's table of seeded files does not (owner's call: amend the spec).
      - `test_devctl_check_integration.py` never asserts the fast tier's exit code.
      - `copy_work_tree` in `devctl_project` passes a directory entry, such as an untracked nested repository, to `shutil.copy2`, which raises; `copy_this_repository` in `tests/test_kit_dogfood.py` skips it. The two copiers of the same file list differ.
      - `test_python_floor_uses_a_separate_environment` checks that `UV_PROJECT_ENVIRONMENT` is set, not that it points outside the work tree, and the floor step's exit-code mapping has no test.
    - **rapid_ship after the `sync.py` split:**
      - This repository's dev dependency ranges (`pytest>=8,<10`, `ruff>=0.15,<1`, `mypy>=1.15,<2`) are looser than the seeded template's. `uv.lock` pins ruff 0.17.0, mypy 1.20.2 and pytest 9.1.1, and the new suppressions rely on Ruff 0.17 reporting S603 on a call's first line.
      - `rapid_ship/kit/pull_request.py` imports `SyncResult` from `sync` under `TYPE_CHECKING`, while `sync` imports from `pull_request`. The cycle exists only for the type checker.
      - `status.fingerprint` reads link targets with `Path.readlink()`, which normalises `./`, doubled slashes and a trailing slash; the Kit's own links are already normal.
      - `work_tree_root` treats a git failure other than exit 128 as a `KitError` (exit 2), and no test pins that branch.
      - The task 18 split of `sync.py` changed import lines and two patch targets in `tests/test_kit_sync.py` (strict mypy forbids implicit re-exports), so controller ruling 2's "without changing tests" holds in substance, not in letter. No assertion changed.
