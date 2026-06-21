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

**Version check:** This skill is version **1.11.2**. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation. Projects on version `1.10.0` or earlier will gain a `### Model Routing` section in their CLAUDE.md unless they opt out — surface this clearly so it's not a silent addition. Projects on `1.11.1` or earlier will gain three new gstack skill rows (`/sync-gbrain`, `/scrape`, `/skillify`) in the evaluation tables.

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

Present this to the user for confirmation, and ask one additional question about harnesses (needed for model routing in Step 5):

> Based on my analysis, this is a **[type]** using **[stack]**. Tests run with `[command]`. [Deployed to X / Local-only]. [Has browser UI at X / No browser UI].
>
> Is this correct? Anything to add?
>
> Also: which harnesses do you run this project under? Pick all that apply: **Claude Code**, **Pi (local-only — no network)**, **Pi (hybrid — local + cloud fallback)**, or **None — skip model routing entirely**. Determines which model-routing columns the CLAUDE.md gets. Pick "None" to opt out of the v1.11.0 Model Routing feature for this project (existing CLAUDE.md content stays untouched; only routing updates happen).

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
| `/superpowers-gstack:autoimplement` | Multi-phase plans where the user always confirms phase boundaries — chains `/review` + `/pitfall-verification` + `/codex review` automatically. v2.14.0+ adds active pre-flight that reviews the plan body itself before Phase 1 unless the latest plan commit matches the marker regex `^(chore\|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]\|$)` (closes the gap between writing-plans and autoimplement). Refuses on <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations/secrets/credentials/.env/.ssh. |
| `/superpowers-gstack:office-hours-track-aware` | All new-project brainstorming — wraps `/office-hours` with track inference, inline platform question, design-doc relocation, htmlify --open, and approve-before-render gate. **Intercepts `/office-hours`** — see routing-intercept rules below. |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing. |
| `/superpowers-gstack:macos-native-review` | macOS apps — pre-implementation HIG-citation-grounded review (vocabulary, controls, keyboard shortcuts, semantic colors, sheets, menu bar, dock, App menu). Run on PRDs/specs/plans before implementation. Phase 0 detects macOS signals; auto-N/A for non-macOS projects. |
| `/superpowers-gstack:ios-native-review` | iOS / iPadOS apps — pre-implementation HIG-citation-grounded review (vocabulary, touch targets, navigation paradigm, modal presentation, gestures, system surfaces, keyboard, haptics, semantic colors, animation, privileged operations, accessibility, lifecycle). Run on PRDs/specs/plans before implementation. Phase 0 detects iOS signals; auto-N/A for non-iOS projects. |

### Step 4: Identify gaps and plan changes

Compare the current project state against what Superpowers + GStack needs. Check each item:

**CLAUDE.md routing:**
- [ ] Does `## Skill routing` section exist?
- [ ] Does it include the correct skills for this project?
- [ ] Does it have Routing Logic, Rules, and Session Management?
- [ ] Does it have a `### Model Routing` section (v1.11.0+)? If not, this adaptation will add one.
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
- The routing section follows the same template as `setup-routing` Step 6, adapted to this project
- **Model Routing (v1.11.0+):** read the canonical routing table from `~/.claude/plugins/cache/*/superpowers-gstack/*/skills/setup-routing/model-routing.md` (sibling skill file). Build the tailored sub-table containing:
  - Only skills relevant to this project (filtered from Step 3 evaluation)
  - Only harness columns the user confirmed in Step 2 (Claude Code / Pi local-only / Pi hybrid)
  - For multi-phase skills selected, include the phase sub-tables inline
  - Insert this as a `### Model Routing` subsection of `## Skill routing`, placed after `### Rules` and before `### Session Continuity`
  - **Fallbacks:** If `model-routing.md` is missing (older cached plugin), warn the user and skip the section entirely. If the user picked an unlisted harness ("Other": Cursor, opencode, etc.), emit only the Claude Code column with a note that harness-native model selection should be used instead. If the harness answer was empty/skipped, default to Claude Code column only.
  - If the user opts out, skip this section entirely and note the choice in the final report
**Insert or upgrade the Autonomy and user interruption section.** This section applies to ALL projects (web and native equally — agents over-asking is platform-agnostic). Scan CLAUDE.md for the heading `^#{2,3} Autonomy and user interruption` and its version marker `<!-- gstack-autonomy-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** (legacy pre-v2.8.0) → REPLACE the same way; one-time silent upgrade adds the v1 marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The Autonomy block to insert (verbatim):

```markdown
## Autonomy and user interruption <!-- gstack-autonomy-v1 -->

Default to autonomous continuation. Stopping to ask the user is the LAST resort, not the default. When you complete a planned phase or pass a milestone, the next action is the next phase — NOT a status report followed by "ping me to continue".

### When you MUST stop and ask the user

Only these five categories warrant stopping:

1. **User-territory operation required** — Apple Developer Portal capability registration, OAuth/SSO login, signing into an external service, payment authorization, anything requiring 2FA / Apple ID / human credentials the agent cannot supply
2. **Destructive operation needing explicit approval** — `rm -rf`, `git push --force`, dropping a database table, deleting cloud resources, any operation listed under the user's `/careful` rules
3. **Genuinely ambiguous design choice** — two paths with materially different long-term consequences AND no signal in the spec / plan / prior conversation pointing to one over the other. ("I assume green but maybe blue?" is NOT this — that is over-asking.)
4. **Explicit checkpoint in the skill or plan** — e.g. `swiftui-design-consultation` Phase 3's Approve/Drill/Change/Start-over gate, `executing-plans`' phase review, `office-hours` final approval
5. **You are truly blocked** — missing information you cannot derive, infinite loop you cannot break, error message you cannot interpret after reasonable investigation (read docs, search corpus, try the obvious fix first)

### When NOT to stop

Do NOT stop to:

- ❌ Report completed work and ask "shall I continue with the next phase?"
- ❌ Check in at convenient milestones because it feels considerate
- ❌ Ask "should I do X?" when X is obviously the next step in scope
- ❌ Wait for permission to do work clearly within the user's original request or agreed plan
- ❌ Wrap up a session early because the plan turned out to be larger than expected — finish it

If the next step is clearly within scope, DO IT. Report what happened after it's done.

### Forbidden phrases

These continuation-tokens signal "I have stopped autonomy and now require user input" — if any creep into your output without a category-1-to-5 reason above, you have failed the autonomy default:

- ❌ "Ping me when you want me to continue"
- ❌ "Let me know when you're ready for the next round"
- ❌ "Ready when you are"
- ❌ "Awaiting your go-ahead"
- ❌ "Si fra når jeg skal fortsette"
- ❌ "Bash-prompten din er fortsatt aktiv — si bare 'fortsett'"

If you catch yourself about to write one of these, ask: "Is there a real category-1-to-5 reason here, or am I just being polite?" If polite, delete the sentence and do the next thing instead.

### Status updates DURING work, not AS wait-states

Give brief progress signals while you continue, not as the final word before stopping:

- ✅ "BookmarkStore + 7 tests green. Moving to RecordingScanner now."
- ✅ "Phase 1 build verified on macOS. Starting Phase 2 UI layer."
- ❌ "Phase 1 done. Here's a 12-row status table. Ready for UI when you say so."

The user reads status WHILE you work, not as a wait-state for permission.

### When to STOP, but only after finishing in-scope work

When you do legitimately reach a stopping point (the agreed scope is done, or a category-1-to-5 reason fires), stop cleanly:

- State what's done in one or two sentences
- Name what's blocked (if anything) with the specific reason from the five categories
- Do NOT propose new work or invite continuation — the next session/turn will decide that
```

**Insert or upgrade the Git hygiene & commit cadence section.** This section applies to ALL projects (git is universal). Scan CLAUDE.md for heading `^#{2,3} Git hygiene` and its version marker `<!-- gstack-git-hygiene-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker `v1` (pre-v2.10.1 emitter — universalist convention rule, autonomy cross-ref missing, stash advice without WIP-branch caveat) OR different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. (The Git hygiene block has H4 subsections; "next heading" alone would stop at the first one and leave old v1 prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the v2 marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The Git hygiene block to insert (verbatim):

```markdown
## Git hygiene & commit cadence <!-- gstack-git-hygiene-v2 -->

Commit at meaningful milestones, not at every file save and not only at session end. The goal is a readable git history that lets future-you (or another agent) understand what shipped and why.

### When to commit

Commit when:
- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- About to switch to unrelated work (don't mix concerns in one commit)
- A reversible decision was made (so you can `git revert` cleanly later)
- Before invoking long-running or risky operations (so you have a rollback point)

Do NOT commit:
- Mid-task — wait until the change is coherent
- Just to "save progress" — that's what `git stash` is for (short-lived holds only, minutes to hours; for longer holds create a WIP branch instead so the work survives `git stash clear` and is visible in `git branch`)
- Unrelated changes batched together — split them into separate commits

### Commit message format

Use the convention established in the repo (check `git log --oneline -10` first). Three cases:

- **Repo has a consistent convention** (every recent commit follows the same prefix style — `feat:` / `fix:` / `[TICKET-123]` / plain prose / etc.) → follow it. Do not introduce a different style.
- **Repo log is empty** (first commit, or freshly init'd) → use the default below.
- **Repo log is inconsistent** (mixed styles, no clear winner) → use the default below AND note in your final summary that the project has no clear commit convention so the user can decide whether to standardize.

Default format (use only when no consistent convention is established):

```
<type>(<scope>): <one-line summary>

<body — what changed and why, not how>

<co-authored-by trailer if relevant>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Scope = subsystem/module name.

### Hygiene rules (NEVER violate)

- ❌ `git commit --no-verify` — pre-commit hooks exist for a reason; if a hook fails, fix the root cause
- ❌ `git commit --amend` on commits already pushed — rewrites shared history
- ❌ `git push --force` to `main` or shared branches — destroys others' work
- ❌ `git reset --hard` without first stashing or committing — silent work loss
- ❌ `git add -A` or `git add .` when secrets / large binaries / build artifacts may be present — stage specific paths instead

### Cadence rule

If >5 distinct commits in a row without testing the cumulative state, STOP and verify (build, run tests) before continuing. This STOP is a category-5 ("truly blocked — verification gap") per the Autonomy section above; it overrides the autonomous-continuation default exactly the same way an unresolvable error would. Commits accumulate quickly; cumulative breakage is harder to diagnose than per-commit breakage.

If multiple commits land in a single session without ANY commit being tested, the session is committing "progress without verification" — break that cycle by running the project's test suite, or document explicitly why testing is deferred.
```

**Insert or upgrade the Multi-lens review section.** This section applies to ALL projects (review hygiene is universal). Scan CLAUDE.md for heading `^#{2,3} Multi-lens review` and its version marker `<!-- gstack-multi-lens-review-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Multi-lens review block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.)
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the v1 marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The Multi-lens review block to insert (verbatim):

```markdown
## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v2 -->

Substantive changes need different review lenses — each catches what the others miss:

1. **Self-check** (always, ~30 sec): placeholders, consistency, scope drift, ambiguity
2. **Pitfall verification** (always, max 2 rounds): invoke `/superpowers-gstack:pitfall-verification` — catches domain-specific traps (security, idempotency, contracts, edge cases, LLM-output quirks)
3. **Codex review** (ship-worthy changes only): invoke `/codex review` — catches drift across files and cross-section inconsistency that self-review systematically misses
4. **Third-house lens** (architecture / real-time / security / contracts / migration-logic only): invoke `/superpowers-gstack:third-lens-review` — a *different model house* via OpenRouter reads the patched artifact and finds what two Western houses both took for granted, ending in an adversarial synthesis

### What counts as "ship-worthy"

**YES (run codex):**
- Commits that bump version files (`plugin.json`, `package.json`, `pyproject.toml`, etc.)
- Commits that produce CHANGELOG entries
- `feat:` / `fix:` / `refactor:` commits that affect runtime behavior
- Changes to public contracts (APIs, schemas, generated artifacts, file formats)

**NO (skip codex — it's overkill):**
- Pure docs/typo fixes
- Comment-only changes
- WIP commits (per Continuous Checkpoint mode)
- Test-only additions where coverage is the only change

### Why three lenses, not two

Self-review catches "is this artifact good?" Pitfall catches "what typically breaks in this domain?" Codex catches "what's inconsistent across the codebase that author was too close to see?". Different lenses see different things; running fewer leaves a known gap.

Dogfood evidence (2026-05-19 in superpowers-gstack repo): self-pitfall verification on v2.10.0 ran two rounds and caught 3 issues. After fixing those, `/codex review` caught a 4th — REPLACE-wording drift across 2 unrelated section blocks. Self-review missed it because the author was focused on the *new* section, not on cross-section consistency.

### Cost

- Self-check: free (~30 sec attention budget)
- Pitfall verification: free (LLM thought)
- Codex review: ~$0.05-0.20 per review + 30s-2min wall clock

Acceptable for ship-worthy work. Skip codex explicitly for trivial changes; don't run it on every commit or you'll burn budget on diminishing returns.

### Order matters

Run lenses in order: self → pitfall → codex → (ship-worthy arch/RT/security) third-house. Each pass fixes issues the previous one couldn't catch and reads a cleaner artifact. Running codex *before* pitfall wastes its tokens on issues a simpler pass would have surfaced first; running the third house before codex pays a third model to re-find what codex would have caught.

### Fourth lens: the third house (escalation)

The first three lenses are all self/Anthropic or OpenAI (Codex). For the highest-stakes changes, add a *different model house* — its value is **training-distribution distance**, not raw IQ: it sees architecture-level mistakes ("you never wired it together"), degraded-state bugs, and challenged assumptions the others took for granted.

- **Gate:** architecture, real-time, security, public contracts, or migration logic. Skip for trivial/standard changes.
- **Routing by `--role`** (`scripts/third-lens-review.py`): `architecture`=GLM-5.2 (default, non-sensitive); `sensitive`=Gemini 3.1 Pro (Western infra — enforced via `--sensitive` for auth/keys/health/finance); `correctness`=DeepSeek V4-Pro; `countersynthesis`=GPT-5.5 (refutes the synthesis on the biggest changes).
- **Cost:** ~$0.05/run (GLM), well under $1 even for a 4-house panel. Key in macOS Keychain `openrouter-api-key`.
- **Synthesis is mandatory and adversarial:** a third-house finding is real until explicitly refuted; disagreement is the signal, not noise. Never dump raw output. See the skill for the synthesis format.
```

**Insert or upgrade the Code reuse discipline section.** This section applies to ALL projects (the agentic-duplication failure mode is platform-agnostic). Scan CLAUDE.md for heading `^#{2,3} Code reuse discipline` and its version marker `<!-- gstack-code-reuse-vN -->`. Apply the four-case logic, but with a CRITICAL difference from the other marker-managed sections in case 3:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Code reuse block has subsections one level below the root; "next heading" alone would stop at the first subsection and leave old prose behind.)
3. **Heading present + marker absent** → **PRESERVE, do NOT replace.** This section was newly introduced in v2.12.0 of the plugin — markerless `Code reuse discipline` headings cannot be pre-marker plugin content, which means they are *user-authored* sections that happen to share the heading. Replacing them would silently destroy the user's hand-written content. Instead, leave the user's section intact and surface a notice to the user in the adapt summary: "Found existing markerless `Code reuse discipline` section in CLAUDE.md; preserved as-is. To switch to the plugin-managed version, delete your existing section and re-run `/adapt`." This is the key difference from the other marker-sections (Autonomy, Git hygiene, Multi-lens review, etc.) where case 3 legitimately treats markerless content as pre-marker plugin legacy.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on this section at ship time.

The Code reuse discipline block to insert (verbatim):

```markdown
## Code reuse discipline (before writing) <!-- gstack-code-reuse-v1 -->

Before introducing a new reusable concept — a component, helper, model, type-alias, view-modifier, button-style, extension, hook, utility function — the agent MUST search the codebase for existing implementations first. This catches "context-bounded duplication": the agentic-coding failure mode where a subagent writes a new `EntityCard` without knowing one already exists one directory over.

This is *not* a DRY purity rule. The default stance is pragmatist: three or four similar lines is fine, premature abstraction is a real cost. The rule only fires when introducing something that could plausibly already exist.

### Scope — when to scan

Scan before writing:
- A new struct, class, or component with a domain-shared name (`Card`, `Item`, `Cell`, `Detail`, `Manager`, `Service`, `View`, `Modifier`, `Style`, etc.)
- A new helper function that smells like utility (`formatX`, `parseY`, `validateZ`, `serializeFoo`)
- A new extension, type-alias, ViewModifier, ButtonStyle (Swift) or hook, HOC, wrapper component (web)
- A new shared model / DTO / schema definition

Do NOT scan:
- Lines inside an existing function — that's refactoring, not new-concept introduction
- Inline closures / callbacks specific to one call-site
- Test helpers private to one test file
- One-off scripts not intended for reuse

### How to scan

1. **Grep for the bare concept name** (full-word, case-insensitive) — e.g. `EntityCard`, `formatDate`, `validateEmail`
2. **Glob for matching file paths** — `**/*Card*.swift`, `**/*card*.tsx`, `**/format*.py`
3. **Read** the matches that look related (don't skim — actually verify it's the same concept)
4. **Decide**: REUSE existing / EXTEND existing / WRITE NEW (and report which)

### Verbalize the scan

Before scaffolding the new code, narrate one line in chat (in whatever language the conversation is happening in):

> Checking whether we already have an existing `<concept>` …

Then report findings:

> Found `EntityCard` at `Views/EntityCard.swift:14` — extending it with `.compact` variant rather than writing new.

or:

> No matches for `EntityCard` or `*Card*.swift` — writing new.

This is **narration, not a stop.** Continue scaffolding immediately after reporting findings — do not wait for user input unless the user actively redirects. The narration is for transparency only; it does NOT add a new category to the "5 categories warrant stopping" rule in the Autonomy section above. If the user wants to redirect, they will; otherwise proceed.

This costs ~3 lines of chat per new concept. Worth it; the user gets a chance to see "actually, see `ItemCard` at line N" before the duplicate exists. Silence-first scanning is worse: when duplicates do happen, the user has no signal until /review catches them post-implementation.

### When dispatched as a subagent

When dispatching a subagent under `/superpowers:subagent-driven-development` or any Task-tool dispatch that will write code, include in the dispatch prompt:

> Before introducing new reusable concepts (components, helpers, models, extensions), search the codebase via Grep/Glob for existing implementations. If you find one, **use it or extend it** and continue with your delegated task — report what you reused. If you do not find one, scaffold new and report what you searched for. Escalate to the orchestrator ONLY if the reuse decision is genuinely ambiguous (e.g. the existing implementation almost-but-not-quite fits and adding a parameter would change its semantics for existing callers).

The subagent has narrower context than the orchestrator — this instruction transfers the scanning discipline across the dispatch boundary. Critically, the subagent must NOT stop with a recommendation after finding existing code; it must complete its delegated coding task using the found implementation, escalating only on genuine ambiguity.

### Pragmatist guardrails

- ❌ Do NOT pre-abstract. If two similar lines exist, leave them as two similar lines until a third one shows up.
- ❌ Do NOT refactor existing code unless the task explicitly asks for it. The scan reports existing implementations; it doesn't authorize touching them.
- ❌ Do NOT ask the user "should we be DRY about this?" — the answer is yes-but-pragmatist by default. Just scan first.

### Coverage at adjacent stages

Other skills already handle DRY at other stages — this rule fills the implementation-time gap:

- **`/plan-eng-review`** does pre-implementation reuse-scan at architecture time ("list existing code/flows that already partially solve sub-problems… whether the plan reuses them or unnecessarily rebuilds them"). When that scan has already run, this rule still applies during code-writing but should defer to plan-eng-review's findings for the high-level architecture decisions.
- **`/review` (gstack)** catches DRY violations post-implementation in the `maintainability` specialist (duplicated literal values, duplicated config/setup, DRY Violations checks). That's the last line of defense; this rule is meant to catch duplicates BEFORE they reach review so review can focus on substantive issues.

### Local override

If the user explicitly says "skip the reuse-check for this session" or "just write it, I know nothing similar exists", honor that override. The user has full-codebase context the agent may lack; their override is informed, not a violation. Do not re-litigate.
```

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

The Track-aware routing block to insert (verbatim):

```markdown
## Track-aware routing (dual-track) <!-- gstack-routing-v1 -->

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

### When user invokes /office-hours (no namespace)

Intercept and invoke `/superpowers-gstack:office-hours-track-aware`
instead. The wrapper runs upstream `/office-hours` for the brainstorm,
then handles:
- Track inference from the brainstormed idea (native vs web signals)
- Inline platform question (iOS/macOS/both) if native or ambiguous, only
  when `.gstack/track` is absent
- Design-doc relocation from gstack defaults into repo `docs/`
- `/htmlify --open` rendering BEFORE the approval gate (so the user can
  read the rich HTML before deciding)
- Approve / Revise / Restart gate after they've seen the rendered HTML
- Suggests `/superpowers-gstack:swiftui-design-consultation` next for
  native tracks

User can bypass by typing `/office-hours` (gstack) directly — but for
all dual-track projects, prefer the wrapper.

### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)

User can always bypass by typing the namespaced version directly.
```

**Insert or upgrade the Native Apple development tools section.** Only emit this section when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip entirely for web-only projects). Scan CLAUDE.md for the heading `^#{2,3} Native Apple development tools` and its version marker `<!-- gstack-xcode-tools-vN -->`. Apply the same four-case logic as Track-aware routing above:

1. **Heading present + marker matches `v3`** → skip (idempotent).
2. **Heading present + marker `v1` or `v2`** (v1 assumed XcodeBuildMCP universally; v2 added CLI fallback but missed capabilities/signing/portal split) → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. (The Native Apple tools block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below. Auto-upgrade is what the marker pattern is for.
3. **Heading present + marker absent** (pre-v2.7.0) → REPLACE the same way; one-time silent upgrade adds the v3 marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The Native Apple development tools block to insert (verbatim, when track ∈ {ios, macos, both}):

```markdown
## Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v3 -->

Xcode-related operations MUST be performed by the agent — NEVER delegated to the user. The user should never need to open Xcode to verify your work. Prefer MCP tools when available; fall back to CLI when not.

### Tool routing for Apple-platform operations

For each operation, **prefer the MCP tool when available**, falling back to CLI otherwise. Check MCP availability via `ToolSearch` first (these are deferred tools loaded on demand); only drop to CLI if the search returns nothing.

| Operation | Preferred (MCP) | Fallback (CLI, always available with Xcode) |
|---|---|---|
| Type-check Swift code | `mcp__swiftui-rag__swift_typecheck` | `xcrun swift -typecheck <file>.swift` |
| Search SwiftUI corpus / HIG | `mcp__swiftui-rag__search_swiftui_corpus` | (no CLI fallback — use `mcp__apple-docs__search_apple_docs`) |
| HIG conformance review | `mcp__swiftui-rag__review_macos_hig`, `review_accessibility`, `review_liquid_glass` | (no CLI fallback — read HIG via `mcp__apple-docs__get_apple_doc_content` and apply rules manually) |
| Build Xcode project for simulator | `mcp__XcodeBuildMCP__build_sim` | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16' build` |
| Build + launch in simulator | `mcp__XcodeBuildMCP__build_run_sim` | `xcodebuild ... build && xcrun simctl launch booted <bundle-id>` |
| Run XCTest / Swift Testing | `mcp__XcodeBuildMCP__test_sim` | `xcodebuild test -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'` |
| List / boot simulators | `mcp__XcodeBuildMCP__list_sims`, `boot_sim` | `xcrun simctl list devices`, `xcrun simctl boot <udid>` |
| Capture simulator logs | `mcp__XcodeBuildMCP__launch_app_logs_sim` | `xcrun simctl spawn booted log stream --predicate '...'` |
| UI automation in simulator | `mcp__XcodeBuildMCP__ui_tap`, `screenshot`, `snapshot_ui`, `ui_describe_all` | `xcrun simctl io booted screenshot <path>.png` (screenshots only; tap/snapshot are MCP-only) |
| Apple platform docs (HIG, APIs) | `mcp__apple-docs__search_apple_docs`, `get_apple_doc_content` | `man` pages for CLI tools; online docs at developer.apple.com |
| WWDC video search / examples | `mcp__apple-docs__search_wwdc_content`, `get_wwdc_code_examples` | (no CLI fallback — fetch via `WebFetch` against developer.apple.com/wwdc) |

### Project file management (prefer declarative)

Avoid hand-editing the auto-generated XML in `.xcodeproj/project.pbxproj`. Two declarative alternatives:

- **XcodeGen** (`brew install xcodegen`) — generate `.xcodeproj` from a committable `project.yml`. Re-runnable via `xcodegen generate`. Strongly recommended for solo / small-team SwiftUI projects.
- **Tuist** — more powerful declarative project manager; heavier dependency. Use if XcodeGen isn't sufficient (multi-target, complex schemes, generated frameworks).

For new SwiftUI projects under this plugin, default to XcodeGen unless the project explicitly requires Tuist.

### Capabilities, signing, and provisioning

Three surfaces, three different handlers:

| Surface | What | Who handles it |
|---|---|---|
| `*.entitlements` file | Declares which capabilities (CloudKit, push, app groups, keychain sharing, etc.) the app uses | **Agent** — edit declaratively as XML |
| `project.yml` (XcodeGen) or `*.xcodeproj` build settings | `DEVELOPMENT_TEAM`, code signing identity, target capabilities | **Agent** — edit declaratively |
| Apple Developer Portal (developer.apple.com) | Registers container IDs (CloudKit), App IDs, provisioning profiles, push certificates | **User** — Apple ID login + 2FA required; agent cannot access |

**CloudKit example workflow:**

1. **Agent edits entitlements** to declare CloudKit + container:
   ```xml
   <key>com.apple.developer.icloud-services</key>
   <array><string>CloudKit</string></array>
   <key>com.apple.developer.icloud-container-identifiers</key>
   <array><string>iCloud.com.example.appname</string></array>
   ```
2. **Agent ensures `DEVELOPMENT_TEAM` is set** (e.g. via `project.yml`):
   ```yaml
   settings:
     base:
       DEVELOPMENT_TEAM: WXNUGGYB2B
   ```
3. **Agent regenerates and builds:**
   ```bash
   xcodegen generate
   xcodebuild build -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'
   ```
4. **If signing fails** with "container not registered" / "no matching provisioning profile":
   - STOP. Surface to user with exact portal steps, e.g.:
     > "Container `iCloud.com.example.appname` is not registered in Apple Developer Portal. Go to https://developer.apple.com/account → Identifiers → click your App ID (com.example.appname) → enable the iCloud capability → link the container `iCloud.com.example.appname`. ~30 seconds. Ping me when done and I'll retry the build."
5. **User does the portal-click** (~30 sec).
6. **Agent retries `xcodebuild build`** — succeeds.

**Why this split:** Apple Developer Portal requires Apple ID + 2FA, which no MCP/CLI tool automates stably. Xcode's Capabilities pane is just a frontend to the same portal — clicking there doesn't help an agent that has no portal session either. The declarative path (entitlements + project.yml) is the only path that works for BOTH the agent AND for git history (YAML is committable; portal state is implicit).

For CI/CD with many apps or frequent provisioning operations, **Fastlane match** + spaceship is the standard automation surface. Out of scope for solo vibe-coder workflows; mention it only if the user scales beyond one or two apps.

### Anti-patterns (NEVER do these)

- ❌ "Open Xcode and run the tests" — use `mcp__XcodeBuildMCP__test_sim` (MCP) or `xcodebuild test` (CLI) instead
- ❌ "Build the app in Xcode to verify" — use `mcp__XcodeBuildMCP__build_sim` (MCP) or `xcodebuild build` (CLI) instead
- ❌ "Take a screenshot of the simulator" — use `mcp__XcodeBuildMCP__screenshot` (MCP) or `xcrun simctl io booted screenshot` (CLI) instead
- ❌ "Click through the Signing & Capabilities pane in Xcode" — declare entitlements in `*.entitlements` + `project.yml` (XcodeGen) instead
- ❌ "Check what the system color looks like in HIG" — use `mcp__apple-docs__search_apple_docs` or `mcp__swiftui-rag__search_swiftui_corpus` instead

If a verification step requires Xcode the UI, you have not finished the task — use MCP or CLI tools to verify, then report results.
```

**Insert or upgrade the Companion skills (discovery) section.** Only emit when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip for web-only projects). Scan CLAUDE.md for heading `^#{2,3} Companion skills` and its version marker `<!-- gstack-companion-skills-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v1`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. **If the existing root is H3** (nested under `## Skill routing`, as setup-routing emits), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the v1 marker.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The Companion skills block to insert (verbatim, when track ∈ {ios, macos, both}):

```markdown
## Companion skills (discovery — not routing) <!-- gstack-companion-skills-v1 -->

The two-framework story (Superpowers + GStack) is what this plugin routes. But other ecosystem-specific expert skills exist that complement the workflow. They are NOT auto-invoked; the plugin doesn't depend on them; they are listed here so any agent reading this CLAUDE.md knows they exist and how to install them when relevant.

### Apple / SwiftUI projects (Antoine van der Lee's skill suite)

| Skill | What it does | Install |
|---|---|---|
| `swiftui-expert-skill` | Code-level SwiftUI review: state management, view composition, deprecated-API migration, Liquid Glass adoption, Instruments tracing | `/plugin marketplace add AvdLee/SwiftUI-Agent-Skill` then `/plugin install swiftui-expert@swiftui-expert-skill` |
| `swift-concurrency-expert-skill` | async/await, actors, Sendable conformance, Swift 6 migration, data-race diagnosis | After adding the marketplace above: `/plugin install swift-concurrency@swift-concurrency-expert-skill` |
| `core-data-expert-skill` | Core Data modeling, performance tuning, CloudKit ↔ Core Data integration | `/plugin install core-data-expert@core-data-expert-skill` |
| `swift-testing-expert-skill` | Swift Testing macros (`#expect`, `#require`), parameterized tests, XCTest migration | `/plugin install swift-testing-expert@swift-testing-expert-skill` |

### How these fit the workflow

The Antoine skills operate at **code review time**, complementing the pre-implementation review skills shipped in this plugin:

| Stage | This plugin | Companion (Antoine) |
|---|---|---|
| Spec / plan validation (pre-code) | `macos-native-review`, `ios-native-review` | — |
| Code-level review (post-code) | — | `swiftui-expert-skill`, `swift-concurrency-expert-skill`, `core-data-expert-skill`, `swift-testing-expert-skill` |

Install separately — they live in their own marketplace, not bundled with superpowers-gstack.
```

- If no `## Session Continuity` section exists in CLAUDE.md: ADD the following block. If it already exists, REPLACE it with the current version:
  ```
  ## Session Continuity
  On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) immediately after presenting the summary.
  After /compact: if handoff.md does not contain `## Mode: auto`, ask the user once: "Context was compressed. Want me to activate auto context guard for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill.
  ```

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
