#!/bin/bash
# Auto-update tokscale dashboard and push to GitHub
# Runs via macOS launchd on schedule (every 6 hours).
#
# This script orchestrates four phases:
#   1. Sync the local repo with origin/main (fast-forward, autostash).
#   2. Refresh README dashboard sections (tokscale + OSS contributions).
#   3. Submit new local usage to tokscale.ai through safe_submit.py
#      (per-(client, model) gated; preserves the reconstructed-claude-history
#      bucket).
#   4. Commit and push the README + floor + erosion ledger updates.
#
# Resilience:
#   - All steps log to .tokscale-update.log with timestamps.
#   - Push reject triggers ONE pull-rebase + push retry (handles race with
#     other machines updating the same README).
#   - Network failures (unable to resolve github.com) abort the cycle so the
#     next launchd tick retries from a clean state instead of accumulating
#     half-committed work.
#   - Floor file (tokscale_floor.json) and erosion ledger (erosion_ledger.json)
#     are committed alongside the README so server snapshots and ratchet state
#     stay in sync across machines.

set -uo pipefail

REPO_DIR="${TOKSCALE_REPO_DIR:-$HOME/Omofictions/shaun0927}"
LOG_FILE="$REPO_DIR/.tokscale-update.log"
PYTHON_BIN="${TOKSCALE_PYTHON:-python3}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

abort() {
  log "ABORT: $1"
  exit 1
}

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Repo not found at $REPO_DIR" >&2
  exit 1
fi

cd "$REPO_DIR"
log "=== auto_tokscale start (cwd=$REPO_DIR) ==="

# ---------- 1. Sync with origin/main (fast-forward, autostash) ----------
# `--autostash` puts any local uncommitted edits aside, fast-forwards, then
# pops them back. Avoids the "fetch first" loop the previous version was
# stuck in. We do NOT swallow failures here — if pull fails we abort so
# the next launchd tick starts clean.
log "phase 1: git pull --rebase --autostash origin main"
if ! git pull --rebase --autostash origin main >> "$LOG_FILE" 2>&1; then
  log "WARN: git pull failed (network or conflict); skipping rest of cycle"
  exit 0
fi

# ---------- 2. Refresh README dashboards ----------
log "phase 2a: update_tokscale.py (dashboard refresh + floor ratchet)"
if ! "$PYTHON_BIN" update_tokscale.py >> "$LOG_FILE" 2>&1; then
  log "WARN: update_tokscale.py failed; continuing without dashboard refresh"
fi

if command -v gh >/dev/null 2>&1 && [ -f update_oss_contributions.py ]; then
  log "phase 2b: update_oss_contributions.py"
  "$PYTHON_BIN" update_oss_contributions.py >> "$LOG_FILE" 2>&1 || \
    log "WARN: OSS contributions refresh failed; continuing"
else
  log "WARN: gh CLI not found or update_oss_contributions.py missing; skipping OSS refresh"
fi

# ---------- 3. Safe submit (per-(client, model) gated) ----------
# safe_submit.py:
#   - blocks if any real model would lose data above tolerance (unless
#     TOKSCALE_FORCE_LOSS=1 is set, which is intentional one-time override)
#   - excludes synthetic/recovery models (e.g. reconstructed-claude-history)
#     from the comparison so they never block real-model decisions
#   - writes a server snapshot to ./snapshots/ before each submission cycle
#   - records accepted losses to erosion_ledger.json
log "phase 3: safe_submit.py"
"$PYTHON_BIN" safe_submit.py >> "$LOG_FILE" 2>&1 || \
  log "WARN: safe_submit.py exited non-zero (a client submit failed)"

# Re-render the dashboard now that server has fresh data.
if [ "${TOKSCALE_RERENDER_AFTER_SUBMIT:-1}" = "1" ]; then
  log "phase 3b: update_tokscale.py (post-submit re-render)"
  "$PYTHON_BIN" update_tokscale.py >> "$LOG_FILE" 2>&1 || \
    log "WARN: post-submit re-render failed"
fi

# ---------- 4. Commit and push ----------
# Stage everything that the pipeline can touch. The repo's .gitignore is
# expected to keep secrets and personal logs out.
git add -- README.md tokscale_floor.json erosion_ledger.json snapshots/ 2>/dev/null || true

if git diff --cached --quiet; then
  log "phase 4: no staged changes, skipping commit"
  log "=== auto_tokscale end (no-op) ==="
  exit 0
fi

COMMIT_MSG="chore: auto-update tokscale dashboard ($(date '+%Y-%m-%d %H:%M'))"
git commit -m "$COMMIT_MSG" --quiet >> "$LOG_FILE" 2>&1 || abort "commit failed"
log "phase 4a: committed -> $COMMIT_MSG"

push_attempt() {
  git push --quiet origin main 2>> "$LOG_FILE"
}

if push_attempt; then
  log "phase 4b: push succeeded"
else
  log "phase 4b: push rejected; rebasing onto origin/main and retrying once"
  if git pull --rebase --autostash origin main >> "$LOG_FILE" 2>&1 \
     && push_attempt; then
    log "phase 4b: push retry succeeded"
  else
    log "ERROR: push retry failed; commits remain local. Resolve manually."
    git status -sb >> "$LOG_FILE" 2>&1
    exit 1
  fi
fi

log "=== auto_tokscale end (success) ==="
