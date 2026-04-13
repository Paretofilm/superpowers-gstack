# Changelog

## [1.3.0] - 2026-04-13

### Added
- **Cross-model quality review** — GStack now includes AI slop reduction with cross-model quality review (v0.16.3.0), improving output quality across all planning and review skills
- **Browser data platform** — New browser data platform for AI agents (v0.16.0.0), enhancing QA and testing capabilities
- **Content security improvements** — 4-layer prompt injection defense for pair-agent and enhanced community security features
- **Team-friendly install mode** — GStack v0.15.7.0 adds team-friendly install mode with automatic symlink detection and vendored copy cleanup

### Changed
- **Office-hours relationship closing** — Office-hours now adapts to repeat users with relationship closing patterns (v0.16.2.0), making subsequent sessions more focused
- **Improved snapshot interactivity** — GStack's snapshot tool now auto-detects dropdown/popover interactive elements, improving QA workflow
- **Enhanced pair-agent reliability** — Fixed pair-agent tunnel drops and improved session stability
- **Better session isolation** — TabSession extraction provides improved per-tab state isolation
- **Deterministic slugs** — gstack-slug now produces consistent slugs across sessions

### Fixed
- **Cookie picker security** — Resolved auth token leak in cookie picker (v0.15.17.0)
- **Auto-symlink detection** — GStack now auto-symlinks into ~/.claude/skills/ when cloned elsewhere
- **Team detection improvements** — gstack-team-init better detects and removes vendored copies

### Technical
- Updated to Claude Code 2.1.104 with improved plugin stability
- All GStack skills updated with latest security and reliability improvements
- Enhanced error handling and session management across both frameworks

## [1.2.0] - 2026-04-07

### Added
- Context Guard skill (`/context-guard`) — lightweight context management inspired by GSD. Saves session state to `docs/superpowers/handoff.md`, auto-resumes after `/clear` or `/compact`, and proactively suggests context resets.
- Session continuity rules in CLAUDE.md template — auto-reads handoff.md on session start, offers auto context guard after `/compact`.
- Auto-mode marker (`## Mode: auto`) in handoff.md for persistent state across compacts.
- CHANGELOG.md is now automatically updated by the GitHub Actions update pipeline.

### Changed
- Consolidated workflow manual into README. Single source of truth — scenarios, quick reference, decision tree all in README now.
- Routing rules clarified: checkpoint = git snapshot (end of day), context-guard = session state (before /clear).
- Stronger "wait for confirmation" instructions in adapt and setup-routing skills (STOP HERE blocks).
- Fixed `/freeze` description in evaluation tables — now correctly described as allow-list, not block-list.
- Plugin description updated to mention context management.
- GitHub Actions workflow updated to use README instead of removed workflow manual.

### Removed
- `superpowers-gstack-workflow-manual.md` — content merged into README.

## [0.0.1.0] - 2026-04-07

### Added
- Marketplace installation as the primary install path. Plugin is now discoverable in Claude Code's skill list after installing via `/plugin marketplace add` + `/plugin install`.
- "Run from project directory" guidance across manual, README, skills, and appendix troubleshooting. Prevents wrong project slug detection and misplaced design docs.
- "Tiny Project" fast-path scenario for projects with fewer than 5 tasks. Skip Phase 1, use executing-plans instead of SDD, tests = spec compliance.
- Design-doc handoff callout in Phase 1→2 transition. "Adopt the design as-is" is now a prominent blockquote instead of a buried tip.
- Directory check in both `setup-routing` and `adapt` skills. Stops the user before they run the skill from the wrong directory.
- Troubleshooting entries for plugin discovery via symlink vs marketplace, and wrong project detection.
- Unknown argument validation in `install-plugin.sh`. Rejects typos like `--Dev` instead of silently printing marketplace instructions.
- GStack skill routing rules in CLAUDE.md.
- Implementation plan for the 4 fixes at `docs/superpowers/plans/`.

### Changed
- `install-plugin.sh` is now dev-only (`--dev` flag). Default behavior prints marketplace install instructions instead of creating a symlink.
- README "Quick Start" renamed to "Kickstart" with tagline and restructured install flow.
- Manual install section split bash commands and Claude Code slash commands into separate code blocks.
- Phase 1 "When to skip" guidance strengthened with explicit small-project threshold (< 5 tasks, < 30 minutes).
