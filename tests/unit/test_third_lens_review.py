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
