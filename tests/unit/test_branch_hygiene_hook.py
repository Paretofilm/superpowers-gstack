"""Guard scripts/check-branch-hygiene.sh — the unlanded-work detector.

Exists because a plugin that ships /ship and finishing-a-development-branch still
had nothing that NOTICED a branch was never landed. Signal discipline is the whole
design: silent on a clean repo and on work in progress, loud only on work that has
actually been left behind.
"""

import os
import signal
import subprocess
import pathlib
import re
import time
import pytest

HOOK = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "check-branch-hygiene.sh"


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, **kw)


def run_hook(repo, idle_days="7", **extra_env):
    r = subprocess.run(["bash", str(HOOK)], cwd=str(repo), capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo),
                            "GSTACK_BRANCH_IDLE_DAYS": idle_days, **extra_env})
    assert r.returncode == 0, f"hook must never fail a session: {r.stderr}"
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t.t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("a")
    git(tmp_path, "add", "-A"); git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_clean_repo_is_silent(repo):
    """A hook that speaks when there is nothing to say gets ignored when there is."""
    assert run_hook(repo) == ""


def test_non_git_directory_is_silent(tmp_path):
    assert run_hook(tmp_path) == ""


def test_uncommitted_changes_are_reported(repo):
    (repo / "f.txt").write_text("changed")
    assert "file(s) not committed" in run_hook(repo)


def test_current_branch_is_never_nagged(repo):
    """Committing on a branch you are standing on is work in progress, not debt."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    assert run_hook(repo) == ""


def test_recent_unmerged_branch_is_not_nagged(repo):
    """Below the idle threshold is active work — reporting it would be noise."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    git(repo, "checkout", "-q", "main")
    assert run_hook(repo, idle_days="7") == ""


def test_idle_unmerged_branch_is_reported(repo):
    """Same branch, genuinely old — now it is at risk of being forgotten."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A")
    old_date = "2020-01-01T00:00:00"
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "wip"], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
                        "GIT_AUTHOR_DATE": old_date, "GIT_COMMITTER_DATE": old_date,
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t"})
    git(repo, "checkout", "-q", "main")
    out = run_hook(repo)
    assert "feature" in out and "never merged into" in out


def test_invalid_threshold_falls_back_instead_of_crashing(repo):
    """A hook that aborts on a typo'd env var is worse than one that ignores it."""
    (repo / "f.txt").write_text("changed")
    assert "file(s) not committed" in run_hook(repo, idle_days="seven")


def test_disable_switch_silences_everything(repo):
    (repo / "f.txt").write_text("changed")
    assert run_hook(repo, idle_days="0") == ""


# --- blind spots found 2026-08-22 while documenting the hook for end users -------
# Both are "work can disappear" cases that every branch-based check missed: a branch
# fully merged locally but never pushed reported nothing, and a stash is not a branch
# at all. Documenting the tool is how they surfaced — writing down what it does not
# catch is a cheaper audit than re-reading the code.


def with_remote(tmp_path, repo):
    """Give `repo` a real upstream so ahead/behind counts are meaningful."""
    # OUTSIDE the work tree — a bare repo created inside it shows up as an
    # untracked directory and the hook correctly reports a dirty tree, which
    # looks like a hook bug and is a test-harness bug.
    bare = tmp_path.parent / f"{tmp_path.name}-remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")
    return bare


def test_pushed_and_clean_is_silent(tmp_path, repo):
    with_remote(tmp_path, repo)
    assert run_hook(repo) == ""


def test_unpushed_commits_are_reported(tmp_path, repo):
    """A commit that exists only on this machine is one disk failure from gone."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("local only")
    git(repo, "commit", "-qam", "local only")
    out = run_hook(repo)
    assert "Only on this computer" in out and "commit(s) not pushed" in out


def test_local_only_repo_is_never_nagged_about_pushing(tmp_path, repo):
    """No remote configured means pushing is not a thing this repo can do. Saying so
    every session would be noise — and noise is what makes a hook get ignored."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    git(repo, "checkout", "-q", "main")
    assert "Only on this computer" not in run_hook(repo)


def test_never_pushed_branch_is_reported(tmp_path, repo):
    """Premise inverted in 2.42.0. This was excluded as "already covered by the
    stale-unmerged check" — but that check skips the branch you are standing on, so
    the intersection (current branch, never pushed) was covered by NEITHER. Verified
    empirically at five commits with no warning ever, which is the default state of
    someone whose agent commits for them and who has never heard of pushing."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    assert "never pushed" in run_hook(repo)


def test_never_pushed_is_reported_once_not_twice(tmp_path, repo):
    """Reported by the backup check, not also by the stale check — one piece of work,
    one line. Double-reporting is how a warning trains you to skim past it."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    findings = findings_of(run_hook(repo))
    assert findings.count("feature") == 1


def test_destructive_options_are_never_offered_first(tmp_path, repo):
    """A remedy a novice cannot evaluate must not be the first thing they read.
    Deleting stays possible; it is just never the opening suggestion."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("changed")
    out = run_hook(repo)
    assert "discard" not in out and "drop" not in out
    assert "git push" in out or "commit" in out


def test_disable_switch_is_not_advertised_to_the_user(tmp_path, repo):
    """The escape hatch was printed on every firing — handing the off switch to the
    reader least able to judge whether the warning mattered. Still supported, no
    longer advertised."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("changed")
    assert "GSTACK_BRANCH_IDLE_DAYS" not in run_hook(repo)


def test_fresh_stash_is_not_nagged(tmp_path, repo):
    """A fresh stash is a short hold typed by hand (git-hygiene steers agents to WIP
    branches instead) — not debt until it outlives the idle threshold."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("wip"); git(repo, "stash", "-q")
    assert "stashed changes" not in run_hook(repo)


def test_stale_stash_is_reported(tmp_path, repo):
    """Past the threshold it stopped being a hold and became forgotten work."""
    with_remote(tmp_path, repo)
    (repo / "f.txt").write_text("wip")
    subprocess.run(["git", "-C", str(repo), "stash", "-q"], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
                        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
                        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})
    out = run_hook(repo)
    assert "stashed changes" in out and "parked change set" in out


# --- worktrees (2.41.0) ---------------------------------------------------------
# `git status` only ever reports the tree you stand in, so uncommitted work in a
# sibling worktree was invisible — while refs/heads is shared, so its BRANCH was
# already checked. Half-covered is the worst state: the branch looked fine and the
# uncommitted work went unmentioned. Relevant in practice because the Agent tool's
# `isolation: "worktree"` mode auto-removes a temp worktree only when UNCHANGED —
# one that produced changes is left on disk by design.


def add_worktree(repo, path, branch):
    git(repo, "worktree", "add", "-q", str(path), "-b", branch)
    return path


def test_clean_worktrees_are_silent(tmp_path, repo):
    with_remote(tmp_path, repo)
    add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "feature")
    assert run_hook(repo) == ""


def test_uncommitted_work_in_another_worktree_is_reported(tmp_path, repo):
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "feature")
    (wt / "stranded.txt").write_text("work nobody will revisit")
    out = run_hook(repo)
    assert "second working folder" in out and "feature" in out


def test_current_and_other_worktree_are_counted_separately(tmp_path, repo):
    """The current tree is already covered by dirty_n; counting it again in the
    worktree scan would report one change twice."""
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "feature")
    (wt / "there.txt").write_text("x")
    (repo / "here.txt").write_text("y")
    out = run_hook(repo)
    assert "1 file(s) not committed" in out      # here, not 2
    assert "1 loose file(s)" in out              # there, not 2


def test_deleted_worktree_directory_does_not_crash(tmp_path, repo):
    """A worktree whose directory was removed but not pruned is a normal state; the
    hook must skip it, not abort the session."""
    import shutil
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "feature")
    shutil.rmtree(wt)
    run_hook(repo)  # run_hook already asserts exit 0


# --- the agent menu (2.43.0) ----------------------------------------------------
# 2.42.0 made the report readable; it still ended in commands, and a command printed
# for someone who does not use a terminal is a task handed back to the person least
# able to do it. The report now names the work and hands the AGENT a menu, which it
# turns into choices the user clicks. These tests guard that split.

MENU = "What can be done"


def action_label(menu, n):
    """The verb of option `n` — asserting on the whole line catches 'deleted by this'
    in a description and calls an inspection destructive."""
    line = [l for l in menu.splitlines() if l.strip().startswith(f"{n}. ")][0]
    return line.split(f"{n}.", 1)[1].split()[0]


def findings_of(out):
    """Everything above the menu — what the user is actually being told."""
    return out.split(MENU)[0]


def test_findings_never_hand_the_user_a_command(tmp_path, repo):
    """The old report's first remedy line was a shell command. Naming the work is
    the report's job; running the command is the agent's. Any 'git ...' above the
    menu is that boundary leaking back."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    (repo / "loose.txt").write_text("y")
    assert "git " not in findings_of(run_hook(repo))


def test_menu_names_the_work_it_would_act_on(tmp_path, repo):
    """An action whose target the agent has to re-derive is an action it will get
    wrong. The menu carries the branch name so the offer can be concrete."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "login-screen")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    menu = run_hook(repo).split(MENU)[1]
    assert "1. back up" in menu and "login-screen" in menu


def test_first_action_preserves_even_when_cleanup_is_available(tmp_path, repo):
    """Ordering is the safety property: someone who picks option 1 without reading
    the rest must land on the one that only saves. Deleting branches is offered —
    below, and never as 1."""
    with_remote(tmp_path, repo)
    for n in range(5):
        git(repo, "branch", f"done-{n}", "main")
    (repo / "loose.txt").write_text("x")
    menu = run_hook(repo).split(MENU)[1]
    assert menu.index("back up") < menu.index("tidy")
    assert "1. back up" in menu


def test_option_one_is_never_destructive_even_with_nothing_else_to_offer(tmp_path, repo):
    """Regression, found by Codex and reproduced: in a repo whose ONLY finding was
    merged clutter, the menu's sole entry was `1. tidy  delete 6 branch(es)` — under
    a printed guarantee that option 1 only preserves. A user who clicks 1 without
    reading must never be authorising a deletion."""
    with_remote(tmp_path, repo)
    for n in range(6):
        git(repo, "branch", f"done-{n}", "main")
    menu = run_hook(repo).split(MENU)[1]
    assert action_label(menu, 1) == "show"     # inspection, not deletion
    assert "tidy" in menu                       # still offered, just not first


def test_hostile_branch_name_is_quoted_before_it_reaches_the_menu(tmp_path, repo):
    """`safe$(whoami)` is a branch name git accepts. The menu exists to be turned
    into shell commands by an agent, so an unquoted ref there is repo-controlled
    input on its way to a command line. Quoted, it survives eval as a literal."""
    with_remote(tmp_path, repo)
    hostile = "wip$(whoami)"
    git(repo, "checkout", "-qb", hostile)
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "wip")
    menu = run_hook(repo).split(MENU)[1]
    assert f"'{hostile}'" in menu, "ref must appear single-quoted in the menu"
    # and quoting must actually neutralise it, not merely decorate it
    quoted = [w for w in menu.split() if w.startswith("'wip")][0]
    out = subprocess.run(["bash", "-c", f"printf '%s' {quoted}"], capture_output=True, text=True)
    assert out.stdout == hostile


# --- the worktree lifecycle (2.44.0) --------------------------------------------
# The plugin scans worktrees, superpowers ships a skill that creates them, and the
# Agent tool leaves one behind exactly when it produced changes. Carrying that work
# to the default branch has its own failure modes, and each of these was silent.


def add_detached_worktree(repo, path):
    git(repo, "worktree", "add", "-q", "--detach", str(path), "HEAD")
    return path


def test_commits_in_a_detached_worktree_are_reported(tmp_path, repo):
    """Verified as total silence before the fix: every other check walks refs/heads,
    and a detached worktree's commits are in no branch. Remove the folder and they
    are unreachable — the sharpest way to lose work this hook has found."""
    with_remote(tmp_path, repo)
    wt = add_detached_worktree(repo, tmp_path.parent / f"{tmp_path.name}-det")
    (wt / "work.txt").write_text("three hours")
    git(wt, "add", "-A"); git(wt, "commit", "-qm", "detached work")
    out = run_hook(repo)
    assert "in no branch" in out
    assert "switch -c" in out.split(MENU)[1]


def test_worktree_branch_is_not_counted_as_deletable_clutter(tmp_path, repo):
    """`git branch -d` refuses a branch checked out in a worktree. Counting it made
    the tidy action a command that fails partway and returns next session."""
    with_remote(tmp_path, repo)
    add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "in-a-worktree")
    git(repo, "merge", "-q", "--no-ff", "in-a-worktree", "-m", "land")
    for n in range(5):
        git(repo, "branch", f"done-{n}", "main")
    out = run_hook(repo)
    assert "5 branch(es)" in out          # the five, not the six
    assert "in-a-worktree" not in out.split("What can be done")[0].split("clutter")[-1]


def test_finish_action_says_which_folder_to_run_it_in(tmp_path, repo):
    """/ship works on the current branch, and a branch checked out in a worktree
    cannot be checked out anywhere else — git hard-fails. Naming the branch without
    naming the folder sends the agent into that error."""
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "old-feature")
    old = "2020-01-01T00:00:00"
    (wt / "f.txt").write_text("x"); git(wt, "add", "-A")
    subprocess.run(["git", "-C", str(wt), "commit", "-qm", "old", "--date", old],
                   check=True, env={"PATH": "/usr/bin:/bin", "HOME": str(repo),
                                    "GIT_COMMITTER_DATE": old,
                                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})
    git(repo, "push", "-q", "origin", "old-feature")
    git(wt, "branch", "-q", "--set-upstream-to=origin/old-feature")
    menu = run_hook(repo).split(MENU)[1]
    assert "finish" in menu and "-wt" in menu, "the folder must be named, not just the branch"


def test_squash_merged_branch_is_not_called_unmerged(tmp_path, repo):
    """A squash merge — GitHub's default — lands the content, not the commits, so an
    ancestor test says "never merged" forever about work that is already on main.
    Telling a user their shipped feature is unshipped is how a report loses its
    authority."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "squashed")
    (repo / "s.txt").write_text("x"); git(repo, "add", "-A")
    old = "2020-01-01T00:00:00"
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "work", "--date", old], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo), "GIT_COMMITTER_DATE": old,
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})
    git(repo, "push", "-q", "origin", "squashed")
    git(repo, "branch", "-q", "--set-upstream-to=origin/squashed")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--squash", "-q", "squashed")
    git(repo, "commit", "-qm", "squash: work")
    git(repo, "push", "-q", "origin", "main")
    assert git(repo, "merge-base", "--is-ancestor", "squashed", "main").returncode != 0
    assert "squashed" not in run_hook(repo)


def test_dirty_spent_worktree_is_not_offered_for_removal(tmp_path, repo):
    """`git worktree remove` refuses a dirty worktree. Offering it would be an action
    that fails when run — and the loose files are already reported as work at risk,
    so the removal is simply premature."""
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "landed")
    (wt / "f.txt").write_text("x"); git(wt, "add", "-A")
    old = "2020-01-01T00:00:00"
    subprocess.run(["git", "-C", str(wt), "commit", "-qm", "work", "--date", old], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo), "GIT_COMMITTER_DATE": old,
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})
    git(repo, "merge", "-q", "--no-ff", "landed", "-m", "land")
    (wt / "leftover.txt").write_text("still working")
    out = run_hook(repo)
    assert "not committed" in out                    # reported as at-risk
    assert "spent working folder" not in out         # but not offered for removal


def test_detached_at_an_already_pushed_tip_is_not_called_at_risk(tmp_path, repo):
    """`base..HEAD` counts commits that are already on a branch or on the remote, so
    checking out a pushed tip detached produced "gone if the disk dies" about work
    that is safely on the server. A false alarm here costs the report its credibility
    for the true ones.

    Note the fix that does NOT work: `rev-list HEAD --not --all` returns 0 always,
    because --all includes HEAD — it would have silenced the check entirely."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "pushed-feature")
    (repo / "f.txt").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "feat")
    git(repo, "push", "-q", "-u", "origin", "pushed-feature")
    git(repo, "checkout", "-q", "main")
    wt = tmp_path.parent / f"{tmp_path.name}-det"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), "pushed-feature")
    assert "in no branch" not in run_hook(repo)          # nothing is at risk here
    git(wt, "commit", "-q", "--allow-empty", "-m", "genuinely new")
    assert "in no branch" in run_hook(repo)              # ...and now there is


def test_branch_held_by_a_deleted_worktree_is_not_offered_for_deletion(tmp_path, repo):
    """A worktree whose folder was deleted by hand stays registered, and git keeps
    refusing `branch -d` until `git worktree prune` runs. Counting it made the tidy
    action fail partway; the fix is to name the prune as its own step.

    Regression guard for an ordering bug found in review: the `[ ! -d $path ]` guard
    ran before the branch was recorded, so the worktrees whose folder is gone — the
    only ones this case is about — were the ones dropped."""
    import shutil
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-gone", "held-branch")
    git(repo, "merge", "-q", "--no-ff", "held-branch", "-m", "land")
    shutil.rmtree(wt)
    for n in range(5):
        git(repo, "branch", f"done-{n}", "main")
    out = run_hook(repo)
    assert "5 branch(es)" in out                          # the five, not the six
    assert "worktree prune" in out.split(MENU)[1]


# --- offering the verification (2.46.0) -----------------------------------------
# A skill nobody remembers the name of is a skill nobody uses. The report already
# fires every session and already offers clickable actions, so it is the one place
# the check can be reached without recalling anything.


def test_report_offers_to_build_and_show_the_app(tmp_path, repo):
    with_remote(tmp_path, repo)
    (repo / "MyApp.xcodeproj").mkdir()
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "project"); git(repo, "push", "-q")
    git(repo, "checkout", "-qb", "fix-login")
    (repo / "f.swift").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "fix")
    menu = run_hook(repo).split(MENU)[1]
    assert "verify-and-land" in menu
    assert action_label(menu, 1) == "back"     # backup still outranks looking at it


def test_no_app_target_means_no_such_offer(tmp_path, repo):
    """A library has nothing to look at; offering to open an app that does not exist
    is the kind of dead-end action this report has spent four releases removing."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "fix-lib")
    (repo / "f.py").write_text("x"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "fix")
    assert "verify-and-land" not in run_hook(repo)


def test_app_target_alone_does_not_break_silence(tmp_path, repo):
    """The offer is an extra action on a report that was already firing — never a
    reason to start one. A clean, pushed repo with an app stays quiet."""
    with_remote(tmp_path, repo)
    (repo / "MyApp.xcodeproj").mkdir()
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "project"); git(repo, "push", "-q")
    assert run_hook(repo) == ""


# --- cognitive-load review (2.47.0) ---------------------------------------------


def test_backup_on_default_branch_warns_about_deploy(tmp_path, repo):
    """Auto-deploy on push to the default branch is the DEFAULT on Vercel, Netlify
    and Pages. A safety-labelled click must never be the thing that publishes
    unverified work without saying so."""
    with_remote(tmp_path, repo)
    (repo / "loose.txt").write_text("x")
    menu = run_hook(repo).split(MENU)[1]
    assert "deploys automatically" in menu


def test_no_remote_says_checkpoint_not_back_up(tmp_path, repo):
    """'Back up — make everything recoverable' about a same-disk commit is the false
    safety this report exists to remove."""
    (repo / "loose.txt").write_text("x")
    menu = run_hook(repo).split(MENU)[1]
    assert "checkpoint" in menu
    assert "recoverable" not in menu


def test_one_click_is_one_action_boundary_is_stated(tmp_path, repo):
    with_remote(tmp_path, repo)
    (repo / "loose.txt").write_text("x")
    assert "anything further is a new question" in run_hook(repo)


def test_menu_briefs_the_agent_on_how_to_turn_it_into_choices(tmp_path, repo):
    """3.0.0 moved the agent brief out of the emitted CLAUDE.md block and into the
    report itself, so the rules travel with the menu they govern: option 1 never
    destroys, a click authorizes only what it names, and a non-interactive session
    takes no action at all (a recovery branch would switch a shared worktree and could
    commit untracked secrets)."""
    with_remote(tmp_path, repo)
    (repo / "loose.txt").write_text("x")
    menu = run_hook(repo).split(MENU)[1]
    assert "Addressed to the agent" in menu
    assert "AskUserQuestion" in menu
    assert "option 1 never" in menu and "destroys anything" in menu
    assert "a click authorizes only what it names" in menu
    assert "in a non-interactive session take no action" in menu
    assert "say what you left unresolved" in menu


# --- parked work and local-only repos (3.1.2) -----------------------------------
# git-hygiene v11 parks unfinished work on wip/<topic> instead of the shared stash.
# The report had one bucket for idle unmerged branches, headed "On the server" and
# answered with /ship: wrong for a parked branch, and wrong in a repo with no remote.


def old_commit(repo, msg="old"):
    old = "2020-01-01T00:00:00"
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", msg, "--date", old], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(repo), "GIT_COMMITTER_DATE": old,
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t"})


def test_parked_wip_branch_is_offered_a_resume_not_a_ship(tmp_path, repo):
    """A pushed wip/ branch idle past the threshold was listed with unlanded features
    and offered '/ship ... opens a PR': a PR, every session, for work nobody meant to
    ship yet."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "wip/parked")
    (repo / "half.txt").write_text("half done"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "push", "-q", "-u", "origin", "wip/parked")
    git(repo, "checkout", "-q", "main")
    out = run_hook(repo)
    findings, menu = findings_of(out), out.split(MENU)[1]
    assert "Parked on wip/ branches" in findings and "wip/parked" in findings
    assert "never merged into" not in findings
    assert "git worktree add" in menu
    assert "/ship" not in menu and "finish" not in menu


def test_feature_branch_next_to_a_parked_one_is_still_offered_finish(tmp_path, repo):
    """Splitting the bucket must not swallow real unlanded work."""
    with_remote(tmp_path, repo)
    for name in ("wip/parked", "feature"):
        git(repo, "checkout", "-qb", name)
        (repo / f"{name.replace('/', '-')}.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
        git(repo, "push", "-q", "-u", "origin", name)
        git(repo, "checkout", "-q", "main")
    menu = run_hook(repo).split(MENU)[1]
    finish_line = [l for l in menu.splitlines() if "finish" in l][0]
    assert "'feature'" in finish_line
    assert "wip/parked" not in finish_line
    assert "'wip/parked'" in menu               # offered, just not as something to ship


def test_no_remote_idle_branch_is_not_called_on_the_server(repo):
    """With no remote configured nothing is on a server; saying so is the false safety
    this report exists to remove."""
    git(repo, "checkout", "-qb", "feature")
    (repo / "g.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-qb", "wip/local-only")
    (repo / "h.txt").write_text("y"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "checkout", "-q", "main")
    out = run_hook(repo)
    assert "On the server" not in out
    assert "no remote is configured" in out and "never merged into" in out
    assert "so they exist only here" in out and "wip/local-only" in findings_of(out)


def test_server_only_wip_branch_is_parked_too(tmp_path, repo):
    """A wip/ branch whose local copy is gone went through the remote-orphan check
    instead, and came back as 'On the server' with the /ship offer."""
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "wip/remote-only")
    (repo / "half.txt").write_text("half done"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "push", "-q", "origin", "wip/remote-only")
    git(repo, "checkout", "-q", "main"); git(repo, "branch", "-qD", "wip/remote-only")
    out = run_hook(repo)
    findings, menu = findings_of(out), out.split(MENU)[1]
    assert "Parked on wip/ branches" in findings and "server-only" in findings
    assert "On the server" not in findings
    assert "finish" not in menu
    # inspected by its remote name: no local branch called wip/remote-only exists
    assert "'origin/wip/remote-only'" in menu and "without origin/" in menu


def test_pipe_in_a_ref_name_does_not_abort_the_session(tmp_path, repo):
    """git allows `|` in a ref name. Split on `|`, `x|UNBOUND` put a variable name into
    the age arithmetic; set -u stopped the hook there, still exiting 0, and none of the
    idle branches was reported, so the session looked clean. Measured on bash 3.2.
    Found by Codex in the 3.1.2 review; it predates that release."""
    with_remote(tmp_path, repo)
    for i, name in enumerate(("old|UNBOUND", "gone|UNBOUND")):
        git(repo, "checkout", "-qb", name)
        (repo / f"p{i}.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
        git(repo, "push", "-q", "-u", "origin", name)
        git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-qD", "gone|UNBOUND")
    out = run_hook(repo)                      # run_hook asserts exit 0
    assert "old|UNBOUND" in out and "gone|UNBOUND" in out


def test_parked_branch_checked_out_in_a_worktree_is_resumed_there(tmp_path, repo):
    """git refuses `worktree add` for a branch another worktree holds, so offering it
    was an action that fails when run. The offer names that folder instead."""
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "wip/parked")
    (wt / "half.txt").write_text("x"); git(wt, "add", "-A"); old_commit(wt)
    git(wt, "push", "-q", "-u", "origin", "wip/parked")
    menu = run_hook(repo).split(MENU)[1]
    look = [l for l in menu.splitlines() if "look at" in l][0]
    assert "-wt" in look and "git worktree add" not in look


def test_parked_rows_are_bounded_across_both_loops(tmp_path, repo):
    """Server-only parked branches skipped the eight-row bound the remote-orphan list
    has, so a repo full of old bot branches could flood every session. Local and
    server-only parked branches share one counter, so the bound has to hold across
    both loops, and a mixed menu still has to say how to resume an origin/ one."""
    with_remote(tmp_path, repo)
    for n in range(10):
        git(repo, "checkout", "-qb", f"wip/p{n}")
        (repo / f"p{n}.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
        git(repo, "push", "-q", "-u", "origin", f"wip/p{n}")
        git(repo, "checkout", "-q", "main")
        if n >= 5:
            git(repo, "branch", "-qD", f"wip/p{n}")    # p5-p9 live only on the server
    out = run_hook(repo)
    findings, menu = findings_of(out), out.split(MENU)[1]
    assert findings.count("wip/p") == 8                # 5 local rows + 3 server-only
    assert findings.count("server-only") == 3
    assert "2 more parked branch(es)" in findings
    assert "without origin/" in menu


# --- the server is not what the last fetch said (3.2.1) -------------------------------
# Remote-tracking refs change only on fetch, and fetch.prune is off by default. A branch
# deleted on GitHub stayed in refs/remotes/origin and was offered /ship as "server-only"
# every session. A pushed branch whose server copy was deleted stayed under "On the
# server", even after `fetch --prune` had marked it [gone]. The server is now asked, at
# most once per session and only when a row depends on it.

SERVER_CHECK_SECS = int(re.search(r"^SERVER_CHECK_SECS=(\d+)$", HOOK.read_text(), re.M).group(1))


def pushed_idle_branch(repo, name):
    git(repo, "checkout", "-qb", name)
    (repo / f"{name.replace('/', '-')}.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "push", "-q", "-u", "origin", name)
    git(repo, "checkout", "-q", "main")


def server_only_orphan(repo, name="orphan"):
    pushed_idle_branch(repo, name)
    git(repo, "branch", "-qD", name)


def fake_ssh(tmp_path, repo, body):
    """Route origin's ssh through a script of our own. Every call appends a line to the
    returned log, so a test can prove the server was (or was not) asked."""
    log = tmp_path.parent / f"{tmp_path.name}-ssh-calls"
    script = tmp_path.parent / f"{tmp_path.name}-ssh.sh"
    script.write_text(f"#!/bin/sh\necho call >> '{log}'\n{body}\n"); script.chmod(0o755)
    git(repo, "config", "core.sshCommand", str(script))
    git(repo, "config", "ssh.variant", "ssh")       # no `-G` probe, which would count as a call
    return log


def hanging_server(tmp_path, repo):
    log = fake_ssh(tmp_path, repo, f"exec sleep {SERVER_CHECK_SECS + 5}")
    git(repo, "remote", "set-url", "origin", "ssh://example.invalid/x.git")
    return log


def calls(log):
    return log.read_text().count("call") if log.exists() else 0


def test_branch_deleted_on_the_server_is_not_reported_server_only(tmp_path, repo):
    """Observed 2026-09-14 in this repo: two bot branches already deleted on GitHub were
    offered /ship at session start, because their refs/remotes copies were never pruned."""
    bare = with_remote(tmp_path, repo)
    server_only_orphan(repo, "gone-feature")
    git(bare, "branch", "-qD", "gone-feature")               # on the server; no fetch here
    assert git(repo, "show-ref", "-q", "refs/remotes/origin/gone-feature").returncode == 0
    assert "gone-feature" not in run_hook(repo)


def test_server_only_branch_that_still_exists_is_still_reported(tmp_path, repo):
    """Checking the server must not swallow a real orphan."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    findings = findings_of(run_hook(repo))
    assert "On the server, never merged" in findings and "orphan" in findings


@pytest.mark.parametrize("pruned", [True, False], ids=["after-fetch-prune", "no-fetch"])
def test_branch_whose_server_copy_was_deleted_is_offered_a_look_not_a_push(tmp_path, repo, pruned):
    """It was listed under "On the server" both before and after `fetch --prune`. It may be
    the only copy, or a squash merge, or deleted on purpose (a leaked secret): the hook
    cannot tell, so it offers a look and never a push bundled into a backup."""
    bare = with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "local-gone")
    git(bare, "branch", "-qD", "local-gone")
    if pruned:
        git(repo, "fetch", "-q", "--prune")
    out = run_hook(repo)
    findings, menu = findings_of(out), out.split(MENU)[1]
    assert "Deleted on the server" in findings and "local-gone" in findings
    assert "never merged into" not in findings and "Only on this computer" not in findings
    assert action_label(menu, 1) == "look" and "back up" not in menu
    look = [l for l in menu.splitlines() if "'local-gone'" in l][0]
    assert "never push it back unasked" in look


def test_squash_merged_branch_deleted_on_the_server_is_silent(tmp_path, repo):
    """[gone] usually means a PR was squash-merged and GitHub deleted its branch. Once the
    default branch moves on, `diff --quiet` no longer sees the work as landed."""
    bare = with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "squashed")
    git(repo, "merge", "-q", "--squash", "squashed"); git(repo, "commit", "-qm", "squash (#1)")
    (repo / "later.txt").write_text("y"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "later")
    git(repo, "push", "-q", "origin", "main")
    git(bare, "branch", "-qD", "squashed")
    git(repo, "fetch", "-q", "--prune")
    assert git(repo, "diff", "--quiet", "origin/main", "squashed").returncode != 0
    assert "squashed" not in run_hook(repo)


def test_a_wide_squash_merged_branch_is_checked_in_pieces(tmp_path, repo):
    """The landed test passes changed paths as argv in pieces of 256; 300 paths cross the
    boundary, and every piece has to agree before the branch counts as landed."""
    bare = with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "wide")
    for n in range(300):
        (repo / f"w{n:03d}.txt").write_text(str(n))
    git(repo, "add", "-A"); old_commit(repo)
    git(repo, "push", "-q", "-u", "origin", "wide"); git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--squash", "wide"); git(repo, "commit", "-qm", "squash (#1)")
    (repo / "later.txt").write_text("y"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "later")
    git(repo, "push", "-q", "origin", "main")
    git(bare, "branch", "-qD", "wide")
    assert "wide" not in run_hook(repo)
    (repo / "w299.txt").write_text("changed on main"); git(repo, "commit", "-qam", "edit last piece")
    git(repo, "push", "-q", "origin", "main")
    assert "wide" in findings_of(run_hook(repo))


def test_squash_merge_then_the_same_file_changed_again_is_never_offered_a_push(tmp_path, repo):
    """The content test is conservative: once main changes a squashed file again it cannot
    call the branch landed. It must then fall under the look-at offer, never a push."""
    bare = with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "squashed")
    git(repo, "merge", "-q", "--squash", "squashed"); git(repo, "commit", "-qm", "squash (#1)")
    (repo / "squashed.txt").write_text("changed again"); git(repo, "commit", "-qam", "edit")
    git(repo, "push", "-q", "origin", "main")
    git(bare, "branch", "-qD", "squashed")
    menu = run_hook(repo).split(MENU)[1]
    assert "back up" not in menu and "never push it back unasked" in menu


def test_a_merge_driver_is_never_run_by_the_hook(tmp_path, repo):
    """A merge-tree landed test ran configured merge drivers: a command at session start,
    a stall past the budget, and a keep-local driver could call unmerged work landed."""
    with_remote(tmp_path, repo)
    marker = tmp_path.parent / f"{tmp_path.name}-driver-ran"
    (repo / ".gitattributes").write_text("* merge=probe\n"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "attrs")
    git(repo, "config", "merge.probe.driver", f"touch '{marker}'; exit 1")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-qb", "side")
    (repo / "f.txt").write_text("side"); git(repo, "add", "-A"); old_commit(repo, "side")
    git(repo, "push", "-q", "-u", "origin", "side"); git(repo, "checkout", "-q", "main")
    (repo / "f.txt").write_text("main"); git(repo, "commit", "-qam", "main"); git(repo, "push", "-q", "origin", "main")
    assert "side" in findings_of(run_hook(repo))
    assert not marker.exists()


def test_branch_with_work_after_its_squash_merge_is_still_reported(tmp_path, repo):
    with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "partly")
    git(repo, "merge", "-q", "--squash", "partly"); git(repo, "commit", "-qm", "squash (#1)")
    (repo / "later.txt").write_text("y"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "later")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "partly")
    (repo / "more.txt").write_text("z"); git(repo, "add", "-A"); old_commit(repo, "follow-up")
    git(repo, "push", "-q"); git(repo, "checkout", "-q", "main")
    assert "partly" in findings_of(run_hook(repo))


def test_squash_merged_worktree_is_spent_after_the_default_branch_moves_on(tmp_path, repo):
    """One landed() test for every site: a squash-merged branch was landed in the idle-branch
    list and still unfinished in the worktree list."""
    with_remote(tmp_path, repo)
    wt = add_worktree(repo, tmp_path.parent / f"{tmp_path.name}-wt", "squashed")
    (wt / "s.txt").write_text("x"); git(wt, "add", "-A"); old_commit(wt)
    git(repo, "merge", "-q", "--squash", "squashed"); git(repo, "commit", "-qm", "squash (#1)")
    (repo / "later.txt").write_text("y"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "later")
    git(repo, "push", "-q", "origin", "main")
    assert "already on main" in run_hook(repo)


def test_upstream_under_another_name_is_looked_up_by_that_name(tmp_path, repo):
    with_remote(tmp_path, repo)
    git(repo, "checkout", "-qb", "local-name")
    (repo / "r.txt").write_text("x"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "push", "-q", "-u", "origin", "local-name:server-name")
    git(repo, "checkout", "-q", "main")
    findings = findings_of(run_hook(repo))
    assert "local-name" in findings and "On the server, never merged" in findings
    assert "Deleted on the server" not in findings


def test_a_force_pushed_server_branch_is_not_called_safe(tmp_path, repo):
    """The name survived on the server but our commits did not. Checking names only said
    "On the server" about commits that now exist on this computer alone."""
    bare = with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "rewritten")
    main_sha = git(repo, "rev-parse", "main").stdout.strip()
    git(bare, "update-ref", "refs/heads/rewritten", main_sha)     # forced back; no fetch here
    findings = findings_of(run_hook(repo))
    assert "rewritten" in findings and "as of the last fetch" in findings


def test_unreachable_server_keeps_the_rows_and_says_so(tmp_path, repo):
    """Offline, the last fetch is the best evidence there is: keep the rows, but do not
    present them as the server's current state."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    git(repo, "remote", "set-url", "origin", str(tmp_path.parent / "no-such-remote.git"))
    findings = findings_of(run_hook(repo))
    assert "orphan" in findings and "as of the last fetch" in findings


def test_a_server_that_never_answers_cannot_stall_the_session(tmp_path, repo):
    """SessionStart hooks run on a 10 s budget. The hang must be reached (not skipped by an
    ssh command of ours) and cut off by the check's own bound."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    log = hanging_server(tmp_path, repo)
    start = time.monotonic()
    findings = findings_of(run_hook(repo))
    assert time.monotonic() - start < SERVER_CHECK_SECS + 3
    assert calls(log) == 1
    assert "orphan" in findings and "as of the last fetch" in findings


def test_a_transport_that_ignores_TERM_is_still_cut_off(tmp_path, repo):
    """One TERM to git left an ssh child running, and a transport that ignores TERM held the
    hook until Claude Code killed it, which prints nothing."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    fake_ssh(tmp_path, repo, f"trap '' TERM\nsleep {SERVER_CHECK_SECS + 5}")
    git(repo, "remote", "set-url", "origin", "ssh://example.invalid/x.git")
    start = time.monotonic()
    findings = findings_of(run_hook(repo))
    assert time.monotonic() - start < SERVER_CHECK_SECS + 3
    assert "orphan" in findings and "as of the last fetch" in findings


def test_a_killed_hook_leaves_no_transport_running(tmp_path, repo):
    """If Claude Code kills the hook mid-check, nothing signals the check's process group,
    and a transport of the user's own ran on with no bound. The bound lives in the group."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    pidfile = tmp_path.parent / f"{tmp_path.name}-transport-pid"
    fake_ssh(tmp_path, repo, f"echo $$ > '{pidfile}'\ntrap '' TERM\nsleep {SERVER_CHECK_SECS + 20}")
    git(repo, "remote", "set-url", "origin", "ssh://example.invalid/x.git")
    hook = subprocess.Popen(["bash", str(HOOK)], cwd=str(repo),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo),
                                 "GSTACK_BRANCH_IDLE_DAYS": "7"})
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not (pidfile.exists() and pidfile.read_text().strip()):
        time.sleep(0.05)
    assert pidfile.exists(), "the transport never started"
    hook.kill(); hook.wait()
    pid = int(pidfile.read_text())
    time.sleep(SERVER_CHECK_SECS + 3)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, signal.SIGKILL)
    assert not alive


def test_a_stacked_branch_with_a_local_upstream_is_not_called_deleted_on_the_server(tmp_path, repo):
    """branch.<name>.remote = . makes another local branch the upstream. Tips were looked up
    under refs/remotes only, so that upstream looked gone and the branch was filed under
    "Deleted on the server", where no server was involved."""
    with_remote(tmp_path, repo)
    pushed_idle_branch(repo, "base-feat")
    git(repo, "checkout", "-qb", "stacked", "base-feat")
    (repo / "b.txt").write_text("b"); git(repo, "add", "-A"); old_commit(repo)
    git(repo, "branch", "-q", "--set-upstream-to=base-feat", "stacked")
    git(repo, "checkout", "-q", "main")
    assert "Deleted on the server" not in findings_of(run_hook(repo))


def test_nothing_to_report_means_no_network_call(tmp_path, repo):
    """The server is asked only when a row depends on it, or every session pays."""
    with_remote(tmp_path, repo)
    log = hanging_server(tmp_path, repo)
    assert run_hook(repo) == ""
    assert calls(log) == 0


def test_the_server_is_asked_once_for_many_rows(tmp_path, repo):
    """Asked per row, an unreachable server costs the bound once per row, and four rows are
    past the budget."""
    bare = with_remote(tmp_path, repo)
    for name in ("orphan-a", "orphan-b", "orphan-c"):
        server_only_orphan(repo, name)
    log = fake_ssh(tmp_path, repo, 'for last; do :; done\neval "set -- $last"\nexec git upload-pack "$2"')
    git(repo, "remote", "set-url", "origin", f"ssh://localhost{bare}")
    findings = findings_of(run_hook(repo))
    assert "orphan-a" in findings and "as of the last fetch" not in findings
    assert calls(log) == 1


def test_an_ssh_wrapper_set_through_GIT_SSH_is_used(tmp_path, repo):
    """git prefers GIT_SSH_COMMAND over GIT_SSH, so a BatchMode command of ours silently
    replaced the user's wrapper, and the check failed on a reachable remote."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    log = tmp_path.parent / f"{tmp_path.name}-git-ssh-calls"
    wrapper = tmp_path.parent / f"{tmp_path.name}-git-ssh.sh"
    wrapper.write_text(f"#!/bin/sh\necho call >> '{log}'\nexit 1\n"); wrapper.chmod(0o755)
    git(repo, "config", "ssh.variant", "ssh")
    git(repo, "remote", "set-url", "origin", "ssh://example.invalid/x.git")
    run_hook(repo, GIT_SSH=str(wrapper))
    assert calls(log) == 1


def test_opting_out_makes_no_network_call(tmp_path, repo):
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    log = hanging_server(tmp_path, repo)
    findings = findings_of(run_hook(repo, GSTACK_BRANCH_SERVER_CHECK="0"))
    assert calls(log) == 0
    assert "orphan" in findings and "as of the last fetch" in findings


def test_a_custom_fetch_mapping_does_not_drop_server_only_rows(tmp_path, repo):
    """With +refs/heads/*:refs/remotes/origin/team/*, origin/team/feature is the server's
    `feature`. Asking the server for team/feature found nothing and dropped the row."""
    with_remote(tmp_path, repo)
    git(repo, "config", "--replace-all", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/team/*")
    server_only_orphan(repo, "feature")
    git(repo, "fetch", "-q", "origin")
    assert "team/feature" in findings_of(run_hook(repo))


def test_a_tag_named_like_a_remote_branch_does_not_hide_the_row(tmp_path, repo):
    """A tag origin/orphan made %(refname:short) print remotes/origin/orphan, which matched
    no server branch, and the row was dropped."""
    with_remote(tmp_path, repo)
    server_only_orphan(repo)
    git(repo, "tag", "origin/orphan", "main")
    findings = findings_of(run_hook(repo))
    assert "orphan" in findings and "server-only" in findings


def test_unreachable_server_marks_server_only_parked_rows(tmp_path, repo):
    with_remote(tmp_path, repo)
    server_only_orphan(repo, "wip/remote-only")
    git(repo, "remote", "set-url", "origin", str(tmp_path.parent / "no-such-remote.git"))
    findings = findings_of(run_hook(repo))
    assert "wip/remote-only" in findings and "the server did not answer" in findings


def test_server_only_wip_branch_deleted_on_the_server_is_dropped(tmp_path, repo):
    bare = with_remote(tmp_path, repo)
    server_only_orphan(repo, "wip/gone")
    git(bare, "branch", "-qD", "wip/gone")
    assert "wip/gone" not in run_hook(repo)


def test_deleted_on_the_server_rows_are_bounded(tmp_path, repo):
    """Parked and server-only rows stop at eight; these must too, or a repo full of
    auto-deleted PR branches floods every session."""
    bare = with_remote(tmp_path, repo)
    for n in range(10):
        pushed_idle_branch(repo, f"g{n}")
        git(bare, "branch", "-qD", f"g{n}")
    out = run_hook(repo)
    findings, menu = findings_of(out), out.split(MENU)[1]
    assert "2 more deleted branch(es)" in findings
    assert "and 7 more" in menu


def test_a_server_with_thousands_of_branches_stays_inside_the_budget(tmp_path, repo):
    """Built up in a shell string, the server's branch list was quadratic: 20 000 names took
    145 s (measured), far past the 10 s a SessionStart hook gets, and a hook killed for
    time reports nothing at all. 6 000 would have taken about 13 s."""
    bare = with_remote(tmp_path, repo)
    server_only_orphan(repo)
    head = git(repo, "rev-parse", "main").stdout.strip()
    refs = "".join(f"create refs/heads/bulk/branch-with-a-longish-name-{n:05d} {head}\n" for n in range(6000))
    subprocess.run(["git", "-C", str(bare), "update-ref", "--stdin"], input=refs, text=True, check=True)
    start = time.monotonic()
    findings = findings_of(run_hook(repo))
    assert time.monotonic() - start < SERVER_CHECK_SECS + 3
    assert "orphan" in findings and "as of the last fetch" not in findings
