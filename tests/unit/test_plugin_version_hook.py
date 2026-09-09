"""Guard check-plugin-version.sh against nudging toward a version it cannot deliver.

A session keeps the plugin root it resolved at startup, and the cache holds every
version ever installed (nine, at the time of writing, all runnable). So the newest
version on disk is not necessarily the one running.

Keying the nudge on the cache's newest produced advice that could never be satisfied:
it told the user to run /adapt to reach a version their /adapt does not come from, so
/adapt wrote the running version's marker back and the next session nudged again.
"Different" is not "older" — reported by the rig session after observing a session
served 2.51.1 while installed_plugins.json said 2.53.1.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "scripts" / "check-plugin-version.sh"


def fake_plugin_root(d: Path, version: str) -> Path:
    root = d / f"root-{version}"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "superpowers-gstack", "version": version}))
    return root


def run_hook(project: Path, plugin_root: Path | None):
    env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(["bash", str(HOOK)], cwd=project, capture_output=True,
                          text=True, env=env, timeout=30)


def test_no_nudge_when_the_project_matches_the_running_version():
    """The case the bug broke: a session running an older plugin, in a project adapted
    by that same plugin. Nothing is stale — the cache merely holds something newer."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        proj = d / "proj"; proj.mkdir()
        (proj / "CLAUDE.md").write_text("# P\n<!-- superpowers-gstack: 2.51.1 -->\n")
        p = run_hook(proj, fake_plugin_root(d, "2.51.1"))
        assert p.stdout.strip() == "", f"nudged when nothing was stale: {p.stdout!r}"


def test_nudge_when_the_project_really_is_behind_the_running_version():
    """The nudge must still fire when it can actually be satisfied — the running
    plugin's /adapt would write the newer marker."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        proj = d / "proj"; proj.mkdir()
        (proj / "CLAUDE.md").write_text("# P\n<!-- superpowers-gstack: 2.47.0 -->\n")
        p = run_hook(proj, fake_plugin_root(d, "2.53.3"))
        assert "2.47.0" in p.stdout and "2.53.3" in p.stdout, p.stdout
        assert "adapt" in p.stdout


def test_the_hook_prefers_the_running_root_over_the_cache():
    """Both exist; the root must win. Otherwise the advice names a version the user's
    own /adapt cannot produce."""
    text = HOOK.read_text()
    root_use = text.index("CLAUDE_PLUGIN_ROOT")
    cache_use = text.index("plugins/cache")
    assert root_use < cache_use, "the running root must be consulted before the cache"
    assert "not the newest one on disk" in text, "say why, or it reverts on the next edit"
