# Attempt lifecycle implementation plan

**Goal:** Separate attempt lifetime management from the controller's worker/check/review pipeline without changing delivery authority or normal outcomes.

**Approved scope:** The user said “merged. Next” after the repository guardrails PR, continuing the previously recommended controller lifecycle refactor. Start from merged PR #20 (`7f4c327`). Leave the unrelated main-checkout skill edit alone.

## Design

Add `rapid_ship/execution/attempt.py`. `run_attempt` owns the lease heartbeat, local cancellation, attempt store, error recording, reverse cleanup, evidence publication, final transition and heartbeat shutdown. It calls the controller pipeline once with an `AttemptContext`. That context supplies the store, environment manager, attempt identity and cancellation event, and records environment preparation identities. The pipeline returns `ApprovedAttempt(evidence, artifact)` only after the existing independent checks pass.

`Controller._attempt` supplies configuration and delegates to the lifecycle runner. `Controller._execute_attempt` retains task/model validation, resource acquisition, worker/check/reviewer environments, repairs, metrics and evidence validation. Scheduling, public CLI, storage schema, environment adapters and delivery permissions remain unchanged.

## Constraints

- Renew leases throughout cleanup using a separate SQLite connection.
- Clean all manager-owned handles in reverse order, including preparation that failed before returning its handle.
- If cleanup is uncertain or the pulse observed ownership loss, keep reservations and publish no evidence or terminal transition.
- After successful cleanup, cancellation overrides approval. Check ownership synchronously before publishing evidence.
- Publish receipt, evidence event and fenced terminal transition in that order. The transition releases reservations; do not add an unconditional release.
- Record ordinary pipeline exceptions and partial agent output, then finalize as blocked. Propagate `BaseException` after cleanup.
- Let errors from receipt publication, event writes and final transitions propagate. Always stop/join the heartbeat on exit.
- Preserve cancellation-file sampling, model selections, repair limits, metrics contents and exact evidence bindings.

## Task 1 — Characterize lifecycle behavior

Own `tests/test_attempt_lifecycle.py`; exercise `Controller.run` with real SQLite and local temporary workspaces, simulated runners and controlled failures.

- [x] Verify supervisor and per-attempt cancellation reaches the runner and releases resources only after successful cleanup.
- [x] Verify background lease loss cancels execution, preserves reservations and suppresses evidence.
- [x] Verify uncertain cleanup after valid review retains state and reservations while attempting the other cleanups.
- [x] Verify cancellation during cleanup overrides approval, and finalization failure stops the heartbeat.
- [x] Verify the final synchronous ownership check rejects a lease lost before the pulse observes it.
- [x] Run these characterization tests against the unchanged controller before extraction.

## Task 2 — Extract the lifecycle

Own `rapid_ship/execution/attempt.py`, `controller.py`, the execution/tests guides and the architecture overview.

- [x] Move lifecycle and environment-observation code behind `run_attempt`; keep pipeline operations and validation in the controller.
- [x] Remove duplicate heartbeat shutdown paths and encode the finalization sequence in one place.
- [x] Run characterization and existing controller/environment/runner/process tests, then strict mypy and Ruff.
- [x] Update navigation and architecture references in the same change.
- [x] Run `uv run python scripts/check.py`, the documentation build and independent review; resolve findings and record actual evidence.

## Review focus

Keep lifecycle exception handling distinct from pipeline exception handling. A rejected cleanup or stale lease must never become permission to publish or release resources. Verify event payloads, repair behavior, cancellation and heartbeat lifetime through observable state, without relying solely on internal call-order mocks.

## Verification

Verified locally on Python 3.13.12 on 2026-10-12:

- Eight new characterization cases passed against the original controller before extraction (13.47 seconds).
- After extraction, 202 controller/lifecycle/environment/runner/process tests passed (52.69 seconds).
- `uv run python scripts/check.py` passed: 786 tests in 89.39 seconds, navigation, Ruff lint/format, strict mypy for 26 source files, builds and both installation smoke checks.
- `npm --prefix website ci --no-audit --no-fund` and `npm --prefix website run build` passed, including documentation link checks.
- Independent review found no blocking findings and independently passed the 33 controller/lifecycle tests. The reviewer confirmed that pipeline validation, repair limits, model choices, metrics, evidence bindings and finalization ordering are preserved.
- `git diff --check` passed. Tests used simulated agents and disposable native workspaces with real Git and SQLite; no live provider or delivery trial was performed.

The lifecycle runner uses one outer `finally` for heartbeat shutdown, including failures while opening the attempt store or finalizing it. The controller pipeline returns validated evidence without owning cleanup or publication.
