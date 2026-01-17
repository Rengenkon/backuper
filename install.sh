#!/bin/bash

# Load core functionality
#!/bin/bash

# 1. Try to find core.sh relative to the command as executed
CORE_FILE="$(dirname "$0")/core.sh"

if [ ! -f "$CORE_FILE" ]; then
    # 2. Fallback: Resolve symlink to find the actual physical directory
    REAL_SCRIPT_PATH=$(readlink -f "$0" 2>/dev/null || perl -MCwd -e 'print Cwd::abs_path shift' "$0")
    SOURCE_DIR="$(dirname "$REAL_SCRIPT_PATH")"
    CORE_FILE="$SOURCE_DIR/core.sh"
fi

# 3. Final check and source
if [ -f "$CORE_FILE" ]; then
    source "$CORE_FILE"
else
    echo "Fatal Error: core.sh not found!"
    echo "Checked: $(dirname "$0")/core.sh"
    echo "Checked: $CORE_FILE"
    exit 1
fi

log_private "Installation started."

# 1. SSH Key setup
read -p "Enter the full path to your SSH private key (default: $HOME/.ssh/id_rsa): " ssh_key_path
ssh_key_path=${ssh_key_path:-"$HOME/.ssh/id_rsa"}

if [ -f "$ssh_key_path" ]; then
    # Update config with the provided key path
    sed -i "s|SSH_GIT_KEY=.*|SSH_GIT_KEY=\"$ssh_key_path\"|" "$SETTINGS_FILE"
    log_private "SSH key set to: $ssh_key_path"
else
    log_public "Warning: SSH key not found at $ssh_key_path. Ensure it exists before the first run."
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

# 3. Schedule setup (Cron)
read -p "Enter backup frequency in cron format (default: weekly '0 0 * * 1'): " cron_freq
cron_freq=${cron_freq:-"0 0 * * 1"}
(crontab -l 2>/dev/null | grep -v "git-committer") | { cat; echo "$cron_freq ${SYMLINKS[1]}"; } | crontab -
log_public "Cron schedule updated: $cron_freq"

# 4. Repository list setup
echo "----------------------------------------------------------------"
echo "Enter paths to repositories one by one."
echo "Press Enter on an empty line to finish."
echo "----------------------------------------------------------------"

while true; do
    read -r -p "Path: " input_path
    [ -z "$input_path" ] && break
    
    # Remove quotes
    clean_path="${input_path%\"}"
    clean_path="${clean_path#\"}"
    
    # Execute manager
    if [ -f "$(dirname "$0")/manager.sh" ]; then
        bash "$(dirname "$0")/manager.sh" "$clean_path"
    else
        log_public "Error: manager.sh not found."
    fi
done

log_public "Setup complete. Config: $SETTINGS_FILE"
log_private "Installation finished successfully."