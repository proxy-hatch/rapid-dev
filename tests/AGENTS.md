# Tests

Keep tests flat and name them for the behavior or module they cover.

| Change | Start here |
| --- | --- |
| Project setup, providers, model readiness | [test_onboarding.py](test_onboarding.py), [test_provider_evidence.py](test_provider_evidence.py), [test_provider_setup_integration.py](test_provider_setup_integration.py) |
| Task execution and isolation | [test_controller.py](test_controller.py), [test_attempt_lifecycle.py](test_attempt_lifecycle.py), [test_environments.py](test_environments.py), [test_runners.py](test_runners.py) |
| Evidence and delivery authority | [test_evidence.py](test_evidence.py), [test_policy.py](test_policy.py), [test_github.py](test_github.py), [test_trials.py](test_trials.py) |
| Repository validation and agent navigation | [test_check.py](test_check.py), [test_repository_navigation.py](test_repository_navigation.py) |
| Mutable file replacement and persistence failures | [test_files.py](test_files.py), [test_file_persistence.py](test_file_persistence.py) |
| Installed controller and generated projects | [test_controller_setup.py](test_controller_setup.py), [test_project_wrapper.py](test_project_wrapper.py), [test_skill_discovery.py](test_skill_discovery.py) |

Use `tmp_path` for project state and temporary executables for native CLI protocols.
[test_providers.py](test_providers.py) supplies fake executable helpers used by provider integration tests.
Keep simulated provider, Docker, and GitHub results visibly separate from live qualification evidence in [docs/trials](../docs/trials/).
Check rejected operations for unchanged state when that is part of the contract.
Run affected files with `uv run pytest tests/test_<area>.py` from the repository root.
