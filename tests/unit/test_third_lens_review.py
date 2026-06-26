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
