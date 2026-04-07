# Fix Test Feedback — Implementation Plan

**Status: COMPLETED** (2026-04-07)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 actionable issues found during the todo-cli test of the superpowers-gstack workflow: broken plugin discovery, missing directory guidance, weak small-project guidance, and buried design-doc handoff tip.

**Architecture:** All changes are documentation and script edits in the superpowers-gstack repo. No new files except marketplace config. Task 1 fixes the critical plugin discovery bug. Tasks 2-4 are independent manual/skill edits.

**Tech Stack:** Bash (install script), Markdown (manual, skills, README), JSON (marketplace config)

---

### Task 1: Fix plugin discovery via marketplace registration

The `install-plugin.sh` script only creates a symlink in `~/.claude/plugins/`, but Claude Code uses `installed_plugins.json` as its plugin registry. The skill never appears in the available skills list.

**Fix:** Add superpowers-gstack to the kjetil-plugins marketplace AND update install instructions to use `/plugin install`. Keep the symlink script as a dev-only convenience but make marketplace the primary install path.

**Files:**
- Modify: `~/Developer/claude-plugins/kjetil-marketplace/.claude-plugin/marketplace.json`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/scripts/install-plugin.sh`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/README.md:41-73`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/superpowers-gstack-workflow-manual.md:30-50`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/CLAUDE.md` (update plugin install note)

- [ ] **Step 1: Add superpowers-gstack to marketplace.json**

Edit `~/Developer/claude-plugins/kjetil-marketplace/.claude-plugin/marketplace.json` — add a new entry to the `plugins` array:

```json
{
  "name": "superpowers-gstack",
  "description": "Setup and configure the Superpowers + GStack combined workflow for any project type",
  "source": {
    "source": "url",
    "url": "https://github.com/Paretofilm/superpowers-gstack.git"
  }
}
```

- [ ] **Step 2: Update install-plugin.sh to be dev-only with marketplace instructions**

Replace the contents of `scripts/install-plugin.sh` with:

```bash
#!/bin/bash
# Install the superpowers-gstack plugin
#
# Recommended: install via marketplace (proper Claude Code registration)
# Dev mode: creates a symlink for local development (skills won't appear
# in the available skills list — use --dev flag explicitly)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.claude/plugins"
LINK_NAME="superpowers-gstack"
LINK_PATH="$PLUGIN_DIR/$LINK_NAME"

if [ "${1:-}" = "--dev" ]; then
  # Dev mode: symlink for local iteration (skills won't be discoverable)
  mkdir -p "$PLUGIN_DIR"

  if [ -L "$LINK_PATH" ]; then
    current_target=$(readlink "$LINK_PATH")
    if [ "$current_target" = "$REPO_DIR" ]; then
      echo "Dev symlink already in place."
      echo "  $LINK_PATH -> $REPO_DIR"
      exit 0
    else
      echo "Updating dev symlink (was: $current_target)"
      rm "$LINK_PATH"
    fi
  elif [ -e "$LINK_PATH" ]; then
    echo "Error: $LINK_PATH exists but is not a symlink. Remove it manually."
    exit 1
  fi

  ln -s "$REPO_DIR" "$LINK_PATH"
  echo "Dev symlink created:"
  echo "  $LINK_PATH -> $REPO_DIR"
  echo ""
  echo "Note: Skills won't appear in the available skills list."
  echo "For full functionality, install via marketplace instead (see README)."
  exit 0
fi

# Default: print marketplace install instructions
echo "Install superpowers-gstack via the Claude Code marketplace:"
echo ""
echo "  1. In Claude Code, run:"
echo "     /plugin marketplace add kjetilge/kjetil-claude-marketplace"
echo "     /plugin install superpowers-gstack@kjetil-plugins"
echo ""
echo "  2. Restart Claude Code"
echo ""
echo "  3. Verify with: /plugin list"
echo ""
echo "For local development, use: $0 --dev"
```

- [ ] **Step 3: Update README.md install instructions**

In `README.md`, replace the "Install this plugin" section (lines ~54-60) with:

```markdown
### 2. Install this plugin

```
# In Claude Code:
/plugin marketplace add kjetilge/kjetil-claude-marketplace
/plugin install superpowers-gstack@kjetil-plugins
```

Restart Claude Code after installation.
```

- [ ] **Step 4: Update manual install instructions**

In `superpowers-gstack-workflow-manual.md`, replace the routing plugin install block (lines ~42-46) with:

```markdown
# Routing plugin (in Claude Code)
/plugin marketplace add kjetilge/kjetil-claude-marketplace
/plugin install superpowers-gstack@kjetil-plugins
```

Remove the `./scripts/install-plugin.sh` line from the Quick Start. Keep `./scripts/setup-hooks.sh` as a separate step.

- [ ] **Step 5: Update CLAUDE.md plugin install note**

In `CLAUDE.md`, update the "Plugin" section to mention marketplace installation as the primary method:

```markdown
## Plugin

This repo is also a Claude Code plugin (`superpowers-gstack`). The skill `setup-routing` generates tailored CLAUDE.md files for new projects.

- Install via marketplace: `/plugin marketplace add kjetilge/kjetil-claude-marketplace` then `/plugin install superpowers-gstack@kjetil-plugins`
- Dev mode: `./scripts/install-plugin.sh --dev` (creates symlink, skills won't be discoverable in the skills list)
```

- [ ] **Step 6: Commit marketplace and install changes**

```bash
cd ~/Developer/claude-plugins/kjetil-marketplace
git add .claude-plugin/marketplace.json
git commit -m "feat: add superpowers-gstack to marketplace"
git push

cd ~/Developer/superpowers-gstack
git add scripts/install-plugin.sh README.md superpowers-gstack-workflow-manual.md CLAUDE.md
git commit -m "fix: switch to marketplace installation for plugin discovery

Symlink-only install doesn't register in installed_plugins.json,
so skills are never discoverable. Marketplace install fixes this."
```

---

### Task 2: Add "run from project directory" guidance

Skills and GStack preambles detect project context from the current working directory. Running from a different directory causes wrong project slug, wrong design doc location, and wrong CLAUDE.md detection.

**Files:**
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/superpowers-gstack-workflow-manual.md`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/skills/setup-routing/SKILL.md`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/skills/adapt/SKILL.md`
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/README.md`

- [ ] **Step 1: Add prerequisite to manual Quick Start**

In `superpowers-gstack-workflow-manual.md`, after the "Three steps to get going" line (line 28) and before "### 1. Install the frameworks", add:

```markdown
> **Important:** Always start Claude Code from your project directory (`cd my-project && claude`). GStack and the routing skills detect project context from the working directory. Running from a different directory causes wrong project detection, misplaced design docs, and incorrect CLAUDE.md checks.
```

- [ ] **Step 2: Add directory check to setup-routing SKILL.md**

In `skills/setup-routing/SKILL.md`, insert after the "Invoke this skill with" line (line 10) and before the "**Important:** If the project already has..." line:

```markdown
**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:setup-routing` again.
```

- [ ] **Step 3: Add directory check to adapt SKILL.md**

In `skills/adapt/SKILL.md`, insert after the "Invoke this skill with" line (line 10) and before "## Process":

```markdown
**Directory check:** Verify that Claude Code's working directory is the target project. If the current directory appears to be a different project (e.g., the superpowers-gstack repo itself rather than the user's project), STOP and tell the user:

> You're currently in `[cwd]`. This skill needs to run from your target project directory. Start a new Claude Code session:
> ```
> cd /path/to/your-project && claude
> ```
> Then run `/superpowers-gstack:adapt` again.
```

- [ ] **Step 4: Add note to README Quick Start**

In `README.md`, after "Restart Claude Code after installation." (line ~62) and before "### 3. Set up your project", add:

```markdown
**Important:** Start Claude Code from your project directory before running setup:

```bash
cd ~/Developer/my-project
claude
```
```

- [ ] **Step 5: Add to appendix troubleshooting**

In `appendix-reference.md`, in the Troubleshooting section, add a new entry:

```markdown
### Wrong project detected / design docs filed under wrong project

**Symptom:** GStack detects the wrong project slug (e.g., `Paretofilm-superpowers-gstack` instead of your project). Design docs are saved under `~/.gstack/projects/` with the wrong name. `/review` checks the wrong CLAUDE.md.

**Cause:** Claude Code was started from a different directory than the target project.

**Fix:** Start a new Claude Code session from the project directory:

```bash
cd /path/to/your-project
claude
```

Both GStack and the routing skills detect project context from the working directory. There is no way to override this mid-session.
```

- [ ] **Step 6: Commit directory guidance changes**

```bash
git add superpowers-gstack-workflow-manual.md skills/setup-routing/SKILL.md skills/adapt/SKILL.md README.md appendix-reference.md
git commit -m "docs: add explicit 'run from project directory' guidance

GStack and routing skills detect context from cwd. Running from
a different directory causes wrong project slug and misplaced artifacts."
```

---

### Task 3: Strengthen small-project guidance

Every skill runs full ceremony regardless of project complexity. The manual says "skip Phase 1 for small projects" but the guidance is too weak — users need an explicit fast-path scenario.

**Files:**
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/superpowers-gstack-workflow-manual.md`

- [ ] **Step 1: Strengthen Phase 1 "When to skip" guidance**

In `superpowers-gstack-workflow-manual.md`, replace the existing "When to skip" line (line 165):

```markdown
**When to skip:** Bug fixes, small refactors, or tasks where scope is already clear. Jump to Phase 2.
```

With:

```markdown
**When to skip:** Bug fixes, small refactors, tasks where scope is already clear, or small projects (< 5 tasks, buildable in under 30 minutes). For these, jump directly to Phase 2. Office-hours adds ~10 minutes of ceremony that won't pay off for simple work.
```

- [ ] **Step 2: Add "Small Project" scenario to Common Scenarios**

In `superpowers-gstack-workflow-manual.md`, after the "### Small Feature (Skip Planning)" section (around line 393), add a new scenario:

```markdown
### Tiny Project (CLI Tool, Script, Single-Purpose App)

For projects with fewer than 5 tasks — small CLI tools, scripts, single-file utilities:

```
/superpowers:brainstorming         → 2-3 clarifying questions, adopt quickly
/superpowers:writing-plans         → TDD task breakdown
/superpowers:executing-plans       → Inline execution (no subagents needed)
# Tests passing = spec compliance. Skip per-task reviews.
/review                            → Manual diff review (skip specialists for < 200 LOC)
/ship                              → Create PR
```

**What to skip and why:**
- **Phase 1 entirely** — Office-hours, CEO/eng review add ~10-15 min of ceremony for a project specifiable in one sentence
- **Subagent-driven development** — Use `/superpowers:executing-plans` instead; subagent dispatch overhead isn't worth it for < 5 tasks
- **Per-task SDD reviews** — Passing tests ARE the spec compliance check for simple tasks
- **Review specialists** — For diffs under 200 lines of actual code, run the core `/review` and skip specialist dispatch (security, performance, etc.)
- **`/clear` between phases** — Not needed; context won't overflow for a 30-minute project
```

- [ ] **Step 3: Add quick-path row to Quick Start table**

In `superpowers-gstack-workflow-manual.md`, in the Quick Start "Start working" table (around line 68-78), add a row:

```markdown
| Small project (< 5 tasks) | `/superpowers:brainstorming` → skip Phase 1 |
```

- [ ] **Step 4: Commit small-project guidance**

```bash
git add superpowers-gstack-workflow-manual.md
git commit -m "docs: add explicit small-project fast path

Small projects (< 5 tasks) should skip Phase 1, use executing-plans
instead of SDD, and skip per-task reviews. Tests = spec compliance."
```

---

### Task 4: Make design-doc handoff more visible

After office-hours produces a design doc, brainstorming asks similar questions. The "adopt the design as-is" tip exists but is buried in Phase 2. Users miss it.

**Files:**
- Modify: `/Users/kjetilge/Developer/superpowers-gstack/superpowers-gstack-workflow-manual.md`

- [ ] **Step 1: Upgrade the Phase 1→2 transition guidance**

In `superpowers-gstack-workflow-manual.md`, replace the existing "Transition to Phase 2" section (lines 178-189):

```markdown
### Transition to Phase 2

When you `/clear` before Phase 2, all conversation context is lost. Bridge the gap:

1. Save key decisions before clearing (ask GStack to write to `docs/architecture-decisions.md`)
2. Reference the artifacts when starting Phase 2:

```
/clear
/superpowers:brainstorming
I need to implement the notification service. Key architecture 
decisions are in docs/architecture-decisions.md — read that first.
```
```

With:

```markdown
### Transition to Phase 2

When you `/clear` before Phase 2, all conversation context is lost. Bridge the gap:

1. Save key decisions before clearing (ask GStack to write to `docs/architecture-decisions.md`)
2. Reference the artifacts when starting Phase 2:

```
/clear
/superpowers:brainstorming
I need to implement the notification service. Key architecture 
decisions are in docs/architecture-decisions.md — read that first.
```

> **If Phase 1 produced a design doc:** Tell brainstorming to "adopt the design as-is" — this skips redundant questioning about scope and approach that office-hours already answered. Brainstorming will still add technical clarifications (storage, libraries, patterns) but won't re-tread product decisions.
>
> ```
> /superpowers:brainstorming
> Adopt the design as-is from the Phase 1 design doc at
> ~/.gstack/projects/<slug>/design.md — focus on technical 
> implementation details only.
> ```
```

- [ ] **Step 2: Add the tip to the "New Feature (Full Workflow)" scenario**

In `superpowers-gstack-workflow-manual.md`, in the "New Feature (Full Workflow)" scenario (around line 353-372), after the `/clear` line and before `/superpowers:brainstorming`, add a comment:

```
  → Save key decisions to docs/architecture-decisions.md
/clear
/superpowers:brainstorming         → "Adopt the design as-is" if office-hours produced a design doc
/superpowers:writing-plans         → Break into TDD tasks
```

- [ ] **Step 3: Commit design-doc handoff changes**

```bash
git add superpowers-gstack-workflow-manual.md
git commit -m "docs: make design-doc handoff tip more visible

Move 'adopt the design as-is' from buried tip to prominent callout
in the Phase 1→2 transition and the full workflow scenario."
```
