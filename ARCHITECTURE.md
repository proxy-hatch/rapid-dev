# Architecture

rapid-ship is being rebuilt as a Kit that projects vendor into their repositories; the [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes it. This page describes what the repository holds today and how to work on it.

## What exists today

| Part | Where | Status |
| --- | --- | --- |
| `rapid-ship` CLI | `rapid_ship/cli.py` | Prints its version only. Plan 2 adds `init`, `status` and `sync` |
| Atomic file replacement | `rapid_ship/files.py` | Kept for the Kit writers; no caller yet |
| Bounded process runner | `rapid_ship/process.py` | Kept for devctl's check steps; plan 3 moves it into devctl |
| Engineering skill | `rapid_ship/skills/rapid-ship-engineering/` | Guides agents working on this repository until the Kit skills replace it |
| Repository checks | `scripts/` | Navigation and skill aliases, lint, format, types, tests, build and distribution smoke |
| Documentation site | `website/` | Builds the Markdown in this repository; rewritten once the product works |

devctl, the Kit templates, the GitHub Apps and the `rs-` skills do not exist yet. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) builds them in the order its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) sets.

## What was removed

The earlier controller, a local orchestrator also named devctl, was removed on 2026-10-14. Its last version is the git tag `archive/controller-2026-10`. Later plans retrieve the parts in Spec 1's borrow list with `git show archive/controller-2026-10:<path>`. Its runtime trials and designs are in the [archive](docs/archive/orchestrator/README.md). The guides under `docs/` that describe it start with a "Historical" line.

## Develop rapid-ship

```sh
uv sync --locked
uv run python scripts/check.py
```

`scripts/check.py` runs, in order: the navigation check (local Markdown links in maintained `AGENTS.md` files, and skill aliases), Ruff lint and format, mypy and pytest in the checkout, then `uv build` and the distribution smoke in a temporary copy of current source. The smoke installs the wheel that `uv build` made from the source archive into a fresh environment and checks `rapid-ship --version`. For navigation alone, run `uv run python scripts/check_repository.py`. CI runs the same command on Python 3.12 and 3.13.

## Documentation site

The site reads this file, the README and the Markdown under `docs/` directly, excluding maintainer `AGENTS.md` files. Public images come from `asset/public/`. To preview it, use Node.js 22+ (CI uses 24):

```sh
npm --prefix website ci
npm --prefix website start
# Production build, including internal link and anchor checks:
npm --prefix website run build
```

The site pins four patched transitive dependencies while upstream catches up. As of 2026-10-11, the remaining [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) has no published fix; it concerns deeply nested build patterns. Pages serves static output, without a Node server. Recheck `npm audit` when updating the lockfile.

The docs workflow builds PRs and deploys successful `main` builds to GitHub Pages. Repository Pages settings must use GitHub Actions.
