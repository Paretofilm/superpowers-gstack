# Changelog

## [1.4.0] - 2026-04-20

### Added
- **New skill**: `/make-pdf` — Markdown to publication-quality PDFs for technical documents and reports
- **New skill**: `/benchmark-models` — Cross-model benchmark comparing Claude, GPT, and Gemini side-by-side for latency, tokens, cost, and quality
- **New skill**: `/learn` — Save cross-session learnings for long-running projects (> 2 weeks)
- **New skill**: `/codex` — OpenAI Codex CLI wrapper with three modes: code review, adversarial challenge, and consultation

### Changed
- **Skill renamed**: `/checkpoint` → `/context-save` and `/context-restore` — Claude Code was treating `/checkpoint` as a native rewind alias, causing conflicts
- `/cso` upgraded to version 2.0.0 with enhanced security audit capabilities
- `/browse` upgraded to version 1.1.0 with Puppeteer parity features including load-html, screenshot selectors, viewport scaling, and file:// support
- Updated Quick Reference with new and renamed skills
- All routing rules and CLAUDE.md templates updated to use new skill names

### Updated upstream versions
- GStack: Major version 1.0.0+ with simpler prompts and improved performance metrics
- Claude Code: 2.1.114 (from 2.1.92) with various stability improvements

### Fixed
- `/ship` now detects and repairs VERSION/package.json drift in Step 12
- Context management improvements for `/plan-ceo-review` and `/office-hours`
- Browser session management with auto-shutdown and disconnect cleanup
- Windows ngrok build issues resolved
- Security hardening with 12 fixes across multiple areas

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
