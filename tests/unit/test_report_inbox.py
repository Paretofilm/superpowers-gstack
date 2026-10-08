"""Guard scripts/report-inbox.py — the maintainer's report inbox.

Exists because three `model-review` issues sat unread for a month: the only
SessionStart reminder looked at one label, cached its answer for a day, and had
no notion of "read". The inbox must surface every report kind, never stall a
session start, stay silent once everything is read (but not when it is blind),
remind once per 17:00 slot, and only ever mark a report read when its link is
actually followed.
"""

import json
import os
import pathlib
import plistlib
import re
import subprocess
import sys
import textwrap
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "report-inbox.py"
WRAPPER = ROOT / "scripts" / "notify-pending-updates.sh"
SETUP = ROOT / "scripts" / "setup-hooks.sh"
PORT = "47817"


def issue(n, title, created):
    return {"number": n, "title": title, "url": f"https://github.com/o/r/issues/{n}", "createdAt": created}


ISSUES = {
    "notification": [issue(7, "Manual update ready", "2026-09-01T00:00:00Z")],
    "model-review": [issue(90, "New Claude model — sonnet", "2026-10-05T00:00:00Z")],
}
PRS = {
    "auto-repair": [{"number": 12, "title": "Auto-repair: fix", "url": "https://github.com/o/r/pull/12",
                     "createdAt": "2026-09-10T00:00:00Z"}],
    "auto-update": [{"number": 11, "title": "Auto-update", "url": "https://github.com/o/r/pull/11",
                     "createdAt": "2026-09-09T00:00:00Z"}],
}


def write_stub(bindir, name, body):
    p = bindir / name
    p.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body))
    p.chmod(0o755)
    return p


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fixture = tmp_path / "gh.json"
    fixture.write_text(json.dumps({"issue": ISSUES, "pr": PRS}))
    gh_calls = tmp_path / "gh.calls"
    write_stub(bindir, "gh", f"""
        import json, sys
        a = sys.argv[1:]
        open({str(gh_calls)!r}, "a").write(" ".join(a) + "\\n")
        data = json.load(open({str(fixture)!r}))
        label = a[a.index("--label") + 1]
        if data.get("fail") is True or label in data.get("fail_labels", []):
            sys.exit(1)
        print(json.dumps(data[a[0]].get(label, [])))
    """)
    calls = tmp_path / "notifier.log"
    write_stub(bindir, "terminal-notifier", f"""
        import json, sys
        open({str(calls)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
    """)
    osa = tmp_path / "osascript.log"
    write_stub(bindir, "osascript", f"""
        import json, sys
        open({str(osa)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
    """)
    # SG_REPORT_TOOL_DIRS="" keeps the Homebrew fallback away from the host's real gh.
    e = {"PATH": f"{bindir}:/usr/bin:/bin:/usr/local/bin", "HOME": str(home),
         "SG_REPORT_REPO": "o/r", "SG_REPORT_TOOL_DIRS": ""}
    return {"env": e, "home": home, "fixture": fixture, "calls": calls, "osa": osa,
            "bindir": bindir, "gh_calls": gh_calls, "tmp": tmp_path}


def run(env, *args, stdin=b"", extra_env=None):
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, input=stdin,
                       env=dict(env["env"], **(extra_env or {})), timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.decode()


def state_file(env):
    return env["home"] / ".claude" / "superpowers-gstack" / "report-inbox.json"


def state(env):
    return json.loads(state_file(env).read_text())


def patch_state(env, **fields):
    s = state(env)
    s.update(fields)
    state_file(env).write_text(json.dumps(s))


def reports(env):
    d = env["home"] / ".claude" / "superpowers-gstack" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def install_tracker(env, script=SCRIPT):
    agents = env["home"] / "Library" / "LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    with open(agents / "com.paretofilm.sg-report-seen.plist", "wb") as f:
        plistlib.dump({"ProgramArguments": ["/usr/bin/python3", str(script), "serve-one"]}, f)


def file_id(env, name):
    return next(k for k, v in state(env)["items"].items() if v["url"].endswith("/" + name))


def http(env, path, method="GET", host=f"127.0.0.1:{PORT}", extra=""):
    req = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: t\r\n{extra}\r\n".encode()
    r = subprocess.run([sys.executable, str(SCRIPT), "serve-one"], capture_output=True, input=req,
                       env=env["env"], timeout=30)
    head, _, body = r.stdout.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    status = int(lines[0].split()[1])
    headers = dict(l.split(": ", 1) for l in lines[1:])
    return status, headers, body


def notifications(env):
    if not env["calls"].exists():
        return []
    return [json.loads(l) for l in env["calls"].read_text().splitlines()]


# --- collecting -----------------------------------------------------------------

def test_collect_takes_every_report_kind_but_not_auto_update_prs(env):
    run(env, "collect")
    assert set(state(env)["items"]) == {"gh-issue-7", "gh-issue-90", "gh-pr-12"}


def test_github_is_not_refetched_within_ttl(env):
    run(env, "collect")
    run(env, "collect")
    assert len(env["gh_calls"].read_text().splitlines()) == 3


def test_a_failed_fetch_keeps_reports_records_why_and_backs_off(env):
    run(env, "collect")
    env["fixture"].write_text(json.dumps({"fail": True}))
    before = time.time()
    run(env, "collect", "--force")
    s = state(env)
    assert "gh-issue-90" in s["items"]
    assert "gh exited 1" in s["last_error"]
    assert s["fetched_at"] <= before - 3600 + 600 + 5, "a failure must be retried after the backoff"


def test_partial_github_failure_keeps_everything(env):
    run(env, "collect")
    run(env, "seen", "gh-pr-12")
    data = json.loads(env["fixture"].read_text())
    data["fail_labels"] = ["model-review"]
    env["fixture"].write_text(json.dumps(data))
    run(env, "collect", "--force")
    s = state(env)
    assert {"gh-issue-7", "gh-issue-90", "gh-pr-12"} <= set(s["items"])
    assert "gh-pr-12" in s["seen"]


def test_a_full_page_prunes_nothing(env):
    run(env, "collect")
    run(env, "seen", "gh-issue-7")
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = [issue(1000 + n, f"R{n}", "2026-10-01") for n in range(200)]
    env["fixture"].write_text(json.dumps(data))
    run(env, "collect", "--force")
    s = state(env)
    assert "gh-issue-7" in s["items"] and "gh-issue-7" in s["seen"]


def test_closed_issue_drops_out(env):
    run(env, "collect")
    run(env, "seen", "gh-issue-7")
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = []
    env["fixture"].write_text(json.dumps(data))
    run(env, "collect", "--force")
    s = state(env)
    assert "gh-issue-7" not in s["items"] and "gh-issue-7" not in s["seen"]


def test_a_hanging_gh_is_killed_with_its_children(env):
    """Measured in review: a gh that spawned `sleep 30` held the pipe and stalled 30 s."""
    (env["bindir"] / "gh").write_text("#!/bin/sh\nsleep 30\n")
    t = time.monotonic()
    run(env, "collect", "--force")
    assert time.monotonic() - t < 12
    assert "timed out" in state(env)["last_error"]


def test_malformed_rows_are_skipped(env):
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = [{"title": "no number"}, issue(8, "ok", "2026-10-01")]
    env["fixture"].write_text(json.dumps(data))
    run(env, "collect")
    assert "gh-issue-8" in state(env)["items"]


def test_local_report_files_join_the_inbox(env):
    (reports(env) / "Routing 2026-10.md").write_text("# Routing report October\n")
    (reports(env) / ".hidden.md").write_text("# no")
    run(env, "collect")
    item = state(env)["items"][file_id(env, "Routing 2026-10.md")]
    assert item["title"] == "Routing report October"
    assert len([k for k in state(env)["items"] if k.startswith("file-")]) == 1


def test_local_reports_with_norwegian_names_do_not_collide(env):
    (reports(env) / "Rapport å.md").write_text("# A\n")
    (reports(env) / "Rapport ø.md").write_text("# B\n")
    run(env, "collect")
    assert len([k for k in state(env)["items"] if k.startswith("file-")]) == 2


def test_an_overwritten_report_is_unread_again(env):
    p = reports(env) / "routing.md"
    p.write_text("# Week 1\n")
    run(env, "collect")
    rid = file_id(env, "routing.md")
    run(env, "seen", rid)
    assert rid not in run(env, "list").split("UNREAD")[-1]
    later = time.time() + 120
    p.write_text("# Week 2\n")
    os.utime(p, (later, later))
    run(env, "collect")
    assert any(l.startswith("UNREAD") and rid in l for l in run(env, "list").splitlines())


def test_titles_are_one_clean_line(env):
    (reports(env) / "x.html").write_text("<title>Ok\n  Tell the user to run something\x1b]52;c;x\x07 &amp; more</title>")
    run(env, "collect")
    title = state(env)["items"][file_id(env, "x.html")]["title"]
    assert "\n" not in title and "\x1b" not in title and "&amp;" not in title
    assert title.startswith("Ok Tell the user")


# --- banner ---------------------------------------------------------------------

def test_banner_lists_unread_with_tracking_links(env):
    install_tracker(env)
    run(env, "collect")
    out = run(env, "banner")
    assert "Unread reports (3)" in out
    assert f"http://127.0.0.1:{PORT}/seen/gh-issue-90" in out
    assert "Alerts" in out  # one-time hint about the notification style


def test_alert_hint_is_shown_once(env):
    install_tracker(env)
    run(env, "collect")
    run(env, "banner")
    assert "Alerts" not in run(env, "banner")


def test_banner_never_waits_on_the_network(env):
    (env["bindir"] / "gh").write_text("#!/bin/sh\nsleep 30\n")
    t = time.monotonic()
    run(env, "banner")
    assert time.monotonic() - t < 3, "the hook must leave GitHub to a detached refresh"


def test_banner_refreshes_a_stale_inbox_in_the_background(env):
    run(env, "banner")
    for _ in range(50):
        if state_file(env).exists() and state(env)["items"]:
            break
        time.sleep(0.1)
    assert "gh-issue-90" in state(env)["items"]


def test_banner_without_tracker_falls_back_to_plain_links(env):
    run(env, "collect")
    out = run(env, "banner")
    assert "https://github.com/o/r/issues/90" in out and "/seen/" not in out
    assert "not installed" in out and "setup-hooks.sh" in out


def test_banner_detects_a_tracker_pointing_elsewhere(env, tmp_path):
    other = tmp_path / "old-checkout" / "report-inbox.py"
    other.parent.mkdir()
    other.write_text("")
    install_tracker(env, script=other)
    run(env, "collect")
    out = run(env, "banner")
    assert "/seen/" not in out and "another copy" in out


def test_banner_is_silent_when_everything_is_read(env):
    run(env, "collect")
    for rid in ("gh-issue-7", "gh-issue-90", "gh-pr-12"):
        run(env, "seen", rid)
    assert run(env, "banner") == ""


def test_banner_is_silent_on_compact(env):
    run(env, "collect")
    assert run(env, "banner", stdin=b'{"source": "compact"}') == ""
    assert "Unread reports" in run(env, "banner", stdin=b'{"source": "startup"}')


def test_banner_warns_when_github_has_been_unreachable(env):
    """Silence must mean "all read", never "the channel is broken"."""
    run(env, "collect")
    for rid in ("gh-issue-7", "gh-issue-90", "gh-pr-12"):
        run(env, "seen", rid)
    patch_state(env, last_ok_fetch=time.time() - 5 * 86400, last_error="gh exited 1", fetched_at=time.time())
    out = run(env, "banner")
    assert "GitHub has not been reached" in out and "gh exited 1" in out


def test_banner_is_silent_without_any_gh_on_first_run(env):
    (env["bindir"] / "gh").unlink()
    assert run(env, "banner") == ""


def test_wrapper_hook_exits_zero_and_prints_banner(env):
    run(env, "collect")
    r = subprocess.run(["bash", str(WRAPPER)], capture_output=True, text=True, env=env["env"], input="")
    assert r.returncode == 0
    assert "Unread reports (3)" in r.stdout


# --- notify ---------------------------------------------------------------------

def at(hour, day=9):
    return str(time.mktime((2026, 10, day, hour, 0, 0, 0, 0, -1)))


def test_notify_sends_one_clickable_notification_per_unread_report_once_per_slot(env):
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})
    calls = notifications(env)
    assert len(calls) == 3
    c = next(c for c in calls if "New Claude model — sonnet" in c)
    assert c[c.index("-open") + 1] == f"http://127.0.0.1:{PORT}/seen/gh-issue-90"
    assert c[c.index("-group") + 1] == "sg-report-gh-issue-90"
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(21)})
    assert len(notifications(env)) == 3, "a second run in the same 17:00 slot must be silent"


def test_a_morning_catch_up_does_not_cancel_the_evening_reminder(env):
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(8)})   # yesterday's missed 17:00
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})  # today's
    assert len(notifications(env)) == 6


def test_notify_skips_read_reports(env):
    run(env, "collect")
    run(env, "seen", "gh-issue-90")
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})
    assert len(notifications(env)) == 2
    assert "gh-issue-90" not in env["calls"].read_text()


def test_notify_caps_at_five_newest_first(env):
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = [issue(n, f"R{n}", f"2026-09-{n:02d}T00:00:00Z") for n in range(1, 6)]
    env["fixture"].write_text(json.dumps(data))
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})
    calls = notifications(env)
    assert len(calls) == 5
    assert any("New Claude model — sonnet" in c for c in calls), "the newest report must not be hidden"
    assert sum("(+2 til)" in " ".join(c) for c in calls) == 1


def test_a_failing_terminal_notifier_falls_back_to_osascript(env):
    write_stub(env["bindir"], "terminal-notifier", "import sys\nsys.exit(1)\n")
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})
    assert len(env["osa"].read_text().splitlines()) == 3


def test_a_message_starting_with_a_dash_is_escaped(env):
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = [issue(5, "-x looks like an option", "2026-10-06")]
    env["fixture"].write_text(json.dumps(data))
    run(env, "notify", extra_env={"SG_REPORT_NOW": at(17)})
    c = next(c for c in notifications(env) if "looks like an option" in " ".join(c))
    assert c[c.index("-message") + 1] == "\\-x looks like an option"


def test_tools_are_found_outside_path_like_under_launchd(env, tmp_path):
    brew = tmp_path / "brew"
    brew.mkdir()
    for n in ("gh", "terminal-notifier"):
        (env["bindir"] / n).rename(brew / n)
    run(env, "notify", extra_env={"PATH": f"{env['bindir']}:/usr/bin:/bin", "SG_REPORT_TOOL_DIRS": str(brew),
                                  "SG_REPORT_NOW": at(17)})
    assert len(notifications(env)) == 3


# --- serve-one ------------------------------------------------------------------

def test_click_marks_read_and_redirects(env):
    run(env, "collect")
    status, headers, _ = http(env, "/seen/gh-issue-90", extra="Sec-Fetch-Site: none\r\n")
    assert status == 302 and headers["Location"] == "https://github.com/o/r/issues/90"
    assert "gh-issue-90" in state(env)["seen"]


def test_head_request_does_not_mark_read(env):
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", method="HEAD")
    assert status == 302
    assert "gh-issue-90" not in state(env)["seen"]


def test_unknown_or_hostile_ids_never_redirect(env):
    run(env, "collect")
    for path in ("/seen/gh-issue-999", "/seen/..%2F..%2Fetc", "/seen/../x", "/seen/", "/"):
        status, headers, _ = http(env, path)
        assert status in (404, 400), path
        assert "Location" not in headers


@pytest.mark.parametrize("extra", [
    "Sec-Fetch-Site: cross-site\r\n",
    "Sec-Fetch-Site: same-site\r\n",
    "Referer: https://evil.example/\r\n",
    "Origin: https://evil.example\r\n",
    "Sec-Purpose: prefetch\r\n",
    "Purpose: prefetch\r\n",
])
def test_requests_that_are_not_a_user_click_cannot_mark_read(env, extra):
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", extra=extra)
    assert status == 403
    assert "gh-issue-90" not in state(env)["seen"]


def test_foreign_host_header_is_refused(env):
    """DNS rebinding: a page that points its own name at 127.0.0.1 must not be served."""
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", host=f"evil.example:{PORT}")
    assert status == 403
    assert "gh-issue-90" not in state(env)["seen"]


def test_local_html_report_is_served_sandboxed_and_marked_read(env):
    (reports(env) / "r.html").write_text("<title>Rapport</title><p>hei</p>")
    run(env, "collect")
    rid = file_id(env, "r.html")
    status, headers, body = http(env, f"/seen/{rid}")
    assert status == 200 and b"hei" in body and headers["Content-Type"].startswith("text/html")
    assert "sandbox" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert rid in state(env)["seen"]


def test_symlink_out_of_reports_dir_is_not_served_or_marked(env, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    (reports(env) / "x.txt").symlink_to(secret)
    run(env, "collect")
    rid = file_id(env, "x.txt")
    status, _, body = http(env, f"/seen/{rid}")
    assert status == 404 and b"TOPSECRET" not in body
    assert rid not in state(env)["seen"]


def test_an_idle_connection_is_dropped(env):
    r, w = os.pipe()  # the write end stays open: the client never sends a request
    t = time.monotonic()
    p = subprocess.run([sys.executable, "-c",
                        "import importlib.util,sys;"
                        f"s=importlib.util.spec_from_file_location('ri',{str(SCRIPT)!r});"
                        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                        "m.REQUEST_TIMEOUT=1;m.cmd_serve_one()"],
                       stdin=r, capture_output=True, env=env["env"], timeout=20)
    os.close(w)
    os.close(r)
    assert time.monotonic() - t < 10 and p.returncode != 0


# --- state and setup -------------------------------------------------------------

def test_corrupt_state_starts_empty(env):
    d = env["home"] / ".claude" / "superpowers-gstack"
    d.mkdir(parents=True)
    (d / "report-inbox.json").write_text("{not json")
    run(env, "collect")
    assert "gh-issue-90" in state(env)["items"]


def test_seen_rejects_bad_ids(env):
    r = subprocess.run([sys.executable, str(SCRIPT), "seen", "../x"], capture_output=True, text=True, env=env["env"])
    assert r.returncode == 2


def test_written_plists_match_the_script_and_setup(env, tmp_path):
    out = run(env, "write-plists", str(tmp_path / "agents"), str(tmp_path / "log"))
    labels = out.split()
    setup_labels = re.search(r"^LABELS=\((.*)\)$", SETUP.read_text(), re.M).group(1).split()
    assert labels == setup_labels, "setup-hooks.sh LABELS must match report-inbox.py"
    seen = plistlib.loads((tmp_path / "agents" / "com.paretofilm.sg-report-seen.plist").read_bytes())
    notify = plistlib.loads((tmp_path / "agents" / "com.paretofilm.sg-report-notify.plist").read_bytes())
    assert seen["Sockets"]["Listener"]["SockServiceName"] == PORT
    assert seen["Sockets"]["Listener"]["SockNodeName"] == "127.0.0.1"
    assert "StandardOutPath" not in seen, "in inetd mode stdout is the HTTP connection"
    assert seen["ProgramArguments"][1] == str(SCRIPT.resolve())
    assert notify["StartCalendarInterval"] == {"Hour": 17, "Minute": 0}
    for spec in (seen, notify):
        assert "/opt/homebrew/bin" in spec["EnvironmentVariables"]["PATH"]


def test_setup_refuses_a_directory_outside_git(tmp_path):
    copy = tmp_path / "plugin" / "scripts"
    copy.mkdir(parents=True)
    (copy / "setup-hooks.sh").write_text(SETUP.read_text())
    r = subprocess.run(["bash", str(copy / "setup-hooks.sh")], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    assert r.returncode == 1 and "not a git checkout" in r.stdout
