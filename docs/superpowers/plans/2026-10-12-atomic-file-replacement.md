# Atomic file replacement implementation plan

**Goal:** Give mutable JSON writers one atomic replacement implementation and remove abandoned temporary files after failed environment writes.

**Approved scope:** Continue the maintenance refactor after merged PR #21 (`c4091f8`). The concrete issue is duplicated replacement code: configuration cleans its temporary file on failure, while environment ownership and cleanup-progress writers leave theirs behind.

## Design

Add `rapid_ship/files.py` with `atomic_replace(path: Path, content: bytes) -> None`. It creates a private temporary file in the destination directory, writes and flushes all content, fsyncs the file, atomically replaces the destination, and removes the temporary file on failure. Callers own JSON serialization, directory creation and existing path/symlink checks.

Migrate only `configuration._write_json`, `EnvironmentManager._remember` and `_persist_progress`. Preserve existing JSON bytes, file permissions, errors, ownership adoption and observer timing. Keep evidence and policy publishers separate: their no-overwrite, mode and directory-sync guarantees differ from replacement.

## Constraints

- Do not add dependencies, serializers, publication modes or a store abstraction.
- Directory creation stays in configuration; environment persistence still requires an existing owner directory.
- Update `_owned` and notify observers only after a successful ownership write, as before.
- Preserve cleanup-progress in-memory semantics and recovery/reconciliation behavior.
- Sync the file before replacement. This refactor does not add parent-directory fsync or claim power-loss durability.
- Leave immutable evidence/policy writers, trust bindings and delivery permissions unchanged.

## Task 1 — Characterize and reproduce

Own `tests/test_file_persistence.py` and `tests/test_files.py`.

- [x] Reproduce environment temporary-file leaks on injected fsync/replace failures before changing callers.
- [x] Verify failures preserve existing destination bytes, owned-handle state and observer behavior.
- [x] Cover complete byte replacement, private permissions, partial-write failure, fsync failure, replacement failure and missing parent directories through the shared helper.
- [x] Retain existing symlink and recovery coverage; add focused caller assertions where needed.

## Task 2 — Consolidate matching writers

Own `rapid_ship/files.py`, `project/configuration.py`, `execution/environments.py`, source/project/execution/tests guides and `ARCHITECTURE.md`.

- [x] Add the small byte-oriented helper and move matching filesystem steps into it.
- [x] Preserve each caller's serialization, validation and state-update order.
- [x] Update scoped navigation and document the boundary with immutable publication.
- [x] Run focused tests, strict mypy, Ruff, the full shared validation command, documentation build and independent review.
- [x] Record actual results and prepare the bounded PR.

## Review focus

A failed write must not replace a complete existing record or adopt an unpublished ownership record. Temporary cleanup must run for write, fsync and replace failures. Symlink rejection and distinct immutable-publication guarantees must remain intact.

## Verification

- Baseline caller regressions: 6 failed, 5 passed. All six failures were abandoned ownership/progress temporary files after injected fsync or replacement errors.
- After migration: 138 focused tests passed, including configuration, onboarding, environments and the unchanged evidence/policy publishers.
- Ruff lint and format passed; strict mypy passed for 27 source files.
- Independent review found no actionable issues and independently passed all 20 new test cases.
- `uv run python scripts/check.py` passed: repository navigation, lint, formatting, types, all 806 tests, isolated controller installation, wheel/source builds and distribution smoke checks.
- `npm --prefix website ci --no-audit --no-fund` and the documentation production build passed.
- No external-provider qualification was performed. Installed controllers and immutable trust publishers remain unchanged.
