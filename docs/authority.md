# Authority and calibration

The installed controller is host-owned and pinned outside the candidate checkout. Candidate code, tests, hooks, and worker reports cannot supply policy or certify a controller upgrade. Local sealed records establish integrity relative to a host key; they do not establish human approval by themselves.

The CLI bundles no external authority adapter. `trial`, `harden`, `github create-pr`, `github merge`, and `release` fail with a blocker. `github preflight` is read-only and reports missing authority even when GitHub protection passes. Setting `verified: true`, editing a JSON approval flag, passing unit tests, or sharing a GitHub identity across two agents grants no merge/release authority.

## Host integration boundary

The library provides `PolicyStore`, `TrialStore`, typed `AuthorityRequest`/`AuthorityDecision` contracts, and an `AuthorityVerifier` callback. A trusted operator service must validate the exact request and return fresh, isolated authority with provenance. That verifier lives outside candidate code and credentials. Trial and policy stores, plus trial receipt keys, must be outside the candidate root and worker mounts.

`TrialStore.trial_request` and `promotion_request` expose the exact binding and payload digests before external sign-off. Recording and promotion revalidate evidence, governing policy, and external authorization. Qualification requires at least three distinct human-reviewed representative changes with distinct heads, plus recovery and adversarial evidence. A grant is scoped to capability, check recipe, environment, controller version, and risk class. Native workers sharing host OS authority cannot receive unattended grants. Hardening records an authorized enforcement rung; it does not widen a grant.

Changing a head, base, policy, recipe, environment, or controller version invalidates the corresponding evidence/authorization match. Human review of these exact trial records and promotion requests is required; there is no automatic trust promotion.

## GitHub broker boundary

Trusted host wiring can construct `GitHubBroker` with a sealed `EvidenceStore` and an authorization callback backed by the verifier and current grant. Public APIs include `push_candidate`, `create_pr`, `merge`, and `publish_release`. Every mutator requires current live evidence, exact approved attempt identity, approved commands, authority, and server protection. Injected test runners/managers and native execution produce no authority-bearing live evidence.

Preflight checks strict status checks, a controller check bound to a **specific real GitHub App**, administrator enforcement, disabled force pushes/deletions, and no PR bypass allowances. The operator must install and configure that App and server protection. This repository's ordinary CI workflow does not supply the App or its app-bound evidence check. Do not substitute a made-up App ID or generic workflow success.

Push imports a sealed candidate Git bundle into a clean bare repository without a checkout, disables hooks/global Git configuration, and reconciles the exact remote branch. PR creation and merge use durable operation keys; merge also checks the current base, exact PR head, and the completed successful App-bound check. The broker never builds or runs candidate code while holding GitHub authentication.

`publish_release` publishes an already staged draft after verifying the tag's commit, asset digests, and a reconciled merge receipt. It neither builds nor uploads artifacts. Annotated tag resolution is currently unsupported. A failed or uncertain external response must be reconciled by operation-specific lookup before retry.

## Bootstrap acceptance

The integration PR remains draft pending the human live agent/model trial. Build, unit tests, simulated broker tests, and Docker compatibility smoke evidence are review inputs, not live autonomy approval. Complete the real representative, recovery, and adversarial trials through trusted host authority before any capability promotion or first production release. No such grant is supplied by this bootstrap.
