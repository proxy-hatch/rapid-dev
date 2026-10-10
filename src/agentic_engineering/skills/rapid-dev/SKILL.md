---
name: rapid-dev
description: Use when setting up a project from an approved design, splitting implementation into small agent tasks, or checking readiness for more agents or unattended delivery with devctl.
---

# rapid-dev

Start from an approved design. Use the installed `devctl`; project changes cannot authorize replacing it.

Write plainly in conversations, reviews, plans and docs. Lead with the outcome. Explain necessary terms once. Review findings state the problem, consequence and file:line. Keep exact commands and safety conditions.

## Setup

Run `devctl doctor --json`. For a new project:

```sh
devctl init --name example --design docs/design.md
devctl interview
```

Ask the returned question and save its answer with `devctl interview --answer ID --value JSON`. Preserve existing answers and files. The default `custom` profile works with any language; `--profile python-cli` supplies Python defaults. Pydantic is internal to devctl.

Read `.devctl/AGENTS.md` and the design. Add a reference to those instructions in an existing root AGENTS file without replacing its rules. Preserve the project's model and harness choices; check adapter support before dispatch. The reviewer should be stronger and know the project. Keep prior user authorization.

## Split and run

Own the translation from approved design to work assignments:

1. Map design requirements to epics. Add stories only when they clarify distinct outcomes. Record material unresolved decisions; stop affected work for a human decision while independent work continues. Use project conventions for routine implementation choices within scope.
2. Split each outcome into the smallest coherent tasks that can be checked and reviewed separately. Keep implementation, its tests and necessary documentation together. Assign shared interfaces to one task; avoid arbitrary file, function or line-count quotas.
3. Record requirement-to-task coverage and dependencies. Have a project-aware reviewer check missing requirements, invented assumptions, ownership conflicts, task size and dependency order before dispatch.

Give a worker one leaf task, normally one PR. Its context contains the outcome, approved design references, relevant interfaces/source, dependency commits, owned paths, exclusions, acceptance cases, named checks, environment and time/retry budget. Include relevant failure cases in acceptance. Give the reviewer the wider design and dependency context as well as the exact change and check results. Do not assign an entire epic to a coding worker.

Keep unresolved decisions and affected task IDs in the saved plan. Exclude those tasks and their dependents from the executable task file; registration makes tasks eligible for scheduling. Include all dependencies of ready tasks, even previously registered ones with unchanged specifications. After a decision, review the affected tasks before adding them. Do not invent a JSON decision-gate field.

Use independent PRs targeting the project branch by default. A task that needs another task's code must use a base containing that code. GitHub parent/sub-issues and blocking relationships can mirror the plan; creating them needs an authorized GitHub operation. Closing an issue does not prove its code is present.

`decompose` validates and registers supplied tasks; it does not plan them or create GitHub issues. Prepare a JSON array with `id`, `title`, `description`, `owned_paths`, `acceptance`, `environment`, `base_sha`, and `checks`; `depends_on` is optional. Keep hierarchy and requirement references in the plan and task descriptions, not unsupported JSON fields. Use full commit IDs and configured environment/check names. Run:

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
