---
mdx:
  format: mdx
---

import Tabs from '@theme/Tabs'
import TabItem from '@theme/TabItem'

# Getting started: ship hello

Learn to take an approved design through setup, planning, implementation and review. We will build a small hello command and merge one PR.

You will practice the same requests you can use for your own project. The hello design and Python checks are just this lesson's example. Projects can use any language.

This preview uses **supervised sessions**: you start each coding or review session and inspect its result before continuing. Automatic delivery remains blocked.

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

Each command prints a version. Install any missing tool before continuing. Complete your coding tool's login when it opens. The setup interview handles GitHub and Linear authentication. GitHub stores code and PRs. Linear tracks tasks.

New to Linear? Its [Intro to Linear](https://linear.app/learn/intro-to-linear) explains the workspace, teams, projects and issues. You can read it before the interview. You do not need to configure an integration yourself.

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

### Supply the design

rapid-ship starts from an approved design. For this lesson, create the example design in your `hello-rapid-ship` directory:

```sh
mkdir -p docs
cat > docs/design.md <<'EOF'
# Hello command

Build a Python command with no third-party dependencies.

- `python3 hello.py` prints `Hello, world!` and exits 0.
- `python3 hello.py --name Ada` prints `Hello, Ada!` and exits 0.
- An empty name prints a clear error to stderr and exits 2.
- Successful output ends with one newline.

Use hello.py for the command and tests/test_hello.py for subprocess tests.
Run the tests with: python3 -m unittest discover -s tests -v
GitHub Actions must run this check in .github/workflows/test.yml.
Include a short README with usage examples. No deployment is needed.
EOF
cat docs/design.md
```

**Check:** the file contains the three behaviors above. This is the project's input, separate from the setup request.

### Start setup

Start your chosen tool here, with access to the framework checkout:

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

Load the skill once in this session:

```text
Read ../rapid-ship/.agents/skills/rapid-ship/SKILL.md.
```

Then ask:

```text
Use rapid-ship setup for this project. The approved design is docs/design.md.
Stop after setup.
```

This is the reusable setup request. For your own project, supply its design file and answer the interview with its choices.

### Answer the interview

The agent asks one question at a time. Use these choices for this lesson:

| When asked about | Choose |
| --- | --- |
| Repository | A private `hello-rapid-ship` repository under your selected GitHub account. |
| Linear | Your workspace and team, with a new or existing `hello-rapid-ship` project. |
| Providers and models | An available small worker and a large reviewer. Choose the exact models from the offered catalog. |
| Concurrent work | One task at a time. |
| Deployment | None. |
| Execution permission | Allow this demo's supervised local commands and tests. Keep any controller environment requirements separate. |

The large reviewer can use Codex, Claude or Antigravity. Your interview tool does not limit that choice.

The agent configures GitHub and Linear. You sign in, choose destinations and grant requested permissions. A Linear **workspace** holds your teams. A **project** groups the work. An **issue** tracks one task.

**Check:** the agent reports repository and Linear read access. The project now has `devctl`, its skills, settings and `docs/setup.md`. That summary includes exact commands to start the worker and reviewer.

The first task and PR will check issue creation, PR linking and CI. Those checks should still show as pending. If login requires a restart, use the agent's restart command, then repeat the same setup request. It resumes from saved progress.

## 4. Plan one small task

First, save the setup as the version the feature will build on. In the setup session, ask:

```text
Check the setup files, then commit and push them to main in the selected repository.
Stop before implementation.
```

**Check:** the agent reports a successful push of the setup files. Resolve a failed push before continuing.

Next, ask it to turn the design into work:

```text
Use rapid-ship to plan docs/design.md for supervised sessions.
Stop after independent plan review.
```

rapid-ship derives the task scope, file ownership, dependencies and checks from the design. You inspect the result.

**Check:** `docs/plan.md` and `tasks.json` describe one reviewed task for this example. Open its Linear issue link. Check that it covers all three behaviors, tests, CI and the README. If Linear access fails, the local plan is still an unsynced draft.

Exit the session. In your terminal, create the feature branch:

```sh
cd "$HOME/rapid-ship-demo/hello-rapid-ship"
git switch -c codex/hello
./devctl doctor --json
```

**Check:** Git reports branch `codex/hello`. `doctor` reports `autonomy_ready: false`. This supervised lesson does not enable automatic delivery.

We will start the worker ourselves. We do not register these tasks or run `devctl run`. To learn that separate path, see [controller execution](usage.md#run-through-devctl).

## 5. Implement with the worker

Run the exact **worker command** from `docs/setup.md` in this project directory. The agent prepared it with your selected tool and model. Then paste:

```text
Use rapid-ship-engineering to implement the task in docs/plan.md.
Run its checks. Stop before committing or publishing.
```

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

```text
Use rapid-ship-engineering to review HEAD against main and docs/plan.md.
Do not edit files.
```

Expected: an independent review of the committed diff, with the commit ID and checks actually run. A skipped check is not a passing check. Fix findings with the worker, rerun tests, commit the fixes, and repeat review of the new HEAD. Keep the review summary for the PR. If an independent reviewer is unavailable, pause this step.

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
```

**Check:** PR state is `MERGED`, with a nonempty `mergedAt`. If the PR enters a merge queue, wait for `MERGED`.

Now update your local copy:

```sh
git switch main
git pull --ff-only
python3 hello.py --name Ada
python3 -m unittest discover -s tests -v
```

Expected: `Hello, Ada!` and passing tests from the merged code.

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

```text
Use rapid-ship-improve. During this trial, I noticed: [describe the problem].
```

Replace the bracketed text with what you did, what you expected and what happened. The skill investigates using the project context.

Keep one worker until quality data justifies more. Promote repeated corrections to checks. This first PR does not qualify unattended delivery.

## 9. Repeat with your own project

Keep the rapid-ship checkout. Open your project's directory in your chosen coding tool, with access to that checkout. Load the setup skill as in step 3, using its actual path.

Supply your approved design, then reuse the setup request:

```text
Use rapid-ship setup for this project. The approved design is docs/design.md.
Stop after setup.
```

Change `docs/design.md` if your design has another path. Answer with your project's repository, Linear destination, models and execution needs. The hello program, Python commands and demo branch name do not carry over.

When setup is complete, ask rapid-ship to plan that design. Check the plan before starting a worker. You have now practiced setup → plan → implement → review → PR → measurements.

Use [Usage](usage.md) as a reference for later sessions. See [environments](archive/orchestrator/environments.md) when you are ready to configure controller execution.
