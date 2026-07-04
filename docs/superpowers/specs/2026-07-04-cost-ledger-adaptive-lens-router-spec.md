# Cost-ledger — adaptive lens-router (implementation spec)

> **Status:** spec, 2026-07-04. Gates the Fable-spawn for Phase 4's ambitious
> cost-ledger. Design decisions locked in `../plans/2026-07-03-system-review-remediation.md`
> (Fase 4 section). This spec pins the *interface + guardrails* precisely so the
> Fable run stays bounded (open-on-approach for the ROI model, bounded-on-deliverable
> for everything the routing and safety layers touch).

## 1. Purpose

The multi-lens verification chain (self-pitfall → Codex → third house) runs a fixed
lens set per change-tier. But lens value is **domain-dependent**: on plain UI work,
Codex/GLM routinely find nothing that survives adversarial synthesis, yet still cost
tokens + latency; on RT-audio/migration/auth work they earn their keep. Today that
mismatch is invisible and static.

The cost-ledger measures per-review lens ROI, learns which lenses pay off per domain,
and **auto-adjusts the verification depth per domain** — bounded, informed, reversible,
and monitored. It is a closed-loop adaptive controller with a supervisory safety layer.

**In scope (v1):** measure lens ROI; learn a per-domain lens-gate recommendation;
apply it via a user-global override layer; monitor for escaped defects and auto-revert.

**Out of scope (v1, → v2):** tracking whether a finding was actually *fixed* (needs an
outcome-tracking subsystem); tuning the *coding* tier (this tunes verification depth
only, never the coder — coder tier stays governed by v0.2 domain-sensitivity); any
cross-user/shared learning (data is user-local).

## 2. What auto-tuning targets (and what it must never touch)

The multi-lens tier-gate today (from `pitfall-verification`):

| Tier | Lenses |
|------|--------|
| Trivial | self-pitfall |
| Ship-worthy | self-pitfall + Codex |
| High-stakes | self-pitfall + Codex + third house (GLM) |

Auto-tuning adjusts **which external lenses run for a given (domain, tier)** — nothing
else. It never touches: the base coder tier, the domain-sensitivity → coder-tier map
(v0.2), or `self-pitfall` (the free floor always runs).

## 3. Storage — user-global override layer

All ledger state lives under `~/.claude/cost-ledger/` (NOT in the plugin repo — the
shipped `model-routing.md` stays pristine, so lint E8 remains valid and the shared
baseline is untouched). Layout:

```
~/.claude/cost-ledger/
  ledger.jsonl          # append-only: one ROI record per lens per review
  overrides.json        # the current learned adjustments (read by routing)
  quarantine.json       # (domain, tier, lens) pairs barred from re-skip + until-sample
  baseline.json         # the human baseline the overrides layer on top of; reset target
  .lock                 # flock target serializing the propose→write→commit section
  .git/                 # each auto-adjustment is a commit here (informed + reversible)
  adjustments.log       # human-readable rationale trail (mirrors the git log)
```

`~/.claude/cost-ledger/` is its own git repo so `git revert` reverses a single
adjustment and the commit history *is* the audit trail. `overrides.json` is the only
file routing reads at decision time.

**Concurrency (fixed — the user runs many parallel sessions).** Appending one record
to `ledger.jsonl` uses a single `O_APPEND` write (atomic for these small lines).
Everything else — reading history, running `propose`, rewriting `overrides.json` /
`quarantine.json`, and the `git commit` — MUST hold an exclusive `flock` on `.lock`
for the whole critical section. A session that cannot acquire the lock within a short
timeout skips tuning for that review (it still appended its record; the next review
tunes on the fuller history). This makes the write path atomic and prevents lost
overrides and Git index-lock failures. Fable must implement this lock, not assume
single-writer.

### 3.1 Ledger record (minimum tuple — the ROI signal)

One JSONL line appended per lens per review:

```json
{"ts":"2026-07-04T19:00:00Z","review_id":"<uuid>","lens":"codex|glm|self-pitfall",
 "domain":"ui|rt-audio|migration|auth|format|...","tier":"ship-worthy|high-stakes",
 "cost_usd":0.12,"findings":3,"max_severity":"P1|P2|P3|none","survived_synthesis":2}
```

`survived_synthesis` = count of this lens's findings that survived the Stage-4
adversarial synthesis (the strong "real finding" proxy). `domain` is the change's
domain-sensitivity classification — it MUST be one of the **exact labels the v0.2
classifier emits** (the single source; do not invent or rename labels here). Its
sensitivity level (`very high | high | medium | low`) is looked up from the v0.2
domain table, and that level — not any hand-copied domain list — defines the
high-blast floor in §5. `shadow` (bool) marks a record produced by a shadow run (§7).

### 3.2 Overrides format (read by routing)

```json
{"version":1,"generated_ts":"...","overrides":[
  {"domain":"ui","tier":"ship-worthy","lens":"codex","action":"skip",
   "evidence":"0/14 findings survived synthesis over 14 reviews; $1.68 spent",
   "adjustment_commit":"<sha>"}
]}
```

`action` ∈ {`skip`, `run`}. Only lenses ABOVE the floor may be set to `skip` (§5).

## 4. The ROI model — the Fable boundary

**Fixed (spec pins this — bounded-on-deliverable):**
- The signature: `propose(history, quarantine) -> proposals`. `history` = parsed
  `ledger.jsonl`; `quarantine` = parsed `quarantine.json` (§7). The scorer MUST NOT
  propose a `skip` for any `(domain, tier, lens)` still under quarantine — without
  this input the escape/quarantine loop cannot converge (a revert would see the same
  low-ROI history and re-propose the same skip immediately).
- The output contract: a set of `{domain, tier, lens, action, evidence}` proposals,
  each keyed by the full `(domain, tier, lens)` triple and respecting §5.
- Determinism/explainability requirement: every proposal MUST carry human-readable
  `evidence` (counts + cost) — no opaque scores that a human can't audit. `propose`
  is a pure function of its inputs (no clock/network) so it is unit-testable.

**Open (Fable discovers this — open-on-approach):**
- The *scoring model* that turns ledger history into a per-(domain, tier, lens)
  keep/skip decision: how to weight cost vs surviving-findings vs recency vs sample
  size; the minimum sample before any proposal (cold-start guard); the confidence
  threshold to propose a `skip`; how to decay old evidence. This is the empirical
  core — it must be discovered from the shape of real ledger data, not specced a
  priori. That is precisely why it clears the Fable bar.

Fable delivers: the scorer (as a testable pure function `propose(history) -> proposals`),
its unit tests against synthetic ledger fixtures, and a short rationale for the model
it converged on.

## 5. Guardrails (fixed — never discovered, never overridden)

1. **Floor.** `self-pitfall` always runs (free). A domain whose v0.2 sensitivity level
   is `very high` or `high` may NEVER have any external lens set to `skip` — the
   eligibility test is the *looked-up level*, not a hand-copied domain list, so a new
   `high` domain (e.g. anything the classifier tags auth/payments/security) is covered
   the moment the classifier emits it. Overrides only ever *reduce* lenses on
   `medium`/`low` domains, never below the human baseline.
2. **Cold-start.** No `skip` proposal for a `(domain, tier, lens)` until a minimum
   sample **of that exact triple** (Fable picks the number; spec floor: ≥ 10 real —
   non-shadow — reviews of that triple). Ship-worthy evidence never unlocks a
   high-stakes skip. Below the sample, run everything.
3. **One-step moves.** An adjustment may only drop ONE lens per (domain, tier) per
   run — never collapse straight to self-pitfall-only in one step.
4. **Bounded blast.** Overrides only ever change lens *selection*. They can never edit
   `model-routing.md`, the coder tier, or disable a guardrail.

## 6. Auto-tune cycle

1. After each multi-lens review, append the per-lens records to `ledger.jsonl`.
2. Run `propose(history)`; filter through §5 guardrails.
3. For each surviving proposal: update `overrides.json`, append to `adjustments.log`,
   and `git commit` in `~/.claude/cost-ledger/` with a message that states the
   domain, lens, action, and evidence.
4. Surface the change (component #2 "informed"): a one-line notice at the next
   session start (reuse the existing SessionStart-hook pattern) — "cost-ledger
   downgraded Codex for UI (0/14 survived); revert: `/cost-ledger reset ui`".

## 7. Escape-defect monitor + auto-revert (the safety layer)

A skipped lens never runs, so a later P1 found by another lens does **not** prove the
skipped lens would have caught it — attributing every surviving finding in a
downgraded domain to the skip creates false reverts driven by unrelated defects. So
the **primary** escape signal is direct measurement, not correlation:

**Shadow-mode (primary — sound).** When a lens is `skip`ped for a `(domain, tier)`,
still run it for real on a sampled fraction of those reviews (Fable picks the rate;
spec floor: ≥ 1-in-8), WITHOUT gating the outcome on it — its findings never block the
change; they are only recorded (`shadow:true`). Shadow records give a *direct*,
causal miss-rate: if the shadowed lens produces findings that survive synthesis, the
skip is measurably costing real findings. This buys back a fraction of the savings —
that is the honest price of knowing the true miss rate rather than guessing it.

**Escape trigger.** Auto-revert a `(domain, tier, lens)` skip when EITHER:
- (primary) a **shadow run** of that lens produces a surviving P1/P2 — direct proof; or
- (secondary, conservative) a real surviving P1/P2 appears in that domain — a weaker
  correlational signal, kept only as a fail-safe and logged as such (it may over-revert;
  over-reverting toward more thorough routing is safe).

Response (**auto-revert, not alert-only — fail-safe**):
1. `git revert` the offending adjustment commit + regenerate `overrides.json` (restore
   the fuller lens set).
2. Write the `(domain, tier, lens)` to `quarantine.json` with an `until_sample` count:
   no further `skip` proposal for that triple until a much larger NON-shadow sample
   accrues (Fable picks the multiplier; spec floor: 3× cold-start). `propose` receives
   `quarantine.json` (§4) and MUST honour it — this is what stops the
   skip→escape→revert→skip oscillation.
3. Raise a `cost-ledger-alert` (reuse the model-review issue/hook mechanism): which
   triple, whether the trigger was a shadow hit (primary) or a correlational fail-safe
   (secondary), and the evidence.

The default state is always the safer (fuller-lens) routing; the system never waits on
the human to be safe. The human is informed of both the adjustment and the
self-correction.

## 8. Commands (`/cost-ledger`)

- `/cost-ledger` — status: current overrides, per-domain lens ROI table, total spend +
  estimated savings.
- `/cost-ledger reset [domain]` — restore baseline (all, or one domain) in one action.
- `/cost-ledger explain <domain>` — the evidence + git history behind a domain's
  current routing.
- `/cost-ledger pause` — freeze auto-tuning (keep measuring, stop adjusting).

## 9. Verification plan

- Fable's scorer ships with unit tests against synthetic ledger fixtures: cold-start
  (per-triple sample floor); clear-skip; per-tier isolation (ship-worthy evidence must
  not unlock a high-stakes skip); quarantine honoured in `propose` (a quarantined
  triple is never re-proposed until `until_sample`); shadow-hit → revert; correlational
  fail-safe → revert; high-blast-floor respected (no `very high`/`high` domain skip for
  any input). Plus a concurrency test: two writers contending on `.lock` never lose an
  override or corrupt `overrides.json`.
- The whole subsystem is **high-stakes** (it mutates routing): after Fable, run the
  multi-lens chain (self-pitfall + Codex + GLM) on the patched artifact, adversarial
  synthesis, then the release gate (lint green, version bump + CHANGELOG).
- A guardrail regression suite asserts §5 invariants hold for arbitrary ledger inputs
  (property-style: no input can produce a below-floor override).

## 10. Integration points (who reads/writes, and when)

`pitfall-verification` owns lens dispatch AND Stage-4 synthesis, so it is the single
integration surface. The cost-ledger is consulted and fed at three precise moments:

1. **Tier-gate read (before dispatch).** When `pitfall-verification` classifies a
   change as ship-worthy/high-stakes and is about to dispatch Codex/GLM, it first reads
   `overrides.json` for this change's `(domain, tier)`. An active `skip` for a lens
   means: do not gate on that lens. If that skipped lens is selected for a shadow run
   (§7 sampling), dispatch it anyway but mark its result non-gating.
2. **Ledger write (after synthesis).** Records are appended only AFTER Stage-4
   adversarial synthesis completes, because `survived_synthesis` is not known before
   it. One record per lens that ran (real or shadow), with the fields in §3.1.
3. **Tune + escape check (after write, under the `.lock`).** With the lock held: run
   `propose(history, quarantine)`, apply §5-filtered proposals (commit + notify), and
   run the §7 escape check (shadow-hit primary, correlational fail-safe secondary)
   with auto-revert. If the lock can't be acquired quickly, skip tuning this cycle
   (the record is already written; the next review tunes on fuller history).

Everything the ledger does hangs off `pitfall-verification`; no other skill writes or
reads it. If `pitfall-verification` did not run (trivial tier), the ledger is inert for
that change.

## 11. Non-goals / v2

- Fix-outcome tracking (did the finding get fixed?) — richer ROI signal, deferred.
- Cross-user / shared learning — data stays user-local.
- Tuning the coder tier — out of scope; verification depth only.
