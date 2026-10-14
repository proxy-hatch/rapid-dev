# Kit and Setup: plan index

**Spec:** [Spec 1: Kit and Setup](../specs/2026-10-14-kit-and-setup-design.md), part of the [rapid-ship design](../specs/2026-10-14-rapid-ship-design.md).

Spec 1 is built as five plans, in this order. Each one ends with a working, tested repository and its own PR.

| Order | Plan | Spec sections | Depends on |
| --- | --- | --- | --- |
| 1 | [Remove the old controller](2026-10-14-remove-controller.md) | 2 | — |
| 2 | [The rapid-ship CLI](2026-10-14-rapid-ship-cli.md): templates, lock, `init`, `status`, `sync`, dog-food init | 3, 4 | 1 |
| 3 | [`devctl check`](2026-10-14-devctl-check.md), the CI workflow and the hook; this repository switches to `./devctl check` | 4, 5 | 2 |
| 4 | [GitHub commands](2026-10-14-github-commands.md): `rapid-ship app`, `devctl doctor`, `dispatch`, `pr`, `review` | 3, 6 | 3 |
| 5 | [Kit skills](2026-10-14-kit-skills.md): forked engineering skills, `rs-setup`, `rs-health`, `rs-contribute`, `rapid-ship adopt` | 3, 7, 8, 9 | 4 |

No part of plan 5 can start before plan 3 merges. Until plan 3 deletes `scripts/check_repository.py`, its skill-alias check fails on every vendored `rs-` skill, because it accepts only skills under `rapid_ship/skills/`. `rs-setup` also needs plan 4.

This index fixes the layout and the names, signatures and formats that more than one plan uses. A plan that needs a different one changes this file in the same PR. Where plans disagreed, the plan that defines the thing wins: plan 2 owns templates, lock, settings and repo; plan 3 owns check, process and suppressions; plan 4 owns GitHub, doctor, dispatch and the gate log; plan 5 owns skills and `adopt`. [Resolved disagreements](#resolved-disagreements) lists each choice.

## Conventions for every plan

- Every command in both CLIs is one word followed by arguments:
  - `rapid-ship init [--stack {python,neutral}] [--owner LOGIN] [--repository OWNER/NAME] [--name NAME] [--package NAME]`
  - `rapid-ship status [--strict] [--json]`, `rapid-ship sync [--in-place]`, `rapid-ship app [--repository OWNER/NAME]`, `rapid-ship adopt`
  - `devctl check [--tier {fast,full}] [--json] [--base REV] [--pr-body PATH]`, `devctl doctor [--skills]`
  - `devctl dispatch <ISSUE> [--retry]`, `devctl dispatch --status`, `devctl dispatch --clean`
  - `devctl pr [--title TEXT] [--body PATH]`, `devctl review <PR> --verdict PATH`
- Exit codes in both CLIs: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run. When both 1 and 2 apply, 2 wins. `KitRefusal` and `AdoptRefused` exit 1. `KitError`, `SettingsError`, `RepoError` and `DevctlError` exit 2.
- Write tests first. Label offline and simulated tests as such. A blocked or skipped step never counts as passed.
- Python 3.12 or later; `uv` runs everything. Settings are TOML, read with `tomllib`.
- Branch names for this work use the `codex/` prefix until plan 1 rewrites that rule, then any prefix except `rs/`.
- devctl source is edited only under `rapid_ship/templates/common/tools/devctl/`. Then run `uv run rapid-ship sync --in-place`, which accepts a dirty work tree. Commit the template, the vendored copy and `.rapid-ship/kit.lock` together.
- devctl starts processes only through `process.run_process`, called through the module (`from devctl import process`). The one other caller is `repo._git` (EX-3). `rapid_ship` never imports devctl (import-linter forbidden contract, plan 3 Task 18).
- From plan 3 Task 18 on, the Python guardrail settings cover `rapid_ship`, devctl and `tests/`: no `print`, no `Any` in a signature, complexity at most 10, every test annotated. Each suppression carries an `rs-exception` marker and an entry.
- From plan 3 Task 16 on, `uv run pytest` and `./devctl check --tier full` need network access and gitleaks 8.30.1 on `PATH`.
- The Kit version is the rapid-ship package version. Each Kit release is a tag `v<version>` on `main`, created by the owner. Run `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>`, or `--from <local checkout>` before the first tag. `sync` fetches its merge base from the tag `v<old>`; without that tag it lists every needed merge as a conflict. PyPI publishing is a later, separate change.
- Each plan's last task runs `uv run python scripts/check.py` (plans 1–2) or `./devctl check` (plans 3–5), builds the docs site with `npm --prefix website run build`, and records the actual results in the plan.

## Layout after all five plans

```text
rapid_ship/                      # the rapid-ship CLI package, run with uvx
  __init__.py
  __main__.py
  cli.py                         # build_parser(), main(argv); init, status, sync, app, adopt
  files.py                       # atomic_replace, UnsafePath, relative_parts, safe_path, create_file
  github_app.py                  # rapid-ship app: manifest flow, Keychain storage (plan 4)
  upstream.lock                  # upstream files of forked skills (plan 5)
  kit/
    __init__.py
    templates.py                 # Stack, Kind, Template, KitManifest, KitError, KitRefusal, load_manifest, render_files, read_excluded, is_excluded
    lock.py                      # Lock, LockEntry, LOCK_PATH, read_lock, write_lock, file_sha256, entry_for
    git.py                       # git, work_tree_root, is_clean
    init.py                      # init_repository, resolve_variables, InitResult
    status.py                    # classify, StatusReport, FileStatus, locate, fingerprint
    sync.py                      # sync_repository, SyncResult, Conflict
    adopt.py                     # adopt_suppressions (plan 5)
  templates/
    kit.toml                     # manifest; see "Kit manifest" below
    common/                      # files for every stack, laid out as in a project
    python/                      # Python stack additions and overrides
    neutral/                     # stack-neutral additions
tests/
  conftest.py                    # the only conftest; plan 4 adds pytest_plugins = ["github_fixtures"]
  test_files.py test_kit_*.py    # rapid-ship CLI tests
  fixtures/upstream/<repository>/<commit>/<path>   # pristine upstream files (plan 5)
  devctl/                        # no __init__.py, no conftest.py; files named test_devctl_*.py
    check_workspace.py           # project_settings, gate_settings, Workspace, new_workspace, fake_tool (plan 3)
    github_fakes.py github_fixtures.py fixtures/github/   # plan 4
scripts/smoke_distribution.py    # wheel and installed smoke; plan 3 deletes check.py and check_repository.py
devctl, tools/devctl/            # this repository's vendored Kit, from its own init and sync
.agents/skills/rs-*, .claude/skills/rs-*   # vendored Kit skills; rapid_ship/skills/ is gone after plan 5
```

`pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["tools/devctl", "tests/devctl"]` (plan 3 Task 2), so tests import the vendored devctl and its test helpers.

devctl inside any project:

```text
devctl                           # sh shim: unset UV_PROJECT_ENVIRONMENT; exec uv run --project "<root>/tools/devctl" --frozen --quiet devctl "$@"
tools/AGENTS.md                  # seeded (plan 3)
tools/devctl/
  pyproject.toml                 # name "devctl"; [project.scripts] devctl = "devctl.cli:main"; [tool.uv.workspace] members = []
  uv.lock
  .gitignore
  devctl/
    __init__.py                  # __version__
    cli.py                       # build_parser, main; core verbs, then devctl_project.register
    repo.py                      # Repo, RepoError
    settings.py                  # Agent, ProjectSettings, GateSettings, ExceptionEntry, load_*, SettingsError
    process.py                   # ProcessResult, safe_environment, run_process (moved from rapid_ship, plan 3)
    check/                       # plan 3
      __init__.py                # run_check, core_steps, all_steps, exit_code, resolve_change, ChangeError
      steps.py                   # Step, StepResult, CheckContext, CommandStep, step helpers
      markdown.py map.py references.py exceptions.py filesize.py kit.py diff.py evidence.py
      stacks/__init__.py stacks/python.py stacks/neutral.py
    github/                      # plan 4
      __init__.py
      api.py                     # GitHubApi: minimal REST client over http.client
      app.py                     # App keys, tokens, GitHubAccess, token-bearing git
      askpass.py                 # GIT_ASKPASS helper, standard library only
    doctor.py dispatch.py pr.py review.py   # plan 4; each has register(commands)
    harness.py                    # plan 4: PROBE_MODELS, AGY_PROBE_ARGS, the skills probe
  devctl_project/                # seeded: project verbs and extra check steps
    __init__.py
```

devctl depends only on PyYAML (`pyyaml>=6.0.3,<7`, plan 3) and `PyJWT[crypto]>=2.10,<3` (plan 4). The root dev group adds the same two, plus `types-pyyaml`, so `tests/devctl` can import devctl. pip-audit 2.10.1 and zizmor 1.30.1 run with `uv tool run --from <pin>` and are not dependencies; gitleaks 8.30.1 is a binary on `PATH`. The rapid-ship CLI depends only on `tomli-w`.

A project whose root `[tool.uv.workspace] members` match `tools/devctl` must list it under `exclude`, or its own `uv lock` fails. `init` never edits that file: `rs-setup` adds the exclude (plan 5) and `devctl doctor` reports it missing (plan 4).

## Shared interfaces

### Files and git helpers (plan 2)

```python
# rapid_ship/files.py
def atomic_replace(path: Path, content: bytes, *, mode: int = 0o600) -> None: ...


class UnsafePath(ValueError): ...


def relative_parts(relative: str) -> tuple[str, ...]: ...  # refuses absolute, "..", backslashes
def safe_path(root: Path, relative: str) -> Path: ...  # refuses every symlink below root
def create_file(
    path: Path, content: bytes, *, executable: bool = False
) -> None: ...  # never overwrites


# rapid_ship/kit/git.py
def git(
    root: Path,
    *args: str,
    stdin: bytes | None = None,
    allowed: tuple[int, ...] = (0,),
    literal: bool = True,
) -> bytes: ...  # git --literal-pathspecs; literal=False omits it, for check-ignore only
def work_tree_root(start: Path) -> Path: ...
def is_clean(root: Path) -> bool: ...
```

### Templates, Kit manifest and lock (plan 2)

```python
# rapid_ship/kit/templates.py
Stack = Literal["python", "neutral"]
Kind = Literal["managed", "seeded"]


class KitError(Exception): ...  # exit 2


class KitRefusal(Exception): ...  # exit 1


@dataclass(frozen=True)
class Template:
    path: str  # project-relative POSIX path, variables already substituted
    kind: Kind
    content: bytes | None  # None for a symlink
    link: str | None  # "../../.agents/skills/<name>", for .claude/skills/<name>


@dataclass(frozen=True)
class KitManifest:  # the five kit.toml lists
    seeded: frozenset[str]
    new_project: frozenset[str]
    executable: frozenset[str]
    optional_skills: frozenset[str]
    variables: frozenset[str]


def load_manifest(root: Path | None = None) -> KitManifest: ...  # None: the packaged templates
def render_files(
    stack: Stack, variables: Mapping[str, str], optional: Sequence[str], *, root: Path | None = None
) -> list[Template]: ...
def read_optional_skills(root: Path) -> tuple[str, ...]: ...  # [kit] optional in project.toml
def read_excluded(root: Path) -> tuple[str, ...]: ...  # [kit] exclude, normalised
def is_excluded(path: str, excluded: Sequence[str]) -> bool: ...  # the entry or below it
def installed_version() -> str: ...  # package version; PackageNotFoundError if not installed


# rapid_ship/kit/lock.py
@dataclass(frozen=True)
class LockEntry:
    path: str
    kind: Kind
    sha256: str | None  # managed files
    link: str | None  # managed symlinks
    template_sha256: str | None  # seeded files


@dataclass(frozen=True)
class Lock:
    kit_version: str
    stack: Stack
    variables: Mapping[str, str]
    entries: tuple[LockEntry, ...]


LOCK_PATH = ".rapid-ship/kit.lock"


def read_lock(root: Path) -> Lock: ...
def write_lock(root: Path, lock: Lock) -> None: ...  # entries sorted by path, mode 0o644
def file_sha256(content: bytes) -> str: ...
def entry_for(template: Template) -> LockEntry: ...
```

`rapid_ship/templates/kit.toml` after all five plans. Paths are relative to `common/` or a stack directory, before substitution. Every other template is managed.

```toml
seeded = [".github/CODEOWNERS", ".rapid-ship/exceptions.toml", ".rapid-ship/gate.toml",
  ".rapid-ship/project.toml", "AGENTS.md", "CLAUDE.md", "docs/AGENTS.md", "docs/features/README.md",
  "docs/patterns/README.md", "tools/AGENTS.md", "tools/devctl/devctl_project/__init__.py"]
new_project = [".gitignore", "pyproject.toml", "src/AGENTS.md", "src/__package__/__init__.py",
  "tests/AGENTS.md", "tests/test_import.py"]   # seeded only when init starts a Python project
executable = ["devctl", ".githooks/pre-commit", "tools/devctl/devctl/github/askpass.py"]
optional_skills = ["rs-contribute"]
variables = ["owner", "package", "project_name", "repository"]
```

Plan 2 adds `devctl` and the `devctl_project` seed. Plan 3 adds the hook and the `AGENTS.md` and `.gitignore` seeds. Plan 4 adds `askpass.py`, and plan 5 adds `rs-contribute`.

`.rapid-ship/kit.lock` is TOML: `kit_version`, `stack`, a `[variables]` table of the four variables, then one `[[file]]` per entry. A managed file has `sha256`, a managed link has `link`, and a seeded file has only `template_sha256`.

Template rules:

- Managed templates are copied byte for byte, so a managed file's hash is the same in every project.
- Only seeded files substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`. A template directory named `__package__` becomes the package name. An empty variable renders as `<name>` and comments out its line in a TOML file or CODEOWNERS; elsewhere it is a `KitError`.
- `.claude/skills/<name>` is always a relative symlink, generated from `.agents/skills/<name>/`. When a symlink cannot be made, `init` and `sync` exit 2 and leave nothing half-written.
- Template discovery skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files, and, when the template root's `kit.toml` is tracked by git, every path git does not keep.
- The execute bit comes only from `executable`: `init` creates a listed path with mode `0o777` less the umask, and `sync` keeps a file's mode, adding execute bits for a listed path. A template's own git mode never reaches a project. List a new executable template before its first sync, so its vendored copy is tracked `100755`.
- `sync` creates a seeded template that a newer Kit adds only where nothing exists at its path, and records it either way. It never adds a new-project seed.

### Settings (plan 2; plan 3 adds `map_exclude`)

```python
# devctl/settings.py
PROJECT = ".rapid-ship/project.toml"
GATE = ".rapid-ship/gate.toml"
EXCEPTIONS = ".rapid-ship/exceptions.toml"


class SettingsError(Exception): ...  # missing or invalid file; unknown keys are errors


@dataclass(frozen=True)
class Agent:
    harness: Literal["claude", "codex", "agy"]
    model: str  # kept exactly


@dataclass(frozen=True)
class ProjectSettings:
    stack: Literal["python", "neutral"]
    worker: Agent | None
    reviewer: Agent | None
    repository: str | None  # "owner/name"
    worker_app_id: int | None  # 0 in the file means unset
    reviewer_app_id: int | None
    linear_team_id: str | None
    linear_project_id: str | None
    optional_skills: tuple[str, ...]  # [kit] optional
    excluded: tuple[
        str, ...
    ]  # [kit] exclude: Kit paths the project owns; a skill directory also covers its .claude/skills link
    max_workers: int  # default 5
    attempt_limit: int  # default 3
    worktree_root: str  # default "../<repo>.worktrees"
    source_roots: tuple[str, ...]  # [map] source_roots
    unguided: tuple[str, ...]  # [map] unguided
    map_exclude: tuple[str, ...]  # [map] exclude, default (); plan 3 Task 4
    unit_tests: tuple[str, ...]  # [tests] unit; default ("tests/unit/**",)
    release_method: Literal["github-deployments", "tags", "none"]


@dataclass(frozen=True)
class GateSettings:
    mode: Literal["walk", "flight"]
    flight_lease_until: str | None
    owner_approves_behavioural_test_removal: bool  # default True


@dataclass(frozen=True)
class ExceptionEntry:
    id: str  # "EX-<n>", n >= 1, unique
    path: str
    rule: str
    reason: str
    remove_when: str


def load_project(root: Path) -> ProjectSettings: ...
def load_gate(root: Path) -> GateSettings: ...
def load_exceptions(root: Path) -> list[ExceptionEntry]: ...
```

### Repository, process and CLI (plans 2 and 3)

```python
# devctl/repo.py (plan 2; plan 3 adds files and git)
class RepoError(Exception): ...


@dataclass(frozen=True)
class Repo:
    root: Path
    git_common_dir: Path  # shared by every worktree of the clone

    @classmethod
    def discover(cls, start: Path) -> Repo: ...
    def tracked_files(self) -> list[str]: ...
    def merge_base(self, ref: str) -> str | None: ...
    def files(self) -> list[str]: ...  # tracked plus untracked files git does not ignore
    def git(self, *args: str) -> str: ...  # RepoError when git fails


# devctl/process.py (plan 3)
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


# devctl/cli.py (plan 2)
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: Sequence[str] | None = None) -> int: ...  # calls args.handler(args)


# devctl_project/__init__.py (seeded)
def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...
def check_steps() -> list[Step]: ...  # plan 2 seeds list[object]; plan 3 narrows it
```

`run_process` gives the child only `safe_environment(env)`: the caller's `PATH` and `HOME`, `LANG` and `LC_ALL` set to `C.UTF-8`, then `env`. It has no cancellation, and it reports truncation in the two flags, never inside the output. Every verb sets `handler`, a callable that takes `argparse.Namespace` and returns the exit code. `rapid_ship/cli.py` has the same `build_parser()` and `main(argv: Sequence[str] | None = None) -> int`.

### Check steps (plan 3)

```python
# devctl/check/steps.py
Tier = Literal["fast", "full"]
Status = Literal["passed", "failed", "blocked", "not_applicable"]


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
    base: str | None  # base commit for the diff policy; None outside a change
    pr_body: str | None  # from GITHUB_EVENT_PATH or --pr-body; None outside a PR


class Step(Protocol):
    name: str
    tier: Tier

    def run(self, context: CheckContext) -> StepResult: ...


def passed(name: str, *details: str) -> StepResult: ...  # also failed, blocked, not_applicable


@dataclass
class CommandStep:  # exit 0 passes, failed_codes fail, anything else blocks
    name: str
    tier: Tier
    argv: tuple[str, ...]
    failed_codes: frozenset[int] = frozenset({1})
    timeout_seconds: float = 1800.0


# devctl/check/__init__.py
def all_steps(
    project: ProjectSettings,
) -> list[Step]: ...  # core steps, then devctl_project.check_steps()
def run_check(context: CheckContext, tier: Tier) -> list[StepResult]: ...


# devctl/check/kit.py: devctl reads the lock itself and ignores [variables]
LOCK_PATH = ".rapid-ship/kit.lock"


class KitLockError(Exception): ...


def is_excluded(
    path: str, excluded: Sequence[str]
) -> (
    bool
): ...  # devctl's copy of rapid_ship.kit.templates.is_excluded; a parity test keeps them equal
def managed_paths(
    root: Path, excluded: Sequence[str]
) -> frozenset[str]: ...  # managed lock paths is_excluded does not cover
```

Step order: fast is `format`, `lint`, `map`, `exceptions`, `file-size`, `kit`; full adds `types`, `contracts`, `tests`, `audit` (pip-audit), `secrets` (gitleaks), `workflows` (zizmor), `diff`, `evidence`. The neutral stack has no `format`, `lint`, `types`, `contracts`, `tests` or `audit` step. `--json` prints a list of `{"name", "status", "details"}` objects.

### Suppressions and exceptions (plan 3; plan 5's `adopt` copies the Python rows)

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

- Several codes join sorted, separated by `,` (`E501,F401`). An entry's `rule` is normalised the same way.
- The marker is `rs-exception: EX-<n>` on the suppression's line, after it: `# noqa: S603  # rs-exception: EX-1`. Each marker matches one rule, so a line with two rules needs two markers and two entries.
- Each ID is used on exactly one line, and an entry that no marker carries fails as stale. File-size entries use `rule = "file-size"` and no marker.
- Kit-managed files that are not excluded under `[kit] exclude` are not scanned. The seeded `exceptions.toml` holds comments only, so `adopt` can append `[[exception]]` tables.
- The rule code lives in `devctl/check/stacks/python.py` (`comments`, `comment_rules`, `marker_rules`) and `stacks/neutral.py` (`text_rules`). `devctl/check/exceptions.py` exports `MARKER`, `SuppressedLine(path, number, rules, optional, markers)` and `scan(root: Path, files: Sequence[str], managed: frozenset[str], stack: str) -> list[SuppressedLine]`. `rapid_ship/kit/adopt.py` cannot import devctl, so it copies the Python rows. `tests/devctl/test_devctl_adopt_rules.py` fails when the copies differ.

### PR body (plan 3 reads it; plan 5's `rs-pr` writes it)

```markdown
## Evidence

- `<command>`: <its result>

Removed tests:
- `<path>::<name>`: <reason>

Not covered: <what the evidence does not show>
```

- A command line is a list item that starts with a code span, a colon and text. A fenced block also counts when its first non-empty line starts with `$ ` and another non-empty line follows.
- `Not covered:` starts a line outside code, with text after the colon.
- `Removed tests:` is optional and read only inside `## Evidence`. Backticks around the identity are optional. `<name>` is `test_x` or `TestA::test_x`.

### Feature and Pattern front matter (plan 2 seeds the READMEs; plan 3 checks them)

| File | Front matter |
| --- | --- |
| `docs/features/*.md` except `README.md` | `purpose`: non-empty text. `entry_points`: non-empty list of existing paths. `data`: list of existing paths, possibly empty. `observe`: non-empty text. `reproduce`: `./devctl <verb> ...`, where the verb is registered |
| `docs/patterns/*.md` except `README.md` | `reference`: an existing path. `enforced_by`: non-empty list of references that resolve |

References: `check:<step>`, `test:<path>::<name>`, and for Python `ruff:<code>`, `banned:<module.member>`, `contract:<name>` and `type:<path>` (spec section 5).

### CODEOWNERS (plan 2 seeds it; plans 3, 4 and 5 read or write it)

- Walk has one active line, `* @<owner>`. Without `--owner`, `init` writes it as `# * @<owner>`, and `rs-setup` writes the line.
- The Protected set follows, commented out, as `# /<path> @<owner>` lines: `/.github/`, `/.githooks/`, `/devctl`, `/tools/devctl/`, `/.agents/skills/`, `/.claude/skills/`, `/.rapid-ship/`, `/pyproject.toml`. Flight uncomments them and removes the `*` line.
- `/pyproject.toml` appears only in the Python stack's template.
- The diff step reads `<pattern> @<owner>` lines, commented or not, and never treats `*` as Protected. doctor accepts each path with or without the leading `/`, and requires `pyproject.toml` only for the Python stack.

### GitHub (plan 4)

```python
# devctl/github/api.py: REST over http.client, which never follows a redirect
API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"


class GitHubError(Exception):
    status: int | None


class GitHubApi:
    def __init__(self, token: str, *, base_url: str = API_URL) -> None: ...
    def request(self, method: str, path: str, body: object | None = None) -> object: ...
    def paginate(self, path: str) -> list[object]: ...


def json_object(value: object, what: str) -> dict[str, object]: ...
def json_list(value: object, what: str) -> list[object]: ...


# devctl/github/app.py
AppRole = Literal["worker", "reviewer"]
KEYCHAIN_SERVICE: dict[AppRole, str] = {
    "worker": "rapid-ship/worker-app",
    "reviewer": "rapid-ship/reviewer-app",
}
APP_PERMISSIONS: dict[AppRole, dict[str, str]]  # spec section 3


class DevctlError(Exception): ...  # exit 2


class AppError(DevctlError): ...


class KeychainMissing(AppError): ...


class GitError(DevctlError): ...


def installation_token(
    role: AppRole,
    repository: str,
    app_id: int,
    *,
    keychain: Keychain | None = None,
    api_url: str = API_URL,
) -> str: ...


@dataclass(frozen=True)
class GitHubAccess:
    repository: str
    api_url: str = API_URL
    remote_url: str | None = None  # None: https://github.com/<repository>.git
    keychain: Keychain | None = None  # None: MacKeychain()

    def token(self, role: AppRole, app_id: int) -> str: ...
    def api(self, token: str) -> GitHubApi: ...


def project_access(project: ProjectSettings) -> GitHubAccess: ...
def run_guarded(action: Callable[[], int]) -> int: ...  # known errors -> stderr, exit 2
def run_git(
    cwd: Path, args: Sequence[str], token: str, *, url: str, timeout_seconds: float = 120.0
) -> ProcessResult: ...


@dataclass(frozen=True)
class PushOutcome:
    pushed: bool
    rejection: str | None


def ls_remote_heads(cwd: Path, url: str, token: str, pattern: str) -> dict[str, str]: ...
def remote_default_branch(cwd: Path, url: str, token: str) -> str: ...
def fetch_ref(cwd: Path, url: str, token: str, ref: str) -> str: ...
def push_ref(
    cwd: Path, url: str, token: str, refspec: str, *, create_only: str | None = None
) -> PushOutcome: ...


# devctl/doctor.py
def ruleset_problems(
    rulesets: Sequence[Mapping[str, object]], default_branch: str
) -> list[str]: ...
# devctl/check/kit.py, added by plan 4
def kit_summary(
    root: Path, excluded: Sequence[str]
) -> KitSummary: ...  # kit_version, unchanged, modified, missing, excluded; excluded from ProjectSettings.excluded


AGY_PROBE_ARGS: tuple[
    str, ...
]  # devctl/harness.py, re-exported by devctl/doctor.py; plan 5 imports it


# devctl/check/stacks/python.py, added by plan 4
def guardrail_gaps(pyproject: Mapping[str, object]) -> list[str]: ...
```

- A token lives in memory only, one per command. git receives it only through `devctl/github/askpass.py`, which reads `RAPID_SHIP_GIT_TOKEN`.
- `rapid_ship/github_app.py` keeps its own `KEYCHAIN_SERVICE` and `APP_PERMISSIONS`. A parity test in `tests/devctl/test_devctl_github_app.py` keeps them equal to devctl's.
- Keychain items written by `security` are read by `security` with no dialog, so any process the owner runs can read both keys.
- The verdict file is the JSON in spec section 6. `devctl review` requires its `reviewer` to match `project.toml`.

### Ruleset (plan 5 applies `rs-setup/ruleset.json`; plan 4's doctor checks it)

One active ruleset on `~DEFAULT_BRANCH`. A `pull_request` rule with `required_approving_review_count` 1, and `require_code_owner_review`, `dismiss_stale_reviews_on_push` and `require_last_push_approval` set to `true`. `required_status_checks` holds `{"context": "devctl check", "integration_id": 15368}`. `non_fast_forward` and `deletion` rules are present. `bypass_actors` is exactly `[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]`. The CI job that satisfies the check is named `devctl check`, in `.github/workflows/devctl-check.yml`.

### Gate log (plan 4, read by Spec 3)

`<git common dir>/rapid-ship/gate-log.jsonl`, never tracked, one JSON object per line. It records every request to a gate with its answer; Spec 3 adds merge-check lines:

| Field | Value |
| --- | --- |
| `time` | UTC, ISO 8601 with seconds |
| `command` | `"dispatch"` or `"dispatch --clean"` |
| `issue` | the issue ID as given |
| `answer` | `"allow"` or `"refuse"` |
| `reason` | text |
| `branch` | `"rs/<issue>"`, or `null` when the issue ID is invalid or `project.toml` names no Worker |
| `attempt` | integer; `0` with a `null` branch |

`dispatch` logs every request, refusals included, while it holds an exclusive `flock` on `<git common dir>/rapid-ship/dispatch.lock`. Its `attempt` is one more than the earlier `dispatch` lines for the issue whose answer is `allow`.

### `adopt` and the upstream lock (plan 5)

```python
# rapid_ship/kit/adopt.py
EXCEPTIONS_PATH = ".rapid-ship/exceptions.toml"
REMOVE_WHEN = "Remove when this code next changes"


class AdoptRefused(Exception): ...  # precondition failed; nothing written; exit 1


@dataclass(frozen=True)
class Suppression:
    path: str
    line: int  # 1-based
    rule: str  # one rule, named as in the suppressions table


@dataclass(frozen=True)
class Adopted:
    id: str  # "EX-<n>"
    suppression: Suppression


def find_suppressions(path: str, source: str) -> list[Suppression]: ...
def adopt_suppressions(root: Path, today: date) -> list[Adopted]: ...
```

`adopt` needs the lock, a clean work tree and `exceptions.toml`. It edits only tracked `.py` and `.pyi` files that are not Kit-managed, or are excluded under `[kit] exclude`, and only their comments. Each entry's reason is `Existed at Setup on <date>`.

`rapid_ship/upstream.lock` is TOML: `forked`, a list of skill directories, then one `[[file]]` per upstream file with `path` (under `rapid_ship/templates/common/`), `upstream_repository`, `upstream_path`, `upstream_commit`, `upstream_blob` and `status` (`"verbatim"` or `"patched"`). A patched file differs from its pristine fixture only between whole-line markers: `<!-- rapid-ship:begin -->` and `<!-- rapid-ship:end -->` in Markdown, `# rapid-ship:begin` and `# rapid-ship:end` in YAML front matter.

## Resolved disagreements

| Name | Chosen | Plans that change |
| --- | --- | --- |
| `rapid_ship.cli.main` argument | `Sequence[str] \| None`, plan 1 | Plan 2 Task 7: done; its `main` takes `Sequence[str] \| None` |
| Ruleset stale-review and last-push settings | Both `true`, plan 5 (the amended spec section 8) | Plan 4: `ruleset_problems`, its "Repository settings" constraint and Task 11's trial ruleset |
| `ruleset_problems` parameter | `Sequence[Mapping[str, object]]`, plan 4 | Plan 5 Task 7's Consumes line says `Mapping[str, Any]` |
| `sync --in-place` on a dirty work tree | Accepted, plan 2 | Plan 5: drop Task 1 Step 1's check and the Global Constraints fallback |
| devctl test import path | pytest `pythonpath`, no `tests/devctl/conftest.py`, plan 3 | Plan 5 Task 6 Step 2 still cites `tests/devctl/conftest.py` |
| devctl test file names | `tests/devctl/test_devctl_*.py`, plan 2 | Plan 5: rename `test_adopt_rules.py` and `test_rs_setup_ruleset.py` |
| Feature `entry_points` | Non-empty list, plan 3 (the check) | Plan 2 Task 6: done; the `docs/features/README.md` row says "A non-empty list; each path exists" |
| Seeded paths named in `rs-setup` | `kit.toml`, plans 2 and 3 | Plan 5 Task 7, `rs-setup` step 1: add plan 3's seeds or read them from `kit.lock` |
| `tools/devctl` uv workspace exclude | Plan 2's rule | Plan 4: add the doctor item. Plan 5: add the exclude in `rs-setup` step 5 |
| Repository common directory | `Repo.git_common_dir`, plan 2 | None: no bare `common_dir` remains in plan 4 |

## Plan style

Plans follow the writing-plans structure: header, global constraints, review focus, then tasks with files, interfaces, failing tests first, implementation, verification and commit. Following this repository's guidance, plans stay concise. They show code for interfaces, test cases and non-obvious steps, and point to the spec instead of repeating it. They never leave a step as "TBD", "handle edge cases" or "similar to task N".

### Kit exclusions and skill discovery (added after review on 2026-10-14)

- `[kit] exclude` (plan 2) is the only record of an exclusion. The lock keeps no mark for it. `status`, `sync`, plan 3's kit step and exceptions scan, plan 4's `kit_summary` and plan 5's `adopt` all read it from `project.toml`; devctl keeps its own copy of `is_excluded`, held equal to the CLI's by a parity test. `render_files` still renders excluded paths; `status` classifies them as `excluded`; `sync` never creates, replaces, merges or deletes them. Excluding a skill directory also covers its `.claude/skills` link.
- Map rule 7 (plan 3): every `.agents/skills/<name>` has a `SKILL.md` with front matter `name == <name>` and a non-empty `description`, and a `.claude/skills/<name>` symlink to it; nothing else sits under `.claude/skills/`.
- `devctl doctor` (plan 4): agy's sign-in is a probe, `hi` sent to a new headless Session on the cheapest model; a non-empty reply is ok. `--skills` creates a temporary worktree with the same code `dispatch` uses, starts one headless Session per Harness the Worker and Reviewer use, compares the skills it reports with `.agents/skills/*`, reports user-invoked skills (`disable-model-invocation: true`) as not checked because a Harness may leave them out of its list, lists outside skills for information, and removes the worktree.
