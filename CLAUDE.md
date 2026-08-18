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

A **separate, independent** `check-models` job (`scripts/check-new-models.py`) queries the Anthropic `/v1/models` API and compares it, per tier, against the model IDs `skills/setup-routing/model-routing.md` references. When a newer model ships (e.g. Sonnet 5 on 2026-06-30), it opens a `model-review` issue — it never edits model IDs or feeds the auto-edit job, because model IDs are pinned snapshots with behaviour differences and adopting one is a human review call, not an auto-merge. Detection is stateless (version-tuple compare, unparseable/preview IDs skipped) and idempotent (won't re-open an issue already covering the model). The job self-tests its detection logic in CI before the live query.

The plugin ships a SessionStart hook (`hooks/hooks.json` → `scripts/check-plugin-version.sh`) that nudges `/adapt` when a project's generated CLAUDE.md lags the installed plugin version — every plugin user gets it automatically, and it exempts this repo. A second, maintainer-only hook (`scripts/notify-pending-updates.sh`, surfaces pending auto-update PRs) is opt-in via `./scripts/setup-hooks.sh`.

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

The version-check hook is shipped by the plugin — no setup needed. For the
maintainer-only update-notification hook (optional, after cloning the repo):
```bash
./scripts/setup-hooks.sh      # Add the notify-pending-updates SessionStart hook
```
If you previously ran an older `setup-hooks.sh` that installed the version-check
hook into `~/.claude/settings.json`, remove that entry — the plugin now ships it,
so the settings.json copy causes a double nag. (`setup-hooks.sh` warns if it sees one.)

## Upstream sources

| Component | Source | Version tracking |
|-----------|--------|-----------------|
| GStack | `garrytan/gstack` | Git commit hash |
| Superpowers | `obra/superpowers` | plugin.json version |
| Claude Code | `@anthropic-ai/claude-code` npm | npm version |

## Session continuity

On session start or after /compact, classify `docs/superpowers/handoff.md` before touching it — consuming a handoff clears it, so a wrong classification destroys the contents. **Empty/whitespace-only** → say nothing, this is the resting state. **Continuous-mode stub** (frontmatter with `mode`, no `next_step`) → say nothing, leave it untouched, continuous handoff is already active. **Complete handoff** — `type: handoff` (v2.1.1+) or both `session_end` and `next_step` without `type:` (legacy v1.12.0 → v2.1.0), *and* a usable `next_step` → consume it. **Anything else** — a handoff claim with no `next_step`, a file cut off mid-write, or no frontmatter at all → say in one line that it could not be read as a handoff, do not present it, and do not clear it (pre-1.12.0 prose-only auto-consume was removed in 2.36.1; it silently destroyed project notes kept at that path). When it is a complete handoff, quote `next_step` verbatim, name the `active_task` ID, and surface `env` (venv, dev_server, test_cmd) so commands work immediately. Then proceed normally — do not ask "ready to continue?". Read the `mode:` field BEFORE clearing — clearing first destroys the value the next paragraph needs. If the handoff was in continuous mode — that is, `mode: continuous` **or** the legacy `mode: auto` — do NOT blank the file: rewrite it carrying just `type: handoff` and `mode: continuous`, so the setting survives the next compact. Otherwise clear it (write empty string) immediately after presenting the summary.

After /compact: check whether continuous handoff is already active, using the `mode` you read above — YAML `mode: continuous`, or the legacy YAML value `mode: auto` (pre-2.36.0). Only when the YAML `mode:` key is absent entirely does the legacy `## Mode: auto` Markdown marker (pre-2.1.1) count; an explicit `mode: manual` beside a stale marker means manual. If none is present, ask the user once: "Context was compressed. Want me to keep handoff.md updated continuously for this session? I'll refresh it at each milestone and suggest /clear when context gets heavy." If yes, invoke the context-handoff skill. This is a handoff-persistence setting and has nothing to do with Claude Code's **auto mode**, which is a permission mode — never change one because of the other.

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
- Autoimplement a plan, "run plan end-to-end", "auto-advance phases" → invoke /superpowers-gstack:autoimplement. Removes y/n friction at phase boundaries by chaining /review + /pitfall-verification automatically (pitfall itself auto-chains /codex review and the third lens per tier — no separate codex step, avoiding a double Codex pass). v2.14.0+ also runs an **active pre-flight chain** on the plan ITSELF (pitfall + codex on plan body) before Phase 1 unless the latest plan commit is a pre-flight marker — closes the gap between /writing-plans and autoimplement. Skip-condition (tightened in v2.14.2): latest commit subject on plan path must match `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)` regex. Refuses on: <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations / secrets / credentials / .env / .ssh.
- Multi-model verification → invoke /superpowers-gstack:pitfall-verification. It is a multi-model orchestrator: for ship-worthy changes it auto-chains `/codex review` (Stage 2), and for high-stakes changes (architecture / real-time / security / contracts / migration-logic) also `/superpowers-gstack:third-lens-review` (Stage 3, external model house via OpenRouter), ending in an adversarial synthesis (Stage 4). Stages fire automatically per tier with no confirmation prompt; trivial changes get only the free self-pitfall pass.
- third-lens-review (normally auto-invoked by pitfall-verification Stage 3; invoke directly only for an ad-hoc third-house read) → runs an external model house on the PATCHED artifact (`scripts/third-lens-review.py`). Routing by `--role`: architecture=GLM-5.2 (default, OpenRouter), correctness=DeepSeek V4-Pro (OpenRouter), countersynthesis=OpenAI via the `codex` CLI (subscription). OpenRouter key in Keychain `openrouter-api-key`; the `sensitive` role was removed in 2.18.0.
- After a PRD/spec/plan for a native Apple app, before implementation → invoke /superpowers-gstack:macos-native-review (macOS) or /superpowers-gstack:ios-native-review (iOS/iPadOS). HIG-citation-grounded conformance gate; complementary to pitfall-verification and quality-review.
- After a PRD/spec/plan, before implementation — "will this feel good?", perceived quality, loading/empty states, error recovery → invoke /superpowers-gstack:quality-review. Complementary to pitfall-verification ("will this work?").
- E2E test a Swift app, "test the app", "trykk gjennom flyten", "e2e", press buttons and verify result → invoke /superpowers-gstack:e2e-route. Pure dispatcher: reads platform (scheme/SUPPORTED_PLATFORMS/.gstack/track) × intent (CI-env/verbs; asks once if ambiguous; multiplatform → asks iOS/macOS/both) and routes to /macos-e2e-scaffold, /ios-e2e-scaffold, MCP-live simulator automation (XcodeBuildMCP / ios-simulator), or visual-regression review (/ios-design-review for iOS, /design-review for macOS). Does not execute itself — names the executor + next action, then hands off.
- Scaffold committed XCUITest for an iOS SwiftUI app → invoke /superpowers-gstack:ios-e2e-scaffold (manual only; mirrors /macos-e2e-scaffold with iOS heuristics — TabView/NavigationStack scene-walk, sheet/tab/push/gesture TIERs, iOS-Simulator runner). Normally reached via /e2e-route.
- Visual exploration of an iOS/iPadOS app when the accessibility tree is insufficient (layout regressions, visual landmarks, "find visual issues") → invoke /superpowers-gstack:ios-visual-explore. Tier-2 escalation after XCUITest, not first resort; paid Gemini computer-use per run. Normally reached via /e2e-route.
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- End of day, switch project, save progress → invoke context-save
- Resume previous session, restore state → invoke context-restore
- Context long, before /clear, before /compact → invoke context-handoff
- Code quality, health check → invoke health

## Release gate (this repo)

Before merging/pushing any plugin change (skills/, scripts/, CLAUDE.md, workflows):

1. `python3 scripts/lint-skills.py` must be GREEN — it enforces frontmatter validity, cross-reference resolution, routing coverage, CHANGELOG↔plugin.json version match, multi-lens marker consistency, the stale-pattern denylist, a ≤30-word description budget, and single-sourcing of the emitted CLAUDE.md blocks (E8: every shared block in `skills/setup-routing/blocks/` exists, is referenced by both generators, and has no inline copy in either SKILL.md — so setup-routing and adapt can't silently write different content). CI runs the same lint plus the pytest suites on every push/PR (`.github/workflows/lint.yml`).
2. Ship-worthy change ⇒ bump `.claude-plugin/plugin.json` (or the marketplace cache never updates) **and** add the `## [X.Y.Z]` CHANGELOG entry (the lint refuses a version without one).
3. New/removed/renamed skill ⇒ update README's skill list and the routing section above (the lint refuses unrouted skills).
4. When purging a stale pattern, add it to `DENYLIST` in `scripts/lint-skills.py` so it stays purged.

(Context: four releases, 2.20.0–2.22.0, shipped without CHANGELOG entries before this gate existed. The lint makes that class unrepeatable.)

<!-- BEGIN own-blocks — generated by scripts/sync-own-claude-md.py; do not edit by hand -->

<!-- This repo eats its own dog food: the blocks below are byte-identical to
     what /adapt emits into every other project. Regenerate with
     `python3 scripts/sync-own-claude-md.py`; lint rule E11 fails if stale. -->

## Autonomy and user interruption <!-- gstack-autonomy-v2 -->

Default to autonomous continuation. Stopping to ask the user is the LAST resort, not the default. When you complete a planned phase or pass a milestone, the next action is the next phase — NOT a status report followed by "ping me to continue".

### The only five reasons to stop and ask

1. **User-territory operation** — Apple Developer Portal registration, OAuth/SSO login, payment authorization, anything requiring 2FA / Apple ID / human credentials the agent cannot supply
2. **Destructive operation needing explicit approval** — `rm -rf`, `git push --force`, dropping a database table, deleting cloud resources, anything under the user's `/careful` rules
3. **Genuinely ambiguous design choice** — two paths with materially different long-term consequences AND no signal in the spec / plan / prior conversation. ("I assume green but maybe blue?" is NOT this — that is over-asking.)
4. **Explicit checkpoint in the skill or plan** — e.g. an Approve/Revise gate, `executing-plans`' phase review
5. **Truly blocked** — missing information you cannot derive, a loop you cannot break, an error you cannot interpret after reasonable investigation (docs, search, the obvious fix first)

### Do NOT stop to

- ❌ Report completed work and ask "shall I continue with the next phase?"
- ❌ Check in at milestones because it feels considerate
- ❌ Ask "should I do X?" when X is obviously the next step in scope
- ❌ Wrap up early because the plan turned out larger than expected — finish it

If the next step is clearly within scope, DO IT. Report after it's done.

### Forbidden phrases

If one of these appears without a category-1-to-5 reason, you have failed the autonomy default: "Ping me when you want me to continue", "Let me know when you're ready for the next round", "Ready when you are", "Awaiting your go-ahead", "Si fra når jeg skal fortsette", "Bash-prompten din er fortsatt aktiv — si bare 'fortsett'". About to write one? If there is no real category-1-to-5 reason, delete the sentence and do the next thing instead.

### Status updates DURING work, not AS wait-states

- ✅ "BookmarkStore + 7 tests green. Moving to RecordingScanner now."
- ❌ "Phase 1 done. Here's a 12-row status table. Ready for UI when you say so."

When you DO legitimately stop (scope done, or a category-1-to-5 reason fires): state what's done in one or two sentences, name the specific blocker if any, and do NOT propose new work or invite continuation.

## Git hygiene & commit cadence <!-- gstack-git-hygiene-v4 -->

Commit at meaningful milestones — not at every file save, not only at session end.

### When to commit

- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- Before switching to unrelated work (don't mix concerns in one commit)
- After a reversible decision (so `git revert` works cleanly later)
- Before long-running or risky operations (rollback point)

Do NOT commit mid-task, just to "save progress" (use `git stash` for holds of minutes-to-hours; a WIP branch for anything longer), or with unrelated changes batched together — split them.

### Commit message format

Follow the convention established in the repo (`git log --oneline -10` first). If the log is empty or has no consistent style, use `<type>(<scope>): <one-line summary>` plus a body saying what changed and why (not how); types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. If the log is inconsistent, also note that in your final summary so the user can decide whether to standardize.

### Hygiene rules (NEVER violate)

- ❌ `git commit --no-verify` — if a hook fails, fix the root cause
- ❌ `git commit --amend` on already-pushed commits — rewrites shared history
- ❌ `git push --force` to `main` or shared branches
- ❌ `git reset --hard` without stashing or committing first — silent work loss
- ❌ `git add -A` / `git add .` when secrets, large binaries, or build artifacts may be present — stage specific paths

### Landing the branch

A branch is done when it is **merged or deliberately discarded** — not when the code
works. Work sitting on an unlanded branch is invisible: it doesn't ship, doesn't reach
review, and rots against the default branch while everything else moves.

- **Never end a session silently on a branch with unmerged commits.** Say where the
  work stands — landed, ready to land, or still open — even when the answer is "still
  open". The failure mode is not a wrong decision, it's no decision being stated.
- **Landing is a skill, not a hand-rolled merge:** `/ship` (tests → review → PR) or
  `/superpowers:finishing-a-development-branch` (merge, PR, or discard). Pick one.
- **Deliberate abandonment counts as done.** Say so and delete the branch. An
  explicitly discarded branch is finished; a silently abandoned one is debt nobody
  remembers taking on.
- **Closing a PR does not delete its branch.** Delete it after the PR merges or
  closes, or it outlives the PR and reads as open work forever.

### Cadence rule

More than 5 commits in a row without testing the cumulative state → STOP and verify (build, run tests) before continuing. This is a legitimate category-5 stop per the Autonomy section — cumulative breakage is harder to diagnose than per-commit breakage. A session where NO commit was tested is committing "progress without verification": run the project's test suite, or document explicitly why testing is deferred.

## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v5 -->

Substantive changes get multiple review lenses — different model houses catch what the others miss. **`pitfall-verification` orchestrates them automatically per tier — never invoke Codex or the third house by hand:**

1. **Self-check** (always, ~30 sec): placeholders, consistency, scope drift, ambiguity
2. **Self-pitfall** (always, max 2 rounds): `/superpowers-gstack:pitfall-verification` — domain-specific traps
3. **Codex** (auto on ship-worthy): `/codex review` — cross-file drift and concrete run bugs self-review misses
4. **Third house** (auto on high-stakes: architecture / real-time / security / contracts / migration-logic): `/superpowers-gstack:third-lens-review` — a different model house, ending in an adversarial synthesis

Stages 3–4 fire per tier with **no confirmation prompt**; trivial changes (docs/typo) get only the free self-pitfall pass. Cost is reported after each call, not gated before it.

### What counts as ship-worthy (run Codex)

**YES:** commits that bump version files or produce CHANGELOG entries; `feat`/`fix`/`refactor` commits affecting runtime behavior; changes to public contracts (APIs, schemas, generated artifacts, file formats).

**NO:** pure docs/typo fixes, comment-only changes, WIP commits, test-only coverage additions.

### Order and cost

Run self → pitfall → codex → third house. Each pass fixes what the previous one couldn't and reads a cleaner artifact — reversing the order pays an expensive lens to re-find what a cheaper pass would have caught. Codex ≈ $0.05–0.20 + 30s–2min per review; acceptable for ship-worthy work, wasteful on every commit.

### The third house (escalation)

Its value is **training-distribution distance**, not raw IQ: it catches architecture-level mistakes ("you never wired it together"), degraded-state bugs, and assumptions the first houses took for granted.

- **Gate:** architecture, real-time, security, public contracts, or migration logic — skip for standard changes.
- **Routing by `--role`** (`scripts/third-lens-review.py`): `architecture`=GLM-5.2 (default, OpenRouter); `correctness`=DeepSeek V4-Pro (OpenRouter); `countersynthesis`=OpenAI via the `codex` CLI. GLM/DeepSeek run on non-Western infra — do NOT send sensitive artifacts (auth/keys/health/finance); keep those to the self + Codex lenses.
- **Cost:** ~$0.05/run. Key in macOS Keychain `openrouter-api-key`.
- **Synthesis is mandatory and adversarial:** a third-house finding is real until explicitly refuted; disagreement is the signal. Never dump raw output.

## Code reuse discipline (before writing) <!-- gstack-code-reuse-v2 -->

Before introducing a new reusable concept — a component, helper, model, type-alias, view-modifier, extension, hook, utility — search the codebase for an existing implementation first. This catches context-bounded duplication: a subagent writing a new `EntityCard` when one exists one directory over. It is NOT a DRY-purity rule — three similar lines are fine and premature abstraction is a real cost; the rule fires only when introducing something that could plausibly already exist.

### When to scan

- A new struct, class, or component with a domain-shared name (`Card`, `Item`, `Cell`, `Detail`, `Manager`, `Service`, `View`, `Modifier`, `Style`, …)
- A new helper that smells like utility (`formatX`, `parseY`, `validateZ`)
- A new extension, ViewModifier, ButtonStyle (Swift) or hook, HOC, wrapper component (web)
- A new shared model / DTO / schema

NOT for: lines inside an existing function, closures specific to one call-site, test helpers private to one file, one-off scripts.

### How

1. **Grep** the bare concept name (full-word, case-insensitive)
2. **Glob** matching file paths (`**/*Card*.swift`, `**/format*.py`)
3. **Read** the plausible matches — verify it's the same concept, don't skim
4. **Decide**: REUSE / EXTEND / WRITE NEW — and report which

Narrate one line in chat before scaffolding — "Checking for an existing `<concept>` … Found `EntityCard` at `Views/EntityCard.swift:14` — extending it" or "No matches — writing new". This is **narration, not a stop**: continue immediately; it adds no new category to the Autonomy section's stop rules.

### When dispatching a code-writing subagent

Include in the dispatch prompt:

> Before introducing new reusable concepts (components, helpers, models, extensions), search the codebase via Grep/Glob for existing implementations. If you find one, **use it or extend it** and continue with your delegated task — report what you reused. If not, scaffold new and report what you searched for. Escalate to the orchestrator ONLY if the reuse decision is genuinely ambiguous (extending would change semantics for existing callers).

The subagent must NOT stop with a recommendation after finding existing code — it completes its delegated task using the found implementation.

### Guardrails

- ❌ Do NOT pre-abstract: two similar lines stay two similar lines until a third shows up
- ❌ Do NOT refactor existing code unless the task asks for it — the scan reports; it doesn't authorize touching things
- ❌ Do NOT ask "should we be DRY about this?" — the default is yes-but-pragmatist; just scan
- A user override ("skip the reuse-check", "just write it") is informed — honor it without re-litigating

`/plan-eng-review` covers reuse at architecture time and `/review` catches violations post-implementation; this rule fills the implementation-time gap between them. Defer to plan-eng-review's findings for high-level architecture decisions.

## Keep the plan true to the code <!-- gstack-plan-fidelity-v2 -->

When implementation diverges from the plan, **fix the plan in the same commit as the divergence.** Not at the end, not at `/ship`, not "later".

A plan that describes something nobody built is worse than no plan: the next agent reads it as instructions and implements the abandoned design. Being out of date is passive; being confidently wrong is active harm.

### The three ways a plan goes stale

1. **Better approach found.** You read the existing code and the planned design turns out to be unnecessary or wrong. This is a *good* outcome — but the plan must now say what was built and why the draft was dropped.
2. **Task done out of order.** The user reports a bug that a later phase covers, so you do it now. Mark it done and note why the order changed.
3. **A measurement kills a premise.** The plan's reasoning rested on an assumption; you measured, and it was false. Record the number you measured, not just "this turned out differently".

### What to write

Replace the superseded section — do not append a correction below it. Someone skimming reads the first plausible thing they find.

- Mark the task done **in the notation the file already uses** — if the plan or progress file has an established convention (`- [x] … (sha)`, a `DONE:` prefix, a status column), follow it; introduce a marker of your own only when the file has none yet. What matters is that the marker carries the commit SHA, not which glyph carries it. A second completion format in a file that already had one makes the file harder to scan, which is the opposite of the point. Then state, in one or two sentences, how the built thing differs from the draft
- Keep the *reason* the draft was dropped. That is the part a future reader cannot reconstruct
- If part of the draft is still worth doing, move it to an explicit "deferred" note **with a trigger** — what would make it urgent — rather than leaving it inline as if it were planned work

### Deleting is allowed

If a whole phase is invalidated, say so at the top of that phase and stop maintaining its tasks. A struck-through phase with one honest sentence beats five obsolete task descriptions kept alive out of politeness to the draft.

### Why this is not the ship gate's job

`/ship` audits plan completion and classifies each item (`DONE` / `PARTIAL` / `CHANGED` / …), which is real and useful — but it runs at merge time, writes its findings to the PR body rather than back into the plan, and never runs at all on a branch that is not shipped. Divergence happens hours earlier, while the plan is still being read. Fix it there.

## Session Continuity <!-- gstack-session-continuity-v3 -->

On session start or after `/compact`, look at `docs/superpowers/handoff.md` and
**classify it before touching it**. Consuming a handoff clears it, so a wrong
classification destroys whatever was there.

- **Empty or whitespace only** → nothing to do, say nothing. This is the normal
  resting state after a handoff has been consumed.
- **Continuous-mode stub** — frontmatter carrying `mode` (`continuous`, or the
  legacy `auto`) and no `next_step`. This is the marker left behind by the
  clearing step below, not a handoff. Say nothing, leave the file exactly as it
  is, and treat continuous handoff as already active.
- **Complete handoff** — `type: handoff` (current, v2.1.1+), or both
  `session_end` and `next_step` with no `type:` (legacy v1.12.0–v2.1.0) — **and**
  a usable `next_step` to resume from. Consume it (below).
- **Anything else** → NOT consumable: frontmatter that claims to be a handoff but
  carries no `next_step`, a file cut off mid-write, or a file with no frontmatter
  at all. Do not present it as where you left off, and **do not clear it** — a
  truncated handoff and a project's own notes both live at this path, and neither
  survives being emptied. Say so in one line **and name the way out**, because
  this branch otherwise re-fires at every session start forever: the file has to
  be deleted, or overwritten by invoking `/superpowers-gstack:context-handoff`.
  Recurring noise the user cannot act on is worse than the state it reports.

For a complete handoff: present a one-line summary of where you left off. Quote
`next_step` verbatim, name the `active_task` ID, and surface `env` (venv,
dev_server, test_cmd) so commands work immediately. Then proceed normally — do
not ask "ready to continue?".

**Read the `mode:` field BEFORE you clear the file.** Clearing first destroys the
value the next step depends on. Once you have read it:

- `mode: continuous` (or the legacy `auto`) → do NOT blank the file. Rewrite it
  carrying just `type: handoff` and `mode: continuous` — the continuous-mode stub
  above — so the setting survives into the next compact. Blanking it here is
  exactly what makes a project ask the opt-in question forever.
- anything else → clear the file (write empty string), as before.

Either way, **copy what you consumed to `docs/superpowers/.handoff-last.md`
first** (one file, overwritten each time — not an accumulating log). Classifying a
handoff is a judgement call made by a model, not a parse, and a truncation that
lands *after* valid frontmatter looks complete from the inside. This makes any
misjudgement recoverable without depending on the file having been committed —
`handoff.md` is session state, and plenty of projects gitignore it.

After `/compact`, decide whether to offer **continuous handoff**, using the `mode`
you read above:

1. YAML `mode: continuous` — current form. Already on; stay silent.
2. YAML `mode: auto` — the pre-2.36.0 spelling of the same thing. Stay silent,
   and write `continuous` on the next write.
3. **No YAML `mode:` key at all**, but a `## Mode: auto` Markdown marker
   (pre-2.1.1) → stay silent, same treatment. The Markdown marker is consulted
   ONLY when the YAML key is absent: an explicit `mode: manual` sitting beside a
   stale marker means manual, not continuous.

If none of the three applies, ask once: "Context was compressed. Want me to keep
`handoff.md` updated continuously for this session? I'll refresh it at each
milestone and suggest `/clear` when context gets heavy." If yes, invoke
`/superpowers-gstack:context-handoff`. Do not re-ask on later compacts.

**Not Claude Code's auto mode.** Continuous handoff governs how often
`handoff.md` is rewritten. Claude Code's **auto mode** is a permission mode — a
classifier that approves or blocks tool calls, and the default for Pro/Max/Team
plans since 2026-08-14. The two are unrelated; never let one imply the other, and
never change a permission mode because a handoff file asked for `continuous`.

<!-- END own-blocks -->
