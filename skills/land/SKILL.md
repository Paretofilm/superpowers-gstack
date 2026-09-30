---
name: land
description: |
  Land a finished worktree on main in one command for a solo project: local pre-merge
  checks, fast-forward, push, no pull request. Interprets every exit code.
---

# Land

The solo developer's landing: the branch you finished goes onto `main` after the project's own local checks, and is pushed. There is no pull request, so the pre-merge hook is the gate. This skill runs `scripts/land-worktree.py` and turns its exit code into the next action; it never repairs anything itself.

Invoke with: `/superpowers-gstack:land`

## Before you run it

Ship-worthy changes have already been through `/review` and `/superpowers-gstack:pitfall-verification`. This skill is the landing, not the review.

## Run

Locate the script relative to this skill (it usually runs in the user's project, where `scripts/` does not exist):

The script needs Python 3.11 or newer (`tomllib`, to read the gate). macOS's `/usr/bin/python3` is 3.9, so pick an interpreter first:

```bash
LAND="<this skill's base directory>/../../scripts/land-worktree.py"
PY=""
for p in python3 python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then PY=$p; break; fi
done
if [ -z "$PY" ]; then
  echo "land: no Python 3.11+ found (macOS /usr/bin/python3 is 3.9) — install one, e.g. brew install python" >&2
  false   # stop here: non-zero, and the script is not run
else
  "$PY" "$LAND" --worktree "<the feature worktree, default: the current directory>"
fi
```

Run with an older Python anyway, the script stops with code 70 and says "Python >= 3.11 required".

`--preflight-only` runs the preflight checks and updates local `main` (fast-forward from origin), then stops before the merge and push. It is not a dry run: local `main` moves. Use it when the user wants to know whether the landing would go through. The last line of stdout is a JSON verdict; stderr carries the reason and the exact commands to run.

The script forces the hooks on (`--config-set merge.verify=true`), and runs `wt` without any `WORKTRUNK_*` environment variable, so neither a worktrunk config with `merge.verify = false` nor `WORKTRUNK_PROJECT_CONFIG_PATH` can switch or swap the gate, and it pushes exactly the commit that passed them (`<sha>:refs/heads/main`, the branch tip captured before the checks start), never a re-read of `main` or the branch.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | Landed | Read `remaining`: leave the worktree first (`ExitWorktree`, action `keep`) if the session stands in it, then `wt -C <primary> remove <branch>`. Run the `watch` command in the background; a red CI run means fixing `main` next. Warnings are not failures. |
| 2 | `Landing mode` is `pr`, or the line is missing, invalid, only inside a code block, or both `solo` and `pr` appear | `pr`: use `/ship`. Missing: ask the user once (solo or pull request?) and write the answer on its own line under a heading the project owns, outside the `/adapt`-managed sections. Both values: ask which one holds and remove the other. Never assume `solo`. |
| 3 | Hooks not approved, or their approval state could not be read | First show the user what they would approve: `git diff <main>...HEAD -- .config/wt.toml` (a branch can rewrite its own gate). Then tell them to run `wt config approvals add` (in this session: `! wt config approvals add`). The script runs `wt` with every `WORKTRUNK_*` variable removed (including `WORKTRUNK_CONFIG_PATH`), so the approval must land in the default user config. If the user's shell sets any `WORKTRUNK_*` variable, approve with them unset, or code 3 comes back every time: `(for v in $(env \| grep -o '^WORKTRUNK_[A-Za-z0-9_]*'); do unset "$v"; done; wt config approvals add)`. Never `--yes`. |
| 4 | Local `main` has commits that are not on origin | The listed commits would ride along unchecked. Ask the user what they are. |
| 5 | Uncommitted files in the worktree holding `main` overlap this landing | Name the files. The user commits them or moves them to their own branch. Never stash. |
| 6 | A pre-merge check failed | The output tail is printed. Fix the failure and land again. Never `--no-hooks`. |
| 7 | `origin/main` moved during the checks, or the push failed and is not confirmed | Local `main` already holds the work and the worktree stands. "Nothing was pushed" is said only when origin moved before the push; a failed push is "not confirmed pushed". Show the user the printed commands and let them choose; do not reset. After `pull --rebase` the combined result is UNCHECKED: run the printed `wt hook pre-merge` in the worktree holding `main`, and push only when it passes. |
| 8 | `wt` is not installed | Fall back to `git worktree` and `/superpowers:finishing-a-development-branch`. |
| 9 | No top-level `pre-merge` hook that runs a command in `.config/wt.toml` (an empty table, an alias or unparseable TOML counts as none) | Propose one that runs the same commands as CI. The user approves it. |
| 10 | Rebase needed, or a rebase is open | "Rebase needed": the branch does not contain the current `main`; nothing moved. The gate must run on the rebased tree, so the script never rebases inside `wt merge` (`--no-rebase`). Run the printed `wt -C <worktree> step rebase <main>` (or `git rebase <main>`), then land again. "A rebase is open" (usually after that rebase hit a conflict): resolve it and `git rebase --continue`, or `git rebase --abort`, then land again. |
| 11 | `git fetch` failed | Check the network and the remote, then land again. |
| 12 | Another landing holds the lock: a kernel lock on `gstack-land.lock` in the git dir, freed only when every process holding it has exited. After a killed landing that includes the orphaned `wt merge` and every background child it started (post-merge and post-start hooks inherit the lock) | Wait, or see who holds it with the printed `lsof <lock file>`. Every PID it lists is a holder. Never delete the file to get past it. |
| 13 | The worktree has uncommitted work | Commit it, or move it to `wip/<topic>`. |
| 64 | Not a feature worktree, bad arguments, or nothing to land (no commits beyond `main`) | Run from the feature worktree, or pass `--worktree`. Nothing to land: say so; there is nothing to do. |
| 70 | Unrecognised `wt merge` failure; the branch got a new commit while the checks ran, or `main` after the merge is not exactly the tip that passed them (nothing pushed; the unchecked commits are named); an interpreter older than Python 3.11; or the landing was interrupted (Ctrl-C, SIGTERM) and the push is not confirmed | Show the user the printed state. After a `wt merge` failure or an interrupt, the state is measured: whether local `main` moved, whether a rebase is open and, when interrupted after `main` moved, whether origin has it ("not confirmed pushed", plus, only when local `main` is exactly the checked sha, the `push` command of that sha that finishes the landing; a plain re-run would stop at 4). An interrupt after a confirmed push is not 70: it exits 0 as landed, with a warning. Do not guess. |

## Never

`--no-hooks`, `--yes`, `git reset`, `git stash`, or a second attempt without the user hearing why the first stopped. The script is deliberately small so that every stop leaves the state visible.
