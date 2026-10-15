# GitHub commands implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner `rapid-ship app`, which creates the Worker App and the Reviewer App once and prints how to install them, and give devctl `doctor`, `dispatch`, `pr` and `review`, with every agent GitHub write made through one of those two Apps.

**Architecture:** Each devctl command reads an App key from the macOS Keychain, signs a JWT and mints an installation token restricted to one repository and the App's named permissions, and keeps the token in memory. REST calls go through a small `http.client` wrapper that never follows redirects. git gets the token only through a `GIT_ASKPASS` helper, with every configured credential helper, extra HTTP header and repository hook switched off for that one git command, and only after git config is shown not to rewrite the remote URL. `rapid-ship app` runs GitHub's manifest flow through a local server on `127.0.0.1` and passes each key to the Keychain on stdin. doctor proves agy's sign-in, and with `--skills` the skills each Harness loads, by starting one headless Session on that Harness's cheapest model (`devctl/harness.py`).

**Tech Stack:** Python 3.12+ standard library (`http.client`, `http.server`, `argparse`, `tomllib`, `fcntl`), PyJWT 2.x with its `crypto` extra (devctl only), git, gh, the macOS `security` tool, uv, pytest, Ruff, mypy; Docusaurus for the docs site.

**Spec:** [Spec 1: Kit and Setup](../specs/2026-10-14-kit-and-setup-design.md), sections 3 (`rapid-ship app`), 6 and 10. Plan 4 of 5 in the [plan index](2026-10-14-kit-and-setup.md).

## Global Constraints

- **Where devctl code lives.** devctl's source is the template under `rapid_ship/templates/common/tools/devctl/`. `uv run rapid-ship sync --in-place` copies it to `tools/devctl/` and updates `.rapid-ship/kit.lock` (spec section 3, dog-fooding). In this plan a path written `devctl/…` means both copies. Edit the template, sync, then test; commit both copies and the lock together. Tests import the vendored copy through plan 3's pytest `pythonpath` (`tools/devctl`, `tests/devctl`). This plan's fixtures live in `tests/devctl/github_fixtures.py`, which `tests/conftest.py` loads with `pytest_plugins`. Do not create `tests/devctl/conftest.py`: a second `conftest` module fails mypy once `tests/` is type-checked (plan 3 Task 2).
- **Guardrails** (plan 3 Task 18 applies them to devctl, `rapid_ship` and `tests/`). Output goes through `sys.stdout.write` and `sys.stderr.write`, because Ruff's T20 forbids `print`; "prints" below means that. No signature uses `Any`: JSON from GitHub is `object`, narrowed with `json_object` and `json_list` (Task 1). Complexity is at most 10. Every test and fixture is annotated for strict mypy. Test files are named `tests/devctl/test_devctl_<area>.py`, so basenames stay unique without `__init__.py`.
- **Processes.** Besides plan 2's `repo._git` (EX-3), which never carries a token, devctl starts processes only through `process.run_process`, called through the module (`from devctl import process`). So the `recorded_argv` and `fake_run` fixtures see every process this plan's code starts. Test helpers in `github_fakes.py` import `run_process` directly, so those patches never reach test setup. `run_process(argv, cwd, timeout_seconds, env=None, input_text=None)` gives the child only `safe_environment(env)`: the caller's `PATH` and `HOME`, `LANG` and `LC_ALL` set to `C.UTF-8`, then `env` (plan 3 Task 1). It has no cancellation. It reports a timeout in `timed_out` and cut output in `stdout_truncated` and `stderr_truncated`, never inside the output; a caller that parses output treats any of the three as a failed command. `rapid_ship` cannot import devctl (plan 3 Task 18's forbidden contract), so `rapid_ship/github_app.py` has its own runner, one `subprocess.run` call with one exception entry.
- **Dependencies.** devctl adds `PyJWT[crypto]>=2.10,<3` and nothing else (index: devctl depends only on PyYAML and PyJWT with its crypto extra). The root dev group adds the same pin so `tests/devctl` can import devctl. The rapid-ship CLI adds nothing.
- **Exit codes** in both CLIs: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run. `dispatch`: 0 admitted, 1 refused, 2 error. `doctor`: 2 when any item is unknown, else 1 when any is missing, else 0.
- **rapid-ship commands in messages.** rapid-ship is fetched from a git tag (index conventions). A devctl message that tells the owner to run rapid-ship prints the full command, `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<kit_version> rapid-ship <command>`, with `kit_version` read from `.rapid-ship/kit.lock`. It never prints `uvx rapid-ship <command>`. `rapid_ship_command` (Task 2) builds it. Task 2 also changes plan 3's kit-step hint `run rapid-ship sync` to `run <rapid_ship_command(root, "sync")>`, keeping the short hint only when the lock is unreadable, and updates plan 3's `test_missing_managed_file_and_link_fail` to expect the full command.
- **Who writes to GitHub.** `dispatch` and `pr` write only as the Worker App; `review` writes only as the Reviewer App. `doctor` reads with the owner's `gh` login, always with `gh api --method GET`, and mints App tokens only to prove the keys and, with `--skills`, to fetch the default branch as `dispatch` does.
- **Tokens.** One token per command, in memory only. git receives it only through `devctl/github/askpass.py`, which reads `RAPID_SHIP_GIT_TOKEN`. A token never appears in argv, a file, a log, the gate log, stdout, stderr or exception text. Never assume a token is 40 characters long.
- **Keys.** Keychain services `rapid-ship/worker-app` and `rapid-ship/reviewer-app` (index `KEYCHAIN_SERVICE`). A key is never written to disk, put in argv or printed. Keychain storage makes these commands macOS-only. An item written by `security` trusts `security` itself (`/usr/bin/security`), so reads show no dialog and any process the owner runs can read both keys (spec section 6). devctl reads through that same tool. Walk therefore does not protect App keys from Workers; Flight needs another key store or access rule first.
- **App permissions** (spec section 3). Worker App: `contents`, `pull_requests` and `issues` write, `metadata` read. Reviewer App: `pull_requests` write, `contents` and `metadata` read. Neither has Workflows, Administration or Checks. Both are private and have no webhook.
- **Claims.** A claim is a remote branch `rs/<issue>`, for example `rs/ENG-123`. The cap is `min(5, max_workers)` in both Modes, because nothing exceeds five supervised Workers until a Flight execution path exists ([ADR 0003](../../adr/0003-walk-on-bare-sessions-orchestrator-deferred.md)). `attempt_limit` defaults to 3.
- **Gate log** (index; `GLOSSARY.md`): `<git common dir>/rapid-ship/gate-log.jsonl`, never tracked. It records every request to a gate with its answer and reason; Spec 3 adds merge-check lines. `dispatch` logs every request, refusals included, while it holds an exclusive `flock` on `<git common dir>/rapid-ship/dispatch.lock`. One JSON object per line, with the index's fields:

  | Field | Value |
  | --- | --- |
  | `time` | UTC, ISO 8601 with seconds |
  | `command` | `"dispatch"` or `"dispatch --clean"` |
  | `issue` | the issue ID as given |
  | `answer` | `"allow"` or `"refuse"` |
  | `reason` | text |
  | `branch` | `"rs/<issue>"`, or `null` when the issue ID is invalid or `project.toml` names no Worker |
  | `attempt` | integer; `0` with a `null` branch |
- **Verdict file:** the JSON schema in spec section 6. A head gets one verdict from the Reviewer App.
- **Repository settings doctor expects** (spec section 8, step 3; the index's Ruleset section): one active ruleset on the default branch. Its `pull_request` rule requires at least one approval and code-owner review, and sets `dismiss_stale_reviews_on_push` and `require_last_push_approval` to `true`. It requires the status check `devctl check` from GitHub Actions (App 15368) and blocks force pushes and deletion. Its bypass list is exactly the repository admin role in `pull_request` mode. Head branches are deleted after merge. A public repository requires approval for workflows from all outside contributors. In Walk, CODEOWNERS has one active line, `* @<owner>`; in Flight, it holds plan 2's Protected-set lines.
- **Local settings doctor expects** (index; spec sections 4 and 8, step 5): gitleaks at plan 3's pinned `GITLEAKS_VERSION` (8.30.1) on `PATH`. A project leaves `tools/devctl` out of its own lint, type, test and uv workspace settings. A new Python project's seeded `pyproject.toml` already does (plan 2 Task 6). `init` never edits an existing project's settings: `rs-setup` adds the excludes (plan 5, spec section 8 step 5) and doctor reports each missing one (Task 8). A repository that tracks `rapid_ship/templates/kit.toml` holds the Kit's source and checks `tools/devctl` itself, so there doctor checks only the uv workspace.
- **Branch** for this work: any prefix except `rs/`.
- **Tests** are offline and say so in their module docstring. GitHub, the Keychain and the browser are simulated, and each Harness is a fake executable on `PATH`. Live behaviour is checked only in Owner steps: the Harness checks in Task 8 Step 1 and Task 10 Step 1, recorded in the Verification record, and Task 12, recorded under `docs/trials/`.
- **Out of scope:** Flight, `devctl gate` and the merge check (Spec 3); the Worker start command templates (Spec 2); choosing repository protection by GitHub plan. doctor reports a ruleset that the plan does not allow as missing.

## Checked facts

Each fact below was checked on 2026-10-14 against its source. Tasks rely on them; Task 12 re-checks the live GitHub ones, and Task 8 Step 1 and Task 10 Step 1 re-check the Harness ones.

| Fact | Source |
| --- | --- |
| `POST /app-manifests/{code}/conversions` returns 201 with `id`, `slug`, `pem`, `client_secret`, `webhook_secret`, `permissions` and `html_url`. The whole manifest flow must finish within one hour. Probot calls it without authentication. | `github/rest-api-description@77ed1ea`; GitHub docs "Registering a GitHub App from a manifest"; `probot/probot` `src/manifest-creation.ts:96-115` |
| The manifest form posts a field named `manifest` to `https://github.com/settings/apps/new?state=<state>`; GitHub redirects to `redirect_url?code=…&state=…`. Only `url` is required. | GitHub docs, same page |
| An App name has at most 34 characters and is unique across GitHub. A private App can be installed only on the account that owns it. | GitHub docs "Registering a GitHub App", "Making a GitHub App public or private" |
| The install URL `https://github.com/apps/<slug>/installations/new/permissions?suggested_target_id=<owner id>&repository_ids[]=<repo id>` preselects the account and repository. | `github/docs` `content/apps/creating-github-apps/about-creating-github-apps/migrating-oauth-apps-to-github-apps.md:92-97` |
| `GET /repos/{owner}/{repo}/installation` and `POST /app/installations/{id}/access_tokens` need an App JWT: RS256, `iat` 60 s in the past, `exp` at most 10 minutes ahead, `iss` the App ID or client ID. The owner's gh token gets 401 (observed on `proxy-hatch/rapid-ship`). The token request takes `repositories` and `permissions` and cannot exceed the installation's grant. Tokens last one hour. A staged rollout since 2026-04-27 gives new tokens a longer stateless format (`ghs_APPID_JWT`). | OpenAPI description; GitHub docs "Generating a JWT for a GitHub App" |
| PyJWT raises `TypeError` unless `iss` is a string, so `iss` is `str(app_id)`. | `jpadilla/pyjwt` `jwt/api_jwt.py` (release 2.15.1) |
| `GET /repos/{o}/{r}/rulesets` lists rulesets; `GET …/rulesets/{id}` adds `rules`, `conditions` and, for a user with write access, `bypass_actors`. `bypass_mode` is `always`, `pull_request` or `exempt`. GitHub Actions is App 15368 (`gh api /apps/github-actions`). The admin repository role is `actor_id` 5, per `integrations/terraform-provider-github` `docs/resources/repository_ruleset.md:305-310`, "at the time of writing"; Task 12 reads it back. | OpenAPI description |
| On the owner's private repositories, `GET …/rulesets` returns 403 "Upgrade to GitHub Pro or make this repository public to enable this feature." | Observed on 18 private repositories |
| The repository object has `delete_branch_on_merge`. `GET /repos/{o}/{r}/actions/permissions/fork-pr-contributor-approval` returns `approval_policy`: `first_time_contributors_new_to_github`, `first_time_contributors` or `all_external_contributors`. On `proxy-hatch/rapid-ship` they are `false` and `first_time_contributors`. | OpenAPI description; observed |
| `POST /repos/{o}/{r}/git/refs` reports an existing ref only as 422 "validation failed" or 409. This plan claims with `git push --force-with-lease=<ref>:` instead: an empty expected value means the ref must not exist, and the same code runs against a local bare repository in tests. `git push --porcelain` marks a rejected ref with `!`. | OpenAPI description; `man git-push` (git 2.39.5) |
| Pull requests are listed with `head=<owner>:<branch>` and `state`, created with `title`, `head`, `base`, `body`, and updated with PATCH. A review is created with `commit_id`, `event` (`APPROVE`, `REQUEST_CHANGES`, `COMMENT`), `body` and `comments` (`path`, `line`, `side`). Listed reviews carry `user`, `commit_id`, `state` and `html_url`. | OpenAPI description |
| API version `2026-03-10` changes none of the fields this plan reads. | GitHub docs "Breaking changes" |
| `security find-generic-password -w` prints the secret as lowercase hex when any byte is not printable, so a PEM comes back as hex. `add-generic-password -w` prompts with `getpass`, which cannot take a multi-line PEM. `security -i` reads commands from stdin into a 4096-byte line buffer and prints no prompt when stdin is not a terminal. A missing item exits 44 (observed). | `apple-oss-distributions/Security` `SecurityTool/macOS/keychain_find.c:429-437`, `keychain_add.c:550`, `security.c:78-79,1176-1199` |
| This machine has credential helpers configured: `osxkeychain` in Xcode's system gitconfig, and `osxkeychain` plus Git Credential Manager in `~/.gitconfig`. An empty `credential.helper` value clears every helper collected before it, URL-scoped ones included (a `credential.http://127.0.0.1:<port>.helper` in repository config was cleared by `-c credential.helper=`, observed). | `git config --show-origin --get-all credential.helper`; `git/git` `credential.c:118-122,186-197`; observed with git 2.39.5 |
| `-c http.extraHeader=` clears only unscoped extra headers. A URL-scoped header, such as the `http.https://github.com/.extraheader` that `actions/checkout` writes, is still sent. `-c http.<exact remote URL>.extraHeader=` cleared generic and scoped headers in every order tried. With a local path as the URL it is harmless. | Observed with git 2.39.5 against a local server that logged request headers |
| `git ls-remote --get-url <url>` applies `insteadOf` only. `git push <url>` also applies `url.<base>.pushInsteadOf`: the push landed in the rewritten repository while `--get-url` printed the original. `git config -z --get-regexp '^url\..*\.(push)?insteadof$'` prints `key\nvalue\0` per rule and exits 1 when there is none. | Observed with git 2.39.5 |
| "By default, the application which creates an item is trusted to access its data without warning. You can remove this default access by explicitly specifying an empty app pathname: -T \"\"." | `man security`, `add-generic-password` (macOS 15) |
| GitHub rejects an App-token push whose commits create or update files under `.github/workflows/` unless the token has the Workflows permission. The reason reads `refusing to allow a GitHub App to create or update workflow <path> without workflows permission`. Not observed here; whether a merge commit that only brings in the base branch's workflow change is rejected is checked in Task 12. | `actions/create-github-app-token` issue 301; GitHub Community thread 182573 |
| Ruff 0.17.0 reports S603 for `subprocess.run(argv, …)` when `argv` is a parameter, and S607 only when the first element is a string literal. An unused code in `noqa` fails RUF100. | Observed with `ruff check --isolated --select S603,S607,RUF100` |
| CPython's `urllib` copies the `Authorization` header to a redirect target on any host. | `urllib.request.HTTPRedirectHandler.redirect_request`, Python 3.14.3 |
| `claude auth status --json` returns `loggedIn` and `authMethod` (`claude.ai` here) and exits 0 when signed in (Claude Code 2.1.287); the old parser expects exit 1 when signed out (`rapid_ship/project/providers.py:204-213`). `codex login status` writes to stderr: `Logged in using ChatGPT` (exit 0), `Not logged in` (exit 1), or `Logged in using an API key - <masked key>` (exit 0) (codex-cli 0.162.0; `openai/codex` `codex-rs/cli/src/login.rs:447-510` at `cb03f28`). `agy --help` (agy 1.3.4 and 1.3.5) lists no auth, login or status subcommand; 1.3.5 lists `models` and the print-mode flags `-p`, `--model`, `--effort`, `--output-format` and `--print-timeout`. | Observed; upstream source |
| Under a root `[tool.uv.workspace] members = ["tools/*"]`, the project's own `uv lock`, `uv sync` and `uv run --locked` fail with `Nested workspaces are not supported` until `exclude` lists `tools/devctl`. | Plan 2 Task 9, observed with uv 0.11.0 |
| gitleaks was not installed on this machine (`command -v gitleaks` found nothing), so the output of `gitleaks version` is unverified here. Plan 3 pins 8.30.1 as `GITLEAKS_VERSION` in `devctl/check/stacks/neutral.py`. | Observed; plan 3 Task 11 |
| `agy models` printed one `<id>\t<name>` line per model on stdout, including `gemini-3.8-flash-high`, `gemini-3.8-flash-medium` and `gemini-3.8-flash-low`, and `Fetching available models...` on stderr (agy 1.3.4). It shows no prices. A successful `agy -p` turn printed its reply on stdout with empty stderr. 5 of 18 container turns failed at Google's eligibility check, none of them a sign-in failure: stdout was empty and stderr held one `error:` line ending `UNAVAILABLE (code 503): The service is currently unavailable.` (four) or `request failed (code 502): HTML response "Error 502 (Server Error)!!1"` (one). | `docs/trials/2026-10-13-login-carry.md` and its raw output |
| agy's exit code alone proves nothing: since 1.1.28 an expired `--print-timeout` returns the partial output and exits 0. Since 1.2.6 a turn that ends on an agent or model error exits 3 with an `AGY_ERROR: {...}` line on stderr. agy must be its own top-level process: Google's FAQ does not support starting it from a Claude Code or Codex session. In this Claude Code 2.1.287 session, `CLAUDECODE` is set; codex-cli 0.162.0's binary contains the name `CODEX_THREAD_ID`, which Task 8 Step 1 confirms in a Codex session. Which variables an agy session sets, and whether agy started inside one answers, is unchecked; Task 8 Step 1 checks both. | `docs/archive/orchestrator/README.md`, Antigravity notes; `agy changelog` (agy 1.3.5); observed |
| Since agy 1.1.11, `agy -p "/skills"` answers without an agent turn, spending quota or leaving a conversation: one tab-separated record per line, or a structured payload under `--output-format json`, which marks built-in skills with `builtin` (1.1.16). agy loads `.agents/skills/` folders. | `agy changelog` (agy 1.3.5) |
| `claude -p --output-format stream-json --verbose` starts with a `system` event of subtype `init` and ends with a `result` event that carries the reply. The init event lists `skills` (plugin skills prefixed `<plugin>:`), `plugins` and `slash_commands`. `--model haiku` ran as `claude-haiku-4-5-20251001` (Claude Code 2.1.287). Whether 2.1.287's own init event has `skills` is checked in Task 10 Step 1. | code.claude.com/docs/en/agent-sdk/plugins and agent-loop; `docs/archive/orchestrator/README.md`; `docs/trials/2026-10-13-login-carry.md` |
| `codex exec --json` prints `thread.started`, `turn.*`, `item.*` and `error` events. An `item.completed` whose `item.type` is `agent_message` carries `text`; a failed turn prints `turn.failed` with `error.message`. No event lists skills. `codex exec` has `--sandbox read-only` and `--ephemeral`. `codex debug models --bundled` lists no prices and describes `gpt-6-luna` as "Fast and affordable model for easier tasks", with `low` its lowest reasoning level (codex-cli 0.162.0). | `openai/codex` `codex-rs/exec/src/exec_events.rs` and `event_processor_with_jsonl_output.rs`; observed |

## Review Focus

1. **The owner's credentials push instead of the App's.** A configured credential helper (Xcode's `osxkeychain`, Git Credential Manager, gh's URL-scoped helper), an `insteadOf` or `pushInsteadOf` rewrite to SSH (such as `url.git@github.com:.pushInsteadOf=https://github.com/`), an `http.extraHeader` carrying someone else's token, or pushing to `origin` makes git authenticate as someone other than the App, and `osxkeychain` would also store the App token. Expected: every token-bearing git command runs against the exact HTTPS URL with `-c credential.helper=` and `-c http.<url>.extraHeader=`, and a URL that any `insteadOf` or `pushInsteadOf` rule rewrites is refused before git runs. Task 3 pins it with `test_configured_credential_helpers_are_bypassed`, `test_extra_headers_from_git_config_are_not_sent` and `test_rewritten_remote_url_is_refused`.
2. **The token leaks.** Paths: argv, the gate log, output, exception text, files, `GIT_TRACE_CURL` with `GIT_TRACE_REDACT=0`, a `pre-push` or `reference-transaction` hook that runs with the token in its environment, and a redirect that carries `Authorization` to another host. Expected: none of them sees the token. Task 1 pins redirects (`test_redirects_are_not_followed`), Task 3 pins hooks and tracing, and Task 6 pins the end-to-end scan (`test_token_stays_in_memory`).
3. **Concurrent dispatch.** Two clones dispatching one issue must produce exactly one claim; the remote push lease decides. Two issues dispatched at once from one clone with one free slot must produce exactly one admission; the remote cannot decide that, so a lock in the git common dir does. Every refusal is logged with its reason. Task 4 pins it with `test_two_clones_claim_one_issue_once` and `test_lock_keeps_the_cap_under_concurrent_dispatch`.
4. **Reviews on the wrong head, or twice.** A verdict whose `head_sha` is not the PR head is refused before any write. A second verdict on a head the Reviewer App already reviewed is refused, while another user's review on that head does not block. GitHub takes inline comments only on lines in the diff, so a finding outside the diff goes into the body. Task 7 pins it.
5. **doctor writes something.** `gh api` with `-f` defaults to POST; `git fetch` writes refs; creating the gate log is a write. Expected: owner reads use `--method GET`, the only non-GET request is the token mint, and the repository and its `.git` are byte-for-byte unchanged. Only `--skills` writes locally: it fetches the default branch as `dispatch` does, and adds and removes one worktree per Harness. Task 9 pins it with `test_doctor_makes_no_writes`.
6. **A probe proves less than it reports, or leaves something behind.** agy's exit code 0 with no reply counted as a sign-in; a 502 or 503 from Google's eligibility check reported as a missing sign-in; agy started from inside another coding session, or doctor's message there not sending the owner to their own terminal; a `--skills` worktree left behind after a failed Session. Expected: only a non-empty reply is ok, service errors are unknown with the error, agy is never started from another coding session (Claude Code, Codex, or agy itself unless Task 8 Step 1 shows agy supports it) and the item asks the owner to run doctor from their own terminal, and the worktree is removed in every case. Task 8 pins the sign-in probe (`test_agy_without_a_reply_is_missing`, `test_agy_eligibility_errors_are_unknown_with_the_error`, `test_agy_is_not_started_from_another_coding_session`); Task 10 pins removal (`test_worktree_is_removed_when_a_session_fails`).

## Starting point

- [ ] Confirm plans 1–3 have merged. The full tier needs network access and gitleaks 8.30.1 on `PATH` (index conventions); check with `gitleaks version`. Then branch:

```sh
git fetch origin
git switch -c github-commands origin/main
./devctl check --tier full
uv run rapid-ship status --strict
git ls-files tools/devctl/devctl/cli.py tools/devctl/devctl/repo.py tools/devctl/devctl/settings.py tools/devctl/devctl/process.py tools/devctl/devctl/check/kit.py tools/devctl/devctl/check/stacks/python.py tools/devctl/devctl/check/stacks/neutral.py tests/conftest.py tests/devctl/check_workspace.py
```

Expected: both checks exit 0 and all nine paths are listed. If either check fails, stop: this plan cannot show its own changes are safe against a red baseline.

- [ ] Read those nine files. This plan uses these names from plans 2–3:
  - `Repo(root: Path, git_common_dir: Path)`, built with `Repo.discover(start)`, with `tracked_files()` (plan 2 Task 11). `git_common_dir` is resolved and shared by every worktree of the clone. `Repo` runs git through its own `_git` (EX-3), not `run_process`. `cli.main` maps `RepoError` and `SettingsError` to exit 2.
  - `cli.main` calls `args.handler(args)`; a command sets it with `set_defaults(handler=…)`, a callable taking `argparse.Namespace` and returning the exit code (plan 2 Task 9).
  - `process.run_process(argv, cwd, timeout_seconds, env=None, input_text=None) -> ProcessResult`, whose result has `argv`, `returncode`, `stdout`, `stderr`, `duration_seconds`, `timed_out`, `stdout_truncated`, `stderr_truncated`, in that order. The child gets only `safe_environment(env)`, and without `input_text` its stdin is `/dev/null` (`rapid_ship/process.py:117` today). There is no `cancel_event` and no `cancelled` field (plan 3 Task 1).
  - `ProjectSettings` has `map_exclude: tuple[str, ...]` after `unguided` (plan 3 Task 4). `check_workspace.project_settings(**changes)` and `check_workspace.gate_settings(**changes)` build settings with test defaults (plan 3 Task 2).
  - `KitLockError`, `is_excluded(path, excluded)`, `managed_paths(root, excluded)` and the lock reader `_entries(root)` in `devctl/check/kit.py` (plan 3 Task 6). Each `_LockFile` has `path`, `kind`, `sha256` and `link`. The lock records no exclusion: `[kit] exclude` in `project.toml`, loaded as `ProjectSettings.excluded`, is the only record (index, "Kit exclusions and skill discovery"). `is_excluded` is devctl's copy of plan 2's rule, held equal to it by a parity test: a path is excluded when it equals an entry or lies below one, and `.claude/skills/<name>` also when `.agents/skills/<name>` is.
  - `GITLEAKS_VERSION = "8.30.1"` in `devctl/check/stacks/neutral.py` (plan 3 Task 11).
  - `[tool.pytest.ini_options] pythonpath = ["tools/devctl", "tests/devctl"]`, and `tests/conftest.py` is the only conftest (plan 3 Task 2).
  - `rapid_ship/templates/kit.toml` `executable` lists the paths `init` and `sync` write with the executable bit: `devctl` and `.githooks/pre-commit` (plan 2 Task 2, plan 3 Task 15). A template's own git mode does not reach the rendered file.
  - `.rapid-ship/exceptions.toml` holds EX-1 to EX-3 and any IDs plan 3 Task 18 added.

### Task 1: GitHub REST client

**Files:**
- Create: `devctl/github/__init__.py` (empty), `devctl/github/api.py`
- Create: `tests/devctl/github_fakes.py`, `tests/devctl/github_fixtures.py`
- Modify: `tests/conftest.py` (add `pytest_plugins = ["github_fixtures"]`)
- Test: `tests/devctl/test_devctl_github_api.py`

**Interfaces:**
- Consumes: nothing beyond the standard library.
- Produces:

```python
API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"


class GitHubError(Exception):
    status: int | None  # HTTP status, or None when no usable response arrived


class GitHubApi:
    def __init__(self, token: str, *, base_url: str = API_URL) -> None: ...
    def request(self, method: str, path: str, body: object | None = None) -> object: ...
    def paginate(self, path: str) -> list[object]: ...


def json_object(
    value: object, what: str
) -> dict[str, object]: ...  # GitHubError(None, f"{what} is not a JSON object")
def json_list(
    value: object, what: str
) -> list[object]: ...  # GitHubError(None, f"{what} is not a JSON list")
```

- [ ] **Step 1: Write the simulated GitHub.** Create `tests/devctl/github_fakes.py`. Later tasks extend it.

```python
"""Simulated GitHub and helpers for offline devctl tests. Nothing here contacts GitHub."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: Any


Reply = tuple[Any, ...]  # (status, body) or (status, body, headers)
Handler = Callable[[Call, re.Match[str]], Reply]


class FakeGitHub:
    """Routes match the path with re.fullmatch; the most recently added route wins."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.routes: list[tuple[str, re.Pattern[str], Handler]] = []
        fake = self

        class _Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                parts = urlsplit(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                call = Call(
                    self.command,
                    parts.path,
                    parse_qs(parts.query),
                    dict(self.headers.items()),
                    json.loads(raw) if raw else None,
                )
                fake.calls.append(call)
                status, body, headers = fake.reply(call)
                data = b"" if body is None else json.dumps(body).encode()
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _serve

            def log_message(self, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def route(self, method: str, pattern: str, handler: Handler) -> None:
        self.routes.append((method, re.compile(pattern), handler))

    def reply(self, call: Call) -> tuple[int, Any, dict[str, str]]:
        for method, pattern, handler in reversed(self.routes):
            match = pattern.fullmatch(call.path)
            if method == call.method and match:
                answer = handler(call, match)
                headers: dict[str, str] = answer[2] if len(answer) > 2 else {}
                return answer[0], answer[1], headers
        return 404, {"message": "Not Found"}, {}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
```

Create `tests/devctl/github_fixtures.py`, the pytest plugin that holds this plan's shared fixtures (later tasks add to it):

```python
"""Fixtures for the offline GitHub command tests. Loaded by tests/conftest.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from github_fakes import FakeGitHub


@pytest.fixture
def github() -> Iterator[FakeGitHub]:
    fake = FakeGitHub()
    yield fake
    fake.close()
```

Add `pytest_plugins = ["github_fixtures"]` to `tests/conftest.py`. pytest accepts it there because that conftest is loaded at startup for any run under `tests/` (checked on 2026-10-14 with pytest 9.1.1 in a scratch layout: `pytest`, `pytest tests/devctl/<file>` and a run from inside `tests/devctl` all found the plugin's fixture). `github_fakes` and `github_fixtures` import by bare name because plan 3 put `tests/devctl` on `pythonpath`.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_github_api.py`:

```python
"""Offline: GitHubApi against the simulated GitHub in github_fakes. No network."""

import secrets

import pytest
from devctl.github.api import API_VERSION, GitHubApi, GitHubError
from github_fakes import FakeGitHub


def test_request_sends_bearer_token_version_and_json(github: FakeGitHub) -> None:
    secret = secrets.token_urlsafe(48)
    github.route("POST", "/repos/o/r/things", lambda call, _: (201, {"echo": call.body}))
    api = GitHubApi(secret, base_url=github.url)
    assert api.request("POST", "/repos/o/r/things", {"a": 1}) == {"echo": {"a": 1}}
    headers = github.calls[-1].headers
    assert headers["Authorization"] == f"Bearer {secret}"
    assert headers["X-GitHub-Api-Version"] == API_VERSION
    assert headers["Accept"] == "application/vnd.github+json"


def test_error_carries_status_and_message_but_never_the_token(github: FakeGitHub) -> None:
    secret = secrets.token_urlsafe(48)
    github.route("GET", "/repos/o/r", lambda call, _: (404, {"message": f"Not Found {secret}"}))
    with pytest.raises(GitHubError) as caught:
        GitHubApi(secret, base_url=github.url).request("GET", "/repos/o/r")
    assert caught.value.status == 404
    assert "Not Found" in str(caught.value)
    assert secret not in str(caught.value)


def test_redirects_are_not_followed(github: FakeGitHub) -> None:
    other = FakeGitHub()
    try:
        github.route(
            "GET", "/repos/o/r", lambda call, _: (301, None, {"Location": f"{other.url}/repos/o/r"})
        )
        with pytest.raises(GitHubError) as caught:
            GitHubApi("t", base_url=github.url).request("GET", "/repos/o/r")
        assert caught.value.status == 301
        assert other.calls == []
    finally:
        other.close()


def test_paginate_follows_next_links_on_the_same_host_only(github: FakeGitHub) -> None:
    github.route(
        "GET",
        "/items",
        lambda call, _: (200, [1, 2], {"Link": f'<{github.url}/items2?page=2>; rel="next"'}),
    )
    github.route("GET", "/items2", lambda call, _: (200, [3]))
    assert GitHubApi("t", base_url=github.url).paginate("/items?per_page=100") == [1, 2, 3]
    github.route(
        "GET",
        "/items2",
        lambda call, _: (200, [3], {"Link": '<https://example.invalid/x>; rel="next"'}),
    )
    with pytest.raises(GitHubError, match="left the API host"):
        GitHubApi("t", base_url=github.url).paginate("/items")


def test_plain_http_is_refused_except_on_loopback() -> None:
    with pytest.raises(ValueError, match="https"):
        GitHubApi("t", base_url="http://api.example.com")


def test_unreachable_server_raises_without_the_token() -> None:
    secret = secrets.token_urlsafe(48)
    with pytest.raises(GitHubError) as caught:
        GitHubApi(secret, base_url="http://127.0.0.1:9").request("GET", "/x")
    assert caught.value.status is None
    assert secret not in str(caught.value)
```

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_github_api.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.github'`.

- [ ] **Step 4: Implement `devctl/github/api.py`.** Use `http.client`, not `urllib`: `urllib` would follow a redirect and copy `Authorization` to its target (Checked facts), and `http.client` follows none.

```python
"""Minimal GitHub REST client. It never follows a redirect, which could carry the token elsewhere."""

from __future__ import annotations

import json
import re
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import urlsplit

API_URL = "https://api.github.com"
API_VERSION = "2026-03-10"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30  # 30 pages of 100 covers GitHub's 3000-file limit for a PR
TIMEOUT_SECONDS = 30.0
_LOOPBACK = {"127.0.0.1", "localhost"}
_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubError(Exception):
    def __init__(self, status: int | None, message: str) -> None:
        prefix = f"GitHub returned {status}" if status else "GitHub request failed"
        super().__init__(f"{prefix}: {message}")
        self.status = status
```

`GitHubApi.__init__` accepts `https` for any host and `http` only for `127.0.0.1` or `localhost` (tests); anything else raises `ValueError("the GitHub API URL must use https (http only on 127.0.0.1)")`. It keeps the scheme and host as the origin and the URL path as a prefix. `__repr__` shows only the host. `_send(method, path, body)` opens one connection per request with `TIMEOUT_SECONDS`, sends `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: API_VERSION`, `User-Agent: devctl` and, with a body, `Content-Type: application/json`; reads at most `MAX_RESPONSE_BYTES + 1` bytes; and closes the connection. `OSError` and `HTTPException` become `GitHubError(None, <exception class name>)` raised `from None`. A body over the cap, a 2xx body that is not JSON, or any status outside 200–299 raises `GitHubError(status, message)`, where `message` is the JSON `message` field or the HTTP reason, cut to 300 characters, with the token replaced by `[token]`. `request` returns the parsed JSON as `object` (`None` for an empty body). `paginate` follows the `rel="next"` link up to `MAX_PAGES` times, requires each page to be a list (`json_list`), and raises `GitHubError(None, "pagination left the API host")` when the link's scheme or host differs from the origin. `json_object` returns its argument when it is a `dict`, and `json_list` when it is a `list`; otherwise each raises the `GitHubError` in Interfaces. Callers narrow every response with them before reading a field, so no signature needs `Any`.

- [ ] **Step 5: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_github_api.py -q`. Expected: 6 passed.

- [ ] **Step 6: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl/devctl/github tools/devctl/devctl/github .rapid-ship/kit.lock tests/conftest.py tests/devctl/github_fakes.py tests/devctl/github_fixtures.py tests/devctl/test_devctl_github_api.py
git commit -m "feat: add a redirect-free GitHub REST client to devctl" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: App keys and installation tokens

**Files:**
- Create: `devctl/github/app.py`
- Modify: `devctl/check/kit.py` (`RAPID_SHIP_SOURCE`, `rapid_ship_command`)
- Modify: `devctl/pyproject.toml` and `devctl/uv.lock` (as template and vendored copies: `rapid_ship/templates/common/tools/devctl/pyproject.toml`, `…/uv.lock`, `tools/devctl/pyproject.toml`, `tools/devctl/uv.lock`); root `pyproject.toml` and `uv.lock`
- Modify: `tests/devctl/github_fakes.py` (Apps, installations, `FakeKeychain`), `tests/devctl/github_fixtures.py` (`app_keys`, `keychain`; `github` now registers both Apps)
- Test: `tests/devctl/test_devctl_github_app.py`, and plan 3's `tests/devctl/test_devctl_kit_step.py` (the kit-step hint); plan 2's `tests/test_kit_contents.py` runs unchanged and must stay green with PyJWT in devctl's lock

**Interfaces:**
- Consumes: `GitHubApi`, `GitHubError`, `API_URL`, `json_object` (Task 1); `ProjectSettings`, `SettingsError` (index); `process.run_process`, `ProcessResult` (plan 3 Task 1); `KitLockError` and the lock reader behind `managed_paths` in `devctl/check/kit.py` (plan 3 Task 6).
- Produces (the index's `installation_token` with keyword-only additions for tests):

```python
AppRole = Literal["worker", "reviewer"]
KEYCHAIN_SERVICE: dict[AppRole, str] = {
    "worker": "rapid-ship/worker-app",
    "reviewer": "rapid-ship/reviewer-app",
}
APP_PERMISSIONS: dict[AppRole, dict[str, str]] = {
    "worker": {
        "contents": "write",
        "pull_requests": "write",
        "issues": "write",
        "metadata": "read",
    },
    "reviewer": {"pull_requests": "write", "contents": "read", "metadata": "read"},
}


class DevctlError(Exception): ...  # base for errors that make a command exit 2


class AppError(DevctlError): ...  # an App, its key or its installation is missing or unusable


class KeychainMissing(AppError): ...


class Keychain(Protocol):
    def read(self, service: str) -> bytes: ...


class MacKeychain:
    def __init__(self, run: Callable[[list[str]], ProcessResult] | None = None) -> None: ...
    def read(self, service: str) -> bytes: ...


def keychain_private_key(role: AppRole, keychain: Keychain | None = None) -> bytes: ...
def app_jwt(private_key: bytes, app_id: int, now: float | None = None) -> str: ...
def installation(
    role: AppRole,
    repository: str,
    app_id: int,
    *,
    keychain: Keychain | None = None,
    api_url: str = API_URL,
) -> dict[str, object]: ...
def installation_token(
    role: AppRole,
    repository: str,
    app_id: int,
    *,
    keychain: Keychain | None = None,
    api_url: str = API_URL,
) -> str: ...
def app_slug(
    role: AppRole, app_id: int, *, keychain: Keychain | None = None, api_url: str = API_URL
) -> str: ...


@dataclass(frozen=True)
class GitHubAccess:
    repository: str  # "owner/name"
    api_url: str = API_URL
    remote_url: str | None = None  # None means https://github.com/<repository>.git
    keychain: Keychain | None = None  # None means MacKeychain()

    @property
    def remote(self) -> str: ...
    def token(
        self, role: AppRole, app_id: int
    ) -> str: ...  # one mint per call; a command calls it once
    def api(self, token: str) -> GitHubApi: ...  # REST client for an already minted token
    def slug(self, role: AppRole, app_id: int) -> str: ...


def project_access(
    project: ProjectSettings,
) -> GitHubAccess: ...  # AppError when repository is unset
# run_guarded: DevctlError, GitHubError, SettingsError, OSError -> message on sys.stderr, 2
def run_guarded(action: Callable[[], int], *, root: Path | None = None) -> int: ...


# devctl/check/kit.py
RAPID_SHIP_SOURCE = "git+https://github.com/proxy-hatch/rapid-ship"


def rapid_ship_command(
    root: Path, command: str
) -> str: ...  # KitLockError when the lock is unreadable
```

- [ ] **Step 1: Add the dependency, regenerate devctl's lock and re-vendor.** `uv add` rewrites the template's `uv.lock`; `sync` copies it and `pyproject.toml` to `tools/devctl/`. `--no-sync` keeps uv from creating a virtual environment inside the template directory.

```sh
uv add --no-sync --project rapid_ship/templates/common/tools/devctl "PyJWT[crypto]>=2.10,<3"
uv add --dev "PyJWT[crypto]>=2.10,<3"
uv lock --check --project rapid_ship/templates/common/tools/devctl
uv run rapid-ship sync --in-place
uv run pytest tests/test_kit_contents.py -q
```

Expected: `uv lock --check` exits 0. Both `pyproject.toml` files list the pin, and the template's `uv.lock` and the root `uv.lock` resolve PyJWT and cryptography. `sync` updates the vendored `tools/devctl/pyproject.toml` and `uv.lock` to match the template. `tests/test_kit_contents.py` passes, including plan 2's `test_devctl_is_its_own_uv_workspace_and_its_versions_agree`.

- [ ] **Step 2: Extend the fakes.** In `github_fakes.py` add:
  - Constants `WORKER_ID = 101`, `REVIEWER_ID = 202`, `WORKER_INSTALLATION = 1001`, `REVIEWER_INSTALLATION = 2002`, and literal permission dicts `WORKER_PERMISSIONS` and `REVIEWER_PERMISSIONS` equal to the spec's table. Tests compare against these literals, not against the code under test.
  - `FakeGitHub.add_app(app_id, slug, public_key_pem)` and `FakeGitHub.install(app_id, repository, permissions, installation_id)`, stored in dicts. `__init__` registers three generic routes. `GET /app` returns `{"id", "slug"}` for the App whose JWT is valid. `GET /repos/{owner}/{repo}/installation` returns `{"id", "app_id", "permissions", "repository_selection": "selected"}`, or 404 when that App is not installed there. `POST /app/installations/{id}/access_tokens` issues `"ghs_" + secrets.token_urlsafe(64)` (longer than 40 characters, like the stateless format), appends it to `issued_tokens` and returns 201 with `token`, `expires_at` and the requested `permissions`. A missing or invalid JWT returns 401 `{"message": "A JSON web token could not be decoded"}`.
  - `FakeGitHub.jwt_app_id(call) -> int | None`: reads `iss` without verifying, then verifies the RS256 signature with that App's public key, requires `iat`, `exp` and `iss`, and accepts only `exp - iat <= 600`.
  - `FakeKeychain(items: dict[str, bytes])` whose `read` raises `KeychainMissing(f"Keychain item {service} not found")` for an absent service.

In `github_fixtures.py` add a session-scoped `app_keys` fixture, annotated `-> dict[str, tuple[bytes, bytes]]`, returning `{role: (private_pem, public_pem)}` from `rsa.generate_private_key(public_exponent=65537, key_size=2048)`, serialised as `TraditionalOpenSSL` PEM and `SubjectPublicKeyInfo` PEM; a `keychain` fixture (`-> FakeKeychain`) with both private keys under their services; and make `github` call `add_app` for both Apps (`rs-worker`, `rs-reviewer`) and `install` both on `o/r`.

- [ ] **Step 3: Write the failing tests.** Create `tests/devctl/test_devctl_github_app.py`:

```python
"""Offline: App JWTs and installation tokens against simulated GitHub and a fake Keychain."""

from pathlib import Path

import jwt
import pytest
from devctl.github.api import GitHubError
from devctl.github.app import (
    AppError,
    KeychainMissing,
    MacKeychain,
    app_jwt,
    app_slug,
    installation_token,
    run_guarded,
)
from devctl.process import ProcessResult
from github_fakes import (
    REVIEWER_ID,
    REVIEWER_PERMISSIONS,
    WORKER_ID,
    WORKER_INSTALLATION,
    WORKER_PERMISSIONS,
    FakeGitHub,
    FakeKeychain,
)

AppKeys = dict[str, tuple[bytes, bytes]]


def test_worker_token_is_restricted_to_one_repository_and_its_permissions(
    github: FakeGitHub, keychain: FakeKeychain
) -> None:
    token = installation_token("worker", "o/r", WORKER_ID, keychain=keychain, api_url=github.url)
    assert token == github.issued_tokens[-1]
    mint = github.calls[-1]
    assert mint.path == f"/app/installations/{WORKER_INSTALLATION}/access_tokens"
    assert mint.body == {"repositories": ["r"], "permissions": WORKER_PERMISSIONS}


def test_reviewer_token_requests_only_reviewer_permissions(
    github: FakeGitHub, keychain: FakeKeychain
) -> None:
    installation_token("reviewer", "o/r", REVIEWER_ID, keychain=keychain, api_url=github.url)
    assert github.calls[-1].body["permissions"] == REVIEWER_PERMISSIONS


def test_jwt_is_short_lived_and_names_the_app_as_a_string(app_keys: AppKeys) -> None:
    private, public = app_keys["worker"]
    token = app_jwt(private, 101, now=1_000_000.0)
    claims = jwt.decode(
        token, public, algorithms=["RS256"], options={"verify_exp": False, "verify_iat": False}
    )
    assert claims == {"iat": 999_940, "exp": 1_000_540, "iss": "101"}


def test_app_slug_comes_from_the_app_itself(github: FakeGitHub, keychain: FakeKeychain) -> None:
    assert app_slug("reviewer", REVIEWER_ID, keychain=keychain, api_url=github.url) == "rs-reviewer"


def test_not_installed_is_an_app_error(github: FakeGitHub, keychain: FakeKeychain) -> None:
    with pytest.raises(AppError, match="worker App is not installed on o/other"):
        installation_token("worker", "o/other", WORKER_ID, keychain=keychain, api_url=github.url)


def test_missing_keychain_item(github: FakeGitHub) -> None:
    with pytest.raises(KeychainMissing, match="rapid-ship/worker-app"):
        installation_token(
            "worker", "o/r", WORKER_ID, keychain=FakeKeychain({}), api_url=github.url
        )


def test_missing_key_message_names_the_tagged_rapid_ship_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".rapid-ship").mkdir()
    (tmp_path / ".rapid-ship" / "kit.lock").write_text('kit_version = "0.2.0"\nstack = "neutral"\n')

    def missing() -> int:
        raise KeychainMissing("Keychain item rapid-ship/worker-app not found")

    assert run_guarded(missing, root=tmp_path) == 2
    assert (
        "Keychain item rapid-ship/worker-app not found; run uvx --from "
        "git+https://github.com/proxy-hatch/rapid-ship@v0.2.0 rapid-ship app"
    ) in capsys.readouterr().err


def test_mint_failure_text_has_no_key_material(github: FakeGitHub, keychain: FakeKeychain) -> None:
    github.route(
        "POST",
        r"/app/installations/\d+/access_tokens",
        lambda call, _: (
            422,
            {"message": "The permissions requested are not granted to this installation."},
        ),
    )
    with pytest.raises(GitHubError) as caught:
        installation_token("worker", "o/r", WORKER_ID, keychain=keychain, api_url=github.url)
    assert "BEGIN" not in str(caught.value)


def test_mac_keychain_decodes_hex_output_and_maps_exit_44(app_keys: AppKeys) -> None:
    pem = app_keys["worker"][0]
    seen: list[list[str]] = []

    def found(argv: list[str]) -> ProcessResult:
        seen.append(argv)
        return ProcessResult(argv, 0, pem.hex() + "\n", "", 0.0)

    assert MacKeychain(run=found).read("rapid-ship/worker-app") == pem
    assert seen == [["security", "find-generic-password", "-s", "rapid-ship/worker-app", "-w"]]
    with pytest.raises(KeychainMissing):
        MacKeychain(run=lambda argv: ProcessResult(argv, 44, "", "not found", 0.0)).read("s")
    with pytest.raises(AppError) as caught:
        MacKeychain(run=lambda argv: ProcessResult(argv, 0, "not a key\n", "", 0.0)).read("s")
    assert "not a key" not in str(caught.value)
```

- [ ] **Step 4: Run it.** `uv run pytest tests/devctl/test_devctl_github_app.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.github.app'`.

- [ ] **Step 5: Implement `devctl/github/app.py`.** The non-obvious parts:

```python
def _decode_secret(output: str) -> bytes:
    text = output.rstrip("\n")
    # `security -w` prints the item as lowercase hex when any byte is not printable, as a
    # PEM's newlines are (keychain_find.c:429-437).
    data = bytes.fromhex(text) if re.fullmatch(r"(?:[0-9a-f]{2})+", text) else text.encode()
    if not data.startswith(b"-----BEGIN "):
        raise AppError("the Keychain item is not a PEM private key")
    return data


def app_jwt(private_key: bytes, app_id: int, now: float | None = None) -> str:
    issued = int(time.time() if now is None else now)
    # 60 s back for clock drift; 9 minutes ahead stays under GitHub's 10-minute limit.
    # PyJWT requires a string issuer.
    return jwt.encode(
        {"iat": issued - 60, "exp": issued + 540, "iss": str(app_id)},
        private_key,
        algorithm="RS256",
    )


def installation_token(
    role: AppRole,
    repository: str,
    app_id: int,
    *,
    keychain: Keychain | None = None,
    api_url: str = API_URL,
) -> str:
    # One Keychain read and one JWT per mint. An item written by `security` trusts it, so
    # the read shows no dialog, and any process the owner runs can read it (spec section 6).
    app = GitHubApi(app_jwt(keychain_private_key(role, keychain), app_id), base_url=api_url)
    found = _installation(app, role, repository)
    issued = app.request(
        "POST",
        f"/app/installations/{found['id']}/access_tokens",
        {"repositories": [repository.split("/", 1)[1]], "permissions": APP_PERMISSIONS[role]},
    )
    token = json_object(issued, "the token response").get("token")
    if not isinstance(token, str) or not token:
        raise AppError("GitHub returned no installation token")
    return token
```

`MacKeychain.read` runs `["security", "find-generic-password", "-s", service, "-w"]` through `process.run_process` from `Path(tempfile.gettempdir())` with a 120 s timeout and no `env`, so the child gets `safe_environment()`'s `PATH`, `HOME` and locale. The read shows no dialog (Global Constraints, Keys). A timeout counts as a failure. Exit 44 raises `KeychainMissing(f"Keychain item {service} not found")`; any other failure raises `AppError(f"could not read Keychain item {service}")`. `MacKeychain` does not know the project, so `run_guarded` adds the remedy below. No message includes `stdout`. `_installation(app, role, repository) -> dict[str, object]` GETs `/repos/{repository}/installation` with the App JWT and narrows it with `json_object`; a 404 raises `AppError(f"the {role} App is not installed on {repository}")` `from None`. `installation` builds the JWT client and calls `_installation`. `app_slug` GETs `/app`. `GitHubAccess.remote` returns `remote_url` or `f"https://github.com/{repository}.git"`; `GitHubAccess.api(token)` returns `GitHubApi(token, base_url=self.api_url)`. `project_access` requires `project.repository` and returns `GitHubAccess(project.repository)`. `rapid_ship_command(root, command)` reads `kit_version` through the same lock reader as `managed_paths` and returns `f"uvx --from {RAPID_SHIP_SOURCE}@v{kit_version} rapid-ship {command}"`. `run_guarded` writes the exception text to `sys.stderr` and returns 2. With `root`, a `KeychainMissing` message gains `; run <rapid_ship_command(root, "app")>`; when that raises `KitLockError`, the message stays as raised. Every command handler passes `root=repo.root`.

- [ ] **Step 6: Point the kit-step hint at the full command.** In the template's `devctl/check/kit.py`, make the missing-file and missing-link details end `restore it or run <rapid_ship_command(context.repo.root, "sync")>` (Global Constraints, rapid-ship commands in messages). In `tests/devctl/test_devctl_kit_step.py`, change `test_missing_managed_file_and_link_fail` to expect `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<kit_version> rapid-ship sync` with the fixture lock's version. Run `uv run pytest tests/devctl/test_devctl_kit_step.py -q` first and expect that test to fail, then make the change.

- [ ] **Step 7: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl tests/test_kit_contents.py -q`. Expected: all pass, 15 of them in the two new files.

- [ ] **Step 8: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock pyproject.toml uv.lock tests/devctl
git commit -m "feat: mint App installation tokens from Keychain keys" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: askpass and token-bearing git

**Files:**
- Create: `devctl/github/askpass.py`, tracked with mode `100755`
- Modify: `devctl/github/app.py` (`GitError`, `git_environment`, `token_options`, `require_exact_remote`, `run_git`)
- Modify: `rapid_ship/templates/kit.toml` (`executable`), `tests/test_kit_contents.py`
- Modify: `tests/devctl/github_fakes.py` (`git` helper, `Remote`), `tests/devctl/github_fixtures.py` (`isolated_home`, `remote`, `recorded_argv`)
- Test: `tests/devctl/test_devctl_askpass.py`

**Interfaces:**
- Consumes: `process.run_process` (plan 3 Task 1), `DevctlError` (Task 2), `KitManifest.executable` and `load_manifest` (plan 2 Task 2).
- Produces:

```python
# devctl/github/askpass.py: standard library only; git executes this file directly
ASKPASS_VARIABLE = "RAPID_SHIP_GIT_TOKEN"
ASKPASS_PATH: Path
GIT_TOKEN_OPTIONS: tuple[str, ...] = ("-c", "credential.helper=", "-c", "core.hooksPath=/dev/null")


def answer(prompt: str, environ: Mapping[str, str]) -> str | None: ...
def main(argv: Sequence[str]) -> int: ...


# devctl/github/app.py
class GitError(DevctlError): ...


def git_environment(token: str) -> dict[str, str]: ...
def token_options(
    url: str,
) -> tuple[str, ...]: ...  # GIT_TOKEN_OPTIONS plus "-c", f"http.{url}.extraHeader="
def require_exact_remote(cwd: Path, url: str) -> None: ...
def run_git(
    cwd: Path, args: Sequence[str], token: str, *, url: str, timeout_seconds: float = 120.0
) -> ProcessResult: ...
```

`url` is the remote the command talks to and must be one of `args`. `run_git` checks it with `require_exact_remote` itself, so no caller can forget the check.

- [ ] **Step 1: Add the fixtures.** In `github_fakes.py` add `git(cwd: Path, *args: str) -> str`, which calls the directly imported `run_process` with `env` holding a fixed author and committer (`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` set to `test` and `test@example.invalid`), asserts exit 0 and returns stripped stdout. Add a `Remote` dataclass with `bare: Path`, `clone: Path`, `git_common_dir: Path` (the clone's resolved `.git`, equal to `Repo.discover(clone).git_common_dir`) and methods `branch(name: str) -> str | None` (via `git ls-remote`), `branch_count(prefix: str) -> int`, `create_branch(name: str, sha: str | None = None) -> None`, `commit_on(branch: str, message: str) -> str` (in a temporary clone) and `clone_again(name: str) -> Path`. In `github_fixtures.py` add, annotated:
  - `isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path`: points `HOME` at `tmp_path / "home"`, so git never reads the owner's `~/.gitconfig`. It is not autouse: plan 3's and plan 5's integration tests run uv, which needs the real `HOME` for its cache. `remote` requests it, and so does every module below that runs git without `remote`.
  - `remote(tmp_path: Path, isolated_home: Path) -> Remote`: `git init --bare --initial-branch=main <tmp>/remote.git`, a clone at `<tmp>/work/r` with one commit on `main`, pushed.
  - `recorded_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]`: wraps `devctl.process.run_process` and returns the list of argv it saw.

- [ ] **Step 2: Write the failing tests.** Append to `tests/test_kit_contents.py`:

```python
def test_askpass_is_written_executable() -> None:
    # init and sync set the executable bit only for paths kit.toml lists (plan 2).
    assert "tools/devctl/devctl/github/askpass.py" in load_manifest().executable
```

Create `tests/devctl/test_devctl_askpass.py`:

```python
"""Offline: the askpass helper and token-bearing git against local repositories and a simulated
GitHub server. No network."""

import os
import secrets
from pathlib import Path

import pytest
from devctl import process
from devctl.github import askpass
from devctl.github.app import GitError, git_environment, require_exact_remote, run_git
from github_fakes import FakeGitHub, Remote, git

pytestmark = pytest.mark.usefixtures("isolated_home")

PROMPT = "Password for 'https://git.example.invalid': "
ELSEWHERE = "https://git.example.invalid/o/r.git"


def test_askpass_answers_git_prompts_from_its_environment(tmp_path: Path) -> None:
    token = secrets.token_urlsafe(48)
    path = git_environment(token)["PATH"]

    def run(prompt: str, env: dict[str, str]) -> process.ProcessResult:
        return process.run_process([str(askpass.ASKPASS_PATH), prompt], tmp_path, 10, env=env)

    password = run(PROMPT, {"PATH": path, askpass.ASKPASS_VARIABLE: token})
    user = run(
        "Username for 'https://git.example.invalid': ",
        {"PATH": path, askpass.ASKPASS_VARIABLE: token},
    )
    without = run(PROMPT, {"PATH": path})
    assert (password.returncode, password.stdout) == (0, token + "\n")
    assert (user.returncode, user.stdout) == (0, "x-access-token\n")
    assert (without.returncode, without.stdout) == (1, "")


def test_configured_credential_helpers_are_bypassed(tmp_path: Path) -> None:
    token = secrets.token_urlsafe(48)
    owner = tmp_path / "owner.gitconfig"
    owner.write_text(
        '[credential]\n\thelper = "!f() { echo username=owner; echo password=owner-login; }; f"\n'
    )
    # GIT_CONFIG_NOSYSTEM keeps Xcode's osxkeychain helper out of the control case.
    env = {**git_environment(token), "GIT_CONFIG_GLOBAL": str(owner), "GIT_CONFIG_NOSYSTEM": "1"}
    request = "protocol=https\nhost=git.example.invalid\n\n"
    reset = process.run_process(
        ["git", *askpass.GIT_TOKEN_OPTIONS, "credential", "fill"],
        tmp_path,
        30,
        env=env,
        input_text=request,
    )
    control = process.run_process(
        ["git", "credential", "fill"], tmp_path, 30, env=env, input_text=request
    )
    assert f"password={token}" in reset.stdout
    assert "password=owner-login" in control.stdout


def test_extra_headers_from_git_config_are_not_sent(remote: Remote, github: FakeGitHub) -> None:
    url = f"{github.url}/o/r.git"
    headers = {"X-Owner-Generic", "X-Owner-Scoped"}
    git(remote.clone, "config", "http.extraHeader", "X-Owner-Generic: owner")
    # actions/checkout writes a URL-scoped header like this one; -c http.extraHeader= keeps it.
    git(remote.clone, "config", f"http.{github.url}/.extraHeader", "X-Owner-Scoped: owner")
    process.run_process(["git", "ls-remote", url], remote.clone, 30)  # control: no reset
    control = {name for call in github.calls for name in call.headers}
    github.calls.clear()
    run_git(remote.clone, ["ls-remote", url], secrets.token_urlsafe(48), url=url)
    sent = {name for call in github.calls for name in call.headers}
    assert headers <= control
    assert github.calls
    assert not headers & sent


def test_repository_hooks_do_not_run_with_the_token(remote: Remote, tmp_path: Path) -> None:
    hooks, leak = tmp_path / "hooks", tmp_path / "leak"
    hooks.mkdir()
    for name in ("pre-push", "reference-transaction"):
        (hooks / name).write_text(f'#!/bin/sh\nprintenv RAPID_SHIP_GIT_TOKEN >> "{leak}"\n')
        (hooks / name).chmod(0o755)
    git(remote.clone, "config", "core.hooksPath", str(hooks))
    url = str(remote.bare)
    result = run_git(
        remote.clone, ["push", url, "HEAD:refs/heads/hooks-1"], secrets.token_urlsafe(48), url=url
    )
    assert result.returncode == 0
    assert not leak.exists()


def test_git_tracing_from_the_callers_environment_is_dropped(
    remote: Remote, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in {"GIT_TRACE": "1", "GIT_TRACE_CURL": "1", "GIT_TRACE_REDACT": "0"}.items():
        monkeypatch.setenv(name, value)
    url = str(remote.bare)
    result = run_git(remote.clone, ["ls-remote", url], secrets.token_urlsafe(48), url=url)
    assert result.returncode == 0
    assert "trace" not in result.stderr


@pytest.mark.parametrize("rule", ["insteadOf", "pushInsteadOf"])
def test_rewritten_remote_url_is_refused(remote: Remote, rule: str) -> None:
    url = str(remote.bare)
    git(
        remote.clone,
        "config",
        f"url.https://elsewhere.invalid/.{rule}",
        "https://unrelated.invalid/",
    )
    require_exact_remote(remote.clone, url)
    git(remote.clone, "config", f"url.{url}-elsewhere.{rule}", url)
    with pytest.raises(GitError, match="rewrites"):
        require_exact_remote(remote.clone, url)
    with pytest.raises(GitError, match="rewrites"):
        run_git(
            remote.clone,
            ["push", url, "HEAD:refs/heads/rewrite-1"],
            secrets.token_urlsafe(48),
            url=url,
        )
    assert remote.branch("rewrite-1") is None


def test_token_is_never_an_argument(remote: Remote, recorded_argv: list[list[str]]) -> None:
    token = secrets.token_urlsafe(48)
    url = str(remote.bare)
    run_git(remote.clone, ["ls-remote", url], token, url=url)
    assert recorded_argv
    assert all(token not in arg for argv in recorded_argv for arg in argv)


def test_askpass_must_be_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain = tmp_path / "askpass.py"
    plain.write_text("")
    monkeypatch.setattr(askpass, "ASKPASS_PATH", plain)
    with pytest.raises(GitError, match="not executable"):
        run_git(tmp_path, ["ls-remote", ELSEWHERE], "t", url=ELSEWHERE)
    assert os.access(Path(askpass.__file__), os.X_OK)
```

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_askpass.py tests/test_kit_contents.py -q`. Expected: collection of the askpass tests fails with `ImportError: cannot import name 'askpass' from 'devctl.github'`, and `test_askpass_is_written_executable` fails its assertion.

- [ ] **Step 4: Implement `askpass.py`.** It imports nothing from devctl: git runs it as a standalone script, where `devctl` is not importable.

```python
#!/usr/bin/env python3
"""GIT_ASKPASS helper. git runs this file to read the App token from RAPID_SHIP_GIT_TOKEN.

The token reaches git only through this process's environment and git's prompt pipe.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

ASKPASS_VARIABLE = "RAPID_SHIP_GIT_TOKEN"
ASKPASS_PATH = Path(__file__).resolve()
# An empty credential.helper clears every helper configured before it, including gh's
# URL-scoped one, so the App token is neither replaced by nor stored in the owner's
# credentials. hooksPath=/dev/null keeps repository hooks from running with the token
# in their environment.
GIT_TOKEN_OPTIONS = ("-c", "credential.helper=", "-c", "core.hooksPath=/dev/null")


def answer(prompt: str, environ: Mapping[str, str]) -> str | None:
    token = environ.get(ASKPASS_VARIABLE)
    if not token:
        return None
    if prompt.startswith("Username"):
        return "x-access-token"
    if prompt.startswith("Password"):
        return token
    return None


def main(argv: Sequence[str]) -> int:
    reply = answer(argv[1] if len(argv) > 1 else "", os.environ)
    if reply is None:
        return 1
    sys.stdout.write(reply + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

In `app.py`:

```python
_REWRITE_RULES = r"^url\..*\.(push)?insteadof$"  # git lowercases section and key names


def token_options(url: str) -> tuple[str, ...]:
    # -c http.extraHeader= clears only unscoped headers; a header scoped to this URL, as
    # actions/checkout writes, survives it. A reset scoped to the exact URL clears both
    # (Checked facts).
    return (*askpass.GIT_TOKEN_OPTIONS, "-c", f"http.{url}.extraHeader=")


def require_exact_remote(cwd: Path, url: str) -> None:
    # `git ls-remote --get-url` applies insteadOf but not pushInsteadOf, so read the rules.
    found = process.run_process(["git", "config", "-z", "--get-regexp", _REWRITE_RULES], cwd, 30)
    if found.returncode == 1:
        return
    if found.returncode != 0:
        raise GitError(f"could not read git config: {_first_line(found.stderr)}")
    for entry in filter(None, found.stdout.split("\0")):
        key, _, prefix = entry.partition("\n")
        if prefix and url.startswith(prefix):
            raise GitError(f"git config rewrites {url} through {key}; remove that rule")
```

`git_environment(token)` returns `PATH` (this interpreter's directory first, so the shebang's `python3` is devctl's own; then the caller's `PATH`), `GIT_ASKPASS=str(askpass.ASKPASS_PATH)`, `GIT_TERMINAL_PROMPT=0` and `RAPID_SHIP_GIT_TOKEN`. `run_process` gives git only `safe_environment(git_environment(token))`: the caller's `HOME`, `LANG` and `LC_ALL` set to `C.UTF-8`, then these four variables. So `GIT_TRACE*`, `GIT_CURL_VERBOSE` and `GIT_CONFIG_*` never reach git. `run_git` raises `GitError(f"{askpass.ASKPASS_PATH} is not executable; check kit.toml's executable list")` unless `os.access(askpass.ASKPASS_PATH, os.X_OK)`, raises `ValueError("run_git needs the remote URL among its arguments")` unless `url in args`, calls `require_exact_remote(cwd, url)`, then runs `["git", *token_options(url), *args]` with `env=git_environment(token)`. `_first_line(text)` returns the first line, cut to 300 characters.

- [ ] **Step 5: Mark it executable in the Kit and run it.** In `rapid_ship/templates/kit.toml`, set `executable = ["devctl", ".githooks/pre-commit", "tools/devctl/devctl/github/askpass.py"]`. Plan 2's `init` and `sync` set the executable bit only for paths listed there, so this line, made before the first sync of the file, is what makes the vendored copy and every project's copy executable.

```sh
git add --chmod=+x rapid_ship/templates/common/tools/devctl/devctl/github/askpass.py
uv run rapid-ship sync --in-place
git add tools/devctl/devctl/github/askpass.py
git ls-files -s tools/devctl/devctl/github/askpass.py
uv run pytest tests/devctl/test_devctl_askpass.py tests/test_kit_contents.py -q
```

Expected: `git ls-files -s` prints a line starting `100755`; then all pass, 9 of them in `test_devctl_askpass.py`. A line starting `100644` means sync ignored the list: compare the `kit.toml` entry with the rendered path character by character.

- [ ] **Step 6: Commit.**

```sh
git add rapid_ship/templates/kit.toml rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/test_kit_contents.py tests/devctl
git commit -m "feat: pass App tokens to git through an askpass helper" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: `devctl dispatch` admission

**Files:**
- Create: `devctl/dispatch.py`
- Modify: `devctl/github/app.py` (remote helpers), `devctl/cli.py` (register `dispatch`)
- Modify: `tests/devctl/github_fakes.py` (`RepoAt`), `tests/devctl/github_fixtures.py` (`project`, `access`, `repo_at`)
- Test: `tests/devctl/test_devctl_dispatch.py`

**Interfaces:**
- Consumes: `Repo`, `Repo.discover` (plan 2 Task 11); `ProjectSettings`, `Agent`, `load_project` (index); `check_workspace.project_settings` (plan 3 Task 2); `GitHubAccess`, `project_access`, `run_git` (which checks the remote URL), `run_guarded`, `GitError` (Tasks 2–3).
- Produces:

```python
# devctl/github/app.py
@dataclass(frozen=True)
class PushOutcome:
    pushed: bool
    rejection: (
        str | None
    )  # summary and reason from `git push --porcelain`, for example "[rejected] (stale info)"


def ls_remote_heads(
    cwd: Path, url: str, token: str, pattern: str
) -> dict[str, str]: ...  # ref -> sha
def remote_default_branch(cwd: Path, url: str, token: str) -> str: ...
def fetch_ref(cwd: Path, url: str, token: str, ref: str) -> str: ...  # fetched sha
def push_ref(
    cwd: Path, url: str, token: str, refspec: str, *, create_only: str | None = None
) -> PushOutcome: ...


# devctl/dispatch.py
ISSUE_PATTERN = re.compile(r"[A-Z][A-Z0-9]{0,9}-[1-9][0-9]{0,8}")
WALK_WORKER_CAP = 5


@dataclass(frozen=True)
class GateLogEntry:
    time: str
    command: str
    issue: str
    answer: Literal["allow", "refuse"]
    reason: str
    branch: str | None
    attempt: int


class GateLogError(DevctlError): ...


def utc_now() -> datetime: ...  # datetime.now(UTC)
def gate_log_path(git_common_dir: Path) -> Path: ...  # <git common dir>/rapid-ship/gate-log.jsonl
def read_gate_log(path: Path) -> list[GateLogEntry]: ...
def append_gate_log(path: Path, entry: GateLogEntry) -> None: ...
def admissions(
    entries: Sequence[GateLogEntry], issue: str
) -> int: ...  # earlier "dispatch" allows for the issue
def default_head(
    cwd: Path, url: str, token: str
) -> str: ...  # fetched head of the remote default branch
def admission_refusal(
    project: ProjectSettings, claims: Mapping[str, str], branch: str, attempt: int, *, retry: bool
) -> str | None: ...
def dispatch(
    repo: Repo,
    project: ProjectSettings,
    access: GitHubAccess,
    issue: str,
    *,
    retry: bool,
    now: Callable[[], datetime] = utc_now,
) -> int: ...
def dispatch_command(args: argparse.Namespace) -> int: ...
def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...
```

- [ ] **Step 1: Add the fixtures.** In `github_fakes.py` add `RepoAt = Callable[[Path], Repo]`. In `github_fixtures.py` add:

```python
@pytest.fixture
def project() -> ProjectSettings:
    # project_settings is plan 3's helper; it fills the remaining fields with test defaults.
    return project_settings(
        worker=Agent("agy", "gemini-3.8-flash-high"),
        reviewer=Agent("claude", "claude-opus-5-5"),
        repository="o/r",
        worker_app_id=WORKER_ID,
        reviewer_app_id=REVIEWER_ID,
        linear_team_id="team",
        linear_project_id="project",
        worktree_root="../<repo>.worktrees",
        map_exclude=(),
    )


@pytest.fixture
def access(github: FakeGitHub, remote: Remote, keychain: FakeKeychain) -> GitHubAccess:
    return GitHubAccess("o/r", api_url=github.url, remote_url=str(remote.bare), keychain=keychain)


@pytest.fixture
def repo_at() -> RepoAt:
    return Repo.discover
```

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_dispatch.py`:

```python
"""Offline: dispatch against a local bare repository standing in for GitHub, with simulated App tokens."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from devctl.dispatch import (
    GateLogEntry,
    GateLogError,
    append_gate_log,
    dispatch,
    gate_log_path,
    read_gate_log,
)
from devctl.github.app import GitHubAccess
from devctl.settings import ProjectSettings
from github_fakes import FakeGitHub, Remote, RepoAt, git


def log(remote: Remote) -> list[GateLogEntry]:
    return read_gate_log(gate_log_path(remote.git_common_dir))


def test_admits_one_worker(
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    repo_at: RepoAt,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert dispatch(repo_at(remote.clone), project, access, "ENG-1", retry=False) == 0
    assert remote.branch("rs/ENG-1") == remote.branch("main")
    worktree = remote.clone.parent / "r.worktrees" / "ENG-1"
    assert git(worktree, "symbolic-ref", "--short", "HEAD") == "rs/ENG-1"
    [entry] = log(remote)
    assert (entry.command, entry.issue, entry.answer, entry.branch, entry.attempt) == (
        "dispatch",
        "ENG-1",
        "allow",
        "rs/ENG-1",
        1,
    )
    out = capsys.readouterr().out
    assert f"worktree: {worktree}" in out
    assert "worker: agy gemini-3.8-flash-high" in out


def test_invalid_issue_is_refused_and_logged(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    assert dispatch(repo_at(remote.clone), project, access, "eng-1", retry=False) == 1
    assert remote.branch_count("rs/") == 0
    [entry] = log(remote)
    assert (entry.answer, entry.branch, entry.attempt) == ("refuse", None, 0)


def test_missing_worker_settings_are_refused_and_logged(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    assert (
        dispatch(repo_at(remote.clone), replace(project, worker=None), access, "ENG-1", retry=False)
        == 1
    )
    assert remote.branch_count("rs/") == 0
    [entry] = log(remote)
    assert (entry.issue, entry.answer, entry.branch, entry.attempt) == ("ENG-1", "refuse", None, 0)
    assert "rs-setup" in entry.reason


def test_existing_claim_needs_retry_which_reuses_it(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    repo = repo_at(remote.clone)
    assert dispatch(repo, project, access, "ENG-2", retry=False) == 0
    claimed = remote.branch("rs/ENG-2")
    remote.commit_on("main", "main moves on")
    git(remote.clone, "worktree", "remove", str(remote.clone.parent / "r.worktrees" / "ENG-2"))
    assert dispatch(repo, project, access, "ENG-2", retry=False) == 1
    assert dispatch(repo, project, access, "ENG-2", retry=True) == 0
    assert remote.branch("rs/ENG-2") == claimed
    assert [(e.answer, e.attempt) for e in log(remote)] == [
        ("allow", 1),
        ("refuse", 2),
        ("allow", 2),
    ]


def test_cap_is_the_lower_of_five_and_max_workers(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    for n in range(1, 6):
        remote.create_branch(f"rs/ENG-{n}")
    repo = repo_at(remote.clone)
    assert dispatch(repo, replace(project, max_workers=8), access, "ENG-9", retry=False) == 1
    assert log(remote)[-1].reason == "cap 5 reached: 5 active claims"
    assert (
        dispatch(repo, project, access, "ENG-1", retry=True) == 0
    )  # a reused claim adds no Worker
    assert dispatch(repo, replace(project, max_workers=2), access, "ENG-9", retry=False) == 1
    assert log(remote)[-1].reason == "cap 2 reached: 5 active claims"


def test_attempt_limit_counts_earlier_admissions(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    path = gate_log_path(remote.git_common_dir)
    for attempt in (1, 2, 3):
        append_gate_log(
            path,
            GateLogEntry(
                "2026-10-14T00:00:00+00:00",
                "dispatch",
                "ENG-3",
                "allow",
                "claimed",
                "rs/ENG-3",
                attempt,
            ),
        )
    assert dispatch(repo_at(remote.clone), project, access, "ENG-3", retry=True) == 1
    assert log(remote)[-1].reason == "attempt limit 3 reached"


def test_malformed_log_stops_dispatch_before_any_claim(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    path = gate_log_path(remote.git_common_dir)
    path.parent.mkdir(parents=True)
    path.write_text("{not json\n")
    with pytest.raises(GateLogError, match="line 1"):
        dispatch(repo_at(remote.clone), project, access, "ENG-4", retry=False)
    assert remote.branch_count("rs/") == 0


def test_two_clones_claim_one_issue_once(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    clones = [remote.clone, remote.clone_again("r2")]
    barrier = threading.Barrier(2)

    def run(clone: Path) -> int:
        repo = repo_at(clone)
        barrier.wait()
        return dispatch(repo, project, access, "ENG-7", retry=False)

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, clones)) == [0, 1]
    assert remote.branch_count("rs/") == 1


def test_lock_keeps_the_cap_under_concurrent_dispatch(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    for n in range(1, 5):
        remote.create_branch(f"rs/ENG-{n}")
    repo = repo_at(remote.clone)
    barrier = threading.Barrier(2)

    def run(issue: str) -> int:
        barrier.wait()
        return dispatch(repo, project, access, issue, retry=False)

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, ["ENG-8", "ENG-9"])) == [0, 1]
    assert remote.branch_count("rs/") == 5
    assert [e.reason for e in log(remote) if e.answer == "refuse"] == [
        "cap 5 reached: 5 active claims"
    ]


def test_claims_are_made_as_the_worker_app(
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    repo_at: RepoAt,
    github: FakeGitHub,
) -> None:
    dispatch(repo_at(remote.clone), project, access, "ENG-5", retry=False)
    mints = [c for c in github.calls if c.path.endswith("/access_tokens")]
    assert [m.body["permissions"]["contents"] for m in mints] == ["write"]
    assert all(
        "pull_requests" in m.body["permissions"] and "issues" in m.body["permissions"]
        for m in mints
    )
```

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_dispatch.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.dispatch'`.

- [ ] **Step 4: Implement the remote helpers.** In `app.py`, each runs through `run_git(..., url=url)` with the token:
  - `ls_remote_heads`: `git ls-remote <url> <pattern>`; parse `sha\tref` lines.
  - `remote_default_branch`: `git ls-remote --symref <url> HEAD`; return the branch from the `ref: refs/heads/<name>\tHEAD` line.
  - `fetch_ref`: `git fetch --no-tags --quiet <url> <ref>`, then return `git rev-parse FETCH_HEAD` (through `process.run_process`; it needs no token).
  - `push_ref`: `git push --porcelain [--force-with-lease=<create_only>:] <url> <refspec>`. A line `!\t<from>:<to>\t<summary>` gives `PushOutcome(False, summary)`. Exit 0 with no `!` line gives `PushOutcome(True, None)`. Any other failure raises `GitError` with the first stderr line, the token replaced by `[token]`.

- [ ] **Step 5: Implement `devctl/dispatch.py`.** The admission order follows spec section 6 steps 1–6; a reused claim adds no Worker, so it is not held to the cap. The work is split so each function stays under complexity 10.

```python
WALK_WORKER_CAP = 5  # ADR 0003: no more than five supervised Workers until Flight can run them


@contextmanager
def dispatch_lock(git_common_dir: Path) -> Iterator[None]:
    """Serialise dispatch across this clone's worktrees. The remote claim covers other clones."""
    directory = git_common_dir / "rapid-ship"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "dispatch.lock").open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def admission_refusal(
    project: ProjectSettings, claims: Mapping[str, str], branch: str, attempt: int, *, retry: bool
) -> str | None:
    ref = f"refs/heads/{branch}"
    cap = min(WALK_WORKER_CAP, project.max_workers)
    if ref not in claims and len(claims) >= cap:
        return f"cap {cap} reached: {len(claims)} active claims"
    if attempt > project.attempt_limit:
        return f"attempt limit {project.attempt_limit} reached"
    if ref in claims and not retry:
        return f"{branch} is already claimed; rerun with --retry to reuse it"
    return None


def default_head(cwd: Path, url: str, token: str) -> str:
    """Fetch the remote default branch and return its head; doctor --skills starts from it too."""
    default = remote_default_branch(cwd, url, token)
    return fetch_ref(cwd, url, token, f"refs/heads/{default}")


def _claim(cwd: Path, url: str, token: str, branch: str, *, reuse: bool) -> tuple[str | None, str]:
    """Return the start commit and the reason; no start commit means another dispatch won."""
    ref = f"refs/heads/{branch}"
    if reuse:
        return fetch_ref(cwd, url, token, ref), "reused the existing claim"
    start = default_head(cwd, url, token)
    outcome = push_ref(cwd, url, token, f"{start}:{ref}", create_only=ref)
    if outcome.pushed:
        return start, "claimed"
    if ref in ls_remote_heads(cwd, url, token, ref):
        return None, f"{branch} was claimed by another dispatch"
    raise GitError(f"could not create {branch}: {outcome.rejection}")


def dispatch(
    repo: Repo,
    project: ProjectSettings,
    access: GitHubAccess,
    issue: str,
    *,
    retry: bool,
    now: Callable[[], datetime] = utc_now,
) -> int:
    log = gate_log_path(repo.git_common_dir)

    def record(
        answer: Literal["allow", "refuse"], reason: str, branch: str | None, attempt: int
    ) -> int:
        append_gate_log(
            log,
            GateLogEntry(
                now().isoformat(timespec="seconds"),
                "dispatch",
                issue,
                answer,
                reason,
                branch,
                attempt,
            ),
        )
        sys.stdout.write(f"{'admitted' if answer == 'allow' else 'refused'} {issue}: {reason}\n")
        return 0 if answer == "allow" else 1

    with dispatch_lock(repo.git_common_dir):
        worker, app_id = project.worker, project.worker_app_id
        if worker is None or app_id is None:
            return record(
                "refuse",
                ".rapid-ship/project.toml names no Worker Agent or worker_app_id; run rs-setup",
                None,
                0,
            )
        if not ISSUE_PATTERN.fullmatch(issue):
            return record("refuse", "issue IDs look like ENG-123", None, 0)
        branch = f"rs/{issue}"
        attempt = admissions(read_gate_log(log), issue) + 1
        token = access.token("worker", app_id)
        claims = ls_remote_heads(repo.root, access.remote, token, "refs/heads/rs/*")
        refusal = admission_refusal(project, claims, branch, attempt, retry=retry)
        if refusal is not None:
            return record("refuse", refusal, branch, attempt)
        start, reason = _claim(
            repo.root, access.remote, token, branch, reuse=f"refs/heads/{branch}" in claims
        )
        if start is None:
            return record("refuse", reason, branch, attempt)
        record("allow", reason, branch, attempt)
        worktree = add_worktree(repo, project.worktree_root, branch, issue, start)
    sys.stdout.write(
        f"branch: {branch}\nworktree: {worktree}\nworker: {worker.harness} {worker.model}\n"
    )
    return 0
```

Describe the rest precisely:
- `gate_log_path` returns `git_common_dir / "rapid-ship" / "gate-log.jsonl"`, beside `dispatch.lock`.
- `read_gate_log` returns `[]` for a missing file. A line that is not a JSON object with exactly the seven fields and their types raises `GateLogError(f"{path} line {n} is not a gate log entry")`; attempt counts are never guessed. It runs before the token is minted, so a malformed log stops dispatch before any claim.
- `admissions` counts entries with `command == "dispatch"`, this `issue` and `answer == "allow"`.
- `append_gate_log` creates the directory with mode `0o700`, appends one `json.dumps(asdict(entry), sort_keys=True)` line, flushes and fsyncs.
- `worktree_root(repo, setting)` takes the main work tree from the first `worktree` line of `git worktree list --porcelain`, replaces a literal `<repo>` in the setting with that directory's name, and resolves the setting relative to it.
- `add_worktree` returns the existing worktree when one is already on `refs/heads/<branch>`. Otherwise it runs `git worktree add <root>/<issue> <branch>` when the local branch exists, which keeps a previous attempt's local commits, or `git worktree add -b <branch> <root>/<issue> <start>`. A failure raises `GitError(f"claimed {branch}, but the worktree failed: {first stderr line}; rerun with --retry")`.
- `register` adds `dispatch` with an optional `issue` (`nargs="?"`), `--retry`, `--status` and `--clean`, and `set_defaults(handler=dispatch_command)`. `dispatch_command` requires exactly one of `issue`, `--status`, `--clean`, and allows `--retry` only with `issue`; otherwise it writes the usage to stderr and returns 2. It builds `repo = Repo.discover(Path.cwd())` and `project = load_project(repo.root)` (plan 2's `cli.main` maps `RepoError` and `SettingsError` to exit 2), then returns `run_guarded(lambda: dispatch(repo, project, project_access(project), args.issue, retry=args.retry), root=repo.root)`. Task 5 adds the other two branches.
- Modify `devctl/cli.py` to call `dispatch.register(commands)` beside `devctl_project.register`.

- [ ] **Step 6: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_dispatch.py -q`. Expected: 10 passed. Then `./devctl dispatch --help` lists `--retry`, `--status` and `--clean`, and `./devctl dispatch` with no argument exits 2 with the usage, not with "does not set a handler".

- [ ] **Step 7: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: admit Workers with devctl dispatch" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: `devctl dispatch --status` and `--clean`

**Files:**
- Modify: `devctl/dispatch.py`
- Modify: `tests/devctl/github_fakes.py` (`FakeGitHub.pull_requests: dict[str, list[dict[str, Any]]]` served on `GET /repos/{o}/{r}/pulls` by the `head` query value)
- Test: `tests/devctl/test_devctl_dispatch_clean.py`

**Interfaces:**
- Consumes: Task 4's helpers, `admissions` and gate log; `GitHubAccess.api` (Task 2); `json_list`, `json_object` (Task 1).
- Produces:

```python
def dispatch_status(repo: Repo, project: ProjectSettings, access: GitHubAccess) -> int: ...
def dispatch_clean(
    repo: Repo,
    project: ProjectSettings,
    access: GitHubAccess,
    *,
    now: Callable[[], datetime] = utc_now,
) -> int: ...
```

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_dispatch_clean.py`. A module fixture `claims(remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt, github: FakeGitHub) -> None` dispatches `ENG-1` to `ENG-4` with Task 4's `dispatch`. It then sets the fake's PRs: `ENG-1` open (#1), `ENG-2` merged (#2, `merged_at` set), `ENG-3` closed unmerged (#3), `ENG-4` none. It deletes `rs/ENG-2` from the bare repository, as GitHub's branch deletion after merge would.

```python
"""Offline: dispatch --status and --clean against a local bare repository and simulated pull requests."""

import pytest
from devctl.dispatch import dispatch_clean, dispatch_status, gate_log_path, read_gate_log
from devctl.github.app import GitHubAccess
from devctl.settings import ProjectSettings
from github_fakes import Remote, RepoAt, git

pytestmark = pytest.mark.usefixtures("claims")


def test_status_lists_claims_and_local_worktrees(
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    repo_at: RepoAt,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert dispatch_status(repo_at(remote.clone), project, access) == 0
    out = capsys.readouterr().out
    assert "ENG-1  rs/ENG-1  PR #1 open" in out
    assert "ENG-2  rs/ENG-2  PR #2 merged" in out  # remote branch gone, worktree still here
    assert "ENG-4  rs/ENG-4  no PR" in out


def test_clean_removes_finished_work_only(
    remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    worktrees = remote.clone.parent / "r.worktrees"
    assert dispatch_clean(repo_at(remote.clone), project, access) == 0
    assert [n for n in (1, 2, 3, 4) if (worktrees / f"ENG-{n}").exists()] == [1, 4]
    assert remote.branch("rs/ENG-3") is None  # closed unmerged: remote branch deleted
    assert remote.branch("rs/ENG-1") is not None
    assert git(remote.clone, "branch", "--list", "rs/ENG-2", "rs/ENG-3") == ""
    cleaned = [
        e
        for e in read_gate_log(gate_log_path(remote.git_common_dir))
        if e.command == "dispatch --clean"
    ]
    assert sorted(e.issue for e in cleaned) == ["ENG-2", "ENG-3", "ENG-3"]


def test_clean_keeps_a_worktree_with_changes(
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    repo_at: RepoAt,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (remote.clone.parent / "r.worktrees" / "ENG-2" / "scratch.txt").write_text("unsaved")
    assert dispatch_clean(repo_at(remote.clone), project, access) == 1
    assert (remote.clone.parent / "r.worktrees" / "ENG-2").exists()
    assert "kept" in capsys.readouterr().out
```

- [ ] **Step 2: Run it.** `uv run pytest tests/devctl/test_devctl_dispatch_clean.py -q`. Expected: collection fails with `ImportError: cannot import name 'dispatch_clean'`.

- [ ] **Step 3: Implement.** Each command mints one Worker token and uses it for git and for `access.api(token)`. Both take the union of remote claims (`ls_remote_heads(…, "refs/heads/rs/*")`) and local worktrees on `rs/` branches. A merged PR's remote branch is usually already gone, so remote claims alone would miss its worktree. Each is looked up with `GET /repos/{repository}/pulls?head=<owner>:<branch>&state=all&per_page=1`, built with `urlencode`, newest first, and narrowed with `json_list` and `json_object`. Every `run_git` call checks the remote URL (Task 3).
  - `dispatch_status` prints one line per branch, sorted by issue, with fields separated by two spaces: issue, branch, `PR #<n> open|merged|closed` or `no PR`, the worktree path or `-`, and `attempts <n>` from `admissions`. It returns 0.
  - `dispatch_clean` holds `dispatch_lock`. It skips branches with an open PR or no PR. For a merged or closed PR it runs `git worktree remove <path>` without `--force`. When that fails, it prints `kept <path>: it has changes` and moves on. When it succeeds, it runs `git branch -D <branch>` and logs `GateLogEntry(…, "dispatch --clean", issue, "allow", f"PR #{n} {state}: removed worktree {path}", branch, admissions(…))`. For a closed, unmerged PR whose remote branch still exists, it runs `push_ref(…, f":refs/heads/{branch}")` and logs `"PR #<n> closed: deleted the remote branch"`. It returns 1 when it kept any worktree, else 0.
  - `dispatch_command` gains the `--status` and `--clean` branches, each wrapped in `run_guarded(…, root=repo.root)`. Keep each function under complexity 10; a per-branch helper does the remove-and-log step.

- [ ] **Step 4: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_dispatch.py tests/devctl/test_devctl_dispatch_clean.py -q`. Expected: 13 passed.

- [ ] **Step 5: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: list and clean Worker claims with devctl dispatch" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: `devctl pr`

**Files:**
- Create: `devctl/pr.py`
- Modify: `devctl/cli.py` (register `pr`), `tests/devctl/github_fakes.py`. `POST /repos/{o}/{r}/pulls` appends `{"number": n, "state": "open", "merged_at": None, "html_url": "https://github.com/o/r/pull/<n>"}` to `pull_requests` under its head and returns it. `PATCH /repos/{o}/{r}/pulls/{n}` returns the PR. Task 5's `GET` route filters by the `state` query.
- Test: `tests/devctl/test_devctl_pr.py`

**Interfaces:**
- Consumes: `ISSUE_PATTERN` (Task 4); remote helpers, `PushOutcome`, `GitHubAccess`, `run_guarded` (Tasks 2–4); `json_list`, `json_object` (Task 1).
- Produces:

```python
BRANCH_PATTERN = re.compile(rf"rs/({ISSUE_PATTERN.pattern})")


def open_pr(
    repo: Repo,
    project: ProjectSettings,
    access: GitHubAccess,
    *,
    title: str | None,
    body_path: Path | None,
) -> int: ...
def pr_command(args: argparse.Namespace) -> int: ...
def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...
```

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_pr.py`. A module fixture `worker(remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt) -> Repo` dispatches `ENG-1`, commits one file in its worktree and returns the worktree's `Repo`.

```python
"""Offline: devctl pr against a local bare repository and simulated GitHub, as the Worker App.
The workflow rejection is simulated by replacing push_ref."""

from pathlib import Path

import pytest
from devctl import pr
from devctl.github.app import GitHubAccess, PushOutcome, run_guarded
from devctl.pr import open_pr
from devctl.repo import Repo
from devctl.settings import ProjectSettings
from github_fakes import FakeGitHub, Remote, RepoAt, files_containing, git


def test_first_run_pushes_and_opens_the_pr(
    worker: Repo,
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    github: FakeGitHub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Evidence\n`./devctl check` passed\nNot covered: none\n")
    assert open_pr(worker, project, access, title="Add a link", body_path=body) == 0
    assert remote.branch("rs/ENG-1") == git(worker.root, "rev-parse", "HEAD")
    [create] = [c for c in github.calls if c.method == "POST" and c.path == "/repos/o/r/pulls"]
    assert create.body == {
        "title": "Add a link",
        "head": "rs/ENG-1",
        "base": "main",
        "body": body.read_text(),
    }
    assert "https://github.com/o/r/pull/1" in capsys.readouterr().out


def test_later_run_updates_only_the_body(
    worker: Repo, access: GitHubAccess, project: ProjectSettings, github: FakeGitHub, tmp_path: Path
) -> None:
    body = tmp_path / "body.md"
    body.write_text("first")
    open_pr(worker, project, access, title="Add a link", body_path=body)
    body.write_text("second")
    assert open_pr(worker, project, access, title=None, body_path=body) == 0
    [update] = [c for c in github.calls if c.method == "PATCH"]
    assert (update.path, update.body) == ("/repos/o/r/pulls/1", {"body": "second"})


def test_refusals_happen_before_any_push(
    worker: Repo, remote: Remote, access: GitHubAccess, project: ProjectSettings, repo_at: RepoAt
) -> None:
    assert (
        open_pr(repo_at(remote.clone), project, access, title="t", body_path=None) == 1
    )  # on main
    (worker.root / "dirty.txt").write_text("x")
    git(worker.root, "add", "dirty.txt")
    assert open_pr(worker, project, access, title="t", body_path=None) == 1  # uncommitted
    git(worker.root, "commit", "-m", "dirty")
    assert open_pr(worker, project, access, title=None, body_path=None) == 1  # no PR yet, no title
    assert remote.branch("rs/ENG-1") == remote.branch("main")


def test_non_fast_forward_is_refused_with_the_merge_hint(
    worker: Repo,
    remote: Remote,
    access: GitHubAccess,
    project: ProjectSettings,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remote.commit_on("rs/ENG-1", "someone else's commit")
    body = tmp_path / "b.md"
    body.write_text("b")
    assert open_pr(worker, project, access, title="t", body_path=body) == 1
    out = capsys.readouterr().out
    assert "merge origin/main" in out
    assert "do not rebase" in out


def test_workflow_change_rejection_sends_the_lead_to_the_owner(
    worker: Repo,
    access: GitHubAccess,
    project: ProjectSettings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reason = (
        "[remote rejected] (refusing to allow a GitHub App to create or update workflow "
        "`.github/workflows/devctl-check.yml` without `workflows` permission)"
    )
    monkeypatch.setattr(pr, "push_ref", lambda *args, **kwargs: PushOutcome(False, reason))
    body = tmp_path / "b.md"
    body.write_text("b")
    assert open_pr(worker, project, access, title="t", body_path=body) == 1
    out = capsys.readouterr().out
    assert "Workflows permission" in out
    assert "owner" in out
    assert "do not rebase" not in out


def test_token_stays_in_memory(
    worker: Repo,
    access: GitHubAccess,
    project: ProjectSettings,
    github: FakeGitHub,
    recorded_argv: list[list[str]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github.route("POST", "/repos/o/r/pulls", lambda call, _: (500, {"message": "boom"}))
    body = tmp_path / "b.md"
    body.write_text("b")
    assert run_guarded(lambda: open_pr(worker, project, access, title="t", body_path=body)) == 2
    out, err = capsys.readouterr()
    assert "boom" in err
    for token in github.issued_tokens:
        assert all(token not in arg for argv in recorded_argv for arg in argv)
        assert token not in out + err
        assert files_containing(tmp_path, token) == []
```

Add `files_containing(root: Path, needle: str) -> list[Path]` to `github_fakes.py`: every regular, non-symlink file under `root` whose bytes contain `needle`. `root` is the test's `tmp_path`, which holds the isolated `HOME`, the bare repository, the clones, every `.git` directory and the worktrees.

- [ ] **Step 2: Run it.** `uv run pytest tests/devctl/test_devctl_pr.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.pr'`.

- [ ] **Step 3: Implement `devctl/pr.py`.** The order puts every refusal before the push:
  1. The current branch (`git symbolic-ref --quiet --short HEAD`) must match `BRANCH_PATTERN`, else `refused: devctl pr runs on an rs/ branch`.
  2. `git status --porcelain --untracked-files=no` must be empty, else `refused: commit or discard tracked changes first`.
  3. Mint the Worker token, find the default branch, fetch it, and require `git rev-list --count FETCH_HEAD..HEAD` > 0, else `refused: no commits ahead of <default>`. Each `run_git` call refuses a rewritten remote URL (Task 3).
  4. Look up the open PR with `access.api(token)`, reusing the one Worker token: `GET /repos/{repository}/pulls?head=<owner>:<branch>&state=open`. With none, require both `--title` and `--body`, else `refused: --title and --body are needed to open the PR`. Read the body file as UTF-8 here, so an unreadable file fails before the push.
  5. `push_ref(…, f"HEAD:refs/heads/{branch}")` with no lease and no force. `pr.py` imports `push_ref` by name, so the workflow test can replace it. A rejection prints `refused: GitHub rejected the push: <summary>` and returns 1, with one hint:
     - When the summary contains `workflow`: `the push changes .github/workflows/, and the Worker App has no Workflows permission. Ask the owner to push <branch> under their own login, or to delete <branch> so the issue can be dispatched again from <default>.` This happens when the Worker merges a base branch that changed a workflow (Checked facts).
     - Otherwise, when it contains `non-fast-forward` or `fetch first`: `merge origin/<default> into the branch; do not rebase`.
  6. With no open PR, `POST /repos/{repository}/pulls` with `title`, `head` (the branch), `base` (the default branch) and `body`. With an open PR and `--body`, `PATCH /repos/{repository}/pulls/{n}` with `{"body": …}` only; spec section 6 updates only the body. Print the PR's `html_url` (read with `json_object`) and return 0.
  Split the steps into helpers so `open_pr` stays under complexity 10. `register` adds `pr` with `--title` and `--body` (a path) and `set_defaults(handler=pr_command)`. `pr_command` builds `Repo.discover(Path.cwd())` and `load_project(repo.root)` and returns `run_guarded(lambda: open_pr(…), root=repo.root)`. `cli.py` calls `pr.register(commands)`.

- [ ] **Step 4: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_pr.py -q`. Expected: 6 passed.

- [ ] **Step 5: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: push and open Worker PRs with devctl pr" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: `devctl review`

**Files:**
- Create: `devctl/review.py`
- Modify: `devctl/cli.py` (register `review`), `tests/devctl/github_fakes.py` (`FakePullRequest`, routes for one PR's object, files and reviews)
- Test: `tests/devctl/test_devctl_review.py`

**Interfaces:**
- Consumes: `Agent`, `ProjectSettings` (index); `GitHubAccess`, `run_guarded` (Task 2); `json_list`, `json_object` (Task 1).
- Produces:

```python
@dataclass(frozen=True)
class Finding:
    severity: Literal["blocking", "non_blocking"]
    path: str | None
    line: int | None
    message: str
    rung: int  # 1-4, the rung that would prevent a repeat
    prevention: str


@dataclass(frozen=True)
class Verdict:
    head_sha: str
    verdict: Literal["approve", "changes_requested"]
    summary: str
    findings: tuple[Finding, ...]
    reviewer: Agent
    session_id: str
    raw: Mapping[str, object]  # the validated JSON, echoed in the fenced block


class VerdictError(Exception):
    problems: tuple[str, ...]


def parse_verdict(data: object, expected_reviewer: Agent) -> Verdict: ...
def commentable_lines(patch: str) -> frozenset[int]: ...
def review_body(verdict: Verdict, outside: Sequence[Finding]) -> str: ...
def post_review(
    project: ProjectSettings, access: GitHubAccess, number: int, verdict_path: Path
) -> int: ...
def review_command(args: argparse.Namespace) -> int: ...
def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...
```

- [ ] **Step 1: Write the failing tests.** Create `tests/devctl/test_devctl_review.py`. A module fixture `pr(github: FakeGitHub) -> FakePullRequest` registers PR 7 on `o/r` in the fake and returns a `FakePullRequest`, a mutable dataclass in `github_fakes.py` with `state: str = "open"` and `reviews: list[dict[str, Any]]` (empty), which the routes read on every request. `GET …/pulls/7` returns `{"number": 7, "state": pr.state, "head": {"sha": "a" * 40}}`. `GET …/pulls/7/files` returns one file `src/app/links.py` with patch `"@@ -40,3 +40,4 @@\n ctx\n+added\n ctx\n ctx"` (right-side lines 40–43). `GET …/pulls/7/reviews` returns `pr.reviews`. `POST …/pulls/7/reviews` appends `{"user": {"login": "rs-reviewer[bot]"}, "commit_id": …, "state": …, "html_url": "https://github.com/o/r/pull/7#pullrequestreview-<n>"}` to `pr.reviews` and returns it.

```python
"""Offline: verdict validation and devctl review against simulated GitHub, as the Reviewer App."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from devctl.github.app import GitHubAccess
from devctl.review import VerdictError, commentable_lines, parse_verdict, post_review
from devctl.settings import Agent, ProjectSettings
from github_fakes import FakeGitHub, FakePullRequest

REVIEWER = Agent("claude", "claude-opus-5-5")
HEAD = "a" * 40


def verdict(**changes: object) -> dict[str, Any]:
    data: dict[str, Any] = {
        "head_sha": HEAD,
        "verdict": "approve",
        "summary": "Looks right.",
        "findings": [
            {
                "severity": "non_blocking",
                "path": "src/app/links.py",
                "line": 41,
                "message": "Name the constant.",
                "rung": 3,
                "prevention": "A naming Rule.",
            }
        ],
        "reviewer": {"harness": "claude", "model": "claude-opus-5-5", "session_id": "s-1"},
    }
    data.update(changes)
    return data


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"head_sha": "abc"}, "head_sha"),
        ({"verdict": "lgtm"}, "verdict"),
        ({"extra": 1}, "unknown field extra"),
        (
            {"findings": [{"severity": "blocking", "message": "m", "rung": 5, "prevention": "p"}]},
            "rung",
        ),
        (
            {
                "findings": [
                    {
                        "severity": "blocking",
                        "line": 3,
                        "message": "m",
                        "rung": 2,
                        "prevention": "p",
                    }
                ]
            },
            "line needs a path",
        ),
        (
            {"findings": [{"severity": "blocking", "message": "m", "rung": 2, "prevention": "p"}]},
            "approve with a blocking finding",
        ),
        (
            {"reviewer": {"harness": "codex", "model": "gpt-x", "session_id": "s"}},
            "project.toml names claude claude-opus-5-5",
        ),
    ],
)
def test_invalid_verdicts_are_refused(change: dict[str, object], problem: str) -> None:
    with pytest.raises(VerdictError) as caught:
        parse_verdict(verdict(**change), REVIEWER)
    assert any(problem in p for p in caught.value.problems)


def test_commentable_lines_are_right_side_context_and_additions() -> None:
    assert commentable_lines(
        "@@ -40,3 +40,4 @@\n ctx\n+added\n-gone\n ctx\n\\ No newline at end of file"
    ) == frozenset({40, 41, 42})


def write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.usefixtures("pr")
def test_approve_posts_one_review_on_the_head(
    project: ProjectSettings,
    access: GitHubAccess,
    github: FakeGitHub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = verdict(
        findings=[
            *verdict()["findings"],
            {
                "severity": "non_blocking",
                "path": "src/app/links.py",
                "line": 90,
                "message": "Outside the diff.",
                "rung": 2,
                "prevention": "A check.",
            },
        ]
    )
    assert post_review(project, access, 7, write(tmp_path, data)) == 0
    [posted] = [c.body for c in github.calls if c.method == "POST" and c.path.endswith("/reviews")]
    assert (posted["event"], posted["commit_id"]) == ("APPROVE", HEAD)
    assert [(c["path"], c["line"], c["side"]) for c in posted["comments"]] == [
        ("src/app/links.py", 41, "RIGHT")
    ]
    assert "src/app/links.py:90" in posted["body"]
    block = re.search(r"(`{3,})rapid-ship-verdict\n(.*?)\n\1", posted["body"], re.S)
    assert block is not None
    assert json.loads(block.group(2)) == data
    assert "https://github.com/o/r/pull/7#pullrequestreview-" in capsys.readouterr().out


@pytest.mark.usefixtures("pr")
def test_changes_requested_maps_to_request_changes(
    project: ProjectSettings, access: GitHubAccess, github: FakeGitHub, tmp_path: Path
) -> None:
    ticks = "`" * 3
    data = verdict(
        verdict="changes_requested",
        findings=[
            {
                "severity": "blocking",
                "path": "src/app/links.py",
                "line": 41,
                "message": f"Breaks {ticks}links{ticks}.",
                "rung": 2,
                "prevention": "A test.",
            }
        ],
    )
    assert post_review(project, access, 7, write(tmp_path, data)) == 0
    [posted] = [c.body for c in github.calls if c.method == "POST" and c.path.endswith("/reviews")]
    assert posted["event"] == "REQUEST_CHANGES"
    assert (
        "`" * 4 + "rapid-ship-verdict" in posted["body"]
    )  # fence longer than any backtick run inside


@pytest.mark.usefixtures("pr")
def test_stale_head_is_refused_before_any_write(
    project: ProjectSettings, access: GitHubAccess, github: FakeGitHub, tmp_path: Path
) -> None:
    assert post_review(project, access, 7, write(tmp_path, verdict(head_sha="b" * 40))) == 1
    assert not [c for c in github.calls if c.method == "POST" and c.path.endswith("/reviews")]


def test_one_verdict_per_head_from_the_reviewer_app(
    pr: FakePullRequest, project: ProjectSettings, access: GitHubAccess, tmp_path: Path
) -> None:
    pr.reviews.append({"user": {"login": "someone"}, "commit_id": HEAD, "state": "APPROVED"})
    assert post_review(project, access, 7, write(tmp_path, verdict())) == 0
    pr.reviews.append(
        {
            "user": {"login": "rs-reviewer[bot]"},
            "commit_id": HEAD,
            "state": "APPROVED",
            "html_url": "https://github.com/o/r/pull/7#pullrequestreview-1",
        }
    )
    assert post_review(project, access, 7, write(tmp_path, verdict())) == 1


def test_closed_pr_is_refused(
    pr: FakePullRequest, project: ProjectSettings, access: GitHubAccess, tmp_path: Path
) -> None:
    pr.state = "closed"
    assert post_review(project, access, 7, write(tmp_path, verdict())) == 1
```

- [ ] **Step 2: Run it.** `uv run pytest tests/devctl/test_devctl_review.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.review'`.

- [ ] **Step 3: Implement `devctl/review.py`.**
  - `parse_verdict` collects every problem before raising. Top-level fields are exactly `head_sha`, `verdict`, `summary`, `findings` (a list) and `reviewer` (exactly `harness`, `model`, `session_id`, all non-empty strings); others report `unknown field <name>` and absent ones `missing field <name>`. Problems use these words: `head_sha must be 40 lowercase hex characters`; `verdict must be approve or changes_requested`; `summary must not be empty`; for finding *i*, `finding <i>: severity must be blocking or non_blocking`, `finding <i>: rung must be an integer from 1 to 4` (a bool is not an integer), `finding <i>: message must not be empty`, `finding <i>: prevention must not be empty`, `finding <i>: line must be an integer of at least 1`, `finding <i>: line needs a path`. `approve` with any blocking finding reports `approve with a blocking finding`. A reviewer whose harness or model differs from `project.reviewer` reports `the verdict names <harness> <model>; project.toml names <harness> <model>`, so the chosen model is never silently replaced.
  - `commentable_lines` walks the unified patch: a `@@ -a,b +c,d @@` header sets the right-side line to `c`; context (` `) and added (`+`) lines are commentable and advance it; removed (`-`) and `\` lines do not.
  - `review_body` writes the summary, then `Findings outside the diff:` with one `- \`path:line\` **severity** (rung N): message` line per finding that could not be inline, when there are any, then the fenced block. The fence is one backtick longer than the longest backtick run in `json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=False)`, and at least three.
  - `post_review` reads and JSON-parses the file (unreadable gives exit 2; invalid JSON or a `VerdictError` prints each problem and returns 1). It then mints one Reviewer token and uses `access.api(token)` for every call below, narrowing each response with `json_object` or `json_list` before reading a field. `GET /repos/{repository}/pulls/{n}`: refuse unless `state` is `open`, and refuse `stale head: the verdict is for <sha>, the PR head is <sha>` unless `head.sha` equals `head_sha`. The bot login is `access.slug("reviewer", id) + "[bot]"`. `paginate` the reviews with `per_page=100`, and refuse `this head already has a verdict from the Reviewer App: <html_url>` when any review has that login and `commit_id == head_sha`. `paginate` the files with `per_page=100` and build `{filename: commentable_lines(patch)}`; a file without `patch` has none. A finding is inline when its path and line are in that map, with body `**<severity>** (rung N): <message>\n\nPrevention: <prevention>`. `POST …/reviews` with `commit_id`, `event` (`APPROVE` or `REQUEST_CHANGES`), `body` and `comments`, each with `side: "RIGHT"`. Print the review's `html_url`; return 0. `commit_id` pins the review to the head that was checked.
  - `register` adds `review <PR> --verdict <path>` and `set_defaults(handler=review_command)`. `review_command` loads the project as `pr_command` does and returns `run_guarded(lambda: post_review(…), root=repo.root)`. `cli.py` calls `review.register(commands)`. Split `parse_verdict` into a top-level check and a per-finding check so each stays under complexity 10.

- [ ] **Step 4: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_review.py -q`. Expected: 13 passed.

- [ ] **Step 5: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: post Reviewer verdicts with devctl review" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: `devctl doctor`, local items

**Files:**
- Create: `devctl/doctor.py`, `devctl/harness.py`
- Modify: `devctl/check/stacks/python.py` (`guardrail_gaps`), `devctl/check/kit.py` (`kit_summary`), `devctl/cli.py` (register `doctor`)
- Modify: `tests/devctl/github_fakes.py` (`FakeRun`, `FakeHarness`, `RepoFiles`, `MakeContext = Callable[..., DoctorContext]`), `tests/devctl/github_fixtures.py` (`fake_run`, `fake_harness`, `ctx`, `repo_files`)
- Test: `tests/devctl/test_devctl_doctor_local.py`, `tests/devctl/test_devctl_python_guardrails.py`

**Interfaces:**
- Consumes: `ProjectSettings`, `GateSettings`, `load_project`, `load_gate`, `LOCK_PATH` layout and `render_files` (index); `Repo.discover`, `tracked_files` (plan 2 Task 11); `ProjectSettings.excluded` (index); `KitLockError`, `is_excluded` and the lock reader `_entries` behind `managed_paths` in `devctl/check/kit.py` (plan 3 Task 6); `GITLEAKS_VERSION` from `devctl/check/stacks/neutral.py` (plan 3 Task 11); `process.run_process`, `safe_environment`, `ProcessResult`, `MAX_OUTPUT_BYTES` (plan 3 Task 1); `check_workspace.project_settings` and `gate_settings` (plan 3 Task 2); `GitHubAccess`, `project_access`, `rapid_ship_command` (Task 2).
- Produces:

```python
# devctl/doctor.py
Status = Literal["ok", "missing", "unknown"]
DEVCTL_DIRECTORY = "tools/devctl"
KIT_SOURCE = "rapid_ship/templates/kit.toml"  # tracked only where the Kit's templates live


@dataclass(frozen=True)
class Item:
    area: str  # toolchain, guardrails, kit, github, app keys, linear, skills
    name: str
    status: Status
    detail: str


OwnerGet = Callable[[str], object]  # GET with the owner's gh login; raises OwnerReadError


class OwnerReadError(Exception):
    status: int | None
    message: str


@dataclass(frozen=True)
class DoctorContext:
    root: Path
    project: ProjectSettings
    gate: GateSettings
    owner_get: OwnerGet
    access: GitHubAccess | None  # None when project.toml has no repository


def gh_get(path: str) -> object: ...
def claude_item(role: str, result: ProcessResult) -> Item: ...  # parses `claude auth status --json`
def codex_item(role: str, result: ProcessResult) -> Item: ...  # parses `codex login status`
def agy_item(role: str, result: ProcessResult) -> Item: ...  # classifies the agy probe's output
def agy_sign_in(role: str) -> Item: ...  # runs the probe unless another coding session is active
def devctl_exclusion_gaps(pyproject: Mapping[str, object], *, python: bool) -> list[str]: ...
def local_items(ctx: DoctorContext) -> list[Item]: ...
def doctor_exit_code(items: Sequence[Item]) -> int: ...
def run_doctor(ctx: DoctorContext) -> int: ...
def doctor_command(args: argparse.Namespace) -> int: ...
def register(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None: ...


# devctl/check/stacks/python.py
def guardrail_gaps(pyproject: Mapping[str, object]) -> list[str]: ...


# devctl/check/kit.py
@dataclass(frozen=True)
class KitSummary:
    kit_version: str
    unchanged: tuple[str, ...]
    modified: tuple[str, ...]
    missing: tuple[str, ...]
    excluded: tuple[
        str, ...
    ]  # covered by [kit] exclude in project.toml: the project's own, never compared


def kit_summary(
    root: Path, excluded: Sequence[str]
) -> KitSummary: ...  # raises plan 3's KitLockError


# devctl/harness.py: headless Sessions that doctor starts; Task 10 adds the skills probe
HarnessName = Literal["claude", "codex", "agy"]
# The cheapest model per Harness in Checked facts; Step 1 and Task 10 Step 1 confirm each one live.
PROBE_MODELS: dict[HarnessName, str] = {
    "claude": "haiku",
    "codex": "gpt-6-luna",
    "agy": "gemini-3.8-flash-low",
}
PROBE_TIMEOUT_SECONDS = 120.0
AGY_PROBE_ARGS: tuple[str, ...] = (
    "-p",
    "hi",
    "--model",
    PROBE_MODELS["agy"],
    "--print-timeout",
    "90s",
)
# Set inside another coding session; agy must not be started from one (Checked facts). Step 1 confirms
# Codex's name and adds an agy session's own variable unless agy supports starting agy.
FOREIGN_SESSION_VARIABLES = ("CLAUDECODE", "CODEX_THREAD_ID")
SERVICE_ERROR = re.compile(r"Eligibility check failed|\(code 50[234]\)")


def foreign_session(
    environ: Mapping[str, str],
) -> str | None: ...  # the first of those variables that is set
def error_line(
    stderr: str,
) -> str | None: ...  # first line starting `error:` or `AGY_ERROR:`, cut to 300 characters
```

`doctor.py` re-exports the probe arguments with `from devctl.harness import AGY_PROBE_ARGS as AGY_PROBE_ARGS`, because plan 5's `rs-setup` imports `AGY_PROBE_ARGS` from `devctl.doctor`. The redundant alias marks an explicit re-export for Ruff and for mypy's `no_implicit_reexport`.

- [ ] **Step 1: Owner step: check the agy probe, the Codex and agy session variables and gitleaks first.** agy has no sign-in status command, so doctor sends `hi` to a new headless Session on the cheapest model (spec section 6). Google's FAQ does not support starting agy from a Claude Code or Codex session (Checked facts), so the owner runs these in their own terminal and pastes the output:

```sh
agy --version
agy models
agy -p hi --model gemini-3.8-flash-low --print-timeout 90s </dev/null; echo "exit $?"
gitleaks version
```

Expected:
  1. `agy models` prints one `<id>\t<name>` line per model and no prices, as on 2026-10-13. The cheapest is the Gemini Flash model at the lowest effort. Keep `PROBE_MODELS["agy"]` when `gemini-3.8-flash-low` is listed; otherwise set it to the listed Flash model with the lowest effort. If agy lists base names only and takes `--effort` (agy 1.3.5's changelog), set it to the Flash base name and add `"--effort", "low"` to `AGY_PROBE_ARGS`.
  2. The probe prints a non-empty reply and exits 0. A 502 or 503 at the eligibility check is a service error: rerun until one turn answers, and record every attempt.
  3. Record the listing, the reply, the exit code and the final `AGY_PROBE_ARGS` in the Verification record.
  4. In a Codex session, run `env | grep '^CODEX_' | cut -d= -f1` and record the names. Keep `CODEX_THREAD_ID` in `FOREIGN_SESSION_VARIABLES` when it is listed; otherwise replace it with the listed variable whose name marks a session or thread, and record why.
  5. Check agy inside its own session. In your own terminal, run `env | cut -d= -f1 | sort > /tmp/terminal-env.txt`, then start `agy` there and have its Session run these two commands with its shell tool, using item 1's model if it changed:

     ```sh
     env | cut -d= -f1 | sort > /tmp/agy-env.txt
     agy -p hi --model gemini-3.8-flash-low --print-timeout 90s </dev/null; echo "exit $?"
     ```

     Back in the terminal, `comm -13 /tmp/terminal-env.txt /tmp/agy-env.txt` prints the names only the agy session sets. Record those names, never their values, and whether the nested `agy -p hi` answered, with its exit code and any `error:` line. Nesting is supported only when the nested probe answered and agy's own documentation (`agy --help`, `agy changelog`) says agy may start agy. Otherwise it is unsupported or unknown: add the listed name that marks an agy session to `FOREIGN_SESSION_VARIABLES`, and record why. Step 2's `test_agy_is_not_started_from_another_coding_session` runs once per name, so it covers the addition. If no listed name marks the session, doctor cannot tell it runs inside agy: record that under Remaining limits.
  6. Record the first line of `gitleaks version`. The parser below accepts `8.30.1` or `v8.30.1`; if the installed gitleaks prints another shape, change the parser and Step 2's test cases to match it.

- [ ] **Step 2: Write the failing tests.** Add a `FakeRun` class to `github_fakes.py` and a `fake_run(monkeypatch: pytest.MonkeyPatch) -> FakeRun` fixture to `github_fixtures.py`; Task 9 reuses it. It patches `devctl.process.run_process` to record every argv in `fake_run.argv: list[list[str]]` and to return the result set with `fake_run.answer(argv: list[str], result: ProcessResult) -> None`, matched on the executable's base name plus the arguments. Unanswered commands get exit 1 and empty output. It also patches `shutil.which` in `devctl.doctor` to return `/usr/bin/<name>` for every name. Test setup never goes through the patch: `github_fakes.git` calls the directly imported `run_process`, and plan 2's `Repo` runs git through its own `_git` (EX-3).

Add a `FakeHarness` class to `github_fakes.py` and a `fake_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeHarness` fixture to `github_fixtures.py`; Task 10 reuses it. The fixture sets `PATH` to `<tmp>/harness-bin`, `/usr/bin` and `/bin`, so a Harness installed elsewhere is never found. It deletes every `FOREIGN_SESSION_VARIABLES` name from the environment, so the tests behave the same inside a coding session. `install(name: str, *, stdout: str = "", stderr: str = "", code: int = 0) -> None` writes `<name>.stdout` and `<name>.stderr` and an executable `#!/bin/sh` script `name` in that directory. Each run appends `pwd` to `<name>.cwd`, appends its arguments to `<name>.args`, one per line followed by a line `--end--`, prints both output files and exits with `code`. `calls(name) -> list[list[str]]` and `cwds(name) -> list[Path]` read those records, and return `[]` when the script never ran.

```python
"""Offline: doctor's local items with recorded command output and a fake agy on PATH. No real Harness,
gh, gitleaks or GitHub is run."""

import pytest
from devctl.check.stacks.neutral import GITLEAKS_VERSION
from devctl.doctor import (
    AGY_PROBE_ARGS,
    Item,
    agy_sign_in,
    claude_item,
    codex_item,
    doctor_exit_code,
    local_items,
)
from devctl.harness import FOREIGN_SESSION_VARIABLES, PROBE_MODELS
from devctl.process import ProcessResult
from github_fakes import FakeHarness, FakeRun, MakeContext, RepoFiles

# Observed on 2026-10-13 (Checked facts): Google's eligibility check failed, not the sign-in.
SERVICE_503 = (
    "error: failed to send message: send failed; already reported to the user: Eligibility check "
    "failed: failed to get load code assist response: UNAVAILABLE (code 503): The service is "
    "currently unavailable.\n"
)
SERVICE_502 = (
    "error: Eligibility check failed: failed to get load code assist response: request failed "
    '(code 502): HTML response "Error 502 (Server Error)!!1"\n'
)


def result(code: int, out: str = "", err: str = "") -> ProcessResult:
    return ProcessResult(["x"], code, out, err, 0.0)


@pytest.mark.parametrize(
    ("output", "status"),
    [
        (result(0, '{"loggedIn": true, "authMethod": "claude.ai"}'), "ok"),
        (result(1, '{"loggedIn": false}'), "missing"),
        (result(0, '{"loggedIn": true, "authMethod": "console"}'), "unknown"),
        (result(0, '{"loggedIn": false}'), "unknown"),  # exit code and flag disagree
        (result(0, "not json"), "unknown"),
    ],
)
def test_claude_sign_in(output: ProcessResult, status: str) -> None:
    assert claude_item("worker", output).status == status


@pytest.mark.parametrize(
    ("output", "status"),
    [
        (result(0, err="Logged in using ChatGPT\n"), "ok"),
        (result(1, err="Not logged in\n"), "missing"),
        (result(0, err="Logged in using an API key - sk-proj-***ABCD\n"), "missing"),
        (result(0, err="Logged in using access token\n"), "unknown"),
    ],
)
def test_codex_sign_in_never_echoes_the_cli(output: ProcessResult, status: str) -> None:
    item = codex_item("reviewer", output)
    assert item.status == status
    assert "ABCD" not in item.detail


def test_agy_reply_means_signed_in(fake_harness: FakeHarness) -> None:
    fake_harness.install("agy", stdout="Hello! How can I help?\n")
    item = agy_sign_in("worker")
    assert (item.name, item.status) == ("worker sign-in (agy)", "ok")
    assert fake_harness.calls("agy") == [list(AGY_PROBE_ARGS)]
    assert PROBE_MODELS["agy"] in AGY_PROBE_ARGS
    assert "Hello" not in item.detail


@pytest.mark.parametrize(("code", "stderr"), [(0, ""), (1, "error: example failure\n")])
def test_agy_without_a_reply_is_missing(fake_harness: FakeHarness, code: int, stderr: str) -> None:
    # Exit code 0 alone proves nothing (Checked facts).
    fake_harness.install("agy", stderr=stderr, code=code)
    assert agy_sign_in("worker").status == "missing"


@pytest.mark.parametrize("stderr", [SERVICE_503, SERVICE_502])
def test_agy_eligibility_errors_are_unknown_with_the_error(
    fake_harness: FakeHarness, stderr: str
) -> None:
    fake_harness.install("agy", stderr=stderr, code=1)
    item = agy_sign_in("worker")
    assert item.status == "unknown"
    assert "Eligibility check failed" in item.detail


@pytest.mark.parametrize("variable", FOREIGN_SESSION_VARIABLES)
def test_agy_is_not_started_from_another_coding_session(
    fake_harness: FakeHarness, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    fake_harness.install("agy", stdout="Hello!\n")
    monkeypatch.setenv(variable, "1")
    item = agy_sign_in("worker")
    assert item.status == "unknown"
    assert f"({variable} is set)" in item.detail
    assert "run ./devctl doctor from your own terminal" in item.detail
    assert fake_harness.calls("agy") == []


@pytest.mark.usefixtures("fake_harness")
def test_missing_agy_is_missing() -> None:
    assert agy_sign_in("reviewer").status == "missing"


def test_local_items_run_the_agy_probe(
    ctx: MakeContext, fake_run: FakeRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in FOREIGN_SESSION_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    fake_run.answer(["agy", *AGY_PROBE_ARGS], result(0, "Hello!\n"))
    items = {i.name: i for i in local_items(ctx(worker=("agy", "gemini-3.8-flash-high")))}
    assert items["worker sign-in (agy)"].status == "ok"


def test_hooks_ci_workflow_kit_and_linear(
    ctx: MakeContext, fake_run: FakeRun, repo_files: RepoFiles
) -> None:
    repo_files.workflow(job_name="devctl check")
    repo_files.lock(unchanged=["devctl"], missing=["tools/devctl/devctl/cli.py"])
    fake_run.answer(["git", "config", "--get", "core.hooksPath"], result(0, ".githooks\n"))
    items = {i.name: i for i in local_items(ctx())}
    assert items["core.hooksPath"].status == "ok"
    assert items["CI workflow"].status == "ok"
    assert items["Kit files"].status == "missing"
    assert "tools/devctl/devctl/cli.py" in items["Kit files"].detail
    assert (
        "uvx --from git+https://github.com/proxy-hatch/rapid-ship@v0.2.0 rapid-ship status"
        in items["Kit files"].detail
    )
    assert items["Linear IDs"].status == "ok"
    assert "not verified" in items["Linear IDs"].detail


@pytest.mark.usefixtures("fake_run")
def test_excluded_kit_files_are_counted_not_missing(
    ctx: MakeContext, repo_files: RepoFiles
) -> None:
    # The lock records no exclusion; [kit] exclude in project.toml does. Excluding the rs-tdd skill
    # directory covers its edited SKILL.md and its absent .claude/skills link.
    repo_files.write(
        ".agents/skills/rs-tdd/SKILL.md", "---\nname: rs-tdd\ndescription: ours\n---\n"
    )
    repo_files.lock(
        unchanged=["devctl"],
        missing=[],
        stale=[".agents/skills/rs-tdd/SKILL.md", ".claude/skills/rs-tdd"],
    )
    included = {i.name: i for i in local_items(ctx())}["Kit files"]
    assert included.status == "missing"
    assert ".claude/skills/rs-tdd" in included.detail
    kit = {i.name: i for i in local_items(ctx(excluded=(".agents/skills/rs-tdd",)))}["Kit files"]
    assert kit.status == "ok"
    assert "Kit 0.2.0: 1 unchanged, 0 modified, 2 excluded" in kit.detail


def test_gitleaks_must_be_the_pinned_version(ctx: MakeContext, fake_run: FakeRun) -> None:
    fake_run.answer(["gitleaks", "version"], result(0, f"{GITLEAKS_VERSION}\n"))
    assert {i.name: i for i in local_items(ctx())}["gitleaks"].status == "ok"
    fake_run.answer(["gitleaks", "version"], result(0, "v8.18.4\n"))
    older = {i.name: i for i in local_items(ctx())}["gitleaks"]
    assert older.status == "missing"
    assert GITLEAKS_VERSION in older.detail
    fake_run.answer(["gitleaks", "version"], result(1))
    assert {i.name: i for i in local_items(ctx())}["gitleaks"].status == "unknown"


@pytest.mark.usefixtures("fake_run")
def test_tools_devctl_exclusions(ctx: MakeContext, repo_files: RepoFiles) -> None:
    pyproject = '[tool.mypy]\nfiles = ["."]\n\n[tool.uv.workspace]\nmembers = ["tools/*"]\n'
    repo_files.write("pyproject.toml", pyproject)
    item = {i.name: i for i in local_items(ctx())}["tools/devctl exclusions"]
    assert item.status == "missing"
    assert all(f"{tool}:" in item.detail for tool in ("ruff", "mypy", "pytest", "uv"))
    repo_files.write(
        "rapid_ship/templates/kit.toml", ""
    )  # the Kit's own source checks tools/devctl
    item = {i.name: i for i in local_items(ctx())}["tools/devctl exclusions"]
    assert item.status == "missing"
    assert "uv:" in item.detail
    assert "ruff:" not in item.detail


def test_exit_code_prefers_unknown_then_missing() -> None:
    ok, missing, unknown = (Item("a", "n", s, "") for s in ("ok", "missing", "unknown"))
    assert doctor_exit_code([ok]) == 0
    assert doctor_exit_code([ok, missing]) == 1
    assert doctor_exit_code([missing, unknown]) == 2
```

The `ctx(tmp_path: Path, isolated_home: Path, project: ProjectSettings) -> MakeContext` fixture creates a temporary repository with `git init` (the same directory the `repo_files` fixture writes into) and returns a factory. The factory builds a `DoctorContext` with `check_workspace.gate_settings()` (mode `walk`), `owner_get` raising `OwnerReadError(None, "no owner reads in this test")` and `access=None`; its keyword `worker=(harness, model)` replaces the Worker Agent, and its keyword `excluded: Sequence[str] = ()` replaces `project.excluded`, as `load_project` would from `[kit] exclude`. The `repo_files(ctx: MakeContext) -> RepoFiles` fixture returns a `RepoFiles` bound to that repository. Its `workflow(job_name)` writes `.github/workflows/devctl-check.yml`, its `lock(unchanged, missing, stale=())` writes `.rapid-ship/kit.lock` with `kit_version = "0.2.0"`, the project's stack, each unchanged file written with its real `sha256`, and for each stale path a managed entry with `sha256 = "0" * 64`, which no file matches; the lock has no `excluded` key; its `write(path, text)` writes any file; each one then `git add`s what it wrote. Create `tests/devctl/test_devctl_python_guardrails.py`:

```python
"""Offline: the Python guardrail floor from spec section 4, and the tools/devctl exclusions."""

import tomllib
from typing import Any

from devctl.check.stacks.python import guardrail_gaps
from devctl.doctor import devctl_exclusion_gaps
from rapid_ship.kit.templates import render_files


def seeded_pyproject() -> dict[str, Any]:
    variables = {"project_name": "demo", "package": "demo", "owner": "o", "repository": "o/r"}
    [template] = [t for t in render_files("python", variables, ()) if t.path == "pyproject.toml"]
    assert template.content is not None
    return tomllib.loads(template.content.decode())


def test_seeded_python_settings_meet_the_floor() -> None:
    assert guardrail_gaps(seeded_pyproject()) == []


def test_gaps_name_each_missing_setting() -> None:
    data = seeded_pyproject()
    lint = data["tool"]["ruff"]["lint"]
    lint["select"] = [c for c in lint["select"] if c != "SIM"]
    lint["ignore"] = [*lint.get("ignore", []), "RUF100"]
    data["tool"]["mypy"]["warn_unreachable"] = False
    data["project"]["dependencies"] = ["fastapi>=0.115"]
    data["tool"]["pytest"]["ini_options"]["addopts"] = "-ra --strict-config"
    gaps = guardrail_gaps(data)
    assert "ruff: select lacks SIM, ASYNC, FAST" in gaps
    assert "ruff: ignore disables RUF100" in gaps
    assert "mypy: warn_unreachable is not true" in gaps
    assert "pytest: addopts lacks --strict-markers" in gaps
    assert not any("--strict-config" in g for g in gaps)


def test_seeded_python_settings_leave_out_tools_devctl() -> None:
    assert devctl_exclusion_gaps(seeded_pyproject(), python=True) == []


def test_exclusion_gaps_name_each_setting() -> None:
    data = seeded_pyproject()
    data["tool"]["ruff"]["extend-exclude"] = []
    data["tool"]["mypy"]["files"] = ["."]
    data["tool"]["pytest"]["ini_options"]["testpaths"] = ["tests", "tools"]
    data["tool"]["uv"] = {"workspace": {"members": ["tools/*"]}}
    ruff = "ruff: tools/devctl is not in exclude or extend-exclude"
    pytest_gap = "pytest: testpaths does not leave out tools/devctl"
    assert devctl_exclusion_gaps(data, python=True) == [
        ruff,
        "mypy: files covers tools/devctl and no exclude pattern matches it",
        pytest_gap,
        "uv: [tool.uv.workspace] members match tools/devctl; add it to exclude",
    ]
    data["tool"]["mypy"]["exclude"] = ["^tools/devctl/"]
    data["tool"]["uv"]["workspace"]["exclude"] = ["tools/devctl"]
    assert devctl_exclusion_gaps(data, python=True) == [ruff, pytest_gap]
    assert devctl_exclusion_gaps(data, python=False) == []
```

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_doctor_local.py tests/devctl/test_devctl_python_guardrails.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'devctl.doctor'` and `ImportError: cannot import name 'guardrail_gaps'`.

- [ ] **Step 4: Implement.**
  - **Toolchain.** Items `git`, `uv` and `gh` are ok when `shutil.which` finds them; `gh sign-in` is ok when `gh auth status` exits 0. Its output is never printed. When `shutil.which("gitleaks")` finds nothing, the `gitleaks` item is missing with the detail `install gitleaks <GITLEAKS_VERSION>; devctl check blocks its secrets step without it`. Otherwise doctor runs `gitleaks version` by absolute path, from `tempfile.gettempdir()` with a 30 s timeout. The item is ok when the first stdout line, with one leading `v` removed, equals `GITLEAKS_VERSION`. A different `\d+\.\d+\.\d+` version is missing with the detail `gitleaks <found> is installed; devctl check pins <GITLEAKS_VERSION>`. Any other output, a non-zero exit or a timeout is unknown. Each Harness named by `project.worker` or `project.reviewer` is checked once, in an item named `<role> sign-in (<harness>)`, or `worker and reviewer sign-in (<harness>)` when both roles use it. The Harness is located with `shutil.which` and run by absolute path from `tempfile.gettempdir()` (outside the project, no directory created), with `safe_environment`'s `PATH` and `HOME` and a 30 s timeout. `claude_item`: ok when the JSON has `loggedIn: true`, `authMethod == "claude.ai"` and exit 0; missing when `loggedIn: false` with exit 1; any other combination is unknown, with the detail naming `authMethod` only. `codex_item` reads only stderr's first line: `Logged in using ChatGPT` is ok; `Not logged in` is missing; a line starting `Logged in using an API key` is missing with the detail `signed in with an API key; ADR 0001 allows only subscription sign-ins`; anything else is unknown. The detail never contains CLI output, except agy's error line below. A missing Harness binary is missing. doctor never reads a token file.
  - **agy probe.** agy has no status command (Checked facts), so `agy_sign_in(role)` asks it for a reply. When `foreign_session(os.environ)` names a variable, the item is unknown with the detail `agy is not started from inside another coding session (<variable> is set); run ./devctl doctor from your own terminal`, and nothing runs (spec section 6). Otherwise it finds agy with `shutil.which` (absent: missing) and runs `[agy, *AGY_PROBE_ARGS]` through `process.run_process` from `tempfile.gettempdir()` with `PROBE_TIMEOUT_SECONDS`; stdin is `/dev/null`. `agy_item` checks, in this order:
    1. A timeout or cut output is unknown: `agy did not finish within 120 s`.
    2. A stderr line that `SERVICE_ERROR` matches is unknown: `agy's service failed, not necessarily the sign-in: <that line, cut to 300 characters>; rerun ./devctl doctor`.
    3. Exit 0 with non-empty stdout after stripping is ok: `signed in: agy answered on <PROBE_MODELS["agy"]>`. The reply is never printed.
    4. Anything else is missing: `agy gave no reply (exit <code>)`, then `: <error_line(stderr)>` when there is one. Exit 0 alone is not a sign-in.
  - **Guardrails.** For the `python` stack, the item `Python guardrail settings` runs `guardrail_gaps(tomllib.load(pyproject.toml))`: missing with the gaps joined by `; `, or ok. A missing or unparsable `pyproject.toml` makes the item missing. The neutral stack has no such item. The floor is spec section 4:

```python
REQUIRED_RUFF = (
    "E",
    "W",
    "F",
    "I",
    "B",
    "UP",
    "SIM",
    "C4",
    "RUF",
    "PGH",
    "ERA",
    "T20",
    "S",
    "TID",
    "PT",
    "PTH",
    "DTZ",
    "C90",
    "TD",
    "BLE",
    "ANN401",
)
ESCAPE_HATCHES = ("PGH003", "PGH004", "RUF100", "ERA001")
MYPY_CODES = ("ignore-without-code", "redundant-expr", "truthy-bool")
DEV_TOOLS = ("ruff", "mypy", "pytest", "import-linter")


def _covers(selectors: Sequence[str], code: str) -> bool:
    # Ruff selectors are prefixes: "C" selects C4 and C90, "ALL" selects everything.
    return any(s == "ALL" or code.startswith(s) for s in selectors)
```

`guardrail_gaps` reports `ruff: select lacks <codes>` from `select` plus `extend-select`; FAST and ASYNC are required when `[project] dependencies` names `fastapi`, and ASYNC also for `anyio` or `trio`. `<codes>` lists the missing codes in `REQUIRED_RUFF` order, then ASYNC, then FAST, joined by `, `. It reports `ruff: ignore disables <code>` for each escape hatch covered by `ignore`, and `ruff: relative imports are not banned` unless `[tool.ruff.lint.flake8-tidy-imports] ban-relative-imports = "all"`. For mypy it reports `mypy: strict is not true`, `mypy: warn_unreachable is not true`, and `mypy: enable_error_code lacks <codes>`. For import-linter: `import-linter: no layers contract` and `import-linter: no forbidden contract`. For pytest: `pytest: addopts lacks --strict-markers` (likewise `--strict-config`), `pytest: xfail_strict is not true` and `pytest: filterwarnings lacks error`. `addopts` may be a list or a string. This repository's is the list `["-ra", "--strict-markers", "--strict-config"]` (plan 3 Task 18); a project may use a string, as the test's `"-ra --strict-config"` does, so split a string with `shlex.split`. For dependencies: `dev dependencies lack <names>`, comparing normalised names from `[dependency-groups] dev`.
  - **tools/devctl exclusions.** `devctl_exclusion_gaps(pyproject, *, python)` reports these gaps, in this order. Path entries are compared after removing one leading `./` and any trailing `/` or `/**`.
    - With `python`: `ruff: tools/devctl is not in exclude or extend-exclude`, unless an entry of `[tool.ruff] exclude` or `extend-exclude` is `tools/devctl` or `tools`.
    - With `python`: `mypy: files covers tools/devctl and no exclude pattern matches it`, when `tools/devctl/devctl/cli.py` equals or lies under an entry of `[tool.mypy] files` (`.` covers every path) and no `[tool.mypy] exclude` pattern, a string or a list, matches it with `re.search`. This is plan 3's rule for `type:` references.
    - With `python`: `pytest: testpaths does not leave out tools/devctl`, when `[tool.pytest.ini_options] testpaths` is absent or has an entry that is `.`, contains `tools/devctl` or lies inside it, unless `addopts` holds `--ignore=tools/devctl`.
    - For either stack: `uv: [tool.uv.workspace] members match tools/devctl; add it to exclude`, when `_glob(entry).fullmatch("tools/devctl")` holds for an entry of `members` and for no entry of `exclude`. Without the exclude, the project's own `uv lock` fails (Checked facts).

```python
def _glob(pattern: str) -> re.Pattern[str]:
    # uv workspace globs: * and ? stay inside one path segment; ** spans segments.
    parts = re.split(r"(\*\*|\*|\?)", pattern.removeprefix("./").rstrip("/"))
    wildcards = {"**": ".*", "*": "[^/]*", "?": "[^/]"}
    return re.compile("".join(wildcards.get(part, re.escape(part)) for part in parts))
```

The item `tools/devctl exclusions` (area `guardrails`) reads `pyproject.toml` from the work tree. It passes `python=True` only for the `python` stack when `KIT_SOURCE` is not in `tracked_files()`. A repository that tracks `KIT_SOURCE` holds the Kit's templates and checks `tools/devctl` itself (spec section 4), so the detail then adds `ruff, mypy and pytest not checked: this repository holds the Kit templates`. Gaps make the item missing, with the gaps joined by `; `; no gaps make it ok. Without `pyproject.toml`, the item is ok for the neutral stack (`no pyproject.toml, so no uv workspace`) and missing for the `python` stack. An unparsable `pyproject.toml` is missing. Split the checks into one helper per tool, so each function stays under complexity 10.
  - `core.hooksPath` is ok when `git config --get core.hooksPath` prints `.githooks`. The `CI workflow` item is ok when `.github/workflows/devctl-check.yml` is in `Repo.discover(ctx.root).tracked_files()` and, parsed with PyYAML, has a job whose `name` is `devctl check`, which the ruleset requires.
  - **Kit.** `kit_summary(root, excluded)` reads the lock through plan 3's `_entries`, the reader behind `managed_paths`, so an unreadable lock raises plan 3's `KitLockError`, and skips the lock's own entry and seeded entries. The lock records no exclusion, so doctor passes `ctx.project.excluded`, the `[kit] exclude` list from `project.toml`. A managed entry that plan 3's `is_excluded(entry.path, excluded)` covers goes into `excluded` without a look at the disk: the project owns that path (spec section 3, Who owns what), so it is never modified or missing. `is_excluded` also covers paths below an excluded directory and `.claude/skills/<name>` when `.agents/skills/<name>` is excluded; never compare paths to the list directly. Every other managed file is unchanged when its SHA-256 matches `sha256`, modified when it differs, and missing when absent or a symlink. A managed link is unchanged when `Path.readlink()` equals `link`; Ruff's PTH rules forbid `os.readlink`. The `Kit files` item is missing when any file that is not excluded is missing, or the lock is unreadable; otherwise it is ok with `Kit <version>: <n> unchanged, <m> modified, <k> excluded` and the modified paths. doctor cannot see template updates, so with a readable lock the detail of either status ends `run <rapid_ship_command(root, "status")> to see template updates` (Task 2), for example `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v0.2.0 rapid-ship status`.
  - **Linear.** `Linear IDs` is ok when both IDs are non-empty, with the detail `configured; doctor cannot verify Linear, rs-setup verifies it through Linear's MCP`; otherwise missing.
  - `run_doctor` prints `<status>  <area>  <name>: <detail>` per item and a final `doctor: <n> ok, <m> missing, <k> unknown`, then returns `doctor_exit_code`. `gh_get(path)` runs `["gh", "api", "--method", "GET", path]` through `process.run_process` with a 60 s timeout, parses stdout as JSON and returns it as `object`. It checks the result in this order. A timeout raises `OwnerReadError(None, "gh api timed out")`. Cut stdout raises `OwnerReadError(None, f"gh api output exceeded {process.MAX_OUTPUT_BYTES} bytes")`. A non-zero exit raises `OwnerReadError` with the status from stderr's `(HTTP <code>)` and the JSON `message` from stdout when present. `register` adds `doctor` with `set_defaults(handler=doctor_command)`. `doctor_command` builds `Repo.discover(Path.cwd())`, `load_project`, `load_gate`, `gh_get` and `project_access(project)` (or `None` without a repository) into a `DoctorContext` and returns `run_doctor`. `cli.py` calls `doctor.register(commands)`.

- [ ] **Step 5: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl/test_devctl_doctor_local.py tests/devctl/test_devctl_python_guardrails.py -q`. Expected: all pass (27 tests, 23 of them in `test_devctl_doctor_local.py`, with one case of `test_agy_is_not_started_from_another_coding_session` per `FOREIGN_SESSION_VARIABLES` name; one more of each when Step 1 added agy's variable).

- [ ] **Step 6: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: report toolchain, agy's sign-in, guardrails, Kit and Linear in devctl doctor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: `devctl doctor`, GitHub and App items

**Files:**
- Modify: `devctl/doctor.py`
- Create: `tests/devctl/fixtures/github/repository.json`, `ruleset-list.json`, `ruleset.json`, `fork-approval.json`, `codeowners.json`
- Modify: `tests/devctl/github_fakes.py` (`RecordedOwner`, `FakeGitHub.uninstall`), `tests/devctl/github_fixtures.py` (`recorded`, `ctx_github`, `keychain_without_reviewer`)
- Test: `tests/devctl/test_devctl_doctor_github.py`

**Interfaces:**
- Consumes: Task 8's `DoctorContext`, `Item`, `OwnerGet`, `OwnerReadError`, `gh_get`; `installation`, `installation_token`, `APP_PERMISSIONS`, `AppError`, `KeychainMissing`, `rapid_ship_command` (Task 2); `json_list`, `json_object` (Task 1); `Repo.discover` and `git_common_dir` (plan 2 Task 11); `render_files` and the seeded `.github/CODEOWNERS` (plan 2 Tasks 2 and 6), in tests only.
- Produces:

```python
ADMIN_ROLE_ID = 5  # repository admin role; Task 12 confirms by reading the ruleset back
GITHUB_ACTIONS_APP_ID = 15368  # gh api /apps/github-actions
# The Flight block of plan 2's seeded CODEOWNERS (spec section 4's Protected set, with the devctl
# shim). Plan 3 added the settings files of gitleaks and zizmor: a settings file can switch its
# check off.
PROTECTED_PATHS = (
    ".github/",
    ".githooks/",
    "devctl",
    "tools/devctl/",
    ".agents/skills/",
    ".claude/skills/",
    ".rapid-ship/",
    ".gitleaks.toml",
    ".gitleaksignore",
    "zizmor.yml",
    "zizmor.yaml",
)
# The Python guardrail settings: every file Ruff, mypy, pytest and import-linter read settings
# from, in the template's last lines. Ruff reads the nearest ruff.toml, so those match at any depth.
PYTHON_PROTECTED_PATHS = (
    "pyproject.toml",
    "**/ruff.toml",
    "**/.ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pytest.ini",
    ".pytest.ini",
    "pytest.toml",
    ".pytest.toml",
    "setup.cfg",
    "tox.ini",
    ".importlinter",
)


def ruleset_problems(
    rulesets: Sequence[Mapping[str, object]], default_branch: str
) -> list[str]: ...
def codeowners_problems(
    text: str, mode: Literal["walk", "flight"], owner: str, stack: Literal["python", "neutral"]
) -> list[str]: ...
def installation_problems(found: Mapping[str, object], role: AppRole) -> list[str]: ...
def github_items(ctx: DoctorContext) -> list[Item]: ...
```

`ruleset_problems` takes rulesets in the shape `GET /repos/{o}/{r}/rulesets/{id}` returns. Plan 5's `tests/devctl/test_devctl_rs_setup_ruleset.py` checks `rs-setup/ruleset.json` with it, and Task 12 Step 8 applies the same JSON.

- [ ] **Step 1: Write the fixtures.** These mirror the shapes observed on 2026-10-14; Task 12 replaces `ruleset.json` with the read-back.
  - `repository.json`: `{"id": 2, "default_branch": "main", "visibility": "public", "delete_branch_on_merge": true, "owner": {"login": "o", "id": 1, "type": "User"}}`.
  - `ruleset-list.json`: `[{"id": 9, "name": "rapid-ship", "target": "branch", "source_type": "Repository", "enforcement": "active"}]`.
  - `ruleset.json`: id 9, `"enforcement": "active"`, `"conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}`, `"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]`, and the four rules from Task 12 Step 8.
  - `fork-approval.json`: `{"approval_policy": "all_external_contributors"}`.
  - `codeowners.json`: a contents response whose base64 `content` decodes to `# Walk\n* @o\n# .github/ @o\n`.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_doctor_github.py`. A `recorded() -> RecordedOwner` fixture returns a callable `owner_get` that serves the fixtures by exact path (`repos/o/r`, `repos/o/r/rulesets?targets=branch`, `repos/o/r/rulesets/9`, `repos/o/r/actions/permissions/fork-pr-contributor-approval`, `repos/o/r/contents/.github/CODEOWNERS?ref=main`). It records each path and raises `OwnerReadError(404, "Not Found")` for any other. `recorded.serve(path: str, value: object)` and `recorded.fail(path: str, error: OwnerReadError)` override one path. Task 8's `fake_run` records every argv.

```python
"""Offline: doctor's GitHub items with recorded responses and simulated Apps. No live GitHub."""

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from devctl.dispatch import gate_log_path
from devctl.doctor import (
    PROTECTED_PATHS,
    PYTHON_PROTECTED_PATHS,
    OwnerReadError,
    codeowners_problems,
    gh_get,
    github_items,
    installation_problems,
    ruleset_problems,
    run_doctor,
)
from devctl.process import ProcessResult
from devctl.repo import Repo
from github_fakes import FakeGitHub, FakeKeychain, FakeRun, MakeContext, RecordedOwner
from rapid_ship.kit.templates import render_files

FIXTURES = Path(__file__).parent / "fixtures" / "github"
RULESET: dict[str, Any] = json.loads((FIXTURES / "ruleset.json").read_text())
PROTECTED = "".join(
    f"/{path} @o\n"
    for path in (
        ".github/",
        ".githooks/",
        "devctl",
        "tools/devctl/",
        ".agents/skills/",
        ".claude/skills/",
        ".rapid-ship/",
        ".gitleaks.toml",
        ".gitleaksignore",
        "zizmor.yml",
        "zizmor.yaml",
    )
)


def rule(ruleset: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(r for r in ruleset["rules"] if r["type"] == kind)


def snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*")}


def test_the_rs_setup_ruleset_passes() -> None:
    assert ruleset_problems([RULESET], "main") == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (
            lambda r: rule(r, "pull_request")["parameters"].update(require_code_owner_review=False),
            "code-owner review",
        ),
        (
            lambda r: rule(r, "pull_request")["parameters"].update(
                dismiss_stale_reviews_on_push=False
            ),
            "stale approvals",
        ),
        (
            lambda r: rule(r, "pull_request")["parameters"].update(
                require_last_push_approval=False
            ),
            "most recent push",
        ),
        (
            lambda r: rule(r, "required_status_checks")["parameters"]["required_status_checks"][
                0
            ].pop("integration_id"),
            "GitHub Actions",
        ),
        (
            lambda r: r["bypass_actors"].append(
                {"actor_id": 101, "actor_type": "Integration", "bypass_mode": "always"}
            ),
            "bypass",
        ),
        (lambda r: r.update(enforcement="evaluate"), "not active"),
        (
            lambda r: r["conditions"]["ref_name"].update(include=["refs/heads/release"]),
            "default branch",
        ),
        (
            lambda r: r.update(rules=[x for x in r["rules"] if x["type"] != "non_fast_forward"]),
            "force pushes",
        ),
    ],
)
def test_ruleset_problems(change: Callable[[dict[str, Any]], object], problem: str) -> None:
    ruleset = copy.deepcopy(RULESET)
    change(ruleset)
    assert any(problem in p for p in ruleset_problems([ruleset], "main"))


def test_owner_reads_are_get_requests(fake_run: FakeRun) -> None:
    fake_run.answer(
        ["gh", "api", "--method", "GET", "repos/o/r"],
        ProcessResult(["gh"], 0, '{"id": 2}', "", 0.0),
    )
    assert gh_get("repos/o/r") == {"id": 2}
    fake_run.answer(
        ["gh", "api", "--method", "GET", "repos/o/r/rulesets"],
        ProcessResult(
            ["gh"],
            1,
            '{"message": "Upgrade to GitHub Pro"}',
            "gh: Upgrade to GitHub Pro (HTTP 403)",
            0.0,
        ),
    )
    with pytest.raises(OwnerReadError) as caught:
        gh_get("repos/o/r/rulesets")
    assert (caught.value.status, caught.value.message) == (403, "Upgrade to GitHub Pro")
    fake_run.answer(
        ["gh", "api", "--method", "GET", "repos/o/r/rulesets/9"],
        ProcessResult(["gh"], 0, '{"id": 9', "", 0.0, stdout_truncated=True),
    )
    with pytest.raises(OwnerReadError, match="exceeded"):
        gh_get("repos/o/r/rulesets/9")


def test_codeowners_must_match_the_mode() -> None:
    assert codeowners_problems("* @o\n", "walk", "o", "python") == []
    assert codeowners_problems("* @o\n/src/ @team\n", "walk", "o", "python")
    assert codeowners_problems(PROTECTED, "flight", "o", "neutral") == []
    assert codeowners_problems("* @o\n" + PROTECTED, "flight", "o", "neutral")
    assert codeowners_problems(PROTECTED.replace("/devctl @o\n", ""), "flight", "o", "neutral")


def test_python_flight_codeowners_protects_the_guardrail_settings() -> None:
    assert any(
        "pyproject.toml" in p for p in codeowners_problems(PROTECTED, "flight", "o", "python")
    )
    python = "".join(f"/{path} @o\n" for path in PYTHON_PROTECTED_PATHS)
    assert codeowners_problems(PROTECTED + python, "flight", "o", "python") == []


def test_protected_paths_match_the_seeded_codeowners() -> None:
    variables = {"project_name": "demo", "package": "demo", "owner": "o", "repository": "o/r"}
    templates = render_files("python", variables, ())
    [template] = [t for t in templates if t.path == ".github/CODEOWNERS"]
    assert template.content is not None
    flight = [
        line.removeprefix("# ")
        for line in template.content.decode().splitlines()
        if re.fullmatch(r"# /\S+ @o", line)
    ]
    protected = {line.split()[0].removeprefix("/") for line in flight}
    assert protected == {*PROTECTED_PATHS, *PYTHON_PROTECTED_PATHS}
    assert (
        codeowners_problems("".join(f"{line}\n" for line in flight), "flight", "o", "python") == []
    )


def test_installation_permissions_must_match_exactly() -> None:
    worker = {"contents": "write", "pull_requests": "write", "issues": "write", "metadata": "read"}
    assert installation_problems({"permissions": worker}, "worker") == []
    assert installation_problems({"permissions": {**worker, "workflows": "write"}}, "worker")


def test_all_github_items_ok(ctx_github: MakeContext) -> None:
    items = github_items(ctx_github())
    assert {(i.name, i.status) for i in items} == {
        ("ruleset", "ok"),
        ("CODEOWNERS", "ok"),
        ("delete branch on merge", "ok"),
        ("fork PR workflow approval", "ok"),
        ("Worker App installation", "ok"),
        ("Reviewer App installation", "ok"),
        ("Worker App key", "ok"),
        ("Reviewer App key", "ok"),
    }


def test_plan_limited_rulesets_are_missing(
    ctx_github: MakeContext, recorded: RecordedOwner
) -> None:
    recorded.fail(
        "repos/o/r/rulesets?targets=branch",
        OwnerReadError(
            403, "Upgrade to GitHub Pro or make this repository public to enable this feature."
        ),
    )
    [ruleset] = [i for i in github_items(ctx_github()) if i.name == "ruleset"]
    assert ruleset.status == "missing"
    assert "public repository or a paid GitHub plan" in ruleset.detail


def test_unreadable_bypass_list_is_unknown(
    ctx_github: MakeContext, recorded: RecordedOwner
) -> None:
    recorded.serve(
        "repos/o/r/rulesets/9", {k: v for k, v in RULESET.items() if k != "bypass_actors"}
    )
    [ruleset] = [i for i in github_items(ctx_github()) if i.name == "ruleset"]
    assert ruleset.status == "unknown"


def test_missing_reviewer_key(
    ctx_github: MakeContext, keychain_without_reviewer: FakeKeychain
) -> None:
    items = {i.name: i for i in github_items(ctx_github(keychain=keychain_without_reviewer))}
    assert items["Reviewer App key"].status == "missing"
    assert items["Reviewer App installation"].status == "missing"  # no key, no JWT to look it up
    assert items["Worker App key"].status == "ok"


def test_uninstalled_app(ctx_github: MakeContext, github: FakeGitHub) -> None:
    github.uninstall(202, "o/r")
    items = {i.name: i for i in github_items(ctx_github())}
    assert items["Reviewer App installation"].status == "missing"
    assert items["Reviewer App key"].status == "unknown"


def test_doctor_makes_no_writes(
    ctx_github: MakeContext, fake_run: FakeRun, github: FakeGitHub
) -> None:
    ctx = ctx_github()
    before = snapshot(ctx.root)
    run_doctor(ctx)
    assert snapshot(ctx.root) == before
    assert not gate_log_path(Repo.discover(ctx.root).git_common_dir).exists()
    assert not any(
        a in {"fetch", "push", "worktree", "commit", "add"} for argv in fake_run.argv for a in argv
    )
    assert all(
        argv[:4] == ["gh", "api", "--method", "GET"]
        for argv in fake_run.argv
        if argv[0] == "gh" and argv[1] == "api"
    )
    writes = [(c.method, c.path) for c in github.calls if c.method != "GET"]
    assert writes
    assert all(m == "POST" and p.endswith("/access_tokens") for m, p in writes)
```

The `ctx_github` fixture requests `isolated_home`, `project`, `github`, `keychain`, `recorded` and `repo_files`, so the temporary repository and its Kit files exist before the test body starts `fake_run`'s patch. It returns a factory whose keyword `keychain` (default: the `keychain` fixture) builds a `DoctorContext` with `check_workspace.gate_settings()` (mode `walk`), the `recorded` owner reader, and `GitHubAccess("o/r", api_url=github.url, keychain=…)`. Add `FakeGitHub.uninstall(app_id: int, repository: str) -> None` and the `keychain_without_reviewer() -> FakeKeychain` fixture, which holds only the Worker key.

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_doctor_github.py -q`. Expected: collection fails with `ImportError: cannot import name 'ruleset_problems'`.

- [ ] **Step 4: Implement.** With no repository in `project.toml`, `github_items` returns one missing item, `repository is not set in .rapid-ship/project.toml`. Otherwise it reads `repos/{repository}` once with `owner_get` and builds the items below, narrowing each response with `json_object` or `json_list` (a `GitHubError` from narrowing makes that item unknown):
  - **ruleset:** `repos/{repository}/rulesets?targets=branch` and each listed ruleset with `source_type == "Repository"` by ID. `ruleset_problems` checks each ruleset and returns `[]` when one has no problem; otherwise it returns the problems of the ruleset with the fewest, or `["no ruleset targets the default branch"]` when there is none. A ruleset's problems, in these words:
    - `the ruleset does not target the default branch`, unless `include` has `~DEFAULT_BRANCH`, `~ALL` or `refs/heads/<default>` and `exclude` has none of them;
    - `the ruleset is not active`, unless `enforcement == "active"`;
    - `no pull_request rule requires an approval`, unless `required_approving_review_count >= 1`;
    - `the pull_request rule does not require code-owner review`;
    - `the pull_request rule does not dismiss stale approvals on push`, unless `dismiss_stale_reviews_on_push` is `true`;
    - `the pull_request rule does not require approval of the most recent push`, unless `require_last_push_approval` is `true`. Without these two, the Worker App, which has Contents and Pull requests write, could push after an approval and merge on it (plan 5 Task 7);
    - `the devctl check status check is not bound to GitHub Actions (integration 15368)`, unless `required_status_checks` contains `{"context": "devctl check", "integration_id": 15368}`;
    - `force pushes are not blocked` (no `non_fast_forward` rule) and `deletion is not blocked` (no `deletion` rule);
    - `the bypass list must hold only the admin role in pull_request mode`, unless `bypass_actors` is exactly `[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]`.
    A ruleset without `bypass_actors` makes the item unknown (`the bypass list is visible only to users who can edit the ruleset`). A 403 whose message contains `Upgrade to GitHub Pro` makes it missing: `rulesets need a public repository or a paid GitHub plan (GitHub returned 403)`. Any other `OwnerReadError` makes it unknown.
  - **CODEOWNERS:** `repos/{repository}/contents/.github/CODEOWNERS?ref=<default>`, base64-decoded, because GitHub reads CODEOWNERS from the base branch. `codeowners_problems` ignores blank and `#` lines and compares owners case-insensitively. In Walk it requires exactly one active line, `* @<owner>`, where the owner comes from `repository`. In Flight it forbids a `*` line and requires each `PROTECTED_PATHS` entry, and for the `python` stack each `PYTHON_PROTECTED_PATHS` entry, with or without a leading `/`, to be owned by `@<owner>`; `github_items` passes `project.stack`. A 404 is missing.
  - **delete branch on merge:** ok when `delete_branch_on_merge` is true.
  - **fork PR workflow approval:** for a public repository, ok when `repos/{repository}/actions/permissions/fork-pr-contributor-approval` returns `all_external_contributors`; for a private one, ok with `not applicable: private repository`.
  - **Worker App installation / Reviewer App installation:** missing when the App ID is unset. Otherwise `installation(role, …)`: an `AppError` is missing; `installation_problems` compares `permissions` exactly with `APP_PERMISSIONS[role]`; a `GitHubError` is unknown.
  - **Worker App key / Reviewer App key:** `installation_token(role, …)` succeeds: ok, `Keychain item found; token minted (changes nothing in the repository)`. `KeychainMissing` is missing, with the error text and the same `; run <rapid_ship_command(ctx.root, "app")>` remedy that `run_guarded` adds (Task 2). An `AppError` for a missing installation is unknown (`key found; minting needs the App installed`). A `GitHubError` is unknown. The token is discarded unprinted.
  `run_doctor` now prints `local_items` then `github_items`.

- [ ] **Step 5: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`. Expected: all pass, 20 in `test_devctl_doctor_github.py` (8 of them parametrised cases).

- [ ] **Step 6: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: check GitHub settings and both Apps in devctl doctor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 10: `devctl doctor --skills`

**Files:**
- Modify: `devctl/harness.py` (the skills probe), `devctl/dispatch.py` (`probe_worktree`), `devctl/doctor.py` (`skills_items`, `--skills`)
- Test: `tests/devctl/test_devctl_doctor_skills.py`

**Interfaces:**
- Consumes: `HarnessName`, `PROBE_MODELS`, `PROBE_TIMEOUT_SECONDS`, `foreign_session`, `error_line`, `Item`, `DoctorContext`, `run_doctor`, `FakeHarness` and `fake_harness` (Task 8); `default_head`, `worktree_root` (Task 4); `GitHubAccess.token`, `DevctlError`, `GitError` (Tasks 2–3); `GitHubError` (Task 1); the `remote`, `access` and `project` fixtures (Tasks 3–4).
- Produces:

```python
# devctl/harness.py
SKILLS_PROMPT = "List the name of every skill you can load, one name per line, and nothing else."


@dataclass(frozen=True)
class SkillReport:
    names: frozenset[str] | None  # None when the Session gave no skill list
    error: str | None  # why not, cut to 300 characters


def skills_args(harness: HarnessName) -> list[str]: ...  # arguments after the executable
def parse_skills(harness: HarnessName, result: ProcessResult) -> SkillReport: ...


# devctl/dispatch.py
@contextmanager
def probe_worktree(
    repo: Repo, setting: str, start: str
) -> Iterator[Path]: ...  # detached; always removed


# devctl/doctor.py
def repository_skills(
    tree: Path,
) -> tuple[frozenset[str], frozenset[str]]: ...  # (checked, user-invoked)
def skills_items(ctx: DoctorContext) -> list[Item]: ...
def run_doctor(ctx: DoctorContext, *, skills: bool = False) -> int: ...
```

- [ ] **Step 1: Owner step: check each Harness's headless skill list first.** The `claude` and `codex exec` commands each start a headless Session and spend a little quota; `agy -p /skills` answers without an agent turn. Run them in your own terminal, not from a coding session, in a scratch clone with at least two `.agents/skills/<name>/SKILL.md` files and their `.claude/skills/<name>` links. One of them sets `disable-model-invocation: true` in its front matter.

```sh
claude -p "List the name of every skill you can load, one name per line, and nothing else." --output-format stream-json --verbose --model haiku </dev/null > /tmp/claude-skills.jsonl; echo "exit $?"
codex debug models | python3 -c "import json, sys; print([(m['slug'], m['description']) for m in json.load(sys.stdin)['models'] if m.get('visibility') == 'list'])"
codex exec --json --model gpt-6-luna -c 'model_reasoning_effort="low"' --sandbox read-only --ephemeral "List the name of every skill you can load, one name per line, and nothing else." </dev/null; echo "exit $?"
agy -p /skills --output-format json --model gemini-3.8-flash-low </dev/null; echo "exit $?"
```

Expected, and what to change when the output differs:
  1. The first line of `/tmp/claude-skills.jsonl` is the `system` `init` event, and its `skills` lists the skill directories' names (Checked facts); the last line is the `result` event. Record whether the user-invoked skill appears in `skills`. If `skills` is absent, `parse_skills` reads the `result` text instead; change `claude_stream` in Step 2 to send no `skills`.
  2. `codex debug models` lists `gpt-6-luna` as the fast and affordable model. If it does not, set `PROBE_MODELS["codex"]` to the listed model with that description. `codex exec` prints `thread.started`, one `item.completed` agent message with one name per line, and `turn.completed`, with no skill list (Checked facts). If Codex rejects `model_reasoning_effort`, drop that `-c` pair from `skills_args`.
  3. agy answers `/skills` without an agent turn (Checked facts). `parse_skills` expects a JSON array of objects, each with a string `name` and a boolean `builtin`. If the shape differs, change `parse_skills` and `agy_skills` in Step 2 to match it. If agy answers with a model turn or an error, give agy `SKILLS_PROMPT` and the text parser, as Codex has.
  4. Record, in the Verification record, each command's exit code, the event types and field names it printed, and the skill names. Never record a path under the home directory, a session ID or an account name.

- [ ] **Step 2: Write the failing tests.** Create `tests/devctl/test_devctl_doctor_skills.py`. The `remote` fixture's bare repository stands in for GitHub; `access` mints simulated Worker tokens; Task 4's `project` uses agy for the Worker and Claude Code for the Reviewer.

```python
"""Offline: doctor --skills with fake Harness executables on PATH, a local bare repository standing in
for GitHub and simulated App tokens. No real Harness runs."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from check_workspace import gate_settings
from devctl.doctor import DoctorContext, OwnerReadError, skills_items
from devctl.github.app import GitHubAccess
from devctl.harness import PROBE_MODELS
from devctl.settings import Agent, ProjectSettings
from github_fakes import FakeHarness, Remote, git


def no_owner_reads(path: str) -> object:
    raise OwnerReadError(None, "no owner reads in this test")


@pytest.fixture
def doctor_ctx(remote: Remote, project: ProjectSettings, access: GitHubAccess) -> DoctorContext:
    return DoctorContext(remote.clone, project, gate_settings(), no_owner_reads, access)


def publish_skills(clone: Path, *names: str, user_invoked: tuple[str, ...] = ()) -> None:
    for name in (*names, *user_invoked):
        flag = "disable-model-invocation: true\n" if name in user_invoked else ""
        skill = clone / ".agents" / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: The {name} skill.\n{flag}---\n"
        )
    git(clone, "add", ".agents")
    git(clone, "commit", "-m", "add skills")
    git(clone, "push", "origin", "HEAD:main")


def claude_stream(skills: list[str]) -> str:
    init = {
        "type": "system",
        "subtype": "init",
        "session_id": "s-1",
        "skills": skills,
        "plugins": [],
        "slash_commands": skills,
    }
    done = {"type": "result", "subtype": "success", "is_error": False, "result": "\n".join(skills)}
    return f"{json.dumps(init)}\n{json.dumps(done)}\n"


def agy_skills(names: list[str]) -> str:
    return json.dumps([{"name": name, "builtin": False} for name in names])


def worktrees(remote: Remote) -> list[str]:
    listing = git(remote.clone, "worktree", "list", "--porcelain")
    return [line for line in listing.splitlines() if line.startswith("worktree ")]


def test_each_harness_sees_the_repository_skills(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    publish_skills(remote.clone, "rs-tdd", "billing-rules")
    fake_harness.install("agy", stdout=agy_skills(["rs-tdd", "billing-rules"]))
    fake_harness.install(
        "claude", stdout=claude_stream(["rs-tdd", "billing-rules", "my-notes", "tools:lint"])
    )
    items = {i.name: i for i in skills_items(doctor_ctx)}
    assert items["worker skills (agy)"].status == "ok"
    reviewer = items["reviewer skills (claude)"]
    assert reviewer.status == "ok"
    assert "outside the repository: my-notes, tools:lint" in reviewer.detail
    [args] = fake_harness.calls("claude")
    assert args[args.index("--model") + 1] == PROBE_MODELS["claude"]
    [cwd] = fake_harness.cwds("claude")
    assert cwd.parent == (remote.clone.parent / "r.worktrees").resolve()
    assert not cwd.exists()
    assert len(worktrees(remote)) == 1


def test_a_skill_the_session_cannot_see_is_missing(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    publish_skills(remote.clone, "rs-tdd")
    # Pushed from another clone: only a worktree at the remote default branch's head has it.
    publish_skills(remote.clone_again("r2"), "billing-rules")
    fake_harness.install("agy", stdout=agy_skills(["rs-tdd", "billing-rules"]))
    fake_harness.install("claude", stdout=claude_stream(["rs-tdd"]))
    reviewer = {i.name: i for i in skills_items(doctor_ctx)}["reviewer skills (claude)"]
    assert reviewer.status == "missing"
    assert "missing: billing-rules" in reviewer.detail


def test_codex_lists_skills_one_name_per_line(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    publish_skills(remote.clone, "rs-tdd")
    events = [
        {"type": "thread.started", "thread_id": "t-1"},
        {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": "- rs-tdd\nreview-notes\n"},
        },
        {"type": "turn.completed", "usage": {}},
    ]
    fake_harness.install("codex", stdout="".join(f"{json.dumps(event)}\n" for event in events))
    codex = replace(
        doctor_ctx.project,
        worker=Agent("codex", "gpt-6.1-sol"),
        reviewer=Agent("codex", "gpt-6-astra"),
    )
    [item] = skills_items(replace(doctor_ctx, project=codex))
    assert (item.name, item.status) == ("worker and reviewer skills (codex)", "ok")
    assert "outside the repository: review-notes" in item.detail
    [args] = fake_harness.calls("codex")
    assert args[:2] == ["exec", "--json"]
    assert args[args.index("--model") + 1] == PROBE_MODELS["codex"]
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in args


def test_user_invoked_skills_are_not_checked(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    publish_skills(remote.clone, "rs-tdd", user_invoked=("rs-setup",))
    fake_harness.install("agy", stdout=agy_skills(["rs-tdd"]))
    # A Harness may list a user-invoked skill anyway; it is still a repository skill, not an outside one.
    fake_harness.install("claude", stdout=claude_stream(["rs-tdd", "rs-setup"]))
    for item in skills_items(doctor_ctx):
        assert item.status == "ok"
        assert "not checked, user-invoked: rs-setup" in item.detail
        assert "outside the repository" not in item.detail


def test_worktree_is_removed_when_a_session_fails(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    publish_skills(remote.clone, "rs-tdd")
    fake_harness.install(
        "agy",
        code=1,
        stderr="error: Eligibility check failed: UNAVAILABLE (code 503): "
        "The service is currently unavailable.\n",
    )
    fake_harness.install("claude", code=1)
    items = {i.name: i for i in skills_items(doctor_ctx)}
    assert items["worker skills (agy)"].status == "unknown"
    assert "code 503" in items["worker skills (agy)"].detail
    assert items["reviewer skills (claude)"].status == "unknown"
    assert len(worktrees(remote)) == 1
    assert list((remote.clone.parent / "r.worktrees").glob(".doctor-skills-*")) == []


def test_skills_probe_skips_agy_inside_another_coding_session(
    doctor_ctx: DoctorContext,
    remote: Remote,
    fake_harness: FakeHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish_skills(remote.clone, "rs-tdd")
    fake_harness.install("agy", stdout=agy_skills(["rs-tdd"]))
    fake_harness.install("claude", stdout=claude_stream(["rs-tdd"]))
    monkeypatch.setenv("CLAUDECODE", "1")
    items = {i.name: i for i in skills_items(doctor_ctx)}
    assert items["worker skills (agy)"].status == "unknown"
    assert "run ./devctl doctor from your own terminal" in items["worker skills (agy)"].detail
    assert fake_harness.calls("agy") == []
    assert items["reviewer skills (claude)"].status == "ok"


def test_without_the_worker_app_no_session_starts(
    doctor_ctx: DoctorContext, remote: Remote, fake_harness: FakeHarness
) -> None:
    fake_harness.install("agy", stdout=agy_skills([]))
    fake_harness.install("claude", stdout=claude_stream([]))
    items = skills_items(
        replace(doctor_ctx, project=replace(doctor_ctx.project, worker_app_id=None))
    )
    assert {i.status for i in items} == {"unknown"}
    assert all("worker_app_id" in i.detail for i in items)
    assert fake_harness.calls("agy") == fake_harness.calls("claude") == []
    assert len(worktrees(remote)) == 1
```

- [ ] **Step 3: Run it.** `uv run pytest tests/devctl/test_devctl_doctor_skills.py -q`. Expected: collection fails with `ImportError: cannot import name 'skills_items' from 'devctl.doctor'`.

- [ ] **Step 4: Implement.**
  - **`skills_args`** prefers a skill list the Harness prints itself (Step 1):
    - claude: `["-p", SKILLS_PROMPT, "--output-format", "stream-json", "--verbose", "--model", PROBE_MODELS["claude"]]`; the `init` event lists the skills.
    - codex: `["exec", "--json", "--model", PROBE_MODELS["codex"], "-c", 'model_reasoning_effort="low"', "--sandbox", "read-only", "--ephemeral", SKILLS_PROMPT]`; no event lists skills, so the reply does.
    - agy: `["-p", "/skills", "--output-format", "json", "--model", PROBE_MODELS["agy"]]`; `/skills` starts no agent turn.
  - **`parse_skills`** returns `SkillReport(None, f"{harness} did not finish within {PROBE_TIMEOUT_SECONDS:.0f} s, or its output was cut")` on a timeout or cut output. Otherwise it reads stdout, skipping lines that are not JSON objects:
    - claude: the `init` event's `skills` when it is a list of strings. Without it, the `result` event's text when `is_error` is false. Otherwise the error is the `result` text, or `claude exited <code> with no skill list`.
    - codex: the text of the last `item.completed` whose `item.type` is `agent_message`. Otherwise the error is `turn.failed`'s `error.message`, an `error` event's `message`, or `codex exited <code> with no reply`.
    - agy: stdout parsed as one JSON array whose items each have a string `name`. Otherwise the error is `error_line(stderr)`, or `agy printed no skill list (exit <code>)`.
    - A reply text gives one name per non-empty line: strip it, then remove one leading `- ` or `* `, surrounding backticks, and one leading `/` or `$`.
  - **`probe_worktree`** is dispatch's worktree code with a detached head. It resolves the root with `worktree_root(repo, setting)`, creates it with its parents, and runs `git worktree add --detach <root>/.doctor-skills-<secrets.token_hex(4)> <start>` through `process.run_process`. It yields the path. In `finally` it runs `git worktree remove --force <path>`, because a Session may have written files there. A failed add or removal raises `GitError` with the path and the first stderr line; the removal message adds `remove it with git worktree remove --force <path>`.
  - **`repository_skills(tree)`** lists the directories under `tree/.agents/skills` that hold a `SKILL.md`. A skill whose front matter, read with `yaml.safe_load`, sets `disable-model-invocation: true` is user-invoked: a Session may not list it, so it is not checked. Unreadable front matter counts as checked; plan 3's map rule 7 reports it.
  - **`skills_items(ctx)`** makes one item per Harness, in area `skills`, named like the sign-in items: `worker skills (agy)`, `reviewer skills (claude)`, or `worker and reviewer skills (<harness>)`.
    1. With no Worker or Reviewer Agent, it returns one missing item `skills`: `.rapid-ship/project.toml names no Worker or Reviewer Agent; run rs-setup`.
    2. Without `ctx.access` or `project.worker_app_id`, every item is unknown: `--skills fetches the default branch as the Worker App, as dispatch does; set repository and worker_app_id in .rapid-ship/project.toml`.
    3. It mints one Worker token and calls `default_head(ctx.root, access.remote, token)`, as `dispatch` does. A `DevctlError` or `GitHubError` makes every item unknown with its text.
    4. For each Harness: agy under `foreign_session` is unknown, with the sign-in item's detail, and a Harness that `shutil.which` cannot find is missing (`<harness> is not on PATH`). Otherwise, inside its own `probe_worktree(Repo.discover(ctx.root), project.worktree_root, start)`, so one Session cannot change what the next one sees, it reads `repository_skills` and runs `[executable, *skills_args(harness)]` through `process.run_process` with the worktree as `cwd` and `PROBE_TIMEOUT_SECONDS`.
    5. A report without names is unknown with its error. Otherwise `missing` is the checked skills the Session did not list, and `outside` is the listed names that are not repository skills, checked or user-invoked. The item is missing when `missing` is not empty, else ok. The detail joins these parts with `; `, each list sorted and joined with `, `: `missing: …` or `<n> repository skills seen`; `outside the repository: …` when there are any; `not checked, user-invoked: …` when there are any.
    6. A `GitError` from adding or removing a Harness's worktree makes that Harness's item unknown with the error's message, which names the path to remove by hand.
  - **CLI.** `run_doctor(ctx, *, skills=False)` prints `local_items`, `github_items`, then `skills_items` when `skills` is true. `register` adds `--skills` (`store_true`, help `also start one headless Session per Harness in a temporary worktree and compare the skills it loads; spends a little quota`), and `doctor_command` passes `skills=args.skills`. One parser per Harness and one helper per numbered step keep each function under complexity 10.

- [ ] **Step 5: Run it.** `uv run rapid-ship sync --in-place && uv run pytest tests/devctl -q`. Expected: all pass, 7 in `test_devctl_doctor_skills.py`. `test_doctor_makes_no_writes` still passes, so doctor without `--skills` starts no Session and adds no worktree. Then `./devctl doctor --help` lists `--skills`.

- [ ] **Step 6: Commit.**

```sh
git add rapid_ship/templates/common/tools/devctl tools/devctl .rapid-ship/kit.lock tests/devctl
git commit -m "feat: compare the skills each Harness loads with devctl doctor --skills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 11: `rapid-ship app`

**Files:**
- Create: `rapid_ship/github_app.py`
- Modify: `rapid_ship/cli.py` (the `app` command), `rapid_ship/AGENTS.md`, `.rapid-ship/exceptions.toml`
- Test: `tests/test_kit_app.py`; add a parity test to `tests/devctl/test_devctl_github_app.py`

**Interfaces:**
- Consumes: nothing from devctl. `rapid_ship` may not import it (plan 3 Task 18's forbidden contract), and plan 3 Task 1 moved `rapid_ship/process.py` into devctl, so this module has its own runner. devctl's `KEYCHAIN_SERVICE` and `APP_PERMISSIONS` appear in the parity test only.
- Produces:

```python
KEYCHAIN_SERVICE = {"worker": "rapid-ship/worker-app", "reviewer": "rapid-ship/reviewer-app"}
APP_PERMISSIONS = {  # the same table as devctl's, kept equal by a test
    "worker": {
        "contents": "write",
        "pull_requests": "write",
        "issues": "write",
        "metadata": "read",
    },
    "reviewer": {"pull_requests": "write", "contents": "read", "metadata": "read"},
}
MAX_SECURITY_LINE = 4095  # `security -i` reads each command into a 4096-byte buffer

Runner = Callable[[list[str], str | None], subprocess.CompletedProcess[str]]
OwnerGet = Callable[[str], object]


def run_command(
    argv: Sequence[str], input_text: str | None = None, *, timeout_seconds: float = 120.0
) -> subprocess.CompletedProcess[str]: ...
def gh_owner_get(path: str) -> object: ...  # gh api --method GET <path>, parsed JSON
def current_repository() -> str: ...  # gh repo view --json nameWithOwner --jq .nameWithOwner


@dataclass(frozen=True)
class StoredApp:
    app_id: int
    slug: str


@dataclass(frozen=True)
class CreatedApp:
    app: StoredApp
    private_key: bytes
    permissions: dict[str, str]


class AppSetupError(Exception): ...


class KeychainStore(Protocol):
    def find(self, service: str) -> StoredApp | None: ...
    def add(self, service: str, app: StoredApp, private_key: bytes) -> None: ...


class MacKeychainStore:
    def __init__(self, run: Runner = run_command) -> None: ...


def app_manifest(role: str, owner_login: str, redirect_url: str) -> dict[str, object]: ...
def install_url(slug: str, owner_id: int, repository_id: int) -> str: ...
def create_app(
    role: str,
    owner_login: str,
    *,
    open_browser: Callable[[str], object],
    api_url: str = "https://api.github.com",
    timeout_seconds: float = 900.0,
) -> CreatedApp: ...
def run_app(
    repository: str,
    *,
    store: KeychainStore,
    owner_get: OwnerGet,
    open_browser: Callable[[str], object],
    api_url: str = "https://api.github.com",
    timeout_seconds: float = 900.0,
) -> int: ...
```

- [ ] **Step 1: Write the failing tests.** Create `tests/test_kit_app.py`. The rapid-ship CLI cannot import devctl's test helpers, so this file keeps its own small fakes and module fixtures: `FakeStore` (`apps: dict[str, StoredApp]`, `keys: dict[str, bytes]`), `FakeSecurity` (a `Runner` that emulates `security` argv and stdin over a dict), `owner_get() -> OwnerGet` serving `repos/o/r`, `repos/org/r` and `user`, and `conversions() -> Iterator[FakeConversions]`, a server built on `http.server` that serves `POST /app-manifests/<code>/conversions`.

```python
"""Offline: rapid-ship app with a simulated browser, GitHub conversion endpoint and Keychain."""

import html
import json
import re
import subprocess
import webbrowser
from collections.abc import Callable
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from rapid_ship import cli
from rapid_ship.github_app import (
    AppSetupError,
    MacKeychainStore,
    OwnerGet,
    StoredApp,
    gh_owner_get,
    run_app,
)

Captured = list[tuple[str, dict[str, Any]]]


def http_get(url: str) -> tuple[int, str]:
    parts = urlsplit(url)
    connection = HTTPConnection(parts.netloc, timeout=5)
    connection.request("GET", f"{parts.path}?{parts.query}" if parts.query else parts.path)
    response = connection.getresponse()
    return response.status, response.read().decode()


def found(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    assert match is not None, pattern
    return match.group(1)


def github_browser(captured: Captured) -> Callable[[str], None]:
    """Act as the owner's browser and GitHub: read the form, reject a forged callback, then call back."""

    def open_browser(start_url: str) -> None:
        _, page = http_get(start_url)
        action = found(r'action="([^"]+)"', page)
        manifest: dict[str, Any] = json.loads(
            html.unescape(found(r'name="manifest" value="([^"]+)"', page))
        )
        captured.append((action, manifest))
        callback = manifest["redirect_url"]
        state = html.unescape(action).split("state=", 1)[1]
        assert http_get(f"{callback}?code=c0de&state=wrong")[0] == 400
        assert http_get(f"{callback}?code={manifest['name']}&state={state}")[0] == 200

    return open_browser


def test_cli_app_calls_run_app_with_the_real_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def record(repository: str, **kwargs: object) -> int:
        calls.append((repository, kwargs))
        return 0

    monkeypatch.setattr(cli, "run_app", record)
    monkeypatch.chdir(tmp_path)  # app reads no Kit file, so it needs no work tree
    assert cli.main(["app", "--repository", "o/r"]) == 0
    [(repository, kwargs)] = calls
    assert repository == "o/r"
    assert isinstance(kwargs["store"], MacKeychainStore)
    assert kwargs["owner_get"] is gh_owner_get
    assert kwargs["open_browser"] is webbrowser.open


def test_creates_both_apps_and_prints_install_urls(
    conversions: FakeConversions,
    store: FakeStore,
    owner_get: OwnerGet,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    captured: Captured = []
    assert (
        run_app(
            "o/r",
            store=store,
            owner_get=owner_get,
            open_browser=github_browser(captured),
            api_url=conversions.url,
            timeout_seconds=10,
        )
        == 0
    )
    (action, worker), (_, reviewer) = captured
    assert action.startswith("https://github.com/settings/apps/new?state=")
    assert (worker["public"], worker["default_events"], "hook_attributes" in worker) == (
        False,
        [],
        False,
    )
    assert worker["default_permissions"] == {
        "contents": "write",
        "pull_requests": "write",
        "issues": "write",
        "metadata": "read",
    }
    assert reviewer["default_permissions"] == {
        "pull_requests": "write",
        "contents": "read",
        "metadata": "read",
    }
    assert worker["redirect_url"].startswith("http://127.0.0.1:")
    assert len(worker["name"]) <= 34
    assert store.keys["rapid-ship/worker-app"] == conversions.pem_for(worker["name"])
    out = capsys.readouterr().out
    assert "Worker App: ID 11" in out
    assert "Reviewer App: ID 12" in out
    assert "/installations/new/permissions?suggested_target_id=1&repository_ids[]=2" in out
    assert "BEGIN" not in out
    assert "client-secret" not in out
    assert not [p for p in tmp_path.rglob("*") if p.is_file() and b"BEGIN" in p.read_bytes()]


def test_existing_apps_are_only_printed(
    store: FakeStore, owner_get: OwnerGet, capsys: pytest.CaptureFixture[str]
) -> None:
    store.apps = {
        "rapid-ship/worker-app": StoredApp(11, "o-rs-worker"),
        "rapid-ship/reviewer-app": StoredApp(12, "o-rs-reviewer"),
    }
    opened: list[str] = []
    assert run_app("o/r", store=store, owner_get=owner_get, open_browser=opened.append) == 0
    assert opened == []
    assert (
        "https://github.com/apps/o-rs-worker/installations/new/permissions"
        in capsys.readouterr().out
    )


def test_organization_repositories_are_refused(store: FakeStore, owner_get: OwnerGet) -> None:
    opened: list[str] = []
    assert run_app("org/r", store=store, owner_get=owner_get, open_browser=opened.append) == 1
    assert (opened, store.keys) == ([], {})


def test_permission_mismatch_keeps_the_key_and_exits_1(
    conversions: FakeConversions, store: FakeStore, owner_get: OwnerGet
) -> None:
    conversions.permissions = {"contents": "write", "metadata": "read"}
    assert (
        run_app(
            "o/r",
            store=store,
            owner_get=owner_get,
            open_browser=github_browser([]),
            api_url=conversions.url,
            timeout_seconds=10,
        )
        == 1
    )
    assert "rapid-ship/worker-app" in store.keys


def test_no_callback_times_out_with_exit_2(store: FakeStore, owner_get: OwnerGet) -> None:
    assert (
        run_app(
            "o/r",
            store=store,
            owner_get=owner_get,
            open_browser=lambda url: None,
            timeout_seconds=0.2,
        )
        == 2
    )


def test_keychain_add_passes_the_key_on_stdin_only() -> None:
    security = FakeSecurity()
    pem = b"-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----\n"
    MacKeychainStore(run=security).add("rapid-ship/worker-app", StoredApp(11, "o-rs-worker"), pem)
    assert ["security", "-i"] in security.argvs
    assert all(pem.hex() not in arg for argv in security.argvs for arg in argv)
    assert MacKeychainStore(run=security).find("rapid-ship/worker-app") == StoredApp(
        11, "o-rs-worker"
    )


def test_keychain_add_refuses_a_line_security_would_cut() -> None:
    security = FakeSecurity()
    with pytest.raises(AppSetupError, match="too long"):
        MacKeychainStore(run=security).add(
            "rapid-ship/worker-app", StoredApp(11, "s"), b"-----BEGIN " + b"A" * 2100
        )
    assert security.argvs == []
```

Define `FakeStore`, `FakeSecurity`, `FakeConversions` and their fixtures between the imports and the first test. `FakeSecurity.__call__(self, argv: list[str], input_text: str | None) -> subprocess.CompletedProcess[str]` records `argvs: list[list[str]]`. On `["security", "-i"]` it splits the stdin line and stores the `-a`, `-j` and `-X` values under `-s`. On `find-generic-password -s <service>` it prints `    "acct"<blob>="<id>"` and `    "icmt"<blob>="<slug>"`, the format of `keychain_utilities.c` `print_keychain_item_attributes`. With `-w` it prints the hex secret. A missing item exits 44. The conversion fake returns `{"id": 11|12, "slug": <name>, "pem": "-----BEGIN RSA PRIVATE KEY-----\n<name>\n-----END RSA PRIVATE KEY-----\n", "client_secret": "client-secret", "webhook_secret": None, "permissions": <requested or overridden>, "html_url": "https://github.com/apps/<name>"}`. The code in the callback is the App name, so the fake knows which App it creates; it learns the requested permissions from a table keyed by the `-rs-worker` or `-rs-reviewer` suffix. `pem_for(name: str) -> bytes` returns that PEM. rapid-ship never parses the key, so a PEM-shaped text is enough here. In `tests/devctl/test_devctl_github_app.py` add:

```python
def test_rapid_ship_and_devctl_agree_on_services_and_permissions() -> None:
    from devctl.github import app
    from rapid_ship import github_app

    assert github_app.KEYCHAIN_SERVICE == app.KEYCHAIN_SERVICE
    assert github_app.APP_PERMISSIONS == app.APP_PERMISSIONS
```

- [ ] **Step 2: Run it.** `uv run pytest tests/test_kit_app.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'rapid_ship.github_app'`.

- [ ] **Step 3: Implement `rapid_ship/github_app.py`.**
  - `run_command` is the module's one process call. Ruff 0.17.0 reports only S603 here, because `argv` is a parameter; adding S607 to the `noqa` would fail RUF100 (Checked facts).

```python
def run_command(
    argv: Sequence[str], input_text: str | None = None, *, timeout_seconds: float = 120.0
) -> subprocess.CompletedProcess[str]:
    """Run security or gh with fixed arguments and no shell. rapid_ship cannot use devctl's runner."""
    try:
        return subprocess.run(  # noqa: S603  # rs-exception: EX-<next>
            list(argv),
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AppSetupError(f"could not run {argv[0]}: {type(error).__name__}") from None
```

`EX-<next>` is one more than the highest ID in `.rapid-ship/exceptions.toml` (`grep -o 'EX-[0-9]*' .rapid-ship/exceptions.toml | sort -t- -k2 -n | tail -1`); write the actual ID on the line. Add the entry:

```toml
[[exception]]
id = "EX-<next>"
path = "rapid_ship/github_app.py"
rule = "S603"
reason = "rapid-ship app runs security and gh with fixed arguments and no shell; rapid_ship may not import devctl's runner"
remove_when = "Ruff stops reporting S603 for list arguments without a shell"
```

`gh_owner_get(path)` runs `["gh", "api", "--method", "GET", path]` with a 60 s timeout and parses stdout as JSON; a non-zero exit raises `AppSetupError` with stderr's first line. `current_repository()` runs `["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]` and returns the stripped output, or raises `AppSetupError`. Neither ever receives a key.
  - `app_manifest(role, owner_login, redirect_url)` returns `name` (`f"{owner_login}-rs-{role}"`, with the login shortened so the name fits 34 characters; the owner can edit it on GitHub's page), `url` `https://github.com/proxy-hatch/rapid-ship`, `description`, `public: False`, `redirect_url`, `default_permissions: APP_PERMISSIONS[role]` and `default_events: []`. It has no `hook_attributes`, so the App has no webhook; Task 12 confirms GitHub accepts this.
  - `create_app` starts a `ThreadingHTTPServer` on `("127.0.0.1", 0)` with a fresh `state = secrets.token_urlsafe(32)`. `GET /start` returns a page with `<form method="post" action="https://github.com/settings/apps/new?state=<state>">`, a hidden `manifest` input holding `html.escape(json.dumps(manifest), quote=True)`, a submit button, and a script that submits the form. `GET /callback` accepts only when `hmac.compare_digest(state, expected)` holds and `code` matches `[A-Za-z0-9_-]{1,128}`. It then queues the code and answers `The App was created. Return to the terminal.`; otherwise it answers 400. The handler's `log_message` is silent, so a code never reaches the terminal. The command prints the start URL, calls `open_browser`, and waits for a code up to `timeout_seconds`; no code raises `AppSetupError("no App was created within <n> minutes")`. It shuts the server down, then POSTs `/app-manifests/<code>/conversions` with `http.client`, without authentication, as Probot does. It requires an integer `id`, a `slug` matching `[a-z0-9-]+`, a `pem` starting `-----BEGIN ` and a `permissions` object. `client_secret` and `webhook_secret` are dropped and never printed or stored.
  - `MacKeychainStore` calls `self.run(argv, input_text)` for every `security` command. `find` runs `security find-generic-password -s <service>` without `-w`, so no secret is read. Exit 44 returns `None`. It parses `"acct"<blob>="<digits>"` and `"icmt"<blob>="<slug>"` and raises `AppSetupError(f"Keychain item {service} was not written by rapid-ship app")` when either is absent. `add` builds `add-generic-password -s <service> -a <app id> -j <slug> -X <key hex>\n`. It raises `AppSetupError("the private key is too long for security -i; …")` before running anything when that line exceeds `MAX_SECURITY_LINE`. It runs `["security", "-i"]` with the line as `input_text`, never `-w <key>` in argv, and without `-U`, so an existing item is never overwritten. Without `-T`, the item trusts `/usr/bin/security`, so devctl reads it with no dialog, and so can any process the owner runs (Global Constraints, Keys). Then it reads the item back with `find-generic-password -s <service> -w`, decodes hex output as devctl does, and raises unless both the secret and `find()` match what was written.
  - `run_app` reads `repos/<repository>` and `user` with `owner_get`. It refuses (exit 1) when the owner's `type` is not `User` or its login differs from the signed-in user: a private App installs only on its owner's account. For each role it reuses `store.find(service)`, or creates the App and calls `store.add` before anything else, because GitHub shows the key only once. It prints `Worker App: ID <id> (<slug>)` and `  Install on <repository>: <install_url(slug, owner id, repository id)>`, then `Record both IDs in .rapid-ship/project.toml under [github]. ./devctl doctor confirms each installation.` A created App whose permissions differ from `APP_PERMISSIONS[role]` leaves its key stored, prints `fix the permissions at https://github.com/settings/apps/<slug>/permissions` and makes the exit 1. `AppSetupError` and conversion failures print their message and exit 2. If the Keychain write fails after creation, the message tells the owner to delete the App at `https://github.com/settings/apps/<slug>/advanced` and rerun, because the key cannot be recovered.
  - `install_url` returns `f"https://github.com/apps/{slug}/installations/new/permissions?suggested_target_id={owner_id}&repository_ids[]={repository_id}"`.
  - In `rapid_ship/cli.py`, add the `app [--repository OWNER/NAME]` subparser and an explicit `if args.command == "app":` branch in `main`. Plan 2's `main` ends with an unconditional `return _sync(root, in_place=args.in_place)`, so without the branch `app` falls through to `_sync` and crashes with `AttributeError: 'Namespace' object has no attribute 'in_place'`. Put the branch before `work_tree_root`: `app` reads no Kit file, so `--repository` works outside a work tree. The branch calls `run_app` with `args.repository`, or `current_repository()` when it is absent, and `MacKeychainStore()`, `gh_owner_get` and `webbrowser.open`. `cli.py` imports `run_app` by name, so the CLI test can replace it. An `AppSetupError` from `current_repository()` writes `rapid-ship: <message>` to stderr and returns 2. Output goes through `sys.stdout.write`. `cli.py` starts no process itself.

- [ ] **Step 4: Run it.** `uv run pytest tests/test_kit_app.py tests/devctl/test_devctl_github_app.py -q`. Expected: all pass (8 and 10). Then `uv run rapid-ship app --help` shows `--repository`, and `./devctl check --tier fast` passes its lint and exceptions steps, so the new entry matches the marker.

- [ ] **Step 5: Commit.**

```sh
git add rapid_ship/github_app.py rapid_ship/cli.py rapid_ship/AGENTS.md .rapid-ship/exceptions.toml tests/test_kit_app.py tests/devctl/test_devctl_github_app.py
git commit -m "feat: create and install the Worker and Reviewer Apps with rapid-ship app" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 12: Live trials

Every step here changes outside state or uses the owner's accounts, so each is an Owner step. Record results in `docs/trials/YYYY-MM-DD-github-apps.md`, named with the trial date. Record versions (macOS, git, gh, this branch's commit), commands, results and limits. The website publishes trial reports: never record a token, a private key, a client secret, an installation token's value or a personal email address. Token length may be recorded.

**Files:**
- Create: `docs/trials/YYYY-MM-DD-github-apps.md`
- Modify: `docs/trials/AGENTS.md` (link the new report), `tests/devctl/fixtures/github/ruleset.json` (replace with the read-back)

- [ ] **Step 1: Owner step: confirm the trial's outside changes.** The owner confirms, in chat, each of these: creating two private GitHub Apps on their personal account (they become the owner's real Worker and Reviewer Apps); creating a public scratch repository `<owner>/rs-trial`; installing both Apps on it and on one second repository the owner names; applying a ruleset, branch deletion after merge and the fork approval policy to `rs-trial`; opening PRs and reviews on `rs-trial`; and merging the owner's own PRs there with the admin bypass, including one that adds two trial skills (Step 14). A public repository is needed because rulesets returned 403 on the owner's private repositories (Checked facts).

- [ ] **Step 2: Owner step: prepare `rs-trial`.** `gh repo create <owner>/rs-trial --public --add-readme --clone`. In it, run `uvx --from <this worktree> rapid-ship init --stack neutral` and commit the Kit to `main` directly; no ruleset exists yet.

- [ ] **Step 3: Owner step: create the Apps.** In `rs-trial`, run `uvx --from <this worktree> rapid-ship app`. Complete both browser pages. Record: both App IDs and slugs; whether GitHub accepted the manifest without `hook_attributes` and whether the App's settings page shows the webhook inactive; whether the conversion worked without authentication; whether `security` raised a Keychain dialog while storing each key; and the printed lines. If GitHub rejects the manifest, stop and record the error; the fix is a change to `app_manifest` with a test.

- [ ] **Step 4: Owner step: install on `rs-trial`.** Open both printed install URLs and install each App on `rs-trial` only. Fill `.rapid-ship/project.toml` `[github]` with the repository and both IDs, and `[agents]` with the exact Worker and Reviewer Harness and model. Commit to `main`.

- [ ] **Step 5: Check the installation and the key access.** Run `./devctl doctor` in `rs-trial`. Expected: `Worker App installation`, `Reviewer App installation`, `Worker App key` and `Reviewer App key` are ok, with no macOS dialog, because the items trust `/usr/bin/security` (Checked facts). Record every line and whether a dialog appeared. Then, from a new terminal that has never run devctl, run `security find-generic-password -s rapid-ship/worker-app -w >/dev/null; echo $?` and record the exit code and whether a dialog appeared. Exit 0 with no dialog confirms that any process the owner runs, a Worker's shell included, can read the key; record that under the report's limits as a Flight prerequisite.

- [ ] **Step 6: Owner step: install on a second repository.** In any clone, run `uvx --from <this worktree> rapid-ship app --repository <owner>/<second>`. Expected: no browser opens, and both IDs and install URLs print. Install both Apps there. Prove a token mints for it without printing the token:

```sh
uv run --project tools/devctl python -c "from devctl.github.app import installation_token as t; t('worker', '<owner>/<second>', <worker id>); print('minted')"
```

Record whether the preselected install URL added the repository to the existing installation.

- [ ] **Step 7: Owner step: apply the repository settings to `rs-trial`.**

```sh
gh api --method PATCH repos/<owner>/rs-trial -F delete_branch_on_merge=true
gh api --method PUT repos/<owner>/rs-trial/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors
```

- [ ] **Step 8: Owner step: apply the ruleset.** Save this as `ruleset.json` outside the repository and run `gh api --method POST repos/<owner>/rs-trial/rulesets --input ruleset.json`. It is the content plan 5 writes to `rs-setup/ruleset.json` (plan 5 Task 7), so the trial reads back the ruleset that `rs-setup` will apply. `dismiss_stale_reviews_on_push` and `require_last_push_approval` are `true` (spec section 8, step 3).

```json
{
  "name": "rapid-ship",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "pull_request"
    }
  ],
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "require_code_owner_review": true,
        "dismiss_stale_reviews_on_push": true,
        "require_last_push_approval": true,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          {"context": "devctl check", "integration_id": 15368}
        ]
      }
    }
  ]
}
```

- [ ] **Step 9: Read it back.** Run `gh api repos/<owner>/rs-trial/rulesets/<id>` and `./devctl doctor`. Expected: `ruleset`, `delete branch on merge` and `fork PR workflow approval` are ok, and the read-back shows `dismiss_stale_reviews_on_push` and `require_last_push_approval` as `true`. Record whether `actor_id` 5 is the admin role, as the GitHub UI shows it. Copy the read-back, with `node_id`, `_links`, `created_at` and `updated_at` removed, over `tests/devctl/fixtures/github/ruleset.json`. Then run `uv run pytest tests/devctl/test_devctl_doctor_github.py -q`; expected: all pass.

- [ ] **Step 10: Owner step: does a Reviewer App approval count?** `main` has no active CODEOWNERS line yet. Run `./devctl dispatch TRIAL-1`. Commit a one-line README change in the printed worktree. Write a body with an `## Evidence` section and a `Not covered:` line, then run `./devctl pr --title "Trial change" --body <file>`. Record the PR author (`gh pr view <n> --json author`). Write an approve verdict for the PR head with the Reviewer Agent's exact Harness and model, and run `./devctl review <n> --verdict <file>`. Record the review author and `gh pr view <n> --json reviewDecision,mergeStateStatus`. Then run the same `devctl review` again; expected exit 1, "already has a verdict". Push another commit with `./devctl pr`, and rerun with the old verdict; expected exit 1, "stale head". Record `gh pr view <n> --json reviews,reviewDecision`: with `dismiss_stale_reviews_on_push` set, the expected result is that the earlier approval no longer counts.

- [ ] **Step 11: Owner step: with the owner as code owner.** Through the owner's own PR, merged with the admin bypass, put `* @<owner>` in `.github/CODEOWNERS` on `main`. Record whether the bypass merge worked with no approval. Have the Reviewer App approve the open trial PR's current head and record `reviewDecision` again. Expected under the spec's design: the Reviewer App's approval no longer satisfies the rule, because code-owner review needs the owner. Record what GitHub actually reports.

- [ ] **Step 12: Owner step: does a Reviewer App change request count?** Commit another one-line change in the trial worktree and push it with `./devctl pr`, so the head has no Reviewer verdict. Write a `changes_requested` verdict for that head with one blocking finding, and run `./devctl review <n> --verdict <file>`. Record the review's state as GitHub shows it, and `gh pr view <n> --json reviewDecision,mergeStateStatus`. Expected under the spec's design: `CHANGES_REQUESTED` and a blocked merge. The Reviewer App has only Contents read, and GitHub may not count reviews from actors without write access; record what GitHub actually reports.

- [ ] **Step 13: Owner step: a workflow change on `main`.** Through the owner's own PR, merged with the admin bypass, change one comment line in `.github/workflows/devctl-check.yml` on `main`. In the trial worktree, run `git fetch origin main && git merge origin/main`, then `./devctl pr`. Record GitHub's response and devctl's output. Expected: GitHub rejects the Worker App's push because the merge brings in a workflow change (Checked facts), and devctl prints the refusal that sends the Lead to the owner. If GitHub accepts the push, record that. The hint stays: an App push that adds or edits a workflow file directly is still refused (Checked facts).

- [ ] **Step 14: Owner step: probe the Harnesses live.** Work from your own terminal, not from a Claude Code, Codex or agy session. `rs-trial`'s `main` holds no skills yet, because the Kit skills arrive in plan 5, and `--skills` reads the default branch as `dispatch` does. So first add two project skills with their `.claude/skills` links, the second one user-invoked, through the owner's own PR, merged with the admin bypass:

```sh
git fetch origin
git switch -c trial-skills origin/main
mkdir -p .agents/skills/trial-notes .agents/skills/trial-release .claude/skills
printf -- '---\nname: trial-notes\ndescription: Notes on the rs-trial repository. Use before editing README.md.\n---\n\nKeep README.md to one paragraph.\n' > .agents/skills/trial-notes/SKILL.md
printf -- '---\nname: trial-release\ndescription: Release steps for the rs-trial repository.\ndisable-model-invocation: true\n---\n\nRun only when the owner asks.\n' > .agents/skills/trial-release/SKILL.md
ln -s ../../.agents/skills/trial-notes .claude/skills/trial-notes
ln -s ../../.agents/skills/trial-release .claude/skills/trial-release
./devctl check --tier fast; echo "exit $?"   # stop and fix the files unless this exits 0
git add .agents/skills .claude/skills
git commit -m "Add two trial skills"
git push --set-upstream origin trial-skills
printf -- '## Evidence\n\n- `./devctl check --tier fast`: exit 0\n\nNot covered: what each Harness loads; doctor --skills checks it next.\n' > /tmp/trial-skills-pr.md
gh pr create --base main --head trial-skills --title "Add two trial skills" --body-file /tmp/trial-skills-pr.md
gh pr merge trial-skills --admin --merge --delete-branch
git switch main && git pull --ff-only
```

Expected: `./devctl check --tier fast` exits 0, because map rule 7 accepts both skills and their links. Record the merged commit. Then edit `[agents]` in `.rapid-ship/project.toml` without committing, so the Worker uses agy and the Reviewer uses Claude Code. Run `./devctl doctor --skills; echo "exit $?"`, then `git worktree list`. Expected: `worker sign-in (agy)` is ok. Each skills item is ok, reports `trial-notes` as seen (`1 repository skills seen`) and `trial-release` as `not checked, user-invoked: trial-release`, never lists `trial-release` under `outside the repository`, and lists outside skills for information. Record whether each Harness listed `trial-release` anyway. No `.doctor-skills-` worktree remains. Repeat with the Worker on Codex. A 502 or 503 from Google's eligibility check makes an agy item unknown; rerun, and record both results. Record every sign-in and skills line, the exit codes and the outside skills each Harness listed. Then run `git checkout .rapid-ship/project.toml`.

- [ ] **Step 15: Owner step: clean up.** Run `./devctl dispatch --clean` after closing the trial PR, and record the gate log lines it added. The owner decides whether to delete `rs-trial`; the Apps stay.

- [ ] **Step 16: Write the report and commit.** The report lists each fact above with its observed result and every deviation from Checked facts. Mark which results came from live calls. Link it from `docs/trials/AGENTS.md`.

```sh
git add docs/trials tests/devctl/fixtures/github/ruleset.json
git commit -m "docs: record the GitHub Apps and ruleset trial" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 13: Verification, guides and docs

**Files:**
- Modify: every `AGENTS.md` whose directory gained files: `rapid_ship/AGENTS.md` (`github_app.py`), `tests/AGENTS.md` (`test_kit_app.py`; in `devctl/`, the `test_devctl_*` GitHub tests, `github_fakes.py`, `github_fixtures.py` and `fixtures/github/`), `docs/trials/AGENTS.md` (Task 12), and the guides nearest `devctl/github/` and `devctl/harness.py` in the template and its vendored copy, as plan 3 laid them out
- Modify: root `AGENTS.md` (Commands: `./devctl doctor`), `ARCHITECTURE.md` (devctl's GitHub commands and the token path)
- Modify: this plan's Verification record

- [ ] **Step 1: Update the guides.** Each guide gets one line or table row per new file, saying when to open it: for example, "`devctl/github/app.py`: App keys, installation tokens and token-bearing git; read before any change that touches a token", and "`devctl/harness.py`: the headless Sessions doctor starts, each Harness's cheapest model and output parsers; read before changing a probe". `ARCHITECTURE.md` gets one paragraph: the four commands, which App each uses, that the token stays in memory and reaches git through askpass, that doctor writes nothing except the worktrees `--skills` adds and removes, and that doctor starts headless Sessions only to prove agy's sign-in and, with `--skills`, the skills each Harness loads. Root `AGENTS.md` lists `./devctl doctor` under Commands. Run `uv run rapid-ship sync --in-place` after template guide edits.

- [ ] **Step 2: Run the full verification.**

```sh
./devctl check --tier full
uv run rapid-ship status --strict
uv run pytest tests/devctl tests/test_kit_app.py -q
./devctl doctor; echo "doctor exit $?"
./devctl doctor --help && ./devctl dispatch --help && ./devctl pr --help && ./devctl review --help && uv run rapid-ship app --help
npm --prefix website ci --no-audit --no-fund
npm --prefix website run build
```

Expected:
- `./devctl check --tier full` exits 0, every step passed or not applicable. The map step confirms every new directory has a reachable guide. The exceptions step passes with Task 11's `rapid_ship/github_app.py` entry as the only new one. Lint and types pass over `tests/`, so every new test is annotated and no command uses `print`.
- `rapid-ship status --strict` exits 0: the vendored copy matches the templates.
- pytest: all pass, none skipped.
- `./devctl doctor` on this repository: record every line and the exit code. Until this repository gets the Apps and the ruleset, expect missing items for at least `ruleset` (none exists), `delete branch on merge` (`false` on 2026-10-14) and `fork PR workflow approval` (`first_time_contributors` on 2026-10-14). Those are this repository's settings, not failures of this plan. Plan 5 Task 12 applies them here as an Owner step, after this plan merges. Record the gap under Remaining limits; until it closes, `devctl check` is not a required status check on this repository. `gitleaks` is ok only with 8.30.1 installed. `tools/devctl exclusions` is expected ok: this repository tracks `rapid_ship/templates/kit.toml`, so doctor checks only its uv workspace, and the root `pyproject.toml` declared none on 2026-10-14. If `project.toml` names agy, run doctor from your own terminal; inside another coding session the agy item is unknown by design and says so.
- Each `--help` exits 0, and doctor's lists `--skills`.
- The site build exits 0 with no broken links.

- [ ] **Step 3: Check this PR's body against the evidence step.** Write the PR description to a file outside the repository, for example `/tmp/github-commands-pr.md`. It has an `## Evidence` section listing each Step 2 command with its result and the Task 12 trial report, a sentence naming Task 11's new exception entry and why it exists, and a line starting `Not covered:` that names what stayed offline or unproven: organisation repositories, Flight, the Keychain access limit, the ruleset this repository still lacks, and Harness output beyond the versions Task 8 Step 1 and Task 10 Step 1 recorded. Then run:

```sh
./devctl check --tier full --pr-body /tmp/github-commands-pr.md; echo "exit $?"
```

Expected: exit 0 and evidence passed.

- [ ] **Step 4: Owner step: push and open the PR.** The owner confirms, then the branch is pushed and the PR opened under the owner's login:

```sh
git push --set-upstream origin github-commands
gh pr create --base main --head github-commands --title "feat: add rapid-ship app and devctl's GitHub commands" --body-file /tmp/github-commands-pr.md
```

Confirm `gh pr checks <n>` shows the `devctl check` job passing. Record the PR URL and the run URL below.

- [ ] **Step 5: Fill in the Verification record** below with the actual output, then commit. Pushing it is an Owner step: the owner confirms, then `git push` updates the PR.

```sh
git add AGENTS.md ARCHITECTURE.md rapid_ship tools/devctl .rapid-ship/kit.lock tests docs
git commit -m "docs: map devctl's GitHub commands and record verification" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Verification record

Fill in after Task 13. Record actual output, not expectations. Mark live, offline and skipped results separately; a skipped or blocked step is not a pass.

- agy listing, probe reply and exit code, and the final `AGY_PROBE_ARGS` (Task 8 Step 1):
- `CODEX_` variable names in a Codex session, the variable names only an agy session sets, whether `agy -p hi` answered inside that session (exit code and any `error:` line), and the final `FOREIGN_SESSION_VARIABLES` with the reason for each change (Task 8 Step 1):
- Headless skill lists per Harness: exit codes, event types and field names, skill names, and the final `PROBE_MODELS` (Task 10 Step 1):
- First line of `gitleaks version`, and whether the parser accepted it (Task 8 Step 1):
- Exception entry added for `rapid_ship/github_app.py` (ID, Task 11):
- `./devctl check --tier full`:
- `uv run rapid-ship status --strict`:
- pytest (`tests/devctl`, `tests/test_kit_app.py`):
- `./devctl doctor` on this repository (lines and exit code):
- Docs site build:
- Live trial report and its deviations from Checked facts (Task 12):
- Evidence step with this PR's body (Step 3):
- PR URL and `devctl check` run (Step 4):
- Remaining limits (include at least: Walk does not protect App keys from Workers, because any process the owner runs can read them through `security` (a Flight prerequisite; `add-generic-password -T ""` would make every read ask, untested); this repository lacks the ruleset, branch deletion and fork approval until plan 5 Task 12 applies them as an Owner step; and doctor never starts agy from inside another coding session, so the owner runs it from their own terminal for agy's items; if Task 8 Step 1 found no variable that marks an agy session, doctor cannot detect one):
