# Superpowers + GStack: Combined Development Manual

A practical guide to using Superpowers and GStack together for AI-assisted development with Claude Code.

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [Installation](#installation)
3. [The Combined Workflow](#the-combined-workflow)
4. [Phase 1: Discovery and Planning (GStack)](#phase-1-discovery-and-planning-gstack)
5. [Phase 2: Implementation (Superpowers)](#phase-2-implementation-superpowers)
6. [Phase 3: Review and QA (GStack)](#phase-3-review-and-qa-gstack)
7. [Phase 4: Ship and Monitor (GStack)](#phase-4-ship-and-monitor-gstack)
8. [Project CLAUDE.md Setup](#project-claudemd-setup)
9. [Session Management](#session-management)
10. [Common Scenarios](#common-scenarios)
11. [Troubleshooting](#troubleshooting)
12. [Anti-Patterns](#anti-patterns)
13. [Quick Reference](#quick-reference)

---

## Philosophy

Each framework owns a distinct part of the development lifecycle:

- **GStack** owns everything **before and after code** — product thinking, architecture review, QA, security, shipping
- **Superpowers** owns the **implementation loop** — TDD, coding, debugging, code review

They never overlap. GStack focuses on *what roles review the work*. Superpowers focuses on *how code gets written*.

---

## Installation

### Superpowers

Superpowers is a Claude Code plugin installed via the official marketplace:

```bash
# In Claude Code, run these slash commands:
/plugin marketplace add claude-plugins-official
/plugin install superpowers
```

After installation, restart Claude Code. Superpowers injects itself automatically via a SessionStart hook — you don't need to invoke it manually. It will activate whenever a relevant skill applies.

### GStack

GStack is installed as native Claude Code skills:

```bash
# Clone and setup
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

The setup script:
1. Installs npm dependencies and builds the Playwright browser daemon (~58MB)
2. Creates symlinks in `~/.claude/skills/` for each GStack skill (office-hours, review, qa, etc.)
3. Generates SKILL.md files for all skills

**Prerequisites:** [Bun](https://bun.sh) must be installed (`brew install oven-sh/bun/bun`).

**First-run prompts:** The first time you use a GStack skill in a new session, it will ask about (in this order):
1. **Boil the Lake principle** — GStack's completeness philosophy (one-time intro)
2. **Telemetry** — anonymous usage data (one-time, can be changed later)
3. **Proactive mode** — whether GStack auto-suggests skills based on context
4. **Cross-project learnings** — whether to search learnings from other projects on this machine (one-time)
5. **CLAUDE.md routing** — whether to add routing rules to your project (skipped if `## Skill routing` header exists)

These are sequential interactive prompts. Expect 4-5 questions before the actual skill work begins. They only happen once per machine/project.

**Note:** `/office-hours` ends with a YC application pitch from Garry Tan. This is baked into the skill and happens every time. It's not a bug — GStack is built by the president of Y Combinator.

### Verify Installation

**You must restart Claude Code** after running setup for skills to be discovered.

After restarting:

```
# Superpowers: ask Claude to brainstorm something — it should 
# automatically invoke the brainstorming skill and ask Socratic questions
"Let's brainstorm a REST API design"

# GStack: run a slash command directly
/office-hours
```

If GStack skills don't appear, verify the symlinks exist: `ls ~/.claude/skills/office-hours/SKILL.md`
If Superpowers skills don't trigger, check: `/plugin list`

### Token Overhead Warning

Both frameworks add system prompt overhead (estimated 50-70K tokens combined before you type anything). This reduces your effective context window. On Claude's standard 200K context, you'll have roughly 130-150K tokens available for actual work. This is manageable but worth knowing — avoid adding unnecessary content to CLAUDE.md.

**Runtime token cost:** Subagent-Driven Development (SDD) dispatches multiple subagents per task: one implementer + one spec reviewer + one code quality reviewer. For a 5-task plan, expect ~10-15 subagent invocations. For small projects (< 5 tasks), consider `/superpowers:executing-plans` (inline) instead — it's faster and cheaper while still following TDD.

**Model selection tip:** SDD supports dispatching implementer subagents with cheaper/faster models (e.g., Haiku) for mechanical tasks. Reserve more capable models for complex integration tasks or reviews. This can significantly reduce cost.

---

## The Combined Workflow

```
┌─────────────────────────────────────────────────┐
│  PHASE 1: DISCOVERY & PLANNING (GStack)         │
│                                                  │
│  /office-hours    → Product framing              │
│  /plan-ceo-review → Strategic validation         │
│  /plan-eng-review → Architecture lock            │
│  /plan-design-review → Design validation         │
│                                                  │
│  OR: /autoplan    → Chains all three reviews     │
├─────────────────────────────────────────────────┤
│  PHASE 2: IMPLEMENTATION (Superpowers)           │
│                                                  │
│  /superpowers:brainstorming   → Refine technical approach    │
│  /superpowers:writing-plans   → Break into TDD tasks         │
│  /superpowers:subagent-driven-development → Execute w/ TDD   │
│  /superpowers:systematic-debugging → Fix issues              │
│                                                  │
├─────────────────────────────────────────────────┤
│  PHASE 3: REVIEW & QA (GStack)                   │
│                                                  │
│  /review          → Pre-landing code review      │
│  /qa <url>        → Browser-based testing        │
│  /cso             → Security audit               │
│  /design-review   → Visual audit                 │
│                                                  │
├─────────────────────────────────────────────────┤
│  PHASE 4: SHIP & MONITOR (GStack)                │
│                                                  │
│  /ship            → Tests, coverage, PR          │
│  /canary          → Post-deploy monitoring       │
│  /retro           → Sprint retrospective         │
│  /document-release → Update docs                 │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Phase 1: Discovery and Planning (GStack)

### Step 1: Product Framing

Start every new feature or project with `/office-hours`.

```
/office-hours

I want to build a notification system that supports email, 
push, and in-app notifications with user preferences.
```

GStack's YC Partner role will ask 6 forcing questions to reframe your idea. This produces a design doc saved to `~/.gstack/projects/`.

**When to skip:** Bug fixes, small refactors, or tasks where the scope is already crystal clear. Jump directly to Phase 2.

### Step 2: Strategic Review

```
/plan-ceo-review
```

Reviews the design doc from Step 1. Operates in one of four modes:
- **Expansion** — Add capabilities
- **Selective Expansion** — Add specific things
- **Hold Scope** — Validate as-is
- **Reduction** — Cut scope

### Step 3: Architecture Lock

```
/plan-eng-review
```

The Engineering Manager role produces:
- ASCII architecture diagrams
- Data flow maps
- State machines
- Failure mode analysis
- Test matrices

This is your architectural contract. Implementation in Phase 2 must follow it.

### Step 4: Design Validation (Optional)

```
/plan-design-review
```

Rates design dimensions 0-10. Includes AI slop detection.

### Shortcut: Autoplan

```
/autoplan
```

Chains CEO review → Design review → Eng review automatically. Use this when you want all three without manual sequencing.

### Transition to Phase 2

After planning is complete, you have architectural decisions, a design doc, and clear scope. Now hand off to Superpowers for implementation.

**Important — Carrying Context Across the `/clear` Boundary:**

When you `/clear` before Phase 2, all conversation context is lost. You must manually bridge the gap:

1. **Note the output file paths** from GStack planning. Key artifacts:
   - Design doc: `~/.gstack/projects/<project>/` (from `/office-hours`)
   - Architecture decisions from `/plan-eng-review` are output in the conversation
2. **Save key decisions** before clearing. Either:
   - Ask GStack to write a summary to a project file (e.g., `docs/architecture-decisions.md`)
   - Copy the architecture diagram and key constraints yourself
3. **Reference the artifacts** when starting Phase 2:

```
/clear

/superpowers:brainstorming

I need to implement the notification service. Key architecture 
decisions from our planning phase are documented in 
docs/architecture-decisions.md — please read that first.
```

Without this step, Superpowers will brainstorm from scratch and may contradict GStack's architectural decisions.

---

## Phase 2: Implementation (Superpowers)

### Step 1: Technical Brainstorming

```
/superpowers:brainstorming
```

Superpowers asks one question at a time to refine the technical approach. Reference the architecture from Phase 1:

```
/superpowers:brainstorming

Based on the architecture review from /plan-eng-review, I need to 
implement the notification service. The eng review specified a 
queue-based architecture with separate handlers per channel.
```

This produces a spec in `docs/superpowers/specs/`.

**Fast-tracking when Phase 1 design is detailed:** Superpowers' brainstorming skill wants to run its full process (explore, question, propose approaches, write spec) even when GStack already produced an approved design doc. If your Phase 1 design doc already has file structure, interfaces, and test strategy, tell brainstorming to "adopt the design as-is" when it asks about approaches. This skips redundant questioning and writes the Superpowers spec directly from the GStack design.

### Step 2: Create Implementation Plan

```
/superpowers:writing-plans
```

Breaks the spec into bite-sized tasks (2-5 minutes each). Each task includes:
- Exact file paths
- Complete code blocks
- TDD steps (write test → verify fail → implement → verify pass)
- Verification commands

Plan saved to `docs/superpowers/plans/`.

### Step 3: Execute with TDD

```
/superpowers:subagent-driven-development
```

This is where the actual coding happens. For each task:

1. A **fresh subagent** is spawned with clean context
2. The subagent writes a **failing test first** (RED)
3. Runs the test to **verify it fails**
4. Writes **minimal code** to pass (GREEN)
5. Runs the test to **verify it passes**
6. **Refactors** if needed
7. **Commits** the work
8. A **spec-reviewer subagent** verifies the implementation matches the spec
9. A **code-quality-reviewer subagent** checks code quality

The orchestrator tracks progress and handles escalations.

### Alternative: Inline Execution

```
/superpowers:executing-plans
```

Runs tasks inline with human checkpoints instead of subagents. Use this for smaller plans or when you want more control.

### Debugging

When something breaks during implementation:

```
/superpowers:systematic-debugging
```

Superpowers' 4-phase root cause process:
1. Observe — gather evidence
2. Hypothesize — form theories
3. Test — validate one theory at a time
4. Fix — only after root cause is confirmed

**Iron Law:** No fixes allowed before Phase 1 completes.

### Parallel Work

For independent tasks (e.g., three unrelated test files failing):

```
/superpowers:dispatching-parallel-agents
```

Spins up concurrent subagents for truly independent problems.

### Git Worktrees

For feature isolation:

```
/superpowers:using-git-worktrees
```

Creates an isolated worktree on a new branch. Automatically detects project setup (npm install, etc.).

### Transition to Phase 3

After all tasks are complete and tests pass, hand back to GStack for review and QA.

**Important — Context Bridge to Phase 3:**

Before clearing, note what was implemented. GStack's `/review` will read the git diff automatically, but providing context helps:

```
/clear

/review

Just completed the notification service implementation across 
Phase 2. All tests pass. Key changes: new NotificationService 
class, queue handlers for email/push/in-app, user preference 
model. Please review the diff against main.
```

---

## Phase 3: Review and QA (GStack)

### Step 1: Code Review

```
/review
```

GStack's Staff Engineer role performs a pre-landing review:
- SQL safety analysis
- LLM trust boundary checks
- Conditional side effect detection
- **Scope drift detection** — compares the diff against the original plan
- Plan completion audit

Auto-fixes obvious issues, flags the rest.

**Prerequisite:** `/review` diffs the current branch against the base branch (usually `main` via remote). It requires:
- A **feature branch** (not `main` itself)
- A **remote** configured (`origin`) so it can `git fetch` and diff

If you're working directly on `main` with no remote (e.g., a local test project), `/review` will say "nothing to review." For testing purposes, create a feature branch first: `git checkout -b feature/my-feature` before running `/review`.

**Important:** If `/review` makes auto-fixes to your code, re-run your test suite before proceeding. GStack's auto-fixes don't go through Superpowers' TDD cycle, so they could introduce regressions:

```bash
# After /review auto-fixes, always verify
npm test  # or your project's test command
```

### Step 2: Browser-Based QA

```
/qa https://localhost:3000
```

**Note:** The first `/qa` call in a session takes ~3 seconds to start the Playwright browser daemon. Subsequent calls are fast (~100-200ms). This is normal — the browser persists cookies, localStorage, and tabs across calls and shuts down after 30 minutes idle.

GStack's QA Lead opens a real browser (Playwright) and:
1. Navigates to your app
2. Takes accessibility tree snapshots
3. Clicks through user flows
4. Finds bugs
5. Fixes them in source code with atomic commits
6. Generates regression tests for every fix
7. Re-verifies in the browser

For report-only mode (no code changes):

```
/qa-only https://localhost:3000
```

### Step 3: Security Audit

```
/cso
```

Chief Security Officer role runs:
- OWASP Top 10 analysis
- STRIDE threat modeling
- Infrastructure-first security audit including secrets archaeology, dependency supply chain, and CI/CD pipeline security
- LLM/AI security and skill supply chain scanning
- 8/10+ confidence gate (only reports high-confidence findings)

### Step 4: Visual Audit (Optional)

```
/design-review
```

Designer's eye QA with before/after screenshots and atomic commits for each fix found.

---

## Phase 4: Ship and Monitor (GStack)

### Prerequisites

- Code must be on a **feature branch** (not main/master). `/ship` will abort if you're on the base branch.
- The feature branch must have a **remote** (`git push -u origin <branch>` first).
- GitHub CLI (`gh`) must be authenticated for PR creation.

### Step 1: Ship

```
/ship
```

The Release Engineer role:
1. Detects platform (GitHub/GitLab) and base branch automatically
2. Shows Review Readiness Dashboard (see below)
3. Syncs with main branch (fetch + merge)
4. Detects test framework and runs full test suite
5. Runs test coverage audit (traces code paths, generates coverage diagram)
6. Checks plan completion (if plan file exists in `~/.gstack/projects/`)
7. Runs pre-landing code review with confidence-scored findings
8. Dispatches specialist reviewers for large diffs (security, performance, etc.)
9. Runs adversarial review (Claude subagent + Codex if available)
10. Creates VERSION file and CHANGELOG.md (auto-decides bump level)
11. Commits in bisectable chunks
12. Pushes and creates PR with structured body
13. Auto-invokes `/document-release` to sync docs

**What to expect:** `/ship` is fully automated and non-interactive for most cases. It only stops for merge conflicts, test failures, MINOR/MAJOR version bumps, or review findings that need judgment. For a clean branch, it runs straight through and outputs the PR URL.

**VERSION format:** 4-digit `MAJOR.MINOR.PATCH.MICRO`. Ship auto-picks MICRO (< 50 lines) or PATCH (50+ lines). MINOR and MAJOR require confirmation.

**Note:** If no VERSION or CHANGELOG exists, `/ship` creates them. First ship on a project will create `VERSION` starting at whatever is appropriate and `CHANGELOG.md` with the initial entry.

**Review Readiness Dashboard:** Before running its own review, `/ship` shows which GStack reviews have already been completed for this branch:

| Status | Meaning |
|--------|---------|
| **CLEARED** | Review was run and passed — `/ship` trusts the result and skips re-running it |
| **NOT CLEARED** | Review was not run — `/ship` runs its own lighter version inline |

The dashboard checks for: code review (`/review`), QA (`/qa`), security (`/cso`), and design review (`/design-review`). You don't need all of them — `/ship` adapts based on what's available. Running `/review` and `/cso` before `/ship` gives the most thorough pipeline.

### Step 2: Deploy and Verify

```
/land-and-deploy
```

Merges PR, waits for CI, verifies production.

### Step 3: Post-Deploy Monitoring

```
/canary
```

SRE role monitors the deployment for issues.

### Step 4: Documentation

```
/document-release
```

Technical Writer role auto-updates all project docs to match what shipped.

### Step 5: Retrospective

```
/retro
```

Engineering Manager role runs a weekly retrospective with per-person breakdowns and shipping streaks. Use `/retro global` to span all projects.

---

## Project CLAUDE.md Setup

**This is critical.** Create a `CLAUDE.md` file in your project root with the following routing rules. Without this, Claude will not consistently choose the right framework for each phase.

Create the file at: `<your-project>/CLAUDE.md`

**Budget warning:** CLAUDE.md compliance drops after ~150-200 total instructions. The routing rules below are ~40 lines. If your project already has a large CLAUDE.md, keep the total under 150 lines. Prioritize routing rules and project conventions — cut verbose descriptions first.

**GStack routing conflict:** GStack checks for a `## Skill routing` section in CLAUDE.md. The template below uses this exact header to prevent GStack from prompting you to add its own routing rules. This saves you one first-run prompt per project.

```markdown
# Development Workflow: Superpowers + GStack

## Skill routing

This project uses two complementary frameworks. Each owns a distinct phase:

### GStack — Planning, Review, QA, and Shipping
Use GStack skills for all non-coding phases:
- Product discovery: `/office-hours`, `/plan-ceo-review`
- Architecture: `/plan-eng-review`, `/plan-design-review`
- Combined planning: `/autoplan`
- Code review: `/review`
- QA testing: `/qa <url>`, `/qa-only <url>`
- Security: `/cso`
- Visual audit: `/design-review`
- Shipping: `/ship`, `/land-and-deploy`, `/canary`
- Docs: `/document-release`
- Retro: `/retro`

### Superpowers — Implementation
Use Superpowers skills for all coding work:
- Technical brainstorming: `/superpowers:brainstorming`
- Planning implementation: `/superpowers:writing-plans`
- Execution with TDD: `/superpowers:subagent-driven-development`
- Inline execution: `/superpowers:executing-plans`
- Debugging: `/superpowers:systematic-debugging`
- Parallel tasks: `/superpowers:dispatching-parallel-agents`
- Feature branches: `/superpowers:using-git-worktrees`
- Branch completion: `/superpowers:finishing-a-development-branch`

### Routing Logic
- New feature or project idea → Start with `/office-hours` (GStack)
- "Build this", "implement", "code this" → Start with `/superpowers:brainstorming` (Superpowers)
- Bug fix → `/superpowers:systematic-debugging` (Superpowers)
- "Review my code", "check the diff" → `/review` (GStack)
- "Test this", "find bugs" → `/qa` (GStack)
- "Is this secure?" → `/cso` (GStack)
- "Ship it", "create PR" → `/ship` (GStack)
- Small/trivial changes → No framework needed, just do it

### Rules
- Never run GStack and Superpowers skills in the same phase
- Never nest subagents from different frameworks
- Consider `/clear` when transitioning between frameworks
- Superpowers specs go in `docs/superpowers/`
- GStack state lives in `~/.gstack/projects/`
- When in doubt, ask which framework to use
```

### Adapting to Your Project

Add project-specific sections below the routing rules:

```markdown
## Project-Specific

### Tech Stack
- Frontend: Next.js 15 + TypeScript
- Backend: Node.js + Prisma
- Testing: Vitest + Playwright

### QA URL
Default QA target: `http://localhost:3000`

### Conventions
- [Your existing coding conventions here]
```

---

## Session Management

### When to `/clear`

Clear your session at these transition points to keep context fresh:

| Transition | Action |
|-----------|--------|
| Phase 1 → Phase 2 | `/clear` for large projects, optional for small (< 5 tasks) |
| Phase 2 → Phase 3 | `/clear` for long implementation sessions, optional for short ones |
| Phase 3 → Phase 4 | Optional — usually fine to continue |
| Between features | Always `/clear` |

**When to skip `/clear`:** For small projects where the full workflow fits in one session (< 5 tasks, < 30 minutes), skipping `/clear` between phases works fine and avoids the overhead of context bridging. The main risk of not clearing is context degradation in long sessions — if Claude starts making repeated mistakes or forgetting decisions, that's a sign to `/clear`.

### GStack Upgrade Checks

Every GStack skill preamble checks for available upgrades. If one is found, it will prompt you with options (upgrade now, snooze, etc.) before the skill runs. This can interrupt workflow if you're in the middle of a `/ship` or `/review` run. If you want uninterrupted flow, upgrade first: `cd ~/.claude/skills/gstack && git pull && ./setup`.

### GStack Preamble Output

Every GStack skill prints a preamble block at the start. Here's what the fields mean:

| Field | Meaning |
|-------|---------|
| `BRANCH` | Current git branch name |
| `PROACTIVE` | Whether GStack will auto-suggest skills based on context (`true`/`false`) |
| `TEL_PROMPTED` | Whether telemetry consent has been asked (`true` = won't ask again) |
| `LEARNINGS` | Whether cross-project learnings search is enabled |
| `UPGRADE` | Shows available upgrade version, or `current` if up to date |

This output is informational — you don't need to act on it. It confirms GStack's configuration state for the current session.

### Long Implementation Sessions

If a Superpowers implementation session runs long:
- The SessionStart hook re-injects Superpowers instructions on `/clear` or compact
- Subagents always get fresh context regardless
- Watch for signs of context degradation: repeated mistakes, forgetting earlier decisions

### Pausing Work

If you need to stop mid-implementation:
1. Let the current subagent task complete
2. The plan in `docs/superpowers/plans/` tracks what's done
3. On resume, run `/superpowers:subagent-driven-development` — it reads the plan and continues

---

## Common Scenarios

### New Feature (Full Workflow)

```
/office-hours          → Frame the idea
/plan-ceo-review       → Validate scope
/plan-eng-review       → Lock architecture
  → Save key decisions to docs/architecture-decisions.md
/clear
/superpowers:brainstorming         → Reference architecture-decisions.md
/superpowers:writing-plans         → Break into TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/review                → Code review (re-run tests if auto-fixes)
/qa http://localhost:3000 → Browser testing
/cso                   → Security check
/ship                  → PR and deploy
```

### Bug Fix

```
/superpowers:systematic-debugging  → Find root cause (Superpowers)
# Fix is implemented with TDD as part of debugging
/clear
/review                → Verify the fix (GStack)
/ship                  → Deploy
```

### Small Feature (Skip Planning)

```
/superpowers:brainstorming         → Quick technical refinement
/superpowers:writing-plans         → TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/review                → Code review
/ship                  → Deploy
```

### Refactoring

```
/superpowers:brainstorming         → Define refactoring scope and goals
/superpowers:writing-plans         → Break into safe, tested steps
/superpowers:subagent-driven-development → Execute with TDD
/clear
/review                → Verify no regressions
```

### Exploring a Vague Idea

```
/office-hours          → Product framing
/plan-ceo-review       → Is this worth building?
# Stop here if the answer is no
/plan-design-review    → Design validation
/plan-eng-review       → Technical feasibility
```

### Security-Critical Feature

```
/office-hours          → Frame it
/plan-eng-review       → Architecture with security focus
/clear
/superpowers:brainstorming         → Technical approach
/superpowers:writing-plans         → TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/cso                   → Security audit FIRST
/review                → Code review
/qa http://localhost:3000 → Functional testing
/ship                  → Deploy
/canary                → Monitor closely
```

---

## Troubleshooting

### GStack skill doesn't trigger

**Symptom:** You type `/office-hours` and Claude says it doesn't recognize the command.

**Fix:** Verify symlinks exist: `ls ~/.claude/skills/office-hours/SKILL.md`. If missing, re-run `cd ~/.claude/skills/gstack && ./setup`. You must restart Claude Code after setup.

### Superpowers skill doesn't trigger

**Symptom:** You say "let's brainstorm" but Superpowers doesn't activate.

**Fix:** Check `/plugin list` — Superpowers should be listed. If not, reinstall: `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`. Restart Claude Code.

### Wrong framework responds

**Symptom:** You ask to implement something and GStack's `/investigate` activates instead of Superpowers' debugging.

**Fix:** Add the `## Skill routing` section to your project's CLAUDE.md (see [Project CLAUDE.md Setup](#project-claudemd-setup)). Without routing rules, Claude guesses based on context and often picks wrong.

### `/review` says "nothing to review"

**Symptom:** You have code changes but `/review` finds nothing.

**Fix:** You're likely on `main` with no remote. `/review` diffs against the remote base branch. Create a feature branch (`git checkout -b feature/name`) and push it (`git push -u origin feature/name`).

### `/ship` fails at PR creation

**Symptom:** Tests pass but PR creation fails.

**Fix:** Ensure: (1) you're on a feature branch, not main; (2) the branch is pushed to remote with `-u`; (3) `gh auth status` shows you're authenticated.

### Subagent runs out of context

**Symptom:** SDD subagent produces incomplete code or misses requirements.

**Fix:** The task in `docs/superpowers/plans/` may be too large. Edit the plan to split it into smaller tasks (2-5 minutes each). Re-run `/superpowers:subagent-driven-development`.

---

## Anti-Patterns

### 1. Mixing Frameworks in One Phase
**Wrong:** Running `/superpowers:brainstorming` then `/plan-ceo-review` then `/superpowers:writing-plans`.
**Right:** Complete all GStack planning, then transition to Superpowers for implementation.

### 2. Skipping TDD During Implementation
**Wrong:** Using GStack's `/review` to catch bugs after writing code without tests.
**Right:** Let Superpowers enforce TDD. GStack review catches what tests missed.

### 3. Mixing Debugging Tools
**Wrong:** Using GStack's `/investigate` for bugs found during Phase 2 implementation.
**Right:** During Phase 2, use Superpowers' `/superpowers:systematic-debugging` — it follows TDD (writes a failing test reproducing the bug, then fixes it). Use GStack's `/investigate` for bugs discovered outside the implementation flow (production issues, bugs found during Phase 3 QA, or bugs reported by users). Both are valid debugging tools, but they serve different contexts.

### 4. Nesting Subagents
**Wrong:** A Superpowers subagent spawning a GStack skill.
**Right:** Each framework's subagents stay within their own framework.

### 5. Skipping `/clear` Between Phases
**Wrong:** Going straight from a long implementation session into `/review`.
**Right:** `/clear` first, then `/review` with fresh context.

### 6. Over-Engineering Small Changes
**Wrong:** Running the full 4-phase workflow for a one-line config change.
**Right:** Just make the change. Use the frameworks when they add value.

### 7. Confusing the Two Code Reviews
**Wrong:** Running both `/superpowers:requesting-code-review` (Superpowers) and `/review` (GStack) at the same point.
**Right:** They serve different purposes:
- **Superpowers' code review** (via SDD) runs automatically during Phase 2 after each task — checks spec compliance and code quality within the implementation context.
- **GStack's `/review`** runs in Phase 3 — a pre-merge review that checks the entire diff for SQL safety, scope drift, trust boundaries, and auto-fixes obvious issues.
They are complementary layers, not alternatives. Don't skip either.

### 8. Running All GStack Reviews Every Time
**Wrong:** Always running CEO, design, eng, security, and QA reviews.
**Right:** Choose reviews based on what changed. A backend API change doesn't need `/design-review`. A CSS fix doesn't need `/cso`.

### 9. Shipping from Main Branch
**Wrong:** Doing all implementation on `main`, then running `/ship`.
**Right:** Create a feature branch before Phase 2. `/ship` requires a feature branch to create a PR against the base branch. If you already committed to main, create a branch retroactively: `git checkout -b feature/name` and push it.

### 10. Running `/ship` Without a Remote
**Wrong:** Running `/ship` on a local-only branch with no upstream.
**Right:** Push the branch first (`git push -u origin <branch>`), then run `/ship`. The PR creation step needs a remote to target.

---

## Quick Reference

### GStack Commands (Planning, Review, QA, Ship)

| Command | When to Use |
|---------|------------|
| `/office-hours` | Starting something new |
| `/plan-ceo-review` | Validating scope and strategy |
| `/plan-eng-review` | Locking architecture |
| `/plan-design-review` | Validating design |
| `/plan-devex-review` | Developer experience planning |
| `/autoplan` | All three reviews chained |
| `/review` | Pre-merge code review |
| `/qa <url>` | Browser-based testing |
| `/qa-only <url>` | Testing without fixes |
| `/cso` | Security audit |
| `/design-review` | Visual audit |
| `/design-consultation` | Create design system |
| `/design-html` | Generate production HTML/CSS |
| `/design-shotgun` | Explore design variants |
| `/devex-review` | Live developer experience audit |
| `/investigate` | Production bug root cause |
| `/ship` | Create PR and deploy |
| `/land-and-deploy` | Merge and verify |
| `/canary` | Post-deploy monitoring |
| `/document-release` | Update docs |
| `/retro` | Sprint retrospective |
| `/learn` | Save/search project learnings |
| `/health` | Code quality dashboard |
| `/benchmark` | Performance regression detection |
| `/browse` | Fast headless browser for testing |
| `/checkpoint` | Save/resume working state |
| `/codex` | OpenAI Codex second opinion |
| `/careful` | Enable destructive command warnings |
| `/freeze` | Lock edits to one directory |
| `/open-gstack-browser` | Browser utilities |
| `/setup-browser-cookies` | Browser cookie management |
| `/setup-deploy` | Deployment configuration |
| `/gstack-upgrade` | Upgrade GStack installation |

### Superpowers Commands (Implementation)

| Command | When to Use |
|---------|------------|
| `/superpowers:brainstorming` | Refining technical approach |
| `/superpowers:writing-plans` | Creating TDD task breakdown |
| `/superpowers:subagent-driven-development` | Executing with subagents + TDD |
| `/superpowers:executing-plans` | Inline execution with checkpoints |
| `/superpowers:dispatching-parallel-agents` | Independent parallel tasks |
| `/superpowers:systematic-debugging` | Finding root cause of bugs |
| `/superpowers:using-git-worktrees` | Feature branch isolation |
| `/superpowers:finishing-a-development-branch` | Merge/PR/discard decisions |
| `/superpowers:test-driven-development` | Manual TDD enforcement |
| `/superpowers:verification-before-completion` | Verify before claiming done |
| `/superpowers:requesting-code-review` | Dispatch review subagent (during Phase 2 only) |

### Decision Tree

```
Is this a new idea or feature?
  YES → /office-hours (GStack)
  NO  →
    Is this a bug?
      YES → /superpowers:systematic-debugging (Superpowers)
      NO  →
        Is the scope already clear?
          YES → /superpowers:brainstorming (Superpowers)
          NO  → /office-hours (GStack)

Ready to code?
  → /superpowers:writing-plans → /superpowers:subagent-driven-development (Superpowers)

Code is written?
  → /clear → /review (GStack)

Review passed?
  Needs QA?   → /qa (GStack)
  Needs security? → /cso (GStack)
  Ready to ship?  → /ship (GStack)
```
