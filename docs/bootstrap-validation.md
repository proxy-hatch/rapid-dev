# Bootstrap validation — 2026-10-10

The reviewed implementation is on `codex/bootstrap-framework` in [draft PR #1](https://github.com/proxy-hatch/rapid-ship/pull/1). The tested implementation commit is `21762cd`; subsequent documentation records these results. This is a supervised bootstrap candidate, with no production release or autonomous capability grant.

| Check | Observed result |
| --- | --- |
| Full local suite | 398 passed on macOS / Python 3.13.12. |
| Static checks | Ruff passed; strict mypy passed for 15 source files. |
| Build | Source distribution and wheel built successfully. |
| Linux CI | Tests, Ruff, mypy and build passed on Python 3.12 and 3.13 in [run 38041572063](https://github.com/proxy-hatch/rapid-ship/actions/runs/38041572063). |
| Clean wheel install | Installed into a fresh external Python 3.13.12 environment; imports verified from site-packages, with no editable source or PYTHONPATH. |
| Installed onboarding | Version/help, packaged skill, all 11 applicable native interview answers, idempotent initialization and read-only doctor passed. Doctor preserved file contents, modes and modification times. |
| Installed feature scaffold | Generated test passed; overwrite guard passed. |
| Installed workflow | Init → interview → doctor → decompose → run → sealed evidence passed with a simulated runner, actual Git/native subprocesses and no model credentials. Evidence remained `live: false`; autonomy remained disabled. |
| Docker provider | Two isolated containers used internal port 8000 simultaneously and returned PONG; both were cleaned. Details in [environment compatibility](environments.md). |

The tested wheel is `trust_first_engineering-0.1.0-py3-none-any.whl`, 58,469 bytes, SHA256 `cb08f081299bc24e425bd568b2ad6e15df4c6d09e9532b67558dfa56f811494d`. This identifies the local tested artifact; it is not a published production release.

Independent reviews covered contracts, store fencing, environment ownership/recovery, runners, onboarding, evidence, policy/trials, broker operations and CLI boundaries. Reported defects were reproduced and fixed before acceptance. Regressions cover uncertain preparation retaining reservations, ownership checks in a fresh Git clone, changed PR responses, retained failed-check artifacts, merge/release transition recovery without repeated effects, and structured database/missing-adapter errors. Component changes were integrated through PRs #2–#7; final controller/broker/CLI integration also received independent review.

## Remaining rollout gates

- Human live agent/model compatibility trials have not run. Complete three representative changes plus recovery/adversarial trials for each capability being promoted.
- No trusted external authority adapter or controller GitHub App is installed. CLI mutation and promotion commands report blockers; the gated library APIs require trusted host wiring.
- During the initial validation, GitHub's branch-protection API returned HTTP 403 for the private repository. The user subsequently requested public visibility and the rapid-dev rename. No controller GitHub App or app-bound required check is installed; ordinary CI does not replace it.
- OpenHands execution and AWS provisioning require separately implemented, registered adapters. Unknown providers and resources block dispatch. Worktrees currently pair with explicit native execution only.
- Native and simulated runs supply no unattended authority. The Docker smoke test covers only its recorded image and provider composition, not coding-agent authentication or arbitrary cloud environments.

The draft PR remains draft pending the human live agent/model trial. Public visibility changes how the project is shared; it does not grant unattended delivery. No account plan, production infrastructure or installed controller was changed to bypass these gates.

## rapid-dev follow-up

At this checkpoint the project and package were named `rapid-dev`; the command remains `devctl`. The public landing page is on `main`, and implementation remains in draft PR #1.

- 521 local tests passed, along with Ruff, strict mypy for 18 source files, skill validation, and distribution builds.
- New projects use a language-neutral profile and one task at a time. Writing rules reach generated instructions and worker/reviewer prompts.
- Metrics include controller measurements, GitHub PR/review and Actions collection, and imports for other systems. A live read-only sync collected eight PRs and four CI attempts; human review time stayed unknown.
- Independent review covered missing-data handling, historical coverage, PR revisions, CI retries, cross-repository links, and compatibility with older saved results.
- Testing exposed a macOS process-group teardown race. The fix confirms the group has disappeared before accepting a transient permission error; real denials still fail. It passed 600 stress repetitions and 13 process tests.

The renamed wheel is `rapid_dev-0.1.0-py3-none-any.whl`, SHA256 `ec3b6332b5aa8e9960d5aa4c66babb8464d9635271b7fdbb1ce91c80b30ed488`. Clean installation checks use an external Python 3.13 environment. This remains a preview, not a production release or a grant of unattended delivery.

## Harness and planning follow-up — 2026-10-11

- 563 local tests passed, plus Ruff, strict mypy for 18 source files, skill validation and distribution builds.
- Antigravity's worker adapter was tested with simulated streams and real subprocess transport. Coverage includes model/session mismatches, permission denials, unfinished steps, cancellation and configured deadlines. Docker-only worker restrictions and simulated-run labeling remain enforced.
- A task can override its model. Switching harness requires an explicit model; absent overrides preserve older saved task serialization.
- Independent review caught and verified the fix for Antigravity's five-minute default overriding the task timeout. A planning trial caught the need to exclude unresolved design tasks from registration; the skill now records those blockers and continues independent work.
- Cleaned artwork was visually reviewed and published through [PR #9](https://github.com/proxy-hatch/rapid-ship/pull/9). The final logo has an opaque off-white background.

No live Antigravity/Gemini run was performed. The local `agy` launcher points to a missing app; an approved Docker environment still needs the standalone CLI and model authentication. Named agent profiles, custom endpoints, Linear sync and native stack automation remain future integrations. See [agent support](agents.md) and [task slicing](task-slicing.md).
