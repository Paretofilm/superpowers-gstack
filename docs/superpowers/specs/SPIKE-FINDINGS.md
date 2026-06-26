# SPIKE-FINDINGS — iOS Computer-Use Visual Explore (Fase 1, Task 1)

> Gate-funn fra Task 1. Verifiserer R1 (API-form), R4 (touch-egnethet), R7 (foreground-oracle)
> og idb-koordinatkonvensjon før resten av planen bygges. **Task 4, 7, 8, 9 justeres mot dette.**

**Rigg:** iPhone 17 Pro, iOS 26.5 (UDID `4FA4A85E-E97F-41BA-A3A7-1ED5FB2574F2`),
`idb` 1.x (companion auto-koblet), `google-genai` **2.10.0**, modell `gemini-3.5-flash`,
testapp = innebygd Innstillinger (`com.apple.Preferences`). Dato: 2026-06-26.

---

## Step 2 — idb tap + koordinatkonvensjon ✅

| Mål | Funn |
|-----|------|
| Skjermbilde-piksler | **1206 × 2622 px** (`xcrun simctl io <udid> screenshot`) |
| Logiske punkter | **402 × 874 pt** (fra `idb ui describe-all` Application-frame) |
| Backing scale | **3.0** (1206/402 = 2622/874 = 3.0; iPhone 17 Pro = @3x) |
| Tar `idb ui tap` punkter eller piksler? | **PUNKTER.** Tap på `(201,319)` pt (senter av "Generelt"-raden) navigerte korrekt inn til Generelt-skjermen. Piksel-tolkning ville bommet grovt. |

**Konsekvens:** koordinatpipelinen er `normalisert 0–1000 → punkter → idb tap`. Ingen
piksel/scale-konvertering trengs for selve tappet.

---

## Step 3 — computer_use API-form (faktisk SDK, ikke bare doc) ✅ + AVVIK

Verifisert med ett ekte kall + introspeksjon, ikke bare dokumentasjon.

### Request

```python
client.interactions.create(
    model="gemini-3.5-flash",
    input=[
        {"type": "text",  "text": MISSION},
        {"type": "image", "data": base64_png, "mime_type": "image/png"},
    ],
    tools=[{"type": "computer_use", "environment": "mobile",
            "enable_prompt_injection_detection": True}],
)
```

- **`client.interactions.create()`** — bekreftet (ikke `models.generate_content()`). SDK ≥ 2.7.0; vi har 2.10.0.
- `create(*, request=None, **body)` — kwargs (`model`, `input`, `tools`, `previous_interaction_id`) går inn i `**body`. Doc-formen er gyldig.
- `environment="mobile"` og `enable_prompt_injection_detection=True` godtatt.
- **Input-blokker:** `{"type":"text",...}` + `{"type":"image","data":<b64>,"mime_type":"image/png"}`.

### Response — **AVVIKER fra plan-antagelsen**

```json
{
  "status": "requires_action",
  "id": "v1_Ch...",
  "steps": [
    {
      "type": "function_call",
      "name": "click",
      "arguments": { "x": 450, "y": 365, "intent": "Tap on the 'Generelt' row." },
      "id": "idgmyxqj",
      "signature": "<opaque base64>"
    }
  ],
  "usage": { "total_tokens": 1241, ... }
}
```

| Felt | Faktisk | Plan antok |
|------|---------|------------|
| Handlingsliste | **`interaction.steps`** | `output`/flat |
| Handlingsnavn | `step["name"]` | `cu["name"]` ✓ |
| Koordinater | **`step["arguments"]["x"]` / `["y"]`** (nested) | `cu["x"]` / `cu["y"]` (flat) ✗ |
| Intent | `step["arguments"]["intent"]` | — |
| call_id | **`step["id"]`** | — |
| signature | `step["signature"]` (Gemini-3 thought-signatur) | — |
| Terminal-signal | **`interaction.status`** (`requires_action` → fortsett, `completed` → ferdig) | `action is None` ✗ |

- **Koordinater er 0–1000 normalisert mot PUNKT-rommet.** `(450,365)` → `450/1000*402=181 pt`, `365/1000*874=319 pt` = "Generelt"-raden. Treffer eksakt.

### function_result-chaining ✅

```python
client.interactions.create(
    model="gemini-3.5-flash",
    previous_interaction_id=prev.id,
    input=[{"type": "function_result", "name": name, "call_id": call_id,
            "result": [{"type": "text",  "text": json.dumps({"status": "success"})},
                       {"type": "image", "data": base64_png, "mime_type": "image/png"}]}],
    tools=[{"type": "computer_use", "environment": "mobile", ...}],
)
```

- Chaining via **`previous_interaction_id`** + `function_result` med **`call_id`** (= forrige `step["id"]`) godtatt.
- `signature` trengte **ikke** ekkoes tilbake for at result skulle godtas i ett steg. Den bør likevel **bevares/sendes** for fler-stegs tankekontinuitet (Gemini-3) — verifiser ved første reelle fler-stegs-løp.
- Etter at appen navigerte til Generelt returnerte R2 `status="completed"` (modellen anså oppdraget løst). **Completed-steget mangler `name`-feltet** → terminal-håndtering må gren på `status`, ikke på stegform.

---

## Step 4 — touch-egnethet (R4) ✅

Full round-trip bekreftet: modell-`click` → denormaliser mot punkter → `idb ui tap` → **appen
navigerte korrekt** (Generelt-celler "Om", "Språk og område", "VPN og enhetsadministrering" dukket
opp). Modellen emitterer `click` for tap. Action-navnerommet (mobil) er:
`click, type, scroll, drag_and_drop, press_key, take_screenshot, wait, go_back, long_press`.
`scroll` er kjerne-navigasjon (ikke `unsupported`) — som planen allerede antar.

---

## Step 5 — foreground-oracle (R7) ✅

To pålitelige signaler, ingen XCTest-bygg nødvendig for fase 1:

1. **Prosess lever:** `xcrun simctl spawn <udid> launchctl list | grep "UIKitApplication:<bundle>"`
   — forsvinner ved terminering/krasj. Skiller *kjørende* vs *død*, ikke forgrunn vs bakgrunn.
2. **Ikke-på-hjemskjerm:** `idb ui describe-all` reflekterer alltid **frontmost** app. Hjemskjerm
   har SpringBoard-signatur (custom_action `Appbibliotek` på ikonene) → `True` på hjem, `False`
   når mål-appen er fremme.

**Oracle (fase 1):** `is_app_foreground = prosess_lever(launchctl) AND NOT springboard_signatur(describe-all)`.
For et enkelt-mål-løp (vi launcher kun mål-appen) er dette tilstrekkelig: forlater appen forgrunnen
er det enten krasj (borte fra launchctl) eller hjem/app-switch (SpringBoard-signatur) — begge fanges.
**Kanonisk alternativ** (`XCUIApplication(bundleIdentifier:).state == .runningForeground`) krever
et bygd test-bundle → utsatt forbi fase 1.

---

## Step 7 (env-pitfall) — bekreftet LIVE ⚠️

Introspeksjonen logget *"Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY."* —
SDK-en plukker arvet `GOOGLE_API_KEY` automatisk. Spec'ens globale constraint (pop begge før
`Client()`-init og bruk Keychain-`gemini-api-key-paid`) er altså **empirisk nødvendig**, ikke bare
defensiv. Verifisert at pop + eksplisitt `api_key=` gir riktig (paid) nøkkel.

---

## Kost

~**1200–1300 tokens per steg** (bildet dominerer: ~1078 tok/skjermbilde, tekst ~10, thought ~117,
output ~36). 25-stegs løp ≈ 30k tokens på `gemini-3.5-flash` → brøkdel av en cent. Ikke en
budsjett-bekymring; bildet er den dominerende posten (relevant for dedup-gevinst, Task 5).

---

## Nødvendige plan-justeringer (FØR de byggene rører API-formen)

1. **Task 4 (`actions.adapt`) + Task 9 (`loop`):** les `cu["name"]` + **`cu["arguments"]["x"/"y"]`**
   (nested), ikke flat `cu["x"]`. Oppdater test-fixturene i Task 4 til nested `arguments`-form.
2. **Task 9 (`Turn`/`loop`):** terminal-deteksjon = **`interaction.status`** (`requires_action`
   vs `completed`), ikke `action is None`. Bær `call_id = step["id"]` og (anbefalt) `signature`
   videre i function_result. Chaining = `previous_interaction_id`.
3. **Task 3 (`coords.denormalize`) + Task 7 (`coordinate_space`):** denormaliser **direkte mot
   punkt-rommet** (402×874 fra `describe-all` Application-frame). Dette **eliminerer Pillow-dep og
   `_device_backing_scale()`-gjettingen** i Task 7 — les punkt-dimensjon fra describe-all i stedet
   for piksel-størrelse + scale. (Plan-formelen `px/scale` gir samme tall, men punkt-direkte er
   enklere og dropper en avhengighet.)
4. **Task 8 (`is_app_foreground`):** implementer kombinert launchctl + SpringBoard-signatur-oracle
   over (erstatter `NotImplementedError`-placeholderen).
5. **Task 10 (kritiker) / Task 9:** input-blokk-form `{"type":"text"}` + `{"type":"image","data","mime_type"}`;
   tool `{"type":"computer_use","environment":"mobile","enable_prompt_injection_detection":true}`.

Ingen av funnene velter arkitekturen (alt. A) eller fase-rekkefølgen — de strammer signaturene i
Task 3, 4, 7, 8, 9. **Gaten er grønn: bygg videre fra Task 2.**

---

## Addendum (runde 2) — scroll emitteres som `drag_and_drop` ⚠️

Fanget under bygging (ekte kall, scrollbar Generelt-skjerm). Oppdrag "Scroll down to see more
settings below" ga **ikke** `scroll`, men:

```json
{"name": "drag_and_drop",
 "arguments": {"start_x": 500, "start_y": 800, "end_x": 500, "end_y": 200,
               "intent": "Scroll down to reveal more settings below"},
 "id": "qps43mmd", "type": "function_call"}
```

- **Scrolling kommer som `drag_and_drop`** med **to punkter** (`start_x/start_y` → `end_x/end_y`),
  begge 0–1000 normalisert. Et dra fra y=800 → y=200 = swipe opp = scroll ned.
- `scroll` (med `{x,y,direction}`) kan fortsatt forekomme i andre kontekster, men `drag_and_drop`
  er det observerte for scroll-intensjon. Adapteren må håndtere **begge**.

**Konsekvens for plan:**
- **Task 4 (`adapt`):** `drag_and_drop` → `swipe`-primitiv med `{start_x,start_y,end_x,end_y}` fra
  `arguments`. Behold `scroll`→swipe defensivt. Begge leser fra nested `arguments`.
- **Task 7 (`executor.swipe`):** signatur tar **to punkter** `swipe(start: Point, end: Point)` →
  `idb ui swipe <x1> <y1> <x2> <y2>` (idb tar nettopp start+slutt). Erstatter punkt+retning-formen.
- **Task 9 (loop):** denormaliser **begge** endepunktene for `drag_and_drop`; safe-area-sjekk på
  begge. `click` denormaliserer ett punkt som før.
