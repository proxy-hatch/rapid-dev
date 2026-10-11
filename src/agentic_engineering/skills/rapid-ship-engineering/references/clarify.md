# Clarify implementation

Use the approved design as input. Do not ask about the project's purpose, motivation, intended problem, or whether it should exist.

1. Read the task, relevant code, accepted decisions and existing answers. Find facts through tools; do not ask the user to supply facts already available in the repository.
2. Identify decisions that change observable behavior, public interfaces, data handling, permissions or costly commitments. Resolve routine naming, layout and reversible implementation choices yourself using project conventions.
3. Ask one unresolved question with a concrete recommendation and its trade-off. Use the harness's selector when available; otherwise offer short numbered choices. Do not ask again for settled decisions or existing authorization.
4. Save the answer where the project already records its plan. Update affected task boundaries or checks. Pause that task and its dependents while the decision is open; continue independent work.

Stop clarifying when the next bounded task can proceed. Do not try to exhaust every possible future decision. New facts during implementation may reveal new questions; record and resolve them then.

Read [language.md](language.md) only when a useful term or meaningful technical decision needs recording. A clarification does not automatically need a glossary entry or ADR.
