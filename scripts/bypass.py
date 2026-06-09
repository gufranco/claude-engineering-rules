#!/usr/bin/env python3
"""CLI for the in-session hook bypass registry.


Usage:

    python scripts/bypass.py set <hook> [--ttl 600] [--reason TEXT]
    python scripts/bypass.py clear [hook]
    python scripts/bypass.py list

Wraps `hooks/_lib/bypass_writer.set_bypass` and `clear_bypass` so the
assistant can engage and release a bypass through Bash without crafting
JSON by hand. Both bypass channels (env var and this file registry)
coexist; either grants a pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass import STATE_PATH  # noqa: E402
from _lib.bypass_writer import (  # noqa: E402
    DEFAULT_TTL_SECONDS,
    clear_bypass,
    set_bypass,
)


def _cmd_set(args: argparse.Namespace) -> int:
    path = set_bypass(args.hook, ttl_seconds=args.ttl, reason=args.reason)
    print(f"bypass engaged: hook={args.hook!r} ttl={args.ttl}s file={path}")
    return 0


def _cmd_clear(args: argparse.Namespace) -> int:
    removed = clear_bypass(args.hook)
    target = args.hook if args.hook else "*all*"
    print(f"bypass cleared: hook={target!r} removed={removed}")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    if not STATE_PATH.exists():
        print("no bypass registry (file does not exist)")
        return 0
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read registry: {exc}", file=sys.stderr)
        return 1
    entries = data.get("bypasses") if isinstance(data, dict) else None
    if not entries:
        print("no active bypasses")
        return 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hook = entry.get("hook", "?")
        expires = entry.get("expires_at", "?")
        reason = entry.get("reason", "")
        suffix = f" reason={reason!r}" if reason else ""
        print(f"hook={hook!r} expires_at={expires}{suffix}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="manage the in-session hook bypass registry"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    set_p = sub.add_parser("set", help="engage a bypass entry for a hook")
    set_p.add_argument("hook", help='hook name or "*" for wildcard')
    set_p.add_argument(
        "--ttl",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help=f"seconds until expiry (clamped to [60, 3600]; default {DEFAULT_TTL_SECONDS})",
    )
    set_p.add_argument(
        "--reason",
        default=None,
        help="free-text justification stored alongside the entry",
    )
    set_p.set_defaults(func=_cmd_set)

    clear_p = sub.add_parser("clear", help="remove one entry or all entries")
    clear_p.add_argument(
        "hook", nargs="?", default=None, help="hook name; omit to clear all"
    )
    clear_p.set_defaults(func=_cmd_clear)

    list_p = sub.add_parser("list", help="show active bypass entries")
    list_p.set_defaults(func=_cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
