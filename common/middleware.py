"""
common.middleware
~~~~~~~~~~~~~~~~

Application-wide Django middleware that is not tied to a specific app.
"""

from __future__ import annotations

import uuid

from loguru import logger


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
    - Writes ``X-Request-ID`` back onto the response so callers can
      correlate client-side traces with server-side logs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        with logger.contextualize(request_id=request_id):
            response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
