---
name: vibe
description: Build one feature end to end under the vibe contract — one intake round, plain-language acceptance criteria as the one checkpoint, a fresh subagent per phase, one review, landing.
---

# Vibe: one feature, intake to landing

Invoke with: `/superpowers-gstack:vibe <what to build>`

The user answers questions once, approves the acceptance criteria once — in plain
language, never as test files — and reviews the finished work once. Everything between
is yours to decide and log. The rules live in
the project's CLAUDE.md section **Vibe contract** (marker `gstack-vibe-v3`); this skill
is the procedure. If `.gstack/workflow` is not `vibe`, say so in one line of the intake
(the contract's standing approvals then hold for this invocation only) and suggest
`/superpowers-gstack:adapt` to choose the profile for good. If the section carries an
older marker (`gstack-vibe-v1` or `-v2`), say so in one line of the intake and suggest
`/superpowers-gstack:adapt`; where the old text describes the checkpoint differently,
Step 3 below is the one you follow.

Begin every Bash call that needs the lock script with:

```bash
SKILL_DIR='<the base directory the Skill tool printed when this skill loaded>'
LOCK="$SKILL_DIR/../../scripts/lock-acceptance-tests.py"
[ -f "$LOCK" ] || LOCK=$(ls ~/.claude/plugins/cache/*/superpowers-gstack/*/scripts/lock-acceptance-tests.py 2>/dev/null | sort -V | tail -1)
[ -f "$LOCK" ] || { echo "BLOCKED — lock-acceptance-tests.py not found; run /plugin update superpowers-gstack"; exit 2; }
```

## Step 0: Read before asking

Load the project's context skill (`.claude/skills/*-context` or `*-kontekst`) if there
is one, then the code the feature touches. Classify the scope: files, tracks, whether
the result is visual (UI, render, video), and the risk tier
`scripts/classify-change.py` would give it. Steps 0–2 change no code (Brainstorm and Utforsk først write nothing either). Do not enter plan
mode yourself: leaving it asks the user a second time, and the acceptance criteria are
the one checkpoint.

## Step 0b: Choose how to start

Ask one `AskUserQuestion` before any intake, recommended way first, so the user picks
how much of the idea is still open. The names below are what the user sees:

- **Brainstorm** — the idea is vague. Run `superpowers:brainstorming` in its short form:
  one question at a time, two or three approaches with a recommendation, no spec and no
  HARD-GATE wait (the contract overrides it). Its result becomes the reference and a draft
  of the acceptance criteria.
- **Hurtig** — the idea is clear. Go straight to Step 1 as written. This is the default
  when the user gives no other signal.
- **Fra ferdig spec/plan** — a spec, plan or office-hours document already exists. Ask for
  the path, read it, draw 5–10 acceptance criteria and the out-of-scope list from it, and
  reuse the file as `SPEC.md` in Step 2 instead of writing a new one.
- **Utforsk først** — read-only. Read the code, propose two or three possible features or
  moves with scope and the tier `scripts/classify-change.py` would give each, and let the
  user pick one. The pick is then handled like Brainstorm's result.

Every way ends in Step 1: the reference and acceptance criteria, and what is out of scope,
are always confirmed there, and from Step 2 on nothing differs. The questions Step 1 asks
that the chosen way already answered are skipped, not asked again.

## Step 1: Intake — one round

Ask everything in one `AskUserQuestion` round: at most eight questions, four per call,
recommended option first and marked `(Recommended)`. Always ask for:
- the reference ("fasit") and the 5–10 acceptance criteria you drew from the request,
  so the user can correct them — each in the user's language as observable behaviour
  (what they will see or be able to do), never a file, test name or code;
- what is out of scope.

Ask nothing you can find in the code, the context skill or CLAUDE.md. After this round,
design, spec and plan are pre-approved.

## Step 2: SPEC.md and PLAN.md

Write `docs/superpowers/vibe/<YYYY-MM-DD>-<feature>/SPEC.md` (goal, non-goals,
acceptance criteria) and `PLAN.md` (small tasks; each has one test and one
"done when" line; no code). Commit both. Do not wait for a spec or plan review.

**A pending `## Project` in CLAUDE.md** (`<!-- gstack-project-pending -->` on the
heading, left by `/superpowers-gstack:adapt` in an empty folder) is filled in now, once,
from what the intake settled — no new question. Write `.gstack/adapt-project.md`:
`## Project` with `### Tech Stack / Testing / QA URL / Deployment` (omit what does not
apply) and `### Routing for this stack` (`/qa <url>` for a browser UI, `/cso` before
`/review` when the acceptance criteria touch auth, user data, payments or external
APIs, the Apple skills on a native track). Pick the sensitivity the way adapt does
(`very high` for real-time audio or lock-free concurrency, `high` for migrations, data
transforms or security signals, `medium` for UI work, `low` for CLI tools and
libraries). For a native platform write `.gstack/track` (`ios` | `macos` | `both`)
first and resolve `IOS_SIMULATOR` and `DEVELOPMENT_TEAM` per adapt's
`blocks/PLACEHOLDERS.md`. Then:

```bash
SKILL_DIR='<the base directory the Skill tool printed when this skill loaded>'
ADAPT="$SKILL_DIR/../../scripts/adapt-claude-md.py"
[ -f "$ADAPT" ] || ADAPT=$(ls ~/.claude/plugins/cache/*/superpowers-gstack/*/scripts/adapt-claude-md.py 2>/dev/null | sort -V | tail -1)
python3 "$ADAPT" --project-section .gstack/adapt-project.md --set 'DOMAIN_SENSITIVITY=<level>' \
  [--set 'IOS_SIMULATOR=…' --set 'DEVELOPMENT_TEAM=…']
```

The script replaces the pending section once and drops the marker. Exit 2 is a refusal
with the reason on stderr: fix the input it names and run it again (an unresolved
native placeholder, a second H2 in the section file, an unclosed code fence, an
invalid pin). Only `no \`## Project\` section carries` means the section is already
the project's own: leave it and say so. Relay the report's Removed list if it has one
(lines someone wrote under the pending heading; the snapshot keeps them). Delete
`.gstack/adapt-project.md`, commit CLAUDE.md with the spec, and write one line in the log: `Filled in ## Project: <stack>, tests via
<command>, sensitivity <level>.`

## Step 3: Acceptance criteria — the one checkpoint

Write the acceptance tests from the criteria, in a directory of their own (for example
`Tests/Acceptance/` or `tests/acceptance/`). For visual work the test is a truth check
against the reference — a screenshot or render measured against it — not only unit
tests. Every criterion is checked by at least one test, and every test checks a
criterion; fix a gap before you write to the user.

The user judges outcomes, not test code: never ask them to approve a test file. Send
ONE message in the user's language, in this order (the bold labels are for you; write
the parts, in the user's words, without copying the labels):

1. **The criteria**, as a short numbered list: the 5–10 acceptance criteria from Step 1,
   each written as observable behaviour — what the user will see or be able to do. No
   file paths, test names or code in this list.
2. **What approving means**, in one plain sentence: these criteria become the definition
   of done, and the tests behind them are locked so no agent can edit a test to turn red
   into green.
3. **For the curious**, marked as optional: the exact test files, one line each (file,
   what it checks). `lock` commits what is on disk, so this list names every file the
   lock will cover, but it is not what the user is asked about.
4. **The question**, last: are these the right criteria for done? Close with this line
   for the user to paste:

```
/goal All tasks in PLAN.md are done: tests green, build without warnings, STATUS.md updated. Or stop after 60 turns.
```

If the user changes a criterion, change `SPEC.md` and the tests to match, commit the
spec, and send the message again; nothing is locked until they approve.

The user approves in one of two ways: they say ok, or they paste the `/goal` line;
whether they say ok or paste the `/goal` line, run the lock first and only then start
Step 4 (a `/goal` the user pastes is started by them; lock before you act on it):

```bash
python3 "$LOCK" lock --feature <feature> --path '<acceptance-test glob>'
```

From here on, never edit a locked test to turn red into green, by any tool. If a test
is wrong, stop and say which one and why; only the user unlocks
(`python3 "$LOCK" unlock --feature <feature>`). Send the lock commit SHA the script
printed in your next message, so the user can check what was locked.

## Step 4: One fresh subagent per phase

Run the phases of PLAN.md with `superpowers:subagent-driven-development`: each phase's
part of the plan is one subagent's brief; the main thread orchestrates and stays under
about 150k tokens of context. Two fixed rules go into every brief:
- **wire what you build into the app in the same round** the tests turn green — green
  tests on code nothing calls are not done;
- **find every place the app already does the same job** and make it follow the new
  rules.

At every phase boundary update `STATUS.md` (done, remaining, open Rulings). Add one line
per round to `ROUNDS.md`: what was tried, which tests still failed. Never ask "what
next" between phases.

**Stop only for:** irreversible or destructive actions, security-sensitive actions,
side effects outside the worktree, a force-push or a push to the default branch outside
the `Landing mode:` line, money, a licence, or a real blocker. Pushing the feature branch
for backup is pre-approved. Decide everything else and log it in STATUS.md as
`Ruling: <choice> — <why> — <cost if wrong>`.

## Step 5: Tests while working

A subagent runs only the tests that cover what it changed (the affected target or a
`--filter`). The full suite runs at each phase boundary and once before landing.
After a timeout: at most two reruns, then one single run with its log.

## Step 6: One review, at the end

Invoke `/superpowers-gstack:pitfall-verification` once, after the last phase, on the
whole branch; its tier is computed as always. Fix critical and important findings; do
not re-review minor ones. No plan reviews, no `/autoplan`.

## Step 7: Lessons, committed before landing

Read `ROUNDS.md`: a mistake that came back in two phases or more becomes one working
rule — at most three per feature — in the **How we work** section of the context skill,
never into CLAUDE.md. Commit the change now, on the feature branch: lessons written
after landing never reach the default branch and vanish with the worktree. Touch neither
the locked tests nor the contract in this step. If the project has no context skill,
create `.claude/skills/<project>-context/SKILL.md` with a `## How we work` section
holding the rules, and commit it with the feature; never put them in CLAUDE.md.

## Step 8: The lock must hold

```bash
python3 "$LOCK" verify --feature <feature>
```

Exit 0 is required before landing.

**Re-lock cases first.** After a rebase it warns that the lock commit left the
branch's history (a warning, not exit 1); in `pr` landing mode, a squash-merge commit on
main that changed the receipt makes `verify` exit 1 (`receipt changed by commit …`).
Both mean the lock must be redone by the user, and re-locking after a rebase or a
squash-merge receipt change is not editing a test. The squash-merge case applies only
when the exit-1 output names no file other than the receipt. A changed test file is never
a re-lock case: it goes to the next paragraph. Tell the user and ask them to re-lock.

**Any other exit 1** names each changed file (the receipt `.gstack/acceptance-lock.json`,
a new file under a locked path and a hidden assume-unchanged flag included): restore it
from the lock commit, or stop and tell the user which test is wrong. The lock defends
against mistakes and shortcuts, not against deliberate history rewriting; `verify` is a
gate, not proof. It compares the locked files with the lock commit in the working tree,
the index and HEAD, and checks the receipt and new files under the locked paths. It
cannot see a `conftest.py` or pytest configuration outside those paths that changes what
the tests do, a faked or amended commit subject on the receipt, or a rewritten history.
Only `__pycache__`, `.pytest_cache` and `.DS_Store` are exempt from the new-file
check.

## Step 9: Land

Land by the project's `Landing mode:` line — `solo` → `/superpowers-gstack:land`,
`pr` → `/ship` — with no options menu. Ask once about the push only when the project
requires it. The lock stays after landing as the record: the landed tests remain
protected, and only the user unlocks them.

## Step 10: Final report

One message: what was built, how the user verifies it, every Ruling, deferred findings.
