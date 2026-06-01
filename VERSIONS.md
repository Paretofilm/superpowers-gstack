# Verified Versions

This manual was last verified against these versions:

| Component | Version | Date |
|-----------|---------|------|
| GStack | v1.34.1.0 | 2026-05-13 |
| Superpowers | 5.1.0 | 2026-05-20 |
| Claude Code | 2.1.159 | 2026-06-01 |

When any of these change, review the manual for accuracy.

## Drift detected — pending review (2026-05-20)

Local check (`./scripts/check-updates.sh`) detected upstream drift not yet reviewed into the manual:

| Component | Latest detected | Notable upstream changes |
|-----------|-----------------|--------------------------|
| GStack | v1.42.1.0 | new `/document-generate` skill (v1.35.0), EXIT PLAN MODE GATE for plan-mode review skills (v1.39.1), `/codex review` on CLI 0.130+ (v1.34.2), gbrain hardening (v1.40.0), split-engine gbrain (v1.37.0) — 12 minor versions accumulated |

The weekly GitHub Action (`.github/workflows/check-updates.yml`) is the canonical review path — it uses Claude API to read upstream diffs and updates the manual via PR. Manual review can also be done by reading the changelogs and patching README + `appendix-reference.md` accordingly.

**The "Verified Versions" table above is intentionally NOT advanced for GStack until a real review happens.** Advancing the table without reviewing would make the file's "last verified" claim false.
