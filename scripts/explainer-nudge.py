#!/usr/bin/env python3
"""PostToolUse hook: after a spec or plan is written, remind the session to make its
explainer page (`/superpowers-gstack:htmlify explain`).

Fires on Write/Edit/MultiEdit of `docs/superpowers/specs/*.md` or
`docs/superpowers/plans/*.md` (not progress.md, not dotfiles). It only adds context
for the model: it renders nothing, opens nothing and never blocks. It stays silent

  - when the explainer next to the document is newer than the document (local target);
  - when it already reminded this session about this document and no explainer has been
    written since: a spec gets edited many times during its self-review, and one
    reminder per draft is enough. A fresh explainer that goes stale again earns one
    more reminder.

The target comes from the project's `.gstack/explainer` (`local` or `artifact`; no
file is local). An artifact page leaves no file to compare against, so there the
reminder comes once per document per session.

Any error is swallowed: a hook that crashes on every file write is worse than one
that misses a reminder. Exit 0 always.
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

SKIP_NAMES = {"progress.md", "handoff.md"}


def doc_kind(path: Path):
    """'spec' or 'plan' for a document this hook is about, else None."""
    if path.suffix != ".md" or path.name.startswith(".") or path.name in SKIP_NAMES:
        return None
    parts = path.parts
    if len(parts) < 4 or parts[-3:-1] not in (("superpowers", "specs"), ("superpowers", "plans")) \
            or parts[-4] != "docs":
        return None
    return "spec" if parts[-2] == "specs" else "plan"


def target_of(docs_parent: Path) -> str:
    """The pin nearest above the docs folder, stopping at the repository root: a
    project whose docs sit in a subfolder keeps its `.gstack/` at the top."""
    for d in (docs_parent, *docs_parent.parents):
        pin = d / ".gstack" / "explainer"
        if pin.is_file():
            try:
                value = pin.read_text().removesuffix("\n")
            except OSError:
                return "local"
            return value if value in ("local", "artifact") else "local"
        if (d / ".git").exists():
            break
    return "local"


def state_file(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "unknown")[:80]
    return Path(tempfile.gettempdir()) / "superpowers-gstack-explainer" / f"{safe}.json"


def decide(event: dict):
    """The reminder text, or None. Updates the per-session state as a side effect."""
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or os.getcwd()) / path
    path = path.resolve()
    kind = doc_kind(path)
    if kind is None or not path.is_file():
        return None
    root = path.parents[3]   # <root>/docs/superpowers/<specs|plans>/<file>.md
    target = target_of(root)
    html = path.with_suffix(".html")
    html_mtime = html.stat().st_mtime if html.is_file() else -1.0
    if target == "local" and html_mtime >= path.stat().st_mtime:
        return None

    # Read-modify-write without a lock: two hooks racing in one session can drop each
    # other's entry. The cost is one extra reminder later, never a missing one, since
    # the reminder below is printed whatever happens to the state.
    sf = state_file(event.get("session_id", ""))
    try:
        state = json.loads(sf.read_text())
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    key = str(path)
    if key in state and state[key] == html_mtime:
        return None
    state[key] = html_mtime
    sf.parent.mkdir(parents=True, exist_ok=True)
    # one file per session; drop the ones a week old so the folder does not grow forever
    for old in sf.parent.glob("*.json"):
        try:
            if time.time() - old.stat().st_mtime > 7 * 86400:
                old.unlink()
        except OSError:
            pass
    # a unique temp name (mode 0600): parallel Edit calls in one session run this hook concurrently
    fd, tmp = tempfile.mkstemp(dir=sf.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(state))
    os.replace(tmp, sf)

    # the path as the session can use it: relative to its cwd when inside it
    try:
        shown = path.relative_to(Path(event.get("cwd") or os.getcwd()).resolve())
    except ValueError:
        shown = path
    where = ("next to it as " + html.name) if target == "local" else "as an Artifact page"
    state_word = "has no explainer page yet" if html_mtime < 0 or target == "artifact" \
        else "is newer than its explainer page"
    return (f"superpowers-gstack: the {kind} `{shown}` {state_word}. When the document is "
            f"finished (after its self-review and any review lenses, before you hand it to the user "
            f"to review), "
            f"invoke `/superpowers-gstack:htmlify explain {shown}`. It goes {where} "
            f"(`.gstack/explainer`: {target}). Do not stop to ask first.")


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
        text = decide(event)
    except Exception:
        return 0
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
