# Architecture

rapid-ship turns an approved design into small tasks, checked changes and reviewed PRs. Product ideation is outside its scope. Projects can use any language; Python and Pydantic implement the controller, `devctl`.

## Separate the responsibilities

| Component | Responsibility | Current status |
| --- | --- | --- |
| Project skills | Setup conversation, design → epics → optional stories → leaf tasks, improvement workflow | Shipped; the agent prepares the plan and task files |
| `devctl` | Task validation, resource allocation, execution, checks, review, recovery and measurements | Available for supervised use |
| Harness and model | Worker or reviewer selected for a role | Bring your own; verify the chosen combination and its authentication |
| Execution environment | Workspace, processes, resource limits and test resources | Docker and explicitly allowed native execution; [other adapters vary](docs/environments.md) |
| AstraBox | Managed Docker sandboxes and durable coding sessions | Selected after trials; integration is not implemented |
| Linear | Accepted scope, dependencies, human responsibility and progress | Official MCP/API setup; automatic sync is planned |
| GitHub | Code, PRs, checks and merge history | Metrics sync available; automated writes require a trusted approval service |

Linear's human assignee and optional app delegation do not select the internal coding worker. rapid-ship selects that worker's model, harness and environment. Do not duplicate the task tracker in GitHub Issues.

## Project setup

`./devctl setup` builds and installs a wheel under the framework checkout's `.controller/`. Project initialization adds settings, instructions, skills and a wrapper. An ignored local connection points the wrapper at the installed controller. Reinitialization preserves existing project choices and customized files.

Setup reuses an existing installation. To install reviewed framework changes, stop the project sessions using it, then explicitly run `./devctl setup --rebuild` in the framework checkout.

Settings live in `.devctl/project.json`: `providers`, `models.small`/`models.large` (optional `models.medium`), `guidance.style` and `guidance.code`, alongside checks and environments. Model entries contain the provider and its exact model ID. Defaults use concise, plain writing and build only what the current task needs. `.devctl/local.json` holds the local framework link; `.devctl/providers.json` holds dated discovery and authentication checks. Both are ignored by Git. Provider checks expire after 24 hours; a catalog refresh cannot renew an earlier model probe.

The setup conversation records the project's code and writing conventions, checks, environments, resources and small/large model choices; a medium tier is optional. The agent discovers providers and available models before proposing exact IDs. Installation, authentication, model availability and successful execution are different checks. Preserve the user's selected model; do not silently substitute another.

Codex and Claude expose native sign-in status and model catalogs without inference. Antigravity exposes its catalog but no verified read-only sign-in status. `./devctl providers --provider agy --verify --model EXACT` confirms the model and session, then sends a small greeting from an empty temporary directory with normal permission controls. It requires a complete successful response and records observed tool activity separately. The directory and prompt are not a sandbox or proof of disabled tools. Provider allowance covers the CLI's built-in context as well as the greeting. A [live agy 1.3.3 trial](docs/trials/2026-10-11-agy-authentication.md) passed with `gemini-3.7-flash-high`; this does not establish access inside a worker container or qualify unattended delivery.

The controller embeds packaged Ponytail and role-specific engineering guidance directly in worker/reviewer prompts. Candidate files cannot replace these defaults. Generated project instructions load the same guidance for interactive sessions, with additional skills read as needed. Existing custom files remain unchanged on initialization; the setup skill must reconcile their instruction links. See [engineering skills](docs/engineering-skills.md) for routing, dependencies and upstream sources.

Keep the framework installation outside candidate workspaces. A project wrapper is editable project code, so a privileged host service must call the installed controller directly. Framework improvements happen in a separate checkout; merging one does not replace the controller running another project.

## One task, one checkable outcome

A worker receives one leaf task with code, tests, owned paths, acceptance checks, dependencies, an exact base commit and a time/retry budget. A stronger reviewer reads the wider design and relevant context. Review the plan for requirement coverage, shared interfaces and conflicting ownership before dispatch. Unresolved design blocks affected tasks.

The skill plans; `devctl decompose` validates and registers supplied task files. It does not create a plan or Linear issues. Independent PRs are the default. Dependent tasks start with their dependency commits present in the base. [Stacked PRs](docs/task-slicing.md) need a future adapter and fresh checks when a head or base changes.

## Execution and recovery

Each controller attempt uses separate worker, check and reviewer environments. The scheduler reserves CPU, memory and declared exclusive resources; a fixed port or shared test account can serialize otherwise independent work. Docker memory is configurable, not capped at 4 GB. A worktree separates source files but does not isolate host processes, credentials or ports.

Checks run before review. Reviewer-requested repairs are limited by the configured retry budget. An approved task has passed that attempt's checks and review; it has not been pushed, merged or released. Controller records bind results to the exact code, commands, environment, policy and version.

Task state lives in SQLite outside worker mounts. `logs` combines task events with command names, exit codes and durations; it omits prompts, raw tool output and credentials. Read `status` and `logs` after interruption, then reconcile the recorded attempt before resuming. Unknown external results or cleanup ownership must be investigated before a retry. Do not start a replacement writer while the old one can still change files.

The [AstraBox trial](docs/runtime-choice.md) supported reusing its sandbox/session lifecycle. It also exposed surviving child processes after turn interruption and failed recovery of an active Codex turn after a server crash. The planned adapter must stop the session, inspect side effects and restart safely. Automatic cross-model or cross-harness [handoff](docs/session-handoffs.md) remains future work.

## Earn autonomy

Start with human-reviewed changes. Define quality thresholds before increasing concurrency, then turn repeated corrections into stronger defaults:

| Rung | Put the fix here | Example |
| --- | --- | --- |
| 1. Prevent the mistake | Architecture, data structures and types | Keep merge credentials out of worker environments |
| 2. Enforce the rule | Compiler, linter, tests and CI | Reject a forbidden import or catch a regression |
| 3. Guide judgment | Skills and automated review | Explain task boundaries or API review criteria |
| 4. Learn from review | Human feedback | Identify a repeated correction to move into rungs 1–2 |

Every installation reports [quality metrics](docs/metrics.md), including observed PR revisions, review rounds and CI duration. Deployment failures, incidents, active human review time and mutation results need inputs from the project's tools. Missing data is unknown. Metrics do not grant permissions or increase concurrency automatically.

Automatic delivery needs a trusted host approval service, verified GitHub protection and representative live trials. That service is not wired into the CLI, so `trial`, `harden`, automated PR creation, merge and release remain blocked. Ordinary CI success is not delivery authorization. A supervised session can create a reviewed PR for a human to merge, as the [hello walkthrough](docs/getting-started.md) demonstrates.

The privileged GitHub broker never runs candidate builds, tests or hooks with its credentials. Every write needs current evidence and permission for that action. Uncertain network outcomes are reconciled against GitHub before retry. See [delivery permissions](docs/authority.md).

## Inspect a project

The agent handles the low-level command arguments; these commands expose the underlying state:

| Command | Purpose |
| --- | --- |
| `./devctl providers` | Inspect installed providers and available model choices |
| `./devctl interview`, `./devctl doctor --json` | Resume setup; check readiness without changing files |
| `./devctl decompose --tasks FILE`, `./devctl run --tasks FILE` | Register tasks; execute ready work |
| `./devctl status`, `./devctl logs`, `./devctl evidence` | Inspect task state, events and controller check/review records |
| `./devctl cancel TASK`, `./devctl resume TASK` | Stop or recover work; use the reported attempt ID when required |
| `./devctl metrics`, `./devctl metrics sync-github` | Report saved measurements; collect GitHub observations |

Results are JSON. Global `--project PATH` and `--state-dir PATH` go before the command. Default state lives in `.devctl/state/`. Exit codes are `0` success, `2` blocked/incomplete, `3` invalid input, `4` runtime failure and `130` interrupted; argument errors also use `2`.

## Develop the framework

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy src
uv build
```

CI runs tests, static checks and the build on Python 3.12 and 3.13. The documentation site reads this file, the README and every Markdown guide under `docs/` directly; it does not maintain a separate copy. To preview it, use Node.js 22+ (CI uses 24):

```sh
npm --prefix website ci
npm --prefix website start
# Production build, including internal link checks:
npm --prefix website run build
```

The site pins four patched transitive dependencies while upstream catches up. As of 2026-10-11, the remaining [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) has no published fix; it concerns deeply nested build patterns. Pages serves static output, without a Node server. Recheck `npm audit` when updating the lockfile.

The docs workflow builds PRs and deploys successful `main` builds to GitHub Pages. Repository Pages settings must use GitHub Actions. Historical [design](docs/superpowers/specs/2026-10-10-framework.md), [implementation plan](docs/superpowers/plans/2026-10-10-bootstrap.md) and [validation records](docs/bootstrap-validation.md) remain available as background; their intended behavior is not a claim of current support.
