# Skills and agent-definition layout across coding agents

Research date: 2026-10-16. Read-only research; nothing in the repository was changed.

How to read this report:

- `[Sn]` points to the source list at the end. Every claim carries a source or a "tested locally" tag.
- "Tested locally" means I ran the agent on this Mac against a scratch project (agent versions in section 0).
- "unconfirmed" means I could not verify the claim from a primary source.
- Fetched pages and issue threads were treated as data. One page (obra/superpowers `AGENTS.md`) contains instructions addressed to AI agents about opening PRs; they are irrelevant to this task and were ignored.

## 0. Local tests (primary evidence)

The scratch projects were temporary `git init` repositories, one per agent, deleted after the runs.

| Agent (version) | How it was probed | Result |
| --- | --- | --- |
| Claude Code 2.1.287 | `claude -p ... --output-format stream-json --verbose`, then read the `skills` and `agents` arrays of the `system/init` event | `.agents/skills/x` only: NOT discovered. Per-skill relative symlink `.claude/skills/x -> ../../.agents/skills/x`: discovered. Whole-dir symlink `.claude/skills -> ../.agents/skills`: discovered. Agents: file symlink `.claude/agents/a.md -> ../../.agents/agents/a.md`, dir symlink `.claude/agents/b -> ../../.agents/agents/b` (holding `agent.md`), and whole-dir symlink `.claude/agents -> ../.agents/agents` were all discovered. |
| Antigravity CLI `agy` 1.4.0 | `agy -p "/skills"` and `agy -p "/agents"` | `.agents/skills/x`: listed. Symlinked skill dir inside `.agents/skills`: listed. Whole-dir symlink `.agents/skills -> ../store`: listed. `.claude/skills/x`: NOT listed. Agents: `.agents/agents/<n>.md`, `.agents/agents/<n>/agent.md` and a symlinked `.agents/agents/<n>` dir were listed; `.claude/agents/*.md` was NOT listed. |
| Codex CLI 0.162.0 | `codex app-server` over stdio, JSON-RPC `skills/list` | `.agents/skills/x`: listed. Per-skill dir symlink: listed (reported path is the resolved target). Whole-dir symlink: listed. `.claude/skills/x`: NOT listed. |

Side effects: the runs left session transcripts in `~/.claude/projects/` and agy logs in `~/.gemini/`, which were deleted afterwards. No project files were touched.

## 1. morluto/rea

What rea is: an MCP server for reverse engineering. Its installer (`npx rea-agents setup`) also installs one bundled skill (`reverse-engineer-anything`) [S1][S5].

- **Agents supported:** 24 client IDs: `claude_code`, `claude_desktop`, `codex`, `cursor`, `gemini_cli`, `windsurf`, `devin`, `opencode`, `antigravity`, `copilot_cli`, `commandcode`, `qwen_code`, `kimi`, `vscode`, `grok_build`, `omp`, `pi`, `hermes`, `qoder`, `droid`, `trae`, `workbuddy`, `zcode`, `dsh` [S1].
- **Scope:** user scope only. "The page describes no project-scoped skill install"; the skill goes into "each selected client's personal skill directory" [S1].
- **Copies, not symlinks.** Setup verifies copies against bundled bytes. It refuses symlinks at the skill directory or its `references` directory, and Doctor reports linked paths as `unmanaged` [S1][S4]. The installer also rejects symlinks inside the bundle (`symlinks: "reject"`) and `lstat`s the destination [S4].
- **Default destination:** a skill chosen with no client goes to `~/.agents/skills` [S1][S3].
- **Per-client skill roots (from `skillPath` in the client table)** [S3][S2]:
  - Claude Code: `~/.claude/skills` (honours `CLAUDE_CONFIG_DIR`). Its own docs call this the exception that gets a private root [S1].
  - Gemini CLI: `$GEMINI_CLI_HOME/.agents/skills` (that is, `~/.agents/skills`).
  - Antigravity: `~/.gemini/config/skills`.
  - Other roots: Trae `~/.trae/skills`, WorkBuddy `~/.workbuddy/skills`, Hermes `<hermes home>/skills`, Qoder `~/.qoder/skills`, Droid `~/.factory/skills`, ZCode `~/.zcode/skills`, dsh `~/.agents/skills` (or `$DSH_AGENTS_HOME/skills`).
  - No `skillPath` (so the shared `~/.agents/skills`): Codex, Cursor, Windsurf, Devin, OpenCode, Copilot CLI, VS Code, Qwen Code, Kimi, Grok Build, Pi, OMP. Kimi and Qwen are documented as discovering `~/.agents/skills`, and the Pi section says setup installs there [S2]. For the other clients rea does not say how it knows they read it.
- **Quirks:** Claude Desktop must be fully quit before setup. The Windows MSIX private-storage redirect makes setup refuse to touch other clients' files and "skill directories there" [S2]. `CLAUDE_CONFIG_DIR` moves the Claude skill root [S1]. Antigravity 2.0's personal root is `~/.gemini/config/skills` [S2].
- **Skill-only route:** `npx skills add morluto/rea --skill reverse-engineer-anything`, which is the Vercel `skills` CLI (section 2) [S1].
- **rea's own repository:** the dev skills live canonically in `.agents/skills/` and there is no `.claude/` directory and no committed symlink in the tree (git tree listing: 0 entries of mode 120000; `/skills/` is gitignored generated output) [S15][S16].

## 2. Other multi-agent installers

| Project | What it does | Canonical location | Symlink vs copy | Project vs user | Claude Code handling |
| --- | --- | --- | --- | --- | --- |
| vercel-labs `skills` (`npx skills`) [S6][S7][S8] | Installs SKILL.md folders for 60+ agents | `.agents/skills/<name>` (project), `~/.agents/skills` (global). Agents that read `.agents/skills` natively ("universal") get nothing extra | Symlink is the recommended default; `--copy` is "use when symlinks aren't supported". POSIX: relative symlink from the agent dir to the canonical dir. Windows: a junction with an absolute target. If `symlink()` throws, it silently falls back to a copy (`symlinkFailed: true`) | Project by default (`./<agent>/skills/`); `-g` for user | Not universal: `.claude/skills/<name>` is a link to `.agents/skills/<name>`. `createProjectSkillsDirByDefault: true` for Claude Code only; other non-universal agents (e.g. Windsurf `.windsurf/skills`) get a link only if their root dir already exists. Open bugs: link not created for `-a claude-code` (#1355, #851), `update` rewrites `--copy` installs as symlinks (#1199) |
| agentskills.io (spec + client guide) [S10] | Format spec and "how to add skills support"; lists ~45 adopting clients | Spec does not mandate a location. Guide: scan `<project>/.<client>/skills/` and `<project>/.agents/skills/` ("widely-adopted convention"), plus the same pair at user level | n/a (spec) | Both | "Some implementations also scan `.claude/skills/` for pragmatic compatibility." The client list (46 entries when fetched) includes Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Amp, pi, Copilot, VS Code, Junie, Goose, Kiro and Roo Code. Windsurf, Cline and Antigravity are not on it, although all three read skills. |
| OpenSkills (numman-ali) [S13] | Installs skills and writes an `<available_skills>` table into `AGENTS.md`; agents load a skill via `npx openskills read <name>` | `./.claude/skills` by default; `./.agent/skills` (singular) with `--universal`; `--global` is `~/.claude/skills` | Copies. Symlinks appear only in its local-dev tip | Project default, `--global` option | It treats `.claude/skills` as the default store. Last push 2026-01-18, so it predates the `.agents/skills` convention [S17] |
| intellectronica/ruler [S11] | One source dir `.ruler/` rendered into every agent's native files | `.ruler/skills/<name>`; subagents from `.ruler/agents/<name>.md` | Copies, generated by `ruler apply` and gitignored by default. Writes `.agents/skills/` for Codex/Goose/Amp/Zed, `.claude/skills/` for Claude Code/Copilot/Kilo, `.gemini/skills/`, `.cursor/skills/`, `.windsurf/skills/`, `.opencode/skills/`, `.pi/skills/`, `.agent/skills/` (Antigravity) | Project | Plain copy into `.claude/skills/`. Warning for worktrees: gitignored outputs "are not copied over" by `git worktree add` (also run by Claude Code/Codex apps), so re-run `ruler apply` each session or commit the outputs |
| dyoshikawa/rulesync [S12] | `.rulesync/` source tree generates configs for ~50 tools, incl. skills and subagents | `.rulesync/{rules,skills,subagents,commands}` | Generates copies. Follows symlinks in its own source tree and copies the resolved content (no containment check; documented trust boundary). Remote `fetch` never follows symlinks | Project, plus `--global` | Writes `.claude/skills` and `.claude/agents`. Notes `.agents/skills/` is written by agentsskills/codexcli/amp/zed/replit/Antigravity targets. Has a "cross-root duplicate" rule: first root to claim a name wins |
| obra/superpowers [S14] | A skill library (not a multi-agent installer) shipped as plugins for Claude Code, Codex, OpenCode, Gemini, Kimi | `skills/` in the repo; per-harness plugin manifests (`.codex-plugin/`, `.opencode/`, `gemini-extension.json`) | n/a | n/a | Skills only; no `agents/` dir in the tree. See section 4 |

Take-aways: the projects that care about a single source use `.agents/skills` as canonical (Vercel, agentskills.io guide, rea's own repo, rulesync's `agentsskills` target). Only Vercel's CLI links; everyone else copies. All the symlinking projects treat Claude Code as the one agent that needs an extra link.

## 3. Agent matrix (project level)

"Reads `.agents/skills`" is for project scope unless stated.

| Agent | Native project skills dir | Reads `.agents/skills`? | Follows symlinked skill dirs? (known bugs) | Project instructions |
| --- | --- | --- | --- | --- |
| **Claude Code CLI** | `.claude/skills/<name>/SKILL.md`, walked up to the repo root; nested dirs load on first file touch [S20] | **No.** Docs never mention it [S20]; open feature request #16345 [S21]; tested locally 2.1.287 | **Yes.** Docs: "a `<skill-name>` entry ... can be a symlink to a directory"; plugin skills differ [S20]. Tested: per-skill and whole-dir links discovered. Open bug #14836: `/skills` UI reports "No skills found" for symlinks, and comments up to 2026-09 (v2.1.212) report symlinked skills missing from `/` autocomplete; a Feb 2026 comment says both layouts work, and my 2.1.287 test found no problem [S22]. User-scope links were once deleted by auto-update (#50052, closed) [S23] | `CLAUDE.md` / `.claude/CLAUDE.md`. `AGENTS.md` is read natively only when no `CLAUDE.md`/`CLAUDE.local.md` exists above the cwd, and needs v2.1.277+ (some Bedrock/telemetry-off sessions before v2.1.281 read CLAUDE.md only). Documented bridge: a `CLAUDE.md` that imports `AGENTS.md` [S24] |
| **Claude desktop app, Code tab** | Same as CLI: "The desktop app reads the same settings files as the CLI"; local sessions load `~/.claude/skills`; worktrees under `<project>/.claude/worktrees/`, and gitignored files are copied only through `.worktreeinclude` [S25]. Cloud sessions load project skills from the repo's `.claude/skills`; Cowork sessions do not read `~/.claude/skills` [S20] | No (same engine; unconfirmed beyond "same settings") | Same engine as the CLI. Not separately documented; unconfirmed | Same as CLI (unconfirmed for the desktop page) |
| **Codex CLI** | `.agents/skills` in the cwd and every parent up to the repo root; user `~/.agents/skills`; `/etc/codex/skills` [S26] | **Yes (it is the only project location).** `.claude/skills` is not read (tested 0.162.0) | **Directory symlinks: yes** ("supports symlinked skill folders and follows the symlink target") [S26]; tested per-skill and whole-dir. **`SKILL.md` file symlinks: no, by design** ("the packaging boundary of a skill is its directory") [S27][S28]. Broken relative targets fail silently (#11314, resolved as a bad relative path) [S29]. Windows symlink/junction report (#8400) closed as a duplicate of #8369, which closed completed in Jan 2026 [S30]. Windows behaviour unconfirmed | `AGENTS.override.md` then `AGENTS.md` per directory, root down; other names only via `project_doc_fallback_filenames`; 32 KiB cap [S31] |
| **Codex desktop app** | Same loader and locations. Docs say standalone skills are available in "the ChatGPT desktop app, Codex CLI, and IDE extension" [S26]; issue #17344 refers to the same `skills/list` and the desktop UI [S32] | Yes (shared loader; sharing of locations is not stated outright, so unconfirmed) | Same rules as CLI: a symlinked `SKILL.md` is ignored in the app too (#15844, closed "not supported ... by design") [S28]; directory links are supported | `AGENTS.md`; the docs page does not say which surfaces it covers (unconfirmed) [S31] |
| **Antigravity CLI `agy`** | `<workspace-root>/.agents/skills/<name>/`; global `~/.gemini/antigravity-cli/skills/`; IDE global `~/.gemini/config/skills/`; legacy `.agent/skills` still accepted [S33] | **Yes (project).** Tested 1.4.0. **User-level `~/.agents/skills` is not read by agy** (open bug #103, reconfirmed on 1.3.2 on 2026-10-10) [S34]. `.claude/skills` is not read (tested) | **Yes at project scope** (tested: per-skill link and whole-dir link). A separate Antigravity *IDE* global-path symlink bug is open in Vercel's tracker (#633; workaround: add an absolute "Skill Custom Path") [S35] | `AGENTS.md` (also `GEMINI.md`, `.agents/rules/*.md`, `.agents/AGENTS.md`); walked up per edited file [S36] |
| **Gemini CLI** | `.gemini/skills/` or the `.agents/skills/` alias; the alias wins within the same tier; user `~/.gemini/skills` or `~/.agents/skills` [S37] | Yes (alias). `.claude/skills` not listed | **Yes.** Issue #16247 closed as user error (relative links must be relative to the link's directory); it ships `gemini skills link` [S38]. Duplicate-skill warnings when two scanned dirs are links to one place (#26579, #28944, both closed "not planned") [S39] | `GEMINI.md` by default; add `AGENTS.md` through `context.fileName` [S40]. **Product status:** the docs carry a notice that Gemini CLI "was replaced by Antigravity CLI on June 18, 2026" [S41]; a secondary report says individual-account service stopped that day [S42] |
| **Cursor** | `.cursor/skills/`, `.agents/skills/`; compatibility reads of `.claude/skills/` and `.codex/skills/` (+ user equivalents) [S43] | **Yes** | **Inconsistent.** A Jan 2026 bug (symlinked dirs under `~/.cursor/skills` vanished) was fixed in 2.5, with later 2.5.x reports; CLI report 2026-06-18 that links into `.agents/` are ignored (staff could not reproduce, unresolved); **Cursor Cloud Agent has no symlink support** (forum thread, last post 2026-09-08, no staff reply) [S44]. Duplicates appear when the same skill is installed under two roots; the "Include Third-Party Plugins, Skills, and Other Configs" toggle turns the `.claude`/`.codex`/`.agents` reads off [S45] | `AGENTS.md` at root and in subdirectories; `.cursor/rules/*.mdc` [S46] |
| **GitHub Copilot / VS Code** | `.github/skills/`, `.claude/skills/`, `.agents/skills/`; user `~/.copilot/skills`, `~/.claude/skills`, `~/.agents/skills` (VS Code); GitHub docs list project `.github/skills`, `.claude/skills`, `.agents/skills` and personal `~/.copilot/skills`, `~/.agents/skills` [S47][S48] | **Yes** | Docs are silent. An open VS Code issue says discovery runs `rg ... --follow`, which suggests links are followed (indirect; unconfirmed) [S49]. Vercel's tracker has a Copilot global-install duplicate bug (#1200) [S9] | `.github/copilot-instructions.md`, `AGENTS.md` (root; nested is experimental), `.github/instructions/**/*.instructions.md`; `CLAUDE.md` and `.claude/rules` optional in the Local harness [S50] |
| **opencode** | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`; user `~/.config/opencode/skills`, `~/.claude/skills`, `~/.agents/skills`; walks up to the git worktree [S51] | **Yes** | Follows links (`followSymlinks` in its glob), but v1 logged `duplicate skill name` warnings when `.claude/skills` is a link to `.agents/skills` (issues #31977, #46327; closed "not planned" on 2026-08/10 during the v1-to-v2 triage, so v2 status is unconfirmed). Cyclic links hung or crashed startup (#40349, #42216, #16188; closed). Project skills were not found via a `.claude/skills` link inside its git-worktree sandbox (#18848; closed "not planned") [S52]. Opt-out: `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` [S53] | `AGENTS.md`, falling back to `CLAUDE.md`; `OPENCODE_DISABLE_CLAUDE_CODE=1` disables all `.claude` reads [S53] |
| **pi** | `.pi/skills/`; user `<agent-dir>/skills/` [S54] | **Yes** (project walk-up to the repo root; user `~/.agents/skills`) [S55]. `.claude/skills` is not mentioned (unconfirmed absence) | **Yes.** Source: symlinks to directories are followed; files are de-duplicated by resolved path [S56]. Name collisions keep the first and warn [S55] | `AGENTS.override.md`, `AGENTS.md`, `AGENTS.MD`, `CLAUDE.md` or `CLAUDE.MD` per directory [S54] |
| **Windsurf** (now "Devin Desktop"; docs moved to docs.devin.ai) | `.devin/skills/` preferred, `.windsurf/skills/` legacy; user `~/.codeium/windsurf/skills`, `~/.config/devin/skills` [S57] | **Yes** (`.agents/skills`, `~/.agents/skills`); `.claude/skills` only if "Claude Code config reading" is enabled [S57] | Not documented; unconfirmed | `AGENTS.md` (root = always-on; subdirectory = glob rule); `.windsurf/rules` / `.devin/rules` [S58] |
| **Cline** | Docs: `.cline/skills/`, `.clinerules/skills/`, `.claude/skills/`; user `~/.cline/skills` [S59]. Source and config doc also list project `.agents/skills` and user `~/.agents/skills`; the docs page lags the code [S60][S61] | **Yes (per source, not per the skills docs page)** | **Yes.** Scanner uses `readdir` + `stat`, which follows links [S62]. Global skills beat project skills of the same name [S59] | `.clinerules/`, `.cline/rules/`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`, `~/.agents/AGENTS.md` [S63] |
| **Amp** | `.agents/skills/` and `.claude/skills/` in the project and parents; user `~/.config/agents/skills`, `~/.agents/skills`, `~/.config/amp/skills`, `~/.claude/skills`; first skill with a given name wins, in that order [S64] | **Yes** | Not documented; unconfirmed. Duplicates are resolved by name, so a link plus its target is harmless | `AGENTS.md`; falls back to `AGENT.md` or `CLAUDE.md` only in a directory with no `AGENTS.md` [S65] |

Notes beyond the requested list:

- Kiro reads `.kiro/skills` and `~/.kiro/skills`; its page names no other locations, so it is probably not reading `.agents/skills` (unconfirmed) [S66].
- Junie reads `.junie/skills` plus `.agents/skills` (trusted projects) and not `.claude/skills` [S67].
- Vercel's table lists `.qwen/skills`, `.roo/skills`, `.goose/skills` and others as install targets [S6]. That is where the installer writes, not necessarily everything the agent reads. rea says Qwen also reads `~/.agents/skills` [S2].

**Verdict on the owner's belief.** Among the agents requested, Claude Code is the only one that cannot read project-level `.agents/skills`: confirmed by vendor docs, plus local tests for Claude Code, Codex and `agy`. Three refinements:

1. `agy` ignores user-level `~/.agents/skills`, so a user-scope install would need `~/.gemini/antigravity-cli/skills` or `~/.gemini/config/skills` [S34][S33]. Project scope is fine.
2. Cline's skills docs page omits `.agents/skills` although its code reads it [S59][S60].
3. Outside the list, Kiro looks like another exception, and Gemini CLI is being retired in favour of `agy`.

## 4. Subagent / agent definition files (project level)

| Agent | Project definition files | Format | Reads another agent's dir? | Notes |
| --- | --- | --- | --- | --- |
| Claude Code | `.claude/agents/` (recursive; walks up to the repo root), `~/.claude/agents/`, plugin `agents/`, `--agents` flag [S69] | Markdown with YAML frontmatter; `name` and `description` required; optional `tools`, `model`, `skills`, `hooks`, `isolation`, ... Unknown fields are ignored [S69] | No `.agents/agents` in the docs. Tested locally: it follows symlinks (file, dir and whole-dir links) | `skills:` preloads full skill text into the subagent; without it the subagent can still call the Skill tool [S69] |
| Codex | `.codex/agents/*.toml`, `~/.codex/agents/` | TOML; `name`, `description`, `developer_instructions` required; optional model settings and `skills.config`. `sandbox_mode`, `approval_policy`, `mcp_servers` placed in an agent file do not override the parent [S70] | No (docs name only `.codex/agents`) | Built-ins `default`, `worker`, `explorer`; a custom file named `explorer` overrides the built-in [S70] |
| Antigravity (CLI + IDE) | `.agents/agents/<name>.md` or `.agents/agents/<name>/agent.md`; user `~/.gemini/config/agents/` [S71][S72] | Markdown + YAML; `name`, `description` required; `tools` (list), `model` (`inherit`/`flash`/`pro`), `commandExecutionPolicy`, `mcpServers`, `skills`, `mainAgent`, `subagent` [S71] | `agy` did not list `.claude/agents` (tested) | Docs warn that an unmapped tool name in `tools` can hang the subagent [S71]. Tested: dir symlinks inside `.agents/agents` are listed |
| Gemini CLI | `.gemini/agents/*.md`, `~/.gemini/agents/*.md` [S73] | Markdown + YAML: `name`, `description`, `kind`, `tools`, `mcpServers`, `model`, `max_turns`, `timeout_mins` | No | Product retired for individuals [S41] |
| Cursor | `.cursor/agents/`, `.claude/agents/`, `.codex/agents/` (+ user equivalents); `.cursor/` wins ties [S74] | Markdown + YAML: optional `name`, `description`, `model`, `readonly`, `is_background` | **Yes, deliberately**: "Claude compatibility" and "Codex compatibility" | Unclear whether `.codex/agents` TOML is parsed; unconfirmed |
| GitHub Copilot / VS Code | `.github/agents/*.agent.md`, `.claude/agents/*.md`; user `~/.copilot/agents`, `~/.claude/agents` [S75]. Copilot CLI docs list only `.github/agents/` and `~/.copilot/agents/` [S76] | `.agent.md` with `description`, `name`, `tools`, `agents`, `model`, `handoffs`, `user-invocable`, ... Claude format (`name`, `description`, `tools` string, `disallowedTools`) also accepted by VS Code | **Yes** (`.claude/agents` in VS Code) | |
| opencode | `.opencode/agents/*.md`, `~/.config/opencode/agents/`, or the `agent` key in `opencode.json` [S77] | Markdown + YAML: `description` required; `mode: primary|subagent|all`, `model`, `permission`, ... | No (docs do not mention `.claude/agents`) | |
| pi | None built in; its README says pi "skips features like sub-agents" [S78]. An optional example extension reads `.pi/agents/*.md` and `~/.pi/agent/agents/` [S79] | Markdown | n/a | |
| Windsurf / Devin Desktop | No documented custom subagent file; unconfirmed (searches found only third-party claims) | n/a | n/a | |
| Cline | `.cline/agents/` is listed as "Project agent definitions" [S61]; rulesync describes YAML files `<name>.yaml` with frontmatter-style header [S12]. Cline's docs page only describes the runtime `spawn_agent` tool [S80] | YAML | n/a | |
| Amp | No Markdown format. Custom agents are TypeScript plugins in `.amp/plugins/*.ts` [S81] | Code | n/a | |

**Does any project centralise these?** Yes, by rendering, not linking:

- **ruler** `.ruler/agents/<name>.md` -> `.claude/agents/*.md`, `.cursor/agents/*.md`, `.codex/agents/*.toml`, `.github/agents/*.md`. It is experimental and off by default, replaces target directories wholesale on each apply, skips agents without a native format, and the outputs are gitignored by default [S11].
- **rulesync** `.rulesync/subagents/*.md` -> about 30 targets, including `.agents/agents/<name>.md` for Antigravity, `.cline/agents/<name>.yaml`, and a "simulated subagents" mode for tools without a native primitive. It documents `.agents/agents/` as "the cross-vendor location AGENTS.md-era clients actually scan", read by Antigravity and Kimi Code [S12].
- **Reader-side compatibility:** Cursor and VS Code load `.claude/agents` (and Cursor `.codex/agents`) directly, so one Claude-format file serves Claude Code, Cursor and VS Code [S74][S75].

**Skills-only projects.** obra/superpowers ships no agent definition files. Its code-review skill says to "Dispatch a `general-purpose` subagent" with a prompt template that lives inside the skill folder (`code-reviewer.md`); `subagent-driven-development` does the same with `implementer-prompt.md` and `task-reviewer-prompt.md`; for Codex it maps dispatch to `spawn_agent`, with optional role files under `~/.codex/agents/` [S14]. Vercel's CLI, OpenSkills and rea also ship only skills [S6][S13][S1].

**Context from this repository.** ADR 0003 and Spec 2 section 9 launch Workers and Reviewers as detached bare Sessions through a wrapper, not as in-session subagents; whether the Lead can drive the review loop with subagents is an open question [R1][R2].

## 5. Git and symlink problems documented by these projects

- **Windows.** `core.symlinks=false` checks symlinks out "as small plain files that contain the link text" [S82]. Git for Windows leaves symlink support off unless `core.symlinks=true`, with Developer Mode (or the `SeCreateSymbolicLinkPrivilege` right) available, and `ln -s` in Git Bash makes copies; directory junctions need no privilege [S83]. The consequence for skills (a `.claude/skills/<name>` text file where Claude expects a directory means no skill loads) is my inference from those two facts; no vendor doc states it. Repository-level confirmation: unconfirmed.
- **Vercel's installer** uses a junction with an absolute target on Windows, so what it creates is not portable if committed, and it falls back to copies whenever `symlink()` fails [S7]. Issue #1199 (open) reports that teams who commit skills hit cross-platform trouble with symlinks and that `update` flips `--copy` installs back to symlinks because the lock records no install mode [S9].
- **rea** refuses symlinks in the destination and installs copies; it also refuses to touch skill directories from a Windows MSIX-redirected process [S1][S2].
- **ruler / rulesync** avoid the problem by copying. ruler's gitignore-by-default design breaks in worktrees (gitignored outputs are not carried over), so it tells users to commit the outputs or re-run `apply` [S11]. rulesync follows symlinks in its source tree with no containment check and documents it as a trust boundary [S12].
- **Codex** ignores a symlinked `SKILL.md` file but follows a symlinked skill directory, in both the CLI and the desktop app [S27][S28]. Both Codex (#11314) and Gemini CLI (#16247) users hit silent failure from relative targets resolved against the wrong directory [S29][S38].
- **Claude Code.** Docs: symlinked skill folders are supported [S20]. In Cowork sessions it skips symlinked `CLAUDE.md`/rules that resolve outside the working directory [S24]. Reports of symlinked skills missing from the `/skills` UI or autocomplete are open (#14836) but did not reproduce in my test on 2.1.287 [S22]. User-level whole-dir link `~/.claude/skills -> ~/.agents/skills` pulls Claude's account-synced `synced/` folder into the shared directory [S21].
- **Duplicate discovery.** Agents that read both `.claude/skills` and `.agents/skills` (opencode, Cursor, VS Code, Cline, Amp, Windsurf) see a linked skill twice. Observed effects: opencode v1 warns per skill [S52]; Gemini CLI warns on `/skills reload` [S39]; Amp resolves by name (documented) [S64]; Cursor's staff say duplicates come from two separate installs (not links) and offer the third-party toggle [S45]. Whether Cursor de-duplicates two links to one target is unconfirmed.
- **Cloud / sandboxed agents.** agentskills.io says project-level skills "travel with the code" when an agent works on a cloned repository [S10]; Claude cloud sessions load the repo's `.claude/skills` [S20]. Cursor Cloud Agent does not follow symlinks [S44]. opencode's worktree sandbox did not find skills behind a `.claude/skills` link (closed "not planned") [S52].

## 6. Recommended layout

### (a) Skills

1. Canonical, committed, real files: `.agents/skills/<name>/` (SKILL.md plus `references/`, `scripts/`). It is the only project location read natively by Codex, `agy`, Gemini CLI, Cursor, Copilot/VS Code, opencode, pi, Windsurf, Cline, Amp and Junie (sections 0 and 3).
2. For Claude Code only: one managed relative directory symlink per skill, `.claude/skills/<name> -> ../../.agents/skills/<name>`, computed from the link's own directory. Verified on Claude Code 2.1.287 and what Vercel's CLI does. Prefer per-skill links over a whole-directory link: the installer then owns exactly the links it records in the lock and leaves the user's own `.claude/skills/*` alone.
3. Never link `SKILL.md` itself (Codex rejects it) and keep the link name equal to the target directory name and the frontmatter `name` (agentskills.io requires the name to match the directory).
4. Windows without symlink rights: make `rapid-ship sync` detect a failed `symlink()` (or a plain file where a link should be) and write a real copy, record "copy" per skill in the lock, and have `status --strict` check byte equality for copies. Do not commit junctions or absolute targets. Add a Linux CI check that each `.claude/skills/<name>` is a symlink to the canonical directory.
5. Document the duplicate-read cost for opencode, Cursor, Amp and others, and the opt-outs (`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` [S53], Amp `amp.skills.disableClaudeCodeSkills` [S64], the Cursor toggle [S45]). Do not add `.cursor/skills`, `.codex/skills` or `.gemini/skills` links; they add duplicates for no gain.
6. Instructions: keep `AGENTS.md` canonical and give Claude Code a real `CLAUDE.md` containing `@AGENTS.md` (this repository already does). Claude Code reads a bare `AGENTS.md` only when no `CLAUDE.md` exists and only on v2.1.277+ [S24].
7. Project scope only. A user-scope install would hit `agy` ignoring `~/.agents/skills` [S34].

### (b) Worker / Reviewer definitions

1. Ship skills only, and keep Worker and Reviewer instructions in the canonical skills (for example `rs-work` and `rs-review`). Walk starts each Worker and Reviewer as a bare Session and names the skill in the launch command, so no definition file is needed [R1][R2]. This matches superpowers [S14].
2. If in-session subagents are adopted later, do not try to share one definition file across agents: Codex needs TOML, tool and model vocabularies differ, and Antigravity can hang on an unmapped tool name [S70][S71]. Generate thin stubs (name, description, and one line "follow skill X") from a single source, and record them in the lock so `status --strict` detects drift. Targets: `.claude/agents/<name>.md` (also read by Cursor and VS Code), `.agents/agents/<name>.md` (Antigravity) and `.codex/agents/<name>.toml` (Codex). Because the stubs hold no instructions, a stale stub cannot disagree with the skill.
3. Symlinks are acceptable for agent files only between Markdown targets: Claude Code followed file, directory and whole-directory links in my test, and `agy` listed a linked directory. Codex always needs a rendered file.
4. Leave out Windsurf, pi and Amp (no Markdown subagent format) and omit `tools:` and `model:` from stubs unless set per target.

## 7. Open items (unconfirmed)

- Whether Claude's desktop Code tab reads `.claude/agents` and project `AGENTS.md` the same way as the CLI (the desktop page confirms shared settings and skills only).
- Windows behaviour of Codex with symlinked skill directories after #8369 closed.
- Whether Cursor, VS Code, Windsurf and Amp follow symlinked skill directories (their docs are silent; Cursor's forum shows mixed results).
- Whether opencode 2.0 still warns about duplicate skills when `.claude/skills` links to `.agents/skills`.
- Windsurf/Devin Desktop custom subagent files.
- Whether Cursor parses `.codex/agents/*.toml`.
- Gemini CLI retirement date: the docs notice says June 18, 2026; the detailed account comes from secondary articles.

## Sources

Local tests and repository context:

- [R1] `docs/adr/0003-walk-on-bare-sessions-orchestrator-deferred.md` (this repo)
- [R2] `docs/superpowers/specs/2026-10-15-walk-flow-design.md` sections 5 and 9 (this repo)

rea:

- [S1] https://github.com/morluto/rea/blob/main/docs/installation.md
- [S2] https://github.com/morluto/rea/blob/main/docs/client-configuration.md
- [S3] https://github.com/morluto/rea/blob/main/src/application/SupportedClients.ts
- [S4] https://github.com/morluto/rea/blob/main/src/application/SetupSkill.ts
- [S5] https://github.com/morluto/rea/blob/main/README.md
- [S15] https://github.com/morluto/rea/tree/main/.agents/skills
- [S16] https://raw.githubusercontent.com/morluto/rea/main/.gitignore

Installers and standards:

- [S6] https://github.com/vercel-labs/skills/blob/main/README.md
- [S7] https://github.com/vercel-labs/skills/blob/main/src/installer.ts
- [S8] https://github.com/vercel-labs/skills/blob/main/src/agents.ts
- [S9] https://github.com/vercel-labs/skills/issues/1199 , /1200 , /1355 , /851
- [S10] https://agentskills.io/home , https://agentskills.io/client-implementation/adding-skills-support , https://agentskills.io/specification
- [S11] https://github.com/intellectronica/ruler/blob/main/README.md
- [S12] https://github.com/dyoshikawa/rulesync/blob/main/docs/reference/file-formats.md , https://github.com/dyoshikawa/rulesync/blob/main/README.md , https://github.com/dyoshikawa/rulesync/blob/main/docs/guide/simulated-features.md
- [S13] https://github.com/numman-ali/openskills/blob/main/README.md
- [S14] https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md , https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md , https://github.com/obra/superpowers/blob/main/skills/using-superpowers/references/codex-tools.md
- [S17] https://github.com/numman-ali/openskills (last push date from the GitHub API)

Claude Code:

- [S20] https://code.claude.com/docs/en/skills
- [S21] https://github.com/anthropics/claude-code/issues/16345
- [S22] https://github.com/anthropics/claude-code/issues/14836
- [S23] https://github.com/anthropics/claude-code/issues/50052
- [S24] https://code.claude.com/docs/en/memory
- [S25] https://code.claude.com/docs/en/desktop
- [S69] https://code.claude.com/docs/en/sub-agents

Codex:

- [S26] https://learn.chatgpt.com/docs/build-skills (308 redirect from https://developers.openai.com/codex/skills)
- [S27] https://github.com/openai/codex/issues/15756
- [S28] https://github.com/openai/codex/issues/15844
- [S29] https://github.com/openai/codex/issues/11314
- [S30] https://github.com/openai/codex/issues/8400 , https://github.com/openai/codex/issues/8369
- [S31] https://learn.chatgpt.com/docs/agent-configuration/agents-md
- [S32] https://github.com/openai/codex/issues/17344
- [S70] https://learn.chatgpt.com/docs/agent-configuration/subagents (308 redirect from https://developers.openai.com/codex/subagents)

Antigravity and Gemini CLI:

- [S33] https://antigravity.google/docs/skills
- [S34] https://github.com/google-antigravity/antigravity-cli/issues/103
- [S35] https://github.com/vercel-labs/skills/issues/633
- [S36] https://antigravity.google/docs/rules
- [S71] https://antigravity.google/docs/subagents
- [S72] https://www.antigravity.google/docs/cli/commands/agents
- [S37] https://geminicli.com/docs/cli/skills/
- [S38] https://github.com/google-gemini/gemini-cli/issues/16247
- [S39] https://github.com/google-gemini/gemini-cli/issues/26579 , https://github.com/google-gemini/gemini-cli/issues/28944
- [S40] https://geminicli.com/docs/cli/gemini-md/
- [S41] https://geminicli.com/docs/core/subagents/ (page notice)
- [S42] https://thenewstack.io/gemini-cli-antigravity-replacement/ (secondary; seen only in search results)
- [S73] https://geminicli.com/docs/core/subagents/

Cursor, VS Code, GitHub:

- [S43] https://cursor.com/docs/context/skills
- [S44] https://forum.cursor.com/t/discovery-of-symlinked-skills-not-working-for-all-cases-in-cli/163569 , https://forum.cursor.com/t/symlink-support-for-skills-missing-in-cursor-cloud-agent/153603 , https://forum.cursor.com/t/cursor-doesnt-follow-symlinks-to-discover-skills/149693
- [S45] https://forum.cursor.com/t/duplicate-skills-and-unknown-origins/169575
- [S46] https://cursor.com/docs/context/rules
- [S74] https://cursor.com/docs/subagents
- [S47] https://code.visualstudio.com/docs/copilot/customization/agent-skills
- [S48] https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- [S49] https://github.com/microsoft/vscode/issues/328122
- [S50] https://code.visualstudio.com/docs/copilot/customization/custom-instructions
- [S75] https://code.visualstudio.com/docs/copilot/customization/custom-agents
- [S76] https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli

opencode, pi, Windsurf, Cline, Amp, others:

- [S51] https://opencode.ai/docs/skills/
- [S52] https://github.com/anomalyco/opencode/issues/31977 , /46327 , /18848 , /40349 , /42216 , /16188
- [S53] https://opencode.ai/docs/rules/
- [S77] https://opencode.ai/docs/agents/
- [S54] https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/configuration.md
- [S55] https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md
- [S56] https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/src/core/skills.ts
- [S78] https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md
- [S79] https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/examples/extensions/subagent
- [S57] https://docs.devin.ai/desktop/cascade/skills (308/307 redirect from https://docs.windsurf.com/windsurf/cascade/skills)
- [S58] https://docs.devin.ai/desktop/cascade/agents-md
- [S59] https://docs.cline.bot/customization/skills
- [S60] https://github.com/cline/cline/blob/main/apps/vscode/src/core/storage/skill-directories.ts
- [S61] https://github.com/cline/cline/blob/main/docs/getting-started/config.mdx
- [S62] https://github.com/cline/cline/blob/main/apps/vscode/src/core/context/instructions/user-instructions/skills.ts
- [S63] https://docs.cline.bot/customization/cline-rules
- [S80] https://docs.cline.bot/features/subagents
- [S64] https://ampcode.com/docs/customize/skills
- [S65] https://ampcode.com/docs/customize/agents-md
- [S81] https://ampcode.com/news/custom-agents (seen only in search results)
- [S66] https://kiro.dev/docs/skills/
- [S67] https://junie.jetbrains.com/docs/agent-skills.html

Git:

- [S82] `man git-config`, entry `core.symlinks` (local git 2.39.5)
- [S83] https://gitforwindows.org/symbolic-links
