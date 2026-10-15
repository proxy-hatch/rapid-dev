---
status: accepted
---

# GitHub gates merges; reviews run locally

Checks run in the project's CI on GitHub and branch protection decides what merges, so rapid-ship keeps no local evidence store, policy store or merge broker. The Reviewer is a local Session for every Harness: under [ADR 0001](0001-subscription-logins-only.md) only Claude could review inside GitHub Actions, and one interface is simpler than two. Agent pull requests come from a Worker App and reviews from a separate Reviewer App, both GitHub Apps the owner controls. The owner can therefore formally approve or request changes on agent pull requests, and the Reviewer's approvals and change requests are real GitHub reviews.

## Considered options

- **Reviewer in GitHub Actions.** Rejected: Claude only, it needs a model token in GitHub secrets, and a same-repository branch can edit the workflow that holds it.
- **Agents act under the owner's GitHub account.** Rejected: GitHub does not let an author approve or request changes on their own pull request, and nothing would distinguish the owner's verdict from an agent's.
- **A local broker with sealed receipts** (the previous design). Rejected: about 1,100 lines that no command could reach, guarding what GitHub already binds to the head commit.

## Consequences

- During Walk, CODEOWNERS assigns every path to the owner, so a Reviewer App approval never replaces the owner's.
- The verdict is produced on the owner's machine, where a Worker can reach the Reviewer App's key. For now the Kit skills instruct Workers never to post reviews or use the Reviewer App. No technical barrier is planned until misuse is observed. Which GitHub credential a Session may hold is decided with the Flight design.
