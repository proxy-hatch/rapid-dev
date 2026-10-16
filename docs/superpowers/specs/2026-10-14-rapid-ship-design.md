# rapid-ship design

*Revised on 2026-10-16 to stop at the team-management boundary ([ADR 0004](../../adr/0004-team-management-boundary.md)). Replaces the 2026-10-10 framework design. Terms follow `GLOSSARY.md` at the repository root.*

## The problem

Coding agents can now finish most well-specified tasks, and every major Harness can run a team of them: a lead Session starts subagents, runs them in parallel and collects their results. What no Harness supplies is what a senior engineer gives a team of people: an architecture to build into, delivery broken into pieces that can run in parallel, and a code-quality bar held on every change. Left alone, agents take shortcuts: they weaken a test, edit the CI that judges them, or repeat a mistake they were corrected for the day before.

rapid-ship supplies those three things to a repository and to whichever Harness the owner works in. The approach follows the owner's *Trust-First Agentic Engineering Playbook*: enforce each rule at the layer that fits its purpose, turn every repeated correction into a rule that prevents it, and widen autonomy as measured results support it, which the owner judges.

## The boundary

rapid-ship does for a team of coding agents what a senior engineer, or a team of seniors, does for a team of people. It does not run the team ([ADR 0004](../../adr/0004-team-management-boundary.md)).

| rapid-ship | The owner's Harness |
| --- | --- |
| Helps write ARCHITECTURE.md, ADRs and feature designs | Starts, watches, resumes and hands over Sessions |
| Breaks a design down in the owner's issue tracker | Runs Workers and Reviewers as subagents or as other vendors' CLIs |
| Installs the Kit: devctl, instructions, Patterns, guardrails and skills | Follows the Lead brief as closely as it can, including each subagent's model |
| Helps the owner write the Lead brief | Pushes, opens PRs, posts reviews and merges, within the guardrails and the ruleset |
| Reports metrics and Suggested threshold breaches | Schedules recurring work, such as gardening |

rapid-ship never pushes, reviews or merges as a step in a flow, and never moves a project between Modes. devctl never talks to the issue tracker. rapid-ship runs no service, daemon, container or local database: it is files in the repository, plus a small command that writes them. It works with any Harness and any Provider, whether a subscription, an API key or a gateway, and nothing it ships needs an API key. GitHub is the only supported remote.

## Who does what

The **owner** designs with rapid-ship's help, chooses the Mode, and decides on every PR the escalation list brings them.

The **Lead** is the Session the owner works with. At the start of a Session the owner runs `rs-lead`, which builds the **Lead brief** from `.rapid-ship/project.toml` and from what the owner wants done now:

- The **Focus** says what to work on now: a milestone or chosen tasks, and in Walk a cap on parallel Workers. It changes often and is never stored.
- The **escalation list** names the kinds of PR the Lead must bring to the owner instead of merging them itself. It sets the [Mode](#modes).
- The optional **Roster** names the Agent, a Harness and an exact model, for each role. Only an owner who uses more than one Provider needs one; otherwise the Lead's Harness chooses its subagents' models.

The escalation list and the Roster live in `project.toml`, which is in the Protected set, so changing the Mode or the Roster is a PR the owner approves. How closely the Lead follows the brief, including using each model exactly as named, is up to its Harness. rapid-ship cannot see which model a subagent received, so "no silent model fallback" is advice.

The **Worker** and the **Reviewer** are roles the Lead's Harness runs. A Worker implements one task by following `rs-work`. A Reviewer judges one change by following `rs-review` and tags each finding blocking or nit, with the rung that would stop it recurring. The Lead tells a generic subagent to follow the skill, or follows it itself. A Reviewer from a different Provider than the Worker is recommended.

No Harness runs another vendor's model as a native subagent. A Roster that crosses Providers has three routes: the Lead runs the other vendor's CLI from its shell (`codex exec`, `agy -p`, or `claude -p` without `--bare`, because bare mode would skip the Kit's hooks and CLAUDE.md), uses OpenAI's official Codex plugin for Claude Code, or uses agy's catalog of Claude and GPT-OSS models. When `rs-lead` offers to run agy from another Harness's shell, it warns that Google's consumer terms do not support that use.

The skills describe how a Lead runs a task, and rapid-ship runs none of it. The Lead starts a Worker for each task in the Focus whose blockers are done, up to the cap. The Worker works test-first, runs `devctl check` and opens a PR, and CI runs the check in full. A Reviewer posts its findings on the PR, and the Lead sends each blocking finding back to a Worker until none is left. The Lead then brings the PR to the owner if its kind is on the escalation list, and merges it otherwise.

## Design and Breakdown

`rs-design` interviews the owner first, then writes a spec. It maintains ARCHITECTURE.md and the ADRs, which live in the repository. Feature designs live wherever the owner keeps them: in the tracker's documents or in the repository.

`rs-breakdown` turns a design into four levels. Breakdown happens whenever there is new work, in either Mode.

| Level | What it is |
| --- | --- |
| Milestone | A dated delivery checkpoint that can be demonstrated: the unit of work the owner hands a Lead |
| Epic | One capability inside a milestone, delivered in several PRs. It links to its spec |
| Story | Optional: a user-visible slice of an epic, used only when the epic ships in more than one slice |
| Task | Exactly one PR, small enough for one review (Spec 1 proposes a 500-line diff cap), with acceptance criteria, a test plan and blocked-by links, so a Lead can run independent tasks in parallel |

The levels are tracker-neutral, and rapid-ship supports whichever tracker the owner uses. The skills reach it through the Harness's own connection, an MCP server or a CLI. Each tracker gets one mapping note. Linear's is first: one Linear project per product, a milestone as a project milestone, an epic as a parent issue, a story as a sub-issue, and a task as a leaf issue with "blocked by" relations.

## Standards

`rs-setup` establishes the standards with the owner in a new repository. In an existing one, `rs-health` audits them and turns its findings into a standards milestone that a Lead works through; it never edits the repository itself.

- **Instructions:** AGENTS.md files, one per maintained directory, are the single instruction source. A real `CLAUDE.md` contains `@AGENTS.md`.
- **README.md and ARCHITECTURE.md:** the Kit seeds skeletons, and `devctl check` verifies that they and their links exist.
- **Patterns:** the Kit ships the mechanism, not code. A Pattern file names the recurring task, its reference implementation and the check that enforces it, and `devctl check` verifies that the reference and the check exist. In a new repository `rs-setup` sets the first Patterns with the owner. In an existing one, `rs-health` finds recurring tasks done several ways and proposes one reference for each. Agents may add a Pattern; changing an existing one needs the owner.
- **Feature map:** one file per feature says where it is entered, what data it touches, and how to observe and reproduce it.

## How the bar is held

Every rule sits on one of four rungs. A rule goes on the rung that fits its purpose, and one bad pattern can need more than one rung.

| Rung | What it is | Example |
| --- | --- | --- |
| 1. Safe interfaces | One supported way to do a recurring task, with the bypass banned | Configuration is read only through `settings`; `os.environ` is banned elsewhere |
| 2. Automated checks | `devctl check`, required in CI | Lint, types, tests, import contracts, the diff policy |
| 3. Judgement | Skills, advisory Rules and the Reviewer | "Prefer deep modules with small interfaces" |
| 4. The owner | Human approval | Changes to CI, guardrails, skills or settings |

A safe interface removes a structural way to misuse something. A check catches local or stylistic problems, such as line length or `Any` in weakly typed code. The two often work together: in rung 1's example, `settings` is the interface and a lint rule bans the bypass. Skills and advisory Rules are the fallback for what no interface or check can carry.

`devctl check` covers everything a machine can decide without a model, so CI stays deterministic and needs no model sign-in. Beyond lint, types and tests, it confirms that the instructions, README.md, ARCHITECTURE.md, the feature map and the Patterns exist and that their links resolve. Its diff policy fails a change that quietly deletes a test or turns an assertion into a tautology; every removed test is declared in the PR. There are no ratchets: an unsafe pattern is prohibited outright, and a legitimate exception is an entry in an exceptions file that only the owner can approve.

**Harness guardrails** bring the rungs into each Harness's own loop. The Kit ships project settings for Claude Code, Codex and agy that deny `--no-verify`, force pushes, `gh pr merge --admin` and hand edits to `.rapid-ship/kit.lock`. They ask before an edit to the Protected set. A Stop hook runs `devctl check --tier fast` when the agent says it is done, and sends the agent back when it fails. These settings files join the Protected set. Sandboxing is a recommendation that `rs-setup` offers, not a default, because subagents inherit the sandbox of the owner's own Session. Any other Harness gets AGENTS.md, `.agents/skills`, the pre-commit hook and CI; rungs 2 and 4 hold for it through git and GitHub. Supporting another Harness takes one more template layer.

The **Protected set** is the kinds of change that need the owner's approval in every Mode: changes to CI and the guardrail settings, devctl, the skills and the other agent instructions, rapid-ship's settings and exceptions, the check tools' settings files, and an existing Pattern. CODEOWNERS assigns them to the owner, and GitHub reads it from the base branch, so a PR cannot exempt itself.

**GitHub is the final gate.** One ruleset on the default branch requires a PR with code-owner review, every review thread resolved, and a passing `devctl check` reported by GitHub Actions. It allows squash merges only and blocks force pushes. Only the repository admin role may bypass it, and only when merging a PR. `rs-setup` applies it and `devctl doctor` checks it. GitHub Free private repositories have no rulesets, so there GitHub requires neither rung 2 nor rung 4 before a merge.

**Agent identity** is optional ([ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md)). `rapid-ship app` creates two GitHub Apps for the owner: one opens and merges PRs, the other posts reviews. With it on, agents make their GitHub writes through one thin devctl command that runs `gh` and `git push` with an App's short-lived token, and the Harness settings deny `git push` and `gh` writes made as the owner. GitHub never lets a PR's author approve or request changes on it, on any plan, so Agent identity buys four things:

1. The owner can formally approve agent PRs, so merges need no admin bypass. In a team, teammates' approvals cover this without it.
2. Reviewer verdicts are real GitHub reviews, so Revisions can be counted.
3. Agent PRs can be told apart, which every per-agent-PR metric needs.
4. CODEOWNERS binds the Lead in Flight, because an App cannot use the owner's bypass.

Without it, agents act as the owner. `rs-setup` explains the trade and the owner opts in or not.

One limit is worth stating plainly. Agents run on the owner's machine under the owner's sign-ins, and deny rules can be bypassed, so a misbehaving agent could act as the owner, with or without Agent identity. Guardrails are advice; the ruleset and CODEOWNERS on GitHub are the enforcement.

## Modes

The Mode is the owner's choice, set by the escalation list. In **Walk** every PR is on it. In **Flight** only the Protected set and the kinds the owner adds are on it, such as migrations, public API changes or removed behavioural tests; the Lead merges everything else once its checks and review pass. Anything between is allowed.

GitHub enforces the Protected set through CODEOWNERS. The kinds the owner adds are advice to the Lead, because CODEOWNERS matches paths only. `rs-lead` writes the escalation list into `project.toml` and proposes the matching CODEOWNERS change as a Protected PR. With Agent identity, CODEOWNERS `*` enforces Walk, and Flight narrows CODEOWNERS to the Protected set. Without it, an agent's PR comes from the owner's account, so for a solo owner only the admin bypass can merge it, and the deny rule on `gh pr merge --admin` keeps the Lead from using that bypass. Flight is still available without Agent identity: `rs-lead` explains that the ruleset must then drop its review requirement, so the Protected set becomes advice. The owner decides and changes the repository setting.

When to fly is mostly the owner's call, made from the metrics. rapid-ship has no gate into Flight and never returns a project to Walk. It helps the owner fly through the Lead brief, in two ways:

1. **Which PRs reach the owner.** A shorter escalation list speeds up delivery.
2. **Which review findings trigger another round.** The Lead always fixes blocking findings and skips nits, which upholds quality and maintainability without endless rounds. These triage rules live in the text of `rs-review` and `rs-lead`, not in settings.

## Metrics

rapid-ship provides a basic set of metrics that a project can extend. Each comes deterministically from GitHub and git, with no model and no attribution step.

| Metric | Without Agent identity |
| --- | --- |
| Revisions per merged agent PR | Unknown |
| Reverts: merged PRs that a later commit reverted | Counted over all PRs |
| Red default-branch CI after a merge | Counted over all PRs |
| Agent PRs the owner closed unmerged | Counted over all PRs |
| Corrections by rung, from the Corrections ledger | Counted |

The owner reads them with `devctl metrics`, or from an optional scheduled GitHub Action that posts the same report. Without Agent identity, a metric that must tell agents from the owner reports "unknown: needs Agent identity"; nothing relies on markers that agents set themselves. A missing metric is unknown, never zero.

The owner records **Suggested thresholds** at Setup. rapid-ship reports a breach and takes no action. Setting up Alarms is a recommendation left to the owner. Metrics the owner defines, such as Alarms or deploy rollbacks, plug in as project-defined metrics.

## Gardening

`rs-garden` covers two things:

- **Corrections**, read from the review threads on PRs, from the Reviewer and the owner. A model reads the threads, so this works without Agent identity. The Lead brief also asks the Lead to add Corrections the owner gives in the Session to the ledger; that part is advisory.
- **Drift**: a stale AGENTS.md, ARCHITECTURE.md or README.md, code that departs from its Pattern, exceptions nothing uses, and dead code.

The gardener shares one audit with `rs-health`, which runs it once at adoption. The gardener reruns it over the changes since its last pass and adds the new Corrections. For each repeated Correction it proposes a fix on the rung that fits: a safe interface for structural misuse, a check for local or stylistic problems, or both; a skill or advisory Rule only when neither can carry it. Rule changes come back as proposed tasks. Doc-only drift fixes come back as one PR per pass.

`rs-garden` is a skill the owner runs. Scheduling it is the Harness's job; the documentation shows each Harness's scheduler and the operating system's cron.

## What rapid-ship ships

- **The `rapid-ship` command** writes and updates the Kit. `init` vendors it, `status` compares the repository with the Kit lock, `sync` proposes Kit updates as a PR, and `app` creates the Apps for Agent identity. `uvx` fetches it from a git tag of this repository; it is not on PyPI yet. `rs-setup`, not a command, marks an existing project's suppressions (a Proposal in Spec 1).
- **The Kit** is what `init` vendors: devctl's source, the instruction and document skeletons, the Pattern and feature-map formats, the Harness guardrail settings, a pre-commit hook, a CI workflow, CODEOWNERS, the `.rapid-ship/` settings and the skills. `init` records each file as managed, which `sync` keeps current, or seeded, which the project owns from the start. A managed file the project edits becomes its own until `rapid-ship sync --revert`.
- **devctl** is the repository's own CLI for people, agents and CI. Its commands are `check`, `doctor` and `metrics`, plus `as`, the thin command for `gh` and `git push` under Agent identity, and `hook`, which the Harness guardrail settings call. Spec 1 proposes both names. `doctor --skills` asks each Harness which Kit skills it loads, and doctor checks the Apps only under Agent identity. A project adds its own verbs.

Eight skills, from `rs-setup` to `rs-garden`, carry the work. The engineering skills forked for TDD and debugging stay in the Kit too, and Spec 1 proposes five more, including `rs-pr`. Every Kit skill's name starts with `rs-`.

| Skill | What it does |
| --- | --- |
| `rs-setup` | Sets up a new repository or adopts an existing one: the Kit, the README, ARCHITECTURE and AGENTS documents, the first Patterns, the Harness guardrails and the ruleset; optionally Agent identity and the metrics Action |
| `rs-health` | Audits a repository and returns a standards milestone |
| `rs-design` | Interviews the owner; writes feature designs, ADRs and ARCHITECTURE.md |
| `rs-breakdown` | Turns a design into milestones, epics, stories and tasks in the tracker |
| `rs-lead` | Builds the Lead brief, triages review findings and helps the owner fly |
| `rs-work` | How a Worker meets the bar on one task |
| `rs-review` | How a Reviewer judges one change |
| `rs-garden` | Records Corrections and finds drift |

There is no metrics skill: `rs-setup` records the thresholds, and project-defined metrics are documented.

Each skill is one real directory under `.agents/skills/<name>/`, which Codex and agy read. Claude Code, the only major agent that cannot, gets a relative symlink per skill, `.claude/skills/<name> -> ../../.agents/skills/<name>`, recorded in the Kit lock. `SKILL.md` itself is never a symlink, because Codex rejects one. opencode and Gemini CLI read both directories and warn about duplicates. `rs-work` and `rs-review` ship with no per-Harness subagent definitions. The owner's machine must run macOS for now, and `devctl check` also runs on Linux, as CI does. Windows is not supported yet, because git there can check the skill links out as plain files (backlog item PRO-104).

## Dog-fooding

*This section describes this repository's own configuration, not product behaviour.* rapid-ship vendors its own Kit and is validated on itself and on its sample project, hello-rapid-ship. It records its own choices as rules in its root AGENTS.md: Linear is its tracker; its agents sign in with vendor subscriptions only, and the owner accepts the risk of running agy inside another Session ([ADR 0001](../../adr/0001-subscription-logins-only.md)); and agy is never a Reviewer here.

## Delivery

Three specs:

1. **[Kit and Setup](2026-10-14-kit-and-setup-design.md)**, mostly built: the `rapid-ship` command, `devctl check` and `doctor`, the Harness guardrails, the README and ARCHITECTURE seeds, the Pattern mechanism, optional Agent identity, `rs-setup` and `rs-health`. Plans 1 to 3 built `init`, `status`, `sync` and `devctl check`. The [plan index](../plans/2026-10-14-kit-and-setup.md) lists the rest: plan 4, doctor and Agent identity; plan 5, Kit standards and Harness guardrails; plan 6, `rs-setup` and `rs-health`.
2. **[Delivery skills](2026-10-16-delivery-skills-design.md):** `rs-design`, `rs-breakdown`, `rs-lead`, `rs-work`, `rs-review` and the tracker mapping notes.
3. **[Metrics and gardening](2026-10-16-metrics-and-gardening-design.md):** `devctl metrics`, the scheduled Action, Suggested thresholds, project-defined metrics, the Corrections ledger and `rs-garden`.

Specs 2 and 3 get their own plans later. Deferred until the product works: a TypeScript stack kit, several stacks in one repository, mapping notes for other trackers, Windows, and rewriting the documentation site.

[ADR 0002](../../adr/0002-github-gates-merges-reviews-run-locally.md) and [ADR 0004](../../adr/0004-team-management-boundary.md) record decisions with lasting trade-offs. [ADR 0001](../../adr/0001-subscription-logins-only.md) is this repository's own rule, and [ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md) is superseded.

## Open

- **The diff cap's rule (Proposal in Spec 1, section 5).** A Task fits devctl's 500-line diff cap, but `devctl check` today caps only each source file at 500 lines. Spec 1 proposes that the `diff` step fail a change of more than 500 added and removed lines, not counting binary, Kit-managed and lock files, unless its Evidence declares `Over the diff cap:` for an overage the owner accepted.
- **A default escalation kind (proposal).** A PR that reached 3 Revision rounds goes to the owner in every Mode. Spec 2 settles it with `rs-lead`.
- **`devctl as` and `devctl hook` (Proposals in Spec 1, section 6).** The names and interfaces of the thin command for `gh` and `git push` under Agent identity, and of the command the Harness guardrails call.
- **The ruleset's approval count in Flight.** With Agent identity, a PR outside the Protected set needs either an approval GitHub counts from the reviewing App, or a ruleset that requires code-owner review and no other approval. Spec 1 decides, after its live ruleset trial.

## What changed on 2026-10-16

The design moved to the team-management boundary. These parts were cut:

- `devctl dispatch`, `pr`, `review`, `merge` and `watch`; Claims, Release, Takeover, the Session registry and the gate log.
- The Lead's event loop (the Walk-flow draft), per-role sandboxed launches, `attempt_limit`, `review_round_limit` and the five-Worker cap.
- rapid-orchestrator, dropped rather than deferred.
- The Flight lease, automatic demotion, Pre-flight, the attack-PR set and the Investigator. Rollbacks became a project-defined metric.
- Linear as the only tracker, subscription sign-ins as a product rule, Agent identity as a requirement, doctor's tracker item, and the test-bed spec.
- The activity "Plan" became Breakdown, and `rs-plan` and `rs-walk` gave way to `rs-breakdown` and `rs-lead`.
