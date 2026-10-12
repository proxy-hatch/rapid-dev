# Bootstrap validation — 2026-10-10

This records historical validation checkpoints, starting with implementation commit `21762cd` in [PR #1](https://github.com/proxy-hatch/rapid-ship/pull/1). The current preview entry point is `main`; see the [hello walkthrough](getting-started.md). Merging preview code does not grant unattended delivery.

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

At this checkpoint, the integration PR was held as a draft pending a human live agent/model trial. Preview code can now merge independently of capability qualification. Public visibility changes how the project is shared; it does not grant unattended delivery. No account plan, production infrastructure or installed controller was changed to bypass these gates.

## rapid-dev follow-up

At this checkpoint the project and package were named `rapid-dev`; the command remains `devctl`. At that time, the public landing page was on `main`, while implementation remained in draft PR #1.

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

No live Antigravity/Gemini run was performed. The local `agy` launcher points to a missing app; an approved Docker environment still needs the standalone CLI and model authentication. Named agent profiles, custom endpoints, Linear sync and native stack automation remain future integrations. See [agent support](model-harnesses.md) and [task slicing](task-slicing.md).

## rapid-ship rename — 2026-10-11

The public repository, distribution and bundled skill are named `rapid-ship`; the CLI remains `devctl`. Current code uses the root-level `rapid_ship` package. Historical artifact names and hashes above identify the files actually tested at those checkpoints.

- The rename passed 563 local tests, Ruff, mypy, lockfile and skill validation, build, and a clean external Python 3.13 installation/init check.
- The rebuilt wheel includes the renamed skill and package metadata: `rapid_ship-0.1.0-py3-none-any.whl`, SHA256 `3ce31745cd3fc4f3170f6ff2219cb938c7a155f3db1ba77068b4634506aeda88`.
- [PR #10](https://github.com/proxy-hatch/rapid-ship/pull/10) published the new name and README on main. Its 1,000 high-quality PR/month figure is an ambition, not an observed result. Old artwork is preserved but not displayed while new ship-themed artwork is prepared.
- Standalone `agy` 1.3.3 is now installed. A supervised native call with `gemini-3.7-flash-high` returned code that passed six independent checks in a restricted Docker container. This does not qualify Docker authentication, tool-using agent behavior or unattended delivery.

## Runtime comparison — 2026-10-11

The [LightDAG and AstraBox trial](trials/2026-10-11-runtime-comparison.md) records real installed-package, Docker and harness execution, deliberate failures, and remaining limits. The archived probes use deterministic workers or a local model stub except for the separately labeled native `agy` smoke. They measure runtime behavior, not coding quality or production reliability.

Independent review corrected a LightDAG probe that accepted a non-running container as cleaned up. Stricter checks exposed a startup leak; the report preserves it alongside a separate, limited provisioning fix. AstraBox's turn interruption also left a child process alive, while session deletion removed the container. Neither interruption nor a successful status alone is enough to authorize replacement work.

An additional AstraBox test killed its server during execution. The command completed exactly once, but the recovered managed turn failed on a conflicting execution ID. This remains a recovery gap: inspect existing effects before retrying rather than treating a failed status as proof no work happened.

The runtime experiments do not change the installed controller or grant unattended delivery. At this checkpoint, implementation validation was 563 local tests, with Python 3.12/3.13 CI passing for `de98eb6`.

## Main preview and feedback workflow — 2026-10-11

The preview now has one entry point on `main`. The README explains the work loop, each project's CLI, AstraBox's selected role, the four enforcement rungs and the current integration limits. It uses the supplied ship banner and logo. No unattended capability is enabled by this consolidation.

- **579 local tests passed**, with Ruff, strict mypy for 18 source files, skill validation and distribution builds.
- A fresh external Python 3.13 wheel installation passed the then-current preview walkthrough: version, init, executable wrapper, interview, expected doctor blockers, status and empty metrics. Both packaged skills were installed; reinitialization preserved customized skills, project settings and wrapper permissions.
- Review caught the missing generated wrapper. Regression tests now cover installation, preservation, symlink rejection, controller selection/version failure, argument forwarding and exit status. A version command that prints the expected text but fails is rejected.
- The `rapid-ship-improve` skill separates local preferences from framework fixes, requires duplicate checks and independent review, and keeps publication separate from controller upgrades. Review also corrected its reporting of partial progress after access fails.
- Headless `agy` scenarios requested `gemini-3.7-flash-high`; the returned JSON did not attest the actual model. Five runs without the improvement skill and repeated guided proposals exposed omitted review/deduplication and invented verification claims. Proposal-only reporting corrected those claims in five guided samples. These were synthetic, no-tool exercises, not actual contribution trials or proof that an agent will always comply. A safety scenario preserved review/controller boundaries but still suggested an unrequested caching feature; real contributions still require scope review.

The installed wheel was `rapid_ship-0.1.0-py3-none-any.whl`, SHA256 `33e69ed2b1fc250f0003da950e38cfdf7bf6295f05f427d517a4a7ff84e6ba3a`. The [handoff design](session-handoffs.md) distinguishes temporary throttling, provider allowances and project budgets. AstraBox integration and automatic model/account handoff remain unimplemented.
