#!/bin/bash
# Auto-update tokscale dashboard and push to GitHub
# Runs via macOS launchd on schedule

set -e

REPO_DIR="$HOME/shaun0927"
LOG_FILE="$REPO_DIR/.tokscale-update.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Ensure repo exists
if [ ! -d "$REPO_DIR/.git" ]; then
  log "ERROR: Repo not found at $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"

log "Starting tokscale dashboard update..."

# Pull latest
git pull --rebase --quiet 2>> "$LOG_FILE" || true

# Run updater
python3 update_tokscale.py >> "$LOG_FILE" 2>&1

# Submit to tokscale.ai as well
npx tokscale@latest submit >> "$LOG_FILE" 2>&1 || true

# Check for changes
if git diff --quiet README.md; then
  log "No changes detected, skipping commit"
  exit 0
fi

# Commit and push
git add README.md
git commit -m "chore: auto-update tokscale dashboard ($(date '+%Y-%m-%d %H:%M'))" --quiet
git push --quiet

log "Dashboard updated and pushed successfully"
