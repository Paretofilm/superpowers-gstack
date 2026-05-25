---
name: autoimplement
description: |
  Auto-advance through a multi-phase implementation plan by dispatching a
  subagent per phase, then chaining /review, /pitfall-verification, and
  /codex review at the phase boundary. Skips the y/n prompts a user would
  always answer "yes" to when reviews pass; stops and surfaces when any
  review flags issues. Composes existing skills — does not reimplement
  review logic. Use when asked to "autoimplement", "run this plan
  end-to-end", or "auto-advance through the phases".
---

# autoimplement

Auto-advance through a multi-phase implementation plan by chaining existing
review skills at phase boundaries. Removes the y/n friction the user would
always answer "yes" to anyway.

## When to use

Invoke when the user asks:
- "autoimplement <plan-file>"
- "run this plan end-to-end"
- "auto-advance through the phases"

## Plan path resolution

Before anything else, resolve which plan file to run on. Order of attempts:

1. Absolute path the user gave → use as-is.
2. Relative path that exists from CWD → use.
3. Filename only → look in `docs/superpowers/plans/<filename>`.
4. If none resolve → list available plans in `docs/superpowers/plans/` and ask which.

Read the resolved file in full. From this point on, "the plan" refers to this file.

## Startup checks (enforced by the shipped skill, not just documented)

Before invoking `AskUserQuestion`, before dispatching any subagent, run these
checks in order. Each is a hard refusal — exit with the named reason and do
not proceed.

### Check 1: Workspace is on a feature branch with a clean tree

```bash
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
status=$(git status --porcelain 2>/dev/null || echo "GIT_FAIL")
```

Refuse if:
- `branch` is empty, `main`, `master`, or `GIT_FAIL` → "autoimplement runs only on a feature branch in a git repo. You are on '<branch>'. Create a feature branch first; suggested name: `feat/<plan-slug>`."
- `status` is non-empty → "working tree has uncommitted changes — autoimplement requires a clean tree (so phase commits are unambiguous). Commit or stash, then re-invoke."

### Check 2: Phase count is at least 2

Apply the phase regex to the plan: `^## Phase \d+:` (case-sensitive, line-anchored).

```
phase_count = number of regex matches
```

Refuse if `phase_count < 2`:
- 0 phases → "Plan has no `## Phase N:` headers — re-author with `superpowers:writing-plans` first."
- 1 phase → "Plan has only 1 phase — autoimplement's value is at phase boundaries. Use `superpowers:subagent-driven-development` directly instead."

### Check 3: Every phase has at least one commit step

For each phase body, scan for at least one occurrence of `git commit` (case-insensitive,
across all code fences inside the phase). Refuse if any phase lacks a commit step:

> "Phase <N> ('<title>') has no `git commit` step. autoimplement's clean-tree check between phases requires per-phase commit discipline. Either add commit steps to the plan, or use `superpowers:subagent-driven-development` (which prompts you per task and tolerates uncommitted phase boundaries)."

This catches the common failure mode where a plan describes work but never tells the subagent to commit it — autoimplement would then trigger the dirty-tree refusal at Step A of Phase 2 and stop pointlessly.

**Assumption:** This check looks for literal `git commit` (case-insensitive). Plans that delegate commits to a wrapper script (e.g., `./scripts/commit-phase.sh`) or to another skill (e.g., `/ship`) will false-negative. This is acceptable given that `superpowers:writing-plans` produces literal `git commit` steps by convention. If your plan uses wrappers, either inline the commits or expect this refusal.

### Check 4: No forbidden file paths or write targets

Two scans, both case-insensitive:

**Scan A — `Files:` block paths.** For each phase body, find blocks formatted as
`**Files:**` followed by bullet lines like `- Create: <path>` / `- Modify: <path>` /
`- Test: <path>`. Extract every `<path>`. Refuse if any path matches any of these
regexes (anchored, not substring):

- `(^|/)migrations(/|$)` — migration directories
- `(^|/)\.env(\..*)?$` — `.env` and `.env.*` files
- `(^|[/._-])secrets?([/._-]|$)` — paths containing "secret" or "secrets" as a word (e.g. `app/secrets/`, `prod.secret.yaml`); avoids matching `secretary/`
- `(^|[/._-])credentials?([/._-]|$)` — paths containing "credential" or "credentials" as a word; avoids matching `credentialed-users.md`
- `(^|/)\.ssh/` — SSH directories

**Scan B — shell command writes.** For each phase body, scan code fences for
shell redirection or git operations that write to forbidden paths:

- `>\s*\.env`, `>>\s*\.env` — redirect to .env files
- `git add.*\.env`, `git add.*secret`, `git add.*credential` — staging forbidden files
- `(^|\s)secrets?\s*=`, `(^|\s)password\s*=` in `export`/`echo` lines

If any match in either scan, refuse with the offending path/command quoted:

> "Plan touches forbidden path or writes secret-shaped content: `<offending match>` in Phase <N>. autoimplement refuses on migrations / secrets / credentials / .env / .ssh — these need human-in-the-loop friction. Run the plan manually."

**Fallback when `Files:` blocks are absent in some phases:** Still run Scan B
on all phases. Surface a note when Scan A finds nothing because no `Files:`
blocks exist: *"Note: phase(s) <list> have no `Files:` blocks — only shell-command
scan ran for those. Verify by hand that they don't write to forbidden paths."*

### Check 5: Codex CLI availability (informational, not blocking)

```bash
codex --version 2>/dev/null
```

If absent → set internal flag `CODEX_AVAILABLE=false`. Continue, but the `/codex
review` step in the per-phase procedure will be skipped (with a logged note in
the final summary).

### After all checks pass

Build the phase queue: `phases = [{num, title, body}, ...]` and echo:
> Found N phases. Startup checks: clean. Codex: <available|unavailable>. Asking one policy question, then starting Phase 1.

## Policy question (one, after startup checks pass)

This is **one policy question** — the only friction autoimplement deliberately adds.
It runs only AFTER plan path resolution and startup checks have all passed; refusal
paths upstream may have produced their own prompts, but those are gates, not the
policy question.

Invoke `AskUserQuestion` with:

**Question:** "Stop on any review issue, or treat pitfall/codex as advisory?"
**Header:** "Stop policy"
**Options (2):**
- "Stop on any review issue (recommended)" — pause if `/review`, `/pitfall-verification`, OR `/codex review` flags anything actionable. Matches the manual workflow this skill is replacing.
- "Treat pitfall/codex as advisory (risky)" — `/pitfall-verification` and `/codex review` findings are surfaced but do not pause execution. Use only when you trust them to over-flag and accept the risk that a real correctness/security/data-loss finding will slip through. `/review` failures still always stop. Severe findings (security, data loss, correctness bugs in test assertions) ALWAYS block regardless of this setting — see § Per-phase procedure Step D.

Store the answer as `STOP_POLICY` (string: `any-issue` or `advisory`).

After the answer, echo:
> Stop policy: <STOP_POLICY>. Proceeding through N phases.
