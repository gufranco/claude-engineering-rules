from __future__ import annotations

import re

GIT_MESSAGE_BASH_PATTERNS = [
    re.compile(r"\bgit\s+commit\b"),
    re.compile(r"\bgit\s+tag\b"),
    re.compile(r"\bgit\s+notes\b"),
]

NON_GIT_PUBLISHING_BASH_PATTERNS = [
    re.compile(r"\bgh\s+(?:pr|issue|api|release|gist)\b"),
    re.compile(r"\bglab\s+(?:mr|issue|api|release)\b"),
    re.compile(r"\bslack(?:-cli)?\s+(?:send|post|chat)\b"),
    re.compile(r"\bcurl\b.*\b(?:slack|discord|teams|telegram)\b"),
]

PUBLISHING_BASH_PATTERNS = [
    *NON_GIT_PUBLISHING_BASH_PATTERNS,
    *GIT_MESSAGE_BASH_PATTERNS,
]

HEREDOC_HEADER_PATTERN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

GIT_MESSAGE_SHORT_FLAG_PATTERN = re.compile(r"^-[A-Za-z]*m$")

GIT_MESSAGE_LONG_FLAGS = ("--message", "-m")

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

LABELS_NEVER_VALID_IN_A_COMMIT_SUBJECT = r"issue\s*\((?:blocking|non-blocking)\)|nitpick|suggestion|question|thought|praise|todo"

CONVENTIONAL_LABEL_PATTERN = re.compile(
    rf"(?m)^\s*(?:{LABELS_NEVER_VALID_IN_A_COMMIT_SUBJECT}|chore)\s*:",
    re.IGNORECASE,
)

CONVENTIONAL_LABEL_PATTERN_IN_GIT_MESSAGE = re.compile(
    rf"(?m)^\s*(?:{LABELS_NEVER_VALID_IN_A_COMMIT_SUBJECT})\s*:",
    re.IGNORECASE,
)

SKILL_FLAG_HEAD_PATTERN = re.compile(
    r"\(?`?--(?:backend|frontend|local|post|focus|severity|fix|pict|coverage)`?\)?",
)

SEVERITY_TIER_PATTERN = re.compile(
    r"(?m)^\s*(?:#+\s+P[0-3]\b|P[0-3]\b(?:\s*[:.\-]"
    r"|\s+(?:blocking|should|nits?|critical|important|optional|minor|major)"
    r"|\s+\w{1,12}:))",
    re.IGNORECASE,
)

INTERNAL_SECTION_HEADINGS = [
    "Behavioral Flow Analysis",
    "Blast Radius Summary",
    "Standards Applied",
]
SECTION_HEADING_PATTERN = re.compile(
    r"(?im)^\s*#+\s*(?:"
    + "|".join(re.escape(h) for h in INTERNAL_SECTION_HEADINGS)
    + r")\b",
)

REVIEW_PREAMBLE_WORDS = (
    "review",
    "this pr",
    "this mr",
    "audit",
    "scope",
    "out of scope",
    "skimmed",
    "looked through",
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
    "/.claude/.github/scripts/",
    "/.claude/agents/",
    "/.claude/tests/",
    "/.claude/projects/",
    "/.claude/settings.json",
    "/.claude/settings.local.json",
)

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

FORGE_CLIS = frozenset({"gh", "glab"})
READ_ONLY_ACTIONS = frozenset({"view", "list", "diff", "checks", "status", "search"})
API_BODY_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field", "--input", "--form"})
API_METHOD_FLAGS = frozenset({"-X", "--method"})

GIT_WORD = re.compile(r"\bgit\b")
SEGMENT_OPERATOR = re.compile(r"&&|\|\||[;|]")

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

INLINE_PAYLOAD_FILE_FLAGS = ("--input", "--body-file", "--file")

PAYLOAD_SIZE_LIMIT = 5 * 1024 * 1024
