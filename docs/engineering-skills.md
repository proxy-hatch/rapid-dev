# Engineering skills

Use `rapid-ship-engineering` from a coding session. The skill chooses a focused workflow, or you can name one:

> Use rapid-ship-engineering grill-with-docs to clarify this approved design before slicing. Keep the project's purpose settled.

> Use rapid-ship-engineering diagnosing-bugs to reproduce this intermittent failure before changing code.

| Work | Guidance | Result |
|---|---|---|
| Every coding session | Ponytail | The smallest clear implementation that completes the assigned scope |
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

Controlled worker prompts include Ponytail, implementation and TDD guidance from the installed controller. Review prompts include Ponytail and review guidance, including the controller's JSON response format. This also works when a harness disables hooks or a reviewer has no file-reading tools. A project's changed skill cannot replace the installed defaults. No global plugin or hook installation is required.

The bundle uses local reference files rather than requiring a harness-specific Skill tool. Its dependencies travel with it. Project terms and decisions inform the work; they cannot override permissions or delivery rules. Guidance alone cannot enforce correctness or grant unattended delivery.

## Sources and evidence

These are adapted, pinned copies of [Ponytail v5.1.0](https://github.com/DietrichGebert/ponytail/tree/9b58c1ffb790c075ca32e70a89cf1d80588f4abf) and [Matt Pocock's engineering skills](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336/skills/engineering). The bundle includes provenance and both MIT notices. Adaptations remove global setup, mandatory agent counts, repeated approval gates and assumptions about the issue tracker.

[Local checks](trials/2026-10-11-engineering-skills.md) cover dependency loading, packaging, two text-only behavior scenarios and offline report rendering. They are not a coding-quality benchmark.

[JetBrains' experiment](https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/) found smaller output and lower median cost across 80 paired tasks with full Ponytail v4.8.4. It did not establish equivalent quality or security, and passive skill discovery did not reliably activate the rules. Those results justify testing explicit loading; they are not a benchmark for this adaptation. Use rapid-ship's [quality metrics](metrics.md) to assess it on your projects.
