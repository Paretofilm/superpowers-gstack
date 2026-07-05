#!/usr/bin/env python3
"""Cost-ledger auto-tune cycle orchestrator (spec §6 + quarantine lifecycle §7).

run_tune_cycle(review_records) is the single entry point:
    1. Acquire the flock (skip-on-timeout — spec §3).
    2. Read history + quarantine + overrides.
    3. run propose(history, quarantine) from scorer.py.
    4. Apply §5-filtered proposals (atomic_write + git commit + log).
    5. Run check_escapes + apply_revert for each escape found.
    6. Clear quarantine entries whose post-quarantine non-shadow count is met.

Steps 2-6 all run under the single lock.

Integration point §10 point 3: pitfall-verification calls
    tune.run_tune_cycle(review_records)
after calling ledger.append_record() for each lens that ran.
"""
from __future__ import annotations

from ledger import (
    _ledger_dir,
    _now,
    ledger_lock,
    atomic_write,
    commit,
    ensure_repo,
    read_history,
    read_quarantine,
    read_overrides,
    read_baseline,
    read_state,
)
from scorer import propose, sensitivity_level, NO_SKIP_LEVELS, FLOOR_LENS
from monitor import check_escapes, apply_revert


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------

def run_tune_cycle(review_records: list[dict]) -> None:
    """Run one complete tune cycle under the exclusive flock.

    Skips tuning (but does NOT error) if the lock cannot be acquired within
    the timeout — the records are already written; the next review will tune
    on fuller history (spec §3).

    review_records: the §3.1 ledger records just appended for this review
        (real + shadow).  Passed through to check_escapes for escape detection
        on the freshest data.
    """
    try:
        with ledger_lock():
            _run_locked(review_records)
    except TimeoutError:
        # Clean skip — another session holds the lock; our record is written.
        pass


# ---------------------------------------------------------------------------
# Locked section (all reads + writes happen here).
# ---------------------------------------------------------------------------

def _run_locked(review_records: list[dict]) -> None:
    ld = _ledger_dir()
    ensure_repo()

    # Check paused flag first (still run escape check even when paused).
    state = read_state()
    paused = state.get("paused", False)

    history = read_history()
    quarantine = read_quarantine()
    # Snapshot the overrides that were ACTIVE when review_records was produced
    # (dispatch time). Escape attribution must use these, not the post-tune
    # overrides — else a `run` proposal could remove a skip before its shadow-hit
    # is seen (missing the required quarantine), and a skip added THIS cycle could
    # be falsely reverted by a same-review correlational finding it never gated
    # (codex P1). So: escape check FIRST, against dispatch overrides.
    overrides = read_overrides()

    # --- Escape check + auto-revert (always, even when paused), vs dispatch state ---
    escapes = check_escapes(review_records, overrides, quarantine, history)
    for esc in escapes:
        overrides, quarantine = apply_revert(
            domain=esc["domain"],
            tier=esc["tier"],
            lens=esc["lens"],
            trigger_source=esc["trigger_source"],
            evidence=esc["evidence"],
            adjustment_commit=esc.get("adjustment_commit"),
            current_overrides=overrides,
            current_quarantine=quarantine,
        )

    # --- Tune: propose + apply (skip if paused). Runs AFTER escape reverts, so
    #     propose() sees any just-written quarantine and won't re-skip it. ---
    if not paused:
        proposals = propose(history, quarantine)
        overrides, quarantine = _apply_proposals(proposals, overrides, quarantine, ld)

    # --- Quarantine lifecycle: clear entries that have accrued enough
    #     post-quarantine non-shadow reviews (spec §7 lifecycle) ---
    quarantine = _advance_quarantine(quarantine, history, ld)


# ---------------------------------------------------------------------------
# Proposal application (§5-filtered + one-step guard).
# ---------------------------------------------------------------------------

def _apply_proposals(
    proposals: list[dict],
    overrides: dict,
    quarantine: list[dict],
    ld,
) -> tuple[dict, list[dict]]:
    """Apply scorer proposals that survive the machinery-level §5 guard.

    The scorer already enforces §5 internally, but the machinery adds one
    extra guard: if another session has ALREADY committed a skip for the same
    (domain, tier) since the current session's lock acquisition, block a
    second drop (spec §5.3 — the one-step guard is evaluated against the
    committed overrides read at lock-acquisition time).
    """
    ov_path = ld / "overrides.json"
    adj_log = ld / "adjustments.log"

    # Index current overrides by triple.
    current_by_triple: dict[tuple, dict] = {
        (o["domain"], o["tier"], o["lens"]): o
        for o in overrides.get("overrides", [])
    }

    # Count existing skips per (domain, tier) for the one-step guard.
    skips_per_dt: dict[tuple, int] = {}
    for o in overrides.get("overrides", []):
        if o.get("action") == "skip":
            dt = (o["domain"], o["tier"])
            skips_per_dt[dt] = skips_per_dt.get(dt, 0) + 1

    changed = False
    now = _now()
    new_override_list = list(overrides.get("overrides", []))
    new_skip_triples: list[tuple] = []  # triples added this cycle (for log + notice)

    for prop in proposals:
        domain, tier, lens, action = (
            prop["domain"], prop["tier"], prop["lens"], prop["action"]
        )
        dt_key = (domain, tier)

        # --- §5 floor guards (defense-in-depth: overrides.json is the hot
        #     routing input, so a bad/stale proposal must never reach it even
        #     though the pure scorer already filters these) ---
        if action == "skip" and lens == FLOOR_LENS:
            continue  # the free floor lens is never skippable (codex P2)
        if action == "skip" and sensitivity_level(domain) in NO_SKIP_LEVELS:
            continue  # §5.1 high-blast floor, by level

        # --- One-step guard (§5.3 machinery-level) ---
        if action == "skip" and skips_per_dt.get(dt_key, 0) >= 1:
            # Already a skip committed for this (domain, tier) in this cycle.
            continue

        if action == "skip":
            # Add or replace the entry.  adjustment_commit is filled in after
            # the git commit; using a sentinel here avoids a second commit.
            new_override_list = [
                o for o in new_override_list
                if not (o["domain"] == domain and o["tier"] == tier and o["lens"] == lens)
            ]
            new_override_list.append({
                "domain": domain,
                "tier": tier,
                "lens": lens,
                "action": "skip",
                "evidence": prop["evidence"],
                "adjustment_commit": "",  # back-filled below after commit
                "generated_ts": now,
                # The scorer only proposes a skip once the triple has cleared the
                # cold-start sample, so a tune-written skip is cold-start-met by
                # construction. gate honors ONLY overrides carrying this flag, so a
                # hand-edited overrides.json (no flag) can't bypass cold-start (GLM P2).
                "cold_start_met": True,
            })
            skips_per_dt[dt_key] = skips_per_dt.get(dt_key, 0) + 1
            new_skip_triples.append((domain, tier, lens, prop["evidence"]))
            changed = True

        elif action == "run":
            # Remove any skip for this triple (shadow-hit "run" proposal).
            before = len(new_override_list)
            new_override_list = [
                o for o in new_override_list
                if not (o["domain"] == domain and o["tier"] == tier and o["lens"] == lens)
            ]
            if len(new_override_list) != before:
                changed = True

    if not changed:
        return overrides, quarantine

    # Write overrides (with sentinel SHA) + log; commit; back-fill SHA atomically.
    # The sentinel ensures the file is always valid JSON before the commit.
    # After the commit, we back-fill the SHA with a second atomic_write.
    # The working tree becomes dirty relative to that commit, but subsequent
    # operations always commit the current file state (git add picks it up).
    new_overrides = {
        "version": 1,
        "generated_ts": now,
        "overrides": new_override_list,
    }
    atomic_write(ov_path, new_overrides)

    log_lines: list[str] = []
    for domain, tier, lens, evidence in new_skip_triples:
        log_lines.append(
            f"{now} | skip | {domain}/{tier}/{lens} | {evidence}"
        )
    with open(str(adj_log), "a", encoding="utf-8") as fh:
        for line in log_lines:
            fh.write(line + "\n")

    sha = commit(
        [ov_path, adj_log],
        _build_commit_msg(new_skip_triples, now),
    )

    # Back-fill adjustment_commit with the real SHA (in-memory + atomic_write).
    # This write is NOT followed by another commit; the SHA is informational
    # for the /cost-ledger explain command — it is NOT used for git-revert in
    # apply_revert (which uses a forward commit for clean audit trail).
    for entry in new_override_list:
        if entry.get("adjustment_commit") == "":
            entry["adjustment_commit"] = sha
    new_overrides["overrides"] = new_override_list
    atomic_write(ov_path, new_overrides)

    # SessionStart notice stub (one line per new skip).
    _emit_session_notice(new_skip_triples, sha, ld)

    return new_overrides, quarantine


def _build_commit_msg(new_skip_triples: list[tuple], ts: str) -> str:
    if not new_skip_triples:
        return f"cost-ledger: apply proposals ({ts})"
    parts = [f"skip {lens} for {domain}/{tier}" for domain, tier, lens, _ in new_skip_triples]
    return f"cost-ledger: {', '.join(parts)}"


def _emit_session_notice(new_skip_triples: list[tuple], sha: str, ld) -> None:
    """Write one-line notices to session_notices.txt for the next SessionStart.

    INTEGRATION POINT: a SessionStart hook should read and clear this file
    (mirrors the check-plugin-version.sh pattern from hooks/hooks.json).
    """
    notices_path = ld / "session_notices.txt"
    now = _now()
    with open(str(notices_path), "a", encoding="utf-8") as fh:
        for domain, tier, lens, evidence in new_skip_triples:
            msg = (
                f"[{now}] cost-ledger: downgraded {lens} for "
                f"{domain}/{tier} ({evidence}); "
                f"revert: python3 <plugin>/scripts/cost-ledger/cli.py reset {domain}\n"
            )
            fh.write(msg)


# ---------------------------------------------------------------------------
# Quarantine lifecycle (§7 step 2 — the tune cycle is the sole mutator).
# ---------------------------------------------------------------------------

def _advance_quarantine(
    quarantine: list[dict],
    history: list[dict],
    ld,
) -> list[dict]:
    """Remove quarantine entries whose post-quarantine non-shadow count is met.

    For each entry, count non-shadow records with ts > quarantined_at_ts for
    the exact triple.  Once that count reaches required_non_shadow_count, the
    entry is removed — reopening the triple to normal cold-start evaluation.
    """
    q_path = ld / "quarantine.json"
    remaining = []
    changed = False

    for q in quarantine:
        d, t, l = q["domain"], q["tier"], q["lens"]
        at_ts = q["quarantined_at_ts"]
        required = q["required_non_shadow_count"]

        post_count = sum(
            1
            for r in history
            if r["domain"] == d and r["tier"] == t and r["lens"] == l
            and not r.get("shadow")
            and r.get("ts", "") > at_ts
        )

        if post_count >= required:
            changed = True  # quarantine entry cleared; don't append
        else:
            remaining.append(q)

    if changed:
        atomic_write(q_path, remaining)
        # Commit the clear so the audit trail is complete — a git log in
        # LEDGER_DIR must show quarantine lifecycle events, not only override
        # changes, or `git reset --hard` would silently restore stale quarantine
        # state (GLM P2 #2).
        commit([q_path], "cost-ledger: clear quarantine entries at required count")

    return remaining
