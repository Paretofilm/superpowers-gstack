## Keep the plan true to the code <!-- gstack-plan-fidelity-v2 -->

When implementation diverges from the plan, **fix the plan in the same commit as the divergence.** Not at the end, not at `/ship`, not "later".

A plan that describes something nobody built is worse than no plan: the next agent reads it as instructions and implements the abandoned design. Being out of date is passive; being confidently wrong is active harm.

### The three ways a plan goes stale

1. **Better approach found.** You read the existing code and the planned design turns out to be unnecessary or wrong. This is a *good* outcome — but the plan must now say what was built and why the draft was dropped.
2. **Task done out of order.** The user reports a bug that a later phase covers, so you do it now. Mark it done and note why the order changed.
3. **A measurement kills a premise.** The plan's reasoning rested on an assumption; you measured, and it was false. Record the number you measured, not just "this turned out differently".

### What to write

Replace the superseded section — do not append a correction below it. Someone skimming reads the first plausible thing they find.

- Mark the task done **in the notation the file already uses** — if the plan or progress file has an established convention (`- [x] … (sha)`, a `DONE:` prefix, a status column), follow it; introduce a marker of your own only when the file has none yet. What matters is that the marker carries the commit SHA, not which glyph carries it. A second completion format in a file that already had one makes the file harder to scan, which is the opposite of the point. Then state, in one or two sentences, how the built thing differs from the draft
- Keep the *reason* the draft was dropped. That is the part a future reader cannot reconstruct
- If part of the draft is still worth doing, move it to an explicit "deferred" note **with a trigger** — what would make it urgent — rather than leaving it inline as if it were planned work

### Deleting is allowed

If a whole phase is invalidated, say so at the top of that phase and stop maintaining its tasks. A struck-through phase with one honest sentence beats five obsolete task descriptions kept alive out of politeness to the draft.

### Why this is not the ship gate's job

`/ship` audits plan completion and classifies each item (`DONE` / `PARTIAL` / `CHANGED` / …), which is real and useful — but it runs at merge time, writes its findings to the PR body rather than back into the plan, and never runs at all on a branch that is not shipped. Divergence happens hours earlier, while the plan is still being read. Fix it there.
