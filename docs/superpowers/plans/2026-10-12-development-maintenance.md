# Development maintenance implementation plan

**Goal:** Make ongoing changes easier to verify with consistent formatting, selective lint rules, and one provider-evidence implementation.

**Approved scope:** Recommendations 1 and 2 from the architecture review, accepted with “proceed.” The user then clarified that completion also requires sensible directories and scoped `AGENTS.md` navigation under P6. Metrics-based decisions, durable-file consolidation, and attempt cleanup are outside this change.

**Base:** `0960a7b` includes agy reviewer support and the Docker interview network fix. Preserve both.

## Design

Keep Ruff, strict mypy, pytest, and the existing build smoke checks. Add the missing format gate and only the demonstrated `PGH`, `RUF043`, and `RUF059` rules. Keep intentional regular expressions explicit; do not change their matching behavior.

Concentrate provider observation contracts, evidence merging, freshness, and model eligibility in `provider_evidence.py`. Use the existing Pydantic dependency. Keep provider protocols in `providers.py` and safe filesystem access in configuration's existing helpers. Do not introduce a storage adapter or schema migration.

The public provider commands still return dictionaries. `.devctl/providers.json` retains its provider-keyed shape and original timestamp strings. Optional presentation fields may remain absent in older records. New observations must pass validation before persistence. Provider producers use typed records internally so mypy can check their fields.

`save_provider_records` returns the effective saved reports. The CLI uses that return value instead of saving, reloading, and patching agy-specific fields. Configuration delegates model eligibility to the same evidence module. Existing public configuration functions remain compatible for callers that ignore the new return value.

## Constraints and review focus

- Discovery, native sign-in status, and explicit model verification remain distinct. No new inference or authentication calls.
- agy success requires complete inference evidence for the exact catalog model. Incomplete success reports cannot establish a proof.
- Catalog refresh preserves proof timestamps without renewing them. An explicit failed probe invalidates only its selected model, even if that model left the catalog.
- Both catalog and relevant proof must be no more than 24 hours old. Future and timezone-naive times cannot establish readiness. Assess against one clock value.
- Preserve separate proofs for every configured tier, including agy reviewers and both agy roles.
- Malformed selected-provider records produce actionable blockers. Refresh can repair a malformed record; unrelated saved entries must not prevent that repair.
- Validate the entire incoming batch before writing. Validation failure leaves the existing cache unchanged.
- `doctor` remains read-only. Preserve project choices, path checks, atomic writes, redacted diagnostics, protocol validation, and process cleanup.
- Typed production records do not type-check untyped test doubles. Runtime validation and realistic executable fixtures must enforce the evidence contract.

## Task 1 — Formatting and selective lint

Owned files: `pyproject.toml`, `.github/workflows/ci.yml`, the two unformatted files, affected test patterns and unpacked values, and development command lists.

- [x] Confirm configured lint passes and format check identifies two files.
- [x] Inspect the 17 proposed-rule diagnostics and preserve intentional matching behavior.
- [x] Enable the selected rules and format gate; update documented commands.
- [x] Run format/lint checks and affected tests. No extra tests for mechanical configuration edits.
- [x] Independently review the final diff. Tooling committed as `cfb0407`; the reviewer found no issues and ran 287 tests.

## Task 2 — Typed provider evidence

Owned files: provider evidence, protocols and configuration (now under `rapid_ship/project/`), `cli.py`, provider/onboarding tests, and a small glossary of the resolved domain terms.

- [x] Add behavioral tests for incomplete successful observations and effective saved reports. Both failed against the old implementation before production changes.
- [x] Implement typed observation handling, shared merge/readiness rules, and effective-save results.
- [x] Preserve existing expiry, refresh, per-model invalidation, and protocol coverage.
- [x] Cover exact freshness cutoff, future/naive times, malformed caches, batch rejection without writes, and report/cache equality.
- [x] Exercise fake executable → real provider command → saved proof → model selection → read-only doctor. This is an offline integration test.
- [x] Run focused tests and strict mypy while integrating.
- [x] Run full pytest, Ruff lint, Ruff format check, mypy, and build on the final tree.
- [x] Obtain independent review and resolve actionable findings before completion.

## Verification results

Verified locally on 2026-10-12 with Python 3.13.12:

- Full suite: 744 tests passed in 77.68 seconds, including 44 new evidence cases and two offline setup integration tests.
- Ruff lint passed; all 93 Python files passed the formatting check.
- Strict mypy passed for all 22 source files. `git diff --check` passed.
- The installed-wheel smoke check passed in this isolated worktree. Source distribution and wheel builds passed afterward.
- Independent review found one contradictory success case: agy verification accepted `request_sent=False`. Four regressions failed before the fix and passed afterward. The final review recheck found no remaining actionable issues.

Provider tests used simulated executables. No live provider authentication or inference was performed. The GitHub Actions Python 3.12/3.13 matrix was not run remotely.

## Task 3 — Directory structure and agent navigation

Group related code one level below the package root: `project/` owns setup, provider observations, preferences and defaults; `execution/` owns attempts, environments, harnesses and embedded guidance; `trust/` owns evidence, authority, GitHub writes and qualification. Shared contracts, storage, processes, entry points and existing measurement modules remain at the root. Preserve CLI/JSON behavior and resource lookup paths; update internal imports without compatibility facades.

Add concise `AGENTS.md` guides at maintained directory boundaries. Each guide identifies the owning files, related tests, local constraints and source of truth. Parent instructions apply to descendants; small resource and reference leaves inherit them. Keep canonical skills at their existing package paths and maintainer guidance outside the individual installed skill trees.

Preserve public documentation while introducing local guides. Rename the public `docs/agents.md` guide to avoid case-insensitive collisions with `docs/AGENTS.md`, retaining its website URL. Exclude `AGENTS.md` files from the docs site and serve only `asset/public/` so maintainer guidance is not copied into static assets.

- [x] Move the 13 modules, update ordinary/dynamic imports, and preserve both CLI entry points.
- [x] Run the existing full suite (744 passed) and static checks after the source moves. Independent source review found no issues.
- [x] Complete scoped guides and root navigation; validate their local links and directory coverage.
- [x] Check skill installation and built-wheel resources, and run the documentation production build.
- [x] Review the final navigation and publication changes independently; record verification before committing.

The fresh source-archive installation check exposed missing canonical skill resources: Hatch followed the checkout discovery symlinks first and deduplicated their source directories. Excluding those aliases before traversal keeps the canonical package files. A new `scripts/smoke_distribution.py` reuses the existing installer and installed-controller smoke from a temporary extraction; CI runs it after building. The check failed before the packaging fix and passed afterward. Both archives retain the 22 files in the three skill bundles and their parent maintainer guide. Checkout-discovery tests require a Git checkout because source archives omit those aliases.

The source migration preserves behavior: 744 tests passed in 78.53 seconds, both CLI entry points worked, and independent review found no source issues. All 19 directory guides have valid local links. The documentation production build passed after updating the renamed public guide's links; its `/docs/agents/` URL and both image contents remain unchanged. Maintainer guides are excluded from site output and individual installed skill bundles.

Final Ruff lint, formatting and strict mypy checks passed. Fresh distributions and source-archive installation smoke passed after the guide edits. Independent navigation/publication and packaging reviews found no remaining actionable issues. Verification used Python 3.13 locally; the hosted Python 3.12/3.13 matrix and deployment were not run.

## Task 4 — Remove obsolete source nesting

The user requested removal of the obsolete package name and unnecessary source directory level. Move the package directly to repository-root `rapid_ship/`. Preserve its project, execution and trust areas, bundled resources and `devctl` behavior. Use ordinary `rapid_ship` imports and wheel packaging; no import mapping or compatibility shim is needed.

- [x] Move the package, update Python imports, resources, entry points, type-check paths and six discovery symlinks.
- [x] Merge source navigation into `rapid_ship/AGENTS.md`, remove the redundant source wrapper and update current guides. Keep historical records labeled and generated-project source examples unchanged.
- [x] Verify a refreshed editable install, full tests, static checks, both command entry points, built distribution installation and documentation links.
- [x] Obtain independent review and commit the completed change.

Verification on Python 3.13: 744 tests passed in 83.08 seconds; Ruff lint/format and strict mypy passed. Both `devctl` and `python -m rapid_ship` worked, including imports from outside the checkout. Source-archive installation and the production documentation build passed. All 18 remaining scoped guides and six discovery symlinks resolve. Wheel paths, entry-point metadata and packaged skill bytes match the new layout; the old package is absent. Independent review found no actionable issues. The hosted Python matrix was not run.

## Delivery

Keep tooling and evidence changes separately reviewable on `codex/development-maintenance`. Do not merge or replace the installed controller as part of this task.
