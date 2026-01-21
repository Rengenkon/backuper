#!/usr/bin/env bash
# committer.sh

# Поиск core.sh
if [[ -f "${0%/*}/core.sh" ]]; then
    source "${0%/*}/core.sh"
elif [[ -f "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh" ]]; then
    source "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh"
else
    echo "Fatal: core.sh not found" >&2
    exit 1
fi

export PATH="/usr/local/bin:/usr/bin:/usr/sbin:/bin:/sbin"
export GIT_SSH_COMMAND="ssh -i $SSH_GIT_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

echo "git-auto-commit started at $(date '+%Y-%m-%d %H:%M:%S')"

[[ ! -s "$REPOS_FILE" ]] && {
    echo "No repositories in $REPOS_FILE → exiting"
    exit 0
}

while IFS= read -r repo || [[ -n "$repo" ]]; do
    [[ -z "$repo" ]] && continue
    [[ ! -d "$repo" ]] && { echo "Directory gone: $repo"; continue; }
    [[ ! -d "$repo/.git" ]] && { echo "Not a git repo anymore: $repo"; continue; }

    cd "$repo" || continue

    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    [[ -z "$branch" ]] && { echo "Cannot determine branch in $repo"; continue; }

    changed=false
    # 1. Есть ли изменения в рабочей копии / индексе?
    if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
        git add --all .
        msg="Auto-backup $(date '+%Y-%m-%d %H:%M')"
        if git commit -q -m "$msg"; then
            echo "COMMITTED in $repo @ $branch → $msg"
            changed=true
        else
            echo "Commit failed in $repo"
        fi
    fi

    # 2. Есть ли незапушенные коммиты? (в т.ч. только что сделанный)
    if git rev-list --count "@{upstream}..HEAD" 2>/dev/null | grep -qE '^[1-9]'; then
        start=$(date +%s)
        push_out=$(git push --quiet origin "$branch" 2>&1)
        ret=$?
        duration=$(( $(date +%s) - start ))

        if [[ $ret -eq 0 ]]; then
            echo "PUSHED $repo @ $branch (${duration}s)"
        else
            echo "PUSH FAILED $repo @ $branch (code $ret)"
            [[ -n "$push_out" ]] && echo "→ $push_out"
        fi
    elif [[ "$changed" = false ]]; then
        echo "Nothing to do in $repo @ $branch"
    fi

done < "$REPOS_FILE"

echo "git-auto-commit finished at $(date '+%Y-%m-%d %H:%M:%S')"