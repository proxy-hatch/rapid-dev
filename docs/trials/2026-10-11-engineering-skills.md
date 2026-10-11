# Engineering skill checks

On 2026-10-11, two synthetic scenarios were run before and after adapting the pinned Matt Pocock skills. Each used a fresh text-only `gemini-3.7-flash-high` session: four requests in total, with no coding or delivery actions requested. These check how guidance is applied; they do not measure code quality, cost savings or unattended readiness.

| Scenario | Upstream guidance | Adapted guidance |
|---|---|---|
| An approved file-import CLI has an agreed progress task, an ambiguous retry task with data-loss implications, and help text depending on progress | Kept purpose settled and independent work moving, but planned glossary/ADR creation automatically | Asked one retry-behavior question, paused only affected work and used the existing task plan |
| One approved task normalizes repeated whitespace through `parse_name(text)`; its public test interface is approved, and a future locale plugin is outside scope | Asked to reconfirm the test interface and planned a current-branch commit | Proceeded with a failing behavior test, minimal implementation and independent review; asked no additional approval |

Both runs received the relevant skill text and were asked to describe next actions without claiming completed work. One sample per condition is too little to establish reliability. The responses were still more verbose than desired; project writing guidance remains necessary. Final controller instructions were subsequently clarified so workers hand results back to the controller and assigned reviewers perform the review themselves.

Structural checks cover installed guidance reaching both roles, candidate rules failing to replace packaged defaults, all local skill references resolving, recursive project copies retaining licenses, and custom instructions remaining unchanged with missing links reported. These use simulated runners. The installed-wheel smoke check exercises the actual package and generated wrapper.

The HTML scaffold was filled with escaped synthetic content and rendered at 1100px and 375px. Visual inspection found no clipped text or horizontal overflow. It used two inline SVG diagrams, no scripts and no network requests. A real report must still be inspected after its content changes.
