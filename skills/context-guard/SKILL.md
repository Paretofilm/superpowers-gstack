---
name: context-guard
description: Context hygiene — saves work state and monitors session length. Invoke to save state, or auto-activated after compact.
---

# Context Guard

Lightweight context hygiene inspired by GSD. Prevents context rot without adding orchestration overhead.

## When this skill activates

- User says "save state", "context getting long", "about to clear"
- CLAUDE.md sensor triggers after /compact (user opts in to auto-modus)
- User explicitly invokes /context-guard

## Save state

1. **Write handoff file** at `docs/superpowers/handoff.md` (overwrite if exists):

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

2. Tell the user: "State saved. You can `/clear` now — I'll pick up automatically."

**STOP HERE.** Do not continue or suggest next steps.

## Auto-modus (activated after compact)

When the user opts in to auto context guard after a compact trigger:

1. **Update handoff.md after each significant milestone** — completing a task, making a key decision, finishing a file. Don't update on every small change.

2. **Suggest /clear proactively** when you estimate context is getting heavy again:
   - Multiple large file reads since last compact
   - Many sequential tool calls (20+) since last compact/clear
   - You're about to start a new major task that would benefit from fresh context

   Say: "Context is getting heavy again. handoff.md is up to date — safe to /clear."

3. **Do NOT ask repeatedly.** Suggest /clear once. If the user continues, respect that and keep working. You may suggest again only if another compact happens.

## Resume is automatic

Resume is NOT part of this skill. It's handled by a CLAUDE.md instruction that runs on every session start and after compact. See the "Session continuity" section in CLAUDE.md.
