# Runtime trial: LightDAG and AstraBox

**Status: describes deferred or removed work. Nothing here is current behaviour. See the [archive README](../README.md).**

Trial date: 11 October 2026. This compares a task scheduler with a managed coding runtime. It tests execution and recovery, not production reliability or coding quality.

**Decision: integrate AstraBox as the first managed Docker backend.** It removes more of the difficult runtime work. Keep rapid-ship's planner, task state, reviews, metrics and GitHub delivery independent; do not add LightDAG as a second scheduler. `agy` and other environments still need their own verified adapters. See the [architecture decision](../runtime-choice.md).

AstraBox demonstrated real advertised capabilities. Its small community still raises maintenance risk, and this short trial cannot establish long-term stability. Pin the tested version and repeat these checks before upgrades. This decision does not enable unattended delivery.

## Method

We installed the real LightAgent package and ran AstraBox's published server and sandbox images. Neither upstream implementation was patched. Both trials exercised long jobs, duplicate requests, cancellation and restart on the same macOS/OrbStack machine. Docker's observed 3.893 GiB allocation is adjustable; it is not a framework limit.

| Candidate | Pinned version | Execution under test |
| --- | --- | --- |
| LightAgent / LightDAG | `v0.11.0`, `8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f` | Installed Python package, SQLite, our small subprocess/Docker adapter and deterministic workers |
| AstraBox | `v0.1.5`, `a84cc2b53183702198a87fa7f04fddba2555ff87` | Published server, PostgreSQL/Redis, OpenSandbox, real Codex 0.160.0 and a deterministic local model endpoint |

The deterministic workers and endpoint make execution counts, delays and child processes predictable. They do not measure a model's ability to build software. A separate native `agy`/Gemini smoke test is described below.

## Observations

| Check | LightDAG | AstraBox |
| --- | --- | --- |
| Long execution | Two 65-second workers plus queued reviews completed in 71.667 seconds. Adapter renewed four-second leases 276 times. | A 65-second Codex shell job completed in 68.2 seconds. |
| Duplicate work | Different scheduler identities rejected concurrent ownership. Same-identity concurrent resume needed our single-flight wrapper. | Repeated session creation returned the same session ID; repeating a client message ID ran the long job once. |
| Isolation | Restricted worker containers; no network, Docker socket or credential environment. | Two real sandboxes; the second could not read the first's file. Workers had no host home/socket mounts or privileged flag. |
| Cancellation | Our adapter stops process groups/containers. Plain `CallableVerifier` continued until its own completion despite cancellation. | Turn interruption left a shell child alive. Deleting the session removed its container. |
| Recovery | Actual scheduler SIGKILL, then our startup reaper and resume, preserved completed work and retried only interrupted work. | API restart preserved files and the native Codex conversation; a subsequent tool call succeeded. |
| Controller loss during execution | The adapter stopped the orphan worker before retrying the interrupted task. This is task retry, not native conversation recovery. | After server SIGKILL, the command finished exactly once, but the managed turn ended `FAILED` with an engine-turn ID conflict. This did not pass successful in-flight recovery. |
| Late container creation | Strict timeout check found a Created-container leak in our simple adapter. A separate provisioning experiment blocked duplicate dispatch while creation was uncertain. | Automatic reaper removed the unclaimed container, sidecar and runtime volume after its unchanged 600-second grace. |
| Status interpretation | Renewal loss prevented publication but left the run marked running pending recovery. | An interrupted turn reported `COMPLETED` with terminal reason `interrupted`; status alone is insufficient. |

## What the tests changed

**LightDAG's lease is manageable.** Its default 60-second claim is not a reason to reject it. Public APIs let the application renew both scheduler and attempt leases through execution, queued review and publication. Alternatively, a fixed lease must exceed the entire enforced attempt duration. Renewal loss must stop work and reject late results.

**Container lifecycle is substantial integration work.** A strict review of our LightDAG probe caught a false cleanup claim: a Docker inspection error or a non-running container does not prove removal. The corrected check exposed a startup race that left a Created container after timeout. This failure belongs to our adapter, but its repair and maintenance count against the cost of choosing LightDAG.

A separate public-API adapter split Docker creation from startup and recorded pending requests. Three fault probes passed: delayed creation then cancellation, uncertain creation blocking duplicate dispatch even after adapter reconstruction, and cancellation of a running container and child. This shows a workable direction without a fork. It does not solve process death during creation, lost replies after host restart, multiple owners or garbage collection.

**AstraBox provides working runtime infrastructure.** The real sandbox, tool execution, duplicate handling and session continuity worked. Its small community is a maintenance risk, not evidence that these features are imaginary. Session interruption is weaker than job cancellation, so rapid-ship must delete the session or explicitly stop its process tree before replacing work.

**A failed turn may already have changed the workspace.** Killing the AstraBox server during execution left its sandbox command running. The command completed once, but AstraBox stopped the recovered turn with `observed conflicting engine turn anchor for the active turn`. That is a conservative failure, not a successful recovery or proof of duplicate execution. Rapid-ship must inspect the workspace and recorded operations before deciding whether to accept, repair or retry. The cause of the changed execution ID was not established by this probe.

A control without replaying the input also failed to recover the active turn: `engine recovery unrecoverable: the live engine client does not implement output reconnect`. Its file effect still completed once. The [pinned recovery code](https://github.com/Colton-z/AstraBox/blob/a84cc2b53183702198a87fa7f04fddba2555ff87/astrabox/core/service/orchestrator/session_kernel/service_mixins/durable_recovery_assistant.py#L263-L274) explicitly requires that client capability. This establishes a limitation of the tested Codex profile independent of duplicate submission. Completed-session continuation passed; transparent in-flight recovery did not. The integration must support stopping a failed session and checking its effects before retrying in a fresh session.

The failed session's file was downloadable through the public API, returning HTTP 200 and the expected once-only result. Reconciliation therefore does not require a Docker-host-only inspection or an upstream fork. The complete inspect/dispose/fresh-attempt workflow still needs integration testing.

**Automatic cleanup saved real work.** A container created after a cold allocation timed out became unclaimed. AstraBox's reaper removed it, its sidecar and its runtime volume just after the 600-second grace. Logs recorded deletion at 20:42:48–49 UTC; a separate Docker check confirmed absence at 20:42:58. The supported sweep interval was shortened for this observation, but the grace period was unchanged. This is a concrete lifecycle feature that the LightDAG integration would need to supply.

## Setup and resource limits

The initial AstraBox deployment combined its services with an embedded LiteLLM gateway. Under the trial's service cap and existing Docker allocation, startup caused substantial contention. We moved LiteLLM to an isolated host environment using the supported external-gateway configuration. API-ready server memory then fell to about 310 MiB; this is a point observation, not a capacity benchmark. No global Docker restart or unrelated service change was needed.

The OrbStack setup also needed the Linux socket group and actual bridge gateway address. The Codex sandbox image was 3.50 GB compressed and 8.68 GB unpacked. These affect installation effort; slow pulls and insufficient trial resources are not product defects.

Only fake model credentials were used in AstraBox. The unique-port external gateway required disabling its protected credential vault for this probe. Protected credential delivery and real provider compatibility remain untested. LightDAG's deterministic workers received no model credentials.

## Model and test-suite evidence

Standalone `agy` 1.3.3 with the explicit argument `gemini-3.7-flash-high` produced code that passed six independent Docker checks. In a separate LightDAG run, the model stage succeeded, but Docker verification exceeded its original allowance while Docker contention was also observed; its causal contribution was not isolated. The saved candidate later passed. This is model-stage success plus later verification, not a clean end-to-end pass. The JSON response did not attest the selected model; the recorded command selected it explicitly.

LightDAG's targeted upstream suite passed **21 tests** against the installed package. AstraBox's broader default suite returned **4,405 passed, 38 skipped, 218 deselected, one failure and one setup error**. The failure assumed Linux `/proc/mounts` on macOS; the setup error was a Node toolchain acquisition timeout. Live integration markers were excluded by default. Test counts cover different scopes and do not rank reliability.

Neither trial qualifies unattended shipping. Missing evidence includes prolonged fault testing, host/Docker restart, disk exhaustion, real tool-using `agy` in the approved container, stronger model review, and checked GitHub delivery. These remain qualification work after selecting a foundation.

## Evidence and reproduction

- [LightDAG report](lightdag-report.md) and [frozen probe bundle](lightdag-trial-2026-10-11.tar.gz). SHA256: `355179ecbc7c18ce3114db265910aaa2e07be323d1217b48212ba528da37811b`.
- [AstraBox report](astrabox-report.md) and [frozen probe and evidence bundle](astrabox-trial-2026-10-11.tar.gz). SHA256: `1446e60efa37fd03b71f4110e3217b4f4d89827272fa27fe65f70de6334d905f`.

The archives preserve experimental scripts, pinned dependencies, results and failed probes. They are research artifacts, not installed controller code. Extract each bundle into the temporary trial directory named in its README before following its commands. Scripts evolved during the trial; their reports distinguish earlier observations from targeted reruns of the final scripts. The candidate implementations were not modified.

Independent review checked the evidence, limitations, cleanup assertions and publication privacy. AstraBox's consolidated helpers capture observations; they are not a fully automated acceptance suite. All owned trial services and worker containers were cleaned up. Downloaded images and isolated source/environments remain local caches; unrelated services and global Docker settings were unchanged.
