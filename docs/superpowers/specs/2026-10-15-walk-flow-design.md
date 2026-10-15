---
status: draft
---

# Spec 2: Walk flow

**Status: draft, started on 2026-10-15.** The owner settled the decisions here in a design interview on 2026-10-15. Section 12 lists what is not yet designed; it is designed with the owner before the plan. This is the second of the four specs listed in the [rapid-ship design](2026-10-14-rapid-ship-design.md), after [Spec 1](2026-10-14-kit-and-setup-design.md). Terms follow `GLOSSARY.md` at the repository root.

## 1. Scope and outcome

When this spec is built, the owner runs `rs-walk` in Claude Code or Codex and picks tasks. The Lead carries each task from `devctl dispatch` to a merged PR. Events wake it, and no model polls. It starts each Worker and Reviewer and recovers their stops. It asks the owner to approve PRs, to choose a Takeover, and to explain a PR that closed while its issue was still started.

This spec covers:

- the Lead's event loop: `devctl watch`, reconciliation, and the action for each event;
- launching Worker and Reviewer Sessions without an orchestrator;
- the merge step, stops, resume and Takeover;
- the sandbox and permissions for each role and Harness;
- how Linear decides why a PR closed;
- what Spec 1 assigns here: the skills `rs-plan`, `rs-walk`, `rs-work`, `rs-review` and `rs-garden` with the upstream skills in Spec 1 section 7, Linear conventions beyond Setup, the corrections ledger, and the start command templates.

Spec 1 keeps devctl's part of a Claim: `devctl dispatch` with `--status`, `--release`, `--clean` and `--session`, the cap, the gate log and the Session registry. It also keeps `devctl pr`, `devctl review`, `devctl merge` in its Walk form, and the ruleset. Spec 3 keeps Flight's conditions on `devctl merge` (a Reviewer approval, the metrics and the lease), the metrics, Pre-flight and the Investigator.

Setup's final step, one small real task through this flow (Spec 1 section 8, step 11), is verified once this spec is built.

## 2. Roles and Sessions

| Role | What it is | Harness | Ends |
| --- | --- | --- | --- |
| Lead | The owner's own Session running `rs-walk`, with the owner's normal settings | Claude Code or Codex, both supported from day 1. agy is not a Lead yet | When the owner stops it. Reconciliation at start-up makes a restart safe |
| Worker | One Session per start, in the Claim's worktree | The Worker Agent's Harness from `project.toml` | With a pushed PR, a clear result, or a stop (section 8) |
| Reviewer | One Session per head commit, in its own worktree at that commit | Claude Code or Codex. agy is never a Reviewer | With one verdict posted through `devctl review` |

- Each Worker start is a new Session: the first implementation, each round of the review loop, a fix for a failed `devctl check`, and the merge step. A resume after a stop continues the same Session.
- The Session registry (Spec 1 section 6) records every Worker and Reviewer Session start, with the place of its transcript.
- The owner judges agy's model and Harness unsuited to review. Spec 1's `rs-setup` therefore recommends a Reviewer on Claude Code or Codex, from a different Provider than the Worker.

## 3. The Claim lifecycle

devctl's part is in Spec 1 section 6. The Lead sees four states:

1. **Dispatched.** `devctl dispatch` created the branch `rs/<issue-id>` and its worktree. The Claim has no PR of its own yet, and it counts toward the cap. A closed PR of an earlier Claim of the same issue is not its PR (Spec 1 section 6).
2. **PR open.** The Worker opened the PR with `devctl pr`. The Claim still counts. Reviews, check results and the merge step happen here.
3. **Merged or closed.** The Claim stops counting at once, even before its branch is deleted.
4. **Released.** The branch is deleted, and the worktree is removed when it is clean: nothing uncommitted, and every commit kept on GitHub (Spec 1 section 6). `devctl merge` releases on merge. The Lead releases with `devctl dispatch --release` after the owner merges directly, and after a PR closes once Linear or the owner explains why (section 6). `devctl dispatch --clean` is the manual fallback. A dirty worktree is reported and kept until `--force`.

A Worker that stops before opening a PR has no timeout in Walk. `devctl dispatch --status` shows each Claim's age, last commit time and Sessions, and the owner ends a Claim with `--release`.

GitHub keeps a closed PR's commits and offers "Restore branch". A later `dispatch` of that issue starts fresh from the default branch. The Lead gives the new Worker the old PR as context, not as its starting point.

## 4. `devctl watch`

`devctl watch` turns outside changes into one line per event. It is a deterministic script and spends no model tokens. It runs only while a Lead uses it; it is not a service.

It reads three sources:

- **GitHub.** For each live Claim's branch and its own PR (Spec 1 section 6), it polls GitHub's REST API every 30 to 60 seconds. Each request is conditional: it sends `If-None-Match` with the last `ETag`, and a `304 Not Modified` reply does not count against the rate limit.
- **Session exits.** The launch wrapper writes an exit-status file when a Worker or Reviewer process exits (section 9). `watch` reports each new file, and a Session that ended without one, as after a sleep or reboot.
- **Timers.** The Lead registers timers in a small local file, for example "resume ENG-123 at 15:45". `watch` emits each one when it falls due.

It prints one line per change:

- a PR opened for a Claim, or a new head commit;
- a review submitted;
- a comment or review thread, new or changed;
- a check result;
- the PR closed;
- the PR merged;
- a Worker or Reviewer process exit, with its status or with none;
- a timer due.

It does not use GitHub's Events API, which has no check events and can lag by hours. Webhook forwarding with `gh webhook forward` may be added later as a faster source. Today it needs repository hook permission, allows one forwarder per repository, and has an open bug that makes it exit when the server disconnects.

### Modes

- **Stream:** `devctl watch` prints one line per event until it is stopped.
- **Once:** `devctl watch --once` waits for the next event, prints it and exits.

### Waking the Lead

- **Claude Code.** The Lead runs the stream under its Monitor tool, and each line wakes it. A Monitor watch lasts at most 30 minutes, so the Lead re-arms it. A background task running `--once` also works: its exit wakes the Lead.
- **Codex.** The Lead registers its Session ID with `watch`. The watcher pushes each event into that Session with `codex queue --thread <id> --message ...`. Codex's release notes say this wakes idle sessions; that is unverified for interactive sessions (section 11). The fallback is a foreground `devctl watch --once`. It costs one model turn each time the command times out.
- **agy** is not a Lead yet.

## 5. Reconciliation and actions

Events only wake the Lead. At start-up and on every wake, the Lead reconciles every live Claim with the current state in GitHub and Linear, then acts. An event missed during a sleep, or while no Lead ran, therefore costs only latency.

| Event or state found | The Lead's action |
| --- | --- |
| PR opened, or a new head commit | Start a Reviewer on the head commit |
| Changes requested, by the Reviewer or the owner | Start a new Worker with the findings and enough context to fix them. The review loop repeats, a new Worker then a new Reviewer, until the Reviewer approves |
| `devctl check` failed | Start a new Worker with the failure |
| The owner approved | Start a Worker for the merge step (section 7) |
| A comment after the approval | The merge-step Worker addresses it first (section 7) |
| The Claim's own PR closed without merging | Check the issue in Linear (section 6) |
| PR merged by the owner directly | Release the Claim with `devctl dispatch --release`, which also removes a clean worktree |
| The issue left its started state in Linear | Close the PR and release the Claim (section 6) |
| A Worker or Reviewer Session ended | Read how it ended (section 8) |
| A timer fell due | Resume the Session it names (section 8) |

Each row means a Claim's own PR, as Spec 1 section 6 defines it. A closed PR of an earlier Claim of the same issue is never an event or a state to act on. The Lead gives it to the new Worker only as context (section 3).

## 6. Linear

Scope decisions are made in Linear. A deferred issue moves to Backlog and a dropped one to Canceled. An issue can also be rescoped or labelled `needs-human`. A started state is a workflow state of Linear's `started` type, such as In Progress or In Review.

- When an issue with a live Claim leaves its started state, the Lead closes the PR and releases the Claim.
- When a Claim's own PR closes on GitHub while its issue is still started, the Lead asks the owner what happened. It never guesses a Linear state.
- Linear gives the Lead no event source. On every wake the Lead reads the state of each live Claim's issue through Linear's MCP.

This relies on two facts:

- Linear's GitHub integration moves an issue when its PR opens (In Progress by default; Spec 1's Setup configures In Review) and when the PR merges (Done by default). It has no event for a PR closed without merging.
- Cancelling a Linear issue closes its linked open PRs.

## 7. The merge step

In Walk the owner reviews and approves, and a Worker merges.

1. The owner approves the PR on GitHub.
2. The Lead starts a Worker for the merge step.
3. The Worker first addresses every comment newer than the approval. If a comment needs a code change, the Worker pushes it. GitHub dismisses the stale approval and the PR returns to the owner. The push also starts a new Reviewer (section 5).
4. Otherwise the Worker runs `devctl merge <issue-id>` (Spec 1 section 6). The gate refuses unless the head commit has a code owner's approval, no "changes requested" review is outstanding, no review thread is unresolved, `devctl check` passed on the head, and the branch is a live Claim.
5. When all hold, `devctl merge` squash-merges as the Worker App, deletes the branch, removes the worktree if it is clean or reports it, and appends its gate log line.

The ruleset allows squash merges only, for agent and human PRs alike (Spec 1 section 8).

## 8. Stops, resume and Takeover

A stop is a Worker or Reviewer Session that ended without a PR or a clear result.

1. The Lead resumes the stopped Session once with "continue" and reads the reply. It sends at most one automatic "continue" per stop.
2. If the Session continues, the stop was transient.
3. If the reply reports a usage limit with a reset time, the Lead registers a timer and resumes the same Session at that time.
4. If there is no reset time, or the reply shows another error, the Lead asks the owner to choose: resume now (credits added), resume later, or a Takeover.

Detection reads the Session's reply, never an exit code: no Harness documents an exit code for a quota stop. Only an interactive Claude Code Session continues by itself after a reset. Headless CLIs do not, so the Lead resumes a detached Worker or Reviewer itself.

### Takeover

Takeover is the owner's choice, never automatic. A continuation on the same Harness is not a Takeover: it is a plain resume of the same Session.

An Agent from a different Provider takes over with the Claim's branch, worktree and PR. It reads the stopped Session's transcript when it can, from the place the Session registry records:

| Harness | Transcript | Read in a Takeover |
| --- | --- | --- |
| Claude Code | JSONL, `~/.claude/projects/<project>/<session-id>.jsonl` | Yes |
| Codex | JSONL, `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | Yes |
| agy | One SQLite database per conversation, `~/.gemini/antigravity-cli/conversations/<id>.db` | Not yet. A backlog item adds a reader |

No progress notes are written. The transcript and the branch are the record.

## 9. Launching Sessions without an orchestrator

The Lead launches each Worker and Reviewer detached, through a small wrapper that writes an exit-status file when the Session's process exits. A Worker starts from the command that `devctl dispatch` prints. `devctl watch` observes the status files. devctl still never runs a Session.

[ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md) records this choice and its three costs:

- A Session launched from the Lead inherits the Lead's sandbox, so the launch must run outside it (section 10).
- A laptop sleep or reboot kills Workers silently. The watcher sees an exit with no status, and section 8's "continue" recovers the Session.
- Exit detection uses the status file, not process IDs.

This choice is reversed when rapid-orchestrator is built. These costs are evidence for building it before Flight.

## 10. Sandbox and permissions

### Principles

- In Walk a sandbox is defense in depth. It is on for Workers and Reviewers wherever a live trial proves that Harness can do the role's whole job inside it.
- Where a trial shows a Harness cannot, its sandbox is off for that role, and Setup records a gap for that Harness.
- The Lead keeps the owner's normal settings.
- No Session uses a blanket bypass flag, except as a fallback recorded as a Setup gap. The flags are Claude Code's `bypassPermissions` mode and `--dangerously-skip-permissions`, Codex's `danger-full-access`, and agy's `--dangerously-skip-permissions`.
- Child processes inherit the sandbox in all three Harnesses, and nested sandboxes generally fail. One report has `codex exec` crashing inside Claude Code's sandbox. Workers and Reviewers are therefore never launched from inside a sandbox.

### Network

- Shell commands in a sandboxed Session reach only a strict allowlist: `github.com`, `api.github.com`, `pypi.org`, `files.pythonhosted.org`, and the domains the project lists in `project.toml`. An unlisted host is refused, never prompted.
- Research tools run inside the Harness process, outside the shell sandbox. Web fetch, web search and read-only MCP servers such as context7 are allowed in every Worker and Reviewer Session. Linear's MCP is reached the same way.
- For agy, `read_url` rules allow https while shell commands stay restricted. A trial confirms this.
- Accepted risk in Walk: a fetched URL can carry data out. Flight revisits it.

### Settings per role and Harness

Live trials fix each cell's exact flags and settings (section 11).

| Role | Claude Code | Codex | agy |
| --- | --- | --- | --- |
| Lead | The owner's settings. Only the Worker launch wrapper runs unsandboxed, through `sandbox.excludedCommands` | The owner's settings. The launch runs through a prefix rule or a per-launch approval | Not a Lead |
| Worker | Sandbox on: `sandbox.enabled`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`, the strict network allowlist, and writable paths for uv's cache. Permission mode `dontAsk`, with sandboxed commands allowed. Research tools allowed | `workspace-write` with network on. Codex's experimental prefix rules let exactly `git add`, `git commit`, `git push` and `./devctl ...` run outside the sandbox without a prompt (trial-gated). If the trial fails, `danger-full-access`, recorded as a Setup gap. Approval `never` | Sandbox on with `--sandbox`. Allow rules for exactly the commands a Worker needs: git, uv, `./devctl` and the test runner. `read_url` for research. Trial-gated |
| Reviewer | As the Worker, but unable to push | `workspace-write` with network on, unable to push | Never a Reviewer |

- **Claude Code Worker.** Its docs say a linked worktree can commit inside the sandbox: the shared `.git` is writable, while its `hooks/` and `config` are not.
- **Codex Worker.** `workspace-write` cannot commit in a linked worktree on macOS, because `.git` is read-only there, and there is no supported fix. The prefix rules exist for that reason.
- **agy Worker.** Headless agy skips a shell command that no rule allows and still exits 0. The Lead therefore treats any skip notice on stderr as a failure. If the trial fails, this spec finds workarounds rather than dropping agy.
- **Reviewer.** It runs in its own worktree at the PR's head commit, sandboxed with the network allowlist, and cannot push. `devctl review` already ties its verdict to that head.
- **Pushes.** Every Worker pushes with `git push`. Which credential that push uses is open (section 12).

## 11. Live trials

Each trial is a real run, recorded under `docs/trials/`. A simulated run does not count.

- **Claude Code Lead wakes:** the Monitor tool waking the Lead on each `devctl watch` line and being re-armed after 30 minutes; a background `devctl watch --once` task waking it on exit.
- **Codex Lead wakes:** `codex queue --thread <id> --message ...` waking an idle interactive Codex Session.
- **The Codex fallback:** a foreground `devctl watch --once`, and the model turns it costs per command timeout.
- **Nested launch:** each Lead, Claude Code and Codex, launching Workers through the unsandboxed wrapper, and the wrapper's exit-status file.
- **Claude Code Worker sandbox:** a commit in a linked worktree, uv with its cache, `git push` through the sandbox's proxy, and `./devctl` GitHub calls, which read an App key from the Keychain.
- **Claude Code research:** web fetch, web search, context7 and Linear's MCP answering without a prompt in a sandboxed Worker and Reviewer under permission mode `dontAsk`.
- **Codex prefix rules:** `git add`, `git commit`, `git push` and `./devctl ...` running outside the `workspace-write` sandbox without a prompt.
- **Codex research:** web search and MCP servers, which run outside the shell sandbox, working from a `workspace-write` Session.
- **agy sandbox:** `--sandbox` with allow rules: a commit, a push, uv, Linear's MCP, `read_url` research, and detection of skip notices on stderr.
- **Quota stops:** each Harness's reply when a usage limit stops it, and resuming the same Session by its ID.
- **The review loop with subagents:** whether the Lead can drive it until a Reviewer approves (Spec 1 section 10).
- **agy with Linear's MCP** (Spec 1 section 10).
- **Reviewer confinement:** each Reviewer configuration cannot push, and `./devctl review` posts from inside its sandbox.

## 12. Not yet designed

These are open. Each is designed with the owner before the plan. Some also change Spec 1's commands or Setup, and Spec 1 section 11 lists those: reading check runs, attempts and `--retry`, closing a PR on release, the push credential, and sandbox settings at Setup.

- **Planning and gardening.** `rs-plan` with its upstream skills (`rs-grilling`, `rs-domain-modeling`, `rs-to-spec`, `rs-to-tickets`), `rs-garden`, `rs-playbook-author` and the corrections ledger's format.
- **The other Walk skills.** `rs-walk`, `rs-work` and `rs-review` beyond what this draft fixes, and how each role follows the skills at the PR's base commit (Spec 1 section 7). The Reviewer's worktree is at the PR head, so a PR that edits a skill would otherwise edit its own Reviewer's instructions.
- **Start commands and the wrapper.** The exact start command templates per Harness and role (Spec 1 section 6, `devctl dispatch` step 7). The wrapper's place in the Kit and its status file's path and format. How `watch` tells a Session that ended with no status from one still running, without process IDs. Where the wrapper keeps stderr for agy's skip notices.
- **Reviewer starts.** How a Reviewer's worktree at the PR head is created and its start command produced.
- **Attempts and `--retry`.** Whether each later Worker (review loop, failed check, merge step, Takeover) is a `dispatch --retry` admission that counts toward `attempt_limit`, 3 by default. Whether `--retry` refuses a Claim that is not live, so that a Claim whose own PR is merged or closed must be released before the issue is dispatched again.
- **Owner approval of starts.** The design says the owner approves each agent start, while section 5 starts Reviewers and later Workers on events. Which starts need the owner's word.
- **Pushes from a running Worker.** Whether each push starts a Reviewer, or the Lead waits for the Worker's Session to end.
- **A refused merge.** What the merge-step Worker does when `devctl merge` refuses, for example while `devctl check` is still running. The Worker also runs inside the worktree that `devctl merge` removes.
- **Reading check runs for `devctl merge`.** Spec 1's plan 4 needs this. The Worker App has no Checks permission (Spec 1 section 3), and GitHub's API needs Checks read access to list a private repository's check runs. Either the Worker App gains read-only Checks, or `devctl merge` reads checks with the owner's `gh` login, as `doctor` does.
- **Closing a PR when its issue leaves the started state.** Whether `--release` closes it by deleting its branch, which closes an open PR on GitHub, or the Lead closes it first with a comment, and under which identity.
- **`devctl watch` details.** Its options and line format, how a Codex Lead registers its Session ID, and the timer file's path and format. Which GitHub identity it polls with: the Worker App or the owner's `gh` login. The choice sets which rate limit the polls spend, and whether `watch` can read a private repository's check runs, which needs Checks read access (Spec 1 section 3).
- **The push credential.** Which credential a Worker's own `git push` uses. Section 10 lets each Worker Harness run `git push`: the Codex prefix rules, the Claude Code sandbox trial and agy's git allow rule. Spec 1 requires every agent GitHub write to go through the Worker App, and only devctl's `GIT_ASKPASS` helper holds that App's token. Without another credential, a raw push uses the owner's own git credentials. The owner then becomes the last pusher, so the ruleset's last-push rule rejects the owner's own approval and `devctl merge` is refused. GitHub also credits the agent's write to the owner, which [ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md) rejects. Pushing with `git push` stands; only its credential is open.
- **Sandbox settings at Setup.** Who writes each Worker and Reviewer Harness's sandbox settings from section 10, where they live, and when Setup records a gap for a role whose trial failed. Spec 1's `rs-setup` has no step for either.
- **Telling the owner.** How the Lead reports a PR awaiting review, a closed PR whose issue is still started, and a stop that needs a choice.
- **Network allowlist details.** The `project.toml` key for extra domains. How Codex holds shell commands to the allowlist, since the table turns its network on and names no domain list.
- **Reviewer push block.** How each Reviewer configuration is kept from pushing.
- **Takeover records.** How the Session registry names a Takeover Agent that `project.toml` does not list.
- **Linear conventions beyond Setup.** How the labels `ready-for-agent` and `needs-human` are used; the epic approval state that `rs-setup` creates (Spec 1 section 8). Who moves an issue into a started state at dispatch, before its PR opens. The start comment the Lead writes when a Worker Harness cannot reach Linear's MCP (Spec 1 section 11).
