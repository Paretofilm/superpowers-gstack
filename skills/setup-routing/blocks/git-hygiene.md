## Git hygiene & commit cadence <!-- gstack-git-hygiene-v5 -->

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

### When the session-start hook reports unlanded work

A SessionStart hook may open the session with a report of work that exists in only
one place, or finished work that never shipped. **That report is addressed to you,
not to the user.** Many users cannot read `git status` output, have never typed `git
stash`, and do not know what "origin" is — for them you are the only interface to
git, so a warning you merely echo is a warning nobody acted on.

When it fires:

1. **Look before you speak.** Run the inspection the report suggests and find out
   what the work actually is — which files, which feature. "5 commits on
   `min-feature`" means nothing to the user; "the login screen changes from Tuesday"
   does.
2. **Lead with what is at stake, in their words.** Distinguish *this exists only on
   your machine and a disk failure ends it* from *this is safely stored, just never
   merged*. They are different problems and only the first is urgent.
3. **Preserve before you offer to remove.** Push, or commit-then-push, first. Only
   once the work is recoverable is it reasonable to ask whether to keep it. Never
   open with discard, drop, or delete — those are answers the user cannot evaluate
   until they know what they would be losing.
4. **Do not act destructively without an explicit yes** to a question that named the
   actual work. "Shall I clean up?" is not that question.
5. **Say what you left unresolved.** If the user declines, or something needs a
   decision you cannot make for them, name it before moving on — otherwise the next
   session starts from the same report and nothing has changed.

### Cadence rule

More than 5 commits in a row without testing the cumulative state → STOP and verify (build, run tests) before continuing. This is a legitimate category-5 stop per the Autonomy section — cumulative breakage is harder to diagnose than per-commit breakage. A session where NO commit was tested is committing "progress without verification": run the project's test suite, or document explicitly why testing is deferred.
