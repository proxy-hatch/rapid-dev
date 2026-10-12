# Small, complete changes

Adapted from [Ponytail v5.1.0](https://github.com/DietrichGebert/ponytail/blob/9b58c1ffb790c075ca32e70a89cf1d80588f4abf/skills/ponytail/SKILL.md). Copyright and MIT terms: [PONYTAIL-LICENSE.txt](../PONYTAIL-LICENSE.txt). This adaptation removes modes, hooks and global settings changes.

Build the user's requested project. Never question its purpose, substitute a different product, or drop requested features to make implementation smaller. Simplify the implementation while meeting the approved design and acceptance criteria. Unresolved design decisions block the affected task; routine implementation choices do not.

Before editing, read the affected code and identify required callers, tests, fixtures, configuration and interfaces. Check for data loss, exposure and broken consumers. Stay within the task's owned paths. If completion needs changes outside them, resolve the scope or dependency before editing those paths.

Choose the smallest clear solution that fully works:

- Reuse the project's existing helpers, patterns and conventions.
- Prefer standard libraries and platform features when they fit the project's architecture, then suitable installed dependencies. Add a dependency when its benefit justifies its cost; do not hand-roll sensitive functionality merely to avoid one.
- Add only the abstractions, options, configuration and conversions the task needs. Preserve existing layers and interfaces. Readable code matters more than line count.
- Fix the shared cause of a bug where scope permits. Complete every required change, including affected callers and tests.
- Explain non-obvious reasons in comments. Document real limits where maintainers need them, without speculative warnings or mandatory boilerplate.

Never simplify away trust-boundary validation, data-loss prevention, security, accessibility, hardware calibration, requested behavior or required verification. Moving or consolidating code preserves its error handling and validation.

Follow the project's testing requirements. Give non-trivial logic meaningful coverage, including relevant edge cases; one small test is not a ceiling. Prefer checks of behavior over tests that mirror implementation. Report checks actually run and material unresolved limits. Missing or skipped verification is never a passing result.
