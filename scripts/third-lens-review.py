#!/usr/bin/env python3
"""third-lens-review.py — run a single external "third lens" review via OpenRouter.

Part of superpowers-gstack's multi-lens review. Claude (author/self-pitfall) and
Codex (OpenAI) are lenses 1 and 2; this script runs lens 3 (and optionally 4) on a
*patched* artifact: a different model house reads the code/diff and reports pitfalls
the first two missed. The orchestrating agent then runs an ADVERSARIAL synthesis
(default: finding is real until refuted) over the raw output this prints.

Design notes:
- Stdlib only (urllib/json/subprocess). No pip install.
- API key comes from macOS Keychain (account `openrouter-api-key`), env
  OPENROUTER_API_KEY as fallback. Never pass keys on the command line.
- Pricing is fetched live from OpenRouter /models and applied to the real `usage`
  object — no hardcoded prices to go stale.
Exit codes: 0 ok | 2 usage error | 3 auth/key error | 4 API/network/CLI failure
           | 6 nothing to review
"""

import argparse
import glob as globmod
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
KEYCHAIN_ACCOUNT = "openrouter-api-key"

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


def eprint(*a):
    print(*a, file=sys.stderr)


def resolve_key():
    """Keychain first, then env. Returns the key or exits 3."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-w"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # not on macOS, or security unavailable — fall through to env
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    eprint("ERROR: no OpenRouter key. Add to Keychain:")
    eprint('  security add-generic-password -a "openrouter-api-key" -s "openrouter-api-key" -w "<key>" -A -U')
    eprint("or export OPENROUTER_API_KEY=<key>")
    sys.exit(3)


def http_json(method, path, key, payload=None, timeout=300):
    url = path if path.startswith("http") else f"{OPENROUTER_BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    # OpenRouter attribution headers (optional but polite).
    req.add_header("HTTP-Referer", "https://github.com/Paretofilm/superpowers-gstack")
    req.add_header("X-Title", "superpowers-gstack third-lens-review")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        eprint(f"ERROR: HTTP {e.code} from OpenRouter:\n{body}")
        sys.exit(4)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        eprint(f"ERROR: network/timeout/parse calling OpenRouter: {e}")
        sys.exit(4)


def get_pricing(key, model):
    """Return (prompt_per_tok, completion_per_tok) in USD, or (None, None)."""
    try:
        d = http_json("GET", "/models", key, timeout=30)
    except SystemExit:
        return (None, None)
    for m in d.get("data", []):
        if m.get("id") == model:
            p = m.get("pricing", {})
            try:
                return (float(p.get("prompt", 0)), float(p.get("completion", 0)))
            except (TypeError, ValueError):
                return (None, None)
    return (None, None)


def get_credits(key):
    try:
        d = http_json("GET", "/credits", key, timeout=30)
        data = d.get("data", d)
        total = data.get("total_credits")
        used = data.get("total_usage")
        if total is not None and used is not None:
            return total - used
    except SystemExit:
        pass
    return None


def gather_content(args):
    """Build the artifact text: --diff (git) or --files (globs/paths) or stdin."""
    if args.diff:
        if args.files:
            eprint("WARN: --diff and --files both given; --files ignored.")
        base = args.diff_base
        try:
            out = subprocess.run(
                ["git", "diff", base, "--"], capture_output=True, text=True, timeout=30
            )
            if out.returncode != 0:
                eprint(f"ERROR: git diff failed: {out.stderr.strip()}")
                sys.exit(6)
            text = out.stdout
            return f"# Git diff against {base}\n\n```diff\n{text}\n```\n" if text.strip() else ""
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            eprint(f"ERROR: cannot run git diff: {e}")
            sys.exit(6)

    paths = []
    for pat in args.files:
        matched = globmod.glob(pat, recursive=True)
        paths.extend(matched if matched else [pat])  # keep literal path if no glob match
    # de-dupe, keep order, files only
    seen, files = set(), []
    for p in paths:
        if p not in seen and os.path.isfile(p):
            seen.add(p)
            files.append(p)
    if not files and not args.files:  # no --files given → read stdin
        stdin = sys.stdin.read()
        return f"# Artifact (stdin)\n\n```\n{stdin}\n```\n" if stdin.strip() else ""
    if not files:
        eprint(f"ERROR: no readable files matched: {args.files}")
        sys.exit(6)

    chunks = []
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                chunks.append(f"## File: {f}\n\n```\n{fh.read()}\n```\n")
        except OSError as e:
            eprint(f"WARN: skipping {f}: {e}")
    return "\n".join(chunks)


DEFAULT_PROMPT = (
    "You are an independent third-lens reviewer. Two strong reviewers (Anthropic Claude "
    "and OpenAI Codex) have ALREADY reviewed and patched this artifact. Do NOT repeat "
    "what they likely caught. Your value is finding what a different training distribution "
    "sees that they took for granted:\n"
    "- architecture-level mistakes (\"this was never wired together\", dead code paths, "
    "components that bypass the thing under test)\n"
    "- challenged core assumptions\n"
    "- degraded/edge states (overflow, late events, partial failure, resource leaks under load)\n"
    "- concurrency / lifecycle / use-after-free hazards\n\n"
    "For each finding give: SEVERITY (P1/P2/P3), the file:line or component, why it is real, "
    "and a concrete fix. Be explicit when you are UNCERTAIN or possibly over-strict — say so, "
    "so the synthesizer can weigh it. Prefer a few real findings over many speculative ones."
)


def run_openrouter(system_prompt, user_msg, model, args, key):
    """Run a review via OpenRouter HTTP API. Prints RAW OUTPUT + usage + balance."""
    # rough pre-flight token estimate (chars/4) for the cost note
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
        # Cap reasoning-token blowout on reasoning models (GLM/DeepSeek/etc.).
        # Ignored by non-reasoning models. Without this a reasoning model can spend
        # the entire token budget thinking and return EMPTY content (finish_reason=length).
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
        # Reasoning models can exhaust the budget thinking and emit no content.
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
    # Prefer OpenRouter's authoritative cost; fall back to pricing-table math.
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


def main():
    ap = argparse.ArgumentParser(description="Run a single external third-lens review via OpenRouter.")
    ap.add_argument("--files", nargs="*", default=[],
                    help="files/globs to review (recursive ** supported). Omit to read stdin.")
    ap.add_argument("--diff", action="store_true", help="review `git diff` instead of files")
    ap.add_argument("--diff-base", default="HEAD", help="git ref to diff against (default HEAD)")
    ap.add_argument("--model", default=None, help="OpenRouter model id (overrides --role)")
    ap.add_argument("--role", choices=list(ROLE_SPEC), default="architecture",
                    help="pick lens by role (default architecture=GLM-5.2 on OpenRouter)")
    ap.add_argument("--prompt", default=None, help="extra instructions appended to the review prompt")
    ap.add_argument("--max-tokens", type=int, default=16000,
                    help="completion token cap (includes reasoning tokens on reasoning models)")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default="medium",
                    help="reasoning effort for reasoning models (caps the reasoning-token blowout)")
    ap.add_argument("--dry-run", action="store_true",
                    help="estimate input size + cost, do not call the model")
    ap.add_argument("--check-credits", action="store_true", help="print OpenRouter balance and exit")
    args = ap.parse_args()

    if args.check_credits:
        key = resolve_key()
        bal = get_credits(key)
        if bal is None:
            eprint("ERROR: could not retrieve balance (bad key or network).")
            sys.exit(3)
        print(f"OpenRouter balance: ${bal:.2f}")
        return

    transport, target = resolve_transport(args.role, args.model)

    content = gather_content(args)
    if not content.strip():
        eprint("ERROR: nothing to review (empty diff / no files / empty stdin).")
        sys.exit(6)

    system_prompt = DEFAULT_PROMPT + (f"\n\nExtra instructions:\n{args.prompt}" if args.prompt else "")
    user_msg = f"Review the following artifact:\n\n{content}"

    if transport == "openrouter":
        key = resolve_key()  # lazy — cli path must never call resolve_key()
        run_openrouter(system_prompt, user_msg, target, args, key)
    else:
        eprint("ERROR: cli transport not implemented yet.")
        sys.exit(4)


if __name__ == "__main__":
    main()
