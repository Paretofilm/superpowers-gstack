import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_tlr():
    """Load scripts/third-lens-review.py (hyphenated → not import-able normally)."""
    path = REPO_ROOT / "scripts" / "third-lens-review.py"
    spec = importlib.util.spec_from_file_location("third_lens_review", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tlr = load_tlr()


def test_module_loads_and_has_default_prompt():
    assert tlr.DEFAULT_PROMPT
    assert callable(tlr.main)


import pytest


def test_sensitive_flag_is_removed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tlr", "--sensitive", "--files", "x"])
    with pytest.raises(SystemExit) as e:
        tlr.main()
    assert e.value.code == 2  # argparse rejects unknown flag


def test_sensitive_role_is_removed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tlr", "--role", "sensitive"])
    with pytest.raises(SystemExit) as e:
        tlr.main()
    assert e.value.code == 2  # invalid choice


def test_western_prefixes_gone():
    assert not hasattr(tlr, "WESTERN_PREFIXES")


def test_resolve_transport_openrouter_roles():
    assert tlr.resolve_transport("architecture", None) == ("openrouter", "z-ai/glm-5.2")
    assert tlr.resolve_transport("correctness", None) == ("openrouter", "deepseek/deepseek-v4-pro")


def test_resolve_transport_cli_role():
    assert tlr.resolve_transport("countersynthesis", None) == ("cli", "codex")


def test_model_override_forces_openrouter():
    assert tlr.resolve_transport("countersynthesis", "anthropic/claude-3.5") == \
        ("openrouter", "anthropic/claude-3.5")


def test_run_openrouter_prints_framing(monkeypatch, capsys):
    fake_resp = {
        "choices": [{"message": {"content": "P2 finding here"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.01},
    }
    monkeypatch.setattr(tlr, "http_json", lambda *a, **k: fake_resp)
    monkeypatch.setattr(tlr, "get_pricing", lambda *a, **k: (1e-6, 2e-6))
    monkeypatch.setattr(tlr, "get_credits", lambda *a, **k: 4.47)

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = False
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.2", Args(), "fakekey")
    out = capsys.readouterr().out
    assert "===== THIRD-LENS RAW OUTPUT (z-ai/glm-5.2) =====" in out
    assert "P2 finding here" in out
    assert "END RAW OUTPUT" in out


import subprocess


class _CodexArgs:
    dry_run = False
    max_tokens = 16000
    effort = "medium"


def test_run_codex_invokes_exec_and_prints(monkeypatch, capsys):
    captured = {}

    def fake_run(cmd, input=None, **kwargs):  # **kwargs: encoding/errors/start_new_session/etc.
        captured["cmd"] = cmd
        captured["input"] = input
        out_path = cmd[cmd.index("-o") + 1]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("P1 codex finding")
        class P:
            returncode = 0
            stderr = ""
            stdout = ""
        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)
    tlr.run_codex("SYS", "USER artifact", "codex", _CodexArgs())
    out = capsys.readouterr().out
    assert captured["cmd"][:2] == ["codex", "exec"]
    assert "--sandbox" in captured["cmd"] and "read-only" in captured["cmd"]
    assert captured["cmd"][-1] == "-"  # prompt comes from stdin, not argv (ARG_MAX safe)
    assert "USER artifact" in captured["input"]  # artifact piped via stdin
    assert "===== THIRD-LENS RAW OUTPUT (codex CLI) =====" in out
    assert "P1 codex finding" in out
    assert "subscription" in out


def test_run_codex_nonzero_exits_4(monkeypatch):
    def fake_run(cmd, input=None, **kwargs):
        class P:
            returncode = 1
            stderr = "boom"
            stdout = ""
        return P()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", _CodexArgs())
    assert e.value.code == 4


def test_run_codex_missing_binary_exits_4(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", _CodexArgs())
    assert e.value.code == 4


def test_run_codex_timeout_exits_4(monkeypatch):
    def fake_run(cmd, input=None, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 600)
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", _CodexArgs())
    assert e.value.code == 4


def test_run_codex_empty_output_exits_4(monkeypatch):
    def fake_run(cmd, input=None, **kwargs):
        out_path = cmd[cmd.index("-o") + 1]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("   \n")  # whitespace-only → treated as empty
        class P:
            returncode = 0
            stderr = ""
            stdout = ""
        return P()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as e:
        tlr.run_codex("SYS", "USER", "codex", _CodexArgs())
    assert e.value.code == 4


def test_main_countersynthesis_never_fetches_openrouter_key(monkeypatch):
    """CONFIRMED P1: the CLI role must never call resolve_key()."""
    monkeypatch.setattr("sys.argv", ["tlr", "--role", "countersynthesis", "--files", "x"])
    monkeypatch.setattr(tlr, "gather_content", lambda args: "some artifact")
    monkeypatch.setattr(tlr, "run_codex", lambda *a, **k: None)

    def boom(*a, **k):
        raise AssertionError("resolve_key() must not be called on the CLI path")
    monkeypatch.setattr(tlr, "resolve_key", boom)
    tlr.main()  # must not raise


def test_main_cli_dry_run_skips_key(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv",
                        ["tlr", "--role", "countersynthesis", "--files", "x", "--dry-run"])
    monkeypatch.setattr(tlr, "gather_content", lambda args: "some artifact")

    def boom(*a, **k):
        raise AssertionError("resolve_key() must not be called on the CLI dry-run path")
    monkeypatch.setattr(tlr, "resolve_key", boom)
    tlr.main()
    assert "codex CLI" in capsys.readouterr().out
