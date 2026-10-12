---
nummer: 10
tag: Verktøykassa
tittel: De andre verktøyene, enkelt forklart
aksent: emerald
oppdatert: 2026-10-12
bruk: et verktøy du ikke kjenner dukker opp i en melding, og du vil vite hva det er og om du skal gjøre noe
ferdig: du vet hva verktøyet gjør, hvilken kommando du skriver selv, og hva Claude gjør uten deg
---

### Worktrunk (`wt`)

Worktrunk er kommandoen `wt`, som lager og rydder arbeidstrær (ekstra mapper med hver sin gren, [se kapittel 6](#k6)) og kjører prosjektets sjekker før noe lander. Tre kommandoer er de du faktisk ser:

- `wt switch --create <type>/<tema> --no-cd --format=json` lager en ny gren og et arbeidstre til den, for eksempel `feat/ny-side`. `--no-cd` betyr at terminalen din blir stående der den er. `--format=json` gjør at svaret kommer som strukturerte data, så Claude kan lese hvor mappen havnet. Claude går så inn i mappen med et eget verktøy (`EnterWorktree`). Vil du selv dit, bruker du stien den skrev ut: `cd <sti>`.
- `wt remove <gren>` fjerner arbeidstreet, og sletter grenen hvis den er slått sammen (sier `wt remove --help`). Har arbeidstreet endringer som ikke er committet, nekter den. Du kjører den etter landing, utenfor arbeidstreet du skal fjerne.
- `wt config approvals add` godkjenner sjekkene en gang. Den spør deg ja eller nei, så den må kjøres i et ekte terminalvindu ([se kapittel 1](#k1)).

Sjekkene står i `.config/wt.toml` under `[pre-merge]`: ett navn og én kommando per linje. I denne pluginens eget prosjekt står for eksempel `lint = "python3 scripts/lint-skills.py"` der. Sjekkene kjører de samme kommandoene som testene på GitHub, og de erstatter gjennomgangen når ingen andre leser. Prosjekter med `Landing mode: solo` lander derfor uten pull request (en forespørsel om gjennomgang på GitHub): `/superpowers-gstack:land` kjører sjekkene, flytter `main` fremover og sender til GitHub ([se kapittel 4](#k4)). Ta det frem når en oppgave skal ha sin egen mappe, og når en ferdig gren skal lande.

### Modellhus

Et modellhus er et selskap som lager språkmodeller, og hvert hus har sine egne blindsoner, så flere hus gir bedre kontroll ([se kapittel 4](#k4)). Det meste av dette starter Claude selv.

- Codex (OpenAI) kommer gjennom `/review`, som kjører Codex mot endringen din, og gjennom `/codex`. `/codex review` gir en uavhengig gjennomgang, `/codex challenge` prøver å knekke koden, og `/codex <spørsmål>` stiller Codex et spørsmål (sier `/codex`-skillen). Bruk dem når du vil ha en annen lesning enn Claudes.
- Det tredje huset er `/superpowers-gstack:third-lens-review`. Pitfall-verification starter den av seg selv på endringer med høy innsats, og skillen sier selv at du bare starter den for hånd når du vil ha en frittstående lesning utenfor den vanlige kontrollen. Hvilke modeller som brukes, står i skriptet `scripts/third-lens-review.py` og endres, så manualen oppgir ingen navn. `python3 scripts/third-lens-review.py --help` viser alternativene.
- `agy` gir Gemini-tekst, og ifølge oppsettet ditt uten kostnad. Skriv `agy -p "<spørsmål>"` for ett svar, eller `cat fil.md | agy -p "finn svakheter i argumentasjonen"` for å la den lese en fil. Bruk den til analyse, oppsummering og oversettelse, ikke til bilder.
- `gemini-media` lager bilde, video, tale og musikk. Det er et skript som ligger i mappen `~/.claude/bin/`, og står ikke på stien din, så skriv hele stien: `~/.claude/bin/gemini-media image "en katt i romdrakt" -o katt.png`, og `video`, `tts` og `music` på samme måte (`~/.claude/bin/gemini-media --help` viser dem). Hvert kall koster penger, og video er dyrest. Si fra til Claude hvis du vil ha mange bilder eller video, så anslår den prisen først. Manualen oppgir ingen priser.

Nøklene ligger i macOS-nøkkelringen (Keychain, Macens innebygde passordlager), og verktøyene henter dem selv derfra. Du skal aldri skrive eller lime en nøkkel inn i en samtale med Claude, og Claude skal aldri skrive den ut. Skal en nøkkel byttes, gjør du det selv i et terminalvindu.

Sikkerhetsregelen fra [kapittel 4](#k4) gjelder fortsatt: kode og data som håndterer innlogging, nøkler, helse eller økonomi leses bare av Claude selv og Codex, og sendes aldri til det tredje huset, fordi Zhipu- og DeepSeek-modellene i det tredje huset kjører på ikke-vestlig infrastruktur.

### Swift-verktøy

Tre verktøy hjelper Claude å skrive og se Apple-apper, og alle er MCP-verktøy (MCP, Model Context Protocol, er standarden som kobler verktøy til Claude). Hva de brukes til i et ekte prosjekt, står i [kapittel 7](#k7). Her er bare hva hvert av dem er.

- `live-swiftui` tegner en `#Preview` (forhåndsvisning) i en SwiftUI-visning på macOS, og lar Claude ta skjermbilde, trykke og måle uten å starte hele appen (verktøyets egen beskrivelse). Bruk det når et utseende eller en interaksjon skal sjekkes uten å bygge hele appen. Mål for iOS støttes ikke ennå.
- `swiftui-rag` slår opp i en samling typesjekkede SwiftUI-eksempler og Apples HIG (designretningslinjene), typesjekker Swift-kode og lint-sjekker den mot HIG (verktøyets egen beskrivelse). Oppsettet ditt i `~/.claude/CLAUDE.md` slår opp der før SwiftUI skrives og kjører HIG-sjekken etterpå. Bruk det når SwiftUI-mekanikk er uklar, for eksempel treffområder, og når et utseende skal sjekkes mot Apples regler.
- XcodeBuildMCP bygger, starter og tester apper i en iOS-simulator og kan ta skjermbilder og trykke i appen (verktøyets egen beskrivelse). Bruk det når Claude skal se en iOS-app kjøre i simulatoren.

### Calyx og reserve-Mac

Calyx er terminalprogrammet Claude kan åpne faner i, og reserve-Macen er en isolert virtuell Mac (en maskin som kjører som et program inni din egen) du leier gjennom `vm-run`.

Calyx trengs for kommandoer som spør deg om noe underveis: ja eller nei, passord eller godkjenning. En kommando som starter med `!` i Claude Code har ikke et ekte terminalvindu og henger ([se kapittel 1](#k1)). Når Calyx finnes, åpner Claude en ny fane i prosjektmappen og kjører kommandoen der. Calyx spør deg før den kjøres, og du svarer selv i fanen. Claude svarer aldri på slike spørsmål for deg. Uten Calyx får du hele kommandoen, og du kjører den i et vanlig terminalvindu.

For reserve-Macen skriver du `vm-run -- <kommando>`. Verktøyet låner en ledig gjest, kjører kommandoen og frigir gjesten igjen, og `vm-run --help` lister hva det kan. Etter hjelpeteksten kan du blant annet kjøre GUI-skripting på navn med System Events, ta skjermbilde av gjesten med `--screenshot <fil.png>` og kopiere filer til og fra gjesten med `--sync` og `--fetch`. Hjelpeteksten sier også at gjesten ikke har noen innloggede kontoer, og at koordinatbaserte klikk ikke virker. Gjesten har Xcode, `swift`, `git`, `jq`, `rsync` og `python3`, men ikke Claude Code, `node` eller `brew`. Det koster omtrent 30 sekunder å starte en gjest.

Bruk den, slik oppsettet ditt sier, når oppgaven automatiserer GUI, endrer systemtilstand (installerer, avinstallerer, skriver i `/Library`), skal se hvordan noe virker på en ren maskin, eller kjører lenge uten tilsyn. Bruk den ikke til å redigere filene i prosjektene dine, og ikke til noe som trenger din signeringsidentitet (bevis på hvem som har laget appen) eller innloggede kontoer. Skal Claude derimot styre appene på din egen maskin, og du ber om det, gjør den det og sier fra først.

> 💡 Du trenger sjelden å skrive `wt` selv, for Claude og `/superpowers-gstack:land` kjører det meste av det. Nøkler skal aldri inn i en samtale.
