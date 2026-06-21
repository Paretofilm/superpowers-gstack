---
name: pitfall-verification
description: Use after completing any PRD, spec, plan, or code implementation — verifies that artifact-specific pitfalls (security, idempotency, integration contracts, edge cases, LLM output) do not apply before declaring work done. For substantive/ship-worthy changes this skill is a MULTI-MODEL orchestrator — it automatically chains Codex + a third model house + an adversarial synthesis after the self-pitfall rounds, with no separate invocation to remember.
---

# Pitfall verification

Use this skill after finishing any PRD, spec, plan, or code artifact — before declaring the work done. It is NOT a generic review. It is a targeted check that *typical pitfalls for this type of artifact, in this domain, do not apply here*.

Invoke with: `/superpowers-gstack:pitfall-verification`

## This skill is a multi-model orchestrator

For anything beyond a trivial change, one model is not enough — there is always more to find, and a single training distribution has fixed blind spots. So this skill does **not** stop at Claude's own pitfall pass. For **substantive / ship-worthy** changes it runs, as ONE automatic flow:

1. **Self-pitfall** (Claude, lens 1) — the rounds below, max 2.
2. **Codex** (lens 2) — `/codex review` on the patched artifact.
3. **Third model house** (lens 3) — `/superpowers-gstack:third-lens-review` on the patched artifact.
4. **Adversarial synthesis** — combine all findings, finding-is-real-until-refuted.

**Stages 2–4 run automatically. Do NOT stop after the self-pitfall rounds to ask the user whether to run Codex or the third lens — run them.** The whole point is that there is nothing extra to remember: invoking pitfall-verification on substantive work *is* the multi-model review. The only thing that skips stages 2–4 is the **trivial** tier (see "Tier gate" below) — a typo or doc fix gets the free self-pitfall pass and nothing else.

## When to invoke

Automatically after completing:

- A PRD, spec, or design document
- An implementation plan
- A code change (feature, refactor, bug fix)
- Output from `writing-specs`, `writing-plans`, `executing-plans`, `verification-before-completion`, or any GStack planning/review skill

Run **twice max**. Two rounds catch almost everything; a third round has sharply diminishing returns.

## Sequence

1. **Self-check first** (~30 seconds): placeholders, scope drift, internal consistency, ambiguity. This is the standard sanity pass. Fix anything obvious.
2. **Pitfall verification** (this skill): targeted check for the pitfalls below, adapted to the artifact type and domain.

Do not skip step 1 — self-check and pitfall verification are different lenses.

## Pitfall lists per artifact type

These are **starting points, not exhaustive checklists**. Always ask: *what typically goes wrong with this kind of artifact, in this specific domain?* Infer additional pitfalls from the actual code/spec under review.

### PRD

- Unclear user story or missing success metric
- Hidden stakeholder assumptions (who signs off? who blocks?)
- Unspecified non-functional requirements (perf, privacy, accessibility, i18n)
- Conflicting requirements across sections
- Missing failure modes (what if X is unavailable? what if load spikes?)
- Over-specification of solution vs under-specification of problem

### Spec / plan

- Ambiguous contracts — input/output types, error shapes, null semantics
- Uspecified edge cases (empty, max-size, concurrent, partial failure)
- Missing error states / recovery paths
- Hidden assumptions about call order, transactions, idempotency
- Signature drift: spec references functions/fields that do not exist in the code
- Assumed external API behavior that has not been verified

### Code

- **Security**: prompt injection, input sanitation, credential leakage, SSRF, path traversal, auth bypass
- **Idempotency**: side effects on retry, hidden state, ordering dependencies
- **Integration contracts**: field names, types, and signatures that actually match the code they call into (cross-check — do not assume)
- **Edge cases**: empty input, oversized input, Unicode, currencies, time zones, DST, negative numbers, leap years
- **LLM output**: markdown-wrapped JSON, unexpected JSON structure, hallucinated fields, schema drift
- **Concurrency**: race conditions, deadlocks, shared mutable state
- **Resource lifecycle**: leaked handles, unclosed connections, memory growth under load

## How to run the check

For each pitfall on the relevant list:

1. **State the pitfall** — one sentence.
2. **Locate the risk surface** — which function, field, section, or claim could be affected?
3. **Verify**, do not assume. Read the actual code/spec. Cross-check field names against the implementation. Test the edge case mentally with real values.
4. **Report**: *Not applicable* (with reason) / *Applicable and handled* (point to where) / *Applicable and not handled* (propose fix).

If a pitfall is not applicable to this domain, say so explicitly — do not silently skip it. Stating "N/A because this code never touches dates" is itself a verification signal.

## Domain inference

The lists above are *generic-LLM-common*. Real pitfalls are often domain-specific. Before the round, spend 15 seconds asking:

- What kind of system is this? (auth? payments? ETL? LLM pipeline? UI? infra?)
- What categories of bugs hit this kind of system most often?
- What did *past* bugs in this codebase/team look like? (check git log, CHANGELOG, incident notes if accessible)

Add those inferred pitfalls to the round before running.

## Output format

End the round with a compact verdict:

```
Pitfall verification (round N/2):
- [pitfall] → N/A | handled at file:line | NOT HANDLED — proposed fix
- ...

Verdict: CLEAN | ISSUES FOUND (see above)
```

If round 1 surfaces issues, fix them, then run round 2 on the patched artifact. If round 2 is clean, declare done. If round 2 still finds issues, surface them to the user — do not silently run round 3.

## Tier gate — which lenses run automatically

After the self-pitfall rounds, classify the change and run the rest of the chain **automatically** for its tier. Do not ask the user which lenses to run — the tier decides.

| Tier | What it is | Lenses (all automatic) |
|------|-----------|------------------------|
| **Trivial** | docs, typo, comment-only, test-only-coverage, WIP checkpoint | Self-pitfall only — stop here |
| **Ship-worthy** | bumps a version file, produces a CHANGELOG entry, `feat`/`fix`/`refactor` affecting runtime, or changes public contracts | Self-pitfall → **Codex** → synthesis |
| **+ High-stakes** | a ship-worthy change that *also* touches **architecture / real-time / security / public contracts / migration logic** | …→ **third model house** → synthesis |

In practice most substantive work is at least ship-worthy, so Codex runs by default — you no longer invoke it by hand. The third house adds itself on the high-stakes subset. Both fire **without a confirmation prompt**; cost is reported after each call, not gated before it.

## Stages 2–4 — external lenses + synthesis (automatic per tier)

Run on the **patched** artifact, in order — each later lens reads a cleaner surface.

### Stage 2 — Codex (ship-worthy and above)

Invoke `/codex review` on the patched artifact. Codex catches cross-file drift, concurrency contracts, and concrete run bugs (false timeouts, stale async-resume, double-acquire leaks) that self-review systematically misses. Fix what it finds. Run it automatically — do not ask first.

**Idempotency guard:** if `/codex review` has already been run on this exact patched artifact earlier in the current flow (e.g. an orchestrator like `autoimplement` runs `/review` + `/codex review` itself around this skill), do **not** re-run it — fold the existing Codex findings into the Stage 4 synthesis instead. The goal is one Codex pass per patched state, not one per skill that mentions Codex.

### Stage 3 — third model house (high-stakes only)

Invoke `/superpowers-gstack:third-lens-review` on the patched artifact. A different model house (different training distribution → different blind spots) finds architecture-level mistakes ("you never wired it together"), degraded-state bugs, and challenged assumptions the two Western houses both took for granted. It picks the model by artifact type (`--role architecture`/`sensitive`/`correctness`) and runs its own adversarial synthesis of the third-house output. Run it automatically for the high-stakes tier — do not ask first.

### Stage 4 — combined adversarial synthesis (mandatory whenever stage 2 or 3 ran)

Do not dump raw findings. Fold Codex + third-house results into one verdict, **adversarially**: an external finding is REAL until you explicitly refute it with a reason (this counters LLM-judge agreement bias — failure-detection drops to ~50% when a judge is conciliatory, worse when it is partly judging its own earlier work). Log each dropped finding with *why*. Treat cross-model disagreement as the signal, not noise — every disagreement ends in an explicit, reasoned decision. Cross-model agreement = high-confidence green, no action.

```
Multi-lens verdict (tier: <trivial|ship-worthy|high-stakes>):
- Lenses run: self-pitfall [+ Codex] [+ <third-house model id>]
- CONFIRMED (fix now): [P1/P2] <finding> — <file:line> → <fix> (survived refutation because …)
- DISAGREEMENT → DECISION: <finding> → <explicit reasoned call>
- DROPPED (with reason): <finding> → <over-strict | handled at file:line | wrong>
- Cost: $<sum from lens footers>
- Verdict: CLEAN | FIX-THEN-RECHECK | SURFACE-TO-USER
```

## Why two rounds

One round catches the obvious pitfalls. Round 2, run on the patched artifact, catches pitfalls that the fixes from round 1 introduced or exposed. Beyond that, returns drop fast and reviewer fatigue introduces noise.

## What this skill is NOT

- Not a security audit (narrower, adversarial, deeper)
- Not a code review of style or readability
- Not a test suite (does not execute code)
- Not a replacement for `verification-before-completion` (which checks *claims vs reality* for already-finished work — pitfall verification is upstream of that)

Use it as the *last check before handing off* — after implementation, before the user sees "done".
