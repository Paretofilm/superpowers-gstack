---
name: context-handoff
description: Write a human-readable handoff file in the repo before /clear or /compact. Different from /context-save (gstack) — this writes to docs/superpowers/handoff.md for cross-machine and post-clear continuity.
---

# Context Handoff

Writes a human-readable session handoff to `docs/superpowers/handoff.md` in the project repo. Use this before `/clear` or `/compact` to capture where you left off.

**Not the same as `/context-save`:** `/context-save` (gstack) stores machine-local session state in `~/.gstack/projects/` and is restored by `/context-restore`. This skill writes a Markdown file directly into the repo — readable by anyone, on any machine, without gstack installed.

## When this skill activates

- User says "context getting long", "about to clear", "save before clear"
- CLAUDE.md sensor triggers after /compact (user opts in to auto-modus)
- User explicitly invokes /context-handoff

## Save state

1. **Create `docs/superpowers/` directory** if it doesn't exist.

2. **Write handoff file** at `docs/superpowers/handoff.md` (overwrite if exists):

   ```markdown
   # Session Handoff — {YYYY-MM-DD HH:MM}

   ## What I was doing
   {1-2 sentence summary of current task}

   ## Current status
   - Branch: {branch name}
   - Last completed step: {what was just finished}
   - Next step: {what should happen next}

   ## Key decisions made this session
   - {decision 1}
   - {decision 2}

   ## Files modified this session
   - {path} — {1-line description of change}

   ## Plan progress
   {If a Superpowers plan exists in docs/superpowers/plans/: list completed vs remaining tasks. Otherwise: "No active plan."}

   ## Open questions / blockers
   - {anything unresolved, or "None"}
   ```

3. Tell the user: "State saved. You can `/clear` now — I'll pick up automatically."

**STOP HERE.** Do not continue or suggest next steps.

## Auto-modus (activated after compact)

When the user opts in to auto context handoff after a compact trigger:

1. **Append `## Mode: auto` to handoff.md** immediately. This marker tells the CLAUDE.md sensor not to re-ask after subsequent compacts.

2. **Update handoff.md after each significant milestone** — completing a task, making a key decision, finishing a file. Don't update on every small change. Always preserve the `## Mode: auto` marker when updating.

3. **Suggest /clear proactively** when you're about to start a new major task that would benefit from fresh context, or when the session has been through multiple large operations since last compact/clear.

   Say: "Context is getting heavy. handoff.md is up to date — safe to /clear."

4. **Do NOT ask repeatedly.** Suggest /clear once. If the user continues, respect that and keep working. You may suggest again only if another compact happens.

## Resume is automatic

Resume is NOT part of this skill. It's handled by a CLAUDE.md instruction that runs on every session start and after compact. See the "Session continuity" section in CLAUDE.md.
