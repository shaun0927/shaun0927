#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe wrapper around `tokscale submit`.

`tokscale submit` is merge/replace: it overwrites the server total with
whatever the local CLI scan currently sees. Because Claude Code and Codex
rotate their local session logs (~30 days), naive auto-submit can erase
historical data the server already has.

This wrapper:

1. Reads the local cumulative via `tokscale --json`.
2. Reads the server cumulative via the public SSR endpoint.
3. Submits ONLY when local meets-or-exceeds the server in all three
   key metrics (cost, tokens, messages) by a small safety margin.

Otherwise it refuses and exits 0 (no submit). Output is logged so the
operator can see exactly why a submit was skipped.
"""

from __future__ import annotations

import codecs
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

USERNAME = "shaun0927"

# Safety margins. Submit only when local exceeds server by at least all of
# these — this prevents pathological cases (a tiny drift from server-side
# rebucketing, for example).
SAFETY_COST = 1.00          # USD
SAFETY_TOKENS = 1_000_000   # 1M tokens
SAFETY_MESSAGES = 50

# How long the CLI is allowed to scan local sessions. Big repos take a while.
SCAN_TIMEOUT = 180


def log(msg: str) -> None:
    kst = timezone(timedelta(hours=9))
    print(f"[{datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')}] [safe_submit] {msg}")


def fetch_local() -> dict | None:
    try:
        r = subprocess.run(
            ["npx", "tokscale@latest", "--json"],
            capture_output=True, text=True, timeout=SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log("local scan timed out")
        return None
    if r.returncode != 0:
        log(f"local scan failed: {r.stderr.strip()[:200]}")
        return None
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("{"):
            return json.loads(r.stdout[r.stdout.index(s):])
    return None


def fetch_server() -> dict | None:
    """Extract cumulative server totals from the tokscale.ai SSR payload.

    The Next.js page emits the payload as escaped JSON inside
    `self.__next_f.push([1, "..."])` chunks; we have to concatenate and
    unicode-unescape them before regex matching. Same shape as
    update_tokscale.py:fetch_ssr_data uses.
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

    m = re.search(
        r'"totalTokens":(\d+),"totalCost":([0-9.]+),'
        r'"inputTokens":(\d+),"outputTokens":(\d+),'
        r'"cacheReadTokens":(\d+),"cacheWriteTokens":(\d+)',
        payload,
    )
    if not m:
        log("server totals not found in SSR payload")
        return None
    tokens = int(m.group(1))
    cost = float(m.group(2))
    # Per-model entries each carry their own "messages" key. The SSR payload
    # repeats this block in multiple structures (e.g. once per data view),
    # so we de-dupe by matching the full entry shape and only counting unique
    # spans. Matches the entry shape used by update_tokscale.py:fetch_ssr_data.
    entry_pat = re.compile(
        r'"[A-Za-z0-9._<>\-]+":\{"cost":[0-9.eE+\-]+,'
        r'"input":\d+,"output":\d+,'
        r'"tokens":\d+,"messages":(\d+),'
        r'"cacheRead":\d+,"reasoning":\d+,'
        r'"cacheWrite":\d+\}'
    )
    seen_spans: set[tuple[int, int]] = set()
    msg_total = 0
    for mm in entry_pat.finditer(payload):
        span = mm.span()
        if span in seen_spans:
            continue
        seen_spans.add(span)
        msg_total += int(mm.group(1))
    # The SSR exposes the same per-model entry block in multiple sibling
    # structures (totals view, breakdown view, ...), so divide by however
    # many copies appear. Detect via the totalCost block count.
    cost_blocks = len(re.findall(r'"totalCost":[0-9.]+', payload))
    if cost_blocks > 1 and msg_total % cost_blocks == 0:
        msg_total //= cost_blocks
    return {"cost": cost, "tokens": tokens, "messages": msg_total}


def main() -> int:
    log("starting safe submit check")
    local = fetch_local()
    if not local:
        return 0  # don't fail the caller; just skip
    local_cost = float(local.get("totalCost", 0))
    local_tok = (
        int(local.get("totalInput", 0))
        + int(local.get("totalOutput", 0))
        + int(local.get("totalCacheRead", 0))
        + int(local.get("totalCacheWrite", 0))
    )
    local_msg = int(local.get("totalMessages", 0))

    server = fetch_server()
    if not server:
        return 0
    s_cost, s_tok, s_msg = server["cost"], server["tokens"], server["messages"]

    log(
        f"local  ${local_cost:,.2f} / {local_tok:,} tok / {local_msg:,} msg"
    )
    log(
        f"server ${s_cost:,.2f} / {s_tok:,} tok / {s_msg:,} msg"
    )

    cost_ok = local_cost >= s_cost + SAFETY_COST
    tok_ok = local_tok >= s_tok + SAFETY_TOKENS
    msg_ok = local_msg >= s_msg + SAFETY_MESSAGES

    if not (cost_ok and tok_ok and msg_ok):
        reasons = []
        if not cost_ok:
            reasons.append(f"cost short by ${s_cost + SAFETY_COST - local_cost:,.2f}")
        if not tok_ok:
            reasons.append(f"tokens short by {s_tok + SAFETY_TOKENS - local_tok:,}")
        if not msg_ok:
            reasons.append(f"messages short by {s_msg + SAFETY_MESSAGES - local_msg:,}")
        log("SKIP submit -- " + "; ".join(reasons))
        log(
            "Local snapshot is smaller than what the server already knows. "
            "Submitting would replace the server total with this smaller snapshot."
        )
        return 0

    log("local exceeds server in cost, tokens, and messages -- submitting")
    r = subprocess.run(
        ["npx", "tokscale@latest", "submit"],
        capture_output=True, text=True, timeout=SCAN_TIMEOUT,
    )
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    log(f"submit exit code: {r.returncode}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
