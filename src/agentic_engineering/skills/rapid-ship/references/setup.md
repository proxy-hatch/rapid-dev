# Guided setup

The agent sets up the project. The user chooses destinations and models, signs in, and grants permissions. Ask only for decisions or actions the agent cannot complete. Give newcomers one sentence of context: GitHub stores code and PRs; Linear tracks tasks. A Linear workspace contains teams, and a project groups related work.

## Resume without duplicates

Read existing configuration, remotes and prior setup notes first. Initialize only the selected project directory; never turn the framework checkout into the new project. Create a design from the user's supplied, approved requirements when needed. Do not invent a hello app or other example unless requested. Preserve custom files, repository visibility, account choices and existing connections.

After project initialization, keep progress in gitignored `.devctl/state/setup.md`. Record chosen destinations, resource IDs, observed results, unresolved actions and the next step. Include the framework and project paths so a restarted session can resume. Do not store credentials, device codes or full authentication responses.

Save the nonsecret project summary in `docs/setup.md`: repository and Linear destination IDs/URLs, observed or pending checks, and the next step. Keep local paths and login details in the gitignored record. Include exact worker/reviewer launch commands using the selected harnesses and model IDs; derive supported flags from installed help. Update existing notes without deleting project-specific guidance.

Before every external write, append its intended operation, destination and identifying details. After success, save the returned ID and result. Mark timeouts or interrupted writes uncertain. Read the remote state and reconcile that operation before retrying. Use an official tool's idempotency feature when available; never assume one exists. If the result cannot be determined, stop that write and report the uncertainty. This applies to repositories, Linear projects/issues, integration settings and PRs.

These notes are agent-maintained setup progress, not controller approval, signed evidence or a substitute for its operation journal. Do not create fields in `.devctl/project.json` or interview answers that their schemas do not support.

## GitHub

The current controller supports `github.com` only. If an existing remote or selected destination uses another host, preserve it and report that controller integration is unsupported. Do not save its `owner/repository` as a usable controller target or redirect it to `github.com`. Continue independent setup work while that connection remains blocked.

1. Inspect the local repository and remotes. Use an existing selected repository when possible. Show account and repository names as choices; resolve their IDs yourself. For a new repository, state the proposed owner/name and private visibility. Create it after the user selects that destination. Use public visibility only when requested; never change an existing repository's visibility or overwrite a remote.
2. Inspect installed `gh` help. Resolve `HOST` from the selected repository; use `github.com` for a new repository unless another host was selected. Run `gh auth status --hostname HOST`, then read the signed-in identity with `gh api --hostname HOST user --jq .login`. If login is needed, start `gh auth login --hostname HOST --web` and hand browser authorization to the user. Substitute the resolved hostname yourself; keep later GitHub commands on that host. Do not print tokens. When the approved setup includes Actions workflows, request the required workflow permission in this flow. With OAuth, `--scopes workflow` adds it; an existing login can use `gh auth refresh --hostname HOST --scopes workflow`. For a supplied token or organization policy, explain the specific missing permission and open its settings instead of switching credentials.
3. Create or connect the chosen repository with `gh` or GitHub's official API. For a new repository, disable GitHub Issues because tasks belong in Linear. Preserve existing repositories' settings. Initialize Git only if missing. Use an existing Git author identity; ask for missing identity values and save them locally, not globally. Check the diff and ignore rules before any initial commit or push; include only project setup files. Do not change Git protocols or keys merely to avoid a login handoff.
4. Read the selected repository and its effective permissions. Save the canonical name and URL, then answer the interview's `repository` question. A successful read does not prove push or workflow access. Verify those through the first real project push and Actions run; report them pending until observed.

Do not leave the user to compose a `gh` command, find a repository ID or copy a routine URL. If authorization needs a person, open the exact page when possible and explain only that action.

## Linear

1. Reuse a working official Linear MCP connection or API credential. Query the authenticated identity, available workspace/team and project records. Do not ask users to paste API keys into the conversation. If no account exists, open [Linear](https://linear.app/) for personal signup. Prepare workspace/team setup when browser tools permit; ask for names or destination choices and let the user complete account-only steps. Resume discovery afterward.
2. If MCP is missing, inspect the chosen harness's help and existing server configuration. Use the [official endpoint](https://linear.app/docs/mcp), `https://mcp.linear.app/mcp`. Preserve unrelated servers and credentials. Never replace a conflicting server named `linear`; choose a distinct name. Register it for the selected project when supported. Run registration from that project's directory, especially with Claude's `--scope local`. These commands are agent operations, checked against local help before use:

   | Harness | Add the server when absent | Authentication |
   |---|---|---|
   | Codex | `codex mcp add linear --url https://mcp.linear.app/mcp` | Start `codex mcp login linear`; the user completes browser authorization. |
   | Claude | `claude mcp add --transport http --scope local linear https://mcp.linear.app/mcp` | Open `/mcp` in the interactive session and complete its authorization flow. |
   | Antigravity | `agy mcp add --type http linear https://mcp.linear.app/mcp` | Use `/mcp` and the installed version's offered authentication flow. |

   Prefer the harness's native connection; never use a third-party Linear CLI. Check scope before adding a server: Codex and some agy versions apply CLI additions beyond one project. For agy, flags precede the server name. Do not guess an unsupported OAuth command. A project-local connection is available to sessions opened in that project, not an existing framework session. If the session started elsewhere or new tools require a restart, save progress and give the exact command to reopen the chosen harness in the project directory. Resume there with the saved notes; grant framework access with the harness's supported directory option when needed. Configuration listings alone never prove authentication or tool access.
3. Read actual Linear data after authorization. Offer workspace, team and project names as choices. Resolve IDs and URLs through the official tools. Reuse a selected project; offer creation in the chosen team when needed. Record the intended creation before sending it. Query the created project afterward. Do not create a sample issue to test permissions; the first approved leaf task supplies the write check.
4. Connect the chosen repository through [Linear's GitHub integration](https://linear.app/docs/github). With browser tools, navigate the selected workspace's integration settings and prepare the GitHub App installation. The user grants its permissions and any required organization approval. Limit installation to the selected repository when supported. If browser tools are unavailable, provide the exact observed settings or authorization URL and one short action. Do not invent deep links or claim the API can perform an admin-only installation.
5. Read the installed integration and repository selection where the tools expose them. If only the UI exposes them, inspect that UI or label the user's confirmation as such. Record what was observed, including whether task status automation is configured. User confirmation and MCP access do not prove that PR linking works.

Official references: [Linear MCP](https://linear.app/docs/mcp), [Linear API](https://linear.app/developers/graphql), [Claude MCP](https://code.claude.com/docs/en/mcp), [Antigravity MCP](https://antigravity.google/docs/mcp?tab=cli).

## Finish setup, verify through real work

Report these states separately: authenticated reads, verified resource writes, integration installation and issue/PR linking. Mark missing evidence pending or blocked, never passed. `doctor` is read-only and configuration-only; it cannot certify these connections.

On the first approved leaf task, create or reuse its Linear issue and re-read it. On its first real GitHub PR, use Linear's documented linking form, such as `Fixes <issue URL>`. If the chosen policy needs a relation without automatic completion, use its documented relation-only keyword instead. A bare URL is not a verified link. Read both the PR and issue to confirm the association, then verify the selected status automation at its actual trigger. Record those IDs and observations. No throwaway PR, synthetic issue or unrequested delivery is needed. Link verification that fails blocks claiming integration success, not independent setup work.

Keep model authentication, environment verification and delivery approval separate. An agy reviewer is read-only by instruction only. The controller blocks the task if Git shows a change in the reviewer's copy, but it cannot see ignored files, writes under `.git/` or outside the copy, or a change that is undone. Under the native provider the reviewer also keeps host file access. agy reads rules and hooks from its working directory, so a candidate can steer its reviewer through any such file its task owns; this is untested live. Say so when the user picks it, and never substitute another model silently. A successful hello trial still cannot grant unattended delivery.
