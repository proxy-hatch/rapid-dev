# Repository guardrails implementation plan

**Goal:** Keep agent navigation valid and provide one local command for the Python/repository CI suite.

**Approved scope:** The user accepted recommendation 1 only: check `AGENTS.md` links and skill aliases, and share validation commands between agents and CI. Attempt lifecycle refactoring is excluded.

**Architecture:** `scripts/check_repository.py` checks the working checkout without changing it. `scripts/check.py` runs that checker, static checks, tests and installation/build smoke checks. CI calls the same entry point on Python 3.12 and 3.13. The website keeps its existing Node build workflow.

## Constraints

- Use the standard library and existing development dependencies.
- Enumerate tracked and untracked nonignored Git paths so new guides count and generated state does not.
- Check local Markdown link destinations, not remote URLs or heading anchors. Ignore code examples.
- Derive expected discovery aliases from canonical packaged skills. Both discovery surfaces must use relative symlinks to the matching canonical directory.
- Preserve the install → smoke → build → source-archive smoke sequence.
- Run installation checks in a temporary source snapshot; never replace or reuse a checkout's installed controller.
- Preserve CLI/runtime behavior and the separate documentation deployment permissions.

## Task 1 — Navigation checker

Own `scripts/check_repository.py` and `tests/test_repository_navigation.py`.

- [x] Write and run failing behavioral tests using temporary Git checkouts: broken/moved link, a new guide, code examples, ignored state, and malformed skill aliases.
- [x] Implement clear file/line diagnostics for local Markdown links and alias diagnostics for missing, dangling, wrong, copied, absolute or extra aliases.
- [x] Derive skill expectations from `rapid_ship/skills/*/SKILL.md`; require corresponding aliases in `.agents/skills` and `.claude/skills`.
- [x] Run focused tests and validate this checkout.

## Task 2 — Shared validation entry point

Own `scripts/check.py`, `tests/test_check.py`, `.github/workflows/ci.yml`, root/scripts/tests/.github guides and `ARCHITECTURE.md`.

- [x] Write failing integration tests with temporary checkout fixtures and executable stand-ins: first failure stops the command; packaging sees edited and new source; aliases retain their targets; ignored installations are neither copied nor replaced; temporary files are removed.
- [x] Implement `uv run python scripts/check.py` with named stages and nonzero failure propagation. Run repository navigation, Ruff lint/format, strict mypy and pytest, then setup, installed smoke, build and archive smoke in a temporary source snapshot.
- [x] Replace duplicated Python workflow commands with that entry point; preserve locked setup and the version matrix.
- [x] Document the full command and the focused navigation command. Update the owning guides.
- [x] Run the full command, review independently, resolve findings and record actual results.

## Review focus

Check that ignored local files cannot make broken maintained navigation appear valid; new skill additions require both aliases; Markdown examples do not fail validation; a failed stage stops later actions; and packaging checks test candidate source without mutating existing installations.

## Verification

Verified locally on Python 3.13.12 on 2026-10-12:

- `uv run python scripts/check.py`: 778 tests passed in 69.97 seconds; navigation, Ruff lint/format, strict mypy, checkout-wheel installation, distribution builds and source-archive installation all passed.
- `uv run mypy scripts/check.py scripts/check_repository.py`: both new scripts passed strict type checks.
- `npm --prefix website ci --no-audit --no-fund` and `npm --prefix website run build`: documentation build and link checks passed.
- Independent review found two cases where ignored local state could mask missing checkout files. Four observed failing regressions now cover required ignored aliases, ignored extra metadata, copied extra aliases, and navigation through a symlink to an ignored target. The re-review found no remaining actionable issues and independently passed 34 focused tests.
- The validation command left no `.controller` or `dist` directory in this worktree. Fixture tests also verify that an existing installation remains unchanged and temporary source copies are removed on success and failure.

The shared entry point covers Python/repository validation. The Node documentation build remains in its existing workflow. Navigation checks local Markdown destinations, not HTML/autolinks, remote URLs or heading anchors.
