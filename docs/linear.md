# Linear task management

Linear tracks what to build and what depends on it. GitHub holds code and PRs. rapid-ship chooses workers, models and execution environments.

New to Linear? Start with its official [Intro to Linear](https://linear.app/learn/intro-to-linear). You need four terms for setup:

| Term | Meaning |
| --- | --- |
| Workspace | The shared space for your organization's work. |
| Team | A group with its own issues and workflow. |
| Project | A delivery effort that groups related issues. |
| Issue | One item of work, such as a rapid-ship task. |

## Set up through the interview

Start the [setup interview](getting-started.md#3-let-the-interview-set-up-the-project) in your project. The agent handles connection commands and resource IDs.

1. **Choose the destination.** Select your workspace, team and an existing or new project when asked. Complete account signup or login if needed.
2. **Grant access.** The agent connects official Linear tools and prepares the [GitHub integration](https://linear.app/docs/github). Grant the required permissions or request organization approval.
3. **Check the result.** The agent reads the selected project and records access checks in `docs/setup.md`. Keep any failed or untested checks visible.

The first planned task verifies issue creation. Its actual PR verifies linking and status changes. These checks remain pending until that work exists; setup does not create throwaway issues or PRs. GitHub Issue synchronization is unnecessary: keep the backlog in Linear.

Expect a setup summary with your chosen destinations, successful checks and pending checks. Progress is saved in gitignored `.devctl/state/setup.md`, so the interview can resume after login. Neither the CLI interview nor `doctor` checks live connections by itself.

The setup skill uses official [Linear MCP](https://linear.app/docs/mcp) or the [GraphQL API](https://linear.app/developers/graphql). It requires no third-party CLI or public webhook server. Store connection names and secret-store references, never tokens in project files or worker context.

Controller-managed synchronization and Linear Agent Sessions are not implemented. The skill updates and checks Linear explicitly. An unsynced local plan remains a draft.

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

## Contributor reference: task updates

These details guide the setup skill and integration maintainers. Users can inspect the selected issues and PR links through the interview.

Snapshot the accepted issue and dependencies into each attempt. Refresh before dispatch, resume and delivery; material scope changes need review. Record writes before sending them and reconcile uncertain results before retry. Check GraphQL errors even on HTTP 200 and share a request budget across workers. Reconcile after downtime even with webhooks.

Assign one owner per status transition. Native PR automation can handle review and merged states; devctl reports execution and blockers. Complete only on the intended trunk. If native automation cannot preserve cancellation or superseding scope, use relation-only PR links and controller-owned transitions. Old events must not revive or complete replacement work. Never close an epic through a PR that completes only one child.

Until synchronization exists, the skill rereads issues, cancels affected devctl work and reconciles PRs explicitly. Changed registered specifications require reviewed replacement task IDs and updated dependencies; removing JSON entries does not stop stored work. Tracker state and parent auto-completion never authorize delivery. GitHub checks must match the actual code, and merged remains distinct from deployed.

## Contributor reference: native agent integration

The following requirements describe an unimplemented adapter. They are not steps for setting up a rapid-ship project. Linear's Agent APIs need compatibility trials before native delegation is enabled.

### Identity and permissions

Record Linear workspace, team and project IDs; GitHub repository ID, `owner/name` and trunk; the accountable human; and team-specific workflow state IDs. Reuse existing records. Map each accepted task to its Linear issue UUID and readable identifier. Record PR-linking and status rules, including public linkback content.

Linear records human responsibility and can record delegation to an app. A Linear delegate or session does not select rapid-ship's internal workers.

The proposed [OAuth app](https://linear.app/developers/agents) requires workspace-admin installation with `actor=app`, required read/write permissions and `app:assignable`. Add `app:mentionable` for mentions. Save the workspace's app-user ID from `viewer` and handle [token refresh](https://linear.app/developers/oauth-2-0-authentication). App actors cannot request `admin` scope.

### Events and agent sessions

Before enabling Agent Sessions, configure session and permission-change events with a working public HTTPS receiver or relay. Verify signatures, deduplicate deliveries, persist them before acknowledgement and support stop requests. See [webhook requirements](https://linear.app/developers/webhooks).

Follow Linear's [AIG](https://linear.app/developers/aig): disclose the agent identity, show useful progress, preserve human responsibility and stop when asked. Publish concise action summaries, results and decision explanations; do not expose private model reasoning, credentials or raw internal prompts.

The [session adapter](https://linear.app/developers/agent-interaction) must acknowledge webhook delivery within five seconds and a new session within ten seconds. A `thought` activity can say “Received; checking the task.” Use `action` for work updates, `elicitation` for a required decision, `response` for the result and `error` for failure. Linear derives session state from these activities. Link the PR through `externalUrls`; session completion does not mean the issue was merged or deployed.

On a [stop signal](https://linear.app/developers/agent-signals), halt the worker and further work immediately, then acknowledge disengagement. Record uncertain external operations locally; reconcile before any later authorized resume. Do not let a delayed event restart stopped work. Cancellation or changed delegation also requires reconciling active attempts.

Before enabling native agent mode, verify delegation, acknowledgement and cancellation in compatibility trials. Record identities, tested permissions, URLs and results without secrets.
