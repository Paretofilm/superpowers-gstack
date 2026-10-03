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

Threat model. The lock defends against an agent that makes mistakes or takes shortcuts
(edits a test to turn it green, forgets a file, adds a conftest that skips the tests, edits
the receipt, re-points it at a newer commit). It does NOT defend against one that
deliberately rewrites history, fakes a commit subject, or edits `.git` directly. verify
detects the cheap, plausible tampering:
  - a locked file differs from its lock commit (working tree, index, HEAD), or carries an
    assume-unchanged / skip-worktree flag;
  - the receipt differs from HEAD, or a commit that touched it since the lock was not made
    by this script (subject not `chore(acceptance): ` / `test(acceptance): ` — a faked
    subject passes), or the lock commit is no longer an ancestor of HEAD;
  - a new file appears under a locked glob that no lock lists (files git ignores, `__pycache__`
    and `.DS_Store` are exempt).
`lock` commits whatever the matched files currently contain (it does not require them clean)
and refuses a symlink: lock the real file. The user approves an overview, not the bytes, so
the overview must list the exact files and the lock commit SHA is reported afterwards.

A deny rule stops the Edit and Write tools, not `sed` through Bash. `verify` is the
gate; the rules make the honest path the easy one.

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
COMMIT_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
OWN_SUBJECTS = ("chore(acceptance): ", "test(acceptance): ")
EXEMPT_NEW = (".DS_Store",)


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


def require_commit(top: Path, lk: dict) -> str:
    c = lk["commit"]
    p = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"{c}^{{commit}}"],
                       cwd=top, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"BLOCKED — lock commit {c[:12]} for {lk['feature']} is not in this repository "
                      f"(squash-merged or rewritten?); the lock cannot be verified — ask the user whether "
                      f"to unlock/re-lock")
    return c


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
            elif not COMMIT_RE.match(lk["commit"]):
                bad = f"lock #{i} has a `commit` that is not a full commit hash"
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
        for h in hits:
            if (top / h).is_symlink():
                raise Refusal(f"BLOCKED — {h.as_posix()} is a symlink; lock the real file")
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


def settings_state(top: Path) -> str:
    """`tracked`, `local-only` (git-ignored and untracked: it may hold secrets, so it is never
    force-added) or `plain` (untracked, not ignored)."""
    if subprocess.run(["git", "ls-files", "--error-unmatch", "--", str(SETTINGS)], cwd=top,
                      capture_output=True).returncode == 0:
        return "tracked"
    if subprocess.run(["git", "check-ignore", "-q", "--", str(SETTINGS)], cwd=top,
                      capture_output=True).returncode == 0:
        return "local-only"
    return "plain"


def commit_meta(top: Path, message: str) -> None:
    git(top, "add", "-f", "--", str(RECEIPT))          # the receipt is the one file forced past .gitignore
    paths = [str(RECEIPT)]
    state = settings_state(top)
    if state == "local-only":
        print(f"note: {SETTINGS} is git-ignored, so the deny rules are local only and not committed")
    else:
        # `add -u` for a tracked file: plain `add` refuses a tracked path under an ignored directory
        git(top, "add", *(["-u"] if state == "tracked" else []), "--", str(SETTINGS))
        paths.append(str(SETTINGS))
    git(top, "commit", "-q", "-m", message, "--", *paths)


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


def matched_files(top: Path, globs: list[str]) -> set[str]:
    """Files a recorded glob matches now, symlinks included. A recorded glob that is absolute
    or climbs out is ignored (the script never wrote one)."""
    out: set[str] = set()
    for g in globs:
        if g.startswith("/") or ".." in Path(g).parts:
            continue
        for p in glob.glob(g, root_dir=str(top), recursive=True, include_hidden=True):
            pp = Path(p)
            if ".git" in pp.parts or "__pycache__" in pp.parts or pp.name in EXEMPT_NEW:
                continue
            if (top / p).is_file() or (top / p).is_symlink():
                out.add(pp.as_posix())
    return out


def git_ignored(top: Path, files: list[str]) -> set[str]:
    if not files:
        return set()
    p = subprocess.run(["git", "check-ignore", "-z", "--stdin"], cwd=top, input="\0".join(files) + "\0",
                       capture_output=True, text=True)
    return {f for f in p.stdout.split("\0") if f}


def foreign_receipt_commits(top: Path, commit: str) -> list[tuple[str, str]]:
    out = git(top, "log", "--format=%H%x09%s", "--end-of-options", f"{commit}..HEAD", "--",
              f":(literal){RECEIPT.as_posix()}")
    bad = []
    for line in out.splitlines():
        sha, _, subject = line.partition("\t")
        if not subject.startswith(OWN_SUBJECTS):
            bad.append((sha, subject))
    return bad


def cmd_verify(top: Path, feature: str | None) -> int:
    receipt = read_receipt(top, None)
    if receipt is None:
        print(f"no acceptance lock in this project ({RECEIPT} is missing)", file=sys.stderr)
        return 2
    locks = [lk for lk in receipt.get("locks", []) if feature in (None, lk.get("feature"))]
    if feature is not None and not locks:
        print(f"no acceptance lock named {feature!r}", file=sys.stderr)
        return 2
    for lk in locks:
        require_commit(top, lk)
    changed: list[str] = []
    for lk in locks:
        commit = lk["commit"]
        files = lk.get("files") or []
        if files:
            lit = [f":(literal){f}" for f in files]
            out = git(top, "diff", "-z", "--name-only", "--end-of-options", commit, "--", *lit)
            changed += [f"CHANGED {lk['feature']} {f}" for f in out.split("\0") if f]
            flagged = git(top, "ls-files", "-v", "-z", "--", *lit)
            for ent in flagged.split("\0"):
                if ent and (ent[0].islower() or ent[0] == "S"):
                    changed.append(f"CHANGED {lk['feature']} {ent[2:]} (assume-unchanged/skip-worktree flag)")
        if subprocess.run(["git", "merge-base", "--is-ancestor", "--end-of-options", commit, "HEAD"],
                          cwd=top, capture_output=True).returncode != 0:
            changed.append(f"CHANGED {lk['feature']} lock commit {commit[:12]} is not an ancestor of HEAD")
    if receipt_differs(top):
        changed.append(f"CHANGED receipt {RECEIPT.as_posix()}")
    seen: set[str] = set()
    for lk in locks:
        for sha, subject in foreign_receipt_commits(top, lk["commit"]):
            if sha not in seen:
                seen.add(sha)
                changed.append(f"CHANGED receipt {RECEIPT.as_posix()} (changed by commit {sha[:12]} "
                               f"\"{subject}\", not by this script)")
    known = {f for lk in receipt.get("locks", []) for f in lk.get("files", [])}
    for lk in locks:
        new = matched_files(top, lk.get("paths", [])) - known
        new -= git_ignored(top, sorted(new))
        changed += [f"CHANGED {lk['feature']} {f} (new file under a locked path)" for f in sorted(new)]
    if changed:
        print("\n".join(dict.fromkeys(changed)))
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
