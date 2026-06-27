# Progress — iOS Computer-Use Visual Explore, Fase 2 (iPadOS)

Plan: `docs/superpowers/plans/2026-06-27-ios-computer-use-phase2-ipados.md`
Spec: `docs/superpowers/specs/2026-06-27-ios-computer-use-phase2-ipados-design.md`
Spike: `docs/superpowers/specs/SPIKE-FINDINGS.md` (Fase 2 addendum, commit `d96ae02`)

## Meta
- **Working dir:** `/Users/kjetilge/Developer/superpowers-gstack-phase2-ipados` (git worktree, branch `feat/ios-computer-use-phase2-ipados`, base = origin/main 4fd9282 @ 2.19.0)
- **Test:** `python3 -m pytest tests/unit/computer_use/ -q` (43 Fase 1-tester grønne på base)
- **iPad-sim:** iPad Pro 11-inch (M5), iOS 26.5, UDID `87BAE6A6-2750-4254-A25A-F2CFFF3226BC` (booted)
- **iPhone-sim (regresjon):** iPhone 17 Pro iOS 26.5, UDID `4FA4A85E-E97F-41BA-A3A7-1ED5FB2574F2`
- **Testapp:** Settings (`com.apple.Preferences`) — system-app, ingen egen build nødvendig

## SPIKE-deltas å tre inn i hver brief (fra addendum)
- **S1:** describe-all har ingen status-bar/home-indicator → `INSET_TABLE` PRIMÆR; derive_insets DROPPET fra Fase 2.
- **S5:** ingen programmatisk rotasjon → preflight VERIFISERER frame-aspekt vs `--orientation`, fail-closed; operatør roterer manuelt.
- **S6:** frame 834×1210 per-modell, @2x → valider fullskjerm via skjermbilde-bredde/scale ≈ frame-bredde, ikke hardkodet `_device_full_width`.
- **S7:** ingen bundleID → oracle bruker `Application.AXLabel`-selvreferanse (`baseline_app_label` fanget ved launch); subsumerer hjem-deteksjon; fjern `_on_home_screen`/spotlight-pill.
- **Tverrgående:** describe-all flaky → settle-retry-til-stabilt (>3 typede elementer) i ALLE preflight/oracle describe-all-kall. loop.py urørt.

## Completed
- **Task 1 (SPIKE):** complete (commit `d96ae02`). Gate grønn — 5 antagelser downgradet til implementerbare fallbacks, arkitektur intakt.
- **Task 2:** complete (commit `e244414`, TDD rød→grønn, 46 suite = 43 baseline + 3 nye). `INSET_TABLE` + `table_insets` appended; `denormalize`/`in_safe_area`/`SafeArea` urørt; `KeyError` på ukjent device_class er tilsiktet (Task 7 mapper → `PreflightError`). ⚠️ FOR FINAL REVIEW: inset-verdiene er HIG-hypoteser, ikke pinnet av testen (`iphone_island` landskap tester kun `left>0 ∧ right<w`); visuell verifisering ved Task 11. iPad landskap = portrett `(0,24,0,20)` (ingen side-insets — korrekt, iPad har ingen notch/island).

## Remaining
- ~~Task 3 (derive_insets)~~ — DEFERRED (S1, ikke levedyktig).
- **Task 4:** device_class (for INSET_TABLE-oppslag; fail-closed ukjent).
- **Task 5:** oracle via AXLabel-selvreferanse + settle-retry; fjern _on_home_screen. Erstatt 3 eksisterende 2-arg-tester.
- **Task 6:** preflight — verifiser orientering (ikke sett), baseline via skjermbilde/scale, fang baseline_app_label, settle-retry, bygg SafeArea fra table_insets.
- **Task 7:** cli — --orientation, env["safe_area"], foreground-closure med baseline_app_label + baseline_full_width.
- **Task 8:** report — utvid Miljø-linjen (orientation/device_class/safe_area_source).
- **Task 9:** SKILL.md — iPad-docs, --orientation (operatør-roterer), kjente begrensninger.
- **Task 10:** full suite grønn + iPhone-portrett-regresjon.
- **Task 11:** live-smoke iPad portrett + landskap (manuell rotasjon) + iPhone-portrett-regresjon.

## Lessons / gotchas
- iPad cold-boot: SpringBoard/UI tar ~30-60s etter "booted"; svart skjerm + tomt AX-tre til UI rendrer. Poll til describe-all gir >3 typede elementer.
- describe-all degenererer til 1 element (`DockFolderViewService` på hjem) under transisjoner — settle-retry obligatorisk.
- idb ui har ingen orientation/rotate/home-button som virker; `simctl terminate` returnerer til hjem.
