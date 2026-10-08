"""Guard scripts/report-inbox.py — the maintainer's report inbox.

Exists because three `model-review` issues sat unread for a month: the only
SessionStart reminder looked at one label, cached its answer for a day, and had
no notion of "read". The inbox must surface every report kind, stay silent once
everything is read, remind at most once a day, and only ever mark a report read
when its link is actually followed.
"""

import io
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "report-inbox.py"
WRAPPER = ROOT / "scripts" / "notify-pending-updates.sh"
PORT = "47817"

ISSUES = {
    "notification": [{"number": 7, "title": "Manual update ready", "url": "https://github.com/o/r/issues/7",
                      "createdAt": "2026-09-01T00:00:00Z"}],
    "model-review": [{"number": 90, "title": "New Claude model — sonnet", "url": "https://github.com/o/r/issues/90",
                      "createdAt": "2026-10-05T00:00:00Z"}],
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


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fixture = tmp_path / "gh.json"
    fixture.write_text(json.dumps({"issue": ISSUES, "pr": PRS}))
    write_stub(bindir, "gh", f"""
        import json, sys
        a = sys.argv[1:]
        data = json.load(open({str(fixture)!r}))
        if data.get("fail"):
            sys.exit(1)
        label = a[a.index("--label") + 1]
        print(json.dumps(data[a[0]].get(label, [])))
    """)
    calls = tmp_path / "notifier.log"
    write_stub(bindir, "terminal-notifier", f"""
        import json, sys
        open({str(calls)!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
    """)
    e = {"PATH": f"{bindir}:/usr/bin:/bin:/usr/local/bin", "HOME": str(home),
         "SG_REPORT_REPO": "o/r", "SG_REPORT_PORT": PORT}
    return {"env": e, "home": home, "fixture": fixture, "calls": calls, "bindir": bindir}


def run(env, *args, stdin=None):
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=stdin is None,
                       input=stdin, env=env["env"])
    assert r.returncode == 0, r.stderr
    return r.stdout


def state(env):
    return json.loads((env["home"] / ".claude" / "superpowers-gstack" / "report-inbox.json").read_text())


def install_tracker(env):
    agents = env["home"] / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.paretofilm.sg-report-seen.plist").write_text("x")


def http(env, path, method="GET", host=f"127.0.0.1:{PORT}", extra=""):
    req = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: t\r\n{extra}\r\n".encode()
    out = run(env, "serve-one", stdin=req)
    head, _, body = out.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    status = int(lines[0].split()[1])
    headers = dict(l.split(": ", 1) for l in lines[1:])
    return status, headers, body


def test_collect_takes_every_report_kind_but_not_auto_update_prs(env):
    run(env, "collect")
    assert set(state(env)["items"]) == {"gh-issue-7", "gh-issue-90", "gh-pr-12"}


def test_local_report_files_join_the_inbox(env):
    reports = env["home"] / ".claude" / "superpowers-gstack" / "reports"
    reports.mkdir(parents=True)
    (reports / "Routing 2026-10.md").write_text("# Routing report October\n")
    (reports / ".hidden.md").write_text("# no")
    run(env, "collect")
    item = state(env)["items"]["file-routing-2026-10.md"]
    assert item["title"] == "Routing report October"


def test_banner_lists_unread_with_tracking_links(env):
    install_tracker(env)
    out = run(env, "banner")
    assert "Unread reports (3)" in out
    assert f"http://127.0.0.1:{PORT}/seen/gh-issue-90" in out
    assert "Alerts" in out  # one-time hint about the notification style


def test_alert_hint_is_shown_once(env):
    install_tracker(env)
    run(env, "banner")
    assert "Alerts" not in run(env, "banner")


def test_banner_without_tracker_falls_back_to_plain_links(env):
    out = run(env, "banner")
    assert "https://github.com/o/r/issues/90" in out
    assert "/seen/" not in out
    assert "setup-hooks.sh" in out


def test_banner_is_silent_when_everything_is_read(env):
    run(env, "collect")
    for rid in ("gh-issue-7", "gh-issue-90", "gh-pr-12"):
        run(env, "seen", rid)
    assert run(env, "banner") == ""


def test_banner_never_fails_without_gh(env):
    (env["bindir"] / "gh").unlink()
    env["env"]["PATH"] = f"{env['bindir']}:/usr/bin:/bin"
    assert run(env, "banner") == ""


def test_wrapper_hook_exits_zero_and_prints_banner(env):
    r = subprocess.run(["bash", str(WRAPPER)], capture_output=True, text=True, env=env["env"])
    assert r.returncode == 0
    assert "Unread reports (3)" in r.stdout


def test_github_outage_keeps_the_previous_reports(env):
    run(env, "collect")
    env["fixture"].write_text(json.dumps({"fail": True}))
    run(env, "collect", "--force")
    assert "gh-issue-90" in state(env)["items"]


def test_closed_issue_drops_out(env):
    run(env, "collect")
    run(env, "seen", "gh-issue-7")
    data = json.loads(env["fixture"].read_text())
    data["issue"]["notification"] = []
    env["fixture"].write_text(json.dumps(data))
    run(env, "collect", "--force")
    s = state(env)
    assert "gh-issue-7" not in s["items"] and "gh-issue-7" not in s["seen"]


def test_notify_sends_one_clickable_notification_per_unread_report_once_a_day(env):
    run(env, "notify")
    calls = [json.loads(l) for l in env["calls"].read_text().splitlines()]
    assert len(calls) == 3
    c = next(c for c in calls if "New Claude model — sonnet" in c)
    assert c[c.index("-open") + 1] == f"http://127.0.0.1:{PORT}/seen/gh-issue-90"
    assert c[c.index("-group") + 1] == "sg-report-gh-issue-90"
    run(env, "notify")
    assert len(env["calls"].read_text().splitlines()) == 3, "second run the same day must be silent"


def test_notify_skips_read_reports_and_resumes_next_day(env):
    run(env, "notify")
    run(env, "seen", "gh-issue-90")
    s = state(env)
    s["last_notified"] = "2000-01-01"
    (env["home"] / ".claude" / "superpowers-gstack" / "report-inbox.json").write_text(json.dumps(s))
    env["calls"].write_text("")
    run(env, "notify")
    calls = env["calls"].read_text()
    assert calls.count("\n") == 2 and "gh-issue-90" not in calls


def test_click_marks_read_and_redirects(env):
    run(env, "collect")
    status, headers, _ = http(env, "/seen/gh-issue-90")
    assert status == 302 and headers["Location"] == "https://github.com/o/r/issues/90"
    assert "gh-issue-90" in state(env)["seen"]


def test_head_request_does_not_mark_read(env):
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", method="HEAD")
    assert status == 302
    assert "gh-issue-90" not in state(env)["seen"]


def test_unknown_or_hostile_ids_never_redirect(env):
    run(env, "collect")
    for path in ("/seen/gh-issue-999", "/seen/..%2F..%2Fetc", "/seen/../x", "/seen/"):
        status, headers, _ = http(env, path)
        assert status in (404, 400), path
        assert "Location" not in headers


def test_foreign_host_header_is_refused(env):
    """DNS rebinding: a page that points its own name at 127.0.0.1 must not be served."""
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", host=f"evil.example:{PORT}")
    assert status == 403
    assert "gh-issue-90" not in state(env)["seen"]


def test_cross_site_request_cannot_mark_read(env):
    """Another page's <img src=...> carries the right Host; Sec-Fetch-Site gives it away."""
    run(env, "collect")
    status, _, _ = http(env, "/seen/gh-issue-90", extra="Sec-Fetch-Site: cross-site\r\n")
    assert status == 403
    assert "gh-issue-90" not in state(env)["seen"]
    status, _, _ = http(env, "/seen/gh-issue-90", extra="Sec-Fetch-Site: none\r\n")
    assert status == 302 and "gh-issue-90" in state(env)["seen"]


def test_local_report_is_served_and_marked_read(env):
    reports = env["home"] / ".claude" / "superpowers-gstack" / "reports"
    reports.mkdir(parents=True)
    (reports / "r.html").write_text("<title>Rapport</title><p>hei</p>")
    run(env, "collect")
    status, headers, body = http(env, "/seen/file-r.html")
    assert status == 200 and b"hei" in body and headers["Content-Type"].startswith("text/html")
    assert "file-r.html" in state(env)["seen"]


def test_index_lists_unread(env):
    run(env, "collect")
    status, _, body = http(env, "/")
    assert status == 200 and b"/seen/gh-pr-12" in body


def test_corrupt_state_starts_empty(env):
    d = env["home"] / ".claude" / "superpowers-gstack"
    d.mkdir(parents=True)
    (d / "report-inbox.json").write_text("{not json")
    run(env, "collect")
    assert "gh-issue-90" in state(env)["items"]


def test_seen_rejects_bad_ids(env):
    r = subprocess.run([sys.executable, str(SCRIPT), "seen", "../x"], capture_output=True, text=True, env=env["env"])
    assert r.returncode == 2
