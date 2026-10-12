# Improve architecture where it hurts

Use this for demonstrated recurring friction or a requested architecture review, not every small edit. Read [design.md](design.md), the relevant glossary and accepted decisions.

Start with the area the user named. Otherwise inspect recent changes and repeated fixes to find a useful focus. Look for one concept spread across files, pass-through abstractions, repeated caller knowledge, or defects that cannot be tested through the current interface. Collect concrete file references and examples; do not propose a refactor merely because another structure is possible.

For each worthwhile candidate, state:

- the observed problem and affected files;
- the smallest useful change and its behavioral constraints;
- a before/after view of calls or responsibilities;
- what becomes easier to change or verify, and what remains uncertain.

Use [report.md](report.md) for a requested visual report or several candidates that need comparison. A single small finding can stay in conversation. Recommend one candidate based on evidence. An existing ADR is a constraint; identify any proposed conflict and the new evidence that warrants revisiting it.

A review does not authorize broad implementation. When improvement work is authorized, turn the selected candidate into a bounded task with checks, owned paths and independent review through [implement.md](implement.md). Resolve material uncertainty through [clarify.md](clarify.md); record useful language or accepted decisions through [language.md](language.md). Keep project purpose settled and allow later discoveries to refine the implementation.
