#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PRICING = {
    "opus": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 18.75,
        "cache_read": 1.5,
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "haiku": {
        "input": 0.80,
        "output": 4.0,
        "cache_write": 1.0,
        "cache_read": 0.08,
    },
}

CONTEXT_WINDOW = {
    "opus": 1_000_000,
    "sonnet": 200_000,
    "haiku": 200_000,
}


def short_model_name(model_id) -> str:
    if isinstance(model_id, dict):
        model_id = model_id.get("id") or model_id.get("display_name") or ""
    if not model_id:
        return "unknown"
    m = str(model_id).lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return model_id


def parse_payload(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def iter_usages(transcript_path: str) -> list[dict]:
    out: list[dict] = []
    p = Path(transcript_path) if transcript_path else None
    if p is None or not p.is_file():
        return out
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            usage = msg.get("usage")
            if isinstance(usage, dict):
                out.append(usage)
    return out


def aggregate(usages: list[dict]) -> dict:
    totals = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
    }
    for u in usages:
        totals["input"] += int(u.get("input_tokens") or 0)
        totals["output"] += int(u.get("output_tokens") or 0)
        totals["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
        totals["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
    return totals


def cache_hit_pct(totals: dict) -> int:
    denom = totals["cache_read"] + totals["cache_write"] + totals["input"]
    if denom <= 0:
        return 0
    return round(100 * totals["cache_read"] / denom)


def session_cost_usd(totals: dict, short: str) -> float:
    rates = PRICING.get(short, PRICING["opus"])
    cost = 0.0
    cost += totals["input"] * rates["input"] / 1_000_000
    cost += totals["output"] * rates["output"] / 1_000_000
    cost += totals["cache_write"] * rates["cache_write"] / 1_000_000
    cost += totals["cache_read"] * rates["cache_read"] / 1_000_000
    return cost


def context_fill_pct(usages: list[dict], short: str) -> int:
    if not usages:
        return 0
    window = CONTEXT_WINDOW.get(short, 200_000)
    last = usages[-1]
    used = (
        int(last.get("input_tokens") or 0)
        + int(last.get("cache_read_input_tokens") or 0)
        + int(last.get("cache_creation_input_tokens") or 0)
    )
    pct = round(100 * used / window)
    return max(0, min(pct, 100))


def format_cost(cost: float) -> str:
    if cost < 0.01:
        return "$0.00"
    if cost < 10:
        return f"${cost:.2f}"
    if cost < 100:
        return f"${cost:.1f}"
    return f"${int(round(cost))}"


def main() -> int:
    data = parse_payload(sys.stdin.read())

    cwd = data.get("cwd") or os.getcwd()
    project = os.path.basename(cwd.rstrip("/")) or cwd
    short = short_model_name(data.get("model", ""))
    transcript_path = data.get("transcript_path", "")

    usages = iter_usages(transcript_path)
    totals = aggregate(usages)
    cache_pct = cache_hit_pct(totals)
    cost = session_cost_usd(totals, short)
    ctx_pct = context_fill_pct(usages, short)

    parts = [
        f"[{project}]",
        f"{short}",
        f"cache {cache_pct}%",
        f"ctx {ctx_pct}%",
        format_cost(cost),
    ]
    sys.stdout.write(" | ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
