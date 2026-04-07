# Superpowers + GStack: Combined Development Manual

A practical guide to using Superpowers and GStack together for AI-assisted development with Claude Code.

---

## Table of Contents

1. [Kickstart](#kickstart)
2. [Philosophy](#philosophy)
3. [Installation](#installation)
4. [The Combined Workflow](#the-combined-workflow)
5. [Phase 1: Discovery and Planning (GStack)](#phase-1-discovery-and-planning-gstack)
6. [Phase 2: Implementation (Superpowers)](#phase-2-implementation-superpowers)
7. [Phase 3: Review and QA (GStack)](#phase-3-review-and-qa-gstack)
8. [Phase 4: Ship and Monitor (GStack)](#phase-4-ship-and-monitor-gstack)
9. [Project CLAUDE.md Setup](#project-claudemd-setup)
10. [Session Management](#session-management)
11. [Common Scenarios](#common-scenarios)
12. [Quick Reference](#quick-reference)

For troubleshooting, anti-patterns, and skill internals, see the [Appendix](appendix-reference.md).

---

## Kickstart

Three steps to get going with a new project:

> **Important:** Always start Claude Code from your project directory (`cd my-project && claude`). GStack and the routing skills detect project context from the working directory. Running from a different directory causes wrong project detection, misplaced design docs, and incorrect CLAUDE.md checks.

### 1. Install the frameworks (once per machine)

```bash
# GStack
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

Then in Claude Code:

```
# Superpowers
/plugin marketplace add claude-plugins-official
/plugin install superpowers

# Routing plugin
/plugin marketplace add kjetilge/kjetil-claude-marketplace
/plugin install superpowers-gstack@kjetil-plugins
```

Restart Claude Code after installation.

### 2. Start working

Open Claude Code from your project directory and follow the path that matches your situation:

**New project** (empty or no CLAUDE.md):

```bash
cd ~/Developer/my-project && claude
```
```
/setup-routing                          → Generates tailored CLAUDE.md with routing rules
# Then:
#   Scope unclear?     → /office-hours
#   Scope clear?       → /superpowers:brainstorming
#   Small project?     → /superpowers:brainstorming (skip Phase 1)
```

**Existing project** (already has CLAUDE.md, code, conventions):

```bash
cd ~/Developer/my-project && claude
```
```
/adapt                                  → Adds routing to existing CLAUDE.md, preserves everything
# Then:
#   New feature?       → /superpowers:brainstorming
#   Bug fix?           → /superpowers:systematic-debugging
#   Code ready?        → /review
#   Ready to ship?     → /ship
```

> **Tip:** `/setup-routing` and `/adapt` are shorthand for `/superpowers-gstack:setup-routing` and `/superpowers-gstack:adapt`. The short form is easier to find in autocomplete.

See [Common Scenarios](#common-scenarios) for full workflow examples.

---

## Philosophy

Each framework owns a distinct part of the development lifecycle:

- **GStack** owns everything **before and after code** — product thinking, architecture review, QA, security, shipping
- **Superpowers** owns the **implementation loop** — TDD, coding, debugging, code review

They never overlap. GStack focuses on *what roles review the work*. Superpowers focuses on *how code gets written*.

---

## Installation

### Superpowers

```bash
# In Claude Code, run these slash commands:
/plugin marketplace add claude-plugins-official
/plugin install superpowers
```

Restart Claude Code after installation. Superpowers activates automatically when a relevant skill applies.

### GStack

```bash
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

**Prerequisites:** [Bun](https://bun.sh) must be installed (`brew install oven-sh/bun/bun`). Restart Claude Code after setup.

GStack will ask 4-5 setup questions on first use (telemetry, proactive mode, etc.). These only happen once. See [Appendix: Installation Details](appendix-reference.md#installation-details) for what to expect.

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

Start every new feature or project with `/office-hours`. GStack asks forcing questions to reframe your idea and produces a design doc saved to `~/.gstack/projects/`.

**When to skip:** Bug fixes, small refactors, tasks where scope is already clear, or small projects (< 5 tasks, buildable in under 30 minutes). For these, jump directly to Phase 2. Office-hours adds ~10 minutes of ceremony that won't pay off for simple work.

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `/office-hours` | Product framing — 6 forcing questions |
| 2 | `/plan-ceo-review` | Strategic scope validation |
| 3 | `/plan-eng-review` | Architecture lock (your contract for Phase 2) |
| 4 | `/plan-design-review` | Design validation (optional) |
| — | `/autoplan` | Chains steps 2-4 automatically |

See [Appendix: Skill Deep Dives](appendix-reference.md#skill-deep-dives) for what each skill produces.

### Transition to Phase 2

When you `/clear` before Phase 2, all conversation context is lost. Bridge the gap:

1. Save key decisions before clearing (ask GStack to write to `docs/architecture-decisions.md`)
2. Reference the artifacts when starting Phase 2:

```
/clear
/superpowers:brainstorming
I need to implement the notification service. Key architecture 
decisions are in docs/architecture-decisions.md — read that first.
```

> **If Phase 1 produced a design doc:** Tell brainstorming to "adopt the design as-is" — this skips redundant questioning about scope and approach that office-hours already answered. Brainstorming will still add technical clarifications (storage, libraries, patterns) but won't re-tread product decisions.
>
> ```
> /superpowers:brainstorming
> Adopt the design as-is from the Phase 1 design doc at
> ~/.gstack/projects/<slug>/design.md — focus on technical 
> implementation details only.
> ```

---

## Phase 2: Implementation (Superpowers)

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `/superpowers:brainstorming` | Refine technical approach → spec in `docs/superpowers/specs/` |
| 2 | `/superpowers:writing-plans` | Break spec into TDD tasks → plan in `docs/superpowers/plans/` |
| 3 | `/superpowers:subagent-driven-development` | Execute each task with TDD (Red → Green → Refactor) |
| alt | `/superpowers:executing-plans` | Inline execution with checkpoints (for smaller plans) |

**Debugging:** When something breaks, use `/superpowers:systematic-debugging` — it enforces the root cause → test → fix cycle.

**Parallel work:** For independent tasks, `/superpowers:dispatching-parallel-agents` spins up concurrent subagents.

**Feature isolation:** `/superpowers:using-git-worktrees` creates an isolated worktree on a new branch.

See [Appendix: Skill Deep Dives](appendix-reference.md#skill-deep-dives) for internal process details.

### Transition to Phase 3

```
/clear
/review
Just completed the notification service. All tests pass. 
Key changes: NotificationService class, queue handlers, preference model.
```

---

## Phase 3: Review and QA (GStack)

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `/review` | Pre-merge code review (requires feature branch + remote) |
| 2 | `/qa <url>` | Browser-based testing with Playwright |
| — | `/qa-only <url>` | Same, but report-only (no auto-fixes) |
| 3 | `/cso` | Security audit (OWASP, STRIDE) |
| 4 | `/design-review` | 80-item visual audit (optional) |
| 5 | `/investigate` | Root cause for bugs found in QA/production (not Phase 2) |

**Review feedback loop:** If `/review` flags issues needing code changes, use `/superpowers:receiving-code-review` to structure the feedback into TDD tasks, implement fixes, then re-run `/review`.

**Auto-fix caution:** If `/review` makes auto-fixes, re-run your tests before proceeding.

See [Appendix: Skill Deep Dives](appendix-reference.md#skill-deep-dives) for what each skill checks.

---

## Phase 4: Ship and Monitor (GStack)

**Prerequisites:** Feature branch with remote. GitHub CLI (`gh`) authenticated.

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `/ship` | Runs tests, creates PR, auto-versions (fully automated) |
| 2 | `/land-and-deploy` | Merges PR, waits for CI, verifies production |
| 3 | `/canary` | Post-deploy monitoring |
| 4 | `/document-release` | Auto-updates project docs |
| 5 | `/retro` | Sprint retrospective |

**Utility skills** (any phase): `/learn`, `/health`, `/careful`, `/freeze`, `/browse`

See [Appendix: `/ship` Full Process](appendix-reference.md#ship--full-process) for the 13-step internal flow.

---

## Project CLAUDE.md Setup

**This is critical.** Without routing rules in your project's CLAUDE.md, Claude will not consistently choose the right framework.

**Recommended:** Use `/superpowers-gstack:setup-routing` (new project) or `/superpowers-gstack:adapt` (existing project). See [Kickstart](#kickstart).

**Manual alternative:** Create `<your-project>/CLAUDE.md` with the template below. Keep total CLAUDE.md under 150 lines — compliance drops beyond that.

**GStack note:** The `## Skill routing` header prevents GStack from prompting you to add its own routing rules.

```markdown
# [Project Name]

## Skill routing

This project uses Superpowers + GStack. Each owns a distinct phase:

### GStack — Planning, Review, QA, and Shipping

**Planning:**
- `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/autoplan`

**Review & QA:**
- `/review`, `/qa <url>`, `/qa-only <url>`, `/cso`, `/design-review`, `/investigate`

**Ship & Monitor:**
- `/ship`, `/land-and-deploy`, `/canary`, `/document-release`, `/retro`

**Utility:**
- `/learn`, `/health`, `/careful`, `/freeze`, `/browse`

### Superpowers — Implementation
- `/superpowers:brainstorming` — technical approach
- `/superpowers:writing-plans` — TDD task breakdown
- `/superpowers:subagent-driven-development` — execute with subagents + TDD
- `/superpowers:executing-plans` — inline execution with checkpoints
- `/superpowers:systematic-debugging` — root cause analysis (Phase 2 bugs)
- `/superpowers:dispatching-parallel-agents` — independent parallel tasks
- `/superpowers:using-git-worktrees` — feature branch isolation
- `/superpowers:finishing-a-development-branch` — merge/PR/discard
- `/superpowers:test-driven-development` — manual TDD enforcement
- `/superpowers:verification-before-completion` — verify before claiming done
- `/superpowers:requesting-code-review` — dispatch review subagent
- `/superpowers:receiving-code-review` — handle review feedback before implementing changes
- `/superpowers:writing-skills` — for Claude Code plugin/skill projects only

### Routing Logic
- New feature or project idea → `/office-hours` (GStack)
- Ready to build → `/superpowers:brainstorming` (Superpowers)
- Bug during implementation → `/superpowers:systematic-debugging` (Superpowers)
- Bug found in QA or production → `/investigate` (GStack)
- Code complete → `/review` (GStack)
- Review feedback needs code changes → `/superpowers:receiving-code-review` (Superpowers)
- Has browser UI → `/qa <url>` (GStack)
- Security-sensitive → `/cso` before `/review` (GStack)
- Ready to ship → `/ship` (GStack)
- Trivial change → No framework needed

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
```

---

## Session Management

### When to `/clear`

| Transition | Action |
|-----------|--------|
| Phase 1 → Phase 2 | `/clear` for large projects, optional for small (< 5 tasks) |
| Phase 2 → Phase 3 | `/clear` for long implementation sessions, optional for short ones |
| Phase 3 → Phase 4 | Optional — usually fine to continue |
| Between features | Always `/clear` |

**When to skip:** For small projects (< 5 tasks, < 30 minutes), skipping `/clear` works fine. If Claude starts making repeated mistakes, that's a sign to `/clear`.

See [Appendix: Session Management Details](appendix-reference.md#session-management-details) for GStack preamble output, upgrade checks, and pausing work.

---

## Common Scenarios

### New Feature (Full Workflow)

```
/office-hours          → Frame the idea
/plan-ceo-review       → Validate scope
/plan-eng-review       → Lock architecture
  → Save key decisions to docs/architecture-decisions.md
/clear
/superpowers:brainstorming         → "Adopt the design as-is" if office-hours produced a design doc
/superpowers:writing-plans         → Break into TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/review                → Code review (re-run tests if auto-fixes)
  # If review feedback needs code changes:
  /superpowers:receiving-code-review → Implement fixes with TDD
  /review                → Re-review after fixes
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

### Tiny Project (CLI Tool, Script, Single-Purpose App)

For projects with fewer than 5 tasks — small CLI tools, scripts, single-file utilities:

```
/superpowers:brainstorming         → 2-3 clarifying questions, adopt quickly
/superpowers:writing-plans         → TDD task breakdown
/superpowers:executing-plans       → Inline execution (no subagents needed)
# Tests passing = spec compliance. Skip per-task reviews.
/review                            → Manual diff review (skip specialists for < 200 LOC)
/ship                              → Create PR
```

**What to skip and why:**
- **Phase 1 entirely** — Office-hours, CEO/eng review add ~10-15 min of ceremony for a project specifiable in one sentence
- **Subagent-driven development** — Use `/superpowers:executing-plans` instead; subagent dispatch overhead isn't worth it for < 5 tasks
- **Per-task SDD reviews** — Passing tests ARE the spec compliance check for simple tasks
- **Review specialists** — For diffs under 200 lines of actual code, run the core `/review` and skip specialist dispatch (security, performance, etc.)
- **`/clear` between phases** — Not needed; context won't overflow for a 30-minute project

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

## Quick Reference

### GStack Commands (Planning, Review, QA, Ship)

| Command | When to Use |
|---------|------------|
| `/office-hours` | Starting something new |
| `/plan-ceo-review` | Validating scope and strategy |
| `/plan-eng-review` | Locking architecture |
| `/plan-design-review` | Validating design |
| `/autoplan` | All three reviews chained |
| `/review` | Pre-merge code review |
| `/qa <url>` | Browser-based testing |
| `/qa-only <url>` | Testing without fixes |
| `/cso` | Security audit |
| `/design-review` | Visual audit |
| `/investigate` | Bug root cause (QA, staging, production) |
| `/ship` | Create PR and deploy |
| `/land-and-deploy` | Merge and verify |
| `/canary` | Post-deploy monitoring |
| `/document-release` | Update docs |
| `/retro` | Sprint retrospective |
| `/learn` | Save/search project learnings |
| `/health` | Code quality dashboard |
| `/careful` | Enable destructive command warnings |
| `/freeze` | Lock edits to one directory |
| `/browse` | Headless browser for ad-hoc testing |

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
| `/superpowers:receiving-code-review` | Handle review feedback before implementing changes |
| `/superpowers:writing-skills` | Claude Code plugin/skill projects only |

### Decision Tree

```
Is this a new idea or feature?
  YES → /office-hours (GStack)
  NO  →
    Is this a bug?
      During implementation (Phase 2)? → /superpowers:systematic-debugging (Superpowers)
      During QA/staging/production?    → /investigate (GStack)
      NO  →
        Is the scope already clear?
          YES → /superpowers:brainstorming (Superpowers)
          NO  → /office-hours (GStack)

Ready to code?
  → /superpowers:writing-plans → /superpowers:subagent-driven-development (Superpowers)

Code is written?
  → /clear → /review (GStack)

Review feedback needs changes?
  → /superpowers:receiving-code-review (Superpowers) → fix → /review again

Review passed?
  Needs QA?   → /qa (GStack)
  Needs security? → /cso (GStack)
  Ready to ship?  → /ship (GStack)
```
