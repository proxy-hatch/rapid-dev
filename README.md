![rapid-ship — Ship more. Supervise less.](asset/banner.jpeg)

[![CI](https://github.com/proxy-hatch/rapid-ship/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/proxy-hatch/rapid-ship/actions/workflows/ci.yml)
[Documentation](https://proxy-hatch.github.io/rapid-ship/) · [Architecture](ARCHITECTURE.md)

**Coding agents that earn the right to ship.** Start with an approved design. rapid-ship helps slice the work, set up your project, coordinate agents, check changes and learn from review. You choose the language, models and coding tools.

The ambition: **1,000 high-quality PRs a month without 1,000 approval requests.** That is a goal to measure, not an achieved benchmark. Start supervised; reduce routine approval only as quality holds.

**Early preview.** Setup, task execution, checks, review and metrics are available for supervised use. Automatic delivery is blocked pending a trusted approval service and live qualification. AstraBox integration, automatic model handoff and Linear sync are still planned. The badge reports repository CI, not permission to ship.

## How it works

1. **Slice the design.** Plan small tasks with clear ownership and dependencies. Each worker gets one change and its tests; a stronger reviewer checks the result with project context.
2. **Keep work recoverable.** The controller saves task state and logs outside workers. AstraBox is the selected future backend for durable coding sessions and Docker sandboxes; its integration is still to come.
3. **Strengthen the rules.** Review the first changes yourself. Move repeated corrections up the enforcement ladder: **1)** prevent mistakes through structure and types, **2)** catch them with automated checks, **3)** guide agent judgment, **4)** discover gaps through human review.
4. **Scale with evidence.** Track PR revisions, defects, review effort and test quality. Increase concurrency only while agreed thresholds hold. See the [architecture](ARCHITECTURE.md) for the boundaries and current limits.

## Install

Requires a POSIX host, Python 3.12+, Git and [uv](https://docs.astral.sh/uv/). Python runs `devctl`; your projects can use any language. Bring a coding agent and its model access. Docker is needed only for container execution.

```sh
git clone https://github.com/proxy-hatch/rapid-ship.git
cd rapid-ship
./devctl setup
```

Setup installs the controller in this checkout's `.controller/`. Keep the framework checkout separate from projects it manages. Projects receive a `./devctl` wrapper and an ignored local link to that installation; no shell environment export is needed.

## Usage

Open your coding agent in this checkout and ask:

> Use rapid-ship setup to set up ../my-project from its approved design. Ask one question at a time. Show my installed providers and available models, then help me choose a small worker and a large reviewer. Preserve my existing choices.

The setup conversation covers the stack, checks, writing and coding preferences, environments, GitHub repository and Linear project. A medium model tier is optional. The agent saves settings and handles the task files. Missing authentication or an unverified integration stays visible; selecting it is not proof it works.

Antigravity catalog discovery works. Its verification currently stops before sending a prompt because the tested CLI still exposes tools; authentication remains unknown. See [provider limits](ARCHITECTURE.md#project-setup).

Continue in the project:

> Split the approved design into small tasks. Check coverage and dependencies before starting. Give each worker one change with its tests; stop for unresolved design decisions.

> Show progress, recent logs and anything waiting for me.

> Use rapid-ship-improve: setup keeps asking me the same question. Fix the project setting if that solves it; otherwise prepare a focused framework PR.

## Getting started: ship hello

Try the whole workflow on a disposable project before trusting larger changes. In your coding agent, start with:

> Use rapid-ship start to create ../hello-rapid-ship. Approved design: a command prints `Hello, world!` and exits successfully; `--name Ada` prints `Hello, Ada!`; an empty name fails with a clear error. Ask which language I want. Keep this to one task with tests. Guide me through independent review, a GitHub PR, manual merge and metrics. Do not enable unattended delivery.

1. **Set up.** Choose the language, test command, worker/reviewer models and environment. Decide the GitHub repository's name and visibility. Connect the selected Linear project and GitHub repository through the [official integrations](docs/linear.md). The agent records the design and initializes the project without replacing existing settings.
2. **Slice.** Have the agent prepare and review one leaf task covering the command and its success/error tests, then register it with `devctl`. Keep the task's scope in Linear and link its eventual PR. Service access that is unavailable is an explicit setup gap.
3. **Build and test.** Use `devctl run` only after the chosen environment has working tools and model access. Otherwise, make the change in your current supervised coding session and run the tests there. That fallback is session work: registration does not mean `devctl` executed or verified it.
4. **Review and revise.** Ask an independent reviewer to read the approved design, diff and actual test results. Fix findings and rerun affected checks. If no separate reviewer is available, pause for your review; do not mark it independently reviewed.
5. **Open the PR.** Have your session agent publish the reviewed branch and create a GitHub PR with the Linear link, test results and remaining limits. Check CI and review the final diff. The preview's automated PR command remains blocked; this is an explicitly supervised GitHub action.
6. **Merge manually.** Merge the PR yourself after the checks and review pass. Pull the merged change, rerun the command and tests, and update the Linear issue. A PR or a local approval is not a merge.
7. **Measure.** In the project, inspect the recorded work and sync GitHub observations:

   ```sh
   ./devctl status
   ./devctl logs
   ./devctl metrics sync-github
   ./devctl metrics
   ```

Direct-session work will not acquire controller execution logs or check/review records retroactively. GitHub sync still collects its PR revisions, review events and CI results. Missing measurements stay unknown, including active human review time. Use what the first change taught you to strengthen checks before adding agents.

[Task slicing](docs/task-slicing.md) · [Agent support](docs/agents.md) · [Environments](docs/environments.md) · [Metrics](docs/metrics.md) · [Delivery limits](docs/authority.md)

Try a small project, tell us where the process gets in your way, or contribute a focused PR. Help make the next agent easier to trust than the last.
