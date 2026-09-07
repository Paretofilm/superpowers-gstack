---
name: spec-drift
description: |
  Standalone plan-vs-code audit on any branch: runs /ship Step 8's plan-completion
  section from disk (hash-pinned) against an explicit plan and base. Report, JSON,
  exit code. Never edits code.
---

# /superpowers-gstack:spec-drift

Does this plan still match the code? `/ship` already answers that — Step 8, the
Plan Completion Audit — but only at merge time, only inside a twenty-step
pipeline, and never on a branch that is not shipped. This skill runs that same
audit standalone. It is a **wrapper**: the audit text is gstack's, read from disk
at run time; this file holds only what differs when nothing is being shipped.

Invoke with:

```
/superpowers-gstack:spec-drift <plan-path> [--base <ref>] [--section <path>]
/superpowers-gstack:spec-drift --repin [--section <path>]
```

- `<plan-path>` — required. A plan with actionable items: `docs/superpowers/plans/*.md`
  or a `progress.md`. The plan path is an argument, never discovered.
- `--base <ref>` — the diff baseline. Default: the repo's default branch
  (`origin/HEAD`, else the first of `origin/main`, `origin/master`, `main`,
  `master` that exists). Pass an older commit to see drift that accumulated on
  the default branch across many small merges.
- `--section <path>` — override the upstream section path. For the hash-guard
  test only; the default is `~/.claude/skills/gstack/ship/sections/plan-completion.md`.
- `--repin` — accept a changed upstream section after reading its diff (below).
  Does no audit.

`SKILL_DIR` below is this skill's base directory, as the Skill tool reports it.
The mechanical half — the pin and the exit code — lives in
`"$SKILL_DIR/../../scripts/spec-drift.py"`; nothing below is decided by reading
the report and guessing.

## Contract

Same human-readable report as `/ship` Step 8, same JSON on the last line —
`{"total_items":N,"done":N,"changed":N,"deferred":N,"unverifiable":N,"summary":"…"}`,
where `"deferred"` counts NOT DONE items exactly as Step 8 uses it — plus a
verdict line just above the JSON:

| Verdict line | Meaning | Exit |
|---|---|---|
| `SPEC-DRIFT: CLEAN (exit 0)` | every item DONE or CHANGED | 0 |
| `SPEC-DRIFT: DRIFT (exit 1)` | any PARTIAL, NOT DONE or UNVERIFIABLE item | 1 |
| `SPEC-DRIFT: COULD-NOT-RUN (exit 2)` | pin mismatch, unreadable plan, empty diff, no actionable items, no JSON | 2 |

**What "exit" means for a Markdown skill.** A skill cannot return a process
status. The verdict line *is* this skill's exit code — structured text, computed
by `spec-drift.py verdict`, never judged from the report. A caller that needs a
real process status runs that same command on the final JSON line:

```bash
python3 "$SKILL_DIR/../../scripts/spec-drift.py" verdict <<'JSON'
<the JSON line the skill ended with>
JSON
echo "exit=$?"     # 0 / 1 / 2 — no prose parsed anywhere; exit 1 counts only
                   # alongside the `SPEC-DRIFT: DRIFT (exit 1)` line on stdout
```

Fail closed: when in doubt the answer is 2, never 0. This skill never edits source code,
the plan, or the upstream section — it reports. Write-back into the plan and a
drift ledger are Fase 2 of the spec
(`docs/superpowers/specs/2026-09-07-spec-drift-design.md`), not this skill.

## Phase 0 — refuse early

| Condition | Do this |
|---|---|
| No `<plan-path>` (and no `--repin`) | Print the usage block above, then `SPEC-DRIFT: COULD-NOT-RUN (exit 2) — plan path is required`. Stop. |
| Plan path missing or unreadable | `COULD-NOT-RUN (exit 2)`, naming the path. Stop. |
| Not a git repository | `COULD-NOT-RUN (exit 2) — the audit is a diff; there is no diff without git`. Stop. |
| Plan is not under `docs/superpowers/plans/` and not named `progress.md` | Warn once: design docs carry prose, not actionable items, and will come back `COULD-NOT-RUN` (prose claims are Fase 3). Continue anyway. |

Resolve the base and make sure there is a diff to audit against. Paste the two
user-supplied values inside **single quotes**, verbatim; if a value itself
contains a single quote, refuse with exit 2 rather than escaping it:

```bash
PLAN='<plan-path>'                 # single-quoted verbatim — a $( ), backtick or $ in a path is inert
BASE='<--base value, or empty>'
[ -f "$PLAN" ] || { echo "plan '$PLAN' is not a readable file"; exit 2; }
if [ -z "$BASE" ]; then
  HEAD_REF=$(git symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/||')
  for c in "$HEAD_REF" origin/main origin/master main master; do
    [ -n "$c" ] && git rev-parse -q --verify --end-of-options "$c^{commit}" >/dev/null 2>&1 && BASE=$c && break
  done
fi
git rev-parse -q --verify --end-of-options "$BASE^{commit}" >/dev/null 2>&1 || { echo "base '$BASE' is not a commit"; exit 2; }
[ -n "$(git diff --stat "$BASE...HEAD" 2>/dev/null)" ] || { echo "empty diff $BASE...HEAD — pass --base <older-commit>"; exit 2; }
echo "PLAN=$PLAN BASE=$BASE"
```

Every candidate is verified as a commit before it is used — a dangling
`origin/HEAD` falls through to the next candidate instead of ending the run —
and the ref that verified is kept as written (`origin/main`, not `main`): in a
fresh clone the remote-tracking ref exists and the local one may not.
`--end-of-options` keeps a value beginning with `-` from being read as a flag.
An empty diff is exit 2, not "everything NOT DONE": on the default branch with
the default base there is nothing to audit against, and the fix is an older
`--base`. Note what `exit 2` inside a block does: it ends that one Bash call.
It does not end the skill — you do, by printing the `SPEC-DRIFT: COULD-NOT-RUN
(exit 2)` verdict line and stopping. The number is the message, not the
mechanism.

## Phase 1 — the pin, before anything is read

```bash
python3 "$SKILL_DIR/../../scripts/spec-drift.py" check   # add --upstream "<--section value>" when given
```

Exit 0 prints `PIN OK …`: continue. Anything else: print the script's stderr
verbatim — it names both hashes, the installed gstack version and the way out —
then `SPEC-DRIFT: COULD-NOT-RUN (exit 2)` and stop. **Never run the audit past
a failed check**, and never edit the upstream file to make it pass: the section
is gstack's, regenerated on their side from a template, and a local edit is
overwritten by the next update. The check is the whole reason this wrapper can
claim to run the audit `/ship` runs, rather than a copy of it.

## Re-pin mode (`--repin`)

The pin breaks whenever gstack changes the section, which is often — gstack
auto-updates weekly. Re-pinning is deliberate, in steps, and never blind:

1. Show what changed:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" repin   # add --upstream when --section was given
   ```
   Exit 0 with `PIN UNCHANGED`: say so and stop. Exit 2 with `REPIN BLOCKED:
   ANCHORS MISSING`: the section no longer carries text the overrides below
   name — that needs a fix to this file first, not a re-pin; say which anchors
   and stop. Exit 3: the unified diff is on stdout, followed by `ANCHORS: all
   present` — show the diff to the user in full, not summarised.
2. The anchors are checked mechanically (the eight strings in `ANCHORS` in
   `spec-drift.py`: the Step 8 and 8.1 headings, Plan File Discovery, Gate
   Logic, `<base>`, Include in PR body, Parent processing, `"total_items"`).
   What the script cannot judge is meaning: read the diff against the overrides
   in Phase 2 below and say, in one or two sentences, whether any override now
   contradicts what the section says — a renamed verdict, a new gate, a changed
   JSON key. If one does, say which — that is also a fix to this file, not a
   re-pin.
3. Ask with `AskUserQuestion`: accept the new section as the pinned one?
   Options: **Accept** (recommended when every override still fits) / **Not
   now**. End your message at this question.
4. On Accept, pass back the sha the diff run printed — `--yes` is refused
   without it, and refused if the file changed since the diff was shown:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" repin --yes --sha <the 12 hex chars from the diff run>
   ```
   then remind the user that `skills/spec-drift/pin.json` and
   `skills/spec-drift/pin/plan-completion.md` must be committed together — the
   pin lives in the plugin, not on this machine.

## Phase 2 — dispatch the audit

Step 8 says to run as a subagent, in the foreground, and that executing it
inline forfeits the fresh-context isolation. That holds here. Invoke the
`Agent` tool with `subagent_type: "general-purpose"`, `run_in_background: false`,
`description: "spec-drift audit"`, and this prompt with the four placeholders
filled (`<SECTION_PATH>` is the upstream path or the `--section` value;
`<SCRIPT_PATH>` is the absolute path of `"$SKILL_DIR/../../scripts/spec-drift.py"`
— the subagent has its own shell and cwd, so never a relative path):

```
You are the dispatched subagent for a standalone plan-completion audit
(superpowers-gstack:spec-drift). Read this file in full, then execute ONLY its
`## Step 8: Plan Completion Audit` section — stop where `## Step 8.1` begins;
Step 8.1, "Prior Learnings" and Step 8.2 are not part of this run:

  <SECTION_PATH>

Overrides. Each replaces the part of Step 8 it names; everything else in Step 8
applies verbatim — the extraction rules, the verification modes, the verdict
definitions and their cautions.

0. Before you read the section, run `python3 <SCRIPT_PATH> check` (add
   `--upstream <SECTION_PATH>` if it is not the default) and confirm it prints
   `PIN OK`. The parent ran it moments ago, but the file is auto-updated by a
   third party and only a check made by the process that reads the bytes
   closes that window. Anything else: emit the JSON line with total_items 0
   and the check's stderr in "summary", and stop.
1. You ARE the subagent Step 8 says to dispatch. Do not dispatch another agent;
   execute the quoted subagent prompt yourself.
2. "Plan File Discovery": skip it entirely. The plan file is <PLAN_PATH> — no
   conversation-context lookup, no content search, no freshness fallback, no
   relevance validation. If it is unreadable, emit the JSON line with
   total_items 0 and the reason in "summary".
3. Wherever Step 8 says `<base>` or `origin/<base>`, use exactly <BASE_REF>.
   The diff is `git diff <BASE_REF>...HEAD`; the log is
   `git log <BASE_REF>..HEAD --oneline`.
4. "Gate Logic": do not use AskUserQuestion and do not wait for anyone.
   Classify every item, print the Output Format block, and stop. The gate's
   decisions are made by the caller from your JSON. Skip "Include in PR body"
   and "Parent processing".
5. Report only. Do not commit, push, edit the plan, or edit any file.
6. Your LAST line is the JSON object Step 8 specifies, with exactly its keys:
   total_items, done, changed, deferred, unverifiable, summary — where
   deferred is the NOT DONE count. Nothing after it.
```

Wait for it (Step 8's own budget: about ten minutes). If it returns without a
parseable JSON last line, or fails outright, do what Step 8 itself prescribes,
once: run the same Step 8 inline in your own context with the same overrides.
If that also yields no JSON, do not guess a result — `SPEC-DRIFT: COULD-NOT-RUN
(exit 2)`.

## Phase 3 — verdict and output

1. Separate the subagent's reply into two parts: the JSON line at its end, and
   everything above it. Print the part above — the human-readable report
   (`PLAN COMPLETION AUDIT … COMPLETION: …`) — verbatim. Do not print the JSON
   here; it appears exactly once, as the last line of your response (step 3).
2. Compute the exit code from the JSON line — never by reading the report:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" verdict <<'JSON'
   <the JSON line>
   JSON
   ```
   It prints the `SPEC-DRIFT: … (exit N)` line on stdout with a breakdown
   (`done= changed= partial= not_done= unverifiable= of N`) and exits N. If the
   object arrived pretty-printed over several lines, collapse it to one line
   first — the contract is one line, and `verdict` reads exactly one. Read the
   code and the line together: exit 1 means DRIFT only when the
   `SPEC-DRIFT: DRIFT (exit 1)` line is there. A bare exit 1 with no
   `SPEC-DRIFT:` line is the Python interpreter itself failing (a missing
   interpreter, a syntax error under an old Python) and is
   `COULD-NOT-RUN (exit 2)`, never drift.
3. End the response with, in this order: `Plan: <PLAN_PATH>  Base: <BASE_REF>`,
   the verdict line, and the JSON as the very last line — so a caller such as
   `/superpowers-gstack:autoimplement` can take the code from the verdict line
   and the counts from the JSON without parsing prose.

## What this skill is not

- Not `/ship`. It runs one of ship's sections; it merges, tests and ships nothing.
- Not `/superpowers-gstack:pitfall-verification`. Pitfall asks "would this work?"
  of an artifact seen from inside; this asks "does the artifact match reality?".
- Not a replacement for the plan-fidelity rule in CLAUDE.md ("fix the plan in the
  same commit as the divergence"). That rule prevents; this catches what it missed.
- Not a fork of Step 8. A change to the audit itself belongs upstream, in
  `garrytan/gstack`.
