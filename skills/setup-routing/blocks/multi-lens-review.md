## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v6 -->

Substantive changes get multiple review lenses — different model houses catch what the others miss. **`pitfall-verification` orchestrates them automatically per tier — never invoke Codex or the third house by hand:**

1. **Self-check** (always, ~30 sec): placeholders, consistency, scope drift, ambiguity
2. **Self-pitfall** (always, max 2 rounds): `/superpowers-gstack:pitfall-verification` — domain-specific traps
3. **Codex** (auto on ship-worthy): `/codex review` — cross-file drift and concrete run bugs self-review misses
4. **Third house** (auto on high-stakes: architecture / real-time / security / contracts / migration-logic): `/superpowers-gstack:third-lens-review` — a different model house, ending in an adversarial synthesis

Stages 3–4 fire per tier with **no confirmation prompt**; trivial changes (docs/typo) get only the free self-pitfall pass. Cost is reported after each call, not gated before it.

**The tier is computed, not guessed.** `scripts/classify-change.py` reads the change and prints a tier **floor** plus the resolved target (`--files` / `--diff --diff-base`, the same spelling `third-lens-review.py` takes). Escalate above the floor whenever you can justify it; never run a tier below it — `--assert-tier <tier>` exits non-zero on a downgrade and names the signals being skipped. If the script is missing or errors, treat the change as ship-worthy at minimum and say the floor was not computed. Left to self-assessment, the tier is decided by the model that just wrote the code, at the moment the cheapest answer is most tempting.

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
