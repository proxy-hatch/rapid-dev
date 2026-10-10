# Bootstrap validation — 2026-10-10

The reviewed implementation is on `codex/bootstrap-framework` in [draft PR #1](https://github.com/proxy-hatch/agentic-engineering/pull/1). The tested implementation commit is `21762cd`; subsequent documentation records these results. This is a supervised bootstrap candidate, with no production release or autonomous capability grant.

| Check | Observed result |
| --- | --- |
| Full local suite | 398 passed on macOS / Python 3.13.12. |
| Static checks | Ruff passed; strict mypy passed for 15 source files. |
| Build | Source distribution and wheel built successfully. |
| Linux CI | Tests, Ruff, mypy and build passed on Python 3.12 and 3.13 in [run 38041572063](https://github.com/proxy-hatch/agentic-engineering/actions/runs/38041572063). |
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
- GitHub's branch-protection API returned HTTP 403 for this private repository: the current plan requires GitHub Pro or public visibility for that feature. The repository remains private. Ordinary successful CI is not an app-bound evidence check.
- OpenHands execution and AWS provisioning require separately implemented, registered adapters. Unknown providers and resources block dispatch. Worktrees currently pair with explicit native execution only.
- Native and simulated runs supply no unattended authority. The Docker smoke test covers only its recorded image and provider composition, not coding-agent authentication or arbitrary cloud environments.

The draft PR remains draft pending the human live agent/model trial. No account plan, repository visibility, production infrastructure or installed controller was changed to bypass these gates.
