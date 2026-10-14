# Models, harnesses, and runtimes

Rapid-ship owns task planning, work coordination, checks, review, and GitHub delivery. It must let projects choose their model, coding harness, and execution environment separately. Projects remain language agnostic.

## Runtime choice

**Use AstraBox for the first managed Docker backend.** The execution trial showed useful sandbox and session reuse; LightDAG leaves substantial resource lifecycle work to our adapters. Rapid-ship retains task planning and delivery rules. This is an integration decision, not a claim that the backend is already connected or qualified for unattended use. See the [decision](archive/orchestrator/runtime-choice.md) and [trial evidence](archive/orchestrator/trials/2026-10-11-runtime-comparison.md).

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

## Quota recovery

Approved alternatives select a complete role, harness, model and isolated credential profile. A replacement reviewer must qualify for that role and review the same commit; a provider change cannot bypass project budgets. Native session resume and cross-harness handoff are different operations. Automatic handoff is not implemented; see the [handoff design](archive/orchestrator/session-handoffs.md).

## Antigravity

The requested workhorse is standalone **Antigravity CLI (`agy`) with Gemini 3.7 Flash**. Keep the reviewer independently configurable. The [official headless interface](https://antigravity.google/docs/cli/headless/) supports streamed JSON input/output and explicit conversation IDs. Run `agy models` in the selected environment to choose an exact available model ID; do not silently upgrade or substitute it.

The adapter supports **workers in the Docker provider** and **reviewers in any provider the project uses**, with an explicit model. It sends one streamed input turn, checks the returned model and conversation, and rejects incomplete output, tool errors, permission requests, diagnostics on stderr, and unverified subagent events. Docker confines project hooks like other candidate scripts; host settings and credentials are not inherited. Workers under other execution providers are blocked until their behavior is verified.

`agy` has no flag that removes its tools for a review, so an `agy` reviewer is read-only by instruction: the reviewer prompt forbids creating, editing or deleting files. The reviewer works in its own copy of the candidate. The controller blocks the task if that copy has a different `HEAD` or any file Git reports as changed. That check is a tripwire, not a sandbox: it does not see ignored files, writes under `.git/` or outside the copy, or a change that is undone. Docker limits the reviewer to its clone and a container that is removed afterwards. Under the native provider the reviewer keeps host file access, and a worktree shares Git metadata with its source. Codex and Claude reviewers also keep their read-only sandbox and no-tool mode.

agy's documentation says it reads [rules](https://antigravity.google/docs/rules/) (`AGENTS.md` or `GEMINI.md` in any directory, `.agents/rules/*.md`) and [hooks](https://antigravity.google/docs/hooks/) (`.agents/hooks.json`) from its working directory, and describes no trust prompt. A hook runs shell commands and can allow tool calls. The reviewer's working directory is the candidate, and the ownership check limits a candidate only to its task's owned paths, so a task that owns a directory can add a rules file there. This has not been tried in a live review.

Supply the standalone binary and model-only authentication in each environment that runs `agy`: the approved Docker environment for a worker, and the reviewer's own environment for a reviewer. Keep the CLI's permission controls: this adapter does not bypass prompts. A soft denial can appear on stderr even with a successful exit, so any stderr output currently blocks acceptance and is retained for inspection. This conservative rule may also block harmless diagnostics until real compatibility trials justify a narrower rule.

Standalone `agy` 1.3.3 is now installed locally. A supervised native call with the exact model argument `gemini-3.7-flash-high` produced code that passed six independent Docker checks. A separate LightDAG run also produced valid code, but its Docker verification timed out while contention was observed; causality was not isolated. The saved candidate passed a later check. Neither result qualifies the production Docker adapter: container authentication, tool permissions, streamed model attestation, project hooks or settings that agy loads from a candidate clone, and independent model review still need live trials. No global installation or authentication was changed during these probes.

Before enabling an adapter for a role, verify its terminal status, permission-denial reporting, cancellation, explicit-session resume, settings and extension behavior, model selection, and environment confinement. A reviewer must not be able to change the code under review. Codex and Claude cannot: they run with a read-only sandbox or no tools. `agy` can, and is only told not to; the controller blocks the task when Git shows a change in the reviewer's copy.
