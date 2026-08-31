#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
BASELINE_PATH = REPO_DIR / "tokscale_submit_baseline.json"
DEFAULT_CLIENTS = ("codex", "claude", "gemini", "hermes", "gjc", "grok", "micode", "opencode")
TOKEN_FIELDS = ("input", "output", "cacheRead", "cacheWrite", "reasoning")


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"schemaVersion": 1, "clients": {}}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def save_baseline(baseline: dict) -> None:
    baseline["updatedAt"] = datetime.now(timezone.utc).isoformat()
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_json(cmd: list[str]) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    start = r.stdout.find("{")
    if start < 0:
        raise RuntimeError("JSON output not found")
    return json.loads(r.stdout[start:])


def graph_for_client(client: str, since: str | None) -> dict:
    cmd = ["npx", "--yes", "tokscale", "graph", "-c", client, "--no-spinner"]
    if since:
        cmd.extend(["--since", since])
    return run_json(cmd)


def flatten_graph(graph: dict) -> dict[str, dict]:
    cells: dict[str, dict] = {}
    for day in graph.get("contributions", []) or []:
        date = day.get("date")
        for entry in day.get("clients", []) or []:
            client = entry.get("client") or "unknown"
            model = entry.get("modelId") or "unknown"
            provider = entry.get("providerId") or "unknown"
            key = f"{date}|{client}|{model}|{provider}"
            tokens = entry.get("tokens") or {}
            cells[key] = {
                "date": date,
                "client": client,
                "model": model,
                "provider": provider,
                "tokens": {field: int(tokens.get(field, 0) or 0) for field in TOKEN_FIELDS},
                "messages": int(entry.get("messages", 0) or 0),
                "cost": float(entry.get("cost", 0) or 0),
            }
    return cells


def cell_total(cell: dict) -> int:
    return sum(int(cell.get("tokens", {}).get(field, 0) or 0) for field in TOKEN_FIELDS)


def delta(current: dict, previous: dict) -> dict:
    token_delta = 0
    message_delta = 0
    cost_delta = 0.0
    changed_cells = 0
    changed_dates: set[str] = set()
    for key, current_cell in current.items():
        previous_cell = previous.get(key, {})
        token_growth = max(0, cell_total(current_cell) - cell_total(previous_cell))
        message_growth = max(0, int(current_cell.get("messages", 0) or 0) - int(previous_cell.get("messages", 0) or 0))
        cost_growth = max(0.0, float(current_cell.get("cost", 0) or 0) - float(previous_cell.get("cost", 0) or 0))
        if token_growth or message_growth or cost_growth:
            changed_cells += 1
            if current_cell.get("date"):
                changed_dates.add(current_cell["date"])
        token_delta += token_growth
        message_delta += message_growth
        cost_delta += cost_growth
    return {
        "tokens": token_delta,
        "messages": message_delta,
        "cost": cost_delta,
        "changedCells": changed_cells,
        "changedDates": sorted(changed_dates),
    }


def max_cell(current_cell: dict, previous_cell: dict | None) -> dict:
    if not previous_cell:
        return current_cell
    out = dict(previous_cell)
    out["date"] = current_cell.get("date") or previous_cell.get("date")
    out["client"] = current_cell.get("client") or previous_cell.get("client")
    out["model"] = current_cell.get("model") or previous_cell.get("model")
    out["provider"] = current_cell.get("provider") or previous_cell.get("provider")
    out["tokens"] = {
        field: max(
            int((current_cell.get("tokens") or {}).get(field, 0) or 0),
            int((previous_cell.get("tokens") or {}).get(field, 0) or 0),
        )
        for field in TOKEN_FIELDS
    }
    out["messages"] = max(int(current_cell.get("messages", 0) or 0), int(previous_cell.get("messages", 0) or 0))
    out["cost"] = max(float(current_cell.get("cost", 0) or 0), float(previous_cell.get("cost", 0) or 0))
    return out


def merge_cells(previous: dict, current: dict) -> dict:
    merged = dict(previous)
    for key, current_cell in current.items():
        merged[key] = max_cell(current_cell, previous.get(key))
    return merged


def submit_client(client: str, since: str | None, until: str | None, dry_run: bool) -> int:
    cmd = ["npx", "--yes", "tokscale", "submit", "-c", client]
    if since:
        cmd.extend(["--since", since])
    if until:
        cmd.extend(["--until", until])
    if dry_run:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, text=True, timeout=240)
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since")
    parser.add_argument("--client", action="append", dest="clients")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()

    clients = tuple(args.clients or DEFAULT_CLIENTS)
    baseline = load_baseline()
    baseline_clients = baseline.setdefault("clients", {})
    failed: list[str] = []
    submitted: list[str] = []
    skipped: list[str] = []
    initialized: list[str] = []

    for client in clients:
        graph = graph_for_client(client, args.since)
        current = flatten_graph(graph)
        previous_record = baseline_clients.get(client)
        previous = (previous_record or {}).get("cells", {})
        growth = delta(current, previous)
        current_total = sum(cell_total(cell) for cell in current.values())
        previous_total = sum(cell_total(cell) for cell in previous.values())
        changed_dates = growth["changedDates"]
        submit_since = min(changed_dates) if changed_dates else args.since
        submit_until = max(changed_dates) if changed_dates else None

        print(
            f"[delta-submit] {client}: current={current_total:,} "
            f"baseline={previous_total:,} growth={growth['tokens']:,} "
            f"messages=+{growth['messages']:,} cells=+{growth['changedCells']}"
        )

        if args.init_only:
            baseline_clients[client] = {
                "since": args.since,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "cells": merge_cells(previous, current),
            }
            initialized.append(client)
            continue

        should_submit = (
            previous_record is None
            or growth["tokens"] > 0
            or growth["messages"] > 0
            or growth["cost"] > 0
        )
        if not should_submit:
            skipped.append(client)
            continue

        print(f"[delta-submit] {client}: submit window {submit_since or 'all'}..{submit_until or 'latest'}")
        rc = submit_client(client, submit_since, submit_until, args.dry_run)
        if rc != 0:
            failed.append(client)
            continue
        submitted.append(client)
        if not args.dry_run:
            baseline_clients[client] = {
                "since": args.since,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "cells": merge_cells(previous, current),
            }

    if not args.dry_run:
        save_baseline(baseline)

    submitted_label = "would_submit" if args.dry_run else "submitted"
    print(f"[delta-submit] summary: {submitted_label}={submitted} skipped={skipped} initialized={initialized} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
