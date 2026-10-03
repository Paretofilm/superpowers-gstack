#!/usr/bin/env python3
"""lock-acceptance-tests — keep the acceptance tests the user approved exactly as approved.

/superpowers-gstack:vibe shows the user the acceptance tests once; after their ok the
tests are the contract for the rest of the feature.

  lock    commits the test files (`test(acceptance): lock <feature>`) — whatever the
          matched files currently contain; they need not be clean — then adds
          `Edit(/<glob>)` and `Write(/<glob>)` deny rules (for the receipt too) to the
          project's .claude/settings.json, records the lock in
          .gstack/acceptance-lock.json and commits both
          (`chore(acceptance): deny edits to <feature> tests`). Two commits because the
          receipt names the first one's SHA.
  verify  exit 0 when every locked path is identical to its lock commit, working tree
          and index included, and the receipt itself is identical to HEAD; exit 1 lists
          `CHANGED <feature> <file>` and `CHANGED receipt .gstack/acceptance-lock.json`;
          exit 2 when there is no receipt or no such feature.
  unlock  removes one feature's lock and only the deny rules no other lock still
          needs. Run it only when the user asks.

A deny rule stops the Edit and Write tools, not `sed` through Bash. `verify` is the
gate; the rules make the honest path the easy one. verify ignores untracked files and
cannot see `assume-unchanged`/`skip-worktree` flags: it is a gate for the honest path.

Exit 0 ok, 1 changed (verify), 2 refused — the reason is on stderr. Never a traceback.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT = Path(".gstack") / "acceptance-lock.json"
SETTINGS = Path(".claude") / "settings.json"
FEATURE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Refusal(Exception):
    pass


def git(top: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=top, capture_output=True, text=True)
    if p.returncode != 0:
        exc = Refusal(f"BLOCKED — `git {' '.join(args)}` failed: {p.stderr.strip()}")
        exc.detail = (p.stderr.strip() or p.stdout.strip())
        raise exc
    return p.stdout


def toplevel(project: Path) -> Path:
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=project, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"BLOCKED — {project} is not inside a git repository")
    return Path(p.stdout.strip())


def read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Refusal(f"BLOCKED — {path} is not valid JSON ({exc}); fix it by hand — nothing was changed")
    if not isinstance(data, dict):
        raise Refusal(f"BLOCKED — {path} must hold a JSON object — nothing was changed")
    return data


def read_receipt(top: Path, default):
    receipt = read_json(top / RECEIPT, default)
    if receipt is None:
        return None
    locks = receipt.get("locks", [])
    bad = None
    if not isinstance(locks, list):
        bad = "`locks` is not a list"
    else:
        for i, lk in enumerate(locks):
            if not isinstance(lk, dict):
                bad = f"lock #{i} is not an object"
            elif not all(isinstance(lk.get(k), str) for k in ("feature", "commit")):
                bad = f"lock #{i} lacks a string `feature`/`commit`"
            elif not all(isinstance(lk.get(k, []), list) and all(isinstance(x, str) for x in lk.get(k, []))
                         for k in ("paths", "files", "rules", "added")):
                bad = f"lock #{i} has a `paths`/`files`/`rules`/`added` that is not a list of strings"
            if bad:
                break
    if bad:
        raise Refusal(f"BLOCKED — {RECEIPT} is malformed ({bad}); fix it by hand — nothing was changed")
    return receipt


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_feature(name: str) -> str:
    if not FEATURE_RE.match(name):
        raise Refusal(f"USAGE ERROR: --feature {name!r} must be letters, digits, `.`, `_` or `-` (max 64)")
    return name


def expand(top: Path, globs: list[str]) -> list[str]:
    files: set[str] = set()
    for g in globs:
        if g.startswith("/") or ".." in Path(g).parts:
            raise Refusal(f"BLOCKED — --path {g!r} must be relative to the repository root and stay inside it")
        # glob.glob, not Path.glob: on Python 3.12 a trailing `**` in Path.glob yields directories only.
        hits = [Path(p) for p in glob.glob(g, root_dir=str(top), recursive=True, include_hidden=True)
                if (top / p).is_file() and ".git" not in Path(p).parts]
        if not hits:
            raise Refusal(f"BLOCKED — --path {g!r} matches no file; write the acceptance tests first")
        files |= {p.as_posix() for p in hits}
    return sorted(files)


def rules_for(globs: list[str]) -> list[str]:
    # the receipt is protected like the tests: verify trusts it, so an edit tool must not touch it
    return [f"{tool}(/{g})" for g in [*globs, RECEIPT.as_posix()] for tool in ("Edit", "Write")]


def deny_list(settings: dict) -> list:
    perms = settings.setdefault("permissions", {})
    if not isinstance(perms, dict) or not isinstance(perms.setdefault("deny", []), list):
        raise Refusal("BLOCKED — .claude/settings.json has a `permissions.deny` that is not a list — nothing was changed")
    return perms["deny"]


def commit_meta(top: Path, message: str) -> None:
    git(top, "add", "-f", "--", str(SETTINGS), str(RECEIPT))
    git(top, "commit", "-q", "-m", message, "--", str(SETTINGS), str(RECEIPT))


def cmd_lock(top: Path, feature: str, globs: list[str]) -> int:
    receipt = read_receipt(top, {"locks": []})
    settings = read_json(top / SETTINGS, {})
    deny = deny_list(settings)
    if any(lk.get("feature") == feature for lk in receipt.setdefault("locks", [])):
        raise Refusal(f"BLOCKED — {feature!r} is already locked; run verify, or unlock it first (only when the user asks)")
    files = expand(top, globs)
    git(top, "add", "--", *files)
    if git(top, "diff", "--cached", "--name-only", "--", *files).strip():
        git(top, "commit", "-q", "-m", f"test(acceptance): lock {feature}", "--", *files)
    commit = git(top, "rev-parse", "HEAD").strip()
    rules = rules_for(globs)
    added = [r for r in rules if r not in deny]
    deny.extend(added)
    receipt["locks"].append({"feature": feature, "commit": commit, "paths": globs, "files": files,
                             "rules": rules, "added": added,
                             "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    write_json(top / SETTINGS, settings)
    write_json(top / RECEIPT, receipt)
    try:
        commit_meta(top, f"chore(acceptance): deny edits to {feature} tests")
    except Refusal as exc:
        raise Refusal(f"BLOCKED — the test commit {commit[:12]} was made but committing the deny rules and "
                      f"receipt failed ({getattr(exc, 'detail', str(exc))}); fix the cause and commit "
                      f"{SETTINGS} and {RECEIPT} by hand (git add -f), or `git reset --soft HEAD~1` to "
                      f"undo the test commit")
    print(f"locked {feature}: {len(files)} file(s) at {commit[:12]}; deny rules: {', '.join(rules)}")
    return 0


def receipt_differs(top: Path) -> bool:
    """True when the receipt is modified (staged or not) or not yet committed at all."""
    if subprocess.run(["git", "cat-file", "-e", f"HEAD:{RECEIPT.as_posix()}"], cwd=top,
                      capture_output=True).returncode != 0:
        return True
    return bool(git(top, "diff", "--name-only", "HEAD", "--", f":(literal){RECEIPT.as_posix()}").strip())


def cmd_verify(top: Path, feature: str | None) -> int:
    receipt = read_receipt(top, None)
    if receipt is None:
        print(f"no acceptance lock in this project ({RECEIPT} is missing)", file=sys.stderr)
        return 2
    locks = [lk for lk in receipt.get("locks", []) if feature in (None, lk.get("feature"))]
    if feature is not None and not locks:
        print(f"no acceptance lock named {feature!r}", file=sys.stderr)
        return 2
    changed = []
    for lk in locks:
        if not lk.get("files"):
            continue
        out = git(top, "diff", "-z", "--name-only", lk["commit"], "--", *[f":(literal){f}" for f in lk["files"]])
        changed += [f"CHANGED {lk['feature']} {f}" for f in out.split("\0") if f]
    if receipt_differs(top):
        changed.append(f"CHANGED receipt {RECEIPT.as_posix()}")
    if changed:
        print("\n".join(changed))
        print("A locked acceptance test (or the receipt) differs from what the user approved. Restore it "
              "(`git checkout <commit> -- <file>`), or stop and tell the user which test is wrong and why.",
              file=sys.stderr)
        return 1
    print(f"acceptance tests unchanged: {', '.join(lk['feature'] for lk in locks) or 'no locks'}")
    return 0


def cmd_unlock(top: Path, feature: str) -> int:
    receipt = read_receipt(top, None)
    lock = next((lk for lk in (receipt or {}).get("locks", []) if lk.get("feature") == feature), None)
    if lock is None:
        raise Refusal(f"BLOCKED — no acceptance lock named {feature!r}")
    settings = read_json(top / SETTINGS, {})
    deny = deny_list(settings)
    others = [lk for lk in receipt["locks"] if lk is not lock]
    for rule in lock.get("added", []):
        heir = next((lk for lk in others if rule in lk.get("rules", [])), None)
        if heir is not None:
            heir.setdefault("added", []).append(rule)    # still needed: ownership moves
        elif rule in deny:
            deny.remove(rule)
    if not deny:
        del settings["permissions"]["deny"]
    if not settings.get("permissions"):
        settings.pop("permissions", None)
    receipt["locks"] = others
    write_json(top / SETTINGS, settings)
    write_json(top / RECEIPT, receipt)
    commit_meta(top, f"chore(acceptance): unlock {feature} tests")
    print(f"unlocked {feature}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("lock")
    lk.add_argument("--feature", required=True)
    lk.add_argument("--path", action="append", required=True, metavar="GLOB")
    vf = sub.add_parser("verify")
    vf.add_argument("--feature")
    ul = sub.add_parser("unlock")
    ul.add_argument("--feature", required=True)
    for p in (lk, vf, ul):
        p.add_argument("--project-dir", default=".")
    a = ap.parse_args(argv)
    try:
        top = toplevel(Path(a.project_dir).expanduser().resolve())
        if a.cmd == "lock":
            return cmd_lock(top, check_feature(a.feature), a.path)
        if a.cmd == "verify":
            return cmd_verify(top, a.feature)
        return cmd_unlock(top, check_feature(a.feature))
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(f"INTERNAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
