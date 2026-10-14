# Runtime choice

**Choose AstraBox for the first managed Docker execution backend.** Keep rapid-ship's task planning, checks, review, metrics and GitHub delivery outside it. Do not add LightDAG as a second scheduler.

This selects the next integration; AstraBox is not yet connected to `devctl`, and unattended delivery remains disabled. The [runtime trial](trials/2026-10-11-runtime-comparison.md) records the tests, failures and reproducible evidence.

## Why this choice

The difficult gap is reliable process and container management. LightDAG's task graph works, and its lease issue has clean workarounds. But its application adapter must still handle uncertain container creation, cancellation, orphan cleanup and recovery after a crash. Our trial exposed a real startup leak in that adapter. A small replacement passed three fault probes but did not solve the full lifecycle problem.

AstraBox already provides managed sandboxes and native coding sessions. In our trial, a real Codex harness executed tools, two sandboxes kept their files separate, duplicate requests did not repeat execution, and an API restart preserved the workspace and conversation. Its automatic reaper also removed a late-created orphan, sidecar and volume after the documented grace. Its built-in runtime work is more valuable here than another task-graph abstraction.

AstraBox also has limits. Interrupting a turn left a shell child alive; deleting its session removed the container. An interrupted turn reported `COMPLETED` with reason `interrupted`. Killing the server during a job let the command finish once, but the managed turn failed on an execution-ID conflict. Rapid-ship must inspect results and confirm work has stopped before replacing it; a failed status does not prove nothing happened. The trial does not prove production stability, protected credential delivery or compatibility with `agy`.

A second crash test without input replay reported that the shipped Codex client does not implement output reconnect. Do not depend on transparent recovery of an active turn. Failed-session files remained readable through the public API. Use that inspection and the tested session-disposal path to reconcile results before a fresh attempt; qualify that complete path before enabling the backend.

The public lifecycle APIs are sufficient for an inspect-and-restart recovery strategy; a permanent fork is not required. Live Codex output reconnect is a separate enhancement, and the suspected turn-ID defect needs a focused regression test. See [quota handling, session handoffs and patch policy](session-handoffs.md).

## Alternatives

| Option | Useful part | Cost for rapid-ship | Decision |
| --- | --- | --- | --- |
| [AstraBox](https://github.com/Colton-z/AstraBox/tree/v0.1.5) | Managed coding sessions, engine adapters, OpenSandbox lifecycle and model routing | PostgreSQL, Redis, gateway and sandbox services; an `agy` adapter; qualification of status, cancellation and credentials | First managed Docker backend |
| [LightAgent / LightDAG](https://github.com/wanxingai/LightAgent/tree/v0.11.0) | SQLite task graph, decomposition proposals and verified artifacts | Harness hosting and resource lifecycle remain ours; lease renewal and single-flight resume need wrappers | Viable scheduler, but does not remove the largest runtime burden |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | General workflows, checkpoints, interrupts and retries | Task/review rules and coding-runtime infrastructure remain ours | Keep as a workflow alternative; not part of this two-candidate execution trial |

Docker's allocation is configurable. The observed 4 GB allocation and cold image downloads did not decide the choice. AstraBox required more setup on this Mac/OrbStack host; using its supported external model gateway relieved the initial resource contention.

## Does the small community matter?

Yes: it raises maintenance and upgrade risk. It does not establish whether the software works. The trial verified several advertised runtime features, but a short trial cannot establish long-term stability.

GitHub snapshot, 11 October 2026:

| Repository | Stars | Forks | Created |
| --- | ---: | ---: | --- |
| AstraBox | 15 | 2 | September 2026 |
| LightAgent | 1,233 | 175 | January 2025 |
| LangGraph | 43,023 | 7,306 | August 2023 |

LightAgent's larger community is relevant, but its LightDAG module was introduced this month and is marked experimental. Package popularity does not establish that module's operational history. AstraBox's broader test suite is encouraging, but test counts do not substitute for runtime trials either.

Pin the AstraBox release and image digests, keep its adapter replaceable, and repeat recovery tests before upgrades. Reconsider the choice if `agy` integration requires an upstream fork, routine resource cleanup remains unreliable, or maintaining the deployment costs more than the lifecycle code it replaces.

## The LightDAG lease issue

A lease is a temporary claim on work. Expiry lets another scheduler recover after a crash and prevents an old worker from publishing late results. In `v0.11.0`, the default claims last 60 seconds; the scheduler renews between batches, not throughout worker execution and review.

Two approaches worked without a fork: renew both scheduler and attempt leases through execution, queued review and publication, or use a fixed lease longer than the entire enforced batch duration. The latter delays crash recovery. Our runtime adapter kept two 65-second workers and serial reviews alive using four-second leases and public renewal APIs. **The lease issue is not the reason to choose AstraBox.** See the [LightDAG report](trials/lightdag-report.md) for the source links and failure cases.

## Integration boundary

- **Rapid-ship** owns task state, scope slicing, worker/reviewer selection, budgets, checks, quality metrics and delivery decisions. Linear records the plan and responsibility.
- **AstraBox** runs supported coding sessions in managed Docker sandboxes. Rapid-ship records its session/request IDs and reconciles uncertain responses before retrying.
- **Harness and model adapters** remain separate choices. Add and test the `agy` engine with the exact configured model; an OpenAI-compatible endpoint alone does not prove tool-protocol compatibility.
- **Other environments** retain their own providers. Native worktrees, OpenHands and AWS test-account allocation must not be forced into AstraBox's session model. Each provider must meet the same execution and recovery requirements.
- **GitHub delivery** stays in the separate credential context. Workers do not receive merge credentials merely because a runtime can materialize Git keys.

Before enabling this backend, implement the `agy` adapter, enforce task resource limits, verify model-only credential delivery, test abrupt failure and host/Docker restart, and complete representative changes with independent review and checked PR delivery. Then qualify specific workflows through human-reviewed trials; selection alone grants no extra autonomy.
