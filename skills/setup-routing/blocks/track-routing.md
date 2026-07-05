## Track-aware routing (dual-track) <!-- gstack-routing-v1 -->

This project follows superpowers-gstack's dual-track convention.
Track is declared in `.gstack/track` (`ios` | `macos` | `both`).
Missing marker = `web` (gstack default).

### When user invokes /office-hours (no namespace)

Intercept and invoke `/superpowers-gstack:office-hours-track-aware`
instead. The wrapper runs upstream `/office-hours` for the brainstorm,
then handles:
- Track inference from the brainstormed idea (native vs web signals)
- Inline platform question (iOS/macOS/both) if native or ambiguous, only
  when `.gstack/track` is absent
- Design-doc relocation from gstack defaults into repo `docs/`
- `/htmlify --open` rendering BEFORE the approval gate (so the user can
  read the rich HTML before deciding)
- Approve / Revise / Restart gate after they've seen the rendered HTML
- Suggests `/superpowers-gstack:swiftui-design-consultation` next for
  native tracks

User can bypass by typing `/office-hours` (gstack) directly — but for
all dual-track projects, prefer the wrapper.

### When user invokes /design-consultation (no namespace)

Read `.gstack/track`:
- `ios` / `macos` / `both` → invoke `/superpowers-gstack:swiftui-design-consultation`
- Absent or `web` → invoke `/design-consultation` (gstack)

User can always bypass by typing the namespaced version directly.
