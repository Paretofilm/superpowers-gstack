# Model routing v0.2 — domain axis + Fable 5 tier (design note)

> **Status:** IMPLEMENTED in plugin v2.27.0 (2026-07-04). `skills/setup-routing/model-routing.md`
> is now v0.2 (two-axis, Claude-only, Fable tier); both generators (`setup-routing`, `adapt`)
> emit the domain-aware `## Model Routing` block. This note is retained as the design rationale.
> **Author context:** raised while building LiveSet Pro's LSPSampler (DSP/RT audio),
> where 1-D routing repeatedly mis-priced the work.

## The problem with v0.1

`model-routing.md` v0.1 routes **one-dimensionally**: each skill is mapped to a model
by its *dominant cognitive demand* (brainstorming→sonnet, verification→haiku, etc.).
Two gaps:

1. **Fable 5 doesn't exist in the table.** v0.1 only knows `opus-4-7`, `sonnet-4-6`,
   `haiku-4-5`. Fable 5 is now Anthropic's top tier — meaningfully more capable than
   Opus on **long, complex, autonomous** tasks (80.3% vs 69.2% Opus on SWE-bench Pro),
   at ~2× the price ($10/$50 vs $5/$25 per Mtok). Its lead *grows with task length*;
   on short well-scoped tasks the two are close. (Verified via web 2026-07-04.)
   Note: Fable routes cybersecurity/bio/chem/distillation to an Opus fallback, so in
   those domains the two are literally identical — never pay the Fable premium there.

2. **Routing by skill ignores the domain the skill operates in.** The same skill
   (`test-driven-development`, `executing-plans`) carries wildly different correctness
   risk depending on domain. That risk should move the routing decision.

## The core insight: route by (novelty × blast-radius × domain-sensitivity)

Difficulty is **not** concentrated in "thinking" phases with a clean handoff to cheap
"coding". In DSP/RT audio, correctness risk is smeared into the *coding itself*.

### Evidence from LSPSampler (2026-07)

The bugs that actually mattered were **correctness-under-detail in the code**, not
planning or architecture failures — and they were caught by *verification*, not by a
better plan:

| Bug | Where it lived | Would a cheaper coder have caught it? |
|-----|----------------|----------------------------------------|
| YIN O(n²) — 62 s per call | coding (algorithm) | No — plausible-looking nested loop |
| Data-reference race on live reload | coding (concurrency) | No — "looked" ordered by the gen counter |
| Velocity ignored at playback | coding (dropped a param) | No — compiled + passed naive tests |
| `vDSP_zvmags` (power) vs `zvabs` (magnitude) | coding (one call) | No — silently corrupts EQ path |
| SFZ `Bb3`→`B3` after uppercasing | coding (string logic) | No — subtle case bug |

None were novel-technique failures. All were one-line-ish correctness traps that a
*less* capable coding model would produce **more** of, not fewer. So "get it planned,
then route coding to the cheapest model" is a **false economy in correctness-sensitive
domains**. The cheap lever is *verification* (multi-lens: self-pitfall + Codex + third
house), not a cheaper coder.

## Proposed v0.2 model: a domain-sensitivity modifier

Keep the per-skill base recommendation, but add a **domain-sensitivity axis** that
shifts the tier up or down. Two independent knobs:

- **Novelty** — is the technique known (map a solution) or genuinely novel (invent one)?
- **Blast-radius / correctness-sensitivity** — does a subtle error compound silently
  (RT audio, concurrency, DSP, migration logic, money, auth) or is it contained and
  test-catchable (format plumbing, CRUD, templated scaffolding)?

### Routing matrix

|                         | **Known technique**                          | **Novel technique**                                   |
|-------------------------|----------------------------------------------|-------------------------------------------------------|
| **High blast-radius**   | **Opus** + mandatory multi-lens verification | **Fable** — research + architecture + first impl as one long autonomous run |
| **Contained**           | **Sonnet** (or Opus), green tests as the net | **Opus**                                              |

### Domain sensitivity table (starter — extend per project)

| Domain                                   | Correctness-sensitivity | Coding-tier floor | Notes |
|------------------------------------------|-------------------------|-------------------|-------|
| RT audio / DSP / lock-free concurrency   | **very high**           | Opus + verify     | silent corruption; no "safe coding" |
| Migration / data-transform logic         | high                    | Opus + verify     | irreversibility |
| Auth / payments / security               | high                    | Opus (Fable→Opus fallback anyway) | |
| App/UI feature wiring                    | medium                  | Sonnet            | tests catch most |
| Format plumbing / serialization          | low                     | Sonnet/Haiku      | round-trip tests are a strong net |
| Templated scaffolding / mechanical refactor | low                  | Haiku             | deterministic |

## Where Fable earns its 2× (and where it does NOT)

**Use Fable when ALL hold:**
- Technique is genuinely novel (must invent the approach, not map a known one)
- Task is long-horizon / autonomous (its lead grows with length)
- Not stuck-able into short well-scoped chunks (chunking → Opus wins on cost)
- Domain is not in the Fable→Opus safety-fallback set (sec/bio/chem)

**Do NOT use Fable for:** planning well-understood work, coding against a fully-pinned
spec, verification (that's the multi-lens job), or anything a tight Opus spec turns into
short well-scoped chunks. A key second-order effect: **a precise Opus spec converts
"long+ambiguous" into "short+well-scoped," which removes the very condition that
justifies Fable.** So Opus spec-writing is itself a Fable-cost-reduction lever.

### LSPSampler worked example

- **Fable:** Trinn B spectral variation synthesis (transient/harmonic/noise decomposition),
  DDSP model design+training. Novel + high-blast + not cleanly chunkable.
- **Opus/self:** amplitude envelope, round-robin rotation, `.lsp` format, disk-streaming
  (RT-critical but a *known* lock-free pattern already in the codebase).
- **Sonnet:** test scaffolding, format plumbing, refactors with green tests.
- **Always, regardless of coder:** multi-lens verification. Highest ROI in the session.

## Concrete next steps for the routing skill (not done here)

1. Add Fable 5 to the "Model identifiers used" block and a `fable` alias
   (`claude-fable-5`) in the Claude Code column.
2. Add a **domain-sensitivity modifier** section + starter table (above) that
   `setup-routing`/`adapt` fold into generated `CLAUDE.md` files.
3. Update generated `CLAUDE.md` routing guidance so orchestrator-Claude consults
   *both* the skill row *and* the project's domain sensitivity before choosing a tier.
4. Consider a `domain:` hint that `setup-routing` asks for (or infers from stack) so
   the modifier is applied automatically per project.

## Addendum — field notes from a real Fable dispatch (2026-07-04)

The LSPSampler worked example above was executed, not just theorized: Opus (orchestrator)
dispatched Fable via the `Agent` tool (`model: fable`, `isolation: worktree`) for
Trinn B (novel HPSS + SMS stochastic resynthesis). It came back clean under independent
Opus read + Codex. New, evidence-backed lessons the routing skill should absorb:

### 1. Scope a Fable task **open on approach, bounded on deliverable**

Over-specifying the *approach* destroys Fable's value (that's the exploration you're
paying 2× for). But leaving the *deliverable* unbounded burns tokens on integration
work Opus does cheaper. The dispatch that worked said: "research + architecture +
prototype + tests — do NOT integrate into the RT path." The RT integration stayed a
cheap Opus follow-up. Rule: **let Fable choose the how; you choose where it stops.**

### 2. Worktree isolation is a no-op for **untracked** targets

`isolation: worktree` only checks out *tracked* files. LSPSampler's package dir was
untracked, so it didn't exist in the worktree — Fable correctly detected this and wrote
to the main tree. Lesson for dispatch guidance: **don't use worktree isolation when the
work targets untracked files/dirs** (new packages, scaffolding). It gives false safety
and confuses the agent. Isolate only when mutating tracked files in parallel.

### 3. A subagent's self-report is a **claim**, not verification

Fable reported "61/61 green, verified." The orchestrator did not trust it — it re-read
every new source file, re-ran the suite, and ran Codex. That found nothing wrong in
Fable's output (good) — but the discipline is non-negotiable for high-stakes work.
The dispatcher owns verification regardless of which tier produced the code.

### 4. Verification ROI is **orthogonal to coder tier** (empirical)

Codex found **0** issues in Fable's novel DSP but **2** real bugs in the *adjacent
Opus-authored* engine code it re-scanned (dropped panic on ring overflow; wrong
`AVAudioConverter` end-of-stream signal). Confirms the note's core claim from the other
direction: the cheap lever is the verification lens, not a pricier coder. Budget for
multi-lens on every ship-worthy change; do **not** buy correctness by upgrading the
coding tier.

### 5. Cost calibration data point

One "novel-DSP technique discovery + design doc + prototype + 12 tests" unit =
**~157k Fable tokens, ~20 min wall-clock**. Useful for scoping: a Fable exploration
unit is ~150k tokens, so reserve it for work whose blast-radius/novelty clearly clears
the 2× premium — and expect one focused unit, not an open-ended session.
