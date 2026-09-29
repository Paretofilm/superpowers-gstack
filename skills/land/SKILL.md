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

```bash
LAND="<this skill's base directory>/../../scripts/land-worktree.py"
python3 "$LAND" --worktree "<the feature worktree, default: the current directory>"
```

`--preflight-only` runs the preflight checks and updates local `main` (fast-forward from origin), then stops before the merge and push. It is not a dry run: local `main` moves. Use it when the user wants to know whether the landing would go through. The last line of stdout is a JSON verdict; stderr carries the reason and the exact commands to run.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | Landed | Read `remaining`: leave the worktree first (`ExitWorktree`, action `keep`) if the session stands in it, then `wt -C <primary> remove <branch>`. Run the `watch` command in the background; a red CI run means fixing `main` next. Warnings are not failures. |
| 2 | `Landing mode` is `pr`, or the line is missing or invalid | `pr`: use `/ship`. Missing: ask the user once (solo or pull request?) and write the answer on its own line under a heading the project owns, outside the `/adapt`-managed sections. Never assume `solo`. |
| 3 | Hooks not approved | Tell the user to run `wt config approvals add` (in this session: `! wt config approvals add`). Never `--yes`. |
| 4 | Local `main` has commits that are not on origin | The listed commits would ride along unchecked. Ask the user what they are. |
| 5 | Uncommitted files in the worktree holding `main` overlap this landing | Name the files. The user commits them or moves them to their own branch. Never stash. |
| 6 | A pre-merge check failed | Fix the failure and land again. Never `--no-hooks`. |
| 7 | `origin/main` moved, or the push was rejected | Nothing was pushed. Local `main` already holds the work and the worktree stands. Show the user the printed commands and let them choose; do not reset. |
| 8 | `wt` is not installed | Fall back to `git worktree` and `/superpowers:finishing-a-development-branch`. |
| 9 | No `pre-merge` hook in `.config/wt.toml` | Propose one that runs the same commands as CI. The user approves it. |
| 10 | Rebase conflict | A rebase is open in the worktree. Resolve it, or `git rebase --abort`, then land again. |
| 11 | `git fetch` failed | Check the network and the remote, then land again. |
| 12 | Another landing holds the lock | Wait, or look at who holds it. |
| 13 | The worktree has uncommitted work | Commit it, or move it to `wip/<topic>`. |
| 64 | Not a feature worktree | Run from the feature worktree, or pass `--worktree`. |
| 70 | Unrecognised `wt merge` failure | Show the user the printed tail. Do not guess. |

## Never

`--no-hooks`, `--yes`, `git reset`, `git stash`, or a second attempt without the user hearing why the first stopped. The script is deliberately small so that every stop leaves the state visible.
