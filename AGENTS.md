# rapid-ship

This repository builds `devctl`, a local tool that takes an approved design through implementation, review, and delivery. Projects may use any language. Python and Pydantic are implementation choices for `devctl`, not project requirements.

## Commands

- Setup: `uv sync --frozen`
- Full Python/repository validation (same as CI): `uv run python scripts/check.py`
- Navigation only: `uv run python scripts/check_repository.py`
- Tests: `uv run pytest`
- Static checks: `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`
- Build: `uv build`
- Distribution installation check after building: `uv run python scripts/smoke_distribution.py`
- CLI: `uv run devctl --help`

## Find the change

Read the directory guide before editing there; parent instructions still apply. Small resource and reference folders inherit their nearest guide.

| Work | Start here |
| --- | --- |
| Python code, domain boundaries and shared facilities | [Source map](rapid_ship/AGENTS.md) |
| Regression and integration coverage | [Tests](tests/AGENTS.md) |
| Wheel installation and installed-controller smoke checks | [Scripts](scripts/AGENTS.md) |
| User guides, design records and trial evidence | [Documentation](docs/AGENTS.md) |
| Sample task and environment contracts | [Examples](examples/AGENTS.md) |
| Documentation site and public images | [Website](website/AGENTS.md), [assets](asset/AGENTS.md) |
| CI and documentation deployment | [Workflows](.github/AGENTS.md) |
| Agent skill discovery | [Codex discovery](.agents/AGENTS.md), [Claude discovery](.claude/AGENTS.md) |

When adding or moving a maintained directory, update its guide and parent navigation in the same change. Keep one canonical implementation and point to it. Move repeated corrections into types, tests or lint checks when practical; local prose explains the remaining judgment. Build output, caches, installed controllers and worktrees are generated state, not source directories to document.

## Writing

Read `.agents/skills/rapid-ship-engineering/references/writing.md` before writing commits, PRs, documentation or agent reports.

Use plain, concise language in conversations, reviews, plans, designs, specs, and documentation. Lead with the outcome or problem. Explain a term only when the reader needs it. Prefer one precise finding over several vague ones; name the problem, consequence, and file:line. Comments should explain non-obvious behavior, not restate code. Keep exact commands, limits, and safety conditions when they affect a decision.

## Development

- Before coding or review, read `.agents/skills/rapid-ship-engineering/references/ponytail.md`. Use the engineering skill for clarification, TDD, debugging, architecture work and review. Reuse `GLOSSARY.md` and relevant ADRs when present; clarify implementation without questioning the project's purpose.
- Linear records scope, issues, dependencies and responsibility. Rapid-ship selects workers, models, harnesses and environments. Use GitHub for code, checks and PRs; do not mirror tasks into GitHub Issues.
- Connect Linear through its official MCP or API and link the GitHub repository during initial setup. Do not use a third-party Linear CLI. Configuration alone is not proof the connections work.
- Support bring-your-own model and coding harness. Keep model connection, harness, and execution environment separate; validate each combination. Preserve the chosen model exactly and never silently substitute another.
- Own scope slicing: approved design → epics → optional stories → independently checkable tasks. Assign each worker one leaf task with its code, tests, owned paths, dependencies, and stopping conditions. A reviewer checks coverage and boundaries before dispatch.
- Keep tasks small enough to check independently. Promote repeated corrections to enforced checks.
- Work in a `codex/` branch, test meaningful behavior, and get independent review before merging.
- Preserve project choices during upgrades. `doctor` is read-only.
- Track quality before increasing concurrency. Missing metrics are unknown, not zero; agent runtime is not human review time. Metrics never grant authority or increase concurrency automatically.

## Safety

- Validate task fields, paths, dependencies, and environment support before execution.
- Checks and review must match the exact task attempt, head, base, policy, commands, environment, and controller version. A worker's report is not independent verification.
- Record external operations before sending them. Resolve an uncertain result before retrying.
- Worktrees isolate source only. Native execution needs explicit permission and cannot qualify for unattended delivery.
- Never run candidate scripts, hooks, builds, or tests in the GitHub broker's credential context. Keep its credentials and signing keys outside worker mounts.
- No silent increase in permissions, weaker-model fallback, automatic approval, or replacement of the installed controller by candidate code.
- Label simulations and offline tests. Missing credentials or providers block execution; they never count as passing checks. Unattended delivery requires real trials and human approval.

The October 2026 re-scope is described in the [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md). Until its first spec removes the old controller, the rules above still describe the current code.
