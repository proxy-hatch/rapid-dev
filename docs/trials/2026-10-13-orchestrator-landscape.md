# Orchestrator landscape survey

On 2026-10-13, a survey of more than forty projects found none that could serve as rapid-orchestrator, either as a dependency or as a fork. Fourteen were read at source level. Several contain pieces worth copying.

This was desk research. Nothing was installed or run. Stars, licences and push dates came from the GitHub API that day. Effort figures are the readers' estimates, not measurements.

## What a candidate had to do

- Run the vendors' own unmodified CLIs: Claude Code, Codex CLI and Antigravity CLI.
- Use subscription sign-ins only, with no API key and no gateway between a CLI and its Provider.
- Run each Session in a Linux container on a Mac, with the sign-in copied in.
- Start a Session, report its result and the Harness's session ID, send a follow-up, and cancel the whole process tree.
- Queue callers under caps per project, per Provider and per machine.
- Commit and push from outside the Session.
- Offer a headless interface under a permissive licence, with active maintenance.

## Projects read at source level

| Project | Commit or release | Licence | Verdict | Main reason |
| --- | --- | --- | --- | --- |
| [OrchestratorInc/agent-orchestrator](https://github.com/OrchestratorInc/agent-orchestrator) | `4a499e8d` | Apache-2.0 | Copy parts | Host terminals only; no caps; the agent pushes; its daemon reads the Claude subscription token and calls Anthropic's API itself |
| [GoogleCloudPlatform/scion](https://github.com/GoogleCloudPlatform/scion) | `06aa4b40` | Apache-2.0 | Copy parts | Interactive terminals in tmux by design, with no result or session ID returned; the agent commits with the host `.git` writable; caps reject |
| [jayminwest/warren](https://github.com/jayminwest/warren) | `9595340` | MIT | Copy parts | Claude Code and Pi only; no model flag, no resume, no caps |
| [sortie-ai/sortie](https://github.com/sortie-ai/sortie) | main after v1.27.0 | Apache-2.0 | Learn from | A tracker-driven daemon with no session interface; no Reviewer; no Antigravity |
| [Enderfga/claw-orchestrator](https://github.com/Enderfga/claw-orchestrator) | `5221a89` | MIT | Learn from | Host only; a retry can run beside a timed-out attempt |
| [no-human-ai/no_human](https://github.com/no-human-ai/no_human) | `cdcbd0af` | MIT | Copy parts | Host sessions through the Agent SDK; no Antigravity; the agent pushes |
| [harbor-framework/harbor](https://github.com/harbor-framework/harbor) | `4778ceba` | Apache-2.0 | Copy parts | Adapters are tied to its own framework; Antigravity accepts API keys only |
| [mattpocock/sandcastle](https://github.com/mattpocock/sandcastle) | main after v0.12.0 | MIT | Copy parts | A single-run library; mounts the host `.git` read-write; no Antigravity |
| [dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py) | `4fcf7f0` | MIT | Learn from | Re-runs a step interrupted mid-flight without checking what happened |
| [awslabs/cli-agent-orchestrator](https://github.com/awslabs/cli-agent-orchestrator) | main after v2.5.3 | Apache-2.0 | Copy the design | Host terminals in tmux; step timeouts too short for long Sessions |
| [openai/symphony](https://github.com/openai/symphony) | `be10a1b7` | Apache-2.0 | Implement part of the spec | Codex only; scheduler state in memory; pull requests and review are non-goals |
| [cskwork/oh-my-symphony](https://github.com/cskwork/oh-my-symphony) | `50ef9855` | Apache-2.0 | Learn from | A small port; useful as a test oracle |
| [openai/codex](https://github.com/openai/codex) | main after 0.162.1 | Apache-2.0 | Use as the Codex Harness | It is one Harness, not an orchestrator |
| Claude Code headless mode | documentation, 2026-10-13 | Proprietary | Use as the Claude Harness | It is one Harness, not an orchestrator |

## Pieces worth taking

- **Antigravity in a container:** Scion's bundle pre-stages the files that skip agy's first-run prompts and validates the token file.
- **Launch and stream handling for Claude Code and Codex:** Sandcastle, Warren and Harbor. Harbor also classifies failures: rate limit, subscription usage limit, sign-in, overload.
- **Review posting and the feedback loop:** agent-orchestrator posts reviews through `gh api` and deduplicates feedback per pull request.
- **Admission and reconciliation for an unattended scheduler:** the Symphony specification, with claims stored durably.
- **Journal resume rules:** the CLI Agent Orchestrator workflow tier.
- **Guardrails:** no_human's test tamper guard, and Claw Orchestrator's protected-test hashing and third outcome for a check that never ran.

## Claims the source did not support

- Warren does not steer a running session, and never passes the requested model to Claude Code.
- no_human's review by "a different model" is a different Claude model on the same subscription. A model can waive its tamper guard.
- Claw Orchestrator's durable workflows re-run the step that was in flight at a crash.
- Scion's REST interface and per-project secrets need its server; its server-less mode was being removed in the week of the survey.

## Findings on the Harnesses

- Claude Code's workflows start only Claude workers.
- The three CLIs' headless modes share one shape: a prompt in, JSON events out, a session ID, and resume by that ID.
- Anthropic's documentation says `--bare` will become the default for `claude -p`. Bare mode does not read a subscription sign-in.

## Limits

- Projects outside the table were judged from READMEs and API metadata only.
- The repositories change fast. Several had more than ten commits a day.
- The decision this supports is recorded in [ADR 0003](../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md).
