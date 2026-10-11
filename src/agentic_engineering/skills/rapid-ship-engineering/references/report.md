# Visual reports

Use a local HTML report when diagrams or tables make an investigation, trial summary, comparison or architecture review easier to assess. A small finding belongs in conversation; do not generate a report by default for every change.

Start with [HTML-REPORT.html](HTML-REPORT.html), adapt its sections to the question, and remove unused diagram cards or fields. Write a fresh file in the OS temporary directory and show its absolute path through the available file/browser preview. Do not publish private project information automatically.

Lead with the finding or recommendation, then its evidence and limits:

- **Trial:** tested setup, actual results, failures and what remains unverified. Separate simulations from live evidence.
- **Investigation:** observed symptom, evidence, supported cause or remaining uncertainty, next action.
- **Comparison:** relevant criteria, options, trade-offs and a recommendation; a table often suffices.
- **Architecture:** affected files, observed friction, proposed change, before/after diagrams, concrete benefit and confidence. Mention ADR conflicts only when relevant. Read [architecture.md](architecture.md) for the workflow.

Replace every placeholder with escaped text. Keep style and markup under your control; never insert raw repository text as HTML, SVG markup, script, event attributes or URLs. Use inline CSS and SVG so the file renders without CDNs, network access or JavaScript. For complex graphs, use an available local renderer and embed safe output rather than adding a remote dependency.

Choose visuals that explain the evidence: tables, call graphs, sequences or responsibility groupings. Keep labels familiar and prose short. Do not use implementation line counts as architectural quality evidence or unmeasured numbers as trial results.

Open the finished report, check narrow and wide layouts, verify it needs no network, and inspect for private data and unresolved placeholders. A report explains evidence; it does not itself prove implementation or passing checks.
