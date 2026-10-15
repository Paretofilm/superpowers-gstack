#!/usr/bin/env bash
# window-shot.sh <pid> <out.png>
#
# Capture ONE window of an app the agent itself launched, without a permission dialog
# and without touching the rest of the display. Never the whole screen: a whole-display
# capture on a working Mac shows calendar, notes and file names, which the task never
# needs. The window is found by PID with CGWindowListCopyWindowInfo (no permission
# needed to list windows) and captured with `screencapture -x -o -l <id>`.
#
# Standing consent: the project's `.gstack/visual-verify` must read exactly `host`.
# `vm`, `off`, a missing file and any other content all refuse; an invalid value is
# BLOCKED rather than read as `off`, as with .gstack/e2e-executor.
#
# Optional: WINDOW_SHOT_EXPECT=<full executable path>. When set, the PID must be
# running exactly that executable (the `ps -o comm=` proof from verify-and-land
# Phase 5), so a helper or another copy cannot answer for the build under test.
#
# Exit codes
#   0  captured; the path is the last line on stdout
#   2  usage error, no `host` pin, or an invalid pin
#   3  not macOS
#   4  no on-screen window for that PID (minimised, other Space, not up yet, or the
#      process is gone): retried for ~10 s before giving up
#   5  the PNG shows nothing (wallpaper or black): Screen Recording is probably not
#      granted. Fall back to live-swiftui or the VM rig and say so; do not report it.
#   6  the PID is not running, or not the executable WINDOW_SHOT_EXPECT names

set -uo pipefail

die() { printf '%s\n' "$2" >&2; exit "$1"; }

[ $# -eq 2 ] || die 2 "USAGE ERROR: window-shot.sh <pid> <out.png>"
PID=$1; OUT=$2
case "$PID" in ''|*[!0-9]*) die 2 "USAGE ERROR: <pid> must be a number, got '$PID'";; esac
case "$OUT" in *.png) ;; *) die 2 "USAGE ERROR: <out.png> must end in .png";; esac

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PIN="$ROOT/.gstack/visual-verify"
if [ -f "$PIN" ]; then
  VALUE=$(cat "$PIN"; printf x); VALUE=${VALUE%x}   # keep every trailing newline: $(...) alone would eat them
  VALUE=${VALUE%$'\n'}                              # the file's own single newline is the only one allowed
  case "$VALUE" in
    host) ;;
    vm|off)
      die 2 "BLOCKED — .gstack/visual-verify is '$VALUE': window capture on the host needs exactly 'host'" ;;
    *) die 2 "BLOCKED — invalid .gstack/visual-verify: must be exactly host, vm or off" ;;
  esac
else
  die 2 "BLOCKED — no .gstack/visual-verify: write 'host' there to authorise window capture of an app this session launched"
fi

[ "$(uname -s)" = "Darwin" ] || die 3 "window-shot.sh needs macOS (CGWindowListCopyWindowInfo, screencapture)"

ACTUAL=$(ps -o comm= -p "$PID" 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
[ -n "$ACTUAL" ] || die 6 "pid $PID is not running"
if [ -n "${WINDOW_SHOT_EXPECT:-}" ] && [ "$ACTUAL" != "$WINDOW_SHOT_EXPECT" ]; then
  die 6 "pid $PID runs '$ACTUAL', not '$WINDOW_SHOT_EXPECT'"
fi

SWIFT_SRC=$(mktemp "${TMPDIR:-/tmp}/window-shot.XXXXXX") || die 2 "cannot create a temp file"
trap 'rm -f "$SWIFT_SRC"' EXIT
cat > "$SWIFT_SRC" <<'SWIFT'
import CoreGraphics
let pid = Int(CommandLine.arguments[1])!
let w = (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? [])
    .first { ($0[kCGWindowOwnerPID as String] as? Int) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
if let n = w?[kCGWindowNumber as String] { print(n) }
SWIFT

WID=""
for _ in $(seq 1 20); do
  WID=$(swift "$SWIFT_SRC" "$PID" 2>/dev/null | tail -1)
  case "$WID" in ''|*[!0-9]*) WID="";; esac
  [ -n "$WID" ] && break
  kill -0 "$PID" 2>/dev/null || die 4 "pid $PID exited before a window appeared"
  sleep 0.5
done
[ -n "$WID" ] || die 4 "no on-screen window for pid $PID after 10 s (minimised, on another Space, or not launched yet)"

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
screencapture -x -o -l "$WID" "$OUT" 2>/dev/null
[ -s "$OUT" ] || die 5 "screencapture produced no image: Screen Recording is probably not granted"

# A window capture that shows nothing is a tiny PNG for its pixel count: a uniform
# image compresses to almost nothing. Real UI is far above this ratio.
W=$(sips -g pixelWidth  "$OUT" 2>/dev/null | awk '/pixelWidth/{print $2}')
H=$(sips -g pixelHeight "$OUT" 2>/dev/null | awk '/pixelHeight/{print $2}')
BYTES=$(wc -c < "$OUT" | tr -d ' ')
if [ -n "$W" ] && [ -n "$H" ] && [ "$((W * H))" -gt 0 ]; then
  [ $((BYTES * 1000 / (W * H))) -ge 2 ] || die 5 "the capture is uniform (${W}x${H}, ${BYTES} bytes): Screen Recording is probably not granted"
fi

printf 'window-shot: pid %s window %s %sx%s %s bytes\n' "$PID" "$WID" "${W:-?}" "${H:-?}" "$BYTES" >&2
printf '%s\n' "$OUT"
