# Third-lens CLI/OpenRouter Transport Dispatch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route the `countersynthesis` role through the `codex` CLI (subscription) while keeping `architecture`/`correctness` on OpenRouter, and remove the `sensitive` role and its fail-closed guard.

**Architecture:** Introduce a transport abstraction in `scripts/third-lens-review.py`: each role resolves to `(transport, target)`. `main()` builds the prompt once, then dispatches to one of two backends — `run_openrouter()` (existing HTTP) or `run_codex()` (subprocess to `codex exec`). Both print the identical `RAW OUTPUT` framing so the synthesizer contract is unchanged.

**Tech Stack:** Python 3 stdlib only (`urllib`, `json`, `subprocess`, `tempfile`). Tests: `pytest` (loads the hyphenated script via `importlib`). No new dependencies.

## Global Constraints

- Stdlib only — no `pip install` in the script (copied verbatim from spec design note).
- API key for OpenRouter roles: macOS Keychain account `openrouter-api-key`, env `OPENROUTER_API_KEY` fallback. Never pass keys on the command line.
- Identical RAW OUTPUT framing across transports: `===== THIRD-LENS RAW OUTPUT (<label>) =====` … `===== END RAW OUTPUT — agent must run adversarial synthesis over this =====`.
- Exit codes: `0` ok | `2` usage error | `3` auth/key error | `4` API/network/CLI failure | `6` nothing to review. (Exit `5` sensitive-routing is REMOVED.)
- Target plugin version: `2.18.0`.
- Unit tests live in `tests/unit/`; run via `bash tests/run.sh --unit`.

---

## File Structure

- Modify: `scripts/third-lens-review.py` — transport dispatch, `run_openrouter()`, `run_codex()`, role removal.
- Create: `tests/unit/test_third_lens_review.py` — pytest unit suite (importlib loader).
- Modify: `tests/run.sh` — wire `--unit` / `all` to run pytest on `tests/unit/`.
- Modify: `skills/third-lens-review/SKILL.md` — role table + routing + cost notes.
- Modify: `CLAUDE.md` — third-lens routing bullet (line ~103).
- Modify: `CHANGELOG.md` — `2.18.0` entry.
- Modify: `.claude-plugin/plugin.json` — version bump.

---

## Task 1: Test harness — load hyphenated script + wire `run.sh --unit`

**Files:**
- Create: `tests/unit/test_third_lens_review.py`
- Modify: `tests/run.sh:18-36` (case statement) and the run body

**Interfaces:**
- Produces: `load_tlr()` helper returning the imported module object (referred to as `tlr` in later tasks); `tlr.ROLE_SPEC`, `tlr.resolve_transport`, `tlr.run_codex`, `tlr.main` are exercised by Tasks 2-5.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_third_lens_review.py`:

```python
import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_tlr():
    """Load scripts/third-lens-review.py (hyphenated → not import-able normally)."""
    path = REPO_ROOT / "scripts" / "third-lens-review.py"
    spec = importlib.util.spec_from_file_location("third_lens_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tlr = load_tlr()


def test_module_loads_and_has_default_prompt():
    assert tlr.DEFAULT_PROMPT
    assert callable(tlr.main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: FAIL — `tests/unit/` does not exist yet / collection error, OR (once created) PASS. If the directory was just created and the script still has `DEFAULT_PROMPT`, this passes immediately; that is acceptable for a harness task (it proves the loader works). Treat a green bar here as success for Step 4.

- [ ] **Step 3: Wire `tests/run.sh` to run pytest on `tests/unit/`**

Replace the case statement block (`tests/run.sh`, the `case "$MODE" in` … `esac`) so each mode sets BOTH flags:

```bash
case "$MODE" in
  --integration|integration)
    RUN_INTEGRATION=true; RUN_UNIT=false
    ;;
  --unit|unit)
    RUN_INTEGRATION=false; RUN_UNIT=true
    ;;
  all|"")
    RUN_INTEGRATION=true; RUN_UNIT=true
    ;;
  -h|--help)
    sed -n '2,15p' "$0"
    exit 0
    ;;
  *)
    echo "Unknown mode: $MODE. See --help." >&2
    exit 2
    ;;
esac
```

Then add a unit block immediately after `FAIL=0` and BEFORE the integration block:

```bash
if [ "${RUN_UNIT:-false}" = "true" ]; then
  echo "=========================================="
  echo "Unit tests (pytest, fast, no API)"
  echo "=========================================="
  if pytest "$REPO_ROOT/tests/unit" -q; then
    echo ">>> unit: PASS"
  else
    echo ">>> unit: FAIL"
    FAIL=$((FAIL + 1))
  fi
fi
```

- [ ] **Step 4: Run via the repo entry point**

Run: `bash tests/run.sh --unit`
Expected: PASS — "unit: PASS" and "All test suites passed."

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_third_lens_review.py tests/run.sh
git commit -m "test(third-lens): add pytest unit harness + wire run.sh --unit"
```

---

## Task 2: Remove the `sensitive` role and fail-closed guard

**Files:**
- Modify: `scripts/third-lens-review.py` (docstring exit table, `ROLE_MODELS`, `WESTERN_PREFIXES`, `--sensitive` arg, guard block)
- Modify: `tests/unit/test_third_lens_review.py`

**Interfaces:**
- Consumes: `load_tlr()` from Task 1.
- Produces: `--sensitive` no longer exists; `sensitive` is not a valid `--role`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_third_lens_review.py`:

```python
import pytest


def test_sensitive_flag_is_removed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tlr", "--sensitive", "--files", "x"])
    with pytest.raises(SystemExit) as e:
        tlr.main()
    assert e.value.code == 2  # argparse rejects unknown flag


def test_sensitive_role_is_removed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tlr", "--role", "sensitive"])
    with pytest.raises(SystemExit) as e:
        tlr.main()
    assert e.value.code == 2  # invalid choice


def test_western_prefixes_gone():
    assert not hasattr(tlr, "WESTERN_PREFIXES")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: FAIL — `--sensitive` is currently accepted; `sensitive` is a valid role; `WESTERN_PREFIXES` exists.

- [ ] **Step 3: Remove the sensitive machinery**

In `scripts/third-lens-review.py`:

(a) Docstring exit table — delete the `| 5 sensitive-data routing violation` entry, leaving:
```python
Exit codes: 0 ok | 2 usage error | 3 auth/key error | 4 API/network/CLI failure
           | 6 nothing to review
```

(b) Delete the `"sensitive": "google/gemini-3.1-pro-preview", ...` line from `ROLE_MODELS` (this dict is fully replaced in Task 3, but remove the line now so this task stands alone).

(c) Delete the entire `WESTERN_PREFIXES = ( ... )` block and its preceding comment.

(d) Delete the `--sensitive` argparse line:
```python
ap.add_argument("--sensitive", action="store_true",
                help="refuse non-Western model houses (auth/keys/health/finance code)")
```

(e) Delete the guard block in `main()`:
```python
if args.sensitive and not any(model.startswith(p) for p in WESTERN_PREFIXES):
    eprint(...)
    eprint(...)
    sys.exit(5)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: PASS (all three new tests green).

- [ ] **Step 5: Commit**

```bash
git add scripts/third-lens-review.py tests/unit/test_third_lens_review.py
git commit -m "feat(third-lens): remove sensitive role and fail-closed guard"
```

---

## Task 3: Add `ROLE_SPEC` + `resolve_transport()`

**Files:**
- Modify: `scripts/third-lens-review.py`
- Modify: `tests/unit/test_third_lens_review.py`

**Interfaces:**
- Produces:
  - `ROLE_SPEC: dict[str, dict]` — keys `architecture`, `correctness`, `countersynthesis`; each value `{"transport": "openrouter"|"cli", "target": str}`.
  - `resolve_transport(role: str, model_override: str | None) -> tuple[str, str]` returning `(transport, target)`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_resolve_transport_openrouter_roles():
    assert tlr.resolve_transport("architecture", None) == ("openrouter", "z-ai/glm-5.2")
    assert tlr.resolve_transport("correctness", None) == ("openrouter", "deepseek/deepseek-v4-pro")


def test_resolve_transport_cli_role():
    assert tlr.resolve_transport("countersynthesis", None) == ("cli", "codex")


def test_model_override_forces_openrouter():
    assert tlr.resolve_transport("countersynthesis", "anthropic/claude-3.5") == \
        ("openrouter", "anthropic/claude-3.5")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: FAIL — `resolve_transport` / `ROLE_SPEC` not defined.

- [ ] **Step 3: Add `ROLE_SPEC` and `resolve_transport`**

Replace the (now sensitive-free) `ROLE_MODELS` dict with `ROLE_SPEC`:

```python
# Default lens-by-role transport + target.
# OpenRouter for distant houses with no CLI; the codex CLI for OpenAI (subscription).
ROLE_SPEC = {
    "architecture": {"transport": "openrouter", "target": "z-ai/glm-5.2"},
    "correctness": {"transport": "openrouter", "target": "deepseek/deepseek-v4-pro"},
    "countersynthesis": {"transport": "cli", "target": "codex"},
}


def resolve_transport(role, model_override):
    """Return (transport, target). An explicit --model always forces OpenRouter."""
    if model_override:
        return ("openrouter", model_override)
    spec = ROLE_SPEC[role]
    return (spec["transport"], spec["target"])
```

Update the `--role` argparse line to use `ROLE_SPEC`:
```python
ap.add_argument("--role", choices=list(ROLE_SPEC), default="architecture",
                help="pick lens by role (default architecture=GLM-5.2 on OpenRouter)")
```

(Leave `main()`'s body still referencing the old `model = args.model or ...` for now — Task 4 rewires it. To keep this task's script runnable, temporarily set `model = args.model or ROLE_SPEC[args.role]["target"]` where `model` was previously assigned.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/third-lens-review.py tests/unit/test_third_lens_review.py
git commit -m "feat(third-lens): add ROLE_SPEC + resolve_transport"
```

---

## Task 4: Extract `run_openrouter()` + dispatch wiring (CLI stubbed)

**Files:**
- Modify: `scripts/third-lens-review.py`
- Modify: `tests/unit/test_third_lens_review.py`

**Interfaces:**
- Consumes: `resolve_transport` (Task 3).
- Produces: `run_openrouter(system_prompt, user_msg, model, args, key) -> None` (prints RAW OUTPUT + usage + balance; calls `sys.exit(4)` on API failure). `main()` dispatches by transport; `cli` transport temporarily exits 4 with "not implemented" (replaced in Task 5).

- [ ] **Step 1: Write the failing test**

Append (this test mocks `http_json` and `get_pricing`/`get_credits` so no network is hit):

```python
def test_run_openrouter_prints_framing(monkeypatch, capsys):
    fake_resp = {
        "choices": [{"message": {"content": "P2 finding here"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.01},
    }
    monkeypatch.setattr(tlr, "http_json", lambda *a, **k: fake_resp)
    monkeypatch.setattr(tlr, "get_pricing", lambda *a, **k: (1e-6, 2e-6))
    monkeypatch.setattr(tlr, "get_credits", lambda *a, **k: 4.47)

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = False
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.2", Args(), "fakekey")
    out = capsys.readouterr().out
    assert "===== THIRD-LENS RAW OUTPUT (z-ai/glm-5.2) =====" in out
    assert "P2 finding here" in out
    assert "END RAW OUTPUT" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_third_lens_review.py::test_run_openrouter_prints_framing -q`
Expected: FAIL — `run_openrouter` not defined.

- [ ] **Step 3: Extract `run_openrouter` and rewire `main()`**

Move the block currently in `main()` from the `# rough pre-flight token estimate` line through the `[balance]` print into a new function. The function owns dry-run handling for the OpenRouter path:

```python
def run_openrouter(system_prompt, user_msg, model, args, key):
    est_in = (len(system_prompt) + len(user_msg)) // 4
    p_in, p_out = get_pricing(key, model)
    if args.dry_run:
        print(f"Model: {model}")
        print(f"Estimated input tokens: ~{est_in:,}")
        if p_in is not None:
            est_cost = est_in * p_in + args.max_tokens * p_out
            print(f"Estimated max cost: ~${est_cost:.4f} "
                  f"(in ${p_in*1e6:.2f}/Mtok, out ${p_out*1e6:.2f}/Mtok, "
                  f"assuming full {args.max_tokens} output tokens)")
        else:
            print("Pricing unavailable for this model id — verify it exists on OpenRouter.")
        return

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": args.max_tokens,
        "reasoning": {"effort": args.effort},
    }
    resp = http_json("POST", "/chat/completions", key, payload=payload, timeout=600)

    choices = resp.get("choices") or []
    if not choices:
        eprint(f"ERROR: no choices in response: {json.dumps(resp)[:500]}")
        sys.exit(4)
    choice = choices[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    finish = choice.get("finish_reason")

    if not text.strip():
        if finish == "length":
            eprint("ERROR: model hit the token cap before emitting an answer "
                   "(all budget spent on reasoning). Retry with a higher --max-tokens "
                   "(e.g. 24000) or a lower --effort (e.g. low).")
        elif msg.get("refusal"):
            eprint(f"ERROR: model refused: {msg.get('refusal')}")
        else:
            eprint(f"ERROR: model returned empty content (finish_reason={finish}).")
        sys.exit(4)

    print(f"===== THIRD-LENS RAW OUTPUT ({model}) =====\n")
    print(text.rstrip())
    if finish == "length":
        print("\n[!] OUTPUT TRUNCATED (finish_reason=length) — raise --max-tokens to get the full review.")
    print("\n===== END RAW OUTPUT — agent must run adversarial synthesis over this =====")

    usage = resp.get("usage") or {}
    tin = usage.get("prompt_tokens")
    tout = usage.get("completion_tokens")
    cost = usage.get("cost")
    if cost is None and tin is not None and tout is not None and p_in is not None:
        cost = tin * p_in + tout * p_out
    cost_str = f"${cost:.4f}" if isinstance(cost, (int, float)) else "unavailable"
    if tin is not None:
        out_str = f"{tout:,}" if tout is not None else "?"
        print(f"\n[usage] in={tin:,} out={out_str} tok | cost={cost_str} | model={model}")
    bal = get_credits(key)
    if bal is not None:
        print(f"[balance] OpenRouter ${bal:.2f} remaining")
```

Rewrite the tail of `main()` (everything after `system_prompt`/`user_msg` are built) to dispatch:

```python
    transport, target = resolve_transport(args.role, args.model)

    content = gather_content(args)
    if not content.strip():
        eprint("ERROR: nothing to review (empty diff / no files / empty stdin).")
        sys.exit(6)

    system_prompt = DEFAULT_PROMPT + (f"\n\nExtra instructions:\n{args.prompt}" if args.prompt else "")
    user_msg = f"Review the following artifact:\n\n{content}"

    if transport == "openrouter":
        run_openrouter(system_prompt, user_msg, target, args, key)
    else:
        eprint("ERROR: cli transport not implemented yet.")
        sys.exit(4)
```

Remove the now-dead inline `model = args.model or ...`, the inline `payload`/`resp`/printing, and the inline dry-run block from `main()` (they now live in `run_openrouter`). Keep `--check-credits` handling where it is (before dispatch).

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: PASS (new framing test + all earlier tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/third-lens-review.py tests/unit/test_third_lens_review.py
git commit -m "refactor(third-lens): extract run_openrouter + transport dispatch"
```

---

## Task 5: Implement `run_codex()` + CLI dispatch

**Files:**
- Modify: `scripts/third-lens-review.py` (add `import tempfile`; add `run_codex`; wire `else` branch)
- Modify: `tests/unit/test_third_lens_review.py`

**Interfaces:**
- Consumes: dispatch `else` branch from Task 4.
- Produces: `run_codex(system_prompt, user_msg, target, args) -> None` — shells out to `codex exec -` with the prompt on **stdin** (ARG_MAX-safe, non-interactive), prints RAW OUTPUT framing labelled `(codex CLI)`, reports subscription usage; `sys.exit(4)` on any CLI failure.

- [ ] **Step 1: Write the failing tests**

Append:

```python
import subprocess


def test_run_codex_invokes_exec_and_prints(monkeypatch, capsys):
    captured = {}

    def fake_run(cmd, input, capture_output, text, timeout):
        captured["cmd"] = cmd
        captured["input"] = input
        # codex writes its final message to the path after -o
        out_path = cmd[cmd.index("-o") + 1]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("P1 codex finding")
        class P:
            returncode = 0
            stderr = ""
        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)

    class Args:
        dry_run = False
    tlr.run_codex("SYS", "USER artifact", "codex", Args())
    out = capsys.readouterr().out
    assert captured["cmd"][:2] == ["codex", "exec"]
    assert "--sandbox" in captured["cmd"] and "read-only" in captured["cmd"]
    assert captured["cmd"][-1] == "-"  # prompt comes from stdin, not argv (ARG_MAX safe)
    assert "USER artifact" in captured["input"]  # artifact piped via stdin
    assert "===== THIRD-LENS RAW OUTPUT (codex CLI) =====" in out
    assert "P1 codex finding" in out
    assert "subscription" in out


def test_run_codex_nonzero_exits_4(monkeypatch):
    def fake_run(cmd, input, capture_output, text, timeout):
        class P:
            returncode = 1
            stderr = "boom"
        return P()
    monkeypatch.setattr(subprocess, "run", fake_run)

    class Args:
        dry_run = False
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", Args())
    assert e.value.code == 4


def test_run_codex_missing_binary_exits_4(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", fake_run)

    class Args:
        dry_run = False
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", Args())
    assert e.value.code == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_third_lens_review.py -q`
Expected: FAIL — `run_codex` not defined.

- [ ] **Step 3: Implement `run_codex` and wire dispatch**

Add `import tempfile` near the top imports. Add the function:

```python
def run_codex(system_prompt, user_msg, target, args):
    """Run the third lens via the codex CLI (OpenAI, subscription). target is the binary name."""
    prompt = f"{system_prompt}\n\n{user_msg}"
    if args.dry_run:
        est_in = len(prompt) // 4
        print("Transport: codex CLI (subscription — no OpenRouter cost)")
        print(f"Estimated input tokens: ~{est_in:,}")
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        out_path = tf.name
    try:
        # Pass the prompt via STDIN (`exec -` reads instructions from stdin), NOT as an
        # argv arg: a large diff would blow past ARG_MAX. Piping stdin also means there is
        # no TTY, so codex cannot block on an interactive trust/login/approval prompt — it
        # runs non-interactively or fails fast instead of hanging for the full timeout.
        cmd = [target, "exec", "--sandbox", "read-only", "--color", "never",
               "--skip-git-repo-check", "-o", out_path, "-"]
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600)
        except FileNotFoundError:
            eprint(f"ERROR: '{target}' CLI not found in PATH (needed for --role countersynthesis).")
            sys.exit(4)
        except subprocess.TimeoutExpired:
            eprint(f"ERROR: '{target}' CLI timed out after 600s.")
            sys.exit(4)
        if proc.returncode != 0:
            eprint(f"ERROR: {target} exec failed (exit {proc.returncode}):\n{proc.stderr.strip()[:500]}")
            sys.exit(4)
        try:
            with open(out_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            eprint(f"ERROR: could not read {target} output: {e}")
            sys.exit(4)
        if not text.strip():
            eprint(f"ERROR: {target} returned empty output.")
            sys.exit(4)
        print("===== THIRD-LENS RAW OUTPUT (codex CLI) =====\n")
        print(text.rstrip())
        print("\n===== END RAW OUTPUT — agent must run adversarial synthesis over this =====")
        print("\n[usage] via codex CLI (subscription — no per-call cost)")
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
```

Replace the dispatch `else` branch in `main()`:
```python
    if transport == "openrouter":
        run_openrouter(system_prompt, user_msg, target, args, key)
    else:
        run_codex(system_prompt, user_msg, target, args)
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `bash tests/run.sh --unit`
Expected: PASS — "unit: PASS", "All test suites passed."

- [ ] **Step 5: Live smoke test (manual — REQUIRED, verifies codex behaviour the mocks can't)**

This step exists because three things about the real `codex exec` are assumed, not proven by the mocked unit tests: (a) `-o` captures the *full* review, not a truncated one-line summary; (b) piping the prompt via stdin runs non-interactively with no hang; (c) a real review artifact round-trips. Run a non-trivial input (not a one-liner) so a truncated summary would be visible:

```bash
# --diff makes the script gather the diff itself (do NOT also pipe one in).
python3 scripts/third-lens-review.py --role countersynthesis --diff --diff-base HEAD~3
```
Expected, ALL of:
- A `===== THIRD-LENS RAW OUTPUT (codex CLI) =====` block containing **multiple sentences / several findings** (if it is one terse line, `-o` is giving a summary — switch the codex invocation to capture full stdout instead of `--output-last-message` and re-test before proceeding).
- The run returns within the timeout with **no interactive prompt** (proves the stdin/non-interactive path). If codex blocks on a trust/login prompt, run `codex login` / trust the dir ONCE interactively, then confirm the piped invocation no longer prompts.
- Ends with `[usage] via codex CLI (subscription — no per-call cost)`.

- [ ] **Step 6: Commit**

```bash
git add scripts/third-lens-review.py tests/unit/test_third_lens_review.py
git commit -m "feat(third-lens): route countersynthesis via codex CLI"
```

---

## Task 6: Docs, routing, and version bump

**Files:**
- Modify: `skills/third-lens-review/SKILL.md`
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md`
- Modify: `.claude-plugin/plugin.json`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Update `skills/third-lens-review/SKILL.md`**

Find the role table row for `sensitive` and delete it. Update the `countersynthesis` row to reflect the codex CLI transport. The resulting table rows (in `skills/third-lens-review/SKILL.md`) read:

```markdown
| `architecture` | `z-ai/glm-5.2` | Zhipu | default 3rd lens — most distant distribution; OpenRouter |
| `correctness` | `deepseek/deepseek-v4-pro` | DeepSeek | correctness sniper; OpenRouter |
| `countersynthesis` | `codex` CLI | OpenAI | refutes Claude's dedup; via codex CLI (subscription, no per-call cost) |
```

Replace any prose mentioning `--sensitive` / Western-infra enforcement with one line:
```markdown
The `sensitive` role and its `--sensitive` fail-closed guard were removed in 2.18.0 (work is not sensitive; default is GLM-5.2).
```

- [ ] **Step 2: Update `CLAUDE.md` routing bullet (line ~103)**

Replace the third-lens bullet's routing sentence with:

```markdown
- third-lens-review (normally auto-invoked by pitfall-verification Stage 3; invoke directly only for an ad-hoc third-house read) → runs an external model house on the PATCHED artifact (`scripts/third-lens-review.py`). Routing by `--role`: architecture=GLM-5.2 (default, OpenRouter), correctness=DeepSeek V4-Pro (OpenRouter), countersynthesis=OpenAI via the `codex` CLI (subscription). OpenRouter key in Keychain `openrouter-api-key`; the `sensitive` role was removed in 2.18.0.
```

- [ ] **Step 3: Add `CHANGELOG.md` entry**

Add at the top of the entries (match the file's existing heading style):

```markdown
## 2.18.0

### Changed
- third-lens-review: `countersynthesis` now runs through the `codex` CLI (subscription) instead of OpenRouter `openai/gpt-5.5`. `architecture` (GLM-5.2) and `correctness` (DeepSeek V4-Pro) stay on OpenRouter — no CLI exists for those houses.

### Removed
- third-lens-review: the `sensitive` role and its fail-closed `--sensitive` guard (`WESTERN_PREFIXES` allowlist, exit code 5). Work targeted by this plugin is not sensitive; the default lens is GLM-5.2.

### Added
- `tests/unit/` pytest suite for `third-lens-review.py`, wired into `tests/run.sh --unit`.
```

- [ ] **Step 4: Bump the version**

Edit `.claude-plugin/plugin.json`: change `"version": "2.17.0"` to `"version": "2.18.0"`.

- [ ] **Step 5: Verify nothing references the removed surface**

Run:
```bash
grep -rn "WESTERN_PREFIXES\|--sensitive\|role sensitive\|gemini-3.1-pro-preview" scripts/ skills/third-lens-review/ CLAUDE.md
```
Expected: no matches (or only inside `CHANGELOG.md`/this plan describing the removal). Fix any stragglers.

- [ ] **Step 6: Commit**

```bash
git add skills/third-lens-review/SKILL.md CLAUDE.md CHANGELOG.md .claude-plugin/plugin.json
git commit -m "docs(third-lens): update routing/SKILL/CHANGELOG, bump 2.18.0"
```

---

## Verification (after all tasks)

Ship-worthy + touches the multi-model review contract → run `superpowers-gstack:pitfall-verification`, which auto-chains `/codex review` and `third-lens-review` on the patched script, ending in adversarial synthesis. Address any P1/P2 findings before opening the PR.
