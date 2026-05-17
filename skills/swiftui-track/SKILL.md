---
name: swiftui-track
description: |
  Declare this project as SwiftUI (iOS / macOS / both). Writes
  .gstack/track. Required upstream of swiftui-design-consultation;
  invoked automatically by office-hours when native intent is inferred
  (via CLAUDE.md routing rule), and as Phase 0 self-bootstrap by
  swiftui-design-consultation if the marker is missing. Idempotent —
  re-invocation lets the user change the value.
  Use when starting a new SwiftUI project, when an existing project
  should be declared as native, or to change the platform target.
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /superpowers-gstack:swiftui-track

Declare this project's SwiftUI platform target. Writes one file:
`.gstack/track` containing `ios`, `macos`, or `both`. That marker is
read by:
- The dual-track CLAUDE.md routing rule (so `/design-consultation`
  dispatches to the SwiftUI variant)
- `swiftui-design-consultation` Phase 0 (so it knows which platforms
  to declare in the generated `Package.swift`)
- Future skills: `swiftui-qa`, `swiftui-design-review`, `swiftui-ship`

Marker absence is treated as `web` (gstack backwards-compatible default).

## Workflow

### Step 1: Read current marker

```bash
mkdir -p .gstack
CURRENT=""
if [ -f .gstack/track ]; then
  CURRENT=$(cat .gstack/track | tr -d '[:space:]')
fi
echo "CURRENT_TRACK: ${CURRENT:-none}"
```

### Step 2: Ask the platform question

Use AskUserQuestion with this brief. If `CURRENT_TRACK` is one of
`ios | macos | both`, mark that option `(recommended)` so keeping the
current value is the one-click path. Otherwise mark `iOS only` as
`(recommended)`.

```
D1 — Which platform target does this project ship to?
Project/branch/task: declaring SwiftUI track for this repo
ELI10: This is a one-time project decision. It tells the rest of the
  plugin whether you're building an iPhone/iPad app, a Mac app, or
  both — so generated Swift Package files and design defaults match.
Stakes if we pick wrong: Package.swift declares wrong platforms; you'll
  need to manually edit it later. Other than that, no permanent damage —
  re-running this skill changes the value cheaply.
Recommendation: <see logic above>
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) iOS only
  ✅ Most common case for new projects; smallest Package.swift
  ✅ iPadOS works automatically via iOS target (no separate declaration)
  ❌ No macOS companion app — you'd have to add it later by re-running
B) macOS only
  ✅ Right for menu-bar tools, productivity apps, system utilities
  ✅ Liquid Glass strategy tuned for macOS chrome conventions
  ❌ No phone/tablet — narrows reach
C) Both iOS + macOS
  ✅ Cross-platform Swift Package with `#if os(...)` where needed
  ✅ Maximum reach; one design system serves both
  ❌ More platform-specific code surfaces; longer compile times
Net: Pick based on where you'll first ship, not where you might
   eventually ship — easy to add platforms later by re-running this
   skill.
```

### Step 3: Write the marker

Write the chosen value (`ios`, `macos`, or `both`) to `.gstack/track`:

```bash
echo "$CHOICE" > .gstack/track
```

### Step 4: Report status

Print one of:
- `Track set: <value>` (new file written)
- `Track changed: <old> → <new>` (overwrite of existing different value)
- `Track already set: <value> (no change)` (user chose same as current)

Then suggest:
```
Next: /superpowers-gstack:swiftui-design-consultation
```

That's the whole skill. ~50 lines including this prose.

## Notes

- `.gstack/track` is committed to the repo (project-level decision,
  not per-developer). The plugin's `.gitignore` advice does NOT
  exclude this file.
- Re-invocation is supported and expected. The current value is
  marked `(recommended)` so the symmetric flow lets the user either
  keep or change.
- If `.gstack/` does not exist, it is created. The skill never
  writes outside `.gstack/`.
