# Design for the current task

Hide useful complexity behind a small interface. Keep related behavior and its tests close enough that one change does not require edits across many callers. Use the project's existing vocabulary; words such as API, service and boundary are fine when accurate.

Assess the concrete change:

- What must callers know: inputs, outputs, errors, ordering and configuration?
- Can the implementation absorb repeated work without adding a larger interface?
- If this abstraction disappeared, would complexity vanish or spread into its callers?
- Does a real dependency vary, or are we building a slot for a hypothetical future use?

Test observable behavior through the useful interface. Pure computation usually needs no adapter. Prefer a real local test resource when it matches the dependency. Inject a remote or external dependency where substitution is necessary; identify what a fake cannot prove about the real integration.

For a consequential interface choice with credible alternatives, compare a few distinct designs against actual callers, implementation cost and test coverage. Parallel exploration is optional and respects the available agent budget. Do not manufacture three alternatives or maximize flexibility for imagined requirements.

A refactor should reduce demonstrated friction. Preserve behavior and useful coverage; replace old tests only after equivalent checks exist. Ask through [clarify.md](clarify.md) when an unresolved technical choice changes acceptance or a costly commitment. Record a decision through [language.md](language.md) only when it meets the ADR criteria.
