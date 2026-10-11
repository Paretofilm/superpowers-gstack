## Skill routing

This project uses Superpowers + GStack. Each owns a distinct phase.

### GStack — Review & QA, Ship
**Review & QA:** `/review` on every finished change; `/investigate` for bugs found in QA or production
**Ship & Monitor:** `/ship` when the project lands through pull requests; `/superpowers-gstack:land` when it lands solo

### Superpowers — Implementation
- `/superpowers:brainstorming` — finds out why you want the thing before proposing features
- `/superpowers:writing-plans` — the plan you review before anything runs
- `/superpowers:test-driven-development` — runs the project's full test suite, not just the named file
- `/superpowers:systematic-debugging` — bugs found during implementation
- `/superpowers:subagent-driven-development` — 5+ tasks, parallel TDD
- `/superpowers:requesting-code-review` / `/superpowers:receiving-code-review` — multi-file changes, and acting on `/review`

### Routing Logic
- Ready to build → `/superpowers-gstack:vibe` with the vibe profile, `/superpowers:brainstorming` with classic
- Bug during coding → `/superpowers:systematic-debugging`
- Bug found in QA → `/investigate`
- Code complete → `/review`
- Ready to ship → by the `Landing mode:` line
- Trivial change → just do it
- Stack decided (first spec written) → `/superpowers-gstack:adapt` fills in `## Project` below

### Rules
- Never run GStack and Superpowers skills in the same phase
- Never nest subagents from different frameworks
- `/superpowers:systematic-debugging` for bugs found during implementation; `/investigate` only for bugs found in QA or production
- Superpowers specs go in `docs/superpowers/`; GStack state lives in `~/.gstack/projects/`

### Session Management
- `/clear` when transitioning between GStack and Superpowers phases; save architecture decisions to `docs/` first
- Skip `/clear` for small projects (< 5 tasks, < 30 min)

## Project <!-- gstack-project-pending -->

Stack: not yet known — filled in after the first spec. Rows that depend on the stack (`/qa <url>`, `/cso`, the Apple skills) are added then.
