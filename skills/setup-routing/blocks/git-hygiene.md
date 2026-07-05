## Git hygiene & commit cadence <!-- gstack-git-hygiene-v2 -->

Commit at meaningful milestones, not at every file save and not only at session end. The goal is a readable git history that lets future-you (or another agent) understand what shipped and why.

### When to commit

Commit when:
- A logical unit of work is done and tested (one feature, one bug fix, one refactor pass)
- About to switch to unrelated work (don't mix concerns in one commit)
- A reversible decision was made (so you can `git revert` cleanly later)
- Before invoking long-running or risky operations (so you have a rollback point)

Do NOT commit:
- Mid-task — wait until the change is coherent
- Just to "save progress" — that's what `git stash` is for (short-lived holds only, minutes to hours; for longer holds create a WIP branch instead so the work survives `git stash clear` and is visible in `git branch`)
- Unrelated changes batched together — split them into separate commits

### Commit message format

Use the convention established in the repo (check `git log --oneline -10` first). Three cases:

- **Repo has a consistent convention** (every recent commit follows the same prefix style — `feat:` / `fix:` / `[TICKET-123]` / plain prose / etc.) → follow it. Do not introduce a different style.
- **Repo log is empty** (first commit, or freshly init'd) → use the default below.
- **Repo log is inconsistent** (mixed styles, no clear winner) → use the default below AND note in your final summary that the project has no clear commit convention so the user can decide whether to standardize.

Default format (use only when no consistent convention is established):

```
<type>(<scope>): <one-line summary>

<body — what changed and why, not how>

<co-authored-by trailer if relevant>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Scope = subsystem/module name.

### Hygiene rules (NEVER violate)

- ❌ `git commit --no-verify` — pre-commit hooks exist for a reason; if a hook fails, fix the root cause
- ❌ `git commit --amend` on commits already pushed — rewrites shared history
- ❌ `git push --force` to `main` or shared branches — destroys others' work
- ❌ `git reset --hard` without first stashing or committing — silent work loss
- ❌ `git add -A` or `git add .` when secrets / large binaries / build artifacts may be present — stage specific paths instead

### Cadence rule

If >5 distinct commits in a row without testing the cumulative state, STOP and verify (build, run tests) before continuing. This STOP is a category-5 ("truly blocked — verification gap") per the Autonomy section above; it overrides the autonomous-continuation default exactly the same way an unresolvable error would. Commits accumulate quickly; cumulative breakage is harder to diagnose than per-commit breakage.

If multiple commits land in a single session without ANY commit being tested, the session is committing "progress without verification" — break that cycle by running the project's test suite, or document explicitly why testing is deferred.
