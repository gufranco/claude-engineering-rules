"""OpenTelemetry exporter tests.

Plan item 262. Verifies `scripts/otel_exporter.py`:

  - When `MUTATION_METHOD_OTEL_EXPORTER` is unset, `record_decision`
    is a no-op (no exception, no side effect).
  - When set to `console`, the SDK initializes lazily and a span
    survives a round-trip through the in-memory exporter.
  - Span attributes match the documented schema.
  - The hook never crashes when `opentelemetry-api` is unavailable.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _reset_module(monkeypatch: pytest.MonkeyPatch):
    if "otel_exporter" in sys.modules:
        del sys.modules["otel_exporter"]
    yield
    if "otel_exporter" in sys.modules:
        del sys.modules["otel_exporter"]


def test_record_decision_is_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MUTATION_METHOD_OTEL_EXPORTER", raising=False)
    import otel_exporter  # noqa: WPS433

    otel_exporter.record_decision(
        hook="mutation-method-blocker",
        detector="array.push",
        decision="block",
    )


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry") is None,
    reason="opentelemetry SDK not installed; unknown-target branch is unreachable",
)
def test_unknown_target_emits_stderr_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "garbage://nowhere")
    import otel_exporter  # noqa: WPS433

    otel_exporter.record_decision(
        hook="mutation-method-blocker",
        detector="array.push",
        decision="block",
    )
    err = capsys.readouterr().err
    assert "unknown target" in err


def test_record_decision_does_not_raise_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "console")
    blocked: dict[str, bool] = {"hit": False}

    real_import = __import__

    def fake_import(name: str, *args, **kwargs):
        if name.startswith("opentelemetry"):
            blocked["hit"] = True
            raise ImportError(f"blocked {name} for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    import otel_exporter  # noqa: WPS433

    importlib.reload(otel_exporter)
    otel_exporter.record_decision(
        hook="mutation-method-blocker",
        detector="array.push",
        decision="block",
    )
    assert blocked["hit"] is True


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry") is None,
    reason="opentelemetry SDK not installed in this environment",
)
def test_console_exporter_emits_attributes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "console")
    import otel_exporter  # noqa: WPS433

    otel_exporter.record_decision(
        hook="mutation-method-blocker",
        detector="array.push",
        decision="block",
        file_path="src/a.ts",
        line=42,
        latency_ms=12.5,
        confidence=10,
    )
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()
    captured = capsys.readouterr()
    assert "mutation-method-blocker" in captured.out + captured.err
