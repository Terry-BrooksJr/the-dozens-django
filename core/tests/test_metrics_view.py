"""
Tests for the /metrics endpoint bearer-token auth enforced by metrics_view.

Auth mechanism: Authorization: Bearer <METRICS_SCRAPE_TOKEN>
Compared with hmac.compare_digest to prevent timing attacks.

Covers:
- Correct token returns 200 and delegates to ExportToDjangoView
- Wrong token is rejected (403)
- Empty token in header is rejected
- Missing Authorization header is rejected
- Non-Bearer scheme (Basic, Token, etc.) is rejected
- Malformed header (no space) is rejected
- METRICS_SCRAPE_TOKEN unset in settings → always 403
- METRICS_SCRAPE_TOKEN empty string in settings → always 403
- Token comparison is case-sensitive
- Surrounding whitespace in provided token is stripped before compare
"""

from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from core.urls import metrics_view

PROMETHEUS_200_PATCH = "core.urls.ExportToDjangoView"
VALID_TOKEN = "super-secret-scrape-token-abc123"


def _request(auth_header: str | None = None):
    """Build a GET /metrics request with an optional Authorization header."""
    factory = RequestFactory()
    kwargs = {}
    if auth_header is not None:
        kwargs["HTTP_AUTHORIZATION"] = auth_header
    return factory.get("/metrics", **kwargs)


class MetricsViewTokenAllowedTests(TestCase):

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_correct_bearer_token_returns_200(self):
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            response = metrics_view(_request(f"Bearer {VALID_TOKEN}"))
        mock_export.assert_called_once()
        self.assertEqual(response.status_code, 200)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_correct_token_with_surrounding_whitespace_is_accepted(self):
        """Prometheus may send a token with trailing newline from credentials_file."""
        with patch(PROMETHEUS_200_PATCH) as mock_export:
            mock_export.return_value.status_code = 200
            response = metrics_view(_request(f"Bearer  {VALID_TOKEN}  "))
        mock_export.assert_called_once()
        self.assertEqual(response.status_code, 200)


class MetricsViewTokenRejectedTests(TestCase):

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_wrong_token_is_forbidden(self):
        response = metrics_view(_request("Bearer wrong-token"))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_empty_bearer_value_is_forbidden(self):
        response = metrics_view(_request("Bearer "))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_missing_authorization_header_is_forbidden(self):
        response = metrics_view(_request())
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_basic_auth_scheme_is_rejected(self):
        response = metrics_view(_request(f"Basic {VALID_TOKEN}"))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_token_scheme_is_rejected(self):
        response = metrics_view(_request(f"Token {VALID_TOKEN}"))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_malformed_header_no_space_is_rejected(self):
        """Header with no space between scheme and value (no Bearer prefix at all)."""
        response = metrics_view(_request(VALID_TOKEN))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_token_is_case_sensitive(self):
        response = metrics_view(_request(f"Bearer {VALID_TOKEN.upper()}"))
        self.assertEqual(response.status_code, 403)

    @override_settings(METRICS_SCRAPE_TOKEN=VALID_TOKEN)
    def test_partial_token_is_rejected(self):
        response = metrics_view(_request(f"Bearer {VALID_TOKEN[:10]}"))
        self.assertEqual(response.status_code, 403)


class MetricsViewUnconfiguredTests(TestCase):

    @override_settings(METRICS_SCRAPE_TOKEN="")
    def test_empty_setting_forbids_all_requests(self):
        """Empty token in settings means endpoint is locked down entirely."""
        response = metrics_view(_request(f"Bearer {VALID_TOKEN}"))
        self.assertEqual(response.status_code, 403)

    def test_missing_setting_forbids_all_requests(self):
        """If METRICS_SCRAPE_TOKEN is absent from settings, always 403."""
        from django.conf import settings as django_settings

        original = getattr(django_settings, "METRICS_SCRAPE_TOKEN", None)
        had_attr = hasattr(django_settings, "METRICS_SCRAPE_TOKEN")
        if had_attr:
            delattr(django_settings, "METRICS_SCRAPE_TOKEN")
        try:
            response = metrics_view(_request(f"Bearer {VALID_TOKEN}"))
            self.assertEqual(response.status_code, 403)
        finally:
            if had_attr and original is not None:
                django_settings.METRICS_SCRAPE_TOKEN = original
