"""Coverage tests for `scripts/otel_exporter.py`.

These tests stub the opentelemetry import surface so the module's
configured branches execute even when the real SDK is not installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def _reset_otel_module():
    if "otel_exporter" in sys.modules:
        del sys.modules["otel_exporter"]
    # Snapshot any opentelemetry shim so we don't poison real installations.
    snapshot = {k: v for k, v in sys.modules.items() if k.startswith("opentelemetry")}
    yield
    if "otel_exporter" in sys.modules:
        del sys.modules["otel_exporter"]
    for k in [k for k in sys.modules if k.startswith("opentelemetry")]:
        if k not in snapshot:
            del sys.modules[k]
    for k, v in snapshot.items():
        sys.modules[k] = v


def _install_otel_stub(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Insert minimal `opentelemetry.*` modules into `sys.modules` and
    return references to the mocks the tests can assert against."""
    captured: dict = {
        "spans": [],
        "exporters": [],
        "set_provider_calls": [],
    }

    span = MagicMock()

    class _SpanContext:
        def __enter__(self):
            return span

        def __exit__(self, *exc_info):
            return False

    tracer = MagicMock()
    tracer.start_as_current_span.return_value = _SpanContext()

    def _set_provider(provider):
        captured["set_provider_calls"].append(provider)

    def _get_tracer(_name):
        captured["tracer_name"] = _name
        return tracer

    trace_module = ModuleType("opentelemetry.trace")
    trace_module.set_tracer_provider = _set_provider  # type: ignore[attr-defined]
    trace_module.get_tracer = _get_tracer  # type: ignore[attr-defined]

    api_module = ModuleType("opentelemetry")
    api_module.trace = trace_module  # type: ignore[attr-defined]

    class _Provider:
        def __init__(self):
            self.processors: list = []

        def add_span_processor(self, proc):
            self.processors.append(proc)

    sdk_root = ModuleType("opentelemetry.sdk")
    sdk_trace = ModuleType("opentelemetry.sdk.trace")
    sdk_trace.TracerProvider = _Provider  # type: ignore[attr-defined]

    class _BatchSpanProcessor:
        def __init__(self, exporter):
            captured["exporters"].append(exporter)
            self.exporter = exporter

    class _ConsoleSpanExporter:
        pass

    sdk_export = ModuleType("opentelemetry.sdk.trace.export")
    sdk_export.BatchSpanProcessor = _BatchSpanProcessor  # type: ignore[attr-defined]
    sdk_export.ConsoleSpanExporter = _ConsoleSpanExporter  # type: ignore[attr-defined]

    sdk_root.trace = sdk_trace  # type: ignore[attr-defined]
    sdk_trace.export = sdk_export  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "opentelemetry", api_module)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_module)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", sdk_root)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", sdk_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace.export", sdk_export)

    captured["span"] = span
    captured["tracer"] = tracer
    return captured


def _install_otlp_http_stub(
    monkeypatch: pytest.MonkeyPatch, *, importable: bool
) -> MagicMock:
    """Install (or refuse) the OTLP HTTP exporter as a separate optional module."""
    if importable:
        otlp_module = ModuleType(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter"
        )

        class _Exporter:
            def __init__(self, endpoint: str):
                self.endpoint = endpoint

        otlp_module.OTLPSpanExporter = _Exporter  # type: ignore[attr-defined]
        # Install all parent packages so the import machinery resolves.
        parents = [
            "opentelemetry.exporter",
            "opentelemetry.exporter.otlp",
            "opentelemetry.exporter.otlp.proto",
            "opentelemetry.exporter.otlp.proto.http",
        ]
        for name in parents:
            monkeypatch.setitem(sys.modules, name, ModuleType(name))
        monkeypatch.setitem(
            sys.modules,
            "opentelemetry.exporter.otlp.proto.http.trace_exporter",
            otlp_module,
        )
        return otlp_module.OTLPSpanExporter
    # Importable=False: ensure the import fails by *not* registering the
    # module. The test relies on it being absent from sys.modules.
    return MagicMock()


# --------------------------------------------------------------------------- #
# Behavior when env var is unset
# --------------------------------------------------------------------------- #


def test_record_decision_noop_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_OTEL_EXPORTER", raising=False)
    import otel_exporter  # noqa: WPS433

    # Act / Assert: no exception, no init.
    otel_exporter.record_decision(hook="x", detector=None, decision="allow")
    assert otel_exporter._INITIALIZED is False


def test_enabled_returns_false_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_OTEL_EXPORTER", raising=False)
    import otel_exporter  # noqa: WPS433

    # Act / Assert
    assert otel_exporter._enabled() is False


def test_enabled_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "   ")
    import otel_exporter  # noqa: WPS433

    # Act / Assert
    assert otel_exporter._enabled() is False


# --------------------------------------------------------------------------- #
# Behavior when SDK initializes successfully
# --------------------------------------------------------------------------- #


def test_console_target_initializes_console_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "console")
    captured = _install_otel_stub(monkeypatch)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(
        hook="mutation-method-blocker",
        detector="array.push",
        decision="block",
        file_path="src/a.ts",
        line=42,
        latency_ms=12.5,
        confidence=10,
    )

    # Assert
    assert otel_exporter._INITIALIZED is True
    assert captured["span"].set_attribute.call_count >= 6
    keys = {call.args[0] for call in captured["span"].set_attribute.call_args_list}
    assert {
        "hook.name",
        "hook.decision",
        "hook.detector",
        "hook.file",
        "hook.line",
        "hook.latency_ms",
        "hook.confidence",
    }.issubset(keys)


def test_otlp_http_target_uses_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "otlp+http://collector:4318")
    captured = _install_otel_stub(monkeypatch)
    _install_otlp_http_stub(monkeypatch, importable=True)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(
        hook="x", detector=None, decision="allow", file_path=None, line=0
    )

    # Assert
    assert any(
        getattr(e, "endpoint", "") == "http://collector:4318"
        for e in captured["exporters"]
    )


def test_otlp_https_target_uses_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(
        "MUTATION_METHOD_OTEL_EXPORTER", "otlp+https://collector.example:4318"
    )
    captured = _install_otel_stub(monkeypatch)
    _install_otlp_http_stub(monkeypatch, importable=True)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(hook="x", detector=None, decision="allow")

    # Assert
    assert any(
        getattr(e, "endpoint", "") == "https://collector.example:4318"
        for e in captured["exporters"]
    )


def test_otlp_target_falls_back_to_console_when_otlp_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "otlp+http://collector:4318")
    captured = _install_otel_stub(monkeypatch)
    # Force OTLP HTTP import to fail by removing any pre-existing entry
    # and patching __import__ to raise on the OTLP module.
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if "exporter.otlp.proto.http.trace_exporter" in name:
            raise ImportError("OTLP unavailable for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(hook="x", detector=None, decision="allow")
    err = capsys.readouterr().err

    # Assert
    assert "otel_exporter" in err
    # console fallback exporter was added to the same provider.
    assert any(
        e.__class__.__name__ == "_ConsoleSpanExporter" for e in captured["exporters"]
    )


def test_unknown_target_writes_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "totally-bogus")
    _install_otel_stub(monkeypatch)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(hook="x", detector=None, decision="allow")
    err = capsys.readouterr().err

    # Assert
    assert "unknown target" in err


def test_init_caches_after_first_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "console")
    _install_otel_stub(monkeypatch)
    import otel_exporter  # noqa: WPS433

    # Act
    otel_exporter.record_decision(hook="x", detector="d", decision="block")
    init_first = otel_exporter._INITIALIZED
    otel_exporter.record_decision(hook="x", detector="d", decision="allow")

    # Assert: second call should hit the early-return branch.
    assert init_first is True
    assert otel_exporter._INITIALIZED is True


def test_init_returns_false_when_target_cleared_after_first_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("MUTATION_METHOD_OTEL_EXPORTER", raising=False)
    import otel_exporter  # noqa: WPS433

    # Force already-initialized state with no tracer.
    otel_exporter._INITIALIZED = True
    otel_exporter._TRACER = None

    # Act
    result = otel_exporter._try_init()

    # Assert
    assert result is False


def test_record_decision_omits_optional_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("MUTATION_METHOD_OTEL_EXPORTER", "console")
    captured = _install_otel_stub(monkeypatch)
    import otel_exporter  # noqa: WPS433

    # Act: detector=None, file_path=None, confidence=None.
    otel_exporter.record_decision(
        hook="h", detector=None, decision="suppress", file_path=None, confidence=None
    )

    # Assert: detector, file, confidence keys not set.
    keys = {call.args[0] for call in captured["span"].set_attribute.call_args_list}
    assert "hook.detector" not in keys
    assert "hook.file" not in keys
    assert "hook.confidence" not in keys
    assert "hook.decision" in keys
    assert "hook.name" in keys
