from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from _lib.comment_families import (
    ASSEMBLY,
    ASSEMBLY_68K,
    C,
    MATLAB,
    PYTHON,
    CommentFamily,
)
from _lib.comment_family_index import (
    BASENAME_FAMILIES,
    BASENAME_PREFIX_FAMILIES,
    EXTENSION_FAMILIES,
    INTERPRETER_FAMILIES,
    NOTEBOOK_FAMILIES,
)

SKIP_SEGMENTS: tuple[str, ...] = (
    "/specs/",
    "/docs/adr/",
    "/docs/plan/",
    "/docs/plans/",
    "/docs/planning/",
    "/templates/",
    "/template/",
    "/node_modules/",
    "/vendor/",
    "/.git/",
    "/dist/",
    "/build/",
    "/.venv/",
    "/site-packages/",
    "/__pycache__/",
    "/.next/",
    "/coverage/",
)


ENV_FILE = re.compile(r"^\.env(?:\..*)?$")


TEST_PATH = re.compile(
    r"\.test\.|\.spec\.|/test_[^/]*\.py$|_test\.py$|_test\.go$|\.bats$"
    r"|/__tests__/|/tests/|/e2e/"
)


OBJECTIVE_C_SIGNAL = re.compile(
    r"^\s*(?:@interface|@implementation|@protocol|@end|#import|#include)\b", re.M
)


C_SIGNAL = re.compile(
    r"^\s*#\s*(?:include|define|ifn?def|if|endif|pragma)\b"
    r"|\b(?:void|struct|typedef|static|const|int|char)\b[^;\n]*[;{(]",
    re.M,
)


LEADING_SEMICOLON = re.compile(r"^\s*;", re.M)


M68K_SIGNAL = re.compile(
    r"^\s+(?:move[aqm]?|lea|addq?|subq?|cmp|tst|clr)\.[bwl]\s+[^;\n]*\b[da][0-7]\b",
    re.I | re.M,
)


SHEBANG = re.compile(r"^#!\s*(\S+)[ \t]*([^\n]*)")


PYTHON_INTERPRETER = re.compile(r"^python[\d.]*$")


@dataclass(frozen=True, slots=True)
class DocumentView:
    family: CommentFamily
    text: str


def is_test_path(path: str) -> bool:
    return TEST_PATH.search("/" + path.lower().lstrip("/")) is not None


def resolve_family(path: str, text: str = "") -> CommentFamily | None:
    lowered = "/" + path.lower().lstrip("/")
    base = os.path.basename(lowered)
    if not path or ENV_FILE.match(base):
        return None
    if any(segment in lowered for segment in SKIP_SEGMENTS):
        return None
    return _family_by_name(base, text)


def _family_by_name(base: str, text: str) -> CommentFamily | None:
    if base in BASENAME_FAMILIES:
        return BASENAME_FAMILIES[base]
    prefixed = next(
        (
            family
            for prefix, family in BASENAME_PREFIX_FAMILIES
            if base.startswith(prefix)
        ),
        None,
    )
    if prefixed is not None:
        return prefixed
    extension = os.path.splitext(base)[1]
    if not extension:
        return _family_by_shebang(text)
    return _family_by_extension(extension, text)


def _family_by_extension(extension: str, text: str) -> CommentFamily | None:
    if extension == ".m":
        return C if OBJECTIVE_C_SIGNAL.search(text) else MATLAB
    if extension == ".inc":
        return _include_family(text)
    if extension in (".s", ".asm"):
        return ASSEMBLY_68K if M68K_SIGNAL.search(text) else ASSEMBLY
    if extension == ".ipynb":
        return _notebook_family(text)
    return EXTENSION_FAMILIES.get(extension)


def _include_family(text: str) -> CommentFamily:
    if LEADING_SEMICOLON.search(text):
        return ASSEMBLY
    return C if C_SIGNAL.search(text) else ASSEMBLY


def _family_by_shebang(text: str) -> CommentFamily | None:
    match = SHEBANG.match(text)
    if match is None:
        return None
    program = os.path.basename(match.group(1))
    if program == "env":
        arguments = [
            word for word in match.group(2).split() if not word.startswith("-")
        ]
        program = arguments[0] if arguments else ""
    if PYTHON_INTERPRETER.match(program):
        return PYTHON
    return INTERPRETER_FAMILIES.get(program)


def _notebook_json(text: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(text)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _notebook_family(text: str) -> CommentFamily:
    metadata = _notebook_json(text).get("metadata")
    if not isinstance(metadata, dict):
        return PYTHON
    for key, field in (("language_info", "name"), ("kernelspec", "language")):
        section = metadata.get(key)
        if isinstance(section, dict) and isinstance(section.get(field), str):
            return NOTEBOOK_FAMILIES.get(str(section[field]).lower(), PYTHON)
    return PYTHON


def notebook_code(text: str) -> str:
    cells = _notebook_json(text).get("cells")
    if not isinstance(cells, list):
        return ""
    sources = [
        cell.get("source")
        for cell in cells
        if isinstance(cell, dict) and cell.get("cell_type") == "code"
    ]
    return "\n".join(
        "".join(source) if isinstance(source, list) else str(source or "")
        for source in sources
    )


def document_view(path: str, text: str) -> DocumentView | None:
    family = resolve_family(path, text)
    if family is None:
        return None
    if path.lower().endswith(".ipynb"):
        return DocumentView(family, notebook_code(text))
    return DocumentView(family, text)
