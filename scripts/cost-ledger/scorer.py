#!/usr/bin/env python3
"""Cost-ledger scorer core — the pure ROI model behind the adaptive lens-router.

Spec: docs/superpowers/specs/2026-07-04-cost-ledger-adaptive-lens-router-spec.md
Rationale for the model + knob values: SCORER-RATIONALE.md (same directory).

This module is deliberately PURE: `propose(history, quarantine)` reads no clock,
touches no file, opens no socket. All ordering derives from the `ts` fields of
the inputs (ISO-8601 UTC strings compare lexicographically), so the same inputs
always yield the same proposals — unit-testable and auditable.

The surrounding machinery (flock, git commit, overrides.json writes, quarantine
lifecycle, shadow sampling) lives OUTSIDE this module (spec §3, §6, §7, §10).
The machinery-facing knobs SHADOW_RATE and QUARANTINE_MULTIPLIER are exported
from here so there is a single source of truth for tuning.

Guardrails (spec §5) enforced here, in code, for arbitrary input:
  - self-pitfall is never proposed for skip (the free floor always runs).
  - A domain whose v0.2 sensitivity level is `very high` or `high` never gets
    any skip proposal. Unknown domains default to `high` (fail-safe).
  - Cold-start: no skip until >= COLD_START_MIN_REAL real (non-shadow) reviews
    of the exact (domain, tier, lens) triple. Tiers never share evidence.
  - One-step: at most one lens dropped per (domain, tier) per proposal set.
  - Quarantine: a triple with a live quarantine entry is never proposed for
    skip; only the tune cycle (under the lock) may clear the entry.
"""

# ---------------------------------------------------------------------------
# Tuning knobs (v1 cold-start heuristics — see SCORER-RATIONALE.md for which
# of these become empirically learnable in v2 once real ledger data accrues).
# ---------------------------------------------------------------------------

# §5.2 — minimum real (non-shadow) reviews of the exact triple before any skip.
# Spec floor: >= 10. v1 sits exactly on the floor.
COLD_START_MIN_REAL = 10

# Evidence decay, implemented as a hard recency window rather than exponential
# weights so the evidence string stays human-auditable (counts, not scores).
# Any surviving finding (real OR shadow) inside the last RECENT_WINDOW records
# of the triple blocks a skip; survivors older than the window stop blocking
# but still count in the all-time rate below.
RECENT_WINDOW = 10

# Skip-confidence threshold: all-time surviving-findings-per-real-review must
# be at or below this. With the recent-window rule, one ancient survivor needs
# >= 20 total reviews (and 10 fresh clean ones) before a skip can re-qualify.
MAX_ALLTIME_SURVIVAL_RATE = 0.05

# §7 — machinery knobs, exported here as the single source of truth.
# Shadow sampling rate for skipped lenses (spec floor: >= 1-in-8).
SHADOW_RATE = 1.0 / 8.0
# Quarantine release requires this multiple of the cold-start sample in fresh
# post-quarantine non-shadow records (spec floor: 3x cold-start).
QUARANTINE_MULTIPLIER = 3
REQUIRED_NON_SHADOW_AFTER_QUARANTINE = QUARANTINE_MULTIPLIER * COLD_START_MIN_REAL

# ---------------------------------------------------------------------------
# Fixed domain -> v0.2 sensitivity level map (from the v0.2 domain table in
# docs/superpowers/specs/2026-07-04-model-routing-domain-axis-design.md).
# Labels are the exact strings the v0.2 classifier emits (spec §3.1).
# The §5.1 high-blast floor is evaluated by LEVEL, never by domain name, and
# an unknown label falls back to "high" so a new classifier label is covered
# (= never skippable) the moment it appears — the safe direction.
# ---------------------------------------------------------------------------

FLOOR_LENS = "self-pitfall"

DOMAIN_SENSITIVITY = {
    "rt-audio": "very high",
    "migration": "high",
    "auth": "high",
    "ui": "medium",
    "format": "low",
    "scaffolding": "low",
}
DEFAULT_SENSITIVITY = "high"  # unknown domain -> fail safe, never skippable
NO_SKIP_LEVELS = frozenset({"very high", "high"})


def sensitivity_level(domain):
    """v0.2 sensitivity level for a domain label; unknown labels fail safe."""
    return DOMAIN_SENSITIVITY.get(domain, DEFAULT_SENSITIVITY)


# ---------------------------------------------------------------------------
# The pure scorer.
# ---------------------------------------------------------------------------

def _survived(record):
    return record.get("survived_synthesis") or 0


def _is_shadow(record):
    return bool(record.get("shadow"))


def _sort_key(record):
    """Order-independent sort key derived ONLY from record content (never input
    position). Two records for the same triple that tie on `ts` must still order
    deterministically, or reordering `history` could move a survivor across the
    recent-window boundary and flip skip eligibility (codex P2). review_id is the
    primary tiebreak; the rest disambiguate a shadow-vs-real pair recorded in the
    same review. Any records still equal after this are byte-identical, hence
    interchangeable — window membership is deterministic in effect."""
    return (
        record.get("ts", ""),
        record.get("review_id", ""),
        int(_is_shadow(record)),
        _survived(record),
        record.get("cost_usd") or 0,
        record.get("findings") or 0,
    )


def propose(history, quarantine):
    """Pure scoring function: ledger history + quarantine -> proposals.

    history:    list of §3.1 ledger records (dicts with ts, review_id, lens,
                domain, tier, cost_usd, findings, max_severity,
                survived_synthesis, and optional shadow flag).
    quarantine: list of entries (dicts with domain, tier, lens,
                quarantined_at_ts, required_non_shadow_count).

    Returns a sorted list of proposals, each
        {"domain", "tier", "lens", "action", "evidence"}
    with action in {"skip", "run"} and evidence a human-readable string of
    counts + cost (no opaque scores). Never proposes a skip that violates a
    §5 guardrail, for any input.
    """
    quarantined = {(q["domain"], q["tier"], q["lens"]) for q in quarantine}

    # Group records by exact triple; order within a triple by a content-derived
    # key (never input position) so the result is order-independent even when
    # timestamps tie. Tiers are never merged (§5.2).
    triples = {}
    for record in history:
        key = (record["domain"], record["tier"], record["lens"])
        triples.setdefault(key, []).append(record)

    proposals = []
    skip_candidates = {}  # (domain, tier) -> [candidate, ...]  (one-step guard)

    for (domain, tier, lens), recs in sorted(triples.items()):
        records = sorted(recs, key=_sort_key)
        if lens == FLOOR_LENS:
            continue  # the free floor is never routed; not even a "run" row

        recent = records[-RECENT_WINDOW:]

        # --- "run" signal: recent shadow runs whose findings survived Stage-4
        # synthesis prove the skipped lens is catching real issues. §7 handles
        # P1/P2 with auto-revert; this also surfaces lower-severity leakage.
        shadow_recent = [r for r in recent if _is_shadow(r)]
        shadow_recent_survived = sum(_survived(r) for r in shadow_recent)
        if shadow_recent_survived > 0:
            proposals.append({
                "domain": domain, "tier": tier, "lens": lens, "action": "run",
                "evidence": (
                    "%d finding(s) from %d recent shadow run(s) survived "
                    "synthesis; the skip is measurably costing real findings"
                    % (shadow_recent_survived, len(shadow_recent))
                ),
            })

        # --- skip eligibility, guardrails first (§5).
        if sensitivity_level(domain) in NO_SKIP_LEVELS:
            continue  # high-blast floor: level-based, covers unknown domains
        if (domain, tier, lens) in quarantined:
            continue  # §7: never re-propose while the entry exists
        real = [r for r in records if not _is_shadow(r)]
        n_real = len(real)
        if n_real < COLD_START_MIN_REAL:
            continue  # §5.2 cold-start, exact triple only

        # --- evidence: recent window must be clean (real AND shadow records),
        # all-time survival rate must clear the confidence threshold.
        recent_survived = sum(_survived(r) for r in recent)
        if recent_survived > 0:
            continue
        survived_total = sum(_survived(r) for r in real)
        if survived_total > MAX_ALLTIME_SURVIVAL_RATE * n_real:
            continue

        cost_total = sum(r.get("cost_usd") or 0 for r in real)
        skip_candidates.setdefault((domain, tier), []).append({
            "domain": domain, "tier": tier, "lens": lens,
            "rate": survived_total / n_real,
            "cost": cost_total,
            "evidence": (
                "%d/%d findings survived synthesis over %d real reviews "
                "(0 survived in last %d records); $%.2f spent"
                % (survived_total, n_real, n_real, len(recent), cost_total)
            ),
        })

    # --- one-step guard (§5.3): drop at most ONE lens per (domain, tier) per
    # proposal set — the worst-ROI candidate (lowest survival rate, then most
    # money spent, then lens name for determinism).
    for (_domain, _tier), candidates in sorted(skip_candidates.items()):
        worst = min(candidates, key=lambda c: (c["rate"], -c["cost"], c["lens"]))
        proposals.append({
            "domain": worst["domain"], "tier": worst["tier"],
            "lens": worst["lens"], "action": "skip",
            "evidence": worst["evidence"],
        })

    proposals.sort(key=lambda p: (p["domain"], p["tier"], p["lens"], p["action"]))
    return proposals
