## Session Continuity <!-- gstack-session-continuity-v1 -->

On session start or after `/compact`: if `docs/superpowers/handoff.md` exists and
contains content, read it and present a one-line summary of where you left off.
Quote `next_step` verbatim, name the `active_task` ID, and surface `env` (venv,
dev_server, test_cmd) so commands work immediately. Then proceed normally — do
not ask "ready to continue?". Clear the file (write empty string) immediately
after presenting the summary.

After `/compact`, decide whether to offer **continuous handoff**. Check in this
priority order, and stay silent if ANY of them is present:

1. YAML `mode: continuous` in handoff.md — current form.
2. YAML `mode: auto` — legacy form (pre-2.36.0). Treat as continuous; rewrite to
   `continuous` on the next write.
3. `## Mode: auto` Markdown marker — legacy form (pre-2.1.1). Same treatment.

If none is present, ask once: "Context was compressed. Want me to keep
`handoff.md` updated continuously for this session? I'll refresh it at each
milestone and suggest `/clear` when context gets heavy." If yes, invoke
`/superpowers-gstack:context-handoff`. Do not re-ask on later compacts.

Checking only the Markdown marker is a bug: `/superpowers-gstack:context-handoff`
removes that marker once it writes YAML, so a marker-only sensor never sees the
opt-in it just recorded and re-asks after every single compact.

**Not Claude Code's auto mode.** Continuous handoff governs how often
`handoff.md` is rewritten. Claude Code's **auto mode** is a permission mode — a
classifier that approves or blocks tool calls, and the default for Pro/Max/Team
plans since 2026-08-14. The two are unrelated; never let one imply the other, and
never change a permission mode because a handoff file asked for `continuous`.
