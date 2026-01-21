#!/usr/bin/env bash
# core.sh

export SETTINGS_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/git-auto-commit"
export SETTINGS_FILE="$SETTINGS_DIR/config.conf"
export REPOS_FILE="$SETTINGS_DIR/repos.list"
export SSH_GIT_KEY="${HOME}/.ssh/id_rsa"   # дефолт, может быть переопределён

mkdir -p "$SETTINGS_DIR" 2>/dev/null
touch "$REPOS_FILE" 2>/dev/null

if [[ ! -f "$SETTINGS_FILE" ]]; then
    cat > "$SETTINGS_FILE" <<- 'EOF'
	# git-auto-commit config
	SSH_GIT_KEY="${HOME}/.ssh/id_rsa"
	EOF
    chmod 600 "$SETTINGS_FILE"
fi

# shellcheck source=disable=SC1090
source "$SETTINGS_FILE" 2>/dev/null || true