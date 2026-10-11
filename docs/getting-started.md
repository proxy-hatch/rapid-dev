# Getting started: ship hello

Build a small command, review it independently, and merge your first PR. Then inspect the quality measurements.

This walkthrough uses Python and Codex. Your projects can use any language and [supported agent](agents.md). The current preview runs this walkthrough in supervised agent sessions. Automatic delivery remains blocked. Keep the same terminal open throughout the walkthrough so the model variables remain available.

## 1. Prepare your tools

Use a POSIX terminal with Python 3.12+, [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/), [GitHub CLI](https://cli.github.com/) and [Codex CLI](https://developers.openai.com/codex/cli/).

Check the installations:

```sh
python3 --version
git --version
uv --version
gh --version
codex --version
```

Each command prints a version. If a command is missing, install that tool before continuing.

Log in if needed:

```sh
codex login
gh auth login --hostname github.com --scopes workflow
gh auth status
```

Complete the browser prompts. GitHub reports the active account. Codex must have access to two distinct models for the worker and reviewer.

For an existing GitHub OAuth login, add workflow permission if missing:

```sh
gh auth refresh --hostname github.com --scopes workflow
```

For a supplied token, grant repository code and workflow writes through its token settings instead.

For Linear, use its [official MCP connection](https://linear.app/docs/mcp). If Codex already has that connection, reuse it. Otherwise:

```sh
codex mcp add linear --url https://mcp.linear.app/mcp
codex mcp login linear
```

Complete Linear's authorization prompt. The setup interview will check access to your selected team and project.

## 2. Install rapid-ship

Use a new directory for this trial:

```sh
mkdir -p "$HOME/rapid-ship-demo"
cd "$HOME/rapid-ship-demo"
git clone https://github.com/proxy-hatch/rapid-ship.git
cd rapid-ship
./devctl setup
./devctl --version
```

Setup builds the controller in `rapid-ship/.controller/`. The last command prints `devctl 0.1.0` in this preview.

Keep this framework checkout. The hello project will use its installed controller through a local `./devctl` wrapper.

## 3. Create the hello project

```sh
mkdir -p ../hello-rapid-ship/docs
cd ../hello-rapid-ship
git init -b main
cat > docs/design.md <<'DESIGN'
# Hello command

Approved scope: a Python command with no third-party dependencies.

- python3 hello.py prints Hello, world! and exits 0.
- python3 hello.py --name Ada prints Hello, Ada! and exits 0.
- python3 hello.py --name '' prints an error to stderr and exits 2.
- Successful output ends with one newline.
- Test the command through subprocesses using unittest.
- GitHub Actions runs python3 -m unittest discover -s tests -v.
- No package publishing, deployment, or unattended merge.
DESIGN

gh repo create hello-rapid-ship --private --source=. --remote=origin --disable-issues
gh repo view --json nameWithOwner --jq .nameWithOwner
```

GitHub creates a **private** repository and prints `YOUR_ACCOUNT/hello-rapid-ship`. If that name already exists, choose a different name in the `gh repo create` command.

In Linear, connect this repository through [Settings → Integrations → GitHub](https://linear.app/docs/github). Grant access to the new repository. Keep GitHub Issues disabled: the task belongs in Linear.

## 4. Complete the setup interview

Start Codex from the framework checkout with access to the project:

```sh
cd "$HOME/rapid-ship-demo/rapid-ship"
codex --add-dir ../hello-rapid-ship
```

Paste this request:

> Use rapid-ship setup for ../hello-rapid-ship. Its approved design is docs/design.md. Ask one question at a time. Use Python standard library and the Codex provider. Allow one task at a time. Select native execution for this supervised trial, no external test resources, and no release target. I authorize local execution of this demo's commands and tests. Use the repository from its origin remote. Set the named test check to `python3 -m unittest discover -s tests -v`. Show the available models and let me choose a small worker and a large reviewer. Check access to my selected Linear team/project and the GitHub repository. Create a Python .gitignore. Do not implement the command or register a task yet.

Answer the model and Linear destination questions. The agent saves your choices and runs the checks. It handles the interview's JSON arguments.

Expected files include `devctl`, `.devctl/project.json`, `AGENTS.md` and the `.agents/skills/` directory. Authentication failures and missing integrations must remain visible.

Exit the session. In the terminal:

```sh
cd "$HOME/rapid-ship-demo/hello-rapid-ship"
./devctl doctor --json
```

With setup complete, expect `configuration_ready: true` and `autonomy_ready: false`. Expect a warning about an unverified live compatibility trial. `ready: false` requires reading the listed blockers before controller execution. `doctor` does not test the Linear/GitHub connection.

Check your Git author identity:

```sh
git var GIT_AUTHOR_IDENT
```

Expected: your name and email. If either is missing or incorrect, replace the sample values below and set them for this repository:

```sh
git config user.name "Your Name"
git config user.email "you@example.com"
```

Save and publish the setup:

```sh
git add .gitignore .devctl .agents .claude AGENTS.md CLAUDE.md devctl docs/design.md
git commit -m "chore: initialize hello project"
git push -u origin main
git switch -c codex/hello
```

Expected: `main` exists on GitHub, and the active local branch is `codex/hello`. Credentials, provider caches and runtime state stay ignored.

## 5. Plan one small task

Read the selected reviewer model from your configuration:

```sh
REVIEWER_MODEL=$(python3 -c 'import json; print(json.load(open(".devctl/project.json"))["models"]["large"]["model"])')
codex --model "$REVIEWER_MODEL"
```

Paste:

> Use rapid-ship to slice docs/design.md into one leaf task named hello. Save docs/plan.md and tasks.json. Include hello.py, tests/test_hello.py, .github/workflows/test.yml and README.md in its owned paths. Use the current main commit as its base, the configured default environment and the named test check. Include all three command behaviors and newline handling in acceptance. Create the issue in my selected Linear project and record its URL. Have an independent reviewer check scope, acceptance and dependencies. Stop before implementation. Do not register or run tasks.json: this walkthrough uses supervised sessions.

Expected: one reviewed task, one Linear issue, and a local plan linking them. There is no separate epic or story for this small change. If Linear is unavailable, the plan remains an unsynced draft.

## 6. Implement with the worker

Exit the planning session. Start a new session with the selected worker model:

```sh
WORKER_MODEL=$(python3 -c 'import json; print(json.load(open(".devctl/project.json"))["models"]["small"]["model"])')
codex --model "$WORKER_MODEL"
```

Paste:

> Use rapid-ship-engineering implement for the hello task in tasks.json. Follow docs/design.md and docs/plan.md. This is an authorized supervised local session, not a devctl task run. Add a failing behavior test, implement the command, and cover all acceptance cases. Add the GitHub Actions test job and a short project README. Run the checks and report the actual results. Do not commit, push, create a PR, or merge.

Expected: the first test fails before implementation. The completed test suite passes. The agent keeps code, tests and CI within the assigned paths.

Exit the session. Run the command yourself:

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

## 7. Review independently

Commit the candidate so the reviewer can identify the exact version:

```sh
git add hello.py tests/test_hello.py .github/workflows/test.yml README.md docs/plan.md tasks.json
git commit -m "feat: add hello command"
git rev-parse HEAD
REVIEWER_MODEL=$(python3 -c 'import json; print(json.load(open(".devctl/project.json"))["models"]["large"]["model"])')
codex --sandbox read-only --model "$REVIEWER_MODEL"
```

Paste:

> Use rapid-ship-engineering review. Review HEAD against main, docs/design.md and docs/plan.md. Check the behavior, tests, CI and repository rules. Run the test command independently if the sandbox permits it. Do not edit files. Report actionable findings with file and line, the reviewed commit, and checks actually run. Missing execution is not a passing check.

Expected: a separate review of the committed diff. Fix findings in the worker session, rerun tests, commit the fixes, and repeat review of the new HEAD. Keep the review summary for the PR. If an independent reviewer is unavailable, pause this step.

## 8. Open and merge the PR

Exit the reviewer. Publish the branch:

```sh
git push -u origin codex/hello
gh pr create --base main --title "Add hello command" --web
```

GitHub opens a PR form. Add the Linear issue URL, the test result, and the independent review summary. Submit the form.

Check CI from the terminal:

```sh
gh pr checks --watch
gh pr diff
```

Expected: the test check passes, and the diff contains the planned change. No checks is not a pass. Fix failed checks before merging.

Check that Linear shows the linked PR. Then merge from the terminal yourself:

```sh
PR_NUMBER=$(gh pr view --json number --jq .number)
gh pr merge "$PR_NUMBER" --squash
gh pr view "$PR_NUMBER" --json state,mergedAt
git switch main
git pull --ff-only
python3 hello.py --name Ada
python3 -m unittest discover -s tests -v
```

Expected: PR state `MERGED`, a nonempty `mergedAt`, `Hello, Ada!`, and passing tests. If repository policy puts the PR in a merge queue, wait for `MERGED` before pulling.

Check the Linear issue's status. If the integration did not complete it, mark it done after checking the merge.

## 9. Inspect the results

```sh
./devctl metrics sync-github
./devctl metrics
./devctl status
./devctl logs
./devctl evidence
```

Expected:

- GitHub sync imports PR and Actions observations. Repeating the sync does not duplicate unchanged observations.
- Metrics include the merged PR, observed revisions and CI duration. Human review minutes and deployment data remain missing unless supplied.
- `status` shows `tasks: []`. This walkthrough did not dispatch a controller task.
- Logs show devctl commands. `evidence` shows `receipts: []`. The supervised session's checks and review are not controller evidence.

PR revision count measures observed code versions. It is a lower bound, not a count of every commit. See [metrics](metrics.md) for collection and missing-data rules.

## 10. Improve the next run

Start a session with access to the framework source:

```sh
codex --add-dir ../rapid-ship
```

Paste a specific observation:

> Use rapid-ship-improve. During this hello trial, [describe the repeated step, failure or missing capability]. Read the project's settings and logs. Fix a project setting if that resolves it. Otherwise, reproduce the problem and prepare a focused, tested framework PR. Keep the installed controller unchanged while it owns active work.

The improvement skill uses the project's local framework link. Project feedback stays connected to the source that produced it.

Keep one worker until you collect enough quality data to justify more. Promote repeated corrections to checks. This first PR does not qualify unattended delivery.

For controller execution, task state and environment requirements, continue with [Usage](usage.md) and [environments](environments.md).
