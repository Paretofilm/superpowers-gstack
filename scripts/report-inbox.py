#!/usr/bin/env python3
"""report-inbox.py — make sure the reports this repo produces are actually seen.

The update pipeline opens GitHub issues (`notification`, `model-review`) and PRs
(`auto-repair`); a future routing report drops a file in the reports directory.
None of that reached the maintainer: nothing surfaced most of it, and nothing
knew whether it had been read. This script keeps a small inbox of open reports
and a record of which ones were opened.

Subcommands:
  collect [--force]   refresh the inbox (GitHub at most once per FETCH_TTL, local files always)
  banner              SessionStart text: unread reports with click-to-mark-read links.
                      Never waits on the network: a stale inbox is refreshed by a detached
                      `collect`, so new reports show at the next session start.
  notify [--force]    daily reminder (launchd, 17:00): one macOS notification per unread
                      report, newest first, once per 17:00 slot
  serve-one           answer one HTTP request on stdin/stdout (launchd inetd mode):
                      GET /seen/<id> marks the report read and redirects to it
  write-plists DIR LOG   write the two launchd agents (used by setup-hooks.sh)
  seen <id> / unseen <id> / list   manual use and tests

A link is http://127.0.0.1:<PORT>/seen/<id>. Following it is the only thing that
marks a report read; a report closed on GitHub drops out of the inbox on its own,
and a local report file that changes after it was read is unread again.

State: ~/.claude/superpowers-gstack/report-inbox.json (written atomically under a
lock). Environment: SG_REPORT_REPO (owner/name) overrides the repo; SG_REPORT_TOOL_DIRS
(colon-separated) and SG_REPORT_NOW (epoch seconds) exist for tests.
Python 3.9+ (launchd runs /usr/bin/python3). Every path exits 0 except usage errors.
"""

import datetime
import fcntl
import hashlib
import html
import json
import os
import plistlib
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

PORT = 47817
FETCH_TTL = 3600            # seconds between GitHub fetches
RETRY_AFTER_FAILURE = 600   # a failed or interrupted fetch is retried after this many seconds
GH_TIMEOUT = 6              # all three gh calls run in parallel under this deadline
GH_LIMIT = 200              # rows per label; a full page means "maybe more", so nothing is pruned
STALE_WARNING = 3 * 86400   # warn in the banner when GitHub has not been reached for this long
NOTIFY_HOUR = 17
MAX_NOTIFICATIONS = 5
REQUEST_TIMEOUT = 10        # serve-one: seconds before an idle connection is dropped
TITLE_MAX = 120
NOTIFY_AGENT = "com.paretofilm.sg-report-notify"
SEEN_AGENT = "com.paretofilm.sg-report-seen"
DEFAULT_REPO = "Paretofilm/superpowers-gstack"
DEFAULT_TOOL_DIRS = "/opt/homebrew/bin:/usr/local/bin"
LAUNCHD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,120}")

# (kind, label): what counts as a report. Auto-update PRs are left out because the
# `notification` issue opened alongside each one already links to it.
GH_SOURCES = (("issue", "notification"), ("issue", "model-review"), ("pr", "auto-repair"))


def now():
    return float(os.environ.get("SG_REPORT_NOW") or time.time())


def state_dir():
    return Path.home() / ".claude" / "superpowers-gstack"


def reports_dir():
    return state_dir() / "reports"


def state_path():
    return state_dir() / "report-inbox.json"


def empty_state():
    return {"version": 2, "fetched_at": 0, "last_ok_fetch": 0, "last_error": "", "failing_since": 0,
            "items": {}, "seen": {}, "last_slot": "", "alert_hint_shown": False}


def load_state():
    try:
        data = json.loads(state_path().read_text())
        if not isinstance(data, dict) or not isinstance(data.get("items"), dict) or not isinstance(data.get("seen"), dict):
            raise ValueError("unexpected shape")
    except (OSError, ValueError):
        return empty_state()
    merged = empty_state()
    merged.update(data)
    # Read marks are epoch seconds; anything else (an older format) counts as "read now".
    merged["seen"] = {k: v if isinstance(v, (int, float)) else now() for k, v in merged["seen"].items()}
    # Version 1 had no last_ok_fetch: its fetched_at was a successful fetch, not "never".
    if "last_ok_fetch" not in data:
        merged["last_ok_fetch"] = merged["fetched_at"]
    # A timestamp ahead of the clock (it moved back) would block fetching and the
    # stale warning until real time caught up: treat it as never.
    for key in ("fetched_at", "last_ok_fetch"):
        if float(merged.get(key) or 0) > now() + 60:
            merged[key] = 0
    return merged


def save_state(state):
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".report-inbox.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(state_path()))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def locked_state():
    """Read-modify-write under an exclusive lock; never hold it across network calls."""
    state_dir().mkdir(parents=True, exist_ok=True)
    with open(str(state_dir() / ".report-inbox.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        yield state
        save_state(state)


def find_tool(name):
    """launchd runs agents with PATH=/usr/bin:/bin:/usr/sbin:/sbin — look where Homebrew installs too."""
    found = shutil.which(name)
    if found:
        return found
    for d in os.environ.get("SG_REPORT_TOOL_DIRS", DEFAULT_TOOL_DIRS).split(":"):
        if d and os.access(os.path.join(d, name), os.X_OK):
            return os.path.join(d, name)
    return None


def clean_title(text, fallback):
    """Titles reach a terminal and an agent's context: one line, no control characters."""
    text = html.unescape(str(text))
    text = re.sub(r"[\x00-\x1f\x7f-\x9f\s]+", " ", text).strip()
    if len(text) > TITLE_MAX:
        text = text[:TITLE_MAX - 1].rstrip() + "…"
    return text or fallback


def detect_repo():
    override = os.environ.get("SG_REPORT_REPO", "").strip()
    if override:
        return override
    repo_dir = Path(__file__).resolve().parent.parent
    try:
        url = subprocess.run(["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        url = ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else DEFAULT_REPO


def stop(proc):
    """Kill gh and anything it started: a child holding the pipe open would block communicate()."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()
    try:
        proc.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def fetch_github(repo):
    """Return (items, truncated, error). items is None when any call failed."""
    gh = find_tool("gh")
    if not gh:
        return None, False, "gh not found"
    procs = []
    for kind, label in GH_SOURCES:
        cmd = [gh, kind, "list", "--repo", repo, "--label", label, "--state", "open",
               "--json", "number,title,url,createdAt", "--limit", str(GH_LIMIT)]
        try:
            procs.append((kind, label, subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                                        stderr=subprocess.DEVNULL, text=True,
                                                        start_new_session=True)))
        except OSError as e:
            for _, _, p in procs:
                stop(p)
            return None, False, f"gh could not start: {e}"
    deadline = time.monotonic() + GH_TIMEOUT
    items, truncated, errors = {}, False, []
    for kind, label, p in procs:
        try:
            out, _ = p.communicate(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            stop(p)
            errors.append(f"{label}: timed out")
            continue
        if p.returncode != 0:
            errors.append(f"{label}: gh exited {p.returncode}")
            continue
        try:
            rows = json.loads(out or "[]")
            if not isinstance(rows, list):
                raise ValueError
        except ValueError:
            errors.append(f"{label}: unreadable output")
            continue
        truncated = truncated or len(rows) >= GH_LIMIT
        for row in rows:
            try:
                number = int(row["number"])
                url = str(row["url"])
            except (KeyError, TypeError, ValueError):
                continue
            if not url.startswith("https://github.com/"):
                continue
            rid = f"gh-{kind}-{number}"
            items[rid] = {"title": clean_title(row.get("title", ""), rid), "url": url,
                          "source": label, "created": str(row.get("createdAt", ""))}
    if errors:
        return None, False, "; ".join(errors)
    return items, truncated, ""


def scan_local():
    items = {}
    d = reports_dir()
    if not d.is_dir():
        return items
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.suffix not in (".md", ".html", ".txt") or p.name.startswith("."):
            continue
        # The slug keeps ids readable; the hash keeps "Rapport å.md" and "Rapport ø.md" apart.
        slug = re.sub(r"[^a-z0-9._-]+", "-", p.name.lower()).strip("-.")[:80] or "report"
        rid = f"file-{slug}-{hashlib.sha1(p.name.encode()).hexdigest()[:8]}"
        mtime = p.stat().st_mtime
        items[rid] = {"title": clean_title(local_title(p), p.name), "url": str(p), "source": "local",
                      "mtime": mtime, "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime))}
    return items


def local_title(path):
    try:
        with open(str(path), errors="replace") as f:
            head = f.read(4000)
    except OSError:
        return path.name
    m = re.search(r"<title>(.*?)</title>", head, re.I | re.S) or re.search(r"^#[ \t]+(.+)$", head, re.M)
    return m.group(1) if m else path.name


def collect(force=False, network=True):
    """Refresh the inbox and return the state. GitHub is hit at most once per FETCH_TTL.

    The fetch is claimed under the lock before any network call: a run killed mid-fetch
    (the SessionStart hook has a 10 s budget) has already pushed the next attempt out,
    and a second process starting at the same moment does not fetch again."""
    t = now()
    do_fetch = False
    if network:
        with locked_state() as st:
            if force or t - float(st.get("fetched_at") or 0) >= FETCH_TTL:
                st["fetched_at"] = t - FETCH_TTL + RETRY_AFTER_FAILURE
                do_fetch = True
    fresh, truncated, error = fetch_github(detect_repo()) if do_fetch else (None, False, "")
    local = scan_local()
    with locked_state() as st:
        gh_items = {k: v for k, v in st["items"].items() if k.startswith("gh-")}
        if fresh is not None:
            # A full page may hide older reports: add what came back, prune nothing.
            gh_items = dict(gh_items, **fresh) if truncated else fresh
            st["fetched_at"] = t
            st["last_ok_fetch"] = t
            st["last_error"] = ""
            st["failing_since"] = 0
        elif do_fetch:
            st["last_error"] = error  # keep the previous items: an outage must not read as "all read"
            st["failing_since"] = st.get("failing_since") or t
        st["items"] = dict(gh_items, **local)
        st["seen"] = {k: v for k, v in st["seen"].items() if k in st["items"]}
        state = json.loads(json.dumps(st))
    return state


def is_unread(state, rid):
    seen = state["seen"].get(rid)
    if seen is None:
        return True
    return float(state["items"][rid].get("mtime") or 0) > float(seen)


def unread(state, newest_first=False):
    rows = [(rid, it) for rid, it in state["items"].items() if is_unread(state, rid)]
    return sorted(rows, key=lambda r: (r[1].get("created", ""), r[0]), reverse=newest_first)


def link(rid):
    return f"http://127.0.0.1:{PORT}/seen/{rid}"


def tracker_problem():
    """None when the click tracker points at this script; otherwise why links would be dead."""
    plist = Path.home() / "Library" / "LaunchAgents" / f"{SEEN_AGENT}.plist"
    if not plist.is_file():
        return "Read tracking is not installed"
    try:
        with open(str(plist), "rb") as f:
            args = plistlib.load(f).get("ProgramArguments") or []
    except Exception:  # noqa: BLE001 — any unreadable plist is a broken tracker
        return "The read-tracking agent is unreadable"
    target = Path(args[1]) if len(args) > 1 else None
    if not target or not target.is_file() or target.resolve() != Path(__file__).resolve():
        return "The read-tracking agent points at another copy of this script"
    return None


def hook_source():
    """SessionStart passes JSON on stdin; read it without ever blocking a manual run."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return ""
        fd = sys.stdin.fileno()
    except (OSError, ValueError, AttributeError):
        return ""
    raw = b""
    deadline = time.monotonic() + 0.5
    # os.read returns what is there (sys.stdin.read would wait for end-of-file); keep
    # reading until the JSON is whole, the writer closes, or the deadline passes.
    while time.monotonic() < deadline:
        try:
            if not select.select([fd], [], [], max(0.0, deadline - time.monotonic()))[0]:
                break
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        raw += chunk
        try:
            return str(json.loads(raw.decode("utf-8", "replace")).get("source", ""))
        except ValueError:
            continue
    if not raw.strip():
        return ""  # nothing on stdin: a manual run, show the banner
    try:
        return str(json.loads(raw.decode("utf-8", "replace")).get("source", ""))
    except (ValueError, AttributeError):
        return "compact"  # unreadable hook input: staying quiet is the safe side


def refresh_in_background():
    """A refresh that cannot start must not cost the banner it was meant to feed."""
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "collect"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    except OSError as e:
        print(f"report-inbox: background refresh failed: {e}", file=sys.stderr)


def cmd_banner():
    if hook_source() == "compact":
        return  # a compaction mid-task is not the moment; startup/clear/resume are
    state = collect(network=False)
    t = now()
    if t - float(state.get("fetched_at") or 0) >= FETCH_TTL:
        refresh_in_background()
    rows = unread(state)
    # Blind, not just unlucky: failing now, and either never reached for longer than two
    # retry windows (gh missing or logged out) or last reached more than STALE_WARNING ago.
    failing_since = float(state.get("failing_since") or 0)
    last_ok = float(state.get("last_ok_fetch") or 0)
    if not failing_since:
        stale = ""
    elif not last_ok and t - failing_since > 2 * RETRY_AFTER_FAILURE:
        stale = "has not been reachable since " + time.strftime("%Y-%m-%d %H:%M", time.localtime(failing_since))
    elif last_ok and t - last_ok > STALE_WARNING:
        stale = f"has not been reached for over {STALE_WARNING // 86400} days"
    else:
        stale = ""
    if not rows and not stale:
        return
    problem = tracker_problem()
    bar = "━" * 42
    print(bar)
    print(f" Unread reports ({len(rows)})")
    print(bar)
    for rid, it in rows:
        print(f"  • {it['title']}")
        print(f"    {it['url'] if problem else link(rid)}")
    if stale:
        reason = state.get("last_error") or "no successful fetch"
        print(f"  ⚠ GitHub {stale} ({reason}); reports may be missing. Check `gh auth status`.")
    if rows and not problem:
        print("  Tell the user in one line that these reports are unread and list the links;"
              " clicking a link opens the report and marks it read.")
    elif rows:
        print(f"  Tell the user in one line that these reports are unread and list the links. {problem}:"
              " run scripts/setup-hooks.sh in the superpowers-gstack primary checkout.")
    if rows and not problem and not state.get("alert_hint_shown"):
        print("  Also tell the user once: so the 17:00 reminder stays on screen until clicked, set"
              " System Settings → Notifications → terminal-notifier → Alerts.")
        with locked_state() as st:
            st["alert_hint_shown"] = True


def notify_one(title, message, url, group):
    """True when a clickable notification was delivered."""
    tn = find_tool("terminal-notifier")
    if tn:
        # terminal-notifier reads a value starting with '-' or '[' as something else.
        safe = "\\" + message if message[:1] in ("-", "[") else message
        try:
            r = subprocess.run([tn, "-title", title, "-message", safe, "-open", url, "-group", group],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                return True
            print(f"terminal-notifier exited {r.returncode}: {r.stderr.decode(errors='replace').strip()}",
                  file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"terminal-notifier failed: {e}", file=sys.stderr)
    # Text goes in as arguments, never into the script source: AppleScript has no \u
    # escape, and "—" or "å" quoted any other way is a syntax error.
    osa = find_tool("osascript") or "osascript"
    try:
        r = subprocess.run([osa, "-e", "on run argv", "-e",
                            "display notification (item 1 of argv) with title (item 2 of argv)",
                            "-e", "end run", message, title], capture_output=True, timeout=15)
        if r.returncode != 0:
            print(f"osascript exited {r.returncode}: {r.stderr.decode(errors='replace').strip()}", file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"osascript failed: {e}", file=sys.stderr)
    return False


def current_slot(t):
    """The date of the most recent 17:00. A run caught up at 08:00 belongs to yesterday's
    slot, so it does not cancel today's 17:00 reminder."""
    day = datetime.date.fromtimestamp(t)
    if time.localtime(t).tm_hour < NOTIFY_HOUR:
        day -= datetime.timedelta(days=1)  # calendar arithmetic: a DST night is not 86400 s
    return day.isoformat()


def cmd_notify(force=False):
    slot = current_slot(now())
    # Claim the slot under the lock before any work, as collect() claims a fetch: two
    # runs at once (a catch-up at wake and a manual one) must not both send.
    with locked_state() as st:
        if st.get("last_slot") == slot and not force:
            return
        st["last_slot"] = slot
    state = collect(force=True)
    rows = unread(state, newest_first=True)  # the newest report must never hide behind old ones
    clickable = True
    for i, (rid, it) in enumerate(rows[:MAX_NOTIFICATIONS]):
        extra = len(rows) - MAX_NOTIFICATIONS
        msg = it["title"] + (f" (+{extra} til)" if i == MAX_NOTIFICATIONS - 1 and extra > 0 else "")
        clickable = notify_one("Ulest rapport — klikk for å åpne", msg, link(rid), f"sg-report-{rid}") and clickable
    if rows and not clickable:
        print("Notifications were not clickable: install terminal-notifier (brew install terminal-notifier).",
              file=sys.stderr)


def http_response(out, status, headers=None, body=b""):
    reason = {200: "OK", 302: "Found", 400: "Bad Request", 403: "Forbidden",
              404: "Not Found", 405: "Method Not Allowed"}.get(status, "OK")
    lines = [f"HTTP/1.1 {status} {reason}", f"Content-Length: {len(body)}", "Connection: close",
             "Cache-Control: no-store", "X-Content-Type-Options: nosniff"]
    for k, v in (headers or {}).items():
        lines.append(f"{k}: {v}")
    out.write(("\r\n".join(lines) + "\r\n\r\n").encode())
    out.write(body)
    out.flush()


def page(title, inner):
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<body style='font:15px -apple-system,sans-serif;max-width:40em;margin:3em auto'>"
            f"{inner}</body>").encode()


def foreign(value):
    """True when a Referer/Origin names a page other than this server."""
    if not value or value == "null":
        return False
    return not re.match(rf"^https?://(127\.0\.0\.1|localhost):{PORT}(/|$)", value)


def cmd_serve_one(stdin=None, stdout=None):
    signal.alarm(REQUEST_TIMEOUT)  # bounds the whole request: an idle client must not hold a process
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
    if method not in ("GET", "HEAD"):
        return http_response(out, 405, {"Allow": "GET, HEAD"})
    m = re.match(r"^/seen/([^/?#]+)(?:\?.*)?$", target)
    rid = m.group(1) if m and ID_RE.fullmatch(m.group(1)) else ""
    item = load_state()["items"].get(rid) if rid else None
    # A click in the terminal or a notification is a top-level navigation the browser
    # marks Sec-Fetch-Site: none; the confirm page below is same-origin (served reports
    # are sandboxed, so they never are). Another site's <img src=…> carries the right
    # Host too; it gives itself away through Sec-Fetch-Site, or, in a browser that does
    # not send Fetch Metadata, through Referer/Origin. Prefetch and preview are not a visit.
    site = headers.get("sec-fetch-site")
    purpose = " ".join(headers.get(h, "") for h in ("sec-purpose", "purpose", "x-purpose")).lower()
    if any(p in purpose for p in ("prefetch", "prerender", "preview")):
        return http_response(out, 403)
    if (site is not None and site not in ("none", "same-origin")) or foreign(headers.get("referer")) \
            or foreign(headers.get("origin")):
        if item and headers.get("sec-fetch-dest", "document") == "document":
            # A real person who followed the link from a web page: say why nothing was
            # recorded and let one click on this page (same-origin) record it.
            body = page("Bekreft", f"<p>Lenken ble åpnet fra en nettside, så den ble ikke registrert som lest.</p>"
                                   f"<p><a href='/seen/{rid}'>Marker som lest og åpne «{html.escape(item['title'])}»</a></p>")
            return http_response(out, 403, {"Content-Type": "text/html; charset=utf-8"}, body)
        return http_response(out, 403)
    if not item:
        body = page("Ukjent rapport", "<p>Rapporten finnes ikke lenger i innboksen (lukket eller fjernet).</p>")
        return http_response(out, 404, {"Content-Type": "text/html; charset=utf-8"}, body)
    if rid.startswith("gh-"):
        if not item["url"].startswith("https://github.com/"):
            return http_response(out, 404)
        mark_read(method, rid)
        return http_response(out, 302, {"Location": item["url"]})
    report = Path(item["url"]).resolve()
    if report.parent != reports_dir().resolve() or not report.is_file():
        return http_response(out, 404)
    try:
        # O_NOFOLLOW: a file swapped for a symlink after the check above is refused, not followed.
        fd = os.open(str(report), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as f:
            body = f.read()
    except OSError:
        return http_response(out, 404)
    mark_read(method, rid)
    ctype = "text/html; charset=utf-8" if report.suffix == ".html" else "text/plain; charset=utf-8"
    # sandbox gives the report an opaque origin: a script in it cannot use this server.
    csp = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    return http_response(out, 200, {"Content-Type": ctype, "Content-Security-Policy": csp},
                         b"" if method == "HEAD" else body)


def mark_read(method, rid):
    if method == "GET":  # HEAD never marks read: only a real visit counts
        set_seen(rid, True)


def set_seen(rid, seen):
    with locked_state() as st:
        if seen:
            st["seen"][rid] = now()
        else:
            st["seen"].pop(rid, None)


def cmd_list():
    state = load_state()
    for rid, it in sorted(state["items"].items()):
        mark = "UNREAD" if is_unread(state, rid) else "read  "
        print(f"{mark}  {rid:<32} {it['title']}")


def cmd_write_plists(agents_dir, log):
    script = str(Path(__file__).resolve())
    env = {"PATH": LAUNCHD_PATH}
    notify = {"Label": NOTIFY_AGENT, "ProgramArguments": ["/usr/bin/python3", script, "notify"],
              "StartCalendarInterval": {"Hour": NOTIFY_HOUR, "Minute": 0}, "EnvironmentVariables": env,
              "StandardOutPath": log, "StandardErrorPath": log, "ProcessType": "Background"}
    # inetd mode: stdin/stdout are the accepted connection, so stdout must not go to the log.
    # Standard priority: the user is waiting on this one after a click.
    seen = {"Label": SEEN_AGENT, "ProgramArguments": ["/usr/bin/python3", script, "serve-one"],
            "inetdCompatibility": {"Wait": False}, "EnvironmentVariables": env, "StandardErrorPath": log,
            "Sockets": {"Listener": {"SockNodeName": "127.0.0.1", "SockServiceName": str(PORT),
                                     "SockType": "stream", "SockFamily": "IPv4"}}}
    Path(agents_dir).mkdir(parents=True, exist_ok=True)
    for spec in (notify, seen):
        with open(os.path.join(agents_dir, spec["Label"] + ".plist"), "wb") as f:
            plistlib.dump(spec, f)
        print(spec["Label"])


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
        elif cmd == "write-plists" and len(rest) == 2:
            cmd_write_plists(rest[0], rest[1])
        elif cmd in ("seen", "unseen") and len(rest) == 1 and ID_RE.fullmatch(rest[0]):
            set_seen(rest[0], cmd == "seen")
        elif cmd == "list":
            cmd_list()
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Exception as e:  # noqa: BLE001 — a reminder must never break a session start
        print(f"report-inbox: {cmd} failed: {e}", file=sys.stderr)
        if cmd == "write-plists":
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
