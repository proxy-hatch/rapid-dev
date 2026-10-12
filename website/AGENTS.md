# Documentation website

The Docusaurus site reads the repository's Markdown; edit content at its source in [docs](../docs/AGENTS.md), [README.md](../README.md), or [ARCHITECTURE.md](../ARCHITECTURE.md).

- [docusaurus.config.js](docusaurus.config.js) controls included documents, routes, metadata, and strict link checks.
- [sidebars.js](sidebars.js) controls public navigation.
- [src/css/custom.css](src/css/custom.css) contains presentation changes.
- [asset/public](../asset/public/) supplies served static files; generated output belongs in `build/`.

Keep `AGENTS.md` excluded from published documents and sidebar generation.
Preserve repository-relative links and the configured deployment base path when changing routes or assets.
For site or public Markdown changes, run `npm ci` then `npm run build` from this directory.
The build enforces broken-link and anchor checks; styling still needs visual inspection when changed.
Dependency versions and scripts live in [package.json](package.json); keep the lockfile consistent with dependency edits.
