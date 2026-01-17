#!/bin/bash

# Load core functionality and shared variables
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

# Ensure git commands can find the SSH key and binaries in cron environment
source "$SETTINGS_FILE"
export GIT_SSH_COMMAND="ssh -i $SSH_GIT_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log_private "Scheduled backup process started."

if [ ! -s "$REPOS_FILE" ]; then
    log_private "No repositories found in the tracking list. Exiting."
    exit 0
fi

# Process each repository in the list
while IFS= read -r repo_path || [ -n "$repo_path" ]; do
    # Skip empty linesё
    [[ -z "$repo_path" ]] && continue

    if [ ! -d "$repo_path" ]; then
        log_public "Warning: Repository directory $repo_path no longer exists. Skipping."
        continue
    fi

    cd "$repo_path" || continue

    # Check for changes (including untracked files)
    if [ -n "$(git status --porcelain)" ]; then
        current_branch=$(git rev-parse --abbrev-ref HEAD)
        
        # 1. Commit Stage: Gather statistics
        # We use --shortstat to get "X files changed, Y insertions(+), Z deletions(-)"
        git add .
        commit_msg="Auto-backup: $(date '+%Y-%m-%d %H:%M')"
        git commit -m "$commit_msg" > /dev/null
        
        # Get stats of the last commit
        stats=$(git diff --shortstat HEAD~1 HEAD 2>/dev/null || echo "Initial commit or stats unavailable")
        log_public "COMMITTED: Changes in [$repo_path] on branch [$current_branch]. Stats: $stats"

        # 2. Push Stage: Measure time and payload size
        # We capture the time taken and use 'git count-objects' for a rough estimate of size
        start_time=$(date +%s)
        
        # Capture stderr to get push details (size/objects)
        push_output=$(git push origin "$current_branch" 2>&1)
        push_exit_code=$?
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))

        if [ $push_exit_code -eq 0 ]; then
            # Extracting object count/size info from git output if available
            log_public "PUSHED: [$repo_path] successfully. Duration: ${duration}s. Remote: origin/$current_branch"
        else
            log_public "ERROR: Failed to push [$repo_path]. Git output: $push_output"
        fi
    else
        log_private "No changes detected in [$repo_path]. Skipping."
    fi

done < "$REPOS_FILE"

log_private "Scheduled backup process finished."