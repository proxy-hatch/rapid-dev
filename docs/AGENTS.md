# Documentation

Use this directory for user-facing guides and development records.

- The guides at this level, such as [getting-started.md](getting-started.md) and [usage.md](usage.md), describe the controller removed on 2026-10-14 and start with a "Historical" line. Do not extend them; the documentation site is rewritten once the product works.
- Put approved specifications and implementation plans in [superpowers](superpowers/AGENTS.md).
- Put observed experiments, failures, limitations, and reproduction evidence in [trials](trials/AGENTS.md).
- Put one decision per file in `adr/`, numbered in order, when it is hard to reverse, surprising without context, and the result of a real trade-off. So far: [0001 subscription logins only](adr/0001-subscription-logins-only.md), [0002 GitHub gates merges](adr/0002-github-gates-merges-reviews-run-locally.md), [0003 Walk on bare sessions](adr/0003-walk-on-bare-sessions-orchestrator-deferred.md).
- Deferred or abandoned work lives in [archive](archive/AGENTS.md), including the controller-era runtime trials and designs. It does not describe current behaviour.
- Consult [ARCHITECTURE.md](../ARCHITECTURE.md) for current implementation boundaries and [GLOSSARY.md](../GLOSSARY.md) for shared terms.

Keep implemented behavior, selected future work, and experimental observations distinct.
Update the relevant guide when changing user-visible commands or setup behavior.
The [website](../website/AGENTS.md) builds these Markdown files directly; keep relative links valid for both repository readers and the site.
Add public navigation entries in [sidebars.js](../website/sidebars.js) when a new guide belongs in the sidebar.
Maintainer `AGENTS.md` files are excluded from publication; public pages should link to public documents.
