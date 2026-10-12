# Project setup

| Responsibility | Implementation |
| --- | --- |
| Init, interview orchestration, configuration files, skill installation and read-only doctor | [configuration.py](configuration.py) |
| Versioned interview questions and typed saved answer records | [interview.py](interview.py) |
| Native provider protocols and explicit model probes | [providers.py](providers.py) |
| Typed observations, retained proofs and model readiness | [provider_evidence.py](provider_evidence.py) |
| Starting checks and writing defaults | [profiles.py](profiles.py), [communication.py](communication.py) |

Use configuration's safe path and JSON helpers for project files. JSON serialization and parent creation stay here; [shared file replacement](../files.py) owns atomic writes and temporary-file cleanup. Reinitialization preserves existing choices and customized instructions; `doctor` only reads state.

Read saved interviews through `InterviewState`. Keep both question sequences, explicit answer provenance and top-level extension fields compatible. `configuration.py` validates each answer against current project choices, invalidates dependent answers and writes state. Stored record validity alone does not mean setup is complete.

Keep discovery, native authentication status and explicit inference verification distinct. Preserve exact model identifiers. Validate new observations before persistence; refresh retains proof timestamps, while a failed explicit probe revokes only its model's proof. Use the shared evidence implementation for both saving and model selection.

Provider protocol tests use fake executables. Discovery must not send inference or start login; agy inference remains an explicit verification command. Keep diagnostics free of raw provider output and credentials.

Decode native CLI JSON responses with [the shared decoder](../protocol_json.py). Keep transport limits, response validation and redacted errors here; malformed initialization must fail before an authentication prompt is sent.

For setup or evidence changes, run `uv run pytest tests/test_configuration.py tests/test_interview_state.py tests/test_onboarding.py tests/test_providers.py tests/test_provider_protocol_json.py tests/test_provider_evidence.py tests/test_provider_setup_integration.py` from the repository root. Resource installation changes also need `tests/test_skill_discovery.py` and `tests/test_project_wrapper.py`.
