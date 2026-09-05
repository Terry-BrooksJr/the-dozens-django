"""
Tests for applications.ld_integration.middleware.LaunchDarklyContextMiddleware.

Covers:
- request.ld_context is attached using context_from_request(request)
- The inner get_response callable is invoked exactly once with the request
- The middleware returns whatever get_response returns
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from applications.ld_integration.middleware import LaunchDarklyContextMiddleware


class LaunchDarklyContextMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_attaches_ld_context_from_context_from_request(self):
        request = self.factory.get("/")
        sentinel_ctx = object()
        get_response = MagicMock(return_value=MagicMock())
        mw = LaunchDarklyContextMiddleware(get_response)

        with patch(
            "applications.ld_integration.middleware.context_from_request",
            return_value=sentinel_ctx,
        ) as mock_ctx_from_request:
            mw(request)

        mock_ctx_from_request.assert_called_once_with(request)
        self.assertIs(request.ld_context, sentinel_ctx)

    def test_calls_get_response_exactly_once_with_request(self):
        request = self.factory.get("/")
        response = MagicMock()
        get_response = MagicMock(return_value=response)
        mw = LaunchDarklyContextMiddleware(get_response)

        result = mw(request)

        get_response.assert_called_once_with(request)
        self.assertIs(result, response)
