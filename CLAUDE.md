# Superpowers + GStack Manual

## About
This repo contains the combined workflow manual for using Superpowers and GStack with Claude Code.

## Automated update pipeline

A GitHub Action (`.github/workflows/check-updates.yml`) runs weekly and:
1. Checks GStack (`garrytan/gstack`), Superpowers (`obra/superpowers`), and Claude Code (npm) for new versions
2. If changes found, uses Claude API to update the manual automatically
3. Creates a PR with the changes
4. Creates a GitHub issue with `notification` label

A SessionStart hook notifies the user of pending updates when starting Claude Code.

The update pipeline also keeps `skills/setup-routing/SKILL.md` in sync — if upstream adds, removes, or renames skills, the skill evaluation tables are updated automatically.

### Required secret
`ANTHROPIC_API_KEY` must be set in GitHub repo secrets for the Claude API call.

### Manual check
Run `./scripts/check-updates.sh` locally for an immediate check.

## Plugin

This repo is also a Claude Code plugin (`superpowers-gstack`). The skill `setup-routing` generates tailored CLAUDE.md files for new projects.

- Install: `./scripts/install-plugin.sh` (creates symlink in `~/.claude/plugins/`)
- The install is verified automatically on every `check-updates.sh` run
- After install, use `/superpowers-gstack:setup-routing` in any project

## Setup

Run all setup scripts after cloning:

```bash
./scripts/install-plugin.sh   # Symlink plugin to ~/.claude/plugins/
./scripts/setup-hooks.sh      # Add SessionStart hook for update notifications
```

## Upstream sources

| Component | Source | Version tracking |
|-----------|--------|-----------------|
| GStack | `garrytan/gstack` | Git commit hash |
| Superpowers | `obra/superpowers` | plugin.json version |
| Claude Code | `@anthropic-ai/claude-code` npm | npm version |
