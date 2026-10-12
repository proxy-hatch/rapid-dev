# Documentation

Use this directory for user-facing guides and development records.

- Put repeatable user workflows alongside [getting-started.md](getting-started.md) and [usage.md](usage.md).
- Put approved specifications and implementation plans in [superpowers](superpowers/AGENTS.md).
- Put observed experiments, failures, limitations, and reproduction evidence in [trials](trials/AGENTS.md).
- Consult [runtime-choice.md](runtime-choice.md) for the selected backend and its current integration limits.
- Consult [ARCHITECTURE.md](../ARCHITECTURE.md) for current implementation boundaries and [GLOSSARY.md](../GLOSSARY.md) for shared terms.

Keep implemented behavior, selected future work, and experimental observations distinct.
Update the relevant guide when changing user-visible commands or setup behavior.
The [website](../website/AGENTS.md) builds these Markdown files directly; keep relative links valid for both repository readers and the site.
Add public navigation entries in [sidebars.js](../website/sidebars.js) when a new guide belongs in the sidebar.
Maintainer `AGENTS.md` files are excluded from publication; public pages should link to public documents.
