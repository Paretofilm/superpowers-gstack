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
