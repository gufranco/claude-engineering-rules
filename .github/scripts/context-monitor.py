#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time

CONTEXT_LIMITS = {
    "opus": 200000,
    "sonnet": 200000,
    "haiku": 200000,
}

BYTES_PER_TOKEN = 3

BAR_FULL = "#"
BAR_EMPTY = "-"
BAR_WIDTH = 10


def get_context_percentage(transcript_path, model):
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    file_size = os.path.getsize(transcript_path)
    estimated_tokens = file_size / BYTES_PER_TOKEN

    limit = CONTEXT_LIMITS.get("sonnet", 200000)
    for key, value in CONTEXT_LIMITS.items():
        if key in model.lower():
            limit = value
            break

    return min(100, int((estimated_tokens / limit) * 100))


def get_git_info(workspace):
    try:
        branch = subprocess.run(
            ["git", "-C", workspace, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        branch_name = branch.stdout.strip() or "detached"

        status = subprocess.run(
            ["git", "-C", workspace, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        dirty = "*" if status.stdout.strip() else ""

        return f"{branch_name}{dirty}"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def format_cost(cost):
    if not cost:
        return ""
    try:
        amount = float(cost)
        if amount < 0.01:
            return ""
        return f"${amount:.2f}"
    except (ValueError, TypeError):
        return ""


def format_duration(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return ""
    try:
        created = os.path.getctime(transcript_path)
        elapsed = int(time.time() - created)
        if elapsed < 60:
            return ""
        hours, remainder = divmod(elapsed, 3600)
        minutes = remainder // 60
        if hours > 0:
            return f"{hours}h{minutes:02d}m"
        return f"{minutes}m"
    except OSError:
        return ""


def build_bar(percentage):
    filled = int(BAR_WIDTH * percentage / 100)
    empty = BAR_WIDTH - filled
    return f"[{BAR_FULL * filled}{BAR_EMPTY * empty}]"


def get_level(percentage):
    if percentage >= 95:
        return "CRITICAL"
    if percentage >= 85:
        return "HIGH"
    if percentage >= 70:
        return "MED"
    if percentage >= 50:
        return "LOW"
    return ""


def _field(value, keys, default):
    if isinstance(value, dict):
        value = next((value[key] for key in keys if value.get(key)), None)
    return str(value) if value else default


def _context_part(transcript_path: str, model: str) -> str:
    pct = get_context_percentage(transcript_path, model)
    level = get_level(pct)
    suffix = f" {level}" if level else ""
    return f"ctx:{build_bar(pct)} {pct}%{suffix}"


def _status_parts(data: dict[str, object]) -> list[str]:
    model = _field(data.get("model"), ("id", "display_name"), "sonnet")
    workspace = _field(
        data.get("workspace"), ("current_dir", "project_dir"), os.getcwd()
    )
    transcript_path = str(data.get("transcript_path") or "")
    cost = _field(data.get("cost"), ("total_cost_usd",), "0")
    context = _context_part(transcript_path, model)
    optional = (
        get_git_info(workspace),
        format_duration(transcript_path),
        format_cost(cost),
    )
    return [context, *(part for part in optional if part)]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        print("")
        return

    print(" | ".join(_status_parts(data)))


if __name__ == "__main__":
    main()
