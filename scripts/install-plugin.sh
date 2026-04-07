#!/bin/bash
# Install the superpowers-gstack plugin
#
# Recommended: install via marketplace (proper Claude Code registration)
# Dev mode: creates a symlink for local development (skills won't appear
# in the available skills list — use --dev flag explicitly)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.claude/plugins"
LINK_NAME="superpowers-gstack"
LINK_PATH="$PLUGIN_DIR/$LINK_NAME"

if [ "${1:-}" = "--dev" ]; then
  # Dev mode: symlink for local iteration (skills won't be discoverable)
  mkdir -p "$PLUGIN_DIR"

  if [ -L "$LINK_PATH" ]; then
    current_target=$(readlink "$LINK_PATH")
    if [ "$current_target" = "$REPO_DIR" ]; then
      echo "Dev symlink already in place."
      echo "  $LINK_PATH -> $REPO_DIR"
      exit 0
    else
      echo "Updating dev symlink (was: $current_target)"
      rm "$LINK_PATH"
    fi
  elif [ -e "$LINK_PATH" ]; then
    echo "Error: $LINK_PATH exists but is not a symlink. Remove it manually."
    exit 1
  fi

  ln -s "$REPO_DIR" "$LINK_PATH"
  echo "Dev symlink created:"
  echo "  $LINK_PATH -> $REPO_DIR"
  echo ""
  echo "Note: Skills won't appear in the available skills list."
  echo "For full functionality, install via marketplace instead (see README)."
  exit 0
fi

# Default: print marketplace install instructions
echo "Install superpowers-gstack via the Claude Code marketplace:"
echo ""
echo "  1. In Claude Code, run:"
echo "     /plugin marketplace add kjetilge/kjetil-claude-marketplace"
echo "     /plugin install superpowers-gstack@kjetil-plugins"
echo ""
echo "  2. Restart Claude Code"
echo ""
echo "  3. Verify with: /plugin list"
echo ""
echo "For local development, use: $0 --dev"
