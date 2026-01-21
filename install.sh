#!/usr/bin/env bash
# install.sh — setup git-auto-commit (systemd timer + symlinks)


SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [[ -f "$SCRIPT_DIR/core.sh" ]]; then
    source "$SCRIPT_DIR/core.sh"
else
    echo "Fatal: core.sh not found in $SCRIPT_DIR" >&2
    exit 1
fi

echo "Starting git-auto-commit installation..."

# Create symlinks in /usr/local/bin
declare -A scripts=(
    ["git-committer"]="committer.sh"
    ["git-manager"]="manager.sh"
)

need_sudo=false
for cmd in "${!scripts[@]}"; do
    if [[ ! -L "/usr/local/bin/$cmd" || ! -x "/usr/local/bin/$cmd" ]]; then
        need_sudo=true
        break
    fi
done

if $need_sudo; then
    echo
    read -r -p "Create symlinks in /usr/local/bin? (requires sudo) [Y/n] " ans
    if [[ "${ans:-Y}" =~ ^[Yy]$ ]]; then
        if ! sudo -v 2>/dev/null; then
            echo "Error: sudo not available" >&2
            exit 1
        fi

        for cmd in "${!scripts[@]}"; do
            src="$SCRIPT_DIR/${scripts[$cmd]}"
            if [[ -f "$src" ]]; then
                sudo ln -sf "$src" "/usr/local/bin/$cmd"
                sudo chmod +x "$src" 2>/dev/null
                echo "Installed: /usr/local/bin/$cmd → $src"
            else
                echo "Source file not found: $src"
            fi
        done
    else
        echo "Installation aborted (symlinks are required for convenient usage)"
        exit 1
    fi
fi

# SSH usage notice
echo
echo "──────────────────────────────────────────────────────────────"
echo "Important: this script does NOT set any SSH key path."
echo "It uses your standard user SSH configuration:"
echo "  • ~/.ssh/config (recommended for custom keys/hosts)"
echo "  • ssh-agent (if you added your key there)"
echo "  • default key names (~/.ssh/id_ed25519, id_rsa, etc.)"
echo
echo "Example ~/.ssh/config content (for GitHub):"
echo
cat << 'EOF'
# Example ~/.ssh/config
Host github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
    AddKeysToAgent yes
EOF

echo
read -r -p "Show your current ~/.ssh/config file? (y/N) " show_config
if [[ "${show_config:-N}" =~ ^[Yy]$ ]]; then
    echo
    if [[ -f "$HOME/.ssh/config" ]]; then
        echo "Your current ~/.ssh/config:"
        echo "────────────────────────────────────────"
        cat "$HOME/.ssh/config"
        echo "────────────────────────────────────────"
    else
        echo "No ~/.ssh/config file found yet."
        echo "You can create it with: nano ~/.ssh/config"
    fi
    echo
fi

echo "Make sure your key is loaded if needed:"
echo "  ssh-add ~/.ssh/your_key   (only needed once per login)"
echo "or set up ssh-agent as a systemd service for automatic loading."
echo "──────────────────────────────────────────────────────────────"
echo

# systemd user timer setup
UNIT="git-auto-commit"
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/$UNIT.service <<'EOF'
[Unit]
Description=Automatic git commit & push for tracked repositories

[Service]
Type=simple
ExecStart=/usr/local/bin/git-committer
Restart=on-failure
RestartSec=45
StandardOutput=journal
StandardError=journal
EOF

echo
echo "How often should auto-commit run?"
echo "  Examples:"
echo "    weekly         → every Monday at 00:15"
echo "    daily          → every day at 01:00"
echo "    0 3 * * *      → every day at 03:00"
echo "    Mon,Thu *-*-* 02:30:00 → Mondays and Thursdays at 02:30"
echo

read -r -p "Enter schedule (OnCalendar format) or keyword [weekly]: " schedule

case "${schedule:-weekly}" in
    daily|"every day")          oncal="*-*-* 01:00:00" ;;
    weekly|"every week")        oncal="Mon *-*-* 00:15:00" ;;
    "")                         oncal="Mon *-*-* 00:15:00" ;;
    *)
        # Простая проверка — хотя бы похоже на cron/OnCalendar
        if [[ "$schedule" =~ ^[A-Za-z0-9*,/-]+(\s+[0-9*:,-]+)+$ ]] ||
           [[ "$schedule" =~ ^[A-Za-z]+(\s+[-*0-9]+)+(\s+[0-9*:,]+)+$ ]]; then
            oncal="$schedule"
        else
            echo "Unrecognized format → using default (weekly)"
            oncal="Mon *-*-* 00:15:00"
        fi
        ;;
esac

cat > ~/.config/systemd/user/$UNIT.timer <<EOF
[Unit]
Description=Timer for $UNIT

[Timer]
OnCalendar=$oncal
Persistent=true
RandomizedDelaySec=600

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT.timer" 2>/dev/null || systemctl --user restart "$UNIT.timer"

echo
echo "Timer installed with schedule: $$oncal"
echo "To change later:"
echo "  1. Edit ~/.config/systemd/user/git-auto-commit.timer"
echo "  2. Run: systemctl --user daemon-reload"
echo "     systemctl --user restart git-auto-commit.timer"
echo

# Add repositories
echo "Add repositories to track:"
echo "--------------------------------"
while true; do
    read -r -p "Path to repo (empty to finish): " path
    [[ -z "$path" ]] && break
    if command -v git-manager >/dev/null 2>&1; then
        git-manager "$path"
    else
        echo "git-manager not in PATH yet → run installation again or add manually"
    fi
done

echo
echo "Installation finished."
echo "View logs:     journalctl --user -u git-auto-commit -f"
echo "Timer status:  systemctl --user status git-auto-commit.timer"
echo "Next runs:     systemctl --user list-timers --all"