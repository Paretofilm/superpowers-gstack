## Multi-lens review (ship-worthy changes) <!-- gstack-multi-lens-review-v4 -->

Substantive changes get multiple review lenses — different model houses, each catching what the others miss. **`pitfall-verification` orchestrates them automatically per tier — you do NOT invoke Codex or the third house by hand:**

1. **Self-check** (always, ~30 sec): placeholders, consistency, scope drift, ambiguity
2. **Self-pitfall** (always, max 2 rounds): `/superpowers-gstack:pitfall-verification` — domain-specific traps (security, idempotency, contracts, edge cases, LLM-output quirks)
3. **Codex** (auto on ship-worthy): `/codex review` — cross-file drift and concrete run bugs self-review misses
4. **Third house** (auto on high-stakes — architecture / real-time / security / contracts / migration-logic): `/superpowers-gstack:third-lens-review` — a *different model house* via OpenRouter, ending in an adversarial synthesis

Stages 3–4 fire automatically per tier with **no confirmation prompt**; trivial changes (docs/typo) get only the free self-pitfall pass. Cost is reported after each call, not gated before it.

### What counts as "ship-worthy"

**YES (run codex):**
- Commits that bump version files (`plugin.json`, `package.json`, `pyproject.toml`, etc.)
- Commits that produce CHANGELOG entries
- `feat:` / `fix:` / `refactor:` commits that affect runtime behavior
- Changes to public contracts (APIs, schemas, generated artifacts, file formats)

**NO (skip codex — it's overkill):**
- Pure docs/typo fixes
- Comment-only changes
- WIP commits (per Continuous Checkpoint mode)
- Test-only additions where coverage is the only change

### Why multiple lenses, not one

Self-review catches "is this artifact good?" Pitfall catches "what typically breaks in this domain?" Codex catches "what's inconsistent across the codebase that author was too close to see?". Different lenses see different things; running fewer leaves a known gap.

Dogfood evidence (2026-05-19 in superpowers-gstack repo): self-pitfall verification on v2.10.0 ran two rounds and caught 3 issues. After fixing those, `/codex review` caught a 4th — REPLACE-wording drift across 2 unrelated section blocks. Self-review missed it because the author was focused on the *new* section, not on cross-section consistency.

### Cost

- Self-check: free (~30 sec attention budget)
- Pitfall verification: free (LLM thought)
- Codex review: ~$0.05-0.20 per review + 30s-2min wall clock

Acceptable for ship-worthy work. Skip codex explicitly for trivial changes; don't run it on every commit or you'll burn budget on diminishing returns.

### Order matters

Run lenses in order: self → pitfall → codex → (ship-worthy arch/RT/security) third-house. Each pass fixes issues the previous one couldn't catch and reads a cleaner artifact. Running codex *before* pitfall wastes its tokens on issues a simpler pass would have surfaced first; running the third house before codex pays a third model to re-find what codex would have caught.

### Fourth lens: the third house (escalation)

The first three lenses are all self/Anthropic or OpenAI (Codex). For the highest-stakes changes, add a *different model house* — its value is **training-distribution distance**, not raw IQ: it sees architecture-level mistakes ("you never wired it together"), degraded-state bugs, and challenged assumptions the others took for granted.

- **Gate:** architecture, real-time, security, public contracts, or migration logic. Skip for trivial/standard changes.
- **Routing by `--role`** (`scripts/third-lens-review.py`): `architecture`=GLM-5.2 (default, OpenRouter); `correctness`=DeepSeek V4-Pro (OpenRouter); `countersynthesis`=OpenAI via the `codex` CLI (refutes the synthesis on the biggest changes). GLM/DeepSeek run on non-Western infra — do NOT send sensitive artifacts (auth/keys/health/finance) to this lens; keep those to the self + Codex lenses.
- **Cost:** ~$0.05/run (GLM), well under $1 even for a 4-house panel. Key in macOS Keychain `openrouter-api-key`.
- **Synthesis is mandatory and adversarial:** a third-house finding is real until explicitly refuted; disagreement is the signal, not noise. Never dump raw output. See the skill for the synthesis format.
