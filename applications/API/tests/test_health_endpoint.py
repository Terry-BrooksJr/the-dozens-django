"""
Tests for applications.API.endpoints.HealthEndpoint.

Covers:
- Default (integration) path: DB reachable, GraphQL schema executes cleanly,
  LaunchDarkly disabled by settings → overall "ok", HTTP 200.
- Database unavailable → "database": "unavailable", overall degraded, 503.
- GraphQL execution returning errors → "graphql": "error", degraded, 503.
- GraphQL raising an exception → "graphql": "error", degraded, 503.
- LaunchDarkly enabled + client initialized → "launchdarkly": "ok".
- LaunchDarkly enabled + client not initialized → "not_initialized", degraded.
- LaunchDarkly enabled + get_client() is None → "not_initialized", degraded.
- LaunchDarkly enabled + get_client() raises → "unavailable", degraded.
- Response always includes an ISO timestamp.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from applications.API.endpoints import HealthEndpoint

DB_TARGET = "applications.API.endpoints.connection.ensure_connection"
GRAPHQL_EXECUTE_TARGET = "applications.graphQL.schema.schema.execute"
LD_GET_CLIENT_TARGET = "applications.ld_integration.client.get_client"


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = HealthEndpoint.as_view()

    def _get(self):
        request = self.factory.get("/api/health/")
        return self.view(request)

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_all_healthy_returns_200_ok(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["database"], "ok")
        self.assertEqual(response.data["graphql"], "ok")
        self.assertEqual(response.data["launchdarkly"], "disabled")

    def test_response_includes_timestamp(self):
        response = self._get()

        self.assertIn("timestamp", response.data)
        self.assertTrue(response.data["timestamp"])

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_database_unavailable_returns_503(self):
        with patch(DB_TARGET, side_effect=Exception("connection refused")):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "degraded")
        self.assertEqual(response.data["database"], "unavailable")

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_graphql_errors_returns_503(self):
        fake_result = MagicMock(errors=["boom"])
        with patch(GRAPHQL_EXECUTE_TARGET, return_value=fake_result):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["graphql"], "error")

    @override_settings(LAUNCHDARKLY_ENABLED=False)
    def test_graphql_exception_returns_503(self):
        with patch(GRAPHQL_EXECUTE_TARGET, side_effect=RuntimeError("kaboom")):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["graphql"], "error")

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_launchdarkly_enabled_and_initialized_is_ok(self):
        mock_client = MagicMock()
        mock_client.is_initialized.return_value = True
        with patch(LD_GET_CLIENT_TARGET, return_value=mock_client):
            response = self._get()

        self.assertEqual(response.data["launchdarkly"], "ok")
        self.assertEqual(response.status_code, 200)

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_launchdarkly_enabled_but_not_initialized_is_degraded(self):
        mock_client = MagicMock()
        mock_client.is_initialized.return_value = False
        with patch(LD_GET_CLIENT_TARGET, return_value=mock_client):
            response = self._get()

        self.assertEqual(response.data["launchdarkly"], "not_initialized")
        self.assertEqual(response.status_code, 503)

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_launchdarkly_enabled_client_none_is_not_initialized(self):
        with patch(LD_GET_CLIENT_TARGET, return_value=None):
            response = self._get()

        self.assertEqual(response.data["launchdarkly"], "not_initialized")
        self.assertEqual(response.status_code, 503)

    @override_settings(LAUNCHDARKLY_ENABLED=True)
    def test_launchdarkly_enabled_get_client_raises_is_unavailable(self):
        with patch(LD_GET_CLIENT_TARGET, side_effect=RuntimeError("ld down")):
            response = self._get()

        self.assertEqual(response.data["launchdarkly"], "unavailable")
        self.assertEqual(response.status_code, 503)
