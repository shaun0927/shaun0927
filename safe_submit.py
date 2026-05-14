#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe wrapper around `tokscale submit` with per-(client, model) safety.

Why this exists
---------------
`tokscale submit` is REPLACE semantics at the CLIENT level. When called for a
client, the server-side rows for that client are overwritten with whatever
models the local CLI scan currently sees. Models present on the server but
absent locally (e.g. the synthetic `reconstructed-claude-history` recovery
bucket) ARE DESTROYED. This was demonstrated empirically on 2026-05-14 when a
single `submit -c claude` reduced reconstructed-claude-history from $12,455 to
$790 (~$11,665 of recovered usage erased irreversibly).

This script therefore:
  - Refuses to submit any client whose server bucket holds a synthetic or
    recovery model unless TOKSCALE_FORCE_SYNTHETIC_DELETE=1 is explicitly set
    AND the operator has already updated tokscale_floor.json to absorb the
    expected loss.
  - Computes per-(client, model) deltas across real (non-synthetic) entries,
    refuses submits that would erode any real model above tolerance unless
    TOKSCALE_FORCE_LOSS=1 is set.
  - Snapshots the full server per-(client, model) state to ./snapshots/
    before each submit attempt so historical state is never lost locally.

Two failure modes the previous gate did not handle:
  1. The aggregate gate (sum local cost/tokens/messages >= sum server) is
     permanently unreachable when the server holds a synthetic recovery model
     that local cannot reproduce. → no client ever submits.
  2. A per-client gate still fails when a single real model has eroded
     locally (Claude Code rotates 30+ days of session logs by default; even
     with `cleanupPeriodDays` extended, a model that is no longer in active
     use cannot grow on local but the server retains the higher historical
     value). → submitting the client would replace that model with a smaller
     value and silently lose data.

This implementation gates per (client, model) and logs every accepted/refused
delta, so the worst-case behavior is "miss new growth", never "delete recovery
data". The reconstructed-claude-history bucket is protected three ways:
  (a) it lives on the server only — submit never touches it;
  (b) any model whose name matches SYNTHETIC_PATTERNS is filtered out of the
      server-side comparison so it cannot block real-model decisions;
  (c) every submission writes a JSON snapshot of the server-side per-(client,
      model) state to ./snapshots/ before submitting, so a regression can be
      detected and a manual recovery is always possible.

Knobs
-----
- SAFETY_PER_MODEL_COST: per-model loss tolerance during a submit. If any
  real (non-synthetic) model on local would shrink the server entry by more
  than this, the client submit is blocked unless TOKSCALE_FORCE_LOSS=1.
- NET_GAIN_THRESHOLD_*: minimum net gain (across all real models) required
  to bother calling submit at all. Avoids clobbering the server with no-op
  replays.
- TOKSCALE_FORCE_LOSS: env override. When set to "1", per-model loss
  blocks become warnings. Use only after manually inspecting the snapshot
  and erosion log and deciding the loss is acceptable.

Outputs
-------
- snapshots/server-<UTC-iso>.json   server per-(client, model) snapshot
- erosion_ledger.json               cumulative known erosion per (client, model)
- stdout                            human-readable log lines (also routed to
                                    .tokscale-update.log by auto_tokscale.sh)
"""

from __future__ import annotations

import codecs
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

USERNAME = "shaun0927"
REPO_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = REPO_DIR / "snapshots"
EROSION_LEDGER = REPO_DIR / "erosion_ledger.json"

# Per-model safety margins. We block a client submit if any real model would
# shrink server data by more than these amounts; any positive growth above
# these amounts is what triggers the actual submit.
SAFETY_PER_MODEL_COST = 1.00          # USD; per-model loss tolerance
SAFETY_PER_MODEL_TOKENS = 5_000_000   # 5M tokens
SAFETY_PER_MODEL_MESSAGES = 50

# Aggregate gain across all real models needed to justify a submit cycle.
NET_GAIN_THRESHOLD_COST = 5.00        # USD
NET_GAIN_THRESHOLD_TOKENS = 10_000_000
NET_GAIN_THRESHOLD_MESSAGES = 100

SCAN_TIMEOUT = 240                    # local CLI scan budget
HTTP_TIMEOUT = 30

KNOWN_CLIENTS = ("claude", "codex", "gemini", "hermes")

# Server-side synthetic / recovery model entries that submit will never touch.
# These must be excluded from the comparison or no real model decision is
# possible. Pattern match is case-insensitive substring.
SYNTHETIC_PATTERNS = (
    "reconstructed-",
    "synthetic",
    "recovered-",
    "<synthetic>",
)

FORCE_LOSS = os.environ.get("TOKSCALE_FORCE_LOSS") == "1"
FORCE_SYNTHETIC_DELETE = os.environ.get("TOKSCALE_FORCE_SYNTHETIC_DELETE") == "1"


def now_kst() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{now_kst()}] [safe_submit] {msg}", flush=True)


def is_synthetic(model: str) -> bool:
    m = model.lower()
    return any(p in m for p in SYNTHETIC_PATTERNS)


# ---------------------------------------------------------------- local scan

def fetch_local_per_model(client: str) -> dict[str, dict] | None:
    """Return {model: {cost, tokens, messages}} for a client via the CLI."""
    try:
        r = subprocess.run(
            ["npx", "tokscale@latest", "--json", "-c", client],
            capture_output=True, text=True, timeout=SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log(f"local scan timed out for client={client}")
        return None
    if r.returncode != 0:
        log(f"local scan failed for client={client}: {r.stderr.strip()[:200]}")
        return None
    i = r.stdout.find("{")
    if i < 0:
        return None
    try:
        d = json.loads(r.stdout[i:])
    except json.JSONDecodeError as e:
        log(f"local JSON decode failed for client={client}: {e}")
        return None
    out: dict[str, dict] = {}
    for e in d.get("entries", []):
        model = e.get("model") or "?"
        if is_synthetic(model):
            continue
        tok = (
            int(e.get("input", 0) or 0)
            + int(e.get("output", 0) or 0)
            + int(e.get("cacheRead", 0) or 0)
            + int(e.get("cacheWrite", 0) or 0)
        )
        out[model] = {
            "cost": float(e.get("cost", 0) or 0),
            "tokens": tok,
            "messages": int(e.get("messageCount", 0) or 0),
        }
    return out


# --------------------------------------------------------------- server scan

def fetch_server_per_client_model() -> dict[str, dict[str, dict]] | None:
    """Return {client: {model: {cost, tokens, messages}}} from the public SSR.

    Each (client, model) appears multiple times in the SSR payload because the
    dashboard renders many sub-views; the per-occurrence values sum to the
    cumulative total, so we accumulate without dedup.
    """
    url = f"https://tokscale.ai/u/{USERNAME}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        log(f"server fetch failed: {e}")
        return None
    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)', html, re.DOTALL)
    if not pushes:
        log("server SSR payload not found")
        return None
    try:
        payload = codecs.decode("".join(pushes), "unicode_escape")
    except Exception as e:
        log(f"server SSR unescape failed: {e}")
        return None

    entry_pat = re.compile(
        r'"([A-Za-z0-9._<>\-]+)":\{"cost":([0-9.eE+\-]+),'
        r'"input":(\d+),"output":(\d+),'
        r'"tokens":(\d+),"messages":(\d+),'
        r'"cacheRead":(\d+),"reasoning":\d+,'
        r'"cacheWrite":(\d+)\}'
    )
    client_starts = [(m.start(), m.group(1)) for m in re.finditer(r'"client":"([^"]+)"', payload)]

    by_client: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"cost": 0.0, "tokens": 0, "messages": 0}
    ))
    for mm in entry_pat.finditer(payload):
        model = mm.group(1)
        if model == "<synthetic>":
            continue
        pos = mm.start()
        client = None
        for cs, cname in client_starts:
            if cs < pos:
                client = cname
            else:
                break
        if not client:
            continue
        by_client[client][model]["cost"] += float(mm.group(2))
        by_client[client][model]["tokens"] += int(mm.group(5))
        by_client[client][model]["messages"] += int(mm.group(6))
    # Convert to plain dicts for json.dump
    return {c: dict(m) for c, m in by_client.items()}


# ------------------------------------------------------------------ snapshot

def write_snapshot(server_state: dict) -> Path:
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = SNAPSHOT_DIR / f"server-{ts}.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(server_state, f, indent=2, ensure_ascii=False)
        f.write("\n")
    # Keep last 30 snapshots; older ones are pruned to keep repo light.
    snaps = sorted(SNAPSHOT_DIR.glob("server-*.json"))
    for old in snaps[:-30]:
        try:
            old.unlink()
        except OSError:
            pass
    return p


# -------------------------------------------------------------- erosion log

def load_erosion() -> dict:
    if not EROSION_LEDGER.exists():
        return {"_note": "Cumulative erosion of real models, recorded each time "
                          "a submit accepts a per-model loss. Reset by deleting "
                          "this file.", "by_client_model": {}}
    try:
        return json.loads(EROSION_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {"_note": "(reset due to parse error)", "by_client_model": {}}


def record_erosion(ledger: dict, client: str, model: str, delta_cost: float,
                   delta_tokens: int, delta_messages: int) -> None:
    bcm = ledger.setdefault("by_client_model", {})
    key = f"{client}:{model}"
    bucket = bcm.setdefault(key, {"cost": 0.0, "tokens": 0, "messages": 0,
                                   "first_seen": now_kst(), "events": 0})
    bucket["cost"] = round(bucket.get("cost", 0.0) + delta_cost, 2)
    bucket["tokens"] = bucket.get("tokens", 0) + delta_tokens
    bucket["messages"] = bucket.get("messages", 0) + delta_messages
    bucket["events"] = bucket.get("events", 0) + 1
    bucket["last_seen"] = now_kst()


def save_erosion(ledger: dict) -> None:
    ledger["_last_updated"] = now_kst()
    EROSION_LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")


# ---------------------------------------------------------------- submission

def submit_client(client: str) -> int:
    log(f"submitting client={client}")
    r = subprocess.run(
        ["npx", "tokscale@latest", "submit", "-c", client],
        capture_output=True, text=True, timeout=SCAN_TIMEOUT,
    )
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    log(f"submit exit code for client={client}: {r.returncode}")
    return r.returncode


# --------------------------------------------------------------- decision

def evaluate_client(client: str, server_models: dict, local_models: dict
                    ) -> tuple[bool, str, list[tuple[str, dict]]]:
    """Return (should_submit, reason, accepted_losses).

    `accepted_losses` is a list of (model, {cost, tokens, messages}) for
    real-model losses that the client submit will incur if it proceeds. These
    are recorded into the erosion ledger when the submit succeeds.
    """
    # Real (non-synthetic) server models only.
    server_real = {m: v for m, v in server_models.items() if not is_synthetic(m)}
    server_synthetic = {m: v for m, v in server_models.items() if is_synthetic(m)}

    # CRITICAL SAFETY GUARD: tokscale CLI's `submit -c <client>` was originally
    # documented (in safe_submit's earlier docstring) to operate at the
    # (client, model) tuple level — leaving server-only models untouched. The
    # 2026-05-14 incident demonstrated this is FALSE: submitting `claude`
    # destroyed ~94% of the `reconstructed-claude-history` server-only bucket
    # ($12,455 → $790, ~$11,665 erased). The CLI appears to wipe any
    # client-scope models that local does not have.
    #
    # Until tokscale ships a per-model submit (or an additive flag), the only
    # safe behavior when the server holds an irreplaceable synthetic/recovery
    # bucket is to NEVER submit that client. Override only if you understand
    # the loss and have a recovery plan: TOKSCALE_FORCE_SYNTHETIC_DELETE=1.
    if server_synthetic and not FORCE_SYNTHETIC_DELETE:
        names = ", ".join(f"{m} (${v['cost']:,.2f})" for m, v in server_synthetic.items())
        return (False,
                f"BLOCK -- server holds synthetic/recovery model(s) for this "
                f"client that the CLI submit will erase: {names}. "
                f"Set TOKSCALE_FORCE_SYNTHETIC_DELETE=1 ONLY if you accept the "
                f"loss and have updated tokscale_floor.json to absorb it.",
                [])

    # Models considered: union of local and server-real.
    all_models = sorted(set(server_real.keys()) | set(local_models.keys()))

    losses: list[tuple[str, dict]] = []   # would-decrease beyond tolerance
    soft_drift: list[tuple[str, dict]] = []  # within tolerance, ignored
    gains: list[tuple[str, dict]] = []

    net_cost = 0.0
    net_tokens = 0
    net_messages = 0

    for m in all_models:
        sv = server_real.get(m, {"cost": 0.0, "tokens": 0, "messages": 0})
        lv = local_models.get(m, {"cost": 0.0, "tokens": 0, "messages": 0})
        d_cost = lv["cost"] - sv["cost"]
        d_tok = lv["tokens"] - sv["tokens"]
        d_msg = lv["messages"] - sv["messages"]
        net_cost += d_cost
        net_tokens += d_tok
        net_messages += d_msg
        if d_cost > 0:
            gains.append((m, {"cost": d_cost, "tokens": d_tok, "messages": d_msg}))
        elif (-d_cost > SAFETY_PER_MODEL_COST
              or -d_tok > SAFETY_PER_MODEL_TOKENS
              or -d_msg > SAFETY_PER_MODEL_MESSAGES):
            losses.append((m, {"cost": -d_cost, "tokens": -d_tok, "messages": -d_msg}))
        elif d_cost < 0:
            soft_drift.append((m, {"cost": -d_cost, "tokens": -d_tok, "messages": -d_msg}))

    # 1) Block if any real model would lose meaningful data.
    if losses and not FORCE_LOSS:
        details = "; ".join(
            f"{m} -${v['cost']:,.2f}/-{v['tokens']:,}tok/-{v['messages']:,}msg"
            for m, v in losses
        )
        return (False,
                f"BLOCK -- per-model loss above tolerance: {details}. "
                f"Set TOKSCALE_FORCE_LOSS=1 to accept (one-time).",
                losses)

    if losses and FORCE_LOSS:
        log(f"client={client} FORCE_LOSS=1 — accepting per-model losses: "
            + "; ".join(f"{m} -${v['cost']:,.2f}" for m, v in losses))

    # 2) Require meaningful gain to justify the submit.
    if (net_cost < NET_GAIN_THRESHOLD_COST
        and net_tokens < NET_GAIN_THRESHOLD_TOKENS
        and net_messages < NET_GAIN_THRESHOLD_MESSAGES):
        return (False,
                f"SKIP -- net gain below threshold: "
                f"+${net_cost:,.2f}/{net_tokens:+,}tok/{net_messages:+,}msg",
                [])

    # 3) Approve. Soft drifts (within tolerance) are also recorded into erosion
    #    ledger because they DO reduce the server entry on submit.
    accepted_losses = losses + soft_drift
    return (True,
            f"OK -- net +${net_cost:,.2f}/+{net_tokens:,}tok/+{net_messages:,}msg "
            f"across {len(gains)} growing models; accepting "
            f"{len(accepted_losses)} model losses",
            accepted_losses)


def main() -> int:
    log("starting safe submit (per-(client, model) gate)")
    server = fetch_server_per_client_model()
    if server is None:
        log("server snapshot unavailable, aborting")
        return 1

    snap_path = write_snapshot(server)
    log(f"server snapshot written: {snap_path.relative_to(REPO_DIR)}")
    log(f"server clients seen: {sorted(server.keys())}")

    ledger = load_erosion()
    submitted: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for client in KNOWN_CLIENTS:
        server_models = server.get(client, {})
        local_models = fetch_local_per_model(client)
        if local_models is None or not local_models:
            log(f"client={client} local has no real-model entries -- skip")
            skipped.append(client)
            continue

        # Surface counts for visibility.
        log(f"client={client} local has {len(local_models)} models, "
            f"server has {len(server_models)} models "
            f"({sum(1 for m in server_models if is_synthetic(m))} synthetic)")

        ok, reason, accepted_losses = evaluate_client(client, server_models, local_models)
        log(f"client={client} {reason}")
        if not ok:
            skipped.append(client)
            continue

        rc = submit_client(client)
        if rc == 0:
            submitted.append(client)
            for m, loss in accepted_losses:
                record_erosion(ledger, client, m, loss["cost"], loss["tokens"], loss["messages"])
        else:
            failed.append(client)

    if submitted:
        save_erosion(ledger)
        log(f"erosion ledger updated: {EROSION_LEDGER.name}")

    log(f"summary: submitted={submitted} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
