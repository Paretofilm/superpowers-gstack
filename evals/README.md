# Plugin evals

Suites for `claude plugin eval` (Claude Code 2.1.269+). Each run is a real model call on
your account, so run them on purpose, not on every push.

## `trigger/` — does natural phrasing pick the right skill?

Fourteen cases: twelve requests phrased the way a user would type them, each graded on
whether the matching `superpowers-gstack:` skill was invoked, and two requests no skill
covers, graded on no skill at all being invoked (bare or namespaced). Free graders only
(`tool_used`), no judge model.

```bash
claude plugin eval . --tag trigger --ablation none --model claude-opus-5-5 --max-cost-usd 15
```

`--ablation none`: a skill can never fire without the plugin, so a no-plugin arm would
only score zero and tell nothing. First run, 2026-10-25, Opus 5.5, 3 runs per case:
14/14 cases at 1.00, $6.02.

What it does not measure:

- **Only the description.** Eval runs load no `CLAUDE.md`, so the routing a project's
  CLAUDE.md adds is absent. A case that fails here may still be rescued by routing.
- **Not which skill came first.** `tool_used` counts matching calls; a run that also
  invoked another skill still passes.
- **Not what the skill then does.** The cases grant only read-only tools and stop after
  four turns. `land`, `work-state`, `pitfall-verification` and `vibe` need `wt`, the
  network, gstack, superpowers or the OpenRouter key, none of which an isolated run has.

A process A/B of Superpowers itself, with and without, is in
`docs/superpowers/evals/superpowers-ab/` (kept out of this directory so it never runs
against this plugin).

## Known limit on the maintainer's Mac

A `credential_process` profile in `~/.aws/config` makes every Bash-granting eval refuse
to run ("a Bash-granting evaluation cannot run here"). Suites that need a shell must run
on a machine without one, such as a CI runner.
