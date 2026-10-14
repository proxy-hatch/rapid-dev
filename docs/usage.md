# Usage

Use a coding session for setup and planning. Use the project's `./devctl` for checks, execution state, logs and measurements.

New here? Follow [Getting started](getting-started.md) for one complete supervised PR.

## Start or resume setup

Save your approved design in the project, for example as `docs/design.md`. Open Codex, Claude Code or Antigravity in that directory, with access to the framework checkout. See the [launch commands](getting-started.md#3-let-the-interview-set-up-the-project), then ask:

> Read the framework's .agents/skills/rapid-ship/SKILL.md and use setup for this project. The approved design is docs/design.md.

Use your design's actual path if it differs. To resume, make the same request from the same project directory.

The agent creates the project wrapper, saves interview answers, and handles GitHub and official Linear setup. It discovers available accounts and destinations, creates selected resources, and checks access. You choose the stack, models and destinations, complete logins, and grant permissions. A medium model tier is optional.

Expect a setup summary with completed checks and remaining blockers. Progress stays in gitignored `.devctl/state/setup.md`. The shareable summary and exact worker/reviewer commands go in `docs/setup.md`. On resumption, the agent reads those notes and checks incomplete operations before retrying.

The interview tool does not select the worker or reviewer implicitly. Those provider/model pairs remain explicit. The controller supports Codex, Claude or Antigravity as the large reviewer, whichever tool runs the interview.

Authentication checks use native provider status where available. Antigravity sends a small greeting to the selected model. The request may consume provider allowance. Authentication does not prove tool isolation or qualify an execution environment.

Provider/model choices stay exact. Missing authentication or integration access remains a setup gap. See [project setup](https://github.com/proxy-hatch/rapid-ship/blob/archive/controller-2026-10/ARCHITECTURE.md#project-setup) for configuration and provider limits.

## Plan and implement

In the project session, ask:

> Use rapid-ship to plan implementation from docs/design.md. Stop after independent plan review, before implementation or task registration.

Expect a reviewed plan and task JSON, with each ready task linked to its Linear issue. Check that the plan covers your design and identifies blocked work. Each worker gets one small task with its tests. See [task slicing](task-slicing.md) for the assignment format.

Next, choose supervised sessions, as in [Getting started](getting-started.md#5-implement-with-the-worker), or controller execution below. Planning alone does not register or run tasks.

The bundled [engineering guidance](engineering-skills.md) covers small changes, shared terminology, TDD, debugging, architecture and independent review. It loads only the references needed for the current work.

## Run through devctl

Use this path only for controller execution. For the supervised walkthrough, leave its tasks unregistered and continue with its worker session.

First, check configuration:

```sh
./devctl doctor --json
```

Resolve reported blockers before continuing. Native execution requires explicit permission and cannot qualify for unattended delivery. Docker needs an image with the required tools and a tested authentication path. A successful model login alone is insufficient. See [environments](environments.md) and [agent support](model-harnesses.md).

When the environment is ready and the plan is reviewed, register its ready tasks. **This command changes controller state.** It validates supplied JSON; it does not generate a plan or synchronize Linear.

```sh
./devctl decompose --tasks tasks.json
```

Continue only if registration succeeds. Run the registered work with the configured worker, checks and reviewer:

```sh
./devctl run --tasks tasks.json
./devctl status
./devctl evidence
```

Inspect the recorded state and check results. A run does not grant merge or release permission.

If an unused task is already registered, cancel it before implementing the same scope in a supervised session. Replace `TASK_ID` with its ID from `./devctl status`:

```sh
./devctl cancel TASK_ID
```

The task must stop before another session executes its scope. Cancellation does not undo a PR or external operation. Supervised session work does not acquire controller execution, check or review records retroactively.

## Inspect progress

```sh
./devctl status
./devctl logs
./devctl evidence
```

Status reports stored task state. Logs show command outcomes and task events. Evidence contains controller check/review records when those stages ran. Empty results mean no recorded work, not successful verification.

To inspect one task, replace `TASK_ID` with its ID from `status`:

```sh
./devctl logs --task TASK_ID --limit 20
```

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
