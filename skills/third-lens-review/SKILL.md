---
name: third-lens-review
description: Use after Claude self-pitfall + Codex have reviewed a SHIP-WORTHY / architecture / real-time / security / contract change — runs a third (and optionally fourth) external model lens (OpenRouter for distant houses, the codex CLI for OpenAI) on the PATCHED artifact, then an adversarial synthesis. The third lens is a different model house (different training distribution → different blind spots) that finds what the first two took for granted. Not for trivial or standard changes.
---

# Third-lens review

The third lens in superpowers-gstack's multi-lens review. Lenses 1–2 are **Claude self-pitfall** (`pitfall-verification`) and **Codex** (`/codex review`). This skill adds **lens 3** — a different model *house* (different training distribution → different blind spots) reading the **already-patched** artifact (via OpenRouter for distant houses, or the `codex` CLI for the countersynthesis role) — followed by a mandatory **adversarial synthesis**.

Invoke with: `/superpowers-gstack:third-lens-review`

The governing principle (field-proven): **cross-model agreement = high confidence; cross-model disagreement = where the value is.** A third house finds architecture-level mistakes ("you never wired it together"), degraded-state bugs, and challenged core assumptions that two Western houses both took for granted — *even after they already fixed 14 issues*.

## When to invoke (tiering)

**Normally you do not invoke this skill by hand.** `pitfall-verification` is a multi-model orchestrator and calls this skill automatically as Stage 3 of its chain for **high-stakes** changes — so the third house fires as part of the standard verification flow, with nothing extra to remember. Invoke it directly only for an ad-hoc third-house read outside that flow.

This is **not** for every change. The lens count scales with stakes, and each added lens must add a *house* or a *role*, never another generalist:

| Change | Lenses |
|--------|--------|
| Trivial (docs, typo, rename) | Claude self-pitfall only |
| Ship-worthy (version bump / CHANGELOG / `feat`/`fix`/`refactor` / public contract) | Claude + Codex |
| **Ship-worthy AND architecture / real-time / security / contracts / migration-logic** | **Claude + Codex + this skill (third house)** |

If the change is not high-stakes, **do not run this skill** — it burns money and tokens for diminishing returns. The gate is owned by `pitfall-verification`'s tier table; this row mirrors it.

## Prerequisites

- **Order matters.** Run *after* self-pitfall (max 2 rounds) and *after* Codex, on the **patched** artifact. A cleaner artifact maximizes house-diversity value and avoids paying a third house to re-find what lens 1–2 already fixed.
- **OpenRouter key** in macOS Keychain (account `openrouter-api-key`), or env `OPENROUTER_API_KEY`. The script resolves it; never put the key on the command line.
- **Balance check** before a run: `python3 scripts/third-lens-review.py --check-credits`.

## Model routing (which third lens, by artifact type)

The script picks the lens by `--role`. `architecture` and `correctness` run via OpenRouter (ids verified 2026-06-21); `countersynthesis` runs via the `codex` CLI (subscription):

| `--role` | Model | House | Use when |
|----------|-------|-------|----------|
| `architecture` *(default)* | `z-ai/glm-5.2` | Zhipu | default 3rd lens — most distant distribution; OpenRouter |
| `correctness` | `deepseek/deepseek-v4-pro` | DeepSeek | correctness sniper; OpenRouter |
| `countersynthesis` | `codex` CLI | OpenAI | refutes Claude's dedup; via codex CLI (subscription, no per-call cost) |

The sensitive role and its fail-closed Western-infra guard were removed in 2.18.0 (work is not sensitive; default lens is GLM-5.2).

**Reasoning models:** GLM-5.2 and DeepSeek are reasoning models — they spend completion tokens *thinking* before answering. The script sends `reasoning.effort` (default `medium`; tune with `--effort low|medium|high`) and defaults `--max-tokens` to 16000 so reasoning does not exhaust the budget before the answer. If you see `finish_reason=length` / empty output, raise `--max-tokens` or lower `--effort`.

**Cost guardrail:** never use `*-pro` extended-reasoning tiers for routine review. At ~30k input tokens a run is well under $1; the default GLM run is ~$0.05. The only way to overspend is the wrong (extended-reasoning) model id.

## Sequence

1. **Confirm lens 1–2 are done** and the artifact is patched. If not, stop and finish them first.
2. **Pick the role** from the table (artifact type → `--role`).
3. **Run the script** on the patched artifact:
   ```bash
   # by files/globs:
   python3 scripts/third-lens-review.py --files "src/**/*.swift" --role architecture
   # or on the diff:
   python3 scripts/third-lens-review.py --diff --diff-base main --role architecture
   ```
   Tip: `--dry-run` first to see the cost estimate on a large artifact.
4. **Adversarial synthesis (Claude, mandatory).** Never dump the raw output and stop. Run a synthesis over it — see below.

## Step 4 — Adversarial synthesis (the part that makes the third lens worth it)

A third lens **without** synthesis is noise: a different-house model over-generalizes strictness (GLM especially), and its raw verdicts are not ship decisions. But the synthesis is itself an LLM-as-judge step, and LLM judges have a documented **agreement bias** (failure-detection rates as low as ~50%) — and here Claude is partly judging its *own* earlier findings. So the synthesis must be **adversarial, not conciliatory**:

- **Default: every third-lens finding is REAL until you explicitly refute it with a reason.** Do not drop a finding because it contradicts your earlier analysis — that is exactly the bias to fight.
- **Log each dropped finding with *why*** (over-strict for this domain? already handled at file:line? factually wrong?). A silent drop is indistinguishable from a missed bug.
- **Treat disagreement as the signal.** Every cross-model disagreement must end in an explicit, reasoned decision — not a smoothed-over average. (Field example: GLM's *wrong* "sample-accurate crossfade" finding forced the precise rule no lens had stated — *MIDI delivery needs sample precision; fade-envelope tolerates 20–50 ms*. The over-strict finding was the trigger for the right call.)
- **Agreement across houses = high-confidence green.** Where all lenses agree, no action needed; note it.
- **For the biggest changes only** (arch/RT/security): run a `--role countersynthesis` pass (via the codex CLI, subscription — no per-call cost) that *refutes Claude's dedup decisions*. Cheap insurance against bias bortrasjonalisering of a real finding.

### Synthesis output format

```
Third-lens synthesis (model: <id>, role: <role>):

CONFIRMED (fix now):
- [P1/P2] <finding> — <file:line> → <fix>. Refutation attempted, survived because <why>.

DISAGREEMENT → DECISION:
- <finding> — lens says X, our view is Y → DECISION: <explicit reasoned call>.

DROPPED (with reason):
- <finding> → dropped because <over-strict for domain | handled at file:line | factually wrong>.

CROSS-HOUSE AGREEMENT (high confidence, no action):
- <area all lenses agreed was sound>

Lens(es) run: Claude self-pitfall + Codex + <model id>[ + countersynthesis]
Cost: $<from script footer>
Verdict: CLEAN | FIX-THEN-RECHECK | SURFACE-TO-USER
```

Always present the raw output's key findings *and* the synthesis. Never the raw dump alone.

## What this skill is NOT

- Not for trivial or standard changes — tiering gates it. Running three houses on a typo is waste.
- Not a replacement for `pitfall-verification` or `/codex` — it is the **third** lens, after both.
- Not autonomous: the script fetches the lens; the *agent* owns the adversarial synthesis and the ship decision.

## Why a third lens (field evidence)

LiveSet Pro (2026-06-21): GLM-5.2 ran as lens 3 *after* Claude + Codex had already fixed 14 issues, and still found real new value — dead code the tested core was never wired into, a use-after-free under render, a silently-dropped scheduler overflow, a leaked late-arriving audio unit. Each lens caught what the other two missed; none was redundant. The mechanism is **training-distribution distance**, not raw model IQ — which is why the third lens is a *different house*, and why GLM (≈18 pts below Fable 5 on SWE-bench Pro) earns its place: it is the cheapest, most distribution-distant, whole-repo-in-context divergence finder available, and its over-strictness becomes useful friction once the synthesis is adversarial.
