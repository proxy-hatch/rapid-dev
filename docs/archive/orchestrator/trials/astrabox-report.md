# AstraBox trial — 2026-10-11 Asia/Taipei

**Status: describes deferred or removed work. Nothing here is current behaviour. See the [archive README](../README.md).**

Status: bounded trial complete. Ordinary sessions, idempotency, disposal, completed-session restart and orphan cleanup passed. Active-turn recovery failed for the tested Codex profile. This is a small integration trial, not production certification.

## Exact software

- AstraBox release `v0.1.5`, commit `a84cc2b53183702198a87fa7f04fddba2555ff87`.
- Published server OCI index digest `sha256:d9f6cc151778bee4b2958676d11e255d68275382179f29559ca0fd8a7a62e978`.
- Published Codex sandbox native linux/arm64 manifest `sha256:84ea4d3d955171d34aa463de55d4e5e20c46295570e101de3e2e464c26233fde`; 3,504,539,079 compressed bytes / 95 layers. Local image inspection confirms linux/arm64, image ID `sha256:334004e55aee27b11e7812b38f49f6d9fa2af307fd306af0424ce405947831ea`, unpacked size 8,680,093,515 bytes.
- Server image has LiteLLM 1.99.0; external host gateway trial also pins 1.99.0.
- Docker Engine 29.4.0, Compose 5.1.2, OrbStack Linux aarch64. VM allocation observed 3.893 GiB and 8 CPUs. Host 16 GiB. This allocation is adjustable and is not a product limit.

## Isolation and changed trial configuration

No user home, SSH, GitHub, cloud, or live model credential is supplied to trial workers. The platform service has the documented Docker socket mount because it creates sandboxes. Worker mounts are inspected separately before claims about isolation.

Initial topology used published Compose services: PostgreSQL, Redis, AstraBox plus embedded OpenSandbox/channel gateway/LiteLLM, and sandbox network edge services. Unique Compose project, host ports, state/database volumes, and secret directory prevent collisions. Trial-specific service memory caps are in `limits.yaml`.

Initial embedded LiteLLM startup drove the capped server to roughly 1.5 GiB and caused severe VM contention. This is a resource-confounded observation, not evidence of upstream failure. We stopped only trial services, then used the documented external-gateway configuration to run LiteLLM in an isolated host Python venv. OpenSandbox and worker containers remain real Docker services. No global Docker setting or unrelated container was changed. At first API readiness after moving the gateway, server memory was approximately 310 MiB.

All inference comes from `model_stub.py`, a deterministic local tool-call generator. The actual harness and runtime are real; this does not test model coding quality or real provider compatibility. Only synthetic keys are used. Because the external gateway uses unique port 18100 and the protected credential gateway explicitly accepts only ports 80/443, `ASTRABOX_SANDBOX_CREDENTIAL_VAULT=false` is set for this test. It does not validate protected credential delivery. A standard-port proxy is the documented way to retain protection.

## Setup findings

- On this Mac/OrbStack host, the documented host socket group command yields group 20 but the Linux socket is group 0. `DOCKER_GID=0` resolves the permission-denied startup failure. This is a deployment configuration mismatch, not a session execution failure.
- OrbStack bridge gateway is 192.168.215.1 rather than the Compose default 172.17.0.1. `ASTRABOX_PUBLISH_HOST_IP` was set to the observed gateway.
- Fresh installation seeds two sample Agents with prepared capacity 1. We set capacity 0 through the API to avoid unrelated prewarming in the trial.
- API creates a Session asynchronously and returns a durable ID before allocation completes. A turn during `CREATING` is rejected with retryable 409 `SESSION_BUSY`, rather than pretending it ran.

## Upstream validation

Command from pinned checkout: `../venv/bin/python -m pytest -q`.

Result: **4,405 passed, 38 skipped, 218 deselected, 72 subtests passed, 1 failure, 1 setup error** in 429.25 seconds.

Failure: `test_filesystem_type_reads_the_longest_matching_mount` assumes Linux `/proc/mounts`; on macOS `_filesystem_type(Path('/'))` returns None. Setup error: AI-SDK wire-schema test's Node toolchain acquisition exceeded its 60-second setup timeout. Neither is demonstrated as a product runtime failure. Default suite excludes live e2e, PostgreSQL, Mongo, and OpenSandbox integration markers.

Pinned release CI is green: https://github.com/Colton-z/AstraBox/actions/runs/37926971651 . Jobs include backend checks/tests, frontend, distribution, snapshot helpers, database suites, and e2e typechecking. No runs were returned for the separate `e2e.yml` workflow. Therefore green CI is useful evidence, but not proof that this release's live harness lifecycle was exercised end-to-end.

## Original local files (not all bundled)

The sanitized bundle uses the capture helpers documented in its `README.md`. The following list describes original local trial files; raw logs, checkout and environments are not bundled.

- `compose.py`, `trial.env`, `limits.yaml`: scoped deployment commands/configuration.
- `gateway.yaml`, `model_stub.py`: external gateway and deterministic inference.
- `api_probe.py`, `send_turn.py`: public API trial driver.
- `pytest.log`: full local unit-test outcome.
- `pull.log`, `codex-pull.log`, `start*.log`, `gateway.log`, `api-probe.log`: deployment logs.
- `trial-agent.json`, `trial-session.json`, `session-state.json`: observed API results.

## Required rapid-ship work regardless of built-in lifecycle

AstraBox can own native harness/session/container lifecycle through HTTP, with a separate rapid-ship process owning design-to-task slicing, Linear synchronization, worker/reviewer assignment, task budgets, checks, metrics, and GitHub delivery. `agy` requires a real engine adapter; documented adapter seams are not proof of an existing adapter. A model must support the harness's wire protocol/tool calling; an OpenAI-compatible label alone does not prove compatibility. Default Git credentials can be materialized in workers, so an independent GitHub write/merge broker remains needed for our privilege model. Per-environment CPU/memory limits are not offered by the current schema; these must be enforced at the deployment/provider boundary.

## Observed runtime results

| Check | Observed result |
|---|---|
| Real external harness | Native ARM64 Codex CLI 0.160.0 ran through AstraBox's own adapter. The deterministic model emitted real tool calls. agy was not tested. |
| Two sessions | Separate managed containers; first session wrote `/workspace/trial-source.txt`, second did not see it. Worker had only its OpenSandbox runtime volume, no host credentials/home/socket mount, and was not privileged. Its supervisor starts as root; Codex writes as user `agent`. |
| Long turn | Corrected probe completed a 65-second shell command after 68.2 seconds. Output was `startend`. |
| Duplicate input | Same client message ID returned the same command/input IDs. Replaying the 65-second command produced one `startend`, not two executions. Duplicate conversation-create idempotency key also returned one session ID. |
| Turn interrupt | Accepted, but the shell process tree launched by asynchronous `exec_command` remained alive. Session reports `last_turn_status=COMPLETED` **and** `last_turn_terminal_reason=interrupted`. An integration must read both. |
| Strong cancellation | DELETE Session returned `deleted=true`; independent Docker inspection confirmed its container no longer existed. This is the tested path that stops all its children. It disposes of the session/container, so callers must preserve any wanted artifacts first. |
| API service restart | Restarted the actual platform container after the long turn. Readiness returned after 8.05 seconds in the probe. Existing source, `startend`, and the original native Codex conversation filename/ID survived. A subsequent tool call wrote `resumed.txt`. This tests a completed-session restart, not in-flight recovery or a destroyed worker. |
| In-flight controller SIGKILL | Worker completed the external effect once (`startend`), but the recovered turn was FAILED with `observed conflicting engine turn anchor for the active turn` (post_dispatch). Same input retry retained its identifiers. This is a recovery failure, not a passing crash-recovery result. |
| Late allocation | A client timeout during a cold image pull left an extra, unclaimed container after a successful replacement was allocated. AstraBox has an installation-scoped sweep with a 600-second grace. The automatic sweep removed the container at 20:42:48 UTC (created 20:32:46), cleaned its sidecar/volume, and reported one ownerless box reaped. Independent inspection reported no such object at 20:42:58. Only the sweep interval was shortened from 300 to 5 seconds; the 600-second grace was unchanged. |

`lifecycle2-results.json` and `restart-results.json` hold the HTTP responses, timestamps and independent Docker/file checks. The first long-job attempt is excluded: our stub failed to parse a tool session ID and ended the model turn early. The corrected stub, not a product change, produced the successful 68.2-second run.

We did not test review quality, live model inference, real provider authentication, the agy adapter, a reviewer approval wait, destroyed-worker source restoration, malicious-worker escape resistance, arbitrary backend providers, or multi-owner execution fencing. Idempotent client retries are not proof of all those properties.

## Resource conclusion

After moving LiteLLM to the host, the platform and real session tests ran without the earlier observed memory contention. A snapshot with three workers (including the late-allocation orphan) showed about 323/361/345 MiB per worker, 381 MiB for the platform, and much smaller database/edge services. These are idle/light shell workload samples, not capacity measurements; no Docker memory ceiling or production concurrency recommendation follows. Each worker's configured memory limit was 4 GiB, despite much lower observed usage. Host gateway memory is outside the Docker figures.

## Selection judgment

The evidence supports AstraBox as a credible managed-runtime candidate. Its low adoption does not negate working native sessions, durable restart, idempotency and strong disposal. Its broader test suite is useful evidence, while this young release and the lack of observed release e2e runs leave maintenance and integration risk.

Compared with LightDAG plus a small Docker/CLI adapter, AstraBox already owns more of the difficult lifecycle: uncertain allocation, background recovery, native conversation attachment, container inventory and garbage collection. A roughly 100-line create/start adapter can fix a specific cancellation race without yet solving process death, lost acknowledgements, ownership conflicts or garbage collection. It would be misleading to call those remaining obligations trivial. The automatic orphan result passed and is meaningful evidence of lifecycle work already supplied by AstraBox.

AstraBox remains my preferred candidate to investigate for managed Docker lifecycle, because replacing its allocator, inventory, completed-session attachment and cleanup with a small adapter would leave substantial work unowned. The active-turn crash failure is an adoption gate: I would not lock it in as the low-touch default until that failure is understood and a repeatable test passes. Its model gateway, database, runtime helpers and engine protocol are a real operational/integration cost. Keep rapid-ship planning and delivery outside its HTTP boundary so it can be replaced.

LightDAG remains the simpler embedding seam for arbitrary worktree, CLI, OpenHands and AWS-resource workers. Choosing it means consciously owning and testing that lifecycle/resource manager. Choosing AstraBox means writing compatible EngineAdapter/SandboxProvider integrations where its existing OpenSandbox profile does not fit. Neither framework allocates dedicated AWS test accounts or enforces our independent reviewer/GitHub merge privilege model by itself. Neither makes the required agy integration proven merely by having an extension interface.

## Crash-recovery finding

The platform received a real running turn, then its container was killed with SIGKILL (exit 137) and started again. The worker container stayed alive. Its external shell effect completed exactly once, and the replayed client message ID was preserved, but the managed turn failed with `observed conflicting engine turn anchor for the active turn`. The result is safe against a false success claim, yet it leaves the controller with completed side effects and a failed status. A generic retry on FAILED would be unsafe. This failure is not explained by the model stub's earlier parser error: the corrected stub had already passed the long-job test, and the error comes from AstraBox's native turn-anchor reconciliation.

The short control waited an extra 3 seconds before SIGKILL and did not replay the input. Its external effect also completed once, but the managed turn failed with `engine recovery unrecoverable: the live engine client does not implement output reconnect`. This demonstrates an active-turn recovery gap in the shipped Codex profile independently of client replay. These are small deterministic probes, not a broad fault-injection campaign.

## Reconciliation and cleanup

After the no-replay crash-control failure, the public Files API returned HTTP 200 and `startend` from `/workspace/crash-count2`. The failed session was then disposed through DELETE Session, which returned `deleted=true`. The installation-scoped sandbox inventory was empty afterward. Rapid-ship can therefore inspect and preserve source through public APIs, then choose disposal/reconciliation without a fork. It still needs a policy that does not blindly retry a FAILED turn with existing side effects.

All trial services, state/database volumes and host gateway/stub processes were stopped and removed after evidence collection. Unrelated Docker services and global daemon settings were untouched. Downloaded images and the isolated source/venvs remain local caches for reproduction; no global packages were installed.

Shareable evidence is in `shareable/`. Raw logs, generated service secrets, model request bodies, labels containing runtime capability tokens, upstream checkout and Python environments are intentionally excluded. The consolidated helper is diagnostic capture code; its exit status is not a pass verdict. Saved observations are the evidence reviewed for this report.
