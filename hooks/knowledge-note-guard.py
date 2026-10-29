#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.shell_segments import command_head, quoted_segments  # noqa: E402

from _lib import knowledge_notes as kn  # noqa: E402

from _lib.audit_log import record as _audit  # noqa: E402


from _lib.bypass import is_bypassed  # noqa: E402


from _lib.output import block as _block  # noqa: E402

from _lib import project_workspace as pw  # noqa: E402


HOOK = "knowledge-note-guard"
ENV_VAR = "KNOWLEDGE_NOTE_DISABLE"
RULE_ANCHOR = "rules/knowledge-notes.md"
MAX_REPORTED = 12
REMOVAL_COMMANDS = ("rm", "unlink", "shred", "trash")

EXPLANATIONS = {
    "KN001": "every note carries date, type, tags, and ai-first so an agent can judge it before reading it",
    "KN002": "the preamble is read first to decide relevance, and the heading string is fixed so it stays greppable",
    "KN003": "an undated present-tense claim about something that moves reads as true forever and quietly becomes a lie",
    "FRESH-3": "a pointer whose target is prose or a command cannot be resolved later, which is the only reason the pointer form is allowed in place of a stamp",
    "KN004": "a link is a claim, and a link to a note that does not exist is a fabricated one",
    "KN005": "raw sources are immutable, because they are what a corrupted derived note gets rebuilt from",
    "KN006": "the vault has no version control, so retirement means moving to the trash folder",
}

FIXES = {
    "KN001": "add the missing key to the YAML frontmatter block at the top of the note",
    "KN002": 'add "## For future agent" directly after the frontmatter, then two or three sentences on what the note holds, why it was saved, and any staleness caveat',
    "KN003": "stamp the line with an as-of date, rewrite it as a pointer to where truth lives, or move the claim into a dated note where it becomes a snapshot",
    "FRESH-3": "give the pointer a URL or a typed id such as linear:TICKET-123",
    "KN004": "create the target note first, or mark the link TBD on the same line until it exists",
    "KN005": "derive a new note instead of editing the source, or file a corrected copy outside the raw folder",
    "KN006": "move the note into the trash folder with a dated reason instead of removing it",
}


def scan_body(
    body: str, dated: bool, root: Path, *, timeless: bool = False
) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    titles: set[str] | None = None
    for number, line, under_dated_heading in kn.walk_lines(body):
        if not dated and not under_dated_heading and kn.POINTER.search(line):
            if not kn.pointer_has_target(line):
                findings.append(("FRESH-3", number, line))
        elif (
            not dated
            and not timeless
            and not under_dated_heading
            and kn.is_volatile_claim(line)
        ):
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
    findings.extend(
        scan_body(
            body, kn.is_dated_container(rel), root, timeless=kn.is_timeless(fields)
        )
    )
    return findings


def introduced(
    findings: list[tuple[str, int, str]], before: list[tuple[str, int, str]]
) -> list[tuple[str, int, str]]:
    remaining = Counter((code, text) for code, _, text in before)
    fresh: list[tuple[str, int, str]] = []
    for code, number, text in findings:
        if remaining[(code, text)] > 0:
            remaining[(code, text)] -= 1
        else:
            fresh.append((code, number, text))
    return fresh


def apply_edit(current: str, old: str, new: str, replace_all: bool) -> str:
    return current.replace(old, new) if replace_all else current.replace(old, new, 1)


def read_current(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def post_text(tool: str, tool_input: dict, current: str | None) -> str | None:
    if tool == "Write":
        return tool_input.get("content")
    if current is None:
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


def _resolve(token: str, cwd: Path) -> Path:
    candidate = Path(os.path.expanduser(os.path.expandvars(token)))
    return candidate if candidate.is_absolute() else cwd / candidate


def _removed_operands(tokens: list[str], root: Path, cwd: Path) -> list[str]:
    base, args = command_head(tokens)
    operands = [arg for arg in args[1:] if not arg.startswith("-")]
    if base in REMOVAL_COMMANDS:
        return operands
    if base != "mv" or len(operands) < 2:
        return []
    staying = kn.relative(_resolve(operands[-1], cwd), root) is not None
    return [] if staying else operands[:-1]


def handle_bash(command: str, root: Path, cwd: Path) -> None:
    for tokens in quoted_segments(command):
        for token in _removed_operands(tokens, root, cwd):
            rel = kn.relative(_resolve(token, cwd), root)
            if rel is None or kn.is_exempt(rel):
                continue
            emit([("KN006", 1, f"removal of {rel}")], rel)


def main() -> None:
    if os.environ.get(ENV_VAR) == "1" or is_bypassed(HOOK):
        sys.exit(0)
    payload = read_hook_payload("knowledge-note-guard")
    root = kn.vault_root()
    if root is None:
        sys.exit(0)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if tool == "Bash":
        cwd = Path(str(payload.get("cwd") or Path.cwd()))
        handle_bash(tool_input.get("command", "") or "", root, cwd)
        sys.exit(0)
    if tool not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)
    raw_path = tool_input.get("file_path")
    if not raw_path:
        sys.exit(0)
    handle_edit(tool, tool_input, Path(raw_path), root)


def in_workspace(rel: Path, root: Path) -> bool:
    if pw is None or not rel.parts or rel.parts[0] not in pw.WORKSPACE_CANDIDATES:
        return False
    try:
        return rel.parts[0] in pw.managed_entries(root)
    except pw.WorkspaceError:
        return False


def handle_edit(tool: str, tool_input: dict, path: Path, root: Path) -> None:
    rel = kn.relative(path, root)
    if rel is None or kn.is_exempt(rel) or in_workspace(rel, root):
        sys.exit(0)
    if rel.parts and rel.parts[0] == kn.RAW_DIR and path.exists():
        emit([("KN005", 1, f"edit to immutable source {rel}")], rel)
    if path.suffix.lower() != ".md":
        sys.exit(0)
    current = read_current(path)
    text = post_text(tool, tool_input, current)
    if text is None:
        sys.exit(0)
    findings = check_note(rel, text, root)
    if findings and current is not None:
        findings = introduced(findings, check_note(rel, current, root))
    if findings:
        emit(findings, rel)
    sys.exit(0)


if __name__ == "__main__":
    main()
