#!/usr/bin/env python3
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from writing_quality_phrases import (  # noqa: E402
    CLOSERS,
    FLUFF,
    HEDGES,
    OPENERS,
    TACTICAL,
    TRANSITIONS,
    VAGUE_QUANTIFIERS,
)

CLAUDE_ROOT = Path(__file__).resolve().parents[2]

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

VAGUE_RE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(?:"
    + "|".join(re.escape(p) for p in VAGUE_QUANTIFIERS)
    + r")\b",
    re.IGNORECASE,
)


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
MD_IMAGE_BADGE_RE = re.compile(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)")
PAREN_RE = re.compile(r"\(([^()\n]{1,200})\)")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def _fence_match(stripped: str) -> tuple[str, bool]:
    m = FENCE_RE.match(stripped)
    if not m:
        return "", False
    marker = m.group(1)
    info = m.group(2).strip()
    return marker, info == ""


PAREN_CARVEOUT_RES: list[re.Pattern[str]] = [
    re.compile(r"^\s*default\b", re.IGNORECASE),
    re.compile(
        r"^\s*(REQUIRED|OPTIONAL|RECOMMENDED|REQUIRED DEFAULT|RECOMMENDED DEFAULT)\b"
    ),
    re.compile(r"^\s*e\.g\.", re.IGNORECASE),
    re.compile(r"^\s*i\.e\.", re.IGNORECASE),
    re.compile(r"^\s*(see|per)\s+", re.IGNORECASE),
    re.compile(
        r"^\s*"
        r"(?:"
        r"[a-z]|"
        r"\d+|"
        r"n\^\d+|n\^\([^)]+\)|n\^d|"
        r"\w+\s*\*\s*\w+|"
        r"[nk]\s+log\s+[nk]|"
        r"log\s+[nk]|"
        r"log_\w+\s*\([^)]+\)|"
        r"n\^?\(log_\w+\(\w+\)\)"
        r")"
        r"\s*$"
    ),
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


PHRASE_DOC_RE = re.compile(
    r"^\s*-\s*\*\*(Openers|Closers|Hedges|Transitions|Fluff(?:\s+adjectives)?|Tactical(?:\s+hyperbole)?|Echoing|Banned)",
    re.IGNORECASE,
)

CHAR_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("banned-box-drawing", BOX_DRAWING_RE),
    ("banned-emoji", EMOJI_RE),
)

VAGUE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (("vague-quantifier", VAGUE_RE),)


@dataclass(frozen=True)
class _MaskState:
    in_frontmatter: bool
    fence: str


def _fence_after(fence: str, marker: str, can_close: bool) -> str:
    if not fence:
        return marker
    closes = can_close and marker[0] == fence[0] and len(marker) >= len(fence)
    return "" if closes else fence


def _next_mask_state(
    state: _MaskState, stripped: str, first: bool
) -> tuple[_MaskState, bool]:
    if state.in_frontmatter:
        closes = not first and stripped == "---"
        return _MaskState(not closes, state.fence), True
    marker, can_close = _fence_match(stripped)
    if marker:
        return _MaskState(False, _fence_after(state.fence, marker, can_close)), True
    return state, bool(state.fence)


def _code_line_mask(lines: list[str]) -> list[bool]:
    state = _MaskState(bool(lines) and lines[0].strip() == "---", "")
    mask: list[bool] = []
    for idx, line in enumerate(lines):
        state, masked = _next_mask_state(state, line.strip(), idx == 0)
        mask.append(masked)
    return mask


def _regex_hits(
    prose: str, rules: Iterable[tuple[str, re.Pattern[str]]]
) -> list[tuple[str, str]]:
    return [
        (label, repr(m.group(0))) for label, pat in rules if (m := pat.search(prose))
    ]


def _char_hits(prose: str) -> list[tuple[str, str]]:
    em_dash = [("banned-em-dash", "U+2014")] if EM_DASH in prose else []
    return [*em_dash, *_regex_hits(prose, CHAR_RULES)]


def _paren_hits(stripped: str, prose: str) -> list[tuple[str, str]]:
    if stripped.startswith("|") or stripped.startswith("#"):
        return []
    for pm in PAREN_RE.finditer(prose):
        inner = pm.group(1).strip()
        if inner and not _is_paren_carveout(inner):
            return [("parens-in-prose", inner[:60])]
    return []


def _phrase_hits(line: str, prose: str) -> list[tuple[str, str]]:
    if PHRASE_DOC_RE.match(line):
        return []
    return _regex_hits(prose, PHRASE_CATEGORIES)


def _should_hits(line: str) -> list[tuple[str, str]]:
    if BULLET_SHOULD_RE.match(line):
        return [("should-bullet", "ambiguous obligation")]
    return []


def _scan_line(rel_path: str, line_no: int, line: str) -> list[Finding]:
    line_no_badges = MD_IMAGE_BADGE_RE.sub("", line)
    prose = INLINE_CODE_RE.sub("", MD_LINK_RE.sub("", line_no_badges))
    hits = [
        *_char_hits(prose),
        *_paren_hits(line.strip(), prose),
        *_phrase_hits(line, prose),
        *_should_hits(line),
        *_regex_hits(prose, VAGUE_RULES),
    ]
    return [
        Finding(rel_path, line_no, category, detail, snippet_of(line))
        for category, detail in hits
    ]


def scan_text(rel_path: str, text: str) -> list[Finding]:
    lines = text.splitlines()
    mask = _code_line_mask(lines)
    return [
        finding
        for line_no, (line, masked) in enumerate(zip(lines, mask), start=1)
        if not masked
        for finding in _scan_line(rel_path, line_no, line)
    ]


def _is_external_target(target: str) -> bool:
    return target.startswith(("http://", "https://", "#", "mailto:"))


def _target_exists(clean_target: str, path: Path, repo_root: Path | None) -> bool:
    if (path.parent / clean_target).resolve().exists():
        return True
    return repo_root is not None and (repo_root / clean_target).resolve().exists()


def scan_links(
    rel_path: str,
    path: Path,
    text: str,
    repo_root: Path | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    masked = _mask_code_regions(text)
    for m in MD_LINK_RE.finditer(masked):
        target = m.group(1)
        clean_target = target.split("#")[0]
        if _is_external_target(target) or not clean_target:
            continue
        if _target_exists(clean_target, path, repo_root):
            continue
        line_no = text[: m.start()].count("\n") + 1
        findings.append(Finding(rel_path, line_no, "stale-link", target, m.group(0)))
    return findings


def _blank_match(m: re.Match[str]) -> str:
    return " " * len(m.group(0))


def _mask_code_regions(text: str) -> str:
    raw_lines = text.splitlines(keepends=True)
    mask = _code_line_mask(raw_lines)
    return "".join(
        " " * len(line) if masked else INLINE_CODE_RE.sub(_blank_match, line)
        for line, masked in zip(raw_lines, mask)
    )


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


def _summary_lines(findings: list[Finding], file_count: int) -> list[str]:
    cat_counts = Counter(f.category for f in findings)
    rows = [
        f"| {cat} | {n} |"
        for cat, n in sorted(cat_counts.items(), key=lambda kv: -kv[1])
    ]
    return [
        "# Audit Findings",
        "",
        f"Total: {len(findings)} findings across {file_count} files.",
        "",
        "## Summary by Category",
        "",
        "| Category | Count |",
        "|----------|-------|",
        *rows,
        "",
        "## Per-File Findings",
        "",
    ]


def _finding_row(finding: Finding) -> str:
    snip = finding.snippet.replace("|", r"\|")
    detail = finding.detail.replace("|", r"\|")
    return f"| {finding.line} | {finding.category} | {detail} | {snip} |"


def _file_section(filename: str, items: list[Finding]) -> list[str]:
    return [
        f"### {filename}",
        "",
        f"{len(items)} findings.",
        "",
        "| Line | Category | Detail | Snippet |",
        "|------|----------|--------|---------|",
        *(_finding_row(f) for f in sorted(items, key=lambda f: f.line)),
        "",
    ]


def write_markdown(findings: list[Finding], out: Path) -> None:
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_file[finding.file].append(finding)
    sorted_files = sorted(by_file.items(), key=lambda kv: -len(kv[1]))
    lines = [
        *_summary_lines(findings, len(by_file)),
        *(line for name, items in sorted_files for line in _file_section(name, items)),
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit writing quality drift.")
    parser.add_argument(
        "--out-dir",
        default="specs/writing-quality",
        help="Directory for output files.",
    )
    parser.add_argument(
        "--root",
        default=str(CLAUDE_ROOT),
        help="Root directory to scan.",
    )
    return parser.parse_args()


def _collect_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in walk_markdown(root):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as error:
            findings.append(Finding(rel, 0, "unreadable", f"cannot read: {error}", ""))
            continue
        findings.extend(scan_text(rel, text))
        findings.extend(scan_links(rel, path, text, root))
    return findings


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    findings = _collect_findings(root)
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
