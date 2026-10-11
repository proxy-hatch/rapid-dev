# Shared language and decisions

Read the relevant `GLOSSARY.md` and `docs/adr/` when present. If the project has `GLOSSARY-MAP.md`, follow it to the relevant context. Respect existing locations. Missing files are not blockers and do not need empty scaffolds.

## Glossary

Create or update `GLOSSARY.md` only when shared project terminology will prevent actual confusion. Prefer established terms and simple language; do not replace familiar words with an invented vocabulary. A useful entry is small:

```markdown
**Attempt**: One execution of an assigned task, including its checks and review.
```

Define project concepts, not general programming terms or implementation plans. Add an avoided synonym only when it has caused confusion. Ask about conflicting meanings only when they affect behavior; otherwise follow the established meaning.

## Decisions

Record an ADR only when a real technical trade-off is costly to reverse and would surprise a future reader without context. Routine choices and temporary priorities do not qualify. Do not reopen accepted decisions without new relevant evidence.

Use the next available number in `docs/adr/`, following repository conventions. A short title and one paragraph are enough: the technical constraint, the accepted choice and the trade-off. Mark a proposal as proposed; do not invent acceptance. Unresolved questions belong with affected tasks, not in accepted ADRs.

Write only within authorized scope and owned paths. Otherwise give the coordinator a concise proposed addition. These documents record engineering decisions; they do not invite questions about the project's purpose or motivation.
