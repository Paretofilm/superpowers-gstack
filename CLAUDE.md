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

A **separate, independent** `check-models` job (`scripts/check-new-models.py`) queries the Anthropic `/v1/models` API and compares it, per tier, against the model IDs `skills/adapt/model-routing.md` references. When a newer model ships (e.g. Sonnet 5 on 2026-06-30), it opens a `model-review` issue — it never edits model IDs or feeds the auto-edit job, because model IDs are pinned snapshots with behaviour differences and adopting one is a human review call, not an auto-merge. Detection is stateless (version-tuple compare, unparseable/preview IDs skipped) and idempotent (won't re-open an issue already covering the model). The job self-tests its detection logic in CI before the live query.

The plugin ships a SessionStart hook (`hooks/hooks.json` → `scripts/check-plugin-version.sh`) that nudges `/adapt` when a project's generated CLAUDE.md lags the installed plugin version — every plugin user gets it automatically, and it exempts this repo. A second, maintainer-only hook (`scripts/notify-pending-updates.sh`, surfaces pending auto-update PRs) is opt-in via `./scripts/setup-hooks.sh`.

Since 2.50.0 the plugin also ships a session-continuity hook pair: `scripts/capture-session-tail.sh` (SessionEnd) deterministically salvages the last user/assistant exchange plus a git snapshot into `<git-dir>/gstack-last-session.md` when a session ends — including `/clear`, where no model is available to write a handoff — and `scripts/session-resume.sh` (SessionStart, matcher `startup|clear`) prints a "Where this project left off" banner from `progress.md`, a complete `handoff.md`, and that capture, before the user types anything. Both are read-only toward `handoff.md` (classification/consumption stays with the Session Continuity rules below), silent when the sources are absent, and active only in repos with a `docs/superpowers/` directory.

The update pipeline also keeps `skills/adapt/roster.md` current — if upstream adds, removes, or renames skills, the skill evaluation tables in that file are updated automatically.

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

This repo is also a Claude Code plugin (`superpowers-gstack`). The skill `adapt` sets up or upgrades a project's CLAUDE.md; every write goes through `scripts/adapt-claude-md.py`.

- Install via marketplace: `/plugin marketplace add Paretofilm/claude-marketplace` then `/plugin install superpowers-gstack@paretofilm-plugins`
- Dev mode: `./scripts/install-plugin.sh --dev` (creates symlink, skills won't be discoverable in the skills list)
- Skills:
  - `/superpowers-gstack:adapt` — set up a new project or adapt an existing one (preserves CLAUDE.md content; the merge itself is `scripts/adapt-claude-md.py`, deterministic and tested)

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

The rules are the emitted `Session Continuity` block in the own-blocks region below —
this repo follows exactly what `/adapt` writes into every other project. In short:
classify `docs/superpowers/handoff.md` before touching it, consume only a complete
`type: handoff` with a `next_step`, keep a `mode: continuous` stub alive, and never
confuse continuous handoff with Claude Code's `auto` permission mode.

## Skill conversation discipline

When a skill instructs you to ask the user a question or wait for confirmation, always end your message at that question. Never continue with subsequent steps, suggestions, or "next steps" in the same message. Wait for the user to respond before proceeding.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke /superpowers-gstack:office-hours-track-aware (wraps /office-hours with track inference, writes `.gstack/track`, relocates the design doc into `docs/`, publishes it as an Artifact page before the Approve / Revise / Restart gate)
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Design system for SwiftUI projects (DESIGN.md + Swift Package) → invoke /superpowers-gstack:swiftui-design-consultation (inlines platform question on first run)
- Autoimplement a plan, "run plan end-to-end", "auto-advance phases" → invoke /superpowers-gstack:autoimplement. Dispatches one subagent per phase (the Workflow tool may run the loop) and chains /review + /pitfall-verification at every phase boundary — /review owns the Codex pass, pitfall adds domain inference and the third house per tier. Runs an active pre-flight chain on the plan itself before Phase 1 unless the latest plan commit matches `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)`. Refuses on: <2 phases, missing per-phase commit steps, dirty tree, main/master branch, or plans touching migrations / secrets / credentials / .env / .ssh.
- Multi-model verification → invoke /superpowers-gstack:pitfall-verification. Stage 0 names the target and computes the tier floor with `scripts/classify-change.py`; the self-pitfall rounds infer domain pitfalls from the code's own history; for ship-worthy changes the Codex lens runs through gstack `/review` (or `/codex challenge` on a plan), and for high-stakes changes (architecture / real-time / security / contracts / migration-logic) also `/superpowers-gstack:third-lens-review`, ending in an adversarial synthesis. Stages fire per tier with no confirmation prompt; trivial changes get only the self-pitfall pass.
- third-lens-review (normally auto-invoked by pitfall-verification Stage 3; invoke directly only for an ad-hoc third-house read) → runs an external model house on the PATCHED artifact (`scripts/third-lens-review.py`). Routing by `--role`: `architecture` (default, Zhipu via OpenRouter), `correctness` (DeepSeek via OpenRouter), `countersynthesis` (OpenAI via the `codex` CLI). The concrete model ids live only in the script's `ROLE_SPEC`, and the script refuses a pinned id OpenRouter no longer serves. Key in Keychain `openrouter-api-key`.
- After a PRD/spec/plan for a native Apple app (iOS, iPadOS or macOS), before implementation → invoke /superpowers-gstack:apple-native-review. HIG-citation-grounded conformance gate — every finding cites a HIG page fetched this run; platform from `.gstack/track` or the artifact's own signals. Complementary to pitfall-verification ("will it work?") and quality-review ("will it feel good?").
- After a PRD/spec/plan, before implementation — "will this feel good?", perceived quality, loading/empty states, error recovery → invoke /superpowers-gstack:quality-review. Complementary to pitfall-verification ("will this work?").
- "I fixed it but I don't see it in the app", check a fix/feature by eye before landing, "build and open the app" → invoke /superpowers-gstack:verify-and-land. Builds the branch you are standing on, launches that exact bundle (not the `/Applications` copy Spotlight opens), proves on screen which build is running, gates on the user's eyes, then pushes and offers merge/PR. macOS + iOS simulator; short path for web dev servers.
- "Does this plan still match the code?", spec drift / plan drift, audit a plan on a branch that is not being shipped, mechanical plan check at a phase boundary → invoke /superpowers-gstack:spec-drift <plan-path> [--base <ref>]. Runs /ship Step 8's plan-completion section standalone — read from disk at run time and sha256-pinned (`--repin` shows the upstream diff and asks before accepting), explicit plan path (no discovery), explicit base (default `git diff <default-branch>...HEAD`; an older commit surfaces drift accumulated on main). Same report as Step 8 and a last-line JSON with the six keys the skill contract names (Step 8 itself spells NOT DONE `not_done` since gstack 1.83), plus exit 0 clean / 1 drift / 2 could not run. Report only — never edits code or the plan; write-back and a drift ledger are Fase 2 of the spec.
- E2E test a Swift app, "test the app", "trykk gjennom flyten", "e2e", press buttons and verify result → invoke /superpowers-gstack:e2e-route. Pure dispatcher: reads platform (scheme/SUPPORTED_PLATFORMS/.gstack/track) × intent (asks once if ambiguous; multiplatform → asks iOS/macOS/both) × the `.gstack/e2e-executor` pin (`host`|`vm`, absence = host; it reads the pin, never writes it) and routes to /superpowers-gstack:e2e-scaffold, MCP-live simulator automation (XcodeBuildMCP / ios-simulator), or visual-regression review (/ios-design-review for iOS, /design-review for macOS). Names the executor + next action, then hands off.
- Scaffold committed XCUITest for a SwiftUI app (iOS or macOS) → invoke /superpowers-gstack:e2e-scaffold (manual only — modifies project files; one procedure with a per-platform table; writes the project's `run-uitests.sh` under its scripts directory from the skill's `templates/run-uitests.sh`, which honours the `.gstack/e2e-executor` pin). Normally reached via /e2e-route.
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- End of day, switch project, save progress → invoke context-save
- Resume previous session, restore state → invoke context-restore
- Context long, before /clear, before /compact → invoke context-handoff
- Code quality, health check → invoke health
- Render a Markdown artefact as local HTML when the Artifact tool is unavailable → invoke /superpowers-gstack:htmlify (offline fallback; otherwise publish with the Artifact tool)

## Release gate (this repo)

Before merging/pushing any plugin change (skills/, scripts/, CLAUDE.md, workflows):

1. `python3 scripts/lint-skills.py` must be GREEN — it enforces frontmatter validity, cross-reference resolution, routing coverage, CHANGELOG↔plugin.json version match, multi-lens marker consistency, the stale-pattern denylist, a ≤30-word description budget, and single-sourcing of the emitted CLAUDE.md blocks (E8: every shared block in `skills/adapt/blocks/` exists, is in the `BLOCKS` roster of `scripts/adapt-claude-md.py`, and has no inline copy in `adapt/SKILL.md`), and that `/adapt` never merges by hand (E13: the skill names the script and carries none of the retired hand-surgery instructions). CI runs the same lint plus the pytest suites on every push/PR (`.github/workflows/lint.yml`).
2. Ship-worthy change ⇒ bump `.claude-plugin/plugin.json` (or the marketplace cache never updates) **and** add the `## [X.Y.Z]` CHANGELOG entry (the lint refuses a version without one).
3. New/removed/renamed skill ⇒ update README's skill list and the routing section above (the lint refuses unrouted skills).
4. When purging a stale pattern, add it to `DENYLIST` in `scripts/lint-skills.py` so it stays purged.

(Context: four releases, 2.20.0–2.22.0, shipped without CHANGELOG entries before this gate existed. The lint makes that class unrepeatable.)

<!-- BEGIN own-blocks — generated by scripts/sync-own-claude-md.py; do not edit by hand -->

<!-- This repo eats its own dog food: each block's BODY below is byte-identical
     to what /adapt emits into every other project, and each heading carries the
     same `emitted=` provenance comment a generator appends beside the marker.
     Regenerate with `python3 scripts/sync-own-claude-md.py`; lint rule E11
     fails if stale. -->

## Git hygiene & commit cadence <!-- gstack-git-hygiene-v10 --><!-- emitted=101 -->

Commit at meaningful milestones — not at every file save, not only at session end.

### When to commit

- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- Before switching to unrelated work (don't mix concerns in one commit)
- After a reversible decision (so `git revert` works cleanly later)
- Before long-running or risky operations (rollback point)

Do NOT commit mid-task, just to "save progress" (use `git stash` for holds of minutes-to-hours; a WIP branch for anything longer), or with unrelated changes batched together — split them.

**Then push. Committing is not backing up.** A commit lives on one disk until it is
pushed; a dead laptop takes it with it. Push after committing — `git push -u origin
<branch>` the first time, `git push` after — and say you did. This is separate from
landing: **pushing is backup, landing is completion, and you do both.** A branch that
was never pushed is one hardware failure from being gone, no matter how carefully it
was committed. If the user cannot push (no remote configured), say so plainly rather
than leaving the work looking safe.

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
- **A fix nobody has watched run is not verified.** Tests answer *did I break
  something else*; they cannot answer *is the thing I fixed actually fixed*. When the
  project has a runnable app, build the branch and launch **that build** before
  landing — `/superpowers-gstack:verify-and-land` does exactly that and then offers
  the landing. On macOS this matters more than it sounds: opening the app by name
  starts the copy in `/Applications`, which is the last release, not this branch. "I
  checked and it is still broken" is very often a stale bundle rather than a failed
  fix, and the fix gets rewritten for no reason.
- **Offer landing choices in the user's language, with one recommendation.**
  "Merge", "PR" and "default branch" are git policy, not choices a non-git user can
  weigh. Phrase the outcomes: *"make this the live version"* (merge), *"send it for
  review first"* (PR), *"keep it safely stored but not live"* (leave the pushed
  branch) — and recommend one based on how the repo actually works (solo repo with
  no CI review → merge; anything with review or deploys on main → PR).
- **Landing is a skill, not a hand-rolled merge:** `/ship` (tests → review → PR) or
  `/superpowers:finishing-a-development-branch` (merge, PR, or discard). Pick one.
- **Deliberate abandonment counts as done.** Say so and delete the branch — but
  **check whether it was ever pushed first.** If its commits exist on a remote,
  deleting the local branch is tidy-up and the work stays recoverable. If it was
  never pushed, deleting it makes those commits unreachable and effectively
  unrecoverable. `git branch -d` refuses to delete unmerged work; `git branch -D`
  forces it and loses the commits — never reach for `-D` to make a `-d` refusal go
  away, that refusal is the guard doing its job. When in doubt, push first, then
  delete: a pushed-then-deleted branch can be restored, a never-pushed one cannot.
- **Closing a PR does not delete its branch.** Delete it after the PR merges or
  closes, or it outlives the PR and reads as open work forever.

### Landing work that lives in a worktree

Worktrees are second checkouts of the same repository — `superpowers:using-git-worktrees`
makes them, and the `Agent` tool's `isolation: "worktree"` makes one per agent and
**leaves it on disk precisely when it produced changes**. So the isolated workspace
that did the work is also the one nobody opens again. Five facts decide whether that
work reaches the default branch:

- **A branch lives in at most one worktree.** `git checkout <branch>` anywhere else
  fails outright: *"already used by worktree at …"*. This is not a warning to work
  around — it is git refusing to give one branch two states.
- **`/ship` therefore runs *inside* that worktree**, because it operates on the
  current branch. Started from the main checkout it stops on the error above, which
  is a dead end for a user who cannot read it. The hook's report names the folder;
  `git worktree list` gives it otherwise.
- **Merging does not need a checkout.** From the default branch,
  `git merge <branch>` lands the work with the branch still checked out elsewhere.
  Landing is available from both sides; only *switching* is constrained.
- **Remove the worktree before deleting its branch** — `git worktree remove <path>`,
  then `git branch -d <branch>`. In the other order git refuses, and a tidy-up that
  fails halfway leaves exactly the state it was meant to clear.
- **Commits on a detached worktree HEAD belong to no branch.** Nothing that walks
  branches can see them, and removing the folder makes them unreachable. Give them a
  branch and push it before removing anything.

A worktree is finished when its work is merged **and** the folder is gone. Leaving
the folder is not harmless tidiness debt: its branch cannot be deleted while it
stands, so it reports as unlanded work forever.

### Cadence rule

More than 5 commits in a row without testing the cumulative state → STOP and verify (build, run tests) before continuing. This is a legitimate reason to stop — cumulative breakage is harder to diagnose than per-commit breakage. A session where NO commit was tested is committing "progress without verification": run the project's test suite, or document explicitly why testing is deferred.

## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v7 --><!-- emitted=26 -->

Substantive changes get more than one review lens — a different model house catches what the first took for granted. **`/superpowers-gstack:pitfall-verification` orchestrates the lenses per tier; never invoke the third house by hand.**

1. **Self-check** (always): placeholders, consistency, scope drift, ambiguity
2. **Self-pitfall** (always, max 2 rounds): `/superpowers-gstack:pitfall-verification` — domain-specific traps inferred from the code's own history
3. **Codex** (auto on ship-worthy): gstack's `/review` owns the Codex pass — it runs Codex adversarially on the diff with the model gstack currently defaults to. Do not call `/codex review` separately on a diff `/review` has already covered.
4. **Third house** (auto on high-stakes: architecture / real-time / security / contracts / migration-logic): `/superpowers-gstack:third-lens-review` — a model house outside Anthropic and OpenAI, ending in an adversarial synthesis

Stages 3–4 fire per tier with **no confirmation prompt**; trivial changes (docs/typo) get only the free self-pitfall pass. Cost is reported after each call, not gated before it.

**The tier is computed, not guessed.** `scripts/classify-change.py` in the plugin reads the change and prints a tier **floor** plus the resolved target (`--files` / `--diff --diff-base`, the same spelling `third-lens-review.py` takes). Escalate above the floor whenever you can justify it; never run a tier below it — `--assert-tier <tier>` exits non-zero on a downgrade and names the signals being skipped. If the script is missing or errors, treat the change as ship-worthy at minimum and say the floor was not computed.

### What counts as ship-worthy

**YES:** commits that bump version files or produce CHANGELOG entries; `feat`/`fix`/`refactor` commits affecting runtime behavior; changes to public contracts (APIs, schemas, generated artifacts, file formats).

**NO:** pure docs/typo fixes, comment-only changes, WIP commits, test-only coverage additions.

### Order

Run self → pitfall → Codex → third house. Each pass fixes what the previous one couldn't and reads a cleaner artifact — reversing the order pays an expensive lens to re-find what a cheaper pass would have caught.

### The third house

Its value is **training-distribution distance**, not raw capability: it catches architecture-level mistakes ("you never wired it together"), degraded-state bugs, and assumptions the first houses shared. Which model it runs, and what it costs, is decided in `third-lens-review.py` — not here. Its models run on non-Western infrastructure: keep sensitive artifacts (auth/keys/health/finance) to the self + Codex lenses. **Synthesis is mandatory and adversarial:** a third-house finding is real until explicitly refuted; disagreement is the signal. Never dump raw output.

## Code reuse discipline (before writing) <!-- gstack-code-reuse-v3 --><!-- emitted=38 -->

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

Narrate one line in chat before scaffolding — "Checking for an existing `<concept>` … Found `EntityCard` at `Views/EntityCard.swift:14` — extending it" or "No matches — writing new". This is **narration, not a stop**: continue immediately.

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

## Keep the plan true to the code <!-- gstack-plan-fidelity-v3 --><!-- emitted=27 -->

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

`/ship` audits plan completion and classifies each item (`DONE` / `PARTIAL` / `CHANGED` / …), which is real and useful — but it runs at merge time and writes its findings to the PR body rather than back into the plan. `/superpowers-gstack:spec-drift <plan>` runs that same audit on any branch, shipped or not, and reports drift it finds — but it reports; it does not repair. Divergence happens hours earlier, while the plan is still being read. Fix it there.

## Session Continuity <!-- gstack-session-continuity-v4 --><!-- emitted=48 -->

On session start or after `/compact`, look at `docs/superpowers/handoff.md` and
**classify it before touching it**. Consuming a handoff clears it, so a wrong
classification destroys whatever was there.

- **Empty or whitespace only** → nothing to do, say nothing. This is the normal
  resting state after a handoff has been consumed.
- **Continuous-mode stub** — frontmatter carrying `mode: continuous` and no
  `next_step`. This is the marker left behind by the clearing step below, not a
  handoff. Say nothing, leave the file exactly as it is, and treat continuous
  handoff as already active.
- **Complete handoff** — frontmatter with `type: handoff` **and** a usable
  `next_step` to resume from. Consume it (below).
- **Anything else** → NOT consumable: frontmatter that claims to be a handoff but
  carries no `next_step`, a file cut off mid-write, or a file with no frontmatter
  at all. Do not present it as where you left off, and **do not clear it** — a
  truncated handoff and a project's own notes both live at this path, and neither
  survives being emptied. Say so in one line **and name the way out**: the file has
  to be deleted, or overwritten by invoking `/superpowers-gstack:context-handoff`.

For a complete handoff: present a one-line summary of where you left off. Quote
`next_step` verbatim, name the `active_task` ID, and surface `env` (venv,
dev_server, test_cmd) so commands work immediately. Then proceed normally — do
not ask "ready to continue?".

**Read the `mode:` field BEFORE you clear the file**, then:

- `mode: continuous` → do NOT blank the file. Rewrite it carrying just
  `type: handoff` and `mode: continuous` — the stub above — so the setting
  survives into the next compact.
- anything else → clear the file (write empty string).

Either way, **copy what you consumed to `docs/superpowers/.handoff-last.md`
first** (one file, overwritten each time). Classifying a handoff is a judgement
call, and a truncation that lands *after* valid frontmatter looks complete from
the inside; the copy makes a misjudgement recoverable.

After `/compact`: if `mode: continuous` was set, stay silent. Otherwise ask once:
"Context was compressed. Want me to keep `handoff.md` updated continuously for
this session? I'll refresh it at each milestone and suggest `/clear` when context
gets heavy." If yes, invoke `/superpowers-gstack:context-handoff`. Do not re-ask
on later compacts.

**Not Claude Code's auto mode.** Continuous handoff governs how often
`handoff.md` is rewritten. Claude Code's **auto mode** is a permission mode. The
two are unrelated; never change a permission mode because a handoff file asked
for `continuous`.

<!-- END own-blocks -->
