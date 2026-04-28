# Changelog

## [1.10.0] - 2026-04-29

### Added
- **`/macos-e2e-scaffold` skill** — One-shot XCUITest scaffolding for macOS SwiftUI projects. Walks the Scene tree deterministically (Read+Grep, no LLM judgment), ranks views by interactive-control density, and generates ranked TIER-1/2/3 test stubs (Smoke + Happy-path + Error-recovery always; Modal/Menubar/Multi-window/Toolbar conditional on pattern detection). Suggests accessibility identifiers with `<ViewName>_<ControlType>_<Purpose>` convention and applies them via batch confirmation (`[a]ll`/`[c]herry-pick`/`[s]kip`). Emits a Claude-readable `scripts/run-uitests.sh` that parses xcresult to JSON (Xcode 16+) with plaintext fallback. Three project-type branches: xcodegen-managed (modifies yml), SPM-based (honest limitation — UI tests require .xcodeproj), plain .xcodeproj (manual Xcode steps; never edits project.pbxproj programmatically). Phase 0 self-check refuses non-Swift, non-SwiftUI, non-macOS, or already-scaffolded projects. Manual invocation only — distinct from artefact-review skills which auto-trigger.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.10.0.
- IDEAS.md: added three sibling stubs (`ios-e2e-scaffold`, `swiftui-snapshot-scaffold`, `appkit-e2e-scaffold`) using the same Gap/Scope/Method/Differentiation/Status template; added `macos-e2e-scaffold` to "Shipped" section.

### Notes for users
- Skill creates new files (UI test target, identifier-doc, runner script) and modifies existing view files (adds `.accessibilityIdentifier(...)` after batch confirmation). Run only after committing or stashing in-progress work.
- Skill is the first plugin-internal skill that *generates code* rather than *reviewing artefacts*. Mental model: `/setup-routing` for the project itself, `/macos-e2e-scaffold` for the project's UI test infrastructure.

## [1.9.1] - 2026-04-29

### Changed
- **README workflow integration** — the three plugin-internal review skills (`/pitfall-verification`, `/quality-review`, `/macos-native-review`) were announced in v1.5.0, v1.8.0, and v1.9.0 in the "What's Included" section but never integrated into the README's workflow guidance. Result: users knew the skills existed but couldn't see where to invoke them in practice. This patch fixes that:
  - **"The Workflow" 4-phase diagram** gains a new `PHASE 1.5: SPEC REVIEW (this plugin)` block between Phase 1 (planning) and Phase 2 (implementation).
  - **"Common Scenarios → New Feature (Full Workflow)"** now shows the spec-review trio explicitly between `/plan-eng-review` and `/superpowers:brainstorming`, plus a `/pitfall-verification` re-check after `/superpowers:writing-plans`.
  - **"Decision Tree"** gains a "Spec or plan written?" branch routing to the review trio before implementation.
- `setup-routing` and `adapt` version markers bumped to 1.9.1.

### Notes for users
- No skill or behavior changes. Documentation-only patch addressing a discoverability gap surfaced after v1.9.0 shipped.

## [1.9.0] - 2026-04-28

### Added
- **`/macos-native-review` skill** — Apple-native conformance gate for macOS PRDs, specs, and implementation plans. Walks 12 HIG-grounded categories (vocabulary, control choices, keyboard shortcuts, semantic colors, sheets/popovers/alerts, animation timing, privileged operations, accessibility, menu bar, app lifecycle, dock icon behavior, App menu) and cites `developer.apple.com/design/human-interface-guidelines/...` for every finding via WebFetch. Phase 0 self-check rejects non-macOS artifacts (returns `N/A` for iOS-only or non-Apple projects). `PROVISIONAL` fallback when the HIG site is unreachable — never silently substitutes training-data recall for verified citations. Sequential after `/pitfall-verification` and `/quality-review`: that pair asks *"will this work?"* and *"will this feel good?"*; this asks *"is this Apple-native?"*. Sibling skills (`ios-native-review`, `windows-native-review`, `material-design-review`) deferred as IDEAS.md backlog entries with consistent template.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.9.0.
- IDEAS.md: removed the `macos-native-review` proposal entry (skill shipped); added three sibling stubs (`ios-native-review`, `windows-native-review`, `material-design-review`) using the same Gap/Scope/Method/Differentiation/Status template.

## [1.8.1] - 2026-04-28

### Changed
- **Claude Code** version tracking bumped to 2.1.119 (was 2.1.114). Folds in the auto-update workflow's PR #9 — closed in favour of this patch because PR #9's `[1.7.1]` slot collided with the just-shipped `[1.8.0]`. No skill or behaviour changes.

## [1.8.0] - 2026-04-28

### Added
- **`/quality-review` skill** — perceived-quality gate run after a PRD, spec, or implementation plan, before implementation begins. Walks 15 categories of "feels cheap" risks (silent failures, missing loading/empty states, error recovery, state drift, scope leakage in workspaced apps, animations, AI structured output, sudo flows, sort order, localization-readiness) and produces severity-tiered findings (CRITICAL / SIGNIFICANT / POLISH) with concrete file/section-anchored fixes. Complementary to `/pitfall-verification`: that one asks *"will this work?"*, this one asks *"will this feel like a premium product, on the level of CleanMyMac, Raycast, Linear, Things, Stripe Dashboard?"*. Recommended flow on a fresh artifact: `/pitfall-verification` → fix bugs → `/quality-review` → fix feel → hand off to implementation.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.8.0.

## [1.7.0] - 2026-04-27

### Added
- **`/context-handoff` skill** — renamed from `/context-guard` to better describe what it does: writes a human-readable handoff file (`docs/superpowers/handoff.md`) in the project repo before `/clear` or `/compact`. Not the same as gstack's `/context-save` (which stores machine-local state in `~/.gstack/`) — this lives in the repo and works cross-machine without gstack installed.

### Fixed
- **GitHub Actions model ID** — both `check-updates.yml` and `self-repair.yml` used the retired `claude-sonnet-4-20250514` model ID, causing all CI API calls to fail. Updated to `claude-sonnet-4-6`.

### Changed
- **VERSIONS.md** — GStack bumped to v1.15.0.0 (dde5510), verified 2026-04-27.
- All references to `/context-guard` updated to `/context-handoff` across CLAUDE.md, README.md, setup-routing, adapt, and the generated CLAUDE.md template.

## [1.6.1] - 2026-04-26

### Fixed
- **`CLAUDE.md` routing rule** — replaced the stale `→ invoke checkpoint` rule with explicit rules for `/context-save`, `/context-restore`, and `/context-guard`. The `/checkpoint` command was removed from gstack in plugin v1.4.0 but the routing rule was missed at the time.

### Changed
- **Routing tables synced with gstack v1.14.0.0** — added 14 new gstack skills to `setup-routing/SKILL.md`, `adapt/SKILL.md`, and `README.md` Quick Reference: `/design-consultation`, `/design-html`, `/design-shotgun`, `/devex-review`, `/guard`, `/landing-report`, `/open-gstack-browser`, `/pair-agent`, `/plan-devex-review`, `/plan-tune`, `/setup-browser-cookies`, `/setup-deploy`, `/setup-gbrain`, `/unfreeze`.
- `VERSIONS.md` updated: GStack v1.4.0.0 → v1.14.0.0 (verified 2026-04-26).
- `.update-state.json` refreshed (last successful check was 2026-04-06).

### Notes for users
- No behavior changes to existing routing rules.
- gstack v1.x ships several internal behavior changes that don't affect plugin routing but are worth knowing about: workspace-aware `/ship` (auto-detects PR queue collisions), plan-mode review skills now run inline without an exit-and-rerun handshake, and the browser sidebar is now an interactive Claude Code REPL.

## [1.6.0] - 2026-04-22

### Added
- **Dependency check** in `setup-routing` and `adapt` — before any other action, the skills now verify that both upstream frameworks (Superpowers, GStack) are installed at their expected paths. If either is missing, the skill stops and prints the exact install commands for the missing framework(s). Prevents cryptic mid-flow failures for new users and keeps the plugin's "glue layer" contract explicit: the underlying tools are not bundled — they must be installed separately.

### Changed
- Corrected marketplace instructions across README, CLAUDE.md, and install-plugin.sh — plugin lives in `Paretofilm/claude-marketplace` (`paretofilm-plugins`), not `kjetilge/kjetil-claude-marketplace` (`kjetil-plugins`).

## [1.5.0] - 2026-04-22

### Added
- **Pitfall verification skill** (`/superpowers-gstack:pitfall-verification`) — targeted final-check skill that runs after any PRD, spec, plan, or code artifact. Not a generic review: it checks that typical pitfalls for that artifact type and domain (security, idempotency, integration contracts, edge cases, LLM output) actually do not apply. Two rounds max, domain-specific inference encouraged.

### Changed
- Plugin.json bumped to 1.5.0 (1.4.0 in CHANGELOG was auto-generated but plugin.json was not bumped in PR #6 — this release re-aligns the two).
- VERSIONS.md: GStack version label corrected from `unknown (d0782c4)` to `v1.4.0.0 (d0782c4)`; verification date rolled forward to 2026-04-22.
- Supersedes PR #4 (conflicting auto-update branch) — closes issues #5 and #7.

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
