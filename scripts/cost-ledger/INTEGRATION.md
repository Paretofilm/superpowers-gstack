# Cost-ledger integration points for `pitfall-verification`

Spec §10 defines three precise moments where `pitfall-verification` touches
the cost-ledger.  This file names the exact functions to call at each moment.

---

## §10 point 1 — Tier-gate read (before dispatch)

**When:** `pitfall-verification` has classified the change as ship-worthy or
high-stakes and is about to dispatch external lenses (Codex / GLM).

**Call:**

```python
from scripts.cost_ledger.ledger import read_overrides

overrides = read_overrides()   # → dict  (never raises; missing file = empty)
active_skips = {
    (o["domain"], o["tier"], o["lens"])
    for o in overrides.get("overrides", [])
    if o.get("action") == "skip"
}
```

**Shadow sampling:** for each skipped lens, decide whether this review is a
shadow run using:

```python
from scripts.cost_ledger.scorer import SHADOW_RATE
import random
is_shadow_run = random.random() < SHADOW_RATE   # currently 1/8
```

If `is_shadow_run` is True, dispatch the lens anyway but mark its result as
non-gating.  Pass `shadow=True` in the ledger record (point 2).

---

## §10 point 2 — Ledger write (after synthesis)

**When:** Stage-4 adversarial synthesis has completed and `survived_synthesis`
counts are known for every lens that ran (real or shadow).

**Call (once per lens that ran):**

```python
from scripts.cost_ledger.ledger import append_record

append_record({
    "ts":                 "<ISO-8601 UTC>",          # e.g. datetime.utcnow().strftime(...)
    "review_id":          "<uuid>",                   # one ID per pitfall-verification run
    "lens":               "codex" | "glm" | "self-pitfall",
    "domain":             "<v0.2 classifier label>",  # exact string the classifier emits
    "tier":               "ship-worthy" | "high-stakes",
    "cost_usd":           0.12,                       # lens cost for this run
    "findings":           3,                          # raw finding count
    "max_severity":       "P1" | "P2" | "P3" | "none",
    "survived_synthesis": 2,                          # findings that survived Stage-4
    "shadow":             False,                      # True for shadow runs (§7)
})
```

`append_record` is a lock-free O_APPEND write — safe to call from concurrent
sessions without holding the `.lock`.

---

## §10 point 3 — Tune + escape check (after write, under the `.lock`)

**When:** Immediately after all ledger writes for this review are done.

**Call:**

```python
from scripts.cost_ledger.tune import run_tune_cycle

run_tune_cycle(review_records)
```

Where `review_records` is the list of dicts you just passed to `append_record`
(one per lens, same structure).  `run_tune_cycle` acquires the exclusive flock
internally; if the lock times out it skips the cycle cleanly (the records are
already written and the next review will tune on fuller history).

`run_tune_cycle` orchestrates under the lock:
1. `propose(history, quarantine)` from `scorer.py`
2. Applies §5-filtered proposals (`atomic_write` overrides + git commit + log)
3. Runs `check_escapes` + `apply_revert` for each escape found
4. Clears quarantine entries whose post-quarantine non-shadow count is met

---

## Module layout

```
scripts/cost-ledger/
  scorer.py         — pure ROI scorer (propose); DO NOT MODIFY
  ledger.py         — storage, flock, atomic writes, git helpers
  monitor.py        — escape detection (check_escapes) + apply_revert
  tune.py           — auto-tune cycle orchestrator (run_tune_cycle)
  cli.py            — /cost-ledger CLI (status, reset, pause, explain)
  INTEGRATION.md    — this file
```

---

## Alert stub (§7 step 3)

`monitor._raise_alert()` currently writes to
`~/.claude/cost-ledger/session_notices.txt`.

**INTEGRATION POINT:** wire this to the same SessionStart-hook pattern as
`scripts/check-plugin-version.sh` — read and clear the file on session start
so the user sees the revert notice immediately.
