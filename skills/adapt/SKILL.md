---
name: adapt
description: Adapt an existing project to the Superpowers + GStack workflow. Analyzes the project, identifies gaps, updates CLAUDE.md routing without losing existing content, and sets up required structure.
---

# Adapt to Superpowers + GStack

You are adapting an existing project to the Superpowers + GStack combined workflow. Unlike `setup-routing` (which is for new/empty projects), this skill preserves everything that already exists and makes only the changes needed for a smooth transition.

Invoke this skill with: `/superpowers-gstack:adapt`

<!-- Keep in sync with skills/setup-routing/SKILL.md dependency + directory checks -->
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
> Only mention the framework(s) that are actually missing. Restart Claude Code after installing, then run `/superpowers-gstack:adapt` again.

Do NOT proceed until both frameworks are present.

**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:adapt` again.

**Version check:** The current version is ALWAYS the installed plugin version read from `plugin.json` (see the marker step) — never a number stated in this file. If the project's CLAUDE.md contains a version marker (`<!-- superpowers-gstack: X.Y.Z -->`) with an older version, inform the user that routing and session rules will be updated to the current version as part of this adaptation. Projects with an older Model Routing block (v0.1 `### Model Routing` with Pi/MLX columns) will have it **replaced** by the new top-level `## Model Routing` (v0.2, Claude-only, domain-aware); projects with none will gain one unless they opt out — surface this clearly so it's not a silent change. Projects on `1.11.1` or earlier will gain three new gstack skill rows (`/sync-gbrain`, `/scrape`, `/skillify`) in the evaluation tables.

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

> Based on my analysis, this is a **[type]** using **[stack]**. Tests run with `[command]`. [Deployed to X / not deployed]. [Has browser UI at X / No browser UI].
>
> Is this correct? Anything to add?

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

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
| `/superpowers:requesting-code-review` | Multi-file changes (runs automatically during SDD, but can be invoked manually) |
| `/superpowers:receiving-code-review` | After `/review` or PR feedback requires code changes — structures the response with TDD |
| `/superpowers:writing-skills` | Only for Claude Code plugin/skill projects |

**GStack skills — Phase 1 (Planning):**

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

**GStack skills — Phase 3 (Review & QA):**

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

**GStack skills — Phase 4 (Ship & Monitor):**

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

**GStack skills — Utility:**

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
| `/superpowers-gstack:autoimplement` | Multi-phase plans where the user always confirms phase boundaries — chains `/review` + `/pitfall-verification` automatically (pitfall auto-chains `/codex review` + the third lens per tier — no separate codex step). v2.14.0+ adds active pre-flight that reviews the plan body itself before Phase 1 unless the latest plan commit matches the marker regex `^(chore\|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]\|$)` (closes the gap between writing-plans and autoimplement). Refuses on <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations/secrets/credentials/.env/.ssh. |
| `/superpowers-gstack:office-hours-track-aware` | All new-project brainstorming — wraps `/office-hours` with track inference (web vs native), inline platform question, design-doc relocation, htmlify --open, and approve-before-render gate. **Intercepts `/office-hours`** — see routing-intercept rules below. |
| `/superpowers-gstack:swiftui-design-consultation` | Native SwiftUI projects — produces DESIGN.md + Swift Package starter; equivalent to /design-consultation for web. Inlines the platform question (iOS/macOS/both) on first run if `.gstack/track` is missing. |
| `/superpowers-gstack:macos-native-review` | macOS apps — pre-implementation HIG-citation-grounded review (vocabulary, controls, keyboard shortcuts, semantic colors, sheets, menu bar, dock, App menu). Run on PRDs/specs/plans before implementation. Phase 0 detects macOS signals; auto-N/A for non-macOS projects. |
| `/superpowers-gstack:ios-native-review` | iOS / iPadOS apps — pre-implementation HIG-citation-grounded review (vocabulary, touch targets, navigation paradigm, modal presentation, gestures, system surfaces, keyboard, haptics, semantic colors, animation, privileged operations, accessibility, lifecycle). Run on PRDs/specs/plans before implementation. Phase 0 detects iOS signals; auto-N/A for non-iOS projects. |
| `/superpowers-gstack:quality-review` | After any PRD/spec/plan, before implementation — hunts perceived-quality pitfalls (silent failures, loading/empty states, error recovery, state drift). Complementary to pitfall-verification ("will it work?" vs "will it feel good?"). |
| `/superpowers-gstack:verify-and-land` | Apple + web projects — after a fix, builds the checked-out branch, launches that exact bundle (not the installed copy), proves which build is on screen, gates on the user seeing the fix, then pushes and offers merge/PR. |
| `/superpowers-gstack:e2e-route` | Swift projects — pure dispatcher for E2E test requests: reads platform × intent and routes to the right executor (scaffold skills, MCP-live simulator automation, visual review, ios-visual-explore). |
| `/superpowers-gstack:ios-e2e-scaffold` | iOS SwiftUI apps — one-shot XCUITest scaffolding (TabView/NavigationStack scene-walk, TIER-ranked stubs, iOS-Simulator xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:macos-e2e-scaffold` | macOS SwiftUI apps — one-shot XCUITest scaffolding (Scene-walk, TIER-ranked stubs, xcresult runner). Normally reached via /e2e-route. |
| `/superpowers-gstack:ios-visual-explore` | iOS/iPadOS apps — Tier-2 visual exploration via Gemini computer-use when the accessibility tree is insufficient (layout regressions, visual landmarks). Paid API per run; normally reached via /e2e-route. |

### Step 4: Identify gaps and plan changes

Compare the current project state against what Superpowers + GStack needs. Check each item:

**CLAUDE.md routing:**
- [ ] Does `## Skill routing` section exist?
- [ ] Does it include the correct skills for this project?
- [ ] Does it have Routing Logic, Rules, and Session Management?
- [ ] Does it have a `## Model Routing` section (v0.2+)? If not, this adaptation will add one.
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

**STOP HERE.** Do not continue to the next step until the user responds. Do not add "Next steps", suggestions, or any other content after the question. End your message with the question.

### Step 5: Apply changes

Apply the changes identified in Step 4. Follow these rules strictly:

**Snapshot before the first write.** Before modifying CLAUDE.md — before any other
rule in this step:

```bash
mkdir -p .gstack
# Rotate, never overwrite: the second /adapt after a bad first one is exactly the
# recovery case, and overwriting would destroy the only copy of the original.
[ -f .gstack/CLAUDE.md.pre-adapt ] && \
  mv .gstack/CLAUDE.md.pre-adapt ".gstack/CLAUDE.md.pre-adapt.$(date +%Y%m%d-%H%M%S)"
cp CLAUDE.md .gstack/CLAUDE.md.pre-adapt
# Keep the snapshots out of git WITHOUT touching the user's tracked .gitignore.
EXCL="$(git rev-parse --git-path info/exclude 2>/dev/null)"
if [ -n "$EXCL" ]; then
  mkdir -p "$(dirname "$EXCL")"
  grep -qxF '.gstack/CLAUDE.md.pre-adapt*' "$EXCL" 2>/dev/null \
    || echo '.gstack/CLAUDE.md.pre-adapt*' >> "$EXCL"
fi
```

`.gstack/` already holds `track`, so this introduces no new location. This snapshot is
what Step 6 diffs against and what the user restores from if the run goes wrong. Do
NOT substitute `git diff` for it: the project may have uncommitted CLAUDE.md changes,
and CLAUDE.md may not be tracked at all. If CLAUDE.md does not exist yet, skip the
copy — there is no prior content to lose — and say so in the Step 6 report.

Three details, each of which was missing and each of which defeats the snapshot on its
own. **Rotate** rather than overwrite: a user who runs `/adapt` again after a bad run
would otherwise replace the good original with the bad result — the one scenario the
snapshot exists for. **Exclude** it via `.git/info/exclude` (local, so it does not edit
a tracked `.gitignore` the user owns): a committed stale copy of an instruction file is
read by future agents as if it were current. **Name it in the report** (Step 6), because
a restore point nobody is told about is not a restore point. If `git rev-parse` fails
this is not a git repository — skip the exclude silently and carry on; the snapshot
still works.

**CLAUDE.md updates:**
- Read the plugin version from `.claude-plugin/plugin.json` in the superpowers-gstack plugin directory (check `~/.claude/plugins/cache/*/superpowers-gstack/*/plugin.json`, use the latest). Add or update the **two-line** HTML header at the very top of CLAUDE.md — rewrite both lines every run, so the warning stays current without needing a marker of its own:

  ```
  <!-- superpowers-gstack: {version} -->
  <!-- Sections whose heading carries a gstack-<name>-vN marker are plugin-managed: /adapt replaces each one wholesale on upgrade. Put project-specific findings — the measurement you took, the flag that worked — in your own H2 section with no marker; /adapt leaves those alone. One exception: the headings it manages are reserved even when unmarked (the marked ones in this file, plus Model Routing), because an unmarked copy of one reads as an older emitted section. Prefix your own headings with this project's name and none of them can collide. -->
  ```

  Keep the second line as a single HTML comment with no nested `<!--` inside it: HTML comments do not nest, so an inner opener followed by the first `-->` would end the comment early and render the remainder as visible text.

  If the file already carries the **one-line** header that 2.47.0 and earlier wrote (`<!-- superpowers-gstack: X.Y.Z -->` alone), replace that line in place with both lines. Do not leave the old line standing above or below the new pair — two version comments in one file is one of them lying, and the reader has no way to tell which.
- If CLAUDE.md exists: READ it first, then INSERT or UPDATE the `## Skill routing` section
- NEVER delete or rewrite existing sections (conventions, tech stack, project-specific rules)
- If a `## Skill routing` section already exists: **UPDATE its plugin-managed subsections per the per-section case-logic below (cases 1-4 for each marker-section).** Do NOT wholesale-replace the entire Skill routing block — that would destroy any user-authored subsections nested inside (e.g. a hand-written `### Code reuse discipline` markerless heading). The per-section logic handles every plugin-managed subsection individually; anything inside Skill routing that the per-section logic does NOT match must be PRESERVED verbatim, including its position and surrounding whitespace.
- If no `## Skill routing` section exists: ADD it after the first heading (or at the top if no heading)
- The routing section follows the same template as `setup-routing` Step 6, adapted to this project. Keep the generated content tight — every word is a per-session context tax on the project: routing-table row descriptions ≤ 15 words; decision-tree lines ≤ 10 words; no rationale prose in generated sections (the rules carry the behavior; the *why* lives in this plugin's docs).
- **Model Routing (v0.2):** read the canonical routing table from `~/.claude/plugins/cache/*/superpowers-gstack/*/skills/setup-routing/model-routing.md`. Infer this project's domain sensitivity from the project analysis and Step 3 evaluation:
    - Real-time audio / DSP / signal processing, or any lock-free concurrency (incl. Swift audio engines, game-audio) → **very high** — NB: a plain Swift/SwiftUI CRUD or UI app with none of these signals is **medium**, not very high
    - Database migrations / ETL / data-transform, OR security concerns (auth/payments/PII/external APIs) → **high**
    - Web/mobile app UI feature work → **medium**
    - CLI tools / libraries / format-plumbing / serialization → **low**
    - If ambiguous, ask the user one line: "How silently could a subtle bug here compound — very high / high / medium / low?"
  - **First, replace any stale Model Routing block.** If the project's existing CLAUDE.md already has a Model Routing section from a prior plugin version — whether a v0.1 `### Model Routing` subsection (the one with Pi/MLX/local-model columns) or an older top-level `## Model Routing` — DELETE that entire section (from its heading through the line before the next heading of equal-or-higher level) before emitting the new one. This is an explicit exception to the "never delete existing sections" rule above: Model Routing is fully plugin-managed, so a stale copy must be **replaced**, not preserved alongside the new block — otherwise the generated CLAUDE.md carries two contradictory routing tables (old Pi/MLX + new Claude-only). **Apply the Attribution check below to it as well** — `Model Routing` carries no marker, and this is the one place `/adapt` DELETES rather than replaces, so an unattributable section is gone outright rather than merely overwritten. Sentinel: the body carries a routing table with a model column (the v0.1 Pi/MLX/local-model columns, or a `Model` / `Sensitivity` column). If it carries none, the heading is the project's own: leave it untouched, skip emitting the plugin's Model Routing this run, and tell the user to rename their section and re-run `/adapt` if they want the plugin-managed one.
  - Then emit a top-level `## Model Routing` section (placed after `## Skill routing` and all its subsections): read `blocks/model-routing-section.md` from the plugin's `skills/setup-routing/blocks/` directory (same path resolution as `model-routing.md` above) and emit its content verbatim, substituting `{{DOMAIN_SENSITIVITY}}` with the inferred value.

  - **Fallback:** If `model-routing.md` is missing (older cached plugin), warn the user and skip the section entirely.
  - If the user opts out, skip this section entirely and note the choice in the final report

**Shared block files.** Every "block to insert" below is single-sourced in the plugin at `skills/setup-routing/blocks/<name>.md` (sibling skill directory — from this skill's base directory: `../setup-routing/blocks/<name>.md`; via the cache glob: `~/.claude/plugins/cache/*/superpowers-gstack/*/skills/setup-routing/blocks/`). Read the named file and use its content as the verbatim block. Resolve `{{...}}` placeholders per `blocks/PLACEHOLDERS.md` before inserting — never let a raw `{{...}}` token reach the generated CLAUDE.md. If the blocks directory is missing (older plugin cache), warn the user to run `/plugin update superpowers-gstack` and skip the affected sections.

**Record what you emitted.** When you write a block into CLAUDE.md, add a SECOND HTML
comment on that block's heading line, immediately after the version marker the block
file itself carries, with nothing at all between the two:

```
<!-- gstack-git-hygiene-v9 --><!-- emitted=162 -->
```

Leave the version marker byte-for-byte as the block wrote it. Provenance is a separate
comment precisely so that marker keeps matching for every reader that knows only the
bare form: an older plugin cache meeting a file this release wrote finds its marker
exactly where it expects it and skips the section as current, instead of reading it as
markerless and appending a duplicate. Putting the attribute inside the marker breaks
that; putting it on a line of its own adds a line to what the next run counts, and is
a line a user tidying their own CLAUDE.md can delete.

This applies to a block whose file carries a version marker, which is what the second
comment attaches to. `blocks/model-routing-section.md` carries none, so it gets no
provenance: an `emitted=` with no marker beside it is a number no reader is looking for,
and the growth check never runs on that section — Model Routing is replaced outright.

`<N>` is `wc -l` of the block file you just read — every line in the file, counted
before any placeholder substitution and before any heading-level demote. This is the
only fact that makes a later upgrade able to tell growth from a block that simply
changed size, so do not estimate it and do not carry a stale value forward from the
section you replaced. Block files themselves never carry `emitted=`; a constant baked
into the source would lie the moment the block changed length.

**Growth check — applies to every marker-managed section below, in cases 2 and 3.**
A marker records who *created* a section, not who has written in it since. Before
replacing any section, compare its length against the block's:

```bash
TMP="$(mktemp)"
sed -n '<start>,<end>p' CLAUDE.md > "$TMP"
wc -l "$TMP" <path-to-block>.md
```

You already know `<start>` and `<end>` — finding them is how you perform the REPLACE
at all. **Read the section from `CLAUDE.md`, not from the snapshot, and do not
"helpfully" repoint this at `.gstack/CLAUDE.md.pre-adapt`.** `<start>` and `<end>` are
line numbers in the LIVE file, and by the time this gate runs Step 5 has already
written above the section — the new header line, the `## Skill routing` insert, the
`## Model Routing` replace. Those same numbers land lower in the snapshot, so the
window slides off the section and past EOF returns nothing. Truncation only ever
shortens, so the ratio only ever falls: the gate goes quiet exactly when it should
fire. Measured on this branch's own fixture (196-line section, 78-line block, true
2.51×): 40 lines inserted above → 2.04× (fires), 90 → 1.40× (silent replace), 200 →
0.00× (silent replace). The section is still unmodified in `CLAUDE.md` at gate time
and the line numbers came from that same file, so reading it there is the only
self-consistent choice. The snapshot's job is Step 6's whole-file diff, not this.

Then run the diff — always, before deciding. The Volume proxy is read off it, and so
is the at-risk list you show the user when the gate fires:

```bash
diff "$TMP" <path-to-block>.md
```

The gate fires when **any** of the three triggers below holds. Run all three every
time — they are checked together, not in precedence order, and the first one to fire
is enough.

- **Provenance (measured, not inferred).** — the section's heading line carries a
  second comment `<!-- emitted=<N> -->` after the version marker, and the section is
  now more than **~20** lines longer than `<N>`. The plugin wrote exactly `<N>` lines
  there, so everything above that came from somewhere else. This is the only one of
  the three that is a measurement rather than a proxy: a block that grew or shrank
  between releases moves the ratio, and it cannot move `<N>`.

  ```bash
  awk 'NR>=<start> && NR<=<end>' CLAUDE.md | wc -l     # what is there now
  ```

  **Count the two sides the way each was counted.** `<N>` is `wc -l` of the block
  file as it shipped; the number above is the section's lines in CLAUDE.md, heading
  line through the last line before the next heading of equal-or-shallower level.
  Placeholder substitution and a trailing blank line move the total by a line or
  two, so the two counts are close rather than equal. The ~20-line threshold exists
  partly to absorb that; do not tighten it to chase an exact match.

  **Distrust an implausible `<N>`.** Nothing verifies it — it is a number a past run
  wrote down. Ignore it, and decide on the other two triggers alone, when either the
  section is at or below `<N>` (the plugin cannot have emitted more lines than are
  there, so the count is wrong), or `<N>` is more than ~20 lines ABOVE the block
  file's current length (blocks grow between releases far more often than they
  shrink, so a `<N>` well over today's block is a miscount, not history). A `<N>`
  well BELOW the block is ordinary — that is just an older, smaller block — and it
  is fine.

- **Ratio (proxy).** — the section is more than **1.5×** the block's line count.
- **Volume (proxy).** — more than ~20 of the section's lines carry material the block
  does not have in any form. Not reworded block prose, which a version bump produces by
  the dozen; lines whose subject matter is absent from the block entirely.

A section with no `emitted=` — everything written before 2.49.0 — has only the two
proxies, and they are why provenance exists. Where provenance IS present it adds a
reason to stop; it never removes one. That precedence is deliberate and it is not
symmetric: a trigger that fires when it should not costs one question, and a trigger
that stays quiet when it should not costs the user whatever they had written. An
`emitted=` that is wrong by a little is the likeliest failure of this whole mechanism,
and letting it silence two working proxies would make this release worse than the one
before it for exactly the sections it was built to protect.

Neither proxy alone is enough, which is why there are two. Ratio scales with the block, so
one threshold buys wildly different exposure: 1.5× of the 162-line `git-hygiene.md` is
81 losable lines, 1.5× of the 23-line `companion-skills.md` is 11 — a 7× difference
from the same number. Volume is flat, so it catches the small-block case the ratio
sleeps through.

When the gate fires, do not replace the section silently:

1. Collect the at-risk lines from the diff you just ran: the `<` lines that are not
   simply a reworded version of block prose. That is the content at risk.
2. Ask the user, naming the section and the number of lines at risk, and offer two
   outcomes: **move that content into a new unmarked H2 section** (recommended — give
   it a heading starting with the project's own name, so it can never collide with a
   heading the plugin manages, and it survives every future upgrade), or
   **leave this section at its old version** and skip its upgrade.
3. Do not proceed past this gate without an answer. This is a category-3 stop under
   the Autonomy rules — genuinely ambiguous, with materially different consequences —
   and the one place in `/adapt` where silent correctness is worse than asking. A
   wrong guess here is unrecoverable for the user; the cost of asking is one question.
4. **Non-interactive runs** — nobody is there to answer. Take the preserving branch
   without asking: leave the section at its old version, do not replace it, and list
   it in the report's **Deferred (grown past its block, not upgraded):** block, naming
   the section. A stale section is recoverable; a deleted one is not.

   Be precise about when this applies. Two `STOP HERE` gates sit above Step 5 — the
   Step 2 stack confirmation and the Step 4 "shall I proceed" — so a bare
   `claude --print "/adapt"` never reaches this gate at all; it stops at the first one.
   Rule 4 is for a run that got *past* those gates and then meets a question it cannot
   put to anyone: a prompt that pre-answered them, an orchestrator running `/adapt` as
   one step of something larger, a subagent with no channel back to the user. Do not
   read it as "`--print` means proceed" — assuming that reachability is exactly what
   made this branch's first test harness report PASS while proving nothing.

The two proxies are heuristics, and neither establishes authorship — a line count is
not a byline. They are cheap stand-ins for "someone has been writing in here", chosen
because they are computable from what the gate already reads. Provenance is not one of
them: it is a measurement against a number the plugin wrote down, which is why it can
only add a reason to stop and never subtract one. A section at 1.1× is usually a
user fixing a typo in plugin prose; the run that motivated this gate was at 2.7× — a
73-line block against a 198-line section, and the 125-line delta held an
`-allowProvisioningUpdates` discovery, three lessons about running on a physical
iPhone, and a note on a tool's current status. None of it was recoverable from the
plugin.

The real test is a three-way compare against the block the section was *originally*
emitted from, which separates project content from plugin drift instead of guessing.
Provenance closes the *length* half of that as of this release — `emitted=<N>` is the
originally-emitted length itself, not a ratio against a block that may have grown or
shrunk since. What it still cannot see is a same-length edit: replace ten lines of
plugin prose with ten lines of a user's own and the count never moves. Closing that
needs the emitted block's own content, or a hash of it, recorded in the marker — a
further format change across all nine blocks and both generators. It is deferred until
the first report of a section lost with all three triggers quiet, or the next time a
block shrinks between releases. Deferred alongside it: a **volume-neutral fixture** — a
section that restates the block's own material more verbosely, so it is more than ~20
lines over `<N>` while almost none of its lines are absent from the block. The fixture
that exists is both, so the integration test proves the gate fired, not which trigger
fired it; build the neutral one the first time provenance and Volume are suspected of
disagreeing in the field. One residual is known and accepted: the sanity band's ~20 and
the trigger's own ~20 stack, so an `<N>` overstated by up to ~20 buys roughly 40 lines
of growth in which only Volume — the judgement-call proxy — is still watching.

**Attribution check — applies to case 3 of the six sections below that replace on a
missing marker.** Three do not need it: `Code reuse discipline` already preserves,
`Session Continuity` has its own `handoff.md` content test, and `Track-aware routing`
carries a heading this plugin coined, which no project would write by accident.
Case 3 is "heading present, marker absent", and it replaces on the theory that a
markerless copy must be pre-marker plugin legacy. That theory is a guess, and it is
wrong exactly where it costs most: most of these headings are ordinary English that a
project would plausibly write for itself. A hand-written 15-line
`Git hygiene & commit cadence` holding a team's own conventions is 0.1× its block, so
the Growth check never fires and case 3 replaces it without a word.

So case 3 does not fire on the heading alone. Each rule below names a **sentinel** — a
string only a past emitter would have written into that section. Before replacing:

- **Sentinel present in the section body** → it is emitted content. REPLACE as in
  case 2, still subject to the Growth check above.
- **Sentinel absent** → you cannot attribute the section to a past emitter. Do NOT
  replace it. Leave it byte-for-byte intact, insert the plugin block as a separate H2
  section immediately below it, and report the outcome in these terms:

  > `<heading>`: I cannot attribute this section to a past emitter — it has no version
  > marker and none of the phrases an older `/adapt` would have written. I left it
  > exactly as it was and put the current plugin version below it, so nothing of yours
  > was touched. If it *is* an old plugin section, delete your copy and re-run
  > `/adapt` and it will upgrade cleanly.

  Two sections sharing a heading is a state the user has to resolve, so tell them
  which one is theirs and what resolves it. A report that only says "both now exist"
  leaves them to work out both.

This is `Code reuse discipline`'s case 3 and `Session Continuity`'s `handoff.md` test
generalised, and it accepts one failure to avoid a worse one: an old emitted section
that has drifted past its sentinel gets preserved instead of upgraded. A stale section
costs one `/adapt` run after the user deletes it; a destroyed one costs whatever was
in it.

**Insert or upgrade the Autonomy and user interruption section.** This section applies to ALL projects (web and native equally — agents over-asking is platform-agnostic). Scan CLAUDE.md for the heading `^#{2,3} Autonomy and user interruption` and its version marker `<!-- gstack-autonomy-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** (legacy pre-v2.8.0) → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. Sentinel: the body contains `The only five reasons to stop and ask` or `Forbidden phrases`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/autonomy.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Git hygiene & commit cadence section.** This section applies to ALL projects (git is universal). Scan CLAUDE.md for heading `^#{2,3} Git hygiene` and its version marker `<!-- gstack-git-hygiene-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v9`** → skip (idempotent).
2. **Heading present + marker `v1` or `v2` (older emitters — universalist convention rule, autonomy cross-ref missing, stash advice without WIP-branch caveat) OR different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. (The Git hygiene block has H4 subsections; "next heading" alone would stop at the first one and leave old v1 prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. Sentinel: the body contains `Hygiene rules (NEVER violate)` or `Committing is not backing up`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/git-hygiene.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Multi-lens review section.** This section applies to ALL projects (review hygiene is universal). Scan CLAUDE.md for heading `^#{2,3} Multi-lens review` and its version marker `<!-- gstack-multi-lens-review-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches the current version (`v5`)** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Multi-lens review block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.)
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. Sentinel: the body contains `What counts as ship-worthy` or `pitfall-verification`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/multi-lens-review.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Code reuse discipline section.** This section applies to ALL projects (the agentic-duplication failure mode is platform-agnostic). Scan CLAUDE.md for heading `^#{2,3} Code reuse discipline` and its version marker `<!-- gstack-code-reuse-vN -->`. Apply the four-case logic, but with a CRITICAL difference from the other marker-managed sections in case 3:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below. (The Code reuse block has subsections one level below the root; "next heading" alone would stop at the first subsection and leave old prose behind.)
3. **Heading present + marker absent** → **PRESERVE, do NOT replace.** This section was newly introduced in v2.12.0 of the plugin — markerless `Code reuse discipline` headings cannot be pre-marker plugin content, which means they are *user-authored* sections that happen to share the heading. Replacing them would silently destroy the user's hand-written content. Instead, leave the user's section intact and surface a notice to the user in the adapt summary: "Found existing markerless `Code reuse discipline` section in CLAUDE.md; preserved as-is. To switch to the plugin-managed version, delete your existing section and re-run `/adapt`." This is the key difference from the other marker-sections (Autonomy, Git hygiene, Multi-lens review, etc.) where case 3 legitimately treats markerless content as pre-marker plugin legacy.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on this section at ship time.

The block to insert: read `blocks/code-reuse.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Keep the plan true to the code section.** This section applies to ALL projects (plan drift is not track-specific). Scan CLAUDE.md for heading `^#{2,3} Keep the plan true to the code` and its version marker `<!-- gstack-plan-fidelity-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. (The block has H3 subsections; "next heading" alone would stop at the first one and leave old prose behind.) **If the existing root is H3**, demote every subsection in the replacement one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. (This heading is specific enough that a user-authored collision is unlikely, but "unlikely" is not a test, and the cost of being wrong is the user's section.) Sentinel: the body contains `The three ways a plan goes stale` or `fix the plan in the same commit`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root). If you instead insert it under `## Skill routing` as H3, you MUST demote every H3 subsection to H4 — otherwise the next marker upgrade stops at the first subsection and leaves stale content behind.

The block to insert: read `blocks/plan-fidelity.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Session Continuity section.** This section applies to ALL projects (context handoff is platform-agnostic). Scan CLAUDE.md for heading `^#{2,3} Session [Cc]ontinuity` and its version marker `<!-- gstack-session-continuity-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v3`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level (see the heading-level rule below). Run the **Growth check** above before replacing.
3. **Heading present + marker absent** → the section is either a pre-2.36.0 emitted block or one the user wrote themselves, and unlike `Git hygiene & commit cadence` or `Autonomy and user interruption`, "Session Continuity" is a heading a project could plausibly own. Tell them apart before touching it: treat it as emitted ONLY if the section body mentions `docs/superpowers/handoff.md`. **If it does** → REPLACE as in case 2. Run the **Growth check** above before replacing. This is the upgrade that matters, because every pre-2.36.0 emitter wrote a sensor keyed only to the `## Mode: auto` Markdown marker, which `/superpowers-gstack:context-handoff` deletes the moment it writes YAML — so those projects re-ask the opt-in question after every single compact. **If it does not** → leave the user's section untouched, insert the block as a separate H2
   section, and report it the way the **Attribution check** above reports a preserve:

   > `Session Continuity`: I cannot attribute this section to a past emitter — its body does
   > not mention `docs/superpowers/handoff.md`, which every emitted copy carries. I left it
   > exactly as it was and put the current plugin version below it, so nothing of yours was
   > touched. If it *is* an old plugin section, delete your copy and re-run `/adapt` and it
   > will upgrade cleanly.

   Never silently overwrite a section you cannot attribute to a past emitter.
4. **Heading absent** → APPEND the block as H2.

**Heading-level rule.** This is the general rule for every marker-managed section, stated once here: when the section you are replacing is rooted at H3, demote the block's first line to `###` **and** demote any `###` subsections it contains to `####`. Do not reason about whether a particular block "has subsections today" — that is a claim about a file, and it expires the moment someone adds one. Applying the demote unconditionally is a no-op for a block with no subsections and the fix for one that grows them. (The `gstack-routing` v1→v2 bump in 2.36.1 activated exactly this bug, which had sat unreachable for as long as its marker never moved.) The block is NOT exempt from matching the existing root level either. `setup-routing` before 2.36.0 emitted this section as `### Session Continuity` nested under `## Skill routing`; pasting the H2 block verbatim over an H3 root promotes it to H2 and silently reparents every following H3 sibling underneath it. So when the section being replaced is H3, demote the block's FIRST LINE to `###`, keeping whatever version marker the block file itself carries, and paste the remaining lines unchanged. Copy the marker from the block — never retype it from this instruction, which is how it goes stale the next time the block is versioned — and then append the provenance comment after it, exactly as **Record what you emitted** above requires. A demoted heading is still one this plugin emitted, and the block file's own marker never carries `emitted=`, so copying the marker is not enough on its own. Leaving it off here would strand provenance on exactly the oldest projects: an H3 root means a pre-2.34.0 adaptation, which is the population with the most accumulated content to lose and the one the growth gate most needs a real number for.

The block to insert: read `blocks/session-continuity.md` (see **Shared block files** above) and insert its content verbatim, subject to the heading-level rule above.

**Verify after inserting.** "Modify the template's first line, then paste the rest verbatim" is the instruction shape most easily skipped under pressure — the reflex is to paste the whole block unchanged. So do not trust that you applied it: re-read the section you just wrote, and confirm its first line has the SAME number of `#` characters as the heading you replaced. If it does not, fix it now, before moving on. Getting this wrong is silent — the file still looks well-formed, but every H3 that followed the section has been reparented underneath it.

**Preserve or upgrade existing Track-aware routing.** Before
inserting the Track-aware routing section, scan the project's
CLAUDE.md. Check two things independently: (a) does any heading
matching `^#{2,3} Track-aware routing \(dual-track\)` exist (H2 or
H3 — `setup-routing` emits H3 as subsection, `adapt` historically
emitted H2 as top-level), and (b) is there a version marker
`<!-- gstack-routing-vN -->` on that heading line (currently `v2`).
Four cases:

1. **Heading present + marker matches current version (`v2`)** →
   skip (idempotent — re-running adapt does not pollute the file).
2. **Heading present + marker present + different version** →
   REPLACE the section from the heading down to (but not including)
   the next heading of the same OR shallower level. Preserves
   surrounding CLAUDE.md content. This is how routing rules evolve
   without manual editing across N projects. Preserve the original
   heading level (H2 or H3) — do not change it during upgrade. Run
   the **Growth check** above before replacing. **If that level is
   H3, you MUST also demote every `###` subsection in the
   replacement block to `####`.** The block ships H2-rooted with H3
   subsections; pasting it under an H3 root leaves the subsections
   as SIBLINGS of the root, so the next upgrade — which replaces
   "through the next heading of equal-or-shallower level" — stops at
   the first subsection and leaves stale content behind. This path
   was unreachable while the marker sat at `v1` (case 1 always
   fired); the `v2` bump activates it.
3. **Heading present + marker absent** (legacy v2.3.0/v2.3.1
   projects) → REPLACE the section the same way as case 2. Run the
   **Growth check** above before replacing. Treats the missing
   marker as "older than v1". This is a one-time silent upgrade;
   the content replaced is byte-identical to what's already there
   in v2.3.2, plus the marker. Preserve the original heading level.
4. **Heading absent** → APPEND the full section as H2 (truly new
   adaptations, or projects that never had dual-track routing).

The version marker is an HTML comment so it does not render in
Markdown previews. Bump the version (`v1` → `v2`) only when the
section's semantics change, not for cosmetic edits.

The block to insert: read `blocks/track-routing.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Native Apple development tools section.** Only emit this section when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip entirely for web-only projects). Scan CLAUDE.md for the heading `^#{2,3} Native Apple development tools` and its version marker `<!-- gstack-xcode-tools-vN -->`. Apply the same four-case logic as Track-aware routing above:

1. **Heading present + marker matches `v6`** → skip (idempotent).
2. **Heading present + marker `v1`–`v5`** (v1 assumed XcodeBuildMCP universally; v2 added CLI fallback but missed capabilities; v3 hardcoded one team's `DEVELOPMENT_TEAM`; v4 was simulator-only and had no macOS build/launch path at all; v5 hardcoded an `iPhone 16` destination that Xcode no longer ships) → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. (The Native Apple tools block has H4 subsections; "next heading" alone would stop at the first one and leave old prose behind.) **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level so subsections do not sit at the same level as the root — same demote requirement as case 4 below. Auto-upgrade is what the marker pattern is for.
3. **Heading present + marker absent** (pre-v2.7.0) → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. Sentinel: the body contains `XcodeBuildMCP` or `MUST be performed by the agent`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/xcode-tools.md` (see **Shared block files** above) and insert its content verbatim.

**Insert or upgrade the Companion skills (discovery) section.** Only emit when `.gstack/track` exists and equals `ios`, `macos`, or `both` (skip for web-only projects). Scan CLAUDE.md for heading `^#{2,3} Companion skills` and its version marker `<!-- gstack-companion-skills-vN -->`. Apply the same four-case logic:

1. **Heading present + marker matches `v2`** → skip (idempotent).
2. **Heading present + marker present + different version** → REPLACE through next heading of equal-or-shallower level. Preserve original heading level. Run the **Growth check** above before replacing. **If the existing root is H3** (nested under `## Skill routing`, as pre-2.34.0 setup-routing emitted), you MUST demote every subsection in the replacement block one level (H3 → H4) so subsections do not sit at the same level as the root — same demote requirement as case 4 below.
3. **Heading present + marker absent** → REPLACE the same way; one-time silent upgrade adds the current marker. Run the **Attribution check** above FIRST — replace only if the sentinel is present; if it is absent, preserve the section and insert the block below it — then the **Growth check** before replacing. Sentinel: the body contains `swiftui-expert-skill` or `discovery — not routing`.
4. **Heading absent** → APPEND the block below as H2 (subsections stay at H3, one level below the root — the REPLACE-through-equal-or-shallower-heading invariant holds). If you instead insert the block under `## Skill routing` as H3 to match `setup-routing`'s structure, you MUST also demote every H3 subsection in the block to H4. Otherwise the H3 subsections sit at the SAME level as the H3 root, and the next marker upgrade stops at the first subsection and leaves stale content behind — same heading-hierarchy class bug `/codex review` flagged on the v2.12.0 Code reuse section.

The block to insert: read `blocks/companion-skills.md` (see **Shared block files** above) and insert its content verbatim.

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
3. **Diff against the snapshot and classify every removed line.** Run:

   ```bash
   diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md
   ```

   Read the `<` side. Every removed line is either **(a)** plugin prose replaced by a
   newer version of the same block — expected — or **(b)** project-authored content,
   which is a loss. Put every hunk in one of those two buckets; the (b) list is what
   the report's **Removed** block prints. **When a hunk cannot be attributed to
   either bucket — and it often cannot, since a diff against the NEW block cannot
   tell project content from reworded old plugin prose — list it.** An over-inclusive
   Removed block costs the user a glance at a line that turns out to be plugin prose;
   a missing one costs them the content. The block's job is to put candidates in front
   of a human, not to be an oracle. Do not summarise the diff without reading it, and
   do not answer this item from memory: the file you would be recalling was
   overwritten earlier in Step 5. If the snapshot is missing because CLAUDE.md did
   not exist before this run, say that instead — do not skip the item silently.

**Write the three block labels verbatim, in English, even when the rest of the
report is in the user's language.** `**Removed (not plugin prose):**`,
`**Deferred (grown past its block, not upgraded):**` and the sentinel
`Nothing project-authored was removed.` are structural markers that lint E13 pins
and tooling greps — the prose inside and around them follows the user's language,
the labels do not.

Report to the user:

> **Changes made:**
> - [list each change]
>
> **Preserved:**
> - [existing CLAUDE.md content that was kept]
>
> **Removed (not plugin prose):**
> - [one line per hunk the verify diff classified as project content: the section
>    it came from, its line count, and where the content went — moved to an
>    unmarked section, or lost]
> - If nothing project-authored was removed, write exactly:
>   `Nothing project-authored was removed.`
>
> **Deferred (grown past its block, not upgraded):**
> - [one line per section the Growth check left at its old version: the section, its
>    line count against the block, and the marker it is still on — or, when it has
>    none, say so instead of inventing one. The Growth check runs in cases 2 **and
>    3**, and case 3 is "marker absent": that section is deferred at no version at
>    all, which is the fact the user needs]
> - Omit this block entirely when nothing was deferred.
>
> (The Growth check reports here. The Attribution check and Session Continuity's case 3
> report inline where they fire, in their own multi-line form — a preserve has to explain
> itself, where a deferral only has to be counted.)
>
> **Snapshot:** `.gstack/CLAUDE.md.pre-adapt` holds CLAUDE.md exactly as it was
> before this run. Restore the whole file with
> `cp .gstack/CLAUDE.md.pre-adapt CLAUDE.md`. [If an earlier snapshot was rotated
> aside at the start of Step 5, name that path too.]

**Never omit the Removed block.** An absent block reads as "not checked" — which is
the state the block exists to prevent — so it is the one part of this report that
must appear even when it is empty. A line under **Changes made** such as
`Native Apple development tools: v3 → v5` is true and says nothing about the 125
project-authored lines that upgrade destroyed; only this block can.

**Deferred is not Removed.** A deferred section lost nothing — that is the whole point
of deferring it — so filing one under a heading that says content was removed
contradicts the verify step that produced the list, and trains the user to discount the
block that matters. Keep the two apart even when only one of them has entries.

Whenever a marker-managed section was replaced at all — not only when the Removed block
has entries — add:

> **Where project knowledge belongs.** A heading carrying a `gstack-<name>-vN` marker
> is plugin-owned: `/adapt` replaces the whole section on every upgrade. Pasting
> rescued content back into one guarantees a repeat at the next upgrade. Project
> findings — the measurement you took, the flag that turned out to work, the thing
> that cost you an hour — belong in your own H2 section with no marker. `/adapt`
> leaves those alone, with one exception: the headings it manages are reserved even
> when unmarked, because an unmarked copy of one reads as an older emitted section.
> Prefix your own headings with this project's name and none of them can collide.

Then ask:

> Would you like me to run a comprehensive review of the adaptation? This will check that:
> - All routing rules are consistent with your project structure
> - No existing CLAUDE.md content was lost or corrupted
> - The selected skills match your actual tech stack, test setup, and deployment
> - docs/superpowers/ structure is correct
> - There are no conflicts between existing project conventions and the new workflow
>
> The review takes a minute but catches issues before you start using the workflow. Recommended for projects with complex existing setups.

**STOP HERE.** Do not continue to Step 7 or add any other content. End your message with the question above. Wait for the user's response before proceeding.

If the user says yes, run the review:

1. **Re-read the updated CLAUDE.md** end-to-end and check for internal consistency
2. **Cross-check routing against project files** — does the routing reference skills that don't make sense? (e.g., `/qa` listed but no browser UI, `/cso` listed but no auth/user data)
3. **Re-check the preservation classification** — re-run `diff .gstack/CLAUDE.md.pre-adapt CLAUDE.md` and re-read the `<` side with fresh eyes. The mandatory verify step above already classified each hunk; this pass asks whether any hunk filed under "expected plugin prose" is actually project content wearing plugin-shaped wording.
4. **Check for contradictions** — do existing CLAUDE.md instructions conflict with the new routing rules?
5. **Validate structure** — do all referenced directories exist? (`docs/superpowers/specs/`, `docs/superpowers/plans/`)
6. **Test routing logic** — walk through 3-4 common scenarios for this project type and verify the decision tree produces the right skill

Report findings. If issues are found, fix them immediately and re-verify.

### Step 7: Suggest next steps

After the review (or if the user skipped it):

> **Next steps:**
> - [suggest the appropriate first action based on project state]
>   - Working on a new feature? → `/superpowers:brainstorming`
>   - Have code ready for review? → `/review`
>   - Starting fresh? → `/office-hours`
>
> **Tip:** Run `/superpowers-gstack:adapt` again after major project changes (new deploy target, added test framework, etc.) to update routing.
