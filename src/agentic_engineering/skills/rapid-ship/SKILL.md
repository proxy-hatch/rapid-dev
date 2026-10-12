---
name: rapid-ship
description: Use when starting a rapid-ship project, continuing its setup interview, splitting an approved design into tasks, running a supervised trial, or checking readiness for more agents.
---

# rapid-ship

Run `setup`, `start`, or `improve` from a Codex, Claude or Antigravity (`agy`) session. Natural-language requests work too. Ask one short question per turn; use available selectors, otherwise numbered choices. The agent runs commands and saves answers. The user should not need to compose CLI flags, JSON or resource IDs. The interview's harness does not determine the project's worker or reviewer.

Resolve the target project separately from the rapid-ship framework checkout. Read existing project instructions and `.devctl/project.json` when present. Follow its writing and code guidance: concise, plain language and no unused code by default. Projects can use any language; extend devctl itself in Python.

## Setup

Read [guided setup](references/setup.md). Handle local initialization, GitHub and Linear setup in the interview. Ask for destination choices, personal login, permissions and material project decisions; perform the routine work yourself. Reuse prior answers and working connections. Save progress before a login or session restart.

1. Locate the framework checkout from the current repository or the project's gitignored `.devctl/local.json` `framework_root`. If absent, locate the user-selected source. If `.controller` is missing, run `./devctl setup` there to build it; otherwise reuse the installed controller. Do not rebuild or replace a controller while it owns active work.
2. Use the approved design and selected project directory. Initialize with the framework's `.controller/bin/devctl --project PROJECT init --name NAME --design RELATIVE_DESIGN`. Preserve existing choices and edited files. Thereafter run the project's `./devctl` wrapper. Read files listed in `instruction_updates`: add missing references while preserving their custom rules. Root `AGENTS.md` should read `.devctl/AGENTS.md`; `CLAUDE.md` should import it with `@.devctl/AGENTS.md`. Delivery instructions should load `.agents/skills/rapid-ship-engineering/references/ponytail.md` before coding/review and `references/writing.md` from that same skill before commits, PRs, docs or reports. Route other work through that skill's `SKILL.md`. Inspect customized skill entry points too; initialization copies missing files without replacing old text.
3. Run `./devctl interview`. At `repository`, follow guided setup to discover or create the selected GitHub repository, then save its verified `owner/repository`. Connect Linear through that same setup flow. Ask the remaining unanswered questions in ordinary language. Save each answer through `./devctl interview --answer ID --value JSON`, using argument-safe invocation. These are agent operations, not instructions for the user to type.
4. Ask which providers the project may use, then run `./devctl providers --provider NAME` for each selected provider. An installed CLI or model list is not proof of authentication. Follow actual login hints without reading or printing secrets. Distinguish failed authentication from an unverified provider that needs a model probe.
5. Offer exact model IDs from each returned catalog. Select a **small** worker and **large** reviewer; **medium** is optional. Reuse a matching `model_verifications` entry for up to 24 hours; catalog refreshes do not renew it. If the provider needs a new probe, run `./devctl providers --provider NAME --verify --model EXACT` before saving that selection. Antigravity sends a small greeting from an empty temporary directory and may consume provider allowance, including its built-in prompt overhead. Report observed tool activity separately: this is an authentication check, not tool isolation. Preserve provider/model pairs exactly. If authentication or catalog access remains blocked, continue independent setup only. Display labels do not qualify a reviewer; authentication does not verify isolated task execution.
6. Finish environment, checks, resource limits and writing/code preferences through the interview. Preserve exact models and explicit native-execution permission. Keep the setup record's access checks and pending first-PR link separate from configuration and delivery approval.
7. Run `./devctl doctor --json`; it checks configuration, not live integrations. Summarize completed setup, pending first-task checks and actual blockers. Continue into an authorized trial; do not create a throwaway PR just to test integration.

## Start

Read [references/run.md](references/run.md) for task slicing, execution and trust gates. Give each worker one independently checkable leaf task; give the reviewer broader project context. Keep progressing until approved scope is done or an actual blocker needs a decision.

Use [rapid-ship-engineering](../rapid-ship-engineering/SKILL.md) to clarify implementation before slicing, then route coding, TDD, debugging and review. Load its Ponytail rules for coding sessions by default. Never revisit the project's purpose or motivation; record useful shared terms and decisions, and accept that development may reveal new questions.

For the hello trial, walk through setup → one small task → implementation and checks → independent review → GitHub PR → merge under existing authorization → metrics → improvement feedback. Record whether work ran through devctl or directly in the supervised coding session. Do not replace blocked devctl execution with direct host execution without authorization. A manually checked PR does not qualify unattended delivery; report blocked stages honestly.

## Improve

Use `rapid-ship-improve` for framework feedback. Resolve its source backlink while retaining the project's reproduction context. Project-only changes stay in the project; reusable framework fixes become separate reviewed PRs.
