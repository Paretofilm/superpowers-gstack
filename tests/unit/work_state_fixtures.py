"""Fixtures for tests/unit/test_work_state.py. Every path contains a space on purpose."""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path


def run(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def commit_file(repo, name, text, message=None):
    f = Path(repo) / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    run(repo, "add", "--", name)
    run(repo, "commit", "-q", "-m", message or f"edit {name}")


def make_repo(tmp_path) -> Path:
    repo = Path(tmp_path) / "my proj"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    run(repo, "config", "user.name", "Test")
    run(repo, "config", "user.email", "test@example.com")
    run(repo, "config", "commit.gpgsign", "false")
    commit_file(repo, "CLAUDE.md", "# proj\n", "init")
    return repo


def add_origin(repo) -> Path:
    repo = Path(repo)
    origin = repo.parent / "origin dir"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(origin)], check=True)
    run(repo, "remote", "add", "origin", str(origin))
    run(repo, "fetch", "-q", "origin")
    run(repo, "branch", "--set-upstream-to=origin/main", "main")
    return origin


_FAKE_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.example.fake</string>
<key>CFBundleExecutable</key><string>Fake</string>
</dict></plist>"""

def _with_settings(extra=None, product="Fake App.app", settings=None):
    """An xcodebuild stub body. `-showBuildSettings` prints the four settings (`product` as
    FULL_PRODUCT_NAME, BUILT_PRODUCTS_DIR = $STUB_OUT), or the shell lines `settings` when given.
    Every other invocation runs `extra` first (it may `exit`) and then the default build, which
    writes `$STUB_OUT/<product>` with a real Info.plist and `built.txt` (the commit built)."""
    shown = settings if settings is not None else (
        "    printf '    BUILT_PRODUCTS_DIR = %s\\n' \"$STUB_OUT\"\n"
        f"    echo '    FULL_PRODUCT_NAME = {product}'\n"
        "    echo '    PRODUCT_BUNDLE_IDENTIFIER = com.example.fake'\n"
        "    echo '    EXECUTABLE_NAME = Fake'\n")
    return (
        'case " $* " in\n'
        '  *" -showBuildSettings "*)\n'
        f"{shown}"
        "    ;;\n"
        "  *)\n"
        f"{extra or ':'}\n"
        f'    app="$STUB_OUT/{product}"\n'
        '    mkdir -p "$app/Contents/MacOS" && touch "$app/Contents/MacOS/Fake"\n'
        "    cat > \"$app/Contents/Info.plist\" <<'PLIST'\n"
        f"{_FAKE_PLIST}\n"
        "PLIST\n"
        '    git rev-parse HEAD > "$app/built.txt"\n'
        "    ;;\n"
        "esac")


# The default stub contract for `install` (Tasks 5 and 6). Everything external is a stub on PATH,
# so the tests run on Linux CI too. Bundle ids are read with plistlib from Contents/Info.plist
# (Ruling R8): there is no plutil stub. codesign fails for a bundle that holds `bad-signature`;
# osascript's quit removes $STUB_PS_FILE, its Finder delete moves the last argument to $STUB_TRASH.
DEFAULT_STUBS = {
    "xcodebuild": _with_settings(),
    "codesign": 'for last; do :; done\n[ -e "$last/bad-signature" ] && exit 1\nexit 0',
    "ditto": 'cp -R "$1" "$2"',
    "ps": 'if [ -f "$STUB_PS_FILE" ]; then cat "$STUB_PS_FILE"; fi',
    "pgrep": "exit 1",
    "osascript": (
        'case "$*" in\n'
        '  *"to quit"*) rm -f "$STUB_PS_FILE" ;;\n'
        '  *Finder*delete*) for last; do :; done; mv "$last" "$STUB_TRASH/" ;;\n'
        "esac"),
    "lsregister": "exit 0",
    "xcodegen": "exit 0",
    "sudo": "exit 1",          # any sudo call is logged (and fails), so "no sudo" can be asserted
}


def write_app(path, bundle_id="com.example.fake") -> Path:
    """A fake app bundle: a folder with a real XML Contents/Info.plist (Ruling R8)."""
    app = Path(path)
    (app / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleIdentifier": bundle_id, "CFBundleExecutable": "Fake"}, f)
    return app


def stub_bin(tmp_path, **behaviours) -> Path:
    """One executable shell script per name in `<tmp_path>/stub bin`; the body is the snippet.
    The DEFAULT_STUBS are always written; a keyword replaces the default of that name or adds a
    new name. Every stub appends 'name argv...' to $STUB_LOG when it is set."""
    d = Path(tmp_path) / "stub bin"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in {**DEFAULT_STUBS, **behaviours}.items():
        f = d / name
        f.write_text(
            "#!/bin/sh\n"
            f'if [ -n "$STUB_LOG" ]; then printf \'%s\\n\' "{name} $*" >> "$STUB_LOG"; fi\n'
            f"{body}\n", encoding="utf-8")
        f.chmod(0o755)
    return d


def stub_env(tmp_path) -> dict:
    """Environment variables the stubs and work-state.py read, all under tmp_path."""
    base = Path(tmp_path)
    out, trash, home = base / "stub out", base / "stub trash", base / "home dir"
    for d in (out, trash, home):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "STUB_OUT": str(out),
        "STUB_LOG": str(base / "stub.log"),
        "STUB_PS_FILE": str(base / "stub ps.txt"),
        "STUB_TRASH": str(trash),
        "GSTACK_LSREGISTER": str(base / "stub bin" / "lsregister"),
        "GSTACK_SWAP": "rename",        # hidden test knob: a rename dance instead of renamex_np
        "HOME": str(home),              # the ~/.Trash fallback never reaches the real home folder
    }
