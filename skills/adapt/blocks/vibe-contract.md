## Vibe contract (standing approvals; overrides skill gates) <!-- gstack-vibe-v1 -->

This project chose the vibe workflow (`.gstack/workflow`): one intake, autonomous completion,
one review by the user. A new feature starts with `/superpowers-gstack:vibe` (the procedure),
not `superpowers:brainstorming` → `writing-plans`; no spec or plan review (pitfall-verification,
quality-review, apple-native-review) runs before the end.

**Standing approvals after intake.** Design, spec and plan are pre-approved. This overrides the
HARD-GATE in `superpowers:brainstorming`, the execution-method choice in `superpowers:writing-plans`
(use subagent-driven) and the options menu in `superpowers:finishing-a-development-branch` (land by
the `Landing mode:` line). Pushing the feature branch for backup is pre-approved. Never ask "what
next" between phases.

**Stop only for:** irreversible or destructive actions, security-sensitive actions, side effects
outside the worktree, a force-push or a push to the default branch outside the `Landing mode:`
line, money, a licence, or a real blocker. Decide everything else and log it:
`Ruling: <choice> — <why> — <cost if wrong>`.

**The one checkpoint is the acceptance tests.** The user reads the test overview once. After their
ok the tests are locked: never edit a locked test to turn red into green, by any tool; if a test is
wrong, stop and say which and why. The lock's `verify` must pass before landing.

**Context.** Keep the main thread under about 150k tokens: one fresh subagent per phase, `STATUS.md`
updated at every phase boundary. Project knowledge lives in the skill `{{CONTEXT_SKILL}}`
(`.claude/skills/{{CONTEXT_SKILL}}/SKILL.md`), not here: load it before planning; working rules go
in its "How we work" section.

**Review once, at the end.** The multi-lens chain runs once per feature, after the last phase, at its
computed tier. Fix critical and important findings; do not re-review minor ones.
