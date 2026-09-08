# spec-drift fixture plan

Fixture for the Fase-1 equivalence run — see Phase 4 of
`docs/superpowers/plans/2026-09-07-spec-drift.md`. Audited against `main...HEAD`
on branch `feat/spec-drift` (branch slug `feat-spec-drift`, repo
`superpowers-gstack`). The nine checkbox items below are the whole content; the
value of this file is the verdicts they produce, so they stay as written.

### Fase 1 — Wrapper

- [ ] Create `scripts/spec-drift.py` with subcommands `check`, `repin` and `verdict`
- [ ] Create `skills/spec-drift/SKILL.md` that reads `~/.claude/skills/gstack/ship/sections/plan-completion.md` at run time
- [ ] Create `skills/spec-drift/pin.json` carrying a sha256 of the upstream section
- [ ] Add a routing row for `superpowers-gstack:spec-drift` to `skills/adapt/SKILL.md`
- [ ] Test that a one-line change upstream is refused, in `tests/unit/test_spec_drift_pin.py`

### Fase 2 — Write-back and ledger

- [ ] Create the append-only drift ledger `.gstack/spec-drift.jsonl`
- [ ] Add `--accept <claimId>` to `scripts/spec-drift.py` that appends a fingerprint `claimId:kind:path` to the ledger
- [ ] Write confirmed CHANGED findings back into the plan under plan-fidelity's rules

### Fase 3 — Independent inventory

- [ ] Add a `--whole-tree` mode with verdicts PRESENT / ABSENT / UNVERIFIABLE
