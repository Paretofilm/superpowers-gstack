# spec-drift fase 1 — implementasjonsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** En frittstående skill, `/superpowers-gstack:spec-drift <plan> [--base <ref>]`, som kjører `/ship` sin Step 8 (Plan Completion Audit) på hvilken som helst gren — lest fra disk ved kjøring, hash-pinnet, med eksplisitt plan-sti og baseline, og med samme rapport, samme JSON og en exit-kode 0/1/2.

**Architecture:** Wrapper, ikke utløfting. Seksjonen `~/.claude/skills/gstack/ship/sections/plan-completion.md` er upstream gstack og autogenerert der; denne plugin-en kan verken patche den eller få `/ship` til å kalle noe. Skillen leser derfor filen ved kjøring og dispatcher den som subagent med et lite sett *overstyringer* (ingen plan-discovery, base som argument, ingen AskUserQuestion-porter). Alt som ikke skal overlates til en modells skjønn ligger i ett stdlib-Python-script, `scripts/spec-drift.py`: `check` (hash-pin), `repin` (vis diff, krev bekreftelse) og `verdict` (Step 8-JSON → exit-kode). Pinnen er sha256 pluss et committet byte-snapshot av seksjonen, slik at `--repin` faktisk kan vise hva som endret seg.

**Tech Stack:** Markdown-instruksjonsfiler (`skills/spec-drift/SKILL.md`, rutingtabeller i `skills/setup-routing/SKILL.md`, `skills/adapt/SKILL.md`, `CLAUDE.md`, `README.md`), Python 3 stdlib (`scripts/spec-drift.py`), pytest (`tests/unit/`), lint (`scripts/lint-skills.py`).

**Spec:** `docs/superpowers/specs/2026-09-07-spec-drift-design.md` — seksjonene «Avgrensning», «Fase 1 — wrapper, ikke utløfting» og «Verifisering hvis fase 1 bygges» er det denne planen implementerer. Fase 2 (skriv-tilbake, ledger) og fase 3 (inventering, prosa-påstander, sikkerhetskategori) er **ikke** med.

---

## Global Constraints

Alle fasers krav inkluderer implisitt denne seksjonen.

- **Repo og gren:** `~/Developer/superpowers-gstack`, gren `feat/spec-drift` (finnes; tre commits foran `main`: specen, IDEAS-entryen og denne planen). Ikke lag ny gren.
- **Alle kommandoer kjøres fra repo-roten.** Stiene i planen er relative til `~/Developer/superpowers-gstack`. Kjører sesjonen eller subagenten med en annen arbeidsmappe, prefiks hvert Bash-kall med `cd /Users/kjetilge/Developer/superpowers-gstack &&` — en `pytest tests/unit` fra feil mappe finner ingenting og rapporterer det som grønt.
- **Lint grønn etter hver fase.** `python3 scripts/lint-skills.py` må avslutte med `0 error(s)`. To advarsler er forventet og er ikke feil: `W2 adapt` og `W2 swiftui-design-consultation`.
- **Enhetstester grønne etter hver fase.** `pytest tests/unit scripts/cost-ledger -q` — nøyaktig CI-kommandoen fra `.github/workflows/lint.yml` (`bash tests/run.sh --unit` kjører den samme). **378 passed, 10 warnings** målt 2026-09-07 på `feat/spec-drift` før fase 1 (352 i `tests/unit`, 26 i `scripts/cost-ledger`). Tallene under er målt-og-forventet, ikke lovet; avviker ditt tall, si det i stedet for å anta at planen har rett. `pytest tests/unit -q` alene er ikke gaten — den hopper over cost-ledger-suiten CI kjører.
- **CI installerer kun pytest.** `scripts/spec-drift.py` bruker bare standardbiblioteket (`argparse`, `difflib`, `hashlib`, `json`, `pathlib`).
- **Harde krav fra specen (gjelder alle faser):**
  - Skillen **leser** `plan-completion.md` fra disk ved kjøring og utfører seksjonen. Teksten kopieres aldri inn i `SKILL.md`, upstream patches aldri, og `/ship` antas aldri å kjenne til skillen.
  - Hash-pin som feiler høyt ved avvik; `--repin` viser diffen og krever bekreftelse; pinnen er committet i skillen (`skills/spec-drift/`), ikke per maskin.
  - Plan-sti er et eksplisitt argument. Ingen discovery-heuristikk (ingen grep etter grennavn, ingen «nyeste fil siste 24 timer»).
  - Baseline er et argument; standard er `git diff <base>...HEAD` der `<base>` er repoets standardgren.
  - Utdata: samme menneskelesbare rapport som Step 8, samme JSON på siste linje (`total_items`, `done`, `changed`, `deferred`, `unverifiable`, `summary`), exit-kode `0` rent / `1` drift / `2` kunne ikke kjøre. **Hva «exit-kode» betyr for en Markdown-skill:** en skill kan ikke returnere en prosess-status. Kontrakten er derfor strukturert tekst — verdikt-linjen `SPEC-DRIFT: … (exit N)` rett over JSON-en, beregnet av `scripts/spec-drift.py verdict`, aldri dømt — pluss én mekanisk kommando: en kaller som trenger en ekte prosess-exit-kode kjører `verdict` på JSON-linjen og får 0/1/2. Ingen prosaparsing i noe ledd.
  - Skillen redigerer aldri kildekode, planen eller upstream-seksjonen.
- **Lint-regler som treffer en ny skill:** E1 (frontmatter, `name` = katalognavn, `description` finnes), E2 (`$SKILL_DIR/../../scripts/<fil>` må finnes i repoet; `superpowers-gstack:<navn>` må finnes), E3 (`spec-drift` må nevnes i `CLAUDE.md`), E4 (versjon ↔ CHANGELOG), E7 (denylist skanner også `scripts/*.py`), W1 (`description` ≤ 30 ord). Merk at E1 feiler på en katalog under `skills/` uten `SKILL.md` — derfor opprettes `skills/spec-drift/` først i fase 3.
- **Versjon:** `.claude-plugin/plugin.json` `2.51.1` → `2.52.0` i fase 3, med matchende `## [2.52.0]`-entry i `CHANGELOG.md`.
- **Git-hygiene:** stage eksplisitte stier (aldri `git add -A`), aldri `--no-verify`, commit-format `<type>(spec-drift): <sammendrag>`. Push etter hver fase-commit (`git push -u origin feat/spec-drift` første gang, deretter `git push`).
- **Upstream-fakta ved planlegging (2026-09-07):** gstack `1.81.0.0` installert som git-klone i `~/.claude/skills/gstack` (MIT, Garry Tan). `ship/sections/plan-completion.md` er 331 linjer, sha256 `e329e5ef76991a02f0248931974667106ee1ad8ec4a324651efa3c6d1291df2f`. Pinnen i fase 3 lages fra disk, ikke fra dette tallet — tallet er der for at implementøren skal *oppdage* om gstack oppdaterte seg mellom plan og implementasjon, og i så fall lese diffen før pinning.

---

## Beslutninger tatt her, så implementøren slipper å ta dem

### D1. Pinnen er sha256 **pluss** et committet byte-snapshot

Specen sier «`--repin` viser diffen». En hash alene kan ikke vise en diff — den kan bare si «ulik». Snapshotet `skills/spec-drift/pin/plan-completion.md` er en byte-identisk kopi av upstream-filen slik den var da den ble pinnet, og brukes **kun** til å vise diffen. Den utføres aldri: skillen leser alltid upstream-stien. `check` verifiserer begge retninger — upstream-hash == `pin.json` og snapshot-hash == `pin.json` — så pin og snapshot kan ikke drive fra hverandre. I tillegg verifiserer både `check` og `repin` åtte **tekstankere** — overskriftene og strengene overstyringene i SKILL.md navngir (`## Step 8:`, `## Step 8.1`, `### Plan File Discovery`, `### Gate Logic`, `<base>`, `Include in PR body`, `Parent processing`, `"total_items"`) — slik at et upstream-omdøp som beholder alt annet ikke kan pinnes: en pin som passerer hash-en men mangler et anker ville fått wrapperen til å kjøre Step 8.1 med, eller finne ingen Gate Logic å overstyre. gstack er MIT-lisensiert; `pin.json` navngir kilden.

### D2. Hele filen pinnes, ikke bare Step 8-regionen

Filen inneholder Step 8, Step 8.1, «Prior Learnings» og Step 8.2. Å pinne bare Step 8 krever parsing av overskriftsgrenser som selv kan endre seg. gstack sin egen enhet er filen (`sections/manifest.json`). Prisen er at en endring i 8.1/8.2 også ryker pinnen; det er akseptert — `--repin` er billig og viser hva som endret seg, og subagent-prompten sier eksplisitt «kun Step 8».

### D3. Subagenten leser seksjonen selv; forelderen limer den ikke inn

Step 8 sin egen begrunnelse for subagent-dispatch er frisk kontekst. Forelderen kjører `check` (bytene er verifisert), og gir subagenten *stien* pluss overstyringene. Samme bytes kjøres, forelderkonteksten holdes liten, og det finnes ingen kopi av teksten noe sted i denne plugin-en utenom D1-snapshotet.

### D4. Gate Logic sine spørsmål kjøres ikke frittstående — exit-koden erstatter dem

Step 8 stiller AskUserQuestion ved NOT DONE og per punkt ved UNVERIFIABLE fordi noe skal *shippes*. Frittstående skal `autoimplement` kunne kalle skillen mekanisk ved fasegrenser. Per-punkt-bekreftelse *med hukommelse* er fase 2 sin ledger; i fase 1 er rapporten + exit-koden hele svaret. «Exit-koden» til en Markdown-skill er nødvendigvis en tekstkontrakt (verdikt-linjen, beregnet av `verdict`); prosess-exit-koden finnes i `scripts/spec-drift.py verdict`, som enhver kaller kan kjøre på JSON-linjen. Det er den eksplisitte definisjonen — ikke en antakelse om at Skill-verktøyet propagerer en status det ikke har.

### D5. PARTIAL teller som drift (exit 1), selv om `/ship` ikke blokkerer på det

Frittstående finnes ikke «ship anyway». Et punkt planen beskriver og koden bare halvveis har, er drift. JSON-en skiller fortsatt (PARTIAL = `total_items − done − changed − deferred − unverifiable`), så en kaller som vil være mildere kan være det.

### D6. `total_items == 0` er exit 2, ikke «skip»

Step 8 hopper over («no actionable items») fordi `/ship` ikke visste hvilken plan som gjaldt. Her navnga brukeren stien. Null punkter fra en eksplisitt sti betyr at auditen ikke fikk kjørt — typisk et designdokument, som er fase 3.

### D7. Tom diff er exit 2

`git diff origin/main...HEAD` på `main` er tom. Uten denne regelen blir alt NOT DONE og skillen roper ulv på standardgrenen. Fiksen er `--base <eldre commit>` — som også er hvordan hull 5 i specen lukkes.

### D8. Fase 4 sin stående test feiler høyt på vedlikeholderens maskin

Samme to-lags mønster som lint E10 + W3 / `test_roster_matches_installed_upstream_when_present`: hoppes over i CI (ingen gstack der), feiler lokalt når upstream-seksjonen har endret seg siden pinning. Det *er* «feiler høyt ved avvik» — bare tidligere enn ved bruk. Feilmeldingen navngir `repin`-kommandoen.

---

## Filstruktur

| Fil | Fase | Ansvar |
|---|---|---|
| `scripts/spec-drift.py` | 1, 2 | Den mekaniske halvdelen: `check`, `repin`, `verdict`. Stdlib. |
| `tests/unit/test_spec_drift_pin.py` | 1 | Pinnen: refuserer uten pin, viser diff før `--yes`, én endret linje refuseres og navngis, korrupt snapshot refuseres. |
| `tests/unit/test_spec_drift_verdict.py` | 2 | JSON → exit-kode-tabellen, siste-linje-regelen, malformert JSON er 2. |
| `skills/spec-drift/SKILL.md` | 3 | Wrapperen: argumenter, pin-sjekk, re-pin-flyt, subagent-dispatch med overstyringer, verdikt. |
| `skills/spec-drift/pin.json` + `skills/spec-drift/pin/plan-completion.md` | 3 | Pinnen (D1). Lages av `repin --yes`, committes sammen. |
| `CLAUDE.md`, `README.md`, `skills/setup-routing/SKILL.md`, `skills/adapt/SKILL.md`, `skills/setup-routing/model-routing.md` | 3 | Ruting: uten disse feiler E3, og ingen andre prosjekter får vite at skillen finnes. |
| `.claude-plugin/plugin.json`, `CHANGELOG.md`, `IDEAS.md` | 3 | Release-gate. |
| `tests/unit/test_spec_drift_skill.py` | 3 | Omisjonstester: wrapperen forblir wrapper. |
| `tests/fixtures/spec-drift/stale-plan.md` | 4 | Kontrollert, bevisst stale plan for ekvivalenskjøringen. |
| `tests/unit/test_spec_drift_upstream_alarm.py` | 4 | Den stående alarmen (D8). |
| `docs/superpowers/specs/2026-09-07-spec-drift-design.md` | 4 | Får en resultatseksjon for verifiseringen. |

---

## Phase 1: Hash-pinnen — `check` og `repin`

Alt som må være sant om «samme filbytes kjøres» ligger her, og ingenting av det skal avgjøres av en modell. Fasen lager scriptet uten `verdict` (fase 2) og uten skill-katalogen (fase 3, se E1-noten i Global Constraints). Tester bruker en falsk gstack-installasjon under `tmp_path`, så `~/.claude` røres aldri.

**Files:**
- Create: `scripts/spec-drift.py`
- Test: `tests/unit/test_spec_drift_pin.py`

**Interfaces:**
- Produces: `python3 scripts/spec-drift.py check [--upstream PATH] [--pin-dir DIR]` → exit `0` (`PIN OK …` på stdout) eller `2` (`UPSTREAM MISSING` / `UPSTREAM UNREADABLE` / `NO PIN` / `PIN CORRUPT` / `PIN MISMATCH` / `ANCHORS MISSING` på stderr, alle navngir veien ut). `PIN CORRUPT` dekker også en `pin.json` som er gyldig JSON av feil form (liste, streng, `sha256` som ikke er streng) — aldri en Python-traceback med exit 1. `ANCHORS MISSING` navngir hvilke av de åtte ankrene (D1) upstream-teksten mangler.
- Produces: `python3 scripts/spec-drift.py repin [--upstream PATH] [--pin-dir DIR] [--yes --sha HEX]` → uten `--yes`: unified diff på stdout, så `ANCHORS: all present` + `REPIN REQUIRES CONFIRMATION … re-run with --yes --sha <12 tegn>`, exit `3`; mangler et anker: `REPIN BLOCKED: ANCHORS MISSING: …` på stderr, exit `2` (fiks SKILL.md sine overstyringer først — det finnes ingenting å akseptere); med `--yes --sha <prefiks av sha256 diffen viste>`: skriver `<pin-dir>/pin.json` og `<pin-dir>/pin/plan-completion.md`, exit `0`; `--yes` uten `--sha`, eller med en `--sha` som ikke matcher upstream *nå*, eller når et anker mangler: `REPIN REFUSED`, exit `2` (aksepten er bundet til bytene som ble vist — en auto-oppdatering mellom diff og `--yes` kan ikke pinnes ulest); ingen endring: `PIN UNCHANGED`, exit `0`.
- Produces: `pin.json`-skjema `{"source", "sha256", "gstack_version", "pinned_at"}`; `gstack_version` leses fra `<upstream>/../../../VERSION` (`ship/sections/plan-completion.md` → gstack-roten), `"unknown"` om den mangler.
- Standardverdier: `--upstream` = `~/.claude/skills/gstack/ship/sections/plan-completion.md`, `--pin-dir` = `<repo>/skills/spec-drift`.

- [ ] **Step 1: Skriv den feilende testen**

Opprett `tests/unit/test_spec_drift_pin.py`:

```python
"""Guard scripts/spec-drift.py check/repin — the hash pin on /ship Step 8's section.

The skill executes an upstream file it does not own (gstack auto-updates weekly).
The pin is what makes "same bytes" a checked fact instead of an assumption, and
--repin is what keeps the override from becoming a reflex: no diff shown, no pin.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"

# A miniature of the upstream section. It carries every anchor the wrapper's
# overrides name (ANCHORS in the script), so the anchor check has something to pass.
SECTION = (
    "## Step 8: Plan Completion Audit\n\n"
    "> ### Plan File Discovery\n"
    "line two\n"
    "### Gate Logic\n"
    "Use `<base>`. **Include in PR body (Step 8):** ... **Parent processing:** ...\n"
    '`{"total_items":N,"done":N}`\n'
    "\n## Step 8.1: Plan Verification\n"
    "line three\n"
)


def run(*args, expect, stdin=None):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, input=stdin)
    assert p.returncode == expect, (
        f"exit {p.returncode} (wanted {expect})\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def shown_sha(diff_run) -> str:
    """The sha the diff run tells the user to pass back with --yes."""
    return re.search(r"--yes --sha ([0-9a-f]{12})", diff_run.stdout).group(1)


def accept(upstream, pin_dir):
    """The two-step accept the skill performs: show the diff, then --yes bound to it."""
    p = run("repin", *common(upstream, pin_dir), expect=3)
    return run("repin", "--yes", "--sha", shown_sha(p), *common(upstream, pin_dir), expect=0)


@pytest.fixture()
def rig(tmp_path):
    """A fake gstack install (VERSION + ship/sections/plan-completion.md) and an empty pin dir."""
    gstack = tmp_path / "gstack"
    (gstack / "ship" / "sections").mkdir(parents=True)
    (gstack / "VERSION").write_text("9.9.9.9\n")
    upstream = gstack / "ship" / "sections" / "plan-completion.md"
    upstream.write_text(SECTION)
    pin_dir = tmp_path / "skill"
    pin_dir.mkdir()
    return upstream, pin_dir


def common(upstream, pin_dir):
    return ["--upstream", str(upstream), "--pin-dir", str(pin_dir)]


def test_check_refuses_without_a_pin(rig):
    upstream, pin_dir = rig
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "NO PIN" in p.stderr


def test_repin_shows_the_diff_and_refuses_without_yes(rig):
    upstream, pin_dir = rig
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "+## Step 8: Plan Completion Audit" in p.stdout, "the diff must be shown"
    assert "REPIN REQUIRES CONFIRMATION" in p.stdout
    assert not (pin_dir / "pin.json").exists(), "nothing may be written without --yes"


def test_repin_yes_writes_pin_and_snapshot_and_check_passes(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    pin = json.loads((pin_dir / "pin.json").read_text())
    assert pin["sha256"] == hashlib.sha256(SECTION.encode()).hexdigest()
    assert pin["gstack_version"] == "9.9.9.9"
    assert (pin_dir / "pin" / "plan-completion.md").read_text() == SECTION
    p = run("check", *common(upstream, pin_dir), expect=0)
    assert "PIN OK" in p.stdout


def test_one_changed_line_upstream_is_refused_and_named(rig):
    """Spec, Verifisering 4: change one line in a local copy of the section — the
    wrapper must refuse to run and name the hash mismatch."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.write_text(SECTION.replace("line two", "line two, reworded upstream"))
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN MISMATCH" in p.stderr
    assert "repin" in p.stderr, "the refusal must name the way out"
    p = run("repin", *common(upstream, pin_dir), expect=3)
    assert "-line two\n" in p.stdout and "+line two, reworded upstream" in p.stdout


def test_repin_is_a_noop_when_nothing_changed(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    p = run("repin", *common(upstream, pin_dir), expect=0)
    assert "PIN UNCHANGED" in p.stdout


def test_repin_yes_is_bound_to_the_bytes_the_diff_showed(rig):
    """Between the diff and the --yes, a weekly gstack update can rewrite the file.
    Accepting whatever is on disk at --yes time would pin bytes nobody read."""
    upstream, pin_dir = rig
    shown = shown_sha(run("repin", *common(upstream, pin_dir), expect=3))
    p = run("repin", "--yes", "--sha", shown[:4], *common(upstream, pin_dir), expect=2)
    assert "REPIN REFUSED" in p.stderr, "a 4-char prefix is a guess, not the receipt the diff run printed"
    upstream.write_text(SECTION + "changed after the diff was shown\n")
    p = run("repin", "--yes", "--sha", shown, *common(upstream, pin_dir), expect=2)
    assert "REPIN REFUSED" in p.stderr
    assert not (pin_dir / "pin.json").exists(), "nothing may be written on a refused accept"
    p = run("repin", "--yes", *common(upstream, pin_dir), expect=2)   # no --sha at all
    assert "REPIN REFUSED" in p.stderr


def test_snapshot_that_disagrees_with_pin_json_is_refused(rig):
    """pin.json and the snapshot are one artefact; edit one without the other and
    --repin's diff would lie about what was accepted."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    (pin_dir / "pin" / "plan-completion.md").write_text(SECTION + "tampered\n")
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "PIN CORRUPT" in p.stderr


def test_pin_json_of_the_wrong_shape_is_corrupt_not_a_traceback(rig):
    """Valid JSON that is not the pin's shape used to reach `.get`/slicing and die
    with a Python traceback — exit 1, which nothing above treats as 'refused'."""
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    for wrong in ("[]", '"a string"', '{"sha256": 5}', "{not json"):
        (pin_dir / "pin.json").write_text(wrong)
        p = run("check", *common(upstream, pin_dir), expect=2)
        assert "PIN CORRUPT" in p.stderr, wrong
        assert "Traceback" not in p.stderr, wrong


def test_repin_refuses_a_section_that_lost_an_anchor(rig):
    """The overrides name Step 8's structure. A section that dropped an anchor can
    still hash fine after a blind accept — and then the wrapper would run Step 8.1
    too, or find no Gate Logic to override. So the anchor check is mechanical."""
    upstream, pin_dir = rig
    upstream.write_text(SECTION.replace("### Gate Logic", "### Decision Logic"))
    p = run("repin", *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr and "### Gate Logic" in p.stderr
    sha = hashlib.sha256(upstream.read_bytes()).hexdigest()[:12]
    p = run("repin", "--yes", "--sha", sha, *common(upstream, pin_dir), expect=2)
    assert "ANCHORS MISSING" in p.stderr
    assert not (pin_dir / "pin.json").exists()


def test_missing_upstream_is_could_not_run_not_clean(rig):
    upstream, pin_dir = rig
    accept(upstream, pin_dir)
    upstream.unlink()
    p = run("check", *common(upstream, pin_dir), expect=2)
    assert "UPSTREAM MISSING" in p.stderr
```

- [ ] **Step 2: Kjør testen og se den feile**

Kjør: `pytest tests/unit/test_spec_drift_pin.py -q`
Forventet: 10 failed — `FileNotFoundError` / exit-kode 2 fra `python3` fordi `scripts/spec-drift.py` ikke finnes.

- [ ] **Step 3: Skriv scriptet**

Opprett `scripts/spec-drift.py` (gjør den kjørbar: `chmod +x scripts/spec-drift.py`):

```python
#!/usr/bin/env python3
"""spec-drift — the mechanical half of /superpowers-gstack:spec-drift.

The skill itself is prose: it reads gstack's /ship Step 8 section
(~/.claude/skills/gstack/ship/sections/plan-completion.md) from disk and executes
it standalone. This script is everything about that which must NOT be left to a
model's judgement:

  check    the upstream section's sha256 matches the committed pin — exit 0 on
           match, 2 on mismatch / missing upstream / missing or corrupt pin.
           The skill refuses to run on anything but 0.
  repin    show the unified diff between the pinned snapshot and the upstream
           section (exit 3: confirmation required); with --yes write the new
           snapshot + pin.json (exit 0). No difference: nothing to do, exit 0.

Why a snapshot and not only a hash: --repin must SHOW what changed upstream
before anyone accepts it. A guard that is overridden routinely without showing
its diff trains away its own effect (spec, Fase 1). The snapshot is never
executed — the skill always reads the upstream path.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PIN_DIR = REPO / "skills" / "spec-drift"
DEFAULT_UPSTREAM = (Path.home() / ".claude" / "skills" / "gstack"
                    / "ship" / "sections" / "plan-completion.md")
SNAPSHOT_NAME = "plan-completion.md"   # lives in <pin-dir>/pin/
PIN_NAME = "pin.json"

# Text the wrapper's overrides name. A section that hashes fine but lost one of
# these would make the skill run Step 8.1 too, or find no Gate Logic to override.
ANCHORS = (
    "## Step 8: Plan Completion Audit",
    "## Step 8.1",
    "### Plan File Discovery",
    "### Gate Logic",
    "<base>",
    "Include in PR body",
    "Parent processing",
    '"total_items"',
)

EXIT_OK, EXIT_CANNOT, EXIT_CONFIRM = 0, 2, 3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def missing_anchors(text: str) -> list[str]:
    return [a for a in ANCHORS if a not in text]


def gstack_version(upstream: Path) -> str:
    # <gstack>/ship/sections/plan-completion.md -> <gstack>/VERSION
    v = upstream.resolve().parents[2] / "VERSION"
    return v.read_text().strip() if v.is_file() else "unknown"


def load_pin(pin_dir: Path) -> dict | None:
    """None when there is no pin file; {} when the file is not a pin-shaped object
    (unparseable, or valid JSON of another shape) — the caller reports PIN CORRUPT
    for {} rather than letting `.get` or a slice raise into an exit-1 traceback."""
    p = pin_dir / PIN_NAME
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return obj if isinstance(obj, dict) else {}


def cmd_check(a) -> int:
    upstream, pin_dir = Path(a.upstream).expanduser(), Path(a.pin_dir)
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream} — is gstack installed? "
              f"(git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack)",
              file=sys.stderr)
        return EXIT_CANNOT
    pin = load_pin(pin_dir)
    if pin is None:
        print(f"NO PIN: {pin_dir / PIN_NAME} does not exist — review the section with "
              f"`python3 scripts/spec-drift.py repin`, then accept it with --yes --sha",
              file=sys.stderr)
        return EXIT_CANNOT
    pinned = pin.get("sha256")
    pinned = pinned if isinstance(pinned, str) else ""
    snap = pin_dir / "pin" / SNAPSHOT_NAME
    try:
        snap_ok = bool(pinned) and snap.is_file() and sha256(snap) == pinned
    except OSError:
        snap_ok = False
    if not snap_ok:
        print(f"PIN CORRUPT: {snap} does not match {PIN_NAME} sha256 {pinned[:12] or '?'} — "
              f"pin.json and its snapshot are committed together; re-run repin",
              file=sys.stderr)
        return EXIT_CANNOT
    try:
        actual = sha256(upstream)
        text = upstream.read_text()
    except OSError as exc:
        print(f"UPSTREAM UNREADABLE: {upstream}: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    if actual != pinned:
        print("PIN MISMATCH: the upstream section changed shape.\n"
              f"  upstream  {upstream}\n"
              f"  sha256    {actual[:12]} (now) vs {pinned[:12]} "
              f"(pinned {pin.get('pinned_at')}, gstack {pin.get('gstack_version')})\n"
              f"  gstack    {gstack_version(upstream)} installed\n"
              "Verify the wrapper's overrides still fit the section, then: "
              "python3 scripts/spec-drift.py repin", file=sys.stderr)
        return EXIT_CANNOT
    missing = missing_anchors(text)
    if missing:
        print(f"ANCHORS MISSING: {', '.join(missing)} — the pinned section no longer carries "
              "text the wrapper's overrides name; fix skills/spec-drift/SKILL.md, then re-pin",
              file=sys.stderr)
        return EXIT_CANNOT
    print(f"PIN OK sha256={actual[:12]} gstack={pin.get('gstack_version')} upstream={upstream}")
    return EXIT_OK


def cmd_repin(a) -> int:
    upstream, pin_dir = Path(a.upstream).expanduser(), Path(a.pin_dir)
    if not upstream.is_file():
        print(f"UPSTREAM MISSING: {upstream}", file=sys.stderr)
        return EXIT_CANNOT
    snap = pin_dir / "pin" / SNAPSHOT_NAME
    try:
        old = snap.read_text().splitlines(keepends=True) if snap.is_file() else []
        new_text = upstream.read_text()
        current = sha256(upstream)
    except OSError as exc:
        print(f"UPSTREAM UNREADABLE: {exc}", file=sys.stderr)
        return EXIT_CANNOT
    new = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old, new, fromfile=f"pinned/{SNAPSHOT_NAME}",
                                     tofile=str(upstream)))
    pin = load_pin(pin_dir) or {}
    missing = missing_anchors(new_text)
    if not diff and pin.get("sha256") == current and not missing:
        print("PIN UNCHANGED: upstream matches the pin — nothing to do")
        return EXIT_OK
    if not a.yes:
        sys.stdout.writelines(diff)
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        if missing:
            print(f"\nREPIN BLOCKED: ANCHORS MISSING: {', '.join(missing)} — the wrapper's "
                  "overrides name text that no longer exists upstream; fix "
                  "skills/spec-drift/SKILL.md before re-pinning", file=sys.stderr)
            return EXIT_CANNOT
        print("\nANCHORS: all present")
        print(f"REPIN REQUIRES CONFIRMATION: +{added} -{removed} lines. Read the diff above, "
              f"verify the wrapper's overrides still match, then re-run with --yes --sha {current[:12]}")
        return EXIT_CONFIRM
    if missing:
        print(f"REPIN REFUSED: ANCHORS MISSING: {', '.join(missing)}", file=sys.stderr)
        return EXIT_CANNOT
    # --yes is bound to the bytes the diff run showed. Between that run and this
    # one a weekly gstack update can rewrite the file; accepting whatever is on
    # disk now would pin bytes nobody read.
    # At least the 12 chars the diff run printed: a 1-char "prefix" matches 1/16
    # of all digests, which is a guess, not a receipt.
    if not a.sha or len(a.sha) < 12 or not current.startswith(a.sha):
        print(f"REPIN REFUSED: --yes must carry the --sha printed by the diff run, 12+ hex chars "
              f"(upstream is now {current[:12]}, got {a.sha or 'nothing'}). "
              "Re-run repin without --yes and read the diff again.", file=sys.stderr)
        return EXIT_CANNOT
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes(upstream.read_bytes())
    digest = sha256(upstream)
    (pin_dir / PIN_NAME).write_text(json.dumps({
        "source": "garrytan/gstack (MIT) — ship/sections/plan-completion.md; snapshot is for --repin's diff only, never executed",
        "sha256": digest,
        "gstack_version": gstack_version(upstream),
        "pinned_at": date.today().isoformat(),
    }, indent=2) + "\n")
    print(f"PINNED sha256={digest[:12]} gstack={gstack_version(upstream)} — "
          f"commit {pin_dir / PIN_NAME} and {snap} together")
    return EXIT_OK


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="spec-drift.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("repin", cmd_repin)):
        s = sub.add_parser(name)
        s.add_argument("--upstream", default=str(DEFAULT_UPSTREAM),
                       help="the gstack section to pin (default: %(default)s)")
        s.add_argument("--pin-dir", default=str(DEFAULT_PIN_DIR),
                       help="directory holding pin.json and pin/ (default: the skill)")
        s.set_defaults(fn=fn)
    sub.choices["repin"].add_argument("--yes", action="store_true",
                                      help="accept the diff shown by a previous run and write the pin")
    sub.choices["repin"].add_argument("--sha", default=None,
                                      help="sha256 prefix printed by the diff run; required with --yes")
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Kjør testen og se den bestå**

Kjør: `pytest tests/unit/test_spec_drift_pin.py -q`
Forventet: `10 passed`.

- [ ] **Step 5: Hele suiten og lint**

Kjør: `pytest tests/unit scripts/cost-ledger -q` — forventet **388 passed** (378 + 10).
Kjør: `python3 scripts/lint-skills.py` — forventet `0 error(s), 2 warning(s) across 17 skills`. (E7 skanner det nye scriptet; ingen denylistet streng finnes i det.)

- [ ] **Step 6: Commit og push**

```bash
git add scripts/spec-drift.py tests/unit/test_spec_drift_pin.py
git commit -m "feat(spec-drift): hash pin for /ship Step 8's section — check + repin with diff

The skill will execute an upstream file this plugin does not own. check
makes 'same bytes' a verified fact (exit 0/2); repin shows the unified
diff against a committed snapshot and refuses to write without --yes, so
a weekly gstack update is read, not waved through."
git push -u origin feat/spec-drift
```

---

## Phase 2: `verdict` — Step 8-JSON til exit-kode

`/ship` gjør auditen om til AskUserQuestion-porter. Frittstående er det ingen å spørre ved en fasegrense; exit-koden *er* porten, og da kan ikke avbildningen være et skjønn modellen gjør forskjellig fra gang til gang.

**Files:**
- Modify: `scripts/spec-drift.py`
- Test: `tests/unit/test_spec_drift_verdict.py`

**Interfaces:**
- Consumes: Step 8 sin siste-linje-JSON `{"total_items":N,"done":N,"changed":N,"deferred":N,"unverifiable":N,"summary":"…"}` der `deferred` er NOT DONE-antallet (Step 8 sin egen bruk: «Parent processing» presenterer NOT DONE-porten når `deferred > 0`).
- Produces: `python3 scripts/spec-drift.py verdict [--json TEXT]` (standard: les stdin, bruk siste ikke-tomme linje) → skriver `SPEC-DRIFT: CLEAN (exit 0) — done=… changed=… partial=… not_done=… unverifiable=… of N`, eller `DRIFT (exit 1)`, eller `COULD-NOT-RUN (exit 2)`; exit-kode = tallet i parentes.
- Regler: `0` når `done + changed == total_items`; `2` når JSON mangler, mangler en av de seks nøklene, tellere ikke er heltall, `total_items <= 0`, eller PARTIAL-resten er negativ; ellers `1`.

- [ ] **Step 1: Skriv den feilende testen**

Opprett `tests/unit/test_spec_drift_verdict.py`:

```python
"""Guard scripts/spec-drift.py verdict — Step 8's JSON -> the standalone exit code.

/ship turns the audit into AskUserQuestion gates. Standalone there is nobody to
ask at a phase boundary; the exit code IS the gate, so its mapping cannot be a
judgement call the model makes differently on each run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"


def verdict(text: str):
    p = subprocess.run([sys.executable, str(SCRIPT), "verdict"],
                       capture_output=True, text=True, input=text)
    return p.returncode, p.stdout + p.stderr


def step8(total, done, changed=0, deferred=0, unverifiable=0):
    return json.dumps({"total_items": total, "done": done, "changed": changed,
                       "deferred": deferred, "unverifiable": unverifiable,
                       "summary": "- [x] ..."})


@pytest.mark.parametrize("line,code,label", [
    (step8(4, 4), 0, "CLEAN"),
    (step8(4, 3, changed=1), 0, "CLEAN"),
    (step8(4, 3, deferred=1), 1, "DRIFT"),
    (step8(4, 3, unverifiable=1), 1, "DRIFT"),
    (step8(4, 3), 1, "DRIFT"),                 # the remainder is PARTIAL (D5)
    (step8(0, 0), 2, "COULD-NOT-RUN"),         # no actionable items (D6)
])
def test_mapping(line, code, label):
    rc, out = verdict("PLAN COMPLETION AUDIT\n...\n" + line + "\n")
    assert rc == code
    assert f"SPEC-DRIFT: {label} (exit {code})" in out


def test_partial_is_reported_in_the_breakdown():
    rc, out = verdict(step8(5, 2, changed=1, deferred=1))
    assert rc == 1 and "partial=1" in out and "not_done=1" in out


def test_only_the_last_line_counts():
    """A JSON-looking line mid-report must not be mistaken for the contract."""
    rc, _ = verdict(step8(2, 0) + "\n" + step8(2, 2) + "\n")
    assert rc == 0


def test_missing_or_malformed_json_is_could_not_run():
    for text in ("no json here\n", '{"total_items": 3}\n', "{not json}\n", ""):
        rc, out = verdict(text)
        assert rc == 2, text
        assert "COULD-NOT-RUN" in out


@pytest.mark.parametrize("line,why", [
    (step8(2, 2, changed=1), "three verdicts for two items"),
    (step8(2, 3, changed=-1), "a negative count that makes done+changed add up to total"),
    (step8(1, True), "a boolean where a count belongs (int(True) == 1)"),
    (step8(2, 1.9, changed=1), "a float that int() would truncate into a CLEAN"),
    (step8(2, "2"), "a numeric string — the contract is integers, not whatever int() accepts"),
])
def test_inconsistent_counts_are_could_not_run(line, why):
    """Assert the message too: argparse rejecting an unknown subcommand is ALSO
    exit 2, so a bare exit-code check passes before verdict exists at all."""
    rc, out = verdict(line)
    assert rc == 2 and "COULD-NOT-RUN" in out, why


def test_fenced_last_line_is_tolerated():
    rc, _ = verdict("```json\n" + step8(1, 1) + "\n```\n")
    assert rc == 0
```

- [ ] **Step 2: Kjør testen og se den feile**

Kjør: `pytest tests/unit/test_spec_drift_verdict.py -q`
Forventet: 15 failed — argparse avviser `verdict` («invalid choice»), exit 2 med feil melding, så alle assertions på `SPEC-DRIFT:`-linjen feiler. Ingen skal bestå: en test som er grønn her, er grønn av feil grunn.

- [ ] **Step 3: Legg til `verdict` i scriptet**

I `scripts/spec-drift.py`:

(a) Erstatt docstring-avsnittet som slutter med `No difference: nothing to do, exit 0.` slik at det får en tredje linje — bytt

```
           snapshot + pin.json (exit 0). No difference: nothing to do, exit 0.
```

med

```
           snapshot + pin.json (exit 0). No difference: nothing to do, exit 0.
  verdict  map Step 8's last-line JSON to the standalone exit code:
           0 clean (every item DONE or CHANGED), 1 drift (anything else),
           2 could not audit (no JSON, malformed, or total_items == 0).
```

(b) Bytt konstantlinjen

```python
EXIT_OK, EXIT_CANNOT, EXIT_CONFIRM = 0, 2, 3
```

med

```python
EXIT_OK, EXIT_DRIFT, EXIT_CANNOT, EXIT_CONFIRM = 0, 1, 2, 3
JSON_KEYS = ("total_items", "done", "changed", "deferred", "unverifiable", "summary")
```

(c) Sett inn rett før `def main(argv=None) -> int:`:

```python
def last_json_line(text: str) -> dict | None:
    """The last non-empty line, parsed — or None. A trailing ``` fence is skipped."""
    for line in reversed(text.splitlines()):
        line = line.strip().strip("`")
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        return obj if isinstance(obj, dict) else None
    return None


def cmd_verdict(a) -> int:
    text = a.json if a.json is not None else sys.stdin.read()
    obj = last_json_line(text)
    if obj is None or any(k not in obj for k in JSON_KEYS):
        print("SPEC-DRIFT: COULD-NOT-RUN (exit 2) — last line is not Step 8's JSON "
              f"({', '.join(JSON_KEYS)})", file=sys.stderr)
        return EXIT_CANNOT
    counts = [obj[k] for k in JSON_KEYS[:5]]
    # The contract is integers. bool is an int subclass, and int() happily eats
    # "2" and 1.9 — each a way for a malformed line to read as CLEAN. Exact type.
    if any(type(c) is not int for c in counts):
        print("SPEC-DRIFT: COULD-NOT-RUN (exit 2) — counts are not integers", file=sys.stderr)
        return EXIT_CANNOT
    total, done, changed, deferred, unver = counts
    if total <= 0:
        print("SPEC-DRIFT: COULD-NOT-RUN (exit 2) — plan has no actionable items "
              "(a design doc? prose claims are Fase 3)", file=sys.stderr)
        return EXIT_CANNOT
    if min(done, changed, deferred, unver) < 0:
        # A negative count can make done + changed == total look CLEAN.
        print("SPEC-DRIFT: COULD-NOT-RUN (exit 2) — negative count in the JSON", file=sys.stderr)
        return EXIT_CANNOT
    partial = total - done - changed - deferred - unver
    if partial < 0:
        print(f"SPEC-DRIFT: COULD-NOT-RUN (exit 2) — counts add up to more than "
              f"total_items={total}", file=sys.stderr)
        return EXIT_CANNOT
    breakdown = (f"done={done} changed={changed} partial={partial} "
                 f"not_done={deferred} unverifiable={unver} of {total}")
    if done + changed == total:
        print(f"SPEC-DRIFT: CLEAN (exit 0) — {breakdown}")
        return EXIT_OK
    print(f"SPEC-DRIFT: DRIFT (exit 1) — {breakdown}")
    return EXIT_DRIFT


```

(d) I `main`, rett etter linjen `sub.choices["repin"].add_argument(...)` (hele kallet), sett inn:

```python
    v = sub.add_parser("verdict")
    v.add_argument("--json", default=None,
                   help="JSON text (default: read stdin and use the last non-empty line)")
    v.set_defaults(fn=cmd_verdict)
```

- [ ] **Step 4: Kjør testen og se den bestå**

Kjør: `pytest tests/unit/test_spec_drift_verdict.py -q`
Forventet: `15 passed`.

- [ ] **Step 5: Hele suiten og lint**

Kjør: `pytest tests/unit scripts/cost-ledger -q` — forventet **403 passed** (388 + 15).
Kjør: `python3 scripts/lint-skills.py` — forventet `0 error(s), 2 warning(s)`.

- [ ] **Step 6: Commit og push**

```bash
git add scripts/spec-drift.py tests/unit/test_spec_drift_verdict.py
git commit -m "feat(spec-drift): verdict — Step 8's last-line JSON to exit 0/1/2

Standalone there is no AskUserQuestion gate, so the exit code is the
gate. Computed, not judged: 0 when every item is DONE or CHANGED, 1 on
any PARTIAL / NOT DONE / UNVERIFIABLE, 2 when the JSON is missing,
malformed, inconsistent, or reports zero actionable items."
git push
```

---

## Phase 3: Skillen, rutingen og release 2.52.0

Her blir wrapperen til. Fasen er stor fordi lint-reglene binder delene sammen: `skills/spec-drift/` uten `SKILL.md` feiler E1, `SKILL.md` uten omtale i `CLAUDE.md` feiler E3, og en ny skill uten versjonsbump og CHANGELOG bryter release-gaten. Alt lander i én commit.

**Files:**
- Create: `skills/spec-drift/SKILL.md`
- Create: `skills/spec-drift/pin.json` (via `repin --yes`)
- Create: `skills/spec-drift/pin/plan-completion.md` (via `repin --yes`)
- Modify: `CLAUDE.md:114` (rutingpunkt etter `verify-and-land`-punktet)
- Modify: `README.md:32` (antall) og `README.md:47` (punkt etter `/ios-visual-explore`)
- Modify: `skills/setup-routing/SKILL.md:171` (rad etter `ios-visual-explore`-raden)
- Modify: `skills/adapt/SKILL.md:175` (rad etter `ios-visual-explore`-raden)
- Modify: `skills/setup-routing/model-routing.md` (rad etter `ios-visual-explore`-raden i «Plugin-internal skills»)
- Modify: `.claude-plugin/plugin.json` (`2.51.1` → `2.52.0`)
- Modify: `CHANGELOG.md` (ny `## [2.52.0]`-entry øverst)
- Modify: `IDEAS.md` (Status-linjen i spec-drift-entryen)
- Test: `tests/unit/test_spec_drift_skill.py`

**Interfaces:**
- Consumes: `scripts/spec-drift.py check|repin|verdict` fra fase 1–2, nøyaktig slik grensesnittene der sier.
- Produces: `/superpowers-gstack:spec-drift <plan-path> [--base <ref>] [--section <path>]` og `/superpowers-gstack:spec-drift --repin [--section <path>]`. Utdata-rekkefølge på slutten av svaret: `Plan: … Base: …`, verdikt-linjen `SPEC-DRIFT: … (exit N)`, JSON på aller siste linje.
- Produces: kontraktstrenger som testen pinner (kopier dem ordrett): `The plan path is an argument, never discovered.`, `never edits source code`, `Do not commit, push`, `run_in_background: false`, `## Re-pin mode`.

- [ ] **Step 1: Skriv den feilende testen**

Opprett `tests/unit/test_spec_drift_skill.py`:

```python
"""Guard skills/spec-drift/SKILL.md — a wrapper that must stay a wrapper.

The failure this skill invites is not a crash but a slow copy: someone pastes
Step 8's text into SKILL.md "for robustness", brings back the plan-discovery
heuristics "for convenience", or drops the hash check "because it keeps
failing". Each is a one-line edit that turns the wrapper into a fork. These
tests make each of those edits red.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO / "skills" / "spec-drift"
SKILL = (SKILL_DIR / "SKILL.md").read_text()
UPSTREAM_PATH = "~/.claude/skills/gstack/ship/sections/plan-completion.md"


def test_skill_reads_the_upstream_section_from_disk():
    assert UPSTREAM_PATH in SKILL
    assert "<SECTION_PATH>" in SKILL and "Read this file in full" in SKILL, \
        "the dispatched subagent must be told to read the section, not handed a copy"


def test_skill_never_inlines_step_8():
    """Phrases that exist only in the upstream section. Any of them in SKILL.md
    means the text was copied — and the hash pin now guards a copy. The line
    budget is the structural half of the same guard: a paraphrased paste dodges
    the needles but not the size."""
    for needle in ("Path concreteness rule", "Be conservative with DONE",
                   "_PLAN_SLUG=", "VAS-449", "Validator detection"):
        assert needle not in SKILL, f"{needle!r} is Step 8 text — read it from disk, do not paste it"
    assert SKILL.count("\n") < 300, \
        "Step 8 alone is ~190 lines; a wrapper that grew past 300 has probably swallowed it"


def test_skill_has_no_plan_discovery_heuristics():
    for needle in (r"-mmin", r"ls -t", r"grep -l", r"\.gstack/plans", r"\.claude/plans"):
        assert not re.search(needle, SKILL), f"{needle!r} is a discovery fallback — the plan path is an argument"
    assert "The plan path is an argument, never discovered." in SKILL


def test_hash_check_runs_before_the_audit_is_dispatched():
    check = SKILL.index('spec-drift.py" check')
    dispatch = SKILL.index("run_in_background: false")
    assert check < dispatch


def test_repin_shows_the_diff_and_asks_before_writing():
    repin = SKILL[SKILL.index("## Re-pin mode"):]
    shown = repin.index('spec-drift.py" repin')
    ask = repin.index("AskUserQuestion")
    yes = repin.index("repin --yes")
    assert shown < ask < yes, "diff first, then the question, then --yes"


def test_output_contract_matches_step_8():
    for key in ("total_items", "done", "changed", "deferred", "unverifiable", "summary"):
        assert f'"{key}"' in SKILL
    for code in ("exit 0", "exit 1", "exit 2"):
        assert code in SKILL
    assert 'spec-drift.py" verdict' in SKILL, "the exit code is computed, not judged"


def test_skill_reports_only():
    assert re.search(r"never\s+(edits?|modif(y|ies))\s+(source|code)", SKILL, re.I)
    assert "Do not commit, push" in SKILL


def test_pin_and_snapshot_are_committed_together():
    pin = json.loads((SKILL_DIR / "pin.json").read_text())
    snapshot = SKILL_DIR / "pin" / "plan-completion.md"
    assert pin["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert pin["gstack_version"] != "unknown"


def test_skill_is_routed_everywhere_the_lint_does_not_check():
    """Lint E3 checks CLAUDE.md only. The two generator tables, the model-routing
    table and the README are where every OTHER project learns the skill exists."""
    for rel in ("skills/setup-routing/SKILL.md", "skills/adapt/SKILL.md",
                "skills/setup-routing/model-routing.md", "README.md"):
        assert "superpowers-gstack:spec-drift" in (REPO / rel).read_text(), rel
```

- [ ] **Step 2: Kjør testen og se den feile**

Kjør: `pytest tests/unit/test_spec_drift_skill.py -q`
Forventet: samlingsfeil (`FileNotFoundError` på `skills/spec-drift/SKILL.md` ved import) — 1 error, 0 passed.

- [ ] **Step 3: Skriv `skills/spec-drift/SKILL.md`**

Opprett katalogen og filen med nøyaktig dette innholdet:

````markdown
---
name: spec-drift
description: |
  Standalone plan-vs-code audit on any branch: runs /ship Step 8's plan-completion
  section from disk (hash-pinned) against an explicit plan and base. Report, JSON,
  exit code. Never edits code.
---

# /superpowers-gstack:spec-drift

Does this plan still match the code? `/ship` already answers that — Step 8, the
Plan Completion Audit — but only at merge time, only inside a twenty-step
pipeline, and never on a branch that is not shipped. This skill runs that same
audit standalone. It is a **wrapper**: the audit text is gstack's, read from disk
at run time; this file holds only what differs when nothing is being shipped.

Invoke with:

```
/superpowers-gstack:spec-drift <plan-path> [--base <ref>] [--section <path>]
/superpowers-gstack:spec-drift --repin [--section <path>]
```

- `<plan-path>` — required. A plan with actionable items: `docs/superpowers/plans/*.md`
  or a `progress.md`. The plan path is an argument, never discovered.
- `--base <ref>` — the diff baseline. Default: the repo's default branch
  (`origin/HEAD`, else the first of `origin/main`, `origin/master`, `main`,
  `master` that exists). Pass an older commit to see drift that accumulated on
  the default branch across many small merges.
- `--section <path>` — override the upstream section path. For the hash-guard
  test only; the default is `~/.claude/skills/gstack/ship/sections/plan-completion.md`.
- `--repin` — accept a changed upstream section after reading its diff (below).
  Does no audit.

`SKILL_DIR` below is this skill's base directory, as the Skill tool reports it.
The mechanical half — the pin and the exit code — lives in
`"$SKILL_DIR/../../scripts/spec-drift.py"`; nothing below is decided by reading
the report and guessing.

## Contract

Same human-readable report as `/ship` Step 8, same JSON on the last line —
`{"total_items":N,"done":N,"changed":N,"deferred":N,"unverifiable":N,"summary":"…"}`,
where `"deferred"` counts NOT DONE items exactly as Step 8 uses it — plus a
verdict line just above the JSON:

| Verdict line | Meaning | Exit |
|---|---|---|
| `SPEC-DRIFT: CLEAN (exit 0)` | every item DONE or CHANGED | 0 |
| `SPEC-DRIFT: DRIFT (exit 1)` | any PARTIAL, NOT DONE or UNVERIFIABLE item | 1 |
| `SPEC-DRIFT: COULD-NOT-RUN (exit 2)` | pin mismatch, unreadable plan, empty diff, no actionable items, no JSON | 2 |

**What "exit" means for a Markdown skill.** A skill cannot return a process
status. The verdict line *is* this skill's exit code — structured text, computed
by `spec-drift.py verdict`, never judged from the report. A caller that needs a
real process status runs that same command on the final JSON line:

```bash
python3 "$SKILL_DIR/../../scripts/spec-drift.py" verdict <<'JSON'
<the JSON line the skill ended with>
JSON
echo "exit=$?"     # 0 / 1 / 2 — no prose parsed anywhere
```

Fail closed: when in doubt the answer is 2, never 0. This skill never edits source code,
the plan, or the upstream section — it reports. Write-back into the plan and a
drift ledger are Fase 2 of the spec
(`docs/superpowers/specs/2026-09-07-spec-drift-design.md`), not this skill.

## Phase 0 — refuse early

| Condition | Do this |
|---|---|
| No `<plan-path>` (and no `--repin`) | Print the usage block above, then `SPEC-DRIFT: COULD-NOT-RUN (exit 2) — plan path is required`. Stop. |
| Plan path missing or unreadable | `COULD-NOT-RUN (exit 2)`, naming the path. Stop. |
| Not a git repository | `COULD-NOT-RUN (exit 2) — the audit is a diff; there is no diff without git`. Stop. |
| Plan is not under `docs/superpowers/plans/` and not named `progress.md` | Warn once: design docs carry prose, not actionable items, and will come back `COULD-NOT-RUN` (prose claims are Fase 3). Continue anyway. |

Resolve the base and make sure there is a diff to audit against. Paste the two
user-supplied values inside **single quotes**, verbatim; if a value itself
contains a single quote, refuse with exit 2 rather than escaping it:

```bash
PLAN='<plan-path>'                 # single-quoted verbatim — a $( ), backtick or $ in a path is inert
BASE='<--base value, or empty>'
[ -f "$PLAN" ] || { echo "plan '$PLAN' is not a readable file"; exit 2; }
if [ -z "$BASE" ]; then
  HEAD_REF=$(git symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/||')
  for c in "$HEAD_REF" origin/main origin/master main master; do
    [ -n "$c" ] && git rev-parse -q --verify --end-of-options "$c^{commit}" >/dev/null 2>&1 && BASE=$c && break
  done
fi
git rev-parse -q --verify --end-of-options "$BASE^{commit}" >/dev/null 2>&1 || { echo "base '$BASE' is not a commit"; exit 2; }
[ -n "$(git diff --stat "$BASE...HEAD" 2>/dev/null)" ] || { echo "empty diff $BASE...HEAD — pass --base <older-commit>"; exit 2; }
echo "PLAN=$PLAN BASE=$BASE"
```

Every candidate is verified as a commit before it is used — a dangling
`origin/HEAD` falls through to the next candidate instead of ending the run —
and the ref that verified is kept as written (`origin/main`, not `main`): in a
fresh clone the remote-tracking ref exists and the local one may not.
`--end-of-options` keeps a value beginning with `-` from being read as a flag.
An empty diff is exit 2, not "everything NOT DONE": on the default branch with
the default base there is nothing to audit against, and the fix is an older
`--base`. Note what `exit 2` inside a block does: it ends that one Bash call.
It does not end the skill — you do, by printing the `SPEC-DRIFT: COULD-NOT-RUN
(exit 2)` verdict line and stopping. The number is the message, not the
mechanism.

## Phase 1 — the pin, before anything is read

```bash
python3 "$SKILL_DIR/../../scripts/spec-drift.py" check   # add --upstream "<--section value>" when given
```

Exit 0 prints `PIN OK …`: continue. Anything else: print the script's stderr
verbatim — it names both hashes, the installed gstack version and the way out —
then `SPEC-DRIFT: COULD-NOT-RUN (exit 2)` and stop. **Never run the audit past
a failed check**, and never edit the upstream file to make it pass: the section
is gstack's, regenerated on their side from a template, and a local edit is
overwritten by the next update. The check is the whole reason this wrapper can
claim to run the audit `/ship` runs, rather than a copy of it.

## Re-pin mode (`--repin`)

The pin breaks whenever gstack changes the section, which is often — gstack
auto-updates weekly. Re-pinning is deliberate, in steps, and never blind:

1. Show what changed:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" repin   # add --upstream when --section was given
   ```
   Exit 0 with `PIN UNCHANGED`: say so and stop. Exit 2 with `REPIN BLOCKED:
   ANCHORS MISSING`: the section no longer carries text the overrides below
   name — that needs a fix to this file first, not a re-pin; say which anchors
   and stop. Exit 3: the unified diff is on stdout, followed by `ANCHORS: all
   present` — show the diff to the user in full, not summarised.
2. The anchors are checked mechanically (the eight strings in `ANCHORS` in
   `spec-drift.py`: the Step 8 and 8.1 headings, Plan File Discovery, Gate
   Logic, `<base>`, Include in PR body, Parent processing, `"total_items"`).
   What the script cannot judge is meaning: read the diff against the overrides
   in Phase 2 below and say, in one or two sentences, whether any override now
   contradicts what the section says — a renamed verdict, a new gate, a changed
   JSON key. If one does, say which — that is also a fix to this file, not a
   re-pin.
3. Ask with `AskUserQuestion`: accept the new section as the pinned one?
   Options: **Accept** (recommended when every override still fits) / **Not
   now**. End your message at this question.
4. On Accept, pass back the sha the diff run printed — `--yes` is refused
   without it, and refused if the file changed since the diff was shown:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" repin --yes --sha <the 12 hex chars from the diff run>
   ```
   then remind the user that `skills/spec-drift/pin.json` and
   `skills/spec-drift/pin/plan-completion.md` must be committed together — the
   pin lives in the plugin, not on this machine.

## Phase 2 — dispatch the audit

Step 8 says to run as a subagent, in the foreground, and that executing it
inline forfeits the fresh-context isolation. That holds here. Invoke the
`Agent` tool with `subagent_type: "general-purpose"`, `run_in_background: false`,
`description: "spec-drift audit"`, and this prompt with the three placeholders
filled (`<SECTION_PATH>` is the upstream path or the `--section` value):

```
You are the dispatched subagent for a standalone plan-completion audit
(superpowers-gstack:spec-drift). Read this file in full, then execute ONLY its
`## Step 8: Plan Completion Audit` section — stop where `## Step 8.1` begins;
Step 8.1, "Prior Learnings" and Step 8.2 are not part of this run:

  <SECTION_PATH>

Overrides. Each replaces the part of Step 8 it names; everything else in Step 8
applies verbatim — the extraction rules, the verification modes, the verdict
definitions and their cautions.

1. You ARE the subagent Step 8 says to dispatch. Do not dispatch another agent;
   execute the quoted subagent prompt yourself.
2. "Plan File Discovery": skip it entirely. The plan file is <PLAN_PATH> — no
   conversation-context lookup, no content search, no freshness fallback, no
   relevance validation. If it is unreadable, emit the JSON line with
   total_items 0 and the reason in "summary".
3. Wherever Step 8 says `<base>` or `origin/<base>`, use exactly <BASE_REF>.
   The diff is `git diff <BASE_REF>...HEAD`; the log is
   `git log <BASE_REF>..HEAD --oneline`.
4. "Gate Logic": do not use AskUserQuestion and do not wait for anyone.
   Classify every item, print the Output Format block, and stop. The gate's
   decisions are made by the caller from your JSON. Skip "Include in PR body"
   and "Parent processing".
5. Report only. Do not commit, push, edit the plan, or edit any file.
6. Your LAST line is the JSON object Step 8 specifies, with exactly its keys:
   total_items, done, changed, deferred, unverifiable, summary — where
   deferred is the NOT DONE count. Nothing after it.
```

Wait for it (Step 8's own budget: about ten minutes). If it returns without a
parseable JSON last line, or fails outright, do what Step 8 itself prescribes,
once: run the same Step 8 inline in your own context with the same overrides.
If that also yields no JSON, do not guess a result — `SPEC-DRIFT: COULD-NOT-RUN
(exit 2)`.

## Phase 3 — verdict and output

1. Separate the subagent's reply into two parts: the JSON line at its end, and
   everything above it. Print the part above — the human-readable report
   (`PLAN COMPLETION AUDIT … COMPLETION: …`) — verbatim. Do not print the JSON
   here; it appears exactly once, as the last line of your response (step 3).
2. Compute the exit code from the JSON line — never by reading the report:
   ```bash
   python3 "$SKILL_DIR/../../scripts/spec-drift.py" verdict <<'JSON'
   <the JSON line>
   JSON
   ```
   It prints the `SPEC-DRIFT: … (exit N)` line with a breakdown
   (`done= changed= partial= not_done= unverifiable= of N`) and exits N. If the
   object arrived pretty-printed over several lines, collapse it to one line
   first — the contract is one line, and `verdict` reads exactly one.
3. End the response with, in this order: `Plan: <PLAN_PATH>  Base: <BASE_REF>`,
   the verdict line, and the JSON as the very last line — so a caller such as
   `/superpowers-gstack:autoimplement` can take the code from the verdict line
   and the counts from the JSON without parsing prose.

## What this skill is not

- Not `/ship`. It runs one of ship's sections; it merges, tests and ships nothing.
- Not `/superpowers-gstack:pitfall-verification`. Pitfall asks "would this work?"
  of an artifact seen from inside; this asks "does the artifact match reality?".
- Not a replacement for the plan-fidelity rule in CLAUDE.md ("fix the plan in the
  same commit as the divergence"). That rule prevents; this catches what it missed.
- Not a fork of Step 8. A change to the audit itself belongs upstream, in
  `garrytan/gstack`.
````

- [ ] **Step 4: Lag pinnen fra disk**

```bash
python3 scripts/spec-drift.py repin
```

Forventet: exit 3 og hele seksjonen som `+`-linjer (det finnes ingen tidligere pin), så `ANCHORS: all present` og `re-run with --yes --sha <12 hex-tegn>`. Får du `REPIN BLOCKED: ANCHORS MISSING` i stedet, har upstream endret struktur siden planen ble skrevet: stopp, og rett overstyringene i SKILL.md (Step 3) før du pinner. Les så gjennom diffen og bekreft at overstyringene fortsatt stemmer *i mening* — verdikt-navnene, JSON-linjen med `total_items`, `done`, `changed`, `deferred`, `unverifiable`, `summary`. Sjekk også `shasum -a 256 ~/.claude/skills/gstack/ship/sections/plan-completion.md` mot `e329e5ef76991a…` fra Global Constraints — er den ulik, har gstack oppdatert seg siden planen ble skrevet; ankrene over er da det du verifiserer ekstra nøye. Deretter, med sha-en diffkjøringen skrev ut:

```bash
python3 scripts/spec-drift.py repin --yes --sha <de 12 hex-tegnene fra forrige kommando>
python3 scripts/spec-drift.py check
cat skills/spec-drift/pin.json
```

Forventet: `PINNED …`, så `PIN OK sha256=… gstack=1.81.0.0 …` (eller den installerte versjonen), og `pin.json` med `source`, `sha256`, `gstack_version`, `pinned_at`.

- [ ] **Step 5: Ruting i `CLAUDE.md`**

Sett inn dette punktet rett etter `verify-and-land`-punktet i «Key routing rules» (linje 114, punktet som begynner `- "I fixed it but I don't see it in the app"`):

```markdown
- "Does this plan still match the code?", spec drift / plan drift, audit a plan on a branch that is not being shipped, mechanical plan check at a phase boundary → invoke /superpowers-gstack:spec-drift <plan-path> [--base <ref>]. Runs /ship Step 8's plan-completion section standalone — read from disk at run time and sha256-pinned (`--repin` shows the upstream diff and asks before accepting), explicit plan path (no discovery), explicit base (default `git diff <default-branch>...HEAD`; an older commit surfaces drift accumulated on main). Same report and last-line JSON as Step 8, plus exit 0 clean / 1 drift / 2 could not run. Report only — never edits code or the plan; write-back and a drift ledger are Fase 2 of the spec.
```

- [ ] **Step 6: Rutingtabellene i de to generatorene**

Sett inn nøyaktig denne raden **rett etter** `ios-visual-explore`-raden i Utility-tabellen — i `skills/setup-routing/SKILL.md` (linje 171) **og** i `skills/adapt/SKILL.md` (linje 175). Samme tekst begge steder:

```markdown
| `/superpowers-gstack:spec-drift` | Any project with plans in `docs/superpowers/plans/` — standalone "does this plan still match the code?" audit: runs `/ship` Step 8's plan-completion section from disk (hash-pinned) against an explicit plan and base, on any branch, shipped or not. Report + JSON + exit 0/1/2; never edits code. |
```

- [ ] **Step 7: Model-routing-raden**

I `skills/setup-routing/model-routing.md`, tabellen «Plugin-internal skills (superpowers-gstack)», sett inn rett etter `ios-visual-explore`-raden:

```markdown
| `/superpowers-gstack:spec-drift`             | sonnet    |
```

Begrunnelse (skal ikke inn i filen): auditen er en general-purpose-subagent som leser plan og diff og dømmer per punkt — samme klasse arbeid som `quality-review`, som står på `sonnet`.

- [ ] **Step 8: README**

I `README.md`: bytt `- **Claude Code Plugin** with sixteen skills:` (linje 32) med `- **Claude Code Plugin** with eighteen skills:` (tallet var allerede ett bak — det er 17 kataloger i `skills/` før denne, 18 etter). Sett så inn dette punktet rett etter `/ios-visual-explore`-punktet (linje 47):

```markdown
  - `/spec-drift` — standalone "does this plan still match the code?" audit, invoked as `/superpowers-gstack:spec-drift <plan-path> [--base <ref>]`. Wraps `/ship` Step 8's plan-completion section: read from `~/.claude/skills/gstack/ship/sections/plan-completion.md` at run time, never copied, sha256-pinned in `skills/spec-drift/pin.json` (`--repin` shows the upstream diff and asks before accepting). Explicit plan path — no discovery heuristics — and explicit `--base` (an older commit surfaces drift that accumulated on the default branch). Same report and last-line JSON as Step 8 plus exit `0` clean / `1` drift / `2` could not run, so `/autoimplement` can call it at phase boundaries. Runs on branches that are never shipped. Report only; write-back and a drift ledger are Fase 2 of `docs/superpowers/specs/2026-09-07-spec-drift-design.md`.
```

- [ ] **Step 9: Versjon, CHANGELOG, IDEAS**

`.claude-plugin/plugin.json`: `"version": "2.51.1"` → `"version": "2.52.0"`.

`CHANGELOG.md`: sett inn rett etter `# Changelog` og den tomme linjen, før `## [2.51.1]`. Bruk dagens dato (`date +%F`):

```markdown
## [2.52.0] - <YYYY-MM-DD>

An assessment of a third-party `--verify <spec>` skill turned out to be a survey of
what this repo already had: `/ship` Step 8 (the Plan Completion Audit) is stronger
than the alternative on the axis that matters — it knows the diff cannot prove
everything (`DIFF-VERIFIABLE` vs `CROSS-REPO` vs `EXTERNAL-STATE`). What it lacked
was a way to be invoked at all outside a twenty-step ship pipeline, on a branch that
will never be shipped, or against a baseline older than the branch. Design:
`docs/superpowers/specs/2026-09-07-spec-drift-design.md`. This is its Fase 1.

### Added — `/superpowers-gstack:spec-drift`
- A **wrapper, not a fork**. `/ship` is upstream gstack and its section is
  generated from a template there, so this plugin can neither patch it nor make
  `/ship` call anything. The skill reads
  `~/.claude/skills/gstack/ship/sections/plan-completion.md` from disk at run time
  and dispatches Step 8 as a foreground subagent with six overrides: no plan
  discovery (the path is an argument), `<base>` is an argument, no
  AskUserQuestion gates, report only, stop before Step 8.1, JSON last.
- **Hash-pinned** (`skills/spec-drift/pin.json` + a byte snapshot used only to
  show diffs). `scripts/spec-drift.py check` exits 2 on any mismatch and the skill
  refuses to run; `repin` prints the unified diff and refuses to write without
  `--yes`. gstack updates weekly, so the pin will break often — that is the point:
  a guard overridden without showing what changed trains away its own effect.
- **Same contract as Step 8** — same report, same last-line JSON — plus
  `SPEC-DRIFT: CLEAN|DRIFT|COULD-NOT-RUN (exit 0|1|2)` computed by
  `scripts/spec-drift.py verdict`, so `/autoimplement` can call it mechanically.
  Fail closed: empty diff, unreadable plan, zero actionable items and pin
  mismatch are all exit 2, never 0.
- Routed in `CLAUDE.md`, both generator tables, `model-routing.md` (sonnet) and the
  README. 34 unit tests across `test_spec_drift_pin.py`,
  `test_spec_drift_verdict.py`, `test_spec_drift_skill.py` — the last one is
  omission tests: Step 8 text pasted into SKILL.md, a discovery heuristic brought
  back, or the check moved after the dispatch each turn the suite red.
- Not in this release, by design: write-back into the plan and the drift ledger
  (Fase 2), the spec-blind inventory agent, prose-claim extraction and the
  security category (Fase 3).
```

`IDEAS.md`: i spec-drift-entryen, bytt Status-avsnittet

```markdown
**Status.** In progress (2026-09-07) — fase 1 godkjent for planlegging på `feat/spec-drift`; fase 2–3 fortsatt deferred. Fullt designdokument med begrunnelse, motforestillinger og verifiseringsplan: `docs/superpowers/specs/2026-09-07-spec-drift-design.md`.
```

med

```markdown
**Status.** Fase 1 implementert i 2.52.0 på `feat/spec-drift` (`skills/spec-drift/SKILL.md`, `scripts/spec-drift.py`); plan: `docs/superpowers/plans/2026-09-07-spec-drift.md`. Fase 2–3 fortsatt deferred — vurderes hver for seg etter at fase 1 har vært i drift (måleform: andel reelle funn etter ti kjøringer). Fullt designdokument med begrunnelse, motforestillinger og verifiseringsplan: `docs/superpowers/specs/2026-09-07-spec-drift-design.md`.
```

- [ ] **Step 10: Kjør testen og se den bestå**

Kjør: `pytest tests/unit/test_spec_drift_skill.py -q`
Forventet: `9 passed`.

- [ ] **Step 11: Hele suiten og lint**

Kjør: `pytest tests/unit scripts/cost-ledger -q` — forventet **412 passed** (403 + 9).
Kjør: `python3 scripts/lint-skills.py` — forventet `0 error(s), 2 warning(s) across 18 skills`. Blir det rødt, er de sannsynlige årsakene: E3 (punktet i `CLAUDE.md` mangler eller staver `spec-drift` feil), E4 (CHANGELOG-overskriften matcher ikke `2.52.0` tegn for tegn), E2 (`spec-drift.py` staves annerledes i SKILL.md enn i `scripts/`), W1 som *error* skjer ikke, men sjekk at `description` er ≤ 30 ord (den er 28).

- [ ] **Step 12: Commit og push**

```bash
git add skills/spec-drift/SKILL.md skills/spec-drift/pin.json skills/spec-drift/pin/plan-completion.md \
        tests/unit/test_spec_drift_skill.py \
        CLAUDE.md README.md skills/setup-routing/SKILL.md skills/adapt/SKILL.md \
        skills/setup-routing/model-routing.md \
        .claude-plugin/plugin.json CHANGELOG.md IDEAS.md
git commit -m "feat(spec-drift): standalone plan-vs-code audit wrapping /ship Step 8 (2.52.0)

Reads gstack's plan-completion section from disk at run time and
dispatches it as a foreground subagent with six overrides — no plan
discovery, base as argument, no AskUserQuestion gates, report only,
stop before Step 8.1, JSON last. sha256-pinned; the skill refuses to run
on a mismatch and --repin shows the diff before writing. Same report and
JSON as Step 8 plus exit 0/1/2 so autoimplement can call it mechanically.
Routed in CLAUDE.md, both generator tables, model-routing and README."
git push
```

---

## Phase 4: Verifisering — ekvivalens mot `/ship` Step 8, hash-guard, stående alarm

> **MANUELL FASE — koster noen cent og krever et menneske.** Den kjører seks subagent-audits (tre via skillen, tre via `/ship` som stoppes etter Step 8) og en ekte `AskUserQuestion`. Hvis du er en subagent dispatchet av `/superpowers-gstack:autoimplement`: gjør ingenting i denne fasen og avslutt med terminatoren
> `BLOCKED Phase 4 is manual — a human runs the six audits and stops /ship after Step 8; costs API cents`.
> Fasen utføres av brukeren i en interaktiv sesjon, med fase 1–3 committet og pushet.

Dette er specens «Verifisering hvis fase 1 bygges», punkt 1–4, pluss den stående formen av hash-guarden (D8). Målet er *ikke* bytelik utdata — to kjøringer av samme prosainstruks er ikke deterministiske. Målet er lik `total_items` og lik dom på DONE/NOT DONE-aksen over tre kjøringer av hver. Uenighet begrenset til `PARTIAL`↔`CHANGED` er støy; uenighet på DONE/NOT DONE er regresjon.

**Files:**
- Create: `tests/fixtures/spec-drift/stale-plan.md`
- Create: `tests/unit/test_spec_drift_upstream_alarm.py`
- Modify: `docs/superpowers/specs/2026-09-07-spec-drift-design.md` (ny seksjon `## Verifisering — resultat (fase 1)` nederst)
- Modify: `docs/superpowers/plans/2026-09-07-spec-drift.md` (avkryssing, per plan-fidelity-regelen)

**Interfaces:**
- Consumes: `/superpowers-gstack:spec-drift`, `scripts/spec-drift.py check`, `/ship` (gstack 1.81.0.0 eller nyere) — alle slik fase 3 etterlot dem.
- Produces: en resultattabell i specen, og én stående test som skippes i CI og feiler lokalt når upstream-seksjonen har endret seg siden pinning.

- [ ] **Step 1: Forutsetninger**

```bash
git status --porcelain            # tomt
git log --oneline main..HEAD      # fase 1–3-commitene (pluss spec/IDEAS/plan-commitene) synlige
bash tests/run.sh --unit          # specens egen kommando: 412 passed (= pytest tests/unit scripts/cost-ledger -q)
python3 scripts/lint-skills.py    # 0 error(s)
python3 scripts/spec-drift.py check   # PIN OK
git fetch origin && git merge origin/main --no-edit   # så /ship sitt Step 3 ikke lager en merge-commit midt i kjøringene
```

Er `check` ikke `PIN OK`, oppdaterte gstack seg mellom fase 3 og nå: kjør `/superpowers-gstack:spec-drift --repin`, les diffen, aksepter, commit pinnen — og noter det i resultattabellen.

- [ ] **Step 2: Fixture-planen — kjent stale ved konstruksjon**

Ekvivalensmålet trenger en plan med færre enn 50 punkter (Step 8 kapper ved 50, og *hvilke* 50 som velges ville selv vært støy) og med en kjent fasit. Denne planen har fem punkter som finnes på `feat/spec-drift` og fire fra fase 2–3 som ikke finnes — altså nøyaktig specens egen situasjon. Opprett `tests/fixtures/spec-drift/stale-plan.md`:

```markdown
# spec-drift fixture plan

Fixture for the Fase-1 equivalence run — see Phase 4 of
`docs/superpowers/plans/2026-09-07-spec-drift.md`. Audited against `main...HEAD`
on branch `feat/spec-drift` (branch slug `feat-spec-drift`, repo
`superpowers-gstack`). The nine checkbox items below are the whole content; the
value of this file is the verdicts they produce, so they stay as written.

### Fase 1 — Wrapper

- [ ] Create `scripts/spec-drift.py` with subcommands `check`, `repin` and `verdict`
- [ ] Create `skills/spec-drift/SKILL.md` that reads `~/.claude/skills/gstack/ship/sections/plan-completion.md` at run time
- [ ] Create `skills/spec-drift/pin.json` carrying a sha256 of the upstream section
- [ ] Add a routing row for `superpowers-gstack:spec-drift` to `skills/adapt/SKILL.md`
- [ ] Test that a one-line change upstream is refused, in `tests/unit/test_spec_drift_pin.py`

### Fase 2 — Write-back and ledger

- [ ] Create the append-only drift ledger `.gstack/spec-drift.jsonl`
- [ ] Add `--accept <claimId>` to `scripts/spec-drift.py` that appends a fingerprint `claimId:kind:path` to the ledger
- [ ] Write confirmed CHANGED findings back into the plan under plan-fidelity's rules

### Fase 3 — Independent inventory

- [ ] Add a `--whole-tree` mode with verdicts PRESENT / ABSENT / UNVERIFIABLE
```

Overskriftene er med vilje `### Fase N —`, ikke `## Phase N:` — det siste er `autoimplement` sitt fase-regex, og en fixture som matcher det ville blitt lest som fire ekstra faser i *denne* planen. Forordet er bevisst uten imperativer («do not …», «keep …»): Step 8 trekker ut imperative setninger som handlingspunkter, og et tiende punkt ville ødelagt fasiten. Forordet navngir grennavnet i *slug-form* (`feat-spec-drift`) og repo-navnet ordrett, fordi Step 8 sitt innholdssøk grepper etter nettopp de to strengene (`$BRANCH` med `/` byttet til `-`, og `$REPO`) — se Step 5. Fasit: punkt 1–5 DONE, punkt 6–9 NOT DONE, `total_items` 9. Commit fixturen før kjøringene, ellers refuserer `/ship` på uren tre:

```bash
git add tests/fixtures/spec-drift/stale-plan.md
git commit -m "test(spec-drift): fixture plan for the Fase-1 equivalence run"
git push
```

- [ ] **Step 3: Hash-guard (specens punkt 4)**

Én linje endret i en *lokal kopi* — den ekte filen røres ikke:

```bash
SCRATCH=$(mktemp -d) && : "${SCRATCH:?mktemp failed}"
cp ~/.claude/skills/gstack/ship/sections/plan-completion.md "$SCRATCH/plan-completion.md"
printf '\n<!-- spec-drift hash-guard test: one extra line -->\n' >> "$SCRATCH/plan-completion.md"
python3 scripts/spec-drift.py check --upstream "$SCRATCH/plan-completion.md"; echo "exit=$?"
```

Forventet: `PIN MISMATCH` på stderr med begge hashene og `repin`-hintet, `exit=2`. Deretter gjennom skillen:

```
/superpowers-gstack:spec-drift tests/fixtures/spec-drift/stale-plan.md --section <SCRATCH>/plan-completion.md
```

Forventet: skillen skriver scriptets stderr, så `SPEC-DRIFT: COULD-NOT-RUN (exit 2)`, og **ingen** subagent dispatches. Noter utfallet.

- [ ] **Step 4: Tre frittstående kjøringer (specens punkt 1 og 3)**

Tre ganger, hver i en **ny** sesjon (`/clear` mellom), på `feat/spec-drift`:

```
/superpowers-gstack:spec-drift tests/fixtures/spec-drift/stale-plan.md --base main
```

Noter per kjøring: `total_items`, mengden punkter dømt DONE, mengden dømt NOT DONE, eventuelle PARTIAL/CHANGED/UNVERIFIABLE, verdikt-linjen og exit-koden. Forventet: `total_items` 9, DONE = {1,2,3,4,5}, NOT DONE = {6,7,8,9}, `SPEC-DRIFT: DRIFT (exit 1)`. Dette er samtidig specens punkt 3: grenen shippes ikke, `/ship` kjøres ikke, auditen virker.

- [ ] **Step 5: Tre `/ship`-kjøringer stoppet etter Step 8 (specens punkt 2)**

`/ship` sitt Step 8 kjører som subagent med frisk kontekst: den ser verken brukerens meldinger eller denne sesjonen, og dens innholdssøk leter kun i `~/.gstack/projects/<slug>`, `~/.claude/plans`, `~/.codex/plans` og `.gstack/plans` — aldri i `tests/fixtures/`. Å nevne stien i samtalen er derfor ikke nok (det var planens første, feilaktige antakelse; tredje lens fant den). Fixturen må ligge der Step 8 søker *først*, utenfor repoet så treet forblir rent, og inneholde grennavnets slug-form som Step 8 grepper etter. Slug-beregningen under er kopiert ordrett fra Step 8 sitt eget script, så stien blir den samme:

```bash
_PLAN_SLUG=$(git remote get-url origin 2>/dev/null | sed 's|.*[:/]\([^/]*/[^/]*\)\.git$|\1|;s|.*[:/]\([^/]*/[^/]*\)$|\1|' | tr '/' '-' | tr -cd 'a-zA-Z0-9._-') || true
_PLAN_SLUG="${_PLAN_SLUG:-$(basename "$PWD" | tr -cd 'a-zA-Z0-9._-')}"
mkdir -p ~/.gstack/projects/"$_PLAN_SLUG"
cp tests/fixtures/spec-drift/stale-plan.md ~/.gstack/projects/"$_PLAN_SLUG"/spec-drift-stale-plan.md
ls -t ~/.gstack/projects/"$_PLAN_SLUG"/*.md | xargs grep -l "feat-spec-drift" | head -1   # må skrive ut kopien
```

Den siste linjen er Step 8 sitt eget søk; skriver den ut en annen fil, er det den `/ship` kommer til å auditere — flytt eller vent, ikke fortsett. Så, tre ganger, hver i en ny sesjon:

1. Kjør `/ship`. La den gå gjennom Step 0–7 (base-deteksjon, pre-flight, merge av base, tester, dekningsaudit). Svar nøkternt på det den spør om underveis, uten å endre filer.
2. Når blokken `PLAN COMPLETION AUDIT … COMPLETION: …` og JSON-linjen fra Step 8 vises: noter de samme feltene som i Step 4, **pluss** `PLAN_FILE:`-linjen subagenten skrev (beviset på at den auditerte kopien av fixturen og ikke noe annet).
3. Step 8 sin port spør om NOT DONE-punktene (A/B/C). Velg **A) Stop** — det avslutter `/ship` uten versjonsbump, CHANGELOG-skriving eller PR.

Etter tredje kjøring: `rm ~/.gstack/projects/"$_PLAN_SLUG"/spec-drift-stale-plan.md`, ellers finner neste ekte `/ship` i dette repoet fixturen i stedet for den virkelige planen.

Forventet: `total_items` 9, samme DONE- og NOT DONE-mengder som i Step 4, i alle tre. Gir en kjøring `No plan file detected` eller `total_items` 0, fant ikke Step 8 kopien — det er et oppsettproblem (kjør `ls`/`grep`-linjen over igjen), ikke et datapunkt; kjøringen telles ikke. Skulle `/ship` bumpe versjon eller opprette PR likevel, avbryt og tilbakestill kun det (`git reset --hard` er **ikke** lov uten stash — se git-hygiene; bruk `git revert` på en eventuell commit).

- [ ] **Step 6: Den stående alarmen (D8)**

Opprett `tests/unit/test_spec_drift_upstream_alarm.py`:

```python
"""Layer 2 of the pin: the maintainer-machine alarm.

`spec-drift.py check` refuses at use time. This fires earlier — on any
`pytest tests/unit` run on a machine where gstack is installed — so a weekly
gstack auto-update that reshapes Step 8 is seen before anyone needs the skill.
Skipped in CI (no upstream there), like test_lint_upstream_skills' roster
check. Failing here is the designed outcome, not flakiness: read the diff with
`python3 scripts/spec-drift.py repin`, accept it with --yes, commit the pin.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "spec-drift.py"
UPSTREAM = (Path.home() / ".claude" / "skills" / "gstack"
            / "ship" / "sections" / "plan-completion.md")


def test_pin_matches_installed_gstack_when_present():
    if not UPSTREAM.is_file():
        pytest.skip("no gstack install on this machine (expected in CI)")
    p = subprocess.run([sys.executable, str(SCRIPT), "check"], capture_output=True, text=True)
    assert p.returncode == 0, (
        "upstream plan-completion.md no longer matches skills/spec-drift/pin.json — "
        "gstack updated Step 8. Review: python3 scripts/spec-drift.py repin ; accept: "
        "python3 scripts/spec-drift.py repin --yes ; then commit pin.json + pin/.\n" + p.stderr)
```

Kjør: `pytest tests/unit/test_spec_drift_upstream_alarm.py -q` — forventet `1 passed` (pinnen fra fase 3 matcher). At den *kan* feile er allerede bevist i Step 3: testen kjører nøyaktig samme `check`-kommando som der ga exit 2 på den endrede kopien, bare uten `--upstream`-overstyringen.

- [ ] **Step 7: Skriv resultatene der neste leser ser dem**

Legg til nederst i `docs/superpowers/specs/2026-09-07-spec-drift-design.md`:

```markdown
## Verifisering — resultat (fase 1, <YYYY-MM-DD>)

Plan under test: `tests/fixtures/spec-drift/stale-plan.md` (9 punkter; 5 finnes på `feat/spec-drift`, 4 er fase 2–3). Baseline `main`. gstack <versjon>, pin sha256 `<12 tegn>`.

| Kjøring | Verktøy | total_items | DONE | NOT DONE | Annet | Exit |
|---|---|---|---|---|---|---|
| 1 | spec-drift | 9 | 1–5 | 6–9 | — | 1 |
| 2 | spec-drift | … | … | … | … | … |
| 3 | spec-drift | … | … | … | … | … |
| 4 | /ship Step 8 | … | … | … | … | (port: A) |
| 5 | /ship Step 8 | … | … | … | … | (port: A) |
| 6 | /ship Step 8 | … | … | … | … | (port: A) |

**Dom på DONE/NOT DONE-aksen:** <lik i 6/6 | avvik: …>. **Hash-guard (punkt 4):** én tilføyd linje i lokal kopi → `PIN MISMATCH`, exit 2, ingen audit dispatchet. **Hull 3:** kjøring 1–3 gjort på en gren `/ship` aldri fullførte.

**Ti-kjøringers-målet** (andel reelle funn) starter nå; føres her etter hvert.
```

Fyll tabellen med de faktiske observasjonene — ikke med fasiten.

**Feilgrenen — den eneste veien videre ved avvik.** Hvis noen av de seks kjøringene gir `total_items` ≠ 9, eller to kjøringer er uenige om ett punkts plass på DONE/NOT DONE-aksen, eller hash-guarden i Step 3 ikke nektet: **stopp her.** Ikke kryss av noe i planen, ikke skriv Step 8 sin commit. Skriv avviket inn i tabellen med kjøringsnummer og hva som var ulikt, og skriv under tabellen én setning om hva som er den sannsynlige årsaken (en overstyring subagenten ikke fulgte? et punkt fixturen formulerer tvetydig? en Step 8-regel wrapperen ikke bevarer?). Rett årsaken i en egen commit merket `fix(spec-drift): …`, og **kjør alle seks auditene på nytt** — ikke bare den som avvek — før tabellen fylles på nytt. Først når tabellen viser lik dom i 6/6 fortsetter Step 8. Et avvik på DONE/NOT DONE-aksen er en regresjon i wrapperen; `PARTIAL`↔`CHANGED` alene er støy og noteres i «Annet»-kolonnen uten å stoppe.

- [ ] **Step 8: Oppdater planen, commit, push — kun etter 6/6**

Kryss av fase 1–3 sine steg i denne planen med commit-SHA-ene fra `git log --oneline main..HEAD` (plan-fidelity: samme notasjon filen allerede bruker; fase 1–3 sine subagenter kan ikke gjøre det selv, planen står ikke i deres `Files:`-blokker). Fase 4 sine egne steg krysses av med markøren `(denne commiten)` i stedet for SHA — commiten som inneholder avkryssingen kan ikke inneholde sin egen SHA. Så, med tallene fra tabellen satt inn (ikke fra fasiten):

```bash
git add tests/unit/test_spec_drift_upstream_alarm.py \
        docs/superpowers/specs/2026-09-07-spec-drift-design.md \
        docs/superpowers/plans/2026-09-07-spec-drift.md
git commit -m "test(spec-drift): Fase-1 verification — <6>/6 equivalence with /ship Step 8, hash-guard, maintainer alarm

Six audits of a 9-item fixture plan (five present on the branch, four
Fase-2/3 items absent): the standalone skill (<3> runs) and /ship's own
Step 8 (<3> runs) agree on the DONE / NOT DONE axis in <6>/6 runs
(<other: PARTIAL/CHANGED noise, if any>). One added line in a local copy
of the section is refused with both hashes named and no audit
dispatched. A standing test now fails on any maintainer machine where
gstack has changed the section since the pin (skipped in CI)."
git push
```

- [ ] **Step 9: Specens siste krav — pitfall-verification på hele diffen**

Specen avslutter «Verifisering» med `superpowers-gstack:pitfall-verification` på diffen. `autoimplement` kjørte den per fase på fase 1–3; fase 4 sine endringer og helheten `main...HEAD` har ingen sett samlet. Kjør:

```
/superpowers-gstack:pitfall-verification --diff --diff-base main
```

Tier-gulvet beregnes av `scripts/classify-change.py` (instruksjonsflate under `skills/` er runtime, så gulvet er minst ship-worthy → Codex kjører). Funn som overlever synthesen rettes i en ny commit (`fix(spec-drift): …` — aldri `--amend` på pushet historikk), etterfulgt av `bash tests/run.sh --unit` og `python3 scripts/lint-skills.py`, og pitfall kjøres én gang til på den nye diffen. Et funn som viser at en av de seks auditene ville dømt annerledes, sender deg tilbake til Step 7 sin feilgren. Først når verdiktet er `CLEAN` er fasen ferdig.

Fase 4 er ferdig når tabellen står i specen med lik dom i 6/6, Step 9 er `CLEAN`, og `bash tests/run.sh --unit` viser **413 passed** lokalt (412 + 1; i CI 412 passed + 1 skipped). Landing er neste beslutning, ikke en del av denne fasen: `/ship` — den fulle pipelinen — kjører Step 8 en gang til på veien, som et sjuende datapunkt.

---

## Self-Review

**Spec-dekning (fase 1 og verifisering):**

| Krav i specen | Hvor |
|---|---|
| Leser `plan-completion.md` fra disk ved kjøring, utfører seksjonen | SKILL.md Phase 2 (fase 3); D3 |
| Null duplisert logikk — samme filbytes | D1–D3; `test_skill_never_inlines_step_8` |
| Hash-pin som feiler høyt; `--repin` viser diff og krever bekreftelse; pinnen committet i skillen | Fase 1 (`check`/`repin`), SKILL.md «Re-pin mode», `test_repin_shows_the_diff_and_asks_before_writing`, `test_pin_and_snapshot_are_committed_together` |
| Eksplisitt mål, ingen heuristikk | SKILL.md Phase 0 + override 2; `test_skill_has_no_plan_discovery_heuristics` |
| Planer, ikke specer (`docs/superpowers/plans/`, `progress.md`); prosa er fase 3 | SKILL.md Phase 0 advarsel; D6 (`total_items == 0` → exit 2) |
| Baseline som argument, fortsatt en diff, standard `git diff <base>...HEAD`; eldre commit lukker hull 5 | SKILL.md Phase 0 + override 3; D7 |
| Samme rapport, samme JSON på siste linje, exit 0/1/2 | SKILL.md «Contract» og Phase 3; fase 2 `verdict`; `test_output_contract_matches_step_8` |
| `autoimplement` kan kalle mekanisk | verdikt-linje + JSON sist; exit beregnet av script |
| Rører aldri upstream, redigerer aldri kildekode | SKILL.md Phase 1 («never edit the upstream file»), override 5, «What this skill is not»; `test_skill_reports_only` |
| Ingen ny tier-gate, ingen overlapp med pitfall/brainstorming | SKILL.md «What this skill is not» |
| Verifisering 1–4, tre kjøringer av hver, lik dom på DONE/NOT DONE | Fase 4 Step 3–5, resultattabellen og feilgrenen i Step 7 |
| Lint grønn inkl. routing coverage; `bash tests/run.sh --unit` | Hver fase kjører CI-kommandoen (samme suite som `tests/run.sh --unit`); fase 4 Step 1 kjører specens kommando ordrett; fase 3 ruting i fem filer |
| «Til slutt pitfall-verification på diffen» | Fase 4 Step 9 (hele `main...HEAD`; per-fase-kjøringene er `autoimplement` sine) |
| Ti-kjøringers-måling | Notert som startpunkt i resultatseksjonen (fase 4 Step 7) — selve målingen ligger utenfor planen |

**Placeholder-skann:** Ingen «TBD»/«TODO»/«fyll inn». `<YYYY-MM-DD>`, `<versjon>`, `<12 tegn>` og `…` i fase 4 Step 7 er celler som skal fylles med *målte* verdier — det er poenget med steget, ikke en utsettelse. `<plan-path>`, `<base>`, `<SECTION_PATH>`, `<PLAN_PATH>`, `<BASE_REF>` i SKILL.md er skillens egne substitusjonsplasser og skal stå slik i filen.

**Navnekonsistens på tvers av faser:** `scripts/spec-drift.py` med subkommandoene `check`, `repin [--yes]`, `verdict [--json]` og flaggene `--upstream`, `--pin-dir` — samme stavemåte i fase 1, 2, 3 (SKILL.md, testene) og 4. Exit-koder: `0/1/2` for skillen og `verdict`; `2` for `check`-avvik; `3` for `repin` uten `--yes` — `3` lekker aldri ut av skillen (SKILL.md oversetter den til «show the diff»). Pin-filer: `skills/spec-drift/pin.json` og `skills/spec-drift/pin/plan-completion.md` — samme stier i scriptets `DEFAULT_PIN_DIR`/`SNAPSHOT_NAME`, i SKILL.md «Re-pin mode», i `test_pin_and_snapshot_are_committed_together` og i fase 4 sin alarmtest. JSON-nøkler: `total_items, done, changed, deferred, unverifiable, summary` — identiske i `JSON_KEYS`, i SKILL.md override 6 og i begge tester som pinner dem. Kontraktstrenger testene leter etter finnes ordrett i SKILL.md: `The plan path is an argument, never discovered.`, `never edits source code`, `Do not commit, push`, `run_in_background: false`, `## Re-pin mode`, `spec-drift.py" check`, `spec-drift.py" repin`, `repin --yes`, `spec-drift.py" verdict`.

**Testtall** (CI-kommandoen `pytest tests/unit scripts/cost-ledger -q`): 378 → 388 (fase 1, +10) → 403 (fase 2, +15) → 412 (fase 3, +9) → 413 lokalt / 412 + 1 skipped i CI (fase 4, +1).
