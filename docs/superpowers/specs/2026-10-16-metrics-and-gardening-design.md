# Spec 3: Metrics and gardening

**Status: proposed on 2026-10-16 and awaiting the owner's review.** This is the third of the three specs listed in the [rapid-ship design](2026-10-14-rapid-ship-design.md). Terms follow `GLOSSARY.md` at the repository root.

## 1. Scope and outcome

When this spec is built, an owner can:

- run `./devctl metrics` and read the basic metrics for the last 30 merged PRs, computed from GitHub and git without a model, with each Suggested threshold marked ok, breached or unknown;
- turn on a scheduled GitHub Action that posts the same report to one issue in the repository, using only `GITHUB_TOKEN`;
- add the project's own metrics, such as Alarms or deploy rollbacks, through settings or a few lines of Python in `devctl_project`;
- keep a Corrections ledger in the repository, with the rung or rungs that would have prevented each Correction and what was done about it;
- run `rs-garden`, by hand or from the Harness's own scheduler, to add new Corrections to the ledger, find drift, propose rule changes as tasks and fix doc-only drift in one PR per pass.

rapid-ship reports and never acts on a report. A breached Suggested threshold changes nothing: rapid-ship never changes the Mode, opens no PR and stops no agent because of a metric ([ADR 0004](../../adr/0004-team-management-boundary.md)). The owner reads the report when choosing the Mode.

Out of scope here:

- Agent identity, the thin devctl command that runs `gh` and `git push` as an App, and the `rs-setup` steps that record thresholds and offer the metrics Action are in [Spec 1](2026-10-14-kit-and-setup-design.md). So are `rs-health` and the audit it shares with `rs-garden`.
- How the Reviewer posts its findings, the Lead brief's request to add in-session Corrections to the ledger, the escalation list and the shape of a task are in [Spec 2](2026-10-16-delivery-skills-design.md).
- Section 12 lists what this spec needs from both.

## 2. Where the numbers come from

**Deterministic.** Every basic metric comes from GitHub's API and the repository's git history. No model reads anything, no step attributes an event by judgement, and no agent reports on itself: devctl reads no label, commit trailer or PR text that an agent writes to describe its own work. Two runs over the same GitHub state and the same git history give the same numbers.

**Read-only.** devctl reads GitHub through `gh api` with the token `gh` has: the owner's `gh` login on the owner's machine, `GITHUB_TOKEN` in the Action. It reads git from the local `origin/<default branch>` and never fetches. Its only write is the Action's post (section 8), which runs only inside GitHub Actions.

**Agent identity.** Agent identity is on when `[github]` in `project.toml` records both Apps, each with its ID and slug (Spec 1, section 4). An agent PR is then a PR authored by the Worker App, the App that opens and merges PRs; its bot account is `<slug>[bot]`. devctl reads the slug from the settings and never needs an App's key. With Agent identity off, agents open PRs as the owner. GitHub then cannot tell an agent PR from the owner's, and nobody signed in as the owner can request changes on it. A metric that needs that distinction reports `unknown: needs Agent identity`. The others count every PR and say so.

**Population.** Each metric names what it counts:

| Population | Meaning |
| --- | --- |
| `agent PRs` | PRs the Worker App authored. Agent identity is on |
| `all PRs` | Every PR. Agent identity is off |
| `ledger` | Entries in the Corrections ledger |
| `repository` | Events in the repository that belong to no PR. Project-defined metrics use it |

**Window.** The window is the last `window` PRs of the population merged into the default branch; `window` is 30 by default. Counting merged PRs instead of weeks judges a quiet month and a busy one on the same number of PRs.

1. devctl walks the first-parent history of `origin/<default branch>` from its tip.
2. For each commit it asks GitHub which PR merged it (`GET /repos/{owner}/{repo}/commits/{sha}/pulls`) and keeps the PR whose `merge_commit_sha` is that commit. A commit that no PR merged, such as a direct push, is skipped.
3. It keeps PRs of the population until it has `window` of them or the history ends. With fewer, the report says so, for example `12 of 30`.

The window's span runs from the merge time of its oldest PR to the time of the report. A PR that GitHub shows as merged but whose merge commit is not yet in the local `origin/<default branch>` is left out, and the report counts it as not fetched. Run `git fetch` and rerun. The Action's checkout has the whole history, so there that count is normally zero.

## 3. The basic metrics

| ID | Metric | Population | Value |
| --- | --- | --- | --- |
| `revisions` | Revisions per merged PR | `agent PRs` only | Mean Revisions per PR in the window |
| `reverts` | Reverts | `agent PRs`, or `all PRs` without Agent identity | PRs in the window that a later commit reverted |
| `red_merges` | Red merges | `agent PRs`, or `all PRs` without Agent identity | PRs in the window whose merge commit failed `devctl check` |
| `closed_unmerged` | Closed unmerged | `agent PRs`, or `all PRs` without Agent identity | PRs closed without merging during the span |
| `corrections` | Corrections | `ledger` | Entries dated in the span, in total and by rung |

Each count lists the PRs or entries behind it, so the owner can open each one.

### Revisions per merged PR

For each PR in the window, devctl counts the distinct head commits that received a review requesting changes, submitted no later than the merge:

1. Read the PR's reviews (`GET .../pulls/{number}/reviews`) and keep those with state `CHANGES_REQUESTED`.
2. Add each dismissed review that requested changes. A dismissed review has state `DISMISSED`; the PR's `review_dismissed` event records the state it had before.
3. Count the distinct `commit_id` values. Several reviewers requesting changes on one head are one Revision, and a second review of the same head adds none.

Any reviewer counts: the Reviewer App or a person. The value is the window's total divided by the number of PRs in it. The report lists the PRs with the most Revisions. Spec 2's `revision_rounds` escalation kind also counts distinct head commits, but the Lead reads each verdict's first line, `rapid-ship review: changes requested`, and people's reviews that requested changes, so the kind works without Agent identity.

This metric needs Agent identity for two reasons. Without it, devctl cannot select agent PRs. And a Reviewer acting as the owner cannot request changes on a PR the owner's account opened, so it posts its verdict as a comment review (Spec 2), which no Revision counts.

### Reverts

A PR in the window counts as reverted when either of these holds at the time of the report:

1. A commit on `origin/<default branch>` after the PR's merge commit has a message line `This reverts commit <sha>`, where `<sha>` is the PR's merge commit in full, 40 characters. `git revert` writes this line, also when it reverts a merge commit.
2. A PR merged into the default branch after it has the body line `Reverts <owner>/<repo>#<number>`. GitHub's Revert button writes this line.

A PR reverted more than once counts once. A revert made by hand, without either line, is not detected (section 16). The Kit's ruleset allows squash merges only, so each PR is one commit on the default branch. Under other merge methods only reverts of the commit GitHub records as `merge_commit_sha` are detected. Recent PRs have had less time to be reverted; the count shows what happened up to the report.

### Red merges

A PR in the window is a red merge when the CI run that checked its merge commit on the default branch failed:

1. List the runs of `.github/workflows/devctl-check.yml` for the merge commit with event `push` (`GET .../actions/workflows/devctl-check.yml/runs?head_sha=<sha>&event=push`). Take the earliest.
2. Read that run's first attempt. A rerun that passed does not clear a failure, because a flaky check is a problem too.
3. A conclusion of `failure` or `timed_out` is red, and `success` is green. Anything else, or no run at all, is unknown for that PR.

GitHub cancels a pending run when a newer one joins the same concurrency group. Two merges in quick succession can therefore leave the first without a run, and that PR is unknown (section 16). The nightly run is not counted: it belongs to no merge, and a newly published advisory can fail it with no change in the repository. CI push runs cover only `main` and `master` (Spec 1); with another default branch, every PR is unknown here.

### Closed unmerged

PRs of the population that are closed and not merged at the time of the report, and whose `closed_at` falls in the span. A PR closed and later reopened counts only if it is closed again.

With Agent identity, a PR counts only when a person closed it: the actor of its last `closed` event is neither App. A PR the Lead closed itself, for example one it replaced with a new PR, does not count. Without Agent identity, devctl cannot tell who closed a PR, so every PR closed unmerged counts.

### Corrections

The value counts ledger entries (section 9) at the tip of `origin/<default branch>` dated on or after the day the span starts. It also counts entries per rung: an entry that names two rungs counts once in the total and once under each rung. The report also counts repeats: entries whose `category` already had an earlier entry anywhere in the ledger.

The ledger is complete only up to the last gardening pass, which `docs/corrections/last-pass.toml` records. A PR in the window whose merge commit is not an ancestor of that file's `through` commit is not gardened yet, and the count is then a lower bound. Without the file, no PR is gardened yet. An entry the Lead added for an in-session Correction counts as soon as it merges.

## 4. Status of a Suggested threshold

A Suggested threshold is an upper limit: the metric should be at most this value. For each metric that has one, devctl reports one status.

| Status | When |
| --- | --- |
| ok | The value is within the threshold even if every unknown part counts against it |
| breached | The known part alone exceeds the threshold |
| unknown | Neither: the metric is unknown, or its unknown part could decide the result |

For a count with `v` known items, `u` unknown items and threshold `m`: breached when `v > m`, ok when `v + u <= m`, and unknown otherwise. For Corrections, with `v` entries: breached when `v > m`, ok when `v <= m` and every PR in the window is gardened, and unknown otherwise. A window with no PRs makes every metric unknown, never zero. A metric that is unknown only because Agent identity is off shows `needs Agent identity` instead of a status.

## 5. `devctl metrics`

```text
./devctl metrics [--window <n>] [--json] [--post]
```

- `--window <n>` overrides `window` from `metrics.toml` for this run.
- `--json` prints the report as data instead of text.
- `--post` posts the report as the Action does (section 8). It refuses with exit 2 unless `GITHUB_ACTIONS` is `true` and `GH_TOKEN` is set. On the owner's machine, and in an agent's Session, `devctl metrics` writes nothing.

### Steps

1. Read `.rapid-ship/project.toml` and `.rapid-ship/metrics.toml` (section 6). Agent identity is on when `project.toml` records both Apps (section 2).
2. Ask GitHub for the default branch's name. Resolve `origin/<default branch>` locally; if it is missing, stop with exit 2 and say to fetch it.
3. Build the window (section 2).
4. Compute the basic metrics, then the project-defined metrics (section 7).
5. Give each Suggested threshold its status (section 4).
6. Print the report, or post it with `--post`.

If `.rapid-ship/gate.toml` still exists, the report adds one note: devctl no longer reads it, and its values belong in `metrics.toml` (section 6).

The default window takes about 200 GitHub API requests: one per first-parent commit walked and about four per PR in the window. That stays well inside the 1,000 requests per hour that `GITHUB_TOKEN` allows per repository.

### Exit codes

- **0:** the report was built and no Suggested threshold is breached.
- **1:** at least one Suggested threshold is breached.
- **2:** the report could not be built: unreadable settings, `gh` missing or signed out, a GitHub error, or no `origin/<default branch>`. With `--post`, a failed post also exits 2.

An unknown status shows in the report but does not change the exit code (section 16). With `--post`, a breach exits 0 once it has been posted, because posting it is the whole response. A project-defined metric that fails is unknown, not an error (section 7).

### Text output

```text
rapid-ship metrics for owner/name at 2026-10-16 05:41 UTC
Agent identity: on. Window: the last 30 merged agent PRs, #212 to #268, merged since 2026-09-03.

metric           population   value                                suggested  status
revisions        agent PRs    0.7 per PR                           <= 1.0     ok
reverts          agent PRs    1 (#231)                             <= 1       ok
red_merges       agent PRs    0, 2 unknown (#240, #262)            <= 1       unknown
closed_unmerged  agent PRs    4 (#219, #225, #250, #266)           <= 3       breached
corrections      ledger       9 (rung 1: 2, rung 2: 5, rung 3: 3)  -          -
alarms           repository   0                                    <= 0       ok

1 Suggested threshold breached and 1 unknown. rapid-ship takes no action.
```

### JSON output

`--json` prints one object. `version` changes only when a field changes meaning.

```json
{
  "version": 1,
  "repository": "owner/name",
  "generated_at": "2026-10-16T05:41:07Z",
  "default_branch": {"name": "main", "commit": "<40-character SHA>"},
  "agent_identity": true,
  "window": {"size": 30, "prs": 30, "population": "agent", "since": "2026-09-03T11:02:44Z", "not_fetched": 0},
  "metrics": [
    {
      "id": "red_merges",
      "title": "Red merges",
      "population": "agent",
      "value": 0,
      "unknown": 2,
      "reason": null,
      "items": [{"pr": 240, "state": "unknown", "detail": "push run cancelled"}],
      "threshold": 1,
      "status": "unknown"
    }
  ],
  "notes": []
}
```

`value` is `null` when the whole metric is unknown, and `reason` then says why, such as `needs Agent identity`. The Corrections metric adds `by_rung`, `repeats` and `not_gardened`.

## 6. Settings: `.rapid-ship/metrics.toml`

`metrics.toml` replaces `.rapid-ship/gate.toml`. It is a seeded Kit file in the Protected set, like every file in `.rapid-ship/`, so changing a threshold is a PR the owner approves. It holds no secret.

```toml
# Suggested thresholds and project-defined metrics. Changes need the owner (Protected set).
# devctl metrics reports a breach; rapid-ship takes no action.
window = 30   # the last merged PRs: agent PRs with Agent identity, every PR without it

[thresholds]  # at most this value; remove a line to report the metric without a threshold
revisions = 1.0        # Revisions per merged PR; needs Agent identity
reverts = 1
red_merges = 1
closed_unmerged = 3
# corrections = 10
# alarms = 0           # a threshold for the project-defined metric below

# A project-defined metric that counts issues labelled alarm:
# [[metric]]
# id = "alarms"
# title = "Alarms"
# source = "issues"
# label = "alarm"
```

`devctl metrics` exits 2 and lists every problem when:

- `window` is not an integer of at least 1;
- a key in `[thresholds]` names no basic or project-defined metric, or its value is not a number of at least 0;
- a `[[metric]]` lacks `id`, `title` or `source`, or a field its source needs;
- an `id` does not match `[a-z][a-z0-9_]*`, repeats another, or is a basic metric's ID.

### Default thresholds

The seeded `gate.toml` of plans 1 to 3 recorded 1.0 Revisions per PR, 1 Rollback and 0 open Alarms. The earlier design allowed 3 Revisions, 0.1 Rollbacks and 0.2 Alarms per PR. This spec proposes these defaults (section 16):

| Threshold | Default | Why |
| --- | --- | --- |
| `revisions` | 1.0 per PR | A mean of 3 would equal the proposed escalation at 3 Revision rounds (Spec 2), so most PRs would reach the owner before the threshold said anything |
| `reverts` | 1 in the window | One revert in 30 merged PRs. Deploy rollbacks are now project-defined, so they no longer share this count |
| `red_merges` | 1 in the window | A merge that breaks the default branch should be rare |
| `closed_unmerged` | 3 in the window | One closed PR in ten merged ones |
| Alarms | none seeded | Alarms are project-defined. The comment suggests 0 for the metric the owner adds |

`rs-setup` shows these and records the owner's values (Spec 1).

### What happens to `gate.toml`

| `gate.toml` key | Now |
| --- | --- |
| `mode`, `flight_lease_until` and `owner_approves_behavioural_test_removal` | Dropped with the file by Spec 1's plan 4. The escalation list, `[escalation]` in `project.toml`, sets the Mode and names behavioural-test removals; there is no lease |
| `[thresholds.promotion]` and `[thresholds.demotion]` | Replaced by `window` and `[thresholds]` in `metrics.toml` |

Spec 1's plan 4 stops seeding and reading `gate.toml`; this spec seeds `metrics.toml`. `rapid-ship sync` creates a seeded file that a newer Kit adds and never edits or deletes an existing one (Spec 1). An existing project therefore receives `metrics.toml` with the defaults and keeps its old `gate.toml`. `devctl metrics` notes the old file until the owner deletes it.

## 7. Project-defined metrics

A project adds its own metric in one of two ways. A project-defined metric counts events in the window's span, belongs to no PR and is attributed to none. Its population is `repository`, and its threshold goes in `[thresholds]` under its ID.

Setting up Alarms is the owner's job; rapid-ship recommends a route and counts what arrives. Most monitoring tools can open a GitHub issue or record a GitHub deployment, so the two settings sources below need no code.

### From settings

Two sources read GitHub with the same token as the basic metrics:

| `source` | Fields | Counts |
| --- | --- | --- |
| `issues` | `label` | Issues with that label opened during the span. Pull requests are not counted |
| `deployments` | `environment`; `count`, either `rollbacks` (the default) or `failures` | See below |

For `deployments`, devctl reads the deployments to `environment` and their statuses:

- **Rollbacks:** a deployment created during the span that reached `success`, whose commit is an ancestor in git of the commit of the previous deployment to that environment that reached `success`, and not the same commit. Deploying older code is a rollback, whatever tool did it.
- **Failures:** a deployment created during the span whose last status is `failure` or `error`.

A deployment whose commit is not in the local history is unknown. Each `deployments` metric names its environment, so project-defined metrics do not read `[release]` in `project.toml`.

### From code

`devctl_project` defines a metric the way it defines a check step:

```python
def metrics() -> list[Metric]:
    """Return project-defined metrics for ./devctl metrics."""
    return [ProbeFailures()]
```

A `Metric` has an `id`, a `title` and `measure(context) -> MetricResult`. The context gives the span's start and end, the window's PRs, the repository, and a read-only helper for `gh api`. A `MetricResult` holds a number, or `None` with a reason when the metric is unknown, and the items behind it, each a label with a URL or a time.

- An empty source is not zero. A metric returns 0 only after it read its source and found nothing. When it cannot read its source, it returns unknown with the reason.
- A metric that raises an exception or runs longer than 60 seconds is unknown, with the error as its reason. The rest of the report is unaffected.
- A metric must be deterministic and must not run a model. devctl cannot check either, so the seeded `devctl_project` says so.
- A metric that needs a credential other than the GitHub token reads it from the environment. The Kit's Action passes no other secret, so such a metric is unknown there unless the project takes the workflow over (section 8).

The seeded `devctl_project` gains a `metrics()` stub that returns an empty list. A `devctl_project` without `metrics` has no project-defined metrics, so existing projects need no change.

## 8. The scheduled metrics Action

`.github/workflows/rapid-ship-metrics.yml` is an optional managed Kit file. `rs-setup` offers it, the owner opts in, and Spec 1 records the choice under `[kit] optional`. It needs no model and no secret other than `GITHUB_TOKEN`.

- **Triggers:** a daily `schedule` and `workflow_dispatch`. GitHub runs scheduled workflows on the default branch only.
- **Permissions:** `contents: read`, `pull-requests: read`, `actions: read`, `deployments: read` and `issues: write`, and nothing else.
- **Concurrency:** one group, `rapid-ship-metrics`. A run never cancels another.
- **Steps:** checkout pinned by commit SHA, with `persist-credentials: false` and the whole history; `astral-sh/setup-uv` pinned by commit SHA; then `./devctl metrics --post` with `GH_TOKEN: ${{ github.token }}`.
- **Job name:** `rapid-ship metrics`.

### Where it posts

1. **The run's job summary** gets the report in Markdown.
2. **One open issue** titled "rapid-ship metrics" holds the latest report. devctl finds it as the open issue opened by `github-actions[bot]` whose body starts with `<!-- rapid-ship-metrics -->`, and opens one when none exists. Each run replaces the body with that marker, the Markdown report, and the report's JSON inside an HTML comment.
3. **A comment on that issue** appears only when a threshold's status differs from the status in the previous body, and lists each change, such as `closed_unmerged: ok -> breached (4, at most 3)`. When devctl has just opened the issue, it comments only if a threshold is breached or unknown. An edited body sends no notification and a comment does, so the owner hears about changes, not about every run.

The issue is a report, not a task. Closing it stops nothing; the next run opens a new one. To stop the reports, the owner disables the workflow in GitHub or removes it from `[kit] optional`. GitHub disables scheduled workflows in a public repository after 60 days without activity. The report shows when it was generated, so a stale report is visible.

A project whose own metrics need other secrets lists the workflow under `[kit] exclude` and adds them to its own copy (Spec 1). The Kit's copy reads no secret beyond `GITHUB_TOKEN`.

## 9. The Corrections ledger

The ledger is the directory `docs/corrections/`: one Markdown file per Correction, a seeded `README.md` that states the format, and `last-pass.toml`, which `rs-garden` writes. One file per entry keeps parallel PRs from conflicting, as appends to one shared file would. This spec proposes keeping the directory outside the Protected set, so that an agent's PR can add an entry without the owner (section 16). Removing or rewriting an entry shows in the PR's diff.

### What counts

A Correction is a change that a human or the Reviewer required of an agent's work: a blocking finding the agent fixed, or a person's request for a change that the agent made. A nit is not a Correction. Neither is a question, or a suggestion that was discussed and not taken.

### An entry

File name: `<date>-<category>-<n>.md`, with the lowest `n` from 1 that is free on the writer's branch. Two PRs that pick the same name conflict at merge, and the second renames its file.

```markdown
---
date: 2026-10-16
by: reviewer
source: https://github.com/owner/name/pull/42#discussion_r1234567890
pr: 42
path: src/app/links.py
category: env-read-outside-settings
rungs: [1, 2]
prevention: Read configuration only through settings, and ban os.environ elsewhere.
status: open
---

The Worker read `LINKS_URL` with `os.environ` inside `links.py`. The Reviewer required it to come from `settings`.
```

| Field | Required | Meaning |
| --- | --- | --- |
| `date` | yes | The day the Correction was made, UTC |
| `by` | yes | `reviewer` or `human` |
| `source` | yes | The URL of the review, thread or comment on GitHub, or `session` for a Correction the owner gave in a Session |
| `pr` | no | The PR whose work was corrected |
| `path` | no | The file the Correction is about |
| `category` | yes | A short kebab-case name shared by repeats of the same mistake |
| `rungs` | yes | One or more distinct rungs from 1 to 4 that would have prevented it. A Correction that needs a safe interface and a check names both |
| `prevention` | yes | One sentence naming the mechanism that would prevent a repeat |
| `status` | yes | `open`, `proposed`, `prevented` or `declined` |
| `task` | when `proposed` | The proposed task in the tracker |
| `prevented_by` | when `prevented` | References that resolve, or repository paths that exist, for the mechanism that now prevents it |
| `reason` | when `declined` | Why the owner chose no fix |

The rungs are the four in the [design](2026-10-14-rapid-ship-design.md): safe interfaces, automated checks, judgement, and the owner.

### Who writes entries

| Writer | When | `source` |
| --- | --- | --- |
| `rs-garden` | On each pass, from the reviews, review threads and comments on PRs in its range | The URL on GitHub |
| The Lead | When the owner corrects it in the Session. The Lead brief asks for this (Spec 2); whether the Lead does it is up to its Harness | `session` |
| The PR that lands a fix | Sets `status: prevented` and `prevented_by` on the entries it prevents | Unchanged |
| The owner | At any time, for example to decline a fix | Unchanged |

The Lead adds a `session` entry to the open PR the Correction concerns, or to its next PR when none is open. `rs-garden` skips any thread, review or comment whose URL is already a `source`.

### `last-pass.toml`

```toml
# Written by rs-garden: the default-branch commit that the last gardening pass covered.
through = "<40-character SHA>"
date = 2026-10-16
```

### The check

`devctl check` gains map rule 9, in the fast tier, after Spec 1's map rules 1 to 8:

1. Every `.md` file in `docs/corrections/` other than `README.md` has front matter with the required fields above.
2. `date` is a date; `by`, `status` and `category` take the forms above; `rungs` is a non-empty list of distinct integers from 1 to 4; `prevention` is not empty; `source` is `session` or an `https` URL.
3. A `proposed` entry has a `task`, a `declined` entry has a `reason`, and a `prevented` entry has a non-empty `prevented_by` list. Each item resolves as a reference from Spec 1's reference kinds (`check:`, `test:`, `ruff:`, `banned:`, `contract:`, `type:`), or is a repository path that exists, such as a skill file or CODEOWNERS.
4. If `last-pass.toml` exists, `through` is a full SHA of a commit in the repository.

## 10. `rs-garden`

`rs-garden` is a user-invoked Kit skill. The owner runs it, or has the Harness's scheduler run it (below). Each pass has three outputs:

1. New entries in the Corrections ledger.
2. One PR with those entries, the doc-only drift fixes and an updated `last-pass.toml`.
3. Proposed tasks for rule changes, created in the backlog of the owner's tracker through the Harness's connection to it. devctl never talks to the tracker.

### What it never does

- It never merges, and never pushes to the default branch.
- It never changes a Protected path except a doc-only fix inside its own PR. The Protected set is always on the escalation list, and CODEOWNERS requires the owner's approval, so such a fix never lands without the owner.
- It never changes CI, guardrail settings, devctl, a skill, an existing Pattern file, `exceptions.toml` or any other Protected setting. It proposes a task instead.
- It never starts, schedules or stops an agent, and never puts a task in a started state.

A **doc-only fix** changes prose in `README.md`, `ARCHITECTURE.md`, an AGENTS.md file or `docs/features/` to match what the repository already does. It adds, removes or changes no Rule, Pattern, check, setting, skill or code. Anything else is a rule change and becomes a proposed task.

### Steps

1. **Preconditions.** The work tree is clean. Fetch `origin/<default branch>`. If an open PR already changes `docs/corrections/last-pass.toml`, the previous pass is still waiting: stop and point to it.
2. **Range.** The range starts at `through` from `last-pass.toml` and ends at the tip of `origin/<default branch>`. On the first pass it starts just before the oldest PR in the window that `./devctl metrics --json` reports. When the default branch has not moved since `through`, report that there is nothing to garden and stop.
3. **Corrections.** Read the reviews, review threads and comments of every PR merged in the range, and of every PR closed unmerged since the `date` in `last-pass.toml`. With Agent identity, read agent PRs only. Without it, read every PR, because agent PRs cannot be told apart; the ledger then includes Corrections of people's work too. Write one entry per Correction (section 9). When the Correction is a blocking finding in a Reviewer's verdict (Spec 2, section 3.6), copy its rungs and prevention. Otherwise assign them by the ladder.
4. **Repeats.** Group the whole ledger by `category`. Two or more entries in one category, at least one of them `open`, are a repeat. A new entry in a category whose earlier entries are `prevented` means the prevention did not hold. Say so in the PR body.
5. **Proposals.** For each repeat, propose one task on the rung that fits: a safe interface for structural misuse, a check for local or stylistic problems, or both; a skill or advisory Rule only when neither can carry the fix. For a prevention that did not hold, propose a task that moves the fix to a rung that can hold it. Before creating a task, search the tracker for an open task for the same category, and reuse it if one exists. A task follows Spec 2's task shape and links the entries it would prevent. Its acceptance criteria include setting those entries to `prevented`. Set each entry it covers to `proposed`, with `task`. Without a tracker connection, leave the entries `open` and put each task draft in the PR body.
6. **Drift.** Run the shared audit over the files changed in the range (below). Fix doc-only drift in the pass's branch; propose a task for everything else.
7. **The pass PR.** Write `last-pass.toml` with the range's end. Run `./devctl check --tier fast`. Open one PR from a new branch based on `origin/<default branch>`: with Agent identity through `devctl as worker push` and `devctl as worker gh pr create` (Spec 1), without it with `git push` and `gh pr create`. The body states the range, the new entries, the repeats with their proposals, the drift with where each item went, any prevention that did not hold, and the Evidence section that `devctl check` requires. If the doc-only fixes would take the PR past a task's 500-line diff cap, keep the ledger changes and the first fixes, and propose a task for the rest.
8. **Report** to whoever ran the pass: the PR, the tasks proposed and anything skipped.

### The shared audit

`rs-health` and `rs-garden` run one audit, kept once in `.agents/skills/rs-health/references/audit.md` (Spec 1). `rs-health` runs it over the whole repository at adoption and returns a standards milestone. `rs-garden` reads the same file and runs each item over the files changed in its range. The audit must cover at least the drift that gardening finds:

| Drift | Output in `rs-garden` |
| --- | --- |
| A statement, command, path or link in `README.md`, `ARCHITECTURE.md` or an AGENTS.md file that no longer matches the repository | Doc-only fix |
| A feature file in `docs/features/` that no longer describes its feature | Doc-only fix |
| Code changed in the range that departs from its Pattern | Proposed task |
| A recurring task done more than one way, with no Pattern | Proposed task for a Pattern |
| An exception whose removal condition now holds | Proposed task |
| A settings entry that matches nothing, such as a `[map] unguided` directory, a `[kit] exclude` path or a CODEOWNERS path | Proposed task |
| Dead code: a module, function or check step that nothing reaches | Proposed task |

`devctl check` already fails on broken AGENTS.md links, exception entries that match no suppression, and Pattern references that do not resolve. CI keeps those at zero on the default branch, so the audit does not repeat them.

### Scheduling

Scheduling an agent is the Harness's job. The skill's `references/scheduling.md` shows the options below, each with a link to the vendor's documentation and the date it was checked. A scheduled pass runs without anyone to answer a prompt, so the Harness must allow, in advance, what the pass needs: git commits and pushes, `gh` reads, opening the PR, and writing to the tracker.

| Harness | Scheduler, as checked on 2026-10-16 |
| --- | --- |
| Claude Code | Routines, which run in Anthropic's cloud on a schedule no more often than hourly and push `claude/`-prefixed branches by default (research preview). Desktop scheduled tasks, which run locally while the machine is on. `/loop`, which lasts only as long as its Session and expires after 7 days |
| Codex | Automations in the Codex app; a local one needs the app running. The CLI has no scheduler: use cron or launchd with `codex exec --sandbox workspace-write` |
| Antigravity CLI | `/schedule` inside a conversation. For unattended runs, cron or launchd with `agy -p`; headless runs deny any tool that needs approval unless it is allowed in advance |
| Any Harness | The operating system's cron or launchd running the Harness's headless mode, while the machine is on |
| GitHub Actions | A Harness's own Action on a `schedule`, with a model credential as a repository secret. A PR opened with `GITHUB_TOKEN` starts no workflow, so `devctl check` would not run on the pass PR. Under Agent identity, the App keys live in the owner's Keychain (Spec 1) and are not available there |

## 11. Kit changes

| Path | Kind | Change |
| --- | --- | --- |
| `.rapid-ship/metrics.toml` | seeded | New: window, Suggested thresholds and settings-sourced metrics |
| `docs/corrections/README.md` | seeded | New: the ledger format |
| `.github/workflows/rapid-ship-metrics.yml` | managed, optional | New: the scheduled Action |
| `.agents/skills/rs-garden/` and its `.claude/skills/rs-garden` link | managed | New skill, with `references/scheduling.md` |
| `tools/devctl/devctl/` | managed | New `metrics` command; map rule 9 |
| `tools/devctl/devctl_project/__init__.py` | seeded | New projects get a `metrics()` stub |
| `docs/AGENTS.md` | seeded | Points to `docs/corrections/` |

Every path above except `docs/corrections/README.md` is in the Protected set already, through `.github/`, `.agents/skills/`, `.claude/`, `tools/devctl/`, `.rapid-ship/` and every AGENTS.md. `docs/corrections/` is not (a proposal, section 16). Spec 1's plan 4 already stopped seeding and reading `.rapid-ship/gate.toml`.

A plan for this spec can build it in five independent slices: `metrics.toml` with the basic metrics; project-defined metrics; the Action; the ledger with map rule 9; `rs-garden`.

## 12. What this spec needs from Specs 1 and 2

From Spec 1:

- The Agent identity settings in `project.toml` record each App's slug as well as its ID, so metrics can match bot authors without an App's key.
- `[kit] optional` can name a Kit file, here the metrics Action, not only a skill.
- `rs-setup` shows the default Suggested thresholds and records the owner's values in `metrics.toml`, and offers the metrics Action. When Agent identity is off, it tells the owner that Revisions will be unknown.
- The audit in `rs-health`'s `references/audit.md` covers the drift in section 10, including settings entries that match nothing.
- Spec 3 does not need `[release]` in `project.toml`; Spec 1's plan 4 removes it.

From Spec 2:

- `rs-review` posts each verdict on the PR in the format of Spec 2's section 3.6, with each blocking finding's rungs and prevention, so `rs-garden` can read them from GitHub.
- The Lead brief asks the Lead to add Corrections the owner gives in the Session to the ledger, in the format of section 9. The entry goes in an agent PR. With the ledger outside the Protected set (a proposal, section 16), no entry needs a Protected PR of its own.
- A task that fixes a repeated Correction sets its ledger entries to `prevented`.
- The `revision_rounds` escalation kind counts rounds by distinct head commit, as section 3 counts Revisions, but reads each verdict's first line, so that it works without Agent identity.

## 13. Dog-fooding

*This section describes this repository's own configuration, not product behaviour.* This repository validates the spec on itself and on hello-rapid-ship. Its `rs-garden` proposals go to Linear, its tracker. Its agents sign in with vendor subscriptions only ([ADR 0001](../../adr/0001-subscription-logins-only.md)), so it schedules `rs-garden` through a Harness scheduler or cron on the owner's subscription, not through a GitHub Action with a model credential.

## 14. What changed on 2026-10-16

This spec replaces the earlier plan for a third spec, "Metrics and the gate". There is no `devctl gate`, no Mode file, no Flight lease, no Pre-flight, no attack-PR set and no Investigator, and no promotion or demotion window. Rollbacks split into Reverts, a basic metric, and deploy rollbacks, which a project defines. `gate.toml` gives way to `metrics.toml`. The Corrections ledger and `rs-garden`, which the withdrawn Walk-flow draft listed as not yet designed, are designed here.

Two earlier designs are reused. The rule that missing data is unknown, and counting Revisions by reviewed head commit, come from the historical metrics guide, `docs/metrics.md`. A ledger entry's `rungs` and `prevention` mean what they meant in the verdict of plan 4's `devctl review`, which was never merged, and what they mean in Spec 2's verdict.

## 15. Testing

**Unit tests**, offline. devctl reads GitHub only through `gh`, so these tests put a fake `gh` on `PATH` that serves recorded responses; the tests that use it are labelled simulated.

- `metrics.toml` validation, each problem listed; the note for a leftover `gate.toml`.
- The window over a local git fixture: the first-parent walk, a skipped direct push, selection by author with and without Agent identity, a window that is not full, and a merged PR that is not fetched.
- Revisions: distinct heads, two reviewers on one head, a dismissed review that requested changes, a review after the merge ignored, approvals ignored.
- Reverts: a `git revert` line, a reverted merge commit, the Revert button's body line, both signals counting once, and an abbreviated SHA not counted.
- Red merges: `failure`, `timed_out` and `success`; a cancelled run and a missing run as unknown; a passing rerun that does not clear a failed first attempt.
- Closed unmerged: a PR closed by an App not counted with Agent identity; a PR closed, reopened and merged not counted.
- Corrections: totals, an entry with two rungs, repeats, and PRs not gardened after `through`.
- The status rule, table-driven over `v`, `u` and `m`; a window with no PRs; `needs Agent identity`.
- Exit codes, and `--post` refusing outside GitHub Actions.
- `--post` with the fake `gh`: opening the issue, replacing its body, commenting only on a status change, and the first-run comment.
- Project-defined metrics: the `issues` source, `deployments` rollbacks by ancestry and failures, a code metric returning a value, returning unknown, raising, and timing out.
- Map rule 9: each required field, each status's extra field, references in `prevented_by`, and `last-pass.toml`.
- The JSON output against a recorded report.

**Integration tests**, offline and labelled as such:

- `init` on scratch repositories for both stacks seeds `metrics.toml` and `docs/corrections/README.md`, and `./devctl check` passes.
- `sync` on a project that has `gate.toml` adds `metrics.toml` and leaves `gate.toml` in place.

**Live trials**, recorded under `docs/trials/`:

- `devctl metrics` against a scratch repository on GitHub that has: a PR reverted with the Revert button and one with `git revert`, a red merge, two quick merges that cancel a pending run, a PR closed unmerged, and a dismissed review that requested changes. The trial confirms the GitHub behaviour this spec relies on, including what the `review_dismissed` event records and the Revert button's body line. It runs with and without Agent identity.
- The Action on the same repository: its permissions suffice, it opens the issue, replaces the body and comments only on a change.
- `rs-garden` on a scratch repository with prepared PRs: a blocking finding that was fixed, a nit that was skipped, a request from the owner, two Corrections in one category, a stale README command, a departure from a Pattern, and an exception whose removal condition holds. The trial records the entries, proposals and doc-only fixes it produced against the expected list, in Claude Code and in Codex. The output comes from a model, so the trial records a result; it is not a pass or fail test.
- One scheduled `rs-garden` pass through a Harness scheduler, and one through cron with a headless Harness.

**Dog-food:** this repository runs `devctl metrics` and `rs-garden` on itself and on hello-rapid-ship.

## 16. Open items

These are the drafter's proposals or questions that the owner has not settled.

- **Default thresholds (proposal).** `window` 30, `revisions` 1.0, `reverts` 1, `red_merges` 1, `closed_unmerged` 3, and no threshold on Corrections (section 6).
- **`metrics.toml` replacing `gate.toml` (proposal).** The alternative is a `[metrics]` table in `project.toml`.
- **Unknown and the exit code.** An unknown status never exits 1 today. A `--strict` option that also exits 1 on an unknown status, like `rapid-ship status --strict`, is one choice.
- **Cancelled push runs.** GitHub cancels a pending run when a newer one queues in the same group, so quick merges leave some PRs unknown under Red merges. Spec 1's CI template could give each push run its own concurrency group.
- **Reverts outside `rs-work`.** `rs-work` requires `git revert` (Spec 2), but a revert that a person makes by hand, without `git revert`'s line or the Revert button's body line, is not counted.
- **The ledger outside the Protected set (proposal).** An agent's PR can add an entry without the owner. Whether removing an entry should need the owner, for example by the diff step listing removed entries as it lists Protected paths.
- **Proposals for a single Correction.** Today only a repeat gets a proposed task. Whether a severe first Correction, such as a security finding, should get one too.
- **Where the report posts (proposal).** One issue, updated in place, with a comment on each status change. The alternatives are a Discussion or the job summary alone.
- **The first gardening pass's range (proposal).** The metrics window. The alternative is the whole history since adoption.
- **Lower limits.** Every Suggested threshold is an upper limit. A project-defined metric where more is better, such as deploys per week, has no lower limit yet.
