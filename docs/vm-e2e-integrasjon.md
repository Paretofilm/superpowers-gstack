# VM-basert E2E-testing: hva som må gjøres i superpowers-gstack

*Flyttet 2026-09-07.* Innholdet er tatt inn i den fullstendige design-spec-en
[`superpowers/specs/2026-09-07-vm-executor-design.md`](superpowers/specs/2026-09-07-vm-executor-design.md),
som også forener dette dokumentet med riggens beslutningsgrunnlag
(`~/Developer/virtual-mac/docs/2026-09-07-vm-e2e-funn.md`). De to foreslo hver sin eier for
executor-valget; spec-en løser det.

Kortversjonen av designet: **tre lag, én fil.** `.gstack/e2e-executor` (`host` | `vm`,
fravær = vert) leses av `e2e-route` for å *forklare*, av `scripts/run-uitests.sh` for å
*velge*, og `vm-e2e` + `vm-lease` i riggen *håndhever* invarianten om én kjøring per
macOS-instans. Fase 0 (riggen) implementeres først; plugin-rutingen (fase 1) venter til
riggen har gått mot ekte arbeid noen dager.
