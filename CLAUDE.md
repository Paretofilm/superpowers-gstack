# Superpowers + GStack Manual

## About
This repo contains the combined workflow manual for using Superpowers and GStack with Claude Code.

## Dual-track: web and native

superpowers-gstack is **dual-track**. The plugin supports two project tracks equally.
Skills in this repo must not assume web as the default.

### Track 1: Web
Next.js/React/Node/Python/etc. HTML is the native output format for mockups,
dashboards, and planning artifacts.

### Track 2: Native (Swift/SwiftUI, Liquid Glass)
Target platform is iOS 26+ / macOS 26 with the **Liquid Glass** design system —
not generic Swift, not pre-26.

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

- Install via marketplace: `/plugin marketplace add Paretofilm/claude-marketplace` then `/plugin install superpowers-gstack@paretofilm-plugins`
- Dev mode: `./scripts/install-plugin.sh --dev` (creates symlink, skills won't be discoverable in the skills list)
- Skills:
  - `/superpowers-gstack:setup-routing` — generate CLAUDE.md for new projects
  - `/superpowers-gstack:adapt` — adapt existing projects (preserves CLAUDE.md content)

## Setup

Install via marketplace (in Claude Code):
```
/plugin marketplace add Paretofilm/claude-marketplace
/plugin install superpowers-gstack@paretofilm-plugins
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

On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Detect format by frontmatter `type:` field — `type: handoff` is the current format (v2.1.1+). For YAML handoffs without `type:` (v1.12.0 → v2.1.0), treat as legacy-handoff and parse the same fields. For prose-only files (pre-1.12.0), fall back to text parsing. In all YAML cases, quote `next_step` verbatim, name the `active_task` ID, and surface `env` (venv, dev_server, test_cmd) so commands work immediately. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) immediately after presenting the summary.

After /compact: check for auto-mode in this priority order — YAML `mode: auto` field, then legacy `## Mode: auto` Markdown marker. If neither is present, ask the user once: "Context was compressed. Want me to activate auto context handoff for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill.

## Skill conversation discipline

When a skill instructs you to ask the user a question or wait for confirmation, always end your message at that question. Never continue with subsequent steps, suggestions, or "next steps" in the same message. Wait for the user to respond before proceeding.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke /superpowers-gstack:office-hours-track-aware (wraps /office-hours with track inference + htmlify --open + approve-before-render)
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Design system for SwiftUI projects (DESIGN.md + Swift Package) → invoke /superpowers-gstack:swiftui-design-consultation (inlines platform question on first run)
- Autoimplement a plan, "run plan end-to-end", "auto-advance phases" → invoke /superpowers-gstack:autoimplement. Removes y/n friction at phase boundaries by chaining /review + /pitfall-verification + /codex review automatically. v2.14.0+ also runs an **active pre-flight chain** on the plan ITSELF (pitfall + codex on plan body) before Phase 1 unless the latest plan commit is a pre-flight marker — closes the gap between /writing-plans and autoimplement. Skip-condition (tightened in v2.14.2): latest commit subject on plan path must match `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)` regex. Refuses on: <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations / secrets / credentials / .env / .ssh.
- Multi-model verification → invoke /superpowers-gstack:pitfall-verification. It is a multi-model orchestrator: for ship-worthy changes it auto-chains `/codex review` (Stage 2), and for high-stakes changes (architecture / real-time / security / contracts / migration-logic) also `/superpowers-gstack:third-lens-review` (Stage 3, external model house via OpenRouter), ending in an adversarial synthesis (Stage 4). Stages fire automatically per tier with no confirmation prompt; trivial changes get only the free self-pitfall pass.
- third-lens-review (normally auto-invoked by pitfall-verification Stage 3; invoke directly only for an ad-hoc third-house read) → runs an external model house via OpenRouter on the PATCHED artifact (`scripts/third-lens-review.py`). Routing by `--role`: architecture=GLM-5.2 (default), sensitive=Gemini 3.1 Pro (Western infra, enforced by `--sensitive`), correctness=DeepSeek V4-Pro, countersynthesis=GPT-5.5. ~$0.05/run; key in Keychain `openrouter-api-key`.
- After a PRD/spec/plan for a native Apple app, before implementation → invoke /superpowers-gstack:macos-native-review (macOS) or /superpowers-gstack:ios-native-review (iOS/iPadOS). HIG-citation-grounded conformance gate; complementary to pitfall-verification and quality-review.
- E2E test a Swift app, "test the app", "trykk gjennom flyten", "e2e", press buttons and verify result → invoke /superpowers-gstack:e2e-route. Pure dispatcher: reads platform (scheme/SUPPORTED_PLATFORMS/.gstack/track) × intent (CI-env/verbs; asks once if ambiguous; multiplatform → asks iOS/macOS/both) and routes to /macos-e2e-scaffold, /ios-e2e-scaffold, MCP-live simulator automation (XcodeBuildMCP / ios-simulator), or /ios-design-review. Does not execute itself — names the executor + next action, then hands off.
- Scaffold committed XCUITest for an iOS SwiftUI app → invoke /superpowers-gstack:ios-e2e-scaffold (manual only; mirrors /macos-e2e-scaffold with iOS heuristics — TabView/NavigationStack scene-walk, sheet/tab/push/gesture TIERs, iOS-Simulator runner). Normally reached via /e2e-route.
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- End of day, switch project, save progress → invoke context-save
- Resume previous session, restore state → invoke context-restore
- Context long, before /clear, before /compact → invoke context-handoff
- Code quality, health check → invoke health
