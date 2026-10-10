# Linear task management

**Linear holds the work plan. GitHub holds code and PRs. rapid-dev assigns workers and runs them.** Do not maintain a second backlog in GitHub Issues.

Linear records human responsibility and can record delegation to the rapid-dev app. The rapid-dev scheduler chooses each task's model, harness, environment and worker attempt. A Linear delegate or session does not select those internal workers.

This is the selected design. Today, the planning skill can use an already configured official connection. Automatic setup, synchronization and Agent Session handling are not implemented. Linear's Agent APIs are in developer preview and need compatibility trials. An unsynced local plan is a draft, not a completed setup or a managed assignment.

## Work structure

| Planning concept | Linear record |
| --- | --- |
| Goal spanning projects | Initiative, when useful |
| Coherent delivery effort | Project |
| Delivery phase | Milestone, when useful |
| Epic or optional story within a project | Parent issue |
| One bounded task | Leaf issue, normally one PR |
| Required predecessor | Blocking relation |

Use only the levels that help. Do not turn every epic into a project or require stories for straightforward work. A leaf issue holds one outcome, owned paths, exclusions, dependencies, acceptance checks and the approved design reference. The [task-slicing skill](task-slicing.md) owns creating that plan and checking coverage.

## Initial setup

Both Linear and its GitHub integration belong in initial setup. The following sequence is required design; the bootstrap CLI does not yet perform or verify it.

1. **Identify the project.** Record Linear workspace, team and project IDs; GitHub repository ID, `owner/name` and trunk; the accountable human; and team-specific workflow state IDs. Reuse existing records. Map each accepted task to its Linear issue UUID and readable identifier.
2. **Connect official services.** Use [Linear MCP](https://linear.app/docs/mcp) at `https://mcp.linear.app/mcp` for interactive planning and the [GraphQL API](https://linear.app/developers/graphql) for controller operations. Verify the authenticated identity and access to the selected project. Store connection names and secret-store references, never tokens in project files or worker context. Third-party CLIs are outside this design.
3. **Choose the interaction mode.** Local MCP/API operation can start without a public webhook endpoint. For native delegation, mentions and Agent Sessions, a workspace admin installs the [rapid-dev OAuth app](https://linear.app/developers/agents) with `actor=app`, required read/write permissions and `app:assignable`; add `app:mentionable` for mentions. Save the workspace's app-user ID from `viewer` and handle [token refresh](https://linear.app/developers/oauth-2-0-authentication). App actors cannot request `admin` scope.
4. **Connect GitHub.** An authorized repository admin or organization owner configures [Linear's GitHub integration](https://linear.app/docs/github) for the selected repository. Choose PR-linking and status rules, public linkback content and the intended trunk. Keep task creation in Linear; GitHub Issue synchronization is unnecessary.
5. **Connect events for native agent mode.** Before enabling Agent Sessions, configure session and permission-change events with a working public HTTPS receiver or relay. Verify signatures, deduplicate deliveries, persist them before acknowledgement and support stop requests. Local MCP/API mode uses explicit sync instead. See [webhook requirements](https://linear.app/developers/webhooks).
6. **Prove the selected mode.** In a designated setup trial, verify issue read/write, PR linking, agreed status transitions and cancellation. Native agent mode also verifies delegation and immediate session acknowledgement. Record identities, tested permissions, URLs and results without secrets. Report missing access or unimplemented adapters as blockers; configuration alone is not proof that setup works.

## Agent interaction

Follow Linear's [AIG](https://linear.app/developers/aig): disclose the agent identity, show useful progress, preserve human responsibility and stop when asked. Publish concise action summaries, results and decision explanations; do not expose private model reasoning, credentials or raw internal prompts.

The planned [session adapter](https://linear.app/developers/agent-interaction) must acknowledge webhook delivery within five seconds and a new session within ten seconds. A `thought` activity can simply say “Received; checking the task.” Use `action` for work updates, `elicitation` for a required decision, `response` for the result and `error` for failure. Linear derives session state from these activities. Link the PR through `externalUrls`; session completion does not mean the issue was merged or deployed.

On a [stop signal](https://linear.app/developers/agent-signals), halt the worker and further work immediately, then acknowledge disengagement. Record uncertain external operations locally; reconcile before any later authorized resume. Do not let a delayed event restart stopped work. Cancellation or changed delegation also requires reconciling active attempts.

## Execution and status

Snapshot the accepted issue and dependencies into each attempt. Refresh before dispatch, resume and delivery; material scope changes need review. Record writes before sending them and reconcile uncertain results before retry. Check GraphQL errors even on HTTP 200 and share a request budget across workers. Reconcile after downtime even with webhooks.

Assign one owner per status transition. Native PR automation can handle review and merged states; devctl reports execution and blockers. Complete only on the intended trunk. If native automation cannot preserve cancellation or superseding scope, use relation-only PR links and controller-owned transitions. Old events must not revive or complete replacement work. Never close an epic through a PR that completes only one child.

Until synchronization exists, the skill rereads issues, cancels affected devctl work and reconciles PRs explicitly. Changed registered specifications require reviewed replacement task IDs and updated dependencies; removing JSON entries does not stop stored work. Tracker state and parent auto-completion never authorize delivery. GitHub checks must match the actual code, and merged remains distinct from deployed.
