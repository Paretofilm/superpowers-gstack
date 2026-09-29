# Worktrunk-integrasjon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Phase 0 and Phase 9 are interactive** (they use session tools and need the user's consent) — run them in the main session, not via `autoimplement`. Phases 1–8 are autoimplement-compatible once Phase 0 has passed.

**Goal:** Solo-landing uten pull request: worktrees brukes automatisk, og ferdig arbeid lander på `main` med én kommando etter lokale sjekker.

**Architecture:** Et lite Python-skript (`scripts/land-worktree.py`) gjør landingen med lås, forhåndssjekker og distinkte feilkoder, og aldri automatisk reparasjon. En ny `land`-skill kjenner skriptets sti og oversetter feilkoder til handling. En ny delt blokk (`worktrunk.md`) lærer alle adapterte prosjekter arbeidsmåten. Sesjonsskriptene flyttes til `git-common-dir` så et worktree ikke gjør en avbrutt økt usynlig.

**Tech Stack:** Python 3.12 (stdlib), bash, pytest, worktrunk `wt` 0.79.0, `gh`.

**Spec:** `docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md` (godkjent 2026-09-29). Fase 1 retter noen få steder i den; rettelsene er listet der.

## Global Constraints

- Målversjon: `3.4.0` (`.claude-plugin/plugin.json` og `## [3.4.0]` i `CHANGELOG.md`).
- Aldri `--no-hooks`, aldri `--yes` mot `wt`, aldri `git stash`, aldri `git reset` i landingsskriptet, aldri automatisk nytt forsøk.
- Blokkfiler er engelske, første linje er en H2 med `<!-- gstack-<navn>-vN -->`, og filen slutter med newline.
- Bruk `git add <bestemte stier>`, aldri `git add -A`. Ikke rør `CLAUDE.md`, `AGENTS.md` eller `JEV-FORSLAG.md` **på `main`** (brukerens uavklarte filer). Endringer i `CLAUDE.md` gjøres bare i dette worktreet.
- Commit-meldinger slutter med `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- `python3 scripts/lint-skills.py` grønn før hver commit som endrer `skills/`, `scripts/` eller `CLAUDE.md`.
- Ingen forkortelser i prosa uten forklaring; norsk prosa i dokumenter, engelsk i blokker, skill-filer og kode.
- Forventet testgrunnlinje på denne maskinen: `574 passed, 2 failed`. De to røde er `test_roster_matches_installed_upstream_when_present` og `test_pin_matches_installed_gstack_when_present` (ekte alarmer om gammel roster og pinne, ikke støy). Alt annet rødt er en feil planen har innført.

## Review Focus

Hver linje har en test i oppgaven som eier koden.

- Landingsskriptets lås blir liggende etter et krasj → gammel lås (død prosess) må ryddes, levende lås må avvise (Task 2.1).
- Sti med mellomrom (`my proj`) og gren med skråstrek (`feat/x`) → alle git- og `wt`-kall bruker argumentlister, aldri shell-strenger (Task 2.1 og 2.2, hele fixturen bruker mellomrom).
- `Landing mode: solo ` med etterfølgende mellomrom, eller linjen skrevet inne i en setning → skal feile lukket, ikke tolkes som `solo` (Task 2.1).
- Repo uten `origin` → lander lokalt uten push og uten å feile på `fetch` (Task 2.1).
- Primærmappen står på en annen gren enn `main` → `main` oppdateres uten å flytte primærmappens gren (Task 2.1).

## Fil-struktur

| Fil | Ansvar | Oppgave |
|---|---|---|
| `scripts/land-worktree.py` (ny) | Landing i én kommando | 2.1 |
| `tests/unit/test_land_worktree.py` (ny) | Kaster-repoer for kode 0, 2–13, 64 | 2.1, 2.2 |
| `.config/wt.toml` (ny) | Prosjektets `pre-merge`-sperre | 1.2 |
| `skills/adapt/blocks/worktrunk.md` (ny) | Utsendt regelblokk | 4.1 |
| `skills/adapt/blocks/git-hygiene.md` | v11→v12, peker til `land` | 4.2 |
| `scripts/adapt-claude-md.py`, `scripts/lint-skills.py`, `scripts/sync-own-claude-md.py` | Tre registre for den nye blokken | 4.1 |
| `skills/land/SKILL.md` (ny) | Finner skriptet og oversetter feilkoder | 3.1 |
| `scripts/capture-session-tail.sh`, `scripts/session-resume.sh` | Sesjonslogg og handoff via `git-common-dir` | 5.1 |
| `skills/autoimplement/SKILL.md` | Worktree ved start, landing til slutt | 6.1 |
| `scripts/check-branch-hygiene.sh` | Foreslår `land` og `wt step prune` | 7.1 |
| `.claude-plugin/plugin.json`, `CHANGELOG.md`, `README.md`, `CLAUDE.md` | Utgivelse | 8.1 |

---

## Phase 0: Verify the two tool assumptions

Mål: bekrefte det spesifikasjonen bare har lest, ikke kjørt. Denne fasen endrer ingen kode. Resultatene skrives inn i denne planen (seksjonen «Phase 0 results» nederst), slik at planen forblir sann mot virkeligheten.

### Task 0.1: `EnterWorktree` med `path`, og at arbeidsmappen følger med

**Files:**
- Modify: `docs/superpowers/plans/2026-09-29-worktrunk-integration.md` (seksjonen «Phase 0 results»)

- [ ] **Step 1: Opprett et kastbart `wt`-worktree**

Run: `wt switch --create scratch/enter-test --no-cd --format=json`
Expected: JSON med `"path"`, f.eks. `/Users/kjetilge/Developer/superpowers-gstack.scratch-enter-test`. Noter stien.

- [ ] **Step 2: Gå inn i det med verktøyet `EnterWorktree`**

Kall `EnterWorktree` med `path=<stien fra steg 1>`. Noter om et tillatelsesspørsmål dukket opp (pluginens `PermissionRequest`-hook skal godkjenne det automatisk).

- [ ] **Step 3: Bekreft at Bash-verktøyets arbeidsmappe er worktreet**

Run: `pwd && git rev-parse --abbrev-ref HEAD`
Expected: `pwd` er stien fra steg 1 og grenen er `scratch/enter-test`. Kommandoen skal virke uten `-C` og uten `cd`.

- [ ] **Step 4: Forlat og rydd**

Kall `ExitWorktree` med `action: "keep"`. Kjør deretter `wt remove scratch/enter-test`.
Expected: økten er tilbake i primærmappen, og `git worktree list` viser ikke lenger `scratch/enter-test`.

- [ ] **Step 5: Skriv resultatet inn i «Phase 0 results»** (PASS/FAIL, om det ble spurt om tillatelse, eventuell feiltekst ordrett).

### Task 0.2: Arver subagenter arbeidsmappen?

**Files:**
- Modify: `docs/superpowers/plans/2026-09-29-worktrunk-integration.md` («Phase 0 results»)

- [ ] **Step 1: Gjenta 0.1 steg 1–2 og bli stående i worktreet**

- [ ] **Step 2: Send en minimal subagent**

Kall `Agent` (type `general-purpose`) med prompten: `Run "pwd && git rev-parse --abbrev-ref HEAD" with the Bash tool and report the two output lines verbatim. Do nothing else.`
Expected: begge linjene viser worktreet og grenen `scratch/enter-test`.

- [ ] **Step 3: Rydd som i 0.1 steg 4, og skriv resultatet inn i «Phase 0 results»**

Hvis subagenten rapporterer primærmappen: Phase 6 må bruke reserven (variabelen `WT` og `git -C "$WT"`, se Task 6.1 «Reserve»). Skriv det eksplisitt.

### Task 0.3: Grunnlinje før endringer, og commit

**Files:**
- Modify: `docs/superpowers/plans/2026-09-29-worktrunk-integration.md`

- [ ] **Step 1: Mål grunnlinjen**

Run: `python3 scripts/lint-skills.py; python3 -m pytest -q -p no:cacheprovider 2>&1 | tail -4`
Expected: lint grønn; `574 passed, 2 failed` (de to alarmene i Global Constraints). Avviker tallet, noter det og stopp til det er forklart.

- [ ] **Step 2: Fyll «Phase 0 results» med de tre resultatene og grunnlinjen**

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-09-29-worktrunk-integration.md
git commit -m "docs(plan): phase 0 results — EnterWorktree, subagent cwd, baseline

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 1: Spec corrections and the project's pre-merge gate

### Task 1.1: Rett spesifikasjonen der planleggingen fant feil

Planleggingen fant fem ting spesifikasjonen har feil eller mangler. Plan-fidelity: spesifikasjonen rettes i samme commit.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md`

- [ ] **Step 1: `Landing mode`-linjen kan ikke ligge i blokken**

Erstatt beslutningsraden som begynner `| Kilde for \`Landing mode\` |` med:

```
| Kilde for `Landing mode` | Én linje `Landing mode: solo` eller `Landing mode: pr` i prosjektets `CLAUDE.md`, **utenfor den utsendte blokken**: `/adapt` erstatter blokker hele ved oppgradering og ville ellers stille nullstilt et valg om `pr`. Prosjektet setter den én gang. Mangler den, spør agenten brukeren og skriver linjen under en overskrift prosjektet eier. Skriptet leser den med et strengt mønster (`^Landing mode: (solo\|pr)$`) og **feiler lukket** (kode 2) ved manglende eller ugyldig verdi. |
```

I komponent 1: erstatt `Linjen \`Landing mode: solo\`.` med `Forklarer \`Landing mode\`-linjen (blokken inneholder den ikke selv).`

- [ ] **Step 2: Ny komponent 10 og to nye feilkoder**

Legg til etter rad 9 i komponenttabellen:

```
| 10 | `skills/land/SKILL.md` (ny) | En blokk i et annet prosjekts `CLAUDE.md` kan ikke peke på et skript i pluginen, men en skill kjenner sin egen basemappe. Skillen finner `land-worktree.py`, kaller det og oversetter feilkoder til handling. `git-hygiene`-blokken og `autoimplement` peker på skillen. |
```

Legg til to rader i feilkodetabellen, etter rad 13:

```
| 64 | Ikke et feature-worktree (mangler git, står på `main`, eller ugyldige argumenter) | Alt urørt. |
| 70 | `wt merge` feilet av en grunn skriptet ikke kjenner igjen | Skriptet skriver de siste linjene av `wt`-utskriften. Ingenting repareres. |
```

- [ ] **Step 3: `autoimplement` og handoff presiseres**

Erstatt setningen `Primærmappens skitne filer stopper ikke kjøringen med mindre de overlapper planens filer (da nevnes de).` med `Primærmappens skitne filer stopper ikke kjøringen. Overlapp med det landingen endrer fanges ved landing (kode 5), der tilstanden fortsatt er intakt.`

I komponent 9: erstatt `og \`handoff.md\`/\`progress.md\` slås opp i primærmappen` med `og \`handoff.md\` (gitignorert) slås opp i primærmappen; \`progress.md\` er sporet i git og leses fra worktreet`.

- [ ] **Step 4: Åpent punkt om de to røde testene løses**

Erstatt punktet `Skal de to \`_when_present\`-testene gjøres maskinuavhengige, eller utelates fra hooken? Avgjøres i planen.` med:

`De to røde testene (\`test_roster_matches_installed_upstream_when_present\`, \`test_pin_matches_installed_gstack_when_present\`) er ekte alarmer, ikke miljøstøy: roster mangler \`diagnosing-superpowers\`, og spec-drift-pinnen er fra gstack 1.84.1 mens 1.91.2 er installert. De utelates fra \`pre-merge\`-hooken med \`--deselect\` (de måler oppstrøms drift, ikke denne endringen), og vurderes eksplisitt i Phase 9 etter \`/gstack-upgrade\`.`

- [ ] **Step 5: Bekreft**

Run: `grep -c "utenfor den utsendte blokken\|skills/land/SKILL.md\|| 64 |\|| 70 |" docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md`
Expected: `4`.

### Task 1.2: `.config/wt.toml` med samme kommandoer som CI

**Files:**
- Create: `.config/wt.toml`

- [ ] **Step 1: Skriv filen**

```toml
# Prosjektets pre-merge-sperre. Kjøres av `wt merge` etter rebase og før main flyttes.
# Kommandoene er de samme som .github/workflows/lint.yml, og kjører samtidig (tabell).
# De to --deselect-testene måler oppstrøms drift (installert gstack/Superpowers mot
# roster og pinne), ikke denne endringen. De kjøres eksplisitt i planens Phase 9.

[pre-merge]
lint = "python3 scripts/lint-skills.py"
unit = "python3 -m pytest tests/unit -q -p no:cacheprovider --deselect tests/unit/test_lint_upstream_skills.py::test_roster_matches_installed_upstream_when_present --deselect tests/unit/test_spec_drift_upstream_alarm.py::test_pin_matches_installed_gstack_when_present"
contract = "for t in skills/*/tests/required-sections.test.sh; do bash \"$t\" || exit 1; done"
```

- [ ] **Step 2: Be brukeren godkjenne hooken (én gang)**

Skriv til brukeren: `Kjør dette én gang i terminalen: wt config approvals add` (eller `! wt config approvals add` i denne økten). Agenten bruker aldri `--yes`. Vent på svar.

- [ ] **Step 3: Verifiser at hooken er grønn på grunnlinjen**

Run: `wt hook pre-merge`
Expected: alle tre kommandoene fullfører uten feil (omtrent 2,5 minutter, den tregeste er testene). Er den rød, er det en feil som må forstås før hooken tas i bruk. Aldri `--no-hooks`.

- [ ] **Step 4: Commit**

```bash
git add .config/wt.toml docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md
git commit -m "feat(wt): pre-merge gate mirrors CI; correct spec after planning

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 2: The landing script

### Task 2.1: `scripts/land-worktree.py` og forhåndssjekk-testene

Testene bruker en **falsk `wt`** (et shell-skript som bare svarer på `config approvals list`), så de kjører uten worktrunk, også i CI. Forhåndssjekkene bruker bare git. Skriptet skrives i sin helhet her; landingsdelen (merge, push, opprydding) får sine tester mot ekte `wt` i Task 2.2 og skal rettes der hvis testene avslører feil.

**Files:**
- Create: `scripts/land-worktree.py`
- Create: `tests/unit/test_land_worktree.py`

**Interfaces:**
- Produces: kommandolinje `land-worktree.py [--worktree PATH] [--main-branch NAME] [--preflight-only] [--ci-wait SECONDS]`; siste stdout-linje er JSON (`{"landed": bool, ...}`); avslutningskoder 0, 2–13, 64, 70 som i spesifikasjonen. `land(a)` returnerer en dict eller kaster `Stop(code, message, state, commands)`.

- [ ] **Step 1: Skriv testene**

```python
"""scripts/land-worktree.py — solo landing in one command (spec 2026-09-29).

Preflight tests use a FAKE `wt` (a shell script answering only `config approvals
list`), so they run without worktrunk, in CI too. The landing tests in the second
half need the real `wt` and skip without it. Every path in the fixture contains a
space on purpose: an argument list that survives `my proj` survives everything a
shell string would have mangled.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "land-worktree.py"

APPROVED = "APPROVED\n↳ (none)\n\nUNAPPROVED\n↳ (none)\n"
UNAPPROVED = "APPROVED\n↳ (none)\n\nUNAPPROVED\n❯ pre-merge check:\n  true\n"
HOOK_TOML = '[pre-merge]\ncheck = "true"\n'


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def commit(repo, name, text, msg):
    (Path(repo) / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", msg)


@pytest.fixture
def lab(tmp_path):
    remote = tmp_path / "remote.git"
    primary = tmp_path / "my proj"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(primary)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(primary, "config", k, v)
    (primary / ".config").mkdir()
    (primary / ".config" / "wt.toml").write_text(HOOK_TOML)
    (primary / "CLAUDE.md").write_text("# proj\n\nLanding mode: solo\n")
    (primary / "shared.md").write_text("base\n")
    git(primary, "add", "-A")
    git(primary, "commit", "-qm", "init")
    git(primary, "remote", "add", "origin", str(remote))
    git(primary, "push", "-q", "-u", "origin", "main")
    wt = tmp_path / "my proj.feat-x"
    git(primary, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    commit(wt, "feature.md", "f\n", "feat: x")
    return SimpleNamespace(root=tmp_path, remote=remote, primary=primary, wt=wt)


def write_shim(root, approvals):
    d = root / "bin"
    d.mkdir(exist_ok=True)
    f = d / "wt"
    f.write_text("#!/bin/sh\nif [ \"$3\" = config ] && [ \"$4\" = approvals ]; then\n"
                 "cat <<'EOF'\n" + approvals + "EOF\nexit 0\nfi\nexit 99\n")
    f.chmod(0o755)
    return d


def land(lab, *args, shim=APPROVED, wt=None, env=None):
    path = "/usr/bin:/bin:/usr/local/bin"
    if shim is not None:
        path = f"{write_shim(lab.root, shim)}:{path}"
    e = {"HOME": str(lab.root), "PATH": path}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(wt or lab.wt),
                           "--ci-wait", "0", *args], capture_output=True, text=True, env=e)


def verdict(p):
    return json.loads(p.stdout.strip().splitlines()[-1])


# --- mode: fails closed -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "# proj\n",                                        # no line at all
    "# proj\n\nLanding mode: pr\n",                    # explicit pr
    "# proj\n\nLanding mode: solo \n",                 # trailing space
    "# proj\n\nSet Landing mode: solo in prose.\n",    # inside a sentence
    "# proj\n\nLanding mode: SOLO\n",                  # wrong case
])
def test_mode_other_than_exact_solo_fails_closed(lab, text):
    (lab.wt / "CLAUDE.md").write_text(text)
    git(lab.wt, "commit", "-qam", "chore: mode")
    p = land(lab, "--preflight-only")
    assert p.returncode == 2, p.stderr
    assert verdict(p)["landed"] is False


# --- hook presence, wt presence, approvals ------------------------------------

def test_no_pre_merge_hook_is_code_9(lab):
    (lab.wt / ".config" / "wt.toml").write_text('[post-start]\nx = "true"\n')
    git(lab.wt, "commit", "-qam", "chore: no gate")
    assert land(lab, "--preflight-only").returncode == 9


def test_wt_missing_is_code_8(lab):
    assert land(lab, "--preflight-only", shim=None).returncode == 8


def test_unapproved_hooks_is_code_3_and_names_the_command(lab):
    p = land(lab, "--preflight-only", shim=UNAPPROVED)
    assert p.returncode == 3
    assert "approvals add" in p.stderr and "--yes" not in p.stderr


# --- fetch, dirty worktree, main ahead ----------------------------------------

def test_fetch_failure_is_code_11(lab):
    git(lab.primary, "remote", "set-url", "origin", str(lab.root / "nowhere.git"))
    assert land(lab, "--preflight-only").returncode == 11


def test_dirty_worktree_is_code_13(lab):
    (lab.wt / "untracked.md").write_text("x\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 13 and "untracked.md" not in p.stdout   # message, not a crash


def test_local_main_ahead_of_origin_is_code_4(lab):
    commit(lab.primary, "local.md", "l\n", "chore: unpushed on main")
    p = land(lab, "--preflight-only")
    assert p.returncode == 4
    assert "unpushed on main" in p.stderr, "the commits that would ride along must be listed"


# --- overlap with the worktree that holds main --------------------------------

def test_dirty_file_the_branch_changes_is_code_5(lab):
    commit(lab.wt, "shared.md", "feature\n", "feat: touches shared")
    (lab.primary / "shared.md").write_text("dirt\n")
    p = land(lab, "--preflight-only")
    assert p.returncode == 5 and "shared.md" in p.stderr


def test_dirty_other_file_does_not_block(lab):
    (lab.primary / "unrelated.md").write_text("dirt\n")
    assert land(lab, "--preflight-only").returncode == 0


# --- primary on another branch: main is updated without a checkout ------------

def test_primary_on_other_branch_main_updated_without_touching_it(lab):
    git(lab.primary, "switch", "-q", "-c", "wip/other")
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    commit(other, "z.md", "z\n", "chore: someone else pushed")
    git(other, "push", "-q", "origin", "main")
    before = git(lab.primary, "rev-parse", "HEAD")
    p = land(lab, "--preflight-only")
    assert p.returncode == 0, p.stderr
    assert git(lab.primary, "rev-parse", "HEAD") == before, "the wrong branch must not move"
    assert git(lab.primary, "rev-parse", "main") == git(other, "rev-parse", "HEAD")


# --- no origin: land locally, no push -----------------------------------------

def test_repo_without_origin_passes_preflight(lab):
    git(lab.primary, "remote", "remove", "origin")
    assert land(lab, "--preflight-only").returncode == 0


# --- lock ---------------------------------------------------------------------

def lock_dir(lab):
    return Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "gstack-land.lock"


def test_live_lock_is_code_12_and_left_alone(lab):
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(os.getpid()))
    assert land(lab, "--preflight-only").returncode == 12
    assert d.exists(), "someone else's lock is never removed"


def test_stale_lock_is_cleared_and_released(lab):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    d = lock_dir(lab)
    d.mkdir()
    (d / "pid").write_text(str(dead.pid))
    assert land(lab, "--preflight-only").returncode == 0
    assert not d.exists(), "the lock must be released on exit"


# --- usage --------------------------------------------------------------------

def test_landing_from_main_is_code_64(lab):
    assert land(lab, "--preflight-only", wt=lab.primary).returncode == 64


def test_bad_argument_is_code_64_not_2(lab):
    assert land(lab, "--no-such-flag").returncode == 64
```

- [ ] **Step 2: Kjør testene og bekreft at de feiler**

Run: `python3 -m pytest tests/unit/test_land_worktree.py -q -p no:cacheprovider`
Expected: FAIL (skriptet finnes ikke: `can't open file`).

- [ ] **Step 3: Skriv skriptet**

```python
#!/usr/bin/env python3
"""Land a wt worktree on main in one command — solo landing, no pull request.

Design: docs/superpowers/specs/2026-09-29-worktrunk-integration-design.md

Contract: exit 0 = landed (possibly with warnings). Any other code = stopped, in the
state the spec's exit-code table names. The script never runs `git reset`, never
retries by itself, never passes --yes or --no-hooks to wt, and never removes the
worktree (the caller leaves it first, then runs `wt remove`).

Usage: land-worktree.py [--worktree PATH] [--main-branch NAME] [--preflight-only]
                        [--ci-wait SECONDS]
The last stdout line is a JSON verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MODE, UNAPPROVED, MAIN_AHEAD, OVERLAP, HOOK_RED, PUSH, NO_WT, NO_HOOK, REBASE, FETCH, LOCKED, DIRTY = (
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
USAGE, UNKNOWN = 64, 70

MODE_RE = re.compile(r"^Landing mode: (solo|pr)$", re.M)
HOOK_RE = re.compile(r"^[ \t]*(\[\[?pre-merge\]\]?[ \t]*$|pre-merge[ \t]*=)", re.M)


class Stop(Exception):
    def __init__(self, code, message, state="", commands=()):
        super().__init__(message)
        self.code, self.message, self.state, self.commands = code, message, state, list(commands)


def sh(*args, cwd=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def git(repo, *args):
    return sh("git", "-C", str(repo), *args)


def out(repo, *args):
    r = git(repo, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def landing_mode(worktree: Path):
    f = worktree / "CLAUDE.md"
    if not f.is_file():
        return None
    m = MODE_RE.search(f.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def has_pre_merge_hook(worktree: Path) -> bool:
    f = worktree / ".config" / "wt.toml"
    return f.is_file() and bool(HOOK_RE.search(f.read_text(encoding="utf-8", errors="replace")))


def unapproved(worktree: Path) -> bool:
    r = sh("wt", "-C", str(worktree), "config", "approvals", "list")
    if r.returncode != 0:
        return False   # unknown: `wt merge` decides, and its own message maps to code 3
    parts = r.stdout.split("UNAPPROVED", 1)
    return len(parts) == 2 and "❯" in parts[1]


def worktrees(repo) -> list[dict]:
    items, cur = [], {}
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = {}
        elif line.startswith("worktree "):
            cur["path"] = Path(line[len("worktree "):])
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].removeprefix("refs/heads/")
    return items


def default_branch(repo) -> str:
    ref = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return ref.split("/", 1)[1] if ref and "/" in ref else "main"


def dirty_files(repo) -> set[str]:
    parts = git(repo, "status", "--porcelain", "-z").stdout.split("\0")
    files, i = set(), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        files.add(entry[3:])
        if entry[0] in "RC" and i < len(parts):   # rename/copy: the old path follows
            files.add(parts[i])
            i += 1
    return files


def changed(repo, *rev_args) -> set[str]:
    r = git(repo, "diff", "--name-only", "-z", *rev_args)
    return {p for p in r.stdout.split("\0") if p} if r.returncode == 0 else set()


class Lock:
    """Atomic per-repo lock: `mkdir` either creates the directory or fails."""

    def __init__(self, common_dir: Path):
        self.dir = common_dir / "gstack-land.lock"

    def _stale(self) -> bool:
        try:
            pid = int((self.dir / "pid").read_text())
        except (OSError, ValueError):
            try:   # no pid yet: only stale if it has been that way for a while
                return time.time() - self.dir.stat().st_mtime > 5
            except OSError:
                return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def __enter__(self):
        for _ in range(2):
            try:
                self.dir.mkdir()
                (self.dir / "pid").write_text(str(os.getpid()))
                return self
            except FileExistsError:
                if self._stale():
                    shutil.rmtree(self.dir, ignore_errors=True)
                    continue
                break
        raise Stop(LOCKED, f"another landing holds {self.dir}",
                   commands=[f"cat '{self.dir}/pid'   # the process that holds it"])

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def _classify(r, wt) -> Stop:
    text = r.stdout + r.stderr
    tail = "\n".join(text.strip().splitlines()[-12:])
    if "Cannot prompt for approval" in text or "needs approval" in text:
        return Stop(UNAPPROVED, "the project's hooks are not approved",
                    commands=[f"wt -C '{wt}' config approvals add"])
    if "pre-merge command failed" in text:
        return Stop(HOOK_RED, "a pre-merge check failed — fix it (never --no-hooks) and land again",
                    state="the branch was rebased onto main; main was not moved; worktree and branch stand",
                    commands=[f"wt -C '{wt}' hook pre-merge"])
    if ("Rebase onto" in text and "incomplete" in text) or "CONFLICT" in text:
        return Stop(REBASE, "rebasing onto main hit a conflict",
                    state="a rebase is open in the worktree; main was not moved",
                    commands=[f"git -C '{wt}' status",
                              f"git -C '{wt}' rebase --abort   # or resolve, then: git rebase --continue"])
    if "conflicting uncommitted changes" in text:
        return Stop(OVERLAP, "the worktree holding main has uncommitted changes in a file this landing touches",
                    state="nothing moved", commands=[tail])
    return Stop(UNKNOWN, "wt merge failed for a reason this script does not recognise", state=tail)


def _ci_watch(wt, main, sha, wait, warnings):
    if not shutil.which("gh"):
        warnings.append("gh is not installed — CI status not checked")
        return None
    deadline = time.time() + wait
    while True:
        r = sh("gh", "run", "list", "--commit", sha, "--branch", main, "--json", "databaseId,url", "-L", "1",
               cwd=str(wt))
        try:
            runs = json.loads(r.stdout) if r.returncode == 0 else []
        except ValueError:
            runs = []
        if runs:
            return f"gh run watch {runs[0]['databaseId']} --exit-status"
        if time.time() >= deadline:
            break
        time.sleep(3)
    warnings.append(f"no CI run found for {sha[:9]} within {wait}s")
    return None


def land(a) -> dict:
    wt = Path(a.worktree).resolve()
    common = out(wt, "rev-parse", "--path-format=absolute", "--git-common-dir")
    branch = out(wt, "rev-parse", "--abbrev-ref", "HEAD")
    if not common or not branch:
        raise Stop(USAGE, f"{wt} is not a git worktree")
    main = a.main_branch or default_branch(wt)
    if branch in ("HEAD", main):
        raise Stop(USAGE, f"{wt} is on '{branch}', not a feature branch — land from the feature worktree")
    with Lock(Path(common)):
        return _land_locked(a, wt, Path(common), branch, main)


def _land_locked(a, wt, common, branch, main) -> dict:
    mode = landing_mode(wt)
    if mode != "solo":
        raise Stop(MODE, (f"Landing mode is '{mode}', not 'solo'" if mode else
                          "CLAUDE.md has no exact 'Landing mode: solo' or 'Landing mode: pr' line (fails closed)"),
                   commands=["mode 'pr': use /ship", "no line: ask the user once, then write it under a heading the project owns"])
    if not has_pre_merge_hook(wt):
        raise Stop(NO_HOOK, "no pre-merge hook in .config/wt.toml — nothing would gate this landing",
                   commands=["propose a .config/wt.toml whose [pre-merge] runs the same commands as CI; the user approves it"])
    if not shutil.which("wt"):
        raise Stop(NO_WT, "wt (worktrunk) is not installed",
                   commands=["fall back to: git worktree add, then /superpowers:finishing-a-development-branch"])
    if unapproved(wt):
        raise Stop(UNAPPROVED, "the project's hooks are not approved",
                   commands=[f"wt -C '{wt}' config approvals add"])
    has_origin = out(wt, "remote", "get-url", "origin") is not None
    if has_origin and git(wt, "fetch", "origin").returncode != 0:
        raise Stop(FETCH, "git fetch origin failed")
    dirty = git(wt, "status", "--porcelain").stdout.strip()
    if dirty:
        raise Stop(DIRTY, "the worktree has uncommitted work — wt merge would commit it for you",
                   state=dirty, commands=["commit it, or move it: git switch -c wip/<topic>"])
    mw = next((w for w in worktrees(wt) if w.get("branch") == main), None)
    feature = changed(wt, f"{main}...{branch}")
    theirs = changed(wt, main, f"origin/{main}") if has_origin else set()
    if mw:
        clash = sorted(dirty_files(mw["path"]) & (feature | theirs))
        if clash:
            raise Stop(OVERLAP, f"uncommitted files in {mw['path']} overlap this landing: {', '.join(clash)}",
                       state="nothing moved", commands=["commit them or move them to their own branch — never stash"])
    if has_origin:
        ahead = git(wt, "log", "--oneline", f"origin/{main}..{main}").stdout.strip()
        if ahead:
            raise Stop(MAIN_AHEAD, f"local {main} has commits that are not on origin (they would ride along unchecked)",
                       state=ahead)
        r = (git(mw["path"], "merge", "--ff-only", f"origin/{main}") if mw
             else git(wt, "fetch", "origin", f"{main}:{main}"))
        if r.returncode:
            raise Stop(MAIN_AHEAD, f"local {main} cannot fast-forward to origin/{main}", state=r.stderr.strip())
    base = out(wt, "rev-parse", f"origin/{main}") if has_origin else None
    if a.preflight_only:
        return {"landed": False, "preflight": "ok", "branch": branch, "main": main,
                "main_worktree": str(mw["path"]) if mw else None}

    merge = sh("wt", "-C", str(wt), "merge", "--no-squash", "--no-remove")
    if merge.returncode:
        raise _classify(merge, wt)
    if git(wt, "merge-base", "--is-ancestor", branch, main).returncode != 0:
        raise Stop(UNKNOWN, f"wt merge reported success but '{branch}' is not in {main}")

    warnings, pushed = [], None
    if has_origin:
        git(wt, "fetch", "origin")
        stop_cmds = [f"git -C '{wt}' log --oneline origin/{main}..{main}",
                     f"resolve in the worktree that has {main} checked out: git pull --rebase",
                     f"git -C '{wt}' push origin {main}"]
        if out(wt, "rev-parse", f"origin/{main}") != base:
            raise Stop(PUSH, f"origin/{main} moved while the checks ran — nothing was pushed",
                       state=f"local {main} already contains your commits; worktree and branch stand",
                       commands=stop_cmds)
        r = git(wt, "push", "origin", main)
        if r.returncode:
            raise Stop(PUSH, f"push of {main} was rejected", state=r.stderr.strip()[-600:], commands=stop_cmds)
        pushed = out(wt, "rev-parse", main)
        if git(wt, "ls-remote", "--exit-code", "--heads", "origin", branch).returncode == 0:
            r = git(wt, "push", "origin", "--delete", branch)
            if r.returncode:
                warnings.append(f"could not delete origin/{branch}: {r.stderr.strip()[-200:]}")
    watch = _ci_watch(wt, main, pushed, a.ci_wait, warnings) if pushed else None
    if not has_origin:
        warnings.append("no origin remote: landed locally, nothing was pushed")
    primary = str(common.parent)
    remaining = ["if this session stands inside the worktree: ExitWorktree with action keep",
                 f"wt -C '{primary}' remove {branch}"]
    if watch:
        remaining.append(f"{watch}   # run in the background; a red run means fixing {main} next")
    return {"landed": True, "branch": branch, "main": main, "sha": pushed or out(wt, "rev-parse", main),
            "watch": watch, "remaining": remaining, "warnings": warnings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Land a worktree on main (solo landing, no pull request).")
    ap.add_argument("--worktree", default=os.getcwd())
    ap.add_argument("--main-branch")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--ci-wait", type=int, default=30)
    ap.error = lambda msg: (print(f"land-worktree: {msg}", file=sys.stderr), sys.exit(USAGE))
    a = ap.parse_args(argv)
    try:
        v = land(a)
    except Stop as s:
        print(f"STOPPED (exit {s.code}): {s.message}", file=sys.stderr)
        if s.state:
            print(f"State: {s.state}", file=sys.stderr)
        for c in s.commands:
            print(f"  {c}", file=sys.stderr)
        print(json.dumps({"landed": False, "code": s.code, "message": s.message}))
        return s.code
    if v.get("landed"):
        print(f"LANDED {v['branch']} on {v['main']} ({(v['sha'] or '')[:9]})")
        for line in v["remaining"]:
            print(f"  remaining: {line}")
        for w in v["warnings"]:
            print(f"  warning: {w}")
    else:
        print("preflight ok")
    print(json.dumps(v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Kjør testene og bekreft at de består**

Run: `python3 -m pytest tests/unit/test_land_worktree.py -q -p no:cacheprovider`
Expected: alle bestått. Feiler en test, les feilmeldingen og rett skriptet (ikke testen) med mindre testen selv er feil.

- [ ] **Step 5: Kjør lint og commit**

Run: `python3 scripts/lint-skills.py`
Expected: grønn.

```bash
git add scripts/land-worktree.py tests/unit/test_land_worktree.py
git commit -m "feat(land): land-worktree.py — lock, preflight and exit codes for solo landing

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

### Task 2.2: Landing mot ekte `wt`

**Files:**
- Modify: `tests/unit/test_land_worktree.py` (legg til på slutten)
- Modify: `scripts/land-worktree.py` (bare hvis testene avslører feil)

- [ ] **Step 1: Skriv testene**

```python
# ===== landing against the real wt (skipped without worktrunk, e.g. in CI) =====

needs_wt = pytest.mark.skipif(shutil.which("wt") is None,
                              reason="wt (worktrunk) not installed — expected in CI")


def real_land(lab, *args):
    """Isolated HOME/XDG so approvals never touch the developer's own config."""
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"),
         "PATH": os.environ["PATH"]}
    return subprocess.run([sys.executable, str(SCRIPT), "--worktree", str(lab.wt), "--ci-wait", "0", *args],
                          capture_output=True, text=True, env=e)


def approve(lab):
    e = {"HOME": str(lab.root), "XDG_CONFIG_HOME": str(lab.root / "xdg"), "PATH": os.environ["PATH"]}
    r = subprocess.run(["wt", "-C", str(lab.wt), "config", "approvals", "add", "--yes"],
                       capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr


def set_hook(lab, command):
    (lab.wt / ".config" / "wt.toml").write_text(f"[pre-merge]\ncheck = '{command}'\n")
    git(lab.wt, "commit", "-qam", "chore: hook")


def remote_log(lab):
    return git(lab.remote, "log", "--format=%s", "main")


@needs_wt
def test_lands_pushes_and_leaves_the_worktree_for_the_caller(lab):
    git(lab.wt, "push", "-q", "-u", "origin", "feat/x")          # a pushed branch must be deleted
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 0, p.stderr
    v = verdict(p)
    assert v["landed"] is True and "feat: x" in remote_log(lab)
    assert git(lab.primary, "rev-parse", "main") == git(lab.remote, "rev-parse", "main")
    assert lab.wt.exists(), "the script never removes the worktree"
    assert git(lab.remote, "branch", "--list", "feat/x") == "", "the remote branch is deleted"
    assert any("remove feat/x" in r for r in v["remaining"])


@needs_wt
def test_unapproved_hooks_are_code_3_before_anything_moves(lab):
    p = real_land(lab)                                            # no approve(lab)
    assert p.returncode == 3, p.stderr
    assert "feat: x" not in remote_log(lab)


@needs_wt
def test_red_hook_is_code_6_and_main_does_not_move(lab):
    set_hook(lab, "false")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 6, p.stderr
    assert "feat: x" not in remote_log(lab)
    assert git(lab.primary, "rev-parse", "main") == git(lab.remote, "rev-parse", "main")
    assert lab.wt.exists()


@needs_wt
def test_rebase_conflict_is_code_10_with_the_rebase_left_open(lab):
    commit(lab.wt, "shared.md", "feature side\n", "feat: shared")
    commit(lab.primary, "shared.md", "main side\n", "chore: main moves the same line")
    git(lab.primary, "push", "-q", "origin", "main")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 10, p.stderr
    assert (Path(git(lab.wt, "rev-parse", "--path-format=absolute", "--git-dir")) / "rebase-merge").exists()


@needs_wt
def test_origin_moving_during_the_checks_is_code_7_and_nothing_is_pushed(lab):
    other = lab.root / "other"
    subprocess.run(["git", "clone", "-q", str(lab.remote), str(other)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        git(other, "config", k, v)
    set_hook(lab, f"cd \"{other}\" && echo x >> z.md && git add -A && git commit -qm race && git push -q origin main")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 7, p.stderr
    assert "feat: x" not in remote_log(lab) and "race" in remote_log(lab)
    assert "feat: x" in git(lab.primary, "log", "--format=%s", "main"), "local main holds the work"
    assert lab.wt.exists(), "worktree and branch stand as the recovery point"


@needs_wt
def test_repo_without_origin_lands_locally_with_a_warning(lab):
    git(lab.primary, "remote", "remove", "origin")
    approve(lab)
    p = real_land(lab)
    assert p.returncode == 0, p.stderr
    assert "feat: x" in git(lab.primary, "log", "--format=%s", "main")
    assert any("no origin" in w for w in verdict(p)["warnings"])
```

- [ ] **Step 2: Kjør dem**

Run: `python3 -m pytest tests/unit/test_land_worktree.py -q -p no:cacheprovider`
Expected: alle bestått. `wt` finnes på denne maskinen, så de fem nye kjører. Feiler en, er det et funn om `wt`-oppførsel eller skriptet: les `p.stderr`, sammenlign med målingene i spesifikasjonen (tekster: `Cannot prompt for approval`, `pre-merge command failed`, `Rebase onto … incomplete`), og rett skriptet i `_classify`/`_land_locked`. Legg **ikke** til `--yes` eller `--no-hooks` for å få en test grønn.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_land_worktree.py scripts/land-worktree.py
git commit -m "test(land): landing against real wt — success, red hook, conflict, origin race

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 3: The `land` skill

### Task 3.1: `skills/land/SKILL.md`, ruting og README

**Files:**
- Create: `skills/land/SKILL.md`
- Modify: `CLAUDE.md` (rutingseksjonen, etter `verify-and-land`-punktet)
- Modify: `README.md` (skill-listen, etter `/verify-and-land`)

- [ ] **Step 1: Skriv skillen**

```markdown
---
name: land
description: |
  Land a finished worktree on main in one command for a solo project: local pre-merge
  checks, fast-forward, push, no pull request. Interprets every exit code.
---

# Land

The solo developer's landing: the branch you finished goes onto `main` after the project's own local checks, and is pushed. There is no pull request, so the pre-merge hook is the gate. This skill runs `scripts/land-worktree.py` and turns its exit code into the next action; it never repairs anything itself.

Invoke with: `/superpowers-gstack:land`

## Before you run it

Ship-worthy changes have already been through `/review` and `/superpowers-gstack:pitfall-verification`. This skill is the landing, not the review.

## Run

Locate the script relative to this skill (it usually runs in the user's project, where `scripts/` does not exist):

```bash
LAND="<this skill's base directory>/../../scripts/land-worktree.py"
python3 "$LAND" --worktree "<the feature worktree, default: the current directory>"
```

Add `--preflight-only` first if the user wants to know whether it would land, without moving anything. The last line of stdout is a JSON verdict; stderr carries the reason and the exact commands to run.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | Landed | Read `remaining`: leave the worktree first (`ExitWorktree`, action `keep`) if the session stands in it, then `wt -C <primary> remove <branch>`. Run the `watch` command in the background; a red CI run means fixing `main` next. Warnings are not failures. |
| 2 | `Landing mode` is `pr`, or the line is missing or invalid | `pr`: use `/ship`. Missing: ask the user once (solo or pull request?) and write the answer on its own line under a heading the project owns, outside the `/adapt`-managed sections. Never assume `solo`. |
| 3 | Hooks not approved | Tell the user to run `wt config approvals add` (in this session: `! wt config approvals add`). Never `--yes`. |
| 4 | Local `main` has commits that are not on origin | The listed commits would ride along unchecked. Ask the user what they are. |
| 5 | Uncommitted files in the worktree holding `main` overlap this landing | Name the files. The user commits them or moves them to their own branch. Never stash. |
| 6 | A pre-merge check failed | Fix the failure and land again. Never `--no-hooks`. |
| 7 | `origin/main` moved, or the push was rejected | Nothing was pushed. Local `main` already holds the work and the worktree stands. Show the user the printed commands and let them choose; do not reset. |
| 8 | `wt` is not installed | Fall back to `git worktree` and `/superpowers:finishing-a-development-branch`. |
| 9 | No `pre-merge` hook in `.config/wt.toml` | Propose one that runs the same commands as CI. The user approves it. |
| 10 | Rebase conflict | A rebase is open in the worktree. Resolve it, or `git rebase --abort`, then land again. |
| 11 | `git fetch` failed | Check the network and the remote, then land again. |
| 12 | Another landing holds the lock | Wait, or look at who holds it. |
| 13 | The worktree has uncommitted work | Commit it, or move it to `wip/<topic>`. |
| 64 | Not a feature worktree | Run from the feature worktree, or pass `--worktree`. |
| 70 | Unrecognised `wt merge` failure | Show the user the printed tail. Do not guess. |

## Never

`--no-hooks`, `--yes`, `git reset`, `git stash`, or a second attempt without the user hearing why the first stopped. The script is deliberately small so that every stop leaves the state visible.
```

- [ ] **Step 2: Legg skillen i rutingen**

I `CLAUDE.md`, etter punktet som begynner `- "I fixed it but I don't see it in the app"`:

```markdown
- Land finished work on main in a project with no review ("land it", "merge this", "finish the branch", solo project, `Landing mode: solo`) → invoke /superpowers-gstack:land. Local pre-merge checks (`.config/wt.toml`), fast-forward, push, CI run reported, no pull request. Exit codes 2–13, 64 and 70 are interpreted in the skill; it never resets, stashes or skips the checks. In a project whose landing mode is `pr`, use /ship instead.
```

- [ ] **Step 3: Legg skillen i README**

I `README.md`, etter `/verify-and-land`-punktet:

```markdown
  - `/land` — solo landing without a pull request: runs the project's local `pre-merge` checks, fast-forwards `main`, pushes, and reports the CI run for the pushed commit. Backed by `scripts/land-worktree.py` (lock, preflight, distinct exit codes, never resets or retries); invoked as `/superpowers-gstack:land`
```

- [ ] **Step 4: Kjør lint og tester**

Run: `python3 scripts/lint-skills.py && python3 -m pytest tests/unit -q -p no:cacheprovider --deselect tests/unit/test_lint_upstream_skills.py::test_roster_matches_installed_upstream_when_present --deselect tests/unit/test_spec_drift_upstream_alarm.py::test_pin_matches_installed_gstack_when_present 2>&1 | tail -3`
Expected: lint grønn, ingen røde tester.

- [ ] **Step 5: Commit**

```bash
git add skills/land/SKILL.md CLAUDE.md README.md
git commit -m "feat(land): the land skill — finds the script, interprets every exit code

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 4: The shared block, its registries and the repo's own copy

### Task 4.1: Blokken `worktrunk.md` og de tre registrene

**Files:**
- Create: `skills/adapt/blocks/worktrunk.md`
- Modify: `scripts/adapt-claude-md.py:104-120` (rosteren `BLOCKS`)
- Modify: `scripts/lint-skills.py:138-147` (`MARKER_BLOCKS`)
- Modify: `scripts/sync-own-claude-md.py:32-38` (`UNIVERSAL`)
- Modify: `tests/unit/test_adapt_script.py:98-99`
- Create: `tests/unit/test_worktrunk_block.py`

- [ ] **Step 1: Skriv testen for blokken**

```python
"""skills/adapt/blocks/worktrunk.md — the rules every adapted project gets.

The block must never contain the parsable `Landing mode:` line itself: /adapt replaces
a block wholesale on upgrade, so a line inside it would silently reset a project's
choice of `pr` back to `solo`. land-worktree.py parses that line with an anchored
pattern; prose that merely mentions it, inside a sentence, must not match.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BLOCK = REPO / "skills" / "adapt" / "blocks" / "worktrunk.md"


def test_heading_carries_the_marker_and_the_file_ends_with_newline():
    text = BLOCK.read_text()
    assert re.match(r"^## Worktrees and solo landing <!-- gstack-worktrunk-v1 -->\n", text)
    assert text.endswith("\n")


def test_block_never_holds_the_parsable_mode_line():
    for line in BLOCK.read_text().splitlines():
        assert not re.match(r"^Landing mode: (solo|pr)$", line), f"reset-on-upgrade trap: {line!r}"


def test_block_forbids_the_shortcuts_the_gate_depends_on():
    text = BLOCK.read_text()
    for needle in ("--no-hooks", "--yes", "git stash", "EnterWorktree", "/superpowers-gstack:land"):
        assert needle in text, needle
```

- [ ] **Step 2: Kjør den og se den feile**

Run: `python3 -m pytest tests/unit/test_worktrunk_block.py -q -p no:cacheprovider`
Expected: FAIL (`FileNotFoundError`).

- [ ] **Step 3: Skriv blokken**

`skills/adapt/blocks/worktrunk.md` (engelsk, slutter med newline):

```markdown
## Worktrees and solo landing <!-- gstack-worktrunk-v1 -->

Work on a branch in its own worktree, and land it on `main` with one command when nobody else reviews this repository. This is what makes a solo developer's day faster: no branch switching, no stash, no pull request to wait for.

- **Start every task in a worktree.** `wt switch --create <type>/<topic> --no-cd --format=json` prints the path (check `command -v wt`; without worktrunk use `git worktree add ../<repo>.<topic> -b <type>/<topic>`). Then enter it with the `EnterWorktree` tool and its `path` argument, so plain `git` and every skill run inside it. Never `git stash` to switch tasks: every worktree shares one stash. Move unfinished work to a `wip/<topic>` branch instead.
- **The landing mode is a decision the project makes once.** A line reading `Landing mode: solo` or `Landing mode: pr`, on its own line in this file *outside* this section (a `/adapt` upgrade replaces this section whole and would overwrite it), sets it. If the line is missing, ask the user once: "Should finished work land straight on main after the local checks, or go through a pull request?" Write the answer on its own line under a heading the project owns. Never assume `solo`.
- **`solo`:** land with `/superpowers-gstack:land`. It runs the project's own pre-merge checks, fast-forwards `main`, pushes, and reports the CI run for the pushed commit. **`pr`:** use `/ship`.
- **The checks are the safety net that replaces the pull request, so never skip them.** No `--no-hooks`, no `--yes`. A red check is fixed, not bypassed. A project without a `pre-merge` hook in `.config/wt.toml` cannot land solo: propose one that runs the same commands as CI, and let the user approve it with `wt config approvals add`.
- **Handoff files live in the primary checkout,** not in a worktree. A worktree is removed after landing and takes its untracked files with it.
- **After landing,** leave the worktree first (`ExitWorktree` with `keep`), then `wt remove <branch>`. Removing the folder a session stands in leaves the session with no working directory.
```

- [ ] **Step 4: Registrer blokken på tre steder**

I `scripts/adapt-claude-md.py`, etter raden for `session-continuity.md` i `BLOCKS`:

```python
    Block("session-continuity.md", "gstack-session-continuity", r"Session [Cc]ontinuity",
          ("docs/superpowers/handoff.md",)),
    Block("worktrunk.md", "gstack-worktrunk", r"Worktrees and solo landing",
          ("EnterWorktree", "Landing mode")),
```

I `scripts/lint-skills.py`, i `MARKER_BLOCKS`, etter `"session-continuity.md",`:

```python
    "session-continuity.md",
    "worktrunk.md",
```

I `scripts/sync-own-claude-md.py`, i `UNIVERSAL`, etter `"session-continuity.md",`:

```python
    "session-continuity.md",
    "worktrunk.md",
```

I `tests/unit/test_adapt_script.py`, utvid tuppelen i `test_fresh_project_gets_the_header_and_every_universal_block`:

```python
    for name in ("git-hygiene.md", "multi-lens-review.md", "code-reuse.md",
                 "plan-fidelity.md", "session-continuity.md", "worktrunk.md", "track-routing.md"):
```

- [ ] **Step 5: Kjør de berørte testene**

Run: `python3 -m pytest tests/unit/test_worktrunk_block.py tests/unit/test_adapt_script.py tests/unit/test_own_blocks_sync.py tests/unit/test_lint_adapt_and_blocks.py -q -p no:cacheprovider`
Expected: `test_worktrunk_block` bestått og `test_adapt_script` bestått. `test_own_blocks_sync::test_region_in_repo_is_current` feiler (repoets `CLAUDE.md` er ikke synkronisert ennå), det tas i Task 4.3. Feiler en test som hardkoder rekkefølgen på overskrifter (f.eks. `hs[i + 1]`), les den og rett forventningen til den nye rekkefølgen (`worktrunk` kommer etter `session-continuity`). Ikke endre rekkefølgen i `BLOCKS` for å slippe å endre testen.

### Task 4.2: `git-hygiene` v11 → v12

**Files:**
- Modify: `skills/adapt/blocks/git-hygiene.md:1` og landing-punktet (linje ~57)
- Modify: `scripts/lint-skills.py:94` (`DENYLIST`)

- [ ] **Step 1: Bump markøren**

Endre første linje til `## Git hygiene & commit cadence <!-- gstack-git-hygiene-v12 -->`.

- [ ] **Step 2: Pek på `land` for solo-prosjekter**

Erstatt

```
- **Landing is a skill, not a hand-rolled merge:** `/ship` (tests → review → PR) or
  `/superpowers:finishing-a-development-branch` (merge, PR, or discard). Pick one.
```

med

```
- **Landing is a skill, not a hand-rolled merge:** `/superpowers-gstack:land` (a project
  whose `Landing mode` is `solo`: local checks → main → push, no pull request), `/ship`
  (tests → review → PR) or `/superpowers:finishing-a-development-branch` (merge, PR, or
  discard). Pick one.
```

- [ ] **Step 3: Hold v11 utestengt**

I `DENYLIST` i `scripts/lint-skills.py`, erstatt regelen for git-hygiene med:

```python
    (re.compile(r"gstack-git-hygiene-v(?:[0-9]|1[01])\b"), "stale git-hygiene marker (current: v12+, 3.4.0 — v11 sent every landing to /ship's pull request; v10 told agents to park work in git stash)"),
```

- [ ] **Step 4: Kjør lint (skal feile på `CLAUDE.md` til Task 4.3)**

Run: `python3 scripts/lint-skills.py 2>&1 | tail -5`
Expected: feil om at `CLAUDE.md`s own-blocks-region er utdatert (E11) og at den inneholder `gstack-git-hygiene-v11` (E7). Begge løses i neste task.

### Task 4.3: Synkroniser repoets egen `CLAUDE.md`, og sett dens landingsmodus

**Files:**
- Modify: `CLAUDE.md` (bare i dette worktreet, aldri på `main`)

- [ ] **Step 1: Regenerer own-blocks-regionen**

Run: `python3 scripts/sync-own-claude-md.py`
Expected: `own-blocks: synced 6 blocks into CLAUDE.md`.

- [ ] **Step 2: Sett landingsmodus for dette repoet, utenfor regionen**

Legg til rett før linjen `<!-- BEGIN own-blocks`:

```markdown
## Landing mode (this repo)

Landing mode: solo

This repository has one maintainer and no review. Finished work lands on `main` with `/superpowers-gstack:land`; the `pre-merge` hook in `.config/wt.toml` mirrors CI and is the gate.

```

- [ ] **Step 3: Kjør lint og hele blokk-relaterte tester**

Run: `python3 scripts/lint-skills.py && python3 -m pytest tests/unit/test_own_blocks_sync.py tests/unit/test_adapt_script.py tests/unit/test_worktrunk_block.py tests/unit/test_lint_adapt_and_blocks.py -q -p no:cacheprovider`
Expected: grønn. `land`-skillen finnes allerede (Phase 3), så referansene til `/superpowers-gstack:land` i blokken og i `git-hygiene` løses av lint (E2).

- [ ] **Step 4: Commit**

```bash
git add skills/adapt/blocks/worktrunk.md skills/adapt/blocks/git-hygiene.md scripts/adapt-claude-md.py scripts/lint-skills.py scripts/sync-own-claude-md.py tests/unit/test_adapt_script.py tests/unit/test_worktrunk_block.py CLAUDE.md
git commit -m "feat(adapt): worktrunk block, git-hygiene v12, three registries, own copy

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 5: Session continuity across worktrees

### Task 5.1: Sesjonslogg og handoff via `git-common-dir`

Uten dette er en avbrutt økt i et worktree usynlig for neste økt fra primærmappen, og loggen forsvinner når worktreet fjernes.

**Files:**
- Modify: `scripts/capture-session-tail.sh:11,48`
- Modify: `scripts/session-resume.sh` (oppslaget av git-mappen og handoff-stien)
- Modify: `tests/unit/test_session_resume_hooks.py`

- [ ] **Step 1: Skriv de feilende testene**

Legg til på slutten av `tests/unit/test_session_resume_hooks.py`:

```python
# ------------------------------------------------- linked worktrees (3.4.0) ----

@pytest.fixture
def linked(repo, tmp_path):
    """The repo plus a linked worktree that also carries docs/superpowers/."""
    (repo / "docs" / "superpowers" / ".gitkeep").write_text("")
    git(repo, "add", "-f", "docs/superpowers/.gitkeep")
    git(repo, "commit", "-qm", "docs dir")
    wt = tmp_path.parent / (tmp_path.name + ".wt")
    git(repo, "worktree", "add", "-q", "-b", "feat/x", str(wt))
    return wt


def test_capture_from_a_linked_worktree_lands_in_the_shared_git_dir(repo, linked, tmp_path):
    t = transcript(tmp_path, [("user", "hello"), ("assistant", "hi")])
    run_capture(linked, payload(linked, t))
    assert capture_file(repo).is_file(), "the primary checkout must be able to read it"
    assert "feat/x" in capture_file(repo).read_text(), "it still describes the worktree's branch"


def test_capture_survives_the_worktree_being_removed(repo, linked, tmp_path):
    t = transcript(tmp_path, [("user", "hello"), ("assistant", "hi")])
    run_capture(linked, payload(linked, t))
    git(repo, "worktree", "remove", "--force", str(linked))
    assert capture_file(repo).is_file()


def test_resume_in_the_primary_shows_a_capture_written_from_a_worktree(repo, linked, tmp_path):
    t = transcript(tmp_path, [("user", "finish the landing script"), ("assistant", "on it")])
    run_capture(linked, payload(linked, t))
    assert "landing script" in run_resume(repo)


def test_resume_in_a_worktree_reads_the_primarys_handoff(repo, linked):
    (repo / "docs" / "superpowers" / "handoff.md").write_text(
        '---\ntype: handoff\nnext_step: "run the phase 3 tests"\n---\nbody\n')
    assert "run the phase 3 tests" in run_resume(linked)
```

- [ ] **Step 2: Kjør dem og se de feile**

Run: `python3 -m pytest tests/unit/test_session_resume_hooks.py -q -p no:cacheprovider -k "linked or worktree"`
Expected: FAIL (loggen havner i worktreets egen git-mappe; `handoff.md` leses fra worktreet).

- [ ] **Step 3: Endre `capture-session-tail.sh`**

Endre linje 48 fra

```python
gitdir = sh("git", "-C", cwd, "rev-parse", "--absolute-git-dir")
```

til

```python
gitdir = sh("git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
```

Oppdater kommentaren på linje 11 fra `written INSIDE the git dir (.git/gstack-last-session.md)` til `written INSIDE the SHARED git dir (<primary>/.git/gstack-last-session.md, also when the session ran in a linked worktree — a worktree's own git dir is deleted with it)`.

- [ ] **Step 4: Endre `session-resume.sh`**

Erstatt

```python
gitdir = sh("git", "rev-parse", "--absolute-git-dir")
```

med

```python
gitdir = sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir")
```

og legg rett etter blokken `if not root or not gitdir: raise SystemExit(0)`:

```python
# handoff.md is gitignored, so it lives only in the primary checkout. progress.md is
# tracked and belongs to the branch, so it keeps being read from the worktree.
primary = os.path.dirname(gitdir) if os.path.basename(gitdir) == ".git" else root
```

Endre linjen `handoff = os.path.join(root, "docs", "superpowers", "handoff.md")` til:

```python
handoff = os.path.join(primary, "docs", "superpowers", "handoff.md")
```

- [ ] **Step 5: Kjør hele sesjonstest-filen**

Run: `python3 -m pytest tests/unit/test_session_resume_hooks.py -q -p no:cacheprovider`
Expected: alle bestått, både de nye og de eksisterende.

- [ ] **Step 6: Commit**

```bash
git add scripts/capture-session-tail.sh scripts/session-resume.sh tests/unit/test_session_resume_hooks.py
git commit -m "fix(session): capture and handoff resolve through git-common-dir, so worktrees do not hide a session

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 6: `autoimplement` works in a worktree

### Task 6.1: Check 1, sluttlanding og oppsummering

**Files:**
- Modify: `skills/autoimplement/SKILL.md` (Check 1, §F, §Final summary)
- Test: `skills/autoimplement/tests/required-sections.test.sh` (skal fortsatt passere)

- [ ] **Step 1: Les kontrakttesten først**

Run: `cat skills/autoimplement/tests/required-sections.test.sh | head -40; bash skills/autoimplement/tests/required-sections.test.sh; echo "exit=$?"`
Expected: `exit=0` før endringene. Noter hvilke overskrifter den krever, og behold dem.

- [ ] **Step 2: Erstatt Check 1**

Erstatt hele blokken fra `### Check 1: Workspace is on a feature branch with a clean tree` til rett før `### Check 2: Phase count is at least 2` med:

````markdown
### Check 1: A clean feature branch, in a worktree of its own

```bash
git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
git_status=$(git status --porcelain 2>/dev/null || echo "GIT_FAIL")
```

(Variable names are deliberately prefixed `git_` — bare `status` is read-only in zsh, the default shell on macOS, which would break this snippet when the agent runs it via Bash. The `git_` prefix avoids the collision and is self-documenting.)

Refuse if:
- `git_branch` is empty or `GIT_FAIL` → "autoimplement runs only in a git repo."

**On `main` or `master`** (the normal start for a solo developer): do not refuse. Create a worktree for the run and move the session into it, so every later `git` call, every review skill and every subagent works in the right folder without change:

1. The plan must be committed **on this branch**, otherwise it does not exist in the new worktree. Check `git ls-files --error-unmatch -- "$plan_path"` and `git status --porcelain -- "$plan_path"` (must be empty). If not → "the plan is not committed on '<branch>' — commit it first, or check out the branch it lives on."
2. Create the worktree: `wt switch --create "autoimpl/<plan-slug>" --no-cd --format=json` (without worktrunk: `git worktree add "../<repo>.autoimpl-<plan-slug>" -b "autoimpl/<plan-slug>"`). The plan slug is the plan file name without date and extension.
3. Call the `EnterWorktree` tool with `path=<the worktree path>`, then verify with `pwd && git rev-parse --abbrev-ref HEAD` that the branch is `autoimpl/<plan-slug>`.
4. The primary checkout's own uncommitted files do **not** stop the run. If they overlap what the run changes, the landing reports it (exit code 5) while everything is still intact.

**On any other branch:** work on it as before, in the worktree it already lives in.

Then refuse if:
- `git_status` (now evaluated inside the worktree or feature branch) is non-empty → "working tree has uncommitted changes — autoimplement requires a clean tree (so phase commits are unambiguous). Commit them here if they belong to this plan; otherwise move them onto their own branch (`git switch -c wip/<topic>`, commit, `git switch <branch>`). Then re-invoke on '<branch>'."

**Reserve (used only if Phase 0 of the worktrunk plan found that subagents do not inherit the working directory):** define `WT=<the worktree path>` once here, and run every `git` call in this skill as `git -C "$WT" …`.

````

- [ ] **Step 3: Endre §F og sluttoppsummeringen**

Erstatt

```
### F. When the last phase is done

Emit a single completion summary (see § Final summary).
```

med

```
### F. When the last phase is done

If the project's `CLAUDE.md` carries the exact line `Landing mode: solo`, invoke `/superpowers-gstack:land` for the worktree; it runs the project's pre-merge checks and pushes, and stops with a named exit code if anything is wrong (see that skill for the codes). If the line is `pr` or missing, do not land: name `/ship` in the summary. Then emit a single completion summary (see § Final summary). `progress.md` gets the commit SHAs **as they are on `main` after landing**, because a rebase can rewrite the phase commits.
```

Og i sluttoppsummeringen, erstatt

```
Suggested next:
  - /ship to land the work
  - git log main..HEAD to see the cumulative diff
```

med

```
Landing: <landed on main (<sha>) | stopped: exit code <N> — <reason> | not attempted: Landing mode is pr or missing — use /ship>
Suggested next:
  - if landed: leave the worktree (ExitWorktree keep), then wt remove <branch>
  - otherwise: git log main..HEAD to see the cumulative diff
```

- [ ] **Step 4: Kjør kontrakttest, lint og alle tester**

Run: `bash skills/autoimplement/tests/required-sections.test.sh && python3 scripts/lint-skills.py && python3 -m pytest tests/unit -q -p no:cacheprovider --deselect tests/unit/test_lint_upstream_skills.py::test_roster_matches_installed_upstream_when_present --deselect tests/unit/test_spec_drift_upstream_alarm.py::test_pin_matches_installed_gstack_when_present 2>&1 | tail -3`
Expected: alt grønt. Feiler kontrakttesten fordi en påkrevd overskrift er borte, gjenopprett overskriften med samme tekst.

- [ ] **Step 5: Commit**

```bash
git add skills/autoimplement/SKILL.md
git commit -m "feat(autoimplement): run in a worktree from main, land through the land skill

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 7: The session-start menu follows the landing mode

### Task 7.1: `check-branch-hygiene.sh` tilbyr `land`, og `wt step prune`

**Files:**
- Modify: `scripts/check-branch-hygiene.sh` (etter linje 53; de tre `act "finish"`-linjene; opprydningsblokken)
- Modify: `tests/unit/test_branch_hygiene_hook.py`

- [ ] **Step 1: Skriv de feilende testene**

Legg til i `tests/unit/test_branch_hygiene_hook.py`. Finn først hvordan eksisterende tester lager en ikke-landet gren som gir «finish»-tilbudet (`grep -n "via /ship" tests/unit/test_branch_hygiene_hook.py`, rundt linje 374), og gjenbruk nøyaktig samme oppsett i `unlanded_branch(repo)`-hjelperen under.

```python
def unlanded_branch(repo):
    """Same setup the existing 'via /ship' tests use: an old, unlanded feature branch."""
    git(repo, "switch", "-q", "-c", "feat/old")
    (repo / "old.txt").write_text("o")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "old work", "--date", "2020-01-01T00:00:00", env={**os.environ, "GIT_COMMITTER_DATE": "2020-01-01T00:00:00"})
    git(repo, "switch", "-q", "main")


def test_solo_repo_is_offered_land_and_never_ship(repo):
    (repo / "CLAUDE.md").write_text("# p\n\nLanding mode: solo\n")
    git(repo, "add", "-A"); git(repo, "commit", "-qm", "mode")
    unlanded_branch(repo)
    out = run_hook(repo)
    assert "/superpowers-gstack:land" in out and "/ship" not in out


def test_repo_without_a_mode_line_keeps_the_ship_offer(repo):
    unlanded_branch(repo)
    out = run_hook(repo)
    assert "/ship" in out and "/superpowers-gstack:land" not in out
```

- [ ] **Step 2: Kjør dem og se de feile**

Run: `python3 -m pytest tests/unit/test_branch_hygiene_hook.py -q -p no:cacheprovider -k "solo_repo or without_a_mode"`
Expected: `test_solo_repo_is_offered_land_and_never_ship` FAIL. Feiler hjelperen `unlanded_branch` selv (grenen gir ikke et «finish»-tilbud), sammenlign med oppsettet i testen rundt linje 374 og rett hjelperen til den gir tilbudet uten mode-linje.

- [ ] **Step 3: Les modusen og bruk den**

Rett etter linje 53 (`_root=$(git rev-parse --show-toplevel 2>/dev/null || echo .)`), legg til:

```bash
# Landing mode: the exact line, outside any /adapt-managed section, decides whether
# a finished branch is offered /superpowers-gstack:land (solo) or /ship (a PR).
land_mode=$(grep -m1 -E '^Landing mode: (solo|pr)$' "$_root/CLAUDE.md" 2>/dev/null | sed 's/^Landing mode: //')
finish_via="/ship"
[ "$land_mode" = "solo" ] && finish_via="/superpowers-gstack:land"
```

Erstatt de tre `act "finish"`-linjene slik at de bruker variabelen. I de to første, bytt `via /ship` med `via ${finish_via}`. I den tredje, erstatt hele strengen med:

```bash
      if [ "$land_mode" = "solo" ]; then
        act "finish" "${target# } via /superpowers-gstack:land — runs the project's local checks, lands it on main and pushes, no pull request"
      else
        act "finish" "${target# } — /ship runs tests and review and opens a PR; /superpowers:finishing-a-development-branch merges or discards instead. Recommend one based on the repo"
      fi
```

- [ ] **Step 4: Foreslå `wt step prune` for spente worktrees**

I opprydningsblokken, rett etter linjen som tilbyr `git worktree remove <path>` for `wt_done_n`, legg til:

```bash
  [ "${wt_done_n:-0}" != "0" ] && command -v wt >/dev/null 2>&1 && \
    act "tidy" "or let worktrunk do it: wt step prune removes every working folder whose branch is already merged into ${default_ref}"
```

- [ ] **Step 5: Kjør hele hook-testfilen**

Run: `python3 -m pytest tests/unit/test_branch_hygiene_hook.py -q -p no:cacheprovider`
Expected: alle bestått (de eksisterende testene verifiserer at repoer uten mode-linje er uendret).

- [ ] **Step 6: Commit**

```bash
git add scripts/check-branch-hygiene.sh tests/unit/test_branch_hygiene_hook.py
git commit -m "feat(branch-hygiene): offer land in solo repos, wt step prune for spent worktrees

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 8: Release gate

### Task 8.1: Versjon, CHANGELOG, README og full verifisering

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `CHANGELOG.md`
- Modify: `README.md` (blokkoversikt, hvis den finnes)

- [ ] **Step 1: Bump versjonen**

Endre `"version": "3.3.0"` til `"version": "3.4.0"` i `.claude-plugin/plugin.json`.

- [ ] **Step 2: Skriv CHANGELOG-oppføringen**

Legg til øverst, rett under `# Changelog`:

```markdown
## [3.4.0] - 2026-09-29

**A solo developer lands work without a pull request: worktrees by default, one command to `main`, the local checks as the gate.**

### Added
- **`/superpowers-gstack:land`** and `scripts/land-worktree.py`: local pre-merge checks, fast-forward `main`, push, and the CI run for the pushed commit. One lock per repository. Every stop has its own exit code (2–13, 64, 70) and leaves the state visible; the script never resets, never retries by itself, never passes `--yes` or `--no-hooks`, and never removes the worktree.
- **`worktrunk.md` block** (`gstack-worktrunk-v1`): start every task in a worktree, enter it with `EnterWorktree`, no stash, land with `land`. The `Landing mode: solo|pr` line is deliberately **not** in the block: `/adapt` replaces blocks whole and would silently reset a project's `pr` choice. The project owns the line; a missing line fails closed.
- `.config/wt.toml` for this repository: a `pre-merge` table that mirrors CI.

### Changed
- `git-hygiene` block v11 → v12 points solo projects at `land`; `gstack-git-hygiene-v11` joins the denylist.
- **`autoimplement`** no longer refuses `main`: it creates a worktree, moves the session into it, and lands through `land` when the mode is `solo`.
- `capture-session-tail.sh` and `session-resume.sh` resolve through `git rev-parse --git-common-dir`, so a session that ended inside a worktree is visible from the primary checkout and survives the worktree's removal. `handoff.md` is read from the primary checkout.
- The session-start menu offers `land` instead of `/ship` in a `solo` repository, and `wt step prune` for spent working folders.

### Verified
- `wt merge` refuses a dirty `main` worktree when the same file changed (measured); a rejected push after `wt merge` leaves a diverged `main` that `git pull --ff-only` cannot fix (measured) — hence `--no-remove` and no automatic repair.
- Two tests that already failed on this machine are real alarms, not noise: the roster lacks `diagnosing-superpowers`, and the spec-drift pin dates from gstack 1.84.1 while 1.91.2 is installed. They are excluded from the `pre-merge` hook and reviewed in the release checklist below.
```

- [ ] **Step 3: Full verifisering**

Run: `python3 scripts/lint-skills.py && python3 -m pytest -q -p no:cacheprovider 2>&1 | tail -4 && for t in skills/*/tests/required-sections.test.sh; do bash "$t" || echo "FAIL $t"; done`
Expected: lint grønn; `2 failed` er nøyaktig de to alarmene i Global Constraints, og alt annet grønt; ingen `FAIL`-linjer. Ethvert annet resultat er en feil planen har innført og må rettes før commit.

- [ ] **Step 4: E2E-test av `/adapt`, manuelt**

Kjør E2E-testen for `adapt` som prosjektet beskriver for endringer i skript og blokker: `bash tests/run.sh --integration` (den bruker `claude --print` og koster penger; si fra til brukeren om anslaget før du kjører). Verifiser i tillegg for hånd i et kaster-prosjekt at en ny `/adapt`-kjøring skriver `## Worktrees and solo landing`-seksjonen og **ikke** endrer en eksisterende linje `Landing mode: pr` som ligger utenfor den.

- [ ] **Step 5: Multi-lens på koden**

Kjør `/superpowers-gstack:pitfall-verification` på diffen (`--diff --diff-base main`). Den beregner tier-gulvet selv, og dette er høy innsats (kontrakt, sikkerhetsnett, push til `main`). Fiks funn, kjør på nytt én gang, og skriv verdikten inn i CHANGELOG-utkastet hvis den endret noe.

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md README.md
git commit -m "chore(release): 3.4.0 — solo landing without a pull request

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

---

## Phase 9: Personal configuration, `/gstack-upgrade`, and landing

Denne fasen er interaktiv: den rører brukerens egne filer og krever samtykke i hvert steg.

### Task 9.1: Personlig konfig (komponent 7), med diff og samtykke

**Files (utenfor repoet, brukerens egne):**
- Modify: `~/.zshenv`
- Modify: `~/.codex/config.toml`
- Modify eller create: `~/.config/worktrunk/config.toml`

- [ ] **Step 1: Les dagens innhold og lag diffen**

Run: `cat ~/.zshenv; echo ---; grep -n "^model\|^service_tier" ~/.codex/config.toml; echo ---; cat ~/.config/worktrunk/config.toml 2>&1 | head -20; claude --version`
Vis brukeren nøyaktig disse tre endringene som en diff, og vent på et ja til hver:

```
~/.zshenv                       + export GSTACK_CODEX_MODEL=gpt-6-sol
~/.codex/config.toml            - model = "gpt-6-astra"
                                + model = "gpt-6-sol"
~/.config/worktrunk/config.toml + [commit.generation]
                                + command = "MAX_THINKING_TOKENS=0 claude -p --no-session-persistence --model=haiku --tools='' --safe-mode --setting-sources='user' --system-prompt=''"
```

`--safe-mode` krever Claude Code ≥ 2.1.169 (worktrunks dokumentasjon). Er den installerte versjonen eldre, dropp `--safe-mode` fra kommandoen og si det til brukeren.

- [ ] **Step 2: Bruk bare de endringene brukeren har sagt ja til**

Bruk `Edit` (ikke `>>`-omdirigering av hele filer). Bekreft etterpå med `grep` at hver endring står der, og at ingen andre linjer er endret (`diff` mot kopien fra steg 1).

- [ ] **Step 3: Bekreft Sol-modellen**

Run: `GSTACK_CODEX_MODEL=gpt-6-sol bash -c 'source ~/.claude/skills/gstack/bin/gstack-codex-probe; _gstack_codex_model_probe'`
Expected: `MODEL_OK`.

- [ ] **Step 4: Ingen commit (filene ligger utenfor repoet).** Noter i «Phase 0 results»-seksjonen at Task 9.1 er utført, med hvilke av de tre endringene brukeren godkjente.

### Task 9.2: `/gstack-upgrade`, og vurder hva som må endres

**Files:**
- Modify (hvis vurderingen krever det): `skills/adapt/roster.md`, `skills/spec-drift/pin.json` og `skills/spec-drift/pin/`, `scripts/lint-skills.py` (`SUPERPOWERS_SKILLS`)

- [ ] **Step 1: Noter før-tilstanden**

Run: `cat ~/.claude/skills/gstack/VERSION 2>/dev/null; python3 scripts/spec-drift.py check; echo "exit=$?"`
Expected: gstack `1.91.2.0`, og `PIN MISMATCH` (exit 2). Det er utgangspunktet.

- [ ] **Step 2: Kjør `/gstack-upgrade`**

Invoker skillen `gstack-upgrade` og følg den. Noter til-versjonen (forventet `1.91.6.0` eller nyere).

- [ ] **Step 3: Vurder effekten, punkt for punkt**

Kjør og noter resultatet av hver:

```bash
# 1. Spec-drift-pinnen: hva endret seg i gstacks planfullførings-steg?
python3 scripts/spec-drift.py check; echo "exit=$?"
python3 scripts/spec-drift.py repin          # viser diff, endrer ingenting uten --yes --token

# 2. Fortsetter gstack å lese GSTACK_CODEX_MODEL, og hva er standard nå?
grep -rn "GSTACK_CODEX_MODEL" ~/.claude/skills/gstack/codex/SKILL.md | head -5
grep -rn "gpt-6" ~/.claude/skills/gstack/review/SKILL.md ~/.claude/skills/gstack/codex/SKILL.md | head -5

# 3. Finnes probe-hjelperen og funksjonene vi bruker?
grep -n "_gstack_codex_model_probe\|_gstack_codex_timeout_wrapper" ~/.claude/skills/gstack/bin/gstack-codex-probe | head -4

# 4. Har gstack fått egne worktree- eller landing-funksjoner som overlapper?
grep -rln "worktree\|wt merge\|land-and-deploy" ~/.claude/skills/gstack/*/SKILL.md | head -10

# 5. Roster-alarmene og resten av testene mot den nye installasjonen
python3 -m pytest tests/unit -q -p no:cacheprovider 2>&1 | tail -5
python3 scripts/lint-skills.py 2>&1 | tail -8
```

- [ ] **Step 4: Avgjør, og handle bare på det som er en reell følge**

For hvert punkt, skriv en av tre ting i «Phase 0 results»: **ingen endring nødvendig**, **endring gjort (commit-SHA)**, eller **utsatt (med utløser)**. Retningslinjer:

- **Pinnen (punkt 1):** en endring i gstacks steg 8 skal leses og vurderes av et menneske. Vis diffen for brukeren og foreslå; kjør `repin --yes --token …` bare etter et uttrykkelig ja (rutinen fra PR #76). Aldri ta en ny pinne blindt.
- **Roster (punkt 5):** legg `diagnosing-superpowers` til i `SUPERPOWERS_SKILLS` og i `skills/adapt/roster.md` **hvis** en gjennomlesing viser at den hører hjemme i rutingen; ellers dokumenter hvorfor ikke.
- **Modell (punkt 2):** endrer gstack standardmodellen eller slutter å lese `GSTACK_CODEX_MODEL`, oppdater komponent 7 og spesifikasjonens F9 og si fra til brukeren.
- **Overlapp (punkt 4):** har gstack fått en landingsfunksjon som gjør det samme som `land`, ta det opp med brukeren i stedet for å bygge videre.

- [ ] **Step 5: Kjør release-verifiseringen på nytt**

Run: `python3 scripts/lint-skills.py && python3 -m pytest -q -p no:cacheprovider 2>&1 | tail -3`
Expected: lint grønn. Antall røde tester er enten de samme to alarmene (hvis de ble utsatt) eller null (hvis pinne og roster ble oppdatert med samtykke).

- [ ] **Step 6: Commit det som ble endret (hvis noe)**

```bash
git add <bare de filene vurderingen faktisk endret> docs/superpowers/plans/2026-09-29-worktrunk-integration.md
git commit -m "chore(upstream): review after gstack upgrade — <kort resultat>

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push
```

### Task 9.3: Land denne funksjonen med sin egen `land`-skill

Dette er den første ekte bruken (og den beste testen) av det som er bygget.

- [ ] **Step 1: Be brukeren avklare de tre uavklarte filene på `main`**

`CLAUDE.md` på `main` er endret og overlapper denne landingen (kode 5). Spør brukeren: skal `CLAUDE.md`, `AGENTS.md` og `JEV-FORSLAG.md` committes, flyttes til en egen gren, eller forkastes? Gjør bare det brukeren velger; aldri `git stash`, aldri `git checkout -- <fil>` uten uttrykkelig ja.

- [ ] **Step 2: Godkjenn hooken hvis det ikke er gjort**

`wt config approvals list` skal vise `.config/wt.toml` under `APPROVED`. Ellers: be brukeren kjøre `wt config approvals add`.

- [ ] **Step 3: Preflight**

Run: `python3 skills/land/../../scripts/land-worktree.py --preflight-only`
Expected: `preflight ok`, exit 0. Får du en kode, følg tabellen i `skills/land/SKILL.md`.

- [ ] **Step 4: Land**

Invoker `/superpowers-gstack:land` (eller kjør `python3 scripts/land-worktree.py`). Forvent `LANDED feat/worktrunk-integration on main`. `pre-merge` kjører i omtrent 2,5 minutter.

- [ ] **Step 5: Rydd etter landing, i denne rekkefølgen**

Kjør `ExitWorktree` med `keep` hvis økten står i worktreet, deretter `wt -C <primærmappen> remove feat/worktrunk-integration`. Kjør `watch`-kommandoen fra landingsutskriften i bakgrunnen og rapporter CI-resultatet til brukeren.

- [ ] **Step 6: Rapporter tilstanden**

Skriv til brukeren: hva som er landet, hvilken SHA, CI-status, hvilke av de tre filene som ble avklart, og at `git worktree list` bare viser primærmappen. Oppdater minnet (`MEMORY.md`) med at 3.4.0 er landet og hva som ble utsatt, og slett `docs/superpowers/.handoff-last.md`-referansen hvis den er utdatert.

---

## Phase 0 results

Fylles ut under Phase 0 og Phase 9. Verdiene under er **ikke kjørt ennå**.

| Punkt | Resultat | Merknad |
|---|---|---|
| `EnterWorktree` med `path` mot `wt`-worktree (Task 0.1) | ikke kjørt | |
| Tillatelsesspørsmål oppstod? | ikke kjørt | |
| Subagenter arver arbeidsmappen (Task 0.2) | ikke kjørt | Ved FAIL: bruk reserven i Task 6.1 |
| Grunnlinje før endringer (Task 0.3) | forventet `574 passed, 2 failed` | |
| Personlig konfig, hvilke endringer godkjent (Task 9.1) | ikke kjørt | |
| Vurdering etter `/gstack-upgrade` (Task 9.2) | ikke kjørt | |

## Selvgjennomgang mot spesifikasjonen

- **Komponent 1** (blokk) → Task 4.1. **2** (git-hygiene v12) → 4.2. **3** (tre registre) → 4.1. **4** (`autoimplement`) → 6.1. **5** (branch-hygiene) → 7.1. **6** (`.config/wt.toml`) → 1.2. **7** (personlig konfig) → 9.1. **8** (`land-worktree.py`) → 2.1, 2.2. **9** (sesjonsskript) → 5.1. **10** (`land`-skill) → 3.1.
- **Feilkoder 2–13, 64, 70:** 2 (mode), 3 (godkjenning), 4 (main foran), 5 (overlapp), 8 (`wt` mangler), 9 (ingen hook), 11 (fetch), 12 (lås), 13 (skittent), 64 (bruk) har egne tester i 2.1; 6 (rød hook), 7 (origin flyttet), 10 (rebase) og 3 mot ekte `wt` i 2.2; 70 fanges av `_classify` og dekkes ikke av en test fordi den krever en `wt`-feil vi ikke kan fremprovosere deterministisk (bevisst gap, dokumentert her).
- **Utgivelsesgrind:** versjon, CHANGELOG, README, DENYLIST (4.2), ruting (3.1), lint, E2E og multi-lens i Phase 8.
- **`gstack-upgrade`:** Task 9.2, med vurdering før landing i 9.3.
- **Brukerens uavklarte filer:** aldri berørt på `main`; Task 9.3 steg 1 ber om avgjørelse.
