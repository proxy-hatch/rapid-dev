# Development maintenance implementation plan

**Goal:** Make ongoing changes easier to verify with consistent formatting, selective lint rules, and one provider-evidence implementation.

**Approved scope:** Recommendations 1 and 2 from the architecture review, accepted with “proceed.” Metrics-based decisions, durable-file consolidation, and attempt cleanup are outside this change.

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

Owned files: new `src/agentic_engineering/provider_evidence.py`, `providers.py`, `configuration.py`, `cli.py`, provider/onboarding tests, and a small glossary of the resolved domain terms.

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

## Delivery

Keep tooling and evidence changes separately reviewable on `codex/development-maintenance`. Do not merge or replace the installed controller as part of this task.
