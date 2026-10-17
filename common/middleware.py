"""
common.middleware
~~~~~~~~~~~~~~~~

Application-wide Django middleware that is not tied to a specific app.
"""

from __future__ import annotations

import uuid

from loguru import logger
from opentelemetry import trace


class RequestIDMiddleware:
    """
    Propagate or generate a per-request correlation ID.

    Behaviour:
    - Reads ``X-Request-ID`` from the inbound request headers.  If absent,
      a UUID4 is generated.
    - Attaches the ID to ``request.request_id`` so views can reference it.
    - Binds the ID into Loguru's context via ``logger.contextualize`` so
      every log line emitted during this request automatically carries
      ``request_id`` in its ``extra`` dict (picked up by the LD sink and
      any structured formatter).
    - When an OpenTelemetry span is active (LaunchDarkly Observability
      auto-instruments Django), also binds its ``trace_id``/``span_id`` and
      tags the span with ``request_id``, so a log line leads to its trace
      and a trace to its logs.
    - Writes ``X-Request-ID`` back onto the response so callers can
      correlate client-side traces with server-side logs.
    """

    def __init__(self, get_response):
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Process the request inside a Loguru context bound to its request ID."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        with logger.contextualize(request_id=request_id, **_trace_context(request_id)):
            response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


def _trace_context(request_id: str):
    """Trace/span IDs of the active OpenTelemetry span, as log context.

    Returns an empty dict when no span is active (observability disabled, or
    a request outside instrumentation). Also tags the span with the request ID.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return {}
    span.set_attribute("request_id", request_id)
    return {
        "trace_id": trace.format_trace_id(ctx.trace_id),
        "span_id": trace.format_span_id(ctx.span_id),
    }
