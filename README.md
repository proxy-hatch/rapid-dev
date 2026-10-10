# Trust-First Engineering

A local Python controller for turning an **already approved design** into bounded coding tasks, isolated workspaces, fresh checks, and independent review evidence. Product ideation is outside its scope.

This is the bootstrap integration candidate, version `0.1.0`. The first integration PR stays draft until a human completes the live agent/model trial. A passing test suite or provider smoke test does not authorize unattended delivery or a production release.

## Install a pinned controller

Requires Python 3.12 or newer on a POSIX host, Git, and `uv` for development. Build and review the wheel first, then install that exact artifact into a dedicated environment **outside the candidate checkout**:

```sh
uv sync --locked
uv build
uv venv --python 3.12 "$HOME/.local/share/devctl/0.1.0"
uv pip install --python "$HOME/.local/share/devctl/0.1.0/bin/python" \
  dist/trust_first_engineering-0.1.0-py3-none-any.whl
export DEVCTL_CONTROLLER="$HOME/.local/share/devctl/0.1.0/bin/devctl"
./devctl --version
./devctl --help
```

The project wrapper requires an explicit absolute executable path and the pinned version `0.1.0`. It never defaults to running the candidate source. It is a convenience for supervised use: a candidate can edit its repository wrapper, so a trusted host broker must invoke the installed executable directly and never run candidate `./devctl` in its credential context. Keep the installed controller, broker credentials, policy stores, and receipt keys outside worker mounts. A framework upgrade requires separate review and installation; candidate changes cannot replace their own controller.

## Start a project

Run these commands in a Git repository containing a nonempty approved design:

```sh
"$DEVCTL_CONTROLLER" init --name my-project --design docs/approved-design.md
"$DEVCTL_CONTROLLER" interview
"$DEVCTL_CONTROLLER" interview --answer worker_runner --value '"codex"'
"$DEVCTL_CONTROLLER" doctor --json
```

`init` preserves existing project files and creates `.devctl/project.json`, a resumable interview, the `python-cli` profile, project instructions, and the project skill. `interview` shows the next unanswered decision; `--answer ID --value JSON` records an explicit answer. Complete repository, worker/reviewer CLI and model, execution provider, image or native permission, resource budgets, checks, and release-target decisions. `doctor` inspects readiness without writing files. Configuration readiness and autonomy readiness are separate; autonomy is currently unavailable through the CLI.

Codex and Claude Code adapters execute **inside the selected environment**. Host CLI logins, API keys, SSH agents, hooks, and user configuration are not inherited. Before a live run, provide the selected CLI and tools in the isolated image or backend, configure a separate model authentication path, and trial the exact CLI version and model. Private Docker networking currently means `--network none`, so an ordinary remote model endpoint is unavailable in that mode. Never solve model authentication by mounting GitHub broker credentials.

Create a task JSON array using [the task example](examples/task-contract.json), replacing its base placeholder with the full approved Git commit ID. Tasks declare dependencies, owned paths, acceptance criteria, a configured environment, and named checks. `decompose` validates and registers these supplied contracts; it does not invent a task plan.

```sh
"$DEVCTL_CONTROLLER" decompose --tasks tasks.json
# Only after provider/tool/model setup and supervised compatibility checks:
"$DEVCTL_CONTROLLER" run --tasks tasks.json
"$DEVCTL_CONTROLLER" status
"$DEVCTL_CONTROLLER" evidence
```

`run` schedules compatible independent tasks within memory/CPU and exclusive-resource budgets. Workers, fresh check environments, and reviewers use separate environments within each attempt; resulting receipts bind exact source and configuration digests. An `approved` task means the configured checks and reviewer gate passed, not that it was pushed, merged, or released. Dependent work requires its approved dependency commit to be integrated into the declared base; the controller does not silently combine commits.

## Commands and recovery

All operational results are JSON. Global `--project PATH` and `--state-dir PATH` precede the subcommand; default state lives in `.devctl/state/`.

| Command | Current behavior |
| --- | --- |
| `init`, `interview`, `doctor` | Preserve project choices, record explicit answers, inspect readiness. |
| `decompose --tasks FILE`, `run --tasks FILE` | Validate/register contracts; execute ready tasks with bounded repair. |
| `status`, `evidence [--receipt PATH]` | Inspect durable state and controller-sealed receipts. |
| `cancel TASK` | Cancel the current exact attempt or a nonactive task. |
| `resume TASK [--attempt ID] [--base SHA --expected-base SHA]` | Reconcile owned environments, optionally replace an exact expected base, then return a task to pending. |
| `new NAME` | Create a small Python feature and executable test without overwriting files. |
| `github preflight --check-context NAME --app-id ID` | Read GitHub branch protection; requires a real installed App ID and configured broker login. |
| `trial`, `harden`, `github create-pr`, `github merge`, `release` | Return an actionable authority blocker. No CLI authority adapter is bundled. |

After interruption, inspect `status` first. If reconciliation is required, copy the exact attempt ID into `resume TASK --attempt ID`. If the approved base has advanced, supply the new full commit ID with `--base` and the previous full commit ID with `--expected-base`. The command returns the revised task contract; update the input task JSON to match before the next `run`, since registration rejects contract drift. Base changes invalidate earlier evidence. Unknown external effects or failed ownership checks require operator reconciliation before retry. Cancelled/expired attempts cannot retain execution authority.

Exit codes: `0` successful command, `2` blocked/not ready/incomplete run, `3` invalid input, `4` operational failure, `130` interruption. Argument parser errors also use `2`; inspect the output and stderr.

## Architecture and limits

Strict Pydantic contracts reject unknown fields, unsafe paths, cycles, and invalid resource declarations. SQLite WAL records claims, events, leases, and external-effect intents; stale attempt owners are fenced. Environments compose a workspace, an execution provider, and explicitly registered test-resource adapters. Evidence binds task/attempt, head/base commits, policy, check recipe, environment, and controller version. The credential-bearing GitHub broker consumes sealed evidence and runs no candidate commands.

The Python library exposes pinned policy/trial stores and gated GitHub push, PR, merge, and staged-release publication APIs. Wiring those APIs to a trusted external authority service is an operator integration, not an installed CLI feature. Release building, staging, uploading, and cloud provisioning are not supplied by the broker. See [authority and calibration](docs/authority.md) and [environment compatibility](docs/environments.md).

Current provider status: clone plus explicitly allowed native execution works as a supervised host convenience; clone plus Docker has a limited real provider smoke test. Worktrees currently support native execution only. `sbx` remains blocked until its CLI/configuration and compatibility are verified; OpenHands has no execution adapter. Named AWS resources require separately registered adapters and explicit leases. The default 4096 MB project budget and the observed Docker allocation are configurable, not universal concurrency ceilings.

## Development checks

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy src
uv build
```

CI runs these checks on Python 3.12 and 3.13 with read-only repository permissions. Offline injected services and fixture agents exercise boundaries; they do not constitute live provider, model, GitHub, or deployment verification. The CI workflow does not install a controller GitHub App or configure required checks.

The [approved design](docs/superpowers/specs/2026-10-10-framework.md) and [implementation plan](docs/superpowers/plans/2026-10-10-bootstrap.md) define the bootstrap acceptance boundary.
