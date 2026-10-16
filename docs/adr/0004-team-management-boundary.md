---
status: accepted
---

# rapid-ship stops at the team-management boundary

rapid-ship does for a team of coding agents what a senior engineer, or a team of seniors, does for a team of people. It helps define the architecture, breaks delivery into milestones, epics, stories and tasks, and sets and holds the code-quality bar. It does not run the team. Starting, watching, resuming and handing over agent Sessions, and routing their work to review and merge, belong to the Harness the owner works in: Claude Code, Codex CLI and Antigravity CLI each start subagents of their own. rapid-ship equips that Harness with a Lead brief, skills, instructions and guardrails. How closely the Harness follows them is the Harness's concern.

The same boundary applies to autonomy. rapid-ship reports metrics, records the owner's Suggested thresholds and reports a breach. It never moves a project between Walk and Flight; the owner decides how the project ships.

This supersedes [ADR 0003](0003-walk-on-bare-sessions-orchestrator-deferred.md).

## Considered options

- **Walk on bare Sessions (ADR 0003).** The Lead launched Workers and Reviewers through `devctl dispatch`, tracked each as a Claim and woke on events from `devctl watch`. Rejected after design: stops, Takeovers, Claim cleanup and sandboxed launches made it brittle, and it duplicated what the Harnesses now do natively.
- **rapid-orchestrator**, a service that runs Sessions. Rejected, not deferred: a dedicated service is as brittle and competes with the Harnesses.
- **A Flight lease and a Pre-flight gate.** The lease returned a project to Walk when its metrics regressed or stopped arriving. Pre-flight admitted a project to Flight only after its metrics, its rungs and a set of attack pull requests passed. Rejected: when and how to change the way a project ships is the owner's call, made from the metrics.
- **An Investigator**, an Agent that attributed each rollback and Alarm to the pull requests behind it. Rejected: the basic metrics come from GitHub and git with no model, and an owner who wants rollbacks or Alarms counted adds them as project-defined metrics.

## Consequences

- devctl never starts an agent to do work, never tracks or resumes one, and never pushes, reviews or merges as a step in a flow. Only `devctl doctor`'s probes start a short headless Session, to check a Harness's sign-in and the skills it loads. `devctl dispatch`, `pr`, `review`, `merge` and `watch`, Claims, Release, Takeover, the Session registry and the gate log are dropped. Plan 4 built some of them on a branch that was never merged; that branch is kept only as history.
- Under the optional Agent identity ([ADR 0002](0002-github-gates-merges-reviews-run-locally.md)), agents call one thin devctl command for `gh` and `git push`. It runs only when an agent calls it, never as a step that rapid-ship drives.
- The Lead brief's choice of models is advice. rapid-ship cannot see which model a Harness gave a subagent, so it cannot enforce "no silent model fallback".
- No rapid-ship code caps how many agents run at once; the Lead brief can suggest a cap.
- rapid-ship runs no gate for entering or leaving Flight.
