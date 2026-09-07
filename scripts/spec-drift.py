#!/usr/bin/env python3
"""spec-drift — the mechanical half of /superpowers-gstack:spec-drift.

The skill itself is prose: it reads gstack's /ship Step 8 section
(~/.claude/skills/gstack/ship/sections/plan-completion.md) from disk and executes
it standalone. This script is everything about that which must NOT be left to a
model's judgement:

  check    the upstream section's sha256 matches the committed pin — exit 0 on
           match, 2 on mismatch / missing upstream / missing or corrupt pin.
           The skill refuses to run on anything but 0.
  repin    show the unified diff between the pinned snapshot and the upstream
           section (exit 3: confirmation required); with --yes write the new
           snapshot + pin.json (exit 0). No difference: nothing to do, exit 0.

Why a snapshot and not only a hash: --repin must SHOW what changed upstream
before anyone accepts it. A guard that is overridden routinely without showing
its diff trains away its own effect (spec, Fase 1). The snapshot is never
executed — the skill always reads the upstream path.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PIN_DIR = REPO / "skills" / "spec-drift"
DEFAULT_UPSTREAM = (Path.home() / ".claude" / "skills" / "gstack"
                    / "ship" / "sections" / "plan-completion.md")
SNAPSHOT_NAME = "plan-completion.md"   # lives in <pin-dir>/pin/
PIN_NAME = "pin.json"

# Text the wrapper's overrides name. A section that hashes fine but lost one of
# these would make the skill run Step 8.1 too, or find no Gate Logic to override.
ANCHORS = (
    "## Step 8: Plan Completion Audit",
    "## Step 8.1",
    "### Plan File Discovery",
    "### Gate Logic",
    "<base>",
    "Include in PR body",
    "Parent processing",
    '"total_items"',
)

EXIT_OK, EXIT_CANNOT, EXIT_CONFIRM = 0, 2, 3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def missing_anchors(text: str) -> list[str]:
    return [a for a in ANCHORS if a not in text]


def gstack_version(upstream: Path) -> str:
    # <gstack>/ship/sections/plan-completion.md -> <gstack>/VERSION
    v = upstream.resolve().parents[2] / "VERSION"
    return v.read_text().strip() if v.is_file() else "unknown"


def load_pin(pin_dir: Path) -> dict | None:
    """None when there is no pin file; {} when the file is not a pin-shaped object
    (unparseable, or valid JSON of another shape) — the caller reports PIN CORRUPT
    for {} rather than letting `.get` or a slice raise into an exit-1 traceback."""
    p = pin_dir / PIN_NAME
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return obj if isinstance(obj, dict) else {}


def cmd_check(a) -> int:
    upstream, pin_dir = Path(a.upstream).expanduser(), Path(a.pin_dir)
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream} — is gstack installed? "
              f"(git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack)",
              file=sys.stderr)
        return EXIT_CANNOT
    pin = load_pin(pin_dir)
    if pin is None:
        print(f"NO PIN: {pin_dir / PIN_NAME} does not exist — review the section with "
              f"`python3 scripts/spec-drift.py repin`, then accept it with --yes --sha",
              file=sys.stderr)
        return EXIT_CANNOT
    pinned = pin.get("sha256")
    pinned = pinned if isinstance(pinned, str) else ""
    snap = pin_dir / "pin" / SNAPSHOT_NAME
    try:
        snap_ok = bool(pinned) and snap.is_file() and sha256(snap) == pinned
    except OSError:
        snap_ok = False
    if not snap_ok:
        print(f"PIN CORRUPT: {snap} does not match {PIN_NAME} sha256 {pinned[:12] or '?'} — "
              f"pin.json and its snapshot are committed together; re-run repin",
              file=sys.stderr)
        return EXIT_CANNOT
    try:
        actual = sha256(upstream)
        text = upstream.read_text()
    except OSError as exc:
        print(f"UPSTREAM UNREADABLE: {upstream}: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    if actual != pinned:
        print("PIN MISMATCH: the upstream section changed shape.\n"
              f"  upstream  {upstream}\n"
              f"  sha256    {actual[:12]} (now) vs {pinned[:12]} "
              f"(pinned {pin.get('pinned_at')}, gstack {pin.get('gstack_version')})\n"
              f"  gstack    {gstack_version(upstream)} installed\n"
              "Verify the wrapper's overrides still fit the section, then: "
              "python3 scripts/spec-drift.py repin", file=sys.stderr)
        return EXIT_CANNOT
    missing = missing_anchors(text)
    if missing:
        print(f"ANCHORS MISSING: {', '.join(missing)} — the pinned section no longer carries "
              "text the wrapper's overrides name; fix skills/spec-drift/SKILL.md, then re-pin",
              file=sys.stderr)
        return EXIT_CANNOT
    print(f"PIN OK sha256={actual[:12]} gstack={pin.get('gstack_version')} upstream={upstream}")
    return EXIT_OK


def cmd_repin(a) -> int:
    upstream, pin_dir = Path(a.upstream).expanduser(), Path(a.pin_dir)
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream}", file=sys.stderr)
        return EXIT_CANNOT
    snap = pin_dir / "pin" / SNAPSHOT_NAME
    try:
        old = snap.read_text().splitlines(keepends=True) if snap.is_file() else []
        new_text = upstream.read_text()
        current = sha256(upstream)
    except OSError as exc:
        print(f"UPSTREAM UNREADABLE: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    new = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old, new, fromfile=f"pinned/{SNAPSHOT_NAME}",
                                     tofile=str(upstream)))
    pin = load_pin(pin_dir) or {}
    missing = missing_anchors(new_text)
    if not diff and pin.get("sha256") == current and not missing:
        print("PIN UNCHANGED: upstream matches the pin — nothing to do")
        return EXIT_OK
    if not a.yes:
        sys.stdout.writelines(diff)
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        if missing:
            print(f"\nREPIN BLOCKED: ANCHORS MISSING: {', '.join(missing)} — the wrapper's "
                  "overrides name text that no longer exists upstream; fix "
                  "skills/spec-drift/SKILL.md before re-pinning", file=sys.stderr)
            return EXIT_CANNOT
        print("\nANCHORS: all present")
        print(f"REPIN REQUIRES CONFIRMATION: +{added} -{removed} lines. Read the diff above, "
              f"verify the wrapper's overrides still match, then re-run with --yes --sha {current[:12]}")
        return EXIT_CONFIRM
    if missing:
        print(f"REPIN REFUSED: ANCHORS MISSING: {', '.join(missing)}", file=sys.stderr)
        return EXIT_CANNOT
    # --yes is bound to the bytes the diff run showed. Between that run and this
    # one a weekly gstack update can rewrite the file; accepting whatever is on
    # disk now would pin bytes nobody read.
    # At least the 12 chars the diff run printed: a 1-char "prefix" matches 1/16
    # of all digests, which is a guess, not a receipt.
    if not a.sha or len(a.sha) < 12 or not current.startswith(a.sha):
        print(f"REPIN REFUSED: --yes must carry the --sha printed by the diff run, 12+ hex chars "
              f"(upstream is now {current[:12]}, got {a.sha or 'nothing'}). "
              "Re-run repin without --yes and read the diff again.", file=sys.stderr)
        return EXIT_CANNOT
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(upstream.read_bytes())
    digest = sha256(upstream)
    (pin_dir / PIN_NAME).write_text(json.dumps({
        "source": "garrytan/gstack (MIT) — ship/sections/plan-completion.md; snapshot is for --repin's diff only, never executed",
        "sha256": digest,
        "gstack_version": gstack_version(upstream),
        "pinned_at": date.today().isoformat(),
    }, indent=2) + "\n")
    print(f"PINNED sha256={digest[:12]} gstack={gstack_version(upstream)} — "
          f"commit {pin_dir / PIN_NAME} and {snap} together")
    return EXIT_OK


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="spec-drift.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("repin", cmd_repin)):
        s = sub.add_parser(name)
        s.add_argument("--upstream", default=str(DEFAULT_UPSTREAM),
                       help="the gstack section to pin (default: %(default)s)")
        s.add_argument("--pin-dir", default=str(DEFAULT_PIN_DIR),
                       help="directory holding pin.json and pin/ (default: the skill)")
        s.set_defaults(fn=fn)
    sub.choices["repin"].add_argument("--yes", action="store_true",
                                      help="accept the diff shown by a previous run and write the pin")
    sub.choices["repin"].add_argument("--sha", default=None,
                                      help="sha256 prefix printed by the diff run; required with --yes")
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
