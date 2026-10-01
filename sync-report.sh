#!/bin/bash

# Simple synchronization script for Overleaf and local report directory.

OVERLEAF_DIR="report/.overleaf"
REPORT_DIR="report"

# Check if .overleaf exists
if [ ! -d "$OVERLEAF_DIR" ]; then
    echo "=========================================================================="
    echo " Error: $OVERLEAF_DIR directory not found."
    echo " Please clone your Overleaf project first using:"
    echo "   git clone <your-overleaf-git-url> $OVERLEAF_DIR"
    echo "=========================================================================="
    exit 1
fi

case "$1" in
    push)
        echo "Syncing local '$REPORT_DIR/' to Overleaf..."
        
        # Copy everything except hidden files (like .git) and the .overleaf folder from report/ to report/.overleaf/
        rsync -av --exclude='.git*' --exclude='.overleaf*' "$REPORT_DIR/" "$OVERLEAF_DIR/"
        
        # Go to .overleaf, commit and push
        cd "$OVERLEAF_DIR" || exit 1
        git add -A
        
        # Prompt for a commit message or use a default one
        commit_msg="Update report: $(date)"
        if [ -n "$2" ]; then
            commit_msg="$2"
        fi
        
        git commit -m "$commit_msg"
        
        # Overleaf git default branch is usually master or main
        # Try pushing to whichever branch is active
        active_branch=$(git branch --show-current)
        echo "Pushing changes to Overleaf ($active_branch)..."
        git push origin "$active_branch"
        
        echo "Done! Local changes pushed to Overleaf."
        ;;
        
    pull)
        echo "Pulling latest changes from Overleaf..."
        
        # Go to .overleaf and pull
        cd "$OVERLEAF_DIR" || exit 1
        active_branch=$(git branch --show-current)
        git pull origin "$active_branch"
        
        # Go back and copy from report/.overleaf/ to report/
        cd - > /dev/null || exit 1
        echo "Syncing Overleaf changes back to local '$REPORT_DIR/'..."
        rsync -av --exclude='.git*' --exclude='.overleaf*' "$OVERLEAF_DIR/" "$REPORT_DIR/"
        
        echo "Done! Overleaf changes pulled and synced locally."
        ;;
        
    *)
        echo "Usage: ./sync-report.sh [pull|push]"
        echo "  pull  - Pulls changes from Overleaf and syncs them into your local 'report/' folder."
        echo "  push  - Syncs your local 'report/' folder into '.overleaf/' and pushes to Overleaf."
        exit 1
        ;;
esac
