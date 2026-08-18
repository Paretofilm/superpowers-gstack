## Session Continuity <!-- gstack-session-continuity-v2 -->

On session start or after `/compact`, look at `docs/superpowers/handoff.md`. It is
consumed **only** when you can positively identify it as a handoff. Reading a
handoff clears it, so misidentifying the file destroys whatever was in it:

- YAML `type: handoff` — the current format (v2.1.1+). Consume it.
- YAML frontmatter carrying **both** `session_end` and `next_step` but no
  `type:` — a legacy handoff (v1.12.0–v2.1.0). Consume it.
- **Anything else, including a file with no frontmatter at all** — NOT a handoff.
  Say in one line that the file exists and holds unrecognized content, do not
  present it as "where you left off", and **do not clear it**. A project may be
  using that path for its own notes, and silently emptying it is not recoverable
  from the session.

When it *is* a handoff: present a one-line summary of where you left off. Quote
`next_step` verbatim, name the `active_task` ID, and surface `env` (venv,
dev_server, test_cmd) so commands work immediately. Then proceed normally — do
not ask "ready to continue?".

**Read the `mode:` field BEFORE you clear the file.** Clearing first destroys the
value the next step depends on. Once you have read it:

- `mode: continuous` (or a legacy spelling, below) → do NOT blank the file.
  Rewrite it carrying just the frontmatter — `type: handoff` plus
  `mode: continuous` — so the setting survives into the next compact. Blanking it
  here is exactly what makes a project ask the opt-in question forever.
- anything else → clear the file (write empty string), as before.

After `/compact`, decide whether to offer **continuous handoff**, using the `mode`
you read above:

1. YAML `mode: continuous` — current form. Already on; stay silent.
2. YAML `mode: auto` — the pre-2.36.0 spelling of the same thing. Stay silent,
   and write `continuous` on the next write.
3. **No YAML `mode:` key at all**, but a `## Mode: auto` Markdown marker
   (pre-2.1.1) → stay silent, same treatment. The Markdown marker is consulted
   ONLY when the YAML key is absent: an explicit `mode: manual` sitting beside a
   stale marker means manual, not continuous.

If none of the three applies, ask once: "Context was compressed. Want me to keep
`handoff.md` updated continuously for this session? I'll refresh it at each
milestone and suggest `/clear` when context gets heavy." If yes, invoke
`/superpowers-gstack:context-handoff`. Do not re-ask on later compacts.

**Not Claude Code's auto mode.** Continuous handoff governs how often
`handoff.md` is rewritten. Claude Code's **auto mode** is a permission mode — a
classifier that approves or blocks tool calls, and the default for Pro/Max/Team
plans since 2026-08-14. The two are unrelated; never let one imply the other, and
never change a permission mode because a handoff file asked for `continuous`.
