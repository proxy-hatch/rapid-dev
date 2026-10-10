# Models, harnesses, and runtimes

Rapid-ship owns task planning, scheduling, checks, review, and GitHub delivery. It must let projects choose their model, coding harness, and execution environment separately. Projects remain language agnostic.

## Runtime choice

**Use AstraBox for the first managed Docker backend.** The execution trial showed useful sandbox and session reuse; LightDAG leaves substantial resource lifecycle work to our adapters. Rapid-ship retains task planning and delivery rules. This is an integration decision, not a claim that the backend is already connected or qualified for unattended use. See the [decision](runtime-choice.md) and [trial evidence](trials/2026-10-11-runtime-comparison.md).

| Option | What it provides | Fit for rapid-ship |
| --- | --- | --- |
| [AstraBox](https://github.com/Colton-z/AstraBox) | Managed coding sessions, harness adapters, sandboxes and model routing. Its standard deployment includes PostgreSQL, LiteLLM and OpenSandbox. | Selected for managed Docker execution. More services and a much smaller, newer community; `agy` still needs an engine adapter. |
| [LightAgent / LightDAG](https://github.com/wanxingai/LightAgent/blob/main/docs/lightdag.md) | Durable SQLite task graphs, decomposition proposals, verification and worker recovery. | Task graph and lease workarounds passed trials. Harness hosting and reliable resource cleanup remain ours. |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | Workflow graphs, checkpoints, interrupts and resume. | Largest ecosystem. We supply the task/review model and coding-runtime infrastructure. |
| [OpenHands](https://docs.openhands.dev/sdk) | Coding agent SDK, tools, server and execution integrations. | Optional harness/environment adapter. Does not replace BYO support. |

This is an architectural judgment, not a performance ranking. Docker memory is configurable; 4 GB is not a fixed ceiling. Measure resource use and quality before increasing concurrency. OpenHands or Docker must use separate network namespaces for fixed internal ports; host networking can reintroduce collisions. AWS accounts and shared installations require separate resource leases.

The useful idea from [Anthropic's managed agents](https://www.anthropic.com/engineering/managed-agents) is to separate coordination, execution, and durable state. A local implementation does not require adopting a cloud service.

## Bring your own

| Choice | Owns | Example |
| --- | --- | --- |
| Model connection | Provider, exact model ID, endpoint reference, credential reference | Gemini 3.7 Flash; a compatible model at a chosen OpenAI-style endpoint |
| Harness | Tool loop, CLI/API, event format, session and permission controls | `agy`, Codex, Claude Code, a future custom harness |
| Environment | Workspace, process and network isolation, resource limits | Docker, worktree with approved native execution, OpenHands |

An OpenAI-compatible endpoint supplies model inference; a coding harness must still drive tools. Each adapter declares which connections and roles it supports. Unsupported combinations stop before launch. Model credentials stay separate from GitHub delivery credentials.

The target configuration uses **named agent profiles**: a worker profile and a reviewer profile each select a harness and a compatible model connection. A task can select a complete profile without inheriting an unrelated model. Adapter code belongs in the reviewed controller installation, never in a candidate project's configuration.

Today configuration has separate `worker_runner`, `worker_model`, `reviewer_runner`, and `reviewer_model` fields. A task may set `runner` and `model`; changing the harness requires an explicit task model, so an unrelated project default cannot carry over. Named profiles, custom endpoint configuration and a public custom-harness registry are planned, not implemented. No harness is assumed to support every model.

## Antigravity

The requested workhorse is standalone **Antigravity CLI (`agy`) with Gemini 3.7 Flash**. Keep the reviewer independently configurable. The [official headless interface](https://antigravity.google/docs/cli/headless/) supports streamed JSON input/output and explicit conversation IDs. Run `agy models` in the selected environment to choose an exact available model ID; do not silently upgrade or substitute it.

The adapter supports **workers in the Docker provider**, with an explicit model. It sends one streamed input turn, checks the returned model and conversation, and rejects incomplete output, tool errors, permission requests, diagnostics on stderr, and unverified subagent events. Docker confines project hooks like other candidate scripts; host settings and credentials are not inherited. Antigravity reviewers and other execution providers are blocked until their behavior is verified.

Supply the standalone binary and model-only authentication in the approved Docker environment. Keep the CLI's permission controls: this adapter does not bypass prompts. A soft denial can appear on stderr even with a successful exit, so any stderr output currently blocks acceptance and is retained for inspection. This conservative rule may also block harmless diagnostics until real compatibility trials justify a narrower rule.

Standalone `agy` 1.3.3 is now installed locally. A supervised native call with the exact model argument `gemini-3.7-flash-high` produced code that passed six independent Docker checks. A separate LightDAG run also produced valid code, but its Docker verification timed out while contention was observed; causality was not isolated. The saved candidate passed a later check. Neither result qualifies the production Docker adapter: container authentication, tool permissions, streamed model attestation and independent model review still need live trials. No global installation or authentication was changed during these probes.

Before enabling an adapter for a role, verify its terminal status, permission-denial reporting, cancellation, explicit-session resume, settings and extension behavior, model selection, and environment confinement. A reviewer must not gain write or command-execution permissions through a worker-only adapter.
