# rapid-ship

rapid-ship is being rebuilt as a Kit that a repository vendors: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and `rs-` skills. The `rapid-ship` command writes and updates the Kit; nothing runs as a service. The [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes the product. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) is built in the five plans of its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md), and [ARCHITECTURE.md](ARCHITECTURE.md) describes what exists today.

Plans 1 to 3 are built: `rapid-ship init`, `status` and `sync`, and `devctl check`. This repository vendors its own Kit, so `devctl`, `tools/devctl/`, `.githooks/`, `.github/workflows/devctl-check.yml` and `.rapid-ship/` come from its templates. Not built yet: `rapid-ship app` and `adopt`, devctl's GitHub commands (plan 4), the `rs-` skills (plan 5) and the Walk flow ([Spec 2](docs/superpowers/specs/2026-10-15-walk-flow-design.md), a draft).

## Commands

- Setup: `uv sync --locked`, then `git config core.hooksPath .githooks`.
- Full check, the same tier CI runs: `./devctl check`. It and `uv run pytest` need network access and gitleaks 8.30.1 on `PATH`.
- Fast check, which the pre-commit hook runs: `./devctl check --tier fast`.
- Tests: `uv run pytest`; devctl's tests only: `uv run pytest tests/devctl`.
- After changing a Kit template: `uv run rapid-ship sync --in-place`, then `uv run rapid-ship status --strict`.
- Documentation site: `npm --prefix website ci --no-audit --no-fund` once, then `npm --prefix website run build`.

## Find the change

Read the directory guide before editing there; parent instructions still apply. Small resource and reference folders inherit their nearest guide.

| Work | Start here |
| --- | --- |
| The `rapid-ship` package, its file helpers and the engineering skill | [Source map](rapid_ship/AGENTS.md) |
| `rapid-ship init`, `status` and `sync`, and the lock | [Kit CLI](rapid_ship/kit/AGENTS.md) |
| Kit templates, including the source of the vendored `devctl`, `tools/devctl/devctl/`, hook and CI workflow: edit the template, then sync | [Kit templates](rapid_ship/templates/AGENTS.md) |
| The vendored devctl, and this repository's own check steps in `tools/devctl/devctl_project/` | [Tools](tools/AGENTS.md) |
| This repository's Kit settings (`.rapid-ship/`); `rapid-ship` writes the lock, so never edit it by hand | [project.toml](.rapid-ship/project.toml), [gate.toml](.rapid-ship/gate.toml), [exceptions.toml](.rapid-ship/exceptions.toml), [kit.lock](.rapid-ship/kit.lock) |
| The secrets step's settings: gitleaks's default rules, plus an allowlist for the placeholder key that a plan document quotes. Protected | [.gitleaks.toml](.gitleaks.toml) |
| Tests | [Tests](tests/AGENTS.md) |
| The distribution smoke that the `distribution` check step runs | [Scripts](scripts/AGENTS.md) |
| Designs, plans, ADRs, trials and the archive | [Documentation](docs/AGENTS.md) |
| Documentation site and public images | [Website](website/AGENTS.md), [assets](asset/AGENTS.md) |
| CI, documentation deployment and CODEOWNERS, which lists the Protected set | [Workflows](.github/AGENTS.md) |
| Agent skill discovery | [`.agents/skills`](.agents/AGENTS.md), [`.claude/skills`](.claude/AGENTS.md) |

When adding or moving a maintained directory, update its guide and parent navigation in the same change. Keep one canonical implementation and point to it. Build output, caches, worktrees and ignored local state are generated, not source directories to document.

## Writing

Read `.agents/skills/rapid-ship-engineering/references/writing.md` before writing commits, PRs, documentation or agent reports. Use the terms in [GLOSSARY.md](GLOSSARY.md), and read the [ADRs](docs/adr/) before reopening a settled decision.

Lead with the outcome or problem. Prefer one precise finding over several vague ones; name the problem, consequence and file:line. Comments explain non-obvious behaviour, not the code. Keep exact commands, limits and safety conditions.

## Development

- Before coding or review, read `.agents/skills/rapid-ship-engineering/references/ponytail.md`. Use the engineering skill for clarification, TDD, debugging, architecture work and review.
- Build what the current plan names. Write the test first, and keep each task small enough to check on its own.
- Work on a branch and merge through a PR after independent review. Never use the `rs/` prefix: Spec 1's `devctl dispatch` counts `rs/` branches as Claims.
- Put each rule that prevents a repeated Correction on the rung that fits its purpose. A safe interface removes structural misuse; a check catches local or stylistic problems; one bad pattern can need both. Use a skill or advisory Rule only for what neither can carry.
- Maintainers keep specs and tasks in Linear; GitHub holds code, checks and PRs. Connect Linear through its official MCP or API, never a third-party CLI.
- Outside contributors cannot see Linear. They use GitHub issues and PRs, and maintainers triage those into Linear. Do not copy Linear tasks into GitHub issues: backlog item PRO-103 covers exposing selected Linear issues on GitHub.
- Agents sign in with their vendor's subscription, never an API key or a proxy ([ADR 0001](docs/adr/0001-subscription-logins-only.md)). agy may run inside another coding session; ADR 0001 records that the owner accepted that risk.
- Use the chosen model exactly as named. If it is unavailable, stop instead of falling back.
- Missing metrics are unknown, not zero, and block promotion. Metrics never grant Flight, and they end it automatically.

## Safety

- Label offline and simulated tests. A blocked, skipped or simulated check never counts as passed; missing credentials block the step.
- A review applies to one head commit. A Worker's own report is not independent verification.
- Record an external operation before sending it. Resolve an uncertain result before retrying.
- Worktrees isolate source only, not processes, credentials or ports.
- No silent increase in permissions, model fallback or automatic approval.
- Never write a GitHub App private key or token to disk, a command line or output.
