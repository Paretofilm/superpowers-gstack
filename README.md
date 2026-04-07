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

- **[Workflow Manual](superpowers-gstack-workflow-manual.md)** — Phase-by-phase guide with routing logic, session management, and common scenarios
- **[Appendix](appendix-reference.md)** — Skill internals, troubleshooting, and anti-patterns
- **Claude Code Plugin** with three skills:
  - `/setup-routing` — Generates a tailored CLAUDE.md for new projects
  - `/adapt` — Adds routing to existing projects without losing your CLAUDE.md content
  - `/context-guard` — Lightweight context management inspired by [GSD](https://github.com/gsd-build/get-shit-done) — saves session state, auto-resumes after `/clear` or `/compact`, and proactively suggests context resets when sessions get long

> **Tip:** In autocomplete, type `/setup-routing`, `/adapt`, or `/context-guard` — Claude Code matches on the skill name. The full prefixed form (e.g. `/superpowers-gstack:adapt`) also works.
- **Automated update pipeline** — GitHub Actions keeps the manual in sync when upstream frameworks change

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
/plugin marketplace add kjetilge/kjetil-claude-marketplace
/plugin install superpowers-gstack@kjetil-plugins
```

Restart Claude Code after installation.

Optionally, set up the update notification hook:

```bash
git clone https://github.com/Paretofilm/superpowers-gstack.git ~/Developer/superpowers-gstack
cd ~/Developer/superpowers-gstack && ./scripts/setup-hooks.sh
```

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

> These are shorthand for `/superpowers-gstack:setup-routing` and `/superpowers-gstack:adapt`. Both forms work — the short form is easier to find in autocomplete.

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

## Context Management

Long sessions degrade Claude's output quality — a problem known as context rot. GSD solves this with a full orchestration layer, but that creates nesting issues when combined with Superpowers' subagent-driven development. This plugin takes a lighter approach:

**How it works:**
1. After `/compact`, Claude asks if you want to activate auto context guard for the session
2. If yes, it keeps `docs/superpowers/handoff.md` updated as a living document — current task, decisions, next step
3. When context gets heavy again, Claude suggests `/clear`
4. After `/clear`, Claude automatically reads the handoff file, presents where you left off, and clears it — no "resume" command needed

**Manual use:** Run `/context-guard` anytime to save state before a `/clear`.

No hooks, no orchestration overhead, no nesting. Just save and restore.

## The Workflow at a Glance

```
Phase 1: Planning (GStack)        Phase 2: Implementation (Superpowers)
/office-hours → frame idea         /superpowers:brainstorming → refine
/plan-ceo-review → validate        /superpowers:writing-plans → TDD tasks
/plan-eng-review → architecture    /superpowers:subagent-driven-development → build
                                   /superpowers:systematic-debugging → fix bugs
        │                                    │
        └──── /clear ────────────────────────┘
                                             │
Phase 3: Review & QA (GStack)      Phase 4: Ship (GStack)
/review → code review              /ship → PR and deploy
/qa <url> → browser testing        /canary → monitor
/cso → security audit              /retro → retrospective
```

Read the full [Workflow Manual](superpowers-gstack-workflow-manual.md) for details.

## Contributing

This is a work in progress and **any help is welcome**. Here are some ways to contribute:

- **Try it out** — Use the workflow on a real project and report what works and what doesn't
- **Open issues** — Bug reports, unclear documentation, missing scenarios
- **Submit PRs** — Fixes, improvements, new common scenarios
- **Share your experience** — Write about your setup, what you added to your CLAUDE.md, or workflow adaptations that worked for your team
- **Suggest skills** — If upstream adds new skills that should be in the routing tables, let us know

### Areas that need help

- Testing with more project types (mobile, data pipelines, monorepos, infrastructure)
- Better routing heuristics for edge cases
- Integration testing after upstream framework updates
- Documentation improvements and examples

### How to contribute

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a PR

No contribution is too small. Even fixing a typo or clarifying a sentence helps.

## How It Stays Up to Date

A GitHub Actions workflow runs weekly and checks for new versions of GStack, Superpowers, and Claude Code. When changes are found, it automatically updates the manual and creates a PR. A self-repair workflow handles failures automatically.

See [VERSIONS.md](VERSIONS.md) for currently tracked versions.

## Frequently Asked Questions

**Should I use GStack or Superpowers?**
Both. They cover different phases. GStack handles planning, code review, QA, security, and shipping. Superpowers handles implementation with TDD, debugging, and structured coding. This project gives you the workflow to combine them.

**Can I use this with an existing project?**
Yes. Run `/superpowers-gstack:adapt` — it analyzes your project, preserves your existing CLAUDE.md content, and adds only the routing section needed.

**Do I need both frameworks installed?**
Yes. This workflow requires both [Superpowers](https://github.com/obra/superpowers) (Claude Code plugin) and [GStack](https://github.com/garrytan/gstack) (Claude Code skills). Install both, then add this plugin for routing.

**What if I only want GStack or only Superpowers?**
Each works fine on its own. This project is specifically for people who want to use both together. If you only use one, you don't need this.

**How does context management compare to GSD?**
GSD (Get Shit Done) is a full orchestration framework with wave-based execution, state machines, and hooks. It's powerful but creates nesting problems when combined with Superpowers' subagent-driven development (three layers of orchestration). This plugin takes GSD's best idea — context hygiene — and implements it as a lightweight save/restore mechanism with no orchestration overhead. If you want full GSD, install it separately; if you want context management that plays nicely with the Superpowers + GStack workflow, use `/context-guard`.

**Does this work with Cursor / Windsurf / other AI editors?**
No. This is built for [Claude Code](https://claude.ai/code) (Anthropic's CLI). Both Superpowers and GStack are Claude Code frameworks.

**How is this different from the comparison articles?**
Articles compare the frameworks. This project integrates them — with a concrete workflow, routing rules that prevent conflicts, a CLAUDE.md generator, and an automated pipeline that keeps everything in sync with upstream changes.

**What project types does this support?**
The setup skill asks about your project and generates routing tailored to it: web apps, APIs, mobile, CLI tools, libraries, data pipelines, monorepos, Claude Code plugins, and more.

## Keywords

`claude code best setup` `claude code workflow` `gstack superpowers together` `best claude code plugins` `claude code TDD workflow` `ai coding workflow` `claude code skills` `agentic development workflow` `claude code framework comparison` `how to use gstack and superpowers` `claude code project setup` `CLAUDE.md generator` `claude code routing` `ai-assisted software development` `claude code context management` `context rot prevention` `claude code session management` `gsd alternative`

## A Note on How This Was Built

This entire project — the workflow manual, the routing plugin, the skill evaluation tables, the consistency checks, and even this README — was developed by Claude Code using the very workflow it documents. No human wrote or edited the content. A human guided the direction and reviewed the results, but every line was authored by AI.

This was deliberate. The workflow needed to make sense to an AI that would actually follow it, not just read well to a human skimming a README. The result is a set of instructions that Claude Code genuinely works well with — because it wrote them for itself.

Whether that's reassuring or unsettling is left as an exercise for the reader.

## License

MIT

## Acknowledgments

- [Superpowers](https://github.com/obra/superpowers) by Jesse Vincent — the implementation backbone
- [GStack](https://github.com/garrytan/gstack) by Garry Tan — the planning and review backbone
- Built for [Claude Code](https://claude.ai/code) by Anthropic
