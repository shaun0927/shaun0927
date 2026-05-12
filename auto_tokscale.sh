#!/bin/bash
# Auto-update tokscale dashboard and push to GitHub
# Runs via macOS launchd on schedule

set -e

REPO_DIR="${TOKSCALE_REPO_DIR:-$HOME/shaun0927}"
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

# Refresh AI Coding Agent Usage dashboard (uses tokscale_floor.json to prevent
# regressions when tokscale.ai server data shrinks due to local log rotation).
python3 update_tokscale.py >> "$LOG_FILE" 2>&1

# Refresh Open Source Contributions section (PR & star counts via gh CLI).
if command -v gh >/dev/null 2>&1 && [ -f update_oss_contributions.py ]; then
  python3 update_oss_contributions.py >> "$LOG_FILE" 2>&1 || true
else
  log "WARN: gh CLI not found or update_oss_contributions.py missing; skipping OSS refresh"
fi

# Do NOT submit local snapshots automatically. Claude Code may have cleaned old logs,
# and tokscale submit is merge/replace, so auto-submit can erase reconstructed history.
# Server/profile refresh should only read tokscale.ai state here.
# npx tokscale@latest submit >> "$LOG_FILE" 2>&1 || true

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
