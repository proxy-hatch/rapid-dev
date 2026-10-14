# Engineering skills

> **Historical:** describes the controller removed on 2026-10-14. See the [rapid-ship design](superpowers/specs/2026-10-14-rapid-ship-design.md).

Use `rapid-ship-engineering` from a coding session. The skill chooses a focused workflow, or you can name one:

> Use rapid-ship-engineering grill-with-docs to clarify this approved design before slicing. Keep the project's purpose settled.

> Use rapid-ship-engineering diagnosing-bugs to reproduce this intermittent failure before changing code.

| Work | Guidance | Result |
|---|---|---|
| Every coding session | Ponytail | The smallest clear implementation that completes the assigned scope |
| Commits, PRs, docs and agent messages | technical-english, asd-ste100 | Clear actions and accurate claims, with uncertainty and technical details preserved |
| Before slicing | grill-with-docs, grilling, domain-modeling | Material questions resolved; useful terms in `GLOSSARY.md` and decisions in `docs/adr/` |
| Implementation | implement → TDD; codebase-design when needed | One leaf task with meaningful behavior checks |
| Hard bugs | diagnosing-bugs → regression test | Reproduction, evidence, minimal fix and checked outcome |
| Review | code-review | Independent findings against the exact task, design and revision |
| Architecture work | improve-codebase-architecture → codebase-design | A demonstrated problem, compared options and a bounded improvement |
| Substantial reports | HTML report guidance | A portable, offline report; short findings stay in ordinary prose |

Clarification covers how to build the approved project, never whether it should exist. Agents read existing answers first, handle routine choices and ask one material question at a time. Unknowns discovered during development stop affected work only. Shared language reuses real domain terms; it does not invent jargon to sound precise.

TDD exercises behavior through useful interfaces, with a failing test followed by the smallest working change. It does not require a test for every cosmetic edit or another approval for already agreed acceptance cases. Independent review remains required; a worker's self-check does not replace it.

## How guidance reaches agents

`init` copies the bundle, its references and MIT notices into `.agents/skills/` and `.claude/skills/`. New project instructions load Ponytail by default and route the remaining workflows when relevant. Existing custom instructions and skills are preserved; during setup, reconcile their links instead of overwriting them.

Controlled worker prompts include Ponytail, writing, implementation and TDD guidance from the installed controller. Review prompts include Ponytail, writing and review guidance, including the controller's JSON response format. This also works when a harness disables hooks or a reviewer has no file-reading tools. A project's changed skill cannot replace the installed defaults. No global plugin or hook installation is required.

The bundle uses local reference files rather than requiring a harness-specific Skill tool. Its dependencies travel with it. Project terms and decisions inform the work; they cannot override permissions or delivery rules. Guidance alone cannot enforce correctness or grant unattended delivery.

## Sources and evidence

**Matt Pocock** created the engineering skills that underpin these workflows. We adapt his clarification, domain modeling, implementation, TDD, debugging, design, review and reporting guidance. See the [skill sources and author credits](credits.md) for direct links to each source.

The bundle also adapts Dietrich Gebert's Ponytail, Vinnie Mazza's technical-english and Dustin Yuchen Teng's asd-ste100. Pinned references and MIT notices travel with the generated project. Adaptations preserve rapid-ship's scope and existing authorization. Writing rules cover commits and PRs, preserve uncertainty, and keep persuasive copy natural. They do not claim ASD-STE100 compliance.

[Local checks](trials/2026-10-11-engineering-skills.md) cover dependency loading, packaging, two text-only behavior scenarios and offline report rendering. They are not a coding-quality benchmark.

[JetBrains' experiment](https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/) found smaller output and lower median cost across 80 paired tasks with full Ponytail v4.8.4. It did not establish equivalent quality or security, and passive skill discovery did not reliably activate the rules. Those results justify testing explicit loading; they are not a benchmark for this adaptation. Use rapid-ship's [quality metrics](metrics.md) to assess it on your projects.
