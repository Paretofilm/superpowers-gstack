#!/usr/bin/env python3
"""Unit + property tests for the cost-ledger scorer core (scorer.py).

Stdlib only. Run:  python3 scripts/cost-ledger/test_scorer.py
Prints "PASS (N assertions)" on success; any failure raises AssertionError.

Covers every §9 fixture that concerns the pure scorer, plus a property-style
guardrail sweep over randomized synthetic histories (spec §9: "no input can
produce a below-floor override"). Machinery fixtures (flock concurrency,
shadow-hit auto-revert, correlational fail-safe) belong to the machinery step,
not the pure function, and are not tested here.
"""

import random

from scorer import (
    COLD_START_MIN_REAL,
    DOMAIN_SENSITIVITY,
    FLOOR_LENS,
    MAX_ALLTIME_SURVIVAL_RATE,
    NO_SKIP_LEVELS,
    RECENT_WINDOW,
    REQUIRED_NON_SHADOW_AFTER_QUARANTINE,
    propose,
    sensitivity_level,
)

ASSERTIONS = 0


def check(condition, message):
    global ASSERTIONS
    assert condition, message
    ASSERTIONS += 1


def rec(i, domain="ui", tier="ship-worthy", lens="codex", cost=0.12,
        findings=0, survived=0, shadow=False, sev="none"):
    """One §3.1 ledger record; ts orders by i (lexicographic ISO fraction)."""
    return {
        "ts": "2026-07-04T00:00:00.%06dZ" % i,
        "review_id": "review-%06d" % i,
        "lens": lens, "domain": domain, "tier": tier,
        "cost_usd": cost, "findings": findings,
        "max_severity": sev, "survived_synthesis": survived,
        "shadow": shadow,
    }


def clean_run(n, start=0, **kw):
    """n consecutive clean (zero-survivor) records of one triple."""
    return [rec(start + i, **kw) for i in range(n)]


def skips(proposals):
    return [p for p in proposals if p["action"] == "skip"]


def runs(proposals):
    return [p for p in proposals if p["action"] == "run"]


def triple(p):
    return (p["domain"], p["tier"], p["lens"])


# ---------------------------------------------------------------------------
# Fixture: cold-start per-triple sample floor (§5.2)
# ---------------------------------------------------------------------------

def test_cold_start():
    below = clean_run(COLD_START_MIN_REAL - 1)
    check(skips(propose(below, [])) == [],
          "no skip below the cold-start sample floor")

    at_floor = clean_run(COLD_START_MIN_REAL)
    got = skips(propose(at_floor, []))
    check(len(got) == 1 and triple(got[0]) == ("ui", "ship-worthy", "codex"),
          "skip proposed exactly at the cold-start floor with clean evidence")

    # Shadow records never count toward the cold-start sample.
    mixed = clean_run(7) + clean_run(3, start=7, shadow=True)
    check(skips(propose(mixed, [])) == [],
          "7 real + 3 shadow records must not satisfy the 10-real floor")


# ---------------------------------------------------------------------------
# Fixture: clear-skip with auditable evidence (§4 explainability)
# ---------------------------------------------------------------------------

def test_clear_skip_and_evidence():
    history = clean_run(14, cost=0.12)
    got = skips(propose(history, []))
    check(len(got) == 1, "clear 0/14 history yields exactly one skip")
    p = got[0]
    check(p["action"] == "skip" and triple(p) == ("ui", "ship-worthy", "codex"),
          "skip carries the full (domain, tier, lens) triple")
    check("0/14" in p["evidence"] and "$1.68" in p["evidence"],
          "evidence is human-readable counts + cost, got: %r" % p["evidence"])


# ---------------------------------------------------------------------------
# Fixture: per-tier isolation (§5.2 — ship-worthy evidence never unlocks
# a high-stakes skip)
# ---------------------------------------------------------------------------

def test_per_tier_isolation():
    history = clean_run(25, tier="ship-worthy") + \
        clean_run(3, start=25, tier="high-stakes")
    got = skips(propose(history, []))
    check([triple(p) for p in got] == [("ui", "ship-worthy", "codex")],
          "25 ship-worthy reviews must not unlock a high-stakes skip")

    # The exact same lens+domain at high-stakes needs its own 10-real sample.
    history += clean_run(7, start=28, tier="high-stakes")
    got = skips(propose(history, []))
    tiers = sorted(p["tier"] for p in got)
    check(tiers == ["high-stakes", "ship-worthy"],
          "high-stakes skip unlocks only once ITS triple reaches the floor")


# ---------------------------------------------------------------------------
# Fixture: quarantine honoured (§7 lifecycle — propose only reads)
# ---------------------------------------------------------------------------

def test_quarantine():
    q_entry = {"domain": "ui", "tier": "ship-worthy", "lens": "codex",
               "quarantined_at_ts": "2026-07-04T00:00:00.000050Z",
               "required_non_shadow_count": REQUIRED_NON_SHADOW_AFTER_QUARANTINE}

    # Plenty of clean pre-quarantine evidence + a few post-quarantine records:
    # the entry exists and the post-quarantine count is below required -> no skip.
    history = clean_run(50) + clean_run(5, start=100)
    check(skips(propose(history, [q_entry])) == [],
          "quarantined triple below its post-quarantine count is never re-proposed")

    # Even with the post-quarantine non-shadow count met, propose NEVER skips
    # while the entry exists — clearing the entry is the tune cycle's job
    # (§7: "MUST NOT propose a skip while the entry exists").
    history = clean_run(50) + clean_run(
        REQUIRED_NON_SHADOW_AFTER_QUARANTINE, start=100)
    check(skips(propose(history, [q_entry])) == [],
          "propose never clears quarantine itself, even at the required count")

    # Same evidence without the entry -> the skip comes back.
    check(len(skips(propose(history, []))) == 1,
          "the identical history skips again once the entry is removed")

    # Quarantine of one triple must not shadow-ban its (domain, tier) siblings.
    sibling = clean_run(12, start=200, lens="glm")
    got = skips(propose(history + sibling, [q_entry]))
    check([triple(p) for p in got] == [("ui", "ship-worthy", "glm")],
          "a sibling lens of a quarantined triple stays independently eligible")


# ---------------------------------------------------------------------------
# Fixture: high-blast floor (§5.1 — by LEVEL, for ANY input)
# ---------------------------------------------------------------------------

def test_high_blast_floor():
    for domain in ("rt-audio", "migration", "auth", "totally-unknown-domain"):
        history = []
        for tier in ("ship-worthy", "high-stakes"):
            for lens in ("codex", "glm"):
                history += clean_run(50, start=len(history),
                                     domain=domain, tier=tier, lens=lens)
        check(skips(propose(history, [])) == [],
              "%s (level %s) must never receive a skip proposal, even on "
              "perfect evidence" % (domain, sensitivity_level(domain)))
    check(sensitivity_level("totally-unknown-domain") in NO_SKIP_LEVELS,
          "unknown domains fail safe to a no-skip level")


# ---------------------------------------------------------------------------
# Fixture: one-step move (§5.3 — one lens dropped per (domain, tier))
# ---------------------------------------------------------------------------

def test_one_step_move():
    # Both codex and glm fully qualify for (ui, ship-worthy); only ONE may drop.
    history = clean_run(20, lens="codex", cost=0.10) + \
        clean_run(20, start=20, lens="glm", cost=0.50)
    got = skips(propose(history, []))
    check(len(got) == 1, "only one lens dropped per (domain, tier) per set")
    check(got[0]["lens"] == "glm",
          "tie on survival rate resolves to the costlier lens (worst ROI)")

    # Independent (domain, tier) groups may each drop their own single lens.
    history += clean_run(20, start=40, tier="high-stakes", lens="codex") + \
        clean_run(20, start=60, tier="high-stakes", lens="glm")
    got = skips(propose(history, []))
    check(len(got) == 2 and len({p["tier"] for p in got}) == 2,
          "the one-step guard is per (domain, tier), not global")


# ---------------------------------------------------------------------------
# Fixture: evidence decay (recent window + all-time rate)
# ---------------------------------------------------------------------------

def test_evidence_decay():
    # A surviving finding inside the recent window blocks the skip...
    history = clean_run(13) + [rec(13, survived=2, findings=3, sev="P2")]
    check(skips(propose(history, [])) == [],
          "a recent surviving finding blocks the skip")

    # ...an old survivor stops blocking once RECENT_WINDOW clean records have
    # accrued AND the all-time rate has decayed under the threshold.
    history = [rec(0, survived=1, findings=2, sev="P3")] + clean_run(19, start=1)
    got = skips(propose(history, []))
    check(len(got) == 1 and "1/20" in got[0]["evidence"],
          "one ancient survivor over 20 reviews decays below the 5%% threshold")

    history = [rec(0, survived=1, findings=2, sev="P3")] + clean_run(15, start=1)
    check(skips(propose(history, [])) == [],
          "1/16 all-time (6.3%%) stays above the confidence threshold — no skip")

    # A surviving SHADOW finding in the window also blocks (and asks to run).
    history = clean_run(14) + [rec(14, shadow=True, survived=1, findings=1, sev="P3")]
    proposals = propose(history, [])
    check(skips(proposals) == [],
          "a recent shadow survivor blocks the skip too")
    got_runs = runs(proposals)
    check(len(got_runs) == 1 and got_runs[0]["action"] == "run"
          and "shadow" in got_runs[0]["evidence"],
          "recent shadow survivors produce an explicit run proposal")


# ---------------------------------------------------------------------------
# Fixture: the floor lens is never routed at all
# ---------------------------------------------------------------------------

def test_floor_lens_never_proposed():
    history = clean_run(40, lens=FLOOR_LENS, cost=0.0)
    check(propose(history, []) == [],
          "self-pitfall never appears in proposals, in either direction")


# ---------------------------------------------------------------------------
# Determinism: pure function of inputs, insensitive to input ORDER
# ---------------------------------------------------------------------------

def test_determinism():
    rng = random.Random(42)
    history = clean_run(20) + clean_run(20, start=20, lens="glm") + \
        clean_run(20, start=40, domain="format", lens="codex") + \
        [rec(60, domain="format", survived=1, sev="P2")]
    first = propose(history, [])
    check(first == propose(history, []), "same input -> identical output")
    shuffled = list(history)
    rng.shuffle(shuffled)
    check(first == propose(shuffled, []),
          "record order must not change the proposal set (ts governs)")


# ---------------------------------------------------------------------------
# Property-style guardrail sweep (§9): §5 invariants hold for ARBITRARY input.
# Deterministically seeded from the loop index — reproducible by construction.
# ---------------------------------------------------------------------------

def property_sweep(iterations=300):
    domains = list(DOMAIN_SENSITIVITY) + ["mystery-domain", "llm-eval", ""]
    tiers = ["ship-worthy", "high-stakes"]
    lenses = [FLOOR_LENS, "codex", "glm", "deepseek"]
    skips_seen = 0

    for i in range(iterations):
        rng = random.Random(i)
        # Every third iteration biases toward mostly-clean histories that
        # CONCENTRATE on few triples, so the sweep actually reaches skip
        # proposals (fully random records spread over ~70 triples never hit
        # the per-triple cold-start floor, leaving the skip-side guardrail
        # assertions vacuously true — no skips to check).
        if i % 3 == 0:
            d_pool = [rng.choice(domains), rng.choice(domains)]
            l_pool = ["codex", "glm"]
            survived_pool, shadow_p = [0] * 40 + [1], 0.05
        else:
            d_pool, l_pool = domains, lenses
            survived_pool, shadow_p = [0, 0, 0, 0, 1, 2, 3], 0.3
        history = [
            rec(k,
                domain=rng.choice(d_pool), tier=rng.choice(tiers),
                lens=rng.choice(l_pool), cost=round(rng.random(), 2),
                findings=rng.randint(0, 5),
                survived=rng.choice(survived_pool),
                shadow=rng.random() < shadow_p,
                sev=rng.choice(["none", "P1", "P2", "P3"]))
            for k in range(rng.randint(0, 80))
        ]
        quarantine = [
            {"domain": r["domain"], "tier": r["tier"], "lens": r["lens"],
             "quarantined_at_ts": r["ts"],
             "required_non_shadow_count": REQUIRED_NON_SHADOW_AFTER_QUARANTINE}
            for r in history if rng.random() < 0.1
        ]
        quarantined = {(q["domain"], q["tier"], q["lens"]) for q in quarantine}

        proposals = propose(history, quarantine)
        seen_drops = set()
        for p in proposals:
            if p["action"] != "skip":
                assert p["action"] == "run", "unknown action %r" % p["action"]
                continue
            skips_seen += 1
            # §5.1 floor — by level, for any input
            assert p["lens"] != FLOOR_LENS, "self-pitfall proposed for skip"
            assert sensitivity_level(p["domain"]) not in NO_SKIP_LEVELS, \
                "below-floor skip for %s" % p["domain"]
            # §5.2 cold-start on the exact triple, real records only
            n_real = sum(1 for r in history if not r.get("shadow")
                         and triple(p) == (r["domain"], r["tier"], r["lens"]))
            assert n_real >= COLD_START_MIN_REAL, \
                "skip below cold-start floor (%d real)" % n_real
            # §5.3 one-step per (domain, tier)
            assert (p["domain"], p["tier"]) not in seen_drops, \
                "two lenses dropped for one (domain, tier)"
            seen_drops.add((p["domain"], p["tier"]))
            # §7 quarantine honoured
            assert triple(p) not in quarantined, "skip proposed under quarantine"
            # §4 explainability
            assert p["evidence"] and "$" in p["evidence"], "unauditable evidence"

    # Meta-assertion: the sweep must have exercised the skip path — a sweep
    # that never proposes a skip proves nothing about the skip guardrails.
    check(skips_seen > 0,
          "guardrail sweep produced zero skip proposals — vacuous test")


def test_tied_ts_determinism():
    # codex P2: two records for one triple share a ts on the recent-window
    # boundary, one a survivor. Under an input-index tiebreak, reversing history
    # moves the survivor across the window edge and flips skip eligibility. The
    # content-derived sort key must make the outcome order-independent.
    base = clean_run(9, start=0)               # 9 clean, ts .0..8
    a = rec(9, survived=1, sev="P2")           # survivor at ts=9 (review-000009)
    b = rec(9, survived=0)                      # clean, same ts, distinct review_id
    b["review_id"] = "review-zzzzzz"           # sorts after a by review_id
    tail = clean_run(9, start=10)              # 9 clean, ts 10..18 -> 20 real total
    history = base + [a, b] + tail
    fwd = propose(history, [])
    rev = propose(list(reversed(history)), [])
    check(fwd == rev,
          "tied-ts survivor on the window boundary: proposals must be order-independent")
    check(len(skips(fwd)) == 1,
          "content tiebreak puts the tied survivor outside the recent window -> skip stands")


def main():
    test_cold_start()
    test_clear_skip_and_evidence()
    test_per_tier_isolation()
    test_quarantine()
    test_high_blast_floor()
    test_one_step_move()
    test_evidence_decay()
    test_floor_lens_never_proposed()
    test_determinism()
    test_tied_ts_determinism()
    property_sweep()
    print("PASS (%d assertions)" % ASSERTIONS)


if __name__ == "__main__":
    main()
