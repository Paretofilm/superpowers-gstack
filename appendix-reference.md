# Appendix: Detailed Reference

This appendix contains operational details, skill internals, troubleshooting, and anti-patterns for the Superpowers + GStack workflow. The [main manual](superpowers-gstack-workflow-manual.md) covers the workflow itself.

---

## Table of Contents

1. [Installation Details](#installation-details)
2. [Skill Deep Dives](#skill-deep-dives)
3. [Session Management Details](#session-management-details)
4. [Troubleshooting](#troubleshooting)
5. [Anti-Patterns](#anti-patterns)

---

## Installation Details

### GStack First-Run Prompts

The first time you use a GStack skill in a new session, it will ask about (in this order):

1. **Boil the Lake principle** — GStack's completeness philosophy (one-time intro)
2. **Telemetry** — anonymous usage data (one-time, can be changed later)
3. **Proactive mode** — whether GStack auto-suggests skills based on context
4. **Cross-project learnings** — whether to search learnings from other projects on this machine (one-time)
5. **CLAUDE.md routing** — whether to add routing rules to your project (skipped if `## Skill routing` header exists)

These are sequential interactive prompts. Expect 4-5 questions before the actual skill work begins. They only happen once per machine/project.

**Note:** `/office-hours` ends with a YC application pitch from Garry Tan. This is baked into the skill and happens every time. It's not a bug — GStack is built by the president of Y Combinator.

### Verify Installation

**You must restart Claude Code** after running setup for skills to be discovered.

After restarting:

```
# Superpowers: ask Claude to brainstorm something — it should 
# automatically invoke the brainstorming skill and ask Socratic questions
"Let's brainstorm a REST API design"

# GStack: run a slash command directly
/office-hours
```

If GStack skills don't appear, verify the symlinks exist: `ls ~/.claude/skills/office-hours/SKILL.md`
If Superpowers skills don't trigger, check: `/plugin list`

### Token Overhead

Both frameworks add system prompt overhead (estimated 50-70K tokens combined before you type anything). This reduces your effective context window. On Claude's standard 200K context, you'll have roughly 130-150K tokens available for actual work. This is manageable but worth knowing — avoid adding unnecessary content to CLAUDE.md.

**Runtime token cost:** Subagent-Driven Development (SDD) dispatches multiple subagents per task: one implementer + one spec reviewer + one code quality reviewer. For a 5-task plan, expect ~10-15 subagent invocations. For small projects (< 5 tasks), consider `/superpowers:executing-plans` (inline) instead — it's faster and cheaper while still following TDD.

**Model selection tip:** SDD supports dispatching implementer subagents with cheaper/faster models (e.g., Haiku) for mechanical tasks. Reserve more capable models for complex integration tasks or reviews. This can significantly reduce cost.

---

## Skill Deep Dives

### `/plan-ceo-review` — Strategic Review Modes

Reviews the design doc and operates in one of four modes:
- **Expansion** — Add capabilities
- **Selective Expansion** — Add specific things
- **Hold Scope** — Validate as-is
- **Reduction** — Cut scope

### `/plan-eng-review` — Architecture Outputs

The Engineering Manager role produces:
- ASCII architecture diagrams
- Data flow maps
- State machines
- Failure mode analysis
- Test matrices

This is your architectural contract. Implementation in Phase 2 must follow it.

### `/superpowers:subagent-driven-development` — SDD Process

For each task in the plan:

1. A **fresh subagent** is spawned with clean context
2. The subagent writes a **failing test first** (RED)
3. Runs the test to **verify it fails**
4. Writes **minimal code** to pass (GREEN)
5. Runs the test to **verify it passes**
6. **Refactors** if needed
7. **Commits** the work
8. A **spec-reviewer subagent** verifies the implementation matches the spec
9. A **code-quality-reviewer subagent** checks code quality

The orchestrator tracks progress and handles escalations.

### `/superpowers:systematic-debugging` — 4-Phase Process

1. Observe — gather evidence
2. Hypothesize — form theories
3. Test — validate one theory at a time
4. Fix — only after root cause is confirmed

**Iron Law:** No fixes allowed before Phase 1 completes.

### `/review` — What It Checks

GStack's Staff Engineer role performs a pre-landing review:
- SQL safety analysis
- LLM trust boundary checks
- Conditional side effect detection
- **Scope drift detection** — compares the diff against the original plan
- Plan completion audit

Auto-fixes obvious issues, flags the rest.

**Prerequisites:** `/review` diffs the current branch against the base branch (usually `main` via remote). It requires a **feature branch** (not `main` itself) and a **remote** configured (`origin`). If you're on `main` with no remote, `/review` will say "nothing to review." Create a feature branch first.

**Auto-fix caution:** If `/review` makes auto-fixes, re-run your test suite before proceeding. GStack's auto-fixes don't go through Superpowers' TDD cycle, so they could introduce regressions.

### `/qa` — Browser Testing Process

**Note:** The first `/qa` call in a session takes ~3 seconds to start the Playwright browser daemon. Subsequent calls are fast (~100-200ms). The browser persists cookies, localStorage, and tabs across calls and shuts down after 30 minutes idle.

GStack's QA Lead opens a real browser (Playwright) and:
1. Navigates to your app
2. Takes accessibility tree snapshots
3. Clicks through user flows
4. Finds bugs
5. Fixes them in source code with atomic commits
6. Generates regression tests for every fix
7. Re-verifies in the browser

### `/cso` — Security Audit Details

Chief Security Officer role runs:
- OWASP Top 10 analysis
- STRIDE threat modeling
- 17 false-positive exclusions to reduce noise
- 8/10+ confidence gate (only reports high-confidence findings)

### `/ship` — Full Process

The Release Engineer role:
1. Detects platform (GitHub/GitLab) and base branch automatically
2. Shows Review Readiness Dashboard (see below)
3. Syncs with main branch (fetch + merge)
4. Detects test framework and runs full test suite
5. Runs test coverage audit (traces code paths, generates coverage diagram)
6. Checks plan completion (if plan file exists in `~/.gstack/projects/`)
7. Runs pre-landing code review with confidence-scored findings
8. Dispatches specialist reviewers for large diffs (security, performance, etc.)
9. Runs adversarial review (Claude subagent + Codex if available)
10. Creates VERSION file and CHANGELOG.md (auto-decides bump level)
11. Commits in bisectable chunks
12. Pushes and creates PR with structured body
13. Auto-invokes `/document-release` to sync docs

**What to expect:** `/ship` is fully automated and non-interactive for most cases. It only stops for merge conflicts, test failures, MINOR/MAJOR version bumps, or review findings that need judgment. For a clean branch, it runs straight through and outputs the PR URL.

**VERSION format:** 4-digit `MAJOR.MINOR.PATCH.MICRO`. Ship auto-picks MICRO (< 50 lines) or PATCH (50+ lines). MINOR and MAJOR require confirmation.

**Note:** If no VERSION or CHANGELOG exists, `/ship` creates them.

**Review Readiness Dashboard:** Before running its own review, `/ship` shows which GStack reviews have already been completed for this branch:

| Status | Meaning |
|--------|---------|
| **CLEARED** | Review was run and passed — `/ship` trusts the result and skips re-running it |
| **NOT CLEARED** | Review was not run — `/ship` runs its own lighter version inline |

The dashboard checks for: code review (`/review`), QA (`/qa`), security (`/cso`), and design review (`/design-review`). Running `/review` and `/cso` before `/ship` gives the most thorough pipeline.

### `/investigate` — When to Use

Use `/investigate` for bugs discovered **during Phase 3** — issues found by `/qa`, `/cso`, or manual testing that weren't caught during Phase 2. GStack's `/investigate` does root cause analysis without TDD enforcement.

**Important:** Do NOT use `/investigate` during Phase 2 implementation. Use `/superpowers:systematic-debugging` instead — it enforces TDD.

| Bug discovered during... | Use |
|--------------------------|-----|
| Phase 2 (implementation) | `/superpowers:systematic-debugging` |
| Phase 3 (QA/review) | `/investigate` |
| Production | `/investigate` |

---

## Session Management Details

### GStack Upgrade Checks

Every GStack skill preamble checks for available upgrades. If one is found, it will prompt you with options (upgrade now, snooze, etc.) before the skill runs. This can interrupt workflow. If you want uninterrupted flow, upgrade first: `cd ~/.claude/skills/gstack && git pull && ./setup`.

### GStack Preamble Output

Every GStack skill prints a preamble block at the start:

| Field | Meaning |
|-------|---------|
| `BRANCH` | Current git branch name |
| `PROACTIVE` | Whether GStack will auto-suggest skills based on context (`true`/`false`) |
| `TEL_PROMPTED` | Whether telemetry consent has been asked (`true` = won't ask again) |
| `LEARNINGS` | Whether cross-project learnings search is enabled |
| `UPGRADE` | Shows available upgrade version, or `current` if up to date |

This output is informational — you don't need to act on it.

### Long Implementation Sessions

If a Superpowers implementation session runs long:
- The SessionStart hook re-injects Superpowers instructions on `/clear` or compact
- Subagents always get fresh context regardless
- Watch for signs of context degradation: repeated mistakes, forgetting earlier decisions

### Pausing Work

If you need to stop mid-implementation:
1. Let the current subagent task complete
2. The plan in `docs/superpowers/plans/` tracks what's done
3. On resume, run `/superpowers:subagent-driven-development` — it reads the plan and continues

---

## Troubleshooting

### GStack skill doesn't trigger

**Symptom:** You type `/office-hours` and Claude says it doesn't recognize the command.

**Fix:** Verify symlinks exist: `ls ~/.claude/skills/office-hours/SKILL.md`. If missing, re-run `cd ~/.claude/skills/gstack && ./setup`. You must restart Claude Code after setup.

### Superpowers skill doesn't trigger

**Symptom:** You say "let's brainstorm" but Superpowers doesn't activate.

**Fix:** Check `/plugin list` — Superpowers should be listed. If not, reinstall: `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`. Restart Claude Code.

### superpowers-gstack skills not found

**Symptom:** Running `/superpowers-gstack:setup-routing` or `/superpowers-gstack:adapt` returns "Unknown skill" even though the plugin files exist.

**Cause:** The plugin was installed via symlink (`./scripts/install-plugin.sh` without `--dev`) instead of via marketplace. Symlinks place the files in `~/.claude/plugins/` but don't register in `installed_plugins.json`, so Claude Code's skill discovery doesn't find the skills.

**Fix:** Remove the symlink and install via marketplace:

```bash
rm ~/.claude/plugins/superpowers-gstack   # remove symlink
```

Then reinstall via marketplace (see [Kickstart](README.md#kickstart) for the commands). Restart Claude Code. Verify with `/plugin list` — `superpowers-gstack` should appear.

**Note:** `./scripts/install-plugin.sh --dev` is for local development only — skills won't be discoverable but you can read them directly.

### Wrong framework responds

**Symptom:** You ask to implement something and GStack's `/investigate` activates instead of Superpowers' debugging.

**Fix:** Add the `## Skill routing` section to your project's CLAUDE.md (see [Project CLAUDE.md Setup](superpowers-gstack-workflow-manual.md#project-claudemd-setup)). Without routing rules, Claude guesses based on context and often picks wrong.

### `/review` says "nothing to review"

**Symptom:** You have code changes but `/review` finds nothing.

**Fix:** You're likely on `main` with no remote. `/review` diffs against the remote base branch. Create a feature branch (`git checkout -b feature/name`) and push it (`git push -u origin feature/name`).

### `/ship` fails at PR creation

**Symptom:** Tests pass but PR creation fails.

**Fix:** Ensure: (1) you're on a feature branch, not main; (2) the branch is pushed to remote with `-u`; (3) `gh auth status` shows you're authenticated.

### Wrong project detected / design docs filed under wrong project

**Symptom:** GStack detects the wrong project slug (e.g., `Paretofilm-superpowers-gstack` instead of your project). Design docs are saved under `~/.gstack/projects/` with the wrong name. `/review` checks the wrong CLAUDE.md.

**Cause:** Claude Code was started from a different directory than the target project.

**Fix:** Start a new Claude Code session from the project directory:

```bash
cd /path/to/your-project
claude
```

Both GStack and the routing skills detect project context from the working directory. There is no way to override this mid-session.

### Subagent runs out of context

**Symptom:** SDD subagent produces incomplete code or misses requirements.

**Fix:** The task in `docs/superpowers/plans/` may be too large. Edit the plan to split it into smaller tasks (2-5 minutes each). Re-run `/superpowers:subagent-driven-development`.

---

## Anti-Patterns

### 1. Mixing Frameworks in One Phase
**Wrong:** Running `/superpowers:brainstorming` then `/plan-ceo-review` then `/superpowers:writing-plans`.
**Right:** Complete all GStack planning, then transition to Superpowers for implementation.

### 2. Skipping TDD During Implementation
**Wrong:** Using GStack's `/review` to catch bugs after writing code without tests.
**Right:** Let Superpowers enforce TDD. GStack review catches what tests missed.

### 3. Mixing Debugging Tools
**Wrong:** Using GStack's `/investigate` for bugs found during Phase 2 implementation.
**Right:** During Phase 2, use Superpowers' `/superpowers:systematic-debugging` — it follows TDD (writes a failing test reproducing the bug, then fixes it). Use GStack's `/investigate` for bugs discovered outside the implementation flow (production issues, bugs found during Phase 3 QA, or bugs reported by users). Both are valid debugging tools, but they serve different contexts.

### 4. Nesting Subagents
**Wrong:** A Superpowers subagent spawning a GStack skill.
**Right:** Each framework's subagents stay within their own framework.

### 5. Skipping `/clear` Between Phases
**Wrong:** Going straight from a long implementation session into `/review`.
**Right:** `/clear` first, then `/review` with fresh context.

### 6. Over-Engineering Small Changes
**Wrong:** Running the full 4-phase workflow for a one-line config change.
**Right:** Just make the change. Use the frameworks when they add value.

### 7. Confusing the Code Reviews
**Wrong:** Running both `/superpowers:requesting-code-review` (Superpowers) and `/review` (GStack) at the same point.
**Right:** They serve different purposes:
- **Superpowers' code review** (via SDD) runs automatically during Phase 2 after each task — checks spec compliance and code quality within the implementation context.
- **GStack's `/review`** runs in Phase 3 — a pre-merge review that checks the entire diff for SQL safety, scope drift, trust boundaries, and auto-fixes obvious issues.
- **Superpowers' `/superpowers:receiving-code-review`** handles feedback from GStack's `/review` or PR reviews — structures the findings into TDD tasks and implements fixes.
They are complementary layers, not alternatives. Don't skip either.

### 8. Running All GStack Reviews Every Time
**Wrong:** Always running CEO, design, eng, security, and QA reviews.
**Right:** Choose reviews based on what changed. A backend API change doesn't need `/design-review`. A CSS fix doesn't need `/cso`.

### 9. Shipping from Main Branch
**Wrong:** Doing all implementation on `main`, then running `/ship`.
**Right:** Create a feature branch before Phase 2. `/ship` requires a feature branch to create a PR. If you already committed to main, create a branch retroactively: `git checkout -b feature/name`.

### 10. Running `/ship` Without a Remote
**Wrong:** Running `/ship` on a local-only branch with no upstream.
**Right:** Push the branch first (`git push -u origin <branch>`), then run `/ship`.
