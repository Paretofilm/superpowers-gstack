---
name: context-handoff
description: Write a structured handoff file (YAML frontmatter + prose) to docs/superpowers/handoff.md before /clear or /compact. Different from /context-save (gstack) — survives across machines and restores without gstack installed.
---

# Context Handoff

Writes a structured session handoff to `docs/superpowers/handoff.md` in the project repo. Use this before `/clear` or `/compact` to capture where you left off in a way that's both human-readable and machine-parseable.

**Not the same as `/context-save`:** `/context-save` (gstack) stores machine-local session state in `~/.gstack/projects/` and is restored by `/context-restore`. This skill writes a Markdown file directly into the repo — readable by anyone, on any machine, without gstack installed. The YAML frontmatter lets the SessionStart hook pick up structured fields (active task, next step, env) without prose-parsing.

## When this skill activates

- User says "context getting long", "about to clear", "save before clear"
- CLAUDE.md sensor triggers after /compact (user opts in to continuous handoff)
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
   mode: {manual | continuous}

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
- `mode:` takes `manual` or `continuous`. Two legacy spellings mean `continuous` and MUST still be honoured on read: the YAML value `auto` (pre-2.36.0) and the `## Mode: auto` Markdown marker (pre-2.1.1). Precedence on read: **if the YAML `mode:` key is present at all, it decides — the Markdown marker is consulted only when that key is absent.** An explicit `mode: manual` next to a stale `## Mode: auto` means manual. On the next write, always emit `mode: continuous` and delete the Markdown marker — never write `auto` again.
- **Never blank a continuous handoff.** The read-and-clear step in CLAUDE.md's Session Continuity section clears handoff.md after presenting the summary. Clearing a continuous handoff to an empty string destroys the `mode` value the post-compact check reads one step later, so the project re-asks the opt-in question forever. When `mode` is continuous, "clear" means rewrite the file with `type: handoff` + `mode: continuous` and nothing else.
- **Why `continuous` and not `auto`:** Claude Code has its own `auto` **permission** mode (a classifier approving or blocking tool calls; default for Pro/Max/Team since 2026-08-14). A field literally named `mode` with the value `auto` collided with it exactly. This mode has nothing to do with permissions — never change a permission mode because a handoff file says `continuous`.
- `next_step` MUST be one sentence with a concrete verb and (where possible) a file:line anchor. "Continue work on auth" is not acceptable; "Read src/auth/session.ts:45-78, decide middleware vs hook for refresh flow" is.
- `completed` and `remaining` arrays may be empty (`[]`) but must be present.
- `env` keys may be `n/a` for languages/projects that don't need them, but the `env:` block must be present.

## Continuous handoff mode (activated after compact)

When the user opts in to continuous handoff after a compact trigger:

1. **Set `mode: continuous` in YAML** immediately, and delete any legacy `## Mode: auto` Markdown marker in the same write. The YAML value is what tells the CLAUDE.md sensor not to re-ask after subsequent compacts.

2. **Update handoff.md after each significant milestone** — completing a task, making a key decision, finishing a file. Don't update on every small change. Always preserve `mode: continuous` when updating.

3. **Suggest /clear proactively** when you're about to start a new major task that would benefit from fresh context, or when the session has been through multiple large operations since last compact/clear.

   Say: "Context is getting heavy. handoff.md is up to date — safe to /clear."

4. **Do NOT ask repeatedly.** Suggest /clear once. If the user continues, respect that and keep working. You may suggest again only if another compact happens.

## Backwards compatibility

A handoff.md **with** YAML frontmatter is handled by the field rules above: `type: handoff` is current, and YAML carrying both `session_end` and `next_step` without `type:` is a v1.12.0–v2.1.0 legacy handoff. Both are read normally and rewritten in the current format.

A handoff.md **without** any frontmatter is NOT assumed to be a handoff (changed in 2.36.1). The old rule — read it as prose, convert it on next write — meant any file sitting at that path got consumed, and the automatic session-start reader then cleared it. At least one project used the path for permanent notes. So:

- **On the automatic read path** (the Session Continuity rule in CLAUDE.md): do not present it, do not clear it. Say in one line that the file holds unrecognized content.
- **When the user explicitly invokes this skill** to save state: writing is what they asked for, so write — but if the existing file has unrecognized content, say what you are replacing in one line first. Overwriting on request is fine; overwriting silently is not.

## Resume is automatic

Resume is NOT part of this skill. It's handled by a CLAUDE.md instruction that runs on every session start and after compact. See the "Session continuity" section in CLAUDE.md.
