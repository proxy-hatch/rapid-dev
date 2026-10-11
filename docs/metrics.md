# Quality metrics

Every devctl installation includes the same metrics commands, whatever language the project uses:

```sh
devctl metrics                         # Last 28 days
devctl metrics --days 56
devctl metrics --days 7 --until 2026-10-10T00:00:00Z
devctl metrics sync-github              # Read the configured GitHub repository
devctl metrics import observations.json
devctl metrics --include-simulated      # Inspect fixtures separately
```

Reports show samples, sources and the latest observation. Missing or stale data is marked; a rate with no denominator is `null`. Simulations are excluded by default. Imported observations are reported measurements, not verified approval.

## What is collected

| Measure | Default collection | External input |
| --- | --- | --- |
| PR revisions, review rounds, size and elapsed review/merge time | Built-in GitHub sync | — |
| Agent review minutes | Timed reviewer calls, grouped by task; linked to PRs created through the broker | PR links for PRs created elsewhere |
| Human review minutes per PR | — | Active review sessions from the reviewer/tool; PR elapsed time is not a substitute |
| Repeated corrections | Reviewer findings with stable categories; uncategorized findings are reported | Human corrections and category corrections |
| Corrections prevented by checks | — | Category, enforcement rung 1 or 2, check name/path and supporting change/reference |
| Local check duration | Each check's duration, outcome, commit and environment | — |
| CI duration | GitHub Actions run attempts | Other CI providers |
| Flaky-test rate | — | Repeated individual test results for the same code and settings |
| Weekly mutation score | — | Mutation-tool counts; choose the tool in the project profile |
| Change-failure rate; rollbacks per 100 deploys | — | Completed production deployments, failures and rollbacks |
| Escaped defects; time to restore | — | Incidents linked to PRs/deployments, plus confirmed restoration times |

A normal check failure is not automatically a flaky test. A release is not a deployment. Missing human review logs are not zero human effort.

## GitHub collection

Projects use GitHub. With `gh` authenticated on the host, run `devctl metrics sync-github`, then `devctl metrics`. Use `--repository owner/repo` without project settings, or `--days 56` for a longer collection window. Sync reads GitHub and saves measurements locally; it never runs project code or changes GitHub. Reporting alone uses saved data and makes no network calls.

Sync collects open and recently updated PRs, submitted reviews, and completed GitHub Actions attempts. **PR revisions** count distinct code versions seen in reviews or syncs after the first observed version. Repeated reviews of the same commit do not inflate it. This is a lower bound: polling cannot reconstruct every intermediate push. **Review rounds** count distinct reviewed commits; total commits and submitted review counts are separate. Change requests count reviews still in that state; dismissed reviews remain part of review rounds.

Time to first review and merge are elapsed times, never human effort estimates. Actions duration spans the first job start to the last job completion in an attempt, including gaps between jobs. Retries are separate attempts. Unsupported or incomplete runs are reported rather than assigned a fabricated duration. Sync fails without importing a partial batch if GitHub returns an error or the collection limit is reached.

Actions discovery uses the run's creation date. A recent retry of a run created before the collection window may be absent; use a longer `--days` window to include it. The sync result states this limit. A failed matrix run still counts when sibling jobs were cancelled and all relevant timestamps are available.

## Import format

An adapter translates its tool's output into a JSON array. This can be a script in any language; no devctl plugin or Python dependency is required. For example:

```json
[
  {
    "source": "ci-adapter",
    "id": "run-123-attempt-1",
    "at": "2026-10-10T10:00:00Z",
    "kind": "ci",
    "simulated": true,
    "data": {
      "change_id": "task-17",
      "pr": "owner/repo#42",
      "seconds": 93.0,
      "outcome": "pass"
    }
  }
]
```

The example is deliberately simulated. Real observations use `simulated: false`. `source` plus `id` identifies one immutable event: reimporting it is safe; changing it under the same ID rejects the whole batch. Times need a timezone. Use namespaced incident and deployment IDs across systems, and stable correction categories instead of matching comment wording.

`data` depends on `kind`:

| Kind | Required data |
| --- | --- |
| `review` | `change_id`, `reviewer` (`human`/`agent`), `seconds`; optional `pr`, `uncategorized_corrections` |
| `correction` | `change_id`, `category`; optional `pr` |
| `enforcement` | `category`, `rung` (1/2), `check`, `reference` |
| `test` | `test_id`, `commit`, `recipe`, `environment`, `outcome` (`pass`/`fail`) |
| `check` | `change_id`, `check_id`, `commit`, `recipe`, `environment`, `seconds`, `outcome`; optional `pr` |
| `ci` | `change_id`, `seconds`, `outcome`; optional `pr` |
| `mutation` | `killed`, `eligible`, `excluded`; optional `invalid`, `timed_out` (default 0) |
| `deploy` | `deployment_id`, `production`, `failed`; optional `pr` |
| `rollback` | `deployment_id` |
| `incident` | `incident_id` and a `pr` or `deployment_id` |
| `restoration` | `incident_id` |
| `pr` | `change_id`, `pr` |
| `coverage` | `metric` (`rollback`/`enforcement`), `start`, `end` as timestamps |
| `github_pr` | Built-in PR snapshot: identity, dates, current head, size, review counts and reviewed heads |

Review/correction records may also include `commit`, `recipe`, `environment` and `attempt_id`. Recipe and environment IDs must change when checks or their settings change. Emit test reruns as separate event IDs. One deployment record means one completed deployment; omit pending or cancelled runs. A later failure can be linked through an incident or rollback record.

An empty feed needs an explicit observation to mean zero. `coverage` records confirm an interval was checked, even if it contained no events; `start < end <= at`. Daily intervals may join, but gaps leave zero unknown. Use `--until` to report through the adapter’s last complete interval; confirmation may arrive later. Positive observations can still produce a reported rate with incomplete coverage.

## Calculations

- **Review:** sum active seconds, convert to minutes, then average per distinct task or linked PR. Agent and human totals stay separate. Missing or conflicting PR links are counted as unmapped.
- **Repeated corrections:** later changes with the same category / distinct category–change pairs. Repeating a finding within one task does not inflate this rate. Categories seen before the window still establish a repeat.
- **Enforced share:** correction categories linked to a reported rung 1/2 change / categories observed. A prose rule does not qualify. The import records the supporting check; it does not prove that check works.
- **Flakiness:** repeated test/code/recipe/environment groups containing both pass and fail / all repeated groups. A result after a code change belongs to a different group.
- **Mutation:** killed / eligible, grouped by UTC week. Eligible means killed plus survived; excluded, invalid and timed-out mutants are shown separately.
- **Change failures:** distinct failed production deployments / completed production deployments in the window. Linked incidents or rollbacks also mark a deployment failed, once.
- **Rollbacks:** production rollback events in the window / production deployments in the window × 100. Multiple rollbacks remain multiple events.
- **Escaped defects:** new incidents traced directly to a PR or through a deployment. Deployment-only incidents are shown separately when no PR is known.
- **Restore time:** incident start to first confirmed restoration. Unresolved and unlinked incidents remain visible.

## Before adding agents

The playbook calls for numeric project thresholds, at least four baseline weeks, and four consecutive passing weeks before increasing concurrency. Pick sample minimums and acceptable regression limits before the experiment; an empty or stale report is not a pass.

New projects start with one task at a time. Existing settings are preserved. This version collects and reports metrics; threshold evaluation and concurrency changes remain explicit operator decisions. Metrics do not grant merge/release permission. Deployment and incident importers, active human-review timers and mutation runners remain project integrations.
