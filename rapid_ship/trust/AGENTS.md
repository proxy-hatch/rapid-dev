# Evidence and authority

| Responsibility | Implementation |
| --- | --- |
| Evidence validation, publication and binding | [evidence.py](evidence.py) |
| Host policy, capabilities, grants and authorization | [policy.py](policy.py) |
| Privileged GitHub writes and uncertain-result reconciliation | [github.py](github.py) |
| Trial and hardening records | [trials.py](trials.py) |

Start authority changes with the [delivery permissions guide](../../docs/authority.md) and the relevant contracts in [models.py](../models.py). Keep exact attempt, head, base, policy, command, environment and controller bindings intact.

Record intended external operations before sending them. Reconcile uncertain outcomes before retries. Keep broker credentials outside candidate environments; broker code must not run candidate hooks, builds or tests.

The store returns typed effect snapshots with nullable results. A completed effect without a result cannot authorize a retry or establish a merge receipt. An empty result dictionary is valid for the generic effect primitive.

Missing authorization or evidence remains a blocker. Measurements and offline simulations do not grant permission or establish live qualification. Preserve rejection and tamper cases when refactoring validation or persistence.

Run `uv run pytest tests/test_evidence.py tests/test_policy.py tests/test_github.py tests/test_github_extended.py tests/test_trials.py` from the repository root. Changes to durable operation state also need `tests/test_storage.py`; use simulated transports for local verification.
