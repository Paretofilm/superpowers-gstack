# Vibe-profilen (3.6.0) — implementeringsplan

> **For agentiske arbeidere:** PÅKREVD UNDER-SKILL: Bruk superpowers:subagent-driven-development (anbefalt) eller superpowers:executing-plans for å gjennomføre planen oppgave for oppgave. Stegene bruker avkrysningssyntaks (`- [ ]`).

**Mål:** Et prosjekt kan velge arbeidsflytprofilen `vibe` én gang i `/adapt`, og pluginen gir det da en kort kontraktblokk i CLAUDE.md, en skill som kjører én feature fra intake til landing, mekanisk låsing av akseptansetester, en prosjektlokal kunnskapsskill og et måleverktøy for før/etter.

**Arkitektur:** Profilen er en pinfil (`.gstack/workflow`) som `scripts/adapt-claude-md.py` leser på samme måte som `.gstack/e2e-executor`; blokker får et `profiles`-filter ved siden av `tracks`. Prosedyren ligger i skillen `vibe` (lastes ved behov), reglene i blokken `gstack-vibe-v1` (alltid lastet). Låsing og måling er rene stdlib-skript med distinkte exit-koder og enhetstester mot midlertidige repoer og syntetiske transkripter.

**Teknologi:** Python 3 (bare standardbiblioteket, CI kjører 3.12), pytest, git, Markdown-skills.

**Spec:** `docs/superpowers/specs/2026-10-03-vibe-profil-design.md` (bare trinn 1, 3.6.0).

## Global Constraints

- Uten `.gstack/workflow` = `vibe` er alt som i 3.5.1 (`classic`). Ingen standard endres for andre brukere.
- Bare standardbiblioteket i Python; `from __future__ import annotations` øverst i hver ny modul.
- Skript: exit 0 ok, 2 avvist med grunnen på stderr (`BLOCKED — …`, `USAGE ERROR: …`, `UNREADABLE: …`), aldri en traceback. `lock-acceptance-tests.py verify` bruker i tillegg exit 1 for «endret».
- Blokkfiler: engelsk, linje 1 er en H2 med `<!-- gstack-<navn>-vN -->`, avsluttende linjeskift, aldri `emitted=` i fila, egne skills alltid med prefikset `/superpowers-gstack:` (lint E9).
- Kontraktblokken er under 30 linjer.
- Skill-beskrivelser er høyst 30 ord (lint W1); `python3 scripts/lint-skills.py` skal gi `0 error(s), 0 warning(s)` etter hver oppgave.
- superpowers- og gstack-skillene endres ikke.
- Versjonen bumpes til 3.6.0 bare i oppgave 10.
- Hver commit slutter med `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Ingen push og ingen landing; landing krever brukerens ja.
- Grunnlinje før oppgave 1: `pytest tests/unit -q` gir 760 passed og 1 failed. Den ene er `test_spec_drift_upstream_alarm.py::test_pin_matches_installed_gstack_when_present`, en drift-alarm mot den installerte gstack-versjonen på denne maskinen. Den hører ikke til denne grenen og skal være den eneste røde etter hver oppgave.

## Avvik fra specen (bevisste, specen rettes i oppgave 10)

1. **Kvitteringen committes i en egen commit.** Specen sier at tester, settings og kvittering committes «i samme commit», men kvitteringen skal inneholde SHA-en til committen som låste testene, og en commit kan ikke inneholde sin egen SHA. Testene committes først (`test(acceptance): lock <feature>`), settings og kvittering rett etter (`chore(acceptance): deny edits to <feature> tests`).
2. **Kvitteringen holder en liste med låser** (`{"locks": [...]}`), én per feature, slik at en ny feature kan låse sine tester uten å oppheve de gamle.
3. **Pekeren til kontekst-skillen står i vibe-blokken, ikke i prosjektets egen seksjon.** Skriptet har siden 3.1.0 aldri skrevet i umarkerte seksjoner; det er garantien som gjør `/adapt` trygg. Blokken får plassholderen `{{CONTEXT_SKILL}}`, som skriptet selv fyller ut.
4. **Standardnavnet er `<prosjekt>-context`.** En eksisterende `.claude/skills/*-context` eller `*-kontekst` brukes alltid (et eksisterende prosjekt kan ha f.eks. `<prosjekt>-kontekst`). Prosjektnavnet er `--project-name` eller mappenavnet til hoved-checkouten, så en worktree ikke gir et annet navn.
5. **Skillen går ikke selv inn i plan-modus.** Å forlate plan-modus spør brukeren én gang til, og det ville gi to kontrollpunkter. Intaket (steg 0–2) er skrivebeskyttet for kode uansett modus.

## Review Focus

1. **En vokst vibe-blokk når prosjektet bytter til `classic`.** Brukerens egne linjer i blokken skal aldri forsvinne: seksjonen blir stående og rapporten sier hvorfor (test i oppgave 4).
2. **`lock` med andre, urelaterte endringer i indeksen.** Bare testfilene, settings og kvitteringen skal havne i committene; en fil brukeren hadde staget skal fortsatt være staget og ikke committet (test i oppgave 2).
3. **`verify` kjørt fra en undermappe eller en worktree.** Skriptet må finne toppnivået selv og sammenligne mot låse-committen, også når endringen ikke er committet (test i oppgave 2).
4. **Ødelagte eller halvskrevne linjer i transkripter** (en sesjon som skrives mens måleverktøyet leser). Linjen hoppes over, tallene for resten stemmer (test i oppgave 7).
5. **To låser som deler et mønster.** `unlock` av den ene skal ikke fjerne en `deny`-regel den andre fortsatt trenger (test i oppgave 2).

---

## Filstruktur

| Fil | Ansvar | Oppgave |
|---|---|---|
| `scripts/adapt-claude-md.py` | Leser `.gstack/workflow`; `Block.profiles`; fjerner en vibe-blokk under `classic`; oppretter kontekst-skillen | 1, 4, 5 |
| `scripts/lock-acceptance-tests.py` | `lock` / `verify` / `unlock` | 2 |
| `skills/vibe/SKILL.md` | Prosedyren for én feature (steg 0–9) | 3 |
| `skills/adapt/blocks/vibe-contract.md` | Kontraktblokken `gstack-vibe-v1` | 4, 5 |
| `skills/adapt/blocks/PLACEHOLDERS.md` | Regelen for `{{CONTEXT_SKILL}}` | 5 |
| `skills/adapt/templates/project-context.md` | Mal for kontekst-skillen | 5 |
| `skills/adapt/SKILL.md` | Profilspørsmålet i steg 4, neste steg i steg 7 | 6 |
| `scripts/workflow_metrics/{__init__,lib,tokens,asks,overhead}.py` | Lesing og de tre kjernemålingene | 7 |
| `scripts/workflow_metrics/{skills,triggers,mcp,digest}.py` | De fire øvrige målingene | 8 |
| `scripts/workflow-metrics.py` | CLI-inngang | 7, 8 |
| `skills/workflow-metrics/SKILL.md` | Før/etter-måling | 9 |
| `scripts/lint-skills.py` | `MARKER_BLOCKS` får `vibe-contract.md` | 4 |
| `CLAUDE.md`, `README.md`, `skills/adapt/roster.md`, `skills/adapt/model-routing.md` | Ruting og dokumentasjon | 3, 9 |
| `.claude-plugin/plugin.json`, `CHANGELOG.md`, specen | Release | 10 |
| `tests/unit/test_adapt_script.py` | Profil, blokk, kontekst-skill | 1, 4, 5 |
| `tests/unit/test_lock_acceptance_tests.py` | Låseskriptet | 2 |
| `tests/unit/test_vibe_skill.py` | Skillkontrakten for `vibe` og `/adapt` steg 4 | 3, 6 |
| `tests/unit/test_workflow_metrics.py` | Måleverktøyet | 7, 8, 9 |

Alle kommandoer kjøres fra worktree-roten `<repo>`.

---

### Task 1: Profilpinnen `.gstack/workflow`

**Files:**
- Modify: `scripts/adapt-claude-md.py` (konstanter ved `EXECUTORS` linje 72; `Context` linje 345–355; ny `read_workflow` etter `read_executor` linje 941–950; `render` linje 840; `main` linje 1019–1057)
- Test: `tests/unit/test_adapt_script.py`

**Interfaces:**
- Produces: `PROFILES = ("vibe", "classic")`; `read_workflow(project: Path, report: Report | None = None) -> str`; `Context.profile: str` (standard `"classic"`); rapportens første linje slutter med `track <t>, workflow <p>)`; testhjelperen `project(tmp_path, claude_md=None, track=None, workflow=None)`.

- [ ] **Step 1: Utvid testhjelperen og skriv de feilende testene**

Erstatt `project()` i `tests/unit/test_adapt_script.py` (linje 58–67):

```python
def project(tmp_path, claude_md: str | None = None, track: str | None = None,
            workflow: str | None = None) -> Path:
    p = tmp_path / "proj"
    p.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True)
    if claude_md is not None:
        (p / "CLAUDE.md").write_text(claude_md)
    if track:
        (p / ".gstack").mkdir(exist_ok=True)
        (p / ".gstack" / "track").write_text(track + "\n")
    if workflow:
        (p / ".gstack").mkdir(exist_ok=True)
        (p / ".gstack" / "workflow").write_text(workflow + "\n")
    return p
```

Legg til nederst i fila:

```python
# --- 3.6.0: the workflow profile pin ------------------------------------------------

def test_no_workflow_pin_means_classic_and_the_report_says_so(tmp_path):
    proj = project(tmp_path)
    p = run(proj, *WEB_SETS)
    assert "workflow classic)" in p.stdout.splitlines()[0]
    assert "no .gstack/workflow file" in p.stdout


def test_a_vibe_pin_is_read(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    p = run(proj, *WEB_SETS)
    assert "workflow vibe)" in p.stdout.splitlines()[0]
    assert "no .gstack/workflow file" not in p.stdout


@pytest.mark.parametrize("value", ["vibe ", "Vibe", "lite", ""])
def test_an_invalid_workflow_pin_is_blocked_and_nothing_written(tmp_path, value):
    proj = project(tmp_path, claude_md="# P\n\nkeep me\n")
    (proj / ".gstack").mkdir()
    (proj / ".gstack" / "workflow").write_text(value + "\n")
    p = run(proj, *WEB_SETS, expect=2)
    assert "BLOCKED — invalid .gstack/workflow" in p.stderr
    assert (proj / "CLAUDE.md").read_text() == "# P\n\nkeep me\n"
    assert not (proj / ".gstack" / "CLAUDE.md.pre-adapt").exists()
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_adapt_script.py -q -k "workflow"`
Expected: FAIL — `workflow classic)` finnes ikke i rapporten, og den ugyldige pinnen gir exit 0.

- [ ] **Step 3: Implementer**

I `scripts/adapt-claude-md.py`, rett under `EXECUTORS = ("host", "vm")`:

```python
PROFILES = ("vibe", "classic")
```

I `Context`, mellom `project: str` og `needed`:

```python
    profile: str = "classic"
```

Rett etter `read_executor`:

```python
def read_workflow(project: Path, report: Report | None = None) -> str:
    """The project's workflow profile. Exactly `vibe` or `classic`; the file's newline
    is the only thing stripped, so `vibe ` is refused, never repaired. No file is
    classic: the profile is opt-in, and a run with nobody to ask never opts in."""
    f = project / ".gstack" / "workflow"
    if not f.is_file():
        if report is not None:
            report.notes.append("no .gstack/workflow file — classic profile "
                                "(write `vibe` there to opt in to the vibe contract)")
        return "classic"
    value = f.read_text().removesuffix("\n")
    if value not in PROFILES:
        raise Refusal(f"BLOCKED — invalid .gstack/workflow {value!r}: must be exactly vibe or classic")
    return value
```

I `render`, første linje:

```python
    out = [f"ADAPT REPORT — {'dry run' if dry_run else 'applied'} (superpowers-gstack {ctx.version}, "
           f"track {ctx.track}, workflow {ctx.profile})", ""]
```

I `main`, rett etter `track = read_track(project, a.track, pre_notes)`:

```python
        profile = read_workflow(project, pre_notes)
```

og i `Context(...)`-kallet, etter `project=...`:

```python
                      profile=profile)
```

(den avsluttende parentesen flyttes; `project=a.project_name or project_name(text or "", project),` får komma.)

- [ ] **Step 4: Kjør testene og se dem passere**

Run: `python3 -m pytest tests/unit/test_adapt_script.py -q`
Expected: alle passerer (også de gamle — ingen eksisterende test leser rapportens første linje).

- [ ] **Step 5: Commit**

```bash
git add scripts/adapt-claude-md.py tests/unit/test_adapt_script.py
git commit -m "feat(adapt): read the .gstack/workflow profile pin (vibe|classic, default classic)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `scripts/lock-acceptance-tests.py`

**Files:**
- Create: `scripts/lock-acceptance-tests.py`
- Test: `tests/unit/test_lock_acceptance_tests.py`

**Interfaces:**
- Produces (CLI, brukt av skillen `vibe` i oppgave 3):
  - `lock-acceptance-tests.py lock --feature <navn> --path <glob> [--path <glob> ...] [--project-dir <dir>]` → exit 0, to commits.
  - `lock-acceptance-tests.py verify [--feature <navn>] [--project-dir <dir>]` → exit 0 uendret, 1 endret (filene listes på stdout, én per linje med `CHANGED <feature> <fil>`), 2 ingen kvittering eller ukjent feature.
  - `lock-acceptance-tests.py unlock --feature <navn> [--project-dir <dir>]` → exit 0, én commit.
- Kvitteringen `.gstack/acceptance-lock.json`: `{"locks": [{"feature", "commit", "paths", "files", "rules", "added", "locked_at"}]}`. `rules` er alle regler låsen trenger; `added` er de låsen selv la til (og dermed eier).
- Regelformen: `Edit(/<glob>)` og `Write(/<glob>)`. En ledende `/` i prosjektets `.claude/settings.json` ankres i prosjektets arbeidsmappe, også i en worktree (Claude Code-dokumentasjonen, «Configure permissions», sjekket 2026-10-03).

- [ ] **Step 1: Skriv de feilende testene**

`tests/unit/test_lock_acceptance_tests.py`:

```python
"""scripts/lock-acceptance-tests.py — the acceptance tests the user approved stay as approved.

The vibe workflow has one checkpoint: the user reads the acceptance tests once. After
that the tests are the contract, and an agent that edits one to turn red into green
has broken it silently. `lock` commits the tests and denies Edit/Write on them;
`verify` is the real gate (a deny rule does not stop `sed` through Bash).
These tests run the script against temporary git repositories.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "lock-acceptance-tests.py"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def repo(tmp_path: Path) -> Path:
    r = tmp_path / "app"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "T")
    git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("app\n")
    git(r, "add", "README.md")
    git(r, "commit", "-q", "-m", "init")
    acc = r / "Tests" / "Acceptance"
    acc.mkdir(parents=True)
    (acc / "test_a.py").write_text("def test_a():\n    assert 1 == 1\n")
    (acc / "test_b.py").write_text("def test_b():\n    assert 2 == 2\n")
    return r


def run(r: Path, *args: str, expect: int = 0, cwd: Path | None = None):
    p = subprocess.run([sys.executable, str(SCRIPT), *args, "--project-dir", str(cwd or r)],
                       capture_output=True, text=True)
    assert p.returncode == expect, f"exit {p.returncode} (wanted {expect})\n{p.stdout}\n{p.stderr}"
    assert "Traceback" not in p.stderr
    return p


def receipt(r: Path) -> dict:
    return json.loads((r / ".gstack" / "acceptance-lock.json").read_text())


def settings(r: Path) -> dict:
    return json.loads((r / ".claude" / "settings.json").read_text())


def lock(r: Path, feature: str = "radid", *globs: str):
    return run(r, "lock", "--feature", feature, *[x for g in (globs or ("Tests/Acceptance/**",)) for x in ("--path", g)])


def test_lock_commits_the_tests_then_the_rules_and_the_receipt(tmp_path):
    r = repo(tmp_path)
    lock(r)
    log = git(r, "log", "--format=%s", "-3").splitlines()
    assert log[0] == "chore(acceptance): deny edits to radid tests"
    assert log[1] == "test(acceptance): lock radid"
    test_commit = git(r, "rev-parse", "HEAD~1").strip()
    lk = receipt(r)["locks"][0]
    assert lk["commit"] == test_commit
    assert lk["files"] == ["Tests/Acceptance/test_a.py", "Tests/Acceptance/test_b.py"]
    assert settings(r)["permissions"]["deny"] == ["Edit(/Tests/Acceptance/**)", "Write(/Tests/Acceptance/**)"]
    assert git(r, "status", "--porcelain") == ""


def test_verify_is_zero_when_untouched_and_one_for_any_change(tmp_path):
    r = repo(tmp_path)
    lock(r)
    run(r, "verify")
    f = r / "Tests" / "Acceptance" / "test_a.py"
    f.write_text("def test_a():\n    assert True\n")          # not committed
    p = run(r, "verify", expect=1)
    assert "CHANGED radid Tests/Acceptance/test_a.py" in p.stdout
    git(r, "add", str(f))                                      # staged
    run(r, "verify", expect=1)
    git(r, "commit", "-q", "-m", "weaken")                     # committed
    run(r, "verify", expect=1)


def test_verify_sees_a_deleted_test(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "test_b.py").unlink()
    p = run(r, "verify", expect=1)
    assert "test_b.py" in p.stdout


def test_verify_without_a_receipt_is_two(tmp_path):
    r = repo(tmp_path)
    p = run(r, "verify", expect=2)
    assert "no acceptance lock" in p.stderr


def test_verify_from_a_subdirectory_finds_the_top_level(tmp_path):
    r = repo(tmp_path)
    lock(r)
    (r / "Tests" / "Acceptance" / "test_a.py").write_text("changed\n")
    run(r, "verify", expect=1, cwd=r / "Tests")


def test_existing_settings_are_kept(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text(json.dumps(
        {"model": "opusplan", "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Read(/.env)"]}}))
    lock(r)
    s = settings(r)
    assert s["model"] == "opusplan" and s["permissions"]["allow"] == ["Bash(ls:*)"]
    assert s["permissions"]["deny"][0] == "Read(/.env)"


def test_invalid_settings_json_refuses_before_any_commit(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text("{ not json")
    before = git(r, "rev-parse", "HEAD")
    p = lock_expect(r, 2)
    assert "BLOCKED" in p.stderr and "settings.json" in p.stderr
    assert git(r, "rev-parse", "HEAD") == before
    assert not (r / ".gstack" / "acceptance-lock.json").exists()


def lock_expect(r: Path, code: int, *extra: str):
    return run(r, "lock", "--feature", "radid", "--path", "Tests/Acceptance/**", *extra, expect=code)


@pytest.mark.parametrize("glob", ["NoSuchDir/**", "/Tests/**", "../elsewhere/**"])
def test_a_bad_glob_refuses(tmp_path, glob):
    r = repo(tmp_path)
    p = run(r, "lock", "--feature", "radid", "--path", glob, expect=2)
    assert "BLOCKED" in p.stderr


def test_a_feature_cannot_be_locked_twice(tmp_path):
    r = repo(tmp_path)
    lock(r)
    p = lock_expect(r, 2)
    assert "already locked" in p.stderr


def test_unrelated_staged_work_is_not_committed(tmp_path):
    r = repo(tmp_path)
    (r / "notes.txt").write_text("mine\n")
    git(r, "add", "notes.txt")
    lock(r)
    assert "notes.txt" not in git(r, "log", "--name-only", "--format=", "-2")
    assert git(r, "diff", "--cached", "--name-only").strip() == "notes.txt"


def test_unlock_removes_only_its_own_rules(tmp_path):
    r = repo(tmp_path)
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"deny": ["Read(/.env)"]}}))
    lock(r)
    run(r, "unlock", "--feature", "radid")
    assert settings(r)["permissions"]["deny"] == ["Read(/.env)"]
    assert receipt(r)["locks"] == []
    assert git(r, "log", "--format=%s", "-1").strip() == "chore(acceptance): unlock radid tests (user request)"


def test_two_locks_sharing_a_glob_keep_the_rule_until_both_are_unlocked(tmp_path):
    r = repo(tmp_path)
    lock(r, "one")
    (r / "Tests" / "Acceptance" / "test_c.py").write_text("def test_c():\n    pass\n")
    lock(r, "two")
    run(r, "unlock", "--feature", "one")
    assert "Edit(/Tests/Acceptance/**)" in settings(r)["permissions"]["deny"]
    run(r, "unlock", "--feature", "two")
    assert "permissions" not in settings(r)


def test_unlock_of_an_unknown_feature_is_two(tmp_path):
    r = repo(tmp_path)
    lock(r)
    p = run(r, "unlock", "--feature", "nope", expect=2)
    assert "nope" in p.stderr
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_lock_acceptance_tests.py -q`
Expected: FAIL — skriptet finnes ikke (`can't open file`).

- [ ] **Step 3: Implementer skriptet**

`scripts/lock-acceptance-tests.py`:

```python
#!/usr/bin/env python3
"""lock-acceptance-tests — keep the acceptance tests the user approved exactly as approved.

/superpowers-gstack:vibe shows the user the acceptance tests once; after their ok the
tests are the contract for the rest of the feature.

  lock    commits the test files (`test(acceptance): lock <feature>`), then adds
          `Edit(/<glob>)` and `Write(/<glob>)` deny rules to the project's
          .claude/settings.json, records the lock in .gstack/acceptance-lock.json and
          commits both (`chore(acceptance): deny edits to <feature> tests`). Two
          commits because the receipt names the first one's SHA.
  verify  exit 0 when every locked path is identical to its lock commit, working tree
          and index included; exit 1 lists `CHANGED <feature> <file>`; exit 2 when
          there is no receipt or no such feature.
  unlock  removes one feature's lock and only the deny rules no other lock still
          needs. Run it only when the user asks.

A deny rule stops the Edit and Write tools, not `sed` through Bash. `verify` is the
gate; the rules make the honest path the easy one.

Exit 0 ok, 1 changed (verify), 2 refused — the reason is on stderr. Never a traceback.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT = Path(".gstack") / "acceptance-lock.json"
SETTINGS = Path(".claude") / "settings.json"
FEATURE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Refusal(Exception):
    pass


def git(top: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=top, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"BLOCKED — `git {' '.join(args)}` failed: {p.stderr.strip()}")
    return p.stdout


def toplevel(project: Path) -> Path:
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=project, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"BLOCKED — {project} is not inside a git repository")
    return Path(p.stdout.strip())


def read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Refusal(f"BLOCKED — {path} is not valid JSON ({exc}); fix it by hand — nothing was changed")
    if not isinstance(data, dict):
        raise Refusal(f"BLOCKED — {path} must hold a JSON object — nothing was changed")
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_feature(name: str) -> str:
    if not FEATURE_RE.match(name):
        raise Refusal(f"USAGE ERROR: --feature {name!r} must be letters, digits, `.`, `_` or `-` (max 64)")
    return name


def expand(top: Path, globs: list[str]) -> list[str]:
    files: set[str] = set()
    for g in globs:
        if g.startswith("/") or ".." in Path(g).parts:
            raise Refusal(f"BLOCKED — --path {g!r} must be relative to the repository root and stay inside it")
        hits = [p for p in top.glob(g) if p.is_file() and ".git" not in p.relative_to(top).parts]
        if not hits:
            raise Refusal(f"BLOCKED — --path {g!r} matches no file; write the acceptance tests first")
        files |= {p.relative_to(top).as_posix() for p in hits}
    return sorted(files)


def rules_for(globs: list[str]) -> list[str]:
    return [f"{tool}(/{g})" for g in globs for tool in ("Edit", "Write")]


def deny_list(settings: dict) -> list:
    perms = settings.setdefault("permissions", {})
    if not isinstance(perms, dict) or not isinstance(perms.setdefault("deny", []), list):
        raise Refusal("BLOCKED — .claude/settings.json has a `permissions.deny` that is not a list — nothing was changed")
    return perms["deny"]


def commit_meta(top: Path, message: str) -> None:
    git(top, "add", "-f", "--", str(SETTINGS), str(RECEIPT))
    git(top, "commit", "-q", "-m", message, "--", str(SETTINGS), str(RECEIPT))


def cmd_lock(top: Path, feature: str, globs: list[str]) -> int:
    receipt = read_json(top / RECEIPT, {"locks": []})
    settings = read_json(top / SETTINGS, {})
    deny = deny_list(settings)
    if any(lk.get("feature") == feature for lk in receipt.setdefault("locks", [])):
        raise Refusal(f"BLOCKED — {feature!r} is already locked; run verify, or unlock it first (only when the user asks)")
    files = expand(top, globs)
    git(top, "add", "--", *files)
    if git(top, "diff", "--cached", "--name-only", "--", *files).strip():
        git(top, "commit", "-q", "-m", f"test(acceptance): lock {feature}", "--", *files)
    commit = git(top, "rev-parse", "HEAD").strip()
    rules = rules_for(globs)
    added = [r for r in rules if r not in deny]
    deny.extend(added)
    receipt["locks"].append({"feature": feature, "commit": commit, "paths": globs, "files": files,
                             "rules": rules, "added": added,
                             "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    write_json(top / SETTINGS, settings)
    write_json(top / RECEIPT, receipt)
    commit_meta(top, f"chore(acceptance): deny edits to {feature} tests")
    print(f"locked {feature}: {len(files)} file(s) at {commit[:12]}; deny rules: {', '.join(rules)}")
    return 0


def cmd_verify(top: Path, feature: str | None) -> int:
    receipt = read_json(top / RECEIPT, None)
    if receipt is None:
        print(f"no acceptance lock in this project ({RECEIPT} is missing)", file=sys.stderr)
        return 2
    locks = [lk for lk in receipt.get("locks", []) if feature in (None, lk.get("feature"))]
    if feature is not None and not locks:
        print(f"no acceptance lock named {feature!r}", file=sys.stderr)
        return 2
    changed = []
    for lk in locks:
        out = git(top, "diff", "--name-only", lk["commit"], "--", *[f":(glob){g}" for g in lk["paths"]])
        changed += [f"CHANGED {lk['feature']} {f}" for f in out.splitlines() if f]
    if changed:
        print("\n".join(changed))
        print("A locked acceptance test differs from what the user approved. Restore it "
              "(`git checkout <commit> -- <file>`), or stop and tell the user which test is wrong and why.")
        return 1
    print(f"acceptance tests unchanged: {', '.join(lk['feature'] for lk in locks) or 'no locks'}")
    return 0


def cmd_unlock(top: Path, feature: str) -> int:
    receipt = read_json(top / RECEIPT, None)
    lock = next((lk for lk in (receipt or {}).get("locks", []) if lk.get("feature") == feature), None)
    if lock is None:
        raise Refusal(f"BLOCKED — no acceptance lock named {feature!r}")
    settings = read_json(top / SETTINGS, {})
    deny = deny_list(settings)
    others = [lk for lk in receipt["locks"] if lk is not lock]
    for rule in lock.get("added", []):
        heir = next((lk for lk in others if rule in lk.get("rules", [])), None)
        if heir is not None:
            heir.setdefault("added", []).append(rule)    # still needed: ownership moves
        elif rule in deny:
            deny.remove(rule)
    if not deny:
        del settings["permissions"]["deny"]
    if not settings.get("permissions"):
        settings.pop("permissions", None)
    receipt["locks"] = others
    write_json(top / SETTINGS, settings)
    write_json(top / RECEIPT, receipt)
    commit_meta(top, f"chore(acceptance): unlock {feature} tests (user request)")
    print(f"unlocked {feature}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("lock")
    lk.add_argument("--feature", required=True)
    lk.add_argument("--path", action="append", required=True, metavar="GLOB")
    vf = sub.add_parser("verify")
    vf.add_argument("--feature")
    ul = sub.add_parser("unlock")
    ul.add_argument("--feature", required=True)
    for p in (lk, vf, ul):
        p.add_argument("--project-dir", default=".")
    a = ap.parse_args(argv)
    try:
        top = toplevel(Path(a.project_dir).expanduser().resolve())
        if a.cmd == "lock":
            return cmd_lock(top, check_feature(a.feature), a.path)
        if a.cmd == "verify":
            return cmd_verify(top, a.feature)
        return cmd_unlock(top, check_feature(a.feature))
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(f"INTERNAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

`chmod +x scripts/lock-acceptance-tests.py`.

- [ ] **Step 4: Kjør testene og se dem passere**

Run: `python3 -m pytest tests/unit/test_lock_acceptance_tests.py -q`
Expected: alle passerer. Feiler `test_unrelated_staged_work_is_not_committed`, sjekk at begge `git commit`-kallene har pathspec (`-- <filer>`): uten den tar git med alt som er staget.

- [ ] **Step 5: Commit**

```bash
git add scripts/lock-acceptance-tests.py tests/unit/test_lock_acceptance_tests.py
git commit -m "feat(scripts): lock-acceptance-tests.py — lock, verify and unlock approved acceptance tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Skillen `vibe` og rutingen til den

**Files:**
- Create: `skills/vibe/SKILL.md`
- Modify: `CLAUDE.md` (rutingslisten, etter `spec-drift`-linjen), `README.md` (skilllisten og antallet), `skills/adapt/roster.md` (etter `spec-drift`-raden), `skills/adapt/model-routing.md` (tabellen «Plugin-internal skills»)
- Test: `tests/unit/test_vibe_skill.py`

**Interfaces:**
- Consumes: `lock-acceptance-tests.py lock|verify` (oppgave 2), `.gstack/workflow` (oppgave 1).
- Produces: skillnavnet `vibe` (`/superpowers-gstack:vibe`), som blokken i oppgave 4 og `/adapt` i oppgave 6 peker til; filoppsettet `docs/superpowers/vibe/<YYYY-MM-DD>-<feature>/{SPEC,PLAN,STATUS,ROUNDS}.md`.

- [ ] **Step 1: Skriv de feilende testene**

`tests/unit/test_vibe_skill.py`:

```python
"""The vibe skill's contract: one intake, one checkpoint, locked tests, one review, landing.

The skill is prose an agent follows; these tests pin the sentences whose loss would
silently bring back the stops the workflow exists to remove, or drop a guard.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIBE = (REPO / "skills" / "vibe" / "SKILL.md").read_text()


def test_the_description_fits_the_budget():
    desc = re.search(r"^description: (.+)$", VIBE, re.M).group(1)
    assert len(desc.split()) <= 30


def test_intake_is_one_round_with_acceptance_criteria_and_out_of_scope():
    assert "one `AskUserQuestion` round" in VIBE
    assert "at most eight questions" in VIBE
    assert "acceptance criteria" in VIBE and "out of scope" in VIBE


def test_the_one_checkpoint_carries_a_goal_line_and_locks_the_tests():
    assert "/goal All tasks in PLAN.md are done" in VIBE
    assert "lock-acceptance-tests.py\" lock --feature" in VIBE
    assert "lock-acceptance-tests.py\" verify" in VIBE


def test_the_two_fixed_rules_for_every_phase():
    assert "wire what you build into the app in the same round" in VIBE
    assert "every place the app already does the same job" in VIBE


def test_the_stop_list_and_the_ruling_format():
    for item in ("irreversible or destructive", "security-sensitive", "outside the worktree",
                 "push to a remote", "money", "licence", "real blocker"):
        assert item in VIBE, item
    assert "Ruling: <choice> — <why> — <cost if wrong>" in VIBE


def test_one_review_at_the_end_and_landing_by_the_landing_mode():
    assert "/superpowers-gstack:pitfall-verification" in VIBE
    assert "once, after the last phase" in VIBE
    assert "Landing mode:" in VIBE and "/superpowers-gstack:land" in VIBE


def test_lessons_go_to_the_context_skill_not_claude_md():
    assert "ROUNDS.md" in VIBE and "at most three" in VIBE
    assert "How we work" in VIBE
    assert "never into CLAUDE.md" in VIBE


def test_the_skill_never_enters_plan_mode_itself():
    assert "Do not enter plan mode yourself" in VIBE
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_vibe_skill.py -q`
Expected: FAIL — `FileNotFoundError: .../skills/vibe/SKILL.md`.

- [ ] **Step 3: Skriv skillen**

`skills/vibe/SKILL.md`:

````markdown
---
name: vibe
description: Build one feature end to end under the vibe contract — one intake round, locked acceptance tests as the only checkpoint, a fresh subagent per phase, one review, landing.
---

# Vibe: one feature, intake to landing

Invoke with: `/superpowers-gstack:vibe <what to build>`

The user answers questions once, reads the acceptance tests once, and reviews the
finished work once. Everything between is yours to decide and log. The rules live in
the project's CLAUDE.md section **Vibe contract** (marker `gstack-vibe-v1`); this skill
is the procedure. If `.gstack/workflow` is not `vibe`, say so in one line of the intake
(the contract's standing approvals then hold for this invocation only) and suggest
`/superpowers-gstack:adapt` to choose the profile for good.

Begin every Bash call that needs the lock script with:

```bash
SKILL_DIR='<the base directory the Skill tool printed when this skill loaded>'
LOCK="$SKILL_DIR/../../scripts/lock-acceptance-tests.py"
[ -f "$LOCK" ] || LOCK=$(ls ~/.claude/plugins/cache/*/superpowers-gstack/*/scripts/lock-acceptance-tests.py 2>/dev/null | sort -V | tail -1)
[ -f "$LOCK" ] || { echo "BLOCKED — lock-acceptance-tests.py not found; run /plugin update superpowers-gstack"; exit 2; }
```

## Step 0: Read before asking

Load the project's context skill (`.claude/skills/*-context` or `*-kontekst`) if there
is one, then the code the feature touches. Classify the scope: files, tracks, whether
the result is visual (UI, render, video), and the risk tier
`scripts/classify-change.py` would give it. Steps 0–2 change no code. Do not enter plan
mode yourself: leaving it asks the user a second time, and the acceptance tests are the
one checkpoint.

## Step 1: Intake — one round

Ask everything in one `AskUserQuestion` round: at most eight questions, four per call,
recommended option first and marked `(Recommended)`. Always ask for:
- the reference ("fasit") and the 5–10 acceptance criteria you drew from the request,
  so the user can correct them;
- what is out of scope.

Ask nothing you can find in the code, the context skill or CLAUDE.md. After this round,
design, spec and plan are pre-approved.

## Step 2: SPEC.md and PLAN.md

Write `docs/superpowers/vibe/<YYYY-MM-DD>-<feature>/SPEC.md` (goal, non-goals,
acceptance criteria) and `PLAN.md` (small tasks; each has one test and one
"done when" line; no code). Commit both. Do not wait for a spec or plan review.

## Step 3: Acceptance tests — the one checkpoint

Write the acceptance tests from the criteria, in a directory of their own (for example
`Tests/Acceptance/` or `tests/acceptance/`). For visual work the test is a truth check
against the reference — a screenshot or render measured against it — not only unit
tests. Then send ONE message: a short overview (test name, what it checks), and this
line for the user to paste:

```
/goal All tasks in PLAN.md are done: tests green, build without warnings, STATUS.md updated. Or stop after 60 turns.
```

`/goal` is started by the user; without it, continue with step 4 when they say ok.
After their ok, lock the tests:

```bash
python3 "$LOCK" lock --feature <feature> --path '<acceptance-test glob>'
```

From here on, never edit a locked test to turn red into green, by any tool. If a test
is wrong, stop and say which one and why; only the user unlocks
(`python3 "$LOCK" unlock --feature <feature>`).

## Step 4: One fresh subagent per phase

Run the phases of PLAN.md with `superpowers:subagent-driven-development`: each phase's
part of the plan is one subagent's brief; the main thread orchestrates and stays under
about 150k tokens of context. Two fixed rules go into every brief:
- **wire what you build into the app in the same round** the tests turn green — green
  tests on code nothing calls are not done;
- **find every place the app already does the same job** and make it follow the new
  rules.

At every phase boundary update `STATUS.md` (done, remaining, open Rulings). Add one line
per round to `ROUNDS.md`: what was tried, which tests still failed. Never ask "what
next" between phases.

**Stop only for:** irreversible or destructive actions, security-sensitive actions,
side effects outside the worktree, a push to a remote, money, a licence, or a real
blocker. Decide everything else and log it in STATUS.md as
`Ruling: <choice> — <why> — <cost if wrong>`.

## Step 5: Tests while working

A subagent runs only the tests that cover what it changed (the affected target or a
`--filter`). The full suite runs at each phase boundary and once before landing.
After a timeout: at most two reruns, then one single run with its log.

## Step 6: One review, at the end

Invoke `/superpowers-gstack:pitfall-verification` once, after the last phase, on the
whole branch; its tier is computed as always. Fix critical and important findings; do
not re-review minor ones. No plan reviews, no `/autoplan`.

## Step 7: The lock must hold

```bash
python3 "$LOCK" verify
```

Exit 0 is required before landing. Exit 1 names each changed file: restore it from the
lock commit, or stop and tell the user which test is wrong.

## Step 8: Land

Land by the project's `Landing mode:` line — `solo` → `/superpowers-gstack:land`,
`pr` → `/ship` — with no options menu. Ask once about the push only when the project
requires it.

## Step 9: Final report and lessons

One message: what was built, how the user verifies it, every Ruling, deferred findings.
Then read `ROUNDS.md`: a mistake that came back in two phases or more becomes one working
rule — at most three per feature — in the **How we work** section of the context skill,
never into CLAUDE.md. Touch neither the locked tests nor the contract in this step.
````

- [ ] **Step 4: Ruting og dokumentasjon**

`CLAUDE.md`, i «Key routing rules», rett etter `spec-drift`-linjen:

```markdown
- Build a feature end to end in a project whose `.gstack/workflow` is `vibe` ("vibe this", "build X", "lag featuren ferdig") → invoke /superpowers-gstack:vibe <what to build>. One intake round, acceptance tests locked by `scripts/lock-acceptance-tests.py` after the user's one ok, a fresh subagent per phase, one /superpowers-gstack:pitfall-verification at the end, landing by the `Landing mode:` line. In a `classic` project, route to /superpowers:brainstorming as before unless the user asks for vibe.
```

`skills/adapt/roster.md`, rett etter `spec-drift`-raden:

```markdown
| `/superpowers-gstack:vibe` | Projects whose `.gstack/workflow` is `vibe` — one feature from intake to landing: one question round, locked acceptance tests as the only checkpoint, a fresh subagent per phase, one review at the end. |
```

`skills/adapt/model-routing.md`, i «Plugin-internal skills», etter `spec-drift`-raden:

```markdown
| `/superpowers-gstack:vibe`                   | opus      |
```

`README.md`: endre `with fifteen skills:` til `with sixteen skills:`, og legg til etter `/spec-drift`-punktet:

```markdown
  - `/vibe` — one feature from intake to landing under the vibe contract (opt-in per project with `.gstack/workflow`): one question round, acceptance tests locked by `scripts/lock-acceptance-tests.py` after the user's one ok, a fresh subagent per phase, one review at the end, landing by the `Landing mode:` line. Invoked as `/superpowers-gstack:vibe <what to build>`.
```

- [ ] **Step 5: Kjør tester og lint**

Run: `python3 -m pytest tests/unit/test_vibe_skill.py tests/unit/test_spec_drift_skill.py -q && python3 scripts/lint-skills.py`
Expected: testene passerer; lint `0 error(s), 0 warning(s) across 16 skills`.

- [ ] **Step 6: Commit**

```bash
git add skills/vibe/SKILL.md tests/unit/test_vibe_skill.py CLAUDE.md README.md skills/adapt/roster.md skills/adapt/model-routing.md
git commit -m "feat(vibe): one feature from intake to landing under the vibe contract

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Kontraktblokken `gstack-vibe-v1` og profilfilteret

**Files:**
- Create: `skills/adapt/blocks/vibe-contract.md`
- Modify: `scripts/adapt-claude-md.py` (`Block` linje 98–104, `BLOCKS` linje 107–121, `apply_block` linje 544–565, ny `_remove_out_of_profile` rett før `apply_block`), `scripts/lint-skills.py` (`MARKER_BLOCKS` linje 131–141)
- Test: `tests/unit/test_adapt_script.py`

**Interfaces:**
- Consumes: `Context.profile` (oppgave 1); skillnavnet `/superpowers-gstack:vibe` (oppgave 3).
- Produces: `Block.profiles: frozenset | None`; blokkfila `vibe-contract.md` med markør `gstack-vibe`. Oppgave 5 legger én linje med `{{CONTEXT_SKILL}}` til i samme fil.

- [ ] **Step 1: Skriv de feilende testene**

Nederst i `tests/unit/test_adapt_script.py`:

```python
# --- 3.6.0: the vibe contract block -------------------------------------------------

def vibe_heading_line(text: str) -> str:
    return next(l for l in text.splitlines() if "gstack-vibe-v" in l)


def test_a_vibe_project_gets_the_vibe_contract_and_a_classic_one_does_not(tmp_path):
    vibe = project(tmp_path / "v", workflow="vibe")
    run(vibe, *WEB_SETS)
    text = (vibe / "CLAUDE.md").read_text()
    head = block("vibe-contract.md").split("\n", 1)[0]
    assert f"{head}<!-- emitted={emitted('vibe-contract.md')} -->\n" in text
    classic = project(tmp_path / "c")
    run(classic, *WEB_SETS)
    assert "gstack-vibe" not in (classic / "CLAUDE.md").read_text()


def test_a_vibe_run_twice_changes_nothing(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    run(proj, *WEB_SETS)
    once = (proj / "CLAUDE.md").read_bytes()
    p = run(proj, *WEB_SETS)
    assert (proj / "CLAUDE.md").read_bytes() == once
    assert last_json(p)["changes"] == [], p.stdout


def test_switching_to_classic_removes_the_vibe_contract_and_reports_it(tmp_path):
    proj = project(tmp_path, claude_md="# P\n\n## P — notes\n\nkeep me\n", workflow="vibe")
    run(proj, *WEB_SETS)
    (proj / ".gstack" / "workflow").write_text("classic\n")
    p = run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    assert "gstack-vibe" not in text and "keep me" in text
    assert any("removed (workflow is classic" in c for c in last_json(p)["changes"]), p.stdout
    assert "\n\n\n" not in text
    once = (proj / "CLAUDE.md").read_bytes()
    p2 = run(proj, *WEB_SETS)
    assert (proj / "CLAUDE.md").read_bytes() == once and last_json(p2)["changes"] == []


def test_a_grown_vibe_contract_is_kept_under_classic_and_the_report_says_why(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    run(proj, *WEB_SETS)
    text = (proj / "CLAUDE.md").read_text()
    head = vibe_heading_line(text)
    own = "\n".join(f"- project rule {i}: keep branch {i} green before landing" for i in range(30))
    grown = text.replace(head, head + "\n" + own, 1)
    (proj / "CLAUDE.md").write_text(grown)
    (proj / ".gstack" / "workflow").write_text("classic\n")
    p = run(proj, *WEB_SETS)
    assert (proj / "CLAUDE.md").read_text() == grown
    assert "has grown past its block" in p.stdout


def test_an_unmarked_vibe_contract_heading_is_the_projects_own_under_classic(tmp_path):
    own = "# P\n\n## Vibe contract notes\n\nour own words\n"
    proj = project(tmp_path, claude_md=own)
    run(proj, *WEB_SETS)
    assert "## Vibe contract notes\n\nour own words" in (proj / "CLAUDE.md").read_text()


def test_the_vibe_contract_names_the_gates_it_overrides_and_stays_short():
    b = block("vibe-contract.md")
    assert b.count("\n") < 30
    for gate in ("superpowers:brainstorming", "superpowers:writing-plans",
                 "superpowers:finishing-a-development-branch", "/superpowers-gstack:vibe"):
        assert gate in b, gate
```

I `test_fresh_project_gets_the_header_and_every_universal_block` (linje 90), etter `assert "gstack-xcode-tools" not in text …`:

```python
    assert "gstack-vibe" not in text, "the vibe contract is opt-in"
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_adapt_script.py -q -k "vibe"`
Expected: FAIL — `FileNotFoundError: .../blocks/vibe-contract.md`.

- [ ] **Step 3: Skriv blokken**

`skills/adapt/blocks/vibe-contract.md` (avsluttende linjeskift; ingen `emitted=`):

```markdown
## Vibe contract (standing approvals; overrides skill gates) <!-- gstack-vibe-v1 -->

This project chose the vibe workflow (`.gstack/workflow`): one intake, then autonomous
completion, then one review by the user. Run `/superpowers-gstack:vibe` for the procedure;
these rules hold whenever a feature is built here.

**Standing approvals after intake.** Once the intake questions are answered, design, spec
and plan are pre-approved. This overrides the HARD-GATE in `superpowers:brainstorming`, the
execution-method choice in `superpowers:writing-plans` (use subagent-driven) and the options
menu in `superpowers:finishing-a-development-branch` (land by the `Landing mode:` line).
Never ask "what next" between phases.

**Stop only for:** irreversible or destructive actions, security-sensitive actions, side
effects outside the worktree, a push to a remote, money, a licence, or a real blocker.
Decide everything else and log it: `Ruling: <choice> — <why> — <cost if wrong>`.

**The one checkpoint is the acceptance tests.** The user reads the test overview once.
After their ok the tests are locked: never edit a locked test to turn red into green, by
any tool; if a test is wrong, stop and say which and why. The lock's `verify` must pass
before landing.

**Context.** Keep the main thread under about 150k tokens: one fresh subagent per phase,
`STATUS.md` updated at every phase boundary.

**Review once, at the end.** The multi-lens chain runs once per feature, after the last
phase, at its computed tier — not at every phase boundary. Fix critical and important
findings; do not re-review minor ones.
```

- [ ] **Step 4: Implementer profilfilteret**

`Block` får et felt til, etter `tracks`:

```python
    profiles: frozenset | None = None   # None: every workflow profile
```

Siste element i `BLOCKS`, etter `companion-skills`:

```python
    Block("vibe-contract.md", "gstack-vibe", r"Vibe contract",
          ("Standing approvals after intake", "/superpowers-gstack:vibe"), profiles=frozenset({"vibe"})),
```

Ny funksjon rett før `apply_block`:

```python
def _remove_out_of_profile(lines: list[str], found, bt: BlockText, ctx: Context, report: Report) -> list[str]:
    """A profile block in a project whose workflow no longer wants it. The emitted
    section is plugin prose and goes, the way the retired autonomy block went; a
    section without a marker is the project's own and stays; one that has grown
    stays too, with a note — the user's lines in it are never removed."""
    start, level, raw_head, version = found
    head_name = heading_text(raw_head)
    if version is None:
        report.preserved.append(f"{head_name}: no marker — the project's own section; kept although the "
                                f"workflow is {ctx.profile}")
        return lines
    end = section_end(lines, start, level)
    g = growth(lines, start, end, bt)
    if g["triggers"]:
        report.notes.append(f"`{head_name}` belongs to another workflow profile and this project's is "
                            f"{ctx.profile}, but it has grown past its block ({g['lines']} lines against "
                            f"{g['block_lines']}); not removed — move your own lines into an unmarked "
                            f"section, then re-run")
        return lines
    report.changes.append(f"{head_name}: removed (workflow is {ctx.profile}; the snapshot has it)")
    if g["at_risk"]:
        report.removed.append({"section": head_name, "lines": g["at_risk"],
                               "where": f"removed with the section — the workflow is {ctx.profile}; "
                                        f"the snapshot has every line"})
    lines = _splice(lines, start, end, [])
    while len(lines) > start > 0 and not lines[start].strip() and not lines[start - 1].strip():
        del lines[start]
    return lines
```

I `apply_block`, erstatt linjen `wanted = blk.tracks is None or ctx.track in blk.tracks` og de to linjene etter `start, level, raw_head, version = found` slik:

```python
    on_track = blk.tracks is None or ctx.track in blk.tracks
    in_profile = blk.profiles is None or ctx.profile in blk.profiles
    wanted = on_track and in_profile
    if found is None:
        if wanted:
            report.changes.append(f"{name}: added ({marker}-v{cur_version})")
            return _append(lines, _emitted_block(raw, ctx, 2))
        return lines
    if not in_profile:
        return _remove_out_of_profile(lines, found, bt, ctx, report)
    start, level, raw_head, version = found
    if not on_track:
        report.notes.append(f"`{heading_text(raw_head)}` is a native-track section and this run's "
                            f"track is {ctx.track} — not on this track, so it is upgraded as usual but never removed; "
                            f"delete it yourself if the project stopped being native")
```

(Notatteksten for spor er den samme som i dag; bare betingelsen er endret fra `not wanted` til `not on_track`.)

`scripts/lint-skills.py`, `MARKER_BLOCKS`: legg til `"vibe-contract.md",` sist i lista.

- [ ] **Step 5: Kjør tester og lint**

Run: `python3 -m pytest tests/unit/test_adapt_script.py tests/unit/test_lint_adapt_and_blocks.py tests/unit/test_own_blocks_sync.py -q && python3 scripts/lint-skills.py`
Expected: alle passerer, lint grønn. `sync-own-claude-md.py` er uendret: vibe-blokken er ikke universell og står ikke i `UNIVERSAL`.

- [ ] **Step 6: Commit**

```bash
git add skills/adapt/blocks/vibe-contract.md scripts/adapt-claude-md.py scripts/lint-skills.py tests/unit/test_adapt_script.py
git commit -m "feat(adapt): gstack-vibe-v1 contract block, emitted only for the vibe profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Prosjektkunnskap som skill

**Files:**
- Create: `skills/adapt/templates/project-context.md`
- Modify: `scripts/adapt-claude-md.py` (konstanter ved `DEFAULT_BLOCKS`; nye `slug`, `main_checkout_name`, `context_skill`, `render_context_skill`; `main`), `skills/adapt/blocks/vibe-contract.md` (én linje), `skills/adapt/blocks/PLACEHOLDERS.md`
- Test: `tests/unit/test_adapt_script.py`

**Interfaces:**
- Consumes: `Context.profile`, `ctx.sets`, `ctx.project`.
- Produces: `slug(name: str) -> str`; `main_checkout_name(project: Path) -> str`; `context_skill(project: Path, explicit: str | None) -> tuple[str, bool]` (navn, finnes); plassholderen `{{CONTEXT_SKILL}}`, som skriptet setter selv; fila `.claude/skills/<navn>/SKILL.md`.

- [ ] **Step 1: Skriv de feilende testene**

```python
# --- 3.6.0: the project's context skill ---------------------------------------------

def context_file(proj: Path, name: str) -> Path:
    return proj / ".claude" / "skills" / name / "SKILL.md"


def test_a_vibe_project_gets_a_context_skill_from_the_template(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    p = run(proj, *WEB_SETS)
    f = context_file(proj, "proj-context")
    text = f.read_text()
    assert re.search(r"^name: proj-context$", text, re.M)
    desc = re.search(r"^description: (.+)$", text, re.M).group(1)
    assert len(desc.split()) < 40
    assert "{{" not in text and "## How we work" in text
    assert "proj-context" in (proj / "CLAUDE.md").read_text(), "the vibe block points to it"
    assert any("created .claude/skills/proj-context/SKILL.md" in c for c in last_json(p)["changes"])


def test_an_existing_context_skill_is_reused_and_never_overwritten(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    f = context_file(proj, "proj-kontekst")
    f.parent.mkdir(parents=True)
    f.write_text("---\nname: proj-kontekst\ndescription: ours\n---\n\nmine\n")
    run(proj, *WEB_SETS)
    assert f.read_text() == "---\nname: proj-kontekst\ndescription: ours\n---\n\nmine\n"
    assert not context_file(proj, "proj-context").exists()
    assert "`proj-kontekst`" in (proj / "CLAUDE.md").read_text()


def test_a_classic_project_gets_no_context_skill(tmp_path):
    proj = project(tmp_path)
    run(proj, *WEB_SETS)
    assert not (proj / ".claude").exists()


def test_dry_run_only_says_it_would_create_the_context_skill(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    p = run(proj, "--dry-run", *WEB_SETS)
    assert not (proj / ".claude").exists()
    assert "would create .claude/skills/proj-context/SKILL.md" in p.stdout


def test_a_second_vibe_run_creates_nothing(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    run(proj, *WEB_SETS)
    p = run(proj, *WEB_SETS)
    assert last_json(p)["changes"] == []


def test_the_project_name_flag_names_the_context_skill(tmp_path):
    proj = project(tmp_path, workflow="vibe")
    run(proj, *WEB_SETS, "--project-name", "My App")
    assert context_file(proj, "my-app-context").is_file()


def test_a_worktree_names_the_context_skill_after_the_main_checkout(tmp_path):
    main = tmp_path / "myapp"
    main.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e.com"], ["config", "user.name", "T"],
                 ["config", "commit.gpgsign", "false"], ["commit", "-q", "--allow-empty", "-m", "init"],
                 ["worktree", "add", "-q", str(tmp_path / "wt-feature"), "-b", "feature"]):
        subprocess.run(["git", *args], cwd=main, check=True)
    wt = tmp_path / "wt-feature"
    (wt / ".gstack").mkdir()
    (wt / ".gstack" / "workflow").write_text("vibe\n")
    run(wt, *WEB_SETS)
    assert context_file(wt, "myapp-context").is_file()


def test_slug():
    m = module()
    assert m.slug("Video-Grading-Worker") == "video-grading-worker"
    assert m.slug("  My  App!! ") == "my-app"
    assert m.slug("???") == "project"
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_adapt_script.py -q -k "context_skill or slug"`
Expected: FAIL — ingen kontekst-skill opprettes; `slug` finnes ikke.

- [ ] **Step 3: Skriv malen**

`skills/adapt/templates/project-context.md`:

```markdown
---
name: {{CONTEXT_SKILL}}
description: Project knowledge for {{PROJECT}} — architecture, domain truths, pitfalls, findings, how to run and test, and the working rules. Load before planning or changing {{PROJECT}}.
---

# {{PROJECT}} — project knowledge

Loaded on demand, not on every turn. CLAUDE.md keeps the rules every session needs;
this skill keeps what a feature needs. Write facts with a reference (`file:line`, a
commit, a measurement), not opinions, and delete what is no longer true.

## What the product is

<!-- One paragraph: who uses it, for what, and what "good" looks like to them. -->

## Architecture

<!-- The parts, how data flows between them, and where each lives (paths). -->

## Domain truths

<!-- Facts about the domain the code relies on and a newcomer would get wrong. -->

## Pitfalls

<!-- What has bitten before: the symptom, the cause, the fix, with a reference. -->

## Findings

<!-- Measurements and experiments worth keeping: what was tried, the number, where it is recorded. -->

## Running and testing

<!-- The exact commands: build, run, the fast tests, the full suite, the end-to-end check. -->

## How we work

<!-- At most three rules per feature, written at the end of /superpowers-gstack:vibe from
ROUNDS.md: a mistake that came back in two phases or more becomes one rule here. -->

## Keeping this skill current

- Update it in the same commit as the change that made it stale.
- Keep the description under 40 words: it is read on every turn to decide whether to load this skill.
```

- [ ] **Step 4: Implementer i skriptet**

Ved `DEFAULT_BLOCKS`:

```python
CONTEXT_TEMPLATE = REPO / "skills" / "adapt" / "templates" / "project-context.md"
CONTEXT_SKILL_RE = re.compile(r"-(context|kontekst)$")
```

Rett etter `project_name`:

```python
def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "project"


def main_checkout_name(project: Path) -> str:
    """The main checkout's directory name, so a worktree (`wt-feature`) names the
    context skill after the project, not after the branch."""
    p = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       cwd=project, capture_output=True, text=True)
    common = Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    if common is not None and common.name == ".git":
        return common.parent.name
    return project.name


def context_skill(project: Path, explicit: str | None) -> tuple[str, bool]:
    """(name, exists). An existing `.claude/skills/*-context` or `*-kontekst` skill
    always wins: the project may have written one before it chose this profile."""
    d = project / ".claude" / "skills"
    if d.is_dir():
        found = sorted(x.name for x in d.iterdir()
                       if CONTEXT_SKILL_RE.search(x.name) and (x / "SKILL.md").is_file())
        if found:
            return found[0], True
    return slug(explicit or main_checkout_name(project)) + "-context", False


def render_context_skill(name: str, project_display: str) -> str:
    if not CONTEXT_TEMPLATE.is_file():
        raise Refusal(f"UNREADABLE: {CONTEXT_TEMPLATE} is missing — run `/plugin update superpowers-gstack`")
    return CONTEXT_TEMPLATE.read_text(encoding="utf-8").replace(
        "{{CONTEXT_SKILL}}", name).replace("{{PROJECT}}", project_display)
```

I `main`, rett etter `ctx = Context(...)` og før `new_text, report = merge(text, ctx)` (blokken trenger `CONTEXT_SKILL` når den emitteres, og alle avvisninger må komme før første skriving):

```python
        ctx_skill, ctx_skill_exists, content, skill_file = None, True, None, None
        if profile == "vibe":
            ctx_skill, ctx_skill_exists = context_skill(project, a.project_name)
            ctx.sets["CONTEXT_SKILL"] = ctx_skill
            skill_file = project / ".claude" / "skills" / ctx_skill / "SKILL.md"
            if not ctx_skill_exists:
                if skill_file.parent.exists() and not skill_file.parent.is_dir():
                    raise Refusal(f"BLOCKED — {skill_file.parent} is a file; the context skill needs that directory")
                content = render_context_skill(ctx_skill, ctx.project)   # a missing template refuses here
```

Rett etter blokken `if not changed: report.changes = []`:

```python
        if content is not None:
            if a.dry_run:
                report.changes.append(f"would create .claude/skills/{ctx_skill}/SKILL.md from the project-context template")
            else:
                skill_file.parent.mkdir(parents=True, exist_ok=True)
                skill_file.write_text(content, encoding="utf-8")
                report.changes.append(f"created .claude/skills/{ctx_skill}/SKILL.md from the project-context "
                                      f"template — fill it in as the project is learned")
```


- [ ] **Step 5: Pekeren i blokken og plassholderregelen**

`skills/adapt/blocks/vibe-contract.md`, ny avsnitt rett før «**Context.**»:

```markdown
**Project knowledge** lives in the skill `{{CONTEXT_SKILL}}` (`.claude/skills/{{CONTEXT_SKILL}}/SKILL.md`),
not in this file: load it before planning; working rules go in its "How we work" section.
```

`skills/adapt/blocks/PLACEHOLDERS.md`, ny seksjon sist:

```markdown
## `{{CONTEXT_SKILL}}` (vibe-contract.md — vibe profile only)

The name of the project's context skill. The one token the script resolves itself —
never pass it with `--set`: an existing `.claude/skills/*-context` or `*-kontekst`
skill, else `<--project-name or the main checkout's directory name, lower-case,
non-alphanumerics as hyphens>-context`, which the script then creates from
`skills/adapt/templates/project-context.md` (never over an existing file).
```

- [ ] **Step 6: Kjør tester og lint**

Run: `python3 -m pytest tests/unit/test_adapt_script.py tests/unit/test_lint_adapt_and_blocks.py -q && python3 scripts/lint-skills.py`
Expected: alle passerer; blokken er fortsatt under 30 linjer; E12 finner regelen for `{{CONTEXT_SKILL}}`.

- [ ] **Step 7: Commit**

```bash
git add skills/adapt/templates/project-context.md skills/adapt/blocks/vibe-contract.md skills/adapt/blocks/PLACEHOLDERS.md scripts/adapt-claude-md.py tests/unit/test_adapt_script.py
git commit -m "feat(adapt): vibe projects get a context skill from a template, named in the contract block

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Profilspørsmålet i `/adapt`

**Files:**
- Modify: `skills/adapt/SKILL.md` (steg 4: nytt punkt 5 etter «Skill routing draft»; steg 5: gap-analysen; steg 7: neste steg)
- Test: `tests/unit/test_vibe_skill.py`

**Interfaces:**
- Consumes: pinfila `.gstack/workflow` (oppgave 1), skillen `vibe` (oppgave 3), kontekst-skillen (oppgave 5).

- [ ] **Step 1: Skriv de feilende testene**

Nederst i `tests/unit/test_vibe_skill.py`:

```python
ADAPT = (REPO / "skills" / "adapt" / "SKILL.md").read_text()


def test_adapt_asks_for_the_profile_once_and_pins_it_committably():
    assert "**Workflow profile.**" in ADAPT
    assert "If `.gstack/workflow` exists the script reads and validates it; do not re-ask." in ADAPT
    assert "printf '%s\\n' \"$PROFILE\" > .gstack/workflow" in ADAPT
    assert "git add -f .gstack/workflow" in ADAPT


def test_adapt_defaults_to_classic_with_nobody_to_answer():
    assert "nobody to answer" in ADAPT and "writes no `.gstack/workflow`" in ADAPT


def test_adapt_lists_contradictions_with_the_vibe_contract():
    assert "contradicts the vibe contract" in ADAPT


def test_adapt_points_a_vibe_project_at_the_vibe_skill():
    assert "/superpowers-gstack:vibe" in ADAPT
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_vibe_skill.py -q -k adapt`
Expected: FAIL — `**Workflow profile.**` finnes ikke.

- [ ] **Step 3: Skriv tekstene**

`skills/adapt/SKILL.md`, steg 4, nytt punkt 5 etter punkt 4 («Skill routing draft»), før `### Step 5`:

````markdown
5. **Workflow profile.** If `.gstack/workflow` exists the script reads and validates it; do not re-ask. If it does not exist, ask **once** with `AskUserQuestion`:

   > How should this project work?
   >
   > - **Vibe** (recommended) — one intake round, then the feature is finished autonomously and you review it once. Your one checkpoint on the way is the acceptance tests, which are then locked. Adds the `Vibe contract` section and a project context skill.
   > - **Classic** — the skills' own approval gates (design, plan, execution method, landing menu), as before.

   Write the pin and keep it committable:

   ```bash
   mkdir -p .gstack && printf '%s\n' "$PROFILE" > .gstack/workflow   # vibe or classic
   if git check-ignore -q .gstack/workflow 2>/dev/null; then
     grep -q '^!\.gstack/workflow$' .gitignore 2>/dev/null \
       || echo '!.gstack/workflow' >> .gitignore
     git add .gitignore && git add -f .gstack/workflow
   else
     git add .gstack/workflow
   fi
   ```

   A run with nobody to answer writes no `.gstack/workflow`: the script then uses
   classic and says so in its notes. With `vibe` the script also creates
   `.claude/skills/<project>-context/SKILL.md` from a template when no `*-context` or
   `*-kontekst` skill exists, and never overwrites one.
````

Steg 5, punkt 1 i gap-analysen: etter `("never use subagents", "don't use TDD")` legg til setningen:

```markdown
   With the vibe profile, also list every rule that contradicts the vibe contract ("write a PRD before any code", "ask before each phase") and let the user choose which one stands.
```

Steg 7, ny første linje i «Next steps»:

```markdown
> - Vibe profile? → `/superpowers-gstack:vibe <what to build>` — and fill in the context skill as you learn the project
```

- [ ] **Step 4: Kjør tester og lint**

Run: `python3 -m pytest tests/unit/test_vibe_skill.py tests/unit/test_lint_adapt_and_blocks.py -q && python3 scripts/lint-skills.py`
Expected: alle passerer; E13 er fortsatt grønn (ingen håndkirurgi lagt til).

- [ ] **Step 5: Commit**

```bash
git add skills/adapt/SKILL.md tests/unit/test_vibe_skill.py
git commit -m "feat(adapt): ask once for the workflow profile and pin it in .gstack/workflow

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `workflow_metrics` — lesing, `tokens`, `asks`, `overhead`

**Files:**
- Create: `scripts/workflow_metrics/__init__.py` (tom), `scripts/workflow_metrics/lib.py`, `scripts/workflow_metrics/tokens.py`, `scripts/workflow_metrics/asks.py`, `scripts/workflow_metrics/overhead.py`, `scripts/workflow-metrics.py`
- Test: `tests/unit/test_workflow_metrics.py`

**Interfaces:**
- Produces: `lib.Scope(root: str, project: str | None, since: float | None, until: float | None)`; `lib.sessions(scope, include_sub=True)` → `(label, dirname, path, is_sub)`; `lib.events`, `lib.ts`, `lib.msg_id`, `lib.api_calls`, `lib.blocks`, `lib.text_of`, `lib.is_human`, `lib.project_label(dirname) -> str`, `lib.parse_date(s) -> float`; hver målemodul har `report(scope: lib.Scope) -> str` (Markdown). CLI: `workflow-metrics.py <command> [--root] [--project] [--since] [--until] [--out]`, exit 0 / 2.
- Kilde: brukerens egne analyseskript (`{lib,tokens,asks,overhead}.py`, 2026-10-02). Logikken flyttes uendret; endringene er listet under, og utskriften er på engelsk.

- [ ] **Step 1: Skriv de feilende testene**

`tests/unit/test_workflow_metrics.py`:

```python
"""scripts/workflow-metrics.py — before/after measurement of a workflow change.

Claude Code writes one transcript event per content block (thinking, text, each tool
call), every one carrying the same `usage`. Counting events instead of `message.id`
inflated token and turn counts 2–3x in the 2026-10-02 analysis. The fixture below
repeats a message id on purpose.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "workflow-metrics.py"
sys.path.insert(0, str(REPO / "scripts"))
from workflow_metrics import lib  # noqa: E402

USAGE = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 100, "output_tokens": 50}
ASK_ANSWER = ('User has answered your questions: "Which store?"="SQLite (Recommended)". '
              'You can now continue with the user\'s answers in mind.')


def human(t, text):
    return {"type": "user", "timestamp": t, "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}


def assistant(t, mid, content, usage=USAGE):
    return {"type": "assistant", "timestamp": t, "message": {"id": mid, "role": "assistant", "content": content, "usage": usage}}


def write(path: Path, events: list, broken_line: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e) for e in events]
    if broken_line:
        lines.insert(2, '{"type": "assistant", "message": {"id": "trunc')
    path.write_text("\n".join(lines) + "\n")


def fixture(root: Path) -> Path:
    d = root / "-Users-ann-Developer-demo"
    write(d / "s1.jsonl", [
        human("2026-10-01T10:00:00Z", "build the importer"),
        assistant("2026-10-01T10:00:05Z", "m1", [{"type": "thinking", "thinking": "…"}]),
        assistant("2026-10-01T10:00:05Z", "m1", [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion",
                                                   "input": {"questions": [{"question": "Which store?", "header": "Store",
                                                                            "options": [{"label": "SQLite (Recommended)"}, {"label": "JSON"}]}]}}]),
        {"type": "user", "timestamp": "2026-10-01T10:01:00Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": ASK_ANSWER}]}},
        assistant("2026-10-01T10:01:05Z", "m2", [{"type": "text", "text": "Done. Shall I land it?"}],
                  usage={**USAGE, "cache_read_input_tokens": 2000}),
        human("2026-10-01T10:02:00Z", "ja"),
    ], broken_line=True)
    write(d / "s1" / "subagents" / "agent-a.jsonl", [
        {"type": "user", "timestamp": "2026-10-01T10:00:30Z", "message": {"role": "user", "content": "phase 1"}},
        assistant("2026-10-01T10:00:40Z", "m3", [{"type": "text", "text": "ok"}]),
    ])
    write(root / "-Users-ann-Developer-other" / "s2.jsonl", [
        human("2026-09-01T09:00:00Z", "old work"),
        assistant("2026-09-01T09:00:05Z", "m9", [{"type": "text", "text": "done"}]),
    ])
    return root


def cli(root: Path, *args: str, expect: int = 0):
    p = subprocess.run([sys.executable, str(CLI), *args, "--root", str(root)], capture_output=True, text=True)
    assert p.returncode == expect, p.stderr
    assert "Traceback" not in p.stderr
    return p.stdout


def test_api_calls_are_one_per_message_id_and_broken_lines_are_skipped(tmp_path):
    root = fixture(tmp_path)
    calls = list(lib.api_calls(str(root / "-Users-ann-Developer-demo" / "s1.jsonl")))
    assert [o["message"]["id"] for o, u, C in calls] == ["m1", "m2"]
    assert calls[0][2] == 1110


def test_project_label_strips_the_home_prefix_and_worktree_suffix():
    assert lib.project_label("-Users-ann-Developer-swiftui-app") == "swiftui-app"
    assert lib.project_label("-Users-ann-Developer-swiftui-app--claude-worktrees-radid") == "swiftui-app"


def test_tokens_counts_model_calls_not_events(tmp_path):
    out = cli(fixture(tmp_path), "tokens")
    assert "Total: 4 model calls" in out          # m1, m2, m3, m9 — not 5 events
    assert "| demo | 2 / 1 |" in out


def test_the_date_filter_keeps_only_sessions_that_start_in_range(tmp_path):
    out = cli(fixture(tmp_path), "tokens", "--since", "2026-09-15")
    assert "Total: 3 model calls" in out and "| other |" not in out


def test_the_project_filter_is_a_substring_of_the_directory(tmp_path):
    out = cli(fixture(tmp_path), "tokens", "--project", "other")
    assert "Total: 1 model calls" in out


def test_asks_recognises_the_recommended_answer_and_short_approvals(tmp_path):
    out = cli(fixture(tmp_path), "asks")
    assert "Total: 1 questions, 100% answered with the recommended option." in out
    assert "Total: 3 messages from you; 33% are short approvals" in out


def test_overhead_reports_the_first_call_baseline(tmp_path):
    out = cli(fixture(tmp_path), "overhead")
    assert "main: 3 model calls" in out and "subagent: 1 model calls" in out


def test_a_missing_root_is_exit_two(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(tmp_path / "nope")],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "UNREADABLE" in p.stderr


def test_a_bad_date_is_a_usage_error(tmp_path):
    p = subprocess.run([sys.executable, str(CLI), "tokens", "--root", str(fixture(tmp_path)), "--since", "last week"],
                       capture_output=True, text=True)
    assert p.returncode == 2 and "USAGE ERROR" in p.stderr
```

Utregning av forventede tall: hovedsesjonene `s1` (m1, m2) og `s2` (m9) gir tre kall, subagenten (m3) ett; m1 har to hendelser og telles én gang. Brukermeldinger: «build the importer», «ja», «old work» = 3; én kort godkjenning («ja») = 33 %.

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'workflow_metrics'`.

- [ ] **Step 3: `lib.py`**

`scripts/workflow_metrics/__init__.py`: én linje, `"""Transcript measurements for /superpowers-gstack:workflow-metrics."""`.

`scripts/workflow_metrics/lib.py`:

```python
"""Shared transcript readers. Standard library only.

Claude Code writes one event per content block, each with the same `usage`: every
token and turn count deduplicates on `message.id` (api_calls). tool_use blocks have
unique ids and are counted as they come.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
from dataclasses import dataclass

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
WORKTREE_SUFFIX = re.compile(r"(--claude-worktrees-|-\.worktrees-|--worktrees-).*$")


@dataclass(frozen=True)
class Scope:
    root: str = DEFAULT_ROOT
    project: str | None = None   # substring of the transcript directory name
    since: float | None = None   # epoch seconds, inclusive
    until: float | None = None   # epoch seconds, exclusive


def parse_date(s: str) -> float:
    """`2026-10-02` or `2026-10-02T22:34`; a date without a zone is local time."""
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.astimezone()
    return d.timestamp()


def project_label(dirname: str) -> str:
    """`-Users-ann-Developer-swiftui-app--claude-worktrees-x` -> `swiftui-app`."""
    s = WORKTREE_SUFFIX.sub("", dirname)
    s = re.sub(r"^-Users-[^-]+-", "", s)
    s = re.sub(r"^(Developer|Projects|projects|src|code|repos)-", "", s)
    return s or dirname


def events(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(o, dict):
                yield o


def ts(o):
    try:
        return dt.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")).timestamp()
    except (KeyError, AttributeError, ValueError):
        return None


def first_ts(path):
    for o in events(path):
        t = ts(o)
        if t is not None:
            return t
    return None


def sessions(scope: Scope, include_sub: bool = True):
    """(label, dirname, path, is_sub) for every transcript file in scope. The date
    filter uses each file's first timestamp."""
    for d in sorted(os.listdir(scope.root)):
        p = os.path.join(scope.root, d)
        if not os.path.isdir(p) or (scope.project and scope.project not in d):
            continue
        for f in sorted(glob.glob(os.path.join(p, "**", "*.jsonl"), recursive=True)):
            is_sub = "/subagents/" in f
            if is_sub and not include_sub:
                continue
            if scope.since is not None or scope.until is not None:
                t = first_ts(f)
                if t is None or (scope.since is not None and t < scope.since) \
                        or (scope.until is not None and t >= scope.until):
                    continue
            yield project_label(d), d, f, is_sub


def msg_id(o):
    return (o.get("message") or {}).get("id")


def api_calls(path):
    """(event, usage, total context) for the first event of each message.id: one per model call."""
    seen = set()
    for o in events(path):
        if o.get("type") != "assistant":
            continue
        i = msg_id(o)
        if i is not None:
            if i in seen:
                continue
            seen.add(i)
        u = (o.get("message") or {}).get("usage") or {}
        C = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        yield o, u, C


def blocks(o):
    c = (o.get("message") or {}).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def text_of(o):
    c = (o.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    return "\n".join(b.get("text", "") for b in blocks(o) if b.get("type") == "text")


def is_human(o):
    """A real user message: not a tool result, a task notification, a peer or meta."""
    if o.get("type") != "user" or o.get("isMeta") or o.get("isCompactSummary"):
        return False
    org = o.get("origin")
    if isinstance(org, dict) and org.get("kind") not in (None, "human"):
        return False
    if any(b.get("type") == "tool_result" for b in blocks(o)):
        return False
    t = text_of(o).strip()
    return bool(t) and not t.startswith(("<task-notification", "<system-reminder", "<local-command"))


def pct(a, b) -> str:
    return f"{a / b:.0%}" if b else "–"
```

- [ ] **Step 4: `tokens.py`, `asks.py`, `overhead.py`**

Flytt `main()` fra hver analysefil til `report(scope: lib.Scope) -> str` med disse endringene, ellers samme logikk:

| I analyseskriptet | I pluginen |
|---|---|
| `import lib` / `lib.sessions()` | `from . import lib` / `lib.sessions(scope)` (og `lib.sessions(scope, include_sub=False)`) |
| `for app, d, f, is_sub in …` | `for label, d, f, is_sub in …`; grupper på `label` |
| `lib.APPS`-rekkefølgen | `sorted(<dict>)` |
| `lib.write_out(...)` og `print(...)` | `return "\n".join(out) + "\n"` |
| `"hoved"` / `"subagent"` | `"main"` / `"subagent"` |
| Filteret `if cr < 1e8: continue` i tokens | fjernes (alle prosjekter i scope vises) |
| Norske overskrifter og totallinjer | engelsk, med eksakt disse totallinjene: |

- tokens: `f"Total: {calls:,} model calls; output {out/1e6:.1f} M; cache_read {cr/1e9:.2f} G; cache_creation {cc/1e6:.0f} M."` (kolonnen «model calls (main / sub)» skrives `f"| {label} | {a['main_calls']:,} / {a['sub_calls']:,} |"` først i hver rad).
- asks: `f"Total: {T} questions, {lib.pct(R, T)} answered with the recommended option."` og `f"Total: {H} messages from you; {lib.pct(A, H)} are short approvals; {lib.pct(AAQ, AQ)} of the replies right after a question are."`
- overhead: per type `f"{kind}: {t['calls']:,} model calls, {t['ctx']/1e9:.2f} billion context tokens reused; the baseline alone {t['base']/1e9:.2f} billion ({t['base']/t['ctx']:.0%})."` og per terskel `f"- {kind}: {..:.0%} of calls happen above {th//1000}k; context above {th//1000}k is {..:.0%} of all context tokens."`

`APPROVE`, `ANS`, `THRESH` og all telling kopieres uendret. Tom scope: hver `report` returnerer `"No transcripts in scope.\n"` når ingen fil ble lest (sjekk med en teller før tabellene bygges; `statistics.median` på tom liste skal aldri nås).

- [ ] **Step 5: CLI-en**

`scripts/workflow-metrics.py`:

```python
#!/usr/bin/env python3
"""workflow-metrics — measure what a workflow change did to questions, stops and tokens.

Commands: tokens, asks, overhead (and skills, triggers, mcp, digest from 3.6.0's
second half). Reads Claude Code transcripts (default ~/.claude/projects), which are
deleted after `cleanupPeriodDays` — copy them aside before a long before/after study.

Exit 0 report printed, 2 refused (reason on stderr). Never a traceback.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflow_metrics import asks, lib, overhead, tokens  # noqa: E402

COMMANDS = {"tokens": tokens.report, "asks": asks.report, "overhead": overhead.report}


def scope_from(a) -> lib.Scope:
    try:
        since = lib.parse_date(a.since) if a.since else None
        until = lib.parse_date(a.until) if a.until else None
    except ValueError as exc:
        raise SystemExit(f"USAGE ERROR: --since/--until must be ISO dates like 2026-10-02 ({exc})")
    root = os.path.expanduser(a.root)
    if not os.path.isdir(root):
        raise SystemExit(f"UNREADABLE: {root} is not a directory")
    return lib.Scope(root=root, project=a.project, since=since, until=until)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--root", default=lib.DEFAULT_ROOT)
    ap.add_argument("--project", help="substring of the transcript directory name")
    ap.add_argument("--since", help="sessions starting on or after this ISO date/time (local time)")
    ap.add_argument("--until", help="sessions starting before this ISO date/time (local time)")
    ap.add_argument("--out", help="also write the report to this file")
    a = ap.parse_args(argv)
    try:
        scope = scope_from(a)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    text = COMMANDS[a.command](scope)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`chmod +x scripts/workflow-metrics.py`.

- [ ] **Step 6: Kjør testene og se dem passere**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py -q`
Expected: alle passerer.

- [ ] **Step 7: Commit**

```bash
git add scripts/workflow_metrics scripts/workflow-metrics.py tests/unit/test_workflow_metrics.py
git commit -m "feat(scripts): workflow-metrics — tokens, asks and overhead, deduplicated on message.id

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `workflow_metrics` — `skills`, `triggers`, `mcp`, `digest`

**Files:**
- Create: `scripts/workflow_metrics/skills.py`, `triggers.py`, `mcp.py`, `digest.py`
- Modify: `scripts/workflow-metrics.py` (`COMMANDS`, `--session` og `--top`)
- Test: `tests/unit/test_workflow_metrics.py`

**Interfaces:**
- Consumes: `lib` fra oppgave 7.
- Produces: `skills.report(scope)`, `triggers.report(scope)`, `mcp.report(scope, claude_json: str = "~/.claude.json")`, `digest.report(scope, session: str | None, top: int | None)`.

- [ ] **Step 1: Skriv de feilende testene**

```python
def fixture_more(root: Path) -> Path:
    fixture(root)
    d = root / "-Users-ann-Developer-demo"
    write(d / "s3.jsonl", [
        {"type": "attachment", "timestamp": "2026-10-02T08:00:00Z",
         "attachment": {"type": "skill_listing", "content": "- superpowers:brainstorming: Use before building\n- unused-skill: Never called"}},
        human("2026-10-02T08:00:01Z", "test it"),
        assistant("2026-10-02T08:00:05Z", "m4", [{"type": "tool_use", "id": "s1", "name": "Skill", "input": {"skill": "superpowers:brainstorming"}}]),
        assistant("2026-10-02T08:00:06Z", "m5", [{"type": "tool_use", "id": "b1", "name": "Bash", "input": {"command": "swift test --filter Foo"}}]),
        {"type": "user", "timestamp": "2026-10-02T08:02:06Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "b1", "content": "ok"}]}},
        assistant("2026-10-02T08:02:10Z", "m6", [{"type": "tool_use", "id": "x1", "name": "mcp__XcodeBuildMCP__build_sim", "input": {}}]),
    ])
    return root


def test_skills_lists_used_and_never_used_skills(tmp_path):
    out = cli(fixture_more(tmp_path), "skills")
    assert "Never used: 1 of 2" in out and "unused-skill" in out


def test_triggers_counts_build_and_test_commands(tmp_path):
    out = cli(fixture_more(tmp_path), "triggers")
    assert "| demo | swift test | 1 |" in out


def test_mcp_counts_calls_per_server_without_reading_secrets(tmp_path):
    cj = tmp_path / "claude.json"
    cj.write_text(json.dumps({"mcpServers": {"XcodeBuildMCP": {"env": {"TOKEN": "secret"}}, "idle": {}}}))
    out = cli(fixture_more(tmp_path / "root"), "mcp", "--claude-json", str(cj))
    assert "| XcodeBuildMCP | 1 | demo (1) |" in out and "| idle | 0 | – |" in out
    assert "secret" not in out


def test_digest_of_one_session(tmp_path):
    root = fixture_more(tmp_path)
    out = cli(root, "digest", "--session", str(root / "-Users-ann-Developer-demo" / "s1.jsonl"))
    assert "Which store?" in out and "SQLite (Recommended)" in out
```

- [ ] **Step 2: Kjør testene og se dem feile**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py -q -k "skills or triggers or mcp or digest"`
Expected: FAIL — `invalid choice: 'skills'`.

- [ ] **Step 3: Flytt de fire analysene**

Fra brukerens analyseskript `{skills,triggers,mcp_per_project,digest}.py`, med samme endringer som i oppgave 7 (`lib.sessions(scope)`, `label` i stedet for app, engelsk, `return` i stedet for `write_out`), og i tillegg:

- **skills.py:** `listing()` leser `skill_listing` fra den nyeste hovedsesjonen i scope, ikke fra en fast prosjektmappe:
  ```python
  def listing(scope):
      files = [f for _, _, f, sub in lib.sessions(scope, include_sub=False)]
      for f in sorted(files, key=os.path.getmtime, reverse=True):
          for o in lib.events(f):
              a = o.get("attachment") if o.get("type") == "attachment" else None
              if a and a.get("type") == "skill_listing":
                  items = {}
                  for ln in a["content"].split("\n- "):
                      ln = ln.lstrip("- ").strip()
                      if ": " in ln:
                          n, desc = ln.split(": ", 1)
                          items[n.strip()] = desc.strip()
                  return items
      return {}
  ```
  `history.jsonl` leses fra `~/.claude/history.jsonl` bare når `scope.root` er `lib.DEFAULT_ROOT` (en kopi av transkriptene har ingen tilhørende historikk). Totallinjen: `f"**Never used: {len(zero)} of {len(rows)}** (≈ {…:,} tokens of descriptions)."`
- **triggers.py:** `CMD`, `kind`, `mentions` uendret. Tabellen per prosjekt og kommando viser alle rader (fjern `if sum(v) > 600`), radformat `f"| {label} | {k} | {len(v)} | {sum(v)/3600:.1f} | {sum(v)/len(v):.0f} | {sum(1 for x in v if x > 300)} |"`.
- **mcp.py:** `report(scope, claude_json="~/.claude.json")` leser bare nøklene i `mcpServers` (aldri verdiene). Fjern «Forslag per app»-seksjonen og «Mekanisme»-teksten (de var personlige råd); behold tabellen og «Never used»-linja. Radformat `f"| {n} | {allused[p]} | {', '.join(apps) or '–'} |"` med `apps = [f"{a} ({used[a][p]})" for a in sorted(used) if used[a][p]]`.
- **digest.py:** `report(scope, session=None, top=None)`: med `top` returneres lista over de lengste hovedsesjonene per prosjekt; med `session` returneres utdraget som tekst (ikke fil). Telling av modellsvar dedupliseres på `message.id` som før.

CLI-en: legg til `skills`, `triggers`, `mcp`, `digest` i `COMMANDS`, flaggene `--claude-json` (standard `~/.claude.json`), `--session` og `--top` (int), og send dem videre:

```python
    if a.command == "mcp":
        text = mcp.report(scope, a.claude_json)
    elif a.command == "digest":
        if not a.session and a.top is None:
            print("USAGE ERROR: digest needs --session <file.jsonl> or --top N", file=sys.stderr)
            return 2
        text = digest.report(scope, a.session, a.top)
    else:
        text = COMMANDS[a.command](scope)
```

- [ ] **Step 4: Kjør testene og se dem passere**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py -q`
Expected: alle passerer.

- [ ] **Step 5: Commit**

```bash
git add scripts/workflow_metrics scripts/workflow-metrics.py tests/unit/test_workflow_metrics.py
git commit -m "feat(scripts): workflow-metrics — skills, triggers, mcp and digest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Skillen `workflow-metrics` og samsvar med analysen fra 2026-10-02

**Files:**
- Create: `skills/workflow-metrics/SKILL.md`
- Modify: `CLAUDE.md`, `README.md` (antall `seventeen`), `skills/adapt/roster.md`, `skills/adapt/model-routing.md`
- Test: `tests/unit/test_workflow_metrics.py`

**Interfaces:**
- Consumes: CLI-en fra oppgave 7–8.

- [ ] **Step 1: Skriv den feilende testen**

```python
def test_the_skill_names_the_cli_and_the_cleanup_period():
    s = (REPO / "skills" / "workflow-metrics" / "SKILL.md").read_text()
    assert "$SKILL_DIR/../../scripts/workflow-metrics.py" in s
    assert "cleanupPeriodDays" in s and "--since" in s and "--until" in s
```

- [ ] **Step 2: Kjør testen og se den feile**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py -q -k skill_names`
Expected: FAIL — `FileNotFoundError`.

- [ ] **Step 3: Skriv skillen**

`skills/workflow-metrics/SKILL.md`:

````markdown
---
name: workflow-metrics
description: Measure a workflow change before and after — questions and recommended answers, stops, tokens, long contexts, skill and MCP use — from Claude Code transcripts, deduplicated per model call.
---

# Workflow metrics

Invoke with: `/superpowers-gstack:workflow-metrics [project] [change date]`

```bash
SKILL_DIR='<the base directory the Skill tool printed when this skill loaded>'
WM="$SKILL_DIR/../../scripts/workflow-metrics.py"
[ -f "$WM" ] || WM=$(ls ~/.claude/plugins/cache/*/superpowers-gstack/*/scripts/workflow-metrics.py 2>/dev/null | sort -V | tail -1)
```

## Before and after

Pick the change's date and time (a commit, the moment a contract went into CLAUDE.md),
then run each measurement twice with the same `--project`:

```bash
python3 "$WM" asks   --project <dir substring> --until <change>
python3 "$WM" asks   --project <dir substring> --since <change>
python3 "$WM" tokens --project <dir substring> --since <change>
```

| Command | Answers |
|---|---|
| `asks` | How many structured questions, how many answered with the recommended option, how long Claude works between your messages |
| `tokens` | Model calls (main / subagent), output, context reused and written, per project |
| `overhead` | How much context is baseline, and how much is spent above 150k / 200k / 300k / 500k |
| `triggers` | Which builds and test runs happened, how long they took, who asked for them |
| `skills` | Which skills are listed every turn and which were never used |
| `mcp` | MCP calls per server and project (server names only, never their settings) |
| `digest --session <file>` / `digest --top N` | A compressed timeline of one session, or the longest sessions |

Every count is one per model call: transcripts write one event per content block, and
counting events inflates the numbers two to three times.

Report the before/after pair as a small table and say what moved. Fewer than about ten
sessions on either side is an anecdote; say so.

**Transcripts are deleted** after `cleanupPeriodDays` (30 by default) in
`~/.claude/settings.json`. For a study longer than that, raise it or copy
`~/.claude/projects` aside and pass `--root <copy>`.
````

- [ ] **Step 4: Ruting og dokumentasjon**

`CLAUDE.md`, etter vibe-linjen fra oppgave 3:

```markdown
- "Did the workflow change help?", count questions / stops / tokens, measure before and after → invoke /superpowers-gstack:workflow-metrics. Runs `scripts/workflow-metrics.py` (asks, tokens, overhead, triggers, skills, mcp, digest) over Claude Code transcripts, one count per model call (`message.id`), with `--project`, `--since`, `--until`.
```

`skills/adapt/roster.md`, etter vibe-raden:

```markdown
| `/superpowers-gstack:workflow-metrics` | Any project changing how it works with Claude (a contract, a profile, a skill) — before/after counts of questions, stops and tokens from the transcripts. |
```

`skills/adapt/model-routing.md`, etter vibe-raden:

```markdown
| `/superpowers-gstack:workflow-metrics`       | haiku     |
```

`README.md`: `with sixteen skills:` → `with seventeen skills:`, og etter `/vibe`-punktet:

```markdown
  - `/workflow-metrics` — before/after measurement of a workflow change from Claude Code transcripts: questions and recommended answers, stops, tokens, long contexts, builds, skill and MCP use, one count per model call. `scripts/workflow-metrics.py`, standard library only.
```

- [ ] **Step 5: Samsvar med analysen fra 2026-10-02 (akseptkriterium 6)**

Kjør begge mot arkivkopien (samme data):

```bash
python3 scripts/workflow-metrics.py tokens --root <archive> | grep '^Total'
python3 scripts/workflow-metrics.py asks --root <archive> | grep '^\*\*Total\|^Total'
python3 <analysis>/tokens.py | grep '^Totalt'
python3 <analysis>/asks.py | grep 'Totalt'
```

Expected: samme antall modellkall, output, cache_read og cache_creation (tokens), og samme antall spørsmål, andel anbefalt og antall brukermeldinger (asks). Analyseskriptene skriver om rapportene sine i `analysis/out/` med de samme tallene; det er ufarlig. Avviker et tall: finn årsaken før du går videre, og skriv den i commit-meldingen.

- [ ] **Step 6: Kjør tester og lint**

Run: `python3 -m pytest tests/unit/test_workflow_metrics.py tests/unit/test_spec_drift_skill.py -q && python3 scripts/lint-skills.py`
Expected: alle passerer; lint `0 error(s), 0 warning(s) across 17 skills`.

- [ ] **Step 7: Commit**

```bash
git add skills/workflow-metrics CLAUDE.md README.md skills/adapt/roster.md skills/adapt/model-routing.md tests/unit/test_workflow_metrics.py
git commit -m "feat(workflow-metrics): before/after measurement skill; numbers match the 2026-10-02 analysis

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Release 3.6.0

**Files:**
- Modify: `.claude-plugin/plugin.json` (`"version": "3.6.0"`), `CHANGELOG.md` (ny `## [3.6.0] - <dato>` øverst), `docs/superpowers/specs/2026-10-03-vibe-profil-design.md` (avvikene)

- [ ] **Step 1: Versjon og CHANGELOG**

`.claude-plugin/plugin.json`: `"version": "3.6.0"`.

`CHANGELOG.md`, rett under `# Changelog`:

```markdown
## [3.6.0] - 2026-10-03

**The vibe profile: a project can choose, once, to be built with one intake round, locked acceptance tests as the only checkpoint and one review at the end.** Opt-in per project with `.gstack/workflow`; without it everything is as in 3.5.1.

### Added
- **Workflow profile pin `.gstack/workflow`** (`vibe` | `classic`). `/adapt` asks once and commits it, like `.gstack/e2e-executor`; no file is classic, and a run with nobody to ask never opts in. An invalid value is `BLOCKED — invalid .gstack/workflow`.
- **`gstack-vibe-v1` block** (`blocks/vibe-contract.md`, under 30 lines), emitted only for `vibe`: standing approvals after intake that override the brainstorming HARD-GATE, the execution-method choice and the finishing menu; the stop list; the acceptance tests as the one checkpoint; context under about 150k with a fresh subagent per phase; the multi-lens chain once per feature. Switching to `classic` removes the emitted block (a grown one stays, with a note). `Block` gained a `profiles` filter beside `tracks`.
- **`/superpowers-gstack:vibe`** — one feature from intake to landing: one `AskUserQuestion` round, `SPEC.md`/`PLAN.md` under `docs/superpowers/vibe/`, acceptance tests shown once with a `/goal` line, then locked; `STATUS.md`/`ROUNDS.md`; one review; landing by `Landing mode:`; lessons into the context skill.
- **`scripts/lock-acceptance-tests.py`** — `lock` commits the tests, adds `Edit(/<glob>)`/`Write(/<glob>)` deny rules to the project's `.claude/settings.json` and a receipt in `.gstack/acceptance-lock.json`; `verify` (exit 0/1/2) is the real gate, since a deny rule does not stop Bash; `unlock` removes only the rules no other lock needs.
- **Project context skill.** With `vibe`, `/adapt` creates `.claude/skills/<project>-context/SKILL.md` from `skills/adapt/templates/project-context.md` unless a `*-context` or `*-kontekst` skill exists; the vibe block names it through the script-resolved `{{CONTEXT_SKILL}}`.
- **`/superpowers-gstack:workflow-metrics`** and `scripts/workflow-metrics.py` (`asks`, `tokens`, `overhead`, `triggers`, `skills`, `mcp`, `digest`; `--project`, `--since`, `--until`): before/after measurement from transcripts, one count per model call (`message.id`). Same totals as the 2026-10-02 analysis on the same data.

### Tests
- `test_adapt_script.py`: the pin (missing, vibe, invalid values), the block emitted / not emitted / removed / kept when grown / idempotent, the context skill (created, reused, never overwritten, dry run, worktree naming, `--project-name`).
- `test_lock_acceptance_tests.py`: lock, verify (clean, unstaged, staged, committed, deleted, from a subdirectory), invalid settings, bad globs, unrelated staged work, unlock with shared rules.
- `test_vibe_skill.py`, `test_workflow_metrics.py` (a fixture with a repeated `message.id` and a truncated line).
```

- [ ] **Step 2: Rett specen**

I `docs/superpowers/specs/2026-10-03-vibe-profil-design.md`:
- 4.4, første punkt: erstatt «committer settings og kvittering i samme commit» med «committer settings og kvittering i en egen commit rett etter (kvitteringen inneholder SHA-en til test-committen); kvitteringen holder én lås per feature (`{"locks": [...]}`)».
- 4.5, andre punkt: erstatt «og skriver én pekerlinje i prosjektets egen (umarkerte) seksjon» med «og vibe-blokken peker til den gjennom `{{CONTEXT_SKILL}}` (skriptet skriver aldri i umarkerte seksjoner). Standardnavn `<prosjekt>-context`; en eksisterende `*-context` eller `*-kontekst` brukes».
- 4.3, steg 1: legg til «Skillen går ikke selv inn i plan-modus (å forlate den spør brukeren én gang til); intaket er skrivebeskyttet for kode.»

- [ ] **Step 3: Full verifisering**

Run: `python3 scripts/lint-skills.py && python3 scripts/sync-own-claude-md.py --check && python3 -m pytest tests/unit -q`
Expected: lint `0 error(s), 0 warning(s) across 17 skills`; `own-blocks: up to date`; pytest viser bare den kjente `test_pin_matches_installed_gstack_when_present` som rød (se Global Constraints), alt annet grønt.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md docs/superpowers/specs/2026-10-03-vibe-profil-design.md
git commit -m "chore(release): 3.6.0 — the vibe profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Deretter: `/superpowers-gstack:pitfall-verification` på hele grenen (tier high-stakes: kontrakter og en blokk som overstyrer porter). Ingen push og ingen landing før brukeren sier ja.
