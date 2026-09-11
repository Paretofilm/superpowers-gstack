# Skill roster — what to evaluate for a project

Read by `/superpowers-gstack:adapt` Step 3. One table set, used for every project;
the weekly update workflow edits this file when upstream adds, removes or renames
a skill. Rows are `| skill | consider relevant when... |`.

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
| `/superpowers-gstack:htmlify` | Offline HTML rendering of MD artefacts when the Artifact tool is unavailable; otherwise prefer the Artifact tool. |
| `/context-save` | Save progress and working state |
| `/context-restore` | Resume where you left off |
| `/benchmark` | Projects with performance monitoring needs |
| `/benchmark-models` | Projects comparing AI model performance |
| `/codex` | Projects needing second opinions or adversarial code review |
| `/superpowers-gstack:autoimplement` | Multi-phase plans — one subagent per phase, `/review` + `/pitfall-verification` chained at every phase boundary (`/review` owns the Codex pass; pitfall adds domain inference and the third lens per tier). Active pre-flight reviews the plan body before Phase 1 unless the latest plan commit matches `^(chore\|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]\|$)`. Refuses on <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations/secrets/credentials/.env/.ssh. |
| `/superpowers-gstack:office-hours-track-aware` | All new-project brainstorming — wraps `/office-hours` with track inference (web vs native), inline platform question, design-doc relocation, and an Artifact preview before the approval gate. **Intercepts `/office-hours`** — see routing-intercept rules below. |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing. |
| `/superpowers-gstack:apple-native-review` | iOS / iPadOS / macOS apps — pre-implementation HIG-citation-grounded review; platform from `.gstack/track` or the artifact; every finding cites a HIG page fetched this run (apple-docs MCP for API reference). Run on PRDs/specs/plans before implementation. |
| `/superpowers-gstack:quality-review` | After any PRD/spec/plan, before implementation — hunts perceived-quality pitfalls (silent failures, loading/empty states, error recovery, state drift). Complementary to pitfall-verification ("will it work?" vs "will it feel good?"). |
| `/superpowers-gstack:verify-and-land` | Apple + web projects — after a fix, builds the checked-out branch, launches that exact bundle (not the installed copy), proves which build is on screen, gates on the user seeing the fix, then pushes and offers merge/PR. |
| `/superpowers-gstack:e2e-route` | Swift projects — pure dispatcher for E2E test requests: reads platform × intent and routes to the right executor (scaffold skill, MCP-live simulator automation, visual review). |
| `/superpowers-gstack:e2e-scaffold` | iOS or macOS SwiftUI apps — one-shot XCUITest scaffolding (scene-walk, TIER-ranked stubs, identifier suggestions, xcresult runner from `templates/run-uitests.sh` honouring `.gstack/e2e-executor`). Manual only; normally reached via /e2e-route. |
| `/superpowers-gstack:spec-drift` | Any project with plans in `docs/superpowers/plans/` — standalone "does this plan still match the code?" audit: runs `/ship` Step 8's plan-completion section from disk (hash-pinned) against an explicit plan and base, on any branch, shipped or not. Report + JSON + exit 0/1/2; never edits code. |
