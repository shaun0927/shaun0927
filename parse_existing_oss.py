#!/usr/bin/env python3
"""One-shot helper: extract the current Open Source Contributions table
from README.md into oss_contributions.json so update_oss_contributions.py
has a stable config to drive future refreshes.
"""

import json
import re
from pathlib import Path

README = Path("README.md").read_text(encoding="utf-8")

start = README.index("## Open Source Contributions")
end = README.index("\n---", start)
section = README[start:end]

# Capture category headers and the rows beneath them.
cat_blocks = re.split(r"\n### ", section)
config = {"username": "shaun0927", "categories": []}

ROW_PAT = re.compile(
    r"^\|\s*<img[^>]*/>\s*\[(?P<repo>[^\]]+)\]\(https://github\.com/(?P<owner>[^/]+)/(?P<name>[^)]+)\)"
    r"\s*\|\s*(?P<desc>[^|]+)\s*\|.*?\|\s*\[(?P<prs>\d+)\]",
    re.MULTILINE,
)

NOTES_PAT = re.compile(r"\|\s*\[(?P<prs>\d+)\][^|]*\|\s*(?P<notes>[^\n]*)\s*\|")


def split_notes(raw):
    raw = raw.strip()
    if not raw:
        return []
    # split on whitespace between adjacent ![](...) badge tags
    parts = re.findall(r"!\[\]\([^)]+\)", raw)
    return parts


for block in cat_blocks[1:]:  # first chunk has the intro paragraph
    title_line, _, rest = block.partition("\n")
    if not rest.strip().startswith("| Project"):
        continue
    category = {"name": title_line.strip(), "repos": []}
    for line in rest.splitlines():
        m = ROW_PAT.match(line)
        if not m:
            continue
        notes_match = NOTES_PAT.search(line)
        notes_raw = notes_match.group("notes") if notes_match else ""
        category["repos"].append(
            {
                "owner": m.group("owner"),
                "name": m.group("name").split("/")[0],
                "description": m.group("desc").strip(),
                "notes_markdown": notes_raw.strip(),
            }
        )
    config["categories"].append(category)

with open("oss_contributions.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write("\n")

total = sum(len(c["repos"]) for c in config["categories"])
print(f"Extracted {total} repos across {len(config['categories'])} categories")
for c in config["categories"]:
    print(f"  - {c['name']}: {len(c['repos'])} repos")
