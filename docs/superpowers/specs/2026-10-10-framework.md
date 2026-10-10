# rapid-dev: approved design

Approved in chat on 2026-10-10, including the subsequent environment amendment. The user authorized implementation with “LGTM. Proceed”.

## Goal

Turn an approved product design into small coding tasks, repeatable development environments, checked pull requests, and eventually unattended releases. Product ideation is excluded. The framework itself is the first pilot. Mac first; real Claude Code and Codex CLI adapters first; Python/AWS and JavaScript/AI profiles follow the first pilot.

The control plane runs locally. Projects are hosted on GitHub. Model inference and deployment resources can be external. A typed Python state machine and SQLite own workflow state. Agent runners, workspace providers, execution providers, and test-resource providers remain replaceable.

## Environment amendment

Docker's observed 4 GB allocation is configurable and is not a concurrency ceiling. Use configurable memory/CPU budgets, actual provider availability, and exclusive leases. New projects start with one task at a time; raise that setting only after measuring quality.

Compose three independent decisions:

1. Workspace: worktree or independent clone.
2. Execution: explicitly approved native execution, Docker, Docker Sandboxes, or an integration such as OpenHands.
3. Test resources: local services, shared installations, dedicated AWS test accounts, or per-PR stacks.

A worktree does not isolate ports, processes, credentials, or shared Git metadata. Fixed internal ports can be reused inside separate namespaces; fixed host ports and global installations require exclusive leases. Cloud account-wide operations also require exclusive leases. Account lifecycle is distinct from ephemeral stack cleanup.

Every task declares environment requirements. The resolver selects an approved compatible recipe; unavailable or unverified capabilities block dispatch. Native execution is never a silent fallback. Provider lifecycle must cover preparation, execution, health, persistence, reset, and cleanup. Crashed attempts retain evidence and ownership until reconciliation.

## Project setup

Use a conversational skill backed by deterministic interview state. Inspect existing configuration, ask for missing decisions, preserve answers, and validate readiness. Consume an existing design document. Separate framework defaults, pinned profiles, project-owned choices, and machine-local settings. Doctor is read-only. Initialization must not overwrite files or execute candidate hooks.

Projects can use any language. The default `custom` profile asks for the project’s checks without adding language-specific tools or source files. `python-cli` is an optional preset with `uv`, Ruff, mypy and pytest. Pydantic validates devctl’s own inputs and saved data; it is not a project requirement. Profiles describe tools, checks, scaffold commands, and environments; executable profile commands run through the selected execution provider.

## Small-task delivery

Each task states one testable outcome, its dependencies, the files it may change, required checks, environment, budget, and allowed actions. Cycles and conflicting concurrently running ownership are rejected. Dependent tasks wait for their dependencies. Fix attempts stop at the configured retry limit. A stronger independent reviewer receives approved requirements, relevant source, exact commit/diff and verification evidence.

Evidence is bound to head SHA, base SHA, policy digest, recipe digest, environment digest, controller version, task, and attempt. Worker output is untrusted. Verification re-executes approved recipes in fresh approved execution environments. Stale, malformed, incomplete, or failed evidence cannot authorize delivery.

## Durable state and effects

Use SQLite WAL and transactional claims. Persist attempts, state transitions, events, leases, evidence and operation intents. Expired leases fence stale owners. A restart cannot blindly repeat an uncertain push, PR, merge, release or deployment. Stable operation keys plus operation-specific reconciliation determine whether an effect happened. Keep artifacts outside disposable workers. Cancellation terminates process trees and leaves durable terminal or reconciliation-needed state.

## Authority

Workers do not receive GitHub merge/admin or production credentials. A host broker performs only validated operations and never runs candidate code. Trusted check recipes come from accepted policy, not candidate modifications. Git operations in the broker use clean temporary repositories with hooks and local configuration disabled; do not invoke hooks from candidate workspaces.

GitHub merges require current, matching evidence, strict server protection, an app-bound required controller check, expected-head matching, and no bypass. Two agents sharing a GitHub identity do not constitute independent human approvals. Missing protection is a blocked capability.

First support planning/inspection and explicit broker commands; unattended grants require human-reviewed trials. The installed controller remains pinned outside candidate changes. A candidate cannot certify its own controller upgrade or weaken its own governing policy.

## Trials and learning

Three representative human-reviewed changes plus recovery/adversarial tests form the initial calibration. Promotion is per capability, recipe, environment and risk class, not a blanket flag. Preapproved recipes can cover specified schema/API/IAM changes. Outside those recipes, or for unresolved design choices, stop for a decision. Retain metrics and corrections; hardening records the strongest enforceable rung. Failed gates suspend the affected capability.

## Metrics and writing (2026-10-10 correction)

Every profile gets the same metrics storage, reports, GitHub sync and import command. GitHub sync collects PR revisions and reviews, change size, elapsed review/merge times, and Actions duration. The controller measures its own check and agent-review time. CI/CD and testing tools supply deployment, rollback, incident, per-test, human-review and mutation results through a common JSON format. Reports show sample counts, sources and missing data. Simulated results do not enter the normal report. See `docs/metrics.md` for definitions.

Before raising concurrency, set project thresholds, collect four baseline weeks and require four passing weeks. These measurements do not authorize merges or change concurrency themselves.

All agents use plain, concise language in conversation, reviews and documents. Lead with the outcome, explain necessary terms once, and retain exact commands and safety conditions where they matter. Shared guidance belongs in project instructions and controller prompts; a review-tool config alone cannot reach every agent.

## Public CLI

`devctl init`, `doctor`, `interview`, `decompose`, `run`, `status`, `resume`, `cancel`, `evidence`, `trial`, `harden`, `new`, `metrics`, `github`, and `release` use structured JSON outputs where appropriate. Project wrapper `./devctl` invokes the pinned package. Error exits distinguish invalid input, blocked capability, and operational failure. Never report a simulated operation as a live one.

## First release acceptance

- Resumable onboarding preserves user files; doctor causes no writes.
- Contracts reject unsafe paths, invalid graphs and inadequate environments.
- Real SQLite concurrency, restart and fencing tests; stable external-effect reconciliation.
- Real subprocess timeout/cancellation and isolated Git workspace tests.
- Runner event parsing rejects malformed/incomplete output; sessions never use ambiguous “latest” continuation.
- Fresh evidence, stale head/base/policy rejection, and trust-policy mutation tests.
- CLI scenario from onboarding through task/review evidence, with simulated external services clearly labelled.
- Build and clean installation smoke test; GitHub Actions runs the same checks.
- Real providers and account bindings are reported unverified until actual compatibility trials pass. Do not grant autonomy or publish a production release merely because unit tests pass.

## Source references

- Overarching playbook: Trust-First Agentic Engineering Playbook — Python Backend on AWS (project guidance)
- https://www.anthropic.com/engineering/managed-agents
- https://docs.docker.com/ai/sandboxes/
- https://docs.docker.com/ai/sandboxes/configuration/credentials/
- https://docs.openhands.dev/openhands/usage/agent-canvas/backend-setup/docker-execution
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
