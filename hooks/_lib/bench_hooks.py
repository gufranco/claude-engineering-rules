"""Benchmark Claude Code Python hooks against representative payloads.
The runtime dispatches every hook on every matching tool call. A hook that
spends 400 ms parsing pushes user latency into the visible range. The bench
records per-hook p50/p95/p99 so a regression that doubles a hook's cost is
caught by `notes/perf-baseline.md` rather than by user complaints.
For each hook the bench runs the same payload N times in a fresh subprocess
to mirror Claude Code's invocation model (one process per call). Three
canonical payloads are dispatched:
    1. `bash` - a Bash tool call with a benign command. Exercises the no-op
       fast-allow path that every hook must take when the tool does not
       match its area of interest.
    2. `write` - a Write tool call writing a small TypeScript snippet.
       Exercises the typical content-scanning path.
    3. `edit` - an Edit tool call with a small `new_string`. Exercises the
       single-line code-style path.
All three are intentionally small. Fixture-realism is covered by the per-hook
suites in `tests/hooks/<name>/`. The bench is the regression gate, not a
correctness test.
Usage:
    python3 scripts/bench_hooks.py                 # all hooks, table output
    python3 scripts/bench_hooks.py --iterations 50 --format json
    python3 scripts/bench_hooks.py --hook secret-scanner --hook redis-atomicity
    python3 scripts/bench_hooks.py --write-baseline notes/perf-baseline.md
"""

from __future__ import annotations
import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_HOOKS_DIR = os.path.expanduser("~/.claude/hooks")
DEFAULT_ITERATIONS = 20
DEFAULT_TIMEOUT_S = 10.0
SUBPROCESS_KILL_GRACE_S = 1.0
# Canonical payloads. Kept tiny so the bench stays under a minute even on
# slow laptops and so a single payload size dominates noise.
PAYLOADS: dict[str, dict[str, Any]] = {
    "bash": {
        "tool_name": "Bash",
        "tool_input": {"command": "echo hello world"},
        "hook_event_name": "PreToolUse",
    },
    "write": {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/repo/src/example.ts",
            "content": (
                "import { useState } from 'react'\n\n"
                "export function Counter() {\n"
                "  const [count, setCount] = useState(0)\n"
                "  return count\n"
                "}\n"
            ),
        },
        "hook_event_name": "PreToolUse",
    },
    "edit": {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/src/example.ts",
            "old_string": "return count",
            "new_string": "return count + 1",
        },
        "hook_event_name": "PreToolUse",
    },
}


@dataclass(frozen=True)
class Sample:
    """One subprocess invocation result."""

    hook: str
    payload: str
    duration_ms: float
    exit_code: int
    timed_out: bool = False


@dataclass(frozen=True)
class HookStats:
    """Aggregate latency stats for a single hook."""

    hook: str
    n: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    timeouts: int = 0
    nonzero_exits: int = 0
    payloads: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# core helpers
# --------------------------------------------------------------------------- #
def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * p
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_values[lo])
    weight = rank - lo
    return float(sorted_values[lo] * (1 - weight) + sorted_values[hi] * weight)


def discover_hooks(hooks_dir: str) -> list[str]:
    """Return absolute paths of `hooks_dir/*.py`, skipping underscore files."""
    if not os.path.isdir(hooks_dir):
        return []
    out: list[str] = []
    for entry in sorted(os.listdir(hooks_dir)):
        if not entry.endswith(".py"):
            continue
        if entry.startswith("_"):
            continue
        path = os.path.join(hooks_dir, entry)
        if os.path.isfile(path):
            out.append(path)
    return out


def _hook_basename(path: str) -> str:
    base = os.path.basename(path)
    if base.endswith(".py"):
        base = base[: -len(".py")]
    return base


def run_one(
    hook_path: str,
    payload: dict[str, Any],
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    env: dict[str, str] | None = None,
) -> tuple[float, int, bool]:
    """Run one subprocess invocation and return `(duration_ms, exit_code, timed_out)`."""
    invocation_env = dict(os.environ)
    invocation_env["CLAUDE_HOOK_AUDIT_DISABLE"] = "1"
    if env:
        invocation_env.update(env)
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, hook_path],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=invocation_env,
            check=False,
        )
        duration_ms = (time.perf_counter() - start) * 1000.0
        return duration_ms, proc.returncode, False
    except subprocess.TimeoutExpired:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return duration_ms, -1, True


def iter_samples(
    hook_paths: Iterable[str],
    *,
    iterations: int,
    payloads: dict[str, dict[str, Any]] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    warmup: int = 1,
    env: dict[str, str] | None = None,
) -> Iterator[Sample]:
    """Yield Sample objects across the hook list, payloads, and iterations.
    A small `warmup` number of un-recorded runs precedes the recorded loop
    so disk-cache and Python-startup cost are amortized.
    """
    payloads = payloads or PAYLOADS
    for hook_path in hook_paths:
        hook = _hook_basename(hook_path)
        for _ in range(max(0, warmup)):
            for body in payloads.values():
                run_one(hook_path, body, timeout_s=timeout_s, env=env)
        for payload_name, body in payloads.items():
            for _ in range(iterations):
                duration_ms, code, timed_out = run_one(
                    hook_path, body, timeout_s=timeout_s, env=env
                )
                yield Sample(
                    hook=hook,
                    payload=payload_name,
                    duration_ms=duration_ms,
                    exit_code=code,
                    timed_out=timed_out,
                )


def aggregate(samples: Iterable[Sample]) -> list[HookStats]:
    """Group samples by hook, compute summary stats for each."""
    grouped: dict[str, list[Sample]] = {}
    for sample in samples:
        grouped.setdefault(sample.hook, []).append(sample)
    out: list[HookStats] = []
    for hook, items in sorted(grouped.items()):
        durations = sorted(item.duration_ms for item in items)
        timeouts = sum(1 for item in items if item.timed_out)
        nonzero = sum(1 for item in items if item.exit_code not in (0, 2))
        mean = statistics.fmean(durations)
        out.append(
            HookStats(
                hook=hook,
                n=len(durations),
                mean_ms=round(mean, 2),
                p50_ms=round(_percentile(durations, 0.50), 2),
                p95_ms=round(_percentile(durations, 0.95), 2),
                p99_ms=round(_percentile(durations, 0.99), 2),
                max_ms=round(max(durations), 2),
                timeouts=timeouts,
                nonzero_exits=nonzero,
                payloads=sorted({item.payload for item in items}),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _format_table(stats: list[HookStats]) -> str:
    if not stats:
        return "No hooks benchmarked.\n"
    headers = ("hook", "n", "mean", "p50", "p95", "p99", "max", "timeouts")
    rows = [
        (
            s.hook,
            str(s.n),
            f"{s.mean_ms:.2f}",
            f"{s.p50_ms:.2f}",
            f"{s.p95_ms:.2f}",
            f"{s.p99_ms:.2f}",
            f"{s.max_ms:.2f}",
            str(s.timeouts),
        )
        for s in stats
    ]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    out = [line]
    out.append("  ".join("-" * w for w in widths))
    for row in rows:
        out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(out) + "\n"


def _format_json(stats: list[HookStats]) -> str:
    return json.dumps([asdict(s) for s in stats], ensure_ascii=False, indent=2) + "\n"


def _format_markdown(
    stats: list[HookStats], *, iterations: int, payloads: list[str]
) -> str:
    lines: list[str] = [
        "# Hook performance baseline",
        "",
        "",
        "",
        f"Generated by `scripts/bench_hooks.py` with iterations={iterations} and "
        f"payloads={', '.join(payloads)}.",
        "",
        "Latencies are subprocess wall time in milliseconds. The runtime spawns a "
        "fresh process per hook call, so subprocess startup is part of the budget.",
        "",
        "| Hook | n | mean | p50 | p95 | p99 | max | timeouts |",
        "|------|---|------|-----|-----|-----|-----|----------|",
    ]
    for s in stats:
        lines.append(
            f"| `{s.hook}` | {s.n} | {s.mean_ms:.2f} | {s.p50_ms:.2f} | "
            f"{s.p95_ms:.2f} | {s.p99_ms:.2f} | {s.max_ms:.2f} | {s.timeouts} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _filter_hooks(paths: list[str], include: Iterable[str] | None) -> list[str]:
    if not include:
        return paths
    wanted = set(include)
    out = [p for p in paths if _hook_basename(p) in wanted]
    return out


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Claude Code Python hooks for regression detection."
    )
    parser.add_argument(
        "--hooks-dir",
        default=DEFAULT_HOOKS_DIR,
        help="Directory containing hook *.py files (default: ~/.claude/hooks).",
    )
    parser.add_argument(
        "--hook",
        action="append",
        default=None,
        help="Limit benchmark to these hook basenames (repeatable).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Iterations per (hook, payload) pair (default: {DEFAULT_ITERATIONS}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"Per-call timeout in seconds (default: {DEFAULT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup iterations per hook before recording (default: 1).",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--write-baseline",
        default=None,
        help="Write markdown report to this path (e.g., notes/perf-baseline.md).",
    )
    args = parser.parse_args(argv)
    iterations = max(1, args.iterations)
    warmup = max(0, args.warmup)
    paths = discover_hooks(args.hooks_dir)
    paths = _filter_hooks(paths, args.hook)
    if not paths:
        sys.stderr.write("No hooks selected.\n")
        return 1
    samples = list(
        iter_samples(
            paths,
            iterations=iterations,
            payloads=PAYLOADS,
            timeout_s=args.timeout,
            warmup=warmup,
        )
    )
    stats = aggregate(samples)
    if args.write_baseline:
        markdown = _format_markdown(
            stats, iterations=iterations, payloads=sorted(PAYLOADS)
        )
        baseline_path = os.path.expanduser(args.write_baseline)
        os.makedirs(os.path.dirname(baseline_path) or ".", exist_ok=True)
        with open(baseline_path, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        sys.stdout.write(f"Wrote baseline to {baseline_path}\n")
    if args.format == "json":
        sys.stdout.write(_format_json(stats))
    elif args.format == "markdown":
        sys.stdout.write(
            _format_markdown(stats, iterations=iterations, payloads=sorted(PAYLOADS))
        )
    else:
        sys.stdout.write(_format_table(stats))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
