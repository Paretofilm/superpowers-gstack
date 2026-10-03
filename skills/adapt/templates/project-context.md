---
name: {{CONTEXT_SKILL}}
description: {{DESCRIPTION}}
---

# {{PROJECT}} — project knowledge

Loaded on demand, not on every turn. CLAUDE.md keeps the rules every session needs;
this skill keeps what a feature needs. Write facts with a reference (`file:line`, a
commit, a measurement), not opinions, and delete what is no longer true.

## What the product is

<!-- One paragraph: who uses it, for what, and what "good" looks like to them. -->

## Architecture

<!-- The parts, how data flows between them, and where each lives (paths). -->

## Domain truths

<!-- Facts about the domain the code relies on and a newcomer would get wrong. -->

## Pitfalls

<!-- What has bitten before: the symptom, the cause, the fix, with a reference. -->

## Findings

<!-- Measurements and experiments worth keeping: what was tried, the number, where it is recorded. -->

## Running and testing

<!-- The exact commands: build, run, the fast tests, the full suite, the end-to-end check. -->

## How we work

<!-- At most three rules per feature, written at the end of /superpowers-gstack:vibe from
ROUNDS.md: a mistake that came back in two phases or more becomes one rule here. -->

## Keeping this skill current

- Update it in the same commit as the change that made it stale.
- Keep the description under 40 words: it is read on every turn to decide whether to load this skill.
