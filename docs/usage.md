# Usage

Use a coding session for setup and planning. Use the project's `./devctl` for checks, execution state, logs and measurements.

New here? Follow [Getting started](getting-started.md) for one complete supervised PR.

## Start or resume setup

Open Codex, Claude Code or Antigravity in the target project. Give the session access to the framework checkout. See the [commands](getting-started.md#3-let-the-interview-set-up-the-project), then ask:

> Read the framework’s .agents/skills/rapid-ship/SKILL.md and use setup for this project from its approved design. Ask one question at a time. Show my installed providers and available models. Help me choose a small worker and a large reviewer. Preserve my existing choices.

The agent creates the project wrapper, saves interview answers, and handles GitHub and official Linear setup. It discovers available accounts and destinations, creates selected resources, and checks access. You choose the stack, models and destinations, complete logins, and grant permissions. A medium model tier is optional.

Progress stays in gitignored `.devctl/state/setup.md`. The shareable summary and exact worker/reviewer commands go in `docs/setup.md`. Resume setup in the same project directory. The agent reads those notes and reconciles incomplete operations before retrying.

The interview tool does not select the worker or reviewer implicitly. Those provider/model pairs remain explicit. The controller supports Codex or Claude as the large reviewer, even when Antigravity runs the interview.

Authentication checks use native provider status where available. Antigravity sends a small greeting to the selected model. The request may consume provider allowance. Authentication does not prove tool isolation or qualify an execution environment.

Provider/model choices stay exact. Missing authentication or integration access remains a setup gap. See [project setup](../ARCHITECTURE.md#project-setup) for configuration and provider limits.

## Plan and implement

In the project session, ask:

> Split the approved design into small tasks. Check coverage and dependencies before starting. Give each worker one change with its tests. Resolve material implementation questions, without revisiting the project's purpose.

The skill prepares the plan and task JSON. A project-aware reviewer checks them before dispatch. Each worker gets one leaf task. The plan lives in Linear, with code and PRs in GitHub.

The bundled [engineering guidance](engineering-skills.md) covers small changes, shared terminology, TDD, debugging, architecture and independent review. It loads only the references needed for the current work.

## Run through devctl

Use this path after the configured environment has working agent tools and model access:

```sh
./devctl doctor --json
./devctl decompose --tasks tasks.json
./devctl run --tasks tasks.json
./devctl status
./devctl evidence
```

`decompose` checks and registers supplied tasks. It does not generate a plan or synchronize Linear. `run` attempts registered work with the configured worker, checks and reviewer. It does not grant merge or release permission.

Stop on reported blockers. Native execution requires explicit permission and cannot qualify for unattended delivery. Docker needs an image with the required tools and a tested authentication path. A successful model login alone is insufficient. See [environments](environments.md) and [agent support](agents.md).

For a supervised coding session, leave its task unregistered. Session work does not acquire controller execution, check or review records retroactively. If an unused task is already registered, cancel it before implementing the same scope elsewhere:

```sh
./devctl cancel TASK_ID
```

Replace `TASK_ID` with the ID from `./devctl status`. The task must stop before another session executes its scope. Cancellation does not undo a PR or external operation.

## Inspect progress

```sh
./devctl status
./devctl logs
./devctl logs --task TASK_ID --limit 20
./devctl evidence
```

Status reports stored task state. Logs show command outcomes and task events. Evidence contains controller check/review records when those stages ran. Empty results mean no recorded work, not successful verification.

For an interrupted task, inspect its state before resuming:

```sh
./devctl resume --help
```

Recovery can require the exact attempt ID and an explicit base update. Follow the reported conditions. See [delivery boundaries](authority.md).

## Measure and improve

```sh
./devctl metrics sync-github
./devctl metrics
```

GitHub sync collects PR revisions, reviews and Actions results. External adapters supply deployment, incident, mutation and active human-review data. Missing data stays unknown. See [metrics](metrics.md).

For framework feedback, ask:

> Use rapid-ship-improve: setup keeps asking the same question. Reproduce it from this project's settings and logs. Fix the project setting if possible, otherwise prepare a focused framework PR.

The skill uses `.devctl/local.json` to locate the framework checkout. Give the session folder access when needed. See [improving rapid-ship](improving-rapid-ship.md).
