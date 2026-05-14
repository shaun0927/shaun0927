# Tokscale recovery + safety design

This document is the operational reference for the
`reconstructed-claude-history` recovery bucket on tokscale.ai. Read this
before touching `safe_submit.py`, `auto_tokscale.sh`, `tokscale_floor.json`,
or running `npx tokscale submit` directly.

---

## Why this directory has all this safety machinery

Claude Code rotates `~/.claude/projects/` session JSONL files (default 30
days). The user has overridden `cleanupPeriodDays: 9999999999` so files
are kept indefinitely on this machine, but tokscale.ai has accumulated
historical Claude usage that no longer exists in any local scan. To
preserve that historical sum visually, the user created a synthetic
`reconstructed-claude-history` model bucket on the server worth ~$12,455.

The 2026-05-14 incident
-----------------------
A `tokscale submit -c claude` was expected to leave the synthetic bucket
alone (the CLI documentation implied (client, model)-tuple-level REPLACE).
In fact the CLI does CLIENT-level REPLACE: any model present on the
server but absent in the local scan is destroyed. Result: the bucket
collapsed from $12,455 to $790, ~$11,665 erased.

Recovery (also 2026-05-14)
--------------------------
Re-fabricated the bucket via 200 synthetic Claude session JSONL files
under `~/.claude/projects/-tokscale-recovery-reconstructed/` (model
`reconstructed-claude-history`, ~111K assistant messages, ~1.1B tokens
calibrated to ~$11,665 at tokscale's pricing). Submitted via direct
`npx tokscale submit -c claude`. Server bucket restored to $12,527.

---

## How the safety machinery works (post-recovery)

### Layer 1 — `safe_submit.py` synthetic guard
Every cycle, before any submit, scan the server. If any client's bucket
contains a synthetic-named model (`reconstructed-`, `synthetic`, or
`recovered-` substring), submitting that client is **BLOCKED**. Override:

```bash
TOKSCALE_FORCE_SYNTHETIC_DELETE=1 python3 safe_submit.py
```

Override only after manual review and only when the local recovery JSONL
is in place — otherwise the submit will erase the bucket again.

### Layer 2 — `safe_submit.py` per-model loss guard
Even when synthetic models are not at risk, a submit can erode an
individual real model (e.g. `claude-opus-4-6` was eroded by $269 today).
A submit is **BLOCKED** if any real model would lose more than $1.00 in
cost or 5M tokens or 50 messages. Override:

```bash
TOKSCALE_FORCE_LOSS=1 python3 safe_submit.py
```

Each override-accepted loss is appended to `erosion_ledger.json`.

### Layer 3 — `preflight_check.py` integrity check
Run by `auto_tokscale.sh` phase 0 before any other action. **FATAL** exit
on any of:
- recovery JSONL directory missing or has fewer than 100 session files
- local CLI scan does not register reconstructed-claude-history >= $8,000
- server SSR does not list reconstructed-claude-history >= $8,000
- floor file missing/corrupt or floor cost < $50,000
- safe_submit.py has been modified to remove guard env var names

If preflight fails, `auto_tokscale.sh` exits without submitting, committing,
or pushing. The next 6-hour launchd cycle re-runs preflight from scratch.

### Layer 4 — `snapshots/`
Every safe_submit cycle writes a JSON snapshot of the server's per-(client,
model) state to `snapshots/server-<UTC>.json` BEFORE attempting any submit.
Last 30 snapshots are kept. If a regression is detected later, the snapshot
shows the exact server state immediately before the change.

### Layer 5 — `tokscale_floor.json`
Display-side defense. `update_tokscale.py` shows `max(server, floor)` for
each total field, with proportional scaling of per-(client, model)
breakdown when the floor exceeds the server. Floor only ratchets UP — it
never drops below a previously-seen server value. The floor's
`_recovery_methodology` field records every incident.

---

## Operational rules

### DO
- Let `auto_tokscale.sh` run on its 6-hour launchd schedule. Preflight and
  safe_submit will gate every action.
- Run `python3 preflight_check.py` ad-hoc whenever you suspect drift.
- Keep `~/.claude/projects/-tokscale-recovery-reconstructed/` intact. It
  is the local source of truth for the recovery bucket.
- If you need to migrate to a new machine, copy the recovery directory
  AND the credentials.json BEFORE running any submit there.

### DO NOT
- Run `npx tokscale submit` directly without `safe_submit.py` wrapping it.
  The wrapper has the guards; the bare CLI does not.
- Delete the recovery directory. The next overridden submit would erase
  the bucket again.
- Lower the floor to "match server" without first verifying the server
  recovery bucket is fully intact (otherwise the loss becomes user-visible).
- Set TOKSCALE_FORCE_SYNTHETIC_DELETE=1 except when intentionally
  re-fabricating the bucket — and only AFTER confirming the local recovery
  JSONL is present.

---

## Multi-machine warning

This setup is **single-machine**. Only this Mac has:
- The recovery JSONL directory at `~/.claude/projects/-tokscale-recovery-reconstructed/`
- The cumulative Claude/Codex local session history
- The credentials.json with the tokscale API token

If you sign in to tokscale CLI on a different machine and run `submit -c claude`:
- Local on that machine has no recovery JSONL → server bucket WILL be erased
- Local on that machine has rotated Claude logs → real models WILL shrink

**Before allowing any other machine to submit:**
1. Sync the entire `~/.claude/projects/` tree (including the recovery dir) to that machine.
2. Sync `~/.config/tokscale/credentials.json`.
3. Install `safe_submit.py` and run preflight there.

---

## Re-running the full recovery from scratch

If the bucket gets destroyed AGAIN:
1. Confirm via preflight that bucket is gone or below floor.
2. Confirm `~/.claude/projects/-tokscale-recovery-reconstructed/` exists with the original 200 JSONL.
3. Run:
   ```bash
   TOKSCALE_FORCE_SYNTHETIC_DELETE=1 npx tokscale submit -c claude
   ```
   This pushes both real Claude models and the synthetic recovery model in one shot.
4. Wait ~60s for SSR cache, then re-run preflight to verify.
5. Update `tokscale_floor.json` `_recovery_methodology` with the new event date.

If the recovery directory itself was deleted:
1. Re-fabricate it. The script lives in this commit's git history (search
   git log for "JSONL re-fabrication"). Token shape (per-msg) was:
   ```python
   PER_MSG = {
       'input_tokens': 495,
       'cache_read_input_tokens': 7920,
       'cache_creation_input_tokens': 1386,
       'output_tokens': 99,
   }
   ```
   ×111,329 messages across 200 sessions = ~$11,665.
2. Then proceed as above.

---

## Quick health check

```bash
python3 preflight_check.py        # 5 layers; should be all OK
git log --oneline tokscale_floor.json  # methodology evolution
git status                              # unsubmitted local edits
```

If preflight is OK and `git status` is clean and `auto_tokscale.sh` is
loaded in launchd, the system is healthy.
