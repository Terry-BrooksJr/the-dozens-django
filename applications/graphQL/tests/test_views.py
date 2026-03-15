# -*- coding: utf-8 -*-
"""
Tests for applications.graphQL.views

Covers:
- DozenGraphQLView.dispatch adds Content-Type, Cache-Control, and
  X-Content-Type-Options headers to API (non-playground) responses.
- Playground responses do NOT receive the API-specific headers.
- The API endpoint is CSRF-exempt (POST without a CSRF token succeeds).
- as_api_view() and as_playground_view() return callables.
"""

import json

from django.test import Client, SimpleTestCase, TestCase

from applications.graphQL.schema import schema
from applications.graphQL.views import DozenGraphQLView

# Minimal valid GraphQL query used to exercise the view without DB access.
_INTROSPECTION_BODY = json.dumps({"query": "{ __typename }"})
_JSON_CT = "application/json"

GRAPHQL_API_URL = "/graphql/"
GRAPHQL_PLAYGROUND_URL = "/graphql/playground/"


# ---------------------------------------------------------------------------
# Unit tests — class method returns
# ---------------------------------------------------------------------------


class TestDozenGraphQLViewClassMethods(SimpleTestCase):
    """as_api_view and as_playground_view return Django-compatible callables."""

    def test_as_api_view_returns_callable(self):
        """as_api_view(schema=...) returns a callable view."""
        view = DozenGraphQLView.as_api_view(schema=schema)
        self.assertTrue(callable(view))

    def test_as_playground_view_returns_callable(self):
        """as_playground_view(schema=...) returns a callable view."""
        view = DozenGraphQLView.as_playground_view(schema=schema)
        self.assertTrue(callable(view))

    def test_as_api_view_sets_graphiql_false(self):
        """as_api_view passes graphiql=False to GraphQLView."""
        # We can inspect the view closure's keywords via view_class attribute
        # that as_view() stores on the returned function.
        view_fn = DozenGraphQLView.as_api_view(schema=schema)
        # csrf_exempt wraps the inner view; introspect the inner function.
        inner = getattr(view_fn, "__wrapped__", view_fn)
        initkwargs = getattr(inner, "view_initkwargs", {})
        self.assertFalse(initkwargs.get("graphiql", True))

    def test_as_playground_view_sets_graphiql_true(self):
        """as_playground_view passes graphiql=True to GraphQLView."""
        view_fn = DozenGraphQLView.as_playground_view(schema=schema)
        initkwargs = getattr(view_fn, "view_initkwargs", {})
        self.assertTrue(initkwargs.get("graphiql", False))


# ---------------------------------------------------------------------------
# Integration tests — HTTP response headers
# ---------------------------------------------------------------------------


class TestDozenGraphQLViewResponseHeaders(TestCase):
    """DozenGraphQLView attaches the correct headers to API responses."""

    def _post_api(self, client=None):
        """POST a minimal query to the API endpoint."""
        c = client or self.client
        return c.post(GRAPHQL_API_URL, _INTROSPECTION_BODY, content_type=_JSON_CT)

    def _post_playground(self):
        """POST a minimal query to the playground endpoint."""
        return self.client.post(
            GRAPHQL_PLAYGROUND_URL, _INTROSPECTION_BODY, content_type=_JSON_CT
        )

    # --- API endpoint headers ------------------------------------------------

    def test_api_response_content_type_is_json(self):
        """API endpoint sets Content-Type: application/json."""
        resp = self._post_api()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp["Content-Type"])

    def test_api_response_cache_control_is_no_store(self):
        """API endpoint sets Cache-Control: no-store."""
        resp = self._post_api()
        self.assertEqual(resp["Cache-Control"], "no-store")

    def test_api_response_x_content_type_options_is_nosniff(self):
        """API endpoint sets X-Content-Type-Options: nosniff."""
        resp = self._post_api()
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")

    def test_api_response_body_is_valid_json(self):
        """API endpoint returns a parseable JSON body."""
        resp = self._post_api()
        body = json.loads(resp.content)
        self.assertIn("data", body)

    # --- Playground endpoint headers ----------------------------------------

    def test_playground_response_omits_cache_control_no_store(self):
        """Playground responses do NOT carry Cache-Control: no-store."""
        resp = self._post_playground()
        # The view skips the header block when graphiql=True.
        self.assertNotEqual(resp.get("Cache-Control", ""), "no-store")

    def test_playground_response_omits_cache_control_no_store_confirmed(self):
        """Cache-Control: no-store is set exclusively by our view logic, not by
        Django middleware.  Its absence on playground responses confirms that the
        dispatch() header block is correctly skipped when graphiql=True.
        """
        resp = self._post_playground()
        cache_ctrl = resp.get("Cache-Control", "")
        self.assertNotIn("no-store", cache_ctrl)

    # --- CSRF exemption ------------------------------------------------------

    def test_api_endpoint_csrf_exempt(self):
        """POST to /graphql/ succeeds without a CSRF token."""
        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post(GRAPHQL_API_URL, _INTROSPECTION_BODY, content_type=_JSON_CT)
        # Must NOT return 403 Forbidden due to CSRF.
        self.assertNotEqual(resp.status_code, 403)
        self.assertEqual(resp.status_code, 200)

    def test_api_endpoint_handles_get_with_query_param(self):
        """GET /graphql/?query=... also returns a 200 with our headers."""
        resp = self.client.get(
            GRAPHQL_API_URL,
            {"query": "{ __typename }"},
            HTTP_ACCEPT=_JSON_CT,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Cache-Control"], "no-store")
