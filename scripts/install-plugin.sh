#!/bin/bash
# Install/update the superpowers-gstack plugin for the current user
# Creates a symlink in ~/.claude/plugins/ pointing to this repo

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_DIR="$HOME/.claude/plugins"
LINK_NAME="superpowers-gstack"
LINK_PATH="$PLUGIN_DIR/$LINK_NAME"

# Ensure plugins directory exists
mkdir -p "$PLUGIN_DIR"

# Check if symlink already points here
if [ -L "$LINK_PATH" ]; then
  current_target=$(readlink "$LINK_PATH")
  if [ "$current_target" = "$REPO_DIR" ]; then
    echo "Plugin already installed and up to date."
    echo "  $LINK_PATH -> $REPO_DIR"
    exit 0
  else
    echo "Updating symlink (was: $current_target)"
    rm "$LINK_PATH"
  fi
elif [ -e "$LINK_PATH" ]; then
  echo "Error: $LINK_PATH exists but is not a symlink. Remove it manually."
  exit 1
fi

ln -s "$REPO_DIR" "$LINK_PATH"
echo "Plugin installed:"
echo "  $LINK_PATH -> $REPO_DIR"
echo ""
echo "Restart Claude Code to activate. Then use: /superpowers-gstack:setup-routing"
