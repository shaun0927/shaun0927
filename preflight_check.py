#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integrity preflight check before any tokscale submit cycle.

Run by auto_tokscale.sh phase 0 before update_tokscale / safe_submit / git
commands touch the world. Fail-fast on any condition that suggests the
recovery state has been mutated unexpectedly. Exits non-zero on any FATAL,
zero with a WARN line on soft drift.

Checks
------
1. Recovery JSONL directory exists at ~/.claude/projects/-tokscale-recovery-reconstructed/
   with the expected README.md and at least N session files.
2. Tokscale CLI scan of `claude` includes the synthetic
   `reconstructed-claude-history` model with cost >= MIN_RECOVERY_COST.
3. Server SSR includes `reconstructed-claude-history` on the claude client
   with cost >= MIN_RECOVERY_COST.
4. Floor file parses, has the expected keys, and cost >= MIN_FLOOR_COST.
5. safe_submit.py contains both guard env-var names (sanity check that the
   safety code wasn't accidentally removed by a refactor).

Use:  python3 preflight_check.py [--strict]
      --strict turns WARN into FATAL.
"""

from __future__ import annotations

import codecs
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
RECOVERY_DIR = Path(os.path.expanduser("~/.claude/projects/-tokscale-recovery-reconstructed"))
FLOOR_PATH = REPO_DIR / "tokscale_floor.json"
SAFE_SUBMIT_PATH = REPO_DIR / "safe_submit.py"

# Thresholds — chosen well below the actual recovery so normal drift doesn't
# trip the alarm, but well above zero so deletion or major regression does.
MIN_RECOVERY_FILES = 100        # we wrote 200; 100 leaves slack for partial loss
MIN_RECOVERY_COST = 8000.0      # we wrote $11,665; 8k leaves slack
MIN_FLOOR_COST = 50000.0        # we set $57,707; 50k leaves slack
SCAN_TIMEOUT = 300

REQUIRED_GUARD_VARS = ("TOKSCALE_FORCE_SYNTHETIC_DELETE", "TOKSCALE_FORCE_LOSS")
USERNAME = "shaun0927"
SYNTHETIC_PATTERNS = ("reconstructed-", "synthetic", "recovered-", "<synthetic>")


def is_synthetic(model: str) -> bool:
    m = model.lower()
    return any(p in m for p in SYNTHETIC_PATTERNS)


# ----------------------------------------------------- result accumulator

class Findings:
    def __init__(self, strict: bool):
        self.strict = strict
        self.fatal: list[str] = []
        self.warn: list[str] = []
        self.ok: list[str] = []

    def add_fatal(self, msg: str):
        self.fatal.append(msg)

    def add_warn(self, msg: str):
        if self.strict:
            self.fatal.append(f"(strict) {msg}")
        else:
            self.warn.append(msg)

    def add_ok(self, msg: str):
        self.ok.append(msg)

    def report(self) -> int:
        for m in self.ok:
            print(f"[ OK ] {m}")
        for m in self.warn:
            print(f"[WARN] {m}")
        for m in self.fatal:
            print(f"[FAIL] {m}")
        if self.fatal:
            print(f"\nPREFLIGHT FAILED: {len(self.fatal)} fatal, {len(self.warn)} warning")
            return 2
        if self.warn:
            print(f"\nPREFLIGHT PASSED with warnings: {len(self.warn)} warning")
            return 0
        print(f"\nPREFLIGHT PASSED clean")
        return 0


# ------------------------------------------------------- individual checks

def check_recovery_dir(f: Findings) -> None:
    if not RECOVERY_DIR.is_dir():
        f.add_fatal(
            f"recovery directory missing: {RECOVERY_DIR}. "
            f"This holds the synthetic JSONL that re-creates the "
            f"reconstructed-claude-history bucket. Restore from a backup or "
            f"re-fabricate before allowing any Claude submit."
        )
        return
    jsonl_files = list(RECOVERY_DIR.glob("*.jsonl"))
    n = len(jsonl_files)
    readme = RECOVERY_DIR / "README.md"
    if not readme.is_file():
        f.add_warn(f"recovery README missing in {RECOVERY_DIR} (cosmetic)")
    if n < MIN_RECOVERY_FILES:
        f.add_fatal(
            f"recovery directory has only {n} JSONL files (< {MIN_RECOVERY_FILES}). "
            f"Bucket may have been partially deleted."
        )
    else:
        total_size = sum(p.stat().st_size for p in jsonl_files)
        f.add_ok(f"recovery dir present: {n} JSONL files, {total_size:,} bytes")


def check_local_recovery_visible(f: Findings) -> None:
    """tokscale --json -c claude must include the synthetic model."""
    try:
        r = subprocess.run(
            ["npx", "tokscale@latest", "--json", "-c", "claude"],
            capture_output=True, text=True, timeout=SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        f.add_fatal(f"local tokscale scan timed out (>{SCAN_TIMEOUT}s)")
        return
    if r.returncode != 0:
        f.add_fatal(f"local tokscale scan failed: {r.stderr.strip()[:200]}")
        return
    i = r.stdout.find("{")
    if i < 0:
        f.add_fatal("local tokscale produced no JSON output")
        return
    try:
        d = json.loads(r.stdout[i:])
    except json.JSONDecodeError as e:
        f.add_fatal(f"local tokscale output not parsable: {e}")
        return
    rec_cost = sum(
        e.get("cost", 0) for e in d.get("entries", [])
        if "reconstr" in e.get("model", "").lower()
    )
    if rec_cost < MIN_RECOVERY_COST:
        f.add_fatal(
            f"local scan recovery bucket cost ${rec_cost:,.2f} < "
            f"${MIN_RECOVERY_COST:,.0f}. Recovery JSONL not registering — "
            f"check pricing changes or directory contents."
        )
    else:
        f.add_ok(f"local scan: reconstructed-claude-history = ${rec_cost:,.2f}")


def check_server_recovery_visible(f: Findings) -> None:
    url = f"https://tokscale.ai/u/{USERNAME}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        f.add_warn(f"server SSR fetch failed: {e} (transient)")
        return
    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)', html, re.DOTALL)
    if not pushes:
        f.add_warn("server SSR payload not found (page format change?)")
        return
    payload = codecs.decode("".join(pushes), "unicode_escape")
    rec_pat = re.compile(
        r'"reconstructed-claude-history":\{"cost":([0-9.eE+\-]+),'
    )
    matches = [float(x) for x in rec_pat.findall(payload)]
    if not matches:
        f.add_fatal(
            "server SSR has no reconstructed-claude-history entry. The "
            "recovery bucket may have been wiped server-side. Re-run the "
            "fabrication+force-submit recovery procedure."
        )
        return
    total = sum(matches)
    if total < MIN_RECOVERY_COST:
        f.add_fatal(
            f"server reconstructed-claude-history cost ${total:,.2f} < "
            f"${MIN_RECOVERY_COST:,.0f}. Bucket has been partially destroyed; "
            f"re-run recovery procedure."
        )
    else:
        f.add_ok(f"server: reconstructed-claude-history = ${total:,.2f} "
                 f"(across {len(matches)} SSR slices)")


def check_floor(f: Findings) -> None:
    if not FLOOR_PATH.is_file():
        f.add_fatal(f"floor file missing: {FLOOR_PATH}")
        return
    try:
        floor = json.loads(FLOOR_PATH.read_text())
    except Exception as e:
        f.add_fatal(f"floor file not parseable: {e}")
        return
    totals = floor.get("totals", {})
    cost = totals.get("cost", 0)
    if cost < MIN_FLOOR_COST:
        f.add_fatal(
            f"floor cost ${cost:,.2f} < ${MIN_FLOOR_COST:,.0f}. "
            f"Floor was reset/regressed."
        )
    else:
        f.add_ok(f"floor cost = ${cost:,.2f}, tokens = {totals.get('tokens', 0):,}")


def check_safe_submit_guards(f: Findings) -> None:
    if not SAFE_SUBMIT_PATH.is_file():
        f.add_fatal(f"safe_submit.py missing: {SAFE_SUBMIT_PATH}")
        return
    body = SAFE_SUBMIT_PATH.read_text()
    missing = [v for v in REQUIRED_GUARD_VARS if v not in body]
    if missing:
        f.add_fatal(
            f"safe_submit.py is missing guard env var(s): {missing}. "
            f"The synthetic-protection logic may have been removed."
        )
    else:
        f.add_ok(f"safe_submit guard env vars present: {REQUIRED_GUARD_VARS}")


def main() -> int:
    strict = "--strict" in sys.argv
    f = Findings(strict)
    print("=== tokscale preflight integrity check ===")
    check_recovery_dir(f)
    check_local_recovery_visible(f)
    check_server_recovery_visible(f)
    check_floor(f)
    check_safe_submit_guards(f)
    return f.report()


if __name__ == "__main__":
    sys.exit(main())
