# rapid-ship design

*Proposed on 2026-10-14. Replaces the 2026-10-10 framework design.*

## The problem

Coding agents can now finish most well-specified tasks, but one person can supervise only three to five of them at a time. Left alone, agents take shortcuts: they weaken a test, edit the CI that judges them, or repeat a mistake they were corrected for the day before.

rapid-ship lets a project hand more of its delivery to agents while keeping evidence that the work is right. It also takes that autonomy back automatically when the evidence stops arriving. The approach follows the owner's *Trust-First Agentic Engineering Playbook*: enforce each rule at the layer that fits its purpose, turn every repeated correction into a rule that prevents it, and widen autonomy only on measured results.

## The path

```text
Setup ──► Walk ──► Pre-flight ──► Flight
           ▲                        │
           └── regression, or no ───┘
               metrics reported
```

**Setup** installs rapid-ship's Kit in the repository: guardrails, a project CLI called devctl, an AGENTS.md tree and a set of skills. It also connects GitHub and Linear and chooses which Agents do the work.

**Walk** is supervised delivery. The owner approves each agent start, reviews each PR and merges it. Up to five Workers run at once. Every Correction the owner or the Reviewer makes is recorded, and repeated ones become checks or skills. Walk is where the project's judgement is taught.

**Pre-flight** is the gate out of Walk. It passes when the metrics meet the owner's thresholds, every enforcement rung is in place, and a fixed set of attack PRs is blocked. It also reads the gate log to confirm that the Lead's proposals agreed with what devctl allowed. The owner then grants Flight.

**Flight** lets agents merge ordinary changes without the owner approving each one. It lasts only while a scheduled job keeps confirming the metrics. If they regress, or the job stops reporting, the project is back in Walk.

Plan is an activity, not a step on this path. Turning a design into tasks happens whenever there is new work, in either Mode.

## What rapid-ship is

rapid-ship runs no service. Everything it provides is files in the project's repository, plus a small command that writes them.

- **The Kit** is what `uvx rapid-ship init` vendors into the repository: devctl's source, the skills, an AGENTS.md skeleton, guardrail settings, a CI workflow and CODEOWNERS. After init the project owns these files. `rapid-ship sync` later proposes Kit updates as a PR. Everything that runs once, such as creating the GitHub Apps, is a `rapid-ship` command, so nothing one-time is left in the project. `uvx` fetches rapid-ship from a git tag of this repository; it is not on PyPI yet.
- **devctl** is the repository's own CLI. People, agents and CI use it repeatedly to check and operate the project. It never starts an agent on its own. Its core commands are `check`, `doctor`, `dispatch`, `pr` and `review`. Plan adds project-specific verbs. In both CLIs each command is a single word followed by arguments.
- **The skills**, all prefixed `rs-`, carry the workflow: `rs-setup`, `rs-plan`, `rs-walk` for the Lead, `rs-work` for Workers, `rs-review` for the Reviewer, `rs-garden` for turning Corrections into rules, and `rs-health` for auditing an existing project. Engineering skills such as TDD and debugging are forked from mattpocock/skills.

Everything else stays where it already belongs. Linear holds specs and tasks. GitHub holds the code, runs CI and decides what may merge. The owner's machine runs the agent Sessions during Walk.

For now Linear is the only supported issue tracker and GitHub the only supported remote. Agents create, read, update and close issues as part of the workflow, so support for other trackers will follow. Another remote host gets a backlog item when a user asks for it.

rapid-ship has no orchestrator, daemon, containers or local database ([ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md)). Agents use their vendors' subscription sign-ins, never API keys or a proxy in front of the vendor ([ADR 0001](../../adr/0001-subscription-logins-only.md)).

## Who does the work

An Agent is a Harness (Claude Code, Codex CLI or Antigravity CLI), an exact model, and a role. Each project names two Agents for delivery: a **Worker**, which implements one task, and a **Reviewer**, which reviews one change. Spec 3 adds a third Agent role, the Investigator, which traces each Rollback and Alarm to the PRs behind it ([How autonomy is earned and lost](#how-autonomy-is-earned-and-lost)). A Reviewer from a different vendor than the Worker is recommended but not required. The chosen model is always used as named. If it is unavailable, the step stops instead of falling back to another model.

Workers and the Reviewer follow the project's skills as they stand at the PR's base commit, so a skill change applies only after the owner merges it. Antigravity CLI also runs from inside another vendor's coding session; this was checked on 2026-10-15 from a Codex CLI session. Google's FAQ says that use is not supported on consumer plans, and the owner accepted that risk in [ADR 0001](../../adr/0001-subscription-logins-only.md).

The **Lead** is the owner's own Session running `rs-walk`. It offers ready tasks, starts Workers, and routes their PRs to review and merge.

## One task in Walk

1. The Lead lists ready tasks from Linear and offers them to the owner.
2. For each task the owner picks, the Lead runs `devctl dispatch`. It claims the task, creates a worktree and prints the command that starts the Worker.
3. The Worker implements the task test-first, runs `devctl check` and opens a PR with `devctl pr`. The PR comes from the Worker App, a GitHub App the owner created, so the owner can approve it.
4. CI runs `devctl check` in full. The branch ruleset requires it to pass.
5. The Reviewer checks the change against the task and the project's standards, then posts its review with `devctl review`. Each finding names the rung or rungs that would stop the mistake recurring. The review comes from a second GitHub App, the Reviewer App, so its approvals and change requests are real GitHub reviews.
6. If changes are needed, the Lead resumes the Worker with the findings, and the loop returns to step 4.
7. The owner reviews and merges. Linear marks the task done.
8. Corrections from the Reviewer and the owner go into the corrections ledger.

## How trust is enforced

Every rule sits on one of four rungs. A rule goes on the rung that fits its purpose, and one bad pattern can need more than one rung.

| Rung | What it is | Example |
| --- | --- | --- |
| 1. Safe interfaces | One supported way to do a recurring task, with the bypass banned | Configuration is read only through `settings`; `os.environ` is banned elsewhere |
| 2. Automated checks | `devctl check`, required in CI | Lint, types, tests, import contracts, the diff policy |
| 3. Judgement | Skills, advisory Rules and the Reviewer | "Prefer deep modules with small interfaces" |
| 4. The owner | Human approval | Changes to CI, guardrails, skills or settings |

Rungs 1 and 2 serve different purposes. A safe interface removes a structural way to misuse something. A check, such as a lint, type or test rule, catches local or stylistic problems, such as line length or `Any` in weakly typed code. The two often work together against one bad pattern: in rung 1's example, `settings` is the interface and a lint rule bans the bypass. Skills and advisory Rules are the fallback for what no interface or check can carry.

`devctl check` covers everything a machine can decide without a model, so CI stays deterministic and needs no model sign-in. Beyond lint, types and tests, it confirms that the feature map and AGENTS.md links are current and that every suppression has an approved exception. It also confirms that a change does not quietly delete a test or replace an assertion with a tautology. Every removed test must be declared in the PR. In Flight, removing a unit test needs nothing more, while removing a behavioural test, such as an integration test, waits for the owner unless the owner turns that off. There are no ratchets. An unsafe pattern is prohibited outright, and a legitimate exception is an entry in an exceptions file that only the owner can approve.

The **Protected set** is the set of paths that need the owner in either Mode: CI and guardrail settings, devctl, the skills, rapid-ship's settings and exceptions, and changes to an existing Pattern. CODEOWNERS enforces it. During Walk, CODEOWNERS assigns every path to the owner; Flight narrows it to the Protected set. GitHub reads CODEOWNERS from the base branch, so a PR cannot exempt itself.

GitHub is the final gate. One ruleset on the default branch requires a PR with code-owner review and a passing `devctl check` reported by GitHub Actions, and it blocks force pushes. Agents act through two GitHub Apps that the owner creates once and installs on each project. The Worker App pushes branches and opens PRs; the Reviewer App posts reviews. Neither can change workflows or settings, and neither is a code owner, so an App's approval never stands in for the owner's. Only the repository admin role may bypass the ruleset, and only when merging a PR. A solo owner therefore merges their own PRs directly, while direct pushes stay blocked. In a team, other people approve and the bypass can be removed.

One limit is worth stating plainly. In Walk, agents run on the owner's machine under the owner's sign-ins, so a misbehaving Worker could act as the owner, including through the owner's bypass. Walk relies on the owner watching. Flight removes that exposure.

## How the path improves

When the owner or the Reviewer corrects an agent, the Correction goes into the ledger with the rung or rungs that would have prevented it. Gardening (`rs-garden`) reads the ledger, groups repeats and proposes a fix on the rung that fits each one: a safe interface for structural misuse, a check for local or stylistic problems, or both together. It proposes a skill or advisory Rule only when no interface or check can carry the fix. Its proposals become ordinary tasks and pass through the same gates as any other change.

Agents also maintain the feature map and the Patterns. The feature map has one file per feature describing where it is entered, what data it touches, how to observe it and how to reproduce it. Each Pattern names its reference implementation and the check that enforces it. Agents may add a Pattern; changing an existing one needs the owner.

## How autonomy is earned and lost

Three measures decide the Mode. Each is counted over merged agent PRs, not weeks.

- **Revisions:** review rounds that ended in changes requested.
- **Rollbacks:** merged PRs later reverted, or deploys rolled back.
- **Alarms:** released behaviour that breached a budget set during Plan, such as a failed probe or red CI on the default branch.

By default, promotion looks at the last 30 merged agent PRs and demotion at the last 20. Each window allows, on average per merged agent PR, at most 3 Revisions, 0.1 Rollbacks and 0.2 Alarms. That is at most 2 Rollbacks and 4 Alarms in 20 PRs, or 3 and 6 in 30. The owner can change any threshold at any time.

Rollbacks and Alarms lag the deploy by varying times, so the PR behind each one is not obvious. An **Investigator**, a third Agent role beside the Worker and the Reviewer, attributes each one to the merged PR or PRs that caused it. The metrics count the Investigator's attribution. A Rollback or Alarm that the Investigator has not yet attributed counts as unknown, not zero, and blocks promotion. The Investigator also decides how to handle each Alarm. With significant user impact, it rolls back and proposes a fix PR. With minor service degradation, it proposes a fix PR and the project rolls forward. In Walk the owner approves the Investigator's decision before it acts.

Metrics can end Flight but never start it. Missing data counts as unknown and blocks promotion. Flight is also a lease that the scheduled metrics job must keep renewing, so a broken job ends Flight instead of extending it.

## Flight, later

Flight is designed but not built. Research found that it can run without an orchestrator if eight deterministic pieces surround the model-driven flow. Three matter most: no agent holds the owner's GitHub credentials, the Reviewer's verdict becomes a required check posted by trusted code, and a merge-time gate fails closed. Vendor-hosted agents may join a project only if they run on a subscription and do not act as the owner's GitHub identity. The pieces are designed in detail when a project first reaches Pre-flight. The [Flight research note](../../trials/2026-10-13-flight-without-orchestrator.md) lists all eight. If they prove insufficient, the deferred rapid-orchestrator returns; its context is kept in [the archive](../../archive/orchestrator/README.md).

## Delivery

Four specs, built in order:

1. **[Kit and Setup](2026-10-14-kit-and-setup-design.md):** remove the old controller, then build the `rapid-ship` command, devctl's core commands, `rs-setup` and `rs-health`.
2. **The Walk flow:** `rs-plan`, `rs-walk`, `rs-work`, `rs-review` and `rs-garden`, Linear conventions and the corrections ledger.
3. **Metrics and the gate:** collecting metrics from GitHub, the Investigator, the Mode file and Flight lease, the Pre-flight report and the attack-PR set.
4. **The test bed:** a small FastAPI service with a synthetic production, driven through Walk, with seeded regressions that prove demotion works.

Deferred until the product works: building Flight, a TypeScript stack kit, several stacks in one repository for monorepos, rewriting the documentation site, Linear delegation for Claude or Antigravity, and measuring how many Sessions a subscription completes per usage window.

Decisions with lasting trade-offs are recorded in [ADR 0001](../../adr/0001-subscription-logins-only.md), [ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md) and [ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md).
