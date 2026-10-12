# Typed task snapshots implementation plan

**Goal:** Make SQLite task snapshot fields visible to static checking without changing stored or returned data.

**Approved scope:** Restore the main checkout's `controller.py` to merged `main`, then type task snapshots from `Store` through controller results. Strict mypy currently accepts misspelled keys, invalid states, wrong generation types and unsafe use of nullable fields.

## Design

Define `TaskState` and `TaskSnapshot` in `storage.py`. The snapshot remains a dictionary with its existing nine keys. Keep `spec` as decoded `dict[str, Any]`; `TaskSpec` remains responsible for its schema. Attempt ID, owner and lease expiry remain nullable. Inactive tasks keep the last attempt's identity.

Annotate the existing snapshot builder, both Store getters and `Controller.run`. Type the active/dependency state sets and transition table using the same state vocabulary. Keep `transition(state: str)` as a validated dynamic input. Narrow the cancellation command's attempt ID before constructing its marker path.

A static consumer fixture in `tests/typecheck_task_snapshots.py` checks inferred public return and field types with `assert_type`. Include it in the existing mypy stage through the configured file list. Reuse existing runtime coverage; add focused CLI cancellation tests for the nullable caller.

## Constraints

- Preserve dictionary keys, state strings, nested spec representation and JSON output.
- Do not change the SQLite schema, SQL statements, transactions, lease fencing or recovery.
- Do not normalize or revalidate stored specs during snapshot reads.
- Leave event/effect typing and metrics outside this change.
- Do not replace installed controllers.

## Tasks

- [x] Restore `controller.py` from merged main and confirm the main checkout is clean.
- [x] Capture the strict-mypy baseline through actual Store/controller interfaces.
- [x] Add the snapshot/state types and propagate them through public returns.
- [x] Add static consumer assertions to the shared checks and narrow CLI cancellation.
- [x] Verify active and unclaimed cancellation, plus corrupt active identity rejection.
- [x] Update navigation and document the static contract.
- [x] Run focused checks, full repository validation, documentation build and independent review.
- [x] Record results and prepare the PR.

## Verification

- Baseline: strict mypy accepted all 13 invalid examples through `Store.get_task`, `Store.tasks` and `Controller.run`.
- After implementation, the same probe rejects all 13 examples: three misspelled keys, three invalid states, three wrong generation types and four unsafe nullable assignments.
- `uv run mypy` passed for 30 source files, including static assertions on all three public returns and nine snapshot fields. Ruff lint/format passed.
- The 66 focused storage, CLI and validation-command tests passed. Missing active attempt identity previously raised an uncaught TypeError; the new guard returns a structured invalid-input result without changing task state or creating a cancellation marker.
- `uv run python scripts/check.py` passed: navigation, Ruff lint/format, mypy, all 899 tests, installed-wheel smoke and source-archive rebuild smoke.
- `npm --prefix website ci --no-audit --no-fund` and `npm --prefix website run build` passed.
- Independent review found no actionable issues. It confirmed unchanged storage/controller runtime behavior, the cancellation guard's placement before filesystem changes, and static-fixture coverage in the shared checks.
