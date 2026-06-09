"""Tests for `scripts/bench_hooks.py`.
The bench runs hooks in subprocesses and aggregates wall-time samples. Tests
build synthetic hook scripts under `tmp_path`, capture deterministic samples,
and exercise every formatter and CLI branch without touching the real
`~/.claude/hooks/` tree.
"""
from __future__ import annotations
import json
import subprocess
import sys
import textwrap
from pathlib import Path
import pytest
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS_DIR))
from _lib import bench_hooks  # noqa: E402
# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    """Empty directory tests fill with synthetic hook scripts."""
    target = tmp_path / "hooks"
    target.mkdir()
    return target
def _write_hook(directory: Path, name: str, source: str) -> Path:
    path = directory / f"{name}.py"
    path.write_text(textwrap.dedent(source).lstrip() + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path
def _allow_hook() -> str:
    return """
        import sys
        sys.exit(0)
    """
def _block_hook() -> str:
    return """
        import sys
        sys.exit(2)
    """
def _slow_hook(sleep_s: float) -> str:
    return f"""
        import time, sys
        time.sleep({sleep_s})
        sys.exit(0)
    """
# --------------------------------------------------------------------------- #
# _percentile
# --------------------------------------------------------------------------- #
def test_percentile_empty_returns_zero() -> None:
    # Arrange
    values: list[float] = []
    # Act
    result = bench_hooks._percentile(values, 0.5)
    # Assert
    assert result == 0.0
def test_percentile_single_value_returns_value() -> None:
    # Arrange
    values = [42.5]
    # Act
    result = bench_hooks._percentile(values, 0.99)
    # Assert
    assert result == 42.5
def test_percentile_p50_of_three() -> None:
    # Arrange
    values = [1.0, 2.0, 3.0]
    # Act
    result = bench_hooks._percentile(values, 0.5)
    # Assert
    assert result == 2.0
def test_percentile_interpolates_between_ranks() -> None:
    # Arrange
    values = [10.0, 20.0, 30.0, 40.0]
    # Act
    result = bench_hooks._percentile(values, 0.5)
    # Assert
    assert result == 25.0
def test_percentile_p95_picks_upper_rank() -> None:
    # Arrange
    values = [float(i) for i in range(1, 11)]
    # Act
    result = bench_hooks._percentile(values, 0.95)
    # Assert
    assert result == pytest.approx(9.55)
def test_percentile_p99_max_when_only_one_above_rank() -> None:
    # Arrange
    values = [1.0, 2.0]
    # Act
    result = bench_hooks._percentile(values, 0.99)
    # Assert
    assert result == pytest.approx(1.99)
# --------------------------------------------------------------------------- #
# discover_hooks
# --------------------------------------------------------------------------- #
def test_discover_hooks_returns_sorted_python_files(hooks_dir: Path) -> None:
    # Arrange
    _write_hook(hooks_dir, "z-last", _allow_hook())
    _write_hook(hooks_dir, "a-first", _allow_hook())
    _write_hook(hooks_dir, "m-mid", _allow_hook())
    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))
    # Assert
    names = [Path(p).name for p in discovered]
    assert names == ["a-first.py", "m-mid.py", "z-last.py"]
def test_discover_hooks_skips_underscore_prefixed_files(hooks_dir: Path) -> None:
    # Arrange
    _write_hook(hooks_dir, "_helper", _allow_hook())
    _write_hook(hooks_dir, "real", _allow_hook())
    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))
    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]
def test_discover_hooks_skips_non_python_files(hooks_dir: Path) -> None:
    # Arrange
    (hooks_dir / "config.txt").write_text("data", encoding="utf-8")
    (hooks_dir / "README.md").write_text("docs", encoding="utf-8")
    _write_hook(hooks_dir, "real", _allow_hook())
    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))
    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]
def test_discover_hooks_skips_directories_with_py_suffix(
    hooks_dir: Path,
) -> None:
    # Arrange
    (hooks_dir / "fake.py").mkdir()
    _write_hook(hooks_dir, "real", _allow_hook())
    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))
    # Assert
    assert [Path(p).name for p in discovered] == ["real.py"]
def test_discover_hooks_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "does-not-exist"
    # Act
    discovered = bench_hooks.discover_hooks(str(missing))
    # Assert
    assert discovered == []
def test_discover_hooks_returns_empty_for_empty_dir(hooks_dir: Path) -> None:
    # Arrange
    # hooks_dir fixture leaves it empty.
    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))
    # Assert
    assert discovered == []
# --------------------------------------------------------------------------- #
# _hook_basename
# --------------------------------------------------------------------------- #
def test_hook_basename_strips_dotpy() -> None:
    # Arrange
    path = "/tmp/hooks/foo.py"
    # Act
    result = bench_hooks._hook_basename(path)
    # Assert
    assert result == "foo"
def test_hook_basename_returns_basename_for_no_extension() -> None:
    # Arrange
    path = "/tmp/hooks/foo"
    # Act
    result = bench_hooks._hook_basename(path)
    # Assert
    assert result == "foo"
# --------------------------------------------------------------------------- #
# run_one
# --------------------------------------------------------------------------- #
def test_run_one_returns_zero_for_allow_hook(hooks_dir: Path) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    duration_ms, code, timed_out = bench_hooks.run_one(
        str(path), {"tool_name": "Bash", "tool_input": {"command": "echo"}}
    )
    # Assert
    assert code == 0
    assert timed_out is False
    assert duration_ms > 0.0
def test_run_one_returns_two_for_block_hook(hooks_dir: Path) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "blocker", _block_hook())
    # Act
    _, code, timed_out = bench_hooks.run_one(
        str(path), {"tool_name": "Bash", "tool_input": {"command": "echo"}}
    )
    # Assert
    assert code == 2
    assert timed_out is False
def test_run_one_marks_timeout(hooks_dir: Path) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "slow", _slow_hook(2.0))
    # Act
    duration_ms, code, timed_out = bench_hooks.run_one(
        str(path),
        {"tool_name": "Bash", "tool_input": {"command": "x"}},
        timeout_s=0.2,
    )
    # Assert
    assert timed_out is True
    assert code == -1
    assert duration_ms > 0.0
def test_run_one_passes_through_extra_env(hooks_dir: Path, tmp_path: Path) -> None:
    # Arrange
    marker = tmp_path / "marker.txt"
    body = (
        textwrap.dedent(
            f"""
        import os, sys
        with open({str(marker)!r}, 'w') as fh:
            fh.write(os.environ.get('CUSTOM_VAR', 'unset'))
        sys.exit(0)
        """
        ).lstrip()
        + "\n"
    )
    path = hooks_dir / "env.py"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    # Act
    bench_hooks.run_one(
        str(path),
        {"tool_name": "Bash", "tool_input": {"command": "x"}},
        env={"CUSTOM_VAR": "captured"},
    )
    # Assert
    assert marker.read_text(encoding="utf-8") == "captured"
def test_run_one_disables_audit_emission_by_default(
    hooks_dir: Path, tmp_path: Path
) -> None:
    # Arrange
    marker = tmp_path / "marker.txt"
    body = (
        textwrap.dedent(
            f"""
        import os, sys
        with open({str(marker)!r}, 'w') as fh:
            fh.write(os.environ.get('CLAUDE_HOOK_AUDIT_DISABLE', 'unset'))
        sys.exit(0)
        """
        ).lstrip()
        + "\n"
    )
    path = hooks_dir / "audit.py"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    # Act
    bench_hooks.run_one(
        str(path), {"tool_name": "Bash", "tool_input": {"command": "x"}}
    )
    # Assert
    assert marker.read_text(encoding="utf-8") == "1"
# --------------------------------------------------------------------------- #
# iter_samples
# --------------------------------------------------------------------------- #
def test_iter_samples_yields_one_sample_per_iteration_per_payload(
    hooks_dir: Path,
) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    payloads = {
        "p1": {"tool_name": "Bash", "tool_input": {"command": "a"}},
        "p2": {"tool_name": "Bash", "tool_input": {"command": "b"}},
    }
    # Act
    samples = list(
        bench_hooks.iter_samples([str(path)], iterations=3, payloads=payloads, warmup=0)
    )
    # Assert
    assert len(samples) == 6
    assert {s.payload for s in samples} == {"p1", "p2"}
    assert all(s.hook == "ok" for s in samples)
def test_iter_samples_runs_warmup_without_yielding(hooks_dir: Path) -> None:
    # Arrange
    counter = hooks_dir / "counter.txt"
    counter.write_text("0", encoding="utf-8")
    body = (
        textwrap.dedent(
            f"""
        import sys
        with open({str(counter)!r}, 'r+') as fh:
            n = int(fh.read() or '0')
            fh.seek(0)
            fh.truncate()
            fh.write(str(n + 1))
        sys.exit(0)
        """
        ).lstrip()
        + "\n"
    )
    path = hooks_dir / "ctr.py"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    payloads = {"p1": {"tool_name": "Bash", "tool_input": {"command": "x"}}}
    # Act
    samples = list(
        bench_hooks.iter_samples([str(path)], iterations=2, payloads=payloads, warmup=2)
    )
    # Assert
    assert len(samples) == 2
    invocations = int(counter.read_text(encoding="utf-8"))
    assert invocations == 2 + 2
def test_iter_samples_handles_negative_warmup(hooks_dir: Path) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    payloads = {"p1": {"tool_name": "Bash", "tool_input": {"command": "x"}}}
    # Act
    samples = list(
        bench_hooks.iter_samples(
            [str(path)], iterations=1, payloads=payloads, warmup=-5
        )
    )
    # Assert
    assert len(samples) == 1
def test_iter_samples_falls_back_to_default_payloads(hooks_dir: Path) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    samples = list(
        bench_hooks.iter_samples([str(path)], iterations=1, payloads=None, warmup=0)
    )
    # Assert
    assert {s.payload for s in samples} == set(bench_hooks.PAYLOADS)
# --------------------------------------------------------------------------- #
# aggregate
# --------------------------------------------------------------------------- #
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
    by_hook = {s.hook: s for s in stats}
    assert set(by_hook) == {"a", "b"}
    assert by_hook["a"].n == 2
    assert by_hook["b"].n == 1
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
    assert len(stats) == 1
    s = stats[0]
    assert s.timeouts == 1
    assert s.nonzero_exits == 2
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
# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
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
    assert "hook" in table
    assert "demo" in table
    assert "12.34" in table
    assert table.endswith("\n")
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
    assert parsed[0]["p95_ms"] == 15.5
def test_format_markdown_includes_header_table_and_iteration_count() -> None:
    # Arrange
    stats = [_stat("demo")]
    # Act
    rendered = bench_hooks._format_markdown(
        stats, iterations=42, payloads=["bash", "edit"]
    )
    # Assert
    assert "# Hook performance baseline" in rendered
    assert "iterations=42" in rendered
    assert "| `demo` |" in rendered
    assert "p99" in rendered
# --------------------------------------------------------------------------- #
# _filter_hooks
# --------------------------------------------------------------------------- #
def test_filter_hooks_returns_all_when_no_include() -> None:
    # Arrange
    paths = ["/h/a.py", "/h/b.py"]
    # Act
    result = bench_hooks._filter_hooks(paths, None)
    # Assert
    assert result == paths
def test_filter_hooks_returns_empty_when_include_empty_iterable() -> None:
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
# --------------------------------------------------------------------------- #
# _cli
# --------------------------------------------------------------------------- #
def test_cli_table_format_writes_to_stdout(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 0
    assert "ok" in captured.out
    assert "p95" in captured.out
def test_cli_json_format_writes_array(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed[0]["hook"] == "ok"
def test_cli_markdown_format_includes_header(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--format",
            "markdown",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 0
    assert "# Hook performance baseline" in captured.out
def test_cli_writes_baseline_file(
    hooks_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    baseline = tmp_path / "out" / "perf-baseline.md"
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--write-baseline",
            str(baseline),
        ]
    )
    # Assert
    assert rc == 0
    assert baseline.exists()
    body = baseline.read_text(encoding="utf-8")
    assert "# Hook performance baseline" in body
    assert "| `ok` |" in body
def test_cli_returns_one_when_no_hooks_match(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "real", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--hook",
            "missing-name",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 1
    assert "No hooks selected." in captured.err
def test_cli_returns_one_when_directory_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    missing = tmp_path / "no-hooks"
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(missing),
            "--iterations",
            "1",
            "--warmup",
            "0",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 1
    assert "No hooks selected." in captured.err
def test_cli_clamps_iterations_to_minimum_one(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "0",
            "--warmup",
            "0",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 0
    parsed = json.loads(captured.out)
    assert parsed[0]["n"] >= 1
def test_cli_filters_to_named_hook(
    hooks_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    _write_hook(hooks_dir, "alpha", _allow_hook())
    _write_hook(hooks_dir, "beta", _allow_hook())
    # Act
    rc = bench_hooks._cli(
        [
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--hook",
            "alpha",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    # Assert
    assert rc == 0
    parsed = json.loads(captured.out)
    assert [item["hook"] for item in parsed] == ["alpha"]
# --------------------------------------------------------------------------- #
# module entrypoint
# --------------------------------------------------------------------------- #
def test_main_module_runs_via_subprocess(
    hooks_dir: Path,
) -> None:
    # Arrange
    _write_hook(hooks_dir, "ok", _allow_hook())
    script = SCRIPTS_DIR / "_lib" / "bench_hooks.py"
    # Act
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--hooks-dir",
            str(hooks_dir),
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    # Assert
    assert proc.returncode == 0
    parsed = json.loads(proc.stdout)
    assert parsed[0]["hook"] == "ok"
