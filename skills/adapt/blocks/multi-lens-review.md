## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v7 -->

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
