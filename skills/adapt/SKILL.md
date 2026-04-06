---
name: adapt
description: Adapt an existing project to the Superpowers + GStack workflow. Analyzes the project, identifies gaps, updates CLAUDE.md routing without losing existing content, and sets up required structure.
---

# Adapt to Superpowers + GStack

You are adapting an existing project to the Superpowers + GStack combined workflow. Unlike `setup-routing` (which is for new/empty projects), this skill preserves everything that already exists and makes only the changes needed for a smooth transition.

Invoke this skill with: `/superpowers-gstack:adapt`

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

Wait for confirmation.

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
| `/superpowers:requesting-code-review` | Multi-file changes |
| `/superpowers:writing-skills` | Only for Claude Code plugin/skill projects |

**GStack skills — Phase 1 (Planning):**

| Skill | Consider relevant when... |
|---|---|
| `/office-hours` | New product ideas, features with unclear scope |
| `/plan-ceo-review` | Projects with strategic decisions or significant scope |
| `/plan-eng-review` | Projects needing architecture decisions |
| `/plan-design-review` | Projects with UI/UX components |
| `/autoplan` | When all three plan reviews are relevant |

**GStack skills — Phase 3 (Review & QA):**

| Skill | Consider relevant when... |
|---|---|
| `/review` | Almost always — pre-merge code review |
| `/qa <url>` | Projects with a browser-accessible UI (include the URL) |
| `/qa-only <url>` | Same, but report-only |
| `/cso` | Projects handling auth, user data, payments, or external APIs |
| `/design-review` | Projects with visual UI |
| `/investigate` | Bugs discovered AFTER Phase 2 — in QA, staging, or production |

**GStack skills — Phase 4 (Ship & Monitor):**

| Skill | Consider relevant when... |
|---|---|
| `/ship` | Projects using git with feature branches and PRs |
| `/land-and-deploy` | Projects with CI/CD deployment pipelines |
| `/canary` | Projects with production monitoring needs |
| `/document-release` | Projects with documentation to maintain |
| `/retro` | Team projects with regular sprint cadence |
| `/learn` | Long-running projects (> 2 weeks) |
| `/health` | Projects with existing linting, type checking, or test suites |

**GStack skills — Utility:**

| Skill | Consider relevant when... |
|---|---|
| `/careful` | Projects where destructive commands are risky |
| `/freeze` | Monorepos or projects with sensitive directories |
| `/browse` | Projects needing headless browser interaction beyond QA |

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

Wait for confirmation.

### Step 5: Apply changes

Apply the changes identified in Step 4. Follow these rules strictly:

**CLAUDE.md updates:**
- If CLAUDE.md exists: READ it first, then INSERT or UPDATE the `## Skill routing` section
- NEVER delete or rewrite existing sections (conventions, tech stack, project-specific rules)
- If a `## Skill routing` section already exists: REPLACE only that section
- If no `## Skill routing` section exists: ADD it after the first heading (or at the top if no heading)
- The routing section follows the same template as `setup-routing` Step 6, adapted to this project

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
>
> **Next steps:**
> - [suggest the appropriate first action based on project state]
>   - Working on a new feature? → `/superpowers:brainstorming`
>   - Have code ready for review? → `/review`
>   - Starting fresh? → `/office-hours`
>
> **Tip:** Run `/superpowers-gstack:adapt` again after major project changes (new deploy target, added test framework, etc.) to update routing.
