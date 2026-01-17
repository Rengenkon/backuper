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

delete_mode=false

# Check for deletion flag
if [ "$1" == "-d" ]; then
    delete_mode=true
    shift # Remove -d from arguments list
fi

if [ $# -eq 0 ]; then
    echo "Usage: git-manager [-d] /path/to/repo1 [/path/to/repo2 ...]"
    exit 1
fi

for repo in "$@"; do
    abs_path=$(realpath "$repo" 2>/dev/null)

    if [ "$delete_mode" = true ]; then
        if grep -Fxq "$abs_path" "$REPOS_FILE"; then
            # Create a temporary file without the specified repo
            grep -Fxv "$abs_path" "$REPOS_FILE" > "${REPOS_FILE}.tmp" && mv "${REPOS_FILE}.tmp" "$REPOS_FILE"
            log_public "REMOVED: $abs_path from the tracking list."
        else
            echo "Notice: $repo was not found in the list."
        fi
        continue
    fi

    # 1. Validation for adding
    if [ ! -d "$abs_path" ]; then
        log_private "Error: $repo is not a directory. Skipping."
        continue
    fi

    if [ ! -r "$abs_path" ] || [ ! -w "$abs_path" ]; then
        log_private "Error: Insufficient permissions for $abs_path. Skipping."
        continue
    fi

    if [ ! -d "$abs_path/.git" ]; then
        log_private "Error: $abs_path is not a Git repository. Skipping."
        continue
    fi

    # 2. Adding to the list
    if grep -Fxq "$abs_path" "$REPOS_FILE"; then
        echo "Notice: $abs_path is already in the list."
    else
        echo "$abs_path" >> "$REPOS_FILE"
        log_public "ADDED: $abs_path to the tracking list."
    fi
done