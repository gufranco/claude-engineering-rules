#!/usr/bin/env python3
"""Enforce the knowledge-note specification on writes into the second brain vault.

Scoped to paths under ``SECOND_BRAIN_VAULT``. Silent everywhere else.

Blocks what is decidable from a single file:

    KN001  a required frontmatter key is missing
    KN002  the fixed "## For future agent" preamble is missing
    KN003  an undated present-tense claim about a volatile subject
    KN004  a wikilink to a note that does not exist and is not marked TBD
    KN005  an edit to an existing file under the immutable raw folder
    KN006  a removal of a vault path outside the trash folder

Whole-graph checks belong to the vault linters, never here. The note grammar
itself lives in ``_lib/knowledge_notes.py`` so the hook and the linters share
one definition.

Rule source: ``rules/knowledge-notes.md``.

Bypass: set ``KNOWLEDGE_NOTE_DISABLE=1`` in a parent shell.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from _lib import knowledge_notes as kn
except ImportError:  # pragma: no cover
    sys.exit(0)

try:
    from _lib.audit_log import record as _audit
except Exception:  # pragma: no cover

    def _audit(**_fields):
        return None


try:
    from _lib.bypass import is_bypassed
except Exception:  # pragma: no cover

    def is_bypassed(_name: str) -> bool:
        return False


try:
    from _lib.output import block as _block
except Exception:  # pragma: no cover
    _block = None


HOOK = "knowledge-note-guard"
ENV_VAR = "KNOWLEDGE_NOTE_DISABLE"
RULE_ANCHOR = "rules/knowledge-notes.md"
MAX_REPORTED = 12
REMOVAL_COMMANDS = ("rm", "unlink", "shred", "trash")

EXPLANATIONS = {
    "KN001": "every note carries date, type, tags, and ai-first so an agent can judge it before reading it",
    "KN002": "the preamble is read first to decide relevance, and the heading string is fixed so it stays greppable",
    "KN003": "an undated present-tense claim about something that moves reads as true forever and quietly becomes a lie",
    "KN004": "a link is a claim, and a link to a note that does not exist is a fabricated one",
    "KN005": "raw sources are immutable, because they are what a corrupted derived note gets rebuilt from",
    "KN006": "the vault has no version control, so retirement means moving to the trash folder",
}

FIXES = {
    "KN001": "add the missing key to the YAML frontmatter block at the top of the note",
    "KN002": 'add "## For future agent" directly after the frontmatter, then two or three sentences on what the note holds, why it was saved, and any staleness caveat',
    "KN003": "stamp the line with an as-of date, rewrite it as a pointer to where truth lives, or move the claim into a dated note where it becomes a snapshot",
    "KN004": "create the target note first, or mark the link TBD on the same line until it exists",
    "KN005": "derive a new note instead of editing the source, or file a corrected copy outside the raw folder",
    "KN006": "move the note into the trash folder with a dated reason instead of removing it",
}


def scan_body(body: str, dated: bool, root: Path) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    titles: set[str] | None = None
    for number, line, under_dated_heading in kn.walk_lines(body):
        if not dated and not under_dated_heading and kn.is_volatile_claim(line):
            findings.append(("KN003", number, line))
        targets = kn.wikilink_targets(line)
        if not targets or kn.TBD.search(line):
            continue
        if titles is None:
            titles = kn.note_titles(root)
        for target in targets:
            if target not in titles:
                findings.append(("KN004", number, f"[[{target}]]"))
    return findings


def check_note(rel: Path, text: str, root: Path) -> list[tuple[str, int, str]]:
    fields = kn.parse_frontmatter(text)
    if fields is None:
        return [("KN001", 1, "no YAML frontmatter block")]
    findings: list[tuple[str, int, str]] = []
    missing = [key for key in kn.REQUIRED_KEYS if key not in fields]
    if missing:
        findings.append(("KN001", 1, "missing key: " + ", ".join(missing)))
    body = kn.body_after_frontmatter(text)
    if kn.PREAMBLE not in body:
        findings.append(("KN002", 1, f"missing the fixed heading {kn.PREAMBLE}"))
    findings.extend(scan_body(body, kn.is_dated_container(rel), root))
    return findings


def apply_edit(current: str, old: str, new: str, replace_all: bool) -> str:
    return current.replace(old, new) if replace_all else current.replace(old, new, 1)


def post_text(tool: str, tool_input: dict, path: Path) -> str | None:
    if tool == "Write":
        return tool_input.get("content")
    try:
        current = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if tool == "Edit":
        return apply_edit(
            current,
            tool_input.get("old_string", ""),
            tool_input.get("new_string", ""),
            bool(tool_input.get("replace_all")),
        )
    for edit in tool_input.get("edits", []) or []:
        current = apply_edit(
            current,
            edit.get("old_string", ""),
            edit.get("new_string", ""),
            bool(edit.get("replace_all")),
        )
    return current


def emit(findings: list[tuple[str, int, str]], rel: Path) -> None:
    codes = sorted({code for code, _, _ in findings})
    reported = [
        f"{rel}:{line} {code}: {text}" for code, line, text in findings[:MAX_REPORTED]
    ]
    if len(findings) > MAX_REPORTED:
        reported.append(f"... and {len(findings) - MAX_REPORTED} more")
    detected = "\n".join(reported)
    why = "\n".join(f"{code}: {EXPLANATIONS[code]}" for code in codes)
    fix = "\n".join(f"{code}: {FIXES[code]}" for code in codes)
    _audit(hook=HOOK, decision="block", codes=codes, path=str(rel))
    if _block is None:  # pragma: no cover
        sys.stderr.write(
            f"BLOCKED by {HOOK} ({RULE_ANCHOR})\n\n{detected}\n\n{why}\n\n{fix}\n"
        )
    else:
        sys.stderr.write(
            _block(
                hook=HOOK,
                rule_anchor=RULE_ANCHOR,
                detected=detected,
                why=why,
                fix=fix,
                bypass_when="the note is a fixture, an imported artifact kept verbatim, or a genuine false positive on the volatile-claim heuristic.",
                decision="FIX-AND-RETRY",
                env_var=ENV_VAR,
                safety="an unspecced note degrades retrieval quietly, and no later gate will catch it.",
            )
        )
    sys.exit(2)


def handle_bash(command: str, root: Path) -> None:
    if not any(word in command.split() for word in REMOVAL_COMMANDS):
        return
    try:
        tokens = shlex.split(command)
    except ValueError:
        return
    for token in tokens:
        if token.startswith("-"):
            continue
        candidate = Path(os.path.expanduser(os.path.expandvars(token)))
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        rel = kn.relative(candidate, root)
        if rel is None or kn.is_exempt(rel):
            continue
        emit([("KN006", 1, f"removal of {rel}")], rel)


def main() -> None:
    if os.environ.get(ENV_VAR) == "1" or is_bypassed(HOOK):
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    root = kn.vault_root()
    if root is None:
        sys.exit(0)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if tool == "Bash":
        handle_bash(tool_input.get("command", "") or "", root)
        sys.exit(0)
    if tool not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)
    raw_path = tool_input.get("file_path")
    if not raw_path:
        sys.exit(0)
    path = Path(raw_path)
    rel = kn.relative(path, root)
    if rel is None or kn.is_exempt(rel):
        sys.exit(0)
    if (
        rel.parts
        and rel.parts[0] == kn.RAW_DIR
        and tool in ("Edit", "MultiEdit")
        and path.exists()
    ):
        emit([("KN005", 1, f"edit to immutable source {rel}")], rel)
    if path.suffix.lower() != ".md":
        sys.exit(0)
    text = post_text(tool, tool_input, path)
    if text is None:
        sys.exit(0)
    findings = check_note(rel, text, root)
    if findings:
        emit(findings, rel)
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
