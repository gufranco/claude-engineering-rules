#!/usr/bin/env python3
"""OpenTelemetry decision exporter for blocking hooks.

Plan items 259-262 (D33). When `MUTATION_METHOD_OTEL_EXPORTER` is set,
every block / allow / suppress decision recorded by the hook is also
emitted as a span attribute through the OTel SDK.

  - `console`              spans printed to stderr; useful for local debug.
  - `otlp+http://h:p`      OTLP HTTP collector at the given endpoint.

When the env var is unset OR `opentelemetry-api` is not installed,
`record_decision()` is a no-op. The hook never crashes because telemetry
is unavailable.

Span attributes emitted per call:

    hook.name        e.g. "mutation-method-blocker"
    hook.detector    e.g. "array.push"
    hook.decision    "block" | "allow" | "suppress" | "warn"
    hook.file        relative path of the file analyzed
    hook.line        line number when applicable, else 0
    hook.latency_ms  wall time of the hook invocation
    hook.confidence  1-10 score (block decisions only)
"""

from __future__ import annotations

import os
import sys
from typing import Any


def _exporter_target() -> str:
    return (os.environ.get("MUTATION_METHOD_OTEL_EXPORTER") or "").strip()


def _enabled() -> bool:
    return bool(_exporter_target())


_INITIALIZED = False
_TRACER: Any = None


def _try_init() -> bool:
    """Lazy-init the tracer provider. Returns True on success."""
    global _INITIALIZED, _TRACER
    if _INITIALIZED:
        return _TRACER is not None
    _INITIALIZED = True

    target = _exporter_target()
    if not target:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        return False

    provider = TracerProvider()
    if target == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif target.startswith("otlp+http://") or target.startswith("otlp+https://"):
        endpoint = target.split("+", 1)[1]
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError:
            sys.stderr.write(
                "otel_exporter: opentelemetry-exporter-otlp-proto-http "
                "not installed; falling back to console.\n"
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        else:
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
    else:
        sys.stderr.write(
            f"otel_exporter: unknown target '{target}'; expected 'console' "
            "or 'otlp+http://host:port'.\n"
        )
        return False

    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("dot-claude.hooks")
    return True


def record_decision(
    *,
    hook: str,
    detector: str | None,
    decision: str,
    file_path: str | None = None,
    line: int = 0,
    latency_ms: float = 0.0,
    confidence: int | None = None,
) -> None:
    """Emit a single OTel span recording a hook decision.

    Safe to call regardless of whether the exporter is configured. When
    disabled or unavailable, this function is a fast no-op.
    """
    if not _enabled():
        return
    if not _try_init() or _TRACER is None:
        return
    span_name = f"{hook}.{decision}"
    with _TRACER.start_as_current_span(span_name) as span:
        span.set_attribute("hook.name", hook)
        span.set_attribute("hook.decision", decision)
        if detector is not None:
            span.set_attribute("hook.detector", detector)
        if file_path is not None:
            span.set_attribute("hook.file", file_path)
        span.set_attribute("hook.line", line)
        span.set_attribute("hook.latency_ms", float(latency_ms))
        if confidence is not None:
            span.set_attribute("hook.confidence", int(confidence))
