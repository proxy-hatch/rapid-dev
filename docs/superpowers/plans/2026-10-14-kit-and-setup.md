# Kit and Setup: plan index

**Spec:** [Spec 1: Kit and Setup](../specs/2026-10-14-kit-and-setup-design.md), part of the [rapid-ship design](../specs/2026-10-14-rapid-ship-design.md).

Spec 1 is built as six plans, in this order. Each one ends with a working, tested repository and its own PR. Plans 1 to 3 are built. Plans 4 to 6 replace the old plans 4 and 5 after the re-scope of 2026-10-16 ([ADR 0004](../../adr/0004-team-management-boundary.md)); each gets its own plan document, written from this index before its work starts. [Spec 2](../specs/2026-10-16-delivery-skills-design.md) and [Spec 3](../specs/2026-10-16-metrics-and-gardening-design.md) get their own plans later.

| Order | Plan | Spec sections | Depends on | State |
| --- | --- | --- | --- | --- |
| 1 | [Remove the old controller](2026-10-14-remove-controller.md) | 2 | — | Built: PR #28, `codex/remove-controller` |
| 2 | [The rapid-ship CLI](2026-10-14-rapid-ship-cli.md): templates, lock, `init`, `status`, `sync`, dog-food init | 3, 4 | 1 | Built: PR #29, `codex/rapid-ship-cli` |
| 3 | [`devctl check`](2026-10-14-devctl-check.md), the CI workflow and the hook; this repository switches to `./devctl check` | 4, 5 | 2 | Built: PR #30, `codex/devctl-check` |
| 4 | [Doctor and Agent identity](#plan-4-doctor-and-agent-identity): `devctl doctor`, `rapid-ship app`, the token code, `devctl as`, and the settings for the Roster and the escalation list | 3, 4, 6, 10 | 3 | Proposed |
| 5 | [Kit standards and Harness guardrails](#plan-5-kit-standards-and-harness-guardrails): `devctl hook` and its wiring, README and ARCHITECTURE seeds, the Pattern `task` key, the `SKILL.md` rule, the diff cap, CODEOWNERS additions | 4, 5, 6, 10 | 4 | Proposed |
| 6 | [`rs-setup` and `rs-health`](#plan-6-rs-setup-and-rs-health), with the engineering skills and `rs-contribute` | 7, 8, 9, 10 | 4, 5 | Proposed |

PRs #28 to #30 form a stack on the design PR, #27: each is based on the one before, and none had reached `main` on 2026-10-16. The re-scope lands on #27 first and is then merged up into #28, #29 and #30. Plan 4 starts from the head of #30.

The merge into #30 deletes the Walk-flow draft, which #30's root AGENTS.md and ARCHITECTURE.md still link. Map rule 1 then fails `./devctl check`, and the dead link in ARCHITECTURE.md fails the docs site build. #30's README.md links no Walk-flow draft, but it states behaviour the re-scope cut, and the merge keeps #30's text because the design branch leaves README.md alone. The same merge therefore rewrites these files, which #30 changed after the design branch:

1. **Root `AGENTS.md`.** Say that Spec 1 is built in six plans, and that plans 4 to 6, [Spec 2](../specs/2026-10-16-delivery-skills-design.md) and [Spec 3](../specs/2026-10-16-metrics-and-gardening-design.md) are not built yet. Drop `adopt` and the Walk-flow link. Drop the rule against `rs/` branches, which only `devctl dispatch` needed. Cut the metrics rule to: a missing metric is unknown, not zero, and a Suggested threshold breach is reported, never acted on. Mark one group as this repository's own rules: Linear is its tracker; its agents sign in with vendor subscriptions only, and the owner accepts the agy risk ([ADR 0001](../../adr/0001-subscription-logins-only.md)); agy is never a Reviewer; and each model is used exactly as named.
2. **`ARCHITECTURE.md`.** Rewrite "Designed, not built" from this index and the design's Delivery section: plans 4, 5 and 6 as defined below, Spec 2 and Spec 3, ADRs 0001, 0002 and 0004, and ADR 0003 as superseded. Drop the Walk-flow link and the claim that Flight is designed but not built. The opening paragraph says Spec 1 is built in six plans, not five. The sentence after the "What exists today" table lists what is not built from this index: plans 4 to 6, Spec 2 and Spec 3. It drops "the GitHub commands", `adopt` and the Walk flow, which the re-scope cut. In the CODEOWNERS paragraph, the Harness settings join the Protected set with plan 5, not Spec 2.
3. **`README.md`.** It is the GitHub front page, and the docs site publishes it. State product behaviour only: tasks live in any tracker the owner's Harness can reach; the owner chooses the Mode, and Flight lasts until the owner changes it; and Spec 1 is built in six plans. Drop "Linear holds the tasks" and "only while measured quality holds". Name this repository's own choices, such as Linear as its tracker, only in one line marked as dog-fooding.
4. **`docs/AGENTS.md`, Spec 1 and this index.** Keep #30's account of what plans 1 to 3 built, and the re-scope's text for everything else.

Two plan documents are superseded and kept as history: [GitHub commands](2026-10-14-github-commands.md), the old plan 4, built on `codex/github-commands` and never merged; and [Kit skills](2026-10-14-kit-skills.md), the old plan 5, never started.

This index fixes the layout and the names, signatures and formats that more than one plan uses. A plan that needs a different one changes this file in the same PR. For what plans 1 to 3 built, the code and [ARCHITECTURE.md](../../../ARCHITECTURE.md) on their branches are canonical; their plan documents keep their task lists and verification records.

## Conventions for every plan

- Every command in both CLIs is one word followed by arguments:
  - `rapid-ship init [--stack {python,agnostic}] [--owner LOGIN] [--repository OWNER/NAME] [--name NAME] [--package NAME]`
  - `rapid-ship status [--strict] [--json]`, `rapid-ship sync [--in-place] [--revert PATH]...`
  - `rapid-ship app [--repository OWNER/NAME]` (plan 4)
  - `devctl check [--tier {fast,full}] [--json] [--base REV] [--pr-body PATH]`
  - `devctl doctor [--skills]`, `devctl as {worker,reviewer} push`, `devctl as {worker,reviewer} gh ARGS...` (plan 4)
  - `devctl hook {claude,codex,agy} {pre-tool,stop}` (plan 5)
- Exit codes in both CLIs: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run. When both 1 and 2 apply, 2 wins. `KitRefusal` exits 1; `KitError`, `SettingsError`, `RepoError` and `DevctlError` exit 2. Two commands differ, as Spec 1 section 6 says: after it runs `gh` or `git`, `devctl as` returns that tool's exit code; `devctl hook` follows each Harness's hook protocol and exits 1 on an internal error, never 2.
- Write tests first. Label offline and simulated tests as such. A blocked or skipped step never counts as passed.
- Python 3.12 or later; `uv` runs everything. Settings are TOML, read with `tomllib`.
- devctl source is edited only under `rapid_ship/templates/common/tools/devctl/`. Then run `uv run rapid-ship sync --in-place`, which accepts a dirty work tree. Commit the template, the vendored copy and `.rapid-ship/kit.lock` together. Never edit the vendored copy: `sync` would make it this repository's own, and `tests/test_kit_dogfood.py` fails.
- devctl starts processes only through `process.run_process`, called through the module (`from devctl import process`). The one other caller is `repo._git` (EX-3). `rapid_ship` never imports devctl, which an import-linter `forbidden` contract enforces.
- The Python guardrail settings cover `rapid_ship`, devctl and `tests/`: no `print`, no `Any` in a signature, complexity at most 10, every test annotated. Each suppression carries an `rs-exception` marker and an entry.
- `uv run pytest` and `./devctl check --tier full` need network access and gitleaks 8.30.1 on `PATH`.
- The Kit version is the rapid-ship package version. Each Kit release is a tag `v<version>` on `main`, created by the owner. Run `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>`, or `--from <local checkout>` before the first tag. PyPI publishing is a later, separate change.
- A live trial is an Owner step: the plan names what to run and what to record under `docs/trials/`, and the owner runs or approves each external write.
- Each plan's last task runs `./devctl check`, builds the docs site with `npm --prefix website run build`, and records the actual results in the plan.

## Layout after plan 6

```text
rapid_ship/                      # the rapid-ship CLI package, run with uvx
  __init__.py  __main__.py
  cli.py                         # build_parser(), main(argv): init, status, sync; app (plan 4)
  files.py                       # atomic_replace, UnsafePath, relative_parts, safe_path, create_file
  github_app.py                  # plan 4: rapid-ship app's manifest flow, Keychain storage, install URLs
  upstream.lock                  # plan 6: upstream files of forked skills
  kit/
    templates.py lock.py git.py init.py existing_checks.py status.py sync.py writes.py pull_request.py
  templates/
    kit.toml                     # see "Kit manifest" below
    common/                      # files for every stack, laid out as in a project
    python/                      # Python stack additions and overrides
    agnostic/                    # stack-agnostic additions
tests/
  conftest.py                    # the only conftest; plan 4 adds pytest_plugins = ["github_fixtures"]
  test_files.py test_kit_*.py    # rapid-ship CLI tests; plan 4 adds test_kit_app*.py, plan 6 test_kit_upstream.py
  fixtures/upstream/<repository>/<commit>/<path>   # plan 6: pristine upstream files
  devctl/                        # no __init__.py, no conftest.py; files named test_devctl_*.py
    check_workspace.py           # plan 3: project_settings, Workspace, new_workspace, fake_tool
    github_fakes.py github_fixtures.py fixtures/github/   # plan 4
    fixtures/hooks/<harness>/    # plan 5: recorded hook events
scripts/smoke_distribution.py
devctl, tools/devctl/            # this repository's vendored Kit
.agents/skills/rs-*, .claude/skills/rs-*   # plan 6: vendored Kit skills; rapid_ship/skills/ is gone
```

`pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["tools/devctl", "tests/devctl"]`, so tests import the vendored devctl and its test helpers.

devctl inside any project:

```text
devctl                           # sh shim: unset UV_PROJECT_ENVIRONMENT; exec uv run --project "<root>/tools/devctl" --frozen --quiet devctl "$@"
tools/AGENTS.md                  # seeded
tools/devctl/
  pyproject.toml                 # name "devctl"; [project.scripts] devctl = "devctl.cli:main"; [tool.uv.workspace] members = []
  uv.lock
  .gitignore
  devctl/
    __init__.py                  # __version__
    cli.py                       # build_parser, main; core verbs, then devctl_project.register
    repo.py                      # Repo, RepoError
    settings.py                  # ProjectSettings and friends, SettingsError (plan 4 reshapes it)
    process.py                   # ProcessResult, safe_environment, run_process
    codeowners.py                # plan 5: the Protected-set lines and their matcher, moved from check/diff.py
    check/                       # plan 3: __init__, steps, markdown, map, references, exceptions,
                                 # filesize, kit, diff, evidence, stacks/python.py, stacks/agnostic.py
    doctor.py doctor_items.py doctor_local.py doctor_signin.py doctor_github.py doctor_rules.py doctor_skills.py
    harness.py                   # plan 4: probe models, the agy sign-in probe, the skills probe
    identity.py                  # plan 4: devctl as
    github/api.py github/app.py github/askpass.py   # plan 4: REST client, App tokens, GIT_ASKPASS helper
    hook.py hook_protocols.py    # plan 5: devctl hook's rules, and each Harness's event format
  devctl_project/                # seeded: project verbs and extra check steps
    __init__.py
```

devctl depends only on PyYAML (`pyyaml>=6.0.3,<7`, plan 3) and `PyJWT[crypto]>=2.10,<3` (plan 4). The root dev group adds the same two, plus `types-pyyaml`, so `tests/devctl` can import devctl. pip-audit 2.10.1 and zizmor 1.30.1 run with `uv tool run --from <pin>` and are not dependencies; gitleaks 8.30.1 is a binary on `PATH`. The rapid-ship CLI depends only on `tomli-w`.

A project whose root `[tool.uv.workspace] members` match `tools/devctl` must list it under `exclude`, or its own `uv lock` fails. `init` never edits that file: `rs-setup` adds the exclude (plan 6) and `devctl doctor` reports it missing (plan 4).

## Built interfaces (plans 1 to 3)

The code on `codex/devctl-check` is canonical; this list names what later plans call.

- `rapid_ship/cli.py`: `build_parser`, and `main(argv: Sequence[str] | None = None)`.
- `rapid_ship/files.py`: `atomic_replace`, `UnsafePath`, `relative_parts`, `safe_path` (refuses every symlink below the root), `create_file` (never overwrites).
- `rapid_ship/kit/`: `templates.py` (`Stack = Literal["python", "agnostic"]`, `Kind`, `Template`, `KitManifest`, `KitError`, `KitRefusal`, `load_manifest`, `render_files`, `read_optional_skills`, `read_excluded`, `is_excluded`, `installed_version`); `lock.py` (`Lock`, `LockEntry`, `LOCK_PATH`, `read_lock`, `write_lock`, `file_sha256`, `entry_for`, `seeded_entry`); `git.py` (`git`, which runs no hook and passes `--literal-pathspecs` except with `literal=False` for `check-ignore`, `work_tree_root`, `is_clean`, `commit_paths`, `leave_branch`); `init.py` (`INIT_BRANCH`, `init_repository`, `resolve_variables`); `status.py` (`classify`, `StatusReport`, `FileStatus`, `locate`, `fingerprint`); `sync.py` (`sync_repository`, `SyncResult`, `Conflict`).
- `devctl/repo.py`: `Repo` with `root`, `git_common_dir`, `discover`, `tracked_files`, `merge_base`, `files`, `git`; `RepoError`.
- `devctl/process.py`: `ProcessResult`, `safe_environment`, `run_process(argv, cwd, timeout_seconds, env=None, input_text=None)`, `MAX_OUTPUT_BYTES`. It reports truncation in flags, never inside the output.
- `devctl/check/steps.py`: `Tier`, `Status`, `StepResult`, `CheckContext`, `Step`, `CommandStep`, `passed`, `failed`, `blocked`, `not_applicable`, `run_tool`, `command_result`. `devctl/check/__init__.py`: `core_steps`, `all_steps`, `run_check`, `exit_code`, `resolve_change`, `ChangeError`.
- `devctl/check/kit.py`: `LOCK_PATH`, `KitLockError`, `is_excluded` (devctl's copy of the CLI's, held equal by a parity test), `managed_paths`.
- `devctl/check/exceptions.py`: `MARKER`, `SuppressedLine`, `scan`, `normal_rule`. `devctl/check/evidence.py`: `evidence_section`, `removed_test_declarations`. `devctl/check/diff.py`: `codeowners_match`, `protected_patterns`, `glob_match`.
- `devctl_project/__init__.py` (seeded): `register(commands)` adds verbs; `check_steps()` returns extra steps.

### Kit manifest

`rapid_ship/templates/kit.toml` after plan 6. Paths are relative to `common/` or a stack directory, before substitution. Every other template is managed.

```toml
seeded = [".agents/hooks.json", ".claude/settings.json", ".codex/hooks.json", ".github/CODEOWNERS",
  ".rapid-ship/exceptions.toml", ".rapid-ship/project.toml", "AGENTS.md",
  "ARCHITECTURE.md", "CLAUDE.md", "README.md", "docs/AGENTS.md", "docs/features/README.md",
  "docs/patterns/README.md", "tools/AGENTS.md", "tools/devctl/devctl_project/__init__.py"]
new_project = [".gitignore", "pyproject.toml", "src/AGENTS.md", "src/__package__/__init__.py",
  "tests/AGENTS.md", "tests/test_import.py"]   # seeded only when init starts a Python project
executable = ["devctl", ".githooks/pre-commit", "tools/devctl/devctl/github/askpass.py"]
optional_skills = ["rs-contribute"]
variables = ["owner", "package", "project_name", "repository"]
```

Plan 4 adds `askpass.py` to `executable` and drops the `.rapid-ship/gate.toml` seed. Plan 5 adds the five new seeds. Plan 6 adds `rs-contribute`. Spec 3's plan adds a `.rapid-ship/metrics.toml` seed. It also renames the manifest key `optional_skills` to `optional`, with `read_optional_skills` and `ProjectSettings.optional_skills` to match, so that `optional` can name an optional Kit file, such as its metrics Action, as well as a skill.

Template rules, as plan 2 built them:

- Managed templates are copied byte for byte, so a managed file's hash is the same in every project.
- Only seeded files substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`. A template directory named `__package__` becomes the package name. An empty variable renders as `<name>` and comments out its line in a TOML file or CODEOWNERS; elsewhere it is a `KitError`.
- `.claude/skills/<name>` is always a relative symlink, generated from `.agents/skills/<name>/`. When a symlink cannot be made, `init` and `sync` exit 2 and leave nothing half-written.
- Template discovery skips `.venv`, `__pycache__`, `.DS_Store` and `.pyc` files, and, when the template root's `kit.toml` is tracked by git, every path git does not keep.
- The execute bit comes only from `executable`: `init` creates a listed path with mode `0o777` less the umask, and `sync` keeps a file's mode, adding execute bits for a listed path. A template's own git mode never reaches a project. List a new executable template before its first sync, so its vendored copy is tracked `100755`.
- `sync` creates a seeded template that a newer Kit adds only where nothing exists at its path, and records it either way. It never adds a new-project seed.

## Shared interfaces for plans 4 to 6

### Settings (plan 4)

```python
# devctl/settings.py after plan 4
Harness = Literal["claude", "codex", "agy"]  # Proposal: Spec 1 section 11, Roster Harnesses
Role = Literal["worker", "reviewer"]


@dataclass(frozen=True)
class Agent:
    harness: Harness
    model: str  # kept exactly


@dataclass(frozen=True)
class App:
    id: int  # [github] <role>_app_id; 0 in the file means unset
    slug: str  # [github] <role>_app_slug; Spec 3 matches agent PR authors against it


@dataclass(frozen=True)
class Escalation:
    every_pr: bool  # default True: Walk
    kinds: tuple[str, ...]  # plain text for the Lead
    revision_rounds: int  # default 3, at least 1


@dataclass(frozen=True)
class ProjectSettings:
    stack: Stack
    repository: str | None  # "owner/name"
    worker_app: App | None  # both Apps recorded, or neither; recorded Apps need repository
    reviewer_app: App | None
    escalation: Escalation
    roster: Mapping[Role, Agent]  # empty without a Roster
    optional_skills: tuple[str, ...]  # [kit] optional
    excluded: tuple[str, ...]  # [kit] exclude
    source_roots: tuple[str, ...]  # [map] source_roots
    unguided: tuple[str, ...]  # [map] unguided
    map_exclude: tuple[str, ...]  # [map] exclude
    unit_tests: tuple[str, ...]  # [tests] unit

    @property
    def agent_identity(self) -> bool: ...  # both Apps recorded


def load_project(root: Path) -> ProjectSettings: ...
def load_exceptions(root: Path) -> list[ExceptionEntry]: ...
```

Plan 4 removes `GateSettings`, `load_gate`, `Mode`, `CheckContext.gate` and `release_method`. `[agents]`, `[linear]`, `[dispatch]` and `[release]` become unknown keys, which are errors; the message names what replaced each. Spec 2's plan adds `[tracker]` and `[design]`.

### doctor (plan 4; plan 5 adds items)

```python
# devctl/doctor_items.py
Status = Literal["ok", "missing", "unknown"]


@dataclass(frozen=True)
class Item:
    area: str  # toolchain, guardrails, kit, github, agent identity, skills
    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class DoctorContext:
    root: Path
    project: ProjectSettings
    owner_get: OwnerGet  # GET with the owner's gh sign-in; raises OwnerReadError
    access: GitHubAccess | None  # None while Agent identity is off


# devctl/doctor_rules.py
PROTECTED_PATHS: tuple[str, ...]  # plan 5 widens .agents/skills/ to .agents/ and adds .codex/
PYTHON_PROTECTED_PATHS: tuple[str, ...]


def ruleset_problems(
    rulesets: Sequence[Mapping[str, object]],
    default_branch: str,
    *,
    every_pr: bool,
    agent_identity: bool,
) -> list[str]: ...  # plan 6's test checks rs-setup's ruleset.json with it
def codeowners_problems(text: str, every_pr: bool, owner: str, stack: Stack) -> list[str]: ...
```

### Ruleset (plan 6 applies `rs-setup/ruleset.json`; plan 4's doctor checks it)

One active ruleset on `~DEFAULT_BRANCH`. A `pull_request` rule with `required_approving_review_count` 1, `allowed_merge_methods` `["squash"]`, and `require_code_owner_review`, `dismiss_stale_reviews_on_push`, `require_last_push_approval` and `required_review_thread_resolution` set to `true`. `required_status_checks` holds `{"context": "devctl check", "integration_id": 15368}`. `non_fast_forward` and `deletion` rules are present. `bypass_actors` is exactly `[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]`.

- Plan 4's live trial settles the approval count with Agent identity in Flight (Spec 1 section 8, step 7). If GitHub does not count the Reviewer App's approval, the count becomes 0, and both plans change this paragraph.
- With `every_pr = false` and Agent identity off, doctor also accepts a `pull_request` rule with no approval, no code-owner review and no last-push approval, because Flight without Agent identity needs that (Spec 1 section 8, step 8).

### Agent identity (plan 4)

```python
# devctl/github/app.py
KEYCHAIN_SERVICE: dict[Role, str]  # "rapid-ship/worker-app", "rapid-ship/reviewer-app"
APP_PERMISSIONS: dict[Role, dict[str, str]]  # Spec 1 section 3


class DevctlError(Exception): ...  # exit 2


def installation_token(
    role: Role,
    repository: str,
    app_id: int,
    *,
    keychain: Keychain | None = None,
    api_url: str = API_URL,
) -> str: ...


# devctl/identity.py: devctl as
GH_COMMANDS = frozenset({"pr", "issue", "api"})


def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...
```

- A token lives in memory only, one per command. `gh` receives it only as `GH_TOKEN` in its own environment, with `GH_REPO`; git receives it only through `devctl/github/askpass.py`, which reads `RAPID_SHIP_GIT_TOKEN`.
- `rapid_ship/github_app.py` keeps its own `KEYCHAIN_SERVICE` and `APP_PERMISSIONS`, because `rapid_ship` cannot import devctl. A parity test keeps them equal to devctl's.

### `devctl hook` (plan 5)

```python
# devctl/hook.py
Decision = Literal["deny", "ask"] | None  # None: no decision; the hook never allows


@dataclass(frozen=True)
class ToolCall:  # one Harness's pre-tool event, normalised
    shell: str | None  # the command line of a shell tool
    edits: tuple[str, ...]  # repository-relative paths a file-edit tool writes
    cwd: Path


@dataclass(frozen=True)
class StopEvent:
    cwd: Path
    continuing: bool  # the Harness's loop flag, such as Claude Code's stop_hook_active


def decide(
    call: ToolCall, project: ProjectSettings, protected: Sequence[str]
) -> tuple[Decision, str]: ...


# devctl/hook_protocols.py
def read_event(
    harness: Harness, event: Literal["pre-tool", "stop"], payload: bytes
) -> ToolCall | StopEvent: ...
def answer(
    harness: Harness, decision: Decision, reason: str
) -> tuple[str, int]: ...  # stdout, exit code
```

`protected` comes from `devctl/codeowners.py`, the matcher the `diff` step also uses, so the hook and the step agree on the Protected set.

### CODEOWNERS (plan 2 seeds it; plans 3 to 6 read or write it)

- Walk has one active line, `* @<owner>`. Without `--owner`, `init` writes it as `# * @<owner>`, and `rs-setup` writes the line.
- The Protected set follows, commented out, as `# /<path> @<owner>` lines, in Spec 1 section 4's order. Flight uncomments them and removes the `*` line.
- The `diff` step and `devctl hook` read `<pattern> @<owner>` lines, commented or not, and never treat `*` as Protected. doctor accepts each path with or without the leading `/`, and requires the Python settings files only for the Python stack.

### Suppressions, PR body, feature and Pattern front matter

Plan 3 built these; Spec 1 section 5 describes them. Plan 5 adds the Pattern `task` key and the Evidence line `Over the diff cap: <reason>`, read only inside `## Evidence`, like `Removed tests:`.

## Plan 4: Doctor and Agent identity

**Goal:** Give devctl `doctor`, with `--skills`, and give the owner optional Agent identity: `rapid-ship app`, the token code and `devctl as`. Move the settings to the re-scope: the Roster, the escalation list and each App's ID and slug, with `[agents]`, `[linear]`, `[dispatch]` and `[release]` removed and `gate.toml` no longer read.

**Method:** a fresh branch from the head of #30 brings over only the surviving code of `codex/github-commands` (head `901bd43`): cherry-pick where a commit applies cleanly, copy otherwise, then reshape. One reviewed PR. This is the largest of the three plans; most of its code was reviewed on the old branch.

| Source on `codex/github-commands` | In plan 4 |
| --- | --- |
| `98082fb`, `de800ae`: the two `process.py` fixes, `process.first_line` and `run_process` finishing when macOS refuses SIGTERM | Applied by hand to the template, with their tests; `sync` regenerates the vendored copy and the lock |
| `1eb138d`: the REST client | Copied: what doctor and `devctl as` use |
| `620e5ff`, `f5177ba`: token minting and the askpass helper | Copied, without the Claim-only git helpers |
| `0c2b27f`, `51c9300`: doctor's local items and sign-ins | Copied, without the Linear item; sign-ins follow the Roster and accept any method |
| `ebe3bd2`: doctor's GitHub and App items | Copied; App items only with Agent identity on; ruleset and CODEOWNERS read `[escalation]` |
| `013cdac`: `doctor --skills` | Reshaped: a temporary worktree at `HEAD` with the owner's git, no App fetch |
| `f9c3872`: worktrees | Only `probe_worktree`, reshaped |
| `3eec7a1`, `901bd43`: `rapid-ship app` | Cherry-picked or copied |
| `db12380`, `d44b673`, `eb2faa1`, `788375f`, `0b20f0b`, `6563e9a`, `2c0a333`, `9c0adcc`, `e3380ea`, `cd6fde6` | Not brought over: `dispatch`, `claims`, `claim_status`, `release`, `records`, `pr`, `review`, `merge`, the gate log and the Session registry, about 2,100 lines plus their tests |

**Files:**

- Templates, then vendored with `sync`: `rapid_ship/templates/common/tools/devctl/devctl/` `process.py`, `settings.py`, `cli.py`, `doctor*.py`, `harness.py`, `identity.py`, `github/`, `check/steps.py`, `check/diff.py`, `check/kit.py`, `check/stacks/python.py`; `tools/devctl/pyproject.toml` and `uv.lock`; `rapid_ship/templates/{python,agnostic}/.rapid-ship/project.toml` and `kit.toml`; `common/.rapid-ship/gate.toml` is deleted.
- `rapid_ship/cli.py`, `rapid_ship/github_app.py`; root `pyproject.toml` and `uv.lock`.
- This repository's `.rapid-ship/project.toml`, edited in place because it is seeded, and its `.rapid-ship/gate.toml`, deleted.
- Tests: `tests/devctl/test_devctl_settings*.py`, `test_devctl_doctor*.py`, `test_devctl_harness.py`, `test_devctl_github_api*.py`, `test_devctl_github_app*.py`, `test_devctl_askpass*.py`, `test_devctl_identity*.py`, `test_devctl_probe_worktree.py`, `github_fakes.py`, `github_fixtures.py`, `fixtures/github/`; `tests/test_kit_app*.py`; `tests/conftest.py`.
- Tests that use what task 2 removes: `tests/devctl/check_workspace.py`, `test_devctl_diff_removed_tests.py`, `test_devctl_check_cli.py`, `test_devctl_cli.py` for the `gate.toml` error, and `tests/test_kit_contents.py` for the seeded `gate.toml` and the `linear` and `dispatch` tables.
- Docs: `ARCHITECTURE.md`, the root `AGENTS.md` (its link to `gate.toml`), `rapid_ship/AGENTS.md`, `rapid_ship/templates/AGENTS.md`, `tools/AGENTS.md`, `tests/AGENTS.md`, and the trial record under `docs/trials/`.

**Tasks:**

1. Branch from #30's head. Apply `98082fb`'s `process.first_line` and `de800ae`'s `_kill_group` fix to the template's `process.py`, with their tests, then run `uv run rapid-ship sync --in-place`. Neither commit cherry-picks cleanly onto #30: both carry `kit.lock` hunks for other hashes, and `98082fb` also edits `github/app.py` and `worktrees.py`, which #30 lacks. Never cherry-pick a `kit.lock` hunk.
2. Settings: `[roster]`, `[escalation]`, and each App's ID and slug; remove `[agents]`, `[linear]`, `[dispatch]`, `[release]`, `GateSettings` and `CheckContext.gate`. The `diff` step drops its Flight note. The project templates and this repository's `project.toml` follow. The Kit stops seeding `gate.toml`, and this repository deletes its own copy and the root AGENTS.md link to it.
3. The REST client, App tokens and the askpass helper, with PyJWT. Tests against a fake HTTP server and a fake `security`, labelled simulated.
4. doctor's core and local items, without the Linear item; Harness sign-ins from the Roster, any method ok; the agy probe.
5. doctor's GitHub items: the ruleset for Walk and for Flight with and without Agent identity, CODEOWNERS against `every_pr`, delete branch on merge, fork workflow approval, the plan-limit message; App items only with Agent identity on.
6. `doctor --skills`: a detached worktree at `HEAD` in a temporary directory; the Roster's Harnesses, or the three supported ones on `PATH`.
7. `rapid-ship app`, printing each App's ID and slug, with the parity test for the Keychain services and permissions.
8. `devctl as`: `push` and `gh`, every refusal, the token only in the child's environment; tests with fake `gh` and `git` executables and a local bare repository.
9. Guides and ARCHITECTURE.md; `uv run rapid-ship sync --in-place`, then `uv run rapid-ship status --strict`.
10. Live trials, an Owner step: `rapid-ship app` on a scratch repository; Agent identity end to end, including whether GitHub counts the Reviewer App's approval; doctor reading the applied ruleset; a GitHub Free private repository's ruleset answer.
11. Verification and record.

## Plan 5: Kit standards and Harness guardrails

**Goal:** Ship the standards and guardrails every Harness works under: `devctl hook` and its seeded wiring for Claude Code, Codex and agy; the README.md and ARCHITECTURE.md seeds with map rule 8; the Pattern `task` key; the `SKILL.md` rule; the diff cap; and the CODEOWNERS additions for the Harness settings.

**Files:**

- devctl templates, then vendored: `codeowners.py`, `hook.py`, `hook_protocols.py`, `cli.py`, `check/map.py`, `check/diff.py`, `check/evidence.py`, `check/stacks/python.py`, `doctor_local.py`, `doctor_rules.py`.
- Kit templates: `common/README.md`, `common/ARCHITECTURE.md`, `common/.claude/settings.json`, `common/.codex/hooks.json`, `common/.agents/hooks.json`, `common/AGENTS.md`, `python/AGENTS.md`, `common/.github/CODEOWNERS`, `python/.github/CODEOWNERS`, `common/docs/patterns/README.md`, `kit.toml`.
- This repository: `.github/CODEOWNERS` and the root `AGENTS.md`, edited in place; `.claude/settings.json`, `.codex/hooks.json` and `.agents/hooks.json`, created by `sync`.
- Tests: `tests/devctl/test_devctl_codeowners.py`, `test_devctl_hook*.py`, `fixtures/hooks/<harness>/`, `test_devctl_map*.py`, `test_devctl_diff*.py`, `test_devctl_doctor_wiring.py`, `tests/test_kit_templates*.py`.
- Docs: `ARCHITECTURE.md`, the template and directory guides, and the trial record under `docs/trials/`.

**Tasks:**

1. Move the Protected-set reader and matcher from `check/diff.py` into `codeowners.py`, with no change in behaviour.
2. `devctl hook`'s rules: G1 to G5, G7 and G8 on a normalised tool call, tested from a table of command lines and edits.
3. The three hook protocols: each Harness's event JSON in, its decision format and exit code out, from recorded fixtures; an internal error exits 1.
4. The Stop event, G6: the check in the event's working directory, the clean-tree skip, and the loop flag.
5. The seeded wiring files, `kit.toml`, doctor's wiring items, and this repository's wiring through `sync`.
6. The CODEOWNERS additions in both templates, doctor's `PROTECTED_PATHS`, and this repository's CODEOWNERS.
7. The README.md and ARCHITECTURE.md seeds, the root guide's new rows, and map rule 8.
8. The Pattern `task` key: the seeded README and map rule 5.
9. The `SKILL.md` rule in map rule 7.
10. The diff cap in the `diff` step, with its exclusions and the `Over the diff cap:` declaration.
11. Live trial, an Owner step: each rule in Claude Code, Codex and agy, in the lead Session and inside a subagent; whether Codex hooks can ask; the hook's added time per tool call.
12. Verification and record.

If review finds plan 5 too large for one PR, it splits in two, in this order: the guardrails (tasks 1 to 6 and 11), then the standards (tasks 7 to 10).

## Plan 6: `rs-setup` and `rs-health`

**Goal:** Ship the Kit's first skills: the engineering skills pinned in an upstream lock, `rs-setup`, `rs-health` with the audit it shares with `rs-garden`, and the optional `rs-contribute`. Retire `rapid-ship-engineering`. Then run `rs-setup` on hello-rapid-ship and apply its GitHub settings to this repository.

**Files:**

- Kit skills under `rapid_ship/templates/common/.agents/skills/`, each with its generated `.claude/skills` link: `rs-tdd/`, `rs-diagnosing-bugs/`, `rs-codebase-design/`, `rs-pr/`, `rs-writing-for-agents/`, `rs-writing/`, `rs-ponytail/`, `rs-setup/` (with `ruleset.json` and its references), `rs-health/` (with `references/audit.md`), `rs-contribute/`.
- `rapid_ship/upstream.lock`, `rapid_ship/templates/kit.toml`.
- Removed: `rapid_ship/skills/rapid-ship-engineering/` and its `.agents/skills` and `.claude/skills` links. Updated: the root `AGENTS.md`, `rapid_ship/AGENTS.md`, `.agents/AGENTS.md`, `.claude/AGENTS.md`.
- Tests: `tests/test_kit_upstream.py` with `tests/fixtures/upstream/`, and `tests/devctl/test_devctl_ruleset_json.py`.
- Docs: `ARCHITECTURE.md` and the trial record under `docs/trials/`.

**Tasks:**

1. The upstream lock and the verbatim forks, `rs-codebase-design` and `rs-writing-for-agents`, with the lock test.
2. The patched forks, `rs-tdd`, `rs-diagnosing-bugs` and `rs-pr`, whose Evidence follows Spec 1 section 5.
3. `rs-writing` and `rs-ponytail`, from this repository's engineering references.
4. `rs-setup`: Spec 1 section 8's steps, and `ruleset.json` checked by `ruleset_problems`. Steps 10 (tracker) and 11 (metrics) come later, with Spec 2's and Spec 3's plans.
5. `rs-health` and its `references/audit.md`: Spec 1 section 9.
6. `rs-contribute`, listed under `optional_skills`.
7. Retire `rapid-ship-engineering`, and point this repository's root AGENTS.md to `rs-writing` and `rs-ponytail`.
8. Live trial, an Owner step: `rs-setup` on a new scratch repository and on hello-rapid-ship, including `doctor --skills` for each Harness; `rs-health` on hello-rapid-ship, ending with a standards milestone in its tracker.
9. Owner step: apply `rs-setup`'s GitHub settings to `proxy-hatch/rapid-ship`.
10. Verification and record.

## Plan style

Plans follow the writing-plans structure: header, global constraints, review focus, then tasks with files, interfaces, failing tests first, implementation, verification and commit. Following this repository's guidance, plans stay concise. They show code for interfaces, test cases and non-obvious steps, and point to the spec instead of repeating it. They never leave a step as "TBD", "handle edge cases" or "similar to task N".
