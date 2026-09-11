## Session Continuity <!-- gstack-session-continuity-v4 -->

On session start or after `/compact`, look at `docs/superpowers/handoff.md` and
**classify it before touching it**. Consuming a handoff clears it, so a wrong
classification destroys whatever was there.

- **Empty or whitespace only** → nothing to do, say nothing. This is the normal
  resting state after a handoff has been consumed.
- **Continuous-mode stub** — frontmatter carrying `mode: continuous` and no
  `next_step`. This is the marker left behind by the clearing step below, not a
  handoff. Say nothing, leave the file exactly as it is, and treat continuous
  handoff as already active.
- **Complete handoff** — frontmatter with `type: handoff` **and** a usable
  `next_step` to resume from. Consume it (below).
- **Anything else** → NOT consumable: frontmatter that claims to be a handoff but
  carries no `next_step`, a file cut off mid-write, or a file with no frontmatter
  at all. Do not present it as where you left off, and **do not clear it** — a
  truncated handoff and a project's own notes both live at this path, and neither
  survives being emptied. Say so in one line **and name the way out**: the file has
  to be deleted, or overwritten by invoking `/superpowers-gstack:context-handoff`.

For a complete handoff: present a one-line summary of where you left off. Quote
`next_step` verbatim, name the `active_task` ID, and surface `env` (venv,
dev_server, test_cmd) so commands work immediately. Then proceed normally — do
not ask "ready to continue?".

**Read the `mode:` field BEFORE you clear the file**, then:

- `mode: continuous` → do NOT blank the file. Rewrite it carrying just
  `type: handoff` and `mode: continuous` — the stub above — so the setting
  survives into the next compact.
- anything else → clear the file (write empty string).

Either way, **copy what you consumed to `docs/superpowers/.handoff-last.md`
first** (one file, overwritten each time). Classifying a handoff is a judgement
call, and a truncation that lands *after* valid frontmatter looks complete from
the inside; the copy makes a misjudgement recoverable.

After `/compact`: if `mode: continuous` was set, stay silent. Otherwise ask once:
"Context was compressed. Want me to keep `handoff.md` updated continuously for
this session? I'll refresh it at each milestone and suggest `/clear` when context
gets heavy." If yes, invoke `/superpowers-gstack:context-handoff`. Do not re-ask
on later compacts.

**Not Claude Code's auto mode.** Continuous handoff governs how often
`handoff.md` is rewritten. Claude Code's **auto mode** is a permission mode. The
two are unrelated; never change a permission mode because a handoff file asked
for `continuous`.
