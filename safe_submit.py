#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe wrapper around `tokscale submit`, gated per-client.

`tokscale submit` is merge/replace at the (client, model) tuple level: it
overwrites the server-side entry for whatever models the local CLI scan
currently sees, for the clients you ask it to submit. Because Claude Code
and Codex rotate their local session logs (~30 days), a naive auto-submit
across all clients can erase historical data the server already has, plus
clobber data submitted from *other* machines (e.g. a Hermes agent running
on a remote box that this machine has no logs for).

The original aggregate gate (local cost/tokens/messages >= server) had a
fatal flaw: once any single client has server-side history that local can
never reproduce — for example the `reconstructed-claude-history` recovery
bucket on the Claude account, ~14B tokens of recovered usage that no
longer exists in the rotated ~/.claude logs — the aggregate condition is
permanently unreachable, so *no* client's new usage ever reaches the
server. Codex / Gemini / Hermes growth gets silently dropped.

This rewrite gates per client and submits per client. Each client passes
its own three-metric check against the server's totals *for that client*,
and only that client is submitted (`tokscale submit -c <client>`), so a
stuck client never blocks the others.
"""

from __future__ import annotations

import codecs
import json
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

USERNAME = "shaun0927"

# Per-client safety margins. Submit only when local exceeds server by at
# least all of these — this prevents pathological cases (a tiny drift from
# server-side rebucketing, for example).
SAFETY_COST = 1.00          # USD
SAFETY_TOKENS = 1_000_000   # 1M tokens
SAFETY_MESSAGES = 50

# How long the CLI is allowed to scan local sessions. Big repos take a while.
SCAN_TIMEOUT = 180

# Clients to consider for per-client submit. These are the tokscale CLI's
# canonical client names (see `tokscale submit --help`). Hermes is included
# because it can in principle run on this machine too, but typically only
# the SSR will know about it (submitted from a remote box); in that case
# local will return zero entries and we skip submitting.
KNOWN_CLIENTS = ("claude", "codex", "gemini")


def log(msg: str) -> None:
    kst = timezone(timedelta(hours=9))
    print(f"[{datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')}] [safe_submit] {msg}")


def fetch_local_for_client(client: str) -> dict | None:
    """Return local cumulative totals for one client via `tokscale --json -c X`."""
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
    # Output may have a header preceding the JSON object.
    i = r.stdout.find("{")
    if i < 0:
        return None
    try:
        d = json.loads(r.stdout[i:])
    except json.JSONDecodeError as e:
        log(f"local JSON decode failed for client={client}: {e}")
        return None
    cost = float(d.get("totalCost", 0) or 0)
    tokens = (
        int(d.get("totalInput", 0) or 0)
        + int(d.get("totalOutput", 0) or 0)
        + int(d.get("totalCacheRead", 0) or 0)
        + int(d.get("totalCacheWrite", 0) or 0)
    )
    messages = int(d.get("totalMessages", 0) or 0)
    return {"cost": cost, "tokens": tokens, "messages": messages, "entries": len(d.get("entries", []))}


def fetch_server_by_client() -> dict[str, dict] | None:
    """Parse the public SSR payload and group cumulative totals by client.

    Each per-model entry on tokscale.ai is attributed to the nearest preceding
    `"client":"..."` marker in the SSR payload. We dedupe entries that appear
    multiple times (the payload repeats blocks for different views).
    """
    url = f"https://tokscale.ai/u/{USERNAME}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
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

    # The SSR breaks the dashboard down into many sub-views (per-day,
    # per-period, per-tab) and each (client, model) appears multiple times
    # with *partial* values that sum to the lifetime total. So we accumulate
    # every occurrence — do NOT dedupe by (client, model), or you'd get a
    # single partial slice instead of the cumulative.
    by_client: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "messages": 0})
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
        by_client[client]["cost"] += float(mm.group(2))
        by_client[client]["tokens"] += int(mm.group(5))
        by_client[client]["messages"] += int(mm.group(6))
    return dict(by_client)


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


def main() -> int:
    log("starting safe submit check (per-client gate)")
    server = fetch_server_by_client()
    if server is None:
        return 0
    log(f"server clients seen: {sorted(server.keys())}")

    submitted: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for client in KNOWN_CLIENTS:
        s = server.get(client, {"cost": 0.0, "tokens": 0, "messages": 0})
        local = fetch_local_for_client(client)
        if local is None or local["entries"] == 0:
            log(f"client={client} local has no entries -- skip")
            skipped.append(client)
            continue
        log(
            f"client={client} "
            f"local ${local['cost']:,.2f} / {local['tokens']:,} tok / {local['messages']:,} msg  vs  "
            f"server ${s['cost']:,.2f} / {s['tokens']:,} tok / {s['messages']:,} msg"
        )
        cost_ok = local["cost"] >= s["cost"] + SAFETY_COST
        tok_ok = local["tokens"] >= s["tokens"] + SAFETY_TOKENS
        msg_ok = local["messages"] >= s["messages"] + SAFETY_MESSAGES
        if not (cost_ok and tok_ok and msg_ok):
            reasons = []
            if not cost_ok:
                reasons.append(f"cost short by ${s['cost'] + SAFETY_COST - local['cost']:,.2f}")
            if not tok_ok:
                reasons.append(f"tokens short by {s['tokens'] + SAFETY_TOKENS - local['tokens']:,}")
            if not msg_ok:
                reasons.append(f"messages short by {s['messages'] + SAFETY_MESSAGES - local['messages']:,}")
            log(f"client={client} SKIP -- " + "; ".join(reasons))
            skipped.append(client)
            continue
        rc = submit_client(client)
        if rc == 0:
            submitted.append(client)
        else:
            failed.append(client)

    log(f"summary: submitted={submitted} skipped={skipped} failed={failed}")
    # Exit non-zero only if any submit attempt failed; skipped clients are
    # expected and shouldn't fail the caller.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
