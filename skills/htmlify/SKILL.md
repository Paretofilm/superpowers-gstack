---
name: htmlify
description: |
  Explain mode: a hand-made visual explainer page for a spec or plan, run
  automatically after each is written. Also offline HTML rendering of Markdown
  artefacts and per-directory dashboards.
---

# /htmlify

Two jobs:

- **Explain mode** (`/superpowers-gstack:htmlify explain <doc.md>`): a visual
  explanation page for a spec or plan, written by hand, with inline SVG diagrams and
  as little text as possible. It runs after every spec and plan. See
  [Explain mode](#explain-mode).
- **Rendering** (`bin/htmlify`): a Markdown artefact to a styled HTML companion, and a
  dashboard page per directory. Since 3.0.0 this is the **offline fallback**: when the
  Artifact tool is available, publish the artefact as a page with it instead (load the
  `artifact-design` skill first). Reach for it when there is no Artifact tool, or when
  the user explicitly asks for a local HTML file.

`styles/companion.css` is the style of the rendering job (Liquid Glass surfaces,
gradient-mesh backgrounds, dual theme). Explain mode has its own style,
`styles/explainer.css`, and never uses companion.css.

## Explain mode

A reader should understand the design from the pictures in two minutes, and open the
document only for detail. The page explains the document; it never adds to it.

**When.** After a spec (`docs/superpowers/specs/*.md`) or a plan
(`docs/superpowers/plans/*.md`) is finished: after its own self-review, before the user
is asked to review it (and after the review lenses, when they run on it), so the user
reviews with the page in front of them. Run it
without asking. The plugin's `PostToolUse` hook reminds the session when such a file is
written, and again if the document changes after its page was made; re-run then. Not
for progress files, handoffs or vibe specs.

**Start from the example.** `examples/explainer-example.html` is the shape of a finished
page (its content is invented). Copy its skeleton: the head, the top bar with the theme
button, the card pattern and the theme script. Replace everything else. The first
`<style>` is `styles/explainer.css` unchanged, comments and all; rules the page needs
beyond it go in a second `<style>`. The page stands alone: no linked stylesheet, no
script but the theme button, no web fonts.

**Shape.** Take the parts the document has, in this order, and skip the ones it lacks:
title (badge with the document type and date, the name, one line under), the problem
(one headline number or fact), the whole (one flow diagram), one card per part of the
design, the detail that is easy to get wrong, who does what, done when, worth knowing.
Write in the document's language. Every claim comes from the document; the footer
names the source file.

### Design rules

1. **One accent per card, and a badge on top of every card.** The card's first element
   is `<span class="tag t-<accent>">`, and the card's diagrams and `.key` use the same
   accent. Other colours inside a card carry meaning only: emerald for what works or is
   done, amber for caution, red only for the failure path.
2. **SVG for anything with order, time or distribution:** steps, flows, who hands what
   to whom, timelines, sums and splits. A bulleted list of steps is the failure this
   rule exists for. Every `<svg>` has `role="img"` and an `aria-label` that says what it
   shows. A wide drawing has a `viewBox` 960 wide and sits in `.scroll`.
3. **One insight per card, in the highlighted box** (`.key`): the one thing the reader
   must take away from that card, never two. Cards that only list (who does what, done
   when, worth knowing) need none.
4. **Tiles have an icon, a title and at most one line under it** (`.chip` with `.ic`,
   `<b>`, `<span>`). Anything longer belongs in the document, not on the page.
5. **No internal identifiers:** no task or requirement ids, commit shas, function, class
   or variable names, or paths the reader never meets. A command the reader types, or a
   file they open, may appear in `<code>`.
6. **Light and dark theme.** Colours come from the tokens (`var(--cyan)`,
   `var(--line)`, …), never as hex values in an SVG or an inline style, so both themes
   work. Keep the theme button.

### Where it goes

Read `.gstack/explainer` at the project root: `local` or `artifact`. No file means
`local`. `/superpowers-gstack:adapt` asks the question once and writes the file.

- **`local`**: write `<the document's folder>/<its name>.html`, next to the document,
  and commit it with the document. After the check, open it with `open <page>`.
- **`artifact`**: write the page to the scratchpad, check it, then publish it with the
  Artifact tool. Load `artifact-design` first, as the tool requires: explainer.css
  already meets its page contract (tokens on `:root`, the dark-mode guards, a body
  background, phone width), so keep the explainer's look. Republish a changed document
  from the same file path, so the link stays.

Then give the user one line: the path or the link.

### Last step, always: the check

```bash
"$SKILL_DIR/bin/explain-check" <page.html>
```

It reads the file against the rules above, then loads the page in gstack's headless
browser at desktop and phone width and measures text that is clipped, runs out of its
box, is cut by a drawing's edge, overlaps other text, or has a line drawn through it.
It screenshots the whole page (light, dark, phone) and every card, and prints the paths.

| Exit | Meaning | Do this |
|---|---|---|
| 0 | Clean | Look at the screenshots, then open or publish |
| 1 | `FINDING` lines | Fix every one and run it again |
| 4 | The page could not be read | Check the path |
| 5 | No browser (`GSTACK_BROWSE` unset and gstack's `browse` not installed), or it failed | Say so; take full-page screenshots with another browser tool (for example Playwright's `browser_take_screenshot` with `fullPage`) and do the visual check on those |

A `WARNING identifier` line is either rewritten or confirmed as a word the reader
actually sees. Then **read the screenshots**: the full pages for the whole, the cards
for detail, for what measuring cannot see: a line through an icon, text unreadable in
the dark theme, a diagram that says nothing. The page is opened or published only after
a clean run and that look. A page whose check did not run is never presented as
checked.

## How to invoke

The skill directory is the "Base directory for this skill" shown when the skill loads.
The wrapper `bin/htmlify` self-locates and runs from any cwd:

```bash
"$SKILL_DIR/bin/htmlify" <path-to-md>            # → <dir>/.superpowers-html/<name>.html
"$SKILL_DIR/bin/htmlify" <path-to-md> --open     # also open it in the default browser (macOS)
"$SKILL_DIR/bin/htmlify" dashboard <dir>         # → <dir>/.superpowers-html/index.html
```

First run per install location: `cd "$SKILL_DIR" && bun install` (the wrapper prints
this exact command and exits 5 if deps are missing; exit 5 also means `bun` is absent).

The open flag opens the file in the user's default browser and touches nothing else.
It never closes windows.

### Flags

- `--plan <plan.json>` — richer layout driven by a rendering plan (see below)
- `--no-clobber` — skip the render if the HTML is newer than the MD
- `--force-rebuild` — render even under `--no-clobber`

## Rendering plan (optional)

Without `--plan` the default template renders the Markdown as structured cards. With a
plan you can map sections to components: `comparison-matrix`, `flowchart-svg`,
`pullquote`, `callout-box`, `stats-bar`, `two-column`, `expandable`, `diff-card`, and a
`feedback_panel` whose answers copy to the clipboard as a prompt for the next session.
Write the plan in this session (no API call), then pass it with `--plan`.

```json
{
  "version": 1,
  "sections": [
    {"heading": "Approaches Considered", "treatment": "comparison-matrix",
     "data": {"items": [{"title": "Option A", "pros": ["…"], "cons": ["…"], "effort": "1d", "risk": "low"},
                        {"title": "Option B", "pros": ["…"], "cons": ["…"], "highlighted": true}]}},
    {"heading": "Architecture", "treatment": "flowchart-svg",
     "data": {"orientation": "LR",
              "nodes": [{"id": "a", "label": "Input"}, {"id": "b", "label": "Process", "emphasis": true}],
              "edges": [{"from": "a", "to": "b", "label": "transform"}]}}
  ],
  "pullquotes": [{"text": "…", "attribution": "…", "after_section": "Problem Statement"}],
  "feedback_panel": {"enabled": true, "premises": ["P1"], "approaches": ["A1"],
                     "custom_questions": [{"id": "q1", "label": "Did this layout help?", "type": "radio", "options": ["yes", "no"]}]}
}
```

| Treatment | Data |
|---|---|
| `comparison-matrix` | `{items: [{title, summary?, pros?, cons?, effort?, risk?, highlighted?}]}` |
| `flowchart-svg` | `{nodes: [{id, label, shape?, emphasis?}], edges: [{from, to, label?}], orientation?: "TB"\|"LR"}` |
| `pullquote` | `{text, attribution?}` |
| `callout-box` | `{level?: "info"\|"warn"\|"insight"\|"danger", title?, body}` |
| `stats-bar` | `{items: [{label, value, delta?, trend?}]}` |
| `two-column` | `{left: {heading?, body}, right: {heading?, body}}` |
| `expandable` | `{summary, body, open?}` |
| `diff-card` | `{title?, before: {label?, content}, after: {label?, content}}` |

Section headings in the plan match the Markdown H2s case- and whitespace-insensitively;
a plan section with no matching H2 renders as a new section.

## Frontmatter types

`type: design-doc` (office-hours), `type: handoff` (context-handoff), `type: plan`
(autoplan); anything else renders through the generic template with a banner.

## Exit codes

0 success · 1 usage error · 2 schema validation failure · 3 Markdown parse error ·
4 I/O error · 5 setup error (bun or deps missing)

## Development

```bash
cd skills/htmlify && bun install && bun test
```
