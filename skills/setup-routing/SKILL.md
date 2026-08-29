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

**Version:** The CLAUDE.md version marker is ALWAYS the installed plugin version read from `plugin.json` (see Step 6) — never a number stated in this file. (Historical feature labels like "v1.11.0 Model Routing" below refer to old marker generations, not to the value to write.)

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Ask about the project

Ask the user ONE question:

> What kind of project is this? (e.g., Swift iOS app, React/Next.js web app, Python API, Node.js backend, Flutter mobile app, Claude Code plugin/skill, data pipeline, infrastructure/Terraform, monorepo, static site, or describe it)

**STOP HERE.** Do not continue to the next step until the user responds. End your message with the question.

### Step 2: Ask follow-up questions

Based on the project type, ask 3-5 focused follow-up questions. Always include questions 1-3. Add 4-9 based on relevance:

1. What test framework will you use? (or "no tests yet")
2. Will this be deployed? Where? (or not deployed)
3. Any security concerns? (auth, user data, payments, external APIs — helps evaluate `/cso`)
4. Will this have a UI testable in a browser? What URL? (skip for CLI tools, libraries, pipelines)
5. Is there a design component? (UI mockups, design system — skip for backend-only)
6. Is this a team project with a regular cadence? (helps evaluate `/retro`)
7. Is this a long-running project or a one-off? (helps evaluate `/learn`)
8. Do you have existing linting, type checking, or test suites? (helps evaluate `/health`)
9. Is this a monorepo? Which directory will you work in? (helps evaluate `/freeze`)

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
| `/superpowers-gstack:autoimplement` | Multi-phase plans where the user always confirms phase boundaries — chains `/review` + `/pitfall-verification` automatically (pitfall auto-chains `/codex review` + the third lens per tier — no separate codex step). v2.14.0+ adds active pre-flight that reviews the plan body itself before Phase 1 unless the latest plan commit matches the marker regex `^(chore\|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]\|$)` (closes the gap between writing-plans and autoimplement). Refuses on <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations/secrets/credentials/.env/.ssh. |
| `/superpowers-gstack:office-hours-track-aware` | All new-project brainstorming — wraps `/office-hours` with track inference (web vs native), inline platform question, design-doc relocation, htmlify --open, and approve-before-render gate. **Intercepts `/office-hours`** — see routing-intercept rules below. |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing. |
| `/superpowers-gstack:macos-native-review` | macOS apps — pre-implementation HIG-citation-grounded review (vocabulary, controls, keyboard shortcuts, semantic colors, sheets, menu bar, dock, App menu). Run on PRDs/specs/plans before implementation. Phase 0 detects macOS signals; auto-N/A for non-macOS projects. |
| `/superpowers-gstack:ios-native-review` | iOS / iPadOS apps — pre-implementation HIG-citation-grounded review (vocabulary, touch targets, navigation paradigm, modal presentation, gestures, system surfaces, keyboard, haptics, semantic colors, animation, privileged operations, accessibility, lifecycle). Run on PRDs/specs/plans before implementation. Phase 0 detects iOS signals; auto-N/A for non-iOS projects. |
| `/superpowers-gstack:quality-review` | After any PRD/spec/plan, before implementation — hunts perceived-quality pitfalls (silent failures, loading/empty states, error recovery, state drift). Complementary to pitfall-verification ("will it work?" vs "will it feel good?"). |
| `/superpowers-gstack:verify-and-land` | Apple + web projects — after a fix, builds the checked-out branch, launches that exact bundle (not the installed copy), proves which build is on screen, gates on the user seeing the fix, then pushes and offers merge/PR. |
| `/superpowers-gstack:e2e-route` | Swift projects — pure dispatcher for E2E test requests: reads platform × intent and routes to the right executor (scaffold skills, MCP-live simulator automation, visual review, ios-visual-explore). |
| `/superpowers-gstack:ios-e2e-scaffold` | iOS SwiftUI apps — one-shot XCUITest scaffolding (TabView/NavigationStack scene-walk, TIER-ranked stubs, iOS-Simulator xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:macos-e2e-scaffold` | macOS SwiftUI apps — one-shot XCUITest scaffolding (Scene-walk, TIER-ranked stubs, xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:ios-visual-explore` | iOS/iPadOS apps — Tier-2 visual exploration via Gemini computer-use when the accessibility tree is insufficient (layout regressions, visual landmarks). Paid API per run; normally reached via /e2e-route. |

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

Read `skills/setup-routing/model-routing.md` (sibling file in this skill's directory) — it holds the canonical per-skill base-tier recommendations and the domain-sensitivity axis (v0.2).

**If `model-routing.md` does not exist** (older cached plugin version, file deletion, etc.): tell the user "Model routing reference is unavailable — likely an older plugin cache. Run `/plugin update superpowers-gstack` and re-run this skill, or proceed without model routing." Then skip directly to Step 6 with the `## Model Routing` section omitted.

**Present the base-tier routing for this project:**

Build a routing preview containing only the skills selected in Step 5 (skip everything excluded). Present as:

**Model routing — base tiers:**

| Skill | Base tier |
|---|---|
| [Skills from Step 5 confirmation, one per row] | [Base tier from model-routing.md] |

For skills marked `see phases` in `model-routing.md`, include a sub-table for that skill showing the per-phase recommendations.

**Infer this project's domain sensitivity** from the Step-2 answers and project type, using the domain table in `model-routing.md`:
- Real-time audio / DSP / signal processing, or any lock-free concurrency (incl. Swift audio engines, game-audio) → **very high** — NB: a plain Swift/SwiftUI CRUD or UI app with none of these signals is **medium**, not very high
- Database migrations / ETL / data-transform, OR security concerns named in Q3 (auth/payments/PII/external APIs) → **high**
- Web/mobile app UI feature work → **medium**
- CLI tools / libraries / format-plumbing / serialization → **low**
- If ambiguous, ask the user one line: "How silently could a subtle bug here compound — very high / high / medium / low?"

After presenting, ask:

> Does this model routing look right? Any adjustments?

**STOP HERE.** Do not continue to Step 6 until the user responds. If adjustments are requested, update and re-present. If the user wants to keep model routing out of CLAUDE.md entirely, note that and skip the Model Routing section in Step 6.

### Step 6: Generate CLAUDE.md

Generate the `CLAUDE.md` file in the project root. Adapt the structure below based on what's relevant — omit entire sections that don't apply.

Keep the generated content tight — every word is a per-session context tax on the project: routing-table row descriptions ≤ 15 words; decision-tree lines ≤ 10 words; no rationale prose in generated sections (the rules carry the behavior; the *why* lives in this plugin's docs).

Before writing the file, read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Include this version as an HTML comment at the top of the generated CLAUDE.md:

```markdown
<!-- superpowers-gstack: {version} -->
<!-- Sections whose heading carries a gstack-<name>-vN marker are plugin-managed: /adapt replaces each one wholesale on upgrade. Put project-specific findings — the measurement you took, the flag that worked — in your own H2 section with no marker, and avoid the reserved headings /adapt owns. -->
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

### Session Management
- `/clear` when transitioning between GStack and Superpowers phases
- Save architecture decisions to `docs/` before clearing after Phase 1
- Reference key changes when starting Phase 3 review
- Skip `/clear` for small projects (< 5 tasks, < 30 min)

[SHARED BLOCKS — emit here, as top-level (H2) sections. Read each file from this
skill's `blocks/` directory (sibling of this SKILL.md) and paste its content
verbatim, in this order:
  1. `blocks/autonomy.md`
  2. `blocks/git-hygiene.md`
  3. `blocks/multi-lens-review.md`
  4. `blocks/code-reuse.md`
  5. `blocks/plan-fidelity.md`
  6. `blocks/session-continuity.md`
  7. `blocks/track-routing.md`
  8. `blocks/xcode-tools.md` — ONLY when `.gstack/track` is `ios`, `macos`, or `both`; skip for web
  9. `blocks/companion-skills.md` — same native-track condition as xcode-tools.md
Resolve `{{...}}` placeholders per `blocks/PLACEHOLDERS.md` before writing — never
let a raw `{{...}}` token reach the generated CLAUDE.md. If the `blocks/` directory
is missing (older plugin cache), warn the user to run `/plugin update
superpowers-gstack` and omit these sections.

**Record what you emitted.** When you write a block into CLAUDE.md, add a SECOND HTML
comment on that block's heading line, immediately after the version marker the block
file itself carries, with nothing at all between the two:

```
<!-- gstack-git-hygiene-v9 --><!-- emitted=162 -->
```

Leave the version marker byte-for-byte as the block wrote it. Provenance is a separate
comment precisely so that marker keeps matching for every reader that knows only the
bare form: an older plugin cache meeting a file this release wrote finds its marker
exactly where it expects it and skips the section as current, instead of reading it as
markerless and appending a duplicate. Putting the attribute inside the marker breaks
that; putting it on a line of its own adds a line to what the next run counts, and is
a line a user tidying their own CLAUDE.md can delete.

This applies to a block whose file carries a version marker, which is what the second
comment attaches to. `blocks/model-routing-section.md` carries none, so it gets no
provenance: an `emitted=` with no marker beside it is a number no reader is looking for,
and the growth check never runs on that section — Model Routing is replaced outright.

`<N>` is `wc -l` of the block file you just read — every line in the file, counted
before any placeholder substitution and before any heading-level demote. This is the
only fact that makes a later upgrade able to tell growth from a block that simply
changed size, so do not estimate it and do not carry a stale value forward from the
section you replaced. Block files themselves never carry `emitted=`; a constant baked
into the source would lie the moment the block changed length.]

[MODEL ROUTING — emit `blocks/model-routing-section.md` here verbatim, resolving
`{{DOMAIN_SENSITIVITY}}` per `blocks/PLACEHOLDERS.md`. Omit the whole section if the
user opted out in Step 5 or `model-routing.md` was unavailable.]

## Project

### Tech Stack
[From user answers]

### Testing
[Test framework and commands]

### QA
[QA URL if applicable — omit this section if no browser UI]

### Deployment
[Deployment target — omit if not deployed]
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
- **Model Routing section:** emit the `## Model Routing` block verbatim (from Step 5.5) with `{{DOMAIN_SENSITIVITY}}` replaced by the inferred value. If the user opted out of model routing in Step 5.5, omit the entire `## Model Routing` section.
- **Phase sub-tables:** include inline only for multi-phase skills selected in Step 5 (e.g. skip the TDD sub-table if `/superpowers:test-driven-development` is not in the selected set).
- Target 100-180 lines total (was 60-100 in v1.10.0 — Model Routing adds ~20 lines). Projects with many multi-phase skills can legitimately reach 200 lines. The 150-line "compliance budget" from v1.10.0 is officially relaxed to 200 lines starting v1.11.0 when Model Routing is present. To stay tight: omit phase sub-tables for skills not selected.

### Step 7: Confirm

After writing the file, tell the user:
- What was generated and which skills were included
- Remind them to add project-specific conventions as they develop them
- Suggest next step based on project type (usually `/office-hours` for new ideas or `/superpowers:brainstorming` if scope is already clear)
