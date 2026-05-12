#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open Source Contributions section refresher.

Reads oss_contributions.json (the curated repo list with descriptions and
notes), queries GitHub for fresh star + merged-PR counts via the local `gh`
CLI, then rewrites the section in README.md between the OSS_START / OSS_END
markers.

Why this lives next to update_tokscale.py:
- The previous workflow only refreshed the AI usage dashboard, so PR/star
  counts went stale until someone hand-edited the README.
- Running this from auto_tokscale.sh keeps both sections fresh on the same
  cron-like cadence.
"""

import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

CONFIG_PATH = Path("oss_contributions.json")
README_PATH = Path("README.md")
START_MARKER = "<!-- OSS_START -->"
END_MARKER = "<!-- OSS_END -->"


def gh_json(args):
    """Run gh, return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            print(f"[WARN] gh {' '.join(args[:3])}... failed: {result.stderr.strip()[:120]}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[WARN] gh call errored: {e}")
        return None


def fetch_stars(owner, name):
    data = gh_json(["api", f"repos/{owner}/{name}", "--jq", ".stargazers_count"])
    return int(data) if isinstance(data, int) else None


def fetch_merged_pr_count(owner, name, author):
    q = f"repo:{owner}/{name} is:pr author:{author} is:merged"
    data = gh_json([
        "api",
        "graphql",
        "-f",
        f"query=query{{ search(query: \"{q}\", type: ISSUE, first: 0) {{ issueCount }} }}",
        "--jq",
        ".data.search.issueCount",
    ])
    return int(data) if isinstance(data, int) else None


def format_stars(n):
    if n is None:
        return "—"
    return f"⭐ {n:,}"


def build_row(repo, owner, name, desc, stars, merged_count, notes_md, author):
    pr_link = f"https://github.com/{owner}/{name}/pulls?q=author%3A{author}+is%3Amerged"
    avatar = f'<img src="https://github.com/{owner}.png" width="18" align="top"/>'
    repo_link = f"[{repo}](https://github.com/{owner}/{name})"
    stars_cell = format_stars(stars)
    merged_cell = f"[{merged_count if merged_count is not None else '—'}]({pr_link})"
    notes_cell = notes_md or ""
    return f"| {avatar} {repo_link} | {desc} | {stars_cell} | {merged_cell} | {notes_cell} |"


def build_table(category, results, author):
    lines = [
        f"### {category['name']}",
        "",
        "| Project | Description | Stars | Merged | Notes |",
        "|:--|:--|--:|:-:|:--|",
    ]
    rows = []
    for repo in category["repos"]:
        owner = repo["owner"]
        name = repo["name"]
        key = f"{owner}/{name}"
        stars, merged = results.get(key, (None, None))
        rows.append((merged or 0, stars or 0, build_row(
            repo=name,
            owner=owner,
            name=name,
            desc=repo["description"],
            stars=stars,
            merged_count=merged,
            notes_md=repo.get("notes_markdown", ""),
            author=author,
        )))
    rows.sort(key=lambda x: (-x[0], -x[1]))
    lines.extend(r[2] for r in rows)
    return "\n".join(lines)


def build_section(config, results):
    """Build only the auto-managed body (footer line + category tables).

    The "## Open Source Contributions" heading and any manually-curated
    narrative above OSS_START are intentionally left untouched.
    """
    author = config.get("username", "shaun0927")
    total_prs = sum((m or 0) for (_s, m) in results.values())
    repo_count = sum(1 for (_s, m) in results.values() if (m or 0) > 0)
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")

    parts = [
        "",
        (
            f"_Auto-refreshed {today} via `gh` CLI (`update_oss_contributions.py`): "
            f"**{total_prs} PRs** merged across **{repo_count} curated repos** below. "
            f"Star counts via repos API; merged-PR counts via GraphQL search._"
        ),
        "",
    ]
    for cat in config["categories"]:
        parts.append(build_table(cat, results, author))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def replace_in_readme(new_section):
    text = README_PATH.read_text(encoding="utf-8")
    block = f"{START_MARKER}\n{new_section}\n{END_MARKER}"
    if START_MARKER in text and END_MARKER in text:
        text = re.sub(
            re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
            block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        raise SystemExit(
            "[ERROR] README missing OSS_START/OSS_END markers. Add them around the\n"
            "        auto-generated portion of the Open Source Contributions section."
        )
    README_PATH.write_text(text, encoding="utf-8")


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    author = config.get("username", "shaun0927")

    results = {}
    for cat in config["categories"]:
        for repo in cat["repos"]:
            owner, name = repo["owner"], repo["name"]
            key = f"{owner}/{name}"
            stars = fetch_stars(owner, name)
            merged = fetch_merged_pr_count(owner, name, author)
            results[key] = (stars, merged)
            print(f"[INFO] {key}: ⭐ {stars}  PRs {merged}")

    section = build_section(config, results)
    replace_in_readme(section)
    print(f"[OK] README.md updated; {sum(1 for v in results.values() if v[0] or v[1])} repos refreshed")


if __name__ == "__main__":
    main()
