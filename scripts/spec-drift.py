#!/usr/bin/env python3
"""spec-drift — the mechanical half of /superpowers-gstack:spec-drift.

The skill itself is prose: it reads gstack's /ship Step 8 section
(~/.claude/skills/gstack/ship/sections/plan-completion.md) from disk and executes
it standalone. This script is everything about that which must NOT be left to a
model's judgement:

  check    the upstream section's sha256 matches the committed pin, and the
           section still carries every ANCHORS heading/string — exit 0 on
           match, 2 on mismatch / missing anchor / missing upstream / missing
           or corrupt pin. The skill refuses to run on anything but 0.
  repin    show the unified diff between the pinned snapshot and the upstream
           section (exit 3: confirmation required; the run prints the --sha
           receipt --yes must carry and records it beside the pin — without a
           diff run, with a stale receipt, or while an anchor is missing,
           --yes is refused with exit 2); with --yes --sha <receipt> write the new
           snapshot + pin.json (exit 0). No difference: nothing to do, exit 0.
  verdict  map Step 8's last-line JSON to the standalone exit code:
           0 clean (every item DONE or CHANGED), 1 drift (anything else),
           2 could not audit (no JSON, malformed, or total_items == 0).

Why a snapshot and not only a hash: --repin must SHOW what changed upstream
before anyone accepts it. A guard that is overridden routinely without showing
its diff trains away its own effect (spec, Fase 1). The snapshot is never
executed — the skill always reads the upstream path.

Fail-closed by construction: every unexpected state is a named reason on stderr
and exit 2 — never exit 0, never a Python traceback. One read of the upstream
bytes feeds the hash, the anchor check, the diff, the receipt and the snapshot,
so a file rewritten between two reads cannot be pinned half-old.

Exit codes: 0 ok / unchanged / clean; 1 drift (verdict only — and only together
with a `SPEC-DRIFT: DRIFT (exit 1)` line on stdout: a bare exit 1 is the
interpreter itself failing, and a caller must read it as could-not-run); 2 could
not run or refused (check/repin name why on stderr: UPSTREAM MISSING, UPSTREAM
UNREADABLE, NO PIN, PIN CORRUPT, PIN MISMATCH, ANCHORS MISSING, REPIN BLOCKED,
RECEIPT WRITE FAILED, REPIN REFUSED, PIN WRITE FAILED, PIN DIR INVALID, USAGE
ERROR, INTERNAL; verdict
prints its `SPEC-DRIFT: COULD-NOT-RUN (exit 2)` line on stdout like its other two
outcomes); 3 repin needs confirmation (the receipt line is the LAST line of
stdout — do not truncate it).
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()          # named in messages: a cwd-relative path is wrong from a user's project
DEFAULT_PIN_DIR = REPO / "skills" / "spec-drift"
UPSTREAM_REL = Path(".claude") / "skills" / "gstack" / "ship" / "sections" / "plan-completion.md"
SNAPSHOT_SUBDIR = "pin"                 # <pin-dir>/pin/<SNAPSHOT_NAME>
SNAPSHOT_NAME = "plan-completion.md"
PIN_NAME = "pin.json"
RECEIPT_NAME = ".repin-receipt"         # written by a diff run, consumed by --yes; never committed
PIN_KEYS = ("source", "sha256", "gstack_version", "pinned_at")
ENCODING = "utf-8"
MAX_UPSTREAM_BYTES = 4 * 1024 * 1024    # the real section is ~15 KB; anything near this is not it

# Text the wrapper's overrides name: (name shown in messages, regex). Headings
# are line-anchored (an optional "> " blockquote prefix allowed) so a copy of the
# words inside a comment or a code fence does not satisfy them, and Step 8 must
# precede Step 8.1 because the wrapper stops at the second heading.
ANCHORS = (
    ("## Step 8: Plan Completion Audit", r"^(> )?## Step 8: Plan Completion Audit"),
    ("## Step 8.1", r"^(> )?## Step 8\.1(?![0-9])"),
    ("### Plan File Discovery", r"^(> )?### Plan File Discovery"),
    ("### Gate Logic", r"^(> )?### Gate Logic"),
    ("<base>", r"<base>"),
    ("Include in PR body", r"Include in PR body"),
    ("Parent processing", r"Parent processing"),
    ('"total_items"', r'"total_items"'),
    # Override 8 suppresses this step: /ship may run a repo's own validator script
    # because it ships that repo's branch, but this skill audits branches nobody
    # is shipping. If upstream renames the step, the override stops suppressing
    # anything and the audit silently regains the right to execute repo code.
    # Line-anchored to the actual step, not the bare phrase: upstream could
    # otherwise rename or move the step while the words survive in a cross-
    # reference, and the override would stop suppressing anything silently.
    ("Validator detection", r"^(> )?\*\*Validator detection\.\*\*"),
)

# The two headings that delimit the executed span. Searched in the whole file;
# every other anchor must fall between them.
BOUNDARY = ("## Step 8: Plan Completion Audit", "## Step 8.1")

EXIT_OK, EXIT_DRIFT, EXIT_CANNOT, EXIT_CONFIRM = 0, 1, 2, 3
COUNT_KEYS = ("total_items", "done", "changed", "deferred", "unverifiable")
JSON_KEYS = COUNT_KEYS + ("summary",)
ALLOWED_EXTRA = ("partial",)   # the only key outside the contract with a checked meaning
SHA_PREFIX = 12   # chars of the digest printed as the --sha receipt; also the minimum --yes must carry

# Terminal-control, bidi and zero-width characters: escaped when the diff is
# shown, so a malicious upstream can neither repaint the confirmation prompt the
# human reads nor hide a change where no diff can render it. Everything below
# 0x20 except tab and newline — carriage return included: splitlines keeps a
# bare \r at the end of its line, and a terminal then returns to column 0 and
# lets the next diff line overwrite the one the reader just saw.
# The invisible set is Unicode's format category (Cf) whole, not a hand-picked
# subset of it. Two review rounds each found one more character the subset had
# missed (LRM/RLM/ALM, then U+2060 WORD JOINER); a guard whose membership is
# decided by whoever last thought about it is not a guard. Enumerated as ranges
# rather than derived from unicodedata at import (that is a 1.1M-codepoint scan
# on every run) — test_format_set_is_exactly_unicode_category_cf proves the
# enumeration equals the category, so it cannot drift from the standard silently.
_FORMAT = (
    "­؀-؅؜۝܏࢐࢑࣢᠎"
    "​-‏‪-‮⁠-⁤⁦-⁯﻿￹-￻"
    "\U000110bd\U000110cd\U00013430-\U0001343f\U0001bca0-\U0001bca3"
    "\U0001d173-\U0001d17a\U000e0001\U000e0020-\U000e007f"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\x80-\x9f" + _FORMAT + "]")
# Characters worth a warning with line numbers even after escaping: a reader
# skims a diff; an escaped zero-width joiner is easy to read past.
_INVISIBLE = re.compile("[" + _FORMAT + "]")
# PADDING ONLY — the edges of a line, never its interior. Stripping invisibles
# from the whole line REPAIRS hostile input instead of refusing it: a model (or
# whoever shaped its output) writing "do​ne" would have the key normalised
# to "done" and the line scored CLEAN. Verified reproducible, 2.52.0.
_INVISIBLE_PAD = re.compile(r"^[\s`" + _FORMAT + r"]+|[\s`" + _FORMAT + r"]+$")


def default_upstream() -> Path | None:
    """~/.claude/.../plan-completion.md, or None when $HOME cannot be determined
    (a container running as an arbitrary uid) — resolved lazily so --help and an
    explicit --upstream keep working there."""
    try:
        return Path.home() / UPSTREAM_REL
    except RuntimeError:
        return None


def resolve_paths(a) -> tuple[Path | None, Path | None]:
    upstream = Path(a.upstream).expanduser() if a.upstream else default_upstream()
    pin_dir = Path(a.pin_dir).expanduser().resolve() if a.pin_dir and a.pin_dir.strip() else None
    return upstream, pin_dir


def refuse_bad_paths(upstream: Path | None, pin_dir: Path | None) -> int | None:
    if upstream is None:
        print("UPSTREAM MISSING: no --upstream given and $HOME is unknown", file=sys.stderr)
        return EXIT_CANNOT
    if pin_dir is None:
        # Path('') is the cwd: a stray pin.json in a project root would satisfy check.
        print("PIN DIR INVALID: --pin-dir is empty", file=sys.stderr)
        return EXIT_CANNOT
    return None


def short(digest: str) -> str:
    return digest[:SHA_PREFIX]


def snapshot_path(pin_dir: Path) -> Path:
    return pin_dir / SNAPSHOT_SUBDIR / SNAPSHOT_NAME


def receipt_path(pin_dir: Path) -> Path:
    return pin_dir / RECEIPT_NAME


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_upstream(upstream: Path) -> tuple[bytes, str, str]:
    """One read: the bytes, their sha256, and their text. Everything downstream
    derives from these same bytes. Raises OSError / UnicodeDecodeError / ValueError
    for the caller to name."""
    if upstream.stat().st_size > MAX_UPSTREAM_BYTES:
        raise ValueError(f"larger than {MAX_UPSTREAM_BYTES} bytes")
    data = upstream.read_bytes()
    return data, sha256_bytes(data), data.decode(ENCODING)


def visible(line: str) -> str:
    def escape(m) -> str:
        c = ord(m.group())
        return f"\\u{c:04x}" if c <= 0xFFFF else f"\\U{c:08x}"
    return _CONTROL.sub(escape, line)


def missing_anchors(text: str) -> list[str]:
    """Names of anchors the text lacks.

    Only the two boundary headings are looked for in the whole file; everything
    else must appear INSIDE Step 8 — between its heading and Step 8.1, which is
    exactly the span the wrapper executes. A whole-file search proved nothing
    about that span: `<base>` also occurs in Step 8.2, so upstream could delete
    it from Step 8 and the anchor would still pass (Codex, 2.52.0). The three
    inner headings must also hold their order, or an override that targets one
    would land in the wrong part of the section."""
    pats = dict(ANCHORS)
    missing = [name for name in BOUNDARY if not re.search(pats[name], text, re.M)]
    if missing:
        return missing
    start = re.search(pats[BOUNDARY[0]], text, re.M).start()
    end = re.search(pats[BOUNDARY[1]], text, re.M).start()
    if end <= start:
        return ["section order (Step 8 must precede Step 8.1)"]
    span = text[start:end]
    missing = [name for name, pat in ANCHORS
               if name not in BOUNDARY and not re.search(pat, span, re.M)]
    if not missing:
        order = ("### Plan File Discovery", "Validator detection", "### Gate Logic")
        positions = [re.search(pats[name], span, re.M).start() for name in order]
        if positions != sorted(positions):
            missing.append("section order (Plan File Discovery > Validator "
                           "detection > Gate Logic, inside Step 8)")
    return missing


def gstack_version(upstream: Path) -> str:
    """The VERSION file of the gstack install that owns `upstream`, found by
    walking up to three levels from the file. "unknown" when absent, unreadable,
    or not a plain version token — third-party file content never reaches
    pin.json or stdout unsanitised."""
    try:
        for parent in list(upstream.resolve().parents)[:3]:
            v = parent / "VERSION"
            if v.is_file():
                first = v.read_text(encoding=ENCODING).splitlines()[0].strip() if v.stat().st_size else ""
                return first if re.fullmatch(r"[\w.+-]{1,40}", first) else "unknown"
    except (OSError, ValueError, IndexError):
        pass
    return "unknown"


def load_pin(pin_dir: Path) -> dict | None:
    """None when there is no pin file; {} when the file is not a pin-shaped object
    (unparseable, undecodable, or valid JSON of another shape) — the caller reports
    PIN CORRUPT for {} rather than letting `.get` or a slice raise into an exit-1
    traceback. JSONDecodeError and UnicodeDecodeError are both ValueError."""
    p = pin_dir / PIN_NAME
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding=ENCODING))
    except (ValueError, RecursionError, OSError):
        return {}
    return obj if isinstance(obj, dict) else {}


def pin_well_formed(pin: dict) -> bool:
    return all(isinstance(pin.get(k), str) and pin.get(k) for k in PIN_KEYS)


def cmd_check(a) -> int:
    upstream, pin_dir = resolve_paths(a)
    if (bad := refuse_bad_paths(upstream, pin_dir)) is not None:
        return bad
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream} — is gstack installed? "
              f"(git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack)",
              file=sys.stderr)
        return EXIT_CANNOT
    pin = load_pin(pin_dir)
    if pin is None:
        print(f"NO PIN: {pin_dir / PIN_NAME} does not exist — review the section with "
              f"`python3 {SELF} repin`, then accept it with --yes --sha",
              file=sys.stderr)
        return EXIT_CANNOT
    if not pin_well_formed(pin):
        print(f"PIN CORRUPT: {pin_dir / PIN_NAME} is not a pin (needs non-empty string fields "
              f"{', '.join(PIN_KEYS)}) — re-run repin", file=sys.stderr)
        return EXIT_CANNOT
    pinned = pin["sha256"]
    snap = snapshot_path(pin_dir)
    try:
        snap_ok = snap.is_file() and sha256(snap) == pinned
    except OSError:
        snap_ok = False
    if not snap_ok:
        print(f"PIN CORRUPT: {snap} does not match {PIN_NAME} sha256 {short(pinned)} — "
              f"pin.json and its snapshot are committed together; re-run repin",
              file=sys.stderr)
        return EXIT_CANNOT
    try:
        _, actual, text = read_upstream(upstream)
    except (OSError, ValueError) as exc:
        print(f"UPSTREAM UNREADABLE: {upstream}: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    if actual != pinned:
        print("PIN MISMATCH: the upstream section changed shape.\n"
              f"  upstream  {upstream}\n"
              f"  sha256    {short(actual)} (now) vs {short(pinned)} "
              f"(pinned {pin['pinned_at']}, gstack {pin['gstack_version']})\n"
              f"  gstack    {gstack_version(upstream)} installed\n"
              "Verify the wrapper's overrides still fit the section, then: "
              f"python3 {SELF} repin", file=sys.stderr)
        return EXIT_CANNOT
    missing = missing_anchors(text)
    if missing:
        print(f"ANCHORS MISSING: {', '.join(missing)} — the pinned section no longer carries "
              "text the wrapper's overrides name; fix skills/spec-drift/SKILL.md, then re-pin",
              file=sys.stderr)
        return EXIT_CANNOT
    print(f"PIN OK sha256={short(actual)} gstack={pin['gstack_version']} upstream={upstream}")
    return EXIT_OK


def _atomic_write(path: Path, data: bytes) -> None:
    """Write via a private temp file in the same directory, then os.replace — a
    reader never sees a half-written file, and two concurrent writers cannot
    share a temp name. A failed write leaves no temp behind."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        # mkstemp creates 0600 and os.replace keeps it; a committed, world-readable
        # file must not flip to owner-only on every repin. One stat, not
        # exists()-then-stat(): a file removed between the two would turn a
        # first write into PIN WRITE FAILED for no reason a reader could see.
        try:
            mode = path.stat().st_mode & 0o777
        except OSError:
            mode = 0o644
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def cmd_repin(a) -> int:
    upstream, pin_dir = resolve_paths(a)
    if (bad := refuse_bad_paths(upstream, pin_dir)) is not None:
        return bad
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream}", file=sys.stderr)
        return EXIT_CANNOT
    try:
        data, current, new_text = read_upstream(upstream)
    except (OSError, ValueError) as exc:
        print(f"UPSTREAM UNREADABLE: {upstream}: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    # The diff baseline is the snapshot ONLY when it is the one pin.json vouches
    # for. A snapshot that merely equals upstream — because someone copied the
    # file over it, or a write failed between the two files — would otherwise
    # produce an empty diff and a receipt for bytes nobody read (red team, 2.52.0).
    pin_loaded = load_pin(pin_dir)          # None: no file; {}: not a pin; dict: a pin
    pin = pin_loaded or {}
    pin_sha = pin["sha256"] if pin_well_formed(pin) else ""
    snap = snapshot_path(pin_dir)
    baseline_note = ""
    try:
        snap_bytes = snap.read_bytes() if snap.is_file() else b""
    except OSError as exc:
        snap_bytes, baseline_note = b"", f"SNAPSHOT UNREADABLE: {snap}: {exc}"
    baseline_ok = bool(pin_sha) and sha256_bytes(snap_bytes) == pin_sha
    old_bytes = snap_bytes if baseline_ok else b""
    if not baseline_ok and not baseline_note:
        baseline_note = ("NO PIN" if pin_loaded is None else
                         f"PIN CORRUPT: {PIN_NAME} is not a pin" if not pin_sha else
                         f"PIN CORRUPT: snapshot does not match {PIN_NAME}")
    try:
        old = old_bytes.decode(ENCODING).splitlines(keepends=True)
    except ValueError:
        old, old_bytes, baseline_note = [], b"", f"SNAPSHOT UNREADABLE: {snap}: not {ENCODING}"
    new = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old, new, fromfile=f"pinned/{SNAPSHOT_NAME}",
                                     tofile=str(upstream)))
    missing = missing_anchors(new_text)
    # "Unchanged" means the same thing check means: a vouched-for snapshot AND
    # pin.json both equal the upstream bytes. Judged on text alone, a CRLF
    # snapshot would be "unchanged" here and PIN CORRUPT in check — no way out.
    if baseline_ok and pin_sha == current and not missing:
        print("PIN UNCHANGED: upstream matches the pin — nothing to do")
        return EXIT_OK
    if not a.yes:
        if baseline_note:
            print(f"{baseline_note} — no usable baseline, so the whole section is shown as new lines")
        sys.stdout.writelines(visible(line) for line in diff)
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        if missing:
            print(f"\nREPIN BLOCKED: ANCHORS MISSING: {', '.join(missing)} — the wrapper's "
                  "overrides name text that no longer exists upstream; fix "
                  "skills/spec-drift/SKILL.md before re-pinning", file=sys.stderr)
            return EXIT_CANNOT
        if not diff:
            # Unreachable when the baseline is vouched for (equal text means equal
            # bytes means UNCHANGED above); kept so an empty diff can never carry a receipt.
            print("REPIN BLOCKED: nothing to show, yet the pin does not match upstream — "
                  "inconsistent state; re-run check", file=sys.stderr)
            return EXIT_CANNOT
        if (b"\r\n" in data) != (b"\r\n" in old_bytes):
            print("\nNOTE: line endings differ between the pinned snapshot and upstream (CRLF vs LF) "
                  "— every line shows as changed above even where the text is the same")
        invisible = [i for i, line in enumerate(new, 1) if _INVISIBLE.search(line)]
        if invisible:
            print(f"\nWARNING: INVISIBLE CHARS (zero-width, BOM or bidi controls) at line(s) "
                  f"{', '.join(map(str, invisible[:10]))} — a diff cannot show them; inspect the "
                  "bytes before accepting", file=sys.stderr)
        print("\nANCHORS: all present")
        print(f"REPIN REQUIRES CONFIRMATION: +{added} -{removed} lines. Read the diff above, "
              f"verify the wrapper's overrides still match, then re-run with --yes --sha {short(current)}")
        # The receipt certifies that a human SAW this diff, so it must not reach
        # disk until the whole message has actually left the process. stdout is
        # buffered: `repin | head` fails at flush, which used to happen AFTER the
        # receipt was written — leaving --yes able to accept never-shown bytes
        # with a --sha lifted from `check`'s output. Codex, 2.52.0; reproduced.
        try:
            sys.stdout.flush()
        except (BrokenPipeError, OSError) as exc:
            print(f"DIFF NOT DELIVERED: stdout closed before the diff was shown ({exc}) — "
                  "no receipt written; re-run with stdout attached", file=sys.stderr)
            return EXIT_CANNOT
        try:
            pin_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write(receipt_path(pin_dir), (current + "\n").encode(ENCODING))
        except OSError as exc:
            print(f"RECEIPT WRITE FAILED: {receipt_path(pin_dir)}: {exc}", file=sys.stderr)
            return EXIT_CANNOT
        return EXIT_CONFIRM
    if missing:
        print(f"REPIN REFUSED: ANCHORS MISSING: {', '.join(missing)}", file=sys.stderr)
        return EXIT_CANNOT
    # --yes is bound to the bytes a diff run showed: the receipt that run wrote
    # must exist, --sha must be a real prefix of it, and upstream must still hash
    # to it now. `check` also prints the current digest, so --sha alone would not
    # tie --yes to a diff run; the receipt file does. That is a procedural guard,
    # not proof: a caller who writes the file by hand from `check`'s output gets
    # past it. The guard exists for the model that runs the skill, whose every
    # file write is visible in its tool log — the diff run is the step it cannot
    # quietly skip.
    try:
        receipt = receipt_path(pin_dir).read_text(encoding=ENCODING).strip() \
            if receipt_path(pin_dir).is_file() else ""
    except (OSError, ValueError):
        receipt = ""
    if not receipt:
        print("REPIN REFUSED: no diff run recorded — run repin without --yes first and read "
              "the diff; --yes only accepts what that run showed", file=sys.stderr)
        return EXIT_CANNOT
    if not a.sha or len(a.sha) < SHA_PREFIX or not receipt.startswith(a.sha) \
            or receipt != current:
        print(f"REPIN REFUSED: --yes must carry the --sha printed by the diff run, {SHA_PREFIX}+ "
              f"hex chars (that run showed {short(receipt)}, upstream is now {short(current)}, "
              f"got {a.sha or 'nothing'}). Re-run repin without --yes and read the diff again.",
              file=sys.stderr)
        return EXIT_CANNOT
    version = gstack_version(upstream)
    pin_json = json.dumps({
        "source": "garrytan/gstack (MIT) — ship/sections/plan-completion.md; snapshot is for --repin's diff only, never executed",
        "sha256": current,
        "gstack_version": version,
        "pinned_at": date.today().isoformat(),
    }, indent=2) + "\n"
    try:
        snap.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(snap, data)
        _atomic_write(pin_dir / PIN_NAME, pin_json.encode(ENCODING))
        receipt_path(pin_dir).unlink(missing_ok=True)
    except OSError as exc:
        # Each file is replaced atomically; if the second replace failed the
        # snapshot is new and pin.json is old, which check reports as PIN CORRUPT.
        print(f"PIN WRITE FAILED: {exc} — nothing half-written; re-run repin", file=sys.stderr)
        return EXIT_CANNOT
    print(f"PINNED sha256={short(current)} gstack={version} — "
          f"commit {pin_dir / PIN_NAME} and {snap} together")
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """Usage errors keep argparse's exit 2 but carry a named token, so a caller
    that greps stderr for a reason does not mistake a quoting bug for a refusal."""

    def error(self, message):
        print(f"USAGE ERROR: {message}", file=sys.stderr)
        raise SystemExit(EXIT_CANNOT)


def _no_duplicate_keys(pairs):
    """json.loads keeps the LAST value of a repeated key, so a line that says
    `"done":2 … "done":4` would read as the green one. Refuse it instead."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def last_json_line(text: str) -> dict | None:
    """The last non-empty line, parsed as one JSON object — or None. Splits on
    "\\n" only (JSON strings may carry U+2028 and friends raw), ignores zero-width
    padding and a trailing ``` fence, and refuses duplicate keys. Text with bare
    "\\r" line endings is therefore one line and parses as nothing — fail closed,
    by design; a trailing "\\r" after the JSON (CRLF) is whitespace to json.

    Padding is stripped from the EDGES only. An invisible character inside the
    object refuses the line rather than being deleted out of it — deleting it
    would turn a key nobody typed into one the contract accepts."""
    for line in reversed(text.split("\n")):
        line = _INVISIBLE_PAD.sub("", line)
        if not line:
            continue
        if _INVISIBLE.search(line):
            return None
        try:
            obj = json.loads(line, object_pairs_hook=_no_duplicate_keys)
        except (ValueError, RecursionError):   # JSONDecodeError is a ValueError
            return None
        return obj if isinstance(obj, dict) else None
    return None


def _verdict(label: str, code: int, reason: str) -> int:
    """The one line a caller reads. Always stdout — the line IS the contract, and
    the printed number is the number returned, by construction.

    The reason is flattened to a single line and escaped before printing. It can
    carry text lifted from an untrusted JSON key, and a raw newline in one would
    print a second line: a forged `SPEC-DRIFT: CLEAN` under the real verdict,
    which is what a caller reading the last such line would believe. Codex,
    2.52.0 — a regression introduced by the unknown-key message itself."""
    print(f"SPEC-DRIFT: {label} (exit {code}) — " + visible(" ".join(reason.split())))
    return code


def cmd_verdict(a) -> int:
    if a.json is not None:
        text = a.json
    elif sys.stdin.isatty():
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT,
                        "no --json and stdin is a terminal; pipe the JSON line in")
    else:
        # Bytes, decoded with a fixed handler: the verdict must not change with
        # the caller's locale, and a stray byte on a line it never reads must not
        # become an exception.
        text = sys.stdin.buffer.read().decode(ENCODING, errors="replace")
    obj = last_json_line(text)
    if obj is None or any(k not in obj for k in JSON_KEYS):
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT,
                        "last line is not Step 8's JSON, or carries invisible characters "
                        f"inside it ({', '.join(JSON_KEYS)})")
    # The contract is exactly the six keys override 6 specifies, plus `partial` —
    # the one extra whose meaning is checked below rather than guessed. Anything
    # else is refused, not ignored: six clean counts beside `"not_done":99` or
    # `"audit_failed":true` scored CLEAN while contradicting itself (Codex,
    # 2.52.0). This is the general form of the `partial` rule the script already
    # applied to one hand-picked key; the earlier reasoning for tolerating extras
    # — that reading `not_done` would impose one meaning on an ambiguous field —
    # argues for refusing the line, not for scoring it.
    unknown = sorted(set(obj) - set(JSON_KEYS) - set(ALLOWED_EXTRA))
    if unknown:
        # ascii(), like the `partial` message's !r: a key name is attacker-shaped
        # text. Capped in count and length — the reason names the offender, it
        # does not reproduce it.
        shown = ", ".join(ascii(k)[:60] for k in unknown[:5])
        if len(unknown) > 5:
            shown += f", and {len(unknown) - 5} more"
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT, f"keys outside the contract: {shown}")
    counts = {k: obj[k] for k in COUNT_KEYS}
    # The contract is integers. bool is an int subclass, and int() happily eats
    # "2" and 1.9 — each a way for a malformed line to read as CLEAN. Exact type.
    if any(type(c) is not int for c in counts.values()):
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT, "counts are not integers")
    # Step 8 specifies summary as a markdown string. null, a list or an object
    # there means the line was not produced by the audit — fail closed, like
    # every other malformed shape, rather than score its counts.
    if type(obj["summary"]) is not str:
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT, "summary is not a string")
    total, done, changed, deferred, unver = (counts[k] for k in COUNT_KEYS)
    if total <= 0:
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT,
                        "plan has no actionable checklist items (a design doc? verdict "
                        "scores checklist items only; prose claims are out of its scope)")
    if min(done, changed, deferred, unver) < 0:
        # A negative count can make done + changed == total look CLEAN.
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT, "negative count in the JSON")
    partial = total - done - changed - deferred - unver
    if partial < 0:
        return _verdict("COULD-NOT-RUN", EXIT_CANNOT,
                        f"counts add up to more than total_items={total}")
    # `partial` is the one key allowed past the contract check above, because a
    # restated remainder has a meaning this script can verify: a model
    # "correcting itself" with a second number is a contradiction, not a
    # clarification.
    if "partial" in obj:
        # Exact type, like the five counts: True == 1 and 1.0 == 1 in Python, so a
        # value-only comparison would let a bool or float restate the remainder.
        if type(obj["partial"]) is not int:
            return _verdict("COULD-NOT-RUN", EXIT_CANNOT, "partial is not an integer")
        if obj["partial"] != partial:
            return _verdict("COULD-NOT-RUN", EXIT_CANNOT,
                            f"partial={obj['partial']!r} contradicts the derived {partial}")
    breakdown = (f"done={done} changed={changed} partial={partial} "
                 f"not_done={deferred} unverifiable={unver} of {total}")
    if done + changed == total:
        return _verdict("CLEAN", EXIT_OK, breakdown)
    return _verdict("DRIFT", EXIT_DRIFT, breakdown)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # The diff carries third-party text; a non-UTF-8 terminal must not turn
        # a shown diff into a UnicodeEncodeError traceback.
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    p = _Parser(prog="spec-drift.py", description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("repin", cmd_repin)):
        s = sub.add_parser(name)
        s.add_argument("--upstream", default=None,
                       help=f"the gstack section to pin (default: ~/{UPSTREAM_REL})")
        s.add_argument("--pin-dir", default=str(DEFAULT_PIN_DIR),
                       help="directory holding pin.json and pin/ (default: the skill)")
        s.set_defaults(fn=fn)
    sub.choices["repin"].add_argument("--yes", action="store_true",
                                      help="accept the diff shown by a previous run and write the pin")
    sub.choices["repin"].add_argument("--sha", default=None,
                                      help="sha256 prefix printed by the diff run; required with --yes")
    v = sub.add_parser("verdict")
    v.add_argument("--json", default=None,
                   help="text whose last non-empty line is Step 8's JSON object "
                        "(default: read that text from stdin)")
    v.set_defaults(fn=cmd_verdict)
    a = p.parse_args(argv)
    try:
        rc = a.fn(a)
        sys.stdout.flush()   # inside the try: an EPIPE at interpreter shutdown would exit 120
        return rc
    except BrokenPipeError:
        # stdout went away (| head, a closed CI pipe): the confirmation was not
        # delivered, so this cannot count as shown. Silence the flush-at-exit too;
        # if even that fails, the exit code still has to be 2, not a traceback.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        return EXIT_CANNOT
    except Exception as exc:  # last resort: the exit contract holds by construction
        print(f"INTERNAL: {type(exc).__name__}: {exc} — treat as could-not-run", file=sys.stderr)
        return EXIT_CANNOT


if __name__ == "__main__":
    sys.exit(main())
