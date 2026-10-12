# Shared strict protocol JSON implementation plan

**Goal:** Give native CLI response parsers one JSON decoder that rejects duplicate fields and nonstandard constants.

**Approved scope:** Extract the existing runner decoder rules and apply them to provider protocol messages and Claude authentication status. Provider discovery currently accepts contradictory `loggedIn` fields by keeping the last value. Runners already reject this ambiguity.

## Design

Add `rapid_ship/protocol_json.py` with `decode_json(text: str | bytes) -> object`. Keep the existing `json.loads` hooks for duplicate fields and `NaN`/`Infinity`/`-Infinity` rejection. Decode one value; callers retain framing, object checks and provider-specific validation.

Migrate `runners._events`, `providers._Protocol.read` and `_claude` status parsing. Keep stored JSON readers and outbound serialization unchanged.

## Constraints

- Preserve JSONL framing, blank-line handling, protocol byte/time limits and cleanup.
- Preserve runner errors and redacted provider diagnostics.
- Preserve exact model/session validation, native login semantics and readiness/evidence requirements.
- Reject malformed authentication initialization before sending a prompt.
- Retain normal stdlib number decoding; do not add new numeric or encoding restrictions.
- No new dependencies, protocol framework or schema migration.
- Fake CLI results are local regression evidence, not live provider qualification.

## Tasks

- [x] Capture provider failures before migration with public fake-CLI regressions. Test writer owns `tests/test_provider_protocol_json.py`.
- [x] Characterize strict parsing of otherwise complete runner responses. Root owns additions to `tests/test_runners.py`.
- [x] Extract the decoder and migrate all three call sites. Root owns `protocol_json.py`, `runners.py` and `providers.py`.
- [x] Update source/project/execution/test guides and the architecture description.
- [x] Run focused tests, static checks, full repository validation and the documentation build.
- [x] Obtain independent review and prepare the PR.

## Verification

- Four Claude authentication cases failed before migration: duplicate login fields and each nonstandard JSON constant produced an authenticated result.
- All 23 new provider cases passed after migration. They cover catalogs, malformed initialization before a prompt, invalid results after a prompt, redaction and retained prior authentication.
- All 136 runner tests passed before extraction, including 18 new cases using otherwise complete responses with valid and invalid metadata.
- `uv run python scripts/check.py` passed: repository navigation, Ruff lint/format, strict mypy for 29 source files, all 896 tests, isolated controller installation and distribution smoke checks.
- `npm --prefix website ci --no-audit --no-fund` and the documentation production build passed.
- Independent review found no actionable issues and passed all 159 provider-protocol and runner cases.
- No live provider qualification was performed. Installed controllers remain unchanged.
