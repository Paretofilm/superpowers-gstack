# autoimplement v2.15 — explore `/ultrareview` as Step D review option

**Status:** Backlog (exploration needed before design)
**Filed:** 2026-05-28
**Source:** Claude Code 2.1.152 shipped; April-May 2026 features include `/ultrareview` as public research preview

---

## Context

Claude Code's April 2026 releases shipped `/ultrareview` — "bug-hunting agents running in the cloud" as a public research preview. autoimplement's per-phase Step D currently chains three reviews:

1. `/review` (gstack) — Claude single-inline PR review
2. `/superpowers-gstack:pitfall-verification` — Claude artifact-pitfall check
3. `/codex review` (OpenAI Codex CLI) — GPT cross-model adversarial

This backlog explores: should `/ultrareview` join Step D as a fourth option, or replace one of the existing reviews?

## Why this might be worth doing

The cross-model adversarial pattern in autoimplement v2.13.0+ catches bugs single-model review systematically misses. Empirical evidence from this plugin's own development: 4 of last 6 PRs landed bugs codex caught that Claude (`/review`, `/pitfall-verification`) missed. The value comes from **model diversity** (Claude vs GPT), not just from running more reviews.

But model diversity is one axis of adversarial value. **Mechanism diversity** is another:

- `/review` = single-inline Claude review of a diff
- `/pitfall-verification` = single-inline Claude check against a curated pitfall list
- `/codex review` = single-inline GPT review
- `/ultrareview` = **multi-agent CLOUD review** (different mechanism even though Claude-family)

Hypothesis worth testing: a multi-agent cloud review may catch a different bug class than single-inline reviews, even when both use the Claude model family. Multi-agent has parallel-search affordances (multiple agents probe different angles simultaneously) that single-inline does not.

## Open questions before designing

1. **Which model(s) does `/ultrareview` use?** Claude Opus 4.7? Sonnet? Mix? The cross-model value depends on this.
2. **What does `/ultrareview` cost per invocation?** It's cloud-billed (not Max-plan). For an autoimplement run with N phases, an extra `/ultrareview` per phase could be expensive.
3. **What is `/ultrareview`'s output contract?** Does it return findings classifiable into the 4-tier system (clean / advisory / blocking / severe)?
4. **Can `/ultrareview` be invoked from within a Skill's execution context?** Same nested-Skill concern that triggered the harness-probe discussion in autoimplement v1.
5. **Is `/ultrareview` available on Max plan or only on paid org-tier?** Affects who can use the resulting v2.15.

## Three candidate designs

### Design A: Additive — `/ultrareview` becomes a 4th step in chain

Step D becomes: `/review` → `/pitfall-verification` → `/codex review` → `/ultrareview`. All four classifications combined; STOP_POLICY interacts with each.

- **Pro:** Maximum adversarial coverage. Best chance of catching everything.
- **Con:** Most expensive. Doubles per-phase review time. May discover too many advisory findings that the user has to triage.

### Design B: Toggle — `/ultrareview` replaces `/codex review` if user prefers Claude-only

A clarification gate option: "Use OpenAI Codex (cross-model) or Anthropic ultrareview (cloud-multi-agent)?" Both are valid choices for the third review slot.

- **Pro:** User picks based on their plan/preference. Same chain depth as today.
- **Con:** Loses one axis of diversity. User who picks `/ultrareview` loses GPT cross-model coverage.

### Design C: Severity-tiered — `/ultrareview` runs only at risk gates

`/ultrareview` only runs at HIGH-severity gates (severe diff, security-touched code, pre-ship of skill itself). Lower-risk phases skip it.

- **Pro:** Cost-effective. Targets adversarial budget at highest-value points.
- **Con:** Adds complexity to Step D's branching logic. The severity-trigger heuristic is itself a thing that needs review.

## Trade-offs

| Axis | Add `/ultrareview` | Don't add |
|---|---|---|
| Cost per autoimplement run | Higher (cloud-billed) | Current |
| Bug catch rate (hypothesized) | Higher (mechanism diversity) | Current |
| Skill complexity | Higher (4-way chain) | Current |
| Skill version churn | New ship + audit trail rounds | None |
| Dependence on cloud availability | New external dep | None added |

## Decision criteria for ship / skip

**Ship if:**
- `/ultrareview` provably catches bug classes the current chain misses (run on past v2.13.x bugs as eval set)
- Cost per phase is < 2× current `/codex review` cost
- Available on Max plan OR Pro plan (broad user accessibility)
- Output classifiable into 4-tier system without major skill changes

**Skip / defer if:**
- `/ultrareview` only repeats findings the existing Claude chain (`/review` + `/pitfall`) already catches
- Cost is prohibitive for typical autoimplement use
- Org-tier only (limits user base)
- Output requires bespoke parsing that does not fit Step D's semantic-judgment model

## Suggested research steps before designing

1. Run `/ultrareview` manually on 3-5 past autoimplement PRs from this repo. Compare findings to what the existing chain caught. Score: novel findings / total findings.
2. Document cost per invocation (token usage × current cloud pricing).
3. Verify nested-skill invocation works from inside autoimplement's execution context (or document fallback to Agent-tool dispatch).
4. Test output classification: can a human (and Claude as orchestrator) easily map `/ultrareview` findings to clean / advisory / blocking / severe?

## Related learnings (durable, from /learn)

- `cross-model-adversarial-catches-structural-blindspots` — empirically validated value of Claude+GPT diversity
- `context-aware-finding-classification-in-orchestrator-chains` — how Step D classifies findings
- `automate-X-often-means-remove-friction-not-full-autonomy` — autoimplement's design intent is friction removal, not maximum review depth

## When this gets picked up

No urgent timeline. Pick up when:
- A user explicitly asks for stronger autoimplement review (signal that current chain has missed something), OR
- `/ultrareview` exits research preview to GA (more stable contract), OR
- This backlog item is referenced from another design discussion (signal that the question matters)

Until then, the current 3-step chain is sufficient based on accumulated evidence.
