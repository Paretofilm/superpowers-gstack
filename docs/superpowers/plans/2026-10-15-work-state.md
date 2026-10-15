# Work-state, a gate that carries its own pytest, and a vibe lock fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship release 3.15.0: the `work-state` skill and `scripts/work-state.py` (a measured one-line state after a task, and an installed Release build of `main` for Mac-app projects), a pre-merge gate that no longer depends on the machine's Homebrew `python3` having `pytest`, and the `/vibe` fixes the third house found in Steps 3, 7 and 8.

**Architecture:** One standard-library Python script with two subcommands, `report` (reads, prints one line plus a JSON verdict, changes nothing but a `git fetch`) and `install` (build, verify, atomic swap, stamp; only for `Installable: macos-app`). Skills and one git-hygiene rule call it; nothing is enforced by a hook. The script reuses `land-worktree.py`'s ideas (kernel lock in the git dir, `claude_md_at`-style reading of `origin/main`, numbered exit codes, last-line JSON) by loading that file with `importlib` instead of copying it. The gate fix is a 10-line shell wrapper the `.config/wt.toml` hook calls; CI is untouched.

**Tech Stack:** Python 3.11+ stdlib (`subprocess`, `fcntl`, `ctypes` for `renamex_np`, `json`, `re`), pytest, bash, git, `wt`, Xcode command-line tools (stubbed in tests).

**Spec:** `docs/superpowers/specs/2026-10-11-work-state-design.md` (Norwegian; status draft, reviewed by self-pitfall and the third house on 2026-10-11/12). The vibe and gate items come from the 2026-10-15 conversation: third-house findings 1–4 on `skills/vibe/SKILL.md` (`scratchpad/tlr-manual.txt`, summarised in Task 9) and the two manual `pytest` workarounds needed to land 3.12.0 and 3.13.0.

## Global Constraints

- Standard library only; Python **3.11 or newer** (`tomllib`-class floor, same as `land-worktree.py`). The script must refuse an older interpreter with exit 70 and the message `Python >= 3.11 required`.
- Exit codes are fixed by the spec. `report`: 0 all ✓ or –, 1 something open, 2 not a git repo, 64 bad usage. `install`: 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 64, 70 with the meanings in the spec's table.
- The last stdout line of both subcommands is a JSON object; `report` prints the human line first.
- `report` never changes anything except `git fetch --quiet origin` with a 15 s timeout. It never proposes `git branch -D`, `git push --force`, `sudo`, or killing a process.
- `install` never uses `sudo`, never `kill`, never overrides the project's signing settings, never starts the app again, and leaves the old copy in place until the new one is verified.
- The `Installable:` line is read from `origin/main` (fallback: local `main`), outside fenced code blocks, like `Landing mode:`; two different values mean *conflict*, which reads as undefined.
- Every fixture path in tests contains a space. No test touches the real `/Applications`, the real Finder, or the real Xcode (stubs on `PATH`, `--applications-dir` for tests).
- A new skill needs: README skill list, CLAUDE.md routing line, lint passing, `plugin.json` bump to **3.15.0** and a `## [3.15.0]` CHANGELOG entry (release gate). The git-hygiene block goes v13 → v14 and the repo's own CLAUDE.md is refreshed through `scripts/sync-own-claude-md.py`.
- Commit messages follow the repo style `<type>(<scope>): …` and end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Never `--no-verify`, never `git add -A`, never `git stash`.
- Tests that run the whole suite: use `uv run --python 3.14 --with pytest python -m pytest tests/unit -q` (the Homebrew `pytest` runs Python 3.10 and gives 156 false failures). Until Task 10 lands, the pre-merge hook still needs `PATH=<venv with pytest>/bin:$PATH` in front of `land-worktree.py`.

## Review Focus

The inputs the spec implies but its tests do not name, most likely first. Each has a test in the owning task.

1. **A repository with no `origin`, or an `origin` that is unreachable.** `report` must print `pushed –`/`pushed ?` with the reason and never claim ✓. (Task 2)
2. **`Installable:` written twice with different values, or only inside a fenced block, or only on the branch.** All read as *undefined* and the line says `installerbar: ikke definert, kjør /adapt`. (Task 1)
3. **A branch created seconds ago from `main`** (another session's fresh worktree). It is an ancestor of `origin/main` but has no commit of its own; it must land in `ask`, never in `safe_actions`. (Task 3)
4. **A worktree directory that is clean except for ignored files that are not cache** (a `.env`, a database). It must not be removed. (Task 3)
5. **An `/Applications` copy with spaces or non-ASCII in its name, a stamp whose `app_path` no longer exists, and a running process whose path only *starts with* the app's path.** Matching is by exact path text, never by prefix or regex. (Tasks 4–6)

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/work-state.py` (new) | `report` and `install`; helpers for reading `Installable:`, measuring git state, the lock, the stamp and the result file. One file, like `land-worktree.py`; sectioned with `# ---` banners. |
| `tests/unit/test_work_state.py` (new) | Report tests against temporary repos with a local bare `origin`; install tests against stubs on `PATH`. |
| `tests/unit/work_state_fixtures.py` (new) | Shared builders: `make_repo(tmp_path)`, `add_origin`, `stub_bin(tmp_path, **behaviours)`. Keeps the test file readable. |
| `skills/work-state/SKILL.md` (new) | Finds the script from the skill's own directory, runs `report`, performs `safe_actions`, asks the `ask` items once, interprets `install` codes. |
| `skills/work-state/tests/required-sections.test.sh` (new) | Shell contract test pinning the skill's key sentences, like the other skills. |
| `skills/land/SKILL.md`, `skills/verify-and-land/SKILL.md` (modify) | Call `work-state` after landing; Phase 6 wording and `--quit-path`. |
| `skills/adapt/blocks/git-hygiene.md` (modify) | v13 → v14, one new rule. |
| `scripts/adapt-claude-md.py`, `skills/adapt/SKILL.md` (modify) | `--installable` flag and the one question in Step 4. |
| `scripts/lint-skills.py`, `scripts/sync-own-claude-md.py` (modify) | Stale-marker denylist `v13`; routing coverage for the new skill; sync refreshes the repo's own block. |
| `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json` (modify) | Routing line, skill list, 3.15.0 entry, version. |
| `scripts/pytest-gate.sh` (new), `.config/wt.toml` (modify), `tests/unit/test_pytest_gate.py` (new) | The gate runs pytest with whichever interpreter has it. |
| `skills/vibe/SKILL.md`, `tests/unit/test_vibe_skill.py` (modify) | Steps 3, 7, 8. |

`work-state.py` is loaded by tests with `importlib.util.spec_from_file_location("work_state", SCRIPT)` (the hyphen forbids a normal import), exactly as `test_land_worktree.py` does.

---

### Task 1: `Installable:` line — parse, read from `origin/main`, CLI skeleton (done: cde97f2)

**Files:**
- Create: `scripts/work-state.py`, `tests/unit/work_state_fixtures.py`, `tests/unit/test_work_state.py`

**Interfaces:**
- Produces:
  - `parse_installable(text: str) -> tuple[str, str|None] | None | str`: returns `("macos-app", "<Scheme>")`, `("plugin", None)`, `("command", "<cmd>")`, `("none", None)`; `None` when no valid line exists outside fences; the string `"conflict"` when two different valid lines exist. A line with an unknown kind, `macos-app` without a scheme, or `command` without a command is invalid and ignored (counted as absent).
  - `installable_at(repo: Path, rev: str) -> parsed | None`: reads `CLAUDE.md` at `rev` with the symlink rules of `land-worktree.py`'s `claude_md_at` (loaded with `importlib`, one source of truth), then `parse_installable`.
  - `main(argv) -> int` with subparsers `report` and `install`; unknown usage returns 64; `sys.version_info < (3, 11)` returns 70.
  - `fixtures.make_repo(tmp_path) -> Path` (directory named `my proj`, branch `main`, one commit with a `CLAUDE.md`), `fixtures.add_origin(repo) -> Path` (a bare clone next to it named `origin dir`, remote `origin`, upstream set, fetched).

- [x] **Step 1: Write the failing tests**

```python
# tests/unit/test_work_state.py
import importlib.util, json, os, subprocess, sys
from pathlib import Path
import pytest
from work_state_fixtures import make_repo, add_origin, commit_file

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "work-state.py"

def load():
    spec = importlib.util.spec_from_file_location("work_state", SCRIPT)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ws = load()

@pytest.mark.parametrize("text,want", [
    ("Installable: plugin\n", ("plugin", None)),
    ("Installable: macos-app Sing Replay\n", ("macos-app", "Sing Replay")),
    ("Installable: command ./check.sh --quick\n", ("command", "./check.sh --quick")),
    ("Installable: none\n", ("none", None)),
    ("no line here\n", None),
    ("Installable: macos-app\n", None),             # scheme missing -> invalid -> absent
    ("Installable: command\n", None),
    ("Installable: teleport\n", None),
    ("```\nInstallable: plugin\n```\n", None),       # inside a fence
    ("Installable: plugin\nInstallable: none\n", "conflict"),
    ("Installable: plugin\nInstallable: plugin\n", ("plugin", None)),
])
def test_parse_installable(text, want):
    assert ws.parse_installable(text) == want

def test_the_line_is_read_from_origin_main_not_from_a_branch(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/x"], check=True)
    commit_file(repo, "CLAUDE.md", "Installable: plugin\n")
    assert ws.installable_at(repo, "origin/main") is None    # the branch cannot change it

def test_usage_errors_are_64():
    assert ws.main([]) == 64
    assert ws.main(["frobnicate"]) == 64
```

- [x] **Step 2: Run to verify failure**

Run: `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_work_state.py -q`
Expected: FAIL (`scripts/work-state.py` does not exist).

- [x] **Step 3: Implement**

Create `scripts/work-state.py` with: the docstring (purpose, subcommands, exit codes — copied from the spec tables); `_load_land()` that returns the module `land-worktree.py` loaded from `Path(__file__).with_name("land-worktree.py")` (reuse `claude_md_at`, `Lock`, `primary_worktree`, `worktrees`, `out`, `git`, `sh`, `FENCE` — do not copy them); `INSTALLABLE_RE = re.compile(r"^Installable:[ \t]+(\S+)(?:[ \t]+(.+?))?[ \t]*$")`; fence tracking identical to `parse_mode`; the validity table above; `main` with `argparse` (`report [--repo PATH] [--json-only]`, `install [--repo PATH] [--quit-running | --quit-path APP] [--accept-migration] [--replace-unstamped] [--applications-dir DIR]` where `--applications-dir` is `argparse.SUPPRESS` help). `report`/`install` bodies raise `NotImplementedError` for now (replaced in Tasks 2–6).

```python
def parse_installable(text):
    found, fence = set(), None
    for line in text.splitlines():
        m = land.FENCE.match(line)
        if m:
            mark = m.group(1)
            if fence is None: fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and line.strip() == mark: fence = None
            continue
        if fence is None:
            m = INSTALLABLE_RE.fullmatch(line)
            if not m: continue
            kind, rest = m.group(1), m.group(2)
            if kind in ("plugin", "none") and not rest: found.add((kind, None))
            elif kind in ("macos-app", "command") and rest: found.add((kind, rest))
    if len(found) > 1: return "conflict"
    return found.pop() if found else None
```

`tests/unit/work_state_fixtures.py`: `make_repo` runs `git init -b main`, sets `user.name/email` locally, commits a `CLAUDE.md` containing `# proj\n`; `add_origin` runs `git clone --bare` into `origin dir`, `git remote add origin`, `git fetch`, `git branch --set-upstream-to=origin/main main`; `commit_file(repo, name, text)` writes and commits.

- [x] **Step 4: Run to verify pass**

Run: `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_work_state.py -q`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/work_state_fixtures.py tests/unit/test_work_state.py
git commit -m "feat(work-state): the Installable: line and the command skeleton"
```

---

### Task 2: `report` — the *committed* and *pushed* parts (done: 8995046, a95ad24)

**Files:**
- Modify: `scripts/work-state.py`, `tests/unit/test_work_state.py`

**Interfaces:**
- Consumes: `make_repo`, `add_origin`, `commit_file` (Task 1); `land.primary_worktree`, `land.git`.
- Produces: `measure_committed(repo) -> dict` and `measure_pushed(repo) -> dict`. Both return `{"status": "ok"|"open"|"unknown"|"undefined", "detail": str, "items": list[str]}`. `measure_pushed` also returns `"safe_actions": list[list[str]]` and `"ask": list[str]` (empty lists when none). `fetch_origin(repo) -> str|None` runs `git fetch --quiet origin` with `timeout=15` and returns the error text or `None`.

- [x] **Step 1: Write the failing tests**

```python
def test_committed_is_open_for_a_dirty_tree_and_names_the_files(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "scratch.txt").write_text("x")
    r = ws.measure_committed(repo)
    assert r["status"] == "open" and r["items"] == ["scratch.txt"]

def test_committed_looks_at_the_main_folder_too(tmp_path):
    repo = make_repo(tmp_path); wt = tmp_path / "other wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "feat/y", str(wt)], check=True)
    (repo / "dirty.txt").write_text("x")
    assert ws.measure_committed(wt)["status"] == "open"      # dirty in the primary, seen from the worktree

def test_pushed_ok_when_branch_and_main_match_origin(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    assert ws.measure_pushed(repo)["status"] == "ok"

def test_pushed_open_for_unpushed_commit_with_upstream_offers_git_push(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "feat/z"], check=True)
    commit_file(repo, "a.txt", "a")
    r = ws.measure_pushed(repo)
    assert r["status"] == "open"
    assert ["git", "-C", str(repo), "push"] in r["safe_actions"]

def test_pushed_never_offers_a_force_push(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "feat/z"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--amend", "-m", "rewritten", "--allow-empty"], check=True)
    r = ws.measure_pushed(repo)
    assert r["safe_actions"] == [] and any("force" in a for a in r["ask"])

def test_pushed_without_origin_is_a_dash_not_a_tick(tmp_path):                 # Review Focus 1
    repo = make_repo(tmp_path)
    r = ws.measure_pushed(repo)
    assert r["status"] == "undefined" and "ingen fjern-repo" in r["detail"]

def test_pushed_with_unreachable_origin_is_unknown_with_the_reason(tmp_path):  # Review Focus 1
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", str(tmp_path / "gone")], check=True)
    r = ws.measure_pushed(repo)
    assert r["status"] == "unknown" and r["detail"]
```

- [x] **Step 2: Run to verify failure** — `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_work_state.py -q -k "committed or pushed"` → FAIL (`measure_committed` missing).

- [x] **Step 3: Implement.** `measure_committed`: `git status --porcelain` in the given folder and in `land.primary_worktree(repo)` when different; `items` is the union of paths (relative); `status` `open` when any, else `ok`; detail `"N filer"`. `fetch_origin`: `subprocess.run(["git","-C",repo,"fetch","--quiet","origin"], timeout=15)`; a `TimeoutExpired` or non-zero exit returns the stderr tail. `measure_pushed`: no `origin` remote → `undefined`, detail `"– (ingen fjern-repo)"`; fetch error → `unknown`, detail the error; otherwise current branch: with upstream, `git rev-list --count @{upstream}..HEAD` > 0 → open and, when `origin/<branch>` is an ancestor of HEAD (fast-forward), `safe_actions=[["git","-C",repo,"push"]]`, else `ask=["push of '<branch>' would need force"]`; without upstream, commits no remote ref contains (`git rev-list HEAD --not --remotes`) → open and `ask`. For the main folder: `origin/main..main` > 0 → open, `ask=["main has N commits not landed through land"]` (never in `safe_actions`). Detached `HEAD` on the current folder counts commits with `--not --remotes` the same way.

- [x] **Step 4: Run to verify pass** — same command → PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/test_work_state.py
git commit -m "feat(work-state): report measures committed and pushed"
```

---

### Task 3: `report` — *mapper ryddet* (tidy), `safe_actions` and `ask` (done: 0b6ad30, 09f06a6)

**Files:**
- Modify: `scripts/work-state.py`, `tests/unit/test_work_state.py`

**Interfaces:**
- Consumes: `land.worktrees(repo)` (list of dicts with `path`, `branch`), `measure_*` shape from Task 2.
- Produces: `measure_tidy(repo) -> dict` with the same shape plus `safe_actions` and `ask`. Constants `CACHE_DIRS = (".gstack/", "node_modules/", ".build/", "DerivedData/", "__pycache__/", ".pytest_cache/")` (one constant, per spec). `proven_landed(repo, branch) -> bool`: `merge-base --is-ancestor <branch> origin/main` **and** the branch reflog has at least one entry whose subject starts with `commit`. `in_use(path) -> bool`: `lsof -d cwd -Fn` output compared by path prefix (`os.sep`-terminated, so `/a/b` does not match `/a/bc`).

- [x] **Step 1: Write the failing tests**

```python
def make_landed_branch(repo, name="feat/done"):
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    git("switch", "-q", "-c", name); commit_file(repo, f"{name.replace('/', '_')}.txt", "x")
    git("switch", "-q", "main"); git("merge", "-q", "--ff-only", name); git("push", "-q", "origin", "main")

def test_a_landed_branch_with_a_commit_is_deleted_with_dash_d(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); make_landed_branch(repo)
    r = ws.measure_tidy(repo)
    assert ["git", "-C", str(repo), "branch", "-d", "feat/done"] in r["safe_actions"]

def test_a_branch_made_seconds_ago_from_main_is_not_proven_landed(tmp_path):    # Review Focus 3
    repo = make_repo(tmp_path); add_origin(repo)
    subprocess.run(["git", "-C", str(repo), "branch", "feat/fresh"], check=True)
    r = ws.measure_tidy(repo)
    assert not any("feat/fresh" in " ".join(a) for a in r["safe_actions"])
    assert any("feat/fresh" in a for a in r["ask"])

def test_a_squash_merged_branch_is_asked_about_never_deleted(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("switch", "-q", "-c", "feat/sq"); commit_file(repo, "s.txt", "s"); g("switch", "-q", "main")
    g("merge", "-q", "--squash", "feat/sq"); g("commit", "-q", "-m", "squash"); g("push", "-q", "origin", "main")
    r = ws.measure_tidy(repo)
    assert not any("-D" in a for a in r["safe_actions"])
    assert any("feat/sq" in a for a in r["ask"])

def test_a_clean_landed_worktree_is_removed_but_not_the_one_the_session_stands_in(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt done"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    g("worktree", "add", "-q", "-b", "feat/w", str(wt)); commit_file(wt, "w.txt", "w")
    g("merge", "-q", "--ff-only", "feat/w"); g("push", "-q", "origin", "main")
    assert any(str(wt) in " ".join(a) for a in ws.measure_tidy(repo)["safe_actions"])
    assert not any(str(wt) in " ".join(a) for a in ws.measure_tidy(wt)["safe_actions"])   # standing in it

def test_ignored_non_cache_files_keep_a_worktree_in_ask(tmp_path):              # Review Focus 4
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt env"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    commit_file(repo, ".gitignore", ".env\n"); g("push", "-q", "origin", "main")
    g("worktree", "add", "-q", "-b", "feat/e", str(wt)); commit_file(wt, "e.txt", "e")
    g("merge", "-q", "--ff-only", "feat/e"); g("push", "-q", "origin", "main")
    (wt / ".env").write_text("SECRET=1")
    r = ws.measure_tidy(repo)
    assert not any(str(wt) in " ".join(a) for a in r["safe_actions"]) and any(str(wt) in a for a in r["ask"])

def test_only_cache_content_counts_as_clean(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo); wt = tmp_path / "wt cache"
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True)
    commit_file(repo, ".gitignore", "node_modules/\n"); g("push", "-q", "origin", "main")
    g("worktree", "add", "-q", "-b", "feat/c", str(wt)); commit_file(wt, "c.txt", "c")
    g("merge", "-q", "--ff-only", "feat/c"); g("push", "-q", "origin", "main")
    (wt / "node_modules").mkdir(); (wt / "node_modules" / "x.js").write_text("1")
    assert any(str(wt) in " ".join(a) for a in ws.measure_tidy(repo)["safe_actions"])

def test_a_leftover_sibling_folder_with_other_content_is_asked_about(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    left = tmp_path / "my proj.old"; left.mkdir(); (left / "notes.md").write_text("keep me")
    r = ws.measure_tidy(repo)
    assert any(str(left) in a for a in r["ask"]) and not any(str(left) in " ".join(a) for a in r["safe_actions"])

def test_in_use_matches_whole_path_components_only(monkeypatch):
    monkeypatch.setattr(ws, "_cwds", lambda: ["/a/bc/sub"])
    assert ws.in_use(Path("/a/b")) is False and ws.in_use(Path("/a/bc")) is True
```

- [x] **Step 2: Run to verify failure** — `-k "tidy or landed or squash or cache or leftover or in_use"` → FAIL.

- [x] **Step 3: Implement.** Algorithm for `measure_tidy`:
  1. `primary = land.primary_worktree(repo)`; `here = repo` (resolve `git rev-parse --show-toplevel`).
  2. For every worktree except `primary` and `here`: if `in_use(path)` → `ask` entry `"<path> i bruk"`; elif not `proven_landed(branch)` → `ask` entry naming the branch; elif not `is_clean(path)` → `ask`; else `safe_actions` entry `["wt","-C",primary,"remove",branch]` when `shutil.which("wt")`, otherwise two entries `["git","-C",primary,"worktree","remove",path]` then `["git","-C",primary,"branch","-d",branch]`.
  3. For every local branch not checked out anywhere and not `main`: `proven_landed` → `safe_actions` `["git","-C",primary,"branch","-d",name]`; otherwise `ask` (`"<name> er ikke bevist landet"`).
  4. Siblings: directories `primary.parent / f"{primary.name}.*"` that are not worktrees: only cache content (`all_cache(path)`) → `safe_actions` `["osascript","-e",f'tell application "Finder" to delete POSIX file "{path}"']` (trash, never `rm`); else `ask`.
  5. `is_clean(path)`: `git status --porcelain --ignored` output where every `!!` entry is under a `CACHE_DIRS` prefix and there are no other entries.
  6. `status`: `ok` when `safe_actions` and `ask` are both empty, else `open`. `detail` summarises counts. The line text never says ✓ while either list is non-empty.

  The Python never executes `safe_actions`; the skill (Task 7) does.

- [x] **Step 4: Run to verify pass** → PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/test_work_state.py
git commit -m "feat(work-state): report measures tidy folders and branches, with proof before deletion"
```

---

### Task 4: `report` — *installable* status, the stored result, the line, the JSON and the exit code (done: 0acd5a9, d42d677)

**Files:**
- Modify: `scripts/work-state.py`, `tests/unit/test_work_state.py`

**Interfaces:**
- Consumes: Tasks 1–3 measurements; `installable_at`.
- Produces:
  - `measure_installable(repo) -> dict` with `kind` in `macos-app|plugin|command|none|undefined`, `status` in `ok|stale|open|unknown|undefined|na`, `detail`.
  - `gitdir(repo) -> Path` (`git rev-parse --git-common-dir`, resolved).
  - Stamp file `gitdir/gstack-installed-app.json` with keys `scheme, bundle_id, commit, app_path, version, installed_at`; result file `gitdir/gstack-install-result.json` with `code, reason, commit`.
  - `build_line(parts) -> str` and `report(args) -> int`. The line is `Tilstand: committet <m> · pushet <m> · mapper ryddet <m> · installerbar <m> (<detail>)`, with `<m>` one of `✓`, `✗ (<what is left>)`, `?` (+reason), `–`. Last stdout line is the JSON from the spec (`line, committed, pushed, tidy, installable, safe_actions, ask`).
  - Exit code: 0 all ✓ or –, 1 any ✗ or `?`, 2 not a git repo, 64 bad usage.

- [x] **Step 1: Write the failing tests**

```python
def run_report(repo, *extra):
    p = subprocess.run([sys.executable, str(SCRIPT), "report", "--repo", str(repo), *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip().splitlines()

def test_a_clean_pushed_repo_with_no_line_reports_undefined_and_exit_0_or_1_by_rule(tmp_path):
    repo = make_repo(tmp_path); add_origin(repo)
    code, lines = run_report(repo)
    last = json.loads(lines[-1])
    assert last["installable"]["status"] == "undefined"
    assert "installerbar: ikke definert, kjør /adapt" in last["line"]
    assert lines[0].startswith("Tilstand:")

def test_all_green_is_exit_0_and_a_tick_per_part(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "# p\nInstallable: none\n"); add_origin(repo)
    code, lines = run_report(repo)
    assert code == 0
    assert "committet ✓" in lines[0] and "pushet ✓" in lines[0] and "mapper ryddet ✓" in lines[0]

def test_never_a_tick_when_something_is_left(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: none\n"); add_origin(repo)
    (repo / "x.txt").write_text("x")
    code, lines = run_report(repo)
    assert code == 1 and "committet ✓" not in lines[0] and "committet ✗" in lines[0]

def test_conflicting_installable_lines_read_as_undefined(tmp_path):             # Review Focus 2
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: plugin\nInstallable: none\n"); add_origin(repo)
    assert json.loads(run_report(repo)[1][-1])["installable"]["status"] == "undefined"

def test_not_a_git_repo_is_exit_2(tmp_path):
    (tmp_path / "plain").mkdir()
    assert run_report(tmp_path / "plain")[0] == 2

def test_a_stored_stop_code_is_shown_under_ask_until_a_run_succeeds(tmp_path):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", "Installable: macos-app App\n"); add_origin(repo)
    (ws.gitdir(repo) / "gstack-install-result.json").write_text(json.dumps({"code": 4, "reason": "App is running", "commit": "abc"}))
    ask = json.loads(run_report(repo)[1][-1])["ask"]
    assert any("App is running" in a for a in ask)

def test_plugin_kind_reads_installed_version_when_the_registry_exists(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    commit_file(repo, "CLAUDE.md", "Installable: plugin\n")
    commit_file(repo, ".claude-plugin/plugin.json", '{"name": "demo", "version": "3.15.0"}\n')
    commit_file(repo, "CHANGELOG.md", "# Changelog\n\n## [3.15.0] - 2026-10-20\n")
    add_origin(repo)
    reg = tmp_path / "home" / ".claude" / "plugins"; reg.mkdir(parents=True)
    (reg / "installed_plugins.json").write_text(json.dumps({"plugins": {"demo@m": [{"version": "3.14.0"}]}}))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", f"{stub_bin(tmp_path, claude='exit 0')}:{os.environ['PATH']}")
    assert "3.15.0 på main, du har 3.14.0" in ws.measure_installable(repo)["detail"]
```

- [x] **Step 2: Run to verify failure** → FAIL.

- [x] **Step 3: Implement.**
  - `measure_installable`: read the parsed line at `origin/main` (no remote → local `main`, and the line's `pushet` part already says `–`). By kind:
    - `macos-app`: stamp present, `stamp["commit"] == rev-parse origin/main`, `Path(stamp["app_path"]).is_dir()`, `plutil -extract CFBundleIdentifier raw` equals `stamp["bundle_id"]` → `ok`; stamp for an older commit or missing → `stale` with `safe_actions` `[["python3", __file__, "install", "--repo", repo]]`; a stored result with `code` ≥ 4 adds its reason to `ask`.
    - `plugin`: extract `git archive origin/main` to a temp dir, run `claude plugin validate <dir>` if `claude` is on `PATH` (else status `unknown`, detail `claude ikke funnet`); version from `.claude-plugin/plugin.json`; CHANGELOG heading `## [<version>]` must exist; local `main` pushed (`origin/main..main` empty). Detail adds the installed version from `~/.claude/plugins/installed_plugins.json` (first entry whose key starts with `<name>@`).
    - `command`: `sh -c <cmd>` in the primary folder, `timeout=120`, exit 0 → `ok`, else `open` with the last output line; timeout → `unknown`.
    - `none` → `na` (printed `–`); `None`/`conflict` → `undefined`.
  - `build_line` as specified. `report(args)`: fetch once (`fetch_origin`), measure all four, assemble, print, exit code per the constraint. `--json-only` prints only the JSON object.

- [x] **Step 4: Run to verify pass** — whole `test_work_state.py` → PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/test_work_state.py
git commit -m "feat(work-state): report assembles the line, the JSON and the exit code"
```

---

### Task 5: `install` — preconditions, discovery, the four questions, the lock (done: 89e3ee4, 67dc882)

**Files:**
- Modify: `scripts/work-state.py`, `tests/unit/test_work_state.py`
- Modify: `tests/unit/work_state_fixtures.py`

**Interfaces:**
- Consumes: `installable_at`, `gitdir`, `land.Lock` pattern (a second class `InstallLock` on `gitdir/gstack-install.lock`, same flock semantics, exit 12 when held).
- Produces:
  - `fixtures.stub_bin(tmp_path, **behaviours) -> Path`: writes executable shell stubs for `xcodebuild, codesign, plutil, pgrep, ps, osascript, lsregister, ditto, xcodegen` into `tmp_path/"stub bin"`; each behaviour is a short shell snippet (`xcodebuild="exit 65"`) that replaces the default. Tests prepend that directory to `PATH`. **Default stub contract** (every stub appends its argv to `$STUB_LOG` when set, so tests can assert what was and was not called, e.g. that `sudo`/`kill` never appear):
  - `xcodebuild`: with `-showBuildSettings` prints `    BUILT_PRODUCTS_DIR = $STUB_OUT`, `    FULL_PRODUCT_NAME = Fake App.app`, `    PRODUCT_BUNDLE_IDENTIFIER = com.example.fake`, `    EXECUTABLE_NAME = Fake`; with `build` creates `$STUB_OUT/Fake App.app/Contents/MacOS/Fake` and a `built.txt` containing the current `git rev-parse HEAD` of the repo in `$PWD`.
  - `plutil -extract CFBundleIdentifier raw <app>`: prints the content of `<app>/bundle-id` when that file exists, else `com.example.fake`.
  - `codesign --verify …<app>`: exit 0 unless `<app>/bad-signature` exists (then exit 1).
  - `ditto SRC DST`: `cp -R SRC DST`.
  - `ps -Axo pid=,comm=`: prints the content of `$STUB_PS_FILE` when it exists, else nothing.
  - `osascript`: when the argument contains `to quit`, deletes `$STUB_PS_FILE` (the app "quits"); when it contains `Finder … delete`, moves the file to `$STUB_TRASH`.
  - `lsregister`: located through the hidden test variable `GSTACK_LSREGISTER` (default is the absolute system path from the spec); the stub records its argv.
  - `xcodegen`: records argv, exit 0.
  - `fixtures.stub_bin` returns the directory and sets nothing global; tests pass `STUB_OUT`, `STUB_LOG`, `STUB_PS_FILE`, `STUB_TRASH`, `GSTACK_LSREGISTER` through `env` (a `stub_env(tmp_path)` helper builds them under `tmp_path`).
  - `discover_build(repo, scheme) -> dict` with `built_products_dir, full_product_name, bundle_id, executable_name` read with `xcodebuild -showBuildSettings -configuration Release -destination 'platform=macOS' -scheme <scheme>` (workspace before project; `xcodegen generate` first when `project.yml` is newer than the project); a missing key raises `Stop(64, …)`.
  - `class Stop(Exception)` carrying `code, message, state`; `install(args) -> int` prints `{"status": …, "code": …, "reason": …, "commit": …}` as the last line and writes the result file atomically (`os.replace` of a temp file in the same directory).
  - Exit codes 2, 3, 4, 5, 6, 7, 12 are produced here; 8–11 in Task 6.

- [x] **Step 1: Write the failing tests** (each runs `install` through `subprocess` with the stub `PATH` and `--applications-dir "<tmp>/Applications dir"`):

```python
def run_install(repo, stubs, apps, *extra, env_extra=None):
    env = {**os.environ, **stub_env(apps.parent), "PATH": f"{stubs}:{os.environ['PATH']}", **(env_extra or {})}
    p = subprocess.run([sys.executable, str(SCRIPT), "install", "--repo", str(repo),
                        "--applications-dir", str(apps), *extra], capture_output=True, text=True, env=env)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1])

def app_repo(tmp_path, line="Installable: macos-app Fake App\n"):
    repo = make_repo(tmp_path); commit_file(repo, "CLAUDE.md", line); add_origin(repo)
    return repo

def test_code_2_when_the_line_is_not_macos_app(tmp_path):
    repo = app_repo(tmp_path, "Installable: plugin\n")
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 2

def test_code_3_when_the_main_folder_is_on_another_branch(tmp_path):
    repo = app_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "switch", "-q", "-c", "feat/q"], check=True)
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3

def test_code_3_when_the_main_folder_is_dirty_but_ignored_files_are_fine(tmp_path):
    repo = app_repo(tmp_path); commit_file(repo, ".gitignore", "local.cfg\n")
    (repo / "local.cfg").write_text("x")
    (repo / "tracked.txt").write_text("y"); subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 3
    subprocess.run(["git", "-C", str(repo), "reset", "-q", "tracked.txt"], check=True); (repo / "tracked.txt").unlink()
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] != 3

def test_code_4_when_the_app_runs_and_only_an_exact_path_match_counts(tmp_path):   # Review Focus 5
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    app = apps / "Fake App.app"
    exe = f"{app}/Contents/MacOS/Fake"
    stubs = stub_bin(tmp_path, ps=f'echo "123 {exe}"')
    assert run_install(repo, stubs, apps)[0] == 4
    stubs = stub_bin(tmp_path, ps=f'echo "123 {exe}-helper"')       # prefix is not a match
    assert run_install(repo, stubs, apps)[0] != 4

def test_quit_running_asks_the_app_to_quit_and_never_kills(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path); ps_file = Path(env["STUB_PS_FILE"])
    ps_file.write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, out = run_install(repo, stub_bin(tmp_path), apps, "--quit-running", "--replace-unstamped")
    log = Path(env["STUB_LOG"]).read_text()
    assert code == 0 and "to quit" in log and "kill" not in log and not ps_file.exists()

def test_code_4_again_when_the_app_will_not_quit_within_the_deadline(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    env = stub_env(tmp_path); Path(env["STUB_PS_FILE"]).write_text(f"123 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    stubs = stub_bin(tmp_path, osascript="exit 0")                 # asks, but never quits
    code, _ = run_install(repo, stubs, apps, "--quit-running", env_extra={"GSTACK_QUIT_DEADLINE": "1"})
    assert code == 4 and "kill" not in Path(env["STUB_LOG"]).read_text()

def test_quit_path_only_accepts_instances_inside_that_bundle(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    branch_app = tmp_path / "DerivedData dir" / "Fake App.app"
    env = stub_env(tmp_path)
    Path(env["STUB_PS_FILE"]).write_text(f"1 {branch_app}/Contents/MacOS/Fake\n2 {apps}/Fake App.app/Contents/MacOS/Fake\n")
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--quit-path", str(branch_app))
    assert code == 4                                               # the /Applications copy also runs

def test_code_5_when_the_span_since_the_stamp_has_a_migration_signal(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (ws.gitdir(repo) / "gstack-installed-app.json").write_text(json.dumps(
        {"scheme": "Fake App", "bundle_id": "com.example.fake", "commit": base, "app_path": str(apps / "Fake App.app"),
         "version": "1", "installed_at": "2026-10-01T00:00:00Z"}))
    (apps / "Fake App.app").mkdir()
    commit_file(repo, "Sources/Migrations/0002_add_column.sql", "ALTER TABLE t ADD COLUMN c INT;\n")
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 5
    assert run_install(repo, stub_bin(tmp_path), apps, "--accept-migration")[0] == 0

def test_code_5_when_the_stamped_commit_no_longer_exists_in_history(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir(); (apps / "Fake App.app").mkdir()
    (ws.gitdir(repo) / "gstack-installed-app.json").write_text(json.dumps(
        {"scheme": "Fake App", "bundle_id": "com.example.fake", "commit": "0" * 40, "app_path": str(apps / "Fake App.app"),
         "version": "1", "installed_at": "2026-10-01T00:00:00Z"}))
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 5

def test_code_6_for_an_unstamped_copy_and_replace_unstamped_clears_it(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    assert run_install(repo, stub_bin(tmp_path), apps)[0] == 6
    assert run_install(repo, stub_bin(tmp_path), apps, "--replace-unstamped")[0] == 0

def test_code_7_for_a_copy_with_another_bundle_id_and_no_flag_helps(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    (apps / "Fake App.app" / "bundle-id").write_text("com.other.app")
    for flags in ([], ["--replace-unstamped"], ["--accept-migration"], ["--quit-running"]):
        assert run_install(repo, stub_bin(tmp_path), apps, *flags)[0] == 7
def test_code_12_when_another_install_holds_the_lock(tmp_path):
    repo = app_repo(tmp_path)
    fd = os.open(ws.gitdir(repo) / "gstack-install.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    assert run_install(repo, stub_bin(tmp_path), tmp_path / "Applications dir")[0] == 12
    os.close(fd)

def test_stale_temporary_copies_for_the_same_bundle_id_are_removed_under_the_lock(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    mine = apps / ".Fake App.gstack-new-999"; mine.mkdir()
    other = apps / ".Other.gstack-new-998"; other.mkdir(); (other / "bundle-id").write_text("com.other.app")
    run_install(repo, stub_bin(tmp_path), apps)
    assert not mine.exists() and other.exists()
```

- [x] **Step 2: Run to verify failure** — `-k install` → FAIL.

- [x] **Step 3: Implement** `InstallLock`, `Stop`, `discover_build`, `running_instances(executable_path) -> list[int]` (`ps -Axo pid=,comm=`, exact string equality with `<app>/Contents/MacOS/<EXECUTABLE_NAME>`), `quit_app(bundle_id, deadline=20)` (`osascript -e 'tell application id "<id>" to quit'`, then poll `running_instances` once a second), `migration_signal(repo, stamp_commit)` (runs `scripts/classify-change.py --diff --diff-base <stamp_commit>` against `origin/main` and looks for the `migration` signal in its JSON; an unreachable stamp commit → treated as signal), precondition 1 (`git status --porcelain --untracked-files=no` clean on `main`, then `git pull --ff-only` while holding `land.Lock`'s lock file `gstack-land.lock` for at most 60 s — exit 12 when `land` holds it longer), and the four questions with their flags. Write the result file in a `finally` so a stop is never lost. The build and swap steps are Task 6; `install` returns `Stop(70, "not implemented")` after the questions until then.

- [x] **Step 4: Run to verify pass** → PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/test_work_state.py tests/unit/work_state_fixtures.py
git commit -m "feat(work-state): install preconditions, discovery, the four questions and the lock"
```

---

### Task 6: `install` — build, verify before the swap, atomic swap, register, stamp (done: 7f17bf8, c8dd3dc)

**Files:**
- Modify: `scripts/work-state.py`, `tests/unit/test_work_state.py`

**Interfaces:**
- Consumes: `discover_build`, `Stop`, `InstallLock` (Task 5).
- Produces: `build(repo, info, scheme) -> Path` (`xcodebuild … -derivedDataPath <gitdir>/gstack-install-build build`, log to `gitdir/gstack-install-build.log`, exit 8 with the log path), `verify_copy(tmp_app, bundle_id)` (exit 9: `codesign --verify --deep --strict` then `plutil -extract CFBundleIdentifier raw`; the temp copy is deleted and the old copy untouched), `swap(old, new)` (`renamex_np(RENAME_SWAP)` through `ctypes.CDLL(None).renamex_np(old.encode(), new.encode(), 0x2)`; when no old copy `os.rename`; the old copy goes to the Trash through `osascript` Finder `delete`, falling back to `~/.Trash/<name> <timestamp>`; unwritable applications dir → exit 10), the `HEAD` re-check before the swap (exit 11), `register_and_stamp` (`lsregister -f`, second `codesign --verify` on the final path, atomic stamp write).

- [x] **Step 1: Write the failing tests**

```python
def test_a_successful_install_swaps_stamps_and_a_second_run_is_current(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "installed"
    stamp = json.loads((ws.gitdir(repo) / "gstack-installed-app.json").read_text())
    assert stamp["commit"] == subprocess.run(["git", "-C", str(repo), "rev-parse", "origin/main"], capture_output=True, text=True).stdout.strip()
    assert (apps / "Fake App.app").is_dir()
    code, out = run_install(repo, stub_bin(tmp_path), apps)
    assert code == 0 and out["status"] == "current"

def test_code_8_leaves_the_old_copy_untouched_and_names_the_log(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    marker = apps / "Fake App.app" / "old.txt"; marker.write_text("old")
    code, out = run_install(repo, stub_bin(tmp_path, xcodebuild="exit 65"), apps, "--replace-unstamped")
    assert code == 8 and "gstack-install-build.log" in out["reason"] and marker.read_text() == "old"

def test_code_9_removes_the_temporary_copy_and_keeps_the_old_one(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    (apps / "Fake App.app" / "old.txt").write_text("old")
    stubs = stub_bin(tmp_path, ditto='cp -R "$1" "$2" && touch "$2/bad-signature"')   # the copy fails verification
    code, _ = run_install(repo, stubs, apps, "--replace-unstamped")
    assert code == 9 and (apps / "Fake App.app" / "old.txt").read_text() == "old"
    assert not [p for p in apps.iterdir() if ".gstack-new-" in p.name]
    assert json.loads((ws.gitdir(repo) / "gstack-install-result.json").read_text())["code"] == 9

def test_code_10_when_the_applications_dir_is_not_writable_and_no_sudo_is_attempted(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir(); apps.chmod(0o555)
    try:
        code, _ = run_install(repo, stub_bin(tmp_path), apps)
    finally:
        apps.chmod(0o755)
    assert code == 10 and "sudo" not in Path(stub_env(tmp_path)["STUB_LOG"]).read_text()

def test_code_11_when_main_moves_during_the_build_nothing_is_swapped_or_stamped(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    mover = (f'git -C "{repo}" commit -q --allow-empty -m moved && git -C "{repo}" push -q origin main; '
             'mkdir -p "$STUB_OUT/Fake App.app/Contents/MacOS"; touch "$STUB_OUT/Fake App.app/Contents/MacOS/Fake"')
    code, _ = run_install(repo, stub_bin(tmp_path, xcodebuild=_with_settings(mover)), apps)
    assert code == 11 and not (apps / "Fake App.app").exists()
    assert not (ws.gitdir(repo) / "gstack-installed-app.json").exists()

def test_install_replaces_with_a_swap_and_the_old_copy_ends_in_the_trash(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; (apps / "Fake App.app").mkdir(parents=True)
    (apps / "Fake App.app" / "old.txt").write_text("old")
    env = stub_env(tmp_path)
    code, _ = run_install(repo, stub_bin(tmp_path), apps, "--replace-unstamped")
    assert code == 0 and (apps / "Fake App.app" / "built.txt").is_file() and not (apps / "Fake App.app" / "old.txt").exists()
    assert list(Path(env["STUB_TRASH"]).rglob("old.txt"))          # the old copy went to the trash, not to rm

def test_a_name_with_spaces_and_non_ascii_survives(tmp_path):                  # Review Focus 5
    repo = app_repo(tmp_path, "Installable: macos-app Fake App æøå\n"); apps = tmp_path / "Applications dir ø"; apps.mkdir()
    stubs = stub_bin(tmp_path, xcodebuild=_with_settings(None, product="Fake App æøå.app"))
    code, _ = run_install(repo, stubs, apps)
    assert code == 0 and (apps / "Fake App æøå.app").is_dir()

def test_no_stamp_when_the_final_path_signature_check_fails(tmp_path):
    repo = app_repo(tmp_path); apps = tmp_path / "Applications dir"; apps.mkdir()
    stubs = stub_bin(tmp_path, lsregister='touch "$1/bad-signature"')   # corrupts the final copy after the swap
    code, _ = run_install(repo, stubs, apps)
    assert code == 9 and not (ws.gitdir(repo) / "gstack-installed-app.json").exists()
```

`_with_settings(extra, product="Fake App.app")` is a fixtures helper that wraps a stub body so `-showBuildSettings` prints the four settings (with `product` as `FULL_PRODUCT_NAME`) and every other invocation runs `extra` (or the default build) — tests that change the build behaviour use it so they never re-implement the settings output.

- [x] **Step 2: Run to verify failure** → FAIL.

- [x] **Step 3: Implement** the functions above and wire them after the questions in `install`. Order exactly as the spec: 4 build → 5 copy with `ditto` to `<apps>/.<name>.gstack-new-<pid>` and verify → HEAD re-check → 6 swap → 7 register and stamp. Every failure path removes only the temporary copy it created. `status: "current"` short-circuits before the build when the stamp already matches `origin/main`, the app path exists and the bundle id matches (this is the same predicate `measure_installable` uses — extract it into `stamp_is_current(repo, stamp, head)` and call it from both).

- [x] **Step 4: Run to verify pass** — whole file → PASS.

- [x] **Step 5: Commit**

```bash
git add scripts/work-state.py tests/unit/test_work_state.py
git commit -m "feat(work-state): install builds, verifies, swaps and stamps"
```

---

### Task 7: The `work-state` skill and its routing (done: f372105, 293a04a)

**Files:**
- Create: `skills/work-state/SKILL.md`, `skills/work-state/tests/required-sections.test.sh`
- Modify: `CLAUDE.md` (routing section), `README.md` (skill list), `scripts/lint-skills.py` only if the lint needs the new skill listed (read the routing-coverage rule first)

**Interfaces:**
- Consumes: the CLI of Tasks 2–6.
- Produces: a skill named `work-state` whose frontmatter `description` is at most 30 words; sections `## Run`, `## Read the result`, `## Do what is safe`, `## Ask once`, `## Install codes`, `## Never`. The script is located relative to the skill (`<base>/../../scripts/work-state.py`) with the same interpreter loop as `skills/land/SKILL.md` (Python 3.11+).

- [x] **Step 1: Write the failing contract test** (`required-sections.test.sh`): grep for `## Run`, `## Never`, the sentence `Run \`safe_actions\` as printed`, the sentence `one \`AskUserQuestion\``, `--quit-path`, `never \`git branch -D\``, and the line `The line never says ✓ while something is left`.

```bash
#!/usr/bin/env bash
set -euo pipefail
f="$(dirname "$0")/../SKILL.md"
for s in '## Run' '## Never' 'Run `safe_actions` as printed' 'one `AskUserQuestion`' '--quit-path' 'never `git branch -D`' 'never says ✓ while something is left'; do
  grep -qF -- "$s" "$f" || { echo "work-state SKILL.md lacks: $s" >&2; exit 1; }
done
```

- [x] **Step 2: Run to verify failure** — `bash skills/work-state/tests/required-sections.test.sh` → exits 1 (file missing).

- [x] **Step 3: Write the skill.** Content, in this order: purpose in two sentences; `## Run` (interpreter loop, `report --repo "$PWD"`); `## Read the result` (the last line is JSON; `line` is what ends the message); `## Do what is safe` (run each `safe_actions` entry as printed, from the main folder, one at a time, and re-run `report` once at the end — never loop more than twice); `## Ask once` (collect `ask` plus any stop code from `install` into one `AskUserQuestion` in one message; if the user does not answer, the line stays honest); `## Install codes` (the spec's table, 4/5/6 ask, 7 tell the user to tidy by hand, 8 show the log path, 9–11 report and stop, 12 wait); `## Never` (`git branch -D`, force push, `sudo`, killing a process, passing `--accept-migration`/`--replace-unstamped`/`--quit-running` without the user's yes in this session). Add the routing line to `CLAUDE.md` after the `land` line: `- "Is everything committed", "is it tidy", "is the app installable", "installer appen", "tilstand" → invoke /superpowers-gstack:work-state. …` and a README bullet.

- [x] **Step 4: Run to verify pass** — the shell test passes; `python3 scripts/lint-skills.py` → 0 errors (fix any routing-coverage or cross-reference error it names).

- [x] **Step 5: Commit**

```bash
git add skills/work-state CLAUDE.md README.md scripts/lint-skills.py
git commit -m "feat(work-state): the skill, its contract test and its routing"
```

---

### Task 8: Wire it in — `land`, `verify-and-land`, git-hygiene v14, `adapt --installable`, the repo's own line (done: 1f82fd9, 0a34ecb, 261d500, 9089780)

**Files:**
- Modify: `skills/land/SKILL.md`, `skills/verify-and-land/SKILL.md`, `skills/adapt/blocks/git-hygiene.md`, `scripts/adapt-claude-md.py`, `skills/adapt/SKILL.md`, `scripts/lint-skills.py`, `scripts/sync-own-claude-md.py`, `CLAUDE.md`, `tests/unit/test_adapt_script.py`, `tests/unit/test_lint_adapt_and_blocks.py`, `tests/unit/test_verify_and_land.py`

**Interfaces:**
- Consumes: the CLI (Tasks 2–6) and the skill (Task 7).
- Produces: `--installable <value>` on `adapt-claude-md.py` written once under `## <project> install`, kept on later runs (mirrors `--local-state` and `apply_local_state`); the marker `gstack-git-hygiene-v14`; denylist entry `gstack-git-hygiene-v1[0-3]\b`.

- [x] **Step 1: Write the failing tests**
  - `test_adapt_script.py`: `--installable plugin` on a project without the line adds `Installable: plugin` under a heading the project owns; a second run with `--installable none` keeps `plugin` and reports it as preserved; a value that is empty, multi-line or contains `<!--` is refused (exit 2) before any write; the line inside a fenced block does not count as present.
  - `test_lint_adapt_and_blocks.py`: the denylist catches `gstack-git-hygiene-v13` in a fixture; the shipped block carries `v14`.
  - `test_verify_and_land.py`: Phase 6 text contains `install it in /Applications` (the exact wording the spec gives: «gjør dette til den gjeldende versjonen, og installer den i `/Applications`») and Phase 7 names `--quit-path`.
  - A land-skill test (`skills/land/tests/required-sections.test.sh` extension or a pytest on the file text): code 0 row mentions `/superpowers-gstack:work-state`.

- [x] **Step 2: Run to verify failure** — `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_adapt_script.py tests/unit/test_lint_adapt_and_blocks.py tests/unit/test_verify_and_land.py -q` → FAIL.

- [x] **Step 3: Implement.**
  - `adapt-claude-md.py`: add `installable: str | None` to `Context`, argparse flag `--installable`, validation next to `local_state`'s (single line, no `<!--`, matches `INSTALLABLE_RE` semantics through a copy of the four valid shapes — if importing `work-state.py` is cheaper, load it the same `importlib` way and call `parse_installable("Installable: " + value)`), `apply_installable(lines, ctx, report)` modelled on `apply_local_state`: skip when a valid line already exists outside fences/managed regions (report as preserved), else append `Installable: <value>` under `## <project> install` (create that heading like the `Local state` rescue heading does). Update the module docstring step list.
  - `skills/adapt/SKILL.md` Step 4: one question with a recommendation per the spec's three rules (`.claude-plugin/plugin.json` → `plugin`; track `macos`/`both` and a scheme whose `SUPPORTED_PLATFORMS` contains `macosx` → `macos-app <Scheme>`; else `command`/`none`), answer passed as `--installable`. Not asked in the fresh path (`Assumed:` line gains `Installable: none`).
  - `git-hygiene.md`: marker v14 and the new bullet under *Landing the branch*: `**Before the last message of a task that changed files, run /superpowers-gstack:work-state**, do what its safe_actions say, ask what its ask says once, and end the message with its line. Not for pure questions or conversations without file changes.`
  - `land/SKILL.md` exit-0 row: after the `remaining` cleanup run `/superpowers-gstack:work-state`; when it reports `macos-app` `stale`, start `install` in the background; end the message with the line.
  - `verify-and-land/SKILL.md`: Phase 6 wording; Phase 7 passes `--quit-path <bundle from Phase 5>`; in `pr` mode run `work-state` after `/ship` and say the work waits for a pull request.
  - `lint-skills.py`: widen the stale-marker denylist to `gstack-git-hygiene-v1[0-3]\b`.
  - Run `python3 scripts/sync-own-claude-md.py` so the repo's own `CLAUDE.md` gets block v14, then add the repo's own line under a heading the project owns: `Installable: plugin`.

- [x] **Step 4: Run to verify pass** — the three test files, then `python3 scripts/lint-skills.py` and `bash skills/adapt/tests/required-sections.test.sh` → all pass.

- [x] **Step 5: Commit**

```bash
git add skills/land/SKILL.md skills/verify-and-land/SKILL.md skills/adapt scripts/adapt-claude-md.py scripts/lint-skills.py scripts/sync-own-claude-md.py CLAUDE.md tests/unit
git commit -m "feat(work-state): land, verify-and-land and git-hygiene v14 call it; adapt asks for Installable once"
```

---

### Task 9: `/vibe` — the `/goal` path locks first; Step 7 fallback; Step 8 order (done: baf49fa)

**Files:**
- Modify: `skills/vibe/SKILL.md`, `tests/unit/test_vibe_skill.py`

**Interfaces:**
- Consumes: the existing `LOCK` variable and the Step 3 lock command.
- Produces: three pinned sentences (below).

The third house (DeepSeek `correctness`, 2026-10-15, $0.054) found, in text this release does not otherwise touch, and each was checked against the file before it went into this plan: **(a)** Step 3 hands the user a `/goal` line to paste but only says "after their ok, lock" — pasting `/goal` is an approval that never says `ok`, so the lock can be skipped (`skills/vibe/SKILL.md:117`); **(b)** Step 7 writes into "the context skill" which a project may not have; **(c)** Step 8 says "exit 1 → restore from the lock commit or stop" and later "after a rebase / in pr mode exit 1 → re-lock", which an agent can read as contradictory; **(d)** subagent briefs in Step 4 do not name the locked-test boundary. (d) is **already covered**: Step 4 reads "Two fixed rules go into every brief" and Step 3 forbids editing locked tests; it is therefore *not* changed and is recorded in the CHANGELOG as refuted with that reason.

- [x] **Step 1: Write the failing tests**

```python
def test_a_pasted_goal_counts_as_approval_and_the_lock_runs_first():
    assert "whether they say ok or paste the `/goal` line, run the lock first" in VIBE

def test_step_7_names_the_file_when_no_context_skill_exists():
    assert "If the project has no context skill, create `.claude/skills/<project>-context/SKILL.md`" in VIBE

def test_step_8_handles_rebase_and_pr_receipt_before_the_generic_exit_1():
    i_special = VIBE.index("Re-lock cases first")
    i_generic = VIBE.index("Any other exit 1")
    assert i_special < i_generic
    assert "re-locking after a rebase or a squash-merge receipt change is not editing a test" in VIBE
```

- [x] **Step 2: Run to verify failure** — `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_vibe_skill.py -q` → the three new tests FAIL.

- [x] **Step 3: Edit `skills/vibe/SKILL.md`.**
  - Step 3: replace "`/goal` is started by the user; without it, continue with step 4 when they say ok. After their ok, lock the tests:" with "The user approves in one of two ways: they say ok, or they paste the `/goal` line. Whether they say ok or paste the `/goal` line, run the lock first and only then start Step 4 (a `/goal` the user pastes is started by them; lock before you act on it):".
  - Step 7: append "If the project has no context skill, create `.claude/skills/<project>-context/SKILL.md` with a `## How we work` section holding the rules, and commit it with the feature; never put them in CLAUDE.md."
  - Step 8: restructure to "**Re-lock cases first.** After a rebase `verify` warns that the lock commit left the branch's history; in `pr` mode a squash-merge on main that changed the receipt makes it exit 1 (`receipt changed by commit …`). Both mean the lock must be redone by the user, and re-locking after a rebase or a squash-merge receipt change is not editing a test. Tell the user and ask them to re-lock. **Any other exit 1** names each changed file …: restore it from the lock commit, or stop and say which test is wrong." Keep all other sentences (the limits of `verify`) unchanged.

- [x] **Step 4: Run to verify pass** — `test_vibe_skill.py` PASS; `python3 scripts/lint-skills.py` 0 errors.

- [x] **Step 5: Commit**

```bash
git add skills/vibe/SKILL.md tests/unit/test_vibe_skill.py
git commit -m "fix(vibe): a pasted /goal locks the tests first; Step 7 has a fallback; Step 8 handles re-lock before generic exit 1"
```

---

### Task 10: The gate carries its own pytest (done: 5dad30f)

**Files:**
- Create: `scripts/pytest-gate.sh`, `tests/unit/test_pytest_gate.py`
- Modify: `.config/wt.toml`

**Interfaces:**
- Produces: `scripts/pytest-gate.sh [pytest args…]` — runs `python3 -m pytest "$@"` when `python3 -c 'import pytest, sys; sys.exit(sys.version_info < (3, 11))'` succeeds; otherwise `uv run --python 3.14 --with pytest python -m pytest "$@"` when `uv` exists; otherwise prints `pytest-gate: no interpreter with pytest and Python >= 3.11 (install uv or: python3 -m pip install pytest)` to stderr and exits 70.

- [x] **Step 1: Write the failing test**

```python
import os, subprocess, stat
from pathlib import Path
GATE = Path(__file__).resolve().parents[2] / "scripts" / "pytest-gate.sh"

def fake(tmp_path, name, body):
    d = tmp_path / "bin dir"; d.mkdir(exist_ok=True)
    f = d / name; f.write_text("#!/bin/sh\n" + body); f.chmod(f.stat().st_mode | stat.S_IEXEC); return d

def run(tmp_path, bins, *args):
    env = {"PATH": f"{bins}:/usr/bin:/bin", "HOME": str(tmp_path)}
    return subprocess.run(["bash", str(GATE), *args], capture_output=True, text=True, env=env)

def test_uses_python3_when_it_has_pytest(tmp_path):
    bins = fake(tmp_path, "python3", 'case "$*" in *"import pytest"*) exit 0;; *) echo "py3 $*";; esac')
    assert "py3 -m pytest -q" in run(tmp_path, bins, "-q").stdout

def test_falls_back_to_uv_when_python3_lacks_pytest(tmp_path):
    bins = fake(tmp_path, "python3", 'exit 1')
    fake(tmp_path, "uv", 'echo "uv $*"')
    assert "uv run --python 3.14 --with pytest python -m pytest -q" in run(tmp_path, bins, "-q").stdout

def test_exits_70_with_a_remedy_when_neither_exists(tmp_path):
    bins = fake(tmp_path, "python3", 'exit 1')
    r = run(tmp_path, bins, "-q")
    assert r.returncode == 70 and "install uv" in r.stderr

def test_arguments_with_spaces_survive(tmp_path):
    bins = fake(tmp_path, "python3", 'case "$*" in *"import pytest"*) exit 0;; *) printf "[%s]" "$@";; esac')
    assert "[tests/unit dir]" in run(tmp_path, bins, "tests/unit dir").stdout
```

- [x] **Step 2: Run to verify failure** — `uv run --python 3.14 --with pytest python -m pytest tests/unit/test_pytest_gate.py -q` → FAIL.

- [x] **Step 3: Implement** the script (`#!/usr/bin/env bash`, `set -u`, the three branches above, `exec` the chosen command with `"$@"`) and change `.config/wt.toml` `unit` to `bash scripts/pytest-gate.sh tests/unit -q -p no:cacheprovider --deselect … --deselect …` (the two deselects stay verbatim). CI's `lint.yml` stays as it is.

- [x] **Step 4: Run to verify pass** — the new test file PASS; then **prove the hook end to end without the temporary venv**: `wt hook pre-merge` in this worktree with the default `PATH` (Homebrew `python3` without pytest) must be green. The hook edit must be approved first (`wt config approvals add` needs a real terminal — use the Calyx tab flow, the user answers).

- [x] **Step 5: Commit**

```bash
git add scripts/pytest-gate.sh tests/unit/test_pytest_gate.py .config/wt.toml
git commit -m "fix(gate): the pre-merge hook runs pytest with an interpreter that has it"
```

---

### Task 11: Release, verification, rehearsal, first real run

**Files:**
- Modify: `.claude-plugin/plugin.json` (3.15.0), `CHANGELOG.md` (`## [3.15.0] - <date of landing>`), `README.md`, `docs/superpowers/specs/2026-10-11-work-state-design.md` (status), `docs/superpowers/plans/2026-10-15-work-state.md` (mark tasks done with SHAs, per plan-fidelity)

- [ ] **Step 1: Version and CHANGELOG.** Entry sections: one-line headline; `### Added` (work-state skill and script, `Installable:` line, `adapt --installable`, git-hygiene v14, `scripts/pytest-gate.sh`); `### Fixed` (vibe Steps 3, 7, 8 with the refuted finding (d) and why); `### Changed` (`land`, `verify-and-land`, gate); `### Upgrade` (`/adapt` replaces the git-hygiene block in adapted projects and asks for `Installable:` once); `### Review` (tier, lenses, findings, what was refuted).

- [ ] **Step 2: Local verification.** `python3 scripts/lint-skills.py` green; full unit suite via `uv run --python 3.14 --with pytest python -m pytest tests/unit -q` (expect only the two known deselected-by-design tests to differ; the slow `test_a_transport_that_ignores_TERM…` can time-out under load: rerun it alone); `for t in skills/*/tests/required-sections.test.sh; do bash "$t"; done`.

- [ ] **Step 3: Pitfall verification** (`/superpowers-gstack:pitfall-verification`). Expected floor: high-stakes (a script that swaps files in `/Applications`, size). Self-pitfall round(s) with the `[domain]` pitfalls *shell/infra scripting* and *native desktop*: an unset variable in a destructive path (`${VAR:?}` everywhere a path is built), unquoted paths, `rm`/`mv` on a computed path, exit status swallowed by a pipe, a non-idempotent re-run. Lens 2 (Codex) is off (`codex_reviews=disabled`) — say so; the third house runs with `--role correctness` on `scripts/work-state.py` (file-scoped; the whole diff exceeds the model's budget, use `--effort low --max-tokens 30000` and `--files`). Synthesis is adversarial; fix confirmed findings, re-run Stage 0 on the patched tree.

- [ ] **Step 4: Rehearsal in the spare Mac.** `vm-run --help` first. A tiny SwiftUI app with ad-hoc signing is built and installed twice (first without a stamp, then with); the second run must build only what changed. Check the tools first: `vm-run -- command -v xcodebuild xcodegen codesign lsregister`; the guest has Xcode, not Homebrew tools. Record the result in the CHANGELOG `### Review`. A failing rehearsal blocks landing.

- [ ] **Step 5: Land** with `/superpowers-gstack:land` (the gate now works with the default `PATH`; if it does not, that is Task 10 failing — fix it, do not fall back to the temporary venv). Watch the CI run; red means fixing `main` next. Then `wt remove feat/work-state` after `ExitWorktree keep`.

- [ ] **Step 6: First real run — needs the user.** The user names one of their own Mac-app projects (decision left open by the spec: *"Hvilken app avtales i planen"*). In that project: `/superpowers-gstack:adapt` (adds `Installable: macos-app <Scheme>` after one question), then `/superpowers-gstack:work-state`, with the user present for the app-quit question. Report what the line said and what `install` did. This step is **not** done until it has happened; if it cannot happen this session, say so in the final report and leave it as the single open item.

- [ ] **Step 7: Commit the plan's own status** (tasks marked done with SHAs; spec status → `implementert i 3.15.0`, with a «Avvik fra utkastet» list if anything differed) and push.

---

## Deviations

Rulings made while executing (details in `.superpowers/sdd/2026-10-15-work-state/progress.md`):

- **R1:** Task 4 creates `stub_bin` and `stub_env`; Task 5 only adds the default-stub contract. The Task 4 test needs them before Task 5.
- **R2:** Task 4 implements `stamp_is_current`; Task 6 reuses it. This avoids a refactor in the middle of the plan.
- **R3:** `quit_app` reads its deadline from the hidden `GSTACK_QUIT_DEADLINE` (default 20 s), so the test does not wait 20 s.
- **R4, replaced by R4':** a failed signature check on the final path rolls the swap back and exits 9; the old copy goes to the Trash only after the check passes. R4 (keep the new copy, old one already trashed) was replaced because the Dock must always have a working app.
- **R5:** Task 10's end-to-end proof (`wt hook pre-merge`, which needs `wt config approvals add` in a real terminal) is run by the controller with the user, not by the subagent.
- **R6:** the session's own worktree, when its branch is proven landed, is listed in `ask` (ryddes etter ExitWorktree), never in `safe_actions`: the line may never be a tick while something stands.
- **R7:** cache directory names are recognised at any depth (nested `node_modules` is common).
- **R8:** bundle ids are read with `plistlib`, not `plutil`; ubuntu CI has no `plutil`, and fake apps carry a real `Info.plist`.
- **R9:** `report` exits 0 for undefined, `none` and no remote; the JSON status carries the truth.
- **R10:** `install` keeps the strict `--untracked-files=all` clean check, and `report` shows a stored stop for every non-zero code.
- **R11:** the `install` safe action starts with `sys.executable`, so macOS's Python 3.9 cannot run it; the skill says entries run exactly as printed.

## Self-review

- **Spec coverage:** Part 1 (the line, `/adapt` question, undefined line, read from `origin/main`) → Tasks 1, 4, 8. Part 2 (`report`, every limit, "proven landed", "clean", "in use", honest line) → Tasks 2–4. Part 3 (lock, leftovers, stored result, steps 1–7, code table, failure principle) → Tasks 5–6. Part 4 (`land`, `verify-and-land`, git-hygiene v14, joint questions) → Tasks 7–8. Testing section (report fixtures, install stubs, rehearsal, first real run, adapt test) → Tasks 2–6, 8, 11. Components table rows 1–9 → Tasks 1–8, 11. "Utenfor første versjon" items are not built. The vibe findings → Task 9; the gate → Task 10.
- **Placeholders:** none; the test bodies in Tasks 4–6 are written out, and the stub contract they rely on is stated in Task 5.
- **Types:** `Stop(code, message, state)`, `measure_*` return the same dict shape (`status, detail, items`, plus `safe_actions` and `ask` where the spec has them), `stamp_is_current` is shared by `measure_installable` and `install`, `gitdir()` is the single source of the state-file directory.
- **Risks to watch while executing:** (1) `renamex_np` through `ctypes` is macOS-only and untestable on Linux CI — guard the call with `sys.platform == "darwin"` and test the swap with an injectable `_swap` function so CI covers the rest; (2) `claude plugin validate` may not exist on every machine — handled as status `unknown`; (3) the first real run changes the user's `/Applications`: it needs their presence and an explicit app choice.
