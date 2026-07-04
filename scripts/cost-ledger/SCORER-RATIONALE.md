# Scorer rationale — cost-ledger adaptive lens-router (v1)

Spec: `docs/superpowers/specs/2026-07-04-cost-ledger-adaptive-lens-router-spec.md` (§4 "Open").

## The model

**Count-based, windowed-decay heuristic — no opaque scores.** `propose(history, quarantine)`
groups records by exact `(domain, tier, lens)` triple (tiers never share evidence) and
proposes a `skip` only when ALL hold:

1. **Floor (§5.1):** domain's v0.2 sensitivity level is `medium`/`low`. The level is looked
   up from `DOMAIN_SENSITIVITY` (mirrors the v0.2 domain table); **unknown labels default to
   `high`** — a new classifier label is un-skippable until someone classifies it. `self-pitfall`
   is excluded from routing entirely.
2. **Cold-start (§5.2):** ≥ 10 real (non-shadow) reviews of the exact triple.
3. **Recent window clean:** zero surviving findings in the triple's last 10 records —
   shadow records included, so a shadow survivor of any severity blocks re-skipping.
4. **All-time confidence:** surviving findings per real review ≤ 5%.
5. **Not quarantined (§7):** no skip while the entry exists, period — clearing is the tune
   cycle's job (see "ambiguity" below).
6. **One-step (§5.3):** if several lenses qualify for one `(domain, tier)`, only the worst-ROI
   one is proposed (lowest survival rate, then highest spend, then lens name — deterministic).

Additionally, `propose` emits a **`run` proposal** when recent shadow runs produced surviving
findings — §7's auto-revert only fires on P1/P2, so this surfaces P3-level leakage the
machinery can act on. Evidence strings are always counts + dollars (e.g.
`"0/14 findings survived synthesis over 14 real reviews (0 survived in last 10); $1.68 spent"`).

**Why windowed decay instead of exponential weights:** exponential recency weighting produces
fractional scores a human can't audit against the ledger. The window gives the same qualitative
behaviour — old survivors age out once 10 fresh clean reviews accrue AND the all-time rate has
diluted below 5% (one ancient survivor ⇒ ≥ 20 total reviews before re-qualifying) — while the
evidence stays raw counts. Severity is deliberately NOT weighted in v1: any survivor blocks the
window; a severity-weighted score is a v2 candidate once data shows P3 survivors are noise.

## Knob values

| Knob | Value | Spec floor | Basis |
|---|---|---|---|
| `COLD_START_MIN_REAL` | 10 | ≥ 10 | on the floor; no data justifies more yet |
| `RECENT_WINDOW` | 10 | — | = cold-start N: a re-qualify needs a full fresh sample |
| `MAX_ALLTIME_SURVIVAL_RATE` | 0.05 | — | 1 survivor / 20 reviews; stricter than "ever zero" but tolerant of one stale outlier |
| `SHADOW_RATE` | 1/8 | ≥ 1-in-8 | on the floor; machinery knob, exported here as single source |
| `QUARANTINE_MULTIPLIER` | 3 (→ 30 records) | ≥ 3× cold-start | on the floor; machinery knob, exported here |

## Hand-set vs. learnable in v2

**Hand-set forever (guardrails, never learned):** the floor levels, the unknown-domain=`high`
default, one-step, quarantine semantics.

**Hand-set now, learnable in v2 with real ledger data:** `MAX_ALLTIME_SURVIVAL_RATE` (calibrate
against the observed per-lens base rate of surviving findings), `RECENT_WINDOW` (fit to how fast
domain ROI actually drifts), `SHADOW_RATE` (adaptive: decay toward the floor as shadow miss-rate
stays at zero, rise after a shadow hit), `QUARANTINE_MULTIPLIER` (calibrate against observed
post-revert relapse rate), and severity weighting (needs fix-outcome tracking, spec §11).
`COLD_START_MIN_REAL` is pinned to the spec floor and should move only with a spec change.

## Spec ambiguity resolved

§9's fixture wording ("never re-proposed **until** post-quarantine count is met") could be read
as: `propose` may re-propose once the count is met even if the entry is still present. §7's
lifecycle text is stricter: "MUST NOT propose a skip **while the entry exists**". I implemented
the strict reading (entry present ⇒ no skip, even at the required count) — it satisfies both
sentences, keeps `propose` pure, and leaves exactly one mutator (the tune cycle) for the entry.
A test pins this behaviour explicitly.
