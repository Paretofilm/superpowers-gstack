---
name: adapt
description: Adapt an existing project to the Superpowers + GStack workflow. Analyzes the project, identifies gaps, updates CLAUDE.md routing without losing existing content, and sets up required structure.
---

# Adapt to Superpowers + GStack

You are adapting an existing project to the Superpowers + GStack combined workflow. Unlike `setup-routing` (which is for new/empty projects), this skill preserves everything that already exists and makes only the changes needed for a smooth transition.

Invoke this skill with: `/superpowers-gstack:adapt`

<!-- Keep in sync with skills/setup-routing/SKILL.md dependency + directory checks -->
**Dependency check:** Before anything else, verify both upstream frameworks are installed. Run:

```bash
ls -d ~/.claude/plugins/cache/claude-plugins-official/superpowers/*/ 2>/dev/null | head -1
ls -d ~/.claude/skills/gstack/ 2>/dev/null
```

If either path is missing, STOP and tell the user:

> This plugin is glue for two upstream frameworks. Install them first:
>
> **Missing: Superpowers** — `/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`
>
> **Missing: GStack** — `git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup`
>
> Only mention the framework(s) that are actually missing. Restart Claude Code after installing, then run `/superpowers-gstack:adapt` again.

Do NOT proceed until both frameworks are present.

**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:adapt` again.

**Version check:** This skill is version **1.8.1**. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation.

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Analyze the project

Read and analyze the following (skip any that don't exist):

1. **CLAUDE.md** — existing instructions, conventions, routing rules
2. **Package files** — `package.json`, `Package.swift`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, `plugin.json`, etc.
3. **Test configuration** — `jest.config.*`, `vitest.config.*`, `pytest.ini`, `.swiftpm/`, `Makefile` test targets, etc.
4. **CI/CD** — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.
5. **Git state** — current branch, remotes, branching strategy (check recent branch names)
6. **Project structure** — `ls` the root and key directories to understand the layout
7. **docs/** — existing documentation structure

Summarize what you found to the user. Be concise — focus on what matters for the transition.

### Step 2: Identify the project type and stack

Based on Step 1, determine:
- Project type (web app, API, mobile, plugin, library, monorepo, etc.)
- Language(s) and frameworks
- Test framework and how to run tests
- Deploy target (if any)
- QA URL (if browser-testable)
- Whether it's a team or solo project

Present this to the user for confirmation:

> Based on my analysis, this is a **[type]** using **[stack]**. Tests run with `[command]`. [Deployed to X / Local-only]. [Has browser UI at X / No browser UI].
>
> Is this correct? Anything to add?

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

### Step 3: Evaluate relevant skills

Use the same evaluation tables as `setup-routing` to determine which Superpowers and GStack skills are relevant. The tables are reproduced here for reference:

**Superpowers skills:**

| Skill | Consider relevant when... |
|---|---|
| `/superpowers:brainstorming` | Almost always — skip only for trivial projects |
| `/superpowers:writing-plans` | Almost always — skip only for single-file changes |
| `/superpowers:subagent-driven-development` | Projects with 5+ tasks, benefits from parallel TDD |
| `/superpowers:executing-plans` | Smaller projects (< 5 tasks), or when user wants more control |
| `/superpowers:systematic-debugging` | Any project with code that can have bugs |
| `/superpowers:dispatching-parallel-agents` | Projects with clearly independent modules |
| `/superpowers:using-git-worktrees` | Projects where feature isolation matters |
| `/superpowers:finishing-a-development-branch` | Projects using feature branches and PRs |
| `/superpowers:test-driven-development` | Projects with testable code (most projects) |
| `/superpowers:verification-before-completion` | Complex projects where correctness is critical |
| `/superpowers:requesting-code-review` | Multi-file changes (runs automatically during SDD, but can be invoked manually) |
| `/superpowers:receiving-code-review` | After `/review` or PR feedback requires code changes — structures the response with TDD |
| `/superpowers:writing-skills` | Only for Claude Code plugin/skill projects |

**GStack skills — Phase 1 (Planning):**

| Skill | Consider relevant when... |
|---|---|
| `/office-hours` | New product ideas, features with unclear scope |
| `/plan-ceo-review` | Projects with strategic decisions or significant scope |
| `/plan-eng-review` | Projects needing architecture decisions |
| `/plan-design-review` | Projects with UI/UX components |
| `/design-consultation` | New projects defining a design system from scratch (creates DESIGN.md) |
| `/design-shotgun` | When you want multiple design variants to compare before committing |
| `/plan-devex-review` | Projects with developer-facing surfaces (APIs, CLIs, SDKs, libraries) |
| `/plan-tune` | Tune plan-skill question preferences (one-time, per-project) |
| `/autoplan` | When all three plan reviews are relevant — chains them automatically |

**GStack skills — Phase 3 (Review & QA):**

| Skill | Consider relevant when... |
|---|---|
| `/review` | Almost always — pre-merge code review |
| `/qa <url>` | Projects with a browser-accessible UI (include the URL) |
| `/qa-only <url>` | Same, but report-only (no auto-fixes) |
| `/cso` | Projects handling auth, user data, payments, or external APIs. For security-critical features, run BEFORE `/review` |
| `/design-review` | Projects with visual UI — catches spacing, alignment, inconsistencies |
| `/design-html` | When you have an approved design and need production HTML/CSS |
| `/devex-review` | Developer-facing projects — live audit of onboarding flow, docs, CLI help |
| `/investigate` | Bugs discovered AFTER Phase 2 — in QA, staging, or production. Do NOT use during Phase 2 implementation (use `/superpowers:systematic-debugging` instead) |

**GStack skills — Phase 4 (Ship & Monitor):**

| Skill | Consider relevant when... |
|---|---|
| `/ship` | Projects using git with feature branches and PRs |
| `/land-and-deploy` | Projects with CI/CD deployment pipelines |
| `/canary` | Projects with production monitoring needs |
| `/landing-report` | Read-only PR queue + sibling-workspace dashboard (workspace-aware ship) |
| `/setup-deploy` | One-time: configure deploy platform (Fly.io, Vercel, Render, etc.) for `/land-and-deploy` |
| `/document-release` | Projects with documentation to maintain |
| `/retro` | Team projects with regular sprint cadence |
| `/learn` | Long-running projects (> 2 weeks) — saves cross-session learnings |
| `/setup-gbrain` | Long-running projects wanting cross-session memory (PGLite local or Supabase) |
| `/health` | Projects with existing linting, type checking, or test suites |
| `/make-pdf` | Projects needing publication-quality documentation or reports |

**GStack skills — Utility:**

| Skill | Consider relevant when... |
|---|---|
| `/careful` | Projects where destructive commands are risky (production DBs, shared infra) |
| `/freeze` | Monorepos or projects where edits should be restricted TO a specific directory (allow-list, not block-list) |
| `/unfreeze` | Clear the `/freeze` boundary mid-session without ending the session |
| `/guard` | Production / shared-infra work — combines `/careful` warnings with `/freeze` directory lock |
| `/browse` | Projects needing headless browser interaction beyond QA |
| `/open-gstack-browser` | Projects wanting a visible AI-controlled Chromium with live activity feed |
| `/pair-agent` | When pairing a remote AI agent with your browser session |
| `/setup-browser-cookies` | One-time: import cookies for authenticated `/qa` and `/browse` testing |
| `/context-handoff` | Long implementation sessions, projects using SDD, or any multi-step workflow |
| `/context-save` | Save progress and working state |
| `/context-restore` | Resume where you left off |
| `/benchmark` | Projects with performance monitoring needs |
| `/benchmark-models` | Projects comparing AI model performance |
| `/codex` | Projects needing second opinions or adversarial code review |

### Step 4: Identify gaps and plan changes

Compare the current project state against what Superpowers + GStack needs. Check each item:

**CLAUDE.md routing:**
- [ ] Does `## Skill routing` section exist?
- [ ] Does it include the correct skills for this project?
- [ ] Does it have Routing Logic, Rules, and Session Management?
- [ ] Is there existing content that must be preserved?

**Project structure:**
- [ ] Does `docs/superpowers/` exist? (needed for specs and plans)
- [ ] Is there a feature branch workflow? (needed for `/review` and `/ship`)
- [ ] Is there a remote configured? (needed for `/review` and `/ship`)

**Potential conflicts:**
- [ ] Does CLAUDE.md have instructions that contradict the workflow? (e.g., "never use subagents", "don't use TDD")
- [ ] Are there existing hooks or workflows that might conflict?
- [ ] Is the project on `main` with no branches? (needs branching strategy)

Present the gap analysis to the user:

> **Ready for Superpowers + GStack:**
> - [things that already work]
>
> **Needs changes:**
> - [what needs to be added/modified — be specific]
>
> **Potential conflicts:**
> - [anything that might cause issues]
>
> Shall I proceed with these changes?

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

### Step 5: Apply changes

Apply the changes identified in Step 4. Follow these rules strictly:

**CLAUDE.md updates:**
- Read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Add or update an HTML comment at the very top of CLAUDE.md: `<!-- superpowers-gstack: {version} -->`
- If CLAUDE.md exists: READ it first, then INSERT or UPDATE the `## Skill routing` section
- NEVER delete or rewrite existing sections (conventions, tech stack, project-specific rules)
- If a `## Skill routing` section already exists: REPLACE only that section
- If no `## Skill routing` section exists: ADD it after the first heading (or at the top if no heading)
- The routing section follows the same template as `setup-routing` Step 6, adapted to this project
- If no `## Session Continuity` section exists in CLAUDE.md: ADD the following block. If it already exists, REPLACE it with the current version:
  ```
  ## Session Continuity
  On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) immediately after presenting the summary.
  After /compact: if handoff.md does not contain `## Mode: auto`, ask the user once: "Context was compressed. Want me to activate auto context guard for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill.
  ```

**Structure setup:**
- Create `docs/superpowers/specs/` and `docs/superpowers/plans/` if they don't exist
- Add a `.gitkeep` in each empty directory

**Git preparation:**
- If on `main` with uncommitted work: warn the user, do NOT create branches automatically
- If on `main` with clean state: suggest creating a feature branch for the adaptation itself

**What NOT to change:**
- Existing test configuration
- CI/CD pipelines
- Git hooks (unless they directly conflict)
- Code style / linting configuration
- Any existing CLAUDE.md content outside the routing section

### Step 6: Verify and report

After applying changes, verify:
1. Read the updated CLAUDE.md and confirm routing section is correct
2. Confirm `docs/superpowers/` directories exist
3. Check that no existing content was lost

Report to the user:

> **Changes made:**
> - [list each change]
>
> **Preserved:**
> - [existing CLAUDE.md content that was kept]

Then ask:

> Would you like me to run a comprehensive review of the adaptation? This will check that:
> - All routing rules are consistent with your project structure
> - No existing CLAUDE.md content was lost or corrupted
> - The selected skills match your actual tech stack, test setup, and deployment
> - docs/superpowers/ structure is correct
> - There are no conflicts between existing project conventions and the new workflow
>
> The review takes a minute but catches issues before you start using the workflow. Recommended for projects with complex existing setups.

**STOP HERE.** Do not continue to Step 7 or add any other content. End your message with the question above. Wait for the user's response before proceeding.

If the user says yes, run the review:

1. **Re-read the updated CLAUDE.md** end-to-end and check for internal consistency
2. **Cross-check routing against project files** — does the routing reference skills that don't make sense? (e.g., `/qa` listed but no browser UI, `/cso` listed but no auth/user data)
3. **Verify preserved content** — diff the old vs new CLAUDE.md mentally. Was anything accidentally removed or mangled?
4. **Check for contradictions** — do existing CLAUDE.md instructions conflict with the new routing rules?
5. **Validate structure** — do all referenced directories exist? (`docs/superpowers/specs/`, `docs/superpowers/plans/`)
6. **Test routing logic** — walk through 3-4 common scenarios for this project type and verify the decision tree produces the right skill

Report findings. If issues are found, fix them immediately and re-verify.

### Step 7: Suggest next steps

After the review (or if the user skipped it):

> **Next steps:**
> - [suggest the appropriate first action based on project state]
>   - Working on a new feature? → `/superpowers:brainstorming`
>   - Have code ready for review? → `/review`
>   - Starting fresh? → `/office-hours`
>
> **Tip:** Run `/superpowers-gstack:adapt` again after major project changes (new deploy target, added test framework, etc.) to update routing.
