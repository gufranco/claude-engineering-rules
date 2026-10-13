from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "hooks"
sys.path.insert(0, str(SCRIPTS_DIR))

from _lib import bench_hooks  # noqa: E402

DEFAULT_PAYLOAD_COUNT = 3
TABLE_HEADER = "hook  n  mean   p50    p95    p99    max    timeouts"
TABLE_RULE = "----  -  -----  -----  -----  -----  -----  --------"

Payload = dict[str, object]


def _bash(faker: Faker) -> Payload:
    return {"tool_name": "Bash", "tool_input": {"command": faker.word()}}


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
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


def test_discover_hooks_returns_sorted_python_files(hooks_dir: Path) -> None:
    # Arrange
    _write_hook(hooks_dir, "z-last", _allow_hook())
    _write_hook(hooks_dir, "a-first", _allow_hook())
    _write_hook(hooks_dir, "m-mid", _allow_hook())

    # Act
    discovered = bench_hooks.discover_hooks(str(hooks_dir))

    # Assert
    assert [Path(p).name for p in discovered] == ["a-first.py", "m-mid.py", "z-last.py"]


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
    argument = str(hooks_dir)

    # Act
    discovered = bench_hooks.discover_hooks(argument)

    # Assert
    assert discovered == []


def test_hook_basename_strips_dotpy(faker: Faker) -> None:
    # Arrange
    name = faker.word()
    path = f"/{faker.word()}/hooks/{name}.py"

    # Act
    result = bench_hooks._hook_basename(path)

    # Assert
    assert result == name


def test_hook_basename_returns_basename_for_no_extension(faker: Faker) -> None:
    # Arrange
    name = faker.word()
    path = f"/{faker.word()}/hooks/{name}"

    # Act
    result = bench_hooks._hook_basename(path)

    # Assert
    assert result == name


def test_run_one_returns_zero_for_allow_hook(hooks_dir: Path, faker: Faker) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())

    # Act
    duration_ms, code, timed_out = bench_hooks.run_one(str(path), _bash(faker))

    # Assert
    assert code == 0
    assert timed_out is False
    assert duration_ms > 0.0


def test_run_one_returns_two_for_block_hook(hooks_dir: Path, faker: Faker) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "blocker", _block_hook())

    # Act
    _, code, timed_out = bench_hooks.run_one(str(path), _bash(faker))

    # Assert
    assert code == 2
    assert timed_out is False


def test_run_one_marks_timeout(hooks_dir: Path, faker: Faker) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "slow", _slow_hook(30.0))

    # Act
    duration_ms, code, timed_out = bench_hooks.run_one(
        str(path), _bash(faker), timeout_s=0.2
    )

    # Assert
    assert timed_out is True
    assert code == -1
    assert duration_ms > 0.0


def test_run_one_passes_through_extra_env(
    hooks_dir: Path, tmp_path: Path, faker: Faker
) -> None:
    # Arrange
    marker = tmp_path / "marker.txt"
    value = faker.word()
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
    bench_hooks.run_one(str(path), _bash(faker), env={"CUSTOM_VAR": value})

    # Assert
    assert marker.read_text(encoding="utf-8") == value


def test_run_one_disables_audit_emission_by_default(
    hooks_dir: Path, tmp_path: Path, faker: Faker
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
    bench_hooks.run_one(str(path), _bash(faker))

    # Assert
    assert marker.read_text(encoding="utf-8") == "1"


def test_iter_samples_yields_one_sample_per_iteration_per_payload(
    hooks_dir: Path, faker: Faker
) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    payloads = {"p1": _bash(faker), "p2": _bash(faker)}

    # Act
    samples = list(
        bench_hooks.iter_samples([str(path)], iterations=3, payloads=payloads, warmup=0)
    )

    # Assert
    assert [(s.hook, s.payload, s.exit_code) for s in samples] == [
        ("ok", "p1", 0),
        ("ok", "p1", 0),
        ("ok", "p1", 0),
        ("ok", "p2", 0),
        ("ok", "p2", 0),
        ("ok", "p2", 0),
    ]


def test_iter_samples_runs_warmup_without_yielding(
    hooks_dir: Path, faker: Faker
) -> None:
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
    payloads = {"p1": _bash(faker)}

    # Act
    samples = list(
        bench_hooks.iter_samples([str(path)], iterations=2, payloads=payloads, warmup=2)
    )

    # Assert
    assert len(samples) == 2
    assert counter.read_text(encoding="utf-8") == "4"


def test_iter_samples_treats_negative_warmup_as_zero(
    hooks_dir: Path, faker: Faker
) -> None:
    # Arrange
    path = _write_hook(hooks_dir, "ok", _allow_hook())
    payloads = {"p1": _bash(faker)}

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

    # Assert
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert lines[:2] == [TABLE_HEADER, TABLE_RULE]
    assert lines[2].split()[:2] == ["ok", str(DEFAULT_PAYLOAD_COUNT)]
    assert len(lines) == 3


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

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert [
        (i["hook"], i["n"], i["timeouts"], i["nonzero_exits"], i["payloads"])
        for i in parsed
    ] == [("ok", DEFAULT_PAYLOAD_COUNT, 0, 0, ["bash", "edit", "write"])]


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

    # Assert
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert lines[0] == "# Hook performance baseline"
    assert lines[4] == (
        "Generated by `scripts/bench_hooks.py` with iterations=1 and "
        "payloads=bash, edit, write."
    )
    assert lines[-1].startswith("| `ok` | 3 | ") is True


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
    lines = baseline.read_text(encoding="utf-8").splitlines()
    assert rc == 0
    assert capsys.readouterr().out.splitlines()[0] == f"Wrote baseline to {baseline}"
    assert lines[0] == "# Hook performance baseline"
    assert lines[-1].startswith("| `ok` | 3 | ") is True


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

    # Assert
    captured = capsys.readouterr()
    assert rc == 1
    assert (captured.out, captured.err) == ("", "No hooks selected.\n")


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

    # Assert
    captured = capsys.readouterr()
    assert rc == 1
    assert (captured.out, captured.err) == ("", "No hooks selected.\n")


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

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert [item["n"] for item in parsed] == [DEFAULT_PAYLOAD_COUNT]


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

    # Assert
    captured = capsys.readouterr()
    assert rc == 0
    parsed = json.loads(captured.out)
    assert [item["hook"] for item in parsed] == ["alpha"]


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
    assert [(item["hook"], item["n"]) for item in parsed] == [
        ("ok", DEFAULT_PAYLOAD_COUNT)
    ]
