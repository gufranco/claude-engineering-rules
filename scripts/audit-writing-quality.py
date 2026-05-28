#!/usr/bin/env python3
"""audit-writing-quality.py

One-shot scanner for drift in ~/.claude/ markdown files. Surfaces violations
of the current writing rules in older content that predates them.

Categories:
  banned-em-dash       em dash codepoint in prose
  banned-box-drawing   box-drawing codepoints in prose
  banned-emoji         emoji or decorative unicode in prose
  parens-in-prose      parentheses outside code, tables, headings, links
  banned-opener        sycophantic openers
  banned-closer        rhetorical closers
  banned-hedge         hedge phrases
  banned-transition    weak transitions
  banned-fluff         fluff adjectives
  banned-tactical      tactical hyperbole
  should-bullet        bullet items starting with Should or should
  vague-quantifier     often, usually, sometimes, a few, several
  stale-link           markdown link to a path that does not exist

Output:
  audit-findings.md     grouped by file, ordered by finding count
  audit-findings.jsonl  one JSON object per finding
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CLAUDE_ROOT = Path.home() / ".claude"

SKIP_DIR_NAMES = {
    "specs",
    "memory",
    "plans",
    "cache",
    "node_modules",
    "htmlcov",
    "_subprocess_cov",
    "__pycache__",
}


# Detection codepoints constructed via chr() so this source file itself
# does not contain the banned characters. The runtime patterns are
# equivalent to the literal forms used in hooks/banned-prose-chars.py.
EM_DASH = chr(0x2014)
BOX_DRAWING_RE = re.compile("[" + chr(0x2500) + "-" + chr(0x257F) + "]")
EMOJI_RE = re.compile(
    "["
    + chr(0x1F300)
    + "-"
    + chr(0x1FAFF)
    + chr(0x2600)
    + "-"
    + chr(0x27BF)
    + chr(0x1F1E6)
    + "-"
    + chr(0x1F1FF)
    + chr(0xFE0F)
    + chr(0x200D)
    + "]"
)

BULLET_SHOULD_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+[Ss]hould\s+\S",
    re.MULTILINE,
)

VAGUE_QUANTIFIERS = [
    "often",
    "usually",
    "sometimes",
    "a few",
    "several",
]
# Only flag vague quantifiers in a normative claim position: a bullet whose
# subject is the bullet itself (the word starts the claim sentence). Plain
# prose use of "often" or "usually" as connectors is allowed.
VAGUE_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(?:"
    + "|".join(re.escape(p) for p in VAGUE_QUANTIFIERS)
    + r")\b",
    re.IGNORECASE,
)

OPENERS = [
    "Great question!",
    "Sure!",
    "Absolutely!",
    "Of course!",
    "That's a great point",
    "That is a great point",
    "Perfect!",
    "Excellent!",
    "Wonderful!",
]
CLOSERS = [
    "Let me know if you need anything else",
    "Let me know if you have any questions",
    "Hope this helps",
    "Hope that helps",
    "Feel free to ask",
    "Feel free to reach out",
    "Happy to help",
]
HEDGES = [
    "It's worth noting",
    "It is worth noting",
    "It should be noted",
    "It's important to mention",
    "It is important to mention",
    "It is important to note",
    "Keep in mind that",
]
TRANSITIONS = [
    "That said,",
    "With that in mind,",
    "Having said that,",
    "On that note,",
]
FLUFF = [
    "robust",
    "comprehensive",
    "seamless",
    "elegant",
    "powerful",
    "streamlined",
    "cutting-edge",
    "leverage",
    "best-in-class",
    "world-class",
    "game-changing",
    "synergy",
    "synergies",
]
TACTICAL = [
    "quick fix",
    "quick win",
    "temporary fix",
    "temporary workaround",
    "temporary hack",
    "band-aid",
    "bandaid",
    "we'll fix later",
    "we will fix later",
    "cleanup later",
    "clean up later",
    "fix it later",
]


def _build_phrase_re(phrases: list[str], word_boundary: bool) -> re.Pattern[str]:
    body = "|".join(re.escape(p) for p in phrases)
    if word_boundary:
        return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)
    return re.compile(rf"(?:{body})", re.IGNORECASE)


PHRASE_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("banned-opener", _build_phrase_re(OPENERS, False)),
    ("banned-closer", _build_phrase_re(CLOSERS, False)),
    ("banned-hedge", _build_phrase_re(HEDGES, False)),
    ("banned-transition", _build_phrase_re(TRANSITIONS, False)),
    ("banned-fluff", _build_phrase_re(FLUFF, True)),
    ("banned-tactical", _build_phrase_re(TACTICAL, False)),
]


MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
# Image badges like [![alt](src)](href). The audit otherwise sees the inner
# (src) as a paren and the outer (href) as another paren.
MD_IMAGE_BADGE_RE = re.compile(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)")
PAREN_RE = re.compile(r"\(([^()\n]{1,200})\)")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def _fence_match(stripped: str) -> tuple[str, bool]:
    """Return (fence marker, is_closing_capable). A closing fence cannot have
    an info string per CommonMark. A bare fence with no info string can
    close any open fence whose marker length is less than or equal to it."""
    m = FENCE_RE.match(stripped)
    if not m:
        return "", False
    marker = m.group(1)
    info = m.group(2).strip()
    return marker, info == ""


# Carve-outs allowed by rules/writing-precision.md "No parentheses in prose".
# When the inner text of a paren matches any of these patterns the audit
# does not flag the paren as a violation.
PAREN_CARVEOUT_RES: list[re.Pattern[str]] = [
    # (default: X) or (default X) or just (default)
    re.compile(r"^\s*default\b", re.IGNORECASE),
    # Uppercase emphasis labels: (REQUIRED), (OPTIONAL), (RECOMMENDED)
    # plus the same labels followed by a comma and a short conditional clause.
    re.compile(
        r"^\s*(REQUIRED|OPTIONAL|RECOMMENDED|REQUIRED DEFAULT|RECOMMENDED DEFAULT)\b"
    ),
    # Clarifiers: (e.g., X) and (i.e., X)
    re.compile(r"^\s*e\.g\.", re.IGNORECASE),
    re.compile(r"^\s*i\.e\.", re.IGNORECASE),
    # Cross-references: (see X) and (per X)
    re.compile(r"^\s*(see|per)\s+", re.IGNORECASE),
    # Big-O and complexity notation: (n), (1), (n^2), (n log n), (log n),
    # (k * n), (k log n), (log_b(a)), (n^(log_b(a))), (log k), (a), etc.
    re.compile(
        r"^\s*"
        r"(?:"
        r"[a-z]|"  # single math variable like (a)
        r"\d+|"  # plain number like (1) or (16)
        r"n\^\d+|n\^\([^)]+\)|n\^d|"  # n^N variants
        r"\w+\s*\*\s*\w+|"  # variable times variable like k * n
        r"[nk]\s+log\s+[nk]|"  # n log n, k log k
        r"log\s+[nk]|"  # log n, log k
        r"log_\w+\s*\([^)]+\)|"  # log_b(a)
        r"n\^?\(log_\w+\(\w+\)\)"  # n^(log_b(a))
        r")"
        r"\s*$"
    ),
    # CSS media-query feature patterns inside docs: (min-width: ...),
    # (prefers-color-scheme: ...), (orientation: ...), etc.
    re.compile(
        r"^\s*(min-width|max-width|prefers-color-scheme|orientation|hover|pointer):\s+"
    ),
]


def _is_paren_carveout(inner: str) -> bool:
    return any(p.search(inner) for p in PAREN_CARVEOUT_RES)


@dataclass
class Finding:
    file: str
    line: int
    category: str
    detail: str
    snippet: str


def snippet_of(line: str, length: int = 100) -> str:
    text = line.strip()
    if len(text) > length:
        return text[:length] + "..."
    return text


def scan_text(rel_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    in_code_fence = False
    fence_marker = ""  # Track the opening fence so nested fences work.
    in_frontmatter = False

    # YAML frontmatter is the block between two `---` markers at the very
    # top of the file. Skip it.
    if lines and lines[0].strip() == "---":
        in_frontmatter = True

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if in_frontmatter:
            if i > 1 and stripped == "---":
                in_frontmatter = False
            continue
        marker, can_close = _fence_match(stripped)
        if marker:
            if not in_code_fence:
                # New opener
                in_code_fence = True
                fence_marker = marker
                continue
            # Already in a fence: only close if marker is bare and matches
            # the opener (same char type, length >= opener).
            if (
                can_close
                and marker[0] == fence_marker[0]
                and len(marker) >= len(fence_marker)
            ):
                in_code_fence = False
                fence_marker = ""
            # If we get here while in_code_fence and can't close, the line is
            # just content inside the fenced block (e.g. ```mermaid as content)
            continue
        if in_code_fence:
            continue

        # Strip image badges, then regular links, then inline code spans, in
        # that order. Image badges (`[![alt](src)](href)`) have nested
        # brackets and parens that confuse the simpler link regex.
        line_no_badges = MD_IMAGE_BADGE_RE.sub("", line)
        line_no_links_only = MD_LINK_RE.sub("", line_no_badges)
        line_no_code = INLINE_CODE_RE.sub("", line_no_links_only)

        if EM_DASH in line_no_code:
            findings.append(
                Finding(rel_path, i, "banned-em-dash", "U+2014", snippet_of(line))
            )

        m = BOX_DRAWING_RE.search(line_no_code)
        if m:
            findings.append(
                Finding(
                    rel_path,
                    i,
                    "banned-box-drawing",
                    repr(m.group(0)),
                    snippet_of(line),
                )
            )

        m = EMOJI_RE.search(line_no_code)
        if m:
            findings.append(
                Finding(
                    rel_path,
                    i,
                    "banned-emoji",
                    repr(m.group(0)),
                    snippet_of(line),
                )
            )

        if not stripped.startswith("|") and not stripped.startswith("#"):
            for pm in PAREN_RE.finditer(line_no_code):
                inner = pm.group(1).strip()
                if not inner:
                    continue
                if _is_paren_carveout(inner):
                    continue
                findings.append(
                    Finding(
                        rel_path,
                        i,
                        "parens-in-prose",
                        inner[:60],
                        snippet_of(line),
                    )
                )
                break

        # Skip banned-phrase detection on lines that are documenting the
        # banned phrases themselves. These appear in CLAUDE.md and similar
        # rule files that quote the patterns by name.
        is_phrase_doc = bool(
            re.match(
                r"^\s*-\s*\*\*(Openers|Closers|Hedges|Transitions|Fluff(?:\s+adjectives)?|Tactical(?:\s+hyperbole)?|Echoing|Banned)",
                line,
                re.IGNORECASE,
            )
        )
        if not is_phrase_doc:
            for label, pat in PHRASE_CATEGORIES:
                m = pat.search(line_no_code)
                if m:
                    findings.append(
                        Finding(
                            rel_path,
                            i,
                            label,
                            repr(m.group(0)),
                            snippet_of(line),
                        )
                    )

        if BULLET_SHOULD_RE.match(line):
            findings.append(
                Finding(
                    rel_path,
                    i,
                    "should-bullet",
                    "ambiguous obligation",
                    snippet_of(line),
                )
            )

        m = VAGUE_RE.search(line_no_code)
        if m:
            findings.append(
                Finding(
                    rel_path,
                    i,
                    "vague-quantifier",
                    repr(m.group(0)),
                    snippet_of(line),
                )
            )

    return findings


def scan_links(
    rel_path: str,
    path: Path,
    text: str,
    repo_root: Path | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    # Mask code fences and inline code so links inside them are ignored.
    masked = _mask_code_regions(text)
    for m in MD_LINK_RE.finditer(masked):
        target = m.group(1)
        if target.startswith("http://") or target.startswith("https://"):
            continue
        if target.startswith("#") or target.startswith("mailto:"):
            continue
        clean_target = target.split("#")[0]
        if not clean_target:
            continue
        resolved = (path.parent / clean_target).resolve()
        if resolved.exists():
            continue
        # Fallback: try repo-root resolution for links that use
        # repo-root-relative paths instead of file-relative.
        if repo_root is not None:
            root_resolved = (repo_root / clean_target).resolve()
            if root_resolved.exists():
                continue
        line_no = text[: m.start()].count("\n") + 1
        findings.append(
            Finding(
                rel_path,
                line_no,
                "stale-link",
                target,
                m.group(0),
            )
        )
    return findings


def _mask_code_regions(text: str) -> str:
    """Return text with code-fence, inline-code, and YAML-frontmatter regions
    blanked out. Code spans become spaces so character positions stay aligned.
    Supports nested fences: a 4-backtick block can contain a 3-backtick block.
    """
    result: list[str] = []
    in_fence = False
    fence_marker = ""
    in_frontmatter = False
    raw_lines = text.splitlines(keepends=True)
    if raw_lines and raw_lines[0].strip() == "---":
        in_frontmatter = True
    for idx, line in enumerate(raw_lines):
        stripped = line.strip()
        if in_frontmatter:
            result.append(" " * len(line))
            if idx > 0 and stripped == "---":
                in_frontmatter = False
            continue
        marker, can_close = _fence_match(stripped)
        if marker:
            if not in_fence:
                in_fence = True
                fence_marker = marker
                result.append(" " * len(line))
                continue
            if (
                can_close
                and marker[0] == fence_marker[0]
                and len(marker) >= len(fence_marker)
            ):
                in_fence = False
                fence_marker = ""
            result.append(" " * len(line))
            continue
        if in_fence:
            result.append(" " * len(line))
            continue
        # Mask inline code spans on this line.
        result.append(INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line))
    return "".join(result)


def walk_markdown(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".")
        ]
        for name in filenames:
            if name.lower().endswith(".md"):
                yield Path(dirpath) / name


def write_jsonl(findings: list[Finding], out: Path) -> None:
    with out.open("w", encoding="utf-8") as f:
        for finding in findings:
            f.write(json.dumps(asdict(finding)) + "\n")


def write_markdown(findings: list[Finding], out: Path) -> None:
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_file[finding.file].append(finding)

    sorted_files = sorted(by_file.items(), key=lambda kv: -len(kv[1]))
    total = len(findings)
    cat_counts = Counter(f.category for f in findings)

    lines: list[str] = []
    lines.append("# Audit Findings")
    lines.append("")
    lines.append(f"Total: {total} findings across {len(by_file)} files.")
    lines.append("")
    lines.append("## Summary by Category")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {cat} | {n} |")
    lines.append("")
    lines.append("## Per-File Findings")
    lines.append("")
    for filename, items in sorted_files:
        lines.append(f"### {filename}")
        lines.append("")
        lines.append(f"{len(items)} findings.")
        lines.append("")
        lines.append("| Line | Category | Detail | Snippet |")
        lines.append("|------|----------|--------|---------|")
        for finding in sorted(items, key=lambda f: f.line):
            snip = finding.snippet.replace("|", r"\|")
            detail = finding.detail.replace("|", r"\|")
            lines.append(f"| {finding.line} | {finding.category} | {detail} | {snip} |")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit writing quality drift.")
    parser.add_argument(
        "--out-dir",
        default="specs/2026-05-27-normative-keywords",
        help="Directory for output files.",
    )
    parser.add_argument(
        "--root",
        default=str(CLAUDE_ROOT),
        help="Root directory to scan.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    findings: list[Finding] = []
    for path in walk_markdown(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(rel, text))
        findings.extend(scan_links(rel, path, text, root))

    jsonl_path = out_dir / "audit-findings.jsonl"
    md_path = out_dir / "audit-findings.md"
    write_jsonl(findings, jsonl_path)
    write_markdown(findings, md_path)

    print(
        f"Wrote {len(findings)} findings to {md_path} and {jsonl_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
