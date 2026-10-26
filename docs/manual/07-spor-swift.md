---
nummer: 7
tag: Spor: Swift
tittel: Native apper (macOS og iOS 26)
aksent: violet
oppdatert: 2026-10-12
bruk: prosjektet er en Mac- eller iPhone-app skrevet i Swift
ferdig: du vet hvilke ekstra skills en Apple-app trekker inn, og du har sett akkurat denne grenen kjøre
---

![[spor.svg]]

### Det som er felles, og det som er ekstra

Kjernen er den samme i alle prosjekter: idé, plan, bygg, bevis og landing ([se kapittel 0](#k0)). Et spor legger verktøy til på sidene. Figuren viser to spor. Dette kapittelet tar Swift, [kapittel 8](#k8) tar web og Python.

Hvilket spor prosjektet har, står i filen `.gstack/track`. For en Apple-app står det `ios`, `macos` eller `both` der, og mangler filen, regnes prosjektet som web. `/superpowers-gstack:office-hours-track-aware` spør om plattformen og skriver filen når en idé handler om en Apple-app, og `/superpowers-gstack:adapt` skriver den når den setter opp prosjektet. Skillene under leser filen for å vite hvilken plattform de skal sjekke mot.

### Hva en Swift-app legger til

Målet er iOS 26 og macOS 26 med Liquid Glass, Apples designspråk fra og med de versjonene (bygget på glassaktige materialer i kontrollene).

| Skill | Hva den gjør | Bruk den når |
|---|---|---|
| `/superpowers-gstack:swiftui-design-consultation` | Spør om produktet og hvor streng sjekken mot Apples regler skal være, viser et forslag som side, og skriver `DESIGN.md` og en Swift-pakke `DesignSystem/` først når du godkjenner | Du starter eller friske opp designsystemet i et SwiftUI-prosjekt |
| `/superpowers-gstack:apple-native-review` | Sjekker en spec eller plan mot Apples HIG (Human Interface Guidelines, Apples offisielle designretningslinjer) | Spec eller plan med brukergrensesnitt er ferdig, og før noe bygges |
| `/superpowers-gstack:swiftui-view-gate` | Kontrollerer en endret SwiftUI-visning mens den bygges: slår opp riktig kontrolltype, sjekker koden mot Apples regler, tegner visningen der den faktisk står og leser bildet, og avslutter med en `View gate:`-linje | Claude har endret en visning. En påminnelse nevner skillen når en visningsfil redigeres |
| `/superpowers-gstack:quality-review` | Leter etter det som får et produkt til å kjennes billig: stille feil, manglende lasting, tomme tilstander, dårlig feilhåndtering | Spec eller plan er ferdig, før noe bygges. Den gjelder også web |

Apple-native-review stiller ett spørsmål: leses appen som en Apple-app, eller som en port fra en annen plattform? Hvert funn skal sitere en HIG-side som er hentet under kjøringen. Kan siden ikke hentes, merkes funnet `(uncited)` (uten kilde), og dommen blir `PROVISIONAL` (foreløpig). Anbefalt rekkefølge på en ny spec er `/superpowers-gstack:pitfall-verification`, så quality-review, så apple-native-review, og så plan ([se kapittel 3](#k3)).

Quality-review spør om det vil kjennes bra, pitfall-verification spør om det vil virke ([se kapittel 4](#k4)). I loggene fra seks prosjekter ble `/superpowers-gstack:quality-review` brukt 1 gang, og `/superpowers-gstack:swiftui-design-consultation` og `/superpowers-gstack:e2e-scaffold` brukt 0 ganger (målt 10. oktober 2026, 61 hovedøkter). Tallene er et øyeblikksbilde, ikke en egenskap ved verktøyene.

### Ende-til-ende-tester: hvem gjør hva

En ende-til-ende-test (E2E) trykker seg gjennom appens brukergrensesnitt (UI) slik en bruker ville gjort. To skills deler jobben.

- `/superpowers-gstack:e2e-route` er en ren veiviser. Den leser plattform, hva du vil, og hvor testene skal kjøre, sier hvem som tar jobben, og overlater den. Den bygger, trykker og skriver ingenting selv.
- `/superpowers-gstack:e2e-scaffold` lager grunnlaget for UI-tester (XCUITest, Apples verktøy for tester som trykker gjennom appen). Den endrer prosjektfiler og kjøres bare når du ber om det.

Hva du vil, avgjør hvor e2e-route sender deg:

| Du vil | Veivisern sender deg til |
|---|---|
| Låse en test som skal vare, for eksempel mot regresjon (at noe som virket slutter å virke) | Prosjektets egen E2E-test hvis den finnes, ellers `/superpowers-gstack:e2e-scaffold` |
| Trykke gjennom nå og se hva som skjer | XcodeBuildMCP på macOS og ios-simulator-MCP på iOS (MCP forklares under) |
| Se om det ser riktig ut | Sammenligning av skjermbilder, og på macOS `/design-review` |

E2e-scaffold finner de viktigste visningene, foreslår `accessibilityIdentifier` på knappene (et navn Claude og testene finner kontrollen på) og bruker dem først når du har godkjent. Så lager den tomme prøver som feiler med `XCTFail("not implemented")` til noen fyller dem inn, `scripts/run-uitests.sh` og `docs/accessibility-identifiers.md`. Finnes det allerede en UI-test, nekter den og ber deg utvide den for hånd. For låste macOS-tester kan filen `.gstack/e2e-executor` si `host` (din egen Mac) eller `vm` (en virtuell maskin). E2e-route leser den, og `/superpowers-gstack:adapt` skriver den.

### Se grensesnittet uten å starte hele appen

To verktøy lar Claude se og slå opp SwiftUI mens den skriver. Begge er MCP-verktøy (MCP, Model Context Protocol, er standarden som kobler verktøy til Claude).

`live-swiftui` er en egen macOS-app som tegner en `#Preview` (en kodeblokk i Swift-filen som beskriver hvordan én visning skal tegnes for forhåndsvisning, som i Xcode). Claude kan så ta skjermbilde, trykke, skrive og måle, uten å starte hele appen. Verktøyets egen beskrivelse nevner utseende, treffområder, interaksjon og bevegelse. Du må skrive `#Preview` selv med falske data, og iOS-mål støttes ikke ennå (sier verktøyets egen beskrivelse). Eksempel fra sing-replay (en Swift-app for iOS 26 og macOS 26 som spiller av innspilte sangøkter): Claude forsøkte å bruke det på take-velgeren, og prosjektets CLAUDE.md skriver ned utfallet. Per 27. august 2026 bygde den utskilte pakken, men verktøyet fant ikke forhåndsvisningen (`previewNotFound`), og årsaken var ikke klarlagt. Per 23. august 2026 vises heller ikke `.popover` og `.sheet` i skjermbildene, så høyden på dem måles med en test i stedet. Verktøyet har altså grenser, og prosjektet skriver dem ned.

`swiftui-rag` slår opp i en samling SwiftUI-eksempler som er typesjekket mot SDK-en (utviklerpakken fra Apple), sammen med HIG-veiledning. Det kan også typesjekke Swift-kode i isolasjon og lint-sjekke den mot HIG, inkludert Liquid Glass og tilgjengelighet (verktøyets egen beskrivelse). Oppsettet ditt i `~/.claude/CLAUDE.md` slår opp i samlingen før SwiftUI skrives, og kjører HIG-sjekken etterpå. Eksempel fra sing-replay: prosjektets CLAUDE.md sier at en Swift-fil typesjekkes alene med `swift_typecheck`. Design-consultation bruker de samme verktøyene, men hopper over macOS-sjekken på en iOS-app, fordi menylinje-funn ville styrt forslaget mot feil plattform.

### Bevis for Swift-apper

Beviset er at du har sett akkurat denne grenen kjøre ([se kapittel 4](#k4)). `/superpowers-gstack:verify-and-land` bygger grenen du står på, starter nøyaktig den bygde appen og melder hvilken gren, hvilken bygging og hvilken commit som kjører. På iOS skjer det i simulatoren (en iPhone som kjører som program på Macen), og skillen sjekker at installasjonen er fra denne kjøringen. Så spør den om rettelsen er der, én gang per endring du kan se. Svarer du ja på alle, lander grenen slik prosjektets `Landing mode:`-linje sier, uten et nytt spørsmål. Svarer du nei, lander ingenting, og skillen foreslår `/investigate`. Har du endret en SwiftUI-visning, nevner spørsmålet filen ved navn og sier om utseendet ble tegnet og sett, eller bare bygget uten at utseendet er kontrollert. Regelen om å slå opp, lese reglene og se visningen før den kalles ferdig, står i prosjektets CLAUDE.md etter at du har kjørt `/superpowers-gstack:adapt` på nytt. `/superpowers-gstack:adapt` spør én gang i macOS-prosjekter om Claude får se på appen selv før den spør deg. Svarer du ja, skrives `host` i filen `.gstack/visual-verify`, og Claude tar da bilde av bare vinduet til appen den selv startet, aldri hele skjermen.

For iOS bygger og starter skillen i simulatoren, og den har ingen vei til en ekte telefon. Det du ikke kan se i en simulator, må du se på en ekte enhet. Sing-replay viser hvordan det ser ut. Filen `progress.md` oppgir testenheten som en iPhone 13 Pro Max med iOS 26.6, paret og i utviklermodus, men Meta-tabellen er ikke datert. Den nyeste datoen i filen er 16. august 2026. Der står også at lydverifiseringen på en ekte telefon (stille-bryter, skjermlås, hodetelefon trukket ut, innkommende samtale) ikke kan simuleres og var «blokkert på brukerens hender, ikke på kode». Med andre ord: filen lister en paret enhet (udatert), og lydverifiseringen på den er fortsatt åpen. At appen ble installert på telefonen 15. august 2026, står i prosjektets CLAUDE.md, som også beskriver en felle derfra: en ny installasjon på telefonen dreper tilgangen til mappen med opptak, og appen viser velkomstskjermen igjen. Det ser ut som en feil, men er forventet.

> 💡 En Apple-app legger Apples regler (HIG og Liquid Glass) til kjernen, og beviset er å se akkurat denne grenen kjøre: i simulatoren for det du kan se, på en ekte telefon for lyd og maskinvare.
