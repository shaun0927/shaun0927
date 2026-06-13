#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tokscale Dashboard Updater
Fetches token usage data via tokscale CLI + profile scraping,
then updates README.md with a visual dashboard section.
"""

import codecs
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta


# Server-side synthetic buckets that should be folded into a canonical model.
# `reconstructed-claude-history` is the tokscale.ai-side recovery bucket for
# pre-erosion Claude usage (see tokscale_floor.json `_recovery_methodology`);
# attribute it to the most recent Opus generation it actually represents.
MODEL_RENAME = {
    "reconstructed-claude-history": "claude-opus-4-7",
}


def extract_json_object_after(text, marker):
    """Return JSON object following marker by balanced-brace scan."""
    idx = text.find(marker)
    if idx < 0:
        return None
    start = text.find("{", idx + len(marker))
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for pos in range(start, len(text)):
        ch = text[pos]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos + 1]
    return None


def fetch_tokscale_data():
    """Run tokscale CLI and return JSON data."""
    print("[INFO] Fetching tokscale CLI data...")
    try:
        result = subprocess.run(
            ["npx", "tokscale@latest", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"[ERROR] tokscale failed: {result.stderr}")
            return None
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("{"):
                json_start = result.stdout.index(line)
                return json.loads(result.stdout[json_start:])
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print("[ERROR] tokscale timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return None


def fetch_ssr_data(username="shaun0927"):
    """Rebuild CLI-shaped data from tokscale.ai profile SSR payload.

    Used when the local tokscale CLI has no session logs (e.g. CI runners).
    """
    print(f"[INFO] Fetching SSR data for @{username}...")
    url = f"https://tokscale.ai/u/{username}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to fetch profile page: {e}")
        return None

    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)', html, re.DOTALL)
    if not pushes:
        print("[ERROR] No SSR payload found")
        return None
    try:
        payload = codecs.decode("".join(pushes), "unicode_escape")
    except Exception as e:
        print(f"[ERROR] Unescape failed: {e}")
        return None

    # Preferred path: parse Next.js initialData exactly. The profile payload
    # contains both top-level modelUsage and per-day contribution data. Regexing
    # every model-shaped object double-counts after submissions because the same
    # model appears in summary and daily sections. Contributions are the
    # authoritative per-client/per-model breakdown; stats is authoritative for
    # top-level totals used by leaderboard.
    initial_json = extract_json_object_after(payload, '"initialData":')
    if initial_json:
        try:
            initial = json.loads(initial_json)
            entries_by_key = {}
            for day in initial.get("contributions", []) or []:
                for client_info in day.get("clients", []) or []:
                    client = client_info.get("client")
                    for model, values in (client_info.get("models") or {}).items():
                        model = MODEL_RENAME.get(model, model)
                        key = (client, model)
                        bucket = entries_by_key.setdefault(key, {
                            "client": client,
                            "model": model,
                            "cost": 0.0,
                            "input": 0,
                            "output": 0,
                            "messageCount": 0,
                            "cacheRead": 0,
                            "cacheWrite": 0,
                        })
                        bucket["cost"] += float(values.get("cost", 0) or 0)
                        bucket["input"] += int(values.get("input", 0) or 0)
                        bucket["output"] += int(values.get("output", 0) or 0)
                        bucket["messageCount"] += int(values.get("messages", 0) or 0)
                        bucket["cacheRead"] += int(values.get("cacheRead", 0) or 0)
                        bucket["cacheWrite"] += int(values.get("cacheWrite", 0) or 0)
            entries = list(entries_by_key.values())
            stats = initial.get("stats") or {}
            total_messages = sum(e["messageCount"] for e in entries)
            print(f"[INFO] SSR entries: {len(entries)}, messages: {total_messages}")
            return {
                "entries": entries,
                "totalCost": float(stats.get("totalCost", 0) or 0),
                "totalMessages": total_messages,
                "totalInput": int(stats.get("inputTokens", 0) or 0),
                "totalOutput": int(stats.get("outputTokens", 0) or 0),
                "totalCacheRead": int(stats.get("cacheReadTokens", 0) or 0),
                "totalCacheWrite": int(stats.get("cacheWriteTokens", 0) or 0),
            }
        except Exception as e:
            print(f"[WARN] initialData parse failed, falling back to regex: {e}")

    # Locate the profile totals block
    m = re.search(
        r'"totalTokens":(\d+),"totalCost":([0-9.]+),'
        r'"inputTokens":(\d+),"outputTokens":(\d+),'
        r'"cacheReadTokens":(\d+),"cacheWriteTokens":(\d+)',
        payload,
    )
    if not m:
        print("[ERROR] SSR totals not found")
        return None
    total_cost = float(m.group(2))
    total_input = int(m.group(3))
    total_output = int(m.group(4))
    total_cache_read = int(m.group(5))
    total_cache_write = int(m.group(6))

    # Walk each per-model record directly. Each model entry carries its own
    # "cost"/"input"/"output"/"tokens"/"messages"/"cacheRead"/"reasoning"/"cacheWrite".
    # We attribute each model to the nearest preceding "client":"..." marker.
    entries = []
    total_messages = 0
    model_pat = re.compile(
        r'"([A-Za-z0-9._<>\-]+)":\{"cost":([0-9.eE+-]+),'
        r'"input":(\d+),"output":(\d+),'
        r'"tokens":\d+,"messages":(\d+),'
        r'"cacheRead":(\d+),"reasoning":\d+,'
        r'"cacheWrite":(\d+)\}'
    )
    client_starts = [(m.start(), m.group(1)) for m in re.finditer(r'"client":"([^"]+)"', payload)]
    for mm in model_pat.finditer(payload):
        model = mm.group(1)
        if model in ("<synthetic>",):
            continue
        model = MODEL_RENAME.get(model, model)
        pos = mm.start()
        # find the nearest client marker before this model entry
        client = None
        for cs, cname in client_starts:
            if cs < pos:
                client = cname
            else:
                break
        if not client:
            continue
        msg = int(mm.group(5))
        total_messages += msg
        entries.append({
            "client": client,
            "model": model,
            "cost": float(mm.group(2)),
            "input": int(mm.group(3)),
            "output": int(mm.group(4)),
            "messageCount": msg,
            "cacheRead": int(mm.group(6)),
            "cacheWrite": int(mm.group(7)),
        })

    if not entries:
        print("[ERROR] SSR parsed zero entries")
        return None

    print(f"[INFO] SSR entries: {len(entries)}, messages: {total_messages}")
    return {
        "entries": entries,
        "totalCost": total_cost,
        "totalMessages": total_messages,
        "totalInput": total_input,
        "totalOutput": total_output,
        "totalCacheRead": total_cache_read,
        "totalCacheWrite": total_cache_write,
    }


def fetch_profile_data(username="shaun0927"):
    """Scrape tokscale.ai profile page for rank and stats."""
    print(f"[INFO] Fetching profile data for @{username}...")
    url = f"https://tokscale.ai/u/{username}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"[WARN] Failed to fetch profile page: {e}")
        return {}

    profile = {}

    # 1) Extract from escaped JSON payload (Next.js SSR data)
    # User object: rank
    m = re.search(r'rank\\?":\s*(\d+)', html)
    if m:
        profile["rank"] = int(m.group(1))

    # Stats object: activeDays
    m = re.search(r'activeDays\\?":\s*(\d+)', html)
    if m:
        profile["active_days"] = int(m.group(1))

    # Date range from JSON
    m = re.search(r'dateRange\\?":\{\\?"start\\?":\\?"(\d{4}-\d{2}-\d{2})\\?",\\?"end\\?":\\?"(\d{4}-\d{2}-\d{2})', html)
    if m:
        profile["date_start"] = m.group(1)
        profile["date_end"] = m.group(2)

    # 2) Extract from rendered HTML (StatsPanel components)
    # Streak: "Streak</div>...<value>66 days</value>"
    m = re.search(r'Streak</div>.*?StatItemValue[^>]*>(\d+)\s*days', html, re.DOTALL)
    if m:
        profile["streak"] = int(m.group(1))

    # Best Day date and cost
    m = re.search(r'Best Day</div>.*?StatItemValue[^>]*>([^<]+)</div>.*?StatItemSubValue[^>]*>\$([0-9,.K]+)', html, re.DOTALL)
    if m:
        profile["best_day_date"] = m.group(1).strip()
        val = m.group(2).replace(",", "")
        if val.endswith("K"):
            profile["best_day_cost"] = float(val[:-1]) * 1000
        else:
            profile["best_day_cost"] = float(val)

    # Average daily cost (tokscale page label is "Avg / Day" or "Avg Daily" depending on version)
    m = re.search(r'Avg[^<]*(?:Daily|/\s*Day)[^<]*</div>.*?StatItemValue[^>]*>\$([0-9,.]+)', html, re.DOTALL)
    if m:
        profile["avg_daily_cost"] = float(m.group(1).replace(",", ""))

    # Active Days from rendered HTML
    m = re.search(r'Active Days</div>.*?StatItemValue[^>]*>(\d+)', html, re.DOTALL)
    if m:
        profile["active_days"] = int(m.group(1))

    # 3) Fetch total users from leaderboard
    try:
        lb_req = urllib.request.Request(
            "https://tokscale.ai/leaderboard",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(lb_req, timeout=15) as resp:
            lb_html = resp.read().decode("utf-8")
        # Try JSON payload first (Next.js SSR), then fall back to rendered text.
        m = re.search(r'totalUsers\\?":\s*(\d+)', lb_html)
        if not m:
            m = re.search(r'(\d+)\s*(?:total\s*)?[Uu]sers', lb_html)
        if m:
            profile["total_users"] = int(m.group(1))
    except Exception:
        pass

    print(f"[INFO] Profile data: {profile}")
    return profile


FLOOR_PATH = "tokscale_floor.json"

ENTRY_FIELDS = ("cost", "messageCount", "input", "output", "cacheRead", "cacheWrite")


def entry_key(entry):
    """Stable identity for the unit tokscale can regress: (client, model)."""
    return (entry.get("client") or "unknown", entry.get("model") or "unknown")


def aggregate_entries(entries):
    """Collapse possibly repeated SSR/CLI rows into one row per (client, model)."""
    by_key = {}
    for entry in entries or []:
        client, model = entry_key(entry)
        bucket = by_key.setdefault(
            (client, model),
            {
                "client": client,
                "model": model,
                "cost": 0.0,
                "messageCount": 0,
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
            },
        )
        bucket["cost"] += float(entry.get("cost", 0) or 0)
        bucket["messageCount"] += int(entry.get("messageCount", 0) or 0)
        bucket["input"] += int(entry.get("input", 0) or 0)
        bucket["output"] += int(entry.get("output", 0) or 0)
        bucket["cacheRead"] += int(entry.get("cacheRead", 0) or 0)
        bucket["cacheWrite"] += int(entry.get("cacheWrite", 0) or 0)
    return by_key


def recompute_totals_from_entries(data):
    """Make top-level totals exactly match the current entry list."""
    entries = data.get("entries", [])
    data["totalCost"] = sum(float(e.get("cost", 0) or 0) for e in entries)
    data["totalMessages"] = sum(int(e.get("messageCount", 0) or 0) for e in entries)
    data["totalInput"] = sum(int(e.get("input", 0) or 0) for e in entries)
    data["totalOutput"] = sum(int(e.get("output", 0) or 0) for e in entries)
    data["totalCacheRead"] = sum(int(e.get("cacheRead", 0) or 0) for e in entries)
    data["totalCacheWrite"] = sum(int(e.get("cacheWrite", 0) or 0) for e in entries)
    return data


def merge_data_by_client_model(local_data, server_data):
    """Merge local CLI and tokscale.ai SSR data with no per-model decrease.

    tokscale submit currently behaves like a client-level REPLACE. That means a
    local rescan can shrink an old model (for example gpt-5.4) while a currently
    active model (for example gpt-5.5) grows. For dashboard display, preserve the
    maximum observed value per (client, model, metric) across local and server.
    """
    if not server_data:
        local_data["entries"] = list(aggregate_entries(local_data.get("entries", [])).values())
        return recompute_totals_from_entries(local_data)

    local_entries = aggregate_entries(local_data.get("entries", []))
    server_entries = aggregate_entries(server_data.get("entries", []))
    merged = {}
    merge_sources = {"local": 0, "server": 0, "mixed": 0}

    for key in sorted(set(local_entries) | set(server_entries)):
        local = local_entries.get(key, {})
        server = server_entries.get(key, {})
        client, model = key
        out = {"client": client, "model": model}
        sources = set()
        for field in ENTRY_FIELDS:
            local_value = local.get(field, 0) or 0
            server_value = server.get(field, 0) or 0
            if server_value > local_value:
                out[field] = server_value
                sources.add("server")
            else:
                out[field] = local_value
                sources.add("local")
        merged[key] = out
        if sources == {"local"}:
            merge_sources["local"] += 1
        elif sources == {"server"}:
            merge_sources["server"] += 1
        else:
            merge_sources["mixed"] += 1

    local_data["entries"] = list(merged.values())
    recompute_totals_from_entries(local_data)
    local_data["_client_model_merge"] = merge_sources
    print(
        "[INFO] Merged local+server per (client,model) max: "
        f"{merge_sources['local']} local, {merge_sources['server']} server, "
        f"{merge_sources['mixed']} mixed"
    )
    return local_data


def load_floor():
    """Load the floor (ratchet) values used to prevent display regression
    when tokscale.ai server data shrinks because Claude Code/Codex local logs
    have been rotated."""
    if not os.path.exists(FLOOR_PATH):
        return None
    try:
        with open(FLOOR_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {FLOOR_PATH}: {e}")
        return None


def save_floor(floor):
    """Persist the updated floor file."""
    if not floor:
        return
    kst = timezone(timedelta(hours=9))
    floor["last_updated"] = datetime.now(kst).strftime("%Y-%m-%d")
    with open(FLOOR_PATH, "w", encoding="utf-8") as f:
        json.dump(floor, f, indent=2, ensure_ascii=False)
        f.write("\n")


def apply_floor(data, profile, floor):
    """Ratchet at the same granularity tokscale can regress: client + model.

    The old fallback scaled every entry proportionally when the global floor was
    higher than the current scan. That made totals monotonic but obscured the
    real issue: one old model can shrink while another active model grows.

    New behavior:
      1. aggregate current data to one row per (client, model);
      2. ratchet floor["by_client_model"][client][model] field-by-field;
      3. render from the ratcheted model rows.

    This keeps gpt-5.4's historical maximum while still accepting new gpt-5.5
    growth, without inventing proportional usage across unrelated models.
    """
    if not floor:
        return floor

    if os.environ.get("TOKSCALE_RESET_FLOOR_FROM_SERVER") == "1":
        print("[INFO] Resetting tokscale floor from current server/local merged data")
        floor["by_client_model"] = {}
        floor["totals"] = {}

    ft = floor.setdefault("totals", {})
    by_client_model = floor.setdefault("by_client_model", {})

    current = aggregate_entries(data.get("entries", []))
    changed_models = []
    for (client, model), entry in current.items():
        client_bucket = by_client_model.setdefault(client, {})
        model_floor = client_bucket.setdefault(
            model,
            {
                "cost": 0.0,
                "messageCount": 0,
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "first_seen": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
            },
        )
        touched = False
        for field in ENTRY_FIELDS:
            old = model_floor.get(field, 0) or 0
            new = entry.get(field, 0) or 0
            if new > old:
                model_floor[field] = new
                touched = True
        if touched:
            model_floor["last_seen"] = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
            changed_models.append(f"{client}:{model}")

    ratcheted_entries = []
    for client, models in sorted(by_client_model.items()):
        if not isinstance(models, dict):
            continue
        for model, values in sorted(models.items()):
            if not isinstance(values, dict):
                continue
            ratcheted_entries.append({
                "client": client,
                "model": model,
                "cost": float(values.get("cost", 0) or 0),
                "messageCount": int(values.get("messageCount", 0) or 0),
                "input": int(values.get("input", 0) or 0),
                "output": int(values.get("output", 0) or 0),
                "cacheRead": int(values.get("cacheRead", 0) or 0),
                "cacheWrite": int(values.get("cacheWrite", 0) or 0),
            })

    data["entries"] = ratcheted_entries
    recompute_totals_from_entries(data)

    cur_cost = data.get("totalCost", 0.0)
    cur_msg = data.get("totalMessages", 0)
    cur_in = data.get("totalInput", 0)
    cur_out = data.get("totalOutput", 0)
    cur_cr = data.get("totalCacheRead", 0)
    cur_cw = data.get("totalCacheWrite", 0)
    cur_tok = cur_in + cur_out + cur_cr + cur_cw

    cur_streak = profile.get("streak", 0) or 0
    cur_active = profile.get("active_days", 0) or 0
    cur_best = profile.get("best_day_cost", 0) or 0

    old_cost = ft.get("cost", 0) or 0
    old_msg = ft.get("messages", 0) or 0
    old_tok = ft.get("tokens", 0) or 0

    new_floor = {
        "cost": max(cur_cost, ft.get("cost", 0) or 0),
        "tokens": max(cur_tok, ft.get("tokens", 0) or 0),
        "messages": max(cur_msg, ft.get("messages", 0) or 0),
        "input": max(cur_in, ft.get("input", 0) or 0),
        "output": max(cur_out, ft.get("output", 0) or 0),
        "cache_read": max(cur_cr, ft.get("cache_read", 0) or 0),
        "cache_write": max(cur_cw, ft.get("cache_write", 0) or 0),
        "active_days": max(cur_active, ft.get("active_days", 0) or 0),
        # Streak is a current-state metric (it legitimately drops to 0 if a
        # day is missed), so we record the current value rather than ratchet.
        "streak": cur_streak,
        "best_day_cost": max(cur_best, ft.get("best_day_cost", 0) or 0),
    }
    if cur_best >= (ft.get("best_day_cost", 0) or 0):
        new_floor["best_day_date"] = profile.get("best_day_date") or ft.get("best_day_date")
    else:
        new_floor["best_day_date"] = ft.get("best_day_date")
    floor["totals"] = new_floor

    # If legacy global totals exceed the new per-model floor, keep the legacy
    # values in the floor file for audit continuity but do not proportionally
    # inflate rendered entries. Current recovered data is expected to exceed the
    # old global floor after local/server model-max merge.
    if new_floor["cost"] > cur_cost or new_floor["messages"] > cur_msg or new_floor["tokens"] > cur_tok:
        print(
            "[WARN] Legacy global floor exceeds summed model floors; "
            "preserving totals in tokscale_floor.json but rendering model-exact rows"
        )

    print(
        f"[INFO] Model floor ratchet: {len(changed_models)} model rows updated; "
        f"cost ${old_cost:.2f} -> ${new_floor['cost']:.2f}, "
        f"tokens {old_tok:,} -> {new_floor['tokens']:,}, "
        f"messages {old_msg:,} -> {new_floor['messages']:,}"
    )

    profile["active_days"] = new_floor["active_days"]
    profile["streak"] = new_floor["streak"]
    profile["best_day_cost"] = new_floor["best_day_cost"]
    if new_floor.get("best_day_date"):
        profile["best_day_date"] = new_floor["best_day_date"]
    if new_floor["active_days"]:
        profile["avg_daily_cost"] = new_floor["cost"] / new_floor["active_days"]

    return floor


def format_cost(cost):
    """Format cost as dollar string."""
    if cost >= 1000:
        return f"${cost:,.0f}"
    return f"${cost:.2f}"


def format_tokens(tokens):
    """Format token count with appropriate suffix."""
    if tokens >= 1_000_000_000:
        return f"{tokens / 1_000_000_000:.1f}B"
    elif tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def format_number(n):
    """Format number with commas."""
    return f"{n:,}"


def badge(label, value, color, style="flat-square", logo=None):
    """Generate a shields.io badge markdown image."""
    label_enc = label.replace(" ", "_").replace("-", "--")
    value_enc = str(value).replace(" ", "_").replace("-", "--").replace("$", "")
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    return f'<img src="https://img.shields.io/badge/{label_enc}-{value_enc}-{color}?style={style}{logo_part}" alt="{label}"/>'


def badge_link(label, value, color, url, style="for-the-badge", logo=None):
    """Generate a clickable shields.io badge."""
    img = badge(label, value, color, style, logo)
    return f'<a href="{url}">{img}</a>'


def get_client_display(client):
    """Get display name for a client."""
    mapping = {
        "claude": "Claude Code",
        "codex": "Codex CLI",
        "gemini": "Gemini CLI",
        "cursor": "Cursor",
        "opencode": "OpenCode",
        "hermes": "Hermes Agent",
    }
    return mapping.get(client, client.title())


def get_client_color(client):
    """Get brand color for a client."""
    colors = {
        "claude": "cc9b7a",
        "codex": "74aa9c",
        "gemini": "8E75B2",
        "cursor": "00A67E",
        "hermes": "FFB400",
    }
    return colors.get(client, "555555")


def get_client_logo(client):
    """Get logo name for a client."""
    logos = {
        "claude": "anthropic",
        "codex": "openai",
        "gemini": "google",
        "hermes": "rocket",
    }
    return logos.get(client)


def generate_dashboard(data, profile):
    """Generate markdown dashboard section."""
    entries = data.get("entries", [])
    if not entries:
        return ""

    total_cost = data.get("totalCost", 0)
    total_messages = data.get("totalMessages", 0)
    total_input = data.get("totalInput", 0)
    total_output = data.get("totalOutput", 0)
    total_cache_read = data.get("totalCacheRead", 0)
    total_cache_write = data.get("totalCacheWrite", 0)
    total_tokens = total_input + total_output + total_cache_read + total_cache_write

    rank = profile.get("rank")
    total_users = profile.get("total_users")
    streak = profile.get("streak")
    active_days = profile.get("active_days")
    avg_daily = profile.get("avg_daily_cost")
    best_day = profile.get("best_day_cost")

    # Group by client
    client_stats = {}
    for entry in entries:
        client = entry.get("client", "unknown")
        if client not in client_stats:
            client_stats[client] = {"cost": 0, "messages": 0, "models": [], "model_costs": {}, "tokens": 0}
        client_stats[client]["cost"] += entry.get("cost", 0)
        client_stats[client]["messages"] += entry.get("messageCount", 0)
        entry_tokens = (
            entry.get("input", 0) + entry.get("output", 0)
            + entry.get("cacheRead", 0) + entry.get("cacheWrite", 0)
        )
        client_stats[client]["tokens"] += entry_tokens
        model = entry.get("model", "")
        if model and model != "<synthetic>" and model not in client_stats[client]["models"]:
            client_stats[client]["models"].append(model)
        if model and model != "<synthetic>":
            client_stats[client]["model_costs"][model] = (
                client_stats[client]["model_costs"].get(model, 0) + entry.get("cost", 0)
            )

    sorted_clients = sorted(client_stats.items(), key=lambda x: x[1]["cost"], reverse=True)
    num_models = sum(len(s["models"]) for _, s in sorted_clients)

    kst = timezone(timedelta(hours=9))
    update_time = datetime.now(kst).strftime("%Y-%m-%d")

    L = []  # lines
    L.append("")
    L.append("## AI Coding Agent Usage")
    L.append("")

    # --- Hero section: rank + total cost ---
    L.append('<div align="center">')
    L.append("")

    if rank:
        rank_value = f"%23{rank}"  # URL-encoded #
        L.append(badge_link("Global Rank", rank_value, "FFD700", "https://tokscale.ai/leaderboard", "for-the-badge", "trophy"))
        L.append(badge_link("Total Cost", format_cost(total_cost), "00d084", "https://tokscale.ai/u/shaun0927", "for-the-badge", "cashapp"))
        L.append(badge(f"Tokens", format_tokens(total_tokens), "00d084", "for-the-badge", "stackblitz"))
    else:
        L.append(badge_link("Total Cost", format_cost(total_cost), "00d084", "https://tokscale.ai/u/shaun0927", "for-the-badge", "cashapp"))
        L.append(badge(f"Tokens", format_tokens(total_tokens), "00d084", "for-the-badge", "stackblitz"))

    L.append("")
    L.append("</div>")
    L.append("")

    # --- Stats row: streak, active days, avg daily, best day, models ---
    stats_badges = []
    if streak:
        stats_badges.append(badge("Streak", f"{streak} days", "FF6B35", "flat-square", "fireship"))
    if active_days:
        stats_badges.append(badge("Active Days", str(active_days), "4A90D9", "flat-square", "calendar"))
    if avg_daily:
        stats_badges.append(badge("Avg Daily", format_cost(avg_daily), "9B59B6", "flat-square", "trending-up"))
    if best_day:
        stats_badges.append(badge("Best Day", format_cost(best_day), "E74C3C", "flat-square", "zap"))
    stats_badges.append(badge("Messages", format_number(total_messages), "3498DB", "flat-square", "chat"))
    stats_badges.append(badge("Models", str(num_models), "1ABC9C", "flat-square", "robot"))

    if stats_badges:
        L.append('<div align="center">')
        L.append("")
        for b in stats_badges:
            L.append(b)
        L.append("")
        L.append("</div>")
        L.append("")

    # --- Platform breakdown: visual bars ---
    L.append('<div align="center">')
    L.append("")
    L.append("<table>")
    L.append("<tr><th>Platform</th><th>Models</th><th>Share</th><th>Messages</th><th>Tokens</th><th>Cost</th></tr>")

    for client, stats in sorted_clients:
        name = get_client_display(client)
        color = get_client_color(client)
        logo = get_client_logo(client)
        pct = (stats["cost"] / total_cost * 100) if total_cost > 0 else 0

        # Model names (shortened)
        models_short = []
        models_by_cost = sorted(
            stats["models"],
            key=lambda m: stats.get("model_costs", {}).get(m, 0),
            reverse=True,
        )
        for m in models_by_cost[:3]:
            short = m.replace("claude-", "").replace("gpt-", "").replace("gemini-", "")
            models_short.append(f"<code>{short}</code>")
        if len(models_by_cost) > 3:
            models_short.append(f"<code>+{len(models_by_cost) - 3}</code>")
        models_str = " ".join(models_short)

        # Visual share bar using unicode block
        bar_len = max(1, round(pct / 5))
        bar = "█" * bar_len + "░" * (20 - bar_len)

        # Platform name badge
        name_badge = f'<img src="https://img.shields.io/badge/{name.replace(" ", "_")}-{color}?style=flat-square&logo={logo}&logoColor=white" alt="{name}"/>' if logo else f"**{name}**"

        L.append(
            f"<tr>"
            f"<td>{name_badge}</td>"
            f"<td>{models_str}</td>"
            f'<td><code>{bar}</code> {pct:.1f}%</td>'
            f"<td align=\"right\">{format_number(stats['messages'])}</td>"
            f"<td align=\"right\">{format_tokens(stats['tokens'])}</td>"
            f"<td align=\"right\"><b>{format_cost(stats['cost'])}</b></td>"
            f"</tr>"
        )

    # Total row
    L.append(
        f'<tr><td colspan="3"><b>Total</b></td>'
        f'<td align="right"><b>{format_number(total_messages)}</b></td>'
        f'<td align="right"><b>{format_tokens(total_tokens)}</b></td>'
        f'<td align="right"><b>{format_cost(total_cost)}</b></td></tr>'
    )
    L.append("</table>")
    L.append("")
    L.append("</div>")
    L.append("")

    # --- Token composition mini-bar ---
    L.append('<div align="center">')
    L.append("")
    L.append(f"**Token Composition**")
    L.append("")
    compositions = [
        ("Cache Read", total_cache_read, "2ECC71"),
        ("Cache Write", total_cache_write, "27AE60"),
        ("Input", total_input, "3498DB"),
        ("Output", total_output, "9B59B6"),
    ]
    for label, val, color in compositions:
        if val > 0:
            pct = val / total_tokens * 100
            L.append(badge(f"{label} ({pct:.1f}%25)", format_tokens(val), color, "flat-square"))
    L.append("")
    L.append("</div>")
    L.append("")

    # --- Footer ---
    L.append(
        f'<div align="center">'
        f'<sub>Tracked by <a href="https://tokscale.ai/u/shaun0927">tokscale</a> '
        f'| <a href="https://tokscale.ai/leaderboard">Leaderboard</a> '
        f'| Auto-updated {update_time}</sub>'
        f"</div>"
    )
    L.append("")

    return "\n".join(L)


def update_readme(dashboard_content):
    """Update README.md with the dashboard section."""
    print("[INFO] Updating README.md...")

    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        print("[ERROR] README.md not found")
        return False

    start_marker = "<!-- TOKSCALE_START -->"
    end_marker = "<!-- TOKSCALE_END -->"

    new_section = f"{start_marker}\n{dashboard_content}\n{end_marker}"

    if start_marker in readme and end_marker in readme:
        pattern = re.compile(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        readme = pattern.sub(new_section, readme)
    else:
        insert_point = "## Tech Stack"
        if insert_point in readme:
            readme = readme.replace(insert_point, f"{new_section}\n---\n\n{insert_point}")
        else:
            insert_point = "## GitHub Stats"
            if insert_point in readme:
                readme = readme.replace(insert_point, f"{new_section}\n---\n\n{insert_point}")
            else:
                readme += f"\n{new_section}\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print("[OK] README.md updated with tokscale dashboard!")
    return True


def main():
    print("=" * 60)
    print("Tokscale Dashboard Updater v2")
    print("=" * 60)

    username = os.environ.get("TOKSCALE_USERNAME", "shaun0927")
    source = os.environ.get("TOKSCALE_SOURCE", "").lower()

    data = None
    if source != "ssr":
        data = fetch_tokscale_data()
        if data and not data.get("entries"):
            print("[WARN] CLI returned no entries, falling back to SSR")
            data = None
    if data is None:
        data = fetch_ssr_data(username)
    if data is None:
        print("[ERROR] Failed to fetch tokscale data")
        sys.exit(1)

    # Merge in tokscale.ai SSR rows with local rows at (client, model) level.
    # The CLI sees only sessions on this machine and can also rescan old local
    # logs lower than what the server already holds. Preserve the maximum value
    # per model/metric so a stale local model (e.g. gpt-5.4) cannot visually
    # erase historical usage while a current model (e.g. gpt-5.5) keeps growing.
    if source != "ssr":
        ssr = fetch_ssr_data(username)
        if ssr:
            data = merge_data_by_client_model(data, ssr)
    else:
        data["entries"] = list(aggregate_entries(data.get("entries", [])).values())
        recompute_totals_from_entries(data)

    profile = fetch_profile_data(username)

    floor = load_floor()
    floor = apply_floor(data, profile, floor)
    if floor:
        save_floor(floor)

    dashboard = generate_dashboard(data, profile)
    if not dashboard:
        print("[ERROR] Failed to generate dashboard")
        sys.exit(1)

    success = update_readme(dashboard)
    if not success:
        sys.exit(1)

    print("=" * 60)
    print("[OK] Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
