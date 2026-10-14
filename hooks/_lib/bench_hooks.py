from __future__ import annotations
import argparse
import json
import math
import os
import re
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
HOOK_COMMAND = re.compile(r"hooks/([\w.-]+\.py)\b")
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
    hook: str
    payload: str
    duration_ms: float
    exit_code: int
    timed_out: bool = False


@dataclass(frozen=True)
class HookStats:
    hook: str
    n: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    timeouts: int = 0
    nonzero_exits: int = 0
    worst_exit: int = 0
    payloads: list[str] = field(default_factory=list)


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


def registered_hooks(settings_path: str, hooks_dir: str, event: str) -> list[str]:
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
    groups = settings.get("hooks", {}).get(event, [])
    commands = [
        hook.get("command", "") for group in groups for hook in group.get("hooks", [])
    ]
    names = sorted({m.group(1) for m in map(HOOK_COMMAND.search, commands) if m})
    return [os.path.join(hooks_dir, name) for name in names]


def gate_violations(
    stats: list[HookStats], missing: list[str], threshold_ms: float
) -> list[str]:
    return [
        *(f"{_hook_basename(path)}: missing" for path in missing),
        *(
            f"{s.hook}: p50 {s.p50_ms} ms over {threshold_ms:g} ms"
            for s in stats
            if s.p50_ms > threshold_ms
        ),
        *(f"{s.hook}: {s.timeouts} timeouts" for s in stats if s.timeouts),
        *(f"{s.hook}: exited {s.worst_exit}" for s in stats if s.nonzero_exits),
    ]


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
    grouped: dict[str, list[Sample]] = {}
    for sample in samples:
        grouped.setdefault(sample.hook, []).append(sample)
    out: list[HookStats] = []
    for hook, items in sorted(grouped.items()):
        durations = sorted(item.duration_ms for item in items)
        timeouts = sum(1 for item in items if item.timed_out)
        nonzero = sum(1 for item in items if item.exit_code not in (0, 2))
        crashes = [item.exit_code for item in items if item.exit_code not in (0, 2)]
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
                worst_exit=crashes[0] if crashes else 0,
                payloads=sorted({item.payload for item in items}),
            )
        )
    return out


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


def _filter_hooks(paths: list[str], include: Iterable[str] | None) -> list[str]:
    if not include:
        return paths
    wanted = set(include)
    out = [p for p in paths if _hook_basename(p) in wanted]
    return out


def _add_selection_args(parser: argparse.ArgumentParser) -> None:
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


def _add_run_args(parser: argparse.ArgumentParser) -> None:
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


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="Benchmark only the hooks this settings file registers for --event.",
    )
    parser.add_argument("--event", default="PreToolUse")


def _add_gate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--threshold-ms",
        type=float,
        default=None,
        help="Exit 1 on a p50 over this, a timeout, a crash, or a missing hook.",
    )
    parser.add_argument(
        "--write-baseline",
        default=None,
        help="Write markdown report to this path (e.g., notes/perf-baseline.md).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark Claude Code Python hooks for regression detection."
    )
    _add_selection_args(parser)
    _add_run_args(parser)
    _add_output_args(parser)
    _add_gate_args(parser)
    return parser


def _selected_hooks(args: argparse.Namespace) -> list[str]:
    selected = (
        registered_hooks(args.settings, args.hooks_dir, args.event)
        if args.settings
        else discover_hooks(args.hooks_dir)
    )
    return _filter_hooks(selected, args.hook)


def _write_baseline(target: str, stats: list[HookStats], iterations: int) -> None:
    markdown = _format_markdown(stats, iterations=iterations, payloads=sorted(PAYLOADS))
    baseline_path = os.path.expanduser(target)
    os.makedirs(os.path.dirname(baseline_path) or ".", exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    sys.stdout.write(f"Wrote baseline to {baseline_path}\n")


def _render(output_format: str, stats: list[HookStats], iterations: int) -> str:
    if output_format == "json":
        return _format_json(stats)
    if output_format == "markdown":
        return _format_markdown(stats, iterations=iterations, payloads=sorted(PAYLOADS))
    return _format_table(stats)


def _cli(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    iterations = max(1, args.iterations)
    warmup = max(0, args.warmup)
    selected = _selected_hooks(args)
    if not selected:
        sys.stderr.write("No hooks selected.\n")
        return 1
    missing = [path for path in selected if not os.path.isfile(path)]
    paths = [path for path in selected if os.path.isfile(path)]
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
        _write_baseline(args.write_baseline, stats, iterations)
    sys.stdout.write(_render(args.format, stats, iterations))
    if args.threshold_ms is None:
        return 0
    return _report_gate(gate_violations(stats, missing, args.threshold_ms))


def _report_gate(violations: list[str]) -> int:
    for violation in violations:
        sys.stderr.write(f"FAIL {violation}\n")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
