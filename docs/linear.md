# Linear task management

**Linear owns scope and tasks. GitHub owns code and PRs. Devctl owns execution attempts and check results.** Do not maintain a second task backlog in GitHub Issues.

This is the selected design. The planning skill can use a configured Linear connection; automatic devctl synchronization is not implemented yet.

Until the adapter exists, the skill reads the selected team/project and existing issues, saves task-to-issue mappings in its plan, and reconciles uncertain writes before retry. Without a working connection, it produces an explicitly unsynced local draft.

## Work structure

| Planning concept | Linear record |
| --- | --- |
| Goal spanning projects | Initiative, when useful |
| Coherent delivery effort | Project |
| Delivery phase | Milestone, when useful |
| Epic or optional story within a project | Parent issue |
| One worker assignment | Leaf issue, normally one PR |
| Required predecessor | Blocking relation |

Use only the levels that help. Do not turn every epic into a project or require stories for straightforward work. A leaf issue holds one outcome, owned paths, exclusions, dependencies, acceptance checks and the approved design reference. The [task-slicing skill](task-slicing.md) owns creating that plan and checking coverage.

## Connections

Use the [official GraphQL API](https://linear.app/developers/graphql) for deterministic controller synchronization. It works from Python without adding a TypeScript service. Treat GraphQL errors as failures even when HTTP returns 200.

Agents can use [Linear's official MCP](https://linear.app/docs/mcp) or a pinned CLI such as [schpet/linear-cli](https://github.com/schpet/linear-cli), which supports JSON output and agent workflows. That CLI is third-party; Linear's official `linear-import` tool serves imports. No general-purpose Linear CLI was available on the PATH checked during this investigation.

Use [Linear's GitHub integration](https://linear.app/docs/github) to link PRs. Include the leaf issue ID in the branch/PR and its URL in the task record. Never use an epic's closing reference for a PR that completes only one child task.

## Controller adapter

1. Read the selected team/project, issue UUID and identifier, content, update time, state, parent, blockers and linked PRs. Resolve team-specific state IDs; do not hard-code status names.
2. Save stable task-to-issue mappings and record each intended write before sending it. Reconcile uncertain outcomes instead of creating duplicate issues or comments.
3. Snapshot the accepted assignment into each attempt. Refresh before dispatch, resume and delivery; a material scope change requires review. Workers receive the assignment, not controller credentials.
4. Report short outcomes and PR/check links. Reconcile cancellation, reassignment and scope edits with active attempts.

Assign one owner per status transition. Prefer Linear's native PR integration for review and merged states; devctl reports execution and blockers. Configure completion for merge into the intended trunk, including stacked work. If devctl owns PR transitions instead, disable the corresponding native automation and use non-closing relations. Merged and deployed remain different states.

Cancellation and superseding scope take precedence over delayed PR events. Ignore events for older assignment versions; they must not revive or complete the replacement assignment. If native status automation cannot preserve those decisions, use non-closing PR relations and controller-owned transitions instead. In the current skill workflow, reread issues before dispatch/resume/delivery, cancel affected devctl work and reconcile its PR manually. Changed registered specifications require reviewed replacement task IDs and updated downstream dependencies; deleting an entry from a JSON file does not stop stored work.

Tracker state never authorizes delivery. Parent auto-completion, manually closed issues and stale PR links cannot replace checks against the actual code. For public repositories, use minimal GitHub linkbacks so private planning descriptions are not copied into PR comments.

Start with explicit sync, startup/resume reconciliation and a shared request budget. A laptop does not need a public endpoint for that. Later, a [webhook relay](https://linear.app/developers/webhooks) can verify signatures, deduplicate events and enqueue them durably. Reconcile after downtime even when webhooks are enabled.

For a durable integration, use an [app identity](https://linear.app/developers/oauth-actor-authorization). Linear can keep a human assignee while an [agent delegates the execution](https://linear.app/developers/agent-best-practices). Agent-session UX can follow the first working sync adapter.
