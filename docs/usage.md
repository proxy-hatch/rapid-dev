# Using rapid-dev

`devctl` takes an **approved design** through small coding tasks, isolated execution, checks, and independent review. Projects can use any programming language. Python and Pydantic power `devctl` itself; they are not required in project code.

Version `0.1.0` is a bootstrap candidate. The integration PR stays draft pending human-reviewed live agent/model trials. Unattended delivery is disabled.

## Install

`devctl` needs Python 3.12+, Git, `uv`, and a POSIX host. From a reviewed rapid-dev checkout, build and install the wheel **outside the project being changed**:

```sh
uv sync --locked
uv build
uv venv --python 3.12 "$HOME/.local/share/devctl/0.1.0"
uv pip install --python "$HOME/.local/share/devctl/0.1.0/bin/python" \
  dist/rapid_dev-0.1.0-py3-none-any.whl
export DEVCTL_CONTROLLER="$HOME/.local/share/devctl/0.1.0/bin/devctl"
"$DEVCTL_CONTROLLER" --version
```

The repository's optional `./devctl` wrapper checks this absolute path and version. The trusted GitHub service must call the installed executable directly: a worker can edit the repository wrapper. Keep the installation, credentials, policy, and signing keys outside worker mounts. Review and install upgrades separately.

## Start a project

Run these commands in a Git repository with a nonempty approved design:

```sh
"$DEVCTL_CONTROLLER" init --name my-project --design docs/approved-design.md
"$DEVCTL_CONTROLLER" interview
"$DEVCTL_CONTROLLER" interview --answer worker_runner --value '"codex"'
"$DEVCTL_CONTROLLER" doctor --json
```

`init` preserves existing files and adds project settings, a resumable setup interview, instructions, and a skill. The default `custom` profile has no language requirements. Use `--profile python-cli` for Python defaults. The interview records repository, agent/model, environment, resource, check, and release choices. `doctor` reports readiness without changing files.

**Initial setup also connects Linear and GitHub.** Follow the [integration setup](linear.md): choose the workspace/team/project and repository, connect official MCP/API access, configure PR linking and status ownership, then verify a small issue-to-PR flow. No third-party Linear CLI is used. The current interview and `doctor` do not verify these integrations; their configuration result alone is not end-to-end readiness.

Provide the agent CLI, runtime, checks, and model authentication inside the chosen environment before a live run. Host logins, API keys, SSH agents, hooks, and user settings are not inherited. Docker's private-network mode has no network access, so it cannot reach an ordinary remote model endpoint. Keep model authentication separate from GitHub credentials.

Choose `agy` for a Docker worker with the standalone Antigravity CLI and an explicit model from `agy models`. Codex or Claude can review its work; Antigravity review is not enabled. A task can override `runner` and `model`, but changing its harness requires its own model. See [agent support and current limits](agents.md).

Use the installed rapid-dev skill to [split the approved design into tasks](task-slicing.md). It maps requirements, defines ownership and dependencies, and requests a review of the plan. Linear is the task tracker; [automatic sync is planned](linear.md). Write the accepted tasks as a JSON array using [this example](../examples/task-contract.json). Set the full base commit ID, dependencies, owned paths, acceptance criteria, environment, and checks. `decompose` validates and registers that array; the CLI does not generate the plan or sync Linear.

```sh
"$DEVCTL_CONTROLLER" decompose --tasks tasks.json
# After environment and model setup has been tested:
"$DEVCTL_CONTROLLER" run --tasks tasks.json
"$DEVCTL_CONTROLLER" status
"$DEVCTL_CONTROLLER" evidence
"$DEVCTL_CONTROLLER" metrics
```

`run` schedules independent tasks within the chosen CPU, memory, and shared-resource limits. Each attempt uses separate worker, check, and reviewer environments. Reviewer-requested fixes retry up to the configured limit. Failed checks stop the attempt. An `approved` task has passed checks and review; it has not yet been pushed, merged, or released. Integrate approved dependency commits into a task's base before running dependent work.

## Commands

Results are JSON. Put global `--project PATH` and `--state-dir PATH` before the command. Default state is `.devctl/state/`.

| Command | Purpose |
| --- | --- |
| `init`, `interview`, `doctor` | Set up a project and check readiness. |
| `decompose --tasks FILE`, `run --tasks FILE` | Register tasks and execute ready work. |
| `status`, `evidence [--receipt PATH]` | Read task state and verified check/review records. |
| `metrics`, `metrics sync-github`, `metrics import FILE` | Report quality, collect GitHub observations, or import external data. |
| `cancel TASK` | Stop the current attempt or cancel a waiting task. |
| `resume TASK [--attempt ID] [--base SHA --expected-base SHA]` | Recover interrupted work and optionally change its base. |
| `new NAME` | Add a Python feature and test without overwriting files; currently requires `python-cli`. |
| `github preflight --check-context NAME --app-id ID` | Inspect branch protection using a real installed GitHub App. |
| `trial`, `harden`, `github create-pr`, `github merge`, `release` | Block until a trusted approval service is connected. |

After an interruption, read `status`. When recovery is required, use the reported attempt ID with `resume`. A base change requires both the new full commit ID and the expected old ID; update the input task file with the returned values. Earlier checks no longer apply. Unknown external results or failed ownership checks need operator investigation before retry.

Exit codes: `0` success, `2` blocked/not ready/incomplete, `3` invalid input, `4` runtime failure, `130` interrupted. Argument errors also use `2`.

## Quality and delivery

Every installation includes [quality metrics](metrics.md). `devctl metrics sync-github` collects PR revisions, review events, and basic CI results. Imports add deployment, incident, active human-review time, and test data from the systems you use. Reports distinguish missing data from zero, and agent runtime from human review time. Metrics do not automatically raise concurrency or enable unattended delivery.

The controller validates inputs with Pydantic and stores task state in SQLite. Each check/review record identifies the exact code and settings tested; a host-held key detects later changes to that record. The GitHub service verifies those records before acting and never runs project code while holding GitHub credentials. See [delivery permissions](authority.md).

Docker and explicitly allowed native execution are implemented. Worktrees currently support native execution only. Docker Sandboxes needs a verified installation; OpenHands and AWS provisioning need adapters. CPU, memory, and concurrency limits are configurable. See [environment setup](environments.md).

## Develop devctl

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy src
uv build
```

CI runs these checks on Python 3.12 and 3.13 with read-only repository access. Simulated tests do not replace live trials. CI does not install a GitHub App, configure branch protection, or grant delivery permissions.

The [design](superpowers/specs/2026-10-10-framework.md) and [plan](superpowers/plans/2026-10-10-bootstrap.md) describe the implementation scope.
