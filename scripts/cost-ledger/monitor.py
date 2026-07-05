#!/usr/bin/env python3
"""Cost-ledger escape-defect monitor and auto-revert (spec §7).

check_escapes() detects escape signals (shadow primary; correlational secondary)
and returns a list of reverts to apply.  apply_revert() executes one revert:
git-revert the adjustment commit, re-atomise overrides.json, write the
quarantine entry, and raise a cost-ledger-alert stub.

Both functions are called by tune.run_tune_cycle() under the flock — they do
NOT acquire the lock themselves.
"""
from __future__ import annotations

import json
from pathlib import Path

from ledger import (
    _ledger_dir,
    _now,
    _git,
    _git_silent,
    atomic_write,
    commit,
    read_overrides,
)
from scorer import REQUIRED_NON_SHADOW_AFTER_QUARANTINE


# ---------------------------------------------------------------------------
# Escape detection.
# ---------------------------------------------------------------------------

def check_escapes(
    review_records: list[dict],
    overrides: dict,
    quarantine: list[dict],
    history: list[dict],
) -> list[dict]:
    """Detect escape signals in the current review and return reverts to apply.

    review_records : the §3.1 records just appended for this review (real + shadow).
    overrides      : current overrides dict (from read_overrides()).
    quarantine     : current quarantine list (from read_quarantine()).
    history        : full ledger history (from read_history()).

    Returns a list of revert descriptors:
        {domain, tier, lens, trigger_source, evidence, adjustment_commit}

    Primary signal (§7): shadow run of a skipped lens with a surviving P1/P2.
    Secondary signal (§7, conservative): real surviving P1/P2 in a domain/tier
        with an active skip — only while NO shadow data yet exists for the
        exact (domain, tier, lens) triple, and only once per quarantine period
        (the quarantine lifecycle naturally enforces the cooldown — once a
        correlational revert fires it quarantines the triple, which blocks
        re-skip, which prevents another correlational check until the triple
        has accrued enough shadow data to activate the primary signal).
    """
    # Index active skips by (domain, tier, lens).
    active_skips: dict[tuple, dict] = {}
    for ov in overrides.get("overrides", []):
        if ov.get("action") == "skip":
            key = (ov["domain"], ov["tier"], ov["lens"])
            active_skips[key] = ov

    if not active_skips:
        return []

    # Quarantined triples block re-proposal; also block secondary trigger
    # (triple under quarantine has no active skip anyway, but guard defensively).
    quarantined: set[tuple] = {
        (q["domain"], q["tier"], q["lens"]) for q in quarantine
    }

    reverts: list[dict] = []
    already_flagged: set[tuple] = set()  # prevent double-revert of same triple

    # --- Primary: shadow hit (direct causal evidence, §7 shadow-mode) -----------
    for rec in review_records:
        if not rec.get("shadow"):
            continue
        key = (rec["domain"], rec["tier"], rec["lens"])
        if key not in active_skips or key in already_flagged:
            continue
        survived = rec.get("survived_synthesis") or 0
        severity = rec.get("max_severity", "none")
        if survived > 0 and severity in ("P1", "P2"):
            already_flagged.add(key)
            reverts.append({
                "domain": rec["domain"],
                "tier": rec["tier"],
                "lens": rec["lens"],
                "trigger_source": "shadow",
                "evidence": (
                    f"shadow run found {survived} surviving {severity} finding(s) "
                    f"in review {rec.get('review_id', '?')} — direct proof the skip "
                    f"is costing real findings"
                ),
                "adjustment_commit": active_skips[key].get("adjustment_commit"),
            })

    # --- Secondary: correlational fail-safe (§7 — conservative, bounded) --------
    # For each real surviving P1/P2 in this review, check whether there is an
    # active skip for the same (domain, tier) with no shadow data yet.
    for rec in review_records:
        if rec.get("shadow"):
            continue  # real records only for the correlational trigger
        survived = rec.get("survived_synthesis") or 0
        severity = rec.get("max_severity", "none")
        if survived <= 0 or severity not in ("P1", "P2"):
            continue

        domain = rec["domain"]
        tier = rec["tier"]

        for skip_key, skip_info in active_skips.items():
            skip_domain, skip_tier, skip_lens = skip_key
            if skip_domain != domain or skip_tier != tier:
                continue
            if skip_key in already_flagged or skip_key in quarantined:
                continue

            # Only fire while NO shadow data exists for this triple — once
            # shadow records appear the primary signal governs (§7 cooldown).
            has_shadow_data = any(
                r.get("shadow")
                and r["domain"] == skip_domain
                and r["tier"] == skip_tier
                and r["lens"] == skip_lens
                for r in history
            )
            if has_shadow_data:
                continue

            already_flagged.add(skip_key)
            reverts.append({
                "domain": skip_domain,
                "tier": skip_tier,
                "lens": skip_lens,
                "trigger_source": "correlational",
                "evidence": (
                    f"real {severity} finding survived synthesis in {domain}/{tier} "
                    f"while lens '{skip_lens}' is skipped and no shadow data yet "
                    f"exists for the triple (correlational fail-safe, §7)"
                ),
                "adjustment_commit": skip_info.get("adjustment_commit"),
            })

    return reverts


# ---------------------------------------------------------------------------
# Revert execution (called by tune.run_tune_cycle under the lock).
# ---------------------------------------------------------------------------

def apply_revert(
    domain: str,
    tier: str,
    lens: str,
    trigger_source: str,
    evidence: str,
    adjustment_commit: str | None,
    current_overrides: dict,
    current_quarantine: list[dict],
) -> tuple[dict, list[dict]]:
    """Execute one escape revert; return (new_overrides, new_quarantine).

    Steps (spec §7):
    1. git-revert the offending adjustment commit (or manual removal if no SHA).
    2. Re-atomise overrides.json so unlocked readers see the change immediately.
    3. Write (domain, tier, lens) to quarantine.json.
    4. Raise a cost-ledger-alert stub (integration point for the hook mechanism).

    Called under the flock by run_tune_cycle; must NOT re-acquire the lock.
    """
    ld = _ledger_dir()
    ov_path = ld / "overrides.json"
    q_path = ld / "quarantine.json"
    adj_log = ld / "adjustments.log"

    # Step 1 + 2: remove the skip and create a forward revert commit.
    #
    # Design note: we use a forward commit rather than `git revert <sha>` because
    # the adjustment flow writes overrides.json twice (once with sentinel SHA, once
    # with the real SHA), which makes git-revert produce conflicts when the file
    # has changed between the adjustment commit and now.  A forward commit achieves
    # the same audit-trail goal: git log shows exactly which adjustment was reversed,
    # by whom, and why — and the history is fully auditable without the fragility.
    # `ledger.revert(sha)` remains available as a utility for simple round-trip tests.
    new_overrides = _manual_remove_skip(current_overrides, domain, tier, lens)
    now = _now()
    new_entry: dict = {
        "domain": domain,
        "tier": tier,
        "lens": lens,
        "quarantined_at_ts": now,
        "required_non_shadow_count": REQUIRED_NON_SHADOW_AFTER_QUARANTINE,
        "trigger_source": trigger_source,
    }
    new_quarantine = [
        q for q in current_quarantine
        if not (q["domain"] == domain and q["tier"] == tier and q["lens"] == lens)
    ] + [new_entry]

    # Write quarantine.json BEFORE overrides.json, then commit BOTH together
    # (GLM P2). The reader reads the JSON files directly, so a crash between the
    # writes must not leave "skip removed from overrides but no quarantine entry"
    # — that would let the next cycle immediately re-skip the just-reverted lens.
    # Quarantine-first makes the crash window fail toward "still skipped + already
    # quarantined", which the next escape check simply retries (self-healing). The
    # single commit of both files keeps the audit trail complete (GLM P2 #2).
    atomic_write(q_path, new_quarantine)
    atomic_write(ov_path, new_overrides)
    sha_note = f" (was {adjustment_commit[:8]})" if adjustment_commit else ""
    commit(
        [ov_path, q_path],
        f"revert(cost-ledger): restore {lens} for {domain}/{tier}"
        f"{sha_note} — {trigger_source} escape",
    )

    # Append to adjustments.log.
    log_line = (
        f"{now} | REVERT | {domain}/{tier}/{lens} | "
        f"{trigger_source}: {evidence}\n"
    )
    with open(str(adj_log), "a", encoding="utf-8") as fh:
        fh.write(log_line)

    # Step 4: cost-ledger-alert stub.
    # INTEGRATION POINT: replace this stub with the actual SessionStart-hook
    # or issue-creation mechanism (mirrors model-review issue/hook pattern).
    _raise_alert(domain, tier, lens, trigger_source, evidence)

    return new_overrides, new_quarantine


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------

def _manual_remove_skip(overrides: dict, domain: str, tier: str, lens: str) -> dict:
    """Return a new overrides dict with the (domain, tier, lens) skip removed."""
    new_list = [
        o for o in overrides.get("overrides", [])
        if not (
            o["domain"] == domain and o["tier"] == tier and o["lens"] == lens
            and o.get("action") == "skip"
        )
    ]
    return {**overrides, "overrides": new_list, "generated_ts": _now()}


def _raise_alert(
    domain: str,
    tier: str,
    lens: str,
    trigger_source: str,
    evidence: str,
) -> None:
    """Stub: raise a cost-ledger-alert notification.

    INTEGRATION POINT (§7 step 3): wire this to the SessionStart-hook or
    GitHub-issue mechanism used by check-new-models.py.  For now, write to
    a notices file that a SessionStart hook can surface on the next session.
    """
    ld = _ledger_dir()
    notices_path = ld / "session_notices.txt"
    now = _now()
    msg = (
        f"[{now}] cost-ledger-alert: REVERTED skip of {lens} for "
        f"{domain}/{tier} ({trigger_source} escape). {evidence}. "
        f"Revert: python3 {Path(__file__).resolve().parent / 'cli.py'} reset {domain}\n"
    )
    with open(str(notices_path), "a", encoding="utf-8") as fh:
        fh.write(msg)
    print(msg, end="", flush=True)
