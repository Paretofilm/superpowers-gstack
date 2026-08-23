## Git hygiene & commit cadence <!-- gstack-git-hygiene-v9 -->

Commit at meaningful milestones — not at every file save, not only at session end.

### When to commit

- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- Before switching to unrelated work (don't mix concerns in one commit)
- After a reversible decision (so `git revert` works cleanly later)
- Before long-running or risky operations (rollback point)

Do NOT commit mid-task, just to "save progress" (use `git stash` for holds of minutes-to-hours; a WIP branch for anything longer), or with unrelated changes batched together — split them.

**Then push. Committing is not backing up.** A commit lives on one disk until it is
pushed; a dead laptop takes it with it. Push after committing — `git push -u origin
<branch>` the first time, `git push` after — and say you did. This is separate from
landing: **pushing is backup, landing is completion, and you do both.** A branch that
was never pushed is one hardware failure from being gone, no matter how carefully it
was committed. If the user cannot push (no remote configured), say so plainly rather
than leaving the work looking safe.

### Commit message format

Follow the convention established in the repo (`git log --oneline -10` first). If the log is empty or has no consistent style, use `<type>(<scope>): <one-line summary>` plus a body saying what changed and why (not how); types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. If the log is inconsistent, also note that in your final summary so the user can decide whether to standardize.

### Hygiene rules (NEVER violate)

- ❌ `git commit --no-verify` — if a hook fails, fix the root cause
- ❌ `git commit --amend` on already-pushed commits — rewrites shared history
- ❌ `git push --force` to `main` or shared branches
- ❌ `git reset --hard` without stashing or committing first — silent work loss
- ❌ `git add -A` / `git add .` when secrets, large binaries, or build artifacts may be present — stage specific paths

### Landing the branch

A branch is done when it is **merged or deliberately discarded** — not when the code
works. Work sitting on an unlanded branch is invisible: it doesn't ship, doesn't reach
review, and rots against the default branch while everything else moves.

- **Never end a session silently on a branch with unmerged commits.** Say where the
  work stands — landed, ready to land, or still open — even when the answer is "still
  open". The failure mode is not a wrong decision, it's no decision being stated.
- **A fix nobody has watched run is not verified.** Tests answer *did I break
  something else*; they cannot answer *is the thing I fixed actually fixed*. When the
  project has a runnable app, build the branch and launch **that build** before
  landing — `/superpowers-gstack:verify-and-land` does exactly that and then offers
  the landing. On macOS this matters more than it sounds: opening the app by name
  starts the copy in `/Applications`, which is the last release, not this branch. "I
  checked and it is still broken" is very often a stale bundle rather than a failed
  fix, and the fix gets rewritten for no reason.
- **Offer landing choices in the user's language, with one recommendation.**
  "Merge", "PR" and "default branch" are git policy, not choices a non-git user can
  weigh. Phrase the outcomes: *"make this the live version"* (merge), *"send it for
  review first"* (PR), *"keep it safely stored but not live"* (leave the pushed
  branch) — and recommend one based on how the repo actually works (solo repo with
  no CI review → merge; anything with review or deploys on main → PR).
- **Landing is a skill, not a hand-rolled merge:** `/ship` (tests → review → PR) or
  `/superpowers:finishing-a-development-branch` (merge, PR, or discard). Pick one.
- **Deliberate abandonment counts as done.** Say so and delete the branch — but
  **check whether it was ever pushed first.** If its commits exist on a remote,
  deleting the local branch is tidy-up and the work stays recoverable. If it was
  never pushed, deleting it makes those commits unreachable and effectively
  unrecoverable. `git branch -d` refuses to delete unmerged work; `git branch -D`
  forces it and loses the commits — never reach for `-D` to make a `-d` refusal go
  away, that refusal is the guard doing its job. When in doubt, push first, then
  delete: a pushed-then-deleted branch can be restored, a never-pushed one cannot.
- **Closing a PR does not delete its branch.** Delete it after the PR merges or
  closes, or it outlives the PR and reads as open work forever.

### Landing work that lives in a worktree

Worktrees are second checkouts of the same repository — `superpowers:using-git-worktrees`
makes them, and the `Agent` tool's `isolation: "worktree"` makes one per agent and
**leaves it on disk precisely when it produced changes**. So the isolated workspace
that did the work is also the one nobody opens again. Five facts decide whether that
work reaches the default branch:

- **A branch lives in at most one worktree.** `git checkout <branch>` anywhere else
  fails outright: *"already used by worktree at …"*. This is not a warning to work
  around — it is git refusing to give one branch two states.
- **`/ship` therefore runs *inside* that worktree**, because it operates on the
  current branch. Started from the main checkout it stops on the error above, which
  is a dead end for a user who cannot read it. The hook's report names the folder;
  `git worktree list` gives it otherwise.
- **Merging does not need a checkout.** From the default branch,
  `git merge <branch>` lands the work with the branch still checked out elsewhere.
  Landing is available from both sides; only *switching* is constrained.
- **Remove the worktree before deleting its branch** — `git worktree remove <path>`,
  then `git branch -d <branch>`. In the other order git refuses, and a tidy-up that
  fails halfway leaves exactly the state it was meant to clear.
- **Commits on a detached worktree HEAD belong to no branch.** Nothing that walks
  branches can see them, and removing the folder makes them unreachable. Give them a
  branch and push it before removing anything.

A worktree is finished when its work is merged **and** the folder is gone. Leaving
the folder is not harmless tidiness debt: its branch cannot be deleted while it
stands, so it reports as unlanded work forever.

### When the session-start hook reports unlanded work

A SessionStart hook may open the session with a report of work that exists in only
one place, or finished work that never shipped, followed by a short **agent menu**.
**That whole report is addressed to you, not to the user.** Many users cannot read
`git status` output, have never typed `git stash`, and do not know what "origin" is
— for them you are the only interface to git, so a warning you merely echo is a
warning nobody acted on, and a command you paste for them to run is a task you
handed back.

When it fires:

1. **Look before you speak.** Run the inspection the report suggests and find out
   what the work actually is — which files, which feature. "3 commits on
   `login-skjerm`" means nothing to the user; "the login screen changes from
   Tuesday" does. Do this first, so every choice you then offer is named in their
   language.
2. **Offer, don't instruct.** Turn the menu into `AskUserQuestion` options, in the
   order given, phrased as *what you will do*, not as what they should type. Keep
   that order: it is sorted most-preserving first, and option 1 never destroys
   anything — so whichever option someone picks without reading, the top one is
   safe. Then **carry out the choice yourself** — commit with a real message, push,
   open the diff, invoke `/ship`. A menu that ends in advice has not moved the work.
   - `AskUserQuestion` takes **at most four options**, and the menu can list more.
     Offer the top three plus "show me the rest", never a silently truncated list —
     dropping the tail is how the same warning arrives again next session.
   - Menu items name refs and paths **already single-quoted**. Keep the quotes when
     you build a command: `git push -u origin 'wip$(whoami)'` is a branch name, the
     same text unquoted is a command substitution. Branch names are repo-controlled
     input, and a cloned repo is somebody else's input.
   - **If the session is non-interactive** (`--print`, piped, CI, a subagent — no
     one can click), do not stall on `AskUserQuestion`. Preserve **without
     publishing**: commit loose work to a local recovery branch
     (`git switch -c recovery/<date>`), and do NOT push it — uncommitted files can
     hold secrets, half-edits, or generated junk that no one has looked at, and a
     push is a publish. Pushing branches that were already committed by a person is
     fine. Report what you did, take nothing below option 1, and name every item
     left unresolved so the decision is still visibly waiting.
3. **Lead with what is at stake, in their words.** Distinguish *this exists only on
   your machine and a disk failure ends it* from *this is safely stored, just never
   merged*. They are different problems and only the first is urgent.
4. **Preserve before you offer to remove.** Push, or commit-then-push, first. Only
   once the work is recoverable is it reasonable to ask whether to keep it. Never
   open with discard, drop, or delete — those are answers the user cannot evaluate
   until they know what they would be losing.
5. **Do not act destructively without an explicit yes** to a question that named the
   actual work. "Shall I clean up?" is not that question.
6. **A click authorizes what it names, nothing more.** "Back up" ends at the push;
   it does not continue into merging, opening PRs, or deleting. Each of those is its
   own question. And when a preservation step succeeds, **offer the next decision
   for that same work immediately** — backed-up-but-unlanded work re-reports next
   session, and a warning that reappears after the user did the right thing teaches
   them that responding changes nothing.
7. **Say what you left unresolved.** If the user declines, or something needs a
   decision you cannot make for them, name it before moving on — otherwise the next
   session starts from the same report and nothing has changed.

Nothing here changes what the hook detects; it changes who does the work. Detection
that ends in a printed command is a to-do list handed to the person least able to
act on it — the point of the menu is that the answer is one click, not one lesson.

### Cadence rule

More than 5 commits in a row without testing the cumulative state → STOP and verify (build, run tests) before continuing. This is a legitimate category-5 stop per the Autonomy section — cumulative breakage is harder to diagnose than per-commit breakage. A session where NO commit was tested is committing "progress without verification": run the project's test suite, or document explicitly why testing is deferred.
