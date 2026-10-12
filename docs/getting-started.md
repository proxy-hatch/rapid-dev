---
mdx:
  format: mdx
---

import Tabs from '@theme/Tabs'
import TabItem from '@theme/TabItem'

# Getting started: ship hello

Build a small command, review it independently, and merge your first PR. Then inspect the quality measurements.

The setup agent handles repositories, issue tracking and configuration. You choose destinations and models, complete logins, and grant permissions. This preview uses supervised sessions. Automatic delivery remains blocked.

## 1. Prepare your tools

Use a POSIX terminal with Python 3.12+, [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/) and [GitHub CLI](https://cli.github.com/).

```sh
python3 --version
git --version
uv --version
gh --version
```

Choose your interview tool below. This choice stays synchronized across the page. Worker and reviewer choices come later.

<Tabs groupId="rapid-ship-harness" defaultValue="codex">
<TabItem value="codex" label="Codex">

Install [Codex CLI](https://developers.openai.com/codex/cli/), then check:

```sh
codex --version
```

</TabItem>
<TabItem value="claude" label="Claude Code">

Install [Claude Code](https://code.claude.com/docs/en/quickstart), then check:

```sh
claude --version
```

</TabItem>
<TabItem value="agy" label="Antigravity">

Install [Antigravity CLI](https://antigravity.google/docs/getting-started?tab=cli), then check:

```sh
agy --version
```

</TabItem>
</Tabs>

Each command prints a version. Install any missing tool before continuing. Complete your coding tool's login when it opens. The setup interview handles GitHub and Linear authentication.

## 2. Install rapid-ship

For a fresh trial:

```sh
mkdir -p "$HOME/rapid-ship-demo"
cd "$HOME/rapid-ship-demo"
git clone https://github.com/proxy-hatch/rapid-ship.git
cd rapid-ship
./devctl setup
./devctl --version
mkdir -p ../hello-rapid-ship
cd ../hello-rapid-ship
```

Setup builds the controller in `rapid-ship/.controller/`. After build logs, a new installation prints:

```text
Installed devctl at .controller/bin/devctl.
```

If this checkout already has an installation, expect:

```text
devctl is already installed at .controller/bin/devctl.
```

Both results mean setup succeeded. Neither starts a project interview. The version command prints `devctl 0.1.0` in this preview.

Keep the framework checkout. Your terminal is now in the separate `hello-rapid-ship` project directory.

## 3. Let the interview set up the project

Start your chosen tool in `hello-rapid-ship`, with access to the framework:

<Tabs groupId="rapid-ship-harness" defaultValue="codex">
<TabItem value="codex" label="Codex">

```sh
codex --add-dir ../rapid-ship
```

</TabItem>
<TabItem value="claude" label="Claude Code">

```sh
claude --add-dir ../rapid-ship
```

</TabItem>
<TabItem value="agy" label="Antigravity">

```sh
agy --add-dir ../rapid-ship
```

</TabItem>
</Tabs>

Paste this request:

> Read ../rapid-ship/.agents/skills/rapid-ship/SKILL.md and use setup for this hello-rapid-ship directory. Ask one question at a time. The approved scope is a Python command with no third-party dependencies. `python3 hello.py` prints `Hello, world!` and exits 0. `python3 hello.py --name Ada` prints `Hello, Ada!` and exits 0. An empty name prints a clear error to stderr and exits 2. Successful output ends with one newline. Save this scope in docs/design.md. Use unittest subprocess tests and a named test check: `python3 -m unittest discover -s tests -v`. GitHub Actions must run that check. Prepare a local repository and a private GitHub repository under my selected account. Set up official Linear access and create or reuse a project I select. Handle configuration and integration steps, asking me only for choices, login, missing identity details or permission grants. Show available models and help me choose a small worker and a large reviewer. Keep one task at a time and no release target. I authorize local execution of this supervised demo's commands and tests. Keep controller environment restrictions separate. Save progress in .devctl/state/setup.md and the nonsecret summary in docs/setup.md, including exact worker and reviewer commands. Publish the checked setup files on main and leave codex/hello ready for the feature. Do not implement the command, register tasks, or enable unattended delivery.

The agent handles GitHub login, repository creation, Linear connection, project discovery and configuration. It saves each completed step so you can resume.

For Linear, choose a workspace, a team and a project. A workspace holds your team's work. The project groups this demo's tasks. If you are new, the agent guides signup and suggests a small `hello-rapid-ship` project. You complete browser authentication and any account or admin approval. You do not need to find IDs or compose integration commands.

Expect the agent to report these separately:

- **Read access:** it can read the selected GitHub repository and Linear project.
- **Setup saved:** `devctl`, project settings, skills and `docs/setup.md` exist.
- **Still pending:** the first issue proves task creation, and its real PR proves linking and CI.

A permission error stays visible. An installed connection is not proof that the integration works. If authentication requires a fresh session, follow the exact restart instruction the agent provides.

The interview tool can differ from the worker or reviewer. The large reviewer must use Codex or Claude. The controller does not support agy review. An agy greeting verifies model access, not its required Docker execution environment. A direct supervised agy session does not qualify native controller execution.

## 4. Plan one small task

In the same interview session, paste:

> Use rapid-ship to slice docs/design.md into one leaf task named hello. Save docs/plan.md and tasks.json. Include hello.py, tests/test_hello.py, .github/workflows/test.yml and README.md in its owned paths. Use the current main commit as its base and the named test check. Include all three command behaviors and newline handling in acceptance. Use the Linear destination in docs/setup.md. Create or reuse its hello issue and record the URL. Have an independent reviewer check scope, acceptance and dependencies. Stop before implementation. Do not register or run tasks.json: this walkthrough uses supervised sessions.

Expected: one reviewed task, one Linear issue and a local plan linking them. Open the returned issue link and check its project and acceptance criteria. If access fails, the local plan remains an unsynced draft.

Exit the session. Check the saved setup:

```sh
cd "$HOME/rapid-ship-demo/hello-rapid-ship"
git branch --show-current
./devctl doctor --json
cat docs/setup.md
```

Expect branch `codex/hello` and `autonomy_ready: false`. Read any `doctor` blockers before controller execution. In particular, agy workers require Docker. This walkthrough uses direct supervised sessions and does not run `devctl run`. `doctor` does not certify the Linear/GitHub connection.

## 5. Implement with the worker

Run the exact **worker command** from `docs/setup.md` in this project directory. The agent prepared it with your selected tool and model. Then paste:

> Read .agents/skills/rapid-ship-engineering/SKILL.md and implement the hello task in tasks.json. Follow docs/design.md and docs/plan.md. This is an authorized supervised local session, not a devctl task run. Add a failing behavior test, implement the command, and cover all acceptance cases. Add the GitHub Actions test job and a short project README. Run the checks and report the actual results. Do not commit, push, create a PR, or merge.

Expected: the first test fails before implementation. The completed suite passes. The agent keeps code, tests and CI within the assigned paths.

Exit the session. Run the commands yourself:

```sh
python3 hello.py
python3 hello.py --name Ada
python3 hello.py --name ''
printf 'exit=%s\n' "$?"
python3 -m unittest discover -s tests -v
```

Expected, in order:

- `Hello, world!`
- `Hello, Ada!`
- An error explaining that the name cannot be empty, then `exit=2`.
- Passing tests ending with `OK`.

If any result differs, return to the worker session. Fix the failure before continuing.

## 6. Review independently

Commit the candidate so the reviewer can identify its exact version:

```sh
git add hello.py tests/test_hello.py .github/workflows/test.yml README.md docs/plan.md tasks.json
git commit -m "feat: add hello command"
git rev-parse HEAD
```

Run the exact **reviewer command** from `docs/setup.md` in a fresh session. Then paste:

> Read .agents/skills/rapid-ship-engineering/SKILL.md and review HEAD against main, docs/design.md and docs/plan.md. Check the behavior, tests, CI and repository rules. Run the test command independently if the tool's permissions permit it. Do not edit files. Report actionable findings with file and line, the reviewed commit, and checks actually run. Missing execution is not a passing check.

Expected: an independent review of the committed diff. Fix findings with the worker, rerun tests, commit the fixes, and repeat review of the new HEAD. Keep the review summary for the PR. If an independent reviewer is unavailable, pause this step.

## 7. Open and merge the PR

Exit the reviewer. Publish the branch:

```sh
git push -u origin codex/hello
gh pr create --base main --title "Add hello command" --web
```

GitHub opens a PR form. Add `Fixes ` followed by the Linear issue URL from `docs/plan.md`. Include the test result and independent review summary, then submit. The prefix tells [Linear to link the PR](https://linear.app/docs/github#link-through-pull-requests).

```sh
gh pr checks --watch
gh pr diff
```

Expected: the test check passes, and the diff contains the planned change. No checks is not a pass. Fix failed checks before merging.

Open the Linear issue and check that its GitHub PR attachment appears. If missing, ask the setup agent to inspect repository access and the link. Keep that check pending until the attachment appears.

Merge from the terminal yourself:

```sh
PR_NUMBER=$(gh pr view --json number --jq .number)
gh pr merge "$PR_NUMBER" --squash
gh pr view "$PR_NUMBER" --json state,mergedAt
git switch main
git pull --ff-only
python3 hello.py --name Ada
python3 -m unittest discover -s tests -v
```

Expected: PR state `MERGED`, a nonempty `mergedAt`, `Hello, Ada!`, and passing tests. If policy puts the PR in a merge queue, wait for `MERGED` before pulling.

Ask the setup agent to record the observed issue/PR link and CI result. It should check the Linear status after merge and complete the issue if needed. The setup notes must distinguish these observed results from any remaining gaps.

## 8. Inspect the results and improve

```sh
./devctl metrics sync-github
./devctl metrics
./devctl status
./devctl logs
./devctl evidence
```

Expected:

- GitHub sync imports PR and Actions observations without duplicating unchanged records.
- Metrics include the merged PR, observed revisions and CI duration. Human review minutes and deployment data remain missing unless supplied.
- `status` shows `tasks: []`. This walkthrough did not dispatch a controller task.
- Logs show devctl commands. `evidence` shows `receipts: []`. Session checks and review are not controller evidence.

PR revision count measures observed code versions. It is a lower bound, not every commit. See [metrics](metrics.md) for details.

For feedback, start your chosen interview tool again from the project:

<Tabs groupId="rapid-ship-harness" defaultValue="codex">
<TabItem value="codex" label="Codex">

```sh
codex --add-dir ../rapid-ship
```

</TabItem>
<TabItem value="claude" label="Claude Code">

```sh
claude --add-dir ../rapid-ship
```

</TabItem>
<TabItem value="agy" label="Antigravity">

```sh
agy --add-dir ../rapid-ship
```

</TabItem>
</Tabs>

Paste:

> Use rapid-ship-improve. During this hello trial, [describe the repeated step, failure or missing capability]. Read this project's settings, logs and setup notes. Fix a project setting if that resolves it. Otherwise, reproduce the problem and prepare a focused, tested framework PR. Keep the installed controller unchanged while it owns active work.

Keep one worker until quality data justifies more. Promote repeated corrections to checks. This first PR does not qualify unattended delivery.

Continue with [Usage](usage.md) for controller commands and [environments](environments.md) for execution requirements.
