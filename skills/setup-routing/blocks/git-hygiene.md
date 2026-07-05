## Git hygiene & commit cadence <!-- gstack-git-hygiene-v3 -->

Commit at meaningful milestones — not at every file save, not only at session end.

### When to commit

- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- Before switching to unrelated work (don't mix concerns in one commit)
- After a reversible decision (so `git revert` works cleanly later)
- Before long-running or risky operations (rollback point)

Do NOT commit mid-task, just to "save progress" (use `git stash` for holds of minutes-to-hours; a WIP branch for anything longer), or with unrelated changes batched together — split them.

### Commit message format

Follow the convention established in the repo (`git log --oneline -10` first). If the log is empty or has no consistent style, use `<type>(<scope>): <one-line summary>` plus a body saying what changed and why (not how); types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. If the log is inconsistent, also note that in your final summary so the user can decide whether to standardize.

### Hygiene rules (NEVER violate)

- ❌ `git commit --no-verify` — if a hook fails, fix the root cause
- ❌ `git commit --amend` on already-pushed commits — rewrites shared history
- ❌ `git push --force` to `main` or shared branches
- ❌ `git reset --hard` without stashing or committing first — silent work loss
- ❌ `git add -A` / `git add .` when secrets, large binaries, or build artifacts may be present — stage specific paths

### Cadence rule

More than 5 commits in a row without testing the cumulative state → STOP and verify (build, run tests) before continuing. This is a legitimate category-5 stop per the Autonomy section — cumulative breakage is harder to diagnose than per-commit breakage. A session where NO commit was tested is committing "progress without verification": run the project's test suite, or document explicitly why testing is deferred.
