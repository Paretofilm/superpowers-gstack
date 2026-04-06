# Superpowers + GStack: The Combined Workflow

> **"Superpowers owns the implementation loop, GStack owns everything before and after it."**

A structured workflow and Claude Code plugin for using [Superpowers](https://github.com/obra/superpowers) and [GStack](https://github.com/garrytan/gstack) together. Instead of choosing one framework, use both — each in the phase where it excels.

**Status: Work in Progress** — This project is actively being developed. Contributions, feedback, and ideas are very welcome. See [Contributing](#contributing).

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
- **Claude Code Plugin** with two skills:
  - `/superpowers-gstack:setup-routing` — Generates a tailored CLAUDE.md for new projects
  - `/superpowers-gstack:adapt` — Adds routing to existing projects without losing your CLAUDE.md content
- **Automated update pipeline** — GitHub Actions keeps the manual in sync when upstream frameworks change

## Quick Start

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

```bash
git clone https://github.com/Paretofilm/superpowers-gstack.git ~/Developer/superpowers-gstack
cd ~/Developer/superpowers-gstack
./scripts/install-plugin.sh
./scripts/setup-hooks.sh
```

Restart Claude Code after installation.

### 3. Set up your project

```
# New project:
/superpowers-gstack:setup-routing

# Existing project:
/superpowers-gstack:adapt
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

## License

MIT

## Acknowledgments

- [Superpowers](https://github.com/obra/superpowers) by Jesse Vincent — the implementation backbone
- [GStack](https://github.com/garrytan/gstack) by Garry Tan — the planning and review backbone
- Built for [Claude Code](https://claude.ai/code) by Anthropic
