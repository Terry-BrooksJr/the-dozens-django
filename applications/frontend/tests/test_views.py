# -*- coding: utf-8 -*-
"""
Tests for applications.frontend.views

Covers:
- LandingPageView — HTTP 200, HTML content type, template_name attribute.
- page_not_found_view — branches on content_type and path prefix:
    * application/json content type → JSON payload, 404 status
    * /api/  path prefix             → JSON payload, 404 status
    * /auth/ path prefix             → JSON payload, 404 status
    * /graphql path prefix           → JSON payload, 404 status
    * browser HTML request           → HTML response body, 404 status
    * JSON payload shape             → has detail / code / status_code keys

Notes
-----
- page_not_found_view is called directly via RequestFactory because Django's
  test client won't route to a 404 handler without DEBUG=False. RequestFactory
  bypasses URL routing and calls the view function directly.
- `request.content_type` reads META['CONTENT_TYPE'] (WSGI uppercase), so the
  RequestFactory call must use CONTENT_TYPE= (uppercase keyword).
- assertTemplateUsed() requires a response from the Django test *Client*, not
  from RequestFactory; so HTML responses are verified by checking the content
  type header and that the response body is non-empty rendered HTML instead.
"""

import json

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from applications.frontend.views import LandingPageView, page_not_found_view


# ---------------------------------------------------------------------------
# LandingPageView
# ---------------------------------------------------------------------------


class TestLandingPageView(SimpleTestCase):
    """GET / renders the landing page with a 200 status."""

    def test_get_returns_200(self):
        """GET / returns HTTP 200 OK."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_view_class_template_name(self):
        """LandingPageView.template_name is 'landing.html'."""
        self.assertEqual(LandingPageView.template_name, "landing.html")

    def test_response_content_type_is_html(self):
        """GET / returns an HTML content type."""
        resp = self.client.get("/")
        self.assertIn("text/html", resp["Content-Type"])

    def test_response_body_is_not_empty(self):
        """GET / returns a non-empty response body."""
        resp = self.client.get("/")
        self.assertTrue(len(resp.content) > 0)

    def test_post_method_not_allowed(self):
        """POST / is not allowed (TemplateView only accepts GET/HEAD)."""
        resp = self.client.post("/")
        self.assertEqual(resp.status_code, 405)


# ---------------------------------------------------------------------------
# page_not_found_view
# ---------------------------------------------------------------------------


class TestPageNotFoundView(SimpleTestCase):
    """Custom 404 handler serves JSON for API/auth/graphql requests and HTML for browsers."""

    def setUp(self):
        self.factory = RequestFactory()
        self.exception = Exception("page not found")

    def _call(self, path: str, *, content_type: str = "text/html; charset=utf-8"):
        """Build a GET request and call the 404 view directly.

        NOTE: CONTENT_TYPE must be the uppercase WSGI environ key so that
        Django's ``request.content_type`` property picks it up correctly.
        """
        request = self.factory.get(path, CONTENT_TYPE=content_type)
        return page_not_found_view(request, self.exception)

    # -----------------------------------------------------------------------
    # JSON response triggers — content-type
    # -----------------------------------------------------------------------

    def test_json_content_type_returns_json_response(self):
        """Requests with Content-Type: application/json get a JsonResponse."""
        resp = self._call("/some/page/", content_type="application/json")
        self.assertIsInstance(resp, JsonResponse)

    def test_json_content_type_returns_404_status(self):
        """JSON response has HTTP status 404."""
        resp = self._call("/some/page/", content_type="application/json")
        self.assertEqual(resp.status_code, 404)

    # -----------------------------------------------------------------------
    # JSON response triggers — path prefixes
    # -----------------------------------------------------------------------

    def test_api_path_root_returns_json(self):
        """/api/ prefix triggers a JSON response."""
        resp = self._call("/api/")
        self.assertIsInstance(resp, JsonResponse)

    def test_api_path_nested_returns_json(self):
        """/api/insults/123/ still triggers JSON (nested API path)."""
        resp = self._call("/api/insults/123/")
        self.assertIsInstance(resp, JsonResponse)

    def test_auth_path_returns_json(self):
        """/auth/ prefix triggers a JSON response."""
        resp = self._call("/auth/token/")
        self.assertIsInstance(resp, JsonResponse)

    def test_graphql_path_no_trailing_slash_returns_json(self):
        """/graphql (no trailing slash) triggers a JSON response."""
        resp = self._call("/graphql")
        self.assertIsInstance(resp, JsonResponse)

    def test_graphql_path_with_trailing_slash_returns_json(self):
        """/graphql/ (with trailing slash) triggers a JSON response."""
        resp = self._call("/graphql/")
        self.assertIsInstance(resp, JsonResponse)

    def test_graphql_playground_path_returns_json(self):
        """/graphql/playground/ triggers a JSON response."""
        resp = self._call("/graphql/playground/")
        self.assertIsInstance(resp, JsonResponse)

    def test_api_path_returns_404_status(self):
        """JSON response for /api/ path carries HTTP 404 status."""
        resp = self._call("/api/missing/")
        self.assertEqual(resp.status_code, 404)

    # -----------------------------------------------------------------------
    # JSON response body — shape and field values
    # -----------------------------------------------------------------------

    def _json_body(self, path: str, **kwargs):
        """Return the decoded JSON body for the given path."""
        resp = self._call(path, **kwargs)
        return json.loads(resp.content)

    def test_json_body_has_detail_key(self):
        """JSON body contains a 'detail' key."""
        body = self._json_body("/api/missing/")
        self.assertIn("detail", body)

    def test_json_body_has_code_key(self):
        """JSON body contains a 'code' key."""
        body = self._json_body("/api/missing/")
        self.assertIn("code", body)

    def test_json_body_code_is_not_found(self):
        """JSON body 'code' value is 'not_found'."""
        body = self._json_body("/api/missing/")
        self.assertEqual(body["code"], "not_found")

    def test_json_body_has_status_code_key(self):
        """JSON body contains a 'status_code' key."""
        body = self._json_body("/api/missing/")
        self.assertIn("status_code", body)

    def test_json_body_status_code_value_is_404(self):
        """JSON body 'status_code' field value is 404."""
        body = self._json_body("/api/missing/")
        self.assertEqual(body["status_code"], 404)

    def test_json_body_detail_message_contains_yo_momma(self):
        """The JSON detail message contains the branded 'yo momma' copy."""
        body = self._json_body("/api/missing/")
        self.assertIn("Yo momma", body["detail"])

    def test_json_body_same_across_api_and_graphql(self):
        """JSON response body is identical for /api/ and /graphql/ paths."""
        api_body = self._json_body("/api/missing/")
        gql_body = self._json_body("/graphql/missing/")
        self.assertEqual(api_body, gql_body)

    def test_json_body_same_for_json_content_type_and_api_path(self):
        """JSON body is identical whether triggered by content-type or path."""
        ct_body = self._json_body("/some/page/", content_type="application/json")
        path_body = self._json_body("/api/missing/")
        self.assertEqual(ct_body, path_body)

    # -----------------------------------------------------------------------
    # HTML 404 response — browser / non-API paths
    # -----------------------------------------------------------------------

    def test_browser_request_returns_html_status_404(self):
        """Browser (non-API) request returns HTTP 404."""
        resp = self._call("/some/random/page/")
        self.assertEqual(resp.status_code, 404)

    def test_browser_request_is_not_json_response(self):
        """Browser (non-API) request does NOT return a JsonResponse."""
        resp = self._call("/some/random/page/")
        self.assertNotIsInstance(resp, JsonResponse)

    def test_browser_request_returns_html_content_type(self):
        """Browser (non-API) request returns an HTML content type."""
        resp = self._call("/some/random/page/")
        self.assertIn("text/html", resp["Content-Type"])

    def test_browser_request_body_is_non_empty(self):
        """Browser (non-API) request returns a rendered HTML body."""
        resp = self._call("/some/random/page/")
        self.assertTrue(len(resp.content) > 0)

    def test_browser_request_body_is_not_valid_json(self):
        """Browser (non-API) response body is not valid JSON (it is HTML)."""
        resp = self._call("/some/random/page/")
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            json.loads(resp.content)

    def test_root_path_browser_request_is_html_not_json(self):
        """A browser 404 at an unknown path is HTML, not JSON."""
        resp = self._call("/completely/unknown/")
        self.assertNotIsInstance(resp, JsonResponse)

    def test_path_starting_with_api_keyword_midway_gets_html(self):
        """A path like /user/api/xyz is not an API path and gets HTML."""
        resp = self._call("/user/api/xyz")
        # Does NOT start with /api/ so should render HTML, not JSON.
        self.assertNotIsInstance(resp, JsonResponse)

    def test_path_with_auth_keyword_midway_gets_html(self):
        """A path like /user/auth/xyz is not an auth path and gets HTML."""
        resp = self._call("/user/auth/xyz")
        self.assertNotIsInstance(resp, JsonResponse)
