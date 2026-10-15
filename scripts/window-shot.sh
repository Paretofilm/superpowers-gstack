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
#   5  the PNG is one uniform colour (wallpaper or black): Screen Recording is probably not
#      granted. Fall back to live-swiftui or the VM rig and say so; do not report it.
#   6  the PID is not running, or not the executable WINDOW_SHOT_EXPECT names
#   7  the Swift helper cannot be built (Xcode command line tools missing or broken)

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
  die 2 "BLOCKED — no .gstack/visual-verify: write 'host' there and commit it (like .gstack/e2e-executor, so every worktree carries it) to authorise window capture of an app this session launched"
fi

[ "$(uname -s)" = "Darwin" ] || die 3 "window-shot.sh needs macOS (CGWindowListCopyWindowInfo, screencapture)"

ACTUAL=$(ps -o comm= -p "$PID" 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
[ -n "$ACTUAL" ] || die 6 "pid $PID is not running"
if [ -n "${WINDOW_SHOT_EXPECT:-}" ] && [ "$ACTUAL" != "$WINDOW_SHOT_EXPECT" ]; then
  die 6 "pid $PID runs '$ACTUAL', not '$WINDOW_SHOT_EXPECT'"
fi

# One compiled helper, built once: `id <pid>` prints the window id, `uniform <png>` says
# whether the image shows nothing. Interpreting the source on every retry costs seconds each
# and hides compile errors behind a misleading "no window".
WORK=$(mktemp -d "${TMPDIR:-/tmp}/window-shot.XXXXXX") || die 2 "cannot create a temp directory"
trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/helper.swift" <<'SWIFT'
import CoreGraphics
import Foundation
import ImageIO

func windowID(_ pid: Int) -> String {
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
    let w = list.first { ($0[kCGWindowOwnerPID as String] as? Int) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }
    if let n = w?[kCGWindowNumber as String] { return "\(n)" }
    return ""
}

// 64x64 thumbnail; the image "shows nothing" when every channel of every pixel is within 6 of the others.
func isUniform(_ path: String) -> Bool {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { return true }
    let n = 64
    var px = [UInt8](repeating: 0, count: n * n * 4)
    let drawn: Bool = px.withUnsafeMutableBytes { buf in
        guard let ctx = CGContext(data: buf.baseAddress, width: n, height: n, bitsPerComponent: 8,
                                  bytesPerRow: n * 4, space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: n, height: n))
        return true
    }
    if !drawn { return true }
    for c in 0..<3 {
        var lo = 255, hi = 0
        for i in stride(from: c, to: px.count, by: 4) { lo = min(lo, Int(px[i])); hi = max(hi, Int(px[i])) }
        if hi - lo > 6 { return false }
    }
    return true
}

let a = CommandLine.arguments
if a.count == 3, a[1] == "id", let pid = Int(a[2]) { print(windowID(pid)) }
else if a.count == 3, a[1] == "uniform" { print(isUniform(a[2]) ? "uniform" : "varied") }
else { exit(64) }
SWIFT
HELPER="$WORK/helper"
if ! swiftc -O -o "$HELPER" "$WORK/helper.swift" 2> "$WORK/swiftc.err"; then
  head -5 "$WORK/swiftc.err" >&2
  die 7 "cannot build the window helper: the Xcode command line tools (swiftc) are missing or broken"
fi

WID=""
for _ in $(seq 1 20); do
  WID=$("$HELPER" id "$PID" 2>/dev/null | tail -1)
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
[ "$("$HELPER" uniform "$OUT" 2>/dev/null)" = "varied" ] \
  || die 5 "the capture shows nothing (one uniform colour): Screen Recording is probably not granted, or the window is genuinely blank"

BYTES=$(wc -c < "$OUT" | tr -d ' ')
printf 'window-shot: pid %s window %s %s bytes\n' "$PID" "$WID" "$BYTES" >&2
printf '%s\n' "$OUT"
