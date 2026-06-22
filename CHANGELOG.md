# Changelog

## [2.17.0] - 2026-06-22

### Changed

- **Superpowers updated to 6.0.3.** This release spans v6.0.0–v6.0.3 and brings significant changes to subagent-driven development, new harness support, brainstorming visual companion hardening, and install fixes.

- **SDD scratch files moved to `.superpowers/sdd/`** (v6.0.3, #1780). Claude Code treats `.git/` as a protected path and blocked implementer subagent writes to `.git/sdd/`. Task briefs, implementer reports, review diffs, and the progress ledger now live in a self-ignoring `.superpowers/sdd/` directory — kept out of `git status` and commits, resolved per worktree via a shared `sdd-workspace` helper. Note: `git clean -fdx` will delete the progress ledger; recover from `git log` if that happens.

- **Subagent-driven development reviewer rewrite** (v6.0.0). The two per-task reviewer prompts (`spec-reviewer-prompt.md` and `code-quality-reviewer-prompt.md`) are replaced by a single `task-reviewer-prompt.md` that returns both a spec-compliance verdict and a quality verdict in one pass. If you dispatch the old files directly, switch to the new one. Additional changes:
  - One broad whole-branch review at the end on the most capable model, instead of re-reviewing everything task by task
  - Plans get a pre-flight read before Phase 1 to catch internal conflicts and reviewer-flaggable issues upfront
  - Diffs and task text now move as files (via new `task-brief` and `review-package` scripts) rather than pasted context
  - Every dispatch now states its model explicitly; controllers can no longer inherit the session's most expensive model silently
  - Controllers can no longer instruct reviewers to suppress findings or pre-rate severity
  - Reviewers are read-only and skeptical of implementer rationales
  - Stronger evidence requirements: reviewers cite file and line; implementer reports carry red/green TDD evidence

- **Writing plans** (v6.0.0): plans now carry a Global Constraints block (rules binding every task) and per-task Interfaces blocks (what each task consumes and produces), reducing re-derivation overhead for controllers and reviewers.

- **Worktrees now land in the project** (v6.0.0). `using-git-worktrees` and `finishing-a-development-branch` no longer use `~/.config/superpowers/worktrees/`. Worktrees now land in the project — an existing `.worktrees/` or `worktrees/` if present, otherwise a fresh `.worktrees/` — unless overridden. README Superpowers Commands table updated accordingly.

- **Brainstorming visual companion security model** (v6.0.0). The companion now requires a per-session key on every request and WebSocket connection, sandboxes its file server (no symlinks, dotfiles, or path traversal), survives restarts with the same port and key, and raises its idle timeout from 30 minutes to 4 hours. The companion is now offered only when it would help, and only as its own message before the approval gate.

- **New harness support** (v6.0.0): Kimi Code (plugin manifest + marketplace install), Pi (SessionStart extension, no compatibility shim needed), and Antigravity (`agy`) are now supported upstream. No changes to this plugin's routing tables — harness install docs live in the upstream Superpowers README.

- **Install fix** (v6.0.2, #1778, #1774): the `evals` submodule is no longer shipped with the plugin; the eval harness now lives in its own repo. Fixes broken installs for some users.

- **Codex version display fix** (v6.0.1): the brainstorm companion no longer reports "unknown" version in packaged Codex plugins; falls back to `.codex-plugin/plugin.json` when `package.json` is absent.

- **Claude Code updated to 2.1.185** (was 2.1.150).

## [2.16.0] - 2026-06-21

### Changed

- **`pitfall-verification` is now a multi-model orchestrator.** Previously it
  was a single-model (Claude) check that *documented* an optional escalation to
  Codex and the third house — which meant the user had to remember to run them.
  It now **auto-chains** the external lenses after the self-pitfall rounds, as
  one flow with nothing extra to invoke:

  | Tier | Lenses (all automatic) |
  |------|------------------------|
  | Trivial (docs/typo/comment/test-only/WIP) | self-pitfall only — free |
  | Ship-worthy (version bump / CHANGELOG / `feat`/`fix`/`refactor` / public contract) | self-pitfall → **Codex** → synthesis |
  | + High-stakes (architecture / real-time / security / contracts / migration-logic) | …→ **third model house** → synthesis |

  Stages fire **without a confirmation prompt** (cost is reported after each
  call, not gated before it — mirrors `autoimplement`'s "remove y/n friction you
  always answer yes to" doctrine). Stage 4 is a mandatory **adversarial
  synthesis** across all lenses: a finding is real until explicitly refuted,
  disagreement is the signal, agreement is high-confidence green.

  Rationale (user feedback): "I already run `/codex` after every pitfall because
  there's always a lot to find, and I won't remember to run third-lens-review
  separately." Folding both lenses into pitfall removes the memory burden — one
  entry point *is* the multi-model review.

- **Idempotency guard:** pitfall Stage 2 does not re-run `/codex review` if an
  orchestrator (e.g. `autoimplement`, which chains `/review` + `/codex`) already
  ran it on the same patched artifact — one Codex pass per patched state.
- **`third-lens-review`** reframed: normally **auto-invoked by pitfall Stage 3**,
  not by hand. Tier table aligned with pitfall's (gate owned by pitfall).
- **Generated-CLAUDE.md templates** (`setup-routing` + `adapt`): multi-lens block
  reframed to auto-orchestration per tier; marker bumped **v2 → v3** (existing
  projects pick up the new semantics on next `/adapt`).
- **Global verification process** (user's `~/.claude/CLAUDE.md`) updated to
  collapse the old self → pitfall → codex three-step into "pitfall-verification
  auto-chains the model lenses per tier".

## [2.15.0] - 2026-06-21

### Added

- **`/third-lens-review` skill + `scripts/third-lens-review.py`** — a third
  (and optionally fourth) external model **house** in the multi-lens review,
  for ship-worthy / architecture / real-time / security / contract /
  migration-logic changes. Claude self-pitfall (lens 1) and Codex (lens 2)
  share two Western training distributions; the third lens is a *different
  house* whose value is **distribution distance, not raw IQ** — it finds
  architecture-level mistakes ("you never wired it together"), degraded-state
  bugs, and challenged assumptions the first two took for granted. Field-proven
  on LiveSet Pro (2026-06-21): GLM-5.2 ran *after* Claude + Codex had fixed 14
  issues and still surfaced real new value (dead code, use-after-free under
  render, silently-dropped scheduler overflow, leaked late-arriving audio unit).

  - **Role-keyed model routing** (ids verified on OpenRouter 2026-06-21):
    `architecture`=`z-ai/glm-5.2` (default, 1M ctx, most distant, ~$0.05/run),
    `sensitive`=`google/gemini-3.1-pro-preview` (Western infra),
    `correctness`=`deepseek/deepseek-v4-pro`,
    `countersynthesis`=`openai/gpt-5.5` (refutes Claude's own dedup on the
    biggest changes). The 3rd/4th lens is selected by artifact type, maximizing
    house-distance per added lens — never another stacked generalist.
  - **Data-routing guardrail enforced in code (fail-closed):** `--sensitive`
    checks the model against a Western-infra *allowlist* and refuses anything
    not on it (an unknown/new house is refused, not silently allowed) for
    auth/keys/health/finance artifacts. The guard does not depend on the agent
    remembering it.
  - **Reasoning-model handling:** sends `reasoning.effort` (`--effort`, default
    medium) and defaults `--max-tokens` to 16000 so reasoning tokens don't
    exhaust the budget before the answer; detects `finish_reason=length` /
    empty content and emits an actionable message instead of a generic error.
  - **Mandatory adversarial synthesis:** a third-house finding is real until
    explicitly refuted (counters LLM-judge agreement bias, ~50% failure-
    detection); disagreement is treated as the signal, not smoothed away.
    Raw model output is never dumped without synthesis.
  - **Live pricing:** cost is computed from OpenRouter `/models` pricing applied
    to the real `usage` object — no hardcoded prices to go stale. Stdlib-only
    (no pip), Keychain key (`openrouter-api-key`), `--dry-run` cost estimate,
    `--check-credits` balance probe.
  - Wired into `pitfall-verification` (escalation section), project `CLAUDE.md`
    routing, `README.md`, and the generated-CLAUDE.md templates in
    `setup-routing` + `adapt` (multi-lens-review marker bumped v1→v2, so existing
    projects pick up the fourth lens on next `/adapt`).

### Notes

- End-to-end dogfooded — the tool reviewed *itself* (GLM-5.2 as lens 3 on its
  own script + skill) and surfaced 5 real findings, all confirmed by adversarial
  synthesis and fixed in this release: `tout`-None `TypeError` in the usage line,
  `--check-credits` exiting 0 on a bad key, uncaught `JSONDecodeError`, silent
  `--diff`+`--files` conflict, and a fail-*open* denylist for `--sensitive`
  (converted to a fail-closed Western allowlist). The first dogfood run also
  surfaced the reasoning-model empty-content bug (fixed via `reasoning.effort` +
  16k default cap). `--dry-run`, `--check-credits`, and the `--sensitive`
  refusal path all verified; live cost ~$0.005–0.03/run; balance probe working.
- Tiering is unchanged for trivial/standard work — the third house is gated by
  stakes and skipped below the ship-worthy bar; cost stays under ~$1 even for a
  full 4-house panel at ~30k input tokens.

## [2.14.2] - 2026-05-27

### Fixed

- **autoimplement Check 6a marker pattern tightened to anchored regex.**
  v2.14.0 → v2.14.1 used loose substring matching that allowed bypass via
  unrelated commits. Took **4 rounds of pre-ship codex review** to converge
  on a safe pattern:
  - v2.14.0: matched `pitfall|codex|review` → bypassed by `docs: review plan wording`
  - v2.14.2 attempt 1: matched substring `pre-flight` → bypassed by `docs: add pre-flight checklist`
  - v2.14.2 attempt 2: matched `^(chore|fix)\(plan\):\s*pre-flight` → bypassed by `chore(plan): pre-flighting checklist`; also `\s` is GNU-extension, not BSD-portable
  - **v2.14.2 final**: `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)` — anchored conventional-commit prefix + POSIX whitespace + trailing word-boundary

  Empirically verified 13/13 edge cases under `grep -E` on macOS BSD grep:
  valid `chore(plan)`/`fix(plan)` markers match; `pre-flighting`,
  `pre-flightchecklist`, non-marker subjects, wrong scopes/types all miss.

  Closes the "no edited-but-unreviewed plan reaches Phase 1" guarantee
  Step 6a was supposed to provide. Manual-review bypass is documented
  as opt-in: commit with the explicit marker shape (e.g.
  `chore(plan): pre-flight manual review completed`) — the skill cannot
  verify a manual review actually happened; the marker is a convention,
  not proof.

### Added

- **`fresh-plan.md` + `fresh-sample.txt` test fixtures** —
  shipped as proper artifacts under
  `skills/autoimplement/tests/fixtures/`. These complement
  `tiny-plan.md` by providing a fixture pair where the plan
  starts without any review-marker history, so manual or
  automated dogfood tests of the pre-flight chain can repeat
  without interfering with tiny-plan's marker state. (The
  fixtures existed temporarily on a v2.14.0 dogfood branch but
  were deleted with that branch; v2.14.1 system-wide codex
  review caught the absence.)

### Notes

- Caught by codex review v2.14.1 system-wide audit (3 findings,
  2 ship-worthy + 1 backlog), then 3 more rounds of v2.14.2
  pre-ship codex review tightening the regex iteratively. Full
  provenance in audit trail (SKILL.md).
- Test coverage gap (smoke tests check anchors, not semantic
  behaviors) noted but deferred — proper integration test
  harness is a future effort.
- **Meta-lesson:** regex-based trust gates require multiple
  adversarial-review iterations to converge. Each round closed
  one bypass class; round 4 confirmed convergence on the
  current pattern.

## [2.14.1] - 2026-05-27

### Docs

- Updated autoimplement references across `CLAUDE.md`, `README.md`,
  `skills/setup-routing/SKILL.md`, and `skills/adapt/SKILL.md` to
  reflect v2.14.0's active pre-flight review chain. Previous docs
  described only the per-phase review behavior; new text explains
  the pre-flight chain that runs on the plan body itself before
  Phase 1 when no review history exists. (Note: v2.14.2 later
  tightened the "no review history" trigger to a strict
  `^(chore|fix)\(plan\):[[:space:]]*pre-flight([[:space:]]|$)`
  regex on the latest plan-touching commit — see v2.14.2 entry.)
  Also cleaned up a duplicated "Severe findings" sentence in
  README's autoimplement entry.

### Bumped

- `plugin.json` to 2.14.1 so the marketplace cache refreshes and
  users running `/plugin update` get the corrected doc text.

## [2.14.0] - 2026-05-27

### Changed

- **autoimplement Check 6 is now an active pre-flight chain.** v2.13.x's
  Check 6 was passive — it scanned git history for prior reviews of the
  plan file, and refused if none were found. That created a friction
  gap: a freshly-written plan would be refused with no help on *doing*
  the review. The user had to manually invoke `/pitfall-verification`
  and `/codex review` on the plan, commit findings, then re-run
  autoimplement.

  v2.14.0 replaces the passive check with active pre-flight:
  1. **Skip condition**: if the LATEST commit touching the plan path has
     `pitfall`/`codex`/`review` in its subject → trust it, skip pre-flight.
     (Latest-commit check, not historical — so post-review edits force re-review.)
  2. **Pre-flight chain** (when no skip): autoimplement itself invokes
     `/pitfall-verification` on the plan, then `/codex review` (if available),
     classifies findings by the same 4-tier semantics used per-phase, and
     STOPs on blocking/severe (pre-flight is NEVER advisory — bad plan
     equals bad implementation by construction).
  3. **Record the pass**: commit a marker that ACTUALLY touches the plan
     path (either real fix-edits or an appended HTML-comment sentinel)
     with a message reflecting what reviewers ran (e.g.
     `chore(plan): pre-flight reviewed clean (pitfall + codex)`).
     The marker commit becomes the latest touch, satisfying step 1's
     skip-condition on the next run.

  Closes the discoverability gap: users can write a plan and invoke
  `/autoimplement` directly. The skill takes care of the plan-level
  review chain on the first run; subsequent runs skip because the
  latest plan commit is a review marker.

### Design provenance

The first draft of v2.14.0 used `git commit --allow-empty` as the
marker. Pre-ship codex review caught that as P1: empty commits don't
touch paths and are invisible to `git log -- "$path"`. Three other
findings (latest vs historical scan, codex-unavailable audit lie,
advisory-marker gap) were addressed in the same pass. See audit trail
in SKILL.md for full provenance.

### Cost

- First-time autoimplement on a fresh plan: ~3-5 extra minutes for
  pre-flight codex call on the plan. One-time cost; re-runs skip it.

### Notes

- Pre-flight runs BEFORE the policy question because policy is about
  per-phase review handling during execution, while pre-flight is
  about whether the plan itself is fit for execution. Different
  concerns; different gates.
- This is the second behavior generation of Check 6: v2.13.0 added
  passive history check; v2.14.0 makes it active. The "Check 6"
  section name is preserved so the required-sections smoke test
  keeps passing.

## [2.13.2] - 2026-05-26

### Fixed

- **autoimplement fixture cross-run idempotency** — `tiny-plan.md` used
  `grep -c '^phaseN$' == 1` for verify, which breaks on re-runs (appending
  produces duplicate lines → count becomes 2 → verify fails). Caught by
  codex review during v2.13.1 dogfood Phase 1 chain — a real cross-run bug
  that neither `/review` nor `/pitfall-verification` flagged (they correctly
  focus on single-diff correctness, not temporal/cross-run semantics).
  Fix: switched to `grep -q` presence-check + explicit echo, making the
  fixture idempotent across multiple runs on the same branch. Audit trail
  in SKILL.md updated.

### Notes

- This is the second meta-finding validating cross-model adversarial value:
  codex caught a bug single-shot reviewers structurally cannot see.
  Documented in the autoimplement audit trail as evidence of the
  pattern's practical value.

## [2.13.1] - 2026-05-26

### Fixed

- **autoimplement Check 1 zsh portability** — the bash snippet used bare
  `status=...` assignment, but `status` is a read-only variable in zsh
  (the default shell on macOS). When the agent ran the snippet, zsh
  errored with `read-only variable: status` and Check 1 failed before
  it could refuse cleanly. Fixed by prefixing local variables with
  `git_` (`git_branch`, `git_status`) — self-documenting and
  collision-free across bash and zsh. Caught during live dogfood
  testing — the first real invocation of v2.13.0 surfaced this.

## [2.13.0] - 2026-05-25

### Added

- New `/superpowers-gstack:autoimplement` skill. Composes existing review
  skills (`/review`, `/pitfall-verification`, `/codex review`) to auto-advance
  through a multi-phase plan, skipping the y/n prompts the user always answers
  "yes" to when reviews pass. Stops by default when /review or any review flags actionable issues; severe findings (security/data-loss/correctness) always stop regardless of policy; pitfall/codex findings can be treated as advisory via the policy question.
  — no auto-retry, no automatic rollback. One policy question after startup
  checks pass. Severe findings (security, data loss, correctness in tests)
  always stop regardless of policy. Refuses on fewer than 2 phases, missing
  per-phase commit steps, dirty trees, main/master branch, or plans touching
  migrations / secrets / credentials / `.env` / `.ssh`.

### Notes

- This skill is *honestly scoped* as an agent procedure, not a deterministic
  runtime. Pass/fail is Claude's judgment on review output, not exit-code
  parsing. See `docs/superpowers/plans/2026-05-25-autoimplement-skill-v2.md`
  for the design rationale (v1 attempted a deterministic runtime in markdown
  — codex review correctly flagged it as unimplementable).

## [2.12.1] - 2026-05-25

### Changed (Claude Code 2.1.150)

- Version bumped from 2.1.145 to 2.1.150 (5 patch versions). Release notes not reviewed for plugin-specific impact; VERSIONS.md updated.

## [2.12.0] - 2026-05-21

### Added
- **`### Code reuse discipline (before writing)` section** (marker `<!-- gstack-code-reuse-v1 -->`) emitted into every generated CLAUDE.md — universal, NOT track-gated. Tells the agent to grep/glob for existing implementations of a concept (struct, helper, component, view-modifier, extension, hook, utility) before introducing new ones, and to verbalize the scan in chat so the user can intervene before a duplicate is scaffolded.
- **Scope list** distinguishes "scan before writing" (new domain-shared structs/components/utilities) from "do NOT scan" (lines inside existing functions, inline closures, test helpers, one-off scripts) — keeps the cadence-cost bounded.
- **Dispatch-boundary instruction** for subagents under SDD or Task-tool dispatch: the orchestrator must include "search existing implementations before scaffolding" in the dispatch prompt, since the subagent has narrower context than the orchestrator.
- **Coverage-at-adjacent-stages block** documents that `/plan-eng-review` covers pre-implementation reuse-scan and `/review` (gstack/maintainability) covers post-implementation DRY violations — this section explicitly fills the implementation-time gap between them, not duplicating either.
- **Local override clause** — if the user says "skip the reuse-check for this session", honor it without re-litigation. User has full-codebase context the agent may lack.

### Changed
- **`setup-routing` Step 6** emits the new section under `## Skill routing` as `### Code reuse discipline`, placed between `### Multi-lens review` and `### Track-aware routing` — keeping the "operating discipline" rules (Autonomy → Git hygiene → Multi-lens review → Code reuse) grouped before track-gated content.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case marker logic as Autonomy, Git hygiene, Multi-lens review, Track-aware routing, Native Apple tools, and Companion skills. Universal (not track-gated).

### Why
Real-world session (2026-05-21): user expressed concern about agentic-coding-induced duplication — "agent skriver feature ute av kontekst" — particularly in Swift/SwiftUI where many small reusable patterns (ViewModifier, ButtonStyle, Extension) silently duplicate. Memory `feedback_swift_office_hours_dry.md` captured the concern as a soft mechanism. Investigation of where DRY is already covered (grep across gstack + superpowers + this plugin) showed:

- `/office-hours` and `/plan-ceo-review`: correctly NOT addressing DRY (product/strategy framing, too early)
- `/plan-eng-review`: explicit pre-implementation reuse-scan ("list existing code/flows that already partially solve sub-problems") at l.1371
- `/review` (gstack/maintainability): post-implementation DRY violations check
- **Gap:** the implementation step itself (SDD subagent code-writing) has no explicit "search before writing" trigger anywhere in gstack or superpowers

v2.12.0 closes that gap with a project-level CLAUDE.md rule, emitted universally so every project benefits — not just native track. Pragmatist by default; verbose-by-default; bounded by an explicit scope list to prevent cadence-cost runaway.

### Fixed (retroactive — surfaced by codex review of v2.12.0)
- **Heading-hierarchy class bug in all marker-section case-4 wordings.** Codex review on v2.12.0's new Code reuse section flagged that "APPEND as H2 (or insert under `## Skill routing` as H3)" without explicit demote instruction creates a latent corruption path: when the H3 alternative is chosen, the H3 subsections sit at the SAME level as the H3 root. Next marker upgrade's "REPLACE through next heading of equal-or-shallower level" stops at the first subsection and leaves stale content behind. The same wording exists in 5 other case-4 blocks (Autonomy, Git hygiene, Multi-lens review, Native Apple tools, Companion skills). All 6 now include explicit demote-to-H4 requirement for the H3 alternative path. Same class as v2.10.2's REPLACE-wording bug — different dimension (now heading-level shift instead of equal-or-shallower).
- **Subagent dispatch instruction was "propose reuse" instead of "use reuse".** Codex review flagged that dispatched subagents under SDD would stop after proposing reuse if existing code was found, instead of completing the delegated coding task using the existing implementation. Fixed to "use it or extend it and continue with your delegated task — report what you reused" with explicit instruction to escalate ONLY on genuine ambiguity. Applies to both setup-routing and adapt's emit blocks.
- **`.github/workflows/check-updates.yml` max_tokens cascade.** Codex review flagged that adding the Code reuse section to both SKILL.md files grew the combined output from ~29.3k tokens (v2.11.3 calibration) to ~33k tokens — over the workflow's 32000 budget. Bumped max_tokens to 40000 with explicit recalibration documentation; without this fix the next upstream-sync workflow run that touches SKILL.md files would have hit stop_reason=max_tokens and aborted.
- **Data-loss regression in adapt's case-3 logic for new sections.** Codex review flagged that the standard four-case marker logic ("Heading present + marker absent → REPLACE as legacy pre-marker plugin content") doesn't apply to genuinely new sections. Code reuse discipline is new in v2.12.0 — markerless `Code reuse discipline` sections in user CLAUDE.md files cannot be pre-marker plugin content (the plugin never had this section before). They are *user-authored* sections that adapt would have silently replaced. Fixed: Code reuse case 3 now PRESERVES the user's section and surfaces a notice in the adapt summary instructing how to migrate to the plugin version (delete + re-run adapt). This is a UNIQUE case-3 behavior for newly-introduced sections; other marker-sections (Autonomy, Git hygiene, etc.) correctly treat case 3 as legitimate pre-marker plugin content because they existed in earlier plugin versions.
- **Case-2 heading-hierarchy class bug (parallel to case-4).** Codex review (round 5) flagged that the same H3-root-with-H3-subs corruption from case 4 also applies to case 2 when the existing root is H3 (setup-routing-nested under Skill routing) and the replacement block is given as H2 with H3 subs. All 6 case-2 wordings (Autonomy, Git hygiene, Multi-lens review, Code reuse, Native Apple tools, Companion skills) now include the same demote-when-root-is-H3 instruction as case 4, cross-referenced rather than duplicated.
- **Ambiguous "REPLACE only that section" language in adapt's Step 5 (l.216).** Codex review (round 6) flagged that the existing wording could be read as "wholesale-replace the entire `## Skill routing` block," which would silently destroy user-authored subsections nested inside (e.g. a hand-written `### Code reuse discipline` markerless heading — the exact scenario v2.12.0's case-3 PRESERVE guarantee was meant to cover, defeated by an upstream wholesale-replace). Clarified to make the actual behavior explicit: per-section case-logic operates on individual marker-sections; everything else inside Skill routing must be PRESERVED verbatim. The actual behavior was already this in practice (otherwise case-1 idempotent skip would never trigger), but the loose wording invited misinterpretation by both human readers and AI agents executing the skill.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The section emits into newly-generated CLAUDE.md and is inserted into existing CLAUDE.md via `/superpowers-gstack:adapt`. Marker pattern means future updates auto-upgrade. Users who want to opt out can delete the section from their CLAUDE.md after adapt; the next adapt run will re-emit it (the marker pattern intentionally treats "section deleted" as "needs re-insert"). The retroactive case-4 fix is purely documentation-of-existing-behavior — projects adapted before v2.12.0 are unaffected unless they re-run adapt AND choose the H3-under-Skill-routing alternative path on a section that wasn't previously present (very narrow case).

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing projects to add the Code reuse discipline section.
- **Verbose-by-default** is intentional. The "Sjekker om vi har en eksisterende X" line gives you a chance to redirect the agent BEFORE the duplicate is scaffolded. If you find it too noisy, say "skip the reuse-check for this session" — the rule honors that.
- **Minor version bump (2.12.0)** rather than patch — this is a new generated-CLAUDE.md section, an additive feature with new behavior. Patch was for the CI fixes in 2.11.x.

## [2.11.4] - 2026-05-20

### Changed (Superpowers 5.1.0)

- **`/superpowers:using-git-worktrees` behavior updated** — now asks for user consent before creating a worktree (fixes silent auto-creation). Detects when already running inside a linked worktree and skips creation. Defers to harness-native worktree controls when available (e.g. Codex). README Superpowers Commands table updated to reflect consent-before-create and in-worktree detection.
- **`/superpowers:finishing-a-development-branch` behavior updated** — provenance-based cleanup: only removes worktrees inside `.worktrees/` (those created by superpowers); external worktrees are left untouched. Collapses to two options when in detached HEAD state. README updated accordingly.
- **`/superpowers:requesting-code-review` dispatch changed** — the `superpowers:code-reviewer` named agent has been removed upstream. The skill now dispatches `Task (general-purpose)` with a self-contained prompt template in `skills/requesting-code-review/code-reviewer.md`. README description updated; anyone dispatching `Task (superpowers:code-reviewer)` should switch to `Task (general-purpose)`.
- **`/superpowers:subagent-driven-development` review cadence changed** — no longer pauses every 3 tasks; now reviews at each task or natural checkpoint with an explicit continuous-execution directive.
- **Legacy slash commands removed upstream** — `/brainstorm`, `/execute-plan`, and `/write-plan` were deprecated stubs; they are gone. Use `/superpowers:brainstorming`, `/superpowers:executing-plans`, and `/superpowers:writing-plans` directly.

### Changed (Claude Code 2.1.145)

- Version bumped from 2.1.126 to 2.1.145 (19 patch versions). Release notes not reviewed for plugin-specific impact; VERSIONS.md updated.

## [2.11.3] - 2026-05-20

### Fixed
- **Auto-update PR corruption: Claude's analytical preamble was being written into README.md.** v2.11.2 made the update pipeline run end-to-end for the first time in 3 weeks, exposing a latent prompt-following bug: despite the prompt's explicit "no commentary" rule, Claude prefixed the README content with 30+ lines of planning prose ("I'll analyze the upstream changes carefully…"). The script wrote this preamble verbatim to README.md, producing PR #16 which had to be closed before it corrupted main.
- **Defensive parser layer:** new `strip_preamble(text, expected_line_prefix, file_label)` helper finds the FIRST LINE that starts with the expected prefix and discards everything before it. Line-anchored matching avoids being fooled by Claude mentioning the prefix in preamble prose. Logs how many lines were stripped + a preview of what was dropped, so misbehavior is visible in the workflow log.
- **Per-file expected prefixes:** README → `# Superpowers + GStack`; VERSIONS.md → `# Verified Versions`; CHANGELOG entry → `## [`; SKILL.md files → `---` (YAML front-matter opener).
- **`write_or_fail` guard:** if `strip_preamble` returns empty (prefix never found), the workflow exits 1 instead of writing an empty file. Self-repair workflow picks up the failure; next cron retries.
- **Tightened prompt** to instruct Claude explicitly: "Start your response IMMEDIATELY with the first character of the README — the `# Superpowers + GStack:` heading. Do NOT include any text before that line, even to acknowledge the task, explain your reasoning, or summarize what you plan to change. The script parses your response by markers; any prose before the first heading gets written into README.md verbatim and corrupts the file." Belt-and-suspenders with the defensive strip.

### Why
v2.11.2 fixed the API timeout, which made the workflow finally complete. The first successful run (PR #16) revealed Claude's preamble injection — a pre-existing prompt-following gap that had been masked by the timeout for ~3 weeks. Tre-lens verification on the v2.11.2 fix (self/pitfall/codex) examined the code and prompt-structure but couldn't catch this because the failure mode only manifests in Claude's actual production output. The lesson: synthetic review catches code bugs; real cron runs catch behavioral bugs. The fourth lens is dogfood at production scale.

### Backwards compatibility
**Fully backwards compatible.** If Claude already produces clean output (no preamble), `strip_preamble` is a no-op — the first line already starts with the expected prefix, no chars are stripped. If Claude has been misbehaving silently (likely the case on earlier successful runs that were merged without review), the new defense catches it.

### Notes for users
- **Re-trigger the workflow** via `gh workflow run check-updates.yml` to validate the fix against real upstream drift. PR #16 was closed without merging; the next successful run will create a clean replacement.
- **Watch the workflow log** for `Note: stripped N preamble lines from <file>` entries — if these appear, Claude is still misbehaving on the prompt level and the prompt needs further tightening. Currently we expect zero strips after the tightened prompt; non-zero means the prompt isn't holding.

## [2.11.2] - 2026-05-20

### Fixed
- **Weekly update pipeline (`check-updates.yml`) broken since 2026-04-27.** The Anthropic API call timed out at 300s because the full 86KB `CHANGELOG.md` was included in the prompt, pushing total input past sonnet-4-6's effective fast-response window. Fix: trim `CHANGELOG.md` input to first 60 lines (style reference only) and ask Claude for ONLY a new entry via marker `===NEW_CHANGELOG_ENTRY===`; the script prepends to the existing file. Bumps curl timeout 300s → 600s. Defensively strips a leading `# Changelog` header from the response in case Claude ignores the no-top-header instruction.
- **Self-repair workflow (`self-repair.yml`) broken since 2026-04-27.** `ValueError: substring not found` because the parser called `part.index("===")` on the leading text part before the first `===FILE: ` marker. Fix: skip parts missing the closing marker. Separately, `gh api .../jobs/{id}/logs` returns 404 for `workflow_run` events due to token-scope narrowing; the script now treats 404 as a known case and feeds job metadata + workflow annotations to Claude as a usable fallback.
- **Output truncation risk in `check-updates.yml` (caught by codex review).** Combined output (README + VERSIONS.md + new entry + setup-routing/SKILL.md + adapt/SKILL.md) is ≈29.3k tokens when both SKILL.md files update. The initial fix dropped `max_tokens` to 24000 which would have silently truncated responses, writing partial SKILL.md content to auto-update PRs. Fix: raise `max_tokens` to 32000 (calibrated against measured file sizes) AND add a `stop_reason == "max_tokens"` check that fails the workflow loudly instead of writing partial files.

### Why
The weekly cron fired three times against the accumulated 12-version GStack drift surfaced in v2.11.1's VERSIONS.md report. Each attempt timed out at the same 300s curl limit, and the self-repair workflow couldn't recover because of its own parse bug — silent drift compounded for ~3 weeks until the user noticed the failure emails. Three-lens verification on this fix (self-check → pitfall verification → codex review) caught the output-budget issue that the first two lenses missed: pitfall verification's max_tokens estimate undercounted SKILL.md size by ~40%, and codex spotted the gap by reasoning about the prompt's "return complete file" contract against the file sizes.

### Backwards compatibility
**Fully backwards compatible.** The `===CHANGELOG.md===` marker was only consumed by `check-updates.yml` itself; the new `===NEW_CHANGELOG_ENTRY===` marker replaces it cleanly. No generated-CLAUDE.md changes, no skill behavior changes. The next scheduled cron run (next Monday 07:23 UTC) will exercise the fix against real upstream drift. Manual trigger via `gh workflow run check-updates.yml` available for impatient operators.

## [2.11.1] - 2026-05-20

### Fixed
- **Documentation drift after `ios-native-review` ship (v2.4.0).** README skill count, skill bullet list, workflow diagram (Phase 1.5), "New Feature" common scenario, and decision tree all referenced `macos-native-review` without the iOS counterpart. CLAUDE.md routing section likewise omitted both native-review skills. IDEAS.md "Shipped" record only listed the v1.9.0 and v1.10.0 ships.

### Changed
- **README.md** — "ten skills" → "eleven skills"; added `/ios-native-review` bullet mirroring the macOS form; added iOS lines to the workflow diagram, common scenario, and decision tree (parallel to existing macOS lines, not nested under "also iOS").
- **CLAUDE.md (project routing)** — added explicit routing bullet for `/macos-native-review` and `/ios-native-review` post-spec/plan, complementary to pitfall-verification and quality-review.
- **IDEAS.md** — Shipped section now records `ios-native-review` (v2.4.0). The body entry above is retained for proposal-vs-shipped record per the section's own convention.
- **VERSIONS.md** — added "Drift detected — pending review" section recording the 2026-05-20 local check (`./scripts/check-updates.sh`). GStack drifted 12 minor versions (v1.34.1.0 → v1.42.1.0), Claude Code 19 patches (2.1.126 → 2.1.145). The "Verified Versions" table is intentionally NOT advanced; the file's "last verified" semantics require an actual review of upstream changes against the manual, which is the weekly GitHub Action's job (or a manual review pass). The script's state file `.update-state.json` is gitignored, so the local check doesn't affect the commit; the drift record lives in `VERSIONS.md` itself.

### Why
Docs-only review on 2026-05-20 surfaced that `ios-native-review` shipped 2 days ago and was already enumerated in skill front-matter and IDEAS body, but the README + CLAUDE.md skill catalogue had never been updated. The drift class is "auto-managed (CLAUDE.md generation via markers) keeps synced; manual prose surfaces don't". Future-proofing this (e.g. a script that generates README skill bullets from `skills/*/SKILL.md` front-matter) is a v2.12 candidate, not in scope here.

### Backwards compatibility
**Fully additive — documentation only.** No skill behavior changes, no marker bumps, no generated-CLAUDE.md changes. Existing adapted projects unaffected.

## [2.11.0] - 2026-05-19

### Added
- **`### Multi-lens review (ship-worthy changes)` section** (marker `<!-- gstack-multi-lens-review-v1 -->`) emitted into every generated CLAUDE.md — NOT conditional on track. Codifies the three-lens review pipeline (self-check → pitfall verification → codex review) as an explicit project-level workflow rule for ship-worthy commits.
- **Explicit ship-worthy criteria** — YES list (version bumps, CHANGELOG entries, feat/fix/refactor commits, public-contract changes) and NO list (docs/typos, comments, WIP, test-only). Lets agents decide deterministically when codex review is justified vs overkill.
- **Cost guidance** — codex ~$0.05-0.20 + 30s-2min per review. Frames the trigger as a cost/value tradeoff, not a hard mandate.
- **Order rule** — self → pitfall → codex. Running codex first wastes tokens on issues simpler passes catch.

### Changed
- **`setup-routing` Step 6** emits the new section under `## Skill routing` as `### Multi-lens review`, placed between `### Git hygiene & commit cadence` and `### Track-aware routing` — natural order since it builds on the commit-trigger concept established by Git hygiene.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case marker logic as Autonomy, Git hygiene, Track-aware, Native Apple tools, and Companion skills. Universal (not track-gated).

### Why
Real-world dogfood (2026-05-19, this repo): self-pitfall verification on v2.10.0 ran two rounds and caught 3 issues. After fixing those, codex review caught a 4th — REPLACE-wording drift across 2 unrelated section blocks that self-review systematically missed. Different lens, different blind spot. The user's question "burde det nedfelles i workflowen?" surfaced the gap: pitfall verification was already in the user-level CLAUDE.md verification process (always-after-completion), but codex review was nowhere — agents had to be asked manually. v2.11.0 makes codex the explicit third lens in the project-level workflow for ship-worthy work.

**User-level twin:** `~/.claude/CLAUDE.md` updated in the same session to add codex as step 3 in the personal verification process. The plugin-level rule applies to *any* agent reading a project's CLAUDE.md; the user-level rule applies to the plugin maintainer's own work. Both fire on the same trigger.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The section emits into newly-generated CLAUDE.md and is inserted into existing CLAUDE.md via `/superpowers-gstack:adapt`. Marker pattern means future updates auto-upgrade.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing projects to add the Multi-lens review section.
- **Codex review is opt-in to your spending budget.** The section frames the cost transparently. If you don't have codex CLI installed, the gstack `/codex` skill will tell you how to install it; if you don't want to spend on it for a particular ship-worthy commit, skip explicitly and note the rationale.
- **The dogfood story (v2.10.0 → v2.10.1 → v2.10.2) is the canonical evidence** for the three-lens approach. 3 self-pitfall issues + 1 codex issue = 4 total catches that the standard "just commit" workflow would have shipped silently.

## [2.10.2] - 2026-05-19

### Fixed
- **Codex review finding [P2]:** adapt's case-2 REPLACE wording for the Git hygiene block (added in v2.10.0) and the Native Apple tools block (added in v2.7.x) said "REPLACE through next heading" without specifying "of equal-or-shallower level". Both blocks contain H3+H4 nested structure; an agent following the instruction literally would stop at the first H4 subsection (e.g. `#### When to commit`) and leave the rest of the old version's prose behind, producing duplicated/conflicting content.
- Same fix applied to both blocks. Wording now matches Autonomy (v2.8.0), Track-aware (v2.3.2), and Companion (v2.9.0) blocks — all use "of equal-or-shallower level". Added a parenthetical note in each fixed block explaining WHY the qualifier matters, so future contributors don't strip it as "redundant".

### Why
Codex code review on v2.10.0 + v2.10.1 diff caught this as a P2 finding ("can corrupt generated CLAUDE.md files during v1-to-v2 replacement"). Manual review confirmed: only 3 of 5 marker-managed sections had the correct wording; Git hygiene and Native Apple tools were drift outliers. Independent cross-model review caught what self-pitfall-verification missed.

### Backwards compatibility
**Fully backwards compatible.** Adapt's case-logic descriptions are instructions for the agent invoking the skill — they affect future adapt runs, not stored state. Projects adapted before v2.10.2 are unaffected; their next adapt run will use the corrected logic.

## [2.10.1] - 2026-05-19

### Changed
- **Git hygiene marker bumped `v1` → `v2`.** Round 1 pitfall verification on v2.10.0 surfaced three real risks that v2.10.1 fixes inline.

### Fixed
- **Convention-discovery ambiguity** — v1 said "use repo convention if exists, else default" but didn't handle the realistic case of MIXED commit styles in the log. v2 splits into three explicit cases: consistent convention → follow it; empty log → use default; inconsistent log → use default AND note in summary so the user can decide whether to standardize.
- **Cross-section conflict with Autonomy rule (v2.8.0)** — v1 cadence rule said "STOP after >5 commits" but Autonomy section says "only stop in 5 specific categories". An agent reading both could ignore cadence as "not in the 5 categories". v2 explicitly maps the cadence STOP to Autonomy category 5 ("truly blocked — verification gap") so the precedence is unambiguous.
- **git stash advice without scope caveat** — v1 said "use git stash to save progress" without noting that stash is risky for longer holds (silent loss via `git stash clear`, invisible in `git branch`). v2 qualifies: "short-lived holds (minutes to hours); for longer holds create a WIP branch instead".

### Why
Pitfall verification (round 1 on v2.10.0): three issues found, all in the same Git hygiene section. Per the skill's two-rounds policy, fix inline and re-run. Round 2 (on the patched artifact): CLEAN. v2.10.1 ships those fixes plus the marker bump that triggers auto-upgrade via adapt's REPLACE path on existing v2.10.0-adapted projects.

### Backwards compatibility
**Fully backwards compatible — auto-upgrade via marker pattern.** Adapt's case-2 logic now explicitly recognizes both `v1` legacy markers and absent markers, REPLACEs through next heading, preserves heading level. Pre-v2.10.0 projects (no marker) get the v2 section appended cleanly.

## [2.10.0] - 2026-05-19

### Added
- **`### Git hygiene & commit cadence` section** (marker `<!-- gstack-git-hygiene-v1 -->`) emitted into every generated CLAUDE.md — NOT conditional on track. Universal git workflow guidance for any project type.
- **"When to commit" guidance** (4 trigger conditions) + **"Do NOT commit"** anti-list (3 anti-patterns). Distinguishes meaningful milestones from progress-saves and mid-task chunks.
- **Commit message format template** with type/scope convention and reference to the repo's existing `git log --oneline -10` as the canonical source for project style.
- **Hygiene rules list** (5 NEVER-violations): no `--no-verify`, no `--amend` on pushed commits, no force-push to main/shared, no `--hard` reset without stash, no `git add -A` with secrets/binaries risk. Mirrors the standard git-safety protocol but as an explicit emit-into-project-CLAUDE.md rule.
- **Cadence rule** — if >5 commits land in a row without testing cumulative state, STOP and verify. Catches the "progress-without-verification" failure mode where committed-but-untested work accumulates.

### Changed
- **`setup-routing` Step 6** emits the new section into the `## Skill routing` block as `### Git hygiene & commit cadence`, placed immediately after `### Autonomy and user interruption` and before `### Track-aware routing`.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case marker logic as Autonomy (v2.8.0), Track-aware routing (v2.3.2), and Xcode tools (v2.7.x). Universal (not track-gated).

### Why
Real-world observation from sing-replay session (2026-05-19): the SwiftUI agent shipped 40 tests + 2404 lines of Swift code without a CLAUDE.md ever being created — meaning no per-project commit-cadence guidance was ever loaded into the agent's context. The agent committed at arbitrary cadences and used phrases like "Bekreft + neste steg" as wait-states, which we patched in v2.8.0. v2.10.0 patches the parallel git-hygiene gap: agents working in projects WITH a CLAUDE.md will now see explicit commit-cadence + commit-message + hygiene rules on every session start.

**Architectural note:** the *trigger* for creating CLAUDE.md in the first place is user-level concern (lives in `~/.claude/CLAUDE.md`), not plugin-level — chicken-and-egg, since the trigger has to fire BEFORE CLAUDE.md exists. The plugin owns the *rules* (what to do once CLAUDE.md exists), the user-level CLAUDE.md owns the *bootstrap-on-detect* trigger.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The section emits into newly-generated CLAUDE.md and is inserted into existing CLAUDE.md via `/superpowers-gstack:adapt`. Marker pattern means future updates auto-upgrade.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing projects to add the Git hygiene section. Universal — runs on web and native projects alike.
- **The cadence rule is the most actionable** — "5 commits without verifying cumulative state" maps directly to the kind of vibe-coder failure mode where commits accumulate and breakage compounds. Worth dogfooding in your own workflow.
- **The trigger for bootstrap-from-empty-project** is in the user's `~/.claude/CLAUDE.md` (added 2026-05-19), NOT this plugin. The plugin handles "what to do once bootstrap completes"; the user-level rule handles "fire bootstrap before 40 tests get shipped without CLAUDE.md".

## [2.9.0] - 2026-05-18

### Added
- **Companion skills (discovery) section** in generated CLAUDE.md for SwiftUI projects (track ∈ {ios, macos, both}). Surfaces four third-party expert skills by Antoine van der Lee: `swiftui-expert-skill`, `swift-concurrency-expert-skill`, `core-data-expert-skill`, `swift-testing-expert-skill`. Lists what each does + the install commands.
- **Workflow fit table** clarifies the complementary stages: this plugin's review skills (`macos-native-review`, `ios-native-review`) operate at spec/plan time (pre-code); Antoine's skills operate at code review time (post-code). Same Apple-platform project, different lifecycle stages, zero overlap.
- **Curation policy stated:** widely-installed, actively-maintained skills from recognized ecosystem experts. PRs welcome to add entries.

### Changed
- **`setup-routing` Step 6** emits the new section under `## Skill routing` as `### Companion skills (discovery — not routing)`, conditional on native track.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case marker logic (`<!-- gstack-companion-skills-v1 -->`) as Track-aware routing and Xcode tools.

### Why
Closes issue #11 ("Companion skills discovery in setup-routing/adapt"). The plugin's evaluation tables list only Superpowers + GStack skills — third-party expert skills are invisible to a user setting up or adapting a project. By the time they reach code-review stage on a SwiftUI app, they may have forgotten that Antoine's skills exist. v2.9.0 makes the discovery durable: every SwiftUI project's CLAUDE.md includes the table; every agent that reads CLAUDE.md on session start sees it.

**Architectural boundary preserved.** This is discovery, NOT routing. The plugin does not auto-invoke the companion skills, does not depend on them being installed, does not write routing rules that assume their presence. Users can run the workflow without them; they just miss the optional code-review pass. The plugin doesn't ship, version, or guarantee the companion skills — that's their authors' job.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The section emits into newly-generated CLAUDE.md for native projects and is inserted into existing native projects via `/superpowers-gstack:adapt`. Web projects unaffected (no companion entries yet for non-Apple ecosystems — separate follow-up).

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing native projects to add the Companion skills section.
- **Adding more companion skills** (other ecosystems, other authors): edit the table in `skills/setup-routing/SKILL.md` (template) and `skills/adapt/SKILL.md` (insert block) together. Bump marker only if the table semantics change (e.g. new columns); adding rows is cosmetic.
- **Non-Apple ecosystems** (React/Next.js, Python data, Rails, etc.) intentionally deferred to a follow-up issue. Start with what we know — the Apple skills are battle-tested in this workflow.

## [2.8.1] - 2026-05-18

### Fixed
- **M1** — `docs/superpowers/plans/2026-05-17-swiftui-design-consultation-implementation.md:738` had a stale docstring comment claiming `contrast-check.sh` exits 0 always. The actual script (and its in-repo docstring) correctly exits nonzero on usage/hex errors. Plan-file comment updated to match reality.
- **M3** — Same plan file's intro overstated Phase 2/3 parallelism. Clarified: writing the two phases can parallelize after Phase 1, but Phase 3 *execution* still requires Phase 2 templates to exist on disk (the skill references template paths).

### Notes
- **M2** stays deferred** per backlog ("Commit steps not idempotent — Real fix would require dynamic commit-message generation based on staged diff — out of scope"). Documented in backlog as accepted-and-deferred.
- Both M1 and M3 are documentation-only fixes in a historical plan artifact. No skill behavior changes.

## [2.8.0] - 2026-05-18

### Added
- **`### Autonomy and user interruption` section** (with version marker `<!-- gstack-autonomy-v1 -->`) emitted into every generated CLAUDE.md — NOT conditional on track. Establishes autonomous continuation as the default behavior for agents; stopping to ask the user is the LAST resort, not the default.
- **Five categories that warrant stopping** (and only these): user-territory operations (Apple Developer Portal, 2FA-gated services), destructive operations needing approval, genuinely ambiguous design choices, explicit skill/plan checkpoints, true blocks. Each category is defined precisely so agents can self-check.
- **"When NOT to stop" anti-list** — five common politeness patterns ("shall I continue?", "ready when you are", convenient-milestone check-ins) flagged as autonomy failures.
- **Forbidden-phrases list** (6 entries, EN + NO) of continuation-token language that signals failed autonomy. If an agent catches itself writing one of these, it must self-correct.
- **Status-update template** showing the difference between progress-signals-during-work (✅) versus wait-state-for-permission (❌). Three concrete before/after examples.

### Changed
- **`setup-routing` Step 6** emits the new section into the `## Skill routing` block as `### Autonomy and user interruption`, placed immediately after `### Rules` and before `### Track-aware routing`.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case marker logic as Track-aware routing and Xcode tools. Universal (not track-gated) since over-asking is platform-agnostic.

### Why
Real-world frustration from downstream session: a SwiftUI agent completed Phase 1 work, produced a 12-row status table, and ended with "Pinge meg når du vil at jeg setter i gang neste rundene" / "Bash-prompten din er fortsatt aktiv — om du vil at jeg fortsetter direkte, si bare 'fortsett UI-runde 1'". The user's reaction: frustration. Solo vibe-coder workflows depend on agents staying in motion through scoped work — every "ready when you are" forces a context-switch back to the user for permission to do work the user already authorized.

v2.8.0 makes the autonomous-by-default behavior an explicit rule emitted into every generated CLAUDE.md. Agents that read CLAUDE.md on session start now see the five-categories-only rule for stopping, the forbidden-phrases list, and the progress-signals-during-work pattern. Same systemic-fix-via-CLAUDE.md-rule pattern as the v2.7.x Xcode-tools work.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The section emits into newly-generated CLAUDE.md and is inserted into existing CLAUDE.md via `/superpowers-gstack:adapt`. Marker pattern (`<!-- gstack-autonomy-v1 -->`) means future updates auto-upgrade existing projects.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing projects to add the Autonomy section. Universal — runs on web and native projects alike.
- **The five categories are the contract.** If you want agents to stop for other reasons in a specific project, add a project-local instruction in your CLAUDE.md alongside the inserted section (the section is gstack-managed; adjacent content is yours).
- **Bump the marker (`v1` → `v2`)** in future versions only when the autonomy rules themselves change — not for cosmetic edits or adding a forbidden phrase to the existing list.

## [2.7.2] - 2026-05-18

### Added
- **New subsection "Capabilities, signing, and provisioning"** in the Native Apple development tools block. Documents the three-surface split: `.entitlements` file (agent-handled, declarative XML), `project.yml` / build settings (agent-handled, declarative YAML), and Apple Developer Portal (user-handled, agent has no API access). Concrete CloudKit example walks through 6 steps from entitlements edit to portal-handoff to retry-build.
- **Error-recovery handoff template** for signing failures: agent stops, surfaces the exact portal URL + steps the user needs (e.g. "Go to developer.apple.com → Identifiers → enable iCloud capability → link container `iCloud.com.example.appname`. ~30 seconds."), then retries build after user confirms portal-side setup is done.
- **Fastlane match mention** as the standard CI/CD provisioning automation surface; explicitly out of scope for solo vibe-coder workflows but acknowledged for users who scale beyond a few apps.

### Changed
- **Marker bumped from `v2` to `v3`** — section semantics expand to cover the capabilities/signing/portal split (v1 = MCP-only tools, v2 = MCP + CLI fallback, v3 = + provisioning workflow).
- **Adapt's case-2 logic updated** to handle both `v1` and `v2` legacy markers (both REPLACE through next heading), not just `v1`.

### Why
Real-world question from downstream session: "Will the agent now successfully check the CloudKit capability + select team WXNUGGYB2B?" Answer in v2.7.1 was implicit — the anti-patterns mention "click through the Signing & Capabilities pane → declare in entitlements + project.yml" but never explain the WHY (portal needs human 2FA) or the WORKFLOW (entitlements → project.yml → xcodegen → xcodebuild → handoff if portal-side missing → retry). v2.7.2 makes that workflow explicit so agents don't either (a) silently fail without a clear handoff or (b) attempt to click through UI that doesn't exist for them.

### Backwards compatibility
**Fully backwards compatible — auto-upgrade via marker pattern.** Projects with v1 or v2 markers get REPLACED through next heading on next `/superpowers-gstack:adapt` run. Surrounding CLAUDE.md untouched. Pre-v2.7.0 projects (no marker) treated as case 3 — same REPLACE behavior, adds v3 marker.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing native projects to upgrade v1/v2 → v3. The capabilities/signing/portal split is now part of the agent's playbook for any SwiftUI project.
- **The CloudKit example is generalizable.** Same pattern applies to push notifications, app groups, keychain sharing, sign-in-with-Apple — any capability that requires both an entitlements declaration AND portal-side registration.
- **Bump the marker (`v3` → `v4`)** in future versions only when the routing or workflow semantics change again — not for cosmetic edits, adding a single tool, or rewording an existing example.

## [2.7.1] - 2026-05-18

### Changed
- **Native Apple development tools section bumped from `v1` to `v2`.** v1 (shipped in v2.7.0) assumed XcodeBuildMCP was universally available — but XcodeBuildMCP is a per-session MCP install, not a default. Agents in sessions without XcodeBuildMCP would search via `ToolSearch`, find nothing, and fall back to asking the user to "open Xcode" — the exact failure mode v2.7.0 was meant to prevent.
- **v2 routing table is now MCP-preferred + CLI-fallback**, with two columns: "Preferred (MCP)" and "Fallback (CLI, always available with Xcode)". CLI fallbacks listed for every operation that supports them: `xcrun swift -typecheck`, `xcodebuild build/test`, `xcrun simctl list/boot/launch/spawn/io`. UI automation (`ui_tap`, `snapshot_ui`) noted as MCP-only since `xcrun simctl io` only supports screenshots.
- **New "Project file management" subsection** recommends XcodeGen (`brew install xcodegen`, declarative `project.yml`) over hand-editing `.xcodeproj` XML or clicking through Xcode UI. Tuist mentioned as the heavier alternative when XcodeGen isn't sufficient.
- **Anti-patterns expanded** to pair each failure mode with BOTH the MCP and CLI fix (e.g. "use `test_sim` (MCP) or `xcodebuild test` (CLI)"). New anti-pattern added: "Click through the Signing & Capabilities pane" → declare in `.entitlements` + `project.yml`.

### Why
Real-world correction from a downstream agent: a SwiftUI agent in a sing-replay project flagged that XcodeBuildMCP wasn't in its MCP-server list (only swiftui-rag, playwright, pencil, gemini, AWS-specific). The agent correctly identified `xcodebuild` CLI + XcodeGen as the universally-available alternative. v2.7.0's tool routing — which named only MCP tools — would have routed agents in such sessions back to "ask user to open Xcode" because the MCP tools simply aren't there. v2.7.1 corrects the universalist assumption.

### Backwards compatibility
**Fully backwards compatible — auto-upgrade via marker pattern.** Projects adapted with v2.7.0 have the section marked `<!-- gstack-xcode-tools-v1 -->`. Re-running `/superpowers-gstack:adapt` on those projects hits case 2 (marker present + different version) and REPLACES the section through to the next heading. Surrounding CLAUDE.md content untouched. This is precisely why the marker pattern (introduced in v2.3.2) exists — fix-forward for routing-rule mistakes without manual editing across N adapted projects.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing native projects to upgrade v1 → v2. If you adapted between v2.7.0 ship time and this fix, you'll get the corrected (MCP-preferred + CLI-fallback + XcodeGen) section automatically.
- **CLI fallbacks tested in concept, not in tests/ suite.** Adding a `tests/integration/test_xcode_routing.sh` is now a natural backlog item — assert that the v2 section emits both MCP and CLI tool names. Deferred.
- **Bump the marker (`v2` → `v3`)** in future versions only when routing semantics change again — not for cosmetic edits or adding a single tool to the existing table.

## [2.7.0] - 2026-05-18

### Added
- **Native Apple development tools routing** in generated CLAUDE.md for SwiftUI projects (track ∈ {ios, macos, both}). New section `## Native Apple development tools (Xcode workflow)` with version marker `<!-- gstack-xcode-tools-v1 -->`. Tells the agent which MCP tools own which Apple-platform operations, and what NEVER to delegate to the user.
- **Tool routing table** lists 11 operation categories — typecheck (swiftui-rag), HIG review (swiftui-rag), build/test/simulator (XcodeBuildMCP), UI automation (XcodeBuildMCP), Apple docs (apple-docs), WWDC content (apple-docs). Every entry names the MCP tool by full identifier (`mcp__XcodeBuildMCP__test_sim`, etc.).
- **Anti-patterns** section explicitly enumerates the failure modes: "Open Xcode and run the tests", "Build in Xcode to verify", "Take a screenshot of the simulator", "Check what a system color looks like" — each paired with the MCP-tool replacement.

### Changed
- **`setup-routing` Step 6** emits the new section into newly-generated CLAUDE.md when the track question (Step 2 Q10 successor) reveals a native project. Web-only projects skip the section entirely.
- **`adapt` Step 5** inserts or upgrades the section using the same four-case logic as Track-aware routing (heading + marker matches → skip; different version → REPLACE; no marker → REPLACE one-time silent upgrade; heading absent → APPEND). Native-track gate: skip entirely for web-only projects.

### Why
Real-world failure-mode observed in a downstream project: a SwiftUI agent type-checked Swift code correctly (via `mcp__swiftui-rag__swift_typecheck`) but then asked the user to "open Xcode and run the 12 tests to verify." The agent had `mcp__XcodeBuildMCP__test_sim` available as a deferred tool but never invoked it — because nothing in CLAUDE.md or any skill ever named XcodeBuildMCP as the canonical test runner. The result: vibe-coder gets handed verification work that the agent should do itself.

v2.7.0 makes the tool surface explicit in generated CLAUDE.md for native projects. Future SwiftUI agents starting in such projects will read the table on session start and route Xcode operations to MCP tools instead of delegating to the user. Web projects are unaffected (no section emitted).

### Backwards compatibility
**Fully additive for new projects. Forward-clean for existing.** Pre-v2.7.0 native projects don't have the section — `adapt` falls into case 4 (heading absent → APPEND), no duplication risk. Web projects: section never emitted at all. Existing CLAUDE.md content outside the new section is never touched. Same version-marker pattern as v2.3.2's track-aware routing means future Xcode-tool-table updates auto-upgrade via REPLACE instead of forcing manual edits across N adapted projects.

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing native projects (track ∈ {ios, macos, both}) to add the Xcode-tools section. Single call; routing-version-marker mechanism (v2.3.2) handles the upgrade.
- **Web projects: nothing changes.** The skill detects `.gstack/track` is absent or `web` and skips the section.
- **Bump the marker (`v1` → `v2`)** in future versions only when the tool routing semantics change — not for cosmetic edits or adding tools to the existing table.

## [2.6.0] - 2026-05-18

### Added
- **`tests/` directory with integration-test infrastructure.** First test: `tests/integration/test_track_aware_dispatch.sh` verifies track-aware routing dispatches `/design-consultation` correctly. Two cases (track=ios → swiftui variant; no marker → gstack default), each shells out to `claude --print` in a temp-dir fixture with a minimal CLAUDE.md containing the routing block. Cost ~1 min and a few cents per case; safety net via `--max-budget-usd 1.00`.
- **`tests/run.sh`** — entry point with `--integration` / `--unit` flags. Discovers and runs `tests/integration/test_*.sh` files.
- **`tests/README.md`** — documents prerequisites (Claude Code CLI, `ANTHROPIC_API_KEY`), cost model, what's tested vs deferred, and why integration over unit for this skill set (dispatch logic lives in LLM-interpreted CLAUDE.md text; can't unit-test that without mocking the dispatcher under test).

### Changed
- **`README.md`** gains a **Testing** section linking to `tests/README.md`.

### Why
Closes backlog item **S1** from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v1.0 of swiftui-design-consultation's smoke tests "verified by inspection" that routing rules existed in the generated CLAUDE.md — but never tested actual dispatch behavior. Codex flagged this as the highest-impact gap because mis-dispatch on a native project means the user gets the wrong skill (gstack web design-consultation instead of `swiftui-design-consultation`) and may not notice until DESIGN.md is wrong.

The new test runs against the real Claude Code dispatcher with the real plugin loaded — there is no mocking. Live verification against `Paretofilm/superpowers-gstack@7eadf4f` shows both cases pass: the LLM correctly identifies `superpowers-gstack:swiftui-design-consultation` for track=ios, and explicitly notes "not the SwiftUI namespaced variant" when defaulting to gstack for missing-marker.

### Backwards compatibility
**Fully additive.** No skill behavior changes. The new `tests/` directory and `tests/README.md` exist for contributors; runtime behavior unaffected. No new dependencies (bash only; uses `claude` CLI which is a prerequisite for using the plugin anyway).

### Notes for users
- **Run before submitting PRs that touch routing rules:** `bash tests/run.sh --integration` catches dispatch regressions that "verify by inspection" misses.
- **CI integration deferred.** Running integration tests in GitHub Actions requires `ANTHROPIC_API_KEY` as a repo secret and willingness to spend on every PR. Open question — left as a separate backlog item.
- **Adding tests:** drop another `tests/integration/test_*.sh` script following the same pattern (mktemp fixture → claude --print → grep output). The runner picks them up automatically.

## [2.5.0] - 2026-05-18

### Added
- **`skills/swiftui-design-consultation/schema/proposal.schema.yaml`** — formal data model for design proposals (JSON Schema vocabulary in YAML form). 11 top-level fields (`schema_version`, `metadata`, `track`, `typography`, `color`, `materials`, `motion`, `spacing`, `accessibility`, `platforms`, `budget`, `decisions_log`) capture every token Phase 6 generators consume. `version: 1` documented as the current schema version; mismatch between proposal `schema_version` and schema `version` is a hard STOP error with explicit upgrade guidance.
- **`skills/swiftui-design-consultation/schema/proposal.example.yaml`** — fully populated canonical example (Lighthouse macOS menu-bar utility). Shows every required and recommended field; new proposals SHOULD start from this template and only modify fields where the actual design differs.
- **New Phase 6 Step 6.0 (schema validation)** — read cached proposal YAML, validate against schema (LLM-side: walk every `required` field, confirm type matches), then confirm `schema_version` + `track` align with project state. STOPs surface schema gaps explicitly; never silently substitute empty strings.
- **Severity monotonicity guard between HIG iterations (Step 6.7)** — after each iteration N, compare findings against N-1. No NEW CRITICAL allowed; SIGNIFICANT count must not increase; POLISH may drift. Rollback proposal YAML to N-1 state if monotonicity violated, then AskUserQuestion (accept N anyway / accept N-1 / refine manually). Prevents the failure mode where a fix trades one CRITICAL for another, or fixes a SIGNIFICANT by introducing two new ones.

### Changed
- **Phase 3 Step 3.1 (build data model)** — now references the schema explicitly and produces a structured YAML proposal alongside the in-memory object. "Build the in-memory DesignProposal" → "Build the DesignProposal as a structured YAML document matching proposal.schema.yaml".
- **Phase 3 Step 3.2 (serialize + htmlify)** — writes BOTH `design-proposal-$TS.md` (human-readable, for htmlify preview) AND `design-proposal-$TS.yaml` (structured, for Phase 6). Same pinned timestamp; same data, different presentation.
- **Phase 3 Step 3.4 (cache approved proposal)** — caches both files under canonical names (`swiftui-consultation-state.proposal.yaml` + `.md`). The YAML is authoritative; the MD is its presentation; they must stay consistent.
- **Phase 6 Step 6.1 (generate DESIGN.md)** — token substitution sources from the parsed proposal YAML object loaded in Step 6.0, NOT from prose. New explicit token-to-YAML-field mapping table (15 tokens × YAML paths).
- **Phase 6 Step 6.2 (generate Swift Package)** — same change: tokens map to parsed YAML paths. New mapping table covers all 9 Swift-template tokens. Both 6.1 and 6.2 read the same parsed object, so prose-vs-code drift is structurally impossible.
- **Phase 6 Step 6.7 iteration loop** — proposal YAML is the only thing that gets edited during iteration; DESIGN.md and DesignSystem/* are always regenerated from it. In-memory backup of the YAML before each iteration enables mechanical rollback for the monotonicity guard.

### Why
Closes backlog items **S3** (formal data model) and **S4** (HIG iteration convergence guard) from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v1.0 of swiftui-design-consultation produced DESIGN.md and DesignSystem/* by substituting tokens into templates from a *prose* proposal MD — the "pure functions of the same data model" guarantee was aspirational, not enforced. Drift was possible whenever the LLM mis-substituted tokens, and the iteration loop could leave the user with a strictly worse artifact than they originally approved (no comparison against iteration N-1, no severity monotonicity).

v2.5.0 makes the data model real (structured YAML + schema) and adds the rollback guard. Both changes are LLM-side (no new dependencies, no validator binary, no build step). The schema is human-readable YAML; the validation is the skill reading the schema and confirming the proposal matches; the monotonicity check is finding-comparison the skill performs between iterations.

### Backwards compatibility
**Breaking for in-flight Phase 3 work**, additive for new consultations. Projects mid-consultation when v2.5.0 lands need to re-run Phase 3 to produce a structured proposal YAML — the cached prose-only `swiftui-consultation-state.proposal.md` is not sufficient for Phase 6 anymore. For new projects: zero migration. For freshly-shipped DESIGN.md/DesignSystem from v1.x consultations: no change (the artifacts are already on disk; the schema only matters when re-running the skill).

### Notes for users
- **Re-running consultation after v2.5.0:** start fresh from Phase 0 to produce the YAML proposal. The skill detects missing YAML in Step 6.0 and surfaces it explicitly.
- **Schema evolution:** when adding/removing/renaming proposal fields in the future, bump `version` in `proposal.schema.yaml` and document the upgrade path in the CHANGELOG. The schema-version mismatch check in Step 6.0 will catch proposals on the old format.
- **Monotonicity guard tuning:** if you find legitimate cases where iteration 2 *should* introduce a new SIGNIFICANT (e.g. a deliberate trade-off the user accepts), the AskUserQuestion offers option (A) to override. The guard never silently blocks — only surfaces the discrepancy.

## [2.4.0] - 2026-05-18

### Added
- **`/superpowers-gstack:ios-native-review`** — pre-implementation HIG-citation-grounded review skill for iOS/iPadOS app specs, mirroring the established `macos-native-review` pattern. 13 iOS-specific categories: vocabulary, controls & touch targets (44×44 pt), navigation paradigm (TabView / NavigationStack / NavigationSplitView), modal presentation (sheets + detents, full-screen, popovers), gestures, system surfaces (safe area, Dynamic Island, status bar), keyboard handling (keyboardType / textContentType / submitLabel), haptics, semantic colors & dark mode, animation timing, privileged operations & permission prompts (ATT, location, notifications), accessibility (VoiceOver, Dynamic Type up to AX5, Reduce Motion), app lifecycle & state restoration.
- **Phase 0 iOS signal detection** mirrors macos-native-review's structure: scans for `.swift` files, `UIKit`/`SwiftUI` imports, iOS-flavored types (`UIViewController`, `TabView`, `NavigationStack`, etc.), `iOS app` text mentions, iOS deployment targets. Multi-target projects (iOS + macOS) proceed; macOS-only signals return N/A with sibling-skill note pointing at `/superpowers-gstack:macos-native-review`.
- **Robust-citation strategy reused.** Same JSON fallback as macos-native-review (`developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json`) for cases where the JS-rendered HTML returns only a page title. Verified at skill creation against `/buttons` (canonical 44×44 pt touch-target quote returned).

### Changed
- **`setup-routing` evaluation table** now includes both `macos-native-review` and `ios-native-review` rows. Closes a pre-existing oversight (macos-native-review was missing from the table though it shipped in v1.9.0). Generated CLAUDE.md routing now offers both review skills with platform-aware descriptions.
- **`adapt` evaluation table** mirrors the addition for projects being adapted into the workflow.
- **`setup-routing/model-routing.md`** adds `ios-native-review` row with same model recommendation as macos-native-review (`sonnet` everywhere, `sonnet (req. web)` for Pi local-only since WebFetch against developer.apple.com is required).
- **`macos-native-review` Phase 0** updated: iOS-only signals now point at the newly-shipped `/superpowers-gstack:ios-native-review` instead of "the skill is in the backlog (IDEAS.md)".
- **`IDEAS.md`** marks ios-native-review entry as ✅ SHIPPED in v2.4.0.

### Why
Closes backlog item S2 from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v2.3.0/v2.3.1 shipped dual-track support but iOS-only projects had no DESIGN.md HIG-review path — only the platform-agnostic rules from `macos-native-review`'s SwiftUI-rag chain fired. v2.4.0 closes that gap symmetrically; iOS + macOS multi-target projects now have parallel review surfaces. The deferral note from IDEAS.md was accurate ("Pick up when a real iOS spec review surfaces the gap") — the gap surfaced as part of dual-track stress-testing.

### Backwards compatibility
**Fully additive.** No existing skill behavior changes. The only edit to `macos-native-review` is the Phase 0 fallback text for iOS-only projects (cosmetic, points at the new skill instead of IDEAS.md). Multi-target projects (iOS + macOS) should run both review skills in parallel — neither replaces the other.

### Notes for users
- **Run on iOS specs the same way as macOS:** `/superpowers-gstack:ios-native-review` after `pitfall-verification` + `quality-review`, before implementation.
- **Re-run `/superpowers-gstack:adapt`** on existing iOS projects to surface the new skill in routing recommendations (uses the v2.3.2 routing-version-marker, so it's a single-call upgrade).
- **macos-native-review unchanged in scope.** Phase 0 just points at the sibling skill now instead of the backlog note.

## [2.3.2] - 2026-05-18

### Changed
- **`adapt` Track-aware routing section now uses a version marker (`<!-- gstack-routing-v1 -->`).** Previously, `adapt` skipped the routing section entirely if a section with the matching H2 already existed — which made the skill idempotent but ALSO prevented updating stale or malformed versions across projects already adapted.
- **New four-case logic in `adapt`:** heading + matching marker → skip (idempotent); heading + different-version marker → REPLACE through next H2 (upgrade path); heading + no marker (legacy v2.3.0/v2.3.1 projects) → REPLACE (one-time silent upgrade adds the marker); heading absent → APPEND.
- **`setup-routing` template** emits the version marker on the H3 heading from this version forward, so all newly-generated CLAUDE.md files are already on `v1` and pick up future updates automatically.

### Why
Closes backlog item S6 from `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md`. v2.3.0 introduced track-aware routing; v2.3.1 will not be the last time the rules evolve. Without a version marker, every rule change would require either (a) manual editing across N adapted projects, or (b) breaking idempotency. The marker pattern is forward-clean: the next semantic change (`v2`) auto-upgrades existing projects without disturbing surrounding CLAUDE.md content.

### Backwards compatibility
**Fully backwards compatible — no duplicate sections.** Projects adapted on v2.3.0/v2.3.1 have a heading without a marker. The four-case logic treats those as case 3 (REPLACE, byte-identical content + new marker), not as APPEND. The APPEND path only fires when no heading exists at all. Re-running `adapt` on existing projects performs a one-time silent upgrade; surrounding CLAUDE.md content outside the routing section is never touched.

**H2 vs H3 handled symmetrically.** Pre-existing inconsistency: `setup-routing` emits the section as **H3** (subsection of `## Skill routing`); `adapt` historically appended it as top-level **H2**. The new marker-detection scans for either level (`^#{2,3} Track-aware routing \(dual-track\)`) and preserves the original level during upgrade. This avoids accidentally promoting H3 → H2 (which would break the nested structure in setup-routing-generated CLAUDE.md files).

### Notes for users
- **Re-run `/superpowers-gstack:adapt`** on existing dual-track projects to add the version marker. The routing rules themselves are unchanged in this version — only the marker is added. After this, future rule changes (v2+) will upgrade silently.
- The marker is an HTML comment, so it does not render in Markdown previews. Bump the version (`v1` → `v2`) only when the section's semantics change, not for cosmetic edits.

## [2.3.1] - 2026-05-17

### Changed
- `swiftui-design-consultation` Step 6.6 now explicitly invokes **all
  three** swiftui-rag review tools in parallel
  (`review_macos_hig` + `review_accessibility` + `review_liquid_glass`)
  with a deduplication rule on `(rule_id, line)`. Previously the trio
  was mentioned but described loosely ("Same for ..."), which led the
  consumer to under-invoke and miss accessibility-only findings.
- Step 6.7 budget aggregation now explicitly counts findings from all
  three tools, deduplicated.
- Schema table now lists `question` (not `query`) as the
  `search_swiftui_corpus` primary parameter — verified against live
  swiftui-rag v1.4.0 / corpus v1.3.3 MCP responses.

### Documented
- **Known limitation** in Step 6.6: `C1-glass-on-content` does not
  always fire when `.glassEffect` is separated from its shape primitive
  by chained modifiers. Pattern that fires: `Circle().glassEffect()`.
  Pattern that does NOT fire: `Circle().fill(...).frame(...).glassEffect()`.
  Verified by live stress-test in this session. Track upstream fix at
  `swiftui-rag-pipeline` issue tracker.

### Why
- Stress-test on swiftui-rag v1.4.0 revealed the three review tools are
  complementary, not overlapping — each owns its own ruleset
  (`review_accessibility` is the only one that fires A1/A3, etc).
  Running only `review_macos_hig` misses all accessibility findings.

## [2.3.0] - 2026-05-17

### Added
- **`/superpowers-gstack:office-hours-track-aware`** — wrapper around
  upstream `/office-hours` that fixes three UX bugs observed in live
  v2.2.0 usage:
  1. Approval gate ran BEFORE htmlify rendered — user had to approve
     a design they hadn't seen rendered. Now htmlify runs first
     (auto-opens in Safari) and the approval gate comes after.
  2. Plain v1 HTML was rendered instead of the rich v2 plan-driven
     layout. Wrapper now inspects design-doc content for visual
     opportunities (Approaches Considered, architecture diagrams,
     pullquotes, metrics, callouts) and generates a v2 plan JSON
     before invoking `/htmlify --plan ... --open`.
  3. Track inference happened too late (or not at all). Wrapper now
     classifies the brainstormed idea as native vs web and asks the
     iOS/macOS/both platform question inline only when needed.
- Wrapper also relocates design docs from gstack's default location
  (`~/super-me/brain/ideas/seeds/...` etc.) into the project's
  `docs/superpowers/specs/` directory so they live alongside other
  project artifacts.

### Changed
- `swiftui-design-consultation` Step 0.1 now asks the platform question
  inline (AskUserQuestion D0 with iOS / macOS / both options) when
  `.gstack/track` is missing — previously delegated to the standalone
  `swiftui-track` skill. One fewer hop, same result.
- `setup-routing` and `adapt` skill tables: replaced
  `/superpowers-gstack:swiftui-track` row with
  `/superpowers-gstack:office-hours-track-aware`. Updated track-aware
  routing block in generated CLAUDE.md to intercept `/office-hours`
  (not `swiftui-track`) for dual-track projects.
- Repo `CLAUDE.md` skill routing: `office-hours` routes through the
  wrapper; dropped the swiftui-track row.
- `README.md` Skills section: replaced swiftui-track entry with
  office-hours-track-aware entry.

### Removed
- **`/superpowers-gstack:swiftui-track`** (v2.2.0 only) — the
  standalone marker-writing skill is gone. Its job is now folded into
  the wrapper (early-stage inference at brainstorm time) and into
  `swiftui-design-consultation` Step 0.1 (late-stage inline question
  if user jumps straight into design without brainstorming).

### Compatibility
- Backwards compatible. Projects with existing `.gstack/track` markers
  continue working unchanged. Projects without the wrapper installed
  fall back to plain `/office-hours` (gstack), as before.
- No upstream gstack or superpowers code touched.

### Review pipeline
- Inline pitfall-verification on v2.3.0 changes (single round)
- Real-world live-fire test: caught all three UX bugs from sing-replay
  session observation; wrapper design verified against that flow

## [2.2.0] - 2026-05-17

### Added
- **`/superpowers-gstack:swiftui-track`** — declare SwiftUI project
  platform target (iOS / macOS / both); writes `.gstack/track` marker.
  Idempotent.
- **`/superpowers-gstack:swiftui-design-consultation`** — Apple-canon
  design system consultation for SwiftUI projects. Produces `DESIGN.md`
  + Swift Package starter with semantic colors, SF Pro typography,
  Liquid Glass material discipline, named motion presets, and
  accessibility baseline. Orchestrates swiftui-rag MCP surface for
  HIG-citation grounding; uses `/htmlify` for Phase 3 proposal preview
  and Phase 6 DESIGN.html generation; chains into `macos-native-review`
  with HIG conformance budget.
- **`skills/swiftui-design-consultation/bin/contrast-check.sh`** — bash
  helper script implementing WCAG 2.1 contrast-ratio math (sRGB →
  linear → relative luminance → contrast). Called by Phase 6 to
  validate brand colors against text/background. Locale-safe via
  `LC_ALL=C` (decimal separator forced to dot regardless of user locale).

### Changed
- `setup-routing` and `adapt` skills now emit/preserve a
  "Track-aware routing (dual-track)" section in generated project
  CLAUDE.md files. This section tells the model how to dispatch
  `/office-hours` and `/design-consultation` based on `.gstack/track`.
- `macos-native-review` SKILL.md cross-references
  `swiftui-design-consultation` as the upstream design-system step.
- `htmlify` SKILL.md notes `swiftui-design-consultation` as a
  programmatic consumer.
- Repo `CLAUDE.md` skill routing table adds entries for both new
  skills.
- `README.md` "Skills" section adds entries for both new skills.

### Compatibility
- Backwards compatible. Projects without `.gstack/track` continue to
  route `/design-consultation` to the gstack web skill (unchanged
  default behavior).
- No changes to upstream gstack code; all routing logic lives in
  CLAUDE.md generated by setup-routing/adapt.

### Review pipeline
- Spec: `docs/superpowers/specs/2026-05-17-swiftui-design-consultation-design.md` (commit `80242e8`)
- Plan: `docs/superpowers/plans/2026-05-17-swiftui-design-consultation-implementation.md` (commit `4d9b75e`, patched by `96b82bd` + `aa32513` + `9fcffb8`)
- Pitfall verification: 2 rounds, 10 issues found, all patched
- Codex adversarial: 6 CRITICAL patched, 7 SIGNIFICANT + 3 MINOR deferred to `docs/superpowers/backlog/2026-05-17-swiftui-design-consultation-v1.1-backlog.md` (S5 fixed inline)
- Smoke tests: 5 of 5 paths verified (4 by inspection + 1 live `claude --plugin-dir` skill-load check)

## [2.1.1] - 2026-05-16

### Changed
- **`context-handoff` template adds `type: handoff` as first YAML field.** Aligns with htmlify v2.0+ classifier, which treats `type:` as the primary type-discriminator. v1.12.0 handoffs (without `type:`) still work via htmlify's filename-based legacy fallback, but new handoffs written by this skill are now first-class instead of legacy.
- **CLAUDE.md "Session continuity" updated** to detect three handoff formats: `type: handoff` (current, v2.1.1+), YAML-without-`type:` (v1.12.0 → v2.1.0), and prose-only (pre-1.12.0). All read the same YAML fields when present.
- **`context-handoff` SKILL documents htmlify hook side effect.** If the `/htmlify` PostToolUse hook is installed, writing handoff.md auto-renders it as HTML and opens it in Safari. Background, non-blocking — but visible. SKILL.md now warns to mention this once if it surprises the user.

### Why
"Forward-clean" patch. v1.12.0 introduced the YAML handoff schema but predated htmlify's `type:` discriminator. As long as this skill keeps producing handoffs without `type:`, htmlify's legacy-fallback path must stay actively maintained. One-line template change moves new handoffs to the first-class path; the fallback freezes into "pre-existing files only" instead of "needed for current tooling".

### Backwards compatibility
**No breaking changes.** Pre-2.1.1 handoff.md files (with or without YAML) keep working — htmlify's classifier still recognizes them, and CLAUDE.md "Session continuity" still parses them. The change only affects what *new* writes look like.

### Notes for users
- **No action required.** Next time `/superpowers-gstack:context-handoff` runs, the written handoff.md will include `type: handoff` automatically.
- If the Safari auto-open is undesired, disable the htmlify PostToolUse hook by removing the relevant block from `~/.claude/settings.json` (the `scripts/setup-htmlify-hook.sh` installer is opt-in to begin with).

## [2.1.0] - 2026-05-16

### Changed
- **Liquid Glass design system.** Hele `companion.css` skrevet om til en 2026-software-aestethic: gradient-mesh canvas, glass-overflater med edge-highlights (`backdrop-filter: blur(28px) saturate(160%)` + `mask-composite` for kantgradient), "knashe" accent-palette (cyan/magenta/violet/amber/emerald/terracotta), SF Pro + Charter typografi-paring, monospace tabular-numerics. Lys og mørk mode med forskjellige aksent-intensiteter (varme i lys, neon i mørk).
- **Dual-theme + toggle.** Ny pill-knapp i øvre høyre hjørne bytter mellom light/dark/system. Valget persistert i localStorage; OS-preferanse er default. Bootstrap-script kjører før paint så ingen flash-of-wrong-theme.
- **Flowchart-layout med kontekst-bevisste regler:**
  - ≤4-noders lineær chain → LR stacked (full bredde øverst, notes under)
  - =5-noders lineær chain → TB single column, eksakt 50/50 med notes-kolonne
  - ≥6-noders lineær chain → TB split i to sub-kolonner med 90°-cornered connector mellom, eksakt 2/3 (diagram) + 1/3 (notes)
  - Trær / DAG → TB regular side-by-side
  - Eksplisitt `orientation` i plan respekteres alltid
- **Connector-kurve for split-chains:** L+C+L+C+L-mønster (rett ned → 90° bend → rett opp midt mellom kolonnene → 90° bend → rett ned), ikke én sammenhengende S-Bezier. Cubic-Bezier-kontrollpunkter plassert utenfor endepunktene så tangentene er strikt vertikale ved exit/entry.
- **`notes`-felt på `FlowchartData`** — optional markdown rendres som side-kolonne (TB) eller stacked-rad (LR). Lar plan-LLM-en putte budsjett, legend, kontekst som ellers ville gått tapt når en seksjon erstattes av et diagram-treatment.
- **Større flowchart-nodes** (165×50 TB / 165×72 LR), større font (15.5px i bokser, 13px på edges), generøs ranksep (55 TB / 70 LR) — labels får luft.
- **Notes-kolonne stretches** til full kortets indre-høyde (`align-items: stretch` på flex), så border-left ikke avsluttes der tekst slutter.
- **Safari som distraksjonsfri viewer:** `--open` bruker `osascript` til å lukke alle eksisterende Safari-vinduer før den åpner companion-HTML-en. Default-nettleseren røres ikke.

### Fixed
- Dashboard-test bruker nå mer presis assertion (sjekker escaped form, ikke fravær av `<script>` overhodet) siden shell-en legitimat embedder theme-bootstrap-script.

## [2.0.0] - 2026-05-16

### Added
- **`/htmlify` v2 — plan-driven rich rendering.** HTML-companions er ikke lenger "penere MD med strukturerte cards" — de er informative plansjer med 9 visuelle komponenter. Nytt `--plan <plan.json>` flagg laster en rendering plan generert av Claude Code i samme sesjon (Max-plan compute — **ingen Anthropic API-kall**). Plan'en definerer per-seksjon treatment (overstyrer default cards) og global feedback-panel.
- **9 nye komponenter:** `comparison-matrix` (side-ved-side A/B/C med Recommended-highlight), `flowchart-svg` (dagre-layout inline SVG, kobler-fri), `pullquote` (editorial highlight), `callout-box` (info/warn/insight/danger varianter), `stats-bar` (metrics + trend), `two-column` (compare/contrast), `expandable` (pure-CSS `<details>` toggle), `diff-card` (før/etter kode), `feedback-panel` (interaktiv).
- **Interaktiv feedback-panel.** Pure-CSS reveals + en `<script>`-tag som gjør én ting: gather → JSON → clipboard. Premise-sjekkbokser, approach-radioer, custom-spørsmål, og obligatorisk fritekst-kommentar. "Copy feedback as prompt"-knapp → bruker limer inn i neste sesjon. Fallback til `<pre>` med tekst-seleksjon hvis Clipboard API ikke er tilgjengelig. **Ingen server.**
- **Plan-skjema med graceful degradation.** `PlanSchema` (zod, `.passthrough()`) validerer struktur. Hvis plan-fil mangler/feil-formatert: stderr-advarsel + fall tilbake til v1-template-rendering. Manglende H2 i MD = plan-seksjon rendres som ny seksjon.
- **Shared `renderPlannedSections` helper** i `helpers/planWiring.ts`. Tre renderere (designDoc, handoff, plan) bruker samme logikk: kanonisk seksjons-liste først (overstyrt av plan hvis matchende heading), så plan-introduserte seksjoner, så pullquotes interleaved.
- **64 nye tester** (138 totalt opp fra 74) — per-komponent (HTML-escape, edge cases, missing data), plan-wiring (case-tolerant matching, pullquote placement, default fallback), feedback-panel (clipboard script, fallback, escaped labels).

### Why
v1 løste "vibe-codere leser ikke MD" ved å gi penere MD-presentasjon. Men brukeren påpekte at v1 fortsatt er prosa: "veldig mye av poenget med å vise vibe coderen html i stedet for md er fordi med html blir det mulig å lage pene informative plansjer/grafiske fremstillinger." v2 leverer det: når plan'en sier "Approaches Considered = comparison-matrix" får brukeren et lesbart 3-koloners visuelt rasterkort i stedet for en bullet-liste; "Architecture = flowchart-svg" gir et statisk SVG-diagram. Den separate **Phase 1 planning-modellen** (LLM-en lager planen i Claude Code-sesjonen, ikke i CLI'en) holder kostnad nede (Max-plan compute = inkludert) og innholdsforståelse oppe (planen er på model-side, ikke deterministic regex-baserte heuristikker).

### Changed
- **`--open` bruker Safari som dedikert leser.** Tidligere åpnet `--open` HTML-en i brukerens default-nettleser (via `open <url>`). Nå brukes Safari spesifikt — alle eksisterende Safari-vinduer lukkes først, og HTML-en åpnes som eneste vindu. Bakgrunn: brukeren bruker normalt ikke Safari, så Safari blir en distraksjonsfri visning som ikke forstyrres av andre tabs/sesjoner. Default-nettleseren røres ikke. Implementert via `osascript`; fallback til `open` hvis AppleScript feiler.

### Backwards compatibility
**Ingen breaking changes for eksisterende brukere.** Uten `--plan` er output identisk med v1.13.x. Hookken kjører som før (uten plan-generering). `--open` skifter nettleser (Safari) men semantikk er den samme — HTML vises. Major version-bump skyldes scope og dybde av nye features, ikke trukne kontrakter.

### Notes for users
- **Bruke v2 manuelt:** I Claude Code, be om "lag en rik HTML av X.md". Claude leser MD-en, identifiserer visuelle muligheter, skriver `plan.json` til en temp-fil, og kjører `htmlify --plan plan.json`.
- **Auto-trigger via hook** bruker fortsatt v1 (uten --plan). v2-rendering er opt-in inntil videre — vi kan eventuelt utvide hooken når plan-generering blir billigere/raskere.
- **Plan-skjema og treatment-katalogen** er dokumentert i `skills/htmlify/SKILL.md` under "Enhanced rendering (v2 — plan-driven layout)".
- **First-run deps oppdatert:** `cd "$SKILL_DIR" && bun install` (dagre lagt til som ny dependency for flowchart-layout).
- **Eksisterende plugin-installasjoner:** etter upgrade, kjør `bun install` i cache-katalogen for å hente `dagre`. Wrapperen rapporterer exit 5 + nøyaktig kommando hvis ikke gjort.

### Engineering process
Brainstormet via `/office-hours`. Phase A (PlanSchema + CLI flag + plumbing) → Phase B (9 komponenter med tester) → Phase C (feedback-panel + clipboard) → Phase D (docs). Hver fase bisectable-committet. Critical constraint underveis: bruker er på Max-plan → ingen API-kall — plan-generering må skje in-session, ikke i CLI'en.

## [1.13.2] - 2026-05-16

### Added
- **`/htmlify` lagt til i model-routing-tabellen** med Haiku-anbefaling (Claude Code), `qwen3.6-mlx-8bit` (Pi local-only) og Haiku (Pi hybrid). Begrunnelse: CLI'en selv er deterministic — orchestrator-Claude trenger bare å invoke bash-kommandoen, ingen reasoning om innholdet. Klassisk Haiku-territorium, samsvar med `/verification-before-completion`, `/using-git-worktrees`, `/macos-e2e-scaffold`, `/context-handoff`.
- **`/htmlify` lagt til i `setup-routing` og `adapt` evaluation tables** så generert CLAUDE.md inkluderer skill'en for nye prosjekter. Anbefales for alle prosjekter — verdien er proporsjonal med hvor mange MD-artefakter prosjektet produserer.

### Notes for users
- **Re-kjør `/superpowers-gstack:adapt`** på eksisterende prosjekter for å få htmlify-rad lagt til i CLAUDE.md.
- Ingen breaking changes. Funksjonalitet samme som v1.13.1; dette er kun routing-metadata + skill-katalog-oppdatering.

## [1.13.1] - 2026-05-16

### Added
- **Self-locating `bin/htmlify` wrapper.** Nytt skript `skills/htmlify/bin/htmlify` resolverer skill-katalogen fra sin egen path og kan kjøres fra hvilken som helst cwd uten å vite den faktiske installasjons-stien. Sjekker at `bun` og `node_modules/` finnes, printer presis feilmelding (exit 5) hvis ikke.

### Fixed
- **SKILL.md ga feile install-paths.** v1.13.0-instruksjonene refererte til repo-relative stier (`skills/htmlify/...`, `./scripts/setup-htmlify-hook.sh`) som ikke fungerer når plugin'et er installert via marketplace (faktisk path er `~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/<version>/...`). Oppdatert til å bruke `$SKILL_DIR/bin/htmlify`-mønsteret som Claude Code resolver automatisk via "Base directory for this skill"-header. CHANGELOG-notater for v1.13.0 hadde samme feil.
- **First-run-setup steg klargjort.** En `bun install` per install-lokasjon er nødvendig — det gjelder både utviklingsrepo og plugin-cache. Wrapperen forteller deg den eksakte kommandoen.

### Notes for users
- **Eksisterende v1.13.0-installasjoner:** Etter oppdatering til v1.13.1, kjør én gang:
  ```bash
  cd ~/.claude/plugins/cache/paretofilm-plugins/superpowers-gstack/1.13.1/skills/htmlify && bun install
  ```
- **Hook-installer-stien er nå tydeligere** i SKILL.md. Hook'en self-lokaliserer fortsatt — installasjon fra cache-stien fungerer.

## [1.13.0] - 2026-05-16

### Added
- **`/htmlify` skill — HTML companions for MD artefacter.** Generates visually elegant, pedagogical HTML next to MD-artefakter fra skills som `/office-hours`, `/autoplan`, `/plan-eng-review`, `/context-handoff` osv. Stilles ut for vibe-codere som ikke orker å lese verbose MD-output. Auto-opens i nettleser via `--open` flag (macOS). Per-katalog aggregert dashboard via `htmlify dashboard <dir>` viser alle companions sortert by mtime med drilldown-lenker. Tre frontmatter-typer støttes: `design-doc`, `handoff`, `plan` (med backward-compat for legacy handoff.md filer uten `type:`-felt). Generic fallback for MD-er uten kjent frontmatter — får banner + full marked-rendret body. Implementert som Bun + TypeScript, kjørt via `bun run skills/htmlify/src/cli.ts <args>`. Output legges i `<dir>/.superpowers-html/<name>.html` (sibling-katalog, auto-gitignored).
- **PostToolUse-hook for auto-trigger.** Et nytt hook-skript (`scripts/htmlify-posttooluse.sh`) fyrer automatisk når Claude Code skriver/redigerer en MD-fil som matcher artefakt-mønstre (`*-design-*.md`, `handoff.md`, `*-plan-*.md`, alt under `.gstack/projects/`). Loop-prevention på `.superpowers-html/*.html` skrives. Installeres én gang via `./scripts/setup-htmlify-hook.sh`.

### Why
Et tilbakevendende mønster: skills produserer verbose MD-output (design-docs, plans, retro-rapporter) som blir liggende ulest. Stockholm-syndrome med MD-format som vinner mot AI-skifte til HTML for menneske-konsum (Thariq Shihipar / Anthropic, mai 2026). Brukerens egen `~/.claude/CLAUDE.md` mandater allerede HTML+MD parallelt for kreative/strategiske artefakter — denne featuren implementerer det mønsteret INNE I plugin'et selv. Companion-HTML er pedagogisk scaffold som viser PROSESSEN (premisser challenged, alternativer vurdert, beslutninger), POSISJONEN (workflow-state), og STATEN (DRAFT/APPROVED/SHIPPED, tasks-progress). YAML-frontmatter er kontrakten (rir på v1.12.0-mønsteret); zod-skjemaer med `.passthrough()` håndterer schema-evolusjon tolerant.

### Notes for users
- **Aktiver auto-trigger:** Kjør `./scripts/setup-htmlify-hook.sh` én gang. Hook'en legges til `~/.claude/settings.json` som PostToolUse-hook. Restart Claude Code etter installasjon.
- **Manuell bruk:** `bun run skills/htmlify/src/cli.ts <path-to-md>` produserer HTML, `--open` åpner i nettleser, `htmlify dashboard <dir>` genererer aggregat-side. Se `skills/htmlify/SKILL.md` for full referanse.
- **First-run deps:** `cd skills/htmlify && bun install` (committed lockfile garanterer reproduserbare bygg). Hook'en feiler silently hvis deps ikke er installert — ingen auto-bootstrap som muterer brukerens checkout.
- **Visual design enforcement:** Stilark `skills/htmlify/styles/companion.css` følger brukerens design-system (Charter/Georgia typografi, varm copper-aksent, hairline borders, asymmetrisk grid). Hardkodet palette — ingen lilla gradient.
- **74 unit-tester følger med** (`cd skills/htmlify && bun test`) — full path coverage på schemas, helpers, renderers, dashboard, output, hook-filter.
- **Cross-platform `--open` kommer i V1.5** (Linux `xdg-open`, WSL `wslview`). V1 er macOS-only by design.
- **`/adapt`-retrofit-integrasjon** (scanning av eksisterende MDer i et prosjekt) er deferred til V1.5.

### Engineering process
Designet via `/office-hours` (builder mode), reviewet via `/plan-eng-review` med 3 reviewer-iterasjoner og uavhengig Codex kald-lesning. Codex utfordret V1-abstraksjonen som førte til scope-expansion: hook og dashboard ble flyttet fra V1.1/V2 inn i V1. Også 7 hardening-fixes anvendt (handoff schema disambiguation, body sanitization via DOMPurify, URL-encoding via `pathToFileURL`, exit-code taxonomy, Levenshtein typo-detection på `type:`-felt). Design-doc + test-plan lever i `~/.gstack/projects/Paretofilm-superpowers-gstack/`.

## [1.12.0] - 2026-05-15

### Changed
- **`context-handoff` schema upgrade — YAML frontmatter + prose hybrid.** `docs/superpowers/handoff.md` now starts with a YAML block carrying machine-parseable fields: `session_end`, `branch`, `commit_at_handoff`, `mode`, `active_task`, `status`, `completed`, `remaining`, `files_in_flight`, `env` (venv/dev_server/test_cmd), and `next_step`. Prose sections below remain for human context (decisions, files modified, plan progress, blockers).
- **Stable task-ID convention** — `<feature-slug>-<n>` (e.g. `auth-rewrite-3`). IDs never renumber; the slug makes them grep-able across handoff history, plan files, and commit messages.
- **`next_step` discipline** — must be one sentence with a concrete verb and (where possible) `file:line` anchor. Vague resumption text ("continue work on auth") is no longer acceptable.
- **`CLAUDE.md` "Session continuity" section** updated to read structured YAML fields. Quotes `next_step` verbatim, names the `active_task`, and surfaces `env` so commands work immediately on resume. Falls back to prose parsing for pre-1.12.0 handoffs.
- **Auto-mode marker migrated to YAML.** New writes use `mode: auto` in YAML; the legacy `## Mode: auto` Markdown marker is still recognized on read for backwards compatibility.

### Why
Phase 1 → Phase 2 handoff was the weakest link in the workflow: prose-only handoffs forced re-parsing on every session start, and "next step" was often too vague to act on without re-reading the whole file. Structured fields let the SessionStart hook restore env automatically, and stable task IDs make it possible to grep across sessions for what happened to a given piece of work. Considered full integration with `acai.sh` (ACIDs) but rejected as too heavy and too immature (v0.0.8) for the actual problem — this is the lighter, reversible alternative.

### Notes for users
- **Existing handoff.md files keep working** — pre-1.12.0 prose-only format is read as-is, then converted to YAML+prose on next write.
- **No action required** unless you've customized the handoff schema yourself. Re-run `/superpowers-gstack:adapt` is NOT needed — `context-handoff` is a self-contained skill.
- Test plan: use on the next project for one week. Iterate on the schema (add/remove YAML fields) or revert based on actual friction.

## [1.11.2] - 2026-05-13

### Changed
- **VERSIONS.md sync** — bumped GStack v1.26.2.0 → v1.34.1.0. Eight upstream point releases scanned; no skills renamed or removed.
- **Three new gstack skills added to `setup-routing` and `adapt` evaluation tables** (upstream additions between v1.26.3.0 and v1.34.1.0):
  - `/sync-gbrain` — keeps gbrain current with the repo's code and refreshes CLAUDE.md search guidance (added next to `/setup-gbrain`).
  - `/scrape` — pulls data from a web page; prototypes a flow via `$B` primitives and returns JSON (added next to `/browse`).
  - `/skillify` — codifies the most recent successful `/scrape` flow into a permanent browser-skill so subsequent calls run in ~200ms.
- `adapt` skill version marker bumped to 1.11.2. `adapt` will now inform users on `1.11.1` or earlier that the three new skill rows are part of the adaptation.

### Notes for users
- **Re-run `/superpowers-gstack:adapt` to pick up the three new skills** if you have an existing CLAUDE.md generated by this plugin. The skill detects the older version marker and adds the new rows without touching the rest of the file.
- Other gstack changes between v1.26.3.0 and v1.34.1.0 are internal (browse-server embedder API, update-check semver guard, signal-handler cleanup, `gbrain code-def/refs/callers/callees`, Conductor worktree leak fix, plan-skill MCP `AskUserQuestion` fallback). None affect this plugin's routing or skill list.

## [1.11.1] - 2026-05-13

### Changed
- **VERSIONS.md sync** — bumped GStack v1.15.0.0 (dde5510) → v1.26.2.0 (30fe6bb) and Claude Code 2.1.119 → 2.1.126. Per auto-update PR #14's own analysis: no new skills added, removed, or renamed upstream. Routing tables and Model Routing recommendations remain accurate. Upstream changes are internal fixes (e.g. `/plan-eng-review` STOP gates, `/office-hours` Phase 4, `AskUserQuestion` MCP fallback, `/ship` PR-title prefix, cross-platform hardening, gbrain manifests, browser-skills runtime, tunnel allowlist expansion).

### Notes for users
- No functional changes in this plugin. v1.11.1 closes auto-update PR #14 / issue #15 which collided with the manually-shipped v1.11.0 model routing release (same pattern as v1.8.1 / PR #9 collision documented in earlier CHANGELOG). The salvageable VERSIONS.md update from PR #14 is incorporated here.

## [1.11.0] - 2026-05-12

### Added
- **Per-skill model routing recommendations** — `setup-routing` and `adapt` now emit a `### Model Routing` subsection inside `## Skill routing` in the generated CLAUDE.md. The table maps each relevant skill (and key per-phase steps within multi-phase skills like `/superpowers:test-driven-development`, `/superpowers:subagent-driven-development`, `/superpowers:systematic-debugging`, `/qa`, `/ship`) to its recommended model per harness.
- **Multi-harness columns** — routing recommendations are column-wise: **Claude Code** (`opus`/`sonnet`/`haiku`), **Pi (local-only)** (concrete Qwen3.6 model IDs from `~/.pi/agent/models.json`), and **Pi (hybrid)** (local default + cloud fallback for heavy reasoning). Orchestrator-Claude identifies its own runtime and picks the matching column. No hook required for the routing itself.
- **Swift-implementation specialization** — Swift/SwiftUI implementation phases route to `qwen3.6-27b-optiQ-SFT` (Stage 12.4 SFT adapter on Qwen3.6-27B-OptiQ-4bit, served via `mlx-sft` provider) when running in Pi. Other implementation phases route to the daily-driver `qwen3.6-mlx-8bit`.
- **Canonical routing table** — `skills/setup-routing/model-routing.md` holds the full table referenced by both `setup-routing` and `adapt`. Includes phase-level sub-tables for the five multi-phase skills, model identifier documentation (Anthropic + Pi), and explicit caveats.
- **`setup-routing` Step 2 question 10** — new always-asked question: which harness(es) will run this project (Claude Code / Pi local-only / Pi hybrid). Determines which columns appear in the generated CLAUDE.md.
- **`setup-routing` Step 5.5** — new step: present model routing recommendations to the user for confirmation before generating CLAUDE.md. Mirrors the existing skill-selection-confirmation pattern in Step 5.
- **`adapt` Step 2 follow-up** — mirrors the harness question. Step 4 gap-detection now includes `### Model Routing` presence check. Step 5 inserts/updates the section without touching other CLAUDE.md content.

### Changed
- `setup-routing` and `adapt` version markers bumped to 1.11.0.
- Generated CLAUDE.md target size: 60-100 lines → 80-130 lines (Model Routing adds ~15-30 lines depending on how many skills and harnesses are selected). The ~150-line compliance budget still applies.

### Notes for users
- **⚠️ Marketplace users:** v1.11.0 adds a new `### Model Routing` subsection to generated CLAUDE.md by default. The **Pi columns reference local-model identifiers specific to the plugin author's setup** (Qwen3.6 variants in `~/.pi/agent/models.json`) — most users won't have those models installed. **To opt out**, answer "None — skip model routing entirely" when prompted for harness in `/setup-routing` (Step 2 Q10) or `/adapt` (Step 2 follow-up). Existing CLAUDE.md files are untouched until you re-run one of those skills.
- **Advisory, not enforced.** Orchestrator-Claude may ignore the recommendations — this v0.1 ships as guidance only. Hook-based enforcement (and online-vs-offline auto-detection for the Pi hybrid column) is deferred to v1.12.0.
- **Empirical validation pending.** The Pi columns lean on the user's `project_vibe_coding_config.md` memory entry (Tier 1/2/3 benchmark from 2026-05-02/03 Quern test). The Anthropic columns are sensible defaults based on each skill's dominant cognitive demand, not benchmarked across this exact skill set.
- **Existing projects:** re-run `/superpowers-gstack:adapt` to pick up Model Routing. The skill detects the older version marker and adds the section without touching other content.
- **Pi model availability:** routing references concrete model IDs (e.g. `qwen3.6-mlx-8bit`, `qwen3.6-27b-optiQ-SFT`). Confirm coverage with `cat ~/.pi/agent/models.json | grep '"id"'` before relying on Pi-column recommendations.
- **Design rationale:** full design doc with scope decisions, known gaps, and future work is at `docs/superpowers/specs/2026-05-12-model-routing-design.md`.

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
