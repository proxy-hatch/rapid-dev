---
name: rapid-ship
description: Use when starting a rapid-ship project, continuing its setup interview, splitting an approved design into tasks, running a supervised trial, or checking readiness for more agents.
---

# rapid-ship

Run `setup`, `start`, or `improve` from a Codex or Claude session. Natural-language requests work too. Ask one short question per turn; use available selectors, otherwise numbered choices. The agent runs commands and saves answers. The user should not need to compose CLI flags or JSON.

Resolve the target project separately from the rapid-ship framework checkout. Read existing project instructions and `.devctl/project.json` when present. Follow its writing and code guidance: concise, plain language and no unused code by default. Projects can use any language; extend devctl itself in Python.

## Setup

1. Locate the framework checkout from the current repository or the project's gitignored `.devctl/local.json` `framework_root`. If absent, locate the user-selected source. If `.controller` is missing, run `./devctl setup` there to build it; otherwise reuse the installed controller. Do not rebuild or replace a controller while it owns active work.
2. Use the approved design and selected project directory. Initialize with the framework's `.controller/bin/devctl --project PROJECT init --name NAME --design RELATIVE_DESIGN`. Preserve existing choices and edited files. Thereafter run the project's `./devctl` wrapper. Read `.devctl/AGENTS.md`; preserve existing root rules when adding its reference.
3. Run `./devctl interview` and ask its next unanswered question in ordinary language. Use prior explicit answers instead of asking again. Save each answer through `./devctl interview --answer ID --value JSON`, using argument-safe invocation. These are agent operations, not instructions for the user to type.
4. Ask which providers the project may use, then run `./devctl providers --provider NAME` for each selected provider. An installed CLI or model list is not proof of authentication. Follow actual login hints without reading or printing secrets. Distinguish failed authentication from an unverified provider that needs a model probe.
5. Offer exact model IDs from each returned catalog. Select a **small** worker and **large** reviewer; **medium** is optional. Reuse a matching `model_verifications` entry for up to 24 hours; catalog refreshes do not renew it. If the provider needs a new probe, run `./devctl providers --provider NAME --verify --model EXACT` before saving that selection. If the CLI cannot confirm the probe restrictions, report the blocker; do not bypass it. Preserve provider/model pairs exactly. If authentication or catalog access remains blocked, continue independent setup only. Display labels do not qualify a reviewer; authentication does not verify isolated task execution.
6. Finish environment, checks, resource limits, repository and writing/code preferences through the interview. Verify issue tracking and code-hosting access, including a linked issue/PR, through the official integrations described in [references/run.md](references/run.md). Configuration alone is not a connection test.
7. Run `./devctl doctor --json`. Summarize configured choices and remaining blockers. Do not call the project ready while required checks are blocked.

## Start

Read [references/run.md](references/run.md) for task slicing, execution and trust gates. Give each worker one independently checkable leaf task; give the reviewer broader project context. Keep progressing until approved scope is done or an actual blocker needs a decision.

For the hello trial, walk through setup → one small task → implementation and checks → independent review → GitHub PR → merge under existing authorization → metrics → improvement feedback. Record whether work ran through devctl or directly in the supervised coding session. Do not replace blocked devctl execution with direct host execution without authorization. A manually checked PR does not qualify unattended delivery; report blocked stages honestly.

## Improve

Use `rapid-ship-improve` for framework feedback. Resolve its source backlink while retaining the project's reproduction context. Project-only changes stay in the project; reusable framework fixes become separate reviewed PRs.
