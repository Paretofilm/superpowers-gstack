import json
import pytest
from test_smoke import load
pf = load("preflight")


def test_resolve_missing_tool_raises(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: None)
    with pytest.raises(pf.PreflightError) as e:
        pf.resolve_tool("idb")
    assert "idb" in str(e.value)


def test_resolve_present_tool_returns_path(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda n: "/opt/homebrew/bin/idb")
    assert pf.resolve_tool("idb") == "/opt/homebrew/bin/idb"


def _fake_run(launchctl_out, describe_out):
    class R:
        pass

    def run(args, **kw):
        r = R()
        r.stdout = launchctl_out if "launchctl" in args else describe_out
        r.returncode = 0
        return r
    return run


def test_foreground_true_when_running_and_not_home(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "501 0 UIKitApplication:com.x.app[abcd]\n",
        json.dumps([{"type": "Application", "AXUniqueId": None}])))
    assert pf.is_app_foreground("U", "com.x.app") is True


def test_foreground_false_when_on_home(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "501 0 UIKitApplication:com.x.app[abcd]\n",
        json.dumps([{"AXUniqueId": "spotlight-pill"}])))
    assert pf.is_app_foreground("U", "com.x.app") is False


def test_foreground_false_when_process_dead(monkeypatch):
    monkeypatch.setattr(pf.subprocess, "run", _fake_run(
        "", json.dumps([{"type": "Application"}])))
    assert pf.is_app_foreground("U", "com.x.app") is False
