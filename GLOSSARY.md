# rapid-ship

rapid-ship helps a team hand software delivery to coding agents, moving a project from supervised to autonomous work as measured quality allows. These terms are the agreed language of the October 2026 re-scope; existing code may use older meanings until it is rewritten.

## Language

### Lifecycle

**Setup**:
The one-time bootstrap of a repository with the Kit.

**Mode**:
The supervision level a project runs under: exactly one of Walk or Flight.
_Avoid_: phase, stage

**Walk**:
The Mode in which a human scrutinises every step and at most five Workers run at once.
_Avoid_: training wheels, supervised trial, start

**Flight**:
The Mode in which agents merge ordinary changes without per-change human approval.
_Avoid_: unattended delivery, autonomy grant

**Pre-flight**:
The gate check that decides whether a project may move from Walk to Flight.
_Avoid_: trial, harden

**Flight lease**:
The time-limited permission for a project to run in Flight. A human grants it; a scheduled check of the metrics renews it.
_Avoid_: permit, grant

**Plan**:
The activity of turning a design or feature into epics, optional stories and tasks. It can happen in either Mode.
_Avoid_: decompose

**Gate log**:
The record of every request to a gate, such as `devctl dispatch` or the merge check, with the answer and the reason. Pre-flight reads it.
_Avoid_: decision log

**Protected set**:
The kinds of change that need human approval in either Mode.

### Repository kit

**Kit**:
What rapid-ship installs into a repository at Setup: a devctl, an AGENTS.md tree, skills and guardrails.

**devctl**:
A repository's own developer CLI, used by people, agents and CI to run and verify that repository. It never runs Worker or Reviewer Sessions.
_Avoid_: controller

**Feature map**:
A per-feature description of what the feature does, where it is entered, what data it touches, how to observe it and how to reproduce it.

**Pattern**:
The one supported way to do a recurring task, with a reference implementation.
_Avoid_: convention, best practice

**Rule**:
A constraint on changes, marked either as enforced by a named check or as advisory.

### Running agents

**rapid-orchestrator**:
The separate project that starts, resumes and cancels Sessions for every Tenant on one machine.
_Avoid_: coordinator, controller, broker

**Tenant**:
One bootstrapped project, as rapid-orchestrator sees it.
_Avoid_: user, organization

**Harness**:
A vendor's coding CLI that runs the agent loop: Claude Code, Codex CLI or Antigravity CLI.
_Avoid_: runner, provider

**Provider**:
The vendor account a Harness signs in to, with its subscription.

**Agent**:
A Harness, an exact model and role instructions, saved under a name.

**Worker**:
The Agent role that implements one task.

**Reviewer**:
The Agent role that independently reviews one change.

**Lead**:
The owner's Session that runs the walk skill: it offers ready tasks, starts Workers through `devctl dispatch`, and routes pull requests to review and merge.
_Avoid_: coordinator, manager

**Session**:
One conversation of an Agent in one workspace, resumable by its ID.
_Avoid_: attempt, run

**Environment**:
Where a Session runs and how it is confined.

### Improving the path

**Correction**:
A change that a human or the Reviewer required of an agent's work.

**Corrections ledger**:
The repository's record of Corrections and of what was done to prevent each repeat.

**Gardening**:
A pass that adds new Corrections to the corrections ledger and proposes a fix for each repeat on the rung that fits it: a safe interface, a check, or both, and a skill or advisory Rule only when neither can carry it.

### Measuring

**Revision**:
One review round on a pull request that ended in changes requested, by the Reviewer or a human.

**Rollback**:
A merged pull request later reverted, or a deploy rolled back, traced to that pull request.

**Alarm**:
A signal that released behaviour breached a budget set during Plan.

### Provider setup

**Provider observation**:
A dated result from inspecting a Harness or explicitly checking a selected model. Discovery alone does not establish model authentication.

**Model verification**:
Evidence that an explicitly selected model satisfied its Harness's verification procedure. An agy verification requires a completed inference response for that exact model.

**Provider evidence**:
The latest provider observation together with retained model verifications. Refreshing discovery does not renew earlier model verifications.

**Model readiness**:
Eligibility to select a model using a recent catalog and the authentication evidence required by its provider. It does not qualify an execution environment or authorize delivery.
