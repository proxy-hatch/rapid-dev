# Kit skills implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Kit's first skills: five engineering skills forked from mattpocock/skills and pinned in an upstream lock, `rs-writing` and `rs-ponytail` moved from `rapid-ship-engineering`, the user-invoked `rs-setup`, `rs-health` and optional `rs-contribute`, and the `rapid-ship adopt` command. Then retire `rapid-ship-engineering`, and apply `rs-setup`'s GitHub settings to `proxy-hatch/rapid-ship` itself.

**Architecture:** Each Kit skill is a template directory under `rapid_ship/templates/common/.agents/skills/`, copied byte for byte into projects by plan 2's `init` and `sync`. Upstream files are pinned in `rapid_ship/upstream.lock` and checked offline: verbatim files against their git blob SHA, patched files against a pristine fixture with every difference inside a marked rapid-ship section. `rapid-ship adopt` is one module in `rapid_ship/kit/` that appends one `rs-exception` marker per unmarked suppression rule in Python files and lists each in `.rapid-ship/exceptions.toml`, changing only comments. Its rule names copy devctl's exceptions step, and a parity test keeps the two equal.

**Tech Stack:** Python 3.12+, uv, pytest, `tomllib`, `tomli-w`, `tokenize` and `ast` from the standard library, git, `gh` (read-only research and Owner steps), Markdown skills.

**Spec:** [Spec 1: Kit and Setup](../specs/2026-10-14-kit-and-setup-design.md), sections 3 (`rapid-ship adopt`), 7, 8 and 9. Shared names and layout: [plan index](2026-10-14-kit-and-setup.md), plan 5 of 5.

## Global Constraints

- Upstream: mattpocock/skills (MIT) at `49dd158d1076134a641b33efb035946536778336`. Every forked skill directory carries the upstream licence notice.
- `rapid_ship/upstream.lock` records, for each upstream file: path, upstream commit, upstream blob SHA, and status `verbatim` or `patched`.
- A patched file differs from upstream only inside marked sections. Markers are whole lines: `<!-- rapid-ship:begin -->` and `<!-- rapid-ship:end -->` in Markdown; `# rapid-ship:begin` and `# rapid-ship:end` inside YAML front matter.
- Kit skills use the `rs-` prefix. Each `SKILL.md` front matter has `name` equal to its directory name and a non-empty `description`, as plan 3's map rule 7 requires of every skill under `.agents/skills/`. Claude Code takes the slash command from `name` (code.claude.com/docs/en/skills), so an unpatched `name: tdd` would register `/tdd`.
- Managed templates are copied byte for byte; only seeded files substitute `{{project_name}}`, `{{package}}`, `{{owner}}` and `{{repository}}`. `.claude/skills/<name>` links are generated from `.agents/skills/<name>`, not stored as templates.
- `rs-contribute` is installed only when listed under `[kit] optional` in `.rapid-ship/project.toml`.
- `rs-setup`, `rs-health` and `rs-contribute` are user-invoked: `disable-model-invocation: true` for Claude Code and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` for Codex.
- `rs-setup` journals each external write in its conversation before making it, and re-reads the outside state before retrying an uncertain one. Every external write waits for the owner's explicit yes.
- Ruleset (spec section 8, step 3; index "Ruleset"): default branch; PR with 1 approval and code-owner review; `dismiss_stale_reviews_on_push` and `require_last_push_approval` set to `true`; required check `devctl check` with GitHub Actions (`integration_id` 15368) as source; block force pushes and deletion; bypass only the repository admin role in `pull_request` mode. Plan 4's `ruleset_problems` reports a ruleset where either flag is not `true`.
- rapid-ship source (index, Conventions): `rs-setup` runs `uvx --from <source> rapid-ship <command>` at `kit_version` from `.rapid-ship/kit.lock`. `<source>` is `git+https://github.com/proxy-hatch/rapid-ship@v<kit_version>` when that tag exists. Before it exists, `<source>` is the owner's local rapid-ship checkout. PyPI publishing is a later, separate change, so no step here reads PyPI.
- Never read token files. Never write or print an App private key. Agents use subscription sign-ins, never API keys (ADR 0001).
- Antigravity CLI always runs as its own top-level process, never from inside another vendor's agent (rapid-ship design, "Who does the work"). `devctl doctor` never starts agy from inside another coding session; there it reports agy items as unknown (plan 4). So `rs-setup` step 9 always asks the owner to run `./devctl doctor --skills` from their own terminal (spec section 8, step 9).
- `[kit] exclude` in `.rapid-ship/project.toml` is the only record of an exclusion (spec section 3; index, "Kit exclusions and skill discovery"). `adopt` reads it with plan 2's `read_excluded`, never from the lock.
- `rs-health` changes nothing in the repository; it creates only the Linear issues the owner selects, in the backlog and without `ready-for-agent`.
- `adopt` reason: `Existed at Setup on <date>`; removal condition: `Remove when this code next changes`; marker `rs-exception: EX-<n>` on the suppression's line.
- Python suppressions: `# noqa`, `# type: ignore`, `# pragma: no cover`, and the skip and xfail markers.
- `adopt` finds and names rules exactly as plan 3's exceptions step does (plan 3, Task 7 table), and gives each rule its own marker and entry. It edits only `.py` and `.pyi` files. A suppression in another file, such as a zizmor ignore in a workflow, is marked by hand, because `adopt` cannot prove that an edit there changes only a comment.
- Exit codes in both CLIs: 0 success; 1 a check failed, something is missing, or a request was refused; 2 the command could not run.
- The rapid-ship CLI depends only on `tomli-w` beyond the standard library. Settings are TOML, read with `tomllib`.
- Write tests first. Label offline and simulated tests. A blocked or skipped step never counts as passed.
- Branch names: any prefix except `rs/`. New code follows this repository's lint settings; any suppression gets an `rs-exception` marker and an `exceptions.toml` entry. Run `uv run ruff format` on new Python files before each commit; the code below shows content, not final wrapping.
- The guardrails of plan 3 Task 18 cover `rapid_ship` and `tests/`: output goes through `sys.stdout.write` and `sys.stderr.write`, no signature uses `Any`, complexity is at most 10, and every test and helper is annotated for strict mypy. Ruff's S603 and S607 apply to tests, so tests start processes through `devctl.process.run_process` or `check_workspace.Workspace` (plan 3 Tasks 1 and 2), never `subprocess`.
- devctl test files are `tests/devctl/test_devctl_<area>.py`, and `tests/devctl/` has no `conftest.py`. pytest's `pythonpath = ["tools/devctl", "tests/devctl"]` (plan 3 Task 2) lets any test import devctl and `check_workspace`.
- After any template change, run `uv run rapid-ship sync --in-place`, which accepts a dirty work tree (plan 2 Task 5). Commit the template, the vendored copy and `.rapid-ship/kit.lock` together; CI runs `rapid-ship status --strict`.

## Review Focus

1. **A forked file drifts from upstream.** A verbatim file edited by even one byte, or a patched file edited outside its markers, must fail `tests/test_kit_upstream.py`. Owner: Task 1.
2. **A copied skill lacks its licence.** Any skill directory with a lock entry, or whose Markdown names a locked upstream repository, must contain that repository's `LICENSE` as a verbatim lock entry; `rs-writing` and `rs-ponytail` must carry their MIT notices. Owner: Task 1 (`test_borrowed_text_carries_its_licence`), extended in Task 4.
3. **A skill makes an external write without the owner.** Every write command in `rs-setup`, `rs-health` or `rs-contribute` must appear in that skill's External writes table, under the rule "Wait for the owner's explicit yes. One yes covers one write." Owner: Task 7 (`test_every_external_write_waits_for_the_owner`).
4. **`adopt` disagrees with the exceptions step, or changes code.** A line with two rules (`# type: ignore[x]  # noqa: E501`) needs two markers and two entries. `pytest.importorskip`, file-level `# ruff: noqa` and `# mypy:` comments, and lower-case noqa codes count too. A second run after commit adds nothing; IDs continue after the highest existing one; a marker that would land inside a string is refused with nothing written; file modes survive; a Kit file listed under `[kit] exclude` in `project.toml` is scanned like a project file, as the exceptions step scans it. Owner: Task 5 (`test_rule_names` and the `adopt` tests) and Task 6 (`test_adopt_finds_what_the_exceptions_step_requires`).
5. **`rs-contribute` leaks project data upstream.** Its scan must catch home-directory paths, Windows paths, GitHub tokens and private-key headers before anything is pushed. Owner: Task 9 (`test_contribute_leak_scan_catches_private_data`).
6. **A Worker's Session cannot see a Kit or project skill.** Every skill template, including the optional `rs-contribute` that this repository does not vendor, must pass plan 3's `skill_errors`, map rule 7's front matter half. `rs-setup` must ask the owner to run `./devctl doctor --skills` from their own terminal, resolve or record each missing skill, and record the recheck gap whenever the Setup branch adds or changes a skill, because the probe reads the default branch. The live trial must record what each Session saw. Owner: Task 1 (`test_skill_front_matter_meets_map_rule_7`), Task 7 (`test_setup_runs_doctor_with_the_skills_probe`) and Task 11.

### Task 1: Upstream lock and the name-only forks

Forks `codebase-design`, `diagnosing-bugs` and `writing-for-agents`. Each changes only the front matter `name`, so the spec's "verbatim" means every file but `SKILL.md` is byte-identical and `SKILL.md` is patched in one marked section.

**Files:**
- Create: `rapid_ship/upstream.lock`
- Create: `rapid_ship/templates/common/.agents/skills/rs-codebase-design/{SKILL.md,DEEPENING.md,DESIGN-IT-TWICE.md,agents/openai.yaml,LICENSE}`
- Create: `rapid_ship/templates/common/.agents/skills/rs-diagnosing-bugs/{SKILL.md,scripts/hitl-loop.template.sh,agents/openai.yaml,LICENSE}`
- Create: `rapid_ship/templates/common/.agents/skills/rs-writing-for-agents/{SKILL.md,SKILL-MECHANICS.md,agents/openai.yaml,LICENSE}`
- Create: pristine fixtures under `tests/fixtures/upstream/mattpocock/skills/49dd158d1076134a641b33efb035946536778336/`: `skills/engineering/codebase-design/SKILL.md`, `skills/engineering/diagnosing-bugs/SKILL.md`, `skills/productivity/writing-for-agents/SKILL.md`
- Test: `tests/test_kit_upstream.py`, `tests/test_kit_skills.py`
- Modify: `tests/test_skill_discovery.py` (one assertion; Task 10 replaces the file)
- Modify (generated by sync): `.agents/skills/rs-*`, `.claude/skills/rs-*`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: plan 2's template layout and `uv run rapid-ship sync --in-place`; plan 1's `test_checkout_discovers_exactly_the_packaged_skills`; from plan 3 Task 5, `skill_errors(root: Path, files: Sequence[str]) -> list[str]` in `devctl/check/map.py`, map rule 7's front matter half, which checks each `.agents/skills/<name>/SKILL.md` among `files` below `root`, and `front_matter(text: str) -> object | None` in `devctl/check/markdown.py`.
- Produces: the `rapid_ship/upstream.lock` format, the marker syntax, and the fixture layout `tests/fixtures/upstream/<upstream_repository>/<upstream_commit>/<upstream_path>`.

- [ ] **Step 1: Check the starting point.** Plans 1–4 must have merged (plan index order). Until plan 3 deleted `scripts/check_repository.py`, its skill-alias check failed on every vendored `rs-` skill. Run:

```bash
git fetch origin
git switch -c kit-skills origin/main
test ! -e scripts/check_repository.py && echo "navigation script removed"
git ls-files tools/devctl/devctl/check/exceptions.py tools/devctl/devctl/check/markdown.py tools/devctl/devctl/doctor.py rapid_ship/github_app.py tests/devctl/check_workspace.py
grep -n "def skill_errors" tools/devctl/devctl/check/map.py
grep -n "def front_matter" tools/devctl/devctl/check/markdown.py
./devctl check --tier full
uv run rapid-ship status --strict
```

Expected: `navigation script removed`, all five paths listed, `def skill_errors(root: Path, files: Sequence[str]) -> list[str]:` in `map.py`, `def front_matter` in `markdown.py`, and both checks exit 0. The tests in step 2 call `skill_errors` itself, so the template check and the map step cannot drift apart; if plan 3 renamed it, import the new name. If any other result differs, stop: a plan this one builds on has not merged.

- [ ] **Step 2: Write the failing tests.** Create `tests/test_kit_upstream.py`:

```python
"""Offline checks of forked Kit skills against rapid_ship/upstream.lock."""

import hashlib
import tomllib
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATES = REPOSITORY / "rapid_ship/templates/common"
SKILLS = TEMPLATES / ".agents/skills"
PRISTINE = REPOSITORY / "tests/fixtures/upstream"
BEGIN = {"<!-- rapid-ship:begin -->", "# rapid-ship:begin"}
END = {"<!-- rapid-ship:end -->", "# rapid-ship:end"}
LOCK = tomllib.loads((REPOSITORY / "rapid_ship/upstream.lock").read_text())
FORKED: list[str] = LOCK["forked"]
ENTRIES: list[dict[str, str]] = LOCK["file"]


def git_blob_sha(content: bytes) -> str:
    """The object ID git gives a file, as `git hash-object` prints it."""
    header = b"blob %d\0" % len(content)
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def unmarked_runs(text: str) -> list[list[str]]:
    """Lines outside rapid-ship sections. N sections give N + 1 runs."""
    runs: list[list[str]] = [[]]
    inside = False
    for line in text.splitlines(keepends=True):
        marker = line.rstrip("\r\n")
        if marker in BEGIN:
            if inside:
                raise ValueError("nested rapid-ship section")
            inside = True
        elif marker in END:
            if not inside:
                raise ValueError("rapid-ship end without begin")
            inside = False
            runs.append([])
        elif not inside:
            runs[-1].append(line)
    if inside:
        raise ValueError("unclosed rapid-ship section")
    return runs


def differs_only_in_marked_sections(local: str, upstream: str) -> bool:
    """True when every difference is whole upstream lines replaced by a marked section.

    Runs between sections are matched at their first occurrence. A repeated run can
    therefore fail a valid file, but a file with an unmarked change never passes.
    """
    lines = upstream.splitlines(keepends=True)
    runs = unmarked_runs(local)
    if len(runs) == 1:
        return runs[0] == lines
    first, *middle, last = runs
    if lines[: len(first)] != first:
        return False
    position = len(first)
    for run in middle:
        width = len(run)
        found = next(
            (i for i in range(position, len(lines) - width + 1) if lines[i : i + width] == run),
            None,
        )
        if found is None:
            return False
        position = found + width
    tail = len(lines) - len(last)
    return tail >= position and lines[tail:] == last


UPSTREAM = "---\nname: tdd\n---\n\nIntro.\n\nAsk the user.\n\nEnd.\n"
PATCHED = (
    "---\n# rapid-ship:begin\nname: rs-tdd\n# rapid-ship:end\n---\n\nIntro.\n\n"
    "<!-- rapid-ship:begin -->\nRead the brief.\n<!-- rapid-ship:end -->\n\nEnd.\n"
)


def test_git_blob_sha_matches_git() -> None:
    assert git_blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_marked_sections_may_replace_upstream_lines() -> None:
    assert differs_only_in_marked_sections(PATCHED, UPSTREAM)


@pytest.mark.parametrize(
    "local",
    [
        PATCHED.replace("Intro.", "Intro, edited."),
        PATCHED.replace("End.\n", ""),
        UPSTREAM.replace("Ask the user.\n\n", ""),
        UPSTREAM.replace("name: tdd", "name: rs-tdd"),
    ],
    ids=["edit-between-sections", "deletion-after-section", "unmarked-deletion", "unmarked-rename"],
)
def test_changes_outside_marked_sections_fail(local: str) -> None:
    assert not differs_only_in_marked_sections(local, UPSTREAM)


@pytest.mark.parametrize(
    "text",
    [
        "<!-- rapid-ship:begin -->\nx\n",
        "x\n<!-- rapid-ship:end -->\n",
        "# rapid-ship:begin\n# rapid-ship:begin\n",
    ],
    ids=["unclosed", "end-without-begin", "nested"],
)
def test_malformed_sections_are_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="rapid-ship"):
        unmarked_runs(text)


@pytest.mark.parametrize("entry", ENTRIES, ids=[entry["path"] for entry in ENTRIES])
def test_upstream_file_matches_its_pin(entry: dict[str, str]) -> None:
    local = (TEMPLATES / entry["path"]).read_bytes()
    if entry["status"] == "verbatim":
        assert git_blob_sha(local) == entry["upstream_blob"]
        return
    assert entry["status"] == "patched"
    pristine = (
        PRISTINE / entry["upstream_repository"] / entry["upstream_commit"] / entry["upstream_path"]
    )
    original = pristine.read_bytes()
    assert git_blob_sha(original) == entry["upstream_blob"], "fixture is not the pinned file"
    assert len(unmarked_runs(local.decode())) > 1, "a patched file needs a marked section"
    assert differs_only_in_marked_sections(local.decode(), original.decode())


def test_lock_paths_are_unique() -> None:
    paths = [entry["path"] for entry in ENTRIES]
    assert len(paths) == len(set(paths))


def test_forked_skills_are_fully_locked() -> None:
    locked = {entry["path"] for entry in ENTRIES}
    for skill in FORKED:
        files = {
            path.relative_to(TEMPLATES).as_posix()
            for path in (SKILLS / skill).rglob("*")
            if path.is_file()
        }
        assert files, skill
        assert files <= locked, sorted(files - locked)


@pytest.mark.parametrize("skill", sorted(p.name for p in SKILLS.iterdir() if p.is_dir()))
def test_borrowed_text_carries_its_licence(skill: str) -> None:
    text = "\n".join(path.read_text() for path in (SKILLS / skill).rglob("*.md"))
    own = [entry for entry in ENTRIES if entry["path"].startswith(f".agents/skills/{skill}/")]
    repositories = {entry["upstream_repository"] for entry in ENTRIES}
    needed = {repo for repo in repositories if repo in text}
    needed |= {entry["upstream_repository"] for entry in own}
    licensed = {
        entry["upstream_repository"]
        for entry in own
        if entry["upstream_path"] == "LICENSE" and entry["status"] == "verbatim"
    }
    assert needed <= licensed, sorted(needed - licensed)
```

Create `tests/test_kit_skills.py`:

```python
"""Rules every Kit skill template follows (offline)."""

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from devctl.check.map import skill_errors
from devctl.check.markdown import front_matter

REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATES = REPOSITORY / "rapid_ship/templates/common"
SKILLS = TEMPLATES / ".agents/skills"
ALL = sorted(path.name for path in SKILLS.iterdir() if path.is_dir())


def frontmatter(skill: str) -> dict[str, object]:
    fields = front_matter((SKILLS / skill / "SKILL.md").read_text())
    assert isinstance(fields, dict), skill
    return fields


@pytest.mark.parametrize("skill", ALL)
def test_skill_front_matter_meets_map_rule_7(skill: str) -> None:
    # The map step checks only vendored skills; this also covers rs-contribute, which
    # this repository does not vendor, and catches a bad template before sync copies it.
    assert skill_errors(TEMPLATES, [f".agents/skills/{skill}/SKILL.md"]) == []


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('---\nname: rs-demo\ndescription: ""\n---\n', "description is missing or empty"),
        ("---\nname: rs-demo\ndescription:\n---\n", "description is missing or empty"),
        (
            "---\n# rapid-ship:begin\nname: demo\n# rapid-ship:end\ndescription: Demo.\n---\n",
            "name must be rs-demo",
        ),
        ("# Demo\n", "no front matter"),
    ],
    ids=["quoted-empty-description", "null-description", "upstream-name", "no-front-matter"],
)
def test_front_matter_problems_are_found(tmp_path: Path, text: str, problem: str) -> None:
    skill = tmp_path / ".agents/skills/rs-demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(text)

    errors = skill_errors(tmp_path, [".agents/skills/rs-demo/SKILL.md"])

    assert len(errors) == 1 and problem in errors[0], errors


@pytest.mark.parametrize("skill", ALL)
def test_skill_links_stay_inside_the_skill(skill: str) -> None:
    directory = (SKILLS / skill).resolve()
    for document in directory.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", document.read_text()):
            link = urlparse(target)
            if link.scheme or not link.path:
                continue
            dependency = (document.parent / unquote(link.path)).resolve()
            assert dependency.is_relative_to(directory), (document, target)
            assert dependency.is_file(), (document, target)
```

- [ ] **Step 3: Run them.** `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py -q`. Expected: both modules fail at collection with `FileNotFoundError`, for `rapid_ship/upstream.lock` and for the skills template directory.

- [ ] **Step 4: Fetch the upstream files.** From the repository root:

```bash
C=49dd158d1076134a641b33efb035946536778336
T=rapid_ship/templates/common/.agents/skills
F=tests/fixtures/upstream/mattpocock/skills/$C
fetch() {  # fetch <upstream path> <destination>
  mkdir -p "$(dirname "$2")"
  gh api -H "Accept: application/vnd.github.raw" "repos/mattpocock/skills/contents/$1?ref=$C" > "$2"
}
for s in rs-codebase-design rs-diagnosing-bugs rs-writing-for-agents; do fetch LICENSE "$T/$s/LICENSE"; done
fetch skills/engineering/codebase-design/SKILL.md "$T/rs-codebase-design/SKILL.md"
fetch skills/engineering/codebase-design/DEEPENING.md "$T/rs-codebase-design/DEEPENING.md"
fetch skills/engineering/codebase-design/DESIGN-IT-TWICE.md "$T/rs-codebase-design/DESIGN-IT-TWICE.md"
fetch skills/engineering/codebase-design/agents/openai.yaml "$T/rs-codebase-design/agents/openai.yaml"
fetch skills/engineering/diagnosing-bugs/SKILL.md "$T/rs-diagnosing-bugs/SKILL.md"
fetch skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh "$T/rs-diagnosing-bugs/scripts/hitl-loop.template.sh"
fetch skills/engineering/diagnosing-bugs/agents/openai.yaml "$T/rs-diagnosing-bugs/agents/openai.yaml"
fetch skills/productivity/writing-for-agents/SKILL.md "$T/rs-writing-for-agents/SKILL.md"
fetch skills/productivity/writing-for-agents/SKILL-MECHANICS.md "$T/rs-writing-for-agents/SKILL-MECHANICS.md"
fetch skills/productivity/writing-for-agents/agents/openai.yaml "$T/rs-writing-for-agents/agents/openai.yaml"
for p in skills/engineering/codebase-design/SKILL.md skills/engineering/diagnosing-bugs/SKILL.md skills/productivity/writing-for-agents/SKILL.md; do fetch "$p" "$F/$p"; done
git hash-object $T/rs-*/LICENSE $T/rs-*/*.md $T/rs-*/*/* $F/skills/*/*/SKILL.md
```

Each printed SHA must equal the blob in the table in step 6. These were read on 2026-10-14 from `gh api "repos/mattpocock/skills/git/trees/$C?recursive=1"`, and every file there has mode 100644. The local `MATTPOCOCK-LICENSE.txt` already has the upstream `LICENSE` blob `f1dd2c0…`.

- [ ] **Step 5: Patch the three names.** In each template `SKILL.md`, replace front matter line 2 (`name: codebase-design`, `name: diagnosing-bugs`, `name: writing-for-agents`) with a marked section. For `rs-codebase-design` the file then starts:

```markdown
---
# rapid-ship:begin
name: rs-codebase-design
# rapid-ship:end
description: Shared vocabulary for designing deep modules. Use when …
```

Change nothing else. Fixtures stay as fetched.

- [ ] **Step 6: Write `rapid_ship/upstream.lock`.** Header and one entry, in full:

```toml
# Upstream files copied into the Kit's skill templates.
# tests/test_kit_upstream.py checks every entry offline.
# path: the file under rapid_ship/templates/common/.
# status: "verbatim" (byte for byte) or "patched" (changed only inside rapid-ship sections).
# A patched file's pristine copy lives at
#   tests/fixtures/upstream/<upstream_repository>/<upstream_commit>/<upstream_path>.
# Fetch:     gh api -H "Accept: application/vnd.github.raw" "repos/<upstream_repository>/contents/<upstream_path>?ref=<upstream_commit>"
# Blob SHA:  git hash-object <file>

forked = ["rs-codebase-design", "rs-diagnosing-bugs", "rs-writing-for-agents"]

[[file]]
path = ".agents/skills/rs-codebase-design/SKILL.md"
upstream_repository = "mattpocock/skills"
upstream_path = "skills/engineering/codebase-design/SKILL.md"
upstream_commit = "49dd158d1076134a641b33efb035946536778336"
upstream_blob = "3f63c8146dd2604b419c929e9876b90c30d410e9"
status = "patched"
```

Write one `[[file]]` entry in that form for each row. All rows use `upstream_repository = "mattpocock/skills"` and the commit above.

| path (under `.agents/skills/`) | `upstream_path` | `upstream_blob` | status |
| --- | --- | --- | --- |
| `rs-codebase-design/SKILL.md` | `skills/engineering/codebase-design/SKILL.md` | `3f63c8146dd2604b419c929e9876b90c30d410e9` | patched |
| `rs-codebase-design/DEEPENING.md` | `skills/engineering/codebase-design/DEEPENING.md` | `cd94075cfd754d147555c5d747a16431ed4c7dd8` | verbatim |
| `rs-codebase-design/DESIGN-IT-TWICE.md` | `skills/engineering/codebase-design/DESIGN-IT-TWICE.md` | `d0990138c35c800bd821289a73115e52680c1620` | verbatim |
| `rs-codebase-design/agents/openai.yaml` | `skills/engineering/codebase-design/agents/openai.yaml` | `3180715edb37f6e96bec42f92f00169faa8886ef` | verbatim |
| `rs-codebase-design/LICENSE` | `LICENSE` | `f1dd2c09108dde1a5f56097cee8461b3ea834499` | verbatim |
| `rs-diagnosing-bugs/SKILL.md` | `skills/engineering/diagnosing-bugs/SKILL.md` | `d039541ddd1c46e6ddbd662fe99d49b686fc5e12` | patched |
| `rs-diagnosing-bugs/scripts/hitl-loop.template.sh` | `skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh` | `243198464a8401a7ba1d63b3708fa43c3d067665` | verbatim |
| `rs-diagnosing-bugs/agents/openai.yaml` | `skills/engineering/diagnosing-bugs/agents/openai.yaml` | `a13a755a77634ce61a649a3a0d905a66d3865b35` | verbatim |
| `rs-diagnosing-bugs/LICENSE` | `LICENSE` | `f1dd2c09108dde1a5f56097cee8461b3ea834499` | verbatim |
| `rs-writing-for-agents/SKILL.md` | `skills/productivity/writing-for-agents/SKILL.md` | `a37608daf6e835e767deecfb498facecaaba82ba` | patched |
| `rs-writing-for-agents/SKILL-MECHANICS.md` | `skills/productivity/writing-for-agents/SKILL-MECHANICS.md` | `9cdbdb22aadc438755392216e75ad9a14cc9832e` | verbatim |
| `rs-writing-for-agents/agents/openai.yaml` | `skills/productivity/writing-for-agents/agents/openai.yaml` | `079c933b75743dec18b5d0c01006def20b6aad26` | verbatim |
| `rs-writing-for-agents/LICENSE` | `LICENSE` | `f1dd2c09108dde1a5f56097cee8461b3ea834499` | verbatim |

- [ ] **Step 7: Run the tests.** `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py -q`. Expected: all pass, with 13 lock-entry cases, one front matter case and one link case per skill directory, and four `test_front_matter_problems_are_found` cases.

- [ ] **Step 8: Vendor.** Run `uv run rapid-ship sync --in-place`, then `uv run rapid-ship status --strict`. Expected: status exits 0, and `ls -l .claude/skills` shows `rs-codebase-design -> ../../.agents/skills/rs-codebase-design` and the other two links.

- [ ] **Step 9: Keep plan 1's discovery test true.** Plan 1's `test_checkout_discovers_exactly_the_packaged_skills` asserts that each surface holds exactly `rapid-ship-engineering`, so the vendored skills now fail it. Run `uv run pytest tests/test_skill_discovery.py -q` to see the failure. Then change its last line to:

```python
assert (
    discovered - {name for name in discovered if name.startswith("rs-")} == packaged == set(SKILLS)
)
```

Rerun; expected: all pass. Task 10 replaces this file.

- [ ] **Step 10: Commit.**

```bash
git add rapid_ship/upstream.lock rapid_ship/templates/common/.agents/skills tests/fixtures/upstream tests/test_kit_upstream.py tests/test_kit_skills.py tests/test_skill_discovery.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: fork codebase-design, diagnosing-bugs and writing-for-agents into the Kit" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: `rs-tdd`, with seams from the brief

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-tdd/{SKILL.md,tests.md,mocking.md,agents/openai.yaml,LICENSE}`
- Create: fixture `tests/fixtures/upstream/mattpocock/skills/49dd158d1076134a641b33efb035946536778336/skills/engineering/tdd/SKILL.md`
- Modify: `rapid_ship/upstream.lock`, `tests/test_kit_skills.py`
- Modify (generated): `.agents/skills/rs-tdd`, `.claude/skills/rs-tdd`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: the lock format and markers from Task 1.
- Produces: `rs-tdd`, the skill Workers follow for test-first work.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_kit_skills.py`:

```python
def test_tdd_takes_seams_from_the_brief() -> None:
    text = (SKILLS / "rs-tdd/SKILL.md").read_text()
    assert "the task's brief names the seams under test" in text
    assert "confirm them with the user" not in text


@pytest.mark.parametrize("skill", ALL)
def test_skill_needs_no_harness_specific_tool(skill: str) -> None:
    for document in (SKILLS / skill).rglob("*.md"):
        assert "Skill tool" not in document.read_text(), document
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_kit_skills.py -q`. Expected: `test_tdd_takes_seams_from_the_brief` fails with `FileNotFoundError`; the other cases pass.

- [ ] **Step 3: Fetch.** With the `fetch` helper from Task 1, fetch `LICENSE` and `skills/engineering/tdd/{SKILL.md,tests.md,mocking.md,agents/openai.yaml}` into `rs-tdd/`, and `SKILL.md` again into the fixture path. Check blobs with `git hash-object`.

- [ ] **Step 4: Patch four sections of `rs-tdd/SKILL.md`.** Upstream line numbers refer to the fixture.
  1. Line 2, `name: tdd`, becomes three lines: `# rapid-ship:begin`, `name: rs-tdd`, `# rapid-ship:end`.
  2. Lines 22–24 (the "Test only at pre-agreed seams" paragraph, the blank line and the "Ask:" paragraph) become:

     ```markdown
     <!-- rapid-ship:begin -->
     **Test only at agreed seams.** In rapid-ship the task's brief names the seams under test, and that agreement stands. Write tests only at those seams. When the brief names no seam for a behaviour the task requires, or a named seam cannot observe it, stop and ask the person who assigned the task before you test anywhere else. You can't test everything, so agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.
     <!-- rapid-ship:end -->
     ```

  3. Line 26 becomes the same paragraph with "call the Skill tool with "codebase-design" for the vocabulary" replaced by "read the `rs-codebase-design` skill for the vocabulary", inside a marked section.
  4. Line 38 becomes, inside a marked section: `- **Refactoring is not part of the loop.** It belongs to the review stage, not the red → green implementation cycle.`

- [ ] **Step 5: Lock entries.** Add `"rs-tdd"` to `forked`, and these entries (mattpocock/skills, same commit):

| path | `upstream_path` | `upstream_blob` | status |
| --- | --- | --- | --- |
| `.agents/skills/rs-tdd/SKILL.md` | `skills/engineering/tdd/SKILL.md` | `01eadaa34e7c9a63a67d6dc3cce1cc81b0e49985` | patched |
| `.agents/skills/rs-tdd/tests.md` | `skills/engineering/tdd/tests.md` | `7ab86479f925a1f9e8ba680af33cb3b12e015381` | verbatim |
| `.agents/skills/rs-tdd/mocking.md` | `skills/engineering/tdd/mocking.md` | `71cbfee674d93244ce81d1830b930ca9a69200bd` | verbatim |
| `.agents/skills/rs-tdd/agents/openai.yaml` | `skills/engineering/tdd/agents/openai.yaml` | `651b838a7663e027b1b8884491e867f26bb9a021` | verbatim |
| `.agents/skills/rs-tdd/LICENSE` | `LICENSE` | `f1dd2c09108dde1a5f56097cee8461b3ea834499` | verbatim |

- [ ] **Step 6: Run the tests.** `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py -q`. Expected: all pass, including `test_upstream_file_matches_its_pin[.agents/skills/rs-tdd/SKILL.md]`.

- [ ] **Step 7: Vendor and commit.**

```bash
uv run rapid-ship sync --in-place && uv run rapid-ship status --strict
git add rapid_ship/upstream.lock rapid_ship/templates/common/.agents/skills/rs-tdd tests/fixtures/upstream tests/test_kit_skills.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: fork tdd into the Kit with seams from the brief" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: `rs-pr`, with rapid-ship evidence

Upstream `pr` copies its Summary guidance from HumanLayer's `show-me`, which is MIT licensed in humanlayer/skills (`gh api repos/humanlayer/skills/license`). Upstream carries only `CREDITS.md`; this fork also carries HumanLayer's notice.

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-pr/{SKILL.md,CREDITS.md,agents/openai.yaml,LICENSE,HUMANLAYER-LICENSE}`
- Create: fixture `tests/fixtures/upstream/mattpocock/skills/49dd158d1076134a641b33efb035946536778336/skills/engineering/pr/SKILL.md`
- Modify: `rapid_ship/upstream.lock`, `tests/test_kit_skills.py`
- Modify (generated): `.agents/skills/rs-pr`, `.claude/skills/rs-pr`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: Task 1's lock and markers. The Evidence rules of spec section 5, which plan 3's evidence and diff steps enforce.
- Produces: the PR body format: `## Evidence` with commands and results, an optional `Removed tests:` list of `<path>::<test name>` with reasons, and a `Not covered:` line.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_kit_skills.py`:

```python
def test_pr_body_template_carries_rapid_ship_evidence() -> None:
    text = (SKILLS / "rs-pr/SKILL.md").read_text()
    template = text.split("```markdown\n", 1)[1].split("\n```\n", 1)[0]
    evidence = template.split("## Evidence\n", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"^- `<command>`: ", evidence, re.MULTILINE)
    assert re.search(r"^Removed tests:$", evidence, re.MULTILINE)
    assert re.search(r"^Not covered: ", evidence, re.MULTILINE)
```

- [ ] **Step 2: Run it.** `uv run pytest tests/test_kit_skills.py -q -k pr_body`. Expected: fails with `FileNotFoundError`.

- [ ] **Step 3: Fetch.** Fetch `LICENSE` and `skills/engineering/pr/{SKILL.md,CREDITS.md,agents/openai.yaml}` into `rs-pr/` and the fixture. Fetch HumanLayer's notice:

```bash
gh api -H "Accept: application/vnd.github.raw" "repos/humanlayer/skills/contents/LICENSE?ref=653b6411c1f70c275a18e37673b042ff99f67ceb" > rapid_ship/templates/common/.agents/skills/rs-pr/HUMANLAYER-LICENSE
git hash-object rapid_ship/templates/common/.agents/skills/rs-pr/HUMANLAYER-LICENSE   # f7ad6f4a1d5ed9bbf0589c172c6360587d1530e3
```

`653b641` is humanlayer/skills `main` on 2026-10-08, and contains `plugins/show-me/skills/show-me/SKILL.md`.

- [ ] **Step 4: Patch three sections of `rs-pr/SKILL.md`.**
  1. Line 2, `name: pr`, becomes three lines: `# rapid-ship:begin`, `name: rs-pr`, `# rapid-ship:end`.
  2. Lines 14–33 (the fenced template) become one marked section holding this template. The markers sit outside the fence, so they never reach a PR body:

     ````markdown
     <!-- rapid-ship:begin -->
     ```markdown
     ## Summary

     <diagram, diff-sketch, or tree>

     ## Evidence

     - `<command>`: <its result, such as "142 passed">
     - **Before:** <screenshot/output/failing test run>
       **After:** <screenshot/output/passing test run>

     Removed tests:
     - `<path>::<test name>`: <why it is removed>

     Not covered: <what this evidence does not show>

     ## Merge Danger

     **Door:** <one-way or two-way>

     <optional: description>

     **Blast Radius:** <one-word description>

     <optional: potential ramifications of merge>
     ```
     <!-- rapid-ship:end -->
     ````

  3. Lines 158–164 (the `### Evidence` guidance) become one marked section:

     ```markdown
     <!-- rapid-ship:begin -->
     ### Evidence

     Concrete evidence that the change works. Show a before and after.

     List each command you ran to check the change, with its result copied from real output. Write a skipped, blocked or simulated check as exactly that; it never counts as passed.

     Screenshots are S-tier - when the environment is set up for it and the change is visual.

     Execution-based evidence is A-tier. Test results, console output. Show the exact test that now fails and passes, using pseudocode.

     When the change deletes a test, list it under `Removed tests:` as `<path>::<test name>` with a one-line reason. A test moved to another file is not removed. Leave out `Removed tests:` when no test is removed. `devctl check` fails a PR that removes a test without listing it.

     End the section with one line that starts `Not covered:` and names what the evidence does not show, such as a platform, a live service or a test tier that did not run.
     <!-- rapid-ship:end -->
     ```

- [ ] **Step 5: Lock entries.** Add `"rs-pr"` to `forked`, and these entries. `49dd158…` stands for the full `49dd158d1076134a641b33efb035946536778336`; write full SHAs in the lock.

| path | `upstream_repository` | `upstream_path` | `upstream_commit` | `upstream_blob` | status |
| --- | --- | --- | --- | --- | --- |
| `.agents/skills/rs-pr/SKILL.md` | `mattpocock/skills` | `skills/engineering/pr/SKILL.md` | `49dd158…` (full SHA) | `84dd4fb2f068e9f6282690235d20dd505b418119` | patched |
| `.agents/skills/rs-pr/CREDITS.md` | `mattpocock/skills` | `skills/engineering/pr/CREDITS.md` | `49dd158…` | `5314bda2fa6005e264c9b5c1de7c425e719dc91f` | verbatim |
| `.agents/skills/rs-pr/agents/openai.yaml` | `mattpocock/skills` | `skills/engineering/pr/agents/openai.yaml` | `49dd158…` | `48286f48f53b937cc19c0e39899b5f956271a98d` | verbatim |
| `.agents/skills/rs-pr/LICENSE` | `mattpocock/skills` | `LICENSE` | `49dd158…` | `f1dd2c09108dde1a5f56097cee8461b3ea834499` | verbatim |
| `.agents/skills/rs-pr/HUMANLAYER-LICENSE` | `humanlayer/skills` | `LICENSE` | `653b6411c1f70c275a18e37673b042ff99f67ceb` | `f7ad6f4a1d5ed9bbf0589c172c6360587d1530e3` | verbatim |

The front matter URL names `humanlayer/skills`, so `test_borrowed_text_carries_its_licence` requires the HumanLayer entry.

- [ ] **Step 6: Run the tests.** `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py -q`. Expected: all pass.

- [ ] **Step 7: Vendor and commit.**

```bash
uv run rapid-ship sync --in-place && uv run rapid-ship status --strict
git add rapid_ship/upstream.lock rapid_ship/templates/common/.agents/skills/rs-pr tests/fixtures/upstream tests/test_kit_skills.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: fork pr into the Kit with rapid-ship evidence" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: `rs-writing` and `rs-ponytail`

These move this repository's own guidance into the Kit. They are not upstream forks, so they have no lock entries; their MIT notices travel with them.

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-writing/{SKILL.md,SOURCES.md,TECHNICAL-ENGLISH-LICENSE.txt,ASD-STE100-SKILL-LICENSE.txt}`
- Create: `rapid_ship/templates/common/.agents/skills/rs-ponytail/{SKILL.md,PONYTAIL-LICENSE.txt}`
- Modify: `tests/test_kit_skills.py`
- Modify (generated): `.agents/skills/rs-writing`, `.agents/skills/rs-ponytail`, their `.claude/skills` links, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: `rapid_ship/skills/rapid-ship-engineering/references/writing.md`, `references/ponytail.md`, `SOURCES.md` and the three licence files, which plan 1 keeps.
- Produces: `.agents/skills/rs-writing/SKILL.md` and `.agents/skills/rs-ponytail/SKILL.md`, the paths root `AGENTS.md` points to after Task 10.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_kit_skills.py`:

```python
OTHER_LICENCES = {
    "rs-ponytail": ("PONYTAIL-LICENSE.txt",),
    "rs-writing": ("TECHNICAL-ENGLISH-LICENSE.txt", "ASD-STE100-SKILL-LICENSE.txt"),
}


@pytest.mark.parametrize(("skill", "names"), sorted(OTHER_LICENCES.items()))
def test_adapted_guidance_carries_mit_notices(skill: str, names: tuple[str, ...]) -> None:
    for name in names:
        notice = (SKILLS / skill / name).read_text()
        assert "Permission is hereby granted, free of charge" in notice
        assert re.search(r"^Copyright \(c\) \d{4} \S", notice, re.MULTILINE)
```

- [ ] **Step 2: Run it.** `uv run pytest tests/test_kit_skills.py -q -k mit_notices`. Expected: 2 failures with `FileNotFoundError`.

- [ ] **Step 3: Create `rs-writing`.**
  - `SKILL.md`: this front matter, one blank line, then the body of `references/writing.md` unchanged except its last line's link. `[sources and licenses](../SOURCES.md)` (`writing.md:37`) becomes `[sources and licenses](SOURCES.md)`.

    ```markdown
    ---
    name: rs-writing
    description: Clear technical writing. Use before writing commits, PRs, reviews, documentation, code comments or agent reports.
    ---
    ```

  - `SOURCES.md`: the "Technical writing" section of the old `SOURCES.md` (lines 20–29) under the title `# Sources and licences`. Its first sentence becomes "This skill adapts these MIT-licensed skills:". Keep both bullets, both pinned links and the closing paragraphs.
  - Copy `TECHNICAL-ENGLISH-LICENSE.txt` and `ASD-STE100-SKILL-LICENSE.txt` byte for byte.

- [ ] **Step 4: Create `rs-ponytail`.**
  - `SKILL.md`: this front matter, one blank line, then the body of `references/ponytail.md`. `[PONYTAIL-LICENSE.txt](../PONYTAIL-LICENSE.txt)` (`ponytail.md:3`) becomes `[PONYTAIL-LICENSE.txt](PONYTAIL-LICENSE.txt)`.

    ```markdown
    ---
    name: rs-ponytail
    description: Small, complete changes. Use before coding or reviewing a change.
    ---
    ```

  - `PONYTAIL-LICENSE.txt`: copy it, changing only line 5 from `references/ponytail.md adapts …` to `SKILL.md adapts …`.

- [ ] **Step 5: Check the move.** Each diff must show only the front matter and the one link:
  `diff <(sed '1,5d' rapid_ship/templates/common/.agents/skills/rs-writing/SKILL.md) rapid_ship/skills/rapid-ship-engineering/references/writing.md` and `diff <(sed '1,5d' rapid_ship/templates/common/.agents/skills/rs-ponytail/SKILL.md) rapid_ship/skills/rapid-ship-engineering/references/ponytail.md`.

- [ ] **Step 6: Run the tests.** `uv run pytest tests/test_kit_skills.py tests/test_kit_upstream.py -q`. Expected: all pass.

- [ ] **Step 7: Vendor and commit.**

```bash
uv run rapid-ship sync --in-place && uv run rapid-ship status --strict
git add rapid_ship/templates/common/.agents/skills/rs-writing rapid_ship/templates/common/.agents/skills/rs-ponytail tests/test_kit_skills.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: move writing and ponytail guidance into Kit skills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: `rapid-ship adopt`

**Files:**
- Create: `rapid_ship/kit/adopt.py`
- Modify: `rapid_ship/cli.py`; the README command list, if it lists rapid-ship's commands (`grep -n "rapid-ship sync" README.md`)
- Test: `tests/test_kit_adopt.py`

**Interfaces:**
- Consumes (plan 2): `LOCK_PATH`, `read_lock(root: Path) -> Lock`, `Lock(kit_version, stack, variables, entries)` with `Lock.stack`, `Lock.variables` and `Lock.entries`, `LockEntry.path`, `LockEntry.kind`, `write_lock(root: Path, lock: Lock) -> None`, `Stack`, `KitError`; from `rapid_ship/kit/templates.py` (plan 2 Task 2), `read_excluded(root: Path) -> tuple[str, ...]`, the normalised `[kit] exclude` of `.rapid-ship/project.toml`, which raises `KitError` when that file cannot be read, and `is_excluded(path: str, excluded: Sequence[str]) -> bool`, under which an excluded directory covers its files; `git(root: Path, *args: str, stdin: bytes | None = None, allowed: tuple[int, ...] = (0,)) -> bytes` and `is_clean(root: Path) -> bool` from `rapid_ship/kit/git.py`; `atomic_replace(path: Path, content: bytes, *, mode: int = 0o600) -> None`; `rapid_ship.cli.build_parser()` and `main(argv: Sequence[str] | None = None) -> int`. Also `tomli_w.dumps`, and the rule definitions of plan 3's `comment_rules`, `marker_rules` and `text_rules`, which `adopt` copies. Tests use plan 3's `new_workspace(path: Path) -> Workspace` from `tests/devctl/check_workspace.py`, whose `Workspace` has `root`, `write(path, text)`, `git(*args)` and `commit(message)`.
- Produces:

```python
# rapid_ship/kit/adopt.py
EXCEPTIONS_PATH = ".rapid-ship/exceptions.toml"
REMOVE_WHEN = "Remove when this code next changes"


class AdoptRefused(Exception): ...  # precondition failed; nothing written


@dataclass(frozen=True)
class Suppression:
    path: str  # project-relative POSIX path
    line: int  # 1-based
    rule: str  # one rule, named as in the table below


@dataclass(frozen=True)
class Adopted:
    id: str  # "EX-<n>"
    suppression: Suppression


def find_suppressions(path: str, source: str) -> list[Suppression]: ...
def adopt_suppressions(root: Path, today: date) -> list[Adopted]: ...
```

CLI: `rapid-ship adopt`, no arguments. Exit 0 when it adopted suppressions or found none; 1 when refused; 2 when it could not run.

**Suppressions and rule names.** These copy the Python rows of plan 3's exceptions table (plan 3, Task 7). Plan 3's `_line_errors` matches each marker's entry against one rule on its line, so a line with two rules needs two markers and two entries. One `Suppression` is one rule on one line.

| On the line | Rule name |
| --- | --- |
| `# noqa`, `# noqa: e501, F401`, `# ruff: noqa`, `# flake8: noqa: E501` | `noqa`, or the codes upper-cased, sorted and joined by `,` (`E501,F401`) |
| `# type: ignore`, `# type: ignore[call-arg, arg-type]` | `type-ignore`, or the codes sorted and joined by `,` (`arg-type,call-arg`) |
| `# mypy: ignore-errors`, `# mypy: disable-error-code=...` | `mypy:ignore-errors`, `mypy:disable-error-code` |
| `# pragma: no cover` | `no-cover` |
| gitleaks's inline allow comment | `gitleaks`, once per occurrence |
| `pytest.mark.skip`, `skipif`, `xfail`, also as `mark.*` | `skip`, `skipif`, `xfail` |
| `pytest.skip()`, `pytest.xfail()`, `pytest.importorskip()` | `skip`, `xfail`, `importorskip` |

On one line the rules come in plan 3's order: noqa, type-ignore, mypy and no-cover matches, then gitleaks, then markers in source order. So `# type: ignore[arg-type]  # noqa: E501` gives `E501`, then `arg-type`. Comments are read as comment tokens and markers from the syntax tree, so text inside a string is never a suppression. A line whose comment already carries `rs-exception: EX-<n>` is already adopted. When it is only partly marked, `./devctl check` names the rule left over, and the owner marks it by hand (`rs-setup` step 5, existing project, item 7).

The rules are copied, not imported: the rapid-ship CLI cannot import the vendored devctl. `tests/devctl/test_devctl_adopt_rules.py` (Task 6) runs both on one source and fails when they differ.

- [ ] **Step 1: Check the code `adopt` builds on.**
  1. Read `rapid_ship/kit/git.py`, `rapid_ship/kit/lock.py`, `rapid_ship/kit/templates.py`, `rapid_ship/files.py`, `rapid_ship/cli.py` and `tests/devctl/check_workspace.py`. Confirm: `git()` passes `--literal-pathspecs` and returns bytes; `is_clean()` exists; `Lock` takes `variables` third; `read_excluded(root)` reads `[kit] exclude` from `.rapid-ship/project.toml` and `is_excluded(path, excluded)` matches an entry or a path below one; `atomic_replace` takes `mode`; `main(argv: Sequence[str] | None = None) -> int` maps `KitRefusal` to exit 1 and `KitError` to exit 2; and `new_workspace` returns a `Workspace` with `write`, `git` and `commit`. `adopt` uses `git()` and `is_clean()`, with no git helper of its own. Under `--literal-pathspecs` a `'*.py'` pathspec matches only a file named `*.py`, so `adopt` lists every tracked file and filters in Python.
  2. Read `comment_rules`, `marker_rules` and `_codes` in `tools/devctl/devctl/check/stacks/python.py`, and `text_rules` in `stacks/neutral.py`. The patterns in step 4 copy them as plan 3 wrote them. If the vendored copy differs, copy the vendored version.

- [ ] **Step 2: Write the failing tests.** Create `tests/test_kit_adopt.py`:

```python
"""`rapid-ship adopt` against temporary git repositories (offline)."""

import json
import tomllib
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from check_workspace import Workspace, new_workspace
from rapid_ship.cli import main
from rapid_ship.kit.adopt import AdoptRefused, adopt_suppressions, find_suppressions
from rapid_ship.kit.lock import Lock, LockEntry, write_lock
from rapid_ship.kit.templates import Stack

SETUP_DAY = date(2026, 10, 14)
HEADER = "# Break-glass exceptions. The owner approves each entry.\n"
MANAGED = LockEntry(
    path="tools/devctl/devctl/cli.py",
    kind="managed",
    sha256="0" * 64,
    link=None,
    template_sha256=None,
)
LEGACY = (
    "import subprocess\n"
    "\n"
    "\n"
    "def run(command: list[str]) -> None:\n"
    "    subprocess.run(command)  # noqa: S603\n"
    "\n"
    "\n"
    "def value() -> int:\n"
    '    return "x"  # type: ignore[return-value]  # noqa: E501\n'
    "\n"
    "\n"
    'if __name__ == "__main__":  # pragma: no cover\n'
    '    run(["true"])\n'
)
LEGACY_TESTS = (
    "import pytest\n"
    "\n"
    "\n"
    '@pytest.mark.skip(reason="flaky upstream")\n'
    "def test_one() -> None:\n"
    "    pass\n"
    "\n"
    "\n"
    "def test_two() -> None:\n"
    '    pytest.xfail("known bug")\n'
)


def project(
    tmp_path: Path,
    files: dict[str, str],
    *,
    stack: Stack = "python",
    exceptions: str = HEADER,
    exclude: Sequence[str] = (),
) -> Workspace:
    workspace = new_workspace(tmp_path / "project")
    write_lock(workspace.root, Lock("0.2.0", stack, {}, (MANAGED,)))
    # A JSON list of strings is a TOML array.
    kit = f"[kit]\nexclude = {json.dumps(list(exclude))}\n"
    workspace.write(".rapid-ship/project.toml", f'stack = "{stack}"\n\n{kit}')
    workspace.write(".rapid-ship/exceptions.toml", exceptions)
    for path, text in files.items():
        workspace.write(path, text)
    workspace.commit("existing project")
    return workspace


def listed(root: Path) -> list[dict[str, str]]:
    document = tomllib.loads((root / ".rapid-ship/exceptions.toml").read_text())
    entries: list[dict[str, str]] = document["exception"]
    return entries


def test_adopt_marks_each_suppression_and_lists_it(tmp_path: Path) -> None:
    root = project(tmp_path, {"legacy.py": LEGACY, "tests/test_legacy.py": LEGACY_TESTS}).root

    adopted = adopt_suppressions(root, SETUP_DAY)

    assert [
        (a.id, a.suppression.path, a.suppression.line, a.suppression.rule) for a in adopted
    ] == [
        ("EX-1", "legacy.py", 5, "S603"),
        ("EX-2", "legacy.py", 9, "E501"),
        ("EX-3", "legacy.py", 9, "return-value"),
        ("EX-4", "legacy.py", 12, "no-cover"),
        ("EX-5", "tests/test_legacy.py", 4, "skip"),
        ("EX-6", "tests/test_legacy.py", 10, "xfail"),
    ]
    legacy = (root / "legacy.py").read_text().splitlines()
    assert legacy[4] == "    subprocess.run(command)  # noqa: S603  # rs-exception: EX-1"
    assert legacy[8] == (
        '    return "x"  # type: ignore[return-value]  # noqa: E501'
        "  # rs-exception: EX-2  # rs-exception: EX-3"
    )
    assert (root / "tests/test_legacy.py").read_text().splitlines()[3] == (
        '@pytest.mark.skip(reason="flaky upstream")  # rs-exception: EX-5'
    )
    assert listed(root)[0] == {
        "id": "EX-1",
        "path": "legacy.py",
        "rule": "S603",
        "reason": "Existed at Setup on 2026-10-14",
        "remove_when": "Remove when this code next changes",
    }
    assert [entry["id"] for entry in listed(root)] == [f"EX-{n}" for n in range(1, 7)]
    assert listed(root)[2]["rule"] == "return-value"
    assert (root / ".rapid-ship/exceptions.toml").read_text().startswith(HEADER)


def test_adopt_twice_adds_nothing(tmp_path: Path) -> None:
    workspace = project(tmp_path, {"legacy.py": LEGACY})
    root = workspace.root
    adopt_suppressions(root, SETUP_DAY)
    workspace.commit("adopt existing suppressions")
    before = {
        path: (root / path).read_bytes() for path in ("legacy.py", ".rapid-ship/exceptions.toml")
    }

    assert adopt_suppressions(root, SETUP_DAY) == []
    assert {path: (root / path).read_bytes() for path in before} == before


def test_adopt_continues_after_existing_ids(tmp_path: Path) -> None:
    existing = HEADER + (
        '\n[[exception]]\nid = "EX-7"\npath = "legacy.py"\nrule = "S603"\n'
        'reason = "Runs a fixed tool"\nremove_when = "The tool has an API"\n'
    )
    marked = LEGACY.replace("# noqa: S603", "# noqa: S603  # rs-exception: EX-7")
    root = project(tmp_path, {"legacy.py": marked}, exceptions=existing).root

    assert [a.id for a in adopt_suppressions(root, SETUP_DAY)] == ["EX-8", "EX-9", "EX-10"]
    assert (root / ".rapid-ship/exceptions.toml").read_text().startswith(existing)


def test_adopt_refuses_a_dirty_tree(tmp_path: Path) -> None:
    workspace = project(tmp_path, {"legacy.py": LEGACY})
    workspace.write("notes.txt", "draft\n")

    with pytest.raises(AdoptRefused, match="work tree has changes"):
        adopt_suppressions(workspace.root, SETUP_DAY)
    assert (workspace.root / "legacy.py").read_text() == LEGACY


def test_adopt_refuses_without_a_lock(tmp_path: Path) -> None:
    workspace = project(tmp_path, {"legacy.py": LEGACY})
    workspace.git("rm", "-q", ".rapid-ship/kit.lock")
    workspace.commit("drop the lock")

    with pytest.raises(AdoptRefused, match="kit.lock is missing"):
        adopt_suppressions(workspace.root, SETUP_DAY)


def test_adopt_leaves_kit_files_and_strings_alone(tmp_path: Path) -> None:
    kit_file = "x = 1  # noqa: E501\n"
    message = 'MESSAGE = "silence it with # noqa: E501"\n'
    root = project(tmp_path, {"tools/devctl/devctl/cli.py": kit_file, "app.py": message}).root

    assert adopt_suppressions(root, SETUP_DAY) == []
    assert (root / "tools/devctl/devctl/cli.py").read_text() == kit_file
    assert (root / "app.py").read_text() == message


def test_adopt_marks_a_kit_file_the_project_excluded(tmp_path: Path) -> None:
    # [kit] exclude in project.toml is the only record of an exclusion; the lock entry has no mark.
    # The project owns the excluded Kit file, so devctl's exceptions step scans it.
    kit_file = {"tools/devctl/devctl/cli.py": "x = 1  # noqa: E501\n"}
    root = project(tmp_path, kit_file, exclude=["tools/devctl"]).root

    adopted = adopt_suppressions(root, SETUP_DAY)

    assert [(a.id, a.suppression.path, a.suppression.rule) for a in adopted] == [
        ("EX-1", "tools/devctl/devctl/cli.py", "E501")
    ]


def test_adopt_refuses_a_marker_that_would_change_code(tmp_path: Path) -> None:
    source = (
        'import pytest\n\n\n@pytest.mark.skip(reason="""spans\ntwo lines""")\n'
        "def test_one() -> None:\n    pass\n"
    )
    root = project(tmp_path, {"test_multi.py": source}).root

    with pytest.raises(AdoptRefused, match="test_multi.py: a marker on line 4 would change code"):
        adopt_suppressions(root, SETUP_DAY)
    assert (root / "test_multi.py").read_text() == source
    assert "[[exception]]" not in (root / ".rapid-ship/exceptions.toml").read_text()


def test_adopt_keeps_file_modes(tmp_path: Path) -> None:
    workspace = project(tmp_path, {"legacy.py": LEGACY})
    (workspace.root / "legacy.py").chmod(0o755)
    workspace.commit("make legacy.py executable")

    adopt_suppressions(workspace.root, SETUP_DAY)

    assert (workspace.root / "legacy.py").stat().st_mode & 0o777 == 0o755


def test_adopt_has_nothing_to_do_for_the_neutral_stack(tmp_path: Path) -> None:
    root = project(tmp_path, {"legacy.py": LEGACY}, stack="neutral").root

    assert adopt_suppressions(root, SETUP_DAY) == []
    assert (root / "legacy.py").read_text() == LEGACY


@pytest.mark.parametrize(
    ("source", "rules"),
    [
        ("x = 1  # noqa\n", ["noqa"]),
        ("x = 1  # noqa: F401, e501\n", ["E501,F401"]),
        ("x = 1  # NOQA:E501\n", ["E501"]),
        ("# ruff: noqa\n", ["noqa"]),
        ("# flake8: noqa: E501\n", ["E501"]),
        ("x = f()  # type: ignore\n", ["type-ignore"]),
        ("x = f()  # type: ignore[call-arg, arg-type]\n", ["arg-type,call-arg"]),
        ("x = f()  # type: ignore[arg-type]  # noqa: E501\n", ["E501", "arg-type"]),
        ("# mypy: ignore-errors\n", ["mypy:ignore-errors"]),
        ('# mypy: disable-error-code="arg-type"\n', ["mypy:disable-error-code"]),
        ("if x:  # pragma: no cover\n    pass\n", ["no-cover"]),
        ("KEY = 'k'  # gitleaks" + ":allow\n", ["gitleaks"]),
        (
            "@pytest.mark.skipif(True, reason='r')  # noqa: E501\ndef test_a():\n    pass\n",
            ["E501", "skipif"],
        ),
        ("pytestmark = mark.xfail\n", ["xfail"]),
        ("yaml = pytest.importorskip('yaml')\n", ["importorskip"]),
    ],
)
def test_rule_names(source: str, rules: list[str]) -> None:
    # The gitleaks case is split so that documents quoting this test hold no allow comment.
    assert [s.rule for s in find_suppressions("a.py", source)] == rules


def test_cli_lists_adopted_suppressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project(tmp_path, {"legacy.py": LEGACY}).root)

    assert main(["adopt"]) == 0

    out = capsys.readouterr().out
    assert "EX-1  legacy.py:5  S603" in out
    assert "Adopted 4 suppressions." in out


def test_cli_refuses_a_dirty_tree_with_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = project(tmp_path, {"legacy.py": LEGACY})
    workspace.write("notes.txt", "draft\n")
    monkeypatch.chdir(workspace.root)

    assert main(["adopt"]) == 1
    assert "work tree has changes" in capsys.readouterr().err
```

The scratch repositories come from plan 3's `new_workspace`, whose git commands run through `run_process` with a fixed identity and no hooks, so this file starts no process itself.

- [ ] **Step 3: Run them.** `uv run pytest tests/test_kit_adopt.py -q`. Expected: collection fails with `ModuleNotFoundError: No module named 'rapid_ship.kit.adopt'`.

- [ ] **Step 4: Implement `rapid_ship/kit/adopt.py`.**

```python
"""`rapid-ship adopt`: list an existing project's suppressions as exceptions, once, at Setup."""

import ast
import os
import re
import stat
import tokenize
import tomllib
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

import tomli_w

from rapid_ship.files import atomic_replace
from rapid_ship.kit.git import git, is_clean
from rapid_ship.kit.lock import LOCK_PATH, read_lock
from rapid_ship.kit.templates import is_excluded, read_excluded

EXCEPTIONS_PATH = ".rapid-ship/exceptions.toml"
REMOVE_WHEN = "Remove when this code next changes"

_ID = re.compile(r"EX-(\d+)")
_MARKER = re.compile(r"rs-exception:\s*EX-(\d+)")
# Copied from devctl/check/stacks/python.py and neutral.py, which this package cannot import.
# tests/devctl/test_devctl_adopt_rules.py fails when the copies differ.
_NOQA = re.compile(
    r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa\b"
    r"(?::\s*(?P<codes>[A-Za-z]+[0-9]+(?:[\s,]+[A-Za-z]+[0-9]+)*))?",
    re.IGNORECASE,
)
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\b(?:\[(?P<codes>[^\]]*)\])?")
_MYPY = re.compile(r"#\s*mypy:\s*(?P<setting>ignore-errors|disable-error-code)")
_NO_COVER = re.compile(r"#\s*pragma:\s*no\s+cover", re.IGNORECASE)
# Split so that documents quoting this code hold no gitleaks allow comment.
_GITLEAKS_ALLOW = "gitleaks" + ":allow"
_SKIP_MARKS = frozenset({"skip", "skipif", "xfail"})
_SKIP_CALLS = frozenset({"skip", "xfail", "importorskip"})


class AdoptRefused(Exception):
    """A precondition failed or a marker would change code. Nothing was written."""


@dataclass(frozen=True)
class Suppression:
    path: str
    line: int
    rule: str


@dataclass(frozen=True)
class Adopted:
    id: str
    suppression: Suppression


def find_suppressions(path: str, source: str) -> list[Suppression]:
    """Unmarked suppressions in one Python file: one per rule, in line then rule order."""
    try:
        comments = {
            token.start[0]: token.string
            for token in tokenize.generate_tokens(StringIO(source).readline)
            if token.type == tokenize.COMMENT
        }
    except (tokenize.TokenError, SyntaxError) as error:
        raise AdoptRefused(f"{path}: cannot read as Python: {error}") from error
    rules = {line: _comment_rules(text) for line, text in comments.items()}
    for line, rule in _marker_rules(source):
        rules.setdefault(line, []).append(rule)
    return [
        Suppression(path, line, rule)
        for line, found in sorted(rules.items())
        if not _MARKER.search(comments.get(line, ""))
        for rule in found
    ]


def adopt_suppressions(root: Path, today: date) -> list[Adopted]:
    """Give each unmarked suppression rule a new ID and list it in exceptions.toml.

    A clean work tree is required, so `git checkout .` undoes a run. Only comments
    change: each rewritten file must parse to the same syntax tree as before.
    """
    if not (root / LOCK_PATH).is_file():
        raise AdoptRefused(f"{LOCK_PATH} is missing; run `rapid-ship init` first")
    if not is_clean(root):
        raise AdoptRefused("the work tree has changes; commit them first")
    exceptions = root / EXCEPTIONS_PATH
    if not exceptions.is_file():
        raise AdoptRefused(f"{EXCEPTIONS_PATH} is missing")
    lock = read_lock(root)
    if lock.stack != "python":
        return []
    # [kit] exclude is the only record of an exclusion, so read it from project.toml, never
    # from the lock. An excluded Kit file is the project's, and devctl's exceptions step scans it.
    excluded = read_excluded(root)
    managed = {
        e.path for e in lock.entries if e.kind == "managed" and not is_excluded(e.path, excluded)
    }
    listed_text = exceptions.read_text(encoding="utf-8")
    listed = tomllib.loads(listed_text).get("exception", [])
    used = {int(m.group(1)) for e in listed if (m := _ID.fullmatch(str(e.get("id", ""))))}
    sources: dict[str, str] = {}
    found: list[Suppression] = []
    # git() passes --literal-pathspecs, where '*.py' would match only a file of that name.
    for raw in git(root, "ls-files", "-z").split(b"\0"):
        path = os.fsdecode(raw)
        if not path.endswith((".py", ".pyi")) or path in managed:
            continue
        if (root / path).is_symlink():
            raise AdoptRefused(f"{path} is a symlink; adopt edits regular files only")
        try:
            source = (root / path).read_bytes().decode("utf-8")
        except UnicodeDecodeError as error:
            raise AdoptRefused(f"{path} is not UTF-8") from error
        sources[path] = source
        used.update(int(number) for number in _MARKER.findall(source))
        found.extend(find_suppressions(path, source))
    first = max(used, default=0) + 1
    adopted = [Adopted(f"EX-{first + offset}", item) for offset, item in enumerate(found)]
    if not adopted:
        return []
    rewritten = {
        path: _mark(path, sources[path], [a for a in adopted if a.suppression.path == path])
        for path in dict.fromkeys(a.suppression.path for a in adopted)
    }
    reason = f"Existed at Setup on {today.isoformat()}"
    entries = [
        {
            "id": item.id,
            "path": item.suppression.path,
            "rule": item.suppression.rule,
            "reason": reason,
            "remove_when": REMOVE_WHEN,
        }
        for item in adopted
    ]
    updated = _append(listed_text, entries, len(listed))
    for path, text in rewritten.items():
        _replace(root / path, text)
    _replace(exceptions, updated)
    return adopted


def _comment_rules(comment: str) -> list[str]:
    """devctl's comment_rules plus text_rules on one comment, in devctl's order."""
    rules = [_codes(m.group("codes"), upper=True) or "noqa" for m in _NOQA.finditer(comment)]
    rules += [_codes(m.group("codes")) or "type-ignore" for m in _TYPE_IGNORE.finditer(comment)]
    rules += [f"mypy:{m.group('setting')}" for m in _MYPY.finditer(comment)]
    rules += ["no-cover" for _ in _NO_COVER.finditer(comment)]
    return rules + ["gitleaks"] * comment.count(_GITLEAKS_ALLOW)


def _codes(text: str | None, *, upper: bool = False) -> str:
    parts = [part for part in re.split(r"[\s,]+", text or "") if part]
    return ",".join(sorted(part.upper() if upper else part for part in parts))


def _marker_rules(source: str) -> list[tuple[int, str]]:
    """devctl's marker_rules, sorted by position so that IDs follow the source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # _mark refuses the file if it needs a marker
    found: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _SKIP_MARKS:
            if _dotted(node.value) in ("pytest.mark", "mark"):
                found.append((node.lineno, node.col_offset, node.attr))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _SKIP_CALLS and _dotted(node.func.value) == "pytest":
                found.append((node.lineno, node.col_offset, node.func.attr))
    return [(line, rule) for line, _, rule in sorted(found)]
```

Private helpers, in the same module:
  - `_dotted(node: ast.expr) -> str`: joins `Name` and `Attribute` chains such as `pytest.mark`, and returns `""` for anything else, as devctl's `_dotted` does.
  - `_mark(path: str, source: str, items: list[Adopted]) -> str`: split `source` on `"\n"` only. Group the items by line. To each line, before any trailing `"\r"`, append `  # rs-exception: <id>` once per item, in item order, so a line with two rules ends `  # rs-exception: EX-2  # rs-exception: EX-3`. Join with `"\n"`. Add this comment in the code: `str.splitlines` also splits on form feeds, which tokenize does not count as line ends, so line numbers would drift. Compare `ast.dump(ast.parse(...))` before and after; on a difference or a `SyntaxError`, raise `AdoptRefused(f"{path}: a marker on line {lines} would change code; mark it by hand")`, where `lines` joins the distinct line numbers with ", ".
  - `_append(text: str, entries: list[dict[str, str]], before: int) -> str`: write each entry as `"[[exception]]\n" + tomli_w.dumps(entry)`, join them with blank lines, and add them after `text`, separated by one blank line when `text` has content. Comment: `tomli_w.dumps({"exception": entries})` is not used because tomli-w 1.2.0 writes a short array of tables inline (`exception = [{ … }]`), which cannot follow existing `[[exception]]` tables. Parse the result with `tomllib`; if it does not hold `before + len(entries)` exceptions, raise `AdoptRefused`.
  - `_replace(path: Path, text: str) -> None`: `atomic_replace(path, text.encode("utf-8"), mode=stat.S_IMODE(path.stat().st_mode))`. Comment: `atomic_replace` publishes `0o600` by default, and the project's mode must survive.

- [ ] **Step 5: Wire the command.** In `rapid_ship/cli.py`, add an `adopt` subparser the way plan 2 added `status`, with help text "Mark existing suppressions as listed exceptions, once, at Setup". Its handler:

```python
def _adopt(root: Path) -> int:
    try:
        adopted = adopt_suppressions(root, datetime.now(UTC).date())
    except AdoptRefused as refusal:
        sys.stderr.write(f"rapid-ship adopt: {refusal}\n")
        return 1
    except (KitError, OSError, ValueError) as error:
        sys.stderr.write(f"rapid-ship adopt: could not run: {error}\n")
        return 2
    if not adopted:
        sys.stdout.write("Nothing to adopt: every suppression already has an rs-exception ID.\n")
        return 0
    for item in adopted:
        found = item.suppression
        sys.stdout.write(f"{item.id}  {found.path}:{found.line}  {found.rule}\n")
    sys.stdout.write(f"Adopted {len(adopted)} suppressions. Review them in the Setup PR.\n")
    return 0
```

`KitError` comes from `read_lock`, from `read_excluded` when `project.toml` is missing or invalid, and from `git()`. `ValueError` covers `tomllib.TOMLDecodeError`. In `main`, dispatch `adopt` to `_adopt(root)` after plan 2's `work_tree_root` call, as `status` is dispatched. Add `adopt` to the README command list if it has one.

- [ ] **Step 6: Run the tests.** `uv run pytest tests/test_kit_adopt.py -q`. Expected: 27 passed (10 `adopt` tests, 15 `test_rule_names` cases, 2 CLI tests). Then `./devctl check --tier fast`. Expected: exit 0. If its exceptions step flags suppression text inside the string literals of `tests/test_kit_adopt.py` or `adopt.py`, the step reads raw lines rather than comment tokens. Stop and report it: the fix belongs in plan 3's step, not in these tests.

- [ ] **Step 7: Commit.**

```bash
git add rapid_ship/kit/adopt.py rapid_ship/cli.py tests/test_kit_adopt.py README.md
git commit -m "feat: add rapid-ship adopt" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: `adopt` against devctl's exceptions step (offline)

**Files:**
- Test: `tests/devctl/test_devctl_adopt_rules.py`, `tests/test_kit_adopt_integration.py`

**Interfaces:**
- Consumes: `find_suppressions` and `rapid-ship adopt` (Task 5); `rapid-ship init --stack python` (plan 2); from plan 3, Task 7, `scan(root: Path, files: Sequence[str], managed: frozenset[str], stack: str) -> list[SuppressedLine]` with `SuppressedLine.number` and `.rules`, and `./devctl check --tier fast --json`, whose entries carry the `StepResult` fields `name`, `status` and `details`; from plan 3, Tasks 1 and 2, `run_process(argv, cwd, timeout_seconds, env=None, input_text=None) -> ProcessResult` and `new_workspace`.
- Produces: proof that `adopt` finds and names the rules the exceptions step requires, and that its markers and entries pass that step.

- [ ] **Step 1: Check plan 3's shapes.**
  1. Run `./devctl check --tier fast --json` in this repository. Confirm stdout is a JSON list of objects with `name`, `status` and `details`. If plan 3 wraps the list, index into the wrapper in the integration test's last lines.
  2. Read `scan` in `tools/devctl/devctl/check/exceptions.py`. Confirm it reads each of `files` as a path relative to `root`. If it takes paths another way, adapt the `scan` call in the parity test and keep its comparison unchanged.

- [ ] **Step 2: Write the parity test.** Create `tests/devctl/test_devctl_adopt_rules.py`. pytest's `pythonpath` puts `tools/devctl` on `sys.path` (plan 3 Task 2), so this test can import both packages.

```python
"""Offline: adopt finds the rules devctl's exceptions step requires, line by line."""

from pathlib import Path

from devctl.check.exceptions import scan
from rapid_ship.kit.adopt import find_suppressions

# The gitleaks line is split so that documents quoting this test hold no allow comment.
SOURCE = (
    "# ruff: noqa: E501\n"
    '# mypy: disable-error-code="arg-type"\n'
    "import pytest\n"
    "from pytest import mark\n"
    "\n"
    "yaml = pytest.importorskip('yaml')  # noqa: f401\n"
    "pytestmark = mark.xfail\n"
    "x = f()  # type: ignore[call-arg, arg-type]  # noqa: E501, F821\n"
    "KEY = 'k'  # gitleaks" + ":allow  # NOQA\n"
    "TEXT = '# noqa: E501  # type: ignore'\n"
    "\n"
    "\n"
    "@pytest.mark.skipif(\n"
    "    True, reason='r'\n"
    ")\n"
    "def test_a() -> None:  # pragma: no cover\n"
    "    pytest.skip('later')\n"
    "    pytest.xfail('known')  # mypy: ignore-errors\n"
)


def test_adopt_finds_what_the_exceptions_step_requires(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_all.py").write_text(SOURCE)
    required = {
        line.number: sorted(line.rules)
        for line in scan(tmp_path, ["tests/test_all.py"], frozenset(), "python")
        if line.rules
    }
    found: dict[int, list[str]] = {}
    for item in find_suppressions("tests/test_all.py", SOURCE):
        found.setdefault(item.line, []).append(item.rule)

    assert {line: sorted(rules) for line, rules in found.items()} == required
    assert sorted(required) == [1, 2, 6, 7, 8, 9, 13, 16, 17, 18]
```

- [ ] **Step 3: Write the integration test.** Create `tests/test_kit_adopt_integration.py`:

```python
"""Offline integration test: `rapid-ship init`, `rapid-ship adopt`, then devctl's exceptions step.

It runs real git, the rapid-ship CLI and the vendored devctl through uv with UV_OFFLINE=1,
so devctl's locked dependencies must already be in uv's cache. Running `./devctl` in this
repository puts them there. A missing dependency fails this test; it is never skipped.
"""

import json
import sys
from pathlib import Path

from check_workspace import new_workspace
from devctl.process import ProcessResult, run_process

OFFLINE = {"UV_OFFLINE": "1"}
LEGACY = (
    "import subprocess\n\n\ndef run(command: list[str]) -> None:\n"
    "    subprocess.run(command)  # noqa: S603\n\n\n"
    "def value() -> int:\n"
    '    return "x"  # type: ignore[return-value]  # noqa: E501\n'
)
LEGACY_TESTS = (
    'import pytest\n\nyaml = pytest.importorskip("yaml")\n\n\n'
    '@pytest.mark.skip(reason="flaky upstream")\n'
    "def test_one() -> None:\n    pass\n"
)


def run(root: Path, *argv: str) -> ProcessResult:
    # run_process passes only PATH, HOME and the locale, plus OFFLINE; uv's cache is under HOME.
    return run_process(argv, root, 600, env=OFFLINE)


def test_adopted_suppressions_pass_devctls_exceptions_step(tmp_path: Path) -> None:
    project = new_workspace(tmp_path / "legacy")
    project.write("legacy.py", LEGACY)
    project.write("tests/test_legacy.py", LEGACY_TESTS)
    project.commit("existing project")

    init = run(project.root, sys.executable, "-m", "rapid_ship", "init", "--stack", "python")
    assert init.returncode == 0, init.stderr
    project.commit("add the Kit")
    adopt = run(project.root, sys.executable, "-m", "rapid_ship", "adopt")
    assert adopt.returncode == 0, adopt.stderr
    assert "Adopted 5 suppressions." in adopt.stdout
    project.commit("adopt existing suppressions")

    check = run(project.root, "./devctl", "check", "--tier", "fast", "--json")
    steps = {step["name"]: step for step in json.loads(check.stdout)}
    assert steps["exceptions"]["status"] == "passed", steps["exceptions"]["details"]
```

The five are `S603`, then `E501` and `return-value` on one line, then `importorskip` and `skip`. The test asserts only the exceptions step, the one `adopt` must satisfy; the legacy code is not meant to pass the other steps.

- [ ] **Step 4: Run both red first.** Each change below is temporary; revert it before the next.
  1. Remove `"importorskip"` from `_SKIP_CALLS` in `adopt.py`, then run `uv run pytest tests/devctl/test_devctl_adopt_rules.py -q`. Expected: fails on line 6, where `adopt` finds `["F401"]` and the step requires `["F401", "importorskip"]`.
  2. Change `"rule": item.suppression.rule` in `adopt.py` to `"rule": "wrong"`, then run `uv run pytest tests/test_kit_adopt_integration.py -q`. Expected: fails on the `exceptions` status with details naming a rule mismatch.

  These prove each test can see a disagreement. Revert, and confirm with `git diff --stat rapid_ship/kit/adopt.py` (no output).

- [ ] **Step 5: Run both green.** `uv run pytest tests/devctl/test_devctl_adopt_rules.py tests/test_kit_adopt_integration.py -q`. Expected: 2 passed. If the integration test fails because the seeded `exceptions.toml` holds `exception = []`, `adopt` cannot append tables to it; fix the seed in plan 2's template so it holds comments only, and rerun.

- [ ] **Step 6: Commit.**

```bash
git add tests/devctl/test_devctl_adopt_rules.py tests/test_kit_adopt_integration.py
git commit -m "test: check adopt against devctl's exceptions step" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: `rs-setup`

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-setup/{SKILL.md,ruleset.json,python-guardrails.toml,agents/openai.yaml,LICENSE}`
- Modify: `rapid_ship/upstream.lock` (the `LICENSE` entry), `tests/test_kit_skills.py`
- Test: `tests/devctl/test_devctl_rs_setup_ruleset.py`
- Modify (generated): `.agents/skills/rs-setup`, `.claude/skills/rs-setup`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: `rapid-ship app [--repository OWNER/NAME]` (plan 4 Task 11), which prints each App's ID and install URL and exits 1 when the repository is not on the signed-in owner's personal account; `devctl doctor [--skills]` (plan 4, Tasks 8–10), whose skills probe reports a user-invoked skill as not checked and which reports agy items as unknown inside another coding session; `AGY_PROBE_ARGS: tuple[str, ...]` from `devctl.doctor`, the arguments after `agy` for doctor's sign-in probe (plan 4; Step 1 confirms the name); `ruleset_problems(rulesets: Sequence[Mapping[str, object]], default_branch: str) -> list[str]` from `devctl.doctor` (plan 4, Task 9, which takes rulesets in the shape `GET /repos/{o}/{r}/rulesets/{id}` returns); `rapid-ship adopt` (Task 5); `rapid-ship sync --in-place`, which accepts a dirty work tree and never creates, replaces, merges or deletes a path under `[kit] exclude`, `rapid-ship status`, which classifies such a path as `excluded`, the `[[file]]` entries of `.rapid-ship/kit.lock` with their `kind`, the seeded `pyproject.toml` and `render_files(stack: Stack, variables: Mapping[str, str], optional: Sequence[str], *, root: Path | None = None) -> list[Template]` (plan 2); plan 3's kit step, which no longer requires a managed path listed under `[kit] exclude`, and its exceptions step, which scans that path; `rs-pr` (Task 3).
- Produces: the user-invoked `rs-setup` skill and `ruleset.json`, the body for `POST /repos/{owner}/{repo}/rulesets`.

Facts this task relies on, checked on 2026-10-14:
- `gh api repos/<owner>/<private repo>/rulesets` on the owner's GitHub Free account answers 403 "Upgrade to GitHub Pro or make this repository public to enable this feature." The public `proxy-hatch/rapid-ship` answers `[]`.
- `gh api apps/github-actions` gives `id` 15368.
- `actor_id` 5 is the built-in repository admin role in two public exports (Azure/azure-sdk-tools `eng/branch-rulesets/require-codeowner-approval.json`, kk0ga/opentofu-github-repository docs). GitHub's REST reference does not list role IDs; Task 11 confirms it live.
- The REST reference lists the ruleset fields used below, `bypass_mode` `pull_request` ("bypass rules only on pull requests"), and `PUT /repos/{owner}/{repo}/actions/permissions/fork-pr-contributor-approval` with `approval_policy` `all_external_contributors`.
- `git ls-remote --tags https://github.com/proxy-hatch/rapid-ship refs/tags/v0.2.0` printed nothing and exited 0: the repository had no tags (plan 2's Checked facts). The same command for an existing tag, `https://github.com/astral-sh/uv refs/tags/0.5.0`, printed one line: the commit SHA and `refs/tags/0.5.0`.
- devctl reads an App key with `security`, which wrote the Keychain item, so macOS shows no dialog and any process the owner runs can read both keys (spec section 6; plan 4, Global Constraints, Keys).
- Harness commands: `claude auth status --json` returns `loggedIn` and `authMethod`, which is `claude.ai` for a subscription sign-in (Claude Code 2.1.287; plan 4's Checked facts; the old parser at `archive/controller-2026-10:rapid_ship/project/providers.py:204-213`). `codex login status` writes `Logged in using ChatGPT`, `Not logged in`, or `Logged in using an API key - <masked key>` to stderr (plan 4's Checked facts). `codex exec --model --sandbox read-only --skip-git-repo-check --ephemeral` exists (Codex CLI 0.162.0); agy 1.3.4 has `-p`, `--model`, `--mode plan`, `--print-timeout`, `models` and `mcp`, and no sign-in status command; `agy --help` for agy 1.3.5 still listed no `auth`, `login` or `status` subcommand. `agy models`, started from a Claude Code session, printed nothing within 60 s and was stopped. Which agy model is cheapest was not checked here; plan 4's doctor fixes it in `AGY_PROBE_ARGS`. `claude mcp add --transport http`, `codex mcp add <name> --url` and `agy mcp add <name> <url>` exist with those forms. `claude mcp add --help` lists `-s, --scope <scope>` (local, user or project) with default `local`; `agy mcp add --help` shows no scope flag; whether agy's server reaches another directory was not checked, and Task 11 checks it from a worktree. `codex mcp add --help` names `~/.codex/config.toml` as Codex's configuration, which is per user.
- gitleaks was not installed on the owner's machine (`gitleaks version`: command not found). Plan 3's secrets step is blocked without it, so `./devctl check` exits 2.
- Codex reads `.agents/skills`, requires `name` and `description`, and honours `policy.allow_implicit_invocation` (learn.chatgpt.com/docs/build-skills). agy 1.3.4's changelog describes loading `.agents/skills/` folders. `agy changelog` from agy 1.3.5, read on 2026-10-14, documents the `/skills` panel that Task 11 uses, and, since 1.1.11, `agy -p "/skills"` printing one tab-separated record per skill without starting an agent turn or spending quota.

- [ ] **Step 1: Check doctor's agy probe and skills probe.** Plan 4 owns both, and this skill must use them unchanged.
  1. Read `tools/devctl/devctl/doctor.py`. Confirm that `AGY_PROBE_ARGS` holds the arguments doctor passes after `agy` for its sign-in probe: the prompt `hi`, the cheapest agy model, and headless print mode. If plan 4 gave it another name, use that name in step 2's import. If doctor has no agy probe, stop: plan 4 has not taken in the amended spec section 6.
  2. In the same file, confirm that `--skills` builds its temporary worktree from the remote default branch's head, as `dispatch` does, and reports a skill with `disable-model-invocation: true` as not checked. If it uses another ref, change `origin/<default branch>` in `rs-setup` step 9.3 to that ref.
  3. Run `./devctl doctor --help`. Expected: it lists `--skills`.
  4. Run `uv run --project tools/devctl --frozen python -c "import shlex; from devctl.doctor import AGY_PROBE_ARGS; print('agy', shlex.join(AGY_PROBE_ARGS))"`. Step 7 writes the printed command into `rs-setup` step 2.1.

- [ ] **Step 2: Write the failing tests.** Append to `tests/test_kit_skills.py`:

```python
import json
import shlex
import tomllib

from devctl.doctor import AGY_PROBE_ARGS
from rapid_ship.kit.templates import render_files

VARIABLES = {"project_name": "demo", "package": "demo", "owner": "octo", "repository": "octo/demo"}
WRITE = re.compile(
    r"^(gh (repo create|repo fork|pr create|issue create|label create)\b"
    r"|gh api (-X|--method) (POST|PUT|PATCH|DELETE)\b"
    r"|git (-C \S+ )?push\b"
    r"|uvx\b.*\brapid-ship app\b"
    r"|(claude|codex|agy) mcp add\b)"
)
WRITING = ("rs-setup",)
USER_INVOKED = ("rs-setup",)


def commands(text: str) -> set[str]:
    found = set(re.findall(r"`([^`\n]+)`", text))
    for block in re.findall(r"^```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL):
        found.update(line.strip() for line in block.splitlines())
    return found


def write_rows(text: str) -> list[str]:
    section = text.split("\n## External writes\n", 1)[1].split("\n## ", 1)[0]
    return [
        line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith(("| Step", "| ---"))
    ]


@pytest.mark.parametrize("skill", WRITING)
def test_every_external_write_waits_for_the_owner(skill: str) -> None:
    text = (SKILLS / skill / "SKILL.md").read_text()
    rows = write_rows(text)
    assert rows
    assert "Wait for the owner's explicit yes. One yes covers one write." in text
    listed = {span for row in rows for span in re.findall(r"`([^`\n]+)`", row.split(" | ")[1])}
    writes = {command for command in commands(text) if WRITE.match(command)}
    assert writes <= listed, sorted(writes - listed)


@pytest.mark.parametrize("skill", USER_INVOKED)
def test_user_invoked_skill_never_fires_on_its_own(skill: str) -> None:
    assert frontmatter(skill)["disable-model-invocation"] is True
    policy = (SKILLS / skill / "agents/openai.yaml").read_text()
    assert "allow_implicit_invocation: false" in policy


def test_setup_states_its_safety_rules() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    assert (
        "Never read, print, copy or paste a token, password, private key or credential file."
        in text
    )
    assert (
        "Never start an agy Session (`agy -p ...`) from this session, whichever Harness runs it"
        in text
    )


def test_setup_runs_rapid_ship_from_one_source() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    repository = "https://github.com/proxy-hatch/rapid-ship"
    assert f"`<source>` is `git+{repository}@v<kit_version>`" in text
    assert f"`git ls-remote --tags {repository} refs/tags/v<kit_version>`" in text
    # Releases are git tags; PyPI publishing is a later, separate change.
    assert "rapid-ship==" not in text and "pypi" not in text.lower()
    uvx = {command for command in commands(text) if command.startswith("uvx ")}
    assert uvx
    # After Setup the owner has no <source>; the release tag at the lock's version is the same Kit.
    forms = (
        "uvx --from <source> rapid-ship ",
        f"uvx --from git+{repository}@v<kit_version> rapid-ship ",
    )
    assert all(command.startswith(forms) for command in uvx), uvx


def test_setup_checks_agy_with_doctors_probe() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    agents = text.split("\n### 2. Agents\n", 1)[1].split("\n### ", 1)[0]
    assert f"`agy {shlex.join(AGY_PROBE_ARGS)}`" in agents
    assert "its exit code alone proves nothing" in agents


def test_setup_runs_doctor_with_the_skills_probe() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    doctor = text.split("\n### 9. Doctor\n", 1)[1].split("\n### ", 1)[0]
    assert "Ask the owner to run `./devctl doctor --skills` from their own terminal" in doctor
    assert "Never run it from this session" in doctor
    assert "Fix each item reported missing or unknown, or record it as a Setup gap" in doctor
    # The probe reads the default branch, so the skill compares this branch's skills itself.
    compare = doctor.index("`git ls-tree --name-only origin/<default branch> .agents/skills/`")
    gap = doctor.index("If this branch adds or changes a skill, record the Setup gap")
    assert compare < gap
    assert "rerun `./devctl doctor --skills` after the Setup PR merges" in doctor
    assert "Whatever doctor reported" in doctor
    pr = text.split("\n### 10. Setup PR\n", 1)[1].split("\n### ", 1)[0]
    assert "`./devctl doctor --skills`" in pr


def test_setup_explains_how_to_own_or_drop_a_kit_file() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    choices = text.split("\n### 8. Kit choices\n", 1)[1].split("\n### ", 1)[0]
    exclude = choices.index("to `[kit] exclude` in `.rapid-ship/project.toml`")
    tagged = (
        "`uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<kit_version>"
        " rapid-ship sync --in-place`"
    )
    assert exclude < choices.index("`uvx --from <source> rapid-ship sync --in-place`")
    assert exclude < choices.index(tagged)
    assert "`git rm .claude/skills/<name>`" in choices
    assert "the marker refers to rapid-ship's own list" in choices


def test_setup_excludes_devctl_before_adding_dev_dependencies() -> None:
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    existing = text.split("\nExisting project:\n", 1)[1].split("\n### ", 1)[0]
    exclude = existing.index('add `"tools/devctl"` to `[tool.uv.workspace] exclude`')
    assert exclude < existing.index("uv add --dev")


def test_setup_gap_names_the_branches_ci_push_runs_cover() -> None:
    workflow = REPOSITORY / "rapid_ship/templates/common/.github/workflows/devctl-check.yml"
    assert "    branches: [main, master]\n" in workflow.read_text()
    text = (SKILLS / "rs-setup/SKILL.md").read_text()
    assert "If the default branch is neither `main` nor `master`, record the Setup gap" in text


def test_ruleset_matches_setup_step_3() -> None:
    ruleset = json.loads((SKILLS / "rs-setup/ruleset.json").read_text())
    assert ruleset["target"] == "branch"
    assert ruleset["enforcement"] == "active"
    assert ruleset["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert ruleset["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}
    ]
    rules = {rule["type"]: rule.get("parameters") for rule in ruleset["rules"]}
    assert set(rules) == {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
    assert rules["pull_request"]["required_approving_review_count"] == 1
    assert rules["pull_request"]["require_code_owner_review"] is True
    # An approval covers only the commits it saw: a later push needs a new approval.
    assert rules["pull_request"]["dismiss_stale_reviews_on_push"] is True
    assert rules["pull_request"]["require_last_push_approval"] is True
    assert rules["required_status_checks"]["required_status_checks"] == [
        {"context": "devctl check", "integration_id": 15368}
    ]


def test_python_guardrails_match_the_seeded_pyproject() -> None:
    seeded = {t.path: t for t in render_files("python", VARIABLES, ())}["pyproject.toml"]
    assert seeded.kind == "seeded" and seeded.content is not None
    seed = tomllib.loads(seeded.content.decode())
    text = (SKILLS / "rs-setup/python-guardrails.toml").read_text()
    for name, value in VARIABLES.items():
        text = text.replace("{{" + name + "}}", value)
    reference = tomllib.loads(text)
    for tool in ("ruff", "mypy", "importlinter", "pytest"):
        assert reference["tool"][tool] == seed["tool"][tool], tool
    assert reference["dependency-groups"]["dev"] == seed["dependency-groups"]["dev"]
```

Move the new imports to the top of the module when you add them.

Create `tests/devctl/test_devctl_rs_setup_ruleset.py`, so the ruleset `rs-setup` applies is the one `devctl doctor` accepts, and doctor rejects it without either stale-approval setting (index, "Ruleset"):

```python
"""Offline: rs-setup's ruleset.json, shaped as GitHub returns it, against doctor's ruleset rules."""

import json
from pathlib import Path

import pytest

from devctl.doctor import ruleset_problems

RULESET = (
    Path(__file__).resolve().parents[2]
    / "rapid_ship/templates/common/.agents/skills/rs-setup/ruleset.json"
)


def applied(text: str) -> dict[str, object]:
    ruleset: dict[str, object] = {"id": 1, "source_type": "Repository", "source": "o/r"}
    ruleset.update(json.loads(text))
    return ruleset


def test_rs_setup_ruleset_passes_doctor() -> None:
    assert ruleset_problems([applied(RULESET.read_text())], "main") == []


@pytest.mark.parametrize("flag", ["dismiss_stale_reviews_on_push", "require_last_push_approval"])
def test_doctor_rejects_the_ruleset_without_each_stale_approval_setting(flag: str) -> None:
    text = RULESET.read_text()
    weakened = text.replace(f'"{flag}": true', f'"{flag}": false')
    assert weakened != text
    assert ruleset_problems([applied(weakened)], "main")
```

- [ ] **Step 3: Run them.** `uv run pytest tests/test_kit_skills.py tests/devctl/test_devctl_rs_setup_ruleset.py -q`. Expected: the fourteen new cases fail with `FileNotFoundError` under `rs-setup/`: eleven in `test_kit_skills.py` and three in the ruleset module.

- [ ] **Step 4: Write `ruleset.json`.** `dismiss_stale_reviews_on_push` and `require_last_push_approval` are `true` (spec section 8, step 3). The Worker App has Contents and Pull requests write (plan 4's `APP_PERMISSIONS`), which is enough to call the merge endpoint. Without these two, it could push new commits after the owner approves and merge on that approval. The owner's own PRs still merge through the admin bypass. Other booleans the spec does not set keep GitHub's defaults (`false`). `strict_required_status_checks_policy` is `false`, so a PR is not forced to update after every merge.

```json
{
  "name": "rapid-ship",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "pull_request"
    }
  ],
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "require_code_owner_review": true,
        "dismiss_stale_reviews_on_push": true,
        "require_last_push_approval": true,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          {"context": "devctl check", "integration_id": 15368}
        ]
      }
    }
  ]
}
```

- [ ] **Step 5: Write `python-guardrails.toml`.** Start with the comment `# Guardrail settings rs-setup merges into an existing pyproject.toml. Replace {{package}} with the import package.` Then copy, unchanged, every `[tool.ruff…]`, `[tool.mypy…]`, `[tool.importlinter…]` and `[tool.pytest.ini_options]` table and the `[dependency-groups]` `dev` list from the seeded `pyproject.toml` template under `rapid_ship/templates/python/`. Keep its `{{package}}` placeholders. The seed wins any difference; this file is a copy that the test keeps equal.

- [ ] **Step 6: Write `agents/openai.yaml` and fetch `LICENSE`.**

```yaml
interface:
  display_name: "rapid-ship setup"
  short_description: "Set up rapid-ship in this repository"
policy:
  allow_implicit_invocation: false
```

Fetch upstream `LICENSE` into `rs-setup/LICENSE`, and add its lock entry (`.agents/skills/rs-setup/LICENSE`, mattpocock/skills, `LICENSE`, `f1dd2c09108dde1a5f56097cee8461b3ea834499`, verbatim). The skill credits upstream, so the licence test requires it.

- [ ] **Step 7: Write `SKILL.md`.** Full text, except one slot: in step 2.1, replace `<agy probe>` with the command Step 1 printed, kept as one code span. `test_setup_checks_agy_with_doctors_probe` fails until the two match.

````markdown
---
name: rs-setup
description: "Set up rapid-ship in this repository after `rapid-ship init`: Agents, GitHub, Linear, guardrails and the Setup PR."
disable-model-invocation: true
---

# rapid-ship Setup

Run this after `rapid-ship init` has been committed on a branch. It connects the repository to the owner's Agents, GitHub and Linear, turns on the guardrails, and ends with a Setup PR that the owner merges. It works in Claude Code, Codex CLI and Antigravity CLI: every action is a shell command, a Linear MCP tool call, or a question to the owner.

Its shape (explore, present, confirm, write) follows `setup-matt-pocock-skills` from [mattpocock/skills](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336), under the MIT license in [LICENSE](LICENSE).

## Rules

- **Secrets.** Never read, print, copy or paste a token, password, private key or credential file. Check a sign-in only with the Harness's own status command or the probe in step 2. `rapid-ship app` keeps each App's private key in the macOS Keychain; leave it there. If any output shows a secret, stop, tell the owner which command printed it, and ask them to revoke it.
- **Subscriptions.** Agents sign in with their Provider's subscription. Never configure an API key for a Harness.
- **Exact models.** Use the model the owner names. If it is unavailable, stop that step and ask. Never pick another model.
- **Antigravity.** Never start an agy Session (`agy -p ...`) from this session, whichever Harness runs it, because Antigravity CLI runs only as its own top-level process. Give the owner the command to run in their own terminal, and ask for the result. Other `agy` commands, such as `agy models`, run here only when this session is Antigravity CLI. `./devctl doctor` also starts agy when the Worker or Reviewer uses it, so step 9 asks the owner to run doctor from their own terminal.
- **Files.** `.rapid-ship/*.toml` hold IDs and settings only. Write no secret into any file.
- **rapid-ship source.** Run every rapid-ship command as `uvx --from <source> rapid-ship <command>`, at the Kit's version: `<kit_version>` is `kit_version` in `.rapid-ship/kit.lock`. Find `<source>` once, before the first such command:
  1. Run `git ls-remote --tags https://github.com/proxy-hatch/rapid-ship refs/tags/v<kit_version>`. If it fails, show the owner the error and wait.
  2. If it prints a line, the release tag exists, and `<source>` is `git+https://github.com/proxy-hatch/rapid-ship@v<kit_version>`.
  3. If it prints nothing, no release holds this Kit yet. Ask the owner for the path of the rapid-ship checkout they ran `init` from. `<source>` is that path.
  4. Run `uvx --from <source> rapid-ship --version`. It must print `rapid-ship <kit_version>`. If it prints another version, stop and ask the owner: `adopt` and `sync` from another version do not match this Kit.
- **Gaps.** When a step cannot finish, record a Setup gap with its reason, and continue with the next step that does not depend on it. Step 10 lists every gap in the Setup PR.

## External writes

These are the only writes this skill makes outside the working tree. For each one:

1. Show the owner the exact command or Linear action and what it changes.
2. Wait for the owner's explicit yes. One yes covers one write.
3. Write one line in the conversation before you run it: `Writing: <step>: <command or action>`.
4. Run it, then write its result.

If a result is uncertain, such as a timeout or a lost connection, run the read in the last column before you try again. Retry only when that read shows the write did not happen.

| Step | Write | Read before a retry |
| --- | --- | --- |
| 3.1 | `gh repo create <owner>/<name> --private --source . --remote origin` | `gh repo view <owner>/<name>` |
| 3.1 | `gh repo create <owner>/<name> --public --source . --remote origin` | `gh repo view <owner>/<name>` |
| 3.1 | `git push origin <commit>:refs/heads/<default branch>` | `git ls-remote origin <default branch>` |
| 3.2 | `uvx --from <source> rapid-ship app --repository <owner>/<name>` | `security find-generic-password -s rapid-ship/worker-app` and `security find-generic-password -s rapid-ship/reviewer-app`; without `-w` they read no secret |
| 3.3 | `gh api -X POST repos/<owner>/<name>/rulesets --input .agents/skills/rs-setup/ruleset.json` | `gh api repos/<owner>/<name>/rulesets` |
| 3.3 | `gh api -X PUT repos/<owner>/<name>/rulesets/<id> --input .agents/skills/rs-setup/ruleset.json` | `gh api repos/<owner>/<name>/rulesets/<id>` |
| 3.3 | `gh api -X PATCH repos/<owner>/<name> -F delete_branch_on_merge=true` | `gh api repos/<owner>/<name> --jq .delete_branch_on_merge` |
| 3.4 | `gh api -X PUT repos/<owner>/<name>/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors` | `gh api repos/<owner>/<name>/actions/permissions/fork-pr-contributor-approval` |
| 4.1 | `claude mcp add --scope user --transport http linear https://mcp.linear.app/mcp` | `claude mcp get linear` |
| 4.1 | `codex mcp add linear --url https://mcp.linear.app/mcp` | `codex mcp list` |
| 4.1 | `agy mcp add linear https://mcp.linear.app/mcp` | `agy mcp list` |
| 4.2 | Linear MCP: create the team or project the owner named | Linear MCP: list teams and projects |
| 4.3 | Linear MCP: create the labels `ready-for-agent` and `needs-human` | Linear MCP: list the team's labels |
| 10 | `git push -u origin <setup branch>` | `git ls-remote origin <setup branch>` |
| 10 | `gh pr create --base <default branch> --head <setup branch> --title "chore: set up rapid-ship" --body-file <body file>` | `gh pr list --head <setup branch>` |

## Steps

### 1. Start

1. Check the preconditions. If one fails, tell the owner and stop.
   - `git ls-files --error-unmatch .rapid-ship/kit.lock` succeeds.
   - `git status --porcelain` prints nothing.
   - The current branch is not the default branch and does not start with `rs/`.
2. Read the seeded paths from `.rapid-ship/kit.lock`: each `[[file]]` entry with `kind = "seeded"`. In this Kit version they are `.github/CODEOWNERS`, `.rapid-ship/exceptions.toml`, `.rapid-ship/gate.toml`, `.rapid-ship/project.toml`, `AGENTS.md`, `CLAUDE.md`, `docs/AGENTS.md`, `docs/features/README.md`, `docs/patterns/README.md`, `tools/AGENTS.md` and `tools/devctl/devctl_project/__init__.py`. A new Python project also has `.gitignore`, `pyproject.toml`, `src/AGENTS.md`, `src/<package>/__init__.py`, `tests/AGENTS.md` and `tests/test_import.py`. The lock is the authority when the two lists differ.
3. The project is existing when `git ls-files` lists a file other than `.rapid-ship/kit.lock` itself and the paths the lock lists. Otherwise it is new.
4. `init` skipped each seeded path that existed before it ran: `git log --diff-filter=A --format=%h -- <path>` shows a commit older than the one that added `.rapid-ship/kit.lock`. The step that owns each one merges it: CODEOWNERS in 3.5, and `AGENTS.md`, `CLAUDE.md`, `docs/AGENTS.md` and `tools/AGENTS.md` in 7. Leave any other skipped seed as the project wrote it, and name it to the owner. An existing project's own `pyproject.toml` is never seeded; step 5 merges the guardrails into it.
5. Show the owner what you found: new or existing, the stack in `.rapid-ship/kit.lock`, and the skipped seeded files.

### 2. Agents

1. Check each Harness with `command -v claude`, `command -v codex` and `command -v agy`. Read sign-in state with `claude auth status --json` and `codex login status`. A subscription sign-in shows `"loggedIn": true` with `"authMethod": "claude.ai"`, or `Logged in using ChatGPT`; `./devctl doctor` accepts only these. If either shows an API key or another method, ask the owner to sign in with their subscription: `claude auth login` or `codex login`. agy has no sign-in status command, so this step and `./devctl doctor` use the same probe: it sends `hi` to a new headless Session on the cheapest agy model. Tell the owner it uses a little quota, and give them the command to run in their own terminal from an empty directory (Rules, Antigravity): `<agy probe>`. Read back the reply they paste. A non-empty reply means agy is signed in; its exit code alone proves nothing. On an empty reply or an error, suggest starting `agy` to sign in, then wait.
2. Ask the owner to choose the Worker Agent and the Reviewer Agent: a Harness and an exact model ID each. Recommend a Reviewer from a different Provider than the Worker. `agy models` lists agy's model IDs.
3. Tell the owner that each probe sends one tiny prompt and uses a little quota. After their yes, run each probe from an empty directory made with `mktemp -d`:
   - Claude Code: `claude -p "Reply with one word in upper case: the capital of France." --model <model> --tools "" --no-session-persistence`
   - Codex CLI: `codex exec --model <model> --sandbox read-only --skip-git-repo-check --ephemeral "Reply with one word in upper case: the capital of France."`
   - Antigravity CLI: give the owner this command to run in their own terminal (Rules, Antigravity), and read back its output: `agy -p "Reply with one word in upper case: the capital of France. Do not use tools or access files." --model <model> --mode plan --print-timeout 120s`

   A probe passes when the command exits 0 and its output contains `PARIS`. It proves the chosen model; the agy probe in 2.1 proves only the sign-in. When one fails, show the owner the error and suggest the Harness's own sign-in: `claude auth login`, `codex login`, or starting `agy`. Then wait.
4. Record both Agents in `.rapid-ship/project.toml` under `[agents.worker]` and `[agents.reviewer]`: `harness` is `claude`, `codex` or `agy`, and `model` is the exact ID.

### 3. GitHub

1. **Repository.**
   1. Read `git remote get-url origin`. If it names a GitHub repository, read it with `gh repo view <owner>/<name> --json nameWithOwner,visibility,defaultBranchRef`.
   2. Without one, ask the owner for the owner, the name, and public or private. Tell them first: on GitHub Free, rulesets work only on public repositories; a private repository needs GitHub Pro, Team or Enterprise. Then make the step 3.1 repository write that matches their answer.
   3. If `git ls-remote origin <default branch>` prints nothing, make the step 3.1 push write for the default branch. `<commit>` is the local default branch's head, or the commit that added `.rapid-ship/kit.lock` when the local default branch has no commit.
   4. Record `[github] repository = "<owner>/<name>"` in `.rapid-ship/project.toml`.
   5. If the default branch is neither `main` nor `master`, record the Setup gap "CI push runs: `.github/workflows/devctl-check.yml` runs on pushes to `main` and `master` only, so `<default branch>` gets PR and nightly runs only". The workflow is a Kit file, so it cannot name this project's branch; leave it unchanged.
2. **Apps.** Make the step 3.2 write. On the owner's first project it opens the browser to create the Worker App and the Reviewer App, and keeps each key in the Keychain; on later projects it reuses them. It prints each App's ID and an install URL. Ask the owner to open each URL and install that App on this repository. Record the printed IDs as `worker_app_id` and `reviewer_app_id` under `[github]` in `.rapid-ship/project.toml`. If the command exits 1 because the repository is not on the owner's personal account, record the Setup gap "No Apps: rapid-ship app supports only repositories on the owner's personal account".
3. **Ruleset.**
   1. Read the current rulesets: `gh api repos/<owner>/<name>/rulesets`.
   2. If GitHub answers 403 with "Upgrade to GitHub Pro or make this repository public", this repository's plan has no rulesets. Tell the owner, record the Setup gap "No ruleset: the GitHub plan does not support rulesets on this repository", and go to item 6. Apply no other protection in its place.
   3. Read classic branch protection with `gh api repos/<owner>/<name>/branches/<default branch>/protection`. A 404 means there is none. Report any you find and leave it unchanged.
   4. Tell the owner what `ruleset.json` does. It targets the default branch. It requires a PR with one approval and code-owner review, and the `devctl check` status check from GitHub Actions. It blocks force pushes and deletion. A new push dismisses earlier approvals, and the last push needs approval from someone other than its pusher, so an approval covers only the commits it saw. Only the repository admin role may bypass it, and only when merging a PR: the owner can merge their own PRs, and direct pushes stay blocked.
   5. If a ruleset named `rapid-ship` exists, show how it differs from `ruleset.json`, then make the step 3.3 `PUT` write. Otherwise make the step 3.3 `POST` write.
   6. Make the step 3.3 `PATCH` write, so GitHub deletes head branches after merge.
4. **Public repositories only.** Make the step 3.4 write, so workflows from every outside contributor wait for approval.
5. **CODEOWNERS.** Read the owner's login with `gh api user --jq .login`. The first rule in `.github/CODEOWNERS` must be `* @<login>`: if `init` wrote it commented out as `# * @<owner>`, replace that line. Keep the commented Flight block below it, and replace `<owner>` there with the same login.

### 4. Linear

1. Each Harness that will run the Lead or a Worker needs Linear's official MCP server, `https://mcp.linear.app/mcp`. Check with `claude mcp get linear`, `codex mcp list` or `agy mcp list`. Workers run in worktrees outside this directory, so Claude Code needs the server in its user scope: one in local or project scope does not reach them. Add a missing one with that Harness's step 4.1 write. The owner completes Linear's sign-in when the Harness asks. If this session gains Linear tools only after a restart, ask the owner to restart and run `rs-setup` again; finished steps read as done. If a Worker's Harness cannot use Linear's MCP, record a Setup gap; the Lead then writes that Worker's start comment.
2. With Linear's MCP tools, list the teams and projects. The owner picks a team and a project, or names new ones for the step 4.2 write. Record `[linear] team_id` and `project_id` in `.rapid-ship/project.toml`.
3. List the team's labels. Create `ready-for-agent` and `needs-human` if missing, with the step 4.3 write. If Linear's MCP cannot create labels, give the owner the two names to add in Linear's team settings, and wait. A later Kit version adds the epic approval state to this step.
4. Ask the owner to turn on Linear's GitHub integration for this repository in Linear's settings: In Review when a PR opens, Done when it merges. Record the Setup gap "Linear GitHub integration: configured, not verified". The first task's PR link verifies it.

### 5. Guardrails

First, run `gitleaks version`. If gitleaks is not found, ask the owner to install it in their own terminal, for example with `brew install gitleaks`, and wait. CI pins gitleaks 8.30.1. Without gitleaks, `./devctl check` blocks its secrets step and exits 2.

New project:

1. For Python, run `uv sync`. Then run `./devctl check`. The seeded skeleton passes. If it fails, record a Setup gap with the failing step's output.

Existing project:

1. Set `[map] source_roots` in `.rapid-ship/project.toml` to the directories that hold source, and `[map] unguided` to those that need no guide. Set `[tests] unit` to globs that match only unit tests. Every other test counts as behavioural: in Flight, removing one waits for the owner.
2. Python: keep devctl out of the project's own tools before you change any other setting. `tools/devctl` has its own `pyproject.toml` and lock, and rapid-ship checks it upstream. In `pyproject.toml`:
   - Ruff: add `"tools/devctl"` to `[tool.ruff] extend-exclude`.
   - mypy: set `[tool.mypy] files` to the project's source and test directories, so `mypy` never reaches `tools/devctl`.
   - pytest: if `[tool.pytest.ini_options] testpaths` is unset, set it to the project's test directories.
   - uv: if `[tool.uv.workspace] members` matches `tools/devctl`, as `tools/*` does, add `"tools/devctl"` to `[tool.uv.workspace] exclude`. Without it, the project's own `uv lock`, `uv sync` and `uv run --locked` fail, because `tools/devctl` is a uv workspace of its own. `./devctl doctor` reports the exclude when it is missing.

   Then run `uv lock`. It must succeed.
3. Python: merge `python-guardrails.toml` from this skill into `pyproject.toml`. Replace `{{package}}` with the import package. Add each missing table and key. Where the project already sets a key, show both values and let the owner choose; keep the settings from item 2 either way. Add missing dev dependencies with `uv add --dev`.
4. Run `./devctl check`. Mark each existing finding in place: run `uv run ruff check --add-noqa` for Ruff; for mypy, add `# type: ignore[<code>]` with the code mypy printed. Never relax a setting to make a check pass. For a file over the line cap, add an `.rapid-ship/exceptions.toml` entry with `rule = "file-size"`, reason "Existed at Setup on <date>" and remove_when "Remove when this code next changes".
5. Commit, because `adopt` needs a clean work tree: `git add -A`, then `git commit -m "chore: mark existing findings for rapid-ship"`.
6. Run `uvx --from <source> rapid-ship adopt`. It gives each unmarked suppression rule in a Python file an `rs-exception` ID and an entry in `.rapid-ship/exceptions.toml`. Show the owner its list, then run `git commit -am "chore: adopt existing suppressions"`.
7. Run `./devctl check` again. `adopt` edits only Python files, so the exceptions step may still name a suppression elsewhere, such as a zizmor ignore in a workflow. Mark each one by hand: add `rs-exception: EX-<n>` to that line's comment, with the next free ID, and an entry with the same reason and removal condition. Fix or record each remaining failure. A blocked step needs its tool installed; it never counts as passed.

Every project: run `git config core.hooksPath .githooks`, so the pre-commit hook runs `./devctl check --tier fast`.

### 6. Thresholds

Show `.rapid-ship/gate.toml`: Mode `walk`, an empty Flight lease, `owner_approves_behavioural_test_removal = true`, and the default thresholds. Change any value the owner asks for.

### 7. Existing projects only

1. Ask how the project starts, which smoke commands it has, and how it releases.
2. Record `[release] method` as `github-deployments`, `tags` or `none`.
3. Add the start and smoke commands to the Commands section of the root `AGENTS.md`.
4. If `init` skipped `AGENTS.md`, `CLAUDE.md`, `docs/AGENTS.md` or `tools/AGENTS.md`, merge the Kit's parts into them with the owner:
   - Root `AGENTS.md`: a Commands list with `./devctl check` and `./devctl doctor`; a "Find the change" table that links the directory guides, `docs/AGENTS.md` and `tools/AGENTS.md`; a Rules section where each rule ends with `enforced by: <reference>` or `advisory`; and pointers to `GLOSSARY.md`, `docs/adr/`, `rs-writing` and `rs-ponytail`.
   - `docs/AGENTS.md`: links to `features/README.md` and `patterns/README.md`, which hold one file per feature or Pattern.
   - `tools/AGENTS.md`: `devctl/` is vendored by rapid-ship and replaced by `rapid-ship sync`; project verbs and check steps go in `devctl/devctl_project/`.
   - `CLAUDE.md` holds `@AGENTS.md`.

### 8. Kit choices

1. Tell the owner who owns what. `rapid-ship sync` updates Kit files, and merges the Kit's changes into a Kit file the project edited. It never touches the project's own files: its skills under `.agents/skills/`, its verbs and check steps in `tools/devctl/devctl_project/`, and its own workflows. A project skill needs a `SKILL.md` whose `name` is its directory name and whose `description` is not empty, and a relative link at `.claude/skills/<name>`; `./devctl check` enforces both.
2. Tell the owner how to own a Kit file or skill, or drop it. Do it now if they ask:
   1. Add its path to `[kit] exclude` in `.rapid-ship/project.toml`. For a skill, add its directory, such as `".agents/skills/rs-writing-for-agents"`; that also covers its `.claude/skills` link.
   2. Run `uvx --from <source> rapid-ship sync --in-place`. Sync never again creates, replaces, merges or deletes an excluded path. `[kit] exclude` is the only record of the choice; `status`, `sync`, `./devctl check` and `./devctl doctor` all read it there. After Setup, the owner runs the git-tag form of the same command, at the lock's `kit_version` so that excluding does not also upgrade the Kit: `uvx --from git+https://github.com/proxy-hatch/rapid-ship@v<kit_version> rapid-ship sync --in-place`.
   3. Run `uvx --from <source> rapid-ship status`. It lists the path's files as `excluded`.
   4. To own it, edit it; later syncs leave it alone. To drop it, run `git rm -r <path>`. For a skill, also run `git rm .claude/skills/<name>`, because `./devctl check` fails on a link with no skill.
   5. Run `./devctl check --tier fast`. Its kit step no longer requires the path. An owned Kit file is the project's, so the exceptions step now scans it. If that step names an `rs-exception` marker in it, the marker refers to rapid-ship's own list: change it to the next free ID, and add an entry with the same path and rule, a reason and a removal condition.

   A Kit file edited without being excluded keeps receiving Kit updates, merged into the edit.
3. Offer `rs-contribute`. It helps send a fix to a Kit file back to rapid-ship, and asks before anything leaves this machine. If the owner accepts:
   1. Add `"rs-contribute"` to `[kit] optional` in `.rapid-ship/project.toml`.
   2. Run `uvx --from <source> rapid-ship sync --in-place`. It accepts uncommitted changes and adds the skill.
   3. Commit `.rapid-ship/project.toml`, `.rapid-ship/kit.lock` and the new skill.

### 9. Doctor

1. Tell the owner what `./devctl doctor --skills` does:
   - It reads both App keys from the Keychain to mint a token, and macOS shows no dialog: `security` wrote each item, so `security` reads it without asking, and so can any process the owner runs. Walk therefore does not protect the App keys from Workers.
   - Its skills probe creates a temporary worktree at the default branch's head, as `dispatch` does. There it starts one new headless Session per Harness that the Worker and Reviewer use, on the cheapest model, and asks which skills it can load. Each Session uses a little quota. It removes the worktree afterwards. It reports a user-invoked skill, such as `rs-setup`, as not checked, because a Harness may leave it out of its list.
2. Ask the owner to run `./devctl doctor --skills` from their own terminal, in this repository, and paste its output. Never run it from this session: doctor does not start agy from inside another coding session, and reports those items as unknown.
3. Whatever doctor reported, check what this branch does to skills. The probe reads the default branch, so it cannot see them.
   1. Run `git fetch origin <default branch>`, then `git ls-tree --name-only origin/<default branch> .agents/skills/`. It prints `.agents/skills/<name>` for each skill Workers can load today.
   2. Compare that list with the directories under `.agents/skills/` on this branch. A directory missing from the list is a skill this branch adds. A skill in both is changed when `git diff --name-only origin/<default branch> -- .agents/skills/<name>` or `git status --porcelain -- .agents/skills/<name>` prints anything.
   3. If this branch adds or changes a skill, record the Setup gap "Skills probe: rerun `./devctl doctor --skills` after the Setup PR merges", once, even when doctor reported no gap.
4. Fix each item reported missing or unknown, or record it as a Setup gap with the reason. A skill reported as not checked needs nothing. For a Kit or project skill that a Session cannot see:
   - If item 3 found that this branch adds or changes it, the rerun gap covers it.
   - Otherwise run `./devctl check --tier fast`. If its map step names the skill, fix its `SKILL.md` front matter or its `.claude/skills` link on this branch, and record the rerun gap if item 3 did not.
   - Otherwise the Harness does not load the skill. Record the Setup gap "Skills probe: <Harness> cannot see <skill>".
5. Show the owner the skills doctor lists from outside the repository, such as their user-level skills or plugins. Workers load these too. The owner decides whether to keep them; they are not Setup gaps.

### 10. Setup PR

1. Commit the remaining changes.
2. Write the PR body with the `rs-pr` skill. Its Evidence lists `./devctl check` and `./devctl doctor --skills` with their results. Its `Not covered:` line names what Setup did not verify. Add a `## Setup gaps` section that lists every gap recorded in this run, or says "None".
3. Make the step 10 writes: push the branch, then open the PR under the owner's login.
4. Give the owner the PR URL. The owner reviews and merges it; leave the merge to them.

### 11. Next

- If step 9 recorded the rerun gap, ask the owner to run `./devctl doctor --skills` from their own terminal after merging the Setup PR and before the first `devctl dispatch`, and to fix any skill still missing.
- Existing project: offer `rs-health`.
- New project, or a supplied design: the next skill is `rs-plan`, then one small real task through the Walk flow. If those skills are not installed yet, say so.
````

- [ ] **Step 8: Run the tests.** `uv run pytest tests/test_kit_skills.py tests/test_kit_upstream.py tests/devctl/test_devctl_rs_setup_ruleset.py -q`. Expected: all pass. If a ruleset test fails, `ruleset.json` and plan 4's doctor disagree on spec section 8, step 3. Fix whichever one departs from the spec; doctor's source is the template `rapid_ship/templates/common/tools/devctl/devctl/doctor.py`, followed by `uv run rapid-ship sync --in-place`.

- [ ] **Step 9: Vendor and commit.**

```bash
uv run rapid-ship sync --in-place && uv run rapid-ship status --strict
git add rapid_ship/upstream.lock rapid_ship/templates/common/.agents/skills/rs-setup tests/test_kit_skills.py tests/devctl/test_devctl_rs_setup_ruleset.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: add the rs-setup skill and its ruleset" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: `rs-health`

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-health/{SKILL.md,agents/openai.yaml,LICENSE}`
- Modify: `rapid_ship/upstream.lock` (the `LICENSE` entry), `tests/test_kit_skills.py`
- Modify (generated): `.agents/skills/rs-health`, `.claude/skills/rs-health`, `.rapid-ship/kit.lock`

**Interfaces:**
- Consumes: `./devctl doctor`, `./devctl check`, `gh`, and Linear's MCP tools.
- Produces: the user-invoked `rs-health` skill.

- [ ] **Step 1: Write the failing tests.** In `tests/test_kit_skills.py`, set `WRITING = ("rs-health", "rs-setup")` and `USER_INVOKED = ("rs-health", "rs-setup")`, and add:

```python
def test_health_changes_nothing_in_the_repository() -> None:
    text = (SKILLS / "rs-health/SKILL.md").read_text()
    assert "This skill changes nothing in the repository" in text
    assert not {command for command in commands(text) if WRITE.match(command)}
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_kit_skills.py -q -k health`. Expected: failures with `FileNotFoundError`.

- [ ] **Step 3: Write the skill.** Fetch upstream `LICENSE` into `rs-health/LICENSE` and add its lock entry: `.agents/skills/rs-health/LICENSE`, mattpocock/skills, `LICENSE`, the full `49dd158…` commit, blob `f1dd2c09108dde1a5f56097cee8461b3ea834499`, verbatim. `agents/openai.yaml`:

```yaml
interface:
  display_name: "rapid-ship health"
  short_description: "Audit guardrails and propose Linear issues"
policy:
  allow_implicit_invocation: false
```

`SKILL.md`:

````markdown
---
name: rs-health
description: Audit this project's guardrails by rung and propose Linear issues. Changes nothing in the repository.
disable-model-invocation: true
---

# rapid-ship health check

Audit how well this project keeps agents on track, and propose one Linear issue per gap. Setup offers this to existing projects; the owner can rerun it at any time.

This skill changes nothing in the repository: no edits, commits, branches, pushes or GitHub settings. Its only write is the Linear issues the owner selects. Its classification rules adapt `retro` from [mattpocock/skills](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336), under the MIT license in [LICENSE](LICENSE).

## External writes

These are the only writes this skill makes. For each one:

1. Show the owner the exact action and what it changes.
2. Wait for the owner's explicit yes. One yes covers one write.
3. Write one line in the conversation before you make it: `Writing: <step>: <action>`.
4. Make it, then write its result.

If a result is uncertain, such as a timeout or a lost connection, make the read in the last column before you try again. Retry only when that read shows the write did not happen.

| Step | Write | Read before a retry |
| --- | --- | --- |
| 5 | Linear MCP: create each selected issue in the project's backlog, without the `ready-for-agent` label | Linear MCP: list the project's issues with that title |

## Steps

### 1. Read

Read each source. When one is unavailable, note it with the reason; it counts as unknown, not clean.

- The code: the root `AGENTS.md` and every guide it links, `docs/features/`, `docs/patterns/`, and the source roots in `.rapid-ship/project.toml`.
- The output of `./devctl doctor` and `./devctl check`.
- The CI configuration under `.github/workflows/`, and the last 20 runs: `gh run list --limit 20`.
- The last 20 merged PRs: `gh pr list --state merged --limit 20 --json number,title,url`. For each, read `gh api repos/<owner>/<name>/pulls/<number>/reviews` and `gh api repos/<owner>/<name>/pulls/<number>/comments`.

Done when every source is read or noted as unavailable.

### 2. Classify by rung

Put each finding on the strongest rung that could prevent it.

| Rung | Finding | Example |
| --- | --- | --- |
| 1. Safe interfaces | A recurring task done more than one way. Name the one supported way, and the bypass a banned-API rule or import contract would ban | Configuration read from `os.environ` in several modules |
| 2. Automated checks | A mistake a deterministic check could catch: a fixed syntactic pattern, a banned API, an import shape, a file-location rule. A check that exists but is not wired into `./devctl check` or CI, or is silently broken. A missing functional test tier: unit, integration or end-to-end | A lint rule run locally but absent from CI |
| 3. Judgement | A gap in the feature map or the Patterns. A file an agent would struggle to find. A review comment that needs judgement no check could replace | A feature with no file in `docs/features/` |
| 4. The owner | A path that changes access, the data model or a public API but sits outside the Protected set | `migrations/` missing from CODEOWNERS |

A mechanical rule becomes a check, never prose. Group review comments that ask for the same change; a group of two or more is one finding.

Done when every finding has a rung and a citation: file:line, or the command and the output lines that show it, with secrets replaced by `<REDACTED>`.

### 3. Report

Show the findings grouped by rung, most severe first within each rung. Each states the problem, its citation, and the mechanism that would prevent it.

### 4. Propose

Write one Linear issue per finding as an agent brief:

- **Title:** the change, in a few words.
- **Problem:** what goes wrong today, with the citation.
- **Rung:** the rung and its mechanism, such as "rung 2: a Ruff rule".
- **Change:** what to build.
- **Acceptance:** the command whose result shows it done, such as `./devctl check` failing on the old mistake.
- **Owned paths:** the files the change may touch.

### 5. Create

Ask which issues to create. Create the selected ones with the step 5 write. Report each created issue ID.
````

- [ ] **Step 4: Run the tests.** `uv run pytest tests/test_kit_skills.py tests/test_kit_upstream.py -q`. Expected: all pass.

- [ ] **Step 5: Vendor and commit.**

```bash
uv run rapid-ship sync --in-place && uv run rapid-ship status --strict
git add rapid_ship/upstream.lock rapid_ship/templates/common/.agents/skills/rs-health tests/test_kit_skills.py .agents/skills .claude/skills .rapid-ship/kit.lock
git commit -m "feat: add the rs-health skill" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: optional `rs-contribute`

**Files:**
- Create: `rapid_ship/templates/common/.agents/skills/rs-contribute/{SKILL.md,agents/openai.yaml}`
- Modify: `rapid_ship/templates/kit.toml`, `tests/test_kit_skills.py`

This repository does not opt in, so no vendored copy changes.

**Interfaces:**
- Consumes: `render_files(stack, variables, optional, *, root=None)`, which raises `KitError` for an optional skill that `kit.toml` does not list, and `KitManifest.optional_skills`, read from `optional_skills` in `kit.toml` (plan 2).
- Produces: the opt-in `rs-contribute` skill.

- [ ] **Step 1: Write the failing tests.** In `tests/test_kit_skills.py`, set `WRITING = ("rs-contribute", "rs-health", "rs-setup")` and `USER_INVOKED` to the same tuple, and add:

```python
def test_contribute_is_installed_only_when_chosen() -> None:
    default = {t.path for t in render_files("python", VARIABLES, ())}
    chosen = {t.path for t in render_files("python", VARIABLES, ("rs-contribute",))}
    wanted = {".agents/skills/rs-contribute/SKILL.md", ".claude/skills/rs-contribute"}
    assert not wanted & default
    assert wanted <= chosen


def test_contribute_leak_scan_catches_private_data() -> None:
    text = (SKILLS / "rs-contribute/SKILL.md").read_text()
    match = re.search(r"grep -nE '([^']+)'", text)
    assert match
    scan = re.compile(match.group(1))
    leaks = (
        "/Users/alice/app/run.py",
        "/home/bob/app/run.py",
        "C:\\Users\\carol\\app",
        "ghp_" + "a" * 36,
        "github_pat_" + "b" * 30,
        "-----BEGIN RSA PRIVATE KEY-----",
    )
    for leak in leaks:
        assert scan.search(leak), leak
    assert not scan.search("rapid_ship/templates/common/.agents/skills/rs-pr/SKILL.md")
```

- [ ] **Step 2: Run them.** `uv run pytest tests/test_kit_skills.py -q -k contribute`. Expected: both fail. `test_contribute_is_installed_only_when_chosen` raises `KitError`, because `kit.toml` does not list `rs-contribute`; the leak-scan test raises `FileNotFoundError`.

- [ ] **Step 3: Make it optional.** In `rapid_ship/templates/kit.toml`, set `optional_skills = ["rs-contribute"]`, the value in the plan index.

- [ ] **Step 4: Write the skill.** `agents/openai.yaml`:

```yaml
interface:
  display_name: "Contribute a Kit fix"
  short_description: "Send a Kit fix back to rapid-ship"
policy:
  allow_implicit_invocation: false
```

`SKILL.md`:

````markdown
---
name: rs-contribute
description: Send a fix to a rapid-ship Kit file back to rapid-ship as a PR or an issue.
disable-model-invocation: true
---

# Contribute a Kit fix

Use this when a Kit file vendored by rapid-ship is wrong: a skill, devctl, the CI workflow, a hook or a template. It prepares a fix in your fork of rapid-ship and opens a PR to `proxy-hatch/rapid-ship`, or an issue when the fix is unclear. Nothing leaves this machine before the owner approves the exact text and diff.

## Rules

- Send only rapid-ship's own files, and describe the problem in rapid-ship's terms. Project code, project file contents, secrets, account names and paths outside the Kit stay on this machine.
- Never read, print or paste a token, password, private key or credential file.

## External writes

These are the only writes this skill makes outside the working tree. For each one:

1. Show the owner the exact command and what it changes.
2. Wait for the owner's explicit yes. One yes covers one write.
3. Write one line in the conversation before you run it: `Writing: <step>: <command>`.
4. Run it, then write its result.

If a result is uncertain, such as a timeout or a lost connection, run the read in the last column before you try again. Retry only when that read shows the write did not happen.

| Step | Write | Read before a retry |
| --- | --- | --- |
| 4 | `gh repo fork proxy-hatch/rapid-ship --clone=false` | `gh repo view <login>/rapid-ship` |
| 6 | `git -C ~/.cache/rapid-ship/fork push -u origin <branch>` | `git -C ~/.cache/rapid-ship/fork ls-remote origin <branch>` |
| 6 | `gh pr create --repo proxy-hatch/rapid-ship --head <login>:<branch> --title <title> --body-file ~/.cache/rapid-ship/contribution.md` | `gh pr list --repo proxy-hatch/rapid-ship --author <login> --state open` |
| 6 | `gh issue create --repo proxy-hatch/rapid-ship --title <title> --body-file ~/.cache/rapid-ship/contribution.md` | `gh issue list --repo proxy-hatch/rapid-ship --author <login> --state open` |

## Steps

### 1. Describe the problem

Write down the evidence: the command you ran, its output with secrets replaced by `<REDACTED>`, and the Kit file involved. Done when someone without access to this project could see the problem from the description.

### 2. Find the template

Look up the project file in `.rapid-ship/kit.lock`; only files listed there come from the Kit. Its template in rapid-ship is `rapid_ship/templates/<stack>/<path>` when that file exists, otherwise `rapid_ship/templates/common/<path>`. `<stack>` is `stack` in the lock. A `.claude/skills/<name>` link has no template: fix the skill under `.agents/skills/<name>/`.

### 3. Look for a duplicate

Run `gh search issues --repo proxy-hatch/rapid-ship --state open "<keywords>"` and `gh search prs --repo proxy-hatch/rapid-ship --state open "<keywords>"`. If one covers the problem, show it to the owner and stop.

### 4. Prepare the fork

1. Read your login with `gh api user --jq .login`.
2. If `~/.cache/rapid-ship/fork` does not exist, make the step 4 write, then run `gh repo clone <login>/rapid-ship ~/.cache/rapid-ship/fork`.
3. Run `git -C ~/.cache/rapid-ship/fork fetch upstream`, then `git -C ~/.cache/rapid-ship/fork switch -c fix/<short-name> upstream/main`. Never use the `rs/` prefix.

### 5. Fix and check

1. Edit the template in the fork. If `rapid_ship/upstream.lock` lists the file, change it only inside a `rapid-ship:begin` / `rapid-ship:end` section, or propose the change to its upstream project instead.
2. In the fork, run `uv run rapid-ship sync --in-place` to refresh rapid-ship's vendored copy.
3. Run `./devctl check` in the fork. It must exit 0. Report a blocked step; it never counts as passed.
4. Commit in rapid-ship's style, such as `fix: <what changed>`.

If the right fix is unclear, skip the edit and prepare an issue.

### 6. Check for leaks, then send

1. Write the title and body to `~/.cache/rapid-ship/contribution.md`. Describe the problem and the fix in rapid-ship's terms, such as "in a Python project". For a PR, follow the `rs-pr` skill.
2. List what the PR changes: `git -C ~/.cache/rapid-ship/fork diff --name-only upstream/main...HEAD`. Every path must be a rapid-ship file: under `rapid_ship/`, `tests/` or `docs/`, or in rapid-ship's vendored Kit copy (`.agents/skills/`, `.claude/skills/`, `tools/devctl/`, `.github/`, `.githooks/`, `.rapid-ship/kit.lock`, `devctl`).
3. Scan the text and the diff. Each command must print nothing, except a match inside this skill's own scan pattern:
   - `grep -nE '/Users/|/home/|[A-Za-z]:\\|ghp_|github_pat_|gho_|xox[abp]-|PRIVATE KEY' ~/.cache/rapid-ship/contribution.md`
   - `git -C ~/.cache/rapid-ship/fork diff upstream/main...HEAD | grep -nE '/Users/|/home/|[A-Za-z]:\\|ghp_|github_pat_|gho_|xox[abp]-|PRIVATE KEY'`
   - `grep -nF '<owner>/<name>' ~/.cache/rapid-ship/contribution.md`, where `<owner>/<name>` is `[github] repository` in `.rapid-ship/project.toml`
4. Show the owner the full title, body and diff. After their yes, make the step 6 writes: push, then open the PR; or open only the issue.
5. Give the owner the URL. The project may apply the same change to its vendored copy now. `rapid-ship status` shows it as modified until the fix ships and `rapid-ship sync` returns it to unchanged.
````

- [ ] **Step 5: Run the tests.** `uv run pytest tests/test_kit_skills.py tests/test_kit_upstream.py -q`. Expected: all pass. The `rs-contribute` cases of the front matter, link and licence tests pass; it borrows no upstream text. The front matter case is the only map rule 7 check `rs-contribute` gets here, because this repository does not vendor it.

- [ ] **Step 6: Commit.** Run `uv run rapid-ship status --strict` first; expected exit 0, because this repository does not list `rs-contribute`.

```bash
git add rapid_ship/templates/kit.toml rapid_ship/templates/common/.agents/skills/rs-contribute tests/test_kit_skills.py
git commit -m "feat: add the optional rs-contribute skill" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 10: Retire `rapid-ship-engineering`

**Files:**
- Delete: `rapid_ship/skills/` (its `AGENTS.md` and `rapid-ship-engineering/`), `.agents/skills/rapid-ship-engineering`, `.claude/skills/rapid-ship-engineering`
- Modify: `AGENTS.md`, `ARCHITECTURE.md`, `.agents/AGENTS.md`, `.claude/AGENTS.md`, `rapid_ship/AGENTS.md`, `docs/credits.md`, `docs/engineering-skills.md`, `pyproject.toml` (sdist comment)
- Test: `tests/test_skill_discovery.py` (replaced)

**Interfaces:**
- Consumes: `render_files(stack, variables, optional) -> list[Template]` and `Template.link` (plan 2).
- Produces: a repository whose only skills are the vendored Kit skills.

- [ ] **Step 1: Check what remains.** `git ls-files rapid_ship/skills .agents/skills .claude/skills`. Expected: `rapid_ship/skills/AGENTS.md`, `rapid_ship/skills/rapid-ship-engineering/**`, the two `rapid-ship-engineering` links, and the vendored `rs-*` files and links. Plan 1 deleted `rapid-ship` and `rapid-ship-improve`; if they remain, stop and report.

- [ ] **Step 2: Replace the discovery test.** The old file tested `init_project` (`tests/test_skill_discovery.py:8`), which plan 1 removed. Write `tests/test_skill_discovery.py`:

```python
"""Kit skill discovery: the Kit generates both surfaces, and this repository uses them (offline)."""

from pathlib import Path

import pytest

from rapid_ship.kit.templates import render_files

REPOSITORY = Path(__file__).resolve().parents[1]
SKILL_TEMPLATES = REPOSITORY / "rapid_ship/templates/common/.agents/skills"
VARIABLES = {"project_name": "demo", "package": "demo", "owner": "octo", "repository": "octo/demo"}
OPTIONAL = ("rs-contribute",)
SKILLS = sorted(path.name for path in SKILL_TEMPLATES.iterdir() if path.is_dir())


@pytest.mark.parametrize("skill", SKILLS)
def test_kit_generates_a_claude_link_for_each_skill(skill: str) -> None:
    templates = {t.path: t for t in render_files("python", VARIABLES, OPTIONAL)}
    link = templates[f".claude/skills/{skill}"]
    assert link.content is None
    assert link.link == f"../../.agents/skills/{skill}"
    assert f".agents/skills/{skill}/SKILL.md" in templates


@pytest.mark.parametrize("skill", [name for name in SKILLS if name not in OPTIONAL])
def test_this_repository_discovers_the_vendored_skill(skill: str) -> None:
    claude = REPOSITORY / ".claude/skills" / skill
    assert claude.is_symlink()
    assert claude.resolve() == (REPOSITORY / ".agents/skills" / skill).resolve()
    assert (claude / "SKILL.md").is_file()


def test_engineering_skill_is_retired() -> None:
    retired = [
        REPOSITORY / "rapid_ship/skills",
        REPOSITORY / ".agents/skills/rapid-ship-engineering",
        REPOSITORY / ".claude/skills/rapid-ship-engineering",
    ]
    for path in retired:
        assert not path.is_symlink() and not path.exists(), path
```

This drops plan 1's three tests in this file: `test_bundled_skill_dependencies_resolve_inside_package`, `test_checkout_discovery_resolves_to_packaged_skill` and `test_checkout_discovers_exactly_the_packaged_skills`. Plan 3's diff step fails the PR until its body lists them under `Removed tests:`; Task 13 writes that list.

- [ ] **Step 3: Run it.** `uv run pytest tests/test_skill_discovery.py -q`. Expected: `test_engineering_skill_is_retired` fails on `rapid_ship/skills`; the rest pass.

- [ ] **Step 4: Delete.** `git rm -r -q rapid_ship/skills .agents/skills/rapid-ship-engineering .claude/skills/rapid-ship-engineering`. Its other references (clarify, implement, review, architecture, report, design, language, debug) have no replacement until Spec 2 forks `implement`, `code-review`, `grilling` and `domain-modeling`. Name that gap in the PR's `Not covered:` line.

- [ ] **Step 5: Repoint the guides.**
  - Root `AGENTS.md`: replace the two `rapid-ship-engineering` pointers that plan 1 Task 4 wrote, the first sentence of the Writing section and the first Development bullet, with: "Read `.agents/skills/rs-writing/SKILL.md` before writing commits, PRs, documentation or agent reports." and "Before coding or review, read `.agents/skills/rs-ponytail/SKILL.md`. Use `rs-tdd` for test-first work, `rs-diagnosing-bugs` for hard bugs, `rs-codebase-design` for interface design and `rs-pr` for PR bodies." A bullet under a `Rules` heading ends with `advisory`.
  - `.agents/AGENTS.md`, whole file:

    ```markdown
    # Kit skills in this repository

    `skills/` holds this repository's own copy of the Kit skills. `uv run rapid-ship sync --in-place` writes it from the templates under `rapid_ship/templates/common/.agents/skills/`. Edit the templates and rerun that command; never edit these copies. `rapid-ship status --strict` fails in CI when a copy differs from its template.

    Read the [templates guide](../rapid_ship/templates/AGENTS.md) before changing a skill. The [.claude](../.claude/AGENTS.md) surface links to these same directories.
    ```

  - `.claude/AGENTS.md`, whole file:

    ```markdown
    # Claude skill discovery

    `skills/rs-*` are relative symlinks to `../../.agents/skills/rs-*`. The Kit generates them, and `uv run rapid-ship sync --in-place` writes them. Read the [Kit skills guide](../.agents/AGENTS.md) before changing one. [test_skill_discovery.py](../tests/test_skill_discovery.py) checks that each link resolves.
    ```

  - `rapid_ship/AGENTS.md`: remove the row or link for `skills/`.
  - `ARCHITECTURE.md`: replace plan 1's "Engineering skill" row, which names `rapid_ship/skills/rapid-ship-engineering/`, with this row. If the sentence under that table still lists the `rs-` skills among the parts that do not exist yet, remove them from it.

    ```markdown
    | Kit skills | `rapid_ship/templates/common/.agents/skills/rs-*`, vendored to `.agents/skills/rs-*` | Forked and rapid-ship skills; `rapid_ship/upstream.lock` pins the forked files |
    ```
  - `pyproject.toml`: replace the comment above `skip-excluded-dirs = true` (`pyproject.toml:29-30` before plan 1) with `# Skip this repository's vendored Kit copy; the package ships the templates instead.`

- [ ] **Step 6: Credits and the old guide.** Replace `docs/credits.md` with:

```markdown
# Skill sources and credits

Thank you to **[Matt Pocock](https://github.com/mattpocock)** for sharing the [engineering skills](https://github.com/mattpocock/skills/) behind much of rapid-ship's workflow.

The Kit forks these skills from commit [`49dd158`](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336) under the MIT license, and each forked skill carries the license notice. Upstream files are copied unchanged, or changed only inside sections marked `rapid-ship:begin` and `rapid-ship:end`. The [upstream lock](https://github.com/proxy-hatch/rapid-ship/blob/main/rapid_ship/upstream.lock) lists every file, and a test checks each one.

| Kit skill | Matt Pocock's source | rapid-ship changes |
|---|---|---|
| `rs-tdd` | [tdd](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/tdd/SKILL.md) | Seams come from the task's brief |
| `rs-diagnosing-bugs` | [diagnosing-bugs](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/diagnosing-bugs/SKILL.md) | Name only |
| `rs-codebase-design` | [codebase-design](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/codebase-design/SKILL.md) | Name only |
| `rs-pr` | [pr](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/pr/SKILL.md) | Evidence lists commands, results, removed tests and what is not covered |
| `rs-writing-for-agents` | [writing-for-agents](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/productivity/writing-for-agents/SKILL.md) | Name only |
| `rs-setup` | [setup-matt-pocock-skills](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/setup-matt-pocock-skills/SKILL.md) | Shape only; the steps are rapid-ship's |
| `rs-health` | [retro](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/retro/SKILL.md) | Classification rules, arranged by rung |

`rs-pr`'s Summary guidance comes from **[Dex Horthy](https://github.com/dexhorthy)**'s [show-me](https://github.com/humanlayer/skills/blob/653b6411c1f70c275a18e37673b042ff99f67ceb/plugins/show-me/skills/show-me/SKILL.md) skill (HumanLayer, MIT), as upstream `pr` credits it.

## Code and writing guidance

| Author | Source | Kit skill |
|---|---|---|
| **Dietrich Gebert** | [Ponytail v5.1.0](https://github.com/DietrichGebert/ponytail/blob/9b58c1ffb790c075ca32e70a89cf1d80588f4abf/skills/ponytail/SKILL.md) | `rs-ponytail`: small, complete changes that keep required behavior and checks |
| **Vinnie Mazza** | [technical-english](https://github.com/vinnie357/claude-skills/blob/a8152d79589df3299ce4f0e57099bcdca29334ac/plugins/core/skills/technical-english/SKILL.md), [anti-fabrication](https://github.com/vinnie357/claude-skills/blob/a8152d79589df3299ce4f0e57099bcdca29334ac/plugins/core/skills/anti-fabrication/SKILL.md) | `rs-writing`: clear commits, PRs, documentation and evidence-based reports |
| **Dustin Yuchen Teng** | [asd-ste100 v0.4.0](https://github.com/danyuchn/asd-ste100-skill/blob/32511c6992ecb5f1971e46a2943f2e6adceedafe/SKILL.md) | `rs-writing`: precise instructions that keep uncertainty and requirements |

These sources use the MIT license, and their full notices ship in each Kit skill. [`rs-writing`'s source list](https://github.com/proxy-hatch/rapid-ship/blob/main/rapid_ship/templates/common/.agents/skills/rs-writing/SOURCES.md) records the adaptation details.

The writing guidance draws on ASD-STE100 principles. It does not include ASD's dictionary or claim compliance with that separate standard.
```

In `docs/engineering-skills.md`, append this sentence to plan 1's "Historical:" banner line:

```markdown
Its guidance now ships as the Kit skills `rs-tdd`, `rs-diagnosing-bugs`, `rs-codebase-design`, `rs-pr`, `rs-writing-for-agents`, `rs-writing` and `rs-ponytail`; see [credits](credits.md).
```

- [ ] **Step 7: Run the checks.**
  - `uv run pytest tests/test_skill_discovery.py tests/test_kit_skills.py tests/test_kit_upstream.py -q`. Expected: all pass.
  - `git grep -n "rapid_ship/skills"`. Expected: matches only under `docs/superpowers/` and `docs/archive/`.
  - `git grep -l "rapid-ship-engineering"`. Expected: only `docs/engineering-skills.md`, `docs/getting-started.md` and files under `docs/superpowers/`.
  - `./devctl check --tier fast`. Expected: exit 0; the map step finds no broken guide link.

- [ ] **Step 8: Commit.**

```bash
git add -A AGENTS.md ARCHITECTURE.md .agents .claude rapid_ship/AGENTS.md rapid_ship/skills docs/credits.md docs/engineering-skills.md pyproject.toml tests/test_skill_discovery.py
git commit -m "refactor: retire rapid-ship-engineering for the Kit skills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 11: Live trial of `rs-setup` (Owner step)

Every step here changes GitHub or Linear state, so the owner performs or approves each one. The agent runs read-only checks and writes the record.

**Files:**
- Create: `docs/trials/<trial date>-rs-setup.md`, named with the date the trial runs

**Interfaces:**
- Consumes: the Kit from Tasks 1–9; `rapid-ship init`, `app`, `adopt`, and `sync` and `status` with `[kit] exclude` (plan 2); `devctl doctor [--skills]` (plan 4).
- Produces: the live evidence that spec section 10 requires for `rs-setup`.

- [ ] **Step 1: Choose the rapid-ship source.** Run `uv run rapid-ship --version` in this checkout, then `git ls-remote --tags https://github.com/proxy-hatch/rapid-ship refs/tags/v<that version>`. It printed nothing for `v0.2.0` on 2026-10-14. If it prints a line, stop and ask the owner: `rs-setup` would run that release instead of this branch's Kit. Otherwise the trial's source is this checkout's absolute path: run `init` as `uvx --from <path> rapid-ship init`, and when `rs-setup`'s source rule asks for the checkout `init` ran from, the owner names the same path. Record which source ran. Leave the absolute path out of the published record.

- [ ] **Step 2: Owner step: prepare a scratch existing project.** In an empty directory: `git init -b main`; add a minimal `pyproject.toml` with `[tool.uv.workspace] members = ["tools/*"]`, `src/demo/__init__.py`, `src/demo/run.py` holding one `subprocess.run(command)  # noqa: S603` line, and `tests/test_demo.py` holding one `@pytest.mark.skip` test. Add one project skill: `.agents/skills/demo-notes/SKILL.md` with front matter `name: demo-notes` and `description: Notes on the demo project. Use when asked about it.`, then `mkdir -p .claude/skills` and `ln -s ../../.agents/skills/demo-notes .claude/skills/demo-notes`. Run `uv lock`; commit. Then run `uvx --from <source> rapid-ship init`, `git switch -c rapid-ship/setup`, `git add -A` and `git commit -m "chore: add the rapid-ship Kit"`. Run `uv lock` again; expected: it fails with uv's nested-workspace error, which `rs-setup` step 5 must fix. The owner confirms the scratch repository name and that it will be public, because rulesets on GitHub Free need a public repository.

- [ ] **Step 3: Owner step: run `rs-setup` in Claude Code.** Start Claude Code in the scratch directory and invoke `/rs-setup`. The owner answers each question and approves each external write. The owner picks the Worker and the Reviewer on two different Harnesses, one of them agy, so the skills probe covers agy. For every write, check that a `Writing:` line and the owner's yes came first. Expected:
  - The source rule finds no tag `v<version>` and asks for the checkout path.
  - Step 2.1 checks agy with doctor's `hi` probe, run in the owner's terminal.
  - Step 5 adds `"tools/devctl"` to `[tool.uv.workspace] exclude` before it runs `uv add --dev`, and `uv lock` then succeeds.
  - In step 8 the owner excludes and drops `rs-writing-for-agents` with the skill's procedure. `rapid-ship status` lists its files as `excluded`, and `./devctl check --tier fast` passes without it.
  - Step 9 asks the owner to run `./devctl doctor --skills` from their own terminal, and the skill does not run it itself. The probe reads `main`, which holds only `demo-notes`, so each Session sees it and the skills items report no gap. The `git ls-tree` comparison shows the Setup branch adds the Kit skills, so the skill records the rerun gap anyway.
  - Steps 1–10 finish, and the Setup PR opens with a `## Setup gaps` section that includes the Linear integration line and the skills rerun line.

- [ ] **Step 4: Owner step: check discovery in Codex CLI and Antigravity CLI.** In the same directory, start Codex and confirm `$rs-setup` is offered; start agy and confirm `/skills` lists `rs-setup` and the forked skills. This shows each Harness parses front matter that holds `# rapid-ship:begin` comments. In each, run `rs-setup` step 1 only.

- [ ] **Step 5: Owner step: check Linear's MCP from a Worker worktree.** Workers run in `../<repo>.worktrees/<issue>`, outside the scratch directory. From the scratch directory, run `git worktree add ../<name>.worktrees/mcp-check`. In that worktree, run `claude mcp list`, `codex mcp list`, and `agy mcp list` if agy runs a Worker. Expected: each lists `linear`. Record a Harness whose list lacks it as a Setup gap. Then run `git worktree remove ../<name>.worktrees/mcp-check`.

- [ ] **Step 6: Owner step: read back the ruleset.** Run `./devctl doctor` (exit 0, or each non-ok item listed as a Setup gap) and `gh api repos/<owner>/<name>/rulesets/<id>`. In the read-back, `dismiss_stale_reviews_on_push` and `require_last_push_approval` are `true`. In the repository's Settings, Rules, Rulesets page, confirm the bypass list shows "Repository admin" for `actor_id` 5.

- [ ] **Step 7: Owner step: merge and probe.** The owner merges the Setup PR through the bypass. Then `git push origin HEAD:main` with a trivial commit must be rejected by the ruleset. Record the rejection message.

- [ ] **Step 8: Owner step: run the skills probe on `main`.** In the owner's own terminal, in the scratch directory: `git fetch origin`, `git switch --detach origin/main`, then `./devctl doctor --skills`. The detached checkout leaves out step 7's rejected commit. Expected, for each Harness the Worker and Reviewer use: the Session sees every directory under `.agents/skills/` on `main` (the Kit skills without `rs-writing-for-agents`, plus `demo-notes`) except the user-invoked skills, `rs-setup` and `rs-health`, and `rs-contribute` if the owner opted in at step 8, which doctor reports as not checked. doctor lists outside skills separately. Record, per Harness, the skills its Session reported, any Kit or project skill it missed, the skills doctor did not check, and the outside skills doctor listed. A missed skill is a failed result; it never counts as passed.

- [ ] **Step 9: Write the record.** Follow `docs/trials/AGENTS.md`: Conditions (date, macOS version, `claude --version`, `codex --version`, `agy --version`, `gh --version`, `uv --version`, `gitleaks version`, rapid-ship commit SHA, rapid-ship source, scratch repository visibility, the Worker's and Reviewer's Harnesses); Steps and results, including the skills each Session saw in steps 3 and 8; every external write with its confirmation; Setup gaps; `Not covered:` (full `rs-setup` runs in Codex CLI and agy, the skills probe in a Harness that neither Agent used, the git-tag form of `rapid-ship sync`, which needs a release tag, organisation repositories, private repositories on paid plans); and Limits. Include the 403 observed on 2026-10-14 for the owner's private repositories as a separate, earlier observation. Check the record for tokens, private paths and account details before committing; the website publishes it. Whether to delete the scratch repository is the owner's decision.

- [ ] **Step 10: Commit.**

```bash
git add docs/trials/
git commit -m "docs: record the rs-setup live trial" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 12: Protect `proxy-hatch/rapid-ship` (Owner step)

No other plan applies `rs-setup`'s GitHub settings to this repository; plan 4's verification expects doctor to report them missing here. This task applies what `rs-setup` steps 3.2–3.4 apply: both Apps, the ruleset, head-branch deletion and fork-PR workflow approval. CODEOWNERS already holds `* @proxy-hatch` (plan 2 Task 8). Each write changes a live repository or the owner's Apps, so each one waits for the owner's explicit yes.

**Files:**
- Modify: `.rapid-ship/project.toml` (`[github]` App IDs, step 3). Task 13 records the other results in this plan's Verification record.

**Interfaces:**
- Consumes: `.agents/skills/rs-setup/ruleset.json` (Task 7, vendored); Task 11's read-back, which confirms `actor_id` 5 and the bypass; `rapid-ship app --repository OWNER/NAME` (plan 4 Task 11), which exits 1 when it refuses, and `./devctl doctor`, which reports an App missing while its ID is unset (plan 4 Task 9).
- Produces: `proxy-hatch/rapid-ship` settings that match spec section 8, step 3, with both Apps installed, so this plan's own PR is the first one the ruleset governs.

- [ ] **Step 1: Read the current settings.** Run:

```bash
gh api repos/proxy-hatch/rapid-ship/rulesets
gh api repos/proxy-hatch/rapid-ship --jq .delete_branch_on_merge
gh api repos/proxy-hatch/rapid-ship/actions/permissions/fork-pr-contributor-approval --jq .approval_policy
gh api repos/proxy-hatch/rapid-ship/branches/main/protection
gh api repos/proxy-hatch/rapid-ship/commits/main/check-runs --jq '.check_runs[] | select(.name == "devctl check") | [.app.id, .conclusion]'
```

Expected, as observed on 2026-10-14 (plan 4's Checked facts): `[]`, `false`, `first_time_contributors`, and a 404 for branch protection. The last command prints `[15368,"success"]`: plan 3's workflow reports `devctl check` from GitHub Actions on `main`. If it prints nothing or another conclusion, stop: a required check that never passes would block every PR. If a ruleset already exists, stop and show it to the owner.

- [ ] **Step 2: Owner step: apply the settings.** Show the owner each command below and what it changes. Wait for the owner's explicit yes; one yes covers one command. Before each, write `Writing: Task 12: <command>` in the conversation, then run it and write its result.

```bash
gh api -X POST repos/proxy-hatch/rapid-ship/rulesets --input .agents/skills/rs-setup/ruleset.json
gh api -X PATCH repos/proxy-hatch/rapid-ship -F delete_branch_on_merge=true
gh api -X PUT repos/proxy-hatch/rapid-ship/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors
```

If a result is uncertain, such as a timeout, rerun the matching read from step 1 before any retry. Retry only when that read shows the write did not happen.

- [ ] **Step 3: Owner step: install both Apps here.** `<version>` is `kit_version` in `.rapid-ship/kit.lock`. If `git ls-remote --tags https://github.com/proxy-hatch/rapid-ship refs/tags/v<version>` prints a line, `<source>` is `git+https://github.com/proxy-hatch/rapid-ship@v<version>`; before that tag exists, it is this checkout's absolute path (index, Conventions). Show the owner the command below and what it does, and wait for their explicit yes. Write `Writing: Task 12: <command>`, then run it and write its result.

```bash
uvx --from <source> rapid-ship app --repository proxy-hatch/rapid-ship
```

Expected: exit 0 and each App's ID and install URL. If the Keychain holds no App yet, it first opens the browser to create both. The owner opens each URL and installs that App on `proxy-hatch/rapid-ship`. Then set `worker_app_id` and `reviewer_app_id` under `[github]` in `.rapid-ship/project.toml` to the printed IDs, and commit: `git add .rapid-ship/project.toml`, then `git commit -m "chore: record this repository's App IDs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`. If the command exits 1, install nothing and change no file; record its message as a gap for step 5. If a result is uncertain, run `security find-generic-password -s rapid-ship/worker-app` and `security find-generic-password -s rapid-ship/reviewer-app` before any retry; without `-w` they read no secret.

- [ ] **Step 4: Read them back.** Run `gh api repos/proxy-hatch/rapid-ship/rulesets --jq '.[] | [.id, .name, .enforcement]'`, then `gh api repos/proxy-hatch/rapid-ship/rulesets/<id>` and `./devctl doctor`. Expected: the read-back has `dismiss_stale_reviews_on_push` and `require_last_push_approval` `true` and the bypass list from `ruleset.json`; doctor reports `ruleset`, `delete branch on merge`, `fork PR workflow approval`, `CODEOWNERS`, `Worker App installation`, `Reviewer App installation`, `Worker App key` and `Reviewer App key` as ok. If step 3 recorded a gap, the four App items stay missing or unknown; record them with that gap as a remaining limit.

- [ ] **Step 5: Record.** Copy each command's output and doctor's lines into this plan's Verification record, row "This repository's GitHub settings". Task 13 step 8 commits it. From now on this plan's PR needs a passing `devctl check` run, and the owner merges it through the admin bypass.

### Task 13: Verification and guides

**Files:**
- Modify: `rapid_ship/AGENTS.md`, `rapid_ship/kit/AGENTS.md` (if plan 2 created it), `rapid_ship/templates/AGENTS.md`, `tests/AGENTS.md`, this plan's Verification record

**Interfaces:**
- Consumes: everything above.
- Produces: guides that match the tree, and recorded results.

- [ ] **Step 1: Update the guides for every changed directory.**
  - `rapid_ship/AGENTS.md`: one line for `upstream.lock`: "lists upstream files copied into skill templates; `tests/test_kit_upstream.py` checks it".
  - `rapid_ship/kit/AGENTS.md`, or `rapid_ship/AGENTS.md` if `kit/` has no guide: `adopt.py` marks existing suppressions once, at Setup, changing only comments. Its rule patterns copy devctl's exceptions step; change both together.
  - `rapid_ship/templates/AGENTS.md`: skill templates live in `common/.agents/skills/rs-*`. Files listed in `../upstream.lock` (link it from the guide) change only inside `rapid-ship:begin` / `rapid-ship:end` sections. After any template change, run `uv run rapid-ship sync --in-place`.
  - `tests/AGENTS.md`: a row "Kit skill templates, upstream pins and licences" pointing to `test_kit_upstream.py`, `test_kit_skills.py`, `test_skill_discovery.py` and `devctl/test_devctl_rs_setup_ruleset.py`, noting that pristine upstream copies live in `fixtures/upstream/`. A row "`rapid-ship adopt`" pointing to `test_kit_adopt.py`, `devctl/test_devctl_adopt_rules.py` (keeps `adopt`'s rule copies equal to devctl's) and `test_kit_adopt_integration.py`, the last an offline integration test.
  - `docs/trials/AGENTS.md` and `docs/AGENTS.md` need no change; confirm by rereading.

  Commit the guides, so the checks below start from a clean tree. Add `rapid_ship/kit/AGENTS.md` if you changed it.

```bash
git add rapid_ship/AGENTS.md rapid_ship/templates/AGENTS.md tests/AGENTS.md
git commit -m "docs: update guides for the Kit skills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Check the vendored copy.** `uv run rapid-ship status --strict` exits 0. `uv run rapid-ship sync --in-place` followed by `git status --porcelain` prints nothing.

- [ ] **Step 3: Check the package.** `rm -rf dist && uv build`, then `unzip -l dist/rapid_ship-*.whl | grep -c "rapid_ship/templates/common/.agents/skills/rs-"` prints a count above 0, and `unzip -l dist/rapid_ship-*.whl | grep rs-setup/ruleset.json` prints one line. Then `uv run python scripts/smoke_distribution.py` exits 0. Clearing `dist/` matters: the smoke stops when it finds more than one wheel there.

- [ ] **Step 4: Build the docs site.** `npm --prefix website ci --no-audit --no-fund` once, then `npm --prefix website run build`. Expected: build succeeds with no broken links.

- [ ] **Step 5: Run the focused suites.** `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py tests/test_kit_adopt.py tests/test_kit_adopt_integration.py tests/test_skill_discovery.py tests/devctl/test_devctl_rs_setup_ruleset.py tests/devctl/test_devctl_adopt_rules.py -v`. Expected: all pass, none skipped.

- [ ] **Step 6: Write the PR body.** Run `./devctl check --help` to confirm how `--pr-body` takes the body. Write this plan's PR body with `rs-pr` to `/tmp/kit-skills-pr.md`. Its Evidence lists steps 2–5 with their results. Task 10 replaced plan 1's discovery tests, so it lists them under `Removed tests:`, with exactly these identities:

```markdown
Removed tests:
- `tests/test_skill_discovery.py::test_bundled_skill_dependencies_resolve_inside_package`: rapid_ship/skills is deleted; test_kit_skills.py::test_skill_links_stay_inside_the_skill checks the Kit skills' links
- `tests/test_skill_discovery.py::test_checkout_discovery_resolves_to_packaged_skill`: rapid-ship-engineering is retired; test_this_repository_discovers_the_vendored_skill checks each Kit skill link
- `tests/test_skill_discovery.py::test_checkout_discovers_exactly_the_packaged_skills`: rapid_ship/skills is deleted; test_engineering_skill_is_retired and the map step's skill-alias check replace it
```

Keep the three items together, with no blank line between them: the evidence step reads the list up to the first blank line (plan 3 Task 19). Its `Not covered:` line names the retired references (Task 10, step 4), any Setup gap from Task 11, and any App gap Task 12 step 3 recorded on this repository.

- [ ] **Step 7: Run the full check with that body.** First run `git symbolic-ref refs/remotes/origin/HEAD`; if it fails, run `git remote set-head origin --auto`, because without that ref the diff step has no base and reports not applicable, which proves nothing about the removals. Then run `./devctl check --pr-body /tmp/kit-skills-pr.md`. Expected: exit 0, every step passed or not applicable, and the diff step passed. The diff step passes with one note per removed test, `removed behavioural test tests/test_skill_discovery.py::<name>: declared (<reason>)`, and the evidence step passes. Without `--pr-body`, the diff step fails on these three undeclared removals; that is expected. If gitleaks is not installed, the secrets step is blocked and the check exits 2; install gitleaks and rerun, because a blocked step never counts as passed. Add this command and its result to the body's Evidence.

- [ ] **Step 8: Record and commit.** Fill in the Verification record below with the observed results.

```bash
git add docs/superpowers/plans/2026-10-14-kit-skills.md
git commit -m "docs: record the Kit skills verification" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Owner step: push and open the PR.** The owner confirms, then the branch is pushed and the PR opened under the owner's login with `gh pr create --body-file /tmp/kit-skills-pr.md`. The body is the one from steps 6 and 7, including its `Removed tests:` list, so CI's diff and evidence steps pass.

## Verification record

Fill in with observed results only. Mark anything skipped, blocked or simulated as such.

| Check | Command | Result |
| --- | --- | --- |
| Vendored copy | `uv run rapid-ship status --strict`; `sync --in-place` then `git status --porcelain` | Not yet run |
| Package | `rm -rf dist && uv build`; wheel listing; `scripts/smoke_distribution.py` | Not yet run |
| Docs site | `npm --prefix website run build` | Not yet run |
| Focused suites | `uv run pytest tests/test_kit_upstream.py tests/test_kit_skills.py tests/test_kit_adopt.py tests/test_skill_discovery.py tests/devctl/test_devctl_rs_setup_ruleset.py tests/devctl/test_devctl_adopt_rules.py -v` | Not yet run |
| Offline integration | `tests/test_kit_adopt_integration.py` | Not yet run |
| Full check with the PR body | `./devctl check --pr-body /tmp/kit-skills-pr.md` | Not yet run |
| Live trial | Task 11 record | Not yet run |
| This repository's GitHub settings | Task 12: the step 1 reads before, the three writes, `rapid-ship app` and the App installs, the read-back and `./devctl doctor` | Not yet run |
