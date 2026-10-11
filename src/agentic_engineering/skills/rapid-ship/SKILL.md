---
name: rapid-ship
description: Use when setting up a project from an approved design, splitting implementation into small agent tasks, or checking readiness for more agents or unattended delivery with devctl.
---

# rapid-ship

Start from an approved design. Use the installed `devctl`; project changes cannot authorize replacing it.

For feedback that should improve rapid-ship itself, use the `rapid-ship-improve` skill.

Write plainly in conversations, reviews, plans and docs. Lead with the outcome. Explain necessary terms once. Review findings state the problem, consequence and file:line. Keep exact commands and safety conditions.

## Setup

Run `devctl doctor --json`. For a new project:

```sh
devctl init --name example --design docs/design.md
devctl interview
```

Ask the returned question and save its answer with `devctl interview --answer ID --value JSON`. Preserve existing answers and files. The default `custom` profile works with any language; `--profile python-cli` supplies Python defaults. Pydantic is internal to devctl.

Read `.devctl/AGENTS.md` and the design. Add a reference to those instructions in an existing root AGENTS file without replacing its rules. Preserve the project's model and harness choices; check adapter support before dispatch. The reviewer should be stronger and know the project. Keep prior user authorization.

Connect Linear and GitHub during initial setup, before live trials. Select the Linear workspace/team/project and GitHub repository; authenticate through Linear's official MCP or API and the configured GitHub integration. Do not use a third-party Linear CLI. Check access, PR linking, status automation and required GitHub checks; record IDs and results without secrets. Verify the end-to-end issue/PR link with a small setup trial. The CLI interview does not yet perform these integration checks; complete them through the official tools and report missing access instead of claiming setup is ready.

Linear records issues, human responsibility and optional delegation to rapid-ship. Rapid-ship selects the actual worker, harness/model, environment and concurrency slot. In native agent mode, use one rapid-ship app identity for its internal workers; do not turn each process into a Linear user. Native delegation/session handling is not implemented and stays unavailable until its event/session adapter passes verification. Local MCP/API operation does not require native delegation or a public webhook receiver. Show concise progress and results, ask for material decisions, and stop active work when asked to disengage.

## Split and run

Own the translation from approved design to work assignments:

1. Map design requirements to epics. Add stories only when they clarify distinct outcomes. Record material unresolved decisions; stop affected work for a human decision while independent work continues. Use project conventions for routine implementation choices within scope.
2. Split each outcome into the smallest coherent tasks that can be checked and reviewed separately. Keep implementation, its tests and necessary documentation together. Assign shared interfaces to one task; avoid arbitrary file, function or line-count quotas.
3. Record requirement-to-task coverage and dependencies. Have a project-aware reviewer check missing requirements, invented assumptions, ownership conflicts, task size and dependency order before dispatch.

Give a worker one leaf task, normally one PR. Its context contains the outcome, approved design references, relevant interfaces/source, dependency commits, owned paths, exclusions, acceptance cases, named checks, environment and time/retry budget. Include relevant failure cases in acceptance. Give the reviewer the wider design and dependency context as well as the exact change and check results. Do not assign an entire epic to a coding worker.

Keep unresolved decisions and affected task IDs in the saved plan. Exclude those tasks and their dependents from the executable task file; registration makes tasks eligible for scheduling. Include all dependencies of ready tasks, even previously registered ones with unchanged specifications. After a decision, review the affected tasks before adding them. Do not invent a JSON decision-gate field.

Use Linear for the accepted plan, parent/leaf issues and blocking relationships. Give a coding worker one leaf issue; keep its Linear ID with the task and PR. Use GitHub for code and independent PRs targeting the project branch by default. Do not duplicate the plan in GitHub Issues. A task that needs another task's code must use a base containing it. Closing a Linear issue does not prove its code is present.

Use Linear's official MCP or API for authorized planning operations. Read the selected team/project and existing issues first; clarify an ambiguous destination before writing. Save task-to-issue UUID/identifier mappings in the plan and update mapped issues instead of recreating them. Record intended writes and reconcile uncertain results before retrying. Re-read changed issues before updating scope. If the connection is unavailable, prepare a local draft and say it is not synced; do not claim the accepted plan is in Linear.

Re-read mapped issues before dispatch, resume and delivery. Cancellation or a material scope change stops affected work: use `devctl cancel TASK`, inspect the recorded state, and reconcile any open PR. Removing a task from JSON does not cancel its stored attempt. Registered specifications cannot be rewritten; review a replacement task with a new ID, update affected downstream tasks and record which assignment it supersedes. Delayed PR events must not revive cancelled or superseded assignments.

A devctl Linear sync adapter is not implemented yet. `decompose` validates and registers supplied tasks; it does not generate the plan or sync Linear. Prepare a JSON array with `id`, `title`, `description`, `owned_paths`, `acceptance`, `environment`, `base_sha`, and `checks`; `depends_on` is optional. Keep Linear IDs, hierarchy and requirement references in the plan and task descriptions, not unsupported JSON fields. Use full commit IDs and configured environment/check names. Run:

```sh
devctl decompose --tasks tasks.json
devctl run --tasks tasks.json
devctl metrics sync-github
devctl metrics
```

Integrate dependency commits before running dependent tasks. Use `resume --help` to update a base explicitly. Fix attempts stop at the retry limit. Unspecified authentication, authorization, public interfaces or data semantics need a decision; internal naming or layout usually does not.

Stacked PR automation is planned, not implemented. Consider a stack only for a linear dependency chain in one repository. Before enabling it, the broker must track each layer, recheck changed head/base commits after rebases, authorize every lower layer included in a bottom-up merge, and reconcile asynchronous results. Queue admission is not a completed merge. A stack skill alone cannot provide these checks.

## Environments and trust

A worktree isolates source files, not ports or credentials. Reserve fixed host ports with `exclusive_resources`, for example `host-port:8000`. Separate containers may reuse internal ports. Change environment fields in `.devctl/project.json`, then run doctor. Docker budgets are adjustable. AWS accounts/stacks and OpenHands need registered adapters.

Start with one task. Set numeric quality thresholds before the experiment, collect four baseline weeks, and require four passing weeks before raising concurrency. Use the metrics report; sync PR and Actions data from GitHub, and import deployment, human-review and test-tool results with `devctl metrics import FILE`. Missing data is unknown. Reuse correction categories and link recurring fixes to working checks.

Unattended delivery separately requires three human-reviewed changes, recovery/adversarial trials, a trusted approval service and GitHub protection for the selected tools and environment. Simulations and native execution cannot grant it. `trial`, `harden` and `github preflight` report remaining blockers.
