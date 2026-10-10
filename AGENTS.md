# rapid-dev

This repository implements a local software-delivery controller. The approved design and environment amendment are in `docs/superpowers/specs/2026-10-10-framework.md`.

## Commands

- Setup: `uv sync --frozen`
- Tests: `uv run pytest`
- Static checks: `uv run ruff check .` and `uv run mypy src`
- Build: `uv build`
- CLI: `uv run devctl --help`

## Rules

- Enforced by contract validation: reject unknown fields, unsafe relative paths, dependency cycles, and unsupported environment capabilities.
- Enforced by broker eligibility: review/check evidence must match head, base, policy, recipe, and environment digests. Never treat a worker's report as independently verified evidence.
- Enforced by controller transitions: persist intents before external effects; reconcile uncertain effects before any retry.
- Enforced by environment eligibility: worktrees provide source isolation only. Native execution requires an explicit project grant; sandbox/provider capabilities are independently verified.
- Advisory: keep tasks independently verifiable, grant the narrowest necessary authority, and promote repeated corrections to structural checks.
- Candidate scripts, hooks, builds, and tests never run in a credential-bearing broker context.
- No silent escalation, weaker-model fallback, automatic trust promotion, or self-replacement of the installed controller.
- Human-owned project choices must survive framework upgrades. `doctor` is read-only.
- Work in a `codex/` branch, test meaningful behaviour, and request independent review before merging.

## Scope and evidence

Missing credentials or unavailable external providers are blocked capabilities, never successful checks. Offline tests and simulated providers must be labelled as such. Capability promotion requires real environment evidence and human sign-off.
