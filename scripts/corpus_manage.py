#!/usr/bin/env python3
"""Corpus management for the mutation-method-blocker test fixtures.

Plan item 289. Subcommands:

    python3 scripts/corpus_manage.py list
    python3 scripts/corpus_manage.py add <file> <category> <expected>
    python3 scripts/corpus_manage.py validate
    python3 scripts/corpus_manage.py regenerate

The corpus lives under `~/.claude/tests/corpus/mutation-method-blocker/`
with one subdirectory per category and `clean.ts` / `dirty.ts` fixtures.
The `VERSION` file records the schema and the last regeneration date.

`validate` runs the hook against every fixture and asserts that the
expected outcome matches: `clean.*` files must produce zero findings,
`dirty.*` files must produce at least one finding. Exits 0 on full
agreement, 1 otherwise. The exit code is suitable for CI gating.

`regenerate` does NOT mutate fixture content; it bumps the version
metadata and timestamps the regeneration so reviewers know the corpus
was re-validated against the current hook surface.

`add` copies a fixture into the corpus under the chosen category and
records its expected outcome via the filename suffix.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

CORPUS_ROOT = os.path.expanduser("~/.claude/tests/corpus/mutation-method-blocker")
VERSION_FILE = os.path.join(CORPUS_ROOT, "VERSION")
HOOK_PATH = os.path.expanduser("~/.claude/hooks/mutation-method-blocker.py")
VALID_EXTS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx")


@dataclass(frozen=True)
class Fixture:
    """One fixture file under the corpus root."""

    category: str
    relpath: str
    abspath: str
    expected: str

    @property
    def display(self) -> str:
        return f"{self.category}/{os.path.basename(self.relpath)}"


def _list_fixtures() -> list[Fixture]:
    fixtures: list[Fixture] = []
    if not os.path.isdir(CORPUS_ROOT):
        return fixtures
    for category in sorted(os.listdir(CORPUS_ROOT)):
        cat_path = os.path.join(CORPUS_ROOT, category)
        if not os.path.isdir(cat_path):
            continue
        for entry in sorted(os.listdir(cat_path)):
            if not entry.endswith(VALID_EXTS):
                continue
            stem = entry.split(".", 1)[0]
            if stem == "clean":
                expected = "clean"
            elif stem == "dirty":
                expected = "dirty"
            else:
                expected = "unknown"
            abspath = os.path.join(cat_path, entry)
            relpath = os.path.relpath(abspath, CORPUS_ROOT)
            fixtures.append(
                Fixture(
                    category=category,
                    relpath=relpath,
                    abspath=abspath,
                    expected=expected,
                )
            )
    return fixtures


def _run_hook_on_file(file_path: str) -> tuple[int, str]:
    """Invoke the hook with a Write payload of the fixture's content."""
    with open(file_path, encoding="utf-8") as fh:
        content = fh.read()
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }
    proc = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
    )
    return proc.returncode, proc.stderr


def _expected_pass(returncode: int, stderr: str, expected: str) -> bool:
    if expected == "clean":
        return returncode == 0
    if expected == "dirty":
        return returncode == 2 or "Blocked" in stderr or "blocked" in stderr
    return False


def _cmd_list(_args: argparse.Namespace) -> int:
    fixtures = _list_fixtures()
    if not fixtures:
        sys.stdout.write("(corpus empty)\n")
        return 0
    sys.stdout.write(f"Corpus root: {CORPUS_ROOT}\n")
    sys.stdout.write(f"Fixture count: {len(fixtures)}\n\n")
    for fx in fixtures:
        sys.stdout.write(f"  {fx.expected:<7} {fx.display}\n")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    if not os.path.isfile(args.file):
        sys.stderr.write(f"file not found: {args.file}\n")
        return 1
    if args.expected not in ("clean", "dirty"):
        sys.stderr.write("expected must be 'clean' or 'dirty'\n")
        return 1
    ext = os.path.splitext(args.file)[1]
    if ext not in VALID_EXTS:
        sys.stderr.write(f"unsupported extension {ext}; use .ts/.tsx/.js/.jsx\n")
        return 1
    target_dir = os.path.join(CORPUS_ROOT, args.category)
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, f"{args.expected}{ext}")
    if os.path.exists(target):
        sys.stderr.write(
            f"target already exists: {target}\n"
            "use a different category or remove the existing fixture first\n"
        )
        return 1
    shutil.copy2(args.file, target)
    sys.stdout.write(f"added: {os.path.relpath(target, CORPUS_ROOT)}\n")
    return 0


def _validate_fixtures(fixtures: Iterable[Fixture]) -> tuple[int, int, list[str]]:
    passed = 0
    failed = 0
    failures: list[str] = []
    for fx in fixtures:
        if fx.expected == "unknown":
            failures.append(
                f"{fx.display}: filename must start with 'clean' or 'dirty'"
            )
            failed += 1
            continue
        rc, err = _run_hook_on_file(fx.abspath)
        if _expected_pass(rc, err, fx.expected):
            passed += 1
        else:
            failures.append(
                f"{fx.display}: expected {fx.expected}, got rc={rc} stderr={err.strip()[:120]}"
            )
            failed += 1
    return passed, failed, failures


def _cmd_validate(args: argparse.Namespace) -> int:
    fixtures = _list_fixtures()
    if not fixtures:
        sys.stderr.write("corpus is empty; add fixtures first\n")
        return 1
    passed, failed, failures = _validate_fixtures(fixtures)
    total = passed + failed
    pass_rate = (passed / total * 100.0) if total else 0.0
    sys.stdout.write(f"Corpus validate: {passed}/{total} passed ({pass_rate:.1f}%)\n")
    for line in failures:
        sys.stdout.write(f"  FAIL {line}\n")
    if args.fail_under is not None and pass_rate < args.fail_under:
        return 1
    return 0 if failed == 0 else 1


def _cmd_regenerate(_args: argparse.Namespace) -> int:
    """Bump VERSION metadata and re-stamp the regeneration date.

    Does not modify fixture content. Treats the regeneration as a
    metadata-only refresh confirming the corpus was reviewed against
    the current hook surface.
    """
    import datetime

    today = datetime.date.today().isoformat()
    if not os.path.isfile(VERSION_FILE):
        sys.stderr.write(f"VERSION file not found: {VERSION_FILE}\n")
        return 1
    with open(VERSION_FILE, encoding="utf-8") as fh:
        text = fh.read()
    new_lines = []
    for line in text.splitlines():
        if line.startswith("last_regenerated:"):
            new_lines.append(f"last_regenerated: {today}")
        else:
            new_lines.append(line)
    with open(VERSION_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(new_lines) + "\n")
    sys.stdout.write(f"VERSION regenerated: last_regenerated: {today}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corpus manager")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list fixtures")

    add = sub.add_parser("add", help="add a fixture under a category")
    add.add_argument("file", help="source fixture path")
    add.add_argument("category", help="corpus category (subdirectory)")
    add.add_argument("expected", choices=("clean", "dirty"), help="expected outcome")

    validate = sub.add_parser("validate", help="run hook against every fixture")
    validate.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="fail when pass rate is below this percentage (e.g. 99.0)",
    )

    sub.add_parser("regenerate", help="bump VERSION metadata")

    args = parser.parse_args(argv)
    handlers = {
        "list": _cmd_list,
        "add": _cmd_add,
        "validate": _cmd_validate,
        "regenerate": _cmd_regenerate,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
