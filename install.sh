#!/usr/bin/env bash
# install.sh

source "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh" 2>/dev/null ||
    { echo "Cannot load core.sh"; exit 1; }

echo "Starting installation..."

# SSH ключ
read -r -p "Path to SSH private key [default: ~/.ssh/id_rsa]: " key
key=${key:-"$HOME/.ssh/id_rsa"}
if [[ -f "$key" ]]; then
    sed -i "s|^SSH_GIT_KEY=.*|SSH_GIT_KEY=\"$key\"|" "$SETTINGS_FILE" 2>/dev/null
    echo "SSH key set: $key"
else
    echo "Warning: SSH key not found at $key"
fi

# 2. Symlinks setup & Privilege Elevation logic
SYMLINKS=("/usr/local/bin/git-manager" "/usr/local/bin/git-committer")
SOURCE_FILES=("manager.sh" "committer.sh")
LINKS_INSTALLED=false

# Check if links already exist and are working
if [ -L "${SYMLINKS[0]}" ] && [ -L "${SYMLINKS[1]}" ]; then
    log_private "Symlinks already exist. Checking integrity..."
    LINKS_INSTALLED=true
fi

if [ "$LINKS_INSTALLED" = false ]; then
    read -p "Symlinks not found. Install them to /usr/local/bin? (Requires sudo) [Y/n]: " add_path
    add_path=${add_path:-Y}

    if [[ "$add_path" =~ ^[Yy]$ ]]; then
        # Check if user has sudo potential (member of sudo or wheel groups)
        if ! groups $USER | grep -qE '\b(sudo|wheel)\b' && [ "$EUID" -ne 0 ]; then
            log_public "Error: User $USER is not in sudo/wheel group. Cannot escalate privileges."
            exit 1
        fi

        log_private "Requesting administrative privileges for symlink creation..."
        
        # We use 'sudo -v' to validate credentials and 'sudo -n' to check if we can run it
        if sudo -v; then
            CMD_PREFIX="sudo"
            
            SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
            for i in "${!SYMLINKS[@]}"; do
                if [ -f "$SCRIPT_DIR/${SOURCE_FILES[$i]}" ]; then
                    # Atomic creation of symlink with privilege escalation
                    if $CMD_PREFIX ln -sf "$SCRIPT_DIR/${SOURCE_FILES[$i]}" "${SYMLINKS[$i]}"; then
                        $CMD_PREFIX chmod +x "$SCRIPT_DIR/${SOURCE_FILES[$i]}"
                        log_public "Successfully installed symlink: ${SYMLINKS[$i]}"
                        LINKS_INSTALLED=true
                    else
                        log_public "Error: Failed to create symlink even with sudo."
                    fi
                else
                    log_public "Error: Source file $SCRIPT_DIR/${SOURCE_FILES[$i]} missing."
                fi
            done
        else
            log_public "Error: Sudo authentication failed or timed out."
            exit 1
        fi
    fi
fi

# Interrupt if links are still missing
if [ "$LINKS_INSTALLED" = false ]; then
    log_public "Installation aborted: Symlinks are required. Please allow creation with sudo."
    exit 1
fi


# systemd unit + timer
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

# Запрос частоты
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
Description=Timer for git auto-commit

[Timer]
OnCalendar=$oncal
Persistent=true
RandomizedDelaySec=600   # ±10 минут

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now $UNIT.timer 2>/dev/null || {
    systemctl --user restart $UNIT.timer
}

echo
echo "Timer installed with schedule: $oncal"
echo
echo "To change schedule later:"
echo "  1. Edit file:   nano ~/.config/systemd/user/git-auto-commit.timer"
echo "  2. Change OnCalendar=..."
echo "  3. Then run:"
echo "     systemctl --user daemon-reload"
echo "     systemctl --user restart git-auto-commit.timer"
echo
echo "Useful commands:"
echo "  journalctl --user -u git-auto-commit -f          # live logs"
echo "  systemctl --user status git-auto-commit.timer    # when next run"
echo "  systemctl --user list-timers --all               # all user timers"

# Добавление репозиториев (как раньше)
echo
echo "Add repositories now?"
while true; do
    read -r -p "Path (empty to finish): " path
    [[ -z "$path" ]] && break
    git-manager "${path}"
done

echo "Installation complete."