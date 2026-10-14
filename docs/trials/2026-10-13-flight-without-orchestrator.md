# Can Flight run without an orchestrator?

On 2026-10-13, four desk-research reads examined whether Flight can run with no custom orchestrator process. The answer is yes, with conditions. Flight driven by a prompt alone is unsound. It becomes sound with eight small deterministic pieces: GitHub settings, GitHub Actions workflows and stateless devctl commands. None is a daemon, a workflow engine or a local state store.

Nothing was executed. Every design here needs a supervised trial. Failure rates for a prompt-driven lead are not published anywhere the readers found.

## What each route offers today

| Route | Offers | Missing |
| --- | --- | --- |
| Claude cloud sessions, Routines and Projects (included on Pro) | Unattended implementation in Anthropic's sandbox; opens the pull request; repairs failing CI and review comments; schedule, HTTP and pull-request triggers | Acts as the owner's GitHub user, so a Worker would hold the owner's merge authority and the owner could not approve its pull requests; no Linear trigger; Routines are a research preview |
| Codex cloud (ChatGPT plan) | Native Linear delegation; automatic GitHub review under a bot identity | The Linear flow ends before the pull request is opened and needs a click; no documented approval or check that a ruleset can require; limits unpublished |
| Jules (Google AI Pro) | Its own bot identity; 15 concurrent tasks and 100 a day; an issue-label trigger; CI repair | No Linear trigger; no merge step; no model pin; open network in its sandbox; changelog silent since March 2026 |
| `anthropics/claude-code-action` on GitHub-hosted runners | Accepts a Claude subscription token; ephemeral runners; caps through `max-parallel` and concurrency groups | Claude only; the Codex and Gemini actions accept API keys only |
| Local, with harness features | Claude Code ships a headless supervisor (`claude --bg`, `claude agents --json`) and schedulers | Needs the Mac awake; Codex and Antigravity scheduling exist only in their desktop apps; a review posted from the Worker's own environment is forgeable |

No vendor's hosted agent takes a Linear issue to a merged pull request on subscription plans alone.

## What GitHub can enforce on a personal account

- A branch ruleset with an empty bypass list.
- Required status checks pinned to a named GitHub App as their source.
- Code-owner review on listed paths, which serves as the Protected set.
- A Worker token without the Workflows permission, so a push that touches a workflow file is rejected.
- Auto-merge, scheduled workflows, and concurrency groups as a cap.

Merge queue is not available to a personal account; a free organization adds it. GitHub cannot require an approval from one specific app, so the Reviewer's verdict must be a required check, not an approval.

## Why a prompt alone is not enough

- **Identity.** A hosted Claude Worker acts as the owner. A gate that relies on the owner's review is then usable by the Worker.
- **Editable CI.** A pull request runs its own version of a workflow, so a Worker that edits CI or tests can pass itself.
- **Merge during an Alarm.** Auto-merge has no notion of an Alarm, and a check that passed stays passed.
- **Missed demotion.** Every scheduler in reach can skip silently, so demotion by revocation fails open.
- **Limits stated as preferences.** Anthropic's Projects documentation describes a requested thread limit as a preference, not a cap.

Published accounts agree on the split. OpenAI's Symphony keeps polling, claims, concurrency, stall detection, retries and reconciliation in code. Reports from Cursor and Anthropic describe agent-held locks failing and CI being added after agents broke working features.

## The eight deterministic pieces

| Piece | Where it lives |
| --- | --- |
| 1. No Session holds the owner's GitHub credential; Workers push as a GitHub App with no Workflows or administration permission | GitHub and vendor settings |
| 2. The Reviewer's verdict becomes a check run from a gate App, posted by default-branch code after it verifies the head commit | One App, one ruleset entry, one workflow |
| 3. The Protected set covers workflows, CODEOWNERS, CI scripts, test configuration, AGENTS.md, skills and gate code | CODEOWNERS and the ruleset |
| 4. A diff policy fails a change that deletes tests, adds skip markers or lowers a threshold | A devctl command run by the gate workflow |
| 5. A merge-time gate that fails closed: all checks green, branch current, no open Alarm, lease unexpired | A merge queue, or one stateless merger workflow |
| 6. Flight is a lease that the metrics job renews; no renewal means Walk | The scheduled metrics workflow |
| 7. Admission in one command: verify the ready label, claim the issue by creating its branch, enforce caps and an attempt limit | A devctl command |
| 8. A reaper and a watchdog that notify the owner when a claim or a heartbeat goes stale | A devctl command and a scheduled workflow |

The readers also proposed that the gate require a Reviewer from a different Provider than the Worker. The owner decided that this is advised and never required.

What stays model-driven: choosing among eligible issues, writing and repairing briefs, answering review findings, resolving conflicts, and deciding to escalate. A wrong choice there costs delay, not safety.

## What Walk should observe before Flight

1. **Shadow tick.** Run the lead's tick procedure in propose-only mode for at least 100 ticks or four weeks. Compare each proposal with what the admission command and the merge gate would allow. Any unsafe proposal confirms that step stays in code.
2. **Gate red-team.** Seed one pull request per attack and require a deterministic block: an edited workflow, a deleted test, instructions planted for the Reviewer, a merge attempt from each agent identity, two changes that conflict only in behaviour, an open Alarm with green pull requests waiting, and a disabled metrics job.
3. **Plan capacity.** On a Claude Pro plan the limit on Flight is probably the allowance, not orchestration. Record how many Sessions complete per usage window.

## Limits

- Vendor features in this area change monthly. Three changes would alter the verdict: Codex opening pull requests without a click, any Reviewer emitting a requirable check on a consumer plan, and Linear delegation for Claude.
- Whether a ruleset stops a Claude cloud session from pushing or merging as the owner was not tested.
- Whether a Codex GitHub review can satisfy a required check is unknown.
