# Model Routing Table — v0.2 (advisory)

> **Status:** v0.2, advisory. Two axes: a per-skill **base tier** (the skill's
> dominant cognitive demand) modulated by a **domain-sensitivity** axis (how
> silently a subtle error compounds). Recommendations are sensible defaults, not
> a benchmarked skill×model matrix — override per project when you have evidence.
>
> **Audience:** read by `setup-routing` and `adapt`; folded into generated
> `CLAUDE.md` files so orchestrator-Claude consults it when dispatching subagents.
>
> Routing is Claude-tier only; the tier names are stable, the ids above move.

## How orchestrator-Claude uses this

In Claude Code you have an `Agent` tool and dispatch subagents with a `model:`
parameter. When you dispatch a subagent to execute one of the skills below, pass
the tier from the **base table** — then apply the **domain modifier** below,
which can shift it up or down. Multi-phase entries (e.g.
`/superpowers:test-driven-development`) become per-phase subagent calls.

Other harnesses (Cursor, opencode, Codex CLI, custom) support multi-model
dispatch via their own mechanisms — treat the tier names as advisory and map
them to your harness's model picker.

**Choosing a tier is a two-step lookup:** (1) find the skill's base tier below;
(2) apply the domain-sensitivity modifier for the code the subagent will touch.
The modifier wins on correctness-sensitive work — a "cheap coding" phase in a
high-blast-radius domain is a false economy (see below).

## Model identifiers used

The tier names are what the emitted CLAUDE.md blocks carry; this file is the one
place they map to model ids. Update the ids here when a new model ships
(`scripts/check-new-models.py` opens an issue when Anthropic lists a newer one).

- `fable` — `claude-fable-5-1` — top tier. Novel, long-horizon, autonomous work
  where the approach must be *invented*, not mapped. Roughly twice the price of
  Opus; its lead grows with task length. On short, well-scoped tasks it is close
  to Opus — don't pay the premium there.
- `opus` — `claude-opus-5` — heavy reasoning, novel synthesis, strategic
  challenge, and the default for high-blast-radius coding.
- `sonnet` — `claude-sonnet-5` — structured engineering, code review, planning,
  contained-blast-radius coding with tests as the net. The split against opus is
  mostly about blast radius; on genuinely hard reasoning, opus still buys capability.
- `haiku` — `claude-haiku-4-5` — mechanical, templated, deterministic.

## The domain-sensitivity axis

Difficulty is **not** concentrated in "thinking" phases with a clean handoff to
cheap "coding". In correctness-sensitive domains (real-time audio, DSP, lock-free
concurrency, migration logic, money, auth), the risk is smeared into the *coding
itself* — subtle one-line traps a *less* capable coder produces *more* of, not
fewer. So "plan it, then route coding to the cheapest model" is a false economy
there. The cheap correctness lever is **verification** (multi-lens: self-pitfall +
Codex + third house), not a pricier coder — verification ROI is *orthogonal to
coder tier*. Budget multi-lens on every ship-worthy change regardless of who
wrote the code.

### Routing matrix — base tier × domain

|                       | **Known technique**                         | **Novel technique**                                                    |
|-----------------------|---------------------------------------------|------------------------------------------------------------------------|
| **High blast-radius** | **opus** + mandatory multi-lens verify      | **fable** — research + architecture + first impl as one long autonomous run |
| **Contained**         | **sonnet** (or opus), green tests as the net| **opus**                                                               |

### Domain-sensitivity table (starter — extend per project)

| Domain                                      | Sensitivity | Coding-tier floor | Notes |
|---------------------------------------------|-------------|-------------------|-------|
| RT audio / DSP / lock-free concurrency      | very high   | opus + verify     | silent corruption; no "safe cheap coding" |
| Migration / data-transform logic            | high        | opus + verify     | irreversibility |
| Auth / payments / security                  | high        | opus (Fable→Opus fallback anyway) | |
| App / UI feature wiring                     | medium      | sonnet            | tests catch most |
| Format plumbing / serialization             | low         | sonnet / haiku    | round-trip tests are a strong net |
| Templated scaffolding / mechanical refactor | low         | haiku             | deterministic |

## When Fable earns its 2× (and when it does NOT)

**Use `fable` only when ALL hold:**
- Technique is genuinely novel (invent the approach, not map a known one)
- Task is long-horizon / autonomous (its lead grows with length)
- Not cleanly chunkable into short well-scoped pieces (chunking → opus wins on cost)

**Do NOT use `fable` for:** planning well-understood work, coding against a
fully-pinned spec, verification (that's the multi-lens job), or anything a tight
opus spec turns into short well-scoped chunks. Second-order effect: **a precise
opus spec converts "long+ambiguous" into "short+well-scoped," removing the very
condition that justifies Fable** — so opus spec-writing is itself a Fable-cost
lever.

### Dispatching a Fable subagent

1. **Scope open on approach, bounded on deliverable.** Over-specifying the
   *approach* destroys the exploration you're paying 2× for; leaving the
   *deliverable* unbounded burns tokens on integration opus does cheaper. Let
   Fable choose the *how*; you choose *where it stops* (e.g. "research +
   architecture + prototype + tests — do NOT integrate into the RT path").
2. **Don't use `isolation: worktree` for untracked targets.** Worktree checkout
   only includes tracked files; new/untracked package dirs won't exist there.
   Isolate only when mutating *tracked* files in parallel.
3. **A subagent's self-report is a claim, not verification.** Re-read the new
   files, re-run the suite, run Codex — regardless of tier. The dispatcher owns
   verification.
4. **Scope one focused unit** — "novel-technique discovery + design doc +
   prototype + tests" — not an open-ended session. Reserve it for work whose
   novelty and blast radius clearly clear the premium.

## Base routing table (Claude tiers; apply the domain modifier above)

### Superpowers skills

| Skill                                          | Base tier   |
|------------------------------------------------|-------------|
| `/superpowers:brainstorming`                   | sonnet      |
| `/superpowers:writing-plans`                   | sonnet      |
| `/superpowers:writing-skills`                  | sonnet      |
| `/superpowers:executing-plans`                 | sonnet      |
| `/superpowers:subagent-driven-development`     | see phases  |
| `/superpowers:dispatching-parallel-agents`     | see phases  |
| `/superpowers:test-driven-development`         | see phases  |
| `/superpowers:systematic-debugging`            | see phases  |
| `/superpowers:verification-before-completion`  | haiku       |
| `/superpowers:requesting-code-review`          | sonnet      |
| `/superpowers:receiving-code-review`           | sonnet      |
| `/superpowers:finishing-a-development-branch`  | sonnet      |
| `/superpowers:using-git-worktrees`             | haiku       |
| `/superpowers:using-superpowers`               | haiku       |

### GStack skills — Phase 1 (Planning)

| Skill                  | Base tier |
|------------------------|-----------|
| `/office-hours`        | sonnet    |
| `/plan-ceo-review`     | **opus**  |
| `/plan-eng-review`     | sonnet    |
| `/plan-design-review`  | sonnet    |
| `/plan-devex-review`   | sonnet    |
| `/design-consultation` | sonnet    |
| `/design-shotgun`      | sonnet    |
| `/autoplan`            | (chained) |
| `/plan-tune`           | haiku     |

### GStack skills — Phase 3 (Review & QA)

| Skill            | Base tier   |
|------------------|-------------|
| `/review`        | sonnet      |
| `/qa`            | see phases  |
| `/qa-only`       | sonnet      |
| `/cso`           | sonnet      |
| `/design-review` | sonnet      |
| `/design-html`   | sonnet      |
| `/devex-review`  | sonnet      |
| `/investigate`   | sonnet      |

### GStack skills — Phase 4 (Ship & Monitor)

| Skill                | Base tier  |
|----------------------|------------|
| `/ship`              | see phases |
| `/land-and-deploy`   | haiku      |
| `/canary`            | haiku      |
| `/landing-report`    | haiku      |
| `/setup-deploy`      | sonnet     |
| `/document-release`  | sonnet     |
| `/retro`             | sonnet     |
| `/learn`             | haiku      |
| `/setup-gbrain`      | haiku      |
| `/health`            | haiku      |
| `/make-pdf`          | haiku      |

### GStack skills — Utility

| Skill                      | Base tier   |
|----------------------------|-------------|
| `/careful`                 | haiku       |
| `/freeze`                  | haiku       |
| `/unfreeze`                | haiku       |
| `/guard`                   | haiku       |
| `/browse`                  | haiku       |
| `/open-gstack-browser`     | haiku       |
| `/pair-agent`              | haiku       |
| `/setup-browser-cookies`   | haiku       |
| `/context-handoff`         | haiku       |
| `/context-save`            | haiku       |
| `/context-restore`         | haiku       |
| `/benchmark`               | haiku       |
| `/benchmark-models`        | haiku       |
| `/codex`                   | (delegated) |

### Plugin-internal skills (superpowers-gstack)

| Skill                                        | Base tier |
|----------------------------------------------|-----------|
| `/superpowers-gstack:setup-routing`          | sonnet    |
| `/superpowers-gstack:adapt`                  | sonnet    |
| `/superpowers-gstack:pitfall-verification`   | sonnet    |
| `/superpowers-gstack:quality-review`         | sonnet    |
| `/superpowers-gstack:apple-native-review`    | sonnet    |
| `/superpowers-gstack:e2e-scaffold`           | haiku     |
| `/superpowers-gstack:spec-drift`             | sonnet    |
| `/superpowers-gstack:e2e-route`              | haiku     |
| `/superpowers-gstack:context-handoff`        | haiku     |
| `/superpowers-gstack:htmlify`                | haiku     |

## Phase-level routing (for "see phases" entries)

### `/superpowers:test-driven-development`

| Phase                              | Base tier | Domain override |
|------------------------------------|-----------|-----------------|
| Write failing test                 | sonnet    | — |
| Implement minimum                  | sonnet    | **opus** if high-blast-radius (RT audio, concurrency, DSP, migration, money, auth); **fable** if also a novel technique |
| Refactor                           | sonnet    | opus if high-blast-radius |
| Run tests + parse failures         | haiku     | — |

### `/superpowers:subagent-driven-development` & `/superpowers:dispatching-parallel-agents`

The orchestrator stays on the session's model. Each per-task subagent's tier is
the *task-type* row above, with the domain modifier applied for the code it
touches. A novel + high-blast-radius task is a Fable candidate — scope it per the
"Dispatching a Fable subagent" rules.

### `/superpowers:systematic-debugging`

| Phase                          | Base tier | Domain override |
|--------------------------------|-----------|-----------------|
| Investigate (gather evidence)  | sonnet    | — |
| Hypothesize (novel/ambiguous)  | opus      | fable if the failure mode is genuinely novel + high-blast-radius |
| Hypothesize (well-scoped)      | sonnet    | — |
| Verify hypothesis              | haiku     | — |
| Implement fix                  | (use TDD row) | (use TDD row) |

### `/qa`

| Phase                          | Base tier | Domain override |
|--------------------------------|-----------|-----------------|
| Navigate + screenshot          | haiku     | — |
| Triage bugs (severity, repro)  | sonnet    | — |
| Write fix                      | sonnet    | opus if high-blast-radius |

### `/ship`

| Phase                       | Base tier |
|-----------------------------|-----------|
| Detect base branch          | haiku     |
| Run tests                   | haiku     |
| Review diff vs base         | sonnet    |
| Bump VERSION + CHANGELOG    | haiku     |
| Write commit message        | sonnet    |
| Push + create PR            | haiku     |
| Write PR description        | sonnet    |

## Caveats

1. **Advisory, not enforced.** Orchestrator-Claude may override — cite evidence when you do.
2. **Empirically calibrated, not benchmarked per skill.** The base tiers come from
   each skill's cognitive-demand profile; the domain axis comes from a real dispatch
   where an independent review found no bugs in the top tier's novel code but two in
   adjacent lower-tier code — verification, not coder tier, is the lever.
3. **Optimizes for capability-per-cost, not latency.** Fable's long autonomous runs
   trade wall-clock for correctness on the hardest, novelest work — reserve accordingly.
