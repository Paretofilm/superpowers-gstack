# Model Routing Table — v0.1 (advisory)

> **Status:** v0.1, advisory only. Recommendations below are sensible defaults derived from each skill's dominant cognitive demand, not empirically benchmarked across this exact skill set. Treat them as guidance — override per project when you have evidence.
>
> **Audience:** This file is read by `setup-routing` and `adapt` skills. It is also rendered (or referenced) in generated `CLAUDE.md` files so orchestrator-Claude can consult it when dispatching subagents.
>
> **Last updated:** plugin v1.11.0

## How orchestrator-Claude should use this

You may be running under different harnesses. Identify your runtime, then use the matching column:

- **Claude Code** — your system prompt names you "Claude Code". Use the **Claude Code** column.
- **Pi (local-only)** — `~/.pi/agent/AGENTS.md` says "You are running in pi coding agent". No network calls allowed (offline, or by policy). Use the **Pi (local-only)** column.
- **Pi (hybrid)** — same Pi harness, but cloud calls are permitted for tasks where local quality is insufficient. Use the **Pi (hybrid)** column.

**Important distinction by harness:**

- **In Claude Code**, you have an `Agent` tool and can dispatch subagents with `model:` parameter. When you dispatch a subagent to execute one of the skills below, pass the recommended model from the **Claude Code** column. Multi-phase entries (e.g. `/superpowers:test-driven-development`) become per-phase subagent calls.
- **In Pi (either mode)**, there is no subagent dispatch — Pi runs a single process per session (see `~/.pi/agent/AGENTS.md`: "No `TodoWrite` tool... No web fetch/search, no MCP"). The Pi columns therefore guide *which Pi provider/model the user should start the session with* for a given task. Switching mid-session requires `/new` and restarting Pi with a different `--provider` / `--model`. For multi-phase skills in Pi, pick the model best matched to the *dominant phase* you expect to spend most time in.

If your runtime doesn't match any column (e.g. Cursor, opencode, Codex CLI, custom harness), default to the **Claude Code** column and treat the recommendations as advisory — these harnesses typically support multi-model dispatch via their own mechanisms (opencode's agent-types, Cursor's model picker, etc.).

## Model identifiers used

**Claude Code column:**
- `opus` — `claude-opus-4-7` (heavy reasoning, novel synthesis, strategic challenge)
- `sonnet` — `claude-sonnet-4-6` (structured engineering, code review, planning)
- `haiku` — `claude-haiku-4-5` (mechanical, templated, deterministic)

**Pi columns** — friendly aliases mapped to actual provider+id from `~/.pi/agent/models.json`. When invoking Pi, use the `--provider` and `--model` flags that match the alias:

| Alias used in tables below      | Provider in models.json | `id` field (use with `--model`)                       | Notes |
|----------------------------------|-------------------------|--------------------------------------------------------|-------|
| `qwen3.6-mlx-8bit`               | `mlx-local`             | `qwen3.6-mlx-8bit`                                     | Daily driver. MoE 35B-A3B (~3B active), 8-bit. Tier 1 default in `project_vibe_coding_config.md`. |
| `qwen3.6-35b-a3b-4bit-dwq`       | `mlx-local`             | `qwen3.6-35b-a3b-4bit-dwq`                             | Stronger reasoning. 4-bit DWQ, +28% tok/s vs 8-bit per 2026-04-30 benchmark. |
| `qwen3.6-27b-optiQ-SFT`          | `mlx-sft`               | `/Users/kjetilge/models/qwen3.6-27b-optiQ-4bit`        | **Swift specialist.** Base = Qwen3.6-27B-OptiQ-4bit + Stage 12.4 SFT LoRA adapter. Served on port 8081, distinct provider — must start `scripts/start-mlx-server.sh` first. **Use for Swift implementation tasks specifically.** |
| `gemma-4-26b-a4b-it-8bit`        | `mlx-local`             | `gemma-4-26b-a4b-it-8bit`                              | opencode driver, Tier 2 architecture. **Note:** degenerates in Pi (repetitive template loop) — do NOT route Pi skills to it. Listed only for completeness. |

The path-form `id` for the SFT model is intentional (mlx-lm.server loads the local model directory). When passing `model:` to a Pi API call, use the exact `id` from the table above, not the alias.

## Routing table

### Superpowers skills

| Skill                                          | Claude Code | Pi (local-only)          | Pi (hybrid)              |
|------------------------------------------------|-------------|--------------------------|--------------------------|
| `/superpowers:brainstorming`                   | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/superpowers:writing-plans`                   | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/superpowers:writing-skills`                  | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/superpowers:executing-plans`                 | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/superpowers:subagent-driven-development`     | see phases  | see phases               | see phases               |
| `/superpowers:dispatching-parallel-agents`     | see phases  | see phases               | see phases               |
| `/superpowers:test-driven-development`         | see phases  | see phases               | see phases               |
| `/superpowers:systematic-debugging`            | see phases  | see phases               | see phases               |
| `/superpowers:verification-before-completion`  | haiku       | qwen3.6-mlx-8bit         | haiku                    |
| `/superpowers:requesting-code-review`          | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/superpowers:receiving-code-review`           | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/superpowers:finishing-a-development-branch`  | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/superpowers:using-git-worktrees`             | haiku       | qwen3.6-mlx-8bit         | haiku                    |
| `/superpowers:using-superpowers`               | haiku       | qwen3.6-mlx-8bit         | haiku                    |

### GStack skills — Phase 1 (Planning)

| Skill                  | Claude Code | Pi (local-only)          | Pi (hybrid)              |
|------------------------|-------------|--------------------------|--------------------------|
| `/office-hours`        | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/plan-ceo-review`     | **opus**    | qwen3.6-35b-a3b-4bit-dwq | **opus**                 |
| `/plan-eng-review`     | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/plan-design-review`  | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/plan-devex-review`   | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/design-consultation` | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/design-shotgun`      | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/autoplan`            | (chained)   | (chained)                | (chained)                |
| `/plan-tune`           | haiku       | qwen3.6-mlx-8bit         | haiku                    |

### GStack skills — Phase 3 (Review & QA)

| Skill            | Claude Code | Pi (local-only)          | Pi (hybrid)              |
|------------------|-------------|--------------------------|--------------------------|
| `/review`        | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/qa`            | see phases  | see phases               | see phases               |
| `/qa-only`       | sonnet      | sonnet (req. browser)    | sonnet                   |
| `/cso`           | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/design-review` | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| `/design-html`   | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |
| `/devex-review`  | sonnet      | sonnet (req. live test)  | sonnet                   |
| `/investigate`   | sonnet      | qwen3.6-35b-a3b-4bit-dwq | sonnet                   |

### GStack skills — Phase 4 (Ship & Monitor)

| Skill                | Claude Code | Pi (local-only)  | Pi (hybrid) |
|----------------------|-------------|------------------|-------------|
| `/ship`              | see phases  | see phases       | see phases  |
| `/land-and-deploy`   | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/canary`            | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/landing-report`    | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/setup-deploy`      | sonnet      | qwen3.6-mlx-8bit | sonnet      |
| `/document-release`  | sonnet      | qwen3.6-mlx-8bit | sonnet      |
| `/retro`             | sonnet      | qwen3.6-mlx-8bit | sonnet      |
| `/learn`             | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/setup-gbrain`      | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/health`            | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/make-pdf`          | haiku       | qwen3.6-mlx-8bit | haiku       |

### GStack skills — Utility

| Skill                      | Claude Code | Pi (local-only)  | Pi (hybrid) |
|----------------------------|-------------|------------------|-------------|
| `/careful`                 | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/freeze`                  | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/unfreeze`                | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/guard`                   | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/browse`                  | haiku       | (no Pi support)  | haiku       |
| `/open-gstack-browser`     | haiku       | (no Pi support)  | haiku       |
| `/pair-agent`              | haiku       | (no Pi support)  | haiku       |
| `/setup-browser-cookies`   | haiku       | (no Pi support)  | haiku       |
| `/context-handoff`         | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/context-save`            | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/context-restore`         | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/benchmark`               | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/benchmark-models`        | haiku       | qwen3.6-mlx-8bit | haiku       |
| `/codex`                   | (delegated) | (delegated)      | (delegated) |

### Plugin-internal skills (superpowers-gstack)

| Skill                          | Claude Code | Pi (local-only)          | Pi (hybrid) |
|--------------------------------|-------------|--------------------------|-------------|
| `/superpowers-gstack:setup-routing` | sonnet | qwen3.6-35b-a3b-4bit-dwq | sonnet      |
| `/superpowers-gstack:adapt`         | sonnet | qwen3.6-35b-a3b-4bit-dwq | sonnet      |
| `/superpowers-gstack:pitfall-verification` | sonnet | qwen3.6-mlx-8bit | sonnet |
| `/superpowers-gstack:quality-review`       | sonnet | qwen3.6-mlx-8bit | sonnet |
| `/superpowers-gstack:macos-native-review`  | sonnet | sonnet (req. web) | sonnet |
| `/superpowers-gstack:macos-e2e-scaffold`   | haiku  | qwen3.6-mlx-8bit | haiku  |
| `/superpowers-gstack:context-handoff`      | haiku  | qwen3.6-mlx-8bit | haiku  |

## Phase-level routing (for "see phases" entries above)

### `/superpowers:test-driven-development`

| Phase                                   | Claude Code | Pi (local-only)          | Pi (hybrid)              |
|-----------------------------------------|-------------|--------------------------|--------------------------|
| Write failing test                      | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| Implement minimum (**Swift/SwiftUI**)   | sonnet      | **qwen3.6-27b-optiQ-SFT**| **qwen3.6-27b-optiQ-SFT**|
| Implement minimum (non-Swift)           | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| Refactor                                | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| Run tests + parse failures              | haiku       | qwen3.6-mlx-8bit         | haiku                    |

### `/superpowers:subagent-driven-development` & `/superpowers:dispatching-parallel-agents`

| Phase                       | Claude Code | Pi (local-only)  | Pi (hybrid) |
|-----------------------------|-------------|------------------|-------------|
| Orchestrator (this session) | (current)   | (current)        | (current)   |
| Per-task subagent           | per-task    | per-task         | per-task    |

Subagent model is determined by the *task type* the subagent is performing. Look up the appropriate row above for that task. The orchestrator stays on whichever model the session was started with.

### `/superpowers:systematic-debugging`

| Phase                          | Claude Code | Pi (local-only)          | Pi (hybrid)              |
|--------------------------------|-------------|--------------------------|--------------------------|
| Investigate (gather evidence)  | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| Hypothesize (novel/ambiguous)  | opus        | qwen3.6-35b-a3b-4bit-dwq | opus                     |
| Hypothesize (well-scoped)      | sonnet      | qwen3.6-mlx-8bit         | sonnet                   |
| Verify hypothesis              | haiku       | qwen3.6-mlx-8bit         | haiku                    |
| Implement fix                  | (use TDD row)| (use TDD row)           | (use TDD row)            |

### `/qa`

| Phase                          | Claude Code | Pi (local-only)       | Pi (hybrid)              |
|--------------------------------|-------------|------------------------|--------------------------|
| Navigate + screenshot          | haiku       | (no Pi browser support)| haiku                    |
| Triage bugs (severity, repro)  | sonnet      | (no Pi browser support)| sonnet                   |
| Write fix (Swift)              | sonnet      | qwen3.6-27b-optiQ-SFT  | qwen3.6-27b-optiQ-SFT    |
| Write fix (non-Swift)          | sonnet      | qwen3.6-mlx-8bit       | sonnet                   |

### `/ship`

| Phase                       | Claude Code | Pi (local-only)  | Pi (hybrid) |
|-----------------------------|-------------|------------------|-------------|
| Detect base branch          | haiku       | qwen3.6-mlx-8bit | haiku       |
| Run tests                   | haiku       | qwen3.6-mlx-8bit | haiku       |
| Review diff vs base         | sonnet      | qwen3.6-mlx-8bit | sonnet      |
| Bump VERSION + CHANGELOG    | haiku       | qwen3.6-mlx-8bit | haiku       |
| Write commit message        | sonnet      | qwen3.6-mlx-8bit | sonnet      |
| Push + create PR            | haiku       | qwen3.6-mlx-8bit | haiku       |
| Write PR description        | sonnet      | qwen3.6-mlx-8bit | sonnet      |

## Caveats

1. **Advisory, not enforced.** Orchestrator-Claude may ignore these recommendations. A future v1.12.0 hook could enforce per-phase routing at subagent-dispatch time.
2. **Empirically untested for this exact skill × model matrix.** The Pi-column recommendations lean on empirical evidence in `~/.claude/projects/-Users-kjetilge/memory/project_vibe_coding_config.md` (for the daily-driver tiers) and `~/Developer/modeltesting/quern/RECOMMENDATION.md` (for benchmark data). The Anthropic-column recommendations are sensible defaults based on each skill's cognitive demand profile, not benchmarked.
3. **Pi-column assumes models are running.** If the recommended Pi model is not loaded, fall back to: (a) any running Pi model with similar reasoning capacity, or (b) the Claude Code column (hybrid mode only).
4. **Swift specialist routing assumes the SFT adapter is loaded.** If `mlx-sft` provider is not running, the Swift rows fall back to `qwen3.6-mlx-8bit` for local-only or `sonnet` for hybrid.
5. **Cost vs latency tradeoff:** these recommendations optimize for capability-per-cost, not latency. Local models on Apple Silicon can be slower than cloud calls — if you're in Pi (hybrid) and want max speed for a phase, the hybrid column already biases toward cloud for non-trivial reasoning.
