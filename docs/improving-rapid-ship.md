# Improve rapid-ship through use

> **Historical:** describes the controller removed on 2026-10-14. See the [rapid-ship design](superpowers/specs/2026-10-14-rapid-ship-design.md).

Every initialized project gets the `rapid-ship-improve` skill. Tell your coding agent what is missing, confusing or repeatedly going wrong:

> Use rapid-ship-improve: every task asks me to choose the same test account again. Reproduce the problem and submit a focused PR.

The skill finds the right home for the change: a local project setting, a reusable project rule, or the framework itself. Framework work happens in a separate rapid-ship checkout. It checks existing issues and PRs, uses a sanitized reproduction, runs meaningful checks, gets independent review and submits the PR when authorized. If access is missing, it leaves a clearly labeled local result.

Choose the strongest practical enforcement: structure/types first, automated checks second, skills/review guidance third, and human style feedback as the discovery layer. A one-off configuration preference should not become a framework-wide rule.

The PR records the observed problem, fix, validation and any remaining uncertainty. A merged improvement does not replace the controller currently managing another project. Review and install that upgrade separately, preserving project settings and requiring new qualification for changed permissions or delivery policy.

The skill is an agent workflow, not a new `devctl improve` command or a background watcher. Invoke it when there is feedback to act on. Existing projects can rerun the original `init` command to add the missing skill without overwriting their current instructions.
