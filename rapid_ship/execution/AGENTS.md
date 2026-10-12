# Task execution

- [controller.py](controller.py) schedules tasks and runs the worker/check/reviewer pipeline.
- [attempt.py](attempt.py) owns each attempt's lease heartbeat, cancellation, environment receipts, cleanup and finalization.
- [environments.py](environments.py) allocates workspaces, execution environments and test resources.
- [runners.py](runners.py) translates harness protocols without changing the assigned model.
- [engineering.py](engineering.py) loads bundled instructions for worker and reviewer sessions.

Use [shared process execution](../process.py) for bounded subprocess work and [storage](../storage.py) for durable attempt state. Keep environment cleanup and ownership explicit across errors, cancellation and restart.

Use [shared file replacement](../files.py) for ownership and cleanup-progress records. Keep symlink checks here; adopt ownership and notify observers only after publication succeeds.

Preserve separate worker, check and reviewer environments. A successful worker report cannot replace that attempt's checks or independent review. Existing ownership, exact-model and resource limits remain required when changing scheduling or recovery.

When changing a harness, exercise its real adapter with simulated protocol output, including failure and interruption. When changing lifecycle behavior, cover its observable state and cleanup effects; do not infer successful cleanup from a returned message alone.
Keep heartbeats active through cleanup. Uncertain cleanup or lost ownership retains reservations and suppresses evidence; a fresh ownership check precedes publication and the terminal transition.

Run `uv run pytest tests/test_attempt_lifecycle.py tests/test_controller.py tests/test_environments.py tests/test_runners.py tests/test_process.py` from the repository root. Changes to embedded guidance also need `tests/test_skill_discovery.py` and the installed-wheel smoke check.
