#!/usr/bin/env bash
# contrast-check.sh — WCAG 2.1 contrast ratio between two hex colors.
#
# Usage: contrast-check.sh <fg-hex> <bg-hex>
# Output: JSON to stdout with ratio + pass flags for AA-normal and AA-large.
# Exit: 0 on success; nonzero on usage error or invalid hex (caller should
# check exit code and treat nonzero as "skip contrast check, warn user").
#
# Implements sRGB → linear → relative luminance → contrast ratio
# per https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio. Uses `bc`
# for floating-point math. No external libraries required (bash + bc
# are present on every macOS + Linux install).

set -euo pipefail

# Force POSIX decimals in printf and bc so JSON output is valid regardless
# of the user's locale (e.g., nb_NO.UTF-8 would otherwise produce comma
# decimals like "ratio": 4,62 which is invalid JSON).
export LC_ALL=C

if [ "$#" -ne 2 ]; then
  echo '{"error": "usage: contrast-check.sh <fg-hex> <bg-hex>"}' >&2
  exit 1
fi

# Strip leading # if present, accept 3-char or 6-char hex.
normalize_hex() {
  local h="${1#\#}"
  if [ "${#h}" = "3" ]; then
    h="${h:0:1}${h:0:1}${h:1:1}${h:1:1}${h:2:1}${h:2:1}"
  fi
  if ! [[ "$h" =~ ^[0-9a-fA-F]{6}$ ]]; then
    echo "invalid hex: $1" >&2
    exit 2
  fi
  printf '%s\n' "$h"
}

FG=$(normalize_hex "$1")
BG=$(normalize_hex "$2")

# Extract R, G, B as 0-255 ints.
hex_channel() {
  printf '%d\n' "0x$1"
}

FR=$(hex_channel "${FG:0:2}")
FG_=$(hex_channel "${FG:2:2}")
FB=$(hex_channel "${FG:4:2}")
BR=$(hex_channel "${BG:0:2}")
BG_=$(hex_channel "${BG:2:2}")
BB=$(hex_channel "${BG:4:2}")

# sRGB channel → linear: if c/255 <= 0.03928 then c/255/12.92 else ((c/255+0.055)/1.055)^2.4
# Use bc -l for floating point + power.
to_linear() {
  local c=$1
  bc -l <<EOF
v = $c / 255
if (v <= 0.03928) v / 12.92 else e(2.4 * l((v + 0.055) / 1.055))
EOF
}

# Relative luminance: 0.2126*R + 0.7152*G + 0.0722*B
luminance() {
  local r=$1 g=$2 b=$3
  local lr lg lb
  lr=$(to_linear "$r")
  lg=$(to_linear "$g")
  lb=$(to_linear "$b")
  bc -l <<EOF
0.2126 * $lr + 0.7152 * $lg + 0.0722 * $lb
EOF
}

LFG=$(luminance "$FR" "$FG_" "$FB")
LBG=$(luminance "$BR" "$BG_" "$BB")

# Contrast ratio: (lighter + 0.05) / (darker + 0.05)
RATIO=$(bc -l <<EOF
if ($LFG > $LBG) (($LFG + 0.05) / ($LBG + 0.05)) else (($LBG + 0.05) / ($LFG + 0.05))
EOF
)

# Format ratio to 2 decimals.
RATIO_FMT=$(printf '%.2f' "$RATIO")

# WCAG AA: 4.5:1 for normal text, 3:1 for large text (≥18pt or ≥14pt bold).
PASS_NORMAL=$(echo "$RATIO >= 4.5" | bc -l)
PASS_LARGE=$(echo "$RATIO >= 3.0" | bc -l)
PASS_AAA=$(echo "$RATIO >= 7.0" | bc -l)

# bc returns 1 for true, 0 for false; convert to JSON booleans.
bool() { [ "$1" = "1" ] && echo "true" || echo "false"; }

cat <<EOF
{
  "fg": "#$FG",
  "bg": "#$BG",
  "ratio": $RATIO_FMT,
  "pass_aa_normal": $(bool "$PASS_NORMAL"),
  "pass_aa_large": $(bool "$PASS_LARGE"),
  "pass_aaa_normal": $(bool "$PASS_AAA")
}
EOF
