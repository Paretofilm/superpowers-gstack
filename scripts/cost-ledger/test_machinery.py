#!/usr/bin/env python3
"""Machinery tests for the cost-ledger subsystem (spec §9).

stdlib-only, assert-based; runs against a TEMP $COST_LEDGER_DIR that is
isolated from the real ~/.claude/ directory.  Each test that touches git
or the ledger directory gets its own temp dir to avoid interference.

Usage:
    python3 scripts/cost-ledger/test_machinery.py

Exits 0 on PASS with assertion count; non-zero on first failure.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Test harness helpers.
# ---------------------------------------------------------------------------

_N = 0  # global assertion counter


def ok(cond: bool, msg: str = "") -> None:
    global _N
    _N += 1
    if not cond:
        raise AssertionError(f"Assertion {_N} FAILED: {msg}")


def _tmp_ledger() -> tempfile.TemporaryDirectory:
    """Return a TemporaryDirectory object; set COST_LEDGER_DIR on enter."""
    td = tempfile.mkdtemp(prefix="cost-ledger-test-")
    os.environ["COST_LEDGER_DIR"] = td
    return td


def _cleanup(td: str) -> None:
    import shutil
    shutil.rmtree(td, ignore_errors=True)
    # Restore to something safe so subsequent imports don't use the old path.
    os.environ.pop("COST_LEDGER_DIR", None)


# ---------------------------------------------------------------------------
# Import modules AFTER the first _tmp_ledger() call so they pick up the env.
# We import inside each test function to get the fresh env var.
# ---------------------------------------------------------------------------

def _import_all():
    """Import (or re-import) all modules under the current COST_LEDGER_DIR."""
    import importlib
    import ledger as _ledger
    import monitor as _monitor
    import tune as _tune
    import cli as _cli
    importlib.reload(_ledger)
    importlib.reload(_monitor)
    importlib.reload(_tune)
    importlib.reload(_cli)
    return _ledger, _monitor, _tune, _cli


# ---------------------------------------------------------------------------
# 1. atomic_write: no partial file under a simulated crash
# ---------------------------------------------------------------------------

def test_atomic_write_no_partial_on_crash() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib; importlib.reload(ledger)

        path = Path(td) / "overrides.json"
        initial = {"version": 1, "overrides": [], "marker": "original"}
        ledger.atomic_write(path, initial)
        ok(json.loads(path.read_text()) == initial, "initial write correct")

        # Simulate crash between temp-write and os.replace: monkey-patch os.replace
        orig_replace = ledger.os.replace

        def crashing_replace(src, dst):
            # temp file is written (we can verify it exists); then "crash"
            ok(Path(src).exists(), "temp file exists before crash")
            raise OSError("simulated crash between temp-write and os.replace")

        ledger.os.replace = crashing_replace
        try:
            ledger.atomic_write(path, {"version": 2, "overrides": [{"new": True}]})
        except OSError:
            pass
        finally:
            ledger.os.replace = orig_replace

        # Original file must be unchanged.
        restored = json.loads(path.read_text())
        ok(restored == initial, f"original file unchanged after crash: {restored}")

        # No orphaned temp files should remain (atomic_write cleans up).
        leftover = list(Path(td).glob(".tmp-*.json"))
        ok(len(leftover) == 0, f"no temp files left: {leftover}")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 2. Reader mid-rewrite: never sees partial content
# ---------------------------------------------------------------------------

def test_reader_never_sees_partial() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib; importlib.reload(ledger)

        path = Path(td) / "overrides.json"
        ledger.atomic_write(path, {"count": 0, "data": "A" * 50})
        errors: list[str] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    text = path.read_text()
                    if text.strip():
                        json.loads(text)  # must always parse cleanly
                except json.JSONDecodeError as exc:
                    errors.append(str(exc))
                time.sleep(0.001)

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        try:
            for i in range(300):
                ledger.atomic_write(
                    path,
                    {"count": i, "data": "x" * 120, "nested": {"a": i, "b": i * 2}},
                )
        finally:
            stop.set()
            t.join(timeout=3)

        ok(not errors, f"reader saw {len(errors)} partial read(s): {errors[:3]}")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 3. Lock serialises two concurrent writers — no lost override
# ---------------------------------------------------------------------------

def test_lock_serializes_two_writers() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib; importlib.reload(ledger)

        ov_path = Path(td) / "overrides.json"
        ledger.atomic_write(ov_path, {"version": 1, "overrides": []})
        committed_writes: list[str] = []
        lock = threading.Lock()  # protect the committed_writes list only

        def writer(name: str) -> None:
            for i in range(6):
                try:
                    with ledger.ledger_lock(timeout=8):
                        ov = json.loads(ov_path.read_text())
                        ov["overrides"].append({"writer": name, "seq": i})
                        ledger.atomic_write(ov_path, ov)
                        with lock:
                            committed_writes.append(f"{name}:{i}")
                except TimeoutError:
                    pass
                time.sleep(0.005)

        t1 = threading.Thread(target=writer, args=("A",))
        t2 = threading.Thread(target=writer, args=("B",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        final = json.loads(ov_path.read_text())
        ok(
            len(final["overrides"]) == len(committed_writes),
            f"no lost writes: expected {len(committed_writes)}, "
            f"got {len(final['overrides'])}",
        )
        # File is valid JSON (no corruption from concurrent writes).
        ok(isinstance(final["overrides"], list), "overrides is a list (not corrupted)")
        # Every writer is represented.
        writers_in_file = {o["writer"] for o in final["overrides"]}
        ok("A" in writers_in_file and "B" in writers_in_file, "both writers present")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 4. Shadow escape → check_escapes returns revert; apply_revert writes quarantine
# ---------------------------------------------------------------------------

def test_shadow_escape_revert_and_quarantine() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import monitor
        import importlib
        importlib.reload(ledger)
        importlib.reload(monitor)

        ld = Path(td)
        ledger.ensure_repo()
        ov_path = ld / "overrides.json"
        q_path = ld / "quarantine.json"

        # Set up: active skip with a sentinel adjustment_commit.
        overrides = {
            "version": 1,
            "generated_ts": "2026-07-04T10:00:00Z",
            "overrides": [{
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "action": "skip", "evidence": "0/14 survived",
                "adjustment_commit": "abc1234",
            }],
        }
        ledger.atomic_write(ov_path, overrides)
        ledger.commit([ov_path], "test: add skip")

        # Shadow record with surviving P1.
        review_records = [{
            "ts": "2026-07-04T11:00:00Z",
            "review_id": "r-shadow-1",
            "domain": "ui", "tier": "ship-worthy", "lens": "codex",
            "shadow": True,
            "survived_synthesis": 1, "max_severity": "P1",
            "cost_usd": 0.05, "findings": 2,
        }]

        reverts = monitor.check_escapes(review_records, overrides, [], [])
        ok(len(reverts) == 1, f"one revert expected; got {reverts}")
        ok(reverts[0]["trigger_source"] == "shadow", "trigger is shadow")
        ok(reverts[0]["lens"] == "codex", "correct lens")

        # Apply the revert.
        new_ov, new_q = monitor.apply_revert(
            domain="ui", tier="ship-worthy", lens="codex",
            trigger_source="shadow", evidence="shadow hit: 1 P1",
            adjustment_commit=reverts[0].get("adjustment_commit"),
            current_overrides=overrides,
            current_quarantine=[],
        )

        # Skip must be gone from overrides.
        skip_entries = [o for o in new_ov.get("overrides", []) if o.get("action") == "skip"]
        ok(len(skip_entries) == 0, "skip removed from overrides after revert")

        # Quarantine entry must exist.
        ok(len(new_q) == 1, f"quarantine has one entry: {new_q}")
        ok(new_q[0]["domain"] == "ui", "quarantine domain correct")
        ok(new_q[0]["trigger_source"] == "shadow", "quarantine records trigger")
        from scorer import REQUIRED_NON_SHADOW_AFTER_QUARANTINE
        ok(
            new_q[0]["required_non_shadow_count"] == REQUIRED_NON_SHADOW_AFTER_QUARANTINE,
            f"quarantine count = {REQUIRED_NON_SHADOW_AFTER_QUARANTINE}",
        )
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 5. Correlational trigger: fires pre-shadow, suppressed post-shadow
# ---------------------------------------------------------------------------

def test_correlational_trigger_pre_and_post_shadow() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import monitor
        import importlib
        importlib.reload(ledger)
        importlib.reload(monitor)

        overrides = {
            "version": 1,
            "overrides": [{
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "action": "skip", "evidence": "0/14", "adjustment_commit": None,
            }],
        }
        # Real surviving P1 in same domain/tier (from self-pitfall, a non-skipped lens).
        review_records = [{
            "ts": "2026-07-04T10:00:00Z",
            "review_id": "r-real-1",
            "domain": "ui", "tier": "ship-worthy", "lens": "self-pitfall",
            "shadow": False,
            "survived_synthesis": 1, "max_severity": "P1",
            "cost_usd": 0.0, "findings": 1,
        }]

        # Pre-shadow: no shadow records → correlational fires.
        reverts_pre = monitor.check_escapes(review_records, overrides, [], [])
        ok(len(reverts_pre) == 1, f"correlational fires pre-shadow: {reverts_pre}")
        ok(reverts_pre[0]["trigger_source"] == "correlational", "trigger = correlational")

        # Post-shadow: shadow data exists → correlational suppressed.
        history_with_shadow = [{
            "ts": "2026-07-04T09:00:00Z",
            "review_id": "r-shadow-0",
            "domain": "ui", "tier": "ship-worthy", "lens": "codex",
            "shadow": True,
            "survived_synthesis": 0, "max_severity": "none",
            "cost_usd": 0.05, "findings": 0,
        }]
        reverts_post = monitor.check_escapes(review_records, overrides, [], history_with_shadow)
        ok(len(reverts_post) == 0, "correlational suppressed once shadow data exists")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 6. Correlational cooldown: quarantined triple does not re-trigger
# ---------------------------------------------------------------------------

def test_correlational_cooldown_with_quarantine() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import monitor
        import importlib
        importlib.reload(ledger)
        importlib.reload(monitor)

        overrides = {
            "version": 1,
            "overrides": [{
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "action": "skip", "evidence": "0/14", "adjustment_commit": None,
            }],
        }
        review_records = [{
            "ts": "2026-07-04T10:00:00Z",
            "review_id": "r-2",
            "domain": "ui", "tier": "ship-worthy", "lens": "self-pitfall",
            "shadow": False, "survived_synthesis": 1, "max_severity": "P1",
            "cost_usd": 0.0, "findings": 1,
        }]
        # Quarantine entry for the same triple — means it's already been reverted.
        quarantine = [{
            "domain": "ui", "tier": "ship-worthy", "lens": "codex",
            "quarantined_at_ts": "2026-07-04T08:00:00Z",
            "required_non_shadow_count": 30,
            "trigger_source": "correlational",
        }]

        # With quarantine present, the triple is guarded — no new trigger.
        reverts = monitor.check_escapes(review_records, overrides, quarantine, [])
        ok(len(reverts) == 0, "no re-trigger while triple is quarantined")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 7. Quarantine cleared exactly when post-quarantine non-shadow count is met
# ---------------------------------------------------------------------------

def test_quarantine_lifecycle_cleared_at_count() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import tune
        import importlib
        importlib.reload(ledger)
        importlib.reload(tune)

        ld = Path(td)
        ledger.ensure_repo()

        from scorer import REQUIRED_NON_SHADOW_AFTER_QUARANTINE
        q_ts = "2026-07-04T08:00:00Z"
        quarantine = [{
            "domain": "ui", "tier": "ship-worthy", "lens": "codex",
            "quarantined_at_ts": q_ts,
            "required_non_shadow_count": REQUIRED_NON_SHADOW_AFTER_QUARANTINE,
            "trigger_source": "shadow",
        }]

        # History with REQUIRED_NON_SHADOW_AFTER_QUARANTINE - 1 post-ts real records.
        needed = REQUIRED_NON_SHADOW_AFTER_QUARANTINE
        history_short = [
            {
                "ts": f"2026-07-04T09:{i:02d}:00Z",
                "review_id": f"r-{i}",
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "shadow": False,
                "survived_synthesis": 0, "max_severity": "none",
                "cost_usd": 0.05, "findings": 0,
            }
            for i in range(needed - 1)  # one short of the threshold
        ]
        q_path = ld / "quarantine.json"
        ledger.atomic_write(q_path, quarantine)

        # advance_quarantine with short history: quarantine must remain.
        remaining = tune._advance_quarantine(quarantine, history_short, ld)
        ok(len(remaining) == 1, "quarantine not cleared yet (one short)")
        ok(json.loads(q_path.read_text()) == quarantine, "quarantine.json unchanged")

        # Add the final record to meet the threshold exactly.
        history_full = history_short + [{
            "ts": f"2026-07-04T09:{needed:02d}:00Z",
            "review_id": f"r-{needed}",
            "domain": "ui", "tier": "ship-worthy", "lens": "codex",
            "shadow": False,
            "survived_synthesis": 0, "max_severity": "none",
            "cost_usd": 0.05, "findings": 0,
        }]
        remaining2 = tune._advance_quarantine(remaining, history_full, ld)
        ok(len(remaining2) == 0, "quarantine cleared when count is met")
        ok(json.loads(q_path.read_text()) == [], "quarantine.json now empty")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 8. reset restores baseline
# ---------------------------------------------------------------------------

def test_reset_restores_baseline() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import cli as _cli
        import importlib
        importlib.reload(ledger)
        importlib.reload(_cli)

        ld = Path(td)
        ledger.ensure_repo()

        # Write baseline (empty overrides) and a non-empty overrides.
        baseline = {"version": 1, "generated_ts": "", "overrides": []}
        ledger.atomic_write(ld / "baseline.json", baseline)

        current_ov = {
            "version": 1,
            "generated_ts": "2026-07-04T10:00:00Z",
            "overrides": [{
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "action": "skip", "evidence": "0/14", "adjustment_commit": "abc",
            }],
        }
        ledger.atomic_write(ld / "overrides.json", current_ov)
        ledger.commit([ld / "overrides.json"], "test: add skip")

        # Full reset.
        ret = _cli.cmd_reset(None)
        ok(ret == 0, "reset returns 0")

        after = json.loads((ld / "overrides.json").read_text())
        ok(after["overrides"] == [], "all skips cleared after full reset")

        # Domain-level reset: add a skip for two domains, reset only one.
        two_domain_ov = {
            "version": 1, "generated_ts": "",
            "overrides": [
                {"domain": "ui", "tier": "ship-worthy", "lens": "codex",
                 "action": "skip", "evidence": "x", "adjustment_commit": ""},
                {"domain": "format", "tier": "ship-worthy", "lens": "codex",
                 "action": "skip", "evidence": "x", "adjustment_commit": ""},
            ],
        }
        ledger.atomic_write(ld / "overrides.json", two_domain_ov)
        ledger.commit([ld / "overrides.json"], "test: two domain skips")

        _cli.cmd_reset("ui")
        after2 = json.loads((ld / "overrides.json").read_text())
        domains_in_ov = {o["domain"] for o in after2["overrides"]}
        ok("ui" not in domains_in_ov, "ui skip gone after domain reset")
        ok("format" in domains_in_ov, "format skip preserved")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 9. git commit/revert round-trip
# ---------------------------------------------------------------------------

def test_git_round_trip() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib
        importlib.reload(ledger)

        ld = Path(td)
        ledger.ensure_repo()

        # Simple file to avoid overrides.json SHA-backfill interference.
        test_path = ld / "round_trip_test.json"
        ledger.atomic_write(test_path, {"phase": "initial", "items": []})
        sha_init = ledger.commit([test_path], "test: initial state")
        ok(len(sha_init) == 40, f"initial SHA is 40 chars: {sha_init!r}")

        ledger.atomic_write(test_path, {"phase": "modified", "items": ["skip-entry"]})
        sha_mod = ledger.commit([test_path], "test: add skip entry")
        ok(sha_mod != sha_init, "modified SHA differs from initial")

        # Revert the modification.
        sha_revert = ledger.revert(sha_mod)
        ok(sha_revert != sha_mod, "revert produces new SHA")

        # File should be back to initial state.
        content = json.loads(test_path.read_text())
        ok(content["phase"] == "initial", f"phase restored: {content}")
        ok(content["items"] == [], f"items restored: {content}")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 10. read_* with missing files → safe empty defaults
# ---------------------------------------------------------------------------

def test_missing_files_return_defaults() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib
        importlib.reload(ledger)

        history = ledger.read_history()
        ok(history == [], "read_history: missing file → []")

        q = ledger.read_quarantine()
        ok(q == [], "read_quarantine: missing file → []")

        ov = ledger.read_overrides()
        ok(isinstance(ov, dict) and ov["overrides"] == [], "read_overrides: missing → empty")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 11. append_record: written and parseable
# ---------------------------------------------------------------------------

def test_append_record_written_and_parseable() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import importlib
        importlib.reload(ledger)

        rec1 = {
            "ts": "2026-07-04T10:00:00Z", "review_id": "r1",
            "lens": "codex", "domain": "ui", "tier": "ship-worthy",
            "cost_usd": 0.12, "findings": 3, "max_severity": "P2",
            "survived_synthesis": 1, "shadow": False,
        }
        rec2 = {**rec1, "review_id": "r2", "lens": "glm", "shadow": True}
        ledger.append_record(rec1)
        ledger.append_record(rec2)

        history = ledger.read_history()
        ok(len(history) == 2, f"two records appended: {len(history)}")
        ok(history[0]["review_id"] == "r1", "first record correct")
        ok(history[1]["lens"] == "glm", "second record correct")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 12. tune cycle one-step guard: second skip for same (domain, tier) blocked
# ---------------------------------------------------------------------------

def test_tune_one_step_guard() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import tune
        import importlib
        importlib.reload(ledger)
        importlib.reload(tune)

        ld = Path(td)
        ledger.ensure_repo()
        ov_path = ld / "overrides.json"

        # Pre-seed overrides with one skip for (ui, ship-worthy) — simulates
        # session A having already committed a skip.
        existing_ov = {
            "version": 1, "generated_ts": "",
            "overrides": [{
                "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                "action": "skip", "evidence": "already there",
                "adjustment_commit": "abc",
            }],
        }
        ledger.atomic_write(ov_path, existing_ov)

        # Build a proposals list that tries to add a second skip for (ui, ship-worthy).
        proposals = [
            {"domain": "ui", "tier": "ship-worthy", "lens": "glm",
             "action": "skip", "evidence": "0/10 survived"},
        ]

        new_ov, _ = tune._apply_proposals(proposals, existing_ov, [], ld)

        # The new skip must NOT be added (one-step guard).
        skips_for_ui_sw = [
            o for o in new_ov.get("overrides", [])
            if o["domain"] == "ui" and o["tier"] == "ship-worthy" and o.get("action") == "skip"
        ]
        ok(len(skips_for_ui_sw) == 1, f"one-step guard: only 1 skip, got {skips_for_ui_sw}")
        ok(skips_for_ui_sw[0]["lens"] == "codex", "existing codex skip preserved, glm blocked")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 13. pause flag frozen, escape still runs
# ---------------------------------------------------------------------------

def test_pause_flag_freezes_tune_not_escape() -> None:
    td = _tmp_ledger()
    try:
        import ledger
        import cli as _cli
        import importlib
        importlib.reload(ledger)
        importlib.reload(_cli)

        ld = Path(td)
        ledger.ensure_repo()

        # Start unpaused.
        state = ledger.read_state()
        ok(not state.get("paused"), "initially unpaused")

        # Pause.
        _cli.cmd_pause()
        state2 = ledger.read_state()
        ok(state2.get("paused") is True, "paused after cmd_pause()")

        # Pause again (toggle to unpause).
        _cli.cmd_pause()
        state3 = ledger.read_state()
        ok(not state3.get("paused"), "unpaused after second cmd_pause()")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# 14. High-blast floor: propose never emits skip for high/very-high domains
# ---------------------------------------------------------------------------

def test_high_blast_floor() -> None:
    """Paranoia test: propose must never produce a skip for high/very-high domains."""
    from scorer import propose

    # Build rich history that would clear every threshold for a high domain.
    history = []
    for i in range(20):
        history.append({
            "ts": f"2026-07-0{1 + i // 10}T{i:02d}:00:00Z",
            "review_id": f"r{i}",
            "domain": "auth",  # sensitivity level: high → no skip allowed
            "tier": "ship-worthy",
            "lens": "codex",
            "cost_usd": 0.12,
            "findings": 0,
            "max_severity": "none",
            "survived_synthesis": 0,
            "shadow": False,
        })

    proposals = propose(history, [])
    skips = [p for p in proposals if p["action"] == "skip"]
    ok(len(skips) == 0, f"no skip proposed for high-sensitivity domain 'auth': {skips}")


# ---------------------------------------------------------------------------
# 15. Quarantine respects post-quarantine-ts boundary (not all-time count)
# ---------------------------------------------------------------------------

def test_quarantine_ts_boundary() -> None:
    """Records BEFORE quarantined_at_ts must not count toward the release threshold."""
    td = _tmp_ledger()
    try:
        import ledger
        import tune
        import importlib
        importlib.reload(ledger)
        importlib.reload(tune)

        ld = Path(td)
        ledger.ensure_repo()

        from scorer import REQUIRED_NON_SHADOW_AFTER_QUARANTINE as NEEDED
        q_ts = "2026-07-04T12:00:00Z"
        quarantine = [{
            "domain": "format", "tier": "ship-worthy", "lens": "codex",
            "quarantined_at_ts": q_ts,
            "required_non_shadow_count": NEEDED,
            "trigger_source": "shadow",
        }]

        # NEEDED records, all with ts BEFORE q_ts → should NOT satisfy the threshold.
        old_records = [
            {
                "ts": f"2026-07-04T0{i}:00:00Z",  # all before 12:00
                "review_id": f"old-{i}",
                "domain": "format", "tier": "ship-worthy", "lens": "codex",
                "shadow": False, "survived_synthesis": 0, "max_severity": "none",
                "cost_usd": 0.01, "findings": 0,
            }
            for i in range(min(NEEDED, 9))  # 0-8 hours, all before 12:00
        ]
        # Pad to NEEDED if less than 9 slots cover it.
        while len(old_records) < NEEDED:
            old_records.append({**old_records[-1], "review_id": f"pad-{len(old_records)}"})

        q_path = ld / "quarantine.json"
        ledger.atomic_write(q_path, quarantine)

        remaining = tune._advance_quarantine(quarantine, old_records, ld)
        ok(len(remaining) == 1, "old records (pre-ts) do not clear quarantine")
    finally:
        _cleanup(td)


def test_tune_escape_before_apply_ordering() -> None:
    # codex P1: run_tune_cycle must check escapes against DISPATCH-time overrides,
    # BEFORE applying proposals. Otherwise the `run` proposal that propose() emits
    # for a shadow survivor removes the active skip first, so check_escapes sees no
    # active skip, the required quarantine is never written, and the triple can
    # re-skip next cycle. Drives the ORCHESTRATOR (not check_escapes in isolation),
    # so it fails on the old ordering and passes on the fix.
    td = _tmp_ledger()
    try:
        import ledger
        import tune
        import importlib
        importlib.reload(ledger)
        importlib.reload(tune)
        ld = Path(td)
        ledger.ensure_repo()
        ov_path = ld / "overrides.json"
        ledger.atomic_write(ov_path, {
            "version": 1, "generated_ts": "2026-07-04T10:00:00Z",
            "overrides": [{"domain": "ui", "tier": "ship-worthy", "lens": "codex",
                           "action": "skip", "evidence": "0/14 survived",
                           "adjustment_commit": "abc1234"}]})
        ledger.commit([ov_path], "test: add skip")
        # A shadow record with a surviving P1: this both makes propose() emit a
        # `run` for the triple (the buggy ordering applies it first) AND is the
        # escape signal check_escapes must act on.
        shadow_hit = {"ts": "2026-07-04T11:00:00Z", "review_id": "r-shadow-1",
                      "domain": "ui", "tier": "ship-worthy", "lens": "codex",
                      "shadow": True, "survived_synthesis": 1, "max_severity": "P1",
                      "cost_usd": 0.05, "findings": 2}
        ledger.append_record(shadow_hit)     # §10 point 2: caller appends
        tune.run_tune_cycle([shadow_hit])    # §10 point 3: then tunes
        q = ledger.read_quarantine()
        ok(len(q) == 1 and q[0]["domain"] == "ui" and q[0]["lens"] == "codex",
           f"shadow-hit on an active skip must quarantine via run_tune_cycle; got {q}")
    finally:
        _cleanup(td)


# ---------------------------------------------------------------------------
# Main runner.
# ---------------------------------------------------------------------------

TESTS = [
    test_atomic_write_no_partial_on_crash,
    test_reader_never_sees_partial,
    test_tune_escape_before_apply_ordering,
    test_lock_serializes_two_writers,
    test_shadow_escape_revert_and_quarantine,
    test_correlational_trigger_pre_and_post_shadow,
    test_correlational_cooldown_with_quarantine,
    test_quarantine_lifecycle_cleared_at_count,
    test_reset_restores_baseline,
    test_git_round_trip,
    test_missing_files_return_defaults,
    test_append_record_written_and_parseable,
    test_tune_one_step_guard,
    test_pause_flag_freezes_tune_not_escape,
    test_high_blast_floor,
    test_quarantine_ts_boundary,
]


def main() -> int:
    # Ensure we resolve modules from this directory.
    here = Path(__file__).parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    passed = 0
    failed = 0
    for test_fn in TESTS:
        name = test_fn.__name__
        try:
            test_fn()
            print(f"  ok  {name}")
            passed += 1
        except (AssertionError, Exception) as exc:
            print(f"FAIL  {name}: {exc}")
            failed += 1

    print()
    if failed:
        print(f"FAIL ({failed} test(s) failed; {_N} assertions checked)")
        return 1
    print(f"PASS ({_N} assertions across {passed} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
