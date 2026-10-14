# rapid-ship

rapid-ship is being rebuilt as a Kit that a repository vendors: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and `rs-` skills. The `rapid-ship` command writes and updates the Kit; nothing runs as a service. The [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes the product, and [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) with its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) describes the work in progress. Today the package provides `rapid-ship init`, `status` and `sync`, and this repository vendors its own Kit: `devctl`, `tools/devctl/` and `.rapid-ship/`. `devctl check`, the GitHub commands and the `rs-` skills are not built yet.

## Commands

- Setup: `uv sync --locked`
- Full Python/repository validation (same as CI): `uv run python scripts/check.py`
- Navigation only: `uv run python scripts/check_repository.py`
- Tests: `uv run pytest`
- Static checks: `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy`
- Build, then check the distribution: `uv build --clear`, then `uv run python scripts/smoke_distribution.py`
- CLI: `uv run rapid-ship --help`
- Check that the vendored Kit equals its templates: `uv run rapid-ship status --strict`
- After changing a Kit template, refresh the vendored copy: `uv run rapid-ship sync --in-place`
- Documentation site: `npm --prefix website ci --no-audit --no-fund` once, then `npm --prefix website run build`

## Find the change

Read the directory guide before editing there; parent instructions still apply. Small resource and reference folders inherit their nearest guide.

| Work | Start here |
| --- | --- |
| The `rapid-ship` package and kept helpers | [Source map](rapid_ship/AGENTS.md) |
| `rapid-ship init`, `status` and `sync`, and the lock | [Kit CLI](rapid_ship/kit/AGENTS.md) |
| Kit templates, and the vendored `devctl` and `tools/devctl/`: edit the template, then sync. `tools/devctl/devctl_project/` is this repository's own | [Kit templates](rapid_ship/templates/AGENTS.md) |
| This repository's Kit settings (`.rapid-ship/`); `rapid-ship` writes the lock, so never edit it by hand | [project.toml](.rapid-ship/project.toml), [gate.toml](.rapid-ship/gate.toml), [exceptions.toml](.rapid-ship/exceptions.toml), [kit.lock](.rapid-ship/kit.lock) |
| Tests | [Tests](tests/AGENTS.md) |
| Validation and distribution checks | [Scripts](scripts/AGENTS.md) |
| Designs, plans, ADRs, trials and the archive | [Documentation](docs/AGENTS.md) |
| Documentation site and public images | [Website](website/AGENTS.md), [assets](asset/AGENTS.md) |
| CI and documentation deployment | [Workflows](.github/AGENTS.md) |
| Agent skill discovery | [Codex discovery](.agents/AGENTS.md), [Claude discovery](.claude/AGENTS.md) |

When adding or moving a maintained directory, update its guide and parent navigation in the same change. Keep one canonical implementation and point to it. Build output, caches, worktrees and state left by the removed controller are generated, not source directories to document.

## Writing

Read `.agents/skills/rapid-ship-engineering/references/writing.md` before writing commits, PRs, documentation or agent reports. Use the terms in [GLOSSARY.md](GLOSSARY.md), and read the [ADRs](docs/adr/) before reopening a settled decision.

Lead with the outcome or problem. Prefer one precise finding over several vague ones; name the problem, consequence and file:line. Comments explain non-obvious behaviour, not the code. Keep exact commands, limits and safety conditions.

## Development

- Before coding or review, read `.agents/skills/rapid-ship-engineering/references/ponytail.md`. Use the engineering skill for clarification, TDD, debugging, architecture work and review.
- Build what the current plan names. Write the test first, and keep each task small enough to check on its own.
- Work on a branch and merge through a PR after independent review. Do not use the `rs/` prefix: Spec 1's `devctl dispatch` counts `rs/` branches as Worker claims.
- Turn a repeated correction into the strongest rule that can carry it: a safe interface, then a check, then a skill or advisory Rule.
- Linear holds specs and tasks; GitHub holds code, checks and PRs. Do not mirror tasks into GitHub Issues. Connect Linear through its official MCP or API, never a third-party CLI.
- Agents sign in with their vendor's subscription, never an API key or a proxy. Use the chosen model exactly as named; if it is unavailable, stop instead of falling back.
- Missing metrics are unknown, not zero, and block promotion. Metrics never grant Flight, and they end it automatically.

## Safety

- Label offline and simulated tests. A blocked, skipped or simulated check never counts as passed; missing credentials block the step.
- A review applies to one head commit. A Worker's own report is not independent verification.
- Record an external operation before sending it. Resolve an uncertain result before retrying.
- Worktrees isolate source only, not processes, credentials or ports.
- No silent increase in permissions, model fallback or automatic approval.
- Never write a GitHub App private key or token to disk, a command line or output.
