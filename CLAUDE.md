# Superpowers + GStack Manual

## About
This repo contains the combined workflow manual for using Superpowers and GStack with Claude Code.

## Automated update pipeline

A GitHub Action (`.github/workflows/check-updates.yml`) runs weekly and:
1. Checks GStack (`garrytan/gstack`), Superpowers (`obra/superpowers`), and Claude Code (npm) for new versions
2. If changes found, uses Claude API to update the manual automatically
3. Creates a PR with the changes
4. Creates a GitHub issue with `notification` label

A SessionStart hook (`scripts/notify-pending-updates.sh`) notifies the user of pending updates when starting Claude Code.

The update pipeline also keeps `skills/setup-routing/SKILL.md` and `skills/adapt/SKILL.md` in sync — if upstream adds, removes, or renames skills, the skill evaluation tables in both skills are updated automatically.

### Required secret
`ANTHROPIC_API_KEY` must be set in GitHub repo secrets for the Claude API call.

### Self-repair
If the update workflow fails, a second workflow (`.github/workflows/self-repair.yml`) automatically:
1. Reads the error logs from the failed run
2. Sends them to Claude API for diagnosis
3. Applies the fix and validates YAML
4. Creates a PR with label `auto-repair`

### Manual check
Run `./scripts/check-updates.sh` locally for an immediate check.

## Plugin

This repo is also a Claude Code plugin (`superpowers-gstack`). The skill `setup-routing` generates tailored CLAUDE.md files for new projects.

- Install via marketplace: `/plugin marketplace add kjetilge/kjetil-claude-marketplace` then `/plugin install superpowers-gstack@kjetil-plugins`
- Dev mode: `./scripts/install-plugin.sh --dev` (creates symlink, skills won't be discoverable in the skills list)
- Skills:
  - `/superpowers-gstack:setup-routing` — generate CLAUDE.md for new projects
  - `/superpowers-gstack:adapt` — adapt existing projects (preserves CLAUDE.md content)

## Setup

Install via marketplace (in Claude Code):
```
/plugin marketplace add kjetilge/kjetil-claude-marketplace
/plugin install superpowers-gstack@kjetil-plugins
```

For the update notification hook (optional, after cloning the repo):
```bash
./scripts/setup-hooks.sh      # Add SessionStart hook for update notifications
```

## Upstream sources

| Component | Source | Version tracking |
|-----------|--------|-----------------|
| GStack | `garrytan/gstack` | Git commit hash |
| Superpowers | `obra/superpowers` | plugin.json version |
| Claude Code | `@anthropic-ai/claude-code` npm | npm version |

## Session continuity

On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) once work has resumed.

After /compact: if no auto context guard is active, ask the user once: "Context was compressed. Want me to activate auto context guard for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-guard skill.

## Skill conversation discipline

When a skill instructs you to ask the user a question or wait for confirmation, always end your message at that question. Never continue with subsequent steps, suggestions, or "next steps" in the same message. Wait for the user to respond before proceeding.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Save state, context long, before /clear → invoke context-guard
- Code quality, health check → invoke health
