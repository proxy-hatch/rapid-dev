# LightDAG runtime trial

**Status: describes deferred or removed work. Nothing here is current behaviour. See the [archive README](../README.md).**

Trial date: 2026-10-11. These are small, reproducible runtime tests, not evidence of production stability.

**Current limit:** stricter checks exposed a Created-container leak when a worker timed out before Docker startup completed. The simple `docker run` adapter is not ready for unattended use. The container never reached worker readiness; it was subsequently removed explicitly. A separate create/ack/start experiment below demonstrates a public-API approach, without claiming a complete resource manager.

## What was tested

LightAgent **0.11.0**, upstream commit `8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f`. Installed the real package and all declared dependencies into `.venv`; imports use the installed package, with no namespace shim or upstream changes. Exact dependency versions are in `dependencies.txt`.

Machine: macOS 15.7.7 arm64, Python 3.13.12, Docker Engine 29.4.0. The existing Docker VM had 8 CPUs and approximately 4 GB RAM. No global Docker setting changed; 4 GB is an observation, not a framework limit. The venv occupied 142 MB. Workers each used a 128 MB container limit and 0.5 CPU.

Pinned worker/verifier image:

```
python@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a
```

`harness.py` is a deterministic external CLI stand-in. It accepts JSON on stdin, runs for the requested duration, starts a child process, and returns a JSON candidate. It is **not a coding model**. Different task model identifiers are passed independently of the harness.

`trial.py` uses LightDAG's public worker factory, verifier, SQLite store, and artifact APIs. Its application adapter supplies subprocess execution, deadlines, process-group/container cleanup, and heartbeat renewal. No private LightDAG API or fork is used.

## Results

Raw outcomes: `results.jsonl`. Per-run raw state and artifacts remain in the original temporary trial directory and are not included in this sanitized bundle; fresh runs recreate `runs/`. The test scripts write `status=pass` when an assertion/diagnostic completes; negative controls below are observed limitations, not passing product behavior.

| Scenario | Observed result |
|---|---|
| Real package installation/import | Passed; 70 packages installed, no credentials supplied to import |
| Two Docker workers, 65 seconds each | Passed in 71.667 seconds including serial review; 276 renewals of four-second leases |
| Reviewer queue | Both two-second reviews passed serially; the second started 2.002 seconds after the first |
| Container isolation | Reviewer verified read-only root, blocked external network, no Docker socket or credential environment variables |
| Worker timeout, native process tree | Both allowed attempts terminated and reaped; run became failed; no artifact |
| Worker timeout, Docker | Initial run ended failed and stopped its children. **Strict rerun failed cleanup:** delayed startup left a Created container; neither attempt reached readiness. See `startup-cleanup-failure.json`. |
| Cancellation, native process tree | Stopped/reaped; persisted cancelled state; measured cancellation return 0.006 seconds |
| Cancellation, Docker | Container removed; persisted cancelled state; measured cancellation return 0.145 seconds |
| Duplicate scheduler, different identities | Second scheduler rejected while first lease active; one dispatch |
| Three repeated resumes after completion | Still one dispatch and one artifact |
| Renewal interruption/loss | Adapter stopped worker; stale result not published; persisted run still running pending recovery |
| Ownership takeover | Old scheduler renewal, old attempt renewal, and stale artifact publication all rejected |
| Scheduler SIGKILL, native worker | Native worker survived scheduler death; adapter startup reaper removed it; restart preserved completed artifact and retried only interrupted task |
| Scheduler SIGKILL, Docker worker | Container survived scheduler death; adapter startup reaper removed it; restart preserved completed artifact and retried only interrupted task |
| Concurrent resume, **same** scheduler identity | Negative control: second resume blocked the live run; original invocation received cancellation through renewal failure |
| Application single-flight resume wrapper | Three concurrent requests joined one run; one dispatch, successful artifact |
| Cancellation during plain CallableVerifier | Negative control: run marked cancelled immediately, but verifier continued for its remaining 1.987 seconds; no publication |

Completed tasks survived scheduler recovery with the same artifact hash and one attempt. Interrupted tasks had two attempts. In both crash tests the scheduler was an actual separate process killed with SIGKILL, not a simulated store close.

## What the integration owns

- Renew both scheduler and attempt leases across worker execution, review queue, review, and publication. The factory's `create`/`release` lifetime covers those stages.
- Enforce worker and reviewer deadlines and stop their subprocesses/containers. A token or Python timeout alone does not kill arbitrary child processes.
- Reap orphan workers after a scheduler crash, using persisted resource identities and ownership checks before redispatch. The probe reaper is intentionally small; production needs durable identities, PID-reuse protection for native processes, and safe multi-owner reconciliation.
- Admit only one active invocation per run in a scheduler process. The tested single-flight wrapper uses only public APIs. Give separate scheduler processes unique identities.
- Handle renewal failure as a stopped attempt awaiting recovery. Native persisted status did not immediately become failed after that loss.
- Give reviewer subprocesses the same cancellation supervision as worker subprocesses. Plain `CallableVerifier` has a timeout but does not observe run cancellation itself.

A long fixed lease is also valid for hard-bounded attempts, as prior probes showed. It must cover worker execution plus review queue, review, finalization and margin; it increases the wait before crash recovery. The runtime trial instead used renewable leases to exercise faster recovery.

The tested adapter is ordinary integration work, not evidence that LightDAG itself supplies Docker lifecycle management. It currently lives only in this trial directory.

## Reproduce

From an isolated temporary checkout:

```sh
git clone --branch v0.11.0 --depth 1 https://github.com/wanxingai/LightAgent /tmp/rapid-dev-lightagent-v011-research
git -C /tmp/rapid-dev-lightagent-v011-research rev-parse HEAD
uv venv --python 3.13 /tmp/rapid-ship-lightdag-trial/.venv
uv pip install --python /tmp/rapid-ship-lightdag-trial/.venv/bin/python /tmp/rapid-dev-lightagent-v011-research
docker pull python@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a
/tmp/rapid-ship-lightdag-trial/.venv/bin/python /tmp/rapid-ship-lightdag-trial/trial.py
/tmp/rapid-ship-lightdag-trial/.venv/bin/python /tmp/rapid-ship-lightdag-trial/edge_cases.py
```

Scripts require `docker` on PATH and a working Docker daemon. Test containers have unique `rapid-ship-lightdag-*` names and the label `rapid-ship.trial=lightdag`. Only the individual test task directory is mounted; no host secrets or Docker socket are mounted. Network is disabled. Native tests are controlled subprocess tests, not a sandbox claim.

A single case can be selected with `--case long_run`, `--case container_crash_recovery`, or another key in `trial.py`.

## Live agy smoke

`live_agy.py` is separate from deterministic results. It runs one supervised no-tool coding prompt through LightDAG with the installed native `agy` CLI and exact requested model `gemini-3.7-flash-high`. It uses existing host authentication without reading/copying credentials. Generated code is verified in a separate restricted Docker container. Observed result: the model stage returned exit 0 / SUCCESS and valid code. The initial LightDAG run failed because both reviewer attempts exceeded its original 10-second Docker-command allowance during shared Docker contention. The same candidate then passed independent Docker verification in 8.517 seconds (`live-candidate-verification-first.json`). Rechecking the copied bundle passed in 10.695 seconds (`live-candidate-verification-bundle.json`). Neither check made another model call. This is **model-stage success plus later verification**, not an end-to-end pass. Preserve `live-agy-initial-result.json`, `live-agy-failure-diagnostics.json`, and both labeled verification records together. Each original verifier recorded TimeoutError. Docker contention was observed concurrently; its causal contribution was not isolated. The original fixture retried once (two actual model calls); the current smoke script limits new runs to one attempt and allows 120 seconds for container startup/execution.

Flags: `--sandbox --disable-slash-commands --model gemini-3.7-flash-high --print-timeout 90s --output-format json`. The conflicting `--mode plan` combination is omitted. The adapter checks process exit, SUCCESS status, one turn, canonical conversation UUID, and response schema. This JSON output does not report the selected model, so the record distinguishes explicit model selection in argv from model attestation.

The probe command helper was also tightened to kill its subprocess group on cancellation/timeout; a dedicated cancellation regression check passed (`helper-cleanup-result.json`). A leftover Created verifier container from the original timeout was explicitly removed.

This is not a container-authentication test, unattended tool-permission approval, or a full agy protocol/conformance trial. Model calls require existing authorized authentication; deterministic runtime tests do not.

## Assessment

LightDAG is a viable foundation for a single-machine orchestration pilot. The tested public APIs can support long external CLI work, independent verification, task retry, leases, and crash recovery without an upstream fork. The 60-second default lease is not a disqualifier.

Adoption still requires an owned harness/environment adapter with the responsibilities above. The stricter startup-cleanup failure means the current simple adapter cannot support an unattended-readiness claim. Production readiness additionally needs longer fault-injection/soak tests, disk-full/SQLite contention tests, resource reconciliation after host/Docker restarts, and real tool-using harness trials. These short probes do not establish production stability or a stronger model reviewer's coding quality.

## Upstream evidence

Observed runtime outcomes are in local logs. Source claims refer to the pinned version:

- [Scheduler batching, renewal, cancellation and worker lifecycle](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/scheduler.py)
- [Public lease renewal, expiry and stale-attempt checks](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/store.py)
- [Worker factory API](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/worker.py)
- [Verifier timeout behavior](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/verification.py)
- [v0.11.0 release](https://github.com/wanxingai/LightAgent/releases/tag/v0.11.0)

## Upstream tests and assertion audit

The pinned upstream DAG suite passed **21 tests, zero skips/deselections, in 19.03 seconds** with pytest 8.4.2. These are byte-identical copies of `test_lightdag.py`, `test_dag_store.py`, and `test_dag_process_recovery.py`, run away from the checkout with isolated Python/importlib mode. Both the test process and its recovery subprocess use the real installed package. Source hashes, command, and import path are recorded in `upstream-dag-tests.json`; stdout, stderr, and JUnit XML are preserved.

The suite covers dynamic decomposition, parallel children, repair, integration, verification gates, artifact tampering, permissions, store fencing/idempotency, and recovery. This is a focused subsystem suite, not broad package coverage. No numerical source-line coverage was measured. For comparison, the parallel AstraBox investigation reported 4,405 passed, 38 skipped and 218 deselected, plus a macOS `/proc` assumption failure and Node-install timeout in broader testing. Those counts have a different scope and were not rerun here; the count difference alone does not decide readiness.

```sh
uv pip install --python /tmp/rapid-ship-lightdag-trial/.venv/bin/python 'pytest>=8,<9'
/tmp/rapid-ship-lightdag-trial/.venv/bin/python /tmp/rapid-ship-lightdag-trial/run_upstream_dag_tests.py
/tmp/rapid-ship-lightdag-trial/.venv/bin/python -m pytest -q /tmp/rapid-ship-lightdag-trial/test_probe_guards.py
/tmp/rapid-ship-lightdag-trial/.venv/bin/python /tmp/rapid-ship-lightdag-trial/reviewer_cleanup.py
```

`test-dependencies.txt` includes test-only dependencies; install stdout/stderr are retained. The **13 probe guard tests passed**: Created/Exited containers are not absence, Docker daemon/permission/timeout errors cannot count as cleanup, only an explicit missing-container response counts, failed diagnostics propagate nonzero exit, and a failed or malformed verifier response cannot print a green exit. Negative controls now assert their expected observations and propagate failures.

Running reviewer cancellation and timeout were separately tested with actual native subprocess trees and Docker containers. All four stricter cases passed; no artifacts were published. This validates the revised cancellation-aware verifier adapter, not native `CallableVerifier` behavior. Container reviewer timeout tests wait for a fresh readiness marker on each attempt before starting the execution deadline.

The stricter worker timeout rerun failed under startup contention and is deliberately retained in `container-cleanup-rerun.stdout`. Running-worker cancellation and Docker scheduler-crash recovery passed the stricter absence check. The initial timeout fixtures did create child processes, as their saved PID files show; the later failing startup case did not.

## Small provisioning experiment

`provisioning_gate.py` separates `docker create` from `docker start`, persists an atomic resource intent, and waits for an actual create acknowledgement before starting work. Cancellation before acknowledgement retains the request long enough to learn its outcome and remove the acknowledged container. A missing acknowledgement marks the task blocked; repeated resume cannot create another resource. Resource intent reloads after adapter reconstruction. Even explicit task unblocking cannot bypass an unresolved resource intent.

All three provisioning experiments passed (1.838s, 1.818s, and 1.666s). The tests inject delayed acknowledgement from a **real Docker create**. They exercise cancellation before acknowledgement, missing acknowledgement plus repeated resume/adapter reconstruction, explicit reconciliation after acknowledgement, and cancellation of a running container with a child in a separate process session. This is about 100 lines of adapter logic plus focused tests, using public APIs and no upstream fork.

It does not solve process death during an uncertain create, lost acknowledgement after host restart, multi-owner reconciliation, power-loss durability, or resource garbage collection. If an outcome remains uncertain, an empty inspect response alone is not accepted as cleanup and automated redispatch stays blocked. A production lifecycle manager remains material work; AstraBox may save that work if its corresponding behavior passes. This experiment is separate from the simple adapter that failed and does not erase the counterexample.

The probe files evolved during the trial. Earlier observations remain in the append-only results; the frozen final scripts include the stricter checks and separate provisioning experiment. No full long-run/model rerun was performed after those targeted changes. Diagnostic `status=pass` means the stated control was captured or asserted; it does not turn an intentionally blocked/failed product outcome into a feature pass.
