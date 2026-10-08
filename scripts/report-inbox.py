#!/usr/bin/env python3
"""report-inbox.py — make sure the reports this repo produces are actually seen.

The update pipeline opens GitHub issues (`notification`, `model-review`) and PRs
(`auto-repair`); a future routing report drops a file in the reports directory.
None of that reached the maintainer: nothing surfaced most of it, and nothing
knew whether it had been read. This script keeps a small inbox of open reports
and a record of which ones were opened.

Subcommands:
  collect     refresh the inbox (GitHub at most once per FETCH_TTL, local files always)
  banner      SessionStart text: unread reports with click-to-mark-read links; silent when none
  notify      daily reminder (launchd, 17:00): one macOS notification per unread report,
              at most once per calendar day
  serve-one   answer one HTTP request on stdin/stdout (launchd inetd mode):
              GET /seen/<id> marks the report read and redirects to it
  seen <id> / unseen <id> / list   manual use and tests

A link is http://127.0.0.1:<PORT>/seen/<id>. Clicking it is the only thing that
marks a report read; a report closed on GitHub drops out of the inbox on its own.

State: ~/.claude/superpowers-gstack/report-inbox.json (written atomically under a
lock). Environment overrides: SG_REPORT_REPO (owner/name), SG_REPORT_PORT.
Python 3.9+ (launchd runs /usr/bin/python3). Every path exits 0 except usage errors.
"""

import fcntl
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

PORT = int(os.environ.get("SG_REPORT_PORT", "47817"))
FETCH_TTL = 3600          # seconds between GitHub fetches
RETRY_AFTER_FAILURE = 600  # a failed fetch is retried after this many seconds
GH_TIMEOUT = 6            # per call; the three calls run in parallel (hook budget is 10 s)
MAX_NOTIFICATIONS = 5
SEEN_AGENT = "com.paretofilm.sg-report-seen"
DEFAULT_REPO = "Paretofilm/superpowers-gstack"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")
REPORT_SUFFIXES = (".md", ".html", ".txt")

# (kind, label): what counts as a report. Auto-update PRs are left out because the
# `notification` issue opened alongside each one already links to it.
GH_SOURCES = (("issue", "notification"), ("issue", "model-review"), ("pr", "auto-repair"))


def state_dir():
    return Path.home() / ".claude" / "superpowers-gstack"


def reports_dir():
    return state_dir() / "reports"


def state_path():
    return state_dir() / "report-inbox.json"


def empty_state():
    return {"version": 1, "fetched_at": 0, "items": {}, "seen": {}, "last_notified": "", "alert_hint_shown": False}


def load_state():
    try:
        data = json.loads(state_path().read_text())
        if not isinstance(data, dict) or not isinstance(data.get("items"), dict) or not isinstance(data.get("seen"), dict):
            raise ValueError("unexpected shape")
    except (OSError, ValueError):
        return empty_state()
    merged = empty_state()
    merged.update(data)
    return merged


def save_state(state):
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".report-inbox.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, str(state_path()))


@contextmanager
def locked_state():
    """Read-modify-write under an exclusive lock; never hold it across network calls."""
    state_dir().mkdir(parents=True, exist_ok=True)
    with open(str(state_dir() / ".report-inbox.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        yield state
        save_state(state)


def detect_repo():
    override = os.environ.get("SG_REPORT_REPO", "").strip()
    if override:
        return override
    repo_dir = Path(__file__).resolve().parent.parent
    try:
        url = subprocess.run(["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        url = ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else DEFAULT_REPO


def find_tool(name):
    """launchd runs agents with PATH=/usr/bin:/bin:/usr/sbin:/sbin — look where Homebrew installs too."""
    found = shutil.which(name)
    if found:
        return found
    for d in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.access(os.path.join(d, name), os.X_OK):
            return os.path.join(d, name)
    return None


def fetch_github(repo):
    """Return {id: item} for every open report on GitHub, or None if any call failed."""
    gh = find_tool("gh")
    if not gh:
        return None
    procs = []
    for kind, label in GH_SOURCES:
        cmd = [gh, kind, "list", "--repo", repo, "--label", label, "--state", "open",
               "--json", "number,title,url,createdAt", "--limit", "30"]
        try:
            procs.append((kind, label, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)))
        except OSError:
            return None
    deadline = time.monotonic() + GH_TIMEOUT
    items = {}
    failed = False
    for kind, label, p in procs:
        try:
            out, _ = p.communicate(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            failed = True
            continue
        if p.returncode != 0:
            failed = True
            continue
        try:
            rows = json.loads(out or "[]")
        except ValueError:
            failed = True
            continue
        for row in rows:
            url = str(row.get("url", ""))
            if not url.startswith("https://github.com/"):
                continue
            rid = f"gh-{kind}-{int(row['number'])}"
            items[rid] = {"title": str(row.get("title", "")).strip() or rid, "url": url,
                          "source": label, "created": str(row.get("createdAt", ""))}
    return None if failed else items


def scan_local():
    items = {}
    d = reports_dir()
    if not d.is_dir():
        return items
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.suffix not in REPORT_SUFFIXES or p.name.startswith("."):
            continue
        slug = re.sub(r"[^a-z0-9._-]", "-", p.name.lower())
        rid = f"file-{slug}"[:121]
        if not ID_RE.match(rid):
            continue
        items[rid] = {"title": local_title(p), "url": str(p), "source": "local",
                      "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))}
    return items


def local_title(path):
    try:
        head = path.read_text(errors="replace")[:4000]
    except OSError:
        return path.name
    m = re.search(r"<title>(.*?)</title>", head, re.I | re.S) or re.search(r"^#\s+(.+)$", head, re.M)
    return m.group(1).strip() if m else path.name


def collect(force=False):
    """Refresh the inbox and return the state. GitHub is hit at most once per FETCH_TTL."""
    now = time.time()
    state = load_state()
    fresh_gh = None
    if force or now - float(state.get("fetched_at") or 0) >= FETCH_TTL:
        fresh_gh = fetch_github(detect_repo())
    local = scan_local()
    with locked_state() as st:
        items = st["items"]
        if fresh_gh is not None:
            items = {k: v for k, v in items.items() if not k.startswith("gh-")}
            items.update(fresh_gh)
            st["fetched_at"] = now
        elif force or now - float(st.get("fetched_at") or 0) >= FETCH_TTL:
            # Failure keeps the previous GitHub items: an outage must not read as "all read".
            st["fetched_at"] = now - FETCH_TTL + RETRY_AFTER_FAILURE
        items = {k: v for k, v in items.items() if not k.startswith("file-")}
        items.update(local)
        st["items"] = items
        # Forget read marks only for reports that are gone after a successful refresh.
        st["seen"] = {k: v for k, v in st["seen"].items()
                      if k in items or (k.startswith("gh-") and fresh_gh is None)}
        state = dict(st)
    return state


def unread(state):
    rows = [(rid, it) for rid, it in state["items"].items() if rid not in state["seen"]]
    return sorted(rows, key=lambda r: (r[1].get("created", ""), r[0]))


def link(rid):
    return f"http://127.0.0.1:{PORT}/seen/{rid}"


def tracker_installed():
    return (Path.home() / "Library" / "LaunchAgents" / f"{SEEN_AGENT}.plist").is_file()


def cmd_banner():
    state = collect()
    rows = unread(state)
    if not rows:
        return
    tracked = tracker_installed()
    bar = "━" * 42
    print(bar)
    print(f" Unread reports ({len(rows)})")
    print(bar)
    for rid, it in rows:
        print(f"  • {it['title']}")
        print(f"    {link(rid) if tracked else it['url']}")
    if tracked:
        print("  Tell the user in one line that these reports are unread and list the links;"
              " clicking a link opens the report and marks it read.")
    else:
        print("  Tell the user in one line that these reports are unread and list the links."
              " Read tracking is not installed: run scripts/setup-hooks.sh in the superpowers-gstack repo.")
    if tracked and not state.get("alert_hint_shown"):
        print("  Also tell the user once: so the 17:00 reminder stays on screen until clicked, set"
              " System Settings → Notifications → terminal-notifier → Alerts.")
        with locked_state() as st:
            st["alert_hint_shown"] = True


def notify_one(title, message, url, group):
    tn = find_tool("terminal-notifier")
    if tn:
        subprocess.run([tn, "-title", title, "-message", message, "-open", url, "-group", group],
                       capture_output=True, timeout=15)
        return True
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15)
    return False


def cmd_notify(force=False):
    today = time.strftime("%Y-%m-%d")
    if not force and load_state().get("last_notified") == today:
        return
    state = collect(force=True)
    rows = unread(state)
    if rows:
        clickable = True
        for i, (rid, it) in enumerate(rows[:MAX_NOTIFICATIONS]):
            extra = len(rows) - MAX_NOTIFICATIONS
            msg = it["title"] + (f" (+{extra} til)" if i == MAX_NOTIFICATIONS - 1 and extra > 0 else "")
            clickable = notify_one("Ulest rapport — klikk for å åpne", msg, link(rid), f"sg-report-{rid}") and clickable
        if not clickable:
            print("terminal-notifier missing: notifications are not clickable; install it with"
                  " `brew install terminal-notifier`.", file=sys.stderr)
    with locked_state() as st:
        st["last_notified"] = today


def http_response(out, status, headers=None, body=b""):
    reason = {200: "OK", 302: "Found", 400: "Bad Request", 403: "Forbidden",
              404: "Not Found", 405: "Method Not Allowed"}.get(status, "OK")
    lines = [f"HTTP/1.1 {status} {reason}", f"Content-Length: {len(body)}", "Connection: close",
             "Cache-Control: no-store"]
    for k, v in (headers or {}).items():
        lines.append(f"{k}: {v}")
    out.write(("\r\n".join(lines) + "\r\n\r\n").encode())
    out.write(body)
    out.flush()


def page(title, inner):
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<body style='font:15px -apple-system,sans-serif;max-width:40em;margin:3em auto'>"
            f"{inner}</body>").encode()


def cmd_serve_one(stdin=None, stdout=None):
    inp = stdin or sys.stdin.buffer
    out = stdout or sys.stdout.buffer
    request_line = inp.readline(8192).decode("latin-1").strip()
    headers = {}
    for _ in range(100):
        line = inp.readline(8192).decode("latin-1")
        if not line or line in ("\r\n", "\n"):
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    parts = request_line.split()
    if len(parts) != 3:
        return http_response(out, 400)
    method, target, _ = parts
    # Only answer requests addressed to this host: a page that rebinds its own DNS
    # name to 127.0.0.1 would otherwise be able to read local reports.
    if headers.get("host", "") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
        return http_response(out, 403)
    # A link clicked in the terminal or a notification is a top-level navigation the
    # browser marks Sec-Fetch-Site: none. Another site's <img src=…> would carry the
    # right Host too, but says cross-site — it must not be able to mark reports read.
    if headers.get("sec-fetch-site", "none") not in ("none", "same-origin"):
        return http_response(out, 403)
    if method not in ("GET", "HEAD"):
        return http_response(out, 405, {"Allow": "GET, HEAD"})
    path = target.split("?", 1)[0]
    state = load_state()
    if path == "/":
        rows = unread(state)
        lis = "".join(f"<li><a href='/seen/{rid}'>{html.escape(it['title'])}</a>" for rid, it in rows)
        body = page("Rapporter", f"<h1>Uleste rapporter</h1><ul>{lis or '<li>Ingen — alt er lest.'}</ul>")
        return http_response(out, 200, {"Content-Type": "text/html; charset=utf-8"}, b"" if method == "HEAD" else body)
    m = re.match(r"^/seen/([^/]+)$", path)
    rid = m.group(1) if m else ""
    item = state["items"].get(rid) if ID_RE.match(rid) else None
    if not item:
        body = page("Ukjent rapport", "<p>Rapporten finnes ikke lenger i innboksen (lukket eller fjernet).</p>")
        return http_response(out, 404, {"Content-Type": "text/html; charset=utf-8"}, body)
    if method == "GET":  # HEAD never marks read: only a real visit counts
        with locked_state() as st:
            st["seen"][rid] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if rid.startswith("gh-"):
        if not item["url"].startswith("https://github.com/"):
            return http_response(out, 404)
        return http_response(out, 302, {"Location": item["url"]})
    report = Path(item["url"]).resolve()
    if report.parent != reports_dir().resolve() or not report.is_file():
        return http_response(out, 404)
    ctype = "text/html; charset=utf-8" if report.suffix == ".html" else "text/plain; charset=utf-8"
    body = report.read_bytes()
    return http_response(out, 200, {"Content-Type": ctype}, b"" if method == "HEAD" else body)


def set_seen(rid, seen):
    with locked_state() as st:
        if seen:
            st["seen"][rid] = time.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            st["seen"].pop(rid, None)


def cmd_list():
    state = load_state()
    for rid, it in sorted(state["items"].items()):
        mark = "read  " if rid in state["seen"] else "UNREAD"
        print(f"{mark}  {rid:<24} {it['title']}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "collect":
            collect(force="--force" in rest)
        elif cmd == "banner":
            cmd_banner()
        elif cmd == "notify":
            cmd_notify(force="--force" in rest)
        elif cmd == "serve-one":
            cmd_serve_one()
        elif cmd in ("seen", "unseen") and len(rest) == 1 and ID_RE.match(rest[0]):
            set_seen(rest[0], cmd == "seen")
        elif cmd == "list":
            cmd_list()
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Exception as e:  # noqa: BLE001 — a reminder must never break a session start
        print(f"report-inbox: {cmd} failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
