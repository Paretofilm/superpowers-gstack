import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PKG = REPO_ROOT / "scripts" / "computer_use"


def load(mod_name):
    path = PKG / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(f"computer_use_{mod_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_package_dir_exists():
    assert PKG.is_dir()
