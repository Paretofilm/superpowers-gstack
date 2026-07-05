## Code reuse discipline (before writing) <!-- gstack-code-reuse-v1 -->

Before introducing a new reusable concept — a component, helper, model, type-alias, view-modifier, button-style, extension, hook, utility function — the agent MUST search the codebase for existing implementations first. This catches "context-bounded duplication": the agentic-coding failure mode where a subagent writes a new `EntityCard` without knowing one already exists one directory over.

This is *not* a DRY purity rule. The default stance is pragmatist: three or four similar lines is fine, premature abstraction is a real cost. The rule only fires when introducing something that could plausibly already exist.

### Scope — when to scan

Scan before writing:
- A new struct, class, or component with a domain-shared name (`Card`, `Item`, `Cell`, `Detail`, `Manager`, `Service`, `View`, `Modifier`, `Style`, etc.)
- A new helper function that smells like utility (`formatX`, `parseY`, `validateZ`, `serializeFoo`)
- A new extension, type-alias, ViewModifier, ButtonStyle (Swift) or hook, HOC, wrapper component (web)
- A new shared model / DTO / schema definition

Do NOT scan:
- Lines inside an existing function — that's refactoring, not new-concept introduction
- Inline closures / callbacks specific to one call-site
- Test helpers private to one test file
- One-off scripts not intended for reuse

### How to scan

1. **Grep for the bare concept name** (full-word, case-insensitive) — e.g. `EntityCard`, `formatDate`, `validateEmail`
2. **Glob for matching file paths** — `**/*Card*.swift`, `**/*card*.tsx`, `**/format*.py`
3. **Read** the matches that look related (don't skim — actually verify it's the same concept)
4. **Decide**: REUSE existing / EXTEND existing / WRITE NEW (and report which)

### Verbalize the scan

Before scaffolding the new code, narrate one line in chat (in whatever language the conversation is happening in):

> Checking whether we already have an existing `<concept>` …

Then report findings:

> Found `EntityCard` at `Views/EntityCard.swift:14` — extending it with `.compact` variant rather than writing new.

or:

> No matches for `EntityCard` or `*Card*.swift` — writing new.

This is **narration, not a stop.** Continue scaffolding immediately after reporting findings — do not wait for user input unless the user actively redirects. The narration is for transparency only; it does NOT add a new category to the "5 categories warrant stopping" rule in the Autonomy section above. If the user wants to redirect, they will; otherwise proceed.

This costs ~3 lines of chat per new concept. Worth it; the user gets a chance to see "actually, see `ItemCard` at line N" before the duplicate exists. Silence-first scanning is worse: when duplicates do happen, the user has no signal until /review catches them post-implementation.

### When dispatched as a subagent

When dispatching a subagent under `/superpowers:subagent-driven-development` or any Task-tool dispatch that will write code, include in the dispatch prompt:

> Before introducing new reusable concepts (components, helpers, models, extensions), search the codebase via Grep/Glob for existing implementations. If you find one, **use it or extend it** and continue with your delegated task — report what you reused. If you do not find one, scaffold new and report what you searched for. Escalate to the orchestrator ONLY if the reuse decision is genuinely ambiguous (e.g. the existing implementation almost-but-not-quite fits and adding a parameter would change its semantics for existing callers).

The subagent has narrower context than the orchestrator — this instruction transfers the scanning discipline across the dispatch boundary. Critically, the subagent must NOT stop with a recommendation after finding existing code; it must complete its delegated coding task using the found implementation, escalating only on genuine ambiguity.

### Pragmatist guardrails

- ❌ Do NOT pre-abstract. If two similar lines exist, leave them as two similar lines until a third one shows up.
- ❌ Do NOT refactor existing code unless the task explicitly asks for it. The scan reports existing implementations; it doesn't authorize touching them.
- ❌ Do NOT ask the user "should we be DRY about this?" — the answer is yes-but-pragmatist by default. Just scan first.

### Coverage at adjacent stages

Other skills already handle DRY at other stages — this rule fills the implementation-time gap:

- **`/plan-eng-review`** does pre-implementation reuse-scan at architecture time ("list existing code/flows that already partially solve sub-problems… whether the plan reuses them or unnecessarily rebuilds them"). When that scan has already run, this rule still applies during code-writing but should defer to plan-eng-review's findings for the high-level architecture decisions.
- **`/review` (gstack)** catches DRY violations post-implementation in the `maintainability` specialist (duplicated literal values, duplicated config/setup, DRY Violations checks). That's the last line of defense; this rule is meant to catch duplicates BEFORE they reach review so review can focus on substantive issues.

### Local override

If the user explicitly says "skip the reuse-check for this session" or "just write it, I know nothing similar exists", honor that override. The user has full-codebase context the agent may lack; their override is informed, not a violation. Do not re-litigate.
