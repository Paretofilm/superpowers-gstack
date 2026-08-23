"""Guard scripts/check-branch-hygiene.sh — the unlanded-work detector.

Exists because a plugin that ships /ship and finishing-a-development-branch still
had nothing that NOTICED a branch was never landed. Signal discipline is the whole
design: silent on a clean repo and on work in progress, loud only on work that has
actually been left behind.
"""

import subprocess
import pathlib
import pytest

HOOK = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "check-branch-hygiene.sh"


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, **kw)


def run_hook(repo, idle_days="7"):
    r = subprocess.run(["bash", str(HOOK)], cwd=str(repo), capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo),
                            "GSTACK_BRANCH_IDLE_DAYS": idle_days})
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
    """git-hygiene tells users a stash is for holds of minutes-to-hours — so a fresh
    one is the tool being used correctly, not debt."""
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
