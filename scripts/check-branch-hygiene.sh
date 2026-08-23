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

# One finding = one aligned line. The previous format spent two to four lines per
# finding on explanation and a literal command; a user who already knows what a
# push is reads that as padding around the only new information — the name.
row() { printf '      %-26s %s' "$1" "$2"; }

# Every ref in the MENU is printed pre-quoted. Refs may legally contain `$( )`,
# backticks, `;`, `&` and `|` — `safe$(whoami)` is an accepted branch name — and the
# menu's whole purpose is that an agent turns it into a shell command. Handing over a
# literal it can paste beats handing over a name it must remember to escape. Findings
# rows stay unquoted: they are read, never executed.
shq() { local v=${1//\'/\'\\\'\'}; printf "'%s'" "$v"; }

# Whether a push is even possible. Gated once, because "and push" printed at a repo
# with no remote is an instruction that dead-ends — and a dead-ended backup reads as
# a completed one.
has_remote=0; git remote 2>/dev/null | grep -q . && has_remote=1

# Worktree paths are absolute and often deep enough to blow the line apart, which
# turns a scannable column into wrapped mush. Shorten for display only: $HOME to ~,
# and anything still long to its last two segments — enough for a human to recognise
# the folder. The agent resolves the real path with `git worktree list`.
shortpath() {
  local t='~' p="$1"
  [ -n "${HOME:-}" ] && p="${p/#$HOME/$t}"
  [ "${#p}" -le 34 ] && { printf '%s' "$p"; return; }
  printf '.../%s/%s' "$(basename "$(dirname "$p")")" "$(basename "$p")"
}
cutoff=$(( $(date +%s) - IDLE_DAYS * 86400 ))

# Commits made on a detached HEAD live in no branch at all, so every check below —
# all of which walk refs/heads — is blind to them. One `git checkout` and they are
# reflog-only. Found 2026-08-23: a commit of real work produced total silence.
detached_n=0
if [ "$current" = "HEAD" ]; then
  detached_n=$(git rev-list --count "$base..HEAD" 2>/dev/null || echo 0)
  case "$detached_n" in ''|*[!0-9]*) detached_n=0 ;; esac
fi

stale=""; stale_n=0; stale_first=""; stale_names=""
while IFS='|' read -r ref ts; do
  [ -z "$ref" ] && continue
  [ "$ref" = "$default_ref" ] && continue
  [ "$ref" = "$current" ] && continue          # you are working here right now
  [ "$ts" -ge "$cutoff" ] 2>/dev/null && continue
  git merge-base --is-ancestor "$ref" "$base" 2>/dev/null && continue   # already landed
  # Already counted under "only on this computer" if it has no upstream, or sits
  # ahead of one. Reporting it here too put the SAME branch under a heading that
  # says it is safe on the server when it has never been on a server — a false
  # statement of safety, and the one a user would act on. Only applied when a remote
  # exists: in a local-only repo no branch has an upstream, and skipping them all
  # would silence this check completely.
  if [ "$has_remote" = "1" ]; then
    up_of=$(git for-each-ref --format='%(upstream:short)' "refs/heads/$ref" 2>/dev/null)
    [ -z "$up_of" ] && continue
    [ "$(git rev-list --count "$up_of..$ref" 2>/dev/null || echo 0)" -gt 0 ] && continue
  fi
  ahead=$(git rev-list --count "$base..$ref" 2>/dev/null || echo "?")
  age=$(( ( $(date +%s) - ts ) / 86400 ))
  stale="${stale}$(row "$ref" "${ahead} commit(s), idle ${age}d")\n"
  stale_n=$((stale_n + 1))
  [ -z "$stale_first" ] && stale_first="$ref"
  [ "$stale_n" -le 3 ] && stale_names="${stale_names} $(shq "$ref")"
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
other_wt=""; other_wt_n=0; scanned=0; wt_first=""; wt_first_n=0; wt_names=""
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
          other_wt="${other_wt}$(row "$(shortpath "$wt_path") (${wt_branch:-detached})" "${n} file(s) not committed")\n"
          other_wt_n=$((other_wt_n + 1))
          [ -z "$wt_first" ] && wt_first="$wt_path" && wt_first_n="$n"
          [ "$other_wt_n" -le 3 ] && wt_names="${wt_names} $(shq "$wt_path")"
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
  [ "$remote_n" -lt 8 ] && remote_orphans="${remote_orphans}$(row "$short" "server-only, idle ${age}d")\n"
  remote_n=$((remote_n + 1))
done < <(git for-each-ref --format='%(refname:short)|%(committerdate:unix)' refs/remotes/origin 2>/dev/null)

# Commits that exist only on this machine. Found as a blind spot on 2026-08-22:
# a branch fully merged locally but never pushed reported nothing, because every
# other check compares against origin/<default> and simply found nothing unmerged.
# At session start this means the previous session ended without pushing — the
# same class as a dirty tree, and the one where a dead laptop costs you the work.
unpushed=""; unpushed_n=0; push_first=""; push_names=""; current_unpushed=0
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
      age_ts=$(git log -1 --format=%ct "$ref" 2>/dev/null || echo 0)
      idle_note=""
      [ "${age_ts:-0}" -lt "$cutoff" ] 2>/dev/null && idle_note=", idle $(( ( $(date +%s) - age_ts ) / 86400 ))d"
      unpushed="${unpushed}$(row "$ref" "${n} commit(s), never pushed${idle_note}")\n"
      [ -z "$push_first" ] && push_first="$ref"
      [ "$unpushed_n" -le 3 ] && push_names="${push_names} $(shq "$ref")"
    else
      n=$(git rev-list --count "$up..$ref" 2>/dev/null || echo 0)
      [ "${n:-0}" -eq 0 ] && continue
      unpushed="${unpushed}$(row "$ref" "${n} commit(s) not pushed")\n"
      [ -z "$push_first" ] && push_first="$ref"
      [ "$unpushed_n" -le 3 ] && push_names="${push_names} $(shq "$ref")"
    fi
    unpushed_n=$((unpushed_n + 1))
    [ "$ref" = "$current" ] && current_unpushed=1
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
   && [ "${unpushed_n:-0}" = "0" ] && [ "${detached_n:-0}" = "0" ] \
   && [ "$stash_oldest" -lt "$IDLE_DAYS" ] \
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

# Report in risk order, not detection order — a novice cannot tell "this exists in
# one place and a dead disk ends it" from "this is on the server, just not shipped".
#
# One line per finding, no inline commands. The report's job is to name the work and
# its risk; ACTING on it is the agent's job, and a command printed for a user who
# does not use a terminal is decoration. What follows the findings is therefore a
# menu addressed to the agent — which turns it into choices the user can click.

at_risk=$(( ${dirty_n:-0} + ${other_wt_n:-0} + ${unpushed_n:-0} + ${detached_n:-0} ))
[ "$stash_oldest" -ge "$IDLE_DAYS" ] && at_risk=$((at_risk + 1))

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Unlanded work"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

if [ "$at_risk" -gt 0 ]; then
  echo "  Only on this computer — gone if the disk dies:"
  [ "${unpushed_n:-0}" != "0" ] && printf "%b" "$unpushed"
  [ "${detached_n:-0}" != "0" ] && printf "%b\n" "$(row "detached HEAD" "${detached_n} commit(s), in no branch")"
  [ "${dirty_n:-0}" != "0" ] && printf "%b\n" "$(row "$current" "${dirty_n} file(s) not committed")"
  [ "${other_wt_n:-0}" != "0" ] && printf "%b" "$other_wt"
  [ "$stash_oldest" -ge "$IDLE_DAYS" ] && printf "%b\n" "$(row "stashed changes" "${stash_n} set(s), oldest ${stash_oldest}d")"
  echo
fi

if [ "$stale_n" != "0" ] || [ "$remote_n" != "0" ]; then
  echo "  On the server, never merged into ${default_ref}:"
  [ "$stale_n" != "0" ] && printf "%b" "$stale"
  [ "$remote_n" != "0" ] && printf "%b" "$remote_orphans"
  echo
fi

[ "${merged_n:-0}" -ge 5 ] && { echo "  Already merged, just clutter: ${merged_n} branch(es)"; echo; }

# The menu. Two invariants, both learned the hard way:
#
#  * Option 1 never destroys anything. A merged-clutter-only repo used to print
#    "Option 1 only ever preserves" directly above "1. tidy  delete 6 branches" —
#    a safety guarantee attached to a deletion. When nothing preservable applies,
#    inspection is offered first and deleting is second.
#  * The back-up option covers EVERY at-risk item, or names what it does not.
#    Covering the first target and leaving the rest guarantees the identical
#    warning next session, which is how a hook teaches you to skip it.
i=0
act()  { i=$((i + 1)); printf '      %d. %-8s %s\n' "$i" "$1" "$2"; }
step() { bk="${bk}             · ${1}\n"; }
more()  { [ "$1" -gt 3 ] && printf ' and %d more' "$(( $1 - 3 ))"; }

bk=""; uncovered=""
push_tail=", then push it"
[ "$has_remote" = "0" ] && push_tail=" (no remote is configured, so this is a checkpoint on the same disk — not a backup)"

# A branch is where the reflog stops being the only way back — but a brand-new local
# branch is still one disk. The step has to carry through to the push, or the next
# session reports the same work under a different name.
if [ "${detached_n:-0}" != "0" ]; then
  det_tail=" — otherwise they are reachable only through the reflog"
  [ "$has_remote" = "1" ] && det_tail=", then push it${det_tail}"
  step "give the ${detached_n} detached commit(s) a branch (git switch -c <name>)${det_tail}"
fi
if [ "${dirty_n:-0}" != "0" ]; then
  dirty_tail="$push_tail"
  [ "${current_unpushed:-0}" = "1" ] && dirty_tail=""   # the push step below covers it
  if [ "$current" = "HEAD" ]; then
    step "commit the ${dirty_n} loose file(s) onto that new branch${dirty_tail}"
  else
    step "commit the ${dirty_n} loose file(s) on $(shq "$current")${dirty_tail}"
  fi
fi
[ "${unpushed_n:-0}" != "0" ] && [ "$has_remote" = "1" ] && \
  step "push${push_names}$(more "$unpushed_n") — every branch listed above as unpushed$([ "${dirty_n:-0}" != "0" ] && [ "${current_unpushed:-0}" = "1" ] && printf ', after the commit above')"
[ "${other_wt_n:-0}" != "0" ] && \
  step "in the other working folder(s)${wt_names}$(more "$other_wt_n") — commit the loose file(s) there and push"
[ "$stash_oldest" -ge "$IDLE_DAYS" ] && \
  uncovered="the ${stash_n} parked change set(s) — no push reaches a stash, so it needs a decision, see below"

echo "  What can be done — offer these as choices and carry out the pick:"
if [ -n "$bk" ]; then
  act "back up" "make everything above recoverable — all of:"
  printf "%b" "$bk"
  [ -n "$uncovered" ] && printf '             (not covered: %s)\n' "$uncovered"
fi
[ "${dirty_n:-0}" != "0" ] && act "show" "what those ${dirty_n} file(s) actually change, before deciding"
[ "${other_wt_n:-0}" != "0" ] && act "look at" "$(shortpath "$wt_first") — a second working folder (git worktree list), ${wt_first_n} loose file(s)"
[ "$stash_oldest" -ge "$IDLE_DAYS" ] && act "look at" "the ${stash_n} parked change set(s) — git stash list, then git stash show -p"
if [ -n "$stale_names" ] || [ "$remote_n" != "0" ]; then
  target="${stale_names}$(more "$stale_n")"
  [ -z "$stale_names" ] && target=" the ${remote_n} server-only branch(es)"
  [ -n "$stale_names" ] && [ "$remote_n" != "0" ] && target="${target} (plus ${remote_n} server-only)"
  act "finish" "${target# } via /ship — merges, opens a PR, or drops it, and says which"
fi
if [ "${merged_n:-0}" -ge 5 ]; then
  [ "$i" -eq 0 ] && act "show" "which ${merged_n} branch(es) are already merged — nothing is deleted by this"
  act "tidy" "delete those ${merged_n} merged branch(es) — their commits are already in ${default_ref}"
fi
echo

report_gstack
exit 0
