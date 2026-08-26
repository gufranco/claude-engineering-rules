#!/usr/bin/env python3
"""
ai-slop-blocker.py

PreToolUse hook that blocks structural AI-slop tells in published text.

Rule source:
  - ~/.claude/rules/anti-slop.md (catalogue, deciding tests, provenance).

Relationship to neighbouring hooks:
  - banned-phrases-blocker.py blocks a vocabulary list.
  - banned-prose-chars.py blocks em dashes, prose parens, emoji, ASCII art.
  - This hook blocks the grammatical and rhetorical shapes that survive any
    wordlist: negative parallelism, significance inflation, participial
    evaluation tails, evasive attribution, hedged speculation, marketing
    verbs standing in for "is" and "has", chat residue, markup residue.

Coverage:
  - Write/Edit/MultiEdit on Markdown files.
  - Bash commands that publish text (gh, glab, git commit/tag, chat webhooks).

Fenced code blocks, indented blocks, inline code spans, link targets and
HTML comments are masked before matching, so quoted examples and sample
output never trip a detector.

Calibration:
  Every detector was measured against the 209 Markdown files under
  rules/, standards/, checklists/, skills/, agents/ and docs/ before
  inclusion. Only patterns at or below three corpus hits were wired
  up. Bold-label bullets measured 311 hits and are documented in the rule
  rather than enforced. Rule of three and structural symmetry are not
  mechanically decidable and stay review-time obligations.

Bypass:
  AI_SLOP_DISABLE=1 (parent shell export, not inline)
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

try:
    from _lib.audit_log import record as _audit  # type: ignore
except Exception:  # pragma: no cover

    def _audit(**_fields):  # type: ignore
        return None


try:
    from _lib.bypass import is_bypassed  # type: ignore
except Exception:  # pragma: no cover

    def is_bypassed(_id: str) -> bool:  # type: ignore
        return False


try:
    from _lib.hook_profile import should_run  # type: ignore
except Exception:  # pragma: no cover

    def should_run(_id: str) -> bool:  # type: ignore
        return True


try:
    from _lib.output import block as _block_message  # type: ignore
except Exception:  # pragma: no cover
    _block_message = None  # type: ignore


HOOK_ID = "ai-slop-blocker"
ENV_VAR = "AI_SLOP_DISABLE"
RULE_ANCHOR = "~/.claude/rules/anti-slop.md"

PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram|hooks\.)"),
]

SKIPPED_PATHS = (
    "/.claude/rules/anti-slop.md",
    "/.claude/hooks/ai-slop-blocker.py",
    "/.claude/tests/hooks/ai-slop-blocker/",
    "/.claude/tests/fixtures/",
    "CHANGELOG.md",
)

FENCED_BLOCK = re.compile(r"```.*?```", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
INDENTED_BLOCK = re.compile(r"(?m)^(?: {4,}|\t)(?![-*+>]\s|\d+[.)]\s)\S.*$")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK_TARGET = re.compile(r"\]\([^)\n]*\)")

DETECTORS: list[tuple[str, str, re.Pattern[str], str, int]] = [
    (
        "SLOP001",
        "negative parallelism / corrective reframe",
        re.compile(
            r"\bnot (?:just|only|merely|simply)\b[^.\n]{0,70}?\bbut\b"
            r"|\b(?:it|this|that)'?s not\b[^.\n]{0,60}?[,.]\s*(?:it|this|that)'?s\b"
            r"|\b(?:is|are|was|were|does|do)\s+not\b[^.\n]{0,70}?\bbut rather\b"
            r"|\bmore than (?:just|merely|simply)\b"
            r"|\bless about\b[^.\n]{0,50}\band more about\b"
            r"|\b(?:isn'?t|is not|aren'?t) (?:really )?about\b[^.\n]{0,50}\bit'?s about\b",
            re.IGNORECASE,
        ),
        'State the positive claim alone. Drop the "not X" half; the reader never held X.',
        1,
    ),
    (
        "SLOP002",
        "significance inflation",
        re.compile(
            r"\b(?:stands?|serves?) as a testament\b|\bis a testament to\b"
            r"|\bplays? an? (?:crucial|pivotal|vital|key|central|significant) role\b"
            r"|\b(?:underscore|underscores|highlight|highlights)\s+the\s+"
            r"(?:importance|significance|need)\b"
            r"|\brich tapestry\b|\btapestry of\b"
            r"|\b(?:ever-)?evolving landscape\b|\bchanging landscape\b"
            r"|\bin today'?s (?:fast-paced|digital|modern|ever-changing)\b"
            r"|\b(?:left|leaves|leaving) an indelible mark\b"
            r"|\bsetting the stage for\b|\bat the forefront of\b"
            r"|\bcannot be (?:overstated|understated)\b|\bspeaks volumes\b"
            r"|\bparadigm shift\b|\bgame[- ]changer\b"
            r"|\bmarks? a (?:significant|major|key) (?:shift|milestone|turning point)\b",
            re.IGNORECASE,
        ),
        "Delete the significance clause, or replace it with the measured consequence.",
        1,
    ),
    (
        "SLOP003",
        "participial evaluation tail",
        re.compile(
            r",\s+(?:highlighting|underscoring|emphasizing|showcasing|reflecting"
            r"|symbolizing|demonstrating|solidifying|cementing|reinforcing"
            r"|signaling|underlining|illustrating|exemplifying)\b",
            re.IGNORECASE,
        ),
        "The sentence ended at the comma. Promote a real consequence to its own "
        'sentence with the mechanism named. "ensuring", "enabling" and "allowing" '
        "are excluded, since they name causation rather than significance.",
        1,
    ),
    (
        "SLOP004",
        "evasive attribution",
        re.compile(
            r"\b(?:experts|observers|critics|analysts|researchers)\s+"
            r"(?:say|says|argue|argues|agree|note|notes|suggest|suggests|believe"
            r"|have (?:cited|noted|argued))\b"
            r"|\b(?:industry reports|studies|research)\s+"
            r"(?:show|shows|suggest|suggests|indicate|indicates)\b"
            r"|\bis (?:widely|generally) "
            r"(?:considered|regarded|recognized|believed|acknowledged)\b"
            r"|\bmany (?:believe|argue|consider)\b",
            re.IGNORECASE,
        ),
        "Name the source and link it, or drop the claim. An unnamed authority "
        "cannot be checked or disputed.",
        1,
    ),
    (
        "SLOP005",
        "hedged speculation / cutoff residue",
        re.compile(
            r"\b(?:not|un)\s?-?\s?(?:publicly\s+)?"
            r"(?:documented|available|disclosed|recorded)\b"
            r"[^.\n]{0,40}[,.]?\s*(?:it|they|the)\b[^.\n]{0,30}\blikely\b"
            r"|\bwhile (?:specific|exact|precise) (?:details|information|data)\b"
            r"[^.\n]{0,60}\b(?:are|is) (?:not|un)\b"
            r"|\bas of my (?:last|knowledge|training)\b"
            r"|\bmaintains? a low profile\b",
            re.IGNORECASE,
        ),
        "Say what is unknown and stop. Asserting both that a fact is unavailable "
        "and what it probably is fabricates the second half.",
        1,
    ),
    (
        "SLOP006",
        "marketing verb replacing is/has",
        re.compile(
            r"\b(?:serves|stands|functions|operates) as (?:a|an|the)\b"
            r"|\bboasts\b"
            r"|\baims to (?:provide|deliver|ensure|offer)\b"
            r"|\bstrives to\b|\bseeks to (?:provide|deliver|ensure)\b",
            re.IGNORECASE,
        ),
        'Use "is" or "has", or name the action directly.',
        1,
    ),
    (
        "SLOP007",
        "throat-clearing / false concession",
        re.compile(
            r"(?im)^\s*(?:Look|Here'?s the thing|Let'?s be clear|Let'?s be honest"
            r"|The truth is|Make no mistake|Let'?s (?:explore|dive|unpack)"
            r"|Buckle up)[,:]"
            r"|\bto be fair,|\bcredit where (?:credit is )?due\b|\bin all fairness\b"
            r"|\bit'?s worth (?:pointing out|mentioning|remembering)\b",
            re.IGNORECASE,
        ),
        "Start with the actual point. Address a counterargument that exists, or none.",
        1,
    ),
    (
        "SLOP008",
        "trailing recap",
        re.compile(
            r"(?im)^\s*(?:In short|In summary|In conclusion|To sum up|All in all"
            r"|At the end of the day|The bottom line|Bottom line)[,:]"
            r"|\bkey takeaways?\b",
            re.IGNORECASE,
        ),
        "End when the point lands. A required TL;DR goes at the top, per "
        'CLAUDE.md "Lead with a TL;DR", never as a closing restatement.',
        1,
    ),
    (
        "SLOP009",
        "AI vocabulary cluster",
        re.compile(
            r"\bdelv(?:e|ing) into\b|\bintricacies\b|\bmeticulous(?:ly)?\b"
            r"|\bmyriad\b|\bplethora\b|\bnavigat(?:e|ing) the complexit(?:y|ies)\b"
            r"|\bunlock(?:ing)? the (?:potential|power)\b|\bharness(?:ing)? the power\b"
            r"|\bpave(?:s|d)? the way\b|\bshed(?:s|ding)? light on\b"
            r"|\bvibrant\b|\bshowcases\b|\bexemplifies\b|\bbolster(?:s|ed|ing)?\b"
            r"|\bgarner(?:s|ed|ing)?\b|\binterplay\b|\bresonates? with\b"
            r"|\bvaluable insights\b|\bseamlessly\b|\beffortlessly\b"
            r"|\bunparalleled\b|\bholistic\b|\btransformative\b"
            r"|\ba (?:wide|diverse|broad) (?:range|array|variety) of\b"
            r"|\bwhen it comes to\b|\bat its core\b|\bnestled\b",
            re.IGNORECASE,
        ),
        "Replace each with the specific claim. Density is the signal, so this "
        "detector requires two or more distinct hits before it fires.",
        2,
    ),
    (
        "SLOP010",
        "chat residue in an artifact",
        re.compile(
            r"\bI hope this (?:helps|message finds you)\b"
            r"|\blet me know if you'?d? (?:like|want)\b"
            r"|\bfeel free to (?:adjust|customize|modify|tweak)\b"
            r"|\bhere'?s a template\b"
            r"|\byou can (?:copy and paste|customize) (?:this|it)\b"
            r"|\bas an AI\b|\bI'?m unable to browse\b",
            re.IGNORECASE,
        ),
        "Delete. Text addressed to a person mid-conversation must not survive "
        "into an artifact.",
        1,
    ),
    (
        "SLOP011",
        "unfilled placeholder",
        re.compile(
            r"\[(?:insert|your|add|company|topic)\s[^\]\n]{1,30}\]"
            r"|\bLorem ipsum dolor\b"
            r"|\b\d{4}-XX-XX\b|\bYYYY-XX-XX\b|\b20XX\b"
            r"|\[TBD:[^\]\n]{0,40}\]",
            re.IGNORECASE,
        ),
        "Fill the placeholder or remove the line. Shipping the template is "
        "shipping unfinished text.",
        1,
    ),
    (
        "SLOP012",
        "typographic residue",
        re.compile("[‘’“”′″]"),
        "Use ASCII apostrophes and quotes. Curly marks in a source file are "
        "auto-substitution residue from a chat surface.",
        1,
    ),
]

CONTEXT_EXCLUSIONS: dict[str, re.Pattern[str]] = {
    "SLOP004": re.compile(
        r"[A-Z][A-Za-z.&-]{2,}\s+(?:studies|research|reports|analysts|researchers"
        r"|experts|observers|critics)\b"
    ),
}

AGENT_TOOL_NAMES = ("Agent", "Task")


MARKDOWN_MASKS = (
    FENCED_BLOCK,
    HTML_COMMENT,
    INDENTED_BLOCK,
    INLINE_CODE,
    LINK_TARGET,
)

COMMAND_MASKS = (FENCED_BLOCK, INLINE_CODE)


def mask_code(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    """Blank out code spans while preserving offsets and line numbers.

    A publishing command carries a Markdown body, so its fenced blocks and
    inline code are masked too. The indent and link-target masks are not
    applied there, since shell continuation lines are prose more often than
    they are code.
    """

    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    for pattern in patterns:
        text = pattern.sub(blank, text)
    return text


def is_publishing_bash(cmd: str) -> bool:
    return any(p.search(cmd) for p in PUBLISHING_BASH_PATTERNS)


def is_skipped_path(path: str) -> bool:
    if not path:
        return False
    return any(seg in path for seg in SKIPPED_PATHS)


def collect(tool: str, tool_input: dict) -> list[tuple[str, str, bool]]:
    """Return (label, text, is_markdown) triples worth scanning."""
    out: list[tuple[str, str, bool]] = []
    fp = tool_input.get("file_path", "") or ""
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        if isinstance(cmd, str) and is_publishing_bash(cmd):
            out.append(("bash command", cmd, False))
        return out
    if is_skipped_path(fp) or not fp.lower().endswith((".md", ".markdown")):
        return out
    if tool == "Write":
        content = tool_input.get("content", "")
        if isinstance(content, str):
            out.append((fp, content, True))
    elif tool == "Edit":
        content = tool_input.get("new_string", "")
        if isinstance(content, str):
            out.append((fp, content, True))
    elif tool == "MultiEdit":
        for i, edit in enumerate(tool_input.get("edits", []) or []):
            if isinstance(edit, dict):
                content = edit.get("new_string", "")
                if isinstance(content, str):
                    out.append((f"{fp} [{i}]", content, True))
    return out


def find(text: str, is_markdown: bool) -> list[tuple[str, str, str, str]]:
    """Return (code, label, located snippet, fix) for each detector that fires."""
    scanned = mask_code(text, MARKDOWN_MASKS if is_markdown else COMMAND_MASKS)
    findings: list[tuple[str, str, str, str]] = []
    for code, label, pattern, fix, min_hits in DETECTORS:
        exclusion = CONTEXT_EXCLUSIONS.get(code)
        matches = [
            m
            for m in pattern.finditer(scanned)
            if not (
                exclusion
                and exclusion.search(scanned[max(0, m.start() - 40) : m.end()])
            )
        ]
        if len(matches) < min_hits:
            continue
        if min_hits > 1 and len({m.group(0).lower() for m in matches}) < min_hits:
            continue
        first = matches[0]
        line_no = scanned.count("\n", 0, first.start()) + 1
        start = max(0, first.start() - 40)
        end = min(len(scanned), first.end() + 40)
        snippet = " ".join(scanned[start:end].split())
        hit_note = f" ({len(matches)} hits)" if len(matches) > 1 else ""
        findings.append(
            (code, f"{label}{hit_note}", f"line {line_no}: ...{snippet}...", fix)
        )
    return findings


def render(all_findings: list[tuple[str, list[tuple[str, str, str, str]]]]) -> str:
    detected_lines: list[str] = []
    fix_lines: list[str] = []
    seen_fixes: set[str] = set()
    for label, findings in all_findings:
        detected_lines.append(f"{label}:")
        for code, name, snippet, fix in findings:
            detected_lines.append(f"  {code} {name}")
            detected_lines.append(f"    {snippet}")
            if code not in seen_fixes:
                seen_fixes.add(code)
                fix_lines.append(f"{code}: {fix}")
    why = (
        "Slop is text whose shape was chosen before its content. It clears every "
        "other gate: it compiles, it lints, it reads as competent, and nothing "
        "reports it, so the defect reaches the reader and is attributed to the "
        "author's judgment. The phrase blocklist in CLAUDE.md catches vocabulary; "
        "these are the grammatical and rhetorical shapes that survive paraphrase.\n"
        "Rule: ~/.claude/rules/anti-slop.md"
    )
    fix = "\n".join(fix_lines) + (
        "\n\nThen re-read the passage against the three deciding tests: could this "
        "sentence appear verbatim in a document about a different subject; does "
        "deleting it change the reader's next action; did the content choose the "
        "structure."
    )
    bypass_when = (
        "You are quoting someone else's text verbatim, such as a review reply that "
        "cites the comment it answers, or a document that catalogues these patterns "
        "as examples. Fenced and inline code is already excluded, so wrapping a "
        "quoted example in backticks is usually the better fix."
    )
    if _block_message is None:  # pragma: no cover
        return (
            f"BLOCKED by {HOOK_ID} ({RULE_ANCHOR})\n\n"
            + "\n".join(detected_lines)
            + f"\n\n{fix}\n\nBypass: {ENV_VAR}=1"
        )
    return _block_message(
        hook=HOOK_ID,
        rule_anchor=RULE_ANCHOR,
        detected="\n".join(detected_lines),
        why=why,
        fix=fix,
        bypass_when=bypass_when,
        decision="FIX-AND-RETRY",
        env_var=ENV_VAR,
        safety="later passages in the same session are not checked for slop tells.",
    )


def main() -> int:
    if not should_run(HOOK_ID):
        return 0
    if os.environ.get(ENV_VAR) == "1":
        _audit(hook=HOOK_ID, decision="bypass", bypass_env=ENV_VAR)
        return 0
    if is_bypassed(HOOK_ID):
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name", "")
    if tool in AGENT_TOOL_NAMES:
        return 0
    tool_input = payload.get("tool_input", {}) or {}

    items = collect(tool, tool_input)
    if not items:
        return 0

    all_findings: list[tuple[str, list[tuple[str, str, str, str]]]] = []
    for label, text, is_markdown in items:
        findings = find(text, is_markdown)
        if findings:
            all_findings.append((label, findings[:6]))

    if not all_findings:
        return 0

    print(render(all_findings), file=sys.stderr)
    codes = sorted({code for _, f in all_findings for code, _, _, _ in f})
    _audit(
        hook=HOOK_ID,
        decision="block",
        tool=tool,
        reason="ai slop tell",
        command_excerpt=",".join(codes)[:240],
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
