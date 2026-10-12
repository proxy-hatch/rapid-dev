# Typed interview state implementation plan

**Goal:** Give saved setup answers one typed validation module and reject non-integer interview schema versions.

**Approved scope:** Extract interview state and answer validation from `project/configuration.py` into `project/interview.py`. The current membership check accepts JSON `true`, `1.0` and `2.0` as versions 1 or 2. Keep this change independent of metrics and delivery authority.

## Design

`interview.py` owns `InterviewState`, `AnswerRecord`, the versioned question sequences and their known identifiers. Use the existing Pydantic dependency. State requires an actual integer version 1 or 2 and a dictionary of known question identifiers to valid records. Records require exactly `value`, `source` and `recorded_at`; values are non-null JSON, source is `explicit-answer`, and timestamps retain the current `datetime.fromisoformat` acceptance and original spelling.

Preserve unknown top-level state fields on round-trip, as the current reader does. Keep question-specific answer validation, invalidation, configuration updates, safe paths and persistence in `configuration.py`. Existing public functions remain the entry points. Convert validation errors to a concise blocker without exposing stored input values.

## Constraints

- Preserve both v1 and v2 question order and execution-dependent questions.
- Replay answers against current configuration so stale answers do not complete setup.
- Retain provider/model and execution/image/native-consent invalidation.
- Keep model readiness checks, explicit provenance, JSON formatting and read-only `doctor` behavior.
- Do not add a schema migration, generic workflow abstraction or new dependency.
- Do not change persistence transaction semantics or replace installed controllers.

## Tasks

- [x] Add public-interface schema regressions and record the failing baseline before migration. Test writer owns `tests/test_interview_state.py`.
- [x] Add typed state/records and move question metadata into the owning module. Root owns `project/interview.py` and `project/configuration.py`.
- [x] Preserve accepted state round-trips, stale-answer detection, invalidation and rejected-operation state. Extend existing coverage only where needed.
- [x] Update project/test guides and the architecture description.
- [x] Run focused tests, static checks, full repository validation and the documentation build.
- [x] Obtain independent review, resolve findings and prepare the PR.

## Verification

- Before migration, 9 schema-regression cases failed and 15 passed. JSON `true`, `1.0` and `2.0` were accepted through interview reads and answers; `doctor` did not report invalid state.
- Design review confirmed the extraction preserves both question sequences, cross-version answer keys, top-level extensions and timestamp spelling.
- All 49 new public-interface cases passed after extraction. The interview, configuration and onboarding suites passed all 98 cases independently.
- `uv run python scripts/check.py` passed: repository navigation, Ruff lint/format, strict mypy for 28 source files, all 855 tests, isolated controller installation and distribution smoke checks.
- `npm --prefix website ci --no-audit --no-fund` and the documentation production build passed.
- Independent review found no actionable findings. A randomized JSON round-trip check found no coercion or extension loss.
- No external-provider qualification was performed. Installed controllers remain unchanged.
