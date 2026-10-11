---
name: rapid-ship-improve
description: Use when the user asks to improve rapid-ship itself from project feedback, recurring friction, missing capabilities, or a proposed framework contribution.
---

# Improve rapid-ship

Turn a demonstrated framework gap into a small, reviewed PR. This skill works from the framework checkout or a generated project.

1. Record expected and actual behavior, reproduction steps and installed devctl version. Read relevant local summaries with `./devctl logs --limit 50` (filter `--task TASK_ID` when known). Check whether a project setting solves the problem; keep project-only changes there. Reusable code, setup or skill defects belong in rapid-ship.
2. From a project, read gitignored `.devctl/local.json` for `framework_root` and `controller`. From the framework, use its checkout. If the backlink is missing, inspect installed controller metadata (`.controller/source.json`) or locate the user's selected framework source. Verify the source version and remote before editing. The project's origin is not the framework destination. Try normal reads; ask for folder access only when the harness actually denies it.
3. Search existing framework Linear work and GitHub PRs. Reuse matching work; report unavailable access accurately. Reduce the failure to synthetic fixtures, leaving private source, credentials and raw logs local. Inspect the actual diff and PR text for sensitive data before publishing.
4. Work on a `codex/` branch in a separate framework worktree when needed. Reproduce the failure first. Choose the strongest practical fix: **1** structure/types, **2** automated checks, **3** skill/rules/agent review, **4** human feedback. Add a meaningful regression test; for skill changes, compare an agent's behavior before and after. Keep code simple and preserve supported project choices.
5. Run relevant checks, obtain independent review and recheck the final revision after fixes. Explain any deliberate checks, permissions or trust-policy change. Do not weaken them to hide a failure.
6. Submit or update the framework PR using existing authorization once its destination and access are established. An improvement/PR request needs no repeated permission; diagnosis alone does not authorize posting. If blocked, leave a concrete local draft and name the blocker.

Report only work performed: destination, matching existing work, change or proposal, checks and independent review, PR URL or local status, and remaining blockers. Before implementation, label proposed changes and checks as pending; do not write a draft PR as though a fix already exists. Name actual commands, reviewer and inspected artifacts when reporting verification. Keep the report concise.

A PR does not replace the installed controller, switch an active run, grant approval or increase concurrency. Installation remains a separate action; do not alter a running controller.
