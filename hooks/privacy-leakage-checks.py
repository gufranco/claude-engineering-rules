#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
from _lib.audit_log import record as _audit  # noqa: E402


SCAN_EXTS = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".vue",
    ".svelte",
    ".html",
    ".htm",
)

SKIP_SEGMENTS = (
    "/__tests__/",
    "/__test__/",
    "/tests/",
    "/test/",
    "/.claude/hooks/",
    "/.claude/specs/",
    "/node_modules/",
    "/dist/",
    "/build/",
    "/.next/",
)

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.edit_resolution import payload_fragments  # noqa: E402


def is_skipped(path: str) -> bool:
    if not path.endswith(SCAN_EXTS):
        return True
    if any(seg in path for seg in SKIP_SEGMENTS):
        return True
    if any(
        part in os.path.basename(path) for part in (".test.", ".spec.", ".stories.")
    ):
        return True
    return False


COOKIE_PAT = re.compile(
    r"\b(?:document\.cookie\s*=|setCookie\s*\(|Cookies\.set\s*\()",
    re.IGNORECASE,
)

CONSENT_CONTEXT_PAT = re.compile(
    r"(?:consent|consented|hasConsent|cookieConsent|onConsent|consentCategories)",
    re.IGNORECASE,
)

EMAIL_PAT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PAT = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|\+\d{1,3}\s?\d{1,4}\s?\d{6,}")
SSN_PAT = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
JWT_PAT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")

CONSOLE_PII_PAT = re.compile(
    r"console\.(?:log|info|warn|error|debug)\s*\([^)]*",
    re.IGNORECASE,
)

LOCALSTORAGE_PAT = re.compile(
    r"\b(?:localStorage|sessionStorage)\.setItem\s*\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

PII_KEY_PAT = re.compile(
    r"(?:email|phone|ssn|cpf|cnpj|passport|driver_?license|tax_?id|password|credit_?card|card_?number|cvv|auth_?token|user_?token|access_?token|refresh_?token|jwt)",
    re.IGNORECASE,
)

TRACKER_PATS = [
    (re.compile(r"\bUA-\d{4,10}-\d{1,4}\b"), "Google Analytics Universal"),
    (re.compile(r"\bG-[A-Z0-9]{8,12}\b"), "Google Analytics 4"),
    (re.compile(r"\bGTM-[A-Z0-9]{4,10}\b"), "Google Tag Manager"),
    (re.compile(r"\bfbq\s*\(\s*['\"]init['\"]"), "Facebook Pixel init"),
    (re.compile(r"\b_linkedin_partner_id\b"), "LinkedIn Insight"),
    (re.compile(r"\bttq\.load\s*\("), "TikTok Pixel"),
]


def find_cookies_without_consent(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in COOKIE_PAT.finditer(content):
        line_num = content[: m.start()].count("\n") + 1
        start_lookback = max(0, m.start() - 3000)
        preceding = content[start_lookback : m.start()]
        if not CONSENT_CONTEXT_PAT.search(preceding):
            findings.append(
                (
                    line_num,
                    "PLC001: cookie set without nearby consent check (ePrivacy Art. 5(3))",
                )
            )
    return findings


def find_console_pii(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in CONSOLE_PII_PAT.finditer(content):
        span = content[m.start() : m.end() + 200]
        for pat, label in [
            (EMAIL_PAT, "email"),
            (PHONE_PAT, "phone"),
            (SSN_PAT, "SSN"),
            (JWT_PAT, "JWT"),
        ]:
            if pat.search(span):
                line_num = content[: m.start()].count("\n") + 1
                findings.append(
                    (
                        line_num,
                        f"PLC002: console output contains {label}-like pattern. Use a structured logger and log the identifier, not the value",
                    )
                )
                break
    return findings


def find_localstorage_pii(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in LOCALSTORAGE_PAT.finditer(content):
        key = m.group(1)
        if PII_KEY_PAT.search(key):
            line_num = content[: m.start()].count("\n") + 1
            findings.append(
                (
                    line_num,
                    f"PLC003: localStorage key '{key}' looks like PII. Use httpOnly cookie for tokens; never store PII in client storage",
                )
            )
    return findings


def find_tracker_without_consent(content: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for pat, label in TRACKER_PATS:
        for m in pat.finditer(content):
            line_num = content[: m.start()].count("\n") + 1
            start_lookback = max(0, m.start() - 3000)
            preceding = content[start_lookback : m.start()]
            if not CONSENT_CONTEXT_PAT.search(preceding):
                findings.append(
                    (
                        line_num,
                        f"PLC004: {label} loaded without consent gate. Wrap in onConsentChange or equivalent",
                    )
                )
    return findings


CHECKS = [
    find_cookies_without_consent,
    find_console_pii,
    find_localstorage_pii,
    find_tracker_without_consent,
]


def extract_content(tool_name: str, tool_input: dict) -> tuple[str, str]:
    text = "\n".join(part for _, part in payload_fragments(tool_name, tool_input))
    return tool_input.get("file_path", ""), text


MAX_LISTED_FINDINGS = 10


def _disabled() -> bool:
    if os.environ.get("PRIVACY_CHECKS_DISABLE") == "1":
        return True
    return is_bypassed("privacy-leakage-checks")


def _run_checks(content: str) -> list[tuple[int, str]]:
    found = [finding for check in CHECKS for finding in check(content)]
    return sorted(found, key=lambda f: f[0])


def _block(tool_name: str, path: str, all_findings: list[tuple[int, str]]) -> int:
    listed = all_findings[:MAX_LISTED_FINDINGS]
    bullet_lines = "\n".join(f"  - line {ln}: {msg}" for ln, msg in listed)
    overflow = len(all_findings) - MAX_LISTED_FINDINGS
    extra = "" if overflow <= 0 else f"\n  ... {overflow} more"
    _audit(
        hook="privacy-leakage-checks",
        decision="block",
        tool=tool_name,
        reason=f"{len(all_findings)} privacy leakage findings",
        command_excerpt=path,
        bypass_env="PRIVACY_CHECKS_DISABLE",
    )
    print(
        "Blocked: privacy leakage patterns detected. Rule: ~/.claude/rules/privacy-defaults.md\n"
        f"\n{bullet_lines}{extra}\n\n"
        "Wrap personal data writes/logs/cookies/trackers in a consent check and use the project logger with identifiers only. "
        "Bypass: PRIVACY_CHECKS_DISABLE=1 in the parent shell.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    if _disabled():
        return 0
    payload = read_hook_payload("privacy-leakage-checks")
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0
    path, content = extract_content(tool_name, tool_input)
    if not path or not content or is_skipped(path):
        return 0
    all_findings = _run_checks(content)
    if not all_findings:
        return 0
    return _block(tool_name, path, all_findings)


if __name__ == "__main__":
    sys.exit(main())
