## Model Routing

When dispatching a subagent (Claude Code `Agent` tool, `model:` parameter), pick its tier in two steps: (1) the skill's **base tier** below; (2) apply this project's **domain-sensitivity** modifier. On correctness-sensitive work the modifier wins — a "cheap coding" phase in a high-blast-radius domain is a false economy; the cheap correctness lever is multi-lens verification (`/pitfall-verification`), not a cheaper coder.

**This project's domain sensitivity: {{DOMAIN_SENSITIVITY}}** (how silently a subtle bug compounds).

**Tiers:** `fable` = claude-fable-5 (novel + long-horizon + not chunkable; ~2× Opus, safety-fallbacks to Opus for sec/bio/chem — never pay the premium there); `opus` = claude-opus-4-8 (heavy reasoning, high-blast-radius coding); `sonnet` = claude-sonnet-5 (structured engineering, contained-blast-radius coding with tests as the net; near-Opus at Sonnet cost); `haiku` = claude-haiku-4-5 (mechanical/deterministic).

**Modifier by sensitivity:**
- **very high / high** — floor coding at `opus` + mandatory `/pitfall-verification`; use `fable` only when the technique is *also* genuinely novel and not cleanly chunkable (scope it open-on-approach, bounded-on-deliverable).
- **medium** — base tier as-is (usually `sonnet`); tests catch most.
- **low** — base tier or one tier cheaper.

**Per-skill base tiers:** see the plugin's `model-routing.md` for the full table; the common ones — planning/review/engineering → `sonnet`, `/plan-ceo-review` → `opus`, mechanical/util/verification → `haiku`. `see phases` skills route per phase.

**Do NOT reach for `fable`** on planning, coding against a pinned spec, or verification — a precise `opus` spec turns long+ambiguous work into short+well-scoped chunks that Opus does cheaper. Verification ROI is orthogonal to coder tier: budget multi-lens on every ship-worthy change regardless of who wrote the code.
