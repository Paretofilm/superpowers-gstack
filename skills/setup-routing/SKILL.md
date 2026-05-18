---
name: setup-routing
description: Generate a tailored CLAUDE.md with routing rules for the Superpowers + GStack workflow. Asks about project type, evaluates relevant skills from both frameworks, and produces a project-specific routing plan.
---

# Setup Routing — CLAUDE.md Generator

You are setting up the Superpowers + GStack combined workflow for a **new project**. Your job is to generate a `CLAUDE.md` file with routing rules tailored to this specific project.

Invoke this skill with: `/superpowers-gstack:setup-routing`

<!-- Keep in sync with skills/adapt/SKILL.md dependency + directory checks -->
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
> Only mention the framework(s) that are actually missing. Restart Claude Code after installing, then run `/superpowers-gstack:setup-routing` again.

Do NOT proceed until both frameworks are present.

**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:setup-routing` again.

**Important:** If the project already has a `CLAUDE.md` file with existing content, STOP and suggest the user runs `/superpowers-gstack:adapt` instead — it preserves existing content while adding routing.

**Version:** This skill writes version **1.11.0** into the CLAUDE.md version marker.

## Process

Follow these steps in order. Do NOT skip steps.

### Step 1: Ask about the project

Ask the user ONE question:

> What kind of project is this? (e.g., Swift iOS app, React/Next.js web app, Python API, Node.js backend, Flutter mobile app, Claude Code plugin/skill, data pipeline, infrastructure/Terraform, monorepo, static site, or describe it)

**STOP HERE.** Do not continue to the next step until the user responds. End your message with the question.

### Step 2: Ask follow-up questions

Based on the project type, ask 3-5 focused follow-up questions. Always include questions 1-3 and 10. Add 4-9 based on relevance:

1. What test framework will you use? (or "no tests yet")
2. Will this be deployed? Where? (or local-only)
3. Any security concerns? (auth, user data, payments, external APIs — helps evaluate `/cso`)
4. Will this have a UI testable in a browser? What URL? (skip for CLI tools, libraries, pipelines)
5. Is there a design component? (UI mockups, design system — skip for backend-only)
6. Is this a team project with a regular cadence? (helps evaluate `/retro`)
7. Is this a long-running project or a one-off? (helps evaluate `/learn`)
8. Do you have existing linting, type checking, or test suites? (helps evaluate `/health`)
9. Is this a monorepo? Which directory will you work in? (helps evaluate `/freeze`)
10. Which harnesses will you run this project under? Pick all that apply: **Claude Code**, **Pi (local-only — no network calls)**, **Pi (hybrid — local + cloud fallback)**, or **None — skip model routing entirely**. Determines which model-routing columns get emitted in CLAUDE.md. Pick "None" to opt out of the new v1.11.0 Model Routing section completely; setup-routing falls back to its v1.10.0 behavior for this project.

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
| `/design-consultation` | New projects defining a design system from scratch (creates DESIGN.md) |
| `/design-shotgun` | When you want multiple design variants to compare before committing |
| `/plan-devex-review` | Projects with developer-facing surfaces (APIs, CLIs, SDKs, libraries) |
| `/plan-tune` | Tune plan-skill question preferences (one-time, per-project) |
| `/autoplan` | When all three plan reviews are relevant — chains them automatically |

**Phase 3 — Review & QA:**

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

**Phase 4 — Ship & Monitor:**

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
| `/sync-gbrain` | Long-running projects with gbrain — keeps the brain current with this repo's code and refreshes CLAUDE.md search guidance |
| `/health` | Projects with existing linting, type checking, or test suites |
| `/make-pdf` | Projects needing publication-quality documentation or reports |

**Utility (any phase):**

| Skill | Consider relevant when... |
|---|---|
| `/careful` | Projects where destructive commands are risky (production DBs, shared infra) |
| `/freeze` | Monorepos or projects where edits should be restricted TO a specific directory (allow-list, not block-list) |
| `/unfreeze` | Clear the `/freeze` boundary mid-session without ending the session |
| `/guard` | Production / shared-infra work — combines `/careful` warnings with `/freeze` directory lock |
| `/browse` | Projects needing headless browser interaction beyond QA |
| `/scrape` | Projects pulling data from web pages — prototypes a flow once, codifies it via `/skillify` |
| `/skillify` | After a successful `/scrape` — persists the flow as a permanent browser-skill so future calls run in ~200ms |
| `/open-gstack-browser` | Projects wanting a visible AI-controlled Chromium with live activity feed |
| `/pair-agent` | When pairing a remote AI agent with your browser session |
| `/setup-browser-cookies` | One-time: import cookies for authenticated `/qa` and `/browse` testing |
| `/context-handoff` | Long implementation sessions, projects using SDD, or any multi-step workflow |
| `/htmlify` | Any project — generates beautiful HTML companions for MD artefacts (design docs, plans, handoffs) so verbose output stays readable. Optional PostToolUse hook auto-fires. |
| `/context-save` | Save progress and working state |
| `/context-restore` | Resume where you left off |
| `/benchmark` | Projects with performance monitoring needs |
| `/benchmark-models` | Projects comparing AI model performance |
| `/codex` | Projects needing second opinions or adversarial code review |
| `/superpowers-gstack:office-hours-track-aware` | All new-project brainstorming — wraps `/office-hours` with track inference (web vs native), inline platform question, design-doc relocation, htmlify --open, and approve-before-render gate. **Intercepts `/office-hours`** — see routing-intercept rules below. |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing. |
| `/superpowers-gstack:macos-native-review` | macOS apps — pre-implementation HIG-citation-grounded review (vocabulary, controls, keyboard shortcuts, semantic colors, sheets, menu bar, dock, App menu). Run on PRDs/specs/plans before implementation. Phase 0 detects macOS signals; auto-N/A for non-macOS projects. |
| `/superpowers-gstack:ios-native-review` | iOS / iPadOS apps — pre-implementation HIG-citation-grounded review (vocabulary, touch targets, navigation paradigm, modal presentation, gestures, system surfaces, keyboard, haptics, semantic colors, animation, privileged operations, accessibility, lifecycle). Run on PRDs/specs/plans before implementation. Phase 0 detects iOS signals; auto-N/A for non-iOS projects. |

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

### Step 5.5: Present model routing recommendations

Read `skills/setup-routing/model-routing.md` (sibling file in this skill's directory) — it holds the canonical per-skill model recommendations for Claude Code and the two Pi modes.

**If `model-routing.md` does not exist** (older cached plugin version, file deletion, etc.): tell the user "Model routing reference is unavailable — likely an older plugin cache. Run `/plugin update superpowers-gstack` and re-run this skill, or proceed without model routing." Then skip directly to Step 6 with the `### Model Routing` section omitted.

**If the user's harness answer to Step 2 Q10 was "None — skip model routing entirely"**: skip directly to Step 6 with the entire `### Model Routing` section omitted. Tell the user: "Skipping Model Routing per your request. Re-run `/superpowers-gstack:adapt` later if you change your mind." Do not present a preview.

**If the user's harness answer to Step 2 Q10 was "Other" or named an unlisted harness** (Cursor, opencode, Codex CLI, etc.): include only the **Claude Code** column in the preview, and emit a note at the **top of the `### Model Routing` section in the generated CLAUDE.md** (immediately after the section header, before the "Identify your runtime" paragraph). The note must say:

> **Note:** Your harness (`<name>`) is not in this routing table. Claude Code defaults are shown as a starting point — override per task with your harness's native model-selection mechanism (e.g. opencode's agent-types, Cursor's model picker, Codex CLI's `--model` flag).

**If Q10 was skipped or returned an empty/unparseable answer**: default to the **Claude Code** column only and proceed.

**If user selected only Pi columns (no Claude Code)**: emit a note at the top of the `### Model Routing` section saying:

> **Note:** Claude Code column is not present because you didn't select it. If you open this project in Claude Code anyway, use the Pi (hybrid) column as a rough approximation — its Anthropic-leaning recommendations (sonnet for most, haiku for mechanical) are the closest stand-in.

Build a routing preview containing only:
- The skills selected in Step 5 (skip everything excluded)
- The harness columns selected in Step 2 question 10 (skip columns the user isn't using)

Present it as:

**Model routing for [list selected harnesses]:**

| Skill | [Selected harness columns] |
|---|---|
| [Skills from Step 5 confirmation, one per row] | [Recommendation from model-routing.md] |

For skills marked `see phases` in `model-routing.md`, include a sub-table for that skill showing the per-phase recommendations.

**For Pi columns specifically:** the table in `model-routing.md` references concrete model IDs (e.g. `qwen3.6-mlx-8bit`, `qwen3.6-27b-optiQ-SFT`). If the user is unsure which Pi models they have loaded, ask them to run:

```bash
cat ~/.pi/agent/models.json 2>/dev/null | grep '"id"'
```

…and confirm coverage. If a recommended Pi model is not listed, mark that row with `(verify availability)` in the generated CLAUDE.md.

After presenting, ask:

> Does this model routing look right? Any adjustments?

**STOP HERE.** Do not continue to Step 6 until the user responds. If adjustments are requested, update and re-present. If the user wants to keep model routing out of CLAUDE.md entirely, note that and skip the Model Routing section in Step 6.

### Step 6: Generate CLAUDE.md

Generate the `CLAUDE.md` file in the project root. Adapt the structure below based on what's relevant — omit entire sections that don't apply.

Before writing the file, read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Include this version as an HTML comment at the top of the generated CLAUDE.md:

```markdown
<!-- superpowers-gstack: {version} -->
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

### Autonomy and user interruption <!-- gstack-autonomy-v1 -->

Default to autonomous continuation. Stopping to ask the user is the LAST resort, not the default. When you complete a planned phase or pass a milestone, the next action is the next phase — NOT a status report followed by "ping me to continue".

#### When you MUST stop and ask the user

Only these five categories warrant stopping:

1. **User-territory operation required** — Apple Developer Portal capability registration, OAuth/SSO login, signing into an external service, payment authorization, anything requiring 2FA / Apple ID / human credentials the agent cannot supply
2. **Destructive operation needing explicit approval** — `rm -rf`, `git push --force`, dropping a database table, deleting cloud resources, any operation listed under the user's `/careful` rules
3. **Genuinely ambiguous design choice** — two paths with materially different long-term consequences AND no signal in the spec / plan / prior conversation pointing to one over the other. ("I assume green but maybe blue?" is NOT this — that is over-asking.)
4. **Explicit checkpoint in the skill or plan** — e.g. `swiftui-design-consultation` Phase 3's Approve/Drill/Change/Start-over gate, `executing-plans`' phase review, `office-hours` final approval
5. **You are truly blocked** — missing information you cannot derive, infinite loop you cannot break, error message you cannot interpret after reasonable investigation (read docs, search corpus, try the obvious fix first)

#### When NOT to stop

Do NOT stop to:

- ❌ Report completed work and ask "shall I continue with the next phase?"
- ❌ Check in at convenient milestones because it feels considerate
- ❌ Ask "should I do X?" when X is obviously the next step in scope
- ❌ Wait for permission to do work clearly within the user's original request or agreed plan
- ❌ Wrap up a session early because the plan turned out to be larger than expected — finish it

If the next step is clearly within scope, DO IT. Report what happened after it's done.

#### Forbidden phrases

These continuation-tokens signal "I have stopped autonomy and now require user input" — if any creep into your output without a category-1-to-5 reason above, you have failed the autonomy default:

- ❌ "Ping me when you want me to continue"
- ❌ "Let me know when you're ready for the next round"
- ❌ "Ready when you are"
- ❌ "Awaiting your go-ahead"
- ❌ "Si fra når jeg skal fortsette"
- ❌ "Bash-prompten din er fortsatt aktiv — si bare 'fortsett'"

If you catch yourself about to write one of these, ask: "Is there a real category-1-to-5 reason here, or am I just being polite?" If polite, delete the sentence and do the next thing instead.

#### Status updates DURING work, not AS wait-states

Give brief progress signals while you continue, not as the final word before stopping:

- ✅ "BookmarkStore + 7 tests green. Moving to RecordingScanner now."
- ✅ "Phase 1 build verified on macOS. Starting Phase 2 UI layer."
- ❌ "Phase 1 done. Here's a 12-row status table. Ready for UI when you say so."

The user reads status WHILE you work, not as a wait-state for permission.

#### When to STOP, but only after finishing in-scope work

When you do legitimately reach a stopping point (the agreed scope is done, or a category-1-to-5 reason fires), stop cleanly:

- State what's done in one or two sentences
- Name what's blocked (if anything) with the specific reason from the five categories
- Do NOT propose new work or invite continuation — the next session/turn will decide that

### Track-aware routing (dual-track) <!-- gstack-routing-v1 -->

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

#### When user invokes /office-hours (no namespace)

Intercept and invoke `/superpowers-gstack:office-hours-track-aware`
instead. The wrapper runs upstream `/office-hours` for the brainstorm,
then handles:
- Track inference from the brainstormed idea (native vs web signals)
- Inline platform question (iOS/macOS/both) if native or ambiguous, only
  when `.gstack/track` is absent
- Design-doc relocation from gstack defaults into repo `docs/`
- `/htmlify --open` rendering BEFORE the approval gate (so the user can
  read the rich HTML before deciding)
- Approve / Revise / Restart gate after they've seen the rendered HTML
- Suggests `/superpowers-gstack:swiftui-design-consultation` next for
  native tracks

User can bypass by typing `/office-hours` (gstack) directly — but for
all dual-track projects, prefer the wrapper.

#### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)

User can always bypass by typing the namespaced version directly.

### Native Apple development tools (Xcode workflow) <!-- gstack-xcode-tools-v3 -->

*This section emits only when `.gstack/track` is `ios`, `macos`, or `both`. Skip entirely for web projects.*

Xcode-related operations MUST be performed by the agent — NEVER delegated to the user. The user should never need to open Xcode to verify your work. Prefer MCP tools when available; fall back to CLI when not.

#### Tool routing for Apple-platform operations

For each operation, **prefer the MCP tool when available**, falling back to CLI otherwise. Check MCP availability via `ToolSearch` first (these are deferred tools loaded on demand); only drop to CLI if the search returns nothing.

| Operation | Preferred (MCP) | Fallback (CLI, always available with Xcode) |
|---|---|---|
| Type-check Swift code | `mcp__swiftui-rag__swift_typecheck` | `xcrun swift -typecheck <file>.swift` |
| Search SwiftUI corpus / HIG | `mcp__swiftui-rag__search_swiftui_corpus` | (no CLI fallback — use `mcp__apple-docs__search_apple_docs`) |
| HIG conformance review | `mcp__swiftui-rag__review_macos_hig`, `review_accessibility`, `review_liquid_glass` | (no CLI fallback — read HIG via `mcp__apple-docs__get_apple_doc_content` and apply rules manually) |
| Build Xcode project for simulator | `mcp__XcodeBuildMCP__build_sim` | `xcodebuild -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16' build` |
| Build + launch in simulator | `mcp__XcodeBuildMCP__build_run_sim` | `xcodebuild ... build && xcrun simctl launch booted <bundle-id>` |
| Run XCTest / Swift Testing | `mcp__XcodeBuildMCP__test_sim` | `xcodebuild test -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'` |
| List / boot simulators | `mcp__XcodeBuildMCP__list_sims`, `boot_sim` | `xcrun simctl list devices`, `xcrun simctl boot <udid>` |
| Capture simulator logs | `mcp__XcodeBuildMCP__launch_app_logs_sim` | `xcrun simctl spawn booted log stream --predicate '...'` |
| UI automation in simulator | `mcp__XcodeBuildMCP__ui_tap`, `screenshot`, `snapshot_ui`, `ui_describe_all` | `xcrun simctl io booted screenshot <path>.png` (screenshots only; tap/snapshot are MCP-only) |
| Apple platform docs (HIG, APIs) | `mcp__apple-docs__search_apple_docs`, `get_apple_doc_content` | `man` pages for CLI tools; online docs at developer.apple.com |
| WWDC video search / examples | `mcp__apple-docs__search_wwdc_content`, `get_wwdc_code_examples` | (no CLI fallback — fetch via `WebFetch` against developer.apple.com/wwdc) |

#### Project file management (prefer declarative)

Avoid hand-editing the auto-generated XML in `.xcodeproj/project.pbxproj`. Two declarative alternatives:

- **XcodeGen** (`brew install xcodegen`) — generate `.xcodeproj` from a committable `project.yml`. Re-runnable via `xcodegen generate`. Strongly recommended for solo / small-team SwiftUI projects.
- **Tuist** — more powerful declarative project manager; heavier dependency. Use if XcodeGen isn't sufficient (multi-target, complex schemes, generated frameworks).

For new SwiftUI projects under this plugin, default to XcodeGen unless the project explicitly requires Tuist.

#### Capabilities, signing, and provisioning

Three surfaces, three different handlers:

| Surface | What | Who handles it |
|---|---|---|
| `*.entitlements` file | Declares which capabilities (CloudKit, push, app groups, keychain sharing, etc.) the app uses | **Agent** — edit declaratively as XML |
| `project.yml` (XcodeGen) or `*.xcodeproj` build settings | `DEVELOPMENT_TEAM`, code signing identity, target capabilities | **Agent** — edit declaratively |
| Apple Developer Portal (developer.apple.com) | Registers container IDs (CloudKit), App IDs, provisioning profiles, push certificates | **User** — Apple ID login + 2FA required; agent cannot access |

**CloudKit example workflow:**

1. **Agent edits entitlements** to declare CloudKit + container:
   ```xml
   <key>com.apple.developer.icloud-services</key>
   <array><string>CloudKit</string></array>
   <key>com.apple.developer.icloud-container-identifiers</key>
   <array><string>iCloud.com.example.appname</string></array>
   ```
2. **Agent ensures `DEVELOPMENT_TEAM` is set** (e.g. via `project.yml`):
   ```yaml
   settings:
     base:
       DEVELOPMENT_TEAM: WXNUGGYB2B
   ```
3. **Agent regenerates and builds:**
   ```bash
   xcodegen generate
   xcodebuild build -scheme <name> -destination 'platform=iOS Simulator,name=iPhone 16'
   ```
4. **If signing fails** with "container not registered" / "no matching provisioning profile":
   - STOP. Surface to user with exact portal steps, e.g.:
     > "Container `iCloud.com.example.appname` is not registered in Apple Developer Portal. Go to https://developer.apple.com/account → Identifiers → click your App ID (com.example.appname) → enable the iCloud capability → link the container `iCloud.com.example.appname`. ~30 seconds. Ping me when done and I'll retry the build."
5. **User does the portal-click** (~30 sec).
6. **Agent retries `xcodebuild build`** — succeeds.

**Why this split:** Apple Developer Portal requires Apple ID + 2FA, which no MCP/CLI tool automates stably. Xcode's Capabilities pane is just a frontend to the same portal — clicking there doesn't help an agent that has no portal session either. The declarative path (entitlements + project.yml) is the only path that works for BOTH the agent AND for git history (YAML is committable; portal state is implicit).

For CI/CD with many apps or frequent provisioning operations, **Fastlane match** + spaceship is the standard automation surface. Out of scope for solo vibe-coder workflows; mention it only if the user scales beyond one or two apps.

#### Anti-patterns (NEVER do these)

- ❌ "Open Xcode and run the tests" — use `mcp__XcodeBuildMCP__test_sim` (MCP) or `xcodebuild test` (CLI) instead
- ❌ "Build the app in Xcode to verify" — use `mcp__XcodeBuildMCP__build_sim` (MCP) or `xcodebuild build` (CLI) instead
- ❌ "Take a screenshot of the simulator" — use `mcp__XcodeBuildMCP__screenshot` (MCP) or `xcrun simctl io booted screenshot` (CLI) instead
- ❌ "Click through the Signing & Capabilities pane in Xcode" — declare entitlements in `*.entitlements` + `project.yml` (XcodeGen) instead
- ❌ "Check what the system color looks like in HIG" — use `mcp__apple-docs__search_apple_docs` or `mcp__swiftui-rag__search_swiftui_corpus` instead

If a verification step requires Xcode the UI, you have not finished the task — use MCP or CLI tools to verify, then report results.

### Model Routing (v0.1, advisory)

**Identify your runtime:**
- **Claude Code** — your system prompt names you "Claude Code". Use the **Claude Code** column.
- **Pi (local-only)** — `~/.pi/agent/AGENTS.md` confirms Pi runtime; no network calls allowed. Use **Pi (local-only)**.
- **Pi (hybrid)** — Pi runtime with cloud calls permitted. Use **Pi (hybrid)**.

If your runtime doesn't match a listed column, default to **Claude Code**.

**How to apply the recommendations** (differs by harness):
- **In Claude Code:** dispatch subagents (via `Agent` tool, parallel agents, or SDD workers) with `model:` set to the column entry for the task. Multi-phase skills become per-phase subagent calls.
- **In Pi:** no subagent dispatch is available (Pi runs a single process per session). Use the column entry as a guide for *which Pi provider/model to start the session with* for tasks of this type. For multi-phase skills with phase-varying recommendations:
  - **Preferred:** end the current Pi session (`/new`) between phases and restart with the model matched to the next phase. Acceptable for long-running implementation work.
  - **Pragmatic:** if restarting is friction, pick the model matched to the **most cognitively-demanding phase** in your session (bias toward the larger/stronger model so weaker phases still get adequate capability).
  - Pi aliases (e.g. `qwen3.6-27b-optiQ-SFT`) map to actual `--provider` / `--model` flags — see the alias table in `model-routing.md`.

[Insert routing table here — only the skills confirmed in Step 5, only the harness columns selected in Step 2 Q10. For skills marked "see phases" in `model-routing.md`, include the phase sub-table inline. For Pi rows, use the friendly aliases for readability; orchestrator should map back to actual `id` from the alias table in `model-routing.md` when invoking.]

For multi-phase skills (`/superpowers:test-driven-development`, `/superpowers:subagent-driven-development`, `/superpowers:systematic-debugging`, `/qa`, `/ship`), route per phase — see the sub-tables above.

**Caveats:**
- Advisory only. Override per task when you have evidence.
- Pi rows assume the named models/providers are loaded (`cat ~/.pi/agent/models.json` to verify, and `scripts/start-mlx-server.sh` for the SFT model).
- Swift-implementation rows route to `qwen3.6-27b-optiQ-SFT` (mlx-sft provider, port 8081) only if that provider is running. Otherwise fall back to the row's non-Swift recommendation.
- **Drift warning:** this table is inlined from `model-routing.md` at the time `/setup-routing` was last run. If the plugin updates its routing recommendations, this inline copy stays frozen — re-run `/superpowers-gstack:adapt` to pull the latest. The plugin version that produced this section is stamped in the top-of-file `<!-- superpowers-gstack: X.Y.Z -->` marker.
- Full canonical table with all skills (not just this project's selected subset) lives at `~/.claude/plugins/cache/.../superpowers-gstack/skills/setup-routing/model-routing.md`.

### Session Continuity

On session start or after /compact: if `docs/superpowers/handoff.md` exists and contains content, read it and present a one-line summary of where you left off. Then proceed normally — do not ask "ready to continue?". Clear the file (write empty string) immediately after presenting the summary.

After /compact: if handoff.md does not contain `## Mode: auto`, ask the user once: "Context was compressed. Want me to activate auto context handoff for this session? I'll keep handoff.md updated and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill.

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
- **Model Routing section:** include only the harness columns selected in Step 2 Q10 and only the rows for skills selected in Step 5. If the user opted out of model routing in Step 5.5, omit the entire `### Model Routing` section.
- **Phase sub-tables:** include inline only for multi-phase skills selected in Step 5 (e.g. skip the TDD sub-table if `/superpowers:test-driven-development` is not in the selected set).
- Target 100-180 lines total (was 60-100 in v1.10.0 — Model Routing adds ~20-50 lines depending on selected skills, harness count, and how many multi-phase skills are included). Projects that select all three harnesses + many multi-phase skills can legitimately reach 200 lines; that is acceptable when the routing is being used. The 150-line "compliance budget" from v1.10.0 is officially relaxed to 200 lines starting v1.11.0 when Model Routing is present. To stay tight: omit any column not selected, omit phase sub-tables for skills not selected.

### Step 7: Confirm

After writing the file, tell the user:
- What was generated and which skills were included
- Remind them to add project-specific conventions as they develop them
- Suggest next step based on project type (usually `/office-hours` for new ideas or `/superpowers:brainstorming` if scope is already clear)
