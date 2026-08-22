#!/usr/bin/env bash
# SessionStart hook: surface work that is at risk of being stranded in a branch.
#
# The failure this exists for: a feature gets built on a branch, the session ends,
# and nothing ever tells anyone the branch was never landed. Weeks later it is
# forgotten work. Superpowers and gstack both ship skills that *finish* a branch
# (/ship, /superpowers:finishing-a-development-branch) — what was missing is the
# thing that NOTICES. This is that.
#
# Deliberately NOT exempt for the superpowers-gstack repo itself. The version-check
# hook exempts it because that repo's CLAUDE.md is the source of the routing and has
# no generated marker — a correct exemption for that check. Branch hygiene is
# universal, and the plugin repo strands branches like any other (six were found
# there on 2026-08-18).
#
# Signal discipline: silent when there is nothing to report. A branch you committed
# to today is work in progress, not a problem — only IDLE unmerged branches are
# surfaced, so mid-feature sessions are never nagged.
set -uo pipefail

command -v git >/dev/null 2>&1 || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Days a branch must sit untouched before it counts as at-risk. 0 disables the hook.
IDLE_DAYS="${GSTACK_BRANCH_IDLE_DAYS:-7}"
# Validate before any arithmetic. A SessionStart hook must never fail the session,
# and under `set -u` a failed $(( )) leaves the next variable unbound and aborts —
# a non-integer override would have crashed the hook rather than being ignored.
case "$IDLE_DAYS" in
  ''|*[!0-9]*) IDLE_DAYS=7 ;;
esac
[ "$IDLE_DAYS" -eq 0 ] && exit 0

# Default branch: origin/HEAD, else main, else master. No network call.
default_ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
if [ -z "$default_ref" ]; then
  for c in main master; do git show-ref --verify -q "refs/heads/$c" && { default_ref="$c"; break; }; done
fi
[ -z "$default_ref" ] && exit 0

# Compare against the remote tip when we have it — a local default branch that is
# behind origin would otherwise report branches that are in fact already landed.
base="$default_ref"
git show-ref --verify -q "refs/remotes/origin/$default_ref" && base="origin/$default_ref"

current=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
cutoff=$(( $(date +%s) - IDLE_DAYS * 86400 ))

stale=""; stale_n=0
while IFS='|' read -r ref ts; do
  [ -z "$ref" ] && continue
  [ "$ref" = "$default_ref" ] && continue
  [ "$ref" = "$current" ] && continue          # you are working here right now
  [ "$ts" -ge "$cutoff" ] 2>/dev/null && continue
  git merge-base --is-ancestor "$ref" "$base" 2>/dev/null && continue   # already landed
  ahead=$(git rev-list --count "$base..$ref" 2>/dev/null || echo "?")
  age=$(( ( $(date +%s) - ts ) / 86400 ))
  stale="${stale}      ${ref}  —  ${ahead} commit(s), idle ${age}d\n"
  stale_n=$((stale_n + 1))
done < <(git for-each-ref --format='%(refname:short)|%(committerdate:unix)' refs/heads 2>/dev/null)

# Uncommitted changes AT SESSION START are leftovers, not work in progress —
# whatever this was, the last session ended without committing it. This is the
# "ikke committet" half of the failure and the cheapest thing to detect.
dirty_n=$(git status --porcelain 2>/dev/null | grep -c . || true)

# ...and the same check for every OTHER worktree. `git status` only ever reports the
# tree you are standing in, so work left in a sibling worktree was invisible — while
# refs/heads is shared, so its BRANCH was already being checked. Half-covered is the
# worst state: the branch looked fine and the uncommitted work went unmentioned.
#
# This matters more than it looks: the Agent tool's `isolation: "worktree"` mode
# auto-removes a temporary worktree only if it is UNCHANGED. One that produced
# changes is left on disk by design — precisely the stranded work nobody revisits.
#
# Bounded to WORKTREE_SCAN_MAX so a repo with many worktrees cannot make a
# SessionStart hook slow; each entry costs one `git status`.
WORKTREE_SCAN_MAX=12
here=$(git rev-parse --show-toplevel 2>/dev/null)
other_wt=""; other_wt_n=0; scanned=0
while IFS= read -r line; do
  case "$line" in
    "worktree "*)  wt_path="${line#worktree }"; wt_branch=""; wt_skip="" ;;
    "branch "*)    wt_branch="${line#branch refs/heads/}" ;;
    "bare"|"prunable"*|"detached")
                   [ "$line" = "detached" ] || wt_skip=1 ;;
    "")
      [ -z "${wt_path:-}" ] && continue
      [ -n "${wt_skip:-}" ] && { wt_path=""; continue; }
      [ "$wt_path" = "$here" ] && { wt_path=""; continue; }   # counted by dirty_n above
      [ ! -d "$wt_path" ] && { wt_path=""; continue; }
      if [ "$scanned" -lt "$WORKTREE_SCAN_MAX" ]; then
        scanned=$((scanned + 1))
        n=$(git -C "$wt_path" status --porcelain 2>/dev/null | grep -c . || true)
        if [ "${n:-0}" -gt 0 ]; then
          other_wt="${other_wt}      ${wt_path}  (${wt_branch:-detached})  —  ${n} change(s)\n"
          other_wt_n=$((other_wt_n + 1))
        fi
      fi
      wt_path=""
      ;;
  esac
done < <(git worktree list --porcelain 2>/dev/null; echo)

# Remote branches with no local counterpart, unmerged — the true orphans. Uses
# already-fetched refs only, so no network call. This is the shape that stranded
# six branches in this very repo: a bot opened them, the PRs were closed, and the
# branches outlived both.
remote_orphans=""; remote_n=0
while IFS='|' read -r ref ts; do
  [ -z "$ref" ] && continue
  short="${ref#origin/}"
  [ "$short" = "$default_ref" ] || [ "$short" = "HEAD" ] && continue
  git show-ref --verify -q "refs/heads/$short" && continue      # has a local twin, counted above
  [ "$ts" -ge "$cutoff" ] 2>/dev/null && continue
  git merge-base --is-ancestor "$ref" "$base" 2>/dev/null && continue
  age=$(( ( $(date +%s) - ts ) / 86400 ))
  [ "$remote_n" -lt 8 ] && remote_orphans="${remote_orphans}      ${short}  —  idle ${age}d\n"
  remote_n=$((remote_n + 1))
done < <(git for-each-ref --format='%(refname:short)|%(committerdate:unix)' refs/remotes/origin 2>/dev/null)

# Commits that exist only on this machine. Found as a blind spot on 2026-08-22:
# a branch fully merged locally but never pushed reported nothing, because every
# other check compares against origin/<default> and simply found nothing unmerged.
# At session start this means the previous session ended without pushing — the
# same class as a dirty tree, and the one where a dead laptop costs you the work.
unpushed=""; unpushed_n=0
# Only meaningful when a remote exists — a local-only repo cannot push, and saying
# so every session would be pure noise. And only branches that HAVE an upstream and
# sit ahead of it: a branch that was never pushed at all is already covered by the
# stale-unmerged check above, so counting it here would double-report the same work.
# What this adds is the case every other check misses — commits merged locally and
# never pushed, which look landed from every branch-comparison angle.
if git remote 2>/dev/null | grep -q .; then
  while IFS='|' read -r ref up; do
    [ -z "$ref" ] && continue
    if [ -z "$up" ]; then
      # Never pushed anywhere. 2.40.0 excluded this as "already covered by the
      # stale-unmerged check" — but that check skips the branch you are standing
      # on, so the intersection (current branch, never pushed) was covered by
      # NEITHER. That is the default state of someone whose agent commits for them
      # and who has never heard of pushing: verified as five commits, no warning,
      # ever. Not gated on idle days — "exists in one place only" is a data-loss
      # risk from the first commit, not a forgetting risk that ripens over a week.
      [ "$ref" = "$default_ref" ] && continue
      n=$(git rev-list --count "$base..$ref" 2>/dev/null || echo 0)
      [ "${n:-0}" -eq 0 ] && continue
      unpushed="${unpushed}      ${ref}  —  ${n} commit(s), never backed up anywhere\n"
    else
      n=$(git rev-list --count "$up..$ref" 2>/dev/null || echo 0)
      [ "${n:-0}" -eq 0 ] && continue
      unpushed="${unpushed}      ${ref}  —  ${n} commit(s) not yet backed up to ${up}\n"
    fi
    unpushed_n=$((unpushed_n + 1))
  done < <(git for-each-ref --format='%(refname:short)|%(upstream:short)' refs/heads 2>/dev/null)
fi

# Stashes. git-hygiene tells users a stash is for "holds of minutes-to-hours" — so
# a stash older than the idle threshold is not a hold, it is forgotten work. And a
# stash is invisible to every branch-based check: it is not a branch.
stash_n=0; stash_oldest=0
if git rev-parse --verify -q refs/stash >/dev/null 2>&1; then
  while read -r ts; do
    [ -z "$ts" ] && continue
    stash_n=$((stash_n + 1))
    age=$(( ( $(date +%s) - ts ) / 86400 ))
    [ "$age" -gt "$stash_oldest" ] && stash_oldest=$age
  done < <(git stash list --format='%ct' 2>/dev/null)
fi

# Merged local branches are pure clutter — cheap to count, never urgent.
merged_n=$(git branch --merged "$base" --format='%(refname:short)' 2>/dev/null \
  | grep -vx -e "$default_ref" -e "$current" | grep -c . || true)

# gstack ships its own updater (`gstack-update-check` + `auto_upgrade` config), but
# it only ever runs inside a gstack SKILL's preamble — invoke none of them and it
# never fires. A user with auto_upgrade already true sat six versions behind for
# exactly that reason (measured 2026-08-18: 1.61.0.0 vs 1.67.1.0 available).
# We only REPORT. Performing the upgrade stays gstack's decision, gated by its own
# config — this plugin has no business mutating another tool's install.
report_gstack() {
  local bin="$HOME/.claude/skills/gstack/bin/gstack-update-check"
  [ -x "$bin" ] || return 0
  local out; out=$("$bin" 2>/dev/null | head -1)
  case "$out" in
    UPGRADE_AVAILABLE\ *)
      set -- $out
      echo "  gstack $2 → $3 available.  Run /gstack-upgrade"
      echo
      ;;
  esac
}

if [ "$stale_n" = "0" ] && [ "$remote_n" = "0" ] && [ "${dirty_n:-0}" = "0" ] \
   && [ "${other_wt_n:-0}" = "0" ] \
   && [ "${unpushed_n:-0}" = "0" ] && [ "$stash_oldest" -lt "$IDLE_DAYS" ] \
   && [ "${merged_n:-0}" -lt 5 ]; then
  # Nothing to say about branches — but a pending gstack upgrade still deserves a line.
  gs=$(report_gstack)
  if [ -n "$gs" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " Upstream"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    printf "%s\n" "$gs"
  fi
  exit 0
fi

# Report in risk order, not detection order. A novice cannot tell "this exists in
# one place and a dead disk ends it" from "this is safely on the server, just not
# shipped yet" from "this is tidy-up" — and the old single banner made all three
# look equally alarming, which means equally ignorable.
#
# Remedies lead with PRESERVATION. The previous wording offered "commit, stash, or
# discard" and "pop, branch, or drop" as the first thing a reader saw: an
# irreversible option presented to someone who cannot evaluate it. Deleting is
# still allowed — it is just never the suggestion that arrives first.

at_risk=$(( ${dirty_n:-0} + ${other_wt_n:-0} + ${unpushed_n:-0} ))
[ "$stash_oldest" -ge "$IDLE_DAYS" ] && at_risk=$((at_risk + 1))

if [ "$at_risk" -gt 0 ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " Work that exists in only one place"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo
  echo "  If this computer died right now, the following would be gone."
  echo
  if [ "${unpushed_n:-0}" != "0" ]; then
    echo "  Saved here, but nowhere else — $unpushed_n branch(es):"
    printf "%b" "$unpushed"
    echo "      Back it up:  git push -u origin <branch>"
    echo
  fi
  if [ "${dirty_n:-0}" != "0" ]; then
    echo "  $dirty_n file change(s) on '$current' not saved into git at all."
    echo "      See what they are:  git status"
    echo "      Keep them:          git add -A && git commit -m \"...\" && git push"
    echo
  fi
  if [ "${other_wt_n:-0}" != "0" ]; then
    echo "  Unsaved changes in $other_wt_n other working folder(s) for this project:"
    printf "%b" "$other_wt"
    echo "      See what they are:  git -C <path> status"
    echo
  fi
  if [ "$stash_oldest" -ge "$IDLE_DAYS" ]; then
    echo "  $stash_n set(s) of changes parked with 'git stash', oldest ${stash_oldest}d."
    echo "      Parking is meant to last hours. Look before deciding:  git stash list"
    echo
  fi
fi

if [ "$stale_n" != "0" ] || [ "$remote_n" != "0" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo " Finished work that never shipped"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo
  echo "  Not at risk of being lost — just never merged into $default_ref,"
  echo "  so nobody is using it and it is drifting out of date."
  echo
  if [ "$stale_n" != "0" ]; then
    echo "  $stale_n branch(es), untouched for over ${IDLE_DAYS} days:"
    printf "%b" "$stale"
    echo
  fi
  if [ "$remote_n" != "0" ]; then
    echo "  $remote_n branch(es) on the server with no copy here:"
    printf "%b" "$remote_orphans"
    echo "      Closing a pull request does not delete its branch."
    echo
  fi
  echo "  Finish them with /ship, or /superpowers:finishing-a-development-branch"
  echo "  — which will merge, open a PR, or discard, and say which it did."
  echo
fi

if [ "${merged_n:-0}" -ge 5 ]; then
  echo "  Tidy-up (nothing at risk): $merged_n branch(es) already merged into"
  echo "  $default_ref. Their work is safely in $default_ref; the labels can go:"
  echo "      git branch --merged $base | grep -v '^[* ]*$default_ref$' | xargs -r git branch -d"
  echo
fi

report_gstack
exit 0
