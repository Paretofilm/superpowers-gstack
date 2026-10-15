#!/usr/bin/env python3
"""swiftui-view-gate helpers.

  view-gate.py nudge              PostToolUse hook (JSON on stdin). Two jobs:
      - a Write/Edit/MultiEdit on a SwiftUI view file earns one reminder to run
        `/superpowers-gstack:swiftui-view-gate`; further view edits stay quiet until a
        HIG/accessibility/Liquid Glass lint has run, because an edit made after a lint
        makes that lint stale and earns a new reminder;
      - a call to review_macos_hig / review_accessibility / review_liquid_glass is
        recorded for that purpose.
      It only adds context for the model: never blocks, never raises. Exit 0 always.

  view-gate.py files --base REF   print the view files changed between REF and HEAD
      (plus uncommitted changes), one per line. Exit 0 with no output when none;
      exit 2 with `BLOCKED — …` when REF does not resolve or this is not a repository.

A view file is a `.swift` file that declares a type conforming to `View`, returns
`some View`, or lives under `Views/` or `Components/`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LINT_TOOLS = re.compile(r"review_(macos_hig|accessibility|liquid_glass)$")
CONFORMS_TO_VIEW = re.compile(r"\b(?:struct|class|extension)\s+\w+\s*:[^{\n]*\bView\b")
SOME_VIEW = re.compile(r"\bsome\s+View\b")
VIEW_DIRS = {"Views", "Components"}
MAX_READ = 512_000


def is_view_file(path: Path, text: str | None = None) -> bool:
    if path.suffix != ".swift":
        return False
    if VIEW_DIRS & set(path.parts[:-1]):
        return True
    if text is None:
        try:
            with path.open("rb") as fh:
                text = fh.read(MAX_READ).decode("utf-8", "replace")
        except OSError:
            return False
    return bool(CONFORMS_TO_VIEW.search(text) or SOME_VIEW.search(text))


def state_file(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "unknown")[:80]
    return Path(tempfile.gettempdir()) / "superpowers-gstack-view-gate" / f"{safe}.json"


def load_state(sf: Path) -> dict:
    try:
        state = json.loads(sf.read_text())
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(sf: Path, state: dict) -> None:
    sf.parent.mkdir(parents=True, exist_ok=True)
    for old in sf.parent.glob("*.json"):
        try:
            if time.time() - old.stat().st_mtime > 7 * 86400:
                old.unlink()
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(dir=sf.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(state))
    os.replace(tmp, sf)


def decide(event: dict) -> str | None:
    """The reminder text, or None. Updates the per-session state as a side effect."""
    sf = state_file(str(event.get("session_id", "")))
    tool = str(event.get("tool_name", ""))
    if LINT_TOOLS.search(tool):
        state = load_state(sf)
        state["linted_at"] = time.time()
        save_state(sf, state)
        return None
    raw = (event.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or os.getcwd()) / path
    path = path.resolve()
    if not path.is_file() or not is_view_file(path):
        return None
    state = load_state(sf)
    linted = float(state.get("linted_at", 0) or 0)
    reminded = float(state.get("reminded_at", 0) or 0)
    if reminded > linted:
        return None   # already reminded since the last lint: one reminder per unlinted streak
    state["reminded_at"] = time.time()
    save_state(sf, state)
    try:
        shown = path.relative_to(Path(event.get("cwd") or os.getcwd()).resolve())
    except ValueError:
        shown = path
    return (f"superpowers-gstack: `{shown}` is a SwiftUI view. A UI change is not done until it has "
            f"been looked up, linted and seen. Before you report it done, follow "
            f"`/superpowers-gstack:swiftui-view-gate`: render it in its real container, run "
            f"`review_macos_hig` / `review_accessibility` (and `review_liquid_glass` on a Liquid Glass "
            f"target), and end the report with a `View gate:` line. The linters are pattern checks, "
            f"so a clean result is not a look. This is a reminder, not a stop; do not ask first.")


def nudge() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
        text = decide(event)
    except Exception:
        return 0
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": text}}))
    return 0


def changed_view_files(base: str) -> list[str]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout

    try:
        top = Path(git("rev-parse", "--show-toplevel").strip())
        git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit(f"BLOCKED — cannot resolve {base!r}, or this is not a git repository")
    names: set[str] = set()
    for args in (("diff", "--name-only", "--diff-filter=d", f"{base}...HEAD"),
                 ("diff", "--name-only", "--diff-filter=d", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        try:
            names.update(n for n in git(*args).splitlines() if n.endswith(".swift"))
        except subprocess.CalledProcessError:
            continue
    return sorted(n for n in names if is_view_file(top / n))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="view-gate.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("nudge")
    f = sub.add_parser("files")
    f.add_argument("--base", required=True)
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if a.cmd == "nudge":
        return nudge()
    try:
        for n in changed_view_files(a.base):
            print(n)
    except SystemExit as exc:
        print(exc.code, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
