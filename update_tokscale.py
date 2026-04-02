#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tokscale Dashboard Updater
Fetches token usage data via tokscale CLI + profile scraping,
then updates README.md with a visual dashboard section.
"""

import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime

import pytz


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

    # Average daily cost
    m = re.search(r'Avg[^<]*Daily[^<]*</div>.*?StatItemValue[^>]*>\$([0-9,.]+)', html, re.DOTALL)
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
        m = re.search(r'(\d+)\s*(?:total\s*)?[Uu]sers', lb_html)
        if m:
            profile["total_users"] = int(m.group(1))
    except Exception:
        pass

    print(f"[INFO] Profile data: {profile}")
    return profile


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
    }
    return mapping.get(client, client.title())


def get_client_color(client):
    """Get brand color for a client."""
    colors = {
        "claude": "cc9b7a",
        "codex": "74aa9c",
        "gemini": "8E75B2",
        "cursor": "00A67E",
    }
    return colors.get(client, "555555")


def get_client_logo(client):
    """Get logo name for a client."""
    logos = {
        "claude": "anthropic",
        "codex": "openai",
        "gemini": "google",
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
            client_stats[client] = {"cost": 0, "messages": 0, "models": [], "tokens": 0}
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

    sorted_clients = sorted(client_stats.items(), key=lambda x: x[1]["cost"], reverse=True)
    num_models = sum(len(s["models"]) for _, s in sorted_clients)

    kst = pytz.timezone("Asia/Seoul")
    update_time = datetime.now(kst).strftime("%Y-%m-%d")

    L = []  # lines
    L.append("")
    L.append("## AI Coding Agent Usage")
    L.append("")

    # --- Hero section: rank + total cost ---
    L.append('<div align="center">')
    L.append("")

    if rank:
        rank_label = f"Global Rank"
        rank_value = f"%23{rank}"  # URL-encoded #
        if total_users:
            rank_value += f" of {total_users}"
            top_pct = round(rank / total_users * 100, 1)
            rank_label = f"Global Top {top_pct}%25"
        L.append(badge_link(rank_label, rank_value, "FFD700", "https://tokscale.ai/leaderboard", "for-the-badge", "trophy"))
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
        for m in stats["models"][:3]:
            short = m.replace("claude-", "").replace("gpt-", "").replace("gemini-", "")
            models_short.append(f"<code>{short}</code>")
        if len(stats["models"]) > 3:
            models_short.append(f"<code>+{len(stats['models']) - 3}</code>")
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

    data = fetch_tokscale_data()
    if data is None:
        print("[ERROR] Failed to fetch tokscale data")
        sys.exit(1)

    profile = fetch_profile_data("shaun0927")

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
