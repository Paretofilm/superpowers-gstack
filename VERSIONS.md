# Verified Versions

This manual was last verified against these versions:

| Component | Version | Date |
|-----------|---------|------|
| GStack | 1.68.3.0 | 2026-08-24 |
| Superpowers | 6.3.0 | 2026-08-18 |
| Claude Code | 2.1.234 | 2026-08-18 |

When any of these change, review the manual for accuracy.

Verified against what is actually installed and published — `~/.claude/skills/gstack/VERSION`,
the Superpowers plugin cache, and `npm view @anthropic-ai/claude-code version` — not against
release notes. The six auto-update PRs closed on 2026-08-18 disagreed with all three:
one claimed GStack v1.67.0.0 and a Superpowers skill (`writing-good-tests`) that the
installed 6.3.0 does not contain. Lint rule **E10** now rejects a reference to an
unknown upstream skill, and **W3** flags roster drift where an upstream is installed.
