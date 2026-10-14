from __future__ import annotations

import textwrap
from pathlib import Path

from faker import Faker

from _helpers.bench_hooks_support import (
    _allow_hook,
    _write_hook,
    bench_hooks,
)


Payload = dict[str, object]


def _bash(faker: Faker) -> Payload:
    return {"tool_name": "Bash", "tool_input": {"command": faker.word()}}


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


def _counter_hook(counter: Path) -> str:
    return f"""
        import sys
        with open({str(counter)!r}, 'r+') as fh:
            n = int(fh.read() or '0')
            fh.seek(0)
            fh.truncate()
            fh.write(str(n + 1))
        sys.exit(0)
        """


def test_iter_samples_runs_warmup_without_yielding(
    hooks_dir: Path, faker: Faker
) -> None:
    # Arrange
    counter = hooks_dir / "counter.txt"
    counter.write_text("0", encoding="utf-8")
    path = _write_hook(hooks_dir, "ctr", _counter_hook(counter))
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
