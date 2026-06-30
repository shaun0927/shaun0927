#!/bin/bash
# Auto-update tokscale dashboard and push to GitHub
# Runs via macOS launchd on schedule (twice daily).
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

# ---------- 0. Preflight integrity check ----------
# Verifies the recovery JSONL directory, server-side recovery bucket, and
# safe_submit guard variables are all in their expected post-2026-05-14
# state. If anything looks regressed, abort the cycle WITHOUT touching the
# server so a human can investigate. The 2026-05-14 incident showed how a
# single bad submit can erase $11K of recovery data — preflight is the
# cheapest insurance against a repeat.
log "phase 0: preflight_check.py"
if ! "$PYTHON_BIN" preflight_check.py >> "$LOG_FILE" 2>&1; then
  log "FATAL: preflight failed; ABORT (no submit, no commit, no push)."
  log "       Investigate $LOG_FILE then re-run after fixing."
  exit 1
fi

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
if ! TOKSCALE_SOURCE=ssr "$PYTHON_BIN" update_tokscale.py >> "$LOG_FILE" 2>&1; then
  log "WARN: update_tokscale.py failed; continuing without dashboard refresh"
fi

if command -v gh >/dev/null 2>&1 && [ -f update_oss_contributions.py ]; then
  log "phase 2b: update_oss_contributions.py"
  "$PYTHON_BIN" update_oss_contributions.py >> "$LOG_FILE" 2>&1 || \
    log "WARN: OSS contributions refresh failed; continuing"
else
  log "WARN: gh CLI not found or update_oss_contributions.py missing; skipping OSS refresh"
fi

# ---------- 3. Incremental date-windowed submit ----------
# CHANGED 2026-06-14: switched from full-client replace (safe_submit.py) to a
# trailing date-window submit.
#
# WHY: `tokscale submit -c <client>` with NO date filter sends the FULL local
# scan. Local session logs rotate (e.g. ~/.codex/sessions holds data only from
# 2026-05-30 onward while the server accumulates back to 2026-01-26), so the
# local aggregate is permanently far below the server aggregate. safe_submit.py
# compared all-time local-vs-server totals and therefore BLOCKED every codex
# submit ("per-model loss above tolerance"), stalling all new usage from
# 2026-06-13 until a manual backfill on 2026-06-14.
#
# WHY THIS IS SAFE: the tokscale server merges per (device, day, client) with a
# server-side regression guard (mergeClientBreakdownsWithRegressionGuard). A
# resubmit can only GROW a given (device, day, client) cell, never shrink it,
# and any day/client absent from the payload is preserved untouched. Submitting
# a bounded trailing window is therefore idempotent and cannot erode history; the
# reconstructed-claude-history recovery bucket lives on historical recovery days
# outside normal Codex rotation windows. safe_submit.py is retained for manual/full audits,
# but is no longer the scheduled path.
#
# Default to a 28-day trailing window: safely inside Codex/Claude 30-day local
# retention while still wide enough to survive vacations/offline periods.
# Override TOKSCALE_SUBMIT_SINCE for one-time wider backfills.
SUBMIT_SINCE="${TOKSCALE_SUBMIT_SINCE:-$(date -v-28d +%Y-%m-%d)}"
log "phase 3: windowed submit (--since $SUBMIT_SINCE, per client)"
# Best-effort pre-submit audit snapshot of server state.
curl -fsS "https://tokscale.ai/api/users/shaun0927" \
  -o "snapshots/server-$(date -u +%Y%m%dT%H%M%SZ).json" 2>/dev/null \
  || log "WARN: could not write pre-submit server snapshot"
for client in codex claude gemini hermes gjc micode; do
  if npx -y tokscale@latest submit -c "$client" --since "$SUBMIT_SINCE" >> "$LOG_FILE" 2>&1; then
    log "phase 3: submitted $client (--since $SUBMIT_SINCE)"
  else
    log "WARN: submit failed for client=$client"
  fi
done

# Re-render the dashboard now that server has fresh data.
if [ "${TOKSCALE_RERENDER_AFTER_SUBMIT:-1}" = "1" ]; then
  log "phase 3b: update_tokscale.py (post-submit re-render)"
  TOKSCALE_SOURCE=ssr "$PYTHON_BIN" update_tokscale.py >> "$LOG_FILE" 2>&1 || \
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
