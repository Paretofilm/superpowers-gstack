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

- **Task 4:** complete (commit `9a8c13a` + korrekthetsfiks `139dda6`, 51 suite = 48 + 3 pinning). `device_class(udid)` via `simctl list -j` → `INSET_TABLE`-nøkkel; ukjent device → `PreflightError` (fail-closed). FIKS: subagenten fanget 2 ekte stub-bugs verifisert mot ekte simctl — (a) `"pro-max"` falsk-positiv (notch 11/12/13 Pro Max → island) + redundant → slettet; (b) `"iphone-air"` falsk-negativ (Air har Dynamic Island) → lagt til. Island/notch-splitten nå pinnet (var helt utestet). ⚠️ FOR FINAL REVIEW: island er allowlist-per-generasjon — fremtidig `iPhone-18` resolver stille til notch (ingen test tvinger årlig edit); fail-closed beskytter kun ekte ikke-iPhone/iPad.

- **Task 5:** complete (commit `0be1d9a`, 55 suite = 51 − 3 gamle foreground + 7 nye). AXLabel-selvreferanse-oracle: `is_app_foreground(udid, baseline_app_label, baseline_full_width)` → frontmost `Application.AXLabel == baseline_app_label ∧ width ≥ 0.95×baseline`. Nye helpers `_describe_all_raw` + `_describe_all_settled` (>3 typede elementer, 8×2s, reiser `PreflightError` ved aldri-stabil — oracle fanger→False, Task 6 lar propagere→fail-closed). Fjernet `_on_home_screen`, `_process_running`, spotlight-pill, `_fake_run` (grep-zero bekreftet). AXLabel None → fail-closed False. ⚠️ TASK 7 MÅ FIKSE `cli.py:102` — kaller fortsatt gammel 2-arg-form i lazy lambda (suite grønn fordi aldri invokert). ⚠️ FOR FINAL REVIEW: 0.95-terskel + `>3`-boundary er utestede heuristikker (kalibreres ved Task 11 live-smoke); ubrukt `json`-import i test_preflight.py (harmløs).

- **Task 6:** complete (commit `71a3802`, 60 suite = 55 + 5). `preflight(udid, bundle_id, orientation)` 3-arg: terminate→launch→`_describe_all_settled`→verifiser frame-aspekt mot orientering (S5: setter IKKE, fail-closed «roter manuelt»)→`_validate_fullscreen` via skjermbilde-px/frame-pt = ren @2x/@3x (S6, droppet `_device_full_width`)→`table_insets` (S1, `safe_area_source="table"`). Fanger `baseline_app_label` (fail-closed hvis None). Nye helpers: `_terminate`, `_launch`, `_frame_matches_orientation`, `_screenshot_width_px` (PNG IHDR via struct), `_validate_fullscreen`, `_load_coords`. ⚠️ TASK 7 MÅ FIKSE `cli.py:73,95` — kaller gammel 2-arg `preflight()` (runtime). ⚠️ FINAL REVIEW: scale-heuristikk har én teoretisk false-accept (SM-vindu @ ~556pt på @2x → ratio 3.0); lav risiko. `_frame_matches_orientation` `>=` begge grener (kvadratisk matcher begge — benign).

- **Task 7:** complete (commit `4b259b7`, 63 suite = 60 + 3). cli.py: `--orientation {portrait,landscape}` default portrait; begge stier bruker `env["safe_area"]`; fjernet `TOP_INSET`/`BOTTOM_INSET` + `coords`-import (grep-zero). 3-arg `preflight()` på begge kallsteder. **KRITISK FIKS:** closure sender `env["baseline_app_label"]` (AXLabel), IKKE `args.bundle` (stubben hadde feil arg — ville aldri matchet → loop-exit på steg 1). F1 default-env seedet med orientation/device_class/safe_area_source. Inngangspunkt = wrapper `scripts/ios-visual-explore` (uv-script → `cli.main()`); `--orientation` verifisert via `--help`. cli.py har ingen `__main__`-guard, men trengs ikke (wrapper invokerer). ⚠️ FINAL REVIEW: `--dry-run` kjører nå full preflight (orientation/fullskjerm-validering + launch) — ikke lenger ren bivirkningsfri probe; defensibelt (trenger skjermbilde fra foregrunns-app), men en utvidelse.

- **Task 8:** complete (commit `d134eb2`, 64 suite = 63 + 1, gjort inline — triviell one-liner). `**Miljø:**`-linjen utvidet med orientation/device_class/safe-area-source via `.get()`+`_s()` (eldre env-dicts rendrer fortsatt grasiøst).

- **Task 9:** complete (commit `afdad05`, docs-only, inline). SKILL.md: `--orientation` i invoke-blokk + iPad-landskap-eksempel; ny «iPad and orientation»-seksjon (manuell rotasjon S5, fullskjerm-only S6, INSET_TABLE, AXLabel-oracle S7, settle-retry + cold-boot); «Known limitations» (orientering persisterer, Slide-Over-hull, ingen split/SM). Rettet doc-påstand: tapp utenfor safe-area **avvises** (loop.py:55,62), styres ikke.

- **Task 10:** complete (commit `741300d`, 65 suite = 43 Fase 1 + 22 Fase 2, inline). iPhone-portrett-regresjonstest: `iphone_notch` portrett-tabell (top=47≥44, bunn-inset=34≥20) holder samme ballpark som Fase 1s hardkodede (0,50,w,h-40).

- **FINAL MULTI-LENS REVIEW:** complete (self-pitfall + Codex GATE-PASS + GLM-5.2 architecture). 71 suite. 4 funn fikset: (1) landskap fullskjerm-validering — sortert-dim + samme-scale-begge-akser, lukket OGSÅ Stage-Manager-556pt-false-accept (`21f1a84`); (2) device_class fail-open → notch-allowlist + raise, + bonus 16e/17e-fiks (`531f4c2`); (3) truncated-PNG-guard, cross-house Codex+GLM (`cf65fcd`). 1 begrunnet KEEP: oracle settle-budsjett = navigation-vs-departure-disambiguator, dokumentert (`36a8654`) — live-smoke måler latens. 2 begrunnet DROP: iPhone-landskap-insets (utenfor Fase 2 testet scope), _load_coords klasse-identitet (pre-eksisterende, duck-typed, hele-kodebase-scope). Kost: GLM $0.07.

## Remaining
- ~~Task 3 (derive_insets)~~ — DEFERRED (S1, ikke levedyktig).
- **Task 11:** live-smoke iPad portrett + landskap (manuell rotasjon) + iPhone-portrett-regresjon. ⚠️ KREVER OPERATØR (manuell rotasjon) + paid Gemini-API. WATCH (fra review): per-steg oracle-latens / falsk `app_left_foreground`-abort (GLM Finding 1) — mål kjøretid + sjekk for tidlig abort.

## Lessons / gotchas
- iPad cold-boot: SpringBoard/UI tar ~30-60s etter "booted"; svart skjerm + tomt AX-tre til UI rendrer. Poll til describe-all gir >3 typede elementer.
- describe-all degenererer til 1 element (`DockFolderViewService` på hjem) under transisjoner — settle-retry obligatorisk.
- idb ui har ingen orientation/rotate/home-button som virker; `simctl terminate` returnerer til hjem.
