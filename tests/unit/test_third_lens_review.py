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
    assert tlr.resolve_transport("architecture", None) == ("openrouter", "z-ai/glm-5.3")
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
    monkeypatch.setattr(tlr, "model_is_served", lambda *a, **k: True)

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = False
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.3", Args(), "fakekey")
    out = capsys.readouterr().out
    assert "===== THIRD-LENS RAW OUTPUT (z-ai/glm-5.3) =====" in out
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


def test_run_codex_unreadable_output_exits_4(monkeypatch):
    """OSError when run_codex tries to open the output file should exit 4."""
    captured = {}
    _real_open = open  # save before monkeypatching

    def fake_run(cmd, input=None, **kwargs):
        out_path = cmd[cmd.index("-o") + 1]
        captured["out_path"] = out_path
        with _real_open(out_path, "w", encoding="utf-8") as fh:
            fh.write("codex output here")
        class P:
            returncode = 0
            stderr = ""
            stdout = ""
        return P()

    def bad_open(path, mode="r", **kwargs):
        # Raise OSError only when run_codex reads its output file (read mode).
        if captured.get("out_path") and str(path) == captured["out_path"] and "w" not in mode:
            raise OSError("simulated unreadable output file")
        return _real_open(path, mode, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("builtins.open", bad_open)

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


def test_run_openrouter_refuses_unserved_model(monkeypatch):
    """The pinned id is version-locked; a retired pin must fail loudly, not review nothing."""
    monkeypatch.setattr(tlr, "fetch_models", lambda *a, **k: [{"id": "z-ai/glm-5.3"}])
    monkeypatch.setattr(tlr, "http_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call the model")))

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = False
        prompt = None
    with pytest.raises(SystemExit) as e:
        tlr.run_openrouter("SYS", "USER", "z-ai/glm-0.0", Args(), "fakekey")
    assert e.value.code == 5


def test_dry_run_surfaces_a_stale_pin_the_same_way(monkeypatch):
    """--dry-run must not soften a retired pin into 'pricing unavailable'."""
    monkeypatch.setattr(tlr, "fetch_models", lambda *a, **k: [{"id": "z-ai/glm-5.3"}])

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = True
        prompt = None
    with pytest.raises(SystemExit) as e:
        tlr.run_openrouter("SYS", "USER", "z-ai/glm-0.0", Args(), "fakekey")
    assert e.value.code == 5


def test_routing_variants_are_served_by_their_base_id():
    assert tlr.model_is_served("k", "z-ai/glm-5.3:nitro", models=[{"id": "z-ai/glm-5.3"}]) is True
    assert tlr.model_is_served("k", "z-ai/glm-9.9", models=[{"id": "z-ai/glm-5.3"}]) is False


def test_malformed_models_response_is_unknown_not_unserved(monkeypatch):
    for bad in (["x"], {"data": "oops"}, {"data": []}, {"nodata": 1}):
        monkeypatch.setattr(tlr, "http_json", lambda *a, **k: bad)
        assert tlr.fetch_models("k") is None


# --- 3.0.0: /models is fetched once and shared by pricing + the watchdog ---------

@pytest.mark.parametrize("models,expect,why", [
    ([{"id": "z-ai/glm-5.3", "pricing": {"prompt": "0.000001", "completion": "0.000002"}}],
     "Estimated max cost", "pricing found → the cost estimate is printed"),
    (None, "Pricing unavailable", "/models unreachable → say so instead of guessing"),
], ids=["priced", "models-outage"])
def test_run_openrouter_dry_run_reports_pricing_or_its_absence(monkeypatch, capsys, models, expect, why):
    """--dry-run must never reach the chat endpoint, whatever /models returned."""
    monkeypatch.setattr(tlr, "fetch_models", lambda *a, **k: models)
    monkeypatch.setattr(tlr, "http_json",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("dry-run must not call the model")))

    class Args:
        max_tokens = 1000
        effort = "medium"
        dry_run = True
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.3", Args(), "fakekey")
    out = capsys.readouterr().out
    assert "Model: z-ai/glm-5.3" in out
    assert expect in out, why
    # the pure helpers agree with what was printed
    assert (tlr.get_pricing("k", "z-ai/glm-5.3", models) == (1e-6, 2e-6)) is (expect == "Estimated max cost")


def test_model_watchdog_never_blocks_on_a_models_outage(monkeypatch, capsys):
    """A /models fetch failure is a network event, not a stale pin: model_is_served()
    answers None and run_openrouter() proceeds to the review — only a definite
    False (id absent from a list we DID get) is allowed to refuse."""
    # http_json() sys.exit(4)s on any HTTP/network error; fetch_models must turn that
    # into None so neither the pricing lookup nor the watchdog can abort the run.
    monkeypatch.setattr(tlr, "http_json", lambda *a, **k: {"data": [{"id": "x"}]})
    assert tlr.fetch_models("k") == [{"id": "x"}]
    fake_resp = {
        "choices": [{"message": {"content": "reviewed despite outage"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
    }
    calls = []

    def dead_models_live_chat(method, path, *a, **k):
        calls.append((method, path))
        if path == "/models":
            raise SystemExit(4)
        return fake_resp
    monkeypatch.setattr(tlr, "http_json", dead_models_live_chat)
    assert tlr.fetch_models("k") is None
    assert tlr.model_is_served("k", "z-ai/glm-5.3") is None          # fetched itself → outage → None
    assert tlr.model_is_served("k", "z-ai/glm-5.3", [{"id": "z-ai/glm-5.3"}]) is True
    assert tlr.model_is_served("k", "z-ai/glm-5.3", [{"id": "other"}]) is False
    assert tlr.get_pricing("k", "z-ai/glm-5.3") == (None, None)       # fetched itself → outage
    calls.clear()
    monkeypatch.setattr(tlr, "get_credits", lambda *a, **k: 1.0)

    class Args:
        max_tokens = 1000
        effort = "medium"
        dry_run = False
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.3", Args(), "fakekey")
    out = capsys.readouterr().out
    assert "reviewed despite outage" in out
    assert ("POST", "/chat/completions") in calls, "the review must still run when /models is down"



def test_model_list_outage_is_fetched_once_and_fails_open(monkeypatch, capsys):
    """A failed /models fetch returns None; that None must not be mistaken for
    'not supplied' and refetched by pricing and the watchdog (three 30 s waits)."""
    calls = {"n": 0}

    def fake_fetch(key):
        calls["n"] += 1
        return None
    monkeypatch.setattr(tlr, "fetch_models", fake_fetch)
    fake_resp = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}
    monkeypatch.setattr(tlr, "http_json", lambda *a, **k: fake_resp)
    monkeypatch.setattr(tlr, "get_credits", lambda *a, **k: None)

    class Args:
        max_tokens = 16000
        effort = "medium"
        dry_run = False
        prompt = None
    tlr.run_openrouter("SYS", "USER", "z-ai/glm-5.3", Args(), "fakekey")
    assert calls["n"] == 1
    assert "RAW OUTPUT" in capsys.readouterr().out
