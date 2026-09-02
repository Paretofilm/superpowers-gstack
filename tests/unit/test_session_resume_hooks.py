"""Guard scripts/capture-session-tail.sh and scripts/session-resume.sh.

The pair closes the trust gap around progress.md/handoff.md: rich state files
existed but nothing surfaced them at session start, and nothing salvaged the
very last exchange when /clear discarded the context. Capture is deterministic
(SessionEnd, shell-only — no model is available there); resume is the visible
banner (SessionStart). Signal discipline as with the branch-hygiene hook:
silent when there is nothing to say, and never, ever fail the session.
"""

import json
import subprocess
import pathlib
import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
CAPTURE = SCRIPTS / "capture-session-tail.sh"
RESUME = SCRIPTS / "session-resume.sh"

ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin"}


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, **kw)


def run_capture(cwd, payload):
    r = subprocess.run(["bash", str(CAPTURE)], input=json.dumps(payload), cwd=str(cwd),
                       capture_output=True, text=True, env={**ENV, "HOME": str(cwd)})
    assert r.returncode == 0, f"hook must never fail a session: {r.stderr}"
    return r.stdout


def run_resume(cwd):
    r = subprocess.run(["bash", str(RESUME)], cwd=str(cwd),
                       capture_output=True, text=True, env={**ENV, "HOME": str(cwd)})
    assert r.returncode == 0, f"hook must never fail a session: {r.stderr}"
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    """A git repo that uses the workflow (docs/superpowers/ exists)."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t.t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("a")
    git(tmp_path, "add", "-A"); git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    return tmp_path


def transcript(tmp_path, entries):
    """Write a Claude Code-style JSONL transcript. entries = [(type, text), ...]."""
    p = tmp_path / "transcript.jsonl"
    lines = []
    for typ, text in entries:
        content = text if typ == "user" else [{"type": "text", "text": text}]
        lines.append(json.dumps({"type": typ, "message": {"role": typ, "content": content}}))
    p.write_text("\n".join(lines) + "\n")
    return p


def payload(repo, transcript_path, reason="clear"):
    return {"session_id": "s1", "transcript_path": str(transcript_path),
            "cwd": str(repo), "hook_event_name": "SessionEnd", "reason": reason}


def capture_file(repo):
    return repo / ".git" / "gstack-last-session.md"


# ---------------------------------------------------------------- capture ----

def test_capture_writes_tail_inside_git_dir(repo, tmp_path):
    """The salvage file lives in .git/ so `git add -A` can never commit a
    transcript excerpt — the whole commit-hazard class is designed away."""
    t = transcript(tmp_path, [("user", "fiks lisens-buggen"),
                              ("assistant", "Buggen er fikset og testene er grønne.")])
    run_capture(repo, payload(repo, t))
    content = capture_file(repo).read_text()
    assert "reason: clear" in content
    assert "fiks lisens-buggen" in content
    assert "testene er grønne" in content
    assert "main" in content  # git snapshot: branch


def test_capture_silent_outside_workflow_repo(tmp_path):
    """A repo without docs/superpowers/ has opted out — no litter."""
    git(tmp_path, "init", "-q", "-b", "main")
    t = transcript(tmp_path, [("assistant", "hello")])
    run_capture(tmp_path, payload(tmp_path, t))
    assert not capture_file(tmp_path).exists()


def test_capture_survives_missing_transcript(repo):
    """Transcript gone or unreadable → still record the git snapshot."""
    run_capture(repo, payload(repo, repo / "does-not-exist.jsonl"))
    content = capture_file(repo).read_text()
    assert "main" in content


def test_capture_non_git_cwd_is_silent(tmp_path):
    d = tmp_path / "plain"
    (d / "docs" / "superpowers").mkdir(parents=True)
    t = transcript(tmp_path, [("assistant", "hi")])
    run_capture(d, payload(d, t))
    assert not (d / ".git").exists()


def test_capture_garbage_stdin_is_survived(repo):
    r = subprocess.run(["bash", str(CAPTURE)], input="not json at all", cwd=str(repo),
                       capture_output=True, text=True, env={**ENV, "HOME": str(repo)})
    assert r.returncode == 0


def test_capture_truncates_long_messages(repo, tmp_path):
    t = transcript(tmp_path, [("assistant", "x" * 5000)])
    run_capture(repo, payload(repo, t))
    content = capture_file(repo).read_text()
    assert len(content) < 3000
    assert "[truncated]" in content


def test_capture_reads_only_the_tail_of_huge_transcripts(repo, tmp_path):
    """Long sessions produce transcripts of tens of MB; parsing every line
    would blow the 10s hook timeout and silently kill capture on exactly the
    sessions that need it most. The script must seek to the tail — proven
    here by planting an invalid line early: line-by-line parsing from the
    start would still work, so instead we require speed AND correctness on a
    file large enough that full-parse is measurably slower."""
    import time
    p = tmp_path / "transcript.jsonl"
    filler = json.dumps({"type": "assistant",
                         "message": {"role": "assistant",
                                     "content": [{"type": "text", "text": "old " * 50}]}})
    with p.open("w") as f:
        for _ in range(200_000):
            f.write(filler + "\n")
        f.write(json.dumps({"type": "assistant",
                            "message": {"role": "assistant",
                                        "content": [{"type": "text",
                                                     "text": "the final answer"}]}}) + "\n")
    assert p.stat().st_size > 40_000_000
    start = time.monotonic()
    run_capture(repo, payload(repo, p))
    elapsed = time.monotonic() - start
    content = capture_file(repo).read_text()
    assert "the final answer" in content
    assert elapsed < 3, f"capture took {elapsed:.1f}s — must stay far under the 10s hook timeout"


def test_capture_overwrites_previous(repo, tmp_path):
    t1 = transcript(tmp_path, [("assistant", "first session")])
    run_capture(repo, payload(repo, t1))
    t2 = transcript(tmp_path, [("assistant", "second session")])
    run_capture(repo, payload(repo, t2))
    content = capture_file(repo).read_text()
    assert "second session" in content
    assert "first session" not in content


def test_capture_skips_meta_user_entries(repo, tmp_path):
    """Skill invocations land in the transcript as type:"user" entries with
    isMeta:true carrying the expanded skill body — verified against a real
    transcript 2026-09-02 (4 such entries). Capturing one as 'last user
    message' would preserve skill instructions instead of the user's words.
    Found by Codex review."""
    p = tmp_path / "transcript.jsonl"
    real = {"type": "user", "message": {"role": "user", "content": "fortsett med fase 4"}}
    meta = {"type": "user", "isMeta": True,
            "message": {"role": "user", "content": [{"type": "text",
                        "text": "# Skill Title\nInstructions for the skill..."}]}}
    asst = {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": "Fase 4 er i gang."}]}}
    p.write_text("\n".join(json.dumps(e) for e in (real, meta, asst)) + "\n")
    run_capture(repo, payload(repo, p))
    content = capture_file(repo).read_text()
    assert "fortsett med fase 4" in content
    assert "Instructions for the skill" not in content


def test_capture_finds_user_message_beyond_first_tail_window(repo, tmp_path):
    """A tool-heavy closing turn can put >256KB of tool-result entries between
    the user's prompt and EOF; a fixed window then silently drops the user
    half of the exchange. The scan must widen until it has both. Found by
    Codex review."""
    p = tmp_path / "transcript.jsonl"
    filler = json.dumps({"type": "user",
                         "message": {"role": "user",
                                     "content": [{"type": "tool_result",
                                                  "content": "x" * 2000}]}})
    with p.open("w") as f:
        f.write(json.dumps({"type": "user", "message": {
            "role": "user", "content": "kjør hele testsuiten"}}) + "\n")
        for _ in range(300):
            f.write(filler + "\n")
        f.write(json.dumps({"type": "assistant", "message": {
            "role": "assistant", "content": [{"type": "text",
                                              "text": "Suiten er grønn."}]}}) + "\n")
    assert p.stat().st_size > 300_000
    run_capture(repo, payload(repo, p))
    content = capture_file(repo).read_text()
    assert "kjør hele testsuiten" in content
    assert "Suiten er grønn" in content


# ----------------------------------------------------------------- resume ----

def test_resume_silent_when_nothing_exists(repo):
    """No progress.md, no handoff, no capture → not one byte of noise."""
    assert run_resume(repo) == ""


def test_resume_silent_in_non_git_dir(tmp_path):
    assert run_resume(tmp_path) == ""


PROGRESS = """# Generalprøve-programmet

> Rullerende fremdriftsfil.

## Meta

- Repo: x

## Fullførte faser

1. **Precheck + dev-gren sikret** (2026-09-02): grønn.
2. **Speilingsverktøy skrevet**: ferdig.

## Gjenstående faser

3. **Upgrade-test dev→staging**: kjør scriptet.
4. **Rollback-øvelse**: verifiser pool.
"""


def test_resume_summarizes_progress(repo):
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(PROGRESS)
    out = run_resume(repo)
    assert "Generalprøve-programmet" in out
    assert "2" in out            # completed count
    assert "Upgrade-test" in out  # next remaining phase


def test_resume_progress_english_headings(repo):
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(
        "# Big Plan\n\n## Completed phases\n\n1. **Setup done**: ok.\n\n"
        "## Remaining phases\n\n2. **Ship it**: go.\n")
    out = run_resume(repo)
    assert "Big Plan" in out
    assert "Ship it" in out


def test_resume_next_skips_struck_through_items(repo):
    """Real progress files strike out finished items inside the remaining
    section (~~...~~ ✅). 'Next' must be the first item still open — found
    live against fagfilm's progress.md on 2026-09-02."""
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(
        "# Plan\n\n## Gjenstående faser\n\n"
        "3. ~~**Verifiser rollback-bygget**~~ ✅ 2026-09-02\n"
        "4. **Rollback-øvelse**: verifiser pool.\n")
    out = run_resume(repo)
    assert "Rollback-øvelse" in out
    assert "Verifiser rollback-bygget" not in out


def test_resume_progress_without_recognized_headings_falls_back(repo):
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(
        "# Freeform notes\n\nsome prose, no phase sections\n")
    out = run_resume(repo)
    assert "progress.md" in out  # presence + fallback, no crash, no lie


def test_resume_shows_handoff_next_step(repo):
    (repo / "docs" / "superpowers" / "handoff.md").write_text(
        "---\ntype: handoff\nsession_end: 2026-09-01T10:00:00+02:00\n"
        "next_step: \"Bestem om CLAUDE.md skal committes\"\n---\n\nprose\n")
    out = run_resume(repo)
    assert "Bestem om CLAUDE.md skal committes" in out


def test_resume_ignores_incomplete_handoff(repo):
    """No next_step → not presentable; classification stays the model's job."""
    (repo / "docs" / "superpowers" / "handoff.md").write_text(
        "---\ntype: handoff\nmode: continuous\n---\n")
    out = run_resume(repo)
    assert out == ""


def test_resume_rejects_handoff_with_foreign_type(repo):
    """The legacy form (session_end + next_step, no type:) is only legacy when
    type is ABSENT — `type: notes` beside those keys is a different artifact
    and must not be presented as resumable. Found by Codex review against the
    session-continuity contract."""
    (repo / "docs" / "superpowers" / "handoff.md").write_text(
        "---\ntype: notes\nsession_end: 2026-09-01T10:00:00+02:00\n"
        "next_step: \"ikke en handoff\"\n---\n")
    assert run_resume(repo) == ""


def test_resume_partial_checkmark_does_not_finish_item(repo):
    """`**Fase 3**: backend ✅, frontend pending` is half-done — a checkmark
    mid-text must not mark the whole phase finished, or the banner skips the
    real next phase. Only whole-item markers count (leading ~~ or [x]).
    Found by Codex review."""
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(
        "# Plan\n\n## Gjenstående faser\n\n"
        "3. **Delvis fase**: backend ✅, frontend pending\n"
        "4. **Neste fase**: alt gjenstår.\n")
    out = run_resume(repo)
    assert "Delvis fase" in out


def test_resume_shows_last_session_capture(repo, tmp_path):
    t = transcript(tmp_path, [("assistant", "Fikset callback-URLene til slutt.")])
    run_capture(repo, payload(repo, t))
    out = run_resume(repo)
    assert "Fikset callback-URLene" in out


def test_resume_instruction_line_only_when_speaking(repo):
    assert "agent" not in run_resume(repo).lower()
    (repo / "docs" / "superpowers" / "plans" / "progress.md").write_text(PROGRESS)
    assert "agent" in run_resume(repo).lower()
