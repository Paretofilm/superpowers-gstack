---
nummer: 8
tag: Spor: Web og Python
tittel: Web, Python og pipelines
aksent: cyan
oppdatert: 2026-10-12
bruk: prosjektet er en nettside, et Python-program eller en pipeline (en kjede av trinn som tar en fil inn og gir en fil ut)
ferdig: du vet hvilke ekstra skills som passer, og du har sett en ekte kjøring mot ekte inndata
---

### Samme kjerne, andre verktøy

Kjernen er den samme som i Swift-sporet ([se figuren i kapittel 7](#k7)). Det som skiller, er verktøyene på sidene. Et prosjekt uten filen `.gstack/track` regnes som web, så et Python-prosjekt havner her uten at du gjør noe.

### Hva et web- eller pipelineprosjekt legger til

Alle skillene under er GStacks egne, ikke pluginens. Beskrivelsene er hentet fra skillenes egne filer.

| Skill | Hva den gjør | Bruk den når |
|---|---|---|
| `/qa` | Tester og retter feil i nettleser, API (grensesnittet programmer snakker med hverandre gjennom), kommandolinje, jobber og webhooks (anrop andre tjenester sender til programmet ditt), og lagrer hver bekreftede rettelse som egen commit | Du vil ha «test og rett», eller en funksjon er klar til å testes |
| `/qa-only` | Samme testing, men skriver bare en rapport med steg for å gjenta feilen. Den retter ingenting | Du vil ha en feilrapport uten kodeendringer |
| `/browse` | Styrer en ekte nettleser: åpner en side, leser den, klikker gjennom et forløp, tar skjermbilder og leser feilmeldinger fra konsollen | Du vil at Claude skal se en side slik du ser den |
| `/design-review` | Ser etter ujevnt utseende, avstander og visuelt hierarki med en designers øye, og retter i koden med skjermbilder før og etter | Siden fungerer, men ser ikke riktig ut |
| `/cso` | Sikkerhetsrevisjon. Uten flagg er den statisk: den leser koden og kjører ikke programmet | Koden rører nøkler, eksterne tjenester eller tekst du ikke stoler på |
| `/investigate` | Feilsøking i fire faser: undersøk, analyser, still en hypotese, rett. Regelen er at ingenting rettes før årsaken er funnet | Noe feiler i en ekte kjøring og du vet ikke hvorfor |

Når `/cso` passer, står i rutingtabellen til KvitteriAi: den kjøres før `/review` når koden rører nøkler, eksterne tjenester eller upålitelig tekst. I loggene fra seks prosjekter ble `/qa` brukt 0 ganger (målt 10. oktober 2026), så den er et forslag, ikke en vane. Tallet er et øyeblikksbilde, ikke en egenskap ved verktøyet.

`/browse` bruker først Aside, nettleseren din med innloggingene dine, så Claude ser det du ser i en fane. Mangler Aside, bruker den gstacks egen nettleser uten skjerm. Claude får altså se det du er logget inn på.

### Verktøy som lar Claude se nettet

Tre verktøy gjør at Claude kan se nettet. Alle er MCP-verktøy eller utvidelser (MCP, Model Context Protocol, er standarden som kobler verktøy til Claude).

- Playwright styrer en nettleser fra Claude: åpne en side, klikke, skrive i skjemaer, ta skjermbilde (verktøyets egen beskrivelse; verktøyene heter blant annet `browser_navigate`, `browser_click` og `browser_take_screenshot`). De tre prosjektene under nevner det ikke i CLAUDE.md-filene sine (sjekket 12. oktober 2026), så det finnes ikke et eksempel derfra.
- Claude in Chrome styrer din egen Chrome, med innloggingene dine (beskrivelsen av utvidelsen i Claude Code). KvitteriAi (en Swift-kommandolinje som finner bilag til banktransaksjoner) bruker det i skillen `hent-fakturaer` (`.claude/skills/hent-fakturaer/SKILL.md` i prosjektet): du logger inn selv, Claude leser fakturalistene på leverandørenes nettsider, laster ned og legger fakturaen inn. Koden avgjør om den blir et bilag. Før noe åpnes, sier skillen hvilke nettsteder du må være innlogget på, og at Claude leser beløp, datoer, firmanavn og fakturaadresse. Så venter den på at du skriver «klar».
- firecrawl henter en side og gir innholdet som tekst, og søker på nettet (verktøyets egen beskrivelse). Heller ikke det står i de tre prosjektenes CLAUDE.md-filer (sjekket 12. oktober 2026).

Ingen av de tre prosjektene er selv nettsteder. De bruker verktøyene utenfra, og to av dem går andre veier til samme mål:

- Resolve-ai-worker styrer DaVinci Resolve (videoredigeringsprogrammet) gjennom Resolves innebygde MCP-server: `run_script` kjører skript skjermet (sandboxed, avskåret fra resten av maskinen), `run_script_unsafe` kjører skript som rører filsystemet og ffmpeg (programmet som behandler video). Prosjektet måler farger med Python og skriver til Resolve-prosjekter.
- fagfilm-pipeline er en Mac-app som tar en mastervideo gjennom ffmpeg, sender den til AWS (Amazons skytjeneste) og publiserer den. Prosjektet bruker `/browse` til å sjekke den publiserte videoen på `staging.fagfilm.no` (testutgaven av nettstedet).

### Bevis for web og pipelines

Beviset er at noen har sett det virke: en ekte kjøring mot ekte inndata, et skjermbilde, eller filen som kom ut. Tester sier at ingenting annet gikk i stykker, ikke at det du rettet er rettet ([se kapittel 4](#k4)).

- **Nettsider.** `/superpowers-gstack:verify-and-land` har en kortere vei for utviklingsservere. Den starter prosjektets utviklingsserver (en lokal webserver du bruker mens du bygger) med prosjektets dev-skript, husker prosessen og sjekker at den fortsatt lever før den stoler på porten, fordi en gammel server fra en annen gren kan holde porten og svare med utdatert kode. Så kommer samme spørsmål som i kapittel 4, og et ja lander grenen slik prosjektets `Landing mode:`-linje sier.
- **Pipelines.** Et kommandolinjeverktøy har ingen app å se på, og da sier verify-and-land at du bør kjøre testene. Beviset blir en kjøring du selv leser. Fagfilm-pipeline skiller mellom `scripts/live-smoke.sh` (tørrkjøring som ikke skriver noe) og den samme med `--force`, som oppretter, verifiserer og rydder bort én testvideo (prosjektets CLAUDE.md).
- **Mot ekte tjenester.** Resolve-ai-worker kjører Resolve-tester via MCP mot et lokalt testprosjekt, aldri mot det delte Blackmagic Cloud-biblioteket. KvitteriAi bruker ingen ekte tjenester i testene sine.

KvitteriAi håndterer fakturaer og nøkler (de hentes fra nøkkelringen på Macen), så koden og dataene som berører dem skal bare leses av Claude selv og Codex, og aldri sendes til det tredje modellhuset ([se kapittel 4](#k4)).

> 💡 I et web- eller pipelineprosjekt er beviset en ekte kjøring du har sett: skjermbildet eller filen som kom ut. Sikkerhets- og økonomimateriale holdes unna det tredje modellhuset.
