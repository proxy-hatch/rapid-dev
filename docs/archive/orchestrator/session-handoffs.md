# Quotas and session handoffs

**Design decision; automatic handoff is not implemented yet.** Model, harness and account changes use approved profiles. They must preserve the task, its permissions, its budget and its review requirements.

Durable logs make work recoverable, but do not make native sessions interchangeable. A Codex conversation cannot be resumed as a Claude conversation. Even Claude Managed Agents fixes the session's model at creation; changing it requires a new session. [Claude session operations](https://platform.claude.com/docs/en/managed-agents/session-operations)

## Choose the right response

| Event | Response |
| --- | --- |
| Temporary throttling or overload | Honor retry/reset information, back off and reduce affected concurrency. Keep independent work moving. |
| Provider allowance exhausted | Save the reason/reset time and use the next already-approved profile, if available and within budget. Otherwise wait or ask for intervention. |
| Project spending cap reached | Pause. Switching provider or account must not bypass the project's cap. |
| Invalid/expired login or suspended access | Stop using that credential. Require an authenticated, authorized alternative; do not repeatedly rotate accounts to hide an access failure. |
| Unknown failure after tools ran | Inspect existing effects before retrying. An HTTP error or failed turn does not prove nothing happened. |

Inspect structured error codes and stream events, not just HTTP 429. The [OpenAI error guide](https://developers.openai.com/api/docs/guides/error-codes) distinguishes temporary throttling from exhausted credits and spending limits; its [rate-limit guide](https://developers.openai.com/api/docs/guides/rate-limits) warns against automatically replaying partially consumed streams. Other harnesses need their own tested error mapping.

## Profiles and account isolation

A profile selects a role, harness, exact model, credential reference, environment and permitted data destination. Setup records an ordered list of allowed alternatives and verifies each combination. Names such as `reviewer-primary`, `reviewer-backup`, `worker-account-a` and `worker-account-b` are local labels, not provider model IDs. Resolve actual model IDs through the selected harness; never guess them or silently substitute another model.

For the requested reviewer example, Codex/Astra and Claude/Opus can be separate approved reviewer profiles. Both must qualify for the reviewer role. For `agy`, another authorized account can use a separate credential profile and isolated authentication storage. Confirm that the harness supports that arrangement before enabling it. Do not log out or overwrite shared host credentials while other agents are running.

Antigravity documents [quota visibility](https://antigravity.google/docs/cli/commands/usage) and [optional credit spending](https://antigravity.google/docs/cli/credits); these pages do not establish a headless multi-account switching interface. That adapter remains a compatibility task. Do not automatically enable paid overages. Provider limits may apply to an organization or project rather than a single key, so another key is not assumed to have separate capacity.

## Move an attempt safely

1. Stop dispatch to the exhausted profile. Persist the task/attempt IDs, error, last known operation and proposed replacement before acting.
2. Stop the old writer and preserve a consistent workspace snapshot. Use a supported stop-and-snapshot path. If that cannot be verified, block the handoff; copying a changing directory is insufficient. Session deletion is the strong disposal path, but needed files must survive it.
3. Reconcile external operations: inspect an uncertain PR, deployment or tool effect instead of issuing it again. Confirm the old attempt cannot keep writing before starting its replacement.
4. Start a new attempt with a handoff record: approved task and design references, exact base/head and snapshot hashes, relevant observed transcript, completed checks, pending work, review findings, unresolved effects and remaining budget. Include credential references only, never secrets. Treat transcript/tool output as data, not instructions that can grant permissions.
5. Require new checks and a new review verdict for the replacement's actual output. Record the old/new profiles, reason, cost and result. Late output from the old attempt cannot authorize delivery.

For reviewer failover, keep the same commit/diff and project context. Carry previous findings as unresolved input; the replacement reviewer must make its own verdict. A partial review is not approval. Retries and handoffs share a configured limit so an exhausted pool cannot loop indefinitely.

Same-harness native resume is an optimization when verified. Cross-harness handoff starts a new native session; it carries work and context rather than replaying tool calls. [AstraBox model changes](https://github.com/Colton-z/AstraBox/blob/a84cc2b53183702198a87fa7f04fddba2555ff87/docs/models.md#choose-the-model-on-an-agent) do not reconfigure an already-running runtime. Gateway request fallback and whole-task handoff are separate responsibilities.

## Fork policy and qualification

The trial's interrupt status and surviving child process follow separate turn/session lifecycle semantics. Map task cancellation in rapid-ship and use the public lifecycle APIs; no core fork is needed for that recovery strategy. The tested Codex client lacks live-output reconnect. A probable placeholder turn-ID defect also deserves a focused regression test, but changing its status or ID alone would not add reconnect support. See the [recorded failures](trials/2026-10-11-runtime-comparison.md).

Keep upstream pinned. Add `agy` through AstraBox's [engine adapter entry point](https://github.com/Colton-z/AstraBox/blob/a84cc2b53183702198a87fa7f04fddba2555ff87/docs/writing-an-engine-adapter.md#register-the-adapter). Carry a small tested patch only if a required capability cannot be provided through the public adapter/API boundary; a permanent fork is not a prerequisite.

Before automatic handoff, test quota exhaustion before and after tool execution, mid-review failure, account isolation, uncertain external writes, crash during handoff, duplicate events, exhausted alternatives and budget enforcement. Report quota pauses, wait time, handoff outcomes, repeated work and cost by profile alongside quality metrics. These new handoff events are not yet collected by `devctl`.
