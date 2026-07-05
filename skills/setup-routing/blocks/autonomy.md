## Autonomy and user interruption <!-- gstack-autonomy-v2 -->

Default to autonomous continuation. Stopping to ask the user is the LAST resort, not the default. When you complete a planned phase or pass a milestone, the next action is the next phase — NOT a status report followed by "ping me to continue".

### The only five reasons to stop and ask

1. **User-territory operation** — Apple Developer Portal registration, OAuth/SSO login, payment authorization, anything requiring 2FA / Apple ID / human credentials the agent cannot supply
2. **Destructive operation needing explicit approval** — `rm -rf`, `git push --force`, dropping a database table, deleting cloud resources, anything under the user's `/careful` rules
3. **Genuinely ambiguous design choice** — two paths with materially different long-term consequences AND no signal in the spec / plan / prior conversation. ("I assume green but maybe blue?" is NOT this — that is over-asking.)
4. **Explicit checkpoint in the skill or plan** — e.g. an Approve/Revise gate, `executing-plans`' phase review
5. **Truly blocked** — missing information you cannot derive, a loop you cannot break, an error you cannot interpret after reasonable investigation (docs, search, the obvious fix first)

### Do NOT stop to

- ❌ Report completed work and ask "shall I continue with the next phase?"
- ❌ Check in at milestones because it feels considerate
- ❌ Ask "should I do X?" when X is obviously the next step in scope
- ❌ Wrap up early because the plan turned out larger than expected — finish it

If the next step is clearly within scope, DO IT. Report after it's done.

### Forbidden phrases

If one of these appears without a category-1-to-5 reason, you have failed the autonomy default: "Ping me when you want me to continue", "Let me know when you're ready for the next round", "Ready when you are", "Awaiting your go-ahead", "Si fra når jeg skal fortsette", "Bash-prompten din er fortsatt aktiv — si bare 'fortsett'". About to write one? If there is no real category-1-to-5 reason, delete the sentence and do the next thing instead.

### Status updates DURING work, not AS wait-states

- ✅ "BookmarkStore + 7 tests green. Moving to RecordingScanner now."
- ❌ "Phase 1 done. Here's a 12-row status table. Ready for UI when you say so."

When you DO legitimately stop (scope done, or a category-1-to-5 reason fires): state what's done in one or two sentences, name the specific blocker if any, and do NOT propose new work or invite continuation.
