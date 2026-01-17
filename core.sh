#!/bin/bash

# Shared Paths
export SETTINGS_DIR="$HOME/.config/git-auto-commit"
export SETTINGS_FILE="$SETTINGS_DIR/config.conf"
export REPOS_FILE="$SETTINGS_DIR/repos.list"
export DATA_DIR="$HOME/.local/share/git-auto-commit"
export LOCAL_LOG_FILE="$DATA_DIR/backup.log"
export GLOBAL_LOG_FILE="/var/log/git_backup.log"

# Global buffer for log messages
MSG_BUF=""

# Ensure base directories exist
mkdir -p "$SETTINGS_DIR"
mkdir -p "$DATA_DIR"
touch "$LOCAL_LOG_FILE"
touch "$REPOS_FILE"

# Initialize config if missing
if [ ! -f "$SETTINGS_FILE" ]; then
    cat << EOF > "$SETTINGS_FILE"
# Git Auto-Commit Config
GLOBAL_LOG_FILE="$GLOBAL_LOG_FILE"
LOCAL_LOG_FILE="$LOCAL_LOG_FILE"
REPOS_FILE="$REPOS_FILE"
SSH_GIT_KEY="$HOME/.ssh/id_rsa"
EOF
    chmod 600 "$SETTINGS_FILE"
fi

log_msg() {
    MSG_BUF="[$(date '+%Y-%m-%d %H:%M:%S')] [User: $USER] $1"
}

log_private() {
    log_msg "$1"
    echo "$MSG_BUF" >> "$LOCAL_LOG_FILE"
    echo "$1"
}

log_public() {
    log_msg "$1"
    echo "$MSG_BUF" >> "$LOCAL_LOG_FILE"
    if [ -w "$GLOBAL_LOG_FILE" ]; then
        echo "$MSG_BUF" >> "$GLOBAL_LOG_FILE"
    fi
    echo "$1"
}