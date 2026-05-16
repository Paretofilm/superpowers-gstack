---
name: setup-routing
description: Generate a tailored CLAUDE.md with routing rules for the Superpowers + GStack workflow. Asks about project type, evaluates relevant skills from both frameworks, and produces a project-specific routing plan.
---

# Setup Routing — CLAUDE.md Generator

You are setting up the Superpowers + GStack combined workflow for a **new project**. Your job is to generate a `CLAUDE.md` file with routing rules tailored to this specific project.

Invoke this skill with: `/superpowers-gstack:setup-routing`

<!-- Keep in sync with skills/adapt/SKILL.md dependency + directory checks -->
**Dependency check:** Before anything else, verify both upstream frameworks are installed. Run:

```bash
ls -d ~/.claude/plugins/cache/claude-plugins-official/superpowers/*/ 2>/dev/null | head -1
ls -d ~/.claude/skills/gstack/ 2>/dev/null
```

If either path is missing, STOP and tell the user:

> This plugin is glue for two upstream frameworks. Install them first:
>
> **Missing: Superpowers** — `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`
>
> **Missing: GStack** — `git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup`
>
> Only mention the framework(s) that are actually missing. Restart Claude Code after installing, then run `/superpowers-gstack:setup-routing` again.

Do NOT proceed until both frameworks are present.

**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:setup-routing` again.

**Important:** If the project already has a `CLAUDE.md` file with existing content, STOP and suggest the user runs `/superpowers-gstack:adapt` instead — it preserves existing content while adding routing.

**Version:** This skill writes version **1.11.0** into the CLAUDE.md version marker.

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Ask about the project

Ask the user ONE question:

> What kind of project is this? (e.g., Swift iOS app, React/Next.js web app, Python API, Node.js backend, Flutter mobile app, Claude Code plugin/skill, data pipeline, infrastructure/Terraform, monorepo, static site, or describe it)

**STOP HERE.** Do not continue to the next step until the user responds. End your message with the question.

### Step 2: Ask follow-up questions

Based on the project type, ask 3-5 focused follow-up questions. Always include questions 1-3 and 10. Add 4-9 based on relevance:

1. What test framework will you use? (or "no tests yet")
2. Will this be deployed? Where? (or local-only)
3. Any security concerns? (auth, user data, payments, external APIs — helps evaluate `/cso`)
4. Will this have a UI testable in a browser? What URL? (skip for CLI tools, libraries, pipelines)
5. Is there a design component? (UI mockups, design system — skip for backend-only)
6. Is this a team project with a regular cadence? (helps evaluate `/retro`)
7. Is this a long-running project or a one-off? (helps evaluate `/learn`)
8. Do you have existing linting, type checking, or test suites? (helps evaluate `/health`)
9. Is this a monorepo? Which directory will you work in? (helps evaluate `/freeze`)
10. Which harnesses will you run this project under? Pick all that apply: **Claude Code**, **Pi (local-only — no network calls)**, **Pi (hybrid — local + cloud fallback)**, or **None — skip model routing entirely**. Determines which model-routing columns get emitted in CLAUDE.md. Pick "None" to opt out of the new v1.11.0 Model Routing section completely; setup-routing falls back to its v1.10.0 behavior for this project.

Ask all follow-up questions in a single message. **STOP HERE.** Do not continue to the next step until the user responds. Do not add suggestions or any other content after the questions. End your message with the questions.

### Step 3: Evaluate relevant Superpowers skills

Based on the project type and answers, evaluate which Superpowers skills are relevant. Think through each one:

| Skill | Consider relevant when... |
|---|---|
| `/superpowers:brainstorming` | Almost always — skip only for trivial projects |
| `/superpowers:writing-plans` | Almost always — skip only for single-file changes |
| `/superpowers:subagent-driven-development` | Projects with 5+ tasks, benefits from parallel TDD |
| `/superpowers:executing-plans` | Smaller projects (< 5 tasks), or when user wants more control |
| `/superpowers:systematic-debugging` | Any project with code that can have bugs |
| `/superpowers:dispatching-parallel-agents` | Projects with clearly independent modules |
| `/superpowers:using-git-worktrees` | Projects where feature isolation matters |
| `/superpowers:finishing-a-development-branch` | Projects using feature branches and PRs |
| `/superpowers:test-driven-development` | Projects with testable code (most projects) |
| `/superpowers:verification-before-completion` | Complex projects where correctness is critical |
| `/superpowers:requesting-code-review` | Multi-file changes (runs automatically during SDD, but can be invoked manually) |
| `/superpowers:receiving-code-review` | After `/review` or PR feedback requires code changes — structures the response with TDD |
| `/superpowers:writing-skills` | Only for Claude Code plugin/skill projects |

### Step 4: Evaluate relevant GStack skills

Think through each GStack skill, organized by phase:

**Phase 1 — Planning:**

| Skill | Consider relevant when... |
|---|---|
| `/office-hours` | New product ideas, features with unclear scope |
| `/plan-ceo-review` | Projects with strategic decisions or significant scope |
| `/plan-eng-review` | Projects needing architecture decisions |
| `/plan-design-review` | Projects with UI/UX components |
| `/design-consultation` | New projects defining a design system from scratch (creates DESIGN.md) |
| `/design-shotgun` | When you want multiple design variants to compare before committing |
| `/plan-devex-review` | Projects with developer-facing surfaces (APIs, CLIs, SDKs, libraries) |
| `/plan-tune` | Tune plan-skill question preferences (one-time, per-project) |
| `/autoplan` | When all three plan reviews are relevant — chains them automatically |

**Phase 3 — Review & QA:**

| Skill | Consider relevant when... |
|---|---|
| `/review` | Almost always — pre-merge code review |
| `/qa <url>` | Projects with a browser-accessible UI (include the URL) |
| `/qa-only <url>` | Same, but report-only (no auto-fixes) |
| `/cso` | Projects handling auth, user data, payments, or external APIs. For security-critical features, run BEFORE `/review` |
| `/design-review` | Projects with visual UI — catches spacing, alignment, inconsistencies |
| `/design-html` | When you have an approved design and need production HTML/CSS |
| `/devex-review` | Developer-facing projects — live audit of onboarding flow, docs, CLI help |
| `/investigate` | Bugs discovered AFTER Phase 2 — in QA, staging, or production. Do NOT use during Phase 2 implementation (use `/superpowers:systematic-debugging` instead) |

**Phase 4 — Ship & Monitor:**

| Skill | Consider relevant when... |
|---|---|
| `/ship` | Projects using git with feature branches and PRs |
| `/land-and-deploy` | Projects with CI/CD deployment pipelines |
| `/canary` | Projects with production monitoring needs |
| `/landing-report` | Read-only PR queue + sibling-workspace dashboard (workspace-aware ship) |
| `/setup-deploy` | One-time: configure deploy platform (Fly.io, Vercel, Render, etc.) for `/land-and-deploy` |
| `/document-release` | Projects with documentation to maintain |
| `/retro` | Team projects with regular sprint cadence |
| `/learn` | Long-running projects (> 2 weeks) — saves cross-session learnings |
| `/setup-gbrain` | Long-running projects wanting cross-session memory (PGLite local or Supabase) |
| `/sync-gbrain` | Long-running projects with gbrain — keeps the brain current with this repo's code and refreshes CLAUDE.md search guidance |
| `/health` | Projects with existing linting, type checking, or test suites |
| `/make-pdf` | Projects needing publication-quality documentation or reports |

**Utility (any phase):**

| Skill | Consider relevant when... |
|---|---|
| `/careful` | Projects where destructive commands are risky (production DBs, shared infra) |
| `/freeze` | Monorepos or projects where edits should be restricted TO a specific directory (allow-list, not block-list) |
| `/unfreeze` | Clear the `/freeze` boundary mid-session without ending the session |
| `/guard` | Production / shared-infra work — combines `/careful` warnings with `/freeze` directory lock |
| `/browse` | Projects needing headless browser interaction beyond QA |
| `/scrape` | Projects pulling data from web pages — prototypes a flow once, codifies it via `/skillify` |
| `/skillify` | After a successful `/scrape` — persists the flow as a permanent browser-skill so future calls run in ~200ms |
| `/open-gstack-browser` | Projects wanting a visible AI-controlled Chromium with live activity feed |
| `/pair-agent` | When pairing a remote AI agent with your browser session |
| `/setup-browser-cookies` | One-time: import cookies for authenticated `/qa` and `/browse` testing |
| `/context-handoff` | Long implementation sessions, projects using SDD, or any multi-step workflow |
| `/htmlify` | Any project — generates beautiful HTML companions for MD artefacts (design docs, plans, handoffs) so verbose output stays readable. Optional PostToolUse hook auto-fires. |
| `/context-save` | Save progress and working state |
| `/context-restore` | Resume where you left off |
| `/benchmark` | Projects with performance monitoring needs |
| `/benchmark-models` | Projects comparing AI model performance |
| `/codex` | Projects needing second opinions or adversarial code review |

### Step 5: Present the routing plan

Show the user which skills from each framework you've selected and why. Format as:

**Superpowers (implementation):**
- Skill — why it's relevant

**GStack (by phase):**
- Phase 1: Skill — why
- Phase 3: Skill — why
- Phase 4: Skill — why

**Excluded:**
- Skill — why it's not relevant for this project

Ask: "Does this look right? Any skills to add or remove?"

**STOP HERE.** Do not continue to the next step until the user responds. Do not generate the CLAUDE.md or add any other content. End your message with the question.

If the user wants changes, update your selection and re-present. Repeat until confirmed.

### Step 5.5: Present model routing recommendations

Read `skills/setup-routing/model-routing.md` (sibling file in this skill's directory) — it holds the canonical per-skill model recommendations for Claude Code and the two Pi modes.

**If `model-routing.md` does not exist** (older cached plugin version, file deletion, etc.): tell the user "Model routing reference is unavailable — likely an older plugin cache. Run `/plugin update superpowers-gstack` and re-run this skill, or proceed without model routing." Then skip directly to Step 6 with the `### Model Routing` section omitted.

**If the user's harness answer to Step 2 Q10 was "None — skip model routing entirely"**: skip directly to Step 6 with the entire `### Model Routing` section omitted. Tell the user: "Skipping Model Routing per your request. Re-run `/superpowers-gstack:adapt` later if you change your mind." Do not present a preview.

**If the user's harness answer to Step 2 Q10 was "Other" or named an unlisted harness** (Cursor, opencode, Codex CLI, etc.): include only the **Claude Code** column in the preview, and emit a note at the **top of the `### Model Routing` section in the generated CLAUDE.md** (immediately after the section header, before the "Identify your runtime" paragraph). The note must say:

> **Note:** Your harness (`<name>`) is not in this routing table. Claude Code defaults are shown as a starting point — override per task with your harness's native model-selection mechanism (e.g. opencode's agent-types, Cursor's model picker, Codex CLI's `--model` flag).

**If Q10 was skipped or returned an empty/unparseable answer**: default to the **Claude Code** column only and proceed.

**If user selected only Pi columns (no Claude Code)**: emit a note at the top of the `### Model Routing` section saying:

> **Note:** Claude Code column is not present because you didn't select it. If you open this project in Claude Code anyway, use the Pi (hybrid) column as a rough approximation — its Anthropic-leaning recommendations (sonnet for most, haiku for mechanical) are the closest stand-in.

Build a routing preview containing only:
- The skills selected in Step 5 (skip everything excluded)
- The harness columns selected in Step 2 question 10 (skip columns the user isn't using)

Present it as:

**Model routing for [list selected harnesses]:**

| Skill | [Selected harness columns] |
|---|---|
| [Skills from Step 5 confirmation, one per row] | [Recommendation from model-routing.md] |

For skills marked `see phases` in `model-routing.md`, include a sub-table for that skill showing the per-phase recommendations.

**For Pi columns specifically:** the table in `model-routing.md` references concrete model IDs (e.g. `qwen3.6-mlx-8bit`, `qwen3.6-27b-optiQ-SFT`). If the user is unsure which Pi models they have loaded, ask them to run:

```bash
cat ~/.pi/agent/models.json 2>/dev/null | grep '"id"'
```

…and confirm coverage. If a recommended Pi model is not listed, mark that row with `(verify availability)` in the generated CLAUDE.md.

After presenting, ask:

> Does this model routing look right? Any adjustments?

**STOP HERE.** Do not continue to Step 6 until the user responds. If adjustments are requested, update and re-present. If the user wants to keep model routing out of CLAUDE.md entirely, note that and skip the Model Routing section in Step 6.

### Step 6: Generate CLAUDE.md

Generate the `CLAUDE.md` file in the project root. Adapt the structure below based on what's relevant — omit entire sections that don't apply.

Before writing the file, read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Include this version as an HTML comment at the top of the generated CLAUDE.md:

```markdown
<!-- superpowers-gstack: {version} -->
# [Project Name]

## Skill routing

This project uses Superpowers + GStack. Each owns a distinct phase:

### GStack — [list relevant phases, e.g., "Planning, Review, Shipping"]

**Planning:**
- [Only skills selected in Step 4, Phase 1]

**Review & QA:**
- [Only skills selected in Step 4, Phase 3]

**Ship & Monitor:**
- [Only skills selected in Step 4, Phase 4]

### Superpowers — Implementation
- [Only skills selected in Step 3]

### Routing Logic
[Generate a project-specific decision tree. See examples below.]

### Rules
- Never run GStack and Superpowers skills in the same phase
- Never nest subagents from different frameworks
- Use `/superpowers:systematic-debugging` for bugs found during implementation (Phase 2)
- Use `/investigate` only for bugs found in QA or production (Phase 3+)
- Superpowers specs go in `docs/superpowers/`
- GStack state lives in `~/.gstack/projects/`

### Model Routing (v0.1, advisory)

**Identify your runtime:**
- **Claude Code** — your system prompt names you "Claude Code". Use the **Claude Code** column.
- **Pi (local-only)** — `~/.pi/agent/AGENTS.md` confirms Pi runtime; no network calls allowed. Use **Pi (local-only)**.
- **Pi (hybrid)** — Pi runtime with cloud calls permitted. Use **Pi (hybrid)**.

If your runtime doesn't match a listed column, default to **Claude Code**.

**How to apply the recommendations** (differs by harness):
- **In Claude Code:** dispatch subagents (via `Agent` tool, parallel agents, or SDD workers) with `model:` set to the column entry for the task. Multi-phase skills become per-phase subagent calls.
- **In Pi:** no subagent dispatch is available (Pi runs a single process per session). Use the column entry as a guide for *which Pi provider/model to start the session with* for tasks of this type. For multi-phase skills with phase-varying recommendations:
  - **Preferred:** end the current Pi session (`/new`) between phases and restart with the model matched to the next phase. Acceptable for long-running implementation work.
  - **Pragmatic:** if restarting is friction, pick the model matched to the **most cognitively-demanding phase** in your session (bias toward the larger/stronger model so weaker phases still get adequate capability).
  - Pi aliases (e.g. `qwen3.6-27b-optiQ-SFT`) map to actual `--provider` / `--model` flags — see the alias table in `model-routing.md`.

[Insert routing table here — only the skills confirmed in Step 5, only the harness columns selected in Step 2 Q10. For skills marked "see phases" in `model-routing.md`, include the phase sub-table inline. For Pi rows, use the friendly aliases for readability; orchestrator should map back to actual `id` from the alias table in `model-routing.md` when invoking.]

For multi-phase skills (`/superpowers:test-driven-development`, `/superpowers:subagent-driven-development`, `/superpowers:systematic-debugging`, `/qa`, `/ship`), route per phase — see the sub-tables above.

**Caveats:**
- Advisory only. Override per task when you have evidence.
- Pi rows assume the named models/providers are loaded (`cat ~/.pi/agent/models.json` to verify, and `scripts/start-mlx-server.sh` for the SFT model).
- Swift-implementation rows route to `qwen3.6-27b-optiQ-SFT` (mlx-sft provider, port 8081) only if that provider is running. Otherwise fall back to the row's non-Swift recommendation.
- **Drift warning:** this table is inlined from `model-routing.md` at the time `/setup-routing` was last run. If the plugin updates its routing recommendations, this inline copy stays frozen — re-run `/superpowers-gstack:adapt` to pull the latest. The plugin version that produced this section is stamped in the top-of-file `<!-- superpowers-gstack: X.Y.Z -->` marker.
- Full canonical table with all skills (not just this project's selected subset) lives at `~/.claude/plugins/cache/.../superpowers-gstack/skills/setup-routing/model-routing.md`.

### Session Continuity

On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) immediately after presenting the summary.

After /compact: if handoff.md does not contain `## Mode: auto`, ask the user once: "Context was compressed. Want me to activate auto context handoff for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill.

### Session Management
- `/clear` when transitioning between GStack and Superpowers phases
- Save architecture decisions to `docs/` before clearing after Phase 1
- Reference key changes when starting Phase 3 review
- Skip `/clear` for small projects (< 5 tasks, < 30 min)

## Project

### Tech Stack
[From user answers]

### Testing
[Test framework and commands]

### QA
[QA URL if applicable — omit this section if no browser UI]

### Deployment
[Deployment target — omit if local-only]
```

**Routing Logic examples** — adapt to the project, don't copy verbatim:

For a web app with UI:
```
New feature idea     → /office-hours
Ready to build       → /superpowers:brainstorming
Bug during coding    → /superpowers:systematic-debugging
Bug found in QA      → /investigate
Code complete        → /review → /qa http://localhost:3000
Review feedback?     → /superpowers:receiving-code-review → fix → /review again
Security-sensitive?  → /cso (before /review)
Ready to ship        → /ship
Trivial change       → Just do it
```

For a CLI tool / library (no UI):
```
New feature idea     → /office-hours
Ready to build       → /superpowers:brainstorming
Bug fix              → /superpowers:systematic-debugging
Code complete        → /review
Review feedback?     → /superpowers:receiving-code-review → fix → /review again
Ready to ship        → /ship
Trivial change       → Just do it
```

For a Claude Code plugin:
```
New skill idea       → /superpowers:brainstorming
Writing skills       → /superpowers:writing-skills
Bug fix              → /superpowers:systematic-debugging
Code complete        → /review
Ready to ship        → /ship
```

**Important rules for generation:**
- Do NOT include skills that were excluded in Step 5
- Do NOT add generic descriptions — keep it actionable
- DO adapt the routing logic to this specific project type
- DO include the default QA URL if the user provided one
- DO include test commands if known
- Omit entire sections that don't apply (no empty "QA: N/A" sections)
- **Model Routing section:** include only the harness columns selected in Step 2 Q10 and only the rows for skills selected in Step 5. If the user opted out of model routing in Step 5.5, omit the entire `### Model Routing` section.
- **Phase sub-tables:** include inline only for multi-phase skills selected in Step 5 (e.g. skip the TDD sub-table if `/superpowers:test-driven-development` is not in the selected set).
- Target 100-180 lines total (was 60-100 in v1.10.0 — Model Routing adds ~20-50 lines depending on selected skills, harness count, and how many multi-phase skills are included). Projects that select all three harnesses + many multi-phase skills can legitimately reach 200 lines; that is acceptable when the routing is being used. The 150-line "compliance budget" from v1.10.0 is officially relaxed to 200 lines starting v1.11.0 when Model Routing is present. To stay tight: omit any column not selected, omit phase sub-tables for skills not selected.

### Step 7: Confirm

After writing the file, tell the user:
- What was generated and which skills were included
- Remind them to add project-specific conventions as they develop them
- Suggest next step based on project type (usually `/office-hours` for new ideas or `/superpowers:brainstorming` if scope is already clear)
