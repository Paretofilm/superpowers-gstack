# Third-lens review: CLI/OpenRouter transport dispatch

**Date:** 2026-06-25
**Status:** Approved (design)
**Target version:** 2.18.0

## Problem

`scripts/third-lens-review.py` reaches every model house through OpenRouter (paid,
~$0.05/run). The user now subscribes to model CLIs (`agy` for Gemini, `codex` for
OpenAI/GPT, `claude` for Claude) and wants those reached via CLI instead of paying
OpenRouter for models already covered by a subscription. OpenRouter stays only for
**distant houses with no CLI** (GLM-5.2, DeepSeek V4-Pro).

Separately, the `sensitive` role (Gemini 3.1 Pro via OpenRouter, Western-infra
guarantee) is no longer needed — the user's work is not sensitive — and is removed.

## Goals

1. Route the `countersynthesis` role (OpenAI/GPT) through the `codex` CLI instead of
   OpenRouter `openai/gpt-5.5`.
2. Keep `architecture` (GLM-5.2) and `correctness` (DeepSeek V4-Pro) on OpenRouter —
   no CLI exists for those houses.
3. Remove the `sensitive` role and its fail-closed `--sensitive` guard entirely.
4. Preserve the synthesizer contract: identical `RAW OUTPUT` framing regardless of
   transport, so the orchestrating agent's adversarial synthesis is unaffected.

## Non-goals

- No `gemini` (agy) or `claude` CLI role added — kept minimal per user choice. The
  transport abstraction leaves room to add them later without rework.
- No change to OpenRouter pricing/usage/credits logic for the roles that stay on it.
- No change to how `pitfall-verification` invokes Stage 3.

## Architecture

### Transport abstraction

Each role resolves to a `(transport, target)` pair:

| Role | House | Transport | Target |
|------|-------|-----------|--------|
| `architecture` (default) | GLM-5.2 | `openrouter` | `z-ai/glm-5.2` |
| `correctness` | DeepSeek V4-Pro | `openrouter` | `deepseek/deepseek-v4-pro` |
| `countersynthesis` | GPT (OpenAI) | `cli` | `codex` |

`--model X` (explicit override) forces `transport=openrouter` with model id `X`,
unchanged from today (arbitrary ids are OpenRouter ids).

### Two backends behind one prompt-builder

`main()` builds `system_prompt` + `user_msg` and gathers content exactly as today,
then dispatches by transport:

- **`run_openrouter(system_prompt, user_msg, model, args, key)`** — the existing HTTP
  path, refactored out of `main()` into a function. Prints RAW OUTPUT + `[usage]`
  cost + `[balance]`.
- **`run_codex(system_prompt, user_msg, target, args)`** — new. Shells out to:
  ```
  codex exec --sandbox read-only --color never --skip-git-repo-check -o <tmpfile> -
  ```
  with `<system_prompt>\n\n<user_msg>` piped on **stdin** (`exec -` reads instructions
  from stdin). Stdin — not an argv arg — because a large diff would exceed ARG_MAX, and
  a piped stdin (no TTY) also prevents codex from blocking on an interactive
  trust/login/approval prompt. Reads the agent's final message from `<tmpfile>` (via
  `-o/--output-last-message`), prints it in the same
  `===== THIRD-LENS RAW OUTPUT (codex CLI) =====` framing. Reports
  `[usage] via codex CLI (subscription — no per-call cost)`. Uses a
  `tempfile.NamedTemporaryFile`; cleans up in a `finally`. The smoke test verifies `-o`
  returns the full review rather than a truncated summary.

### Why `read-only` sandbox + stdin-fed content

The artifact (diff or file contents) is fed to codex on stdin, so codex never needs to
touch the repo. `--sandbox read-only` is the safe floor (bounds any prompt-injection in
reviewed content to read-only actions); `--skip-git-repo-check` lets it run even when
invoked outside a git tree (mirrors the OpenRouter path's indifference to repo state).

## Removals

- `ROLE_MODELS["sensitive"]` entry.
- `--sensitive` argparse flag.
- `WESTERN_PREFIXES` constant and the fail-closed allowlist guard block in `main()`.
- Exit code 5 (sensitive-data routing violation) — removed from the docstring's exit
  table.
- The `--role sensitive` suggestion in the empty-content/guard error messages.

**Accepted tradeoff (user-approved 2026-06-25):** removing the fail-closed
`--sensitive` guard means there is no longer an in-code guardrail preventing sensitive
code from being sent to non-Western houses (GLM/DeepSeek, which are now the default).
This is acceptable because the user's work is not sensitive. If a sensitive use case
returns later, the guard must be reintroduced.

## Error handling

- `codex` not found / non-zero exit / empty output file → print a clear error to
  stderr and exit 4 (same class as an OpenRouter API failure), so the orchestrator
  treats a CLI failure like any transport failure.
- `codex` timeout → reuse the 600s ceiling; on `subprocess.TimeoutExpired` exit 4 with
  a "codex CLI timed out" message.
- `--check-credits` and `--dry-run` pricing are OpenRouter-specific. For a `cli`-role:
  - `--check-credits` still queries OpenRouter (it is about the OR balance) — unchanged.
  - `--dry-run` prints "Transport: codex CLI (subscription — no OpenRouter cost)" and
    the estimated input token count, but no `$` estimate.

## Testing (TDD)

`pytest`, stdlib `unittest.mock`, no network:

1. **Role→transport resolution** — `architecture`/`correctness` resolve to
   `openrouter`; `countersynthesis` resolves to `cli`/`codex`; `--model X` forces
   `openrouter`.
2. **codex invocation** — mock `subprocess.run`; assert `codex exec` is called with
   `--sandbox read-only`, `--color never`, `-o <file>`, and the prompt containing both
   system prompt and artifact. Simulate the output file and assert the RAW OUTPUT
   framing matches the OpenRouter path's framing byte-for-byte (minus the model label).
3. **codex failure** — non-zero exit / missing binary / empty output → exit 4.
4. **Removed `--sensitive`** — passing `--sensitive` exits 2 (argparse unknown flag).
5. **OpenRouter path unchanged** — existing OR tests still pass (regression guard).

## Follow-on edits (same change set)

- `skills/third-lens-review/SKILL.md` — role table + routing description (drop
  `sensitive`, point `countersynthesis` at codex CLI, note subscription cost).
- `CLAUDE.md` (project) line ~103 — third-lens routing bullet updated to the new map.
- `CHANGELOG.md` — entry under a new `2.18.0`.
- `.claude-plugin/plugin.json` — version bump `2.17.0` → `2.18.0`.

## Verification

Ship-worthy + touches the multi-model review contract → after implementation run
`pitfall-verification` (which auto-chains `/codex review` and, since this touches
review-contract logic, `third-lens-review` on the patched script), ending in
adversarial synthesis.
