---
status: accepted
---

# GitHub gates merges; Agent identity is optional

Checks run in the project's CI on GitHub, and the ruleset and CODEOWNERS decide what merges. rapid-ship therefore keeps no local evidence store, policy store or merge broker. Reviews run wherever the Lead's Harness runs them: a subagent following `rs-review`, another vendor's CLI, or the Lead itself. rapid-ship ships the review skill, not a review runner.

Agent identity is an optional feature. `rapid-ship app` creates two GitHub Apps that the owner controls: one opens and merges pull requests, the other posts reviews. With Agent identity on, agents make their GitHub writes through one thin devctl command that runs `gh` and `git push` with an App's short-lived token. The Kit's Harness settings then deny `git push` and `gh` writes made as the owner. `rs-setup` explains what Agent identity buys and costs, and the owner opts in or not.

GitHub never lets a pull request's author approve or request changes on it, on any plan. Agent identity therefore buys four things:

1. The owner can formally approve agent pull requests, so merges need no admin bypass. In a team, teammates' approvals cover this without it.
2. The Reviewer's verdicts are real GitHub reviews, so Revisions can be counted.
3. Agent pull requests can be told apart from the owner's, which every per-agent-PR metric needs.
4. CODEOWNERS binds the Lead in Flight, because an App cannot use the owner's bypass.

Without Agent identity, agents act as the owner and these four are lost:

1. The owner cannot approve an agent's pull request, so a solo owner merges it through the admin bypass.
2. The Reviewer's verdicts are comments from the owner's account, not reviews.
3. Revisions and the other per-agent-PR metrics report "unknown: needs Agent identity". Metrics over all pull requests still work: Reverts, red default-branch CI after a merge, and pull requests closed unmerged.
4. Flight needs the ruleset to drop its review requirement, so the Protected set becomes advice. `rs-lead` explains this, and the owner decides.

## Considered options

- **Agent identity as a requirement** (the design before 2026-10-16). Rejected: it costs every owner two Apps, keys in the macOS Keychain and extra Harness settings, while a team's approvals already cover its first benefit.
- **Agents always act under the owner's GitHub account, with no App option.** Rejected: the owner could never approve agent pull requests, Revisions could never be counted, and CODEOWNERS could never bind the Lead in Flight.
- **devctl commands that push, review and merge as steps of a flow** (`devctl pr`, `review` and `merge`, built on the never-merged plan 4 branch). Rejected with the flow itself ([ADR 0004](0004-team-management-boundary.md)). Only the thin command for `gh` and `git push` remains, and only under Agent identity.
- **A Reviewer in GitHub Actions.** Rejected: CI stays deterministic and needs no model sign-in, a model token in GitHub secrets is reachable by a same-repository branch that edits the workflow, and reviewing is the Lead's Harness's job.
- **A local broker with sealed receipts** (the design before 2026-10-14). Rejected: about 1,100 lines that no command could reach, guarding what GitHub already binds to the head commit.

## Consequences

- One ruleset on the default branch requires a pull request with code-owner review, every review thread resolved, and a passing `devctl check` reported by GitHub Actions. It allows squash merges only and blocks force pushes. Only the repository admin role may bypass it, and only when merging a pull request.
- The Kit's Harness settings deny every agent `gh pr merge --admin`, with or without Agent identity.
- With Agent identity, CODEOWNERS `*` enforces Walk: every pull request needs the owner's approval, and an App cannot bypass the ruleset.
- Neither App has the Workflows, Administration or Checks permission, and neither is a code owner, so an App's approval never stands in for the owner's.
- Each App's private key is stored in the macOS Keychain, which makes Agent identity macOS-only. devctl mints a short-lived installation token for each command and holds it only in memory. No key or token is written to disk, a command line or output.
- Any process the owner runs can read both keys, so a Worker can reach the reviewing App. `rs-work` tells Workers never to post reviews or act as that App. No technical barrier is planned until misuse is observed.
- Deny rules can be bypassed. A misbehaving agent on the owner's machine could still act as the owner, with or without Agent identity. The ruleset and CODEOWNERS on GitHub are the enforcement.
- GitHub Free private repositories have no rulesets, so GitHub gates no merge there (backlog item PRO-100).
