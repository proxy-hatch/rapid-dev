---
name: trust-first-engineering
description: Use when initializing an approved software design with devctl, slicing implementation work into agent task contracts, or preparing environment trials and enforcement before autonomous delivery.
---

# Trust-First Engineering

Consume an approved design; product ideation is outside this workflow. Use the installed, pinned `devctl` controller. Project code cannot authorize upgrading that controller or changing its governing policy.

## Set up

Run `devctl --help` and `devctl doctor --json` in the project. For a new project:

```sh
devctl init --name example --design docs/design.md
devctl interview
devctl interview --answer repository --value '"owner/repository"'
```

Ask the returned question, encode the answer as JSON, and repeat. Persist decisions through `interview`, not edits to its provenance records. Preserve existing answers and user files. Choose worker/reviewer models from the user's available models; the reviewer should be stronger and know the design and project context. Existing authorization persists.

`doctor` separates setup readiness from live autonomy. Read `.devctl/AGENTS.md` and the approved design before dispatch; for an existing root AGENTS file, include a reference to that fragment without replacing existing rules.

## Slice work

Each task has one verifiable outcome, explicit paths, acceptance criteria, named checks, and a dependency only when another change must land first. Assign shared registry/interface changes to one task. Small disjoint implementations may run concurrently; a worker owns its test changes too. Use this exact JSON array shape:

```json
[
  {
    "id": "list-command",
    "title": "Add the read-only list command",
    "description": "Implement the approved list behavior using the existing repository interface.",
    "depends_on": [],
    "owned_paths": ["src/commands/list.py", "tests/test_list.py"],
    "acceptance": ["Lists repository items with the approved output and performs no writes."],
    "environment": "default",
    "base_sha": "REPLACE_WITH_FULL_COMMIT_ID",
    "checks": ["lint", "types", "unit"],
    "timeout_seconds": 1800
  }
]
```

Resolve the full base commit with `git rev-parse HEAD`; use actual configured environment/check names. Save the array to a project-owned task file, then run `devctl decompose --tasks tasks.json` and `devctl run --tasks tasks.json`. Validation is deterministic. An approved dependency must be integrated into the dependent task's base; a status label cannot substitute for its code. Use `resume --help` for an explicit audited base update after integration.

## Match environments and harden

Workspace, execution, and test resources are separate choices. A worktree isolates files, not ports or credentials. For fixed **host** port 8000, declare `exclusive_resources: ["host-port:8000"]` in the environment. For fields outside interview questions, edit the project-owned `.devctl/project.json` environment object and rerun doctor; preserve interview provenance. Container-internal ports can repeat across separate network namespaces. Nonnative execution requires independent clones in this version. Docker memory/CPU budgets are configurable, not capped at 4 GB. Dedicated AWS accounts/stacks require registered resource adapters and any account-wide leases; naming an account does not provision it.

Run representative human-supervised trials before promotion. Retain exact sealed evidence and feedback. Three distinct representative changes, recovery and adversarial evidence, an externally verified human decision, and valid server enforcement are required per capability/recipe/environment/risk class. Missing model authentication, provider compatibility, or an operator authority adapter remains a blocker. Simulated tests and native execution cannot grant unattended authority. `trial`, `harden`, and `github preflight` explain readiness; they never invent signoff.
