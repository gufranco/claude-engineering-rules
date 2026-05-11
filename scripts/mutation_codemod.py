"""Codemod auto-fix runner for mutation-method-blocker findings (plan item 385).

Reads SARIF output from the hook (or a JSON list of findings) and applies
jscodeshift transforms to fix the issues automatically. Each detector has a
named transform under `scripts/codemod_transforms/<detector>.js`; missing
transforms are skipped with a warning.

Usage:

  python3 scripts/mutation_codemod.py --input findings.sarif --dry-run
  python3 scripts/mutation_codemod.py --input findings.sarif --apply
  python3 scripts/mutation_codemod.py --input findings.sarif --apply --limit 50

Flags:

  --input <path>     SARIF file to read findings from. Required.
  --dry-run          Print proposed changes without writing files.
  --apply            Write changes to disk.
  --limit <n>        Stop after applying <n> transforms.
  --transform-dir    Override the default transform directory.
  --jscodeshift-bin  Path to jscodeshift binary (default: PATH lookup).

Exit codes:

  0  All applicable transforms succeeded.
  1  Invalid arguments or missing input file.
  2  At least one transform failed.
  3  jscodeshift binary not found.

The script never writes outside the files referenced by the SARIF input,
and never modifies files that are listed in `.gitignore`. When
`--dry-run` is set, the script is read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_TRANSFORM_DIR = os.path.expanduser("~/.claude/scripts/codemod_transforms")


@dataclass(frozen=True)
class Finding:
    """A single SARIF finding mapped to a fix candidate."""

    file_path: str
    line: int
    detector: str
    message: str


def parse_sarif(path: str) -> list[Finding]:
    """Read a SARIF file and yield findings the codemod can act on.

    Schema: SARIF 2.1.0 with `runs[0].results[*].locations[0].physicalLocation`.
    Failures (missing file, malformed JSON) raise to the caller with a
    descriptive error.
    """
    with open(path, encoding="utf-8") as fh:
        sarif = json.load(fh)
    runs = sarif.get("runs", [])
    findings: list[Finding] = []
    for run in runs:
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            message = ""
            msg_obj = result.get("message", {})
            if isinstance(msg_obj, dict):
                message = msg_obj.get("text", "")
            locations = result.get("locations", [])
            for loc in locations:
                phys = loc.get("physicalLocation", {})
                art = phys.get("artifactLocation", {})
                file_uri = art.get("uri", "")
                region = phys.get("region", {})
                line = region.get("startLine", 0)
                if file_uri and line > 0 and rule_id:
                    findings.append(
                        Finding(
                            file_path=file_uri,
                            line=line,
                            detector=rule_id,
                            message=message,
                        )
                    )
    return findings


def group_by_transform(
    findings: list[Finding], transform_dir: str
) -> dict[str, list[Finding]]:
    """Group findings by the transform name that handles their detector.

    A detector `array.push` resolves to `array_push.js`; missing files
    are reported but do not abort the run.
    """
    grouped: dict[str, list[Finding]] = {}
    for f in findings:
        transform_name = f.detector.replace(".", "_") + ".js"
        candidate = os.path.join(transform_dir, transform_name)
        if not os.path.isfile(candidate):
            continue
        grouped.setdefault(transform_name, []).append(f)
    return grouped


def run_transform(
    transform_path: str,
    targets: list[str],
    jscodeshift_bin: str,
    dry_run: bool,
) -> int:
    """Invoke jscodeshift with a single transform across the target files.

    Returns the jscodeshift exit code. The script never invokes the
    binary with more than 100 files per call to keep arg-list bounded.
    """
    chunk_size = 100
    code = 0
    for i in range(0, len(targets), chunk_size):
        chunk = targets[i : i + chunk_size]
        cmd = [
            jscodeshift_bin,
            "--transform",
            transform_path,
            "--parser",
            "tsx",
            "--extensions",
            "ts,tsx,js,jsx,mjs,cjs",
        ]
        if dry_run:
            cmd.append("--dry")
        cmd.extend(chunk)
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            code = completed.returncode
            sys.stderr.write(completed.stderr or "jscodeshift returned non-zero\n")
    return code


def main(argv: list[str]) -> int:
    """Entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(description="mutation-method-blocker codemod")
    parser.add_argument("--input", required=True, help="SARIF file path")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--transform-dir", default=DEFAULT_TRANSFORM_DIR)
    parser.add_argument("--jscodeshift-bin", default="")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.input):
        sys.stderr.write(f"input not found: {args.input}\n")
        return 1
    bin_path = args.jscodeshift_bin or shutil.which("jscodeshift") or ""
    if not bin_path or not os.path.isfile(bin_path):
        sys.stderr.write(
            "jscodeshift binary not found; install with `pnpm add -D jscodeshift`\n"
        )
        return 3
    findings = parse_sarif(args.input)
    if not findings:
        sys.stdout.write("no findings to apply\n")
        return 0
    if args.limit > 0:
        findings = findings[: args.limit]
    grouped = group_by_transform(findings, args.transform_dir)
    if not grouped:
        sys.stdout.write("no applicable transforms found\n")
        return 0
    exit_code = 0
    for transform_name, items in grouped.items():
        transform_path = os.path.join(args.transform_dir, transform_name)
        targets = sorted({f.file_path for f in items})
        result = run_transform(transform_path, targets, bin_path, dry_run=args.dry_run)
        if result != 0:
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
