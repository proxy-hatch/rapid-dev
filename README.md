# rapid-ship

**Ship more. Supervise less.**

An opinionated framework for coding agents that earn the right to ship without routine human approval.

Managing a few agents can already consume your day. rapid-ship takes on the task slicing, environment setup, scheduling, checks and review so you can focus on direction and difficult decisions.

The goal: **a fleet of agents you can trust to deliver**, with autonomy earned through measured quality. Our ambition is 1,000 high-quality PRs a month without 1,000 approval requests. That is a target we intend to validate, not an achieved benchmark.

## Trust first. Then scale.

1. **Bring a design.** rapid-ship turns it into small tasks with clear ownership and dependencies.
2. **Set up your project.** Answer a short interview, then verify your agents, environments, Linear and GitHub connections.
3. **Prove the workflow.** Review early changes yourself. Measure defects, PR revisions, repeated corrections, review effort and test quality.
4. **Make quality repeatable.** Turn recurring feedback into enforced checks. Qualify specific workflows for unattended delivery.
5. **Scale what works.** Add agents while quality holds. Let proven workflows ship; step in for material ambiguity and exceptions.

Your attention should go to decisions, not dispatching workers. Each worker gets one small task; a stronger reviewer checks its work with project context. Linear tracks the plan, GitHub tracks the code, and `devctl` coordinates execution and records the results.

## Your stack. Your agents.

Any project language. Separate choices for models, coding harnesses and environments. Codex, Claude Code and Antigravity CLI (`agy`) are initial targets. Use isolated environments suited to the project, from Docker to future OpenHands and AWS integrations.

[Task slicing](https://github.com/proxy-hatch/rapid-ship/blob/codex/bootstrap-framework/docs/task-slicing.md) · [Agents and environments](https://github.com/proxy-hatch/rapid-ship/blob/codex/bootstrap-framework/docs/agents.md) · [Quality metrics](https://github.com/proxy-hatch/rapid-ship/blob/codex/bootstrap-framework/docs/metrics.md)

## Try the preview

**Early preview:** scheduling, agent adapters, checks, review, recovery and quality reports are implemented. Automated integration setup and unattended delivery are not ready. Live trials and the trusted approval service must pass before routine human approval can be removed. See [current limits](https://github.com/proxy-hatch/rapid-ship/blob/codex/bootstrap-framework/docs/authority.md).

Requires Python 3.12+, Git and [uv](https://docs.astral.sh/uv/) on a POSIX host. Python runs the controller; your project can use any language.

```sh
git clone --branch codex/bootstrap-framework https://github.com/proxy-hatch/rapid-ship.git
cd rapid-ship
uv sync --locked
uv run devctl --help
```

Continue with [project setup](https://github.com/proxy-hatch/rapid-ship/blob/codex/bootstrap-framework/docs/usage.md). Implementation is in [draft PR #1](https://github.com/proxy-hatch/rapid-ship/pull/1).

Try a small project, share where trust breaks down, or contribute a focused PR. Help make the next agent easier to trust than the last.
