# Runtime choice: AstraBox, LightAgent or LangGraph

**Recommendation: trial LightAgent's LightDAG first for the single-machine controller. Keep AstraBox as the coding-runtime alternative and LangGraph as the general workflow alternative.** No foundation is selected until the trial passes.

## Comparison

| Requirement | AstraBox | LightAgent / LightDAG | LangGraph |
| --- | --- | --- | --- |
| Main abstraction | Managed coding harness sessions and sandboxes | Persistent dynamic task graph and verified artifacts | General stateful workflows |
| Local operation | Docker host; API/UI, PostgreSQL, LiteLLM, OpenSandbox | Python and SQLite; one scheduler per run | Embedded Python with local checkpoint storage; cloud service optional |
| BYO harness | Explicit engine adapter API and sandbox images | Callable worker wrapper; harness operations are ours | Python nodes can call any harness; harness operations are ours |
| BYO model | Routes must match the harness's protocol | Model APIs plus custom workers | Model libraries optional; custom nodes can use any compatible connection |
| Sandbox/session work reused | Substantial | No built-in coding sandbox | No built-in coding sandbox |
| Dynamic task planning | Rapid-dev supplies it | Decomposition proposals and verifier are built in | Dynamic fan-out and nodes; rapid-dev defines task rules |
| Recovery | Saved conversations; failed compute still needs task reconciliation | SQLite leases and verified artifacts; long tasks need the policy below | Checkpoint replay, interrupts and retries; external effects need reconciliation |
| Linear, GitHub delivery, trust metrics | Rapid-dev integration | Rapid-dev integration | Rapid-dev integration |
| License | Apache-2.0 | Apache-2.0 | MIT |

Sources: [AstraBox deployment](https://github.com/Colton-z/AstraBox/blob/main/docs/deploy.md), [engine adapters](https://github.com/Colton-z/AstraBox/blob/main/docs/writing-an-engine-adapter.md), [LightDAG](https://github.com/wanxingai/LightAgent/blob/v0.11.0/docs/lightdag.md), [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) and [persistence](https://docs.langchain.com/oss/python/langgraph/checkpointers).

### Adoption and maturity

GitHub snapshot, 11 October 2026. These are community signals, not counts of production installations.

| Repository | Stars | Forks | Created |
| --- | ---: | ---: | --- |
| [AstraBox](https://github.com/Colton-z/AstraBox) | 15 | 2 | September 2026 |
| [LightAgent](https://github.com/wanxingai/LightAgent) | 1,233 | 175 | January 2025 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 43,023 | 7,306 | August 2023 |

LightAgent has a substantially larger established community than AstraBox. Its **LightDAG module is still new and experimental**, introduced this month; the whole library's adoption does not establish the scheduler's reliability. See the [v0.11.0 release](https://github.com/wanxingai/LightAgent/releases/tag/v0.11.0).

LightDAG's task graph and verifier fit rapid-dev closely, with a small Python/SQLite deployment. Custom workers can wrap `agy` or other harnesses without adopting LightAgent's model loop. We still supply container lifecycle, process cancellation, credentials and SDLC policy.

AstraBox removes more harness-hosting, session and sandbox work. Its API/UI, PostgreSQL, LiteLLM and OpenSandbox services are an operational tradeoff, not a memory disqualification: Docker's allocation is adjustable. Choose it if trials show that its runtime reuse outweighs those services and its smaller, newer community.

LangGraph has the strongest adoption of the three and established checkpoint, interrupt and retry primitives. It can call CLIs without requiring LangChain agents. It is attractive if workflow flexibility and ecosystem support matter more than LightDAG's ready-made task and verification model; coding environments and delivery rules still remain ours.

## The LightDAG lease issue

A lease is a temporary claim on work. Its expiry lets another scheduler recover after a crash and prevents an old worker from publishing late results.

In `v0.11.0`, both scheduler and task leases default to 60 seconds. The [scheduler renews between batches](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/scheduler.py#L150-L193), but does not renew while workers and reviewers run. Task leases are not renewed by the scheduler. A long attempt can therefore [lose permission to publish its result](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/store.py#L1095-L1107), leaving the run blocked and the task marked running or verifying until recovery.

**Two clean workarounds passed local probes; neither requires a fork.**

| Approach | What rapid-dev must do | Tradeoff |
| --- | --- | --- |
| Longer leases | Set both leases above an enforced maximum batch duration: setup, worker, queued reviews, verification and cleanup, plus margin | A crashed owner can delay recovery until the lease expires |
| Heartbeat adapter | Renew both leases from trusted host code, from worker creation through review/publication and release | More integration code; renewal loss must stop work and prevent stale publication |

Longer leases work when the whole batch has an enforced time limit. Include waiting for scarce reviewers; a worker-only timeout is insufficient. Each retry receives a fresh lease. Apply configuration changes to new runs; do not bypass saved configuration checks to recover an existing run.

The heartbeat probe used public `RegistryWorkerFactory.create/release` hooks and the store's [attempt renewal](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/store.py#L478-L485) and [scheduler renewal](https://github.com/wanxingai/LightAgent/blob/8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f/LightAgent/dag/store.py#L349-L357) APIs. It preserved owner/epoch checks. Renewing only inside the worker misses the subsequent review period.

### What was tested

Unmodified DAG modules at commit `8318a5d7cb7a573b6ee63ed5e10d0d23bf10466f` (`v0.11.0` and current main on the snapshot date), Python 3.13, temporary SQLite/artifacts. Imports bypassed optional top-level model SDK dependencies. These are synthetic correctness probes, not model or packaged-application benchmarks.

| Probe | Result |
| --- | --- |
| 0.25s worker + 0.25s review; both leases 0.4s / 0.8s | Short lease blocked during review; longer lease succeeded |
| Three parallel workers, serial reviews; both leases 0.4s / 0.8s | Short lease verified only one task; longer lease verified all three |
| Worker/reviewer deadlines; rejected first review | Deadline failures ended terminally; retry received a fresh lease |
| 0.15s leases with lifecycle heartbeat | 0.864s attempt succeeded with nine renewals |
| Abandoned owner with 0.5s lease | New owner rejected before expiry; recovery succeeded afterward |

## Trial and architecture

Use one orchestration foundation. Linear records the plan; rapid-dev selects workers and applies checks, review and delivery rules. The first trial places LightDAG behind that controller, with separate harness and environment adapters. GitHub write/merge credentials remain in the delivery service, outside worker environments. Neither a checkpoint nor a resumed session proves an external operation completed.

Test real `agy`/Gemini workers, an independent stronger reviewer, two isolated environments, tasks exceeding 60 seconds, queued reviews, owner takeover, renewal loss, cancellation during review, restart, duplicate events and child-process cleanup. Finish with one checked PR and measured resource use. Choose LightDAG if these pass without a fork or substantial scheduler replacement. Otherwise compare AstraBox's runtime integration and LangGraph's workflow primitives against the failed requirement. No candidate is integrated yet; these probes do not grant unattended delivery.
