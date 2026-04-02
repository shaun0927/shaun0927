#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tokscale Dashboard Updater
Fetches token usage data via tokscale CLI and updates README.md
with a visual dashboard section.
"""

import json
import re
import subprocess
import sys
from datetime import datetime

import pytz


def fetch_tokscale_data():
    """Run tokscale CLI and return JSON data."""
    print("[INFO] Fetching tokscale data...")
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
        # Extract JSON from output (skip npm warnings)
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("{"):
                # Find the full JSON object
                json_start = result.stdout.index(line)
                return json.loads(result.stdout[json_start:])
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print("[ERROR] tokscale timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return None


def format_cost(cost):
    """Format cost as dollar string."""
    if cost >= 1000:
        return f"${cost:,.0f}"
    elif cost >= 1:
        return f"${cost:.2f}"
    else:
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


def get_client_display(client):
    """Get display name and emoji for a client."""
    mapping = {
        "claude": ("Claude Code", "anthropic"),
        "codex": ("Codex CLI", "openai"),
        "gemini": ("Gemini CLI", "google"),
        "cursor": ("Cursor", "cursor"),
        "opencode": ("OpenCode", "code"),
    }
    name, logo = mapping.get(client, (client.title(), "terminal"))
    return name, logo


def get_badge_color(client):
    """Get badge color for a client."""
    colors = {
        "claude": "cc9b7a",
        "codex": "74aa9c",
        "gemini": "8E75B2",
        "cursor": "00A67E",
    }
    return colors.get(client, "555555")


def generate_dashboard(data):
    """Generate markdown dashboard section."""
    entries = data.get("entries", [])
    if not entries:
        return ""

    total_cost = data.get("totalCost", 0)
    total_messages = data.get("totalMessages", 0)
    total_tokens = (
        data.get("totalInput", 0)
        + data.get("totalOutput", 0)
        + data.get("totalCacheRead", 0)
        + data.get("totalCacheWrite", 0)
    )

    # Group by client
    client_stats = {}
    for entry in entries:
        client = entry.get("client", "unknown")
        if client not in client_stats:
            client_stats[client] = {
                "cost": 0,
                "messages": 0,
                "models": [],
                "tokens": 0,
            }
        client_stats[client]["cost"] += entry.get("cost", 0)
        client_stats[client]["messages"] += entry.get("messageCount", 0)
        entry_tokens = (
            entry.get("input", 0)
            + entry.get("output", 0)
            + entry.get("cacheRead", 0)
            + entry.get("cacheWrite", 0)
        )
        client_stats[client]["tokens"] += entry_tokens
        model = entry.get("model", "")
        if model and model != "<synthetic>" and model not in client_stats[client]["models"]:
            client_stats[client]["models"].append(model)

    # Sort clients by cost (descending)
    sorted_clients = sorted(client_stats.items(), key=lambda x: x[1]["cost"], reverse=True)

    # Build summary badges
    kst = pytz.timezone("Asia/Seoul")
    update_time = datetime.now(kst).strftime("%Y-%m-%d")

    lines = []
    lines.append("")
    lines.append("## AI Coding Agent Usage")
    lines.append("")
    lines.append('<div align="center">')
    lines.append("")
    lines.append(
        f'<a href="https://tokscale.ai/u/shaun0927">'
        f'<img src="https://img.shields.io/badge/Total_Cost-{format_cost(total_cost).replace("-","--")}-00d084?style=for-the-badge&logo=cashapp&logoColor=white" alt="Total Cost"/>'
        f"</a>"
    )
    lines.append(
        f'<img src="https://img.shields.io/badge/Messages-{format_number(total_messages)}-00d084?style=for-the-badge&logo=chatbot&logoColor=white" alt="Messages"/>'
    )
    lines.append(
        f'<img src="https://img.shields.io/badge/Tokens-{format_tokens(total_tokens)}-00d084?style=for-the-badge&logo=stackblitz&logoColor=white" alt="Tokens"/>'
    )
    lines.append("")
    lines.append("</div>")
    lines.append("")

    # Client badges
    lines.append('<div align="center">')
    lines.append("")
    for client, stats in sorted_clients:
        name, _ = get_client_display(client)
        color = get_badge_color(client)
        cost_str = format_cost(stats["cost"]).replace("-", "--")
        lines.append(
            f'<img src="https://img.shields.io/badge/{name.replace(" ", "_")}-{cost_str}-{color}?style=flat-square" alt="{name}"/>'
        )
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append("<br/>")
    lines.append("")

    # Detailed table
    lines.append('<div align="center">')
    lines.append("")
    lines.append("| Platform | Models | Messages | Tokens | Cost |")
    lines.append("|:---------|:-------|-------:|-------:|-----:|")

    for client, stats in sorted_clients:
        name, _ = get_client_display(client)
        models_str = ", ".join(
            m.replace("claude-", "").replace("gpt-", "") for m in stats["models"][:3]
        )
        if len(stats["models"]) > 3:
            models_str += f" +{len(stats['models']) - 3}"
        lines.append(
            f"| **{name}** | {models_str} | {format_number(stats['messages'])} | {format_tokens(stats['tokens'])} | **{format_cost(stats['cost'])}** |"
        )

    # Total row
    lines.append(
        f"| **Total** | | **{format_number(total_messages)}** | **{format_tokens(total_tokens)}** | **{format_cost(total_cost)}** |"
    )
    lines.append("")
    lines.append("</div>")
    lines.append("")
    lines.append(
        f'<div align="center">'
        f'<sub>Tracked by <a href="https://tokscale.ai/u/shaun0927">tokscale</a> | Updated {update_time}</sub>'
        f"</div>"
    )
    lines.append("")

    return "\n".join(lines)


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
        # Replace existing section
        pattern = re.compile(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        readme = pattern.sub(new_section, readme)
    else:
        # Insert before Tech Stack section
        insert_point = "## Tech Stack"
        if insert_point in readme:
            readme = readme.replace(
                insert_point,
                f"{new_section}\n---\n\n{insert_point}",
            )
        else:
            # Fallback: insert before GitHub Stats
            insert_point = "## GitHub Stats"
            if insert_point in readme:
                readme = readme.replace(
                    insert_point,
                    f"{new_section}\n---\n\n{insert_point}",
                )
            else:
                # Append at end
                readme += f"\n{new_section}\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print("[OK] README.md updated with tokscale dashboard!")
    return True


def main():
    print("=" * 60)
    print("Tokscale Dashboard Updater")
    print("=" * 60)

    data = fetch_tokscale_data()
    if data is None:
        print("[ERROR] Failed to fetch tokscale data")
        sys.exit(1)

    dashboard = generate_dashboard(data)
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
