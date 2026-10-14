# Delivery permissions

Unattended delivery requires live trials, human approval, and a trusted approval service outside project code. The CLI does not yet include that service: `trial`, `harden`, PR creation, merge, and release commands report a blocker. Read-only `github preflight` can inspect branch protection.

The installed controller, policy, credentials, and signing keys stay outside worker mounts. A signed check/review record detects later edits; it does not prove that a human approved the work. A passing test or an edited approval flag grants no permissions.

## Qualify a project

The library provides `PolicyStore`, `TrialStore`, and an `AuthorityVerifier` callback for a trusted host service. That service must validate the exact request and return a fresh approval with its source recorded. `trial_request` and `promotion_request` expose the data to approve.

Qualification needs three distinct, representative changes reviewed by a human, plus recovery and adversarial trials. Approval applies only to the specified action, checks, environment, controller version, and risk class. Changing the code or those settings requires matching new evidence. Native workers cannot qualify for unattended delivery because they share host access. Recording a stronger check does not expand permissions.

[Quality metrics](../../metrics.md) help decide whether to raise concurrency. They do not issue approval or change the worker count automatically.

## Connect GitHub

`GitHubBroker` exposes `push_candidate`, `create_pr`, `merge`, and `publish_release`. Host wiring must supply verified check/review records and the approval callback. Every write requires current live results for the exact approved attempt, approved check commands, permission for that action, and server protection. Simulated or native runs cannot authorize these writes.

Preflight requires:

- Strict required status checks, including the controller check from a specific installed GitHub App.
- Enforcement for administrators.
- Force pushes and deletions disabled, with no PR bypass allowances.

The ordinary CI workflow supplies none of this configuration. The operator must install the App and configure protection; a made-up App ID or generic CI success cannot substitute for it.

Push uses a clean bare Git repository without running a checkout or hooks. PR creation checks the exact head and base. Merge checks the current base, PR head, and successful App check. Operations are recorded before sending; uncertain responses must be resolved by looking up the remote result before retrying. The broker never runs project builds, hooks, or tests with its GitHub credentials.

`publish_release` publishes an already staged draft after checking its tag commit, asset hashes, and confirmed merge. It does not build or upload artifacts. Annotated tags are currently unsupported.

## Current status

The preview is consolidated on `main` for supervised functional testing. Human-reviewed live trials still govern which capabilities can run unattended. Unit tests, simulated GitHub tests, and runtime trials support review but grant no unattended permissions. No production delivery approval ships with this preview.
