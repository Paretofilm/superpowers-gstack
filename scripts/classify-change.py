#!/usr/bin/env python3
"""classify-change.py — compute the review-tier FLOOR for a change, mechanically.

Why this exists (2.51.0). `pitfall-verification`'s tier gate decided whether the
expensive lenses (Codex, third house) run at all — and it was decided by the same
model that had just written the code, in prose, with no test asserting it. That is
self-assessment placed exactly where the incentive to pick the cheapest outcome is
strongest, late in a long session. `/autoimplement` has hard refusals; the review
gate had none.

So the machine computes a FLOOR from the change itself and the agent may only
ESCALATE above it, never fall below. The floor is deliberately blunt and biased
UPWARD: over-classifying costs ~$0.05 and two minutes, under-classifying costs a
lens that would have caught the bug. Everything a regex cannot see — a subtle
protocol change, a data-loss path in ordinary-looking code — is what the agent's
own escalation is still for.

It also resolves and NAMES THE TARGET, using the same `--files` / `--diff` /
`--diff-base` spelling as third-lens-review.py, so Stage 0 and Stage 3 review the
same artifact by construction instead of by hope.

Known and accepted: this file contains the signal patterns as literals, so a change
touching THIS file matches its own security/migration signals. A pattern file always
self-matches. It is a floor, so the failure direction is extra review — `--explain`
makes it visible rather than mysterious.

Usage:
  python3 scripts/classify-change.py                       # auto target, JSON
  python3 scripts/classify-change.py --diff --diff-base main
  python3 scripts/classify-change.py --files "src/**/*.swift"
  python3 scripts/classify-change.py --text --explain
  python3 scripts/classify-change.py --assert-tier ship-worthy   # exit 1 if below floor

Exit codes: 0 ok | 1 --assert-tier below the floor | 2 usage error
            | 5 nothing to classify (no changed files / not a git repo)
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import os
import re
import subprocess
import sys

TIERS = ["trivial", "ship-worthy", "high-stakes"]

# --- size proxy for "architecture" -------------------------------------------
# Architecture is not detectable by regex. These thresholds are a PROXY, chosen
# against this repo's own history: releases that touched >=8 files or added >=400
# lines are the ones whose review provenance shows the third house earning its
# place (2.41-2.44). Blunt on purpose, and a floor, so a false positive costs one
# GLM run.
ARCH_FILE_COUNT = 8
ARCH_ADDED_LINES = 400

# --- path classes -------------------------------------------------------------
# Instruction surface is the PRODUCT of a plugin/agent repo, so a .md file here is
# runtime behaviour, not documentation. Checked before DOC_PATHS for that reason.
INSTRUCTION_PATHS = re.compile(
    r"(^|/)(CLAUDE\.md|AGENTS\.md)$|(^|/)(skills|prompts|blocks|\.claude|\.github)/", re.I)
DOC_PATHS = re.compile(
    r"\.(md|markdown|txt|rst|adoc)$|(^|/)(docs|doc)/|(^|/)(LICENSE|NOTICE|AUTHORS)$", re.I)
TEST_PATHS = re.compile(
    r"(^|/)(tests?|spec|__tests__|testdata|fixtures)/|(^|/)test_[^/]+$|_test\.[a-z]+$"
    r"|\.(test|spec)\.[a-z]+$|Tests?\.swift$", re.I)
VERSION_FILES = re.compile(
    r"(^|/)(package\.json|plugin\.json|pyproject\.toml|Cargo\.toml|version\.txt"
    r"|build\.gradle(\.kts)?|Info\.plist)$|\.(podspec|gemspec)$", re.I)
CHANGELOG_FILES = re.compile(r"(^|/)CHANGELOG[^/]*$", re.I)

# --- high-stakes signals ------------------------------------------------------
# Each entry maps a tier-table category to what can actually be seen mechanically.
# Kept deliberately narrow: a signal that fires on everything gates nothing.
#
# Word boundaries, and why they are not just [/_.-]. A keyword ends at a separator
# in snake_case and kebab-case, but CamelCase — the convention across Swift, Kotlin
# and TypeScript — ends a word with a CAPITAL, and plurals end it with an 's'.
# Requiring a separator therefore missed `AuthManager.swift`, `authService.ts`,
# `sessions/`, `tokens/`, `AudioEngine.swift` and `WebSocketClient.swift`: they got
# only a ship-worthy floor and skipped the third house. This repo is dual-track
# (web AND native, CLAUDE.md), so missing every Swift name is missing half the
# mandate. `s?(?![a-z])` accepts a separator, end-of-string, a capital, or a plural,
# and still rejects a longer lowercase word — `tokenizer` and `streamlit` do NOT
# match, which is what keeps the signal narrow.
#
# The `(?-i:...)` wrapper is load-bearing: these patterns compile with re.I, which
# would make a bare `[a-z]` match capitals too, so the lookahead would reject the
# CamelCase boundary it exists to accept. Scoping IGNORECASE off keeps "followed by
# a lowercase letter" meaning exactly that.
_B = r"s?(?-i:(?![a-z]))"
HIGH_STAKES_PATH = [
    ("security", re.compile(
        r"(^|/|_|-)(auth|authn|authz|authentication|authorization|authorized|authenticate"
        r"|login|signin|signup|session|oauth|jwt|token|secret"
        r"|credential|password|keychain|crypto|cipher|permission|acl|rbac)" + _B, re.I)),
    ("migration", re.compile(
        r"(^|/)(migrations?|alembic|prisma)/|(^|/|_|-)migrat|(^|/|_|-)schema" + _B + r"|\.sql$", re.I)),
    ("public-contract", re.compile(
        r"openapi|swagger|\.proto$|\.graphql$|(^|/)schema\.json$|\.d\.ts$"
        r"|(^|/)Package\.swift$|(^|/)api/", re.I)),
    ("real-time-concurrency", re.compile(
        r"(^|/|_|-)(audio|dsp|realtime|websocket|stream|streaming|scheduler|worker|queue"
        r"|concurren|concurrency|concurrent)" + _B, re.I)),
]
HIGH_STAKES_CONTENT = [
    ("security", re.compile(
        r"shell\s*=\s*True|os\.system\(|subprocess\.|\beval\(|\bexec\(|pickle\.loads"
        r"|innerHTML|dangerouslySetInnerHTML|verify\s*=\s*False|NSAllowsArbitraryLoads"
        r"|--no-verify|chmod\s+777")),
    ("migration", re.compile(
        r"\b(ALTER\s+TABLE|DROP\s+TABLE|DROP\s+COLUMN|CREATE\s+TABLE|ADD\s+COLUMN"
        r"|TRUNCATE)\b", re.I)),
    ("real-time-concurrency", re.compile(
        r"DispatchQueue|NSLock|os_unfair_lock|AVAudioEngine|Task\.detached"
        r"|threading\.(Thread|Lock|RLock)|asyncio\.|std::thread|sync\.Mutex|\bgo func\b")),
]


def eprint(*a):
    print(*a, file=sys.stderr)


def git(*args, check=False):
    """Run a git command; return stdout ('' on failure) unless check is set."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True,
                             errors="replace", timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        if check:
            eprint(f"ERROR: cannot run git: {e}")
            sys.exit(5)
        return ""
    if out.returncode != 0:
        if check:
            eprint(f"ERROR: git {' '.join(args)}: {out.stderr.strip()}")
            sys.exit(5)
        return ""
    return out.stdout


def default_base():
    """Best guess at the branch this work will land on."""
    ref = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
    if ref:
        return ref.replace("refs/remotes/", "")
    for cand in ("origin/main", "origin/master", "main", "master"):
        if git("rev-parse", "--verify", "--quiet", cand).strip():
            return cand
    return "HEAD"


def resolve_target(args):
    """Return (target_dict, files, diff_text).

    Three modes, same spelling as third-lens-review.py so Stage 0 and Stage 3 can
    be pointed at one artifact:
      --files GLOB...   explicit paths/globs
      --diff            git diff against --diff-base (default HEAD)
      neither           auto: dirty tree -> working tree vs HEAD;
                        clean tree -> merge-base with the default branch
    """
    # Precedence must match third-lens-review.py, which resolves --diff first and
    # ignores --files. Winning the other way here would hand Stage 0 and Stage 3
    # DIFFERENT artifacts for the same argv — the exact failure this script exists
    # to prevent, arrived at through the argument parser instead of the tier.
    if args.files and not args.diff:
        if args.diff_base is not None:
            eprint(f"WARN: --diff-base {args.diff_base} ignored in --files mode "
                   "(files are read from disk, not from a ref).")
        paths, seen = [], set()
        for pat in args.files:
            matched = globmod.glob(pat, recursive=True)
            for p in (matched or [pat]):
                if p not in seen and os.path.isfile(p):
                    seen.add(p)
                    paths.append(p)
        if not paths:
            eprint(f"ERROR: no readable files matched: {args.files}")
            sys.exit(5)
        text = []
        for p in paths:
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text.append(fh.read())
            except OSError as e:
                eprint(f"WARN: skipping {p}: {e}")
        # `degraded` is part of the target contract in every mode — a consumer
        # reading target["degraded"] must not get a KeyError depending on which
        # flag the caller used. Files mode reads current disk content, so it is
        # never degraded.
        return ({"mode": "files", "base": None, "degraded": False,
                 "spec": f"files: {' '.join(args.files)}"},
                paths, "\n".join(text))

    if args.files and args.diff:
        eprint("WARN: --diff and --files both given; --diff wins "
               "(same precedence as third-lens-review.py).")

    # `--diff-base X` without `--diff` used to fall through to auto mode silently,
    # which on a dirty tree classifies the WORKING TREE instead of the branch — a
    # downgrade, arrived at by typo. Observed live: `--diff-base main` on a branch
    # whose real floor was high-stakes reported ship-worthy off one stray untracked
    # file. Naming a base is unambiguous intent, so honour it.
    if args.diff_base is not None and not args.diff and not args.files:
        eprint(f"WARN: --diff-base {args.diff_base} given without --diff; assuming --diff.")
        args.diff = True

    if args.diff:
        base = args.diff_base if args.diff_base is not None else "HEAD"
        spec = f"git diff {base}"
    else:
        dirty = git("status", "--porcelain").strip()
        if dirty:
            base, spec = "HEAD", "working tree vs HEAD (uncommitted)"
        else:
            head = default_base()
            mb = git("merge-base", head, "HEAD").strip()
            base = mb or head
            spec = f"git diff {head}...HEAD (merge-base {base[:12]})" if mb else f"git diff {head}"

    names = git("diff", "--name-only", base, "--", check=True)
    files = [f for f in names.splitlines() if f.strip()]
    tracked_diff = git("diff", base, "--")
    diff_text = tracked_diff

    # A brand-new file is untracked, so `git diff` shows nothing for it — and a new
    # file is the single most review-worthy thing a change can contain. Fold the
    # untracked, non-ignored files in and synthesise added-line hunks for them so
    # the size proxy and the content signals see them like any other addition.
    extra, extra_text = [], []
    for f in git("ls-files", "--others", "--exclude-standard").splitlines():
        f = f.strip()
        if not f or f in files:
            continue
        extra.append(f)
        try:
            if os.path.getsize(f) > 1_000_000:  # don't slurp a blob into the scan
                continue
            with open(f, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        extra_text.append("+++ b/%s\n" % f
                          + "\n".join("+" + ln for ln in body.splitlines()))
    files += extra
    if extra_text:
        diff_text = diff_text + "\n" + "\n".join(extra_text)

    if not files:
        eprint(f"ERROR: nothing to classify — no changed files for {spec}.")
        sys.exit(5)
    # If there are changed files but no diff body, the diff call failed (or the
    # content is binary): the content signals and the size proxy did not run. That
    # loses signal in the DOWNWARD direction, which is the one failure this gate
    # exists to prevent — so say so rather than reporting a floor built on nothing.
    #
    # Test the TRACKED diff, not the concatenation: synthesised untracked hunks are
    # appended above, so a failed `git diff` plus one untracked file produced a
    # non-empty diff_text and reported degraded=False — hiding the loss behind
    # unrelated content, which is precisely the mask this flag exists to lift.
    degraded = bool(files) and not tracked_diff.strip() and any(
        f not in extra for f in files)
    return ({"mode": "diff", "base": base, "spec": spec, "degraded": degraded},
            files, diff_text)


def added_lines(diff_text):
    """Count added lines in a unified diff, excluding the +++ file headers."""
    return sum(1 for ln in diff_text.splitlines()
               if ln.startswith("+") and not ln.startswith("+++"))


def scannable(diff_text, mode):
    """The text the content signals run against.

    For a diff that is the ADDED lines only: a signal is about what this change
    introduces, not about what the surrounding file already contained (which would
    make every edit near an auth block read as an auth change).
    """
    if mode != "diff":
        return diff_text
    return "\n".join(ln[1:] for ln in diff_text.splitlines()
                     if ln.startswith("+") and not ln.startswith("+++"))


def classify(files, diff_text, mode, degraded=False):
    """Return (floor_tier, signals, reasons). Floor only — the agent may escalate."""
    signals, reasons = [], []
    if degraded:
        reasons.append("DEGRADED: no diff body for the changed files — content and "
                       "size signals did NOT run. Escalate by hand; the floor below "
                       "is built on paths alone.")

    for f in files:
        for label, rx in HIGH_STAKES_PATH:
            if rx.search(f):
                signals.append({"kind": "path", "label": label, "evidence": f})

    body = scannable(diff_text, mode)
    for label, rx in HIGH_STAKES_CONTENT:
        m = rx.search(body)
        if m:
            signals.append({"kind": "content", "label": label,
                            "evidence": m.group(0).strip()[:60]})

    n_files, n_added = len(files), added_lines(diff_text) if mode == "diff" else 0
    if n_files >= ARCH_FILE_COUNT or n_added >= ARCH_ADDED_LINES:
        signals.append({"kind": "size", "label": "architecture-scale",
                        "evidence": f"{n_files} files, +{n_added} lines"})

    # De-dupe by (kind,label), keeping the first evidence — one line per signal.
    seen, uniq = set(), []
    for s in signals:
        key = (s["kind"], s["label"])
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    signals = uniq

    if signals:
        reasons.append("high-stakes signals fired: "
                       + ", ".join(sorted({s["label"] for s in signals})))
        return "high-stakes", signals, reasons

    version_hits = [f for f in files if VERSION_FILES.search(f)]
    changelog_hits = [f for f in files if CHANGELOG_FILES.search(f)]
    instruction_hits = [f for f in files if INSTRUCTION_PATHS.search(f)]
    runtime_hits = [f for f in files
                    if not (DOC_PATHS.search(f) or TEST_PATHS.search(f))
                    and not VERSION_FILES.search(f) and not CHANGELOG_FILES.search(f)]

    if version_hits:
        reasons.append(f"version file changed: {version_hits[0]}")
    if changelog_hits:
        reasons.append(f"CHANGELOG changed: {changelog_hits[0]}")
    if instruction_hits:
        reasons.append("instruction surface changed (agent-runtime behaviour, not docs): "
                       f"{instruction_hits[0]}")
    if runtime_hits:
        reasons.append(f"runtime source changed: {runtime_hits[0]}")

    if version_hits or changelog_hits or instruction_hits or runtime_hits:
        return "ship-worthy", signals, reasons

    reasons.append("only docs/tests changed, no version or CHANGELOG entry")
    return "trivial", signals, reasons


def header(target, floor, signals):
    """The one line the agent must copy into its verdict header.

    The DEGRADED state has to travel on THIS line, not only in `reasons`. The skill
    tells the agent to copy the header into its verdict, so a degraded run whose
    warning lived elsewhere produced an audit trail reading "Tier floor: ship-worthy
    (signals: none)" — indistinguishable from a fully computed clean result, when the
    content and size signals never ran at all. That is a floor reported lower than
    the truth arriving through the verdict surface instead of the classifier.
    """
    labels = ", ".join(sorted({s["label"] for s in signals})) or "none"
    degraded = (" · DEGRADED (content + size signals did NOT run — escalate by hand)"
                if target.get("degraded") else "")
    return (f"Target: {target['spec']} · Tier floor: {floor} "
            f"(signals: {labels}) · computed by scripts/classify-change.py{degraded}")


def main():
    ap = argparse.ArgumentParser(
        description="Compute the review-tier floor and name the target for pitfall-verification.")
    ap.add_argument("--files", nargs="*", default=[],
                    help="paths/globs to classify (same spelling as third-lens-review.py)")
    ap.add_argument("--diff", action="store_true", help="classify a git diff instead of files")
    # default None, not "HEAD", so resolve_target can tell "user named a base" from
    # "user named nothing" and honour the former even without an explicit --diff.
    ap.add_argument("--diff-base", default=None, help="git ref to diff against (default HEAD)")
    ap.add_argument("--assert-tier", choices=TIERS, default=None,
                    help="exit 1 if this claimed tier is BELOW the computed floor")
    ap.add_argument("--text", action="store_true", help="human-readable output instead of JSON")
    ap.add_argument("--explain", action="store_true", help="list every signal with its evidence")
    args = ap.parse_args()

    target, files, diff_text = resolve_target(args)
    floor, signals, reasons = classify(files, diff_text, target["mode"],
                                       degraded=target.get("degraded", False))
    result = {
        "target": {**target, "file_count": len(files),
                   "added_lines": added_lines(diff_text) if target["mode"] == "diff" else None,
                   "files": files[:50]},
        "floor_tier": floor,
        "signals": signals,
        "reasons": reasons,
        "verdict_header": header(target, floor, signals),
        "contract": "floor only — the agent may escalate above this, never below",
    }

    if args.text or args.explain:
        print(result["verdict_header"])
        for r in reasons:
            print(f"  - {r}")
        if args.explain:
            for s in signals:
                print(f"  [{s['kind']}] {s['label']}: {s['evidence']}")
    else:
        print(json.dumps(result, indent=2))

    if args.assert_tier and TIERS.index(args.assert_tier) < TIERS.index(floor):
        eprint(f"ERROR: claimed tier '{args.assert_tier}' is BELOW the computed floor "
               f"'{floor}'. {'; '.join(reasons)}")
        eprint("Escalation is allowed; downgrading is not. Run the lenses for the floor tier.")
        sys.exit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
