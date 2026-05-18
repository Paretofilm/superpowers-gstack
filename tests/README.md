# Tests

End-to-end tests for `superpowers-gstack` plugin behaviors.

## Layout

```
tests/
├── README.md                  ← this file
├── run.sh                     ← entry point: bash tests/run.sh [--integration|--unit]
└── integration/
    └── test_track_aware_dispatch.sh   ← verifies track-aware routing dispatches correctly
```

Unit tests would live in `tests/unit/` when added. None exist yet — the plugin is mostly Markdown skill definitions, not executable code (htmlify has its own `skills/htmlify/tests/` Bun suite).

## Running

```bash
# All tests
bash tests/run.sh

# Integration only
bash tests/run.sh --integration

# Help
bash tests/run.sh --help
```

## Integration tests

Integration tests shell out to `claude --print` to verify real dispatch behavior — they catch bugs that "verify by inspection" can't (e.g., the LLM following or ignoring CLAUDE.md routing rules).

**Prerequisites:**

- Claude Code CLI installed (`claude` in PATH)
- `ANTHROPIC_API_KEY` env var set, OR an active Claude Code session with credentials in the OS keychain
- Network access to `api.anthropic.com`

**Cost & speed:**

- Each test case = one `claude --print` invocation ≈ 30-60 seconds and a few cents in tokens
- Each test caps spend at `$1.00` via `--max-budget-usd 1.00` (safety net, well under typical cost)
- Two cases per dispatch test = ~2 minutes wall-clock total

**Why integration over unit:** the dispatch logic lives in *generated CLAUDE.md text* interpreted by the LLM at runtime. Unit-testing that requires either mocking the LLM (which then doesn't test the actual dispatch) or running the LLM end-to-end (which is integration testing). Codex flagged this gap in the v1.0 swiftui-design-consultation spec — "Spec lines 651-663 acknowledge native projects can mis-dispatch to web. Plan smoke tests at lines 1854-1856 and 1894-1896 'verify by inspection' that the routing rules exist — but don't test actual dispatch behavior in a real session." This test suite closes that gap.

## What's tested

| Test | Cases | What it verifies |
|---|---|---|
| `test_track_aware_dispatch.sh` | 2 | track=ios fixture → LLM dispatches to `/superpowers-gstack:swiftui-design-consultation`; no marker → LLM dispatches to gstack's `/design-consultation`. Tests the routing rule that `setup-routing` and `adapt` emit. |

## What's NOT tested yet (deferred backlog)

- `/office-hours-track-aware` wrapper dispatch (intercepts `/office-hours`)
- `/context-handoff` write + restore cycle (YAML frontmatter survives `/clear`)
- `/htmlify` PostToolUse hook actually fires when `handoff.md` is written
- Other CLAUDE.md routing rules emitted by `setup-routing`

These would be additional `tests/integration/test_*.sh` files following the same pattern.

## CI

No CI integration yet. Running integration tests in CI requires `ANTHROPIC_API_KEY` as a repo secret and a willingness to spend on every PR. If/when that's set up, the natural entry is `bash tests/run.sh --integration` in a GitHub Actions workflow.
