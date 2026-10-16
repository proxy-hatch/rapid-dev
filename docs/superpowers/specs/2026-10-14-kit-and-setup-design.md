# Spec 1: Kit and Setup

**Status:** revised on 2026-10-16 for the team-management boundary ([ADR 0004](../../adr/0004-team-management-boundary.md)). Plans 1 to 3 are built. Plans 4 to 6 are proposed in the [plan index](../plans/2026-10-14-kit-and-setup.md). This is the first of the three specs in the [rapid-ship design](2026-10-14-rapid-ship-design.md), and its terms follow `GLOSSARY.md` at the repository root. A detail marked **Proposal** is not yet confirmed by the owner; [section 11](#11-questions) lists each one.

## 1. Scope and outcome

When this spec is built, an owner runs `uvx rapid-ship init` in a new or existing repository, then runs the `rs-setup` skill in their Harness, and ends with:

- the Kit vendored and recorded in its lock;
- `devctl check` in the pre-commit hook, in the Stop hook of Claude Code, Codex and agy, and in CI as a required status check;
- the Kit's Harness guardrails for Claude Code, Codex and agy;
- README.md, ARCHITECTURE.md, the AGENTS.md tree, the feature map and the first Patterns, each verified by `devctl check`;
- the ruleset and CODEOWNERS applied for Walk, and `devctl doctor` reporting no gap that the owner has not accepted;
- optionally, Agent identity: two GitHub Apps that agents act as through `devctl as`;
- Suggested thresholds recorded and, optionally, the scheduled metrics Action installed, both as [Spec 3](2026-10-16-metrics-and-gardening-design.md) defines them;
- for an existing repository, a standards milestone from `rs-health` in the owner's tracker.

This spec covers the `rapid-ship` command (section 3), the Kit's files (section 4), `devctl check` (section 5), devctl's other commands (section 6), the skills the Kit ships (section 7), and the skills `rs-setup` (section 8) and `rs-health` (section 9).

Out of scope:

- [Spec 2: Delivery skills](2026-10-16-delivery-skills-design.md): `rs-design`, `rs-breakdown`, `rs-lead`, `rs-work`, `rs-review` and the tracker mapping notes. Section 4 stores the escalation list and the Roster; Spec 2 says how `rs-lead` builds a Lead brief from them.
- [Spec 3: Metrics and gardening](2026-10-16-metrics-and-gardening-design.md): `devctl metrics`, the scheduled metrics Action, Suggested thresholds and where they are recorded, project-defined metrics, the Corrections ledger and `rs-garden`. `rs-garden` reruns the audit that section 9 defines.
- Anything that starts an agent Session to do work, watches or resumes one, or pushes, reviews or merges as a step in a flow ([ADR 0004](../../adr/0004-team-management-boundary.md)).

GitHub is the only supported remote. rapid-ship works with any issue tracker that the owner's Harness can reach through an MCP server or a CLI, and devctl never talks to the tracker. The owner's machine must run macOS for now: Agent identity keeps its App keys in the macOS Keychain, and on Windows git can check the skill links out as plain files. `devctl check` also runs on Linux, as CI does.

### What changed on 2026-10-16

The re-scope removed these parts of this spec: `devctl dispatch`, `pr`, `review` and `merge`, with Claims, Release, the gate log and the Session registry; the `[dispatch]` settings and `review_round_limit`; `gate.toml`, with its Mode, Flight lease and test-removal switch, and the `diff` step's Flight note that read it; doctor's Linear item and `rs-setup`'s Linear step; the requirement for Agent identity; subscription sign-ins as a product rule; the `rapid-ship adopt` command, folded into `rs-setup`; the old skill list's `rs-plan`, `rs-walk`, `rs-grilling`, `rs-domain-modeling`, `rs-to-spec`, `rs-to-tickets` and `rs-playbook-author`, which `rs-design` and `rs-breakdown` replace; and the live trials of the Walk flow. Plan 4's branch, `codex/github-commands`, is kept as history, and its surviving code moves into the new plan 4. The Kit gains Harness guardrails, README and ARCHITECTURE seeds, the Pattern's `task` key, a diff cap, the escalation list and the Roster, and the thin command `devctl as`.

### Dog-fooding

*This paragraph describes this repository's own configuration, not product behaviour.* rapid-ship vendors its own Kit (section 3) and is validated on itself and on its sample project, hello-rapid-ship. Its tracker is Linear. Its agents sign in with vendor subscriptions only, and the owner accepts the risk of running agy inside another Session, including `devctl doctor`'s agy probe ([ADR 0001](../../adr/0001-subscription-logins-only.md)). agy is never a Reviewer here. This repository records these choices as rules in its root AGENTS.md; no Kit file enforces them.

## 2. Removing the old controller

Built in plan 1. The last commit that contains the controller is tagged `archive/controller-2026-10` (`f7b877b`).

1. The controller code and its tests were deleted: `rapid_ship/execution/`, `rapid_ship/trust/` and `rapid_ship/project/`; the old `cli.py`, `models.py`, `storage.py`, `logs.py`, `protocol_json.py`, `metrics.py`, `github_metrics.py` and templates; the root controller `devctl` with its build and smoke scripts; the `tests/typecheck_*.py` fixtures; and `examples/`.
2. `rapid_ship/files.py` stayed. `rapid_ship/process.py` moved into devctl in plan 3. The console script is `rapid-ship`.
3. The `rapid-ship` and `rapid-ship-improve` skills were deleted. `rapid-ship-engineering` stays until plan 6's Kit skills replace it; the optional `rs-contribute` replaces `rapid-ship-improve`.
4. The controller-era records moved into `docs/archive/orchestrator/`, as the [archive dossier](../../archive/orchestrator/README.md) lists, and the remaining old guides start with a "Historical" line.
5. `README.md`, `ARCHITECTURE.md`, the root `AGENTS.md` and `CLAUDE.md` were rewritten for the Kit.

Later plans reused these parts of the tagged commit:

| Source at the tag | Reused in |
| --- | --- |
| `rapid_ship/files.py`: `atomic_replace` and the safe-path helpers that refuse symlinks and never overwrite | The rapid-ship CLI (plan 2) |
| `rapid_ship/process.py`, the bounded process runner | devctl (plan 3), with the caller's `PATH` and truncation reported in flags rather than in the output. Plan 4 adds two more fixes from its old branch (`de800ae`, `98082fb`) |
| `scripts/check_repository.py` and `scripts/check.py` | devctl's `map` step and `devctl check` (plan 3), which deleted both scripts |
| `rapid_ship/trust/github.py` `inspect_protection` | Replaced by doctor's ruleset item (plan 4), which reads rulesets rather than branch protection |
| `tests/typecheck_*.py`, `assert_type` fixtures checked by mypy | The `type:` reference kind (section 5) |
| `docs/metrics.md`: definitions and the rule that a missing metric is unknown | Spec 3 |

## 3. The rapid-ship CLI

The rapid-ship CLI is a small Python package run with `uvx`; nothing is installed. It holds what runs once or rarely, so devctl keeps only the commands that people, agents and CI use repeatedly. In both CLIs each command is one word followed by arguments.

`uvx` fetches the package from a git tag of this repository: `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>`. Each Kit release is a tag `v<version>` on `main`, created by the owner, and the Kit version is the package version. No release tag exists yet; until one does, run `uvx --from <local checkout> rapid-ship <command>`. Publishing to PyPI waits until the Kit settles. This spec writes `uvx rapid-ship` for short.

`rapid-ship` has four commands. `init`, `status` and `sync` are built (plan 2). `app` belongs to Agent identity and is built in plan 4. `rs-setup` marks an existing project's suppressions itself (section 8). Every command exits 0 on success, 1 when a check failed or the repository's state refused the request, and 2 when it could not run.

### `rapid-ship init`

1. **Preconditions:** the current directory is inside a git work tree with a clean status, with no `.rapid-ship/kit.lock` and no branch `rapid-ship/init`. `init` installs at the top of the work tree, even when run from a subdirectory. A project in a subdirectory of a repository is not supported. When the work tree is not clean, `init` writes nothing and exits 1. It lists the uncommitted and untracked paths, at most 20 and then how many more, and says that `rs-setup` can help commit or stash them before `init` runs again.
2. **Stack:** a repository with `pyproject.toml` gets the `python` stack. Otherwise the owner passes `--stack python` or `--stack agnostic`; without either, `init` exits 2. A repository has one stack; several stacks in one repository are deferred.
3. **Variables:** `--owner`, `--repository`, `--name` and `--package` fill the template variables. The project name defaults to the GitHub repository name, from `--repository` or the `origin` remote, then to the main checkout's directory name. Without `--owner`, CODEOWNERS names `<owner>` with its line commented out, and `rs-setup` writes the login.
4. **Plan the writes.** Each Kit file is managed (`sync` updates it later) or seeded (written once, then owned by the project). Section 4 lists both kinds.
5. **Conflicts:** if any managed file already exists, `init` writes nothing, lists the conflicts and exits 1. If a seeded file exists, even as a symlink, `init` skips it and lists it for `rs-setup` to merge.
6. **List existing checks:** before writing, `init` collects the tool settings, hooks and workflows already in the repository: Ruff, mypy, pytest, flake8, pylint, isort and Black settings, `.pre-commit-config.yaml`, Husky and lefthook files, a configured `core.hooksPath`, executable hooks in git's hooks directory, and workflows in `.github/workflows/`. It reads them without running project code or a hook, and lists an unreadable file as unreadable.
7. **Write and commit:** it creates the branch `rapid-ship/init` at `HEAD` and switches to it, from any branch, the default branch included, or from a detached `HEAD`. It writes with the safe-path helpers (never outside the repository, never through a symlink, never over an existing file), and commits exactly the created files and `.rapid-ship/kit.lock` with the message `chore: vendor the rapid-ship Kit <version>`. A repository with no commits gets the Kit as its first commit on the current branch. Every git command runs with `core.hooksPath=/dev/null`, so no git hook runs, not even one from a tracked hooks path such as husky's.
8. **Failure:** when the switch, a write, `git add` or `git commit` fails, for example without a git identity, `init` removes the files and directories it created and unstages them. It then returns to the starting branch or commit and deletes `rapid-ship/init`. The error includes git's message.
9. **Report:** it prints what it created and skipped, the existing checks, the branch and the commit, and the next step: open a PR from `rapid-ship/init`, which `rs-setup` does. For a repository that had no commits, it says that the Kit is its first commit.

`init` never edits an existing file, never runs project code and never runs a git hook, the Kit's own hooks included.

### `rapid-ship status`

Read-only. It compares the repository with the lock and the installed templates.

| Class | Meaning |
| --- | --- |
| unchanged | A managed file matches its locked hash |
| modified | A managed file differs from its locked hash. The next `sync` makes it the project's own unless it is reverted |
| missing | A managed file is absent. The next `sync` makes it the project's own unless it is reverted |
| template updated | A seeded file's template changed since it was seeded, or since the project made a managed file its own. The file itself is never compared |
| excluded | The project listed the path under `[kit] exclude` and owns it |
| outdated | A managed lock entry that the installed template no longer matches, or that the installed Kit dropped |
| not installed | A managed template of the installed Kit that the lock does not list yet, such as a file a newer Kit added |

Files not in the lock are the project's and are not reported. When `status` lists a modified or missing file, it also prints how to revert it: `rapid-ship sync --revert <path>`. `--strict` exits 1 unless every managed file that is not excluded is unchanged and current. A file that `sync` made the project's own has a seeded entry, so `--strict` no longer checks it. `--json` prints the report as data.

### `rapid-ship sync`

1. **Preconditions:** a clean work tree, unless `--in-place` is given. `--in-place` keeps uncommitted edits: it replaces only files equal to their locked content and makes the rest the project's own (step 4). `sync` compares template hashes, not version numbers; when nothing changed it says so and stops.
2. Without `--in-place`, it creates the branch `rapid-ship/kit-sync-<version>` at `HEAD`. It refuses a detached `HEAD` and an existing branch of that name.
3. It replaces each unchanged managed file with its new template, adds new managed files, including the optional skills listed under `[kit] optional`, and deletes unchanged managed files that the Kit dropped. It never creates, replaces, deletes or reports a path under `[kit] exclude`. A new managed template whose path already holds a different file that the lock does not list is a conflict: `sync` leaves the path alone, lists it and exits 1.
4. A managed file that the project edited to equal the new template stays managed; `sync` only updates the lock. Any other managed file that the project edited or deleted, or whose symlink target it changed, becomes the project's own: `sync` leaves it as it is, records it in the lock as seeded with the current template's hash, and lists it under a heading that says the project owns it now, with one line on how to give it back. An edited file that the Kit dropped keeps a seeded entry with its locked hash; a dropped file that is already gone leaves the lock.
5. `--revert <path>`, repeatable, gives a file back to the Kit: `sync` writes the current template over it and records it as managed again. It accepts a path whose current template is managed: a file the project owns after step 4, or a modified or missing managed file that this sync would otherwise make the project's own. Naming an unchanged managed file changes nothing. Any other path refuses the whole sync with exit 1 before anything is written, and the reason names the path: a path that is not a Kit file, a path under `[kit] exclude`, a seeded template, or a file the Kit dropped.
6. It never changes an existing seeded or project-authored file. It creates a seeded file that a newer Kit adds only where nothing exists at its path, and records the template either way. It lists seeded files whose template changed, including managed files the project made its own.
7. It updates the lock. Without `--in-place`, it commits, pushes the branch and opens a PR with `gh` under the owner's sign-in, and the owner merges the PR. As in `init`, no git hook runs. With `--in-place` it writes the work tree only. A failed write restores the work tree.

`sync` without `--in-place` is an owner command. Its push runs inside its own process, where the Harness guardrails cannot see it, so skills run `sync` only with `--in-place`.

### `rapid-ship app`

Part of Agent identity (section 6); built in plan 4 from its old branch. The owner has two GitHub Apps. They belong to the owner, not to one project: `app` creates each App that does not exist yet, then prints how to install both on the current repository.

| App | Permissions | Used by |
| --- | --- | --- |
| Worker App | Contents, Pull requests and Issues: read and write. Metadata: read | `devctl as worker`: pushes, opens and merges PRs, comments |
| Reviewer App | Pull requests: read and write. Contents and Metadata: read | `devctl as reviewer`: posts reviews |

Neither App has the Workflows, Administration or Checks permission, and neither is a code owner, so an App's approval never stands in for the owner's.

1. To create an App, `app` runs GitHub's manifest flow. A local HTTP server on `127.0.0.1` opens the browser at a page that posts the manifest. The App is private and has no webhook. `app` exchanges GitHub's one-time code at `POST /app-manifests/{code}/conversions`.
2. It stores each private key in the macOS Keychain, under `rapid-ship/worker-app` and `rapid-ship/reviewer-app`, by passing it to `security` on stdin. A key is never written to disk, put on a command line or printed. An existing Keychain item is left in place.
3. It prints each App's ID and slug, and the URL that installs it on the repository; `--repository OWNER/NAME` names another repository. The owner installs both Apps, and `rs-setup` records the IDs and slugs in `project.toml`.

### Who owns what

`sync` sorts every path into one of four groups, and respects the project's choices in each.

| Group | Examples | What `sync` does |
| --- | --- | --- |
| Language-agnostic Kit | devctl core, the `rs-` skills, the CI workflow, the pre-commit hook | Replaces unchanged files. A file the project edited or deleted becomes the project's own until `sync --revert` |
| Stack Kit | Python guardrail seeds and check steps | The same; where a stack file and a common file share a path, the stack's wins |
| Project extensions | `tools/devctl/devctl_project/`, the project's own skills under `.agents/skills/`, extra workflows | Never touches them. Seeded files are reported when their template changes |
| Project overrides | A Kit path listed under `[kit] exclude` | Never touches it again |

Editing or deleting a managed Kit file makes it the project's own: the next `sync` records it as seeded, stops updating it and reports only later template changes (step 4), and `sync --revert <path>` gives it back (step 5). The seeded root `AGENTS.md` tells agents so. To change behaviour and keep Kit updates, a project uses `devctl_project` and its settings. A project that wants its own version of a Kit file, or none, lists it under `[kit] exclude`. Excluding a skill's directory also excludes its `.claude/skills` link. `[kit] exclude` is the only record of an exclusion: `status`, `sync`, `devctl check` and `devctl doctor` all read it there.

### Package layout

```text
rapid_ship/
  cli.py              # init, status, sync; app from plan 4
  files.py            # atomic_replace, safe_path, create_file
  github_app.py       # plan 4: manifest flow, Keychain storage, install URLs
  kit/                # templates, lock, git, init, existing_checks, status, sync, writes, pull_request
  templates/
    kit.toml          # seeded, new-project, executable and optional lists; template variables
    common/           # every stack: devctl, tools/devctl, skills, settings, CI, hook, guides
    python/           # Python stack: pyproject.toml seed, guardrail settings, skeleton, CODEOWNERS
    agnostic/         # stack-agnostic project.toml
```

`rapid_ship` never imports devctl. The upstream lock for forked skills (section 7) lives in this repository only, beside the templates.

### Lock file

`.rapid-ship/kit.lock` is TOML that `rapid-ship` writes; nobody edits it by hand.

```toml
# Written by rapid-ship. To own or drop a Kit file, list it under [kit] exclude in project.toml.
kit_version = "0.1.0"
stack = "python"

[variables]
owner = "octo"
package = "app"
project_name = "app"
repository = "octo/app"

[[file]]
path = "tools/devctl/devctl/check/map.py"
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

### This repository's vendored Kit

*This repository's own development, not product behaviour.* This repository ran `init` on itself, so `devctl`, `tools/devctl/`, `.githooks/pre-commit`, `.github/workflows/devctl-check.yml` and `.rapid-ship/` come from its templates. `uv run rapid-ship sync --in-place` refreshes the vendored copy from the working-tree templates, so a template change and its vendored copy land in the same PR. Three project steps in `devctl_project` guard this: `vendored` runs `rapid-ship status --strict`, `distribution` builds the wheel and runs `scripts/smoke_distribution.py`, and `python-3.12` runs the tests on the oldest supported Python. In this repository nothing is excluded and no managed file may become the project's own: `status --strict` holds every managed file to its template, and `tests/test_kit_dogfood.py` fails when the lock records a Kit-managed file as seeded, which `--strict` allows.

## 4. Kit contents

| Path | Kind | Purpose |
| --- | --- | --- |
| `devctl` | managed | Shim that runs devctl from `tools/devctl/` with `uv run --frozen` |
| `tools/devctl/` | managed | devctl's source, with its own `pyproject.toml`, `uv.lock` and `.gitignore` |
| `tools/devctl/devctl_project/` | seeded | The project's verbs and extra check steps |
| `.agents/skills/rs-*/` | managed, plan 6 | Kit skills, each one real directory (section 7) |
| `.claude/skills/rs-*` | managed, plan 6 | One relative symlink per skill, to `../../.agents/skills/<name>`. Where a symlink cannot be made, `init` and `sync` exit 2 and leave nothing half-written |
| `.github/workflows/devctl-check.yml` | managed | CI |
| `.githooks/pre-commit` | managed | Runs `./devctl check --tier fast` |
| `.rapid-ship/kit.lock` | written by `rapid-ship` | The lock; not a template |
| `.rapid-ship/project.toml` | seeded | Repository, Agent identity, escalation list, Roster, Kit, map and test settings |
| `.rapid-ship/exceptions.toml` | seeded | Break-glass exceptions |
| `AGENTS.md`, `docs/AGENTS.md`, `tools/AGENTS.md` | seeded | The root guide and the first directory guides |
| `CLAUDE.md` | seeded | `@AGENTS.md`, so Claude Code reads the same instructions |
| `README.md`, `ARCHITECTURE.md` | seeded, plan 5 | Skeletons that `devctl check` verifies |
| `.claude/settings.json`, `.codex/hooks.json`, `.agents/hooks.json` | seeded, plan 5 | Harness guardrail wiring for Claude Code, Codex and agy |
| `.github/CODEOWNERS` | seeded | The owner for every path in Walk; below it, commented out, the Protected set |
| `docs/features/README.md` | seeded | The feature-file format |
| `docs/patterns/README.md` | seeded | The Pattern-file format |
| `.gitignore`, `pyproject.toml`, `src/AGENTS.md`, `src/<package>/__init__.py`, `tests/AGENTS.md`, `tests/test_import.py` | seeded, Python, only when there is no `pyproject.toml` yet | Guardrail settings, dev dependencies and a skeleton that passes `check` |

devctl runs through uv for every stack. Its own lock keeps its dependencies apart from the project's. Kit-owned code is excluded from the project's lint, type and test settings; this repository checks it upstream.

### Settings files

None of these holds a secret. All are in the Protected set. devctl rejects an unknown key, so a typo cannot silently keep a default.

`.rapid-ship/project.toml` after plan 4:

```toml
stack = "python"

[github]
repository = "owner/name"
# Agent identity: each App's ID and slug, as rapid-ship app prints them. 0 and "" mean off.
worker_app_id = 0
worker_app_slug = ""
reviewer_app_id = 0
reviewer_app_slug = ""

[escalation]
# The kinds of pull request the Lead brings to the owner instead of merging it itself.
# true is Walk. false leaves the Protected set and the kinds below: Flight, or anything between.
every_pr = true
kinds = [
  "a pull request that removes a behavioural test",
]
revision_rounds = 3    # a PR that reached this many Revisions also goes to the owner

# Optional. Only an owner who uses more than one Provider needs a Roster.
# [roster.worker]
# harness = "codex"        # claude, codex or agy
# model = "<exact model ID>"
#
# [roster.reviewer]
# harness = "claude"
# model = "<exact model ID>"

[kit]
optional = []          # opt-in Kit skills, such as "rs-contribute"
exclude = []           # Kit files or directories the project owns instead

[map]
source_roots = ["src/<package>"]
unguided = []          # maintained directories that need no guide
exclude = []           # directories whose AGENTS.md files are template content

[tests]
unit = ["tests/unit/**"]   # every other test counts as behavioural
```

- **`[github]`:** `repository` is `owner/name`. Agent identity is on when both Apps are recorded, each with its ID and slug. A partial record, or Apps recorded without `repository`, is a settings error. [Spec 3](2026-10-16-metrics-and-gardening-design.md) matches an agent PR's author against the Worker App's slug, so it needs no App key.
- **`[escalation]` (Proposal for the key names):** the escalation list. The Protected set is always on it, whether or not it is written here. `every_pr = true` is Walk. With `every_pr = false`, the list is the Protected set plus `kinds`: that is Flight, and each kind the owner adds moves it toward Walk. `kinds` is plain text for the Lead, because CODEOWNERS can match paths only; GitHub enforces only the Protected set. The seeded kind replaces the old test-removal switch. `revision_rounds = 3` replaces `review_round_limit`; [Spec 2](2026-10-16-delivery-skills-design.md) settles it with `rs-lead`. `rs-lead` changes this table, and proposes the matching CODEOWNERS change, as a Protected PR.
- **`[roster]`:** one table per role, `worker` and `reviewer`, each naming a Harness (`claude`, `codex` or `agy`; a Proposal, section 11) and an exact model ID, kept exactly as written. It is optional; without it the Lead's Harness chooses its subagents' models. Spec 2 may add roles. `devctl doctor` checks that each Harness named here is installed and signed in (section 6).
- **`[kit]`, `[map]`, `[tests]`:** built in plans 2 and 3. `[map] exclude` lets this repository keep the template guides under `rapid_ship/templates/` out of the map rules. Spec 3's plan lets `[kit] optional` name an optional Kit file, such as the metrics Action, as well as a skill.
- **Added by Spec 2's plan:** `[tracker]` and `[design]`, which [Spec 2](2026-10-16-delivery-skills-design.md) defines.
- **Removed by plan 4:** `[agents]`, which the Roster replaces; `[linear]`, because devctl never talks to the tracker; `[dispatch]` (`max_workers`, `attempt_limit`, `worktree_root`), because nothing dispatches; and `[release]`, which nothing reads, because a project defines its own deploy metrics (Spec 3).

Plan 4 stops seeding `.rapid-ship/gate.toml`, and devctl stops reading it. The Mode now lives in `[escalation]`, Flight has no lease, and the test-removal switch became a seeded escalation kind. The file's threshold tables described automatic promotion and demotion, which no longer exist. Spec 3's plan seeds `.rapid-ship/metrics.toml`, which holds the Suggested thresholds ([Spec 3](2026-10-16-metrics-and-gardening-design.md), a proposal there). `sync` never deletes a seeded file, so an existing project keeps its old `gate.toml` until the owner deletes it; this repository deletes its own in plan 4.

`.rapid-ship/exceptions.toml` holds the break-glass entries. The seed holds comments only:

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
2. Commands: `./devctl check`, `./devctl doctor` and `./devctl --help` for the project's verbs.
3. A "Find the change" table that points to directory guides, `docs/features/` and `docs/patterns/`, and from plan 5 to `README.md` and `ARCHITECTURE.md`.
4. **Rules.** Each rule ends with `enforced by: <reference>` or `advisory` (section 5).
5. Pointers to `GLOSSARY.md`, `docs/adr/`, and the `rs-writing` and `rs-ponytail` skills (a Proposal, section 7).

AGENTS.md files are the single instruction source. The seeded `CLAUDE.md` is a real file containing `@AGENTS.md`.

### README.md and ARCHITECTURE.md

Plan 5 seeds both. For a new repository `rs-setup` fills them in with the owner; in an existing one `init` skips them where they exist, and `rs-setup` merges the skeleton's sections into them (section 8).

- **README.md:** what the project does and for whom, how to run it, how to check a change (`./devctl check`), and where the agent instructions start (`AGENTS.md`).
- **ARCHITECTURE.md:** the system's purpose and context, a table of its main parts (part, where, what it does), how data moves between them, links to the ADRs in `docs/adr/`, and how to work on the code. `rs-design` (Spec 2) maintains it.

`devctl check` verifies that both exist and that their links resolve (map rule 8, section 5).

### Patterns

A Pattern is the one supported way to do a recurring task. The Kit ships the mechanism, not code: the file format in the seeded `docs/patterns/README.md`, and map rule 5, which verifies it. Each Pattern has one file in `docs/patterns/`, whose YAML front matter names three things:

```yaml
---
task: Read configuration
reference: src/app/settings.py
enforced_by:
  - banned:os.environ
  - test:tests/test_settings.py::test_settings_are_the_only_reader
---
```

- `task` is the recurring task in a few words. Plan 5 adds it (Proposal); `reference` and `enforced_by` are built.
- `reference` is the path of the reference implementation. It must exist.
- `enforced_by` lists at least one reference to the check that enforces the Pattern (section 5). Each must resolve.

The text after the front matter states the rule, when it applies and the bypass it bans. Agents may add a Pattern; changing an existing one needs the owner, so CODEOWNERS lists each existing Pattern file. That line is itself a Protected change, which the owner makes or approves. `rs-setup` sets the first Patterns in a new repository; `rs-health` proposes them in an existing one.

### Skills layout

Each skill, from the Kit or the project, is one real directory, `.agents/skills/<name>/`, which Codex and agy read. Claude Code is the only major Harness that does not read `.agents/skills`, so it gets one relative directory symlink per skill: `.claude/skills/<name> -> ../../.agents/skills/<name>`. The Kit lock records each link like any other managed file. `SKILL.md` itself is never a symlink, because Codex rejects one by design. opencode and Gemini CLI read both directories and warn about the duplicates; that cost is accepted.

`rs-work` and `rs-review` ship as skills only, with no per-Harness subagent definition files. The Lead tells its Harness's generic subagent to follow the skill, or follows it itself.

### Harness guardrails

The Kit brings the rungs into the loop of Claude Code, Codex and agy. One devctl command, `devctl hook` (section 6, Proposal), holds every rule, and each Harness's seeded settings file only wires that command to the Harness's hook events. A Kit update therefore changes the rules for every project, while each project keeps its own settings files.

| Rule | When | Decision |
| --- | --- | --- |
| G1. A git command with `--no-verify`, or `git commit -n` | Before a shell command | Deny |
| G2. `git push` with `--force`, `-f`, `--force-with-lease`, `--force-if-includes`, or a refspec that starts with `+` | Before a shell command | Deny |
| G3. `gh pr merge` with `--admin` | Before a shell command | Deny |
| G4. A file-edit tool writing `.rapid-ship/kit.lock` | Before a file edit | Deny: `rapid-ship` writes the lock |
| G5. A file-edit tool writing a path in the Protected set | Before a file edit | Ask the owner |
| G6. The agent or a subagent stops | On the Harness's Stop and subagent-stop events | Run `./devctl check --tier fast`; on failure, send the agent back with the failing steps |
| G7. With Agent identity on: `git push` in any form | Before a shell command | Deny, and name `./devctl as worker push` |
| G8. With Agent identity on: a `gh` write as the owner, which is any `gh pr` subcommand other than `view`, `list`, `status`, `diff`, `checks` or `checkout`; any `gh issue` subcommand other than `view`, `list` or `status`; or `gh api` with a method other than `GET` or with `-f`, `-F`, `--field`, `--raw-field` or `--input` | Before a shell command | Deny, and name `./devctl as <role> gh` |

- **Commands:** the hook splits the command line with shell rules and checks each simple command joined by `;`, `&&`, `||` or `|`.
- **The Protected set** for G5 is read from the Protected-set lines of `.github/CODEOWNERS`, commented or not, never the `*` line. These are the lines the `diff` step reads, and both use one matcher.
- **G6:** the check runs in the working directory that the hook event names, else at the repository root. When that tree has no uncommitted change and no commit since its merge base with the default branch, the hook lets the agent stop without running the check. To avoid a loop, the hook sends the agent back once per stop: when the Harness reports that the agent is already continuing because of this hook (`stop_hook_active` in Claude Code), it lets the agent stop and tells the owner that the check still fails (Proposal). The wiring gives the Stop hook a timeout long enough for the fast tier.
- **Decisions:** the hook only denies or asks. It never allows or approves anything; with no rule matched it gives no decision, and the Harness's own permission flow continues. Its exit codes follow each Harness's hook protocol, not devctl's convention, because Claude Code reads exit 2 as "block". An internal error exits 1 with a message. Claude Code and Codex treat that as no decision; the live trial confirms agy's handling.
- **Limits:** the hook reads the command line as the Harness passes it. It does not follow scripts, aliases, `sh -c` strings or shell redirections that write files. Other `gh` commands that write, such as `gh release` or `gh workflow run`, are outside G8, and `devctl as` refuses them. These rules stop habits and mistakes, not a determined agent; the ruleset and CODEOWNERS on GitHub are the enforcement.

| Harness | Seeded file | Wiring |
| --- | --- | --- |
| Claude Code | `.claude/settings.json` | `PreToolUse` for `Bash`, `Edit`, `Write`, `MultiEdit` and `NotebookEdit`, then `Stop` and `SubagentStop`, each running `"$CLAUDE_PROJECT_DIR"/devctl hook claude <event>`. Settings hooks also fire inside subagents |
| Codex | `.codex/hooks.json` | `PreToolUse` for `Bash` and `apply_patch`, then `Stop` and `SubagentStop`, running `devctl hook codex <event>`. Codex runs project hooks only in a trusted project, after the owner reviews them in `/hooks`; a changed hook needs a new review. Whether Codex hooks can ask, and fire inside subagents, is confirmed in the live trial (section 10). If they cannot ask, the Codex wiring omits G5 and leaves those edits to CODEOWNERS |
| agy | `.agents/hooks.json` | `PreToolUse` and `Stop`, running `devctl hook agy <event>`. Whether agy's hooks fire inside subagents is confirmed in the live trial |

The files are seeded, not managed, because many repositories already have a `.claude/settings.json`; `init` skips an existing one and `rs-setup` merges the Kit's entries into it. `devctl doctor` reports a wiring file that lacks the Kit's hooks (section 6). Any other Harness gets AGENTS.md, `.agents/skills`, the pre-commit hook and CI, and rungs 2 and 4 hold for it through git and GitHub. Supporting another Harness takes one more wiring file and one more `devctl hook` protocol.

Sandboxing is not part of the Kit. A Harness's subagents inherit the sandbox of the owner's own Session, so a sandbox is the owner's choice for their whole Session. `rs-setup` offers it (section 8).

### The Protected set and CODEOWNERS

The Protected set is the kinds of change that need the owner's approval in every Mode. CODEOWNERS assigns them to the owner, and GitHub reads it from the PR's base branch, so a PR cannot exempt itself. The seeded CODEOWNERS has one active line in Walk, `* @<owner>`. Below it, commented out for Flight, is the Protected set:

- `/.github/`, `/.githooks/`, `/devctl`, `/tools/devctl/`;
- the skills and the Harness guardrail wiring: `/.agents/` (widened from `/.agents/skills/` in plan 5, so it covers `.agents/hooks.json`), `/.claude/`, and `/.codex/` (added in plan 5);
- every `AGENTS.md` and `CLAUDE.md` (`/**/AGENTS.md`, `/**/CLAUDE.md`);
- `/.rapid-ship/`, which holds the escalation list, the Roster and the exceptions;
- the settings files of the check tools, because a settings file can switch its check off: `/.gitleaks.toml`, `/.gitleaksignore`, `/zizmor.yml`, `/zizmor.yaml`, and for the Python stack `/pyproject.toml`, `/**/ruff.toml`, `/**/.ruff.toml`, `/mypy.ini`, `/.mypy.ini`, `/pytest.ini`, `/.pytest.ini`, `/pytest.toml`, `/.pytest.toml`, `/setup.cfg`, `/tox.ini` and `/.importlinter`;
- one line for each existing Pattern file, and any paths the project adds for access, the data model or the public API.

Plan 5 replaces the seed's placeholder comment about Harness settings with the lines above, and updates doctor's list of Protected paths to match. Flight uncomments the Protected set and removes the `*` line; `rs-lead` proposes that change as a Protected PR. With Agent identity, the `*` line enforces Walk because an App cannot bypass the ruleset. Without it, an agent's PR comes from the owner's account and only the owner's bypass can merge it.

### CI workflow

`.github/workflows/devctl-check.yml` (built in plan 3):

- **Triggers:** `pull_request`, including body edits; `push` to `main` or `master`; a nightly `schedule`; and `workflow_dispatch`. A workflow cannot name the default branch, and a push run skipped by a condition would report a passing `devctl check` on the same commit, so the branches are listed. `rs-setup` records a Setup gap when the default branch has another name.
- **Permissions:** `contents: read` only. The job uses no secrets, so fork PRs behave the same.
- **Concurrency:** one group per ref; PR runs cancel superseded runs.
- **Steps:** checkout and `astral-sh/setup-uv`, both pinned by commit SHA, with `persist-credentials: false` and full history for the diff policy. Install gitleaks 8.30.1, verified by its SHA-256. Run `./devctl check --tier full`.
- **Job name:** `devctl check`, which the ruleset requires.

The nightly run checks the default branch. Spec 3 counts a red default-branch run after a merge as a metric.

### Python guardrail settings

New projects get these settings in the seeded `pyproject.toml`. For existing projects, `rs-setup` merges them into the existing configuration, keeping the project's rule where the two conflict, and `devctl doctor` reports what is still missing.

- **Ruff:** E, W, F, I, B, UP, SIM, C4, RUF, PGH, ERA, T20, S, TID, PT, PTH, DTZ, C90, TD, BLE and ANN401. C90's `max-complexity` is 10. Relative imports are banned. A `banned-api` table starts empty, and Patterns fill it. PGH003, PGH004, RUF100 and ERA001 control escape hatches. `rs-setup` adds ASYNC and FAST where it finds asyncio or FastAPI; the seed does not.
- **mypy:** strict over source and tests, with `warn_unreachable` and the error codes `ignore-without-code`, `redundant-expr` and `truthy-bool`.
- **import-linter:** one `layers` contract, whose layers stay optional until the architecture names them, and one `forbidden` contract that keeps pytest out of production code.
- **pytest:** `--strict-markers --strict-config`, `xfail_strict = true`, `filterwarnings = ["error"]`.
- **Dev dependencies:** ruff, mypy, pytest and import-linter in the project's lock.

There is no ratchet. Unsafe patterns are prohibited. A legitimate exception is a listed break-glass entry (section 5).

## 5. `devctl check`

`check` is the single entry point for hooks and CI. It covers everything a machine can decide, and it never runs a model. Built in plan 3; plan 5 adds map rule 8, the Pattern `task` key, the `SKILL.md` rule and the diff cap.

### Steps

| Step | Tier | Fails when |
| --- | --- | --- |
| format | fast | Formatting differs (Python: `ruff format --check`) |
| lint | fast | The linter reports a finding (Python: `ruff check`) |
| map | fast | A map rule below fails |
| exceptions | fast | A suppression lacks a listed exception, or an exception matches nothing |
| file-size | fast | A source file exceeds 500 lines without an exception |
| kit | fast | The lock is unreadable, or a managed file that is not excluded is missing. The message names both choices: `rapid-ship sync --revert <path>` restores the file, and `rapid-ship sync` keeps the deletion as the project's own, after which this step passes |
| types | full | The type checker fails (Python: mypy) |
| contracts | full | An import contract is broken (Python: `lint-imports`) |
| tests | full | The test suite fails (Python: pytest) |
| audit | full | A locked dependency has a known vulnerability (Python: pip-audit 2.10.1) |
| secrets | full | gitleaks finds a secret in the change's commits, or in the whole history without a base. gitleaks must be on `PATH` |
| workflows | full | zizmor 1.30.1 reports a finding in a GitHub Actions workflow |
| diff | full | The diff policy below fails |
| evidence | full, PRs only | The PR body lacks its Evidence section |

The Python stack supplies the Python column. The agnostic stack has no `format`, `lint`, `types`, `contracts`, `tests` or `audit` step. pip-audit and zizmor run through `uv tool run --from <pin>` and are not dependencies. A project adds steps in `devctl_project`.

### Output and exit codes

- `./devctl check [--tier fast|full] [--json] [--base REV] [--pr-body PATH]`. The default tier is `full`.
- One line per step: passed, failed, blocked, or not applicable, with details below a step that did not pass. `--json` prints the same as a list of `{"name", "status", "details"}` objects.
- Exit 0: every applicable step passed. Exit 1: at least one step failed. Exit 2: at least one step could not run, for example a missing tool or an unreadable setting. A blocked step never counts as passed, and 2 outranks 1.
- The `diff` and `evidence` steps need a change. In CI the base is the PR's base and the body comes from the PR event. Locally, `--base` names the base, or devctl uses the merge base with `origin`'s default branch, and `--pr-body` names a file with the body. Without a base `diff` is not applicable; outside a PR, `evidence` is not applicable.

### Map rules

1. Every Markdown link in every AGENTS.md resolves to a tracked or non-ignored file.
2. Every maintained directory has an AGENTS.md. Maintained directories are the top-level tracked directories and the immediate children of each source root, except hidden directories and those listed in `[map] unguided`. AGENTS.md files under a `[map] exclude` directory are template content: the map rules ignore them.
3. Every AGENTS.md is reachable by links from the root AGENTS.md.
4. Every file in `docs/features/` other than its README has front matter with `purpose`, `entry_points`, `data`, `observe` and `reproduce`. Each path it names exists. `entry_points` is not empty. Each `reproduce` command is `./devctl` followed by a registered verb.
5. Every file in `docs/patterns/` other than its README has front matter with `reference`, a path that exists, and a non-empty `enforced_by` list whose references resolve. Plan 5 adds a non-empty `task` (Proposal).
6. Every bullet under a `Rules` heading in any AGENTS.md ends with `enforced by: <reference>` or `advisory`. Each reference resolves.
7. Every skill directory under `.agents/skills/`, from the Kit or the project, has a `SKILL.md` whose front matter `name` equals the directory name and whose `description` is not empty, and a relative symlink at `.claude/skills/<name>` that points to it. No other entry exists under `.claude/skills/`. A skill directory that is itself a symlink must be relative and stay inside the repository. Plan 5 adds: `SKILL.md` is a regular file, not a symlink.
8. Plan 5: `README.md` and `ARCHITECTURE.md` exist at the repository root, every local link in them resolves, and the root AGENTS.md links to both (Proposal for the last part).

Spec 3 adds a rule for the Corrections ledger after these.

### References

A reference names the check that enforces a Rule or Pattern. The stack defines the kinds, and `check` resolves each one.

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

A suppression is a line that switches a check off. For Python these are `# noqa`, `# type: ignore`, the `# mypy:` file comments, `# pragma: no cover`, and pytest's skip, skipif, xfail and importorskip. gitleaks's inline allow comment and `# zizmor: ignore[...]` are suppressions in every stack.

1. Each suppression carries `rs-exception: EX-<n>` on the same line. One marker matches one rule, so a line that switches off two rules needs two markers and two entries.
2. `EX-<n>` exists in `.rapid-ship/exceptions.toml` with a matching path and rule, a reason and a removal condition.
3. Each ID is used exactly once. An entry that matches no suppression fails as stale.
4. File-size exceptions are path entries with `rule = "file-size"` and no inline marker. They fail as stale once the file is under the cap.

Kit-managed files that are not excluded are not scanned. An added suppression needs an edit to `exceptions.toml`, which is Protected. Nothing is counted, so removing one suppression cannot pay for adding another. For an existing project, `rs-setup` marks each existing suppression at Setup (section 8).

### Diff policy

The diff policy compares the change with its base. It is adapted from no_human's test-tamper guard (MIT), using each test's identity instead of its net counts.

1. **Removed tests:** a test present at the base and absent everywhere at the head fails, unless the PR body declares it under `Removed tests:` with a reason. A test's identity is its name within its file (`test_x` or `TestA::test_x`), so a test moved to another file is not a removal. The step classes each removed test as unit or behavioural: a test is a unit test only when its path matches `[tests] unit`; every other test, such as an integration or end-to-end test, is behavioural. Whether a declared removal goes to the owner is the escalation list's business: the seeded list names behavioural-test removals.
2. **Tautologies:** an assertion that the change turns into a tautology, such as `assert True` or `x == x`, fails.
3. **Faking fixtures:** a new `autouse` fixture in a `conftest.py` fails without an exception.
4. **Protected paths:** the step lists each Protected path the change touches. It does not fail; CODEOWNERS enforces the approval.
5. **Diff cap (plan 5, Proposal):** a change that adds and removes more than 500 lines in total fails, unless the PR's Evidence section has a line starting `Over the diff cap:` with a reason. The count leaves out binary files, Kit-managed files, `.rapid-ship/kit.lock` and the stack's lock files (`uv.lock` for Python), so a Kit sync stays under the cap. A declared overage passes with a note. A Task fits within this cap, so `rs-work` declares an overage only after the owner accepted it before the work ([Spec 2](2026-10-16-delivery-skills-design.md)); the declaration records that decision, and no escalation kind brings the PR back to the owner for it.

Skip markers are suppressions, so the exceptions step handles them.

### Evidence

On a PR, the body must contain an `## Evidence` section with at least one command and its result, and a line starting `Not covered:`. When the change removes tests, the section also lists them under `Removed tests:`. A Worker writes the section by following `rs-work` (Spec 2) and the `rs-pr` engineering skill (a Proposal, section 7). CI reruns the check when the PR body is edited.

```markdown
## Evidence

- `./devctl check`: exit 0; every step passed except evidence, not applicable

Removed tests:
- `tests/test_flags.py::test_legacy_flag`: the flag was deleted in this PR

Not covered: behaviour on Windows.
```

### Where `check` runs

1. The pre-commit hook runs the fast tier. `git commit --no-verify` skips it, which the Kit's Harness guardrails deny to agents.
2. Each supported Harness's Stop hook runs the fast tier when an agent says it is done (G6, plan 5).
3. `rs-work` has the Worker run it before opening a PR. That run is advisory.
4. CI runs the full tier on every PR. The ruleset requires it; this is the enforcement.
5. The nightly CI run checks the default branch.

## 6. Other devctl commands

devctl keeps only commands used repeatedly. The owner asked to keep this surface small, so a new need becomes an option of an existing command where one fits.

| Command | Built in | What it does |
| --- | --- | --- |
| `check` | plan 3 | Section 5 |
| `doctor [--skills]` | plan 4 | Reports what this machine and repository lack |
| `as {worker,reviewer} ...` | plan 4 | Agent identity's thin command for `gh` and `git push` (Proposal for the name) |
| `hook {claude,codex,agy} {pre-tool,stop}` | plan 5 | The Harness guardrails (Proposal) |
| `metrics` | Spec 3 | The metrics report |

A project adds its own verbs in `devctl_project`. devctl never starts an agent to do work, never tracks or resumes one, and never talks to the issue tracker. Only doctor's probes start a short headless Session, to check a Harness's sign-in and the skills it loads.

### `devctl doctor`

doctor changes nothing in the repository. It reports each item as ok, missing or unknown, then a summary line. It exits 0 when everything is ok, 1 when something is missing and 2 when an item could not be checked. Plan 4 brings it over from the old branch, reshaped as below. It reads GitHub with the owner's `gh` sign-in, always as `GET`.

| Area | Item | ok when |
| --- | --- | --- |
| toolchain | git | git 2.31 or later |
| toolchain | uv, gh | On `PATH` |
| toolchain | gh sign-in | `gh auth status` succeeds |
| toolchain | gitleaks | Version 8.30.1, which `devctl check` pins |
| toolchain | Each Harness the Roster names | Installed and signed in (below) |
| guardrails | `core.hooksPath` | Set to `.githooks` |
| guardrails | CI | The workflow has a job named `devctl check` |
| guardrails | Python floor | The settings of section 4 are present (Python stack) |
| guardrails | devctl exclusions | `tools/devctl` is excluded from the project's Ruff, mypy, pytest and uv workspace |
| guardrails | Harness wiring (plan 5) | Each of the three wiring files runs `devctl hook` for its events |
| kit | Kit files | The `rapid-ship status` summary has nothing missing |
| github | ruleset | An active ruleset on the default branch matches section 8 for the current Mode and Agent identity |
| github | CODEOWNERS | Matches the Mode: the `*` line when `every_pr = true`, the Protected set otherwise |
| github | delete branch on merge | On |
| github | fork PR workflow approval | A public repository requires approval for workflows from all outside contributors |
| agent identity | Worker App, Reviewer App installation | Only with Agent identity on: installed on this repository with exactly the permissions of section 3 |
| agent identity | Worker App, Reviewer App key | Only with Agent identity on: the Keychain item exists and mints a token. Minting changes nothing in the repository |

- **Sign-ins:** Claude Code and Codex CLI report their sign-in through `claude auth status --json` and `codex login status`. agy has no status command, so doctor starts a new headless Session on the cheapest model, sends `hi`, and counts a non-empty reply as signed in; agy's exit code alone proves nothing, and a service error is unknown, not missing. Any sign-in method is ok: a subscription, an API key or a gateway is the owner's choice of Provider. doctor never reads a token file.
- **GitHub Free private repositories** have no rulesets. GitHub refuses the read with a plan-limit message, and doctor reports the ruleset as missing with that reason.
- **Removed:** the issue-tracking item, and every App item while Agent identity is off.

`devctl doctor --skills` also checks what each Harness's Session would see. For each Harness the Roster names, or without a Roster for each of `claude`, `codex` and `agy` that is on `PATH` (Proposal), it adds a temporary detached worktree at `HEAD` in a temporary directory, starts one new headless Session there on the cheapest model, and asks which skills it can load. A Kit or project skill the Session does not list is missing. A user-invoked skill (`disable-model-invocation: true`) is reported as not checked, because a Harness may leave it out of its list. Skills the Session sees from outside the repository, such as the owner's own skills or plugins, are listed for the owner to judge. The worktree is removed afterwards, whatever the Session did. Each probe uses a little quota. `rs-setup` runs it, and the owner reruns it after adding a skill or upgrading a Harness.

The agy probes start agy as a child of whatever runs doctor. When an agent runs doctor from another Harness's Session, that is the use Google's consumer terms do not support; `rs-setup` warns about it (section 8).

### Agent identity and `devctl as`

Agent identity is optional ([ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md)). It is on when `[github]` records both Apps (section 4). Agents then make their GitHub writes through one thin command, which runs `gh` or `git push` with an App's short-lived token. It runs only when an agent calls it, never as a step that rapid-ship drives. Proposal for its interface:

```text
./devctl as worker push
./devctl as worker gh <gh arguments>
./devctl as reviewer gh <gh arguments>
```

- **Off:** while Agent identity is off, `devctl as` exits 2 and says how to turn it on.
- **`push`:** pushes the current branch to the branch of the same name on GitHub, as the Worker App. It takes no other arguments and never forces, so a non-fast-forward push fails; the agent merges the base branch rather than rewriting history. It refuses a detached `HEAD` and the default branch, and refuses `devctl as reviewer push`.
- **`gh`:** runs `gh` with the given arguments as the role's App. The first argument must be `pr`, `issue` or `api`; any other is refused, because `gh auth` can print the token and `gh alias` or `gh extension` can run other code with it. `gh pr merge --admin` is refused.
- **Exit codes:** 1 when devctl refuses, 2 when it cannot mint a token or start the tool, otherwise the exit code of `gh` or `git`.
- **Workflows:** neither App has the Workflows permission, so GitHub refuses an App's push that changes `.github/workflows/`. The owner pushes such a change, which is in the Protected set anyway.

Each run mints its own token and holds it only in memory:

1. Read the App's private key from the Keychain with `security find-generic-password -s rapid-ship/<role>-app -w`.
2. Sign a JWT and request an installation token restricted to this one repository and the App's named permissions. REST calls go through a small `http.client` wrapper that never follows a redirect.
3. Give `gh` the token only through `GH_TOKEN`, with `GH_REPO` set to the repository, in that one child's environment. Give `git push` the token only through a `GIT_ASKPASS` helper that reads it from that one git command's environment, with every configured credential helper and repository hook switched off for that command.

No key or token is written to disk, put on a command line or printed. An item that `security` wrote trusts `security` itself, so reads show no dialog, and any process the owner runs can read both keys. A Worker can therefore reach the Reviewer App; `rs-work` tells Workers never to act as it, and no technical barrier is planned until misuse is observed. With Agent identity on, the Harness guardrails deny `git push` and `gh` writes made as the owner (G7, G8).

### `devctl hook`

`devctl hook <harness> <event>` is the one implementation of the Harness guardrails (section 4, Proposal). `<harness>` is `claude`, `codex` or `agy`; `<event>` is `pre-tool` or `stop`. It reads the Harness's event JSON on stdin and answers in that Harness's hook protocol. `pre-tool` applies G1 to G5, and G7 and G8 when Agent identity is on. `stop` applies G6. It reads `.github/CODEOWNERS` and `.rapid-ship/project.toml` from the repository, and changes nothing.

## 7. Skills in the Kit

The Kit ships eight skills from `rs-setup` to `rs-garden`, the engineering skills, and one optional skill, `rs-contribute`. Every Kit skill's name starts with `rs-`, which avoids collisions with Harness built-in commands and with an installed upstream plugin.

| Skill | Spec | Built in | What it does |
| --- | --- | --- | --- |
| `rs-setup` | 1 | plan 6 | Sets up a new repository or adopts an existing one (section 8) |
| `rs-health` | 1 | plan 6 | Audits a repository and returns a standards milestone (section 9) |
| `rs-design` | 2 | Spec 2's plan | Interviews the owner; writes feature designs, ADRs and ARCHITECTURE.md |
| `rs-breakdown` | 2 | Spec 2's plan | Turns a design into milestones, epics, stories and tasks in the tracker |
| `rs-lead` | 2 | Spec 2's plan | Builds the Lead brief, triages review findings and helps the owner fly |
| `rs-work` | 2 | Spec 2's plan | How a Worker meets the bar on one task |
| `rs-review` | 2 | Spec 2's plan | How a Reviewer judges one change |
| `rs-garden` | 3 | Spec 3's plan | Records Corrections and finds drift |
| `rs-contribute` | 1 | plan 6 | Optional: sends a Kit fix back to rapid-ship |

`rs-work` and `rs-review` must work for an agent: the Lead starts a subagent with them or follows them itself. People rarely run them, but must be able to read them. There is no metrics skill: `rs-setup` records the Suggested thresholds, and project-defined metrics are documented in Spec 3.

### Engineering skills

The engineering skills carry rung 3 for every task. Spec 1 owns them, and plan 6 builds them. TDD and debugging are decided; keeping the other five is a Proposal.

| Skill | Source |
| --- | --- |
| `rs-tdd` | Upstream `tdd`, near verbatim |
| `rs-diagnosing-bugs` | Upstream `diagnosing-bugs`, near verbatim |
| `rs-codebase-design` | Upstream `codebase-design`, verbatim |
| `rs-pr` | Upstream `pr`; its Evidence adds the commands run and `Not covered:`. It carries the HumanLayer credit |
| `rs-writing-for-agents` | Upstream `writing-for-agents`, verbatim |
| `rs-writing` | This repository's `writing.md` |
| `rs-ponytail` | This repository's `ponytail.md` |

The forked skills come from mattpocock/skills (MIT), pinned at `49dd158`, and stay as close to upstream as rapid-ship allows. Each forked skill directory carries the upstream licence notice. This repository's upstream lock records, for each upstream file, its path, upstream commit, upstream blob SHA and status, `verbatim` or `patched`. A test requires `verbatim` files to match their blob SHA, and `patched` files to differ only inside marked rapid-ship sections. The seeded root AGENTS.md already names `rs-writing` and `rs-ponytail`. When the Kit skills land, `rapid-ship-engineering` is deleted and this repository's root AGENTS.md points to them.

[Spec 2](2026-10-16-delivery-skills-design.md) says which upstream skills `rs-design` and `rs-breakdown` draw on.

### `rs-contribute`

`rs-contribute` sends a Kit fix from a project back to rapid-ship. It is user-invoked and installed only when the owner opts in at Setup, through `[kit] optional`.

1. Describe the problem with the evidence that shows it: the command, the output and the Kit file involved.
2. Map the project file to its template through the lock.
3. Search rapid-ship's open issues and PRs for a duplicate.
4. In a cached fork of rapid-ship, fix the template and refresh the vendored copy with `rapid-ship sync --in-place`.
5. Run rapid-ship's own `./devctl check`.
6. Push the fix to the fork and open a PR to rapid-ship. Leave out project code, secrets and private paths. If the fix is unclear, open an issue instead. With Agent identity on, the guardrails may deny the agent's `git push` and `gh` writes (G7, G8), and a `devctl as` token reaches only the project's repository. The owner then pushes and opens the PR or issue in a terminal, as in `rs-setup` step 14.

A project may apply the same change to its vendored copy at once. When the fix ships, the next `rapid-ship sync` finds the file equal to the new template and keeps it managed. If a sync ran in between, the file became the project's own (section 3), and `rapid-ship sync --revert <path>` gives it back.

## 8. `rs-setup`

`rs-setup` is user-invoked. The owner runs it in their Harness on the `rapid-ship/init` branch, after `uvx rapid-ship init` committed the Kit there. Before each write outside the repository, such as a GitHub setting, an App, the tracker or the owner's own Harness settings, it states the write and waits for the owner's yes. Before retrying a write whose result is uncertain, it re-reads the outside state. It records each gap it cannot resolve in the Setup PR's body.

### Steps

1. **New or existing.** A repository with source beyond the Kit is existing.
2. **Documents.**
   - New: ask the owner what the project does, for whom and how it runs. Fill in README.md, the root AGENTS.md's first paragraph, and ARCHITECTURE.md's purpose and context. Its parts wait for `rs-design`.
   - Existing: `init` skipped the README.md, ARCHITECTURE.md, AGENTS.md and CLAUDE.md that already exist. Merge the skeleton's sections into them from what the code shows, keeping the project's own text, and add a guide for each maintained directory that the `map` step reports. What the code does not show becomes a gap for `rs-health`.
3. **Patterns** (new repositories). Agree the first Patterns with the owner, such as how configuration is read. For each, write the Pattern file, a minimal reference implementation and its enforcing check. When the reference needs real product code, record the Pattern as a task for the first milestone instead. In an existing repository `rs-health` proposes Patterns.
4. **Checks.**
   1. Confirm gitleaks 8.30.1 with `gitleaks version`; if it is missing, ask the owner to install it.
   2. New project: run `uv sync` and `./devctl check`. The seeded skeleton passes.
   3. Existing project: devctl's checks can overlap or conflict with the project's own linters, hooks and CI, and the owner decides how to combine them. Exclude `tools/devctl` from the project's lint, type, test and uv workspace settings. Show each overlap or conflict with the settings, hooks and workflows that `init` listed, such as hooks in `.git/hooks` that `core.hooksPath` would stop running, and offer to fold them into `devctl_project`. Merge the stack's settings into the existing configuration; where an existing rule conflicts, keep the project's rule, and doctor reports the gap. Add Ruff's ASYNC and FAST families where asyncio or FastAPI is used. Warn about duplicate checks, which are harmless, and about checks that race, such as two hooks writing the same files, which are harmful. Never block on either.
   4. Existing suppressions: for each one the `exceptions` step reports, add its `rs-exception` marker and an entry with the reason "Existed at Setup on <date>" and the removal condition "Remove when this code next changes". Repeat `./devctl check --tier fast` until the step passes. The owner reviews the entries in the Setup PR. Marking them in this step, rather than with a separate command, is a Proposal.
   5. Run `git config core.hooksPath .githooks`. In an existing project, run it only after the owner has decided how to combine the existing hooks.
   6. Run `./devctl check` until it passes.
5. **Harness guardrails.** Show the owner the rules of section 4. Where `init` skipped an existing `.claude/settings.json`, `.codex/hooks.json` or `.agents/hooks.json`, merge the Kit's entries into it. For Codex, the owner trusts the project and reviews its hooks in `/hooks`.
6. **Sandbox (an offer, not a default).** Explain that a sandbox confines the owner's own Session and every subagent it starts, because subagents inherit it. It is defense in depth, and it needs network access for git, gh, uv, the package index and the tracker. If the owner accepts, write the setting into the owner's own uncommitted settings for their Harness, such as Claude Code's `.claude/settings.local.json`, Codex's `sandbox_mode` in the owner's Codex configuration, or agy's terminal sandbox setting. agy's terminal sandbox has no network by default, so a CLI started inside it cannot reach its Provider. Never commit sandbox settings.
7. **GitHub.**
   1. Find the repository, or create it with `gh` after the owner confirms its visibility.
   2. After the owner confirms, apply the ruleset from the skill's `ruleset.json` with `gh api`, and turn on automatic deletion of head branches. The ruleset targets the default branch (`~DEFAULT_BRANCH`). Its `pull_request` rule requires code-owner review, dismisses approvals when new commits arrive, requires the most recent push to be approved by someone other than its pusher, requires every review thread to be resolved, and allows squash merges only (`allowed_merge_methods: ["squash"]`). It requires the status check `devctl check` from GitHub Actions (`integration_id` 15368). It blocks force pushes and deletion. Its bypass list holds only the repository admin role (`actor_id` 5), in pull-request mode, so the owner can merge their own PRs.
   3. The required approval count is `1` until the live trial (section 10) settles it. With Agent identity in Flight, a PR outside the Protected set has no code owner, so unless the owner reviews it, its approval must come from the Reviewer App. If GitHub does not count that approval, the count becomes `0` and code-owner review stays required, so CODEOWNERS alone decides who must approve: the owner for every path in Walk, and for the Protected set in Flight.
   4. For a public repository, require approval for workflows from all outside contributors. If the default branch is neither `main` nor `master`, record a gap: CI push runs cover only those two names. On a GitHub Free private repository, record a gap: there are no rulesets, so GitHub requires neither rung 2 nor rung 4 before a merge.
   5. Write `* @<owner>` into CODEOWNERS for Walk.
8. **Agent identity (opt-in).**
   1. Explain the trade-off that [ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md) records: the four things Agent identity buys, and its cost of two Apps per owner, keys in the macOS Keychain, and agents writing to GitHub only through `devctl as`.
   2. Ask whether the owner opts in.
   3. If so, run `uvx rapid-ship app`. The owner installs both Apps, and `rs-setup` records each App's ID and slug in `[github]`.
   4. If not, explain which metrics will report "unknown: needs Agent identity", and that Flight would need the ruleset to drop its review requirement, which makes the Protected set advice.
9. **Escalation list and Roster.** The seeded `[escalation]` table is Walk. Ask whether the owner uses more than one Provider; if so, record the Roster with exact model IDs, and recommend a Reviewer from a different Provider than the Worker. `rs-lead` maintains both later.
10. **Tracker.** Ask which tracker the owner uses, confirm that their Harness can reach it through an MCP server or a CLI, and record it in `[tracker]`. Spec 2's plan adds this step.
11. **Metrics.** Show the default Suggested thresholds and record the owner's values in `metrics.toml`. Offer the scheduled metrics Action. Explain that setting up Alarms is the owner's, and that an Alarm plugs in as a project-defined metric. Spec 3's plan adds this step.
12. **Contributing back.** Offer `rs-contribute`. If the owner accepts, add it to `[kit] optional` and run `uvx rapid-ship sync --in-place`.
13. **Doctor.** Run `./devctl doctor --skills`, then resolve or record each gap. The probes include agy when the Roster names it, or when there is no Roster and `agy` is on `PATH`. When they include agy and `rs-setup` itself runs inside another Harness, the agy probes would run agy inside that Session, which Google's consumer terms do not support; say so first, and offer that the owner run `./devctl doctor --skills` in a terminal instead.
14. **Setup PR.** Commit, then push `rapid-ship/init` and open the PR under the owner's sign-in: the branch adds `.github/workflows/`, which neither App may push. With Agent identity on, the guardrails may deny the agent's `git push`; the owner then runs the push and `gh pr create` in a terminal. The owner merges the PR.
15. **Next.** For an existing repository, offer `rs-health`. For a new one, point to `rs-design`, then `rs-breakdown`, then `rs-lead`.

## 9. `rs-health`

`rs-health` is user-invoked. `rs-setup` offers it to existing repositories, and the owner can rerun it at any time. It never edits the repository: its output is a standards milestone that a Lead works through like any other milestone.

- **Reads:** the code; the output of `./devctl doctor` and `./devctl check`; the CI configuration and recent runs; README.md, ARCHITECTURE.md and the AGENTS.md tree; the feature map, the Patterns and `exceptions.toml`; and the last merged PRs with their review threads.
- **Audits** by rung, citing file:line or command output for every finding:
  - rung 1: recurring tasks done several ways, each with one proposed reference implementation and the check that would enforce it; safe interfaces that are missing and the bypasses they would ban; code that departs from an existing Pattern;
  - rung 2: missing checks and test tiers, doctor gaps, Python floor settings the project's own rules replace, advisory Rules that a check could enforce, exceptions whose removal condition has been met, and settings entries that match nothing, such as a `[kit] exclude`, `[map] unguided` or `[tests] unit` entry;
  - rung 3: AGENTS.md, ARCHITECTURE.md and README.md text that no longer matches the code, missing directory guides, gaps in the feature map, and dead code;
  - rung 4: gaps in the Protected set, CODEOWNERS and the ruleset;
  - review comments repeated across recent PRs that a rung could prevent.
- **Returns** a standards milestone in `rs-breakdown`'s levels: one epic per area with findings, and tasks that each fit one PR within the diff cap, with acceptance criteria, a test plan and the tasks each is blocked by. The owner selects what to keep. `rs-health` writes only the selected items to the tracker, as Spec 2's mapping note describes.

The audit is shared with the gardener. `rs-health` runs it once at adoption; `rs-garden` (Spec 3) reruns it over the changes since its last pass and adds new Corrections. The audit lives in `rs-health`'s `references/audit.md`, which `rs-garden` reads (Proposal).

## 10. Testing

**Unit tests**, offline. Plans 2 and 3 built these:

- Lock reading and writing, and status classification.
- `init`: conflicts, seeded skips, symlinked targets, the never-overwrite rule, no git hook running from a tracked hooks path, and the listing of tool settings, hooks and workflows already in the repository.
- `sync`: unchanged files replaced; edited and deleted files made the project's own and never changed; `--revert` and its refusals; excluded paths never touched; project extensions untouched; the stack version winning over the common one.
- Each check step's rules, with fixture repositories: map, references, exceptions, removed tests, tautologies, evidence.
- The removed-test rule: a moved test passes, an undeclared removal fails, a declared one passes, and each removal is classed unit or behavioural by its path.

The new plans add:

- Plan 4: settings, with `[roster]` and `[escalation]` read, a partial App record or Apps without a repository refused, and the removed tables refused. doctor's parsers against recorded GitHub responses and fake Harness executables: a sign-in by any method is ok, the agy probe, the ruleset in Walk, in Flight with Agent identity and in Flight without it, CODEOWNERS against `every_pr`, App items only with Agent identity on, and `--skills` adding and removing its temporary worktree at `HEAD`. Token minting, the `GIT_ASKPASS` helper and `rapid-ship app` against a local fake HTTP server and a fake `security`; these are labelled simulated. `devctl as` with fake `gh` and `git` executables and a local bare repository: each refusal, the token present only in the one child's environment and never in argv or output, and the exit codes.
- Plan 5: `devctl hook` against recorded event JSON for each Harness: each rule's deny or ask, a command list split on `;`, `&&`, `||` and `|`, G7 and G8 only with Agent identity on, no decision when no rule matches, and the Stop event skipping a clean tree, sending the agent back on a failing check, and letting it stop when the Harness's loop flag is set. Map rule 8, the Pattern `task` key, the `SKILL.md` rule, and the diff cap's count, exclusions and declaration. doctor's wiring items.
- Plan 6: the upstream lock (`verbatim` and `patched` files), every Kit skill through map rule 7, and `ruleset.json` passing doctor's ruleset check.

**Integration tests**, offline and labelled as such: `init` on scratch repositories for both stacks, after which `./devctl check` passes; `sync --in-place` between two template versions; and this repository's dog-food tests.

**Live trials**, recorded under `docs/trials/`:

- `rapid-ship app` creating both Apps, then installing them on a second repository.
- Agent identity on a scratch repository: `devctl as worker push` and `devctl as worker gh pr create`; a review posted with `devctl as reviewer gh` that GitHub shows as the Reviewer App's; whether GitHub counts the Reviewer App's approval toward the ruleset's required approval (section 8, step 7); a squash merge with `devctl as worker gh pr merge`; and GitHub refusing a merge while a review thread is unresolved or `devctl check` has not passed.
- The ruleset applied and read back by doctor, and doctor's answer on a GitHub Free private repository.
- The Harness guardrails in Claude Code, Codex and agy: each deny rule, the ask rule, and the Stop hook sending an agent back on a failing fast check, each in the lead Session and inside a subagent. The trial also records whether Codex hooks can ask, the review in Codex's `/hooks`, and the hook's added time per tool call.
- `rs-setup` on a new scratch repository and on an existing one, hello-rapid-ship, including `doctor --skills` for each Harness.
- `rs-health` on an existing repository, ending with a standards milestone in the tracker.

**Dog-food:** this repository's CI runs `./devctl check --tier full`, whose `vendored` step runs `rapid-ship status --strict`.

## 11. Questions

### Answered

The owner confirmed these on 2026-10-16, in the re-scope decision record.

- **Orchestration:** rapid-ship never starts a Session to do work, never watches, resumes or hands one over, and never pushes, reviews or merges as a step in a flow; only doctor's probes start a short headless Session. `devctl dispatch`, `pr`, `review`, `merge` and `watch` are dropped, and `[dispatch]`, `attempt_limit` and `review_round_limit` are gone (sections 4 and 6).
- **Agent identity** is optional, with `rapid-ship app`, the token code and one thin devctl command for `gh` and `git push`. `rs-setup` explains what it buys and the owner opts in. Without it, Flight needs the ruleset to drop its review requirement (sections 3, 6 and 8).
- **Harness guardrails:** the Kit ships settings for Claude Code, Codex and agy that deny `--no-verify`, force pushes, `gh pr merge --admin` and hand edits to the Kit lock, ask before edits to the Protected set, and run the fast check when the agent says it is done. These files join the Protected set. Sandboxing is an offer, not a default (sections 4 and 8).
- **Standards:** the Kit seeds README.md and ARCHITECTURE.md and checks that they and their links exist. It ships the Pattern mechanism, not code. `rs-health` turns findings into a standards milestone and never edits (sections 4, 5 and 9).
- **Trackers and Providers:** any tracker, reached through the Harness; doctor's tracker item is removed. Any Provider; doctor accepts any sign-in method (section 6).
- **Skills:** the eight skills from `rs-setup` to `rs-garden`, the TDD and debugging engineering skills, one real directory per skill under `.agents/skills/` with a `.claude/skills` link for Claude Code, and no per-Harness subagent files (sections 4 and 7).
- **Settings:** the escalation list and the Roster live in `project.toml`, in the Protected set; the Focus is never stored (section 4).
- **Plan 4's code:** doctor, `doctor --skills`, `rapid-ship app`, the token code and the two `process.py` fixes survive, on a fresh branch from the head of `codex/devctl-check` ([plan index](../plans/2026-10-14-kit-and-setup.md)).
- **The gardener** shares `rs-health`'s audit (section 9).
- **Default caps** (answered on 2026-10-15): Ruff's `max-complexity` of 10 and the 500-line `file-size` cap stand.

### Open

- **`devctl hook` (Proposal).** One new devctl command holds the guardrail rules for all three Harnesses, instead of three sets of native permission rules. Codex and agy need hooks for path rules anyway, so one implementation is simpler to keep correct.
- **The Stop hook's loop bound (Proposal).** It sends the agent back once per stop, using the Harness's own loop flag. Codex's and agy's flags are unconfirmed, and so are their working-directory fields.
- **Codex and agy hooks.** Whether Codex hooks can ask, and whether Codex and agy hooks fire inside subagents. Without ask, the Codex wiring omits G5. The live trial settles both.
- **The hook's cost.** Each `devctl hook` run starts uv and Python on every matched tool call. The live trial measures it.
- **`devctl as` (Proposal):** the name, the `pr`, `issue` and `api` allowlist, and passing `gh`'s and git's exit codes through.
- **The ruleset's approval count with Agent identity in Flight:** `1`, if GitHub counts the Reviewer App's approval, else `0` with code-owner review required. The live trial settles it.
- **The diff cap (Proposal):** 500 changed lines, its exclusions, and the `Over the diff cap:` declaration, which `rs-work` makes only after the owner accepted the overage.
- **`[escalation]` (Proposal):** the key names `every_pr`, `kinds` and `revision_rounds`, and the seeded kinds. Spec 2 settles `revision_rounds` with `rs-lead`.
- **`gate.toml` (Proposal):** plan 4 stops seeding and reading it, and this repository deletes its own copy; Spec 3 proposes `metrics.toml` in its place.
- **`rapid-ship adopt` (Proposal):** folded into `rs-setup` step 4, where the agent marks existing suppressions and the `exceptions` step verifies them, rather than built as a command. If a repository has more suppressions than an agent marks reliably, revisit the command.
- **Engineering skills beyond TDD and debugging (Proposal):** keep `rs-codebase-design`, `rs-pr`, `rs-writing-for-agents`, `rs-writing` and `rs-ponytail`. Section 5's Evidence and Spec 2's `rs-work` rely on `rs-pr`, and the seeded root AGENTS.md names `rs-writing` and `rs-ponytail`.
- **`doctor --skills` without a Roster (Proposal):** probe each of the three supported Harnesses found on `PATH`.
- **Map rule 8 (Proposal):** whether the root AGENTS.md must also link to README.md and ARCHITECTURE.md.
- **The Pattern `task` key (Proposal).**
- **The shared audit's home (Proposal):** `rs-health`'s `references/audit.md`, which `rs-garden` reads; Spec 3 uses the same path.
- **Settings that other specs asked for:** the App slugs in `[github]` and dropping `[release]` (Spec 3); `[tracker]` and `[design]` (Spec 2).
- **Roster Harnesses (Proposal):** `harness` accepts `claude`, `codex` and `agy` only, the Harnesses doctor can check. Another Harness, such as pi, joins with its own wiring layer. This limits only the Harnesses a Roster can name for a role: a Lead in any Harness can use the Kit, and needs no Roster when it uses one Provider.
