#!/usr/bin/env bash
# core.sh — minimal shared definitions

SETTINGS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/git-auto-commit"
REPOS_FILE="$SETTINGS_DIR/repos.list"

# Ensure the directory and file exist
mkdir -p "$SETTINGS_DIR" 2>/dev/null || true
touch "$REPOS_FILE" 2>/dev/null || true