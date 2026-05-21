#!/usr/bin/env python3
"""
internal-config-leakage.py

PreToolUse hook that blocks references to internal Claude config in external output.
Rule source: ~/.claude/standards/code-review.md "No Internal Config Leakage".

External output channels covered:
  - Bash commands that publish text: gh pr/issue/api, glab mr/issue/api, git commit -m,
    git tag, git notes, slack-cli send.
  - Bash commands that publish via a payload file referenced with --input,
    --body-file, -F file=@..., or @file shorthand. The hook reads the referenced
    file and scans its content.
  - Write/Edit/MultiEdit on Markdown files (.md) and JSON payload files (.json)
    that look like a publishing payload (top-level "body", "comments", "title",
    or "commit_id" + "event").

Patterns flagged:
  - Internal path tokens: ~/.claude/, .claude/<dir>/, rules/<name>.md,
    standards/<name>.md, checklists/checklist.md, rules/index.yml
  - Bare internal file names: CLAUDE.md when cited as authority
  - Conventional Comments labels at line start (issue (blocking):, nitpick:, ...)
  - Internal severity tokens: P0, P1, P2, P3 as standalone scaffolding labels
  - Skill invocation flags: --backend, --frontend, --local, --post, --focus,
    --severity (when treated as authoritative scaffolding rather than legitimate
    code-review subject matter)
  - Internal section headings: "Behavioral Flow Analysis", "Blast Radius Summary",
    "Standards Applied"
  - Category number references and "category N" / "cat N" shorthand

Skipped:
  - Bash commands that do not publish (cat, grep, find, ls, sed, awk, less, head,
    tail, wc, cd, source, python, node, etc.)
  - .md files inside the personal config tree (this directory)

Bypass:
  CONFIG_LEAKAGE_DISABLE=1 (export it in a parent shell; inline assignment does
  not work because the hook reads the command string before assignments take
  effect).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/scripts"))
try:
    from audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


# Bash commands that publish text externally. The hook scans the command text
# AND any payload file referenced with --input, --body-file, -F file=@, or @file.
PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bgit\s+notes\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram)\b"),
]

# Path / file reference leaks.
PATH_LEAK_PATTERNS = [
    (re.compile(r"~/\.claude\b"), "~/.claude path reference"),
    (
        re.compile(r"\.claude/(?:rules|standards|checklists|skills|hooks)/"),
        ".claude/<dir>/ reference",
    ),
    (
        re.compile(r"\b(?:rules|standards|checklists)/[a-z0-9_\-]+\.md\b"),
        "internal markdown reference",
    ),
    (re.compile(r"\bchecklist\.md\b"), "checklist.md reference"),
    (re.compile(r"\brules/index\.yml\b"), "rules/index.yml reference"),
    # Bare CLAUDE.md cited as authority.
    (re.compile(r"\bCLAUDE\.md\b"), "CLAUDE.md reference"),
]

CATEGORY_LEAK_PATTERNS = [
    (
        re.compile(r"\bcategor(?:y|ies)\s*#?\s*\d+\b", re.IGNORECASE),
        "category number reference",
    ),
    (
        re.compile(r"\bcat\.?\s*\d+\b(?!\s*(?:bytes|MB|KB|GB|files|items))"),
        "cat <n> shorthand",
    ),
    (
        re.compile(r"checklist[s]?\s+(?:item|category)", re.IGNORECASE),
        "checklist item/category mention",
    ),
]

# Conventional Comments label prefix at line start.
CONVENTIONAL_LABEL_PATTERN = re.compile(
    r"(?m)^\s*(?:issue\s*\((?:blocking|non-blocking)\)|nitpick|suggestion|question|thought|praise|chore|todo)\s*:",
    re.IGNORECASE,
)

# Skill invocation flags at first-person voice.
SKILL_FLAG_HEAD_PATTERN = re.compile(
    r"\(?`?--(?:backend|frontend|local|post|focus|severity|fix|pict|coverage)`?\)?",
)

# Internal severity tier as standalone heading or label scaffolding.
# Triggers when P0/P1/P2/P3 appears at line start in any of these shapes:
#   - markdown heading: "## P0", "### P1 ..."
#   - bare punctuation: "P0:", "P1.", "P2-"
#   - keyword form: "P0 Blocking", "P1 Should Fix", "P2 Nits"
#   - taxonomy header: "P1 items:", "P2 concerns:", "P0 finding:"
SEVERITY_TIER_PATTERN = re.compile(
    r"(?m)^\s*(?:#+\s+P[0-3]\b|P[0-3]\b(?:\s*[:.\-]"
    r"|\s+(?:blocking|should|nits?|critical|important|optional|minor|major)"
    r"|\s+\w{1,12}:))",
    re.IGNORECASE,
)

# Internal section headings that should never appear in published text.
INTERNAL_SECTION_HEADINGS = [
    "Behavioral Flow Analysis",
    "Blast Radius Summary",
    "Standards Applied",
]
SECTION_HEADING_PATTERN = re.compile(
    r"(?im)^\s*#+\s*(?:" + "|".join(re.escape(h) for h in INTERNAL_SECTION_HEADINGS) + r")\b",
)

SKIPPED_DOCS = (
    "/.claude/CLAUDE.md",
    "/.claude/README.md",
    "/.claude/CHANGELOG.md",
    "/.claude/rules/",
    "/.claude/standards/",
    "/.claude/checklists/",
    "/.claude/hooks/",
    "/.claude/skills/",
    "/.claude/specs/",
    "/.claude/scripts/",
)

# Bash subcommands that never publish and should be skipped wholesale, even if
# their command text accidentally contains a publishing-pattern substring (such
# as documentation strings that mention "gh pr" or "git commit").
NON_PUBLISHING_PREFIXES = (
    "cat ",
    "head ",
    "tail ",
    "less ",
    "ls ",
    "find ",
    "grep ",
    "rg ",
    "sed ",
    "awk ",
    "wc ",
    "echo ",
    "printf ",
    "python ",
    "python3 ",
    "node ",
    "ruby ",
    "go ",
    "rustc ",
    "cargo ",
    "npm ",
    "pnpm ",
    "yarn ",
    "make ",
    "cd ",
    "pwd",
    "source ",
    ". ",
    "rm ",
    "mv ",
    "cp ",
    "mkdir ",
    "touch ",
    "chmod ",
    "chown ",
    "stat ",
    "file ",
    "diff ",
    "tar ",
    "zip ",
    "unzip ",
)


def is_publishing_bash(cmd: str) -> bool:
    """True if the Bash command publishes externally. False for inert commands."""
    if not cmd:
        return False
    stripped = cmd.lstrip()
    for pref in NON_PUBLISHING_PREFIXES:
        if stripped.startswith(pref):
            return False
    return any(p.search(cmd) for p in PUBLISHING_BASH_PATTERNS)


def is_skipped_md_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_DOCS)


def looks_like_publishing_json(content: str) -> bool:
    """True if the JSON content looks like a GitHub/GitLab API publishing payload."""
    if not content or not content.strip().startswith("{"):
        return False
    try:
        obj = json.loads(content)
    except Exception:
        return False
    if not isinstance(obj, dict):
        return False
    # Review payload
    if "comments" in obj and ("commit_id" in obj or "event" in obj):
        return True
    # PR / issue / release creation or update with a body
    if isinstance(obj.get("body"), str) and obj["body"].strip():
        return True
    if isinstance(obj.get("title"), str) and (
        "head" in obj or "base" in obj or "labels" in obj or "draft" in obj
    ):
        return True
    return False


def extract_publishing_text_blocks(content: str) -> list[tuple[str, str]]:
    """Pull human-prose fields from a publishing JSON payload.

    Returns list of (field_label, text) tuples for each body/title/message
    discovered. Scanning these as separate text blocks lets line-anchored
    patterns (Conventional Comments labels, severity tier headings) hit on
    the actual prose rather than the surrounding JSON syntax.
    """
    out: list[tuple[str, str]] = []
    try:
        obj = json.loads(content)
    except Exception:
        return out
    if not isinstance(obj, dict):
        return out

    if isinstance(obj.get("body"), str) and obj["body"].strip():
        out.append(("body", obj["body"]))
    if isinstance(obj.get("title"), str) and obj["title"].strip():
        out.append(("title", obj["title"]))
    if isinstance(obj.get("message"), str) and obj["message"].strip():
        out.append(("message", obj["message"]))

    comments = obj.get("comments")
    if isinstance(comments, list):
        for i, c in enumerate(comments):
            if not isinstance(c, dict):
                continue
            b = c.get("body")
            if isinstance(b, str) and b.strip():
                out.append((f"comments[{i}].body", b))

    return out


PAYLOAD_FILE_FLAGS = (
    "--input",
    "--body-file",
    "--file",
    "-F",
    "--form",
    "--data-binary",
    "--data",
    "-d",
)


def extract_referenced_files(cmd: str) -> list[str]:
    """Best-effort extraction of payload file paths referenced by the command."""
    paths: list[str] = []
    try:
        tokens = shlex.split(cmd, comments=False, posix=True)
    except Exception:
        return paths

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # --input=PATH form
        for flag in ("--input", "--body-file", "--file"):
            if tok.startswith(flag + "="):
                paths.append(tok[len(flag) + 1 :])
        # --input PATH form
        if tok in PAYLOAD_FILE_FLAGS and i + 1 < len(tokens):
            nxt = tokens[i + 1]
            # @file shorthand for curl: -d @file or -F field=@file
            if nxt.startswith("@"):
                paths.append(nxt[1:])
            elif "=" in nxt and nxt.split("=", 1)[1].startswith("@"):
                paths.append(nxt.split("=", 1)[1][1:])
            else:
                paths.append(nxt)
            i += 2
            continue
        i += 1

    # Resolve relative paths and dedupe.
    resolved: list[str] = []
    seen = set()
    for p in paths:
        p = os.path.expanduser(p)
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        resolved.append(p)
    return resolved


def read_payload_file(path: str) -> str | None:
    """Read a payload file if it exists and is reasonably small."""
    try:
        if not os.path.isfile(path):
            return None
        if os.path.getsize(path) > 5 * 1024 * 1024:  # 5 MB cap
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, str, str]]:
    """Return a list of (source_label, path_or_field, content_kind, content) tuples."""
    out: list[tuple[str, str, str, str]] = []
    fp = tool_input.get("file_path", "") or ""

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        if not isinstance(cmd, str) or not is_publishing_bash(cmd):
            return out
        out.append(("bash", "command", "command", cmd))
        # Follow --input/--body-file/--file references and scan the file contents
        # too, so a clean command that references a leaky payload still gets blocked.
        for ref in extract_referenced_files(cmd):
            payload = read_payload_file(ref)
            if payload is None:
                continue
            # If it parses as a publishing JSON, expand each body/title/comment
            # field so line-anchored patterns hit on the prose, not the JSON.
            blocks = extract_publishing_text_blocks(payload)
            if blocks:
                for label, text in blocks:
                    out.append((f"bash-payload:{ref}", label, "payload", text))
            else:
                out.append(("bash-payload", ref, "payload", payload))

    elif tool in ("Write", "Edit", "MultiEdit"):
        if is_skipped_md_path(fp):
            return out
        kind = ""
        ext = fp.lower()
        if ext.endswith(".md"):
            kind = "markdown"
        elif ext.endswith(".json"):
            kind = "json-maybe"
        else:
            return out

        if tool == "Write":
            content = tool_input.get("content", "")
            if isinstance(content, str):
                if kind == "json-maybe":
                    if not looks_like_publishing_json(content):
                        return out
                    # Expand prose fields for line-anchored scanning.
                    blocks = extract_publishing_text_blocks(content)
                    if blocks:
                        for label, text in blocks:
                            out.append((fp, label, "payload", text))
                    else:
                        out.append((fp, "content", "payload", content))
                else:
                    out.append((fp, "content", "markdown", content))
        elif tool == "Edit":
            content = tool_input.get("new_string", "")
            if isinstance(content, str):
                if kind == "json-maybe":
                    out.append((fp, "new_string", "payload", content))
                else:
                    out.append((fp, "new_string", "markdown", content))
        elif tool == "MultiEdit":
            for i, edit in enumerate(tool_input.get("edits", []) or []):
                if isinstance(edit, dict):
                    content = edit.get("new_string", "")
                    if isinstance(content, str):
                        out.append((fp, f"edits[{i}].new_string", "markdown" if kind == "markdown" else "payload", content))

    return out


def find_leaks(text: str, content_kind: str) -> list[str]:
    """Return list of human-readable leak descriptions found in the text."""
    hits: list[str] = []

    def add(label: str, m: re.Match[str]) -> None:
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        snippet = text[start:end].replace("\n", " | ")
        hits.append(f"{label}: ...{snippet}...")

    for pat, label in PATH_LEAK_PATTERNS + CATEGORY_LEAK_PATTERNS:
        m = pat.search(text)
        if m:
            add(label, m)

    m = CONVENTIONAL_LABEL_PATTERN.search(text)
    if m:
        add("Conventional Comments label prefix", m)

    m = SEVERITY_TIER_PATTERN.search(text)
    if m:
        add("internal severity tier (P0/P1/P2 scaffolding)", m)

    m = SECTION_HEADING_PATTERN.search(text)
    if m:
        add("internal section heading", m)

    if content_kind in ("payload", "markdown"):
        head = text[:300]
        m = SKILL_FLAG_HEAD_PATTERN.search(head)
        if m:
            head_lower = head.lower()
            meta_words = (
                "review",
                "this pr",
                "this mr",
                "audit",
                "scope",
                "out of scope",
                "skimmed",
                "looked through",
            )
            if any(w in head_lower for w in meta_words):
                add("skill invocation flag in review preamble", m)

    return hits


def main() -> int:
    if os.environ.get("CONFIG_LEAKAGE_DISABLE") == "1":
        _audit(
            hook="internal-config-leakage",
            decision="bypass",
            bypass_env="CONFIG_LEAKAGE_DISABLE",
        )
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    findings: list[str] = []
    for source_label, path_or_field, content_kind, text in items:
        hits = find_leaks(text, content_kind)
        if hits:
            findings.append(f"  - {path_or_field} ({source_label}):")
            findings.extend(f"      {h}" for h in hits[:6])

    if not findings:
        return 0

    print(
        "Blocked: internal Claude config or templated scaffolding leaking into "
        'external output. Rule: ~/.claude/standards/code-review.md "No Internal '
        'Config Leakage".\n'
        + "\n".join(findings)
        + "\n\nFix: rewrite the message so it reads as if a human engineer wrote it. "
        "State the engineering reason directly. Strip Conventional Comments labels "
        "(`issue (blocking):`, `nitpick:`, etc.), internal severity tiers (P0/P1/P2), "
        "skill invocation flags (--backend/--frontend/--local), and references to "
        "personal config paths.\n"
        "Bypass (when editing the config itself): export CONFIG_LEAKAGE_DISABLE=1 "
        "in a parent shell.",
        file=sys.stderr,
    )
    _audit(
        hook="internal-config-leakage",
        decision="block",
        tool=tool,
        reason="claude config or templated scaffolding leakage",
        command_excerpt=" | ".join(findings)[:240] if findings else None,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
