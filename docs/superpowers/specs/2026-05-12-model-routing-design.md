# Per-skill model routing — design rationale (v0.1 / plugin v1.11.0)

**Status:** Shipped as v1.11.0 advisory routing. Empirically untested across the exact skill × model matrix. Future iterations may add empirical validation, hook enforcement, and online/offline auto-detection.

**Audience:** Maintainers extending the routing logic. Marketplace users wanting to understand or disable the feature. Future-me debugging why a routing decision was made.

---

## 1. Why this exists

### 1.1 The user's empirical foundation

Before this feature was scoped, the user had spent a full day (2026-05-02/03) running Quern-benchmark on seven local oMLX models × three task types (brainstorm/plan/implement). Results documented in `~/Developer/modeltesting/quern/RECOMMENDATION.md` and crystallized into a memory entry at `~/.claude/projects/-Users-kjetilge/memory/project_vibe_coding_config.md` — an empirically verified 3-tier workflow:

| Tier | Use case | Stack | Score |
|---|---|---|---|
| 1 | Daily vibe coding (snappy) | Pi + qwen3.6-mlx-8bit + cclsp | 3.3 |
| 2 | Heavier architecture | opencode + Gemma 26B | 3.86 |
| 3 | Cloud fallback | Kimi K2.6 → DeepSeek V3.2 → Sonnet | — |

This was working but **manually dispatched** — different CLI commands for different task types. The user wanted to codify it so superpowers-gstack workflows would automatically route to the right model.

### 1.2 The ChatGPT conversations that informed this

Three external advisor conversations directly informed the v1.11.0 scope (referenced in chat history, summarized here for the resuming developer):

- **"Gstack for swiftui" (2026-05-06)** — Established that superpowers-gstack already has routing infrastructure (`setup-routing` skill generates project-tailored CLAUDE.md). Suggested a SwiftUI-overlay axis (rules around SF Symbols, swift-format, XCTest), which is **separate from model routing** but uses the same generator.
- **"Swift coding finetuning" (2026-05-09)** — Argued that skills should be **distilled** for small local models (200-500 token rules instead of 10K-30K passive skills) and that conditional skill loading + RAG via CLI is the right architecture. Established that the user prefers Pi for context-frugality.
- **Same conversation, follow-up** — Established that Pi explicitly does NOT support MCP/subagents, but can use `fastmcp list/call` via bash as a bridge. This shaped the "Pi has no subagent dispatch" framing in the routing table.

### 1.3 What the existing model-routing-auditor plugin does NOT solve

The user has a separate plugin at `~/Developer/claude-plugins/model-routing-auditor/` that classifies entire skills with Sonnet and writes a global registry. It's complementary but different scope:

- `model-routing-auditor`: per-skill classification, compile-time, global registry
- `superpowers-gstack v1.11.0`: per-phase recommendation within a skill, runtime, project-tailored CLAUDE.md

Both can coexist. A future v0.2 of either could merge them.

### 1.4 The core insight

gstack/superpowers skills are **explicitly phase-structured** (brainstorm → write-tests → implement → review → verify → ship). Each phase has different cognitive demand. In a typical gstack workflow run, an estimated 60-75% of phases are mechanical work that doesn't need Opus — but today they all run on whichever model the orchestrator session started with.

Per-phase routing is the natural way to capture this efficiency gain. The routing table is the spec.

---

## 2. Design decisions

Captured at scoping time, with rationale. If future-me disagrees, the rationale here lets you judge whether the original argument still holds.

### 2.1 Anthropic-only? No — multi-harness

Initial scope was Anthropic-only (opus/sonnet/haiku) to keep the table universal. User pushed back: "we must include when local models should be used. I think when I work in Pi I likely use either only local model or combine local model with cloud model."

Decision: three columns — **Claude Code**, **Pi (local-only)**, **Pi (hybrid)**. Orchestrator self-identifies via system prompt content and picks its column.

Trade-off accepted: Pi-column recommendations are user-specific (depend on which models exist in their `~/.pi/agent/models.json`). Plugin distribution to other marketplace users means those users see a column referencing models they don't have. Mitigation: explicit alias→provider+id mapping table, plus opt-out (see §3.2 below).

### 2.2 Granularity — per-skill, with phase overrides for 5 cases

Decision: full per-fase routing only for the five obviously multi-phase skills:
- `/superpowers:test-driven-development`
- `/superpowers:subagent-driven-development` (+ `dispatching-parallel-agents`)
- `/superpowers:systematic-debugging`
- `/qa`
- `/ship`

All other skills get a single recommendation. Rationale: 90% of the value, 30% of the maintenance burden. Phase boundaries are clear in those five; ambiguous in most others.

### 2.3 Friendly aliases for Pi models

Pi models in `models.json` use file paths as `id` fields (e.g. `/Users/kjetilge/models/qwen3.6-27b-optiQ-4bit`). Putting raw paths in a routing table is unreadable. Decision: use friendly aliases (`qwen3.6-27b-optiQ-SFT`) with an explicit mapping table at the top of `model-routing.md`.

**Caught during pitfall verification round 1** that orchestrator passing the alias directly to the Pi API would fail — the alias→id mapping is critical.

### 2.4 Advisory, not enforced

Routing is advisory. Orchestrator-Claude reads the table and chooses to follow it (or not). No hook enforcement in v1.11.0.

Same caveat applies to the existing project-type routing in `setup-routing` (ChatGPT flagged this as feedback point #3 on 2026-05-06: "routing is advisory, not enforced"). v1.11.0 doesn't fix that — it just adds another advisory layer.

Hook enforcement is v1.12.0 candidate (see §4.2).

### 2.5 File layout — own file, not duplicated inline

The existing routing tables in `setup-routing/SKILL.md` and `adapt/SKILL.md` are duplicated inline with a "Keep in sync" comment. For the much larger model-routing table (3 columns × ~50 rows + 5 phase sub-tables), duplication would be unwieldy.

Decision: canonical table in `skills/setup-routing/model-routing.md`, referenced by both skills via Read tool. First case of "shared reference file" in this plugin — sets precedent for future v2 refactor that could similarly extract the project-type routing tables.

### 2.6 Hook deferred

User explicitly raised the question: "maybe a hook can inform which environment it's in." Decision: defer to v1.12.0.

Reason: orchestrator-Claude already knows its harness via system prompt content (Claude Code's prompt says "Claude Code"; Pi's `AGENTS.md` says "running in pi coding agent"). The hook would only add value for:
- Telemetry (count routing decisions, measure savings)
- Auto-detecting online vs offline for the Pi hybrid column
- Setting env vars for subagent dispatch

These are real but not blocking for MVP. v1.12.0 is the natural slot.

---

## 3. Scope: in and out

### 3.1 In scope for v1.11.0

- Per-skill model recommendations across 3 harness columns
- Per-phase overrides for 5 multi-phase skills
- Friendly alias → actual provider+id mapping for Pi models
- Generated CLAUDE.md gets a new `### Model Routing` subsection
- `setup-routing` flow asks which harness(es) — Step 2 Q10 + Step 5.5 confirmation step
- `adapt` flow has matching follow-up question + gap detection + insertion logic
- Caveats explicitly documented in both `model-routing.md` and generated CLAUDE.md
- Fallbacks for: missing `model-routing.md`, unrecognized "Other" harness, empty harness answer, missing Pi providers (port 8081 SFT model)

### 3.2 Explicitly out of scope for v1.11.0

- **Hook enforcement.** Orchestrator-Claude is trusted to read and apply.
- **Empirical validation.** Recommendations are sensible defaults based on each skill's dominant cognitive demand, not benchmarked across the exact matrix. Pi columns lean on user's existing 3-tier vibe-coding-config benchmark (which used different tasks).
- **Online/offline auto-detection for Pi hybrid.** User picks the column manually.
- **Per-project routing overrides.** Table is plugin-wide. Project-specific deviations require hand-editing the generated CLAUDE.md after generation.
- **Non-Pi local harnesses.** Cursor with local models, opencode with local, Codex CLI — all default to Claude Code column.
- **Cost-savings reporting.** Can't measure "this run would have cost $X without routing".
- **Auto-update of Pi aliases when `models.json` changes.** Hard-coded list.

---

## 4. Known gaps and future work

Catalogued so the resuming developer doesn't have to re-derive them.

### 4.1 v1.12.0 candidates (logical next iteration)

- **Hook enforcement.** A `PreToolUse` hook on the `Agent` tool checks that the dispatched `model:` matches the recommended one for the task. Warning-only, with opt-out to hard-block. Addresses ChatGPT's feedback point #3 from 2026-05-06.
- **Online/offline auto-detection for Pi.** A `SessionStart` hook (Pi-side) detects network reachability and either: (a) writes an indicator file the skill reads, or (b) sets `$SUPERPOWERS_GSTACK_PI_MODE=local-only|hybrid`. Removes manual Q10 burden for Pi users.
- **Cost telemetry.** Log routing decisions to `~/.claude/superpowers-gstack/routing-log.jsonl`. `/retro` skill can summarize. Lets users measure if routing actually saves money.
- **Marketplace user disable command.** Currently disable happens during `/setup-routing` Step 5.5 or `/adapt` (answer "None" to harness question). v1.12.0 could add `/superpowers-gstack:disable-model-routing` as explicit one-liner. See §5.

### 4.2 v2 candidates (deeper architectural change)

- **Project-specific override file.** `<project>/.claude/model-routing-overlay.md` that adds/overrides rows. Similar to how `model-routing-auditor` plans per-project overlay.
- **Phase detection beyond "trust the orchestrator".** Currently the orchestrator must recognize "I am now in the implement phase of TDD" and pick the right row. A `PreToolUse` hook could detect phase from the call site (e.g. dispatched-by-skill-name) and inject the recommendation.
- **Merge with `model-routing-auditor`.** That plugin classifies whole skills via Sonnet at install time and writes a global registry. `superpowers-gstack v1.11.0` ships hand-curated per-phase recommendations. A merged v2 could: auditor produces the per-skill defaults, this plugin's table holds the per-phase overrides. Two tools, complementary scopes.

### 4.3 Maintenance burdens introduced

- **Routing table drift.** When upstream gstack or superpowers adds/renames skills, `model-routing.md` must be updated. No automation yet — same problem as the existing routing tables.
- **README mini-table consistency.** README has an abbreviated 6-row table for quick reference. If `model-routing.md` rows change, README can drift. Worth a CI check.
- **Pi alias hard-coding.** The four Pi aliases are hard-coded. When the user adds new local models to `models.json`, the routing table doesn't auto-discover them.

### 4.4 Things that should be measured before claiming success

ChatGPT's feedback point #5 from 2026-05-06 ("measure if workflow actually helps") applies even more here. Before v1.12.0 commits to hook enforcement:

1. Run one identical gstack workflow with and without routing enabled (e.g. "implement Feature X end-to-end"). Measure: total tokens consumed, cost, wall-clock time, output quality.
2. Run on at least 3 different feature types (UI feature, refactor, bug fix) to control for task variance.
3. Update `model-routing.md` recommendations based on what wins.

Without this, the table is "feels right" guidance — exactly the cycle ChatGPT flagged in the earlier review.

---

## 5. Marketplace user considerations

This plugin is distributed via `Paretofilm/claude-marketplace`. v1.11.0 is a non-trivial UX change for existing users.

### 5.1 What marketplace users see when they update

After `/plugin update superpowers-gstack`:

- Next `/setup-routing` invocation gains a new mandatory Q10 (harness selection)
- Next `/adapt` invocation asks the same question
- Generated CLAUDE.md gains a new `### Model Routing` subsection (~15-30 lines)
- The Pi columns reference Qwen3.6 model IDs that **most marketplace users do not have installed** (they're specific to the plugin author's setup)

### 5.2 How users opt out

Three explicit opt-out paths exist:

1. **At setup-routing/adapt time**: when prompted for harness in Q10 (setup-routing) or Step 2 follow-up (adapt), answer "None — skip model routing". The skill omits the `### Model Routing` section entirely.
2. **For projects already using v1.10.0 or earlier**: do nothing. The plugin only adds Model Routing on next `/setup-routing` or `/adapt` invocation. Existing CLAUDE.md files are untouched.
3. **Manual removal**: delete the `### Model Routing` subsection from any generated CLAUDE.md. Re-running `/adapt` will re-add it unless you opt out via #1.

### 5.3 Why default is opt-in-when-asked, not opt-out-by-default

Decision: ask the harness question always, but allow "None" answer that effectively disables.

Alternative considered: skip the section by default unless user explicitly requests it. Rejected because: discovery suffers — most users wouldn't know the feature exists. The opt-out option in the question itself is enough to respect users who don't want it.

### 5.4 Warning to add to README + CHANGELOG

Both files now include explicit notes that this is a new generated-output section, Pi columns are user-specific, and how to opt out. See "Notes for users" in CHANGELOG [1.11.0] and the new "Model Routing" subsection in README Quick Reference.

---

## 6. Cross-references

| Source | What's there |
|---|---|
| `skills/setup-routing/model-routing.md` | Canonical routing table + alias mapping |
| `skills/setup-routing/SKILL.md` | Flow that emits the routing table during setup |
| `skills/adapt/SKILL.md` | Flow that adds the routing table to existing projects |
| `CHANGELOG.md` [1.11.0] | User-facing release notes |
| `README.md` Quick Reference → Model Routing | Abbreviated table + opt-out instructions |
| `~/.claude/projects/-Users-kjetilge/memory/project_vibe_coding_config.md` | Empirical foundation (user's 3-tier benchmark) |
| `~/Developer/modeltesting/quern/RECOMMENDATION.md` | Raw Quern-benchmark data feeding the Pi columns |
| `~/Developer/claude-plugins/model-routing-auditor/` | Sibling plugin, complementary scope, not yet shipped |
