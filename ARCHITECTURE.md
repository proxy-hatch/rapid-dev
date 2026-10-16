# Architecture

rapid-ship is being rebuilt as a Kit that projects vendor into their repositories; the [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes it. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) builds the Kit and Setup in six plans, listed in its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md). Plans 1 to 3 are built. This page describes what the repository holds today, how the parts fit together and how to work on them.

## What exists today

| Part | Where | What it does |
| --- | --- | --- |
| `rapid-ship` CLI | `rapid_ship/cli.py`, `rapid_ship/kit/` | `init`, `status` and `sync`: writes the Kit into a repository and keeps it current |
| Kit templates | `rapid_ship/templates/` | `kit.toml` and three layers, `common/`, `python/` and `agnostic/`, which the commands render and the wheel ships |
| devctl | `tools/devctl/`, run through the `devctl` shim | `devctl check`, the one entry point for every check, in the pre-commit hook and in CI |
| This repository's check steps | `tools/devctl/devctl_project/` | `vendored`, `distribution` and `python-3.12`, after the Kit's steps |
| Vendored Kit | `devctl`, `tools/devctl/` (the `devctl` package, `pyproject.toml`, `uv.lock`, `.gitignore`), `.githooks/pre-commit`, `.github/workflows/devctl-check.yml` | Managed files from this repository's own `rapid-ship init`, kept equal to the templates. `rapid-ship` writes `.rapid-ship/kit.lock` itself; it is not a template |
| Seeded files | `.rapid-ship/project.toml`, `gate.toml` and `exceptions.toml`, `tools/devctl/devctl_project/`, `.github/CODEOWNERS`, `AGENTS.md`, `CLAUDE.md`, `docs/AGENTS.md`, `tools/AGENTS.md`, `docs/features/README.md`, `docs/patterns/README.md` | Kit files this repository owns; `sync` never rewrites them |
| File helpers | `rapid_ship/files.py` | Atomic replacement, create-only writes and safe paths for the Kit writers |
| Distribution smoke | `scripts/smoke_distribution.py` | Checks the built wheel and runs its `rapid-ship` in scratch repositories |
| Engineering skill | `rapid_ship/skills/rapid-ship-engineering/`, linked from `.agents/skills/` and `.claude/skills/` | Guides agents working on this repository until plan 6's Kit skills replace it |
| Documentation site | `website/` | Builds the Markdown in this repository; rewritten once the product works |

Nothing here runs as a service. Plans 4 to 6 of Spec 1, Spec 2 and Spec 3 are designed but not built ([Designed, not built](#designed-not-built)).

## The rapid-ship CLI

`rapid-ship` writes and updates the Kit. Run it with `uv run rapid-ship` here. In another repository, run `uvx --from <local checkout> rapid-ship <command>`; once the owner tags a release `v<version>` on `main`, `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>` works too. No release tag exists yet, and the package is not on PyPI. A command exits 0 on success, 1 when a check failed or the repository's state refused the request, and 2 when it could not run.

- `init` vendors the Kit at the top of a git work tree. The work tree must be clean, with no `.rapid-ship/kit.lock` and no branch `rapid-ship/init`. Without `--stack`, a repository with `pyproject.toml` gets the Python stack, and one without it cannot run (exit 2); pass `--stack python` or `--stack agnostic`. `--owner`, `--repository`, `--name` and `--package` fill the template variables. `init` commits the Kit on a new branch, `rapid-ship/init`; a repository with no commits gets the Kit as its first commit on the current branch instead.
- `init` never edits an existing file and runs no project code or git hook. It writes nothing when a managed file already exists. It skips an existing seeded file, a symlink included, and lists it for `rs-setup`. Before it writes, it looks for the tool settings, hooks and workflows the repository already has, such as Ruff or mypy settings, `.pre-commit-config.yaml`, executable hooks in the git hooks directory and files in `.github/workflows/`. After a successful run it lists them, because devctl's checks can overlap or conflict with them. A conflict or failure lists nothing, and a file it cannot read is listed as unreadable. A failed switch, write or commit removes what `init` created and returns to the starting branch.
- `status` compares the repository with the lock and the installed templates, and never writes. It reports each managed file as unchanged, modified or missing, each seeded file whose template changed as `template updated`, and each path under `[kit] exclude` as excluded. A managed lock entry that the installed template no longer matches, or that the installed Kit dropped, is `outdated`; this repository shows it right after a template edit and before `sync --in-place`. A managed template of the installed Kit that the lock does not list yet, such as a file a newer Kit added, is `not installed`. `--strict` exits 1 unless every managed file that is not excluded is unchanged and matches the current template. `--json` prints the report as data.
- `sync` brings the vendored Kit to the installed templates. It replaces unchanged managed files, adds new ones and deletes unchanged ones the Kit dropped. A managed file the project edited or deleted becomes the project's own: sync leaves it as it is, records it as seeded and prints how to give it back with `sync --revert <path>`. It never changes a seeded or project-authored file, and records the new template hash of a seeded file whose template changed. Without `--in-place` it commits on `rapid-ship/kit-sync-<version>` and opens a PR with `gh`; with `--in-place` it writes the work tree only. A failed write restores the work tree.

## Kit templates and layers

`rapid_ship/templates/kit.toml` lists the seeded files, the new-project seeds, the executable files, the optional skills and the template variables. Every other template is managed.

- `common/` holds the files for every stack: the `devctl` shim, `tools/devctl/`, the CI workflow, the pre-commit hook, the settings seeds, CODEOWNERS and the guide skeletons.
- `python/` adds or overrides files for the Python stack: a seeded `pyproject.toml` with the guardrail settings, a source and test skeleton, and its own `project.toml`, root guide and CODEOWNERS. Its CODEOWNERS adds the Python tools' settings files to the Protected set. Where a stack file and a common file share a path, the stack's wins.
- `agnostic/` holds only the stack-agnostic `.rapid-ship/project.toml` today.

A managed file is copied byte for byte, and `sync` replaces it with each new template. A seeded file substitutes `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`, is written once and then belongs to the project. An empty owner or repository renders as `<owner>` or `<repository>` and comments out its line, which only TOML and CODEOWNERS templates allow. The Python stack's new-project seeds, a `pyproject.toml` with a skeleton package and test, are written only when `init` finds no `pyproject.toml`. Each `.claude/skills/<name>` is a relative symlink to `.agents/skills/<name>`; the Kit has no skills yet. A project lists the Kit paths it owns under `[kit] exclude` in `.rapid-ship/project.toml`, and `sync` never touches them.

## The lock

`.rapid-ship/kit.lock` records the Kit version, the stack, the variables and one entry per Kit file: a content hash for a managed file, a link target for a managed symlink and the template's hash for a seeded file. An entry moves from managed to seeded when the project edits or deletes the file, and back through `sync --revert`. The Kit version is the package version. `rapid-ship` writes the lock; nobody edits it by hand.

## devctl and `devctl check`

The `devctl` shim runs devctl with `uv run --project tools/devctl --frozen`, so devctl has its own `pyproject.toml`, `uv.lock` and environment, apart from the project's. It depends only on PyYAML. Today devctl has `--version` and `check`, plus any verbs the project registers in `tools/devctl/devctl_project/`; this repository registers none.

`./devctl check [--tier fast|full] [--json] [--base REV] [--pr-body PATH]` runs the steps below in order and prints one line per step: passed, failed, blocked or not applicable. It exits 0 when every applicable step passed, 1 when a step failed and 2 when a step could not run. A blocked step never counts as passed, and 2 outranks 1. The default tier is `full`.

| Step | Tier | Fails when |
| --- | --- | --- |
| `format`, `lint` | fast | `ruff format --check` or `ruff check` reports a finding |
| `map` | fast | An AGENTS.md link is broken, a maintained directory has no guide, a guide is unreachable from the root guide, a feature file, Pattern file or Rule lacks its fields or names something that does not exist, or a skill lacks its front matter or `.claude/skills` link |
| `exceptions` | fast | A suppression lacks its `rs-exception: EX-<n>` marker and entry in `.rapid-ship/exceptions.toml`, or an entry matches nothing |
| `file-size` | fast | A source file exceeds 500 lines without an exception |
| `kit` | fast | The lock is unreadable, or a managed file that is not excluded is missing |
| `types`, `contracts`, `tests` | full | mypy, import-linter's `lint-imports` or pytest fails |
| `audit` | full | pip-audit 2.10.1 finds a known vulnerability in the locked dependencies |
| `secrets` | full | gitleaks finds a secret in the change's commits, or in the whole history without a base. gitleaks must be on `PATH`; CI installs 8.30.1 |
| `workflows` | full | zizmor 1.30.1 reports a finding in a GitHub Actions workflow |
| `diff` | full | The change removes a test without declaring it, turns an assertion into a tautology, or adds an `autouse` fixture without an exception. It also lists each Protected path the change touches, without failing |
| `evidence` | full, PRs only | The PR body lacks its `## Evidence` section with a command, its result and a `Not covered:` line |

The agnostic stack has no `format`, `lint`, `types`, `contracts`, `tests` or `audit` step. pip-audit and zizmor run through `uv tool run --from <pin>`; they are not dependencies.

The `diff` and `evidence` steps need a change. In CI the base is the PR's base and the body comes from the PR event. Locally, `--base` names the base, or devctl uses the merge base with `origin`'s default branch, and `--pr-body` names a file with the body. Without a base the `diff` step is not applicable, and outside a PR so is `evidence`.

### This repository's own steps

`tools/devctl/devctl_project/` adds three steps after the Kit's:

- `vendored` (fast) runs `uv run --locked rapid-ship status --strict`, so the check fails until the vendored Kit equals its templates.
- `distribution` (full) runs `uv build` in a copy of the files git keeps, then `scripts/smoke_distribution.py`. The smoke checks that the wheel ships every template, installs it into a fresh environment, checks `rapid-ship --version`, and runs `init`, `status --strict` and `./devctl --version` in scratch projects.
- `python-3.12` (full) runs the tests on Python 3.12, the oldest version `pyproject.toml` supports.

### Hook, CI and CODEOWNERS

- The pre-commit hook, `.githooks/pre-commit`, runs `./devctl check --tier fast`. `git config core.hooksPath .githooks` enables it, and `git commit --no-verify` skips it once.
- CI runs `./devctl check --tier full` in `.github/workflows/devctl-check.yml`, a managed Kit file. It runs on each PR, including body edits, on pushes to `main` or `master`, nightly and on demand. It has `contents: read` only, installs gitleaks 8.30.1 checked against its SHA-256, and its job is named `devctl check`, which Spec 1's ruleset requires.
- `.github/CODEOWNERS` is seeded. In Walk its one active line, `* @proxy-hatch`, assigns every path to the owner. Below it, commented out for Flight, is the Protected set: `.github/`, `.githooks/`, devctl, the skills, `.claude/`, every AGENTS.md and CLAUDE.md, `.rapid-ship/`, and the settings files of the check tools. The Harness settings join it with plan 5. The `diff` step reads these lines, commented or not.

`.github/workflows/docs.yml` is this repository's own: it builds the documentation site and deploys `main` to GitHub Pages.

## Dog-fooding

This repository ran `init` on itself, so `devctl`, `tools/devctl/` and `.rapid-ship/` are the vendored Kit. Ruff and mypy check `tools/devctl/` and skip `rapid_ship/templates/`, so devctl is checked once, and pytest imports the vendored copy.

To change devctl, the hook or the CI workflow:

1. Edit the template under `rapid_ship/templates/common/`.
2. Run `uv run rapid-ship sync --in-place`.
3. Commit the template, the vendored copy and `.rapid-ship/kit.lock` together.

Never edit the vendored copy itself. `sync` would record the edited file as this repository's own and stop updating it, and `status --strict` passes such a file. `tests/test_kit_dogfood.py` therefore fails on any Kit-managed file that the lock records as seeded; `uv run rapid-ship sync --in-place --revert <path>` gives it back. `tests/devctl/test_devctl_project_dogfood.py` syncs a template edit in a copy of this repository and checks that this repository's own steps still run. A seeded file, such as `.github/CODEOWNERS` or `tools/devctl/devctl_project/__init__.py`, is edited in place.

## Designed, not built

Spec 1's [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) defines three more plans:

- **[Plan 4, doctor and Agent identity](docs/superpowers/plans/2026-10-14-kit-and-setup.md#plan-4-doctor-and-agent-identity):** `devctl doctor` and `doctor --skills`; optional Agent identity through `rapid-ship app`, the App token code and `devctl as`, the thin command for `gh` and `git push`; and the settings for the Roster and the escalation list, after which the Kit no longer seeds or reads `gate.toml`. It brings over the surviving code of `codex/github-commands`, the old plan 4's branch, which was never merged and is kept as history.
- **[Plan 5, Kit standards and Harness guardrails](docs/superpowers/plans/2026-10-14-kit-and-setup.md#plan-5-kit-standards-and-harness-guardrails):** `devctl hook` and its wiring for Claude Code, Codex and agy; the README.md and ARCHITECTURE.md seeds; the Pattern `task` key; the `SKILL.md` rule; the diff cap; and the Harness settings in CODEOWNERS.
- **[Plan 6, `rs-setup` and `rs-health`](docs/superpowers/plans/2026-10-14-kit-and-setup.md#plan-6-rs-setup-and-rs-health):** the Kit's first skills, with the forked engineering skills and the optional `rs-contribute`. They replace `rapid-ship-engineering`.

Two more specs get their own plans later:

- **[Spec 2, Delivery skills](docs/superpowers/specs/2026-10-16-delivery-skills-design.md):** `rs-design`, `rs-breakdown`, `rs-lead`, `rs-work`, `rs-review` and the tracker mapping notes.
- **[Spec 3, Metrics and gardening](docs/superpowers/specs/2026-10-16-metrics-and-gardening-design.md):** `devctl metrics`, the scheduled metrics Action, Suggested thresholds, project-defined metrics, the Corrections ledger and `rs-garden`.

Decisions with lasting trade-offs are in [ADR 0002](docs/adr/0002-github-gates-merges-reviews-run-locally.md) (GitHub gates merges; Agent identity is optional) and [ADR 0004](docs/adr/0004-team-management-boundary.md) (the team-management boundary). [ADR 0001](docs/adr/0001-subscription-logins-only.md) is this repository's own rule, not product behaviour: its agents use subscription sign-ins only. [ADR 0003](docs/adr/0003-walk-on-bare-sessions-orchestrator-deferred.md) is superseded by ADR 0004.

## What was removed

The earlier controller, a local orchestrator also named devctl, was removed on 2026-10-14. Its last version is the git tag `archive/controller-2026-10`. Spec 1's section 2 lists the parts that later plans reuse, retrieved with `git show archive/controller-2026-10:<path>`. Its runtime trials and designs are in the [archive](docs/archive/orchestrator/README.md). The guides under `docs/` that describe it, such as its `devctl decompose` command, start with a "Historical" line.

## Develop rapid-ship

You need uv, Python 3.12 or later, network access and gitleaks 8.30.1 on `PATH`.

```sh
uv sync --locked
git config core.hooksPath .githooks
./devctl check
```

After changing a template, run `uv run rapid-ship sync --in-place`, then `uv run rapid-ship status --strict`. Run one area's tests with `uv run pytest tests/test_<area>.py`, and devctl's with `uv run pytest tests/devctl`. On a branch, `./devctl check` compares the change with `origin`'s default branch; pass `--pr-body <file>` to check a PR body's Evidence section locally.

## Documentation site

The site reads this file, the README and the Markdown under `docs/` directly, excluding maintainer `AGENTS.md` files. Public images come from `asset/public/`. To preview it, use Node.js 22+ (CI uses 24):

```sh
npm --prefix website ci --no-audit --no-fund
npm --prefix website start
# Production build, including internal link and anchor checks:
npm --prefix website run build
```

The site pins four patched transitive dependencies while upstream catches up. As of 2026-10-11, the remaining [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) has no published fix; it concerns deeply nested build patterns. Pages serves static output, without a Node server. Recheck `npm audit` when updating the lockfile.

The docs workflow builds PRs and deploys successful `main` builds to GitHub Pages. Repository Pages settings must use GitHub Actions.
