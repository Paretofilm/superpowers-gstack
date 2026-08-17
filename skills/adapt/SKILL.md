---
name: adapt
description: Adapt an existing project to the Superpowers + GStack workflow. Analyzes the project, identifies gaps, updates CLAUDE.md routing without losing existing content, and sets up required structure.
---

# Adapt to Superpowers + GStack

You are adapting an existing project to the Superpowers + GStack combined workflow. Unlike `setup-routing` (which is for new/empty projects), this skill preserves everything that already exists and makes only the changes needed for a smooth transition.

Invoke this skill with: `/superpowers-gstack:adapt`

<!-- Keep in sync with skills/setup-routing/SKILL.md dependency + directory checks -->
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
> Only mention the framework(s) that are actually missing. Restart Claude Code after installing, then run `/superpowers-gstack:adapt` again.

Do NOT proceed until both frameworks are present.

**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:adapt` again.

**Version check:** The current version is ALWAYS the installed plugin version read from `plugin.json` (see the marker step) — never a number stated in this file. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation. Projects with an older Model Routing block (v0.1 `### Model Routing` with Pi/MLX columns) will have it **replaced** by the new top-level `## Model Routing` (v0.2, Claude-only, domain-aware); projects with none will gain one unless they opt out — surface this clearly so it's not a silent change. Projects on `1.11.1` or earlier will gain three new gstack skill rows (`/sync-gbrain`, `/scrape`, `/skillify`) in the evaluation tables.

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Analyze the project

Read and analyze the following (skip any that don't exist):

1. **CLAUDE.md** — existing instructions, conventions, routing rules
2. **Package files** — `package.json`, `Package.swift`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, `plugin.json`, etc.
3. **Test configuration** — `jest.config.*`, `vitest.config.*`, `pytest.ini`, `.swiftpm/`, `Makefile` test targets, etc.
4. **CI/CD** — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.
5. **Git state** — current branch, remotes, branching strategy (check recent branch names)
6. **Project structure** — `ls` the root and key directories to understand the layout
7. **docs/** — existing documentation structure

Summarize what you found to the user. Be concise — focus on what matters for the transition.

### Step 2: Identify the project type and stack

Based on Step 1, determine:
- Project type (web app, API, mobile, plugin, library, monorepo, etc.)
- Language(s) and frameworks
- Test framework and how to run tests
- Deploy target (if any)
- QA URL (if browser-testable)
- Whether it's a team or solo project

Present this to the user for confirmation:

> Based on my analysis, this is a **[type]** using **[stack]**. Tests run with `[command]`. [Deployed to X / not deployed]. [Has browser UI at X / No browser UI].
>
> Is this correct? Anything to add?

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

### Step 3: Evaluate relevant skills

Use the same evaluation tables as `setup-routing` to determine which Superpowers and GStack skills are relevant. The tables are reproduced here for reference:

**Superpowers skills:**

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

**GStack skills — Phase 1 (Planning):**

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

**GStack skills — Phase 3 (Review & QA):**

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

**GStack skills — Phase 4 (Ship & Monitor):**

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

**GStack skills — Utility:**

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
| `/superpowers-gstack:e2e-route` | Swift projects — pure dispatcher for E2E test requests: reads platform × intent and routes to the right executor (scaffold skills, MCP-live simulator automation, visual review, ios-visual-explore). |
| `/superpowers-gstack:ios-e2e-scaffold` | iOS SwiftUI apps — one-shot XCUITest scaffolding (TabView/NavigationStack scene-walk, TIER-ranked stubs, iOS-Simulator xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:macos-e2e-scaffold` | macOS SwiftUI apps — one-shot XCUITest scaffolding (Scene-walk, TIER-ranked stubs, xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:ios-visual-explore` | iOS/iPadOS apps — Tier-2 visual exploration via Gemini computer-use when the accessibility tree is insufficient (layout regressions, visual landmarks). Paid API per run; normally reached via /e2e-route. |

### Step 4: Identify gaps and plan changes

Compare the current project state against what Superpowers + GStack needs. Check each item:

**CLAUDE.md routing:**
- [ ] Does `## Skill routing` section exist?
- [ ] Does it include the correct skills for this project?
- [ ] Does it have Routing Logic, Rules, and Session Management?
- [ ] Does it have a `## Model Routing` section (v0.2+)? If not, this adaptation will add one.
- [ ] Is there existing content that must be preserved?

**Project structure:**
- [ ] Does `docs/superpowers/` exist? (needed for specs and plans)
- [ ] Is there a feature branch workflow? (needed for `/review` and `/ship`)
- [ ] Is there a remote configured? (needed for `/review` and `/ship`)

**Potential conflicts:**
- [ ] Does CLAUDE.md have instructions that contradict the workflow? (e.g., "never use subagents", "don't use TDD")
- [ ] Are there existing hooks or workflows that might conflict?
- [ ] Is the project on `main` with no branches? (needs branching strategy)

Present the gap analysis to the user:

> **Ready for Superpowers + GStack:**
> - [things that already work]
>
> **Needs changes:**
> - [what needs to be added/modified — be specific]
>
> **Potential conflicts:**
> - [anything that might cause issues]
>
> Shall I proceed with these changes?

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

### Step 5: Apply changes

Apply the changes identified in Step 4. Follow these rules strictly:

**CLAUDE.md updates:**
- Read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Add or update an HTML comment at the very top of CLAUDE.md: `<!-- superpowers-gstack: {version} -->`
- If CLAUDE.md exists: READ it first, then INSERT or UPDATE the `## Skill routing` section
- NEVER delete or rewrite existing sections (conventions, tech stack, project-specific rules)
- If a `## Skill routing` section already exists: **UPDATE its plugin-managed subsections per the per-section case-logic below (cases 1-4 for each marker-section).** Do NOT wholesale-replace the entire Skill routing block — that would destroy any user-authored subsections nested inside (e.g. a hand-written `### Code reuse discipline` markerless heading). The per-section logic handles every plugin-managed subsection individually; anything inside Skill routing that the per-section logic does NOT match must be PRESERVED verbatim, including its position and surrounding whitespace.
- If no `## Skill routing` section exists: ADD it after the first heading (or at the top if no heading)
- The routing section follows the same template as `setup-routing` Step 6, adapted to this project. Keep the generated content tight — every word is a per-session context tax on the project: routing-table row descriptions ≤ 15 words; decision-tree lines ≤ 10 words; no rationale prose in generated sections (the rules carry the behavior; the *why* lives in this plugin's docs).
- **Model Routing (v0.2):** read the canonical routing table from `~/.claude/plugins/cache/*/superpowers-gstack/*/skills/setup-routing/model-routing.md`. Infer this project's domain sensitivity from the project analysis and Step 3 evaluation:
    - Real-time audio / DSP / signal processing, or any lock-free concurrency (incl. Swift audio engines, game-audio) → **very high** — NB: a plain Swift/SwiftUI CRUD or UI app with none of these signals is **medium**, not very high
    - Database migrations / ETL / data-transform, OR security concerns (auth/payments/PII/external APIs) → **high**
    - Web/mobile app UI feature work → **medium**
    - CLI tools / libraries / format-plumbing / serialization → **low**
    - If ambiguous, ask the user one line: "How silently could a subtle bug here compound — very high / high / medium / low?"
  - **First, replace any stale Model Routing block.** If the project's existing CLAUDE.md already has a Model Routing section from a prior plugin version — whether a v0.1 `### Model Routing` subsection (the one with Pi/MLX/local-model columns) or an older top-level `## Model Routing` — DELETE that entire section (from its heading through the line before the next heading of equal-or-higher level) before emitting the new one. This is an explicit exception to the "never delete existing sections" rule above: Model Routing is fully plugin-managed, so a stale copy must be **replaced**, not preserved alongside the new block — otherwise the generated CLAUDE.md carries two contradictory routing tables (old Pi/MLX + new Claude-only).
  - Then emit a top-level `## Model Routing` section (placed after `## Skill routing` and all its subsections): read `blocks/model-routing-section.md` from the plugin's `skills/setup-routing/blocks/` directory (same path resolution as `model-routing.md` above) and emit its content verbatim, substituting `{{DOMAIN_SENSITIVITY}}` with the inferred value.

  - **Fallback:** If `model-routing.md` is missing (older cached plugin), warn the user and skip the section entirely.
  - If the user opts out, skip this section entirely and note the choice in the final report

**Shared block files.** Every "block to insert" below is single-sourced in the plugin at `skills/setup-routing/blocks/<name>.md` (sibling skill directory — from this skill's base directory: `../setup-routing/blocks/<name>.md`; via the cache glob: `~/.claude/plugins/cache/*/superpowers-gstack/*/skills/setup-routing/blocks/`). Read the named file and use its content as the verbatim block. Resolve `{{...}}` placeholders per `blocks/PLACEHOLDERS.md` before inserting — never let a raw `{{...}}` token reach the generated CLAUDE.md. If the blocks directory is missing (older plugin cache), warn the user to run `/plugin update superpowers-gstack` and skip the affected sections.

**Insert or upgrade the Autonomy and user interruption section.** This section applies to ALL projects (web and native equally — agents over-asking is platform-agnostic). Scan CLAUDE.md for the heading `^#{2,3} Autonomy and user interruption` and its version marker `<!-- gstack-autonomy-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** (legacy pre-v2.8.0) → REPLACE the same way; one-time silent upgrade adds the current marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/autonomy.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Git hygiene & commit cadence section.** This section applies to ALL projects (git is universal). Scan CLAUDE.md for heading `^#{2,3} Git hygiene` and its version marker `<!-- gstack-git-hygiene-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v3`** → skip (idempotent).
2. **Heading present + marker `v1` or `v2` (older emitters — universalist convention rule, autonomy cross-ref missing, stash advice without WIP-branch caveat) OR different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. (The Git hygiene block has H4 subsections; "next heading" alone would stop at the first one and leave old v1 prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/git-hygiene.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Multi-lens review section.** This section applies to ALL projects (review hygiene is universal). Scan CLAUDE.md for heading `^#{2,3} Multi-lens review` and its version marker `<!-- gstack-multi-lens-review-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches the current version (`v5`)** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Multi-lens review block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.)
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/multi-lens-review.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Code reuse discipline section.** This section applies to ALL projects (the agentic-duplication failure mode is platform-agnostic). Scan CLAUDE.md for heading `^#{2,3} Code reuse discipline` and its version marker `<!-- gstack-code-reuse-vN -->`. Apply the four-case logic, but with a CRITICAL difference from the other marker-managed sections in case 3:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Code reuse block has subsections one level below the root; "next heading" alone would stop at the first subsection and leave old prose behind.)
3. **Heading present + marker absent** → **PRESERVE, do NOT replace.** This section was newly introduced in v2.12.0 of the plugin — markerless `Code reuse discipline` headings cannot be pre-marker plugin content, which means they are *user-authored* sections that happen to share the heading. Replacing them would silently destroy the user's hand-written content. Instead, leave the user's section intact and surface a notice to the user in the adapt summary: "Found existing markerless `Code reuse discipline` section in CLAUDE.md; preserved as-is. To switch to the plugin-managed version, delete your existing section and re-run `/adapt`." This is the key difference from the other marker-sections (Autonomy, Git hygiene, Multi-lens review, etc.) where case 3 legitimately treats markerless content as pre-marker plugin legacy.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on this section at ship time.

The block to insert: read `blocks/code-reuse.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Keep the plan true to the code section.** This section applies to ALL projects (plan drift is not track-specific). Scan CLAUDE.md for heading `^#{2,3} Keep the plan true to the code` and its version marker `<!-- gstack-plan-fidelity-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. (The block has H3 subsections; "next heading" alone would stop at the first one and leave old prose behind.) **If the existing root is H3**, demote every subsection in the replacement one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker. (Unlike Code reuse, this heading is specific enough that a user-authored collision is implausible.)
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root). If you instead insert it under `## Skill routing` as H3, you MUST demote every H3 subsection to H4 — otherwise the next marker upgrade stops at the first subsection and leaves stale content behind.

The block to insert: read `blocks/plan-fidelity.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Session Continuity section.** This section applies to ALL projects (context handoff is platform-agnostic). Scan CLAUDE.md for heading `^#{2,3} Session [Cc]ontinuity` and its version marker `<!-- gstack-session-continuity-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level (see the heading-level rule below).
3. **Heading present + marker absent** → the section is either a pre-2.36.0 emitted block or one the user wrote themselves, and unlike `Git hygiene & commit cadence` or `Autonomy and user interruption`, "Session Continuity" is a heading a project could plausibly own. Tell them apart before touching it: treat it as emitted ONLY if the section body mentions `docs/superpowers/handoff.md`. **If it does** → REPLACE as in case 2. This is the upgrade that matters, because every pre-2.36.0 emitter wrote a sensor keyed only to the `## Mode: auto` Markdown marker, which `/superpowers-gstack:context-handoff` deletes the moment it writes YAML — so those projects re-ask the opt-in question after every single compact. **If it does not** → leave the user's section untouched, insert the block as a separate H2 section, and tell the user both now exist so they can merge by hand. Never silently overwrite a section you cannot attribute to a past emitter.
4. **Heading absent** → APPEND the block as H2.

**Heading-level rule.** The block ships with an H2 root and has NO subsections, so it is exempt from the H3→H4 subsection demote that complicates the other marker-managed sections. It is NOT exempt from matching the existing root level. `setup-routing` before 2.36.0 emitted this section as `### Session Continuity` nested under `## Skill routing`; pasting the H2 block verbatim over an H3 root promotes it to H2 and silently reparents every following H3 sibling underneath it. So when the section being replaced is H3, change the block's FIRST LINE to `### Session Continuity <!-- gstack-session-continuity-v1 -->` and paste the remaining lines unchanged.

The block to insert: read `blocks/session-continuity.md` (see **Shared block files** above) and insert its content verbatim, subject to the heading-level rule above.

**Verify after inserting.** "Modify the template's first line, then paste the rest verbatim" is the instruction shape most easily skipped under pressure — the reflex is to paste the whole block unchanged. So do not trust that you applied it: re-read the section you just wrote, and confirm its first line has the SAME number of `#` characters as the heading you replaced. If it does not, fix it now, before moving on. Getting this wrong is silent — the file still looks well-formed, but every H3 that followed the section has been reparented underneath it.

**Preserve or upgrade existing Track-aware routing.** Before
inserting the Track-aware routing section, scan the project's
CLAUDE.md. Check two things independently: (a) does any heading
matching `^#{2,3} Track-aware routing \(dual-track\)` exist (H2 or
H3 — `setup-routing` emits H3 as subsection, `adapt` historically
emitted H2 as top-level), and (b) is there a version marker
`<!-- gstack-routing-vN -->` on that heading line (currently `v1`).
Four cases:

1. **Heading present + marker matches current version (`v1`)** →
   skip (idempotent — re-running adapt does not pollute the file).
2. **Heading present + marker present + different version** →
   REPLACE the section from the heading down to (but not including)
   the next heading of the same OR shallower level. Preserves
   surrounding CLAUDE.md content. This is how routing rules evolve
   without manual editing across N projects. Preserve the original
   heading level (H2 or H3) — do not change it during upgrade.
3. **Heading present + marker absent** (legacy v2.3.0/v2.3.1
   projects) → REPLACE the section the same way as case 2. Treats
   the missing marker as "older than v1". This is a one-time silent
   upgrade; the content replaced is byte-identical to what's already
   there in v2.3.2, plus the marker. Preserve the original heading
   level.
4. **Heading absent** → APPEND the full section as H2 (truly new
   adaptations, or projects that never had dual-track routing).

The version marker is an HTML comment so it does not render in
Markdown previews. Bump the version (`v1` → `v2`) only when the
section's semantics change, not for cosmetic edits.

The block to insert: read `blocks/track-routing.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Native Apple development tools section.** Only emit this section when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip entirely for web-only projects). Scan CLAUDE.md for the heading `^#{2,3} Native Apple development tools` and its version marker `<!-- gstack-xcode-tools-vN -->`. Apply the same four-case logic as Track-aware routing above:

1. **Heading present + marker matches `v4`** → skip (idempotent).
2. **Heading present + marker `v1`, `v2`, or `v3`** (v1 assumed XcodeBuildMCP universally; v2 added CLI fallback but missed capabilities; v3 hardcoded one team's `DEVELOPMENT_TEAM` as default/signing/portal split) → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. (The Native Apple tools block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below. Auto-upgrade is what the marker pattern is for.
3. **Heading present + marker absent** (pre-v2.7.0) → REPLACE the same way; one-time silent upgrade adds the current marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/xcode-tools.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Companion skills (discovery) section.** Only emit when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip for web-only projects). Scan CLAUDE.md for heading `^#{2,3} Companion skills` and its version marker `<!-- gstack-companion-skills-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/companion-skills.md` (see **Shared block files** above) and insert its content verbatim.

**Structure setup:**
- Create `docs/superpowers/specs/` and `docs/superpowers/plans/` if they don't exist
- Add a `.gitkeep` in each empty directory

**Git preparation:**
- If on `main` with uncommitted work: warn the user, do NOT create branches automatically
- If on `main` with clean state: suggest creating a feature branch for the adaptation itself

**What NOT to change:**
- Existing test configuration
- CI/CD pipelines
- Git hooks (unless they directly conflict)
- Code style / linting configuration
- Any existing CLAUDE.md content outside the routing section

### Step 6: Verify and report

After applying changes, verify:
1. Read the updated CLAUDE.md and confirm routing section is correct
2. Confirm `docs/superpowers/` directories exist
3. Check that no existing content was lost

Report to the user:

> **Changes made:**
> - [list each change]
>
> **Preserved:**
> - [existing CLAUDE.md content that was kept]

Then ask:

> Would you like me to run a comprehensive review of the adaptation? This will check that:
> - All routing rules are consistent with your project structure
> - No existing CLAUDE.md content was lost or corrupted
> - The selected skills match your actual tech stack, test setup, and deployment
> - docs/superpowers/ structure is correct
> - There are no conflicts between existing project conventions and the new workflow
>
> The review takes a minute but catches issues before you start using the workflow. Recommended for projects with complex existing setups.

**STOP HERE.** Do not continue to Step 7 or add any other content. End your message with the question above. Wait for the user's response before proceeding.

If the user says yes, run the review:

1. **Re-read the updated CLAUDE.md** end-to-end and check for internal consistency
2. **Cross-check routing against project files** — does the routing reference skills that don't make sense? (e.g., `/qa` listed but no browser UI, `/cso` listed but no auth/user data)
3. **Verify preserved content** — diff the old vs new CLAUDE.md mentally. Was anything accidentally removed or mangled?
4. **Check for contradictions** — do existing CLAUDE.md instructions conflict with the new routing rules?
5. **Validate structure** — do all referenced directories exist? (`docs/superpowers/specs/`, `docs/superpowers/plans/`)
6. **Test routing logic** — walk through 3-4 common scenarios for this project type and verify the decision tree produces the right skill

Report findings. If issues are found, fix them immediately and re-verify.

### Step 7: Suggest next steps

After the review (or if the user skipped it):

> **Next steps:**
> - [suggest the appropriate first action based on project state]
>   - Working on a new feature? → `/superpowers:brainstorming`
>   - Have code ready for review? → `/review`
>   - Starting fresh? → `/office-hours`
>
> **Tip:** Run `/superpowers-gstack:adapt` again after major project changes (new deploy target, added test framework, etc.) to update routing.
