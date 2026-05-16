---
name: context-handoff
description: Write a structured handoff file (YAML frontmatter + prose) to docs/superpowers/handoff.md before /clear or /compact. Different from /context-save (gstack) — survives across machines and restores without gstack installed.
---

# Context Handoff

Writes a structured session handoff to `docs/superpowers/handoff.md` in the project repo. Use this before `/clear` or `/compact` to capture where you left off in a way that's both human-readable and machine-parseable.

**Not the same as `/context-save`:** `/context-save` (gstack) stores machine-local session state in `~/.gstack/projects/` and is restored by `/context-restore`. This skill writes a Markdown file directly into the repo — readable by anyone, on any machine, without gstack installed. The YAML frontmatter lets the SessionStart hook pick up structured fields (active task, next step, env) without prose-parsing.

## When this skill activates

- User says "context getting long", "about to clear", "save before clear"
- CLAUDE.md sensor triggers after /compact (user opts in to auto-modus)
- User explicitly invokes /context-handoff

**Side effect to know about:** If the `/htmlify` PostToolUse hook is installed (`scripts/setup-htmlify-hook.sh`), writing handoff.md will automatically render it as HTML and open it in Safari. This happens in the background and doesn't block. Tell the user once if it seems to surprise them.

## Save state

1. **Create `docs/superpowers/` directory** if it doesn't exist.

2. **Write handoff file** at `docs/superpowers/handoff.md` (overwrite if exists). Use this YAML+prose hybrid:

   ```markdown
   ---
   type: handoff
   session_end: {ISO-8601 with timezone, e.g. 2026-05-14T16:30:00+02:00}
   branch: {current git branch, or "n/a" if not a repo}
   commit_at_handoff: {short SHA of HEAD, or "n/a"}
   mode: {manual | auto}

   active_task: {feature-slug-N, e.g. auth-rewrite-3}
   status: {in_progress | blocked | ready_to_review | done}
   completed: [task-id-1, task-id-2]
   remaining: [task-id-4, task-id-5]

   files_in_flight:
     - {path/to/file.ts}

   env:
     venv: {.venv | n/a}
     dev_server: {"npm run dev (port 3000)" | n/a}
     test_cmd: {"npm test -- auth" | n/a}

   next_step: {one concrete sentence — file:line + verb. E.g. "Read session.ts:45-78, decide if refresh-flow goes in middleware or hook"}
   ---

   # Session Handoff — {YYYY-MM-DD HH:MM}

   ## What I was doing
   {1-2 sentence summary of current task}

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

## Task ID convention

Use `<feature-slug>-<n>` where `<feature-slug>` is a stable kebab-case identifier for the feature/initiative and `<n>` is a sequence number. Examples: `auth-rewrite-3`, `pdf-export-1`, `bug-double-charge-2`.

- IDs are **stable** — once assigned, never renumber. Even if task 2 is deleted, do not shift task 3 down to 2.
- IDs are **grep-able** — including the feature-slug means `grep auth-rewrite-` finds all related tasks across handoff history, plan files, and commit messages.
- One feature-slug per coherent unit of work. New unrelated work gets a new slug.

## YAML field rules

- `type: handoff` MUST be the first field — downstream tools (e.g. `/htmlify`) use it as the primary type-discriminator. Filename-based detection exists as a fallback for pre-2.1.1 handoffs but should not be relied on going forward.
- `mode: auto` in YAML replaces the older `## Mode: auto` Markdown marker. If both exist (legacy handoff), YAML takes precedence; remove the Markdown marker on next write.
- `next_step` MUST be one sentence with a concrete verb and (where possible) a file:line anchor. "Continue work on auth" is not acceptable; "Read src/auth/session.ts:45-78, decide middleware vs hook for refresh flow" is.
- `completed` and `remaining` arrays may be empty (`[]`) but must be present.
- `env` keys may be `n/a` for languages/projects that don't need them, but the `env:` block must be present.

## Auto-modus (activated after compact)

When the user opts in to auto context handoff after a compact trigger:

1. **Set `mode: auto` in YAML** immediately. This marker tells the CLAUDE.md sensor not to re-ask after subsequent compacts.

2. **Update handoff.md after each significant milestone** — completing a task, making a key decision, finishing a file. Don't update on every small change. Always preserve `mode: auto` when updating.

3. **Suggest /clear proactively** when you're about to start a new major task that would benefit from fresh context, or when the session has been through multiple large operations since last compact/clear.

   Say: "Context is getting heavy. handoff.md is up to date — safe to /clear."

4. **Do NOT ask repeatedly.** Suggest /clear once. If the user continues, respect that and keep working. You may suggest again only if another compact happens.

## Backwards compatibility

If you encounter an existing handoff.md without YAML frontmatter (pre-1.12.0 prose-only format):
- Read it as-is for the current session.
- On next write, convert to YAML+prose format. Preserve the user-meaningful prose sections; populate YAML fields from prose where possible, leave others as `n/a`.

## Resume is automatic

Resume is NOT part of this skill. It's handled by a CLAUDE.md instruction that runs on every session start and after compact. See the "Session continuity" section in CLAUDE.md.
