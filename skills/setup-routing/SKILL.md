---
name: setup-routing
description: Generate a tailored CLAUDE.md with routing rules for the Superpowers + GStack workflow. Asks about project type, evaluates relevant skills from both frameworks, and produces a project-specific routing plan.
---

# Setup Routing — CLAUDE.md Generator

You are setting up the Superpowers + GStack combined workflow for a **new project**. Your job is to generate a `CLAUDE.md` file with routing rules tailored to this specific project.

Invoke this skill with: `/superpowers-gstack:setup-routing`

<!-- Keep in sync with skills/adapt/SKILL.md directory check -->
**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:setup-routing` again.

**Important:** If the project already has a `CLAUDE.md` file with existing content, STOP and suggest the user runs `/superpowers-gstack:adapt` instead — it preserves existing content while adding routing.

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Ask about the project

Ask the user ONE question:

> What kind of project is this? (e.g., Swift iOS app, React/Next.js web app, Python API, Node.js backend, Flutter mobile app, Claude Code plugin/skill, data pipeline, infrastructure/Terraform, monorepo, static site, or describe it)

**STOP HERE.** Do not continue to the next step until the user responds. End your message with the question.

### Step 2: Ask follow-up questions

Based on the project type, ask 3-5 focused follow-up questions. Always include questions 1-3. Add 4-5 based on relevance:

1. What test framework will you use? (or "no tests yet")
2. Will this be deployed? Where? (or local-only)
3. Any security concerns? (auth, user data, payments, external APIs — helps evaluate `/cso`)
4. Will this have a UI testable in a browser? What URL? (skip for CLI tools, libraries, pipelines)
5. Is there a design component? (UI mockups, design system — skip for backend-only)
6. Is this a team project with a regular cadence? (helps evaluate `/retro`)
7. Is this a long-running project or a one-off? (helps evaluate `/learn`)
8. Do you have existing linting, type checking, or test suites? (helps evaluate `/health`)
9. Is this a monorepo? Which directory will you work in? (helps evaluate `/freeze`)

Ask all follow-up questions in a single message. **STOP HERE.** Do not continue to the next step until the user responds. Do not add suggestions or any other content after the questions. End your message with the questions.

### Step 3: Evaluate relevant Superpowers skills

Based on the project type and answers, evaluate which Superpowers skills are relevant. Think through each one:

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

### Step 4: Evaluate relevant GStack skills

Think through each GStack skill, organized by phase:

**Phase 1 — Planning:**

| Skill | Consider relevant when... |
|---|---|
| `/office-hours` | New product ideas, features with unclear scope |
| `/plan-ceo-review` | Projects with strategic decisions or significant scope |
| `/plan-eng-review` | Projects needing architecture decisions |
| `/plan-design-review` | Projects with UI/UX components |
| `/autoplan` | When all three plan reviews are relevant — chains them automatically |

**Phase 3 — Review & QA:**

| Skill | Consider relevant when... |
|---|---|
| `/review` | Almost always — pre-merge code review |
| `/qa <url>` | Projects with a browser-accessible UI (include the URL) |
| `/qa-only <url>` | Same, but report-only (no auto-fixes) |
| `/cso` | Projects handling auth, user data, payments, or external APIs. For security-critical features, run BEFORE `/review` |
| `/design-review` | Projects with visual UI — catches spacing, alignment, inconsistencies |
| `/investigate` | Bugs discovered AFTER Phase 2 — in QA, staging, or production. Do NOT use during Phase 2 implementation (use `/superpowers:systematic-debugging` instead) |

**Phase 4 — Ship & Monitor:**

| Skill | Consider relevant when... |
|---|---|
| `/ship` | Projects using git with feature branches and PRs |
| `/land-and-deploy` | Projects with CI/CD deployment pipelines |
| `/canary` | Projects with production monitoring needs |
| `/document-release` | Projects with documentation to maintain |
| `/retro` | Team projects with regular sprint cadence |
| `/learn` | Long-running projects (> 2 weeks) — saves cross-session learnings |
| `/health` | Projects with existing linting, type checking, or test suites |

**Utility (any phase):**

| Skill | Consider relevant when... |
|---|---|
| `/careful` | Projects where destructive commands are risky (production DBs, shared infra) |
| `/freeze` | Monorepos or projects where edits should be restricted TO a specific directory (allow-list, not block-list) |
| `/browse` | Projects needing headless browser interaction beyond QA |
| `/context-guard` | Long implementation sessions, projects using SDD, or any multi-step workflow |

### Step 5: Present the routing plan

Show the user which skills from each framework you've selected and why. Format as:

**Superpowers (implementation):**
- Skill — why it's relevant

**GStack (by phase):**
- Phase 1: Skill — why
- Phase 3: Skill — why
- Phase 4: Skill — why

**Excluded:**
- Skill — why it's not relevant for this project

Ask: "Does this look right? Any skills to add or remove?"

**STOP HERE.** Do not continue to the next step until the user responds. Do not generate the CLAUDE.md or add any other content. End your message with the question.

If the user wants changes, update your selection and re-present. Repeat until confirmed.

### Step 6: Generate CLAUDE.md

Generate the `CLAUDE.md` file in the project root. Adapt the structure below based on what's relevant — omit entire sections that don't apply.

```markdown
# [Project Name]

## Skill routing

This project uses Superpowers + GStack. Each owns a distinct phase:

### GStack — [list relevant phases, e.g., "Planning, Review, Shipping"]

**Planning:**
- [Only skills selected in Step 4, Phase 1]

**Review & QA:**
- [Only skills selected in Step 4, Phase 3]

**Ship & Monitor:**
- [Only skills selected in Step 4, Phase 4]

### Superpowers — Implementation
- [Only skills selected in Step 3]

### Routing Logic
[Generate a project-specific decision tree. See examples below.]

### Rules
- Never run GStack and Superpowers skills in the same phase
- Never nest subagents from different frameworks
- Use `/superpowers:systematic-debugging` for bugs found during implementation (Phase 2)
- Use `/investigate` only for bugs found in QA or production (Phase 3+)
- Superpowers specs go in `docs/superpowers/`
- GStack state lives in `~/.gstack/projects/`

### Session Continuity

On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) once work has resumed.

After /compact: if no auto context guard is active, ask the user once: "Context was compressed. Want me to activate auto context guard for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-guard skill.

### Session Management
- `/clear` when transitioning between GStack and Superpowers phases
- Save architecture decisions to `docs/` before clearing after Phase 1
- Reference key changes when starting Phase 3 review
- Skip `/clear` for small projects (< 5 tasks, < 30 min)

## Project

### Tech Stack
[From user answers]

### Testing
[Test framework and commands]

### QA
[QA URL if applicable — omit this section if no browser UI]

### Deployment
[Deployment target — omit if local-only]
```

**Routing Logic examples** — adapt to the project, don't copy verbatim:

For a web app with UI:
```
New feature idea     → /office-hours
Ready to build       → /superpowers:brainstorming
Bug during coding    → /superpowers:systematic-debugging
Bug found in QA      → /investigate
Code complete        → /review → /qa http://localhost:3000
Review feedback?     → /superpowers:receiving-code-review → fix → /review again
Security-sensitive?  → /cso (before /review)
Ready to ship        → /ship
Trivial change       → Just do it
```

For a CLI tool / library (no UI):
```
New feature idea     → /office-hours
Ready to build       → /superpowers:brainstorming
Bug fix              → /superpowers:systematic-debugging
Code complete        → /review
Review feedback?     → /superpowers:receiving-code-review → fix → /review again
Ready to ship        → /ship
Trivial change       → Just do it
```

For a Claude Code plugin:
```
New skill idea       → /superpowers:brainstorming
Writing skills       → /superpowers:writing-skills
Bug fix              → /superpowers:systematic-debugging
Code complete        → /review
Ready to ship        → /ship
```

**Important rules for generation:**
- Do NOT include skills that were excluded in Step 5
- Do NOT add generic descriptions — keep it actionable
- DO adapt the routing logic to this specific project type
- DO include the default QA URL if the user provided one
- DO include test commands if known
- Omit entire sections that don't apply (no empty "QA: N/A" sections)
- Target 60-100 lines total. The CLAUDE.md compliance budget is ~150 lines — leave room for the user to add conventions later

### Step 7: Confirm

After writing the file, tell the user:
- What was generated and which skills were included
- Remind them to add project-specific conventions as they develop them
- Suggest next step based on project type (usually `/office-hours` for new ideas or `/superpowers:brainstorming` if scope is already clear)
