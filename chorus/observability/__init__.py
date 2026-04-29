# pyright: basic
"""Observability helpers for Chorus services.

Per ADR 0010, audit and decision-trail rows carry the active OpenTelemetry
trace and span IDs in their `metadata` jsonb so reviewers can join Postgres
audit rows to Tempo traces with ``metadata->>'otel.trace_id'``. This module
exposes the single helper that audit-write code uses to capture those IDs.

The OpenTelemetry SDK is imported lazily so contract, persistence, and test
code that does not need instrumentation does not pay the import cost. If no
SDK is installed or no span is currently active, the helper returns an
empty dict and the audit write is unaffected. The module sits at
``# pyright: basic`` because the lazy-import contract intentionally crosses
a typed boundary — the imported names exist only inside instrumented
services.
"""

from __future__ import annotations

from typing import Final

OTEL_TRACE_ID_KEY: Final[str] = "otel.trace_id"
OTEL_SPAN_ID_KEY: Final[str] = "otel.span_id"


def current_otel_ids() -> dict[str, str]:
    """Return the active span's trace/span IDs, or an empty dict.

    The IDs are returned as the lowercase hex strings produced by the OTel
    SDK helpers (32-char trace, 16-char span). The result is suitable for
    merging into the audit row's ``metadata`` jsonb under the
    ``otel.trace_id`` and ``otel.span_id`` keys.

    Returns an empty dict if the SDK is not installed, no span is currently
    active, or the active span has an invalid context.
    """

    try:
        from opentelemetry import trace  # pyright: ignore[reportMissingImports]
        from opentelemetry.trace import (  # pyright: ignore[reportMissingImports]
            format_span_id,
            format_trace_id,
        )
    except ImportError:
        return {}

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return {}
    return {
        OTEL_TRACE_ID_KEY: format_trace_id(ctx.trace_id),
        OTEL_SPAN_ID_KEY: format_span_id(ctx.span_id),
    }


def set_current_span_attributes(
    *,
    tenant_id: str | None = None,
    correlation_id: str | None = None,
    workflow_id: str | None = None,
) -> None:
    """Stamp ADR 0010 join keys on the active span when OTel is loaded."""

    try:
        from opentelemetry import trace  # pyright: ignore[reportMissingImports]
    except ImportError:
        return

    span = trace.get_current_span()
    if tenant_id is not None:
        span.set_attribute("chorus.tenant_id", tenant_id)
    if correlation_id is not None:
        span.set_attribute("chorus.correlation_id", correlation_id)
    if workflow_id is not None:
        span.set_attribute("chorus.workflow_id", workflow_id)


__all__ = [
    "OTEL_SPAN_ID_KEY",
    "OTEL_TRACE_ID_KEY",
    "current_otel_ids",
    "set_current_span_attributes",
]
