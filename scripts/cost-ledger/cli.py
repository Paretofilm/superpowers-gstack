#!/usr/bin/env python3
"""Cost-ledger CLI — /cost-ledger commands (spec §8).

Usage:
    python3 cli.py              # status
    python3 cli.py status
    python3 cli.py reset [domain]
    python3 cli.py pause
    python3 cli.py explain <domain>

Every state-mutating command (reset, pause) acquires the exclusive flock
before touching overrides.json / quarantine.json / git.  Read-only commands
(status, explain) use a short timeout — if the lock is held they show
possibly-stale state rather than blocking (spec §3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

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
    git_log,
    LOCK_TIMEOUT_S,
)

_READ_TIMEOUT = 2.0  # seconds; read-only commands skip-on-timeout (stale-ok)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    try:
        with ledger_lock(timeout=_READ_TIMEOUT):
            overrides = read_overrides()
            history = read_history()
            quarantine = read_quarantine()
            state = read_state()
    except TimeoutError:
        print("(lock held; showing possibly-stale state)")
        overrides = read_overrides()
        history = read_history()
        quarantine = read_quarantine()
        state = read_state()

    paused = state.get("paused", False)
    if paused:
        print("STATUS: auto-tuning is PAUSED (measuring, not adjusting)\n")
    else:
        print("STATUS: auto-tuning active\n")

    # Current overrides table.
    active = overrides.get("overrides", [])
    if not active:
        print("No active adjustments (running full lens set for all domains).")
    else:
        print(f"{'Domain':<14} {'Tier':<14} {'Lens':<14} {'Action':<8} Evidence")
        print("-" * 78)
        for o in sorted(active, key=lambda x: (x["domain"], x["tier"], x["lens"])):
            print(
                f"{o['domain']:<14} {o['tier']:<14} {o['lens']:<14} "
                f"{o.get('action','?'):<8} {o.get('evidence','')}"
            )

    # Quarantine summary.
    if quarantine:
        print(f"\nQuarantined triples ({len(quarantine)}):")
        for q in quarantine:
            print(
                f"  {q['domain']}/{q['tier']}/{q['lens']} — quarantined at "
                f"{q['quarantined_at_ts']}, needs {q['required_non_shadow_count']} "
                f"post-quarantine real reviews (trigger: {q.get('trigger_source','?')})"
            )

    # Per-domain ROI table.
    print()
    _print_roi_table(history)
    return 0


def _print_roi_table(history: list[dict]) -> None:
    from collections import defaultdict
    # key: (domain, tier, lens) → {reviews, survived, cost_usd, real_reviews}
    stats: dict[tuple, dict] = defaultdict(lambda: {"reviews": 0, "survived": 0, "cost": 0.0, "real": 0})
    for r in history:
        key = (r.get("domain", "?"), r.get("tier", "?"), r.get("lens", "?"))
        s = stats[key]
        s["reviews"] += 1
        s["survived"] += r.get("survived_synthesis") or 0
        s["cost"] += r.get("cost_usd") or 0.0
        if not r.get("shadow"):
            s["real"] += 1

    if not stats:
        print("No ledger history yet.")
        return

    print(f"{'Domain':<14} {'Tier':<14} {'Lens':<14} {'Real':<6} {'Survived':<10} {'Cost $':<10} {'Rate'}")
    print("-" * 78)
    for key in sorted(stats):
        domain, tier, lens = key
        s = stats[key]
        rate = (s["survived"] / s["real"]) if s["real"] else 0.0
        print(
            f"{domain:<14} {tier:<14} {lens:<14} {s['real']:<6} "
            f"{s['survived']:<10} {s['cost']:<10.2f} {rate:.2%}"
        )

    total_cost = sum(s["cost"] for s in stats.values())
    # Estimated savings: cost of real reviews of skipped lenses (rough proxy).
    print(f"\nTotal spend: ${total_cost:.2f}")


# ---------------------------------------------------------------------------
# reset [domain]
# ---------------------------------------------------------------------------

def cmd_reset(domain: str | None) -> int:
    with ledger_lock():
        ld = _ledger_dir()
        ensure_repo()
        baseline = read_baseline()
        ov_path = ld / "overrides.json"

        if domain:
            # Restore only the overrides for this domain to baseline.
            current = read_overrides()
            baseline_for_domain = [
                o for o in baseline.get("overrides", [])
                if o["domain"] == domain
            ]
            other_domains = [
                o for o in current.get("overrides", [])
                if o["domain"] != domain
            ]
            new_ov = {
                **current,
                "overrides": other_domains + baseline_for_domain,
                "generated_ts": _now(),
            }
            atomic_write(ov_path, new_ov)
            # commit() returns "" on a true no-op (already at baseline) and raises
            # only on a real git failure — so a broken repo/index.lock now fails
            # loud instead of silently leaving routing changed but unaudited (P2).
            commit([ov_path], f"cost-ledger: reset domain '{domain}' to baseline")
            print(f"Reset domain '{domain}' to baseline.")
        else:
            # Full reset to baseline.
            baseline["generated_ts"] = _now()
            atomic_write(ov_path, baseline)
            commit([ov_path], "cost-ledger: full reset to baseline")
            print("Full reset to baseline (all domain adjustments cleared).")

    return 0


# ---------------------------------------------------------------------------
# pause (toggle)
# ---------------------------------------------------------------------------

def cmd_pause() -> int:
    with ledger_lock():
        ld = _ledger_dir()
        state = read_state()
        state_path = ld / "state.json"
        was_paused = state.get("paused", False)
        state["paused"] = not was_paused
        atomic_write(state_path, state)
        if state["paused"]:
            print("Auto-tuning PAUSED. Ledger still measures; adjustments frozen.")
            print("Run `/cost-ledger pause` again to resume.")
        else:
            print("Auto-tuning RESUMED.")
    return 0


# ---------------------------------------------------------------------------
# explain <domain>
# ---------------------------------------------------------------------------

def cmd_explain(domain: str) -> int:
    try:
        with ledger_lock(timeout=_READ_TIMEOUT):
            overrides = read_overrides()
            history = read_history()
            quarantine = read_quarantine()
    except TimeoutError:
        print("(lock held; showing possibly-stale state)")
        overrides = read_overrides()
        history = read_history()
        quarantine = read_quarantine()

    # Current overrides for this domain.
    domain_overrides = [
        o for o in overrides.get("overrides", [])
        if o["domain"] == domain
    ]
    if not domain_overrides:
        print(f"No active adjustments for domain '{domain}' (running full lens set).")
    else:
        print(f"Active adjustments for '{domain}':")
        for o in domain_overrides:
            print(f"  {o['tier']}/{o['lens']}: {o.get('action')} — {o.get('evidence')}")
            if o.get("adjustment_commit"):
                print(f"    commit: {o['adjustment_commit']}")

    # Quarantine entries for this domain.
    domain_q = [q for q in quarantine if q["domain"] == domain]
    if domain_q:
        print(f"\nQuarantined ({len(domain_q)}):")
        for q in domain_q:
            print(
                f"  {q['tier']}/{q['lens']}: quarantined at {q['quarantined_at_ts']}, "
                f"needs {q['required_non_shadow_count']} more real reviews "
                f"(trigger: {q.get('trigger_source','?')})"
            )

    # History for this domain.
    domain_hist = [r for r in history if r.get("domain") == domain]
    if not domain_hist:
        print(f"\nNo ledger records for domain '{domain}' yet.")
    else:
        print(f"\nLedger history for '{domain}' ({len(domain_hist)} records):")
        # Group by (tier, lens).
        from collections import defaultdict
        groups: dict[tuple, list] = defaultdict(list)
        for r in domain_hist:
            groups[(r.get("tier", "?"), r.get("lens", "?"))].append(r)
        for (tier, lens), recs in sorted(groups.items()):
            real = [r for r in recs if not r.get("shadow")]
            shadow = [r for r in recs if r.get("shadow")]
            survived = sum(r.get("survived_synthesis") or 0 for r in real)
            cost = sum(r.get("cost_usd") or 0 for r in real)
            print(
                f"  {tier}/{lens}: {len(real)} real reviews, "
                f"{survived} survived, ${cost:.2f} spent"
                + (f"; {len(shadow)} shadow runs" if shadow else "")
            )

    # Git log entries mentioning this domain.
    log_lines = git_log(domain=domain, n=20)
    if log_lines:
        print(f"\nGit history (mentioning '{domain}'):")
        for line in log_lines:
            print(f"  {line}")

    return 0


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] == "status":
        return cmd_status()
    if args[0] == "reset":
        domain = args[1] if len(args) > 1 else None
        return cmd_reset(domain)
    if args[0] == "pause":
        return cmd_pause()
    if args[0] == "explain":
        if len(args) < 2:
            print("usage: cli.py explain <domain>", file=sys.stderr)
            return 1
        return cmd_explain(args[1])
    print(f"unknown command: {args[0]}", file=sys.stderr)
    print("commands: status, reset [domain], pause, explain <domain>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
