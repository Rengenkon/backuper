#!/usr/bin/env bash
# manager.sh — add / remove repositories from tracking list

# Locate and source core.sh
if [[ -f "${0%/*}/core.sh" ]]; then
    source "${0%/*}/core.sh"
elif [[ -f "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh" ]]; then
    source "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0")")/core.sh"
else
    echo "Fatal: core.sh not found" >&2
    exit 1
fi

delete_mode=false

if [[ "$1" == "-d" ]]; then
    delete_mode=true
    shift
fi

if [[ $# -eq 0 ]]; then
    echo "Usage: git-manager [-d] /path/to/repo1 [ /path/to/repo2 ... ]"
    echo "  -d    remove repository from tracking list"
    exit 1
fi

for repo in "$@"; do
    abs_path=$(realpath "$repo" 2>/dev/null)
    if [[ -z "$abs_path" ]]; then
        echo "Cannot resolve path: $repo"
        continue
    fi

    if [[ "$delete_mode" == true ]]; then
        if grep -Fxq "$abs_path" "$REPOS_FILE"; then
            grep -Fxv "$abs_path" "$REPOS_FILE" > "${REPOS_FILE}.tmp" && mv "${REPOS_FILE}.tmp" "$REPOS_FILE"
            echo "REMOVED: $abs_path from tracking list"
        else
            echo "Not found in list: $abs_path"
        fi
        continue
    fi

    # Add mode
    if [[ ! -d "$abs_path" ]]; then
        echo "Not a directory: $repo"
        continue
    fi
    if [[ ! -d "$abs_path/.git" ]]; then
        echo "Not a git repository: $repo"
        continue
    fi
    if [[ ! -r "$abs_path" || ! -w "$abs_path" ]]; then
        echo "Insufficient permissions: $repo"
        continue
    fi

    if grep -Fxq "$abs_path" "$REPOS_FILE"; then
        echo "Already tracked: $abs_path"
    else
        echo "$abs_path" >> "$REPOS_FILE"
        echo "ADDED: $abs_path"
    fi
done