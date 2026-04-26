# Superpowers + GStack: Routing, Context Management & Workflow

> **"Superpowers owns the implementation loop, GStack owns everything before and after it. Context Guard keeps the session clean."**

A Claude Code plugin that integrates [Superpowers](https://github.com/obra/superpowers) and [GStack](https://github.com/garrytan/gstack) into one workflow — with skill routing, automatic context management, and project auto-configuration. Already have an existing project? Run `/adapt` and it analyzes your setup, preserves your CLAUDE.md, and adds routing — so you can jump right in.

**Status: Work in Progress** — Actively developed. Contributions, feedback, and ideas are very welcome. See [Contributing](#contributing).

### What problem does this solve?

If you've installed both Superpowers and GStack, you've probably run into these issues:
- Claude picks the **wrong framework** for the task (GStack's `/investigate` when you wanted Superpowers' debugging)
- **No clear handoff** between planning (GStack) and implementation (Superpowers)
- **Context rot** in long sessions — quality degrades as the context window fills up
- You don't know **which skills to use when**, or which to skip for your project type

This project solves all of that with routing rules, automatic context management, and a structured 4-phase workflow.

## Why Both?

Every comparison article says "use both" but nobody explains how. This project fills that gap:

| Framework | Strengths | Phase |
|-----------|-----------|-------|
| **GStack** (Garry Tan) | Product thinking, architecture review, QA, security, shipping | Planning, Review, Ship |
| **Superpowers** (Jesse Vincent) | TDD, structured coding, debugging, code review | Implementation |

They never overlap. GStack focuses on *what roles review the work*. Superpowers focuses on *how code gets written*.

## What's Included

- **Claude Code Plugin** with four skills:
  - `/setup-routing` — Generates a tailored CLAUDE.md for new projects
  - `/adapt` — Adds routing to existing projects without losing your CLAUDE.md content
  - `/context-guard` — Saves session state, auto-resumes after `/clear` or `/compact`, and proactively suggests context resets when sessions get long
  - `/pitfall-verification` — Final-check skill run after any PRD, spec, plan, or code artifact. Targeted check that typical pitfalls for that artifact type and domain (security, idempotency, contracts, edge cases, LLM output) actually do not apply. Two rounds max.
- **[Appendix](appendix-reference.md)** — Skill internals, troubleshooting, and anti-patterns
- **Automated update pipeline** — GitHub Actions keeps the plugin in sync when upstream frameworks change

> **Tip:** In autocomplete, type `/setup-routing`, `/adapt`, or `/context-guard` — Claude Code matches on the skill name. The full prefixed form (e.g. `/superpowers-gstack:adapt`) also works.

## Kickstart

> *Vibe coding with a flight plan.*
> *Because your AI already has opinions. Might as well make them good.*

### 1. Install the frameworks

```bash
# Superpowers (in Claude Code)
/plugin marketplace add claude-plugins-official
/plugin install superpowers

# GStack
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

### 2. Install this plugin

```
# In Claude Code:
/plugin marketplace add Paretofilm/claude-marketplace
/plugin install superpowers-gstack@paretofilm-plugins
```

Restart Claude Code after installation.

**Important:** Start Claude Code from your project directory before running setup:

```bash
cd ~/Developer/my-project
claude
```

### 3. Set up your project

```
# New project:
/setup-routing

# Existing project:
/adapt
```

This generates a CLAUDE.md with routing rules tailored to your project type, tech stack, and deployment target.

### 4. Start working

| Situation | Start with |
|-----------|-----------|
| New idea, unclear scope | `/office-hours` |
| Scope is clear, ready to build | `/superpowers:brainstorming` |
| Bug fix | `/superpowers:systematic-debugging` |
| Code complete, ready for review | `/review` |
| Ready to ship | `/ship` |
| Long session, save state | `/context-guard` |

## The Workflow

```
┌─────────────────────────────────────────────────┐
│  PHASE 1: DISCOVERY & PLANNING (GStack)         │
│                                                  │
│  /office-hours    → Product framing              │
│  /plan-ceo-review → Strategic validation         │
│  /plan-eng-review → Architecture lock            │
│  /plan-design-review → Design validation         │
│  /autoplan        → Chains all three reviews     │
├─────────────────────────────────────────────────┤
│  PHASE 2: IMPLEMENTATION (Superpowers)           │
│                                                  │
│  /superpowers:brainstorming           → Refine   │
│  /superpowers:writing-plans           → TDD tasks│
│  /superpowers:subagent-driven-development → Build│
│  /superpowers:systematic-debugging    → Fix bugs │
├─────────────────────────────────────────────────┤
│  PHASE 3: REVIEW & QA (GStack)                   │
│                                                  │
│  /review          → Pre-landing code review      │
│  /qa <url>        → Browser-based testing        │
│  /cso             → Security audit               │
│  /design-review   → Visual audit                 │
├─────────────────────────────────────────────────┤
│  PHASE 4: SHIP & MONITOR (GStack)                │
│                                                  │
│  /ship            → Tests, coverage, PR          │
│  /canary          → Post-deploy monitoring       │
│  /retro           → Sprint retrospective         │
│  /document-release → Update docs                 │
└─────────────────────────────────────────────────┘
```

### Phase transitions

Use `/clear` when switching between GStack and Superpowers phases (skip for small projects < 5 tasks). Before clearing after Phase 1, save key decisions:

```
# Save decisions, then clear
/clear
/superpowers:brainstorming
Adopt the design as-is from the Phase 1 design doc — focus on technical details only.
```

If review feedback needs code changes: `/superpowers:receiving-code-review` → fix → `/review` again.

## Context Management

Long sessions degrade Claude's output quality — a problem known as context rot. [GSD](https://github.com/gsd-build/get-shit-done) solves this with a full orchestration layer, but that creates nesting issues when combined with Superpowers' subagent-driven development (three layers of orchestration). This plugin takes a lighter approach:

**How it works:**
1. After `/compact`, Claude asks if you want to activate auto context guard for the session
2. If yes, it keeps `docs/superpowers/handoff.md` updated as a living document — current task, decisions, next step
3. When context gets heavy again, Claude suggests `/clear`
4. After `/clear`, Claude automatically reads the handoff file, presents where you left off, and clears it — no "resume" command needed

**Manual use:** Run `/context-guard` anytime to save state before a `/clear`.

No hooks, no orchestration overhead, no nesting. Just save and restore.

## Common Scenarios

### New Feature (Full Workflow)

```
/office-hours          → Frame the idea
/plan-ceo-review       → Validate scope
/plan-eng-review       → Lock architecture
  → Save key decisions to docs/
/clear
/superpowers:brainstorming         → Adopt design, refine technical approach
/superpowers:writing-plans         → Break into TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/review                → Code review
/qa http://localhost:3000 → Browser testing
/cso                   → Security check
/ship                  → PR and deploy
```

### Bug Fix

```
/superpowers:systematic-debugging  → Find root cause + fix with TDD
/clear
/review                → Verify the fix
/ship                  → Deploy
```

### Small Feature (Skip Planning)

```
/superpowers:brainstorming         → Quick technical refinement
/superpowers:writing-plans         → TDD tasks
/superpowers:subagent-driven-development → Build it
/clear
/review → /ship
```

### Tiny Project (< 5 tasks)

```
/superpowers:brainstorming         → Adopt quickly
/superpowers:writing-plans         → TDD breakdown
/superpowers:executing-plans       → Inline execution (no subagents)
/review → /ship
```

Skip Phase 1, skip `/clear` between phases, skip subagents, skip review specialists for < 200 LOC.

### Security-Critical Feature

```
/office-hours → /plan-eng-review (security focus)
/clear
/superpowers:brainstorming → /superpowers:writing-plans → SDD
/clear
/cso                   → Security audit FIRST
/review → /qa → /ship → /canary
```

## Quick Reference

### Decision Tree

```
New idea or feature?
  YES → /office-hours (GStack)
  NO  →
    Bug?
      During coding?    → /superpowers:systematic-debugging
      During QA/prod?   → /investigate (GStack)
    Scope clear?
      YES → /superpowers:brainstorming
      NO  → /office-hours

Code written?  → /clear → /review
Review feedback needs changes? → /superpowers:receiving-code-review → fix → /review
Review passed? → /qa → /cso → /ship
```

### GStack Commands

| Command | When to Use |
|---------|------------|
| `/office-hours` | Starting something new |
| `/plan-ceo-review` | Validating scope and strategy |
| `/plan-eng-review` | Locking architecture |
| `/plan-design-review` | Validating design |
| `/plan-devex-review` | Validating developer experience |
| `/plan-tune` | Tune plan-skill question preferences (one-time, per-project) |
| `/autoplan` | Chains all three reviews |
| `/review` | Pre-merge code review |
| `/qa <url>` | Browser-based testing |
| `/cso` | Security audit |
| `/design-review` | Visual audit |
| `/design-consultation` | Design system from scratch |
| `/design-shotgun` | Generate multiple design variants |
| `/design-html` | Finalize design as production HTML/CSS |
| `/devex-review` | Live developer experience audit |
| `/investigate` | Bug root cause (QA/production) |
| `/ship` | Create PR and deploy |
| `/land-and-deploy` | Merge and verify |
| `/canary` | Post-deploy monitoring |
| `/landing-report` | Read-only PR queue + sibling-workspace dashboard |
| `/setup-deploy` | Configure deploy platform (one-time) |
| `/document-release` | Update docs |
| `/retro` | Sprint retrospective |
| `/health` | Code quality dashboard |
| `/context-save` | Save progress, save state |
| `/context-restore` | Resume where left off |
| `/context-guard` | Save session state before /clear |
| `/careful` | Destructive command warnings |
| `/freeze` | Restrict edits to one directory |
| `/unfreeze` | Clear the freeze boundary mid-session |
| `/guard` | Full safety: `/careful` + `/freeze` combined |
| `/browse` | Headless browser |
| `/open-gstack-browser` | Launch GStack Browser (Chromium + sidebar) |
| `/pair-agent` | Pair a remote AI agent with your browser |
| `/setup-browser-cookies` | Import cookies for authenticated tests |
| `/benchmark` | Performance regression detection |
| `/benchmark-models` | Cross-model benchmark |
| `/make-pdf` | Markdown to publication-quality PDFs |
| `/learn` | Save cross-session learnings |
| `/setup-gbrain` | Onboard cross-session memory (gbrain) |
| `/codex` | OpenAI Codex CLI second opinion |

### Superpowers Commands

| Command | When to Use |
|---------|------------|
| `/superpowers:brainstorming` | Refining technical approach |
| `/superpowers:writing-plans` | Creating TDD task breakdown |
| `/superpowers:subagent-driven-development` | Executing with subagents + TDD |
| `/superpowers:executing-plans` | Inline execution (small projects) |
| `/superpowers:dispatching-parallel-agents` | Independent parallel tasks |
| `/superpowers:systematic-debugging` | Finding root cause of bugs |
| `/superpowers:using-git-worktrees` | Feature branch isolation |
| `/superpowers:finishing-a-development-branch` | Merge/PR/discard |
| `/superpowers:test-driven-development` | Manual TDD enforcement |
| `/superpowers:verification-before-completion` | Verify before claiming done |
| `/superpowers:requesting-code-review` | Dispatch review subagent |
| `/superpowers:receiving-code-review` | Handle review feedback |
| `/superpowers:writing-skills` | Plugin/skill projects only |

## How It Stays Up to Date

A GitHub Actions workflow runs weekly and checks for new versions of GStack, Superpowers, and Claude Code. When changes are found, it automatically updates the plugin and creates a PR. A self-repair workflow handles failures automatically.

See [VERSIONS.md](VERSIONS.md) for currently tracked versions.

## Contributing

This is a work in progress and **any help is welcome**:

- **Try it out** — Use the workflow on a real project and report what works and what doesn't
- **Open issues** — Bug reports, unclear documentation, missing scenarios
- **Submit PRs** — Fixes, improvements, new common scenarios
- **Share your experience** — Write about your setup or workflow adaptations

### Areas that need help

- Testing with more project types (mobile, data pipelines, monorepos, infrastructure)
- Better routing heuristics for edge cases
- Integration testing after upstream framework updates

### How to contribute

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a PR

## Frequently Asked Questions

**Should I use GStack or Superpowers?**
Both. They cover different phases. This project gives you the workflow to combine them.

**Can I use this with an existing project?**
Yes. Run `/adapt` — it preserves your existing CLAUDE.md and adds only the routing section.

**Do I need both frameworks installed?**
Yes. Install both [Superpowers](https://github.com/obra/superpowers) and [GStack](https://github.com/garrytan/gstack), then add this plugin for routing.

**What if I only want one framework?**
Each works fine on its own. This project is for people who want to use both together.

**How does context management compare to GSD?**
GSD is a full orchestration framework with wave-based execution and state machines. It's powerful but creates nesting problems with Superpowers' SDD (three layers of orchestration). This plugin takes GSD's best idea — context hygiene — and implements it as a lightweight save/restore mechanism. If you want full GSD, install it separately.

**Does this work with Cursor / Windsurf?**
No. Built for [Claude Code](https://claude.ai/code) only.

**What project types does this support?**
Web apps, APIs, mobile, CLI tools, libraries, data pipelines, monorepos, Claude Code plugins, and more. The setup skill tailors routing to your project.

## Keywords

`claude code best setup` `claude code workflow` `gstack superpowers together` `best claude code plugins` `claude code TDD workflow` `ai coding workflow` `claude code skills` `agentic development workflow` `claude code framework comparison` `how to use gstack and superpowers` `claude code project setup` `CLAUDE.md generator` `claude code routing` `ai-assisted software development` `claude code context management` `context rot prevention` `claude code session management` `gsd alternative`

## A Note on How This Was Built

This entire project — the routing plugin, the skill evaluation tables, the consistency checks, and even this README — was developed by Claude Code using the very workflow it documents. No human wrote or edited the content. A human guided the direction and reviewed the results, but every line was authored by AI.

The workflow needed to make sense to an AI that would actually follow it, not just read well to a human skimming a README. The result is a set of instructions that Claude Code genuinely works well with — because it wrote them for itself.

Whether that's reassuring or unsettling is left as an exercise for the reader.

## License

MIT

## Acknowledgments

- [Superpowers](https://github.com/obra/superpowers) by Jesse Vincent — the implementation backbone
- [GStack](https://github.com/garrytan/gstack) by Garry Tan — the planning and review backbone
- Built for [Claude Code](https://claude.ai/code) by Anthropic
