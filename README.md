# Superpowers + GStack: Routing, Context Management & Workflow

> **"Superpowers owns the implementation loop, GStack owns everything before and after it. Context Guard keeps the session clean."**

A Claude Code plugin that integrates [Superpowers](https://github.com/obra/superpowers) and [GStack](https://github.com/garrytan/gstack) into one workflow — with skill routing, automatic context management, and project auto-configuration. New or existing project, run `/adapt`: it analyzes your setup, preserves your CLAUDE.md, and adds routing — so you can jump right in.

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

- **Claude Code Plugin** with fourteen skills:
  - `/adapt` — Sets up a new project's CLAUDE.md or upgrades an existing one without losing its content. The analysis and skill selection are the skill's; every write is `scripts/adapt-claude-md.py` — deterministic, idempotent, with a growth gate that defers (never destroys) a section you have written into, `--rescue` to move such content into an unmarked section, and a Removed / Deferred report
  - `/autoimplement` — Auto-advance through a multi-phase implementation plan: one subagent per phase (the Claude Code Workflow tool may run the loop), `/review` + `/pitfall-verification` chained at every phase boundary, an active pre-flight chain on the plan itself before Phase 1 unless the latest plan commit matches `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)`. Stops by default on any actionable finding; severe findings always stop. Hard refusals: fewer than 2 phases, missing per-phase commit steps, dirty working tree, on `main`/`master`, plan touches migrations / secrets / credentials / `.env` / `.ssh`.
  - `/context-handoff` — Writes a human-readable handoff to `docs/superpowers/handoff.md` before `/clear` or `/compact`. Auto-resumes on next session start. Different from gstack's `/context-save` — this lives in the repo and works cross-machine.
  - `/htmlify` — Offline HTML rendering of MD artefacts (design docs, plans, handoffs) and per-directory dashboards in the plugin's house style (`styles/companion.css`). Since 3.0.0 the fallback: previews normally go through Claude Code's Artifact tool. Bun + TypeScript with its own test suite; sanitized via DOMPurify.
  - `/pitfall-verification` — Final-check skill run after any PRD, spec, plan, or code artifact. Stage 0 resolves the target explicitly and computes the tier **floor** mechanically via `scripts/classify-change.py` — the agent may escalate above it, never below. The self-pitfall rounds infer domain-specific pitfalls from the code's own history (paths, `git log`, past `fix:` commits, existing tests). **Multi-model orchestrator:** for ship-worthy changes the Codex lens runs through gstack `/review` (which owns the Codex pass), for high-stakes changes also `/superpowers-gstack:third-lens-review`, ending in an adversarial synthesis. Trivial changes get only the self-pitfall pass.
  - `/quality-review` — Perceived-quality gate run after a PRD, spec, or implementation plan, before implementation begins. Hunts pitfalls that make a product feel cheap or broken even when it technically works (silent failures, missing loading/empty states, error recovery, state drift, animations, AI output, sudo flows). Complementary to `/pitfall-verification`: that one asks "will this work?", this one asks "will this feel good?".
  - `/third-lens-review` — External model house lens, **normally auto-invoked by `/pitfall-verification` Stage 3** for high-stakes changes; invoke directly only for an ad-hoc third-house read. A different training distribution sees what two Western houses both took for granted (dead code, use-after-free, degraded-state bugs). Runs via `scripts/third-lens-review.py` on the patched artifact, then a mandatory **adversarial synthesis** (finding is real until refuted). Routing by `--role`: `architecture` (Zhipu, default), `correctness` (DeepSeek), `countersynthesis` (OpenAI via the `codex` CLI); the model ids live only in the script, which refuses a pin OpenRouter no longer serves. Non-Western infra — keep sensitive artifacts to the self + Codex lenses. Key in macOS Keychain `openrouter-api-key`.
  - `/apple-native-review` — Apple-native conformance gate for iOS, iPadOS and macOS PRDs, specs, and plans. Platform from `.gstack/track` or the artifact's own signals; per-platform HIG categories (macOS: keyboard shortcuts, menu bar, dock, App menu …; iOS: touch targets, navigation paradigm, modal presentation, gestures, haptics …). Every finding cites a HIG page fetched this run (the apple-docs MCP supplies API reference; the swiftui-rag corpus the current idiom). Asks "is this Apple-native?" — complementary to `/pitfall-verification` and `/quality-review`.
  - `/e2e-scaffold` — One-shot XCUITest scaffolding for SwiftUI projects on iOS or macOS: deterministic scene-walk, ranked TIER-1/2/3 stubs, accessibility-identifier suggestions (`<ViewName>_<ControlType>_<Purpose>`) with batch confirmation, and a Claude-readable xcresult runner copied from `templates/run-uitests.sh` that honours the `.gstack/e2e-executor` pin (`host`|`vm`). Manual invocation only — modifies project files; normally reached via `/e2e-route`.
  - `/verify-and-land` — the step between "fixed" and "shipped": builds the branch you are standing on, launches that exact bundle rather than the `/Applications` copy Spotlight opens, proves on screen which build is running, asks whether the fix is actually there, then pushes and offers merge or PR. macOS + iOS simulator; short path for web dev servers.
  - `/e2e-route` — pure dispatcher for Swift E2E requests: reads platform × intent × the `.gstack/e2e-executor` pin and routes to `/e2e-scaffold`, MCP-live simulator automation, or visual-regression review. Names the executor + next action, then hands off. Pinned to `vm`, committed macOS runs go to a VM rig via `vm-e2e`; absent rig → host run with a printed line, failing rig → loud failure.
  - `/spec-drift` — standalone "does this plan still match the code?" audit, invoked as `/superpowers-gstack:spec-drift <plan-path> [--base <ref>]`. Wraps `/ship` Step 8's plan-completion section: read from `~/.claude/skills/gstack/ship/sections/plan-completion.md` at run time, never copied, sha256-pinned in `skills/spec-drift/pin.json` (`--repin` shows the upstream diff and asks before accepting). Explicit plan path and explicit `--base`. Same report as Step 8 and a last-line JSON with the six keys the skill contract names (Step 8 itself spells NOT DONE `not_done` since gstack 1.83), plus exit `0` clean / `1` drift / `2` could not run. Report only; write-back and a drift ledger are Fase 2 of `docs/superpowers/specs/2026-09-07-spec-drift-design.md`.
  - `/superpowers-gstack:office-hours-track-aware` — wraps upstream `/office-hours` for dual-track projects: runs the gstack brainstorm, infers track (native vs web), asks the platform question inline only if needed, writes `.gstack/track`, relocates the design doc into `docs/`, publishes it as an Artifact page BEFORE the Approve / Revise / Restart gate, and suggests `/superpowers-gstack:swiftui-design-consultation` next for native tracks. **Intercepts `/office-hours`** via CLAUDE.md routing rules.
  - `/superpowers-gstack:swiftui-design-consultation` — Apple-canon design system consultation for SwiftUI projects; produces `DESIGN.md` + a Swift Package starter from templates and chains into `/apple-native-review` with a HIG conformance budget. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing.
- **Per-skill model routing** (v0.2) — `/adapt` emits a `## Model Routing` section inside the generated CLAUDE.md. Routes by two axes: a per-skill **base tier** (`fable`/`opus`/`sonnet`/`haiku`) and a project-level **domain-sensitivity** modifier (very high/high/medium/low — inferred from project type and security signals). See `skills/adapt/model-routing.md` for the canonical table. Advisory — orchestrator-Claude consults it when dispatching subagents.
- **[Appendix](appendix-reference.md)** — Skill internals, troubleshooting, and anti-patterns
- **Automated update pipeline** — GitHub Actions keeps the plugin in sync when upstream frameworks change

> **Tip:** In autocomplete, type `/adapt` or `/context-handoff` — Claude Code matches on the skill name. The full prefixed form (e.g. `/superpowers-gstack:adapt`) also works.

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
/adapt        # new project or existing one — same skill
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
| Long session, save state | `/context-handoff` |

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
│  PHASE 1.5: SPEC REVIEW (this plugin)            │
│                                                  │
│  /pitfall-verification → "will this work?"       │
│  /quality-review       → "will this feel good?"  │
│  /apple-native-review  → "is this Apple-native?" │
│                          (iOS, iPadOS, macOS)    │
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
1. After `/compact`, Claude asks if you want continuous handoff for the session (unrelated to Claude Code's `auto` permission mode — this only governs how often `handoff.md` is rewritten)
2. If yes, it keeps `docs/superpowers/handoff.md` updated as a living document — current task, decisions, next step
3. When context gets heavy again, Claude suggests `/clear`
4. After `/clear`, Claude automatically reads the handoff file, presents where you left off, and clears it — no "resume" command needed. In continuous mode it keeps the `mode:` line instead of blanking the file, so the next compact doesn't ask you again

**Manual use:** Run `/context-handoff` anytime to save state before a `/clear`.

No hooks, no orchestration overhead, no nesting. Just save and restore.

## Common Scenarios

### New Feature (Full Workflow)

```
/office-hours          → Frame the idea
/plan-ceo-review       → Validate scope
/plan-eng-review       → Lock architecture
  → Save key decisions to docs/
/clear
/pitfall-verification  → Spec-level: "will this work?"
/quality-review        → Spec-level: "will this feel good?"
/apple-native-review   → Spec-level: "is this Apple-native?"
/superpowers:brainstorming         → Adopt design, refine technical approach
/superpowers:writing-plans         → Break into TDD tasks
/pitfall-verification  → Plan-level: re-check after writing-plans
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

Spec or plan written? (after writing-specs / writing-plans / plan-eng-review)
  → /pitfall-verification → /quality-review
  → /apple-native-review (platform from .gstack/track)
  → /superpowers:writing-plans (or /superpowers:subagent-driven-development)

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
| `/autoplan` | Chains all three reviews; Eng review runs last, always |
| `/review` | Pre-merge code review (8 lenses, incl. advisory simplification) |
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
| `/retro` | Sprint retrospective; harvests shortcut-debt markers |
| `/health` | Code quality dashboard |
| `/context-save` | Save progress, save state |
| `/context-restore` | Resume where left off |
| `/context-handoff` | Write handoff to repo before /clear (cross-machine, no gstack required) |
| `/careful` | Destructive command warnings |
| `/freeze` | Restrict edits to one directory |
| `/unfreeze` | Clear the freeze boundary mid-session |
| `/guard` | Full safety: `/careful` + `/freeze` combined |
| `/browse` | Headless browser |
| `/open-gstack-browser` | Launch GStack Browser (Chromium + sidebar) |
| `/pair-agent` | Pair a remote AI agent with your browser; a re-pair with the same `--client` and a narrower `--restrict` revokes the old session immediately |
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
| `/superpowers:using-git-worktrees` | Feature branch isolation — asks for consent before creating; detects if already in a worktree |
| `/superpowers:finishing-a-development-branch` | Merge/PR/discard — only cleans up worktrees it created (inside `.worktrees/`) |
| `/superpowers:test-driven-development` | Manual TDD enforcement |
| `/superpowers:verification-before-completion` | Verify before claiming done |
| `/superpowers:requesting-code-review` | Dispatch review subagent (uses `general-purpose` agent with self-contained template) |
| `/superpowers:receiving-code-review` | Handle review feedback |
| `/superpowers:writing-skills` | Plugin/skill projects only |

### Model Routing (v0.2)

When orchestrator-Claude dispatches a subagent, it should pick the model based on the **task being executed** and the project's **domain sensitivity**, not the orchestrator's default. The full table lives at [`skills/adapt/model-routing.md`](skills/adapt/model-routing.md). Highlights:

| Skill / Phase                                         | Base tier         |
|-------------------------------------------------------|-------------------|
| `/plan-ceo-review`                                    | opus              |
| `/superpowers:brainstorming`, planning, engineering   | sonnet            |
| `/review`, `/cso`, `/retro`                           | sonnet            |
| `/superpowers:verification-before-completion`         | haiku             |
| `/ship`, `/health`, `/learn`, `/canary`               | haiku             |
| High-blast-radius coding (RT audio, migrations, auth) | opus + verify     |
| Novel technique, long-horizon, not chunkable          | fable             |

The recommendations are **advisory v0.2**. Domain sensitivity (inferred at setup/adapt time from project type and Q3 security signals) acts as a modifier: very-high/high domains floor coding at `opus`; medium uses the base tier; low can go one tier cheaper. See `skills/adapt/model-routing.md` for the full table with phase-level breakdowns and caveats.

## How It Stays Up to Date

A GitHub Actions workflow runs weekly and checks for new versions of GStack, Superpowers, and Claude Code. When changes are found, it automatically updates the plugin and creates a PR. A self-repair workflow handles failures automatically.

See [VERSIONS.md](VERSIONS.md) for currently tracked versions.

## Testing

Plugin behaviors that depend on LLM dispatch (track-aware routing, slash-command interception) are tested end-to-end against `claude --print`. See [`tests/README.md`](tests/README.md) for prerequisites, cost (~1 min per case, a few cents each), and what's covered.

```bash
bash tests/run.sh --integration
```

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
Yes. Run `/adapt` — it preserves your existing CLAUDE.md and adds only the plugin's sections; every write goes through a deterministic script with a snapshot and a Removed report.

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
