# rapid-orchestrator: deferred work

**Status: deferred on 2026-10-13 by [ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md). Nothing here is current behaviour. Do not build from it unless that ADR is superseded.**

This file holds the context a future agent needs to resume the work: what rapid-orchestrator was meant to be, what was decided, what was proven, what was only argued, and where to copy from.

## What it was meant to be

rapid-orchestrator is a separate project from rapid-ship. It starts, resumes and cancels Sessions for every Tenant on one machine. It knows nothing about Linear or GitHub; rapid-ship drives it through its CLI.

The first version had six capabilities:

1. Start a Session for a Tenant: a Harness, an exact model, a role brief, and a fresh workspace on its own branch.
2. Report status, the final result, and the Harness's own session ID.
3. Follow output while a Session runs.
4. Send a follow-up message to the same Session.
5. Cancel a Session by killing its whole process tree.
6. Hold caps per Tenant, per Provider and per machine. Callers wait for a slot.

Three additions were accepted later:

- The orchestrator commits each Session's work after every turn. The agent does not commit.
- The Claude Code launch mode is swappable between print mode and background sessions.
- The orchestrator keeps its own copy of each Session's output. It does not parse a vendor's transcript format.

State was one ledger: a row per Session. After a crash, a Session is marked interrupted and the caller resumes it with a new message. There is no recovery of a turn in flight.

## Decisions made before the deferral

| Decision | Reason |
| --- | --- |
| Subscription sign-ins only; no API keys; no gateway between a Harness and its Provider | [ADR 0001](../../adr/0001-subscription-logins-only.md) |
| AstraBox is not used | It accepts API keys only, has no Antigravity engine, and documents Linux hosts only |
| Docker Sandboxes is not used | Its credential modes put a proxy that rewrites the authorization header in front of the Provider |
| Sessions run in Linux containers on plain Docker | One uniform boundary for files, processes, memory and network; the sign-in trial passed |
| Build an own thin core; adopt or fork nothing | [Landscape survey](../../trials/2026-10-13-orchestrator-landscape.md) |
| No workflow-script layer | It would trail each Harness's own subagents and background sessions |
| Tenant means one project; one owner; one machine | Isolation is for credential scope and fair resource use, not for hostile tenants |

Two points were left open:

- **Language.** Python was proposed for consistency with rapid-ship. Go was judged the better fit for a long-running supervisor: one static binary, strong process supervision, and a compiler that checks cheap Workers' output.
- **Container lifetime.** One container per turn and one container per Session, stopped while idle, both work. The second keeps installed dependencies between turns.

## Why it was deferred

- Walk does not need it. The owner starts and oversees at most five Workers by hand.
- The Harnesses' own background sessions, schedulers and subagents are improving quickly.
- Research found that Flight can run without an orchestrator process, given eight small deterministic pieces. See the [Flight research note](../../trials/2026-10-13-flight-without-orchestrator.md).

## When to resume

Resume only if a project is ready for Pre-flight and those eight pieces prove insufficient. The likely causes are:

- Workers on Codex or Antigravity must run unattended, and no hosted route on a subscription exists for them.
- Several projects need caps across Providers that GitHub concurrency groups cannot express.
- Unattended local Sessions need a container boundary that a single project dev container does not give.

## What was proven

- One sign-in per Provider served several containers at once for all three Harnesses. See the [sign-in trial](../../trials/2026-10-13-login-carry.md). The Dockerfiles and check scripts are in `login-carry-spike/` beside this file.
- The two sign-in volumes from that trial, `spike-agy-seed` and `spike-codex-auth`, were kept on the owner's machine for a later recheck after a token refresh.

Everything else in this file comes from reading documentation and source. None of it was run.

## Notes for a future builder

### The three headless contracts

All three Harnesses share one shape: a prompt in, a stream of JSON events out, a session ID, and resume by that ID.

**Claude Code**

- Start: `claude -p --output-format stream-json --verbose --model <id> --append-system-prompt-file <brief> --permission-mode <mode> --permission-prompts none`, with `--json-schema <schema>` for a checked result.
- Pass `--session-id <uuid>` on the first turn so the ledger knows the ID before the start. Use `--resume <id>` for a follow-up.
- The session ID and model are in the first `system` event. The last `result` line carries the result, cost and denied permissions.
- Exit code 0 means success. A SIGTERM gives 143 and ends the process tree of a running shell command.
- Transcripts are under `~/.claude/projects/<project>/<session-id>.jsonl`. `CLAUDE_CONFIG_DIR` moves them.
- Sign-in in a container: `claude setup-token` on the host, then `CLAUDE_CODE_OAUTH_TOKEN` passed by variable name.
- Risks: the documentation says `--bare` will become the default for `-p`, and bare mode does not read a subscription sign-in. An `ANTHROPIC_API_KEY` in the environment outranks the subscription token. Remove it from every launch.
- Alternative launch mode: `claude --bg`, with `claude agents --json` for state.

**Codex CLI**

- Start: `codex exec --json -m <model> -C <dir> --output-schema <file> -`, with the prompt on standard input. Add `--skip-git-repo-check` outside a repository.
- Follow-up: `codex exec resume <thread-id> --json`. Restate the sandbox mode on every resume; the thread does not keep it.
- The thread ID is in the first `thread.started` event.
- Codex's sandbox makes a worktree's git metadata read-only, so `git commit` fails in unattended mode.
- Sign-in in a container: `codex login --device-auth` into a `CODEX_HOME` on a volume. All Sessions must use the one live `auth.json`, through a shared mount or a link from a per-session home. Never give Sessions copies: refresh tokens are single-use, and there is no lock across processes.
- `CODEX_API_KEY` and `OPENAI_API_KEY` override the subscription sign-in. Remove them from every launch.

**Antigravity CLI**

- Start: `agy -p --output-format stream-json --model <id> --print-timeout <duration>`. Follow-up: add `--conversation <id>`.
- The conversation ID is in the first event.
- Exit code 0 is not proof of success. Treat a non-success status, an error field, an empty response or a passed deadline as a failed turn.
- Sign-in in a container: agy's own sign-in by URL and pasted code. With no D-Bus session it writes `~/.gemini/antigravity-cli/antigravity-oauth-token`. A copy of that file in an empty home was enough in the trial.
- Pre-stage the files that skip agy's first-run prompts. Scion shows how: `harnesses/antigravity/provision.py:582-785` at commit `06aa4b40`.
- agy fires hooks only from the project's `.agents/hooks.json`. Its permission settings are one global file.
- Google's FAQ says headless mode is for direct scripting and CI, and that wrapping agy inside third-party coding agents is not supported on consumer plans. Start agy as its own top-level process. Do not call it from a Claude Code or Codex session.
  - Checked on 2026-10-15: agy ran from inside a Codex CLI session and answered. The owner accepted the consumer-plan risk in [ADR 0001](../../adr/0001-subscription-logins-only.md), so the current design no longer forbids this.
- The trial saw HTTP 502 and 503 at Google's eligibility check on 5 of 18 container turns.

### Containers

- Cancel by stopping or removing the container. A signal sent to a process inside one does not reliably end its children.
- Run as a non-root user. Claude Code refuses to skip permission prompts as root.
- Use `--security-opt no-new-privileges` and drop capabilities. Give each container a deterministic name so a repeated start collides.
- Pass a secret by variable name or through an env file with mode 0600. Never put it on the command line.
- Limit outbound traffic with a firewall allowlist inside the container. The Trail of Bits dev container shows an iptables and ipset version. Do not use a proxy that terminates TLS.
- The trial's Docker VM had 4 GiB of memory. Size the machine cap from that.

### The workspace

A git worktree shares the host repository's `.git` directory, hooks included. If the orchestrator later runs git on the host in that repository, a hook written by an agent runs on the host. Two fixes exist: give each Session a fresh clone, or run host-side git with hooks and local configuration disabled. The old controller did the second; see `rapid_ship/execution/environments.py:244-294` at commit `f7b877b`. That commit is tagged `archive/controller-2026-10` when the old controller is removed.

### The ledger

If the orchestrator is built, it needs these rules:

- Record the intent before each external effect: a container start, a commit, a push.
- Before a retry, check the outside world: does the container exist, is the result event in the log, is the remote branch at the expected commit. Stop for a person when the check cannot decide.
- Claim cap slots in the same transaction that records the intent.

Sources for the design:

- rapid-ship's old effect ledger: `rapid_ship/storage.py:565-614` and `rapid_ship/trust/github.py:167-224` at commit `f7b877b`.
- The resume rules of the CLI Agent Orchestrator workflow tier: `src/cli_agent_orchestrator/services/step_replay.py:187-466`.

DBOS Transact was rejected for this role. It re-runs a step that was interrupted mid-flight without checking what happened.

### Where to copy from

| Source and commit | Licence | Take |
| --- | --- | --- |
| GoogleCloudPlatform/scion `06aa4b40` | Apache-2.0 | `harnesses/antigravity/`: `provision.py`, `capture_auth.py:76-130`, `dialect.yaml`, `Dockerfile:27-36`. Seed files under `harnesses/claude/home/` and `harnesses/codex/home/` |
| OrchestratorInc/agent-orchestrator `4a499e8d` | Apache-2.0 | `backend/pkg/agentruntime/command.go` for launch and resume arguments; `cloud/internal/workerexec/harness_credentials.go` for container credentials; `backend/internal/review/prompt.go` for review posting |
| mattpocock/sandcastle | MIT | `src/AgentProvider.ts` command builders and stream parsers; `src/SessionStore.ts` for where each Harness keeps sessions |
| jayminwest/warren `9595340` | MIT | `src/runtime/docker/container-spec.ts` and `spawn.ts` for the Docker launch; `src/runtime/local/finalize.ts` for a host-side push with a per-operation credential |
| harbor-framework/harbor `4778ceba` | Apache-2.0 | `agents/installed/base.py` for failure classification; `claude_code.py` and `codex.py` for launch and sign-in handling |
| Enderfga/claw-orchestrator `5221a89` | MIT | `src/persistent-agy-session.ts` for agy's failure rules; `src/persistent-codex-session.ts` for Codex resume flags |
| openai/symphony `be10a1b7` | Apache-2.0 | `SPEC.md` sections on admission, claims and reconciliation, for an unattended scheduler |

Keep each licence text and note every change when code is copied.

## Open questions

- Does a Codex sign-in shared by several containers survive a token refresh?
- Does agy's token file keep working across its hourly refresh, and across agy releases?
- Does Anthropic treat several unattended containers on one subscription as ordinary individual use?
- How much memory does each containerised Session need on a 16 GiB Mac?
- Do the three Harnesses recover a long turn after the laptop sleeps?

## Older records

These describe the direction that came before. The removal of the old controller moves them into this directory.

- `docs/runtime-choice.md`: the earlier choice of AstraBox.
- `docs/trials/astrabox-report.md`, `docs/trials/lightdag-report.md`, `docs/trials/2026-10-11-runtime-comparison.md`: the earlier runtime trials.
- `docs/session-handoffs.md`, `docs/environments.md`, `docs/authority.md`: designs for the old controller.
