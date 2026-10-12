# Clear technical writing

Use this guidance for development conversations, task instructions, commits, PRs, reviews, documentation and code comments. Follow the project's chosen tone and terminology. Read relevant `GLOSSARY.md` entries when present.

## Instructions and claims

State who acts, what they do, and the condition that controls the action. Put prerequisites and safety conditions before commands. Use one instruction per sentence and numbered steps for procedures. Give each term one meaning. Keep exact commands, paths, identifiers, limits and output schemas.

Prefer active voice, concrete verbs and familiar words. Aim for at most 20 words per instruction and 25 per descriptive sentence. Keep a longer sentence when splitting it would lose meaning. Use one topic per paragraph.

Separate directives from uncertain claims. "Run the check" is an instruction. "The request may have failed" is an uncertain claim. Preserve that uncertainty, including compound tenses when needed. A rewrite must preserve requirement strength, exceptions and scope. Never change "may have failed" to "failed", or "must" to "should".

Base factual claims on inspected source, observed output or an attributable execution record. Distinguish observation from inference. Name missing evidence when it matters. A check that was skipped, blocked or simulated is not a passing live check.

## Development artifacts

| Artifact | Include |
|---|---|
| Commit | One concrete change in the subject, using repository conventions. Add the reason or important consequence when the diff cannot explain it. |
| PR | The problem and resulting behavior, relevant validation and material limits. Describe the final change without the conversation history. |
| Review | The problem, consequence and file:line. Separate observed failures from risks that still need verification. |
| Procedure or error | The condition, exact action and observable result. Place required permissions before the affected step. |
| Status or agent report | The result, evidence and remaining blocker. Follow any required output schema. |
| Code comment | A non-obvious reason, constraint or trade-off. Keep explanations of obvious code out of comments. |
| ADR | The accepted choice and trade-off. Keep proposals and unresolved decisions visibly distinct from accepted decisions. |

Explanatory prose can use natural phrasing. Landing-page and marketing copy can keep its voice. Factual claims still need evidence. Do not force controlled-language rules onto persuasive copy.

## Tutorials

Teach a workflow the reader can repeat with their own project. Separate example inputs, reusable requests and example-specific answers. Keep agent bookkeeping in the skill. Label whether each action belongs in the terminal or the coding session, then show its expected result. Put checks before dependent actions, in separate code blocks when the reader must inspect the result. Finish by showing what changes for the reader's own project. Link to reference material when more detail would interrupt the lesson.

This follows [Diátaxis tutorial guidance](https://diataxis.fr/tutorials/): learn through concrete actions and observable results.

Before sending, remove repeated ideas and empty qualifiers. Recheck uncertainty, conditions, numbers and commands against the source. For a rewrite, return the revised text unless the user requests analysis.

These are adaptations of technical-english and asd-ste100, not a claim of ASD-STE100 compliance. No ASD dictionary is bundled. See [sources and licenses](../SOURCES.md).
