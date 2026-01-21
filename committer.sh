#!/usr/bin/env bash
# committer.sh — automatically commit & push changed repositories

# Locate and source core.sh
if [[ -f "${0%/*}/core.sh" ]]; then
    source "${0%/*}/core.sh"
elif [[ -f "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh" ]]; then
    source "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh"
else
    echo "Fatal: core.sh not found" >&2
    exit 1
fi

export PATH="/usr/local/bin:/usr/bin:/usr/sbin:/bin:/sbin"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] git-auto-commit started"

if [[ ! -s "$REPOS_FILE" ]]; then
    echo "No repositories in $REPOS_FILE → exiting"
    exit 0
fi

while IFS= read -r repo || [[ -n "$repo" ]]; do
    [[ -z "$repo" ]] && continue

    if [[ ! -d "$repo" || ! -d "$repo/.git" ]]; then
        echo "Skipped (gone or not git repo): $repo"
        continue
    fi

    cd "$repo" || continue

    branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")
    [[ -z "$branch" ]] && { echo "No branch in $repo"; continue; }

    changed=false

    # 1. Are there changes in working directory / index?
    if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
        git add --all .
        msg="Auto-backup $(date '+%Y-%m-%d %H:%M')"
        if git commit -q -m "$msg"; then
            echo "COMMITTED  $repo @ $branch  → $msg"
            changed=true
        else
            echo "commit failed in $repo"
        fi
    fi

    # 2. Are there unpushed commits?
    upstream_branch="origin/$branch"
    if git rev-parse --verify "$upstream_branch" >/dev/null 2>&1; then
        if git rev-list --count "$upstream_branch..HEAD" 2>/dev/null | grep -qE '^[1-9]'; then
            start=$(date +%s)
            push_out=$(git push --quiet origin "$branch" 2>&1)
            ret=$?
            duration=$(( $(date +%s) - start ))

            if [[ $ret -eq 0 ]]; then
                echo "PUSHED     $repo @ $branch (${duration}s)"
            else
                echo "PUSH FAILED $repo @ $branch (code $ret)"
                [[ -n "$push_out" ]] && echo "  → $push_out"
            fi
        elif [[ "$changed" = false ]]; then
            echo "Up-to-date $repo @ $branch"
        fi
    else
        echo "No upstream tracking for $branch in $repo — skipping push"
    fi

done < "$REPOS_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] git-auto-commit finished"