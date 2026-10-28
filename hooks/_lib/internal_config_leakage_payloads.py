from __future__ import annotations

import json
import os
import shlex
import sys

from _lib.internal_config_leakage_patterns import (
    INLINE_PAYLOAD_FILE_FLAGS,
    PAYLOAD_FILE_FLAGS,
    PAYLOAD_SIZE_LIMIT,
)

TEXT_FIELDS = ("body", "title", "message")
PULL_REQUEST_KEYS = ("head", "base", "labels", "draft")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def looks_like_publishing_json(content: str) -> bool:
    if not content or not content.strip().startswith("{"):
        return False
    try:
        obj = json.loads(content)
    except ValueError:
        return False
    if "comments" in obj and ("commit_id" in obj or "event" in obj):
        return True
    if _has_text(obj.get("body")):
        return True
    return isinstance(obj.get("title"), str) and any(
        key in obj for key in PULL_REQUEST_KEYS
    )


def _comment_blocks(comments: object) -> list[tuple[str, str]]:
    if not isinstance(comments, list):
        return []
    return [
        (f"comments[{i}].body", c["body"])
        for i, c in enumerate(comments)
        if isinstance(c, dict) and _has_text(c.get("body"))
    ]


def extract_publishing_text_blocks(content: str) -> list[tuple[str, str]]:
    try:
        obj = json.loads(content)
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    top = [(key, obj[key]) for key in TEXT_FIELDS if _has_text(obj.get(key))]
    return [*top, *_comment_blocks(obj.get("comments"))]


def _flag_value_path(value: str) -> str:
    if value.startswith("@"):
        return value[1:]
    if "=" in value and value.split("=", 1)[1].startswith("@"):
        return value.split("=", 1)[1][1:]
    return value


def _payload_flag_paths(tokens: list[str]) -> list[str]:
    paths: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        paths = [
            *paths,
            *(
                tok[len(flag) + 1 :]
                for flag in INLINE_PAYLOAD_FILE_FLAGS
                if tok.startswith(flag + "=")
            ),
        ]
        if tok in PAYLOAD_FILE_FLAGS and i + 1 < len(tokens):
            paths = [*paths, _flag_value_path(tokens[i + 1])]
            i += 2
            continue
        i += 1
    return paths


def extract_referenced_files(cmd: str) -> list[str]:
    try:
        tokens = shlex.split(cmd, comments=False, posix=True)
    except Exception:
        return []
    expanded = (os.path.expanduser(p) for p in _payload_flag_paths(tokens))
    return list(dict.fromkeys(p for p in expanded if p))


def read_payload_file(path: str) -> str | None:
    try:
        if not os.path.isfile(path):
            return None
        if os.path.getsize(path) > PAYLOAD_SIZE_LIMIT:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as error:
        sys.stderr.write(f"internal-config-leakage: cannot read {path}: {error}\n")
        return None
