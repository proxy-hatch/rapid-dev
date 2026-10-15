# Spec 1: Kit and Setup

**Status: proposed on 2026-10-14 and awaiting the owner's review.** This is the first of the four specs listed in the [rapid-ship design](2026-10-14-rapid-ship-design.md). Terms follow `GLOSSARY.md` at the repository root.

## 1. Scope and outcome

When this spec is built, an owner can run `uvx rapid-ship init` in a new or existing repository, then run the `rs-setup` skill in any supported Harness, and end with:

- the Kit vendored and recorded in a lock file;
- a devctl whose `check` runs in hooks and in CI as a required status check;
- `devctl doctor` (including `--skills`), `dispatch`, `pr` and `review` working, with every agent GitHub write made through the owner's Worker App or Reviewer App;
- GitHub and Linear connected, the Worker and Reviewer Agents chosen and their sign-ins confirmed;
- default thresholds recorded and the Mode set to Walk;
- for an existing project, a health report with proposed Linear issues.

rapid-ship runs its own `init` on itself, and its CI fails when the vendored copy disagrees with the templates.

Out of scope here:

- The Walk flow skills (`rs-plan`, `rs-walk`, `rs-work`, `rs-review`, `rs-garden`), Linear conventions beyond Setup, and the corrections ledger. These are Spec 2. Setup's final step, one small real task through the flow, is verified once Spec 2 exists.
- `devctl metrics`, `devctl gate`, the merge check, the Flight lease and Pre-flight. These are Spec 3.

## 2. Removing the old controller

The first PR of this spec removes the old controller. Every later PR builds on a repository that no longer contains it.

### Steps

1. Tag the last commit that contains the controller as `archive/controller-2026-10` and push the tag. Today that is `f7b877b`; the archive dossier cites it. If `main` moves first, tag the new commit and update the citations.
2. Delete the controller code and its tests:
   - `rapid_ship/execution/`, `rapid_ship/trust/`, `rapid_ship/project/`;
   - `rapid_ship/cli.py`, `models.py`, `storage.py`, `logs.py`, `protocol_json.py`, `metrics.py`, `github_metrics.py`, `rapid_ship/templates/`;
   - the root `devctl`, `scripts/build_controller.py`, `scripts/smoke_controller.py`;
   - every test of the deleted modules, and both `tests/typecheck_*.py` fixtures;
   - `examples/`.
3. Keep `rapid_ship/files.py`, `rapid_ship/process.py` and their tests. Replace the console script `devctl` with `rapid-ship`, whose first version prints only its version. Keep `scripts/check_repository.py` and `scripts/check.py`, minus the controller stages, and point `scripts/smoke_distribution.py` at `rapid-ship --version`.
4. Delete the `rapid-ship` skill, which drives the deleted controller. Keep `rapid-ship-engineering` until the Kit skills replace it (section 7). Delete `rapid-ship-improve`; the opt-in `rs-contribute` skill replaces it (section 7).
5. Move these records into `docs/archive/orchestrator/`, as the [archive dossier](../../archive/orchestrator/README.md) lists, and fix their relative links: `docs/runtime-choice.md`, `docs/session-handoffs.md`, `docs/environments.md`, `docs/authority.md`, `docs/trials/astrabox-report.md`, `docs/trials/lightdag-report.md`, `docs/trials/2026-10-11-runtime-comparison.md` and both trial tarballs.
6. Add one line at the top of each remaining old guide: "Historical: describes the controller removed on <date>. See the rapid-ship design." This applies to `getting-started.md`, `usage.md`, `task-slicing.md`, `model-harnesses.md`, `linear.md`, `metrics.md`, `engineering-skills.md`, `improving-rapid-ship.md` and `bootstrap-validation.md`.
7. Remove the moved pages from `website/sidebars.js`. The documentation site is rewritten once the product works; until then this PR does only what keeps it building and honest.
8. Rewrite `README.md`, `ARCHITECTURE.md`, root `AGENTS.md` and `CLAUDE.md` for the new scope. Root `AGENTS.md` loses these stale rules: devctl as a controller, the `codex/` branch prefix, "Native execution … cannot qualify for unattended delivery", and "Metrics never grant authority or increase concurrency automatically". The last becomes: metrics never grant Flight, and they end it automatically.
9. Update every AGENTS.md guide whose directory changed.

### Borrow list

These parts are reused. Code is retrieved from the tag with `git show archive/controller-2026-10:<path>` when the PR that needs it is written.

| Source at the tag | Reused in |
| --- | --- |
| `rapid_ship/files.py` `atomic_replace` | rapid-ship CLI and devctl, for every file write |
| `rapid_ship/project/configuration.py:33-58`, safe-path helpers that refuse symlinks and never overwrite | `rapid-ship init` |
| `rapid_ship/process.py`, the bounded process supervisor | devctl, for check steps. Fix the hard-coded macOS `PATH` (`:33`), the in-band truncation marker (`:15-16`, `:57-62`) and the 10 ms poll |
| `scripts/check_repository.py` | devctl's map check, extended with directory coverage and reachability; its skill-alias half loses the hard-coded `rapid_ship/skills` |
| `scripts/check.py`, one entry point for local runs and CI | `devctl check` |
| `rapid_ship/trust/github.py:57-77` `inspect_protection` | `devctl doctor`, extended from branch protection to rulesets |
| `tests/typecheck_*.py`, `assert_type` fixtures checked by mypy | A Pattern enforcement type in the Python kit |
| `docs/metrics.md` definitions and missing-is-unknown rules | Spec 3 |
| `rapid_ship/project/providers.py` sign-in status parsers | Optional, for `rs-setup` |

## 3. The rapid-ship CLI

The rapid-ship CLI is a small Python package run with `uvx`; nothing is installed. `uvx` fetches it from a git tag of this repository: `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>`. Each Kit release is a tag `v<version>` on `main`, created by the owner; the Kit version is the package version. Publishing to PyPI waits until the Kit settles. This spec writes `uvx rapid-ship` for short. It holds everything that runs once or rarely, so devctl keeps only the commands that people and agents use repeatedly. In both CLIs each command is a single word followed by arguments.

`rapid-ship` has five commands: `init`, `status`, `sync`, `app` and `adopt`.

### `rapid-ship init`

1. **Preconditions:** the current directory is inside a git work tree with a clean status, and `.rapid-ship/kit.lock` does not exist.
2. **Stack:** `pyproject.toml` present means `python`. Otherwise the owner passes `--stack python` or `--stack neutral`. `--owner <handle>` is optional; without it the CODEOWNERS line is written commented out, and `rs-setup` fills it in. The project name defaults to the GitHub repository name, from `--repository` or the `origin` remote, else the main checkout's directory name; `--name` overrides it.
3. **Plan the writes.** Each Kit file is either managed (rapid-ship updates it later) or seeded (written once, then owned by the project). Section 4 lists both kinds.
4. **Conflicts:** if any managed file already exists, `init` writes nothing, lists the conflicts and exits 1. If a seeded file exists, `init` skips it and lists it for `rs-setup` to merge.
5. **Write** with the safe-path helpers: never outside the repository, never through a symlink, never over an existing file.
6. **Record** `.rapid-ship/kit.lock` and print the next step: commit on a branch, then run `rs-setup`.

`init` never edits an existing file, never runs project code and never runs a hook.

### `rapid-ship status`

Read-only. It compares the repository with the lock and the installed rapid-ship version.

| Class | Meaning |
| --- | --- |
| unchanged | A managed file matches its locked hash |
| modified | A managed file differs from its locked hash. The next `sync` makes it the project's own unless it is reverted |
| missing | A managed file is absent. The next `sync` makes it the project's own unless it is reverted |
| template updated | A seeded file's template changed since it was seeded, or since the project made a managed file its own. The file itself is never compared |
| excluded | The project listed the path under `[kit] exclude` and owns it |

Files not in the lock are project-authored and not reported. When `status` lists a modified or missing file, it also prints how to revert it: `rapid-ship sync --revert <path>`. `--strict` exits 1 unless every managed file that is not excluded is unchanged and matches the current template. rapid-ship's own CI runs `--strict`.

### `rapid-ship sync`

1. **Preconditions:** a clean work tree, except with `--in-place`, which keeps uncommitted edits: it replaces only files equal to their locked content and makes the rest the project's own (step 4). Sync compares template hashes, not version numbers; when nothing changed it reports that and stops.
2. Create the branch `rapid-ship/kit-sync-<version>`. It does not use the `rs/` prefix, which `dispatch` counts as Worker claims.
3. Overwrite each unchanged managed file with its new template. Add new managed files, including the optional skills listed under `[kit] optional` in `project.toml`. Delete managed files the Kit dropped, if unchanged. Skip every path under `[kit] exclude`: sync never creates, replaces, deletes or reports it.
4. A managed file that differs from its locked content, or is missing, is the project's own: the project edited or deleted it, or changed a managed symlink's target. Sync never changes that file. It records the entry as seeded, with the current template's hash, and lists the path under a heading that says the project owns it now, with one line on how to revert. A file that already equals the new template is not an edit: sync records it as managed with the new hash. An edited file the Kit dropped keeps a seeded entry with its locked hash; a dropped file that is already gone leaves the lock.
5. `--revert <path>`, repeatable, gives a file back to the Kit. Sync writes the current template over the project's file and records the entry as managed again. It accepts a path whose current template is managed: a file the project owns after step 4, or a modified or missing managed file that this sync would otherwise make the project's own. Any other path refuses the whole sync with exit 1 before anything is written, and the reason names the path: a path that is not a Kit file, a path under `[kit] exclude`, a seeded template, or a file the Kit dropped. Naming an unchanged managed file changes nothing.
6. Never change an existing seeded or project-authored file. Create a seeded file that a newer Kit adds only where nothing exists at its path. List seeded files whose template changed, including managed files the project made its own.
7. Update the lock, commit, and open a PR with `gh` under the owner's login. The owner merges it. `--in-place` instead writes the changes to the work tree without a branch, commit or PR.

### `rapid-ship app`

The owner has two GitHub Apps. They belong to the owner, not to one project: `app` creates them on the first project and installs them on each later one.

| App | Permissions | Used by |
| --- | --- | --- |
| Worker App | Contents, Pull requests and Issues: read and write. Metadata: read | `devctl dispatch` and `devctl pr` |
| Reviewer App | Pull requests: read and write. Contents and Metadata: read | `devctl review` |

Neither App has the Workflows, Administration or Checks permission.

1. If an App does not exist yet, create it through GitHub's manifest flow. A local HTTP server on `127.0.0.1` opens the browser at a page that posts the manifest. The App is private and has no webhook. The command exchanges the returned one-time code at `POST /app-manifests/{code}/conversions`.
2. Store each private key in the macOS Keychain, under `rapid-ship/worker-app` and `rapid-ship/reviewer-app`. Never write a key to disk or print it.
3. Print each App's ID and its installation URL for the current repository.

### `rapid-ship adopt`

`adopt` brings an existing project's current violations under the exceptions rule, once, at Setup. It gives every unmarked suppression an `rs-exception` ID and an entry with the reason "Existed at Setup on <date>" and the removal condition "Remove when this code next changes". The owner reviews the result in the Setup PR.

### Who owns what

`sync` sorts every path into one of four groups, and respects the project's choices in each.

| Group | Examples | What `sync` does |
| --- | --- | --- |
| Language-agnostic Kit | devctl core, the `rs-` skills, settings seeds, the CI workflow | Updates unchanged files. A file the project edits or deletes becomes the project's own: sync records that, never changes the file, and says how to revert it |
| Stack Kit | Python guardrail seeds and check steps | The same, using the stack's version where a stack file and a common file share a path |
| Project extensions | `tools/devctl/devctl_project/` (project verbs and check steps), the project's own skills under `.agents/skills/`, extra workflows | Never touches them. Seeded files are reported when their template changes |
| Project overrides | A Kit path listed under `[kit] exclude` | Never touches it again. The project owns it from then on |

Editing or deleting a managed Kit file makes it the project's own. The next `sync` records it as seeded, stops updating it and reports only later template changes (step 4); `sync --revert <path>` gives it back (step 5). The seeded root `AGENTS.md` tells agents so. To change behaviour and keep Kit updates, a project uses `devctl_project` and its settings. A project that wants a Kit file never reported, or not present at all, lists it under `[kit] exclude`. Excluding a skill's directory also excludes its `.claude/skills` link. `[kit] exclude` is the only record of an exclusion: `status`, `sync`, `check` and `doctor` all read it there. In this repository nothing is excluded and no managed file is the project's own, so `status --strict` holds every Kit file to its template, and this repository's own additions live in `devctl_project` and in files the Kit does not manage.

### Package layout

```text
rapid_ship/
  cli.py              # init, status, sync, app, adopt
  kit/                # lock, classification, init, sync, adopt
  github_app.py       # manifest flow, installation and Keychain storage
  files.py            # kept from the old package; process.py moves into devctl
  templates/
    common/           # every stack: devctl, tools/devctl, skills, settings, CI, hooks
    python/           # Python stack: pyproject.toml seed, guardrail settings, check steps
    neutral/          # stack-neutral additions, if any
```

The upstream lock for forked skills (section 7) lives in this repository only, beside the templates.

### Lock file

`.rapid-ship/kit.lock` is TOML:

```toml
kit_version = "0.2.0"
stack = "python"

[[file]]
path = "tools/devctl/devctl/check.py"
kind = "managed"
sha256 = "…"

[[file]]
path = ".claude/skills/rs-tdd"
kind = "managed"
link = "../../.agents/skills/rs-tdd"

[[file]]
path = "AGENTS.md"
kind = "seeded"
template_sha256 = "…"
```

An entry moves from managed to seeded when the project edits or deletes the file (`sync` step 4), and back to managed through `sync --revert` (step 5). A seeded entry's `template_sha256` is the hash of the template's content, or of a symlink template's target.

### Dog-fooding

This repository runs `uv run rapid-ship init` on itself. The vendored copy lives where any project's would. Here `uv run rapid-ship sync --in-place` refreshes the vendored copy from the working-tree templates, so a template change and its vendored copy land in the same PR. CI runs `rapid-ship status --strict` and `./devctl check --tier full`. Once it does, `scripts/check.py` and `scripts/check_repository.py` are deleted.

## 4. Kit contents

| Path | Kind | Purpose |
| --- | --- | --- |
| `devctl` | managed | Shim that runs devctl from `tools/devctl/` with `uv run --frozen` |
| `tools/devctl/` | managed | devctl source with its own `pyproject.toml` and `uv.lock` |
| `tools/devctl/devctl_project/` | seeded | Project verbs and extra check steps; Plan adds to it |
| `.agents/skills/rs-*/` | managed | Kit skills, one canonical copy |
| `.claude/skills/rs-*` | managed | Relative symlinks to `.agents/skills/rs-*`. Where a symlink cannot be created, `init` and `sync` stop with exit 2 and leave nothing half-written |
| `.github/workflows/devctl-check.yml` | managed | CI |
| `.githooks/pre-commit` | managed | Runs `./devctl check --tier fast` |
| `.rapid-ship/kit.lock` | managed | Written by the CLI |
| `.rapid-ship/project.toml` | seeded | Agents, GitHub, Linear, dispatch and map settings |
| `.rapid-ship/gate.toml` | seeded | Mode, Flight lease and thresholds |
| `.rapid-ship/exceptions.toml` | seeded | Break-glass exceptions |
| `AGENTS.md` | seeded | Short root guide |
| `CLAUDE.md` | seeded | `@AGENTS.md` |
| `.github/CODEOWNERS` | seeded | During Walk, one line `* @<owner>`, so every change needs the owner. Below it, commented out for Flight, the Protected set: the `devctl` shim, `.github/`, `.githooks/`, `tools/devctl/`, `.agents/skills/`, `.claude/skills/`, `.rapid-ship/`, guardrail settings, existing Pattern files, and any paths the project adds for access, data model or public API |
| `docs/features/README.md` | seeded | The feature-file format |
| `docs/patterns/README.md` | seeded | The Pattern-file format |
| `pyproject.toml`, `src/<package>/__init__.py`, `tests/test_import.py` | seeded, Python, new projects only | Guardrail settings, dev dependencies and a skeleton that passes `check` |

devctl runs through uv for every stack. Its own lock keeps its dependencies apart from the project's. Kit-owned code is excluded from the project's lint, type and test settings; this repository checks it upstream.

### Settings files

None of these holds a secret. All are in the Protected set.

`.rapid-ship/project.toml`:

```toml
stack = "python"

[agents.worker]
harness = "agy"
model = "gemini-3.8-flash-high"

[agents.reviewer]
harness = "claude"
model = "<exact model ID>"

[github]
repository = "owner/name"
worker_app_id = 0
reviewer_app_id = 0

[kit]
optional = []     # opt-in Kit skills, such as "rs-contribute"
exclude = []      # Kit files or directories the project owns instead

[linear]
team_id = ""
project_id = ""

[dispatch]
max_workers = 5
attempt_limit = 3
worktree_root = "../<repo>.worktrees"

[map]
source_roots = ["src/<package>"]
unguided = []

[tests]
unit = ["tests/unit/**"]   # every other test counts as behavioural

[release]
method = "none"   # github-deployments, tags or none
```

`.rapid-ship/gate.toml` holds `mode = "walk"`, an empty Flight lease, `owner_approves_behavioural_test_removal = true` and the default thresholds from the [design](2026-10-14-rapid-ship-design.md#how-autonomy-is-earned-and-lost). Spec 3 defines how they are read.

`.rapid-ship/exceptions.toml` holds the break-glass entries:

```toml
[[exception]]
id = "EX-1"
path = "src/app/run.py"
rule = "S603"
reason = "Runs the project's own build tool with fixed arguments"
remove_when = "The build tool has a Python API"
```

### Root AGENTS.md skeleton

The root guide stays short, following upstream `writing-for-agents`:

1. One paragraph naming the project.
2. Commands: `./devctl check`, `./devctl doctor` and the project's verbs.
3. A "Find the change" table that points to directory guides, `docs/features/` and `docs/patterns/`.
4. **Rules.** Each rule ends with `enforced by: <reference>` or `advisory` (section 5).
5. Pointers to `GLOSSARY.md`, `docs/adr/`, `rs-writing` and `rs-ponytail`.

### CI workflow

`.github/workflows/devctl-check.yml`:

- **Triggers:** `pull_request`, including body edits; `push` to `main` or `master`; a nightly `schedule`; and `workflow_dispatch`. A workflow cannot name the default branch, and a push run skipped by a condition would report a passing `devctl check` on the same commit, so the branches are listed. `rs-setup` records a Setup gap when the default branch has another name.
- **Permissions:** `contents: read` only. The job uses no secrets, so fork PRs behave the same.
- **Concurrency:** one group per ref; PR runs cancel superseded runs.
- **Steps:** checkout and `astral-sh/setup-uv`, both pinned by commit SHA, with `persist-credentials: false` and full history for the diff policy. Install the pinned gitleaks release, verified by checksum. Run `./devctl check --tier full`.
- **Job name:** `devctl check`, which the ruleset requires.

The nightly run checks the default branch. Spec 3 turns its failure into an Alarm.

### Python guardrail settings

New projects get these settings in the seeded `pyproject.toml`. For existing projects, `rs-setup` merges them into the existing configuration, and `devctl doctor` reports what is still missing.

- **Ruff:** E, W, F, I, B, UP, SIM, C4, RUF, PGH, ERA, T20, S, TID, PT, PTH, DTZ, C90, TD, BLE and ANN401, plus ASYNC and FAST when those frameworks are detected. Relative imports are banned. A `banned-api` table starts empty, and Patterns fill it. PGH003, PGH004, RUF100 and ERA001 control escape hatches.
- **mypy:** strict over source and tests, with `warn_unreachable` and the error codes `ignore-without-code`, `redundant-expr` and `truthy-bool`.
- **import-linter:** one `layers` contract and one `forbidden` contract.
- **pytest:** `--strict-markers --strict-config`, `xfail_strict = true`, `filterwarnings = ["error"]`.
- **Dev dependencies:** ruff, mypy, pytest and import-linter in the project's lock.

There is no ratchet. Unsafe patterns are prohibited. A legitimate exception is a listed break-glass entry (section 5).

## 5. `devctl check`

`check` is the single entry point for hooks and CI. It covers everything a machine can decide and never runs a model.

### Steps

| Step | Tier | Fails when |
| --- | --- | --- |
| format | fast | Formatting differs (Python: `ruff format --check`) |
| lint | fast | The linter reports a finding (Python: `ruff check`) |
| map | fast | The map rules below fail |
| exceptions | fast | A suppression lacks a listed exception, or an exception matches nothing |
| file-size | fast | A source file exceeds the line cap without an exception |
| kit | fast | The lock is unreadable, or a managed file that is not excluded is missing |
| types | full | The type checker fails (Python: mypy) |
| contracts | full | An import contract is broken (Python: `lint-imports`) |
| tests | full | The test suite fails (Python: pytest) |
| audit | full | A dependency has a known vulnerability (Python: `pip-audit`; `uv audit` is still experimental) |
| secrets | full | gitleaks finds a secret |
| workflows | full | zizmor reports a finding |
| diff | full | The diff policy below fails |
| evidence | full, PRs only | The PR body lacks its Evidence section |

The stack kit supplies the Python column. The neutral kit runs every step that is not language-specific. A project adds steps in `devctl_project`.

### Output and exit codes

- One line per step: passed, failed, blocked, or not applicable. `--json` prints the same as data.
- Exit 0: every applicable step passed.
- Exit 1: at least one step failed.
- Exit 2: at least one step could not run, for example a missing tool or an unreadable setting. A blocked step never counts as passed.
- `--tier fast` runs fast steps only. The default is `full`.

### Map rules

1. Every Markdown link in every AGENTS.md resolves to a tracked or non-ignored file.
2. Every maintained directory has an AGENTS.md. Maintained directories are the top-level tracked directories and the immediate children of each source root, except hidden directories and those listed in `[map] unguided`.
3. Every AGENTS.md is reachable by links from the root AGENTS.md.
4. Every file in `docs/features/` other than its README has front matter with `purpose`, `entry_points`, `data`, `observe` and `reproduce`. Each path it names exists. Each `reproduce` command is a registered devctl verb.
5. Every file in `docs/patterns/` other than its README has front matter with `reference`, a path that exists, and a non-empty `enforced_by` list whose references resolve.
6. Every bullet under a `Rules` heading in any AGENTS.md ends with `enforced by: <reference>` or `advisory`. Each reference resolves.
7. Every skill directory under `.agents/skills/`, from the Kit or the project, has a `SKILL.md` whose front matter `name` equals the directory name and whose `description` is not empty, and a relative symlink at `.claude/skills/<name>` that points to it. No other entry exists under `.claude/skills/`.

### References

A reference names the check that enforces a Rule or Pattern. The stack kit defines the kinds; `check` resolves each one.

| Reference | Resolves when |
| --- | --- |
| `check:<step>` | The devctl check step exists |
| `test:<path>::<name>` | The test exists |
| `ruff:<code>` | The rule is selected in the Ruff settings (Python) |
| `banned:<module.member>` | The member is in Ruff's `banned-api` table (Python) |
| `contract:<name>` | An import-linter contract has that name (Python) |
| `type:<path>` | The file exists and mypy checks it (Python) |

These map to the four Pattern enforcement types: import contract, banned-API rule, type fixture and architecture test.

### Exceptions

A suppression is a line that switches a check off. For Python these are `# noqa`, `# type: ignore`, `# pragma: no cover` and the skip and xfail markers.

1. Each suppression carries `rs-exception: EX-<n>` on the same line.
2. `EX-<n>` exists in `.rapid-ship/exceptions.toml` with a matching path and rule, a reason and a removal condition.
3. Each ID is used exactly once. An entry that matches no suppression fails as stale.
4. File-size exceptions are path entries with `rule = "file-size"` and no inline marker. They fail as stale once the file is under the cap.

An added suppression therefore needs an edit to `exceptions.toml`, which is Protected. Nothing is counted, so removing one suppression cannot pay for adding another. For an existing project, `rapid-ship adopt` marks each existing suppression in place at Setup (section 3).

### Diff policy

The diff policy compares the change with its base: the PR base in CI, or the merge base with the default branch locally. It is adapted from no_human's test-tamper guard (MIT), using each test's identity instead of its net counts.

1. **Removed tests:** a test present at the base and absent everywhere at the head fails, unless the PR body declares it under `Removed tests:` with a reason. A test moved to another file keeps its identity and is not a removal. The step classes each removed test as unit or behavioural. A test is a unit test only when its path matches `[tests] unit` in `project.toml`; every other test, such as an integration or end-to-end test, is behavioural. In Walk the owner sees every declaration. In Flight a declared unit-test removal needs nothing more, while a behavioural-test removal waits for the owner. `gate.toml` can turn that off with `owner_approves_behavioural_test_removal = false`; it is on by default. The Flight merge gate enforces it.
2. **Tautologies:** an assertion that the change turns into a tautology, such as `assert True` or `x == x`, fails.
3. **Faking fixtures:** a new `autouse` fixture in a `conftest.py` fails without an exception.
4. **Protected paths:** the step lists any Protected path the change touches. It does not fail; CODEOWNERS enforces approval.

Skip markers are suppressions, so the exceptions step handles them.

### Evidence

On a PR, the body must contain an `## Evidence` section with at least one command and its result, and a line starting `Not covered:`. When the change removes tests, the section also lists them under `Removed tests:`. The `rs-pr` skill writes this section. CI reruns the check when the PR body is edited.

### Where `check` runs

1. The pre-commit hook runs the fast tier. It can be skipped.
2. `rs-work` runs it as its last step. That run is advisory.
3. CI runs the full tier on every PR. The ruleset requires it; this is the enforcement.
4. The nightly CI run checks the default branch.

## 6. Other devctl commands

devctl keeps only commands used repeatedly: `check`, `doctor`, `dispatch`, `pr` and `review`. One-time setup lives in the rapid-ship CLI.

GitHub writes from devctl go through the Worker App or the Reviewer App. devctl mints a token for each command and holds it only in memory:

1. Read the App's private key from the Keychain, for example with `security find-generic-password -s rapid-ship/worker-app -w`. An item written by `security` trusts `security` itself, so reads show no dialog and any process the owner runs can read both keys. Walk therefore does not protect App keys from Workers; Flight needs another key store or access rule first.
2. Sign a JWT and request an installation token for this one repository.
3. Pass the token to git through a `GIT_ASKPASS` helper that reads an environment variable. Never put it on a command line, in a file or in output.

Keychain storage makes these commands macOS-only.

### `devctl doctor`

It changes nothing in the repository. It reports each item as ok, missing or unknown.

- **Toolchain:** git, uv, gh and gitleaks, and each Harness named in `project.toml`. Claude Code and Codex CLI report their sign-in through their own status commands. Antigravity CLI has none, so doctor starts a new headless Session with the cheapest model, sends `hi`, and counts a non-empty reply as signed in; agy's exit code alone proves nothing. doctor never reads a token file.
- **Guardrails:** the stack's required settings (section 4), `core.hooksPath` set to `.githooks`, and the CI workflow.
- **Kit:** the `rapid-ship status` summary.
- **GitHub,** read with the owner's `gh` login: the ruleset on the default branch matches the settings in section 8; CODEOWNERS matches the current Mode; head branches are deleted after merge; both Apps are installed on this repository with exactly their listed permissions; public repositories require approval for workflows from outside contributors.
- **App keys:** both Keychain items exist and can mint a token. Minting changes nothing in the repository.
- **Linear:** team and project IDs are present. doctor cannot verify Linear and says so; `rs-setup` verifies it through Linear's MCP.

`devctl doctor --skills` also checks what a Worker would see. For each Harness the Worker and Reviewer use, it creates a temporary worktree at the default branch's head the way `dispatch` does, starts one new headless Session there with the cheapest model, and asks which skills it can load. A Kit or project skill the Session cannot see is missing. A user-invoked skill (`disable-model-invocation: true`) is reported as not checked, because a Harness may leave it out of its list. Skills the Session sees from outside the repository, such as the owner's user-level skills or plugins, are listed for the owner to judge. The worktree is removed afterwards. `rs-setup` runs it; the owner reruns it after adding a skill or upgrading a Harness. Each probe uses a little quota. doctor never starts Antigravity CLI from inside another coding session, because Google does not support that; there it reports agy items as unknown and asks the owner to run doctor from their own terminal.

Exit 0 when everything is ok, 1 when something is missing, 2 when an item could not be checked.

### `devctl dispatch`

`devctl dispatch <ISSUE> [--retry]` admits one Worker.

1. Check the issue ID format, for example `ENG-123`.
2. **Cap:** count active claims, which are remote branches under `rs/`. In Walk the cap is the lower of 5 and `max_workers`. At the cap, refuse.
3. **Attempt limit:** count this issue's earlier admissions in the gate log. At `attempt_limit`, refuse.
4. **Claim:** create the remote branch `rs/<issue-id>` at the default branch's head, only if it does not exist, as the Worker App. If it exists, refuse unless `--retry` is given; `--retry` reuses it.
5. Create a worktree for the branch under `worktree_root`.
6. Append one line to the gate log: time, command, issue, answer, reason, branch and attempt number.
7. Print the start command for the Worker Agent, from a template per Harness. Spec 2 fixes the templates.

The branch name contains the issue ID, so Linear links the PR to the issue.

- `devctl dispatch --status` lists claims with their PR state, worktree and attempts.
- `devctl dispatch --clean` removes worktrees whose PR is merged or closed, and deletes remote branches of closed, unmerged PRs. It logs each removal.

The gate log is `<git common dir>/rapid-ship/gate-log.jsonl`. It records every request to a gate, with the answer and the reason: admissions from `dispatch` now, and merge checks from Spec 3. It is shared by every worktree of the clone and never tracked. Pre-flight reads it (Spec 3). A lost log is missing data, which blocks promotion.

Exit 0 when admitted, 1 when refused, 2 on error.

### `devctl pr`

`devctl pr [--title <text>] [--body <path>]` runs on an `rs/` branch with committed work.

1. Push the branch as the Worker App. A non-fast-forward push is refused; the Worker merges the base branch instead of rebasing.
2. If no PR is open for the branch, open one with the given title and body. Otherwise update the body when a new one is given.
3. Print the PR URL.

Agent PRs are the ones the Worker App opened. Metrics count only those. The owner opens their own PRs as usual and merges them through the bypass.

### `devctl review`

`devctl review <PR> --verdict <path>` posts the Reviewer's review through the Reviewer App.

The verdict file is JSON:

```json
{
  "head_sha": "…",
  "verdict": "approve | changes_requested",
  "summary": "…",
  "findings": [
    {
      "severity": "blocking | non_blocking",
      "path": "src/app/links.py",
      "line": 42,
      "message": "…",
      "rung": 1,
      "prevention": "One sentence naming the mechanism that prevents a repeat"
    }
  ],
  "reviewer": {"harness": "claude", "model": "…", "session_id": "…"}
}
```

1. Validate the file against the schema.
2. Refuse when `head_sha` is not the PR's current head.
3. Refuse when the Reviewer App already reviewed this head. A head gets one verdict.
4. Submit a review on `head_sha`: Approve or Request changes, as the verdict says. Add an inline comment for each finding that has a path. Put the summary in the body, with the findings in a fenced `rapid-ship-verdict` block so the corrections ledger can read their rungs.
5. Print the review URL.

## 7. Skills in the Kit

Kit skills are forked per skill from mattpocock/skills (MIT), pinned at `49dd158`, and kept as close to upstream as rapid-ship allows. Each forked skill directory carries the upstream licence notice. This repository's upstream lock records, for each upstream file: path, upstream commit, upstream blob SHA, and status (`verbatim` or `patched`). A test requires `verbatim` files to match their blob SHA and `patched` files to differ only inside marked rapid-ship sections.

| Skill | Source | Spec |
| --- | --- | --- |
| `rs-setup` | rapid-ship; shape from upstream `setup-matt-pocock-skills` | 1 |
| `rs-health` | rapid-ship; classification rules from upstream `retro` | 1 |
| `rs-tdd` | upstream `tdd`, near verbatim; seams come from the brief | 1 |
| `rs-diagnosing-bugs` | upstream `diagnosing-bugs`, near verbatim | 1 |
| `rs-codebase-design` | upstream `codebase-design`, verbatim | 1 |
| `rs-pr` | upstream `pr`; Evidence adds commands run and `Not covered:`. Carries the HumanLayer credit | 1 |
| `rs-writing-for-agents` | upstream `writing-for-agents`, verbatim | 1 |
| `rs-writing` | this repository's `writing.md` | 1 |
| `rs-ponytail` | this repository's `ponytail.md` | 1 |
| `rs-contribute` | rapid-ship; optional, installed only when chosen at Setup | 1 |
| `rs-plan`, `rs-grilling`, `rs-domain-modeling`, `rs-to-spec`, `rs-to-tickets` | upstream, with a verification design per ticket | 2 |
| `rs-walk`, `rs-work`, `rs-review`, `rs-garden`, `rs-playbook-author` | rapid-ship and upstream `implement`, `code-review`, `retro`; Anthropic's skill-creator | 2 |

- The `rs-` prefix avoids collisions with Claude Code's built-in commands and with an installed upstream plugin.
- When the Kit skills land, `rapid-ship-engineering` is deleted and root `AGENTS.md` points to `rs-writing` and `rs-ponytail`.
- Workers and the Reviewer follow the skills at the PR's base commit. The Kit supports this by keeping skills as plain files in the repository; Spec 2 defines how each role reads them.

### `rs-contribute`

`rs-contribute` sends a Kit fix from a project back to rapid-ship. It is user-invoked and installed only when the owner opts in at Setup.

1. Describe the problem with the evidence that shows it: the command, the output, the Kit file involved.
2. Map the project file to its template through the lock.
3. Search rapid-ship's open issues and PRs for a duplicate.
4. In a cached fork of rapid-ship, fix the template and refresh the vendored copy with `rapid-ship sync --in-place`.
5. Run rapid-ship's own `./devctl check`.
6. Open a PR to rapid-ship. Leave out project code, secrets and private paths. If the fix is unclear, open an issue instead.

The project may apply the same change to its vendored copy at once; `rapid-ship status` shows it as modified. When the fix ships, `rapid-ship sync` finds identical changes and the file returns to unchanged.

## 8. `rs-setup`

`rs-setup` is user-invoked. It runs in the owner's Harness after `init` has been committed on a branch. It journals each external write in its conversation before making it, and re-reads the outside state before retrying an uncertain one.

### Steps for every project

1. **New or existing.** A repository with source beyond the Kit is existing.
2. **Agents.**
   1. List the installed Harnesses and their sign-in state, using each CLI's own status command. Never read token files.
   2. The owner picks the Worker Agent and the Reviewer Agent: a Harness and an exact model each. Recommend a Reviewer from a different Provider.
   3. Send each Agent one tiny headless prompt to prove the sign-in and the model. This uses a little quota.
   4. Record both in `project.toml`.
3. **GitHub.**
   1. Find the repository, or create it with `gh` after the owner confirms its visibility.
   2. Run `uvx rapid-ship app`. On the owner's first project it creates the Worker App and the Reviewer App; later it only installs them. The owner approves each installation. Record both App IDs.
   3. After the owner confirms, apply the ruleset from the skill's `ruleset.json` with `gh api`, and turn on automatic deletion of head branches. The ruleset targets the default branch. It requires a PR with one approval and code-owner review, and the status check `devctl check` with GitHub Actions as its source. It dismisses approvals when new commits arrive and requires the most recent push to be approved by someone other than its pusher. It blocks force pushes and deletion. Its bypass list holds only the repository admin role, in pull-request-only mode, so the owner can merge their own PRs directly.
   4. For a public repository, require approval for workflows from all outside contributors. If the default branch is neither `main` nor `master`, record a Setup gap: CI push runs cover only those two names.
   5. Write `* @<owner>` into CODEOWNERS.
4. **Linear.**
   1. Confirm that each Harness used by the Lead or a Worker has Linear's official MCP, `https://mcp.linear.app/mcp`.
   2. The owner picks or creates the team and project. Record their IDs.
   3. Create the labels `ready-for-agent` and `needs-human`, and the epic approval state that Spec 2 defines.
   4. The owner turns on Linear's GitHub integration for the repository in Linear's settings, with In Review on PR open and Done on merge. The skill records this as configured, not verified. The first task's PR link verifies it.
5. **Guardrails.**
   - Confirm gitleaks is installed with `gitleaks version`; if not, ask the owner to install it.
   - New project: run `uv sync` and `./devctl check`. The seeded skeleton passes.
   - Existing project: exclude `tools/devctl` from the project's own lint, type, test and uv settings first, then merge the stack's settings into the existing configuration, mark existing findings in place with suppressions, and run `uvx rapid-ship adopt`. Run `./devctl check` until it passes.
   - Run `git config core.hooksPath .githooks`.
6. **Thresholds.** Show the defaults in `gate.toml`. The owner may change them.
7. **Existing projects only:** ask how the project starts, which smoke commands it has, and how it releases. Record the release method. For new projects, Plan designs these.
8. **Contributing back.** Offer `rs-contribute`. If the owner accepts, add it to `[kit] optional` and run `uvx rapid-ship sync --in-place`.
9. **Doctor.** Ask the owner to run `./devctl doctor --skills` from their own terminal, then resolve or record each gap. The skills probe reads the default branch, as `dispatch` does, so skills that the Setup branch adds or changes are recorded as a gap to recheck after the Setup PR merges.
10. **Setup PR.** Commit and open the PR. The owner merges it.
11. **Next.** Offer `rs-health` to an existing project. Point to `rs-plan` for a new project or a supplied design, and to one small real task through the Walk flow (Spec 2).

## 9. `rs-health`

`rs-health` is user-invoked. Setup offers it to existing projects, and the owner can rerun it at any time. It changes nothing in the repository.

- **Reads:** the code, `devctl doctor` and `devctl check` output, the CI configuration and recent runs, and the last merged PRs with their review comments.
- **Reports by rung:** missing safe interfaces and the bypasses they would ban; missing checks; gaps in the feature map and Patterns; missing functional test tiers; repeated review comments that a rung could prevent. Each item cites file:line or command output.
- **Proposes:** one Linear issue per item, written as an agent brief. It creates the issues the owner selects, in the backlog and without `ready-for-agent`.

## 10. Testing

**Unit tests**, offline:

- Lock reading and writing, and status classification.
- `init`: conflicts, seeded skips, symlinked targets and the never-overwrite rule.
- `sync`: unchanged files replaced; edited and deleted files made the project's own and never changed; `--revert` and its refusals; excluded paths never touched; project extensions untouched; the stack version winning over the common one.
- Each check step's rules, with fixture repositories: map, references, exceptions, removed tests, tautologies, evidence.
- `dispatch` against a local bare repository standing in for GitHub: claim atomicity under two concurrent claims, the cap, the attempt limit, and `--clean`.
- Token minting and `review` against a local fake HTTP server: schema validation, stale head and one verdict per head.
- The removed-test rule: a moved test passes, an undeclared removal fails, a declared one passes, and each removal is classed unit or behavioural by its path.
- `doctor` parsers against recorded API responses; the agy probe and `--skills` against fake Harness executables.

**Integration tests**, offline and labelled as such:

- `init` on scratch repositories for both stacks, then `./devctl check` passes.
- `sync --in-place` between two template versions, and `adopt` on a repository with existing suppressions.

**Live trials**, recorded under `docs/trials/`:

- `rapid-ship app` creating both Apps, then installing them on a second repository.
- The ruleset applied and read back by `doctor`. The trial also records whether a Reviewer App approval counts toward the required approval; the `* @<owner>` CODEOWNERS line makes the owner's approval necessary either way.
- `rs-setup` on a real scratch repository, including `doctor --skills` for each Harness it uses.

**Dog-food:** this repository's CI runs `./devctl check --tier full` and `rapid-ship status --strict`.

## 11. Open questions for the plan

- Default caps: lines per source file (500 proposed) and Ruff's `max-complexity` (10 proposed).
- Whether agy can use Linear's MCP. If a Worker Harness cannot, the Lead writes the start comment instead.
- Whether Linear's MCP can create labels and workflow states, or the owner creates them in Linear's settings.
