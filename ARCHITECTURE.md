# Architecture

rapid-ship is being rebuilt as a Kit that projects vendor into their repositories; the [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md) describes it. This page describes what the repository holds today and how to work on it.

## What exists today

| Part | Where | Status |
| --- | --- | --- |
| `rapid-ship` CLI | `rapid_ship/cli.py` | `init`, `status` and `sync`. Plans 4 and 5 add `app` and `adopt` |
| Kit commands | `rapid_ship/kit/` | Template rendering, the lock, and the code behind the three commands |
| Kit templates | `rapid_ship/templates/` | `kit.toml` and the `common/`, `python/` and `agnostic/` trees that the commands render and the wheel ships |
| Vendored Kit | `devctl`, `tools/devctl/`, `.rapid-ship/`, `.github/CODEOWNERS`, `docs/features/`, `docs/patterns/` | This repository's own `rapid-ship init`. `rapid-ship status --strict` and a dogfood test keep it equal to the templates |
| File helpers | `rapid_ship/files.py` | Atomic replacement, create-only writes and safe paths for the Kit writers |
| Bounded process runner | `rapid_ship/process.py` | Kept for devctl's check steps; plan 3 moves it into devctl |
| Engineering skill | `rapid_ship/skills/rapid-ship-engineering/` | Guides agents working on this repository until the Kit skills replace it |
| Repository checks | `scripts/` | Navigation and skill aliases, vendored-Kit check, lint, format, types, tests, build and installed-wheel smoke |
| Documentation site | `website/` | Builds the Markdown in this repository; rewritten once the product works |

The vendored devctl runs `--version` and the project's own verbs. `devctl check`, the GitHub commands, the GitHub Apps and the `rs-` skills do not exist yet. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) builds them in the order its [plan index](docs/superpowers/plans/2026-10-14-kit-and-setup.md) sets.

## The rapid-ship CLI

`rapid-ship` writes and updates the Kit; nothing runs as a service. Run it with `uv run rapid-ship` here, or `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<version> rapid-ship <command>` in another repository. A command exits 0 on success, 1 when a check failed or the repository's state refused the request, and 2 when it could not run.

- `init` vendors the Kit at the top of a git work tree with a clean status and no `.rapid-ship/kit.lock`, and commits it on a new branch, `rapid-ship/init`. A repository with no commits gets the Kit as its first commit on the current branch instead. `init` never edits an existing file, runs no project code or git hook, and writes nothing when a managed file already exists. It skips an existing seeded file, a symlink included, and lists it for `rs-setup`. Before it writes, `init` also looks for the tool settings, hooks and workflows the repository already has, such as Ruff or mypy settings, `.pre-commit-config.yaml`, executable hooks in the git hooks directory and files in `.github/workflows/`. After a successful run it lists them, because devctl's checks can overlap or conflict with them and `rs-setup` will help combine them. A conflict or failure lists nothing, and a file it cannot read is listed as unreadable. A failed switch, write or commit removes what it created and returns to the starting branch.
- `status` compares the repository with the lock and the installed templates. It never writes. `--strict` exits 1 unless every managed file that is not excluded is unchanged and matches the current template.
- `sync` brings the vendored Kit to the installed templates. It replaces unchanged managed files. A managed file the project edited or deleted becomes the project's own: sync leaves it as it is, records it as seeded and prints how to revert it with `sync --revert <path>`. It never changes a seeded or project-authored file. Without `--in-place` it commits on `rapid-ship/kit-sync-<version>` and opens a PR with `gh`; with `--in-place` it writes the work tree only. A failed write restores the work tree.

Templates live in `rapid_ship/templates/`. `kit.toml` lists the seeded files, the seeds for a new project, the executable files, the optional skills and the template variables; every other template is managed. A managed file is copied byte for byte, and `sync` replaces it with each new template. Editing or deleting it makes it the project's own: the next `sync` records that and stops updating it, until `sync --revert <path>` writes the template back. A seeded file substitutes the project name, package, owner and repository, is written once and then belongs to the project. `.claude/skills/<name>` is always a relative symlink to `.agents/skills/<name>`. A project lists the Kit paths it owns under `[kit] exclude` in `.rapid-ship/project.toml`, and `sync` never touches them.

`.rapid-ship/kit.lock` records the Kit version, the stack, the variables and one entry per Kit file: a content hash for a managed file, a link target for a managed symlink and the template's hash for a seeded file. An entry moves from managed to seeded when the project edits or deletes the file, and back through `sync --revert`. The Kit version is the package version. Each release is a tag `v<version>` on `main` that the owner creates.

### Dog-fooding

This repository ran `init` on itself, so `devctl`, `tools/devctl/` and `.rapid-ship/` are the vendored Kit. Ruff and mypy check `tools/devctl/` and skip `rapid_ship/templates/`, so devctl is checked once, and pytest tests the vendored copy. To change devctl, edit its template under `rapid_ship/templates/common/tools/devctl/`, run `uv run rapid-ship sync --in-place`, and commit the template, the vendored copy and `.rapid-ship/kit.lock` together. `tools/devctl/devctl_project/` is this repository's own. `scripts/check.py` runs `rapid-ship status --strict`, which fails until the copy equals its templates. `--strict` passes a vendored file that `sync` recorded as this repository's own after an edit, so `tests/test_kit_dogfood.py` fails on any such file; `uv run rapid-ship sync --in-place --revert <path>` gives it back.

## What was removed

The earlier controller, a local orchestrator also named devctl, was removed on 2026-10-14. Its last version is the git tag `archive/controller-2026-10`. Spec 1's section 2 lists the parts that later plans reuse, retrieved with `git show archive/controller-2026-10:<path>`. Its runtime trials and designs are in the [archive](docs/archive/orchestrator/README.md). The guides under `docs/` that describe it start with a "Historical" line.

## Develop rapid-ship

```sh
uv sync --locked
uv run python scripts/check.py
```

`scripts/check.py` runs, in order: the navigation check (local Markdown links in maintained `AGENTS.md` files, and skill aliases), `rapid-ship status --strict`, Ruff lint and format, mypy and pytest in the checkout, then `uv build` and the distribution smoke in a temporary copy of current source. The smoke checks that the wheel ships every template git keeps, installs the wheel into a fresh environment, checks `rapid-ship --version`, and runs `init`, `status --strict` and `./devctl` in scratch projects, where `init` must leave its commit and a clean work tree. For navigation alone, run `uv run python scripts/check_repository.py`. CI runs the same command on Python 3.12 and 3.13.

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
