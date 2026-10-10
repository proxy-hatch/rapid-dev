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

Read `.devctl/AGENTS.md` and the design. Add a reference to those instructions in an existing root AGENTS file without replacing its rules. Choose available worker/reviewer models; the reviewer should be stronger and know the project. Keep prior user authorization.

## Split and run

Give each task one testable outcome, files it may change, acceptance criteria, environment and named checks. Assign shared interfaces to one task. Add dependencies only when another change must land first.

`decompose` accepts a JSON array of objects with `id`, `title`, `description`, `owned_paths`, `acceptance`, `environment`, `base_sha`, and `checks`; `depends_on` is optional. Use full commit IDs and configured environment/check names. Run:

```sh
devctl decompose --tasks tasks.json
devctl run --tasks tasks.json
devctl metrics sync-github
devctl metrics
```

Integrate dependency commits before running dependent tasks. Use `resume --help` to update a base explicitly. Fix attempts stop at the retry limit; unresolved design choices need a human decision.

## Environments and trust

A worktree isolates source files, not ports or credentials. Reserve fixed host ports with `exclusive_resources`, for example `host-port:8000`. Separate containers may reuse internal ports. Change environment fields in `.devctl/project.json`, then run doctor. Docker budgets are adjustable. AWS accounts/stacks and OpenHands need registered adapters.

Start with one task. Set numeric quality thresholds before the experiment, collect four baseline weeks, and require four passing weeks before raising concurrency. Use the metrics report; sync PR and Actions data from GitHub, and import deployment, human-review and test-tool results with `devctl metrics import FILE`. Missing data is unknown. Reuse correction categories and link recurring fixes to working checks.

Unattended delivery separately requires three human-reviewed changes, recovery/adversarial trials, a trusted approval service and GitHub protection for the selected tools and environment. Simulations and native execution cannot grant it. `trial`, `harden` and `github preflight` report remaining blockers.
