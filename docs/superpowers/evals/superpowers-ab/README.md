# Superpowers with and without — A/B on process

Asked 2026-10-25: a tester reported the same result with and without Superpowers on
Opus 5.5, so should superpowers-gstack keep it as a dependency? This suite measures
*process* (does it ask before building, does it write the test first, does it find the
root cause), not only the end result, with `claude plugin eval`'s no-plugin baseline.

It is a suite for **Superpowers**, not for this plugin, so it lives here and not under
`evals/` (where `claude plugin eval .` would run it against superpowers-gstack). To run
it, copy Superpowers and put the cases in its eval directory:

```bash
rsync -a --exclude tests --exclude .git ~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/ /tmp/sp/
mkdir -p /tmp/sp/evals && cp -R docs/superpowers/evals/superpowers-ab/process /tmp/sp/evals/
cd /tmp/sp && claude plugin eval . --tag process --runs 3 --model claude-opus-5-5 \
  --judge-model claude-sonnet-5-5 --scaffold --allow-tools Write Edit --max-cost-usd 25
```

No shell is granted: on the maintainer's Mac a `credential_process` profile in
`~/.aws/config` makes Bash-granting evals refuse to run, so the cases say there is no
shell and grade what can be graded without one.

## Result, 2026-10-25 (Superpowers 7.0.0, Opus 5.5, 3 runs per arm, $3.07)

| Case | With | Without | Δ | What happened |
|---|---|---|---|---|
| `vague-request` — "make an app to track my workouts" | 1.00 | 0.00 | **+1.00** | With: `brainstorming` fired 3/3, asked what was wanted, wrote nothing. Without: built an app straight away 3/3 |
| `debug-failing-test` — one failing test, output pasted | 1.00 | 1.00 | 0 | Both found the missing sort and left the test alone. `systematic-debugging` fired 1/3 |
| `tdd-new-function` — `slugify` plus tests | 0.50 | 0.50 | 0 | Both wrote the code before the test, 6/6. `test-driven-development` never fired |

Mean Δ +0.33. The two cases where the outcome is the same are the "same result" the
tester saw: on a small, clear task Opus 5.5 does the right thing on its own, and
Superpowers 7.0.0 sizes such a task as "just do it". The value it adds here is in
front of the work, not in it: a vague idea gets questions instead of an app.

Limits: three runs per arm, three cases, no shell, so no red-green cycle and no test
runs could be graded. A Bash-capable runner (CI) is needed to measure TDD properly.
