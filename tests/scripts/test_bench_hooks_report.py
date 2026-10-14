from __future__ import annotations

import json

import pytest

from _helpers.bench_hooks_support import (
    TABLE_HEADER,
    TABLE_RULE,
    bench_hooks,
)


def test_aggregate_groups_samples_by_hook() -> None:
    # Arrange
    samples = [
        bench_hooks.Sample(hook="a", payload="bash", duration_ms=10.0, exit_code=0),
        bench_hooks.Sample(hook="a", payload="write", duration_ms=20.0, exit_code=0),
        bench_hooks.Sample(hook="b", payload="bash", duration_ms=5.0, exit_code=0),
    ]

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    assert [(s.hook, s.n, s.mean_ms) for s in stats] == [("a", 2, 15.0), ("b", 1, 5.0)]


def test_aggregate_returns_sorted_by_hook_name() -> None:
    # Arrange
    samples = [
        bench_hooks.Sample(hook="zeta", payload="bash", duration_ms=1.0, exit_code=0),
        bench_hooks.Sample(hook="alpha", payload="bash", duration_ms=2.0, exit_code=0),
    ]

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    assert [s.hook for s in stats] == ["alpha", "zeta"]


def test_aggregate_counts_timeouts_and_nonzero_exits() -> None:
    # Arrange
    samples = [
        bench_hooks.Sample(
            hook="x", payload="bash", duration_ms=10.0, exit_code=0, timed_out=False
        ),
        bench_hooks.Sample(
            hook="x", payload="bash", duration_ms=10.0, exit_code=2, timed_out=False
        ),
        bench_hooks.Sample(
            hook="x", payload="bash", duration_ms=10.0, exit_code=-1, timed_out=True
        ),
        bench_hooks.Sample(
            hook="x", payload="bash", duration_ms=10.0, exit_code=7, timed_out=False
        ),
    ]

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    assert [(s.hook, s.timeouts, s.nonzero_exits, s.worst_exit) for s in stats] == [
        ("x", 1, 2, -1)
    ]


def test_aggregate_computes_mean_p50_p95_p99() -> None:
    # Arrange
    samples = [
        bench_hooks.Sample(hook="x", payload="bash", duration_ms=float(i), exit_code=0)
        for i in range(1, 101)
    ]

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    s = stats[0]
    assert s.n == 100
    assert s.mean_ms == pytest.approx(50.5)
    assert s.p50_ms == pytest.approx(50.5)
    assert s.p95_ms == pytest.approx(95.05)
    assert s.p99_ms == pytest.approx(99.01)
    assert s.max_ms == 100.0


def test_aggregate_includes_unique_payloads_sorted() -> None:
    # Arrange
    samples = [
        bench_hooks.Sample(hook="x", payload="write", duration_ms=1.0, exit_code=0),
        bench_hooks.Sample(hook="x", payload="bash", duration_ms=1.0, exit_code=0),
        bench_hooks.Sample(hook="x", payload="edit", duration_ms=1.0, exit_code=0),
        bench_hooks.Sample(hook="x", payload="bash", duration_ms=1.0, exit_code=0),
    ]

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    assert stats[0].payloads == ["bash", "edit", "write"]


def test_aggregate_with_no_samples_returns_empty() -> None:
    # Arrange
    samples: list[bench_hooks.Sample] = []

    # Act
    stats = bench_hooks.aggregate(samples)

    # Assert
    assert stats == []


def _stat(hook: str = "demo", n: int = 5) -> bench_hooks.HookStats:
    return bench_hooks.HookStats(
        hook=hook,
        n=n,
        mean_ms=12.34,
        p50_ms=11.0,
        p95_ms=15.5,
        p99_ms=17.7,
        max_ms=20.0,
        timeouts=0,
        nonzero_exits=0,
        payloads=["bash", "edit", "write"],
    )


def test_format_table_includes_header_and_row() -> None:
    # Arrange
    stats = [_stat()]

    # Act
    table = bench_hooks._format_table(stats)

    # Assert
    assert table == (
        f"{TABLE_HEADER}\n"
        f"{TABLE_RULE}\n"
        "demo  5  12.34  11.00  15.50  17.70  20.00  0       \n"
    )


def test_format_table_no_stats_returns_placeholder() -> None:
    # Arrange
    stats: list[bench_hooks.HookStats] = []

    # Act
    table = bench_hooks._format_table(stats)

    # Assert
    assert table == "No hooks benchmarked.\n"


def test_format_json_returns_parseable_array() -> None:
    # Arrange
    stats = [_stat("alpha"), _stat("beta")]

    # Act
    rendered = bench_hooks._format_json(stats)

    # Assert
    parsed = json.loads(rendered)
    assert [item["hook"] for item in parsed] == ["alpha", "beta"]
    assert parsed[0] == {
        "hook": "alpha",
        "n": 5,
        "mean_ms": 12.34,
        "p50_ms": 11.0,
        "p95_ms": 15.5,
        "p99_ms": 17.7,
        "max_ms": 20.0,
        "timeouts": 0,
        "nonzero_exits": 0,
        "worst_exit": 0,
        "payloads": ["bash", "edit", "write"],
    }


def test_format_markdown_includes_header_table_and_iteration_count() -> None:
    # Arrange
    stats = [_stat("demo")]

    # Act
    rendered = bench_hooks._format_markdown(
        stats, iterations=42, payloads=["bash", "edit"]
    )

    # Assert
    lines = rendered.splitlines()
    assert lines[0] == "# Hook performance baseline"
    assert lines[4] == (
        "Generated by `scripts/bench_hooks.py` with iterations=42 and "
        "payloads=bash, edit."
    )
    assert lines[-3:] == [
        "| Hook | n | mean | p50 | p95 | p99 | max | timeouts |",
        "|------|---|------|-----|-----|-----|-----|----------|",
        "| `demo` | 5 | 12.34 | 11.00 | 15.50 | 17.70 | 20.00 | 0 |",
    ]


def test_filter_hooks_returns_all_when_no_include() -> None:
    # Arrange
    paths = ["/h/a.py", "/h/b.py"]

    # Act
    result = bench_hooks._filter_hooks(paths, None)

    # Assert
    assert result == paths


def test_filter_hooks_returns_all_when_include_is_empty() -> None:
    # Arrange
    paths = ["/h/a.py", "/h/b.py"]

    # Act
    result = bench_hooks._filter_hooks(paths, [])

    # Assert
    assert result == paths


def test_filter_hooks_keeps_only_matching_basenames() -> None:
    # Arrange
    paths = ["/h/a.py", "/h/b.py", "/h/c.py"]

    # Act
    result = bench_hooks._filter_hooks(paths, ["a", "c"])

    # Assert
    assert result == ["/h/a.py", "/h/c.py"]
