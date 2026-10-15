"""
Tests for common.middleware.RequestIDMiddleware.

Covers:
- Existing X-Request-ID header is propagated (not overwritten)
- Missing header causes a fresh UUID4 to be generated
- Generated ID is a valid UUID (won't collide across requests)
- request.request_id is attached to the request object
- X-Request-ID is written onto the response
- Loguru context is active during request processing (contextualise smoke-test)
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from common.middleware import RequestIDMiddleware


def _make_middleware(response=None):
    """Return a middleware instance whose inner callable returns *response*."""
    if response is None:
        response = MagicMock()
        response.__setitem__ = MagicMock()  # support response["X-Request-ID"] = ...
    get_response = MagicMock(return_value=response)
    mw = RequestIDMiddleware(get_response)
    return mw, get_response, response


class RequestIDMiddlewarePropagationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_existing_header_is_preserved(self):
        """Client-supplied X-Request-ID must not be replaced."""
        client_id = "my-client-request-id-123"
        request = self.factory.get("/", HTTP_X_REQUEST_ID=client_id)
        mw, _get_response, _response = _make_middleware()

        mw(request)

        self.assertEqual(request.request_id, client_id)

    def test_missing_header_generates_uuid(self):
        """No X-Request-ID header → middleware generates one."""
        request = self.factory.get("/")
        mw, _get_response, _response = _make_middleware()

        mw(request)

        generated_id = request.request_id
        self.assertIsNotNone(generated_id)
        # Must be parseable as a UUID
        parsed = uuid.UUID(generated_id)
        self.assertEqual(str(parsed), generated_id)

    def test_generated_ids_are_unique_per_request(self):
        """Two requests without a header must receive different IDs."""
        mw, _, _ = _make_middleware()
        r1 = self.factory.get("/")
        r2 = self.factory.get("/")

        mw(r1)
        # Need a fresh middleware instance (or the same — both fine since uuid4 is random)
        mw2, _, _ = _make_middleware()
        mw2(r2)

        self.assertNotEqual(r1.request_id, r2.request_id)

    def test_response_header_set_to_propagated_id(self):
        """X-Request-ID on the response must equal the inbound header value."""
        client_id = "trace-abc-789"
        request = self.factory.get("/", HTTP_X_REQUEST_ID=client_id)
        response = {}
        get_response = MagicMock(return_value=response)
        mw = RequestIDMiddleware(get_response)

        mw(request)

        self.assertEqual(response["X-Request-ID"], client_id)

    def test_response_header_set_to_generated_id(self):
        """X-Request-ID on the response must equal the generated ID when none supplied."""
        request = self.factory.get("/")
        response = {}
        get_response = MagicMock(return_value=response)
        mw = RequestIDMiddleware(get_response)

        mw(request)

        self.assertEqual(response["X-Request-ID"], request.request_id)

    def test_get_response_called_exactly_once(self):
        """The inner callable must be called exactly once per request."""
        request = self.factory.get("/")
        mw, get_response, _ = _make_middleware()

        mw(request)

        get_response.assert_called_once_with(request)


class RequestIDMiddlewareLogContextTests(TestCase):
    """Smoke-test that Loguru contextualise is entered during request handling."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_loguru_contextualize_called_with_request_id(self):
        """logger.contextualize must be entered with the request_id during the call."""
        request = self.factory.get("/", HTTP_X_REQUEST_ID="ctx-test-id")
        response = {}
        get_response = MagicMock(return_value=response)
        mw = RequestIDMiddleware(get_response)

        with patch("common.middleware.logger") as mock_logger:
            ctx_manager = MagicMock()
            ctx_manager.__enter__ = MagicMock(return_value=None)
            ctx_manager.__exit__ = MagicMock(return_value=False)
            mock_logger.contextualize.return_value = ctx_manager

            mw(request)

            mock_logger.contextualize.assert_called_once_with(request_id="ctx-test-id")
            ctx_manager.__enter__.assert_called_once()
            ctx_manager.__exit__.assert_called_once()


class RequestIDMiddlewareOrderingTests(TestCase):
    def test_runs_outside_the_cache_middleware(self):
        """It must wrap UpdateCache/FetchFromCache, so cache hits get their own
        ID and the stored response never carries a stale one."""
        from django.conf import settings

        mw = list(settings.MIDDLEWARE)
        rid = mw.index("common.middleware.RequestIDMiddleware")
        self.assertLess(rid, mw.index("django.middleware.cache.UpdateCacheMiddleware"))
        self.assertLess(
            rid, mw.index("django.middleware.cache.FetchFromCacheMiddleware")
        )


def _capture_extra(captured: dict) -> None:
    """Log one line through a temporary sink and copy its ``extra`` context."""
    from loguru import logger

    sink_id = logger.add(lambda m: captured.update(m.record["extra"]), level="DEBUG")
    try:
        logger.debug("inside")
    finally:
        logger.remove(sink_id)


class RequestIDMiddlewareTraceContextTests(TestCase):
    def test_trace_and_span_ids_are_bound_when_a_span_is_active(self):
        from opentelemetry import trace
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

        ctx = SpanContext(
            trace_id=0x0AF7651916CD43DD8448EB211C80319C,
            span_id=0x00F067AA0BA902B7,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        captured = {}

        def get_response(request):
            _capture_extra(captured)
            return MagicMock()

        mw = RequestIDMiddleware(get_response)
        with trace.use_span(NonRecordingSpan(ctx)):
            mw(RequestFactory().get("/"))

        self.assertEqual(captured["trace_id"], "0af7651916cd43dd8448eb211c80319c")
        self.assertEqual(captured["span_id"], "00f067aa0ba902b7")

    def test_no_trace_ids_without_an_active_span(self):
        captured = {}

        def get_response(request):
            _capture_extra(captured)
            return MagicMock()

        RequestIDMiddleware(get_response)(RequestFactory().get("/"))

        self.assertIn("request_id", captured)
        self.assertNotIn("trace_id", captured)
